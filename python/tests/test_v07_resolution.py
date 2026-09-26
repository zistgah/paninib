# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""v0.7 biological resolution, ExperimentalIR, knowledge-growth invariant."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panini.diagnostics import DIAGNOSTIC_CATALOG, Diagnostic
from panini.experimental_ir import ExperimentalIR, ResolutionWorkOrder, dumps_canonical
from panini.frontend import parse_source
from panini.genotype_compiler import (
    compile_any,
    compile_sequence_program,
    compile_unresolved_phenotype,
    write_bundle,
)
from panini.knowledge import KnowledgeRecord, get_knowledge_registry, reset_knowledge_registry
from panini.pipeline import compile_source
from panini.reference_backend import demo_backend
from panini.resolution import (
    UnavailableGenerativeProvider,
    compile_intent_genotype,
    get_generative_provider,
)
from panini.schema_validate import SchemaError, validate_named
from panini.version import COMPILER_VERSION

ROOT = Path(__file__).resolve().parents[2]
MOUSE_SRC = (ROOT / "examples" / "mouse_axial.panini").read_text()
REPLACE_SRC = (ROOT / "examples" / "replace.panini").read_text()
REPORTER_SRC = (ROOT / "examples" / "reporter_cassette.panini").read_text()
PARTIAL_SRC = (ROOT / "examples" / "partial_resolution.panini").read_text()
UAC_SRC = (ROOT / "examples" / "user_asserted.panini").read_text()
ASSOC_SRC = (ROOT / "examples" / "glow_associated.panini").read_text()
UAC_SEQ = (ROOT / "examples" / "user_asserted_sequence.panini").read_text()

COMPILER_FILES = [
    ROOT / "python" / "panini" / "resolution.py",
    ROOT / "python" / "panini" / "pipeline.py",
    ROOT / "python" / "panini" / "genotype_compiler.py",
    ROOT / "python" / "panini" / "lowering.py",
    ROOT / "python" / "panini" / "frontend.py",
]


def _hash_compiler() -> str:
    h = hashlib.sha256()
    for path in COMPILER_FILES:
        h.update(path.read_bytes())
    return h.hexdigest()


class SchemaContracts(unittest.TestCase):
    def test_valid_work_order_and_diagnostic(self):
        diag = Diagnostic(code="E0001", constraint_id="c001_establish_axial_pattern", message="unresolved mechanism")
        validate_named(diag.to_dict(), "diagnostic.schema.json")
        order = ResolutionWorkOrder(
            work_order_id="rwo_demo",
            constraint_id="c001_establish_axial_pattern",
            diagnostic_code="E0001",
            question="What realization satisfies this constraint?",
            target_property="axial_pattern",
            missing_relation="genotype_realization_of_phenotype_constraint",
            required_evidence_class="causal",
            resolution_criterion="add a RealizationMapping record",
        )
        validate_named(order.to_dict(), "resolution_work_order.schema.json")
        eir = ExperimentalIR(experimental_ir_id="eir_demo", program_id="p1", work_orders=[order])
        validate_named(eir.to_dict(), "experimental_ir.schema.json")

    def test_missing_required_field(self):
        with self.assertRaises(SchemaError):
            validate_named({"schema_version": "0.7.0"}, "diagnostic.schema.json")

    def test_invalid_enum(self):
        with self.assertRaises(SchemaError):
            validate_named({"schema_version": "0.7.0", "code": "E9999", "severity": "error", "constraint_id": "x", "message": "nope"}, "diagnostic.schema.json")

    def test_invalid_type(self):
        with self.assertRaises(SchemaError):
            validate_named({"schema_version": "0.7.0", "code": "E0001", "severity": "error", "constraint_id": "x", "message": 12}, "diagnostic.schema.json")

    def test_schema_version_handling(self):
        with self.assertRaises(SchemaError):
            validate_named({"schema_version": "0.6.0", "code": "E0001", "severity": "error", "constraint_id": "x", "message": "x"}, "diagnostic.schema.json")

    def test_round_trip(self):
        order = ResolutionWorkOrder(
            work_order_id="rwo_rt", constraint_id="c001", diagnostic_code="E0001",
            question="q", target_property="p", missing_relation="m",
            required_evidence_class="causal", resolution_criterion="r",
        )
        text = dumps_canonical(order.to_dict())
        again = ResolutionWorkOrder.from_dict(json.loads(text))
        self.assertEqual(again.to_dict(), json.loads(text))
        self.assertEqual(dumps_canonical(again.to_dict()), text)


