# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Register two synthetic conformance organisms."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ...contracts import (
    BiologicalKnowledgeModel,
    ContractMeta,
    EvidenceModel,
    GenomeModel,
    ModelDescriptor,
    OrganismModel,
    RealizationModel,
)
from ...ir import (
    CausalEdge,
    CausalIr,
    CausalNode,
    ConstructSpec,
    RealizationPackage,
    SimulationProgram,
    SimulationResult,
    TrajectoryPoint,
)
from ...ir import Authorization
from ...simulator.state import BiologicalState, GeneState, Quantity
from ...types import EvidenceLevel
from . import DOMAIN_VERSION, PACKAGE

if TYPE_CHECKING:
    from ...registry import ModelRegistry


class _SynthArtifact:
    def __init__(self, identity: str, symbol: str, organism: str):
        self.id = identity
        self.organism = organism
        self.taxon_id = 0
        self.kind = "REFERENCE_LOCUS"
        self.function = "conformance"
        self.tissue = "virtual"
        self.symbol = symbol
        self.sequence_ref = f"conformance://{identity}"
        self.sequence = None
        self.annotation = "TEST / NON-BIOLOGICAL / CONFORMANCE MODEL"
        self.provenance = "synthetic fixture; not a biological claim"
        self.version = DOMAIN_VERSION
        self.evidence = EvidenceLevel.THEORETICAL
        self.license = "test fixture"
        self.checksum = None
        self.retrieval = None
        self.drives = "switch"
        self.chrom = "virtual"
        self.start = 0
        self.end = 0
        self.strand = "."
        self.assembly = None


def _artifacts_a():
    return [_SynthArtifact("toa.SwitchA", "SwitchA", "TestOrganismA")]


def _artifacts_b():
    return [_SynthArtifact("tob.SwitchB", "SwitchB", "TestOrganismB")]


class _SwitchModel:
    """Minimal two-state executor used only for architecture conformance."""

    def __init__(self, model_id: str, on_name: str):
        self.id = model_id
        self.on_name = on_name

    def initialize(self, genotype, params):
        s = BiologicalState(time=0.0, step=0, stage="off")
        s.environment = {"temperature": 37.0}
        s.spatial = {"backend": "conformance_point", "n_bins": 1}
        s.fields = {"wnt": [0.0], "fgf": [0.0], "ra": [0.0], "cdx": [0.0], "hox": [0.0]}
        for g in genotype.genes:
            s.genes[g.identity] = GeneState(
                identity=g.identity, locus=g.locus.identity, kind=g.locus.kind, enabled=True,
                copy_number=g.copy_number, context="conformance",
            )
            s.rna[g.identity] = Quantity(0.0)
            s.protein[g.identity] = Quantity(0.0)
        s.molecular["wnt"] = Quantity(0.0)
        s.molecular["fgf"] = Quantity(0.0)
        s.molecular["ra"] = Quantity(0.0)
        s.molecular["cdx"] = Quantity(0.0)
        s.molecular["hox_posterior"] = Quantity(0.0)
        s.molecular["tail_identity"] = Quantity(0.0)
        s.molecular["energy"] = Quantity(1.0)
        s.molecular["switch"] = Quantity(0.0)
        s.anatomy = {
            "primary_axis": "indeterminate",
            "secondary_axis": "absent",
            "tail_count": 0,
            "head_identity": False,
            "conformance_state": "off",
        }
        s.flags = {"matured": False, "assertions_failed": [], "conformance": True}
        s.cells = []
        return s

    def transcribe(self, state, genotype, params):
        for g in genotype.genes:
            if g.identity in state.rna and state.genes.get(g.identity) and state.genes[g.identity].enabled:
                state.rna[g.identity].value = min(1.0, state.rna[g.identity].value + 0.25 * params.dt)
        return {g.identity: 0.25 * params.dt for g in genotype.genes}

    def translate(self, state, genotype, params):
        for g in genotype.genes:
            if g.identity in state.protein:
                state.protein[g.identity].value = min(1.0, state.protein[g.identity].value + 0.25 * params.dt)
        return {}

    def react(self, state, genotype, params):
        enabled = any(gs.enabled for gs in state.genes.values())
        cur = state.molecular["switch"].value
        state.molecular["switch"].value = min(1.0, cur + (0.4 if enabled else 0.0) * params.dt)

    def update_cells(self, state, params):
        return []

    def update_development(self, state):
        prev = state.stage
        if state.molecular["switch"].value >= 0.6:
            state.stage = "on"
            state.flags["matured"] = True
            state.anatomy["conformance_state"] = "on"
            state.anatomy["primary_axis"] = self.on_name
        else:
            state.stage = "off"
            state.anatomy["conformance_state"] = "off"
        return prev

    def plan_simulation(self, bio):
        return SimulationProgram(
            program_id=bio.program_id,
            entities=["switch"],
            state_variables=["switch"],
            equations=["dSwitch/dt = 0.4 if locus enabled"],
            transition_rules=["if switch >= 0.6 then stage=on"],
            spatial_model="point",
            temporal_model="explicit_euler",
            stochastic_model="deterministic_mean_field",
            parameters={"dt": 0.1, "t_end": 12.0},
            observations=["switch"],
            model_kind=self.id,
            resolution="conformance",
        )

    def compile_time_simulate(self, bio):
        traj = [
            TrajectoryPoint(time=float(i), axis_position=0.0, wnt=0, fgf=0, ra=0, cdx=0,
                            hox_posterior=0, tail_identity=0)
            for i in range(13)
        ]
        return SimulationResult(
            program_id=bio.program_id,
            trajectory=traj,
            terminal_phenotype_score=0.0,
            matured=True,
            notes=["TEST / NON-BIOLOGICAL / CONFORMANCE MODEL"],
        )

    def compile_time_simulate_plan(self, plan):
        return self.compile_time_simulate(type("B", (), {"program_id": plan.program_id})())

    def adjust_compile_preview(self, predicted_bundle, bio, sim):
        predicted_bundle.setdefault("anatomical", {})
        predicted_bundle["anatomical"]["conformance_state"] = "on"
        predicted_bundle["anatomical"]["primary_axis"] = self.on_name
        predicted_bundle.setdefault("temporal", {})["matured"] = True
        return predicted_bundle


