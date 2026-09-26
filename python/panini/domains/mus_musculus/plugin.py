# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Register the Mus musculus domain with the generic registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...contracts import (
    BiologicalKnowledgeModel,
    ContractMeta,
    EvidenceModel,
    GenomeModel,
    GeometryModel,
    ModelDescriptor,
    OrganismModel,
    PhenotypeModel,
    RealizationModel,
)
from . import (
    DATA_VERSION,
    DOMAIN_VERSION,
    EVIDENCE_VERSION,
    MODEL_VERSION_1D,
    MODEL_VERSION_2AXIS,
    PACKAGE,
)
from .execution import MouseAxial1D, MouseAxial2Axis, build_causal
from .knowledge import modules_for_intent, mouse_axial_library, verify_retrievals

if TYPE_CHECKING:
    from ...registry import ModelRegistry


def register(registry: "ModelRegistry") -> None:
    org = OrganismModel(
        meta=ContractMeta(
            id="organism.mus_musculus",
            version=DOMAIN_VERSION,
            kind="OrganismModel",
            capabilities=["developmental_axial_patterning"],
            inputs=["panini_program"],
            outputs=["organism_identity"],
            state_representation="taxon + default model ids",
            validity_domain="Mus musculus developmental examples shipped with this package",
            provenance=["MGI", "NCBI RefSeq", "GRCm39"],
            evidence_status="WIDELY_VALIDATED",
            label="Mus musculus domain plugin",
        ),
        taxon_name="Mus musculus",
        taxon_id=10090,
        aliases=["Mouse", "mouse", "mus", "mmu", "M. musculus"],
        default_model_id="mouse_axial_1d",
        default_backend="mammalian_cell.developmental",
        genome_model_id="genome.mus_musculus.grcm39_axial",
        knowledge_model_id="knowledge.mus_musculus.axial",
        development_model_id="development.mus_musculus.axial",
        phenotype_model_id="phenotype.mus_musculus.axial",
        geometry_model_id="geometry.mus_musculus.axial_1d",
        realization_model_id="realization.mus_musculus.axial",
        evidence_model_id="evidence.mus_musculus.axial",
        package=PACKAGE,
        scientific=True,
    )
    registry.register_organism(org)

    registry.register_genome(GenomeModel(
        meta=ContractMeta(
            id="genome.mus_musculus.grcm39_axial",
            version=DATA_VERSION,
            kind="GenomeModel",
            capabilities=["reference_locus_retrieval"],
            inputs=["intent_primary", "intent_secondary"],
            outputs=["reference_loci"],
            state_representation="GRCm39 coordinates + digest, no ATGC in the catalogue",
            validity_domain="five axial loci shipped as snapshots",
            provenance=["GRCm39", "GCF_000001635.27"],
            evidence_status="WIDELY_VALIDATED",
            label="Mus musculus GRCm39 axial locus pack",
        ),
        organism_id=org.meta.id,
        assembly="GRCm39",
        assembly_accession="GCF_000001635.27",
        data_version=DATA_VERSION,
        artifacts_fn=mouse_axial_library,
        modules_for_intent_fn=modules_for_intent,
        verify_fn=verify_retrievals,
    ))

    registry.register_knowledge(BiologicalKnowledgeModel(
        meta=ContractMeta(
            id="knowledge.mus_musculus.axial",
            version=DOMAIN_VERSION,
            kind="BiologicalKnowledgeModel",
            capabilities=["causal_prior"],
            inputs=["universal_bio_ir"],
            outputs=["causal_ir"],
            state_representation="Wnt/FGF/RA/Cdx/Hox prior graph",
            validity_domain="murine axial literature prior used by the shipped example",
            provenance=["domain plugin, not PANINI Core"],
            evidence_status="WIDELY_VALIDATED",
            label="Mus musculus axial causal prior",
        ),
        organism_id=org.meta.id,
        build_causal_fn=build_causal,
    ))

    registry.register_phenotype(PhenotypeModel(
        meta=ContractMeta(
            id="phenotype.mus_musculus.axial",
            version=DOMAIN_VERSION,
            kind="PhenotypeModel",
            capabilities=["anatomical_axis", "tail_count"],
            outputs=["anatomical", "molecular", "temporal"],
            state_representation="phenotype_projection of BiologicalState",
            validity_domain="reduced-order axial twin",
            evidence_status="COMPUTATIONALLY_SUPPORTED",
        ),
        organism_id=org.meta.id,
        properties=["primary_axis", "secondary_axis", "tail_count", "head_identity"],
    ))

    registry.register_geometry(GeometryModel(
        meta=ContractMeta(
            id="geometry.mus_musculus.axial_1d",
            version=DOMAIN_VERSION,
            kind="GeometryModel",
            capabilities=["1d_axis_bins"],
            state_representation="1d_axis_bins + optional two-basin origins",
            validity_domain="uncalibrated schematic geometry",
            evidence_status="COMPUTATIONALLY_SUPPORTED",
        ),
        spatial_dimension=1,
        topology="1d_axis",
    ))

    registry.register_evidence(EvidenceModel(
        meta=ContractMeta(
            id="evidence.mus_musculus.axial",
            version=EVIDENCE_VERSION,
            kind="EvidenceModel",
            evidence_status="WIDELY_VALIDATED",
            provenance=["MGI", "NCBI", "Ensembl GRCm39"],
        ),
        data_version=DATA_VERSION,
        evidence_version=EVIDENCE_VERSION,
        references=[
            "https://www.ncbi.nlm.nih.gov/assembly/GCF_000001635.27",
            "https://www.informatics.jax.org/",
        ],
    ))

    registry.register_realization(RealizationModel(
        meta=ContractMeta(
            id="realization.mus_musculus.axial",
            version=DOMAIN_VERSION,
            kind="RealizationModel",
            capabilities=["reference_locus_pack"],
            outputs=["construct_specification"],
            evidence_status="WIDELY_VALIDATED",
            label="reference-locus realization, specification only",
        ),
        organism_id=org.meta.id,
        library_id="mouse_axial_reference_loci@0.3.0",
        realize_note="Retrieved reference loci. Not a designed construct. Not a synthesis order.",
    ))

    caps_1d = {"morphogen_field", "cell_state", "developmental_stage"}
    caps_2 = set(caps_1d) | {"axis_initiation"}

    registry.register_model(
        ModelDescriptor(
            id="mouse_axial_1d",
            package=PACKAGE,
            organism="Mus musculus",
            organism_aliases=list(org.aliases),
            domain="developmental_axial_patterning",
            spatial_dimension=1,
            dimensions=1,
            fidelity="DT-3",
            capabilities=caps_1d,
            implemented=True,
            stochastic=False,
            gpu=False,
            status="IMPLEMENTED",
            version=MODEL_VERSION_1D,
            data_version=DATA_VERSION,
            evidence_version=EVIDENCE_VERSION,
            reference_assembly="GRCm39",
            default_for_organism=True,
            kind="BIOLOGICAL",
            label="Mus musculus 1-D axial twin",
        ),
        MouseAxial1D,
    )
    registry.register_model(
        ModelDescriptor(
            id="mouse_axial_2axis",
            package=PACKAGE,
            organism="Mus musculus",
            organism_aliases=list(org.aliases),
            domain="developmental_axial_patterning",
            spatial_dimension=2,
            dimensions=2,
            fidelity="DT-3",
            capabilities=caps_2,
            implemented=True,
            stochastic=False,
            gpu=False,
            status="IMPLEMENTED",
            version=MODEL_VERSION_2AXIS,
            data_version=DATA_VERSION,
            evidence_version=EVIDENCE_VERSION,
            reference_assembly="GRCm39",
            default_for_organism=False,
            kind="BIOLOGICAL",
            label="Mus musculus two-basin axial twin",
        ),
        MouseAxial2Axis,
    )
    registry.register_model(
        ModelDescriptor(
            id="mouse_axial_3d",
            package=PACKAGE,
            organism="Mus musculus",
            organism_aliases=list(org.aliases),
            domain="developmental_axial_patterning",
            spatial_dimension=3,
            dimensions=3,
            fidelity="DT-4",
            capabilities={"morphogen_field", "cell_mechanics"},
            implemented=False,
            stochastic=False,
            gpu=True,
            status="REGISTERED",
            version="0.0.0",
            data_version=DATA_VERSION,
            evidence_version=EVIDENCE_VERSION,
            reference_assembly="GRCm39",
            default_for_organism=False,
            kind="BIOLOGICAL",
            label="Mus musculus 3-D axial twin (not implemented in this task)",
        ),
        lambda: (_ for _ in ()).throw(RuntimeError("mouse_axial_3d is REGISTERED, not IMPLEMENTED")),
    )
