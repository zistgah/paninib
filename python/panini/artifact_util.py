# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Digest and provenance helpers shared by v0.8 artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical(obj: Any) -> Any:
    if is_dataclass(obj):
        return {k: canonical(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): canonical(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [canonical(v) for v in obj]
    return obj


def artifact_digest(obj: Any) -> str:
    blob = json.dumps(canonical(obj), sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(blob).hexdigest()


def text_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def provenance_block(
    *,
    layer: str,
    compiler_version: str,
    provider: str = "",
    model_id: str = "",
    model_version: str = "",
    reference_version: str = "",
    parameters: Dict[str, Any] | None = None,
    random_seed: Any = None,
    parent_digests: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    block = {
        "layer": layer,
        "compiler_version": compiler_version,
        "provider": provider,
        "model_id": model_id,
        "model_version": model_version,
        "reference_version": reference_version,
        "parameters": parameters or {},
        "random_seed": random_seed,
        "parent_digests": parent_digests or {},
        "timestamp": utc_now(),
    }
    block["digest"] = artifact_digest({k: v for k, v in block.items() if k != "digest"})
    return block
