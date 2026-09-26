# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Honest classification of every v0.8/v0.9 component."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List


class CapabilityClass(str, Enum):
    CONTRACT = "CONTRACT"
    ADAPTER = "ADAPTER"
    FIXTURE = "FIXTURE"
    ENGINE = "ENGINE"
    MODEL = "MODEL"
    PROVIDER = "PROVIDER"
    SCAFFOLDED = "SCAFFOLDED"


STATUS_IMPLEMENTED = "Implemented"
STATUS_SCAFFOLDED = "Scaffolded / Contract only"
STATUS_UNAVAILABLE = "Unavailable"


def classify_component(name: str) -> Dict[str, Any]:
    rec = INVENTORY.get(name)
    if rec is None:
        return {"name": name, "class": CapabilityClass.SCAFFOLDED.value, "status": STATUS_SCAFFOLDED, "note": "unknown"}
    return dict(rec)


def inventory() -> List[Dict[str, Any]]:
    return [dict(v) for v in INVENTORY.values()]


def _e(name, cls, status, note, **extra):
    d = {"name": name, "class": cls, "status": status, "note": note}
    d.update(extra)
    return d


INVENTORY: Dict[str, Dict[str, Any]] = {
    "SimulatorDigitalBackend": _e("SimulatorDigitalBackend", "ADAPTER", STATUS_IMPLEMENTED, "backend adapter, not a new scientific model"),
    "axial_1d_model": _e("axial_1d_model", "MODEL", STATUS_IMPLEMENTED, "reduced-order 1-D axial model; not a genome realization"),
    "axial_2axis_model": _e("axial_2axis_model", "MODEL", STATUS_IMPLEMENTED, "reduced-order two-axis computational fixture, not causal genomics"),
    "DeterministicGeometryBackend": _e("DeterministicGeometryBackend", "FIXTURE", STATUS_IMPLEMENTED, "schematic point-cloud fixture / reference engine"),
    "DeterministicAnimationBackend": _e("DeterministicAnimationBackend", "FIXTURE", STATUS_IMPLEMENTED, "JSON-frame animation fixture"),
    "DeterministicMockGenerativeProvider": _e("DeterministicMockGenerativeProvider", "PROVIDER", STATUS_IMPLEMENTED, "explicitly non-biological fixture provider"),
    "UnavailableGenerativeProvider": _e("UnavailableGenerativeProvider", "PROVIDER", STATUS_UNAVAILABLE, "default; no foundation model is bound"),
    "NullInverseStrategyProvider": _e("NullInverseStrategyProvider", "PROVIDER", STATUS_UNAVAILABLE, "v0.8 null provider retained"),
    "ConstraintGraph": _e("ConstraintGraph", "ENGINE", STATUS_IMPLEMENTED, "typed graph + topological order; not quantitative genetics"),
    "ValidationRegistry": _e("ValidationRegistry", "ENGINE", STATUS_IMPLEMENTED, "observation → evidence → claim history"),
    "LocalMockRealizationBackend": _e("LocalMockRealizationBackend", "ADAPTER", STATUS_IMPLEMENTED, "physical adapter / mock; not a synthesis vendor"),
    "MultiscaleStateEngine": _e("MultiscaleStateEngine", "ENGINE", STATUS_IMPLEMENTED, "extensible state machinery; not a populated mammalian state"),
    "BiochemicalEngine": _e("BiochemicalEngine", "ENGINE", STATUS_IMPLEMENTED, "generic ODE substrate + synthetic A→B→C fixture; not mammalian biochemistry"),
    "CPUReferenceBackend": _e("CPUReferenceBackend", "ENGINE", STATUS_IMPLEMENTED, "CPU reference oracle for execution models"),
    "GPUBackend": _e("GPUBackend", "CONTRACT", STATUS_UNAVAILABLE, "CUDA unavailable in this environment; contract + detection only"),
    "SpatialFieldEngine": _e("SpatialFieldEngine", "ENGINE", STATUS_IMPLEMENTED, "grid/scalar/vector/voxel substrate; not a tissue atlas"),
    "ReactionDiffusionEngine": _e("ReactionDiffusionEngine", "ENGINE", STATUS_IMPLEMENTED, "generic RD primitive + canonical fixture; not a morphogen claim"),
    "CellularEngine": _e("CellularEngine", "ENGINE", STATUS_IMPLEMENTED, "cell substrate + synthetic fixture; not a mammalian cell"),
    "DevelopmentalEngine": _e("DevelopmentalEngine", "ENGINE", STATUS_IMPLEMENTED, "combines kinetics + fields + cells; domain models plug in later"),
    "PhenotypeEngine": _e("PhenotypeEngine", "ENGINE", STATUS_IMPLEMENTED, "desired / predicted / observed remain distinct artifacts"),
    "PhysiologicalEngine": _e("PhysiologicalEngine", "ENGINE", STATUS_IMPLEMENTED, "generic organ/system fixture; not a complete physiology model"),
    "PointCloudEngine": _e("PointCloudEngine", "ENGINE", STATUS_IMPLEMENTED, "point-cloud materialization with provenance"),
    "VoxelEngine": _e("VoxelEngine", "ENGINE", STATUS_IMPLEMENTED, "voxelization of fields / parametric axes"),
    "ParametricGeometryEngine": _e("ParametricGeometryEngine", "ENGINE", STATUS_IMPLEMENTED, "axis/radius/branching → geometry; schematic, uncalibrated"),
    "MeshBackend": _e("MeshBackend", "ENGINE", STATUS_IMPLEMENTED, "triangle mesh from parametric cylinders; no external mesher"),
    "AnimationEngine": _e("AnimationEngine", "ENGINE", STATUS_IMPLEMENTED, "consumes state trajectories; renderer optional"),
    "RealizationPlanningEngine": _e("RealizationPlanningEngine", "ENGINE", STATUS_IMPLEMENTED, "plans physical artifacts from GenotypeDesign; labs remain adapters"),
    "ReferenceGenomeEngine": _e("ReferenceGenomeEngine", "ENGINE", STATUS_IMPLEMENTED, "assembly/interval/digest over synthetic + retrieved loci"),
    "SequenceEngine": _e("SequenceEngine", "ENGINE", STATUS_IMPLEMENTED, "canonical v0.6/v0.7 edit engine, strengthened"),
    "GenerativeSequenceEngine": _e("GenerativeSequenceEngine", "ENGINE", STATUS_IMPLEMENTED, "candidate pipeline over provider abstraction; default is non-biological"),
    "InverseResolutionEngine": _e("InverseResolutionEngine", "ENGINE", STATUS_IMPLEMENTED, "synthetic inverse candidates only; no unsupported knockout claims"),
    "ConstraintSolver": _e("ConstraintSolver", "ENGINE", STATUS_IMPLEMENTED, "graph solver producing ResolutionPlan; not a QG solver"),
    "CoverageEngine": _e("CoverageEngine", "ENGINE", STATUS_IMPLEMENTED, "class-separated coverage; no single misleading percentage"),
    "VerificationEngine": _e("VerificationEngine", "ENGINE", STATUS_IMPLEMENTED, "cross-artifact digest/provenance/separation checks"),
    "ArtifactDebugger": _e("ArtifactDebugger", "ENGINE", STATUS_IMPLEMENTED, "artifact-level traces; full causal inversion is later work"),
    "SSA_stochastic": _e("SSA_stochastic", "ENGINE", STATUS_IMPLEMENTED, "CPU Gillespie fixture on a synthetic reaction system; not mammalian SSA"),
    "SSABackend": _e("SSABackend", "ENGINE", STATUS_IMPLEMENTED, "seeded Gillespie backend; fixture kinetics only"),
}
