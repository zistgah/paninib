# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Living biological knowledge spine.

PANINI Core owns the record schema and provider interfaces.
It does not own an encyclopedia of biology.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Protocol, Set


KNOWLEDGE_KINDS = (
    "Genome",
    "Sequence",
    "Gene",
    "Transcript",
    "Protein",
    "RegulatoryElement",
    "Variant",
    "StructuralVariant",
    "Pathway",
    "GeneRegulatoryRelation",
    "CellType",
    "Phenotype",
    "BiologicalProcess",
    "MolecularFunction",
    "Evidence",
    "Publication",
    "Organism",
    "Assembly",
    "RealizationMapping",
    "StandardPart",
    "Mechanism",
    "CausalClaim",
    "SequencePart",
    "Feature",
    "PhenotypeAssociation",
    "CausalRelationship",
    "ModelParameter",
    "Reference",
)

EVIDENCE_STATUS = (
    "authoritative_reference",
    "curated",
    "computational_prediction",
    "model_assumption",
    "unverified_candidate",
)

PROVENANCE_CLASS = (
    "REFERENCE_DATA",
    "EVIDENCE",
    "MODEL",
    "INFERENCE",
    "DESIGN",
    "SIMULATION",
    "OBSERVATION",
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class KnowledgeRecord:
    canonical_id: str
    namespace: str
    name: str
    kind: str
    version: str = "0.6.0"
    source: str = "panini.core"
    source_id: str = ""
    provenance: str = "MODEL"
    evidence_status: str = "unverified_candidate"
    validity_domain: str = "unspecified"
    created: str = ""
    updated: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in KNOWLEDGE_KINDS:
            raise ValueError(f"unknown knowledge kind: {self.kind}")
        if self.evidence_status not in EVIDENCE_STATUS:
            raise ValueError(f"unknown evidence_status: {self.evidence_status}")
        if self.provenance not in PROVENANCE_CLASS:
            raise ValueError(f"unknown provenance class: {self.provenance}")
        if not self.created:
            self.created = _now()
        if not self.updated:
            self.updated = self.created
        if not self.source_id:
            self.source_id = self.canonical_id

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class KnowledgeProvider(Protocol):
    def resolve(self, canonical_id: str) -> Optional[KnowledgeRecord]: ...
    def search(self, query: str, limit: int = 20) -> List[KnowledgeRecord]: ...
    def capabilities(self) -> Set[str]: ...
    def provenance(self) -> Dict[str, Any]: ...
    def version(self) -> str: ...


class SequenceProvider(Protocol):
    def resolve_sequence(self, assembly: str, sequence_id: str) -> Optional[KnowledgeRecord]: ...


class GenomeProvider(Protocol):
    def resolve_genome(self, organism: str) -> Optional[KnowledgeRecord]: ...


class AnnotationProvider(Protocol):
    def resolve_feature(self, feature_id: str) -> Optional[KnowledgeRecord]: ...


class VariantProvider(Protocol):
    def resolve_variant(self, variant_id: str) -> Optional[KnowledgeRecord]: ...


class EvidenceProvider(Protocol):
    def resolve_evidence(self, evidence_id: str) -> Optional[KnowledgeRecord]: ...


class PhenotypeProvider(Protocol):
    def resolve_phenotype(self, phenotype_id: str) -> Optional[KnowledgeRecord]: ...


class PathwayProvider(Protocol):
    def resolve_pathway(self, pathway_id: str) -> Optional[KnowledgeRecord]: ...


class MemoryKnowledgeProvider:
    """Minimal in-core provider. Domain plugins register additional records."""

    def __init__(self, name: str, version: str, records: Iterable[KnowledgeRecord]):
        self._name = name
        self._version = version
        self._records: Dict[str, KnowledgeRecord] = {}
        for rec in records:
            self._records[rec.canonical_id] = rec
            self._records[rec.canonical_id.lower()] = rec

    def resolve(self, canonical_id: str) -> Optional[KnowledgeRecord]:
        return self._records.get(canonical_id) or self._records.get(canonical_id.lower())

    def search(self, query: str, limit: int = 20) -> List[KnowledgeRecord]:
        q = query.lower()
        seen = set()
        out: List[KnowledgeRecord] = []
        for rec in self._records.values():
            if id(rec) in seen:
                continue
            blob = f"{rec.canonical_id} {rec.name} {rec.kind} {rec.namespace}".lower()
            if q in blob:
                seen.add(id(rec))
                out.append(rec)
            if len(out) >= limit:
                break
        return out

    def capabilities(self) -> Set[str]:
        return {rec.kind for rec in {id(r): r for r in self._records.values()}.values()}

    def provenance(self) -> Dict[str, Any]:
        return {
            "provider": self._name,
            "version": self._version,
            "class": "REFERENCE_DATA" if self._name.endswith("reference") else "MODEL",
        }

    def version(self) -> str:
        return self._version

    def add(self, rec: KnowledgeRecord) -> None:
        self._records[rec.canonical_id] = rec
        self._records[rec.canonical_id.lower()] = rec

    def remove(self, canonical_id: str) -> None:
        rec = self._records.get(canonical_id) or self._records.get(canonical_id.lower())
        if rec is None:
            return
        for key in list(self._records):
            if self._records[key] is rec:
                del self._records[key]

    def records(self) -> List[KnowledgeRecord]:
        seen = set()
        out: List[KnowledgeRecord] = []
        for rec in self._records.values():
            if id(rec) in seen:
                continue
            seen.add(id(rec))
            out.append(rec)
        return out


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: Dict[str, KnowledgeProvider] = {}

    def register(self, name: str, provider: KnowledgeProvider) -> None:
        self._providers[name] = provider

    def get(self, name: str) -> KnowledgeProvider:
        return self._providers[name]

    def names(self) -> List[str]:
        return sorted(self._providers)

    def resolve(self, canonical_id: str) -> Optional[KnowledgeRecord]:
        for provider in self._providers.values():
            rec = provider.resolve(canonical_id)
            if rec is not None:
                return rec
        return None

    def search(self, query: str, limit: int = 20) -> List[KnowledgeRecord]:
        hits: List[KnowledgeRecord] = []
        for provider in self._providers.values():
            hits.extend(provider.search(query, limit=limit))
            if len(hits) >= limit:
                break
        return hits[:limit]

    def writable(self, name: str = "session") -> MemoryKnowledgeProvider:
        provider = self._providers.get(name)
        if provider is None or not isinstance(provider, MemoryKnowledgeProvider):
            provider = MemoryKnowledgeProvider(f"panini.knowledge.{name}", "0.7.0", [])
            self._providers[name] = provider
        return provider

    def add_record(self, rec: KnowledgeRecord, provider: str = "session") -> KnowledgeRecord:
        self.writable(provider).add(rec)
        return rec

    def remove_record(self, canonical_id: str, provider: str = "session") -> None:
        self.writable(provider).remove(canonical_id)

    def records_of_kind(self, kind: str) -> List[KnowledgeRecord]:
        seen = set()
        out: List[KnowledgeRecord] = []
        for provider in self._providers.values():
            recs = provider.records() if isinstance(provider, MemoryKnowledgeProvider) else []
            for rec in recs:
                if rec.kind != kind or id(rec) in seen:
                    continue
                seen.add(id(rec))
                out.append(rec)
        return out


def mvp_records() -> List[KnowledgeRecord]:
    """Just enough records to demonstrate organism/assembly/sequence/provenance."""
    return [
        KnowledgeRecord(
            canonical_id="org:synthetic",
            namespace="panini",
            name="synthetic",
            kind="Organism",
            source="panini.knowledge.mvp",
            provenance="MODEL",
            evidence_status="model_assumption",
            validity_domain="non-biological-conformance",
            attributes={"scientific": False, "note": "TEST fixture organism"},
        ),
        KnowledgeRecord(
            canonical_id="org:TestOrganismA",
            namespace="panini.conformance",
            name="TestOrganismA",
            kind="Organism",
            source="panini.domains.conformance",
            provenance="MODEL",
            evidence_status="model_assumption",
            validity_domain="conformance",
        ),
        KnowledgeRecord(
            canonical_id="org:TestOrganismB",
            namespace="panini.conformance",
            name="TestOrganismB",
            kind="Organism",
            source="panini.domains.conformance",
            provenance="MODEL",
            evidence_status="model_assumption",
            validity_domain="conformance",
        ),
        KnowledgeRecord(
            canonical_id="asm:demo-v1",
            namespace="panini",
            name="demo-v1",
            kind="Assembly",
            source="panini.knowledge.mvp",
            provenance="REFERENCE_DATA",
            evidence_status="curated",
            validity_domain="synthetic-demo",
            attributes={"sequences": ["chrDemo"], "length": 12},
        ),
        KnowledgeRecord(
            canonical_id="seq:demo-v1:chrDemo",
            namespace="panini",
            name="chrDemo",
            kind="Sequence",
            source="panini.knowledge.mvp",
            provenance="REFERENCE_DATA",
            evidence_status="curated",
            validity_domain="synthetic-demo",
            attributes={"assembly": "demo-v1", "length": 12, "alphabet": "ACGT"},
        ),
        KnowledgeRecord(
            canonical_id="pheno:explicit_sequence_transformation",
            namespace="panini",
            name="explicit_sequence_transformation",
            kind="Phenotype",
            source="panini.knowledge.mvp",
            provenance="DESIGN",
            evidence_status="model_assumption",
            validity_domain="compiler-demo",
            attributes={"maps_to_sequence": True, "causal": False},
        ),
    ]


_REGISTRY: Optional[ProviderRegistry] = None


def reset_knowledge_registry() -> ProviderRegistry:
    global _REGISTRY
    _REGISTRY = ProviderRegistry()
    _REGISTRY.register("mvp", MemoryKnowledgeProvider("panini.knowledge.mvp", "0.7.0", mvp_records()))
    _REGISTRY.register("stdlib", MemoryKnowledgeProvider("panini.knowledge.stdlib", "0.7.0", stdlib_records()))
    _REGISTRY.register("session", MemoryKnowledgeProvider("panini.knowledge.session", "0.7.0", []))
    return _REGISTRY


def get_knowledge_registry() -> ProviderRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        reset_knowledge_registry()
    return _REGISTRY


def stdlib_records() -> List[KnowledgeRecord]:
    return [
        KnowledgeRecord(
            canonical_id="part:demo.reporter_cassette",
            namespace="panini.stdlib",
            name="reporter_cassette",
            kind="StandardPart",
            version="0.7.0",
            source="panini.knowledge.stdlib",
            provenance="REFERENCE_DATA",
            evidence_status="curated",
            validity_domain="synthetic-demo",
            attributes={"organism": "synthetic", "assembly": "demo-v1", "reference": "chrDemo"},
        ),
        KnowledgeRecord(
            canonical_id="ev:demo.reporter_cassette",
            namespace="panini.stdlib",
            name="reporter_cassette_curation",
            kind="Evidence",
            version="0.7.0",
            source="panini.knowledge.stdlib",
            provenance="EVIDENCE",
            evidence_status="curated",
            validity_domain="synthetic-demo",
            attributes={"supports": "realize:synthetic:reporter_cassette", "class": "MECHANISTICALLY_SUPPORTED"},
        ),
        KnowledgeRecord(
            canonical_id="realize:synthetic:reporter_cassette",
            namespace="panini.stdlib",
            name="reporter_cassette",
            kind="RealizationMapping",
            version="0.7.0",
            source="panini.knowledge.stdlib",
            provenance="DESIGN",
            evidence_status="curated",
            validity_domain="synthetic-demo",
            attributes={
                "organism": "synthetic",
                "intent_verb": "use_part",
                "intent_name": "reporter_cassette",
                "association_class": "MECHANISTICALLY_SUPPORTED",
                "causal_basis": "STANDARD_PART",
                "validation_status": "NOT_VALIDATED",
                "strategy": "STANDARD_LIBRARY",
                "assembly": "demo-v1",
                "reference": "chrDemo",
                "standard_part": "part:demo.reporter_cassette",
                "evidence_ids": ["ev:demo.reporter_cassette"],
                "provider": "stdlib",
                "edits": [{"operation": "REPLACE", "start": 0, "end": 4, "replacement": "GGGG"}],
            },
        ),
        KnowledgeRecord(
            canonical_id="assoc:synthetic:glow",
            namespace="panini.stdlib",
            name="glow_association_only",
            kind="CausalClaim",
            version="0.7.0",
            source="panini.knowledge.stdlib",
            provenance="EVIDENCE",
            evidence_status="unverified_candidate",
            validity_domain="synthetic-demo",
            attributes={
                "organism": "synthetic",
                "intent_verb": "establish",
                "intent_name": "glow_associated",
                "association_class": "ASSOCIATED",
                "gene": "demoX",
                "phenotype": "glow",
                "licenses_inverse": False,
                "direction": "lof",
            },
        ),
    ]


def lookup_realization_records(organism: str, intent_verb: str, intent_name: str) -> List[KnowledgeRecord]:
    org = (organism or "").lower()
    verb = (intent_verb or "").lower()
    name = (intent_name or "").lower()
    hits: List[KnowledgeRecord] = []
    for rec in get_knowledge_registry().records_of_kind("RealizationMapping"):
        attrs = rec.attributes or {}
        rec_org = str(attrs.get("organism", "")).lower()
        rec_verb = str(attrs.get("intent_verb", "")).lower()
        rec_name = str(attrs.get("intent_name", rec.name)).lower()
        aliases = [a.lower() for a in attrs.get("organism_aliases", [])]
        org_ok = (not rec_org) or rec_org == org or org in aliases
        verb_ok = (not rec_verb) or rec_verb == verb
        name_ok = rec_name == name or rec.canonical_id.lower().endswith(":" + name)
        if org_ok and verb_ok and name_ok:
            hits.append(rec)
    return hits


def lookup_association_records(organism: str, intent_verb: str, intent_name: str) -> List[KnowledgeRecord]:
    org = (organism or "").lower()
    verb = (intent_verb or "").lower()
    name = (intent_name or "").lower()
    hits: List[KnowledgeRecord] = []
    for rec in get_knowledge_registry().records_of_kind("CausalClaim"):
        attrs = rec.attributes or {}
        rec_org = str(attrs.get("organism", "")).lower()
        rec_verb = str(attrs.get("intent_verb", "")).lower()
        rec_name = str(attrs.get("intent_name", rec.name)).lower()
        if rec_org in {"", org} and rec_verb in {"", verb} and rec_name == name:
            hits.append(rec)
    return hits
