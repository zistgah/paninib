# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Machine-readable Genetic CISC semantics and CISC→RISC lowering contract.

The 77-op catalogue remains the working CISC. The 16-op RISC is a
candidate primitive basis — no minimality claim is made.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .ontology import RISC_OPCODES, catalog
from .version import ISA_VERSION, LOWERING_VERSION, SEMANTIC_VERSION


IMPLEMENTATION_STATUS = (
    "SPECIFIED",
    "LOWERABLE",
    "EXECUTABLE",
    "MODEL_DEPENDENT",
    "UNIMPLEMENTED",
    "UNKNOWN",
)

LOWERING_STATUS = (
    "AVAILABLE",
    "UNAVAILABLE",
    "MODEL_DEPENDENT",
)

EXECUTION_STATE_DOMAINS = (
    "sequence_state",
    "chemical_state",
    "topological_state",
    "structural_state",
    "occupancy_state",
    "copy_number_state",
    "localization_state",
    "expression_state",
    "epigenetic_state",
    "temporal_state",
    "context_state",
)

# Existing compiler lowering algebra (see lowering.cisc_to_risc). These are
# the only CISC ops with an explicit, currently consumed RISC rewrite.
_EXISTING_LOWERING = {
    "REPLACE": ("REPLACE → CLEAVE; WRITE_STATE; POLYMERIZE; LIGATE; COMMIT",
                ["CLEAVE", "WRITE_STATE", "POLYMERIZE", "LIGATE", "COMMIT"]),
    "AMPLIFY": ("AMPLIFY → COPY; BRANCH; COMMIT",
                ["COPY", "BRANCH", "COMMIT"]),
    "REGULATE": ("REGULATE → READ_STATE; COMPARE; BIND; WRITE_STATE",
                 ["READ_STATE", "COMPARE", "BIND", "WRITE_STATE"]),
    "DEVELOP": ("DEVELOP → EMIT_SIGNAL; WRITE_STATE; BRANCH; COMMIT",
                ["EMIT_SIGNAL", "WRITE_STATE", "BRANCH", "COMMIT"]),
    "DIFFERENTIATE": ("DIFFERENTIATE → READ_STATE; WRITE_STATE; COMMIT",
                      ["READ_STATE", "WRITE_STATE", "COMMIT"]),
    "SENSE": ("SENSE → BIND; READ_STATE", ["BIND", "READ_STATE"]),
    "SIGNAL": ("SIGNAL → EMIT_SIGNAL; TRANSPORT", ["EMIT_SIGNAL", "TRANSPORT"]),
    "PROPAGATE": ("PROPAGATE → EMIT_SIGNAL; TRANSPORT", ["EMIT_SIGNAL", "TRANSPORT"]),
    "LOCALIZE": ("LOCALIZE → TRANSPORT", ["TRANSPORT"]),
    "ACTIVATE": ("ACTIVATE → BIND; TRANSCRIBE", ["BIND", "TRANSCRIBE"]),
    "REPRESS": ("REPRESS → BIND; WRITE_STATE", ["BIND", "WRITE_STATE"]),
    "FEEDBACK": ("FEEDBACK → READ_STATE; BIND; WRITE_STATE",
                 ["READ_STATE", "BIND", "WRITE_STATE"]),
    "VERIFY": ("VERIFY → READ_STATE; COMPARE; COMMIT",
               ["READ_STATE", "COMPARE", "COMMIT"]),
    "TRANSCRIBE": ("TRANSCRIBE → TRANSCRIBE", ["TRANSCRIBE"]),
    "TRANSLATE": ("TRANSLATE → TRANSLATE", ["TRANSLATE"]),
    "COPY": ("COPY → COPY", ["COPY"]),
    "INSERT": ("INSERT → CLEAVE; POLYMERIZE; LIGATE; COMMIT",
               ["CLEAVE", "POLYMERIZE", "LIGATE", "COMMIT"]),
    "DELETE": ("DELETE → CLEAVE; WRITE_STATE; LIGATE; COMMIT",
               ["CLEAVE", "WRITE_STATE", "LIGATE", "COMMIT"]),
    "EDIT": ("EDIT → CLEAVE; POLYMERIZE; LIGATE; COMMIT",
             ["CLEAVE", "POLYMERIZE", "LIGATE", "COMMIT"]),
}

