# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Machine-readable CISC / RISC / sequence coverage report."""

from __future__ import annotations

from typing import Any, Dict, List

from ..isa_spec import all_specs
from ..ontology import CISC_OPCODES, RISC_OPCODES
from ..sequence_ir import EXECUTABLE_EDITS
from ..version import CISC_VERSION, COMPILER_VERSION, ISA_VERSION, RISC_VERSION


def cisc_coverage_report() -> Dict[str, Any]:
    specs = all_specs()
    buckets = {
        "SPECIFIED": [],
        "LOWERABLE": [],
        "EXECUTABLE": [],
        "MODEL_DEPENDENT": [],
        "UNIMPLEMENTED": [],
        "UNKNOWN": [],
    }
    lowerable = []
    sequence_realizable = []
    unimplemented_lowering = []
    for op in CISC_OPCODES:
        spec = specs.get(op)
        status = spec.implementation_status if spec else "UNKNOWN"
        buckets.setdefault(status, [])
        buckets[status].append(op)
        if spec and spec.risc_lowering.lowering_status == "AVAILABLE":
            lowerable.append(op)
        if spec and spec.risc_lowering.sequence_realizable:
            sequence_realizable.append(op)
        if spec and spec.risc_lowering.lowering_status == "UNAVAILABLE":
            unimplemented_lowering.append(op)
    report = {
        "type": "cisc_coverage_report",
        "version": "1.0.0",
        "compiler_version": COMPILER_VERSION,
        "isa_version": ISA_VERSION,
        "cisc_version": CISC_VERSION,
        "risc_version": RISC_VERSION,
        "cisc_catalogue_size": len(CISC_OPCODES),
        "risc_catalogue_size": len(RISC_OPCODES),
        "cisc_specified": len(specs),
        "by_implementation_status": {k: {"count": len(v), "opcodes": v} for k, v in buckets.items()},
        "lowerable_count": len(lowerable),
        "lowerable": lowerable,
        "sequence_realizable": sorted(sequence_realizable),
        "sequence_realizable_count": len(sequence_realizable),
        "executable_sequence_ops": sorted(EXECUTABLE_EDITS),
        "unimplemented_lowering": unimplemented_lowering,
        "unimplemented_lowering_count": len(unimplemented_lowering),
        "model_dependent_count": len(buckets.get("MODEL_DEPENDENT", [])),
        "unresolved_coverage": {
            "unimplemented_lowering": len(unimplemented_lowering),
            "unknown": len(buckets.get("UNKNOWN", [])),
        },
        "honesty": "EXECUTABLE means a justified computational path exists; it is not biological validation.",
    }
    return report
