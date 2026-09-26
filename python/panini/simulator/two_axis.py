# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Compatibility façade. Multi-axis numerics live in a domain plugin."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from ..registry import get_registry


def _impl():
    org = get_registry().resolve_organism("Mouse")
    if org is None:
        raise RuntimeError("no domain plugin registered")
    return import_module(org.package + ".two_axis")


def __getattr__(name: str) -> Any:
    return getattr(_impl(), name)
