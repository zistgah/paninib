# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Spatial phenotype and temporal animation backend contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .artifact_util import artifact_digest, provenance_block, text_digest
from .version import COMPILER_VERSION


SUPPORTED_GEOMETRIES = (
    "point_cloud",
    "mesh",
    "voxels",
    "implicit_surface",
    "skeleton",
    "parametric",
    "spatial_field",
    "animation",
)


@dataclass
class SpatialPhenotype:
    spatial_id: str
    phenotype_ref: str
    representation: str
    coordinates: List[Dict[str, Any]]
    fields: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "spatial_id": self.spatial_id,
            "phenotype_ref": self.phenotype_ref,
            "representation": self.representation,
            "coordinates": list(self.coordinates),
            "fields": dict(self.fields),
            "provenance": dict(self.provenance),
        }
        payload["digest"] = artifact_digest(payload)
        return payload


@dataclass
class GeometryArtifact:
    geometry_id: str
    spatial_id: str
    kind: str
    payload: Dict[str, Any]
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "geometry_id": self.geometry_id,
            "spatial_id": self.spatial_id,
            "kind": self.kind,
            "payload": dict(self.payload),
            "provenance": dict(self.provenance),
        }
        data["digest"] = artifact_digest(data)
        return data


@dataclass
class PhenotypeTrajectory:
    trajectory_id: str
    frames: List[Dict[str, Any]]
    dt: float = 1.0
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "trajectory_id": self.trajectory_id,
            "frames": list(self.frames),
            "dt": self.dt,
            "provenance": dict(self.provenance),
        }
        payload["digest"] = artifact_digest(payload)
        return payload


@dataclass
class AnimationArtifact:
    animation_id: str
    trajectory_id: str
    frames: List[Dict[str, Any]]
    representation: str = "json_frames"
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "animation_id": self.animation_id,
            "trajectory_id": self.trajectory_id,
            "frames": list(self.frames),
            "representation": self.representation,
            "time": [f.get("time") for f in self.frames],
            "state": [f.get("state") for f in self.frames],
            "observation": [f.get("observation") for f in self.frames],
            "geometry": [f.get("geometry") for f in self.frames],
            "provenance": dict(self.provenance),
        }
        payload["digest"] = artifact_digest(payload)
        return payload


class GeometryBackend(Protocol):
    def capabilities(self) -> Dict[str, Any]: ...
    def project(self, phenotype: Dict[str, Any], phenotype_ref: str = "") -> SpatialPhenotype: ...
    def materialize(self, spatial: SpatialPhenotype) -> GeometryArtifact: ...
    def provenance(self) -> Dict[str, Any]: ...


class AnimationBackend(Protocol):
    def capabilities(self) -> Dict[str, Any]: ...
    def from_history(self, state_history: List[Dict[str, Any]], phenotype: Dict[str, Any]) -> PhenotypeTrajectory: ...
    def animate(self, trajectory: PhenotypeTrajectory) -> AnimationArtifact: ...
    def provenance(self) -> Dict[str, Any]: ...


class DeterministicGeometryBackend:
    def capabilities(self) -> Dict[str, Any]:
        return {
            "implemented": ["point_cloud", "spatial_field", "animation"],
            "declared_unimplemented": ["implicit_surface", "skeleton"],
            "implemented_elsewhere": ["mesh", "voxels", "parametric"],
            "calibrated": False,
        }

    def provenance(self) -> Dict[str, Any]:
        return provenance_block(
            layer="geometry",
            compiler_version=COMPILER_VERSION,
            provider="panini.geometry.fixture",
            model_id="schematic_axis",
            model_version="0.8.0",
        )

    def project(self, phenotype: Dict[str, Any], phenotype_ref: str = "") -> SpatialPhenotype:
        anatomical = phenotype.get("anatomical") or {}
        if not isinstance(anatomical, dict):
            anatomical = {"value": anatomical}
        tail = anatomical.get("tail_count", phenotype.get("tail_count", 1))
        try:
            tail_n = int(tail)
        except (TypeError, ValueError):
            tail_n = 1
        coords = []
        for i in range(11):
            x = i / 10.0
            label = "posterior" if x > 0.66 else "anterior" if x < 0.33 else "trunk"
            coords.append({"x": x, "y": 0.0, "z": 0.0, "label": label, "axis": 0})
        if tail_n >= 2:
            for i in range(11):
                x = i / 10.0
                coords.append({"x": x, "y": 0.4, "z": 0.0, "label": "secondary", "axis": 1})
        sid = "sp_" + text_digest(phenotype_ref + str(tail_n))[:12]
        return SpatialPhenotype(
            spatial_id=sid,
            phenotype_ref=phenotype_ref or "phenotype",
            representation="point_cloud",
            coordinates=coords,
            fields={"tail_count": tail_n, "anatomical": anatomical},
            provenance=self.provenance(),
        )

    def materialize(self, spatial: SpatialPhenotype) -> GeometryArtifact:
        return GeometryArtifact(
            geometry_id="geom_" + spatial.spatial_id[3:],
            spatial_id=spatial.spatial_id,
            kind="point_cloud",
            payload={
                "points": spatial.coordinates,
                "fields": spatial.fields,
                "topology": "schematic",
                "units": "uncalibrated_model_units",
            },
            provenance=self.provenance(),
        )


class DeterministicAnimationBackend:
    def capabilities(self) -> Dict[str, Any]:
        return {"representation": "json_frames", "calibrated": False}

    def provenance(self) -> Dict[str, Any]:
        return provenance_block(
            layer="animation",
            compiler_version=COMPILER_VERSION,
            provider="panini.animation.fixture",
            model_id="state_frames",
            model_version="0.8.0",
        )

    def from_history(self, state_history: List[Dict[str, Any]], phenotype: Dict[str, Any]) -> PhenotypeTrajectory:
        frames = []
        if not state_history:
            frames.append({"time": 0.0, "state": {"stage": "t0"}, "observation": None, "geometry": None, "phenotype": phenotype})
        for item in state_history:
            frames.append({
                "time": item.get("time", item.get("timestamp", 0.0)),
                "state": {"stage": item.get("stage"), "checkpoint_id": item.get("checkpoint_id")},
                "observation": None,
                "geometry": None,
                "phenotype": phenotype if item == state_history[-1] else {},
            })
        tid = "tr_" + text_digest(str(len(frames)) + str(phenotype)[:40])[:12]
        return PhenotypeTrajectory(trajectory_id=tid, frames=frames, provenance=self.provenance())

    def animate(self, trajectory: PhenotypeTrajectory) -> AnimationArtifact:
        return AnimationArtifact(
            animation_id="an_" + trajectory.trajectory_id[3:],
            trajectory_id=trajectory.trajectory_id,
            frames=list(trajectory.frames),
            provenance=self.provenance(),
        )


def default_geometry_backend() -> DeterministicGeometryBackend:
    return DeterministicGeometryBackend()


def default_animation_backend() -> DeterministicAnimationBackend:
    return DeterministicAnimationBackend()
