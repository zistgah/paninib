# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Reference genome engine over synthetic fixtures and retrieved loci."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..artifact_util import provenance_block
from ..reference_backend import MemoryReferenceBackend, demo_backend
from ..sequence_ir import ReferenceSequence, SequenceIRError
from ..version import COMPILER_VERSION, REFERENCE_CONTRACT_VERSION

RETRIEVED = Path(__file__).resolve().parents[3] / "data" / "retrieved"


def _read_fasta(path: Path) -> str:
    lines = path.read_text().splitlines()
    seq = "".join(line.strip() for line in lines if line and not line.startswith(">"))
    return "".join(c for c in seq.upper() if c in "ACGTN")


class ReferenceGenomeEngine:
    def __init__(self, backend: Optional[MemoryReferenceBackend] = None) -> None:
        self.backend = backend or _extended_backend()

    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "ReferenceGenomeEngine", "class": "ENGINE", "contract_version": REFERENCE_CONTRACT_VERSION, "assemblies": sorted({asm for asm, _ in self.backend.refs}), "future_providers": ["NCBI_Datasets", "GA4GH_Refget"], "scientific_model": False}

    def resolve_assembly(self, assembly: str) -> Dict[str, Any]:
        return self.backend.resolve_assembly(assembly)

    def resolve_sequence(self, assembly: str, sequence_id: str) -> ReferenceSequence:
        return self.backend.resolve_sequence(assembly, sequence_id)

    def retrieve_interval(self, assembly: str, sequence_id: str, start: int, end: int) -> str:
        return self.backend.retrieve_interval(assembly, sequence_id, start, end)

    def resolve_feature(self, feature_id: str) -> Optional[Dict[str, Any]]:
        return self.backend.resolve_feature(feature_id)

    def verify_digest(self, ref: ReferenceSequence, digest: str) -> bool:
        ok = self.backend.verify_digest(ref, digest)
        if not ok:
            raise SequenceIRError("REFERENCE_MISMATCH", "digest")
        return ok

    def retrieve_metadata(self, assembly: str, sequence_id: str) -> Dict[str, Any]:
        meta = self.backend.retrieve_metadata(assembly, sequence_id)
        meta["engine_provenance"] = provenance_block(layer="reference", compiler_version=COMPILER_VERSION, provider="panini.engines.reference", model_id="reference.v09", model_version="0.9.0", reference_version=str(meta.get("version") or ""))
        return meta

    def list_loci(self) -> List[str]:
        return sorted({sid for _, sid in self.backend.refs})


def _extended_backend() -> MemoryReferenceBackend:
    base = demo_backend()
    if RETRIEVED.is_dir():
        for fa in sorted(RETRIEVED.glob("*.fa")):
            locus = fa.stem
            seq = _read_fasta(fa)
            if not seq:
                continue
            ref = ReferenceSequence(sequence_id=locus, assembly="GRCm39-snapshot", sequence=seq, provider="local_retrieved", version="snapshot", accession=f"local:{locus}", provenance="REFERENCE_DATA")
            base.refs[("GRCm39-snapshot", locus)] = ref
            base.features[locus] = {"feature_id": locus, "kind": "locus", "assembly": "GRCm39-snapshot", "sequence_id": locus, "start": 0, "end": ref.length}
        seqs = [sid for asm, sid in base.refs if asm == "GRCm39-snapshot"]
        if seqs:
            base.assemblies["GRCm39-snapshot"] = {"assembly": "GRCm39-snapshot", "sequences": seqs, "provider": "local_retrieved", "note": "retrieved loci snapshots; not a full assembly"}
    return base
