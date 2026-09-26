"""Canonical biological state S = (G,R,P,M,C,T,A,B,O,E,τ,Γ)."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


def _hash(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()


@dataclass
class Quantity:
    value: float
    units: str = "au"
    sigma: float = 0.0
    source: str = "model"
    evidence_level: str = "COMPUTATIONALLY_SUPPORTED"
    model_version: str = "0.2.0"

    def with_value(self, v: float) -> "Quantity":
        q = copy.copy(self)
        q.value = v
        return q


@dataclass
class Entity:
    identity: str
    type: str
    location: str = ""
    state: str = "active"
    value: Any = None
    units: str = ""
    uncertainty: float = 0.0
    provenance: List[str] = field(default_factory=list)
    timestamp: float = 0.0
    model_version: str = "0.2.0"


@dataclass
class GeneState:
    identity: str
    locus: str
    kind: str
    strand: str = "+"
    enabled: bool = True
    copy_number: int = 1
    expression_rate: float = 0.0
    transcription_rate: float = 0.0
    context: str = "developmental"
    source_cisc: List[str] = field(default_factory=list)
    source_risc: List[str] = field(default_factory=list)
    source_micro: List[str] = field(default_factory=list)
    source_intent: str = ""


@dataclass
class CellRecord:
    identity: str
    cell_type: str
    position: float  # 0 anterior … 1 posterior on the schematic axis
    volume: float = 1.0
    cycle_phase: str = "G1"
    lineage: str = "axial_progenitor"
    signals: Dict[str, float] = field(default_factory=dict)


@dataclass
class BiologicalState:
    """Strongly typed complete biological state."""

    time: float = 0.0
    step: int = 0
    stage: str = "gastrula"
    genes: Dict[str, GeneState] = field(default_factory=dict)
    rna: Dict[str, Quantity] = field(default_factory=dict)
    protein: Dict[str, Quantity] = field(default_factory=dict)
    molecular: Dict[str, Quantity] = field(default_factory=dict)
    cells: List[CellRecord] = field(default_factory=list)
    tissue: Dict[str, Any] = field(default_factory=dict)
    anatomy: Dict[str, Any] = field(default_factory=dict)
    behavior: Dict[str, Any] = field(default_factory=dict)
    observations: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    spatial: Dict[str, Any] = field(default_factory=dict)
    fields: Dict[str, List[float]] = field(default_factory=dict)
    flags: Dict[str, Any] = field(default_factory=dict)
    model_version: str = "0.2.0"

    def snapshot(self) -> "BiologicalState":
        return copy.deepcopy(self)

    def to_plain(self) -> Dict[str, Any]:
        def conv(o: Any) -> Any:
            if hasattr(o, "__dataclass_fields__"):
                return {k: conv(v) for k, v in asdict(o).items()}
            if isinstance(o, dict):
                return {str(k): conv(v) for k, v in o.items()}
            if isinstance(o, list):
                return [conv(v) for v in o]
            return o

        return conv(self)

    def hash(self) -> str:
        return _hash(self.to_plain())

    def get_path(self, path: str) -> Any:
        """Inspect dotted / bracket-ish paths used by the debugger."""
        p = path.strip().lstrip("/")
        aliases = {
            "genome": "genes",
            "phenotype": "anatomy",
            "developmental.state": "stage",
            "developmental_state": "stage",
        }
        p = aliases.get(p, p)
        cur: Any = self
        for part in p.replace("[", ".").replace("]", "").split("."):
            if part == "":
                continue
            if isinstance(cur, BiologicalState):
                if hasattr(cur, part):
                    cur = getattr(cur, part)
                    continue
            if isinstance(cur, dict):
                if part in cur:
                    cur = cur[part]
                    continue
                # case-insensitive gene lookup
                hits = [k for k in cur if str(k).lower() == part.lower()]
                if hits:
                    cur = cur[hits[0]]
                    continue
            if isinstance(cur, list):
                if part.isdigit():
                    cur = cur[int(part)]
                    continue
            if hasattr(cur, part):
                cur = getattr(cur, part)
                continue
            raise KeyError(f"inspect path not found: {path} (at {part})")
        if isinstance(cur, Quantity):
            return cur.value
        return cur

    def expression(self, gene_id: str) -> float:
        g = self._gene(gene_id)
        if g is None:
            return 0.0
        rna = self.rna.get(g.identity)
        return rna.value if rna else g.expression_rate

    def _gene(self, gene_id: str) -> Optional[GeneState]:
        if gene_id in self.genes:
            return self.genes[gene_id]
        for g in self.genes.values():
            if gene_id.lower() in (g.identity.lower(), g.identity.split(":")[-1].lower()):
                return g
            if gene_id.lower() in g.identity.lower():
                return g
        return None

    def phenotype_projection(self) -> Dict[str, Any]:
        tail_id = self.molecular.get("tail_identity")
        score = tail_id.value if tail_id else 0.0
        axes = self.anatomy.get("axes") or []
        if axes:
            score = max(score, max(a.get("identity_score", 0.0) for a in axes))
        primary = "tail" if (len(axes) >= 1 or score > 0.6) else "indeterminate"
        bins = self.fields.get("hox", [])
        posterior = bins[-1] if bins else 0.0
        progenitors = sum(1 for c in self.cells if "progenitor" in c.cell_type or "nmps" in c.cell_type)
        anatomical = {
            "tail_count": int(len(axes) if axes else self.anatomy.get("tail_count", 1 if score > 0.6 else 0)),
            "axis_extent": float(self.anatomy.get("axis_extent", min(1.0, score))),
            "axis_extent_units": "uncalibrated",
            "primary_axis": "tail" if (len(axes) >= 1 or self.anatomy.get("primary_axis") == "tail") else self.anatomy.get("primary_axis", primary),
            "secondary_axis": "tail" if len(axes) >= 2 else self.anatomy.get("secondary_axis", "absent"),
            "head_identity": False if len(axes) else bool(self.anatomy.get("head_identity", score < 0.35)),
            "axes": axes,
        }
        for key, value in self.anatomy.items():
            if key not in anatomical:
                anatomical[key] = value
        return {
            "molecular": {
                "pathway_wnt_fgf_activity": self.molecular.get("wnt", Quantity(0)).value
                + self.molecular.get("fgf", Quantity(0)).value,
                "hox_posterior": posterior,
                "cdx": self.molecular.get("cdx", Quantity(0)).value,
            },
            "cellular": {
                "caudal_progenitor_count": progenitors,
                "cell_count": len(self.cells),
            },
            "tissue": {
                "axis_polarity": "posteriorized" if score > 0.6 else "weak",
            },
            "anatomical": anatomical,
            "temporal": {
                "stage": self.stage,
                "time_h": self.time,
                "matured": self.stage == "mature" or bool(self.flags.get("matured")),
            },
            "geometric": {
                "backend": self.spatial.get("backend", "1d_axis_bins"),
                "n_bins": len(self.fields.get("wnt", [])),
            },
        }
