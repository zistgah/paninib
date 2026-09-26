import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panini.errors import SemanticError, UnsupportedError
from panini.frontend import parse_source
from panini.ontology import CISC_OPCODES
from panini.pipeline import CompileOptions, compile_source

SRC = r"""
organism Mouse {
    intent {
        establish axial_pattern {
            primary = tail
            secondary = tail
        }
        reach_state mature
    }
    constraints {
        viability
        developmental_consistency
        phenotype_fidelity
    }
    verify {
        molecular
        cellular
        tissue
        anatomical
        temporal
    }
}
"""


class VerticalSlice(unittest.TestCase):
    def test_parse(self):
        p = parse_source(SRC)
        self.assertEqual(p.organism, "Mouse")
        self.assertEqual(len(p.intents), 2)
        self.assertEqual(len(p.constraints), 3)

    def test_bad_verb(self):
        src = "organism Mouse { intent { florb axial_pattern } constraints { viability } verify { molecular } }"
        with self.assertRaises(SemanticError):
            compile_source(src)

    def test_layers(self):
        r = compile_source(SRC)
        p = r.payload
        self.assertTrue(p["cisc"]["instructions"])
        self.assertTrue(p["risc"]["instructions"])
        self.assertTrue(p["microcode"]["ops"])
        self.assertEqual(len(p["risc"]["lowering_map"]), len(p["cisc"]["instructions"]))
        self.assertEqual(len(p["microcode"]["ops"]), len(p["risc"]["instructions"]))
        self.assertTrue(p["realization"]["construct_specification"])
        self.assertTrue(p["simulation_result"]["matured"])
        self.assertGreater(p["simulation_result"]["terminal_phenotype_score"], 0.5)
        self.assertTrue(p["capability"]["sufficient"])
        self.assertEqual(
            p["invariant"],
            "Intent ≠ Genetic CISC ≠ Microcode ≠ ATGC ≠ Physical execution",
        )
        for c in p["realization"]["construct_specification"]:
            self.assertTrue(c["sequence_ref"].startswith("mgi://"))
            self.assertIsNone(c.get("sequence"))
            self.assertTrue(c["artifact_id"].startswith("mmu."))
        self.assertFalse(any(f["level"] == "L0" for f in p["verification"]["failed"]))
        self.assertTrue(p["verification"]["overall_pass"])

    def test_cell_free_unsupported(self):
        with self.assertRaises(UnsupportedError) as ctx:
            compile_source(SRC, CompileOptions(backend="cell_free.in_vitro"))
        self.assertIn("cell_free", ctx.exception.backend)

    def test_cisc_vocab(self):
        self.assertIn("RECOGNIZE", CISC_OPCODES)
        self.assertIn("DEVELOP", CISC_OPCODES)
        self.assertIn("FEEDBACK", CISC_OPCODES)
        self.assertGreaterEqual(len(CISC_OPCODES), 60)

    def test_stable_hash(self):
        a = compile_source(SRC)
        b = compile_source(SRC)
        self.assertEqual(a.payload["source_hash"], b.payload["source_hash"])
        self.assertEqual(a.payload["program_id"], b.payload["program_id"])
        self.assertEqual(a.payload["pass_records"][0]["output_hash"], b.payload["pass_records"][0]["output_hash"])


if __name__ == "__main__":
    unittest.main()
