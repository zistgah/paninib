# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""First-class coverage with separated classes."""

from __future__ import annotations

from typing import Any, Dict, Iterable

CLASS_MAP = {"RESOLVED": "deterministically_resolved", "MODEL_DERIVED": "model_derived", "USER_ASSERTED": "user_asserted", "UNRESOLVED": "unresolved"}


def coverage_from_nodes(nodes: Iterable[Any]) -> Dict[str, Any]:
    total = 0
    classes = {"deterministically_resolved": 0, "model_derived": 0, "user_asserted": 0, "unresolved": 0, "validated": 0, "other": 0}
    for n in nodes:
        total += 1
        status = getattr(n, "status", None)
        if status is None and isinstance(n, dict):
            status = n.get("status")
        status = str(status or "UNRESOLVED")
        classes[CLASS_MAP.get(status, "other")] += 1
        validation = getattr(n, "validation_status", None)
        if validation is None and isinstance(n, dict):
            validation = n.get("validation_status")
        if validation in {"VERIFIED", "EXPERIMENTALLY_VALIDATED", "SUPPORTED"}:
            classes["validated"] += 1
    resolved = classes["deterministically_resolved"] + classes["model_derived"] + classes["user_asserted"]
    return {"total_declared": total, "resolved_declared": resolved, "coverage_ratio": (resolved / total) if total else 0.0, "classes": classes, "note": "do not collapse classes into one misleading percentage"}


def coverage_from_resolution_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    br = payload.get("biological_resolution") or {}
    cons = br.get("constraints") or payload.get("constraints") or []
    return coverage_from_nodes(cons)
