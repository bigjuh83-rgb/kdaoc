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
        "api_url": "http://localhost:5000",
        "api_timeout": 5.0,
        "api_password": "",
        "leader_account": "dummy001",
        "leader_name": "Dummy001",
        "companion_account": "dummy002",
        "companion_name": "Dummy002",
        "password": "dummy-pass",
        "leader_password": "dummy-pass",
        "companion_password": "dummy-pass",
        "accounts_csv": "",
        "realm": 1,
        "hold": 45.0,
        "leader_startup_delay": 4.0,
        "movement_speed": 191.0,
        "movement_update_interval": 0.2,
        "party_follow_distance": 450.0,
        "party_follow_catchup_distance": 900.0,
        "party_follow_hard_catchup_distance": 1600.0,
        "party_follow_teleport_distance": 0.0,
        "party_follow_teleport_stop_distance": 120.0,
        "reset_start_position": True,
        "leader_start_anchor": smoke.DEFAULT_LEADER_START_ANCHOR,
        "companion_start_anchor": smoke.DEFAULT_COMPANION_START_ANCHOR,
        "start_position_api_retries": 3,
        "start_position_api_retry_delay": 0.75,
        "command_gap": 3.0,
        "commands": ["따라와", "대기", "여기로", "소환"],
        "command_channel": "party",
        "group_before_commands": True,
        "group_setup_timeout": 20.0,
        "group_confirm_timeout": 10.0,
        "live_control_apply_timeout": 8.0,
        "waypoints": smoke.DEFAULT_WAYPOINTS,
        "trace_observed_player_positions": True,
        "audit": False,
        "audit_log_dir": str(smoke.DEFAULT_AUDIT_LOG_DIR),
    }
    values.update(overrides)
    return Namespace(**values)


class MovementCommandSmokeTests(unittest.TestCase):
    def test_leader_command_is_movement_only_and_live_controlled(self) -> None:
        command = smoke.build_leader_command(make_args(), Path("case"))

        self.assertIn("--move", command)
        self.assertIn("--live-control-file", command)
        self.assertIn("--trace-movement-log", command)
        self.assertEqual(command[command.index("--nav-api-url") + 1], "http://localhost:5000")
        self.assertNotIn("--hunter", command)
        self.assertNotIn("--combat", command)
        self.assertNotIn("--target-selection", command)

    def test_companion_command_enables_chat_commands_and_noncombat_catchup_policy(self) -> None:
        command = smoke.build_companion_command(make_args(), Path("case"))

        self.assertIn("--companion-chat-reply", command)
        self.assertIn("--live-control-file", command)
        self.assertIn("--follow-nearby-player", command)
        self.assertEqual(command[command.index("--nav-api-url") + 1], "http://localhost:5000")
        self.assertEqual(command[command.index("--follow-player-name") + 1], "Dummy001")
        self.assertEqual(command[command.index("--party-follow-teleport-distance") + 1], "0")
        self.assertNotIn("--live-companion-role", command)
        self.assertNotIn("--hunter", command)
        self.assertNotIn("--combat", command)

    def test_commands_reset_leader_and_companion_to_known_close_anchors(self) -> None:
        args = make_args()
        leader = smoke.build_leader_command(args, Path("case"))
        companion = smoke.build_companion_command(args, Path("case"))

        self.assertEqual(
            leader[leader.index("--startup-route-home-after-services") + 1],
            smoke.DEFAULT_LEADER_START_ANCHOR,
        )
        self.assertEqual(
            companion[companion.index("--startup-route-home-after-services") + 1],
            smoke.DEFAULT_COMPANION_START_ANCHOR,
        )
        self.assertIn("--startup-route-home-reset-player", leader)
        self.assertIn("--startup-route-home-reset-player", companion)
        self.assertEqual(leader[leader.index("--route-home-api-retries") + 1], "3")
        self.assertEqual(companion[companion.index("--route-home-api-retry-delay") + 1], "0.75")

        leader_x, leader_y, _leader_z = [int(part) for part in smoke.DEFAULT_LEADER_START_ANCHOR.split(",")]
        companion_x, companion_y, _companion_z = [int(part) for part in smoke.DEFAULT_COMPANION_START_ANCHOR.split(",")]
        self.assertLessEqual(((leader_x - companion_x) ** 2 + (leader_y - companion_y) ** 2) ** 0.5, 450.0)

    def test_reset_start_position_can_be_disabled_for_stale_position_diagnostics(self) -> None:
        args = make_args(reset_start_position=False)

        leader = smoke.build_leader_command(args, Path("case"))
        companion = smoke.build_companion_command(args, Path("case"))

        self.assertNotIn("--startup-route-home-after-services", leader)
        self.assertNotIn("--startup-route-home-after-services", companion)

    def test_shutdown_wait_accounts_for_remaining_hold_time(self) -> None:
        args = make_args(hold=70.0, leader_startup_delay=5.0, shutdown_timeout=20.0)

        self.assertEqual(smoke.shutdown_wait_timeout(args, 100.0, now=160.0), 25.0)
        self.assertEqual(smoke.shutdown_wait_timeout(args, 100.0, now=190.0), 20.0)

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

    def test_audit_option_adds_startup_commands(self) -> None:
        args = make_args(audit=True)

        leader = smoke.build_leader_command(args, Path("case"))
        companion = smoke.build_companion_command(args, Path("case"))

        self.assertIn("/movementaudit on {character} full", leader)
        self.assertIn("/movementaudit on {character} full", companion)

    def test_collect_audit_logs_copies_only_new_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_dir = root / "logs"
            run_dir = root / "run"
            audit_dir.mkdir()
            run_dir.mkdir()
            source = audit_dir / "movement-audit-Dummy002.jsonl"
            source.write_text('{"event":"old"}\n', encoding="utf-8")
            args = make_args(audit=True, audit_log_dir=str(audit_dir))
            offsets = smoke.snapshot_audit_offsets(args)

            source.write_text(
                '{"event":"old"}\n'
                + json.dumps({"event": "c2s_position", "horizontalDelta": 10, "deltaZ": 2})
                + "\n",
                encoding="utf-8",
            )
            smoke.collect_audit_logs(args, run_dir, offsets)

            copied = (run_dir / "movement-audit-Dummy002.jsonl").read_text(encoding="utf-8")
        self.assertNotIn('"old"', copied)
        self.assertIn('"c2s_position"', copied)

    def test_client_movement_summary_excludes_server_audit_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "client-movement.jsonl").write_text(
                json.dumps({"event": "move_step", "from_x": 0, "from_y": 0, "from_z": 0, "x": 10, "y": 0, "z": 0}) + "\n",
                encoding="utf-8",
            )
            (run_dir / "movement-audit-Dummy002.jsonl").write_text(
                json.dumps({"event": "c2s_position", "horizontalDelta": 1200, "deltaZ": 0}) + "\n",
                encoding="utf-8",
            )

            summary = smoke.summarize_movement_command_run(run_dir)

        self.assertEqual(summary["movement"]["files"], 1)
        self.assertEqual(summary["server_audit"]["files"], 1)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
