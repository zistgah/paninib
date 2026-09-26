# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Digital execution backend contract wrapping the existing simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .artifact_util import artifact_digest, provenance_block, text_digest
from .engines.maturity import profile_for_axial_twin
from .version import COMPILER_VERSION


@dataclass
class ExecutionIR:
    execution_ir_id: str
    design_id: str
    program_id: str
    organism: str
    model_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "execution_ir_id": self.execution_ir_id,
            "design_id": self.design_id,
            "program_id": self.program_id,
            "organism": self.organism,
            "model_id": self.model_id,
            "payload_digest": text_digest(str(sorted(self.payload.keys()))),
        }
        payload["digest"] = artifact_digest(payload)
        return payload


@dataclass
class DigitalTwinDescriptor:
    model_id: str
    model_version: str
    scope: str
    resolution: str
    maturity: str
    unsupported_domains: List[str]
    parameters: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        profile = profile_for_axial_twin()
        profile.level = self.maturity or profile.level
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "scope": self.scope,
            "resolution": self.resolution,
            "maturity": self.maturity,
            "maturity_profile": profile.to_dict(),
            "unsupported_domains": list(self.unsupported_domains),
            "parameters": dict(self.parameters),
            "equation": "S(t+Δt)=F(S(t),G,E(t),U(t),θ,ξ(t)); Φ(t)=H(S(t))",
            "note": "A simulation that reaches a target is not a biological validation claim.",
        }


@dataclass
class ExecutionRun:
    run_id: str
    input_artifact: str
    model_id: str
    model_version: str
    parameters: Dict[str, Any]
    environment: Dict[str, Any]
    random_seed: int
    state_history: List[Dict[str, Any]]
    events: List[Dict[str, Any]]
    observations: List[Dict[str, Any]]
    phenotype: Dict[str, Any]
    verification: Dict[str, Any]
    provenance: Dict[str, Any]
    twin: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "run_id": self.run_id,
            "input_artifact": self.input_artifact,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "parameters": dict(self.parameters),
            "environment": dict(self.environment),
            "random_seed": self.random_seed,
            "state_history": list(self.state_history),
            "events": list(self.events),
            "observations": list(self.observations),
            "phenotype": dict(self.phenotype),
            "verification": dict(self.verification),
            "provenance": dict(self.provenance),
            "twin": dict(self.twin),
        }
        payload["digest"] = artifact_digest({
            "run_id": self.run_id,
            "input_artifact": self.input_artifact,
            "model_id": self.model_id,
            "random_seed": self.random_seed,
            "phenotype": self.phenotype,
        })
        return payload


class DigitalExecutionBackend(Protocol):
    def capabilities(self) -> Dict[str, Any]: ...
    def execute(self, execution_ir: ExecutionIR, environment: Dict[str, Any], options: Dict[str, Any]) -> ExecutionRun: ...
    def inspect(self, run: ExecutionRun) -> Dict[str, Any]: ...
    def checkpoint(self, run: ExecutionRun) -> List[Dict[str, Any]]: ...
    def trace(self, run: ExecutionRun) -> Dict[str, Any]: ...
    def verify(self, run: ExecutionRun) -> Dict[str, Any]: ...
    def provenance(self) -> Dict[str, Any]: ...


