"""Desired ≠ predicted ≠ observed phenotype."""

from .constraints import PhenotypeConstraint, PhenotypeConstraintSet
from .evaluator import verify_target_phenotype, verdict_bundle
from .diff import compare_phenotypes, constraints_from_intents

__all__ = [
    "PhenotypeConstraint",
    "PhenotypeConstraintSet",
    "verify_target_phenotype",
    "verdict_bundle",
    "compare_phenotypes",
    "constraints_from_intents",
]
