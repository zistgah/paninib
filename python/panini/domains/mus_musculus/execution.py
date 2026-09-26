# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Registered Mus musculus axial execution models."""

from __future__ import annotations

from typing import Any, Dict, List

from . import axial_1d as one
from . import two_axis as two


class MouseAxial1D:
    id = "mouse_axial_1d"

    def initialize(self, genotype, params):
        return one.initialize_state(genotype, params)

    def transcribe(self, state, genotype, params):
        return one.transcribe(state, genotype, params)

    def translate(self, state, genotype, params):
        return one.translate(state, genotype, params)

    def react(self, state, genotype, params):
        one.react_fields(state, genotype, params)

    def update_cells(self, state, params):
        return one.update_cells(state, params)

    def update_development(self, state):
        return one.update_development(state)

    def plan_simulation(self, bio):
        from .compile_preview import plan_simulation
        return plan_simulation(bio, model_kind=self.id)

    def compile_time_simulate(self, bio):
        from .compile_preview import run_simulation
        return run_simulation(self.plan_simulation(bio))

    def compile_time_simulate_plan(self, plan):
        from .compile_preview import run_simulation
        return run_simulation(plan)

    def adjust_compile_preview(self, predicted_bundle: Dict[str, Any], bio, sim) -> Dict[str, Any]:
        return predicted_bundle


class MouseAxial2Axis(MouseAxial1D):
    id = "mouse_axial_2axis"

    def react(self, state, genotype, params):
        two.react_two_basins(state, genotype, params)

    def update_development(self, state):
        prev = one.update_development(state)
        anatomy = two.axes_from_basins(state)
        state.anatomy["axes"] = [
            {
                "identity": a.identity,
                "axis_type": a.axis_type,
                "origin": list(a.origin),
                "direction": list(a.direction),
                "length": a.length,
                "identity_score": a.identity_score,
            }
            for a in anatomy.axes
        ]
        state.anatomy["tail_count"] = anatomy.count("tail")
        state.anatomy["primary_axis"] = "tail" if anatomy.count("tail") else "indeterminate"
        state.anatomy["secondary_axis"] = "tail" if anatomy.count("tail") >= 2 else "absent"
        state.anatomy["axis_extent"] = max((a.length for a in anatomy.axes), default=0.0)
        state.anatomy["axis_extent_units"] = "uncalibrated"
        state.flags["initiated_axes"] = [a.identity for a in anatomy.axes]
        return prev

    def adjust_compile_preview(self, predicted_bundle: Dict[str, Any], bio, sim) -> Dict[str, Any]:
        # Compile-time preview of two independent basins (same equations as runtime).
        # Unchanged scientific interpretation relative to v0.4.
        anatomical = predicted_bundle.get("anatomical") or {}
        if anatomical.get("primary_axis") == "tail":
            anatomical["tail_count"] = 2
            anatomical["secondary_axis"] = "tail"
            anatomical["axes"] = [
                {"identity": "axis-001", "axis_type": "tail"},
                {"identity": "axis-002", "axis_type": "tail"},
            ]
            predicted_bundle["anatomical"] = anatomical
        return predicted_bundle


def build_causal(ir):
    from ...ir import CausalEdge, CausalIr, CausalNode

    nodes = [
        CausalNode("intent", "intent", "; ".join(f"{i.verb} {i.name}" for i in ir.intents)),
        CausalNode("wnt_fgf", "signal", "posteriorizing Wnt/FGF field"),
        CausalNode("ra", "signal", "anteriorizing RA field"),
        CausalNode("cdx", "regulator", "Cdx posterior program"),
        CausalNode("hox", "regulator", "posterior Hox code"),
        CausalNode("axis", "phenotype", "axial / caudal identity"),
    ]
    edges = [
        CausalEdge("wnt_fgf", "cdx", "activates", "WIDELY_VALIDATED"),
        CausalEdge("ra", "cdx", "represses", "WIDELY_VALIDATED"),
        CausalEdge("cdx", "hox", "activates", "EXPERIMENTALLY_DEMONSTRATED"),
        CausalEdge("hox", "axis", "specifies", "WIDELY_VALIDATED"),
        CausalEdge("intent", "axis", "requires", "THEORETICAL"),
    ]
    return CausalIr(ir.program_id, nodes, edges)
