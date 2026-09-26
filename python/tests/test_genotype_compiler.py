# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Tasks 2–5 acceptance: knowledge spine, CISC spec, Sequence IR, genotype compiler."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panini.genotype_compiler import (
    DesignStatus,
    compile_any,
    compile_sequence_program,
    compile_unresolved_phenotype,
    detect_source_kind,
    inspect_stage,
    parse_sequence_program,
    verify_bundle,
    write_bundle,
)
from panini.isa_spec import all_specs, isa_manifest, lowering_for, spec_for
from panini.knowledge import EVIDENCE_STATUS, KNOWLEDGE_KINDS, get_knowledge_registry
from panini.pipeline import CompileOptions, compile_source
from panini.reference_backend import demo_backend, standards_note
from panini.sequence_ir import SequenceEdit, SequenceIRError, apply_edits
from panini.simulator.api import Simulator
from panini.simulator.models import ModelParams

ROOT = Path(__file__).resolve().parents[2]
REPLACE_SRC = (ROOT / "examples" / "replace.panini").read_text()
MOUSE_SRC = (ROOT / "examples" / "mouse_axial.panini").read_text()
ORG_A = (ROOT / "examples" / "test_organism_a.panini").read_text()


class KnowledgeSpine(unittest.TestCase):
    def test_mvp_records_and_provider(self):
        reg = get_knowledge_registry()
        org = reg.resolve("org:synthetic")
        self.assertIsNotNone(org)
        self.assertEqual(org.kind, "Organism")
        self.assertIn(org.evidence_status, EVIDENCE_STATUS)
        asm = reg.resolve("asm:demo-v1")
        self.assertEqual(asm.kind, "Assembly")
        seq = reg.resolve("seq:demo-v1:chrDemo")
        self.assertEqual(seq.kind, "Sequence")
        self.assertTrue(set(KNOWLEDGE_KINDS))
        self.assertTrue(reg.search("demo"))


class CiscSemantics(unittest.TestCase):
    def test_every_opcode_has_spec(self):
        specs = all_specs()
        self.assertGreaterEqual(len(specs), 70)
        for op, spec in specs.items():
            self.assertEqual(spec.opcode_id, op)
            self.assertTrue(spec.description)
            self.assertIn(spec.implementation_status, {
                "SPECIFIED", "LOWERABLE", "EXECUTABLE", "MODEL_DEPENDENT", "UNIMPLEMENTED", "UNKNOWN"
            })
            self.assertIn(spec.risc_lowering.lowering_status, {"AVAILABLE", "UNAVAILABLE", "MODEL_DEPENDENT"})

    def test_replace_is_sequence_realizable(self):
        spec = spec_for("REPLACE")
        self.assertIsNotNone(spec)
        self.assertTrue(spec.risc_lowering.sequence_realizable)
        self.assertEqual(spec.implementation_status, "EXECUTABLE")

    def test_unspecified_lowering_is_unavailable_not_invented(self):
        low = lowering_for("INVERT")
        self.assertEqual(low.lowering_status, "UNAVAILABLE")
        self.assertEqual(low.risc_sequence, [])

    def test_isa_is_versioned(self):
        man = isa_manifest()
        self.assertTrue(man["isa_version"])
        self.assertFalse(man["risc_minimality_claim"])
        self.assertIn("sequence_state", man["execution_state_domains"])


