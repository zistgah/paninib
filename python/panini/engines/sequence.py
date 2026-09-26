# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Canonical sequence engine. Strengthens v0.6/v0.7 rather than bypassing it."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from ..artifact_util import provenance_block
from ..sequence_ir import DerivedSequence, ReferenceSequence, SequenceEdit, SequenceIRError, apply_edits, sha256_text
from ..version import COMPILER_VERSION, SEQUENCE_IR_VERSION


class SequenceEngine:
    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "SequenceEngine", "class": "ENGINE", "version": SEQUENCE_IR_VERSION, "ops": ["REPLACE", "INSERT", "DELETE", "SUBSTITUTE"], "rejected": ["INVERT", "DUPLICATE", "MOVE", "COPY"], "scientific_model": False}

    def normalize_edits(self, edits: List[Union[SequenceEdit, Dict[str, Any]]]) -> List[SequenceEdit]:
        out: List[SequenceEdit] = []
        for i, raw in enumerate(edits):
            if isinstance(raw, SequenceEdit):
                out.append(raw)
                continue
            out.append(SequenceEdit(edit_id=str(raw.get("edit_id") or f"e{i:03d}"), operation=str(raw.get("operation") or raw.get("op") or "").upper(), start=int(raw.get("start", 0)), end=int(raw.get("end", raw.get("start", 0))), replacement=str(raw.get("replacement") or ""), source=str(raw.get("source") or ""), orientation=str(raw.get("orientation") or "+"), reference_sequence=str(raw.get("reference_sequence") or ""), provenance=str(raw.get("provenance") or "DESIGN")))
        return out

    def validate_coordinates(self, edits: List[SequenceEdit], length: int) -> None:
        for e in edits:
            if not (0 <= e.start <= e.end <= length):
                raise SequenceIRError("INVALID_EDIT", f"coordinates [{e.start},{e.end}) vs {length}")

    def overlaps(self, edits: List[SequenceEdit]) -> bool:
        ordered = sorted(edits, key=lambda e: (e.start, e.end))
        last_end = -1
        for e in ordered:
            if e.start < last_end:
                return True
            last_end = e.end
        return False

    def apply(self, ref: ReferenceSequence, edits: List[SequenceEdit]) -> DerivedSequence:
        return apply_edits(ref, edits)

    def fasta(self, derived: DerivedSequence) -> str:
        return derived.to_fasta()

    def genbank_min(self, derived: DerivedSequence, features: Optional[List[Dict[str, Any]]] = None) -> str:
        lines = [f"LOCUS       {derived.sequence_id} {len(derived.sequence)} bp    DNA", f"DEFINITION  PANINI derived sequence ({derived.assembly}).", f"ACCESSION   {derived.digest[:12]}", f"COMMENT     provenance={derived.provenance}; not a biological claim.", "FEATURES             Location/Qualifiers"]
        for feat in features or []:
            kind = feat.get("kind", "misc_feature")
            start = int(feat.get("start", 0)) + 1
            end = int(feat.get("end", 0))
            lines.append(f"     {kind:<16}{start}..{end}")
        lines.append("ORIGIN")
        seq = derived.sequence.lower()
        for i in range(0, len(seq), 60):
            chunk = seq[i:i + 60]
            spaced = " ".join(chunk[j:j + 10] for j in range(0, len(chunk), 10))
            lines.append(f"{i + 1:>9} {spaced}")
        lines.append("//")
        return "\n".join(lines) + "\n"

    def trace_edit(self, *, constraint: str, decision: str, edit: SequenceEdit, interval: str, derived: str) -> Dict[str, Any]:
        return {"biological_constraint": constraint, "realization_decision": decision, "edit": edit.to_dict(), "sequence_interval": interval, "derived_sequence_digest": sha256_text(derived), "provenance": provenance_block(layer="sequence.trace", compiler_version=COMPILER_VERSION, provider="panini.engines.sequence", model_id="sequence.v09", model_version=SEQUENCE_IR_VERSION)}
