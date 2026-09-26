# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""X(t+Δt) = F(X(t), G, E(t), U(t), θ, ξ(t))."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..artifact_util import artifact_digest, provenance_block
from ..version import COMPILER_VERSION
from .state import MultiscaleState

TransitionFn = Callable[[MultiscaleState, Dict[str, Any]], MultiscaleState]


@dataclass
class TransitionSpec:
    kind: str
    name: str
    dt: float = 0.1
    seed: int = 0
    parameters: Dict[str, Any] = field(default_factory=dict)
    model_version: str = "0.9.0"


@dataclass
class Trajectory:
    trajectory_id: str
    model_id: str
    model_version: str
    seed: int
    dt: float
    states: List[Dict[str, Any]]
    events: List[Dict[str, Any]]
    checkpoints: List[Dict[str, Any]]
    parameters: Dict[str, Any]
    environment: Dict[str, Any]
    provenance: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "trajectory_id": self.trajectory_id, "model_id": self.model_id,
            "model_version": self.model_version, "seed": self.seed, "dt": self.dt,
            "n_states": len(self.states), "states": list(self.states),
            "events": list(self.events), "checkpoints": list(self.checkpoints),
            "parameters": dict(self.parameters), "environment": dict(self.environment),
            "provenance": dict(self.provenance),
        }
        payload["digest"] = artifact_digest({
            "trajectory_id": self.trajectory_id, "seed": self.seed,
            "n_states": len(self.states), "last": self.states[-1] if self.states else {},
        })
        return payload


class TransitionEngine:
    def __init__(self, spec: TransitionSpec, fn: TransitionFn) -> None:
        self.spec = spec
        self.fn = fn

    def step(self, state: MultiscaleState, extras: Optional[Dict[str, Any]] = None) -> MultiscaleState:
        ctx = {"G": state.genotype, "E": state.environment, "U": state.controls, "theta": state.parameters, "xi": state.noise, "dt": self.spec.dt, "kind": self.spec.kind, "seed": self.spec.seed}
        if extras:
            ctx.update(extras)
        nxt = self.fn(state, ctx)
        nxt.time = state.time + self.spec.dt
        nxt.step = state.step + 1
        nxt.seed = self.spec.seed
        nxt.model_version = self.spec.model_version
        return nxt

    def integrate(self, initial: MultiscaleState, steps: int, *, checkpoint_every: int = 1, events_from: Optional[Callable[[MultiscaleState], List[Dict[str, Any]]]] = None) -> Trajectory:
        rng = random.Random(self.spec.seed)
        state = initial.copy()
        state.seed = self.spec.seed
        snaps = [state.snapshot()]
        events: List[Dict[str, Any]] = []
        checkpoints = [{"step": 0, "time": state.time, "digest": snaps[0]["digest"]}]
        for i in range(steps):
            if self.spec.kind == "stochastic":
                state.noise = {"u": rng.random(), "step": i}
            state = self.step(state)
            snap = state.snapshot()
            snaps.append(snap)
            if events_from:
                events.extend(events_from(state))
            if checkpoint_every and ((i + 1) % checkpoint_every == 0):
                checkpoints.append({"step": state.step, "time": state.time, "digest": snap["digest"]})
        tid = hashlib.sha256(f"{self.spec.name}:{self.spec.seed}:{steps}".encode()).hexdigest()[:16]
        return Trajectory(
            trajectory_id="trj_" + tid, model_id=self.spec.name, model_version=self.spec.model_version,
            seed=self.spec.seed, dt=self.spec.dt, states=snaps, events=events, checkpoints=checkpoints,
            parameters=dict(self.spec.parameters), environment=dict(initial.environment),
            provenance=provenance_block(layer="transition", compiler_version=COMPILER_VERSION, provider="panini.engines.transitions", model_id=self.spec.name, model_version=self.spec.model_version, random_seed=self.spec.seed, parameters={"dt": self.spec.dt, "steps": steps, "kind": self.spec.kind}),
        )
