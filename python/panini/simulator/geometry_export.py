# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Mesh export for visualization, animation frames, and 3-D print files.

Units are uncalibrated model units. Not millimetres unless a calibration
record is attached — none is, in v0.4.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

Vertex = Tuple[float, float, float]


def _capsule(origin: Tuple[float, float, float], direction: Tuple[float, float, float],
             length: float, radius: float, rings: int = 8, segs: int = 12) -> tuple[List[Vertex], List[Tuple[int, int, int]]]:
    ox, oy, oz = origin
    dx, dy, dz = direction
    norm = math.sqrt(dx*dx + dy*dy + dz*dz) or 1.0
    dx, dy, dz = dx/norm, dy/norm, dz/norm
    # orthonormal basis
    up = (0.0, 1.0, 0.0) if abs(dy) < 0.9 else (1.0, 0.0, 0.0)
    cx = dy*up[2] - dz*up[1]
    cy = dz*up[0] - dx*up[2]
    cz = dx*up[1] - dy*up[0]
    cl = math.sqrt(cx*cx+cy*cy+cz*cz) or 1.0
    cx, cy, cz = cx/cl, cy/cl, cz/cl
    bx, by, bz = dy*cz - dz*cy, dz*cx - dx*cz, dx*cy - dy*cx
    verts: List[Vertex] = []
    faces: List[Tuple[int, int, int]] = []
    for i in range(rings + 1):
        t = i / rings
        z = t * length
        r = radius * (1.0 - 0.45 * t)
        for j in range(segs):
            ang = 2 * math.pi * j / segs
            px = ox + dx*z + r*(cx*math.cos(ang) + bx*math.sin(ang))
            py = oy + dy*z + r*(cy*math.cos(ang) + by*math.sin(ang))
            pz = oz + dz*z + r*(cz*math.cos(ang) + bz*math.sin(ang))
            verts.append((px, py, pz))
    for i in range(rings):
        for j in range(segs):
            a = i * segs + j
            b = i * segs + (j + 1) % segs
            c = (i + 1) * segs + j
            d = (i + 1) * segs + (j + 1) % segs
            faces.append((a, c, b))
            faces.append((b, c, d))
    return verts, faces


def mesh_from_phenotype(phenotype: Dict[str, Any]) -> tuple[List[Vertex], List[Tuple[int, int, int]], List[str]]:
    axes = phenotype.get("axes") or []
    if not axes:
        n = int(phenotype.get("anatomical", {}).get("tail_count") or 0)
        if n >= 1:
            axes = [{"origin": [0.7, 0.0, 0.0], "direction": [0.0, 0.0, 1.0], "length": 0.8, "axis_type": "tail"}]
        if n >= 2:
            axes.append({"origin": [0.7, 0.25, 0.0], "direction": [0.0, 0.0, 1.0], "length": 0.8, "axis_type": "tail"})
    verts: List[Vertex] = []
    faces: List[Tuple[int, int, int]] = []
    labels: List[str] = []
    # body ellipsoid as a coarse capsule along x
    bv, bf = _capsule((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 0.7, 0.18, rings=6, segs=10)
    faces.extend((a+len(verts), b+len(verts), c+len(verts)) for a, b, c in bf)
    verts.extend(bv)
    labels.append("body")
    for ax in axes:
        origin = tuple(ax.get("origin") or (0.7, 0.0, 0.0))  # type: ignore
        direction = tuple(ax.get("direction") or (0.0, 0.0, 1.0))  # type: ignore
        length = float(ax.get("length") or 0.8)
        av, af = _capsule(origin, direction, max(0.15, length), 0.07)
        base = len(verts)
        faces.extend((a+base, b+base, c+base) for a, b, c in af)
        verts.extend(av)
        labels.append(ax.get("identity") or ax.get("axis_type") or "axis")
    return verts, faces, labels


def write_obj(path: Path, verts: List[Vertex], faces: List[Tuple[int, int, int]]) -> None:
    lines = ["# Copyright © 1993-2026 Abhishek Choudhary. All rights reserved.", "# PANINI phenotype mesh, uncalibrated units"]
    for x, y, z in verts:
        lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")
    for a, b, c in faces:
        lines.append(f"f {a+1} {b+1} {c+1}")
    path.write_text("\n".join(lines) + "\n")


def write_ply(path: Path, verts: List[Vertex], faces: List[Tuple[int, int, int]]) -> None:
    lines = [
        "ply", "format ascii 1.0",
        "comment Copyright 1993-2026 Abhishek Choudhary",
        f"element vertex {len(verts)}",
        "property float x", "property float y", "property float z",
        f"element face {len(faces)}",
        "property list uchar int vertex_indices",
        "end_header",
    ]
    for x, y, z in verts:
        lines.append(f"{x:.6f} {y:.6f} {z:.6f}")
    for a, b, c in faces:
        lines.append(f"3 {a} {b} {c}")
    path.write_text("\n".join(lines) + "\n")


def write_stl(path: Path, verts: List[Vertex], faces: List[Tuple[int, int, int]]) -> None:
    lines = ["solid panini_phenotype"]
    for a, b, c in faces:
        ax, ay, az = verts[a]
        bx, by, bz = verts[b]
        cx, cy, cz = verts[c]
        ux, uy, uz = bx-ax, by-ay, bz-az
        vx, vy, vz = cx-ax, cy-ay, cz-az
        nx = uy*vz - uz*vy
        ny = uz*vx - ux*vz
        nz = ux*vy - uy*vx
        nrm = math.sqrt(nx*nx+ny*ny+nz*nz) or 1.0
        lines.append(f"  facet normal {nx/nrm:.6f} {ny/nrm:.6f} {nz/nrm:.6f}")
        lines.append("    outer loop")
        lines.append(f"      vertex {ax:.6f} {ay:.6f} {az:.6f}")
        lines.append(f"      vertex {bx:.6f} {by:.6f} {bz:.6f}")
        lines.append(f"      vertex {cx:.6f} {cy:.6f} {cz:.6f}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append("endsolid panini_phenotype")
    path.write_text("\n".join(lines) + "\n")


def export_all(out: Path, phenotype: Dict[str, Any]) -> Dict[str, str]:
    out.mkdir(parents=True, exist_ok=True)
    verts, faces, labels = mesh_from_phenotype(phenotype)
    write_obj(out / "phenotype.obj", verts, faces)
    write_ply(out / "phenotype.ply", verts, faces)
    write_stl(out / "phenotype.stl", verts, faces)
    (out / "phenotype_cloud.json").write_text(json.dumps({
        "copyright": "Copyright © 1993-2026 Abhishek Choudhary. All rights reserved.",
        "units": "uncalibrated",
        "labels": labels,
        "vertices": verts,
        "n_faces": len(faces),
        "has_nonzero_z": any(abs(v[2]) > 1e-9 for v in verts),
        "has_nonzero_y": any(abs(v[1]) > 1e-9 for v in verts),
    }, indent=2))
    return {
        "obj": str(out / "phenotype.obj"),
        "ply": str(out / "phenotype.ply"),
        "stl": str(out / "phenotype.stl"),
        "cloud": str(out / "phenotype_cloud.json"),
        "vertices": str(len(verts)),
        "faces": str(len(faces)),
    }
