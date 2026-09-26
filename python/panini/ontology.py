from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .types import BioType, EvidenceLevel

# Comprehensive Genetic CISC is defined in cisc_catalog.
# The 16-op set below is the *candidate Genetic RISC*, not the CISC.
# Imported CISC_OPCODES is overwritten after catalog load to avoid a cycle.
CISC_OPCODES = []  # filled by cisc_catalog.catalog keys at import of get_def

RISC_OPCODES = [
    "BIND", "UNBIND", "READ_STATE", "WRITE_STATE", "POLYMERIZE",
    "CLEAVE", "LIGATE", "TRANSCRIBE", "TRANSLATE", "MODIFY_RESIDUE",
    "TRANSPORT", "COMPARE", "BRANCH", "EMIT_SIGNAL", "COMMIT", "COPY",
]


@dataclass
class CiscDef:
    opcode: str
    semantic_definition: str
    input_types: List[BioType]
    output_types: List[BioType]
    required_capabilities: List[str]
    state_reads: List[str]
    state_writes: List[str]
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    possible_side_effects: List[str] = field(default_factory=list)
    stochasticity: float = 0.2
    reversibility: bool = False
    context_dependencies: List[str] = field(default_factory=list)
    known_realizations: List[str] = field(default_factory=list)
    evidence_level: EvidenceLevel = EvidenceLevel.THEORETICAL
    source_references: List[str] = field(default_factory=list)
    version: str = "0.1.0"


def _d(op, sem, inputs, outputs, caps, reads, writes, ev, realizations, stoch, rev) -> CiscDef:
    return CiscDef(
        opcode=op,
        semantic_definition=sem,
        input_types=inputs,
        output_types=outputs,
        required_capabilities=caps,
        state_reads=reads,
        state_writes=writes,
        preconditions=["typed_operands"],
        postconditions=["state_consistent"],
        possible_side_effects=["off_target_context"],
        stochasticity=stoch,
        reversibility=rev,
        context_dependencies=["organism", "cell_type"],
        known_realizations=realizations,
        evidence_level=ev,
        source_references=["PANINI CISC ontology v0.1"],
    )


