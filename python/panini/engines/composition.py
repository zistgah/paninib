# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Explicit composition: biochemical → field → cellular → developmental → phenotype."""

from __future__ import annotations

from typing import Any, Dict, List

from ..artifact_util import artifact_digest, provenance_block
from ..version import COMPILER_VERSION
from .biochemical import BiochemicalEngine, fixture_abc
from .cellular import CellularEngine
from .developmental import DevelopmentalEngine
from .phenotype_engine import PhenotypeEngine
from .reaction_diffusion import fixture_source_decay
from .trace import ArtifactDebugger


def compose_synthetic_stack(*, dt: float = 0.05, steps: int = 8, seed: int = 3) -> Dict[str, Any]:
    transitions: List[Dict[str, Any]] = []
    bio = BiochemicalEngine(fixture_abc())
    traj = bio.integrate(dt=dt, t_end=dt * steps, seed=seed)
    mol = bio.final_observables(traj)
    transitions.append({"from": "biochemical", "to": "field", "observables": mol})
    field = fixture_source_decay()
    transitions.append({"from": "field", "to": "cellular", "digest": field.get("digest")})
    cells = CellularEngine().run_fixture()
    transitions.append({"from": "cellular", "to": "developmental", "n_cells": len(cells["cells"])})
    dev = DevelopmentalEngine().run_spatial_fixture(steps=steps, dt=dt)
    transitions.append({"from": "developmental", "to": "phenotype", "final": dev.get("final")})
    pheno = PhenotypeEngine()
    predicted = pheno.from_developmental(dev["final"], kind="predicted")
    bundle = pheno.bundle(desired={"pattern": "synthetic"}, predicted=predicted)
    steps_trace = ArtifactDebugger().build_forward([
        {"layer": "biochemical", "id": "bio", "digest": traj.to_dict()["digest"]},
        {"layer": "field", "id": "rd", "digest": field.get("digest")},
        {"layer": "cellular", "id": "cell", "digest": str(len(cells["cells"]))},
        {"layer": "developmental", "id": "dev", "digest": dev.get("digest")},
        {"layer": "phenotype", "id": "ph", "digest": bundle["digest"]},
    ])
    payload = {
        "composition": ["biochemical", "field", "cellular", "developmental", "phenotype"],
        "transitions": transitions,
        "biochemical": mol,
        "field_digest": field.get("digest"),
        "cellular": {"n_cells": len(cells["cells"])},
        "developmental": dev.get("final"),
        "phenotype_bundle": bundle,
        "trace": ArtifactDebugger().explain(steps_trace),
        "provenance": provenance_block(
            layer="composition.synthetic",
            compiler_version=COMPILER_VERSION,
            provider="panini.engines.composition",
            model_id="synthetic.stack",
            model_version="1.0.0",
            random_seed=seed,
        ),
        "note": "synthetic fixture composition; not a biological mechanism claim",
    }
    payload["digest"] = artifact_digest({"mol": mol, "field": field.get("digest"), "pheno": bundle["digest"]})
    return payload
