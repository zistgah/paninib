# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""First-class typed diagnostics for biological resolution."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .schema_validate import validate_named


DIAGNOSTIC_SCHEMA_VERSION = "0.7.0"

DIAGNOSTIC_CATALOG = {
    "E0001": "UNRESOLVED_BIOLOGICAL_MECHANISM",
    "E0002": "MISSING_STANDARD_PART",
    "E0003": "AMBIGUOUS_BIOLOGICAL_MAPPING",
    "E0004": "INSUFFICIENT_EVIDENCE",
    "E0005": "REFERENCE_SEQUENCE_UNAVAILABLE",
    "E0006": "REFERENCE_CONTEXT_INCOMPATIBLE",
    "E0007": "UNSUPPORTED_BIOLOGICAL_OPERATION",
    "E0008": "MODEL_ONLY_REALIZATION",
    "E0009": "USER_ASSERTION_REQUIRES_VALIDATION",
    "E0010": "CANDIDATE_SEQUENCE_NOT_CAUSALLY_ESTABLISHED",
    "E0011": "BIOLOGICAL_CONSTRAINT_DEPENDENCY_UNRESOLVED",
}

CAUSAL_BASIS = (
    "STANDARD_PART",
    "EVIDENCE_BACKED",
    "USER_ASSERTED",
    "MODEL_DERIVED",
    "GENERATIVE_HYPOTHESIS",
    "UNRESOLVED",
    "ASSOCIATED",
    "CORRELATED",
)

VALIDATION_STATUS = (
    "NOT_EVALUATED",
    "NOT_VALIDATED",
    "COMPUTATIONALLY_SUPPORTED",
    "EXPERIMENTALLY_SUPPORTED",
    "EXPERIMENTALLY_VALIDATED",
)

ASSOCIATION_CLASS = (
    "ASSOCIATED",
    "CORRELATED",
    "MECHANISTICALLY_SUPPORTED",
    "CAUSALLY_SUPPORTED",
    "EXPERIMENTALLY_VALIDATED",
)

REALIZATION_STRATEGIES = (
    "STANDARD_LIBRARY",
    "REGISTRY_LOOKUP",
    "KNOWLEDGE_PROVIDER",
    "MODEL_DERIVED",
    "GENERATIVE_HYPOTHESIS",
    "USER_ASSERTED",
    "UNRESOLVED",
)

CAUSAL_ENOUGH = {
    "MECHANISTICALLY_SUPPORTED",
    "CAUSALLY_SUPPORTED",
    "EXPERIMENTALLY_VALIDATED",
    "STANDARD_PART",
}


@dataclass
class Diagnostic:
    code: str
    constraint_id: str
    message: str
    severity: str = "error"
    schema_version: str = DIAGNOSTIC_SCHEMA_VERSION
    name: str = ""
    source_location: str = ""
    current_evidence: List[str] = field(default_factory=list)
    causal_basis: str = "UNRESOLVED"
    validation_status: str = "NOT_EVALUATED"
    why_lowering_stopped: str = ""
    resolution_path: str = ""
    affected_artifacts: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.code not in DIAGNOSTIC_CATALOG:
            raise ValueError(f"unknown diagnostic code {self.code}")
        if not self.name:
            self.name = DIAGNOSTIC_CATALOG[self.code]
        if self.severity not in {"error", "warning", "info"}:
            raise ValueError(f"unknown severity {self.severity}")
        if self.causal_basis not in CAUSAL_BASIS:
            raise ValueError(f"unknown causal_basis {self.causal_basis}")
        if self.validation_status not in VALIDATION_STATUS:
            raise ValueError(f"unknown validation_status {self.validation_status}")

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        validate_named(payload, "diagnostic.schema.json")
        return payload


def emit(code: str, constraint_id: str, message: str, *, severity: Optional[str] = None, **kwargs: Any) -> Diagnostic:
    if severity is None:
        severity = "warning" if code in {"E0008", "E0009"} else "error"
    return Diagnostic(code=code, constraint_id=constraint_id, message=message, severity=severity, **kwargs)