class ExistingPathPreserved(unittest.TestCase):
    def test_explicit_replace_still_deterministic(self):
        result = compile_sequence_program(REPLACE_SRC, backend=demo_backend())
        self.assertEqual(result["status"], "COMPILED")
        self.assertEqual(result["derived_sequence"], "AACCTTTTAACC")

    def test_two_tail_mouse_still_unresolved_and_emits_work_order(self):
        result = compile_source(MOUSE_SRC)
        self.assertEqual(result.payload["genotype_design"]["status"], "DESIGN_UNRESOLVED")
        self.assertEqual(result.payload["genotype_realization"]["genomic_realization"], "unresolved")
        diags = result.payload["diagnostics"]
        self.assertTrue(any(d["code"] == "E0001" for d in diags))
        orders = result.payload["resolution_work_orders"]
        self.assertTrue(orders)
        validate_named(orders[0], "resolution_work_order.schema.json")
        self.assertFalse(result.payload["genotype_design"]["edits"])
        eir = result.payload["experimental_ir"]
        self.assertNotIn("dosing", eir["note"].lower())
        self.assertEqual(eir["integration"]["neutrality"], "integration-neutral")

    def test_compile_unresolved_helper(self):
        payload = compile_unresolved_phenotype(MOUSE_SRC, "Mouse", "two_tails")
        self.assertEqual(payload["status"], "DESIGN_UNRESOLVED")
        self.assertIsNone(payload["derived_sequence"])
        self.assertEqual(payload["diagnostics"][0]["code"], "E0001")


class RegistryResolution(unittest.TestCase):
    def test_standard_part_compiles_to_atgc(self):
        program = parse_source(REPORTER_SRC)
        payload = compile_intent_genotype(REPORTER_SRC, program)
        self.assertEqual(payload["status"], "COMPILED")
        self.assertEqual(payload["derived_sequence"], "GGGGGGTTAACC")
        resolved = payload["biological_resolution"]["constraints"]
        self.assertEqual(resolved[0]["strategy"], "STANDARD_LIBRARY")
        self.assertEqual(resolved[0]["causal_basis"], "STANDARD_PART")
        self.assertEqual(resolved[0]["validation_status"], "NOT_VALIDATED")
        self.assertEqual(resolved[0]["knowledge_record_id"], "realize:synthetic:reporter_cassette")

    def test_registry_not_hardcoded_in_compiler_source(self):
        text = (ROOT / "python" / "panini" / "resolution.py").read_text()
        self.assertNotIn("reporter_cassette", text)
        self.assertNotIn("two_tail", text)
        self.assertNotIn("Mus musculus", text)


class PartialCompilation(unittest.TestCase):
    def test_partial_program(self):
        program = parse_source(PARTIAL_SRC)
        payload = compile_intent_genotype(PARTIAL_SRC, program)
        self.assertEqual(payload["status"], "COMPILED_WITH_WARNINGS")
        self.assertEqual(payload["genomic_realization"], "partial")
        self.assertTrue(payload["derived_sequence"])
        self.assertTrue(payload["resolved_constraints"])
        self.assertTrue(payload["unresolved_constraints"])
        self.assertTrue(any(d["code"] == "E0001" for d in payload["diagnostics"]))
        self.assertEqual(payload["derived_sequence"], "GGGGGGTTAACC")


