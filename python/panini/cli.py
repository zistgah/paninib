from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .debugger.session import DebugSession
from .errors import PaniniError
from .ontology import CISC_OPCODES, RISC_OPCODES, catalog
from .pipeline import CompileOptions, compile_source
from .simulator.api import Simulator, load_compile_payload
from .stdlib import SearchQuery, find
from .bundle import write_bundle
from .simulator.geometry_export import export_all
from .simulator.models import ModelParams


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="panini", description="PANINI genetic compiler platform")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("compile", help="compile a .panini source through every IR layer")
    c.add_argument("input")
    c.add_argument("-o", "--output")
    c.add_argument("--backend", default="mammalian_cell.developmental")
    c.add_argument("--model", default=None, help="registered execution model id")

    o = sub.add_parser("ontology", help="print CISC/RISC vocabulary")
    o.add_argument("--json", action="store_true")

    s = sub.add_parser("search", help="search the genetic standard library")
    s.add_argument("--organism")
    s.add_argument("--function")
    s.add_argument("--tissue")

    g = sub.add_parser("genotype", help="build a semantic genotype from a compile artifact")
    g_sub = g.add_subparsers(dest="gcmd", required=True)
    gb = g_sub.add_parser("build", help="emit compiled-genotype JSON")
    gb.add_argument("input")
    gb.add_argument("-o", "--output")

    sim = sub.add_parser("sim", help="execute a compiled genotype")
    sim_sub = sim.add_subparsers(dest="scmd", required=True)
    sr = sim_sub.add_parser("run", help="run G_compiled → Φ_digital")
    sr.add_argument("input", help=".panini source or .compile.json")
    sr.add_argument("-o", "--output", help="directory to write the run record")
    sr.add_argument("--seed", type=int, default=1)
    sr.add_argument("--until", type=float, default=None)
    sr.add_argument("--dt", type=float, default=None)
    sr.add_argument("--t-end", type=float, default=None)
    si = sim_sub.add_parser("inspect", help="inspect a saved run")
    si.add_argument("run")
    si.add_argument("path", nargs="?", default="phenotype")
    scp = sim_sub.add_parser("checkpoint", help="list checkpoints in a saved run")
    scp.add_argument("run")

    d = sub.add_parser("debug", help="biological debugger for a compile artifact or run")
    d.add_argument("input", help=".panini, .compile.json, or run directory")
    d.add_argument("-c", "--command", action="append", default=[], help="run debugger command (repeatable)")
    d.add_argument("--seed", type=int, default=1)

    b = sub.add_parser("bundle", help="write the v0.4 four-deliverable artifact bundle")
    b.add_argument("input")
    b.add_argument("-o", "--output", default="panini-bundle")
    b.add_argument("--seed", type=int, default=1)
    gex = sub.add_parser("geometry", help="export OBJ/STL/PLY from a compile artifact")
    gex.add_argument("input")
    gex.add_argument("-o", "--output", default="phenotype-geom")
    gex.add_argument("--model", default=None, help="execution model id (domain default if omitted)")

    ins = sub.add_parser("inspect", help="inspect a genotype-compiler artifact stage")
    ins.add_argument("bundle")
    ins.add_argument("--stage", default="manifest")

    ver = sub.add_parser("verify", help="verify a genotype-compiler output directory")
    ver.add_argument("bundle")

    isa = sub.add_parser("isa", help="dump versioned CISC semantic specifications")
    isa.add_argument("--opcode")

    kn = sub.add_parser("knowledge", help="inspect or search the knowledge substrate")
    kn.add_argument("query", nargs="?", default="")
    kn.add_argument("--kind")
    kn.add_argument("--id")

    res = sub.add_parser("resolution", help="print biological resolution artifacts from a compile payload")
    res.add_argument("input")
    res.add_argument("--section", default="report", help="report|diagnostics|work-orders|coverage|experimental-ir|graph")

    des = sub.add_parser("design", help="emit GenotypeDesign without executing backends")
    des.add_argument("input")
    des.add_argument("-o", "--output")

    rz = sub.add_parser("realize", help="physical realization mock from source or design JSON")
    rz.add_argument("input")
    rz.add_argument("-o", "--output")
    rz.add_argument("--sbol", action="store_true")

    val = sub.add_parser("validate", help="ingest an observation JSON into the validation registry")
    val.add_argument("input", help="observation JSON or fixture path")
    val.add_argument("--claim", default="claim:cli")
    val.add_argument("--status", default="OBSERVED")
    val.add_argument("--predicted")

    simu = sub.add_parser("simulate", help="alias for sim run")
    simu.add_argument("input")
    simu.add_argument("-o", "--output")
    simu.add_argument("--seed", type=int, default=1)
    simu.add_argument("--json", action="store_true")

    cov = sub.add_parser("coverage", help="emit machine-readable CISC/RISC coverage")
    cov.add_argument("--json", action="store_true")

    loop = sub.add_parser("feedback", help="observation → residual → knowledge-update (synthetic)")
    loop.add_argument("--predicted", type=float, default=0.8)
    loop.add_argument("--observed", type=float, default=0.5)

    args = p.parse_args(argv)
    if args.cmd == "compile":
        src = Path(args.input).read_text()
        from .genotype_compiler import (
            DesignStatus,
            compile_sequence_program,
            detect_source_kind,
            write_bundle as write_design_bundle,
        )
        if detect_source_kind(src) == "sequence_design":
            try:
                result = compile_sequence_program(src)
            except DesignStatus as e:
                print(str(e), file=sys.stderr)
                return 2
            dest = Path(args.output) if args.output else Path(args.input).with_suffix("").name + "-out"
            man = write_design_bundle(result, src, dest)
            print(json.dumps(man, indent=2, sort_keys=True))
            return 0 if man.get("status") in {"COMPILED", "COMPILED_WITH_WARNINGS", "DESIGN_UNRESOLVED"} else 1
        try:
            result = compile_source(src, CompileOptions(backend=args.backend, model=args.model))
        except PaniniError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(result.summary())
        dest = Path(args.output) if args.output else Path(args.input).with_suffix(".compile.json")
        dest.write_text(result.to_json())
        print(f"wrote {dest}", file=sys.stderr)
        verdict = result.payload.get("verdict", {})
        print(f"verdict compilation={verdict.get('compilation')} target={verdict.get('target_phenotype')} overall={verdict.get('overall')}", file=sys.stderr)
        return 0 if verdict.get("compilation") == "PASS" else 1
    if args.cmd == "ontology":
        if args.json:
            print(json.dumps({k: v.__dict__ for k, v in catalog().items()}, default=str, indent=2))
        else:
            print(f"Genetic CISC ({len(CISC_OPCODES)} ops):")
            for op in CISC_OPCODES:
                print(f"  {op}")
            print(f"\nGenetic RISC ({len(RISC_OPCODES)} ops):")
            for op in RISC_OPCODES:
                print(f"  {op}")
        return 0
    if args.cmd == "search":
        hits = find(SearchQuery(organism=args.organism, function=args.function, tissue=args.tissue))
        for a in hits:
            print(f"{a.id:<16} {a.kind:<18} {a.function:<24} {a.evidence.value}  {a.annotation}")
        return 0
    if args.cmd == "bundle":
        src = Path(args.input).read_text()
        info = write_bundle(src, Path(args.output), seed=args.seed)
        print(json.dumps(info, indent=2, default=str))
        return 0
    if args.cmd == "geometry":
        payload = load_compile_payload(args.input)
        params = ModelParams()
        params.model_id = args.model or (payload.get("execution_contract") or {}).get("model_id") or ""
        sim = Simulator(payload=payload, params=params, seed=1)
        run = sim.run()
        paths = export_all(Path(args.output), run.phenotype)
        print(json.dumps(paths, indent=2))
        return 0
    if args.cmd == "genotype":
        payload = load_compile_payload(args.input)
        simu = Simulator(payload=payload)
        simu.load_genotype(payload)
        gjson = {
            "program_id": simu.genotype.program_id,
            "organism": simu.genotype.organism,
            "chromosomes": simu.genotype.chromosomes,
            "genes": [
                {
                    "identity": g.identity,
                    "symbol": g.symbol,
                    "artifact_id": g.artifact_id,
                    "role": g.role,
                    "locus": g.locus.identity,
                    "sequence_ref": g.sequence_ref,
                    "source_cisc": g.source_cisc,
                    "source_risc": g.source_risc,
                    "source_micro": g.source_micro,
                    "source_intent": g.source_intent,
                }
                for g in simu.genotype.genes
            ],
            "provenance": simu.genotype.provenance,
            "note": simu.genotype.realization_note,
        }
        text = json.dumps(gjson, indent=2)
        if args.output:
            Path(args.output).write_text(text)
            print(f"wrote {args.output}", file=sys.stderr)
        else:
            print(text)
        return 0
    if args.cmd == "sim":
        return _sim_cmd(args)
    if args.cmd == "debug":
        return _debug_cmd(args)
    if args.cmd == "inspect":
        from .genotype_compiler import inspect_stage
        data = inspect_stage(args.bundle, args.stage)
        if isinstance(data, str):
            print(data)
        else:
            print(json.dumps(data, indent=2, sort_keys=True, default=str))
        return 0
    if args.cmd == "verify":
        from .genotype_compiler import verify_bundle
        report = verify_bundle(args.bundle)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report.get("overall_pass") else 1
    if args.cmd == "isa":
        from .isa_spec import isa_manifest, spec_for
        if args.opcode:
            spec = spec_for(args.opcode)
            if spec is None:
                print(f"unknown opcode {args.opcode}", file=sys.stderr)
                return 2
            print(json.dumps(spec.to_dict(), indent=2, sort_keys=True))
        else:
            man = isa_manifest()
            man.pop("opcodes", None)
            print(json.dumps(man, indent=2, sort_keys=True))
        return 0
    if args.cmd == "knowledge":
        from .knowledge import get_knowledge_registry
        reg = get_knowledge_registry()
        if args.id:
            rec = reg.resolve(args.id)
            print(json.dumps(rec.to_dict() if rec else None, indent=2, default=str))
            return 0 if rec else 1
        hits = reg.search(args.query or args.kind or "", limit=50)
        if args.kind:
            hits = [h for h in hits if h.kind == args.kind]
        for rec in hits:
            print(f"{rec.canonical_id:<42} {rec.kind:<22} {rec.evidence_status}")
        return 0
    if args.cmd == "resolution":
        path = Path(args.input)
        if path.is_dir():
            payload = json.loads((path / "compile.json").read_text() if (path / "compile.json").exists() else (path / "manifest.json").read_text())
        else:
            payload = json.loads(path.read_text())
        section = args.section.replace("_", "-")
        mapping = {
            "report": payload.get("biological_resolution") or payload,
            "diagnostics": payload.get("diagnostics"),
            "work-orders": payload.get("resolution_work_orders"),
            "coverage": payload.get("coverage"),
            "experimental-ir": payload.get("experimental_ir"),
            "graph": payload.get("constraint_graph"),
        }
        print(json.dumps(mapping.get(section, payload), indent=2, default=str))
        return 0
    if args.cmd == "design":
        src_path = Path(args.input)
        if src_path.suffix == ".json":
            payload = json.loads(src_path.read_text())
            design = payload.get("genotype_design") or payload
        else:
            from .core_v08 import design_from_source
            payload = design_from_source(src_path.read_text())
            design = payload.get("genotype_design") or payload
        text = json.dumps(design, indent=2, default=str)
        if args.output:
            Path(args.output).write_text(text)
            print(f"wrote {args.output}", file=sys.stderr)
        else:
            print(text)
        return 0
    if args.cmd == "realize":
        from .physical import default_physical_backend
        from .sbol_adapter import MinimalSbolAdapter
        src_path = Path(args.input)
        if src_path.suffix == ".json":
            payload = json.loads(src_path.read_text())
            design = payload.get("genotype_design") or payload
        else:
            from .core_v08 import design_from_source
            design = design_from_source(src_path.read_text()).get("genotype_design") or {}
        realization = default_physical_backend().realize(design)
        out = realization.to_dict()
        if args.sbol:
            out = {"realization": out, "sbol": MinimalSbolAdapter().export(out)}
        text = json.dumps(out, indent=2, default=str)
        if args.output:
            Path(args.output).write_text(text)
            print(f"wrote {args.output}", file=sys.stderr)
        else:
            print(text)
        return 0
    if args.cmd == "validate":
        from .observe import Observation
        from .validation import get_validation_registry
        raw = json.loads(Path(args.input).read_text())
        obs = Observation(
            observation_id=raw.get("observation_id") or "obs_cli",
            source=raw.get("source") or "MANUAL_ASSERTION",
            source_id=raw.get("source_id") or args.input,
            subject=raw.get("subject") or "unspecified",
            measurement=raw.get("measurement"),
            unit=raw.get("unit") or "",
            method=raw.get("method") or "cli",
            uncertainty=raw.get("uncertainty"),
            provenance=raw.get("provenance") or {},
        )
        reg = get_validation_registry()
        ev = reg.ingest_observation(obs, args.claim, method=obs.method)
        if args.predicted is not None:
            try:
                predicted = json.loads(args.predicted)
            except json.JSONDecodeError:
                predicted = args.predicted
            claim = reg.evaluate_against_prediction(args.claim, obs, predicted)
        else:
            claim = reg.transition(args.claim, args.status, ev, note="cli ingest")
        print(json.dumps({"observation": obs.to_dict(), "evidence": ev.to_dict(), "claim": claim.to_dict()}, indent=2))
        return 0
    if args.cmd == "simulate":
        payload = load_compile_payload(args.input)
        sim = Simulator(payload=payload, seed=args.seed)
        run = sim.run()
        record = {
            "run_id": run.run_id,
            "phenotype": run.phenotype,
            "verification": run.verification,
            "maturity": run.maturity,
        }
        if args.output:
            dest = Path(args.output)
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "simulate.json").write_text(json.dumps(record, indent=2, default=str))
        print(json.dumps(record, indent=2, default=str) if args.json else f"simulate {run.run_id} maturity={run.maturity}")
        return 0
    if args.cmd == "coverage":
        from .engines.cisc_coverage import cisc_coverage_report
        report = cisc_coverage_report()
        print(json.dumps(report, indent=2))
        return 0
    if args.cmd == "feedback":
        from .feedback import compute_residual, explicit_knowledge_update
        from .knowledge import KnowledgeRecord, reset_knowledge_registry
        from .observe import Observation
        obs = Observation(
            observation_id="obs_cli_feedback",
            source="SIMULATION",
            source_id="cli",
            subject="observable_C",
            measurement=args.observed,
            unit="fixture",
            method="cli",
        )
        residual = compute_residual(args.predicted, args.observed, domain="molecular", residual_id="res_cli")
        rec = KnowledgeRecord(
            canonical_id="evidence:cli:observable_C",
            namespace="session",
            name="observable_C",
            kind="Evidence",
            source="session",
            provenance="OBSERVATION",
            evidence_status="computational_prediction",
            attributes={"residual": residual.to_dict(), "observation": obs.to_dict()},
        )
        update = explicit_knowledge_update(rec, reason="cli feedback", residual_id=residual.residual_id)
        print(json.dumps({"observation": obs.to_dict(), "residual": residual.to_dict(), "update": update.to_dict()}, indent=2))
        return 0
    return 2


