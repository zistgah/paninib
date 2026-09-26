# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Two spatially separated posterior basins.

Not: if desired_tail_count == 2: tail_count = 2
Instead: two organizer sites independently cross a Hox threshold.
"""

from __future__ import annotations

import math
from typing import List

from ...simulator.anatomy import AnatomyState, AxisStructure
from ...simulator.genotype import CompiledGenotype
from ...simulator.models import ModelParams
from .axial_1d import _protein
from ...simulator.state import BiologicalState


def _present(state: BiologicalState, genotype: CompiledGenotype, symbols: List[str]) -> float:
    genes = [
        g for g in genotype.genes
        if any(s.lower() in g.artifact_id.lower() or s.lower() == g.symbol.lower() for s in symbols)
    ]
    if not genes:
        return 0.0
    on = [state.genes[g.identity].enabled for g in genes if g.identity in state.genes]
    return 1.0 if any(on) else 0.0


def react_two_basins(state: BiologicalState, genotype: CompiledGenotype, params: ModelParams) -> None:
    """2-D field sampled at two organizer sites plus a coarse grid for geometry."""
    wnt_p = _protein(state, genotype, ["Wnt3a", "Wnt"]) * _present(state, genotype, ["Wnt3a", "Wnt"])
    fgf_p = _protein(state, genotype, ["Fgf8", "Fgf"]) * _present(state, genotype, ["Fgf8", "Fgf"])
    ra_p = _protein(state, genotype, ["Raldh2", "Raldh", "Aldh1a2"]) * _present(state, genotype, ["Raldh2", "Raldh", "Aldh1a2"])
    cdx_p = _protein(state, genotype, ["Cdx2", "Cdx"]) * _present(state, genotype, ["Cdx2", "Cdx"])
    hox_p = _protein(state, genotype, ["Hoxd13", "Hox"]) * _present(state, genotype, ["Hoxd13", "Hox"])

    # Two basins in the posterior half-plane.
    sites = [(0.78, -0.22), (0.78, 0.22)]
    dt = params.dt
    hox_sites = []
    for j, (sx, sy) in enumerate(sites):
        key = f"basin_{j}"
        rec = state.anatomy.setdefault("basins", {})
        b = rec.setdefault(key, {"wnt": 0.0, "fgf": 0.0, "ra": 0.0, "cdx": 0.0, "hox": 0.0})
        # local posterior prior at this site
        post = min(sx ** 2, 1.0)
        ant = min((1.0 - sx) ** 2, 1.0)
        b["wnt"] += dt * (0.8 * post * wnt_p - params.decay_morphogen * b["wnt"])
        b["fgf"] += dt * (0.7 * post * fgf_p - params.decay_morphogen * b["fgf"])
        b["ra"] += dt * (0.7 * ant * ra_p - params.decay_morphogen * b["ra"])
        drive = (b["wnt"] * b["fgf"]) * max(1.0 - b["ra"], 0.0)
        b["cdx"] += dt * (params.k_cdx * drive * (0.2 + cdx_p) - params.decay_cdx * b["cdx"])
        b["hox"] += dt * (params.k_hox * b["cdx"] * (0.2 + hox_p) - params.decay_hox * b["hox"])
        for k in b:
            b[k] = max(0.0, b[k])
        hox_sites.append(b["hox"])

    # Keep the 1-D field as a projection of basin 0 for inspectors that still read it.
    n = params.n_bins
    if "hox" in state.fields and state.fields["hox"]:
        mean_hox = sum(hox_sites) / max(len(hox_sites), 1)
        for i in range(n):
            x = i / max(n - 1, 1)
            state.fields["hox"][i] = mean_hox * (x ** 2)


def axes_from_basins(state: BiologicalState) -> AnatomyState:
    anatomy = AnatomyState()
    basins = state.anatomy.get("basins") or {}
    sites = [(0.78, -0.22, 0.0), (0.78, 0.22, 0.0)]
    for j, key in enumerate(("basin_0", "basin_1")):
        b = basins.get(key) or {}
        hox = float(b.get("hox") or 0.0)
        score = 1.0 / (1.0 + math.exp(-6.0 * (hox - 0.45)))
        if score > 0.6:
            sx, sy, sz = sites[j]
            anatomy.axes.append(AxisStructure(
                identity=f"axis-{j+1:03d}",
                axis_type="tail",
                origin=(sx, sy, sz),
                direction=(0.0, 0.0, 1.0),
                length=min(1.0, score),
                identity_score=score,
                developmental_stage=state.stage,
                confidence=0.55,
            ))
    return anatomy
