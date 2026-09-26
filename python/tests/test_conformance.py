"""Conformance suite against the r2 scorecard (C1–C22)."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panini.errors import UnsupportedError
from panini.ontology import CISC_OPCODES, catalog
from panini.pipeline import CompileOptions, compile_source
from panini.simulator.api import Simulator
from panini.stdlib import find, SearchQuery, mouse_axial_library, verify_retrievals

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "examples" / "mouse_axial.panini").read_text()
HEAD = SRC.replace("primary = tail", "primary = head").replace("secondary = tail", "secondary = head")


class Conformance(unittest.TestCase):
    def test_C1_compiled_genotype_exists(self):
        p = compile_source(SRC).payload
        self.assertTrue(p["realization"]["construct_specification"])

    def test_C2_twin_varies_with_intent(self):
        tail = compile_source(SRC).payload
        head = compile_source(HEAD).payload
        self.assertNotEqual(
            tail["simulation_result"]["terminal_phenotype_score"],
            head["simulation_result"]["terminal_phenotype_score"],
        )
        self.assertGreater(tail["simulation_result"]["terminal_phenotype_score"], 0.55)
        self.assertLess(head["simulation_result"]["terminal_phenotype_score"], 0.45)

    def test_C3_contradiction_not_certified(self):
        head = compile_source(HEAD).payload
        self.assertEqual(head["predicted_bundle"]["anatomical"]["primary_axis"], "head")
        self.assertNotEqual(head["verdict"]["overall"], "SATISFIED")  # secondary/head extras may fail

    def test_C4_unknown_backend_is_error(self):
        with self.assertRaises(UnsupportedError):
            compile_source(SRC, CompileOptions(backend="e_coli.k12"))

    def test_C5_source_backend_honoured(self):
        src = SRC.replace("organism Mouse {", "organism Mouse backend e_coli.k12 {")
        with self.assertRaises(UnsupportedError) as ctx:
            compile_source(src)
        self.assertIn("e_coli", ctx.exception.backend)

    def test_C6_no_invented_nucleotides(self):
        p = compile_source(SRC).payload
        for c in p["realization"]["construct_specification"]:
            self.assertIsNone(c.get("sequence"))
            self.assertFalse((c.get("sequence") or "").startswith("ATG"))

    def test_C7_organism_filter(self):
        mouse = find(SearchQuery(organism="mouse"))
        human = find(SearchQuery(organism="human"))
        self.assertTrue(mouse)
        self.assertTrue(all(a.organism == "Mus musculus" for a in mouse))
        self.assertEqual(human, [])

    def test_C8_cisc_defined_only(self):
        self.assertEqual(set(CISC_OPCODES), set(catalog()))
        self.assertGreaterEqual(len(CISC_OPCODES), 60)

    def test_C12_provenance_derived(self):
        a = compile_source(SRC).payload
        b = compile_source(HEAD).payload
        self.assertNotEqual(a["provenance"], b["provenance"])

    def test_C13_retrieval_digest(self):
        self.assertEqual(verify_retrievals(), [])
        for a in mouse_axial_library():
            self.assertIsNotNone(a.retrieval)
            self.assertEqual(a.retrieval.assembly, "GRCm39")
            self.assertTrue(a.retrieval.digest)

    def test_C14_loci_retrieved(self):
        p = compile_source(SRC).payload
        fgf = next(c for c in p["realization"]["construct_specification"] if "Fgf8" in c["artifact_id"])
        self.assertEqual(str(fgf["chrom"]), "19")
        self.assertEqual(int(fgf["start"]), 45725237)
        self.assertEqual(fgf["strand"], "-")

    def test_C15_runtime_varies(self):
        tail = Simulator(payload=compile_source(SRC).payload, seed=1).run()
        head = Simulator(payload=compile_source(HEAD).payload, seed=1).run()
        self.assertEqual(tail.phenotype["anatomical"]["primary_axis"], "tail")
        self.assertEqual(head.phenotype["anatomical"]["primary_axis"], "head")

    def test_C16_target_unsatisfied_for_two_tails(self):
        p = compile_source(SRC).payload
        self.assertEqual(p["target"]["status"], "UNSATISFIED")
        self.assertEqual(p["predicted_bundle"]["anatomical"]["tail_count"], 1)
        tails = [c for c in p["target"]["constraints"] if c["property"] == "tail_count"]
        self.assertTrue(tails)
        self.assertEqual(tails[0]["target"], 2)
        self.assertEqual(tails[0]["observed"], 1)
        self.assertEqual(p["verdict"]["overall"], "UNSATISFIED")

    def test_C17_no_fabricated_mm(self):
        run = Simulator(payload=compile_source(SRC).payload, seed=1).run()
        self.assertNotIn("tail_length_mm", run.phenotype["anatomical"])
        self.assertEqual(run.phenotype["anatomical"].get("axis_extent_units"), "uncalibrated")

    def test_C19_loci_load_bearing(self):
        payload = compile_source(SRC).payload
        wt = Simulator(payload=payload, seed=3)
        wt.run()
        wt_wnt = wt.engine.state.molecular["wnt"].value
        wt_ra = wt.engine.state.molecular["ra"].value
        mut = Simulator(payload=payload, seed=3)
        mut.initialize()
        mut.engine.intervene({"disable(Wnt3a)": True})
        mut.engine.run()
        self.assertGreater(wt_wnt, 0.05)
        self.assertLess(mut.engine.state.molecular["wnt"].value, wt_wnt * 0.2)
        mut2 = Simulator(payload=payload, seed=3)
        mut2.initialize()
        mut2.engine.intervene({"disable(Aldh1a2)": True})
        mut2.engine.run()
        self.assertLess(mut2.engine.state.molecular["ra"].value, wt_ra * 0.2)

    def test_C21_realization_structured(self):
        p = compile_source(SRC).payload
        r = p["realization"]
        self.assertIn("authorization", r)
        self.assertFalse(r["authorization"]["authorized"])
        self.assertEqual(r["assembly_plan"]["format"], "panini.assembly.v0")

    def test_C22_authorization_gate(self):
        p = compile_source(SRC).payload
        self.assertFalse(p["realization"]["authorization"]["authorized"])
        self.assertEqual(p["realization"]["authorization"]["scope"], "specification_only")
        self.assertEqual(p["realization"]["designed_constructs"], [])


if __name__ == "__main__":
    unittest.main()
