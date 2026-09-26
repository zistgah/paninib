# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""v0.9 engine tests. Fixtures are fixtures. Models are labelled models."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panini.constraint_graph import ConstraintGraph, ConstraintNode, GraphEdge
from panini.engines.animation_engine import AnimationEngine
from panini.engines.biochemical import BiochemicalEngine, fixture_abc
from panini.engines.cellular import CellularEngine
from panini.engines.developmental import DevelopmentalEngine
from panini.engines.execution import biochemical_model
from panini.engines.fields import fixture_gradient_1d
from panini.engines.generative import GenerativeSequenceEngine
from panini.engines.geometry_engine import MeshEngine, ParametricGeometryEngine, PointCloudEngine, VoxelEngine
from panini.engines.gpu import GPUBackend, cpu_gpu_equivalence_fixture, detect_cuda
from panini.engines.inverse_engine import FixtureInverseStrategyProvider, InverseResolutionEngine
from panini.engines.maturity import profile_for_axial_twin
from panini.engines.phenotype_engine import PhenotypeEngine
from panini.engines.physiology import PhysiologicalEngine, fixture_tank
from panini.engines.reaction_diffusion import fixture_source_decay
from panini.engines.realization import RealizationPlanningEngine
from panini.engines.reference import ReferenceGenomeEngine
from panini.engines.sequence import SequenceEngine
from panini.engines.solver import ConstraintSolver
from panini.engines.state import MultiscaleStateEngine, STATE_LAYERS
from panini.engines.taxonomy import CapabilityClass, classify_component, inventory
from panini.engines.trace import ArtifactDebugger
from panini.engines.transitions import TransitionEngine, TransitionSpec
from panini.engines.vertical import digital_vertical_slice, physical_vertical_slice
from panini.fixtures_v08 import CASE_SOURCES
from panini.frontend import parse_source
from panini.providers import fixture_cassette_provider, UnavailableGenerativeProvider
from panini.resolution import compile_intent_genotype
from panini.version import COMPILER_VERSION


class Taxonomy(unittest.TestCase):
    def test_adapter_not_engine(self):
        self.assertEqual(classify_component("SimulatorDigitalBackend")["class"], CapabilityClass.ADAPTER.value)

    def test_gpu_not_claimed(self):
        self.assertEqual(classify_component("GPUBackend")["status"], "Unavailable")

    def test_ssa_scaffolded(self):
        rec = classify_component("SSA_stochastic")
        self.assertIn(rec["status"], {"Implemented", "Scaffolded / Contract only"})
        self.assertIn(rec["class"], {"ENGINE", "CONTRACT"})

    def test_inventory_populated(self):
        self.assertGreaterEqual(len(inventory()), 20)


class StateAndTransitions(unittest.TestCase):
    def test_layers_exist(self):
        for layer in STATE_LAYERS:
            self.assertTrue(layer)

    def test_extensible_layer(self):
        st = MultiscaleStateEngine().initialize(epigenetic={"methyl": 0.1})
        self.assertEqual(st.layer("epigenetic")["methyl"], 0.1)

    def test_deterministic_trajectory(self):
        s0 = MultiscaleStateEngine().initialize(molecular={"x": 1.0}, seed=3)

        def fn(st, ctx):
            nxt = st.copy()
            nxt.molecular = {"x": float(st.molecular["x"]) * 0.5}
            return nxt

        spec = TransitionSpec(kind="deterministic", name="half", dt=0.1, seed=3)
        traj = TransitionEngine(spec, fn).integrate(s0, 4)
        again = TransitionEngine(spec, fn).integrate(s0, 4)
        self.assertEqual(len(traj.states), 5)
        self.assertEqual(traj.states[-1]["digest"], again.states[-1]["digest"])


