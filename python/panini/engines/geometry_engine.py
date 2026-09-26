# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Point cloud, voxel, parametric, and mesh geometry engines."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from ..artifact_util import provenance_block, text_digest
from ..geometry_backend import GeometryArtifact, SpatialPhenotype
from ..version import COMPILER_VERSION


@dataclass
class Axis:
    origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    direction: Tuple[float, float, float] = (1.0, 0.0, 0.0)
    length: float = 1.0
    radius: float = 0.05
    branching: List["Axis"] = field(default_factory=list)
    label: str = "axis"

    def to_dict(self) -> Dict[str, Any]:
        return {"origin": list(self.origin), "direction": list(self.direction), "length": self.length, "radius": self.radius, "label": self.label, "branching": [b.to_dict() for b in self.branching]}


def _norm(v):
    mag = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / mag, v[1] / mag, v[2] / mag)


def _add(a, b, s=1.0):
    return (a[0] + s * b[0], a[1] + s * b[1], a[2] + s * b[2])


class ParametricGeometryEngine:
    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "ParametricGeometryEngine", "class": "ENGINE", "scientific_model": False}

    def from_phenotype_params(self, params: Dict[str, Any]) -> Axis:
        n_axes = int(params.get("tail_count") or params.get("axes") or 1)
        length = float(params.get("length") or 1.0)
        radius = float(params.get("radius") or 0.05)
        root = Axis(length=length, radius=radius, label="primary")
        if n_axes >= 2:
            root.branching.append(Axis(origin=(0.0, 0.4, 0.0), direction=(1.0, 0.0, 0.0), length=length, radius=radius, label="secondary"))
        return root

    def sample_points(self, axis: Axis, n: int = 11) -> List[Dict[str, Any]]:
        pts: List[Dict[str, Any]] = []
        self._sample(axis, n, pts)
        return pts

    def _sample(self, axis: Axis, n: int, pts: List[Dict[str, Any]]) -> None:
        d = _norm(axis.direction)
        for i in range(n):
            t = i / max(1, n - 1)
            p = _add(axis.origin, d, t * axis.length)
            pts.append({"x": p[0], "y": p[1], "z": p[2], "label": axis.label, "radius": axis.radius})
        for b in axis.branching:
            self._sample(b, n, pts)

    def provenance(self) -> Dict[str, Any]:
        return provenance_block(layer="geometry.parametric", compiler_version=COMPILER_VERSION, provider="panini.engines.geometry", model_id="parametric.axis", model_version="0.9.0")


class PointCloudEngine:
    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "PointCloudEngine", "class": "ENGINE", "scientific_model": False}

    def materialize(self, points: List[Dict[str, Any]], *, phenotype_ref: str, spatial_ref: str) -> GeometryArtifact:
        payload = {"points": points, "units": "uncalibrated_model_units", "coordinate_system": "model_xyz", "model": "point_cloud.v09", "phenotype_ref": phenotype_ref, "spatial_ref": spatial_ref}
        return GeometryArtifact(geometry_id="pc_" + text_digest(phenotype_ref + str(len(points)))[:12], spatial_id=spatial_ref, kind="point_cloud", payload=payload, provenance=provenance_block(layer="geometry.point_cloud", compiler_version=COMPILER_VERSION, provider="panini.engines.geometry", model_id="point_cloud", model_version="0.9.0"))


