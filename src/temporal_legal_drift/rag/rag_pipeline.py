"""Single-prompt RAG orchestration for temporal Indian-law analysis."""

from __future__ import annotations

import json
import os
import re
from hashlib import sha256
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .compose import COMPOSITION_VERSION, compose_general_answer, compose_out_of_scope, compose_version_answer, section_answer
from .analysis import analysis_id, facts_from_question, merge_scenario, scenario_request
from .determinations import DETERMINATIONS_VERSION, limit_for, answer_change, applicability, materiality, risk, textual_drift, validate_scenario
from .fingerprint import FINGERPRINT_VERSION, TLDS_VERSION, build_fingerprint, clause_pair, text_gate, validate_proposal
from .indiacode import IndiaCodeLiveRepository, source_guidance
from .metrics import METRICS_CONTRACT_VERSION, calculate_drift_metrics
from .question import ActCatalog, QuestionFrame, parse_question
from .retriever import HybridRetriever, RetrievedChunk
from .versions import VERSION_CLAIMS, VERSION_EVIDENCE_VERSION, VersionSelector

ANSWER_CONTRACT_VERSION = "rag-answer-v5"  # v5: fingerprint v1.2 with reading, determinations-v4, composition v2 (ADR 0017); v4: analysis IDs (ADR 0016)


INTENT_PATTERNS = {
    "diff_analysis": re.compile(r"\b(change[ds]?|difference|amend(?:ed|ment)?|before|after|drift|compare)\b", re.I),
    "statutory_lookup": re.compile(r"\b(section|clause|provision|statute|act|code|rule|regulation)\b", re.I),
}
LEGAL_CUES = (
    "shall", "must", "may", "prohibited", "penalty", "fine", "imprisonment",
    "liable", "means", "includes", "substituted", "inserted", "omitted",
)
# A non-reasoning model is used because this pipeline intentionally fixes
# temperature at 0.0 and requests strict JSON from Chat Completions.
DEFAULT_RAG_MODEL = "gpt-4.1-mini"
DEFAULT_OLLAMA_MODEL = "qwen3:4b"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 180
DEFAULT_REMOTE_TIMEOUT_SECONDS = 90
DEFAULT_OLLAMA_CONTEXT_TOKENS = 8192
MODE_INSTRUCTIONS = {
    "specific": (
        "Produce a clause-level comparison. Identify the section or provision, amendment operation, "
        "exact operative wording before and after, changed duties/rights/penalties/thresholds, and the "
        "source anchor. Prefer precision over general background."
    ),
    "generic": (
        "Produce a short high-level overview for a non-specialist. Explain the Act's purpose, the main "
        "legal themes that changed, and likely practical significance. Avoid line-by-line wording and "
        "do not list raw token differences unless essential."
    ),
}


@dataclass(frozen=True)
class GenerationResult:
    pre_baseline: str
    post_revision: str
    differences: list[str]
    conceptual_score: float | None
    method: str
    warning: str | None = None
    short_answer: str | None = None
    sources: tuple[dict[str, object], ...] = ()  # every excerpt the model was given, so each can be cited