class Biochemical(unittest.TestCase):
    def test_abc_conserves_mass_approximately(self):
        traj = BiochemicalEngine(fixture_abc(k1=1.0, k2=0.5, a0=1.0)).integrate(dt=0.02, t_end=4.0, seed=1)
        last = traj.states[-1]["molecular"]
        self.assertAlmostEqual(last["A"] + last["B"] + last["C"], 1.0, places=2)
        self.assertGreater(last["C"], last["A"])

    def test_regulatory_parameter(self):
        slow = BiochemicalEngine(fixture_abc(k1=0.1, k2=0.1, a0=1.0)).integrate(dt=0.05, t_end=1.0, seed=1, regulatory={"k1": 0.05})
        fast = BiochemicalEngine(fixture_abc(k1=0.1, k2=0.1, a0=1.0)).integrate(dt=0.05, t_end=1.0, seed=1, regulatory={"k1": 2.0})
        self.assertGreater(fast.states[-1]["molecular"]["B"] + fast.states[-1]["molecular"]["C"], slow.states[-1]["molecular"]["B"] + slow.states[-1]["molecular"]["C"])

    def test_reproducible(self):
        a = BiochemicalEngine().integrate(dt=0.05, t_end=1.0, seed=9)
        b = BiochemicalEngine().integrate(dt=0.05, t_end=1.0, seed=9)
        self.assertEqual(a.states[-1]["digest"], b.states[-1]["digest"])


class GPUBoundary(unittest.TestCase):
    def test_detection_unavailable(self):
        det = detect_cuda()
        gpu = GPUBackend()
        self.assertIn(det["status"], {"AVAILABLE", "UNAVAILABLE"})
        if not det["available"]:
            self.assertFalse(gpu.device().available)
            res = gpu.execute(biochemical_model(), {"seed": 1})
            self.assertFalse(res.available)
            self.assertIn("unavailable", res.note.lower())

    def test_cpu_equivalence_protocol(self):
        report = cpu_gpu_equivalence_fixture()
        self.assertTrue(report["cpu_self_equivalent"])
        self.assertEqual(report["precision"], "float64")
        self.assertTrue(report["result_digest"])


class FieldsAndRD(unittest.TestCase):
    def test_field_ops(self):
        f = fixture_gradient_1d(11)
        self.assertAlmostEqual(f.sample(0), 0.0, places=6)
        self.assertAlmostEqual(f.sample(10), 1.0, places=6)
        mid = f.interpolate(0.5, 0.0, 0.0)
        self.assertGreater(mid, 0.3)
        self.assertLess(mid, 0.7)
        self.assertTrue(f.gradient().components)
        self.assertEqual(f.threshold(0.5).sample(10), 1.0)
        self.assertEqual(f.threshold(0.5).sample(0), 0.0)
        self.assertGreaterEqual(f.combine(f.threshold(0.5), "mul").sample(10), 0.5)

    def test_rd_fixture(self):
        out = fixture_source_decay()
        self.assertTrue(out["frames"] and out["checkpoints"] and out["digest"])
        self.assertEqual(out["digest"], fixture_source_decay()["digest"])


class CellularDev(unittest.TestCase):
    def test_cellular_fixture(self):
        out = CellularEngine().run_fixture()
        self.assertGreaterEqual(len(out["cells"]), 7)
        self.assertTrue(any(e["event"] == "division" for e in out["events"]))
        self.assertGreaterEqual(out["history"][-1]["n_diff"], 1)

    def test_developmental_spatial(self):
        out = DevelopmentalEngine().run_spatial_fixture(steps=6)
        self.assertTrue(out["trajectory"])
        self.assertIn("anatomical_state", out["final"])
        self.assertFalse(out["maturity"]["experimentally_validated"])

    def test_maturation_frames(self):
        out = DevelopmentalEngine().run_maturation(5)
        self.assertEqual(len(out["frames"]), 5)
        self.assertEqual(out["frames"][-1]["stage"], "mature")
        self.assertGreater(out["frames"][-1]["observables"]["length"], out["frames"][0]["observables"]["length"])


