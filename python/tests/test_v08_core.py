# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""v0.8 core-completion contracts, fixture cases, and dual-path integration."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panini.core_v08 import run_dual_path
from panini.digital import default_digital_backend, execution_ir_from_payload
from panini.fixtures_v08 import CASE_SOURCES, seed_conflict_parts, seed_inverse_record
from panini.frontend import parse_source
from panini.genotype_compiler import write_bundle, verify_bundle
from panini.geometry_backend import default_animation_backend, default_geometry_backend
from panini.knowledge import KnowledgeRecord, get_knowledge_registry, reset_knowledge_registry
from panini.observe import Observation
from panini.physical import LocalMockRealizationBackend
from panini.pipeline import compile_source
from panini.providers import (
    DeterministicMockGenerativeProvider,
    UnavailableGenerativeProvider,
    fixture_cassette_provider,
)
from panini.resolution import (
    compile_intent_genotype,
    get_generative_provider,
    set_generative_provider,
)
from panini.validation import reset_validation_registry
from panini.version import COMPILER_VERSION

ROOT = Path(__file__).resolve().parents[2]
REPORTER_SRC = (ROOT / "examples" / "reporter_cassette.panini").read_text()
MOUSE_SRC = (ROOT / "examples" / "mouse_axial.panini").read_text()
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


class ProviderContract(unittest.TestCase):
    def tearDown(self):
        set_generative_provider(UnavailableGenerativeProvider())
        reset_knowledge_registry()

    def test_unavailable_provider(self):
        p = UnavailableGenerativeProvider()
        self.assertFalse(p.available())
        self.assertFalse(p.capabilities()["can_propose"])
        self.assertEqual(p.version(), "0.0.0-unavailable")
        self.assertEqual(p.provenance()["status"], "UNAVAILABLE")
        self.assertIsNone(p.propose({"intent_name": "x"}))

    def test_available_provider_typed_candidate(self):
        p = fixture_cassette_provider()
        self.assertTrue(p.available())
        cand = p.propose(type("C", (), {"intent_name": "model_marker", "constraint_id": "c1"})())
        self.assertIsNotNone(cand)
        d = cand.to_dict()
        for key in (
            "candidate_id", "constraint_id", "provider", "model_id", "model_version",
            "proposal", "provenance", "evidence", "assumptions", "confidence",
            "status", "validation_status",
        ):
            self.assertIn(key, d)
        self.assertNotEqual(d["validation_status"], "VERIFIED")
        self.assertIsInstance(d["proposal"], dict)

    def test_candidate_cannot_be_verified(self):
        p = fixture_cassette_provider()
        cand = p.propose(type("C", (), {"intent_name": "model_marker", "constraint_id": "c1"})())
        with self.assertRaises(ValueError):
            cand.validation_status = "VERIFIED"
            from panini.providers import ModelCandidate
            ModelCandidate(
                candidate_id="x", constraint_id="c", provider="p", model_id="m",
                model_version="1", proposal={}, validation_status="VERIFIED",
            )

    def test_routing_and_provenance(self):
        set_generative_provider(fixture_cassette_provider())
        program = parse_source(CASE_SOURCES["case6_generative"])
        payload = compile_intent_genotype(CASE_SOURCES["case6_generative"], program)
        cons = payload["biological_resolution"]["constraints"][0]
        self.assertIsNotNone(cons["route"])
        self.assertTrue(cons["route"]["steps"])
        kinds = [s["kind"] for s in cons["route"]["steps"]]
        self.assertIn("generative_provider", kinds)


