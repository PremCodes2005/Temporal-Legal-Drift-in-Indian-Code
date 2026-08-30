"""Read-only research views and controlled dashboard submissions."""

from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from temporal_legal_drift.comparison import analyze_legal_drift
from temporal_legal_drift.gates import check_engineering_gates
from temporal_legal_drift.jsonio import atomic_write_new, canonical_json_bytes, load_json
from temporal_legal_drift.llm_evaluation import build_drift_evaluation_from_executed_plan
from temporal_legal_drift.parsing.models import ParseContext
from temporal_legal_drift.parsing.pdf import PdfParser


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_UPLOAD_SUFFIXES = {".pdf", ".json"}


class DashboardService:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def overview(self) -> dict[str, object]:
        corpus = self._load("reports/corpus/india-code-temporal-pilot-v1.lock.json")
        graph = self._load("reports/phase3/version_graph.lock.json")
        llm = self._load("reports/phase9/evaluation_plan.lock.json")
        explanation = self._load("reports/phase10/explanation_plan.lock.json")
        reproduction = self._load("reports/phase11/reproducibility.lock.json")
        demo = self._load("experiments/phase9/temporal_drift_demo.results.v1.json")
        gates = check_engineering_gates(self.root)
        return {
            "project": {
                "title": "Temporal Legal Drift in the Indian Code",
                "subtitle": "Temporal legal reasoning and compliance-drift evaluation",
                "trl": 2,
                "engineering_phase": 11,
                "core_question": "Do LLM-based compliance systems correctly propagate legally applicable changes in Indian law over time?",
            },
            "metrics": {
                "corpus_documents": corpus.get("entry_count"),
                "provision_versions": graph.get("version_count"),
                "amendment_candidates": graph.get("amendment_event_count"),
                "controlled_llm_runs": llm.get("executed_run_count"),
                "explanations_evaluated": explanation.get("automated_evaluation_count"),
                "engineering_gates_passed": sum(item.engineering_passed for item in gates),
                "engineering_gate_total": len(gates),
                "reproducibility_artifacts": reproduction.get("artifact_count"),
                "demo_false_stability_rate": demo.get("metrics", {}).get(
                    "false_stability_rate"
                ),
            },
            "status": {
                "engineering": "passed" if all(item.engineering_passed for item in gates) else "attention",
                "legal_validation": "not_performed",
                "benchmark": "not_frozen",
                "research_claims": "not_available",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "boundaries": [
                "The corpus is an authoritative-source technical pilot, not legal gold.",
                "The 78-run experiment verifies execution; it does not measure model performance.",
                "The one-pair drift result is a non-gold controlled demonstration.",
                "Independent qualified legal review remains unavailable.",
            ],
        }

    def gates(self) -> dict[str, object]:
        results = check_engineering_gates(self.root)
        return {
            "all_engineering_passed": all(item.engineering_passed for item in results),
            "qualified_review_complete": all(item.review_status == "approved" for item in results),
            "phases": [item.to_dict() for item in results],
        }

    def corpus(self) -> dict[str, object]:
        report = self._load("reports/corpus/india-code-temporal-pilot-v1.lock.json")
        entries = []
        for raw in report.get("entries", []):
            if not isinstance(raw, dict):
                continue
            filename = f"{raw.get('entry_id')}.pdf"
            entries.append(
                {
                    "entry_id": raw.get("entry_id"),
                    "official_identifier": raw.get("official_identifier"),
                    "research_role": raw.get("research_role"),
                    "source_url": raw.get("parent_reference_url"),
                    "sha256": raw.get("sha256"),
                    "byte_length": raw.get("byte_length"),
                    "normalized_blocks": raw.get("normalized_block_count"),
                    "parser": raw.get("parser_name"),
                    "risk": raw.get("known_extraction_risk"),
                    "pdf_filename": filename,
                    "pdf_available": (self.root / "data/corpus/pdfs" / filename).is_file(),
                    "pdf_url": f"/corpus/{filename}",
                }
            )
        return {
            "manifest_id": report.get("manifest_id"),
            "status": report.get("manifest_status"),
            "legal_validation_status": report.get("legal_validation_status"),
            "entry_count": len(entries),
            "total_bytes": report.get("total_bytes"),
            "total_normalized_blocks": report.get("total_normalized_blocks"),
            "entries": entries,
        }

    def demo(self) -> dict[str, object]:
        scenario_document = self._load("data/scenarios/temporal_drift_demo.v1.json")
        experiment = self._load("experiments/phase9/temporal_drift_demo.v1.json")
        results = self._load("experiments/phase9/temporal_drift_demo.results.v1.json")
        scenario = scenario_document.get("scenarios", [{}])[0]
        runs = []
        for run in experiment.get("runs", []):
            if isinstance(run, dict):
                runs.append(
                    {
                        "run_id": run.get("run_id"),
                        "condition": run.get("condition"),
                        "status": run.get("execution_status"),
                        "response": run.get("raw_response"),
                    }
                )
        return {
            "scenario": scenario,
            "results": results,
            "runs": sorted(runs, key=lambda item: str(item["condition"])),
            "execution": experiment.get("execution"),
        }

    def architecture(self) -> dict[str, object]:
        return {
            "stages": [
                {"phase": "1", "title": "Authoritative sources", "detail": "India Code PDFs, provenance and immutable hashes"},
                {"phase": "2", "title": "Parsing & normalization", "detail": "Deterministic blocks with parser provenance"},
                {"phase": "3", "title": "Version reconstruction", "detail": "Instrument, lineage, versions and amendment events"},
                {"phase": "4", "title": "Temporal applicability", "detail": "Scenario + date → applicable version with evidence"},
                {"phase": "5–7", "title": "Benchmark construction", "detail": "Materiality, scenarios, leakage-safe release"},
                {"phase": "8–10", "title": "Evaluation", "detail": "Baselines, LLM drift and explanation support"},
                {"phase": "11", "title": "Reproducibility", "detail": "Fresh-environment checks and artifact reconciliation"},
            ],
            "concepts": [
                {"name": "Materiality", "definition": "How legally significant is the amendment?"},
                {"name": "Temporal applicability", "definition": "Which legal version governs this scenario at this time?"},
                {"name": "Compliance consequence", "definition": "What does that applicable version imply for the facts?"},
            ],
        }

    def submit_scenario(self, value: dict[str, object]) -> dict[str, object]:
        title = _required_text(value, "title", 160)
        legal_question = _required_text(value, "legal_question", 2000)
        facts_text = _required_text(value, "facts", 8000)
        pre_date = _iso_date(value.get("pre_reference_date"), "pre_reference_date")
        post_date = _iso_date(value.get("post_reference_date"), "post_reference_date")
        if post_date <= pre_date:
            raise ValueError("Post-amendment date must be after the pre-amendment date")
        expected_change = value.get("expected_change")
        if expected_change not in {"change", "stable", "unknown"}:
            raise ValueError("Expected change must be change, stable or unknown")
        for answer_field in ("expected_pre_answer", "expected_post_answer"):
            answer = value.get(answer_field, "unknown")
            if answer not in {"compliant", "non_compliant", "indeterminate", "unknown", None}:
                raise ValueError(f"{answer_field} uses an unsupported answer label")
        materiality = value.get("materiality_level")
        if materiality not in {"High", "Medium", "Low", "None", "", None}:
            raise ValueError("Materiality must be High, Medium, Low, None or unassigned")
        evidence_ids = value.get("evidence_ids", [])
        if not isinstance(evidence_ids, list) or not all(isinstance(item, str) for item in evidence_ids):
            raise ValueError("Evidence IDs must be a list of strings")
        facts = [line.strip() for line in facts_text.splitlines() if line.strip()]
        if not facts:
            raise ValueError("Provide at least one scenario fact")
        scenario_id = f"submitted_{uuid4().hex}"
        record = {
            "schema_version": "1.0.0-submission",
            "scenario_id": scenario_id,
            "title": title,
            "facts": facts,
            "legal_question": legal_question,
            "pre_reference_date": pre_date.isoformat(),
            "post_reference_date": post_date.isoformat(),
            "pre_applicable_version_id": value.get("pre_applicable_version_id"),
            "post_applicable_version_id": value.get("post_applicable_version_id"),
            "amendment_event_id": value.get("amendment_event_id"),
            "expected_change": expected_change,
            "expected_pre_answer": value.get("expected_pre_answer"),
            "expected_post_answer": value.get("expected_post_answer"),
            "expected_compliance_consequence": value.get("expected_compliance_consequence"),
            "materiality_level": materiality,
            "domain": value.get("domain"),
            "legal_instrument": value.get("legal_instrument"),
            "provision_path": value.get("provision_path"),
            "evidence_ids": evidence_ids,
            "expert_rationale": value.get("expert_rationale"),
            "notes": value.get("notes"),
            "status": "submitted_for_human_review_not_gold",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        output = self.root / "data/submissions/scenarios" / f"{scenario_id}.json"
        atomic_write_new(output, canonical_json_bytes(record))
        return {
            "accepted": True,
            "scenario_id": scenario_id,
            "status": record["status"],
            "message": "Scenario saved to the review queue. It is not benchmark gold.",
        }

    def upload_evidence(self, value: dict[str, object]) -> dict[str, object]:
        filename = _safe_filename(_required_text(value, "filename", 180))
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_UPLOAD_SUFFIXES:
            raise ValueError("Only PDF and JSON evidence files are accepted")
        encoded = _required_text(value, "content_base64", MAX_UPLOAD_BYTES * 2)
        try:
            payload = base64.b64decode(encoded, validate=True)
        except ValueError as error:
            raise ValueError("Upload content is not valid base64") from error
        if not payload or len(payload) > MAX_UPLOAD_BYTES:
            raise ValueError("Upload must be between 1 byte and 20 MB")
        if suffix == ".pdf" and not payload.startswith(b"%PDF-"):
            raise ValueError("The uploaded file does not have a valid PDF signature")
        if suffix == ".json":
            try:
                json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("The uploaded JSON is invalid") from error
        digest = sha256(payload).hexdigest()
        upload_id = f"upload_{digest[:24]}"
        directory = self.root / "data/submissions/uploads" / upload_id
        atomic_write_new(directory / filename, payload)
        metadata = {
            "schema_version": "1.0.0",
            "upload_id": upload_id,
            "filename": filename,
            "sha256": digest,
            "byte_length": len(payload),
            "category": value.get("category"),
            "official_identifier": value.get("official_identifier"),
            "source_url": value.get("source_url"),
            "uploader_asserts_authoritative_source": value.get("authoritative_confirmation") is True,
            "status": "evidence_review_queue_not_corpus",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        atomic_write_new(directory / "metadata.json", canonical_json_bytes(metadata))
        return {
            "accepted": True,
            "upload_id": upload_id,
            "sha256": digest,
            "byte_length": len(payload),
            "status": metadata["status"],
            "message": "Evidence saved to the review queue; it was not added to the corpus.",
        }

    def compare_amendments(self, value: dict[str, object]) -> dict[str, object]:
        """Extract and compare two PDFs without adding them to the corpus."""
        question = _required_text(value, "question", 4000)
        facts_raw = value.get("facts", "")
        if not isinstance(facts_raw, str) or len(facts_raw) > 8000:
            raise ValueError("facts must be text no longer than 8000 characters")
        pre_name, pre_payload = _pdf_from_request(value, "pre")
        post_name, post_payload = _pdf_from_request(value, "post")
        pre_text, pre_pages, pre_warnings = _extract_pdf_text(pre_name, pre_payload)
        post_text, post_pages, post_warnings = _extract_pdf_text(post_name, post_payload)
        result = analyze_legal_drift(pre_text, post_text, question, facts_raw)
        result["documents"] = {
            "pre": {
                "filename": pre_name,
                "sha256": sha256(pre_payload).hexdigest(),
                "page_count": pre_pages,
                "warnings": pre_warnings,
            },
            "post": {
                "filename": post_name,
                "sha256": sha256(post_payload).hexdigest(),
                "page_count": post_pages,
                "warnings": post_warnings,
            },
        }
        result["question"] = question
        return result

    def score_demo(self) -> dict[str, object]:
        return build_drift_evaluation_from_executed_plan(
            self._load("experiments/phase9/temporal_drift_demo.v1.json"),
            self._load("data/scenarios/temporal_drift_demo.v1.json"),
        )

    def run_tests(self, timeout_seconds: int = 120) -> dict[str, object]:
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        output = completed.stdout + completed.stderr
        match = re.search(r"Ran (\d+) tests?", output)
        return {
            "passed": completed.returncode == 0,
            "exit_code": completed.returncode,
            "test_count": int(match.group(1)) if match else None,
            "output_tail": output[-6000:],
        }

    def _load(self, relative: str) -> dict[str, object]:
        return load_json(self.root / relative)


def _required_text(value: dict[str, object], field: str, maximum: int) -> str:
    raw = value.get(field)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{field} is required")
    text = raw.strip()
    if len(text) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")
    return text


def _iso_date(value: object, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{field} is required")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field} must use YYYY-MM-DD") from error


def _safe_filename(value: str) -> str:
    name = Path(value).name
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    if not safe or safe != name:
        raise ValueError("Filename contains unsupported characters")
    return safe


def _pdf_from_request(value: dict[str, object], prefix: str) -> tuple[str, bytes]:
    filename = _safe_filename(_required_text(value, f"{prefix}_filename", 180))
    if Path(filename).suffix.lower() != ".pdf":
        raise ValueError(f"{prefix}_filename must be a PDF")
    encoded = _required_text(value, f"{prefix}_content_base64", MAX_UPLOAD_BYTES * 2)
    try:
        payload = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise ValueError(f"{prefix} PDF content is not valid base64") from error
    if not payload or len(payload) > MAX_UPLOAD_BYTES:
        raise ValueError(f"{prefix} PDF must be between 1 byte and 20 MB")
    if not payload.startswith(b"%PDF-"):
        raise ValueError(f"{prefix} file does not have a valid PDF signature")
    return filename, payload


def _extract_pdf_text(filename: str, payload: bytes) -> tuple[str, int, list[str]]:
    digest = sha256(payload).hexdigest()
    context = ParseContext(
        source_artifact_id=f"comparison_{digest[:24]}",
        source_sha256=digest,
        media_type="application/pdf",
        filename=filename,
    )
    try:
        document = PdfParser().parse(payload, context)
    except Exception as error:
        raise ValueError(f"Could not extract text from {filename}: {error}") from error
    text = "\n".join(block.normalized_text for block in document.blocks)
    return text, len(document.blocks), list(document.warnings)
