# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Compile-time reduced-order preview for the murine axial twin.

Runtime execution is authoritative. This preview is unchanged from v0.4.
"""

from __future__ import annotations

import math
from typing import Optional

from ...ir import SimulationProgram, SimulationResult, TrajectoryPoint, UniversalBioIr


def _primary(bio: UniversalBioIr) -> str:
    for i in bio.intents:
        if i.name == "axial_pattern":
            return i.bindings.get("primary", "unspecified")
    return "unspecified"


def _secondary(bio: UniversalBioIr) -> Optional[str]:
    for i in bio.intents:
        if i.name == "axial_pattern":
            return i.bindings.get("secondary")
    return None


def plan_simulation(bio: UniversalBioIr, model_kind: str = "mouse_axial_1d") -> SimulationProgram:
    primary = _primary(bio)
    posterior = 1.0 if primary == "tail" else 0.05
    anterior = 1.0 if primary == "head" else 0.35
    return SimulationProgram(
        program_id=bio.program_id,
        entities=["axis_bin", "Wnt", "Fgf", "RA", "Cdx", "HoxP"],
        state_variables=["wnt", "fgf", "ra", "cdx", "hox_posterior", "tail_identity"],
        equations=[
            "production gated by compiled loci present in the genotype",
            "dField/dt = gene_drive * spatial_prior - decay * Field",
        ],
        transition_rules=[
            "AXIS_INITIATE when a posterior domain crosses threshold",
            "if time >= t_end then stage=mature",
        ],
        spatial_model="1d_axis_bins",
        temporal_model="explicit_euler",
        stochastic_model="deterministic_mean_field",
        parameters={
            "k_cdx": 0.22, "k_hox": 0.20, "dt": 0.1, "t_end": 12.0, "n_bins": 21.0,
            "posterior_drive": posterior, "anterior_drive": anterior,
        },
        observations=["posterior_tail_identity", "hox_posterior_profile"],
        model_kind=model_kind,
        resolution="tissue",
    )


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-6.0 * x))


def run_simulation(plan: SimulationProgram) -> SimulationResult:
    dt = plan.parameters.get("dt", 0.1)
    t_end = plan.parameters.get("t_end", 12.0)
    n = int(plan.parameters.get("n_bins", 21))
    k_cdx = plan.parameters.get("k_cdx", 0.22)
    k_hox = plan.parameters.get("k_hox", 0.20)
    post = plan.parameters.get("posterior_drive", 1.0)
    ant = plan.parameters.get("anterior_drive", 0.35)
    wnt = [0.0] * n
    fgf = [0.0] * n
    ra = [0.0] * n
    cdx = [0.0] * n
    hox = [0.0] * n
    traj = []
    t = 0.0
    while t <= t_end + 1e-9:
        for i in range(n):
            x = i / max(n - 1, 1)
            prod_post = min(x ** 2, 1.0) * post
            prod_ant = min((1.0 - x) ** 2, 1.0) * ant
            wnt[i] += dt * (0.6 * prod_post - 0.12 * wnt[i])
            fgf[i] += dt * (0.5 * prod_post - 0.12 * fgf[i])
            ra[i] += dt * (0.55 * prod_ant - 0.12 * ra[i])
            drive = (wnt[i] + fgf[i]) * max(1.0 - ra[i], 0.0)
            cdx[i] += dt * (k_cdx * drive - 0.10 * cdx[i])
            hox[i] += dt * (k_hox * cdx[i] - 0.08 * hox[i])
        i_post = n - 1
        traj.append(TrajectoryPoint(
            time=t, axis_position=1.0, wnt=wnt[i_post], fgf=fgf[i_post], ra=ra[i_post],
            cdx=cdx[i_post], hox_posterior=hox[i_post], tail_identity=_sigmoid(hox[i_post] - 0.45),
        ))
        t += dt
    score = traj[-1].tail_identity if traj else 0.0
    return SimulationResult(
        program_id=plan.program_id,
        trajectory=traj,
        terminal_phenotype_score=score,
        matured=True,
        notes=[
            f"{plan.model_kind} n_bins={n} posterior_drive={post} anterior_drive={ant}",
            "compile-time twin; runtime engine is authoritative for V12",
        ],
    )
