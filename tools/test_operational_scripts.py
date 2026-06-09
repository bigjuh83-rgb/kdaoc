import unittest
import csv
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]

PROVISION_SPEC = importlib.util.spec_from_file_location(
    "provision_dummy_accounts",
    ROOT / "tools" / "provision-dummy-accounts.py",
)
assert PROVISION_SPEC is not None and PROVISION_SPEC.loader is not None
provision_dummy_accounts = importlib.util.module_from_spec(PROVISION_SPEC)
PROVISION_SPEC.loader.exec_module(provision_dummy_accounts)

GROWTH_SUMMARY_SPEC = importlib.util.spec_from_file_location(
    "summarize_dummy_growth_run",
    ROOT / "tools" / "summarize-dummy-growth-run.py",
)
assert GROWTH_SUMMARY_SPEC is not None and GROWTH_SUMMARY_SPEC.loader is not None
summarize_dummy_growth_run = importlib.util.module_from_spec(GROWTH_SUMMARY_SPEC)
GROWTH_SUMMARY_SPEC.loader.exec_module(summarize_dummy_growth_run)

GROWTH_REPLAY_SPEC = importlib.util.spec_from_file_location(
    "replay_dummy_growth_watchers",
    ROOT / "tools" / "replay-dummy-growth-watchers.py",
)
assert GROWTH_REPLAY_SPEC is not None and GROWTH_REPLAY_SPEC.loader is not None
replay_dummy_growth_watchers = importlib.util.module_from_spec(GROWTH_REPLAY_SPEC)
GROWTH_REPLAY_SPEC.loader.exec_module(replay_dummy_growth_watchers)

GROWTH_MONITOR_SPEC = importlib.util.spec_from_file_location(
    "monitor_dummy_growth_live",
    ROOT / "tools" / "monitor-dummy-growth-live.py",
)
assert GROWTH_MONITOR_SPEC is not None and GROWTH_MONITOR_SPEC.loader is not None
monitor_dummy_growth_live = importlib.util.module_from_spec(GROWTH_MONITOR_SPEC)
GROWTH_MONITOR_SPEC.loader.exec_module(monitor_dummy_growth_live)

RVR_SMOKE_SPEC = importlib.util.spec_from_file_location(
    "run_dummy_rvr_smoke",
    ROOT / "tools" / "run-dummy-rvr-smoke.py",
)
assert RVR_SMOKE_SPEC is not None and RVR_SMOKE_SPEC.loader is not None
run_dummy_rvr_smoke = importlib.util.module_from_spec(RVR_SMOKE_SPEC)
RVR_SMOKE_SPEC.loader.exec_module(run_dummy_rvr_smoke)

LIVE_COMPANION_ROLE_MATRIX_SPEC = importlib.util.spec_from_file_location(
    "run_live_companion_role_matrix",
    ROOT / "tools" / "run-live-companion-role-matrix.py",
)
assert LIVE_COMPANION_ROLE_MATRIX_SPEC is not None and LIVE_COMPANION_ROLE_MATRIX_SPEC.loader is not None
run_live_companion_role_matrix = importlib.util.module_from_spec(LIVE_COMPANION_ROLE_MATRIX_SPEC)
LIVE_COMPANION_ROLE_MATRIX_SPEC.loader.exec_module(run_live_companion_role_matrix)

LIVE_COMPANION_PLAYER_DRIVER_SPEC = importlib.util.spec_from_file_location(
    "run_live_companion_player_driver_smoke",
    ROOT / "tools" / "run-live-companion-player-driver-smoke.py",
)
assert LIVE_COMPANION_PLAYER_DRIVER_SPEC is not None and LIVE_COMPANION_PLAYER_DRIVER_SPEC.loader is not None
run_live_companion_player_driver_smoke = importlib.util.module_from_spec(LIVE_COMPANION_PLAYER_DRIVER_SPEC)
LIVE_COMPANION_PLAYER_DRIVER_SPEC.loader.exec_module(run_live_companion_player_driver_smoke)


