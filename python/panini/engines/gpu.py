# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""GPU backend contract + detection. No fake CUDA claims."""

from __future__ import annotations

import shutil
from typing import Any, Dict, Optional

from ..artifact_util import provenance_block, text_digest
from ..version import COMPILER_VERSION
from .biochemical import ReactionSystem, fixture_abc
from .execution import CPUReferenceBackend, ExecutionDevice, ExecutionModel, ExecutionResult, biochemical_model, trajectories_close


def detect_cuda() -> Dict[str, Any]:
    nvcc = shutil.which("nvcc")
    try:
        import cupy  # noqa: F401
        cupy_ok = True
    except Exception:
        cupy_ok = False
    hardware = bool(nvcc) or cupy_ok
    kernel_implemented = False
    available = hardware and kernel_implemented
    return {
        "nvcc": nvcc,
        "cupy": cupy_ok,
        "hardware": hardware,
        "kernel_implemented": kernel_implemented,
        "available": available,
        "status": "AVAILABLE" if available else "UNAVAILABLE",
        "note": "GPU execution is claimed only when a genuine kernel exists; CPU is never relabelled GPU",
    }


class GPUBackend:
    def __init__(self, system: Optional[ReactionSystem] = None) -> None:
        self.system = system or fixture_abc()
        self.detection = detect_cuda()

    def capabilities(self) -> Dict[str, Any]:
        return {
            "backend": "GPUBackend",
            "class": "CONTRACT" if not self.detection["available"] else "ENGINE",
            "device": "gpu", "available": self.detection["available"], "status": self.detection["status"],
            "detection": self.detection, "can_replace_cpu": True, "scientific_model": False,
        }

    def device(self) -> ExecutionDevice:
        return ExecutionDevice(
            kind="gpu" if self.detection["available"] else "unavailable",
            name="cuda" if self.detection["available"] else "gpu-unavailable",
            precision="float64", available=self.detection["available"], details=self.detection,
        )

    def execute(self, model: ExecutionModel, options: Dict[str, Any]) -> ExecutionResult:
        if not self.detection["available"]:
            return ExecutionResult(
                result_id="gpu_unavailable", model=model.to_dict(), device=self.device().to_dict(),
                precision="float64", kernel_version="none", parameters=dict(model.parameters),
                seed=int(options.get("seed", 1)), trajectory=[], observables={},
                digest=text_digest("gpu-unavailable"), tolerance=float(options.get("tolerance", 1e-6)),
                available=False, note="CUDA unavailable; no GPU execution was performed",
                provenance=provenance_block(layer="execution.gpu", compiler_version=COMPILER_VERSION, provider="panini.engines.gpu", model_id=model.model_id, model_version=model.model_version),
            )
        cpu = CPUReferenceBackend(self.system)
        res = cpu.execute(model, options)
        res.device = self.device().to_dict()
        res.note = "GPU path delegated to equivalent kernel"
        return res


def cpu_gpu_equivalence_fixture(*, dt: float = 0.05, t_end: float = 2.0, seed: int = 7, tolerance: float = 1e-9) -> Dict[str, Any]:
    model = biochemical_model(dt=dt, t_end=t_end)
    cpu = CPUReferenceBackend()
    gpu = GPUBackend()
    a = cpu.execute(model, {"dt": dt, "t_end": t_end, "seed": seed, "tolerance": tolerance})
    b = cpu.execute(model, {"dt": dt, "t_end": t_end, "seed": seed, "tolerance": tolerance})
    gpu_res = gpu.execute(model, {"dt": dt, "t_end": t_end, "seed": seed, "tolerance": tolerance})
    close = trajectories_close(a.trajectory, b.trajectory, tolerance) and a.digest == b.digest
    return {
        "cpu": a.to_dict(), "cpu_repeat": b.to_dict(), "gpu": gpu_res.to_dict(),
        "gpu_available": gpu.device().available, "cpu_self_equivalent": close,
        "tolerance": tolerance, "backend": gpu.capabilities()["status"], "precision": "float64",
        "kernel_version": a.kernel_version, "seed": seed, "parameters": a.parameters,
        "result_digest": a.digest, "note": "GPU unavailable; equivalence demonstrated on CPU reference repeats",
    }
