"""Deterministic engineering self-check without claiming an Indian-law gold label."""

from __future__ import annotations

from datetime import date
from hashlib import sha256

from temporal_legal_drift.versioning.models import (
    AmendmentEvent,
    EvidenceReference,
    LegalInstrument,
    ProvisionLineage,
    ProvisionVersion,
    VersionGraph,
    VersionTransition,
)

from .models import ApplicabilityQuery, TemporalFact
from .resolver import ApplicabilityResolver


def run_resolver_self_check() -> bool:
    evidence = EvidenceReference("src_fixture", "0" * 64, "doc_fixture", "blk_fixture", "fixture:1", "1" * 64)
    instrument = LegalInstrument("ins_fixture", "fixture", "fixture", "fixture", "Fixture", "src_fixture")
    lineage = ProvisionLineage("lin_fixture", "ins_fixture", "section:1", "1", "Fixture")
    before_text = "1. Fixture.—Before."
    after_text = "1. Fixture.—After."
    before = ProvisionVersion(
        "ver_before", "lin_fixture", "before", before_text, sha256(before_text.encode()).hexdigest(), evidence
    )
    after = ProvisionVersion(
        "ver_after", "lin_fixture", "after", after_text, sha256(after_text.encode()).hexdigest(), evidence
    )
    event = AmendmentEvent("amd_fixture", "ins_fixture", "lin_fixture", "section:1", "substitution", evidence, "fixture")
    transition = VersionTransition("trn_fixture", "ver_before", "ver_after", "amd_fixture", "substitution", evidence)
    graph = VersionGraph((instrument,), (lineage,), (before, after), (event,), (transition,))
    facts = (
        TemporalFact("tmp_before", "commencement", "ver_before", "2020-01-01", date(2020, 1, 1), "src_fixture", "fixture:date:1", "approved"),
        TemporalFact("tmp_after", "commencement", "ver_after", "2021-01-01", date(2021, 1, 1), "src_fixture", "fixture:date:2", "approved"),
    )
    resolver = ApplicabilityResolver(graph, facts)
    old = resolver.resolve(ApplicabilityQuery("scenario_old", "lin_fixture", date(2020, 6, 1)))
    new = resolver.resolve(ApplicabilityQuery("scenario_new", "lin_fixture", date(2021, 6, 1)))
    no_context = ApplicabilityResolver(graph, ()).resolve(
        ApplicabilityQuery("scenario_none", "lin_fixture", date(2021, 6, 1))
    )
    return (
        old.governing_version_id == "ver_before"
        and new.governing_version_id == "ver_after"
        and no_context.status == "unresolved_escalate"
    )
