# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Designed-genotype compiler MVP.

Compiles an explicit sequence transformation through:

  source → semantic IR → CISC → RISC → GenotypeDesign
        → Sequence IR → reference backend → derived ATGC → verification

Does not invent a nucleotide sequence for an unresolved phenotype.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .isa_spec import lowering_for
from .knowledge import get_knowledge_registry
from .reference_backend import MemoryReferenceBackend, default_backend
from .sequence_ir import (
    DerivedSequence,
    SequenceEdit,
    SequenceIR,
    SequenceIRError,
    apply_edits,
    sha256_text,
)
from .version import (
    COMPILER_VERSION,
    GENOTYPE_COMPILER_VERSION,
    ISA_VERSION,
    LOWERING_VERSION,
    SEMANTIC_VERSION,
    SEQUENCE_IR_VERSION,
)


STATUSES = (
    "COMPILED",
    "COMPILED_WITH_WARNINGS",
    "DESIGN_UNRESOLVED",
    "REFERENCE_UNAVAILABLE",
    "INVALID_PROGRAM",
    "INVALID_EDIT",
    "REFERENCE_MISMATCH",
    "INSUFFICIENT_EVIDENCE",
    "UNSUPPORTED_OPERATION",
)

_KEYVAL = re.compile(r"^(organism|assembly|reference|target|expected_digest|causal_basis|validation_status)\s+(\S+)\s*$")
_REPLACE = re.compile(r"^(replace|insert|delete|substitute|invert|duplicate|move|copy)\s+(\d+)\s+(\d+)\s*(\S*)\s*$", re.I)
_OP = re.compile(r"^(COPY|INSERT|DELETE|REPLACE|DUPLICATE|INVERT|MOVE|SUBSTITUTE)\s*$")


class DesignStatus(Exception):
    def __init__(self, status: str, message: str, payload: Optional[Dict[str, Any]] = None):
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message
        self.payload = payload or {}


@dataclass
class SequenceProgram:
    organism: str
    assembly: str
    reference: str
    edits: List[SequenceEdit]
    target: str = "explicit_sequence_transformation"
    expected_digest: Optional[str] = None
    source_kind: str = "sequence_design"
    raw: str = ""
    causal_basis: str = "EVIDENCE_BACKED"
    validation_status: str = "NOT_VALIDATED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "organism": self.organism,
            "assembly": self.assembly,
            "reference": self.reference,
            "target": self.target,
            "expected_digest": self.expected_digest,
            "source_kind": self.source_kind,
            "causal_basis": self.causal_basis,
            "validation_status": self.validation_status,
            "edits": [e.to_dict() for e in self.edits],
        }


@dataclass
class GenotypeDesign:
    design_id: str
    organism: str
    assembly: str
    reference: str
    edits: List[Dict[str, Any]]
    constraints: List[str] = field(default_factory=list)
    resolved_constraints: List[str] = field(default_factory=list)
    unresolved_constraints: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    status: str = "COMPILED"
    provenance: str = "DESIGN"
    phenotype_target: str = "explicit_sequence_transformation"
    genomic_realization: str = "resolved"
    reason: str = ""
    program_id: str = ""
    realization_strategy: str = ""
    causal_basis: str = ""
    validation_status: str = "NOT_VALIDATED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def detect_source_kind(source: str) -> str:
    text = source.strip()
    if not text:
        return "invalid"
    if re.search(r"^\s*organism\s+\S+\s*\{", text, re.M):
        return "intent"
    if re.search(r"^\s*(replace|insert|delete|substitute|invert|duplicate|move|copy)\b", text, re.I | re.M):
        return "sequence_design"
    if re.search(r"^\s*program\s+\S+", text, re.I | re.M):
        return "sequence_design"
    if re.search(r"^\s*organism\s+\S+\s*$", text, re.M) and re.search(
        r"^\s*(assembly|reference)\s+", text, re.M
    ):
        return "sequence_design"
    return "intent"


