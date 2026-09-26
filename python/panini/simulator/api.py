"""Simulator API used by the CLI and the debugger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

from ..pipeline import CompileOptions, compile_source
from .engine import ExecutionEngine
from .genotype import CompiledGenotype
from .models import ModelParams
from .observation import render
from .phenotype import phenotype_bundle
from .run import SimulationManifest, SimulationRun, now_iso, _h
from .verify_runtime import verify_runtime


def load_compile_payload(source: Union[str, Path, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(source, dict):
        return source
    path = Path(source)
    if path.exists():
        text = path.read_text()
        if path.suffix == ".json" or text.lstrip().startswith("{"):
            return json.loads(text)
        result = compile_source(text, CompileOptions())
        return result.payload
    # treat as raw PANINI source
    result = compile_source(str(source), CompileOptions())
    return result.payload


class Simulator:
    def __init__(
        self,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[ModelParams] = None,
        seed: int = 1,
        model_kind: str = "hybrid",
    ) -> None:
        self.payload = payload or {}
        self.genotype = CompiledGenotype.from_compile_payload(self.payload) if payload else None
        self.params = params or ModelParams()
        self.seed = seed
        self.model_kind = model_kind
        self.engine: Optional[ExecutionEngine] = None
        self.last_run: Optional[SimulationRun] = None

    @classmethod
    def from_path(cls, path: Union[str, Path], seed: int = 1, **kwargs) -> "Simulator":
        payload = load_compile_payload(path)
        return cls(payload=payload, seed=seed, **kwargs)

    def load_genotype(self, payload: Dict[str, Any]) -> CompiledGenotype:
        self.payload = payload
        self.genotype = CompiledGenotype.from_compile_payload(payload)
        return self.genotype

    def initialize(self) -> ExecutionEngine:
        if self.genotype is None:
            raise RuntimeError("no compiled genotype loaded")
        mid = (self.payload.get("execution_contract") or {}).get("model_id")
        if mid:
            self.params.model_id = mid
        self.engine = ExecutionEngine(
            genotype=self.genotype,
            params=self.params,
            seed=self.seed,
            model_kind=self.model_kind,
        )
        return self.engine

    def run(self, until: Optional[float] = None) -> SimulationRun:
        if self.engine is None:
            self.initialize()
        assert self.engine is not None and self.genotype is not None
        self.engine.run(until=until)
        return self._package()

    def step(self):
        if self.engine is None:
            self.initialize()
        return self.engine.step()

    def step_event(self):
        if self.engine is None:
            self.initialize()
        return self.engine.step_event()

    def checkpoint(self, name: Optional[str] = None):
        if self.engine is None:
            raise RuntimeError("not initialized")
        return self.engine.checkpoint(name)

    def restore(self, checkpoint_id: str):
        if self.engine is None:
            raise RuntimeError("not initialized")
        return self.engine.restore(checkpoint_id)

    def inspect(self, path: str) -> Any:
        if self.engine is None:
            raise RuntimeError("not initialized")
        if path in {"phenotype", "Φ", "phi"}:
            return self.engine.state.phenotype_projection()
        if path == "genome":
            return {k: vars(v) for k, v in self.engine.state.genes.items()}
        return self.engine.state.get_path(path)

    def intervene(self, change: Dict[str, Any]):
        if self.engine is None:
            raise RuntimeError("not initialized")
        return self.engine.intervene(change)

    def render(self, instrument: str = "schematic_axis") -> Dict[str, Any]:
        if self.engine is None:
            raise RuntimeError("not initialized")
        return render(self.engine.state, instrument)

    def export_phenotype(self) -> Dict[str, Any]:
        if self.engine is None:
            raise RuntimeError("not initialized")
        return phenotype_bundle(self.engine.state)

    def verify(self) -> Dict[str, Any]:
        if self.engine is None:
            raise RuntimeError("not initialized")
        desired = None
        if self.payload and self.payload.get("predicted_bundle"):
            # constraints live separately; declared target is in phenotype_constraints
            declared = {}
            for c in (self.payload.get("phenotype_constraints") or {}).get("constraints") or []:
                declared.setdefault(c.get("layer", "anatomical"), {})[c.get("property")] = c.get("target")
            desired = declared or None
        return verify_runtime(self.engine, desired)

    def _package(self) -> SimulationRun:
        assert self.engine and self.genotype
        eng = self.engine
        man = SimulationManifest(
            genotype_hash=_h({
                "program_id": self.genotype.program_id,
                "source_hash": self.genotype.source_hash,
                "genes": [g.identity for g in self.genotype.genes],
            }),
            compiler_hash=_h(self.payload.get("pass_records", [])),
            compiler_version=self.genotype.compiler_version or "0.2.0",
            model_hash=_h({"kind": self.model_kind, "eq": "axial_wnt_fgf_ra_cdx_hox"}),
            parameter_hash=_h(self.params.to_dict()),
            environment_hash=_h(eng.state.environment),
            random_seed=self.seed,
            program_id=self.genotype.program_id,
            created_at=now_iso(),
        )
        run = SimulationRun(
            manifest=man,
            run_id=man.run_id(),
            events=[e.to_plain() for e in eng.log.events],
            checkpoints=[
                {
                    "checkpoint_id": cp.checkpoint_id,
                    "parent_hash": cp.parent_hash,
                    "state_hash": cp.state_hash,
                    "timestamp": cp.timestamp,
                    "step": cp.step,
                    "event_index": cp.event_index,
                    "stage": cp.stage,
                }
                for cp in eng.checkpoints.list()
            ],
            phenotype=phenotype_bundle(eng.state),
            terminal_state={
                "time": eng.state.time,
                "step": eng.state.step,
                "stage": eng.state.stage,
                "hash": eng.state.hash(),
                "molecular": {k: v.value for k, v in eng.state.molecular.items()},
                "anatomy": eng.state.anatomy,
                "cells": len(eng.state.cells),
            },
            verification=self.verify(),
            notes=[
                "executes compiled genotype through molecular → cellular → developmental → phenotype",
                "reduced-order twin; not a claim of quantitative embryology",
                self.genotype.realization_note,
            ],
            maturity=self.verify().get("maturity", "DT-3"),
        )
        self.last_run = run
        return run
