# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""v0.4 acceptance tests (docs/v0.4-contract.md)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panini.bundle import write_bundle
from panini.ontology import CISC_OPCODES, catalog
from panini.pipeline import CompileOptions, compile_source
from panini.retrieval import LOCI, load_all
from panini.simulator.api import Simulator
from panini.simulator.geometry_export import mesh_from_phenotype
from panini.simulator.models import ModelParams

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "examples" / "mouse_axial.panini").read_text()


class V04(unittest.TestCase):
    def test_B1_comprehensive_cisc(self):
        self.assertGreaterEqual(len(catalog()), 60)
        self.assertGreaterEqual(len(CISC_OPCODES), 60)
        for op, dfn in catalog().items():
            self.assertTrue(dfn.semantic_definition)
            self.assertNotEqual(dfn.semantic_definition, f"CISC operation {op} (generic catalog entry)")

    def test_B3_internal_validity_field(self):
        p = compile_source(SRC).payload
        self.assertIn("internal_validity_pass", p["verification"])
        self.assertTrue(p["verification"]["internal_validity_pass"])
        self.assertEqual(p["verdict"]["overall"], "UNSATISFIED")

    def test_B6_execution_contract(self):
        p = compile_source(SRC).payload
        self.assertEqual(p["execution_contract"]["model_id"], "mouse_axial_1d")
        self.assertTrue(p["execution_contract"]["need_multi_axis"])

    def test_B8_two_axis_runtime_not_an_assignment(self):
        payload = compile_source(SRC, CompileOptions(model="mouse_axial_2axis")).payload
        params = ModelParams()
        params.model_id = "mouse_axial_2axis"
        sim = Simulator(payload=payload, params=params, seed=1)
        run = sim.run()
        self.assertEqual(run.phenotype["anatomical"]["tail_count"], 2)
        self.assertEqual(len(run.phenotype["anatomical"]["axes"]), 2)
        self.assertTrue(any(e["operation"] == "AXIS_INITIATE" for e in run.events))
        # basins are independent: two origins, not a cloned scalar
        o0 = tuple(run.phenotype["anatomical"]["axes"][0]["origin"])
        o1 = tuple(run.phenotype["anatomical"]["axes"][1]["origin"])
        self.assertNotEqual(o0, o1)

    def test_B9_default_one_axis_unsatisfied(self):
        p = compile_source(SRC).payload
        self.assertEqual(p["predicted_bundle"]["anatomical"]["tail_count"], 1)
        self.assertEqual(p["target"]["status"], "UNSATISFIED")

    def test_B10_retrieved_fasta_is_acgt(self):
        seqs = load_all()
        self.assertEqual(set(seqs), set(LOCI))
        for rec in seqs.values():
            self.assertGreater(len(rec.sequence), 100)
            self.assertTrue(set(rec.sequence) <= set("ACGTN"))
            self.assertEqual(len(rec.sha256), 64)

    def test_B13_mesh_has_volume(self):
        verts, faces, labels = mesh_from_phenotype({
            "axes": [
                {"origin": [0.7, -0.2, 0.0], "direction": [0.0, 0.0, 1.0], "length": 0.9},
                {"origin": [0.7, 0.2, 0.0], "direction": [0.0, 0.0, 1.0], "length": 0.9},
            ]
        })
        self.assertGreater(len(faces), 20)
        self.assertTrue(any(abs(v[2]) > 1e-6 for v in verts))
        self.assertTrue(any(abs(v[1]) > 1e-6 for v in verts))

    def test_B15_bundle_graph(self):
        with tempfile.TemporaryDirectory() as td:
            result = write_bundle(SRC, Path(td) / "out", seed=1)
            root = Path(result["out"])
            self.assertTrue((root / "genome" / "Fgf8.fa").exists())
            self.assertTrue((root / "genome" / "Fgf8.gb").exists())
            man = json.loads((root / "genome" / "MANIFEST.json").read_text())
            self.assertFalse(man["authorization"]["authorized"])
            self.assertEqual(man["designed_constructs"], [])
            self.assertTrue((root / "phenotype" / "2axis" / "phenotype.stl").exists())
            self.assertTrue((root / "PROVENANCE.json").exists())
            self.assertEqual(result["runtime_2axis_tails"], 2)
            self.assertEqual(result["verdict_1d"]["overall"], "UNSATISFIED")


if __name__ == "__main__":
    unittest.main()