def _sim_cmd(args) -> int:
    from .simulator.run import SimulationRun

    if args.scmd == "run":
        sim = Simulator.from_path(args.input, seed=args.seed)
        if args.dt:
            sim.params.dt = args.dt
        if args.t_end:
            sim.params.t_end = args.t_end
        run = sim.run(until=args.until)
        ph = run.phenotype.get("anatomical", {})
        print(
            f"PANINI sim {run.run_id}\n"
            f"program {run.manifest.program_id}\n"
            f"events {len(run.events)} checkpoints {len(run.checkpoints)}\n"
            f"stage {run.terminal_state.get('stage')} t={run.terminal_state.get('time')}\n"
            f"primary_axis={ph.get('primary_axis')} tail_count={ph.get('tail_count')} "
            f"tail_length_mm={ph.get('tail_length_mm')}\n"
            f"verification overall={run.verification.get('overall_pass')} maturity={run.maturity}\n"
        )
        dest_dir = Path(args.output) if args.output else Path("runs")
        written = run.write(dest_dir)
        print(f"wrote {written}", file=sys.stderr)
        return 0 if run.verification.get("overall_pass") else 1
    if args.scmd == "inspect":
        run = SimulationRun.read(Path(args.run))
        if args.path == "phenotype":
            print(json.dumps(run.phenotype, indent=2, default=str))
        elif args.path == "manifest":
            print(json.dumps(run.manifest.__dict__, indent=2, default=str))
        elif args.path == "events":
            print(f"{len(run.events)} events")
            for ev in run.events[-12:]:
                print(f"{ev.get('event_id')} t={ev.get('timestamp')} {ev.get('operation')} {ev.get('notes')}")
        else:
            print(json.dumps(run.terminal_state, indent=2, default=str))
        return 0
    if args.scmd == "checkpoint":
        run = SimulationRun.read(Path(args.run))
        for cp in run.checkpoints:
            print(f"{cp['checkpoint_id']:<16} t={cp['timestamp']:<8} stage={cp['stage']:<16} events≤{cp['event_index']}")
        return 0
    return 2


def _debug_cmd(args) -> int:
    sim = Simulator.from_path(args.input, seed=args.seed)
    session = DebugSession(sim)
    if args.command:
        for cmd in args.command:
            out = session.exec(cmd)
            if out:
                print(out)
        return 0
    if sys.stdin.isatty():
        print("(panini-debug)")
        print(f"loaded {sim.genotype.program_id if sim.genotype else args.input}")
        print("type help")
        while session.running:
            try:
                line = input("> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            out = session.exec(line)
            if out:
                print(out)
        return 0
    for line in sys.stdin:
        out = session.exec(line)
        if out:
            print(out)
        if not session.running:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
