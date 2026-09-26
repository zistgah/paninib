# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Mus musculus GRCm39 locus retrieval. Domain-owned. Never invent nucleotides."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
from urllib.request import Request, urlopen

# Domain-owned snapshot. Repository data/retrieved is Mus musculus data, not core.
DATA = Path(__file__).resolve().parents[4] / "data" / "retrieved"

NCBI = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

LOCI = {
    "Wnt3a": dict(acc="NC_000077.7", start=59138859, stop=59181578, strand=2, chrom="11"),
    "Fgf8": dict(acc="NC_000085.7", start=45725237, stop=45731354, strand=2, chrom="19"),
    "Cdx2": dict(acc="NC_000071.7", start=147237710, stop=147244059, strand=2, chrom="5"),
    "Hoxd13": dict(acc="NC_000068.8", start=74498569, stop=74501947, strand=1, chrom="2"),
    "Aldh1a2": dict(acc="NC_000075.7", start=71123071, stop=71203525, strand=1, chrom="9"),
}


@dataclass
class RetrievedSequence:
    symbol: str
    header: str
    sequence: str
    path: str
    sha256: str
    source_url: str
    assembly: str = "GRCm39"
    assembly_accession: str = "GCF_000001635.27"


def _parse_fasta(text: str) -> tuple[str, str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines or not lines[0].startswith(">"):
        raise ValueError("not FASTA")
    header = lines[0][1:]
    seq = "".join(lines[1:]).upper()
    if not seq or any(ch not in "ACGTN" for ch in seq):
        raise ValueError("FASTA contains non-ACGTN or is empty")
    return header, seq


def load_cached(symbol: str) -> RetrievedSequence:
    path = DATA / f"{symbol}.fa"
    if not path.exists():
        raise FileNotFoundError(path)
    header, seq = _parse_fasta(path.read_text())
    digest = hashlib.sha256(seq.encode()).hexdigest()
    meta = LOCI[symbol]
    url = (
        f"{NCBI}?db=nuccore&id={meta['acc']}&seq_start={meta['start']}"
        f"&seq_stop={meta['stop']}&strand={meta['strand']}&rettype=fasta"
    )
    return RetrievedSequence(symbol, header, seq, str(path), digest, url)


def fetch(symbol: str, timeout: int = 30) -> RetrievedSequence:
    meta = LOCI[symbol]
    url = (
        f"{NCBI}?db=nuccore&id={meta['acc']}&seq_start={meta['start']}"
        f"&seq_stop={meta['stop']}&strand={meta['strand']}&rettype=fasta&retmode=text"
    )
    req = Request(url, headers={"User-Agent": "PANINI/0.4 AyeAI research"})
    with urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode()
    header, seq = _parse_fasta(text)
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / f"{symbol}.fa").write_text(f">{header}\n" + "\n".join(seq[i:i+70] for i in range(0, len(seq), 70)) + "\n")
    return load_cached(symbol)


def load_all() -> Dict[str, RetrievedSequence]:
    out = {}
    for symbol in LOCI:
        try:
            out[symbol] = load_cached(symbol)
        except FileNotFoundError:
            out[symbol] = fetch(symbol)
    return out


def to_genbank(rec: RetrievedSequence, locus_tag: str) -> str:
    meta = LOCI[rec.symbol]
    seq = rec.sequence
    n = len(seq)
    lines = [
        f"LOCUS       {rec.symbol:<16}{n:>8} bp    DNA     linear   ROD 25-SEP-2026",
        f"DEFINITION  Mus musculus {rec.symbol} retrieved from {rec.assembly} {meta['acc']}:{meta['start']}..{meta['stop']}.",
        f"ACCESSION   {meta['acc']}",
        f"VERSION     {meta['acc']}",
        f"KEYWORDS    REFERENCE_LOCUS; not a designed construct.",
        f"SOURCE      Mus musculus (house mouse)",
        f"  ORGANISM  Mus musculus",
        f"COMMENT     Copyright © 1993-2026 Abhishek Choudhary. All rights reserved.",
        f"COMMENT     Retrieved snapshot. SHA256={rec.sha256}",
        f"COMMENT     SOURCE {rec.source_url}",
        f"COMMENT     This record is a reference annotation, not an authorised synthesis file.",
        f"FEATURES             Location/Qualifiers",
        f"     source          1..{n}",
        f"                     /organism=\"Mus musculus\"",
        f"                     /mol_type=\"genomic DNA\"",
        f"                     /assembly=\"{rec.assembly}\"",
        f"                     /chromosome=\"{meta['chrom']}\"",
        f"     gene            1..{n}",
        f"                     /gene=\"{rec.symbol}\"",
        f"                     /locus_tag=\"{locus_tag}\"",
        "ORIGIN",
    ]
    for i in range(0, n, 60):
        chunk = seq[i:i+60]
        spaced = " ".join(chunk[j:j+10] for j in range(0, len(chunk), 10))
        lines.append(f"{i+1:>9} {spaced}")
    lines.append("//")
    return "\n".join(lines) + "\n"
