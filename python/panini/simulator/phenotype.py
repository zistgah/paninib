"""Digital phenotype: typed projection Φ = H(S), never a JPEG."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .state import BiologicalState


@dataclass
class PhenotypeGeometry:
    kind: str
    topology: str
    point_cloud: List[Dict[str, Any]] = field(default_factory=list)
    mesh: List[Dict[str, Any]] = field(default_factory=list)
    voxel_field: List[Any] = field(default_factory=list)
    skeleton: List[Any] = field(default_factory=list)
    implicit_surface: Dict[str, Any] = field(default_factory=dict)
    parametric_model: Dict[str, Any] = field(default_factory=dict)
    annotations: List[str] = field(default_factory=list)


def geometry_from_state(state: BiologicalState) -> PhenotypeGeometry:
    points = []
    n = len(state.fields.get("hox", [])) or 11
    hox = state.fields.get("hox") or [0.0] * n
    tail = state.molecular.get("tail_identity")
    score = tail.value if tail else 0.0
    for i in range(n):
        x = i / max(n - 1, 1)
        label = "posterior" if x > 0.66 else "anterior" if x < 0.33 else "trunk"
        points.append({
            "x": x, "y": 0.0, "z": 0.0,
            "label": label,
            "state": f"hox={hox[i]:.3f}",
            "time": state.time,
            "confidence": 0.65,
        })
    return PhenotypeGeometry(
        kind="PointCloud",
        topology="1d_axis",
        point_cloud=points,
        parametric_model={
            "axis_length": 1.0,
            "tail_identity": score,
            "stage": state.stage,
        },
        annotations=[
            "geometry is a projection of biological state, not a rendered fake image",
        ],
    )


def phenotype_bundle(state: BiologicalState) -> Dict[str, Any]:
    proj = state.phenotype_projection()
    geom = geometry_from_state(state)
    return {
        "molecular": proj["molecular"],
        "cellular": proj["cellular"],
        "tissue": proj["tissue"],
        "anatomical": proj["anatomical"],
        "physiological": {"energy": state.molecular.get("energy").value if state.molecular.get("energy") else None},
        "behavioural": state.behavior,
        "temporal": proj["temporal"],
        "geometric": {
            "kind": geom.kind,
            "topology": geom.topology,
            "point_cloud": geom.point_cloud,
            "parametric_model": geom.parametric_model,
        },
        "observational": state.observations,
    }
