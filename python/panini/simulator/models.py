# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Generic execution parameters and dispatch onto a registered ExecutionModel.

Numerical field equations live in domain plugins, not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .genotype import CompiledGenotype
from .state import BiologicalState
from ..registry import get_registry


@dataclass
class ModelParams:
    k_wnt: float = 0.18
    k_fgf: float = 0.16
    k_ra: float = 0.14
    k_cdx: float = 0.22
    k_hox: float = 0.20
    decay_morphogen: float = 0.12
    decay_cdx: float = 0.10
    decay_hox: float = 0.08
    dt: float = 0.1
    t_end: float = 12.0
    n_bins: int = 21
    n_cells: int = 24
    temperature: float = 37.0
    diffusion: float = 0.02
    transcription_gain: float = 0.35
    translation_gain: float = 0.40
    rna_decay: float = 0.08
    protein_decay: float = 0.06
    model_id: str = ""

    def to_dict(self) -> Dict[str, float]:
        return dict(self.__dict__)

    @staticmethod
    def from_dict(d: Dict[str, float] | None) -> "ModelParams":
        p = ModelParams()
        if not d:
            return p
        for k, v in d.items():
            if hasattr(p, k):
                setattr(p, k, type(getattr(p, k))(v))
        return p


def _exec(params: ModelParams):
    mid = params.model_id
    if not mid:
        raise RuntimeError("no execution model resolved")
    return get_registry().get_execution(mid)


def initialize_state(genotype: CompiledGenotype, params: ModelParams) -> BiologicalState:
    return _exec(params).initialize(genotype, params)


def transcribe(state: BiologicalState, genotype: CompiledGenotype, params: ModelParams) -> Dict[str, float]:
    return _exec(params).transcribe(state, genotype, params)


def translate(state: BiologicalState, genotype: CompiledGenotype, params: ModelParams) -> Dict[str, float]:
    return _exec(params).translate(state, genotype, params)


def react_fields(state: BiologicalState, genotype: CompiledGenotype, params: ModelParams) -> None:
    _exec(params).react(state, genotype, params)


def update_cells(state: BiologicalState, params: ModelParams) -> List[str]:
    return _exec(params).update_cells(state, params)


def update_development(state: BiologicalState, params: ModelParams | None = None) -> str:
    # Called from the engine with params available on the engine.
    if params is None:
        raise RuntimeError("update_development requires resolved model params")
    return _exec(params).update_development(state)


PATHWAY_MODELS: Dict[str, str] = {
    "deterministic_ODE": "explicit Euler reduced-order twin (domain plugin)",
    "stochastic_SSA": "not shipped; registered for substitution",
    "agent_based": "not shipped; registered for substitution",
    "neural_surrogate": "not shipped; registered for substitution",
    "hybrid": "event molecular + ODE field + agent-like cells (default)",
}