def parse_sequence_program(source: str) -> SequenceProgram:
    fields: Dict[str, str] = {}
    edits: List[SequenceEdit] = []
    for raw in source.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        if line in {"{", "}", "operation:", "operation"} or line.startswith("program "):
            continue
        line = line.replace("=", " ")
        line = re.sub(r"[,:]+$", "", line)
        m = _KEYVAL.match(line)
        if m:
            fields[m.group(1)] = m.group(2)
            continue
        m = _REPLACE.match(line)
        if m:
            op, start, end, repl = m.group(1).upper(), int(m.group(2)), int(m.group(3)), m.group(4)
            edits.append(SequenceEdit(
                edit_id=f"edit-{len(edits)+1}",
                operation=op,
                start=start,
                end=end,
                replacement=(repl or "").upper(),
                provenance="DESIGN",
            ))
            continue
        raise DesignStatus("INVALID_PROGRAM", line)
    for key in ("organism", "assembly", "reference"):
        if key not in fields:
            raise DesignStatus("INVALID_PROGRAM", f"missing {key}")
    if not edits:
        raise DesignStatus("INVALID_PROGRAM", "no sequence operation")
    return SequenceProgram(
        organism=fields["organism"],
        assembly=fields["assembly"],
        reference=fields["reference"],
        edits=edits,
        target=fields.get("target", "explicit_sequence_transformation"),
        expected_digest=fields.get("expected_digest"),
        raw=source,
        causal_basis=fields.get("causal_basis", "EVIDENCE_BACKED"),
        validation_status=fields.get("validation_status", "NOT_VALIDATED"),
    )


