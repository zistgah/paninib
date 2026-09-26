# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Configurable provider routing. Biological semantics do not hard-code order."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .artifact_util import artifact_digest


DEFAULT_RESOLUTION_ORDER = (
    "user_assertion",
    "knowledge_mapping",
    "deterministic_resolver",
    "association_guard",
    "generative_provider",
)


@dataclass
class RouteStep:
    step_id: str
    provider: str
    kind: str
    available: bool
    invoked: bool
    outcome: str
    detail: str = ""
    artifact_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "provider": self.provider,
            "kind": self.kind,
            "available": self.available,
            "invoked": self.invoked,
            "outcome": self.outcome,
            "detail": self.detail,
            "artifact_refs": list(self.artifact_refs),
        }


@dataclass
class RouteTrace:
    constraint_id: str
    order: List[str]
    steps: List[RouteStep] = field(default_factory=list)
    terminal: str = "UNRESOLVED"

    def add(self, step: RouteStep) -> None:
        self.steps.append(step)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "constraint_id": self.constraint_id,
            "order": list(self.order),
            "steps": [s.to_dict() for s in self.steps],
            "terminal": self.terminal,
        }
        payload["digest"] = artifact_digest(payload)
        return payload


class ProviderRouter:
    def __init__(self, order: Optional[List[str]] = None) -> None:
        self.order = list(order or DEFAULT_RESOLUTION_ORDER)

    def new_trace(self, constraint_id: str) -> RouteTrace:
        return RouteTrace(constraint_id=constraint_id, order=list(self.order))


_ROUTER = ProviderRouter()


def get_router() -> ProviderRouter:
    return _ROUTER


def set_router(router: ProviderRouter) -> None:
    global _ROUTER
    _ROUTER = router


def reset_router() -> ProviderRouter:
    global _ROUTER
    _ROUTER = ProviderRouter()
    return _ROUTER
