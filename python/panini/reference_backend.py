# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Reference backend contract.

Adapters may later bind NCBI Datasets, GA4GH Refget / Sequence Collections,
FASTA, or GFF3. The MVP ships an in-memory backend so the compiler can
resolve a pinned reference without embedding an encyclopedia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, Tuple

from .sequence_ir import ReferenceSequence, SequenceIRError, sha256_text
from .version import REFERENCE_CONTRACT_VERSION


STANDARDS = {
    "NCBI_Datasets": {
        "role": "genome package retrieval by assembly accession",
        "example": "assembly accessions such as GCF_* identify a versioned package",
        "mvp": "not connected; adapter slot only",
    },
    "GA4GH_Refget": {
        "role": "content-derived identifiers for reference sequences",
        "example": "retrieve sequence by digest rather than mutable name",
        "mvp": "local SHA-256 digest is the MVP stand-in; Refget HTTP not bundled",
    },
    "GA4GH_Sequence_Collections": {
        "role": "identify collections such as reference assemblies",
        "example": "compare / retrieve named collections of sequences",
        "mvp": "in-memory collection keyed by assembly id",
    },
    "GA4GH_VR": {
        "role": "variation representation independent of a single edit syntax",
        "mvp": "SequenceEdit is a local IR; VR adapter is future work",
    },
    "FASTA": {"role": "literal sequence exchange", "mvp": "emitted as derived.fasta"},
    "GFF3": {"role": "feature annotation", "mvp": "resolve_feature is stubbed"},
}


class ReferenceBackend(Protocol):
    def resolve_assembly(self, assembly: str) -> Dict[str, Any]: ...
    def resolve_sequence(self, assembly: str, sequence_id: str) -> ReferenceSequence: ...
    def retrieve_interval(self, assembly: str, sequence_id: str, start: int, end: int) -> str: ...
    def resolve_feature(self, feature_id: str) -> Optional[Dict[str, Any]]: ...
    def verify_digest(self, ref: ReferenceSequence, digest: str) -> bool: ...
    def retrieve_metadata(self, assembly: str, sequence_id: str) -> Dict[str, Any]: ...


@dataclass
class MemoryReferenceBackend:
    refs: Dict[Tuple[str, str], ReferenceSequence]
    assemblies: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    features: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    provider: str = "in_memory"
    version: str = REFERENCE_CONTRACT_VERSION

    def resolve_assembly(self, assembly: str) -> Dict[str, Any]:
        if assembly in self.assemblies:
            return dict(self.assemblies[assembly])
        seqs = [sid for (asm, sid) in self.refs if asm == assembly]
        if not seqs:
            raise SequenceIRError("REFERENCE_UNAVAILABLE", f"assembly {assembly}")
        return {
            "assembly": assembly,
            "sequences": seqs,
            "provider": self.provider,
            "version": self.version,
        }

    def resolve_sequence(self, assembly: str, sequence_id: str) -> ReferenceSequence:
        try:
            return self.refs[(assembly, sequence_id)]
        except KeyError:
            raise SequenceIRError("REFERENCE_UNAVAILABLE", f"{assembly}:{sequence_id}") from None

    def retrieve_interval(self, assembly: str, sequence_id: str, start: int, end: int) -> str:
        ref = self.resolve_sequence(assembly, sequence_id)
        if not (0 <= start <= end <= ref.length):
            raise SequenceIRError("INVALID_EDIT", "interval")
        return ref.sequence[start:end]

    def resolve_feature(self, feature_id: str) -> Optional[Dict[str, Any]]:
        return self.features.get(feature_id)

    def verify_digest(self, ref: ReferenceSequence, digest: str) -> bool:
        return ref.digest == digest

    def retrieve_metadata(self, assembly: str, sequence_id: str) -> Dict[str, Any]:
        ref = self.resolve_sequence(assembly, sequence_id)
        return {
            "provider": ref.provider,
            "accession": ref.accession or f"{assembly}:{sequence_id}",
            "identifier": ref.sequence_id,
            "version": ref.version,
            "digest": ref.digest,
            "retrieval_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "provenance": ref.provenance,
            "length": ref.length,
            "contract_version": self.version,
        }


def demo_backend() -> MemoryReferenceBackend:
    ref = ReferenceSequence(
        sequence_id="chrDemo",
        assembly="demo-v1",
        sequence="AACCGGTTAACC",
        provider="in_memory",
        version="1",
        accession="panini:demo-v1:chrDemo",
        provenance="REFERENCE_DATA",
    )
    alt = ReferenceSequence(
        sequence_id="chrDemo",
        assembly="demo-v2",
        sequence="TTTTGGTTAACC",
        provider="in_memory",
        version="2",
        accession="panini:demo-v2:chrDemo",
        provenance="REFERENCE_DATA",
    )
    return MemoryReferenceBackend(
        refs={
            ("demo-v1", "chrDemo"): ref,
            ("demo-v2", "chrDemo"): alt,
        },
        assemblies={
            "demo-v1": {
                "assembly": "demo-v1",
                "sequences": ["chrDemo"],
                "provider": "in_memory",
                "note": "synthetic MVP reference; not a biological assembly",
            },
            "demo-v2": {
                "assembly": "demo-v2",
                "sequences": ["chrDemo"],
                "provider": "in_memory",
                "note": "alternate synthetic reference used for digest-change tests",
            },
        },
    )


_DEFAULT: Optional[MemoryReferenceBackend] = None


def default_backend() -> MemoryReferenceBackend:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = demo_backend()
    return _DEFAULT


def standards_note() -> Dict[str, Any]:
    return {
        "contract_version": REFERENCE_CONTRACT_VERSION,
        "policy": "reference by provider + accession + digest + version + timestamp; do not embed encyclopedias",
        "standards": STANDARDS,
    }
