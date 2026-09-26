# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Physical realization backend contract and local mock adapter.

Digital compilation is not physical execution. The mock backend exercises
the contract without a laboratory vendor dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .artifact_util import artifact_digest, provenance_block, text_digest
from .version import COMPILER_VERSION


REALIZATION_STATUS = ("REALIZED", "REALIZATION_UNAVAILABLE", "REALIZATION_INVALID")


@dataclass
class PhysicalRealization:
    realization_id: str
    design_id: str
    status: str
    constructs: List[Dict[str, Any]] = field(default_factory=list)
    sequence_artifacts: List[Dict[str, Any]] = field(default_factory=list)
    assembly_references: List[str] = field(default_factory=list)
    standard_library_components: List[str] = field(default_factory=list)
    qc_requirements: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    checksums: Dict[str, str] = field(default_factory=dict)
    note: str = "Physical realization is a specification/handoff artifact, not wet-lab execution."

    def __post_init__(self) -> None:
        if self.status not in REALIZATION_STATUS:
            raise ValueError(f"unknown realization status {self.status}")

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "realization_id": self.realization_id,
            "design_id": self.design_id,
            "status": self.status,
            "constructs": list(self.constructs),
            "sequence_artifacts": list(self.sequence_artifacts),
            "assembly_references": list(self.assembly_references),
            "standard_library_components": list(self.standard_library_components),
            "qc_requirements": list(self.qc_requirements),
            "constraints": list(self.constraints),
            "provenance": dict(self.provenance),
            "checksums": dict(self.checksums),
            "note": self.note,
        }
        payload["digest"] = artifact_digest(payload)
        return payload


class PhysicalRealizationBackend(Protocol):
    def capabilities(self) -> Dict[str, Any]: ...
    def realize(self, genotype_design: Dict[str, Any]) -> PhysicalRealization: ...
    def inspect(self, realization: PhysicalRealization) -> Dict[str, Any]: ...
    def verify(self, realization: PhysicalRealization) -> Dict[str, Any]: ...
    def provenance(self) -> Dict[str, Any]: ...


class LocalMockRealizationBackend:
    """Deterministic local adapter. Not a synthesis vendor."""

    def __init__(self, name: str = "panini.physical.local_mock") -> None:
        self.name = name

    def capabilities(self) -> Dict[str, Any]:
        return {
            "backend": self.name,
            "physical": True,
            "laboratory_vendor": False,
            "can_realize": True,
            "can_verify": True,
            "adapters": ["local_mock", "sbol_export"],
            "note": "specification-only mock; authorization remains false",
        }

    def provenance(self) -> Dict[str, Any]:
        return provenance_block(
            layer="physical_realization",
            compiler_version=COMPILER_VERSION,
            provider=self.name,
            model_id="local_mock",
            model_version="0.8.0",
        )

    def realize(self, genotype_design: Dict[str, Any]) -> PhysicalRealization:
        design_id = str(genotype_design.get("design_id") or "gd_unknown")
        status_in = str(genotype_design.get("status") or "DESIGN_UNRESOLVED")
        edits = list(genotype_design.get("edits") or [])
        if status_in in {"INVALID_PROGRAM", "INVALID_EDIT", "REFERENCE_MISMATCH"}:
            out_status = "REALIZATION_INVALID"
        elif status_in == "DESIGN_UNRESOLVED" or not edits:
            out_status = "REALIZATION_UNAVAILABLE"
        else:
            out_status = "REALIZED"
        rid = "pr_" + text_digest(design_id + out_status + str(edits))[:16]
        constructs = []
        seq_artifacts = []
        if out_status == "REALIZED":
            constructs.append({
                "construct_id": f"{rid}:construct",
                "role": "designed_edit_set",
                "edits": edits,
                "organism": genotype_design.get("organism"),
                "assembly": genotype_design.get("assembly"),
                "reference": genotype_design.get("reference"),
            })
            seq_artifacts.append({
                "kind": "sequence_intent",
                "reference": genotype_design.get("reference"),
                "assembly": genotype_design.get("assembly"),
                "edit_count": len(edits),
            })
        realization = PhysicalRealization(
            realization_id=rid,
            design_id=design_id,
            status=out_status,
            constructs=constructs,
            sequence_artifacts=seq_artifacts,
            assembly_references=[genotype_design.get("assembly")] if genotype_design.get("assembly") else [],
            standard_library_components=list(genotype_design.get("evidence") or []),
            qc_requirements=["retrieval_digest_recomputed", "no_invented_nucleotide_string", "authorization_gate"],
            constraints=list(genotype_design.get("constraints") or []),
            provenance=self.provenance(),
            checksums={
                "design": text_digest(str(genotype_design.get("design_id"))),
                "edits": artifact_digest(edits),
            },
        )
        return realization

    def inspect(self, realization: PhysicalRealization) -> Dict[str, Any]:
        return {
            "realization_id": realization.realization_id,
            "status": realization.status,
            "constructs": len(realization.constructs),
            "digest": realization.to_dict()["digest"],
        }

    def verify(self, realization: PhysicalRealization) -> Dict[str, Any]:
        checks = [
            {"name": "typed_status", "passed": realization.status in REALIZATION_STATUS},
            {"name": "has_id", "passed": bool(realization.realization_id)},
            {"name": "not_pretending_wetlab", "passed": "not wet-lab" in realization.note.lower()},
            {"name": "realized_has_construct", "passed": realization.status != "REALIZED" or bool(realization.constructs)},
        ]
        # keep the note honest: digital ≠ physical
        checks.append({
            "name": "digital_is_not_physical",
            "passed": realization.provenance.get("layer") == "physical_realization",
        })
        return {
            "overall_pass": all(c["passed"] for c in checks),
            "checks": checks,
            "status": realization.status,
        }


def default_physical_backend() -> LocalMockRealizationBackend:
    return LocalMockRealizationBackend()
