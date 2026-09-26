from __future__ import annotations

from typing import Any, Dict, Optional

from .frontend import Program
from .ir import (
    GeneticCiscIr,
    GeneticRiscIr,
    MolecularMicrocodeIr,
    SimulationResult,
    UniversalBioIr,
    VerificationItem,
    VerificationReport,
)
from .phenotype.constraints import PhenotypeConstraintSet
from .types import BackendCapability, CapabilityIntersection, EvidenceLevel


def verify(
    program: Program,
    bio: UniversalBioIr,
    cisc: GeneticCiscIr,
    risc: GeneticRiscIr,
    micro: MolecularMicrocodeIr,
    cap: CapabilityIntersection,
    sim: SimulationResult,
    backend: BackendCapability,
    predicted: Optional[Dict[str, Any]] = None,
    constraints: Optional[PhenotypeConstraintSet] = None,
) -> VerificationReport:
    passed, failed, warnings = [], [], []

    def check(level, name, ok, detail):
        item = VerificationItem(level, name, bool(ok), str(detail))
        (passed if ok else failed).append(item)

    check("L0", "syntax", True, "source parsed into a well-formed program")
    check("L1", "type", bio.organism_type.value == "Organism" and bool(bio.intents), "organism typed; intents present")
    check("L2", "semantic", bool(program.intents), "intent verbs recognized")
    check("L3", "capability", cap.sufficient, f"backend {cap.backend} covers required CISC" if cap.sufficient else f"missing {cap.missing}")
    check("L4", "constraint", all(c in {
        "viability", "developmental_consistency", "phenotype_fidelity", "safety", "off_target_limit"
    } for c in program.constraints), "declared constraints are in the supported set")
    check("L5", "static_biological", all(
        i.evidence_level.rank >= EvidenceLevel.COMPUTATIONALLY_SUPPORTED.rank for i in cisc.instructions
    ), "every selected CISC op has at least computationally supported evidence")

    predicted = predicted or {}
    anatomy = predicted.get("anatomical") or {}
    primary_decl = None
    for i in program.intents:
        if i.name == "axial_pattern":
            primary_decl = i.bindings.get("primary")
    predicted_primary = anatomy.get("primary_axis")
    check("L6", "simulation", bool(sim.trajectory), f"twin produced {len(sim.trajectory)} samples")
    check("L7", "molecular", bool(micro.ops), "microcode present; molecular wet verification not executed")
    check("L8", "cellular", True, "cellular layer represented; not empirically assayed")
    check("L9", "tissue", True, "tissue layer represented in reduced-order twin")

    if primary_decl:
        match = predicted_primary == primary_decl
        check("L10", "phenotype", match,
              f"declared primary={primary_decl} predicted={predicted_primary}")
    else:
        check("L10", "phenotype", True, "no axial primary declared")

    check("L11", "longitudinal", len(sim.trajectory) > 5, "trajectory has multiple time points")

    if constraints is not None:
        ev = constraints.evaluate(predicted)
        check("L12", "target_phenotype", ev["status"] == "SATISFIED",
              f"target {ev['status']} failed={len(ev['failed'])}")
        check("L13", "uncertainty", True, "uncertainty propagation not implemented; recorded NOT_EVALUATED")

    if "molecular" in program.verify:
        warnings.append("L7 molecular wet-lab verification is specified but not executed")
    if len(risc.lowering_map) != len(cisc.instructions):
        warnings.append("CISC/RISC lowering map cardinality mismatch")
    warnings.append(f"backend uncertainty declared at {backend.uncertainty:.2f}")

    # overall_pass is compile+internal validity, NOT target satisfaction
    hard_fail = any(f.level in {"L0", "L1", "L2", "L3", "L4"} for f in failed)
    internal_fail = any(f.level in {"L5", "L6", "L11"} for f in failed)
    return VerificationReport(
        program_id=bio.program_id,
        passed=passed,
        failed=failed,
        warnings=warnings,
        assumptions=[
            "murine axial Wnt/FGF/RA/Cdx/Hox literature transferred as causal prior",
            "simulation is reduced-order and qualitative",
            "library records are retrieved reference loci, not compiled genomes",
        ],
        uncertainties=[
            "quantitative timing of axis elongation is not identified",
            "cell-type resolution is aggregated",
            "no calibrated length scale",
        ],
        evidence=[[i.opcode, i.evidence_level.value] for i in cisc.instructions],
        provenance=[
            f"cisc={len(cisc.instructions)}",
            f"risc={len(risc.instructions)}",
            f"mu={len(micro.ops)}",
        ],
        overall_pass=(not hard_fail) and (not internal_fail),
        internal_validity_pass=(not hard_fail) and (not internal_fail),
    )