# CISC ops that may become literal sequence edits when operands are explicit.
SEQUENCE_REALIZABLE = {"REPLACE", "INSERT", "DELETE", "EDIT", "MUTATE", "SUBSTITUTE"}

# Category heuristic from opcode families.
_CATEGORIES = {
    "RECOGNIZE": "recognition", "IDENTIFY": "recognition", "ADDRESS": "addressing",
    "BIND": "association", "ASSOCIATE": "association", "RECRUIT": "association",
    "RELEASE": "association", "DISSOCIATE": "association",
    "COPY": "polymerization", "TRANSCRIBE": "polymerization", "TRANSLATE": "polymerization",
    "POLYMERIZE": "polymerization", "AMPLIFY": "polymerization",
    "CLEAVE": "cleavage", "LIGATE": "ligation", "RESTRICT": "cleavage",
    "INSERT": "sequence_edit", "DELETE": "sequence_edit", "REPLACE": "sequence_edit",
    "EDIT": "sequence_edit", "MUTATE": "sequence_edit", "ERASE": "sequence_edit",
    "REARRANGE": "rearrangement", "RECOMBINE": "rearrangement", "INVERT": "rearrangement",
    "TRANSLOCATE": "rearrangement", "DUPLICATE": "rearrangement",
    "TRANSPOSITION": "rearrangement", "GENE_CONVERSION": "rearrangement",
    "INTEGRATE": "rearrangement", "EXCISE": "rearrangement",
    "SENSE": "signaling", "SIGNAL": "signaling", "PROPAGATE": "signaling",
    "COMMUNICATE": "signaling",
    "ACTIVATE": "regulation", "REPRESS": "regulation", "REGULATE": "regulation",
    "FEEDBACK": "regulation", "SWITCH": "regulation", "RNAi": "regulation",
    "CRISPR_INTERFERE": "regulation",
    "DIFFERENTIATE": "development", "DEVELOP": "development",
    "AXIS_INITIATE": "development", "TERMINATE": "development",
    "LOCALIZE": "localization", "TRANSFER": "localization",
    "VERIFY": "checkpoint", "PROOFREAD": "checkpoint", "REJECT": "checkpoint",
}


@dataclass
class GeneticState:
    """Canonical abstract genetic execution state."""

    sequence_state: Dict[str, Any] = field(default_factory=dict)
    chemical_state: Dict[str, Any] = field(default_factory=dict)
    topological_state: Dict[str, Any] = field(default_factory=dict)
    structural_state: Dict[str, Any] = field(default_factory=dict)
    occupancy_state: Dict[str, Any] = field(default_factory=dict)
    copy_number_state: Dict[str, Any] = field(default_factory=dict)
    localization_state: Dict[str, Any] = field(default_factory=dict)
    expression_state: Dict[str, Any] = field(default_factory=dict)
    epigenetic_state: Dict[str, Any] = field(default_factory=dict)
    temporal_state: Dict[str, Any] = field(default_factory=dict)
    context_state: Dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LoweringSpec:
    cisc_opcode: str
    lowering_status: str
    risc_sequence: List[str]
    rule: str
    side_conditions: List[str]
    required_capabilities: List[str]
    model_dependencies: List[str]
    evidence_requirements: List[str]
    sequence_realizable: bool = False


@dataclass
class CiscSemanticSpec:
    opcode_id: str
    name: str
    category: str
    description: str
    operand_types: List[str]
    preconditions: List[str]
    postconditions: List[str]
    transition: str
    state_effects: List[str]
    affected_domains: List[str]
    mechanism_class: str
    risc_lowering: LoweringSpec
    microcode_class: str
    evidence_requirements: List[str]
    implementation_status: str
    isa_version: str = ISA_VERSION
    semantic_version: str = SEMANTIC_VERSION
    lowering_version: str = LOWERING_VERSION
    compatibility_version: str = ISA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


def _domains_for(defn) -> List[str]:
    mapping = {
        "genomic": "sequence_state",
        "rna": "expression_state",
        "protein": "chemical_state",
        "complex": "occupancy_state",
        "localization": "localization_state",
        "cellular": "context_state",
        "tissue": "context_state",
        "time": "temporal_state",
        "environment": "context_state",
        "conformation": "structural_state",
        "metabolic": "chemical_state",
        "state": "context_state",
    }
    out = []
    for item in list(defn.state_reads) + list(defn.state_writes):
        mapped = mapping.get(item)
        if mapped and mapped not in out:
            out.append(mapped)
    if not out:
        out = ["context_state"]
    return out


