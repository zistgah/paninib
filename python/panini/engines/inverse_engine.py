# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Inverse-resolution strategy engine. Synthetic fixtures only."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..artifact_util import artifact_digest
from ..inverse import InverseResolution, InverseStrategyProvider, NullInverseStrategyProvider, evaluate_inverse


@dataclass
class InverseCandidate:
    strategy: str
    basis: str
    evidence: List[str]
    assumptions: List[str]
    candidate_realization: Dict[str, Any]
    validation_state: str
    inverse: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {"strategy": self.strategy, "basis": self.basis, "evidence": list(self.evidence), "assumptions": list(self.assumptions), "candidate_realization": dict(self.candidate_realization), "validation_state": self.validation_state, "inverse": dict(self.inverse)}
        payload["digest"] = artifact_digest(payload)
        return payload


class FixtureInverseStrategyProvider:
    def available(self) -> bool:
        return True

    def licenses(self, record_attrs: Dict[str, Any], wanted_direction: str) -> bool:
        return bool(record_attrs.get("fixture_inverse_ok")) and wanted_direction == "lof"

    def propose_strategy(self, record_attrs: Dict[str, Any], constraint: Any) -> Optional[InverseResolution]:
        if not self.licenses(record_attrs, str(record_attrs.get("wanted_direction") or "lof")):
            return None
        cid = constraint.get("constraint_id") if isinstance(constraint, dict) else getattr(constraint, "constraint_id", "c")
        return InverseResolution(constraint_id=str(cid), association_class="CAUSALLY_SUPPORTED", direction="gof", wanted_direction="lof", licenses_inverse=True, evidence_status="curated", validation_status="NOT_VALIDATED", status="LICENSED", strategy_id="fixture_invert_direction", strategy_provider="panini.inverse.fixture", notes="synthetic fixture strategy; not a knockout claim", candidate_hypotheses=["delete_demo_prefix"])

    def provenance(self) -> Dict[str, Any]:
        return {"provider": "panini.inverse.fixture", "available": True, "scientific_model": False}


class InverseResolutionEngine:
    def __init__(self, provider: Optional[InverseStrategyProvider] = None) -> None:
        self.provider = provider or NullInverseStrategyProvider()

    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "InverseResolutionEngine", "class": "ENGINE", "provider_available": bool(self.provider.available()), "scientific_model": False}

    def resolve(self, *, association_record: Dict[str, Any], causal_evidence: List[str], desired_direction: str, constraint_id: str = "c_inv") -> InverseCandidate:
        rec = dict(association_record)
        rec["wanted_direction"] = desired_direction
        inv = evaluate_inverse(constraint_id, rec, desired_direction, provider=self.provider)
        licensed = inv.status == "LICENSED"
        realization: Dict[str, Any] = {}
        strategy = inv.strategy_id or "none"
        if licensed:
            realization = {"assembly": rec.get("assembly") or "demo-v1", "reference": rec.get("reference") or "chrDemo", "edits": rec.get("edits") or [{"operation": "DELETE", "start": 0, "end": 2, "replacement": ""}]}
        else:
            strategy = "blocked"
        return InverseCandidate(strategy=strategy, basis=str(rec.get("association_class") or inv.association_class), evidence=list(causal_evidence), assumptions=["synthetic fixture" if licensed else "inverse not licensed"], candidate_realization=realization, validation_state="NOT_VALIDATED", inverse=inv.to_dict())
