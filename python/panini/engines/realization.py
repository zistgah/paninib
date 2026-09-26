# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Realization planning engine. Labs remain adapters."""

from __future__ import annotations

from typing import Any, Dict, List

from ..artifact_util import artifact_digest, provenance_block, text_digest
from ..physical import LocalMockRealizationBackend, PhysicalRealization
from ..version import COMPILER_VERSION
from .reference import ReferenceGenomeEngine
from .sequence import SequenceEngine


class RealizationPlanningEngine:
    def __init__(self) -> None:
        self.seq = SequenceEngine()
        self.ref = ReferenceGenomeEngine()
        self.physical = LocalMockRealizationBackend()

    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "RealizationPlanningEngine", "class": "ENGINE", "stages": ["planning", "packaging", "verification", "physical_execution"], "physical_execution": "adapter_boundary", "laboratory_vendor": False, "scientific_model": False}

    def plan(self, genotype_design: Dict[str, Any]) -> Dict[str, Any]:
        design_id = str(genotype_design.get("design_id") or "gd_unknown")
        status = str(genotype_design.get("status") or "DESIGN_UNRESOLVED")
        edits_raw = list(genotype_design.get("edits") or [])
        assembly = str(genotype_design.get("assembly") or "")
        reference = str(genotype_design.get("reference") or "")
        issues: List[str] = []
        derived = None
        resolved_ref = None
        try:
            if assembly and reference:
                resolved_ref = self.ref.resolve_sequence(assembly, reference)
                self.ref.verify_digest(resolved_ref, resolved_ref.digest)
        except Exception as exc:
            issues.append(f"reference: {exc}")
        normalized = []
        try:
            normalized = self.seq.normalize_edits(edits_raw)
            self.seq.validate_coordinates(normalized, length=getattr(resolved_ref, "length", 10**9))
            if self.seq.overlaps(normalized):
                issues.append("overlapping edits")
        except Exception as exc:
            issues.append(f"edits: {exc}")
        if resolved_ref is not None and normalized and status not in {"DESIGN_UNRESOLVED", "INVALID_EDIT", "INVALID_PROGRAM"}:
            try:
                derived = self.seq.apply(resolved_ref, normalized)
            except Exception as exc:
                issues.append(f"apply: {exc}")
        plan_status = "PLANNED" if derived is not None and not issues else "PLAN_UNAVAILABLE"
        if status in {"INVALID_PROGRAM", "INVALID_EDIT", "REFERENCE_MISMATCH"}:
            plan_status = "PLAN_INVALID"
        artifact = {
            "plan_id": "rp_" + text_digest(design_id + plan_status)[:16], "design_id": design_id, "status": plan_status,
            "assembly": assembly, "reference": reference, "resolved_reference_digest": getattr(resolved_ref, "digest", None),
            "edits": [e.to_dict() if hasattr(e, "to_dict") else e for e in normalized],
            "derived_sequence": derived.sequence if derived else None, "derived_digest": derived.digest if derived else None,
            "qc_requirements": ["retrieval_digest_recomputed", "coordinate_validity", "no_invented_nucleotide_string", "authorization_gate", "edit_traceability"],
            "issues": issues, "checksums": {"design": text_digest(design_id), "edits": artifact_digest(edits_raw), "derived": derived.digest if derived else ""},
            "provenance": provenance_block(layer="realization.planning", compiler_version=COMPILER_VERSION, provider="panini.engines.realization", model_id="realize.plan", model_version="0.9.0", parent_digests={"design": text_digest(design_id)}),
            "note": "planning artifact; not wet-lab execution",
        }
        artifact["digest"] = artifact_digest({k: artifact[k] for k in ("plan_id", "status", "derived_digest", "edits")})
        return artifact

    def package(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        pkg = {"package_id": "pkg_" + plan["plan_id"][3:], "plan_id": plan["plan_id"], "constructs": [], "qc_requirements": list(plan.get("qc_requirements") or []), "checksums": dict(plan.get("checksums") or {})}
        if plan.get("derived_sequence"):
            pkg["constructs"].append({"construct_id": pkg["package_id"] + ":seq", "sequence": plan["derived_sequence"], "digest": plan.get("derived_digest")})
        pkg["digest"] = artifact_digest(pkg)
        return pkg

    def verify_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        checks = [
            {"name": "has_id", "passed": bool(plan.get("plan_id"))},
            {"name": "provenance", "passed": bool(plan.get("provenance"))},
            {"name": "not_wetlab", "passed": "not wet-lab" in str(plan.get("note", "")).lower()},
            {"name": "planned_has_seq", "passed": plan.get("status") != "PLANNED" or bool(plan.get("derived_sequence"))},
            {"name": "digest_present", "passed": bool(plan.get("digest"))},
        ]
        return {"overall_pass": all(c["passed"] for c in checks), "checks": checks}

    def realize_adapter(self, genotype_design: Dict[str, Any]) -> PhysicalRealization:
        return self.physical.realize(genotype_design)