class UserAssertion(unittest.TestCase):
    def test_intent_assertion_is_not_validation(self):
        program = parse_source(UAC_SRC)
        payload = compile_intent_genotype(UAC_SRC, program)
        self.assertIn(payload["status"], {"COMPILED", "COMPILED_WITH_WARNINGS"})
        self.assertEqual(payload["derived_sequence"], "AAAAGGTTAACC")
        cons = payload["biological_resolution"]["constraints"][0]
        self.assertEqual(cons["causal_basis"], "USER_ASSERTED")
        self.assertEqual(cons["validation_status"], "NOT_VALIDATED")
        self.assertTrue(any(d["code"] == "E0009" for d in payload["diagnostics"]))

    def test_sequence_program_assertion(self):
        result = compile_sequence_program(UAC_SEQ, backend=demo_backend())
        self.assertEqual(result["status"], "COMPILED_WITH_WARNINGS")
        self.assertEqual(result["genotype_design"]["causal_basis"], "USER_ASSERTED")
        self.assertEqual(result["genotype_design"]["validation_status"], "NOT_VALIDATED")
        self.assertEqual(result["derived_sequence"], "AACCTTTTAACC")


class ScientificNegatives(unittest.TestCase):
    def test_association_is_not_causation(self):
        program = parse_source(ASSOC_SRC)
        payload = compile_intent_genotype(ASSOC_SRC, program)
        self.assertEqual(payload["status"], "DESIGN_UNRESOLVED")
        self.assertIsNone(payload["derived_sequence"])
        self.assertTrue(any(d["code"] == "E0010" for d in payload["diagnostics"]))

    def test_loss_of_function_does_not_license_inverse(self):
        reset_knowledge_registry()
        get_knowledge_registry().add_record(KnowledgeRecord(
            canonical_id="realize:synthetic:anti_glow",
            namespace="test", name="anti_glow", kind="RealizationMapping",
            source="session", provenance="EVIDENCE", evidence_status="curated",
            attributes={
                "organism": "synthetic", "intent_verb": "establish", "intent_name": "anti_glow",
                "association_class": "CAUSALLY_SUPPORTED", "causal_basis": "EVIDENCE_BACKED",
                "validation_status": "EXPERIMENTALLY_SUPPORTED", "strategy": "KNOWLEDGE_PROVIDER",
                "direction": "lof", "licenses_inverse": False,
                "assembly": "demo-v1", "reference": "chrDemo",
                "edits": [{"operation": "DELETE", "start": 0, "end": 2, "replacement": ""}],
            },
        ))
        src = """
organism synthetic {
    intent {
        establish anti_glow { direction = gof }
        reach_state dummy
    }
    constraints { viability }
    verify { molecular }
}
"""
        program = parse_source(src)
        payload = compile_intent_genotype(src, program)
        self.assertIn("E0007", {d["code"] for d in payload["diagnostics"]})
        reset_knowledge_registry()

    def test_model_prediction_is_not_experimental_validation(self):
        result = compile_source(MOUSE_SRC)
        self.assertEqual(result.payload["coverage"]["validation_coverage"], 0.0)
        self.assertGreater(result.payload["coverage"]["semantic_coverage"], 0.0)
        self.assertTrue(result.payload["simulation_result"])

    def test_generative_interface_is_unavailable_by_default(self):
        self.assertFalse(get_generative_provider().available())
        self.assertIsInstance(get_generative_provider(), UnavailableGenerativeProvider)

    def test_catalog_has_required_codes(self):
        for code in [f"E{i:04d}" for i in range(1, 12)]:
            self.assertIn(code, DIAGNOSTIC_CATALOG)


