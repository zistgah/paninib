# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Biological domain plugins. Core discovers packages; it does not name a species."""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import ModelRegistry


def load_plugins(registry: "ModelRegistry") -> None:
    for module_info in pkgutil.iter_modules(__path__):
        try:
            plugin = importlib.import_module(f"{__name__}.{module_info.name}.plugin")
        except Exception:
            continue
        register = getattr(plugin, "register", None)
        if callable(register):
            register(registry)
