# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Generic reaction-diffusion: du/dt = D∇²u + f(u,v)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple

from ..artifact_util import artifact_digest, provenance_block
from ..version import COMPILER_VERSION
from .fields import Grid, ScalarField, SpatialFieldEngine, _copy3, _zeros

ReactionFn = Callable[[float, float], Tuple[float, float]]


@dataclass
class RDConfig:
    Du: float = 0.01
    Dv: float = 0.005
    dt: float = 0.01
    steps: int = 50
    boundary: str = "neumann"
    seed: int = 1


class ReactionDiffusionEngine:
    def __init__(self, config: RDConfig | None = None) -> None:
        self.config = config or RDConfig()

    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "ReactionDiffusionEngine", "class": "ENGINE", "cpu": True, "scientific_model": False, "equation": "du/dt = D∇²u + f(u,v)"}

    def step(self, u: ScalarField, v: ScalarField, f: ReactionFn) -> Tuple[ScalarField, ScalarField]:
        cfg = self.config
        lap_u, lap_v = u.laplacian(), v.laplacian()
        un, vn = _zeros(u.grid.shape()), _zeros(v.grid.shape())
        nx, ny, nz = u.grid.shape()
        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    fu, gv = f(u.values[i][j][k], v.values[i][j][k])
                    un[i][j][k] = max(0.0, u.values[i][j][k] + cfg.dt * (cfg.Du * lap_u.values[i][j][k] + fu))
                    vn[i][j][k] = max(0.0, v.values[i][j][k] + cfg.dt * (cfg.Dv * lap_v.values[i][j][k] + gv))
        return (ScalarField(name=u.name, grid=u.grid, values=un, units=u.units, boundary_conditions=cfg.boundary),
                ScalarField(name=v.name, grid=v.grid, values=vn, units=v.units, boundary_conditions=cfg.boundary))

    def integrate(self, u0: ScalarField, v0: ScalarField, f: ReactionFn, *, checkpoint_every: int = 10) -> Dict[str, Any]:
        u, v = u0, v0
        frames, checkpoints = [], []
        for t in range(self.config.steps + 1):
            rec = {"step": t, "time": t * self.config.dt, "u_max": _max3(u.values), "v_max": _max3(v.values)}
            frames.append(rec)
            if t % checkpoint_every == 0 or t == self.config.steps:
                checkpoints.append(dict(rec))
            if t == self.config.steps:
                break
            u, v = self.step(u, v, f)
        payload = {
            "engine": "ReactionDiffusionEngine", "config": self.config.__dict__, "frames": frames,
            "checkpoints": checkpoints, "final_u": u.to_dict(), "final_v": v.to_dict(),
            "provenance": provenance_block(layer="reaction_diffusion", compiler_version=COMPILER_VERSION, provider="panini.engines.rd", model_id="rd.cpu", model_version="0.9.0", random_seed=self.config.seed, parameters=self.config.__dict__),
        }
        payload["digest"] = artifact_digest({"frames": frames, "cfg": self.config.__dict__})
        return payload


def fixture_source_decay() -> Dict[str, Any]:
    grid = Grid(nx=17, ny=1, nz=1, origin=(0.0, 0.0, 0.0), spacing=(1.0 / 16.0, 1.0, 1.0))
    eng_f = SpatialFieldEngine()
    u, v = eng_f.zeros("u", grid), eng_f.zeros("v", grid)
    u.values[0][0][0] = 1.0

    def f(uu: float, vv: float) -> Tuple[float, float]:
        return (-0.2 * uu, 0.2 * uu - 0.1 * vv)

    return ReactionDiffusionEngine(RDConfig(Du=0.05, Dv=0.02, dt=0.02, steps=40, seed=3)).integrate(u, v, f, checkpoint_every=8)


def _max3(values: List[List[List[float]]]) -> float:
    m = values[0][0][0]
    for plane in values:
        for row in plane:
            for x in row:
                if x > m:
                    m = x
    return m
