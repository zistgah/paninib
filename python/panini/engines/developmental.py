# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Developmental engine: kinetics + fields + cells + events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..artifact_util import artifact_digest, provenance_block
from ..version import COMPILER_VERSION
from .biochemical import BiochemicalEngine, fixture_abc
from .cellular import Cell, CellularEngine
from .fields import Grid, SpatialFieldEngine
from .maturity import profile_for_spatial_dev
from .reaction_diffusion import RDConfig, ReactionDiffusionEngine


@dataclass
class DevelopmentalState:
    time: float
    stage: str
    cell_population: List[Dict[str, Any]]
    field_state: Dict[str, Any]
    molecular_state: Dict[str, Any]
    anatomical_state: Dict[str, Any]
    events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = {"time": self.time, "stage": self.stage, "cell_population": list(self.cell_population), "field_state": dict(self.field_state), "molecular_state": dict(self.molecular_state), "anatomical_state": dict(self.anatomical_state), "events": list(self.events)}
        payload["digest"] = artifact_digest({"time": self.time, "stage": self.stage, "anatomical": self.anatomical_state})
        return payload


def _stage(t: float, t_end: float) -> str:
    frac = t / t_end if t_end else 0.0
    if frac < 0.25:
        return "induction"
    if frac < 0.5:
        return "patterning"
    if frac < 0.75:
        return "differentiation"
    return "mature"


class DevelopmentalEngine:
    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "DevelopmentalEngine", "class": "ENGINE", "combines": ["molecular", "fields", "cells", "events"], "scientific_model": False, "maturity": profile_for_spatial_dev().to_dict()}

    def run_spatial_fixture(self, steps: int = 12, dt: float = 0.05) -> Dict[str, Any]:
        bio = BiochemicalEngine(fixture_abc(k1=1.2, k2=0.4, a0=1.0))
        mol_traj = bio.integrate(dt=dt, t_end=steps * dt, seed=2)
        grid = Grid(nx=13, ny=1, nz=1, origin=(0.0, 0.0, 0.0), spacing=(1.0 / 12.0, 1.0, 1.0))
        u = SpatialFieldEngine().zeros("signal", grid)
        u.values[0][0][0] = 1.0
        v = SpatialFieldEngine().zeros("response", grid)
        rd = ReactionDiffusionEngine(RDConfig(Du=0.04, Dv=0.01, dt=dt, steps=steps, seed=2))

        def f(uu: float, vv: float):
            return (-0.15 * uu, 0.3 * uu - 0.2 * vv)

        rd_out = rd.integrate(u, v, f, checkpoint_every=4)
        cells_eng = CellularEngine(neighborhood_radius=0.2)
        cells: List[Cell] = cells_eng.seed_line(7)
        history: List[DevelopmentalState] = []
        events: List[Dict[str, Any]] = []
        t_end = steps * dt
        for t_idx in range(steps + 1):
            t = t_idx * dt
            for c in cells:
                x = c.position[0]
                c.signals["morphogen"] = max(0.0, (1.0 - x) * pow(2.718281828, -0.15 * t))
                c.time = t
                c.protein_state["C"] = float((mol_traj.states[min(t_idx, len(mol_traj.states) - 1)].get("molecular") or {}).get("C", 0.0))
            cells_eng.exchange_signals(cells)
            for c in cells:
                ev = cells_eng.transition(c, threshold=0.35)
                if ev:
                    events.append(ev)
            n_diff = sum(1 for c in cells if c.state == "differentiated")
            pattern = "bipolar" if n_diff >= 2 else "unipolar" if n_diff == 1 else "none"
            history.append(DevelopmentalState(
                time=t, stage=_stage(t, t_end), cell_population=[c.to_dict() for c in cells],
                field_state={"u_max": rd_out["frames"][min(t_idx, len(rd_out["frames"]) - 1)]["u_max"]},
                molecular_state=dict(mol_traj.states[min(t_idx, len(mol_traj.states) - 1)].get("molecular") or {}),
                anatomical_state={"pattern": pattern, "differentiated": n_diff, "n_cells": len(cells)},
                events=list(events),
            ))
        payload = {
            "trajectory": [s.to_dict() for s in history], "final": history[-1].to_dict() if history else {},
            "events": events, "maturity": profile_for_spatial_dev().to_dict(),
            "provenance": provenance_block(layer="developmental", compiler_version=COMPILER_VERSION, provider="panini.engines.developmental", model_id="dev.spatial_fixture", model_version="0.9.0", random_seed=2),
            "note": "synthetic developmental fixture; not an embryo model",
        }
        payload["digest"] = artifact_digest({"final": payload["final"], "n": len(history)})
        return payload

    def run_maturation(self, stages: int = 5) -> Dict[str, Any]:
        frames = []
        for i in range(stages):
            t = float(i)
            frac = i / max(1, stages - 1)
            frames.append({"time": t, "stage": _stage(t, float(stages - 1)), "state": {"maturity_frac": frac, "length": 0.4 + 0.6 * frac}, "geometry": {"axis_length": 0.4 + 0.6 * frac, "radius": 0.05 + 0.02 * frac}, "observables": {"length": 0.4 + 0.6 * frac}, "events": [{"event": "growth", "time": t}] if i else []})
        payload = {"frames": frames, "mature": frames[-1], "provenance": provenance_block(layer="maturation", compiler_version=COMPILER_VERSION, provider="panini.engines.developmental", model_id="dev.maturation", model_version="0.9.0")}
        payload["digest"] = artifact_digest(frames)
        return payload
