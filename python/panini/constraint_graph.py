# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Typed multi-constraint / polygenic dependency graph.

v0.8 does not implement quantitative genetics. It implements executable
graph semantics so later engines can attach without rewriting the core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

from .artifact_util import artifact_digest


EDGE_KINDS = (
    "DEPENDENCY",
    "JOINT",
    "CONFLICT",
    "EVIDENCE_DEPENDENCY",
    "RESOLUTION_DEPENDENCY",
    "PROVIDER_REQUIREMENT",
)


@dataclass
class GraphEdge:
    source: str
    target: str
    kind: str
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"source": self.source, "target": self.target, "kind": self.kind, "note": self.note}


@dataclass
class ConstraintNode:
    constraint_id: str
    status: str
    intent_name: str = ""
    required_provider: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "status": self.status,
            "intent_name": self.intent_name,
            "required_provider": self.required_provider,
        }


@dataclass
class ConstraintGraph:
    program_id: str
    nodes: List[ConstraintNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)
    conflicts: List[GraphEdge] = field(default_factory=list)
    resolution_order: List[str] = field(default_factory=list)
    graph_status: str = "EMPTY"

    def add_node(self, node: ConstraintNode) -> None:
        self.nodes.append(node)

    def add_edge(self, edge: GraphEdge) -> None:
        if edge.kind not in EDGE_KINDS:
            raise ValueError(f"unknown edge kind {edge.kind}")
        self.edges.append(edge)
        if edge.kind == "CONFLICT":
            self.conflicts.append(edge)

    def node_map(self) -> Dict[str, ConstraintNode]:
        return {n.constraint_id: n for n in self.nodes}

    def blocked(self) -> List[str]:
        by_id = self.node_map()
        blocked_ids: List[str] = []
        for edge in self.edges:
            if edge.kind not in {"DEPENDENCY", "RESOLUTION_DEPENDENCY", "EVIDENCE_DEPENDENCY"}:
                continue
            src = by_id.get(edge.source)
            dst = by_id.get(edge.target)
            if src and dst and src.status == "UNRESOLVED" and dst.status != "UNRESOLVED":
                continue
            if src and src.status == "UNRESOLVED":
                blocked_ids.append(edge.target)
        return sorted(set(blocked_ids))

    def classify(self) -> str:
        statuses = {n.status for n in self.nodes}
        if not self.nodes:
            self.graph_status = "EMPTY"
        elif self.conflicts:
            self.graph_status = "CONFLICTING"
        elif statuses <= {"RESOLVED", "USER_ASSERTED", "MODEL_DERIVED"}:
            self.graph_status = "ALL_RESOLVED"
        elif "UNRESOLVED" in statuses and statuses & {"RESOLVED", "USER_ASSERTED", "MODEL_DERIVED"}:
            if self.blocked():
                self.graph_status = "DEPENDENCY_BLOCKED"
            else:
                self.graph_status = "PARTIALLY_RESOLVED"
        elif statuses == {"UNRESOLVED"}:
            self.graph_status = "UNSUPPORTED"
        else:
            self.graph_status = "PARTIALLY_RESOLVED"
        return self.graph_status

    def compute_order(self) -> List[str]:
        incoming: Dict[str, Set[str]] = {n.constraint_id: set() for n in self.nodes}
        for edge in self.edges:
            if edge.kind in {"DEPENDENCY", "RESOLUTION_DEPENDENCY", "EVIDENCE_DEPENDENCY", "JOINT"}:
                if edge.target in incoming:
                    incoming[edge.target].add(edge.source)
        ordered: List[str] = []
        remaining = set(incoming)
        while remaining:
            ready = [cid for cid in remaining if not (incoming[cid] & remaining)]
            if not ready:
                ordered.extend(sorted(remaining))
                break
            ready.sort()
            pick = ready[0]
            ordered.append(pick)
            remaining.remove(pick)
        self.resolution_order = ordered
        return ordered

    def to_dict(self) -> Dict[str, Any]:
        self.classify()
        self.compute_order()
        payload = {
            "program_id": self.program_id,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "conflicts": [e.to_dict() for e in self.conflicts],
            "resolution_order": list(self.resolution_order),
            "blocked": self.blocked(),
            "graph_status": self.graph_status,
        }
        payload["digest"] = artifact_digest(payload)
        return payload


def graph_from_constraints(
    program_id: str,
    constraints: Iterable[Any],
    extra_edges: Optional[List[GraphEdge]] = None,
) -> ConstraintGraph:
    graph = ConstraintGraph(program_id=program_id)
    for c in constraints:
        required = None
        bindings = getattr(c, "bindings", {}) or {}
        required = bindings.get("requires_provider") or getattr(c, "provider", None)
        graph.add_node(ConstraintNode(
            constraint_id=c.constraint_id,
            status=c.status,
            intent_name=getattr(c, "intent_name", ""),
            required_provider=required if required else None,
        ))
        depends = bindings.get("depends_on") or bindings.get("requires")
        if depends:
            for dep in str(depends).split("+"):
                dep = dep.strip()
                if dep:
                    kind = "JOINT" if "+" in str(depends) else "DEPENDENCY"
                    graph.add_edge(GraphEdge(source=dep, target=c.constraint_id, kind="DEPENDENCY", note=f"declared {depends}"))
        conflicts = bindings.get("conflicts_with")
        if conflicts:
            for other in str(conflicts).split(","):
                other = other.strip()
                if other:
                    graph.add_edge(GraphEdge(source=c.constraint_id, target=other, kind="CONFLICT", note="declared conflict"))
        if bindings.get("requires_provider"):
            graph.add_edge(GraphEdge(
                source=c.constraint_id,
                target=c.constraint_id,
                kind="PROVIDER_REQUIREMENT",
                note=str(bindings.get("requires_provider")),
            ))
    for edge in extra_edges or []:
        graph.add_edge(edge)
    graph.classify()
    graph.compute_order()
    return graph
