# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""PANINI Core / biological-domain contracts.

These types are the only way the compiler core may talk to an organism,
genome, developmental model, or realization strategy. Core code must not
name a species, locus, or phenotype-specific geometry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Set


@dataclass
class ContractMeta:
    """Identity and provenance shared by every domain contract."""

    id: str
    version: str
    kind: str
    capabilities: List[str] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    state_representation: str = ""
    validity_domain: str = ""
    provenance: List[str] = field(default_factory=list)
    evidence_status: str = "UNKNOWN"
    label: str = ""


@dataclass
class OrganismModel:
    """Who the program is about. Not a genome and not an executor."""

    meta: ContractMeta
    taxon_name: str
    taxon_id: Optional[int]
    aliases: List[str]
    default_model_id: Optional[str]
    default_backend: str
    genome_model_id: Optional[str] = None
    knowledge_model_id: Optional[str] = None
    development_model_id: Optional[str] = None
    phenotype_model_id: Optional[str] = None
    geometry_model_id: Optional[str] = None
    realization_model_id: Optional[str] = None
    evidence_model_id: Optional[str] = None
    package: str = ""
    scientific: bool = True


@dataclass
class GenomeModel:
    """Locus catalogue and intent→module composition. No invented sequence."""

    meta: ContractMeta
    organism_id: str
    assembly: Optional[str] = None
    assembly_accession: Optional[str] = None
    data_version: str = ""
    artifacts_fn: Optional[Callable[[], List[Any]]] = None
    modules_for_intent_fn: Optional[Callable[..., List[Any]]] = None
    verify_fn: Optional[Callable[[], List[str]]] = None


@dataclass
class BiologicalKnowledgeModel:
    """Causal / prior graph used at analysis time. Domain-owned."""

    meta: ContractMeta
    organism_id: str
    build_causal_fn: Optional[Callable[[Any], Any]] = None
    intent_capabilities_fn: Optional[Callable[[Any], List[str]]] = None


@dataclass
class DevelopmentModel:
    """Stage vocabulary and developmental update rules."""

    meta: ContractMeta
    organism_id: str
    stages: List[str] = field(default_factory=list)


@dataclass
class PhenotypeModel:
    """How a domain projects state onto phenotype fields."""

    meta: ContractMeta
    organism_id: str
    properties: List[str] = field(default_factory=list)


@dataclass
class GeometryModel:
    """Spatial representation declared by a domain model."""

    meta: ContractMeta
    spatial_dimension: int
    topology: str


@dataclass
class EvidenceModel:
    """Evidence grade attached to domain data, not to core."""

    meta: ContractMeta
    data_version: str = ""
    evidence_version: str = ""
    references: List[str] = field(default_factory=list)


@dataclass
class RealizationModel:
    """How a domain turns CISC into a specification package."""

    meta: ContractMeta
    organism_id: str
    library_id: str = ""
    realize_note: str = ""


class ExecutionModel(Protocol):
    """Runtime twin. Core engine calls these methods and nothing species-named."""

    id: str

    def initialize(self, genotype: Any, params: Any) -> Any: ...

    def transcribe(self, state: Any, genotype: Any, params: Any) -> Dict[str, float]: ...

    def translate(self, state: Any, genotype: Any, params: Any) -> Dict[str, float]: ...

    def react(self, state: Any, genotype: Any, params: Any) -> None: ...

    def update_cells(self, state: Any, params: Any) -> List[str]: ...

    def update_development(self, state: Any) -> str: ...

    def compile_time_simulate(self, bio: Any) -> Any: ...

    def adjust_compile_preview(self, predicted_bundle: Dict[str, Any], bio: Any, sim: Any) -> Dict[str, Any]: ...

    def plan_simulation(self, bio: Any) -> Any: ...


@dataclass
class ModelDescriptor:
    """Capability card the resolver uses. No species switch in core."""

    id: str
    package: str
    organism: str
    organism_aliases: List[str]
    domain: str
    spatial_dimension: int
    fidelity: str
    capabilities: Set[str]
    implemented: bool
    stochastic: bool
    gpu: bool
    status: str
    version: str
    data_version: str
    evidence_version: str
    reference_assembly: Optional[str]
    default_for_organism: bool
    kind: str
    label: str
    dimensions: int = 1

    def __post_init__(self) -> None:
        if not self.dimensions:
            self.dimensions = self.spatial_dimension
