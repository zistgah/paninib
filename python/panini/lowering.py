from __future__ import annotations

from typing import List, Tuple

from .errors import SemanticError, TypeError_
from .frontend import Program
from .ir import (
    CausalEdge,
    CausalIr,
    CausalNode,
    CiscInstruction,
    GeneticCiscIr,
    GeneticRiscIr,
    LoweringRecord,
    MicroOp,
    MolecularMicrocodeIr,
    PhenotypeIr,
    PhenotypeProperty,
    RiscInstruction,
    UniversalBioIr,
)
from .ontology import get_def
from .types import BioType


ALLOWED_VERBS = {"establish", "reach_state", "maintain", "suppress", "induce"}
ALLOWED_CONSTRAINTS = {
    "viability",
    "developmental_consistency",
    "phenotype_fidelity",
    "off_target_limit",
    "safety",
}


def analyze(program: Program, source: str):
    if not program.organism.strip():
        raise SemanticError("organism name required")
    if not program.intents:
        raise SemanticError("at least one intent is required")
    for intent in program.intents:
        if intent.verb not in ALLOWED_VERBS:
            raise SemanticError(f"unknown intent verb `{intent.verb}`")
        if intent.verb == "establish" and intent.name == "axial_pattern":
            if "primary" not in intent.bindings:
                raise TypeError_("establish axial_pattern requires binding `primary`")
    for c in program.constraints:
        if c not in ALLOWED_CONSTRAINTS:
            raise SemanticError(f"unknown constraint `{c}`")

    bio = UniversalBioIr.from_program(program, source)
    return bio, build_causal(bio), desired_phenotype(bio)


def build_causal(ir: UniversalBioIr) -> CausalIr:
    from .registry import get_registry
    knowledge = get_registry().knowledge_for_organism(ir.organism)
    if knowledge and knowledge.build_causal_fn:
        return knowledge.build_causal_fn(ir)
    nodes = [
        CausalNode("intent", "intent", "; ".join(f"{i.verb} {i.name}" for i in ir.intents)),
        CausalNode("state", "state", "domain-neutral state node"),
    ]
    edges = [
        CausalEdge("intent", "state", "requires", "THEORETICAL"),
    ]
    return CausalIr(ir.program_id, nodes, edges)


def desired_phenotype(ir: UniversalBioIr) -> PhenotypeIr:
    primary = "unspecified"
    secondary = None
    for i in ir.intents:
        if i.name == "axial_pattern":
            primary = i.bindings.get("primary", "unspecified")
            secondary = i.bindings.get("secondary")
    p = PhenotypeIr(ir.program_id)
    p.anatomical.append(PhenotypeProperty(
        "anatomical", "primary_axis_identity", primary, None,
        "anteroposterior_axis", "mature", 0.2, "anatomical_landmark + Hox code",
    ))
    if secondary:
        p.anatomical.append(PhenotypeProperty(
            "anatomical", "secondary_axis_identity", secondary, None,
            "second_axis", "mature", 0.4, "declared secondary axis",
        ))
    tails = sum(1 for v in (primary, secondary) if v == "tail")
    p.anatomical.append(PhenotypeProperty(
        "anatomical", "tail_count", str(tails), None,
        "organism", "mature", 0.3, "inferred from primary/secondary bindings",
    ))
    p.molecular.append(PhenotypeProperty(
        "molecular", "posterior_hox_bias", "high", None,
        "posterior", "mature", 0.25, "expression_domain",
    ))
    p.temporal.append(PhenotypeProperty(
        "temporal", "developmental_stage", "mature", None,
        None, "terminal", 0.15, "stage_series",
    ))
    p.geometric.append(PhenotypeProperty(
        "geometric", "axis_polarity", "posterior_enriched", None,
        "1d_axis", "mature", 0.2, "spatial_profile",
    ))
    return p