class SimulatorDigitalBackend:
    """Adapts python/panini/simulator into the DigitalExecutionBackend contract."""

    def __init__(self) -> None:
        self.name = "panini.digital.simulator"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "backend": self.name,
            "wraps": "python/panini/simulator",
            "whole_organism": False,
            "maturity_default": "DT-3",
            "can_checkpoint": True,
        }

    def provenance(self) -> Dict[str, Any]:
        return provenance_block(
            layer="digital_execution",
            compiler_version=COMPILER_VERSION,
            provider=self.name,
            model_id="simulator",
            model_version="0.8.0",
        )

    def twin_descriptor(self, payload: Dict[str, Any], params: Any) -> DigitalTwinDescriptor:
        contract = payload.get("execution_contract") or {}
        return DigitalTwinDescriptor(
            model_id=str(contract.get("model_id") or getattr(params, "model_id", "") or "unspecified"),
            model_version=str(contract.get("model_version") or "unspecified"),
            scope="reduced-order axial / conformance twin",
            resolution="1d_or_2axis_plugin",
            maturity=str(contract.get("model_status") or "DT-3"),
            unsupported_domains=["whole_organism", "biochemical_kinetics", "wet_lab_closed_loop"],
            parameters={"dt": getattr(params, "dt", None), "t_end": getattr(params, "t_end", None)},
        )

    def execute(self, execution_ir: ExecutionIR, environment: Dict[str, Any], options: Dict[str, Any]) -> ExecutionRun:
        from .simulator.api import Simulator
        from .simulator.models import ModelParams

        seed = int(options.get("seed", environment.get("seed", 1)))
        params = ModelParams()
        if options.get("dt"):
            params.dt = float(options["dt"])
        if options.get("t_end"):
            params.t_end = float(options["t_end"])
        sim = Simulator(payload=execution_ir.payload, params=params, seed=seed)
        run = sim.run(until=options.get("until"))
        twin = self.twin_descriptor(execution_ir.payload, params)
        history = []
        for cp in run.checkpoints or []:
            history.append({
                "checkpoint_id": cp.get("checkpoint_id"),
                "time": cp.get("timestamp"),
                "stage": cp.get("stage"),
            })
        events = []
        for ev in (run.events or [])[-32:]:
            if isinstance(ev, dict):
                events.append({"event_id": ev.get("event_id"), "time": ev.get("timestamp"), "op": ev.get("operation")})
        observations = [{"source": "SIMULATION", "phenotype": run.phenotype}]
        return ExecutionRun(
            run_id=run.run_id,
            input_artifact=execution_ir.execution_ir_id,
            model_id=twin.model_id,
            model_version=twin.model_version,
            parameters=twin.parameters,
            environment=dict(environment),
            random_seed=seed,
            state_history=history,
            events=events,
            observations=observations,
            phenotype=run.phenotype if isinstance(run.phenotype, dict) else {"raw": run.phenotype},
            verification=run.verification if isinstance(run.verification, dict) else {"raw": run.verification},
            provenance=self.provenance(),
            twin=twin.to_dict(),
        )

    def inspect(self, run: ExecutionRun) -> Dict[str, Any]:
        return {
            "run_id": run.run_id,
            "model_id": run.model_id,
            "events": len(run.events),
            "checkpoints": len(run.state_history),
            "phenotype_keys": sorted(run.phenotype),
        }

    def checkpoint(self, run: ExecutionRun) -> List[Dict[str, Any]]:
        return list(run.state_history)

    def trace(self, run: ExecutionRun) -> Dict[str, Any]:
        return {
            "run_id": run.run_id,
            "model_id": run.model_id,
            "seed": run.random_seed,
            "events": list(run.events),
            "state_history": list(run.state_history),
            "observations": list(run.observations),
            "note": "trace of executed digital twin; not causal inversion",
        }

    def verify(self, run: ExecutionRun) -> Dict[str, Any]:
        checks = [
            {"name": "run_id", "passed": bool(run.run_id)},
            {"name": "model_identity", "passed": bool(run.model_id)},
            {"name": "seeded", "passed": run.random_seed is not None},
            {"name": "phenotype_present", "passed": bool(run.phenotype)},
            {"name": "provenance", "passed": bool(run.provenance)},
        ]
        return {"overall_pass": all(c["passed"] for c in checks), "checks": checks, "run_id": run.run_id}


def execution_ir_from_payload(payload: Dict[str, Any], design: Optional[Dict[str, Any]] = None) -> ExecutionIR:
    design = design or payload.get("genotype_design") or {}
    pid = payload.get("program_id") or design.get("program_id") or design.get("design_id") or "unknown"
    eid = "eirx_" + text_digest(str(pid))[:12]
    return ExecutionIR(
        execution_ir_id=eid,
        design_id=str(design.get("design_id") or ""),
        program_id=str(pid),
        organism=str(payload.get("organism") or design.get("organism") or ""),
        model_id=str((payload.get("execution_contract") or {}).get("model_id") or ""),
        payload=payload,
    )


def default_digital_backend() -> SimulatorDigitalBackend:
    return SimulatorDigitalBackend()
