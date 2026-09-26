# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Cellular execution substrate. Not a mammalian cell model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..artifact_util import artifact_digest, provenance_block
from ..version import COMPILER_VERSION


@dataclass
class Cell:
    cell_id: str
    position: Tuple[float, float, float]
    state: str = "progenitor"
    gene_state: Dict[str, float] = field(default_factory=dict)
    protein_state: Dict[str, float] = field(default_factory=dict)
    signals: Dict[str, float] = field(default_factory=dict)
    neighbors: List[str] = field(default_factory=list)
    lineage: str = "root"
    time: float = 0.0
    alive: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {"cell_id": self.cell_id, "position": list(self.position), "state": self.state, "gene_state": dict(self.gene_state), "protein_state": dict(self.protein_state), "signals": dict(self.signals), "neighbors": list(self.neighbors), "lineage": self.lineage, "time": self.time, "alive": self.alive}


class CellularEngine:
    def __init__(self, neighborhood_radius: float = 0.15) -> None:
        self.neighborhood_radius = neighborhood_radius
        self._seq = 0

    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "CellularEngine", "class": "ENGINE", "events": ["transition", "signal", "division", "death", "migration"], "scientific_model": False}

    def _nid(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}{self._seq:04d}"

    def neighbors(self, cells: List[Cell], cell: Cell) -> List[Cell]:
        r2 = self.neighborhood_radius ** 2
        out = []
        for other in cells:
            if other.cell_id == cell.cell_id or not other.alive:
                continue
            dx, dy, dz = other.position[0] - cell.position[0], other.position[1] - cell.position[1], other.position[2] - cell.position[2]
            if dx * dx + dy * dy + dz * dz <= r2:
                out.append(other)
        return out

    def refresh_neighbors(self, cells: List[Cell]) -> None:
        for c in cells:
            c.neighbors = [n.cell_id for n in self.neighbors(cells, c)]

    def exchange_signals(self, cells: List[Cell], key: str = "morphogen") -> None:
        self.refresh_neighbors(cells)
        updates = {}
        for c in cells:
            if not c.alive:
                continue
            neigh = self.neighbors(cells, c)
            acc = c.signals.get(key, 0.0)
            for n in neigh:
                acc += n.signals.get(key, 0.0)
            updates[c.cell_id] = acc / (len(neigh) + 1)
        for c in cells:
            if c.cell_id in updates:
                c.signals[key] = updates[c.cell_id]

    def transition(self, cell: Cell, threshold: float = 0.4) -> Optional[Dict[str, Any]]:
        sig = cell.signals.get("morphogen", 0.0)
        prev = cell.state
        if sig >= threshold and cell.state == "progenitor":
            cell.state = "differentiated"
            cell.gene_state["on"] = 1.0
            return {"event": "transition", "cell_id": cell.cell_id, "from": prev, "to": cell.state, "time": cell.time}
        return None

    def divide(self, cells: List[Cell], cell: Cell) -> Optional[Cell]:
        if not cell.alive:
            return None
        child = Cell(cell_id=self._nid("c"), position=(cell.position[0] + 0.05, cell.position[1], cell.position[2]), state="progenitor", gene_state=dict(cell.gene_state), protein_state=dict(cell.protein_state), signals=dict(cell.signals), lineage=cell.lineage + "/" + cell.cell_id, time=cell.time)
        cells.append(child)
        return child

    def die(self, cell: Cell) -> Dict[str, Any]:
        cell.alive = False
        cell.state = "dead"
        return {"event": "death", "cell_id": cell.cell_id, "time": cell.time}

    def migrate(self, cell: Cell, delta: Tuple[float, float, float]) -> Dict[str, Any]:
        cell.position = (cell.position[0] + delta[0], cell.position[1] + delta[1], cell.position[2] + delta[2])
        return {"event": "migration", "cell_id": cell.cell_id, "position": list(cell.position), "time": cell.time}

    def seed_line(self, n: int = 7) -> List[Cell]:
        cells = []
        for i in range(n):
            x = i / max(1, n - 1)
            cells.append(Cell(cell_id=self._nid("c"), position=(x, 0.0, 0.0), state="progenitor", signals={"morphogen": 1.0 if i == 0 else 0.0}, lineage="root"))
        self.refresh_neighbors(cells)
        return cells

    def run_fixture(self, steps: int = 8) -> Dict[str, Any]:
        cells = self.seed_line(7)
        events: List[Dict[str, Any]] = []
        history = []
        for t in range(steps):
            for c in cells:
                c.time = float(t)
            self.exchange_signals(cells)
            for c in list(cells):
                ev = self.transition(c, threshold=0.25)
                if ev:
                    events.append(ev)
            if t == 1:
                child = self.divide(cells, cells[0])
                if child:
                    events.append({"event": "division", "parent": cells[0].cell_id, "child": child.cell_id, "time": t})
            if t == 5:
                events.append(self.migrate(cells[-1], (0.02, 0.01, 0.0)))
            history.append({"time": float(t), "n_alive": sum(1 for c in cells if c.alive), "n_diff": sum(1 for c in cells if c.state == "differentiated")})
        payload = {"cells": [c.to_dict() for c in cells], "events": events, "history": history, "provenance": provenance_block(layer="cellular", compiler_version=COMPILER_VERSION, provider="panini.engines.cellular", model_id="cell.fixture", model_version="0.9.0")}
        payload["digest"] = artifact_digest({"history": history, "n": len(cells)})
        return payload
