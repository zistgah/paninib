# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Compatibility shim. The live registry is panini.registry."""

from __future__ import annotations

from ..contracts import ModelDescriptor
from ..registry import REGISTRY, get_registry, resolve

__all__ = ["ModelDescriptor", "REGISTRY", "resolve", "get_registry"]
