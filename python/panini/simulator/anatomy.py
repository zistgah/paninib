"""Multi-axis anatomy. The 1-D backend initiates at most one posterior axis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class AxisStructure:
    identity: str
    axis_type: str
    origin: Tuple[float, float, float]
    direction: Tuple[float, float, float]
    length: float
    identity_score: float
    developmental_stage: str
    confidence: float


@dataclass
class AnatomyState:
    axes: List[AxisStructure] = field(default_factory=list)

    def count(self, axis_type: str) -> int:
        return sum(1 for a in self.axes if a.axis_type == axis_type)

    def primary_axis(self) -> Optional[AxisStructure]:
        if not self.axes:
            return None
        return max(self.axes, key=lambda a: a.identity_score)
