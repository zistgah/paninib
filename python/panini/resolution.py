# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Biological resolution engine."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .constraint_graph import ConstraintGraph, graph_from_constraints
from .diagnostics import CAUSAL_ENOUGH, Diagnostic, emit
from .experimental_ir import ExperimentalIR, ResolutionWorkOrder, work_order_from_diagnostic
from .frontend import IntentStmt, Program
from .inverse import InverseResolution, evaluate_inverse
from .knowledge import (
    KnowledgeRecord,
    get_knowledge_registry,
    lookup_association_records,
    lookup_realization_records,
)
from .providers import (
    GenerativeModelProvider,
    ModelCandidate,
    UnavailableGenerativeProvider,
)
from .reference_backend import MemoryReferenceBackend, default_backend
from .routing import ProviderRouter, RouteStep, RouteTrace, get_router
from .sequence_ir import SequenceEdit, SequenceIR, SequenceIRError, apply_edits
from .version import COMPILER_VERSION, RESOLUTION_VERSION


_GENERATIVE: GenerativeModelProvider = UnavailableGenerativeProvider()


def set_generative_provider(provider: GenerativeModelProvider) -> None:
    global _GENERATIVE
    _GENERATIVE = provider


def get_generative_provider() -> GenerativeModelProvider:
    return _GENERATIVE


@dataclass
class BioConstraint:
    constraint_id: str
    intent_verb: str
    intent_name: str
    bindings: Dict[str, str]
    organism: str
    source_location: str = ""
    status: str = "UNRESOLVED"
    causal_basis: str = "UNRESOLVED"
    validation_status: str = "NOT_EVALUATED"
    strategy: str = "UNRESOLVED"
    knowledge_record_id: Optional[str] = None
    evidence_record_ids: List[str] = field(default_factory=list)
    provider: Optional[str] = None
    model_id: Optional[str] = None
    edits: List[SequenceEdit] = field(default_factory=list)
    assembly: str = ""
    reference: str = ""
    association_class: str = ""
    notes: str = ""
    inverse: Optional[Dict[str, Any]] = None
    candidate: Optional[Dict[str, Any]] = None
    route: Optional[Dict[str, Any]] = None
    direction: str = ""
    licenses_inverse: bool = False
    evidence_status: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "intent_verb": self.intent_verb,
            "intent_name": self.intent_name,
            "bindings": self.bindings,
            "organism": self.organism,
            "status": self.status,
            "causal_basis": self.causal_basis,
            "validation_status": self.validation_status,
            "strategy": self.strategy,
            "knowledge_record_id": self.knowledge_record_id,
            "evidence_record_ids": list(self.evidence_record_ids),
            "provider": self.provider,
            "model_id": self.model_id,
            "assembly": self.assembly,
            "reference": self.reference,
            "association_class": self.association_class,
            "notes": self.notes,
            "edits": [e.to_dict() for e in self.edits],
            "inverse": self.inverse,
            "candidate": self.candidate,
            "route": self.route,
            "direction": self.direction,
            "licenses_inverse": self.licenses_inverse,
            "evidence_status": self.evidence_status,
        }


@dataclass
class ResolutionReport:
    program_id: str
    status: str
    constraints: List[BioConstraint]
    diagnostics: List[Diagnostic]
    work_orders: List[ResolutionWorkOrder]
    experimental_ir: ExperimentalIR
    coverage: Dict[str, float]
    genotype_design: Dict[str, Any]
    sequence_result: Optional[Dict[str, Any]] = None
    resolved_ids: List[str] = field(default_factory=list)
    unresolved_ids: List[str] = field(default_factory=list)
    constraint_graph: Optional[Dict[str, Any]] = None
    provider_diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    route_traces: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": RESOLUTION_VERSION,
            "program_id": self.program_id,
            "status": self.status,
            "constraints": [c.to_dict() for c in self.constraints],
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "coverage": self.coverage,
            "resolved": list(self.resolved_ids),
            "unresolved": list(self.unresolved_ids),
            "constraint_graph": self.constraint_graph,
            "provider_diagnostics": list(self.provider_diagnostics),
            "route_traces": list(self.route_traces),
        }


