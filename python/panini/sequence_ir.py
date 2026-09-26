# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Sequence IR: structured bridge between genetic semantics and ATGC.

ATGC is a backend representation. Sequence IR keeps reference identity,
coordinates, edits, validation and provenance.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .version import SEQUENCE_IR_VERSION


DNA_ALPHABET = set("ACGT")
COORDINATE_SYSTEM = "0-based-half-open"

EDIT_OPERATIONS = (
    "COPY",
    "INSERT",
    "DELETE",
    "REPLACE",
    "DUPLICATE",
    "INVERT",
    "MOVE",
    "SUBSTITUTE",
)

EXECUTABLE_EDITS = {"REPLACE", "INSERT", "DELETE", "SUBSTITUTE"}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Coordinate:
    assembly: str
    sequence_id: str
    start: int
    end: int
    coordinate_system: str = COORDINATE_SYSTEM
    orientation: str = "+"

    def validate_against(self, length: int) -> None:
        if self.coordinate_system != COORDINATE_SYSTEM:
            raise SequenceIRError("INVALID_EDIT", f"unsupported coordinate system {self.coordinate_system}")
        if self.orientation not in {"+", "-", "."}:
            raise SequenceIRError("INVALID_EDIT", f"invalid orientation {self.orientation}")
        if not (0 <= self.start <= self.end <= length):
            raise SequenceIRError(
                "INVALID_EDIT",
                f"coordinates [{self.start}, {self.end}) outside [0, {length})",
            )


@dataclass
class ReferenceSequence:
    sequence_id: str
    assembly: str
    sequence: str
    provider: str = "in_memory"
    version: str = "1"
    accession: str = ""
    provenance: str = "REFERENCE_DATA"

    @property
    def digest(self) -> str:
        return sha256_text(self.sequence)

    @property
    def length(self) -> int:
        return len(self.sequence)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["digest"] = self.digest
        d["length"] = self.length
        return d


@dataclass
class SequenceSegment:
    sequence_id: str
    start: int
    end: int
    sequence: str
    orientation: str = "+"


@dataclass
class Feature:
    feature_id: str
    kind: str
    location: Coordinate
    name: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SequenceEdit:
    edit_id: str
    operation: str
    start: int
    end: int
    replacement: str = ""
    source: str = ""
    orientation: str = "+"
    reference_sequence: str = ""
    provenance: str = "DESIGN"
    validation: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SequenceConstraint:
    name: str
    expression: str
    status: str = "unchecked"


@dataclass
class SequenceIR:
    reference: str
    assembly: str
    edits: List[SequenceEdit]
    coordinate_system: str = COORDINATE_SYSTEM
    organism: str = ""
    features: List[Feature] = field(default_factory=list)
    constraints: List[SequenceConstraint] = field(default_factory=list)
    type: str = "SequenceIR"
    version: str = SEQUENCE_IR_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "version": self.version,
            "organism": self.organism,
            "assembly": self.assembly,
            "reference": self.reference,
            "coordinate_system": self.coordinate_system,
            "edits": [e.to_dict() for e in self.edits],
            "constraints": [asdict(c) for c in self.constraints],
        }


@dataclass
class DerivedSequence:
    sequence_id: str
    assembly: str
    sequence: str
    parent_digest: str
    digest: str
    edits: List[Dict[str, Any]]
    provenance: str = "DESIGN"
    alphabet: str = "ACGT"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_fasta(self) -> str:
        return f">{self.sequence_id}|{self.assembly}|derived\n{self.sequence}\n"


class SequenceIRError(Exception):
    def __init__(self, status: str, message: str):
        super().__init__(f"{status}: {message}")
        self.status = status
        self.detail = message


def validate_edit(edit: SequenceEdit, ref: ReferenceSequence) -> None:
    if edit.operation not in EDIT_OPERATIONS:
        raise SequenceIRError("UNSUPPORTED_OPERATION", edit.operation)
    if edit.operation not in EXECUTABLE_EDITS:
        raise SequenceIRError("UNSUPPORTED_OPERATION", edit.operation)
    if not (0 <= edit.start <= edit.end <= ref.length):
        raise SequenceIRError("INVALID_EDIT", "coordinates")
    payload = (edit.replacement or "").upper()
    edit.replacement = payload
    if edit.operation in {"REPLACE", "INSERT", "SUBSTITUTE"}:
        if any(c not in DNA_ALPHABET for c in payload):
            raise SequenceIRError("INVALID_EDIT", "nucleotide alphabet")
    if edit.orientation not in {"+", "-", "."}:
        raise SequenceIRError("INVALID_EDIT", "orientation")
    edit.validation = "ok"


def apply_edits(ref: ReferenceSequence, edits: List[SequenceEdit]) -> DerivedSequence:
    for edit in edits:
        validate_edit(edit, ref)
    ordered = sorted(edits, key=lambda e: (e.start, e.end), reverse=True)
    out = ref.sequence
    last_start = len(out) + 1
    for edit in ordered:
        if edit.end > last_start:
            raise SequenceIRError("INVALID_EDIT", "overlapping edits")
        if edit.operation in {"REPLACE", "SUBSTITUTE"}:
            out = out[:edit.start] + edit.replacement + out[edit.end:]
        elif edit.operation == "INSERT":
            out = out[:edit.start] + edit.replacement + out[edit.start:]
        elif edit.operation == "DELETE":
            out = out[:edit.start] + out[edit.end:]
        last_start = edit.start
    if any(c not in DNA_ALPHABET for c in out):
        raise SequenceIRError("INVALID_EDIT", "output alphabet")
    return DerivedSequence(
        sequence_id=ref.sequence_id,
        assembly=ref.assembly,
        sequence=out,
        parent_digest=ref.digest,
        digest=sha256_text(out),
        edits=[e.to_dict() for e in edits],
        provenance="DESIGN",
    )
