# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Explicit inverse-resolution contract.

Association is not inverse causality. A future causal-inference provider
may supply a strategy without modifying compiler core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .artifact_util import artifact_digest


ASSOCIATION_STRENGTH = (
    "ASSOCIATED",
    "CORRELATED",
    "MECHANISTICALLY_SUPPORTED",
    "CAUSAL",
    "CAUSALLY_SUPPORTED",
    "INVERSE_CAUSAL",
    "STANDARD_PART",
    "USER_ASSERTED",
    "MODEL_DERIVED",
)

INVERSE_STATUS = (
    "NOT_APPLICABLE",
    "LICENSED",
    "NOT_LICENSED",
    "STRATEGY_UNAVAILABLE",
    "APPLIED",
)


@dataclass
class InverseResolution:
    constraint_id: str
    association_class: str
    direction: str
    wanted_direction: str
    licenses_inverse: bool
    evidence_status: str
    validation_status: str
    status: str = "NOT_LICENSED"
    strategy_id: Optional[str] = None
    strategy_provider: Optional[str] = None
    notes: str = ""
    candidate_hypotheses: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "constraint_id": self.constraint_id,
            "association_class": self.association_class,
            "direction": self.direction,
            "wanted_direction": self.wanted_direction,
            "licenses_inverse": self.licenses_inverse,
            "evidence_status": self.evidence_status,
            "validation_status": self.validation_status,
            "status": self.status,
            "strategy_id": self.strategy_id,
            "strategy_provider": self.strategy_provider,
            "notes": self.notes,
            "candidate_hypotheses": list(self.candidate_hypotheses),
        }
        payload["digest"] = artifact_digest(payload)
        return payload


class InverseStrategyProvider(Protocol):
    def available(self) -> bool: ...
    def licenses(self, record_attrs: Dict[str, Any], wanted_direction: str) -> bool: ...
    def propose_strategy(self, record_attrs: Dict[str, Any], constraint: Any) -> Optional[InverseResolution]: ...
    def provenance(self) -> Dict[str, Any]: ...


class NullInverseStrategyProvider:
    def available(self) -> bool:
        return False

    def licenses(self, record_attrs: Dict[str, Any], wanted_direction: str) -> bool:
        return bool(record_attrs.get("licenses_inverse", False))

    def propose_strategy(self, record_attrs: Dict[str, Any], constraint: Any) -> Optional[InverseResolution]:
        return None

    def provenance(self) -> Dict[str, Any]:
        return {"provider": "panini.inverse.null", "available": False}


def evaluate_inverse(
    constraint_id: str,
    attrs: Dict[str, Any],
    wanted_direction: str,
    *,
    provider: Optional[InverseStrategyProvider] = None,
) -> InverseResolution:
    provider = provider or NullInverseStrategyProvider()
    direction = str(attrs.get("direction", "")).lower()
    wanted = (wanted_direction or "").lower()
    association = str(attrs.get("association_class", "")).upper() or "ASSOCIATED"
    licenses = bool(attrs.get("licenses_inverse", False)) or provider.licenses(attrs, wanted)
    evidence_status = str(attrs.get("evidence_status", attrs.get("validation_status", "NOT_EVALUATED")))
    validation_status = str(attrs.get("validation_status", "NOT_VALIDATED"))

    if association in {"ASSOCIATED", "CORRELATED"}:
        status = "NOT_LICENSED"
        notes = "association/correlation does not license inverse causal realization"
    elif wanted and direction and wanted != direction and not licenses:
        status = "NOT_LICENSED"
        notes = f"record direction={direction} does not license wanted={wanted}"
    elif wanted and direction and wanted != direction and licenses:
        status = "LICENSED"
        notes = "inverse licensed by record or strategy provider"
    else:
        status = "NOT_APPLICABLE"
        notes = "no inverse requested or directions already match"

    result = InverseResolution(
        constraint_id=constraint_id,
        association_class=association if association in ASSOCIATION_STRENGTH else "ASSOCIATED",
        direction=direction,
        wanted_direction=wanted,
        licenses_inverse=licenses,
        evidence_status=evidence_status,
        validation_status=validation_status,
        status=status,
        strategy_id=None if not provider.available() else "external",
        strategy_provider=provider.provenance().get("provider"),
        notes=notes,
    )
    extra = provider.propose_strategy(attrs, {"constraint_id": constraint_id})
    if extra is not None and extra.status == "LICENSED":
        return extra
    return result
