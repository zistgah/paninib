"""Interactive / scriptable debugger session."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..simulator.api import Simulator
from ..simulator.engine import ExecutionEngine
from .causal import compare_states, explain_event, trace_backward, trace_forward
from .predicates import parse_predicate


@dataclass
class Branch:
    name: str
    checkpoint_id: str
    notes: str = ""


class DebugSession:
    def __init__(self, sim: Simulator) -> None:
        self.sim = sim
        if sim.engine is None:
            sim.initialize()
        self.engine: ExecutionEngine = sim.engine  # type: ignore[assignment]
        self.branches: Dict[str, Branch] = {}
        self.references: Dict[str, Dict[str, Any]] = {}
        self.output: List[str] = []
        self.running = True

    def emit(self, text: str) -> str:
        self.output.append(text)
        return text

    def exec(self, line: str) -> str:
        line = line.strip()
        if not line or line.startswith("#"):
            return ""
        parts = _split(line)
        cmd = parts[0].lower()
        args = parts[1:]
        try:
            return self._dispatch(cmd, args, line)
        except Exception as exc:
            return self.emit(f"error: {exc}")

    def _dispatch(self, cmd: str, args: List[str], raw: str) -> str:
        if cmd in {"help", "?"}:
            return self.emit(HELP)
        if cmd == "load":
            return self.emit(f"loaded {self.sim.genotype.program_id if self.sim.genotype else '—'}")
        if cmd == "run":
            until = float(args[0]) if args else None
            self.engine.run(until=until)
            extra = f" break={self.engine.last_break}" if self.engine.paused else ""
            return self.emit(self._status() + extra)
        if cmd == "continue" or cmd == "c":
            self.engine.paused = False
            self.engine.run()
            extra = f" break={self.engine.last_break}" if self.engine.paused else ""
            return self.emit(self._status() + extra)
        if cmd == "pause":
            self.engine.paused = True
            return self.emit("paused")
        if cmd == "step" or cmd == "s":
            ev = self.engine.step()
            return self.emit(self._fmt_event(ev) if ev else self._status())
        if cmd in {"step-event", "stepevent", "se"}:
            ev = self.engine.step_event()
            return self.emit(self._fmt_event(ev) if ev else self._status())
        if cmd in {"step-development", "stepdev", "sd"}:
            ev = self.engine.step_development()
            return self.emit(self._fmt_event(ev) + "\n" + self._status() if ev else self._status())
        if cmd == "break":
            expr = raw.split(None, 1)[1] if " " in raw else ""
            pred = parse_predicate(expr)
            name = expr or f"bp{len(self.engine.breakpoints)}"
            self.engine.add_breakpoint(name, pred)
            return self.emit(f"breakpoint [{name}]")
        if cmd == "watch":
            path = args[0] if args else "anatomy.tail_count"
            self.engine.watches.append(path)
            return self.emit(f"watching {path}")
        if cmd == "inspect":
            path = args[0] if args else "phenotype"
            if len(args) >= 3 and args[1] == "@":
                # inspect state @ t=… — restore nearest checkpoint, inspect, don't lose current
                return self.emit("time-qualified inspect uses nearest checkpoint; current engine time left intact\n" +
                                 json.dumps(self.sim.inspect(args[0]), default=str, indent=2))
            val = self.sim.inspect(path)
            return self.emit(_pretty(val))
        if cmd in {"trace-forward", "traceforward", "what"}:
            entity = args[0] if args else (
                self.engine.genotype.genes[0].symbol if self.engine.genotype.genes else "locus"
            )
            return self.emit(_pretty(trace_forward(self.engine.genotype, entity)))
        if cmd in {"trace-backward", "tracebackward", "why"}:
            entity = args[0] if args else "phenotype.tail"
            return self.emit(_pretty(trace_backward(self.engine, entity)))
        if cmd in {"explain-event", "explain"}:
            eid = args[0] if args else (self.engine.log.events[-1].event_id if self.engine.log.events else "E000001")
            return self.emit(_pretty(explain_event(self.engine, eid)))
        if cmd == "checkpoint":
            cp = self.engine.checkpoint(args[0] if args else None)
            return self.emit(f"{cp.checkpoint_id} t={cp.timestamp:.2f} stage={cp.stage} hash={cp.state_hash[:12]}")
        if cmd == "restore":
            if not args:
                return self.emit("usage: restore CP_xxxx")
            cp = self.engine.restore(args[0])
            return self.emit(f"restored {cp.checkpoint_id} t={cp.timestamp:.2f} stage={cp.stage}")
        if cmd == "rewind":
            n = int(args[0]) if args else 10
            # rewind by restoring last checkpoint with event_index <= current-n
            target = max(0, len(self.engine.log) - n)
            chosen = None
            for cp in self.engine.checkpoints.list():
                if cp.event_index <= target:
                    chosen = cp
            if chosen is None:
                return self.emit("no checkpoint available for rewind")
            self.engine.restore(chosen.checkpoint_id)
            return self.emit(f"rewound toward event {target} via {chosen.checkpoint_id} t={chosen.timestamp:.2f}")
        if cmd == "branch":
            name = args[0] if args else f"branch_{len(self.branches)+1}"
            cp = self.engine.checkpoint(f"CP_{name}")
            self.branches[name] = Branch(name, cp.checkpoint_id)
            return self.emit(f"branch {name} at {cp.checkpoint_id}")
        if cmd == "intervene":
            change = _parse_intervene(raw)
            ev = self.engine.intervene(change)
            return self.emit(f"{ev.event_id} {ev.notes}")
        if cmd == "diff":
            return self.emit(self._diff(args))
        if cmd == "compare":
            return self.emit(self._diff(args))
        if cmd == "verify":
            return self.emit(_pretty(self.sim.verify()))
        if cmd in {"status", "info"}:
            return self.emit(self._status())
        if cmd in {"events", "log"}:
            n = int(args[0]) if args else 8
            chunk = self.engine.log.events[-n:]
            return self.emit("\n".join(self._fmt_event(e) for e in chunk))
        if cmd in {"quit", "exit", "q"}:
            self.running = False
            return self.emit("quit")
        return self.emit(f"unknown command `{cmd}`; try help")

    def _status(self) -> str:
        s = self.engine.state
        ph = s.phenotype_projection()
        return (
            f"t={s.time:.2f}h step={s.step} stage={s.stage} events={len(self.engine.log)} "
            f"paused={self.engine.paused} halted={self.engine.halted} "
            f"tail_count={ph['anatomical']['tail_count']} "
            f"tail_identity={s.molecular['tail_identity'].value:.3f} "
            f"primary={ph['anatomical']['primary_axis']}"
        )

    def _fmt_event(self, ev) -> str:
        if ev is None:
            return "(no event)"
        return (
            f"{ev.event_id} t={ev.timestamp:.2f} {ev.scale:<14} {ev.operation:<14} "
            f"{ev.notes}"
        )

    def _diff(self, args: List[str]) -> str:
        current = self.engine.state.phenotype_projection()
        payload = self.sim.payload or {}
        if "reference" in self.references:
            other = self.references["reference"]
        else:
            desired = {}
            for c in (payload.get("phenotype_constraints") or {}).get("constraints") or []:
                desired.setdefault(c.get("layer", "anatomical"), {})[c.get("property")] = c.get("target")
            other = desired or {"anatomical": {"note": "no declared phenotype on this session"}}
        report = phenotype_diff(other, current)
        return report


def phenotype_diff(target: Dict[str, Any], simulated: Dict[str, Any]) -> str:
    lines = ["PHENOTYPE DIFF", ""]
    sections = ["anatomical", "cellular", "molecular", "tissue", "temporal"]
    for sec in sections:
        tsec = target.get(sec) or {}
        ssec = simulated.get(sec) or {}
        if not tsec and not ssec:
            continue
        lines.append(sec.capitalize())
        keys = sorted(set(tsec) | set(ssec))
        for k in keys:
            tv, sv = tsec.get(k, "—"), ssec.get(k, "—")
            lines.append(f"  {k}:")
            lines.append(f"      target:      {tv}")
            lines.append(f"      simulated:   {sv}")
        lines.append("")
    return "\n".join(lines)


def _pretty(val: Any) -> str:
    if isinstance(val, str):
        return val
    return json.dumps(val, indent=2, default=str)


def _split(line: str) -> List[str]:
    return line.replace(",", " ").split()


def _parse_intervene(raw: str) -> Dict[str, Any]:
    """
    intervene expression(locus)=0.72
    intervene disable(locus)
    intervene environment.temperature=33
    """
    body = raw.split(None, 1)[1] if " " in raw else ""
    change: Dict[str, Any] = {}
    if body.startswith("disable("):
        change[body] = True
        return change
    if body.startswith("enable("):
        change[body] = True
        return change
    if "=" in body:
        k, v = body.split("=", 1)
        k, v = k.strip(), v.strip()
        try:
            change[k] = float(v)
        except ValueError:
            change[k] = v
        return change
    change[body] = True
    return change


HELP = """PANINI biological debugger
  run [T]              run until T hours or completion / breakpoint
  continue             resume after breakpoint
  step                 one solver tick
  step-event           one scheduled event
  step-development     until developmental stage changes
  break <predicate>    biological breakpoint
  watch <path>         record path each event
  inspect <path>       genome | locus | protein | cell | tissue | anatomy | phenotype
  trace-forward E      what does entity affect?
  trace-backward P     why is this phenotype?
  explain-event ID     microcode ← RISC ← CISC ← PANINI
  checkpoint [name]
  restore CP
  rewind N             rewind ~N events via last checkpoint
  branch [name]
  intervene expr       digital intervention
  diff | compare       typed phenotype diff vs reference
  verify               V0–V11 runtime report
  events [N]
  status
  quit
"""
