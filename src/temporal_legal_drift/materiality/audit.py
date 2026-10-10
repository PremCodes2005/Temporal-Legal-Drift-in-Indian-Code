"""Versioned audit of the original silver-rule disagreements."""

from __future__ import annotations

import re
from hashlib import sha256
from typing import Any

from temporal_legal_drift.amendment_extraction.extractor import QUOTED
from temporal_legal_drift.jsonio import canonical_json_bytes

from .silver import _cue_transition_annotator, _operation_delta_annotator


def build_disagreement_audit_v2(
    silver: dict[str, Any],
    round_document: dict[str, Any],
    graph: dict[str, Any],
    reextracted_events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Re-extract only the original disagreement evidence and compare rule versions.

    This is a diagnostic 19-case artifact, not a replacement 50-case dataset and
    not a legal adjudication. Source evidence and the v1 predictions are retained.
    """
    if silver.get("status") != "automated_silver_labels_not_gold":
        raise ValueError("Expected the preserved v1 non-gold silver dataset")
    if len(silver.get("agreement", {}).get("disagreement_pair_ids", [])) != 19:
        raise ValueError("Audit v2 is scoped to the frozen set of 19 original disagreements")
    tasks = {str(item["pair_id"]): item for item in round_document.get("tasks", [])}
    rows = {str(item["pair_id"]): item for item in silver.get("rows", [])}
    events = {str(item["amendment_event_id"]): item for item in graph.get("amendment_events", [])}
    corpus_entry_by_source = {
        str(item["source_id"]): str(item["corpus_entry_id"])
        for item in graph.get("legal_sources", [])
    }
    reextracted_by_source_and_evidence: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in reextracted_events:
        key = (str(item.get("source_document")), str(item.get("evidence_text")))
        reextracted_by_source_and_evidence.setdefault(key, []).append(item)

    audit_rows: list[dict[str, Any]] = []
    for pair_id in silver["agreement"]["disagreement_pair_ids"]:
        task, silver_row = tasks[str(pair_id)], rows[str(pair_id)]
        original_event = events[str(task["amendment_event_id"])]
        source_id = str(original_event["evidence"]["source_id"])
        corpus_entry = corpus_entry_by_source.get(source_id)
        source_text = str(original_event["evidence"]["exact_text"])
        matches = reextracted_by_source_and_evidence.get((str(corpus_entry), source_text), [])
        reparsed = matches[0] if len(matches) == 1 else None

        old_a = str(silver_row["annotator_a"]["label"])
        old_b = str(silver_row["annotator_b"]["label"])
        old_before, old_after = str(task.get("before_text") or ""), str(task.get("after_text") or "")
        old_similarity = float(silver_row["annotator_b"].get("similarity", 0.0))
        extraction_status, defect_codes = _assess_extraction(task, original_event, reparsed)
        new_task = dict(task)
        if reparsed and reparsed.get("operation") in {"INSERT", "SUBSTITUTE", "REPLACE", "OMIT", "REPEAL"}:
            operation = str(reparsed["operation"])
            new_task["operation"] = operation
            new_task["before_text"] = "" if operation == "INSERT" else str(reparsed.get("old_text") or "")
            new_task["after_text"] = "" if operation in {"OMIT", "REPEAL"} else str(reparsed.get("new_text") or "")
        else:
            new_task["operation"] = "UNKNOWN"
            new_task["before_text"] = None
            new_task["after_text"] = None

        if extraction_status == "REVIEW_REQUIRED" or not reparsed or reparsed.get("operation") == "UNKNOWN":
            new_a = {"label": None, "status": "REVIEW_REQUIRED", "rationale": "Source event or operation is not represented as one unambiguous aligned fragment."}
            new_b = {"label": None, "status": "REVIEW_REQUIRED", "rationale": "No materiality label is emitted when the source fragment is unresolved."}
        else:
            new_a = _cue_transition_annotator(new_task)
            new_a["status"] = "PROVISIONAL_RULE_OUTPUT"
            new_b = _operation_delta_v2(new_task)
        consolidated_support = _consolidated_support(task, reparsed)
        if consolidated_support is False:
            new_a["status"] = "REVIEW_REQUIRED_CROSS_SOURCE_MISMATCH"
            new_b["status"] = "REVIEW_REQUIRED_CROSS_SOURCE_MISMATCH"

        audit_rows.append({
            "pair_id": str(pair_id),
            "act_title": task.get("act_title"),
            "provision_path_v1": task.get("provision_path"),
            "operation_v1": task.get("operation"),
            "source_id": source_id,
            "source_sha256": original_event["evidence"].get("source_sha256"),
            "source_page": original_event["evidence"].get("page"),
            "source_line": original_event["evidence"].get("line"),
            "source_instruction": source_text,
            "v1": {
                "before_text": old_before,
                "after_text": old_after,
                "rule_a": old_a,
                "rule_b": old_b,
                "rule_b_similarity": old_similarity,
                "rule_b_rationale": silver_row["annotator_b"]["rationale"],
                "provisional_tiebreak": silver_row["automated_adjudication"]["label"],
            },
            "extraction_v2": {
                "matched_reparsed_event": reparsed is not None,
                "operation": reparsed.get("operation") if reparsed else None,
                "target_provision": reparsed.get("target_provision") if reparsed else None,
                "old_text": reparsed.get("old_text") if reparsed else None,
                "new_text": reparsed.get("new_text") if reparsed else None,
                "status": extraction_status,
                "defect_codes": defect_codes,
                "source_span_check": _source_span_check(reparsed, source_text),
                "consolidated_snapshot_support": consolidated_support,
            },
            "v2": {
                "before_text": new_task["before_text"],
                "after_text": new_task["after_text"],
                "rule_a": new_a,
                "rule_b": new_b,
                "labels_are_legal_truth": False,
            },
            "legal_correctness": "UNVERIFIED_NO_INDEPENDENT_LEGAL_LABELS",
            "gold_status": "NOT_GOLD",
        })

    comparable = [
        item for item in audit_rows
        if item["extraction_v2"]["status"] != "REVIEW_REQUIRED"
        and item["extraction_v2"]["consolidated_snapshot_support"] is True
        and item["v2"]["rule_a"].get("status") == "PROVISIONAL_RULE_OUTPUT"
        and item["v2"]["rule_b"].get("status") == "PROVISIONAL_RULE_OUTPUT"
        and item["v2"]["rule_a"].get("label") is not None
        and item["v2"]["rule_b"].get("label") is not None
    ]
    matching = sum(item["v2"]["rule_a"]["label"] == item["v2"]["rule_b"]["label"] for item in comparable)
    return {
        "schema_version": "2.3.0",
        "audit_id": "materiality-disagreement-audit-v2.3",
        "status": "diagnostic_reextraction_and_rule_reassessment_not_gold",
        "source_silver_sha256": sha256(canonical_json_bytes(silver)).hexdigest(),
        "source_round_sha256": sha256(canonical_json_bytes(round_document)).hexdigest(),
        "reextracted_events_sha256": sha256(canonical_json_bytes(reextracted_events)).hexdigest(),
        "extractor_version": "generalised-amendment-extractor-v2",
        "rule_b_version": "operation-delta-v2-abstains-on-size-only-signal",
        "case_count": len(audit_rows),
        "confirmed_alignment_defect_count": sum(item["extraction_v2"]["status"] == "CONFIRMED_EXTRACTION_DEFECT" for item in audit_rows),
        "review_required_count": sum(item["extraction_v2"]["status"] == "REVIEW_REQUIRED" for item in audit_rows),
        "reextracted_aligned_count": sum(item["extraction_v2"]["status"] == "REEXTRACTED_ALIGNED" for item in audit_rows),
        "cross_source_revalidation_required_count": sum(item["extraction_v2"]["consolidated_snapshot_support"] is False for item in audit_rows),
        "v1_rule_disagreement_count": sum(item["v1"]["rule_a"] != item["v1"]["rule_b"] for item in audit_rows),
        "v2_rule_a_labelled_count": sum(item["v2"]["rule_a"].get("label") is not None for item in audit_rows),
        "v2_rule_a_review_held_label_count": sum(
            item["v2"]["rule_a"].get("label") is not None
            and item["v2"]["rule_a"].get("status") != "PROVISIONAL_RULE_OUTPUT"
            for item in audit_rows
        ),
        "v2_rule_b_labelled_count": sum(item["v2"]["rule_b"].get("label") is not None for item in audit_rows),
        "v2_rule_b_review_held_label_count": sum(
            item["v2"]["rule_b"].get("label") is not None
            and item["v2"]["rule_b"].get("status") != "PROVISIONAL_RULE_OUTPUT"
            for item in audit_rows
        ),
        "v2_rule_b_abstention_count": sum(item["v2"]["rule_b"].get("label") is None for item in audit_rows),
        "rule_a_changed_from_v1_count": sum(item["v2"]["rule_a"].get("label") != item["v1"]["rule_a"] for item in audit_rows),
        "rule_b_changed_from_v1_count": sum(item["v2"]["rule_b"].get("label") != item["v1"]["rule_b"] for item in audit_rows),
        "v2_comparable_count": len(comparable),
        "v2_rule_agreement_count": matching,
        "v2_rule_agreement_rate_on_comparable_only": matching / len(comparable) if comparable else None,
        "v2_low_medium_disagreement_count": sum(
            item["v2"]["rule_a"].get("status") == "PROVISIONAL_RULE_OUTPUT"
            and item["v2"]["rule_b"].get("status") == "PROVISIONAL_RULE_OUTPUT"
            and {item["v2"]["rule_a"].get("label"), item["v2"]["rule_b"].get("label")} == {"Low", "Medium"}
            for item in audit_rows
        ),
        "interpretation": "Rule agreement is descriptive only and not legal accuracy. Low edit similarity alone now results in REVIEW_REQUIRED rather than Medium. No labels are gold.",
        "rows": audit_rows,
    }


def render_disagreement_audit_v2(document: dict[str, Any]) -> str:
    rows = document["rows"]
    parts = [
        "# Materiality Disagreement Review — Version 2.3",
        "",
        "This report re-extracts source clauses with extractor v2 and reassesses the original 19 cases. The v1 report and silver dataset remain unchanged. Machine outputs are not legal findings or gold labels.",
        "",
        f"- Confirmed extraction/alignment defects: **{document['confirmed_alignment_defect_count']}**",
        f"- Review-required compound or unresolved cases: **{document['review_required_count']}**",
        f"- Re-extracted aligned cases: **{document['reextracted_aligned_count']}**",
        f"- Cases requiring revalidation against the consolidated principal-Act snapshot: **{document['cross_source_revalidation_required_count']}**",
        f"- v1 disagreements: **{document['v1_rule_disagreement_count']}/{document['case_count']}**",
        f"- v2 comparable cases (both rules emitted labels): **{document['v2_comparable_count']}**",
        f"- v2 agreement among comparable cases: **{document['v2_rule_agreement_count']}/{document['v2_comparable_count']}**" if document["v2_comparable_count"] else "- v2 agreement: not calculable (no comparable cases)",
        f"- v2 Rule A emitted labels for {document['v2_rule_a_labelled_count']}/19; Rule B proposed {document['v2_rule_b_labelled_count']}/19, with {document['v2_rule_b_review_held_label_count']} held for cross-source review and {document['v2_rule_b_abstention_count']} null-label abstentions.",
        f"- Predictions changed from v1: Rule A **{document['rule_a_changed_from_v1_count']}/19**; Rule B **{document['rule_b_changed_from_v1_count']}/19**. The two Rule B label candidates are not score-eligible because their complete inserted text did not exactly match the existing consolidated snapshot.",
        f"- Remaining paired Low-versus-Medium disagreements: **{document['v2_low_medium_disagreement_count']}**; abstentions are not counted as agreement.",
        "",
        "Rule B v1 assigned Medium solely from token similarity below 0.65 in all original disagreements. That ratio is not a legal-effect measure; v2 abstains with REVIEW_REQUIRED when low similarity is the only signal. Insertions correctly have an empty before fragment, but this makes a SequenceMatcher ratio of zero structurally uninformative.",
        "",
    ]
    for index, row in enumerate(rows, 1):
        old, new, extraction = row["v1"], row["v2"], row["extraction_v2"]
        parts.extend([
            f"## {index}. {row['pair_id']} — {row['act_title']} / {row['provision_path_v1']}",
            "",
            f"- Source: `{row['source_id']}` page {row['source_page']}, line {row['source_line']} (SHA-256 `{row['source_sha256']}`).",
            f"- v1 operation/fragments: `{row['operation_v1']}`; before ({len(old['before_text'])} chars): “{_excerpt(old['before_text'])}”; after ({len(old['after_text'])} chars): “{_excerpt(old['after_text'])}”.",
            f"- v1 rule labels: A **{old['rule_a']}**, B **{old['rule_b']}** (similarity {old['rule_b_similarity']:.4f}); v1 tie-break **{old['provisional_tiebreak']}** (provisional).",
            f"- v2 extraction status: **{extraction['status']}**; new operation `{extraction['operation']}`, target `{extraction['target_provision']}`; defects: {', '.join(extraction['defect_codes']) or 'none identified'}.",
            f"- v2 fragments: before ({len(str(new['before_text'] or ''))} chars): “{_excerpt(new['before_text'])}”; after ({len(str(new['after_text'] or ''))} chars): “{_excerpt(new['after_text'])}”.",
            f"- v2 rules: A **{new['rule_a'].get('label') or 'ABSTAIN'}** ({new['rule_a']['status']}); B **{new['rule_b'].get('label') or 'ABSTAIN'}** ({new['rule_b']['status']}).",
            "- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.",
            "",
        ])
    parts.extend([
        "## Limits and next step",
        "",
        "This audit corrects identified extraction mechanics and rule behavior, but it does not certify the resulting text as the legally applicable provision. Before replacing the 50-case dataset, regenerate a complete versioned Phase 2/3 graph and materiality round, then independently inspect consolidated-source alignment. Legal validity remains unverified without qualified review.",
        "",
    ])
    return "\n".join(parts)


def _assess_extraction(task: dict[str, Any], old_event: dict[str, Any], new_event: dict[str, Any] | None) -> tuple[str, list[str]]:
    if new_event is None:
        return "REVIEW_REQUIRED", ["reextracted_source_clause_not_uniquely_matched"]
    defects: list[str] = []
    operation = str(new_event.get("operation"))
    instruction = str(new_event.get("evidence_text", ""))
    if _old_after_is_inserted_anchor(str(task.get("after_text") or ""), instruction):
        defects.append("v1_after_text_was_anchor_not_inserted_operand")
    old_detail = old_event.get("target_path_detail")
    source_detail = _operation_detail(instruction, str(task.get("after_text") or ""))
    if old_detail and source_detail and _path_conflicts(str(old_detail), source_detail):
        defects.append("target_path_detail_mismatch")
    if operation == "UNKNOWN":
        if defects:
            defects.append("compound_operation_requires_event_split_or_adjudication")
            return "CONFIRMED_EXTRACTION_DEFECT", defects
        return "REVIEW_REQUIRED", ["compound_operation_requires_event_split_or_adjudication"]
    if operation != str(task.get("operation")):
        defects.append("operation_changed_on_reextraction")
    old_new = (str(old_event.get("old_text") or ""), str(old_event.get("new_text") or ""))
    new_new = (str(new_event.get("old_text") or ""), str(new_event.get("new_text") or ""))
    if old_new != new_new:
        defects.append("wording_changed_on_reextraction")
    old_target = str(task.get("provision_path", "")).split(":")[-1].upper()
    new_target = str(new_event.get("target_provision", "")).split(":")[-1].upper()
    if old_target != new_target:
        defects.append("target_changed_on_reextraction")
    expected_detail = old_event.get("target_path_detail")
    source_detail = _operation_detail(instruction, str(new_event.get("new_text") or ""))
    if expected_detail and source_detail and _path_conflicts(str(expected_detail), source_detail):
        if "target_path_detail_mismatch" not in defects:
            defects.append("target_path_detail_mismatch")
    source_check = _source_span_check(new_event, str(new_event.get("evidence_text", "")))
    if not source_check:
        defects.append("reextracted_wording_not_source_supported")
    if defects:
        return "CONFIRMED_EXTRACTION_DEFECT", defects
    return "REEXTRACTED_ALIGNED", []


def _old_after_is_inserted_anchor(old_after: str, instruction: str) -> bool:
    """Detect a recorded old phrase used as the insertion anchor, not its payload."""
    if not old_after:
        return False
    normalized_old = _normalise(old_after)
    previous_cue_end = 0
    for cue in re.finditer(r"\bshall\s+be\s+inserted\b", instruction, re.I):
        quoted = [
            " ".join((match.group("straight") or match.group("curly") or "").split())
            for match in QUOTED.finditer(instruction, previous_cue_end, cue.start())
        ]
        quoted = [value for value in quoted if value]
        if len(quoted) >= 2 and _normalise(quoted[-2]) == normalized_old and _normalise(quoted[-1]) != normalized_old:
            return True
        previous_cue_end = cue.end()
    return False


def _operation_delta_v2(task: dict[str, Any]) -> dict[str, Any]:
    old_before, old_after = str(task.get("before_text") or ""), str(task.get("after_text") or "")
    provisional = _operation_delta_annotator(task)
    if provisional["label"] in {"High", "Medium", "None"}:
        # Explicit cue/numeric paths do not depend on edit magnitude. The older
        # function's selected explanation identifies its size-only branch.
        if provisional["rationale"] != "The operation changes a large fraction of the controlled fragment without a detected severe cue transition.":
            return {"label": provisional["label"], "status": "PROVISIONAL_RULE_OUTPUT", "rationale": provisional["rationale"], "similarity": provisional.get("similarity")}
    similarity = provisional.get("similarity")
    return {
        "label": None,
        "status": "REVIEW_REQUIRED",
        "rationale": "Token similarity alone is not evidence of materiality; no supported rule cue determines a class.",
        "similarity": similarity,
        "empty_before_is_expected_for_insert": str(task.get("operation", "")).upper() == "INSERT" and not old_before,
        "after_text_present": bool(old_after),
    }


def _source_span_check(event: dict[str, Any] | None, evidence: str) -> bool:
    if not event:
        return False
    norm_source = _normalise(evidence)
    return all(
        not value or _normalise(str(value)) in norm_source
        for value in (event.get("old_text"), event.get("new_text"))
    )


def _consolidated_support(task: dict[str, Any], event: dict[str, Any] | None) -> bool | None:
    if event is None:
        return None
    phrase = str(event.get("new_text") or event.get("old_text") or "")
    if not phrase:
        return None
    snapshots = [
        str(item.get("evidence_text") or "") for item in task.get("source_evidence", [])
        if item.get("role") == "consolidated_after_text_corroboration"
    ]
    if not snapshots:
        return None
    return any(_normalise(phrase) in _normalise(snapshot) for snapshot in snapshots)


def _operation_detail(instruction: str, after_text: str) -> str | None:
    normalized = _normalise(instruction)
    # Detect which numbered subinstruction actually encloses the selected
    # inserted fragment, rather than using only the first path-like phrase.
    if after_text:
        at = normalized.find(_normalise(after_text)[:80])
        prefix = normalized[:at] if at >= 0 else normalized
    else:
        prefix = normalized
    subsection = list(re.finditer(r"in sub section\s*\(?\s*(\d+[a-z]?)", prefix))
    section = re.search(r"(?:after|in) section\s*(\d+[a-z]{0,3})", normalized)
    if subsection:
        return f"section:{section.group(1).upper()}/sub-section:{subsection[-1].group(1).upper()}" if section else f"sub-section:{subsection[-1].group(1).upper()}"
    return f"section:{section.group(1).upper()}" if section else None


def _path_conflicts(left: str, right: str) -> bool:
    left_parts = dict(re.findall(r"([a-z-]+):([a-z0-9]+)", left.casefold()))
    right_parts = dict(re.findall(r"([a-z-]+):([a-z0-9]+)", right.casefold()))
    # A shorter path is less specific, not contradictory. Only conflicting
    # values for a shared path component count as an alignment defect.
    return any(key in right_parts and right_parts[key] != value for key, value in left_parts.items())


def _normalise(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _excerpt(value: Any, size: int = 230) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= size else text[:size].rstrip() + " …"
