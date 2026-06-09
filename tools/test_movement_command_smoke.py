#!/usr/bin/env python3
"""Focused tests for the movement-command companion smoke."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path


TOOLS = Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


smoke = load_module("run_movement_command_smoke_for_tests", "run-movement-command-smoke.py")


def make_args(**overrides) -> Namespace:
    values = {
        "host": "127.0.0.1",
        "port": 10300,
        "leader_account": "dummy001",
        "leader_name": "Dummy001",
        "companion_account": "dummy002",
        "companion_name": "Dummy002",
        "password": "dummy-pass",
        "realm": 1,
        "hold": 45.0,
        "leader_startup_delay": 4.0,
        "movement_speed": 191.0,
        "movement_update_interval": 0.2,
        "party_follow_distance": 450.0,
        "party_follow_catchup_distance": 900.0,
        "party_follow_hard_catchup_distance": 1600.0,
        "party_follow_teleport_distance": 2500.0,
        "party_follow_teleport_stop_distance": 120.0,
        "command_gap": 3.0,
        "commands": ["따라와", "대기", "여기로", "소환"],
        "waypoints": smoke.DEFAULT_WAYPOINTS,
        "trace_observed_player_positions": True,
    }
    values.update(overrides)
    return Namespace(**values)


class MovementCommandSmokeTests(unittest.TestCase):
    def test_leader_command_is_movement_only_and_live_controlled(self) -> None:
        command = smoke.build_leader_command(make_args(), Path("case"))

        self.assertIn("--move", command)
        self.assertIn("--live-control-file", command)
        self.assertIn("--trace-movement-log", command)
        self.assertNotIn("--hunter", command)
        self.assertNotIn("--combat", command)
        self.assertNotIn("--target-selection", command)

    def test_companion_command_enables_chat_commands_and_noncombat_catchup_policy(self) -> None:
        command = smoke.build_companion_command(make_args(), Path("case"))

        self.assertIn("--companion-chat-reply", command)
        self.assertIn("--follow-nearby-player", command)
        self.assertEqual(command[command.index("--follow-player-name") + 1], "Dummy001")
        self.assertEqual(command[command.index("--party-follow-teleport-distance") + 1], "2500")
        self.assertNotIn("--hunter", command)
        self.assertNotIn("--combat", command)

    def test_movement_summary_fails_on_forbidden_movement_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "companion").mkdir()
            (run_dir / "companion" / "encounters.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"event": "companion_command_mode_change", "intent": "wait", "mode": "stay"}),
                        json.dumps({"event": "attack_decision", "actions": {"companion_command_stay_hold": 1}}),
                        json.dumps({"event": "attack_decision", "actions": {"party_follow_teleport_catchup": 1}}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "companion" / "movement.jsonl").write_text(
                json.dumps(
                    {
                        "event": "observe_player_position",
                        "name": "Dummy001",
                        "horizontal_delta": 1400,
                        "delta_z": 380,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            summary = smoke.summarize_movement_command_run(
                run_dir,
                teleport_threshold=800.0,
                z_threshold=250.0,
                repeat_rewind_threshold=2,
            )

        self.assertFalse(summary["ok"])
        self.assertIn("stay mode following", summary["failures"])
        self.assertIn("combat catchup or teleport", summary["failures"])
        self.assertIn("near follow teleport", summary["failures"])
        self.assertIn("excessive Z mismatch", summary["failures"])

    def test_live_control_payloads_cover_required_korean_commands(self) -> None:
        payloads = smoke.leader_command_payloads(make_args())

        self.assertEqual([payload["say_text"] for payload in payloads], ["따라와", "대기", "여기로", "소환"])
        self.assertTrue(all(payload["say_channel"] == "party" for payload in payloads))
        self.assertEqual([payload["revision"] for payload in payloads], ["cmd-001", "cmd-002", "cmd-003", "cmd-004"])

    def test_summary_includes_server_movement_audit_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "movement-audit-Dummy002.jsonl").write_text(
                json.dumps(
                    {
                        "event": "c2s_position",
                        "player": "Dummy002",
                        "horizontalDelta": 1200,
                        "deltaZ": 320,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            summary = smoke.summarize_movement_command_run(
                run_dir,
                teleport_threshold=800.0,
                z_threshold=250.0,
                repeat_rewind_threshold=1,
            )

        self.assertEqual(summary["server_audit"]["files"], 1)
        self.assertEqual(summary["server_audit"]["samples"], 1)
        self.assertEqual(summary["server_audit"]["rewinds"], 1)
        self.assertEqual(summary["server_audit"]["z_spikes"], 1)
        self.assertIn("large repeated rewind", summary["failures"])
        self.assertIn("excessive Z mismatch", summary["failures"])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
