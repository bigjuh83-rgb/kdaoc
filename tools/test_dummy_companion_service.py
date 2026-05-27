import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / "tools" / "dummy-companion-service.py"
SMOKE_PATH = ROOT / "tools" / "run-live-companion-party-smoke.py"
LIVE_COMPANION_POOL_PATH = ROOT / "tools" / "dummy-live-companions.csv"


def load_service():
    spec = importlib.util.spec_from_file_location("dummy_companion_service", SERVICE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_smoke():
    spec = importlib.util.spec_from_file_location("run_live_companion_party_smoke", SMOKE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DummyCompanionServiceTests(unittest.TestCase):
    def test_service_script_exists(self) -> None:
        self.assertTrue(SERVICE_PATH.exists())

    def test_live_companion_pool_has_realm_role_and_home_metadata(self) -> None:
        import csv

        self.assertTrue(LIVE_COMPANION_POOL_PATH.exists())
        with LIVE_COMPANION_POOL_PATH.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))

        self.assertTrue(rows)
        self.assertTrue({"username", "realm", "roles", "home_x", "home_y", "home_z"}.issubset(rows[0].keys()))
        self.assertTrue(any(row["realm"] == "1" and "healer" in row["roles"] for row in rows))
        self.assertTrue(any(row["realm"] == "2" and "tank" in row["roles"] for row in rows))
        self.assertTrue(any(row["realm"] == "3" and "dps" in row["roles"] for row in rows))

    def test_service_defaults_to_live_companion_pool(self) -> None:
        service = load_service()

        args = service.build_parser().parse_args(["--once"])

        self.assertEqual(Path(args.accounts_csv), LIVE_COMPANION_POOL_PATH)

    def test_service_accepts_max_runtime_for_smoke_runs(self) -> None:
        service = load_service()

        args = service.build_parser().parse_args(["--max-runtime", "30"])

        self.assertEqual(args.max_runtime, 30)

    def test_service_accepts_api_password_for_state_changing_routes(self) -> None:
        service = load_service()

        args = service.build_parser().parse_args(["--api-password", "secret"])

        self.assertEqual(args.api_password, "secret")

    def test_live_companion_roles_map_to_safe_rotations(self) -> None:
        service = load_service()

        self.assertEqual(service.normalize_role("healer"), "healer")
        self.assertEqual(service.normalize_role("weird"), "fill")
        self.assertEqual(service.role_to_rotation("healer"), "healer-support")
        self.assertEqual(service.role_to_rotation("support"), "healer-support")
        self.assertEqual(service.role_to_rotation("tank"), "melee-basic")
        self.assertEqual(service.role_to_rotation("dps"), "melee-burst")

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

    def test_real_player_join_release_request_uses_active_companion_priority(self) -> None:
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

        self.assertEqual(request_id, "dps-req")

    def test_real_player_join_release_credit_prevents_releasing_twice_for_one_player(self) -> None:
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
        self.assertIn("--party-external-member-names", command)
        self.assertIn("--party-assist-only", command)
        self.assertIn("--party-use-assist-command", command)
        self.assertIn("--party-follow-interval", command)
        self.assertEqual(command[command.index("--party-follow-distance") + 1], "450")
        self.assertIn("--waypoints", command)
        self.assertIn("111,222,333", command)
        self.assertIn("--flee-home", command)
        self.assertNotEqual(command[command.index("--flee-home") + 1], "111,222,333")
        self.assertIn("531504,479073,2200", command)
        self.assertIn("--flee-dynamic-safe-point", command)
        self.assertIn("--flee-safe-api-scout", command)
        self.assertIn("--flee-pressure-health-percent", command)
        self.assertIn("90", command)
        self.assertIn("--flee-safe-threat-radius", command)
        self.assertIn("6500", command)
        self.assertIn("--flee-safe-point-distance", command)
        self.assertIn("7000", command)
        self.assertIn("--use-skills", command)
        self.assertIn("--combat-usable-api", command)
        self.assertIn("--move", command)
        self.assertIn("--smooth-movement", command)
        self.assertIn("--combat-direct-move-distance", command)
        self.assertIn("--action-rotation", command)
        self.assertIn("healer-support", command)
        self.assertIn("--player-level", command)
        self.assertEqual(command[command.index("--player-level") + 1], "50")
        self.assertIn("--ideal-target-level", command)
        self.assertEqual(command[command.index("--ideal-target-level") + 1], "50")
        self.assertIn("--min-target-level", command)
        self.assertEqual(command[command.index("--min-target-level") + 1], "42")
        self.assertIn("--live-control-file", command)
        self.assertTrue(command[command.index("--live-control-file") + 1].endswith("live-control.json"))
        self.assertIn("--live-control-interval", command)
        self.assertEqual(command[command.index("--live-control-interval") + 1], "0.5")
        self.assertIn("--no-auto-loot", command)
        self.assertNotIn("--auto-loot", command)
        self.assertNotIn("--hunter", command)

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

    def test_request_companion_dialogue_disabled_does_not_call_gateway(self) -> None:
        service = load_service()
        args = mock.Mock(dialogue_enabled=False)

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(service, "call_ai_gateway") as gateway:
            written = service.request_companion_dialogue(args, {"event_type": "status"}, Path(temp_dir) / "live-control.json")

        self.assertFalse(written)
        gateway.assert_not_called()

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

    def test_api_request_adds_password_to_post_only(self) -> None:
        service = load_service()
        args = mock.Mock(api_url="http://127.0.0.1:5000", api_timeout=1.0, api_password="secret")
        response = mock.Mock()
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=None)
        response.read.return_value = b'{"ok": true}'

        with mock.patch.object(service.urllib.request, "urlopen", return_value=response) as urlopen:
            service.api_request(args, "POST", "/api/dummy/companions/requests/claim")

        request = urlopen.call_args.args[0]
        self.assertIn("password=secret", request.full_url)

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
        update_status.assert_called_once_with(args, "req1", "failed", "cannot spawn companion: requester dead")

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
        update_status.assert_any_call(args, "req1", "grouping", "live companion behavior client started; waiting for grouping")

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

    def test_stop_all_active_companions_cleans_processes_and_statuses(self) -> None:
        service = load_service()
        args = mock.Mock()
        process = mock.Mock()
        active = {"req1": service.ActiveCompanion({"id": "req1"}, process, account="companion1")}

        with mock.patch.object(service, "stop_companion") as stop_companion, mock.patch.object(
            service, "update_request_status"
        ) as update_status:
            service.stop_all_active_companions(args, active, "done")

        stop_companion.assert_called_once_with(process)
        update_status.assert_called_once_with(args, "req1", "completed", "done", "companion1")
        self.assertEqual(active, {})

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
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir)
            leader = smoke.build_leader_command(args, "dummy300", "Dummy300", case_dir)
            service = smoke.build_service_command(args, case_dir / "service")

        self.assertIn("--startup-delay", leader)
        self.assertEqual(leader[leader.index("--startup-delay") + 1], "45.0")
        self.assertIn("--party-size", leader)
        self.assertIn("--current-target-api-refresh", leader)
        self.assertIn("--command", leader)
        self.assertEqual(leader[leader.index("--command") + 1], "")
        self.assertIn("--max-runtime", service)
        self.assertEqual(service[service.index("--max-runtime") + 1], "120.0")
        self.assertIn("--accounts-csv", service)
        self.assertEqual(Path(service[service.index("--accounts-csv") + 1]), LIVE_COMPANION_POOL_PATH)

    def test_live_companion_party_smoke_extracts_request_id(self) -> None:
        smoke = load_smoke()

        self.assertEqual(smoke.request_id_from_payload({"request": {"id": "abc"}}), "abc")
        self.assertEqual(smoke.request_id_from_payload({"Request": {"Id": "def"}}), "def")

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
                "username,damage_done,healing_done,action_party_assist,action_party_follow\n"
                "companion,12,4,3,5\n",
                encoding="utf-8",
            )

            summary = smoke.summarize_encounters(root)

        self.assertEqual(summary["damage_done"], 12)
        self.assertEqual(summary["heal"], 4)
        self.assertEqual(summary["party_assist"], 3)
        self.assertEqual(summary["party_follow"], 5)

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

    def test_poll_active_stops_companion_when_requester_logs_out(self) -> None:
        service = load_service()
        args = mock.Mock()
        process = mock.Mock()
        process.poll.return_value = None
        active = {"req1": service.ActiveCompanion({"id": "req1", "requesterAccount": "leader1"}, process)}

        with mock.patch.object(service, "fetch_requester_state", return_value=None), mock.patch.object(
            service, "stop_companion"
        ) as stop_companion, mock.patch.object(service, "update_request_status") as update_status:
            service.poll_active(args, active)

        stop_companion.assert_called_once_with(process)
        update_status.assert_called_once_with(args, "req1", "completed", "requester offline; companion stopped")
        self.assertEqual(active, {})

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
        self.assertIn("req1:low_health", dialogue_state)
        self.assertEqual(request_dialogue.call_args.args[2], Path("runs") / "req1" / "live-control.json")

    def test_poll_active_releases_low_priority_companion_when_real_player_joins(self) -> None:
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

        detach.assert_called_once_with(args, "req1", "albdps")
        stop_companion.assert_called_once_with(process)
        update_status.assert_called_once_with(args, "req1", "completed", "real player joined; companion released", "albdps")
        self.assertEqual(active, {})
        self.assertEqual(release_counts["account:leader1"], 1)


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

        self.assertIn("동료 고용관", source)
        self.assertIn("파티 동료", source)
        self.assertIn("치유 동료", source)
        self.assertIn("방어 동료", source)
        self.assertIn("공격 동료", source)
        self.assertIn("동료 해산", source)
        self.assertIn("new HubPlacement(1, eRealm.Albion", source)
        self.assertIn("new HubPlacement(100, eRealm.Midgard", source)
        self.assertIn("new HubPlacement(200, eRealm.Hibernia", source)
        self.assertNotIn("더미", source)

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


if __name__ == "__main__":
    unittest.main()