def decompose_constraints(program: Program) -> List[BioConstraint]:
    out: List[BioConstraint] = []
    for i, intent in enumerate(program.intents, start=1):
        cid = f"c{i:03d}_{intent.verb}_{intent.name}"
        out.append(BioConstraint(
            constraint_id=cid,
            intent_verb=intent.verb,
            intent_name=intent.name,
            bindings=dict(intent.bindings),
            organism=program.organism,
            source_location=f"intent.{intent.verb}.{intent.name}",
        ))
    return out


def _edits_from_mapping(attrs: Dict[str, Any], constraint_id: str) -> List[SequenceEdit]:
    edits = []
    for i, raw in enumerate(attrs.get("edits") or [], start=1):
        op = str(raw.get("operation", "REPLACE")).upper()
        edits.append(SequenceEdit(
            edit_id=f"{constraint_id}-edit-{i}",
            operation=op,
            start=int(raw.get("start", 0)),
            end=int(raw.get("end", 0)),
            replacement=str(raw.get("replacement", "")).upper(),
            provenance=str(attrs.get("causal_basis", "DESIGN")),
        ))
    return edits


def _apply_mapping(constraint: BioConstraint, rec: KnowledgeRecord) -> Optional[Diagnostic]:
    attrs = rec.attributes or {}
    association = str(attrs.get("association_class", "")).upper()
    basis = str(attrs.get("causal_basis", "EVIDENCE_BACKED")).upper()
    validation = str(attrs.get("validation_status", "NOT_VALIDATED")).upper()
    strategy = str(attrs.get("strategy", "KNOWLEDGE_PROVIDER")).upper()
    direction = str(attrs.get("direction", "")).lower()
    licenses_inverse = bool(attrs.get("licenses_inverse", False))
    wanted_direction = str(constraint.bindings.get("direction", "")).lower()
    inverse = evaluate_inverse(constraint.constraint_id, attrs, wanted_direction)
    constraint.inverse = inverse.to_dict()
    constraint.direction = inverse.direction
    constraint.licenses_inverse = inverse.licenses_inverse
    constraint.evidence_status = inverse.evidence_status

    if association in {"ASSOCIATED", "CORRELATED"}:
        constraint.association_class = association
        constraint.causal_basis = association
        constraint.validation_status = validation
        constraint.knowledge_record_id = rec.canonical_id
        constraint.strategy = "KNOWLEDGE_PROVIDER"
        return emit(
            "E0010",
            constraint.constraint_id,
            f"Record {rec.canonical_id} is {association}; association is not a causal genotype realization.",
            causal_basis=association,
            validation_status=validation if validation else "NOT_EVALUATED",
            current_evidence=list(attrs.get("evidence_ids") or []),
            why_lowering_stopped="association_is_not_causation",
            resolution_path="knowledge_provider",
        )

    if wanted_direction and direction and wanted_direction != direction and not licenses_inverse:
        return emit(
            "E0007",
            constraint.constraint_id,
            f"Record {rec.canonical_id} has direction={direction} and does not license an inverse mapping.",
            causal_basis=basis if basis else "UNRESOLVED",
            why_lowering_stopped="inverse_mapping_not_licensed",
            resolution_path="knowledge_provider",
        )

    edits = _edits_from_mapping(attrs, constraint.constraint_id)
    if not edits:
        return emit(
            "E0002",
            constraint.constraint_id,
            f"Realization record {rec.canonical_id} has no sequence edits or standard-part payload.",
            causal_basis=basis if basis else "UNRESOLVED",
            why_lowering_stopped="missing_standard_part_payload",
            resolution_path=strategy or "REGISTRY_LOOKUP",
        )

    constraint.status = "USER_ASSERTED" if basis == "USER_ASSERTED" else (
        "MODEL_DERIVED" if basis == "MODEL_DERIVED" else "RESOLVED"
    )
    constraint.causal_basis = basis
    constraint.validation_status = validation or "NOT_VALIDATED"
    constraint.strategy = strategy or "KNOWLEDGE_PROVIDER"
    constraint.knowledge_record_id = rec.canonical_id
    constraint.evidence_record_ids = list(attrs.get("evidence_ids") or [])
    constraint.provider = attrs.get("provider") or rec.source
    constraint.model_id = attrs.get("model_id")
    constraint.assembly = str(attrs.get("assembly") or "")
    constraint.reference = str(attrs.get("reference") or "")
    constraint.association_class = association
    constraint.edits = edits
    constraint.notes = f"realized from {rec.canonical_id}"
    return None


