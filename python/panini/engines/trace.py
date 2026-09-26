# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Artifact-level debugger traces. Causal inversion is later work."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..artifact_util import artifact_digest, text_digest


@dataclass
class TraceStep:
    index: int
    layer: str
    artifact_id: str
    digest: str
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"index": self.index, "layer": self.layer, "artifact_id": self.artifact_id, "digest": self.digest, "summary": dict(self.summary)}


class ArtifactDebugger:
    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "ArtifactDebugger", "class": "ENGINE", "mode": "artifact_trace", "causal_inversion": False}

    def build_forward(self, slices: List[Dict[str, Any]]) -> List[TraceStep]:
        steps = []
        for i, item in enumerate(slices):
            digest = str(item.get("digest") or text_digest(str(item.get("id") or i)))
            steps.append(TraceStep(index=i, layer=str(item.get("layer") or "unknown"), artifact_id=str(item.get("id") or f"a{i}"), digest=digest, summary={k: v for k, v in item.items() if k not in {"digest", "layer", "id"}}))
        return steps

    def inspect_reverse(self, steps: List[TraceStep], start_layer: str) -> List[TraceStep]:
        acc: List[TraceStep] = []
        seen = False
        for step in reversed(steps):
            if step.layer == start_layer:
                seen = True
            if seen:
                acc.append(step)
        return acc

    def explain(self, steps: List[TraceStep]) -> Dict[str, Any]:
        payload = {"forward": [s.to_dict() for s in steps], "layers": [s.layer for s in steps], "note": "artifact-level trace only; causal inversion not implemented"}
        payload["digest"] = artifact_digest({"layers": payload["layers"]})
        return payload
