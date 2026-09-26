"""Event-driven hybrid execution engine.

while simulation_time < T_end:
    event = scheduler.next()
    state_before = snapshot()
    result = execute(event)
    commit()
    record()
    trigger_dependent_events()
    run_assertions()
    if breakpoint_hit(): pause()
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .assertions import run_assertions
from .checkpoint import Checkpoint, CheckpointManager
from .events import Event, EventLog
from .genotype import CompiledGenotype
from .models import (
    ModelParams,
    initialize_state,
    react_fields,
    transcribe,
    translate,
    update_cells,
    update_development,
)
from ..registry import get_registry
from .state import BiologicalState


BreakPredicate = Callable[[BiologicalState], bool]


def _hid(*parts: Any) -> str:
    blob = "|".join(str(p) for p in parts).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


@dataclass
class Scheduled:
    time: float
    kind: str
    actor: str
    operands: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)
    seq: int = 0


class Scheduler:
    def __init__(self) -> None:
        self._q: List[Scheduled] = []
        self._seq = 0

    def push(self, item: Scheduled) -> None:
        item.seq = self._seq
        self._seq += 1
        self._q.append(item)
        self._q.sort(key=lambda s: (s.time, s.seq))

    def next(self) -> Optional[Scheduled]:
        return self._q.pop(0) if self._q else None

    def peek(self) -> Optional[Scheduled]:
        return self._q[0] if self._q else None

    def __len__(self) -> int:
        return len(self._q)


class ExecutionEngine:
    def __init__(
        self,
        genotype: CompiledGenotype,
        params: Optional[ModelParams] = None,
        seed: int = 1,
        model_kind: str = "hybrid",
    ) -> None:
        self.genotype = genotype
        self.params = params or ModelParams()
        if not self.params.model_id:
            desc, _reason = get_registry().resolve(organism=genotype.organism, required_capabilities=[])
            self.params.model_id = desc.id
        self.seed = seed
        self.model_kind = model_kind
        self.rng = random.Random(seed)
        self.state = initialize_state(genotype, self.params)
        self._exec = get_registry().get_execution(self.params.model_id)
        self.log = EventLog()
        self.scheduler = Scheduler()
        self.checkpoints = CheckpointManager()
        self.event_counter = 0
        self.paused = False
        self.halted = False
        self.breakpoints: List[tuple[str, BreakPredicate]] = []
        self.watches: List[str] = []
        self.watch_hits: List[Dict[str, Any]] = []
        self.last_break: Optional[str] = None
        self.assertions_on = True
        self._schedule_horizon()
        self._record(
            actor="runtime",
            operation="INIT",
            operands=[genotype.program_id],
            scale="organism",
            notes="initialized from compiled genotype",
            pre="0" * 16,
        )
        self.checkpoint("CP_0000")

    def _schedule_horizon(self) -> None:
        t = 0.0
        k = 0
        while t <= self.params.t_end + 1e-12:
            self.scheduler.push(Scheduled(t, "TRANSCRIBE", "transcription", []))
            self.scheduler.push(Scheduled(t, "TRANSLATE", "translation", []))
            self.scheduler.push(Scheduled(t, "REACT", "reaction_engine", []))
            self.scheduler.push(Scheduled(t, "SIGNAL", "signaling", []))
            if k % 5 == 0:
                self.scheduler.push(Scheduled(t, "DIFFERENTIATE", "cell_cycle", []))
            if k % 8 == 0:
                self.scheduler.push(Scheduled(t, "DEVELOP", "morphogenesis", []))
            t += self.params.dt
            k += 1
        self.scheduler.push(Scheduled(self.params.t_end, "OBSERVE", "phenotype_engine", []))

    def add_breakpoint(self, name: str, pred: BreakPredicate) -> None:
        self.breakpoints.append((name, pred))

    def _record(self, actor, operation, operands, scale="molecular", notes="", pre=None, delta=None) -> Event:
        self.event_counter += 1
        eid = f"E{self.event_counter:06d}"
        post = self.state.hash()
        ancestry_cisc, ancestry_risc, ancestry_micro, intent = [], [], [], ""
        for opnd in operands:
            g = self.genotype.gene(opnd) or next(
                (gg for gg in self.genotype.genes if gg.identity == opnd), None
            )
            if g:
                ancestry_cisc += g.source_cisc
                ancestry_risc += g.source_risc
                ancestry_micro += g.source_micro
                intent = g.source_intent or intent
        ev = Event(
            event_id=eid,
            timestamp=self.state.time,
            actor=actor,
            operation=operation,
            operands=list(operands),
            pre_state_hash=pre or "unknown",
            post_state_hash=post,
            scale=scale,
            source_intent=intent,
            source_cisc=list(dict.fromkeys(ancestry_cisc)),
            source_risc=list(dict.fromkeys(ancestry_risc)),
            source_micro=list(dict.fromkeys(ancestry_micro)),
            notes=notes,
            delta=delta or {},
            stochastic_sample=self.rng.random(),
        )
        return self.log.append(ev)

    def checkpoint(self, checkpoint_id: Optional[str] = None) -> Checkpoint:
        cid = checkpoint_id or f"CP_{len(self.checkpoints.list()):04d}"
        parent = self.checkpoints.last()
        cp = Checkpoint(
            checkpoint_id=cid,
            parent_hash=parent.state_hash if parent else "genesis",
            state_hash=self.state.hash(),
            timestamp=self.state.time,
            step=self.state.step,
            event_index=len(self.log),
            random_state=self.rng.getstate(),
            model_version=self.state.model_version,
            parameter_hash=_hid(sorted(self.params.to_dict().items())),
            genotype_hash=_hid(self.genotype.program_id, self.genotype.source_hash),
            environment_hash=_hid(self.state.environment),
            stage=self.state.stage,
            state=self.state.snapshot(),
        )
        return self.checkpoints.add(cp)

    def restore(self, checkpoint_id: str) -> Checkpoint:
        cp = self.checkpoints.get(checkpoint_id)
        if cp is None:
            raise KeyError(f"unknown checkpoint {checkpoint_id}")
        self.state = cp.restore_state()
        self.rng.setstate(cp.random_state)
        self.paused = False
        # keep history; future events continue numbering
        return cp

    def _execute(self, item: Scheduled) -> Event:
        pre = self.state.hash()
        self.state.time = item.time
        delta: Dict[str, Any] = {}
        notes = ""
        scale = "molecular"
        operands = list(item.operands)

        if item.kind == "TRANSCRIBE":
            delta = transcribe(self.state, self.genotype, self.params)
            operands = [g.identity for g in self.genotype.genes]
            notes = f"transcribed {len(delta)} loci"
            scale = "molecular"
        elif item.kind == "TRANSLATE":
            delta = translate(self.state, self.genotype, self.params)
            operands = [g.identity for g in self.genotype.genes]
            notes = f"translated {len(delta)} products"
            scale = "molecular"
        elif item.kind == "REACT":
            react_fields(self.state, self.genotype, self.params)
            delta = {
                k: self.state.molecular[k].value
                for k in self.state.molecular
            }
            notes = "field step"
            scale = "molecular"
        elif item.kind == "SIGNAL":
            n_bins = max(int(self.params.n_bins or 1), 1)
            for cell in self.state.cells:
                idx = min(n_bins - 1, max(0, int(round(cell.position * (n_bins - 1)))))
                cell.signals = {
                    name: (field[idx] if idx < len(field) else 0.0)
                    for name, field in self.state.fields.items()
                    if field
                }
            notes = "propagated field onto cells"
            scale = "cellular"
        elif item.kind == "DIFFERENTIATE":
            changed = update_cells(self.state, self.params)
            delta = {"changed_cells": changed}
            notes = f"{len(changed)} cells changed type"
            scale = "cellular"
        elif item.kind == "DEVELOP":
            prev = update_development(self.state, self.params)
            axes = (self.state.anatomy or {}).get("axes") or []
            if axes:
                self._record(
                    "anatomy", "AXIS_INITIATE", [a.get("identity", "") for a in axes],
                    scale="developmental",
                    notes=f"{len(axes)} axes from independent basins",
                    pre=pre,
                    delta={"n": len(axes)},
                )
            delta = {"from": prev, "to": self.state.stage, "axes": self.state.anatomy.get("tail_count")}
            notes = f"stage {prev} → {self.state.stage}"
            scale = "developmental"
        elif item.kind == "OBSERVE":
            update_development(self.state, self.params)
            self.state.observations["phenotype"] = self.state.phenotype_projection()
            delta = self.state.observations["phenotype"]["anatomical"]
            notes = "phenotype observation H(S)"
            scale = "organism"
        else:
            notes = f"unknown op {item.kind}"

        self.state.step += 1
        ev = self._record(
            actor=item.actor,
            operation=item.kind,
            operands=operands,
            scale=scale,
            notes=notes,
            pre=pre,
            delta=delta if not isinstance(delta, dict) or len(str(delta)) < 2000 else {k: delta[k] for k in list(delta)[:12]},
        )
        if self.assertions_on:
            failures = run_assertions(self.state)
            if failures:
                self.state.flags["assertions_failed"] = failures
                self._record(
                    actor="verifier",
                    operation="ASSERT_FAIL",
                    operands=failures,
                    scale="verification",
                    notes="; ".join(failures),
                    pre=self.state.hash(),
                )
        return ev

    def _hit_breakpoint(self) -> Optional[str]:
        for name, pred in self.breakpoints:
            try:
                if pred(self.state):
                    return name
            except Exception:
                continue
        return None

    def step_event(self) -> Optional[Event]:
        if self.halted:
            return None
        item = self.scheduler.next()
        if item is None:
            self.halted = True
            return None
        ev = self._execute(item)
        for path in self.watches:
            try:
                val = self.state.get_path(path)
                self.watch_hits.append({"time": self.state.time, "path": path, "value": val, "event": ev.event_id})
            except KeyError:
                pass
        hit = self._hit_breakpoint()
        if hit:
            self.paused = True
            self.last_break = hit
        return ev

    def step(self) -> Optional[Event]:
        """Advance one solver tick (all events scheduled at the next timestamp)."""
        if self.halted or not self.scheduler.peek():
            self.halted = not self.scheduler.peek()
            return None
        t = self.scheduler.peek().time
        last = None
        while self.scheduler.peek() and abs(self.scheduler.peek().time - t) < 1e-12:
            last = self.step_event()
            if self.paused:
                break
        return last

    def step_development(self) -> Optional[Event]:
        last = None
        start = self.state.stage
        while not self.halted and self.state.stage == start:
            last = self.step()
            if self.paused or last is None:
                break
        return last

    def run(self, until: Optional[float] = None) -> BiologicalState:
        limit = self.params.t_end if until is None else until
        self.paused = False
        self.last_break = None
        while not self.halted:
            nxt = self.scheduler.peek()
            if nxt is None or nxt.time > limit + 1e-12:
                break
            self.step_event()
            if self.paused:
                break
            if self.state.step % 40 == 0:
                self.checkpoint()
        if self.halted or (self.scheduler.peek() is None):
            update_development(self.state, self.params)
            self.state.observations["phenotype"] = self.state.phenotype_projection()
        return self.state

    def intervene(self, change: Dict[str, Any]) -> Event:
        """Sandbox digital intervention, then continue from current time."""
        pre = self.state.hash()
        notes = []
        for key, val in change.items():
            if key.startswith("expression(") and key.endswith(")"):
                gid = key[len("expression("):-1]
                g = self.genotype.gene(gid)
                if g and g.identity in self.state.genes:
                    self.state.genes[g.identity].expression_rate = float(val)
                    if g.identity in self.state.rna:
                        self.state.rna[g.identity].value = float(val)
                    notes.append(f"set expression {g.identity}={val}")
            elif key.startswith("disable("):
                gid = key[len("disable("):-1]
                g = self.genotype.gene(gid)
                if g and g.identity in self.state.genes:
                    self.state.genes[g.identity].enabled = False
                    notes.append(f"disabled {g.identity}")
            elif key.startswith("enable("):
                gid = key[len("enable("):-1]
                g = self.genotype.gene(gid)
                if g and g.identity in self.state.genes:
                    self.state.genes[g.identity].enabled = True
                    notes.append(f"enabled {g.identity}")
            elif key == "environment.temperature" or key == "temperature":
                self.state.environment["temperature"] = float(val)
                notes.append(f"temperature={val}")
            elif key.startswith("modify("):
                notes.append(f"modify recorded: {key}={val}")
            else:
                try:
                    # generic path assign if numeric
                    notes.append(f"raw {key}={val}")
                except Exception:
                    pass
        return self._record(
            actor="debugger",
            operation="INTERVENE",
            operands=list(change.keys()),
            scale="intervention",
            notes="; ".join(notes) or str(change),
            pre=pre,
            delta=change,
        )
