"""Append-only review ledger for case runs.

Each entry records reviewer identity and role, timestamp, prior and new state,
and a mandatory reason, and is chained to the previous entry by SHA-256 so any
edit or deletion is detectable. No action produces a legally approved state:
without a registered qualified reviewer, every entry is engineering review.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from temporal_legal_drift.jsonio import canonical_json_bytes, load_json

LEDGER = "data/reviews/ledger.v1.jsonl"
REGISTRY = "configs/review/reviewers.v1.json"
ACTIONS = {
    "ACKNOWLEDGE": "REVIEW_ACKNOWLEDGED",
    "REQUEST_CHANGES": "CHANGES_REQUESTED",
    "ESCALATE": "ESCALATED_FOR_QUALIFIED_REVIEW",
    "RECORD_OPINION": "OPINION_RECORDED",
}
GENESIS = "0" * 64
_LOCK = threading.Lock()


class ReviewRejected(ValueError):
    pass


class ReviewLedger:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.path = self.root / LEDGER

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def verify(self) -> list[str]:
        errors, previous = [], GENESIS
        for index, entry in enumerate(self.entries()):
            body = {key: value for key, value in entry.items() if key != "entry_sha256"}
            if entry.get("previous_entry_sha256") != previous or entry.get("sequence") != index:
                errors.append(f"entry {index} breaks the chain")
            if sha256(canonical_json_bytes(body)).hexdigest() != entry.get("entry_sha256"):
                errors.append(f"entry {index} content was altered")
            previous = str(entry.get("entry_sha256"))
        return errors

    def current_state(self, subject_id: str, initial_state: str) -> str:
        state = initial_state
        for entry in self.entries():
            if entry["subject_id"] == subject_id:
                state = entry["new_state"]
        return state

    def history(self, subject_id: str) -> list[dict[str, Any]]:
        return [entry for entry in self.entries() if entry["subject_id"] == subject_id]

    def record(self, *, subject_id: str, initial_state: str, action: str, reviewer_id: str,
               reason: str, expected_prior_state: str) -> dict[str, Any]:
        reviewers = load_json(self.root / REGISTRY)["reviewers"]
        if reviewer_id not in reviewers:
            raise ReviewRejected("unknown reviewer; reviewers must be registered in configs/review/reviewers.v1.json")
        if action not in ACTIONS:
            raise ReviewRejected(f"action must be one of {sorted(ACTIONS)}")
        reason = " ".join(str(reason or "").split())
        if len(reason) < 10 or len(reason) > 2000:
            raise ReviewRejected("a reason of 10-2000 characters is required")
        with _LOCK:
            errors = self.verify()
            if errors:
                raise ReviewRejected("ledger integrity check failed: " + "; ".join(errors))
            prior = self.current_state(subject_id, initial_state)
            if prior != expected_prior_state:
                raise ReviewRejected(f"state changed to {prior}; reload before reviewing")
            entries = self.entries()
            reviewer = reviewers[reviewer_id]
            body = {
                "schema_version": "1.0.0",
                "sequence": len(entries),
                "subject_type": "run",
                "subject_id": subject_id,
                "action": action,
                "prior_state": prior,
                "new_state": ACTIONS[action],
                "reviewer_id": reviewer_id,
                "reviewer_role": reviewer["role"],
                "qualified_legal_reviewer": bool(reviewer["qualified_legal_reviewer"]),
                "reason": reason,
                "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "legal_validation": "UNVERIFIED",
                "previous_entry_sha256": entries[-1]["entry_sha256"] if entries else GENESIS,
            }
            entry = {**body, "entry_sha256": sha256(canonical_json_bytes(body)).hexdigest()}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return entry
