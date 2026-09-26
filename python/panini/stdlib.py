# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Domain-neutral standard-library façade.

Catalogue entries live in registered GenomeModel plugins. This module
does not own species data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .registry import get_registry
from .types import EvidenceLevel


# Re-exported so existing callers keep a stable import path. The dataclass
# definition used by the shipped mouse catalogue lives in the domain package;
# this alias is filled lazily.
Artifact = None  # set below after optional domain import for type checkers


def _all_artifacts():
    out = []
    reg = get_registry()
    seen = set()
    for org in {id(o): o for o in reg._organisms.values()}.values():
        gm = reg.genome_for_organism(org.taxon_name)
        if gm and gm.artifacts_fn:
            key = gm.meta.id
            if key in seen:
                continue
            seen.add(key)
            out.extend(gm.artifacts_fn())
    return out


@dataclass
class SearchQuery:
    organism: Optional[str] = None
    function: Optional[str] = None
    tissue: Optional[str] = None
    min_evidence: Optional[EvidenceLevel] = None


def _organism_match(query: str, artifact) -> bool:
    q = query.lower().strip()
    name = str(getattr(artifact, "organism", "")).lower()
    taxon = getattr(artifact, "taxon_id", None)
    if q == name or (taxon is not None and q == str(taxon)):
        return True
    org = get_registry().resolve_organism(query)
    if org is None:
        return False
    if taxon is not None and org.taxon_id is not None and int(taxon) == int(org.taxon_id):
        return True
    aliases = {org.taxon_name.lower(), *[a.lower() for a in org.aliases], org.meta.id.lower()}
    return name in aliases


def find(q: SearchQuery) -> List:
    out = []
    for a in _all_artifacts():
        if q.organism and not _organism_match(q.organism, a):
            continue
        if q.function and getattr(a, "function", None) != q.function:
            continue
        if q.tissue and getattr(a, "tissue", None) != q.tissue:
            continue
        if q.min_evidence and getattr(a, "evidence", None) is not None:
            if a.evidence.rank < q.min_evidence.rank:
                continue
        out.append(a)
    return out


def verify_retrievals() -> List[str]:
    errors = []
    reg = get_registry()
    seen = set()
    for org in {id(o): o for o in reg._organisms.values()}.values():
        gm = reg.genome_for_organism(org.taxon_name)
        if gm and gm.verify_fn and gm.meta.id not in seen:
            seen.add(gm.meta.id)
            errors.extend(gm.verify_fn() or [])
    return errors


def modules_for_intent(primary: str, secondary: Optional[str] = None, organism: Optional[str] = None) -> List:
    if organism:
        gm = get_registry().genome_for_organism(organism)
        if gm and gm.modules_for_intent_fn:
            return gm.modules_for_intent_fn(primary, secondary)
    # Compatibility: if no organism given, use every registered composer that
    # accepts the intent. Prefer a genome that actually returns modules.
    hits = []
    for org in {id(o): o for o in get_registry()._organisms.values()}.values():
        gm = get_registry().genome_for_organism(org.taxon_name)
        if gm and gm.modules_for_intent_fn:
            got = gm.modules_for_intent_fn(primary, secondary)
            if got:
                return list(got)
            hits = got
    return list(hits)


def mouse_axial_library():
    """Compatibility wrapper. Implementation lives in the mouse domain package."""
    gm = get_registry().genome_for_organism("Mouse")
    if gm and gm.artifacts_fn:
        return gm.artifacts_fn()
    return []
