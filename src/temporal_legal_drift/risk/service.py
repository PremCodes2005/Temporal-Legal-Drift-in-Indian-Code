"""Read-only risk API backed by versioned server-owned models and evidence."""

from hashlib import sha256
from pathlib import Path
from typing import Any

from temporal_legal_drift.jsonio import load_json
from .engine import evaluate_risk
from .models import ComplianceScenario, ObligationRule


class RiskService:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _registry(self) -> dict[str, Any]:
        value = load_json(self.root / "data/risk/obligation_registry.v1.json")
        for name, expected in value["input_sha256"].items():
            path = (self.root / name).resolve()
            if not path.is_relative_to(self.root) or not path.is_file() or sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError(f"Risk registry input changed or missing: {name}; rebuild a versioned registry")
        checkpoint = load_json(self.root / "reports/risk/checkpoint.v1.json")
        for name in ("data/risk/obligation_registry.v1.json", "data/risk/compliance_scenarios.v1.json"):
            if sha256((self.root / name).read_bytes()).hexdigest() != checkpoint["artifacts"].get(name):
                raise ValueError(f"Risk artifact checksum mismatch: {name}")
        return value

    def assess(self, value: dict[str, Any]) -> dict[str, Any]:
        scenario = ComplianceScenario.from_dict(value)
        registry = self._registry()
        rules = [ObligationRule.from_dict(row) for row in registry["rules"]]
        return evaluate_risk(scenario, rules, registry["evidence"]).to_dict()

    def catalog(self) -> dict[str, Any]:
        registry = self._registry()
        benchmark = load_json(self.root / "data/risk/compliance_scenarios.v1.json")
        return {"scenarios": benchmark["scenarios"], "conditional_demonstrations": benchmark["conditional_demonstrations"],
                "supported_rules": [{k: r[k] for k in ("rule_id", "provision", "provision_version", "reference_dates", "rationale")} for r in registry["rules"]],
                "risk_levels": {"High": "Severe modelled consequence requiring immediate review", "Medium": "Material operational consequence requiring review", "Low": "Limited consequence or approaching deadline", "None": "No adverse consequence detected under this rule"},
                "unknown_risk": "null: insufficient evidence; never interpreted as None/zero risk",
                "expert_validation": "NOT_PERFORMED", "drift_used_in_risk": False}
