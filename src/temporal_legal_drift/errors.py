"""Domain exceptions used by the Phase 0-2 foundation."""


class TemporalLegalDriftError(Exception):
    """Base class for expected project errors."""


class ContractValidationError(TemporalLegalDriftError):
    """Raised when the research contract violates a structural invariant."""


class SourcePolicyError(TemporalLegalDriftError):
    """Raised when a source request violates the approved acquisition policy."""


class AcquisitionError(TemporalLegalDriftError):
    """Raised when a source cannot be acquired safely."""


class IntegrityError(TemporalLegalDriftError):
    """Raised when bytes or metadata fail an integrity check."""


class ParseError(TemporalLegalDriftError):
    """Raised when an artifact cannot be parsed without silent data loss."""


class UnsupportedFormatError(ParseError):
    """Raised when no approved parser is available for the artifact format."""

