"""Hybrid multiscale models used by the execution engine.

v0.2 ships one executable fidelity: a reduced-order murine axial twin
(Wnt/FGF/RA → Cdx → posterior Hox → tail identity) driven by the compiled
genotype rather than a black-box sequence model.

Other PathwayModel kinds (SSA, agent, neural surrogate) are registered as
substitutable backends so the same genotype can be rerun at different fidelity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List

from ...simulator.genotype import CompiledGenotype, Gene
from ...simulator.models import ModelParams
from ...simulator.state import BiologicalState, CellRecord, GeneState, Quantity


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-6.0 * x))


def _gene_drive(g: Gene) -> float:
    table = {
        "posteriorizing_signal": 1.0,
        "anteriorizing_countergradient": 1.0,
        "posterior_identity_program": 1.1,
        "module": 0.5,
    }
    return table.get(g.role, 0.6)


def initialize_state(genotype: CompiledGenotype, params: ModelParams) -> BiologicalState:
    s = BiologicalState(time=0.0, step=0, stage="early_streak")
    s.environment = {
        "temperature": params.temperature,
        "nutrients": 1.0,
        "oxygen": 1.0,
    }
    s.spatial = {"backend": "1d_axis_bins", "n_bins": params.n_bins}
    n = params.n_bins
    s.fields = {
        "wnt": [0.0] * n,
        "fgf": [0.0] * n,
        "ra": [0.0] * n,
        "cdx": [0.0] * n,
        "hox": [0.0] * n,
    }
    for g in genotype.genes:
        s.genes[g.identity] = GeneState(
            identity=g.identity,
            locus=g.locus.identity,
            kind=g.locus.kind,
            enabled=True,
            copy_number=g.copy_number,
            expression_rate=0.0,
            transcription_rate=0.0,
            context=g.locus.context,
            source_cisc=list(g.source_cisc),
            source_risc=list(g.source_risc),
            source_micro=list(g.source_micro),
            source_intent=g.source_intent,
        )
        s.rna[g.identity] = Quantity(0.0, "au", 0.05, source=g.artifact_id)
        s.protein[g.identity] = Quantity(0.0, "au", 0.08, source=g.artifact_id)

    for name in ("wnt", "fgf", "ra", "cdx", "hox_posterior", "tail_identity", "energy"):
        s.molecular[name] = Quantity(0.0 if name != "energy" else 1.0, "au", 0.1)

    s.cells = []
    for i in range(params.n_cells):
        x = i / max(params.n_cells - 1, 1)
        kind = "anterior_progenitor" if x < 0.33 else "trunk_progenitor" if x < 0.66 else "nmps"
        s.cells.append(CellRecord(
            identity=f"C{i:05d}",
            cell_type=kind,
            position=x,
            lineage="axial_progenitor",
            signals={},
        ))
    s.tissue = {
        "axis_bins": n,
        "caudal_extension": 0.0,
        "boundary_formed": False,
    }
    s.anatomy = {
        "tail_count": 0,
        "primary_axis": "indeterminate",
        "secondary_axis": "indeterminate",
    }
    s.flags = {
        "matured": False,
        "assertions_failed": [],
    }
    return s


def gene_by_role(genotype: CompiledGenotype, role_substr: str) -> List[Gene]:
    return [g for g in genotype.genes if role_substr in g.role or role_substr.lower() in g.symbol.lower()]


def transcribe(state: BiologicalState, genotype: CompiledGenotype, params: ModelParams) -> Dict[str, float]:
    """Stochastic-mean transcription: RNA increases from enabled loci."""
    delta = {}
    x_post = 0.85
    for g in genotype.genes:
        gs = state.genes.get(g.identity)
        if gs is None or not gs.enabled:
            continue
        drive = _gene_drive(g) * gs.copy_number * params.transcription_gain
        # Bounded role cue. Live field must not open a transcription feedback explosion.
        if "posterior" in g.role or g.symbol.lower() in {"wnt3a", "fgf8", "cdx2", "hoxd13"}:
            cue = 0.85
        elif "anterior" in g.role or "Raldh" in g.symbol:
            cue = 0.70
        else:
            cue = 0.45
        rate = drive * cue * (1.2 if state.environment.get("temperature", 37) > 35 else 0.7)
        gs.transcription_rate = rate
        gs.expression_rate = rate
        rna = state.rna[g.identity]
        produced = rate * params.dt
        decayed = params.rna_decay * rna.value * params.dt
        rna.value = max(0.0, rna.value + produced - decayed)
        delta[g.identity] = produced - decayed
    return delta


def translate(state: BiologicalState, genotype: CompiledGenotype, params: ModelParams) -> Dict[str, float]:
    delta = {}
    for g in genotype.genes:
        if g.identity not in state.protein:
            continue
        gs = state.genes.get(g.identity)
        if gs is None or not gs.enabled:
            continue
        rna = state.rna[g.identity].value
        prot = state.protein[g.identity]
        produced = params.translation_gain * rna * params.dt
        decayed = params.protein_decay * prot.value * params.dt
        prot.value = max(0.0, prot.value + produced - decayed)
        delta[g.identity] = produced - decayed
    return delta


def _protein(state: BiologicalState, genotype: CompiledGenotype, symbols: List[str]) -> float:
    total = 0.0
    for g in genotype.genes:
        if g.symbol.lower() in {s.lower() for s in symbols} or any(s.lower() in g.artifact_id.lower() for s in symbols):
            total += state.protein.get(g.identity, Quantity(0)).value
    return total


def react_fields(state: BiologicalState, genotype: CompiledGenotype, params: ModelParams) -> None:
    """Explicit Euler on the 1-D axial morphogen field, gated by gene products."""
    n = params.n_bins
    wnt, fgf, ra, cdx, hox = (state.fields[k] for k in ("wnt", "fgf", "ra", "cdx", "hox"))

    def present(symbols: List[str]) -> float:
        genes = [g for g in genotype.genes if any(s.lower() in g.artifact_id.lower() or s.lower() == g.symbol.lower() for s in symbols)]
        if not genes:
            return 0.0
        on = [state.genes[g.identity].enabled for g in genes if g.identity in state.genes]
        return 1.0 if any(on) else 0.0

    wnt_p = _protein(state, genotype, ["Wnt3a", "Wnt"]) * present(["Wnt3a", "Wnt"])
    fgf_p = _protein(state, genotype, ["Fgf8", "Fgf"]) * present(["Fgf8", "Fgf"])
    ra_p = _protein(state, genotype, ["Raldh2", "Raldh", "Aldh1a2"]) * present(["Raldh2", "Raldh", "Aldh1a2"])
    cdx_p = _protein(state, genotype, ["Cdx2", "Cdx"]) * present(["Cdx2", "Cdx"])
    hox_p = _protein(state, genotype, ["Hoxd13", "Hox"]) * present(["Hoxd13", "Hox"])

    dt = params.dt
    for i in range(n):
        x = i / max(n - 1, 1)
        prod_post = min(x ** 2, 1.0)
        prod_ant = min((1.0 - x) ** 2, 1.0)
        wnt[i] += dt * (0.8 * prod_post * wnt_p - params.decay_morphogen * wnt[i])
        fgf[i] += dt * (0.7 * prod_post * fgf_p - params.decay_morphogen * fgf[i])
        ra[i] += dt * (0.7 * prod_ant * ra_p - params.decay_morphogen * ra[i])
        drive = (wnt[i] * fgf[i]) * max(1.0 - ra[i], 0.0)
        cdx[i] += dt * (params.k_cdx * drive * (0.2 + cdx_p) - params.decay_cdx * cdx[i])
        hox[i] += dt * (params.k_hox * cdx[i] * (0.2 + hox_p) - params.decay_hox * hox[i])
        for arr in (wnt, fgf, ra, cdx, hox):
            arr[i] = max(0.0, arr[i])

    if params.diffusion > 0:
        for arr in (wnt, fgf, ra):
            nxt = arr[:]
            for i in range(1, n - 1):
                nxt[i] = arr[i] + params.diffusion * (arr[i - 1] - 2 * arr[i] + arr[i + 1])
            arr[:] = nxt

    i_post = n - 1
    state.molecular["wnt"].value = wnt[i_post]
    state.molecular["fgf"].value = fgf[i_post]
    state.molecular["ra"].value = ra[0]
    state.molecular["cdx"].value = cdx[i_post]
    state.molecular["hox_posterior"].value = hox[i_post]
    state.molecular["tail_identity"].value = sigmoid(hox[i_post] - 0.45)
    energy = state.molecular["energy"].value
    state.molecular["energy"].value = max(0.2, energy - 0.002 * dt + 0.002 * dt)


def update_cells(state: BiologicalState, params: ModelParams) -> List[str]:
    """Map field onto cell types; return identities that changed type."""
    changed = []
    n = max(len(state.fields.get("hox", [])), 1)
    for cell in state.cells:
        idx = min(n - 1, max(0, int(round(cell.position * (n - 1)))))
        w = state.fields["wnt"][idx] if state.fields.get("wnt") else 0.0
        h = state.fields["hox"][idx] if state.fields.get("hox") else 0.0
        r = state.fields["ra"][idx] if state.fields.get("ra") else 0.0
        cell.signals = {"wnt": w, "hox": h, "ra": r}
        prev = cell.cell_type
        if h > 0.55 and cell.position > 0.66:
            cell.cell_type = "somite" if h > 0.9 else "nmps"
        elif r > 0.4 and cell.position < 0.33:
            cell.cell_type = "anterior_neural"
        elif cell.position < 0.66:
            cell.cell_type = "trunk_progenitor"
        if cell.cell_type != prev:
            changed.append(cell.identity)
    caudal = sum(1 for c in state.cells if c.cell_type in {"nmps", "somite"})
    state.tissue["caudal_extension"] = caudal / max(len(state.cells), 1)
    state.tissue["boundary_formed"] = state.tissue["caudal_extension"] > 0.2
    return changed


def update_development(state: BiologicalState) -> str:
    score = state.molecular["tail_identity"].value
    t = state.time
    prev = state.stage
    if t < 2.0:
        state.stage = "early_streak"
    elif t < 5.0:
        state.stage = "late_streak"
    elif t < 8.0:
        state.stage = "tail_bud" if score > 0.35 else "axis_extension"
    elif score > 0.6 and t >= 11.5:
        state.stage = "mature"
        state.flags["matured"] = True
    else:
        state.stage = "axis_extension" if score > 0.4 else "indeterminate"
    tail = 1 if score > 0.6 else 0
    state.anatomy["tail_count"] = tail
    # No millimetre figure. The 1-D twin has no calibrated length scale.
    state.anatomy["axis_extent"] = round(min(1.0, score / 0.85), 3)
    state.anatomy["axis_extent_units"] = "uncalibrated"
    state.anatomy["primary_axis"] = "tail" if score > 0.6 else ("head" if score < 0.35 else "indeterminate")
    state.anatomy["secondary_axis"] = "absent"
    state.anatomy["head_identity"] = score < 0.35
    return prev


