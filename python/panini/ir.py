from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Dict, List, Optional

from .frontend import Program
from .ontology import CiscDef
from .types import BioType, EvidenceLevel


def to_plain(obj: Any) -> Any:
    if is_dataclass(obj):
        return {k: to_plain(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_plain(v) for v in obj]
    if isinstance(obj, EnumWrap := type(obj)) and hasattr(obj, "value"):
        try:
            return obj.value  # type: ignore
        except Exception:
            return str(obj)
    return obj


def ir_hash(value: Any) -> str:
    payload = json.dumps(to_plain(value), sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()


def text_hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


@dataclass
class TypedIntent:
    verb: str
    name: str
    intent_type: BioType
    operand_types: Dict[str, BioType]
    bindings: Dict[str, str]


@dataclass
class TypedConstraint:
    name: str
    constraint_type: BioType


@dataclass
class UniversalBioIr:
    program_id: str
    organism: str
    organism_type: BioType
    intents: List[TypedIntent]
    constraints: List[TypedConstraint]
    verification_targets: List[str]
    source_hash: str

    @staticmethod
    def from_program(program: Program, source: str) -> "UniversalBioIr":
        intents = []
        for i in program.intents:
            itype = {
                "axial_pattern": BioType.PATTERN,
                "mature": BioType.STATE,
            }.get(i.name, BioType.INTENT)
            otypes = {
                k: BioType.AXIS if k in ("primary", "secondary") else BioType.INFORMATION
                for k, v in i.bindings.items()
            }
            intents.append(TypedIntent(i.verb, i.name, itype, otypes, dict(i.bindings)))
        ir = UniversalBioIr(
            program_id="",
            organism=program.organism,
            organism_type=BioType.ORGANISM,
            intents=intents,
            constraints=[TypedConstraint(c, BioType.CONSTRAINT) for c in program.constraints],
            verification_targets=list(program.verify),
            source_hash=text_hash(source),
        )
        ir.program_id = "prog_" + ir_hash(ir)[:12]
        return ir


@dataclass
class CiscInstruction:
    id: str
    opcode: str
    operands: List[str]
    operand_types: List[BioType]
    input_types: List[BioType]
    output_types: List[BioType]
    preconditions: List[str]
    postconditions: List[str]
    required_capabilities: List[str]
    state_reads: List[str]
    state_writes: List[str]
    evidence_level: EvidenceLevel
    provenance: List[str]
    reversibility: bool
    stochasticity: float
    state_effect: str
    source_intent: str

    @staticmethod
    def from_def(id: str, defn: CiscDef, source_intent: str, operands: List[str]) -> "CiscInstruction":
        return CiscInstruction(
            id=id,
            opcode=defn.opcode,
            operands=operands,
            operand_types=list(defn.input_types),
            input_types=list(defn.input_types),
            output_types=list(defn.output_types),
            preconditions=list(defn.preconditions),
            postconditions=list(defn.postconditions),
            required_capabilities=list(defn.required_capabilities),
            state_reads=list(defn.state_reads),
            state_writes=list(defn.state_writes),
            evidence_level=defn.evidence_level,
            provenance=[f"cisc_def:{defn.opcode}"],
            reversibility=defn.reversibility,
            stochasticity=defn.stochasticity,
            state_effect=defn.semantic_definition,
            source_intent=source_intent,
        )


@dataclass
class GeneticCiscIr:
    program_id: str
    instructions: List[CiscInstruction]


@dataclass
class RiscInstruction:
    id: str
    opcode: str
    operands: List[str]
    operand_types: List[BioType]
    source_cisc: str
    source_intent: str


@dataclass
class LoweringRecord:
    source_instruction: str
    lowered_to: List[str]
    rule: str
    approximation: Optional[str] = None


@dataclass
class GeneticRiscIr:
    program_id: str
    instructions: List[RiscInstruction]
    lowering_map: List[LoweringRecord]


@dataclass
class MicroOp:
    id: str
    mechanism: str
    machinery: str
    substrate: str
    source_risc: str
    state_transition: str
    notes: str


@dataclass
class MolecularMicrocodeIr:
    program_id: str
    backend: str
    organism_context: str
    ops: List[MicroOp]


@dataclass
class PhenotypeProperty:
    layer: str
    name: str
    value: str
    units: Optional[str]
    spatial_reference: Optional[str]
    temporal_reference: Optional[str]
    uncertainty: float
    measurement_method: str


@dataclass
class PhenotypeIr:
    program_id: str
    molecular: List[PhenotypeProperty] = field(default_factory=list)
    cellular: List[PhenotypeProperty] = field(default_factory=list)
    tissue: List[PhenotypeProperty] = field(default_factory=list)
    anatomical: List[PhenotypeProperty] = field(default_factory=list)
    physiological: List[PhenotypeProperty] = field(default_factory=list)
    behavioral: List[PhenotypeProperty] = field(default_factory=list)
    temporal: List[PhenotypeProperty] = field(default_factory=list)
    geometric: List[PhenotypeProperty] = field(default_factory=list)


@dataclass
class Point:
    x: float
    y: float
    z: float
    label: str
    state: str
    time: float
    confidence: float


@dataclass
class GeometryIr:
    kind: str
    topology: str
    points: List[Point]
    annotations: List[str]


@dataclass
class CausalNode:
    id: str
    kind: str
    label: str


@dataclass
class CausalEdge:
    frm: str
    to: str
    relation: str
    evidence: str


@dataclass
class CausalIr:
    program_id: str
    nodes: List[CausalNode]
    edges: List[CausalEdge]


@dataclass
class SimulationProgram:
    program_id: str
    entities: List[str]
    state_variables: List[str]
    equations: List[str]
    transition_rules: List[str]
    spatial_model: str
    temporal_model: str
    stochastic_model: str
    parameters: Dict[str, float]
    observations: List[str]
    model_kind: str
    resolution: str


@dataclass
class TrajectoryPoint:
    time: float
    axis_position: float
    wnt: float
    fgf: float
    ra: float
    cdx: float
    hox_posterior: float
    tail_identity: float


@dataclass
class SimulationResult:
    program_id: str
    trajectory: List[TrajectoryPoint]
    terminal_phenotype_score: float
    matured: bool
    notes: List[str]


@dataclass
class VerificationItem:
    level: str
    name: str
    passed: bool
    detail: str


@dataclass
class VerificationReport:
    program_id: str
    passed: List[VerificationItem]
    failed: List[VerificationItem]
    warnings: List[str]
    assumptions: List[str]
    uncertainties: List[str]
    evidence: List[List[str]]
    provenance: List[str]
    overall_pass: bool
    internal_validity_pass: bool = False


@dataclass
class ConstructSpec:
    artifact_id: str
    role: str
    organism: str
    kind: str
    sequence_ref: str
    topology: str
    annotations: List[str]
    evidence: str
    sequence: Optional[str]
    chrom: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None
    strand: Optional[str] = None
    assembly: Optional[str] = None
    retrieval_digest: Optional[str] = None
    drives: Optional[str] = None
    artifact_class: str = "REFERENCE_LOCUS"


@dataclass
class Authorization:
    authorized: bool = False
    person: Optional[str] = None
    facility: Optional[str] = None
    approval_reference: Optional[str] = None
    scope: str = "specification_only"


@dataclass
class RealizationPackage:
    program_id: str
    backend: str
    construct_specification: List[ConstructSpec]
    required_capabilities: List[str]
    qc_requirements: List[str]
    verification_plan: List[str]
    provenance: List[str]
    safety_constraints: List[str]
    note: str
    authorization: Optional[Authorization] = None
    assembly_plan: Optional[dict] = None
    sequence_verification_plan: Optional[dict] = None
    instrument_bindings: Optional[list] = None
    designed_constructs: Optional[list] = None


@dataclass
class PassRecord:
    pass_name: str
    input_hash: str
    output_hash: str
    compiler_version: str
    transformations: List[str]
    assumptions: List[str]
    approximation: Optional[str]


@dataclass
class ProvNode:
    id: str
    kind: str
    label: str


@dataclass
class ProvEdge:
    frm: str
    to: str
    relation: str


@dataclass
class ProvenanceGraph:
    nodes: List[ProvNode] = field(default_factory=list)
    edges: List[ProvEdge] = field(default_factory=list)

    def add_node(self, id: str, kind: str, label: str):
        if any(n.id == id for n in self.nodes):
            return
        self.nodes.append(ProvNode(id, kind, label))

    def add_edge(self, frm: str, to: str, relation: str):
        self.edges.append(ProvEdge(frm, to, relation))