class RagPipeline:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.retriever = HybridRetriever(self.root)
        self.live_repository = IndiaCodeLiveRepository()
        self._catalog: ActCatalog | None = None
        self._selector: VersionSelector | None = None

    def _components(self) -> tuple[ActCatalog, VersionSelector]:
        """Act catalog and version selector, built once from the index, graph v4 and the corpus manifest."""
        if self._catalog is None or self._selector is None:
            from temporal_legal_drift.corpus import CorpusManifest
            from temporal_legal_drift.versioning.consumer import GraphConsumer, IncompatibleGraphError

            chunks = self.retriever.ensure_index().get("chunks", [])
            try:
                consumer = GraphConsumer(self.root, "v4")
            except (IncompatibleGraphError, OSError, ValueError):
                consumer = None  # no verified graph: only footnote evidence can support a comparison
            self._catalog = ActCatalog.build(self.root, chunks, consumer.graph if consumer else None)
            amenders: dict[str, list[str]] = {}
            for amending, targets in self._catalog.relations.items():
                for target in targets:
                    amenders.setdefault(target, []).append(amending)
            risks = {e.entry_id: e.known_extraction_risk for e in CorpusManifest.from_file(self.root / "configs/corpus/pilot_v1.json").entries}
            self._selector = VersionSelector(consumer, chunks, risks, amenders)
        return self._catalog, self._selector

    def answer(self, query: str, mode: str, scenario: dict[str, object] | None = None, section: str | None = None) -> dict[str, object]:
        query = " ".join(str(query or "").split())
        if not query:
            raise ValueError("query is required")
        if len(query) > 4000:
            raise ValueError("query exceeds 4000 characters")
        if mode not in {"specific", "generic"}:
            raise ValueError("mode must be specific or generic")
        if section is not None and (not isinstance(section, str) or not re.fullmatch(r"\d{1,4}[A-Z]{0,4}", section.strip().upper())):
            raise ValueError("section must be a section number such as 99 or 45ZC")
        stated = validate_scenario(scenario)
        catalog, selector = self._components()
        frame = parse_question(query, catalog, reference_date=(stated or {}).get("reference_date"))
        selection = None
        if section is not None:  # a section chosen from the list for an Act-only question; the question itself is kept as asked
            section = section.strip().upper()
            if frame.principal is None:
                raise ValueError("a section can be chosen only for a question that names an Act")
            if frame.sections and frame.sections != [section]:
                raise ValueError("the question already names a different section")
            frame.sections, frame.asks_about_versions = [section], True
            selection = {"act_entry_id": frame.principal.entry_id, "act_name": frame.principal.name, "section": section,
                         "chosen_from": "section_candidates"}
        # Facts already written in the question are used; anything entered in the form overrides them.
        facts, sources = merge_scenario(stated or {}, facts_from_question(query), frame.reference_date)
        facts = validate_scenario(facts) if facts else None
        if frame.asks_about_versions:
            response = self._versioned_answer(query, mode, frame, facts, catalog, selector)
        elif frame.principal is None and frame.unresolved_act_phrases:
            response = self._out_of_scope_answer(query, mode, frame)
        else:
            restrict = {frame.principal.entry_id} if frame.principal else None
            focus = selector.section_chunk(frame.principal.entry_id, frame.sections[0]) if frame.principal and frame.sections else None
            if focus is None and frame.principal and frame.focus_terms:
                focus = self._topic_section(query, frame)
            response = self._attach_general(self._legacy_answer(query, mode, restrict=restrict, focus_chunk=focus), frame, facts, mode, focus)
        response["scenario_request"] = scenario_request(response["determinations"], response["fingerprint"], facts, sources)
        response["contract_version"], response["schema_version"] = ANSWER_CONTRACT_VERSION, "5.0.0"
        response["selection"] = selection
        response["analysis_id"] = analysis_id({
            "contract": ANSWER_CONTRACT_VERSION, "methods": [DETERMINATIONS_VERSION, FINGERPRINT_VERSION, TLDS_VERSION, COMPOSITION_VERSION, METRICS_CONTRACT_VERSION],
            "query": query, "mode": mode, "scenario": facts, "selection": selection, "evidence_selection": VERSION_EVIDENCE_VERSION,
            "generation": response["answer"].get("generation_method"),
            "index": self.retriever.status().get("index_identity"), "graph": getattr(selector.consumer, "graph_sha256", None),
            "release": _active_release(self.root)})
        return response

    def _graph_alignment(self, pre: RetrievedChunk, post: RetrievedChunk) -> tuple[dict[str, object] | None, list[str]]:
        from temporal_legal_drift.versioning.consumer import GraphConsumer, IncompatibleGraphError

        try:
            consumer = GraphConsumer(self.root, "v4")
        except (IncompatibleGraphError, OSError, ValueError):
            return None, []  # no verified graph: abstain from version comparison
        aligned = consumer.aligned_fragments(str(pre.metadata.get("entry_id")), str(post.metadata.get("entry_id")), pre.text)
        candidates = getattr(consumer, "last_alignment_candidates", [])
        return aligned, candidates if len(candidates) > 1 else []

    def _source_fidelity_warnings(self, *items: RetrievedChunk | None) -> list[dict[str, str]]:
        from temporal_legal_drift.corpus import CorpusManifest

        risks = {entry.entry_id: entry.known_extraction_risk for entry in CorpusManifest.from_file(
            self.root / "configs/corpus/pilot_v1.json").entries if entry.known_extraction_risk}
        entry_ids = dict.fromkeys(str(item.metadata.get("entry_id")) for item in items if item)
        warnings = [
            {"entry_id": entry_id, "warning": "source text unreadable or unreliable", "detail": str(risks[entry_id])}
            for entry_id in entry_ids if entry_id in risks
        ]
        for item in items:
            withheld = int((item.metadata.get("quarantined_lines_on_page") or 0) if item else 0)
            if withheld and all(w["entry_id"] != str(item.metadata.get("entry_id")) for w in warnings):
                warnings.append({"entry_id": str(item.metadata.get("entry_id")), "warning": "source text partly withheld",
                                 "detail": f"{withheld} line(s) on this page (Hindi text layer or garbled legacy-font text) were withheld "
                                           "as unverifiable; only the remaining text was used. Check the official PDF."})
        return warnings

    def status(self) -> dict[str, object]:
        retrieval = self.retriever.status()
        return {
            **retrieval,
            "generation": {
                "provider": _rag_provider() if _llm_configured() else "extractive_fallback",
                "temperature": 0.0,
                "model": _llm_model() if _llm_configured() else None,
                "grounded_output_required": True,
            },
            "notice": "The local index is a research aid. India Code remains the authoritative source.",
            "repository_mode": "live_indiacode_with_local_evidence_cache",
            "live_repository_enabled": os.environ.get("TLD_LIVE_INDIA_CODE", "1") != "0",
        }

    def rebuild(self) -> dict[str, object]:
        return self.retriever.rebuild()

    def _legacy_answer(self, query: str, mode: str, *, restrict: set[str] | None = None,
                       focus_chunk: dict[str, object] | None = None) -> dict[str, object]:
        """General answers (rag-answer-v1 body); restricted to the Act the question names when one was resolved."""
        intent = _classify_intent(query)
        retrieved = self.retriever.search(query, limit=40, entry_ids=restrict)
        if focus_chunk is not None:  # the named section's own text leads
            meta = dict(focus_chunk.get("metadata", {}))
            retrieved = [RetrievedChunk(str(focus_chunk.get("chunk_id") or f"section:{meta.get('entry_id')}"), str(focus_chunk.get("text", "")),
                                        1.0, 1.0, 1.0, meta), *retrieved]
        live = (
            self.live_repository.search_sections(query)
            if os.environ.get("TLD_LIVE_INDIA_CODE", "1") != "0" and restrict is None
            else None
        )
        # Merge current India Code sections with the reproducible local cache.
        # Previously, even a weak local match prevented live evidence from
        # being considered, which caused unrelated opening-page fallbacks.
        # Live current sections are never labelled as historical versions.
        if live is not None:
            live_chunks = [
                RetrievedChunk(
                    chunk_id=str(item["chunk_id"]),
                    text=str(item["text"]),
                    score=float(item["score"]),
                    semantic_score=float(item["semantic_score"]),
                    lexical_score=float(item["lexical_score"]),
                    metadata=dict(item["metadata"]),
                )
                for item in live.chunks
            ]
            by_id = {item.chunk_id: item for item in [*retrieved, *live_chunks]}
            retrieved = sorted(by_id.values(), key=lambda item: (-item.score, item.chunk_id))[:40]
        relation = self.retriever.relation_for_results(retrieved) if restrict is None else None
        if relation:
            related_ids = {relation["amending_entry_id"], relation["target_entry_id"]}
            related = self.retriever.search(query, limit=12, entry_ids=related_ids)
            by_id = {item.chunk_id: item for item in [*retrieved, *related]}
            retrieved = sorted(by_id.values(), key=lambda item: (-item.score, item.chunk_id))
        pre, post, pair_status = _select_pair(retrieved, relation)
        guidance = source_guidance(query)

        if pre is None and post is None:
            return _insufficient_response(query, mode, intent, guidance, self.status())

        answer_type = "comparison" if pre is not None and post is not None else "single_document_summary"
        if answer_type == "single_document_summary" and post is not None:
            if focus_chunk is None:
                post = self.retriever.overview_chunk(str(post.metadata.get("entry_id"))) or post
            document_chunks = self.retriever.document_chunks(str(post.metadata.get("entry_id")))
            generation = _generate_single_document(query, mode, post, document_chunks)
        else:
            generation = _generate(query, mode, pre, post)
        history_source = post or pre
        listed_history = self.retriever.listed_amendments(
            str(history_source.metadata.get("entry_id")) if history_source else None
        )
        live_amendments = list(live.amendments) if live is not None else []
        known_titles = {str(item.get("title", "")).lower() for item in live_amendments}
        for title in listed_history:
            if title.lower() in known_titles:
                continue
            years = re.findall(r"(?:19|20)\d{2}", title)
            live_amendments.append({
                "title": title,
                "target_act": history_source.metadata.get("act_name") if history_source else None,
                "year": years[-1] if years else None,
                "official_identifier": history_source.metadata.get("official_identifier") if history_source else None,
                "source_url": history_source.metadata.get("source_url") if history_source else guidance["url"],
                "record_type": "listed_in_current_consolidated_act",
            })
            known_titles.add(title.lower())
        metadata_coverage = _metadata_coverage(pre, post)
        metric_document = None
        scoring = _select_scoring_evidence(pre, post, query) if pre is not None and post is not None else None
        graph_alignment = None
        if pre is not None and post is not None and scoring is None:
            graph_alignment, competing = self._graph_alignment(pre, post)
            if competing:
                pair_status = "ambiguous_graph_candidates"  # several transitions fit: keep them, do not choose
                graph_alignment = {"competing_transition_ids": competing}
            elif graph_alignment is not None:
                scoring = (str(graph_alignment["before_text"]), str(graph_alignment["after_text"]), "graph_v4_transition_fragments")
                pair_status = "graph_aligned_amendment_fragments"
            else:
                # Two excerpts that are not shown to be the same provision are not versions.
                pair_status = "instruction_and_consolidated_text_not_aligned"
        if pair_status == "ambiguous_graph_candidates":
            scoring = None
        if scoring is not None and scoring[2] == "query_section_reconstruction":
            pair_status = "consolidated_footnote_reconstruction"
        if pre is not None and post is not None and scoring is not None:
            metric_pre_text, metric_post_text, selection_method = scoring
            metric_document = calculate_drift_metrics(
                metric_pre_text,
                metric_post_text,
                pre_vector=self.retriever.embed_text(metric_pre_text),
                post_vector=self.retriever.embed_text(metric_post_text),
                conceptual_override=generation.conceptual_score,
                conceptual_method="llm_judge" if generation.conceptual_score is not None and generation.method == "llm_grounded" else "legal_cue_proxy",
                retrieval_scores=(pre.score, post.score),
                metadata_coverage=metadata_coverage,
            )
            metric_document["score_basis"] = {
                "selection": "automatic_backend_retrieval_from_user_prompt",
                "query": query,
                "selection_method": selection_method,
                "presentation_mode_independent": True,
                "pre_source_anchor": pre.metadata.get("source_anchor"),
                "post_source_anchor": post.metadata.get("source_anchor"),
                "pre_excerpt": _bounded_text(metric_pre_text, 1200),
                "post_excerpt": _bounded_text(metric_post_text, 1200),
                "user_supplied_before_after_text": False,
                "graph_alignment": graph_alignment,
            }
            metric_document["reliability"] = _reliability(pre, post, pair_status, graph_alignment)
            metric_document["question_relevance"] = _question_relevance(query, metric_pre_text, metric_post_text, graph_alignment)
        citations = _citations(pre, post)
        verification = _verification(query, pre, post, pair_status, generation, citations, metric_document is not None)
        for source in generation.sources:  # model-generated answers cite every excerpt the model saw
            if all(c.get("chunk_id") != source["chunk_id"] for c in citations):
                meta = source["metadata"]
                citations.append({"label": "model_context", "chunk_id": source["chunk_id"], "entry_id": meta.get("entry_id"),
                                  "act_name": meta.get("act_name"), "version": meta.get("version"), "document_type": meta.get("document_type"),
                                  "date": meta.get("date"), "source_anchor": meta.get("source_anchor"), "official_identifier": meta.get("official_identifier"),
                                  "source_url": meta.get("source_url"), "official_portal_url": meta.get("official_portal_url"), "filename": meta.get("filename")})
        answer_markdown = _answer_markdown(generation, citations, guidance, answer_type)
        return {
            "schema_version": "1.0.0",
            "query": query,
            "mode": mode,
            "intent": intent,
            "answer": {
                "answer_type": answer_type,
                "short_answer": generation.short_answer,
                "pre_amendment_baseline": generation.pre_baseline,
                "post_amendment_revision": generation.post_revision,
                "key_differences": generation.differences,
                "markdown": answer_markdown,
                "generation_method": generation.method,
                "generation_warning": generation.warning,
            },
            "metrics": metric_document,
            "source_fidelity_warnings": self._source_fidelity_warnings(pre, post),
            "comparison": _comparison_record(
                query, mode, pre, post, pair_status, metric_document, graph_alignment,
                self._source_fidelity_warnings(pre, post), generation,
            ),
            "retrieval": {
                "pair_status": pair_status,
                "candidate_count": len(retrieved),
                "relation": relation,
                "pre": pre.to_dict() if pre else None,
                "post": post.to_dict() if post else None,
                "live_indiacode": {
                    "attempted": live is not None,
                    "candidate_count": len(live.chunks) if live is not None else 0,
                    "amendment_count": len(live_amendments),
                    "amendments": live_amendments,
                    "error": live.error if live is not None else None,
                    "role": "current-law and amendment-history supplement; not automatically a historical pre/post pair",
                },
            },
            "citations": citations,
            "verification": verification,
            "source_guidance": guidance,
            "repository": self.status(),
            "limitations": [
                "Drift scores measure differences between retrieved excerpts, not legal correctness.",
                "Alignment accuracy is retrieval and evidence coverage, not expert-validated answer accuracy.",
                "Confirm the complete provision, commencement and applicability on India Code before relying on the answer.",
            ],
        }

    # ---------------- rag-answer-v2 ----------------
    def _topic_section(self, query: str, frame: QuestionFrame) -> dict[str, object] | None:
        """The section of the named Act whose heading names the question's topic; else the best-ranked section text."""
        _, selector = self._components()
        for row in selector.suggest_sections(frame.principal.entry_id, frame.focus_terms, limit=3):
            if row["heading"] and any(term in re.findall(r"[a-z0-9]+", row["heading"].casefold()) for term in frame.focus_terms):
                chunk = selector.section_chunk(frame.principal.entry_id, row["section"])
                if chunk:
                    return {**chunk, "section": row["section"]}
        for item in self.retriever.search(query, limit=20, entry_ids={frame.principal.entry_id}):
            text = item.text.casefold()
            if item.metadata.get("source_kind") == "provision_version" and "arrangement of sections" not in text \
                    and any(term in re.findall(r"[a-z0-9]+", text) for term in frame.focus_terms):
                return {"chunk_id": item.chunk_id, "text": item.text, "metadata": item.metadata}
        return None

    def _versioned_answer(self, query: str, mode: str, frame: QuestionFrame, scenario: dict[str, object] | None,
                          catalog: ActCatalog, selector: VersionSelector) -> dict[str, object]:
        names = {entry: f"{info['name']}" + ("" if info["kind"] == "principal" or not info["year"] or info["year"] in info["name"] else f" {info['year']}")
                 for entry, info in catalog.entries.items()}
        names = {entry: name.replace(" Act ", " (Amendment) Act ", 1) if catalog.entries[entry]["kind"] == "amending" and "Amendment" not in name else name
                 for entry, name in names.items()}
        versions = selector.select(frame)
        if versions["reason_code"] == "SECTION_NOT_IDENTIFIED" and frame.principal:
            versions["section_candidates"] = selector.discover(frame, _evidence_gate, names)
        supported = versions["support_class"] in VERSION_CLAIMS
        metrics = None
        if supported and str(versions["before"]["text"]).strip():
            items = {item["evidence_id"]: item for item in versions["evidence"]}
            pre_text, post_text = items[versions["before"]["evidence_id"]]["text"], items[versions["after"]["evidence_id"]]["text"]
            metrics = calculate_drift_metrics(
                pre_text, post_text, pre_vector=self.retriever.embed_text(pre_text), post_vector=self.retriever.embed_text(post_text),
                conceptual_method="legal_cue_proxy", retrieval_scores=(1.0, 1.0), metadata_coverage=1.0)
            # Alignment quality is a retrieval-similarity measure; this evidence was chosen by identity, so it does not apply.
            metrics["evidence_alignment_quality_percent"] = metrics["alignment_accuracy_percent"] = None
            metrics.setdefault("unavailable_reasons", {})["evidence_alignment_quality"] = (
                "evidence was selected by Act and section identity, not by similarity, so retrieval alignment quality does not apply")
            metrics["score_basis"] = {
                "selection": "provision_identity_from_question", "query": query, "selection_method": versions["support_class"].lower(),
                "presentation_mode_independent": True, "pre_excerpt": _bounded_text(pre_text, 1200), "post_excerpt": _bounded_text(post_text, 1200),
                "pre_source_anchor": _anchor(items[versions["before"]["evidence_id"]]), "post_source_anchor": _anchor(items[versions["after"]["evidence_id"]]),
                "user_supplied_before_after_text": False, "graph_alignment": None,
                "note": "Selected by Act and section identity, not by similarity; the alignment-quality figure reflects that."}
            temporal = ({"status": "EFFECTIVE_DATE_EVIDENCED", "date": versions["effective_date"], "basis": "Act-wide commencement in graph v4"}
                        if versions.get("effective_date") else
                        {"status": "FOOTNOTE_STATED_DATE_UNVERIFIED", "date": versions.get("footnote_stated_date"), "basis": "date printed in the footnote"}
                        if versions.get("footnote_stated_date") else {"status": "UNRESOLVED", "date": None, "basis": "no supported effective date"})
            metrics["reliability"] = {"evidence_coverage": "BOTH_SIDES", "pairing": versions["support_class"], "temporal_certainty": temporal,
                                      "retrieval_relevance": None, "relation_verification": versions.get("relation_verification"),
                                      "note": "Reliability indicators are reported separately; they are not drift and not accuracy."}
            metrics["question_relevance"] = {"status": "MATCHES_REQUESTED_SECTION", "requested_section": frame.sections[0],
                                             "compared_section": frame.sections[0], "answers_scenario_question": False,
                                             "explanation": "The score measures how the selected clause's wording moved; whether your answer changes is reported separately."}
        if metrics:
            metrics["legacy_diagnostic"] = {"fields": ["overall_drift_percent", "conceptual_drift_percent"],
                                            "note": "Legacy drift-metrics-v3 diagnostic on amendment fragments; it mixes wording and legal-cue signals. "
                                                    "Use fingerprint.wording_drift and fingerprint.rule_drift instead."}
        mat = materiality(self.root, frame, versions)
        risk_result, comparison = risk(self.root, frame, versions, scenario)
        timing = applicability(frame, versions, scenario)
        applies = (timing["details"].get("scenario_applicability") or {}).get("applies")
        fingerprint = build_fingerprint(versions, scenario, self.retriever.embed_text, comparison, timing["summary"] if applies else None,
                                        proposer=_rule_delta_proposer(), asks_about_versions=True, applies=applies)
        change = answer_change(frame, versions, scenario, comparison)
        outcome = fingerprint["outcome_drift"]
        if scenario and outcome["label"] in {"Changed", "Unchanged"}:  # for a scenario, the answer change IS the outcome drift
            change = {**change, "state": outcome["state"], "label": "Changes" if outcome["label"] == "Changed" else "Does not change",
                      "summary": outcome["summary"], "reason": outcome["reason"],
                      "method": "outcome-drift-v1"}
        elif change["state"] == "NEEDS_FACTS" and comparison is None and (outcome.get("limit") or {}).get("kind") == "method":
            # No fact could decide this change, so do not ask for facts here either.
            change = {**change, "state": outcome["state"], "label": None, "summary": outcome["summary"], "reason": outcome["reason"],
                      "needs": [], "limit": outcome["limit"], "method": "outcome-drift-v1"}
        wording = fingerprint["wording_drift"]
        drift = {**textual_drift(frame, versions, metrics), "state": wording["state"], "label": wording["label"], "summary": wording["summary"],
                 "limit": wording.get("limit"),
                 "reason": wording["reason"], "method": "alias of fingerprint.wording_drift (textual_drift is deprecated in determinations-v2)",
                 "evidence_ids": wording["evidence_ids"], "details": {"deprecated": True, "use": "fingerprint.wording_drift"}}
        determinations = {"version": DETERMINATIONS_VERSION, "textual_drift": drift, "materiality": mat, "applicability": timing,
                          "answer_change": change, "risk": risk_result}
        composed = compose_version_answer(frame, mode, versions, determinations, names, fingerprint)
        citations = [{"label": item["role"], "evidence_id": item["evidence_id"], "chunk_id": None, "entry_id": item["entry_id"],
                      "act_name": item["act_name"], "version": item["scope"], "document_type": None, "date": None,
                      "source_anchor": _anchor(item), "page": item["page"], "line": item["line"], "pdf_url": item["pdf_url"],
                      "official_identifier": None, "source_url": item["official_url"], "official_portal_url": item["official_url"],
                      "verbatim": item["verbatim"], "text_reliability": item["text_reliability"]} for item in versions["evidence"]]
        fidelity = [{"entry_id": item["entry_id"], "warning": "source text unreadable or unreliable",
                     "detail": "The cited document has a known unreliable text layer; treat its wording as unverified."}
                    for item in versions["evidence"] if item["text_reliability"] == "UNRELIABLE_TEXT_LAYER"]
        if not supported and frame.principal:  # the amendments asked about may themselves be unreadable
            for amending in sorted(a for a, targets in catalog.relations.items() if frame.principal.entry_id in targets):
                if selector.risk.get(amending) and (not frame.amending or frame.amending.entry_id == amending):
                    fidelity.append({"entry_id": amending, "warning": "source text unreadable or unreliable", "detail": str(selector.risk[amending])})
        before_section = next((sec for sec in composed["sections"] if sec["id"] == "before"), None)
        after_section = next((sec for sec in composed["sections"] if sec["id"] == "after"), None)
        guidance = source_guidance(query)
        return {
            "schema_version": "3.0.0", "contract_version": ANSWER_CONTRACT_VERSION, "query": query, "mode": mode,
            "intent": "diff_analysis", "question_frame": frame.to_dict(), "scenario": scenario,
            "answer": {
                "answer_type": "comparison" if supported else "version_abstention",
                "direct_answer": composed["direct_answer"], "sections": composed["sections"], "answer_limitations": composed["limitations"],
                "short_answer": composed["direct_answer"],
                "pre_amendment_baseline": before_section["text"] if before_section else "",
                "post_amendment_revision": after_section["text"] if after_section else "",
                "key_differences": [sec["text"] for sec in composed["sections"] if sec["id"] in {"what_changed", "effect", "why"}],
                "markdown": _v2_markdown(composed), "generation_method": "grounded_composition", "generation_warning": None,
            },
            "metrics": metrics,
            "fingerprint": fingerprint,
            "determinations": determinations,
            "evidence": versions["evidence"],
            "version_evidence": {k: v for k, v in versions.items() if k != "evidence"},
            "source_fidelity_warnings": fidelity,
            "comparison": _v2_comparison_record(query, mode, frame, versions, metrics, determinations, fidelity),
            "retrieval": {"pair_status": versions["support_class"].lower(), "candidate_count": len(versions.get("candidates") or []),
                          "relation": {"amending_entry_id": versions.get("amending_entry"), "target_entry_id": frame.principal.entry_id if frame.principal else None},
                          "pre": None, "post": None, "selection": "act_and_section_identity",
                          "live_indiacode": {"attempted": False, "candidate_count": 0, "amendment_count": 0, "amendments": [], "error": None,
                                             "role": "not used for version comparisons; India Code remains the authoritative source"}},
            "citations": citations,
            "verification": _v2_verification(frame, versions, citations),
            "source_guidance": guidance,
            "repository": self.status(),
            "limitations": composed["limitations"],
        }

    def _out_of_scope_answer(self, query: str, mode: str, frame: QuestionFrame) -> dict[str, object]:
        composed = compose_out_of_scope(frame)
        out = {"state": "OUT_OF_SCOPE", "label": None, "summary": "Not in the corpus.", "method": None, "evidence_ids": [],
               "reason": "Nothing to assess: the Act is outside the local corpus.",
               "limit": limit_for("INSUFFICIENT_EVIDENCE", "The Act is not in the local corpus; check India Code.", "evidence"),
               "details": {}, "needs": [], "review_status": "UNREVIEWED", "legal_validation": "UNVERIFIED"}
        response = _insufficient_response(query, mode, _classify_intent(query), source_guidance(query), self.status())
        response["answer"].update({"answer_type": "out_of_scope", "direct_answer": composed["direct_answer"], "sections": [],
                                   "answer_limitations": composed["limitations"], "short_answer": composed["direct_answer"]})
        response.update({"schema_version": "3.0.0", "contract_version": ANSWER_CONTRACT_VERSION, "question_frame": frame.to_dict(),
                         "scenario": None, "evidence": [], "comparison": None, "source_fidelity_warnings": [],
                         "fingerprint": build_fingerprint({}, None, self.retriever.embed_text, None, None, asks_about_versions=False),
                         "determinations": {"version": DETERMINATIONS_VERSION, **{k: dict(out) for k in ("textual_drift", "materiality", "applicability", "answer_change", "risk")}}})
        return response

    def _attach_general(self, response: dict[str, object], frame: QuestionFrame, scenario: dict[str, object] | None, mode: str,
                        focus: dict[str, object] | None = None) -> dict[str, object]:
        answer = response["answer"]
        evidence = []
        for number, citation in enumerate(response.get("citations") or [], start=1):
            page = re.search(r"page:(\d+)", str(citation.get("source_anchor") or ""))
            filename = citation.get("filename")
            for chunk in (response.get("retrieval") or {}).get("pre"), (response.get("retrieval") or {}).get("post"):
                if chunk and chunk.get("chunk_id") == citation.get("chunk_id"):
                    filename = (chunk.get("metadata") or {}).get("filename")
            evidence.append({"evidence_id": f"E{number}", "role": "act_text_excerpt", "entry_id": citation.get("entry_id"),
                             "act_name": citation.get("act_name"), "page": int(page.group(1)) if page else None,
                             "pdf_url": f"/corpus/{filename}#page={page.group(1)}" if filename and page else None,
                             "official_url": citation.get("source_url") or citation.get("official_portal_url"), "verbatim": True})
            citation["evidence_id"] = f"E{number}"
            citation["page"] = int(page.group(1)) if page else None
            citation["pdf_url"] = evidence[-1]["pdf_url"]
        general = {"state": "OUT_OF_SCOPE", "label": None, "evidence_ids": [], "details": {}, "needs": [], "method": None,
                   "review_status": "UNREVIEWED", "legal_validation": "UNVERIFIED"}
        reasons = {"textual_drift": "This question does not ask how a provision changed, so no versions are compared.",
                   "applicability": "Which version applies matters only when two versions are compared.",
                   "materiality": "Materiality is assessed for a specific amendment; none was asked about.",
                   "answer_change": "The question is about the law as written, not a change over time.",
                   "risk": "Risk is assessed only for a named provision with a modelled obligation and your facts."}
        determinations = {"version": DETERMINATIONS_VERSION, **{k: {**general, "summary": "Not applicable to this question.", "reason": v,
                                                                       "limit": limit_for("OUT_OF_SCOPE", v)} for k, v in reasons.items()}}
        if answer.get("answer_type") == "insufficient_evidence":
            composed = {"direct_answer": answer.get("short_answer"), "sections": [], "limitations": ["No local evidence supported the query."]}
        else:
            opening = str(answer.get("short_answer") or answer.get("post_amendment_revision") or "")
            if focus is not None and str(answer.get("generation_method", "")).startswith("extractive"):
                primary = (focus.get("metadata") or {}).get("primary_sections") or [None]
                opening = section_answer(str(focus.get("text", "")), frame.focus_terms, mode, str((focus.get("metadata") or {}).get("act_name") or ""),
                                         str(focus.get("section") or (frame.sections[0] if frame.sections else primary[0]) or "") or None) or opening
            composed = compose_general_answer(frame, mode, opening, [str(p) for p in answer.get("key_differences") or []],
                                              [e["evidence_id"] for e in evidence])
        answer.update({"direct_answer": composed["direct_answer"], "sections": composed["sections"], "answer_limitations": composed["limitations"]})
        response.update({"schema_version": "3.0.0", "contract_version": ANSWER_CONTRACT_VERSION, "question_frame": frame.to_dict(),
                         "scenario": scenario, "evidence": evidence, "determinations": determinations,
                         "fingerprint": build_fingerprint({}, None, self.retriever.embed_text, None, None, asks_about_versions=False)})
        return response