def _digest_obj(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(blob).hexdigest()


def _semantic_ir(program: SequenceProgram) -> Dict[str, Any]:
    return {
        "type": "SemanticIR",
        "version": SEMANTIC_VERSION,
        "organism": program.organism,
        "assembly": program.assembly,
        "reference": program.reference,
        "target": program.target,
        "operations": [e.to_dict() for e in program.edits],
        "knowledge": _knowledge_view(program),
    }


def _knowledge_view(program: SequenceProgram) -> Dict[str, Any]:
    reg = get_knowledge_registry()
    recs = []
    for cid in (
        f"org:{program.organism}",
        f"asm:{program.assembly}",
        f"seq:{program.assembly}:{program.reference}",
    ):
        hit = reg.resolve(cid)
        if hit:
            recs.append(hit.to_dict())
    return {"resolved": recs}


def _cisc_ir(program: SequenceProgram) -> Dict[str, Any]:
    ops = []
    for edit in program.edits:
        low = lowering_for(edit.operation if edit.operation != "SUBSTITUTE" else "REPLACE")
        ops.append({
            "opcode": edit.operation if edit.operation != "SUBSTITUTE" else "REPLACE",
            "edit": edit.to_dict(),
            "implementation_status": "EXECUTABLE" if low.sequence_realizable or edit.operation in {"REPLACE", "INSERT", "DELETE", "SUBSTITUTE"} else "SPECIFIED",
            "lowering_status": low.lowering_status,
        })
    return {"type": "GeneticCISC", "version": ISA_VERSION, "operations": ops}


def _risc_ir(program: SequenceProgram) -> Dict[str, Any]:
    operations = [{"opcode": "COPY", "note": "reference-derived regions"}]
    lowering = []
    unresolved = []
    for edit in program.edits:
        cisc_op = edit.operation if edit.operation != "SUBSTITUTE" else "REPLACE"
        low = lowering_for(cisc_op)
        if edit.operation not in {"REPLACE", "INSERT", "DELETE", "SUBSTITUTE"} or low.lowering_status == "UNAVAILABLE" and cisc_op not in {"REPLACE", "INSERT", "DELETE", "EDIT"}:
            unresolved.append(edit.operation)
            lowering.append({
                "cisc_opcode": edit.operation,
                "lowering_status": "UNAVAILABLE",
                "risc_sequence": [],
            })
            continue
        operations.append({"opcode": edit.operation, "edit": edit.to_dict()})
        lowering.append({
            "cisc_opcode": cisc_op,
            "lowering_status": "AVAILABLE",
            "risc_sequence": low.risc_sequence or [edit.operation],
            "rule": low.rule or f"{edit.operation} applied as explicit sequence primitive",
        })
    status = "LOWERED" if not unresolved else "UNAVAILABLE"
    return {
        "type": "GeneticRISC",
        "version": LOWERING_VERSION,
        "lowering_status": status,
        "operations": operations,
        "lowering": lowering,
        "unresolved": unresolved,
    }


def compile_sequence_program(
    source: str,
    backend: Optional[MemoryReferenceBackend] = None,
    expected_reference_digest: Optional[str] = None,
) -> Dict[str, Any]:
    backend = backend or default_backend()
    program = parse_sequence_program(source)
    semantic = _semantic_ir(program)
    cisc = _cisc_ir(program)
    risc = _risc_ir(program)

    if risc["lowering_status"] == "UNAVAILABLE" or risc["unresolved"]:
        design = GenotypeDesign(
            design_id="gd_" + _digest_obj(program.to_dict())[:12],
            organism=program.organism,
            assembly=program.assembly,
            reference=program.reference,
            edits=[e.to_dict() for e in program.edits],
            status="DESIGN_UNRESOLVED",
            phenotype_target=program.target,
            genomic_realization="unresolved",
            reason="No evidence-backed sequence realization is currently available.",
        )
        return {
            "status": "DESIGN_UNRESOLVED",
            "semantic_ir": semantic,
            "cisc": cisc,
            "risc": risc,
            "genotype_design": design.to_dict(),
            "sequence_ir": SequenceIR(
                reference=program.reference,
                assembly=program.assembly,
                edits=program.edits,
                organism=program.organism,
            ).to_dict(),
            "derived_sequence": None,
            "warnings": ["unsupported CISC→sequence lowering"],
            "program": program.to_dict(),
        }

    try:
        ref = backend.resolve_sequence(program.assembly, program.reference)
    except SequenceIRError as exc:
        raise DesignStatus(exc.status, exc.detail)

    want = expected_reference_digest or program.expected_digest
    if want and not backend.verify_digest(ref, want):
        raise DesignStatus("REFERENCE_MISMATCH", "reference digest does not match pinned value")

    seq_ir = SequenceIR(
        reference=program.reference,
        assembly=program.assembly,
        edits=program.edits,
        organism=program.organism,
    )
    try:
        derived = apply_edits(ref, program.edits)
    except SequenceIRError as exc:
        raise DesignStatus(exc.status, exc.detail)

    asserted = program.causal_basis == "USER_ASSERTED"
    design = GenotypeDesign(
        design_id="gd_" + _digest_obj(program.to_dict())[:12],
        organism=program.organism,
        assembly=program.assembly,
        reference=program.reference,
        edits=[e.to_dict() for e in program.edits],
        evidence=["user_assertion"] if asserted else ["explicit_sequence_transformation"],
        status="COMPILED_WITH_WARNINGS" if asserted else "COMPILED",
        phenotype_target=program.target,
        genomic_realization="resolved",
        reason=(
            "user-asserted sequence edit; causal_basis=USER_ASSERTED; not scientific validation"
            if asserted else "explicit validated sequence edit; no causal phenotype claim"
        ),
    )
    design_dict = design.to_dict()
    design_dict["causal_basis"] = program.causal_basis
    design_dict["validation_status"] = "NOT_VALIDATED" if asserted else program.validation_status
    warnings = []
    diagnostics = []
    if asserted:
        from .diagnostics import emit
        diag = emit(
            "E0009",
            "uac-explicit",
            "User assertion compiled; validation_status remains NOT_VALIDATED.",
            severity="warning",
            causal_basis="USER_ASSERTED",
            validation_status="NOT_VALIDATED",
            resolution_path="USER_ASSERTED",
        )
        diagnostics.append(diag.to_dict())
        warnings.append(diag.message)
    return {
        "status": design.status,
        "semantic_ir": semantic,
        "cisc": cisc,
        "risc": risc,
        "genotype_design": design_dict,
        "sequence_ir": seq_ir.to_dict(),
        "reference": ref.to_dict(),
        "reference_metadata": backend.retrieve_metadata(program.assembly, program.reference),
        "derived_sequence": derived.sequence,
        "derived": derived.to_dict(),
        "fasta": derived.to_fasta(),
        "warnings": warnings,
        "diagnostics": diagnostics,
        "program": program.to_dict(),
    }


def compile_unresolved_phenotype(
    source: str,
    organism: str,
    phenotype_target: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Honest result when a phenotype has no evidence-backed sequence mapping."""
    design = GenotypeDesign(
        design_id="gd_unresolved_" + sha256_text(source)[:12],
        organism=organism,
        assembly="",
        reference="",
        edits=[],
        status="DESIGN_UNRESOLVED",
        phenotype_target=phenotype_target,
        genomic_realization="unresolved",
        reason="No evidence-backed sequence realization is currently available.",
        evidence=[],
    )
    from .diagnostics import emit
    from .experimental_ir import ExperimentalIR, work_order_from_diagnostic

    diag = emit(
        "E0001",
        "c001_unresolved_phenotype",
        design.reason,
        causal_basis="UNRESOLVED",
        validation_status="NOT_EVALUATED",
        why_lowering_stopped="unresolved_biological_mechanism",
        resolution_path="UNRESOLVED",
        affected_artifacts=["genotype_design"],
    )
    order = work_order_from_diagnostic(diag, target_property=phenotype_target)
    experimental = ExperimentalIR(
        experimental_ir_id="eir_" + sha256_text(source)[:12],
        program_id=design.design_id,
        work_orders=[order],
    )
    payload = {
        "status": "DESIGN_UNRESOLVED",
        "semantic_ir": {
            "type": "SemanticIR",
            "organism": organism,
            "target": phenotype_target,
            "source_kind": "intent",
            "note": "phenotype program; sequence realization not justified",
        },
        "cisc": {"type": "GeneticCISC", "operations": [], "note": "no sequence-realizable opcode supplied"},
        "risc": {
            "type": "GeneticRISC",
            "lowering_status": "UNAVAILABLE",
            "operations": [],
            "unresolved": [phenotype_target],
        },
        "genotype_design": design.to_dict(),
        "sequence_ir": None,
        "derived_sequence": None,
        "warnings": [design.reason],
        "phenotype_target": "known",
        "genomic_realization": "unresolved",
        "diagnostics": [diag.to_dict()],
        "resolution_work_orders": [order.to_dict()],
        "experimental_ir": experimental.to_dict(),
    }
    if extra:
        payload["context"] = extra
    return payload


def write_bundle(result: Dict[str, Any], source: str, outdir: str | Path) -> Dict[str, Any]:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    source_digest = sha256_text(source)
    artifacts: Dict[str, str] = {}

    stages = [
        ("01-source", {"source": source, "digest": source_digest}),
        ("02-semantic-ir", result.get("semantic_ir")),
        ("03-cisc", result.get("cisc")),
        ("04-risc", result.get("risc")),
        ("05-genotype-design", result.get("genotype_design")),
        ("06-sequence-ir", result.get("sequence_ir")),
    ]
    for name, payload in stages:
        path = out / f"{name}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        artifacts[name] = _digest_obj(payload)

    derived = result.get("derived_sequence")
    seq_digest = sha256_text(derived) if derived else None
    if derived:
        fasta = result.get("fasta") or f">derived\n{derived}\n"
        (out / "07-derived-sequence.fasta").write_text(fasta, encoding="utf-8")
        (out / "derived.fasta").write_text(fasta, encoding="utf-8")
        (out / "sequence.fasta").write_text(fasta, encoding="utf-8")
        (out / "sequence.json").write_text(
            json.dumps(result.get("derived") or {"sequence": derived}, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    ref = result.get("reference") or {}
    manifest = {
        "compiler_version": COMPILER_VERSION,
        "genotype_compiler_version": GENOTYPE_COMPILER_VERSION,
        "isa_version": ISA_VERSION,
        "semantic_version": SEMANTIC_VERSION,
        "lowering_version": LOWERING_VERSION,
        "sequence_ir_version": SEQUENCE_IR_VERSION,
        "organism": (result.get("program") or {}).get("organism")
        or (result.get("genotype_design") or {}).get("organism"),
        "assembly": (result.get("program") or {}).get("assembly") or ref.get("assembly"),
        "reference_identifier": ref.get("sequence_id") or (result.get("program") or {}).get("reference"),
        "reference_digest": ref.get("digest"),
        "input_program_digest": source_digest,
        "semantic_ir_digest": artifacts.get("02-semantic-ir"),
        "cisc_digest": artifacts.get("03-cisc"),
        "risc_digest": artifacts.get("04-risc"),
        "genotype_design_digest": artifacts.get("05-genotype-design"),
        "sequence_ir_digest": artifacts.get("06-sequence-ir"),
        "output_sequence_digest": seq_digest,
        "artifact_digests": artifacts,
        "edits": (result.get("genotype_design") or {}).get("edits") or [],
        "evidence": (result.get("genotype_design") or {}).get("evidence") or [],
        "warnings": result.get("warnings") or [],
        "status": result.get("status"),
        "causal_basis": (result.get("genotype_design") or {}).get("causal_basis"),
        "validation_status": (result.get("genotype_design") or {}).get("validation_status"),
        "phenotype_target": (result.get("genotype_design") or {}).get("phenotype_target"),
        "genomic_realization": (result.get("genotype_design") or {}).get("genomic_realization"),
        "provenance": {
            "reference": "REFERENCE_DATA" if ref else "MODEL",
            "design": "DESIGN",
            "compiler": "MODEL",
            "simulation": "SIMULATION",
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    (out / "08-provenance.json").write_text(
        json.dumps(
            {
                "chain": [
                    "source",
                    "semantic_ir",
                    "cisc",
                    "risc",
                    "genotype_design",
                    "sequence_ir",
                    "reference",
                    "derived_sequence",
                    "verification",
                ],
                "parent_digests": artifacts,
                "output_sequence_digest": seq_digest,
                "classes": manifest["provenance"],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    extras = [
        ("diagnostics.json", result.get("diagnostics")),
        ("resolution-report.json", result.get("biological_resolution")),
        ("experimental-ir.json", result.get("experimental_ir")),
        ("resolution-work-orders.json", result.get("resolution_work_orders")),
        ("coverage.json", result.get("coverage")),
    ]
    for name, payload in extras:
        if payload is None:
            continue
        (out / name).write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")

    verification = verify_bundle(out)
    (out / "verification.json").write_text(json.dumps(verification, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def verify_bundle(outdir: str | Path) -> Dict[str, Any]:
    out = Path(outdir)
    man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    checks = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "passed": ok, "detail": detail})

    for name in (
        "01-source.json",
        "02-semantic-ir.json",
        "03-cisc.json",
        "04-risc.json",
        "05-genotype-design.json",
        "08-provenance.json",
        "manifest.json",
    ):
        check(f"artifact:{name}", (out / name).exists(), str(out / name))

    if man.get("status") == "DESIGN_UNRESOLVED":
        check(
            "no_invented_sequence",
            not (out / "07-derived-sequence.fasta").exists() and not (out / "derived.fasta").exists(),
            "unresolved designs must not emit a derived biological sequence artifact",
        )
        check("status_recorded", man.get("status") == "DESIGN_UNRESOLVED", man.get("status"))
        return {"overall_pass": all(c["passed"] for c in checks), "status": man.get("status"), "checks": checks}

    fasta_path = out / "07-derived-sequence.fasta"
    if not fasta_path.exists():
        fasta_path = out / "derived.fasta"
    if fasta_path.exists():
        lines = fasta_path.read_text(encoding="utf-8").splitlines()
        seq = "".join(x.strip() for x in lines if x and not x.startswith(">"))
        digest = sha256_text(seq)
        check("output_digest", digest == man.get("output_sequence_digest"), digest)
        check("fasta_alphabet", all(c in "ACGT" for c in seq), f"len={len(seq)}")
        check("reproducible_digest_field", bool(man.get("output_sequence_digest")), man.get("output_sequence_digest"))
    else:
        check("derived_fasta", False, "missing")

    check("reference_digest_present", bool(man.get("reference_digest")), str(man.get("reference_digest")))
    check("input_digest_present", bool(man.get("input_program_digest")), str(man.get("input_program_digest")))
    overall = all(c["passed"] for c in checks)
    return {"overall_pass": overall, "status": man.get("status"), "checks": checks}


def inspect_stage(outdir: str | Path, stage: str) -> Any:
    out = Path(outdir)
    aliases = {
        "source": "01-source.json",
        "semantic-ir": "02-semantic-ir.json",
        "semantic_ir": "02-semantic-ir.json",
        "cisc": "03-cisc.json",
        "risc": "04-risc.json",
        "genotype": "05-genotype-design.json",
        "genotype-design": "05-genotype-design.json",
        "sequence-ir": "06-sequence-ir.json",
        "sequence_ir": "06-sequence-ir.json",
        "manifest": "manifest.json",
        "provenance": "08-provenance.json",
        "verification": "verification.json",
        "diagnostics": "diagnostics.json",
        "resolution": "resolution-report.json",
        "resolution-report": "resolution-report.json",
        "experimental-ir": "experimental-ir.json",
        "experimental_ir": "experimental-ir.json",
        "work-orders": "resolution-work-orders.json",
        "resolution-work-orders": "resolution-work-orders.json",
        "coverage": "coverage.json",
    }
    name = aliases.get(stage, stage)
    path = out / name
    if not path.exists():
        raise FileNotFoundError(stage)
    if path.suffix == ".fasta":
        return path.read_text(encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def compile_any(
    source: str,
    backend: Optional[MemoryReferenceBackend] = None,
    intent_context: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Dict[str, Any]]:
    kind = detect_source_kind(source)
    if kind == "sequence_design":
        return kind, compile_sequence_program(source, backend=backend)
    organism = "unknown"
    target = "unspecified_phenotype"
    if intent_context:
        organism = intent_context.get("organism") or organism
        target = intent_context.get("phenotype_target") or target
    try:
        from .frontend import parse_source
        from .resolution import compile_intent_genotype
        program = parse_source(source)
        payload = compile_intent_genotype(
            source,
            program,
            program_id=intent_context.get("program_id") if intent_context else "",
            phenotype_target=target,
            extra=intent_context,
            backend=backend,
        )
        return kind, payload
    except Exception:
        return kind, compile_unresolved_phenotype(source, organism, target, extra=intent_context)
