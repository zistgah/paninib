"""Forward and reverse causal tracing across compilation + execution."""

from __future__ import annotations

from typing import Any, Dict, List

from ..simulator.engine import ExecutionEngine
from ..simulator.events import Event
from ..simulator.genotype import CompiledGenotype


AXIAL_CHAIN = [
    ("genotype", "posteriorizing / identity loci"),
    ("transcription", "RNA of Wnt/FGF/RA/Cdx/Hox"),
    ("translation", "protein products"),
    ("molecular", "Wnt/FGF vs RA field"),
    ("regulation", "Cdx posterior program"),
    ("regulation", "posterior Hox code"),
    ("cellular", "NMPs / caudal progenitors"),
    ("tissue", "axis polarity / caudal extension"),
    ("developmental", "tail-bud / axis-extension stage"),
    ("anatomical", "primary axis identity / tail_count"),
    ("phenotype", "digital phenotype Φ"),
]


def explain_event(engine: ExecutionEngine, event_id: str) -> Dict[str, Any]:
    ev = engine.log.get(event_id)
    if ev is None:
        # allow integer / short forms
        if event_id.isdigit():
            ev = engine.log.get(f"E{int(event_id):06d}")
        if ev is None and not event_id.startswith("E"):
            ev = engine.log.get(f"E{event_id}")
    if ev is None:
        raise KeyError(f"unknown event {event_id}")
    return {
        "physical_event": ev.to_plain(),
        "ancestry": {
            "microcode": ev.source_micro,
            "risc": ev.source_risc,
            "cisc": ev.source_cisc,
            "panini_intent": ev.source_intent,
        },
        "chain": [
            "PANINI source intent",
            "CISC " + (", ".join(ev.source_cisc) or "(unbound)"),
            "RISC " + (", ".join(ev.source_risc) or "(unbound)"),
            "microcode " + (", ".join(ev.source_micro) or "(unbound)"),
            f"physical {ev.operation} @{ev.timestamp:.2f}h",
        ],
    }


def trace_forward(genotype: CompiledGenotype, entity: str) -> Dict[str, Any]:
    g = genotype.gene(entity)
    label = g.artifact_id if g else entity
    nodes = [
        {"id": "gene", "label": label},
        {"id": "rna", "label": f"RNA({label})"},
        {"id": "protein", "label": f"Protein({label})"},
        {"id": "pathway", "label": _pathway_for(g.role if g else entity)},
        {"id": "signal", "label": "axial field / cell signal"},
        {"id": "cell", "label": "cell-state transition"},
        {"id": "tissue", "label": "tissue boundary / polarity"},
        {"id": "morph", "label": "morphogenesis"},
        {"id": "pheno", "label": "phenotype"},
    ]
    edges = [
        ("gene", "rna", "transcribes"),
        ("rna", "protein", "translates"),
        ("protein", "pathway", "participates"),
        ("pathway", "signal", "produces"),
        ("signal", "cell", "induces"),
        ("cell", "tissue", "aggregates"),
        ("tissue", "morph", "shapes"),
        ("morph", "pheno", "projects"),
    ]
    return {"entity": entity, "direction": "forward", "nodes": nodes, "edges": edges}


def trace_backward(engine: ExecutionEngine, entity: str) -> Dict[str, Any]:
    s = engine.state
    score = s.molecular["tail_identity"].value
    nodes = [
        {"id": "pheno", "label": f"phenotype {entity} (tail_count={s.anatomy.get('tail_count')}, score={score:.3f})"},
        {"id": "morph", "label": f"morphogenesis stage={s.stage}"},
        {"id": "tissue", "label": f"caudal_extension={s.tissue.get('caudal_extension')}"},
        {"id": "cell", "label": f"cells={len(s.cells)} caudal={sum(1 for c in s.cells if c.cell_type in {'nmps','somite'})}"},
        {"id": "signal", "label": f"Wnt={s.molecular['wnt'].value:.3f} RA={s.molecular['ra'].value:.3f}"},
        {"id": "protein", "label": "Cdx/Hox protein state"},
        {"id": "rna", "label": "transcript state of identity program"},
        {"id": "reg", "label": "regulatory enablement of compiled loci"},
        {"id": "geno", "label": "compiled genotype / execution events"},
    ]
    edges = [
        ("pheno", "morph", "caused-by"),
        ("morph", "tissue", "caused-by"),
        ("tissue", "cell", "caused-by"),
        ("cell", "signal", "caused-by"),
        ("signal", "protein", "caused-by"),
        ("protein", "rna", "caused-by"),
        ("rna", "reg", "caused-by"),
        ("reg", "geno", "caused-by"),
    ]
    disabled = [g.identity for g in s.genes.values() if not g.enabled]
    why = []
    if s.anatomy.get("tail_count", 0) != 2:
        why.append("model produces a single primary axis, not a second tail; tail_count∈{0,1}")
    if score < 0.6:
        why.append("posterior Hox did not cross the tail-identity threshold")
    if disabled:
        why.append(f"disabled loci: {disabled}")
    last_dev = [e for e in engine.log.events if e.operation == "DEVELOP"]
    return {
        "entity": entity,
        "direction": "backward",
        "nodes": nodes,
        "edges": edges,
        "residual": why,
        "last_developmental_event": last_dev[-1].event_id if last_dev else None,
        "chain_text": " → ".join(n["label"] for n in reversed(nodes)),
    }


def _pathway_for(role: str) -> str:
    if "posteriorizing" in (role or ""):
        return "Wnt/FGF posteriorizing pathway"
    if "anterior" in (role or ""):
        return "RA anteriorizing countergradient"
    if "identity" in (role or ""):
        return "Cdx/Hox posterior identity program"
    return "axial patterning network"


def compare_states(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Typed phenotype / state diff."""
    def walk(x, y, prefix=""):
        out = []
        if isinstance(x, dict) and isinstance(y, dict):
            keys = sorted(set(x) | set(y))
            for k in keys:
                out.extend(walk(x.get(k), y.get(k), f"{prefix}.{k}" if prefix else k))
            return out
        if x != y:
            out.append({"path": prefix, "reference": x, "candidate": y})
        return out

    return {"deltas": walk(a, b)}
