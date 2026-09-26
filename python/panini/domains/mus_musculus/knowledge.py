# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Mus musculus reference-locus catalogue. Domain-owned, not core."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import List, Optional

from ...types import EvidenceLevel

ASSEMBLY = "GRCm39"
ASSEMBLY_ACCESSION = "GCF_000001635.27"


def _digest(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


@dataclass
class RetrievalRecord:
    assembly: str
    assembly_accession: str
    chrom: str
    start: int
    end: int
    strand: str
    source_database: str
    versioned_accession: str
    mgi: str
    ncbi_gene: str
    retrieved_at: str
    retrieval_url: str
    digest: str


@dataclass
class Artifact:
    id: str
    organism: str
    taxon_id: int
    kind: str
    function: str
    tissue: str
    symbol: str
    sequence_ref: str
    sequence: Optional[str]
    annotation: str
    provenance: str
    version: str
    evidence: EvidenceLevel
    license: str
    checksum: Optional[str]
    retrieval: Optional[RetrievalRecord]
    drives: str


def _ref(
    symbol: str,
    mgi: str,
    ncbi: str,
    chrom: str,
    start: int,
    end: int,
    strand: str,
    function: str,
    tissue: str,
    annotation: str,
    url: str,
    drives: str,
    retrieved_at: str = "2026-09-25T00:00:00Z",
) -> Artifact:
    acc = f"{mgi}/{ASSEMBLY}"
    rec_body = {
        "assembly": ASSEMBLY,
        "assembly_accession": ASSEMBLY_ACCESSION,
        "chrom": chrom,
        "start": start,
        "end": end,
        "strand": strand,
        "source_database": "MGI+NCBI RefSeq",
        "versioned_accession": acc,
        "mgi": mgi,
        "ncbi_gene": ncbi,
        "retrieved_at": retrieved_at,
        "retrieval_url": url,
    }
    digest = _digest(rec_body)
    rec = RetrievalRecord(digest=digest, **rec_body)
    return Artifact(
        id=f"mmu.{symbol}",
        organism="Mus musculus",
        taxon_id=10090,
        kind="REFERENCE_LOCUS",
        function=function,
        tissue=tissue,
        symbol=symbol,
        sequence_ref=f"mgi://{mgi}@{ASSEMBLY}",
        sequence=None,
        annotation=annotation,
        provenance=f"{mgi}; {url}",
        version="0.3.0",
        evidence=EvidenceLevel.WIDELY_VALIDATED,
        license="reference annotation; not a designed construct",
        checksum=digest,
        retrieval=rec,
        drives=drives,
    )


def mouse_axial_library() -> List[Artifact]:
    return [
        _ref("Wnt3a", "MGI:98956", "22416", "11", 59138859, 59181578, "-",
             "developmental_patterning", "axial",
             "posteriorizing Wnt source (PSM / tail bud)",
             "https://www.informatics.jax.org/marker/MGI:98956", "wnt"),
        _ref("Fgf8", "MGI:99604", "14179", "19", 45725237, 45731354, "-",
             "developmental_patterning", "axial",
             "caudal FGF wavefront",
             "https://www.informatics.jax.org/marker/MGI:99604", "fgf"),
        _ref("Cdx2", "MGI:88361", "12591", "5", 147237710, 147244059, "-",
             "developmental_patterning", "axial",
             "posterior identity transcription factor",
             "https://www.ncbi.nlm.nih.gov/gene/12591", "cdx"),
        _ref("Hoxd13", "MGI:96205", "15433", "2", 74498569, 74501947, "+",
             "developmental_patterning", "axial",
             "posterior Hox code",
             "https://www.informatics.jax.org/marker/MGI:96205", "hox"),
        _ref("Aldh1a2", "MGI:107928", "19378", "9", 71123071, 71203525, "+",
             "developmental_patterning", "axial",
             "RA synthesis; anteriorizing counter-gradient (Raldh2)",
             "https://ensembl.org/Mus_musculus/Gene/Summary?g=ENSMUSG00000013584", "ra"),
    ]


SYMBOL_ALIASES = {"Raldh2": "Aldh1a2", "mmu.Raldh2": "mmu.Aldh1a2"}


def verify_retrievals() -> List[str]:
    errors = []
    for a in mouse_axial_library():
        if a.sequence is not None:
            errors.append(f"{a.id}: REFERENCE_LOCUS must not carry a sequence string")
        if a.retrieval is None:
            errors.append(f"{a.id}: missing retrieval record")
            continue
        body = {k: v for k, v in asdict(a.retrieval).items() if k != "digest"}
        got = _digest(body)
        if got != a.retrieval.digest or got != a.checksum:
            errors.append(f"{a.id}: retrieval digest mismatch")
    return errors


def modules_for_intent(primary: str, secondary: Optional[str] = None) -> List[Artifact]:
    lib = {a.symbol: a for a in mouse_axial_library()}
    if primary == "tail":
        chosen = ["Wnt3a", "Fgf8", "Cdx2", "Hoxd13", "Aldh1a2"]
    elif primary == "head":
        chosen = ["Aldh1a2"]
    else:
        chosen = ["Aldh1a2"]
    return [lib[s] for s in chosen if s in lib]
