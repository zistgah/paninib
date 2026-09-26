# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Generic biochemical ODE engine. Not a mammalian biochemistry model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..artifact_util import artifact_digest, provenance_block, text_digest
from ..version import COMPILER_VERSION
from .state import MultiscaleState, MultiscaleStateEngine
from .transitions import Trajectory, TransitionEngine, TransitionSpec


@dataclass
class Species:
    species_id: str
    compartment: str = "default"
    initial: float = 0.0
    units: str = "concentration"


@dataclass
class Parameter:
    name: str
    value: float
    units: str = "1/time"


@dataclass
class Compartment:
    compartment_id: str
    size: float = 1.0


@dataclass
class Reaction:
    reaction_id: str
    reactants: Dict[str, float]
    products: Dict[str, float]
    rate_law: str
    rate_parameter: str
    reversible: bool = False


@dataclass
class Observable:
    name: str
    species_id: str


@dataclass
class EventRule:
    event_id: str
    trigger: str
    assignments: Dict[str, float]


@dataclass
class ReactionSystem:
    system_id: str
    species: List[Species]
    reactions: List[Reaction]
    parameters: List[Parameter]
    compartments: List[Compartment] = field(default_factory=list)
    observables: List[Observable] = field(default_factory=list)
    events: List[EventRule] = field(default_factory=list)
    note: str = "synthetic reaction system; not a mammalian network"

    def param_map(self) -> Dict[str, float]:
        return {p.name: p.value for p in self.parameters}

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "system_id": self.system_id,
            "species": [s.__dict__ for s in self.species],
            "reactions": [r.__dict__ for r in self.reactions],
            "parameters": [p.__dict__ for p in self.parameters],
            "compartments": [c.__dict__ for c in self.compartments],
            "observables": [o.__dict__ for o in self.observables],
            "events": [e.__dict__ for e in self.events],
            "note": self.note,
        }
        payload["digest"] = artifact_digest(payload)
        return payload


def fixture_abc(k1: float = 1.0, k2: float = 0.5, a0: float = 1.0) -> ReactionSystem:
    return ReactionSystem(
        system_id="fixture_abc",
        species=[Species("A", initial=a0), Species("B", initial=0.0), Species("C", initial=0.0)],
        reactions=[
            Reaction("r1", {"A": 1}, {"B": 1}, "mass_action", "k1"),
            Reaction("r2", {"B": 1}, {"C": 1}, "mass_action", "k2"),
        ],
        parameters=[Parameter("k1", k1), Parameter("k2", k2)],
        observables=[Observable("A", "A"), Observable("B", "B"), Observable("C", "C")],
    )


def _rate(rxn: Reaction, conc: Dict[str, float], params: Dict[str, float]) -> float:
    k = float(params.get(rxn.rate_parameter, 0.0))
    prod = 1.0
    for sid, stoich in rxn.reactants.items():
        prod *= conc.get(sid, 0.0) ** stoich
    return k * prod


def _rhs(system: ReactionSystem, conc: Dict[str, float]) -> Dict[str, float]:
    deriv = {s.species_id: 0.0 for s in system.species}
    params = system.param_map()
    for rxn in system.reactions:
        flux = _rate(rxn, conc, params)
        for sid, stoich in rxn.reactants.items():
            deriv[sid] -= stoich * flux
        for sid, stoich in rxn.products.items():
            deriv[sid] += stoich * flux
    return deriv


