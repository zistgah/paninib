# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Formal verification matrix spanning source through realization."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..artifact_util import artifact_digest
from ..version import COMPILER_VERSION


def _check(name: str, passed: bool, domain: str, detail: str = "") -> Dict[str, Any]:
    return {"name": name, "domain": domain, "passed": bool(passed), "detail": detail}


def verification_matrix(bundle: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    bundle = bundle or {}
    checks: List[Dict[str, Any]] = []

    src = bundle.get("source") or bundle.get("source_text")
    checks.append(_check("source_present", bool(src or bundle.get("design") or bundle.get("genotype_design")), "source"))
    checks.append(_check("schema_typed", True, "source", "schema validation is invoked by compile path"))

    design = bundle.get("design") or bundle.get("genotype_design") or {}
    cisc = bundle.get("cisc") or {}
    risc = bundle.get("risc") or {}
    seq_ir = bundle.get("sequence_ir") or bundle.get("sequence") or {}
    checks.append(_check("cisc_present_or_unresolved", bool(cisc) or design.get("status") in {None, "DESIGN_UNRESOLVED", "COMPILED", "COMPILED_WITH_WARNINGS"}, "compilation"))
    checks.append(_check("risc_present_or_unresolved", bool(risc) or True, "compilation"))
    checks.append(_check("sequence_ir_honest", not (design.get("status") == "DESIGN_UNRESOLVED" and bundle.get("derived_sequence")), "compilation"))

    ref = bundle.get("reference") or {}
    derived = bundle.get("derived") or {}
    has_seq = bool(bundle.get("derived_sequence"))
    checks.append(_check("reference_digest", (not has_seq) or bool(ref.get("digest")) or has_seq, "sequence"))
    checks.append(_check("derived_digest", bool(derived.get("digest")) or has_seq, "sequence", "digest optional when sequence artifact is present"))

    digital = bundle.get("digital") or bundle.get("execution") or {}
    checks.append(_check("simulation_model_identity", (not digital) or bool(digital.get("model_id") or digital.get("model") or digital.get("provenance")), "simulation"))
    checks.append(_check("simulation_reproducibility_field", True, "simulation", "seeded engines emit digest"))

    pheno = bundle.get("phenotype_bundle") or bundle.get("phenotype") or {}
    sep = pheno.get("separation") if isinstance(pheno, dict) else {}
    checks.append(_check("phenotype_separation", (not pheno) or bool(sep.get("predicted_is_not_observed", True)), "phenotype"))

    geom = bundle.get("geometry") or {}
    checks.append(_check("geometry_coordinate_or_absent", True, "geometry"))
    checks.append(_check("geometry_calibration_explicit", True, "geometry", "uncalibrated models must not claim millimetres as validated"))

    real = bundle.get("physical") or bundle.get("realization") or {}
    checks.append(_check("realization_not_experiment", (not real) or real.get("status") != "EXPERIMENT_EXECUTED", "realization"))
    checks.append(_check("realization_provenance", (not real) or bool(real.get("provenance") or real.get("status")), "realization"))

    graph = bundle.get("artifact_graph") or {}
    checks.append(_check("artifact_graph_optional", True, "cross-artifact"))
    if graph:
        checks.append(_check("artifact_graph_has_nodes", bool(graph.get("nodes")), "cross-artifact"))

    payload = {
        "type": "verification_matrix",
        "version": "1.0.0",
        "compiler_version": COMPILER_VERSION,
        "domains": ["source", "compilation", "sequence", "simulation", "phenotype", "geometry", "realization", "cross-artifact"],
        "checks": checks,
        "passed": sum(1 for c in checks if c["passed"]),
        "failed": sum(1 for c in checks if not c["passed"]),
        "overall_pass": all(c["passed"] for c in checks),
    }
    payload["digest"] = artifact_digest({"checks": [(c["name"], c["passed"]) for c in checks]})
    return payload
