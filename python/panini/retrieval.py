# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Retrieval façade. Sequence snapshots belong to a domain GenomeModel."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .registry import get_registry


def _domain_retrieval():
    org = get_registry().resolve_organism("Mouse")
    if org is None or not org.package:
        raise RuntimeError("no domain package registered for retrieval")
    return import_module(org.package + ".retrieval")


def __getattr__(name: str) -> Any:
    return getattr(_domain_retrieval(), name)
