# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Vertical integration slices for v0.9 engines."""

from __future__ import annotations

from typing import Any, Dict

from ..artifact_graph import ArtifactGraph
from ..artifact_util import artifact_digest, text_digest
from ..constraint_graph import ConstraintGraph, ConstraintNode, GraphEdge
from ..fixtures_v08 import CASE_SOURCES
from ..frontend import parse_source
from ..physical import LocalMockRealizationBackend
from ..resolution import compile_intent_genotype
from .animation_engine import AnimationEngine
from .biochemical import BiochemicalEngine, fixture_abc
from .coverage import coverage_from_resolution_payload
from .developmental import DevelopmentalEngine
from .geometry_engine import MeshEngine, ParametricGeometryEngine, PointCloudEngine, VoxelEngine
from .phenotype_engine import PhenotypeEngine
from .realization import RealizationPlanningEngine
from .solver import ConstraintSolver
from .trace import ArtifactDebugger
from .verification import VerificationEngine


def _graph_from_design(payload: Dict[str, Any]) -> ConstraintGraph:
    raw = payload.get("constraint_graph") or {}
    g = ConstraintGraph(program_id=str(payload.get("program_id") or "vertical"))
    for n in raw.get("nodes") or []:
        g.add_node(ConstraintNode(constraint_id=n["constraint_id"], status=n.get("status", "UNRESOLVED"), intent_name=n.get("intent_name", ""), required_provider=n.get("required_provider")))
    for e in raw.get("edges") or []:
        try:
            g.add_edge(GraphEdge(source=e["source"], target=e["target"], kind=e["kind"], note=e.get("note", "")))
        except Exception:
            continue
    if not g.nodes:
        br = payload.get("biological_resolution") or {}
        for c in br.get("constraints") or []:
            g.add_node(ConstraintNode(constraint_id=c.get("constraint_id", "c"), status=c.get("status", "UNRESOLVED"), intent_name=c.get("intent_name", "")))
    g.classify()
    g.compute_order()
    return g


def digital_vertical_slice() -> Dict[str, Any]:
    src = CASE_SOURCES["case1_direct"]
    payload = compile_intent_genotype(src, parse_source(src))
    design = payload.get("genotype_design") or {}
    bio = BiochemicalEngine(fixture_abc(k1=1.0, k2=0.5, a0=1.0))
    traj = bio.integrate(dt=0.05, t_end=2.0, seed=1, genotype={"design_id": design.get("design_id")}, regulatory={"k1": 1.0})
    mol_obs = bio.final_observables(traj)
    dev = DevelopmentalEngine().run_spatial_fixture(steps=8, dt=0.05)
    pheno = PhenotypeEngine()
    spatial_pred = pheno.from_developmental(dev["final"], kind="predicted")
    desired = pheno.desired({"observable_C": "present", "pattern": "any"})
    bundle_pheno = pheno.bundle(desired=desired.values, predicted=spatial_pred)
    axis = ParametricGeometryEngine().from_phenotype_params({"tail_count": 1, "length": 1.0, "radius": 0.05})
    points = ParametricGeometryEngine().sample_points(axis)
    cloud = PointCloudEngine().materialize(points, phenotype_ref=str(design.get("design_id")), spatial_ref="parametric")
    voxels = VoxelEngine().from_axis(axis)
    mesh = MeshEngine().from_axis(axis)
    anim_traj = AnimationEngine().from_developmental(dev["trajectory"])
    anim = AnimationEngine().animate(anim_traj)
    gltf = AnimationEngine().export_gltf_min(anim_traj)
    graph = ArtifactGraph(graph_id="ag_digital_v09")
    graph.add("source", "source", text_digest(src))
    graph.add("resolution", "resolution", artifact_digest(payload.get("biological_resolution") or {}))
    graph.add("design", "genotype_design", artifact_digest(design))
    graph.add("sequence", "sequence_ir", text_digest(str(payload.get("derived_sequence") or "")))
    graph.add("biochem", "biochemical", traj.to_dict()["digest"])
    graph.add("dev", "developmental", dev["digest"])
    graph.add("phenotype", "phenotype", bundle_pheno["digest"])
    graph.add("geometry", "geometry", cloud.to_dict()["digest"])
    graph.add("animation", "animation", anim.to_dict()["digest"])
    graph.link("source", "resolution", "lowers")
    graph.link("resolution", "design", "realizes")
    graph.link("design", "sequence", "edits")
    graph.link("design", "biochem", "parameterizes")
    graph.link("biochem", "dev", "feeds")
    graph.link("dev", "phenotype", "projects")
    graph.link("phenotype", "geometry", "embeds")
    graph.link("dev", "animation", "frames")
    trace = ArtifactDebugger().build_forward([
        {"layer": "intent", "id": "src", "digest": text_digest(src)},
        {"layer": "resolution", "id": "res", "digest": artifact_digest(payload.get("biological_resolution") or {})},
        {"layer": "design", "id": design.get("design_id"), "digest": artifact_digest(design)},
        {"layer": "sequence", "id": "seq", "digest": text_digest(str(payload.get("derived_sequence") or ""))},
        {"layer": "execution", "id": traj.trajectory_id, "digest": traj.to_dict()["digest"]},
        {"layer": "state", "id": "mol", "digest": text_digest(str(mol_obs))},
        {"layer": "phenotype", "id": "ph", "digest": bundle_pheno["digest"]},
    ])
    verify = VerificationEngine().verify_artifacts({"design": design, "digital": traj.to_dict(), "geometry": cloud.to_dict(), "phenotype_bundle": bundle_pheno, "artifact_graph": graph.to_dict(), "derived_sequence": payload.get("derived_sequence")})
    plan = ConstraintSolver().solve(_graph_from_design(payload))
    return {"slice": "digital_vertical", "source": src.strip(), "design": design, "resolution_status": payload.get("status"), "derived_sequence": payload.get("derived_sequence"), "biochemical_observables": mol_obs, "developmental_final": dev["final"], "phenotype_bundle": bundle_pheno, "geometry": {"point_cloud": cloud.to_dict(), "voxels": voxels.to_dict(), "mesh": mesh.to_dict()}, "animation": anim.to_dict(), "gltf_min": gltf, "coverage": coverage_from_resolution_payload(payload), "resolution_plan": plan.to_dict(), "artifact_graph": graph.to_dict(), "trace": ArtifactDebugger().explain(trace), "verification": verify}


def physical_vertical_slice() -> Dict[str, Any]:
    src = CASE_SOURCES["case1_direct"]
    payload = compile_intent_genotype(src, parse_source(src))
    design = payload.get("genotype_design") or {}
    planner = RealizationPlanningEngine()
    plan = planner.plan(design)
    pkg = planner.package(plan)
    vplan = planner.verify_plan(plan)
    physical = planner.realize_adapter(design)
    phys_v = LocalMockRealizationBackend().verify(physical)
    verify = VerificationEngine().verify_artifacts({"design": design, "physical": physical.to_dict(), "derived_sequence": payload.get("derived_sequence")})
    return {"slice": "physical_vertical", "design": design, "plan": plan, "package": pkg, "plan_verification": vplan, "physical": physical.to_dict(), "physical_verification": phys_v, "verification": verify}