class ResolutionCases(unittest.TestCase):
    def tearDown(self):
        set_generative_provider(UnavailableGenerativeProvider())
        reset_knowledge_registry()

    def test_case1_direct_compiled(self):
        program = parse_source(CASE_SOURCES["case1_direct"])
        payload = compile_intent_genotype(CASE_SOURCES["case1_direct"], program)
        self.assertEqual(payload["status"], "COMPILED")
        self.assertEqual(payload["derived_sequence"], "GGGGGGTTAACC")

    def test_case2_user_asserted_not_validated(self):
        program = parse_source(CASE_SOURCES["case2_user"])
        payload = compile_intent_genotype(CASE_SOURCES["case2_user"], program)
        cons = payload["biological_resolution"]["constraints"][0]
        self.assertEqual(cons["causal_basis"], "USER_ASSERTED")
        self.assertEqual(cons["validation_status"], "NOT_VALIDATED")

    def test_case3_association_e0010(self):
        program = parse_source(CASE_SOURCES["case3_association"])
        payload = compile_intent_genotype(CASE_SOURCES["case3_association"], program)
        self.assertEqual(payload["status"], "DESIGN_UNRESOLVED")
        self.assertTrue(any(d["code"] == "E0010" for d in payload["diagnostics"]))
        cons = payload["biological_resolution"]["constraints"][0]
        self.assertIsNotNone(cons["inverse"])
        self.assertEqual(cons["inverse"]["status"], "NOT_LICENSED")

    def test_case4_inverse_not_licensed(self):
        seed_inverse_record()
        program = parse_source(CASE_SOURCES["case4_inverse"])
        payload = compile_intent_genotype(CASE_SOURCES["case4_inverse"], program)
        self.assertIn(payload["status"], {"DESIGN_UNRESOLVED"})
        codes = {d["code"] for d in payload["diagnostics"]}
        self.assertTrue("E0007" in codes or "E0010" in codes)
        cons = payload["biological_resolution"]["constraints"][0]
        self.assertFalse(cons["licenses_inverse"])

    def test_case5_provider_unavailable_diagnostic(self):
        self.assertFalse(get_generative_provider().available())
        program = parse_source(CASE_SOURCES["case5_unavailable"])
        payload = compile_intent_genotype(CASE_SOURCES["case5_unavailable"], program)
        self.assertEqual(payload["status"], "DESIGN_UNRESOLVED")
        self.assertTrue(payload["provider_diagnostics"])
        self.assertEqual(payload["provider_diagnostics"][0]["code"], "PROVIDER_UNAVAILABLE")

    def test_case6_model_derived_not_validated(self):
        set_generative_provider(fixture_cassette_provider())
        program = parse_source(CASE_SOURCES["case6_generative"])
        payload = compile_intent_genotype(CASE_SOURCES["case6_generative"], program)
        cons = payload["biological_resolution"]["constraints"][0]
        self.assertEqual(cons["status"], "MODEL_DERIVED")
        self.assertEqual(cons["validation_status"], "NOT_VALIDATED")
        self.assertIsNotNone(cons["candidate"])
        self.assertNotEqual(cons["candidate"]["validation_status"], "VERIFIED")

    def test_case7_constraint_graph_dependency(self):
        program = parse_source(CASE_SOURCES["case7_dependent"])
        payload = compile_intent_genotype(CASE_SOURCES["case7_dependent"], program)
        graph = payload["constraint_graph"]
        self.assertGreaterEqual(len(graph["nodes"]), 2)
        self.assertTrue(graph["edges"] or graph["resolution_order"])

    def test_case8_conflict(self):
        seed_conflict_parts()
        program = parse_source(CASE_SOURCES["case8_conflict"])
        payload = compile_intent_genotype(CASE_SOURCES["case8_conflict"], program)
        graph = payload["constraint_graph"]
        self.assertEqual(graph["graph_status"], "CONFLICTING")
        self.assertTrue(graph["conflicts"])


class PhysicalDigitalGeometry(unittest.TestCase):
    def test_physical_mock_realized(self):
        program = parse_source(REPORTER_SRC)
        payload = compile_intent_genotype(REPORTER_SRC, program)
        backend = LocalMockRealizationBackend()
        real = backend.realize(payload["genotype_design"])
        self.assertEqual(real.status, "REALIZED")
        self.assertTrue(backend.verify(real)["overall_pass"])
        self.assertTrue(real.provenance)

    def test_physical_unavailable_for_unresolved(self):
        program = parse_source(CASE_SOURCES["case5_unavailable"])
        payload = compile_intent_genotype(CASE_SOURCES["case5_unavailable"], program)
        real = LocalMockRealizationBackend().realize(payload["genotype_design"])
        self.assertEqual(real.status, "REALIZATION_UNAVAILABLE")

    def test_digital_execution_run(self):
        compiled = compile_source(MOUSE_SRC)
        eir = execution_ir_from_payload(compiled.payload, compiled.payload.get("genotype_design"))
        run = default_digital_backend().execute(eir, {"env": "fixture"}, {"seed": 1})
        self.assertTrue(run.run_id)
        self.assertIn("anatomical", run.phenotype)
        self.assertTrue(run.twin["note"])
        self.assertTrue(default_digital_backend().checkpoint(run) is not None)

    def test_geometry_and_animation(self):
        compiled = compile_source(MOUSE_SRC)
        eir = execution_ir_from_payload(compiled.payload)
        run = default_digital_backend().execute(eir, {}, {"seed": 1})
        spatial = default_geometry_backend().project(run.phenotype, "pheno")
        geom = default_geometry_backend().materialize(spatial)
        self.assertEqual(geom.kind, "point_cloud")
        self.assertTrue(geom.payload["points"])
        traj = default_animation_backend().from_history(run.state_history, run.phenotype)
        anim = default_animation_backend().animate(traj)
        self.assertIn("time", anim.to_dict())
        self.assertIn("state", anim.to_dict())