def _causal(ir):
    return CausalIr(
        ir.program_id,
        [
            CausalNode("intent", "intent", "; ".join(f"{i.verb} {i.name}" for i in ir.intents)),
            CausalNode("switch", "state", "TEST / NON-BIOLOGICAL / CONFORMANCE MODEL"),
        ],
        [CausalEdge("intent", "switch", "requires", "THEORETICAL")],
    )


def _realize_factory(organism: str, artifacts_fn):
    def realize(cisc, micro, org_name, bio):
        constructs = []
        for a in artifacts_fn():
            constructs.append(ConstructSpec(
                artifact_id=a.id,
                role="module",
                organism=a.organism,
                kind=a.kind,
                sequence_ref=a.sequence_ref,
                topology="virtual",
                annotations=[a.annotation, a.provenance],
                evidence=a.evidence.value,
                sequence=None,
                chrom="virtual",
                start=0,
                end=0,
                strand=".",
                assembly=None,
                retrieval_digest=None,
                drives=a.drives,
                artifact_class="REFERENCE_LOCUS",
            ))
        return RealizationPackage(
            program_id=cisc.program_id,
            backend=micro.backend,
            construct_specification=constructs,
            required_capabilities=[],
            qc_requirements=[],
            verification_plan=[],
            provenance=["TEST / NON-BIOLOGICAL / CONFORMANCE MODEL"],
            safety_constraints=[],
            note="Synthetic conformance realization. No biological claim. No sequence invented.",
            authorization=Authorization(authorized=False, scope="specification_only"),
            assembly_plan={"format": "panini.assembly.v0", "steps": [], "note": "conformance"},
            sequence_verification_plan={"format": "panini.seqverify.v0", "acceptance": []},
            instrument_bindings=[],
            designed_constructs=[],
        )
    return realize