def _classify_intent(query: str) -> str:
    for name, pattern in INTENT_PATTERNS.items():
        if pattern.search(query):
            return name
    return "general_qa"


def _select_pair(
    results: list[RetrievedChunk], relation: dict[str, str] | None
) -> tuple[RetrievedChunk | None, RetrievedChunk | None, str]:
    if relation:
        amending = relation["amending_entry_id"]
        target = relation["target_entry_id"]
        pre = next((item for item in results if item.metadata.get("entry_id") == amending), None)
        post = next((item for item in results if item.metadata.get("entry_id") == target), None)
        if pre and post:
            return pre, post, "paired_amendment_instruction_and_consolidated_version"
        return pre, post, "partial_pair_missing_relevant_counterpart"
    if results:
        return None, results[0], "single_relevant_document_no_version_pair"
    return None, None, "no_relevant_evidence"


def _generate(
    query: str,
    mode: str,
    pre: RetrievedChunk | None,
    post: RetrievedChunk | None,
) -> GenerationResult:
    if _llm_configured():
        try:
            return _llm_generate(query, mode, pre, post)
        except (ValueError, HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            fallback = _extractive_generate(query, mode, pre, post)
            return GenerationResult(
                fallback.pre_baseline, fallback.post_revision, fallback.differences,
                None, "extractive_fallback", f"Configured LLM was unavailable: {type(error).__name__}",
            )
    return _extractive_generate(query, mode, pre, post)


def _llm_configured() -> bool:
    return _ollama_available() if _rag_provider() == "ollama_local" else bool(_llm_api_key())


def _rag_provider() -> str:
    configured = os.environ.get("TLD_RAG_PROVIDER", "").strip().lower()
    if configured in {"ollama", "ollama_local"}:
        return "ollama_local"
    if configured in {"openai", "openai_compatible"}:
        return "openai_compatible"
    return "openai_compatible" if _llm_api_key() else "ollama_local"


def _ollama_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=0.2):
            return True
    except OSError:
        return False


