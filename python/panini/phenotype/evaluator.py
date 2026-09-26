from __future__ import annotations

from typing import Any, Dict, Optional

from .constraints import PhenotypeConstraintSet


def verify_target_phenotype(desired: PhenotypeConstraintSet, predicted: dict) -> dict:
    result = desired.evaluate(predicted)
    return {
        "level": "V12",
        "name": "target_phenotype_satisfaction",
        "passed": result["status"] == "SATISFIED",
        "status": result["status"],
        "constraints": result["all"],
        "failed_constraints": result["failed"],
        "unknown_constraints": result["unknown"],
        "detail": (
            "all required phenotype constraints satisfied"
            if result["status"] == "SATISFIED"
            else (
                f"{len(result['unknown'])} required constraints indeterminate"
                if result["status"] == "UNKNOWN"
                else f"{len(result['failed'])} required phenotype constraints failed"
            )
        ),
    }


def verify_uncertainty(desired: PhenotypeConstraintSet, predicted: dict) -> dict:
    """V13: conservative. UNKNOWN only if a prediction carries an explicit interval."""
    flagged = []
    for c in desired.constraints:
        if c.operator not in {"==", "approximately"}:
            continue
        node = predicted
        for part in f"{c.layer}.{c.property}".split("."):
            node = node.get(part) if isinstance(node, dict) else None
            if node is None:
                break
        if isinstance(node, dict) and "sigma" in node:
            flagged.append(c.id)
    return {
        "level": "V13",
        "name": "uncertainty_adequacy",
        "passed": True,
        "status": "UNKNOWN" if flagged else "NOT_EVALUATED",
        "detail": (
            "uncertainty propagation is not implemented; V13 is recorded as NOT_EVALUATED"
            if not flagged
            else f"interval present on {flagged} but not propagated"
        ),
    }


def verdict_bundle(
    compile_ok: bool,
    simulation_ok: bool,
    runtime_ok: bool,
    target_status: str,
) -> Dict[str, Any]:
    """Compilation ≠ execution ≠ target satisfaction ≠ biological validation."""
    target = target_status
    overall = "UNSATISFIED"
    if not compile_ok:
        overall = "COMPILE_FAIL"
    elif not simulation_ok:
        overall = "SIMULATION_FAIL"
    elif target == "SATISFIED" and runtime_ok:
        overall = "SATISFIED"
    elif target == "UNKNOWN":
        overall = "UNKNOWN"
    else:
        overall = "UNSATISFIED"
    return {
        "compilation": "PASS" if compile_ok else "FAIL",
        "simulation": "PASS" if simulation_ok else "FAIL",
        "runtime_verification": "PASS" if runtime_ok else "FAIL",
        "target_phenotype": target,
        "overall": overall,
        "invariants": [
            "Intent ≠ Genetic CISC ≠ Microcode ≠ ATGC ≠ Physical execution",
            "Desired Phenotype ≠ Predicted Phenotype ≠ Observed Phenotype",
            "Compilation Success ≠ Execution Success ≠ Target Satisfaction ≠ Biological Validation",
        ],
    }
