from __future__ import annotations

import math
from typing import List, Optional

from .ir import (
    Authorization,
    ConstructSpec,
    GeneticCiscIr,
    GeometryIr,
    MolecularMicrocodeIr,
    PhenotypeIr,
    PhenotypeProperty,
    Point,
    RealizationPackage,
    SimulationProgram,
    SimulationResult,
    TrajectoryPoint,
    UniversalBioIr,
)
from .registry import get_registry
from .stdlib import modules_for_intent, verify_retrievals


def _primary(bio: UniversalBioIr) -> str:
    for i in bio.intents:
        if i.name == "axial_pattern":
            return i.bindings.get("primary", "unspecified")
    return "unspecified"


def _secondary(bio: UniversalBioIr) -> Optional[str]:
    for i in bio.intents:
        if i.name == "axial_pattern":
            return i.bindings.get("secondary")
    return None


def realize(cisc: GeneticCiscIr, micro: MolecularMicrocodeIr, organism: str, bio: UniversalBioIr) -> RealizationPackage:
    gm = get_registry().genome_for_organism(organism)
    if gm and gm.verify_fn:
        errors = gm.verify_fn()
        if errors:
            raise RuntimeError("retrieval digest failure: " + "; ".join(errors))
    primary = _primary(bio)
    secondary = _secondary(bio)
    hits = modules_for_intent(primary, secondary, organism=organism)
    if not hits:
        raise RuntimeError("no retrieved reference loci for this intent; refusing realization")

    constructs: List[ConstructSpec] = []
    for a in hits:
        if a.sequence is not None:
            raise RuntimeError(f"{a.id} must not carry an invented sequence string")
        if a.kind != "REFERENCE_LOCUS":
            raise RuntimeError(f"{a.id} is not a reference locus")
        r = getattr(a, "retrieval", None)
        role = {
            "wnt": "posteriorizing_signal",
            "fgf": "posteriorizing_signal",
            "ra": "anteriorizing_countergradient",
            "cdx": "posterior_identity_program",
            "hox": "posterior_identity_program",
        }.get(getattr(a, "drives", ""), "module")
        constructs.append(ConstructSpec(
            artifact_id=a.id,
            role=role,
            organism=a.organism,
            kind=a.kind,
            sequence_ref=a.sequence_ref,
            topology="reference_locus" if r is not None else "virtual",
            annotations=[a.annotation, a.provenance, f"drives={getattr(a, 'drives', '')}"],
            evidence=a.evidence.value if hasattr(a.evidence, "value") else str(a.evidence),
            sequence=None,
            chrom=r.chrom if r is not None else getattr(a, "chrom", None),
            start=r.start if r is not None else getattr(a, "start", None),
            end=r.end if r is not None else getattr(a, "end", None),
            strand=r.strand if r is not None else getattr(a, "strand", None),
            assembly=r.assembly if r is not None else getattr(a, "assembly", None),
            retrieval_digest=r.digest if r is not None else None,
            drives=getattr(a, "drives", None),
            artifact_class="REFERENCE_LOCUS",
        ))

    required = sorted({cap for i in cisc.instructions for cap in i.required_capabilities})
    return RealizationPackage(
        program_id=cisc.program_id,
        backend=micro.backend,
        construct_specification=constructs,
        required_capabilities=required,
        qc_requirements=[],
        verification_plan=[],
        provenance=[
            f"cisc_instructions={len(cisc.instructions)}",
            f"micro_ops={len(micro.ops)}",
            f"intent_primary={primary}",
            f"intent_secondary={secondary}",
            f"domain={get_registry().resolve_organism(organism).package if get_registry().resolve_organism(organism) else 'unregistered'}",
        ],
        safety_constraints=[],
        note=(
            "Realization is a specification. It contains retrieved reference loci, "
            "not designed constructs and not executable laboratory protocol."
            + (
                " TEST / NON-BIOLOGICAL / CONFORMANCE MODEL."
                if (get_registry().resolve_organism(organism)
                    and not get_registry().resolve_organism(organism).scientific)
                else ""
            )
        ),
        authorization=Authorization(authorized=False, scope="specification_only"),
        assembly_plan={
            "format": "panini.assembly.v0",
            "steps": [],
            "note": "empty: no designed construct to assemble",
        },
        sequence_verification_plan={
            "format": "panini.seqverify.v0",
            "acceptance": [
                {"check": "retrieval_digest_recomputed", "required": True},
                {"check": "no_invented_nucleotide_string", "required": True},
            ],
        },
        instrument_bindings=[
            {"step": "none", "instrument_class": None, "reason": "specification_only"},
        ],
        designed_constructs=[],
    )


def plan_simulation(bio: UniversalBioIr) -> SimulationProgram:
    org = get_registry().resolve_organism(bio.organism)
    if org and org.default_model_id:
        model = get_registry().get_execution(org.default_model_id)
        return model.plan_simulation(bio)
    raise RuntimeError(f"no execution model registered for organism {bio.organism!r}")


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-6.0 * x))


def run_simulation(plan: SimulationProgram) -> SimulationResult:
    mid = plan.model_kind
    model = get_registry().get_execution(mid)
    # Domain models expose compile-time integration via plan + their own runner.
    if hasattr(model, "compile_time_simulate_plan"):
        return model.compile_time_simulate_plan(plan)
    from importlib import import_module
    desc = get_registry().get_descriptor(mid)
    try:
        preview = import_module(desc.package + ".compile_preview")
        return preview.run_simulation(plan)
    except Exception:
        return model.compile_time_simulate(type("B", (), {"program_id": plan.program_id, "organism": "", "intents": []})())


def phenotype_from_sim(spec: PhenotypeIr, sim: SimulationResult) -> PhenotypeIr:
    out = PhenotypeIr(
        program_id=spec.program_id,
        molecular=list(spec.molecular),
        cellular=list(spec.cellular),
        tissue=list(spec.tissue),
        anatomical=list(spec.anatomical),
        physiological=list(spec.physiological),
        behavioral=list(spec.behavioral),
        temporal=list(spec.temporal),
        geometric=list(spec.geometric),
    )
    value = "tail" if sim.terminal_phenotype_score > 0.6 else (
        "head" if sim.terminal_phenotype_score < 0.35 else "indeterminate"
    )
    last_hox = sim.trajectory[-1].hox_posterior if sim.trajectory else 0.0
    out.anatomical.append(PhenotypeProperty(
        "anatomical", "predicted_primary_axis_identity", value, None,
        "posterior_third", "t_end", 0.3, "digital_twin_reduced_order",
    ))
    out.anatomical.append(PhenotypeProperty(
        "anatomical", "predicted_tail_count",
        "1" if value == "tail" else "0", None,
        "axis", "t_end", 0.3, "axis_initiation_count",
    ))
    out.molecular.append(PhenotypeProperty(
        "molecular", "predicted_posterior_hox", f"{last_hox:.3f}", "au",
        "posterior", "t_end", 0.35, "digital_twin_reduced_order",
    ))
    return out


def geometry_from_sim(sim: SimulationResult) -> GeometryIr:
    last = sim.trajectory[-1] if sim.trajectory else None
    points = []
    if last:
        for i in range(11):
            x = i / 10.0
            label = "posterior" if x > 0.66 else "anterior" if x < 0.33 else "trunk"
            points.append(Point(x, 0.0, 0.0, label, f"tail_identity~{last.tail_identity * x:.2f}", last.time, 0.6))
    return GeometryIr(
        kind="PointCloud",
        topology="1d_axis",
        points=points,
        annotations=["schematic 1-D profile; not a calibrated length; y=z=0 by construction of this backend"],
    )