def _apply_user_assertion(constraint: BioConstraint, assertion: IntentStmt) -> Optional[Diagnostic]:
    b = assertion.bindings
    assembly = b.get("assembly", "")
    reference = b.get("reference", "")
    op = (b.get("operation") or "REPLACE").upper()
    try:
        start = int(b.get("start", "0"))
        end = int(b.get("end", "0"))
    except ValueError:
        return emit(
            "E0007",
            constraint.constraint_id,
            "User assertion coordinates are not integers.",
            causal_basis="USER_ASSERTED",
            validation_status="NOT_VALIDATED",
        )
    replacement = (b.get("replacement") or "").upper()
    if not assembly or not reference:
        return emit(
            "E0005",
            constraint.constraint_id,
            "User assertion is missing assembly or reference identity.",
            causal_basis="USER_ASSERTED",
            validation_status="NOT_VALIDATED",
        )
    constraint.status = "USER_ASSERTED"
    constraint.causal_basis = "USER_ASSERTED"
    constraint.validation_status = "NOT_VALIDATED"
    constraint.strategy = "USER_ASSERTED"
    constraint.assembly = assembly
    constraint.reference = reference
    constraint.edits = [SequenceEdit(
        edit_id=f"{constraint.constraint_id}-uac",
        operation=op,
        start=start,
        end=end,
        replacement=replacement,
        provenance="USER_ASSERTED",
    )]
    constraint.notes = "user-asserted causality; not scientific validation"
    return emit(
        "E0009",
        constraint.constraint_id,
        "User assertion compiled with causal_basis=USER_ASSERTED; validation_status remains NOT_VALIDATED.",
        severity="warning",
        causal_basis="USER_ASSERTED",
        validation_status="NOT_VALIDATED",
        resolution_path="USER_ASSERTED",
        why_lowering_stopped="",
    )


def _match_assertion(program: Program, constraint: BioConstraint) -> Optional[IntentStmt]:
    for assertion in program.assertions:
        target = assertion.bindings.get("constrains") or assertion.bindings.get("constraint") or assertion.name
        if target == constraint.intent_name or target == constraint.constraint_id or assertion.name == constraint.intent_name:
            return assertion
        if assertion.verb in {"bind", "assert", "edit"} and assertion.name == constraint.intent_name:
            return assertion
    return None


