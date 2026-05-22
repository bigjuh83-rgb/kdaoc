#!/usr/bin/env python3
"""Unit checks for paired dummy Z/movement comparison."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


def load_module():
    module_path = Path(__file__).with_name("run-dummy-z-pair-check.py")
    spec = importlib.util.spec_from_file_location("run_dummy_z_pair_check_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


zpair = load_module()


class DummyZPairCheckTests(unittest.TestCase):
    def test_duplicate_cycle_creates_same_class_pairs(self) -> None:
        self.assertEqual(zpair.duplicate_cycle("1|2|3", 2), "1|1|2|2")
        self.assertEqual(zpair.duplicate_spec_cycle("A||B||C", 2), "A||A||B||B")

    def test_build_pair_profile_duplicates_first_classes(self) -> None:
        profile = zpair.build_pair_profile("alb", 2)

        self.assertTrue(profile.class_cycle.startswith("1|1|2|2"))
        self.assertTrue(profile.spec_cycle.split("||")[0] == profile.spec_cycle.split("||")[1])

    def test_unique_output_dir_includes_realm_and_avoids_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = zpair.unique_output_dir(root, "mid", 1)
            first.mkdir(parents=True)
            second = zpair.unique_output_dir(root, "mid", 1)

        self.assertIn("mid-pairs1", first.name)
        self.assertTrue(second.name.endswith("-2"))

    def test_compare_trace_pair_reports_z_and_xy_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            left = Path(temp_dir) / "left.jsonl"
            right = Path(temp_dir) / "right.jsonl"
            left.write_text(
                "\n".join(
                    json.dumps(row)
                    for row in [
                        {"event": "move_step", "x": 100, "y": 100, "z": 1000, "z_source": "ground_z_sampler"},
                        {"event": "move_step", "x": 200, "y": 100, "z": 1010, "z_source": "ground_z_sampler"},
                        {"event": "ground_z_sample", "x": 200, "y": 100, "z": 1010},
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            right.write_text(
                "\n".join(
                    json.dumps(row)
                    for row in [
                        {"event": "move_step", "x": 110, "y": 100, "z": 990, "z_source": "ground_z_sampler"},
                        {"event": "move_step", "x": 210, "y": 100, "z": 1000, "z_source": "interpolated"},
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = zpair.compare_trace_pair(left, right)

        self.assertEqual(summary["samples"], 2)
        self.assertEqual(summary["max_abs_z_delta"], 10)
        self.assertEqual(summary["avg_xy_delta"], 10)
        self.assertEqual(summary["ground_z_sample_events"], 1)
        self.assertEqual(summary["ground_z_sampler_moves"], 3)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
