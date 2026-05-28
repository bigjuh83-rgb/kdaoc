import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / "tools" / "dummy-companion-service.py"
SMOKE_PATH = ROOT / "tools" / "run-live-companion-party-smoke.py"
SUMMARY_PATH = ROOT / "tools" / "summarize-live-companion-requests.py"
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

    def test_service_accepts_api_password_for_state_changing_routes(self) -> None:
        service = load_service()

        args = service.build_parser().parse_args(["--api-password", "secret"])

        self.assertEqual(args.api_password, "secret")

    def test_service_defaults_api_url_to_localhost_bridge(self) -> None:
        service = load_service()

        args = service.build_parser().parse_args(["--once"])

        self.assertEqual(args.api_url, "http://localhost:5000")

    def test_live_companion_smoke_defaults_api_url_to_localhost_bridge(self) -> None:
        smoke = load_smoke()

        args = smoke.build_parser().parse_args(["--dry-run"])

        self.assertEqual(args.api_url, "http://localhost:5000")

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
        self.assertIn("--party-require-leader-engaged", command)
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
        self.assertEqual(command[command.index("--required-target-tank-commit-health-percent") + 1], "25")
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
        self.assertIn("--follow-player-required-for-objective-move", command)
        self.assertNotIn("--follow-player-hold-allows-waypoint", command)
        self.assertIn("--party-external-member-names", command)
        self.assertIn("--party-assist-only", command)
        self.assertNotIn("--party-use-assist-command", command)
        self.assertIn("--party-follow-interval", command)
        self.assertEqual(command[command.index("--party-assist-interval") + 1], "0")
        self.assertEqual(command[command.index("--party-assist-attack-delay") + 1], "0")
        self.assertEqual(command[command.index("--party-follow-distance") + 1], "1800")
        self.assertIn("--boss-ranged-safe-distance", command)
        self.assertEqual(command[command.index("--boss-ranged-safe-distance") + 1], "3500")
        self.assertIn("--party-preengage-ranged-safe-distance", command)
        self.assertEqual(command[command.index("--party-preengage-ranged-safe-distance") + 1], "3500")
        self.assertIn("--hunter", command)
        self.assertIn("--waypoints", command)
        self.assertIn("111,222,333", command)
        self.assertEqual(command[command.index("--waypoint-stop-distance") + 1], "3500")
        self.assertIn("--required-target-home", command)
        self.assertEqual(command[command.index("--required-target-home") + 1], "111,222,333")
        self.assertEqual(command[command.index("--required-target-home-stop-distance") + 1], "3500")
        self.assertEqual(command[command.index("--required-target-home-hunt-distance") + 1], "3600")
        self.assertIn("--flee-home", command)
        self.assertNotEqual(command[command.index("--flee-home") + 1], "111,222,333")
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
        self.assertEqual(command[command.index("--party-heal-leader-health-percent") + 1], "95")
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
        self.assertIn("--boss-ranged-safe-distance", command)
        self.assertEqual(command[command.index("--boss-ranged-safe-distance") + 1], "1400")
        self.assertEqual(command[command.index("--party-preengage-ranged-safe-distance") + 1], "1500")
        self.assertEqual(command[command.index("--waypoint-stop-distance") + 1], "1500")
        self.assertEqual(command[command.index("--required-target-home-stop-distance") + 1], "1400")
        self.assertEqual(command[command.index("--required-target-home-hunt-distance") + 1], "3200")
        self.assertIn("--stationary-cast-actions", command)
        self.assertNotIn("--party-boss-non-tank-melee-backoff", command)

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
        self.assertEqual(command[command.index("--boss-ranged-safe-distance") + 1], "3500")
        self.assertIn("--party-preengage-ranged-safe-distance", command)
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
        update_status.assert_called_once_with(args, "req1", "failed", "cannot spawn companion: requester dead")

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
        update_status.assert_called_once_with(args, "req1", "failed", "cannot spawn companion: no companion accounts left")

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
        stop_companion.assert_called_once_with(leader_process)
        update_status.assert_has_calls(
            [
                mock.call(args, "active1", "completed", "leave request; companion released", "albdps"),
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

    def test_live_companion_party_smoke_resets_pool_to_staging_not_boss_center(self) -> None:
        smoke = load_smoke()
        args = smoke.build_parser().parse_args(["--dry-run", "--leader-account", "dummy300"])

        with mock.patch.object(smoke.growth, "reset_growth_characters") as reset:
            smoke.reset_live_accounts(args, "dummy300")

        start_point = reset.call_args.kwargs["start_point"]
        self.assertNotEqual(smoke.BARFOG_STAGING_HOME, smoke.BARFOG_HOME)
        self.assertEqual((start_point.x, start_point.y, start_point.z), smoke.BARFOG_STAGING_HOME)

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
        self.assertEqual(query["contentType"], "pve:moorlich")
        self.assertEqual(query["requestedCapabilities"], "speed_song|stealth")
        self.assertEqual((query["x"], query["y"], query["z"]), smoke.BARFOG_HOME)

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
                "username,damage_done,healing_done,action_party_assist,action_party_follow,action_live_control_say,action_death_detected\n"
                "companion,12,4,3,5,1,1\n",
                encoding="utf-8",
            )
            (root / "service" / "req" / "companion-encounters.jsonl").write_text(
                '{"event":"live_control_applied","actions":{"live_control_say":1},"command_count":1}\n',
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
        self.assertEqual(summary["dialogue_live_control"], 1)
        self.assertEqual(summary["dialogue_party"], 1)
        self.assertEqual(summary["dialogue_heal_priority"], 1)
        self.assertEqual(summary["dialogue_live_control_applied"], 1)
        self.assertEqual(summary["dialogue_live_control_say"], 2)
        self.assertEqual(summary["death"], 1)

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

    def test_live_companion_party_smoke_accepts_real_join_release_without_combat_activity(self) -> None:
        smoke = load_smoke()

        summary = {"damage_done": 0, "heal": 0, "party_assist": 0, "party_follow": 0}

        self.assertFalse(smoke.has_companion_activity(summary))
        self.assertTrue(smoke.release_completed({"req1": "completed"}))

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
        stop_companion.assert_called_once_with(process)
        update_status.assert_called_once_with(args, "req1", "completed", "party disbanded or companion removed; companion released", "albhealer")
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
        stop_companion.assert_called_once_with(process)
        update_status.assert_not_called()
        self.assertEqual(active, {})


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
        self.assertIn("동료 상태", source)
        self.assertIn("동료 요청 취소", source)
        self.assertIn("동료 해산", source)
        self.assertIn("ShowStatus", source)
        self.assertIn("CancelPending", source)
        self.assertIn("LatestForPlayer(player.Name)", source)
        self.assertIn("new HubPlacement(1, eRealm.Albion", source)
        self.assertIn("new HubPlacement(100, eRealm.Midgard", source)
        self.assertIn("new HubPlacement(200, eRealm.Hibernia", source)
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

        self.assertIn("동료 요청이 접수되었습니다.", combined)
        self.assertIn("동료 해산 요청이 접수되었습니다.", combined)
        self.assertIn("동료 서비스가 요청을 처리 중입니다.", combined)
        self.assertIn("동료가 파티에 합류했습니다.", combined)
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
        self.assertGreaterEqual(routes.count("RequireMutationAllowed(context)"), 9)

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
