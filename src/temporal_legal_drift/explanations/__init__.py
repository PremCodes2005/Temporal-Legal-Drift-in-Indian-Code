"""Phase 10 evidence-grounded explanation evaluation."""

from .evaluator import (
    build_explanation_evaluation_plan,
    evaluate_explanation_support,
    write_explanation_plan_and_lock,
)

__all__ = [
    "build_explanation_evaluation_plan",
    "evaluate_explanation_support",
    "write_explanation_plan_and_lock",
]
