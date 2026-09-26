# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""SBOL / external representation export boundary.

Complete SBOL3 is out of scope. This adapter defines the interface,
emits a minimal valid fixture document, and records unsupported fields.
"""

from __future__ import annotations

from typing import Any, Dict, List, Protocol

from .artifact_util import artifact_digest, provenance_block
from .version import COMPILER_VERSION


UNSUPPORTED_SBOL_FIELDS = (
    "CombinatorialDerivation",
    "Implementation",
    "Attachment",
    "ExperimentalData",
    "Measure",
)


class RealizationExporter(Protocol):
    def format_name(self) -> str: ...
    def export(self, realization: Dict[str, Any]) -> Dict[str, Any]: ...
    def unsupported_fields(self) -> List[str]: ...


class MinimalSbolAdapter:
    def format_name(self) -> str:
        return "sbol3-minimal-fixture"

    def unsupported_fields(self) -> List[str]:
        return list(UNSUPPORTED_SBOL_FIELDS)

    def export(self, realization: Dict[str, Any]) -> Dict[str, Any]:
        components = []
        for i, construct in enumerate(realization.get("constructs") or [], start=1):
            components.append({
                "identity": f"https://panini.local/sbol/{realization.get('realization_id')}/c{i}",
                "displayId": construct.get("construct_id") or f"component_{i}",
                "type": "https://identifiers.org/SBO:0000251",
                "role": construct.get("role") or "unspecified",
                "provenance_ref": realization.get("realization_id"),
            })
        doc = {
            "format": "SBOL3",
            "completeness": "minimal_fixture",
            "unsupported_fields": self.unsupported_fields(),
            "component": components,
            "realization_id": realization.get("realization_id"),
            "design_id": realization.get("design_id"),
            "status": realization.get("status"),
            "provenance": provenance_block(
                layer="sbol_export",
                compiler_version=COMPILER_VERSION,
                provider="panini.sbol.minimal",
            ),
            "note": "Minimal valid fixture for interchange. Not a complete SBOL document.",
        }
        doc["digest"] = artifact_digest(doc)
        return doc