def _status_for(opcode: str) -> str:
    if opcode in _EXISTING_LOWERING:
        if opcode in SEQUENCE_REALIZABLE:
            return "EXECUTABLE"
        return "LOWERABLE"
    if opcode in {"INVERT", "DUPLICATE", "MOVE", "REARRANGE", "TRANSLOCATE"}:
        return "SPECIFIED"
    if opcode in {"DEVELOP", "DIFFERENTIATE", "AXIS_INITIATE"}:
        return "MODEL_DEPENDENT"
    return "SPECIFIED"


def spec_for(opcode: str) -> Optional[CiscSemanticSpec]:
    defn = catalog().get(opcode)
    if defn is None:
        return None
    rule, risc = _EXISTING_LOWERING.get(opcode, ("", []))
    if risc:
        lowering = LoweringSpec(
            cisc_opcode=opcode,
            lowering_status="AVAILABLE",
            risc_sequence=risc,
            rule=rule,
            side_conditions=["typed_operands", "capability_intersection"],
            required_capabilities=list(defn.required_capabilities),
            model_dependencies=[],
            evidence_requirements=[defn.evidence_level.value if hasattr(defn.evidence_level, "value") else str(defn.evidence_level)],
            sequence_realizable=opcode in SEQUENCE_REALIZABLE,
        )
    else:
        lowering = LoweringSpec(
            cisc_opcode=opcode,
            lowering_status="UNAVAILABLE",
            risc_sequence=[],
            rule="no scientifically defensible RISC lowering recorded",
            side_conditions=["do_not_invent_lowering"],
            required_capabilities=list(defn.required_capabilities),
            model_dependencies=["domain_plugin"] if opcode in {"DEVELOP", "DIFFERENTIATE", "AXIS_INITIATE"} else [],
            evidence_requirements=["explicit evidence before sequence realization"],
            sequence_realizable=False,
        )
    ev = defn.evidence_level.value if hasattr(defn.evidence_level, "value") else str(defn.evidence_level)
    return CiscSemanticSpec(
        opcode_id=opcode,
        name=opcode,
        category=_CATEGORIES.get(opcode, "general"),
        description=defn.semantic_definition,
        operand_types=[t.value if hasattr(t, "value") else str(t) for t in defn.input_types],
        preconditions=list(defn.preconditions) or ["typed_operands"],
        postconditions=list(defn.postconditions) or ["state_consistent"],
        transition=f"S --{opcode}(operands)--> S'",
        state_effects=[defn.semantic_definition],
        affected_domains=_domains_for(defn),
        mechanism_class=(defn.known_realizations[0] if defn.known_realizations else "unspecified"),
        risc_lowering=lowering,
        microcode_class="molecular_step" if lowering.lowering_status == "AVAILABLE" else "unspecified",
        evidence_requirements=[ev],
        implementation_status=_status_for(opcode),
    )


def all_specs() -> Dict[str, CiscSemanticSpec]:
    return {op: spec_for(op) for op in catalog()}


def lowering_for(opcode: str) -> LoweringSpec:
    spec = spec_for(opcode)
    if spec is None:
        return LoweringSpec(
            cisc_opcode=opcode,
            lowering_status="UNAVAILABLE",
            risc_sequence=[],
            rule="unknown opcode",
            side_conditions=[],
            required_capabilities=[],
            model_dependencies=[],
            evidence_requirements=[],
        )
    return spec.risc_lowering


def isa_manifest() -> Dict[str, Any]:
    specs = all_specs()
    return {
        "isa_version": ISA_VERSION,
        "semantic_version": SEMANTIC_VERSION,
        "lowering_version": LOWERING_VERSION,
        "compatibility_version": ISA_VERSION,
        "cisc_count": len(specs),
        "risc_candidate_basis": list(RISC_OPCODES),
        "risc_minimality_claim": False,
        "sequence_realizable": sorted(SEQUENCE_REALIZABLE),
        "execution_state_domains": list(EXECUTION_STATE_DOMAINS),
        "opcodes": {k: v.to_dict() for k, v in specs.items()},
    }
