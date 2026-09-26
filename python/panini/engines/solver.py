# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""First solver over ConstraintGraph. Not a quantitative-genetics solver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..artifact_util import artifact_digest, provenance_block
from ..constraint_graph import ConstraintGraph
from ..version import COMPILER_VERSION
from .coverage import coverage_from_nodes

RESOLVED_STATUSES = {"RESOLVED", "USER_ASSERTED", "MODEL_DERIVED"}


@dataclass
class ResolutionPlan:
    ordered_constraints: List[str]
    resolved_constraints: List[str]
    blocked_constraints: List[str]
    candidate_combinations: List[List[str]]
    conflicts: List[Dict[str, Any]]
    unresolved_symbols: List[str]
    coverage: Dict[str, Any]
    graph_status: str
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = {"ordered_constraints": list(self.ordered_constraints), "resolved_constraints": list(self.resolved_constraints), "blocked_constraints": list(self.blocked_constraints), "candidate_combinations": [list(c) for c in self.candidate_combinations], "conflicts": list(self.conflicts), "unresolved_symbols": list(self.unresolved_symbols), "coverage": dict(self.coverage), "graph_status": self.graph_status, "notes": list(self.notes)}
        payload["digest"] = artifact_digest(payload)
        payload["provenance"] = provenance_block(layer="constraint.solver", compiler_version=COMPILER_VERSION, provider="panini.engines.solver", model_id="solver.v09", model_version="0.9.0")
        return payload


class ConstraintSolver:
    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "ConstraintSolver", "class": "ENGINE", "supports": ["independent", "dependent", "joint", "conflicts", "provider_requirements", "partial"], "scientific_model": False, "note": "computational substrate for a future quantitative-genetics solver"}

    def solve(self, graph: ConstraintGraph) -> ResolutionPlan:
        graph.classify()
        order = graph.compute_order()
        blocked = graph.blocked()
        resolved = [n.constraint_id for n in graph.nodes if n.status in RESOLVED_STATUSES]
        unresolved = [n.constraint_id for n in graph.nodes if n.status == "UNRESOLVED"]
        incoming = {n.constraint_id: [] for n in graph.nodes}
        for e in graph.edges:
            if e.kind in {"DEPENDENCY", "RESOLUTION_DEPENDENCY", "EVIDENCE_DEPENDENCY", "JOINT"}:
                incoming.setdefault(e.target, []).append(e.source)
        independents = [cid for cid, srcs in incoming.items() if not srcs]
        combinations = []
        if independents:
            combinations.append(independents)
        if resolved:
            combinations.append(resolved)
        notes = []
        if graph.conflicts:
            notes.append("conflicts present; joint realization is blocked")
        if blocked:
            notes.append("dependency-blocked constraints require upstream resolution")
        return ResolutionPlan(ordered_constraints=order, resolved_constraints=resolved, blocked_constraints=list(blocked), candidate_combinations=combinations, conflicts=[e.to_dict() for e in graph.conflicts], unresolved_symbols=unresolved, coverage=coverage_from_nodes(graph.nodes), graph_status=graph.graph_status, notes=notes)