def register(registry: "ModelRegistry") -> None:
    def _org(oid, taxon, aliases, default_mid, genome_id):
        return OrganismModel(
            meta=ContractMeta(
                id=oid,
                version=DOMAIN_VERSION,
                kind="OrganismModel",
                capabilities=["conformance_switch"],
                validity_domain="TEST / NON-BIOLOGICAL / CONFORMANCE MODEL",
                evidence_status="THEORETICAL",
                label="TEST / NON-BIOLOGICAL / CONFORMANCE MODEL",
            ),
            taxon_name=taxon,
            taxon_id=None,
            aliases=aliases,
            default_model_id=default_mid,
            default_backend="virtual.conformance",
            genome_model_id=genome_id,
            knowledge_model_id=f"knowledge.{oid}",
            realization_model_id=f"realization.{oid}",
            evidence_model_id=f"evidence.{oid}",
            package=PACKAGE,
            scientific=False,
        )

    org_a = _org("organism.test_a", "TestOrganismA", ["TestOrganismA", "test_a"],
                 "test_organism_a_switch", "genome.test_a")
    org_b = _org("organism.test_b", "TestOrganismB", ["TestOrganismB", "test_b"],
                 "test_organism_b_switch", "genome.test_b")
    registry.register_organism(org_a)
    registry.register_organism(org_b)

    registry.register_genome(GenomeModel(
        meta=ContractMeta(id="genome.test_a", version=DOMAIN_VERSION, kind="GenomeModel",
                          validity_domain="TEST / NON-BIOLOGICAL / CONFORMANCE MODEL",
                          evidence_status="THEORETICAL"),
        organism_id=org_a.meta.id,
        artifacts_fn=_artifacts_a,
        modules_for_intent_fn=lambda primary, secondary=None: _artifacts_a(),
        verify_fn=lambda: [],
    ))
    registry.register_genome(GenomeModel(
        meta=ContractMeta(id="genome.test_b", version=DOMAIN_VERSION, kind="GenomeModel",
                          validity_domain="TEST / NON-BIOLOGICAL / CONFORMANCE MODEL",
                          evidence_status="THEORETICAL"),
        organism_id=org_b.meta.id,
        artifacts_fn=_artifacts_b,
        modules_for_intent_fn=lambda primary, secondary=None: _artifacts_b(),
        verify_fn=lambda: [],
    ))
    registry.register_knowledge(BiologicalKnowledgeModel(
        meta=ContractMeta(id="knowledge.organism.test_a", version=DOMAIN_VERSION, kind="BiologicalKnowledgeModel"),
        organism_id=org_a.meta.id, build_causal_fn=_causal,
    ))
    registry.register_knowledge(BiologicalKnowledgeModel(
        meta=ContractMeta(id="knowledge.organism.test_b", version=DOMAIN_VERSION, kind="BiologicalKnowledgeModel"),
        organism_id=org_b.meta.id, build_causal_fn=_causal,
    ))
    registry.register_realization(RealizationModel(
        meta=ContractMeta(id="realization.organism.test_a", version=DOMAIN_VERSION, kind="RealizationModel"),
        organism_id=org_a.meta.id, library_id="conformance.a",
    ))
    registry.register_realization(RealizationModel(
        meta=ContractMeta(id="realization.organism.test_b", version=DOMAIN_VERSION, kind="RealizationModel"),
        organism_id=org_b.meta.id, library_id="conformance.b",
    ))
    registry.register_evidence(EvidenceModel(
        meta=ContractMeta(id="evidence.organism.test_a", version=DOMAIN_VERSION, kind="EvidenceModel",
                          evidence_status="THEORETICAL"),
        evidence_version="none",
    ))
    registry.register_evidence(EvidenceModel(
        meta=ContractMeta(id="evidence.organism.test_b", version=DOMAIN_VERSION, kind="EvidenceModel",
                          evidence_status="THEORETICAL"),
        evidence_version="none",
    ))

    common = dict(
        package=PACKAGE,
        domain="conformance_switch",
        spatial_dimension=0,
        dimensions=0,
        fidelity="DT-0",
        capabilities={"cell_state", "developmental_stage", "conformance_switch"},
        implemented=True,
        stochastic=False,
        gpu=False,
        status="IMPLEMENTED",
        version=DOMAIN_VERSION,
        data_version="none",
        evidence_version="none",
        reference_assembly=None,
        default_for_organism=True,
        kind="TEST_CONFORMANCE",
        label="TEST / NON-BIOLOGICAL / CONFORMANCE MODEL",
    )
    registry.register_model(
        ModelDescriptor(id="test_organism_a_switch", organism="TestOrganismA",
                        organism_aliases=["TestOrganismA"], **common),
        lambda: _SwitchModel("test_organism_a_switch", "state_a"),
    )
    registry.register_model(
        ModelDescriptor(id="test_organism_b_switch", organism="TestOrganismB",
                        organism_aliases=["TestOrganismB"], **common),
        lambda: _SwitchModel("test_organism_b_switch", "state_b"),
    )
