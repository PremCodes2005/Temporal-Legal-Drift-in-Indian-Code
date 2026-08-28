"""Evidence-constrained temporal applicability resolution."""

from .cross_validation import validate_cross_source_consistency, write_cross_validation_and_lock
from .models import ApplicabilityDetermination, ApplicabilityQuery, TemporalFact
from .resolver import ApplicabilityResolver

__all__ = [
    "ApplicabilityDetermination",
    "ApplicabilityQuery",
    "ApplicabilityResolver",
    "TemporalFact",
    "validate_cross_source_consistency",
    "write_cross_validation_and_lock",
]
