from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class BioType(str, Enum):
    INFORMATION = "Information"
    SEQUENCE = "Sequence"
    DNA = "DNA"
    RNA = "RNA"
    PROTEIN = "Protein"
    MOLECULE = "Molecule"
    COMPLEX = "Complex"
    CELL = "Cell"
    CELL_TYPE = "CellType"
    TISSUE = "Tissue"
    ORGAN = "Organ"
    ORGANISM = "Organism"
    POPULATION = "Population"
    ENVIRONMENT = "Environment"
    PHENOTYPE = "Phenotype"
    GEOMETRY = "Geometry"
    SIGNAL = "Signal"
    STATE = "State"
    PATHWAY = "Pathway"
    REGULATORY_NETWORK = "RegulatoryNetwork"
    DEVELOPMENTAL_PROGRAM = "DevelopmentalProgram"
    GENE = "Gene"
    INTENT = "Intent"
    CONSTRAINT = "Constraint"
    CAPABILITY = "Capability"
    OBSERVATION = "Observation"
    EVIDENCE = "Evidence"
    PREDICTION = "Prediction"
    INTERVENTION = "Intervention"
    TRANSITION = "Transition"
    TRAJECTORY = "Trajectory"
    MORPHOGEN = "Morphogen"
    AXIS = "Axis"
    PATTERN = "Pattern"
    CONSTRUCT = "Construct"
    GENOME = "Genome"
    TRANSCRIPT = "Transcript"


class EvidenceLevel(str, Enum):
    UNKNOWN = "UNKNOWN"
    THEORETICAL = "THEORETICAL"
    COMPUTATIONALLY_SUPPORTED = "COMPUTATIONALLY_SUPPORTED"
    OBSERVED = "OBSERVED"
    EXPERIMENTALLY_DEMONSTRATED = "EXPERIMENTALLY_DEMONSTRATED"
    WIDELY_VALIDATED = "WIDELY_VALIDATED"
    CONTEXT_LIMITED = "CONTEXT_LIMITED"

    @property
    def rank(self) -> int:
        order = {
            "UNKNOWN": 0,
            "THEORETICAL": 1,
            "COMPUTATIONALLY_SUPPORTED": 2,
            "CONTEXT_LIMITED": 2,
            "OBSERVED": 3,
            "EXPERIMENTALLY_DEMONSTRATED": 4,
            "WIDELY_VALIDATED": 5,
        }
        return order[self.value]

    def __lt__(self, other: "EvidenceLevel") -> bool:
        return self.rank < other.rank


@dataclass
class BioState:
    genomic: Dict[str, float] = field(default_factory=dict)
    rna: Dict[str, float] = field(default_factory=dict)
    protein: Dict[str, float] = field(default_factory=dict)
    metabolic: Dict[str, float] = field(default_factory=dict)
    cellular: Dict[str, float] = field(default_factory=dict)
    tissue: Dict[str, float] = field(default_factory=dict)
    conformation: Dict[str, float] = field(default_factory=dict)
    localization: Dict[str, float] = field(default_factory=dict)
    abundance: Dict[str, float] = field(default_factory=dict)
    environment: Dict[str, float] = field(default_factory=dict)
    time: float = 0.0
    context: Dict[str, str] = field(default_factory=dict)


@dataclass
class BackendCapability:
    id: str
    organism_context: str
    substrate: str
    supported_operations: List[str]
    state_variables: List[str]
    constraints: List[str]
    evidence: EvidenceLevel
    uncertainty: float
    dependencies: List[str]

    def supports(self, opcode: str) -> bool:
        return opcode in self.supported_operations

    @staticmethod
    def mammalian_developmental() -> "BackendCapability":
        return BackendCapability(
            id="mammalian_cell.developmental",
            organism_context="mammalian",
            substrate="cellular",
            supported_operations=[
                "RECOGNIZE", "SENSE", "SIGNAL", "REGULATE", "ACTIVATE", "REPRESS",
                "LOCALIZE", "TRAFFIC", "TRANSCRIBE", "TRANSLATE", "MODIFY", "FOLD",
                "DIFFERENTIATE", "DEVELOP", "FEEDBACK", "VERIFY", "COPY",
                "POLYMERIZE", "ASSOCIATE", "DISSOCIATE", "SWITCH", "PROPAGATE",
                "INHERIT",
            ],
            state_variables=["genomic", "rna", "protein", "localization", "tissue", "environment", "time"],
            constraints=["viability", "developmental_consistency"],
            evidence=EvidenceLevel.WIDELY_VALIDATED,
            uncertainty=0.25,
            dependencies=["transcriptional_machinery", "morphogen_transport"],
        )

    @staticmethod
    def e_coli() -> "BackendCapability":
        return BackendCapability(
            id="e_coli.k12",
            organism_context="Escherichia coli K-12",
            substrate="prokaryotic_cell",
            supported_operations=[
                "RECOGNIZE", "TRANSCRIBE", "TRANSLATE", "COPY", "REPRESS", "ACTIVATE",
            ],
            state_variables=["genomic", "rna", "protein"],
            constraints=["viability"],
            evidence=EvidenceLevel.WIDELY_VALIDATED,
            uncertainty=0.3,
            dependencies=["prokaryotic_rnaps"],
        )

    @staticmethod
    def cell_free() -> "BackendCapability":
        return BackendCapability(
            id="cell_free.in_vitro",
            organism_context="cell-free",
            substrate="molecular",
            supported_operations=[
                "RECOGNIZE", "HYBRIDIZE", "ANNEAL", "POLYMERIZE", "CLEAVE", "LIGATE",
                "COPY", "TRANSCRIBE", "TRANSLATE", "DEGRADE",
            ],
            state_variables=["rna", "protein", "metabolic"],
            constraints=[],
            evidence=EvidenceLevel.EXPERIMENTALLY_DEMONSTRATED,
            uncertainty=0.4,
            dependencies=["cell_extract"],
        )


BACKEND_REGISTRY = {
    "mammalian_cell.developmental": BackendCapability.mammalian_developmental,
    "cell_free.in_vitro": BackendCapability.cell_free,
    "e_coli.k12": BackendCapability.e_coli,
}


def resolve_backend(backend_id: str) -> BackendCapability:
    factory = BACKEND_REGISTRY.get(backend_id)
    if factory is None:
        from .errors import UnsupportedError
        raise UnsupportedError([f"unknown backend {backend_id}"], backend_id)
    return factory()


@dataclass
class CapabilityIntersection:
    backend: str
    required: List[str]
    available: List[str]
    missing: List[str]
    sufficient: bool

    @staticmethod
    def resolve(required: List[str], backend: BackendCapability) -> "CapabilityIntersection":
        missing = [op for op in required if not backend.supports(op)]
        return CapabilityIntersection(
            backend=backend.id,
            required=list(required),
            available=list(backend.supported_operations),
            missing=missing,
            sufficient=not missing,
        )