class BiologicalResolutionEngine:
    def __init__(self, backend: Optional[MemoryReferenceBackend] = None, generative: Optional[GenerativeModelProvider] = None):
        self.backend = backend or default_backend()
        self.generative = generative or get_generative_provider()

    def resolve_program(self, program: Program, program_id: str = "") -> ResolutionReport:
        constraints = decompose_constraints(program)
        diagnostics: List[Diagnostic] = []
        pid = program_id or f"prog_{program.organism}"

        for constraint in constraints:
            diagnostics.extend(self._resolve_one(program, constraint))

        resolved = [c for c in constraints if c.status in {"RESOLVED", "USER_ASSERTED", "MODEL_DERIVED"}]
        unresolved = [c for c in constraints if c.status == "UNRESOLVED"]
        ambiguous = [c for c in constraints if c.status == "AMBIGUOUS"]

        work_orders: List[ResolutionWorkOrder] = []
        for diag in diagnostics:
            if diag.severity == "error":
                work_orders.append(work_order_from_diagnostic(
                    diag,
                    target_property=next(
                        (f"{c.intent_verb}:{c.intent_name}" for c in constraints if c.constraint_id == diag.constraint_id),
                        diag.constraint_id,
                    ),
                ))

        sequence_result = None
        design_status = "DESIGN_UNRESOLVED"
        reason = "No evidence-backed sequence realization is currently available."
        genomic = "unresolved"
        merged_edits: List[SequenceEdit] = []
        assembly = ""
        reference = ""

        if resolved:
            assemblies = {c.assembly for c in resolved if c.assembly}
            refs = {c.reference for c in resolved if c.reference}
            if len(assemblies) > 1 or len(refs) > 1:
                diagnostics.append(emit(
                    "E0006",
                    resolved[0].constraint_id,
                    "Resolved constraints name incompatible reference contexts.",
                    why_lowering_stopped="reference_context_incompatible",
                ))
                work_orders.append(work_order_from_diagnostic(diagnostics[-1], target_property="reference_context"))
            else:
                assembly = next(iter(assemblies), "")
                reference = next(iter(refs), "")
                for c in resolved:
                    merged_edits.extend(c.edits)
                if assembly and reference:
                    try:
                        ref = self.backend.resolve_sequence(assembly, reference)
                        derived = apply_edits(ref, merged_edits)
                        seq_ir = SequenceIR(reference=reference, assembly=assembly, edits=merged_edits, organism=program.organism)
                        sequence_result = {
                            "sequence_ir": seq_ir.to_dict(),
                            "reference": ref.to_dict(),
                            "derived_sequence": derived.sequence,
                            "derived": derived.to_dict(),
                            "fasta": derived.to_fasta(),
                            "reference_metadata": self.backend.retrieve_metadata(assembly, reference),
                        }
                    except SequenceIRError as exc:
                        code = "E0005" if exc.status == "REFERENCE_UNAVAILABLE" else "E0007"
                        diagnostics.append(emit(code, resolved[0].constraint_id, str(exc), why_lowering_stopped=exc.status))
                        work_orders.append(work_order_from_diagnostic(diagnostics[-1], target_property=f"{assembly}:{reference}"))
                        sequence_result = None

        if resolved and not unresolved and not ambiguous and sequence_result:
            design_status = "COMPILED"
            genomic = "resolved"
            reason = "all constraints resolved against knowledge/registry/assertion contracts"
        elif resolved and sequence_result:
            design_status = "COMPILED_WITH_WARNINGS"
            genomic = "partial"
            reason = "resolved subset compiled; unresolved constraints retained as diagnostics"
        elif resolved and not sequence_result:
            design_status = "DESIGN_UNRESOLVED"
            genomic = "unresolved"
            reason = "resolved mappings could not be lowered through Sequence IR"
        else:
            design_status = "DESIGN_UNRESOLVED"
            genomic = "unresolved"
            reason = "No evidence-backed sequence realization is currently available."

        warnings_only = [d for d in diagnostics if d.code == "E0008"]
        if design_status == "COMPILED" and warnings_only:
            design_status = "COMPILED_WITH_WARNINGS"

        total = max(len(constraints), 1)
        n_resolved = len(resolved)
        n_seq = 1.0 if sequence_result else 0.0
        n_evidence = sum(1 for c in resolved if c.evidence_record_ids) / total
        n_validated = sum(1 for c in constraints if c.validation_status in {"EXPERIMENTALLY_SUPPORTED", "EXPERIMENTALLY_VALIDATED"}) / total
        n_registry = sum(1 for c in resolved if c.strategy in {"STANDARD_LIBRARY", "REGISTRY_LOOKUP"}) / total
        n_model = sum(1 for c in resolved if c.strategy == "MODEL_DERIVED") / total
        coverage = {
            "semantic_coverage": 1.0 if constraints else 0.0,
            "lowering_coverage": n_resolved / total,
            "sequence_coverage": n_seq * (n_resolved / total),
            "evidence_coverage": n_evidence,
            "validation_coverage": n_validated,
            "constraint_resolution_coverage": n_resolved / total,
            "registry_resolution_coverage": n_registry,
            "model_coverage": n_model,
        }

        design_id = "gd_" + hashlib.sha256(pid.encode()).hexdigest()[:12]
        genotype_design = {
            "design_id": design_id,
            "program_id": pid,
            "organism": program.organism,
            "assembly": assembly,
            "reference": reference,
            "constraints": [c.constraint_id for c in constraints],
            "resolved_constraints": [c.constraint_id for c in resolved],
            "unresolved_constraints": [c.constraint_id for c in unresolved + ambiguous],
            "edits": [e.to_dict() for e in merged_edits],
            "realization_strategy": resolved[0].strategy if len({c.strategy for c in resolved}) == 1 and resolved else ("MIXED" if resolved else "UNRESOLVED"),
            "causal_basis": resolved[0].causal_basis if len(resolved) == 1 else ("MIXED" if resolved else "UNRESOLVED"),
            "evidence": [eid for c in resolved for eid in c.evidence_record_ids],
            "provenance": "RESOLUTION",
            "status": design_status,
            "validation_status": (
                resolved[0].validation_status if len({c.validation_status for c in resolved}) == 1 and resolved
                else ("NOT_VALIDATED" if resolved else "NOT_EVALUATED")
            ),
            "phenotype_target": ";".join(f"{c.intent_verb}:{c.intent_name}" for c in constraints) or "unspecified",
            "genomic_realization": genomic,
            "reason": reason,
            "causal_basis": resolved[0].causal_basis if len(resolved) == 1 else ("MIXED" if resolved else "UNRESOLVED"),
            "validation_status": (
                resolved[0].validation_status if len({c.validation_status for c in resolved}) == 1 and resolved
                else ("NOT_VALIDATED" if resolved else "NOT_EVALUATED")
            ),
        }

        graph = graph_from_constraints(pid, constraints)
        provider_diagnostics = []
        for c in constraints:
            if c.route and any(
                s.get("kind") == "generative_provider" and not s.get("available")
                for s in (c.route.get("steps") or [])
            ):
                provider_diagnostics.append({
                    "code": "PROVIDER_UNAVAILABLE",
                    "constraint_id": c.constraint_id,
                    "provider": (c.route.get("steps") or [{}])[-1].get("provider"),
                    "message": "generative provider is not available; no candidate fabricated",
                })
        experimental = ExperimentalIR(
            experimental_ir_id="eir_" + hashlib.sha256(pid.encode()).hexdigest()[:12],
            program_id=pid,
            work_orders=work_orders,
        )
        experimental.integration = dict(experimental.integration or {})
        experimental.integration["design_ref"] = design_id
        experimental.integration["status"] = design_status
        return ResolutionReport(
            program_id=pid,
            status=design_status,
            constraints=constraints,
            diagnostics=diagnostics,
            work_orders=work_orders,
            experimental_ir=experimental,
            coverage=coverage,
            genotype_design=genotype_design,
            sequence_result=sequence_result,
            resolved_ids=[c.constraint_id for c in resolved],
            unresolved_ids=[c.constraint_id for c in unresolved + ambiguous],
            constraint_graph=graph.to_dict(),
            provider_diagnostics=provider_diagnostics,
            route_traces=[c.route for c in constraints if c.route],
        )

    def _resolve_one(self, program: Program, constraint: BioConstraint) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []
        router = get_router()
        trace = router.new_trace(constraint.constraint_id)

        assertion = _match_assertion(program, constraint)
        trace.add(RouteStep(
            step_id="user_assertion",
            provider="user",
            kind="user_assertion",
            available=assertion is not None,
            invoked=assertion is not None,
            outcome="hit" if assertion is not None else "miss",
        ))
        if assertion is not None:
            diag = _apply_user_assertion(constraint, assertion)
            if diag:
                diagnostics.append(diag)
            if constraint.status != "UNRESOLVED":
                trace.terminal = constraint.status
                constraint.route = trace.to_dict()
                return diagnostics

        mappings = lookup_realization_records(program.organism, constraint.intent_verb, constraint.intent_name)
        trace.add(RouteStep(
            step_id="knowledge_mapping",
            provider="knowledge_registry",
            kind="knowledge_mapping",
            available=True,
            invoked=True,
            outcome=f"n={len(mappings)}",
            artifact_refs=[m.canonical_id for m in mappings],
        ))
        if len(mappings) > 1:
            constraint.status = "AMBIGUOUS"
            diagnostics.append(emit(
                "E0003",
                constraint.constraint_id,
                f"Ambiguous realization: {len(mappings)} RealizationMapping records match "
                f"{program.organism}/{constraint.intent_verb}/{constraint.intent_name}.",
                why_lowering_stopped="ambiguous_mapping",
                resolution_path="KNOWLEDGE_PROVIDER",
                current_evidence=[m.canonical_id for m in mappings],
            ))
            trace.terminal = "AMBIGUOUS"
            constraint.route = trace.to_dict()
            return diagnostics
        if len(mappings) == 1:
            extra = _apply_mapping(constraint, mappings[0])
            if extra:
                diagnostics.append(extra)
                if extra.severity != "warning":
                    constraint.status = "UNRESOLVED"
                    trace.terminal = extra.code
                    constraint.route = trace.to_dict()
                    return diagnostics
            if constraint.causal_basis == "MODEL_DERIVED" and constraint.validation_status in {
                "NOT_VALIDATED", "NOT_EVALUATED", "COMPUTATIONALLY_SUPPORTED",
            }:
                diagnostics.append(emit(
                    "E0008",
                    constraint.constraint_id,
                    "Realization is MODEL_DERIVED; sequence emission is not experimental validation.",
                    severity="warning",
                    causal_basis="MODEL_DERIVED",
                    validation_status=constraint.validation_status,
                    resolution_path="MODEL_DERIVED",
                ))
            trace.terminal = constraint.status
            constraint.route = trace.to_dict()
            return diagnostics

        associations = lookup_association_records(program.organism, constraint.intent_verb, constraint.intent_name)
        trace.add(RouteStep(
            step_id="association_guard",
            provider="knowledge_registry",
            kind="association_guard",
            available=True,
            invoked=True,
            outcome=f"n={len(associations)}",
            artifact_refs=[a.canonical_id for a in associations],
        ))
        if associations:
            rec = associations[0]
            attrs = rec.attributes or {}
            klass = str(attrs.get("association_class", "ASSOCIATED")).upper()
            constraint.knowledge_record_id = rec.canonical_id
            constraint.association_class = klass
            constraint.causal_basis = klass if klass in {"ASSOCIATED", "CORRELATED"} else "UNRESOLVED"
            inverse = evaluate_inverse(constraint.constraint_id, attrs, str(constraint.bindings.get("direction", "")))
            constraint.inverse = inverse.to_dict()
            constraint.direction = inverse.direction
            constraint.licenses_inverse = inverse.licenses_inverse
            diagnostics.append(emit(
                "E0010" if klass in {"ASSOCIATED", "CORRELATED"} else "E0004",
                constraint.constraint_id,
                f"Knowledge contains {klass} claim {rec.canonical_id} but not a causal genotype realization.",
                causal_basis=constraint.causal_basis,
                current_evidence=[rec.canonical_id],
                why_lowering_stopped="association_is_not_causation",
                resolution_path="KNOWLEDGE_PROVIDER",
            ))
            trace.terminal = "E0010"
            constraint.route = trace.to_dict()
            return diagnostics

        gen_available = bool(self.generative.available())
        trace.add(RouteStep(
            step_id="generative_provider",
            provider=getattr(self.generative, "provenance", lambda: {"provider": "generative"})().get("provider", "generative"),
            kind="generative_provider",
            available=gen_available,
            invoked=gen_available,
            outcome="available" if gen_available else "UNAVAILABLE",
        ))
        if gen_available:
            proposal = self.generative.propose(constraint)
            if isinstance(proposal, ModelCandidate):
                validated = self.generative.validate_candidate(proposal)
                constraint.candidate = validated.to_dict()
                constraint.provider = validated.provider
                constraint.model_id = validated.model_id
                raw = validated.proposal or {}
                if validated.status in {"CANDIDATE", "SUPPORTED"} and raw.get("edits"):
                    constraint.status = "MODEL_DERIVED"
                    constraint.causal_basis = "MODEL_DERIVED"
                    constraint.validation_status = "NOT_VALIDATED"
                    constraint.strategy = "MODEL_DERIVED"
                    constraint.assembly = str(raw.get("assembly") or "")
                    constraint.reference = str(raw.get("reference") or "")
                    constraint.edits = _edits_from_mapping(raw, constraint.constraint_id)
                    constraint.notes = "model-derived candidate; not experimental validation"
                    diagnostics.append(emit(
                        "E0008",
                        constraint.constraint_id,
                        "Generative provider returned a MODEL_DERIVED candidate; validation_status remains NOT_VALIDATED.",
                        severity="warning",
                        causal_basis="MODEL_DERIVED",
                        validation_status="NOT_VALIDATED",
                        resolution_path="MODEL_DERIVED",
                    ))
                    trace.terminal = "MODEL_DERIVED"
                    constraint.route = trace.to_dict()
                    return diagnostics
                constraint.causal_basis = "GENERATIVE_HYPOTHESIS"
                constraint.strategy = "GENERATIVE_HYPOTHESIS"
                constraint.notes = "generative proposal recorded; not compiled as established biology"
                diagnostics.append(emit(
                    "E0010",
                    constraint.constraint_id,
                    "Generative hypothesis is not a causally established genotype.",
                    causal_basis="GENERATIVE_HYPOTHESIS",
                    validation_status="NOT_VALIDATED",
                    why_lowering_stopped="generative_hypothesis_not_established",
                    resolution_path="GENERATIVE_HYPOTHESIS",
                ))
                trace.terminal = "E0010"
                constraint.route = trace.to_dict()
                return diagnostics
            if proposal:
                constraint.causal_basis = "GENERATIVE_HYPOTHESIS"
                constraint.strategy = "GENERATIVE_HYPOTHESIS"
                constraint.notes = "generative proposal recorded; not compiled as established biology"
                diagnostics.append(emit(
                    "E0010",
                    constraint.constraint_id,
                    "Generative hypothesis is not a causally established genotype.",
                    causal_basis="GENERATIVE_HYPOTHESIS",
                    validation_status="NOT_VALIDATED",
                    why_lowering_stopped="generative_hypothesis_not_established",
                    resolution_path="GENERATIVE_HYPOTHESIS",
                ))
                trace.terminal = "E0010"
                constraint.route = trace.to_dict()
                return diagnostics

        diagnostics.append(emit(
            "E0001",
            constraint.constraint_id,
            (
                f"No defensible genotype realization is known for "
                f"{program.organism} {constraint.intent_verb} {constraint.intent_name}."
            ),
            causal_basis="UNRESOLVED",
            validation_status="NOT_EVALUATED",
            why_lowering_stopped="unresolved_biological_mechanism",
            resolution_path="UNRESOLVED",
            affected_artifacts=["genotype_design", "sequence_ir"],
        ))
        if not gen_available:
            constraint.notes = (constraint.notes + " PROVIDER_UNAVAILABLE").strip()
        trace.terminal = "E0001"
        constraint.route = trace.to_dict()
        return diagnostics


