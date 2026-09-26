"""Run records, manifests, reproducibility, disk layout."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _h(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


@dataclass
class SimulationManifest:
    genotype_hash: str
    compiler_hash: str
    compiler_version: str
    model_hash: str
    parameter_hash: str
    environment_hash: str
    random_seed: int
    numerical_backend: str = "cpu.explicit_euler"
    hardware_backend: str = "cpu"
    precision: str = "float64"
    timestep_policy: str = "fixed_dt"
    program_id: str = ""
    created_at: str = ""

    def run_id(self) -> str:
        payload = {
            "G": self.genotype_hash,
            "C": self.compiler_hash,
            "M": self.model_hash,
            "P": self.parameter_hash,
            "E": self.environment_hash,
            "R": self.random_seed,
            "B": self.numerical_backend,
        }
        return "run_" + _h(payload)[:12]


@dataclass
class SimulationRun:
    manifest: SimulationManifest
    run_id: str
    events: List[Dict[str, Any]] = field(default_factory=list)
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)
    phenotype: Dict[str, Any] = field(default_factory=dict)
    terminal_state: Dict[str, Any] = field(default_factory=dict)
    verification: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    maturity: str = "DT-3"

    def to_plain(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "manifest": asdict(self.manifest),
            "events": self.events,
            "checkpoints": self.checkpoints,
            "phenotype": self.phenotype,
            "terminal_state": self.terminal_state,
            "verification": self.verification,
            "notes": self.notes,
            "maturity": self.maturity,
        }

    def write(self, directory: Path) -> Path:
        directory = Path(directory)
        dest = directory / self.run_id
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "manifest.json").write_text(json.dumps(asdict(self.manifest), indent=2))
        with (dest / "events.jsonl").open("w") as fh:
            for ev in self.events:
                fh.write(json.dumps(ev, default=str) + "\n")
        (dest / "phenotype.json").write_text(json.dumps(self.phenotype, indent=2, default=str))
        (dest / "state.json").write_text(json.dumps(self.terminal_state, indent=2, default=str))
        (dest / "run.json").write_text(json.dumps(self.to_plain(), indent=2, default=str))
        cps = dest / "checkpoints"
        cps.mkdir(exist_ok=True)
        for cp in self.checkpoints:
            (cps / f"{cp['checkpoint_id']}.json").write_text(json.dumps(cp, indent=2, default=str))
        return dest

    @staticmethod
    def read(path: Path) -> "SimulationRun":
        path = Path(path)
        if path.is_dir():
            raw = json.loads((path / "run.json").read_text())
        else:
            raw = json.loads(path.read_text())
        man = SimulationManifest(**raw["manifest"])
        return SimulationRun(
            manifest=man,
            run_id=raw["run_id"],
            events=raw.get("events") or [],
            checkpoints=raw.get("checkpoints") or [],
            phenotype=raw.get("phenotype") or {},
            terminal_state=raw.get("terminal_state") or {},
            verification=raw.get("verification") or {},
            notes=raw.get("notes") or [],
            maturity=raw.get("maturity", "DT-3"),
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
