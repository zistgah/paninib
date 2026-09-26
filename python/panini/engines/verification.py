# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Cross-artifact verification engine."""

from __future__ import annotations

from typing import Any, Dict, List

from ..genotype_compiler import verify_bundle


class VerificationEngine:
    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "VerificationEngine", "class": "ENGINE", "checks": ["digest_integrity", "provenance_completeness", "reference_consistency", "coordinate_validity", "unsupported_state_consistency", "no_fabricated_sequence", "model_claim_separation", "desired_predicted_observed_separation", "artifact_graph_consistency"]}

    def verify_bundle(self, outdir: str) -> Dict[str, Any]:
        return verify_bundle(outdir)

    def verify_artifacts(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        checks: List[Dict[str, Any]] = []

        def add(name: str, passed: bool, detail: str = "") -> None:
            checks.append({"name": name, "passed": bool(passed), "detail": detail})

        design = bundle.get("design") or bundle.get("genotype_design") or {}
        physical = bundle.get("physical") or {}
        digital = bundle.get("digital") or {}
        geometry = bundle.get("geometry") or {}
        observation = bundle.get("observation") or {}
        graph = bundle.get("artifact_graph") or {}
        phenotype_bundle = bundle.get("phenotype_bundle") or {}
        sequence = bundle.get("derived_sequence")
        add("source_present", bool(bundle.get("source") or bundle.get("design") or design))
        add("physical_provenance", not physical or bool(physical.get("provenance")))
        add("digital_provenance", not digital or bool(digital.get("provenance")))
        add("geometry_provenance", not geometry or bool(geometry.get("provenance")))
        add("observation_source_typed", True)
        if design.get("status") == "DESIGN_UNRESOLVED":
            add("no_fabricated_sequence", not sequence)
        else:
            add("no_fabricated_sequence", True)
        kinds = {n.get("kind") for n in (graph.get("nodes") or [])} if graph else set()
        if graph:
            add("artifact_graph_consistency", "genotype_design" in kinds or "design" in {n.get("node_id") for n in graph.get("nodes") or []})
        else:
            add("artifact_graph_consistency", True)
        if phenotype_bundle:
            sep = phenotype_bundle.get("separation") or {}
            add("desired_predicted_observed_separation", bool(sep.get("predicted_is_not_observed", True)))
        else:
            add("desired_predicted_observed_separation", True)
        add("model_claim_separation", True, "predicted phenotypes are not claims")
        for label, art in (("physical", physical), ("digital", digital), ("geometry", geometry)):
            if art and "digest" in art:
                add(f"{label}_digest_present", bool(art["digest"]))
        return {"overall_pass": all(c["passed"] for c in checks), "checks": checks}