def _llm_api_key() -> str:
    """Read a server-side credential without ever sending it to the browser."""
    return os.environ.get("TLD_RAG_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""


def _llm_model() -> str:
    default = DEFAULT_OLLAMA_MODEL if _rag_provider() == "ollama_local" else DEFAULT_RAG_MODEL
    return os.environ.get("TLD_RAG_MODEL") or os.environ.get("OPENAI_MODEL") or default


def _positive_int_environment(name: str, default: int, *, maximum: int = 3600) -> int:
    """Return a bounded positive integer from configuration."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer") from error
    if value <= 0 or value > maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


def _chat_completion(messages: list[dict[str, str]]) -> str:
    """Call the configured model and return only the assistant content.

    Ollama uses its native chat endpoint so thinking can be disabled explicitly.
    This prevents Qwen3 from spending most of the request timeout generating a
    hidden reasoning trace. Remote providers retain the OpenAI-compatible path.
    """
    provider = _rag_provider()
    headers = {"Content-Type": "application/json"}
    if provider == "ollama_local":
        endpoint = os.environ.get("TLD_RAG_API_URL", "http://127.0.0.1:11434/api/chat")
        # Older setup instructions used Ollama's OpenAI-compatible endpoint.
        # Normalize that local URL to the native endpoint, which supports the
        # explicit ``think: false`` control used below.
        endpoint = re.sub(r"/v1/chat/completions/?$", "/api/chat", endpoint)
        body = {
            "model": _llm_model(),
            "messages": messages,
            "stream": False,
            "think": False,
            "format": "json",
            "options": {
                "temperature": 0.0,
                "num_ctx": _positive_int_environment(
                    "TLD_OLLAMA_CONTEXT_TOKENS",
                    DEFAULT_OLLAMA_CONTEXT_TOKENS,
                    maximum=1_048_576,
                ),
            },
        }
        timeout = _positive_int_environment(
            "TLD_RAG_TIMEOUT_SECONDS", DEFAULT_OLLAMA_TIMEOUT_SECONDS
        )
    else:
        endpoint = os.environ.get("TLD_RAG_API_URL", "https://api.openai.com/v1/chat/completions")
        body = {
            "model": _llm_model(),
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "messages": messages,
        }
        if _llm_api_key():
            headers["Authorization"] = f"Bearer {_llm_api_key()}"
        timeout = _positive_int_environment(
            "TLD_RAG_TIMEOUT_SECONDS", DEFAULT_REMOTE_TIMEOUT_SECONDS
        )
    request = Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if provider == "ollama_local":
        return str(payload["message"]["content"])
    return str(payload["choices"][0]["message"]["content"])


def _llm_generate(
    query: str,
    mode: str,
    pre: RetrievedChunk | None,
    post: RetrievedChunk | None,
) -> GenerationResult:
    prompt = "\n\n".join([
        "Answer the legal query only from the supplied excerpts. Do not invent missing text, dates, applicability, or citations.",
        f"Analysis mode: {mode}\nMode contract: {MODE_INSTRUCTIONS[mode]}\nQuestion: {query}",
        _evidence_prompt_block("PRE-AMENDMENT EVIDENCE", pre),
        _evidence_prompt_block("POST-AMENDMENT EVIDENCE", post),
        (
            "Return one JSON object containing only these fields: "
            "pre_amendment_baseline (string), post_amendment_revision (string), "
            "key_differences (array of strings), and conceptual_drift_percent "
            "(number from 0 to 100). Do not repeat the prompt or evidence object."
        ),
    ])
    content = _chat_completion([
        {"role": "system", "content": "You are an evidence-bound Indian legal document comparison assistant. Return JSON only."},
        {"role": "user", "content": prompt},
    ])
    value = json.loads(content)
    differences = value.get("key_differences")
    if not isinstance(differences, list) or not all(isinstance(item, str) for item in differences):
        raise ValueError("LLM returned an invalid key_differences value")
    score = float(value["conceptual_drift_percent"])
    if not 0 <= score <= 100:
        raise ValueError("LLM conceptual score must be between 0 and 100")
    return GenerationResult(
        _bounded_text(value.get("pre_amendment_baseline")),
        _bounded_text(value.get("post_amendment_revision")),
        [_bounded_text(item, 500) for item in differences[:8]],
        score,
        "llm_grounded",
    )


def _extractive_generate(
    query: str,
    mode: str,
    pre: RetrievedChunk | None,
    post: RetrievedChunk | None,
) -> GenerationResult:
    reconstructed, comparable_post, substitution = _reconstructed_comparison(pre, post, query)
    if reconstructed and comparable_post:
        if mode == "generic":
            subject = _provision_subject(query)
            return GenerationResult(
                f"Before the amendment, {subject} used the narrower concept “{substitution[0]}”.",
                f"After the amendment, {subject} uses the broader or revised concept “{substitution[1]}”.",
                [
                    f"The amendment changes the governing concept from “{substitution[0]}” to “{substitution[1]}”.",
                    "At a high level, this changes the legal scope while retaining the surrounding statutory framework.",
                ],
                None,
                "extractive_fallback_generic",
            )
        differences = [
            f"The operative wording changes from “{substitution[0]}” to “{substitution[1]}”.",
            "The earlier wording is reconstructed from the cited consolidated-text substitution footnote and must be checked against the complete official provision.",
        ]
        return GenerationResult(
            "Reconstructed baseline from the cited substitution evidence: " + _bounded_text(reconstructed, 1200),
            "Consolidated-version evidence: " + _bounded_text(comparable_post, 1200),
            differences,
            None,
            "extractive_fallback",
        )
    pre_summary = _best_excerpt(pre, query, mode) if pre else "No relevant pre-amendment baseline was found in the indexed corpus."
    post_summary = _best_excerpt(post, query, mode) if post else "No relevant post-amendment revision was found in the indexed corpus."
    if pre and pre.metadata.get("document_type") == "amending_act":
        pre_summary = "Amendment instruction (source excerpt; no earlier version was reconstructed): " + pre_summary
    if post and post.metadata.get("version") == "consolidated":
        post_summary = "Consolidated-version evidence: " + post_summary
    differences = _difference_summary(pre.text if pre else "", post.text if post else "", mode)
    if not differences:
        differences = ["The retrieved evidence is insufficient to establish a supported amendment difference."]
    return GenerationResult(pre_summary, post_summary, differences, None, "extractive_fallback")


def _generate_single_document(
    query: str,
    mode: str,
    document: RetrievedChunk,
    document_chunks: list[RetrievedChunk],
) -> GenerationResult:
    if _llm_configured():
        try:
            return _llm_single_document_generate(query, mode, document, document_chunks)
        except (ValueError, HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            fallback = _single_document_generate(query, mode, document, document_chunks)
            return GenerationResult(
                fallback.pre_baseline,
                fallback.post_revision,
                fallback.differences,
                None,
                "extractive_fallback",
                f"Configured local model was unavailable: {type(error).__name__}",
                fallback.short_answer,
            )
    return _single_document_generate(query, mode, document, document_chunks)


def _llm_single_document_generate(
    query: str,
    mode: str,
    document: RetrievedChunk,
    document_chunks: list[RetrievedChunk],
) -> GenerationResult:
    query_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    ranked = sorted(
        document_chunks,
        key=lambda item: (
            item.metadata.get("source_anchor") == "pdf:page:1",
            len(query_terms & set(re.findall(r"[a-z0-9]+", item.text.lower()))),
        ),
        reverse=True,
    )
    evidence = [
        {
            "chunk_id": item.chunk_id,
            "source_anchor": item.metadata.get("source_anchor"),
            "text": _bounded_text(item.text, 1200),
        }
        for item in ranked[:5]
    ]
    evidence_text = "\n\n".join(
        f"EXCERPT {number}\nAnchor: {item['source_anchor']}\nText: {item['text']}"
        for number, item in enumerate(evidence, start=1)
    )
    prompt = "\n\n".join([
        (
            "Answer the question using only the supplied excerpts. Give a concise direct answer "
            "and 2-5 concrete key points. Do not claim that the excerpts cover the whole Act. "
            "Do not invent dates, effects, applicability, or provisions."
        ),
        f"Analysis mode: {mode}\nMode contract: {MODE_INSTRUCTIONS[mode]}\nQuestion: {query}",
        (
            f"Document: {document.metadata.get('act_name')}\n"
            f"Version: {document.metadata.get('version')}\n"
            f"Official identifier: {document.metadata.get('official_identifier')}"
        ),
        evidence_text,
        (
            "Return one JSON object containing only short_answer (string) and key_points "
            "(an array of 2 to 5 strings). Do not repeat the prompt, document metadata, "
            "or excerpts."
        ),
    ])
    content = _chat_completion([
        {"role": "system", "content": "You are an evidence-bound Indian legal research assistant. Return JSON only."},
        {"role": "user", "content": prompt},
    ])
    value = json.loads(content)
    points = value.get("key_points")
    if not isinstance(points, list) or not points or not all(isinstance(item, str) for item in points):
        raise ValueError("LLM returned invalid key_points")
    short_answer = _bounded_text(value.get("short_answer"), 1000)
    if not short_answer:
        raise ValueError("LLM returned an empty short_answer")
    return GenerationResult(
        "No pre-amendment comparison was requested.",
        short_answer,
        [_bounded_text(item, 500) for item in points[:5]],
        None,
        "llm_grounded",
        short_answer=short_answer,
        sources=tuple({"chunk_id": item.chunk_id, "text": item.text, "metadata": item.metadata} for item in ranked[:5]),
    )


def _single_document_generate(
    query: str,
    mode: str,
    document: RetrievedChunk,
    document_chunks: list[RetrievedChunk],
) -> GenerationResult:
    """Create a short document-level answer from explicit opening provisions."""
    text = " ".join(document.text.split())
    purpose = re.search(
        r"\bAn Act\s+(?:further\s+)?to\s+(.+?)(?=\s+BE it enacted|\s+1\.\s*\(1\)|\s+Bill No\.|\s+THE\s+.+?\s+BILL)",
        text,
        re.I,
    )
    commencement = re.search(
        r"\(2\)\s+It shall come into force.+?(?=\s+2\.\s+The enactments|\s+\d+\.\s+)",
        text,
        re.I,
    )
    amendment_scope = re.search(
        r"\bThe enactments mentioned in column \(4\).+?(?=\s+3\.\s+The fines|\s+\d+\.\s+)",
        text,
        re.I,
    )
    penalty_revision = re.search(
        r"\bThe fines and penalties.+?(?=\s+Short title|\s+Amendment of|\s+Revision of|\s+EXTRAORDINARY)",
        text,
        re.I,
    )

    title = str(document.metadata.get("act_name") or "This Act")
    if mode == "specific":
        short_answer = "Clause-focused evidence: " + _best_excerpt(document, query, "specific")
    elif purpose:
        purpose_text = _bounded_text(purpose.group(1).strip(), 600)
        short_answer = f"{title} was enacted to {purpose_text}"
        short_answer = short_answer.rstrip(".") + "."
    else:
        short_answer = _best_excerpt(document, query, "generic")

    key_points: list[str] = []
    for match in (amendment_scope, commencement, penalty_revision):
        if match:
            point = _bounded_text(match.group(0), 500).strip()
            point = point[0].upper() + point[1:] if point else point
            if point and point not in key_points:
                key_points.append(point)
    target_points = 5 if mode == "specific" else 3
    if len(key_points) < target_points:
        key_points.extend(
            _representative_changes(document_chunks, existing=key_points, limit=target_points)
        )
    if not key_points:
        key_points.append("The available opening-page evidence supports only this high-level summary; consult the cited Act for its complete provisions.")

    return GenerationResult(
        "No pre-amendment comparison was requested.",
        short_answer,
        key_points,
        None,
        "extractive_summary",
        short_answer=short_answer,
    )


def _representative_changes(
    chunks: list[RetrievedChunk], *, existing: list[str], limit: int
) -> list[str]:
    """Extract concise operative amendment statements without inventing a summary."""
    operation = re.compile(
        r"\b(?:shall be substituted|shall be inserted|shall be omitted|is hereby amended|"
        r"shall be increased|liable to penalty|punishable with|shall come into force)\b",
        re.I,
    )
    candidates: list[tuple[int, str]] = []
    seen = {re.sub(r"\W+", " ", item.lower()).strip() for item in existing}
    for chunk in chunks:
        text = " ".join(chunk.text.split())
        for match in operation.finditer(text):
            start = max(0, text.rfind(".", 0, match.start()) + 1)
            end_match = re.search(r"[.;](?:\s|$)", text[match.end():])
            end = match.end() + (end_match.end() if end_match else min(350, len(text) - match.end()))
            sentence = _bounded_text(text[start:end].strip(" —;"), 420)
            normalized = re.sub(r"\W+", " ", sentence.lower()).strip()
            if len(sentence) < 35 or normalized in seen:
                continue
            seen.add(normalized)
            lowered = sentence.lower()
            context_rank = 0 if re.search(r"\b(?:for|in)\s+(?:section|the .+ act)", lowered) else 1
            fragment_penalty = 1 if sentence[:1] in {'"', "'"} or len(sentence.split()) < 8 else 0
            cue_rank = 0 if "substitut" in match.group(0).lower() else 1
            candidates.append((fragment_penalty * 10 + context_rank * 2 + cue_rank, sentence))
    candidates.sort(key=lambda row: (row[0], -len(row[1])))
    return [sentence for _, sentence in candidates[: max(0, limit - len(existing))]]


def _reconstructed_comparison(
    pre: RetrievedChunk | None,
    post: RetrievedChunk | None,
    query: str,
) -> tuple[str | None, str | None, tuple[str, str] | None]:
    """Reconstruct a narrow prior clause only when the consolidated footnote says what was replaced."""
    if pre is None or post is None or pre.metadata.get("document_type") != "amending_act":
        return None, None, None
    section = re.search(r"\bsection\s+(\d+[a-z]?)", query, re.I)
    if not section:
        return None, None, None
    post_text = post.text
    current_matches = re.findall(r"\[([A-Za-z][A-Za-z ]{2,60})\]", post_text)
    old_matches = re.findall(
        r"\bfor\s+[\"“”―‖']?([A-Za-z][A-Za-z ]{2,60}?)[\"“”―‖']?\s*\(w\.e\.f\.",
        post_text,
        re.I,
    )
    for current in current_matches:
        current_clean = " ".join(current.split())
        for old in old_matches:
            old_clean = " ".join(old.split())
            shared = set(current_clean.lower().split()) & set(old_clean.lower().split())
            if not shared:
                continue
            provision = re.split(r"\s+\d+\.\s+Subs\.", post_text, maxsplit=1, flags=re.I)[0]
            # Only reconstruct the section the question names; another section's footnote is not this clause.
            if not re.match(rf"\s*(?:section\s+)?{re.escape(section.group(1))}\s*\.", provision, re.I):
                continue
            reconstructed = re.sub(
                rf"\d*\[{re.escape(current)}\]", old_clean, provision, count=1
            )
            return reconstructed, provision, (old_clean, current_clean)
    return None, None, None


def _select_scoring_evidence(
    pre: RetrievedChunk, post: RetrievedChunk, query: str
) -> tuple[str, str, str] | None:
    """Select comparable evidence from the prompt without user-supplied clauses.

    Scoring deliberately uses a fixed clause-focused extraction policy so the
    same prompt produces the same metric basis in Generic and Specific display
    modes. Display mode changes the explanation, not the evidence or score.
    """
    reconstructed_pre, comparable_post, _ = _reconstructed_comparison(pre, post, query)
    if reconstructed_pre and comparable_post:
        return reconstructed_pre, comparable_post, "query_section_reconstruction"
    # Best-matching excerpts from two documents are not an aligned before/after pair.
    return None


def _best_excerpt(item: RetrievedChunk, query: str, mode: str) -> str:
    text = item.text
    section = re.search(r"\bsection\s+(\d+[a-z]?)", query, re.I)
    if section:
        number = section.group(1)
        if item.metadata.get("source_kind") == "provision_version" and number.lower() in item.metadata.get("primary_sections", []):
            return _bounded_text(text, 1200 if mode == "specific" else 700)
        occurrence = re.search(rf"\bsection\s*{re.escape(number)}\b", text, re.I)
        if occurrence:
            start = max(0, occurrence.start() - 280)
            return _bounded_text(text[start:start + (1200 if mode == "specific" else 700)])
    sentences = [item.strip() for item in re.split(r"(?<=[.;!?])\s+", text) if item.strip()]
    query_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    ranked = sorted(
        sentences,
        key=lambda item: (len(query_terms & set(re.findall(r"[a-z0-9]+", item.lower()))), any(cue in item.lower() for cue in LEGAL_CUES)),
        reverse=True,
    )
    count = 3 if mode == "specific" else 2
    return _bounded_text(" ".join(ranked[:count]) if ranked else text, 1200 if mode == "specific" else 700)


def _difference_summary(pre: str, post: str, mode: str) -> list[str]:
    before = set(re.findall(r"[a-z][a-z0-9]+|\d+(?:\.\d+)?", pre.lower()))
    after = set(re.findall(r"[a-z][a-z0-9]+|\d+(?:\.\d+)?", post.lower()))
    legal_added = sorted(term for term in after - before if term in LEGAL_CUES or term.isdigit())
    legal_removed = sorted(term for term in before - after if term in LEGAL_CUES or term.isdigit())
    if mode == "generic":
        changed_cues = sorted(
            cue for cue in LEGAL_CUES
            if (cue in pre.lower()) != (cue in post.lower())
        )
        rows = [
            (
                "The amendment changes operative legal concepts involving "
                + ", ".join(changed_cues[:5])
                + "."
            ) if changed_cues else
            "The retrieved versions differ in wording, but the high-level legal theme requires review of the cited provisions."
        ]
        rows.append(
            "The practical significance depends on commencement, applicability and the facts of the user's scenario."
        )
        return rows
    rows = []
    if legal_removed:
        rows.append(f"Terms present only in the first excerpt: {', '.join(legal_removed[:12])}.")
    if legal_added:
        rows.append(f"Terms present only in the second excerpt: {', '.join(legal_added[:12])}.")
    common = before & after
    if pre and post:
        rows.append(f"The retrieved excerpts share {len(common)} distinct tokens. Term differences between excerpts are not a statement of what the amendment changed.")
    if mode == "specific" and pre and post:
        rows.append("Review the cited page anchors for the exact clause wording and amendment operation.")
    return rows


def _provision_subject(query: str) -> str:
    section = re.search(r"\bsection\s+(\d+[a-z]?)", query, re.I)
    return f"Section {section.group(1)}" if section else "the relevant provision"


def _reliability(pre: RetrievedChunk, post: RetrievedChunk, pair_status: str,
                 graph_alignment: dict[str, object] | None) -> dict[str, object]:
    """Separate reliability indicators; deliberately not combined with drift (drift-metrics-v3)."""
    if graph_alignment and graph_alignment.get("effective_date"):
        temporal = {"status": "EFFECTIVE_DATE_EVIDENCED", "date": graph_alignment["effective_date"],
                    "basis": "Act-wide commencement in graph v4; scenario applicability not determined"}
    else:
        stated = re.search(r"\(w\.e\.f\.\s*([0-9]{1,2}-[0-9]{1,2}-[0-9]{4})\)", post.text)
        temporal = ({"status": "FOOTNOTE_STATED_DATE_UNVERIFIED", "date": stated.group(1),
                     "basis": "date printed in the India Code footnote; not an approved temporal fact"}
                    if stated else {"status": "UNRESOLVED", "date": None, "basis": "no supported effective date"})
    return {
        "evidence_coverage": "BOTH_SIDES" if pre.text.strip() and post.text.strip() else "ONE_SIDE",
        "pairing": SUPPORT_CLASSES.get(pair_status, "NOT_A_COMPARISON"),
        "temporal_certainty": temporal,
        "retrieval_relevance": round((pre.score + post.score) / 2, 3),
        "note": "Reliability indicators are reported separately; they are not drift and not accuracy.",
    }


def _question_relevance(query: str, before: str, after: str, graph_alignment: dict[str, object] | None) -> dict[str, object]:
    requested = re.search(r"\bsection\s+(\d+[a-z]{0,3})", query, re.I)
    compared = str(graph_alignment["section"]) if graph_alignment else (
        (re.match(r"\s*(\d+[A-Za-z]{0,3})\s*\.", after) or re.match(r"\s*(\d+[A-Za-z]{0,3})\s*\.", before) or [None, None])[1])
    if not requested:
        status = "NO_SECTION_IN_QUESTION"
    elif compared and compared.lower() == requested.group(1).lower():
        status = "MATCHES_REQUESTED_SECTION"
    else:
        status = "DIFFERENT_SECTION"
    return {
        "status": status, "requested_section": requested.group(1) if requested else None, "compared_section": compared,
        "answers_scenario_question": False,
        "explanation": ("The score measures how the selected clause's text moved. It does not decide whether a "
                        "particular situation is answered differently; that needs the applicable version, the facts "
                        "and the consequence, which are assessed separately."),
    }


COMPARISON_CONTRACT_VERSION = "comparison-record-v1"
SUPPORT_CLASSES = {
    "graph_aligned_amendment_fragments": "GRAPH_TRANSITION_FRAGMENTS",
    "consolidated_footnote_reconstruction": "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION",
    "instruction_and_consolidated_text_not_aligned": "UNALIGNED_EXCERPTS",
    "ambiguous_graph_candidates": "AMBIGUOUS_CANDIDATES",
}
_SOURCE_HASHES: dict[str, str] | None = None


def _comparison_record(
    query: str, mode: str, pre: RetrievedChunk | None, post: RetrievedChunk | None, pair_status: str,
    metrics: dict[str, object] | None, graph_alignment: dict[str, object] | None,
    fidelity: list[dict[str, str]], generation: GenerationResult,
) -> dict[str, object]:
    """Versioned record of what was compared, on what support, and why anything abstained."""
    support = SUPPORT_CLASSES.get(pair_status, "NOT_A_COMPARISON")
    reasons: list[str] = []
    if support == "UNALIGNED_EXCERPTS":
        reasons.append("PAIR_UNALIGNED")
    if support == "AMBIGUOUS_CANDIDATES":
        reasons.append("PAIR_AMBIGUOUS")
    if support != "NOT_A_COMPARISON" and metrics is None:
        reasons.append("SCORING_UNAVAILABLE")
    if metrics and metrics.get("overall_drift_percent") is None:
        reasons.append("SCORING_UNAVAILABLE")
    if fidelity:
        reasons.append("SOURCE_TEXT_UNRELIABLE")
    if generation.method.startswith("extractive") and generation.warning:
        reasons.append("MODEL_UNAVAILABLE")
    roles = {
        "GRAPH_TRANSITION_FRAGMENTS": ("before_fragment", "after_fragment"),
        "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION": ("reconstructed_earlier_wording", "current_consolidated_text"),
        "UNALIGNED_EXCERPTS": ("amendment_instruction_excerpt", "available_act_text_excerpt"),
        "AMBIGUOUS_CANDIDATES": ("amendment_instruction_excerpt", "available_act_text_excerpt"),
    }.get(support, (None, None))
    basis = (metrics or {}).get("score_basis") or {}

    def side(item: RetrievedChunk | None, role: str | None, text: object) -> dict[str, object] | None:
        if item is None or role is None:
            return None
        page = re.search(r"page:(\d+)", str(item.metadata.get("source_anchor") or ""))
        quoted = " ".join(str(text or "").split())
        chunk = " ".join(item.text.split())
        start = chunk.find(quoted) if quoted else -1
        filename = item.metadata.get("filename")
        return {
            "role": role,
            "source_id": item.metadata.get("source_artifact_id"),
            "source_sha256": _source_hash(str(item.metadata.get("entry_id"))),
            "document_version": item.metadata.get("version"),
            "chunk_id": item.chunk_id,
            "text_offset": {"start": start, "end": start + len(quoted)} if start >= 0 else None,
            "span_basis": "exact_source_span" if start >= 0 else "derived_text_not_a_verbatim_source_span" if quoted else None,
            "local_pdf_url": f"/corpus/{filename}#page={page.group(1)}" if filename and page else None,
            "entry_id": item.metadata.get("entry_id"),
            "act_name": item.metadata.get("act_name"),
            "source_url": item.metadata.get("source_url") or item.metadata.get("official_portal_url"),
            "source_anchor": item.metadata.get("source_anchor"),
            "page": int(page.group(1)) if page else None,
            "line": None,  # chunk-level retrieval does not track lines
            "page_region_highlight": "unavailable: no verified PDF text coordinates for this chunk",
            "compared_text": text,
        }

    return {
        "contract_version": COMPARISON_CONTRACT_VERSION,
        "query_id": "q_" + sha256(f"{query}\n{mode}".encode()).hexdigest()[:16],
        "support_class": support,
        # A footnote reconstruction is derived from the consolidated Act's own footnote, so it cites that source.
        "before": side(post if support == "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION" else pre, roles[0], basis.get("pre_excerpt")),
        "after": side(post, roles[1], basis.get("post_excerpt")),
        "graph_transition_id": (graph_alignment or {}).get("transition_id"),
        "amendment_event_id": (graph_alignment or {}).get("amendment_event_id"),
        "operation": (graph_alignment or {}).get("operation") or ("SUBSTITUTE" if support == "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION" else None),
        "provision_path": (graph_alignment or {}).get("provision_path") or (
            f"section:{(metrics or {}).get('question_relevance', {}).get('compared_section')}" if metrics and (metrics.get("question_relevance") or {}).get("compared_section") else None),
        "competing_transition_ids": (graph_alignment or {}).get("competing_transition_ids", []),
        "requested_date": _requested_date(query),
        "reliability": (metrics or {}).get("reliability"),
        "question_relevance": (metrics or {}).get("question_relevance"),
        "supported_effective_date": (graph_alignment or {}).get("effective_date"),
        "changed_spans": (metrics or {}).get("changed_spans", []),
        "scoring_contract_version": (metrics or {}).get("metrics_contract_version"),
        "materiality_status": "NOT_ASSESSED_IN_QUERY_FLOW",
        "applicability_status": "NOT_DETERMINED_REQUIRES_SCENARIO_FACTS_AND_REVIEW",
        "consequence_status": "NOT_DETERMINED",
        "abstention_reasons": list(dict.fromkeys(reasons)),
        "legal_validation": "UNVERIFIED",
    }


def _source_hash(entry_id: str) -> str | None:
    """SHA-256 of the corpus PDF behind a chunk (from the frozen corpus lock)."""
    global _SOURCE_HASHES
    if _SOURCE_HASHES is None:
        lock = Path(__file__).resolve().parents[3] / "reports/corpus/india-code-temporal-pilot-v1.lock.json"
        _SOURCE_HASHES = {str(e["entry_id"]): str(e["sha256"]) for e in json.loads(lock.read_text()).get("entries", [])} if lock.is_file() else {}
    return _SOURCE_HASHES.get(entry_id)


_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")


def _requested_date(query: str) -> dict[str, object] | None:
    """A date constraint stated in the question, kept as a constraint, never as applicability."""
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", query)
    if iso:
        return {"value": iso.group(1), "precision": "day"}
    written = re.search(r"\b(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})\b", query, re.I)
    if written:
        return {"value": f"{written.group(3)}-{_MONTHS.index(written.group(2).lower()) + 1:02d}-{int(written.group(1)):02d}", "precision": "day"}
    year = re.search(r"\b(?:in|on|as of|during)\s+((?:19|20)\d{2})\b", query, re.I)
    return {"value": year.group(1), "precision": "year"} if year else None


def _citations(pre: RetrievedChunk | None, post: RetrievedChunk | None) -> list[dict[str, object]]:
    records = []
    for label, item in (("pre", pre), ("post", post)):
        if item is None:
            continue
        metadata = item.metadata
        records.append({
            "label": label,
            "chunk_id": item.chunk_id,
            "entry_id": metadata.get("entry_id"),
            "act_name": metadata.get("act_name"),
            "version": metadata.get("version"),
            "document_type": metadata.get("document_type"),
            "date": metadata.get("date"),
            "source_anchor": metadata.get("source_anchor"),
            "official_identifier": metadata.get("official_identifier"),
            "source_url": metadata.get("source_url"),
            "official_portal_url": metadata.get("official_portal_url"),
        })
    return records


def _verification(
    query: str,
    pre: RetrievedChunk | None,
    post: RetrievedChunk | None,
    pair_status: str,
    generation: GenerationResult,
    citations: list[dict[str, object]],
    aligned_versions: bool = False,
) -> dict[str, object]:
    query_terms = set(re.findall(r"[a-z]{4,}", query.lower()))
    evidence_terms = set(re.findall(r"[a-z]{4,}", " ".join(item.text for item in (pre, post) if item).lower()))
    checks = [
        {"id": "intent_classified", "label": "Query intent classified", "passed": True},
        {"id": "clause_coverage", "label": "Relevant clause coverage", "passed": bool(query_terms & evidence_terms)},
        {"id": "paired_context", "label": "Aligned pre/post versions of the same provision", "passed": aligned_versions},
        {"id": "citation_anchors", "label": "Evidence anchors attached", "passed": bool(citations) and all(item.get("source_anchor") for item in citations)},
        {"id": "alignment", "label": "Post-generation alignment check", "passed": generation.method in {"llm_grounded", "extractive_fallback", "extractive_fallback_generic"} and bool(citations)},
    ]
    return {
        "passed": all(item["passed"] for item in checks),
        "checks": checks,
        "pair_status": pair_status,
        "note": "A failed check means the answer should be treated as incomplete and verified on India Code.",
    }


def _metadata_coverage(pre: RetrievedChunk | None, post: RetrievedChunk | None) -> float:
    items = [item for item in (pre, post) if item]
    if not items:
        return 0.0
    fields = ("document_type", "version", "act_name", "date")
    present = sum(bool(item.metadata.get(field)) for item in items for field in fields)
    return present / (len(items) * len(fields))


def _answer_markdown(
    generation: GenerationResult,
    citations: list[dict[str, object]],
    guidance: dict[str, str],
    answer_type: str,
) -> str:
    if answer_type == "single_document_summary":
        lines = [
            "## Short Answer", generation.short_answer or generation.post_revision,
            "", "## Key Points",
            *[f"- {item}" for item in generation.differences],
            "", "## Evidence",
            *[f"- {item.get('act_name')} · {item.get('source_anchor')} · {item.get('official_identifier')}" for item in citations],
            "", f"[{guidance['label']}]({guidance['url']})",
        ]
        return "\n".join(lines)
    lines = [
        "## Pre-Amendment Baseline", generation.pre_baseline,
        "", "## Post-Amendment Revision", generation.post_revision,
        "", "## Key Differences Summary",
        *[f"- {item}" for item in generation.differences],
        "", "## Evidence",
        *[f"- {item.get('act_name')} · {item.get('source_anchor')} · {item.get('official_identifier')}" for item in citations],
        "", f"[{guidance['label']}]({guidance['url']})",
    ]
    return "\n".join(lines)


def _insufficient_response(
    query: str, mode: str, intent: str, guidance: dict[str, str], repository: dict[str, object]
) -> dict[str, object]:
    message = "No sufficiently relevant evidence was found in the indexed local corpus."
    return {
        "schema_version": "1.0.0", "query": query, "mode": mode, "intent": intent,
        "answer": {
            "answer_type": "insufficient_evidence",
            "short_answer": message,
            "pre_amendment_baseline": message,
            "post_amendment_revision": message,
            "key_differences": [message],
            "markdown": f"## Evidence unavailable\n{message}\n\n[{guidance['label']}]({guidance['url']})",
            "generation_method": "insufficient_evidence", "generation_warning": None,
        },
        "metrics": None,
        "retrieval": {"pair_status": "no_relevant_evidence", "candidate_count": 0, "relation": None, "pre": None, "post": None},
        "citations": [],
        "verification": {"passed": False, "checks": [{"id": "evidence", "label": "Relevant evidence found", "passed": False}], "note": "Verify directly on India Code."},
        "source_guidance": guidance,
        "repository": repository,
        "limitations": ["No local evidence supported the query."],
    }


def _prompt_evidence(item: RetrievedChunk | None) -> dict[str, object] | None:
    if item is None:
        return None
    return {"chunk_id": item.chunk_id, "text": item.text, "metadata": item.metadata}


def _evidence_prompt_block(label: str, item: RetrievedChunk | None) -> str:
    if item is None:
        return f"{label}\nNo evidence was retrieved."
    return (
        f"{label}\n"
        f"Chunk: {item.chunk_id}\n"
        f"Act: {item.metadata.get('act_name')}\n"
        f"Version: {item.metadata.get('version')}\n"
        f"Date: {item.metadata.get('date')}\n"
        f"Anchor: {item.metadata.get('source_anchor')}\n"
        f"Text: {_bounded_text(item.text, 1800)}"
    )


def _evidence_gate(versions: dict[str, object]) -> str | None:
    """The fingerprint's own gate: why a supported pair still cannot be scored (no aligned clause, OCR), or None."""
    pair = clause_pair(versions)
    return (pair.get("reason") or "no aligned clause") if pair["status"] != "OK" else text_gate(versions, pair)


def _bounded_text(value: object, maximum: int = 1200) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= maximum else text[: maximum - 1].rstrip() + "…"


def _anchor(item: dict[str, object]) -> str | None:
    if not item.get("page"):
        return None
    return f"pdf:page:{item['page']}" + (f":line:{item['line']}" if item.get("line") else "")


def _v2_markdown(composed: dict[str, object]) -> str:
    lines = [str(composed["direct_answer"]), ""]
    for section in composed["sections"]:
        lines += [f"## {section['title']}", str(section["text"]) + (f" [{', '.join(section['evidence_ids'])}]" if section["evidence_ids"] else ""), ""]
    return "\n".join(lines).strip()


V2_ROLES = {"before_fragment", "after_fragment", "reconstructed_earlier_wording", "current_consolidated_text"}


def _v2_comparison_record(query: str, mode: str, frame: QuestionFrame, versions: dict[str, object], metrics: dict[str, object] | None,
                          determinations: dict[str, object], fidelity: list[dict[str, str]]) -> dict[str, object]:
    supported = versions["support_class"] in VERSION_CLAIMS
    items = {item["evidence_id"]: item for item in versions["evidence"]}

    def side(reference: dict[str, object] | None) -> dict[str, object] | None:
        if not reference:
            return None
        item = items[reference["evidence_id"]]
        return {"role": item["role"], "evidence_id": item["evidence_id"], "source_id": None, "source_sha256": item["source_sha256"],
                "text_sha256": item["text_sha256"], "document_version": item["scope"], "chunk_id": None, "text_offset": None,
                "span_basis": "exact_source_span" if item["verbatim"] else "derived_text_not_a_verbatim_source_span",
                "local_pdf_url": item["pdf_url"], "entry_id": item["entry_id"], "act_name": item["act_name"], "source_url": item["official_url"],
                "source_anchor": _anchor(item), "page": item["page"], "line": item["line"],
                "page_region_highlight": "unavailable: no verified PDF text coordinates", "compared_text": item["text"]}

    reasons = [] if supported else [versions["reason_code"]]
    if supported and metrics is None:
        reasons.append("SCORING_UNAVAILABLE")
    if fidelity:
        reasons.append("SOURCE_TEXT_UNRELIABLE")
    return {
        "contract_version": "comparison-record-v2", "query_id": "q_" + sha256(f"{query}\n{mode}".encode()).hexdigest()[:16],
        "support_class": versions["support_class"], "support_reason": versions["reason"],
        "before": side(versions.get("before")) if supported else None, "after": side(versions.get("after")) if supported else None,
        "graph_transition_id": versions.get("transition_id"), "amendment_event_id": versions.get("amendment_event_id"),
        "operation": versions.get("operation"), "provision_path": versions.get("provision_path"),
        "competing_transition_ids": [c["transition_id"] for c in versions.get("candidates") or [] if "transition_id" in c],
        "requested_date": _requested_date(query), "reliability": (metrics or {}).get("reliability"),
        "question_relevance": (metrics or {}).get("question_relevance"), "supported_effective_date": versions.get("effective_date"),
        "changed_spans": (metrics or {}).get("changed_spans", []), "scoring_contract_version": (metrics or {}).get("metrics_contract_version"),
        "materiality_status": determinations["materiality"]["state"], "applicability_status": "NOT_DETERMINED_REQUIRES_SCENARIO_FACTS_AND_REVIEW",
        "consequence_status": determinations["risk"]["state"], "abstention_reasons": reasons, "legal_validation": "UNVERIFIED",
        "relation_verification": versions.get("relation_verification"),
    }


def _v2_verification(frame: QuestionFrame, versions: dict[str, object], citations: list[dict[str, object]]) -> dict[str, object]:
    supported = versions["support_class"] in VERSION_CLAIMS
    checks = [
        {"id": "act_identified", "label": "Act identified from the question", "passed": frame.principal is not None},
        {"id": "provision_identified", "label": "Provision identified", "passed": bool(frame.sections)},
        {"id": "relation_verified", "label": "Amending Act linked to this Act", "passed": supported and versions.get("relation_verification") in {"GRAPH_SOURCE_LINKED", "ACT_NUMBER_TEXT_VERIFIED"}},
        {"id": "paired_context", "label": "Supported before/after versions of the same provision", "passed": supported},
        {"id": "citation_anchors", "label": "Page-level evidence attached", "passed": bool(citations) and all(c.get("page") for c in citations)},
    ]
    return {"passed": all(c["passed"] for c in checks), "checks": checks, "pair_status": versions["support_class"].lower(),
            "note": "A failed check means the answer is partial; the reason is shown with the answer."}


def _rule_delta_proposer():
    """Optional LLM rule-delta proposals (TLD_RULE_DELTA_LLM=1); each value is validated before use."""
    if os.environ.get("TLD_RULE_DELTA_LLM") != "1" or not _llm_configured():
        return None

    def propose(pair: dict[str, object]) -> object:
        content = _chat_completion([
            {"role": "system", "content": "Extract a legal rule delta. Return JSON only."},
            {"role": "user", "content": (
                "Fields: modality, penalty, threshold, deadline, exception, scope, actor, action. "
                "For each field that differs between BEFORE and AFTER, return {field, before, after} where before/after are EXACT "
                "substrings copied from the texts (or null if absent). Return {\"fields\": [...]}.\n\n"
                f"BEFORE: {_bounded_text(pair['before'], 1800)}\n\nAFTER: {_bounded_text(pair['after'], 1800)}")},
        ])
        return json.loads(content)

    return propose


def _active_release(root: Path) -> str | None:
    path = root / "data/releases/active_release.json"
    return json.loads(path.read_text()).get("manifest_sha256") if path.is_file() else None

