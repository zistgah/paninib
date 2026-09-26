# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Validation ingestion. Ingestion is not verification.

Observation → EvidenceRecord → ClaimEvaluation → status transition.
History is appended, never overwritten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .artifact_util import artifact_digest, text_digest, utc_now
from .observe import Observation


CLAIM_STATUSES = (
    "NOT_VALIDATED",
    "OBSERVED",
    "SUPPORTED",
    "VERIFIED",
    "CONTRADICTED",
    "INCONCLUSIVE",
    "NOT_EVALUATED",
)


@dataclass
class EvidenceRecord:
    evidence_id: str
    observation_id: str
    claim_id: str
    method: str
    source: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    actor: str = "panini.validate"

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = utc_now()

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "evidence_id": self.evidence_id,
            "observation_id": self.observation_id,
            "claim_id": self.claim_id,
            "method": self.method,
            "source": self.source,
            "payload": dict(self.payload),
            "timestamp": self.timestamp,
            "actor": self.actor,
        }
        payload["digest"] = artifact_digest(payload)
        return payload


@dataclass
class ClaimTransition:
    previous_status: str
    new_status: str
    evidence_id: str
    method: str
    source: str
    timestamp: str
    actor: str
    artifact_digest: str
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "evidence_id": self.evidence_id,
            "method": self.method,
            "source": self.source,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "artifact_digest": self.artifact_digest,
            "note": self.note,
        }


@dataclass
class ClaimEvaluation:
    claim_id: str
    subject: str
    statement: str
    status: str = "NOT_VALIDATED"
    history: List[ClaimTransition] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "subject": self.subject,
            "statement": self.statement,
            "status": self.status,
            "history": [h.to_dict() for h in self.history],
            "evidence_ids": list(self.evidence_ids),
        }


class ValidationRegistry:
    def __init__(self) -> None:
        self.observations: Dict[str, Observation] = {}
        self.evidence: Dict[str, EvidenceRecord] = {}
        self.claims: Dict[str, ClaimEvaluation] = {}

    def ensure_claim(self, claim_id: str, subject: str, statement: str) -> ClaimEvaluation:
        if claim_id not in self.claims:
            self.claims[claim_id] = ClaimEvaluation(
                claim_id=claim_id,
                subject=subject,
                statement=statement,
                status="NOT_VALIDATED",
            )
        return self.claims[claim_id]

    def ingest_observation(self, observation: Observation, claim_id: str, method: str = "ingest") -> EvidenceRecord:
        self.observations[observation.observation_id] = observation
        ev_id = "ev_" + text_digest(observation.observation_id + claim_id)[:16]
        record = EvidenceRecord(
            evidence_id=ev_id,
            observation_id=observation.observation_id,
            claim_id=claim_id,
            method=method,
            source=observation.source,
            payload={"measurement": observation.measurement, "subject": observation.subject},
        )
        self.evidence[ev_id] = record
        claim = self.ensure_claim(claim_id, observation.subject, f"claim about {observation.subject}")
        if ev_id not in claim.evidence_ids:
            claim.evidence_ids.append(ev_id)
        return record

    def transition(
        self,
        claim_id: str,
        new_status: str,
        evidence: EvidenceRecord,
        *,
        actor: str = "panini.validate",
        note: str = "",
    ) -> ClaimEvaluation:
        if new_status not in CLAIM_STATUSES:
            raise ValueError(f"unknown claim status {new_status}")
        claim = self.claims.get(claim_id) or self.ensure_claim(claim_id, evidence.payload.get("subject", ""), claim_id)
        previous = claim.status
        if previous == new_status and claim.history:
            # still record explicit no-op transitions so history is complete
            pass
        trans = ClaimTransition(
            previous_status=previous,
            new_status=new_status,
            evidence_id=evidence.evidence_id,
            method=evidence.method,
            source=evidence.source,
            timestamp=utc_now(),
            actor=actor,
            artifact_digest=evidence.to_dict()["digest"],
            note=note,
        )
        claim.history.append(trans)
        claim.status = new_status
        if evidence.evidence_id not in claim.evidence_ids:
            claim.evidence_ids.append(evidence.evidence_id)
        return claim

    def evaluate_against_prediction(
        self,
        claim_id: str,
        observation: Observation,
        predicted: Any,
        *,
        method: str = "residual_compare",
    ) -> ClaimEvaluation:
        evidence = self.ingest_observation(observation, claim_id, method=method)
        measured = observation.measurement
        if _comparable(measured, predicted) and measured == predicted:
            new_status = "SUPPORTED"
            note = "observation matches prediction; not automatically VERIFIED"
        elif _contradictory(measured, predicted):
            new_status = "CONTRADICTED"
            note = "observation contradicts prediction"
        else:
            new_status = "OBSERVED"
            note = "observation ingested; relation to prediction inconclusive"
        return self.transition(claim_id, new_status, evidence, note=note)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observations": {k: v.to_dict() for k, v in self.observations.items()},
            "evidence": {k: v.to_dict() for k, v in self.evidence.items()},
            "claims": {k: v.to_dict() for k, v in self.claims.items()},
        }


def _comparable(a: Any, b: Any) -> bool:
    return type(a) is type(b) or (isinstance(a, (int, float)) and isinstance(b, (int, float)))


def _contradictory(measured: Any, predicted: Any) -> bool:
    if isinstance(measured, (int, float)) and isinstance(predicted, (int, float)):
        return measured != predicted
    if isinstance(measured, str) and isinstance(predicted, str):
        return measured.lower() != predicted.lower()
    return False


_REGISTRY: Optional[ValidationRegistry] = None


def get_validation_registry() -> ValidationRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ValidationRegistry()
    return _REGISTRY


def reset_validation_registry() -> ValidationRegistry:
    global _REGISTRY
    _REGISTRY = ValidationRegistry()
    return _REGISTRY
