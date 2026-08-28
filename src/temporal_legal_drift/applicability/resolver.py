"""Resolver that refuses to infer applicability from publication or recency alone."""

from __future__ import annotations

from collections import defaultdict, deque

from temporal_legal_drift.versioning.models import VersionGraph

from .models import (
    ApplicabilityDetermination,
    ApplicabilityQuery,
    TemporalFact,
    make_determination_id,
)


EFFECTIVE_FACT_TYPES = frozenset(
    {
        "commencement",
        "applicability",
        "legal_effect",
        "retrospective_effect",
        "deferred_commencement",
        "partial_commencement",
    }
)


class ApplicabilityResolver:
    def __init__(self, graph: VersionGraph, facts: tuple[TemporalFact, ...]) -> None:
        errors = graph.validate()
        if errors:
            raise ValueError("Cannot resolve against invalid version graph: " + "; ".join(errors))
        self.graph = graph
        self.facts = facts

    def resolve(self, query: ApplicabilityQuery) -> ApplicabilityDetermination:
        determination_id = make_determination_id(query)
        versions = self.graph.versions_for_lineage(query.lineage_id)
        if not versions:
            return self._unresolved(query, determination_id, "unknown_lineage")

        version_ids = {item.version_id for item in versions}
        reviewed = [
            fact
            for fact in self.facts
            if fact.version_id in version_ids and fact.review_status == "approved"
        ]
        if not reviewed:
            return self._unresolved(query, determination_id, "no_approved_temporal_evidence")
        uncertain = [fact.fact_id for fact in reviewed if fact.uncertainty]
        if uncertain:
            return self._unresolved(
                query,
                determination_id,
                "approved_temporal_evidence_retains_material_uncertainty",
                tuple(uncertain),
            )

        conditional_unknown: list[str] = []
        eligible_facts: list[TemporalFact] = []
        for fact in reviewed:
            missing = [key for key in fact.conditions if key not in query.attributes]
            if missing:
                conditional_unknown.append(f"{fact.fact_id}:missing:{','.join(sorted(missing))}")
                continue
            if any(query.attributes[key] != value for key, value in fact.conditions.items()):
                continue
            eligible_facts.append(fact)

        transitional = [fact for fact in eligible_facts if fact.fact_type == "transitional_provision"]
        if transitional:
            return self._unresolved(
                query,
                determination_id,
                "transitional_rule_requires_explicit_adjudication",
                tuple(fact.fact_id for fact in transitional),
            )
        if conditional_unknown:
            return self._unresolved(
                query,
                determination_id,
                "scenario_attributes_insufficient_for_partial_or_conditional_effect",
                (),
                tuple(conditional_unknown),
            )

        effective_by_version: dict[str, list[TemporalFact]] = defaultdict(list)
        for fact in eligible_facts:
            if fact.fact_type in EFFECTIVE_FACT_TYPES and fact.effective_date is not None:
                effective_by_version[fact.version_id].append(fact)
        if not effective_by_version:
            return self._unresolved(
                query,
                determination_id,
                "publication_or_assent_evidence_does_not_establish_applicability",
            )

        activation: dict[str, object] = {}
        supporting: dict[str, tuple[str, ...]] = {}
        for version_id, facts in effective_by_version.items():
            dates = {fact.effective_date for fact in facts}
            if len(dates) != 1:
                return self._unresolved(
                    query,
                    determination_id,
                    f"conflicting_effective_dates:{version_id}",
                    tuple(fact.fact_id for fact in facts),
                )
            activation[version_id] = next(iter(dates))
            supporting[version_id] = tuple(fact.fact_id for fact in facts)

        active = [
            version_id
            for version_id, effective_date in activation.items()
            if effective_date is not None and effective_date <= query.reference_date  # type: ignore[operator]
        ]
        if not active:
            return ApplicabilityDetermination(
                determination_id,
                query.scenario_id,
                query.reference_date.isoformat(),
                query.lineage_id,
                "not_yet_effective",
                None,
                (),
                ("Approved effective-date evidence exists only after the reference date.",),
                (),
            )
        if len(active) == 1:
            chosen = active[0]
        else:
            maximal = [
                candidate
                for candidate in active
                if all(
                    other == candidate or self._transition_reaches(other, candidate)
                    for other in active
                )
            ]
            if len(maximal) != 1:
                return self._unresolved(
                    query,
                    determination_id,
                    "multiple_active_versions_without_proven_supersession_path",
                    tuple(fact for version_id in active for fact in supporting[version_id]),
                )
            chosen = maximal[0]

        return ApplicabilityDetermination(
            determination_id,
            query.scenario_id,
            query.reference_date.isoformat(),
            query.lineage_id,
            "resolved_requires_expert_confirmation",
            chosen,
            supporting[chosen],
            (
                "Used approved commencement/applicability evidence, not document recency.",
                "Confirmed any supersession through explicit version transitions.",
            ),
            (),
        )

    def _transition_reaches(self, start: str, target: str) -> bool:
        edges: dict[str, list[str]] = defaultdict(list)
        for transition in self.graph.transitions:
            edges[transition.before_version_id].append(transition.after_version_id)
        queue = deque([start])
        visited: set[str] = set()
        while queue:
            node = queue.popleft()
            if node == target:
                return True
            if node in visited:
                continue
            visited.add(node)
            queue.extend(edges.get(node, []))
        return False

    @staticmethod
    def _unresolved(
        query: ApplicabilityQuery,
        determination_id: str,
        reason: str,
        facts: tuple[str, ...] = (),
        trace: tuple[str, ...] = (),
    ) -> ApplicabilityDetermination:
        return ApplicabilityDetermination(
            determination_id,
            query.scenario_id,
            query.reference_date.isoformat(),
            query.lineage_id,
            "unresolved_escalate",
            None,
            facts,
            trace,
            (reason,),
        )
