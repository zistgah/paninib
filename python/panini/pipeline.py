from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

from .version import COMPILER_NAME, COMPILER_VERSION, CORE_VERSION
from .backends import geometry_from_sim, phenotype_from_sim, plan_simulation, realize, run_simulation
from .errors import UnsupportedError
from .frontend import parse_source
from .ir import PassRecord, ProvenanceGraph, ir_hash, to_plain
from .lowering import analyze, cisc_to_risc, intent_to_cisc, risc_to_microcode
from .phenotype import constraints_from_intents, verdict_bundle, verify_target_phenotype
from .types import CapabilityIntersection, resolve_backend
from .verify import verify


INVARIANT = "Intent ≠ Genetic CISC ≠ Microcode ≠ ATGC ≠ Physical execution"


@dataclass
class CompileOptions:
    backend: str = "mammalian_cell.developmental"
    model: str | None = None


@dataclass
class CompileResult:
    payload: Dict[str, Any]

    @property
    def program_id(self) -> str:
        return self.payload["program_id"]

    @property
    def verification(self) -> Dict[str, Any]:
        return self.payload["verification"]

    def summary(self) -> str:
        p = self.payload
        v = p["verification"]
        return (
            f"PANINI compile {p['program_id']}\n"
            f"invariant: {p['invariant']}\n"
            f"CISC {len(p['cisc']['instructions'])} → RISC {len(p['risc']['instructions'])} → "
            f"μcode {len(p['microcode']['ops'])}\n"
            f"backend {p['capability']['backend']} (sufficient={p['capability']['sufficient']})\n"
            f"digital twin tail_identity={p['simulation_result']['terminal_phenotype_score']:.3f} "
            f"matured={p['simulation_result']['matured']}\n"
            f"realization modules={len(p['realization']['construct_specification'])} "
            f"(retrieved reference loci)\n"
            f"target {p.get('target', {}).get('status')} overall={p.get('verdict', {}).get('overall')}\n"
            f"verification passed={len(v['passed'])} failed={len(v['failed'])} "
            f"overall_pass={v['overall_pass']}\n"
        )

    def to_json(self) -> str:
        return json.dumps(self.payload, indent=2, default=str)