class SequenceCompilation(unittest.TestCase):
    def setUp(self):
        self.backend = demo_backend()

    def test_1_explicit_replace_is_deterministic_atgc(self):
        result = compile_sequence_program(REPLACE_SRC, backend=self.backend)
        self.assertEqual(result["status"], "COMPILED")
        self.assertEqual(result["derived_sequence"], "AACCTTTTAACC")
        self.assertTrue(result["fasta"].startswith(">"))

    def test_2_same_source_same_digest(self):
        a = compile_sequence_program(REPLACE_SRC, backend=self.backend)
        b = compile_sequence_program(REPLACE_SRC, backend=self.backend)
        self.assertEqual(a["derived_sequence"], b["derived_sequence"])
        with tempfile.TemporaryDirectory() as da, tempfile.TemporaryDirectory() as db:
            ma = write_bundle(a, REPLACE_SRC, da)
            mb = write_bundle(b, REPLACE_SRC, db)
            self.assertEqual(ma["output_sequence_digest"], mb["output_sequence_digest"])
            self.assertEqual(ma["input_program_digest"], mb["input_program_digest"])

    def test_3_changing_reference_changes_result(self):
        src_v2 = REPLACE_SRC.replace("demo-v1", "demo-v2")
        a = compile_sequence_program(REPLACE_SRC, backend=self.backend)
        b = compile_sequence_program(src_v2, backend=self.backend)
        self.assertNotEqual(a["reference"]["digest"], b["reference"]["digest"])
        self.assertNotEqual(a["derived_sequence"], b["derived_sequence"])
        self.assertEqual(b["derived_sequence"], "TTTTTTTTAACC")

    def test_4_invalid_coordinates_fail(self):
        edit = SequenceEdit("x", "REPLACE", 1, 99, "A")
        with self.assertRaises(SequenceIRError) as ctx:
            apply_edits(self.backend.resolve_sequence("demo-v1", "chrDemo"), [edit])
        self.assertEqual(ctx.exception.status, "INVALID_EDIT")

    def test_5_invalid_nucleotide_symbols_fail(self):
        edit = SequenceEdit("x", "REPLACE", 1, 2, "N")
        with self.assertRaises(SequenceIRError) as ctx:
            apply_edits(self.backend.resolve_sequence("demo-v1", "chrDemo"), [edit])
        self.assertEqual(ctx.exception.status, "INVALID_EDIT")

    def test_6_reference_digest_mismatch_fails(self):
        with self.assertRaises(DesignStatus) as ctx:
            compile_sequence_program(
                REPLACE_SRC,
                backend=self.backend,
                expected_reference_digest="0" * 64,
            )
        self.assertEqual(ctx.exception.status, "REFERENCE_MISMATCH")

    def test_7_unsupported_lowering_is_unresolved(self):
        src = (ROOT / "examples" / "invert.panini").read_text()
        # parser must accept invert as an operation word
        try:
            result = compile_sequence_program(src, backend=self.backend)
        except DesignStatus as exc:
            self.assertEqual(exc.status, "UNSUPPORTED_OPERATION")
            return
        self.assertEqual(result["status"], "DESIGN_UNRESOLVED")
        self.assertIsNone(result["derived_sequence"])

    def test_8_two_tail_mouse_simulation_vs_genotype(self):
        one = compile_source(MOUSE_SRC)
        self.assertEqual(one.payload["execution_contract"]["model_id"], "mouse_axial_1d")
        self.assertEqual(one.payload["genotype_realization"]["genomic_realization"], "unresolved")
        self.assertEqual(one.payload["genotype_design"]["status"], "DESIGN_UNRESOLVED")
        two = compile_source(MOUSE_SRC, CompileOptions(model="mouse_axial_2axis"))
        params = ModelParams()
        params.model_id = "mouse_axial_2axis"
        run = Simulator(payload=two.payload, params=params, seed=1).run()
        self.assertEqual(run.phenotype["anatomical"]["tail_count"], 2)
        self.assertEqual(two.payload["genotype_design"]["status"], "DESIGN_UNRESOLVED")
        self.assertEqual(two.payload["genotype_design"]["edits"], [])

    def test_9_non_mouse_reaches_sequence_ir(self):
        self.assertEqual(detect_source_kind(REPLACE_SRC), "sequence_design")
        result = compile_sequence_program(REPLACE_SRC, backend=self.backend)
        self.assertEqual(result["sequence_ir"]["type"], "SequenceIR")
        self.assertEqual(result["program"]["organism"], "synthetic")
        kind, unresolved = compile_any(ORG_A)
        self.assertEqual(kind, "intent")
        self.assertEqual(unresolved["status"], "DESIGN_UNRESOLVED")
        self.assertIsNone(unresolved["derived_sequence"])

    def test_10_artifact_graph(self):
        with tempfile.TemporaryDirectory() as d:
            write_bundle(compile_sequence_program(REPLACE_SRC, backend=self.backend), REPLACE_SRC, d)
            report = verify_bundle(d)
            self.assertTrue(report["overall_pass"], msg=report)
            for stage in (
                "source", "semantic-ir", "cisc", "risc", "genotype", "sequence-ir", "manifest", "provenance"
            ):
                inspect_stage(d, stage)
            fasta = Path(d) / "07-derived-sequence.fasta"
            self.assertTrue(fasta.exists())
            seq = "".join(l.strip() for l in fasta.read_text().splitlines() if not l.startswith(">"))
            self.assertEqual(seq, "AACCTTTTAACC")
            self.assertEqual(hashlib.sha256(seq.encode()).hexdigest(), json.loads((Path(d)/"manifest.json").read_text())["output_sequence_digest"])

    def test_missing_reference(self):
        src = "organism synthetic\nassembly missing\nreference chrDemo\nreplace 0 1 A\n"
        with self.assertRaises(DesignStatus) as ctx:
            compile_sequence_program(src, backend=self.backend)
        self.assertEqual(ctx.exception.status, "REFERENCE_UNAVAILABLE")

    def test_standards_documented(self):
        note = standards_note()
        self.assertIn("GA4GH_Refget", note["standards"])
        self.assertIn("NCBI_Datasets", note["standards"])


class HonestyBoundary(unittest.TestCase):
    def test_unresolved_helper_does_not_emit_atgc(self):
        payload = compile_unresolved_phenotype(
            MOUSE_SRC, "Mouse", "two_tails"
        )
        self.assertEqual(payload["status"], "DESIGN_UNRESOLVED")
        self.assertIsNone(payload["derived_sequence"])
        self.assertEqual(payload["genomic_realization"], "unresolved")
        self.assertEqual(payload["phenotype_target"], "known")


if __name__ == "__main__":
    unittest.main()
