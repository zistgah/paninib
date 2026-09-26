# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Minimal CPU Gillespie SSA backend.

This is a synthetic conformance engine. It is not a mammalian
molecular simulation and must not be advertised as one.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional

from ..artifact_util import artifact_digest, provenance_block, text_digest
from ..version import COMPILER_VERSION, SSA_ENGINE_VERSION
from .biochemical import Reaction, ReactionSystem, Species, Parameter, Observable, fixture_abc, _rate
from .execution import ExecutionDevice, ExecutionModel, ExecutionResult


def fixture_ssa_abc(a0: int = 100, k1: float = 0.05, k2: float = 0.03) -> ReactionSystem:
    return ReactionSystem(
        system_id="fixture_ssa_abc",
        species=[Species("A", initial=float(a0)), Species("B", initial=0.0), Species("C", initial=0.0)],
        reactions=[
            Reaction("r1", {"A": 1}, {"B": 1}, "mass_action_count", "k1"),
            Reaction("r2", {"B": 1}, {"C": 1}, "mass_action_count", "k2"),
        ],
        parameters=[Parameter("k1", k1, units="1/time"), Parameter("k2", k2, units="1/time")],
        observables=[Observable("A", "A"), Observable("B", "B"), Observable("C", "C")],
        note="synthetic SSA fixture; integer molecule counts; not a mammalian network",
    )


def _propensity(rxn: Reaction, counts: Dict[str, int], params: Dict[str, float]) -> float:
    k = float(params.get(rxn.rate_parameter, 0.0))
    prod = 1.0
    for sid, stoich in rxn.reactants.items():
        n = int(counts.get(sid, 0))
        s = int(stoich)
        if n < s:
            return 0.0
        # combinatorial mass-action on counts
        comb = 1
        for i in range(s):
            comb *= n - i
        prod *= float(comb)
    return k * prod


class SSAEngine:
    """Seeded Gillespie direct method on a ReactionSystem of counts."""

    def __init__(self, system: Optional[ReactionSystem] = None) -> None:
        self.system = system or fixture_ssa_abc()
        self.kernel_version = "gillespie-direct-" + SSA_ENGINE_VERSION

    def capabilities(self) -> Dict[str, Any]:
        return {
            "engine": "SSAEngine",
            "class": "ENGINE",
            "mode": "SSA_stochastic",
            "device": "cpu",
            "scientific_model": False,
            "fixture": self.system.system_id,
            "kernel_version": self.kernel_version,
            "note": "synthetic stochastic kinetics only",
        }

    def simulate(
        self,
        *,
        t_end: float = 20.0,
        seed: int = 7,
        max_events: int = 5000,
    ) -> Dict[str, Any]:
        rng = random.Random(int(seed))
        counts = {s.species_id: int(round(s.initial)) for s in self.system.species}
        params = self.system.param_map()
        t = 0.0
        events: List[Dict[str, Any]] = []
        trajectory: List[Dict[str, Any]] = [{"time": 0.0, "counts": dict(counts)}]
        n = 0
        while t < t_end and n < max_events:
            props = {rxn.reaction_id: _propensity(rxn, counts, params) for rxn in self.system.reactions}
            total = sum(props.values())
            if total <= 0.0:
                break
            r1 = rng.random() or 1e-15
            r2 = rng.random()
            dt = -math.log(r1) / total
            t = t + dt
            if t > t_end:
                t = t_end
                trajectory.append({"time": t, "counts": dict(counts)})
                break
            threshold = r2 * total
            acc = 0.0
            chosen = None
            for rxn in self.system.reactions:
                acc += props[rxn.reaction_id]
                if acc >= threshold:
                    chosen = rxn
                    break
            if chosen is None:
                chosen = self.system.reactions[-1]
            for sid, stoich in chosen.reactants.items():
                counts[sid] = max(0, int(counts.get(sid, 0)) - int(stoich))
            for sid, stoich in chosen.products.items():
                counts[sid] = int(counts.get(sid, 0)) + int(stoich)
            n += 1
            events.append({
                "event_index": n,
                "time": t,
                "reaction_id": chosen.reaction_id,
                "counts": dict(counts),
            })
            if n % max(1, max_events // 40) == 0 or n < 8:
                trajectory.append({"time": t, "counts": dict(counts)})
        if not trajectory or trajectory[-1]["time"] != t:
            trajectory.append({"time": t, "counts": dict(counts)})
        payload = {
            "system_id": self.system.system_id,
            "kernel_version": self.kernel_version,
            "seed": int(seed),
            "t_end": float(t_end),
            "parameters": params,
            "event_count": n,
            "events": events,
            "trajectory": trajectory,
            "final_counts": dict(counts),
            "conservation": {
                "initial_mass": sum(int(round(s.initial)) for s in self.system.species),
                "final_mass": sum(counts.values()),
            },
            "note": self.system.note,
            "provenance": provenance_block(
                layer="execution.ssa",
                compiler_version=COMPILER_VERSION,
                provider="panini.engines.ssa",
                model_id=self.system.system_id,
                model_version=self.kernel_version,
                random_seed=int(seed),
            ),
        }
        payload["digest"] = artifact_digest({
            "seed": seed,
            "final": payload["final_counts"],
            "events": n,
            "kernel": self.kernel_version,
        })
        return payload


class SSABackend:
    def __init__(self, system: Optional[ReactionSystem] = None) -> None:
        self.engine = SSAEngine(system)

    def capabilities(self) -> Dict[str, Any]:
        caps = self.engine.capabilities()
        caps["backend"] = "SSABackend"
        caps["available"] = True
        return caps

    def device(self) -> ExecutionDevice:
        return ExecutionDevice(kind="cpu", name="cpu-ssa", precision="int-count", available=True)

    def execute(self, model: ExecutionModel, options: Dict[str, Any]) -> ExecutionResult:
        seed = int(options.get("seed", 7))
        t_end = float(options.get("t_end", model.parameters.get("t_end", 20.0)))
        out = self.engine.simulate(t_end=t_end, seed=seed, max_events=int(options.get("max_events", 5000)))
        thin = [{"time": s["time"], "molecular": s["counts"]} for s in out["trajectory"]]
        return ExecutionResult(
            result_id="ssa_" + out["digest"][:12],
            model=model.to_dict(),
            device=self.device().to_dict(),
            precision="int-count",
            kernel_version=self.engine.kernel_version,
            parameters=dict(out["parameters"]),
            seed=seed,
            trajectory=thin,
            observables=out["final_counts"],
            digest=out["digest"],
            tolerance=0.0,
            available=True,
            note="CPU Gillespie fixture; not mammalian SSA",
            provenance=out["provenance"],
        )
