"""Structural validation for the draft Phase 0 research contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ContractValidationError
from .jsonio import load_json


EXPECTED_TITLE = "Temporal Legal Drift in the Indian Code"
EXPECTED_LEVELS = ["High", "Medium", "Low", "None"]
EXPECTED_RQS = {"RQ1", "RQ2", "RQ3", "RQ4"}


@dataclass(frozen=True)
class ContractValidationResult:
    structurally_valid: bool
    gate_passed: bool
    errors: tuple[str, ...]
    blockers: tuple[str, ...]


def validate_contract(contract: dict[str, Any]) -> ContractValidationResult:
    errors: list[str] = []

    if contract.get("project_title") != EXPECTED_TITLE:
        errors.append(f"project_title must be {EXPECTED_TITLE!r}")

    research_questions = contract.get("research_questions")
    if not isinstance(research_questions, dict) or set(research_questions) != EXPECTED_RQS:
        errors.append("research_questions must contain exactly RQ1, RQ2, RQ3, and RQ4")

    materiality = contract.get("materiality")
    if not isinstance(materiality, dict):
        errors.append("materiality must be an object")
    else:
        if materiality.get("role") != "intermediate_component":
            errors.append("materiality.role must be intermediate_component")
        if materiality.get("levels") != EXPECTED_LEVELS:
            errors.append(f"materiality.levels must be {EXPECTED_LEVELS}")
        if materiality.get("compliance_consequence_is_separate") is not True:
            errors.append("compliance consequence must remain separate from materiality")

    corpus = contract.get("corpus")
    if not isinstance(corpus, dict) or corpus.get("jurisdiction") != "India":
        errors.append("corpus.jurisdiction must be India")
    if isinstance(corpus, dict) and "ecfr" in str(corpus.get("primary_source_family", "")).lower():
        errors.append("eCFR cannot be the active primary source family")

    optional_agent = contract.get("optional_agent")
    if not isinstance(optional_agent, dict) or optional_agent.get("is_core_completion_requirement") is not False:
        errors.append("the optional agent must not be a core completion requirement")

    gate = contract.get("gate")
    if not isinstance(gate, dict):
        errors.append("gate must be an object")
        gate_passed = False
        blockers: tuple[str, ...] = ()
    else:
        gate_passed = gate.get("passed") is True
        raw_blockers = gate.get("blockers", [])
        blockers = tuple(str(item) for item in raw_blockers) if isinstance(raw_blockers, list) else ()
        if gate_passed and blockers:
            errors.append("a passed Phase 0 gate cannot retain blockers")

    return ContractValidationResult(not errors, gate_passed, tuple(errors), blockers)


def validate_contract_file(path: Path) -> ContractValidationResult:
    return validate_contract(load_json(path))


def require_structurally_valid_contract(path: Path) -> ContractValidationResult:
    result = validate_contract_file(path)
    if not result.structurally_valid:
        raise ContractValidationError("; ".join(result.errors))
    return result