_RICH = [
    _d("SENSE", "Detect a signal or morphogen in context.",
       [BioType.SIGNAL, BioType.CELL], [BioType.STATE], ["SENSE"],
       ["environment", "localization"], ["cellular"],
       EvidenceLevel.WIDELY_VALIDATED, ["receptor occupancy"], 0.15, True),
    _d("SIGNAL", "Emit or relay a signal.",
       [BioType.CELL, BioType.MOLECULE], [BioType.SIGNAL], ["SIGNAL"],
       ["protein"], ["environment"],
       EvidenceLevel.WIDELY_VALIDATED, ["ligand secretion"], 0.2, True),
    _d("REGULATE", "Change activity of a regulatory network.",
       [BioType.REGULATORY_NETWORK, BioType.SIGNAL], [BioType.REGULATORY_NETWORK], ["REGULATE"],
       ["rna", "protein"], ["rna", "protein"],
       EvidenceLevel.WIDELY_VALIDATED, ["TF occupancy"], 0.25, True),
    _d("ACTIVATE", "Increase activity of a target module.",
       [BioType.GENE, BioType.SIGNAL], [BioType.STATE], ["ACTIVATE"],
       ["genomic"], ["rna"],
       EvidenceLevel.WIDELY_VALIDATED, ["enhancer activation"], 0.2, True),
    _d("REPRESS", "Decrease activity of a target module.",
       [BioType.GENE, BioType.SIGNAL], [BioType.STATE], ["REPRESS"],
       ["genomic"], ["rna"],
       EvidenceLevel.WIDELY_VALIDATED, ["repressor binding"], 0.2, True),
    _d("LOCALIZE", "Place a molecule or state at a spatial address.",
       [BioType.MOLECULE, BioType.GEOMETRY], [BioType.STATE], ["LOCALIZE"],
       ["localization"], ["localization"],
       EvidenceLevel.EXPERIMENTALLY_DEMONSTRATED, ["directed transport"], 0.3, True),
    _d("DIFFERENTIATE", "Commit a cell toward a typed identity.",
       [BioType.CELL, BioType.DEVELOPMENTAL_PROGRAM], [BioType.CELL_TYPE], ["DIFFERENTIATE"],
       ["cellular", "rna"], ["cellular"],
       EvidenceLevel.WIDELY_VALIDATED, ["lineage commitment"], 0.35, False),
    _d("DEVELOP", "Execute a multi-step developmental program.",
       [BioType.DEVELOPMENTAL_PROGRAM, BioType.ORGANISM], [BioType.PHENOTYPE], ["DEVELOP"],
       ["tissue", "time"], ["tissue"],
       EvidenceLevel.WIDELY_VALIDATED, ["axis elongation"], 0.4, False),
    _d("FEEDBACK", "Couple output state onto an upstream regulator.",
       [BioType.STATE, BioType.REGULATORY_NETWORK], [BioType.REGULATORY_NETWORK], ["FEEDBACK"],
       ["protein"], ["rna"],
       EvidenceLevel.EXPERIMENTALLY_DEMONSTRATED, ["negative-feedback loop"], 0.25, True),
    _d("VERIFY", "Check predicted state against a constraint.",
       [BioType.STATE, BioType.CONSTRAINT], [BioType.OBSERVATION], ["VERIFY"],
       ["state"], [],
       EvidenceLevel.COMPUTATIONALLY_SUPPORTED, ["in-silico assay"], 0.1, True),
    _d("TRANSCRIBE", "Polymerize RNA from a DNA template.",
       [BioType.DNA], [BioType.RNA], ["TRANSCRIBE"],
       ["genomic"], ["rna"],
       EvidenceLevel.WIDELY_VALIDATED, ["RNAP II"], 0.1, False),
    _d("TRANSLATE", "Polymerize polypeptide from mRNA.",
       [BioType.RNA], [BioType.PROTEIN], ["TRANSLATE"],
       ["rna"], ["protein"],
       EvidenceLevel.WIDELY_VALIDATED, ["ribosome"], 0.1, False),
    _d("COPY", "Duplicate an information polymer.",
       [BioType.SEQUENCE], [BioType.SEQUENCE], ["COPY"],
       ["genomic"], ["genomic"],
       EvidenceLevel.WIDELY_VALIDATED, ["DNA polymerase"], 0.05, False),
    _d("REPLACE", "Substitute a region of a polymer.",
       [BioType.SEQUENCE, BioType.SEQUENCE], [BioType.SEQUENCE], ["REPLACE"],
       ["genomic"], ["genomic"],
       EvidenceLevel.EXPERIMENTALLY_DEMONSTRATED, ["HDR"], 0.4, False),
    _d("PROPAGATE", "Transmit a state or signal along an axis.",
       [BioType.SIGNAL, BioType.AXIS], [BioType.TRAJECTORY], ["PROPAGATE"],
       ["environment"], ["environment", "localization"],
       EvidenceLevel.EXPERIMENTALLY_DEMONSTRATED, ["morphogen transport"], 0.3, True),
    _d("RECOGNIZE", "Bind a target under a recognition mode.",
       [BioType.MOLECULE, BioType.SEQUENCE], [BioType.COMPLEX], ["RECOGNIZE"],
       ["protein"], ["complex"],
       EvidenceLevel.WIDELY_VALIDATED, ["TF-DNA binding"], 0.2, True),
]


def catalog() -> Dict[str, CiscDef]:
    from .cisc_catalog import catalog as full
    return full()


def get_def(opcode: str) -> Optional[CiscDef]:
    return catalog().get(opcode)


# Public CISC vocabulary is the comprehensive catalog.
CISC_OPCODES = list(catalog())
