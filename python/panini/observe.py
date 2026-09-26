# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""First-class Observation artifact. An observation is not automatically truth."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .artifact_util import artifact_digest, utc_now


OBSERVATION_SOURCES = (
    "SIMULATION",
    "PHYSICAL_EXPERIMENT",
    "MANUAL_ASSERTION",
    "EXTERNAL_DATASET",
)


@dataclass
class Observation:
    observation_id: str
    source: str
    source_id: str
    subject: str
    measurement: Any
    unit: str = ""
    method: str = ""
    uncertainty: Optional[float] = None
    timestamp: str = ""
    provenance: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.source not in OBSERVATION_SOURCES:
            raise ValueError(f"unknown observation source {self.source}")
        if not self.timestamp:
            self.timestamp = utc_now()

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "observation_id": self.observation_id,
            "source": self.source,
            "source_id": self.source_id,
            "timestamp": self.timestamp,
            "subject": self.subject,
            "measurement": self.measurement,
            "unit": self.unit,
            "method": self.method,
            "uncertainty": self.uncertainty,
            "provenance": dict(self.provenance),
        }
        payload["digest"] = artifact_digest(payload)
        return payload
