"""Observation model Y = H(S, θ_obs, ε). Separate from biology."""

from __future__ import annotations

from typing import Any, Dict

from .state import BiologicalState


def render(state: BiologicalState, instrument: str = "schematic_axis", noise: float = 0.0) -> Dict[str, Any]:
    pheno = state.phenotype_projection()
    field = {k: list(v) for k, v in state.fields.items()}
    if noise:
        # observation noise is recorded, not silently baked into S
        field["_noise"] = noise
    return {
        "instrument": instrument,
        "theta_obs": {"noise": noise, "modality": instrument},
        "channels": {
            "brightfield": {"anatomy": pheno["anatomical"]},
            "fluorescence": {"hox": field.get("hox"), "cdx": field.get("cdx")},
            "confocal": {"cells": [{"id": c.identity, "type": c.cell_type, "x": c.position} for c in state.cells]},
            "schematic_axis": field,
        }.get(instrument, {"anatomy": pheno["anatomical"], "field": field}),
        "note": "observation is a projection; a mismatch here may be optical rather than biological",
    }
