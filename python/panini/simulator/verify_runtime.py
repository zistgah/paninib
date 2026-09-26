"""Runtime verification layers V0–V11. Compiled ≠ biologically validated."""

from __future__ import annotations

from typing import Any, Dict, List

from .engine import ExecutionEngine
from .state import BiologicalState


def verify_runtime(engine: ExecutionEngine, desired: Dict[str, Any] | None = None) -> Dict[str, Any]:
    s: BiologicalState = engine.state
    items: List[Dict[str, Any]] = []

    def check(level: str, name: str, ok: bool, detail: str) -> None:
        items.append({"level": level, "name": name, "passed": bool(ok), "detail": detail})

    check("V0", "syntax", True, "engine accepted compiled genotype")
    check("V1", "type", bool(s.genes), f"{len(s.genes)} typed gene states")
    check("V2", "semantic", bool(engine.genotype.genes), "semantic genotype present")
    check("V3", "genotype_validity", all(
            (g.sequence_ref.startswith("mgi://") or g.sequence_ref.startswith("stdlib://"))
            and "ATGC" not in (g.sequence_ref or "")
            for g in engine.genotype.genes
        ) if engine.genotype.genes else False,
          "loci are retrieved reference records, not invented sequences")
    check("V4", "molecular_validity", all(q.value >= -1e-9 for q in s.protein.values()),
          "protein abundances non-negative")
    check("V5", "regulatory_validity", any(g.enabled for g in s.genes.values()) if s.genes else True,
          "at least one locus enabled" if s.genes else "no loci")
    check("V6", "cellular_validity", all(c.volume > 0 for c in s.cells) and bool(s.cells),
          f"{len(s.cells)} cells with positive volume")
    check("V7", "developmental_validity", s.stage in {
        "early_streak", "late_streak", "tail_bud", "axis_extension", "mature", "indeterminate", "gastrula",
    }, f"stage={s.stage}")
    declared_tails = None
    if desired and desired.get("anatomical") and "tail_count" in desired["anatomical"]:
        declared_tails = desired["anatomical"]["tail_count"]
    observed_tails = s.anatomy.get("tail_count", 0)
    if declared_tails is None:
        check("V8", "anatomical_validity", observed_tails in (0, 1, 2), f"tail_count={observed_tails} (no declared target)")
    else:
        check("V8", "anatomical_validity", observed_tails == declared_tails,
              f"declared tail_count={declared_tails} observed={observed_tails}")
    energy = s.molecular.get("energy")
    check("V9", "physiological_validity", energy is None or energy.value > 0, "energy state positive")
    score = s.molecular.get("tail_identity")
    score_v = score.value if score else 0.0
    want_primary = None
    if desired and desired.get("anatomical"):
        want_primary = desired["anatomical"].get("primary_axis") or desired["anatomical"].get("primary")
    observed_primary = s.anatomy.get("primary_axis")
    if want_primary:
        check("V10", "phenotype_validity", observed_primary == want_primary,
              f"declared primary={want_primary} observed={observed_primary} tail_identity={score_v:.3f}")
    else:
        check("V10", "phenotype_validity", True, f"no declared primary; tail_identity={score_v:.3f}")
    check("V11", "longitudinal_stability", engine.state.step > 5 and len(engine.log) > 5,
          f"steps={engine.state.step} events={len(engine.log)}")

    failed = [i for i in items if not i["passed"]]
    return {
        "passed": [i for i in items if i["passed"]],
        "failed": failed,
        "overall_pass": not failed,
        "compiled_true_is_not_biologically_validated": True,
        "maturity": "DT-3" if s.stage in {"tail_bud", "axis_extension", "mature"} else "DT-2",
    }