def compile_source(source: str, opts: CompileOptions | None = None) -> CompileResult:
    opts = opts or CompileOptions()
    program = parse_source(source)
    bio, causal, pheno_spec = analyze(program, source)

    backend_id = program.target_backend or opts.backend
    backend = resolve_backend(backend_id)

    cisc = intent_to_cisc(bio)
    required = sorted({cap for i in cisc.instructions for cap in i.required_capabilities})
    cap = CapabilityIntersection.resolve(required, backend)
    if not cap.sufficient:
        raise UnsupportedError(cap.missing, backend.id)

    risc = cisc_to_risc(cisc)
    micro = risc_to_microcode(risc, backend.id, program.organism)
    sim_plan = plan_simulation(bio)
    sim = run_simulation(sim_plan)
    predicted = phenotype_from_sim(pheno_spec, sim)
    geometry = geometry_from_sim(sim)
    realization = realize(cisc, micro, program.organism, bio)

    predicted_anatomy = {
        "primary_axis": "tail" if sim.terminal_phenotype_score > 0.6 else (
            "head" if sim.terminal_phenotype_score < 0.35 else "indeterminate"
        ),
        "secondary_axis": "absent",
        "tail_count": 1 if sim.terminal_phenotype_score > 0.6 else 0,
        "head_identity": sim.terminal_phenotype_score < 0.35,
    }
    predicted_bundle = {
        "anatomical": predicted_anatomy,
        "temporal": {"matured": sim.matured, "stage": "mature" if sim.matured else "indeterminate"},
        "molecular": {"hox_posterior": sim.trajectory[-1].hox_posterior if sim.trajectory else 0.0},
    }
    constraints = constraints_from_intents(bio.program_id, program)
    from .execution_contract import make_contract
    from .ir import to_plain as _plain
    contract = make_contract(bio.program_id, program, constraints, backend.id, opts.model)
    from .registry import get_registry
    exec_model = get_registry().get_execution(contract.model_id)
    predicted_bundle = exec_model.adjust_compile_preview(predicted_bundle, bio, sim)
    target = verify_target_phenotype(constraints, predicted_bundle)
    verification = verify(program, bio, cisc, risc, micro, cap, sim, backend, predicted_bundle, constraints)
    verdict = verdict_bundle(
        compile_ok=cap.sufficient,
        simulation_ok=bool(sim.trajectory),
        runtime_ok=not any(i.level in {"L0", "L1", "L2", "L3"} for i in verification.failed),
        target_status=target["status"],
    )

    def rec(name, inp, out):
        return PassRecord(name, ir_hash(inp), ir_hash(out), COMPILER_VERSION, [name], [], None)

    pass_pairs = [
        ("parse+semantic", program.source_summary(), bio),
        ("cisc-lowering", bio, cisc),
        ("risc-lowering", cisc, risc),
        ("microcode-lowering", risc, micro),
        ("simulation", sim_plan, sim),
        ("realization", cisc, realization),
        ("target-constraints", program.source_summary(), constraints),
    ]
    pass_records = [rec(*x) for x in pass_pairs]

    prov = ProvenanceGraph()
    for rec_i, (name, _inp, _out) in enumerate(pass_pairs):
        prov.add_node(name, "pass", f"{name} {pass_records[rec_i].output_hash[:12]}")
    for i in range(len(pass_pairs) - 1):
        prov.add_edge(pass_pairs[i][0], pass_pairs[i + 1][0], "feeds")
    prov.add_node("core", "core", f"PANINI Core {CORE_VERSION}")
    prov.add_node("domain", "domain", contract.domain_package or "unregistered")
    prov.add_node("model", "model", f"{contract.model_id}@{contract.model_version}")
    prov.add_node("data", "data", contract.data_version or "none")
    if contract.reference_assembly:
        prov.add_node("assembly", "reference_assembly", contract.reference_assembly)
    prov.add_node("evidence", "evidence", contract.evidence_version or "none")
    prov.add_edge("core", "domain", "hosts")
    prov.add_edge("domain", "model", "provides")
    prov.add_edge("domain", "data", "owns")
    prov.add_edge("domain", "evidence", "owns")

    from .resolution import compile_intent_genotype
    primary = next((i.bindings.get("primary") for i in bio.intents if i.name == "axial_pattern"), None)
    secondary = next((i.bindings.get("secondary") for i in bio.intents if i.name == "axial_pattern"), None)
    tails = sum(1 for v in (primary, secondary) if v == "tail")
    phenotype_target = f"tail_count={tails}" if tails else ";".join(f"{i.verb}:{i.name}" for i in bio.intents)
    genotype_design = compile_intent_genotype(
        source,
        program,
        program_id=bio.program_id,
        phenotype_target=phenotype_target,
        extra={
            "program_id": bio.program_id,
            "simulation_target": target.get("status"),
            "note": "simulation status and genotype-design status are independent",
        },
    )

    payload = {
        "compiler": COMPILER_NAME,
        "version": COMPILER_VERSION,
        "program_id": bio.program_id,
        "source_hash": bio.source_hash,
        "invariant": INVARIANT,
        "genotype_design": genotype_design["genotype_design"],
        "genotype_realization": {
            "status": genotype_design["status"],
            "phenotype_target": "known" if tails or bio.intents else "unknown",
            "genomic_realization": genotype_design.get("genomic_realization")
            or genotype_design["genotype_design"].get("genomic_realization", "unresolved"),
            "reason": genotype_design["genotype_design"]["reason"],
        },
        "biological_resolution": genotype_design.get("biological_resolution"),
        "diagnostics": genotype_design.get("diagnostics") or [],
        "resolution_work_orders": genotype_design.get("resolution_work_orders") or [],
        "experimental_ir": genotype_design.get("experimental_ir"),
        "coverage": genotype_design.get("coverage"),
        "resolved_constraints": genotype_design.get("resolved_constraints") or [],
        "unresolved_constraints": genotype_design.get("unresolved_constraints") or [],
        "invariants": verdict["invariants"],
        "universal": to_plain(bio),
        "causal": to_plain(causal),
        "cisc": to_plain(cisc),
        "risc": to_plain(risc),
        "microcode": to_plain(micro),
        "simulation_program": to_plain(sim_plan),
        "simulation_result": to_plain(sim),
        "desired_phenotype": to_plain(pheno_spec),
        "predicted_phenotype": to_plain(predicted),
        "predicted_bundle": predicted_bundle,
        "phenotype_constraints": to_plain(constraints),
        "target": target,
        "verdict": verdict,
        "geometry": to_plain(geometry),
        "realization": to_plain(realization),
        "verification": to_plain(verification),
        "provenance": to_plain(prov),
        "pass_records": [to_plain(p) for p in pass_records],
        "capability": to_plain(cap),
        "backend_id": backend.id,
        "execution_contract": {
            "model_id": contract.model_id,
            "reason": contract.reason,
            "status": contract.model_status,
            "need_multi_axis": contract.requirements.need_multi_axis,
            "domain_package": contract.domain_package,
            "model_version": contract.model_version,
            "data_version": contract.data_version,
            "evidence_version": contract.evidence_version,
            "reference_assembly": contract.reference_assembly,
            "core_version": contract.core_version,
        },
        "architecture": {
            "core_version": CORE_VERSION,
            "domain_package": contract.domain_package,
            "model_id": contract.model_id,
            "model_version": contract.model_version,
            "biological_data_version": contract.data_version,
            "reference_assembly": contract.reference_assembly,
            "evidence_version": contract.evidence_version,
        },
    }
    return CompileResult(payload)
