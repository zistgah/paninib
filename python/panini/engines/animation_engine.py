# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Animation engine consuming spatial / developmental trajectories."""

from __future__ import annotations

from typing import Any, Dict, List

from ..artifact_util import provenance_block, text_digest
from ..geometry_backend import AnimationArtifact, PhenotypeTrajectory
from ..version import COMPILER_VERSION


class AnimationEngine:
    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "AnimationEngine", "class": "ENGINE", "representation": ["json_frames", "gltf_min"], "renderer": False, "scientific_model": False}

    def provenance(self) -> Dict[str, Any]:
        return provenance_block(layer="animation", compiler_version=COMPILER_VERSION, provider="panini.engines.animation", model_id="traj.frames", model_version="0.9.0")

    def from_developmental(self, trajectory: List[Dict[str, Any]]) -> PhenotypeTrajectory:
        frames = [{"time": item.get("time", 0.0), "state": {"stage": item.get("stage"), "molecular": item.get("molecular_state"), "anatomical": item.get("anatomical_state")}, "geometry": item.get("geometry"), "phenotype": item.get("anatomical_state") or item.get("phenotype") or {}, "observation": None, "provenance": item.get("digest")} for item in trajectory]
        return PhenotypeTrajectory(trajectory_id="tr_" + text_digest(str(len(frames)))[:12], frames=frames, provenance=self.provenance())

    def from_maturation(self, frames_in: List[Dict[str, Any]]) -> PhenotypeTrajectory:
        frames = [{"time": item.get("time", 0.0), "state": item.get("state") or {"stage": item.get("stage")}, "geometry": item.get("geometry"), "phenotype": item.get("observables") or {}, "observation": item.get("observables"), "provenance": None} for item in frames_in]
        return PhenotypeTrajectory(trajectory_id="tr_" + text_digest("mat" + str(len(frames)))[:12], frames=frames, provenance=self.provenance())

    def animate(self, trajectory: PhenotypeTrajectory) -> AnimationArtifact:
        return AnimationArtifact(animation_id="an_" + trajectory.trajectory_id[3:], trajectory_id=trajectory.trajectory_id, frames=list(trajectory.frames), provenance=self.provenance())

    def export_gltf_min(self, trajectory: PhenotypeTrajectory) -> Dict[str, Any]:
        nodes = []
        for i, fr in enumerate(trajectory.frames):
            geom = fr.get("geometry") or {}
            nodes.append({"name": f"t{i}", "translation": [float(geom.get("axis_length") or i), 0.0, 0.0], "extras": {"time": fr.get("time"), "state": fr.get("state")}})
        return {"asset": {"version": "2.0", "generator": "panini.animation.gltf_min"}, "nodes": nodes, "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}], "extras": {"trajectory_id": trajectory.trajectory_id, "representation": "gltf_min"}}
