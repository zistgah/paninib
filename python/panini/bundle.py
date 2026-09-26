# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Write the four v0.4 deliverables plus the provenance graph."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from .execution_contract import make_contract
from .frontend import parse_source
from .ir import to_plain
from .phenotype import constraints_from_intents
from .pipeline import COMPILER_VERSION, CompileOptions, compile_source
from .retrieval import load_all, to_genbank
from .simulator.api import Simulator
from .simulator.geometry_export import export_all
from .simulator.models import ModelParams


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_bundle(source: str, out: Path, seed: int = 1) -> Dict[str, Any]:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    program = parse_source(source)

    from .registry import get_registry
    parsed = program
    org = get_registry().resolve_organism(parsed.organism)
    if org is None:
        raise RuntimeError("bundle requires a registered organism plugin")
    one_id = org.default_model_id
    two_id = None
    for desc in get_registry().list_models():
        if desc.package == org.package and desc.implemented and desc.spatial_dimension >= 2:
            two_id = desc.id
            break
    if not one_id or not two_id:
        raise RuntimeError("bundle requires a 1-D default model and a multi-axis model in the domain plugin")
    one = compile_source(source, CompileOptions(model=one_id))
    two = compile_source(source, CompileOptions(model=two_id))

    (out / "compile_1d.json").write_text(one.to_json())
    (out / "compile_2axis.json").write_text(two.to_json())

    # --- genomic / realization ---
    gen_dir = out / "genome"
    gen_dir.mkdir(exist_ok=True)
    seqs = load_all()
    manifest = {
        "copyright": "Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.",
        "assembly": (get_registry().genome_for_organism(parsed.organism).assembly
                     if get_registry().genome_for_organism(parsed.organism) else None),
        "assembly_accession": (
            get_registry().genome_for_organism(parsed.organism).assembly_accession
            if get_registry().genome_for_organism(parsed.organism) else None
        ),
        "taxon": {"name": org.taxon_name, "id": org.taxon_id},
        "artifact_class": "REFERENCE_LOCUS_PACK",
        "authorization": {"authorized": False, "scope": "specification_only"},
        "designed_constructs": [],
        "before": "GRCm39 reference loci as retrieved",
        "after": "no sequence edit authored; designed genomic state is specification-only",
        "loci": {},
        "note": (
            "A two-tail developmental intent is not a synthesizable whole-genome rewrite. "
            "This pack is the retrieved reference state the twin executes against. "
            "Laboratory synthesis is not authorised."
        ),
        "references": [
            "https://www.ncbi.nlm.nih.gov/assembly/GCF_000001635.27",
            "https://www.informatics.jax.org/",
            "https://eutils.ncbi.nlm.nih.gov/",
        ],
    }
    for symbol, rec in seqs.items():
        fa = gen_dir / f"{symbol}.fa"
        gb = gen_dir / f"{symbol}.gb"
        fa.write_text(Path(rec.path).read_text())
        gb.write_text(to_genbank(rec, f"PANINI_{symbol}"))
        manifest["loci"][symbol] = {
            "header": rec.header,
            "sha256": rec.sha256,
            "length": len(rec.sequence),
            "source_url": rec.source_url,
            "fasta": str(fa.name),
            "genbank": str(gb.name),
            "class": "REFERENCE_LOCUS",
        }
    (gen_dir / "designed_state.json").write_text(json.dumps({
        "class": "DESIGNED_GENOMIC_STATE",
        "authorized": False,
        "modifications": [],
        "reason": "No nucleotide-level edit is implied by primary=tail secondary=tail. The request is a developmental pattern, not a sequence substitution.",
    }, indent=2))
    (gen_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))

    # --- twins ---
    twin_dir = out / "twin"
    twin_dir.mkdir(exist_ok=True)
    runs = {}
    for label, payload, mid in (
        ("1d", one.payload, one_id),
        ("2axis", two.payload, two_id),
    ):
        params = ModelParams()
        params.model_id = mid
        sim = Simulator(payload=payload, params=params, seed=seed)
        run = sim.run()
        rec = {
            "run_id": run.run_id,
            "model": mid,
            "phenotype": run.phenotype,
            "verification": run.verification,
            "n_events": len(run.events),
            "axes": (run.phenotype.get("anatomical") or {}),
        }
        (twin_dir / f"run_{label}.json").write_text(json.dumps(rec, indent=2, default=str))
        runs[label] = rec

        # animation frames
        frames = []
        for t in [1.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0]:
            s = Simulator(payload=payload, params=params, seed=seed)
            s.run(until=t)
            ph = s.engine.state.phenotype_projection()
            frames.append({"t": t, "stage": s.engine.state.stage, "anatomical": ph["anatomical"],
                           "axes": s.engine.state.anatomy.get("axes", [])})
        (twin_dir / f"frames_{label}.json").write_text(json.dumps({
            "copyright": "Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.",
            "model": mid, "frames": frames,
        }, indent=2))

    # --- geometry ---
    geo = {}
    for label in ("1d", "2axis"):
        gdir = out / "phenotype" / label
        ph = {
            "anatomical": runs[label]["phenotype"]["anatomical"],
            "axes": (runs[label]["phenotype"].get("anatomical") or {}).get("axes")
            or (two.payload.get("predicted_bundle") if label == "2axis" else {}),
        }
        # pull axes from twin frames last
        last_axes = json.loads((twin_dir / f"frames_{label}.json").read_text())["frames"][-1]["axes"]
        ph["axes"] = last_axes
        geo[label] = export_all(gdir, ph)

    # --- verification bundle ---
    ver = {
        "copyright": "Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.",
        "one_axis": {
            "verdict": one.payload.get("verdict"),
            "target": one.payload.get("target"),
            "internal_validity_pass": one.payload.get("verification", {}).get("internal_validity_pass"),
        },
        "two_axis": {
            "verdict": two.payload.get("verdict"),
            "target": two.payload.get("target"),
            "runtime_phenotype": runs["2axis"]["phenotype"]["anatomical"],
        },
        "states": ["COMPILED", "EXECUTABLE", "RUNTIME-VALID", "TARGET-SATISFIED", "EXPERIMENTALLY-VALIDATED"],
        "experimentally_validated": False,
    }
    (out / "verification.json").write_text(json.dumps(ver, indent=2, default=str))

    graph = {
        "copyright": "Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.",
        "compiler": COMPILER_VERSION,
        "core_version": COMPILER_VERSION,
        "domain_package": org.package,
        "model_1d": one_id,
        "model_multi_axis": two_id,
        "biological_data_version": (
            get_registry().genome_for_organism(parsed.organism).data_version
            if get_registry().genome_for_organism(parsed.organism) else None
        ),
        "reference_assembly": (
            get_registry().genome_for_organism(parsed.organism).assembly
            if get_registry().genome_for_organism(parsed.organism) else None
        ),
        "nodes": [
            {"id": "source", "kind": "panini"},
            {"id": "constraints", "kind": "phenotype_constraints"},
            {"id": "cisc", "kind": "genetic_cisc"},
            {"id": "risc", "kind": "candidate_genetic_risc"},
            {"id": "micro", "kind": "microcode"},
            {"id": "genome", "kind": "reference_locus_pack"},
            {"id": "twin_1d", "kind": "digital_twin"},
            {"id": "twin_2axis", "kind": "digital_twin"},
            {"id": "geometry", "kind": "phenotype_mesh"},
            {"id": "verify", "kind": "verification"},
        ],
        "edges": [
            ["source", "constraints"], ["source", "cisc"], ["cisc", "risc"],
            ["risc", "micro"], ["source", "genome"], ["cisc", "twin_1d"],
            ["cisc", "twin_2axis"], ["twin_2axis", "geometry"], ["twin_1d", "verify"],
            ["twin_2axis", "verify"], ["constraints", "verify"],
        ],
        "files": {p.name: _sha_file(p) for p in out.rglob("*") if p.is_file() and p.suffix != ".pyc"},
    }
    (out / "PROVENANCE.json").write_text(json.dumps(graph, indent=2))
    (out / "README.md").write_text(
        "# PANINI v0.4 artifact bundle\n\n"
        "Copyright © 1993–2026 Abhishek Choudhary. All rights reserved. · AyeAI\n\n"
        "genome/     retrieved GRCm39 loci (REFERENCE_LOCUS)\n"
        "twin/       1-D and 2-axis runs + maturation frames\n"
        "phenotype/  OBJ/STL/PLY for each model\n"
        "verification.json   COMPILED / EXECUTABLE / target / not experimentally validated\n"
        "PROVENANCE.json     artifact graph\n\n"
        "authorization.authorized = false. Not a synthesis order.\n"
    )
    return {
        "out": str(out),
        "verdict_1d": one.payload.get("verdict"),
        "verdict_2axis": two.payload.get("verdict"),
        "runtime_2axis_tails": runs["2axis"]["phenotype"]["anatomical"].get("tail_count"),
        "geometry": geo,
    }
