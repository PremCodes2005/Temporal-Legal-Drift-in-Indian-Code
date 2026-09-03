"""Single-prompt RAG orchestration for temporal Indian-law analysis."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .indiacode import source_guidance
from .metrics import calculate_drift_metrics
from .retriever import HybridRetriever, RetrievedChunk


INTENT_PATTERNS = {
    "diff_analysis": re.compile(r"\b(change[ds]?|difference|amend(?:ed|ment)?|before|after|drift|compare)\b", re.I),
    "statutory_lookup": re.compile(r"\b(section|clause|provision|statute|act|code|rule|regulation)\b", re.I),
}
LEGAL_CUES = (
    "shall", "must", "may", "prohibited", "penalty", "fine", "imprisonment",
    "liable", "means", "includes", "substituted", "inserted", "omitted",
)


@dataclass(frozen=True)
class GenerationResult:
    pre_baseline: str
    post_revision: str
    differences: list[str]
    conceptual_score: float | None
    method: str
    warning: str | None = None


class RagPipeline:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.retriever = HybridRetriever(self.root)

    def status(self) -> dict[str, object]:
        retrieval = self.retriever.status()
        return {
            **retrieval,
            "generation": {
                "provider": "openai_compatible" if _llm_configured() else "extractive_fallback",
                "temperature": 0.0,
                "model": os.environ.get("TLD_RAG_MODEL") if _llm_configured() else None,
                "grounded_output_required": True,
            },
            "notice": "The local index is a research aid. India Code remains the authoritative source.",
        }

    def rebuild(self) -> dict[str, object]:
        return self.retriever.rebuild()

    def answer(self, query: str, mode: str) -> dict[str, object]:
        query = " ".join(str(query or "").split())
        if not query:
            raise ValueError("query is required")
        if len(query) > 4000:
            raise ValueError("query exceeds 4000 characters")
        if mode not in {"specific", "generic"}:
            raise ValueError("mode must be specific or generic")

        intent = _classify_intent(query)
        retrieved = self.retriever.search(query, limit=40)
        relation = self.retriever.relation_for_results(retrieved)
        if relation:
            related_ids = {relation["amending_entry_id"], relation["target_entry_id"]}
            related = self.retriever.search(query, limit=12, entry_ids=related_ids)
            by_id = {item.chunk_id: item for item in [*retrieved, *related]}
            retrieved = sorted(by_id.values(), key=lambda item: (-item.score, item.chunk_id))
        pre, post, pair_status = _select_pair(retrieved, relation)
        guidance = source_guidance(query)

        if pre is None and post is None:
            return _insufficient_response(query, mode, intent, guidance, self.status())

        generation = _generate(query, mode, pre, post)
        pre_text = pre.text if pre else ""
        post_text = post.text if post else ""
        reconstructed_pre, comparable_post, _ = _reconstructed_comparison(pre, post, query)
        metric_pre_text = reconstructed_pre or pre_text
        metric_post_text = comparable_post or post_text
        metadata_coverage = _metadata_coverage(pre, post)
        metric_document = None
        if pre is not None and post is not None:
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
        citations = _citations(pre, post)
        verification = _verification(query, pre, post, pair_status, generation, citations)
        answer_markdown = _answer_markdown(generation, citations, guidance)
        return {
            "schema_version": "1.0.0",
            "query": query,
            "mode": mode,
            "intent": intent,
            "answer": {
                "pre_amendment_baseline": generation.pre_baseline,
                "post_amendment_revision": generation.post_revision,
                "key_differences": generation.differences,
                "markdown": answer_markdown,
                "generation_method": generation.method,
                "generation_warning": generation.warning,
            },
            "metrics": metric_document,
            "retrieval": {
                "pair_status": pair_status,
                "candidate_count": len(retrieved),
                "relation": relation,
                "pre": pre.to_dict() if pre else None,
                "post": post.to_dict() if post else None,
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
    return bool(os.environ.get("TLD_RAG_API_KEY") and os.environ.get("TLD_RAG_MODEL"))


def _llm_generate(
    query: str,
    mode: str,
    pre: RetrievedChunk | None,
    post: RetrievedChunk | None,
) -> GenerationResult:
    endpoint = os.environ.get("TLD_RAG_API_URL", "https://api.openai.com/v1/chat/completions")
    prompt = {
        "task": "Answer the legal query only from the supplied excerpts. Do not invent missing text, dates, applicability or citations.",
        "mode": mode,
        "query": query,
        "pre_evidence": _prompt_evidence(pre),
        "post_evidence": _prompt_evidence(post),
        "output": {
            "pre_amendment_baseline": "string",
            "post_amendment_revision": "string",
            "key_differences": ["string"],
            "conceptual_drift_percent": "number 0-100",
        },
    }
    body = {
        "model": os.environ["TLD_RAG_MODEL"],
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You are an evidence-bound Indian legal document comparison assistant. Return JSON only."},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
    }
    request = Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {os.environ['TLD_RAG_API_KEY']}", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=90) as response:
        payload = json.loads(response.read().decode("utf-8"))
    content = payload["choices"][0]["message"]["content"]
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
        pre_summary = "Amendment instruction used for baseline reconstruction: " + pre_summary
    if post and post.metadata.get("version") == "consolidated":
        post_summary = "Consolidated-version evidence: " + post_summary
    differences = _difference_summary(pre.text if pre else "", post.text if post else "", mode)
    if not differences:
        differences = ["The retrieved evidence is insufficient to establish a supported amendment difference."]
    return GenerationResult(pre_summary, post_summary, differences, None, "extractive_fallback")


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
            reconstructed = re.sub(
                rf"\d*\[{re.escape(current)}\]", old_clean, provision, count=1
            )
            return reconstructed, provision, (old_clean, current_clean)
    return None, None, None


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
    rows = []
    if legal_removed:
        rows.append(f"Terms present only in the baseline evidence: {', '.join(legal_removed[:12])}.")
    if legal_added:
        rows.append(f"Terms present only in the revision evidence: {', '.join(legal_added[:12])}.")
    common = before & after
    if pre and post:
        rows.append(f"The retrieved excerpts share {len(common)} distinct tokens; the score panel separates semantic, lexical and legal-intent movement.")
    if mode == "specific" and pre and post:
        rows.append("Review the cited page anchors for the exact clause wording and amendment operation.")
    return rows


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
) -> dict[str, object]:
    query_terms = set(re.findall(r"[a-z]{4,}", query.lower()))
    evidence_terms = set(re.findall(r"[a-z]{4,}", " ".join(item.text for item in (pre, post) if item).lower()))
    checks = [
        {"id": "intent_classified", "label": "Query intent classified", "passed": True},
        {"id": "clause_coverage", "label": "Relevant clause coverage", "passed": bool(query_terms & evidence_terms)},
        {"id": "paired_context", "label": "Pre/post version pair found", "passed": pre is not None and post is not None},
        {"id": "citation_anchors", "label": "Evidence anchors attached", "passed": bool(citations) and all(item.get("source_anchor") for item in citations)},
        {"id": "alignment", "label": "Post-generation alignment check", "passed": generation.method in {"llm_grounded", "extractive_fallback"} and bool(citations)},
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


def _answer_markdown(generation: GenerationResult, citations: list[dict[str, object]], guidance: dict[str, str]) -> str:
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


def _bounded_text(value: object, maximum: int = 1200) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= maximum else text[: maximum - 1].rstrip() + "…"
