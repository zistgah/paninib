"""Biological assertions. Failures become debugger events."""

from __future__ import annotations

from typing import List

from .state import BiologicalState


def run_assertions(state: BiologicalState) -> List[str]:
    fails: List[str] = []
    if any(g.copy_number < 0 for g in state.genes.values()):
        fails.append("ASSERT copy_number >= 0")
    for name, q in state.protein.items():
        if q.value < -1e-9:
            fails.append(f"ASSERT protein_concentration >= 0 ({name})")
    for cell in state.cells:
        if cell.volume <= 0:
            fails.append(f"ASSERT cell_volume > 0 ({cell.identity})")
    legal = {
        "early_streak", "late_streak", "tail_bud", "axis_extension", "mature", "indeterminate",
        "gastrula",
    }
    if state.stage not in legal:
        fails.append(f"ASSERT developmental_state_transition_is_legal ({state.stage})")
    if state.molecular.get("energy") and state.molecular["energy"].value < 0:
        fails.append("ASSERT energy_state >= 0")
    return fails
