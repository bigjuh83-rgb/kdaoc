#!/usr/bin/env python3
"""Unit checks for dummy movement trace analysis."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


def load_module():
    module_path = Path(__file__).with_name("analyze-dummy-movement-traces.py")
    spec = importlib.util.spec_from_file_location("analyze_dummy_movement_traces_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class MovementTraceAnalysisTests(unittest.TestCase):
    def write_trace(self, directory: Path, name: str, rows: list[dict]) -> Path:
        path = directory / name
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        return path

    def test_analyzes_observed_teleport_and_z_spike(self):
        analyzer = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_trace(
                root,
                "dummy400.jsonl",
                [
                    {"event": "observe_player_position", "name": "dummy401", "horizontal_delta": "120.0", "delta_z": 10},
                    {"event": "observe_player_position", "name": "dummy401", "horizontal_delta": "950.0", "delta_z": 20},
                    {"event": "observe_player_position", "name": "dummy402", "horizontal_delta": "180.0", "delta_z": -310},
                    {
                        "event": "observe_self_position",
                        "previous_x": 100,
                        "previous_y": 100,
                        "previous_z": 10,
                        "horizontal_delta": "40.0",
                        "delta_z": 5,
                    },
                    {
                        "event": "observe_self_position",
                        "previous_x": 140,
                        "previous_y": 100,
                        "previous_z": 15,
                        "horizontal_delta": "880.0",
                        "delta_z": 15,
                    },
                ],
            )

            result = analyzer.analyze_paths([root / "*.jsonl"], teleport_threshold=800.0, z_threshold=250.0)

        self.assertEqual(result["files"], 1)
        self.assertEqual(result["observed_samples"], 3)
        self.assertEqual(result["observed_teleports"], 1)
        self.assertEqual(result["observed_z_spikes"], 1)
        self.assertEqual(result["self_position_samples"], 2)
        self.assertEqual(result["self_snaps"], 1)
        self.assertAlmostEqual(result["observed_horizontal_max"], 950.0)
        self.assertAlmostEqual(result["observed_abs_z_max"], 310.0)

    def test_writes_markdown_summary(self):
        analyzer = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            trace = self.write_trace(
                root,
                "dummy400.jsonl",
                [{"event": "observe_player_position", "name": "dummy401", "horizontal_delta": "100.0", "delta_z": 8}],
            )
            result = analyzer.analyze_paths([trace], teleport_threshold=800.0, z_threshold=250.0)
            report_path = root / "movement.md"
            analyzer.write_markdown(report_path, result)

            report = report_path.read_text(encoding="utf-8")

        self.assertIn("# Dummy Movement Trace Analysis", report)
        self.assertIn("Observed samples: `1`", report)
        self.assertIn("Severe observed teleports: `0`", report)

    def test_ignores_initial_self_position_snap_from_origin(self):
        analyzer = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_trace(
                root,
                "dummy400.jsonl",
                [
                    {
                        "event": "observe_self_position",
                        "previous_x": 0,
                        "previous_y": 0,
                        "previous_z": 0,
                        "horizontal_delta": "667142.0",
                        "delta_z": 4868,
                    },
                    {
                        "event": "observe_self_position",
                        "previous_x": 561900,
                        "previous_y": 357450,
                        "previous_z": 4868,
                        "horizontal_delta": "40.0",
                        "delta_z": 4,
                    },
                ],
            )

            result = analyzer.analyze_paths([root / "*.jsonl"], teleport_threshold=800.0, z_threshold=250.0)

        self.assertEqual(result["self_position_samples"], 1)
        self.assertEqual(result["self_snaps"], 0)


if __name__ == "__main__":
    unittest.main()
