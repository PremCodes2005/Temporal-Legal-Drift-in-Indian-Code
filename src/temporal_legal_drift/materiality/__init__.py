"""Phase 5 amendment representation and annotation-workload support."""

from .annotation import (
    build_materiality_round,
    compute_annotation_agreement,
    freeze_materiality_gold,
    write_materiality_round,
)
from .builder import build_annotation_workload, write_annotation_workload_and_lock
from .classifier import ExperimentalMaterialityModel, evaluate_materiality_gold
from .silver import (
    build_materiality_silver,
    freeze_materiality_silver,
    search_potential_none_cases,
    write_materiality_silver,
)
from .llm_assessment import (
    AssessmentValidationError,
    assess_materiality_with_llm,
    build_disagreement_report,
    build_materiality_ensemble,
    render_none_coverage_report,
    validate_llm_assessment,
    write_ensemble,
    write_llm_assessments,
)
from .audit import build_disagreement_audit_v2, render_disagreement_audit_v2

__all__ = [
    "build_annotation_workload",
    "write_annotation_workload_and_lock",
    "build_materiality_round",
    "compute_annotation_agreement",
    "freeze_materiality_gold",
    "write_materiality_round",
    "ExperimentalMaterialityModel",
    "evaluate_materiality_gold",
    "build_materiality_silver",
    "freeze_materiality_silver",
    "search_potential_none_cases",
    "write_materiality_silver",
    "AssessmentValidationError",
    "assess_materiality_with_llm",
    "build_disagreement_report",
    "build_materiality_ensemble",
    "render_none_coverage_report",
    "validate_llm_assessment",
    "write_ensemble",
    "write_llm_assessments",
    "build_disagreement_audit_v2",
    "render_disagreement_audit_v2",
]
