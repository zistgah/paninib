# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Expose the existing mouse axial models through generic state layers.

No new mouse biology is invented. The reduced-order 1-D / two-axis
models remain domain-owned. This module only maps their existing
state onto MultiscaleState + phenotype + geometry contracts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from ...artifact_util import artifact_digest, provenance_block
from ...version import COMPILER_VERSION
from ...engines.maturity import profile_for_axial_twin
from ...engines.phenotype_engine import PhenotypeEngine
from ...engines.state import MultiscaleState, MultiscaleStateEngine


def _safe_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return dict(obj)
    out: Dict[str, Any] = {}
    for name in ("fields", "proteins", "transcripts", "anatomy", "cells", "flags", "stage", "time", "anatomical"):
        if hasattr(obj, name):
            val = getattr(obj, name)
            if isinstance(val, dict):
                out[name] = dict(val)
            else:
                out[name] = val
    return out


def axial_state_to_multiscale(runtime_state: Any, *, model_id: str, seed: int = 1) -> MultiscaleState:
    raw = _safe_dict(runtime_state)
    anatomy = raw.get("anatomy") or raw.get("anatomical") or {}
    fields = raw.get("fields") or {}
    proteins = raw.get("proteins") or raw.get("transcripts") or {}
    flags = raw.get("flags") or {}
    eng = MultiscaleStateEngine(model_id=model_id, model_version="1.0.0")
    st = eng.initialize(
        molecular=dict(proteins) if isinstance(proteins, dict) else {},
        regulatory=dict(flags) if isinstance(flags, dict) else {},
        cellular={"n_cells": len(raw.get("cells") or [])},
        spatial=dict(fields) if isinstance(fields, dict) else {},
        developmental={"stage": raw.get("stage") or anatomy.get("stage")},
        anatomical=dict(anatomy) if isinstance(anatomy, dict) else {},
        seed=seed,
    )
    st.model_id = model_id
    st.time = float(raw.get("time") or 0.0)
    st.provenance = provenance_block(
        layer="domain.bridge",
        compiler_version=COMPILER_VERSION,
        provider="panini.engines.mouse_bridge",
        model_id=model_id,
        model_version="1.0.0",
        random_seed=seed,
    )
    return st


def project_axial_stack(runtime_state: Any, *, model_id: str = "mouse_axial_1d") -> Dict[str, Any]:
    st = axial_state_to_multiscale(runtime_state, model_id=model_id)
    anatomy = dict(st.anatomical)
    pheno = PhenotypeEngine()
    predicted = pheno.from_anatomical(anatomy, kind="predicted")
    desired = pheno.desired({"tail_count": 2})
    bundle = pheno.bundle(desired=desired.values, predicted=predicted)
    geom_params = {
        "tail_count": int(anatomy.get("tail_count") or 0),
        "length": float(anatomy.get("axis_extent") or anatomy.get("tail_length") or anatomy.get("tail_length_mm") or 1.0),
        "radius": 0.05,
        "units": "uncalibrated",
        "calibration_status": "UNCALIBRATED",
        "coordinate_system": "model-local",
        "source_phenotype": predicted.to_dict()["digest"],
        "model": model_id,
    }
    maturity = profile_for_axial_twin()
    payload = {
        "model_id": model_id,
        "state": st.snapshot(),
        "phenotype_bundle": bundle,
        "geometry_params": geom_params,
        "maturity": maturity.to_dict(),
        "note": "architectural integration of existing axial model; no new biology",
    }
    payload["digest"] = artifact_digest({"model_id": model_id, "anatomy": anatomy, "maturity": maturity.level})
    return payload


def run_axial_through_generic(*, two_axis: bool = False, seed: int = 1) -> Dict[str, Any]:
    """Compile + simulate the golden mouse program, then lift state."""
    from ...pipeline import CompileOptions, compile_source
    from ...simulator.api import Simulator
    from ...simulator.models import ModelParams

    root = Path(__file__).resolve().parents[4]
    src_path = root / "examples" / "mouse_axial.panini"
    src = src_path.read_text()
    model_id = "mouse_axial_2axis" if two_axis else "mouse_axial_1d"
    compiled = compile_source(src, CompileOptions(model=model_id))
    params = ModelParams()
    params.model_id = model_id
    sim = Simulator(payload=compiled.payload, params=params, seed=seed)
    run = sim.run()
    phenotype = run.phenotype if isinstance(run.phenotype, dict) else {}
    lifted = project_axial_stack(
        {
            "anatomical": phenotype.get("anatomical") or phenotype,
            "stage": (phenotype.get("anatomical") or {}).get("stage") or phenotype.get("stage"),
            "time": getattr(run, "terminal_state", {}) and (run.terminal_state or {}).get("time"),
        },
        model_id=model_id,
    )
    lifted["simulation_run_id"] = getattr(run, "run_id", "")
    lifted["target"] = (compiled.payload.get("verdict") or {}).get("target_phenotype")
    lifted["two_axis"] = two_axis
    lifted["seed"] = seed
    lifted["genotype_status"] = ((compiled.payload.get("genotype_design") or {}).get("status")
                                 or compiled.payload.get("status"))
    return lifted
