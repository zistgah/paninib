from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Literal, Optional

Operator = Literal[
    "==", "!=", "<", "<=", ">", ">=",
    "in", "contains", "approximately",
]


def _walk(phenotype: dict, path: str) -> Any:
    value: Any = phenotype
    for part in path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    return value


@dataclass(frozen=True)
class PhenotypeConstraint:
    id: str
    layer: str
    property: str
    operator: Operator
    target: Any
    tolerance: float | None = None
    spatial_reference: str | None = None
    temporal_reference: str | None = None
    required: bool = True
    evidence_level: str = "THEORETICAL"

    def evaluate(self, phenotype: dict) -> dict:
        path = self.property
        if self.layer and not path.startswith(self.layer):
            # allow both "primary_axis" with layer anatomical and "anatomical.primary_axis"
            layered = f"{self.layer}.{self.property}"
            value = _walk(phenotype, layered)
            if value is None:
                value = _walk(phenotype, path)
        else:
            value = _walk(phenotype, path)
        passed, unknown = self._compare(value)
        status = "UNKNOWN" if unknown else ("SATISFIED" if passed else "UNSATISFIED")
        return {
            "id": self.id,
            "layer": self.layer,
            "property": self.property,
            "operator": self.operator,
            "target": self.target,
            "observed": value,
            "passed": passed and not unknown,
            "status": status,
            "required": self.required,
        }

    def _compare(self, value) -> tuple[bool, bool]:
        if value is None:
            return False, False
        op = self.operator
        if op in {"==", "approximately"}:
            try:
                if self.tolerance is not None:
                    return abs(float(value) - float(self.target)) <= self.tolerance, False
            except (TypeError, ValueError):
                pass
            if op == "approximately":
                try:
                    return abs(float(value) - float(self.target)) <= (self.tolerance or 0.0), False
                except (TypeError, ValueError):
                    return False, False
            return value == self.target or str(value) == str(self.target), False
        if op == "!=":
            return value != self.target, False
        try:
            lv, rv = float(value), float(self.target)
        except (TypeError, ValueError):
            return False, False
        if op == "<":
            return lv < rv, False
        if op == "<=":
            return lv <= rv, False
        if op == ">":
            return lv > rv, False
        if op == ">=":
            return lv >= rv, False
        if op == "in":
            return value in self.target, False
        if op == "contains":
            return self.target in value, False
        raise ValueError(op)


@dataclass
class PhenotypeConstraintSet:
    program_id: str
    constraints: List[PhenotypeConstraint]

    def evaluate(self, phenotype: dict) -> dict:
        results = [c.evaluate(phenotype) for c in self.constraints]
        required = [r for r in results if r["required"]]
        unknown = [r for r in required if r["status"] == "UNKNOWN"]
        failed = [r for r in required if r["status"] == "UNSATISFIED"]
        passed = [r for r in required if r["status"] == "SATISFIED"]
        if failed:
            status = "UNSATISFIED"
        elif unknown:
            status = "UNKNOWN"
        else:
            status = "SATISFIED"
        return {
            "status": status,
            "passed": passed,
            "failed": failed,
            "unknown": unknown,
            "all": results,
        }
