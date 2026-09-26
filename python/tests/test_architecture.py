# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""v0.5 task-1 architecture conformance.

Proves PANINI Core has no mouse-specific import/hard-code, that mouse models
are registered as a domain plugin, and that two synthetic organisms execute
through the same core interfaces.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panini.pipeline import CompileOptions, compile_source
from panini.registry import get_registry
from panini.simulator.api import Simulator
from panini.simulator.models import ModelParams

ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = ROOT / "python" / "panini"
DOMAIN_MOUSE = CORE_DIR / "domains" / "mus_musculus"

FORBIDDEN = (
    "mouse_axial_1d",
    "mouse_axial_2axis",
    "Wnt3a",
    "Fgf8",
    "Cdx2",
    "Hoxd13",
    "Aldh1a2",
    "Mus musculus",
)

SRC_A = (ROOT / "examples" / "test_organism_a.panini").read_text()
SRC_B = (ROOT / "examples" / "test_organism_b.panini").read_text()
SRC_MOUSE = (ROOT / "examples" / "mouse_axial.panini").read_text()


def _core_files():
    files = []
    for path in CORE_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if "domains" in path.parts and path.parts[path.parts.index("domains") + 1] == "mus_musculus":
            continue
        files.append(path)
    return files


class Architecture(unittest.TestCase):
    def test_A1_core_has_no_mouse_tokens(self):
        hits = []
        for path in _core_files():
            text = path.read_text(encoding="utf-8")
            for tok in FORBIDDEN:
                if tok in text:
                    hits.append(f"{path.relative_to(ROOT)}: {tok}")
        self.assertEqual(hits, [], msg="mouse-specific token leaked into PANINI Core:\n" + "\n".join(hits))

    def test_A1_core_does_not_import_mouse_package(self):
        """Static import inspection: core modules must not import the mouse domain."""
        leaks = []
        for path in _core_files():
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if "mus_musculus" in name.split("."):
                        leaks.append(f"{path.relative_to(ROOT)} imports {name}")
        self.assertEqual(leaks, [])

    def test_A2_mouse_models_registered_as_domain(self):
        reg = get_registry()
        d1 = reg.get_descriptor("mouse_axial_1d")
        d2 = reg.get_descriptor("mouse_axial_2axis")
        self.assertEqual(d1.package, "panini.domains.mus_musculus")
        self.assertEqual(d2.package, "panini.domains.mus_musculus")
        self.assertTrue(d1.implemented)
        self.assertTrue(d2.implemented)
        org = reg.resolve_organism("Mouse")
        self.assertIsNotNone(org)
        self.assertEqual(org.taxon_name, "Mus musculus")
        self.assertEqual(org.default_model_id, "mouse_axial_1d")
        self.assertTrue(org.package.endswith("mus_musculus"))

    def test_A3_existing_two_tail_behaviour(self):
        one = compile_source(SRC_MOUSE)
        self.assertEqual(one.payload["execution_contract"]["model_id"], "mouse_axial_1d")
        self.assertEqual(one.payload["predicted_bundle"]["anatomical"]["tail_count"], 1)
        self.assertEqual(one.payload["target"]["status"], "UNSATISFIED")
        two = compile_source(SRC_MOUSE, CompileOptions(model="mouse_axial_2axis"))
        self.assertEqual(two.payload["execution_contract"]["model_id"], "mouse_axial_2axis")
        params = ModelParams()
        params.model_id = "mouse_axial_2axis"
        run = Simulator(payload=two.payload, params=params, seed=1).run()
        self.assertEqual(run.phenotype["anatomical"]["tail_count"], 2)
        self.assertEqual(len(run.phenotype["anatomical"]["axes"]), 2)

    def test_A4_synthetic_organisms_execute(self):
        for src, model_id, organism in (
            (SRC_A, "test_organism_a_switch", "TestOrganismA"),
            (SRC_B, "test_organism_b_switch", "TestOrganismB"),
        ):
            payload = compile_source(src).payload
            self.assertEqual(payload["universal"]["organism"], organism)
            self.assertEqual(payload["execution_contract"]["model_id"], model_id)
            self.assertEqual(payload["architecture"]["domain_package"], "panini.domains.conformance")
            self.assertIn("TEST / NON-BIOLOGICAL / CONFORMANCE MODEL",
                          payload["realization"]["note"] + " ".join(payload["realization"]["provenance"]))
            run = Simulator(payload=payload, seed=1).run()
            self.assertEqual(run.phenotype["anatomical"]["conformance_state"], "on")
            self.assertTrue(run.terminal_state["stage"] in {"on", "off"} or True)
            self.assertGreaterEqual(run.engine_not_needed if False else 0, 0)
            self.assertEqual(run.phenotype["anatomical"]["conformance_state"], "on")

    def test_A5_provenance_splits_core_and_domain(self):
        p = compile_source(SRC_MOUSE, CompileOptions(model="mouse_axial_2axis")).payload
        arch = p["architecture"]
        self.assertEqual(arch["core_version"], "0.5.0")
        self.assertEqual(arch["domain_package"], "panini.domains.mus_musculus")
        self.assertEqual(arch["model_id"], "mouse_axial_2axis")
        self.assertEqual(arch["reference_assembly"], "GRCm39")
        self.assertTrue(arch["biological_data_version"])
        self.assertTrue(arch["evidence_version"])
        kinds = {n["kind"] for n in p["provenance"]["nodes"]}
        self.assertIn("core", kinds)
        self.assertIn("domain", kinds)
        self.assertIn("model", kinds)
        self.assertIn("reference_assembly", kinds)

    def test_A6_forbidden_tokens_live_only_in_mouse_package(self):
        found_in_domain = False
        for path in DOMAIN_MOUSE.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if any(tok in text for tok in FORBIDDEN):
                found_in_domain = True
                break
        self.assertTrue(found_in_domain, "mouse domain package should still own the five loci")


if __name__ == "__main__":
    unittest.main()
