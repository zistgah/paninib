"""PANINI genetic compiler platform.

Intent ≠ Genetic CISC ≠ Microcode ≠ ATGC ≠ Physical execution
"""

from .pipeline import compile_source, CompileOptions, CompileResult
from .simulator.api import Simulator
from .debugger.session import DebugSession

from .version import COMPILER_NAME, COMPILER_VERSION

__all__ = [
    "compile_source",
    "CompileOptions",
    "CompileResult",
    "Simulator",
    "DebugSession",
    "COMPILER_NAME",
    "COMPILER_VERSION",
]
