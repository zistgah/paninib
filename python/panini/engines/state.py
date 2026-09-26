# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Extensible multiscale state. Do not populate every biological variable."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..artifact_util import artifact_digest, provenance_block, text_digest
from ..version import COMPILER_VERSION

STATE_LAYERS = ("molecular", "regulatory", "cellular", "spatial", "developmental", "anatomical", "physiological")


@dataclass
class MultiscaleState:
    time: float = 0.0
    step: int = 0
    molecular: Dict[str, Any] = field(default_factory=dict)
    regulatory: Dict[str, Any] = field(default_factory=dict)
    cellular: Dict[str, Any] = field(default_factory=dict)
    spatial: Dict[str, Any] = field(default_factory=dict)
    developmental: Dict[str, Any] = field(default_factory=dict)
    anatomical: Dict[str, Any] = field(default_factory=dict)
    physiological: Dict[str, Any] = field(default_factory=dict)
    layers: Dict[str, Any] = field(default_factory=dict)
    genotype: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    controls: Dict[str, Any] = field(default_factory=dict)
    noise: Dict[str, Any] = field(default_factory=dict)
    seed: int = 0
    model_id: str = ""
    model_version: str = "0.9.0"
    events: List[Dict[str, Any]] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def layer(self, name: str) -> Dict[str, Any]:
        if hasattr(self, name) and isinstance(getattr(self, name), dict):
            return getattr(self, name)
        return self.layers.setdefault(name, {})

    def set_layer(self, name: str, value: Dict[str, Any]) -> None:
        if hasattr(self, name) and isinstance(getattr(self, name), dict):
            setattr(self, name, value)
        else:
            self.layers[name] = value

    def snapshot(self) -> Dict[str, Any]:
        payload = {
            "time": self.time, "step": self.step,
            "molecular": dict(self.molecular), "regulatory": dict(self.regulatory),
            "cellular": dict(self.cellular), "spatial": dict(self.spatial),
            "developmental": dict(self.developmental), "anatomical": dict(self.anatomical),
            "physiological": dict(self.physiological), "layers": dict(self.layers),
            "genotype": dict(self.genotype), "environment": dict(self.environment),
            "parameters": dict(self.parameters), "controls": dict(self.controls),
            "noise": dict(self.noise), "seed": self.seed,
            "model_id": self.model_id, "model_version": self.model_version,
            "events": list(self.events),
        }
        payload["digest"] = artifact_digest(payload)
        return payload

    def copy(self) -> "MultiscaleState":
        nxt = MultiscaleState(
            time=self.time, step=self.step,
            molecular=dict(self.molecular), regulatory=dict(self.regulatory),
            cellular=dict(self.cellular), spatial=dict(self.spatial),
            developmental=dict(self.developmental), anatomical=dict(self.anatomical),
            physiological=dict(self.physiological),
            layers={k: dict(v) if isinstance(v, dict) else v for k, v in self.layers.items()},
            genotype=dict(self.genotype), environment=dict(self.environment),
            parameters=dict(self.parameters), controls=dict(self.controls),
            noise=dict(self.noise), seed=self.seed, model_id=self.model_id,
            model_version=self.model_version, events=list(self.events),
            provenance=dict(self.provenance),
        )
        return nxt


class MultiscaleStateEngine:
    def __init__(self, model_id: str = "panini.state", model_version: str = "0.9.0") -> None:
        self.model_id = model_id
        self.model_version = model_version

    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "MultiscaleStateEngine", "layers": list(STATE_LAYERS), "extensible": True, "class": "ENGINE", "scientific_model": False}

    def initialize(self, *, genotype=None, environment=None, parameters=None, seed: int = 0, **layers: Any) -> MultiscaleState:
        st = MultiscaleState(
            genotype=dict(genotype or {}), environment=dict(environment or {}),
            parameters=dict(parameters or {}), seed=int(seed),
            model_id=self.model_id, model_version=self.model_version,
            provenance=provenance_block(layer="state", compiler_version=COMPILER_VERSION, provider="panini.engines.state", model_id=self.model_id, model_version=self.model_version, random_seed=seed),
        )
        for name, value in layers.items():
            if isinstance(value, dict):
                st.set_layer(name, dict(value))
        return st

    def digest(self, state: MultiscaleState) -> str:
        return text_digest(state.snapshot()["digest"])