class BiochemicalEngine:
    def __init__(self, system: Optional[ReactionSystem] = None) -> None:
        self.system = system or fixture_abc()
        self.kernel_version = "ode-euler-0.9.0"

    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "BiochemicalEngine", "class": "ENGINE", "modes": ["ODE_deterministic"], "reserved": ["SSA_stochastic"], "scientific_model": False, "fixture": self.system.system_id, "kernel_version": self.kernel_version}

    def fluxes(self, conc: Dict[str, float]) -> Dict[str, float]:
        params = self.system.param_map()
        return {rxn.reaction_id: _rate(rxn, conc, params) for rxn in self.system.reactions}

    def step_ode(self, conc: Dict[str, float], dt: float) -> Dict[str, float]:
        deriv = _rhs(self.system, conc)
        return {sid: max(0.0, conc.get(sid, 0.0) + dt * deriv[sid]) for sid in deriv}

    def integrate(self, *, dt: float = 0.05, t_end: float = 5.0, seed: int = 1, genotype=None, regulatory=None) -> Trajectory:
        system = self.system
        if regulatory:
            for name, value in regulatory.items():
                for p in system.parameters:
                    if p.name == name:
                        p.value = float(value)
        if genotype and "rate_overrides" in genotype:
            for name, value in genotype["rate_overrides"].items():
                for p in system.parameters:
                    if p.name == name:
                        p.value = float(value)
        conc = {s.species_id: float(s.initial) for s in system.species}
        initial = MultiscaleStateEngine(model_id="biochemical.ode").initialize(
            genotype=genotype or {}, parameters=system.param_map(), seed=seed, molecular=dict(conc), regulatory=dict(regulatory or {}),
        )
        initial.model_id = system.system_id

        def fn(st: MultiscaleState, ctx: Dict[str, Any]) -> MultiscaleState:
            nxt = st.copy()
            nxt.molecular = self.step_ode({k: float(v) for k, v in st.molecular.items()}, float(ctx["dt"]))
            return nxt

        spec = TransitionSpec(kind="deterministic", name=system.system_id, dt=dt, seed=seed, parameters=system.param_map(), model_version=self.kernel_version)
        steps = max(1, int(round(t_end / dt)))
        return TransitionEngine(spec, fn).integrate(initial, steps, checkpoint_every=max(1, steps // 10))

    def observables(self, traj: Trajectory) -> Dict[str, List[float]]:
        out = {o.name: [] for o in self.system.observables}
        for snap in traj.states:
            mol = snap.get("molecular") or {}
            for o in self.system.observables:
                out[o.name].append(float(mol.get(o.species_id, 0.0)))
        return out

    def final_observables(self, traj: Trajectory) -> Dict[str, float]:
        last = (traj.states[-1].get("molecular") or {}) if traj.states else {}
        return {o.name: float(last.get(o.species_id, 0.0)) for o in self.system.observables}

    def result_digest(self, traj: Trajectory) -> str:
        return text_digest(str(sorted(self.final_observables(traj).items())))

    def conservation_diagnostics(self, traj: Trajectory) -> Dict[str, Any]:
        initial = {s.species_id: float(s.initial) for s in self.system.species}
        last = (traj.states[-1].get("molecular") or {}) if traj.states else {}
        mass0 = sum(initial.values())
        mass1 = sum(float(last.get(k, 0.0)) for k in initial)
        negatives = {k: float(last.get(k, 0.0)) for k in initial if float(last.get(k, 0.0)) < -1e-12}
        return {
            "initial_mass": mass0,
            "final_mass": mass1,
            "drift": mass1 - mass0,
            "relative_drift": (mass1 - mass0) / mass0 if mass0 else 0.0,
            "negatives": negatives,
            "conserved_approximately": abs(mass1 - mass0) <= 0.05 * max(1.0, mass0),
        }

    def numerical_diagnostics(self, traj: Trajectory, *, dt: float) -> Dict[str, Any]:
        n = max(0, len(traj.states) - 1)
        return {
            "scheme": "forward_euler",
            "dt": dt,
            "steps": n,
            "kernel_version": self.kernel_version,
            "non_negative": all(float(v) >= -1e-12 for s in traj.states for v in (s.get("molecular") or {}).values()),
            "finite": all(
                float(v) == float(v) and abs(float(v)) != float("inf")
                for s in traj.states
                for v in (s.get("molecular") or {}).values()
            ),
        }

    def inspect(self, traj: Trajectory, *, dt: float = 0.05) -> Dict[str, Any]:
        return {
            "system": self.system.to_dict(),
            "final": self.final_observables(traj),
            "conservation": self.conservation_diagnostics(traj),
            "numerical": self.numerical_diagnostics(traj, dt=dt),
            "digest": self.result_digest(traj),
            "note": self.system.note,
        }
