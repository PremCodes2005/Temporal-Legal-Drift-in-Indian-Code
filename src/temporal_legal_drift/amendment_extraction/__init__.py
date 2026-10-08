"""Generalised, evidence-bound legal amendment extraction."""

from .extractor import GeneralisedAmendmentExtractor
from .models import AmendmentEvent, SilverAmendmentLabel, UnresolvedAmendment
from .pipeline import AmendmentExtractionPipeline
from .silver import build_silver_label, silver_metrics

__all__ = [
    "AmendmentEvent",
    "AmendmentExtractionPipeline",
    "GeneralisedAmendmentExtractor",
    "SilverAmendmentLabel",
    "UnresolvedAmendment",
    "build_silver_label",
    "silver_metrics",
]