def intent_to_cisc(bio: UniversalBioIr) -> GeneticCiscIr:
    instructions: List[CiscInstruction] = []
    n = 0

    def push(opcode: str, intent: str, operands: List[str]):
        nonlocal n
        defn = get_def(opcode)
        if defn is None:
            raise SemanticError(f"missing CISC definition for {opcode}")
        n += 1
        instructions.append(CiscInstruction.from_def(f"CISC#{n:02d}", defn, intent, operands))

    for intent in bio.intents:
        tag = f"{intent.verb}:{intent.name}"
        if intent.verb == "establish" and intent.name == "axial_pattern":
            primary = intent.bindings.get("primary", "axis")
            secondary = intent.bindings.get("secondary")
            push("SENSE", tag, ["morphogen_field", primary])
            if primary == "head":
                push("PROPAGATE", tag, ["ra", "anterior"])
                push("REGULATE", tag, ["anterior_network"])
                push("ACTIVATE", tag, ["anterior_program"])
                push("REPRESS", tag, ["posterior_program"])
                push("LOCALIZE", tag, ["anterior_determinants", primary])
                push("DIFFERENTIATE", tag, ["anterior_progenitors"])
                push("DEVELOP", tag, ["head_identity"])
            else:
                push("PROPAGATE", tag, ["wnt_fgf", "posterior"])
                push("REGULATE", tag, ["cdx_hox_network"])
                push("ACTIVATE", tag, ["posterior_program"])
                push("REPRESS", tag, ["anterior_program"])
                push("LOCALIZE", tag, ["caudal_determinants", primary])
                push("DIFFERENTIATE", tag, ["axial_progenitors"])
                push("DEVELOP", tag, ["caudal_extension"])
                if secondary == "tail":
                    push("FEEDBACK", tag, ["second_axis_not_in_1d_model"])
                else:
                    push("FEEDBACK", tag, ["hox_auto_maintenance"])
        elif intent.verb == "reach_state":
            push("DEVELOP", tag, [intent.name])
            push("VERIFY", tag, [intent.name, "state_target"])
        else:
            push("REGULATE", tag, [f"{intent.verb}:{intent.name}"])

    if any(c.name == "phenotype_fidelity" for c in bio.constraints):
        push("VERIFY", "constraint:phenotype_fidelity", ["phenotype"])

    return GeneticCiscIr(bio.program_id, instructions)


def cisc_to_risc(cisc: GeneticCiscIr) -> GeneticRiscIr:
    instructions: List[RiscInstruction] = []
    lowering_map: List[LoweringRecord] = []
    n = 0

    def emit(opcode: str, operands: List[str], src: CiscInstruction) -> str:
        nonlocal n
        n += 1
        rid = f"RISC#{n:02d}"
        instructions.append(RiscInstruction(
            rid, opcode, operands, list(src.operand_types), src.id, src.source_intent
        ))
        return rid

    rules = {
        "REPLACE": ("REPLACE → CLEAVE; ERASE; POLYMERIZE; LIGATE; COMMIT",
                    lambda s: [emit("CLEAVE", s.operands, s), emit("WRITE_STATE", ["erase_region"], s),
                               emit("POLYMERIZE", s.operands, s), emit("LIGATE", s.operands, s), emit("COMMIT", [], s)]),
        "AMPLIFY": ("AMPLIFY → COPY + CONTROL/ITERATION",
                    lambda s: [emit("COPY", s.operands, s), emit("BRANCH", ["iterate"], s), emit("COMMIT", [], s)]),
        "REGULATE": ("REGULATE → READ; COMPARE; BIND; WRITE",
                     lambda s: [emit("READ_STATE", ["regulatory_input"], s), emit("COMPARE", ["threshold"], s),
                                emit("BIND", s.operands, s), emit("WRITE_STATE", ["network_output"], s)]),
        "DEVELOP": ("DEVELOP → SIGNAL; WRITE; ITERATE; COMMIT",
                    lambda s: [emit("EMIT_SIGNAL", ["program_clock"], s), emit("WRITE_STATE", ["progress"], s),
                               emit("BRANCH", ["continue_until_mature"], s), emit("COMMIT", [], s)]),
        "DIFFERENTIATE": ("DIFFERENTIATE → READ; WRITE identity; COMMIT",
                          lambda s: [emit("READ_STATE", ["progenitor"], s), emit("WRITE_STATE", ["identity"], s),
                                     emit("COMMIT", [], s)]),
        "SENSE": ("SENSE → BIND; READ occupancy",
                  lambda s: [emit("BIND", s.operands, s), emit("READ_STATE", ["occupancy"], s)]),
        "SIGNAL": ("SIGNAL/PROPAGATE → EMIT; TRANSPORT",
                   lambda s: [emit("EMIT_SIGNAL", s.operands, s), emit("TRANSPORT", s.operands, s)]),
        "PROPAGATE": ("SIGNAL/PROPAGATE → EMIT; TRANSPORT",
                      lambda s: [emit("EMIT_SIGNAL", s.operands, s), emit("TRANSPORT", s.operands, s)]),
        "LOCALIZE": ("LOCALIZE → TRANSPORT", lambda s: [emit("TRANSPORT", s.operands, s)]),
        "ACTIVATE": ("ACTIVATE → BIND; TRANSCRIBE",
                     lambda s: [emit("BIND", s.operands, s), emit("TRANSCRIBE", s.operands, s)]),
        "REPRESS": ("REPRESS → BIND; WRITE repressed",
                    lambda s: [emit("BIND", s.operands, s), emit("WRITE_STATE", ["repressed"], s)]),
        "FEEDBACK": ("FEEDBACK → READ output; BIND upstream; WRITE gain",
                     lambda s: [emit("READ_STATE", ["output"], s), emit("BIND", ["upstream"], s),
                                emit("WRITE_STATE", ["gain"], s)]),
        "VERIFY": ("VERIFY → READ; COMPARE; COMMIT",
                   lambda s: [emit("READ_STATE", s.operands, s), emit("COMPARE", ["constraint"], s),
                              emit("COMMIT", [], s)]),
        "TRANSCRIBE": ("TRANSCRIBE → TRANSCRIBE", lambda s: [emit("TRANSCRIBE", s.operands, s)]),
        "TRANSLATE": ("TRANSLATE → TRANSLATE", lambda s: [emit("TRANSLATE", s.operands, s)]),
    }

    for ins in cisc.instructions:
        if ins.opcode in rules:
            rule, fn = rules[ins.opcode]
            ids = fn(ins)
        else:
            rule = "generic CISC → READ; WRITE"
            ids = [emit("READ_STATE", ins.operands, ins), emit("WRITE_STATE", [ins.opcode], ins)]
        lowering_map.append(LoweringRecord(f"{ins.id} ({ins.opcode})", ids, rule))

    return GeneticRiscIr(cisc.program_id, instructions, lowering_map)


