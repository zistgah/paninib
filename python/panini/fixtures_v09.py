# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Synthetic fixtures for v0.9 engines. Not a biological corpus."""

from __future__ import annotations

from typing import Any, Dict

from .engines.biochemical import fixture_abc
from .engines.inverse_engine import FixtureInverseStrategyProvider, InverseResolutionEngine
from .knowledge import KnowledgeRecord, get_knowledge_registry


def biochemical_chain() -> Dict[str, Any]:
    return {"system": fixture_abc(k1=1.0, k2=0.5, a0=1.0).to_dict(), "note": "A→B→C mass-action fixture"}


def inverse_fixture_record() -> KnowledgeRecord:
    rec = KnowledgeRecord(
        canonical_id="realize:synthetic:fixture_invert", namespace="fixture", name="fixture_invert",
        kind="RealizationMapping", source="session", provenance="DESIGN", evidence_status="curated",
        attributes={"organism": "synthetic", "intent_verb": "establish", "intent_name": "fixture_invert", "association_class": "CAUSALLY_SUPPORTED", "causal_basis": "EVIDENCE_BACKED", "validation_status": "NOT_VALIDATED", "direction": "gof", "licenses_inverse": False, "fixture_inverse_ok": True, "wanted_direction": "lof", "assembly": "demo-v1", "reference": "chrDemo", "edits": [{"operation": "DELETE", "start": 0, "end": 2, "replacement": ""}]},
    )
    get_knowledge_registry().add_record(rec)
    return rec


def run_inverse_fixture() -> Dict[str, Any]:
    rec = inverse_fixture_record()
    engine = InverseResolutionEngine(FixtureInverseStrategyProvider())
    return engine.resolve(association_record=rec.attributes, causal_evidence=["fixture"], desired_direction="lof", constraint_id="c_inv_fix").to_dict()
