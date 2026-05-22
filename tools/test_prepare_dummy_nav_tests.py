#!/usr/bin/env python3
"""Unit checks for dummy nav test command preparation."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


def load_module():
    module_path = Path(__file__).with_name("prepare-dummy-nav-tests.py")
    spec = importlib.util.spec_from_file_location("prepare_dummy_nav_tests_for_tests", module_path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


navtests = load_module()


class PrepareDummyNavTests(unittest.TestCase):
    def test_grid_on_command_contains_trace_and_client_grid_flags(self):
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            accounts="tools/dummy-accounts.csv",
            concurrency=1,
            hold=300,
            char_index=0,
            movement_speed=191.0,
            interval=0.20,
            cell_size=256,
            max_step_z=240,
            fixture_padding=160,
        )

        command = navtests.build_behavior_command(args, navtests.PROFILES["salisbury-slope"], grid=True)

        self.assertIn("--client-grid-nav-map", command)
        self.assertIn("--ground-z-map", command)
        self.assertIn("--trace-movement-log", command)
        self.assertIn("tools/pathing/heightmaps/region001_client_zones.json", command)
        self.assertIn("--server-correction-smoothing", command)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
