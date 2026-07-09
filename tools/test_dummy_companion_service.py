import csv
import importlib.util
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / "tools" / "dummy-companion-service.py"
BEHAVIOR_PATH = ROOT / "tools" / "behavior-dummy-client.py"
SMOKE_PATH = ROOT / "tools" / "run-live-companion-party-smoke.py"
SUMMARY_PATH = ROOT / "tools" / "summarize-live-companion-requests.py"
PERSONALITY_MATRIX_PATH = ROOT / "tools" / "run-live-companion-personality-matrix.py"
LIVE_COMPANION_POOL_PATH = ROOT / "tools" / "dummy-live-companions.csv"


def load_service():
    spec = importlib.util.spec_from_file_location("dummy_companion_service", SERVICE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_behavior():
    spec = importlib.util.spec_from_file_location("behavior_dummy_client_for_companion_tests", BEHAVIOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_smoke():
    spec = importlib.util.spec_from_file_location("run_live_companion_party_smoke", SMOKE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_summary():
    spec = importlib.util.spec_from_file_location("summarize_live_companion_requests", SUMMARY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DummyCompanionServiceTests(unittest.TestCase):
    def test_service_script_exists(self) -> None:
        self.assertTrue(SERVICE_PATH.exists())

    def test_live_companion_pool_has_realm_role_and_home_metadata(self) -> None:
        import csv

        service = load_service()

        self.assertTrue(LIVE_COMPANION_POOL_PATH.exists())
        with LIVE_COMPANION_POOL_PATH.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))

        self.assertTrue(rows)
        self.assertTrue({"username", "realm", "roles", "home_x", "home_y", "home_z"}.issubset(rows[0].keys()))
        self.assertTrue(any(row["realm"] == "1" and "healer" in row["roles"] for row in rows))
        self.assertTrue(any(row["realm"] == "2" and "tank" in row["roles"] for row in rows))
        self.assertTrue(any(row["realm"] == "3" and "dps" in row["roles"] for row in rows))
        self.assertTrue(any("speed_song" in service.companion_row_capabilities(row) for row in rows))
        self.assertTrue(any("stealth" in service.companion_row_capabilities(row) for row in rows))
        self.assertTrue(
            any(
                row["realm"] == "1"
                and service.companion_row_class_key(row) == "minstrel"
                and {"speed_song", "stealth"}.issubset(service.companion_row_capabilities(row))
                for row in rows
            )
        )

    def test_service_defaults_to_live_companion_pool(self) -> None:
        service = load_service()

        args = service.build_parser().parse_args(["--once"])

        self.assertEqual(Path(args.accounts_csv), LIVE_COMPANION_POOL_PATH)

    def test_service_accepts_max_runtime_for_smoke_runs(self) -> None:
        service = load_service()

        args = service.build_parser().parse_args(["--max-runtime", "30"])

        self.assertEqual(args.max_runtime, 30)

    def test_service_recovers_orphaned_active_requests_on_startup_by_default(self) -> None:
        service = load_service()

        args = service.build_parser().parse_args(["--once"])

        self.assertTrue(args.recover_orphaned_active_requests)

    def test_recover_orphaned_active_requests_requeues_only_missing_behavior_processes(self) -> None:
        service = load_service()
        args = mock.Mock(recover_orphaned_active_requests=True)
        active_requests = [
            {"id": "req-missing", "assignedCompanionName": "Albtest005"},
            {"id": "req-running", "assignedCompanionName": "Albtest006"},
        ]

        with mock.patch.object(service, "snapshot_requests", return_value=active_requests) as snapshot, mock.patch.object(
            service, "live_behavior_process_lines", return_value=["python tools/behavior-dummy-client.py req-running"]
        ), mock.patch.object(service, "update_request_status") as update_status:
            recovered = service.recover_orphaned_active_requests(args)

        self.assertEqual(recovered, 1)
        snapshot.assert_called_once_with(args, "active", 100)
        update_status.assert_called_once_with(
            args,
            "req-missing",
            "queued",
            "companion service recovered orphaned active request",
            "Albtest005",
        )

    def test_service_accepts_api_password_for_state_changing_routes(self) -> None:
        service = load_service()

        args = service.build_parser().parse_args(["--api-password", "secret"])

        self.assertEqual(args.api_password, "secret")

    def test_service_defaults_api_url_to_localhost_bridge(self) -> None:
        service = load_service()

        args = service.build_parser().parse_args(["--once"])

        self.assertEqual(args.api_url, "http://localhost:5000")

    def test_service_startup_wait_retries_until_server_api_is_ready(self) -> None:
        service = load_service()
        args = service.build_parser().parse_args(
            [
                "--api-startup-wait",
                "5",
                "--api-startup-retry-interval",
                "0.25",
            ]
        )

        with mock.patch.object(
            service,
            "api_request",
            side_effect=[None, None, {"dialogue_enabled": False}],
        ) as api_request, mock.patch.object(service.time, "sleep") as sleep:
            self.assertTrue(service.wait_for_server_api_ready(args))

        self.assertEqual(api_request.call_count, 3)
        sleep.assert_has_calls([mock.call(0.25), mock.call(0.25)])

    def test_service_main_exits_before_polling_when_server_api_never_becomes_ready(self) -> None:
        service = load_service()

        with mock.patch.object(service, "wait_for_server_api_ready", return_value=False) as wait_ready, mock.patch.object(
            service, "poll_active"
        ) as poll_active, mock.patch.object(service, "claim_next_request") as claim_next_request:
            exit_code = service.main(["--once", "--api-startup-wait", "0.1"])

        self.assertEqual(exit_code, 2)
        wait_ready.assert_called_once()
        poll_active.assert_not_called()
        claim_next_request.assert_not_called()

    def test_live_companion_smoke_defaults_api_url_to_localhost_bridge(self) -> None:
        smoke = load_smoke()

        args = smoke.build_parser().parse_args(["--dry-run"])

        self.assertEqual(args.api_url, "http://localhost:5000")

    def test_support_crowd_control_profile_requests_cc_capability(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(
            smoke.build_parser().parse_args(["--dry-run", "--smoke-profile", "support-crowd-control"])
        )

        self.assertEqual(args.roles, ["support"])
        self.assertEqual(args.requested_capabilities, "crowd_control")
        self.assertEqual(args.expect_companion_actions, ["crowd_control"])

    def test_support_crowd_control_request_enables_preemptive_cc(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "support",
            "realm": 1,
            "requestedCapabilities": "crowd_control",
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "albminstrel,dummy-pass,1,0,4,Minstrel,support|dps,531504,479073,2200\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(
                args,
                request,
                account_csv,
                Path(temp_dir) / "run",
                requester_state={"player": {"level": 50}},
            )

        self.assertIn("--startup-speed-song", command)
        self.assertIn("--party-support-evasion", command)
        self.assertEqual(command[command.index("--crowd-control-preemptive-min-threats") + 1], "1")

    def test_live_companion_smoke_summarizes_external_service_request_logs(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "case"
            request_id = "req-external"
            service_dir = root / "service-root" / request_id
            service_dir.mkdir(parents=True)
            (service_dir / "live-control.json").write_text(
                json.dumps({"say_channel": "party", "intent_hint": "cc_add"}),
                encoding="utf-8",
            )
            (service_dir / "companion.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"event": "live_control_applied"}),
                        json.dumps({"event": "tick", "action_counts": {"validated_crowd_control_spell": 1}}),
                        json.dumps({"event": "crowd_control_multi_aggro", "spell_type": "Mesmerize"}),
                        json.dumps({"event": "tick", "action_counts": {"speed_song_spell": 1}}),
                    ]
                ),
                encoding="utf-8",
            )
            with mock.patch.object(smoke, "DEFAULT_COMPANION_SERVICE_RUN_DIR", root / "service-root"):
                summary = smoke.summarize_encounters(run_dir, [request_id])
                missing = smoke.missing_companion_metrics(run_dir, [request_id])

        self.assertEqual(summary["crowd_control"], 2)
        self.assertEqual(summary["speed_song"], 1)
        self.assertEqual(summary["dialogue_cc_add"], 1)
        self.assertEqual(summary["dialogue_live_control_applied"], 1)
        self.assertEqual(missing, [])

    def test_live_companion_summary_tool_formats_operational_overview(self) -> None:
        summary = load_summary()

        lines = summary.format_summary(
            {
                "total": 4,
                "statusCounts": {"queued": 1, "active": 2, "completed": 1},
                "openCount": 3,
                "activeCount": 2,
                "active": [
                    {
                        "requesterName": "Leader",
                        "assignedCompanionName": "Arel",
                        "requestedRole": "healer",
                        "message": "live companion heartbeat",
                    }
                ],
            }
        )

        self.assertIn("total=4 open=3 active=2", lines[0])
        self.assertTrue(any("queued=1" in line and "active=2" in line for line in lines))
        self.assertTrue(any("Leader <- Arel role=healer" in line for line in lines))

    def test_live_companion_roles_map_to_safe_rotations(self) -> None:
        service = load_service()

        self.assertEqual(service.normalize_role("healer"), "healer")
        self.assertEqual(service.normalize_role("weird"), "fill")
        self.assertEqual(service.role_to_rotation("healer"), "healer-support")
        self.assertEqual(service.role_to_rotation("support"), "healer-support")
        self.assertEqual(service.role_to_rotation("tank"), "melee-basic")
        self.assertEqual(service.role_to_rotation("dps"), "melee-burst")

    def test_class_role_hints_cover_daoc_companion_roles(self) -> None:
        service = load_service()
        expected = {
            "heretic": {"healer", "support", "dps"},
            "thane": {"tank", "dps"},
            "valkyrie": {"tank", "support", "dps"},
            "bonedancer": {"support", "dps"},
            "warden": {"healer", "support", "tank", "dps"},
            "animist": {"support", "dps"},
            "vampiir": {"dps"},
            "scout": {"dps"},
            "hunter": {"dps"},
            "ranger": {"dps"},
        }

        for class_name, roles in expected.items():
            with self.subTest(class_name=class_name):
                self.assertTrue(roles.issubset(service.CLASS_ROLE_HINTS.get(class_name, set())))

    def test_support_behavior_command_uses_class_rotation_for_non_healer_support(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "support",
            "realm": 1,
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "albsorc,dummy-pass,1,0,8,Sorcerer,support,531504,479073,2200\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(args, request, account_csv, Path(temp_dir) / "run")

        self.assertEqual(command[command.index("--action-rotation") + 1], "caster-basic")
        self.assertIn("--party-support-evasion", command)

    def test_support_crowd_control_selection_prefers_cc_caster_over_speed_hybrid(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "support",
            "realm": 1,
            "requestedCapabilities": "crowd_control",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            source_csv = Path(temp_dir) / "accounts.csv"
            source_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "albtheurg,dummy-pass,1,0,5,Theurgist,support|dps,531504,479073,2200\n"
                "albminstrel,dummy-pass,1,0,4,Minstrel,support|dps,531504,479073,2200\n",
                encoding="utf-8",
            )
            selected_csv = service.select_companion_accounts_csv(request, source_csv, Path(temp_dir) / "run")

            with selected_csv.open(encoding="utf-8-sig", newline="") as handle:
                row = next(csv.DictReader(handle))

        self.assertEqual(row["class_name"], "Theurgist")

    def test_support_crowd_control_command_does_not_wait_for_follow_anchor(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "support",
            "realm": 1,
            "requestedCapabilities": "crowd_control",
            "objectiveTarget": "moorlich",
            "x": 332701,
            "y": 669142,
            "z": 2660,
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "albtheurg,dummy-pass,1,0,5,Theurgist,support|dps,531504,479073,2200\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(
                args,
                request,
                account_csv,
                Path(temp_dir) / "run",
                requester_state={"player": {"level": 50}},
            )

        self.assertEqual(command[command.index("--action-rotation") + 1], "caster-basic")
        self.assertNotIn("--follow-player-required-for-objective-move", command)
        self.assertNotIn("--party-require-leader-engaged", command)
        self.assertNotIn("--required-target-home", command)
        self.assertNotIn("--required-target-home-hunt-distance", command)
        self.assertNotIn("--target-home-max-distance", command)

    def test_caster_dps_command_does_not_wait_at_required_home(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "dps",
            "realm": 1,
            "requestedCapabilities": "caster_dps",
            "objectiveTarget": "moorlich",
            "x": 332701,
            "y": 669142,
            "z": 2660,
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "albwizard,dummy-pass,1,0,7,Wizard,dps,531504,479073,2200\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(
                args,
                request,
                account_csv,
                Path(temp_dir) / "run",
                requester_state={"player": {"level": 50}},
            )

        self.assertEqual(command[command.index("--action-rotation") + 1], "caster-basic")
        self.assertEqual(command[command.index("--party-encounter-mode") + 1], "standard")
        self.assertEqual(command[command.index("--max-target-level") + 1], "50")
        self.assertEqual(command[command.index("--max-target-level-delta") + 1], "0")
        self.assertIn("--require-target-name", command)
        self.assertEqual(command[command.index("--startup-delay") + 1], "15")
        self.assertEqual(command[command.index("--crowd-control-interval") + 1], "0")
        self.assertIn("--stationary-cast-actions", command)
        self.assertEqual(command[command.index("--stationary-cast-min-hold") + 1], "3.4")
        self.assertNotIn("--party-require-leader-engaged", command)
        self.assertNotIn("--required-target-home", command)

    def test_stealth_companion_command_enables_startup_stealth(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "dps",
            "realm": 1,
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "albscout,dummy-pass,1,0,3,Scout,dps,531504,479073,2200\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(args, request, account_csv, Path(temp_dir) / "run")

        self.assertIn("--startup-stealth", command)

    def test_companion_command_includes_realm_ground_z_map_and_correction_smoothing(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "dps",
            "realm": 100,
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000, hold=3600, party_size=2, combat_home_leash_distance=4500.0)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "midmerc,dummy-pass,100,0,11,Mercenary,dps,729152,760225,4573\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(args, request, account_csv, Path(temp_dir) / "run")

        self.assertIn("--ground-z-map", command)
        self.assertEqual(
            command[command.index("--ground-z-map") + 1],
            "tools/pathing/heightmaps/region100_client_zones.json",
        )
        self.assertIn("--server-correction-smoothing", command)

    def test_speed_song_companion_command_enables_startup_speed_song(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "support",
            "realm": 2,
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "midskald,dummy-pass,2,10,24,Skald,support|dps,774601,755307,4600\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(args, request, account_csv, Path(temp_dir) / "run")

        self.assertIn("--startup-speed-song", command)

    def test_companion_guide_command_uses_service_gateway_timeout(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "healer",
            "realm": 1,
        }
        args = mock.Mock(
            host="127.0.0.1",
            port=10300,
            api_port=5000,
            dialogue_enabled=True,
            guide_enabled=True,
            ai_gateway_timeout=20,
            ai_gateway_model_alias="small-dialogue",
            ai_guide_model_alias="openai-small-guide",
            ai_gateway_config="live-gateway.json",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "albcleric,dummy-pass,1,0,6,Cleric,healer|support,531504,479073,2200\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(args, request, account_csv, Path(temp_dir) / "run")

        self.assertIn("--companion-guide-timeout", command)
        self.assertEqual(command[command.index("--companion-guide-timeout") + 1], "20.0")
        self.assertIn("--companion-free-chat", command)
        self.assertEqual(command[command.index("--ai-gateway-model-alias") + 1], "small-dialogue")
        self.assertIn("--ai-gateway-config", command)
        self.assertIn("--companion-guide-ai-gateway-config", command)

    def test_requested_capability_prefers_matching_live_companion_row(self) -> None:
        service = load_service()
        rows = [
            {"username": "albcleric", "realm": "1", "class_name": "Cleric", "roles": "healer|support"},
            {"username": "albminstrel", "realm": "1", "class_name": "Minstrel", "roles": "support|dps"},
            {"username": "midskald", "realm": "2", "class_name": "Skald", "roles": "support|dps"},
        ]

        ranked = service.rank_companion_rows(
            {
                "realm": 1,
                "requestedRole": "support",
                "requestedCapabilities": "speed song|stealth",
            },
            rows,
        )

        self.assertEqual(ranked[0]["username"], "albminstrel")

    def test_stealth_only_request_prefers_non_speed_stealth_dps(self) -> None:
        service = load_service()
        rows = [
            {
                "username": "albminstrel",
                "realm": "1",
                "class_name": "Minstrel",
                "roles": "support|dps",
                "home_x": "100",
                "home_y": "100",
                "home_z": "0",
            },
            {
                "username": "albscout",
                "realm": "1",
                "class_name": "Scout",
                "roles": "dps",
                "home_x": "100",
                "home_y": "100",
                "home_z": "0",
            },
        ]

        ranked = service.rank_companion_rows(
            {
                "realm": 1,
                "requestedRole": "dps",
                "requestedCapabilities": "stealth",
                "x": 100,
                "y": 100,
                "z": 0,
            },
            rows,
        )

        self.assertEqual(ranked[0]["username"], "albscout")

    def test_owned_mercenary_request_prefers_matching_class_row(self) -> None:
        service = load_service()
        rows = [
            {"username": "albcleric", "realm": "1", "class_name": "Cleric", "roles": "healer|support"},
            {"username": "albminstrel", "realm": "1", "class_name": "Minstrel", "roles": "support|dps"},
            {"username": "albpaladin", "realm": "1", "class_name": "Paladin", "roles": "tank|support"},
        ]

        ranked = service.rank_companion_rows(
            {
                "realm": 1,
                "requestedRole": "support",
                "mercenaryClassName": "Minstrel",
            },
            rows,
        )

        self.assertEqual(ranked[0]["username"], "albminstrel")

    def test_owned_mercenary_request_personality_overrides_role_default(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "healer",
            "realm": 1,
            "mercenaryPersonality": "shifty_traitor",
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000, force_companion_personality="")

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "albcleric,dummy-pass,1,0,6,Cleric,healer|support,531504,479073,2200\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(args, request, account_csv, Path(temp_dir) / "run")

        self.assertEqual(command[command.index("--companion-personality") + 1], "shifty_traitor")

    def test_owned_mercenary_tactical_state_modifies_behavior_command(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "healer",
            "realm": 1,
            "mercenaryPersonality": "calm_support",
            "mercenaryTacticPreset": "safe",
            "mercenaryTrust": 86,
            "mercenaryFatigue": 8,
            "mercenaryTraits": "응급치료|도망 빠름",
            "mercenaryAdventureMemory": "브리튼 남쪽 숲에서 초보 파티를 무사히 호위했다.",
            "mercenaryTotalContracts": 6,
            "mercenaryTotalContractMinutes": 143,
            "mercenaryKillsTogether": 22,
            "mercenaryDeathsTogether": 1,
            "mercenaryRescues": 4,
            "mercenaryQuestsCompleted": 2,
            "mercenaryEarnedTitles": "위기 구원자|의뢰 해결사",
            "mercenaryPersonalQuestState": "completed:first_bond",
            "mercenaryRelationshipEventState": "bond_acknowledged",
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000, party_size=1, force_companion_personality="")

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "albcleric,dummy-pass,1,0,6,Cleric,healer|support,531504,479073,2200\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(args, request, account_csv, Path(temp_dir) / "run")

        def last_option_value(option: str) -> str:
            index = len(command) - 1 - command[::-1].index(option)
            return command[index + 1]

        self.assertEqual(last_option_value("--party-assist-attack-delay"), "0.9")
        self.assertEqual(last_option_value("--party-heal-leader-health-percent"), "95")
        self.assertEqual(last_option_value("--flee-movement-speed"), "360")
        self.assertEqual(last_option_value("--combat-interval"), "0.5")
        self.assertEqual(last_option_value("--mercenary-trust"), "86")
        self.assertEqual(last_option_value("--mercenary-fatigue"), "8")
        self.assertEqual(last_option_value("--mercenary-tactic-preset"), "safe")
        self.assertEqual(last_option_value("--mercenary-adventure-memory"), "브리튼 남쪽 숲에서 초보 파티를 무사히 호위했다.")
        self.assertEqual(last_option_value("--mercenary-total-contracts"), "6")
        self.assertEqual(last_option_value("--mercenary-total-contract-minutes"), "143")
        self.assertEqual(last_option_value("--mercenary-kills-together"), "22")
        self.assertEqual(last_option_value("--mercenary-deaths-together"), "1")
        self.assertEqual(last_option_value("--mercenary-rescues"), "4")
        self.assertEqual(last_option_value("--mercenary-quests-completed"), "2")
        self.assertEqual(last_option_value("--mercenary-earned-titles"), "위기 구원자|의뢰 해결사")
        self.assertEqual(last_option_value("--mercenary-personal-quest-state"), "completed:first_bond")
        self.assertEqual(last_option_value("--mercenary-relationship-event-state"), "bond_acknowledged")

    def test_owned_mercenary_empty_progression_strings_are_not_forwarded_as_blank_args(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "healer",
            "realm": 1,
            "mercenaryPersonality": "calm_support",
            "mercenaryTrust": 50,
            "mercenaryFatigue": 0,
            "mercenaryEarnedTitles": "",
            "mercenaryPersonalQuestState": "",
            "mercenaryRelationshipEventState": "",
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000, party_size=1, force_companion_personality="")

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "albcleric,dummy-pass,1,0,6,Cleric,healer|support,531504,479073,2200\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(args, request, account_csv, Path(temp_dir) / "run")

        self.assertNotIn("--mercenary-earned-titles", command)
        self.assertNotIn("--mercenary-personal-quest-state", command)
        self.assertNotIn("--mercenary-relationship-event-state", command)

    def test_companion_dialogue_payload_uses_owned_mercenary_state_memory(self) -> None:
        service = load_service()
        companion = service.ActiveCompanion(
            {
                "id": "req1",
                "requesterName": "LiveLeader",
                "requestedRole": "dps",
                "mercenaryPersonality": "shifty_traitor",
                "mercenaryTacticPreset": "aggressive",
                "mercenaryTrust": 33,
                "mercenaryFatigue": 72,
                "mercenaryTraits": "돈 밝힘|탈출로 확인",
                "mercenaryAdventureMemory": "이전 전투에서 후퇴로를 먼저 확인해 파티를 살렸다.",
                "mercenaryTotalContracts": 5,
                "mercenaryKillsTogether": 13,
                "mercenaryRescues": 1,
                "mercenaryQuestsCompleted": 1,
                "mercenaryEarnedTitles": "사냥길 용병",
                "mercenaryPersonalQuestState": "available:field_oath",
                "mercenaryRelationshipEventState": "bond_acknowledged",
            },
            mock.Mock(),
            account="albmerc",
        )

        payload = service.build_companion_dialogue_payload(
            companion,
            {"player": {"inCombat": True, "healthPercent": 64}, "groupMembers": []},
            "status",
        )

        self.assertEqual(payload["personality"], "shifty_traitor")
        self.assertEqual(payload["state"]["mercenary"]["tactic"], "aggressive")
        self.assertEqual(payload["state"]["mercenary"]["trust"], 33)
        self.assertEqual(payload["state"]["mercenary"]["trust_stage"], "낯섦")
        self.assertEqual(payload["state"]["mercenary"]["fatigue"], 72)
        self.assertIn("친밀도 말투: 낯섦", payload["memory"])
        self.assertIn("과한 친근함을 피함", payload["memory"])
        self.assertIn("탈출로 확인", payload["memory"])
        self.assertIn("현재 칭호: 사냥길 용병", payload["memory"])
        self.assertIn("누적 기록: 계약 5회", payload["memory"])
        self.assertIn("개인 의뢰: 전장의 맹세 진행 중", payload["memory"])
        self.assertIn("관계 이벤트: 처음으로 리더를 믿겠다고 인정", payload["memory"])
        self.assertEqual(payload["state"]["mercenary"]["record"]["kills_together"], 13)

    def test_behavior_companion_replies_to_journal_tactic_and_experience_tips(self) -> None:
        behavior = load_behavior()
        context = behavior.build_companion_chat_status_context(
            role="healer-support",
            command_mode=behavior.CompanionCommandMode.defensive,
            trust=88,
            fatigue=18,
            guide_enabled=True,
            free_chat_enabled=True,
            mercenary_record={
                "personality": "calm_support",
                "tactic": "heal_priority",
                "adventure_memory": "드럼 리자드 무리에서 리더를 살려냈다.",
                "total_contracts": 9,
                "total_contract_minutes": 240,
                "persistent_kills": 31,
                "persistent_rescues": 4,
                "persistent_quests_completed": 2,
                "earned_titles": "위기 구원자",
                "personal_quest_state": "completed:first_bond",
                "relationship_event_state": "bond_acknowledged",
            },
        )
        rng = random.Random(1)

        journal = behavior.choose_companion_chat_reply("용병아 추억 일지 말해줘", [], rng, status_context=context)
        tactic = behavior.choose_companion_chat_reply("너 성격이랑 전술 뭐야?", [], rng, status_context=context)
        beginner = behavior.choose_companion_chat_reply("초보면 뭐부터 말하면 돼?", [], rng, status_context=context)
        veteran = behavior.choose_companion_chat_reply("숙련 운용팁 알려줘", [], rng, status_context=context)

        self.assertIn("드럼 리자드", journal)
        self.assertIn("위기 구원자", journal)
        self.assertIn("침착한 보좌관형", tactic)
        self.assertIn("치유 우선", tactic)
        self.assertIn("상태", beginner)
        self.assertIn("ㄱㄱ", beginner)
        self.assertIn("숙련 운용", veteran)
        self.assertIn("치유 우선", veteran)

    def test_tank_selection_prefers_defensive_self_sustain_when_home_ties(self) -> None:
        service = load_service()
        rows = [
            {
                "username": "albarmsman",
                "realm": "1",
                "class_name": "Armsman",
                "roles": "tank|dps",
                "home_x": "531504",
                "home_y": "479073",
                "home_z": "2200",
            },
            {
                "username": "albpaladin",
                "realm": "1",
                "class_name": "Paladin",
                "roles": "tank|support",
                "home_x": "531504",
                "home_y": "479073",
                "home_z": "2200",
            },
        ]

        ranked = service.rank_companion_rows(
            {
                "realm": 1,
                "requestedRole": "tank",
                "x": 531504,
                "y": 479073,
                "z": 2200,
            },
            rows,
        )

        self.assertEqual(ranked[0]["username"], "albpaladin")
        self.assertIn("defensive_tank", service.companion_row_capabilities(ranked[0]))
        self.assertIn("self_sustain", service.companion_row_capabilities(ranked[0]))

    def test_boss_tank_selection_prefers_pure_tank_over_support_hybrid_when_home_ties(self) -> None:
        service = load_service()
        rows = [
            {
                "username": "albarmsman",
                "realm": "1",
                "class_name": "Armsman",
                "roles": "tank|dps",
                "home_x": "531504",
                "home_y": "479073",
                "home_z": "2200",
            },
            {
                "username": "albpaladin",
                "realm": "1",
                "class_name": "Paladin",
                "roles": "tank|support",
                "home_x": "531504",
                "home_y": "479073",
                "home_z": "2200",
            },
        ]

        ranked = service.rank_companion_rows(
            {
                "realm": 1,
                "requestedRole": "tank",
                "contentType": "pve",
                "objectiveTarget": "moorlich",
                "x": 531504,
                "y": 479073,
                "z": 2200,
            },
            rows,
        )

        self.assertEqual(ranked[0]["username"], "albarmsman")
        self.assertIn("defensive_tank", service.companion_row_capabilities(ranked[0]))

    def test_dps_selection_prefers_dedicated_damage_when_home_ties(self) -> None:
        service = load_service()
        rows = [
            {
                "username": "albarmsman",
                "realm": "1",
                "class_name": "Armsman",
                "roles": "tank|dps",
                "home_x": "531504",
                "home_y": "479073",
                "home_z": "2200",
            },
            {
                "username": "albmercenary",
                "realm": "1",
                "class_name": "Mercenary",
                "roles": "dps",
                "home_x": "531504",
                "home_y": "479073",
                "home_z": "2200",
            },
        ]

        ranked = service.rank_companion_rows(
            {
                "realm": 1,
                "requestedRole": "dps",
                "x": 531504,
                "y": 479073,
                "z": 2200,
            },
            rows,
        )

        self.assertEqual(ranked[0]["username"], "albmercenary")
        self.assertIn("dedicated_dps", service.companion_row_capabilities(ranked[0]))

    def test_boss_dps_selection_prefers_safe_caster_damage_when_home_ties(self) -> None:
        service = load_service()
        rows = [
            {
                "username": "albmercenary",
                "realm": "1",
                "class_name": "Mercenary",
                "roles": "dps",
                "home_x": "531504",
                "home_y": "479073",
                "home_z": "2200",
            },
            {
                "username": "albwizard",
                "realm": "1",
                "class_name": "Wizard",
                "roles": "dps",
                "home_x": "531504",
                "home_y": "479073",
                "home_z": "2200",
            },
        ]

        ranked = service.rank_companion_rows(
            {
                "realm": 1,
                "requestedRole": "dps",
                "contentType": "pve:moorlich",
                "x": 531504,
                "y": 479073,
                "z": 2200,
            },
            rows,
        )

        self.assertEqual(ranked[0]["username"], "albwizard")
        self.assertIn("caster_dps", service.companion_row_capabilities(ranked[0]))

    def test_capability_selected_minstrel_command_enables_speed_and_stealth(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "support",
            "realm": 1,
            "requestedCapabilities": "speed-song|stealth",
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z,specs\n"
                "albcleric,dummy-pass,1,0,6,Cleric,healer|support,531504,479073,2200,Rejuvenation|40;Enhancement|36\n"
                "albminstrel,dummy-pass,1,0,4,Minstrel,support|dps,531504,479073,2200,Instruments|44;Slash|39;Stealth|25\n",
                encoding="utf-8",
            )
            selected_csv = service.select_companion_accounts_csv(request, account_csv, Path(temp_dir) / "run")
            command = service.build_behavior_command(args, request, selected_csv, Path(temp_dir) / "run")

            self.assertEqual(service.first_account_username(selected_csv), "albminstrel")
            self.assertEqual(command[command.index("--action-rotation") + 1], "hybrid")
            self.assertIn("--startup-speed-song", command)
            self.assertIn("--startup-stealth", command)

    def test_objective_support_minstrel_command_keeps_hybrid_tools_with_safe_support_spacing(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "support",
            "realm": 1,
            "requestedCapabilities": "speed-song",
            "contentType": "pve",
            "objectiveTarget": "moorlich",
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z,specs\n"
                "albminstrel,dummy-pass,1,0,4,Minstrel,support|dps,531504,479073,2200,Instruments|44;Slash|39;Stealth|25\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(args, request, account_csv, Path(temp_dir) / "run")

        self.assertEqual(command[command.index("--action-rotation") + 1], "hybrid")
        self.assertIn("--startup-speed-song", command)
        self.assertNotIn("--startup-stealth", command)
        self.assertEqual(command[command.index("--party-follow-distance") + 1], "120")
        self.assertEqual(command[command.index("--boss-ranged-safe-distance") + 1], "1400")
        self.assertEqual(command[command.index("--party-preengage-ranged-safe-distance") + 1], "1500")

    def test_normal_pve_caster_companion_uses_field_combat_profile(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "dps",
            "realm": 1,
            "contentType": "pve",
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000, party_size=1)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z,specs\n"
                "albwizard,dummy-pass,1,0,12,Wizard,dps,531504,479073,2200,Fire Magic|5;Earth Magic|5\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(args, request, account_csv, Path(temp_dir) / "run")

        self.assertEqual(command[command.index("--action-rotation") + 1], "caster-basic")
        self.assertEqual(command[command.index("--party-encounter-mode") + 1], "standard")
        self.assertNotIn("--party-require-leader-engaged", command)
        self.assertNotIn("--party-mark-pull-engaged", command)
        self.assertNotIn("--boss-ranged-safe-distance", command)
        self.assertNotIn("--party-preengage-ranged-safe-distance", command)
        self.assertNotIn("--stationary-cast-actions", command)
        self.assertIn("--party-use-assist-command", command)
        self.assertEqual(command[command.index("--ranged-stop-distance") + 1], "650")
        self.assertEqual(command[command.index("--attack-target-in-view-prime-delay") + 1], "0.75")

    def test_normal_pve_melee_companion_uses_stable_field_chase_profile(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "dps",
            "realm": 1,
            "contentType": "pve",
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000, party_size=1)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z,specs\n"
                "albmerc,dummy-pass,1,0,11,Mercenary,dps,531504,479073,2200,Dual Wield|5;Slash|5\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(args, request, account_csv, Path(temp_dir) / "run")

        self.assertEqual(command[command.index("--action-rotation") + 1], "melee-burst")
        self.assertEqual(command[command.index("--party-encounter-mode") + 1], "standard")
        self.assertEqual(command[len(command) - 1 - command[::-1].index("--target-face-command-interval") + 1], "0")
        self.assertEqual(command[len(command) - 1 - command[::-1].index("--melee-stick-attack-distance") + 1], "330")
        self.assertNotIn("--party-boss-non-tank-melee-backoff", command)

    def test_elite_contract_tier_extends_hold_and_improves_behavior_timing(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "dps",
            "realm": 1,
            "contractTier": "elite",
            "contractDurationSeconds": 3600,
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z,specs\n"
                "albmerc,dummy-pass,1,0,11,Mercenary,dps,531504,479073,2200,Slash|50;Dual Wield|50\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(args, request, account_csv, Path(temp_dir) / "run")

        def last_option_value(option: str) -> str:
            index = len(command) - 1 - command[::-1].index(option)
            return command[index + 1]

        self.assertEqual(command[command.index("--hold") + 1], "3600")
        self.assertEqual(last_option_value("--combat-interval"), "0.45")
        self.assertEqual(last_option_value("--skill-interval"), "0.72")
        self.assertEqual(last_option_value("--party-follow-interval"), "0.18")
        self.assertEqual(last_option_value("--startup-self-buff-count"), "4")

    def test_live_companion_pool_can_reach_minstrel_after_prior_support_excluded(self) -> None:
        service = load_service()
        excluded = {"albtest005", "albtest001", "albtest008"}

        with tempfile.TemporaryDirectory() as temp_dir:
            selected_csv = service.select_companion_accounts_csv(
                {"realm": 1, "requestedRole": "support"},
                LIVE_COMPANION_POOL_PATH,
                Path(temp_dir) / "run",
                excluded,
            )

            self.assertEqual(service.first_account_username(selected_csv), "albtest012")

    def test_tank_companion_command_enables_live_reaggro_handoff(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "tank",
            "realm": 1,
            "contentType": "pve",
            "objectiveTarget": "moorlich",
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "albtank,dummy-pass,1,0,1,Armsman,tank,531504,479073,2200\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(args, request, account_csv, Path(temp_dir) / "run")

        self.assertIn("--party-active-tank-handoff-health-percent", command)
        self.assertEqual(int(command[command.index("--party-active-tank-handoff-health-percent") + 1]), 100)
        self.assertIn("--party-focus-pressure-offtank-reaggro", command)
        self.assertIn("--party-active-tank-reaggro-taunt-interval", command)
        self.assertIn("--party-focus-target-backoff", command)
        self.assertEqual(command[command.index("--party-focus-target-max-age") + 1], "6")
        self.assertIn("--party-active-tank-last-known-stop-distance", command)
        self.assertEqual(command[command.index("--party-active-tank-last-known-stop-distance") + 1], "25")
        self.assertNotIn("--party-require-leader-engaged", command)
        self.assertIn("--party-mark-pull-engaged", command)
        self.assertIn("--party-block-solo-required-retaliation", command)
        self.assertEqual(command[command.index("--party-rescue-assist-after") + 1], "3")
        self.assertEqual(command[command.index("--party-rescue-emergency-assist-after") + 1], "2")
        self.assertIn("--party-rescue-aggro", command)
        self.assertIn("--party-rescue-before-objective-engaged", command)
        self.assertEqual(command[command.index("--party-protection-interval") + 1], "4")
        self.assertIn("--party-use-assist-command", command)
        self.assertEqual(command[command.index("--party-encounter-mode") + 1], "boss")
        self.assertEqual(command[command.index("--party-assist-interval") + 1], "0.6")
        self.assertEqual(command[command.index("--party-assist-attack-delay") + 1], "0.3")
        self.assertGreaterEqual(int(command[command.index("--party-rescue-max-distance") + 1]), 6000)
        self.assertGreaterEqual(int(command[command.index("--flee-melee-counterattack-health-floor") + 1]), 40)
        flee_pressure_indexes = [index for index, value in enumerate(command) if value == "--flee-pressure-health-percent"]
        self.assertEqual(command[flee_pressure_indexes[-1] + 1], "40")
        self.assertEqual(command[command.index("--required-target-tank-commit-health-percent") + 1], "25")
        self.assertEqual(command[command.index("--flee-critical-health-percent") + 1], "25")
        self.assertEqual(command[command.index("--party-survival-active-tank-health-percent") + 1], "25")

    def test_party_vacancy_clamps_to_available_slots(self) -> None:
        service = load_service()

        self.assertEqual(service.party_vacancy(8, 1), 7)
        self.assertEqual(service.party_vacancy(8, 8), 0)
        self.assertEqual(service.party_vacancy(8, 12), 0)

    def test_leave_requests_are_control_requests_not_spawn_requests(self) -> None:
        service = load_service()

        self.assertTrue(service.is_leave_request({"requestedRole": "leave"}))
        self.assertTrue(service.is_leave_request({"status": "leaving"}))
        self.assertFalse(service.is_leave_request({"requestedRole": "healer", "status": "queued"}))

    def test_real_player_join_releases_lowest_priority_companion(self) -> None:
        service = load_service()
        members = [
            {"name": "RealPlayer", "role": "player", "is_dummy": False},
            {"name": "CompanionHealer", "role": "healer", "is_dummy": True},
            {"name": "CompanionDps", "role": "dps", "is_dummy": True},
            {"name": "CompanionTank", "role": "tank", "is_dummy": True},
        ]

        self.assertEqual(service.choose_release_candidate(members)["name"], "CompanionDps")

    def test_real_player_join_does_not_auto_release_active_companion(self) -> None:
        service = load_service()
        active = {
            "tank-req": service.ActiveCompanion(
                {"id": "tank-req", "requesterAccount": "leader1", "requestedRole": "tank"},
                mock.Mock(),
                account="albtank",
            ),
            "dps-req": service.ActiveCompanion(
                {"id": "dps-req", "requesterAccount": "leader1", "requestedRole": "dps"},
                mock.Mock(),
                account="albdps",
            ),
            "healer-req": service.ActiveCompanion(
                {"id": "healer-req", "requesterAccount": "leader1", "requestedRole": "healer"},
                mock.Mock(),
                account="albhealer",
            ),
        }
        requester_state = {
            "groupMembers": [
                {"name": "Leader", "account": "leader1"},
                {"name": "RealPlayer", "account": "real1"},
                {"name": "RealPlayer2", "account": "real2"},
                {"name": "RealPlayer3", "account": "real3"},
                {"name": "RealPlayer4", "account": "real4"},
                {"name": "AlbTank", "account": "albtank", "isCompanion": True},
                {"name": "AlbDps", "account": "albdps", "isCompanion": True},
                {"name": "AlbHealer", "account": "albhealer", "isCompanion": True},
            ]
        }

        request_id = service.choose_release_request_for_real_player_join(
            active,
            "account:leader1",
            requester_state,
            release_counts={},
        )

        self.assertEqual(request_id, "")

    def test_real_player_join_release_credit_is_ignored_without_explicit_leave(self) -> None:
        service = load_service()
        active = {
            "dps-req": service.ActiveCompanion(
                {"id": "dps-req", "requesterAccount": "leader1", "requestedRole": "dps"},
                mock.Mock(),
                account="albdps",
            )
        }
        requester_state = {
            "groupMembers": [
                {"name": "Leader", "account": "leader1"},
                {"name": "RealPlayer", "account": "real1"},
                {"name": "AlbDps", "account": "albdps", "isCompanion": True},
            ]
        }

        request_id = service.choose_release_request_for_real_player_join(
            active,
            "account:leader1",
            requester_state,
            release_counts={"account:leader1": 1},
        )

        self.assertEqual(request_id, "")

    def test_missing_group_companion_is_released_when_party_disbands(self) -> None:
        service = load_service()
        active = {
            "dps-req": service.ActiveCompanion(
                {"id": "dps-req", "requesterAccount": "leader1", "requestedRole": "dps"},
                mock.Mock(),
                account="albdps",
            )
        }

        request_id = service.choose_release_request_for_missing_group_companion(
            active,
            "account:leader1",
            {"player": {"name": "Leader"}, "groupMembers": []},
        )

        self.assertEqual(request_id, "dps-req")

    def test_companion_account_selection_excludes_requester_account(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "Albtest001",
            "requesterAccount": "albtest001",
            "requestedRole": "healer",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index\n"
                "albtest001,dummy-pass,1,0\n"
                "albtest002,dummy-pass,1,0\n",
                encoding="utf-8",
            )
            selected = service.select_companion_accounts_csv(request, account_csv, Path(temp_dir) / "run")
            payload = selected.read_text(encoding="utf-8")

        self.assertNotIn("albtest001", payload)
        self.assertIn("albtest002", payload)

    def test_companion_account_selection_accepts_utf8_bom_csv(self) -> None:
        service = load_service()
        request = {"id": "req1", "requesterAccount": "leader1", "requesterName": "Leader"}

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "\ufeffusername,password,realm,char_index\n"
                "albtest005,dummy-pass,1,0\n",
                encoding="utf-8",
            )
            selected = service.select_companion_accounts_csv(request, account_csv, Path(temp_dir) / "run")
            self.assertEqual(service.first_account_username(selected), "albtest005")

    def test_companion_account_selection_prefers_realm_role_and_nearest_home(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterAccount": "dummy043",
            "requesterName": "Dummy043",
            "requestedRole": "healer",
            "realm": 1,
            "x": 560000,
            "y": 356000,
            "z": 5000,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_name,home_x,home_y,home_z\n"
                "midhealer,dummy-pass,2,10,Healer,560000,356000,5000\n"
                "albtank,dummy-pass,1,0,Paladin,560000,356000,5000\n"
                "albfarhealer,dummy-pass,1,0,Cleric,400000,740000,300\n"
                "albnearhealer,dummy-pass,1,0,Cleric,560400,356200,5000\n",
                encoding="utf-8",
            )
            selected = service.select_companion_accounts_csv(request, account_csv, Path(temp_dir) / "run")
            rows = selected.read_text(encoding="utf-8").splitlines()

        self.assertIn("albnearhealer", rows[1])
        self.assertIn("albfarhealer", "\n".join(rows))
        self.assertNotIn("midhealer", "\n".join(rows))
        self.assertNotIn("albtank", "\n".join(rows))

    def test_companion_account_selection_starts_companion_at_request_position(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterAccount": "leader1",
            "requesterName": "Leader",
            "realm": 1,
            "region": 1,
            "x": 531452,
            "y": 478913,
            "z": 2200,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_name\n"
                "albcleric,dummy-pass,1,0,Cleric\n",
                encoding="utf-8",
            )
            selected = service.select_companion_accounts_csv(request, account_csv, Path(temp_dir) / "run")
            with selected.open(encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))

        self.assertEqual(row["start_x"], "531452")
        self.assertEqual(row["start_y"], "478913")
        self.assertEqual(row["start_z"], "2200")
        self.assertEqual(row["zone_id"], "1")

    def test_companion_account_selection_excludes_active_companion_accounts(self) -> None:
        service = load_service()
        request = {"id": "req1", "requestedRole": "healer", "realm": 1}

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_name,roles\n"
                "albhealer1,dummy-pass,1,0,Cleric,healer|support\n"
                "albhealer2,dummy-pass,1,0,Cleric,healer|support\n",
                encoding="utf-8",
            )
            selected = service.select_companion_accounts_csv(
                request,
                account_csv,
                Path(temp_dir) / "run",
                excluded_accounts={"albhealer1"},
            )
            rows = selected.read_text(encoding="utf-8").splitlines()

        self.assertIn("albhealer2", rows[1])
        self.assertNotIn("albhealer1", "\n".join(rows))

    def test_account_usernames_from_csv_reads_pool_accounts(self) -> None:
        service = load_service()

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index\n"
                "albhealer1,dummy-pass,1,0\n"
                "albtank1,dummy-pass,1,0\n",
                encoding="utf-8",
            )

            self.assertEqual(service.account_usernames_from_csv(account_csv), ["albhealer1", "albtank1"])

    def test_live_companion_personality_matrix_smoke_covers_distinct_behavior_profiles(self) -> None:
        result = subprocess.run(
            [sys.executable, str(PERSONALITY_MATRIX_PATH), "--json"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        rows = payload["rows"]
        by_personality = {row["personality"]: row for row in rows}

        self.assertEqual(payload["count"], 12)
        self.assertEqual(len(by_personality), 12)
        self.assertEqual(payload["unique_signatures"], 12)
        self.assertEqual(by_personality["reckless_berserker"]["values"]["party_assist_attack_delay"], 0.0)
        self.assertEqual(by_personality["shifty_traitor"]["values"]["flee_health_percent"], 60.0)
        self.assertEqual(by_personality["wary_survivor"]["values"]["flee_health_percent"], 55.0)
        self.assertEqual(by_personality["calm_support"]["values"]["skill_interval"], 0.85)
        self.assertEqual(by_personality["eager_rookie"]["values"]["party_follow_step"], 410.0)

    def test_behavior_command_can_force_companion_personality_for_smoke_matrix(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "dps",
            "realm": 1,
            "x": 111,
            "y": 222,
            "z": 333,
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000, force_companion_personality="shifty_traitor")

        with tempfile.TemporaryDirectory() as temp_dir:
            command = service.build_behavior_command(
                args,
                request,
                ROOT / "tools" / "dummy-live-companions.csv",
                Path(temp_dir),
                requester_state={"player": {"level": 50}},
            )

        self.assertEqual(command[command.index("--companion-personality") + 1], "shifty_traitor")
        self.assertEqual(command[len(command) - 1 - command[::-1].index("--party-assist-attack-delay") + 1], "1.6")
        self.assertEqual(command[len(command) - 1 - command[::-1].index("--flee-health-percent") + 1], "60")

    def test_live_companion_party_smoke_passes_forced_personality_to_service(self) -> None:
        smoke = load_smoke()
        args = smoke.build_parser().parse_args(["--force-companion-personality", "reckless_berserker"])

        command = smoke.build_service_command(args, Path("run"), ROOT / "tools" / "dummy-live-companions.csv")

        self.assertIn("--force-companion-personality", command)
        self.assertEqual(command[command.index("--force-companion-personality") + 1], "reckless_berserker")

    def test_live_companion_party_smoke_passes_guide_gateway_alias_to_service(self) -> None:
        smoke = load_smoke()
        args = smoke.build_parser().parse_args(
            [
                "--dialogue-enabled",
                "--ai-gateway-config",
                "live-gateway.json",
                "--ai-gateway-model-alias",
                "small-dialogue",
                "--ai-guide-model-alias",
                "openai-small-guide",
            ]
        )

        command = smoke.build_service_command(args, Path("run"), ROOT / "tools" / "dummy-live-companions.csv")

        self.assertEqual(command[command.index("--ai-gateway-config") + 1], "live-gateway.json")
        self.assertEqual(command[command.index("--ai-gateway-model-alias") + 1], "small-dialogue")
        self.assertEqual(command[command.index("--ai-guide-model-alias") + 1], "openai-small-guide")

    def test_live_companion_party_smoke_reads_gateway_defaults_from_environment(self) -> None:
        smoke = load_smoke()
        with mock.patch.dict(
            "os.environ",
            {
                "OPENDAOC_COMPANION_AI_GATEWAY_CONFIG": "env-live-gateway.json",
                "OPENDAOC_COMPANION_AI_GATEWAY_MODEL_ALIAS": "env-dialogue",
                "OPENDAOC_COMPANION_AI_GUIDE_MODEL_ALIAS": "env-guide",
            },
        ):
            args = smoke.build_parser().parse_args([])

        self.assertEqual(args.ai_gateway_config, "env-live-gateway.json")
        self.assertEqual(args.ai_gateway_model_alias, "env-dialogue")
        self.assertEqual(args.ai_guide_model_alias, "env-guide")

    def test_live_companion_party_smoke_env_loader_strips_crlf_values(self) -> None:
        smoke = load_smoke()
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict("os.environ", {}, clear=True):
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "OPENDAOC_COMPANION_AI_GATEWAY_CONFIG=live-gateway.json\r\n"
                "OPENDAOC_COMPANION_AI_GUIDE_MODEL_ALIAS=openai-small-guide\r\n",
                encoding="utf-8",
            )

            smoke.load_env_file_defaults(env_path)

            self.assertEqual(os.environ["OPENDAOC_COMPANION_AI_GATEWAY_CONFIG"], "live-gateway.json")
            self.assertEqual(os.environ["OPENDAOC_COMPANION_AI_GUIDE_MODEL_ALIAS"], "openai-small-guide")

    def test_behavior_command_follows_real_player_and_disables_autoloot(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "healer",
            "realm": 1,
            "x": 111,
            "y": 222,
            "z": 333,
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000)

        with tempfile.TemporaryDirectory() as temp_dir:
            command = service.build_behavior_command(
                args,
                request,
                ROOT / "tools" / "dummy-live-companions.csv",
                Path(temp_dir),
                requester_state={"player": {"level": 50}},
            )

        self.assertIn("--follow-nearby-player", command)
        self.assertIn("--follow-player-name", command)
        self.assertIn("LiveLeader", command)
        self.assertIn("--companion-chat-reply", command)
        self.assertEqual(command[command.index("--companion-chat-reply-channel") + 1], "party")
        self.assertEqual(command[command.index("--companion-chat-reply-cooldown") + 1], "2")
        self.assertEqual(command[command.index("--companion-personality") + 1], "calm_support")
        self.assertIn("--flee-health-percent", command)
        self.assertGreaterEqual(int(command[command.index("--flee-health-percent") + 1]), 45)
        self.assertIn("--follow-player-required-for-objective-move", command)
        self.assertNotIn("--follow-player-hold-allows-waypoint", command)
        self.assertIn("--party-external-member-names", command)
        self.assertIn("--party-assist-only", command)
        self.assertIn("--party-use-assist-command", command)
        self.assertIn("--party-follow-interval", command)
        self.assertEqual(command[command.index("--party-assist-interval") + 1], "0.6")
        self.assertEqual(command[command.index("--party-assist-attack-delay") + 1], "0")
        self.assertEqual(command[command.index("--party-follow-distance") + 1], "120")
        self.assertEqual(command[command.index("--party-follow-catchup-distance") + 1], "800")
        self.assertEqual(command[command.index("--party-follow-hard-catchup-distance") + 1], "1600")
        self.assertEqual(command[command.index("--party-follow-teleport-distance") + 1], "0")
        self.assertEqual(command[command.index("--party-encounter-mode") + 1], "standard")
        self.assertNotIn("--boss-ranged-safe-distance", command)
        self.assertNotIn("--party-preengage-ranged-safe-distance", command)
        self.assertNotIn("--boss-non-tank-follow-distance", command)
        self.assertEqual(command[command.index("--ranged-stop-distance") + 1], "650")
        self.assertEqual(command[command.index("--attack-target-in-view-prime-delay") + 1], "0.75")
        self.assertIn("--hunter", command)
        self.assertNotIn("--waypoints", command)
        self.assertNotIn("--required-target-home", command)
        self.assertIn("--flee-home", command)
        self.assertNotEqual(command[command.index("--flee-home") + 1], "111,222,333")

    def test_behavior_command_keeps_healer_from_hostile_assist_for_explicit_objective(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "healer",
            "realm": 1,
            "x": 111,
            "y": 222,
            "z": 333,
            "objectiveTarget": "Golestandt",
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000)

        with tempfile.TemporaryDirectory() as temp_dir:
            command = service.build_behavior_command(
                args,
                request,
                ROOT / "tools" / "dummy-live-companions.csv",
                Path(temp_dir),
                requester_state={"player": {"level": 50}},
            )

        self.assertNotIn("--party-use-assist-command", command)
        self.assertEqual(command[command.index("--party-assist-interval") + 1], "0")
        self.assertIn("531504,479073,2200", command)
        self.assertIn("--flee-dynamic-safe-point", command)
        self.assertIn("--flee-safe-api-scout", command)
        self.assertIn("--flee-pressure-health-percent", command)
        self.assertIn("90", command)
        self.assertIn("--flee-safe-threat-radius", command)
        self.assertIn("9000", command)
        self.assertIn("--flee-safe-point-distance", command)
        self.assertIn("10500", command)
        self.assertEqual(command[command.index("--flee-duration") + 1], "28")
        self.assertEqual(command[command.index("--flee-step") + 1], "1200")
        self.assertEqual(command[command.index("--flee-move-interval") + 1], "0.30")
        self.assertIn("--flee-movement-speed", command)
        self.assertGreaterEqual(float(command[command.index("--flee-movement-speed") + 1]), 280.0)
        self.assertNotIn("--flee-self-preserve-hold-movement", command)
        self.assertEqual(command[command.index("--healer-self-health-percent") + 1], "92")
        self.assertEqual(command[command.index("--party-heal-leader-health-percent") + 1], "92")
        self.assertEqual(command[command.index("--party-heal-leader-interval") + 1], "1.0")
        self.assertEqual(command[command.index("--self-preserve-heal-min-interval") + 1], "8.0")
        self.assertIn("--use-skills", command)
        self.assertIn("--combat-usable-api", command)
        self.assertIn("--startup-summon-pet", command)
        self.assertIn("--startup-self-buff-count", command)
        self.assertEqual(command[command.index("--startup-self-buff-count") + 1], "2")
        self.assertIn("--move", command)
        self.assertIn("--smooth-movement", command)
        self.assertIn("--combat-direct-move-distance", command)
        self.assertEqual(command[command.index("--combat-interval") + 1], "0.6")
        self.assertEqual(command[command.index("--skill-interval") + 1], "1.0")
        self.assertIn("--current-target-api-refresh", command)
        self.assertIn("--reject-target-on-server-los-failure", command)
        self.assertEqual(command[command.index("--party-target-loss-grace") + 1], "12")
        self.assertEqual(command[command.index("--party-target-removed-preserve-limit") + 1], "12")
        self.assertEqual(command[command.index("--target-loss-grace") + 1], "8")
        self.assertEqual(command[command.index("--target-timeout") + 1], "65")
        self.assertIn("--action-rotation", command)
        self.assertIn("healer-support", command)
        self.assertIn("--player-level", command)
        self.assertEqual(command[command.index("--player-level") + 1], "50")
        self.assertIn("--ideal-target-level", command)
        self.assertEqual(command[command.index("--ideal-target-level") + 1], "50")
        self.assertIn("--min-target-level", command)
        self.assertEqual(command[command.index("--min-target-level") + 1], "42")
        self.assertIn("--startup-train-full-specs", command)
        self.assertEqual(command[command.index("--startup-train-level") + 1], "50")
        self.assertIn("--live-control-file", command)
        self.assertTrue(command[command.index("--live-control-file") + 1].endswith("live-control.json"))
        self.assertIn("--live-control-interval", command)
        self.assertEqual(command[command.index("--live-control-interval") + 1], "0.5")
        self.assertIn("--no-auto-loot", command)
        self.assertNotIn("--auto-loot", command)

    def test_behavior_command_uses_objective_target_from_content_type(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "tank",
            "realm": 1,
            "region": 1,
            "contentType": "pve:moorlich",
            "x": 111,
            "y": 222,
            "z": 333,
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000, combat_home_leash_distance=4500.0)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "albtank,dummy-pass,1,0,2,Armsman,tank,531504,479073,2200\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(
                args,
                request,
                account_csv,
                Path(temp_dir) / "run",
                requester_state={"player": {"level": 50}},
            )

        self.assertIn("--require-target-name", command)
        self.assertEqual(command[command.index("--require-target-name") + 1], "moorlich")
        self.assertNotIn("--required-target-api", command)
        self.assertNotIn("--hunter-target-api-scout", command)
        self.assertEqual(command[command.index("--path-region") + 1], "1")
        self.assertIn("--party-use-assist-command", command)
        self.assertNotIn("--follow-player-required-for-objective-move", command)
        self.assertIn("--follow-player-hold-allows-waypoint", command)

    def test_behavior_command_prefers_explicit_objective_target(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "tank",
            "realm": 1,
            "region": 1,
            "contentType": "pve:old-target",
            "objectiveTarget": "moorlich",
            "x": 111,
            "y": 222,
            "z": 333,
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000, combat_home_leash_distance=4500.0)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "albtank,dummy-pass,1,0,2,Armsman,tank,531504,479073,2200\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(
                args,
                request,
                account_csv,
                Path(temp_dir) / "run",
                requester_state={"player": {"level": 50}},
            )

        self.assertEqual(command[command.index("--require-target-name") + 1], "moorlich")

    def test_dps_companion_waits_for_assist_instead_of_claiming_objective_boss(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "dps",
            "realm": 1,
            "region": 1,
            "contentType": "pve:moorlich",
            "x": 111,
            "y": 222,
            "z": 333,
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000, combat_home_leash_distance=4500.0)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "albdps,dummy-pass,1,0,11,Mercenary,dps,531504,479073,2200\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(
                args,
                request,
                account_csv,
                Path(temp_dir) / "run",
                requester_state={"player": {"level": 50}},
            )

        self.assertIn("--party-use-assist-command", command)
        self.assertNotIn("--require-target-name", command)
        self.assertNotIn("--prefer-target-name", command)
        self.assertEqual(command[command.index("--party-assist-attack-delay") + 1], "8.0")
        self.assertEqual(command[command.index("--party-rescue-assist-after") + 1], "0")
        self.assertEqual(command[command.index("--party-rescue-emergency-assist-after") + 1], "0")
        self.assertIn("--party-boss-non-tank-melee-backoff", command)
        self.assertEqual(command[command.index("--party-boss-non-tank-melee-backoff-distance") + 1], "1400")
        self.assertIn("--party-focus-pressure-melee-backoff", command)
        self.assertEqual(command[command.index("--party-burn-required-target-health-percent") + 1], "20")
        self.assertIn("--party-melee-survival-health-percent", command)
        self.assertEqual(command[command.index("--party-melee-survival-health-percent") + 1], "45")

    def test_live_boss_dps_defaults_to_caster_for_safe_contribution(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "dps",
            "realm": 1,
            "region": 1,
            "contentType": "pve:moorlich",
            "x": 531504,
            "y": 479073,
            "z": 2200,
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000, combat_home_leash_distance=4500.0)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z,specs\n"
                "albmercenary,dummy-pass,1,0,11,Mercenary,dps,531504,479073,2200,Slash|50;Dual Wield|50\n"
                "albwizard,dummy-pass,1,0,7,Wizard,dps,531504,479073,2200,Fire Magic|50\n",
                encoding="utf-8",
            )
            selected_csv = service.select_companion_accounts_csv(request, account_csv, Path(temp_dir) / "selected")
            selected_row = service.first_account_row(selected_csv)
            command = service.build_behavior_command(
                args,
                request,
                selected_csv,
                Path(temp_dir) / "run",
                requester_state={"player": {"level": 50}},
            )

        self.assertEqual(selected_row["username"], "albwizard")
        self.assertEqual(command[command.index("--action-rotation") + 1], "caster-basic")
        self.assertEqual(command[command.index("--party-assist-attack-delay") + 1], "1.0")
        self.assertEqual(command[command.index("--party-ranged-assist-extra-delay") + 1], "0")
        self.assertEqual(command[command.index("--crowd-control-interval") + 1], "0")
        self.assertIn("--boss-ranged-safe-distance", command)
        self.assertEqual(command[command.index("--boss-ranged-safe-distance") + 1], "1400")
        self.assertEqual(command[command.index("--party-preengage-ranged-safe-distance") + 1], "1500")
        self.assertNotIn("--waypoint-stop-distance", command)
        self.assertNotIn("--required-target-home", command)
        self.assertNotIn("--required-target-home-stop-distance", command)
        self.assertNotIn("--required-target-home-hunt-distance", command)
        self.assertNotIn("--target-home-max-distance", command)
        self.assertIn("--stationary-cast-actions", command)
        self.assertIn("--party-assist-travel-leader-target", command)
        self.assertNotIn("--party-require-leader-engaged", command)
        self.assertEqual(command[command.index("--startup-delay") + 1], "15")
        self.assertNotIn("--party-boss-non-tank-melee-backoff", command)
        self.assertIn("--require-target-name", command)
        self.assertEqual(command[command.index("--require-target-name") + 1], "moorlich")
        self.assertIn("--prefer-target-name", command)
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "moorlich")

    def test_healer_behavior_command_does_not_retarget_objective_boss(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "healer",
            "realm": 1,
            "region": 1,
            "contentType": "pve:moorlich",
            "x": 111,
            "y": 222,
            "z": 333,
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000, combat_home_leash_distance=4500.0)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z,specs\n"
                "albhealer,dummy-pass,1,0,6,Cleric,healer|support,531504,479073,2200,Rejuvenation|40;Enhancement|36\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(
                args,
                request,
                account_csv,
                Path(temp_dir) / "run",
                requester_state={"player": {"level": 50}},
            )

        self.assertNotIn("--party-use-assist-command", command)
        self.assertNotIn("--require-target-name", command)
        self.assertNotIn("--prefer-target-name", command)
        self.assertNotIn("--required-target-api", command)
        self.assertNotIn("--hunter-target-api-scout", command)
        self.assertIn("--current-target-api-refresh", command)
        self.assertIn("--action-rotation", command)
        self.assertIn("healer-support", command)
        self.assertIn("--boss-ranged-safe-distance", command)
        self.assertEqual(command[command.index("--boss-ranged-safe-distance") + 1], "1800")
        self.assertIn("--party-preengage-ranged-safe-distance", command)
        self.assertEqual(command[command.index("--party-preengage-ranged-safe-distance") + 1], "2000")
        self.assertEqual(command[command.index("--boss-non-tank-follow-distance") + 1], "1800")
        self.assertEqual(command[command.index("--party-rescue-assist-after") + 1], "0")
        self.assertNotIn("--party-boss-non-tank-melee-backoff", command)

    def test_behavior_command_skips_startup_train_without_specs(self) -> None:
        service = load_service()
        request = {
            "id": "req1",
            "requesterName": "LiveLeader",
            "requestedRole": "tank",
            "realm": 1,
        }
        args = mock.Mock(host="127.0.0.1", port=10300, api_port=5000)

        with tempfile.TemporaryDirectory() as temp_dir:
            account_csv = Path(temp_dir) / "accounts.csv"
            account_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "albtank,dummy-pass,1,0,2,Armsman,tank,531504,479073,2200\n",
                encoding="utf-8",
            )
            command = service.build_behavior_command(
                args,
                request,
                account_csv,
                Path(temp_dir) / "run",
                requester_state={"player": {"level": 50}},
            )

        self.assertNotIn("--startup-train-full-specs", command)

    def test_companion_dialogue_payload_uses_sanitized_summary(self) -> None:
        service = load_service()
        companion = service.ActiveCompanion(
            {"id": "req1", "requesterAccount": "secret_account", "requestedRole": "healer", "realm": 1},
            mock.Mock(),
            account="albhealer",
        )
        requester_state = {
            "player": {
                "name": "LiveLeader",
                "account": "secret_account",
                "healthPercent": 41,
                "inCombat": True,
                "x": 111,
                "y": 222,
            },
            "groupMembers": [{"name": "DeadOne", "isDead": True}],
        }

        payload = service.build_companion_dialogue_payload(companion, requester_state, "player_requested_heal")

        self.assertEqual(payload["feature"], "companion_dialogue")
        self.assertEqual(payload["role"], "healer")
        self.assertEqual(payload["personality"], "calm_support")
        self.assertEqual(payload["state"]["leader_health_band"], "low")
        self.assertEqual(payload["state"]["party_dead"], 1)
        self.assertNotIn("requesterAccount", payload)
        self.assertNotIn("player", payload)
        self.assertNotIn("x", payload["state"])

    def test_companion_dialogue_payload_includes_party_pressure_and_companion_status(self) -> None:
        service = load_service()
        companion = service.ActiveCompanion(
            {"id": "req1", "requesterAccount": "leader1", "requestedRole": "support", "realm": 1},
            mock.Mock(),
            account="albsupport",
        )
        requester_state = {
            "player": {"name": "Leader", "healthPercent": 91, "inCombat": True},
            "groupMembers": [
                {"name": "Leader", "healthPercent": 91, "targetObjectId": 1001, "targetType": "DOL.GS.GameNPC"},
                {"name": "Tank", "healthPercent": 22, "targetObjectId": 1002, "targetType": "DOL.GS.GameNPC"},
                {"name": "Mezzed", "healthPercent": 80, "isMezzed": True},
            ],
        }
        companion_state = {"player": {"healthPercent": 44, "manaPercent": 28}}

        payload = service.build_companion_dialogue_payload(companion, requester_state, "add_pressure", companion_state)

        self.assertEqual(payload["state"]["adds"], 1)
        self.assertEqual(payload["state"]["party_lowest_health_band"], "critical")
        self.assertEqual(payload["state"]["party_crowd_controlled"], 1)
        self.assertEqual(payload["state"]["companion_health_band"], "low")
        self.assertEqual(payload["state"]["companion_mana_band"], "critical")
        self.assertEqual(payload["state"]["command_intent"], "cc_add")

    def test_dialogue_event_prioritizes_dead_then_adds_then_low_health(self) -> None:
        service = load_service()

        self.assertEqual(
            service.dialogue_event_for_requester_state(
                {"player": {"healthPercent": 20, "inCombat": True}, "groupMembers": [{"isDead": True}]}
            ),
            "party_member_dead",
        )
        self.assertEqual(
            service.dialogue_event_for_requester_state(
                {
                    "player": {"healthPercent": 90, "inCombat": True},
                    "groupMembers": [
                        {"targetObjectId": 1001, "targetType": "DOL.GS.GameNPC"},
                        {"targetObjectId": 1002, "targetType": "DOL.GS.GameNPC"},
                    ],
                }
            ),
            "add_pressure",
        )
        self.assertEqual(
            service.dialogue_event_for_requester_state({"player": {"healthPercent": 41, "inCombat": True}}),
            "player_requested_heal",
        )

    def test_request_companion_dialogue_disabled_does_not_call_gateway(self) -> None:
        service = load_service()
        args = mock.Mock(dialogue_enabled=False)

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(service, "call_ai_gateway") as gateway:
            written = service.request_companion_dialogue(args, {"event_type": "status"}, Path(temp_dir) / "live-control.json")

        self.assertFalse(written)
        gateway.assert_not_called()

    def test_dialogue_enabled_from_server_config_when_cli_disabled(self) -> None:
        service = load_service()
        args = mock.Mock(dialogue_enabled=False)
        service._server_companion_config = {}
        service._server_config_fetched_at = 0.0

        with mock.patch.object(service, "api_request", return_value={"dialogue_enabled": True}) as api_request:
            self.assertTrue(service.dialogue_enabled_from_server_or_cli(args))

        api_request.assert_called_once_with(args, "GET", "/api/dummy/companions/config")

    def test_request_companion_dialogue_writes_allowed_response(self) -> None:
        service = load_service()
        args = mock.Mock(dialogue_enabled=True)
        response = {
            "allowed": True,
            "response": {
                "say_channel": "party",
                "say_text": "I will heal now.",
                "intent_hint": "heal_priority",
                "urgency": "high",
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            service, "call_ai_gateway", return_value=response
        ):
            control_path = Path(temp_dir) / "req1" / "live-control.json"
            written = service.request_companion_dialogue(args, {"event_type": "player_requested_heal"}, control_path)
            payload = control_path.read_text(encoding="utf-8")

        self.assertTrue(written)
        self.assertIn('"say_channel": "party"', payload)
        self.assertIn('"intent_hint": "heal_priority"', payload)

    def test_request_companion_guide_writes_three_to_five_guide_lines(self) -> None:
        service = load_service()
        args = mock.Mock(dialogue_enabled=True)
        response = {
            "allowed": True,
            "response": {
                "say_channel": "party",
                "guide_lines": [
                    "20레벨이면 안전한 사냥터부터 보세요.",
                    "노란색 몬스터 위주로 잡으면 안정적입니다.",
                    "위험하면 용병에게 대기라고 말하세요.",
                ],
                "source_ids": ["docs/leveling.md"],
                "confidence": "medium",
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            service, "call_ai_gateway", return_value=response
        ) as gateway:
            control_path = Path(temp_dir) / "req1" / "live-control.json"
            written = service.request_companion_guide(
                args,
                {"question": "용병아 20레벨 어디서 사냥해?"},
                control_path,
            )
            payload = json.loads(control_path.read_text(encoding="utf-8"))

        self.assertTrue(written)
        gateway.assert_called_once()
        self.assertEqual(payload["guide_lines"][0], "20레벨이면 안전한 사냥터부터 보세요.")
        self.assertEqual(payload["source_ids"], ["docs/leveling.md"])

    def test_behavior_guide_payload_carries_speaker_class_for_my_class_questions(self) -> None:
        behavior = load_behavior()
        party_state = behavior.PartyState("Leader", ["Leader"])
        party_state.update_member_condition(
            "Leader",
            behavior.PlayerConditionSnapshot(name="Leader", level=30, class_name="Cleric", class_id=6, realm=1),
        )

        player_context = behavior.companion_guide_player_context_from_context(party_state, "Leader")
        payload = behavior.build_companion_guide_payload(
            "용병아 내 직업이면 스킬 뭐 찍어?",
            role="healer",
            realm=player_context.get("player_realm") or 1,
            player_class=str(player_context.get("player_class") or ""),
            player_class_id=player_context.get("player_class_id") or 0,
            player_level=int(player_context.get("player_level") or 0),
        )

        self.assertEqual(player_context["player_class"], "Cleric")
        self.assertEqual(player_context["player_class_id"], 6)
        self.assertEqual(player_context["player_realm"], 1)
        self.assertEqual(payload["player_class"], "Cleric")
        self.assertEqual(payload["player_class_id"], 6)
        self.assertEqual(payload["realm"], "1")
        self.assertEqual(payload["player_level"], 30)

    def test_behavior_free_chat_payload_carries_safe_player_context(self) -> None:
        behavior = load_behavior()
        player_context = {
            "player_class": "Cleric",
            "player_class_id": 6,
            "player_level": 30,
            "player_realm": 1,
        }

        payload = behavior.build_companion_free_chat_payload(
            "용병아 오늘 컨디션 어때?",
            {"name": "Albtest005", "role": "healer", "personality": "calm_support"},
            player_context=player_context,
        )

        self.assertEqual(payload["player_context"]["player_class"], "Cleric")
        self.assertEqual(payload["player_context"]["player_class_id"], 6)
        self.assertEqual(payload["player_context"]["player_level"], 30)
        self.assertNotIn("player_name", payload)

    def test_behavior_persona_followup_short_question_uses_memory_topic(self) -> None:
        behavior = load_behavior()
        memory = behavior.create_companion_short_memory()
        now = 100.0
        behavior.remember_companion_persona_result(
            memory,
            question="너 어디 출신이야?",
            reply="Camelot Hills 변방 초소 출신입니다.",
            topic="origin",
            now=now,
        )

        self.assertEqual(behavior.resolve_companion_identity_intent("그럼?", memory=memory, now=now + 5.0), "background")
        self.assertEqual(
            behavior.resolve_companion_identity_intent("누구한테 배웠어?", memory=memory, now=now + 5.0),
            "mentor",
        )

    def test_behavior_identity_question_detects_spaced_origin_wording(self) -> None:
        behavior = load_behavior()

        self.assertEqual(behavior.resolve_companion_identity_intent("용병아 너 어디 출신이야?"), "origin")

    def test_behavior_profile_reply_adds_personality_tone_without_commands(self) -> None:
        behavior = load_behavior()
        reply = behavior.companion_profile_reply(
            "너 어디 출신이야?",
            {
                "name": "Albtest005",
                "origin": "Camelot Hills 변방 초소",
                "background": "국경 경비대 출신",
                "personality": "calm_support",
                "leader_address": "대장",
            },
            intent="origin",
        )

        self.assertIn("Camelot Hills", reply)
        self.assertIn("오래 버티는", reply)
        self.assertNotIn("/", reply)

    def test_behavior_profile_reply_answers_mentor_without_repeating_background(self) -> None:
        behavior = load_behavior()
        reply = behavior.companion_profile_reply(
            "누구한테 배웠어?",
            {
                "name": "Albtest005",
                "origin": "Camelot Hills 변방 초소",
                "background": "야전 치료소 조수",
                "personality": "calm_support",
                "leader_address": "대장",
            },
            intent="mentor",
        )

        self.assertIn("현장에서 배웠습니다", reply)
        self.assertIn("오래 버티는", reply)
        self.assertNotIn("예전엔", reply)

    def test_behavior_companion_chat_intent_handles_natural_command_phrases(self) -> None:
        behavior = load_behavior()

        examples = {
            "용병아 여기 있어": "wait",
            "용병아 움직이지마": "wait",
            "용병아 나 따라와": "summon",
            "용병아 옆에 있어": "summon",
            "용병아 공격하지마": "passive",
            "용병아 나 지켜": "defensive",
            "용병아 같이 쳐": "combat",
            "용병아 위험하면 도망쳐": "flee",
            "용병아 피로도 보여줘": "status",
            "용병아 친밀도 어때": "status",
            "용병아 기록 보여줘": "record",
            "용병아 다음 뭐하지": "next_action",
            "용병아 운용 추천해줘": "next_action",
        }

        for body, expected in examples.items():
            with self.subTest(body=body):
                self.assertEqual(behavior.companion_chat_intent(body), expected)

    def test_behavior_companion_chat_intent_does_not_treat_thanks_as_go(self) -> None:
        behavior = load_behavior()

        self.assertEqual(behavior.companion_chat_intent("용병아 고마워"), "thanks")

    def test_behavior_companion_status_and_record_include_contract_details(self) -> None:
        behavior = load_behavior()
        context = behavior.build_companion_chat_status_context(
            role="healer",
            command_mode=behavior.CompanionCommandMode.stay,
            health_percent=82,
            trust=77,
            fatigue=58,
            guide_enabled=True,
            free_chat_enabled=True,
            combat_metrics=[],
            action_counts={"party_heal": 3, "death_detected": 1},
            mercenary_record={
                "total_contracts": 6,
                "total_contract_minutes": 143,
                "persistent_kills": 22,
                "persistent_rescues": 4,
                "persistent_quests_completed": 2,
                "earned_titles": "위기 구원자|의뢰 해결사",
                "personal_quest_state": "completed:first_bond",
            },
        )

        status = behavior.companion_status_reply(context)
        record = behavior.companion_record_reply(context)

        self.assertIn("치유/해제", status)
        self.assertIn("대기", status)
        self.assertIn("친밀도 77", status)
        self.assertIn("피로도 58", status)
        self.assertIn("안내/대화", status)
        self.assertIn("다음은 무리해서 이어가기보다", status)
        self.assertIn("지원 3회", record)
        self.assertIn("전투불능 1회", record)
        self.assertIn("계약 6회/143분", record)
        self.assertIn("처치 22회", record)
        self.assertIn("칭호는 위기 구원자", record)
        self.assertIn("개인 의뢰는 신뢰의 첫 증표 완료", record)

    def test_behavior_companion_next_action_reply_uses_current_state(self) -> None:
        behavior = load_behavior()
        tired_context = behavior.build_companion_chat_status_context(
            role="healer",
            command_mode=behavior.CompanionCommandMode.defensive,
            health_percent=91,
            trust=80,
            fatigue=83,
            mercenary_record={"tactic": "heal_priority"},
        )
        mez_context = behavior.build_companion_chat_status_context(
            role="support",
            command_mode=behavior.CompanionCommandMode.defensive,
            health_percent=91,
            trust=80,
            fatigue=12,
            mercenary_record={"tactic": "mez_priority"},
        )

        tired = behavior.choose_companion_chat_reply("용병아 다음 뭐하지?", [], random.Random(2), status_context=tired_context)
        mez = behavior.choose_companion_chat_reply("운용 추천해줘", [], random.Random(3), status_context=mez_context)

        self.assertIn("휴식", tired)
        self.assertIn("치유/해제", tired)
        self.assertIn("둘 이상 붙으면", mez)
        self.assertIn("메즈 우선", mez)

    def test_growth_mysql_resolver_prefers_windows_client_on_windows(self) -> None:
        smoke = load_smoke()

        def fake_exists(path: Path) -> bool:
            return str(path) in {
                r"C:\Program Files\MariaDB 12.3\bin\mariadb.exe",
                "/home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb",
            }

        with mock.patch.object(smoke.growth.os, "name", "nt"), mock.patch.object(
            smoke.growth.shutil,
            "which",
            return_value=None,
        ), mock.patch.object(smoke.growth.Path, "exists", fake_exists):
            resolved = smoke.growth.resolve_mysql_bin(None)

        self.assertEqual(resolved, r"C:\Program Files\MariaDB 12.3\bin\mariadb.exe")

    def test_call_ai_gateway_can_route_companion_guide_feature(self) -> None:
        service = load_service()
        args = mock.Mock(
            ai_gateway_config="local-config.json",
            ai_gateway_model_alias="small-dialogue",
            ai_guide_model_alias="openai-small-guide",
            ai_gateway_timeout=5.0,
            repo_root=str(ROOT),
        )
        completed = mock.Mock(returncode=0, stdout='{"allowed": true, "response": {}}')

        with mock.patch.object(service.subprocess, "run", return_value=completed) as run:
            result = service.call_ai_gateway(
                args,
                {"question": "용병아 어디가?"},
                feature="companion_guide",
            )

        self.assertTrue(result["allowed"])
        command = run.call_args.args[0]
        self.assertIn("--feature", command)
        self.assertIn("companion_guide", command)
        self.assertIn("openai-small-guide", command)
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertEqual(run.call_args.kwargs["env"]["PYTHONIOENCODING"], "utf-8")

    def test_request_companion_dialogue_rejects_unsafe_allowed_response(self) -> None:
        service = load_service()
        args = mock.Mock(dialogue_enabled=True)
        response = {
            "allowed": True,
            "response": {
                "say_channel": "party",
                "say_text": "/release now",
                "intent_hint": "heal_priority",
                "urgency": "high",
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            service, "call_ai_gateway", return_value=response
        ):
            control_path = Path(temp_dir) / "req1" / "live-control.json"
            written = service.request_companion_dialogue(args, {"event_type": "player_requested_heal"}, control_path)

        self.assertFalse(written)
        self.assertFalse(control_path.exists())

    def test_api_request_adds_password_to_all_companion_api_calls(self) -> None:
        service = load_service()
        args = mock.Mock(api_url="http://127.0.0.1:5000", api_timeout=1.0, api_password="secret")
        response = mock.Mock()
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=None)
        response.read.return_value = b'{"ok": true}'

        with mock.patch.object(service.urllib.request, "urlopen", return_value=response) as urlopen:
            service.api_request(args, "POST", "/api/dummy/companions/requests/claim")
            service.api_request(args, "GET", "/api/dummy/companions/requests", {"status": "queued"})

        post_request = urlopen.call_args_list[0].args[0]
        get_request = urlopen.call_args_list[1].args[0]
        self.assertIn("password=secret", post_request.full_url)
        self.assertIn("password=secret", get_request.full_url)

    def test_call_ai_gateway_timeout_returns_blocked_result(self) -> None:
        service = load_service()
        args = mock.Mock(repo_root=str(ROOT), ai_gateway_timeout=0.1, ai_gateway_config="", ai_gateway_model_alias="small-dialogue")

        with mock.patch.object(
            service.subprocess,
            "run",
            side_effect=service.subprocess.TimeoutExpired(cmd=["gateway"], timeout=0.1),
        ):
            result = service.call_ai_gateway(args, {"event_type": "player_requested_heal"})

        self.assertFalse(result["allowed"])
        self.assertEqual(result["blocked_reason"], "gateway_timeout")

    def test_handle_request_rejects_dead_requester_before_spawning(self) -> None:
        service = load_service()
        args = mock.Mock(accounts_csv="accounts.csv", dry_run=False)
        request = {"id": "req1", "requesterAccount": "leader1", "requesterName": "Leader"}
        state = {"player": {"name": "Leader", "isAlive": False, "isDead": True}}

        with mock.patch.object(service, "fetch_requester_state", return_value=state), mock.patch.object(
            service, "update_request_status"
        ) as update_status, mock.patch.object(service.subprocess, "Popen") as popen:
            service.handle_request(args, request, {})

        popen.assert_not_called()
        update_status.assert_called_once_with(
            args,
            "req1",
            "failed",
            "cannot spawn companion: requester dead",
            close_reason="system_spawn_blocked",
        )

    def test_handle_request_rejects_full_party_before_spawning(self) -> None:
        service = load_service()
        args = mock.Mock(accounts_csv="accounts.csv", dry_run=False)
        request = {"id": "req1", "requesterAccount": "leader1", "requesterName": "Leader"}
        state = {
            "player": {"name": "Leader", "isAlive": True, "isDead": False},
            "groupMembers": [
                {"name": "Leader", "account": "leader1"},
                {"name": "Player2", "account": "real2"},
                {"name": "Player3", "account": "real3"},
                {"name": "Player4", "account": "real4"},
                {"name": "Player5", "account": "real5"},
                {"name": "Player6", "account": "real6"},
                {"name": "Player7", "account": "real7"},
                {"name": "Player8", "account": "real8"},
            ],
        }

        with mock.patch.object(service, "fetch_requester_state", return_value=state), mock.patch.object(
            service, "update_request_status"
        ) as update_status, mock.patch.object(service.subprocess, "Popen") as popen:
            service.handle_request(args, request, {})

        popen.assert_not_called()
        update_status.assert_called_once_with(
            args,
            "req1",
            "failed",
            "cannot spawn companion: group is full (8/8)",
            close_reason="party_full",
        )

    def test_handle_request_rejects_when_pending_companion_reserves_last_slot(self) -> None:
        service = load_service()
        args = mock.Mock(accounts_csv="accounts.csv", dry_run=False)
        request = {"id": "req2", "requesterAccount": "leader1", "requesterName": "Leader"}
        state = {
            "player": {"name": "Leader", "isAlive": True, "isDead": False},
            "groupMembers": [
                {"name": "Leader", "account": "leader1"},
                {"name": "Player2", "account": "real2"},
                {"name": "Player3", "account": "real3"},
                {"name": "Player4", "account": "real4"},
                {"name": "Player5", "account": "real5"},
                {"name": "Player6", "account": "real6"},
                {"name": "Player7", "account": "real7"},
            ],
        }
        active = {
            "req1": service.ActiveCompanion(
                {"id": "req1", "requesterAccount": "leader1", "requestedRole": "healer"},
                mock.Mock(),
                account="albhealer",
            )
        }

        with mock.patch.object(service, "fetch_requester_state", return_value=state), mock.patch.object(
            service, "update_request_status"
        ) as update_status, mock.patch.object(service.subprocess, "Popen") as popen:
            service.handle_request(args, request, active)

        popen.assert_not_called()
        update_status.assert_called_once_with(
            args,
            "req2",
            "failed",
            "cannot spawn companion: pending companion already reserves remaining group slot",
            close_reason="party_full",
        )
        self.assertIn("req1", active)

    def test_companion_slot_block_allows_vacant_party_slot(self) -> None:
        service = load_service()
        state = {
            "player": {"name": "Leader", "isAlive": True, "isDead": False},
            "groupMembers": [
                {"name": "Leader", "account": "leader1"},
                {"name": "Player2", "account": "real2"},
            ],
        }

        reason = service.companion_slot_block_reason({}, {"requesterAccount": "leader1"}, state)

        self.assertEqual(reason, "")

    def test_handle_request_marks_failed_when_no_companion_accounts_available(self) -> None:
        service = load_service()
        args = mock.Mock(accounts_csv="accounts.csv", dry_run=False, run_dir="runs")
        request = {"id": "req1", "requesterAccount": "leader1", "requesterName": "Leader"}
        state = {"player": {"name": "Leader", "isAlive": True, "isDead": False}}

        with mock.patch.object(service, "fetch_requester_state", return_value=state), mock.patch.object(
            service, "online_accounts_from_pool", return_value=set()
        ), mock.patch.object(
            service,
            "select_companion_accounts_csv",
            side_effect=ValueError("no companion accounts left"),
        ), mock.patch.object(service, "update_request_status") as update_status, mock.patch.object(
            service.subprocess, "Popen"
        ) as popen:
            service.handle_request(args, request, {})

        popen.assert_not_called()
        update_status.assert_called_once_with(
            args,
            "req1",
            "failed",
            "cannot spawn companion: no companion accounts left",
            close_reason="system_spawn_failed",
        )

    def test_handle_request_attaches_online_companion_before_active(self) -> None:
        service = load_service()
        args = mock.Mock(
            accounts_csv="accounts.csv",
            dry_run=False,
            repo_root=str(ROOT),
            run_dir="runs",
            attach_group=True,
        )
        request = {"id": "req1", "requesterAccount": "leader1", "requesterName": "Leader"}
        state = {"player": {"name": "Leader", "isAlive": True, "isDead": False}}
        process = mock.Mock()

        with mock.patch.object(service, "fetch_requester_state", return_value=state), mock.patch.object(
            service, "select_companion_accounts_csv", return_value=Path("selected.csv")
        ), mock.patch.object(service, "build_behavior_command", return_value=["python3", "worker.py"]), mock.patch.object(
            service.subprocess, "Popen", return_value=process
        ) as popen, mock.patch.object(
            service, "first_account_username", return_value="companion1"
        ), mock.patch.object(
            service, "wait_for_companion_online", return_value="companion1"
        ), mock.patch.object(
            service, "attach_companion_to_request", return_value=(True, "")
        ) as attach, mock.patch.object(service, "update_request_status") as update_status:
            active = {}
            service.handle_request(args, request, active)

        popen.assert_called_once_with(["python3", "worker.py"], cwd=str(ROOT))
        attach.assert_called_once_with(args, "req1", "companion1")
        self.assertIn("req1", active)
        update_status.assert_any_call(args, "req1", "grouping", "live companion behavior client started; waiting for grouping", "companion1")

    def test_handle_request_emits_join_dialogue_after_attach(self) -> None:
        service = load_service()
        args = mock.Mock(
            accounts_csv="accounts.csv",
            dry_run=False,
            repo_root=str(ROOT),
            run_dir="runs",
            attach_group=True,
            dialogue_enabled=True,
        )
        request = {"id": "req1", "requesterAccount": "leader1", "requesterName": "Leader", "requestedRole": "healer"}
        state = {"player": {"name": "Leader", "isAlive": True, "isDead": False}}
        process = mock.Mock()

        with mock.patch.object(service, "fetch_requester_state", return_value=state), mock.patch.object(
            service, "select_companion_accounts_csv", return_value=Path("selected.csv")
        ), mock.patch.object(service, "build_behavior_command", return_value=["python3", "worker.py"]), mock.patch.object(
            service.subprocess, "Popen", return_value=process
        ), mock.patch.object(
            service, "first_account_username", return_value="companion1"
        ), mock.patch.object(
            service, "wait_for_companion_online", return_value="companion1"
        ), mock.patch.object(
            service, "attach_companion_to_request", return_value=(True, "")
        ), mock.patch.object(service, "update_request_status"), mock.patch.object(
            service, "request_companion_dialogue", return_value=True
        ) as request_dialogue:
            service.handle_request(args, request, {})

        request_dialogue.assert_called_once()
        payload = request_dialogue.call_args.args[1]
        self.assertEqual(payload["event_type"], "companion_joined")
        self.assertEqual(request_dialogue.call_args.args[2], Path("runs") / "req1" / "live-control.json")

    def test_poll_active_uses_event_cooldown_and_retries_failed_dialogue(self) -> None:
        service = load_service()
        args = mock.Mock(dialogue_enabled=True, dialogue_min_interval=5.0, run_dir="runs")
        process = mock.Mock()
        process.poll.return_value = None
        active = {
            "req1": service.ActiveCompanion(
                {"id": "req1", "requesterAccount": "leader1", "requestedRole": "support"},
                process,
                account="albsupport",
            )
        }
        low_health_state = {"player": {"healthPercent": 41, "inCombat": True, "isAlive": True, "isDead": False}}
        dead_state = {
            "player": {"healthPercent": 80, "inCombat": True, "isAlive": True, "isDead": False},
            "groupMembers": [{"name": "DeadOne", "isDead": True}],
        }
        dialogue_state = {}

        with mock.patch.object(service, "fetch_requester_state", side_effect=[low_health_state, low_health_state, dead_state]), mock.patch.object(
            service, "emit_companion_dialogue", side_effect=[False, True, True]
        ) as emit_dialogue, mock.patch.object(service, "choose_release_request_for_real_player_join", return_value=""):
            service.poll_active(args, active, release_counts={}, dialogue_state=dialogue_state)
            service.poll_active(args, active, release_counts={}, dialogue_state=dialogue_state)
            service.poll_active(args, active, release_counts={}, dialogue_state=dialogue_state)

        self.assertEqual(emit_dialogue.call_count, 3)
        self.assertIn("req1:player_requested_heal", dialogue_state)
        self.assertIn("req1:party_member_dead", dialogue_state)

    def test_handle_request_excludes_online_pool_accounts(self) -> None:
        service = load_service()
        args = mock.Mock(
            accounts_csv="accounts.csv",
            dry_run=True,
            repo_root=str(ROOT),
            run_dir="runs",
            attach_group=True,
        )
        request = {"id": "req1", "requesterAccount": "leader1", "requesterName": "Leader"}
        state = {"player": {"name": "Leader", "isAlive": True, "isDead": False}}

        with mock.patch.object(service, "fetch_requester_state", return_value=state), mock.patch.object(
            service, "online_accounts_from_pool", return_value={"albhealer1"}
        ), mock.patch.object(service, "select_companion_accounts_csv", return_value=Path("selected.csv")) as select, mock.patch.object(
            service, "first_account_username", return_value="albhealer2"
        ), mock.patch.object(
            service, "build_behavior_command", return_value=["python3", "worker.py"]
        ), mock.patch("builtins.print"):
            service.handle_request(args, request, {})

        self.assertIn("albhealer1", select.call_args.args[3])

    def test_handle_request_excludes_accounts_in_reuse_cooldown(self) -> None:
        service = load_service()
        args = mock.Mock(
            accounts_csv="accounts.csv",
            dry_run=True,
            repo_root=str(ROOT),
            run_dir="runs",
            attach_group=True,
            account_reuse_cooldown=75.0,
        )
        request = {"id": "req1", "requesterAccount": "leader1", "requesterName": "Leader"}
        state = {"player": {"name": "Leader", "isAlive": True, "isDead": False}}
        cooldowns = {"albhealer1": service.time.monotonic() + 30.0}

        with mock.patch.object(service, "fetch_requester_state", return_value=state), mock.patch.object(
            service, "online_accounts_from_pool", return_value=set()
        ), mock.patch.object(service, "select_companion_accounts_csv", return_value=Path("selected.csv")) as select, mock.patch.object(
            service, "first_account_username", return_value="albhealer2"
        ), mock.patch.object(
            service, "build_behavior_command", return_value=["python3", "worker.py"]
        ), mock.patch("builtins.print"):
            service.handle_request(args, request, {}, cooldowns)

        self.assertIn("albhealer1", select.call_args.args[3])

    def test_stop_all_active_companions_cleans_processes_and_statuses(self) -> None:
        service = load_service()
        args = mock.Mock()
        process = mock.Mock()
        active = {"req1": service.ActiveCompanion({"id": "req1"}, process, account="companion1")}

        with mock.patch.object(service, "stop_companion") as stop_companion, mock.patch.object(
            service, "update_request_status"
        ) as update_status:
            service.stop_all_active_companions(args, active, "done")

        stop_companion.assert_called_once_with(process, control_path=None)
        update_status.assert_called_once_with(args, "req1", "completed", "done", "companion1")
        self.assertEqual(active, {})

    def test_request_companion_quit_writes_live_control_command(self) -> None:
        service = load_service()
        with tempfile.TemporaryDirectory() as tmp:
            control_path = Path(tmp) / "live-control.json"

            service.request_companion_quit(control_path)

            payload = json.loads(control_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["commands"], ["/quit"])
            self.assertEqual(payload["intent_hint"], "leave")
            self.assertEqual(payload["quit_after_sit_seconds"], 4.0)
            self.assertGreater(payload["revision"], 0)

    def test_request_companion_quit_can_send_leave_farewell_before_quit(self) -> None:
        service = load_service()
        with tempfile.TemporaryDirectory() as tmp:
            control_path = Path(tmp) / "live-control.json"

            service.request_companion_quit(control_path, farewell_line=service.companion_leave_farewell_line("party_kick"))

            payload = json.loads(control_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["commands"][0], "/g 알겠습니다. 계약을 정리하고 파티에서 빠지겠습니다. 빈자리는 제가 비워두겠습니다.")
            self.assertEqual(payload["commands"][1], "/quit")
            self.assertEqual(payload["intent_hint"], "leave")

    def test_service_stop_file_defaults_to_run_dir_and_is_detected(self) -> None:
        service = load_service()
        with tempfile.TemporaryDirectory() as tmp:
            args = mock.Mock(run_dir=tmp, stop_file="")
            stop_file = service.service_stop_file(args)

            self.assertEqual(stop_file, Path(tmp) / "companion-service.stop")
            self.assertFalse(service.service_stop_requested(args))

            stop_file.write_text("stop", encoding="utf-8")

            self.assertTrue(service.service_stop_requested(args))

    def test_handle_leave_request_releases_active_companions_for_requester(self) -> None:
        service = load_service()
        args = mock.Mock()
        leader_process = mock.Mock()
        other_process = mock.Mock()
        active = {
            "active1": service.ActiveCompanion(
                {"id": "active1", "requesterAccount": "leader1", "requestedRole": "dps"},
                leader_process,
                account="albdps",
            ),
            "other": service.ActiveCompanion(
                {"id": "other", "requesterAccount": "leader2", "requestedRole": "healer"},
                other_process,
                account="albhealer",
            ),
        }
        leave_request = {"id": "leave1", "requesterAccount": "leader1", "requestedRole": "leave"}

        with mock.patch.object(service, "detach_companion_from_request", return_value=(True, "")) as detach, mock.patch.object(
            service, "stop_companion"
        ) as stop_companion, mock.patch.object(service, "update_request_status") as update_status:
            service.handle_request(args, leave_request, active)

        detach.assert_called_once_with(args, "active1", "albdps")
        stop_companion.assert_called_once_with(
            leader_process,
            control_path=None,
            farewell_line="알겠습니다. 계약을 정리하고 파티에서 빠지겠습니다. 빈자리는 제가 비워두겠습니다.",
        )
        update_status.assert_has_calls(
            [
                mock.call(
                    args,
                    "active1",
                    "completed",
                    "leave request; companion released",
                    "albdps",
                    close_reason="leader_dismissed",
                ),
                mock.call(args, "leave1", "completed", "leave request acknowledged; released 1 companion(s)"),
            ]
        )
        self.assertEqual(set(active), {"other"})

    def test_handle_leave_request_without_active_companion_is_completed(self) -> None:
        service = load_service()
        args = mock.Mock()
        leave_request = {"id": "leave1", "requesterAccount": "leader1", "requestedRole": "leave"}

        with mock.patch.object(service, "update_request_status") as update_status:
            service.handle_request(args, leave_request, {})

        update_status.assert_called_once_with(args, "leave1", "completed", "leave request acknowledged; no active companion")

    def test_live_companion_party_smoke_script_builds_leader_and_service_commands(self) -> None:
        smoke = load_smoke()
        args = smoke.build_parser().parse_args(
            [
                "--dry-run",
                "--leader-account",
                "dummy300",
                "--leader-hold",
                "90",
                "--leader-startup-delay",
                "45",
                "--service-max-runtime",
                "120",
                "--api-password",
                "secret",
                "--dialogue-enabled",
                "--ai-gateway-config",
                "ai.json",
                "--ai-gateway-model-alias",
                "small-dialogue",
                "--ai-gateway-timeout",
                "3",
                "--dialogue-min-interval",
                "1",
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir)
            leader = smoke.build_leader_command(args, "dummy300", "Dummy300", case_dir)
            service = smoke.build_service_command(args, case_dir / "service")

        self.assertIn("--startup-delay", leader)
        self.assertEqual(leader[leader.index("--startup-delay") + 1], "45.0")
        self.assertNotIn("--speak-state-changes", leader)
        self.assertNotIn("--state-speech-min-interval", leader)
        self.assertIn("--party-size", leader)
        self.assertIn("--current-target-api-refresh", leader)
        self.assertIn("--required-target-tank-commit-health-percent", leader)
        self.assertGreaterEqual(int(leader[leader.index("--required-target-tank-commit-health-percent") + 1]), 40)
        self.assertIn("--flee-melee-counterattack-health-floor", leader)
        self.assertGreaterEqual(int(leader[leader.index("--flee-melee-counterattack-health-floor") + 1]), 40)
        self.assertIn("--command", leader)
        self.assertEqual(leader[leader.index("--command") + 1], "")
        self.assertIn("--max-runtime", service)
        self.assertEqual(service[service.index("--max-runtime") + 1], "210.0")
        self.assertEqual(smoke.service_wait_timeout(args), 230.0)
        self.assertIn("--hold", service)
        self.assertEqual(service[service.index("--hold") + 1], "135.0")
        self.assertIn("--accounts-csv", service)
        self.assertEqual(Path(service[service.index("--accounts-csv") + 1]), LIVE_COMPANION_POOL_PATH)
        self.assertIn("--api-password", service)
        self.assertEqual(service[service.index("--api-password") + 1], "secret")
        self.assertIn("--dialogue-enabled", service)
        self.assertEqual(service[service.index("--ai-gateway-config") + 1], "ai.json")
        self.assertEqual(service[service.index("--ai-gateway-model-alias") + 1], "small-dialogue")
        self.assertEqual(service[service.index("--ai-gateway-timeout") + 1], "3.0")
        self.assertEqual(service[service.index("--dialogue-min-interval") + 1], "1.0")

    def test_live_companion_party_smoke_leader_party_command_enables_live_control(self) -> None:
        smoke = load_smoke()
        args = smoke.build_parser().parse_args(["--leader-party-command", "명령어", "--leader-party-command", "ㄱㄱ"])

        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir)
            leader = smoke.build_leader_command(args, "dummy300", "Dummy300", case_dir)

        self.assertIn("--live-control-file", leader)
        self.assertIn("leader-control.json", leader[leader.index("--live-control-file") + 1])
        self.assertEqual(smoke.leader_party_command_texts(args), ["명령어", "ㄱㄱ"])
        self.assertNotIn("--speak-state-changes", leader)

    def test_live_companion_party_smoke_filters_service_pool_for_leader_and_joiner_accounts(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            companion_pool = Path(temp_dir) / "companions.csv"
            companion_pool.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "dummy300,dummy-pass,1,0,2,Armsman,tank|dps,531504,479073,2200\n"
                "albtest007,dummy-pass,1,0,7,Wizard,dps,531504,479073,2200\n"
                "albtest005,dummy-pass,1,0,6,Cleric,healer|support,531504,479073,2200\n"
                "albtest003,dummy-pass,1,0,11,Mercenary,dps,531504,479073,2200\n",
                encoding="utf-8",
            )
            args = smoke.build_parser().parse_args(
                [
                    "--dry-run",
                    "--companion-accounts-csv",
                    str(companion_pool),
                ]
            )

            filtered = smoke.prepare_service_accounts_csv(args, Path(temp_dir), "dummy300", "albtest007")
            rows = smoke.read_accounts(filtered)

        self.assertNotEqual(filtered, companion_pool)
        self.assertEqual([row["username"] for row in rows], ["albtest005", "albtest003"])

    def test_live_companion_party_smoke_joiner_command_builds_real_player_party_dps(self) -> None:
        smoke = load_smoke()
        args = smoke.build_parser().parse_args(
            [
                "--dry-run",
                "--leader-hold",
                "90",
                "--joiner-hold",
                "70",
                "--joiner-party-follow-distance",
                "480",
                "--joiner-party-assist-attack-delay",
                "0.2",
                "--joiner-flee-pressure-health-percent",
                "65",
                "--joiner-flee-health-percent",
                "30",
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            joiner = smoke.build_joiner_command(args, "dummy300", "Dummy300", "Dummy040", Path(temp_dir))

        self.assertIn("--follow-nearby-player", joiner)
        self.assertIn("--follow-player-name", joiner)
        self.assertEqual(joiner[joiner.index("--follow-player-name") + 1], "Dummy040")
        self.assertIn("--party-external-member-names", joiner)
        self.assertEqual(joiner[joiner.index("--party-external-member-names") + 1], "Dummy040")
        self.assertIn("--party-assist-only", joiner)
        self.assertIn("--hunter", joiner)
        self.assertIn("--combat", joiner)
        self.assertEqual(joiner[joiner.index("--party-follow-distance") + 1], "480.0")
        self.assertEqual(joiner[joiner.index("--party-assist-attack-delay") + 1], "0.2")
        self.assertEqual(joiner[joiner.index("--flee-pressure-health-percent") + 1], "65")
        self.assertEqual(joiner[joiner.index("--flee-health-percent") + 1], "30")
        self.assertEqual(joiner[joiner.index("--behavior-profile") + 1], "party-dps")
        self.assertEqual(joiner[joiner.index("--action-rotation") + 1], "melee-burst")
        self.assertIn("--no-auto-loot", joiner)

    def test_live_companion_party_smoke_joiner_command_uses_live_pool_class_rotation_for_explicit_joiner(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            leader_candidates = Path(temp_dir) / "leaders.csv"
            companion_pool = Path(temp_dir) / "companions.csv"
            leader_candidates.write_text(
                "username,password,realm,char_index,class_id,class_name,roles\n"
                "dummy300,dummy-pass,1,0,2,Armsman,tank|dps\n",
                encoding="utf-8",
            )
            companion_pool.write_text(
                "username,password,realm,char_index,class_id,class_name,roles,home_x,home_y,home_z\n"
                "albwizard,dummy-pass,1,0,7,Wizard,dps,531504,479073,2200\n"
                "albminstrel,dummy-pass,1,0,4,Minstrel,support|dps,531504,479073,2200\n",
                encoding="utf-8",
            )
            args = smoke.build_parser().parse_args(
                [
                    "--dry-run",
                    "--leader-candidates-csv",
                    str(leader_candidates),
                    "--companion-accounts-csv",
                    str(companion_pool),
                ]
            )

            wizard_joiner = smoke.build_joiner_command(
                args,
                "albwizard",
                "Albwizard",
                "Dummy040",
                Path(temp_dir),
            )
            minstrel_joiner = smoke.build_joiner_command(
                args,
                "albminstrel",
                "Albminstrel",
                "Dummy040",
                Path(temp_dir),
            )

        self.assertEqual(wizard_joiner[wizard_joiner.index("--behavior-profile") + 1], "party-dps")
        self.assertEqual(wizard_joiner[wizard_joiner.index("--action-rotation") + 1], "caster-basic")
        self.assertNotIn("--startup-speed-song", wizard_joiner)
        self.assertEqual(minstrel_joiner[minstrel_joiner.index("--action-rotation") + 1], "hybrid")
        self.assertIn("--startup-speed-song", minstrel_joiner)

    def test_live_companion_party_smoke_resets_pool_to_staging_not_boss_center(self) -> None:
        smoke = load_smoke()
        args = smoke.build_parser().parse_args(["--dry-run", "--leader-account", "dummy300"])

        with mock.patch.object(smoke.growth, "reset_growth_characters") as reset:
            smoke.reset_live_accounts(args, "dummy300")

        start_point = reset.call_args.kwargs["start_point"]
        self.assertNotEqual(smoke.BARFOG_STAGING_HOME, smoke.BARFOG_HOME)
        self.assertEqual((start_point.x, start_point.y, start_point.z), smoke.BARFOG_STAGING_HOME)

    def test_live_companion_party_smoke_can_reset_pool_at_objective_start(self) -> None:
        smoke = load_smoke()
        args = smoke.build_parser().parse_args(
            ["--dry-run", "--leader-account", "dummy300", "--reset-start-location", "objective"]
        )

        with mock.patch.object(smoke.growth, "reset_growth_characters") as reset:
            smoke.reset_live_accounts(args, "dummy300")

        start_point = reset.call_args.kwargs["start_point"]
        self.assertEqual((start_point.x, start_point.y, start_point.z), smoke.BARFOG_HOME)

    def test_live_companion_party_smoke_api_json_adds_password_to_all_calls(self) -> None:
        smoke = load_smoke()
        args = smoke.build_parser().parse_args(["--api-password", "secret"])
        response = mock.Mock()
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=None)
        response.read.return_value = b'{"ok": true}'

        with mock.patch.object(smoke.urllib.request, "urlopen", return_value=response) as urlopen:
            smoke.api_json(args, "POST", "/api/dummy/companions/requests", {"player": "Leader"})
            smoke.api_json(args, "GET", "/api/dummy/companions/requests", {"status": "queued"})

        post_request = urlopen.call_args_list[0].args[0]
        get_request = urlopen.call_args_list[1].args[0]
        self.assertIn("password=secret", post_request.full_url)
        self.assertIn("password=secret", get_request.full_url)

    def test_live_companion_party_smoke_extracts_request_id(self) -> None:
        smoke = load_smoke()

        self.assertEqual(smoke.request_id_from_payload({"request": {"id": "abc"}}), "abc")
        self.assertEqual(smoke.request_id_from_payload({"Request": {"Id": "def"}}), "def")

    def test_live_companion_party_smoke_request_carries_objective_target(self) -> None:
        smoke = load_smoke()
        args = smoke.build_parser().parse_args(
            ["--target-name", "moorlich", "--requested-capabilities", "speed_song|stealth"]
        )

        with mock.patch.object(smoke, "api_json", return_value={"request": {"id": "req1"}}) as api_json:
            request_id = smoke.create_companion_request(args, "Dummy040", "tank", "smoke")

        self.assertEqual(request_id, "req1")
        query = api_json.call_args.args[3]
        self.assertEqual(query["contentType"], "pve")
        self.assertEqual(query["objectiveTarget"], "moorlich")
        self.assertEqual(query["requestedCapabilities"], "speed_song|stealth")
        self.assertEqual((query["x"], query["y"], query["z"]), smoke.BARFOG_HOME)

    def test_live_companion_party_smoke_chat_request_uses_staging_position(self) -> None:
        smoke = load_smoke()
        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "player-chat-only"]))

        with mock.patch.object(smoke, "api_json", return_value={"request": {"id": "req1"}}) as api_json:
            request_id = smoke.create_companion_request(args, "Dummy040", "tank", "smoke")

        self.assertEqual(request_id, "req1")
        query = api_json.call_args.args[3]
        self.assertEqual(query["objectiveTarget"], "")
        self.assertEqual((query["x"], query["y"], query["z"]), smoke.BARFOG_STAGING_HOME)

    def test_live_companion_party_smoke_caster_dps_request_uses_objective_home(self) -> None:
        smoke = load_smoke()
        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "caster-dps"]))

        with mock.patch.object(smoke, "api_json", return_value={"request": {"id": "req1"}}) as api_json:
            request_id = smoke.create_companion_request(args, "Dummy300", "dps", "smoke")

        self.assertEqual(request_id, "req1")
        query = api_json.call_args.args[3]
        self.assertEqual(query["objectiveTarget"], "moorlich")
        self.assertEqual(query["requestedCapabilities"], "caster_dps")
        self.assertEqual((query["x"], query["y"], query["z"]), smoke.BARFOG_HOME)

    def test_live_companion_party_smoke_caster_dps_service_accounts_start_at_staging(self) -> None:
        smoke = load_smoke()
        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "caster-dps"]))

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "companions.csv"
            run_dir = Path(temp_dir) / "run"
            source.write_text(
                "username,password,realm,char_index,class_id,class_name,roles\n"
                "albwizard,dummy-pass,1,0,12,Wizard,dps|caster\n",
                encoding="utf-8",
            )
            args.companion_accounts_csv = source

            filtered = smoke.prepare_service_accounts_csv(args, run_dir)
            with filtered.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            (rows[0]["start_x"], rows[0]["start_y"], rows[0]["start_z"]),
            tuple(str(part) for part in smoke.BARFOG_STAGING_HOME),
        )

    def test_live_companion_party_smoke_parses_expected_companion_actions(self) -> None:
        smoke = load_smoke()

        args = smoke.build_parser().parse_args(["--expect-companion-actions", "speed-song|stealth,res"])

        self.assertEqual(args.expect_companion_actions, ["speed_song", "stealth", "resurrect"])

    def test_live_companion_party_smoke_parses_allowed_death_thresholds(self) -> None:
        smoke = load_smoke()

        args = smoke.build_parser().parse_args(
            [
                "--allow-companion-deaths",
                "2",
                "--allow-leader-deaths",
                "1",
                "--allow-joiner-deaths",
                "3",
            ]
        )

        self.assertEqual(args.allow_companion_deaths, 2)
        self.assertEqual(args.allow_leader_deaths, 1)
        self.assertEqual(args.allow_joiner_deaths, 3)

    def test_live_companion_party_smoke_parses_custom_leader_profile(self) -> None:
        smoke = load_smoke()

        args = smoke.build_parser().parse_args(
            ["--leader-behavior-profile", "party-tank", "--leader-action-rotation", "melee-basic"]
        )

        self.assertEqual(args.leader_behavior_profile, "party-tank")
        self.assertEqual(args.leader_action_rotation, "melee-basic")

    def test_live_companion_party_smoke_parses_reset_start_location(self) -> None:
        smoke = load_smoke()

        args = smoke.build_parser().parse_args(["--reset-start-location", "objective"])

        self.assertEqual(args.reset_start_location, "objective")

    def test_live_companion_party_smoke_stealth_passive_profile_sets_capability_defaults(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "stealth-passive"]))

        self.assertEqual(args.target_name, "")
        self.assertEqual(args.requested_capabilities, "stealth")
        self.assertEqual(args.expect_companion_actions, ["stealth"])
        self.assertEqual(args.leader_hold, 55.0)
        self.assertEqual(args.companion_hold, 55.0)
        self.assertEqual(args.service_max_runtime, 90.0)
        self.assertEqual(args.leader_startup_delay, 25.0)

    def test_live_companion_party_smoke_stealth_passive_profile_preserves_explicit_runtime_overrides(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(
            smoke.build_parser().parse_args(
                [
                    "--smoke-profile",
                    "stealth-passive",
                    "--leader-hold",
                    "80",
                    "--companion-hold",
                    "75",
                    "--service-max-runtime",
                    "110",
                    "--leader-startup-delay",
                    "15",
                    "--requested-capabilities",
                    "speed_song|stealth",
                    "--expect-companion-actions",
                    "speed_song|stealth",
                ]
            )
        )

        self.assertEqual(args.target_name, "")
        self.assertEqual(args.requested_capabilities, "speed_song|stealth")
        self.assertEqual(args.expect_companion_actions, ["speed_song", "stealth"])
        self.assertEqual(args.leader_hold, 80.0)
        self.assertEqual(args.companion_hold, 75.0)
        self.assertEqual(args.service_max_runtime, 110.0)
        self.assertEqual(args.leader_startup_delay, 15.0)

    def test_live_companion_party_smoke_healer_tankleader_profile_sets_healer_defaults(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "healer-tankleader"]))

        self.assertEqual(args.roles, ["healer"])
        self.assertEqual(args.expect_companion_actions, ["heal"])

    def test_live_companion_party_smoke_healer_forced_heal_profile_damages_leader(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "healer-forced-heal"]))

        self.assertEqual(args.roles, ["healer"])
        self.assertEqual(args.expect_companion_actions, ["heal"])
        self.assertEqual(args.healer_test_damage_delay, 2.0)
        self.assertEqual(args.healer_test_damage_percent, 35.0)
        self.assertEqual(args.leader_behavior_profile, "party-tank")
        self.assertEqual(args.leader_action_rotation, "melee-basic")

    def test_live_companion_party_smoke_damage_hook_targets_companion_test_api(self) -> None:
        smoke = load_smoke()
        args = smoke.build_parser().parse_args(["--api-password", "secret"])

        with mock.patch.object(smoke, "api_json", return_value={"ok": True}) as api_json:
            result = smoke.damage_player_via_test_hook(args, name="Leader", account="dummy300", health_percent=35)

        self.assertEqual(result, {"ok": True})
        api_json.assert_called_once_with(
            args,
            "POST",
            "/api/dummy/companions/test/damage",
            {"player": "Leader", "account": "dummy300", "healthPercent": 35},
        )

    def test_live_companion_party_smoke_player_command_combat_profile_sets_command_defaults(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "player-command-combat"]))

        self.assertEqual(args.roles, ["healer"])
        self.assertEqual(args.target_name, "moorlich")
        self.assertEqual(args.leader_behavior_profile, "party-tank")
        self.assertEqual(args.leader_action_rotation, "melee-basic")
        self.assertEqual(args.leader_party_commands, ["명령어", "ㄱㄱ"])
        self.assertEqual(args.reset_start_location, "objective")
        self.assertIn("companion_chat_reply", args.expect_companion_actions)
        self.assertIn("companion_command_attack", args.expect_companion_actions)
        self.assertNotIn("party_assist", args.expect_companion_actions)
        self.assertNotIn("damage_done", args.expect_companion_actions)
        self.assertEqual(
            args.leader_party_command_start_delay,
            smoke.PLAYER_COMMAND_DEFAULT_COMMAND_START_DELAY_AFTER_STARTUP_SECONDS,
        )
        self.assertEqual(args.leader_party_command_gap, 5.0)
        self.assertEqual(args.leader_control_apply_timeout, 20.0)
        self.assertEqual(args.allow_leader_deaths, 1)
        self.assertGreaterEqual(args.allow_companion_deaths, 2)

    def test_live_companion_party_smoke_player_command_modes_profile_sets_command_defaults(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "player-command-modes"]))

        self.assertEqual(args.roles, ["tank"])
        self.assertEqual(args.target_name, "")
        self.assertEqual(args.reset_start_location, "objective")
        self.assertEqual(args.leader_party_commands, ["명령어", "수동태세", "방어태세", "대기", "여기로", "따라와"])
        self.assertIn("companion_command_help", args.expect_companion_actions)
        self.assertIn("companion_command_passive", args.expect_companion_actions)
        self.assertIn("companion_command_defensive", args.expect_companion_actions)
        self.assertIn("companion_command_stay", args.expect_companion_actions)
        self.assertIn("companion_command_summon", args.expect_companion_actions)
        self.assertIn("companion_command_follow", args.expect_companion_actions)
        self.assertNotIn("companion_command_clear_target", args.expect_companion_actions)
        self.assertEqual(
            args.leader_party_command_start_delay,
            smoke.PLAYER_COMMAND_DEFAULT_COMMAND_START_DELAY_AFTER_STARTUP_SECONDS,
        )
        self.assertEqual(args.leader_party_command_gap, 4.0)
        self.assertEqual(args.allow_leader_deaths, 1)
        self.assertGreaterEqual(args.allow_companion_deaths, 2)

    def test_live_companion_party_smoke_player_chat_only_profile_sets_idle_leader_defaults(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "player-chat-only"]))

        self.assertEqual(args.roles, ["tank"])
        self.assertEqual(args.target_name, "")
        self.assertEqual(args.reset_start_location, "staging")
        self.assertTrue(args.leader_chat_only)
        self.assertEqual(args.leader_behavior_profile, "custom")
        self.assertEqual(args.leader_action_rotation, "none")
        self.assertEqual(
            args.leader_party_commands,
            ["용병아 너 어디 출신이야?", "용병아 오늘 어때?", "대기"],
        )
        self.assertEqual(args.expect_companion_actions, ["companion_chat_reply"])
        self.assertEqual(args.allow_leader_deaths, 0)
        self.assertEqual(args.leader_hold, 110.0)
        self.assertEqual(args.leader_startup_delay, 8.0)
        self.assertEqual(args.companion_hold, 90.0)
        self.assertEqual(args.service_max_runtime, 130.0)
        self.assertEqual(args.request_active_timeout, 90.0)
        self.assertEqual(args.leader_party_command_start_delay, 1.0)
        self.assertEqual(args.leader_party_command_gap, 1.0)

    def test_live_companion_party_smoke_stealth_passive_profile_uses_single_dps_request(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "stealth-passive"]))

        self.assertEqual(args.roles, ["dps"])
        self.assertEqual(args.requested_capabilities, "stealth")
        self.assertEqual(args.expect_companion_actions, ["stealth"])
        self.assertTrue(args.leader_chat_only)
        self.assertEqual(args.leader_behavior_profile, "custom")
        self.assertEqual(args.leader_action_rotation, "none")

    def test_live_companion_party_smoke_chat_only_leader_command_disables_hunter_and_combat(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "player-chat-only"]))

        with tempfile.TemporaryDirectory() as temp_dir:
            leader = smoke.build_leader_command(args, "dummy300", "Dummy300", Path(temp_dir))

        self.assertNotIn("--hunter", leader)
        self.assertNotIn("--combat", leader)
        self.assertNotIn("--party-local-rescue-target", leader)
        self.assertNotIn("--waypoints", leader)
        self.assertNotIn("--required-target-home", leader)
        self.assertNotIn("--required-target-home-hunt-distance", leader)
        self.assertNotIn("--target-auto-lowest-visible-level", leader)
        self.assertNotIn("--current-target-api-refresh", leader)
        self.assertNotIn("--hunter-target-api-scout", leader)
        self.assertNotIn("--combat-usable-api", leader)
        self.assertNotIn("--use-skills", leader)
        self.assertNotIn("--auto-loot", leader)
        self.assertIn("--no-auto-loot", leader)
        self.assertEqual(leader[leader.index("--behavior-profile") + 1], "custom")
        self.assertEqual(leader[leader.index("--action-rotation") + 1], "none")
        self.assertIn("--live-control-file", leader)
        self.assertIn("--round-wall-timeout-seconds", leader)
        self.assertIn("--allow-round-wall-timeout-success", leader)
        self.assertIn("--command", leader)
        self.assertEqual(leader[leader.index("--command") + 1], "")

    def test_live_companion_party_smoke_player_command_all_roles_profile_sets_command_defaults(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "player-command-all-roles"]))

        self.assertEqual(args.roles, ["tank", "healer", "dps", "support"])
        self.assertEqual(args.target_name, "moorlich")
        self.assertEqual(args.requested_capabilities, "defensive_tank|healer|caster_dps|speed_song")
        self.assertEqual(args.reset_start_location, "objective")
        self.assertEqual(args.leader_party_commands, ["명령어", "수동태세", "방어태세", "대기", "여기로", "따라와", "ㄱㄱ"])
        self.assertIn("companion_command_attack", args.expect_companion_actions)
        self.assertIn("companion_command_summon", args.expect_companion_actions)
        self.assertIn("party_assist", args.expect_companion_actions)
        self.assertIn("damage_done", args.expect_companion_actions)
        self.assertIn("heal", args.expect_companion_actions)
        self.assertEqual(
            args.leader_party_command_start_delay,
            smoke.PLAYER_COMMAND_DEFAULT_COMMAND_START_DELAY_AFTER_STARTUP_SECONDS,
        )
        self.assertEqual(args.allow_leader_deaths, 1)

    def test_live_companion_party_smoke_support_speed_song_profile_sets_support_defaults(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "support-speed-song"]))

        self.assertEqual(args.roles, ["support"])
        self.assertEqual(args.target_name, "")
        self.assertTrue(args.leader_chat_only)
        self.assertEqual(args.leader_behavior_profile, "custom")
        self.assertEqual(args.leader_action_rotation, "none")
        self.assertEqual(args.requested_capabilities, "speed_song")
        self.assertEqual(args.expect_companion_actions, ["speed_song"])
        self.assertEqual(args.leader_hold, 55.0)
        self.assertEqual(args.companion_hold, 55.0)
        self.assertEqual(args.service_max_runtime, 90.0)
        self.assertEqual(args.leader_startup_delay, 25.0)

    def test_live_companion_party_smoke_support_speed_song_leader_has_round_wall_success(self) -> None:
        smoke = load_smoke()
        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "support-speed-song"]))

        with tempfile.TemporaryDirectory() as temp_dir:
            leader = smoke.build_leader_command(args, "dummy300", "Dummy300", Path(temp_dir))

        self.assertIn("--round-wall-timeout-seconds", leader)
        self.assertEqual(leader[leader.index("--round-wall-timeout-seconds") + 1], "100.0")
        self.assertIn("--allow-round-wall-timeout-success", leader)

    def test_live_companion_party_smoke_support_crowd_control_profile_sets_combat_defaults(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "support-crowd-control"]))

        self.assertEqual(args.roles, ["support"])
        self.assertEqual(args.target_name, "moorlich")
        self.assertEqual(args.requested_capabilities, "crowd_control")
        self.assertEqual(args.expect_companion_actions, ["crowd_control"])
        self.assertEqual(args.allow_leader_deaths, 1)
        self.assertEqual(args.leader_behavior_profile, "party-tank")
        self.assertEqual(args.leader_action_rotation, "melee-basic")
        self.assertEqual(args.leader_hold, 90.0)
        self.assertEqual(args.companion_hold, 90.0)
        self.assertEqual(args.service_max_runtime, 120.0)
        self.assertEqual(args.leader_startup_delay, 35.0)
        self.assertEqual(args.service_flee_pressure_health_percent, 50.0)
        self.assertEqual(args.service_flee_health_percent, 32.0)

    def test_live_companion_party_smoke_support_crowd_control_profile_allows_companion_deaths(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "support-crowd-control"]))

        self.assertEqual(args.allow_companion_deaths, smoke.ROLE_SMOKE_ALLOW_COMPANION_DEATHS)

    def test_live_companion_party_smoke_mixed_real_join_profile_allows_companion_deaths(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "mixed-real-join"]))

        self.assertEqual(args.allow_companion_deaths, 3)

    def test_live_companion_party_smoke_tank_protection_profile_sets_tank_defaults(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "tank-protection"]))

        self.assertEqual(args.roles, ["tank"])
        self.assertEqual(args.target_name, "moorlich")
        self.assertEqual(args.requested_capabilities, "defensive_tank|group_support")
        self.assertEqual(args.expect_companion_actions, ["literal_taunt_used", "party_protection"])
        self.assertEqual(args.allow_leader_deaths, 1)
        self.assertEqual(args.leader_behavior_profile, "party-dps")
        self.assertEqual(args.leader_action_rotation, "melee-burst")
        self.assertEqual(args.leader_hold, 90.0)
        self.assertEqual(args.companion_hold, 90.0)
        self.assertEqual(args.service_max_runtime, 120.0)
        self.assertEqual(args.leader_startup_delay, 35.0)

    def test_live_companion_party_smoke_caster_dps_profile_sets_caster_defaults(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "caster-dps"]))

        self.assertEqual(args.roles, ["dps"])
        self.assertEqual(args.target_name, "moorlich")
        self.assertEqual(args.requested_capabilities, "caster_dps")
        self.assertEqual(args.expect_companion_actions, ["damage_done"])
        self.assertEqual(args.leader_behavior_profile, "party-tank")
        self.assertEqual(args.leader_action_rotation, "melee-basic")
        self.assertEqual(args.leader_hold, 110.0)
        self.assertEqual(args.companion_hold, 135.0)
        self.assertEqual(args.service_max_runtime, 180.0)
        self.assertEqual(args.leader_startup_delay, 35.0)
        self.assertEqual(args.allow_leader_deaths, 1)
        self.assertEqual(args.allow_companion_deaths, 3)

    def test_live_companion_party_smoke_healer_resurrection_profile_uses_safe_staging_defaults(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "healer-resurrection"]))

        self.assertEqual(args.roles, ["tank", "healer", "dps"])
        self.assertEqual(args.expect_companion_actions, ["resurrect"])
        self.assertEqual(args.leader_behavior_profile, "party-tank")
        self.assertEqual(args.leader_action_rotation, "melee-basic")
        self.assertEqual(args.reset_start_location, "staging")
        self.assertEqual(args.leader_hold, 180.0)
        self.assertEqual(args.leader_startup_delay, 20.0)
        self.assertEqual(args.companion_hold, 180.0)
        self.assertEqual(args.service_max_runtime, 210.0)
        self.assertEqual(args.service_healer_boss_ranged_safe_distance, 2200.0)
        self.assertEqual(args.service_healer_party_preengage_ranged_safe_distance, 2400.0)
        self.assertEqual(args.service_healer_boss_non_tank_follow_distance, 2200.0)
        self.assertEqual(args.allow_leader_deaths, 1)
        self.assertEqual(args.allow_companion_deaths, 3)

    def test_live_companion_party_smoke_healer_resurrection_profile_preserves_explicit_objective_reset(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(
            smoke.build_parser().parse_args(
                ["--smoke-profile", "healer-resurrection", "--reset-start-location", "objective"]
            )
        )

        self.assertEqual(args.reset_start_location, "objective")

    def test_live_companion_party_smoke_healer_resurrection_real_join_profile_tunes_joiner_pressure_defaults(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(
            smoke.build_parser().parse_args(["--smoke-profile", "healer-resurrection", "--real-player-join"])
        )

        self.assertTrue(args.real_player_join)
        self.assertEqual(args.target_name, "")
        self.assertTrue(args.leader_chat_only)
        self.assertEqual(args.leader_behavior_profile, "custom")
        self.assertEqual(args.leader_action_rotation, "none")
        self.assertEqual(args.allow_joiner_deaths, 3)
        self.assertEqual(args.joiner_hold, 175.0)
        self.assertEqual(args.joiner_party_follow_distance, 450.0)
        self.assertEqual(args.joiner_party_assist_attack_delay, 0.3)
        self.assertEqual(args.joiner_flee_pressure_health_percent, 0.0)
        self.assertEqual(args.joiner_flee_health_percent, 0.0)
        self.assertEqual(args.service_healer_flee_pressure_health_percent, 50.0)
        self.assertEqual(args.service_healer_flee_health_percent, 32.0)
        self.assertEqual(args.service_flee_pressure_health_percent, 50.0)
        self.assertEqual(args.service_flee_health_percent, 32.0)
        self.assertEqual(args.resurrection_victim_kill_delay, 5.0)

    def test_live_companion_party_smoke_healer_resurrection_real_join_profile_preserves_joiner_overrides(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(
            smoke.build_parser().parse_args(
                [
                    "--smoke-profile",
                    "healer-resurrection",
                    "--real-player-join",
                    "--joiner-hold",
                    "88",
                    "--joiner-party-follow-distance",
                    "520",
                    "--joiner-party-assist-attack-delay",
                    "0.4",
                    "--joiner-flee-pressure-health-percent",
                    "75",
                    "--joiner-flee-health-percent",
                    "40",
                    "--allow-joiner-deaths",
                    "2",
                ]
            )
        )

        self.assertEqual(args.allow_joiner_deaths, 2)
        self.assertEqual(args.joiner_hold, 88.0)
        self.assertEqual(args.joiner_party_follow_distance, 520.0)
        self.assertEqual(args.joiner_party_assist_attack_delay, 0.4)
        self.assertEqual(args.joiner_flee_pressure_health_percent, 75.0)
        self.assertEqual(args.joiner_flee_health_percent, 40.0)

    def test_live_companion_party_smoke_healer_resurrection_real_join_builds_idle_joiner(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(
            smoke.build_parser().parse_args(["--smoke-profile", "healer-resurrection", "--real-player-join"])
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            joiner = smoke.build_joiner_command(args, "albtest007", "Albtest007", "Dummy300", Path(temp_dir))

        self.assertEqual(joiner[joiner.index("--behavior-profile") + 1], "custom")
        self.assertEqual(joiner[joiner.index("--action-rotation") + 1], "none")
        self.assertNotIn("--hunter", joiner)
        self.assertNotIn("--combat", joiner)
        self.assertNotIn("--use-skills", joiner)
        self.assertIn("--auto-release-on-death", joiner)
        self.assertEqual(joiner[joiner.index("--death-release-delay") + 1], "90.0")

    def test_live_companion_party_smoke_build_service_command_passes_healer_spacing_overrides(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(
            smoke.build_parser().parse_args(
                [
                    "--smoke-profile",
                    "healer-resurrection",
                    "--service-healer-boss-ranged-safe-distance",
                    "2300",
                    "--service-healer-party-preengage-ranged-safe-distance",
                    "2500",
                    "--service-healer-boss-non-tank-follow-distance",
                    "2250",
                ]
            )
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            service = smoke.build_service_command(args, Path(temp_dir) / "service")

        self.assertEqual(service[service.index("--healer-boss-ranged-safe-distance") + 1], "2300.0")
        self.assertEqual(service[service.index("--healer-party-preengage-ranged-safe-distance") + 1], "2500.0")
        self.assertEqual(service[service.index("--healer-boss-non-tank-follow-distance") + 1], "2250.0")

    def test_live_companion_service_boss_role_flags_accept_healer_spacing_overrides(self) -> None:
        service = load_service()

        args = service.build_parser().parse_args(
            [
                "--healer-boss-ranged-safe-distance",
                "2300",
                "--healer-party-preengage-ranged-safe-distance",
                "2500",
                "--healer-boss-non-tank-follow-distance",
                "2250",
            ]
        )

        flags = service.live_companion_boss_role_flags("healer", "healer-support", args)

        self.assertEqual(flags[flags.index("--boss-ranged-safe-distance") + 1], "2300")
        self.assertEqual(flags[flags.index("--party-preengage-ranged-safe-distance") + 1], "2500")
        self.assertEqual(flags[flags.index("--boss-non-tank-follow-distance") + 1], "2250")

    def test_live_companion_party_smoke_healer_resurrection_builds_leader_form_up_gates(self) -> None:
        smoke = load_smoke()
        args = smoke.apply_smoke_profile(
            smoke.build_parser().parse_args(
                [
                    "--smoke-profile",
                    "healer-resurrection",
                    "--real-player-join",
                ]
            )
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            leader = smoke.build_leader_command(args, "dummy300", "Dummy300", Path(temp_dir))

        self.assertEqual(leader[leader.index("--party-min-ready") + 1], "2")
        self.assertEqual(leader[leader.index("--party-ready-max-leader-distance") + 1], "2800.0")
        self.assertEqual(leader[leader.index("--party-form-up-delay") + 1], "4.0")
        self.assertEqual(leader[leader.index("--party-form-up-timeout") + 1], "45.0")
        self.assertEqual(leader[leader.index("--party-pre-pull-home-stop-distance") + 1], "1800.0")
        flee_pressure_indexes = [index for index, value in enumerate(leader) if value == "--flee-pressure-health-percent"]
        flee_health_indexes = [index for index, value in enumerate(leader) if value == "--flee-health-percent"]
        self.assertEqual(leader[flee_pressure_indexes[-1] + 1], "50")
        self.assertEqual(leader[flee_health_indexes[-1] + 1], "32")

    def test_live_companion_party_smoke_caster_dps_builds_leader_form_up_gates(self) -> None:
        smoke = load_smoke()
        args = smoke.apply_smoke_profile(
            smoke.build_parser().parse_args(["--smoke-profile", "caster-dps"])
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            leader = smoke.build_leader_command(args, "dummy300", "Dummy300", Path(temp_dir))

        self.assertEqual(leader[leader.index("--party-min-ready") + 1], "2")
        self.assertEqual(leader[leader.index("--party-ready-max-leader-distance") + 1], "2800.0")
        self.assertEqual(leader[leader.index("--party-form-up-delay") + 1], "4.0")
        self.assertEqual(leader[leader.index("--party-form-up-timeout") + 1], "75.0")
        self.assertEqual(leader[leader.index("--party-pre-pull-home-stop-distance") + 1], "2800.0")

    def test_live_companion_party_smoke_choose_leader_prefers_pure_tank_for_party_tank_profile(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            candidates = Path(temp_dir) / "leaders.csv"
            candidates.write_text(
                "username,password,realm,char_index,class_id,class_name,roles\n"
                "dummy040,dummy-pass,1,0,1,Paladin,tank|support\n"
                "dummy300,dummy-pass,1,0,2,Armsman,tank|dps\n"
                "dummy041,dummy-pass,1,0,11,Mercenary,dps\n",
                encoding="utf-8",
            )
            args = smoke.build_parser().parse_args(
                [
                    "--leader-candidates-csv",
                    str(candidates),
                    "--leader-behavior-profile",
                    "party-tank",
                ]
            )

            with mock.patch.object(smoke, "fetch_state", return_value=None):
                self.assertEqual(smoke.choose_leader_account(args), "dummy300")

    def test_live_companion_party_smoke_choose_leader_prefers_dps_for_tank_protection_profile(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            candidates = Path(temp_dir) / "leaders.csv"
            candidates.write_text(
                "username,password,realm,char_index,class_id,class_name,roles\n"
                "dummy040,dummy-pass,1,0,1,Paladin,tank|support\n"
                "dummy300,dummy-pass,1,0,2,Armsman,tank|dps\n"
                "dummy041,dummy-pass,1,0,11,Mercenary,dps\n",
                encoding="utf-8",
            )
            args = smoke.apply_smoke_profile(
                smoke.build_parser().parse_args(
                    [
                        "--leader-candidates-csv",
                        str(candidates),
                        "--smoke-profile",
                        "tank-protection",
                    ]
                )
            )

            with mock.patch.object(smoke, "fetch_state", return_value=None):
                self.assertEqual(smoke.choose_leader_account(args), "dummy041")

    def test_live_companion_party_smoke_choose_joiner_prefers_pure_dps_for_real_join(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            candidates = Path(temp_dir) / "leaders.csv"
            candidates.write_text(
                "username,password,realm,char_index,class_id,class_name,roles\n"
                "dummy040,dummy-pass,1,0,1,Paladin,tank|support\n"
                "dummy300,dummy-pass,1,0,2,Armsman,tank|dps\n"
                "dummy041,dummy-pass,1,0,11,Mercenary,dps\n",
                encoding="utf-8",
            )
            args = smoke.build_parser().parse_args(
                [
                    "--leader-candidates-csv",
                    str(candidates),
                    "--real-player-join",
                ]
            )

            with mock.patch.object(smoke, "fetch_state", return_value=None):
                self.assertEqual(smoke.choose_joiner_account(args, "dummy040"), "dummy041")

    def test_live_companion_party_smoke_choose_joiner_dry_run_uses_ranked_role_metadata(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            candidates = Path(temp_dir) / "leaders.csv"
            candidates.write_text(
                "username,password,realm,char_index,class_id,class_name,roles\n"
                "dummy040,dummy-pass,1,0,1,Paladin,tank|support\n"
                "dummy300,dummy-pass,1,0,2,Armsman,tank|dps\n"
                "dummy041,dummy-pass,1,0,11,Mercenary,dps\n",
                encoding="utf-8",
            )
            args = smoke.build_parser().parse_args(
                [
                    "--leader-candidates-csv",
                    str(candidates),
                    "--real-player-join",
                    "--dry-run",
                ]
            )

            self.assertEqual(smoke.choose_joiner_account(args, "dummy040"), "dummy041")

    def test_live_companion_party_smoke_choose_joiner_prefers_tank_for_mixed_real_join_profile(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            candidates = Path(temp_dir) / "leaders.csv"
            candidates.write_text(
                "username,password,realm,char_index,class_id,class_name,roles\n"
                "dummy040,dummy-pass,1,0,1,Paladin,tank|support\n"
                "dummy300,dummy-pass,1,0,2,Armsman,tank|dps\n"
                "dummy041,dummy-pass,1,0,11,Mercenary,dps\n",
                encoding="utf-8",
            )
            args = smoke.apply_smoke_profile(
                smoke.build_parser().parse_args(
                    [
                        "--leader-candidates-csv",
                        str(candidates),
                        "--smoke-profile",
                        "mixed-real-join",
                    ]
                )
            )

            with mock.patch.object(smoke, "fetch_state", return_value=None):
                self.assertEqual(smoke.choose_joiner_account(args, "dummy040"), "dummy300")

    def test_live_companion_party_smoke_mixed_real_join_profile_sets_group_defaults(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "mixed-real-join"]))

        self.assertTrue(args.real_player_join)
        self.assertEqual(args.roles, ["tank"])
        self.assertEqual(args.expect_companion_actions, ["party_protection"])
        self.assertEqual(args.leader_hold, 120.0)
        self.assertEqual(args.leader_startup_delay, 45.0)
        self.assertEqual(args.companion_hold, 125.0)
        self.assertEqual(args.service_max_runtime, 170.0)
        self.assertEqual(args.joiner_hold, 85.0)
        self.assertEqual(args.release_timeout, 45.0)
        self.assertEqual(args.request_active_timeout, 60.0)
        self.assertEqual(args.allow_companion_deaths, 3)

    def test_live_companion_party_smoke_mixed_real_join_disables_party_resurrection_wait(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(smoke.build_parser().parse_args(["--smoke-profile", "mixed-real-join"]))

        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(
                smoke,
                "resolve_joiner_row",
                return_value={"roles": "tank", "class_name": "Armsman"},
            ):
                leader = smoke.build_leader_command(args, "dummy040", "Dummy040", Path(temp_dir))
                joiner = smoke.build_joiner_command(args, "dummy300", "Dummy300", "Dummy040", Path(temp_dir))

        self.assertEqual(leader[leader.index("--party-resurrect-interval") + 1], "0.0")
        self.assertEqual(joiner[joiner.index("--party-resurrect-interval") + 1], "0.0")
        self.assertEqual(leader[leader.index("--round-wall-timeout-seconds") + 1], "185.0")
        self.assertIn("--allow-round-wall-timeout-success", leader)
        self.assertEqual(joiner[joiner.index("--round-wall-timeout-seconds") + 1], "101.0")
        self.assertIn("--allow-round-wall-timeout-success", joiner)

    def test_live_companion_party_smoke_mixed_real_join_profile_preserves_manual_overrides(self) -> None:
        smoke = load_smoke()

        args = smoke.apply_smoke_profile(
            smoke.build_parser().parse_args(
                [
                    "--smoke-profile",
                    "mixed-real-join",
                    "--roles",
                    "healer|support",
                    "--expect-companion-actions",
                    "heal|speed_song",
                    "--leader-hold",
                    "130",
                    "--leader-startup-delay",
                    "30",
                    "--companion-hold",
                    "140",
                    "--service-max-runtime",
                    "200",
                    "--joiner-hold",
                    "95",
                    "--release-timeout",
                    "50",
                    "--request-active-timeout",
                    "70",
                ]
            )
        )

        self.assertTrue(args.real_player_join)
        self.assertEqual(args.roles, ["healer", "support"])
        self.assertEqual(args.expect_companion_actions, ["heal", "speed_song"])
        self.assertEqual(args.leader_hold, 130.0)
        self.assertEqual(args.leader_startup_delay, 30.0)
        self.assertEqual(args.companion_hold, 140.0)
        self.assertEqual(args.service_max_runtime, 200.0)
        self.assertEqual(args.joiner_hold, 95.0)
        self.assertEqual(args.release_timeout, 50.0)
        self.assertEqual(args.request_active_timeout, 70.0)

    def test_live_companion_party_smoke_summarizes_companion_metrics_only(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "leader").mkdir()
            (root / "service" / "req").mkdir(parents=True)
            (root / "leader" / "leader-metrics.csv").write_text(
                "username,damage_done,action_party_assist\nleader,99,7\n",
                encoding="utf-8",
            )
            (root / "service" / "req" / "companion-metrics.csv").write_text(
                "username,damage_done,healing_done,action_party_assist,action_party_follow,action_validated_taunt_spell,action_validated_party_guard_member,action_live_control_say,action_companion_chat_reply,action_companion_command_attack_assist,action_death_detected\n"
                "companion,12,4,3,5,2,1,1,2,1,1\n",
                encoding="utf-8",
            )
            (root / "service" / "req" / "companion-encounters.jsonl").write_text(
                '{"event":"live_control_applied","actions":{"live_control_say":1},"command_count":1}\n'
                '{"event":"companion_command_mode_change","intent":"passive","mode":"passive"}\n'
                '{"event":"companion_command_mode_change","intent":"defensive","mode":"defensive"}\n'
                '{"event":"companion_command_mode_change","intent":"wait","mode":"stay"}\n'
                '{"event":"companion_command_mode_change","intent":"follow","mode":"follow"}\n'
                '{"event":"companion_chat_reply","intent":"help"}\n'
                '{"event":"companion_chat_reply","intent":"summon"}\n'
                '{"event":"companion_chat_reply","intent":"wait"}\n',
                encoding="utf-8",
            )
            (root / "service" / "req" / "live-control.json").write_text(
                '{"say_channel":"party","say_text":"I will heal now.","intent_hint":"heal_priority"}',
                encoding="utf-8",
            )

            summary = smoke.summarize_encounters(root)

        self.assertEqual(summary["damage_done"], 12)
        self.assertEqual(summary["heal"], 4)
        self.assertEqual(summary["party_assist"], 3)
        self.assertEqual(summary["party_follow"], 5)
        self.assertEqual(summary["taunt"], 2)
        self.assertEqual(summary["party_protection"], 1)
        self.assertEqual(summary["dialogue_live_control"], 1)
        self.assertEqual(summary["dialogue_party"], 1)
        self.assertEqual(summary["dialogue_heal_priority"], 1)
        self.assertEqual(summary["dialogue_live_control_applied"], 1)
        self.assertEqual(summary["dialogue_live_control_say"], 2)
        self.assertEqual(summary["companion_chat_reply"], 2)
        self.assertEqual(summary["companion_command_attack"], 1)
        self.assertEqual(summary["companion_command_passive"], 1)
        self.assertEqual(summary["companion_command_defensive"], 1)
        self.assertEqual(summary["companion_command_stay"], 1)
        self.assertEqual(summary["companion_command_follow"], 1)
        self.assertEqual(summary["companion_command_help"], 1)
        self.assertEqual(summary["companion_command_summon"], 1)
        self.assertEqual(summary["companion_command_wait"], 1)
        self.assertEqual(summary["death"], 1)

    def test_live_companion_party_smoke_uses_combat_damage_messages_as_damage_evidence(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "service" / "req").mkdir(parents=True)
            (root / "service" / "req" / "companion-metrics.csv").write_text(
                "\n".join(
                    [
                        "username,damage_done,healing_done,action_combat_damage_msg,action_validated_spell,action_validated_dot_spell",
                        "companion,0,0,2,1,1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = smoke.summarize_encounters(root)

        self.assertEqual(summary["damage_done"], 2)

    def test_live_companion_party_smoke_summarizes_companion_jsonl_events_without_metrics(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "service" / "req").mkdir(parents=True)
            (root / "service" / "req" / "companion-encounters.jsonl").write_text(
                "\n".join(
                    [
                        '{"event":"companion_chat_reply","intent":"chatter"}',
                        '{"event":"companion_command_attack_assist","speaker":"Dummy300"}',
                        '{"event":"companion_command_clear_target","speaker":"Dummy300"}',
                        '{"event":"party_assist","target":"moorlich"}',
                        '{"event":"party_follow","leader":"Dummy300"}',
                        '{"event":"combat_finish","damage_done":18}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = smoke.summarize_encounters(root)

        self.assertEqual(summary["companion_chat_reply"], 1)
        self.assertEqual(summary["companion_command_attack"], 1)
        self.assertEqual(summary["companion_command_clear_target"], 1)
        self.assertEqual(summary["damage_done"], 18)
        self.assertEqual(summary["party_assist"], 1)
        self.assertEqual(summary["party_follow"], 1)

    def test_live_companion_party_smoke_counts_preflight_taunt_spell_cast_message(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "service" / "req").mkdir(parents=True)
            (root / "service" / "req" / "companion-encounters.jsonl").write_text(
                "\n".join(
                    [
                        '{"event":"combat_plan_preflight","character":"Albtest001","taunt_spell_names":["Infuriate"]}',
                        '{"event":"server_message","character":"Albtest001","text":"Infuriate 주문을 시전했습니다!"}',
                        '{"event":"server_message","character":"Albtest001","text":"Heal 주문을 시전했습니다!"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = smoke.summarize_encounters(root)

        self.assertEqual(summary["literal_taunt_used"], 1)
        self.assertEqual(summary["taunt"], 1)
        self.assertEqual(summary["tank_control_established"], 1)

    def test_live_companion_party_smoke_uses_custom_leader_profile_flags(self) -> None:
        smoke = load_smoke()
        args = smoke.build_parser().parse_args(
            [
                "--dry-run",
                "--leader-behavior-profile",
                "party-tank",
                "--leader-action-rotation",
                "melee-basic",
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            leader = smoke.build_leader_command(args, "dummy300", "Dummy300", Path(temp_dir))

        self.assertEqual(leader[leader.index("--behavior-profile") + 1], "party-tank")
        self.assertEqual(leader[leader.index("--action-rotation") + 1], "melee-basic")

    def test_live_companion_party_smoke_summarizes_support_utility_actions(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "service" / "req").mkdir(parents=True)
            (root / "service" / "req" / "companion-metrics.csv").write_text(
                "\n".join(
                    [
                        "username,damage_done,healing_done,action_validated_party_cure_curedisease,action_validated_crowd_control_spell,action_precombat_speed_song_spell,action_maintain_stealth_spell",
                        "companion,0,0,1,2,1,3",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = smoke.summarize_encounters(root)

        self.assertEqual(summary["cure"], 1)
        self.assertEqual(summary["crowd_control"], 2)
        self.assertEqual(summary["speed_song"], 1)
        self.assertEqual(summary["stealth"], 3)

    def test_live_companion_party_smoke_counts_speed_song_server_message_from_preflight(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service_dir = root / "service" / "req"
            service_dir.mkdir(parents=True)
            (service_dir / "companion-encounters.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "event": "combat_plan_preflight",
                                "character": "Albtest012",
                                "speed_song_spell_names": ["Motivational Anthem"],
                            }
                        ),
                        json.dumps(
                            {
                                "event": "server_message",
                                "character": "Albtest012",
                                "text": "Motivational Anthem을 연주하기 시작합니다!",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = smoke.summarize_encounters(root)

        self.assertEqual(summary["speed_song"], 1)

    def test_live_companion_party_smoke_counts_stealth_server_message_from_preflight(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service_dir = root / "service" / "req"
            service_dir.mkdir(parents=True)
            (service_dir / "companion-encounters.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "event": "combat_plan_preflight",
                                "character": "Albtest029",
                                "stealth_spell_names": ["스텔스"],
                            }
                        ),
                        json.dumps(
                            {
                                "event": "server_message",
                                "character": "Albtest029",
                                "text": "이제 숨어 있습니다!",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = smoke.summarize_encounters(root)

        self.assertEqual(summary["stealth"], 1)

    def test_live_companion_party_smoke_summarizes_validated_resurrection_actions(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "service" / "req").mkdir(parents=True)
            (root / "service" / "req" / "companion-metrics.csv").write_text(
                "\n".join(
                    [
                        "username,damage_done,healing_done,action_validated_party_resurrect_member,action_party_resurrect_target_hold",
                        "companion,0,0,1,5",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = smoke.summarize_encounters(root)

        self.assertEqual(summary["resurrect"], 1)

    def test_live_companion_party_smoke_counts_resurrection_server_message(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "service" / "req").mkdir(parents=True)
            (root / "service" / "req" / "encounters.jsonl").write_text(
                "\n".join(
                    [
                        '{"event":"server_message","character":"Albtest005","text":"Resurrection 주문을 시전하기 시작합니다!"}',
                        '{"event":"server_message","character":"Albtest005","text":"Resurrection 주문을 시전했습니다!"}',
                        '{"event":"server_message","character":"Albtest005","text":"Raise Fallen 주문을 시전했습니다!"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = smoke.summarize_encounters(root)

        self.assertEqual(summary["resurrect"], 2)

    def test_live_control_revision_uses_nanoseconds_to_avoid_fast_collisions(self) -> None:
        service = load_service()
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(service.time, "time", return_value=123.0), mock.patch.object(
            smoke.time, "time", return_value=123.0
        ):
            service_path = Path(temp_dir) / "service-live-control.json"
            smoke_path = Path(temp_dir) / "smoke-live-control.json"
            service.write_companion_live_control(service_path, {"say_channel": "party", "say_text": "first"})
            first_service = service_path.read_text(encoding="utf-8")
            service.write_companion_live_control(service_path, {"say_channel": "party", "say_text": "second"})
            second_service = service_path.read_text(encoding="utf-8")
            smoke.write_live_control(smoke_path, {"say": "first"})
            first_smoke = smoke_path.read_text(encoding="utf-8")
            smoke.write_live_control(smoke_path, {"say": "second"})
            second_smoke = smoke_path.read_text(encoding="utf-8")

        self.assertNotEqual(service.json.loads(first_service)["revision"], service.json.loads(second_service)["revision"])
        self.assertNotEqual(smoke.json.loads(first_smoke)["revision"], smoke.json.loads(second_smoke)["revision"])

    def test_live_companion_party_smoke_waits_for_live_control_revision(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            revision = smoke.write_live_control(log_dir / "control.json", {"commands": ["/invite Player"]})
            (log_dir / "leader-encounters.jsonl").write_text(
                smoke.json.dumps({"event": "live_control_applied", "revision": revision}) + "\n",
                encoding="utf-8",
            )

            self.assertTrue(smoke.wait_for_live_control_applied(log_dir, revision, timeout=0.1))

    def test_live_companion_party_smoke_detects_joiner_group_membership(self) -> None:
        smoke = load_smoke()

        state = {
            "groupMembers": [
                {"name": "Dummy300", "account": "dummy300"},
                {"Name": "Dummy040", "Account": "dummy040"},
            ]
        }

        self.assertEqual(smoke.player_group_member_names(state), {"dummy300", "dummy040"})

        with mock.patch.object(smoke, "fetch_state", return_value=state):
            self.assertTrue(smoke.player_is_grouped_with(mock.Mock(), "dummy300", "Dummy040"))

    def test_live_companion_party_smoke_waits_until_joiner_is_grouped(self) -> None:
        smoke = load_smoke()
        args = mock.Mock()
        states = [
            {"groupMembers": [{"name": "Dummy300"}]},
            {"groupMembers": [{"name": "Dummy300"}, {"name": "Dummy040"}]},
        ]

        with mock.patch.object(smoke, "fetch_state", side_effect=states), mock.patch.object(smoke.time, "sleep"):
            self.assertTrue(smoke.wait_for_player_grouped_with(args, "dummy300", "Dummy040", timeout=1.0))

    def test_live_companion_party_smoke_reinvites_until_joiner_groups(self) -> None:
        smoke = load_smoke()
        args = mock.Mock(
            joiner_accept_attempts=3,
            leader_control_apply_timeout=0.5,
            joiner_invite_delay=0.1,
            joiner_accept_confirm_timeout=0.2,
        )
        leader_control = Path("leader-control.json")
        joiner_control = Path("joiner-control.json")
        write_calls: list[tuple[Path, dict[str, object]]] = []

        def fake_write(path: Path, payload: dict[str, object]) -> str:
            write_calls.append((path, payload))
            return f"rev-{len(write_calls)}"

        with mock.patch.object(smoke, "player_is_grouped_with", return_value=False), mock.patch.object(
            smoke,
            "wait_for_live_control_applied",
            return_value=True,
        ), mock.patch.object(
            smoke,
            "wait_for_player_grouped_with",
            side_effect=[False, True],
        ), mock.patch.object(
            smoke,
            "write_live_control",
            side_effect=fake_write,
        ), mock.patch.object(smoke.time, "sleep"):
            grouped = smoke.attempt_real_player_join(
                args,
                run_dir=Path("run"),
                leader_control_file=leader_control,
                joiner_control_file=joiner_control,
                joiner_account="dummy300",
                joiner_name="Dummy300",
                leader_name="Dummy040",
                leader_session_id=25,
            )

        self.assertTrue(grouped)
        leader_invites = [payload for path, payload in write_calls if path == leader_control]
        joiner_accepts = [payload for path, payload in write_calls if path == joiner_control]
        self.assertEqual(len(leader_invites), 2)
        self.assertEqual(len(joiner_accepts), 2)
        self.assertEqual(leader_invites[0]["commands"], ["/invite Dummy300"])
        self.assertEqual(joiner_accepts[0]["accept_group_invite_session_id"], 25)

    def test_live_companion_party_smoke_reports_failed_join_after_retries(self) -> None:
        smoke = load_smoke()
        args = mock.Mock(
            joiner_accept_attempts=2,
            leader_control_apply_timeout=0.5,
            joiner_invite_delay=0.1,
            joiner_accept_confirm_timeout=0.2,
        )

        with mock.patch.object(smoke, "player_is_grouped_with", return_value=False), mock.patch.object(
            smoke,
            "wait_for_live_control_applied",
            return_value=True,
        ), mock.patch.object(
            smoke,
            "wait_for_player_grouped_with",
            side_effect=[False, False],
        ), mock.patch.object(
            smoke,
            "write_live_control",
            return_value="rev",
        ) as write_live_control, mock.patch.object(smoke.time, "sleep"):
            grouped = smoke.attempt_real_player_join(
                args,
                run_dir=Path("run"),
                leader_control_file=Path("leader-control.json"),
                joiner_control_file=Path("joiner-control.json"),
                joiner_account="dummy300",
                joiner_name="Dummy300",
                leader_name="Dummy040",
                leader_session_id=25,
            )

        self.assertFalse(grouped)
        self.assertEqual(write_live_control.call_count, 4)

    def test_live_companion_party_smoke_rejects_replace_outside_test_output(self) -> None:
        smoke = load_smoke()

        with self.assertRaises(ValueError):
            smoke.validate_replace_run_dir(Path(ROOT))

    def test_live_companion_party_smoke_reads_leader_errors(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "leader").mkdir()
            (root / "leader" / "leader-metrics.csv").write_text(
                "username,error\nleader,safe_exit_deadline_reached\n",
                encoding="utf-8",
            )

            self.assertEqual(smoke.leader_errors(root), ["safe_exit_deadline_reached"])
            self.assertTrue(smoke.safe_exit_deadline_only(smoke.leader_errors(root)))

    def test_live_companion_party_smoke_reads_joiner_errors(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "joiner").mkdir()
            (root / "joiner" / "joiner-metrics.csv").write_text(
                "username,error\njoiner,safe_exit_deadline_reached\n",
                encoding="utf-8",
            )

            self.assertEqual(smoke.joiner_errors(root), ["safe_exit_deadline_reached"])
            self.assertTrue(smoke.safe_exit_deadline_only(smoke.joiner_errors(root)))

    def test_live_companion_party_smoke_reads_companion_errors(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "service" / "req").mkdir(parents=True)
            (root / "service" / "req" / "companion-metrics.csv").write_text(
                "username,error\ncompanion,name 'now' is not defined\n",
                encoding="utf-8",
            )

            self.assertEqual(smoke.companion_errors(root), ["name 'now' is not defined"])

    def test_live_companion_party_smoke_reports_missing_companion_metrics(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "service" / "req1").mkdir(parents=True)
            (root / "service" / "req2").mkdir(parents=True)
            (root / "service" / "req2" / "req2-metrics.csv").write_text(
                "username,error\ncompanion,\n",
                encoding="utf-8",
            )

            self.assertEqual(smoke.missing_companion_metrics(root, ["req1", "req2"]), ["req1: companion metrics missing"])

    def test_live_companion_party_smoke_accepts_companion_jsonl_when_metrics_are_missing(self) -> None:
        smoke = load_smoke()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "service" / "req1").mkdir(parents=True)
            (root / "service" / "req1" / "req1-encounters.jsonl").write_text(
                '{"event":"companion_chat_reply","intent":"chatter"}\n',
                encoding="utf-8",
            )

            self.assertEqual(smoke.missing_companion_metrics(root, ["req1"]), [])

    def test_live_companion_party_smoke_accepts_real_join_release_without_combat_activity(self) -> None:
        smoke = load_smoke()

        summary = {"damage_done": 0, "heal": 0, "party_assist": 0, "party_follow": 0}

        self.assertFalse(smoke.has_companion_activity(summary))
        self.assertTrue(smoke.release_completed({"req1": "completed"}))

    def test_live_companion_party_smoke_treats_companion_chat_as_activity(self) -> None:
        smoke = load_smoke()

        summary = {
            "damage_done": 0,
            "heal": 0,
            "party_assist": 0,
            "party_follow": 0,
            "companion_chat_reply": 1,
        }

        self.assertTrue(smoke.has_companion_activity(summary))

    def test_live_companion_party_smoke_treats_expected_role_actions_as_activity(self) -> None:
        smoke = load_smoke()

        for action in (
            "party_protection",
            "resurrect",
            "cure",
            "crowd_control",
            "speed_song",
            "stealth",
            "taunt",
            "target_rejected",
            "party_member_target_rejected",
        ):
            with self.subTest(action=action):
                summary = {
                    "damage_done": 0,
                    "heal": 0,
                    "party_assist": 0,
                    "party_follow": 0,
                    action: 1,
                }

                self.assertTrue(smoke.has_companion_activity(summary))

    def test_live_companion_party_smoke_exit_accepts_consumed_dialogue_live_control_when_applied(self) -> None:
        smoke = load_smoke()

        exit_code, notes = smoke.smoke_exit_code(
            active_statuses={"req1": "active"},
            release_statuses={},
            summary={
                "damage_done": 0,
                "heal": 0,
                "party_assist": 0,
                "party_follow": 0,
                "companion_chat_reply": 1,
                "death": 0,
                "dialogue_live_control": 0,
                "dialogue_live_control_applied": 1,
            },
            leader_errors=[],
            joiner_errors=[],
            leader_rc=0,
            service_rc=0,
            joiner_rc=0,
            real_player_join=False,
            dialogue_enabled=True,
            expected_actions={"companion_chat_reply"},
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("return_codes=leader:0,service:0,joiner:0", notes)

    def test_live_companion_party_smoke_exit_accepts_real_join_release_and_safe_joiner_exit(self) -> None:
        smoke = load_smoke()

        exit_code, notes = smoke.smoke_exit_code(
            active_statuses={"req1": "active"},
            release_statuses={"req1": "completed"},
            summary={
                "damage_done": 0,
                "heal": 0,
                "party_assist": 0,
                "party_follow": 0,
                "dialogue_live_control": 0,
                "dialogue_live_control_applied": 0,
            },
            leader_errors=[],
            joiner_errors=["safe_exit_deadline_reached"],
            leader_rc=0,
            service_rc=0,
            joiner_rc=1,
            real_player_join=True,
            dialogue_enabled=False,
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("joiner_safe_exit_warning=safe_exit_deadline_reached", notes)
        self.assertIn("return_codes=leader:0,service:0,joiner:0", notes)

    def test_live_companion_party_smoke_exit_accepts_real_join_without_release_when_companion_stays_active(self) -> None:
        smoke = load_smoke()

        exit_code, notes = smoke.smoke_exit_code(
            active_statuses={"req1": "active"},
            release_statuses={"req1": "active"},
            summary={
                "damage_done": 5,
                "heal": 1,
                "party_assist": 3,
                "party_follow": 7,
                "death": 0,
                "dialogue_live_control": 0,
                "dialogue_live_control_applied": 0,
            },
            leader_errors=[],
            joiner_errors=[],
            leader_rc=0,
            service_rc=0,
            joiner_rc=0,
            real_player_join=True,
            dialogue_enabled=False,
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("return_codes=leader:0,service:0,joiner:0", notes)

    def test_live_companion_party_smoke_exit_warns_on_leader_rc_after_expected_activity(self) -> None:
        smoke = load_smoke()

        exit_code, notes = smoke.smoke_exit_code(
            active_statuses={"req1": "active"},
            release_statuses={},
            summary={
                "damage_done": 0,
                "heal": 0,
                "party_assist": 0,
                "party_follow": 0,
                "party_protection": 2,
                "death": 0,
                "dialogue_live_control": 0,
                "dialogue_live_control_applied": 1,
            },
            leader_errors=[],
            joiner_errors=[],
            leader_rc=1,
            service_rc=0,
            joiner_rc=0,
            real_player_join=False,
            dialogue_enabled=False,
            expected_actions={"party_protection"},
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("leader_exit_warning=rc:1", notes)
        self.assertIn("return_codes=leader:0,service:0,joiner:0", notes)

    def test_live_companion_party_smoke_exit_requires_activity_without_real_join_release(self) -> None:
        smoke = load_smoke()

        exit_code, notes = smoke.smoke_exit_code(
            active_statuses={"req1": "active"},
            release_statuses={},
            summary={
                "damage_done": 0,
                "heal": 0,
                "party_assist": 0,
                "party_follow": 0,
                "dialogue_live_control": 0,
                "dialogue_live_control_applied": 0,
            },
            leader_errors=[],
            joiner_errors=[],
            leader_rc=0,
            service_rc=0,
            joiner_rc=0,
            real_player_join=False,
            dialogue_enabled=False,
        )

        self.assertEqual(exit_code, 3)
        self.assertEqual(notes, [])

    def test_live_companion_party_smoke_exit_fails_on_companion_death(self) -> None:
        smoke = load_smoke()

        exit_code, notes = smoke.smoke_exit_code(
            active_statuses={"req1": "active"},
            release_statuses={},
            summary={
                "damage_done": 1,
                "heal": 1,
                "party_assist": 0,
                "party_follow": 0,
                "death": 1,
                "dialogue_live_control": 0,
                "dialogue_live_control_applied": 0,
            },
            leader_errors=[],
            joiner_errors=[],
            leader_rc=0,
            service_rc=0,
            joiner_rc=0,
            real_player_join=False,
            dialogue_enabled=False,
        )

        self.assertEqual(exit_code, 8)
        self.assertIn("companion_death_detected=1", notes)

    def test_live_companion_party_smoke_exit_fails_on_leader_death(self) -> None:
        smoke = load_smoke()

        exit_code, notes = smoke.smoke_exit_code(
            active_statuses={"req1": "active"},
            release_statuses={},
            summary={
                "damage_done": 1,
                "heal": 1,
                "party_assist": 0,
                "party_follow": 0,
                "death": 0,
                "dialogue_live_control": 0,
                "dialogue_live_control_applied": 0,
            },
            leader_errors=[],
            joiner_errors=[],
            leader_rc=0,
            service_rc=0,
            joiner_rc=0,
            real_player_join=False,
            dialogue_enabled=False,
            leader_deaths=1,
        )

        self.assertEqual(exit_code, 10)
        self.assertIn("leader_death_detected=1", notes)

    def test_live_companion_party_smoke_exit_allows_configured_companion_death_when_resurrected(self) -> None:
        smoke = load_smoke()

        exit_code, notes = smoke.smoke_exit_code(
            active_statuses={"req1": "active"},
            release_statuses={},
            summary={
                "damage_done": 0,
                "heal": 0,
                "resurrect": 1,
                "cure": 0,
                "crowd_control": 0,
                "speed_song": 0,
                "stealth": 0,
                "party_assist": 0,
                "party_follow": 10,
                "death": 1,
                "dialogue_live_control": 0,
                "dialogue_live_control_applied": 0,
            },
            leader_errors=[],
            joiner_errors=[],
            leader_rc=0,
            service_rc=0,
            joiner_rc=0,
            real_player_join=False,
            dialogue_enabled=False,
            expected_actions={"resurrect"},
            allowed_companion_deaths=1,
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("return_codes=leader:0,service:0,joiner:0", notes)

    def test_live_companion_party_smoke_exit_allows_configured_joiner_death_when_resurrected(self) -> None:
        smoke = load_smoke()

        exit_code, notes = smoke.smoke_exit_code(
            active_statuses={"req1": "active"},
            release_statuses={"req1": "completed"},
            summary={
                "damage_done": 0,
                "heal": 0,
                "resurrect": 1,
                "cure": 0,
                "crowd_control": 0,
                "speed_song": 0,
                "stealth": 0,
                "party_assist": 0,
                "party_follow": 10,
                "death": 0,
                "dialogue_live_control": 0,
                "dialogue_live_control_applied": 0,
            },
            leader_errors=[],
            joiner_errors=[],
            leader_rc=0,
            service_rc=0,
            joiner_rc=0,
            real_player_join=True,
            dialogue_enabled=False,
            joiner_deaths=1,
            expected_actions={"resurrect"},
            allowed_joiner_deaths=1,
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("return_codes=leader:0,service:0,joiner:0", notes)

    def test_live_companion_party_smoke_exit_fails_on_companion_error(self) -> None:
        smoke = load_smoke()

        exit_code, notes = smoke.smoke_exit_code(
            active_statuses={"req1": "active"},
            release_statuses={"req1": "active"},
            summary={
                "damage_done": 1,
                "heal": 0,
                "party_assist": 0,
                "party_follow": 0,
                "death": 0,
                "dialogue_live_control": 0,
                "dialogue_live_control_applied": 0,
            },
            leader_errors=[],
            joiner_errors=[],
            leader_rc=0,
            service_rc=0,
            joiner_rc=0,
            real_player_join=False,
            dialogue_enabled=False,
            companion_errors=["name 'now' is not defined"],
        )

        self.assertEqual(exit_code, 9)
        self.assertTrue(any("name 'now' is not defined" in note for note in notes))

    def test_live_companion_party_smoke_exit_fails_when_expected_actions_are_missing(self) -> None:
        smoke = load_smoke()

        exit_code, notes = smoke.smoke_exit_code(
            active_statuses={"req1": "active"},
            release_statuses={},
            summary={
                "damage_done": 1,
                "heal": 0,
                "resurrect": 0,
                "cure": 0,
                "crowd_control": 0,
                "speed_song": 1,
                "stealth": 0,
                "party_assist": 0,
                "party_follow": 10,
                "death": 0,
                "dialogue_live_control": 0,
                "dialogue_live_control_applied": 0,
            },
            leader_errors=[],
            joiner_errors=[],
            leader_rc=0,
            service_rc=0,
            joiner_rc=0,
            real_player_join=False,
            dialogue_enabled=False,
            expected_actions={"speed_song", "stealth"},
        )

        self.assertEqual(exit_code, 12)
        self.assertTrue(any("missing_expected_actions=stealth" in note for note in notes))

    def test_live_companion_party_smoke_exit_accepts_present_expected_actions(self) -> None:
        smoke = load_smoke()

        exit_code, notes = smoke.smoke_exit_code(
            active_statuses={"req1": "active"},
            release_statuses={},
            summary={
                "damage_done": 0,
                "heal": 3,
                "resurrect": 0,
                "cure": 1,
                "crowd_control": 0,
                "speed_song": 0,
                "stealth": 0,
                "party_assist": 0,
                "party_follow": 10,
                "death": 0,
                "dialogue_live_control": 0,
                "dialogue_live_control_applied": 0,
            },
            leader_errors=[],
            joiner_errors=[],
            leader_rc=0,
            service_rc=0,
            joiner_rc=0,
            real_player_join=False,
            dialogue_enabled=False,
            expected_actions={"heal", "cure"},
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("return_codes=leader:0,service:0,joiner:0", notes)

    def test_live_companion_party_smoke_exit_keeps_service_failure_visible(self) -> None:
        smoke = load_smoke()

        exit_code, notes = smoke.smoke_exit_code(
            active_statuses={"req1": "active"},
            release_statuses={"req1": "completed"},
            summary={
                "damage_done": 0,
                "heal": 0,
                "party_assist": 0,
                "party_follow": 0,
                "dialogue_live_control": 0,
                "dialogue_live_control_applied": 0,
            },
            leader_errors=[],
            joiner_errors=["safe_exit_deadline_reached"],
            leader_rc=0,
            service_rc=7,
            joiner_rc=1,
            real_player_join=True,
            dialogue_enabled=False,
        )

        self.assertEqual(exit_code, 7)
        self.assertIn("return_codes=leader:0,service:7,joiner:0", notes)

    def test_live_companion_party_smoke_main_passes_allowed_death_thresholds_to_exit_evaluation(self) -> None:
        smoke = load_smoke()
        leader_process = mock.Mock()
        leader_process.wait.return_value = 0
        leader_process.poll.return_value = 0
        service_process = mock.Mock()
        service_process.wait.return_value = 0
        service_process.poll.return_value = 0

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            smoke.growth, "resolve_mysql_bin", return_value="mysql"
        ), mock.patch.object(
            smoke, "choose_leader_account", return_value="dummy040"
        ), mock.patch.object(
            smoke, "character_name_from_account", return_value="Dummy040"
        ), mock.patch.object(
            smoke, "build_leader_command", return_value=["leader"]
        ), mock.patch.object(
            smoke, "build_service_command", return_value=["service"]
        ), mock.patch.object(
            smoke.subprocess, "Popen", side_effect=[leader_process, service_process]
        ), mock.patch.object(
            smoke, "fail_if_existing_queued_requests"
        ), mock.patch.object(
            smoke, "wait_for_leader_online", return_value={"player": {"name": "Dummy040"}}
        ), mock.patch.object(
            smoke, "create_companion_request", return_value="req1"
        ), mock.patch.object(
            smoke, "wait_for_requests_active", return_value={"req1": "active"}
        ), mock.patch.object(
            smoke, "summarize_encounters",
            return_value={
                "damage_done": 0,
                "heal": 0,
                "resurrect": 1,
                "cure": 0,
                "crowd_control": 0,
                "speed_song": 0,
                "stealth": 0,
                "party_assist": 0,
                "party_follow": 10,
                "death": 1,
                "dialogue_live_control": 0,
                "dialogue_live_control_applied": 0,
            },
        ), mock.patch.object(
            smoke, "leader_errors", return_value=[]
        ), mock.patch.object(
            smoke, "companion_errors", return_value=[]
        ), mock.patch.object(
            smoke, "missing_companion_metrics", return_value=[]
        ), mock.patch.object(
            smoke, "joiner_errors", return_value=[]
        ), mock.patch.object(
            smoke, "death_count_in_subdir", return_value=1
        ), mock.patch.object(
            smoke,
            "smoke_exit_code",
            return_value=(
                0,
                ["return_codes=leader:0,service:0,joiner:0"],
            ),
        ) as smoke_exit_code:
            exit_code = smoke.main(
                [
                    "--skip-reset",
                    "--skip-gear",
                    "--run-dir",
                    temp_dir,
                    "--allow-companion-deaths",
                    "1",
                    "--allow-leader-deaths",
                    "2",
                    "--allow-joiner-deaths",
                    "3",
                    "--expect-companion-actions",
                    "res",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(smoke_exit_code.call_args.kwargs["allowed_companion_deaths"], 1)
        self.assertEqual(smoke_exit_code.call_args.kwargs["allowed_leader_deaths"], 2)
        self.assertEqual(smoke_exit_code.call_args.kwargs["allowed_joiner_deaths"], 3)

    def test_poll_active_stops_companion_when_requester_offline_grace_expires(self) -> None:
        service = load_service()
        args = mock.Mock()
        process = mock.Mock()
        process.poll.return_value = None
        active = {
            "req1": service.ActiveCompanion(
                {"id": "req1", "requesterAccount": "leader1", "offlineGraceSeconds": 1},
                process,
            )
        }
        active["req1"].requester_offline_since = service.time.monotonic() - 5.0

        with mock.patch.object(service, "fetch_requester_state", return_value=None), mock.patch.object(
            service, "stop_companion"
        ) as stop_companion, mock.patch.object(service, "update_request_status") as update_status:
            service.poll_active(args, active)

        stop_companion.assert_called_once_with(process, control_path=None)
        update_status.assert_called_once_with(
            args,
            "req1",
            "completed",
            "requester offline grace expired; companion stopped",
            close_reason="offline_grace_expired",
        )
        self.assertEqual(active, {})

    def test_poll_active_waits_for_requester_reconnect_during_offline_grace(self) -> None:
        service = load_service()
        args = mock.Mock(active_lease_refresh_interval=0.0)
        process = mock.Mock()
        process.poll.return_value = None
        active = {
            "req1": service.ActiveCompanion(
                {"id": "req1", "requesterAccount": "leader1", "offlineGraceSeconds": 60},
                process,
                account="albhealer",
            )
        }

        with mock.patch.object(service, "fetch_requester_state", return_value=None), mock.patch.object(
            service, "stop_companion"
        ) as stop_companion, mock.patch.object(service, "update_request_status") as update_status:
            service.poll_active(args, active)

        stop_companion.assert_not_called()
        self.assertIn("req1", active)
        self.assertGreater(active["req1"].requester_offline_since, 0.0)
        self.assertEqual(update_status.call_args_list[0].args[2], "active")
        self.assertIn("waiting 60 seconds for reconnect", update_status.call_args_list[0].args[3])

    def test_poll_active_requests_dialogue_for_low_health_requester(self) -> None:
        service = load_service()
        args = mock.Mock(dialogue_enabled=True, dialogue_min_interval=5.0, run_dir="runs")
        process = mock.Mock()
        process.poll.return_value = None
        active = {
            "req1": service.ActiveCompanion(
                {"id": "req1", "requesterAccount": "leader1", "requestedRole": "healer"},
                process,
                account="albhealer",
            )
        }
        state = {"player": {"healthPercent": 41, "inCombat": True, "isAlive": True, "isDead": False}}
        dialogue_state = {}

        with mock.patch.object(service, "fetch_requester_state", return_value=state), mock.patch.object(
            service, "request_companion_dialogue", return_value=True
        ) as request_dialogue:
            service.poll_active(args, active, release_counts={}, dialogue_state=dialogue_state)

        request_dialogue.assert_called_once()
        self.assertIn("req1:player_requested_heal", dialogue_state)
        self.assertEqual(request_dialogue.call_args.args[2], Path("runs") / "req1" / "live-control.json")

    def test_poll_active_refreshes_active_companion_lease(self) -> None:
        service = load_service()
        args = mock.Mock(active_lease_refresh_interval=0.0)
        process = mock.Mock()
        process.poll.return_value = None
        active = {
            "req1": service.ActiveCompanion(
                {"id": "req1", "requesterAccount": "leader1"},
                process,
                account="albhealer",
            )
        }
        active["req1"].last_lease_refresh = 0.0
        state = {"player": {"healthPercent": 100, "inCombat": False, "isAlive": True, "isDead": False}}

        with mock.patch.object(service, "fetch_requester_state", return_value=state), mock.patch.object(
            service, "update_request_status"
        ) as update_status:
            service.poll_active(args, active, release_counts={}, dialogue_state={})

        update_status.assert_called_once_with(args, "req1", "active", "live companion heartbeat", "albhealer")

    def test_completion_metrics_choose_resurrection_save_reason(self) -> None:
        service = load_service()
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "req1-metrics.csv").write_text(
                (
                    "username,target_removed,player_deaths,damage_done,healing_done,"
                    "action_validated_party_resurrect_member\n"
                    "albhealer,0,0,0,120,1\n"
                ),
                encoding="utf-8",
            )

            reason = service.live_companion_success_close_reason({"id": "req1"}, run_dir)

        self.assertEqual(reason, "resurrection_save")

    def test_completion_metrics_choose_boss_defeated_reason_for_objective_kill(self) -> None:
        service = load_service()
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "req1-metrics.csv").write_text(
                "username,target_removed,player_deaths,damage_done,healing_done\nalbdps,1,0,500,0\n",
                encoding="utf-8",
            )

            reason = service.live_companion_success_close_reason(
                {
                    "id": "req1",
                    "objectiveTarget": "Boss",
                    "encounterMode": "boss",
                },
                run_dir,
            )

        self.assertEqual(reason, "boss_defeated")

    def test_completion_metrics_count_crowd_control_event_log(self) -> None:
        service = load_service()
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "req1-albcc-1-encounters.jsonl").write_text(
                json.dumps({"event": "crowd_control_multi_aggro", "spell_type": "Mesmerize"}) + "\n",
                encoding="utf-8",
            )

            metrics = service.live_companion_completion_metrics(run_dir)
            reason = service.live_companion_success_close_reason({"id": "req1"}, run_dir)

        self.assertEqual(metrics["crowd_control"], 1)
        self.assertEqual(reason, "honorable_release")

    def test_live_companion_party_smoke_summary_deduplicates_request_artifacts(self) -> None:
        smoke = load_smoke()
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            request_dir = run_dir / "service" / "req1"
            request_dir.mkdir(parents=True)
            (request_dir / "req1-albcc-1-encounters.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"event": "crowd_control_multi_aggro", "spell_type": "Mesmerize"}),
                        json.dumps({"event": "death_detected"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (request_dir / "req1-metrics.csv").write_text(
                "username,damage_done,action_combat_damage_msg\nalbcc,10,1\n",
                encoding="utf-8",
            )
            (request_dir / "live-control.json").write_text(
                json.dumps({"say_channel": "party", "intent_hint": "cc_add"}),
                encoding="utf-8",
            )

            summary = smoke.summarize_encounters(run_dir, ["req1"])

        self.assertEqual(summary["crowd_control"], 1)
        self.assertEqual(summary["death"], 1)
        self.assertEqual(summary["damage_done"], 10)
        self.assertEqual(summary["dialogue_live_control"], 1)

    def test_poll_active_completed_process_reports_metrics_close_reason(self) -> None:
        service = load_service()
        with tempfile.TemporaryDirectory() as temp_dir:
            request_dir = Path(temp_dir) / "req1"
            request_dir.mkdir()
            (request_dir / "req1-metrics.csv").write_text(
                (
                    "username,target_removed,player_deaths,damage_done,healing_done,"
                    "action_validated_party_resurrect_member\n"
                    "albhealer,0,0,0,120,1\n"
                ),
                encoding="utf-8",
            )
            args = mock.Mock(run_dir=temp_dir, account_reuse_cooldown=0.0)
            process = mock.Mock()
            process.poll.return_value = 0
            active = {
                "req1": service.ActiveCompanion(
                    {"id": "req1", "requesterAccount": "leader1", "requestedRole": "healer"},
                    process,
                    account="albhealer",
                )
            }

            with mock.patch.object(service, "update_request_status") as update_status:
                service.poll_active(args, active, release_counts={}, dialogue_state={})

        update_status.assert_called_once_with(
            args,
            "req1",
            "completed",
            "behavior client exited with 0",
            close_reason="resurrection_save",
        )
        self.assertEqual(active, {})

    def test_poll_active_keeps_companion_when_real_player_joins_with_vacant_slots(self) -> None:
        service = load_service()
        args = mock.Mock(active_lease_refresh_interval=0.0)
        process = mock.Mock()
        process.poll.return_value = None
        active = {
            "req1": service.ActiveCompanion(
                {"id": "req1", "requesterAccount": "leader1", "requestedRole": "dps"},
                process,
                account="albdps",
            )
        }
        active["req1"].last_lease_refresh = 0.0
        state = {
            "player": {"name": "Leader", "isAlive": True, "isDead": False},
            "groupMembers": [
                {"name": "Leader", "account": "leader1"},
                {"name": "RealPlayer", "account": "real1"},
                {"name": "AlbDps", "account": "albdps", "isCompanion": True},
            ],
        }
        release_counts = {}

        with mock.patch.object(service, "fetch_requester_state", return_value=state), mock.patch.object(
            service, "detach_companion_from_request", return_value=(True, "")
        ) as detach, mock.patch.object(service, "stop_companion") as stop_companion, mock.patch.object(
            service, "update_request_status"
        ) as update_status:
            service.poll_active(args, active, release_counts)

        detach.assert_not_called()
        stop_companion.assert_not_called()
        update_status.assert_called_once_with(args, "req1", "active", "live companion heartbeat", "albdps")
        self.assertIn("req1", active)
        self.assertEqual(release_counts, {})

    def test_poll_active_keeps_companion_when_full_party_real_player_joins(self) -> None:
        service = load_service()
        args = mock.Mock(active_lease_refresh_interval=0.0)
        process = mock.Mock()
        process.poll.return_value = None
        active = {
            "req1": service.ActiveCompanion(
                {"id": "req1", "requesterAccount": "leader1", "requestedRole": "dps"},
                process,
                account="albdps",
            )
        }
        state = {
            "player": {"name": "Leader", "isAlive": True, "isDead": False},
            "groupMembers": [
                {"name": "Leader", "account": "leader1"},
                {"name": "RealPlayer1", "account": "real1"},
                {"name": "RealPlayer2", "account": "real2"},
                {"name": "RealPlayer3", "account": "real3"},
                {"name": "RealPlayer4", "account": "real4"},
                {"name": "RealPlayer5", "account": "real5"},
                {"name": "RealPlayer6", "account": "real6"},
                {"name": "AlbDps", "account": "albdps", "isCompanion": True},
            ],
        }
        release_counts = {}

        with mock.patch.object(service, "fetch_requester_state", return_value=state), mock.patch.object(
            service, "detach_companion_from_request", return_value=(True, "")
        ) as detach, mock.patch.object(service, "stop_companion") as stop_companion, mock.patch.object(
            service, "update_request_status"
        ) as update_status:
            service.poll_active(args, active, release_counts)

        detach.assert_not_called()
        stop_companion.assert_not_called()
        for call in update_status.mock_calls:
            self.assertNotIn("real player joined; companion released", str(call))
        self.assertIn("req1", active)
        self.assertEqual(release_counts, {})

    def test_poll_active_stops_companion_when_group_membership_is_lost(self) -> None:
        service = load_service()
        args = mock.Mock()
        process = mock.Mock()
        process.poll.return_value = None
        active = {
            "req1": service.ActiveCompanion(
                {"id": "req1", "requesterAccount": "leader1", "requestedRole": "healer"},
                process,
                account="albhealer",
            )
        }
        state = {
            "player": {"name": "Leader", "isAlive": True, "isDead": False},
            "groupMembers": [{"name": "Leader", "account": "leader1"}],
        }

        with mock.patch.object(service, "fetch_requester_state", return_value=state), mock.patch.object(
            service, "detach_companion_from_request", return_value=(True, "")
        ) as detach, mock.patch.object(service, "stop_companion") as stop_companion, mock.patch.object(
            service, "update_request_status"
        ) as update_status:
            service.poll_active(args, active, release_counts={}, dialogue_state={})

        detach.assert_called_once_with(args, "req1", "albhealer")
        stop_companion.assert_called_once_with(process, control_path=None)
        update_status.assert_called_once_with(
            args,
            "req1",
            "completed",
            "party disbanded or companion removed; companion released",
            "albhealer",
            close_reason="party_lost",
        )
        self.assertEqual(active, {})

    def test_poll_active_stops_companion_when_request_is_canceled_externally(self) -> None:
        service = load_service()
        args = mock.Mock()
        process = mock.Mock()
        process.poll.return_value = None
        active = {
            "req1": service.ActiveCompanion(
                {"id": "req1", "requesterAccount": "leader1", "requestedRole": "dps"},
                process,
                account="albdps",
            )
        }

        with mock.patch.object(service, "current_request_status", return_value="canceled"), mock.patch.object(
            service, "fetch_requester_state"
        ) as fetch_state, mock.patch.object(service, "detach_companion_from_request", return_value=(True, "")) as detach, mock.patch.object(
            service, "stop_companion"
        ) as stop_companion, mock.patch.object(service, "update_request_status") as update_status:
            service.poll_active(args, active, release_counts={}, dialogue_state={})

        fetch_state.assert_not_called()
        detach.assert_called_once_with(args, "req1", "albdps")
        stop_companion.assert_called_once_with(process, control_path=None)
        update_status.assert_not_called()
        self.assertEqual(active, {})

    def test_poll_active_throttles_active_request_status_checks(self) -> None:
        service = load_service()
        args = mock.Mock(active_request_status_interval=30.0, active_lease_refresh_interval=30.0)
        process = mock.Mock()
        process.poll.return_value = None
        companion = service.ActiveCompanion(
            {"id": "req1", "requesterAccount": "leader1", "requestedRole": "healer"},
            process,
            account="albhealer",
        )
        active = {"req1": companion}
        state = {"player": {"name": "Leader", "isAlive": True, "isDead": False}}

        with mock.patch.object(service.time, "monotonic", return_value=100.0), mock.patch.object(
            service, "current_request_status", return_value=""
        ) as status, mock.patch.object(service, "fetch_requester_state", return_value=state), mock.patch.object(
            service, "choose_release_request_for_real_player_join", return_value=""
        ), mock.patch.object(
            service, "choose_release_request_for_missing_group_companion", return_value=""
        ):
            service.poll_active(args, active, release_counts={}, dialogue_state={})

        self.assertEqual(status.call_count, 1)
        self.assertEqual(companion.last_request_status_check, 100.0)

        with mock.patch.object(service.time, "monotonic", return_value=110.0), mock.patch.object(
            service, "current_request_status", return_value=""
        ) as status, mock.patch.object(service, "fetch_requester_state", return_value=state), mock.patch.object(
            service, "choose_release_request_for_real_player_join", return_value=""
        ), mock.patch.object(
            service, "choose_release_request_for_missing_group_companion", return_value=""
        ):
            service.poll_active(args, active, release_counts={}, dialogue_state={})

        status.assert_not_called()
        self.assertEqual(companion.last_request_status_check, 100.0)

    def test_poll_active_can_disable_active_request_status_throttle(self) -> None:
        service = load_service()
        args = mock.Mock(active_request_status_interval=0.0, active_lease_refresh_interval=30.0)
        process = mock.Mock()
        process.poll.return_value = None
        companion = service.ActiveCompanion(
            {"id": "req1", "requesterAccount": "leader1", "requestedRole": "healer"},
            process,
            account="albhealer",
        )
        companion.last_request_status_check = 100.0
        active = {"req1": companion}
        state = {"player": {"name": "Leader", "isAlive": True, "isDead": False}}

        with mock.patch.object(service.time, "monotonic", return_value=110.0), mock.patch.object(
            service, "current_request_status", return_value=""
        ) as status, mock.patch.object(service, "fetch_requester_state", return_value=state), mock.patch.object(
            service, "choose_release_request_for_real_player_join", return_value=""
        ), mock.patch.object(
            service, "choose_release_request_for_missing_group_companion", return_value=""
        ):
            service.poll_active(args, active, release_counts={}, dialogue_state={})

        status.assert_called_once_with(args, "req1")
        self.assertEqual(companion.last_request_status_check, 110.0)


class DummyCompanionServerSurfaceTests(unittest.TestCase):
    def test_gm_dummy_command_is_gm_only_and_not_player_command(self) -> None:
        command_path = ROOT / "GameServer" / "commands" / "gmcommands" / "dummy.cs"
        source = command_path.read_text(encoding="utf-8")

        self.assertIn('[CmdAttribute("&dummy"', source)
        self.assertIn("ePrivLevel.GM", source)
        self.assertIn("CompanionRequestService.CreateRequest", source)
        self.assertIn("CompanionRequestService.RequestLeave", source)
        self.assertFalse((ROOT / "GameServer" / "commands" / "playercommands" / "dummy.cs").exists())

    def test_hire_npc_uses_player_facing_companion_language(self) -> None:
        npc_path = ROOT / "GameServer" / "scripts" / "customnpc" / "CompanionHireNpc.cs"
        source = npc_path.read_text(encoding="utf-8")

        self.assertIn("용병 고용관", source)
        self.assertNotIn("[파티 용병]", source)
        self.assertNotIn('case "파티 용병":', source)
        self.assertIn("고용: [추천 고용] [치유형 고용] [방어형 고용] [공격형 고용] [지원형 고용]", source)
        self.assertIn("관리: [용병 상세] [용병 일지] [휴식] [상태 확인] [소문] [요청 취소] [용병 해산]", source)
        self.assertIn('case "추천 고용":', source)
        self.assertIn('case "치유형 고용":', source)
        self.assertIn('case "방어형 고용":', source)
        self.assertIn('case "공격형 고용":', source)
        self.assertIn('case "지원형 고용":', source)
        self.assertIn('case "상태 확인":', source)
        self.assertIn("치유 용병", source)
        self.assertIn("방어 용병", source)
        self.assertIn("공격 용병", source)
        self.assertIn("용병 상태", source)
        self.assertIn("용병 요청 취소", source)
        self.assertIn("용병 해산", source)
        self.assertIn("ShowStatus", source)
        self.assertIn("CancelPending", source)
        self.assertIn("LatestForPlayer(player.Name)", source)
        self.assertIn("[GameServerStartedEvent]", source)
        self.assertIn("WorldMgr.GetAllRegions()", source)
        self.assertIn(".OfType<LiveTeleporter>()", source)
        self.assertIn("ComputeHireNpcPlacement(teleporter)", source)
        self.assertIn("PackageIdForTeleporter(teleporter)", source)
        self.assertIn("TeleporterSideOffset", source)
        self.assertNotIn("531504, 479073", source)
        self.assertNotIn("774601, 755307", source)
        self.assertNotIn("345677, 490738", source)
        self.assertIn('private const string CompanionHireNpcName = "용병 고용관";', source)
        self.assertIn("existing.Name = CompanionHireNpcName;", source)
        self.assertIn("ApplyPlacement(existing, placement, region, packageId);", source)
        self.assertIn("npc.MoveTo(placement.Region, placement.X, placement.Y, placement.Z, placement.Heading);", source)
        self.assertNotIn("더미", source)
        self.assertNotIn("����", source)
        self.assertNotIn("?숇즺", source)
        self.assertNotIn("媛숈", source)

    def test_companion_server_messages_are_readable_korean(self) -> None:
        service_source = (ROOT / "GameServer" / "LiveCompanion" / "CompanionRequestService.cs").read_text(
            encoding="utf-8"
        )
        routes_source = (ROOT / "GameServer" / "API" / "DummyCompanion" / "DummyCompanionRoutes.cs").read_text(
            encoding="utf-8"
        )
        combined = service_source + routes_source

        self.assertIn("용병 요청이 접수되었습니다.", combined)
        self.assertIn("용병 해산 요청이 접수되었습니다.", combined)
        self.assertIn("용병 서비스가 요청을 처리 중입니다.", combined)
        self.assertIn("용병이 파티에 합류했습니다.", combined)
        self.assertNotIn("����", combined)
        self.assertNotIn("?숇즺", combined)
        self.assertNotIn("?붿껌", combined)
        self.assertNotIn("媛숈", combined)

    def test_companion_request_summary_api_is_registered(self) -> None:
        service_source = (ROOT / "GameServer" / "LiveCompanion" / "CompanionRequestService.cs").read_text(
            encoding="utf-8"
        )
        routes_source = (ROOT / "GameServer" / "API" / "DummyCompanion" / "DummyCompanionRoutes.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn("CompanionRequestSummary", service_source)
        self.assertIn("StatusCounts", service_source)
        self.assertIn("ActiveRequests", service_source)
        self.assertIn("CompanionRequestService.Summary", routes_source)
        self.assertIn('/api/dummy/companions/summary', routes_source)

    def test_companion_request_api_is_registered(self) -> None:
        routes = (ROOT / "GameServer" / "API" / "DummyCompanion" / "DummyCompanionRoutes.cs").read_text(
            encoding="utf-8"
        )
        host = (ROOT / "GameServer" / "API" / "ApiHost.cs").read_text(encoding="utf-8")
        combat_routes = (ROOT / "GameServer" / "API" / "DummyCombat" / "DummyCombatRoutes.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn('/api/dummy/companions/requests', routes)
        self.assertIn("ClaimNextQueued", routes)
        self.assertIn('/api/dummy/companions/requests/{id}/attach', routes)
        self.assertIn('/api/dummy/companions/requests/{id}/detach', routes)
        self.assertIn("AttachCompanion", routes)
        self.assertIn("RequireMutationAllowed", routes)
        self.assertIn("VerifyAPIPassword", routes)
        self.assertIn("IPAddress.IsLoopback", routes)
        self.assertIn("CompanionRequestStatus.Leaving", routes + (ROOT / "GameServer" / "LiveCompanion" / "CompanionRequestService.cs").read_text(encoding="utf-8"))
        self.assertIn("UpdateStatus", routes)
        self.assertIn("sessionId", combat_routes)
        self.assertIn("isCompanion", combat_routes)
        self.assertIn("companionRole", combat_routes)
        self.assertIn("ActiveCompanionRoleFor", combat_routes)
        self.assertIn("MapDummyCompanionRoutes", host)

    def test_companion_request_api_preserves_objective_location_override(self) -> None:
        routes = (ROOT / "GameServer" / "API" / "DummyCompanion" / "DummyCompanionRoutes.cs").read_text(
            encoding="utf-8"
        )
        service_source = (ROOT / "GameServer" / "LiveCompanion" / "CompanionRequestService.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn('ParseUShort(Query(context, "region"), 0)', routes)
        self.assertIn('ParseInt(Query(context, "x"), 0)', routes)
        self.assertIn('ParseInt(Query(context, "y"), 0)', routes)
        self.assertIn('ParseInt(Query(context, "z"), 0)', routes)
        self.assertIn("ushort objectiveRegion = 0", service_source)
        self.assertIn("bool hasObjectiveLocation = objectiveX != 0 || objectiveY != 0 || objectiveZ != 0", service_source)
        self.assertIn("Region = hasObjectiveLocation ? requestRegion : requester.CurrentRegionID", service_source)
        self.assertIn("X = hasObjectiveLocation ? objectiveX : requester.X", service_source)
        self.assertIn("Y = hasObjectiveLocation ? objectiveY : requester.Y", service_source)
        self.assertIn("Z = hasObjectiveLocation ? objectiveZ : requester.Z", service_source)

    def test_companion_request_api_preserves_requested_capabilities(self) -> None:
        routes = (ROOT / "GameServer" / "API" / "DummyCompanion" / "DummyCompanionRoutes.cs").read_text(
            encoding="utf-8"
        )
        service_source = (ROOT / "GameServer" / "LiveCompanion" / "CompanionRequestService.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn("public string RequestedCapabilities", service_source)
        self.assertIn('Query(context, "requestedCapabilities"', routes)
        self.assertIn('Query(context, "capabilities"', routes)
        self.assertIn('Query(context, "capability"', routes)
        self.assertIn("RequestedCapabilities = string.IsNullOrWhiteSpace(requestedCapabilities)", service_source)
        self.assertIn("RequestedCapabilities = request.RequestedCapabilities", service_source)

    def test_companion_request_tracks_contract_tier_duration_and_offline_grace(self) -> None:
        routes = (ROOT / "GameServer" / "API" / "DummyCompanion" / "DummyCompanionRoutes.cs").read_text(
            encoding="utf-8"
        )
        service_source = (ROOT / "GameServer" / "LiveCompanion" / "CompanionRequestService.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn("public static class CompanionContractTiers", service_source)
        self.assertIn("public string ContractTier", service_source)
        self.assertIn("public int ContractDurationSeconds", service_source)
        self.assertIn("public int OfflineGraceSeconds", service_source)
        self.assertIn("public DateTime ContractStartedUtc", service_source)
        self.assertIn('Query(context, "contractTier", Query(context, "tier"))', routes)
        self.assertIn("ContractTier = request.ContractTier", service_source)
        self.assertIn("ContractDurationSeconds = request.ContractDurationSeconds", service_source)
        self.assertIn("OfflineGraceSeconds = request.OfflineGraceSeconds", service_source)
        self.assertIn("companion contract time expired", service_source)

    def test_owned_mercenary_surface_exists_for_hire_npc_and_requests(self) -> None:
        table_source = (ROOT / "CoreDatabase" / "Tables" / "DbPlayerMercenary.cs").read_text(encoding="utf-8")
        service_source = (ROOT / "GameServer" / "LiveCompanion" / "PlayerMercenaryService.cs").read_text(
            encoding="utf-8"
        )
        request_source = (ROOT / "GameServer" / "LiveCompanion" / "CompanionRequestService.cs").read_text(
            encoding="utf-8"
        )
        hire_npc_source = (ROOT / "GameServer" / "scripts" / "customnpc" / "CompanionHireNpc.cs").read_text(
            encoding="utf-8"
        )
        routes = (ROOT / "GameServer" / "API" / "DummyCompanion" / "DummyCompanionRoutes.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn('[DataTable(TableName = "player_mercenary")]', table_source)
        self.assertIn("public string MercenaryId", table_source)
        self.assertIn("public string OwnerCharacterId", table_source)
        self.assertIn("public string Background", table_source)
        self.assertIn("public string Personality", table_source)
        self.assertIn("public string ItemProfile", table_source)
        self.assertIn("EnsureStarterMercenary", service_source)
        self.assertIn("GrantRandom", service_source)
        self.assertIn("OwnedBy", service_source)
        self.assertIn("CreateOwnedMercenaryRequest", request_source)
        self.assertIn("public string MercenaryId", request_source)
        self.assertIn("public string MercenaryClassName", request_source)
        self.assertIn("public string MercenaryPersonality", request_source)
        self.assertIn('Query(context, "mercenaryId"', routes)
        self.assertIn("내 용병", hire_npc_source)
        self.assertIn("PlayerMercenaryService.EnsureStarterMercenary", hire_npc_source)

    def test_owned_mercenary_progression_fields_surface_to_requests_and_hire_npc(self) -> None:
        table_source = (ROOT / "CoreDatabase" / "Tables" / "DbPlayerMercenary.cs").read_text(encoding="utf-8")
        service_source = (ROOT / "GameServer" / "LiveCompanion" / "PlayerMercenaryService.cs").read_text(
            encoding="utf-8"
        )
        request_source = (ROOT / "GameServer" / "LiveCompanion" / "CompanionRequestService.cs").read_text(
            encoding="utf-8"
        )
        routes = (ROOT / "GameServer" / "API" / "DummyCompanion" / "DummyCompanionRoutes.cs").read_text(
            encoding="utf-8"
        )
        hire_npc_source = (ROOT / "GameServer" / "scripts" / "customnpc" / "CompanionHireNpc.cs").read_text(
            encoding="utf-8"
        )

        for field in (
            "TacticPreset",
            "Trust",
            "Fatigue",
            "AdventureMemory",
            "RumorHint",
            "TotalContracts",
            "TotalContractMinutes",
            "KillsTogether",
            "DeathsTogether",
            "RevivesReceived",
            "Rescues",
            "QuestsCompleted",
            "EarnedTitles",
            "PersonalQuestState",
            "RelationshipEventState",
            "LastHiredAt",
        ):
            self.assertIn(field, table_source)
            self.assertIn(f"Mercenary{field}", request_source)

        self.assertIn("RecordContractStarted", service_source)
        self.assertIn("RecordContractCompleted", service_source)
        self.assertIn("RecordContractFailed", service_source)
        self.assertIn("TrustGainForCompletedReason", service_source)
        self.assertIn("TrustStageLabel", service_source)
        self.assertIn("ApplyMercenaryContractOutcome", request_source)
        self.assertIn("IsPlayerAccountableMercenaryFailure", request_source)
        self.assertIn("request.CloseReason", request_source)
        self.assertIn("string closeReason = \"\"", request_source)
        self.assertIn('Query(context, "closeReason", Query(context, "reason"))', routes)
        live_service_source = (ROOT / "tools" / "dummy-companion-service.py").read_text(encoding="utf-8")
        self.assertIn("close_reason", live_service_source)
        self.assertIn("real_player_joined", live_service_source)
        self.assertIn("system_attach_failed", live_service_source)
        self.assertIn("mercenary_death", request_source)
        self.assertIn("companion active lease expired", request_source)
        self.assertIn("RefreshTitlesAndPersonalQuest", service_source)
        self.assertIn("BuildMercenaryProgressLine", request_source)
        self.assertIn("request_mercenary_record", live_service_source)
        self.assertIn("--mercenary-earned-titles", live_service_source)
        self.assertIn("ShowMercenaryRumors", hire_npc_source)
        self.assertIn("[소문]", hire_npc_source)
        self.assertIn("친밀도 {row.Trust}", hire_npc_source)
        self.assertIn("RecordSummary", hire_npc_source)
        self.assertIn("PersonalQuestLine", hire_npc_source)

    def test_owned_mercenary_detail_and_rest_controls_exist_on_hire_npc(self) -> None:
        service_source = (ROOT / "GameServer" / "LiveCompanion" / "PlayerMercenaryService.cs").read_text(
            encoding="utf-8"
        )
        hire_npc_source = (ROOT / "GameServer" / "scripts" / "customnpc" / "CompanionHireNpc.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn("RestMercenary", service_source)
        self.assertIn("RestAll", service_source)
        self.assertIn("mercenary.Fatigue", service_source)
        self.assertIn("[용병 상세]", hire_npc_source)
        self.assertIn("[휴식]", hire_npc_source)
        self.assertIn("ShowMercenaryDetails", hire_npc_source)
        self.assertIn("TryShowMercenaryDetails", hire_npc_source)
        self.assertIn("TryRestMercenary", hire_npc_source)
        self.assertIn("ExtractMercenaryCommandSubject", hire_npc_source)
        self.assertIn("[{row.DisplayName} 상세]", hire_npc_source)
        self.assertIn("[{row.DisplayName} 휴식]", hire_npc_source)
        self.assertIn("이름만 누르면 고용합니다", hire_npc_source)
        self.assertIn("보유 용병 상세입니다", hire_npc_source)

    def test_combat_usable_spellinfo_exposes_role_capability_tags(self) -> None:
        combat_routes = (ROOT / "GameServer" / "API" / "DummyCombat" / "DummyCombatRoutes.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn("damageType = spell.DamageType.ToString()", combat_routes)
        self.assertIn("frequency = spell.Frequency", combat_routes)
        self.assertIn("pulse = spell.Pulse", combat_routes)
        self.assertIn("uninterruptible = spell.Uninterruptible", combat_routes)
        self.assertIn("instrumentRequirement = spell.InstrumentRequirement", combat_routes)
        self.assertIn("capabilityTags = SpellCapabilityTags(spell)", combat_routes)
        self.assertIn('"speedSong"', combat_routes)
        self.assertIn('"stealth"', combat_routes)
        self.assertIn('"resurrection"', combat_routes)
        self.assertIn('"cureDisease"', combat_routes)
        self.assertIn('"pet"', combat_routes)
        self.assertIn('"summon"', combat_routes)
        self.assertIn('"charm"', combat_routes)
        self.assertIn('"bladeturn"', combat_routes)
        self.assertIn('"lifedrain"', combat_routes)
        self.assertIn('"disease"', combat_routes)
        self.assertIn("case eSpellType.Pet:", combat_routes)
        self.assertNotIn('spellTypeKey.Contains("summon") || spellTypeKey.Contains("pet")', combat_routes)

    def test_companion_attach_requires_preassigned_companion_identity(self) -> None:
        routes = (ROOT / "GameServer" / "API" / "DummyCompanion" / "DummyCompanionRoutes.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn("AttachCompanionMatchesRequest", routes)
        self.assertIn("AssignedCompanionName", routes)
        self.assertIn("UnexpectedCompanion", routes)

    def test_companion_attach_requires_grouping_request_status(self) -> None:
        routes = (ROOT / "GameServer" / "API" / "DummyCompanion" / "DummyCompanionRoutes.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn("RequireAttachableRequest(request)", routes)
        self.assertIn("RequestNotAttachable", routes)
        self.assertIn("CompanionRequestStatus.Grouping", routes)

    def test_companion_request_read_api_is_protected(self) -> None:
        routes = (ROOT / "GameServer" / "API" / "DummyCompanion" / "DummyCompanionRoutes.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn('api.MapGet("/api/dummy/companions/requests", (HttpContext context)', routes)
        self.assertIn('api.MapGet("/api/dummy/companions/requests/{id}", (HttpContext context, string id)', routes)
        self.assertIn('api.MapGet("/api/dummy/companions/players/{playerName}/latest", (HttpContext context, string playerName)', routes)
        self.assertIn('api.MapPost("/api/dummy/companions/test/damage", (HttpContext context)', routes)
        self.assertIn("healthPercent", routes)
        self.assertGreaterEqual(routes.count("RequireMutationAllowed(context)"), 10)

    def test_companion_request_service_counts_pending_requests_against_party_slots(self) -> None:
        source = (ROOT / "GameServer" / "LiveCompanion" / "CompanionRequestService.cs").read_text(encoding="utf-8")

        self.assertIn("SlotHoldingStatuses", source)
        self.assertIn("OpenRequestCountForRequesterLocked", source)
        self.assertIn("availableSlots = Math.Max(0, vacantSlots - reservedSlots)", source)
        self.assertIn("AddRequestLocked(request)", source)

    def test_companion_request_service_expires_stale_open_requests(self) -> None:
        source = (ROOT / "GameServer" / "LiveCompanion" / "CompanionRequestService.cs").read_text(encoding="utf-8")

        self.assertIn("StaleOpenRequestTimeout", source)
        self.assertIn("ExpireStaleOpenRequestsLocked", source)
        self.assertIn("CompanionRequestStatus.Failed", source)
        self.assertIn("Snapshot(string status", source)
        self.assertIn("ClaimNextQueued()", source)

    def test_companion_request_service_rejects_terminal_status_reactivation(self) -> None:
        source = (ROOT / "GameServer" / "LiveCompanion" / "CompanionRequestService.cs").read_text(encoding="utf-8")

        self.assertIn("TerminalStatuses", source)
        self.assertIn("CanTransitionStatus", source)
        self.assertIn("if (!CanTransitionStatus(request.Status, normalizedStatus))", source)

    def test_companion_request_cancel_api_releases_pending_slot(self) -> None:
        service_source = (ROOT / "GameServer" / "LiveCompanion" / "CompanionRequestService.cs").read_text(
            encoding="utf-8"
        )
        routes_source = (ROOT / "GameServer" / "API" / "DummyCompanion" / "DummyCompanionRoutes.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn("public const string Canceled", service_source)
        self.assertIn("CancelPendingRequests", service_source)
        self.assertIn("request.Status = CompanionRequestStatus.Canceled", service_source)
        self.assertIn("CancelableStatuses", service_source)
        self.assertIn("SlotHoldingStatuses.Contains(request.Status)", service_source)
        self.assertIn('/api/dummy/companions/requests/{id}/cancel', routes_source)
        self.assertIn("CompanionRequestService.CancelRequest", routes_source)

    def test_active_companion_lease_is_refreshed_and_expires_when_service_stops(self) -> None:
        server_source = (ROOT / "GameServer" / "LiveCompanion" / "CompanionRequestService.cs").read_text(encoding="utf-8")
        service_source = (ROOT / "tools" / "dummy-companion-service.py").read_text(encoding="utf-8")

        self.assertIn("ActiveCompanionLeaseTimeout", server_source)
        self.assertIn("CompanionRequestStatus.Active", server_source)
        self.assertIn("ExpireStaleOpenRequestsLocked(DateTime.UtcNow);", server_source)
        self.assertIn("refresh_active_companion_lease", service_source)
        self.assertIn("active_lease_refresh_interval", service_source)

    def test_active_companion_rewards_are_suppressed_server_side(self) -> None:
        source = (ROOT / "GameServer" / "gameobjects" / "GamePlayer.cs").read_text(encoding="utf-8")

        self.assertIn("using DOL.GS.LiveCompanion;", source)
        self.assertIn("SuppressLiveCompanionReward", source)
        self.assertIn("RecordSuppressedReward", source)
        self.assertIn("CompanionRequestService.IsActiveCompanion(Name)", source)
        self.assertLess(source.index("SuppressLiveCompanionReward"), source.index("RealmPoints += amount;"))
        self.assertLess(source.index("SuppressLiveCompanionReward"), source.index("BountyPoints += amount;"))
        self.assertLess(source.index("SuppressLiveCompanionReward"), source.index("AddMoney(money, messageFormat, ct, cl);"))

    def test_active_companion_rvr_kill_credit_is_suppressed_before_award_stats(self) -> None:
        source = (ROOT / "GameServer" / "serverrules" / "AbstractServerRules.cs").read_text(encoding="utf-8")

        self.assertIn("using DOL.GS.LiveCompanion;", source)
        self.assertIn("CompanionRequestService.IsActiveCompanion(player.Name)", source)
        self.assertIn("UpdateKillStatsOnPlayerKill", source)
        gate_index = source.index("CompanionRequestService.IsActiveCompanion(player.Name)")
        self.assertLess(
            gate_index,
            source.index("ProcessDamage(player, pair.Value, player, mostDamagingPlayer, playerCountAndDamage);", gate_index),
        )

    def test_combat_usable_marks_target_relation_for_companion_policy(self) -> None:
        source = (ROOT / "GameServer" / "API" / "DummyCombat" / "DummyCombatRoutes.cs").read_text(encoding="utf-8")

        self.assertIn("targetCanAttack = TargetCanAttack(player, player.TargetObject)", source)
        self.assertIn("targetRelation = TargetRelationFor(player, player.TargetObject)", source)
        self.assertIn("GameServer.ServerRules.IsAllowedToAttack(player, livingTarget, true)", source)
        self.assertIn('return "party";', source)
        self.assertIn('return "same_realm";', source)
        self.assertIn('return TargetCanAttack(player, target) ? "enemy" : "blocked";', source)


if __name__ == "__main__":
    unittest.main()
