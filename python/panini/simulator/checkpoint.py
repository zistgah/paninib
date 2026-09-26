"""Immutable checkpoints for time-travel debugging."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .state import BiologicalState


@dataclass
class Checkpoint:
    checkpoint_id: str
    parent_hash: str
    state_hash: str
    timestamp: float
    step: int
    event_index: int
    random_state: Any
    model_version: str
    parameter_hash: str
    genotype_hash: str
    environment_hash: str
    stage: str
    state: BiologicalState
    notes: str = ""

    def restore_state(self) -> BiologicalState:
        return self.state.snapshot()


class CheckpointManager:
    def __init__(self) -> None:
        self._items: List[Checkpoint] = []
        self._by_id: Dict[str, Checkpoint] = {}

    def add(self, cp: Checkpoint) -> Checkpoint:
        self._items.append(cp)
        self._by_id[cp.checkpoint_id] = cp
        return cp

    def get(self, checkpoint_id: str) -> Optional[Checkpoint]:
        return self._by_id.get(checkpoint_id)

    def last(self) -> Optional[Checkpoint]:
        return self._items[-1] if self._items else None

    def at_or_before(self, timestamp: float) -> Optional[Checkpoint]:
        found = None
        for cp in self._items:
            if cp.timestamp <= timestamp:
                found = cp
        return found

    def at_stage(self, stage: str) -> Optional[Checkpoint]:
        for cp in reversed(self._items):
            if cp.stage == stage:
                return cp
        return None

    def list(self) -> List[Checkpoint]:
        return list(self._items)
