"""Run the generalised extractor over every configured amending Act."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from temporal_legal_drift.corpus import CorpusManifest
from temporal_legal_drift.jsonio import atomic_write_new, canonical_json_bytes, load_json

from .extractor import GeneralisedAmendmentExtractor
from .models import UNRESOLVED_REASONS


class AmendmentExtractionPipeline:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.extractor = GeneralisedAmendmentExtractor()

    def run(self) -> dict[str, object]:
        manifest = CorpusManifest.from_file(self.root / "configs/corpus/pilot_v1.json")
        report = load_json(
            self.root / "reports/corpus/india-code-temporal-pilot-v1.lock.json"
        )
        report_by_id = {
            str(item["entry_id"]): item
            for item in report.get("entries", []) if isinstance(item, dict)
        }
        configured = [
            entry for entry in manifest.entries if entry.instrument_type == "amending_act"
        ]
        events = []
        unresolved = []
        processed: list[str] = []
        for entry in configured:
            source = report_by_id.get(entry.entry_id)
            if not source:
                raise ValueError(f"missing corpus report entry for {entry.entry_id}")
            normalized_path = (
                self.root / "data/normalized" / f"{source['normalized_document_id']}.json"
            )
            if not normalized_path.is_file():
                raise ValueError(f"missing normalized amending Act: {normalized_path}")
            document = load_json(normalized_path)
            extracted, failures = self.extractor.extract(
                document,
                source_document=entry.entry_id,
                source_sha256=str(source["sha256"]),
                amending_act=entry.entry_id.replace("-", " ").title(),
            )
            events.extend(item.to_dict() for item in extracted)
            unresolved.extend(item.to_dict() for item in failures)
            processed.append(entry.entry_id)

        event_ids = {str(item["amendment_id"]) for item in events}
        unresolved_event_ids = {
            str(item["amendment_id"])
            for item in unresolved if item.get("amendment_id") is not None
        }
        reasons = Counter(str(item["reason_code"]) for item in unresolved)
        event_count = len(events)
        metrics = {
            "target_identification_coverage": _rate(
                sum(bool(item.get("principal_act") and item.get("target_provision")) for item in events),
                event_count,
            ),
            "operation_resolution_coverage": _rate(
                sum(item.get("operation") != "UNKNOWN" for item in events), event_count
            ),
            "old_new_extraction_coverage": _rate(
                sum(item.get("old_text") is not None or item.get("new_text") is not None for item in events),
                event_count,
            ),
            "commencement_extraction_coverage": _rate(
                sum(item.get("effective_date") is not None for item in events), event_count
            ),
            "unresolved_event_rate": _rate(len(unresolved_event_ids & event_ids), event_count),
            "unresolved_record_count": len(unresolved),
            "unresolved_reason_counts": {
                reason: reasons.get(reason, 0) for reason in sorted(UNRESOLVED_REASONS)
            },
            "real_corpus_accuracy": {
                "target_identification_accuracy": None,
                "operation_accuracy": None,
                "old_new_extraction_accuracy": None,
                "commencement_extraction_accuracy": None,
                "reason": "human-reviewed gold labels are not available",
            },
            "controlled_fixture_accuracy": _controlled_fixture_accuracy(self.extractor),
        }
        document = {
            "schema_version": "1.0.0",
            "extractor_version": "generalised-amendment-extractor-v1",
            "status": "machine_extracted_human_review_required_not_legal_gold",
            "configured_amending_act_count": len(configured),
            "processed_amending_act_count": len(processed),
            "processed_amending_acts": processed,
            "amendment_event_count": event_count,
            "unresolved_count": len(unresolved),
            "all_events_traceable": all(
                bool(item.get("source_document") and item.get("evidence_text"))
                and isinstance(item.get("source_page"), int)
                and isinstance(item.get("source_line"), int)
                and len(str(item.get("source_sha256", ""))) == 64
                for item in events
            ),
            "every_document_accounted_for": all(
                any(item.get("source_document") == entry_id for item in [*events, *unresolved])
                for entry_id in processed
            ),
            "metrics": metrics,
            "events": events,
            "unresolved": unresolved,
        }
        return document

    def write(self, document: dict[str, object], output: Path) -> None:
        atomic_write_new(output, canonical_json_bytes(document))


def _rate(numerator: int, denominator: int) -> dict[str, object]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "percent": round(100.0 * numerator / denominator, 2) if denominator else None,
    }


def _controlled_fixture_accuracy(extractor: GeneralisedAmendmentExtractor) -> dict[str, object]:
    text = """THE FIXTURE (AMENDMENT) ACT, 2021
[12th August, 2021.]
An Act to amend the Fixture Act, 2020.
1. (1) This Act may be called the Fixture (Amendment) Act, 2021.
(2) It shall be deemed to have come into force on the 4th day of April, 2021.
2. In the Fixture Act, 2020, in section 5, for the words "ten days", the words "fifteen days" shall be substituted.
3. In section 6 of the principal Act, after the words "written form", the words "or electronic form" shall be inserted.
4. In section 7 of the principal Act, the words "old requirement" shall be omitted.
5. In the principal Act, section 8 shall be renumbered as section 9.
6. In section 10 of the principal Act, the words "former rule" shall be replaced by the words "revised rule".
7. In section 11 of the principal Act, the provision shall be repealed.
8. Amendment of section 12 of the principal Act.
9. In section 13 of the principal Act, the words "old phrase" shall be omitted and the words "new phrase" shall be inserted.
"""
    document = {"blocks": [{
        "block_id": "fixture-block",
        "source_anchor": "pdf:page:1",
        "normalized_text": text,
    }]}
    events, _ = extractor.extract(
        document,
        source_document="controlled-fixture",
        source_sha256="a" * 64,
        amending_act="Fixture Amendment Act, 2021",
    )
    expected = {
        "section:5": ("SUBSTITUTE", "ten days", "fifteen days"),
        "section:6": ("INSERT", None, "or electronic form"),
        "section:7": ("OMIT", "old requirement", ""),
        "section:8": ("RENUMBER", "8", "9"),
        "section:10": ("REPLACE", "former rule", "revised rule"),
        "section:11": ("REPEAL", None, ""),
        "section:12": ("MODIFY", None, None),
        "section:13": ("UNKNOWN", None, None),
    }
    by_target = {item.target_provision: item for item in events if item.target_provision in expected}
    denominator = len(expected)
    target_correct = len(by_target)
    operation_correct = sum(
        by_target[target].operation == values[0]
        for target, values in expected.items() if target in by_target
    )
    wording_expected = {
        target: values
        for target, values in expected.items()
        if values[0] not in {"MODIFY", "UNKNOWN"}
    }
    wording_correct = sum(
        (by_target[target].old_text, by_target[target].new_text) == values[1:]
        for target, values in wording_expected.items() if target in by_target
    )
    commencement_correct = sum(
        by_target[target].effective_date == "2021-04-04"
        for target in expected if target in by_target
    )
    return {
        "fixture_count": denominator,
        "target_identification_accuracy": _rate(target_correct, denominator),
        "operation_accuracy": _rate(operation_correct, denominator),
        "old_new_extraction_accuracy": _rate(wording_correct, len(wording_expected)),
        "commencement_extraction_accuracy": _rate(commencement_correct, denominator),
        "scope": "controlled parser fixtures only; not real-corpus legal accuracy",
    }
