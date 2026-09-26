# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Closed-loop discrepancy artifacts. Residuals do not auto-update the compiler."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .artifact_util import artifact_digest, utc_now
from .knowledge import KnowledgeRecord, get_knowledge_registry


@dataclass
class Residual:
    residual_id: str
    prediction: Any
    observation: Any
    delta: Any
    domain: str
    numeric: bool
    note: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = utc_now()

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "residual_id": self.residual_id,
            "prediction": self.prediction,
            "observation": self.observation,
            "delta": self.delta,
            "domain": self.domain,
            "numeric": self.numeric,
            "note": self.note,
            "timestamp": self.timestamp,
        }
        payload["digest"] = artifact_digest(payload)
        return payload


def compute_residual(prediction: Any, observation: Any, *, domain: str = "unspecified", residual_id: str = "") -> Residual:
    numeric = isinstance(prediction, (int, float)) and isinstance(observation, (int, float))
    if numeric:
        delta: Any = observation - prediction
    else:
        delta = {
            "kind": "typed_discrepancy",
            "equal": prediction == observation,
            "predicted_type": type(prediction).__name__,
            "observed_type": type(observation).__name__,
        }
    return Residual(
        residual_id=residual_id or "res_" + domain,
        prediction=prediction,
        observation=observation,
        delta=delta,
        domain=domain,
        numeric=numeric,
        note="Residual is an artifact. It does not rewrite compiler semantics.",
    )


@dataclass
class KnowledgeUpdate:
    update_id: str
    record: Dict[str, Any]
    reason: str
    residual_id: Optional[str] = None
    applied: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "update_id": self.update_id,
            "record": dict(self.record),
            "reason": self.reason,
            "residual_id": self.residual_id,
            "applied": self.applied,
            "note": "Knowledge updates must be explicit artifacts.",
        }


def explicit_knowledge_update(record: KnowledgeRecord, reason: str, *, residual_id: Optional[str] = None) -> KnowledgeUpdate:
    get_knowledge_registry().add_record(record)
    return KnowledgeUpdate(
        update_id="ku_" + record.canonical_id,
        record=record.to_dict(),
        reason=reason,
        residual_id=residual_id,
        applied=True,
    )
