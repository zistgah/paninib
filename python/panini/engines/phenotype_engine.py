# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Phenotype from multiscale state. Desired ≠ predicted ≠ observed."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..artifact_util import artifact_digest, provenance_block
from ..version import COMPILER_VERSION


@dataclass
class PhenotypeArtifact:
    kind: str
    source_layer: str
    values: Dict[str, Any]
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {"kind": self.kind, "source_layer": self.source_layer, "values": dict(self.values), "provenance": dict(self.provenance)}
        payload["digest"] = artifact_digest(payload)
        return payload


class PhenotypeEngine:
    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "PhenotypeEngine", "class": "ENGINE", "inputs": ["molecular", "cellular", "field", "developmental", "anatomical", "physiological"], "kinds": ["desired", "predicted", "observed", "validated"], "scientific_model": False}

    def from_molecular(self, molecular: Dict[str, Any], *, kind: str = "predicted") -> PhenotypeArtifact:
        c = float(molecular.get("C", 0.0) or 0.0)
        return self._mk(kind, "molecular", {"observable_C": c, "saturated": c > 0.5})

    def from_cells(self, cells: list, *, kind: str = "predicted") -> PhenotypeArtifact:
        n_diff = sum(1 for c in cells if (c.get("state") if isinstance(c, dict) else c.state) == "differentiated")
        return self._mk(kind, "cellular", {"n_cells": len(cells), "differentiated": n_diff})

    def from_field(self, field_state: Dict[str, Any], *, kind: str = "predicted") -> PhenotypeArtifact:
        return self._mk(kind, "field", {"u_max": field_state.get("u_max"), "pattern_proxy": field_state.get("u_max", 0)})

    def from_developmental(self, dev: Dict[str, Any], *, kind: str = "predicted") -> PhenotypeArtifact:
        anat = dev.get("anatomical_state") or dev.get("anatomical") or {}
        return self._mk(kind, "developmental", dict(anat))

    def from_anatomical(self, anatomical: Dict[str, Any], *, kind: str = "predicted") -> PhenotypeArtifact:
        return self._mk(kind, "anatomical", dict(anatomical))

    def from_physiological(self, phys: Dict[str, Any], *, kind: str = "predicted") -> PhenotypeArtifact:
        return self._mk(kind, "physiological", dict(phys))

    def desired(self, values: Dict[str, Any]) -> PhenotypeArtifact:
        return self._mk("desired", "intent", dict(values))

    def observed(self, values: Dict[str, Any], source: str = "SIMULATION") -> PhenotypeArtifact:
        return self._mk("observed", source.lower(), dict(values))

    def _mk(self, kind: str, layer: str, values: Dict[str, Any]) -> PhenotypeArtifact:
        if kind not in {"desired", "predicted", "observed", "validated"}:
            raise ValueError(kind)
        return PhenotypeArtifact(kind=kind, source_layer=layer, values=values, provenance=provenance_block(layer="phenotype." + kind, compiler_version=COMPILER_VERSION, provider="panini.engines.phenotype", model_id="phenotype.v10", model_version="1.0.0"))

    def validated(self, values: Dict[str, Any], source: str = "VALIDATION") -> PhenotypeArtifact:
        return self._mk("validated", source.lower(), dict(values))

    def residual(self, left: PhenotypeArtifact, right: PhenotypeArtifact, *, pair: str) -> Dict[str, Any]:
        keys = set(left.values) | set(right.values)
        numeric: Dict[str, Any] = {}
        other: Dict[str, Any] = {}
        for k in keys:
            a, b = left.values.get(k), right.values.get(k)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                numeric[k] = {"left": a, "right": b, "delta": b - a}
            else:
                other[k] = {"left": a, "right": b, "equal": a == b}
        payload = {
            "pair": pair,
            "left_kind": left.kind,
            "right_kind": right.kind,
            "numeric": numeric,
            "typed": other,
            "note": "residuals do not promote predicted to observed or observed to validated",
        }
        payload["digest"] = artifact_digest(payload)
        return payload

    def bundle(self, desired=None, predicted=None, observed=None, validated=None) -> Dict[str, Any]:
        d = desired if isinstance(desired, PhenotypeArtifact) else self.desired(desired or {})
        payload = {
            "desired": d.to_dict(),
            "predicted": predicted.to_dict() if predicted else None,
            "observed": observed.to_dict() if observed else None,
            "validated": validated.to_dict() if validated else None,
            "residuals": {},
            "separation": {
                "predicted_is_not_observed": observed is None or (predicted is not None and observed.kind != predicted.kind),
                "desired_is_not_predicted": True,
                "observed_is_not_validated": validated is None,
            },
        }
        if predicted is not None:
            payload["residuals"]["desired_minus_predicted"] = self.residual(d, predicted, pair="desired-predicted")
        if predicted is not None and observed is not None:
            payload["residuals"]["predicted_minus_observed"] = self.residual(predicted, observed, pair="predicted-observed")
        if observed is not None:
            payload["residuals"]["desired_minus_observed"] = self.residual(d, observed, pair="desired-observed")
        payload["digest"] = artifact_digest(payload)
        return payload