class KnowledgeGrowthInvariant(unittest.TestCase):
    def test_adding_knowledge_resolves_without_compiler_edits(self):
        reset_knowledge_registry()
        src = """
organism synthetic {
    intent { establish novel_marker }
    constraints { viability }
    verify { molecular }
}
"""
        before = _hash_compiler()
        program = parse_source(src)
        first = compile_intent_genotype(src, program)
        self.assertEqual(first["status"], "DESIGN_UNRESOLVED")
        self.assertTrue(any(d["code"] == "E0001" for d in first["diagnostics"]))
        self.assertIsNone(first["derived_sequence"])
        get_knowledge_registry().add_record(KnowledgeRecord(
            canonical_id="realize:synthetic:novel_marker",
            namespace="test", name="novel_marker", kind="RealizationMapping",
            source="session", provenance="DESIGN", evidence_status="curated",
            attributes={
                "organism": "synthetic", "intent_verb": "establish", "intent_name": "novel_marker",
                "association_class": "MECHANISTICALLY_SUPPORTED", "causal_basis": "STANDARD_PART",
                "validation_status": "NOT_VALIDATED", "strategy": "KNOWLEDGE_PROVIDER",
                "assembly": "demo-v1", "reference": "chrDemo", "provider": "session",
                "edits": [{"operation": "REPLACE", "start": 8, "end": 12, "replacement": "CCCC"}],
            },
        ))
        self.assertEqual(before, _hash_compiler())
        second = compile_intent_genotype(src, program)
        self.assertEqual(second["status"], "COMPILED")
        self.assertEqual(second["derived_sequence"], "AACCGGTTCCCC")
        self.assertFalse(any(d["code"] == "E0001" for d in second["diagnostics"]))
        reset_knowledge_registry()

    def test_compiler_version_is_current(self):
        # v0.8 preserves the v0.7 knowledge-growth invariant; compiler version advances.
        self.assertTrue(COMPILER_VERSION.startswith("1.") or COMPILER_VERSION.startswith("0.9") or COMPILER_VERSION.startswith("0.8") or COMPILER_VERSION.startswith("0.7"))


class ProvenanceAndCoverage(unittest.TestCase):
    def test_resolved_artifact_answers_provenance_questions(self):
        program = parse_source(REPORTER_SRC)
        payload = compile_intent_genotype(REPORTER_SRC, program)
        cons = payload["biological_resolution"]["constraints"][0]
        self.assertEqual(cons["provider"], "stdlib")
        self.assertEqual(cons["knowledge_record_id"], "realize:synthetic:reporter_cassette")
        self.assertEqual(cons["causal_basis"], "STANDARD_PART")
        self.assertEqual(payload["reference"]["digest"], hashlib.sha256(b"AACCGGTTAACC").hexdigest())
        self.assertEqual(payload["derived"]["digest"], hashlib.sha256(payload["derived_sequence"].encode()).hexdigest())
        for key in ("semantic_coverage","lowering_coverage","sequence_coverage","evidence_coverage","validation_coverage","constraint_resolution_coverage"):
            self.assertIn(key, payload["coverage"])

    def test_bundle_writes_resolution_artifacts(self):
        program = parse_source(PARTIAL_SRC)
        payload = compile_intent_genotype(PARTIAL_SRC, program)
        with tempfile.TemporaryDirectory() as d:
            write_bundle(payload, PARTIAL_SRC, d)
            self.assertTrue((Path(d) / "diagnostics.json").exists())
            self.assertTrue((Path(d) / "resolution-work-orders.json").exists())
            self.assertTrue((Path(d) / "experimental-ir.json").exists())
            self.assertTrue((Path(d) / "07-derived-sequence.fasta").exists())


class CompileAnyDispatch(unittest.TestCase):
    def test_intent_uses_resolution_engine(self):
        kind, payload = compile_any(REPORTER_SRC)
        self.assertEqual(kind, "intent")
        self.assertEqual(payload["status"], "COMPILED")


if __name__ == "__main__":
    unittest.main()
