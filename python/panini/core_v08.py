# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""v0.8 dual-path orchestration: one GenotypeDesign feeds physical + digital."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .artifact_graph import build_dual_path_graph
from .artifact_util import artifact_digest, text_digest
from .digital import default_digital_backend, execution_ir_from_payload
from .frontend import parse_source
from .geometry_backend import default_animation_backend, default_geometry_backend
from .observe import Observation
from .physical import default_physical_backend
from .pipeline import CompileOptions, compile_source
from .resolution import compile_intent_genotype
from .sbol_adapter import MinimalSbolAdapter
from .validation import get_validation_registry
from .version import COMPILER_VERSION


def design_from_source(source: str) -> Dict[str, Any]:
    program = parse_source(source)
    return compile_intent_genotype(source, program)


def run_dual_path(
    source: str,
    *,
    compile_payload: Optional[Dict[str, Any]] = None,
    claim_id: str = "claim:dual",
) -> Dict[str, Any]:
    """Shared semantic design, separate physical and digital execution domains."""
    if compile_payload is None:
        try:
            compile_payload = compile_source(source, CompileOptions()).payload
        except Exception:
            compile_payload = None
    design_payload = design_from_source(source)
    design = design_payload.get("genotype_design") or {}
    physical = default_physical_backend().realize(design)
    sbol = MinimalSbolAdapter().export(physical.to_dict())

    digital_run = None
    geometry = None
    animation = None
    if compile_payload:
        eir = execution_ir_from_payload(compile_payload, design)
        digital_run = default_digital_backend().execute(eir, environment={"source": "fixture"}, options={"seed": 1})
        spatial = default_geometry_backend().project(digital_run.phenotype, phenotype_ref=design.get("design_id", ""))
        geometry = default_geometry_backend().materialize(spatial)
        traj = default_animation_backend().from_history(digital_run.state_history, digital_run.phenotype)
        animation = default_animation_backend().animate(traj)

    measurement = None
    if digital_run:
        anatomical = digital_run.phenotype.get("anatomical") or {}
        measurement = anatomical.get("tail_count", anatomical)
    observation = Observation(
        observation_id="obs_" + text_digest(design.get("design_id", "d"))[:12],
        source="SIMULATION" if digital_run else "MANUAL_ASSERTION",
        source_id=(digital_run.run_id if digital_run else design.get("design_id", "")),
        subject=design.get("phenotype_target") or "unspecified",
        measurement=measurement,
        method="digital_twin_projection",
        provenance={"design_id": design.get("design_id"), "compiler_version": COMPILER_VERSION},
    )
    registry = get_validation_registry()
    evidence = registry.ingest_observation(observation, claim_id, method="dual_path_ingest")
    claim = registry.transition(claim_id, "OBSERVED", evidence, note="ingested; not verified biology")

    graph = build_dual_path_graph(
        source_digest=text_digest(source),
        semantic_digest=artifact_digest(design_payload.get("semantic_ir") or {}),
        constraint_digest=artifact_digest(design_payload.get("biological_resolution", {}).get("constraints") or []),
        resolution_digest=artifact_digest(design_payload.get("biological_resolution") or {}),
        design_digest=artifact_digest(design),
        physical_digest=physical.to_dict()["digest"],
        execution_digest=digital_run.to_dict()["digest"] if digital_run else text_digest("none"),
        phenotype_digest=artifact_digest(digital_run.phenotype if digital_run else {}),
        geometry_digest=geometry.to_dict()["digest"] if geometry else text_digest("none"),
        observation_digest=observation.to_dict()["digest"],
        evidence_digest=evidence.to_dict()["digest"],
        claim_digest=artifact_digest(claim.to_dict()),
    )
    return {
        "compiler_version": COMPILER_VERSION,
        "design": design,
        "resolution": design_payload.get("biological_resolution"),
        "physical": physical.to_dict(),
        "sbol": sbol,
        "digital": digital_run.to_dict() if digital_run else None,
        "geometry": geometry.to_dict() if geometry else None,
        "animation": animation.to_dict() if animation else None,
        "observation": observation.to_dict(),
        "evidence": evidence.to_dict(),
        "claim": claim.to_dict(),
        "artifact_graph": graph.to_dict(),
        "shared": {
            "design_id": design.get("design_id"),
            "constraints": design.get("constraints"),
            "compiler_version": COMPILER_VERSION,
            "semantic_identity": artifact_digest(design_payload.get("semantic_ir") or {}),
        },
    }
