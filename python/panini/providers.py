# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Generative model provider contract (completes the v0.7 interface).

A provider may be unavailable. Unavailability is a typed state, not an
invitation to invent a sequence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .artifact_util import artifact_digest, provenance_block, utc_now
from .version import COMPILER_VERSION


CANDIDATE_STATUS = ("CANDIDATE", "SUPPORTED", "REJECTED", "UNAVAILABLE")
CANDIDATE_VALIDATION = (
    "NOT_VALIDATED",
    "MODEL_DERIVED",
    "NOT_EVALUATED",
    "REJECTED",
    "INCONCLUSIVE",
)


@dataclass
class ModelCandidate:
    candidate_id: str
    constraint_id: str
    provider: str
    model_id: str
    model_version: str
    proposal: Dict[str, Any]
    provenance: Dict[str, Any] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    confidence: float = 0.0
    status: str = "CANDIDATE"
    validation_status: str = "NOT_VALIDATED"

    def __post_init__(self) -> None:
        if self.status not in CANDIDATE_STATUS:
            raise ValueError(f"unknown candidate status {self.status}")
        if self.validation_status not in CANDIDATE_VALIDATION:
            raise ValueError(f"unknown validation_status {self.validation_status}")
        if self.validation_status in {"VERIFIED", "EXPERIMENTALLY_VALIDATED"}:
            raise ValueError("a model candidate must not silently become VERIFIED")

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "candidate_id": self.candidate_id,
            "constraint_id": self.constraint_id,
            "provider": self.provider,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "proposal": self.proposal,
            "provenance": self.provenance,
            "evidence": list(self.evidence),
            "assumptions": list(self.assumptions),
            "confidence": self.confidence,
            "status": self.status,
            "validation_status": self.validation_status,
        }
        payload["digest"] = artifact_digest(payload)
        return payload


class GenerativeModelProvider(Protocol):
    def available(self) -> bool: ...
    def capabilities(self) -> Dict[str, Any]: ...
    def propose(self, constraint: Any) -> Optional[ModelCandidate]: ...
    def provenance(self) -> Dict[str, Any]: ...
    def version(self) -> str: ...
    def validate_candidate(self, candidate: ModelCandidate) -> ModelCandidate: ...


class UnavailableGenerativeProvider:
    """Default provider. Present as a contract, absent as a scientific source."""

    def available(self) -> bool:
        return False

    def capabilities(self) -> Dict[str, Any]:
        return {
            "available": False,
            "can_propose": False,
            "can_validate": False,
            "domains": [],
            "note": "no generative biological foundation model is bound",
        }

    def propose(self, constraint: Any) -> Optional[ModelCandidate]:
        return None

    def provenance(self) -> Dict[str, Any]:
        return {
            "provider": "panini.generative.unavailable",
            "status": "UNAVAILABLE",
            "compiler_version": COMPILER_VERSION,
        }

    def version(self) -> str:
        return "0.0.0-unavailable"

    def validate_candidate(self, candidate: ModelCandidate) -> ModelCandidate:
        candidate.status = "UNAVAILABLE"
        candidate.validation_status = "NOT_VALIDATED"
        return candidate


class DeterministicMockGenerativeProvider:
    """Fixture provider. Deterministic, not a biological foundation model."""

    def __init__(
        self,
        *,
        name: str = "panini.generative.mock",
        model_id: str = "mock-cassettes",
        model_version: str = "0.8.0-fixture",
        proposals: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        self._name = name
        self._model_id = model_id
        self._model_version = model_version
        self._proposals = proposals or {}

    def available(self) -> bool:
        return True

    def capabilities(self) -> Dict[str, Any]:
        return {
            "available": True,
            "can_propose": True,
            "can_validate": True,
            "domains": sorted(self._proposals),
            "scientific": False,
            "note": "TEST / NON-BIOLOGICAL / FIXTURE PROVIDER",
        }

    def propose(self, constraint: Any) -> Optional[ModelCandidate]:
        key = getattr(constraint, "intent_name", None) or (constraint.get("intent_name") if isinstance(constraint, dict) else None)
        cid = getattr(constraint, "constraint_id", None) or (constraint.get("constraint_id") if isinstance(constraint, dict) else "unknown")
        raw = self._proposals.get(str(key))
        if raw is None:
            return ModelCandidate(
                candidate_id=f"cand_{cid}_unavailable",
                constraint_id=str(cid),
                provider=self._name,
                model_id=self._model_id,
                model_version=self._model_version,
                proposal={},
                provenance=self.provenance(),
                assumptions=["no fixture proposal registered for this constraint"],
                confidence=0.0,
                status="UNAVAILABLE",
                validation_status="NOT_VALIDATED",
            )
        return ModelCandidate(
            candidate_id=f"cand_{cid}_{self._model_id}",
            constraint_id=str(cid),
            provider=self._name,
            model_id=self._model_id,
            model_version=self._model_version,
            proposal=dict(raw),
            provenance=provenance_block(
                layer="generative_provider",
                compiler_version=COMPILER_VERSION,
                provider=self._name,
                model_id=self._model_id,
                model_version=self._model_version,
            ),
            evidence=list(raw.get("evidence") or []),
            assumptions=list(raw.get("assumptions") or ["fixture proposal; not established biology"]),
            confidence=float(raw.get("confidence", 0.4)),
            status=str(raw.get("status", "CANDIDATE")),
            validation_status="NOT_VALIDATED",
        )

    def provenance(self) -> Dict[str, Any]:
        return {
            "provider": self._name,
            "model_id": self._model_id,
            "model_version": self._model_version,
            "class": "MODEL",
            "scientific": False,
            "timestamp": utc_now(),
        }

    def version(self) -> str:
        return self._model_version

    def validate_candidate(self, candidate: ModelCandidate) -> ModelCandidate:
        if candidate.status == "UNAVAILABLE" or not candidate.proposal:
            candidate.status = "REJECTED" if candidate.status != "UNAVAILABLE" else "UNAVAILABLE"
            candidate.validation_status = "NOT_VALIDATED"
            return candidate
        candidate.validation_status = "NOT_VALIDATED"
        if candidate.status == "CANDIDATE":
            candidate.status = "SUPPORTED"
        return candidate


def fixture_cassette_provider() -> DeterministicMockGenerativeProvider:
    return DeterministicMockGenerativeProvider(
        proposals={
            "model_marker": {
                "edits": [{"operation": "REPLACE", "start": 0, "end": 4, "replacement": "TTTT"}],
                "assembly": "demo-v1",
                "reference": "chrDemo",
                "assumptions": ["synthetic fixture cassette"],
                "confidence": 0.5,
                "status": "CANDIDATE",
                "evidence": ["fixture:model_marker"],
            }
        }
    )
