"""Biological breakpoint predicates.

BREAKPOINT phenotype.tail_count != 2
BREAKPOINT expression(GENE_X) > θ
BREAKPOINT developmental_state == tail_bud
"""

from __future__ import annotations

import re
from typing import Any, Callable

from ..simulator.state import BiologicalState


Predicate = Callable[[BiologicalState], bool]


def _num(x: Any) -> float:
    if isinstance(x, bool):
        return float(x)
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, dict) and "value" in x:
        return float(x["value"])
    try:
        return float(x)
    except (TypeError, ValueError):
        raise ValueError(f"not numeric: {x!r}")


def _resolve(state: BiologicalState, token: str) -> Any:
    token = token.strip()
    m = re.match(r"expression\(([^)]+)\)", token)
    if m:
        return state.expression(m.group(1).strip())
    aliases = {
        "developmental_state": "stage",
        "developmental.state": "stage",
        "phenotype.tail_count": "anatomy.tail_count",
        "phenotype.tail_length": "anatomy.tail_length_mm",
        "phenotype.primary": "anatomy.primary_axis",
        "phenotype.primary_axis": "anatomy.primary_axis",
        "cell.type": "cells.0.cell_type",
    }
    token = aliases.get(token, token)
    if token in {"stage", "time", "step"}:
        return getattr(state, token)
    try:
        return state.get_path(token)
    except KeyError:
        # allow anatomy / molecular shorthand
        if token in state.anatomy:
            return state.anatomy[token]
        if token in state.molecular:
            return state.molecular[token].value
        raise


def parse_predicate(expr: str) -> Predicate:
    raw = expr.strip()
    if raw.lower().startswith("break "):
        raw = raw[6:].strip()
    if raw.lower().startswith("when "):
        raw = raw[5:].strip()

    m = re.match(
        r"(.+?)\s*(==|!=|>=|<=|>|<)\s*(.+)$",
        raw,
    )
    if not m:
        path = raw

        def pred_truthy(state: BiologicalState) -> bool:
            v = _resolve(state, path)
            return bool(v)

        pred_truthy.__doc__ = raw
        return pred_truthy

    left_s, op, right_s = m.group(1).strip(), m.group(2), m.group(3).strip()
    right_s = right_s.strip("\"'")

    def pred(state: BiologicalState) -> bool:
        left = _resolve(state, left_s)
        # try numeric compare first
        try:
            lv, rv = _num(left), _num(right_s)
            if op == "==":
                return abs(lv - rv) < 1e-9
            if op == "!=":
                return abs(lv - rv) >= 1e-9
            if op == ">":
                return lv > rv
            if op == "<":
                return lv < rv
            if op == ">=":
                return lv >= rv
            if op == "<=":
                return lv <= rv
        except (ValueError, TypeError):
            lv, rv = str(left), str(right_s)
            if op == "==":
                return lv == rv
            if op == "!=":
                return lv != rv
            return False
        return False

    pred.__doc__ = raw
    return pred
