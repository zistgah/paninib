# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Addressable artifact graph spanning compile, realize, simulate, and validate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .artifact_util import artifact_digest


@dataclass
class ArtifactNode:
    node_id: str
    kind: str
    digest: str
    refs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"node_id": self.node_id, "kind": self.kind, "digest": self.digest, "refs": dict(self.refs)}


@dataclass
class ArtifactEdge:
    source: str
    target: str
    relation: str

    def to_dict(self) -> Dict[str, Any]:
        return {"source": self.source, "target": self.target, "relation": self.relation}


@dataclass
class ArtifactGraph:
    graph_id: str
    nodes: List[ArtifactNode] = field(default_factory=list)
    edges: List[ArtifactEdge] = field(default_factory=list)

    def add(self, node_id: str, kind: str, digest: str, **refs: Any) -> None:
        self.nodes.append(ArtifactNode(node_id, kind, digest, refs))

    def link(self, source: str, target: str, relation: str) -> None:
        self.edges.append(ArtifactEdge(source, target, relation))

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "graph_id": self.graph_id,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }
        payload["digest"] = artifact_digest(payload)
        return payload


def build_dual_path_graph(
    *,
    source_digest: str,
    semantic_digest: str,
    constraint_digest: str,
    resolution_digest: str,
    design_digest: str,
    physical_digest: str,
    execution_digest: str,
    phenotype_digest: str,
    geometry_digest: str,
    observation_digest: str,
    evidence_digest: str,
    claim_digest: str,
) -> ArtifactGraph:
    g = ArtifactGraph(graph_id="ag_" + design_digest[:12])
    g.add("source", "source", source_digest)
    g.add("semantic", "semantic_ir", semantic_digest)
    g.add("constraint", "constraint", constraint_digest)
    g.add("resolution", "resolution", resolution_digest)
    g.add("design", "genotype_design", design_digest)
    g.add("physical", "physical_realization", physical_digest)
    g.add("execution", "execution_ir", execution_digest)
    g.add("phenotype", "phenotype", phenotype_digest)
    g.add("geometry", "geometry", geometry_digest)
    g.add("observation", "observation", observation_digest)
    g.add("evidence", "evidence", evidence_digest)
    g.add("claim", "claim", claim_digest)
    g.link("source", "semantic", "lowers")
    g.link("semantic", "constraint", "decomposes")
    g.link("constraint", "resolution", "resolves")
    g.link("resolution", "design", "designs")
    g.link("design", "physical", "realizes")
    g.link("design", "execution", "executes")
    g.link("execution", "phenotype", "projects")
    g.link("phenotype", "geometry", "spatializes")
    g.link("phenotype", "observation", "observed_as")
    g.link("observation", "evidence", "supports")
    g.link("evidence", "claim", "evaluates")
    return g
