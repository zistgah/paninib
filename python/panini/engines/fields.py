# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Spatial field substrate: scalar, vector, grid, voxel."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from ..artifact_util import artifact_digest, provenance_block
from ..version import COMPILER_VERSION


@dataclass
class Grid:
    nx: int
    ny: int = 1
    nz: int = 1
    origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    spacing: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    units: str = "model_units"

    def shape(self) -> Tuple[int, int, int]:
        return (self.nx, self.ny, self.nz)

    def coord(self, i: int, j: int = 0, k: int = 0) -> Tuple[float, float, float]:
        return (self.origin[0] + i * self.spacing[0], self.origin[1] + j * self.spacing[1], self.origin[2] + k * self.spacing[2])

    def in_bounds(self, i: int, j: int = 0, k: int = 0) -> bool:
        return 0 <= i < self.nx and 0 <= j < self.ny and 0 <= k < self.nz

    def to_dict(self) -> Dict[str, Any]:
        return {"nx": self.nx, "ny": self.ny, "nz": self.nz, "origin": list(self.origin), "spacing": list(self.spacing), "units": self.units}


def _zeros(shape):
    nx, ny, nz = shape
    return [[[0.0 for _ in range(nz)] for _ in range(ny)] for _ in range(nx)]


def _copy3(v):
    return [[[float(x) for x in row] for row in plane] for plane in v]


def _flat(v):
    return [x for plane in v for row in plane for x in row]


@dataclass
class ScalarField:
    name: str
    grid: Grid
    values: List[List[List[float]]]
    units: str = "au"
    boundary_conditions: str = "neumann"
    provenance: Dict[str, Any] = field(default_factory=dict)

    def sample(self, i: int, j: int = 0, k: int = 0) -> float:
        if not self.grid.in_bounds(i, j, k):
            raise IndexError((i, j, k))
        return self.values[i][j][k]

    def interpolate(self, x: float, y: float = 0.0, z: float = 0.0) -> float:
        gx, gy, gz = self.grid.origin
        sx, sy, sz = self.grid.spacing
        fi = (x - gx) / sx if sx else 0.0
        fj = (y - gy) / sy if sy else 0.0
        i0 = max(0, min(self.grid.nx - 1, int(fi)))
        i1 = max(0, min(self.grid.nx - 1, i0 + 1))
        j0 = max(0, min(self.grid.ny - 1, int(fj)))
        j1 = max(0, min(self.grid.ny - 1, j0 + 1))
        tx, ty = fi - int(fi), fj - int(fj)
        v00 = self.values[i0][j0][0]
        v10 = self.values[i1][j0][0]
        v01 = self.values[i0][j1][0]
        v11 = self.values[i1][j1][0]
        return (1 - tx) * (1 - ty) * v00 + tx * (1 - ty) * v10 + (1 - tx) * ty * v01 + tx * ty * v11

    def gradient(self) -> "VectorField":
        gx = _zeros(self.grid.shape()); gy = _zeros(self.grid.shape()); gz = _zeros(self.grid.shape())
        sx, sy, sz = self.grid.spacing
        nx, ny, nz = self.grid.shape()
        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    im, ip = max(0, i - 1), min(nx - 1, i + 1)
                    jm, jp = max(0, j - 1), min(ny - 1, j + 1)
                    km, kp = max(0, k - 1), min(nz - 1, k + 1)
                    gx[i][j][k] = (self.values[ip][j][k] - self.values[im][j][k]) / (sx * max(1, ip - im) or 1)
                    gy[i][j][k] = (self.values[i][jp][k] - self.values[i][jm][k]) / (sy * max(1, jp - jm) or 1)
                    gz[i][j][k] = (self.values[i][j][kp] - self.values[i][j][km]) / (sz * max(1, kp - km) or 1)
        return VectorField(name=self.name + "_grad", grid=self.grid, components=(gx, gy, gz), units=self.units + "/L")

    def laplacian(self) -> "ScalarField":
        out = _zeros(self.grid.shape())
        sx, sy, sz = self.grid.spacing
        nx, ny, nz = self.grid.shape()
        invx = 1.0 / (sx * sx) if sx else 0.0
        invy = 1.0 / (sy * sy) if sy else 0.0
        invz = 1.0 / (sz * sz) if sz else 0.0
        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    c = self.values[i][j][k]
                    im, ip = max(0, i - 1), min(nx - 1, i + 1)
                    jm, jp = max(0, j - 1), min(ny - 1, j + 1)
                    km, kp = max(0, k - 1), min(nz - 1, k + 1)
                    out[i][j][k] = ((self.values[ip][j][k] - 2 * c + self.values[im][j][k]) * invx + (self.values[i][jp][k] - 2 * c + self.values[i][jm][k]) * invy + (self.values[i][j][kp] - 2 * c + self.values[i][j][km]) * invz)
        return ScalarField(name=self.name + "_lap", grid=self.grid, values=out, units=self.units + "/L2")

    def threshold(self, t: float) -> "ScalarField":
        out = _zeros(self.grid.shape())
        nx, ny, nz = self.grid.shape()
        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    out[i][j][k] = 1.0 if self.values[i][j][k] >= t else 0.0
        return ScalarField(name=self.name + "_thr", grid=self.grid, values=out, units="mask")

    def mask(self, other: "ScalarField") -> "ScalarField":
        return self.combine(other, "mul")

    def combine(self, other: "ScalarField", op: str = "add") -> "ScalarField":
        out = _zeros(self.grid.shape())
        nx, ny, nz = self.grid.shape()
        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    a, b = self.values[i][j][k], other.values[i][j][k]
                    out[i][j][k] = a + b if op == "add" else a * b if op == "mul" else (a if a > b else b) if op == "max" else a - b
        return ScalarField(name=f"{self.name}_{op}_{other.name}", grid=self.grid, values=out, units=self.units)

    def to_dict(self) -> Dict[str, Any]:
        payload = {"name": self.name, "grid": self.grid.to_dict(), "values": self.values, "units": self.units, "boundary_conditions": self.boundary_conditions, "provenance": dict(self.provenance)}
        payload["digest"] = artifact_digest({"name": self.name, "grid": self.grid.to_dict(), "flat": _flat(self.values)})
        return payload


