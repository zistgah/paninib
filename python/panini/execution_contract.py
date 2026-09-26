# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Compiled genotype → ExecutionContract → ModelResolver → model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .contracts import ModelDescriptor
from .frontend import Program
from .phenotype.constraints import PhenotypeConstraintSet
from .registry import get_registry


@dataclass
class ModelRequirements:
    organism: str
    spatial_dimensions_min: int
    required_capabilities: List[str]
    fidelity_target: str
    need_multi_axis: bool


@dataclass
class ExecutionContract:
    program_id: str
    organism: str
    backend: str
    model_id: str
    model_status: str
    requirements: ModelRequirements
    selected: Optional[str]
    reason: str
    parameter_source: str = "MODEL_DEFAULT"
    assumptions: List[str] = field(default_factory=list)
    domain_package: str = ""
    model_version: str = ""
    data_version: str = ""
    evidence_version: str = ""
    reference_assembly: Optional[str] = None
    core_version: str = ""


def requirements_from(program: Program, constraints: PhenotypeConstraintSet) -> ModelRequirements:
    need_multi = any(
        c.property == "tail_count" and isinstance(c.target, int) and c.target >= 2
        for c in constraints.constraints
    )
    caps = ["morphogen_field", "cell_state", "developmental_stage"]
    org = get_registry().resolve_organism(program.organism)
    if org and not org.scientific:
        caps = ["conformance_switch"]
    if need_multi:
        caps.append("axis_initiation")
    return ModelRequirements(
        organism=program.organism,
        spatial_dimensions_min=2 if need_multi else 1,
        required_capabilities=caps,
        fidelity_target="DT-3",
        need_multi_axis=need_multi,
    )


def resolve_model(req: ModelRequirements, requested: Optional[str] = None) -> tuple[ModelDescriptor, str]:
    return get_registry().resolve(
        organism=req.organism,
        required_capabilities=req.required_capabilities if requested else [],
        spatial_dimensions_min=req.spatial_dimensions_min,
        requested=requested,
    )


def make_contract(program_id: str, program: Program, constraints: PhenotypeConstraintSet,
                  backend: str, requested_model: Optional[str] = None) -> ExecutionContract:
    from .version import CORE_VERSION

    req = requirements_from(program, constraints)
    desc, reason = resolve_model(req, requested_model)
    return ExecutionContract(
        program_id=program_id,
        organism=program.organism,
        backend=backend,
        model_id=desc.id,
        model_status=desc.status,
        requirements=req,
        selected=desc.id,
        reason=reason,
        domain_package=desc.package,
        model_version=desc.version,
        data_version=desc.data_version,
        evidence_version=desc.evidence_version,
        reference_assembly=desc.reference_assembly,
        core_version=CORE_VERSION,
        assumptions=[
            "model is a reduced-order planning twin, not a biochemical embryo",
            "MODEL PREDICTION ≠ EXPERIMENTAL OBSERVATION ≠ BIOLOGICAL VALIDATION",
            "domain plugin is not PANINI Core",
        ],
    )
