from __future__ import annotations

from typing import Any, Dict, List

from ..frontend import Program
from .constraints import PhenotypeConstraint, PhenotypeConstraintSet


def constraints_from_intents(program_id: str, program: Program) -> PhenotypeConstraintSet:
    """Infer typed target constraints from PANINI bindings. secondary=tail is not dropped."""
    cs: List[PhenotypeConstraint] = []
    n = 0

    def add(layer, prop, op, target, **kw):
        nonlocal n
        n += 1
        cs.append(PhenotypeConstraint(
            id=f"P{n:03d}", layer=layer, property=prop, operator=op, target=target, **kw,
        ))

    primary = secondary = None
    want_mature = False
    for intent in program.intents:
        if intent.name == "axial_pattern":
            primary = intent.bindings.get("primary")
            secondary = intent.bindings.get("secondary")
        if intent.verb == "reach_state" and intent.name == "mature":
            want_mature = True

    if primary:
        add("anatomical", "primary_axis", "==", primary, temporal_reference="mature")
    if secondary:
        add("anatomical", "secondary_axis", "==", secondary, temporal_reference="mature")

    tails = sum(1 for v in (primary, secondary) if v == "tail")
    heads = sum(1 for v in (primary, secondary) if v == "head")
    if tails:
        add("anatomical", "tail_count", "==", tails)
    elif primary == "head":
        add("anatomical", "tail_count", "==", 0)
    if heads and primary == "head":
        add("anatomical", "head_identity", "==", True)

    if want_mature:
        add("temporal", "matured", "==", True)

    return PhenotypeConstraintSet(program_id, cs)


def compare_phenotypes(desired: Dict[str, Any], observed: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    def walk(d, o, prefix=""):
        if isinstance(d, dict) and isinstance(o, dict):
            for k in sorted(set(d) | set(o)):
                walk(d.get(k), o.get(k), f"{prefix}.{k}" if prefix else k)
            return
        rec: Dict[str, Any] = {"desired": d, "observed": o, "match": d == o}
        try:
            rec["delta"] = float(o) - float(d)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            rec["delta"] = None
        out[prefix] = rec

    walk(desired, observed)
    return out
