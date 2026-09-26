# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Structured digital-twin maturity. A level label is not validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class MaturityProfile:
    level: str = "DT-3"
    molecular: bool = False
    cellular: bool = False
    developmental: bool = False
    physiological: bool = False
    whole_organism: bool = False
    calibrated: bool = False
    experimentally_validated: bool = False
    spatial: bool = False
    biochemical: bool = False
    notes: str = "DT level is an architectural capability label, not scientific validation."
    extras: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "molecular": self.molecular,
            "cellular": self.cellular,
            "developmental": self.developmental,
            "physiological": self.physiological,
            "whole_organism": self.whole_organism,
            "calibrated": self.calibrated,
            "experimentally_validated": self.experimentally_validated,
            "spatial": self.spatial,
            "biochemical": self.biochemical,
            "notes": self.notes,
            "extras": dict(self.extras),
        }


def profile_for_axial_twin() -> MaturityProfile:
    return MaturityProfile(level="DT-3", cellular=True, developmental=True, notes="reduced-order axial twin; DT-3 ≠ experimentally validated")


def profile_for_biochemical_fixture() -> MaturityProfile:
    return MaturityProfile(level="DT-1", molecular=True, biochemical=True, notes="synthetic kinetic fixture only")


def profile_for_spatial_dev() -> MaturityProfile:
    return MaturityProfile(level="DT-2", molecular=True, cellular=True, developmental=True, spatial=True, biochemical=True, notes="synthetic RD + cell pattern fixture")