_MECH = {
    "BIND": ("protein_nucleic_or_ligand_association", "complex_occupancy += k_on * free_ligand"),
    "UNBIND": ("complex_dissociation", "complex_occupancy -= k_off * bound"),
    "READ_STATE": ("sensor_or_checkpoint_read", "observer <- S[addr]"),
    "WRITE_STATE": ("chromatin_or_protein_state_write", "S[addr] <- value"),
    "TRANSCRIBE": ("rna_polymerase_elongation", "RNA += pol_rate * promoter_on"),
    "TRANSLATE": ("ribosome_elongation", "Protein += ribosome_rate * mRNA"),
    "POLYMERIZE": ("template_directed_polymerization", "polymer_length += 1"),
    "CLEAVE": ("endonuclease_cut", "polymer -> fragment_a + fragment_b"),
    "LIGATE": ("ligase_seal", "fragment_a + fragment_b -> polymer"),
    "TRANSPORT": ("directed_or_diffusive_transport", "loc(x) <- loc(x) + flux"),
    "EMIT_SIGNAL": ("ligand_release_or_contact", "field += secretion"),
    "COMPARE": ("threshold_or_proofreading_gate", "flag <- (value ? setpoint)"),
    "BRANCH": ("program_continuation_gate", "if flag then continue"),
    "MODIFY_RESIDUE": ("covalent_modification", "mod_state <- on"),
    "COMMIT": ("irreversible_lock_or_checkpoint", "committed <- true"),
    "COPY": ("replicative_polymerization", "copy <- template"),
}


def risc_to_microcode(risc: GeneticRiscIr, backend: str, organism: str) -> MolecularMicrocodeIr:
    machinery = {
        "mammalian_cell.developmental": "mammalian_nucleus_and_cytoplasm",
        "mammalian": "mammalian_nucleus_and_cytoplasm",
        "cell_free.in_vitro": "cell_extract",
        "cell_free": "cell_extract",
    }.get(backend, backend)
    ops = []
    for r in risc.instructions:
        mechanism, transition = _MECH.get(r.opcode, ("unspecified_molecular_step", r.opcode))
        ops.append(MicroOp(
            id=f"MU-{r.id}",
            mechanism=mechanism,
            machinery=machinery,
            substrate="mammalian_chromatin_rna_protein",
            source_risc=r.id,
            state_transition=transition,
            notes=f"lowered from {r.source_cisc} / {r.source_intent}",
        ))
    return MolecularMicrocodeIr(risc.program_id, backend, organism, ops)
