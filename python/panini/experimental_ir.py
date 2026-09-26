# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Experimental IR and ResolutionWorkOrder."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .schema_validate import validate_named
from .diagnostics import Diagnostic


EXPERIMENTAL_IR_VERSION = "0.7.0"
WORK_ORDER_STATUS = ("OPEN", "BLOCKED", "SATISFIED", "WITHDRAWN")
EVIDENCE_CLASSES = (
    "association",
    "correlation",
    "mechanistic",
    "causal",
    "experimental_validation",
    "reference_sequence",
    "standard_part",
    "user_assertion_review",
)


def _digest(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(blob).hexdigest()


@dataclass
class ResolutionWorkOrder:
    work_order_id: str
    constraint_id: str
    diagnostic_code: str
    question: str
    target_property: str
    missing_relation: str
    required_evidence_class: str
    resolution_criterion: str
    schema_version: str = EXPERIMENTAL_IR_VERSION
    current_knowledge: Dict[str, Any] = field(default_factory=dict)
    candidate_hypotheses: List[str] = field(default_factory=list)
    recommended_information_source: str = "knowledge_provider_or_primary_literature"
    recommended_assay_class: str = "unspecified_evidence_class"
    measurement_required: bool = True
    knowledge_record_to_create: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    unblocks: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    status: str = "OPEN"

    def __post_init__(self) -> None:
        if self.required_evidence_class not in EVIDENCE_CLASSES:
            raise ValueError(f"unknown evidence class {self.required_evidence_class}")
        if self.status not in WORK_ORDER_STATUS:
            raise ValueError(f"unknown work-order status {self.status}")

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        validate_named(payload, "resolution_work_order.schema.json")
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResolutionWorkOrder":
        validate_named(data, "resolution_work_order.schema.json")
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in allowed})


@dataclass
class ExperimentalIR:
    experimental_ir_id: str
    program_id: str
    work_orders: List[ResolutionWorkOrder] = field(default_factory=list)
    note: str = (
        "ExperimentalIR names unknowns, evidence classes, and knowledge records "
        "that would unblock compilation. It is not a laboratory protocol and is "
        "not bound to a LIMS, ELN, vendor, or assay platform."
    )
    schema_version: str = EXPERIMENTAL_IR_VERSION
    integration: Dict[str, Any] = field(default_factory=lambda: {
        "neutrality": "integration-neutral",
        "lims": "adapter-only",
        "eln": "adapter-only",
        "vendor": "none",
    })
    question: str = ""
    hypothesis: str = ""
    constraints: List[str] = field(default_factory=list)
    design: Dict[str, Any] = field(default_factory=dict)
    execution: Dict[str, Any] = field(default_factory=dict)
    observation: Dict[str, Any] = field(default_factory=dict)
    measurement: Dict[str, Any] = field(default_factory=dict)
    expected_result: Any = None
    actual_result: Any = None
    evidence: List[str] = field(default_factory=list)
    claim: Dict[str, Any] = field(default_factory=dict)
    status: str = "OPEN"

    def context_dict(self) -> Dict[str, Any]:
        """Extended experimental fields that live beside the 0.7 schema document."""
        return {
            "question": self.question,
            "hypothesis": self.hypothesis,
            "constraints": list(self.constraints),
            "design": dict(self.design),
            "execution": dict(self.execution),
            "observation": dict(self.observation),
            "measurement": dict(self.measurement),
            "expected_result": self.expected_result,
            "actual_result": self.actual_result,
            "evidence": list(self.evidence),
            "claim": dict(self.claim),
            "status": self.status,
        }

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "experimental_ir_id": self.experimental_ir_id,
            "program_id": self.program_id,
            "work_orders": [w.to_dict() for w in self.work_orders],
            "note": self.note,
            "integration": self.integration,
        }
        validate_named(payload, "experimental_ir.schema.json")
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentalIR":
        validate_named(data, "experimental_ir.schema.json")
        orders = [ResolutionWorkOrder.from_dict(w) for w in data.get("work_orders") or []]
        return cls(
            experimental_ir_id=data["experimental_ir_id"],
            program_id=data.get("program_id", ""),
            work_orders=orders,
            note=data.get("note", ""),
            schema_version=data.get("schema_version", EXPERIMENTAL_IR_VERSION),
            integration=data.get("integration") or {},
        )


def work_order_from_diagnostic(
    diagnostic: Diagnostic,
    *,
    target_property: str,
    current_knowledge: Optional[Dict[str, Any]] = None,
    missing_relation: str = "genotype_realization_of_phenotype_constraint",
) -> ResolutionWorkOrder:
    evidence_class = {
        "E0001": "causal",
        "E0002": "standard_part",
        "E0003": "mechanistic",
        "E0004": "causal",
        "E0005": "reference_sequence",
        "E0006": "reference_sequence",
        "E0007": "mechanistic",
        "E0008": "experimental_validation",
        "E0009": "user_assertion_review",
        "E0010": "causal",
        "E0011": "causal",
    }.get(diagnostic.code, "causal")
    template = {
        "kind": "RealizationMapping",
        "constraint_id": diagnostic.constraint_id,
        "required_fields": [
            "organism", "intent_verb", "intent_name", "association_class",
            "causal_basis", "validation_status", "assembly", "reference", "edits",
        ],
        "note": "Create this record through the knowledge provider. Do not edit compiler source.",
    }
    body = {"constraint_id": diagnostic.constraint_id, "code": diagnostic.code, "message": diagnostic.message}
    return ResolutionWorkOrder(
        work_order_id="rwo_" + _digest(body)[:16],
        constraint_id=diagnostic.constraint_id,
        diagnostic_code=diagnostic.code,
        question=(
            f"What evidence-backed genotype realization, if any, satisfies "
            f"constraint {diagnostic.constraint_id}?"
        ),
        target_property=target_property,
        current_knowledge=current_knowledge or {
            "causal_basis": diagnostic.causal_basis,
            "validation_status": diagnostic.validation_status,
            "evidence": diagnostic.current_evidence,
        },
        missing_relation=missing_relation,
        candidate_hypotheses=[],
        required_evidence_class=evidence_class,
        recommended_information_source="knowledge_provider_or_primary_literature",
        recommended_assay_class="evidence_class_only_not_a_protocol",
        measurement_required=True,
        resolution_criterion=(
            "A RealizationMapping knowledge record whose association_class is "
            "mechanistically or causally supported, with pinned reference identity, "
            "must be added through the knowledge interface."
        ),
        knowledge_record_to_create=template,
        dependencies=[],
        unblocks=["constraint_resolution", "genotype_design", "sequence_ir", diagnostic.constraint_id],
        provenance={"compiler": "panini", "layer": "biological_resolution", "diagnostic": diagnostic.code},
        status="OPEN",
    )


def dumps_canonical(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, default=str)
