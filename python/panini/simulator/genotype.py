"""Semantic compiled genotype — not a naked ATGC string."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Locus:
    identity: str
    chrom: str
    start: int
    end: int
    kind: str
    strand: str = "+"
    context: str = "developmental"
    source: str = ""
    version: str = "0.2.0"


@dataclass
class Gene:
    identity: str
    locus: Locus
    symbol: str
    role: str
    sequence_ref: str
    artifact_id: str
    evidence: str
    source_cisc: List[str] = field(default_factory=list)
    source_risc: List[str] = field(default_factory=list)
    source_micro: List[str] = field(default_factory=list)
    source_intent: str = ""
    copy_number: int = 1


@dataclass
class RegulatoryRegion:
    identity: str
    target: str
    kind: str
    strength: float = 1.0


@dataclass
class CompiledGenotype:
    program_id: str
    organism: str
    chromosomes: List[Dict[str, Any]]
    genes: List[Gene]
    loci: List[Locus]
    regulatory_regions: List[RegulatoryRegion]
    variants: List[Dict[str, Any]]
    epigenetic_initial_state: Dict[str, str]
    structural_variants: List[Dict[str, Any]]
    copy_numbers: Dict[str, int]
    genomic_context: str
    provenance: List[str]
    source_hash: str
    compiler_version: str
    realization_note: str

    def gene(self, identity: str) -> Optional[Gene]:
        key = identity.lower()
        for g in self.genes:
            if g.identity.lower() == key or g.symbol.lower() == key or g.artifact_id.lower() == key:
                return g
            if key in g.identity.lower() or key in g.artifact_id.lower():
                return g
        return None

    @staticmethod
    def from_compile_payload(payload: Dict[str, Any]) -> "CompiledGenotype":
        realization = payload.get("realization", {})
        constructs = realization.get("construct_specification", [])
        cisc = payload.get("cisc", {}).get("instructions", [])
        risc = payload.get("risc", {}).get("instructions", [])
        micro = payload.get("microcode", {}).get("ops", [])
        organism = payload.get("universal", {}).get("organism", "Mouse")

        genes: List[Gene] = []
        loci: List[Locus] = []
        regs: List[RegulatoryRegion] = []
        copy_numbers: Dict[str, int] = {}

        # Bind compilation ancestry by role keywords so debugger can climb
        # PANINI → CISC → RISC → microcode → physical event.
        def ancestry_for(role: str, artifact: str):
            cisc_ids, risc_ids, micro_ids, intent = [], [], [], ""
            keys = [role, artifact]
            if "posteriorizing" in role:
                keys += ["SENSE", "REGULATE", "SIGNAL"]
            if "anterior" in role:
                keys += ["SENSE", "REGULATE"]
            if "identity" in role:
                keys += ["DIFFERENTIATE", "DEVELOP", "REGULATE"]
            blob = " ".join(keys).lower()
            for ins in cisc:
                op = (ins.get("opcode") or "").lower()
                writes = " ".join(ins.get("state_writes") or []).lower()
                if op in blob or any(k.lower() in writes or k.lower() in op for k in keys):
                    cisc_ids.append(ins.get("id", ""))
                    intent = ins.get("source_intent") or intent
            for ins in risc:
                if ins.get("source_cisc") in cisc_ids:
                    risc_ids.append(ins.get("id", ""))
            for op in micro:
                if op.get("source_risc") in risc_ids:
                    micro_ids.append(op.get("id", ""))
            return cisc_ids[:6], risc_ids[:12], micro_ids[:12], intent

        for i, c in enumerate(constructs):
            artifact = c.get("artifact_id", f"G{i:06d}")
            role = c.get("role", "module")
            chrom = str(c.get("chrom") or "unplaced")
            start = int(c.get("start") or 0)
            end = int(c.get("end") or 0)
            strand = c.get("strand") or "."
            gid = f"G{i+1:06d}"
            loc = Locus(
                identity=f"{chrom}:{start}..{end}:{strand}",
                chrom=chrom,
                start=start,
                end=end,
                strand=strand,
                kind="coding" if "program" in role or "signal" in role else "regulatory",
                context="developmental",
                source=c.get("sequence_ref", ""),
            )
            loci.append(loc)
            cisc_ids, risc_ids, micro_ids, intent = ancestry_for(role, artifact)
            gene = Gene(
                identity=gid,
                locus=loc,
                symbol=artifact.split(".")[-1] if "." in artifact else artifact,
                role=role,
                sequence_ref=c.get("sequence_ref", ""),
                artifact_id=artifact,
                evidence=c.get("evidence", ""),
                source_cisc=cisc_ids,
                source_risc=risc_ids,
                source_micro=micro_ids,
                source_intent=intent,
                copy_number=1,
            )
            genes.append(gene)
            copy_numbers[gid] = 1
            regs.append(RegulatoryRegion(
                identity=f"REG_{gid}",
                target=gid,
                kind="promoter",
                strength=1.0 if "posterior" in role or "identity" in role else 0.8,
            ))

        chroms = sorted({l.chrom for l in loci})
        return CompiledGenotype(
            program_id=payload.get("program_id", "unknown"),
            organism=organism,
            chromosomes=[{"name": c, "topology": "linear", "metadata": {"organism": organism}} for c in chroms],
            genes=genes,
            loci=loci,
            regulatory_regions=regs,
            variants=[],
            epigenetic_initial_state={g.identity: "permissive" for g in genes},
            structural_variants=[],
            copy_numbers=copy_numbers,
            genomic_context=payload.get("architecture", {}).get("domain_package") or "compiled_genotype",
            provenance=list(realization.get("provenance") or []) + [
                f"compiler={payload.get('compiler')}@{payload.get('version')}",
                f"source_hash={payload.get('source_hash')}",
            ],
            source_hash=payload.get("source_hash", ""),
            compiler_version=str(payload.get("version", "")),
            realization_note=realization.get("note", ""),
        )
