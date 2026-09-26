# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Generic model / domain registry and resolver.

The compiler core asks: which registered model can execute this program?
It never contains a species-named branch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .contracts import (
    BiologicalKnowledgeModel,
    EvidenceModel,
    ExecutionModel,
    GenomeModel,
    GeometryModel,
    ModelDescriptor,
    OrganismModel,
    PhenotypeModel,
    RealizationModel,
)


@dataclass
class _Entry:
    descriptor: ModelDescriptor
    factory: Optional[Callable[[], ExecutionModel]] = None
    instance: Optional[ExecutionModel] = None


class ModelRegistry:
    def __init__(self) -> None:
        self._models: Dict[str, _Entry] = {}
        self._organisms: Dict[str, OrganismModel] = {}
        self._genomes: Dict[str, GenomeModel] = {}
        self._knowledge: Dict[str, BiologicalKnowledgeModel] = {}
        self._phenotypes: Dict[str, PhenotypeModel] = {}
        self._geometry: Dict[str, GeometryModel] = {}
        self._evidence: Dict[str, EvidenceModel] = {}
        self._realization: Dict[str, RealizationModel] = {}
        self._bootstrapped = False

    def register_model(self, descriptor: ModelDescriptor, factory: Callable[[], ExecutionModel]) -> None:
        self._models[descriptor.id] = _Entry(descriptor=descriptor, factory=factory)

    def register_organism(self, model: OrganismModel) -> None:
        self._organisms[model.meta.id] = model
        for alias in [model.taxon_name, *model.aliases, model.meta.id]:
            self._organisms[alias.lower()] = model

    def register_genome(self, model: GenomeModel) -> None:
        self._genomes[model.meta.id] = model

    def register_knowledge(self, model: BiologicalKnowledgeModel) -> None:
        self._knowledge[model.meta.id] = model

    def register_phenotype(self, model: PhenotypeModel) -> None:
        self._phenotypes[model.meta.id] = model

    def register_geometry(self, model: GeometryModel) -> None:
        self._geometry[model.meta.id] = model

    def register_evidence(self, model: EvidenceModel) -> None:
        self._evidence[model.meta.id] = model

    def register_realization(self, model: RealizationModel) -> None:
        self._realization[model.meta.id] = model

    def get_descriptor(self, model_id: str) -> ModelDescriptor:
        if model_id not in self._models:
            raise KeyError(model_id)
        return self._models[model_id].descriptor

    def get_execution(self, model_id: str) -> ExecutionModel:
        if model_id not in self._models:
            raise KeyError(model_id)
        entry = self._models[model_id]
        desc = entry.descriptor
        if not desc.implemented:
            raise RuntimeError(f"model {model_id} is {desc.status}, not IMPLEMENTED")
        if entry.instance is None:
            if entry.factory is None:
                raise RuntimeError(f"model {model_id} has no factory")
            entry.instance = entry.factory()
        return entry.instance

    def list_models(self) -> List[ModelDescriptor]:
        seen = []
        out = []
        for e in self._models.values():
            if e.descriptor.id in seen:
                continue
            seen.append(e.descriptor.id)
            out.append(e.descriptor)
        return out

    def resolve_organism(self, name: str) -> Optional[OrganismModel]:
        if not name:
            return None
        key = name.strip().lower()
        if key in self._organisms:
            return self._organisms[key]
        for org in {id(o): o for o in self._organisms.values()}.values():
            aliases = [a.lower() for a in org.aliases] + [org.taxon_name.lower(), org.meta.id.lower()]
            if key in aliases or any(key in a or a in key for a in aliases):
                return org
        return None

    def resolve(self, organism: str, required_capabilities: List[str],
                spatial_dimensions_min: int = 1, requested: Optional[str] = None
                ) -> Tuple[ModelDescriptor, str]:
        """Capability resolution. Explicit request wins. Otherwise the
        organism plugin's declared default is used — never a core species branch.
        """
        if requested:
            if requested not in self._models:
                raise KeyError(requested)
            desc = self._models[requested].descriptor
            if not desc.implemented:
                raise RuntimeError(f"model {requested} is {desc.status}")
            return desc, f"explicit request {requested}"

        org = self.resolve_organism(organism)
        if org and org.default_model_id and org.default_model_id in self._models:
            desc = self._models[org.default_model_id].descriptor
            reason = f"organism default {desc.id}"
            if spatial_dimensions_min > desc.spatial_dimension:
                reason = (
                    f"organism default {desc.id}; a higher-dimension registered "
                    f"model exists but was not selected"
                )
            return desc, reason

        candidates = []
        for desc in self.list_models():
            if not desc.implemented:
                continue
            if desc.spatial_dimension < spatial_dimensions_min:
                continue
            if required_capabilities and not set(required_capabilities).issubset(desc.capabilities):
                continue
            candidates.append(desc)
        if candidates:
            candidates.sort(key=lambda d: (d.spatial_dimension, d.id))
            desc = candidates[0]
            return desc, f"capability match {desc.id}"
        raise RuntimeError(
            f"no implemented model registered for organism={organism!r} "
            f"capabilities={required_capabilities}"
        )

    def genome_for_organism(self, organism: str) -> Optional[GenomeModel]:
        org = self.resolve_organism(organism)
        if org and org.genome_model_id and org.genome_model_id in self._genomes:
            return self._genomes[org.genome_model_id]
        return None

    def knowledge_for_organism(self, organism: str) -> Optional[BiologicalKnowledgeModel]:
        org = self.resolve_organism(organism)
        if org and org.knowledge_model_id and org.knowledge_model_id in self._knowledge:
            return self._knowledge[org.knowledge_model_id]
        return None

    def realization_for_organism(self, organism: str) -> Optional[RealizationModel]:
        org = self.resolve_organism(organism)
        if org and org.realization_model_id and org.realization_model_id in self._realization:
            return self._realization[org.realization_model_id]
        return None

    def evidence_for_organism(self, organism: str) -> Optional[EvidenceModel]:
        org = self.resolve_organism(organism)
        if org and org.evidence_model_id and org.evidence_model_id in self._evidence:
            return self._evidence[org.evidence_model_id]
        return None


_REGISTRY = ModelRegistry()


def get_registry() -> ModelRegistry:
    ensure_plugins()
    return _REGISTRY


def ensure_plugins() -> None:
    if _REGISTRY._bootstrapped:
        return
    _REGISTRY._bootstrapped = True
    from .domains import load_plugins
    load_plugins(_REGISTRY)


# Compatibility view used by v0.4 callers that imported REGISTRY as a dict.
class _RegistryMap(dict):
    def __getitem__(self, key: str) -> ModelDescriptor:
        return get_registry().get_descriptor(key)

    def __contains__(self, key: object) -> bool:
        try:
            get_registry().get_descriptor(str(key))
            return True
        except KeyError:
            return False

    def keys(self):
        return [d.id for d in get_registry().list_models()]


REGISTRY = _RegistryMap()


def resolve(model_id: str) -> ModelDescriptor:
    desc = get_registry().get_descriptor(model_id)
    if not desc.implemented:
        raise RuntimeError(f"model {model_id} is {desc.status}, not IMPLEMENTED")
    return desc