class PhenotypePhys(unittest.TestCase):
    def test_separation(self):
        eng = PhenotypeEngine()
        bundle = eng.bundle(desired={"C": 1.0}, predicted=eng.from_molecular({"C": 0.8}))
        self.assertEqual(bundle["desired"]["kind"], "desired")
        self.assertEqual(bundle["predicted"]["kind"], "predicted")
        self.assertIsNone(bundle["observed"])

    def test_physiology_tank(self):
        out = PhysiologicalEngine().run(fixture_tank(volume0=1.0, inflow=0.2, leak=0.1), steps=15, molecular_input={"solute_in": 0.05})
        self.assertIn("volume", out["observables"])
        self.assertIn("not_modeled", out["descriptor"])
        self.assertFalse(out["descriptor"]["maturity"]["experimentally_validated"])


class GeometryAnim(unittest.TestCase):
    def test_parametric_to_all_reps(self):
        axis = ParametricGeometryEngine().from_phenotype_params({"tail_count": 2, "length": 1.0})
        pts = ParametricGeometryEngine().sample_points(axis)
        self.assertGreaterEqual(len(pts), 22)
        cloud = PointCloudEngine().materialize(pts, phenotype_ref="p", spatial_ref="s")
        self.assertEqual(cloud.kind, "point_cloud")
        vx = VoxelEngine().from_axis(axis)
        self.assertEqual(vx.kind, "voxels")
        self.assertGreater(vx.payload["occupied"], 0)
        mesh = MeshEngine().from_axis(axis)
        self.assertEqual(mesh.kind, "mesh")
        self.assertTrue(mesh.payload["faces"])

    def test_animation_from_dev(self):
        dev = DevelopmentalEngine().run_maturation(4)
        traj = AnimationEngine().from_maturation(dev["frames"])
        anim = AnimationEngine().animate(traj)
        self.assertIn("time", anim.to_dict())
        self.assertEqual(AnimationEngine().export_gltf_min(traj)["asset"]["version"], "2.0")


class ReferenceSequence(unittest.TestCase):
    def test_demo_and_retrieved_loci(self):
        eng = ReferenceGenomeEngine()
        ref = eng.resolve_sequence("demo-v1", "chrDemo")
        self.assertEqual(ref.sequence, "AACCGGTTAACC")
        self.assertTrue(eng.verify_digest(ref, ref.digest))
        self.assertEqual(eng.retrieve_interval("demo-v1", "chrDemo", 0, 4), "AACC")
        self.assertIn("chrDemo", eng.list_loci())
        self.assertTrue(any(sid != "chrDemo" for sid in eng.list_loci()))

    def test_sequence_engine_apply(self):
        eng = SequenceEngine()
        ref = ReferenceGenomeEngine().resolve_sequence("demo-v1", "chrDemo")
        derived = eng.apply(ref, eng.normalize_edits([{"operation": "REPLACE", "start": 4, "end": 8, "replacement": "TTTT"}]))
        self.assertEqual(derived.sequence, "AACCTTTTAACC")
        self.assertIn("AACCTTTTAACC", eng.fasta(derived))
        self.assertIn("ORIGIN", eng.genbank_min(derived))


