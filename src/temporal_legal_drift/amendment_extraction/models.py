"""Phase 2 amendment-event and unresolved-record contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass


AMENDMENT_OPERATIONS = frozenset({
    "INSERT", "SUBSTITUTE", "OMIT", "REPEAL", "RENUMBER", "REPLACE", "MODIFY", "UNKNOWN",
})
UNRESOLVED_REASONS = frozenset({
    "target_not_found",
    "ambiguous_section",
    "unclear_operation",
    "missing_old_text",
    "missing_new_text",
    "commencement_unclear",
    "parsing_failure",
})


@dataclass(frozen=True)
class AmendmentEvent:
    amendment_id: str
    amending_act: str
    principal_act: str | None
    target_provision: str | None
    operation: str
    old_text: str | None
    new_text: str | None
    effective_date: str | None
    assent_date: str | None
    publication_date: str | None
    source_document: str
    source_page: int | None
    source_line: int | None
    source_sha256: str
    evidence_text: str
    confidence: float
    review_status: str = "HUMAN_REVIEW_PENDING"
    extraction_version: str = "generalised-amendment-extractor-v1"

    def __post_init__(self) -> None:
        if self.operation not in AMENDMENT_OPERATIONS:
            raise ValueError(f"unsupported amendment operation: {self.operation}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not self.evidence_text or len(self.source_sha256) != 64:
            raise ValueError("every amendment event requires hashed source evidence")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class UnresolvedAmendment:
    unresolved_id: str
    source_document: str
    reason_code: str
    evidence_text: str
    source_page: int | None
    source_line: int | None
    amendment_id: str | None
    detail: str
    review_status: str = "HUMAN_REVIEW_REQUIRED"

    def __post_init__(self) -> None:
        if self.reason_code not in UNRESOLVED_REASONS:
            raise ValueError(f"unsupported unresolved reason: {self.reason_code}")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SilverAmendmentLabel:
    """Automatically accepted fields with explicit abstention and evidence checks.

    Silver labels are reproducible weak-supervision outputs.  They are deliberately
    not represented as human-reviewed legal ground truth.
    """

    label_id: str
    amendment_id: str
    source_document: str
    principal_act: str | None
    target_provision: str | None
    operation: str | None
    old_text: str | None
    new_text: str | None
    effective_date: str | None
    field_status: dict[str, str]
    validator_checks: dict[str, bool]
    agreement_score: float
    confidence_tier: str
    label_status: str
    abstention_reasons: tuple[str, ...]
    evidence_text: str
    source_sha256: str
    labelling_version: str = "amendment-silver-labeller-v1"

    def __post_init__(self) -> None:
        if self.operation is not None and self.operation not in AMENDMENT_OPERATIONS:
            raise ValueError(f"unsupported silver-label operation: {self.operation}")
        if not 0.0 <= self.agreement_score <= 1.0:
            raise ValueError("agreement_score must be between 0 and 1")
        if self.confidence_tier not in {"HIGH", "MEDIUM", "LOW", "ABSTAIN"}:
            raise ValueError(f"unsupported confidence tier: {self.confidence_tier}")
        if self.label_status not in {"AUTO_ACCEPTED", "ABSTAIN"}:
            raise ValueError(f"unsupported label status: {self.label_status}")
        if len(self.source_sha256) != 64 or not self.evidence_text:
            raise ValueError("silver labels require hashed source evidence")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