class VoxelEngine:
    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "VoxelEngine", "class": "ENGINE", "scientific_model": False}

    def from_axis(self, axis: Axis, nx: int = 12, ny: int = 8, nz: int = 4) -> GeometryArtifact:
        voxels = []
        occupied = 0
        axes = [axis] + list(axis.branching)
        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    x, y, z = i / max(1, nx - 1), (j / max(1, ny - 1) - 0.5) * 0.8, (k / max(1, nz - 1) - 0.5) * 0.3
                    hit = False
                    for ax in axes:
                        d = _norm(ax.direction)
                        rel = (x - ax.origin[0], y - ax.origin[1], z - ax.origin[2])
                        t = max(0.0, min(ax.length, rel[0] * d[0] + rel[1] * d[1] + rel[2] * d[2]))
                        cx, cy, cz = _add(ax.origin, d, t)
                        dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2)
                        if dist <= ax.radius + 0.03:
                            hit = True
                            break
                    voxels.append({"i": i, "j": j, "k": k, "occ": 1 if hit else 0})
                    occupied += int(hit)
        payload = {"voxels": voxels, "grid": {"nx": nx, "ny": ny, "nz": nz}, "occupied": occupied, "units": "uncalibrated_model_units", "coordinate_system": "model_ijk", "model": "voxel.v09", "phenotype_ref": axis.label, "spatial_ref": "parametric"}
        return GeometryArtifact(geometry_id="vx_" + text_digest(str(occupied))[:12], spatial_id="parametric", kind="voxels", payload=payload, provenance=provenance_block(layer="geometry.voxels", compiler_version=COMPILER_VERSION, provider="panini.engines.geometry", model_id="voxel", model_version="0.9.0"))


class MeshEngine:
    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "MeshEngine", "class": "ENGINE", "scientific_model": False}

    def from_axis(self, axis: Axis, segments: int = 8, ring: int = 6) -> GeometryArtifact:
        verts: List[List[float]] = []
        faces: List[List[int]] = []
        self._tube(axis, segments, ring, verts, faces)
        for b in axis.branching:
            self._tube(b, segments, ring, verts, faces)
        payload = {"vertices": verts, "faces": faces, "units": "uncalibrated_model_units", "coordinate_system": "model_xyz", "model": "mesh.tube.v09", "phenotype_ref": axis.label, "spatial_ref": "parametric"}
        return GeometryArtifact(geometry_id="ms_" + text_digest(str(len(faces)))[:12], spatial_id="parametric", kind="mesh", payload=payload, provenance=provenance_block(layer="geometry.mesh", compiler_version=COMPILER_VERSION, provider="panini.engines.geometry", model_id="mesh.tube", model_version="0.9.0"))

    def _tube(self, axis: Axis, segments: int, ring: int, verts, faces) -> None:
        d = _norm(axis.direction)
        up = (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (0.0, 1.0, 0.0)
        px = _norm((d[1] * up[2] - d[2] * up[1], d[2] * up[0] - d[0] * up[2], d[0] * up[1] - d[1] * up[0]))
        py = _norm((d[1] * px[2] - d[2] * px[1], d[2] * px[0] - d[0] * px[2], d[0] * px[1] - d[1] * px[0]))
        base = len(verts)
        for s in range(segments + 1):
            t = s / segments
            center = _add(axis.origin, d, t * axis.length)
            for r in range(ring):
                ang = 2 * math.pi * r / ring
                ox, oy = math.cos(ang) * axis.radius, math.sin(ang) * axis.radius
                p = (center[0] + ox * px[0] + oy * py[0], center[1] + ox * px[1] + oy * py[1], center[2] + ox * px[2] + oy * py[2])
                verts.append([p[0], p[1], p[2]])
        for s in range(segments):
            for r in range(ring):
                a = base + s * ring + r
                b = base + s * ring + (r + 1) % ring
                c = base + (s + 1) * ring + r
                d2 = base + (s + 1) * ring + (r + 1) % ring
                faces.append([a, b, c])
                faces.append([b, d2, c])


def project_parametric(phenotype: Dict[str, Any], phenotype_ref: str = "") -> SpatialPhenotype:
    anat = phenotype.get("anatomical") if isinstance(phenotype.get("anatomical"), dict) else {}
    params = {"tail_count": anat.get("tail_count", phenotype.get("tail_count", 1)), "length": anat.get("length", phenotype.get("length", 1.0))}
    engine = ParametricGeometryEngine()
    axis = engine.from_phenotype_params(params)
    pts = engine.sample_points(axis)
    return SpatialPhenotype(spatial_id="sp_" + text_digest(phenotype_ref + str(params))[:12], phenotype_ref=phenotype_ref or "phenotype", representation="parametric", coordinates=pts, fields={"parametric": axis.to_dict(), "params": params}, provenance=engine.provenance())