@dataclass
class VectorField:
    name: str
    grid: Grid
    components: Tuple[List[List[List[float]]], List[List[List[float]]], List[List[List[float]]]]
    units: str = "au"

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "grid": self.grid.to_dict(), "units": self.units}


@dataclass
class VoxelField:
    name: str
    grid: Grid
    values: List[List[List[float]]]
    units: str = "au"

    def to_dict(self) -> Dict[str, Any]:
        payload = {"name": self.name, "grid": self.grid.to_dict(), "values": self.values, "units": self.units}
        payload["digest"] = artifact_digest({"name": self.name, "flat": _flat(self.values)})
        return payload


class SpatialFieldEngine:
    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "SpatialFieldEngine", "class": "ENGINE", "ops": ["sample", "interpolate", "gradient", "laplacian", "threshold", "mask", "combine"], "scientific_model": False}

    def zeros(self, name: str, grid: Grid) -> ScalarField:
        return ScalarField(name=name, grid=grid, values=_zeros(grid.shape()), provenance=provenance_block(layer="spatial_field", compiler_version=COMPILER_VERSION, provider="panini.engines.fields", model_id="field.cpu", model_version="0.9.0"))

    def to_voxel(self, field: ScalarField) -> VoxelField:
        return VoxelField(name=field.name, grid=field.grid, values=_copy3(field.values), units=field.units)


def fixture_gradient_1d(n: int = 21) -> ScalarField:
    engine = SpatialFieldEngine()
    grid = Grid(nx=n, ny=1, nz=1, origin=(0.0, 0.0, 0.0), spacing=(1.0 / max(1, n - 1), 1.0, 1.0))
    field = engine.zeros("linear_x", grid)
    for i in range(n):
        field.values[i][0][0] = i / max(1, n - 1)
    return field