class OperationalScriptTests(unittest.TestCase):
    def test_live_companion_role_matrix_defaults_cover_current_operational_baseline(self) -> None:
        self.assertEqual(
            run_live_companion_role_matrix.DEFAULT_PROFILES,
            [
                "support-crowd-control",
                "support-speed-song",
                "stealth-passive",
                "mixed-real-join",
                "tank-protection",
                "caster-dps",
                "healer-resurrection",
            ],
        )

    def test_live_companion_role_matrix_builds_profile_command_with_passthrough(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = run_live_companion_role_matrix.build_parser().parse_args(
                ["--run-root", temp_dir, "--replace"]
            )

            command = run_live_companion_role_matrix.build_profile_command(
                "caster-dps",
                args,
                ["--allow-leader-deaths", "1"],
            )

        self.assertEqual(command[0], sys.executable)
        self.assertTrue(command[1].replace("\\", "/").endswith("tools/run-live-companion-party-smoke.py"))
        self.assertEqual(command[command.index("--smoke-profile") + 1], "caster-dps")
        self.assertEqual(command[command.index("--run-dir") + 1], str(Path(temp_dir) / "caster-dps"))
        self.assertIn("--replace", command)
        self.assertEqual(command[-2:], ["--allow-leader-deaths", "1"])

    def test_live_companion_role_matrix_builds_healer_resurrection_with_stable_real_join_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = run_live_companion_role_matrix.build_parser().parse_args(
                ["--run-root", temp_dir]
            )

            command = run_live_companion_role_matrix.build_profile_command(
                "healer-resurrection",
                args,
                [],
            )

        self.assertIn("--real-player-join", command)
        self.assertEqual(command[command.index("--joiner-account") + 1], "albtest007")
        self.assertEqual(command[command.index("--roles") + 1], "healer,dps")

    def test_live_companion_player_driver_smoke_wraps_command_profile(self) -> None:
        command = run_live_companion_player_driver_smoke.build_command(["--dry-run"])

        self.assertTrue(command[1].replace("\\", "/").endswith("tools/run-live-companion-party-smoke.py"))
        self.assertEqual(command[command.index("--smoke-profile") + 1], "player-command-combat")
        self.assertEqual(
            command[command.index("--run-dir") + 1].replace("\\", "/"),
            "test-output/live-companion-selftest/player-command-combat",
        )
        self.assertIn("--replace", command)
        self.assertEqual(command[-1], "--dry-run")

    def test_live_companion_role_matrix_reads_player_accounts_from_profile_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "player-accounts.csv").write_text(
                "username,password,realm,char_index\n"
                "dummy300,dummy-pass,1,0\n"
                "albtest007,dummy-pass,1,0\n"
                "dummy300,dummy-pass,1,0\n",
                encoding="utf-8",
            )

            accounts = run_live_companion_role_matrix.profile_player_accounts(run_dir)

        self.assertEqual(accounts, ["dummy300", "albtest007"])

    def test_live_companion_role_matrix_main_returns_failure_when_any_profile_fails(self) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], cwd: Path | None = None) -> mock.Mock:
            calls.append(command)
            profile = command[command.index("--smoke-profile") + 1]
            return mock.Mock(returncode=0 if profile == "stealth-passive" else 12)

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            run_live_companion_role_matrix.subprocess,
            "run",
            side_effect=fake_run,
        ), mock.patch.object(run_live_companion_role_matrix, "wait_for_accounts_offline", return_value=True), mock.patch.object(
            run_live_companion_role_matrix.time, "sleep"
        ) as sleep_mock:
            rc = run_live_companion_role_matrix.main(
                [
                    "--run-root",
                    temp_dir,
                    "--profiles",
                    "stealth-passive,caster-dps",
                    "--replace",
                    "--allow-leader-deaths",
                    "1",
                ]
            )

        self.assertEqual(rc, 1)
        self.assertEqual(len(calls), 2)
        self.assertIn("--replace", calls[0])
        self.assertEqual(calls[1][-2:], ["--allow-leader-deaths", "1"])
        sleep_mock.assert_called_once_with(45.0)

    def test_live_companion_role_matrix_defaults_use_matrix_stability_settle(self) -> None:
        args = run_live_companion_role_matrix.build_parser().parse_args([])

        self.assertEqual(args.account_offline_timeout, 60.0)
        self.assertEqual(args.profile_settle_seconds, 45.0)
        self.assertEqual(args.healer_resurrection_pre_settle_seconds, 60.0)

    def test_live_companion_role_matrix_main_waits_for_previous_player_accounts_to_clear(self) -> None:
        def fake_run_profile(profile: str, args: object, passthrough: object) -> dict[str, object]:
            run_dir = Path(args.run_root) / profile
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "player-accounts.csv").write_text(
                "username,password,realm,char_index\n"
                f"{profile}-leader,dummy-pass,1,0\n",
                encoding="utf-8",
            )
            return {"profile": profile, "run_dir": str(run_dir), "return_code": 0}

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            run_live_companion_role_matrix,
            "run_profile",
            side_effect=fake_run_profile,
        ), mock.patch.object(
            run_live_companion_role_matrix,
            "wait_for_accounts_offline",
            return_value=True,
        ) as wait_mock, mock.patch.object(run_live_companion_role_matrix.time, "sleep") as sleep_mock:
            rc = run_live_companion_role_matrix.main(
                [
                    "--run-root",
                    temp_dir,
                    "--profiles",
                    "support-crowd-control,caster-dps",
                    "--profile-settle-seconds",
                    "5",
                ]
            )

        self.assertEqual(rc, 0)
        wait_mock.assert_called_once_with(
            "http://localhost:5000",
            ["support-crowd-control-leader"],
            timeout=60.0,
            poll_interval=1.0,
        )
        sleep_mock.assert_called_once_with(5.0)

    def test_live_companion_role_matrix_wait_for_accounts_offline_polls_until_clear(self) -> None:
        states = [
            {"player": {"name": "Dummy300"}},
            None,
        ]

        def fake_fetch_player_state(api_url: str, account: str, *, timeout: float = 2.0) -> dict[str, object] | None:
            self.assertEqual(api_url, "http://localhost:5000")
            self.assertEqual(account, "dummy300")
            self.assertEqual(timeout, 1.0)
            return states.pop(0)

        with mock.patch.object(
            run_live_companion_role_matrix,
            "fetch_player_state",
            side_effect=fake_fetch_player_state,
        ), mock.patch.object(run_live_companion_role_matrix.time, "sleep") as sleep_mock:
            cleared = run_live_companion_role_matrix.wait_for_accounts_offline(
                "http://localhost:5000",
                ["dummy300"],
                timeout=5.0,
                poll_interval=1.0,
            )

        self.assertTrue(cleared)
        sleep_mock.assert_called_once_with(1.0)

    def test_live_companion_player_facing_korean_text_is_readable(self) -> None:
        hire_npc = (ROOT / "GameServer" / "scripts" / "customnpc" / "CompanionHireNpc.cs").read_text(encoding="utf-8")
        gm_dummy = (ROOT / "GameServer" / "commands" / "gmcommands" / "dummy.cs").read_text(encoding="utf-8")
        companion_api = (ROOT / "GameServer" / "API" / "DummyCompanion" / "DummyCompanionRoutes.cs").read_text(
            encoding="utf-8"
        )

        for expected in [
            "용병 고용관",
            "고용: [치유형 고용] [방어형 고용] [공격형 고용]",
            "관리: [상태 확인] [요청 취소] [용병 해산]",
            "용병에게 연락을 넣었습니다.",
            "지금 가능한 용병이 없습니다.",
            "최근 용병 요청: 상태=",
        ]:
            self.assertIn(expected, hire_npc)
        self.assertNotIn("[파티 용병]", hire_npc)

        for expected in [
            "역할은 healer, tank, dps, support 중 하나여야 합니다.",
            "플레이어를 찾을 수 없습니다:",
            "용병 요청 상태",
        ]:
            self.assertIn(expected, gm_dummy)

        for expected in [
            "용병 요청이 취소되었습니다.",
            "용병이 파티에 합류했습니다.",
            "용병을 찾을 수 없습니다.",
            "용병이 이미 다른 파티에 속해 있습니다.",
        ]:
            self.assertIn(expected, companion_api)

    def test_rvr_smoke_behavior_command_targets_enemy_players_without_required_pve_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            accounts_csv = tmp_path / "alb.csv"
            accounts_csv.write_text("username,password,realm,char_index\nrvr001,p,1,0\n", encoding="utf-8")
            args = mock.Mock(
                host="127.0.0.1",
                port=10300,
                api_port=5000,
                hold=10,
                ramp_up=1,
                login_retries=1,
                login_retry_delay=0.1,
                enemy_player_max_distance=3600,
            )

            command = run_dummy_rvr_smoke.build_behavior_command(args, "alb", accounts_csv, tmp_path / "alb", 2)

        self.assertIn("--rvr-enemy-player-hunter", command)
        self.assertIn("--trace-observed-player-positions", command)
        self.assertIn("--startup-train-full-specs", command)
        self.assertIn("--startup-train-level", command)
        self.assertNotIn("--required-target-home", command)
        self.assertNotIn("--require-target-name", command)

    def test_rvr_smoke_uses_new_frontiers_region(self) -> None:
        self.assertEqual(run_dummy_rvr_smoke.FRONTIER_REGION, 163)

    def test_rvr_smoke_dry_run_skip_provision_builds_three_realm_commands_without_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                exit_code = run_dummy_rvr_smoke.main(
                    [
                        "--dry-run",
                        "--skip-provision",
                        "--run-dir",
                        str(Path(tmp) / "rvr-smoke"),
                        "--party-size",
                        "2",
                        "--hold",
                        "1",
                    ]
                )

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertEqual(output.count("behavior-dummy-client.py"), 3)
        for realm in ("alb", "mid", "hib"):
            self.assertIn(f"{realm}-accounts.csv", output)
        self.assertIn("--rvr-enemy-player-hunter", output)

    def test_rvr_smoke_reads_account_rows_for_level50_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accounts.csv"
            path.write_text(
                "username,password,realm,char_index,class_id,class_name,specs\n"
                "growthalb1,p,1,0,1,Paladin,Slash|39\n",
                encoding="utf-8",
            )

            rows = run_dummy_rvr_smoke.account_rows_from_csv(path)

        self.assertEqual(rows[0]["username"], "growthalb1")
        self.assertEqual(rows[0]["class_id"], "1")

    def test_rvr_smoke_stages_realms_inside_observation_range(self) -> None:
        points = list(run_dummy_rvr_smoke.FRONTIER_MEET_POINTS.values())

        for index, first in enumerate(points):
            for second in points[index + 1 :]:
                dx = first[0] - second[0]
                dy = first[1] - second[1]
                self.assertLessEqual(dx * dx + dy * dy, 700 * 700)

    def test_rvr_smoke_waypoints_stay_inside_frontier_patrol_envelope(self) -> None:
        center_x, center_y, center_z = run_dummy_rvr_smoke.FRONTIER_PATROL_CENTER

        for realm_key, meet_point in run_dummy_rvr_smoke.FRONTIER_MEET_POINTS.items():
            with self.subTest(realm=realm_key):
                waypoints = [
                    tuple(int(value) for value in waypoint.split(","))
                    for waypoint in run_dummy_rvr_smoke.rvr_waypoints(*meet_point).split("|")
                ]

                self.assertEqual(waypoints[0], meet_point)
                self.assertEqual(waypoints[1], run_dummy_rvr_smoke.FRONTIER_PATROL_CENTER)
                for x, y, z in waypoints:
                    self.assertEqual(z, center_z)
                    self.assertLessEqual(abs(x - center_x), 700)
                    self.assertLessEqual(abs(y - center_y), 700)

    def test_rvr_smoke_summary_counts_damage_when_attack_toggle_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir)
            encounters = case_dir / "encounters"
            encounters.mkdir()
            (encounters / "dummy.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"event": "rvr_enemy_player_target_committed"}),
                        json.dumps({"event": "tick", "action_counts": {"combat_damage_done": 3}}),
                        json.dumps({"event": "tick", "damage_done": 250}),
                        json.dumps({"event": "incoming_damage_player_counterattack"}),
                    ]
                ),
                encoding="utf-8",
            )

            summary = run_dummy_rvr_smoke.summarize_case(case_dir)

        self.assertEqual(summary["enemy_target_committed"], 1)
        self.assertEqual(summary["damage_done"], 250)
        self.assertEqual(summary["incoming_counterattack"], 1)

    def test_rvr_smoke_summary_counts_friendly_target_rejected_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir)
            encounters = case_dir / "encounters"
            encounters.mkdir()
            (encounters / "dummy.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"event": "friendly_target_rejected"}),
                        json.dumps({"event": "friendly_target_feedback"}),
                    ]
                ),
                encoding="utf-8",
            )

            summary = run_dummy_rvr_smoke.summarize_case(case_dir)

        self.assertEqual(summary["friendly_rejections"], 2)

    def test_midgard_hammer_spec_prefers_hammer_starter_weapon(self) -> None:
        rows = [
            {"TemplateID": "axe", "Item_Type": "10", "Object_Type": "13"},
            {"TemplateID": "hammer", "Item_Type": "10", "Object_Type": "12"},
            {"TemplateID": "shield", "Item_Type": "11", "Object_Type": "42"},
        ]

        ordered = provision_dummy_accounts.sort_starter_templates_for_specs(22, "Hammer|50;Sword|1;Axe|1", rows)

        self.assertEqual(ordered[0]["TemplateID"], "hammer")

    def test_midgard_axe_spec_prefers_axe_starter_weapon(self) -> None:
        rows = [
            {"TemplateID": "hammer", "Item_Type": "10", "Object_Type": "12"},
            {"TemplateID": "axe", "Item_Type": "10", "Object_Type": "13"},
        ]

        ordered = provision_dummy_accounts.sort_starter_templates_for_specs(31, "Axe|50;Hammer|1", rows)

        self.assertEqual(ordered[0]["TemplateID"], "axe")

    def test_preferred_starter_weapon_filter_removes_offspec_hand_weapon(self) -> None:
        rows = [
            {"TemplateID": "training_hammer", "Item_Type": "10", "Object_Type": "12"},
            {"TemplateID": "training_axe", "Item_Type": "11", "Object_Type": "13"},
            {"TemplateID": "small_training_shield", "Item_Type": "11", "Object_Type": "42"},
            {"TemplateID": "bronze_helm", "Item_Type": "21", "Object_Type": "34"},
        ]

        filtered = provision_dummy_accounts.filter_starter_templates_for_preferred_weapon(rows, 12)

        self.assertEqual(
            [row["TemplateID"] for row in filtered],
            ["training_hammer", "small_training_shield", "bronze_helm"],
        )

    def test_preferred_starter_weapon_filter_keeps_original_when_no_match_exists(self) -> None:
        rows = [
            {"TemplateID": "training_axe", "Item_Type": "11", "Object_Type": "13"},
            {"TemplateID": "small_training_shield", "Item_Type": "11", "Object_Type": "42"},
        ]

        filtered = provision_dummy_accounts.filter_starter_templates_for_preferred_weapon(rows, 12)

        self.assertEqual(filtered, rows)

    def test_growth_run_summary_treats_missing_columns_as_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            case_dir = root / "hib-p1"
            case_dir.mkdir()
            with (case_dir / "segment-001-metrics.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["username", "target_removed", "player_deaths"])
                writer.writeheader()
                writer.writerow({"username": "growthhib001", "target_removed": "2", "player_deaths": "0"})

            rows = summarize_dummy_growth_run.summarize_run(root)

        self.assertEqual(rows[0]["case"], "hib-p1")
        self.assertEqual(rows[0]["target_removed"], 2)
        self.assertEqual(rows[0]["player_deaths"], 0)
        self.assertEqual(rows[0]["target_timeouts"], 0)
        self.assertEqual(rows[0]["flee_events"], 0)
        self.assertEqual(rows[0]["watcher_rewind_warn"], 0)

    def test_growth_run_summary_reads_watcher_and_flee_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            case_dir = root / "hib-p8"
            case_dir.mkdir()
            with (case_dir / "segment-001-metrics.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "username",
                        "target_removed",
                        "player_deaths",
                        "target_timeouts",
                        "action_flee_start",
                        "action_flee_extend",
                        "action_flee_home_overrun",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "growthhib001",
                        "target_removed": "3",
                        "player_deaths": "0",
                        "target_timeouts": "1",
                        "action_flee_start": "1",
                        "action_flee_extend": "2",
                        "action_flee_home_overrun": "1",
                    }
                )
            with (case_dir / "watcher-movement-summary.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "xy_status",
                        "z_status",
                        "rewind_status",
                        "primary_behavior_anomaly_status",
                        "primary_behavior_aggro_not_dropped",
                        "primary_behavior_flee_too_short",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "xy_status": "warn",
                        "z_status": "ok",
                        "rewind_status": "warn",
                        "primary_behavior_anomaly_status": "critical",
                        "primary_behavior_aggro_not_dropped": "1",
                        "primary_behavior_flee_too_short": "1",
                    }
                )

            rows = summarize_dummy_growth_run.summarize_run(root)

        self.assertEqual(rows[0]["flee_events"], 4)
        self.assertEqual(rows[0]["watcher_xy_warn"], 1)
        self.assertEqual(rows[0]["watcher_z_warn"], 0)
        self.assertEqual(rows[0]["watcher_rewind_warn"], 1)
        self.assertEqual(rows[0]["watcher_behavior_critical"], 1)
        self.assertEqual(rows[0]["watcher_aggro_not_dropped"], 1)
        self.assertEqual(rows[0]["watcher_flee_too_short"], 1)

    def test_growth_live_monitor_detects_completed_primary_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir)
            self.assertFalse(monitor_dummy_growth_live.primary_metrics_complete(case_dir))

            with (case_dir / "segment-001-watcher-01-metrics.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["username", "ok"])
                writer.writeheader()
                writer.writerow({"username": "watcher001", "ok": "true"})
            self.assertFalse(monitor_dummy_growth_live.primary_metrics_complete(case_dir))

            with (case_dir / "segment-001-metrics.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["username", "ok"])
                writer.writeheader()
                writer.writerow({"username": "growthmid001", "ok": "true"})

            self.assertTrue(monitor_dummy_growth_live.primary_metrics_complete(case_dir))

    def test_growth_live_monitor_does_not_expand_target_radius_while_traveling(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "mid-p1"
            encounter_dir = case_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            control_path = case_dir / "live-control.json"
            control_path.write_text(
                json.dumps(
                    {
                        "hunter_target_api_engage_distance": 1500.0,
                        "max_target_distance": 1500.0,
                        "combat_direct_move_distance": 1500.0,
                        "hunter_target_api_radius": 2200.0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            rows = [
                {
                    "elapsed": 1.0,
                    "event": "hunter_target_scan_empty",
                    "behavior_state": "TravelToObjective",
                    "hunter_reject_counts": {"visible": 10, "distance": 10, "eligible": 0},
                },
                {
                    "elapsed": 4.0,
                    "event": "attack_decision",
                    "behavior_state": "ReturnToObjective",
                    "reason": "distance",
                },
            ]
            (encounter_dir / "segment-001-growthmid6500-1.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )

            changed, reason = monitor_dummy_growth_live.tune_control(
                case_dir,
                max_engage=2800.0,
                max_radius=5200.0,
                step=350.0,
            )
            payload = json.loads(control_path.read_text(encoding="utf-8"))

        self.assertFalse(changed)
        self.assertEqual(reason, "traveling_to_objective")
        self.assertEqual(payload["max_target_distance"], 1500.0)
        self.assertEqual(payload["hunter_target_api_radius"], 2200.0)

    def test_growth_live_monitor_expands_target_radius_while_hunting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "mid-p1"
            encounter_dir = case_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            control_path = case_dir / "live-control.json"
            control_path.write_text("{}\n", encoding="utf-8")
            rows = [
                {
                    "elapsed": 1.0,
                    "event": "hunter_target_scan_empty",
                    "behavior_state": "HuntObjective",
                    "hunter_reject_counts": {"visible": 10, "distance": 10, "eligible": 0},
                },
                {
                    "elapsed": 4.0,
                    "event": "attack_decision",
                    "behavior_state": "HuntObjective",
                    "reason": "distance",
                },
            ]
            (encounter_dir / "segment-001-growthmid6500-1.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )

            changed, reason = monitor_dummy_growth_live.tune_control(
                case_dir,
                max_engage=2800.0,
                max_radius=5200.0,
                step=350.0,
            )
            payload = json.loads(control_path.read_text(encoding="utf-8"))

        self.assertTrue(changed)
        self.assertEqual(reason, "distance")
        self.assertEqual(payload["max_target_distance"], 1850.0)
        self.assertEqual(payload["hunter_target_api_radius"], 2725.0)

    def test_growth_live_monitor_does_not_expand_target_radius_during_active_combat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "mid-p1"
            encounter_dir = case_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            control_path = case_dir / "live-control.json"
            control_path.write_text(
                json.dumps(
                    {
                        "hunter_target_api_engage_distance": 1500.0,
                        "max_target_distance": 1500.0,
                        "combat_direct_move_distance": 1500.0,
                        "hunter_target_api_radius": 2200.0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            rows = [
                {
                    "elapsed": 1.0,
                    "event": "hunter_target_scan_empty",
                    "behavior_state": "TravelToObjective",
                    "hunter_reject_counts": {"visible": 10, "distance": 10, "eligible": 0},
                },
                {
                    "elapsed": 4.0,
                    "event": "hunter_target_scan_empty",
                    "behavior_state": "TravelToObjective",
                    "hunter_reject_counts": {"visible": 10, "distance": 10, "eligible": 0},
                },
                {
                    "elapsed": 8.0,
                    "event": "attack_decision",
                    "behavior_state": "HuntObjective",
                    "current_target": 12100,
                    "target_name": "wood imp",
                    "reason": "smooth_visible_target",
                },
            ]
            (encounter_dir / "segment-001-growthmid6500-1.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )

            changed, reason = monitor_dummy_growth_live.tune_control(
                case_dir,
                max_engage=2800.0,
                max_radius=5200.0,
                step=350.0,
            )
            payload = json.loads(control_path.read_text(encoding="utf-8"))

        self.assertFalse(changed)
        self.assertEqual(reason, "active_combat")
        self.assertEqual(payload["max_target_distance"], 1500.0)
        self.assertEqual(payload["hunter_target_api_radius"], 2200.0)

    def test_replay_dummy_growth_watchers_rebuilds_summary_from_existing_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            case_dir = root / "mid-p1"
            movement_dir = case_dir / "movement"
            encounter_dir = case_dir / "encounters"
            movement_dir.mkdir(parents=True)
            encounter_dir.mkdir()
            with (root / "timeline.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["case", "segment", "level_before"])
                writer.writeheader()
                writer.writerow({"case": "mid-p1", "segment": "1", "level_before": "6"})
            with (case_dir / "watcher-movement-summary.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["case", "segment", "primary_account", "watcher_account"])
                writer.writeheader()
                writer.writerow(
                    {
                        "case": "mid-p1",
                        "segment": "1",
                        "primary_account": "growthmid001",
                        "watcher_account": "growthmid002",
                    }
                )
            movement_rows = [
                {"event": "move_step", "t": 0, "x": 10, "y": 10, "z": 100},
                {"event": "move_step", "t": 1, "x": 20, "y": 20, "z": 100},
            ]
            for account in ("growthmid001", "growthmid002"):
                (movement_dir / f"segment-001-{account}-1.jsonl").write_text(
                    "\n".join(json.dumps(row) for row in movement_rows) + "\n",
                    encoding="utf-8",
                )
            (encounter_dir / "segment-001-growthmid001-1.jsonl").write_text(
                json.dumps({"event": "flee_start", "t": 0, "target_name": "huldu hunter", "x": 10, "y": 10})
                + "\n"
                + json.dumps(
                    {
                        "event": "flee_threat_pressure",
                        "t": 15,
                        "target_name": "huldu hunter",
                        "character": "GrowthMid001",
                        "flee_threat_target": "GrowthMid001",
                        "flee_threat_active": True,
                        "flee_threat_distance": 900,
                        "x": 20,
                        "y": 20,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            rows, critical = replay_dummy_growth_watchers.replay_run(
                root,
                replay_dummy_growth_watchers.parse_args([str(root)]),
            )

            with (case_dir / "watcher-movement-summary.csv").open(encoding="utf-8", newline="") as handle:
                summary_rows = list(csv.DictReader(handle))

        self.assertEqual(rows, 1)
        self.assertEqual(critical, 1)
        self.assertEqual(summary_rows[0]["primary_behavior_anomaly_status"], "critical")
        self.assertEqual(summary_rows[0]["primary_behavior_aggro_not_dropped"], "1")

    def test_boss_rule_matrix_runner_uses_disjoint_party_account_files(self) -> None:
        script = (ROOT / "tools" / "run-dummy-boss-rule-matrix.sh").read_text(encoding="utf-8")

        self.assertIn("dummy-party-albion-pve8.csv", script)
        self.assertIn("dummy-party-albion-mixed-pve8.csv", script)
        self.assertIn("dummy-party-albion-boss-support-pve8.csv", script)
        self.assertIn("dummy-party-albion-boss-healwall-pve8.csv", script)
        self.assertIn("dummy-party-albion-boss-ranged-pve8.csv", script)

    def test_boss_rule_matrix_runner_varies_rescue_rules(self) -> None:
        script = (ROOT / "tools" / "run-dummy-boss-rule-matrix.sh").read_text(encoding="utf-8")

        self.assertIn("--party-rescue-objective-max-distance", script)
        self.assertIn("--party-rescue-assist-after", script)
        self.assertIn("OPENDAOC_MATRIX_MODE", script)
        self.assertIn("--party-size \"$party_size\"", script)
        self.assertIn("matrix.tsv", script)

    def test_boss_rule_matrix_has_realm_120_mode(self) -> None:
        script = (ROOT / "tools" / "run-dummy-boss-rule-matrix.sh").read_text(encoding="utf-8")

        self.assertIn('MATRIX_MODE" == "realms120"', script)
        cleanup_block = 'if [[ "$ISOLATE_BOSS_CLONES" == "1" ]]; then\n  delete_test_boss_clones\nfi'
        self.assertIn(cleanup_block, script)
        cleanup_index = script.index(cleanup_block)
        realms_index = script.index('MATRIX_MODE" == "realms120"')
        self.assertLess(cleanup_index, realms_index)
        self.assertIn("dummy-accounts-albion-40.csv", script)
        self.assertIn("dummy-accounts-midgard-40.csv", script)
        self.assertIn("dummy-accounts-hibernia-40.csv", script)
        self.assertIn("Golestandt", script)
        self.assertIn("Gjalpinulva", script)
        self.assertIn("Cuuldurach the Glimmer King", script)
        self.assertIn("alb_golestandt40\tGolestandt\t80\ttools/dummy-accounts-albion-40.csv\t2200\t3\t1\t0\t1\t40", script)
        self.assertIn("mid_gjalpinulva40\tGjalpinulva\t80\ttools/dummy-accounts-midgard-40.csv\t2200\t3\t1\t0\t1\t40", script)
        self.assertIn("hib_cuuldurach40\tCuuldurach the Glimmer King\t80\ttools/dummy-accounts-hibernia-40.csv\t2200\t3\t1\t0\t1\t40", script)
        self.assertIn('launch_case alb_golestandt40 "Golestandt" 80 tools/dummy-accounts-albion-40.csv "$REALM_ROTATIONS_40" 2200 3 1 0 1 40 40', script)
        self.assertIn('launch_case mid_gjalpinulva40 "Gjalpinulva" 80 tools/dummy-accounts-midgard-40.csv "$REALM_ROTATIONS_40" 2200 3 1 0 1 40 40', script)
        self.assertIn('launch_case hib_cuuldurach40 "Cuuldurach the Glimmer King" 80 tools/dummy-accounts-hibernia-40.csv "$REALM_ROTATIONS_40" 2200 3 1 0 1 40 40', script)
        self.assertIn('RANGED_ASSIST_EXTRA_DELAY="${OPENDAOC_MATRIX_RANGED_ASSIST_EXTRA_DELAY:-0}"', script)
        self.assertIn('--party-ranged-assist-extra-delay "$RANGED_ASSIST_EXTRA_DELAY"', script)
        self.assertIn('PREENGAGE_RANGED_SAFE_DISTANCE="${OPENDAOC_MATRIX_PREENGAGE_RANGED_SAFE_DISTANCE:-0}"', script)
        self.assertIn('--party-preengage-ranged-safe-distance "$PREENGAGE_RANGED_SAFE_DISTANCE"', script)
        self.assertIn('BURN_REQUIRED_TARGET_HEALTH_PERCENT="${OPENDAOC_MATRIX_BURN_REQUIRED_TARGET_HEALTH_PERCENT:-0}"', script)
        self.assertIn('--party-burn-required-target-health-percent "$BURN_REQUIRED_TARGET_HEALTH_PERCENT"', script)
        self.assertIn("--party-focus-pressure-offtank-reaggro", script)
        self.assertIn("--party-target-loss-grace 12", script)
        self.assertIn("--party-target-removed-preserve-limit 100", script)
        self.assertIn('SERVER_SNAPSHOT_RADIUS="${OPENDAOC_MATRIX_SERVER_SNAPSHOT_RADIUS:-5000}"', script)
        self.assertIn('--snapshot-radius "$SERVER_SNAPSHOT_RADIUS"', script)
        self.assertIn('CASE_FILTER="${OPENDAOC_MATRIX_CASE_FILTER:-}"', script)
        self.assertIn('case_enabled()', script)
        self.assertIn('MATRIX_MODE" == "realms120" && -n "$CASE_FILTER"', script)
        self.assertIn(
            'run_case "$case_name" "$@" &\n'
            '  pids+=($!)\n'
            '  cases_launched=$((cases_launched + 1))\n'
            '  if (( CASE_LAUNCH_STAGGER > 0 )); then\n'
            '    sleep "$CASE_LAUNCH_STAGGER"\n'
            '  fi\n'
            '  if (( MAX_PARALLEL_CASES > 0 && ${#pids[@]} >= MAX_PARALLEL_CASES )); then\n'
            '    wait_case_wave\n'
            '  fi',
            script,
        )
        self.assertIn('LOGIN_RETRIES="${OPENDAOC_MATRIX_LOGIN_RETRIES:-', script)
        self.assertIn('--login-retries "$LOGIN_RETRIES" --login-retry-delay "$LOGIN_RETRY_DELAY"', script)
        self.assertIn('CASE_WAVE_COOLDOWN="${OPENDAOC_MATRIX_CASE_WAVE_COOLDOWN:-8}"', script)
        self.assertIn('if (( CASE_WAVE_COOLDOWN > 0 )); then\n    sleep "$CASE_WAVE_COOLDOWN"\n  fi', script)
        self.assertIn('FORCE_CASTER_RESCUE="${OPENDAOC_MATRIX_FORCE_CASTER_RESCUE:-}"', script)
        self.assertIn('FORCE_SUPPORT_EVASION="${OPENDAOC_MATRIX_FORCE_SUPPORT_EVASION:-}"', script)
        self.assertIn('CLEAR_OBJECTIVE_ADDS_BEFORE_ENGAGE="${OPENDAOC_MATRIX_CLEAR_OBJECTIVE_ADDS_BEFORE_ENGAGE:-0}"', script)
        self.assertIn('ACTIVE_TANK_HANDOFF_HEALTH_PERCENT="${OPENDAOC_MATRIX_ACTIVE_TANK_HANDOFF_HEALTH_PERCENT:-0}"', script)
        self.assertIn('BOSS_NON_TANK_MELEE_BACKOFF="${OPENDAOC_MATRIX_BOSS_NON_TANK_MELEE_BACKOFF:-0}"', script)
        self.assertIn('if [[ -n "$FORCE_CASTER_RESCUE" ]]; then\n    caster_rescue="$FORCE_CASTER_RESCUE"\n  fi', script)
        self.assertIn('if [[ -n "$FORCE_SUPPORT_EVASION" ]]; then\n    support_evasion="$FORCE_SUPPORT_EVASION"\n  fi', script)
        self.assertIn('if [[ "$CLEAR_OBJECTIVE_ADDS_BEFORE_ENGAGE" == "1" ]]; then\n    clear_objective_adds_args+=(--party-clear-objective-adds-before-engage)\n  fi', script)
        self.assertIn('--party-active-tank-handoff-health-percent "$ACTIVE_TANK_HANDOFF_HEALTH_PERCENT"', script)
        self.assertIn('boss_non_tank_melee_backoff_args+=(--party-boss-non-tank-melee-backoff)', script)

    def test_boss_rule_matrix_raidmix_uses_shared_case_launcher(self) -> None:
        script = (ROOT / "tools" / "run-dummy-boss-rule-matrix.sh").read_text(encoding="utf-8")

        self.assertIn('MATRIX_MODE" == "raidmix"', script)
        self.assertIn('launch_case moran_balanced16 "Moran the Mighty"', script)
        self.assertIn('launch_case cailleach_heal16 "Cailleach Uragaig"', script)
        self.assertIn('launch_case fester_ranged8 "Fester"', script)

    def test_boss_rule_matrix_has_raidmix40_mode(self) -> None:
        script = (ROOT / "tools" / "run-dummy-boss-rule-matrix.sh").read_text(encoding="utf-8")

        self.assertIn('MATRIX_MODE" == "raidmix40"', script)
        self.assertIn("accounts-raidmix40.csv", script)
        self.assertIn("moran_raid40\tMoran the Mighty\t73\t$RAIDMIX40", script)
        self.assertIn("cailleach_raid40\tCailleach Uragaig\t70\t$RAIDMIX40", script)
        self.assertIn("fester_raid40\tFester\t64\t$RAIDMIX40", script)
        self.assertIn('launch_case moran_raid40 "Moran the Mighty" 73 "$RAIDMIX40" "$REALM_ROTATIONS_40" 1800 3 1 0 0 40 40', script)
        self.assertIn('launch_case cailleach_raid40 "Cailleach Uragaig" 70 "$RAIDMIX40" "$REALM_ROTATIONS_40" 1800 4 1 0 0 40 40', script)
        self.assertIn('launch_case fester_raid40 "Fester" 64 "$RAIDMIX40" "$REALM_ROTATIONS_40" 1800 2 1 0 0 40 40', script)

    def test_boss_rule_matrix_has_sweep_300_mode_with_account_slices(self) -> None:
        script = (ROOT / "tools" / "run-dummy-boss-rule-matrix.sh").read_text(encoding="utf-8")

        self.assertIn('MATRIX_MODE" == "sweep300"', script)
        self.assertIn("SWEEP_POOL_COUNT", script)
        self.assertIn("slice_accounts_csv", script)
        self.assertIn("clone_target_for_case", script)
        self.assertIn("delete_test_boss_clones", script)
        self.assertIn("OPENDAOC_MATRIX_ISOLATE_BOSS_CLONES", script)
        self.assertIn("OPENDAOC_MATRIX_CLONE_DENSITY_PROFILE", script)
        self.assertIn("OPENDAOC_MATRIX_CLONE_MIN_SOURCE_DISTANCE", script)
        self.assertIn("OPENDAOC_MATRIX_CLONE_MIN_TEST_DISTANCE", script)
        self.assertIn('CLONE_NEARBY_RADIUS="${OPENDAOC_MATRIX_CLONE_NEARBY_RADIUS:-2600}"', script)
        self.assertIn('"nearbyRadius": str(nearby_radius)', script)
        self.assertIn("clone_nearby_radius", script)
        self.assertIn("source-distance", script)
        self.assertIn("test-clone-distance", script)
        self.assertIn("OPENDAOC_MATRIX_CASE_LAUNCH_STAGGER", script)
        self.assertIn("OPENDAOC_MATRIX_RESCUE_MAX_AGE", script)
        self.assertIn("OPENDAOC_MATRIX_RESCUE_EMERGENCY_ASSIST_AFTER", script)
        self.assertIn("dense", script)
        self.assertIn("tools/dummy-accounts-albion-${SWEEP_POOL_COUNT}.csv", script)
        self.assertIn("support_evasion|2200|3|1|0|1|8", script)
        self.assertIn("party16|2200|3|1|0|0|16", script)
        self.assertIn("party16_caster_rescue|2600|2|1|1|0|16", script)

    def test_boss_rule_matrix_case_filter_tracks_completed_launched_cases(self) -> None:
        script = (ROOT / "tools" / "run-dummy-boss-rule-matrix.sh").read_text(encoding="utf-8")

        self.assertIn("cases_launched=0", script)
        self.assertIn("cases_launched=$((cases_launched + 1))", script)
        self.assertIn('&& "$cases_launched" -eq 0', script)

    def test_dummy_combat_npc_query_ignores_deleted_test_clones(self) -> None:
        source = (ROOT / "GameServer" / "API" / "DummyCombat" / "DummyCombatRoutes.cs").read_text(encoding="utf-8")
        query_block = source[source.index('api.MapGet("/api/dummy/combat/npcs"') : source.index('api.MapPost("/api/dummy/combat/clone-npc"')]

        self.assertIn("npc.ObjectState is GameObject.eObjectState.Active", query_block)

    def test_boss_rule_matrix_uses_dynamic_party_formation_offsets(self) -> None:
        script = (ROOT / "tools" / "run-dummy-boss-rule-matrix.sh").read_text(encoding="utf-8")

        self.assertIn("def formation_offset", script)
        self.assertIn("if total <= 8:", script)
        self.assertNotIn("index % len(offsets)", script)

    def test_dummy_combat_api_can_create_and_cleanup_test_clones(self) -> None:
        source = (ROOT / "GameServer" / "API" / "DummyCombat" / "DummyCombatRoutes.cs").read_text(encoding="utf-8")

        self.assertIn('/api/dummy/combat/clone-npc', source)
        self.assertIn('/api/dummy/combat/test-clones', source)
        self.assertIn('TestClonePrefix = "KDAOC_TEST_"', source)
        self.assertIn("CreateNpcClone", source)
        self.assertIn("RemoveTestClones", source)
        self.assertIn("CountNearbyNpcs", source)
        self.assertIn("nearbyNpcCount", source)

    def test_dummy_combat_api_exposes_server_side_encounter_snapshot(self) -> None:
        source = (ROOT / "GameServer" / "API" / "DummyCombat" / "DummyCombatRoutes.cs").read_text(encoding="utf-8")

        self.assertIn('/api/dummy/combat/encounter-snapshot', source)
        self.assertIn('eventType = "server_encounter_snapshot"', source)
        self.assertIn("ToPlayerEncounterDto", source)
        self.assertIn("ToNpcEncounterDto", source)
        self.assertIn("targetObjectId", source)
        self.assertIn("distance = HorizontalDistance", source)

    def test_dummy_combat_api_exposes_player_condition_flags_for_support_ai(self) -> None:
        source = (ROOT / "GameServer" / "API" / "DummyCombat" / "DummyCombatRoutes.cs").read_text(encoding="utf-8")

        self.assertIn("ToPlayerCombatDto", source)
        self.assertIn("isStunned = player.IsStunned", source)
        self.assertIn("isMezzed = player.IsMezzed", source)
        self.assertIn("isDiseased = player.IsDiseased", source)
        self.assertIn("isPoisoned = player.IsPoisoned", source)
        self.assertIn("isSilenced = player.IsSilenced", source)
        self.assertIn("isNearsighted = player.effectListComponent.ContainsEffectForEffectType(DOL.GS.eEffect.Nearsight)", source)

    def test_game_npc_left_hand_weapon_setter_is_not_recursive(self) -> None:
        source = (ROOT / "GameServer" / "gameobjects" / "GameNPC.cs").read_text(encoding="utf-8")

        property_block = source[source.index("public bool CanUseLefthandedWeapon") : source.index("public override void StartInterruptTimer")]
        self.assertNotIn("set => CanUseLefthandedWeapon = value", property_block)
        self.assertIn("m_leftHandSwingChance = 0", property_block)

    def test_boss_runner_enables_local_rescue_by_default(self) -> None:
        script = (ROOT / "tools" / "run-dummy-boss-elidyn-pve40.sh").read_text(encoding="utf-8")

        self.assertIn('LOCAL_RESCUE="${OPENDAOC_BOSS_LOCAL_RESCUE:-1}"', script)

    def test_boss_runner_allows_pre_engage_add_rescue_by_default(self) -> None:
        script = (ROOT / "tools" / "run-dummy-boss-elidyn-pve40.sh").read_text(encoding="utf-8")

        self.assertIn('RESCUE_BEFORE_OBJECTIVE_ENGAGED="${OPENDAOC_BOSS_RESCUE_BEFORE_OBJECTIVE_ENGAGED:-1}"', script)
        self.assertIn("--party-rescue-before-objective-engaged", script)

    def test_boss_runner_keeps_objective_add_preclear_opt_in(self) -> None:
        script = (ROOT / "tools" / "run-dummy-boss-elidyn-pve40.sh").read_text(encoding="utf-8")

        self.assertIn('CLEAR_OBJECTIVE_ADDS_BEFORE_ENGAGE="${OPENDAOC_BOSS_CLEAR_OBJECTIVE_ADDS_BEFORE_ENGAGE:-0}"', script)
        self.assertIn("--party-clear-objective-adds-before-engage", script)

    def test_boss_runner_uses_wide_objective_add_rescue_radius(self) -> None:
        script = (ROOT / "tools" / "run-dummy-boss-elidyn-pve40.sh").read_text(encoding="utf-8")

        self.assertIn('RESCUE_OBJECTIVE_DISTANCE="${OPENDAOC_BOSS_RESCUE_OBJECTIVE_DISTANCE:-1800}"', script)

    def test_boss_runner_uses_stationary_cast_hold(self) -> None:
        script = (ROOT / "tools" / "run-dummy-boss-elidyn-pve40.sh").read_text(encoding="utf-8")

        self.assertIn("--stationary-cast-actions", script)
        self.assertIn("--cast-action-hold", script)

    def test_visible_launcher_does_not_pause_on_exit_by_default(self) -> None:
        script = (ROOT / "start-main-server-visible.bat").read_text(encoding="utf-8")

        self.assertIn("OPENDAOC_PAUSE_ON_EXIT", script)
        self.assertNotIn("\npause >nul\nexit /b", script.lower())

    def test_visible_launcher_defers_companion_until_api_ready(self) -> None:
        script = (ROOT / "start-main-server-visible.bat").read_text(encoding="utf-8")

        self.assertIn("start-companion-after-api-ready.ps1", script)
        self.assertIn("OPENDAOC_START_COMPANION_SERVICE", script)
        self.assertNotIn('start "OpenDAoC Companion Service" "%SCRIPT_DIR%start-live-companion-service-visible.bat"', script)

    def test_visible_launcher_exports_gemini_key_to_wsl(self) -> None:
        script = (ROOT / "start-main-server-visible.bat").read_text(encoding="utf-8")

        self.assertIn("GEMINI_API_KEY/u", script)
        self.assertIn("OPENAI_API_KEY/u", script)
        self.assertLess(script.index("GEMINI_API_KEY/u"), script.index("wsl.exe -d Ubuntu"))
        self.assertLess(script.index("OPENAI_API_KEY/u"), script.index("wsl.exe -d Ubuntu"))

    def test_companion_api_ready_helper_starts_visible_companion_launcher_after_probe(self) -> None:
        script = (ROOT / "tools" / "start-companion-after-api-ready.ps1").read_text(encoding="utf-8")

        self.assertIn("OPENDAOC_COMPANION_API_URL", script)
        self.assertIn("/api/dummy/companions/config", script)
        self.assertIn("Invoke-WebRequest", script)
        self.assertIn("start-live-companion-service-visible.bat", script)
        self.assertLess(script.find("Invoke-WebRequest"), script.find("start-live-companion-service-visible.bat"))
        self.assertNotIn("OPENAI_API_KEY", script)
        self.assertNotIn("sk-", script.lower())

    def test_live_companion_visible_launcher_uses_standard_wsl_service_runner(self) -> None:
        script = (ROOT / "start-live-companion-service-visible.bat").read_text(encoding="utf-8")

        self.assertIn("OpenDAoC Companion Service", script)
        self.assertIn("wsl.exe -d Ubuntu", script)
        self.assertIn("tools/start-live-companion-service.sh", script)
        self.assertIn("OPENDAOC_COMPANION_PAUSE_ON_EXIT", script)
        self.assertNotIn("\npause >nul\nexit /b", script.lower())

    def test_live_companion_service_runner_uses_safe_operational_defaults(self) -> None:
        script = (ROOT / "tools" / "start-live-companion-service.sh").read_text(encoding="utf-8")

        self.assertIn('API_URL="${OPENDAOC_COMPANION_API_URL:-http://localhost:5000}"', script)
        self.assertIn('ACCOUNTS_CSV="${OPENDAOC_COMPANION_ACCOUNTS:-tools/dummy-live-companions.csv}"', script)
        self.assertIn('RUN_DIR="${OPENDAOC_COMPANION_RUN_DIR:-test-output/live-companion-service}"', script)
        self.assertIn('MAX_RUNTIME="${OPENDAOC_COMPANION_MAX_RUNTIME:-0}"', script)
        self.assertIn("tools/dummy-companion-service.py", script)
        self.assertIn("--max-runtime", script)
        self.assertIn("OPENDAOC_COMPANION_ONCE", script)
        self.assertIn("OPENDAOC_COMPANION_DRY_RUN", script)
        self.assertIn("OPENDAOC_COMPANION_WAIT_API", script)
        self.assertIn("OPENDAOC_COMPANION_WAIT_API_TIMEOUT", script)
        self.assertIn("/api/dummy/companions/config", script)
        self.assertIn('sed "s/\\r$//" "$ENV_FILE"', script)
        self.assertIn('if [[ "$DIALOGUE_ENABLED" == "1" ]]', script)
        self.assertIn("--ai-gateway-model-alias", script)
        self.assertIn("--ai-guide-model-alias", script)
        self.assertIn("small-dialogue", script)
        self.assertIn("openai-small-guide", script)
        self.assertNotIn("OPENAI_API_KEY=", script)
        self.assertNotIn("sk-", script.lower())

    def test_live_companion_windows_wrapper_calls_visible_launcher(self) -> None:
        script = (ROOT / "tools" / "windows-open-visible-companion-service.cmd").read_text(encoding="utf-8")

        self.assertIn("start-live-companion-service-visible.bat", script)

    def test_live_companion_request_model_carries_explicit_objective_target(self) -> None:
        service = (ROOT / "GameServer" / "LiveCompanion" / "CompanionRequestService.cs").read_text(encoding="utf-8")
        api = (ROOT / "GameServer" / "API" / "DummyCompanion" / "DummyCompanionRoutes.cs").read_text(encoding="utf-8")

        self.assertIn("public string ObjectiveTarget { get; set; }", service)
        self.assertIn("string objectiveTarget = \"\"", service)
        self.assertIn("ObjectiveTarget = string.IsNullOrWhiteSpace(objectiveTarget)", service)
        self.assertIn("ObjectiveTarget = request.ObjectiveTarget", service)
        self.assertIn('Query(context, "objectiveTarget"', api)

    def test_windows_cleanup_rechecks_cmd_windows_after_wsl_bridge_cleanup(self) -> None:
        script = (ROOT / "tools" / "cleanup-main-server-windows.ps1").read_text(encoding="utf-8")

        self.assertIn("function Stop-StaleOpenDaocCmdWindows", script)
        self.assertIn("$currentLauncherPids", script)
        self.assertIn("Get-CurrentLauncherProcessIds", script)
        self.assertIn("-not $currentLauncherPids.ContainsKey($_.ProcessId)", script)
        self.assertGreater(script.rfind("Stop-StaleOpenDaocCmdWindows"), script.find("old WSL server bridge"))

    def test_provision_character_insert_overrides_realm_and_class_cycle(self) -> None:
        args = mock.Mock(
            realm=2,
            class_cycle_values=["22", "26"],
            race_cycle_values=["5"],
            creation_model_cycle_values=[],
            current_model_cycle_values=[],
            spec_cycle_values=["Hammer|50;Shields|42"],
            ability_cycle_values=[],
            start_x=None,
            start_y=None,
            start_z=None,
            start_region=None,
            position_step=20,
            template_account="bigjuh",
            template_character="천재다",
        )

        with mock.patch.object(
            provision_dummy_accounts,
            "get_columns",
            return_value=[
                "AccountName",
                "AccountSlot",
                "Name",
                "DOLCharacters_ID",
                "Realm",
                "Class",
                "Race",
                "SerializedSpecs",
                "Xpos",
                "Ypos",
            ],
        ):
            sql = provision_dummy_accounts.build_character_insert(args, "midtest001", "Midtest001", 200, 0)

        self.assertIn("2 AS `Realm`", sql)
        self.assertIn("22 AS `Class`", sql)
        self.assertIn("5 AS `Race`", sql)
        self.assertIn("'Hammer|50;Shields|42' AS `SerializedSpecs`", sql)

    def test_dummy_csv_char_index_uses_world_init_realm_offset(self) -> None:
        self.assertEqual(provision_dummy_accounts.client_character_index(1, 0), 0)
        self.assertEqual(provision_dummy_accounts.client_character_index(2, 0), 10)
        self.assertEqual(provision_dummy_accounts.client_character_index(3, 0), 20)

    def test_dummy_csv_includes_class_metadata_for_boss_reports(self) -> None:
        path = ROOT / "tools" / "test-dummy-accounts-metadata.csv"
        try:
            provision_dummy_accounts.write_accounts_csv(
                path,
                [
                    {
                        "username": "albtest005",
                        "password": "dummy-pass",
                        "realm": 1,
                        "char_index": 0,
                        "class_id": 5,
                        "class_name": "Theurgist",
                        "specs": "Earth Magic|45;Ice Magic|25;Wind Magic|8",
                    }
                ],
            )
            payload = path.read_text(encoding="utf-8")
        finally:
            path.unlink(missing_ok=True)

        self.assertIn("username,password,realm,char_index,class_id,class_name,specs", payload)
        self.assertIn("albtest005,dummy-pass,1,0,5,Theurgist", payload)

    def test_realm_pool_provisioner_creates_one_hundred_twenty_across_three_realms(self) -> None:
        script = (ROOT / "tools" / "provision-dummy-realm-pools.sh").read_text(encoding="utf-8")

        self.assertIn("--prefix albtest", script)
        self.assertIn("--prefix midtest", script)
        self.assertIn("--prefix hibtest", script)
        self.assertIn("--count \"${OPENDAOC_REALM_POOL_COUNT:-40}\"", script)
        self.assertIn("--realm 1", script)
        self.assertIn("--realm 2", script)
        self.assertIn("--realm 3", script)
        self.assertIn("dummy-accounts-albion-${POOL_COUNT}.csv", script)

    def test_realm_pool_provisioner_uses_extended_albion_class_cycle(self) -> None:
        script = (ROOT / "tools" / "provision-dummy-realm-pools.sh").read_text(encoding="utf-8")

        self.assertIn('--class-cycle "1|2|11|10|6|6|7|5|1|2|11|4|6|10|13|8"', script)
        self.assertIn("Staff|39;Enhancement|45;Rejuvenation|30;Parry|18", script)
        self.assertIn("Earth Magic|45;Cold Magic|25;Wind Magic|8", script)
        self.assertIn("Instruments|44;Slash|39;Stealth|25", script)
        self.assertIn("Body Magic|45;Mind Magic|29;Matter Magic|4", script)

    def test_realm_pool_provisioner_equips_and_validates_boss_ready_dummies(self) -> None:
        script = (ROOT / "tools" / "provision-dummy-realm-pools.sh").read_text(encoding="utf-8")

        self.assertIn("tools/equip-dummy-boss-gear.py", script)
        self.assertIn("tools/validate-dummy-50-setup.py", script)
        self.assertLess(script.find("tools/equip-dummy-boss-gear.py"), script.find("tools/validate-dummy-50-setup.py"))

    def test_fast_status_checks_read_only_dynamic_quest_api_on_standard_port(self) -> None:
        script = (ROOT / "tools" / "check-main-server-fast.sh").read_text(encoding="utf-8")

        self.assertIn('local port="${OPENDAOC_API_PORT:-5000}"', script)
        self.assertIn("/api/world/dynamic-quests/story-config", script)
        self.assertIn("OK api ${OPENDAOC_API_PORT:-5000}", script)
        self.assertIn("DOWN api ${OPENDAOC_API_PORT:-5000}", script)

    def test_dummy_load_test_uses_current_dummy_template_defaults(self) -> None:
        script = (ROOT / "tools" / "run-dummy-load-test.py").read_text(encoding="utf-8")

        self.assertIn('parser.add_argument("--template-account", default=os.environ.get("OPENDAOC_TEMPLATE_ACCOUNT", "dummy040"))', script)
        self.assertIn('parser.add_argument("--template-character", default=os.environ.get("OPENDAOC_TEMPLATE_CHARACTER", "Dummy040"))', script)
        self.assertIn('"--template-account"', script)
        self.assertIn('"--template-character"', script)

    def test_mobgrowth_pressure_load_scenario_has_hunt_area(self) -> None:
        script = (ROOT / "tools" / "run-dummy-load-test.py").read_text(encoding="utf-8")
        scenario_start = script.index('"mobgrowth-pressure": BalanceScenario(')
        scenario_end = script.index("),", scenario_start)
        scenario = script[scenario_start:scenario_end]

        self.assertIn("max_target_distance=4500", scenario)
        self.assertIn("path_graph=ALBION_LOW_LEVEL_PATH_GRAPH", scenario)
        self.assertIn("start_x=ALBION_LOW_LEVEL_START[0]", scenario)
        self.assertIn("waypoints=ALBION_LOW_LEVEL_WAYPOINTS", scenario)

    def test_behavior_dummy_does_not_send_invalid_face_or_stick_commands(self) -> None:
        script = (ROOT / "tools" / "behavior-dummy-client.py").read_text(encoding="utf-8")

        self.assertNotIn('send_command("/face")', script)
        self.assertNotIn('send_command("/stick")', script)
        self.assertIn("facegloc_command_for_point", script)
        self.assertIn("stick_command_skipped_unavailable", script)

    def test_behavior_dummy_default_commands_are_player_safe(self) -> None:
        script = (ROOT / "tools" / "behavior-dummy-client.py").read_text(encoding="utf-8")

        self.assertIn('DEFAULT_COMMANDS = ["/worldnews"]', script)
        self.assertNotIn('DEFAULT_COMMANDS = ["/mobgrowth status"', script)
        self.assertNotIn('"/worldai jobs"]', script)

    def test_worldai_smoke_reads_serverconfig_db_password(self) -> None:
        script = (ROOT / "tools" / "worldai-smoke-test.py").read_text(encoding="utf-8")

        self.assertIn("def read_serverconfig_password()", script)
        self.assertIn("read_serverconfig_password()", script)
        self.assertIn("CoreServer", script)
        self.assertIn("serverconfig.xml", script)


if __name__ == "__main__":
    unittest.main()