class GenerativeInverseSolver(unittest.TestCase):
    def test_generative_unavailable_does_not_invent(self):
        out = GenerativeSequenceEngine(UnavailableGenerativeProvider()).pipeline(type("C", (), {"intent_name": "x", "constraint_id": "c"})())
        self.assertEqual(out["status"], "UNAVAILABLE")
        self.assertIsNone(out["candidate"])

    def test_generative_fixture_pipeline(self):
        out = GenerativeSequenceEngine(fixture_cassette_provider()).pipeline(type("C", (), {"intent_name": "model_marker", "constraint_id": "c1"})())
        self.assertEqual(out["status"], "CANDIDATE")
        self.assertNotEqual(out["candidate"]["validation_status"], "VERIFIED")

    def test_inverse_fixture_licensed(self):
        cand = InverseResolutionEngine(FixtureInverseStrategyProvider()).resolve(association_record={"association_class": "CAUSALLY_SUPPORTED", "direction": "gof", "fixture_inverse_ok": True, "wanted_direction": "lof", "assembly": "demo-v1", "reference": "chrDemo"}, causal_evidence=["fixture"], desired_direction="lof")
        self.assertEqual(cand.inverse["status"], "LICENSED")
        self.assertTrue(cand.candidate_realization.get("edits"))
        self.assertEqual(cand.validation_state, "NOT_VALIDATED")

    def test_inverse_association_blocked(self):
        cand = InverseResolutionEngine().resolve(association_record={"association_class": "ASSOCIATED", "direction": "gof"}, causal_evidence=[], desired_direction="lof")
        self.assertEqual(cand.inverse["status"], "NOT_LICENSED")
        self.assertFalse(cand.candidate_realization)

    def test_solver_and_coverage(self):
        g = ConstraintGraph(program_id="p")
        g.add_node(ConstraintNode("a", "RESOLVED"))
        g.add_node(ConstraintNode("b", "UNRESOLVED"))
        g.add_node(ConstraintNode("c", "MODEL_DERIVED"))
        g.add_edge(GraphEdge("a", "b", "DEPENDENCY"))
        d = ConstraintSolver().solve(g).to_dict()
        self.assertIn("a", d["resolved_constraints"])
        self.assertEqual(d["coverage"]["total_declared"], 3)


class RealizationAndVerify(unittest.TestCase):
    def test_physical_plan_on_compiled_design(self):
        payload = compile_intent_genotype(CASE_SOURCES["case1_direct"], parse_source(CASE_SOURCES["case1_direct"]))
        plan = RealizationPlanningEngine().plan(payload["genotype_design"])
        self.assertEqual(plan["status"], "PLANNED")
        self.assertTrue(plan["derived_sequence"])
        self.assertTrue(RealizationPlanningEngine().verify_plan(plan)["overall_pass"])

    def test_physical_plan_unresolved(self):
        payload = compile_intent_genotype(CASE_SOURCES["case5_unavailable"], parse_source(CASE_SOURCES["case5_unavailable"]))
        plan = RealizationPlanningEngine().plan(payload["genotype_design"])
        self.assertEqual(plan["status"], "PLAN_UNAVAILABLE")
        self.assertFalse(plan["derived_sequence"])


class Vertical(unittest.TestCase):
    def test_digital_slice(self):
        out = digital_vertical_slice()
        self.assertEqual(out["resolution_status"], "COMPILED")
        self.assertTrue(out["derived_sequence"])
        self.assertIn("C", out["biochemical_observables"])
        self.assertTrue(out["geometry"]["point_cloud"]["payload"]["points"])
        self.assertEqual(out["geometry"]["voxels"]["kind"], "voxels")
        self.assertEqual(out["geometry"]["mesh"]["kind"], "mesh")
        self.assertTrue(out["animation"]["frames"])
        self.assertTrue(out["verification"]["overall_pass"])
        self.assertIn("intent", out["trace"]["layers"])

    def test_physical_slice(self):
        out = physical_vertical_slice()
        self.assertEqual(out["plan"]["status"], "PLANNED")
        self.assertEqual(out["physical"]["status"], "REALIZED")
        self.assertTrue(out["plan_verification"]["overall_pass"])
        self.assertTrue(out["physical_verification"]["overall_pass"])

    def test_maturity_structured(self):
        p = profile_for_axial_twin()
        self.assertEqual(p.level, "DT-3")
        self.assertFalse(p.experimentally_validated)

    def test_version(self):
        self.assertTrue(COMPILER_VERSION.startswith("1.") or COMPILER_VERSION.startswith("0.9"))


class DebuggerTrace(unittest.TestCase):
    def test_reverse_inspect(self):
        dbg = ArtifactDebugger()
        steps = dbg.build_forward([{"layer": "intent", "id": "i"}, {"layer": "design", "id": "d"}, {"layer": "phenotype", "id": "p"}])
        rev = dbg.inspect_reverse(steps, "phenotype")
        self.assertEqual(rev[0].layer, "phenotype")
        self.assertEqual(rev[-1].layer, "intent")


if __name__ == "__main__":
    unittest.main()
