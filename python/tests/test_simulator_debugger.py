import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panini.debugger.predicates import parse_predicate
from panini.debugger.session import DebugSession
from panini.pipeline import compile_source
from panini.simulator.api import Simulator
from panini.simulator.genotype import CompiledGenotype

SRC = Path(__file__).resolve().parents[2] / "examples" / "mouse_axial.panini"
SOURCE = SRC.read_text()


class SimulatorDebugger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = compile_source(SOURCE).payload

    def test_semantic_genotype_not_naked_sequence(self):
        g = CompiledGenotype.from_compile_payload(self.payload)
        self.assertGreaterEqual(len(g.genes), 3)
        for gene in g.genes:
            self.assertTrue(gene.identity.startswith("G"))
            self.assertTrue(gene.sequence_ref.startswith("mgi://"))
            self.assertTrue(gene.locus.identity)

    def test_execution_produces_inspectable_trace(self):
        sim = Simulator(payload=self.payload, seed=1)
        run = sim.run()
        self.assertGreater(len(run.events), 20)
        ops = {e["operation"] for e in run.events}
        for required in {"INIT", "TRANSCRIBE", "TRANSLATE", "REACT", "DIFFERENTIATE", "DEVELOP"}:
            self.assertIn(required, ops)
        self.assertGreater(run.phenotype["anatomical"]["tail_count"], 0)
        self.assertEqual(run.phenotype["anatomical"]["primary_axis"], "tail")
        # V8 compares declared tail_count=2 to observed 1 — must be allowed to fail
        self.assertTrue(run.verification["compiled_true_is_not_biologically_validated"])

    def test_disable_locus_changes_phenotype(self):
        wild = Simulator(payload=self.payload, seed=7)
        wild.run()
        wild_score = wild.engine.state.molecular["tail_identity"].value

        mut = Simulator(payload=self.payload, seed=7)
        mut.initialize()
        # disable posterior identity + posteriorizing signals
        for g in list(mut.genotype.genes):
            mut.engine.intervene({f"disable({g.symbol})": True})
        mut.engine.run()
        mut_score = mut.engine.state.molecular["tail_identity"].value
        self.assertLess(mut_score, wild_score)
        self.assertLess(mut_score, 0.6)

    def test_breakpoint_and_time_travel(self):
        sim = Simulator(payload=self.payload, seed=2)
        sess = DebugSession(sim)
        sess.exec("break developmental_state == tail_bud")
        sess.exec("run")
        self.assertTrue(sim.engine.paused or sim.engine.state.stage == "tail_bud" or sim.engine.halted)
        sess.exec("checkpoint CP_TEST")
        t0 = sim.engine.state.time
        sess.exec("continue")
        self.assertGreaterEqual(sim.engine.state.time, t0)
        sess.exec("restore CP_TEST")
        self.assertAlmostEqual(sim.engine.state.time, t0, places=5)

    def test_causal_trace_and_explain(self):
        sim = Simulator(payload=self.payload, seed=3)
        sim.initialize()
        for _ in range(30):
            sim.step_event()
        sess = DebugSession(sim)
        fwd = sess.exec("trace-forward Wnt3a")
        self.assertIn("transcribes", fwd)
        back = sess.exec("trace-backward phenotype.tail")
        self.assertIn("caused-by", back)
        ev = sim.engine.log.events[-1].event_id
        expl = sess.exec(f"explain-event {ev}")
        self.assertIn("PANINI", expl)

    def test_predicates(self):
        sim = Simulator(payload=self.payload, seed=1)
        sim.initialize()
        pred = parse_predicate("phenotype.tail_count != 2")
        self.assertTrue(pred(sim.engine.state))
        pred2 = parse_predicate("time >= 0")
        self.assertTrue(pred2(sim.engine.state))

    def test_run_is_reproducible(self):
        a = Simulator(payload=self.payload, seed=11).run()
        b = Simulator(payload=self.payload, seed=11).run()
        self.assertEqual(a.run_id, b.run_id)
        self.assertEqual(a.terminal_state["hash"], b.terminal_state["hash"])

    def test_disk_roundtrip(self):
        sim = Simulator(payload=self.payload, seed=4)
        run = sim.run()
        with tempfile.TemporaryDirectory() as td:
            dest = run.write(Path(td))
            from panini.simulator.run import SimulationRun
            loaded = SimulationRun.read(dest)
            self.assertEqual(loaded.run_id, run.run_id)
            self.assertEqual(len(loaded.events), len(run.events))


if __name__ == "__main__":
    unittest.main()