def compile_intent_genotype(
    source: str,
    program: Program,
    *,
    program_id: str = "",
    phenotype_target: str = "",
    extra: Optional[Dict[str, Any]] = None,
    backend: Optional[MemoryReferenceBackend] = None,
) -> Dict[str, Any]:
    engine = BiologicalResolutionEngine(backend=backend)
    report = engine.resolve_program(program, program_id=program_id or phenotype_target or program.organism)
    seq = report.sequence_result or {}
    payload: Dict[str, Any] = {
        "status": report.status,
        "semantic_ir": {
            "type": "SemanticIR",
            "organism": program.organism,
            "target": phenotype_target or report.genotype_design.get("phenotype_target"),
            "source_kind": "intent",
            "constraints": [c.to_dict() for c in report.constraints],
            "note": "biological intent resolved per-constraint against the knowledge substrate",
        },
        "cisc": {
            "type": "GeneticCISC",
            "operations": [
                {"opcode": e.operation, "edit": e.to_dict(), "constraint_id": cid}
                for cid, edits in ((c.constraint_id, c.edits) for c in report.constraints)
                for e in edits
            ],
        },
        "risc": {
            "type": "GeneticRISC",
            "lowering_status": "LOWERED" if seq else "UNAVAILABLE",
            "operations": [e.to_dict() for c in report.constraints for e in c.edits],
            "unresolved": report.unresolved_ids,
        },
        "genotype_design": report.genotype_design,
        "sequence_ir": seq.get("sequence_ir"),
        "derived_sequence": seq.get("derived_sequence"),
        "derived": seq.get("derived"),
        "fasta": seq.get("fasta"),
        "reference": seq.get("reference"),
        "reference_metadata": seq.get("reference_metadata"),
        "warnings": [d.message for d in report.diagnostics],
        "phenotype_target": "known" if program.intents else "unknown",
        "genomic_realization": report.genotype_design.get("genomic_realization"),
        "biological_resolution": report.to_dict(),
        "diagnostics": [d.to_dict() for d in report.diagnostics],
        "resolution_work_orders": [w.to_dict() for w in report.work_orders],
        "experimental_ir": report.experimental_ir.to_dict(),
        "coverage": report.coverage,
        "resolved_constraints": report.resolved_ids,
        "unresolved_constraints": report.unresolved_ids,
        "constraint_graph": report.constraint_graph,
        "provider_diagnostics": report.provider_diagnostics,
        "route_traces": report.route_traces,
        "resolution_version": RESOLUTION_VERSION,
        "compiler_version": COMPILER_VERSION,
    }
    if extra:
        payload["context"] = extra
    return payload