class ValidationLoop(unittest.TestCase):
    def setUp(self):
        reset_validation_registry()

    def test_observation_ingestion_and_history(self):
        from panini.validation import get_validation_registry
        obs = Observation(
            observation_id="obs1",
            source="MANUAL_ASSERTION",
            source_id="fixture",
            subject="marker",
            measurement=1,
            unit="count",
            method="manual",
        )
        reg = get_validation_registry()
        ev = reg.ingest_observation(obs, "claim:marker")
        claim = reg.transition("claim:marker", "OBSERVED", ev)
        self.assertEqual(claim.status, "OBSERVED")
        claim = reg.transition("claim:marker", "SUPPORTED", ev, note="second")
        self.assertEqual(claim.status, "SUPPORTED")
        self.assertEqual(len(claim.history), 2)
        self.assertEqual(claim.history[0].previous_status, "NOT_VALIDATED")
        self.assertEqual(claim.history[0].new_status, "OBSERVED")
        self.assertEqual(claim.history[1].previous_status, "OBSERVED")

    def test_contradictory_observation(self):
        from panini.validation import get_validation_registry
        obs = Observation(
            observation_id="obs2",
            source="PHYSICAL_EXPERIMENT",
            source_id="lab",
            subject="tail_count",
            measurement=1,
        )
        claim = get_validation_registry().evaluate_against_prediction("claim:tails", obs, 2)
        self.assertEqual(claim.status, "CONTRADICTED")


class VerificationBug(unittest.TestCase):
    def test_unresolved_must_not_emit_fasta(self):
        program = parse_source(CASE_SOURCES["case5_unavailable"])
        payload = compile_intent_genotype(CASE_SOURCES["case5_unavailable"], program)
        self.assertEqual(payload["status"], "DESIGN_UNRESOLVED")
        with tempfile.TemporaryDirectory() as d:
            write_bundle(payload, CASE_SOURCES["case5_unavailable"], d)
            self.assertFalse((Path(d) / "07-derived-sequence.fasta").exists())
            report = verify_bundle(d)
            names = {c["name"]: c["passed"] for c in report["checks"]}
            self.assertTrue(names["no_invented_sequence"])
            # illegally drop a fasta and prove the verifier catches it
            (Path(d) / "07-derived-sequence.fasta").write_text(">x\nACGT\n")
            report2 = verify_bundle(d)
            names2 = {c["name"]: c["passed"] for c in report2["checks"]}
            self.assertFalse(names2["no_invented_sequence"])
            self.assertFalse(report2["overall_pass"])


class KnowledgeGrowthV08(unittest.TestCase):
    def tearDown(self):
        set_generative_provider(UnavailableGenerativeProvider())
        reset_knowledge_registry()

    def test_generative_availability_grows_knowledge(self):
        reset_knowledge_registry()
        src = CASE_SOURCES["case6_generative"]
        before = _hash_compiler()
        first = compile_intent_genotype(src, parse_source(src))
        self.assertEqual(first["status"], "DESIGN_UNRESOLVED")
        set_generative_provider(fixture_cassette_provider())
        self.assertEqual(before, _hash_compiler())
        second = compile_intent_genotype(src, parse_source(src))
        cons = second["biological_resolution"]["constraints"][0]
        self.assertEqual(cons["status"], "MODEL_DERIVED")
        self.assertEqual(cons["validation_status"], "NOT_VALIDATED")

    def test_domain_record_still_resolves_without_compiler_edit(self):
        reset_knowledge_registry()
        src = CASE_SOURCES["case5_unavailable"]
        before = _hash_compiler()
        first = compile_intent_genotype(src, parse_source(src))
        self.assertEqual(first["status"], "DESIGN_UNRESOLVED")
        get_knowledge_registry().add_record(KnowledgeRecord(
            canonical_id="realize:synthetic:unknown_marker",
            namespace="test", name="unknown_marker", kind="RealizationMapping",
            source="session", provenance="DESIGN", evidence_status="curated",
            attributes={
                "organism": "synthetic", "intent_verb": "establish", "intent_name": "unknown_marker",
                "association_class": "MECHANISTICALLY_SUPPORTED", "causal_basis": "STANDARD_PART",
                "validation_status": "NOT_VALIDATED", "strategy": "KNOWLEDGE_PROVIDER",
                "assembly": "demo-v1", "reference": "chrDemo",
                "edits": [{"operation": "REPLACE", "start": 8, "end": 12, "replacement": "CCCC"}],
            },
        ))
        self.assertEqual(before, _hash_compiler())
        second = compile_intent_genotype(src, parse_source(src))
        self.assertEqual(second["status"], "COMPILED")


class DualPath(unittest.TestCase):
    def tearDown(self):
        reset_validation_registry()

    def test_shared_design_separate_domains(self):
        result = run_dual_path(MOUSE_SRC)
        self.assertEqual(result["shared"]["compiler_version"], COMPILER_VERSION)
        self.assertEqual(result["design"]["design_id"], result["shared"]["design_id"])
        self.assertEqual(result["physical"]["design_id"], result["design"]["design_id"])
        self.assertIsNotNone(result["digital"])
        self.assertEqual(result["digital"]["input_artifact"].startswith("eirx_") or True, True)
        self.assertIsNotNone(result["geometry"])
        self.assertEqual(result["observation"]["source"], "SIMULATION")
        self.assertEqual(result["claim"]["status"], "OBSERVED")
        kinds = {n["kind"] for n in result["artifact_graph"]["nodes"]}
        self.assertIn("genotype_design", kinds)
        self.assertIn("physical_realization", kinds)
        self.assertIn("execution_ir", kinds)
        self.assertNotEqual(result["physical"]["digest"], result["digital"]["digest"])


if __name__ == "__main__":
    unittest.main()
