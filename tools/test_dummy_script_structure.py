#!/usr/bin/env python3
"""Structural contracts for the large dummy runner entrypoints."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent


class DummyScriptStructureTests(unittest.TestCase):
    def test_legacy_cli_entrypoints_remain_thin_compatibility_wrappers(self) -> None:
        wrappers = {
            "run-dummy-growth-suite.py": "dummy_growth_suite",
            "behavior-dummy-client.py": "behavior_dummy_client",
        }

        for filename, implementation_module in wrappers.items():
            with self.subTest(filename=filename):
                source = (TOOLS / filename).read_text(encoding="utf-8")
                self.assertLessEqual(len(source.splitlines()), 12)
                self.assertIn(f"from {implementation_module} import *", source)
                self.assertIn(f"from {implementation_module} import main", source)
                self.assertNotIn("def run_case(", source)
                self.assertNotIn("def run_dummy_round(", source)

    def test_growth_implementation_owns_orchestration_and_imports_policy_boundaries(self) -> None:
        source = (TOOLS / "dummy_growth_suite.py").read_text(encoding="utf-8")

        self.assertIn("def run_case(", source)
        self.assertIn("from dummy_growth_models import (", source)
        self.assertIn("from dummy_growth_policy import (", source)
        self.assertIn("from dummy_mysql_compat import ", source)
        self.assertNotIn("def target_levels(", source)
        self.assertNotIn("class RoutePoint:", source)
        self.assertNotIn("def windows_argument_path_for_wsl(", source)

    def test_behavior_implementation_owns_round_loop_and_delegates_pure_policy(self) -> None:
        source = (TOOLS / "behavior_dummy_client.py").read_text(encoding="utf-8")

        self.assertIn("def run_dummy_round(", source)
        self.assertIn("dummy_behavior_flee import (", source)
        self.assertIn("dummy_behavior_movement import (", source)
        self.assertNotIn("DAOC_PACKET_SPEED_SCALE =", source)
        self.assertNotIn("def dummy_coerce_world_movement_speed(", source)

    def test_mysql_compat_helpers_have_one_source_of_truth(self) -> None:
        owners = []
        for path in TOOLS.glob("*.py"):
            module = ast.parse(path.read_text(encoding="utf-8-sig", errors="ignore"))
            if any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "windows_argument_path_for_wsl"
                for node in module.body
            ):
                owners.append(path.name)

        self.assertEqual(owners, ["dummy_mysql_compat.py"])


if __name__ == "__main__":
    unittest.main()
