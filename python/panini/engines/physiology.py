# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Generic physiological-state engine. Not a complete organism model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from ..artifact_util import artifact_digest, provenance_block
from ..version import COMPILER_VERSION
from .maturity import MaturityProfile


@dataclass
class OrganSystem:
    system_id: str
    state_variables: Dict[str, float]
    flows: Dict[str, float] = field(default_factory=dict)
    rates: Dict[str, float] = field(default_factory=dict)
    parameters: Dict[str, float] = field(default_factory=dict)
    inputs: Dict[str, float] = field(default_factory=dict)
    outputs: Dict[str, float] = field(default_factory=dict)
    observables: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"system_id": self.system_id, "state_variables": dict(self.state_variables), "flows": dict(self.flows), "rates": dict(self.rates), "parameters": dict(self.parameters), "inputs": dict(self.inputs), "outputs": dict(self.outputs), "observables": dict(self.observables)}


PhysModel = Callable[[OrganSystem, float], OrganSystem]


class PhysiologicalEngine:
    def __init__(self) -> None:
        self.models: Dict[str, PhysModel] = {}
        self.register("fixture_tank", _tank_model)

    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "PhysiologicalEngine", "class": "ENGINE", "scientific_model": False, "modeled": ["fixture_tank"], "not_modeled": ["whole_organism", "disease_encyclopedia", "drug_interaction_library"], "slots": ["organ/system", "biochemical_pathway", "drug_interaction", "disease_state", "treatment", "patient_specific"], "registered": sorted(self.models)}

    def register(self, name: str, model: PhysModel) -> None:
        self.models[name] = model

    def descriptor(self) -> Dict[str, Any]:
        return {"modeled": "single-compartment tank with inflow/outflow (synthetic)", "not_modeled": "any real organ, closed-loop physiology, or patient digital twin", "maturity": MaturityProfile(level="DT-1", physiological=True).to_dict()}

    def run(self, system: OrganSystem, *, model_id: str = "fixture_tank", dt: float = 0.1, steps: int = 20, molecular_input: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        if model_id not in self.models:
            raise KeyError(model_id)
        model = self.models[model_id]
        if molecular_input:
            system.inputs.update({k: float(v) for k, v in molecular_input.items()})
        history = [system.to_dict()]
        cur = system
        for _ in range(steps):
            cur = model(cur, dt)
            history.append(cur.to_dict())
        payload = {"model_id": model_id, "descriptor": self.descriptor(), "history": history, "final": history[-1], "observables": dict(cur.observables), "provenance": provenance_block(layer="physiology", compiler_version=COMPILER_VERSION, provider="panini.engines.physiology", model_id=model_id, model_version="0.9.0")}
        payload["digest"] = artifact_digest({"final": history[-1], "model": model_id})
        return payload


def fixture_tank(volume0: float = 1.0, inflow: float = 0.1, leak: float = 0.05) -> OrganSystem:
    return OrganSystem(system_id="fixture_tank", state_variables={"volume": volume0, "solute": 0.0}, flows={"inflow": inflow, "outflow": 0.0}, rates={"leak": leak}, parameters={"capacity": 5.0}, inputs={"inflow": inflow, "solute_in": 0.0}, outputs={"outflow": 0.0}, observables={"volume": volume0})


def _tank_model(sys: OrganSystem, dt: float) -> OrganSystem:
    inflow = float(sys.inputs.get("inflow", 0.0))
    leak = float(sys.rates.get("leak", 0.0))
    vol = float(sys.state_variables.get("volume", 0.0))
    outflow = leak * vol
    vol = max(0.0, vol + dt * (inflow - outflow))
    solute = float(sys.state_variables.get("solute", 0.0)) + dt * float(sys.inputs.get("solute_in", 0.0))
    return OrganSystem(system_id=sys.system_id, state_variables={"volume": vol, "solute": solute}, flows={"inflow": inflow, "outflow": outflow}, rates=dict(sys.rates), parameters=dict(sys.parameters), inputs=dict(sys.inputs), outputs={"outflow": outflow}, observables={"volume": vol, "solute": solute})
