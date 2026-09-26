# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Execution protocol: model / backend / device / result. CPU is the oracle."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from ..artifact_util import artifact_digest, provenance_block
from ..version import COMPILER_VERSION
from .biochemical import BiochemicalEngine, ReactionSystem, fixture_abc


@dataclass
class ExecutionDevice:
    kind: str
    name: str
    precision: str = "float64"
    available: bool = True
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "name": self.name, "precision": self.precision, "available": self.available, "details": dict(self.details)}


@dataclass
class ExecutionModel:
    model_id: str
    model_version: str
    semantics: str
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"model_id": self.model_id, "model_version": self.model_version, "semantics": self.semantics, "parameters": dict(self.parameters)}


@dataclass
class ExecutionResult:
    result_id: str
    model: Dict[str, Any]
    device: Dict[str, Any]
    precision: str
    kernel_version: str
    parameters: Dict[str, Any]
    seed: int
    trajectory: List[Dict[str, Any]]
    observables: Dict[str, Any]
    digest: str
    tolerance: float
    available: bool
    note: str = ""
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "result_id": self.result_id, "model": dict(self.model), "device": dict(self.device),
            "precision": self.precision, "kernel_version": self.kernel_version, "parameters": dict(self.parameters),
            "seed": self.seed, "trajectory": list(self.trajectory), "observables": dict(self.observables),
            "digest": self.digest, "tolerance": self.tolerance, "available": self.available,
            "note": self.note, "provenance": dict(self.provenance),
        }
        payload["envelope_digest"] = artifact_digest({"result_id": self.result_id, "digest": self.digest, "device": self.device, "seed": self.seed})
        return payload


class ExecutionBackend(Protocol):
    def capabilities(self) -> Dict[str, Any]: ...
    def device(self) -> ExecutionDevice: ...
    def execute(self, model: ExecutionModel, options: Dict[str, Any]) -> ExecutionResult: ...


class CPUReferenceBackend:
    def __init__(self, system: Optional[ReactionSystem] = None) -> None:
        self.system = system or fixture_abc()
        self.engine = BiochemicalEngine(self.system)

    def capabilities(self) -> Dict[str, Any]:
        return {"backend": "CPUReferenceBackend", "class": "ENGINE", "device": "cpu", "available": True, "reference_oracle": True, "kernel_version": self.engine.kernel_version}

    def device(self) -> ExecutionDevice:
        return ExecutionDevice(kind="cpu", name="cpu-reference", precision="float64", available=True)

    def execute(self, model: ExecutionModel, options: Dict[str, Any]) -> ExecutionResult:
        dt = float(options.get("dt", model.parameters.get("dt", 0.05)))
        t_end = float(options.get("t_end", model.parameters.get("t_end", 5.0)))
        seed = int(options.get("seed", 1))
        regulatory = options.get("regulatory") or model.parameters.get("regulatory")
        genotype = options.get("genotype") or model.parameters.get("genotype")
        traj = self.engine.integrate(dt=dt, t_end=t_end, seed=seed, genotype=genotype, regulatory=regulatory)
        obs = self.engine.final_observables(traj)
        digest = self.engine.result_digest(traj)
        stride = max(1, len(traj.states) // 20)
        thin = [{"time": s["time"], "molecular": s["molecular"]} for s in traj.states[::stride]]
        if traj.states and (not thin or thin[-1]["time"] != traj.states[-1]["time"]):
            thin.append({"time": traj.states[-1]["time"], "molecular": traj.states[-1]["molecular"]})
        return ExecutionResult(
            result_id="cpu_" + digest[:12], model=model.to_dict(), device=self.device().to_dict(),
            precision="float64", kernel_version=self.engine.kernel_version,
            parameters={"dt": dt, "t_end": t_end, **self.system.param_map()}, seed=seed,
            trajectory=thin, observables=obs, digest=digest,
            tolerance=float(options.get("tolerance", 1e-9)), available=True, note="CPU reference oracle",
            provenance=provenance_block(layer="execution.cpu", compiler_version=COMPILER_VERSION, provider="panini.engines.execution", model_id=model.model_id, model_version=model.model_version, random_seed=seed),
        )


def biochemical_model(system: Optional[ReactionSystem] = None, **params: Any) -> ExecutionModel:
    system = system or fixture_abc()
    return ExecutionModel(model_id=system.system_id, model_version="0.9.0", semantics="mass_action_ode_euler", parameters=params)


def trajectories_close(a: List[Dict[str, Any]], b: List[Dict[str, Any]], tol: float) -> bool:
    if len(a) != len(b):
        return False
    for sa, sb in zip(a, b):
        ma, mb = sa.get("molecular") or {}, sb.get("molecular") or {}
        for k in set(ma) | set(mb):
            if abs(float(ma.get(k, 0.0)) - float(mb.get(k, 0.0))) > tol:
                return False
    return True
