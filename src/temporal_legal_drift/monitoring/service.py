"""Incremental, 24-hour-gated official-source monitoring (plan.md §0.7, ADR 0008).

Discovery → bounded download → SHA-256 (and the source's MD5 where offered)
→ immutable artifact → identity/byte comparison with prior observations →
only new or revised content goes to the review queue and downstream stages.
Downstream stage outputs are cached by content hash plus stage version, so an
unchanged download only updates ``last_seen_at``. Nothing here asserts legal
effect: a publication is not commencement, and new documents never alter the
active graph, index or any frozen release automatically.
"""

from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import md5, sha256
from pathlib import Path
from typing import Any, Callable, Iterator
from uuid import uuid4

from temporal_legal_drift.acquisition.models import utc_now_iso
from temporal_legal_drift.amendment_extraction.extractor import GeneralisedAmendmentExtractor
from temporal_legal_drift.amendment_extraction.models import EXTRACTOR_VERSION
from temporal_legal_drift.jsonio import atomic_replace, atomic_write_new, canonical_json_bytes

from .indiacode import DiscoveredRecord, SourceShapeError

WINDOW = timedelta(hours=24)
LEASE = timedelta(hours=1)
ACCESS_LIMITED_SOURCES = {"egazette": "No documented machine interface; reviewed manual import only (S1 decision v1)."}
ROOT = "data/monitoring"


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class MonitoringService:
    def __init__(self, root: Path, connectors: dict[str, Any], *, clock: Callable[[], str] = utc_now_iso,
                 parser: Any | None = None) -> None:
        self.root = root.resolve()
        self.base = self.root / ROOT
        self.connectors = connectors
        self.clock = clock
        self.parser = parser

    # ---------- scheduling ----------
    def run_due(self, owner: str, *, manual_reason: str | None = None) -> list[dict[str, Any]]:
        """Attempt each connector at most once per rolling 24 h; ``manual_reason`` records an audited retry."""
        return [result for key in sorted(self.connectors) if (result := self._run_source(key, owner, manual_reason)) is not None]

    def backfill(self, source_key: str, owner: str, *, pages: int, reason: str) -> dict[str, Any]:
        """Bounded historical pages; recorded as backfill, never as the daily run, and does not move the daily window."""
        if not 1 <= pages <= 20:
            raise ValueError("backfill pages must be between 1 and 20")
        if len(reason.strip()) < 10:
            raise ValueError("backfill requires a reason")
        return self._execute(source_key, owner, mode="BACKFILL", since=None, max_pages=pages, reason=reason)

    def _run_source(self, key: str, owner: str, manual_reason: str | None) -> dict[str, Any] | None:
        now = _parse_time(self.clock())
        with self._locked_state() as state:
            entry = state.setdefault(key, {"source_key": key})
            eligible = entry.get("next_eligible_at")
            if manual_reason is None and eligible and _parse_time(eligible) > now:
                return None  # not due: at most one automatic attempt per 24 h window
            lease_until = entry.get("lease_expires_at")
            if lease_until and _parse_time(lease_until) > now and entry.get("lease_owner") != owner:
                return {"source_key": key, "status": "SKIPPED_LEASE_HELD", "lease_owner": entry["lease_owner"]}
            if manual_reason is not None and len(manual_reason.strip()) < 10:
                raise ValueError("a manual retry requires a reason")
            entry.update(lease_owner=owner, lease_expires_at=(now + LEASE).isoformat(), last_attempt_at=now.isoformat())
            if manual_reason is None:
                entry["next_eligible_at"] = (now + WINDOW).isoformat()
            since = entry.get("cursor")
        mode = "MANUAL_RETRY" if manual_reason else "SCHEDULED"
        # First run has no cursor: take one page to establish it; history is a separate backfill.
        result = self._execute(key, owner, mode=mode, since=since, max_pages=5 if since else 1, reason=manual_reason)
        with self._locked_state() as state:
            entry = state[key]
            entry.update(lease_owner=None, lease_expires_at=None, last_run_id=result["run_id"], last_status=result["status"])
            if result["status"] == "OK":
                entry["last_success_at"] = result["completed_at"]
                if result.get("cursor"):
                    entry["cursor"] = max(result["cursor"], entry.get("cursor") or "")
        return result

    # ---------- one run ----------
    def _execute(self, key: str, owner: str, *, mode: str, since: str | None, max_pages: int,
                 reason: str | None) -> dict[str, Any]:
        started = self.clock()
        run_id = f"mon_{uuid4().hex[:20]}"
        manifest: dict[str, Any] = {"schema_version": "1.0.0", "run_id": run_id, "source_key": key, "mode": mode,
                                    "owner": owner, "reason": reason, "started_at": started, "since_cursor": since,
                                    "records": [], "counts": {}, "graph_index_update": "NONE_PENDING_REVIEW"}
        connector = self.connectors[key]
        try:
            discovered = connector.discover(since, max_pages=max_pages)
            manifest["status"] = "OK"
        except SourceShapeError as error:
            discovered, manifest["status"], manifest["error"] = [], "SOURCE_SHAPE_CHANGED", str(error)
        except Exception as error:  # network outage, HTTP failure, policy refusal
            discovered, manifest["status"], manifest["error"] = [], "SOURCE_UNAVAILABLE", f"{type(error).__name__}: {error}"
        for record in discovered:
            manifest["records"].append(self._ingest(record, connector, run_id))
        statuses = [item["status"] for item in manifest["records"]]
        manifest["counts"] = {name: statuses.count(name) for name in sorted(set(statuses))}
        manifest["cursor"] = max((r.accessioned_at for r in discovered), default=None)
        if manifest["status"] == "OK" and any(s == "DOWNLOAD_FAILED" for s in statuses):
            manifest["status"] = "PARTIAL_FAILURE"
        manifest["completed_at"] = self.clock()
        atomic_write_new(self.base / "runs" / f"{run_id}.json", canonical_json_bytes(manifest))
        return manifest

    def _ingest(self, record: DiscoveredRecord, connector: Any, run_id: str) -> dict[str, Any]:
        # Only verified content is a baseline; failed or mismatched downloads never are.
        prior = [item for item in self.observations() if item["official_id"] == record.official_id
                 and item["status"] in {"NEW", "REVISED", "UNCHANGED"}]
        base = {"official_id": record.official_id, "title": record.title, "canonical_url": record.canonical_url}
        if not record.bitstream_url:
            self._observe(record, run_id, None, "NO_SINGLE_PDF_BITSTREAM")
            return {**base, "status": "REVIEW_REQUIRED", "reason": "item has no single PDF in its ORIGINAL bundle"}
        try:
            payload = connector.download(record.bitstream_url)
        except Exception as error:
            self._observe(record, run_id, None, "DOWNLOAD_FAILED", f"{type(error).__name__}: {error}")
            return {**base, "status": "DOWNLOAD_FAILED", "error": f"{type(error).__name__}: {error}"}
        digest = sha256(payload).hexdigest()
        # India Code serves a stamped rendition whose bytes differ from the stored file the
        # repository MD5 describes (S1 addendum); served bytes were byte-identical across
        # downloads, so the served SHA-256 is the integrity basis and the MD5 is recorded.
        checksum = ("REPOSITORY_MD5_VERIFIED" if record.bitstream_md5 and md5(payload).hexdigest() == record.bitstream_md5
                    else "SERVED_RENDITION_DIFFERS_FROM_REPOSITORY_MD5" if record.bitstream_md5 else "NO_REPOSITORY_CHECKSUM")
        base["repository_checksum"] = checksum
        atomic_write_new(self.root / "data/raw/monitoring/sha256" / digest[:2] / f"{digest}.pdf", payload)
        if any(item["sha256"] == digest for item in prior):
            self._observe(record, run_id, digest, "UNCHANGED")
            return {**base, "status": "UNCHANGED", "sha256": digest}  # last_seen only; no downstream work
        previous = prior[-1]["sha256"] if prior else None
        status = "REVISED" if previous else "NEW"
        self._observe(record, run_id, digest, status, previous_sha256=previous)
        stages = self._process(digest, payload, record)
        queue_id = "mreview_" + sha256(f"{record.official_id}\n{digest}".encode()).hexdigest()[:20]
        atomic_write_new(self.base / "review_queue" / f"{queue_id}.json", canonical_json_bytes({
            "schema_version": "1.0.0", "queue_id": queue_id, "status": "HUMAN_REVIEW_PENDING",
            "official_id": record.official_id, "sha256": digest, "previous_sha256": previous, "change": status,
            "title": record.title, "canonical_url": record.canonical_url, "stated_dates": record.stated_dates,
            "stages": stages, "legal_effect_claimed": False,
            "note": "Publication is not commencement; applicability remains unresolved until reviewed facts exist.",
        }))
        return {**base, "status": status, "sha256": digest, "previous_sha256": previous, "queue_id": queue_id, "stages": stages}

    def _process(self, digest: str, payload: bytes, record: DiscoveredRecord) -> dict[str, Any]:
        """Parse and extract, cached by content hash + stage version; failures stay reviewable."""
        stages: dict[str, Any] = {}
        parser_version = f"{getattr(self.parser, 'name', 'none')}-{getattr(self.parser, 'version', '0')}"
        parse_key = f"parse:{parser_version}:{digest}"
        normalized_path = self.base / "normalized" / f"{digest}.{parser_version}.json"
        if self._cached(parse_key):
            stages["parse"] = "CACHED"
        elif self.parser is None:
            stages["parse"] = "PARSER_UNAVAILABLE"
            return stages
        else:
            from temporal_legal_drift.parsing.models import ParseContext

            try:
                document = self.parser.parse(payload, ParseContext(record.official_id, digest, "application/pdf", f"{digest}.pdf"))
            except Exception as error:
                self._stage_run(parse_key, "FAILED", f"{type(error).__name__}: {error}")
                stages["parse"] = "FAILED"
                return stages
            atomic_write_new(normalized_path, canonical_json_bytes(document.to_dict()))
            self._stage_run(parse_key, "OK")
            stages["parse"] = "OK"
        extract_key = f"extract:{EXTRACTOR_VERSION}:{parser_version}:{digest}"
        if self._cached(extract_key):
            stages["extract"] = "CACHED"
            return stages
        document = json.loads(normalized_path.read_text(encoding="utf-8"))
        events, unresolved = GeneralisedAmendmentExtractor().extract(
            document, source_document=record.official_id, source_sha256=digest, amending_act=record.title)
        atomic_write_new(self.base / "candidates" / f"{digest}.{EXTRACTOR_VERSION}.json", canonical_json_bytes({
            "extractor_version": EXTRACTOR_VERSION, "official_id": record.official_id, "sha256": digest,
            "events": [item.to_dict() for item in events], "unresolved": [item.to_dict() for item in unresolved],
            "status": "machine_candidates_not_in_active_graph",
        }))
        self._stage_run(extract_key, "OK")
        stages["extract"] = {"status": "OK", "events": len(events), "unresolved": len(unresolved)}
        return stages

    # ---------- reviewed manual import (ACCESS_LIMITED sources) ----------
    def manual_import(self, source_key: str, *, official_id: str, canonical_url: str, title: str,
                      payload: bytes, reviewer_id: str, reason: str) -> dict[str, Any]:
        if source_key not in ACCESS_LIMITED_SOURCES:
            raise ValueError("manual import is only for ACCESS_LIMITED sources")
        if not payload.startswith(b"%PDF-") or len(reason.strip()) < 10 or not reviewer_id.strip():
            raise ValueError("manual import needs a PDF, a reviewer and a reason")
        record = DiscoveredRecord(source_key, official_id, None, title, canonical_url, self.clock(), None,
                                  {"issued": None, "enactment": None}, None, "manual", None, len(payload))

        class _Manual:
            @staticmethod
            def download(url: str) -> bytes:
                return payload

        result = self._ingest(record, _Manual(), f"manual:{reviewer_id}")
        return {**result, "imported_by": reviewer_id, "reason": reason, "mode": "MANUAL_IMPORT"}

    # ---------- storage ----------
    def observations(self) -> list[dict[str, Any]]:
        path = self.base / "observations.v1.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []

    def _observe(self, record: DiscoveredRecord, run_id: str, digest: str | None, status: str,
                 error: str | None = None, previous_sha256: str | None = None) -> None:
        self._append("observations.v1.jsonl", {**asdict(record), "run_id": run_id, "observed_at": self.clock(),
                                               "sha256": digest, "status": status, "error": error,
                                               "previous_sha256": previous_sha256})

    def _cached(self, key: str) -> bool:
        path = self.base / "stage_runs.v1.jsonl"
        return path.is_file() and any(
            json.loads(line).get("key") == key and json.loads(line).get("status") == "OK"
            for line in path.read_text(encoding="utf-8").splitlines() if line.strip())

    def _stage_run(self, key: str, status: str, error: str | None = None) -> None:
        self._append("stage_runs.v1.jsonl", {"key": key, "status": status, "error": error, "at": self.clock()})

    def _append(self, name: str, value: dict[str, Any]) -> None:
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @contextmanager
    def _locked_state(self) -> Iterator[dict[str, Any]]:
        self.base.mkdir(parents=True, exist_ok=True)
        with (self.base / ".state.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)  # cross-process: one worker updates state at a time
            path = self.base / "state.v1.json"
            state = json.loads(path.read_text(encoding="utf-8"))["sources"] if path.is_file() else {}
            yield state
            atomic_replace(path, canonical_json_bytes({"schema_version": "1.0.0", "time_base": "UTC", "sources": state}))

    # ---------- health ----------
    def health(self) -> dict[str, Any]:
        path = self.base / "state.v1.json"
        state = json.loads(path.read_text(encoding="utf-8"))["sources"] if path.is_file() else {}
        now = _parse_time(self.clock())
        queue = [json.loads(p.read_text()) for p in sorted((self.base / "review_queue").glob("*.json"))] if (self.base / "review_queue").is_dir() else []
        sources = []
        for key in sorted(set(self.connectors) | set(state)):
            entry = state.get(key, {})
            success = entry.get("last_success_at")
            lag = (now - _parse_time(success)).total_seconds() / 3600 if success else None
            sources.append({
                "source_key": key, "last_attempt_at": entry.get("last_attempt_at"), "last_success_at": success,
                "next_eligible_at": entry.get("next_eligible_at"), "last_status": entry.get("last_status"),
                "lag_hours": round(lag, 1) if lag is not None else None,
                "scheduled_ingestion_healthy": lag is not None and lag <= 48,
            })
        sources += [{"source_key": key, "status": "ACCESS_LIMITED", "detail": detail} for key, detail in ACCESS_LIMITED_SOURCES.items()]
        return {"sources": sources, "review_queue_pending": sum(item["status"] == "HUMAN_REVIEW_PENDING" for item in queue),
                "failed_observations": sum(o["status"] in {"DOWNLOAD_FAILED", "CHECKSUM_MISMATCH"} for o in self.observations()),
                "time_base": "UTC", "coverage_claim": "partial; see docs/sprint/s1_source_access_decision.v1.md"}
