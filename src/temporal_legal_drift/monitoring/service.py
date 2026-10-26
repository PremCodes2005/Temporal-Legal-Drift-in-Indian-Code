"""Incremental, 24-hour-gated official-source monitoring (plan.md §0.7, ADR 0008, ADR 0009).

Each discovered official document follows a persisted state machine:

    DISCOVERED → FETCHED → HASHED → VERIFIED → EXTRACTION_PENDING → PROCESSED
                                               ↘ REVIEW_REQUIRED / FAILED

Every transition is written before the next stage starts, so a crash resumes
only incomplete stages. A known document whose source metadata is unchanged is
not re-downloaded; identical bytes are never reprocessed; changed bytes for the
same official ID create a new linked version. Nothing here asserts legal
effect: discovery, a changed PDF, an amendment event, a commenced change and a
changed scenario answer are different findings, and new documents never alter
the active graph, frozen releases or the base index.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import time
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Iterator
from urllib.parse import urlparse
from uuid import uuid4
from zoneinfo import ZoneInfo

from temporal_legal_drift.acquisition.models import utc_now_iso
from temporal_legal_drift.amendment_extraction.extractor import GeneralisedAmendmentExtractor
from temporal_legal_drift.amendment_extraction.models import EXTRACTOR_VERSION
from temporal_legal_drift.jsonio import atomic_replace, atomic_write_new, canonical_json_bytes, load_json
from temporal_legal_drift.parsing.text_quality import TEXT_QUALITY_VERSION, quarantine_document

from .commencement import extract_commencement, find_conflicts
from .indiacode import DiscoveredRecord, SourceShapeError

WINDOW = timedelta(hours=24)
LEASE = timedelta(hours=6)
MISSED_RUN_GRACE = timedelta(hours=2)  # the trigger fires hourly; two silent hours past eligibility means it is not running
STALE_AFTER_HOURS = 48
MAX_STAGE_ATTEMPTS = 3
ROOT = "data/monitoring"
PIPELINE_VERSION = "source-monitoring-v2"
TERMINAL = {"PROCESSED", "REVIEW_REQUIRED"}
# A start due this soon waits for it, so a few seconds of start-up jitter never pushes the daily run to the next trigger.
SLOT_TOLERANCE = timedelta(minutes=10)
ON_TIME = timedelta(hours=1)  # a start within one trigger period after its slot is on time, even if the trigger is offset
ALERTS_LEDGER = "alerts_sent.v1.jsonl"
QUARANTINE_REASONS = ("SOURCE_TEXT", "PARSER_UNAVAILABLE", "not a PDF", "listed size")


def next_eligible(start: datetime, schedule: tuple[int, int, str] | None = None) -> datetime:
    """24 h after this start. With a daily slot, a start more than an hour after its slot (a catch-up) moves the next
    start to the first slot at least 24 h later, so the run returns to its slot instead of staying late."""
    earliest = start + WINDOW
    if schedule is None:
        return earliest
    hour, minute, zone = schedule
    started = start.astimezone(ZoneInfo(zone))
    own_slot = started.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if own_slot > started + SLOT_TOLERANCE:
        own_slot = (own_slot - timedelta(days=1)).replace(hour=hour, minute=minute)
    if started < own_slot + ON_TIME:
        return earliest
    local = (earliest - SLOT_TOLERANCE).astimezone(ZoneInfo(zone))
    slot = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if slot < local:
        slot = (slot + timedelta(days=1)).replace(hour=hour, minute=minute)
    return max(earliest, slot.astimezone(timezone.utc))


def machine_state(version: dict[str, Any]) -> str:
    """The explicit machine state of one document version; no state here needs or implies a human decision."""
    state = version.get("state")
    if state == "PROCESSED":
        return "CANDIDATE_AMENDMENT" if ((version.get("stages") or {}).get("extract") or {}).get("events") else "PROCESSED"
    if state == "REVIEW_REQUIRED":
        reason = str(version.get("review_reason") or "")
        return "QUARANTINED" if any(code in reason for code in QUARANTINE_REASONS) else "UNRESOLVED"
    if state == "FAILED":
        return "FAILED_RETRYING"
    return "DISCOVERED"


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _normal(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(text).casefold()))


class MonitoringService:
    def __init__(self, root: Path, connectors: dict[str, Any], *, clock: Callable[[], str] = utc_now_iso,
                 parser: Any | None = None,
                 index_updater: Callable[[Path, list[dict[str, Any]]], dict[str, Any]] | None = None,
                 graph_mapper: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
                 schedule: tuple[int, int, str] | None = None, sleep: Callable[[float], None] = time.sleep) -> None:
        self.root = root.resolve()
        self.base = self.root / ROOT
        self.connectors = connectors
        self.clock = clock
        self.parser = parser
        self.index_updater = index_updater
        self.graph_mapper = graph_mapper
        self.schedule = schedule  # (hour, minute, IANA zone) of the daily run, or None for "24 h after the last start"
        self.sleep = sleep

    # ---------- scheduling ----------
    def run_due(self, owner: str, *, manual_reason: str | None = None) -> list[dict[str, Any]]:
        """Each source starts at most once per 24 h after its previous start, even after errors or restarts."""
        self.resume_incomplete()
        return [result for key in sorted(self.connectors) if (result := self._run_source(key, owner, manual_reason)) is not None]

    def backfill(self, source_key: str, owner: str, *, pages: int, reason: str) -> dict[str, Any]:
        """Bounded historical pages; recorded as backfill and never moves the daily window."""
        if not 1 <= pages <= 20:
            raise ValueError("backfill pages must be between 1 and 20")
        if len(reason.strip()) < 10:
            raise ValueError("backfill requires a reason")
        return self._execute(source_key, owner, mode="BACKFILL", since=None, max_pages=pages, reason=reason)

    def _run_source(self, key: str, owner: str, manual_reason: str | None) -> dict[str, Any] | None:
        now = _parse_time(self.clock())
        if manual_reason is not None and len(manual_reason.strip()) < 10:
            raise ValueError("a manual retry requires a reason")
        if manual_reason is None and self.schedule is not None:
            with self._locked_state() as state:
                eligible = state.get(key, {}).get("next_eligible_at")
            wait = (_parse_time(eligible) - now).total_seconds() if eligible else 0
            if 0 < wait <= SLOT_TOLERANCE.total_seconds():
                self.sleep(wait)
                now = _parse_time(self.clock())
        with self._locked_state() as state:
            entry = state.setdefault(key, {"source_key": key})
            eligible = entry.get("next_eligible_at")
            if manual_reason is None and eligible and _parse_time(eligible) > now:
                return None  # not due
            lease_until = entry.get("lease_expires_at")
            if lease_until and _parse_time(lease_until) > now:
                return {"source_key": key, "status": "SKIPPED_LEASE_HELD", "lease_owner": entry.get("lease_owner")}
            # The window is anchored to this attempt's start and persisted before any network call.
            entry.update(lease_owner=owner, lease_expires_at=(now + LEASE).isoformat(), last_attempt_at=now.isoformat())
            if manual_reason is None:
                entry["next_eligible_at"] = next_eligible(now, self.schedule).isoformat()
                entry["schedule"] = f"{self.schedule[0]:02d}:{self.schedule[1]:02d} {self.schedule[2]}" if self.schedule else None
            since = entry.get("cursor")
        mode = "MANUAL_RETRY" if manual_reason else "SCHEDULED"
        result = self._execute(key, owner, mode=mode, since=since, max_pages=5 if since else 1, reason=manual_reason)
        with self._locked_state() as state:
            entry = state[key]
            entry.update(lease_owner=None, lease_expires_at=None, last_run_id=result["run_id"], last_status=result["status"],
                         last_completed_at=result["completed_at"],
                         last_run_counts={"listed": result["listed"], "retried": result["retried"], **result["counts"]})
            if result["status"] in {"OK", "PARTIAL_FAILURE"}:
                entry["last_success_at"] = result["completed_at"]
                if result.get("cursor"):
                    entry["cursor"] = max(result["cursor"], entry.get("cursor") or "")
        return result

    # ---------- one run ----------
    def _execute(self, key: str, owner: str, *, mode: str, since: str | None, max_pages: int,
                 reason: str | None) -> dict[str, Any]:
        run_id = f"mon_{uuid4().hex[:20]}"
        manifest: dict[str, Any] = {"schema_version": "2.0.0", "pipeline_version": PIPELINE_VERSION, "run_id": run_id,
                                    "source_key": key, "mode": mode, "owner": owner, "reason": reason,
                                    "started_at": self.clock(), "since_cursor": since, "records": []}
        connector = self.connectors[key]
        try:
            discovered = connector.discover(since, max_pages=max_pages)
            manifest["status"] = "OK"
        except SourceShapeError as error:
            discovered, manifest["status"], manifest["error"] = [], "SOURCE_SHAPE_CHANGED", str(error)
        except Exception as error:  # outage, HTTP failure, policy refusal: observable, retried next window
            discovered, manifest["status"], manifest["error"] = [], "SOURCE_UNAVAILABLE", f"{type(error).__name__}: {error}"
        for record in discovered:
            manifest["records"].append(self._ingest(record, connector, run_id))
        manifest["listed"], manifest["retried"] = len(discovered), 0
        if manifest["status"] == "OK":
            listed = {record.official_id for record in discovered}
            for doc in self.documents():
                version = doc["versions"][-1] if doc["versions"] else None
                if (doc["source_key"] != key or doc["official_id"] in listed or not version or version["state"] in TERMINAL
                        or version.get("sha256")):
                    continue  # fetched versions resume from their stored artifact instead
                record = DiscoveredRecord(**version["record"])
                if not record.bitstream_url:
                    self._settle_without_pdf(doc, version, record, run_id)
                    continue
                retried = self._advance(doc, version, record, connector, run_id)
                self._observe(record, run_id, version.get("sha256"), retried["status"], version.get("error"), version.get("previous_sha256"))
                manifest["records"].append({"doc_id": doc["doc_id"], "official_id": record.official_id, "title": record.title,
                                            "retried": True, **retried})
                manifest["retried"] += 1
        statuses = [item["status"] for item in manifest["records"]]
        manifest["counts"] = {name: statuses.count(name) for name in sorted(set(statuses))}
        manifest["cursor"] = max((r.accessioned_at for r in discovered), default=None)
        if manifest["status"] == "OK" and "FAILED" in statuses:
            manifest["status"] = "PARTIAL_FAILURE"
        manifest["completed_at"] = self.clock()
        atomic_write_new(self.base / "runs" / f"{run_id}.json", canonical_json_bytes(manifest))
        return manifest

    # ---------- per-document state machine ----------
    def _ingest(self, record: DiscoveredRecord, connector: Any, run_id: str) -> dict[str, Any]:
        doc_id = "doc_" + sha256(f"{record.source_key}\n{record.official_id}".encode()).hexdigest()[:20]
        doc = self._load_document(doc_id) or {"schema_version": "1.0.0", "doc_id": doc_id, "source_key": record.source_key,
                                               "official_id": record.official_id, "versions": []}
        base = {"doc_id": doc_id, "official_id": record.official_id, "title": record.title}
        fingerprint = record.metadata_fingerprint()
        latest = doc["versions"][-1] if doc["versions"] else None
        if not record.download_eligible or not record.bitstream_url:
            self._observe(record, run_id, None, "METADATA_ONLY")
            return {**base, "status": "METADATA_ONLY"}
        if latest and latest["metadata_fingerprint"] == fingerprint and latest["state"] in TERMINAL:
            # The source describes the same bytes as a completed version: no download, no downstream work.
            self._observe(record, run_id, latest.get("sha256"), "UNCHANGED_NOT_REFETCHED")
            return {**base, "status": "UNCHANGED", "version": latest["version"]}
        if latest and latest["state"] not in TERMINAL and latest["metadata_fingerprint"] == fingerprint:
            version = latest  # interrupted earlier: resume only incomplete stages
        else:
            version = {"version": len(doc["versions"]) + 1, "metadata_fingerprint": fingerprint, "state": "DISCOVERED",
                       "history": [], "record": asdict(record), "attempts": 0}
            doc["versions"].append(version)
            self._transition(doc, version, "DISCOVERED", run_id)
        result = self._advance(doc, version, record, connector, run_id)
        self._observe(record, run_id, version.get("sha256"), result["status"], version.get("error"),
                      version.get("previous_sha256"))
        return {**base, **result}

    def _advance(self, doc: dict, version: dict, record: DiscoveredRecord, connector: Any, run_id: str) -> dict[str, Any]:
        try:
            if not version.get("sha256"):
                payload = connector.download(record.bitstream_url)
                digest = sha256(payload).hexdigest()
                relative = f"data/raw/monitoring/sha256/{digest[:2]}/{digest}.pdf"
                atomic_write_new(self.root / relative, payload)  # identical bytes share one immutable artifact
                version.update(sha256=digest, artifact=relative)
                self._transition(doc, version, "FETCHED", run_id)
            payload = (self.root / version["artifact"]).read_bytes()
            if "HASHED" not in self._done(version):
                if sha256(payload).hexdigest() != version["sha256"]:
                    raise ValueError("stored artifact no longer matches its recorded SHA-256")
                earlier = [v for v in doc["versions"] if v is not version and v.get("sha256")]
                version["previous_sha256"] = earlier[-1]["sha256"] if earlier else None
                version["same_bytes_as_official_ids"] = sorted({
                    o["official_id"] for o in self.observations()
                    if o.get("sha256") == version["sha256"] and o["official_id"] != record.official_id})
                self._transition(doc, version, "HASHED", run_id)
                if earlier and earlier[-1]["sha256"] == version["sha256"]:
                    # Same bytes as the previous version: only the source metadata changed.
                    version["same_bytes_as_version"] = earlier[-1]["version"]
                    self._transition(doc, version, earlier[-1]["state"], run_id)
                    return {"status": "UNCHANGED", "version": version["version"], "sha256": version["sha256"]}
            elif sha256(payload).hexdigest() != version["sha256"]:
                raise ValueError("stored artifact no longer matches its recorded SHA-256")
            if "VERIFIED" not in self._done(version):
                problem = self._verify(payload, record)
                if problem:
                    version["review_reason"] = problem
                    self._transition(doc, version, "REVIEW_REQUIRED", run_id)
                    return self._queue(doc, version, record, "REVIEW_REQUIRED")
                self._transition(doc, version, "VERIFIED", run_id)
                self._transition(doc, version, "EXTRACTION_PENDING", run_id)
            stages = self._process(version["sha256"], payload, record)
            version["stages"] = stages
            outcome = "PROCESSED" if stages.get("terminal") == "PROCESSED" else "REVIEW_REQUIRED"
            version["review_reason"] = stages.get("review_reason")
            self._transition(doc, version, outcome, run_id)
            return self._queue(doc, version, record, outcome)
        except Exception as error:  # recoverable: resumed at the next run, bounded attempts
            version["attempts"] = version.get("attempts", 0) + 1
            version["error"] = f"{type(error).__name__}: {error}"
            state = "REVIEW_REQUIRED" if version["attempts"] >= MAX_STAGE_ATTEMPTS else "FAILED"
            self._transition(doc, version, state, run_id)
            return {"status": "FAILED" if state == "FAILED" else "REVIEW_REQUIRED", "error": version["error"],
                    "version": version["version"]}

    def resume_incomplete(self) -> list[dict[str, Any]]:
        """Finish interrupted or failed versions from stored artifacts; never rediscovers or refetches early."""
        resumed = []
        for doc in self.documents():
            version = doc["versions"][-1] if doc["versions"] else None
            if not version or version["state"] in TERMINAL:
                continue
            record = DiscoveredRecord(**version["record"])
            if not version.get("sha256"):
                if not record.bitstream_url:
                    self._settle_without_pdf(doc, version, record, f"resume_{uuid4().hex[:16]}")
                continue  # never fetched: retried by its source's next scheduled run
            resumed.append({"doc_id": doc["doc_id"], **self._advance(doc, version, record, None, f"resume_{uuid4().hex[:16]}")})
        return resumed

    def _settle_without_pdf(self, doc: dict, version: dict, record: DiscoveredRecord, run_id: str) -> None:
        """A ledger entry from before items without a single PDF were listed only: abstain; there is nothing to fetch."""
        version.update(review_reason="NO_SINGLE_PDF_LISTED", first_error=version.pop("error", None))
        self._transition(doc, version, "REVIEW_REQUIRED", run_id)
        self._observe(record, run_id, None, "METADATA_ONLY")

    @staticmethod
    def _verify(payload: bytes, record: DiscoveredRecord) -> str | None:
        if not payload.startswith(b"%PDF-"):
            return "downloaded bytes are not a PDF"
        if record.size_tolerance and record.bitstream_bytes:
            if abs(len(payload) - record.bitstream_bytes) > record.bitstream_bytes * record.size_tolerance:
                return f"size {len(payload)} differs from the listed size {record.bitstream_bytes} beyond tolerance"
        return None

    # ---------- downstream stages ----------
    def _process(self, digest: str, payload: bytes, record: DiscoveredRecord) -> dict[str, Any]:
        stages: dict[str, Any] = {"pipeline_version": PIPELINE_VERSION}
        if self.parser is None:
            return {**stages, "parse": "PARSER_UNAVAILABLE", "terminal": "REVIEW_REQUIRED", "review_reason": "PARSER_UNAVAILABLE"}
        parser_version = f"{getattr(self.parser, 'name', 'parser')}-{getattr(self.parser, 'version', '0')}"
        normalized_path = self.base / "normalized" / f"{digest}.{parser_version}.json"
        if normalized_path.is_file():
            stages["parse"] = "CACHED"
        else:
            from temporal_legal_drift.parsing.models import ParseContext

            try:
                document = self.parser.parse(payload, ParseContext(record.official_id, digest, "application/pdf", f"{digest}.pdf"))
            except Exception as error:
                return {**stages, "parse": f"FAILED: {type(error).__name__}", "terminal": "REVIEW_REQUIRED",
                        "review_reason": "SOURCE_TEXT_UNREADABLE"}
            atomic_write_new(normalized_path, canonical_json_bytes(document.to_dict()))
            stages["parse"] = "OK"
        # Untrustworthy lines (Devanagari text layer, legacy-font mojibake) are withheld before any use.
        document, quarantine = quarantine_document(load_json(normalized_path))
        if quarantine["withheld_lines"]:
            quarantine_path = self.base / "quarantine" / f"{digest}.{parser_version}.{TEXT_QUALITY_VERSION}.json"
            if not quarantine_path.is_file():
                atomic_write_new(quarantine_path, canonical_json_bytes(
                    {**quarantine, "official_id": record.official_id, "sha256": digest, "parser": parser_version}))
        fidelity = _text_fidelity(document)
        fidelity["quarantine"] = {key: quarantine[key] for key in ("version", "status", "withheld_lines", "by_reason")}
        stages["text_fidelity"] = fidelity
        if fidelity["status"] == "UNREADABLE":
            reason = "SOURCE_TEXT_QUARANTINED" if quarantine["withheld_lines"] else "SOURCE_TEXT_UNREADABLE"
            return {**stages, "terminal": "REVIEW_REQUIRED", "review_reason": reason}
        events, unresolved = GeneralisedAmendmentExtractor().extract(
            document, source_document=record.official_id, source_sha256=digest, amending_act=record.title,
            source_risk="automated text-fidelity check flagged this document" if fidelity["status"] == "UNRELIABLE" else None)
        candidates = []
        for event in (item.to_dict() for item in events):
            fingerprint = "evt_" + sha256(_normal(event["evidence_text"]).encode()).hexdigest()[:24]
            reasons = sorted({u.reason_code for u in unresolved if u.amendment_id == event["amendment_id"]})
            candidates.append(self._record_candidate(fingerprint, event, record, digest, reasons))
        stages["extract"] = {"version": EXTRACTOR_VERSION, "events": len(events), "unresolved_records": len(unresolved),
                             "candidate_fingerprints": [item["fingerprint"] for item in candidates]}
        stages["applicability"] = {
            "status": "NOT_DETERMINED",
            "publication_fact": {"date": record.stated_dates.get("published") or record.stated_dates.get("issued"),
                                 "status": "UNAPPROVED", "note": "publication is not commencement"},
        }
        commencement = extract_commencement(document, official_id=record.official_id, sha256=digest,
                                            published=record.stated_dates.get("published"))
        if commencement is not None:
            stages["commencement"] = self._record_commencement(commencement)
        if fidelity["status"] == "UNRELIABLE":  # extracted for review only; never served as evidence
            return {**stages, "index": {"status": "WITHHELD", "reason": "SOURCE_TEXT_UNRELIABLE"},
                    "terminal": "REVIEW_REQUIRED", "review_reason": "SOURCE_TEXT_UNRELIABLE"}
        if self.index_updater is None:
            stages["index"] = {"status": "NOT_CONFIGURED"}
        else:
            try:
                stages["index"] = self.index_updater(self.root, self.processed_documents(include=(record.official_id, digest)))
            except Exception as error:  # the previous overlay stays active; the document waits for review
                return {**stages, "index": {"status": "FAILED", "error": f"{type(error).__name__}: {error}"},
                        "terminal": "REVIEW_REQUIRED", "review_reason": "INDEX_UPDATE_FAILED"}
        stages["terminal"] = "PROCESSED"
        return stages

    def _record_commencement(self, commencement: dict[str, Any]) -> dict[str, Any]:
        """Write-once per content hash; conflicts with earlier notifications are recorded, never resolved."""
        folder = self.base / "commencement"
        path = folder / f"{commencement['official_id']}.{commencement['sha256'][:12]}.json"
        with self._file_lock("commencement"):
            if not path.is_file():
                existing = [load_json(item) for item in sorted(folder.glob("*.json"))] if folder.is_dir() else []
                commencement = {**commencement, "conflicts": find_conflicts(commencement, existing)}
                atomic_write_new(path, canonical_json_bytes(commencement))
            stored = load_json(path)
        return {"status": stored["status"], "record": path.name, "legal_effect_claimed": False,
                "facts": sum(f["fact_type"] != "publication" for f in stored["facts"]),
                "unresolved": len(stored["unresolved"]), "conflicts": len(stored["conflicts"])}

    def commencement_records(self) -> list[dict[str, Any]]:
        folder = self.base / "commencement"
        return [load_json(path) for path in sorted(folder.glob("*.json"))] if folder.is_dir() else []

    def _record_candidate(self, fingerprint: str, event: dict[str, Any], record: DiscoveredRecord, digest: str,
                          reasons: list[str]) -> dict[str, Any]:
        """One candidate per amendment text; a second portal adds provenance instead of a duplicate event."""
        path = self.base / "candidates" / f"{fingerprint}.json"
        provenance = {"source_key": record.source_key, "official_id": record.official_id, "sha256": digest,
                      "page": event.get("source_page"), "line": event.get("source_line"), "canonical_url": record.canonical_url}
        with self._file_lock("candidates"):
            existing = load_json(path) if path.is_file() else {
                "schema_version": "1.0.0", "fingerprint": fingerprint, "status": "MACHINE_CANDIDATE_PENDING_REVIEW",
                "event": event, "unresolved_reasons": reasons, "provenance": [],
                "graph_candidate": self.graph_mapper(event) if self.graph_mapper else {"status": "NOT_CONFIGURED"},
                "materiality_triage": _materiality_triage(event, reasons),
                "legal_effect_claimed": False,
            }
            if provenance not in existing["provenance"]:
                existing["provenance"].append(provenance)
            existing["linked_sources"] = sorted({item["source_key"] for item in existing["provenance"]})
            atomic_replace(path, canonical_json_bytes(existing))
        return existing

    def candidates(self) -> list[dict[str, Any]]:
        folder = self.base / "candidates"
        return [load_json(path) for path in sorted(folder.glob("evt_*.json"))] if folder.is_dir() else []

    def _queue(self, doc: dict, version: dict, record: DiscoveredRecord, outcome: str) -> dict[str, Any]:
        queue_id = "mreview_" + sha256(f"{record.official_id}\n{version.get('sha256')}".encode()).hexdigest()[:20]
        change = "REVISED" if version.get("previous_sha256") else "NEW"
        item = {
            "schema_version": "2.0.0", "queue_id": queue_id, "status": "HUMAN_REVIEW_PENDING", "doc_id": doc["doc_id"],
            "official_id": record.official_id, "source_key": record.source_key, "version": version["version"],
            "sha256": version.get("sha256"), "previous_sha256": version.get("previous_sha256"), "change": change,
            "outcome": outcome, "machine_state": machine_state(version), "review_reason": version.get("review_reason"), "title": record.title,
            "canonical_url": record.canonical_url, "stated_dates": record.stated_dates, "stages": version.get("stages"),
            "legal_effect_claimed": False,
            "note": "Discovery or a changed PDF is not an amendment, a commenced change or a changed scenario answer.",
        }
        atomic_write_new(self.base / "review_queue" / f"{queue_id}.json", canonical_json_bytes(item))
        version["queue_id"] = queue_id
        self._save_document(doc)
        return {"status": change, "outcome": outcome, "machine_state": machine_state(version), "version": version["version"], "sha256": version.get("sha256"),
                "previous_sha256": version.get("previous_sha256"), "queue_id": queue_id, "stages": version.get("stages"),
                "review_reason": version.get("review_reason"),
                "same_bytes_as_official_ids": version.get("same_bytes_as_official_ids", [])}

    def processed_documents(self, include: tuple[str, str] | None = None) -> list[dict[str, Any]]:
        """Parsed text of every processed monitored version (for the index overlay)."""
        docs = []
        for doc in self.documents():
            for version in doc["versions"]:
                ready = version["state"] == "PROCESSED" or include == (doc["official_id"], version.get("sha256"))
                normalized = sorted((self.base / "normalized").glob(f"{version.get('sha256')}.*.json")) if ready else []
                if normalized:
                    # Applied on every read, so versions processed before the gate existed are cleaned too.
                    evidence, quarantine = quarantine_document(load_json(normalized[-1]))
                    if _text_fidelity(evidence)["status"] != "READABLE":
                        continue
                    docs.append({"doc_id": doc["doc_id"], "official_id": doc["official_id"], "source_key": doc["source_key"],
                                 "version": version["version"], "sha256": version["sha256"], "record": version["record"],
                                 "normalized": evidence, "text_quality": {key: quarantine[key] for key in ("version", "withheld_lines", "by_reason")}})
        return docs

    # ---------- reviewed manual import ----------
    def manual_import(self, source_key: str, *, official_id: str, canonical_url: str, title: str,
                      payload: bytes, reviewer_id: str, reason: str) -> dict[str, Any]:
        if source_key != "egazette":
            raise ValueError("manual import is only offered for e-Gazette documents outside the daily listing")
        if not payload.startswith(b"%PDF-") or len(reason.strip()) < 10 or not reviewer_id.strip():
            raise ValueError("manual import needs a PDF, a reviewer and a reason")
        record = DiscoveredRecord(source_key, official_id, None, title, canonical_url, self.clock(), None,
                                  {"issued": None, "published": None}, None, "manual", None, len(payload),
                                  {"manual_import_by": reviewer_id})

        class _Manual:
            @staticmethod
            def download(url: str) -> bytes:
                return payload

        result = self._ingest(record, _Manual(), f"manual:{reviewer_id}")
        return {**result, "imported_by": reviewer_id, "reason": reason, "mode": "MANUAL_IMPORT"}

    # ---------- storage ----------
    def _transition(self, doc: dict, version: dict, state: str, run_id: str) -> None:
        version["state"] = state
        version["history"].append({"state": state, "at": self.clock(), "run_id": run_id})
        self._save_document(doc)

    @staticmethod
    def _done(version: dict) -> set[str]:
        return {item["state"] for item in version["history"]}

    def _load_document(self, doc_id: str) -> dict | None:
        path = self.base / "documents" / f"{doc_id}.json"
        return load_json(path) if path.is_file() else None

    def _save_document(self, doc: dict) -> None:
        atomic_replace(self.base / "documents" / f"{doc['doc_id']}.json", canonical_json_bytes(doc))

    def documents(self) -> list[dict[str, Any]]:
        folder = self.base / "documents"
        return [load_json(path) for path in sorted(folder.glob("doc_*.json"))] if folder.is_dir() else []

    def observations(self) -> list[dict[str, Any]]:
        path = self.base / "observations.v1.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []

    def _observe(self, record: DiscoveredRecord, run_id: str, digest: str | None, status: str,
                 error: str | None = None, previous_sha256: str | None = None) -> None:
        self._append("observations.v1.jsonl", {**asdict(record), "run_id": run_id, "observed_at": self.clock(),
                                               "sha256": digest, "status": status, "error": error,
                                               "previous_sha256": previous_sha256})

    def _append(self, name: str, value: dict[str, Any]) -> None:
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @contextmanager
    def _file_lock(self, name: str) -> Iterator[None]:
        self.base.mkdir(parents=True, exist_ok=True)
        with (self.base / f".{name}.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    @contextmanager
    def _locked_state(self) -> Iterator[dict[str, Any]]:
        with self._file_lock("state"):
            path = self.base / "state.v1.json"
            state = json.loads(path.read_text(encoding="utf-8"))["sources"] if path.is_file() else {}
            yield state
            atomic_replace(path, canonical_json_bytes({"schema_version": "1.0.0", "time_base": "UTC", "sources": state}))

    # ---------- health ----------
    def health(self) -> dict[str, Any]:
        path = self.base / "state.v1.json"
        state = json.loads(path.read_text(encoding="utf-8"))["sources"] if path.is_file() else {}
        now = _parse_time(self.clock())
        folder = self.base / "review_queue"
        queue = [load_json(p) for p in sorted(folder.glob("*.json"))] if folder.is_dir() else []
        latest = [doc["versions"][-1] for doc in self.documents() if doc["versions"]]
        states = [version["state"] for version in latest]
        machine = [machine_state(version) for version in latest]
        sources, alerts = [], []
        for key in sorted(set(self.connectors) | set(state)):
            entry = state.get(key, {})
            success = entry.get("last_success_at")
            lag = (now - _parse_time(success)).total_seconds() / 3600 if success else None
            eligible = entry.get("next_eligible_at")
            if eligible and now > _parse_time(eligible) + MISSED_RUN_GRACE:
                alerts.append({"source_key": key, "code": "SCHEDULER_MISSED_RUN",
                               "detail": f"eligible since {eligible} but no attempt was started"})
            if entry.get("last_attempt_at") and (lag is None or lag > STALE_AFTER_HOURS):
                alerts.append({"source_key": key, "code": "INGESTION_STALE",
                               "detail": f"last success {success or 'never'}; last status {entry.get('last_status')}"})
            sources.append({
                "source_key": key, "last_attempt_at": entry.get("last_attempt_at"), "last_success_at": success,
                "next_eligible_at": entry.get("next_eligible_at"), "last_status": entry.get("last_status"),
                "lag_hours": round(lag, 1) if lag is not None else None,
                "scheduled_ingestion_healthy": lag is not None and lag <= STALE_AFTER_HOURS,
                "freshness": "NEVER_SUCCEEDED" if lag is None else "FRESH" if lag <= STALE_AFTER_HOURS else "STALE",
                "stage": (f"RUNNING (lease held by {entry.get('lease_owner')} until {entry.get('lease_expires_at')})"
                          if entry.get("lease_expires_at") and _parse_time(entry["lease_expires_at"]) > now else "IDLE"),
                "schedule": entry.get("schedule"), "last_completed_at": entry.get("last_completed_at"),
                "last_run_counts": entry.get("last_run_counts"),
            })
        return {"sources": sources, "alerts": alerts, "review_queue_pending": sum(item["status"] == "HUMAN_REVIEW_PENDING" for item in queue),
                "document_states": {name: states.count(name) for name in sorted(set(states))},
                "machine_states": {name: machine.count(name) for name in sorted(set(machine))},
                "failed_documents": states.count("FAILED"),
                "commencement_pending_review": sum(r["status"] != "REVIEWED" for r in self.commencement_records()),
                "time_base": "UTC", "coverage_claim": "partial; see docs/sprint/s1_source_access_decision.v2.md"}


NOTIFICATIONS_VERSION = "source-notifications-v2"  # v2: records keyed by official id + content hash; latest five
SOURCE_LABELS = {"india_code": "India Code", "egazette": "e-Gazette of India"}
OFFICIAL_HOSTS = {"india_code": {"indiacode.gov.in", "www.indiacode.gov.in"}, "egazette": {"egazette.gov.in"}}
LATEST = 5
# What a record can be. Nothing in this system can yet mark an amendment as verified: the review ledger has no such action.
CATEGORIES = {
    "NEW_DOCUMENT": "Newly discovered document",
    "POSSIBLE_AMENDMENT": "Possible amendment awaiting review",
    "VERIFIED_AMENDMENT": "Verified amendment",
}
CATEGORY_NOTE = {
    "NEW_DOCUMENT": "Downloaded from a monitored source and waiting for review. Not a change to law.",
    "POSSIBLE_AMENDMENT": "Machine extraction found amendment wording; nobody has checked it yet.",
    "VERIFIED_AMENDMENT": "Would need a recorded decision by a qualified legal reviewer. The review ledger has no such action, so nothing is in this category.",
}
# Precise wording per ledger state. Nothing here says a law changed: discovery and download are not amendment or commencement.
ITEM_STATUS = {
    "AWAITING_REVIEW": "New document awaiting review",
    "REVISED_AWAITING_REVIEW": "Revised document awaiting review",
    "CANDIDATE_UNVERIFIED": "Possible amendment text found by machine extraction; not verified",
    "LISTED_NOT_DOWNLOADED": "Listed by the source; document not downloaded",
    "DOWNLOAD_FAILED": "Download or processing failed",
    "REVIEW_ACKNOWLEDGED": "Review acknowledged; not a legal decision",
    "ESCALATED_FOR_QUALIFIED_REVIEW": "Escalated for qualified legal review",
    "CHANGES_REQUESTED": "Reviewer requested changes",
    "OPINION_RECORDED": "Reviewer opinion recorded; not a legal decision",
}


def notifications(service: "MonitoringService", review_ledger: Any | None = None, limit: int = 25) -> dict[str, Any]:
    """Latest documents discovered in the monitored sources, read only from the persisted ledger (no network access).

    A record is one downloaded version: its official id plus its content hash, so a repeat check never makes a new record and a
    revised PDF does. The same bytes under several official ids are one record. Its discovery time is the first observation of
    that version. Review-ledger actions are reported as they are; no ledger state means a verified change to law."""
    health = service.health()
    now = _parse_time(service.clock())
    folder = service.base / "review_queue"
    queue = [load_json(p) for p in sorted(folder.glob("*.json"))] if folder.is_dir() else []
    documents = {doc["official_id"]: doc for doc in service.documents()}
    candidates: dict[str, list[dict[str, Any]]] = {}
    for path in sorted((service.base / "candidates").glob("*.json")) if (service.base / "candidates").is_dir() else []:
        record = load_json(path)
        for event in record.get("events") or ([record["event"]] if record.get("event") else []):
            for official_id in [record.get("official_id")] + [p.get("official_id") for p in record.get("provenance", [])]:
                if official_id:
                    candidates.setdefault(official_id, []).append(event)
    observations: dict[str, list[dict[str, Any]]] = {}
    for observation in sorted(service.observations(), key=lambda row: row["observed_at"]):
        observations.setdefault(observation["official_id"], []).append(observation)

    def describe(official_id: str, sha: str | None, item: dict[str, Any] | None) -> dict[str, Any]:
        seen = observations.get(official_id) or [{}]
        first = next((o for o in seen if sha and o.get("sha256") == sha), seen[0])
        last = seen[-1]
        source = last.get("source_key") or (item or {}).get("source_key")
        url = (item or {}).get("canonical_url") or last.get("canonical_url")
        dates = (item or {}).get("stated_dates") or last.get("stated_dates") or {}
        return {"id": official_id, "key": f"{official_id}:{sha or 'none'}", "sha256": sha, "version": (item or {}).get("version"),
                "title": " ".join(str((item or {}).get("title") or last.get("title") or "Untitled record").split()),
                "source_key": source, "source": SOURCE_LABELS.get(source, source),
                "published": dates.get("published") or dates.get("issued") or dates.get("enactment"),
                "discovered_at": first.get("observed_at"), "last_checked_at": last.get("observed_at"),
                "official_url": url if urlparse(str(url or "")).scheme == "https" and urlparse(str(url)).hostname in OFFICIAL_HOSTS.get(source, set()) else None,
                "legal_effect_claimed": False}

    records: dict[str, dict[str, Any]] = {}
    by_hash: dict[str, str] = {}
    for item in queue:
        official_id, sha = item["official_id"], item.get("sha256")
        row = describe(official_id, sha, item)
        if sha and sha in by_hash:  # the same bytes published under another official id: one record
            records[by_hash[sha]].setdefault("same_document_ids", []).append(official_id)
            continue
        code = "REVISED_AWAITING_REVIEW" if item.get("change") == "REVISED" else "AWAITING_REVIEW"
        if candidates.get(official_id):
            code = "CANDIDATE_UNVERIFIED"
        reviewed = review_ledger.current_state(item["queue_id"], item["status"]) if review_ledger else item["status"]
        code = reviewed if reviewed in ITEM_STATUS else code
        targets = sorted({str(e.get("target_act") or e.get("principal_act") or "").strip() for e in candidates.get(official_id, [])} - {""})
        version = next((v for v in (documents.get(official_id) or {}).get("versions", []) if v.get("sha256") == sha), None)
        records[row["key"]] = {**row, "status": code, "status_label": ITEM_STATUS[code], "queue_id": item["queue_id"],
                               "machine_state": machine_state(version) if version else item.get("machine_state"),
                               "category": "POSSIBLE_AMENDMENT" if candidates.get(official_id) else "NEW_DOCUMENT",
                               "candidate_events": len(candidates.get(official_id, [])), "candidate_targets": targets}
        if sha:
            by_hash[sha] = row["key"]
    for row in records.values():
        row["category_label"] = CATEGORIES[row["category"]]
    queued = {item["official_id"] for item in queue}
    failed, listed = [], []
    for official_id, seen in observations.items():
        if official_id in queued:
            continue
        doc = documents.get(official_id)
        state = doc["versions"][-1]["state"] if doc and doc.get("versions") else None
        if state == "FAILED" or (seen[-1]["status"] in {"FAILED", "CHECKSUM_MISMATCH"} and not doc):
            failed.append({**describe(official_id, None, None), "status": "DOWNLOAD_FAILED", "status_label": ITEM_STATUS["DOWNLOAD_FAILED"]})
        elif seen[-1]["status"] == "METADATA_ONLY":
            listed.append({**describe(official_id, None, None), "status": "LISTED_NOT_DOWNLOADED", "status_label": ITEM_STATUS["LISTED_NOT_DOWNLOADED"]})
    order = lambda row: (row["discovered_at"] or "", row["key"])  # noqa: E731
    items = sorted(records.values(), key=order, reverse=True)
    failed.sort(key=order, reverse=True)
    listed.sort(key=order, reverse=True)
    sources = []
    for row in health["sources"]:
        lag = row["lag_hours"]
        state = ("NEVER_SUCCEEDED" if row["last_success_at"] is None else "FAILED" if row["last_status"] not in {"OK", "PARTIAL_FAILURE"}
                 else "STALE" if not row["scheduled_ingestion_healthy"] else "OK")
        detail = ("Checked within the last 48 hours." if state == "OK"
                  else f"The last check ended with {str(row['last_status']).lower().replace('_', ' ')}; "
                       "showing items from the last successful check." if state == "FAILED"
                  else f"No successful check for {round(lag)} hours; new items may be missing." if state == "STALE"
                  else "No successful check is recorded; nothing from this source can be listed.")
        if state == "FAILED" and lag is not None and lag > STALE_AFTER_HOURS:
            detail += f" No successful check for {round(lag)} hours."
        sources.append({"source_key": row["source_key"], "source": SOURCE_LABELS.get(row["source_key"], row["source_key"]), "state": state,
                        "detail": detail, "last_success_at": row["last_success_at"], "last_attempt_at": row["last_attempt_at"],
                        "next_eligible_at": row["next_eligible_at"]})
    counts = {name: sum(row["category"] == name for row in items) for name in CATEGORIES}
    return {"version": NOTIFICATIONS_VERSION, "generated_at": now.isoformat().replace("+00:00", "Z"),
            "latest": items[:LATEST], "older": items[LATEST:limit], "items": items[:limit], "total": len(items),
            "categories": [{"category": name, "label": label, "count": counts[name], "note": CATEGORY_NOTE[name]} for name, label in CATEGORIES.items()],
            "failed": failed[:limit], "listed": listed[:limit], "listed_total": len(listed),
            "sources": sources, "scope": "Latest discovered in monitored sources (India Code and the e-Gazette), checked at most once every "
                                          "24 hours. Not a complete list of Indian amendments.",
            "note": "A discovered or downloaded document is not a confirmed change to law, and nothing listed here changes the answers "
                    "until it is reviewed and added to the corpus.", "legal_effect_claimed": False}


def pending_alerts(service: "MonitoringService") -> list[dict[str, Any]]:
    """Alerts not yet delivered, each under a stable key: a record version (official id + content hash), a failed version,
    or a source condition tied to the attempt that caused it. Read from the ledger only; nothing is fetched."""
    feed = notifications(service, limit=10**6)
    alerts = [{"key": f"record:{row['key']}", "kind": "NEW_RECORD",
               "text": f"{row['source']}: {row['title']} [{row.get('machine_state') or row['status']}] {row.get('official_url') or ''}".strip()}
              for row in feed["items"]]
    for doc in service.documents():
        version = doc["versions"][-1] if doc["versions"] else None
        # Only exhausted attempts are actionable; a FAILED version is retried automatically at its source's next run.
        if version and version["state"] == "REVIEW_REQUIRED" and version.get("error"):
            alerts.append({"key": f"failure:{doc['doc_id']}:v{version['version']}:{version['state']}", "kind": "DOCUMENT_FAILURE",
                           "text": f"{doc['source_key']} {doc['official_id']}: {version['state']} after {version.get('attempts', 0)} "
                                   f"attempt(s): {version.get('error')}"})
    path = service.base / "state.v1.json"
    state = json.loads(path.read_text(encoding="utf-8"))["sources"] if path.is_file() else {}
    for alert in service.health()["alerts"]:
        entry = state.get(alert["source_key"], {})
        anchor = entry.get("next_eligible_at") if alert["code"] == "SCHEDULER_MISSED_RUN" else entry.get("last_attempt_at")
        alerts.append({"key": f"source:{alert['source_key']}:{alert['code']}:{anchor}", "kind": alert["code"],
                       "text": f"{alert['source_key']}: {alert['code']}: {alert['detail']}"})
    sent = {row["key"] for row in _read_jsonl(service.base / ALERTS_LEDGER)}
    return [alert for alert in alerts if alert["key"] not in sent]


def deliver_alerts(service: "MonitoringService", send: Callable[[str], bool] | None) -> dict[str, Any]:
    """Send every pending alert once, as one message. A key is recorded only after delivery succeeds, so a failed or missing
    channel is retried next time and a delivered key is never sent again. On the first use, records already in the ledger
    are recorded as a baseline instead of being announced as new."""
    ledger = service.base / ALERTS_LEDGER
    pending = pending_alerts(service)
    now = service.clock()
    if not ledger.is_file():
        for alert in [a for a in pending if a["kind"] == "NEW_RECORD"]:
            service._append(ALERTS_LEDGER, {"key": alert["key"], "kind": alert["kind"], "at": now, "delivery": "BASELINE"})
        pending = [a for a in pending if a["kind"] != "NEW_RECORD"]
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.touch()
    if not pending:
        return {"status": "NOTHING_NEW", "pending": 0}
    records = [a for a in pending if a["kind"] == "NEW_RECORD"]
    problems = [a for a in pending if a["kind"] != "NEW_RECORD"]
    lines = [f"Temporal Legal Drift source monitoring ({now} UTC)"]
    if records:
        lines += [f"{len(records)} newly discovered official record(s). Machine states only: nothing here is a verified "
                  "amendment, a commencement or legal advice, and the monitored sources are not all Indian legal changes."]
        lines += [f"- {a['text']}" for a in records]
    if problems:
        lines += [f"{len(problems)} problem(s) needing attention:"] + [f"- {a['text']}" for a in problems]
    if send is None or not send("\n".join(lines) + "\n"):
        return {"status": "UNDELIVERED" if send else "NO_ALERT_CHANNEL", "pending": len(pending),
                "keys": [a["key"] for a in pending]}
    for alert in pending:
        service._append(ALERTS_LEDGER, {"key": alert["key"], "kind": alert["kind"], "at": now, "delivery": "SENT"})
    return {"status": "SENT", "pending": 0, "sent": len(pending), "new_records": len(records), "problems": len(problems)}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def _text_fidelity(document: dict[str, Any]) -> dict[str, Any]:
    """Cheap, explainable signal that routes documents to review; it does not certify text."""
    text = " ".join(str(block.get("normalized_text", "")) for block in document.get("blocks", []))
    words = re.findall(r"\S+", text)
    if len(words) < 20:
        return {"status": "UNREADABLE", "words": len(words), "reason": "little or no extractable text (scanned image?)"}
    odd = sum(bool(re.search(r"[A-Za-z]", word)) and bool(re.search(r"[^A-Za-z0-9.,;:()'\"\-–—/\[\]“”‘’]", word)) for word in words)
    ratio = odd / len(words)
    return {"status": "UNRELIABLE" if ratio > 0.08 else "READABLE", "words": len(words), "odd_token_ratio": round(ratio, 4),
            "method": "share of word tokens mixing letters with unexpected symbols; threshold 0.08"}


def _materiality_triage(event: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    from temporal_legal_drift.materiality.silver import _cue_transition_annotator

    operation, before, after = event.get("operation"), event.get("old_text"), event.get("new_text")
    if {"source_text_unreliable", "operand_contains_page_furniture", "unclear_operation"} & set(reasons):
        return {"status": "REVIEW_REQUIRED", "label": None, "reason": "unreliable or ambiguous operand"}
    if (operation == "INSERT" and after) or (operation in {"SUBSTITUTE", "REPLACE"} and before and after) or (operation == "OMIT" and before):
        result = _cue_transition_annotator({"operation": operation, "before_text": before or "", "after_text": after or ""})
        return {"status": "PROVISIONAL_RULE_OUTPUT", "label": result["label"], "method": "rule_a_cue_transition",
                "rationale": result["rationale"], "is_gold": False}
    return {"status": "INSUFFICIENT_EVIDENCE", "label": None, "reason": "operands not extracted"}
