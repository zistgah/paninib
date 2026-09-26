"""Canonical execution events and the append-only event log."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Event:
    event_id: str
    timestamp: float
    actor: str
    operation: str
    operands: List[str]
    pre_state_hash: str
    post_state_hash: str
    causal_parents: List[str] = field(default_factory=list)
    causal_children: List[str] = field(default_factory=list)
    stochastic_sample: Optional[float] = None
    evidence: str = "model"
    model_version: str = "0.2.0"
    scale: str = "molecular"
    source_intent: str = ""
    source_cisc: List[str] = field(default_factory=list)
    source_risc: List[str] = field(default_factory=list)
    source_micro: List[str] = field(default_factory=list)
    notes: str = ""
    delta: Dict[str, Any] = field(default_factory=dict)

    def to_plain(self) -> Dict[str, Any]:
        return asdict(self)

    def hash(self) -> str:
        payload = json.dumps(self.to_plain(), sort_keys=True, default=str).encode()
        return hashlib.sha256(payload).hexdigest()


class EventLog:
    def __init__(self) -> None:
        self.events: List[Event] = []
        self._by_id: Dict[str, Event] = {}

    def append(self, event: Event) -> Event:
        if self.events:
            parent = self.events[-1]
            if event.event_id not in parent.causal_children:
                parent.causal_children.append(event.event_id)
            if parent.event_id not in event.causal_parents:
                event.causal_parents.append(parent.event_id)
        self.events.append(event)
        self._by_id[event.event_id] = event
        return event

    def get(self, event_id: str) -> Optional[Event]:
        return self._by_id.get(event_id)

    def __len__(self) -> int:
        return len(self.events)

    def slice(self, start: int = 0, end: Optional[int] = None) -> List[Event]:
        return self.events[start:end]

    def of_operation(self, op: str) -> List[Event]:
        return [e for e in self.events if e.operation == op]

    def of_actor(self, actor: str) -> List[Event]:
        return [e for e in self.events if e.actor == actor or actor in e.operands]
