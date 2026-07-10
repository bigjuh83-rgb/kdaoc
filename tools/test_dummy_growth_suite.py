#!/usr/bin/env python3
"""Unit checks for the dummy growth-suite runner."""

from __future__ import annotations

import csv
import dataclasses
import importlib.util
import json
import math
import sys
import tempfile
import urllib.parse
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def load_module():
    module_path = Path(__file__).with_name("dummy_growth_suite.py")
    spec = importlib.util.spec_from_file_location("run_dummy_growth_suite_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_hunting_ground_analyzer():
    module_path = Path(__file__).with_name("analyze-dummy-growth-hunting-grounds.py")
    spec = importlib.util.spec_from_file_location("analyze_dummy_growth_hunting_grounds_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_preservice_growth_case_supervisor():
    module_path = Path(__file__).with_name("run-preservice-growth-case-supervisor.py")
    spec = importlib.util.spec_from_file_location("run_preservice_growth_case_supervisor_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_equip_dummy_boss_gear():
    module_path = Path(__file__).with_name("equip-dummy-boss-gear.py")
    spec = importlib.util.spec_from_file_location("equip_dummy_boss_gear_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_provision_dummy_accounts():
    module_path = Path(__file__).with_name("provision-dummy-accounts.py")
    spec = importlib.util.spec_from_file_location("provision_dummy_accounts_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_live_monitor():
    module_path = Path(__file__).with_name("monitor-dummy-growth-live.py")
    spec = importlib.util.spec_from_file_location("monitor_dummy_growth_live_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


growth = load_module()
hunting_analyzer = load_hunting_ground_analyzer()
preservice_supervisor = load_preservice_growth_case_supervisor()
equip_gear = load_equip_dummy_boss_gear()
provision_accounts = load_provision_dummy_accounts()
live_monitor = load_live_monitor()


def route_point_inside_zone_config(route, zone_config: dict) -> bool:
    for zone in zone_config.get("zones", {}).values():
        world_x = int(zone["offset_x"]) * 8192
        world_y = int(zone["offset_y"]) * 8192
        world_width = int(zone.get("width", 8)) * 8192
        world_height = int(zone.get("height", 8)) * 8192

        if world_x <= route.x <= world_x + world_width and world_y <= route.y <= world_y + world_height:
            return True

    return False


class DummyGrowthSuiteTests(unittest.TestCase):
    def test_growth_carry_party_form_up_timeout_keeps_force_pull_enabled(self) -> None:
        self.assertEqual(growth.growth_party_form_up_timeout(5, 2, carry_tuning=True), "12")
        self.assertEqual(growth.growth_party_form_up_timeout(30, 8, carry_tuning=True), "12")
        self.assertEqual(growth.growth_party_form_up_timeout(5, 1, carry_tuning=False), "0")
        self.assertEqual(growth.growth_party_form_up_timeout(50, 8, level50_boss_party=True, carry_tuning=True), "45")

    def test_ungeared_carry_command_does_not_select_below_carry_reward_floor(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=150,
            safe_exit_max_seconds=90,
            safe_exit_recent_damage_grace=12,
            ramp_up=5,
            login_retries=12,
            login_retry_delay=5.0,
            api_port=5000,
            max_target_distance=6500.0,
            target_home_max_distance=10000.0,
            combat_home_leash_distance=10000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=2200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            startup_delay=4.0,
            growth_fast_travel="route-home",
            growth_allow_lower_xp_gear_farm=True,
            growth_allow_lower_xp_target_plan=False,
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=33,
            growth_route_level_override=5,
            growth_route_level_is_carry_target=True,
            growth_target_level_override=5,
            growth_target_plan_override=(5, 5, 0),
            case_name="duo-s150-hib-r001",
            growth_party_carry_level_offset=12,
            current_party_size=2,
            growth_equip_party_carry_gear=False,
            growth_party_carry_count=-1,
            growth_failure_target_memory=False,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["hib"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=30,
                party_size=2,
                current_level=5,
                path_graph=Path("graph.json"),
            )

        self.assertEqual(growth.growth_party_carry_reward_floor(args, 5, 2, "hib"), 5)
        self.assertEqual(command[command.index("--min-target-level") + 1], "5")
        self.assertEqual(command[command.index("--ideal-target-level") + 1], "5")
        self.assertEqual(command[command.index("--max-target-level") + 1], "5")
        self.assertEqual(command[command.index("--preferred-low-con-min-level") + 1], "5")

    def test_live_anchor_route_home_command_preserves_anchor_z(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=150,
            safe_exit_max_seconds=90,
            safe_exit_recent_damage_grace=12,
            ramp_up=5,
            login_retries=12,
            login_retry_delay=5.0,
            api_port=5000,
            max_target_distance=6500.0,
            target_home_max_distance=10000.0,
            combat_home_leash_distance=10000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=2200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            startup_delay=4.0,
            growth_fast_travel="route-home",
            growth_allow_lower_xp_gear_farm=True,
            growth_allow_lower_xp_target_plan=False,
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=33,
            growth_route_level_override=5,
            growth_route_level_is_carry_target=True,
            growth_target_level_override=5,
            growth_target_plan_override=(5, 5, 0),
            case_name="duo-s150-hib-r001",
            growth_party_carry_level_offset=12,
            current_party_size=2,
            growth_equip_party_carry_gear=False,
            growth_party_carry_count=-1,
            growth_failure_target_memory=False,
        )
        live_route = growth.route_point(
            5,
            350688,
            534196,
            4598,
            "water beetle collector",
            source="hunting-index",
            mob_level=5,
            live_anchor_z=True,
            startup_anchor=True,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            with mock.patch.object(growth, "select_growth_route_point", return_value=live_route), mock.patch.object(
                growth,
                "sample_route_z",
                return_value=3586,
            ):
                command = growth.build_behavior_command(
                    args=args,
                    realm=growth.REALMS["hib"],
                    accounts_csv=Path("accounts.csv"),
                    case_dir=case_dir,
                    segment_index=31,
                    party_size=2,
                    current_level=5,
                    path_graph=Path("graph.json"),
                )

        self.assertIn("--route-home-preserve-z", command)
        self.assertEqual(command[command.index("--required-target-home") + 1], "350688,534196,4598")
        self.assertEqual(command[command.index("--startup-route-home-after-services") + 1], "350688,534196,4598")

    def test_ungeared_carry_lower_xp_route_still_uses_reward_floor(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=150,
            safe_exit_max_seconds=90,
            safe_exit_recent_damage_grace=12,
            ramp_up=5,
            login_retries=12,
            login_retry_delay=5.0,
            api_port=5000,
            max_target_distance=6500.0,
            target_home_max_distance=10000.0,
            combat_home_leash_distance=10000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=2200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            startup_delay=4.0,
            growth_fast_travel="route-home",
            growth_allow_lower_xp_gear_farm=True,
            growth_allow_lower_xp_target_plan=True,
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=36,
            growth_route_level_override=5,
            growth_target_level_override=5,
            growth_target_plan_override=(4, 4, 0),
            case_name="duo-s150-hib-r001",
            growth_party_carry_level_offset=12,
            current_party_size=2,
            growth_equip_party_carry_gear=False,
            growth_party_carry_count=-1,
            growth_failure_target_memory=False,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["hib"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=30,
                party_size=2,
                current_level=5,
                path_graph=Path("graph.json"),
            )

        self.assertNotIn(
            command[command.index("--prefer-target-name") + 1],
            {"small freshwater crab", "mudman"},
        )
        self.assertTrue(getattr(args, "growth_route_level_is_carry_target", False))
        self.assertEqual(command[command.index("--min-target-level") + 1], "5")
        self.assertEqual(command[command.index("--ideal-target-level") + 1], "5")
        self.assertEqual(command[command.index("--max-target-level") + 1], "5")

    def test_ungeared_carry_replaces_below_floor_route_after_selection(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=150,
            safe_exit_max_seconds=90,
            safe_exit_recent_damage_grace=12,
            ramp_up=5,
            login_retries=12,
            login_retry_delay=5.0,
            api_port=5000,
            max_target_distance=6500.0,
            target_home_max_distance=10000.0,
            combat_home_leash_distance=10000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=2200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            startup_delay=4.0,
            growth_fast_travel="route-home",
            growth_allow_lower_xp_gear_farm=True,
            growth_allow_lower_xp_target_plan=True,
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=36,
            growth_route_level_override=5,
            growth_target_level_override=5,
            growth_target_plan_override=(4, 4, 0),
            case_name="duo-s150-hib-r001",
            growth_party_carry_level_offset=12,
            current_party_size=2,
            growth_equip_party_carry_gear=False,
            growth_party_carry_count=-1,
            growth_failure_target_memory=False,
        )
        low_route = growth.route_point(
            5,
            361545,
            491812,
            4662,
            "small freshwater crab",
            source="static-fallback",
            mob_level=0,
        )
        floor_route = growth.route_point(
            6,
            329667,
            470837,
            5616,
            "eirebug",
            source="hunting-index",
            mob_level=5,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            with mock.patch.object(growth, "select_growth_route_point", return_value=low_route), mock.patch.object(
                growth,
                "select_growth_hunting_index_point_for_target",
                return_value=floor_route,
            ):
                command = growth.build_behavior_command(
                    args=args,
                    realm=growth.REALMS["hib"],
                    accounts_csv=Path("accounts.csv"),
                    case_dir=case_dir,
                    segment_index=30,
                    party_size=2,
                    current_level=5,
                    path_graph=Path("graph.json"),
                )

        self.assertEqual(command[command.index("--prefer-target-name") + 1], "eirebug")
        self.assertEqual(command[command.index("--min-target-level") + 1], "5")

    def test_run_mysql_wraps_wsl_mysql_binary_on_windows(self) -> None:
        args = SimpleNamespace(
            mysql_bin="/home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb",
            db_password="secret",
            db_host="127.0.0.1",
            db_port=3306,
            db_user="root",
            db_name="opendaoc",
        )

        with mock.patch.object(growth.os, "name", "nt"), mock.patch.object(growth.subprocess, "run") as run:
            run.return_value = SimpleNamespace(stdout="ok")
            output = growth.run_mysql(args, "select 1")

        command = run.call_args.args[0]
        env = run.call_args.kwargs["env"]
        self.assertEqual(output, "ok")
        self.assertTrue(command[0].lower().endswith("wsl.exe"))
        self.assertIn("--exec", command)
        self.assertIn(args.mysql_bin, command)
        self.assertIn("MYSQL_PWD/u", env["WSLENV"])

    def test_equip_gear_run_mysql_wraps_wsl_mysql_binary_on_windows(self) -> None:
        args = SimpleNamespace(
            mysql_bin="/home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb",
            db_password="secret",
            db_host="127.0.0.1",
            db_port=3306,
            db_user="root",
            db_name="opendaoc",
        )

        with mock.patch.object(equip_gear.os, "name", "nt"), mock.patch.object(equip_gear.subprocess, "check_output") as check_output:
            check_output.return_value = "ok"
            output = equip_gear.run_mysql(args, "select 1")

        command = check_output.call_args.args[0]
        env = check_output.call_args.kwargs["env"]
        self.assertEqual(output, "ok")
        self.assertTrue(command[0].lower().endswith("wsl.exe"))
        self.assertIn("--exec", command)
        self.assertIn(args.mysql_bin, command)
        self.assertIn("MYSQL_PWD/u", env["WSLENV"])

    def test_provision_accounts_run_mysql_wraps_wsl_mysql_binary_on_windows(self) -> None:
        args = SimpleNamespace(
            mysql_bin="/home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb",
            db_password="secret",
            db_host="127.0.0.1",
            db_port=3306,
            db_user="root",
            db_name="opendaoc",
        )

        with mock.patch.object(provision_accounts.os, "name", "nt"), mock.patch.object(
            provision_accounts.subprocess, "run"
        ) as run:
            run.return_value = SimpleNamespace(stdout="ok")
            output = provision_accounts.run_mysql(args, "select 1")

        command = run.call_args.args[0]
        env = run.call_args.kwargs["env"]
        self.assertEqual(output, "ok")
        self.assertTrue(command[0].lower().endswith("wsl.exe"))
        self.assertIn("--exec", command)
        self.assertIn(args.mysql_bin, command)
        self.assertIn("MYSQL_PWD/u", env["WSLENV"])
        self.assertNotIn("-psecret", command)

    def test_growth_run_mysql_uses_defaults_file_for_windows_client_from_wsl(self) -> None:
        args = SimpleNamespace(
            mysql_bin="/mnt/d/mariadb/bin/mariadb.exe",
            db_password="secret",
            db_host="127.0.0.1",
            db_port=3306,
            db_user="root",
            db_name="opendaoc",
        )

        with mock.patch.object(growth.os, "name", "posix"), mock.patch.object(growth.subprocess, "run") as run:
            run.return_value = SimpleNamespace(stdout="ok")
            output = growth.run_mysql(args, "select 1")

        command = run.call_args.args[0]
        env = run.call_args.kwargs["env"]
        self.assertEqual(output, "ok")
        self.assertIn("--defaults-extra-file=", " ".join(command))
        self.assertNotIn("MYSQL_PWD", env)
        self.assertNotIn("secret", command)

    def test_equip_gear_run_mysql_uses_defaults_file_for_windows_client_from_wsl(self) -> None:
        args = SimpleNamespace(
            mysql_bin="/mnt/d/mariadb/bin/mariadb.exe",
            db_password="secret",
            db_host="127.0.0.1",
            db_port=3306,
            db_user="root",
            db_name="opendaoc",
        )

        with mock.patch.object(equip_gear.os, "name", "posix"), mock.patch.object(equip_gear.subprocess, "check_output") as check_output:
            check_output.return_value = "ok"
            output = equip_gear.run_mysql(args, "select 1")

        command = check_output.call_args.args[0]
        env = check_output.call_args.kwargs["env"]
        self.assertEqual(output, "ok")
        self.assertIn("--defaults-extra-file=", " ".join(command))
        self.assertNotIn("MYSQL_PWD", env)
        self.assertNotIn("secret", command)

    def test_provision_accounts_run_mysql_uses_defaults_file_for_windows_client_from_wsl(self) -> None:
        args = SimpleNamespace(
            mysql_bin="/mnt/d/mariadb/bin/mariadb.exe",
            db_password="secret",
            db_host="127.0.0.1",
            db_port=3306,
            db_user="root",
            db_name="opendaoc",
        )

        with mock.patch.object(provision_accounts.os, "name", "posix"), mock.patch.object(
            provision_accounts.subprocess, "run"
        ) as run:
            run.return_value = SimpleNamespace(stdout="ok")
            output = provision_accounts.run_mysql(args, "select 1")

        command = run.call_args.args[0]
        env = run.call_args.kwargs["env"]
        self.assertEqual(output, "ok")
        self.assertIn("--defaults-extra-file=", " ".join(command))
        self.assertNotIn("MYSQL_PWD", env)
        self.assertNotIn("secret", command)

    def test_provision_accounts_accepts_wsl_mysql_binary_on_windows(self) -> None:
        mysql_bin = "/home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb"

        with mock.patch.object(provision_accounts.os, "name", "nt"), mock.patch.object(
            provision_accounts.Path, "exists", return_value=False
        ), mock.patch.object(provision_accounts.subprocess, "run") as run:
            run.return_value = SimpleNamespace(returncode=0)
            self.assertTrue(provision_accounts.mysql_bin_available(mysql_bin))

        command = run.call_args.args[0]
        self.assertTrue(command[0].lower().endswith("wsl.exe"))
        self.assertEqual(command[1:4], ["--exec", "test", "-x"])
        self.assertEqual(command[4], mysql_bin)

    def test_command_for_metadata_redacts_all_password_flags(self) -> None:
        rendered = growth.command_for_metadata(
            [
                "python3",
                "tool.py",
                "--password",
                "login-secret",
                "--api-password",
                "api-secret",
                "--db-password",
                "db-secret",
                "--other",
                "visible",
            ]
        )

        self.assertIn("--password '***'", rendered)
        self.assertIn("--api-password '***'", rendered)
        self.assertIn("--db-password '***'", rendered)
        self.assertIn("visible", rendered)
        self.assertNotIn("login-secret", rendered)
        self.assertNotIn("api-secret", rendered)
        self.assertNotIn("db-secret", rendered)

    def test_money_to_copper_uses_daoc_coin_scale(self) -> None:
        row = {"Copper": "7", "Silver": "6", "Gold": "5", "Platinum": "4"}

        self.assertEqual(growth.money_to_copper(row), 40_050_607)

    def test_coin_parts_from_copper_uses_daoc_coin_scale(self) -> None:
        self.assertEqual(growth.coin_parts_from_copper(40_050_607), (7, 6, 5, 4))
        self.assertEqual(growth.coin_parts_from_copper(100), (0, 1, 0, 0))

    def test_alb_level_ten_solo_checkpoint_seeds_minimal_gear_copper(self) -> None:
        self.assertEqual(
            growth.checkpoint_seed_money_copper(
                SimpleNamespace(checkpoint_seed_copper=-1),
                10,
                1,
                "alb",
            ),
            100,
        )
        self.assertEqual(
            growth.checkpoint_seed_money_copper(
                SimpleNamespace(checkpoint_seed_copper=0),
                10,
                1,
                "alb",
            ),
            0,
        )
        self.assertEqual(
            growth.checkpoint_seed_money_copper(
                SimpleNamespace(checkpoint_seed_copper=-1),
                10,
                1,
                "mid",
            ),
            0,
        )

    def test_inventory_category_summary_splits_weapon_armor_and_junk(self) -> None:
        items = [
            growth.InventoryItem("acct", 40, "sword", "Sword", 1, 10, 30, 3, 10, 100, 0, "", 1, 12),
            growth.InventoryItem("acct", 41, "vest", "Vest", 1, 10, 0, 33, 25, 100, 0, "", 1, 9),
            growth.InventoryItem("acct", 42, "bone", "Bone", 1, 0, 0, 0, 0, 0, 0, "", 3, 2),
        ]

        summary = growth.inventory_category_summary(items)

        self.assertEqual(summary["weapon_items"], 1)
        self.assertEqual(summary["armor_items"], 1)
        self.assertEqual(summary["junk_items"], 3)
        self.assertEqual(summary["zero_value_junk_items"], 0)
        self.assertEqual(summary["sellable_junk_items"], 3)
        self.assertEqual(summary["sellable_junk_value_copper"], 6)
        self.assertEqual(summary["total_sell_value_copper"], 27)

    def test_target_levels_scale_with_party_size(self) -> None:
        self.assertEqual(growth.target_levels(1, 1), (0, 0, 1))
        self.assertEqual(growth.target_levels(1, 2), (1, 1, 0))
        self.assertEqual(growth.target_levels(1, 4), (1, 1, 0))
        self.assertEqual(growth.target_levels(1, 8), (1, 1, 0))
        self.assertEqual(growth.target_levels(1, 2, "mid"), (1, 1, 0))
        self.assertEqual(growth.target_levels(1, 4, "mid"), (1, 1, 0))
        self.assertEqual(growth.target_levels(1, 4, "hib"), (1, 1, 0))
        self.assertEqual(growth.target_levels(1, 8, "hib"), (1, 1, 0))
        self.assertEqual(growth.target_levels(3, 1), (2, 2, 0))
        self.assertEqual(growth.target_levels(3, 2), (2, 2, 0))
        self.assertEqual(growth.target_levels(3, 2, "hib"), (2, 3, 1))
        self.assertEqual(growth.target_levels(3, 4), (2, 3, 0))
        self.assertEqual(growth.target_levels(3, 8), (2, 3, 0))
        self.assertEqual(growth.target_levels(4, 1), (2, 2, 0))
        self.assertEqual(growth.target_levels(5, 1), (2, 2, 0))
        self.assertEqual(growth.target_levels(5, 1, "alb"), (3, 3, 0))
        self.assertEqual(growth.target_levels(5, 1, "mid"), (3, 3, 0))
        self.assertEqual(growth.target_levels(5, 1, "hib"), (4, 4, 0))
        self.assertEqual(growth.target_levels(5, 2), (4, 4, 0))
        self.assertEqual(growth.target_levels(5, 2, "mid"), (4, 5, 1))
        self.assertEqual(growth.target_levels(5, 4, "mid"), (4, 5, 1))
        self.assertEqual(growth.target_levels(6, 2), (4, 4, 0))
        self.assertEqual(growth.target_levels(6, 2, "mid"), (4, 5, 1))
        self.assertEqual(growth.target_levels(6, 2, "alb"), (5, 6, 1))
        self.assertEqual(growth.target_levels(7, 2), (5, 5, 0))
        self.assertEqual(growth.target_levels(7, 2, "alb"), (5, 6, 1))
        self.assertEqual(growth.target_levels(7, 2, "mid"), (5, 6, 1))
        self.assertEqual(growth.target_levels(6, 4), (5, 5, 0))
        self.assertEqual(growth.target_levels(6, 4, "mid"), (4, 5, 1))
        self.assertEqual(growth.target_levels(6, 4, "alb"), (5, 5, 0))
        self.assertEqual(growth.target_levels(6, 1), (4, 4, 0))
        self.assertEqual(growth.target_levels(6, 1, "alb"), (4, 4, 0))
        self.assertEqual(growth.target_levels(6, 1, "mid"), (4, 4, 0))
        self.assertEqual(growth.target_levels(6, 1, "hib"), (4, 4, 0))
        self.assertEqual(growth.target_levels(7, 1), (6, 6, 0))
        self.assertEqual(growth.target_levels(7, 1, "mid"), (6, 6, 0))
        self.assertEqual(growth.target_levels(8, 1, "mid"), (6, 7, 1))
        self.assertEqual(growth.target_levels(10, 1, "mid"), (7, 7, 0))
        self.assertEqual(growth.target_levels(8, 1), (6, 6, 0))
        self.assertEqual(growth.target_levels(8, 1, "alb"), (6, 6, 0))
        self.assertEqual(growth.target_levels(9, 1, "alb"), (7, 7, 0))
        self.assertEqual(growth.target_levels(9, 1, "mid"), (7, 8, 1))
        self.assertEqual(growth.target_levels(10, 1), (7, 8, 1))
        self.assertEqual(growth.target_levels(8, 8, "hib"), (8, 8, 1))
        self.assertEqual(growth.target_levels(9, 1, "hib"), (6, 6, 0))
        self.assertEqual(growth.target_levels(20, 2), (19, 21, 2))
        self.assertEqual(growth.target_levels(20, 4), (19, 22, 3))
        self.assertEqual(growth.target_levels(49, 8), (48, 50, 5))

    def test_level_one_party_growth_index_skips_zero_level_camps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "alb,4,1,0,0,1,small snake,0,40,567325,508906,2626,40,0,0,0,Bind Start,1000,999\n"
                "alb,4,1,1,2,2,black wolf pup,2,12,525876,471818,2236,12,0,0,0,Bind Start,1000,100\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 1, 4)

        self.assertEqual(route.prefer, "black wolf pup")
        self.assertEqual(route.mob_level, 2)

    def test_party_carry_growth_index_skips_upper_edge_above_ideal_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,2,10,8,9,10,shadow,10,10,712749,792535,4650,0,200,200,500,Huginfell,5317,999\n"
                "mid,2,10,8,9,10,envy drakeling,9,12,758411,871134,4877,0,50,51,500,Gotar,36742,100\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_allow_lower_xp_target_plan=False,
            )

            index = growth.load_growth_hunting_index(args)
            routes = index[("mid", 2, 10)]

        self.assertEqual([route.prefer for route in routes], ["envy drakeling"])
        self.assertEqual(routes[0].mob_level, 9)

    def test_party_carry_target_index_skips_upper_edge_above_ideal_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,2,10,8,9,10,shadow,10,10,712749,792535,4650,0,200,200,500,Huginfell,5317,999\n"
                "mid,2,10,8,9,10,envy drakeling,9,12,758411,871134,4877,0,50,51,500,Gotar,36742,100\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=21,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_allow_lower_xp_target_plan=False,
            )

            route = growth.select_growth_hunting_index_point_for_target(
                args,
                "mid",
                9,
                2,
                caller_player_level=10,
            )

        self.assertIsNotNone(route)
        self.assertEqual(route.prefer, "envy drakeling")
        self.assertEqual(route.mob_level, 9)

    def test_party_carry_live_discovery_skips_upper_edge_source_route(self) -> None:
        args = SimpleNamespace(
            growth_route_preflight=True,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            live_api_url="http://dummy-api:5000",
            api_port=5000,
        )
        source_candidates = [
            (
                0,
                0,
                -10.0,
                1,
                10,
                growth.route_point(
                    10,
                    712749,
                    792535,
                    4650,
                    "shadow",
                    "",
                    "Huginfell",
                    source="hunting-index",
                    mob_level=10,
                    mob_count=10,
                ),
            )
        ]

        with mock.patch.object(growth, "fetch_growth_route_preflight_payload") as fetch:
            selected = growth.select_live_growth_preflight_candidate_route(
                args,
                growth.REALMS["mid"],
                source_candidates,
                realm_key="mid",
                target_level=9,
                current_level=10,
                caller_level=10,
                party_size=2,
            )

        self.assertIsNone(selected)
        fetch.assert_not_called()

    def test_level_one_duo_growth_index_allows_zero_level_safe_camp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "alb,2,1,0,0,1,green snake,0,40,532542,476345,2317,40,0,0,0,Bind Start,1000,999\n"
                "alb,2,1,1,1,1,boar piglet,1,12,525876,471818,2236,12,0,0,0,Bind Start,1000,100\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 1, 2)
            adjusted = growth.adjust_growth_target_plan_for_required_route(
                route,
                current_level=1,
                party_size=2,
                realm_key="alb",
                min_target=1,
                ideal_target=1,
                max_delta=0,
            )

        self.assertEqual(route.prefer, "green snake")
        self.assertEqual(route.mob_level, 0)
        self.assertEqual(adjusted, (0, 1, 0))

    def test_hib_level_one_small_party_avoids_large_frog(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "hib,1,1,0,0,1,large frog,0,31,343544,473889,5349,31,0,0,0,Bind Start,1000,999\n"
                "hib,1,1,0,0,1,water beetle larva,0,31,344422,591538,5107,31,0,0,0,Bind Start,1000,100\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["hib"], 1, 1)

        self.assertEqual(route.prefer, "water beetle larva")
        self.assertNotIn("large frog", growth.preferred_growth_hunting_candidates("hib", 1, 1))
        self.assertIn("large frog", growth.growth_hunting_index_avoid_targets("hib", 1, 1))
        self.assertNotIn("water beetle larva", growth.growth_hunting_index_avoid_targets("hib", 1, 1))

    def test_hib_duo_level_six_avoid_targets_include_orchard_nipper(self) -> None:
        avoid_targets = growth.growth_hunting_index_avoid_targets("hib", 6, 2)

        self.assertIn("orchard nipper", avoid_targets)
        self.assertIn("blackthorn", avoid_targets)

    def test_level_one_party8_growth_index_falls_back_when_party_camps_are_too_high(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "hib,8,1,1,4,7,spraggon,4,40,327727,467546,5441,40,0,0,0,Bind Start,1000,999\n"
                "hib,0,1,1,3,3,water beetle larva,3,18,344888,473348,5366,18,0,0,0,Bind Start,1000,100\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["hib"], 1, 8)

        self.assertEqual(route.prefer, "water beetle larva")
        self.assertEqual(route.mob_level, 3)

    def test_hib_party8_level_one_prefers_safe_xp_targets(self) -> None:
        self.assertEqual(growth.target_levels(1, 8, "hib"), (1, 1, 0))
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("hib", 1, 8),
            ("water beetle larva",),
        )
        avoid_targets = growth.growth_hunting_index_avoid_targets("hib", 1, 8)
        self.assertIn("large frog", avoid_targets)
        self.assertIn("skeletal pawn", avoid_targets)
        self.assertIn("badger cub", avoid_targets)
        self.assertNotIn("water beetle larva", avoid_targets)
        static_route = growth.select_route_point(growth.REALMS["hib"], 1, 8)
        self.assertEqual(static_route.prefer, "water beetle larva")
        self.assertGreater(static_route.y, 580000)
        self.assertNotIn("large frog", static_route.prefer)

    def test_alb_party8_level_one_avoids_level_two_starter_camps(self) -> None:
        self.assertEqual(growth.target_levels(1, 8, "alb"), (1, 1, 0))
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("alb", 1, 8),
            ("black wolf pup", "boar piglet", "green snake"),
        )
        avoid_targets = growth.growth_hunting_index_avoid_targets("alb", 1, 8)
        self.assertIn("skeleton", avoid_targets)
        self.assertIn("spriggarn", avoid_targets)
        self.assertNotIn("black wolf pup", avoid_targets)

    def test_level_one_party8_growth_index_falls_back_after_preflight_rejects_party_camp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "hib,8,1,1,3,3,party camp,3,31,344206,473348,5366,31,0,0,0,Bind Start,1000,999\n"
                "hib,4,1,1,3,3,fallback camp,3,20,346223,472373,5919,20,0,0,0,Bind Start,1000,100\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_preflight=True,
            )

            def fake_preflight_filter(
                filter_args: object,
                route_candidates: list[growth.RoutePoint],
                *,
                realm: growth.RealmProfile,
                current_level: int,
                party_size: int,
            ) -> list[growth.RoutePoint]:
                del filter_args, realm, current_level, party_size
                return [candidate for candidate in route_candidates if candidate.prefer == "fallback camp"]

            with mock.patch.object(
                growth,
                "growth_route_preflight_filter_routes",
                side_effect=fake_preflight_filter,
            ) as preflight_filter:
                route = growth.select_growth_route_point(args, growth.REALMS["hib"], 1, 8)

        self.assertEqual(route.prefer, "fallback camp")
        self.assertNotEqual(route.prefer, "party camp")
        self.assertGreaterEqual(preflight_filter.call_count, 1)

    def test_hib_level_one_party8_preflight_uses_tighter_hazard_radius(self) -> None:
        args = SimpleNamespace(growth_route_preflight_hazard_radius=2500)

        self.assertEqual(
            growth.growth_route_preflight_hazard_radius(
                args,
                realm_key="hib",
                current_level=1,
                party_size=8,
            ),
            800,
        )
        self.assertEqual(
            growth.growth_route_preflight_hazard_radius(
                args,
                realm_key="hib",
                current_level=2,
                party_size=8,
            ),
            2500,
        )
        self.assertEqual(
            growth.growth_route_preflight_hazard_radius(
                args,
                realm_key="mid",
                current_level=1,
                party_size=8,
            ),
            5200,
        )
        self.assertEqual(
            growth.growth_route_preflight_hazard_radius(
                args,
                realm_key="mid",
                current_level=6,
                party_size=8,
            ),
            2500,
        )

    def test_mid_party8_low_carry_preflight_prioritizes_wood_eater_hazards(self) -> None:
        route = growth.RoutePoint(
            1,
            786637,
            723034,
            4722,
            "wood-eater worker",
            "hill person,young grendelorm,vein spider",
            "Mularn",
            source="hunting-index",
            mob_level=4,
        )

        hazard_tokens = growth.growth_route_preflight_hazard_tokens(
            route,
            realm_key="mid",
            current_level=4,
            party_size=8,
        )

        self.assertEqual(hazard_tokens[:4], (
            "wood-eater hunter",
            "wood-eater soldier",
            "wood-eater royal guard",
            "young grendelorm",
        ))
        self.assertNotIn("wood-eater worker", hazard_tokens)
        self.assertIn("wood-eater hunter", growth.growth_hunting_index_avoid_targets("mid", 4, 8))
        self.assertIn("young grendelorm", growth.growth_hunting_index_avoid_targets("mid", 4, 8))

    def test_route_preflight_hazard_tokens_skip_generic_growth_prefix_names(self) -> None:
        route = growth.route_point(
            8,
            774600,
            858572,
            4864,
            "tawny lynx",
            "",
            "Vasudheim",
            source="hunting-index",
            mob_level=8,
        )

        hazard_tokens = growth.growth_route_preflight_hazard_tokens(
            route,
            realm_key="mid",
            current_level=10,
            party_size=2,
        )

        self.assertNotIn("노련한", hazard_tokens)
        self.assertNotIn("돌연변이", hazard_tokens)
        self.assertNotIn("champion", hazard_tokens)
        self.assertIn("small hill cat", hazard_tokens)
        self.assertIn("host of the wind", hazard_tokens)

    def test_route_preflight_does_not_reject_anchor_for_generic_growth_prefix_hazard(self) -> None:
        args = SimpleNamespace(
            growth_fast_travel="route-home",
            growth_route_preflight=True,
            growth_route_preflight_anchor=True,
            growth_route_preflight_timeout=0.1,
            growth_route_preflight_radius=6500,
            growth_route_preflight_low_solo_radius=2500,
            growth_route_preflight_limit=3,
            growth_route_preflight_min_available_targets=1,
            growth_route_preflight_hazard_radius=2500,
            growth_route_preflight_hazard_limit=3,
            growth_route_preflight_hazard_token_limit=12,
            growth_route_level_is_carry_target=True,
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            dry_run=False,
            nav_api_url="http://dummy-api:5000",
            host="127.0.0.1",
            api_port=5000,
            max_target_distance=6500.0,
            run_dir="",
        )
        route = growth.route_point(
            8,
            775404,
            870474,
            5306,
            "nordic dirge",
            "노련한,돌연변이,small hill cat",
            "Vasudheim",
            source="hunting-index",
            mob_level=8,
            mob_count=7,
        )
        queried_hazards: list[str] = []

        def fake_preflight(url: str, timeout: float) -> object:
            del timeout
            query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            name = (query.get("name") or [""])[0]
            if name == "nordic dirge":
                return [
                    {
                        "name": "nordic dirge",
                        "level": 8,
                        "x": 775404,
                        "y": 870474,
                        "z": 5306,
                        "healthPercent": 100,
                    }
                ]
            queried_hazards.append(name)
            if name == "노련한":
                return [
                    {
                        "name": "노련한 haunt",
                        "level": 9,
                        "x": 775900,
                        "y": 870900,
                        "z": 5300,
                    }
                ]
            return []

        with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
            checked = growth.growth_route_preflight_checked_route(
                args,
                route,
                realm=growth.REALMS["mid"],
                current_level=10,
                party_size=2,
            )

        self.assertIsNotNone(checked)
        self.assertNotIn("노련한", queried_hazards)
        self.assertIn("small hill cat", queried_hazards)

    def test_same_base_growth_prefix_filter_matches_runtime_nearby_radius(self) -> None:
        available_items = (
            {"name": "rock crab", "x": 10000, "y": 10000},
            {"name": "rock crab", "x": 10100, "y": 10000},
        )
        raw_items = available_items + (
            {"name": "노련한 rock crab", "x": 12250, "y": 10000},
        )

        runtime_safe_items, runtime_prefix_items = growth.growth_route_preflight_filter_same_base_growth_prefix_pressure(
            "rock crab",
            available_items,
            raw_items,
            radius=1800,
        )
        hazard_safe_items, hazard_prefix_items = growth.growth_route_preflight_filter_same_base_growth_prefix_pressure(
            "rock crab",
            available_items,
            raw_items,
            radius=2500,
        )

        self.assertEqual(runtime_safe_items, available_items)
        self.assertEqual(len(runtime_prefix_items), 0)
        self.assertEqual(hazard_safe_items, ())
        self.assertEqual(len(hazard_prefix_items), 1)

    def test_route_preflight_target_query_uses_runtime_nearby_avoid_names(self) -> None:
        args = SimpleNamespace(
            growth_fast_travel="route-home",
            growth_route_preflight=True,
            growth_route_preflight_anchor=True,
            growth_route_preflight_timeout=0.1,
            growth_route_preflight_radius=6500,
            growth_route_preflight_low_solo_radius=2500,
            growth_route_preflight_limit=3,
            growth_route_preflight_min_available_targets=1,
            growth_route_preflight_hazard_radius=2500,
            growth_route_preflight_hazard_limit=3,
            growth_route_preflight_hazard_token_limit=12,
            growth_route_level_is_carry_target=True,
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            dry_run=False,
            nav_api_url="http://dummy-api:5000",
            host="127.0.0.1",
            api_port=5000,
            max_target_distance=6500.0,
            run_dir="",
        )
        route = growth.route_point(
            8,
            775404,
            870474,
            5306,
            "nordic dirge",
            "ghost light",
            "Vasudheim",
            source="hunting-index",
            mob_level=8,
            mob_count=7,
        )
        target_queries: list[dict[str, list[str]]] = []
        hazard_queries: list[dict[str, list[str]]] = []

        def fake_preflight(url: str, timeout: float) -> object:
            del timeout
            query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            name = (query.get("name") or [""])[0]
            if name == "nordic dirge":
                target_queries.append(query)
                return [
                    {
                        "name": "nordic dirge",
                        "level": 8,
                        "x": 775404,
                        "y": 870474,
                        "z": 5306,
                        "healthPercent": 100,
                        "nearbyAvoidCount": 0,
                    }
                ]
            hazard_queries.append(query)
            return []

        with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
            checked = growth.growth_route_preflight_checked_route(
                args,
                route,
                realm=growth.REALMS["mid"],
                current_level=10,
                party_size=2,
            )

        self.assertIsNotNone(checked)
        self.assertTrue(target_queries)
        self.assertIn("ghost light", (target_queries[0].get("nearbyAvoidName") or [""])[0])
        self.assertEqual((target_queries[0].get("nearbyRadius") or [""])[0], "1800")
        self.assertTrue(hazard_queries)
        self.assertEqual((hazard_queries[0].get("radius") or [""])[0], "1800")

    def test_no_lower_xp_gear_farm_enforces_effective_xp_targets(self) -> None:
        args = SimpleNamespace(growth_allow_lower_xp_gear_farm=False)

        self.assertEqual(growth.enforce_no_lower_xp_target_plan(args, 7, 4, 5, 5, 0), (5, 5, 0))
        self.assertEqual(growth.enforce_no_lower_xp_target_plan(args, 9, 4, 8, 8, 0), (8, 8, 0))
        self.assertEqual(growth.enforce_no_lower_xp_target_plan(args, 5, 1, 3, 3, 0, "mid"), (3, 3, 0))
        self.assertEqual(growth.enforce_no_lower_xp_target_plan(args, 9, 1, 7, 8, 1, "mid"), (7, 8, 1))
        self.assertEqual(growth.enforce_no_lower_xp_target_plan(args, 11, 1, 7, 8, 1, "hib"), (11, 11, 1))
        growth.validate_growth_target_plan(
            realm_key="mid",
            current_level=5,
            party_size=1,
            route_level=5,
            min_target=5,
            ideal_target=5,
            max_delta=0,
        )

    def test_no_lower_xp_solo_route_rejects_low_alb_level_eight_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "alb,1,8,5,5,6,emerald snake,5,30,489093,599432,1196,30,0,0,0,Campacorentin Station,1200,999\n"
                "alb,1,8,8,8,9,bear,8,10,575246,547179,2594,10,0,0,0,Prydwen Keep,1200,400\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_allow_lower_xp_gear_farm=False,
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=False,
                case_name="solo-s150-r2-alb-r001",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 8, 1)

        self.assertEqual(route.prefer, "rot worm")
        self.assertEqual(route.level, 8)
        self.assertEqual(route.mob_level, 6)

    def test_no_lower_xp_solo_routes_avoid_known_los_or_death_traps(self) -> None:
        args = SimpleNamespace(
            growth_allow_lower_xp_gear_farm=False,
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=16,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
            case_name="solo-route-trap-check",
        )

        hib_route = growth.select_growth_route_point(args, growth.REALMS["hib"], 7, 1)
        mid_route = growth.select_growth_route_point(args, growth.REALMS["mid"], 9, 1)
        alb_route = growth.select_growth_route_point(args, growth.REALMS["alb"], 8, 1)

        self.assertNotEqual(hib_route.prefer, "water beetle")
        self.assertNotEqual(mid_route.prefer, "wind wisp")
        self.assertNotEqual(alb_route.prefer, "devout filidh")

    def test_live_scan_empty_solo_routes_skip_known_empty_camps(self) -> None:
        alb_args = SimpleNamespace(
            growth_allow_lower_xp_gear_farm=True,
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=17,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
            case_name="solo-s150-r2-alb-r002",
        )
        alb_official_retry_args = SimpleNamespace(
            growth_allow_lower_xp_gear_farm=True,
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=22,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
            case_name="solo-s150-r2-alb-r002",
        )
        mid_level_nine_args = SimpleNamespace(
            growth_allow_lower_xp_gear_farm=True,
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=19,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
            case_name="solo-s150-r2-mid-r001",
        )
        mid_level_seven_args = SimpleNamespace(
            growth_allow_lower_xp_gear_farm=True,
            growth_allow_lower_xp_target_plan=True,
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=19,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
            case_name="solo-s150-r2-mid-r002",
        )

        alb_route = growth.select_growth_route_point(alb_args, growth.REALMS["alb"], 8, 1)
        alb_retry_route = growth.select_growth_route_point(alb_official_retry_args, growth.REALMS["alb"], 8, 1)
        mid_level_nine_route = growth.select_growth_route_point(mid_level_nine_args, growth.REALMS["mid"], 9, 1)
        mid_level_seven_route = growth.select_growth_route_point(mid_level_seven_args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(alb_route.prefer, "undead filidh")
        self.assertNotEqual(alb_route.prefer, "young cutpurse")
        self.assertNotEqual(alb_retry_route.prefer, "young cutpurse")
        self.assertNotEqual(mid_level_nine_route.prefer, "wind wisp")
        self.assertEqual(mid_level_nine_route.prefer, "ghost light")
        self.assertEqual(growth.strict_route_target_name(mid_level_nine_route, 9, 1, "mid"), "ghost light")
        self.assertIn("hill person", mid_level_nine_route.avoid)
        self.assertEqual(mid_level_seven_route.prefer, "carrion crawler")
        self.assertNotEqual(mid_level_seven_route.prefer, "wolf spiderling")
        self.assertLessEqual(mid_level_seven_route.level, 7)

    def test_lower_xp_gear_farm_preserves_legacy_targets(self) -> None:
        args = SimpleNamespace(growth_allow_lower_xp_gear_farm=True)

        self.assertEqual(growth.enforce_no_lower_xp_target_plan(args, 7, 4, 5, 5, 0), (5, 5, 0))

    def test_official_carry_routes_skip_known_no_progress_targets(self) -> None:
        args = SimpleNamespace(
            growth_allow_lower_xp_gear_farm=True,
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=30,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            case_name="duo-s150-alb-r001",
        )

        alb_route = growth.select_growth_route_point(args, growth.REALMS["alb"], 6, 2)
        self.assertEqual(alb_route.prefer, "rot worm")
        self.assertIn("dappled lynx cub", alb_route.avoid)

        args.growth_route_case_index = 25
        args.case_name = "duo-s150-hib-r001"
        hib_route = growth.select_growth_route_point(args, growth.REALMS["hib"], 9, 2)
        self.assertEqual(hib_route.prefer, "water beetle")
        self.assertIn("lough wolf", hib_route.avoid)

    def test_mid_duo_low_carry_route_uses_verified_worker_cluster(self) -> None:
        args = SimpleNamespace(
            growth_allow_lower_xp_gear_farm=True,
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=11,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            case_name="duo-s150-mid-r001",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 5, 2)

        self.assertEqual(route.prefer, "wood-eater worker")
        self.assertEqual((route.x, route.y, route.z), (786637, 723034, 4722))
        self.assertEqual(route.mob_level, 4)
        self.assertNotEqual((route.x, route.y), (810920, 726686))

    def test_buy_shortage_recovery_uses_previous_safe_solo_band(self) -> None:
        args = SimpleNamespace(growth_allow_lower_xp_gear_farm=True)

        self.assertEqual(
            growth.growth_shortage_recovery_route_override(
                args,
                growth.REALMS["alb"],
                current_level=9,
                party_size=1,
                item_plans={"growthalb": growth.GrowthItemPlan([], [], buy_shortage_copper=2278)},
            ),
            (8, 6),
        )
        self.assertEqual(
            growth.growth_shortage_recovery_route_override(
                args,
                growth.REALMS["alb"],
                current_level=8,
                party_size=1,
                item_plans={"growthalb": growth.GrowthItemPlan([], [], buy_shortage_copper=60)},
            ),
            (8, 6),
        )
        self.assertEqual(
            growth.growth_shortage_recovery_route_override(
                args,
                growth.REALMS["mid"],
                current_level=7,
                party_size=1,
                item_plans={"growthmid": growth.GrowthItemPlan([], [], buy_shortage_copper=473)},
            ),
            (7, 5),
        )
        self.assertEqual(
            growth.growth_shortage_recovery_route_override(
                args,
                growth.REALMS["hib"],
                current_level=7,
                party_size=1,
                item_plans={"growthhib": growth.GrowthItemPlan([], [], buy_shortage_copper=473)},
            ),
            (7, 5),
        )
        self.assertEqual(
            growth.growth_shortage_recovery_route_override(
                args,
                growth.REALMS["hib"],
                current_level=9,
                party_size=1,
                item_plans={"growthhib": growth.GrowthItemPlan([], [], buy_shortage_copper=712)},
            ),
            (8, 8),
        )

    def test_hib_level_three_solo_does_not_force_large_frogs(self) -> None:
        self.assertEqual(growth.target_levels(1, 1), (0, 0, 1))
        self.assertEqual(growth.target_levels(1, 1, "hib"), (0, 0, 1))
        self.assertEqual(growth.target_levels(2, 1), (1, 1, 0))
        self.assertEqual(growth.target_levels(2, 1, "hib"), (1, 1, 0))
        self.assertEqual(growth.target_levels(3, 1), (2, 2, 0))
        self.assertEqual(growth.target_levels(3, 1, "hib"), (1, 1, 0))

        for level in (2, 3):
            with self.subTest(level=level):
                route = growth.select_route_point(growth.REALMS["hib"], level=level, party_size=1)

                self.assertIn("badger cub", route.prefer)
                self.assertIn("large frog", route.prefer)
                self.assertIn("annoying lucradan", route.prefer)
                self.assertNotIn("skeletal pawn", route.prefer)
                self.assertIn("water beetle larva", route.avoid)
                self.assertEqual(
                    growth.strict_route_target_name(route, level, party_size=1, realm_key="hib"),
                    "",
                )

    def test_hib_level_one_growth_index_prefers_weaker_badger_cubs(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("hib", 1, 1),
            ("water beetle larva", "annoying lucradan", "badger cub"),
        )

    def test_hib_level_three_growth_index_prefers_weaker_level_one_targets(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("hib", 3, 1),
            ("water beetle larva", "skeletal pawn", "large frog", "sand crab"),
        )
        route = growth.RoutePoint(0, 0, 0, 200, "water beetle larva", "")
        self.assertEqual(
            growth.strict_route_target_name(route, 3, party_size=1, realm_key="hib"),
            "water beetle larva",
        )

    def test_hib_level_four_growth_index_prefers_safe_level_two_targets(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("hib", 4, 1),
            ("lough wolf cadger", "haunted driftwood", "skeletal pawn", "minor changeling", "beach rat", "mudman"),
        )
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
        )
        route = growth.select_growth_route_point(args, growth.REALMS["hib"], 4, 1)

        self.assertEqual(route.level, 4)
        self.assertEqual(route.prefer, "lough wolf cadger")
        distance_args = SimpleNamespace(max_target_distance=1500)
        self.assertEqual(growth.growth_max_target_distance(distance_args, 4, 1, "hib", route), 6500.0)

    def test_mid_party8_level_five_growth_index_prefers_visible_dense_route(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("mid", 5, 8),
            ("carrion crawler", "ghost light", "army ant soldier", "wind wisp"),
        )

    def test_mid_party8_level_seven_uses_lake_serpent_carry_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 8)

        self.assertEqual(route.level, 10)
        self.assertEqual(route.prefer, "lake serpent")
        self.assertEqual((route.x, route.y, route.z), (713945, 769705, 4191))
        self.assertEqual(growth.growth_hunter_target_max_ground_z_delta(7, 8, "mid"), 500)
        self.assertIn("wind wisp", route.avoid)
        self.assertIn("ghost light", route.avoid)
        self.assertIn("ghost light", route.avoid)
        self.assertIn("seithr orb", route.avoid)

    def test_hib_party4_level_six_carry_uses_hill_toad_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["hib"], 6, 4)

        self.assertEqual(route.level, 6)
        self.assertEqual(route.prefer, "hill toad")
        self.assertEqual((route.x, route.y, route.z), (309663, 647096, 5234))
        self.assertEqual(route.teleport_destination, "Shannon Estuary")
        self.assertIn("underhill companion", route.avoid)

    def test_hib_duo_target_seven_carry_uses_water_beetle_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=16,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["hib"], 7, 2)

        self.assertEqual(route.prefer, "water beetle")
        self.assertEqual(route.teleport_destination, "Mag Mell")
        self.assertEqual((route.x, route.y, route.z), (348885, 504608, 4686))

    def test_alb_duo_level_five_carry_uses_xp_eligible_emerald_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=19,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["alb"], 5, 2)

        self.assertEqual(route.level, 4)
        self.assertEqual(route.prefer, "emerald snake")
        self.assertEqual((route.x, route.y, route.z), (491813, 601083, 1858))
        self.assertEqual(route.teleport_destination, "Campacorentin Station")
        self.assertGreaterEqual(route.mob_level, 4)

    def test_alb_duo_carry_level_nine_uses_dense_bear_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["alb"], 9, 2)

        self.assertEqual(route.level, 8)
        self.assertEqual(route.prefer, "bear")
        self.assertEqual((route.x, route.y, route.z), (575246, 547179, 2594))
        self.assertEqual(growth.growth_max_target_distance(SimpleNamespace(growth_fast_travel="route-home", max_target_distance=1500, target_home_max_distance=1400), 8, 4, "alb", route), 6500.0)
        self.assertIn("devout filidh", route.avoid)
        self.assertIn("cutpurse", route.avoid)

    def test_growth_avoid_targets_keep_preferred_target_eligible(self) -> None:
        route = growth.RoutePoint(
            10,
            334856,
            531370,
            5456,
            "red wolfhound",
            "anger sprite,red wolfhound,lough wolf",
            source="hunting-index",
        )

        avoid = growth.growth_avoid_targets_for_current_context(route, "hib", 10, 4)

        self.assertNotIn("red wolfhound", avoid)
        self.assertIn("anger sprite", avoid)

    def test_growth_avoid_targets_drop_broad_token_that_blocks_preferred_target(self) -> None:
        route = growth.RoutePoint(
            5,
            786637,
            723034,
            4722,
            "huldu stalker",
            "huldu,huldu hunter,huldu stalker,small hill cat",
            "Mularn",
            source="hunting-index",
        )

        avoid_tokens = growth.growth_avoid_targets_for_current_context(route, "mid", 6, 2).split(",")

        self.assertNotIn("huldu", avoid_tokens)
        self.assertNotIn("huldu stalker", avoid_tokens)
        self.assertIn("huldu hunter", avoid_tokens)
        self.assertIn("small hill cat", avoid_tokens)

    def test_target_name_matching_handles_mojibake_prefix_from_failure_memory(self) -> None:
        self.assertTrue(growth.target_name_matches_any("tree spirit", ["����� tree spirit"]))
        self.assertTrue(growth.target_name_matches_any("����� tree spirit", ["tree spirit"]))
        self.assertFalse(growth.target_name_matches_any("ant", ["giant spider"]))

    def test_mid_party8_catch_up_avoids_grey_level_two_rewards_void(self) -> None:
        self.assertEqual(growth.target_levels(3, 8, "mid"), (2, 3, 1))
        self.assertIn("wild hog", growth.growth_hunting_index_avoid_targets("mid", 3, 8))

        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,8,3,3,3,3,wild hog,2,32,744988,807603,4548,32,0,0,0,Fort Atla,10806,900\n"
                "mid,8,3,3,3,3,wood-eater,3,49,791118,714834,4891,49,0,0,0,Mularn,17211,800\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["mid"], 3, 8)

        self.assertEqual(route.prefer, "wild hog")
        self.assertEqual(route.level, 3)
        self.assertEqual(route.mob_level, 2)
        self.assertEqual(growth.strict_route_target_name(route, 3, party_size=8, realm_key="mid"), "wild hog")

    def test_alb_party8_low_level_route_uses_starter_safe_variant_before_index(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("alb", 2, 8),
            ("skeleton", "spriggarn", "decayed zombie", "black wolf pup"),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "alb,8,2,1,5,5,rot worm,5,28,464792,645770,1699,28,0,0,0,Avalon Marsh,12985,10\n"
                "alb,8,2,1,5,5,skeleton,2,28,525876,471818,2226,28,0,0,0,Bind Start,10664,900\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 2, 8)

        self.assertEqual(route.prefer, "black wolf pup")
        self.assertEqual((route.x, route.y, route.z), (534900, 478900, 2310))

    def test_alb_party8_level_five_uses_dense_carry_camp(self) -> None:
        self.assertEqual(growth.target_levels(5, 8, "alb"), (4, 4, 0))
        self.assertEqual(growth.minimum_growth_effective_target_level(5, 8, "alb"), 4)
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("alb", 5, 8),
            ("gray wolf", "emerald snake", "small bear", "rot worm"),
        )

        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=19,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["alb"], 5, 8)

        self.assertEqual(route.prefer, "ant drone")
        self.assertEqual(route.mob_level, 7)
        self.assertGreaterEqual(route.mob_count, 8)
        self.assertEqual(route.teleport_destination, "Caer Ulfwych")

    def test_mid_solo_level_nine_growth_index_uses_gotar_ghost_light_camp(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("mid", 9, 1),
            ("ghost light", "wood-eater alate", "host of the wind"),
        )
        self.assertEqual(growth.target_levels(9, 1, "mid"), (7, 8, 1))
        self.assertEqual(growth.minimum_growth_effective_target_level(9, 1, "mid"), 7)
        self.assertNotIn("ghost light", growth.growth_hunting_index_avoid_targets("mid", 9, 1))
        self.assertIn("nacken", growth.growth_hunting_index_avoid_targets("mid", 9, 1))
        self.assertIn("haunt", growth.growth_hunting_index_avoid_targets("mid", 9, 1))
        self.assertIn("svartalf", growth.growth_hunting_index_avoid_targets("mid", 9, 1))
        self.assertIn("Svartmoln", growth.growth_hunting_index_avoid_targets("mid", 9, 1))
        self.assertIn("tawny lynx cub", growth.growth_hunting_index_avoid_targets("mid", 9, 1))
        self.assertIn("vein spiderling", growth.growth_hunting_index_avoid_targets("mid", 9, 1))
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,9,7,7,7,Svartmoln,7,2,773089,749600,5822,2,0,0,0,Bind Start,244,-900\n"
                "mid,1,9,7,7,7,carrion crawler,6,33,784000,864000,8868,33,0,0,0,Gotar,36025,800\n"
                "mid,1,9,7,7,7,carrion crawler,6,15,774991,856631,5388,15,0,0,0,Gotar,20612,300\n"
                "mid,1,9,7,7,7,ghost light,7,19,757484,847726,4650,19,0,0,0,Gotar,17764,900\n"
                "mid,1,9,7,7,7,wood-eater alate,7,9,787278,717693,5163,9,0,0,0,Mularn,18639,850\n"
                "mid,1,9,7,7,7,host of the wind,7,11,750636,854357,4800,11,0,0,0,Gotar,27278,700\n"
                "mid,1,9,7,7,7,tawny lynx cub,7,3,770541,749708,4552,3,0,0,0,Bind Start,2787,100\n"
                "mid,1,9,7,7,7,vein spiderling,7,3,767315,749047,4550,3,0,0,0,Bind Start,6042,50\n"
                "mid,1,9,8,8,8,tawny lynx,8,3,764956,839202,4637,3,0,0,500,Gotar,6808,500\n"
                "mid,1,10,7,7,7,ghost light,7,19,757484,847726,4650,19,0,0,0,Gotar,17764,900\n"
                "mid,1,10,8,8,8,army ant soldier,8,16,739371,789159,4714,16,0,0,0,Huginfell,400,700\n"
                "mid,1,10,8,8,8,tawny lynx cub,8,3,768964,749751,4552,3,0,0,0,Bind Start,2787,-300\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["mid"], 9, 1)

        self.assertEqual(route.prefer, "ghost light")
        self.assertEqual((route.x, route.y, route.z), (757484, 847726, 4650))
        self.assertEqual(route.teleport_destination, "Gotar")
        self.assertEqual(route.source, "hunting-index")

    def test_mid_solo_level_eight_growth_index_avoids_host_of_earth(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("mid", 8, 1),
            ("carrion crawler", "army ant worker"),
        )
        self.assertIn("host of the earth", growth.growth_hunting_index_avoid_targets("mid", 8, 1))
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,8,6,6,6,host of the earth,6,14,732225,842592,5203,14,0,0,500,Fort Atla,30266,900\n"
                "mid,1,8,6,6,6,carrion crawler,6,15,774991,856631,5388,15,0,0,500,Gotar,20612,100\n"
                "mid,1,8,6,6,6,army ant worker,6,7,719301,770132,4506,7,0,0,500,Fort Atla,30266,50\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["mid"], 8, 1)

        self.assertEqual(route.prefer, "carrion crawler")
        self.assertIn("host of the earth", route.avoid)

    def test_mid_solo_level_eight_strict_preflight_empty_uses_unverified_index_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,8,6,6,6,carrion crawler,6,33,787192,868637,6698,33,0,0,500,Gotar,36025,900\n"
                "mid,1,8,6,6,6,army ant worker,6,7,719301,770132,4506,7,0,0,500,Audliten,13971,100\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=0,
                growth_route_preflight_low_solo_radius=2500,
                growth_route_preflight_limit=3,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=2200.0,
                run_dir="",
            )

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", return_value=[]):
                route = growth.select_growth_route_point(args, growth.REALMS["mid"], 8, 1)

        self.assertEqual(route.prefer, "carrion crawler")
        self.assertEqual(route.source, "hunting-index-preflight-unverified-fallback")

    def test_alb_duo_level_seven_growth_index_uses_stable_rot_worm_camp(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("alb", 7, 2),
            ("rot worm", "gray wolf", "small bear", "faerie bell-wether"),
        )
        self.assertEqual(growth.target_levels(7, 2, "alb"), (5, 6, 1))
        self.assertEqual(growth.minimum_growth_effective_target_level(7, 2, "alb"), 5)
        self.assertIn("ant drone", growth.growth_hunting_index_avoid_targets("alb", 7, 2))
        self.assertIn("bandit", growth.growth_hunting_index_avoid_targets("alb", 7, 2))
        self.assertIn("tree spirit", growth.growth_hunting_index_avoid_targets("alb", 7, 2))
        self.assertNotIn("rot worm", growth.growth_hunting_index_avoid_targets("alb", 7, 2))
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "alb,2,7,6,7,7,ant drone,7,10,517887,630221,1765,10,0,0,0,Caer Ulfwych,14200,900\n"
                "alb,2,7,6,7,7,bandit,7,7,526821,614578,1847,7,0,0,0,Caer Ulfwych,5745,950\n"
                "alb,2,7,5,6,6,emerald snake,5,20,491813,601083,1858,20,0,0,0,Campacorentin Station,1200,850\n"
                "alb,2,7,6,7,7,tree spirit,6,20,516155,594424,1800,20,0,0,0,Campacorentin Station,22632,100\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 7, 2)

        self.assertEqual(route.prefer, "rot worm")
        self.assertEqual((route.x, route.y, route.z), (464792, 645770, 1699))

    def test_alb_duo_official_case_index_skips_live_empty_ant_drone_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=25,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["alb"], 6, 2)

        self.assertNotEqual(route.prefer, "ant drone")
        self.assertNotEqual((route.x, route.y, route.z), (489000, 600500, 1900))
        self.assertEqual(route.prefer, "rot worm")
        self.assertEqual(route.mob_level, 5)
        self.assertEqual(route.teleport_destination, "Avalon Marsh")

    def test_alb_duo_carry_level_seven_uses_distributed_hunting_index_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=31,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["alb"], 7, 2)

        self.assertNotEqual((route.x, route.y, route.z), (489000, 600500, 1900))
        self.assertEqual(route.prefer, "rot worm")
        self.assertEqual(route.mob_level, 5)
        self.assertEqual(route.teleport_destination, "Avalon Marsh")

    def test_alb_party4_level_six_growth_index_avoids_tree_spirit_death_camp(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("alb", 6, 4),
            ("emerald snake", "faerie bell-wether", "zombie boar", "gray wolf", "small bear"),
        )
        self.assertEqual(growth.target_levels(6, 4, "alb"), (5, 5, 0))
        self.assertEqual(growth.minimum_growth_effective_target_level(6, 4, "alb"), 5)
        self.assertIn("tree spirit", growth.growth_hunting_index_avoid_targets("alb", 6, 4))
        self.assertIn("rot worm", growth.growth_hunting_index_avoid_targets("alb", 6, 4))
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "alb,4,6,5,8,9,tree spirit,6,20,516155,594424,1800,20,0,0,0,Campacorentin Station,1200,950\n"
                "alb,4,6,5,8,9,rot worm,5,28,464792,645770,1699,28,0,0,0,Avalon Marsh,1200,900\n"
                "alb,4,6,5,8,9,emerald snake,5,20,491813,601083,1858,20,0,0,0,Campacorentin Station,1200,850\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 6, 4)

        self.assertEqual(route.prefer, "emerald snake")
        self.assertEqual((route.x, route.y, route.z), (491813, 601083, 1858))

    def test_alb_solo_level_seven_shortage_route_uses_rot_worm_baseline(self) -> None:
        args = SimpleNamespace(growth_route_case_index=0)

        route = growth.select_growth_route_point(args, growth.REALMS["alb"], 7, 1)

        self.assertEqual(route.prefer, "rot worm")
        self.assertEqual(route.mob_level, 6)
        self.assertEqual(route.mob_count, 28)
        self.assertEqual((route.x, route.y, route.z), (464792, 645770, 1699))
        self.assertEqual(route.teleport_destination, "Avalon Marsh")
        self.assertNotIn("rot worm", route.avoid.split(","))
        self.assertIn("faerie bell-wether", route.avoid.split(","))
        self.assertIn("emerald snake", route.avoid.split(","))
        self.assertIn("zombie boar", route.avoid.split(","))

    def test_mid_duo_level_four_growth_index_prefers_mularn_workers(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("mid", 4, 2),
            ("wood-eater", "wood-eater worker", "wayward ghoul", "hobgoblin prankster"),
        )

    def test_mid_duo_level_seven_growth_index_avoids_wood_eater_alate_death_camp(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("mid", 7, 2),
            ("black mauler juvenile", "carrion crawler", "vein spider", "young grendelorm"),
        )
        self.assertEqual(growth.target_levels(7, 2, "mid"), (5, 6, 1))
        self.assertEqual(growth.minimum_growth_effective_target_level(7, 2, "mid"), 5)
        self.assertIn("ghost light", growth.growth_hunting_index_avoid_targets("mid", 7, 2))
        self.assertIn("wood-eater alate", growth.growth_hunting_index_avoid_targets("mid", 7, 2))
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,2,6,5,5,5,carrion crawler,6,33,787192,868637,6698,33,0,0,0,Gotar,36025,800\n"
                "mid,2,6,5,5,5,black mauler juvenile,5,26,731633,814288,5479,26,0,0,0,Fort Atla,12000,950\n"
                "mid,2,7,6,7,7,ghost light,7,19,757484,847726,4650,19,0,0,0,Gotar,17764,950\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 2)

        self.assertEqual(route.prefer, "carrion crawler")
        self.assertEqual((route.x, route.y, route.z), (787192, 868637, 6698))
        self.assertGreaterEqual(route.level, growth.minimum_growth_effective_target_level(7, 2, "mid"))
        self.assertIn("wood-eater alate", growth.growth_avoid_targets_for_current_context(route, "mid", 7, 2))

    def test_mid_duo_carry_level_nine_uses_grounded_smiera_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=7,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 9, 2)

        self.assertEqual(route.level, 9)
        self.assertEqual(route.prefer, "smiera-gatto")
        self.assertEqual((route.x, route.y, route.z), (720665, 762516, 4553))
        self.assertIn("wind wisp", route.avoid)
        self.assertIn("seithr orb", route.avoid)
        self.assertIn("carrion crawler", route.avoid)
        self.assertIn("ghost light", route.avoid)
        self.assertIn("wood-eater alate", route.avoid)

    def test_mid_duo_carry_level_eight_uses_dense_wind_wisp_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=7,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 8, 2)

        self.assertEqual(route.prefer, "wind wisp")
        self.assertEqual((route.x, route.y, route.z), (728346, 853902, 6095))
        self.assertNotIn(route.prefer, growth.growth_avoid_targets_for_current_context(route, "mid", 8, 2).split(","))
        self.assertIn("ghost light", route.avoid)

    def test_mid_party4_carry_level_nine_uses_grounded_army_ant_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 9, 4)

        self.assertEqual(route.level, 8)
        self.assertEqual(route.prefer, "army ant soldier")
        self.assertEqual((route.x, route.y, route.z), (739371, 789159, 4714))
        self.assertIn("wind wisp", route.avoid)
        self.assertIn("lake serpent", route.avoid)

    def test_mid_party4_carry_level_seven_uses_army_ant_not_ghost_light(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 4)

        self.assertEqual(route.level, 8)
        self.assertEqual(route.prefer, "army ant soldier")
        self.assertEqual((route.x, route.y, route.z), (739371, 789159, 4714))
        self.assertIn("ghost light", route.avoid)
        self.assertIn("host of the wind", route.avoid)

    def test_mid_party4_carry_level_eight_respects_command_target_band(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=27,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            growth_target_level_override=6,
            growth_target_plan_override=(8, 8, 1),
            case_name="party4-s180-mid-r001",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 8, 4)

        self.assertEqual(route.prefer, "army ant soldier")
        self.assertEqual((route.x, route.y, route.z), (739371, 789159, 4714))
        self.assertNotEqual(route.prefer, "lake serpent")

    def test_mid_party4_carry_target_eighteen_skips_stale_gotar_tawny_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 18, 4)

        self.assertNotEqual(route.prefer, "tawny lynx")
        self.assertNotEqual((route.x, route.y), (764739, 833564))

    def test_hib_party4_carry_target_nineteen_prefers_dense_camp_over_eight_mob_rotation(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=2,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            growth_route_player_level=11,
            growth_target_level_override=11,
            growth_target_plan_override=growth.growth_party_carry_target_plan_for_realm(11, 4, "hib"),
        )

        route = growth.select_growth_route_point(args, growth.REALMS["hib"], 19, 4)

        self.assertEqual(route.prefer, "large red wolfhound")
        self.assertEqual((route.x, route.y), (377311, 495020))

    def test_mid_party8_carry_level_ten_uses_matching_index_camp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,8,10,10,12,13,lake serpent,12,20,740000,820000,4774,20,0,0,0,Fort Atla,1200,900\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=8,
                growth_target_level_override=8,
                growth_target_plan_override=growth.growth_party_carry_target_plan_for_realm(8, 8, "mid"),
            )

            route = growth.select_growth_route_point(args, growth.REALMS["mid"], 12, 8)

        self.assertEqual(route.level, 10)
        self.assertEqual(route.prefer, "lake serpent")
        self.assertEqual((route.x, route.y, route.z), (740000, 820000, 4774))

    def test_mid_party8_carry_target_eleven_uses_inverse_target_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,8,8,7,11,13,lake serpent,11,14,715021,770060,4191,14,0,0,0,Huginfell,1200,593.682\n"
                "mid,8,11,10,14,16,water snake,14,2,739282,822331,4772,2,0,0,0,Fort Atla,1200,-855.182\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=8,
                growth_target_level_override=8,
                growth_target_plan_override=growth.growth_party_carry_target_plan_for_realm(8, 8, "mid"),
            )

            route = growth.select_growth_route_point(args, growth.REALMS["mid"], 11, 8)

        self.assertEqual(route.level, 8)
        self.assertEqual(route.prefer, "lake serpent")
        self.assertEqual((route.x, route.y, route.z), (715021, 770060, 4191))

    def test_carry_target_index_rotation_stays_in_top_safe_pool(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "alb,8,13,12,16,18,forest adder,16,4,591010,470785,3343,4,0,0,0,Castle Sauvage,1200,-865\n"
                "alb,8,14,13,17,19,giant wolf,17,2,572080,470647,3215,2,0,0,0,Castle Sauvage,1200,-1034\n"
                "alb,8,14,13,17,19,forest adder,17,6,577690,469393,2983,6,0,0,0,Castle Sauvage,1200,-1035\n"
                "alb,8,12,11,15,17,ebony fellwood,15,4,575253,468390,3039,4,0,0,0,Castle Sauvage,1200,-1074\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=99,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=12,
                growth_target_level_override=12,
                growth_target_plan_override=growth.growth_party_carry_target_plan_for_realm(12, 8, "alb"),
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 14, 8)

        self.assertIn(route.prefer, {"forest adder", "giant wolf"})
        self.assertNotEqual(route.prefer, "ebony fellwood")

    def test_carry_target_index_rotation_dedupes_same_physical_camp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,4,16,15,18,21,tawny lynx,18,8,764739,833564,4603,8,0,0,0,Gotar,7004,-946\n"
                "mid,4,17,16,18,21,tawny lynx,18,8,764739,833564,4603,8,0,0,0,Gotar,7004,-1446\n"
                "mid,4,18,17,18,21,tawny lynx,18,8,764739,833564,4603,8,0,0,0,Gotar,7004,-1946\n"
                "mid,4,17,16,18,21,rock crab,18,8,767511,829023,4774,8,0,0,0,Gotar,8209,-1500\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=1,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=16,
                growth_target_level_override=16,
                growth_target_plan_override=growth.growth_party_carry_target_plan_for_realm(16, 4, "mid"),
            )

            route = growth.select_growth_route_point(args, growth.REALMS["mid"], 18, 4)

        self.assertEqual(route.prefer, "rock crab")
        self.assertEqual((route.x, route.y, route.z), (767511, 829023, 4774))

    def test_carry_target_index_demotes_sparse_live_target_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "hib,2,13,12,14,16,fishing bear forager,14,15,310930,436273,5496,15,0,0,0,Druim Ligen,1200,-421\n"
                "hib,2,15,14,17,19,faerie beetle,17,12,345583,428917,5918,12,0,0,0,Druim Ligen,1200,-476\n"
                "hib,2,15,14,16,18,small walking boulder,16,3,350956,558757,5550,3,0,0,0,Ardagh,1200,-523\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=8,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
            )

            route = growth.select_growth_route_point(args, growth.REALMS["hib"], 14, 2)

        self.assertIn(route.prefer, {"fishing bear forager", "faerie beetle"})
        self.assertNotEqual(route.prefer, "small walking boulder")

    def test_carry_target_index_prefers_positive_score_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "hib,8,14,13,17,19,faerie beetle,17,12,345583,428917,5918,12,0,0,0,Druim Ligen,1200,23.2\n"
                "hib,8,16,15,19,21,large red wolfhound,19,18,377311,495020,5095,18,0,0,0,Tir na mBeo,1200,-114.8\n"
                "hib,8,15,14,18,20,faerie horse,18,3,323824,715617,4314,3,0,0,0,Innis Carthaig,1200,-450.0\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=99,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=12,
                growth_target_level_override=12,
                growth_target_plan_override=growth.growth_party_carry_target_plan_for_realm(12, 8, "hib"),
            )

            route = growth.select_growth_route_point(args, growth.REALMS["hib"], 16, 8)

        self.assertEqual(route.prefer, "faerie beetle")
        self.assertEqual((route.x, route.y, route.z), (345583, 428917, 5918))

    def test_carry_target_route_home_uses_wide_hunt_radius_after_level_ten(self) -> None:
        args = SimpleNamespace(
            max_target_distance=2200.0,
            target_home_max_distance=1400.0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )
        route = growth.route_point(
            16,
            377311,
            495020,
            5095,
            "large red wolfhound",
            source="hunting-index",
        )

        self.assertEqual(growth.growth_target_home_max_distance(args, 11, 4, "hib"), 6500.0)
        self.assertEqual(growth.growth_max_target_distance(args, 11, 4, "hib", route), 6500.0)

    def test_low_level_carry_route_home_uses_wide_hunt_radius(self) -> None:
        args = SimpleNamespace(
            max_target_distance=2200.0,
            target_home_max_distance=1400.0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )
        route = growth.route_point(
            6,
            309663,
            647096,
            5234,
            "hill toad",
            source="hunting-index",
        )

        self.assertEqual(growth.growth_target_home_max_distance(args, 7, 2, "hib"), 10000.0)
        self.assertEqual(growth.growth_max_target_distance(args, 7, 2, "hib", route), 6500.0)

    def test_hib_duo_water_beetle_carry_uses_wide_hunt_radius(self) -> None:
        args = SimpleNamespace(
            max_target_distance=2200.0,
            target_home_max_distance=1400.0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )
        route = growth.route_point(
            8,
            349499,
            567686,
            4762,
            "water beetle",
            source="hunting-index",
        )

        self.assertEqual(growth.growth_max_target_distance(args, 7, 2, "hib", route), 6500.0)

    def test_mid_duo_carrion_crawler_carry_uses_wide_hunt_radius(self) -> None:
        args = SimpleNamespace(
            max_target_distance=2200.0,
            target_home_max_distance=1400.0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )
        route = growth.route_point(
            6,
            777576,
            869618,
            5947,
            "carrion crawler",
            source="hunting-index",
        )

        self.assertEqual(growth.growth_max_target_distance(args, 6, 2, "mid", route), 6500.0)

    def test_hib_solo_level_eight_avoids_water_beetle_z_mismatch_route(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("hib", 8, 1),
            ("hill toad", "lugradan whelp"),
        )
        self.assertEqual(growth.target_levels(8, 1, "hib"), (5, 6, 1))
        self.assertEqual(growth.minimum_growth_effective_target_level(8, 1, "hib"), 6)
        self.assertEqual(
            growth.enforce_no_lower_xp_target_plan(
                SimpleNamespace(growth_allow_lower_xp_gear_farm=True),
                8,
                1,
                *growth.target_levels(8, 1, "hib"),
                "hib",
            ),
            (6, 6, 1),
        )
        route = growth.select_growth_route_point(
            SimpleNamespace(
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=False,
            ),
            growth.REALMS["hib"],
            8,
            1,
        )
        self.assertEqual(route.level, 7)
        self.assertIn(route.prefer, {"hill toad", "lugradan whelp"})
        avoid_tokens = [token.strip() for token in growth.growth_hunting_index_avoid_targets("hib", 8, 1).split(",")]
        self.assertIn("water beetle", avoid_tokens)
        self.assertIn("water beetle collector", avoid_tokens)
        self.assertIn("wild crouch", avoid_tokens)

    def test_hib_solo_level_nine_uses_non_gray_recovery_route(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=23,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["hib"], 9, 1)

        self.assertEqual(route.level, 9)
        self.assertIn(route.prefer, {"lough wolf", "rat boy"})
        self.assertGreaterEqual(route.mob_level, growth.minimum_growth_effective_target_level(9, 1, "hib"))
        avoid_tokens = [token.strip() for token in route.avoid.split(",")]
        self.assertIn("water beetle", avoid_tokens)
        self.assertIn("hill toad", avoid_tokens)
        self.assertIn("lugradan whelp", avoid_tokens)
        self.assertIn("wild crouch", avoid_tokens)

    def test_alb_solo_level_eight_growth_index_uses_live_verified_rot_worm_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["alb"], 8, 1)

        self.assertEqual(growth.target_levels(8, 1, "alb"), (6, 6, 0))
        self.assertEqual(growth.minimum_growth_effective_target_level(8, 1, "alb"), 6)
        self.assertEqual(route.prefer, "rot worm")
        self.assertEqual(route.mob_level, 6)
        self.assertEqual((route.x, route.y), (486334, 592350))
        self.assertNotIn("rot worm", growth.growth_avoid_targets_for_current_context(route, "alb", 8, 1))
        self.assertIn("emerald snake", growth.growth_avoid_targets_for_current_context(route, "alb", 8, 1))
        self.assertIn("tree spirit", growth.growth_avoid_targets_for_current_context(route, "alb", 8, 1))
        self.assertIn("giant spider", growth.growth_avoid_targets_for_current_context(route, "alb", 8, 1))

    def test_alb_solo_level_eight_no_engagement_uses_undead_filidh_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-05T00:00:00Z,alb-p1,alb,1,45,8,no_engagement,downgrade_target_plan,,,timeline,48\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=46,
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 8, 1)

        self.assertEqual(route.prefer, "undead filidh")
        self.assertEqual(route.mob_level, 6)
        self.assertEqual((route.x, route.y), (600781, 529920))
        self.assertIn("rot worm", growth.growth_avoid_targets_for_current_context(route, "alb", 8, 1))

    def test_alb_solo_level_nine_uses_safe_prydwen_river_racer_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["alb"], 9, 1)

        self.assertEqual(growth.target_levels(9, 1, "alb"), (7, 7, 0))
        self.assertEqual(route.prefer, "river racer")
        self.assertEqual(route.mob_level, 7)
        self.assertEqual((route.x, route.y), (592858, 549006))
        self.assertNotEqual((route.x, route.y), (595800, 526000))
        self.assertEqual(route.teleport_destination, "Prydwen Keep")
        self.assertIn("adder", growth.growth_avoid_targets_for_current_context(route, "alb", 9, 1).split(","))
        self.assertNotIn("river racer", growth.growth_avoid_targets_for_current_context(route, "alb", 9, 1).split(","))
        self.assertIn("large skeleton", growth.growth_avoid_targets_for_current_context(route, "alb", 9, 1))
        self.assertIn("filidh", growth.growth_avoid_targets_for_current_context(route, "alb", 9, 1))

    def test_alb_solo_level_nine_river_racer_failure_uses_xp_eligible_undead_filidh_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-05T00:00:00Z,alb-p1,alb,1,56,9,combat_no_kill,avoid_target,river racer,7,combat_csv,59\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=48,
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 9, 1)

        self.assertEqual(route.prefer, "undead filidh")
        self.assertEqual(route.mob_level, 7)
        self.assertGreaterEqual(route.mob_level, growth.minimum_non_grey_target_level(9))
        self.assertEqual((route.x, route.y), (518282, 609298))
        self.assertNotEqual((route.x, route.y), (595800, 526000))
        self.assertEqual(route.teleport_destination, "Caer Ulfwych")
        self.assertIn("river racer", growth.growth_avoid_targets_for_current_context(route, "alb", 9, 1).split(","))

    def test_alb_solo_level_nine_expired_river_racer_hard_failure_keeps_undead_filidh_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-05T00:00:00Z,alb-p1,alb,1,56,9,combat_no_kill,avoid_target,river racer,7,combat_csv,59\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=60,
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 9, 1)

        self.assertEqual(route.prefer, "undead filidh")
        self.assertEqual(route.mob_level, 7)
        self.assertEqual((route.x, route.y), (518282, 609298))

    def test_alb_solo_level_nine_unrelated_no_engagement_keeps_default_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-05T00:00:00Z,alb-p1,alb,1,57,9,no_engagement,downgrade_target_plan,,,timeline,60\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=58,
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 9, 1)

        self.assertEqual(route.prefer, "river racer")
        self.assertEqual(route.mob_level, 7)
        self.assertEqual((route.x, route.y), (592858, 549006))

    def test_alb_solo_level_nine_expired_generic_no_engagement_keeps_default_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-05T00:00:00Z,alb-p1,alb,1,57,9,no_engagement,downgrade_target_plan,,,timeline,60\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=63,
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 9, 1)

        self.assertEqual(route.prefer, "river racer")
        self.assertEqual(route.mob_level, 7)
        self.assertEqual((route.x, route.y), (592858, 549006))

    def test_alb_solo_level_nine_undead_filidh_failure_uses_secondary_xp_eligible_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-05T00:00:00Z,alb-p1,alb,1,56,9,combat_no_kill,avoid_target,river racer,7,combat_csv,59\n"
                "2026-07-05T00:01:00Z,alb-p1,alb,1,58,9,combat_no_kill,avoid_target,undead filidh,7,combat_csv,61\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=59,
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 9, 1)

        self.assertEqual(route.prefer, "rotting zombie")
        self.assertEqual(route.mob_level, 7)
        self.assertGreaterEqual(route.mob_level, growth.minimum_non_grey_target_level(9))
        self.assertEqual((route.x, route.y), (527242, 624780))
        self.assertNotEqual(route.prefer, "undead filidh")

    def test_alb_solo_level_nine_rotting_zombie_failure_uses_tertiary_xp_eligible_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-05T00:00:00Z,alb-p1,alb,1,56,9,combat_no_kill,avoid_target,river racer,7,combat_csv,59\n"
                "2026-07-05T00:01:00Z,alb-p1,alb,1,58,9,combat_no_kill,avoid_target,undead filidh,7,combat_csv,61\n"
                "2026-07-05T00:02:00Z,alb-p1,alb,1,60,9,combat_no_kill,avoid_target,rotting zombie,7,combat_csv,63\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=61,
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 9, 1)

        self.assertEqual(route.prefer, "sylvan goblin hunter")
        self.assertEqual(route.mob_level, 7)
        self.assertGreaterEqual(route.mob_level, growth.minimum_non_grey_target_level(9))
        self.assertEqual((route.x, route.y), (513958, 638406))

    def test_alb_level_ten_rotting_route_home_uses_same_plane_safe_landing(self) -> None:
        route = growth.route_point(
            10,
            527242,
            624780,
            1965,
            "rotting zombie",
            teleport_destination="Caer Ulfwych",
            source="hunting-index",
            mob_level=7,
        )

        safe = growth.startup_route_home_after_services_point(
            growth.REALMS["alb"],
            route,
            current_level=10,
            party_size=1,
            ground_z_offset=0,
        )

        self.assertNotEqual((safe.x, safe.y), (route.x, route.y))
        self.assertEqual(safe.prefer, "rotting zombie")
        self.assertEqual(safe.x, route.x)
        self.assertEqual(route.y - safe.y, 1300)
        self.assertLessEqual(abs(safe.z - route.z), 220)
        self.assertLess(math.hypot(safe.x - 521393, safe.y - 616461), math.hypot(route.x - 521393, route.y - 616461))

    def test_alb_solo_level_nine_broad_filidh_token_does_not_trigger_secondary_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-05T00:00:00Z,alb-p1,alb,1,56,9,combat_no_kill,avoid_target,river racer,7,combat_csv,59\n"
                "2026-07-05T00:01:00Z,alb-p1,alb,1,58,9,death_pressure,avoid_target,filidh,0,encounter_death_message,61\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=59,
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 9, 1)

        self.assertEqual(route.prefer, "undead filidh")
        self.assertEqual(route.mob_level, 7)
        self.assertEqual((route.x, route.y), (518282, 609298))

    def test_alb_solo_level_nine_undead_filidh_fallback_does_not_self_block_with_avoid_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-05T00:00:00Z,alb-p1,alb,1,56,9,combat_no_kill,avoid_target,river racer,7,combat_csv,59\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=58,
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 9, 1)

        self.assertEqual(route.prefer, "undead filidh")
        self.assertEqual(route.mob_level, 7)
        self.assertEqual((route.x, route.y), (518282, 609298))
        self.assertFalse(growth.target_name_matches_any("undead filidh", growth.preferred_target_tokens(route.avoid)))

    def test_hib_solo_level_ten_growth_index_uses_xp_eligible_water_beetle(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("hib", 10, 1),
            ("hill toad", "lugradan whelp", "lough wolf", "rat boy"),
        )
        self.assertEqual(growth.target_levels(10, 1, "hib"), (6, 6, 0))
        self.assertEqual(growth.minimum_growth_effective_target_level(9, 1, "hib"), 7)
        self.assertEqual(growth.minimum_growth_effective_target_level(10, 1, "hib"), 7)
        avoid_tokens = [token.strip() for token in growth.growth_hunting_index_avoid_targets("hib", 10, 1).split(",")]
        self.assertNotIn("water beetle", avoid_tokens)
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "hib,1,10,7,8,9,water beetle,8,9,293012,649014,4873,9,0,0,0,Tir na mBeo,700,100\n"
                "hib,1,10,7,8,9,rat boy,8,3,348590,491555,5746,3,0,0,0,Mag Mell,2496,10\n"
                "hib,1,10,7,8,9,lough wolf,7,3,349869,494579,5191,3,0,0,0,Mag Mell,4944,5\n"
                "hib,1,10,7,8,9,lugradan whelp,7,12,307930,634160,4972,12,0,0,0,Shannon Estuary,1800,900\n"
                "hib,1,10,7,8,9,hill toad,7,37,309663,647096,5234,37,0,0,0,Shannon Estuary,1600,800\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["hib"], 10, 1)

        self.assertEqual(route.prefer, "water beetle")
        self.assertEqual((route.x, route.y, route.z), (352178, 532352, 4598))
        self.assertEqual(route.mob_count, 1)
        self.assertTrue(route.live_anchor_z)
        self.assertIn("minor changeling", growth.growth_hunting_index_avoid_targets("hib", 10, 1))

    def test_hib_level_ten_water_beetle_route_home_uses_same_plane_safe_landing(self) -> None:
        route = growth.select_growth_route_point(
            SimpleNamespace(growth_hunting_index="", growth_route_case_index=0),
            growth.REALMS["hib"],
            10,
            1,
        )

        safe = growth.startup_route_home_after_services_point(
            growth.REALMS["hib"],
            route,
            current_level=10,
            party_size=1,
            ground_z_offset=0,
        )

        self.assertEqual((route.x, route.y, route.z), (352178, 532352, 4598))
        self.assertEqual((safe.x, safe.y, safe.z), (352178, 531052, 4598))
        self.assertEqual(safe.prefer, "water beetle")
        self.assertTrue(safe.live_anchor_z)

    def test_hib_duo_level_eight_uses_xp_eligible_ground_targets(self) -> None:
        self.assertEqual(growth.target_levels(8, 2, "hib"), (7, 8, 0))
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("hib", 8, 2),
            ("rat boy", "lough wolf"),
        )
        self.assertIn("water beetle", growth.growth_hunting_index_avoid_targets("hib", 8, 2))

    def test_hib_party4_level_nine_uses_lough_wolf_camp(self) -> None:
        self.assertEqual(growth.target_levels(9, 4, "hib"), (8, 8, 0))
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("hib", 9, 4),
            ("lough wolf", "hill toad", "large eirebug", "badger"),
        )

    def test_mid_party4_level_nine_uses_safer_army_ant_soldier_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 9, 4)

        self.assertEqual(growth.target_levels(9, 4, "mid"), (8, 8, 0))
        self.assertEqual(growth.minimum_growth_effective_target_level(9, 4, "mid"), 8)
        self.assertEqual(route.level, 8)
        self.assertEqual(route.prefer, "army ant soldier")
        self.assertEqual((route.x, route.y, route.z), (739371, 789159, 4714))
        self.assertIn("lake serpent", route.avoid)
        self.assertIn("wind wisp", route.avoid)

    def test_alb_party4_level_seven_uses_xp_eligible_emerald_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["alb"], 7, 4)

        self.assertEqual(route.level, 6)
        self.assertEqual(route.prefer, "emerald snake")
        self.assertEqual((route.x, route.y, route.z), (491813, 601083, 1858))
        self.assertIn("rot worm", route.avoid)
        self.assertIn("bandit", route.avoid)

    def test_alb_party4_carry_level_seven_avoids_tree_spirit_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["alb"], 7, 4)

        self.assertEqual(route.level, 6)
        self.assertEqual(route.prefer, "emerald snake")
        self.assertEqual((route.x, route.y, route.z), (491813, 601083, 1858))
        self.assertIn("tree spirit", route.avoid)

    def test_alb_party4_carry_level_twelve_uses_dense_slave_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["alb"], 12, 4)

        self.assertEqual(route.level, 11)
        self.assertEqual(route.prefer, "slave")
        self.assertEqual((route.x, route.y, route.z), (606316, 562852, 2066))
        self.assertIn("giant wolf", route.avoid)

    def test_mid_duo_carry_target_twelve_falls_back_to_dense_level_eleven_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=109,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            growth_route_player_level=9,
            growth_target_level_override=9,
            growth_target_plan_override=growth.growth_party_carry_target_plan_for_realm(9, 2, "mid"),
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 12, 2)

        self.assertEqual(growth.growth_party_carry_target_plan_for_realm(9, 2, "mid"), (11, 12, 3))
        self.assertEqual(route.prefer, "lake serpent")
        self.assertEqual((route.x, route.y, route.z), (715021, 770060, 4191))

    def test_alb_party4_carry_level_eight_uses_bear_camp_before_slave_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["alb"], 8, 4)

        self.assertEqual(route.level, 8)
        self.assertEqual(route.prefer, "bear")
        self.assertEqual((route.x, route.y, route.z), (575246, 547179, 2594))

    def test_hib_party4_level_ten_uses_neutral_red_wolfhound_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            max_target_distance=1500,
            target_home_max_distance=1400,
            combat_home_leash_distance=1200,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["hib"], 10, 4)

        self.assertEqual(route.level, 10)
        self.assertEqual(route.prefer, "red wolfhound")
        self.assertEqual((route.x, route.y, route.z), (334856, 531370, 5456))
        self.assertIn("anger sprite", route.avoid)
        self.assertIn("badger", route.avoid)
        self.assertIn("curmudgeon harvester", route.avoid)
        self.assertEqual(growth.growth_max_target_distance(args, 10, 4, "hib", route), 6500.0)
        self.assertEqual(growth.growth_target_home_max_distance(args, 10, 4), 6500.0)
        self.assertEqual(growth.growth_combat_home_leash_distance(args, 10, 4), 6500.0)

    def test_hib_duo_level_four_growth_index_prefers_non_spraggon_camps(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("hib", 3, 8),
            ("large frog", "water beetle larva", "skeletal pawn", "badger cub", "water beetle collector"),
        )
        self.assertEqual(growth.target_levels(3, 8, "hib"), (1, 2, 1))
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("hib", 4, 2),
            ("mudman", "small freshwater crab"),
        )
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("hib", 4, 4),
            ("mudman", "small freshwater crab"),
        )
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("hib", 5, 8),
            ("mudman", "small freshwater crab", "villainous youth", "water beetle collector", "spraggon", "water beetle"),
        )
        self.assertIn("underhill companion", growth.growth_hunting_index_avoid_targets("hib", 7, 2))
        self.assertEqual(growth.growth_flee_pressure_health_percent(4, 8, "hib"), 55)
        args = SimpleNamespace(
            growth_hunting_index="",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
        )
        route = growth.select_growth_route_point(args, growth.REALMS["hib"], 4, 8)
        self.assertEqual(route.prefer, "small freshwater crab")
        self.assertEqual((route.x, route.y, route.z), (361545, 491812, 4659))

    def test_low_alb_party8_growth_index_prefers_simpler_safe_camps(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("alb", 4, 8),
            ("rot worm", "gray wolf", "small bear", "ant drone", "bandit"),
        )
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("alb", 6, 8),
            ("ant drone", "rot worm", "gray wolf", "small bear", "bandit"),
        )
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("alb", 7, 8),
            ("ant drone", "bandit", "rot worm", "gray wolf", "small bear"),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "alb,8,4,3,7,7,giant spider,8,3,496426,593548,1904,3,0,0,0,Campacorentin Station,1200,900\n"
                "alb,8,4,3,7,7,gray wolf,6,22,495960,596970,1961,22,0,0,0,Campacorentin Station,1200,800\n"
                "alb,8,6,5,9,9,bandit,9,16,526821,614578,1847,16,0,0,0,Campacorentin Station,1200,960\n"
                "alb,8,6,5,9,9,boulderling,9,58,587493,532154,2597,58,0,0,0,Prydwen Keep,1200,950\n"
                "alb,8,6,5,9,9,wild boar,10,18,509954,613604,1857,18,0,51,100,Caer Ulfwych,1200,900\n"
                "alb,8,6,5,9,9,tree spirit,6,20,516155,594424,1800,20,0,0,0,Campacorentin Station,1200,800\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            level_four = growth.select_growth_route_point(args, growth.REALMS["alb"], 4, 8)
            level_six = growth.select_growth_route_point(args, growth.REALMS["alb"], 6, 8)

        self.assertEqual(level_four.prefer, "gray wolf")
        self.assertEqual(level_six.prefer, "ant drone")

    def test_alb_party8_level_eight_uses_xp_eligible_ant_drone_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["alb"], 8, 8)

        self.assertEqual(route.level, 7)
        self.assertEqual(route.prefer, "ant drone")
        self.assertEqual((route.x, route.y, route.z), (517887, 630221, 1765))
        self.assertIn("filidh", route.avoid)
        self.assertIn("devout filidh", route.avoid)

    def test_hib_party8_level_nine_uses_neutral_red_wolfhound_camp(self) -> None:
        self.assertEqual(growth.target_levels(9, 8, "hib"), (9, 9, 1))
        self.assertEqual(growth.minimum_growth_effective_target_level(9, 8, "hib"), 9)
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "hib,8,9,8,12,14,red wolfhound,12,8,347430,520936,5651,0,0,0,0,Tir na mBeo,8147,900\n"
                "hib,8,9,8,12,14,red wolfhound,10,19,334856,531370,5456,17,0,200,500,Tir na mBeo,11120,100\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["hib"], 9, 8)

        self.assertEqual(route.level, 10)
        self.assertEqual(route.prefer, "red wolfhound")
        self.assertEqual((route.x, route.y, route.z), (334856, 531370, 5456))
        self.assertIn("curmudgeon harvester", route.avoid)

    def test_hib_party8_level_eight_growth_index_avoids_hazard_camps(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("hib", 8, 8),
            ("water beetle", "large eirebug", "red wolfhound", "lough wolf"),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "hib,8,8,7,9,9,red wolfhound,10,18,334856,531370,5456,0,200,400,1200,Tir na mBeo,11120,900\n"
                "hib,8,8,7,9,9,water beetle,8,16,352162,527862,4679,16,0,0,0,Tir na mBeo,6546,100\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["hib"], 8, 8)

        self.assertEqual(route.prefer, "water beetle")
        self.assertIn("blackthorn", route.avoid)
        self.assertIn("lunantishee", route.avoid)
        self.assertIn("red wolfhound", route.avoid)
        self.assertNotIn("lough wolf", route.avoid)

    def test_hib_party8_carry_level_seven_uses_safe_water_beetle_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=14,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            case_name="party8-s240-hib-r001",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["hib"], 7, 8)

        self.assertEqual(route.prefer, "water beetle")
        self.assertEqual((route.x, route.y, route.z), (350899, 531716, 4610))
        self.assertEqual(route.mob_level, 7)
        self.assertIn("red wolfhound", route.avoid)
        self.assertIn("red wolfhound", route.avoid)

    def test_hib_party8_carry_level_eight_uses_safe_water_beetle_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=14,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            case_name="party8-s240-hib-r001",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["hib"], 8, 8)

        self.assertEqual(route.prefer, "water beetle")
        self.assertEqual((route.x, route.y, route.z), (352162, 527862, 4679))
        self.assertEqual(route.mob_level, 8)
        self.assertIn("red wolfhound", route.avoid)
        self.assertIn("red wolfhound", route.avoid)

    def test_hib_party4_carry_level_seven_avoids_old_water_beetle_z_mismatch_anchor(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=13,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            case_name="party4-s180-hib-r001",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["hib"], 7, 4)

        self.assertEqual(route.prefer, "water beetle")
        self.assertIn("water beetle", route.avoid)
        self.assertNotEqual((route.x, route.y, route.z), (348885, 504608, 4686))

    def test_mid_party4_carry_level_four_carrion_crawler_uses_wide_hunt_radius(self) -> None:
        args = SimpleNamespace(
            max_target_distance=2200.0,
            target_home_max_distance=1400.0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )
        route = growth.route_point(
            4,
            787192,
            868637,
            6698,
            "carrion crawler",
            source="hunting-index",
        )

        self.assertEqual(growth.growth_max_target_distance(args, 4, 4, "mid", route), 6500.0)

    def test_mid_solo_level_seven_growth_index_uses_xp_eligible_target(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("mid", 7, 1),
            ("carrion crawler", "young grendelorm", "vein spider"),
        )
        avoid_targets = growth.growth_hunting_index_avoid_targets("mid", 7, 1)
        self.assertNotIn("young grendelorm", avoid_targets)
        self.assertIn("black mauler juvenile", avoid_targets)
        self.assertIn("wood-eater worker", avoid_targets)
        self.assertIn("wayward ghoul", avoid_targets)
        self.assertIn("dryad sprig", avoid_targets)
        self.assertIn("army ant worker", avoid_targets)
        self.assertIn("rock crab", avoid_targets)
        self.assertIn("roaming thrall", avoid_targets)
        self.assertIn("huldu", avoid_targets)
        self.assertIn("small hill cat", avoid_targets)
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,9,7,7,7,Svartmoln,7,2,773089,749600,5822,2,0,0,0,Bind Start,244,-900\n"
                "mid,1,7,5,6,6,army ant worker,6,20,732194,775472,4658,20,0,0,0,Mularn,4000,980\n"
                "mid,1,7,5,7,7,rock crab,7,12,729847,776408,4765,12,0,0,0,Mularn,5000,970\n"
                "mid,1,7,6,6,6,young grendelorm,6,15,776006,724447,4719,15,0,0,0,Bind Start,25348,900\n"
                "mid,1,7,6,6,6,vein spider,6,25,772957,725582,4754,25,0,0,0,Bind Start,24074,900\n"
                "mid,1,7,5,5,5,wood-eater worker,4,31,786637,723034,4722,31,0,0,0,Mularn,17360,800\n"
                "mid,1,7,5,5,5,black mauler juvenile,5,26,731633,814288,5479,26,0,0,0,Fort Atla,12000,950\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=2,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(route.prefer, "young grendelorm")
        self.assertEqual(route.mob_level, 6)
        self.assertEqual((route.x, route.y, route.z), (776006, 724447, 4719))
        self.assertEqual(growth.strict_route_target_name(route, 7, party_size=1, realm_key="mid"), "young grendelorm")

    def test_mid_solo_level_seven_shortage_recovery_does_not_force_black_mauler(self) -> None:
        args = SimpleNamespace(
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            growth_route_preflight=False,
            growth_failure_target_memory=True,
            run_dir="",
            case_name="",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(route.prefer, "carrion crawler")
        self.assertNotEqual(route.prefer, "black mauler juvenile")
        self.assertIn("vein spider", route.avoid)
        self.assertIn("black mauler juvenile", route.avoid)

    def test_mid_solo_level_seven_shortage_prefers_carrion_crawler_over_xp_void_vein(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,7,4,5,6,carrion crawler,6,33,787192,868637,6698,33,0,0,500,Gotar,36025,1200\n"
                "mid,1,7,4,5,6,vein spider,5,25,772957,725582,4754,25,0,0,0,Bind Start,24074,900\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=2500,
                growth_route_preflight_low_solo_radius=2500,
                growth_route_preflight_limit=3,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_allow_lower_xp_target_plan=True,
                growth_allow_lower_xp_gear_farm=True,
                growth_target_plan_override=(6, 6, 0),
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=5200,
                run_dir="",
            )

            def fake_preflight(url: str, timeout: float) -> object:
                del timeout
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                if name == "vein spider":
                    return [{"name": "vein spider", "level": 5, "x": 774727, "y": 726157, "z": 4771}]
                if name == "carrion crawler":
                    return [{"name": "carrion crawler", "level": 6, "x": 786950, "y": 873259, "z": 4715}]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(route.prefer, "carrion crawler")
        self.assertEqual(route.mob_level, 6)
        self.assertEqual((route.x, route.y, route.z), (786950, 873259, 4715))

    def test_mid_solo_level_seven_shortage_prefers_low_density_vein_spider_camp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,7,5,5,5,vein spider,5,25,772957,725582,4754,25,0,0,0,Bind Start,24074,1200\n"
                "mid,1,7,5,5,5,vein spider,5,9,813800,688337,5922,9,0,0,0,Fort Veldon,16053,500\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_preflight=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_allow_lower_xp_target_plan=True,
                growth_allow_lower_xp_gear_farm=True,
                growth_target_plan_override=(5, 5, 0),
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=2200.0,
                run_dir="",
            )

            with mock.patch.object(
                growth,
                "fetch_growth_route_preflight_payload",
                return_value=[{"name": "vein spider", "level": 5}],
            ):
                route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(route.prefer, "vein spider")
        self.assertEqual(route.mob_count, 9)
        self.assertEqual((route.x, route.y, route.z), (813800, 688337, 5922))

    def test_growth_failed_target_memory_skips_repeated_zero_kill_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir) / "run"
            run_dir = base_dir / "cases" / "case-a"
            failed_dir = base_dir / "failed-attempts" / "case-a" / "segment-016-attempt-001"
            failed_dir.mkdir(parents=True)
            (failed_dir / "segment-016-combat.csv").write_text(
                "username,round,target_id,target_name,target_level,outcome,duration_seconds,attacks,skills,start_distance,end_distance\n"
                "growthmid,1,100,young grendelorm,5,flee,12.0,10,2,100,80\n"
                "growthmid,1,101,young grendelorm,5,round_end,8.0,6,1,120,100\n",
                encoding="utf-8",
            )
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,7,5,5,5,young grendelorm,5,15,776006,724447,4719,15,0,0,0,Bind Start,25348,950\n"
                "mid,1,7,5,5,5,vein spider,5,25,772957,725582,4754,25,0,0,0,Bind Start,24074,900\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_preflight=False,
                growth_failure_target_memory=True,
                growth_failure_target_memory_attempts=8,
                growth_failure_target_memory_min_engagements=2,
                growth_current_segment_index=16,
                run_dir=str(run_dir),
                case_name="case-a",
            )

            avoid_targets = growth.growth_failed_target_memory_avoid_targets(args, "mid", 7, 1)
            route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertIn("young grendelorm", avoid_targets)
        self.assertEqual(route.prefer, "carrion crawler")

    def test_growth_failed_target_memory_blocks_xp_void_kill_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir) / "run"
            run_dir = base_dir / "cases" / "case-a"
            failed_dir = base_dir / "failed-attempts" / "case-a" / "segment-009-attempt-001"
            failed_dir.mkdir(parents=True)
            (failed_dir / "timeline.csv").write_text(
                "case,segment,account,level_after,xp_effective_delta,target_removed,bottleneck_reason\n"
                "case-a,9,growthmid,7,0,1,target_removed_no_xp;no_loot_from_kills\n",
                encoding="utf-8",
            )
            (failed_dir / "segment-009-combat.csv").write_text(
                "username,round,target_id,target_name,target_level,outcome,duration_seconds,attacks,skills,start_distance,end_distance\n"
                "growthmid,1,100,vein spider,5,target_removed,10.0,40,2,100,80\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_failure_target_memory_attempts=8,
                growth_failure_target_memory_min_engagements=2,
                growth_current_segment_index=9,
                run_dir=str(run_dir),
                case_name="case-a",
            )

            avoid_targets = growth.growth_failed_target_memory_avoid_targets(args, "mid", 7, 1)

        self.assertIn("vein spider", avoid_targets)

    def test_growth_failed_target_memory_blocks_single_critical_health_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir) / "run"
            run_dir = base_dir / "cases" / "case-a"
            failed_dir = base_dir / "failed-attempts" / "case-a" / "segment-008-attempt-001"
            failed_dir.mkdir(parents=True)
            (failed_dir / "segment-008-combat.csv").write_text(
                "username,round,target_id,target_name,target_level,outcome,duration_seconds,attacks,skills,start_distance,end_distance\n"
                "growthalb,1,100,노련한 emerald snake,6,critical_health_drop_aggro,1.4,0,0,300,30\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_failure_target_memory_attempts=8,
                growth_failure_target_memory_min_engagements=2,
                growth_current_segment_index=8,
                run_dir=str(run_dir),
                case_name="case-a",
            )

            avoid_targets = growth.growth_failed_target_memory_avoid_targets(args, "alb", 7, 1)

        self.assertIn("노련한 emerald snake", avoid_targets)

    def test_growth_failed_target_memory_blocks_engaged_flee_target_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir) / "run"
            run_dir = base_dir / "cases" / "case-a"
            failed_dir = base_dir / "failed-attempts" / "case-a" / "segment-009-attempt-001"
            failed_dir.mkdir(parents=True)
            (failed_dir / "segment-009-combat.csv").write_text(
                "username,round,target_id,target_name,target_level,outcome,duration_seconds,attacks,skills,start_distance,end_distance\n"
                "growthmid,1,100,army ant worker,6,flee,4.7,0,1,1200,290\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_failure_target_memory_attempts=8,
                growth_failure_target_memory_min_engagements=2,
                growth_current_segment_index=9,
                run_dir=str(run_dir),
                case_name="case-a",
            )

            avoid_targets = growth.growth_failed_target_memory_avoid_targets(args, "mid", 7, 1)

        self.assertIn("army ant worker", avoid_targets)

    def test_growth_failed_scan_empty_level_memory_relaxes_next_target_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir) / "run"
            run_dir = base_dir / "cases" / "case-a"
            failed_dir = base_dir / "failed-attempts" / "case-a" / "segment-008-attempt-001"
            encounter_dir = failed_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            (encounter_dir / "segment-008-growthhib-1.jsonl").write_text(
                json.dumps(
                    {
                        "event": "hunter_target_scan_empty",
                        "hunter_visible_npcs": 8,
                        "hunter_eligible_npcs": 0,
                        "hunter_reject_counts": {"visible": 8, "eligible": 0, "level": 8},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_failure_target_memory_attempts=8,
                growth_current_segment_index=8,
                run_dir=str(run_dir),
                case_name="case-a",
                growth_party_carry_count=0,
            )

            self.assertEqual(growth.growth_failed_attempt_scan_empty_level_count(args), 1)
            adjusted = growth.adjust_growth_target_plan_for_failed_level_scan(args, 4, 8, 3, 4, 0)

        self.assertEqual(adjusted, (2, 2, 2))

    def test_growth_runtime_failure_memory_blocks_target_through_ttl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-06-29T00:00:00Z,case-a,mid,1,9,7,target_removed_no_xp,avoid_target,vein spider,5,combat_csv,12\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=12,
            )

            active_avoid = growth.growth_runtime_failure_memory_avoid_targets(args, "mid", 7, 1)
            args.growth_current_segment_index = 13
            expired_avoid = growth.growth_runtime_failure_memory_avoid_targets(args, "mid", 7, 1)

        self.assertIn("vein spider", active_avoid)
        self.assertNotIn("vein spider", expired_avoid)

    def test_growth_runtime_failure_memory_ignores_below_reward_floor_no_xp_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-06-29T00:00:00Z,case-a,hib,2,30,5,target_removed_no_xp,avoid_target,small freshwater crab,4,combat_csv,33\n"
                "2026-06-29T00:00:01Z,case-a,hib,2,30,5,combat_no_kill,avoid_target,skeletal minion,4,combat_csv,33\n"
                "2026-06-29T00:00:02Z,case-a,hib,2,30,5,combat_no_kill,avoid_target,orchard nipper,5,combat_csv,33\n"
                "2026-06-29T00:00:03Z,case-a,hib,2,30,5,death_pressure,avoid_target,lough wolf,4,encounter,33\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=31,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                current_party_size=2,
            )

            active_avoid = growth.growth_runtime_failure_memory_avoid_targets(args, "hib", 5, 2)

        self.assertNotIn("small freshwater crab", active_avoid)
        self.assertNotIn("skeletal minion", active_avoid)
        self.assertIn("orchard nipper", active_avoid)
        self.assertIn("lough wolf", active_avoid)

    def test_growth_runtime_failure_memory_ignores_successful_death_pressure_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            memory_path = base / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-06-29T00:00:00Z,case-a,hib,2,30,5,death_pressure,avoid_target,water beetle collector,0,encounter_death_message,33\n"
                "2026-06-29T00:00:01Z,case-a,hib,2,30,5,death_pressure,avoid_target,huldu lurker,0,encounter_death_message,33\n",
                encoding="utf-8",
            )
            (base / "segment-030-combat.csv").write_text(
                "username,round,target_id,target_name,target_level,outcome,duration_seconds,attacks,skills,start_distance,end_distance\n"
                "growthhib70481,1,100,water beetle collector,5,critical_health_drop_aggro,4.4,14,2,389,50\n"
                "growthhib70481,1,101,water beetle collector,5,target_removed,31.3,120,11,1634,17\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=31,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                current_party_size=2,
            )

            active_avoid = growth.growth_runtime_failure_memory_avoid_targets(args, "hib", 5, 2)

        self.assertNotIn("water beetle collector", active_avoid)
        self.assertIn("huldu lurker", active_avoid)

    def test_growth_failed_attempt_memory_ignores_below_reward_floor_no_xp_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            run_dir = base / "cases" / "case-a"
            attempt_dir = base / "failed-attempts" / "case-a" / "segment-030-attempt-001"
            attempt_dir.mkdir(parents=True)
            (attempt_dir / "timeline.csv").write_text(
                "case,segment,account,level_after,xp_effective_delta,target_removed,bottleneck_reason\n"
                "case-a,30,growthhib,5,0,0,target_removed_no_xp\n",
                encoding="utf-8",
            )
            (attempt_dir / "segment-030-combat.csv").write_text(
                "username,round,target_id,target_name,target_level,outcome,duration_seconds,attacks,skills,start_distance,end_distance\n"
                "growthhib,1,100,small freshwater crab,4,target_removed_no_reward,10.0,40,2,100,80\n"
                "growthhib,1,101,orchard nipper,5,target_removed_no_reward,10.0,40,2,100,80\n"
                "growthhib,1,102,lough wolf,4,critical_health_drop_aggro,10.0,40,2,100,80\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_failure_target_memory_attempts=8,
                growth_current_segment_index=30,
                run_dir=str(run_dir),
                case_name="case-a",
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                current_party_size=2,
            )

            active_avoid = growth.growth_failed_target_memory_avoid_targets(args, "hib", 5, 2)

        self.assertNotIn("small freshwater crab", active_avoid)
        self.assertIn("orchard nipper", active_avoid)
        self.assertIn("lough wolf", active_avoid)

    def test_growth_runtime_failure_memory_downgrades_no_engagement_target_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-06-29T00:00:00Z,case-a,hib,8,5,4,no_engagement,downgrade_target_plan,,,timeline,6\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=6,
                current_realm_key="hib",
                growth_party_carry_count=0,
                growth_allow_lower_xp_gear_farm=False,
            )

            adjusted = growth.adjust_growth_target_plan_for_failed_level_scan(args, 4, 8, 3, 4, 0)

        self.assertEqual(adjusted, (2, 2, 2))

    def test_growth_failed_scan_memory_can_break_party_carry_floor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-06-29T00:00:00Z,case-a,alb,8,9,1,no_engagement,downgrade_target_plan,,,timeline,10\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=10,
                current_realm_key="alb",
            )

            adjusted = growth.adjust_growth_target_plan_for_failed_level_scan(args, 1, 8, 3, 3, 2)

        self.assertEqual(adjusted, (1, 1, 2))

    def test_growth_failed_scan_memory_relaxes_repeated_party_carry_scan_empty_cases(self) -> None:
        cases = (
            ("alb", 2, 7, (13, 13, 1), (8, 8, 1)),
            ("mid", 4, 8, (14, 14, 2), (9, 9, 2)),
            ("hib", 4, 7, (14, 14, 2), (9, 9, 2)),
            ("hib", 2, 3, (10, 10, 6), (5, 5, 6)),
        )
        for realm_key, party_size, level, plan, expected in cases:
            with self.subTest(realm=realm_key, party=party_size, level=level):
                with tempfile.TemporaryDirectory() as temp_dir:
                    memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
                    rows = [
                        "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                    ]
                    for index in range(5):
                        rows.append(
                            f"2026-06-29T00:00:0{index}Z,case-a,{realm_key},{party_size},9,{level},"
                            "scan_empty,downgrade_target_plan,,,timeline,10\n"
                        )
                    memory_path.write_text("".join(rows), encoding="utf-8")
                    args = SimpleNamespace(
                        growth_failure_target_memory=True,
                        growth_runtime_failure_memory_csv=str(memory_path),
                        growth_current_segment_index=10,
                        current_realm_key=realm_key,
                        growth_party_carry_level_offset=12,
                        current_party_size=party_size,
                        growth_party_carry_count=-1,
                        growth_equip_party_carry_gear=True,
                    )

                    adjusted = growth.adjust_growth_target_plan_for_failed_level_scan(
                        args,
                        level,
                        party_size,
                        int(plan[0]),
                        int(plan[1]),
                        int(plan[2]),
                    )

                self.assertEqual(adjusted, expected)

    def test_ungeared_party_carry_failed_scan_memory_keeps_xp_target_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-06-29T00:00:00Z,case-a,mid,8,16,2,scan_empty,downgrade_target_plan,,,timeline,17\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=16,
                current_realm_key="mid",
                growth_party_carry_level_offset=12,
                current_party_size=8,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
            )

            adjusted = growth.adjust_growth_target_plan_for_failed_level_scan(args, 2, 8, 3, 4, 1)

        self.assertEqual(adjusted, (3, 4, 1))

    def test_ungeared_party_carry_death_pressure_clamps_to_xp_floor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-06-29T00:00:00Z,case-a,alb,4,17,6,death_pressure,avoid_target,river racer,7,encounter,18\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=18,
                current_realm_key="alb",
                growth_party_carry_level_offset=12,
                current_party_size=4,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
            )

            adjusted = growth.adjust_growth_target_plan_for_failed_level_scan(args, 6, 4, 5, 6, 1)

        self.assertEqual(adjusted, (5, 5, 0))

    def test_low_ungeared_party_carry_death_pressure_clamps_to_tracked_floor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-06-29T00:00:00Z,case-a,mid,8,18,2,death_pressure,avoid_target,wood-eater,3,encounter,21\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=18,
                current_realm_key="mid",
                growth_party_carry_level_offset=12,
                current_party_size=8,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_allow_lower_xp_gear_farm=True,
            )

            adjusted = growth.adjust_growth_target_plan_for_failed_level_scan(args, 2, 8, 3, 4, 1)

        self.assertEqual(adjusted, (2, 2, 0))

    def test_solo_death_pressure_lower_gear_farm_uses_non_grey_floor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-06-29T00:00:00Z,case-a,mid,1,27,7,death_pressure,avoid_target,black mauler juvenile,5,encounter,28\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=28,
                current_realm_key="mid",
                growth_party_carry_count=0,
                growth_equip_party_carry_gear=False,
                growth_allow_lower_xp_gear_farm=True,
            )

            adjusted = growth.adjust_growth_target_plan_for_failed_level_scan(args, 7, 1, 6, 6, 0)

        self.assertEqual(adjusted, (5, 5, 0))

    def test_solo_scan_empty_lower_gear_farm_uses_non_grey_floor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-06-29T00:00:00Z,case-a,mid,1,32,0,scan_empty,downgrade_target_plan,,,encounter,35\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=32,
                current_realm_key="mid",
                growth_party_carry_count=0,
                growth_equip_party_carry_gear=False,
                growth_allow_lower_xp_gear_farm=True,
            )

            adjusted = growth.adjust_growth_target_plan_for_failed_level_scan(args, 7, 1, 6, 6, 0)

        self.assertEqual(adjusted, (5, 5, 1))

    def test_record_growth_runtime_failure_memory_records_xp_void_success_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            combat_path = Path(temp_dir) / "segment-009-combat.csv"
            combat_path.write_text(
                "username,round,target_id,target_name,target_level,outcome,duration_seconds,attacks,skills,start_distance,end_distance\n"
                "growthmid,1,100,vein spider,5,target_removed,10.0,40,2,100,80\n",
                encoding="utf-8",
            )

            growth.record_growth_runtime_failure_memory_for_segment(
                memory_path,
                case_name="case-a",
                realm_key="mid",
                party_size=1,
                segment_index=9,
                current_level=7,
                bottleneck_reasons={"target_removed_no_xp"},
                combat_csv=combat_path,
            )
            with memory_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["action"], "avoid_target")
        self.assertEqual(rows[0]["target_name"], "vein spider")
        self.assertEqual(rows[0]["expires_segment"], str(9 + growth.GROWTH_RUNTIME_FAILURE_MEMORY_TTL_SEGMENTS))

    def test_record_growth_runtime_failure_memory_records_no_reward_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            combat_path = Path(temp_dir) / "segment-009-combat.csv"
            combat_path.write_text(
                "username,round,target_id,target_name,target_level,outcome,duration_seconds,attacks,skills,start_distance,end_distance\n"
                "growthmid,1,100,vein spider,5,target_removed_no_reward,10.0,40,2,100,80\n",
                encoding="utf-8",
            )

            growth.record_growth_runtime_failure_memory_for_segment(
                memory_path,
                case_name="case-a",
                realm_key="mid",
                party_size=1,
                segment_index=9,
                current_level=7,
                bottleneck_reasons={"target_removed_no_xp"},
                combat_csv=combat_path,
            )
            with memory_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["action"], "avoid_target")
        self.assertEqual(rows[0]["target_name"], "vein spider")
        self.assertEqual(rows[0]["reason"], "target_removed_no_xp")

    def test_record_growth_runtime_failure_memory_no_xp_skips_hard_failure_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            combat_path = Path(temp_dir) / "segment-009-combat.csv"
            combat_path.write_text(
                "username,round,target_id,target_name,target_level,outcome,duration_seconds,attacks,skills,start_distance,end_distance\n"
                "growthhib,1,100,small freshwater crab,4,target_removed_no_reward,10.0,40,2,100,80\n"
                "growthhib,1,101,Summoner,4,critical_health_drop_aggro,10.0,40,2,100,80\n",
                encoding="utf-8",
            )

            growth.record_growth_runtime_failure_memory_for_segment(
                memory_path,
                case_name="case-a",
                realm_key="hib",
                party_size=2,
                segment_index=30,
                current_level=5,
                bottleneck_reasons={"target_removed_no_xp"},
                combat_csv=combat_path,
            )
            with memory_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["target_name"], "small freshwater crab")

    def test_write_growth_segment_summary_json_captures_route_result_and_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            memory_path = base / "runtime-failure-memory.csv"
            combat_path = base / "segment-093-combat.csv"
            summary_path = base / "segment-093-summary.json"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-06T04:45:16Z,alb-p1,alb,1,90,10,combat_no_kill,avoid_target,bear,8,combat_csv,93\n",
                encoding="utf-8",
            )
            combat_path.write_text(
                "username,round,target_id,target_name,target_level,outcome,duration_seconds,attacks,skills,start_distance\n"
                "growthalb701,1,1439,river racer,7,target_removed,19.7,69,6,255\n"
                "growthalb701,1,22528,river racer,7,critical_health_drop_aggro,13.0,67,5,210\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=93,
            )
            route = growth.RoutePoint(
                10,
                440220,
                619503,
                1863,
                "river racer",
                "bear",
                "Caer Ulfwych",
                source="hunting-index",
                mob_level=7,
                mob_count=2,
            )
            metrics = {
                "target_removed": 1,
                "loot_acquired": 1,
                "combat_engagements": 2,
                "damage_done": 115,
                "damage_taken": 250,
                "player_deaths": 0,
                "movement_failures": 0,
                "target_timeouts": 0,
                "action_critical_health_drop_aggro": 1,
                "action_required_target_pre_hunt_recover": 5,
                "action_target_removed": 1,
                "action_loot_acquired": 1,
            }

            growth.write_growth_segment_summary_json(
                summary_path,
                args=args,
                case_name="alb-p1",
                realm=growth.REALMS["alb"],
                party_size=1,
                segment_index=93,
                current_level=10,
                route_level=10,
                route=route,
                metrics=metrics,
                combat_csv=combat_path,
                bottleneck_reasons={"combat_no_kill"},
                xp_effective_delta=1234,
                xp_effective_by_account={"growthalb701": 1234},
                require_kill=True,
                require_xp=True,
                aggregate_xp_ok=True,
                account_xp_ok=True,
                rc=0,
            )
            payload = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["route"]["prefer"], "river racer")
        self.assertEqual(payload["route"]["nearby_avoid"], "river racer")
        self.assertEqual(payload["result"]["target_removed"], 1)
        self.assertEqual(payload["combat"]["outcomes"]["target_removed"], 1)
        self.assertEqual(payload["combat"]["outcomes"]["critical_health_drop_aggro"], 1)
        self.assertEqual(payload["actions"]["required_target_pre_hunt_recover"], 5)
        self.assertEqual(payload["failure_memory"][0]["target_name"], "bear")
        self.assertEqual(payload["next_recommendation"], "continue_same_route_once_watch_health_pressure")

    def test_record_growth_runtime_failure_memory_records_death_killer_from_encounter_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            memory_path = base / "runtime-failure-memory.csv"
            combat_path = base / "segment-009-combat.csv"
            case_dir = base / "case-a"
            encounter_dir = case_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            combat_path.write_text(
                "username,round,target_id,target_name,target_level,outcome,duration_seconds,attacks,skills,start_distance,end_distance\n"
                "growthmid,1,100,hobgoblin snake-finder,1,player_death,2.0,3,1,60,60\n",
                encoding="utf-8",
            )
            (encounter_dir / "segment-009-growthmid-1.jsonl").write_text(
                json.dumps(
                    {
                        "event": "server_message",
                        "text": "GrowthMid70788이 a huldu lurker에게 사망했습니다.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            growth.record_growth_runtime_failure_memory_for_segment(
                memory_path,
                case_name="case-a",
                realm_key="mid",
                party_size=8,
                segment_index=9,
                current_level=1,
                bottleneck_reasons={"death_pressure"},
                combat_csv=combat_path,
                case_dir=case_dir,
            )
            with memory_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        huldu_rows = [row for row in rows if row["target_name"] == "huldu lurker"]
        self.assertEqual(len(huldu_rows), 1)
        self.assertEqual(huldu_rows[0]["source"], "encounter_death_message")
        self.assertEqual(huldu_rows[0]["expires_segment"], "12")

    def test_record_growth_runtime_failure_memory_does_not_avoid_successful_death_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            memory_path = base / "runtime-failure-memory.csv"
            combat_path = base / "segment-030-combat.csv"
            case_dir = base / "case-a"
            encounter_dir = case_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            (case_dir / "primary-accounts.csv").write_text(
                "username,password,realm,char_index,class_id,class_name,specs,start_x,start_y,start_z,zone_id,growth_role\n"
                "growthhib70481,dummy-pass,3,20,44,Hero,Blades|50,0,0,0,200,carry\n",
                encoding="utf-8",
            )
            combat_path.write_text(
                "username,round,target_id,target_name,target_level,outcome,duration_seconds,attacks,skills,start_distance,end_distance\n"
                "growthhib70481,1,100,water beetle collector,5,critical_health_drop_aggro,4.4,14,2,389,50\n"
                "growthhib70481,1,101,water beetle collector,5,target_removed,31.3,120,11,1634,17\n",
                encoding="utf-8",
            )
            (encounter_dir / "segment-030-growthhib70481-1.jsonl").write_text(
                json.dumps(
                    {
                        "event": "server_message",
                        "text": "GrowthHib70481이 a water beetle collector에게 사망했습니다.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            growth.record_growth_runtime_failure_memory_for_segment(
                memory_path,
                case_name="case-a",
                realm_key="hib",
                party_size=2,
                segment_index=30,
                current_level=5,
                bottleneck_reasons={"death_pressure"},
                combat_csv=combat_path,
                case_dir=case_dir,
            )
            rows = []
            if memory_path.exists():
                with memory_path.open("r", encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))

        self.assertFalse(any(row["target_name"] == "water beetle collector" for row in rows))

    def test_record_growth_runtime_failure_memory_records_offtarget_actor_before_objective(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            memory_path = base / "runtime-failure-memory.csv"
            combat_path = base / "segment-030-combat.csv"
            case_dir = base / "case-a"
            encounter_dir = case_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            combat_path.write_text(
                "username,round,target_id,target_name,target_level,outcome,duration_seconds,attacks,skills,start_distance,end_distance\n"
                "growthhib,1,100,mudman,4,timeout,150.0,20,1,5800,200\n",
                encoding="utf-8",
            )
            (encounter_dir / "segment-030-growthhib-1.jsonl").write_text(
                json.dumps(
                    {
                        "event": "unengaged_pull_offtarget_damage",
                        "reason": "unengaged_pull_offtarget_damage",
                        "rescue_target_name": "feckless lucragan",
                        "rescue_target_level": 5,
                        "target_name": "mudman",
                        "target_level": 4,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            growth.record_growth_runtime_failure_memory_for_segment(
                memory_path,
                case_name="case-a",
                realm_key="hib",
                party_size=2,
                segment_index=30,
                current_level=5,
                bottleneck_reasons={"combat_no_kill"},
                combat_csv=combat_path,
                case_dir=case_dir,
            )
            with memory_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual([row["target_name"] for row in rows], ["feckless lucragan"])
        self.assertEqual(rows[0]["source"], "encounter_offtarget_damage")
        self.assertEqual(rows[0]["reason"], "combat_no_kill")

    def test_growth_runtime_failure_memory_ignores_other_case_death_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            memory_path = base / "runtime-failure-memory.csv"
            combat_path = base / "segment-009-combat.csv"
            case_dir = base / "case-a"
            encounter_dir = case_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            (case_dir / "primary-accounts.csv").write_text(
                "username,password,realm,char_index,class_id,class_name,specs,start_x,start_y,start_z,zone_id,growth_role\n"
                "growthhib70481,dummy-pass,3,20,44,Hero,Blades|50,0,0,0,200,carry\n"
                "growthhib70482,dummy-pass,3,20,47,Druid,Regrowth|40,0,0,0,200,tracked\n",
                encoding="utf-8",
            )
            combat_path.write_text(
                "username,round,target_id,target_name,target_level,outcome,duration_seconds,attacks,skills,start_distance,end_distance\n",
                encoding="utf-8",
            )
            (encounter_dir / "segment-009-growthhib70481-1.jsonl").write_text(
                json.dumps(
                    {
                        "event": "server_message",
                        "text": "GrowthHib70241이 a 노련한 eirebug에게 사망했습니다.",
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "event": "server_message",
                        "text": "GrowthHib70481이 a 노련한 water beetle에게 사망했습니다.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            growth.record_growth_runtime_failure_memory_for_segment(
                memory_path,
                case_name="case-a",
                realm_key="hib",
                party_size=2,
                segment_index=9,
                current_level=5,
                bottleneck_reasons={"death_pressure"},
                combat_csv=combat_path,
                case_dir=case_dir,
            )
            with memory_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual([row["target_name"] for row in rows], ["water beetle"])
        self.assertEqual(rows[0]["source"], "encounter_death_message")

    def test_growth_clean_failure_actor_name_removes_unusable_prefixes(self) -> None:
        self.assertEqual(
            growth.growth_clean_failure_actor_name("\uFFFD\uFFFD\uFFFD\uFFFD\uFFFD bandit"),
            "bandit",
        )
        self.assertEqual(growth.growth_clean_failure_actor_name("노련한 emerald snake"), "emerald snake")

    def test_growth_failed_target_memory_ignores_non_engaged_flee_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir) / "run"
            run_dir = base_dir / "cases" / "case-a"
            failed_dir = base_dir / "failed-attempts" / "case-a" / "segment-013-attempt-001"
            failed_dir.mkdir(parents=True)
            (failed_dir / "segment-013-combat.csv").write_text(
                "username,round,target_id,target_name,target_level,outcome,duration_seconds,attacks,skills,start_distance,end_distance\n"
                "growthmid,1,100,army ant worker,6,flee,0.972,0,0,773,773\n"
                "growthmid,1,101,army ant worker,6,flee,1.214,0,0,801,801\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_failure_target_memory_attempts=8,
                growth_failure_target_memory_min_engagements=2,
                growth_current_segment_index=13,
                run_dir=str(run_dir),
                case_name="case-a",
            )

            avoid_targets = growth.growth_failed_target_memory_avoid_targets(args, "mid", 7, 1)

        self.assertNotIn("army ant worker", avoid_targets)

    def test_growth_failed_target_memory_is_cached_per_context_during_index_load(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,7,5,5,5,young grendelorm,5,15,776006,724447,4719,15,0,0,0,Bind Start,25348,950\n"
                "mid,1,7,5,5,5,vein spider,5,25,772957,725582,4754,25,0,0,0,Bind Start,24074,900\n"
                "mid,1,8,6,6,6,carrion crawler,6,20,786950,873259,4715,20,0,0,0,Mularn,1200,980\n",
                encoding="utf-8",
            )
            failed_dir = Path(temp_dir) / "run" / "failed-attempts" / "case-a" / "segment-016-attempt-001"
            failed_dir.mkdir(parents=True)
            (failed_dir / "segment-016-combat.csv").write_text(
                "username,round,target_id,target_name,target_level,outcome,duration_seconds,attacks,skills,start_distance,end_distance\n"
                "growthmid,1,100,young grendelorm,5,flee,12.0,10,2,100,80\n"
                "growthmid,1,101,young grendelorm,5,round_end,8.0,6,1,120,100\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_fast_travel="route-home",
                growth_failure_target_memory=True,
                growth_failure_target_memory_attempts=8,
                growth_failure_target_memory_min_engagements=2,
                growth_current_segment_index=16,
                run_dir=str(Path(temp_dir) / "run" / "cases" / "case-a"),
                case_name="case-a",
            )

            with mock.patch.object(
                growth,
                "growth_failed_target_memory_attempt_dirs",
                wraps=growth.growth_failed_target_memory_attempt_dirs,
            ) as attempt_dirs:
                growth.load_growth_hunting_index(args)

        self.assertEqual(attempt_dirs.call_count, 2)

    def test_route_preflight_skips_stale_hunting_index_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,7,5,5,5,young grendelorm,5,15,776006,724447,4719,15,0,0,0,Bind Start,25348,900\n"
                "mid,1,7,5,5,5,vein spider,5,25,772957,725582,4754,25,0,0,0,Bind Start,24074,800\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_preflight=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_allow_lower_xp_target_plan=True,
                growth_allow_lower_xp_gear_farm=True,
                growth_target_plan_override=(5, 5, 0),
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=2200.0,
                run_dir="",
            )

            def fake_preflight(url: str, timeout: float) -> object:
                del timeout
                if "young+grendelorm" in url:
                    return []
                if "vein+spider" in url:
                    return [{"name": "vein spider", "level": 5}]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(route.prefer, "vein spider")
        self.assertEqual(growth.strict_route_target_name(route, 7, party_size=1, realm_key="mid"), "vein spider")

    def test_route_preflight_skips_hazardous_live_camp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,7,5,5,5,young grendelorm,5,15,776006,724447,4719,15,0,0,0,Bind Start,25348,900\n"
                "mid,1,7,5,5,5,vein spider,5,25,767886,715928,5166,25,0,0,0,Bind Start,24074,800\n"
                "mid,1,7,5,5,5,wood-eater worker,4,31,786637,723034,4722,31,0,0,0,Mularn,17360,750\n"
                "mid,1,7,5,5,5,black mauler juvenile,5,26,731633,814288,5479,26,0,0,0,Fort Atla,12000,700\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_preflight=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=2500,
                growth_route_preflight_low_solo_radius=2500,
                growth_route_preflight_limit=3,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_allow_lower_xp_target_plan=True,
                growth_allow_lower_xp_gear_farm=True,
                growth_target_plan_override=(5, 5, 0),
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=2200.0,
                run_dir="",
            )

            def fake_preflight(url: str, timeout: float) -> object:
                del timeout
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                x = int((query.get("x") or ["0"])[0])
                if name == "young grendelorm":
                    return []
                if name == "vein spider":
                    return [{"name": "vein spider", "level": 5}]
                if name == "black mauler juvenile":
                    return [{"name": "black mauler juvenile", "level": 5}]
                if name == "wood-eater worker":
                    return [{"name": "wood-eater worker", "level": 4}]
                if name == "huldu" and x == 767886:
                    return [{"name": "huldu stalker", "level": 6}]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(route.prefer, "vein spider")
        self.assertEqual(route.mob_level, 5)

    def test_route_preflight_skips_party_carry_floor_hazard(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(
                growth_route_preflight=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_low_solo_radius=2500,
                growth_route_preflight_limit=3,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_fast_travel="route-home",
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_target_level_override=5,
                growth_target_plan_override=(5, 5, 0),
                growth_party_carry_level_offset=12,
                current_party_size=2,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                run_dir=temp_dir,
                case_name="duo-s150-hib-r001",
            )
            route = growth.route_point(
                6,
                331797,
                467208,
                5247,
                "eirebug",
                "spraggon,feccan",
                source="hunting-index",
                mob_level=5,
                mob_count=18,
            )

            def fake_preflight(url: str, timeout: float) -> object:
                del timeout
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                if name == "eirebug":
                    return [{"name": "eirebug", "level": 5}]
                if name == "spraggon":
                    return [{"name": "spraggon", "level": 12}]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                status = growth.growth_route_preflight_status(
                    args,
                    route,
                    realm=growth.REALMS["hib"],
                    current_level=5,
                    party_size=2,
                )

        self.assertFalse(status)

    def test_route_preflight_rejects_sparse_party_carry_target_pool(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(
                growth_route_preflight=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_low_solo_radius=2500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_fast_travel="route-home",
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                nav_api_url="http://127.0.0.1:5000",
                run_dir=temp_dir,
            )
            route = growth.route_point(
                5,
                348002,
                535114,
                4673,
                "water beetle collector",
                "spraggon",
                "Tir na mBeo",
                source="hunting-index",
                mob_level=5,
                mob_count=1,
            )

            def fake_preflight(url: str, _timeout: float) -> object:
                if "name=water+beetle+collector" in url or "name=water%20beetle%20collector" in url:
                    return [{"name": "water beetle collector", "level": 5, "x": 350688, "y": 534196, "z": 4598}]
                return []

            with (
                mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight),
                mock.patch.object(growth, "sample_route_z", return_value=4598),
            ):
                status = growth.growth_route_preflight_status(
                    args,
                    route,
                    realm=growth.REALMS["hib"],
                    current_level=5,
                    party_size=2,
                )

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertFalse(status)
        self.assertIn("live_target_insufficient:water beetle collector", log_text)

    def test_mid_duo_level_ten_exact_preflight_uses_wider_sample_for_prefix_mix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(
                growth_route_preflight=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=2200,
                growth_route_preflight_low_solo_radius=2500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                nav_api_url="http://127.0.0.1:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=2200.0,
                run_dir=temp_dir,
            )
            route = growth.mid_level_ten_tawny_lynx_party_route()
            observed_limits: list[int] = []

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                limit = int((query.get("limit") or ["0"])[0])
                if name == "tawny lynx":
                    observed_limits.append(limit)
                    if limit < 10:
                        return [
                            {"name": "노련한 tawny lynx", "level": 9, "x": 790100, "y": 850000, "z": 4820},
                            {"name": "tawny lynx", "level": 8, "x": 780200, "y": 850000, "z": 4820},
                            {"name": "노련한 tawny lynx", "level": 9, "x": 790300, "y": 850000, "z": 4820},
                        ]
                    return [
                        {"name": "노련한 tawny lynx", "level": 9, "x": 790100, "y": 850000, "z": 4820},
                        {"name": "노련한 tawny lynx", "level": 9, "x": 790300, "y": 850000, "z": 4820},
                        {"name": "tawny lynx", "level": 8, "x": 780200, "y": 850000, "z": 4820},
                        {"name": "tawny lynx", "level": 8, "x": 780400, "y": 850000, "z": 4820},
                        {"name": "tawny lynx", "level": 8, "x": 780500, "y": 850000, "z": 4820},
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                status = growth.growth_route_preflight_status(
                    args,
                    route,
                    realm=growth.REALMS["mid"],
                    current_level=10,
                    party_size=2,
                )

        self.assertTrue(status)
        self.assertTrue(observed_limits)
        self.assertGreaterEqual(observed_limits[0], 10)

    def test_route_preflight_preserves_live_anchor_z_for_mismatched_target_pool(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(
                growth_route_preflight=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_low_solo_radius=2500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_fast_travel="route-home",
                ground_z_offset=0,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                nav_api_url="http://127.0.0.1:5000",
                run_dir=temp_dir,
            )
            route = growth.route_point(
                5,
                348002,
                535114,
                4673,
                "water beetle collector",
                "spraggon",
                "Tir na mBeo",
                source="hunting-index",
                mob_level=5,
                mob_count=1,
            )

            def fake_preflight(url: str, _timeout: float) -> object:
                if "name=water+beetle+collector" in url or "name=water%20beetle%20collector" in url:
                    return [
                        {"name": "water beetle collector", "level": 5, "x": 350688, "y": 534196, "z": 4598},
                        {"name": "water beetle collector", "level": 5, "x": 350720, "y": 534220, "z": 4598},
                        {"name": "water beetle collector", "level": 5, "x": 350760, "y": 534260, "z": 4598},
                    ]
                return []

            with (
                mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight),
                mock.patch.object(growth, "sample_route_z", return_value=3586),
            ):
                status = growth.growth_route_preflight_status(
                    args,
                    route,
                    realm=growth.REALMS["hib"],
                    current_level=5,
                    party_size=2,
                )
                adjusted = growth.growth_route_preflight_adjusted_route(
                    args,
                    route,
                    realm=growth.REALMS["hib"],
                    current_level=5,
                    party_size=2,
                )

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertTrue(status)
        self.assertTrue(adjusted.live_anchor_z)
        self.assertEqual(growth.route_home_string_for_point(growth.REALMS["hib"], adjusted), "350688,534196,4598")
        self.assertIn("live_target_z_preserved:water beetle collector", log_text)
        self.assertIn("live_target_present:water beetle collector", log_text)
        self.assertIn("target_z=4598", log_text)
        self.assertIn("ground_z=3586", log_text)
        self.assertIn("delta=1012", log_text)
        self.assertIn("max=500", log_text)

    def test_route_preflight_anchors_low_solo_route_to_live_target_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,7,5,5,5,vein spider,5,25,772957,725582,4754,25,0,0,0,Bind Start,24074,900\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=2500,
                growth_route_preflight_low_solo_radius=2500,
                growth_route_preflight_limit=3,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_allow_lower_xp_target_plan=True,
                growth_allow_lower_xp_gear_farm=True,
                growth_target_plan_override=(5, 5, 0),
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=2200.0,
                run_dir="",
            )
            target_queries: list[dict[str, list[str]]] = []

            def fake_preflight(url: str, timeout: float) -> object:
                del timeout
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                if name == "vein spider":
                    target_queries.append(query)
                    return [
                        {
                            "name": "vein spider",
                            "level": 5,
                            "x": 772812,
                            "y": 725190,
                            "z": 4764,
                            "distance": 2350,
                        }
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(route.prefer, "vein spider")
        self.assertEqual(route.mob_level, 5)
        self.assertEqual((route.x, route.y, route.z), (772812, 725190, 4764))
        self.assertTrue(any(query.get("minLevel") == ["5"] and query.get("maxLevel") == ["5"] for query in target_queries))

    def test_route_preflight_anchor_prefers_available_target_over_in_combat_nearest(self) -> None:
        args = SimpleNamespace(
            growth_fast_travel="route-home",
            growth_route_preflight_anchor=True,
            growth_route_case_index=0,
            case_name="",
        )
        route = growth.RoutePoint(
            7,
            813800,
            688337,
            5922,
            "vein spider",
            "",
            "Fort Veldon",
            source="hunting-index",
            mob_level=5,
            mob_count=9,
        )

        growth.store_growth_route_preflight_anchor(
            args,
            route,
            (
                {
                    "name": "vein spider",
                    "level": 5,
                    "x": 810580,
                    "y": 688342,
                    "z": 5632,
                    "distance": 3220,
                    "inCombat": True,
                    "hasAggro": True,
                    "target": "GrowthMid61121",
                    "healthPercent": 52,
                },
                {
                    "name": "vein spider",
                    "level": 5,
                    "x": 809591,
                    "y": 687883,
                    "z": 5533,
                    "distance": 4233,
                    "inCombat": False,
                    "hasAggro": False,
                    "target": "",
                    "healthPercent": 100,
                },
            ),
            realm_key="mid",
            current_level=7,
            party_size=1,
        )

        adjusted = growth.growth_route_preflight_adjusted_route(
            args,
            route,
            realm=growth.REALMS["mid"],
            current_level=7,
            party_size=1,
        )

        self.assertEqual((adjusted.x, adjusted.y, adjusted.z), (809591, 687883, 5533))
        self.assertEqual(adjusted.mob_count, 9)

    def test_route_preflight_anchor_spreads_solo_cases_across_available_targets(self) -> None:
        args = SimpleNamespace(
            growth_fast_travel="route-home",
            growth_route_preflight_anchor=True,
            growth_route_case_index=1,
            case_name="",
        )
        route = growth.RoutePoint(
            7,
            813800,
            688337,
            5922,
            "vein spider",
            "",
            "Fort Veldon",
            source="hunting-index",
            mob_level=5,
        )

        growth.store_growth_route_preflight_anchor(
            args,
            route,
            (
                {"name": "vein spider", "level": 5, "x": 809591, "y": 687883, "z": 5533, "distance": 4233},
                {"name": "vein spider", "level": 5, "x": 812964, "y": 681924, "z": 5095, "distance": 6467},
            ),
            realm_key="mid",
            current_level=7,
            party_size=1,
        )

        adjusted = growth.growth_route_preflight_adjusted_route(
            args,
            route,
            realm=growth.REALMS["mid"],
            current_level=7,
            party_size=1,
        )

        self.assertEqual((adjusted.x, adjusted.y, adjusted.z), (812964, 681924, 5095))

    def test_route_home_low_solo_preflight_uses_wide_anchor_search(self) -> None:
        args = SimpleNamespace(
            growth_fast_travel="route-home",
            max_target_distance=2200.0,
        )
        route = growth.RoutePoint(
            7,
            772957,
            725582,
            4754,
            "vein spider",
            "",
            "Bind Start",
            source="hunting-index",
            mob_level=5,
        )

        self.assertEqual(
            growth.growth_route_preflight_radius(
                args,
                route,
                realm_key="mid",
                current_level=7,
                party_size=1,
            ),
            6500,
        )
        self.assertEqual(growth.growth_route_home_low_solo_target_cap(args, 7, 1, "mid", route), 6500.0)
        self.assertEqual(growth.growth_max_target_distance(args, 7, 1, "mid", route), 6500.0)
        self.assertEqual(growth.growth_combat_chase_max_distance(7, 1, args, "mid", route), 0.0)

    def test_mid_solo_level_seven_lower_xp_route_uses_nearby_runtime_cap(self) -> None:
        args = SimpleNamespace(
            growth_fast_travel="route-home",
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            growth_route_preflight_limit=3,
            max_target_distance=2200.0,
            target_home_max_distance=1400.0,
            combat_home_leash_distance=1200.0,
        )
        route = growth.RoutePoint(
            7,
            772957,
            725582,
            4754,
            "vein spider",
            "",
            "Bind Start",
            source="hunting-index",
            mob_level=5,
        )

        self.assertEqual(
            growth.growth_route_preflight_radius(
                args,
                route,
                realm_key="mid",
                current_level=7,
                party_size=1,
            ),
            6500,
        )
        self.assertEqual(
            growth.growth_route_preflight_limit_for_route(
                args,
                route,
                realm_key="mid",
                current_level=7,
                party_size=1,
            ),
            10,
        )
        self.assertEqual(growth.growth_max_target_distance(args, 7, 1, "mid", route), 2800.0)
        self.assertEqual(growth.growth_target_home_max_distance(args, 7, 1, "mid", route), 2800.0)
        self.assertEqual(growth.growth_required_target_home_hunt_distance(args, 7, 1, "mid", route), 2800.0)
        self.assertEqual(growth.growth_hunter_target_api_radius(args, 7, 1, "mid", route), 2800.0)
        self.assertEqual(growth.growth_hunter_target_api_engage_distance(args, 7, 1, "mid", route), 2800.0)
        self.assertEqual(growth.growth_combat_home_leash_distance_for_route(args, 7, 1, "mid", route), 2800.0)
        self.assertEqual(growth.growth_flee_pressure_health_percent_for_route(args, 7, 1, "mid", route), 60)

    def test_mid_carrion_crawler_low_solo_route_home_keeps_live_anchor_target_cap(self) -> None:
        args = SimpleNamespace(
            growth_fast_travel="route-home",
            max_target_distance=2200.0,
        )
        route = growth.RoutePoint(
            7,
            787192,
            868637,
            6698,
            "carrion crawler",
            "",
            "Gotar",
            source="hunting-index",
            mob_level=6,
        )

        self.assertEqual(growth.growth_route_home_low_solo_target_cap(args, 7, 1, "mid", route), 6500.0)
        self.assertEqual(growth.growth_max_target_distance(args, 7, 1, "mid", route), 6500.0)

    def test_route_home_party_preflight_uses_live_anchor(self) -> None:
        args = SimpleNamespace(
            growth_fast_travel="route-home",
            growth_route_preflight_anchor=True,
        )
        route = growth.RoutePoint(
            7,
            787192,
            868637,
            6698,
            "carrion crawler",
            "",
            "Gotar",
            source="hunting-index",
            mob_level=6,
        )

        self.assertTrue(
            growth.growth_route_preflight_anchor_enabled(
                args,
                route=route,
                current_level=7,
                party_size=4,
            )
        )

    def test_hib_low_solo_route_home_shortage_recovery_uses_wide_combat_chase(self) -> None:
        args = SimpleNamespace(
            growth_fast_travel="route-home",
            max_target_distance=2200.0,
        )
        route = growth.RoutePoint(
            1,
            344500,
            474500,
            5372,
            "large frog",
            "",
            "Mag Mell",
            source="hunting-index",
            mob_level=0,
        )

        self.assertEqual(growth.growth_max_target_distance(args, 2, 1, "hib", route), 6500.0)
        self.assertEqual(growth.growth_combat_chase_max_distance(2, 1, args, "hib", route), 6500.0)

    def test_route_preflight_checks_hazards_around_live_anchor(self) -> None:
        args = SimpleNamespace(
            growth_fast_travel="route-home",
            growth_route_preflight=True,
            growth_route_preflight_anchor=True,
            growth_route_preflight_timeout=0.1,
            growth_route_preflight_radius=0,
            growth_route_preflight_low_solo_radius=2500,
            growth_route_preflight_limit=3,
            growth_route_preflight_hazard_radius=2500,
            growth_route_preflight_hazard_limit=3,
            growth_route_preflight_hazard_token_limit=1,
            dry_run=False,
            nav_api_url="http://dummy-api:5000",
            host="127.0.0.1",
            api_port=5000,
            max_target_distance=2200.0,
            run_dir="",
        )
        route = growth.RoutePoint(
            7,
            772957,
            725582,
            4754,
            "vein spider",
            "huldu,young grendelorm",
            "Bind Start",
            source="hunting-index",
            mob_level=5,
        )
        target_queries: list[dict[str, list[str]]] = []
        hazard_queries: list[dict[str, list[str]]] = []

        def fake_preflight(url: str, timeout: float) -> object:
            del timeout
            query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            name = (query.get("name") or [""])[0]
            if name == "vein spider":
                target_queries.append(query)
                return [
                    {
                        "name": "vein spider",
                        "level": 5,
                        "x": 775767,
                        "y": 727292,
                        "z": 4712,
                        "distance": 3289,
                    }
                ]
            if name == "young grendelorm":
                hazard_queries.append(query)
                if query.get("x") == ["775767"] and query.get("y") == ["727292"]:
                    return [{"name": "young grendelorm", "level": 7, "x": 774447, "y": 727403, "z": 4700}]
            return []

        with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
            checked = growth.growth_route_preflight_checked_route(
                args,
                route,
                realm=growth.REALMS["mid"],
                current_level=7,
                party_size=1,
            )

        self.assertIsNone(checked)
        expected_radius = str(
            growth.growth_route_preflight_radius(
                args,
                route,
                realm_key="mid",
                current_level=7,
                party_size=1,
            )
        )
        self.assertTrue(any(query.get("radius") == [expected_radius] for query in target_queries))
        self.assertTrue(any(query.get("x") == ["775767"] and query.get("y") == ["727292"] for query in hazard_queries))

    def test_route_preflight_reanchors_to_safe_live_target_when_nearest_has_hazard(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(
                growth_fast_travel="route-home",
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_low_solo_radius=2500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=1,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=1,
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                run_dir=temp_dir,
            )
            route = growth.route_point(
                5,
                348694,
                498242,
                4620,
                "water beetle collector",
                "lough wolf",
                "Mag Mell",
                source="hunting-index",
                mob_level=5,
                mob_count=10,
            )

            def fake_preflight(url: str, timeout: float) -> object:
                del timeout
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                x = (query.get("x") or [""])[0]
                y = (query.get("y") or [""])[0]
                if name == "water beetle collector":
                    return [
                        {
                            "name": "water beetle collector",
                            "level": 5,
                            "x": 348442,
                            "y": 497904,
                            "z": 4598,
                            "distance": 100,
                        },
                        {
                            "name": "water beetle collector",
                            "level": 5,
                            "x": 348623,
                            "y": 498337,
                            "z": 4598,
                            "distance": 200,
                        },
                    ]
                if name == "lough wolf" and x == "348442" and y == "497904":
                    return [{"name": "lough wolf", "level": 7, "x": 348800, "y": 498000, "z": 4598}]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                status = growth.growth_route_preflight_status(
                    args,
                    route,
                    realm=growth.REALMS["hib"],
                    current_level=5,
                    party_size=2,
                )
                adjusted = growth.growth_route_preflight_adjusted_route(
                    args,
                    route,
                    realm=growth.REALMS["hib"],
                    current_level=5,
                    party_size=2,
                )

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertTrue(status)
        self.assertNotEqual((adjusted.x, adjusted.y), (route.x, route.y))
        nearest_distance = min(
            math.hypot(adjusted.x - item_x, adjusted.y - item_y)
            for item_x, item_y in ((348442, 497904), (348623, 498337))
        )
        self.assertGreater(
            nearest_distance,
            growth.growth_route_preflight_startup_landing_buffer_radius(5, 2, 350),
        )
        self.assertEqual(adjusted.z, 4620)
        self.assertTrue(adjusted.live_anchor_z)
        self.assertIn("live_startup_anchor_replaced:spawn_overlap", log_text)
        self.assertIn("live_target_present:water beetle collector", log_text)

    def test_route_preflight_reanchors_party_route_when_target_overlaps_startup_spawn(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(
                growth_fast_travel="route-home",
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_low_solo_radius=2500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=1,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=0,
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                run_dir=temp_dir,
            )
            route = growth.route_point(
                6,
                292898,
                647251,
                4598,
                "water beetle",
                source="hunting-index",
                mob_level=6,
                mob_count=10,
            )

            def fake_preflight(url: str, timeout: float) -> object:
                del timeout
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                if name != "water beetle":
                    return []
                return [
                    {
                        "name": "water beetle",
                        "level": 6,
                        "x": 292898,
                        "y": 647251,
                        "z": 4598,
                        "distance": 0,
                    },
                    {
                        "name": "water beetle",
                        "level": 6,
                        "x": 292626,
                        "y": 648636,
                        "z": 4598,
                        "distance": 1411,
                    },
                ]

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                status = growth.growth_route_preflight_status(
                    args,
                    route,
                    realm=growth.REALMS["hib"],
                    current_level=6,
                    party_size=2,
                )
                adjusted = growth.growth_route_preflight_adjusted_route(
                    args,
                    route,
                    realm=growth.REALMS["hib"],
                    current_level=6,
                    party_size=2,
                )

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertTrue(status)
        self.assertEqual((adjusted.x, adjusted.y, adjusted.z), (294298, 647251, 4598))
        self.assertTrue(adjusted.live_anchor_z)
        self.assertTrue(adjusted.startup_anchor)
        self.assertEqual(
            growth.startup_route_home_after_services_point(
                growth.REALMS["hib"],
                adjusted,
                current_level=6,
                party_size=2,
                ground_z_offset=0,
            ),
            adjusted,
        )
        self.assertIn("live_startup_anchor_replaced:spawn_overlap", log_text)

    def test_route_preflight_startup_anchor_skips_wrong_ground_plane(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(
                growth_fast_travel="route-home",
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_low_solo_radius=2500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=1,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=0,
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
            )
            route = growth.route_point(
                10,
                780175,
                836833,
                4472,
                "perfidious pook",
                source="hunting-index",
                mob_level=10,
                mob_count=2,
            )

            def fake_preflight(url: str, timeout: float) -> object:
                del timeout
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                if (query.get("name") or [""])[0] != "perfidious pook":
                    return []
                return [
                    {
                        "name": "perfidious pook",
                        "level": 10,
                        "x": 780175,
                        "y": 836833,
                        "z": 4472,
                        "distance": 0,
                    },
                    {
                        "name": "perfidious pook",
                        "level": 10,
                        "x": 780037,
                        "y": 836372,
                        "z": 4442,
                        "distance": 500,
                    },
                ]

            def fake_sample_route_z(_realm, _samplers, x, y, target_z, *, ground_z_offset=0):
                del _realm, _samplers, ground_z_offset
                if int(x) == 781575 and int(y) == 836833:
                    return 3490
                return int(target_z)

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                with mock.patch.object(growth, "sample_route_z", side_effect=fake_sample_route_z):
                    status = growth.growth_route_preflight_status(
                        args,
                        route,
                        realm=growth.REALMS["mid"],
                        current_level=10,
                        party_size=2,
                    )
                    adjusted = growth.growth_route_preflight_adjusted_route(
                        args,
                        route,
                        realm=growth.REALMS["mid"],
                        current_level=10,
                        party_size=2,
                    )

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertTrue(status)
        self.assertNotEqual((adjusted.x, adjusted.y, adjusted.z), (781575, 836833, 4472))
        self.assertTrue(adjusted.startup_anchor)
        self.assertIn("live_startup_anchor_replaced:spawn_overlap", log_text)

    def test_mid_solo_level_seven_preflight_failure_uses_recordable_recovery_fallback(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_preflight=True,
            growth_route_preflight_anchor=True,
            growth_route_preflight_timeout=0.1,
            growth_route_preflight_radius=0,
            growth_route_preflight_low_solo_radius=2500,
            growth_route_preflight_limit=3,
            growth_route_preflight_hazard_radius=2500,
            growth_route_preflight_hazard_limit=3,
            growth_route_preflight_hazard_token_limit=12,
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            growth_failure_target_memory=True,
            growth_failure_target_memory_attempts=8,
            growth_failure_target_memory_min_engagements=2,
            run_dir="",
            case_name="case",
            dry_run=False,
            nav_api_url="http://dummy-api:5000",
            host="127.0.0.1",
            api_port=5000,
            max_target_distance=2200.0,
        )

        with mock.patch.object(growth, "fetch_growth_route_preflight_payload", return_value=[]):
            route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(route.prefer, "carrion crawler")
        self.assertEqual(route.mob_level, 6)

    def test_mid_solo_level_seven_strict_preflight_failure_uses_recordable_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,7,5,5,5,young grendelorm,5,15,776006,724447,4719,15,0,0,0,Bind Start,25348,900\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=0,
                growth_route_preflight_low_solo_radius=2500,
                growth_route_preflight_limit=3,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=2200.0,
                run_dir="",
            )

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", return_value=[]):
                route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(route.prefer, "vein spider")
        self.assertEqual(route.source, "hunting-index-preflight-fallback")
        self.assertEqual(route.mob_level, 5)

    def test_mid_solo_level_seven_uses_verified_level_six_recovery_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,7,5,5,5,young grendelorm,5,15,776006,724447,4719,15,0,0,0,Bind Start,25348,900\n"
                "mid,1,7,5,5,5,vein spider,5,25,772957,725582,4754,25,0,0,0,Bind Start,24074,900\n"
                "mid,1,7,5,6,6,army ant worker,6,20,760846,771756,4768,20,0,0,0,Mularn,4000,980\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=0,
                growth_route_preflight_low_solo_radius=2500,
                growth_route_preflight_limit=3,
                growth_route_preflight_hazard_radius=1800,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_allow_lower_xp_target_plan=True,
                growth_allow_lower_xp_gear_farm=True,
                growth_failure_target_memory=True,
                growth_failure_target_memory_attempts=8,
                growth_failure_target_memory_min_engagements=2,
                run_dir="",
                case_name="case",
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=2200.0,
            )

            queries: list[dict[str, list[str]]] = []

            def fake_preflight(url: str, timeout: float) -> object:
                del timeout
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                queries.append(query)
                name = (query.get("name") or [""])[0]
                if name in {"young grendelorm", "vein spider"}:
                    return []
                if name == "army ant worker":
                    return [
                        {
                            "name": "army ant worker",
                            "level": 6,
                            "x": 760836,
                            "y": 771827,
                            "z": 4768,
                            "distance": 72,
                        }
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(route.prefer, "army ant worker")
        self.assertEqual(route.mob_level, 6)
        self.assertEqual((route.x, route.y, route.z), (760836, 771827, 4768))
        self.assertTrue(
            any(
                (query.get("name") or [""])[0] == "army ant worker"
                and (query.get("minLevel") or [""])[0] == "6"
                for query in queries
            )
        )

    def test_mid_solo_level_seven_preflight_exact_rejects_prefixed_target(self) -> None:
        args = SimpleNamespace(
            growth_fast_travel="route-home",
            growth_route_preflight=True,
            growth_route_preflight_anchor=True,
            growth_route_preflight_timeout=0.1,
            growth_route_preflight_radius=0,
            growth_route_preflight_low_solo_radius=2500,
            growth_route_preflight_limit=3,
            growth_route_preflight_hazard_radius=2500,
            growth_route_preflight_hazard_limit=3,
            growth_route_preflight_hazard_token_limit=12,
            dry_run=False,
            nav_api_url="http://dummy-api:5000",
            host="127.0.0.1",
            api_port=5000,
            max_target_distance=2200.0,
            run_dir="",
        )
        route = growth.RoutePoint(
            7,
            772957,
            725582,
            4754,
            "vein spider",
            "",
            "Bind Start",
            source="hunting-index",
            mob_level=5,
        )

        def fake_prefixed_preflight(url: str, timeout: float) -> object:
            del timeout
            query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            if (query.get("name") or [""])[0] == "vein spider":
                return [{"name": "노련한 vein spider", "level": 5, "x": 772812, "y": 725190, "z": 4764}]
            return []

        with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_prefixed_preflight):
            self.assertIsNone(
                growth.growth_route_preflight_checked_route(
                    args,
                    route,
                    realm=growth.REALMS["mid"],
                    current_level=7,
                    party_size=1,
                )
            )

    def test_mid_solo_level_seven_build_command_uses_live_anchor_and_lowest_xp_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,7,6,6,6,carrion crawler,6,25,787192,868637,6698,25,0,0,0,Gotar,24074,900\n",
                encoding="utf-8",
            )
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            args = SimpleNamespace(
                host="127.0.0.1",
                port=10300,
                segment_seconds=150,
                safe_exit_max_seconds=25,
                safe_exit_recent_damage_grace=5,
                ramp_up=2,
                login_retries=5,
                login_retry_delay=3.0,
                api_port=5000,
                max_target_distance=5200,
                target_home_max_distance=10000.0,
                combat_home_leash_distance=1200.0,
                target_timeout=65,
                combat_interval=1.5,
                target_pool=5,
                smooth_move_interval=0.2,
                movement_speed=240.0,
                path_last_mile_distance=1200.0,
                ground_z_offset=0,
                encounter_log_interval=3.0,
                nav_api_url="http://dummy-api:5000",
                live_api_url="",
                party_external_member_names="",
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=2500,
                growth_route_preflight_low_solo_radius=2500,
                growth_route_preflight_limit=3,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_allow_lower_xp_gear_farm=True,
                dry_run=False,
                run_dir="",
            )

            def fake_preflight(url: str, timeout: float) -> object:
                del timeout
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                if name == "carrion crawler":
                    return [
                        {
                            "name": "carrion crawler",
                            "level": 6,
                            "x": 787192,
                            "y": 868637,
                            "z": 6698,
                            "distance": 2350,
                        }
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                command = growth.build_behavior_command(
                    args=args,
                    realm=growth.REALMS["mid"],
                    accounts_csv=Path("accounts.csv"),
                    case_dir=case_dir,
                    segment_index=16,
                    party_size=1,
                    current_level=7,
                    path_graph=Path("graph.json"),
                )
            payload = json.loads((case_dir / "live-control.json").read_text(encoding="utf-8"))

        self.assertEqual(command[command.index("--player-level") + 1], "7")
        self.assertEqual(command[command.index("--require-target-name") + 1], "carrion crawler")
        self.assertIn("--require-target-name-exact", command)
        self.assertEqual(command[command.index("--ideal-target-level") + 1], "6")
        self.assertEqual(command[command.index("--min-target-level") + 1], "6")
        self.assertEqual(command[command.index("--max-target-level") + 1], "6")
        self.assertEqual(command[command.index("--max-target-level-delta") + 1], "0")
        self.assertEqual(command[command.index("--max-target-distance") + 1], "6500.0")
        self.assertEqual(command[command.index("--target-home-max-distance") + 1], "6500.0")
        self.assertEqual(command[command.index("--hunter-target-api-engage-distance") + 1], "6500.0")
        self.assertEqual(command[command.index("--required-target-home-hunt-distance") + 1], "6500.0")
        self.assertTrue(command[command.index("--required-target-home") + 1].startswith("787192,868637,"))
        self.assertIn("787192,868637", command[command.index("--waypoints") + 1])
        self.assertEqual(payload["baseline_player_level"], 7)
        self.assertEqual(payload["baseline_min_target_level"], 6)
        self.assertEqual(payload["baseline_max_target_level"], 6)

    def test_mid_solo_level_seven_rejects_xp_ineligible_worker_index_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,7,4,5,6,wood-eater worker,4,31,786637,723034,4722,31,0,0,0,Mularn,17360,1752\n",
                encoding="utf-8",
            )
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            args = SimpleNamespace(
                host="127.0.0.1",
                port=10300,
                segment_seconds=150,
                safe_exit_max_seconds=25,
                safe_exit_recent_damage_grace=5,
                ramp_up=2,
                login_retries=5,
                login_retry_delay=3.0,
                api_port=5000,
                max_target_distance=5200,
                target_home_max_distance=10000.0,
                combat_home_leash_distance=1200.0,
                target_timeout=65,
                combat_interval=1.5,
                target_pool=5,
                smooth_move_interval=0.2,
                movement_speed=240.0,
                path_last_mile_distance=1200.0,
                ground_z_offset=0,
                encounter_log_interval=3.0,
                nav_api_url="http://127.0.0.1:5000",
                live_api_url="",
                party_external_member_names="",
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_allow_lower_xp_gear_farm=True,
            )

            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["mid"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=16,
                party_size=1,
                current_level=7,
                path_graph=Path("graph.json"),
            )
            payload = json.loads((case_dir / "live-control.json").read_text(encoding="utf-8"))

        self.assertEqual(command[command.index("--require-target-name") + 1], "carrion crawler")
        self.assertIn("wood-eater worker", command[command.index("--avoid-target-name") + 1].split(","))
        self.assertEqual(command[command.index("--min-target-level") + 1], "6")
        self.assertEqual(command[command.index("--max-target-level") + 1], "6")
        self.assertEqual(payload["baseline_min_target_level"], 6)
        self.assertEqual(payload["baseline_max_target_level"], 6)

    def test_mid_solo_level_seven_shortage_recovery_uses_level_six_carrion_target(self) -> None:
        args = SimpleNamespace(
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            growth_target_plan_override=(6, 6, 0),
            growth_hunting_index="",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_preflight=True,
            growth_route_preflight_anchor=True,
            growth_route_preflight_timeout=0.1,
            growth_route_preflight_radius=2500,
            growth_route_preflight_low_solo_radius=2500,
            growth_route_preflight_limit=3,
            growth_route_preflight_hazard_radius=2500,
            growth_route_preflight_hazard_limit=3,
            growth_route_preflight_hazard_token_limit=12,
            dry_run=False,
            nav_api_url="http://dummy-api:5000",
            host="127.0.0.1",
            api_port=5000,
            max_target_distance=2200.0,
            run_dir="",
        )
        def fake_preflight(url: str, timeout: float) -> object:
            del timeout
            query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            name = (query.get("name") or [""])[0]
            if name == "carrion crawler":
                return [
                    {
                        "name": "carrion crawler",
                        "level": 6,
                        "x": 786950,
                        "y": 873259,
                        "z": 4715,
                        "distance": 2350,
                    }
                ]
            return []

        with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
            route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(route.prefer, "carrion crawler")
        self.assertEqual(route.mob_level, 6)
        self.assertEqual((route.x, route.y, route.z), (786950, 873259, 4715))

    def test_mid_solo_level_seven_shortage_recovery_uses_level_five_safe_target(self) -> None:
        args = SimpleNamespace(
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            growth_target_plan_override=(5, 5, 0),
            growth_hunting_index="",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_preflight=False,
            run_dir="",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(route.prefer, "young grendelorm")
        self.assertEqual(route.mob_level, 5)

    def test_mid_solo_level_seven_shortage_recovery_prefers_low_density_black_mauler(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,7,4,5,6,vein spider,5,25,772957,725582,4754,25,0,0,0,Bind Start,24074,900\n"
                "mid,1,7,4,5,6,black mauler juvenile,5,26,731633,814288,5479,26,0,0,500,Fort Atla,17884,1600\n"
                "mid,1,7,4,5,6,black mauler juvenile,5,3,731147,756936,4621,3,0,0,500,Audliten,3847,1200\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=18,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=False,
                growth_allow_lower_xp_target_plan=True,
                growth_allow_lower_xp_gear_farm=True,
                growth_target_plan_override=(5, 5, 0),
                growth_route_preflight=False,
                case_name="solo-s150-r2-mid-r001",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(route.prefer, "black mauler juvenile")
        self.assertEqual(route.mob_count, 3)
        self.assertEqual((route.x, route.y, route.z), (731147, 756936, 4621))

    def test_mid_solo_level_seven_shortage_recovery_applies_level_five_plan(self) -> None:
        args = SimpleNamespace(growth_allow_lower_xp_gear_farm=True)
        behavior_args = SimpleNamespace()

        applied = growth.apply_growth_shortage_recovery_route_override(
            behavior_args,
            args,
            growth.REALMS["mid"],
            current_level=7,
            party_size=1,
            item_plans={"growthmid": growth.GrowthItemPlan([], [], buy_shortage_copper=345)},
        )

        self.assertTrue(applied)
        self.assertEqual(behavior_args.growth_route_level_override, 7)
        self.assertEqual(behavior_args.growth_target_level_override, 5)
        self.assertEqual(behavior_args.growth_target_plan_override, (5, 5, 0))
        self.assertTrue(behavior_args.growth_allow_lower_xp_target_plan)

    def test_mid_solo_level_seven_shortage_recovery_forces_carrion_before_generic_index(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=50,
            growth_fast_travel="route-home",
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            growth_shortage_recovery_player_level=7,
            growth_target_plan_override=(6, 6, 0),
            case_name="solo-s150-r2-mid-r001",
            run_dir="",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(route.prefer, "carrion crawler")
        self.assertEqual(route.mob_level, 6)
        self.assertEqual(route.mob_count, 33)
        self.assertEqual((route.x, route.y, route.z), (787192, 868637, 6698))
        self.assertIn("vein spider", route.avoid)

    def test_mid_solo_level_seven_shortage_recovery_skips_stale_forced_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,7,5,5,5,vein spider,5,23,787694,707122,5580,23,0,0,0,Mularn,25210,950\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=2500,
                growth_route_preflight_low_solo_radius=2500,
                growth_route_preflight_limit=3,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_allow_lower_xp_target_plan=True,
                growth_allow_lower_xp_gear_farm=True,
                growth_shortage_recovery_player_level=7,
                growth_target_plan_override=(5, 5, 0),
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=2800.0,
                run_dir="",
            )

            def fake_preflight(url: str, timeout: float) -> object:
                del timeout
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                x = int((query.get("x") or ["0"])[0])
                if name == "vein spider" and x == 787694:
                    return [{"name": "vein spider", "level": 5, "x": 787694, "y": 707122, "z": 5580}]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(route.prefer, "vein spider")
        self.assertEqual(route.mob_level, 5)
        self.assertEqual((route.x, route.y, route.z), (787694, 707122, 5580))

    def test_mid_solo_level_seven_shortage_recovery_falls_back_when_preflight_empty(self) -> None:
        args = SimpleNamespace(
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            growth_target_plan_override=(5, 5, 0),
            growth_hunting_index="",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_preflight=True,
            growth_route_preflight_anchor=True,
            growth_route_preflight_timeout=0.1,
            growth_route_preflight_radius=2500,
            growth_route_preflight_low_solo_radius=2500,
            growth_route_preflight_limit=3,
            growth_route_preflight_hazard_radius=2500,
            growth_route_preflight_hazard_limit=3,
            growth_route_preflight_hazard_token_limit=12,
            dry_run=False,
            nav_api_url="http://dummy-api:5000",
            host="127.0.0.1",
            api_port=5000,
            max_target_distance=2200.0,
            run_dir="",
        )

        with mock.patch.object(growth, "fetch_growth_route_preflight_payload", return_value=[]):
            route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(route.prefer, "young grendelorm")
        self.assertEqual(route.mob_level, 5)

    def test_mid_solo_level_seven_official_case_index_skips_mularn_death_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=20,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 7, 1)

        self.assertEqual(route.prefer, "carrion crawler")
        self.assertGreaterEqual(route.mob_level, growth.minimum_growth_effective_target_level(7, 1, "mid"))
        self.assertNotIn(route.prefer, {"army ant worker", "rock crab", "roaming thrall"})
        self.assertIn("huldu", route.avoid)
        self.assertIn("small hill cat", route.avoid)
        self.assertEqual(growth.strict_route_target_name(route, 7, party_size=1, realm_key="mid"), "carrion crawler")

    def test_mid_solo_level_six_prefers_non_wood_eater_camps(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("mid", 6, 1),
            ("wayward ghoul", "dryad sprig", "rugged dwarven pony", "skeletal seafarer"),
        )
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=5,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
            case_name="solo-s150-r2-mid-r001",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 6, 1)

        self.assertIn(route.prefer, {"wayward ghoul", "dryad sprig", "rugged dwarven pony", "skeletal seafarer"})
        self.assertNotEqual(route.prefer, "wood-eater worker")

    def test_hib_solo_level_seven_uses_dense_low_risk_camps(self) -> None:
        args_one = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=7,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            case_name="solo-s150-r2-hib-r001",
        )
        args_two = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=7,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            case_name="solo-s150-r2-hib-r002",
        )

        first = growth.select_growth_route_point(args_one, growth.REALMS["hib"], 7, 1)
        second = growth.select_growth_route_point(args_two, growth.REALMS["hib"], 7, 1)

        self.assertEqual(growth.target_levels(7, 1, "hib"), (5, 6, 1))
        self.assertEqual(growth.minimum_growth_effective_target_level(7, 1, "hib"), 5)
        self.assertEqual(first.level, 7)
        self.assertEqual(second.level, 7)
        self.assertEqual(first.prefer, "hill toad")
        self.assertEqual(second.prefer, "hill toad")
        self.assertEqual(first.mob_level, 6)
        self.assertEqual(second.mob_level, 6)
        self.assertNotEqual(first.prefer, "water beetle collector")
        self.assertNotEqual(second.prefer, "water beetle collector")
        self.assertNotEqual((first.x, first.y, first.z), (333371, 590108, 8146))
        self.assertNotEqual((second.x, second.y, second.z), (333371, 590108, 8146))

    def test_hib_solo_level_seven_shortage_recovery_uses_xp_eligible_hill_toad_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=23,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            case_name="solo-s150-r2-hib-r002",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["hib"], 7, 1)

        self.assertEqual(route.prefer, "hill toad")
        self.assertEqual(route.mob_level, 6)
        self.assertEqual(route.teleport_destination, "Shannon Estuary")
        self.assertNotEqual(route.prefer, "spraggon")

    def test_hib_solo_level_seven_shortage_command_uses_prefer_fallback(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=150,
            safe_exit_max_seconds=25,
            safe_exit_recent_damage_grace=5,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=10000.0,
            combat_home_leash_distance=1200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            party_external_member_names="",
            growth_hunting_index="",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_preflight=False,
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            growth_route_level_override=7,
            growth_target_level_override=6,
            growth_target_plan_override=(5, 6, 0),
            dry_run=False,
            run_dir="",
        )
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["hib"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=20,
                party_size=1,
                current_level=7,
                path_graph=Path("graph.json"),
            )

        self.assertEqual(command[command.index("--min-target-level") + 1], "5")
        self.assertEqual(command[command.index("--max-target-level") + 1], "6")
        self.assertIn("--prefer-target-name", command)
        self.assertIn("--require-target-name", command)
        self.assertEqual(command[command.index("--require-target-name") + 1], "eirebug")
        self.assertNotIn("--target-auto-lowest-visible-level", command)
        self.assertNotIn("--allow-preferred-low-con-fallback", command)

    def test_hib_solo_level_seven_shortage_recovery_uses_xp_eligible_route(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=39,
            growth_fast_travel="route-home",
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            growth_shortage_recovery_player_level=7,
            case_name="solo-s150-r2-hib-r002",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["hib"], 7, 1)

        self.assertEqual(route.prefer, "lugradan whelp")
        self.assertEqual(route.mob_level, 6)
        self.assertNotEqual(route.prefer, "mudman")

    def test_mid_solo_level_seven_shortage_prefers_without_requiring_single_target(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=150,
            safe_exit_max_seconds=25,
            safe_exit_recent_damage_grace=5,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=10000.0,
            combat_home_leash_distance=1200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            party_external_member_names="",
            growth_hunting_index="",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_preflight=False,
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            growth_target_plan_override=(5, 5, 1),
            dry_run=False,
            run_dir="",
        )
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["mid"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=13,
                party_size=1,
                current_level=7,
                path_graph=Path("graph.json"),
            )

        self.assertEqual(command[command.index("--min-target-level") + 1], "5")
        self.assertEqual(command[command.index("--max-target-level") + 1], "6")
        self.assertNotIn("--require-target-name", command)
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "young grendelorm")
        avoid_targets = command[command.index("--avoid-target-name") + 1]
        self.assertIn("sapherd", avoid_targets.split(","))
        self.assertIn("pine imp", avoid_targets.split(","))
        self.assertIn("wood-eater worker", avoid_targets.split(","))
        self.assertNotIn("--target-auto-lowest-visible-level", command)
        self.assertNotIn("--allow-preferred-low-con-fallback", command)

    def test_mid_solo_level_seven_shortage_preflight_does_not_treat_sapherd_as_hazard(self) -> None:
        args = SimpleNamespace(
            growth_route_preflight=True,
            growth_route_preflight_anchor=True,
            growth_route_preflight_timeout=0.1,
            growth_route_preflight_radius=2500,
            growth_route_preflight_limit=3,
            growth_route_preflight_hazard_radius=2500,
            growth_route_preflight_hazard_limit=3,
            growth_route_preflight_hazard_token_limit=12,
            growth_fast_travel="route-home",
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            growth_target_plan_override=(5, 5, 1),
            dry_run=False,
            nav_api_url="http://dummy-api:5000",
            host="127.0.0.1",
            api_port=5000,
            max_target_distance=5200,
            run_dir="",
        )
        route = growth.route_point(
            7,
            787192,
            868637,
            6698,
            "carrion crawler",
            "sapherd,ghost light",
            "Gotar",
            source="hunting-index",
            mob_level=6,
        )

        def fake_preflight(url: str, timeout: float) -> object:
            del timeout
            query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            name = (query.get("name") or [""])[0]
            if name == "carrion crawler":
                return [
                    {
                        "name": "carrion crawler",
                        "level": 6,
                        "x": 786950,
                        "y": 873259,
                        "z": 4715,
                        "distance": 900,
                    }
                ]
            if name == "sapherd":
                return [
                    {
                        "name": "sapherd",
                        "level": 6,
                        "x": 786500,
                        "y": 873000,
                        "z": 4715,
                        "distance": 700,
                    }
                ]
            return []

        with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
            status = growth.growth_route_preflight_status(
                args,
                route,
                realm=growth.REALMS["mid"],
                current_level=7,
                party_size=1,
            )

        self.assertTrue(status)
        adjusted = growth.growth_route_preflight_adjusted_route(
            args,
            route,
            realm=growth.REALMS["mid"],
            current_level=7,
            party_size=1,
        )
        self.assertEqual((adjusted.x, adjusted.y, adjusted.z), (786950, 873259, 4715))

    def test_case_named_growth_routes_spread_low_mid_camps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,1,7,4,5,6,carrion crawler,6,30,777576,869618,5947,30,0,0,500,Gotar,33853,1228\n"
                "mid,1,7,4,5,6,black mauler juvenile,5,26,731633,814288,5479,26,0,0,500,Fort Atla,17884,1667\n"
                "mid,1,7,4,5,6,black mauler juvenile,5,10,731147,756936,4621,10,0,0,500,Audliten,3847,1200\n"
                "mid,1,7,4,5,6,young grendelorm,5,15,776006,724447,4719,15,0,0,0,Bind Start,25348,900\n"
                "mid,1,7,4,5,6,vein spider,5,25,772957,725582,4754,25,0,0,0,Bind Start,24074,800\n"
                "mid,2,7,6,7,7,carrion crawler,6,33,787192,868637,6698,33,0,0,500,Gotar,36025,1228\n"
                "mid,2,7,6,7,7,black mauler juvenile,5,26,731633,814288,5479,26,0,0,500,Fort Atla,17884,1667\n"
                "mid,2,7,6,7,7,young grendelorm,5,15,776006,724447,4719,15,0,0,0,Bind Start,25348,900\n",
                encoding="utf-8",
            )
            solo_args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=4,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=False,
                case_name="solo-s150-r2-mid-r002",
            )
            duo_args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=11,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                case_name="duo-s150-mid-r001",
            )

            solo_route = growth.select_growth_route_point(solo_args, growth.REALMS["mid"], 7, 1)
            duo_route = growth.select_growth_route_point(duo_args, growth.REALMS["mid"], 7, 2)

        self.assertEqual((solo_route.prefer, solo_route.x, solo_route.y), ("carrion crawler", 777576, 869618))
        self.assertGreaterEqual(solo_route.mob_level, growth.minimum_growth_effective_target_level(7, 1, "mid"))
        self.assertEqual((duo_route.prefer, duo_route.x, duo_route.y), ("carrion crawler", 787192, 868637))
        self.assertNotEqual((solo_route.x, solo_route.y, solo_route.z), (duo_route.x, duo_route.y, duo_route.z))

    def test_low_party_carry_command_keeps_preferred_hunting_target(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=180,
            safe_exit_max_seconds=25,
            safe_exit_recent_damage_grace=5,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=2800,
            target_home_max_distance=6200.0,
            combat_home_leash_distance=1200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            startup_delay=0.0,
            growth_fast_travel="route-home",
            growth_allow_lower_xp_gear_farm=False,
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=13,
            growth_route_level_override=5,
            growth_route_level_is_carry_target=True,
            growth_target_level_override=3,
            growth_target_plan_override=growth.growth_party_carry_target_plan(3, 4),
            case_name="party4-s180-hib-r001",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["hib"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=7,
                party_size=4,
                current_level=3,
                path_graph=Path("graph.json"),
        )

        self.assertIn("--prefer-target-name", command)
        preferred = command[command.index("--prefer-target-name") + 1]
        self.assertEqual(preferred, "spraggon")
        self.assertIn("--avoid-target-name", command)
        avoid_targets = command[command.index("--avoid-target-name") + 1]
        self.assertIn("wolf cub", avoid_targets)
        self.assertIn("underhill companion", avoid_targets)
        self.assertNotIn(preferred, avoid_targets.split(","))

    def test_low_mid_hib_party4_prefers_safer_growth_index_camps(self) -> None:
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("mid", 3, 4),
            ("wood-eater", "wood-eater worker", "hobgoblin prankster", "wayward ghoul", "black mauler juvenile"),
        )
        self.assertIn("black mauler juvenile", growth.growth_hunting_index_avoid_targets("mid", 4, 4))
        self.assertEqual(
            growth.preferred_growth_hunting_candidates("hib", 2, 4),
            ("large frog", "water beetle larva", "skeletal pawn", "minor changeling", "badger cub"),
        )

    def test_low_party_carry_target_routes_follow_preferred_hunting_index(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )

        hib_duo_target = growth.growth_party_carry_target_level(3, 2)
        hib_duo_route = growth.select_growth_route_point(args, growth.REALMS["hib"], hib_duo_target, 2)
        mid_duo_target = growth.growth_party_carry_target_level(3, 2)
        mid_duo_route = growth.select_growth_route_point(args, growth.REALMS["mid"], mid_duo_target, 2)
        hib_party8_target = growth.growth_party_carry_target_level(2, 8)
        hib_party8_route = growth.select_growth_route_point(args, growth.REALMS["hib"], hib_party8_target, 8)

        self.assertEqual(hib_duo_target, 4)
        self.assertEqual(hib_duo_route.prefer, "mudman")
        self.assertEqual(mid_duo_target, 4)
        self.assertEqual(mid_duo_route.prefer, "wood-eater worker")
        self.assertEqual(hib_party8_target, 7)
        self.assertEqual(hib_party8_route.prefer, "water beetle")

    def test_alb_duo_level_ten_carry_uses_live_index_level_eight_plan(self) -> None:
        self.assertEqual(growth.growth_party_carry_target_level_for_realm(10, 2, "alb"), 8)
        self.assertEqual(growth.growth_party_carry_target_plan_for_realm(10, 2, "alb"), (7, 8, 1))

    def test_alb_duo_level_ten_carry_route_uses_safer_rotting_zombie_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )

        target = growth.growth_party_carry_target_level_for_realm(10, 2, "alb")
        route = growth.select_growth_route_point(args, growth.REALMS["alb"], target, 2)

        self.assertEqual(target, 8)
        self.assertEqual(route.prefer, "rotting zombie")
        self.assertEqual((route.x, route.y, route.z), (527242, 624780, 1971))
        self.assertEqual(route.teleport_destination, "Caer Ulfwych")
        self.assertEqual(route.mob_level, 7)
        self.assertIn("death grip vines", route.avoid)
        self.assertIn("river racer", route.avoid)
        self.assertIn("giant spider", route.avoid)
        self.assertIn("bear", route.avoid)
        self.assertIn("adder", route.avoid)
        self.assertIn("ant drone", route.avoid)

    def test_alb_duo_level_ten_carry_river_racer_failure_uses_rotting_zombie_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-06T23:56:19Z,alb-p2,alb,2,1,10,death_pressure,avoid_target,river racer,7,encounter_death_message,4\n"
                "2026-07-06T23:56:19Z,alb-p2,alb,2,1,10,combat_no_kill;death_pressure,avoid_target,노련한 river racer,8,combat_csv,4\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=2,
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_target_level_override=10,
                growth_target_plan_override=(7, 8, 1),
            )

            target = growth.growth_party_carry_target_level_for_realm(10, 2, "alb")
            route = growth.select_growth_route_point(args, growth.REALMS["alb"], target, 2)

        self.assertEqual(target, 8)
        self.assertEqual(route.prefer, "rotting zombie")
        self.assertEqual(route.mob_level, 7)
        self.assertEqual((route.x, route.y, route.z, route.teleport_destination), (527242, 624780, 1971, "Caer Ulfwych"))
        self.assertIn("river racer", route.avoid.split(","))

    def test_alb_duo_level_ten_carry_route_home_start_uses_selected_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            position_step=80,
            ground_z_offset=0,
        )
        target = growth.growth_party_carry_target_level_for_realm(10, 2, "alb")
        route = growth.select_growth_route_point(args, growth.REALMS["alb"], target, 2)
        start = growth.startup_route_home_after_services_point(
            growth.REALMS["alb"],
            route,
            current_level=10,
            party_size=2,
            ground_z_offset=0,
        )
        rows = [
            {"username": "growthalb120", "growth_role": "carry"},
            {"username": "growthalb121", "growth_role": "tracked"},
        ]

        growth.apply_checkpoint_start_to_account_rows(
            args,
            rows,
            growth.REALMS["alb"],
            target,
            2,
            start_point=start,
        )

        self.assertEqual(route.prefer, "rotting zombie")
        self.assertEqual(rows[0]["start_x"], "527242")
        self.assertEqual(rows[0]["start_y"], "623480")
        self.assertNotEqual(rows[0]["start_x"], "575246")
        self.assertEqual(rows[1]["start_x"], "527692")
        self.assertEqual(rows[1]["start_y"], "623480")

    def test_alb_duo_level_ten_checkpoint_start_uses_carry_target_route(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="off",
            checkpoint_start_location="route-home",
            growth_party_carry_count=-1,
            ground_z_offset=0,
        )

        point = growth.checkpoint_start_point(args, growth.REALMS["alb"], 10, 2)

        self.assertEqual(point.prefer, "rotting zombie")
        self.assertEqual((point.x, point.y), (527242, 623480))
        self.assertNotEqual((point.x, point.y), (575246, 547179))

    def test_mid_duo_level_ten_checkpoint_start_uses_behavior_carry_route_level(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="",
            growth_route_case_index=0,
            growth_fast_travel="off",
            checkpoint_start_location="route-home",
            growth_party_carry_count=-1,
            growth_equip_party_carry_gear=False,
            ground_z_offset=0,
        )

        route_level = growth.growth_party_behavior_route_level_for_start(args, 10, 2, "mid")
        point = growth.checkpoint_start_point(args, growth.REALMS["mid"], 10, 2)

        self.assertEqual(route_level, 9)
        self.assertEqual(point.prefer, "tawny lynx")
        self.assertEqual(point.level, 10)
        self.assertEqual(point.mob_level, 8)
        target_route = growth.mid_level_ten_tawny_lynx_party_route()
        self.assertNotEqual((point.x, point.y), (target_route.x, target_route.y))
        self.assertGreater(
            math.hypot(point.x - target_route.x, point.y - target_route.y),
            growth.growth_objective_entry_aggro_avoid_radius(10, 2, "mid", target_route),
        )
        self.assertLess(
            math.hypot(point.x - 771152, point.y - 836380),
            math.hypot(target_route.x - 771152, target_route.y - 836380),
        )
        self.assertTrue(point.live_anchor_z)
        self.assertFalse(point.startup_anchor)
        self.assertNotEqual((point.x, point.y), (775592, 836840))
        self.assertIn("노련한", growth.growth_target_nearby_avoid_names_for_route(10, 2, "mid", point))
        self.assertIn("tawny lynx cub", growth.growth_target_nearby_avoid_names_for_route(10, 2, "mid", point))
        self.assertEqual(growth.growth_objective_entry_aggro_avoid_radius(10, 2, "mid", point), 1800.0)
        distance_args = SimpleNamespace(
            growth_fast_travel="route-home",
            max_target_distance=2200.0,
            target_home_max_distance=10000.0,
            combat_home_leash_distance=10000.0,
        )
        self.assertEqual(growth.growth_max_target_distance(distance_args, 10, 2, "mid", point), 2200.0)
        self.assertEqual(growth.growth_max_target_distance(distance_args, 9, 2, "mid", point), 2200.0)
        self.assertEqual(growth.growth_target_home_max_distance(distance_args, 10, 2, "mid", point), 2200.0)
        self.assertEqual(growth.growth_target_home_max_distance(distance_args, 9, 2, "mid", point), 2200.0)
        self.assertEqual(growth.growth_combat_home_leash_distance_for_route(distance_args, 10, 2, "mid", point), 2200.0)
        self.assertEqual(growth.growth_combat_home_leash_distance_for_route(distance_args, 9, 2, "mid", point), 2200.0)
        self.assertEqual(growth.growth_required_target_home_hunt_distance(distance_args, 10, 2, "mid", point), 2200.0)
        self.assertEqual(growth.growth_hunter_target_api_radius(distance_args, 9, 2, "mid", point), 2200.0)
        self.assertEqual(growth.growth_hunter_target_api_engage_distance(distance_args, 9, 2, "mid", point), 2200.0)
        self.assertNotEqual(point.prefer, "spindly rock crab")
        self.assertNotEqual(point.prefer, "wind wisp")
        self.assertNotEqual(point.prefer, "hobgoblin prowler")
        self.assertNotEqual(point.prefer, "svartalf outcast")
        self.assertNotEqual(point.prefer, "young grendelorm")

    def test_mid_duo_level_ten_startup_anchor_is_not_reoffset_beyond_short_engage_cap(self) -> None:
        args = SimpleNamespace(
            growth_fast_travel="route-home",
            max_target_distance=2200.0,
            target_home_max_distance=10000.0,
            combat_home_leash_distance=10000.0,
        )
        target_route = growth.route_point(
            10,
            764498,
            831270,
            4726,
            "tawny lynx",
            source="hunting-index",
            mob_level=8,
            mob_count=3,
            live_anchor_z=True,
            teleport_destination="Gotar",
        )
        startup_anchor = growth.route_point(
            10,
            765855,
            831240,
            4765,
            "tawny lynx",
            source="hunting-index",
            mob_level=8,
            mob_count=3,
            live_anchor_z=True,
            startup_anchor=True,
            teleport_destination="Gotar",
        )

        start = growth.startup_route_home_after_services_point(
            growth.REALMS["mid"],
            startup_anchor,
            current_level=10,
            party_size=2,
            ground_z_offset=0,
        )

        self.assertEqual(start, startup_anchor)
        self.assertLessEqual(
            math.hypot(start.x - target_route.x, start.y - target_route.y),
            growth.growth_max_target_distance(args, 10, 2, "mid", target_route),
        )

    def test_mid_duo_level_ten_live_discovery_routes_keep_short_engage_distance(self) -> None:
        point = growth.route_point(
            10,
            754088,
            782578,
            4778,
            "envy drakeling",
            source="hunting-index",
            mob_level=9,
            mob_count=5,
        )
        distance_args = SimpleNamespace(
            growth_fast_travel="route-home",
            max_target_distance=2200.0,
            target_home_max_distance=10000.0,
            combat_home_leash_distance=10000.0,
        )

        self.assertEqual(growth.growth_max_target_distance(distance_args, 10, 2, "mid", point), 2200.0)
        self.assertEqual(growth.growth_max_target_distance(distance_args, 9, 2, "mid", point), 2200.0)
        self.assertEqual(growth.growth_target_home_max_distance(distance_args, 10, 2, "mid", point), 2200.0)
        self.assertEqual(growth.growth_combat_home_leash_distance_for_route(distance_args, 10, 2, "mid", point), 2200.0)
        self.assertEqual(growth.growth_required_target_home_hunt_distance(distance_args, 10, 2, "mid", point), 2200.0)
        self.assertEqual(growth.growth_hunter_target_api_radius(distance_args, 10, 2, "mid", point), 2200.0)
        self.assertEqual(growth.growth_hunter_target_api_engage_distance(distance_args, 10, 2, "mid", point), 2200.0)

    def test_hib_duo_level_ten_checkpoint_start_uses_safe_water_beetle_route(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="",
            growth_route_case_index=0,
            growth_fast_travel="off",
            checkpoint_start_location="route-home",
            growth_party_carry_count=-1,
            growth_equip_party_carry_gear=False,
            ground_z_offset=0,
        )

        route_level = growth.growth_party_behavior_route_level_for_start(args, 10, 2, "hib")
        point = growth.checkpoint_start_point(args, growth.REALMS["hib"], 10, 2)

        self.assertEqual(route_level, 8)
        self.assertEqual(point.prefer, "water beetle")
        self.assertEqual(point.mob_level, 7)
        self.assertEqual((point.x, point.y, point.z), (347118, 502495, 4728))
        self.assertNotEqual((point.x, point.y), (347282, 504287))
        self.assertIn("lunantishee", point.avoid)
        self.assertIn(
            "blackthorn",
            growth.growth_target_nearby_avoid_names_for_route(10, 2, "hib", point),
        )
        self.assertEqual(growth.growth_objective_entry_aggro_avoid_radius(10, 2, "hib", point), 1800.0)

    def test_mid_duo_level_ten_tawny_lynx_route_home_uses_safe_camp_anchor(self) -> None:
        route = growth.mid_level_ten_tawny_lynx_party_route()

        safe = growth.startup_route_home_after_services_point(
            growth.REALMS["mid"],
            route,
            current_level=10,
            party_size=2,
            ground_z_offset=0,
        )

        self.assertNotEqual((safe.x, safe.y), (route.x, route.y))
        self.assertEqual((safe.x, safe.y, safe.z), (778910, 848323, 4780))
        self.assertGreater(
            math.hypot(safe.x - route.x, safe.y - route.y),
            growth.growth_objective_entry_aggro_avoid_radius(10, 2, "mid", route),
        )
        self.assertLessEqual(
            math.hypot(safe.x - route.x, safe.y - route.y),
            growth.growth_required_target_home_hunt_distance(SimpleNamespace(), 10, 2, "mid", route),
        )
        self.assertLess(
            math.hypot(safe.x - 771152, safe.y - 836380),
            math.hypot(route.x - 771152, route.y - 836380),
        )
        self.assertEqual(safe.prefer, "tawny lynx")
        self.assertEqual(safe.teleport_destination, "Gotar")
        self.assertTrue(safe.live_anchor_z)
        self.assertNotEqual(safe.prefer, "spindly rock crab")
        self.assertNotEqual(safe.prefer, "wind wisp")
        self.assertNotEqual(safe.prefer, "hobgoblin prowler")
        self.assertNotEqual(safe.prefer, "svartalf outcast")

    def test_mid_duo_level_ten_live_tawny_anchor_route_home_uses_safe_landing(self) -> None:
        base = growth.mid_level_ten_tawny_lynx_party_route()
        route = growth.route_point(
            10,
            781870,
            851245,
            7272,
            "tawny lynx",
            base.avoid,
            "Gotar",
            source="hunting-index",
            mob_level=8,
            mob_count=6,
            live_anchor_z=True,
        )

        safe = growth.startup_route_home_after_services_point(
            growth.REALMS["mid"],
            route,
            current_level=10,
            party_size=2,
            ground_z_offset=0,
        )

        self.assertEqual((safe.x, safe.y, safe.z), (780700, 849623, 4838))
        self.assertNotEqual((safe.x, safe.y), (route.x, route.y))
        self.assertGreater(
            math.hypot(safe.x - route.x, safe.y - route.y),
            growth.growth_objective_entry_aggro_avoid_radius(10, 2, "mid", route),
        )
        self.assertLessEqual(
            math.hypot(safe.x - route.x, safe.y - route.y),
            growth.growth_required_target_home_hunt_distance(SimpleNamespace(), 10, 2, "mid", route),
        )

    def test_mid_duo_level_ten_live_tawny_after_services_start_stays_inside_required_home_cap(self) -> None:
        route = growth.route_point(
            10,
            765855,
            829440,
            4777,
            "tawny lynx",
            "",
            "Gotar",
            source="hunting-index",
            mob_level=8,
            mob_count=3,
            live_anchor_z=True,
        )

        safe = growth.startup_route_home_after_services_point(
            growth.REALMS["mid"],
            route,
            current_level=10,
            party_size=2,
            ground_z_offset=0,
        )

        self.assertEqual((safe.x, safe.y, safe.z), (767068, 831030, 4582))
        self.assertGreater(
            math.hypot(safe.x - route.x, safe.y - route.y),
            growth.growth_objective_entry_aggro_avoid_radius(10, 2, "mid", route),
        )
        self.assertLessEqual(
            math.hypot(safe.x - route.x, safe.y - route.y),
            growth.growth_required_target_home_hunt_distance(SimpleNamespace(), 10, 2, "mid", route),
        )

    def test_mid_duo_level_ten_generic_live_anchor_route_home_uses_safe_landing(self) -> None:
        route = growth.route_point(
            8,
            802660,
            683810,
            6904,
            "young grendelorm",
            teleport_destination="Fort Veldon",
            source="hunting-index",
            mob_level=7,
            mob_count=17,
            live_anchor_z=True,
        )

        safe = growth.startup_route_home_after_services_point(
            growth.REALMS["mid"],
            route,
            current_level=10,
            party_size=2,
            ground_z_offset=0,
        )

        self.assertEqual(growth.growth_objective_entry_aggro_avoid_radius(10, 2, "mid", route), 0.0)
        self.assertNotEqual((safe.x, safe.y), (route.x, route.y))
        self.assertGreater(math.hypot(safe.x - route.x, safe.y - route.y), 1800.0)
        self.assertLessEqual(
            math.hypot(safe.x - route.x, safe.y - route.y),
            growth.growth_required_target_home_hunt_distance(SimpleNamespace(), 10, 2, "mid", route),
        )
        self.assertLess(
            math.hypot(safe.x - 801046, safe.y - 678588),
            math.hypot(route.x - 801046, route.y - 678588),
        )
        self.assertEqual(safe.prefer, "young grendelorm")
        self.assertTrue(safe.live_anchor_z)

    def test_hib_duo_level_ten_water_beetle_route_home_uses_safe_landing(self) -> None:
        route = growth.route_point(
            8,
            347282,
            504287,
            4841,
            "water beetle",
            teleport_destination="Mag Mell",
            source="hunting-index",
            mob_level=7,
        )

        safe = growth.startup_route_home_after_services_point(
            growth.REALMS["hib"],
            route,
            current_level=10,
            party_size=2,
            ground_z_offset=0,
        )

        self.assertNotEqual((safe.x, safe.y), (route.x, route.y))
        self.assertEqual((safe.x, safe.y, safe.z), (347118, 502495, 4728))
        self.assertEqual(safe.prefer, "water beetle")
        self.assertLess(math.hypot(safe.x - 346100, safe.y - 491380), math.hypot(route.x - 346100, route.y - 491380))

    def test_alb_duo_level_ten_carry_command_uses_route_policy_distances(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=300,
            safe_exit_max_seconds=90,
            safe_exit_recent_damage_grace=12,
            ramp_up=5,
            login_retries=12,
            login_retry_delay=5.0,
            api_port=5000,
            max_target_distance=2200.0,
            target_home_max_distance=1400.0,
            combat_home_leash_distance=1200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            startup_delay=4.0,
            growth_fast_travel="route-home",
            growth_allow_lower_xp_gear_farm=True,
            growth_allow_lower_xp_target_plan=False,
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_route_level_override=8,
            growth_route_level_is_carry_target=True,
            growth_target_level_override=8,
            growth_target_plan_override=(7, 8, 1),
            case_name="alb-p2",
            growth_party_carry_level_offset=12,
            current_party_size=2,
            growth_equip_party_carry_gear=False,
            growth_party_carry_count=-1,
            growth_failure_target_memory=False,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=1,
                party_size=2,
                current_level=10,
                path_graph=Path("graph.json"),
            )
            payload = json.loads((case_dir / "live-control.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["baseline_min_target_level"], 7)
        self.assertEqual(payload["baseline_max_target_level"], 9)
        self.assertTrue(command[command.index("--required-target-home") + 1].startswith("527242,624780,"))
        self.assertEqual(command[command.index("--min-target-level") + 1], "7")
        self.assertEqual(command[command.index("--max-target-level") + 1], "9")
        self.assertEqual(float(command[command.index("--target-home-max-distance") + 1]), 10000.0)
        self.assertGreaterEqual(float(command[command.index("--hunter-target-api-radius") + 1]), 5200.0)
        self.assertGreaterEqual(float(command[command.index("--hunter-target-api-engage-distance") + 1]), 5200.0)
        self.assertGreater(float(command[command.index("--hunter-target-api-radius") + 1]), 2200.0)
        self.assertGreater(float(command[command.index("--hunter-target-api-engage-distance") + 1]), 1500.0)
        self.assertEqual(command[command.index("--require-target-name") + 1], "rotting zombie")
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "rotting zombie")
        self.assertNotIn("--target-nearby-avoid-name", command)
        self.assertEqual(command[command.index("--objective-entry-aggro-avoid-radius") + 1], "2200")
        self.assertEqual(command[command.index("--flee-health-percent") + 1], "45")
        self.assertEqual(command[command.index("--flee-pressure-health-percent") + 1], "55")
        self.assertEqual(command[command.index("--flee-critical-health-percent") + 1], "25")
        self.assertEqual(command[command.index("--flee-melee-counterattack-health-floor") + 1], "25")
        self.assertEqual(command[command.index("--required-target-tank-commit-health-percent") + 1], "45")

    def test_mid_duo_level_ten_carry_command_keeps_safe_route_target_tokens(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=300,
            safe_exit_max_seconds=90,
            safe_exit_recent_damage_grace=12,
            ramp_up=5,
            login_retries=12,
            login_retry_delay=5.0,
            api_port=5000,
            max_target_distance=2200.0,
            target_home_max_distance=1400.0,
            combat_home_leash_distance=1200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            startup_delay=4.0,
            growth_fast_travel="route-home",
            growth_allow_lower_xp_gear_farm=True,
            growth_allow_lower_xp_target_plan=False,
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_route_level_override=9,
            growth_route_level_is_carry_target=True,
            growth_target_level_override=9,
            growth_target_plan_override=(8, 9, 1),
            case_name="mid-p2",
            growth_party_carry_level_offset=12,
            current_party_size=2,
            growth_equip_party_carry_gear=False,
            growth_party_carry_count=-1,
            growth_failure_target_memory=False,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["mid"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=1,
                party_size=2,
                current_level=10,
                path_graph=Path("graph.json"),
            )

        self.assertEqual(command[command.index("--require-target-name") + 1], "tawny lynx")
        self.assertIn("--require-target-name-exact", command)
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "tawny lynx")
        self.assertEqual(command[command.index("--min-target-level") + 1], "8")
        self.assertEqual(command[command.index("--max-target-level") + 1], "10")
        self.assertEqual(command[command.index("--max-target-distance") + 1], "2200.0")
        self.assertEqual(command[command.index("--target-home-max-distance") + 1], "2200.0")
        self.assertEqual(command[command.index("--combat-home-leash-distance") + 1], "2200.0")
        self.assertEqual(command[command.index("--combat-chase-max-distance") + 1], "2200.0")
        self.assertEqual(command[command.index("--hunter-target-api-radius") + 1], "2200.0")
        self.assertEqual(command[command.index("--hunter-target-api-engage-distance") + 1], "2200.0")
        self.assertEqual(
            command[command.index("--startup-route-home-after-services") + 1],
            "778910,848323,4780",
        )
        self.assertEqual(command[command.index("--required-target-home") + 1], "780000,850000,4820")
        self.assertNotEqual(
            command[command.index("--startup-route-home-after-services") + 1],
            command[command.index("--required-target-home") + 1],
        )
        self.assertIn("--route-home-preserve-z", command)
        self.assertIn("노련한", command[command.index("--avoid-target-name") + 1])
        self.assertIn("tawny lynx cub", command[command.index("--target-nearby-avoid-name") + 1])

    def test_mid_duo_level_ten_static_route_preflight_uses_verified_index_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,2,9,8,9,10,army ant soldier,9,12,739371,789159,4714,12,0,0,0,Huginfell,1200,900\n"
                "mid,2,9,8,9,10,roaming dirge,9,29,801844,909191,4778,29,0,0,0,Gotar,1800,1200\n"
                "mid,2,9,8,9,10,tomte aggressor,9,12,748545,789700,4650,12,0,0,0,Huginfell,1200,1100\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=0,
                growth_route_preflight_low_solo_radius=2500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="mid-p2",
            )

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                x = int((query.get("x") or ["0"])[0])
                if name == "tawny lynx":
                    return []
                if name == "army ant soldier":
                    return [
                        {"name": "army ant soldier", "level": 9, "x": 740371, "y": 789159, "z": 4714},
                        {"name": "army ant soldier", "level": 9, "x": 740671, "y": 789459, "z": 4714},
                    ]
                if name in {"seithr orb", "black mauler juvenile", "wind wisp", "ghost light"} and x < 745000:
                    return [{"name": name, "level": 9, "x": 740500, "y": 789250, "z": 4714}]
                if name == "roaming dirge":
                    return [
                        {"name": "roaming dirge", "level": 9, "x": 802844, "y": 909191, "z": 4778},
                        {"name": "roaming dirge", "level": 9, "x": 803144, "y": 909491, "z": 4778},
                        {"name": "roaming dirge", "level": 9, "x": 803444, "y": 909791, "z": 4778},
                    ]
                if name == "tomte aggressor":
                    return [
                        {"name": "tomte aggressor", "level": 9, "x": 748545, "y": 789700, "z": 4650},
                        {"name": "tomte aggressor", "level": 9, "x": 748629, "y": 789753, "z": 4650},
                        {"name": "tomte aggressor", "level": 9, "x": 749036, "y": 790915, "z": 4624},
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                with mock.patch.object(growth, "growth_live_discovery_startup_landing_pressure", return_value=None):
                    with mock.patch.object(growth, "growth_live_discovery_reanchor_landing_pressure", return_value=None):
                        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 9, 2)

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertEqual(route.prefer, "tomte aggressor")
        self.assertIn("live_target_unsuitable_combat_profile:roaming dirge:caster_cc", log_text)
        self.assertNotEqual(route.prefer, "tawny lynx")
        self.assertNotEqual(route.prefer, "army ant soldier")
        self.assertNotEqual(route.prefer, "roaming dirge")

    def test_mid_duo_level_ten_preflight_rejects_unsuitable_combat_profile_before_api(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(
                growth_route_preflight=True,
                dry_run=False,
                run_dir=temp_dir,
            )
            route = growth.route_point(
                9,
                801844,
                909191,
                4778,
                "roaming dirge",
                source="hunting-index",
                mob_level=9,
                mob_count=29,
            )

            with mock.patch.object(
                growth,
                "fetch_growth_route_preflight_payload",
                side_effect=AssertionError("unsuitable combat profile must fail before live API query"),
            ):
                checked = growth.growth_route_preflight_checked_route(
                    args,
                    route,
                    realm=growth.REALMS["mid"],
                    current_level=10,
                    party_size=2,
                )

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertIsNone(checked)
        self.assertIn("live_target_unsuitable_combat_profile:roaming dirge:caster_cc", log_text)

    def test_mid_duo_level_ten_static_route_preflight_miss_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,2,9,8,9,10,army ant soldier,9,12,739371,789159,4714,12,0,0,0,Bind Start,1200,900\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="mid-p2",
            )

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", return_value=[]):
                with self.assertRaisesRegex(RuntimeError, "route_unsuitable_live_world"):
                    growth.select_growth_route_point(args, growth.REALMS["mid"], 9, 2)

    def test_mid_duo_level_ten_static_route_preflight_miss_reports_missing_index_seed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(
                growth_hunting_index="",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="mid-p2",
            )

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", return_value=[]):
                with self.assertRaisesRegex(RuntimeError, "no growth_hunting_index fallback seed"):
                    growth.select_growth_route_point(args, growth.REALMS["mid"], 9, 2)

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertIn("route_unsuitable_live_world:static_route_failed:no_growth_hunting_index_for_fallback", log_text)

    def test_mid_duo_level_ten_static_route_preflight_uses_live_discovery_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,2,9,8,9,10,army ant soldier,9,12,739371,789159,4714,12,0,0,0,Bind Start,1200,900\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="mid-p2",
            )
            live_scan_seen: list[tuple[int, int, int]] = []
            verified_names: list[str] = []

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                min_level = int((query.get("minLevel") or ["0"])[0])
                max_level = int((query.get("maxLevel") or ["0"])[0])
                radius = int((query.get("radius") or ["0"])[0])
                if name == "army ant soldier":
                    return []
                if not name and min_level <= 9 <= max_level:
                    live_scan_seen.append((min_level, max_level, radius))
                    return [
                        {"name": "undead scout", "level": 10, "x": 772504, "y": 868950, "z": 5770},
                        {"name": "undead scout", "level": 10, "x": 771932, "y": 863808, "z": 5328},
                        {"name": "undead scout", "level": 10, "x": 771546, "y": 865359, "z": 5434},
                        {"name": "undead scout", "level": 10, "x": 770758, "y": 864946, "z": 5270},
                        {"name": "노련한 tomte aggressor", "level": 10, "x": 748400, "y": 789550, "z": 4650},
                        {"name": "tomte aggressor", "level": 9, "x": 748545, "y": 789700, "z": 4650},
                        {"name": "tomte aggressor", "level": 9, "x": 748629, "y": 789753, "z": 4650},
                        {"name": "tomte aggressor", "level": 9, "x": 749036, "y": 790915, "z": 4624},
                    ]
                if name == "undead scout":
                    self.fail("live discovery must not verify over-ideal level candidates")
                if name == "tomte aggressor":
                    verified_names.append(name)
                    return [
                        {
                            "name": "tomte aggressor",
                            "level": 9,
                            "x": 748545,
                            "y": 789700,
                            "z": 4650,
                            "nearbyAvoidCount": 0,
                        },
                        {
                            "name": "tomte aggressor",
                            "level": 9,
                            "x": 748629,
                            "y": 789753,
                            "z": 4650,
                            "nearbyAvoidCount": 0,
                        },
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                with mock.patch.object(growth, "growth_live_discovery_startup_landing_pressure", return_value=None):
                    with mock.patch.object(growth, "growth_live_discovery_reanchor_landing_pressure", return_value=None):
                        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 9, 2)

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertEqual(route.prefer, "tomte aggressor")
        self.assertEqual(route.mob_level, 9)
        self.assertGreaterEqual(route.mob_count, 3)
        self.assertTrue(live_scan_seen)
        self.assertTrue(all(max_level <= 9 for _min_level, max_level, radius in live_scan_seen if radius >= 12000))
        self.assertIn("tomte aggressor", verified_names)
        self.assertIn("live_discovery_candidate_selected:tomte aggressor", log_text)

    def test_mid_duo_level_ten_carry_hunting_index_prefers_ideal_level_before_score(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,2,10,8,9,10,high score guard,10,12,742854,830717,4731,0,80,80,500,Fort Atla,16037,9000\n"
                "mid,2,10,8,9,10,ideal drakeling,9,12,758411,871134,4877,0,80,80,500,Gotar,12000,100\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=False,
                growth_route_preflight_anchor=True,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="",
            )

            route = growth.select_growth_hunting_index_point_for_target(
                args,
                "mid",
                9,
                2,
                caller_player_level=10,
            )

        self.assertIsNotNone(route)
        assert route is not None
        self.assertEqual(route.prefer, "ideal drakeling")
        self.assertEqual(route.mob_level, 9)

    def test_hunting_index_preserves_live_preflight_adjusted_startup_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score,"
                "live_preflight_status,live_preflight_adjusted,live_preflight_current_level\n"
                "mid,2,10,8,9,10,envy drakeling,9,17,762609,926852,5032,0,50,50,500,West Skona,49164,-4297,ok,1,10\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=False,
                growth_route_preflight_anchor=True,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="",
            )

            route = growth.select_growth_hunting_index_point_for_target(
                args,
                "mid",
                9,
                2,
                caller_player_level=10,
            )
            assert route is not None
            startup = growth.startup_route_home_after_services_point(
                growth.REALMS["mid"],
                route,
                current_level=10,
                party_size=2,
                ground_z_offset=0,
            )

        self.assertTrue(route.startup_anchor)
        self.assertTrue(route.live_anchor_z)
        self.assertNotEqual((startup.x, startup.y), (762609, 926852))
        self.assertLessEqual(
            math.hypot(startup.x - route.x, startup.y - route.y),
            growth.growth_required_target_home_hunt_distance(SimpleNamespace(), 10, 2, "mid", route),
        )

    def test_live_preflight_item_route_preserves_startup_anchor(self) -> None:
        route = growth.route_point(
            10,
            762609,
            926852,
            5032,
            "envy drakeling",
            source="hunting-index",
            mob_level=9,
            live_anchor_z=True,
            startup_anchor=True,
        )

        anchored = growth.growth_route_preflight_item_route(
            route,
            {"x": 762609, "y": 926852, "z": 5032, "level": 9},
        )

        self.assertIsNotNone(anchored)
        assert anchored is not None
        self.assertTrue(anchored.live_anchor_z)
        self.assertTrue(anchored.startup_anchor)
        self.assertEqual((anchored.x, anchored.y, anchored.z), (762609, 926852, 5032))

    def test_mid_duo_level_ten_live_discovery_filters_runtime_distance_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,2,9,8,9,10,army ant soldier,9,12,739371,789159,4714,12,0,0,0,Bind Start,1200,900\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="mid-p2",
            )

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                min_level = int((query.get("minLevel") or ["0"])[0])
                max_level = int((query.get("maxLevel") or ["0"])[0])
                if name in {"army ant soldier", "tawny lynx"}:
                    return []
                if not name and min_level <= 9 <= max_level:
                    return [
                        {"name": "tawny lynx", "level": 8, "x": 743000, "y": 789000, "z": 4777},
                        {"name": "tawny lynx", "level": 8, "x": 746000, "y": 789000, "z": 4777},
                        {"name": "tawny lynx", "level": 8, "x": 749500, "y": 789000, "z": 4777},
                        {"name": "tomte aggressor", "level": 9, "x": 748545, "y": 789700, "z": 4650},
                        {"name": "tomte aggressor", "level": 9, "x": 748629, "y": 789753, "z": 4650},
                        {"name": "tomte aggressor", "level": 9, "x": 749036, "y": 790915, "z": 4624},
                    ]
                if name == "tomte aggressor":
                    return [
                        {"name": "tomte aggressor", "level": 9, "x": 748545, "y": 789700, "z": 4650},
                        {"name": "tomte aggressor", "level": 9, "x": 748629, "y": 789753, "z": 4650},
                        {"name": "tomte aggressor", "level": 9, "x": 749036, "y": 790915, "z": 4624},
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                with mock.patch.object(growth, "growth_live_discovery_startup_landing_pressure", return_value=None):
                    with mock.patch.object(growth, "growth_live_discovery_reanchor_landing_pressure", return_value=None):
                        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 9, 2)

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertEqual(route.prefer, "tomte aggressor")
        self.assertNotEqual(route.prefer, "tawny lynx")
        self.assertIn("live_discovery_runtime_distance_mismatch:tawny lynx", log_text)
        self.assertIn("live_discovery_candidate_selected:tomte aggressor", log_text)

    def test_mid_duo_level_ten_short_engage_preflight_keeps_leash_margin(self) -> None:
        args = SimpleNamespace(
            growth_fast_travel="route-home",
            max_target_distance=2200.0,
            target_home_max_distance=10000.0,
            combat_home_leash_distance=10000.0,
        )
        route = growth.route_point(
            10,
            765855,
            831240,
            4765,
            "tawny lynx",
            source="hunting-index",
            mob_level=8,
            mob_count=3,
        )
        items = (
            {"name": "tawny lynx", "level": 8, "x": 764694, "y": 831252, "z": 4728},
            {"name": "tawny lynx", "level": 8, "x": 764429, "y": 829613, "z": 4777},
        )

        runtime_items = growth.growth_route_preflight_runtime_distance_items(
            args,
            route,
            items,
            realm_key="mid",
            current_level=10,
            party_size=2,
        )

        self.assertEqual(len(runtime_items), 1)
        self.assertEqual(runtime_items[0]["x"], 764694)
        self.assertEqual(
            growth.growth_route_preflight_safe_home_distance(
                args,
                route,
                realm_key="mid",
                current_level=10,
                party_size=2,
            ),
            1800.0,
        )

    def test_mid_duo_level_ten_named_preflight_rejects_runtime_distance_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=8000,
                growth_route_preflight_limit=10,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="mid-p2",
            )
            route = growth.route_point(
                10,
                764541,
                829533,
                4777,
                "tawny lynx",
                "",
                source="hunting-index",
                mob_level=8,
                mob_count=8,
                live_anchor_z=True,
            )

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                if (query.get("name") or [""])[0] == "tawny lynx":
                    return [
                        {"name": "tawny lynx", "level": 8, "x": 764541, "y": 829533, "z": 4777, "healthPercent": 100},
                        {"name": "tawny lynx", "level": 8, "x": 763228, "y": 827074, "z": 4765, "healthPercent": 100},
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                checked = growth.growth_route_preflight_checked_route(
                    args,
                    route,
                    realm=growth.REALMS["mid"],
                    current_level=10,
                    party_size=2,
                )

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertIsNone(checked)
        self.assertIn("live_target_runtime_distance_mismatch:tawny lynx", log_text)
        self.assertIn("available=2:runtime=1:required=2:max=2200:home=2200", log_text)

    def test_mid_duo_level_ten_live_discovery_deprioritizes_startup_plane_delta(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,2,9,8,9,10,army ant soldier,9,12,739371,789159,4714,12,0,0,0,Bind Start,1200,900\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="mid-p2",
            )
            verified_names: list[str] = []

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                min_level = int((query.get("minLevel") or ["0"])[0])
                max_level = int((query.get("maxLevel") or ["0"])[0])
                if name == "army ant soldier":
                    return []
                if not name and min_level <= 9 <= max_level:
                    return [
                        {"name": "young grendelorm", "level": 9, "x": 802660, "y": 683810, "z": 15000},
                        {"name": "young grendelorm", "level": 9, "x": 802620, "y": 683840, "z": 15000},
                        {"name": "young grendelorm", "level": 9, "x": 802700, "y": 683760, "z": 15000},
                        {"name": "young grendelorm", "level": 9, "x": 802740, "y": 683790, "z": 15000},
                        {"name": "tomte aggressor", "level": 9, "x": 748545, "y": 789700, "z": 4650},
                        {"name": "tomte aggressor", "level": 9, "x": 748629, "y": 789753, "z": 4650},
                        {"name": "tomte aggressor", "level": 9, "x": 749036, "y": 790915, "z": 4624},
                    ]
                if name == "young grendelorm":
                    verified_names.append(name)
                    return [
                        {"name": "young grendelorm", "level": 9, "x": 802660, "y": 683810, "z": 15000},
                        {"name": "young grendelorm", "level": 9, "x": 802620, "y": 683840, "z": 15000},
                        {"name": "young grendelorm", "level": 9, "x": 802700, "y": 683760, "z": 15000},
                    ]
                if name == "tomte aggressor":
                    verified_names.append(name)
                    return [
                        {"name": "tomte aggressor", "level": 9, "x": 748545, "y": 789700, "z": 4650},
                        {"name": "tomte aggressor", "level": 9, "x": 748629, "y": 789753, "z": 4650},
                        {"name": "tomte aggressor", "level": 9, "x": 749036, "y": 790915, "z": 4624},
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                with mock.patch.object(growth, "growth_live_discovery_startup_landing_pressure", return_value=None):
                    with mock.patch.object(growth, "growth_live_discovery_reanchor_landing_pressure", return_value=None):
                        with mock.patch.object(growth, "growth_route_preflight_startup_safety_radius", return_value=0.0):
                            route = growth.select_growth_route_point(args, growth.REALMS["mid"], 9, 2)

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertEqual(route.prefer, "tomte aggressor")
        self.assertIn("young grendelorm", verified_names)
        self.assertIn("tomte aggressor", verified_names)
        self.assertIn("live_discovery_startup_plane_delta:young grendelorm", log_text)
        self.assertIn("live_discovery_candidate_selected:tomte aggressor", log_text)

    def test_mid_duo_level_ten_live_discovery_filters_nearby_avoid_blocked_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,2,9,8,8,10,rock crab,8,5,756054,741454,6395,5,0,0,0,Bind Start,1200,900\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 8, 3),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="mid-p2",
            )
            broad_scan_nearby_names: list[str] = []

            blocked = [
                {
                    "name": "rock crab",
                    "level": 8,
                    "x": 754381,
                    "y": 739487,
                    "z": 8980,
                    "distance": 100,
                    "nearbyAvoidCount": 2,
                    "healthPercent": 100,
                },
                {
                    "name": "rock crab",
                    "level": 8,
                    "x": 754159,
                    "y": 739645,
                    "z": 8980,
                    "distance": 200,
                    "nearbyAvoidCount": 1,
                    "healthPercent": 100,
                },
            ]
            safe = [
                {
                    "name": "rock crab",
                    "level": 8,
                    "x": 754233,
                    "y": 741403,
                    "z": 7026,
                    "distance": 1900,
                    "nearbyAvoidCount": 0,
                    "healthPercent": 100,
                },
                {
                    "name": "rock crab",
                    "level": 8,
                    "x": 754906,
                    "y": 741176,
                    "z": 7362,
                    "distance": 1200,
                    "nearbyAvoidCount": 0,
                    "healthPercent": 100,
                },
            ]

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                x = int((query.get("x") or ["0"])[0])
                if not name:
                    broad_scan_nearby_names.append((query.get("nearbyAvoidName") or [""])[0])
                    return blocked + safe
                if name == "rock crab" and x == 756054:
                    return blocked
                if name == "rock crab":
                    return safe
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                with mock.patch.object(growth, "growth_live_discovery_startup_landing_pressure", return_value=None):
                    with mock.patch.object(growth, "growth_live_discovery_reanchor_landing_pressure", return_value=None):
                        with mock.patch.object(growth, "growth_route_preflight_startup_safety_radius", return_value=0.0):
                            route = growth.select_growth_route_point(args, growth.REALMS["mid"], 9, 2)

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertEqual(route.prefer, "rock crab")
        self.assertNotIn((route.x, route.y), {(754381, 739487), (754159, 739645)})
        self.assertTrue(broad_scan_nearby_names)
        self.assertIn("carrion crawler", broad_scan_nearby_names[0])
        self.assertIn("live_target_nearby_avoid_pressure:rock crab", log_text)
        self.assertIn("live_discovery_candidate_selected:rock crab", log_text)

    def test_mid_duo_level_ten_live_discovery_allows_startup_plane_delta_without_safe_alternative(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,2,9,8,9,10,army ant soldier,9,12,739371,789159,4714,12,0,0,0,Bind Start,1200,900\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="mid-p2",
            )

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                min_level = int((query.get("minLevel") or ["0"])[0])
                max_level = int((query.get("maxLevel") or ["0"])[0])
                if name == "army ant soldier":
                    return []
                if not name and min_level <= 9 <= max_level:
                    return [
                        {"name": "young grendelorm", "level": 9, "x": 802660, "y": 683810, "z": 15000},
                        {"name": "young grendelorm", "level": 9, "x": 802620, "y": 683840, "z": 15000},
                        {"name": "young grendelorm", "level": 9, "x": 802700, "y": 683760, "z": 15000},
                    ]
                if name == "young grendelorm":
                    return [
                        {"name": "young grendelorm", "level": 9, "x": 802660, "y": 683810, "z": 15000},
                        {"name": "young grendelorm", "level": 9, "x": 802620, "y": 683840, "z": 15000},
                        {"name": "young grendelorm", "level": 9, "x": 802700, "y": 683760, "z": 15000},
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                with mock.patch.object(growth, "growth_live_discovery_startup_landing_pressure", return_value=None):
                    with mock.patch.object(growth, "growth_live_discovery_reanchor_landing_pressure", return_value=None):
                        with mock.patch.object(growth, "growth_route_preflight_startup_safety_radius", return_value=0.0):
                            route = growth.select_growth_route_point(args, growth.REALMS["mid"], 9, 2)

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertEqual(route.prefer, "young grendelorm")
        self.assertIn("live_discovery_startup_plane_delta:young grendelorm", log_text)
        self.assertIn("live_discovery_candidate_selected:young grendelorm", log_text)

    def test_mid_duo_level_ten_live_discovery_rejects_startup_landing_pressure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,2,9,8,9,10,army ant soldier,9,12,739371,789159,4714,12,0,0,0,Bind Start,1200,900\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="mid-p2",
            )
            pillager_route = growth.route_point(
                9,
                759461,
                761912,
                4530,
                "tomte pillager",
                source="hunting-index",
                mob_level=9,
                mob_count=4,
                live_anchor_z=True,
            )
            pillager_landing = growth.live_anchor_party_safe_landing_point(
                growth.REALMS["mid"],
                pillager_route,
                current_level=10,
                party_size=2,
                ground_z_offset=0,
            )
            self.assertIsNotNone(pillager_landing)
            assert pillager_landing is not None

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                x = int((query.get("x") or ["0"])[0])
                y = int((query.get("y") or ["0"])[0])
                radius = int((query.get("radius") or ["0"])[0])
                min_level = int((query.get("minLevel") or ["0"])[0])
                max_level = int((query.get("maxLevel") or ["0"])[0])
                if name == "army ant soldier":
                    return []
                if not name and radius <= 2000 and 754000 <= x <= 764000 and 760000 <= y <= 770000:
                    return [
                        {
                            "name": "tomte plunderer",
                            "level": 9,
                            "x": x,
                            "y": y,
                            "z": 4530,
                        }
                    ]
                if not name and 754000 <= x <= 760000 and 760000 <= y <= 764000:
                    return [
                        {
                            "name": "tomte plunderer",
                            "level": 9,
                            "x": pillager_landing.x,
                            "y": pillager_landing.y,
                            "z": pillager_landing.z,
                        }
                    ]
                if not name and x == 739371 and y == 789159 and min_level <= 9 <= max_level:
                    return [
                        {"name": "tomte pillager", "level": 9, "x": 759461, "y": 761912, "z": 4530},
                        {"name": "tomte pillager", "level": 9, "x": 759500, "y": 761940, "z": 4530},
                        {"name": "tomte pillager", "level": 9, "x": 759540, "y": 761970, "z": 4530},
                        {"name": "tomte pillager", "level": 9, "x": 759580, "y": 762000, "z": 4530},
                        {"name": "tomte aggressor", "level": 9, "x": 748545, "y": 789700, "z": 4650},
                        {"name": "tomte aggressor", "level": 9, "x": 748629, "y": 789753, "z": 4650},
                        {"name": "tomte aggressor", "level": 9, "x": 749036, "y": 790915, "z": 4624},
                    ]
                if name == "tomte pillager":
                    return [
                        {"name": "tomte pillager", "level": 9, "x": 759461, "y": 761912, "z": 4530},
                        {"name": "tomte pillager", "level": 9, "x": 759500, "y": 761940, "z": 4530},
                        {"name": "tomte pillager", "level": 9, "x": 759540, "y": 761970, "z": 4530},
                    ]
                if name == "tomte aggressor":
                    return [
                        {"name": "tomte aggressor", "level": 9, "x": 748545, "y": 789700, "z": 4650},
                        {"name": "tomte aggressor", "level": 9, "x": 748629, "y": 789753, "z": 4650},
                        {"name": "tomte aggressor", "level": 9, "x": 749036, "y": 790915, "z": 4624},
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                with mock.patch.object(growth, "growth_live_discovery_reanchor_landing_pressure", return_value=None):
                    route = growth.select_growth_route_point(args, growth.REALMS["mid"], 9, 2)

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertEqual(route.prefer, "tomte aggressor")
        self.assertIn("live_discovery_startup_landing_pressure:tomte pillager", log_text)
        self.assertIn("nearest=tomte plunderer", log_text)
        self.assertIn("live_discovery_candidate_selected:tomte aggressor", log_text)

    def test_mid_duo_level_ten_live_discovery_reanchors_startup_landing_pressure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,2,9,8,9,10,army ant soldier,9,12,739371,789159,4714,12,0,0,0,Bind Start,1200,900\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="mid-p2",
            )
            landing_pressure_calls = 0

            def fake_preflight(url: str, _timeout: float) -> object:
                nonlocal landing_pressure_calls
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                x = int((query.get("x") or ["0"])[0])
                y = int((query.get("y") or ["0"])[0])
                radius = int((query.get("radius") or ["0"])[0])
                min_level = int((query.get("minLevel") or ["0"])[0])
                max_level = int((query.get("maxLevel") or ["0"])[0])
                if name == "army ant soldier":
                    return []
                if not name and radius <= 2000:
                    landing_pressure_calls += 1
                    if landing_pressure_calls == 1:
                        return [{"name": "tomte plunderer", "level": 9, "x": x, "y": y, "z": 4530}]
                    return []
                if not name and x == 739371 and y == 789159 and min_level <= 9 <= max_level:
                    return [
                        {"name": "tomte pillager", "level": 9, "x": 759461, "y": 761912, "z": 4530},
                        {"name": "tomte pillager", "level": 9, "x": 759500, "y": 761940, "z": 4530},
                        {"name": "tomte pillager", "level": 9, "x": 759540, "y": 761970, "z": 4530},
                    ]
                if name == "tomte pillager":
                    return [
                        {"name": "tomte pillager", "level": 9, "x": 759461, "y": 761912, "z": 4530},
                        {"name": "tomte pillager", "level": 9, "x": 759500, "y": 761940, "z": 4530},
                        {"name": "tomte pillager", "level": 9, "x": 759540, "y": 761970, "z": 4530},
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                route = growth.select_growth_route_point(args, growth.REALMS["mid"], 9, 2)

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertEqual(route.prefer, "tomte pillager")
        self.assertNotEqual((route.x, route.y), (759461, 761912))
        self.assertIn("live_discovery_startup_landing_anchor_replaced:tomte pillager", log_text)
        self.assertIn("live_discovery_candidate_selected:tomte pillager", log_text)

    def test_live_discovery_landing_pressure_counts_lower_level_hostiles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(
                growth_fast_travel="route-home",
                ground_z_offset=0,
                run_dir=temp_dir,
            )
            route = growth.route_point(
                10,
                767237,
                781077,
                4400,
                "spindly rock crab",
                source="hunting-index",
                mob_level=9,
                mob_count=8,
                live_anchor_z=True,
            )
            landing = dataclasses.replace(route, x=766093, y=783407, z=4679)
            queried_min_levels: list[int] = []

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                queried_min_levels.append(int((query.get("minLevel") or ["0"])[0]))
                return [
                    {
                        "name": "rock crab",
                        "level": 7,
                        "x": 766556,
                        "y": 784047,
                        "z": 4505,
                        "healthPercent": 100,
                    }
                ]

            with (
                mock.patch.object(growth, "live_anchor_party_safe_landing_point", return_value=landing),
                mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight),
            ):
                pressure = growth.growth_live_discovery_startup_landing_pressure(
                    args,
                    growth.REALMS["mid"],
                    route,
                    endpoint="http://dummy-api:5000/api/dummy/combat/npcs",
                    timeout=0.1,
                    current_level=10,
                    party_size=2,
                )

        self.assertIsNotNone(pressure)
        assert pressure is not None
        self.assertLessEqual(min(queried_min_levels), 7)
        self.assertEqual(pressure["nearest_name"], "rock crab")
        self.assertEqual(pressure["nearest_distance"], 790)

    def test_mid_duo_level_ten_spindly_route_rejects_rock_crab_nearby_pressure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(
                growth_fast_travel="route-home",
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=8000,
                growth_route_preflight_limit=10,
                growth_route_preflight_min_available_targets=2,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
            )
            route = growth.route_point(
                10,
                738261,
                778190,
                4390,
                "spindly rock crab",
                source="hunting-index",
                mob_level=9,
                mob_count=8,
                live_anchor_z=True,
            )
            queried_nearby_avoid = ""

            def fake_preflight(url: str, _timeout: float) -> object:
                nonlocal queried_nearby_avoid
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                queried_nearby_avoid = (query.get("nearbyAvoidName") or [""])[0]
                rock_crab_guard_enabled = "rock crab" in queried_nearby_avoid.lower()
                if name == "spindly rock crab":
                    nearby_count = 1 if rock_crab_guard_enabled else 0
                    return [
                        {
                            "name": "spindly rock crab",
                            "level": 9,
                            "x": 738261,
                            "y": 778190,
                            "z": 4390,
                            "nearbyAvoidCount": nearby_count,
                            "healthPercent": 100,
                        },
                        {
                            "name": "spindly rock crab",
                            "level": 9,
                            "x": 738690,
                            "y": 780288,
                            "z": 4390,
                            "nearbyAvoidCount": nearby_count,
                            "healthPercent": 100,
                        },
                    ]
                return []

            with (
                mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight),
                mock.patch.object(
                    growth,
                    "growth_route_preflight_z_viable_items",
                    side_effect=lambda _args, _route, items, **_kwargs: (items, ()),
                ),
            ):
                status = growth.growth_route_preflight_status(
                    args,
                    route,
                    realm=growth.REALMS["mid"],
                    current_level=10,
                    party_size=2,
                )

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertFalse(status)
        self.assertIn("rock crab", queried_nearby_avoid.lower())
        self.assertIn("live_target_nearby_avoid_pressure:spindly rock crab", log_text)

    def test_live_discovery_reanchor_rejects_target_plane_delta(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(
                growth_fast_travel="route-home",
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                ground_z_offset=0,
                max_target_distance=6500.0,
                run_dir=temp_dir,
            )
            route = growth.route_point(
                10,
                759442,
                704305,
                6058,
                "manes demon",
                source="hunting-index",
                mob_level=8,
                mob_count=5,
                live_anchor_z=True,
            )

            def high_plane_landing(_realm, candidate, **_kwargs):
                return dataclasses.replace(candidate, z=8772)

            with (
                mock.patch.object(growth, "sample_route_z", return_value=8772),
                mock.patch.object(growth, "live_anchor_party_safe_landing_point", side_effect=high_plane_landing),
                mock.patch.object(growth, "growth_live_discovery_startup_landing_pressure", return_value=None),
                mock.patch.object(growth, "growth_route_preflight_status", return_value=True) as status_mock,
            ):
                reanchored = growth.growth_live_discovery_reanchor_landing_pressure(
                    args,
                    growth.REALMS["mid"],
                    route,
                    endpoint="http://dummy-api:5000/api/dummy/combat/npcs",
                    timeout=0.1,
                    current_level=10,
                    party_size=2,
                )

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertIsNone(reanchored)
        status_mock.assert_not_called()
        self.assertIn("live_discovery_reanchor_target_plane_delta:manes demon", log_text)
        self.assertIn("target_z=6058", log_text)
        self.assertIn("landing_z=8772", log_text)

    def test_mid_duo_level_ten_tomte_route_marks_same_family_nearby_avoid(self) -> None:
        route = growth.route_point(
            9,
            748545,
            789700,
            4650,
            "tomte aggressor",
            source="hunting-index",
            mob_level=9,
            mob_count=3,
            live_anchor_z=True,
        )

        nearby_avoid = growth.growth_target_nearby_avoid_names_for_route(10, 2, "mid", route)

        self.assertIn("tomte aggressor", nearby_avoid)
        self.assertIn("tomte skirmisher", nearby_avoid)
        self.assertIn("tomte pillager", nearby_avoid)
        self.assertIn("tomte plunderer", nearby_avoid)

    def test_mid_duo_level_ten_manes_route_rejects_hill_cat_grumoz_pressure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(
                growth_fast_travel="route-home",
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=8000,
                growth_route_preflight_limit=10,
                growth_route_preflight_min_available_targets=2,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                target_home_max_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
            )
            route = growth.route_point(
                10,
                764179,
                703189,
                4728,
                "manes demon",
                source="hunting-index",
                mob_level=8,
                mob_count=9,
                live_anchor_z=True,
            )
            queried_nearby_avoid = ""

            def fake_preflight(url: str, _timeout: float) -> object:
                nonlocal queried_nearby_avoid
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                queried_nearby_avoid = (query.get("nearbyAvoidName") or [""])[0]
                if name == "manes demon":
                    return [
                        {
                            "name": "manes demon",
                            "level": 8,
                            "x": 760987,
                            "y": 702317,
                            "z": 6058,
                            "healthPercent": 100,
                            "nearbyAvoidCount": 1,
                        },
                        {
                            "name": "manes demon",
                            "level": 8,
                            "x": 761220,
                            "y": 700208,
                            "z": 6532,
                            "healthPercent": 100,
                            "nearbyAvoidCount": 1,
                        },
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                checked = growth.growth_route_preflight_checked_route(
                    args,
                    route,
                    realm=growth.REALMS["mid"],
                    current_level=10,
                    party_size=2,
                )

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertIsNone(checked)
        self.assertIn("hill cat", queried_nearby_avoid)
        self.assertIn("grumoz demon", queried_nearby_avoid)
        self.assertIn("live_target_nearby_avoid_pressure:manes demon", log_text)

    def test_mid_duo_level_ten_preflight_rejects_same_family_tomte_pressure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(
                growth_fast_travel="route-home",
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="mid-p2",
            )
            route = growth.route_point(
                9,
                748545,
                789700,
                4650,
                "tomte aggressor",
                source="hunting-index",
                mob_level=9,
                mob_count=3,
                live_anchor_z=True,
            )

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                nearby_names = (query.get("nearbyAvoidName") or [""])[0]
                nearby_radius = int((query.get("nearbyRadius") or ["0"])[0])
                if name != "tomte aggressor":
                    return []
                self.assertIn("tomte skirmisher", nearby_names)
                self.assertIn("tomte pillager", nearby_names)
                self.assertIn("tomte plunderer", nearby_names)
                self.assertEqual(nearby_radius, 1800)
                return [
                    {"name": "tomte aggressor", "level": 9, "x": 748545, "y": 789700, "z": 4650, "nearbyAvoidCount": 1},
                    {"name": "tomte aggressor", "level": 9, "x": 748629, "y": 789753, "z": 4650, "nearbyAvoidCount": 1},
                    {"name": "tomte aggressor", "level": 9, "x": 749036, "y": 790915, "z": 4624, "nearbyAvoidCount": 1},
                ]

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                status = growth.growth_route_preflight_status(
                    args,
                    route,
                    realm=growth.REALMS["mid"],
                    current_level=10,
                    party_size=2,
                )

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertFalse(status)
        self.assertIn("live_target_nearby_avoid_pressure:tomte aggressor", log_text)
        self.assertIn("blocked=3", log_text)

    def test_mid_duo_level_ten_static_route_preflight_uses_carry_floor_index_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,2,10,8,8,8,ghost light,8,19,757484,847726,4650,19,0,0,500,Gotar,17764,905.759\n",
                encoding="utf-8",
            )
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            args = SimpleNamespace(
                host="127.0.0.1",
                port=10300,
                segment_seconds=300,
                safe_exit_max_seconds=90,
                safe_exit_recent_damage_grace=12,
                ramp_up=5,
                login_retries=12,
                login_retry_delay=5.0,
                api_port=5000,
                max_target_distance=6500.0,
                target_home_max_distance=1400.0,
                combat_home_leash_distance=1200.0,
                target_timeout=65,
                combat_interval=1.5,
                target_pool=5,
                smooth_move_interval=0.2,
                movement_speed=240.0,
                path_last_mile_distance=1200.0,
                ground_z_offset=0,
                encounter_log_interval=3.0,
                nav_api_url="http://dummy-api:5000",
                live_api_url="",
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                run_dir=temp_dir,
                case_name="mid-p2",
            )
            observed_target_bands: list[tuple[int, int]] = []

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                min_level = int((query.get("minLevel") or ["0"])[0])
                max_level = int((query.get("maxLevel") or ["0"])[0])
                if name == "tawny lynx":
                    return []
                if name == "ghost light":
                    observed_target_bands.append((min_level, max_level))
                    return [
                        {"name": "ghost light", "level": 8, "x": 757484, "y": 847726, "z": 4650},
                        {"name": "ghost light", "level": 8, "x": 757920, "y": 847930, "z": 4650},
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                route = growth.select_growth_route_point(args, growth.REALMS["mid"], 9, 2)
                command = growth.build_behavior_command(
                    args=args,
                    realm=growth.REALMS["mid"],
                    accounts_csv=Path("accounts.csv"),
                    case_dir=case_dir,
                    segment_index=1,
                    party_size=2,
                    current_level=10,
                    path_graph=Path("graph.json"),
                )
            payload = json.loads((case_dir / "live-control.json").read_text(encoding="utf-8"))

        self.assertEqual(route.prefer, "ghost light")
        self.assertEqual(route.mob_level, 8)
        self.assertIn((8, 10), observed_target_bands)
        self.assertEqual(command[command.index("--require-target-name") + 1], "ghost light")
        self.assertEqual(command[command.index("--min-target-level") + 1], "8")
        self.assertGreaterEqual(int(command[command.index("--max-target-level") + 1]), 9)
        self.assertEqual(payload["baseline_min_target_level"], 8)

    def test_mid_duo_level_ten_static_route_preflight_expands_stale_candidate_radius(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,2,10,8,8,8,ghost light,8,19,757484,847726,4650,19,0,0,500,Gotar,17764,905.759\n"
                "mid,2,10,8,8,8,host of the wind,8,11,750636,854357,4800,11,0,0,0,Gotar,18500,-608.521\n",
                encoding="utf-8",
            )
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            args = SimpleNamespace(
                host="127.0.0.1",
                port=10300,
                segment_seconds=300,
                safe_exit_max_seconds=90,
                safe_exit_recent_damage_grace=12,
                ramp_up=5,
                login_retries=12,
                login_retry_delay=5.0,
                api_port=5000,
                max_target_distance=6500.0,
                target_home_max_distance=1400.0,
                combat_home_leash_distance=1200.0,
                target_timeout=65,
                combat_interval=1.5,
                target_pool=5,
                smooth_move_interval=0.2,
                movement_speed=240.0,
                path_last_mile_distance=1200.0,
                ground_z_offset=0,
                encounter_log_interval=3.0,
                nav_api_url="http://dummy-api:5000",
                live_api_url="",
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=0,
                growth_route_preflight_low_solo_radius=2500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                run_dir=temp_dir,
                case_name="mid-p2",
            )
            host_radii: list[int] = []

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                radius = int((query.get("radius") or ["0"])[0])
                if name == "tawny lynx":
                    return [
                        {
                            "name": "tawny lynx",
                            "level": 8,
                            "x": 778948,
                            "y": 850162,
                            "z": 4828,
                            "nearbyAvoidCount": 1,
                            "healthPercent": 100,
                        },
                        {
                            "name": "tawny lynx",
                            "level": 8,
                            "x": 779017,
                            "y": 849258,
                            "z": 4822,
                            "nearbyAvoidCount": 2,
                            "healthPercent": 100,
                        },
                    ]
                if name == "ghost light":
                    if radius < 8000:
                        return []
                    return [
                        {"name": "노련한 ghost light", "level": 8, "x": 757715, "y": 848197, "z": 4598},
                        {"name": "노련한 ghost light", "level": 8, "x": 756941, "y": 847660, "z": 4640},
                    ]
                if name == "host of the wind":
                    host_radii.append(radius)
                    if radius < 8000:
                        return [{"name": "노련한 host of the wind", "level": 8, "x": 746726, "y": 859489, "z": 4861}]
                    return [
                        {"name": "host of the wind", "level": 8, "x": 745886, "y": 858965, "z": 4909},
                        {"name": "host of the wind", "level": 8, "x": 746173, "y": 859754, "z": 4926},
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                route = growth.select_growth_route_point(args, growth.REALMS["mid"], 9, 2)
                command = growth.build_behavior_command(
                    args=args,
                    realm=growth.REALMS["mid"],
                    accounts_csv=Path("accounts.csv"),
                    case_dir=case_dir,
                    segment_index=1,
                    party_size=2,
                    current_level=10,
                    path_graph=Path("graph.json"),
                )

        self.assertEqual(route.prefer, "host of the wind")
        self.assertIn(8000, host_radii)
        self.assertEqual(command[command.index("--require-target-name") + 1], "host of the wind")
        self.assertIn("--require-target-name-exact", command)
        self.assertEqual(command[command.index("--min-target-level") + 1], "8")

    def test_hib_duo_level_ten_static_route_preflight_can_use_fresh_water_beetle_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "hib,2,10,7,7,7,water beetle,7,13,350899,531716,4610,13,0,0,0,Tir na mBeo,5916,1035\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(7, 8, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="hib-p2",
            )
            observed_limits: list[int] = []

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                x = int((query.get("x") or ["0"])[0])
                limit = int((query.get("limit") or ["0"])[0])
                if name == "water beetle" and x == 350899:
                    observed_limits.append(limit)
                    if limit < 10:
                        return [
                            {
                                "name": "노련한 water beetle",
                                "level": 8,
                                "x": 357000,
                                "y": 532035,
                                "z": 4598,
                                "healthPercent": 91,
                            },
                            {
                                "name": "노련한 water beetle",
                                "level": 7,
                                "x": 357300,
                                "y": 532352,
                                "z": 4598,
                                "healthPercent": 91,
                            },
                            {
                                "name": "water beetle",
                                "level": 8,
                                "x": 349169,
                                "y": 532209,
                                "z": 4598,
                                "healthPercent": 100,
                            },
                        ]
                    return [
                        {
                            "name": "노련한 water beetle",
                            "level": 8,
                            "x": 357000,
                            "y": 532035,
                            "z": 4598,
                            "healthPercent": 91,
                        },
                        {
                            "name": "노련한 water beetle",
                            "level": 7,
                            "x": 357300,
                            "y": 532352,
                            "z": 4598,
                            "healthPercent": 91,
                        },
                        {
                            "name": "water beetle",
                            "level": 8,
                            "x": 349169,
                            "y": 532209,
                            "z": 4598,
                            "healthPercent": 100,
                        },
                        {
                            "name": "water beetle",
                            "level": 8,
                            "x": 349250,
                            "y": 532858,
                            "z": 4598,
                            "healthPercent": 100,
                        },
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                route = growth.select_growth_route_point(args, growth.REALMS["hib"], 8, 2)

        self.assertEqual(route.prefer, "water beetle")
        self.assertGreaterEqual(route.mob_level, 7)
        self.assertNotEqual((route.x, route.y), (347282, 504287))
        self.assertTrue(observed_limits)
        self.assertGreaterEqual(observed_limits[0], 10)

    def test_hib_duo_level_ten_fresh_water_beetle_fallback_rejects_nearby_prefixed_same_base(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "hib,2,10,7,7,7,water beetle,7,13,350899,531716,4610,13,0,0,0,Tir na mBeo,5916,1035\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(7, 8, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="hib-p2",
            )

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                x = int((query.get("x") or ["0"])[0])
                if name == "water beetle" and x == 350899:
                    return [
                        {
                            "name": "노련한 water beetle",
                            "level": 8,
                            "x": 349667,
                            "y": 532035,
                            "z": 4598,
                            "healthPercent": 91,
                        },
                        {
                            "name": "노련한 water beetle",
                            "level": 7,
                            "x": 349720,
                            "y": 532520,
                            "z": 4598,
                            "healthPercent": 91,
                        },
                        {
                            "name": "water beetle",
                            "level": 8,
                            "x": 349169,
                            "y": 532209,
                            "z": 4598,
                            "healthPercent": 100,
                        },
                        {
                            "name": "water beetle",
                            "level": 8,
                            "x": 349250,
                            "y": 532858,
                            "z": 4598,
                            "healthPercent": 100,
                        },
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                with self.assertRaisesRegex(RuntimeError, "route_unsuitable_live_world"):
                    growth.select_growth_route_point(args, growth.REALMS["hib"], 8, 2)

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertIn("live_growth_prefix_pressure:water beetle", log_text)

    def test_mid_duo_level_ten_preflight_rejects_level_nine_prefixed_same_base(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,2,9,8,8,8,svartalf outcast,8,20,730969,834240,4792,20,0,0,500,Gotar,3000,7000\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 8, 0),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="mid-p2",
            )

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                if name == "svartalf outcast":
                    return [
                        {
                            "name": "svartalf outcast",
                            "level": 8,
                            "x": 731329,
                            "y": 833562,
                            "z": 4878,
                            "healthPercent": 100,
                        },
                        {
                            "name": "svartalf outcast",
                            "level": 8,
                            "x": 731225,
                            "y": 833443,
                            "z": 4902,
                            "healthPercent": 100,
                        },
                    ]
                if name == "노련한 svartalf outcast":
                    return [
                        {
                            "name": "노련한 svartalf outcast",
                            "level": 9,
                            "x": 731137,
                            "y": 834168,
                            "z": 4868,
                            "healthPercent": 91,
                        }
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                with self.assertRaisesRegex(RuntimeError, "route_unsuitable_live_world"):
                    growth.select_growth_route_point(args, growth.REALMS["mid"], 10, 2)

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertIn("live_growth_prefix_pressure:svartalf outcast", log_text)

    def test_mid_duo_level_ten_preflight_reanchors_when_landing_has_no_buffer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = SimpleNamespace(
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=2,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="mid-p2",
            )
            route = growth.route_point(
                10,
                732369,
                834240,
                4792,
                "svartalf outcast",
                "",
                "Gotar",
                source="hunting-index",
                mob_level=8,
                mob_count=20,
            )

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                if (query.get("name") or [""])[0] == "svartalf outcast":
                    return [
                        {
                            "name": "svartalf outcast",
                            "level": 8,
                            "x": 732669,
                            "y": 834240,
                            "z": 4792,
                            "healthPercent": 100,
                        },
                        {
                            "name": "svartalf outcast",
                            "level": 8,
                            "x": 733000,
                            "y": 834240,
                            "z": 4792,
                            "healthPercent": 100,
                        },
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                checked = growth.growth_route_preflight_checked_route(
                    args,
                    route,
                    realm=growth.REALMS["mid"],
                    current_level=10,
                    party_size=2,
                )

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertIsNotNone(checked)
        assert checked is not None
        self.assertTrue(checked.startup_anchor)
        self.assertNotEqual((checked.x, checked.y), (route.x, route.y))
        self.assertIn("live_startup_anchor_replaced:spawn_overlap", log_text)

    def test_mid_duo_level_ten_startup_anchor_skips_close_landing_pressure(self) -> None:
        args = SimpleNamespace(ground_z_offset=0)
        route = growth.route_point(
            10,
            10000,
            10000,
            4800,
            "perfidious pook",
            "",
            "Gotar",
            source="hunting-index",
            mob_level=10,
            mob_count=20,
        )
        primary_offsets = (
            (1400, 0),
            (1400, 1400),
            (0, 1400),
            (-1400, 1400),
            (-1400, 0),
            (-1400, -1400),
            (1400, -1400),
        )
        items: list[dict[str, object]] = [
            {"name": "perfidious pook", "level": 10, "x": 10000, "y": 10000, "z": 4800, "healthPercent": 100},
            {"name": "perfidious pook", "level": 10, "x": 10000, "y": 8986, "z": 4800, "healthPercent": 100},
        ]
        for dx, dy in primary_offsets:
            items.append(
                {
                    "name": "perfidious pook",
                    "level": 10,
                    "x": 10000 + dx,
                    "y": 10000 + dy,
                    "z": 4800,
                    "healthPercent": 100,
                }
            )

        with mock.patch.object(growth, "sample_route_z", return_value=4800):
            checked = growth.growth_route_preflight_startup_safe_anchor_route(
                args,
                route,
                tuple(items),
                realm=growth.REALMS["mid"],
                current_level=10,
                party_size=2,
                safety_radius=350,
            )

        self.assertIsNotNone(checked)
        assert checked is not None
        self.assertNotEqual((checked.x, checked.y), (10000, 8600))
        nearest_distance = min(math.hypot(checked.x - int(item["x"]), checked.y - int(item["y"])) for item in items)
        self.assertGreater(nearest_distance, 1050)

    def test_mid_duo_level_ten_startup_anchor_counts_prefixed_target_pressure(self) -> None:
        args = SimpleNamespace(ground_z_offset=0)
        route = growth.route_point(
            10,
            10000,
            10000,
            4800,
            "envy drakeling",
            "",
            "West Skona",
            source="hunting-index",
            mob_level=9,
            mob_count=10,
        )
        items = (
            {"name": "envy drakeling", "level": 9, "x": 10000, "y": 10000, "z": 4800, "healthPercent": 100},
            {
                "name": "노련한 envy drakeling",
                "level": 10,
                "x": 11400,
                "y": 10000,
                "z": 4800,
                "healthPercent": 100,
            },
        )
        with mock.patch.object(growth, "sample_route_z", return_value=4800):
            checked = growth.growth_route_preflight_startup_safe_anchor_route(
                args,
                route,
                items,
                realm=growth.REALMS["mid"],
                current_level=10,
                party_size=2,
                safety_radius=350,
            )

        self.assertIsNotNone(checked)
        assert checked is not None
        self.assertTrue(checked.startup_anchor)
        self.assertNotEqual((checked.x, checked.y), (11400, 10000))

    def test_hib_duo_level_ten_preflight_rejects_nearby_avoid_blocked_water_beetles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "hib,2,10,7,7,7,water beetle,7,14,348885,504608,4686,14,0,0,0,Mag Mell,900,900\n"
                "hib,2,10,7,7,7,water beetle,7,11,347590,571072,4826,11,0,0,0,Ardagh,1800,800\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_min_available_targets=0,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=10,
                growth_target_plan_override=(7, 8, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                dry_run=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                ground_z_offset=0,
                run_dir=temp_dir,
                case_name="hib-p2",
            )

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                x = int((query.get("x") or ["0"])[0])
                nearby_names = (query.get("nearbyAvoidName") or [""])[0]
                nearby_radius = int((query.get("nearbyRadius") or ["0"])[0])
                if name != "water beetle":
                    return []
                self.assertIn("lunantishee", nearby_names)
                self.assertEqual(nearby_radius, 1800)
                if x == 348885:
                    return [
                        {"name": "water beetle", "level": 8, "x": 347393, "y": 503648, "z": 4709, "nearbyAvoidCount": 1},
                        {"name": "water beetle", "level": 8, "x": 348391, "y": 504380, "z": 4598, "nearbyAvoidCount": 1},
                    ]
                if x == 347590:
                    return [
                        {"name": "water beetle", "level": 7, "x": 345299, "y": 567947, "z": 4797, "nearbyAvoidCount": 0},
                        {"name": "water beetle", "level": 7, "x": 345620, "y": 567920, "z": 4797, "nearbyAvoidCount": 0},
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                route = growth.select_growth_route_point(args, growth.REALMS["hib"], 8, 2)

            log_text = (Path(temp_dir) / "route-preflight.jsonl").read_text(encoding="utf-8")

        self.assertEqual(route.prefer, "water beetle")
        self.assertIn((route.x, route.y, route.z), {(345299, 567947, 4797), (345620, 567920, 4797)})
        self.assertIn("live_target_nearby_avoid_pressure:water beetle", log_text)

    def test_hib_duo_level_ten_carry_command_keeps_safe_route_target_tokens(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=300,
            safe_exit_max_seconds=90,
            safe_exit_recent_damage_grace=12,
            ramp_up=5,
            login_retries=12,
            login_retry_delay=5.0,
            api_port=5000,
            max_target_distance=2200.0,
            target_home_max_distance=1400.0,
            combat_home_leash_distance=1200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            startup_delay=4.0,
            growth_fast_travel="route-home",
            growth_allow_lower_xp_gear_farm=True,
            growth_allow_lower_xp_target_plan=False,
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_route_level_override=8,
            growth_route_level_is_carry_target=True,
            growth_target_level_override=8,
            growth_target_plan_override=(7, 8, 1),
            case_name="hib-p2",
            growth_party_carry_level_offset=12,
            current_party_size=2,
            growth_equip_party_carry_gear=False,
            growth_party_carry_count=-1,
            growth_failure_target_memory=False,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["hib"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=1,
                party_size=2,
                current_level=10,
                path_graph=Path("graph.json"),
            )

        self.assertEqual(command[command.index("--require-target-name") + 1], "water beetle")
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "water beetle")
        self.assertEqual(command[command.index("--min-target-level") + 1], "7")
        self.assertEqual(command[command.index("--max-target-level") + 1], "9")
        self.assertNotEqual(
            command[command.index("--startup-route-home-after-services") + 1],
            command[command.index("--required-target-home") + 1],
        )
        self.assertEqual(command[command.index("--startup-route-home-after-services") + 1], "347118,502495,4728")
        self.assertTrue(command[command.index("--required-target-home") + 1].startswith("347282,504287,"))
        self.assertIn("blackthorn", command[command.index("--target-nearby-avoid-name") + 1])

    def test_alb_duo_level_ten_river_racer_failure_command_lands_safe_rotting_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-06T23:56:19Z,alb-p2,alb,2,1,10,death_pressure,avoid_target,river racer,7,encounter_death_message,4\n"
                "2026-07-06T23:56:19Z,alb-p2,alb,2,1,10,combat_no_kill;death_pressure,avoid_target,노련한 river racer,8,combat_csv,4\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                host="127.0.0.1",
                port=10300,
                segment_seconds=300,
                safe_exit_max_seconds=90,
                safe_exit_recent_damage_grace=12,
                ramp_up=5,
                login_retries=12,
                login_retry_delay=5.0,
                api_port=5000,
                max_target_distance=2200.0,
                target_home_max_distance=1400.0,
                combat_home_leash_distance=1200.0,
                target_timeout=65,
                combat_interval=1.5,
                target_pool=5,
                smooth_move_interval=0.2,
                movement_speed=240.0,
                path_last_mile_distance=1200.0,
                ground_z_offset=0,
                encounter_log_interval=3.0,
                nav_api_url="http://127.0.0.1:5000",
                live_api_url="",
                startup_delay=4.0,
                growth_fast_travel="route-home",
                growth_allow_lower_xp_gear_farm=True,
                growth_allow_lower_xp_target_plan=False,
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_route_level_override=8,
                growth_route_level_is_carry_target=True,
                growth_target_level_override=10,
                growth_target_plan_override=(7, 8, 1),
                case_name="alb-p2",
                growth_party_carry_level_offset=12,
                current_party_size=2,
                growth_equip_party_carry_gear=False,
                growth_party_carry_count=-1,
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=2,
            )
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()

            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=2,
                party_size=2,
                current_level=10,
                path_graph=Path("graph.json"),
            )

        startup_home = command[command.index("--startup-route-home-after-services") + 1]
        required_home = command[command.index("--required-target-home") + 1]
        start_x, start_y, start_z = (int(part) for part in startup_home.split(","))
        avoid_targets = command[command.index("--avoid-target-name") + 1].split(",")

        self.assertNotEqual(startup_home, required_home)
        self.assertTrue(required_home.startswith("527242,624780,"))
        self.assertEqual(command[command.index("--require-target-name") + 1], "rotting zombie")
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "rotting zombie")
        self.assertEqual(start_x, 527242)
        self.assertEqual(624780 - start_y, 1300)
        self.assertLessEqual(abs(start_z - 1965), 220)
        self.assertIn("river racer", avoid_targets)
        self.assertNotIn("rotting zombie", avoid_targets)

    def test_mid_duo_level_four_carry_uses_lower_bound_safe_worker_route(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=10,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )

        target = growth.growth_party_carry_target_level(4, 2)
        route = growth.select_growth_route_point(args, growth.REALMS["mid"], target, 2)

        self.assertEqual(target, 5)
        self.assertEqual(route.prefer, "wood-eater worker")
        self.assertNotIn("wood-eater", route.avoid.split(","))
        self.assertNotEqual(route.prefer, "black mauler juvenile")

    def test_mid_duo_level_five_carry_caps_route_to_level_six(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=46,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            growth_target_level_override=5,
            growth_target_plan_override=growth.growth_party_carry_target_plan_for_realm(5, 2, "mid"),
            case_name="duo-s150-mid-r001",
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            growth_party_carry_level_offset=12,
            current_party_size=2,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 6, 2)

        self.assertEqual(growth.target_levels(6, 2, "mid"), (4, 5, 1))
        self.assertEqual(route.prefer, "vein spider")
        self.assertEqual(route.mob_level, 5)
        self.assertEqual(route.teleport_destination, "Mularn")
        self.assertNotIn("vein spider", route.avoid.split(","))
        self.assertIn("black mauler juvenile", route.avoid.split(","))
        self.assertIn("wood-eater hunter", route.avoid.split(","))
        self.assertIn("wood-eater worker", route.avoid.split(","))
        self.assertNotIn(route.prefer, {"host of the wind", "ghost light"})

    def test_alb_duo_level_four_carry_uses_current_safe_route(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=12,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            case_name="duo-s150-alb-r001",
        )

        target = growth.growth_party_carry_target_level(4, 2)
        route = growth.select_growth_route_point(args, growth.REALMS["alb"], target, 2)

        self.assertEqual(target, 5)
        self.assertEqual(route.prefer, "faerie bell-wether")
        self.assertEqual(route.teleport_destination, "Cotswold Village")
        self.assertGreaterEqual(route.mob_level, growth.growth_party_carry_reward_floor(args, 4, 2, "alb"))

    def test_low_hib_mid_party_carry_uses_lower_bound_safe_routes(self) -> None:
        hib_duo_args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=10,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            growth_party_carry_count=-1,
            growth_party_carry_level_offset=12,
            growth_equip_party_carry_gear=False,
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
        )
        hib_party4_args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=13,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            growth_party_carry_count=-1,
            growth_party_carry_level_offset=12,
            growth_equip_party_carry_gear=False,
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
        )
        mid_party8_args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=16,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )

        hib_duo_route = growth.select_growth_route_point(hib_duo_args, growth.REALMS["hib"], 5, 2)
        hib_party4_route = growth.select_growth_route_point(hib_party4_args, growth.REALMS["hib"], 5, 4)
        mid_party8_route = growth.select_growth_route_point(mid_party8_args, growth.REALMS["mid"], 7, 8)

        self.assertEqual(hib_duo_route.prefer, "hill toad")
        self.assertNotEqual(hib_duo_route.prefer, "spraggon")
        self.assertNotEqual(hib_duo_route.prefer, "water beetle")
        self.assertNotEqual(hib_duo_route.prefer, "water beetle collector")
        self.assertGreaterEqual(hib_duo_route.mob_level, growth.growth_party_carry_reward_floor(hib_duo_args, 5, 2, "hib"))
        self.assertEqual(hib_duo_route.teleport_destination, "Shannon Estuary")
        self.assertIn("orchard nipper", hib_duo_route.avoid)
        self.assertEqual(hib_party4_route.prefer, "hill toad")
        self.assertNotEqual(hib_party4_route.prefer, "spraggon")
        self.assertNotEqual(hib_party4_route.prefer, "water beetle")
        self.assertNotEqual(hib_party4_route.prefer, "water beetle collector")
        self.assertGreaterEqual(hib_party4_route.mob_level, growth.growth_party_carry_reward_floor(hib_party4_args, 5, 4, "hib"))
        self.assertEqual(mid_party8_route.prefer, "lake serpent")
        self.assertNotIn(mid_party8_route.prefer, {"wood-eater", "wood-eater worker"})

    def test_hib_duo_carry_level_five_preflight_does_not_fallback_to_no_xp_crab(self) -> None:
        def fake_preflight_payload(url: str, _timeout: float):
            if (
                ("name=water+beetle+collector" in url or "name=water%20beetle%20collector" in url)
                and "x=348694" in url
                and "y=498242" in url
            ):
                return [
                    {"name": "water beetle collector", "level": 5, "x": 348442, "y": 497904, "z": 4598},
                    {"name": "water beetle collector", "level": 5, "x": 348537, "y": 498111, "z": 4598},
                    {"name": "water beetle collector", "level": 5, "x": 348623, "y": 498337, "z": 4598},
                ]
            if "name=water+beetle+collector" in url or "name=water%20beetle%20collector" in url:
                return [{"name": "water beetle collector", "level": 5, "x": 347960, "y": 535206, "z": 4673}]
            if "name=water+beetle" in url or "name=water%20beetle" in url:
                return [{"name": "water beetle", "level": 6, "x": 348350, "y": 534590, "z": 4598}]
            if "x=348002" in url and "y=535114" in url:
                return []
            if "name=hill%20toad" in url or "name=hill+toad" in url:
                return [{"name": "hill toad", "level": 6, "x": 309663, "y": 647096, "z": 5234}]
            if "x=309663" in url and "y=647096" in url:
                return []
            if "name=eirebug" in url:
                return [{"name": "eirebug", "level": 5, "x": 329667, "y": 470837, "z": 5616}]
            if ("name=spraggon" in url or "name=feccan" in url) and (
                "x=331797" in url or "x=329667" in url
            ):
                return [{"name": "spraggon", "level": 5, "x": 331797, "y": 467208, "z": 5247}]
            return []

        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=45,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            growth_party_carry_level_offset=12,
            growth_party_carry_count=-1,
            growth_route_preflight=True,
            growth_route_preflight_anchor=True,
            growth_route_preflight_timeout=1.5,
            growth_route_preflight_radius=0,
            growth_route_preflight_hazard_radius=2500,
            growth_route_preflight_hazard_limit=3,
            growth_route_preflight_hazard_token_limit=12,
            growth_route_preflight_limit=3,
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            nav_api_url="http://127.0.0.1:5000",
            run_dir="",
        )

        with (
            mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight_payload),
            mock.patch.object(growth, "sample_route_z", return_value=4598),
        ):
            route = growth.select_growth_route_point(args, growth.REALMS["hib"], 5, 2)

        self.assertNotEqual(route.prefer, "small freshwater crab")
        self.assertEqual(route.prefer, "water beetle collector")
        self.assertEqual(route.teleport_destination, "Mag Mell")
        self.assertGreaterEqual(route.mob_level, growth.growth_party_carry_reward_floor(args, 5, 2, "hib"))

    def test_hib_duo_carry_level_six_preflight_miss_fails_fast_not_static_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "hib,2,6,5,6,6,hill toad,6,37,309663,647096,5234,37,0,0,0,Shannon Estuary,1200,3939\n"
                "hib,2,6,5,6,6,water beetle,6,19,350110,532178,4719,19,0,0,0,Tir na mBeo,900,1723\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=55,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=6,
                growth_target_plan_override=(6, 6, 0),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                run_dir=temp_dir,
                case_name="duo-s150-hib-r001",
            )

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", return_value=[]):
                with self.assertRaisesRegex(RuntimeError, "refusing static route"):
                    growth.select_growth_route_point(args, growth.REALMS["hib"], 6, 2)

    def test_hib_duo_carry_level_six_can_use_safe_water_beetle_despite_static_avoid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "hib,2,6,5,6,6,hill toad,6,37,309663,647096,5234,37,0,0,0,Shannon Estuary,1200,3939\n"
                "hib,2,6,5,6,6,water beetle,6,19,350110,532178,4719,19,0,0,0,Tir na mBeo,900,1723\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=56,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=True,
                growth_route_preflight=True,
                growth_route_preflight_anchor=True,
                growth_route_preflight_timeout=0.1,
                growth_route_preflight_radius=6500,
                growth_route_preflight_limit=3,
                growth_route_preflight_hazard_radius=2500,
                growth_route_preflight_hazard_limit=3,
                growth_route_preflight_hazard_token_limit=12,
                growth_target_level_override=6,
                growth_target_plan_override=(6, 6, 0),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_party_carry_level_offset=12,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                nav_api_url="http://dummy-api:5000",
                host="127.0.0.1",
                api_port=5000,
                max_target_distance=6500.0,
                run_dir=temp_dir,
                case_name="duo-s150-hib-r001",
            )

            def fake_preflight(url: str, _timeout: float) -> object:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                name = (query.get("name") or [""])[0]
                x = int((query.get("x") or ["0"])[0])
                if name == "hill toad" and x < 330000:
                    return [{"name": "hill toad", "level": 6, "x": 309663, "y": 647096, "z": 5234}]
                if name == "spraggon" and x < 330000:
                    return [{"name": "spraggon", "level": 7, "x": 309800, "y": 647100, "z": 5234}]
                if name == "water beetle":
                    return [
                        {"name": "water beetle", "level": 6, "x": 350110, "y": 532178, "z": 4719},
                        {"name": "water beetle", "level": 6, "x": 350210, "y": 532278, "z": 4719},
                    ]
                return []

            with mock.patch.object(growth, "fetch_growth_route_preflight_payload", side_effect=fake_preflight):
                route = growth.select_growth_route_point(args, growth.REALMS["hib"], 6, 2)

        self.assertEqual(route.prefer, "water beetle")
        self.assertEqual(route.mob_level, 6)
        self.assertEqual(route.source, "hunting-index")

    def test_alb_solo_level_six_hunting_index_routes_to_level_four_targets(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=3,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["alb"], 6, 1)

        self.assertEqual(growth.target_levels(6, 1, "alb"), (4, 4, 0))
        self.assertEqual(route.mob_level, 4)
        self.assertEqual(route.prefer, "gray wolf")
        self.assertNotEqual(route.prefer, "river spriteling")

    def test_alb_solo_level_seven_hunting_index_uses_level_five_to_six_candidates(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=3,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["alb"], 7, 1)

        self.assertEqual(growth.target_levels(7, 1, "alb"), (5, 5, 0))
        self.assertEqual(growth.minimum_growth_effective_target_level(7, 1, "alb"), 5)
        self.assertEqual(route.level, 7)
        self.assertEqual(route.prefer, "rot worm")
        self.assertEqual(route.mob_level, 5)
        self.assertEqual(route.mob_count, 28)
        self.assertEqual(route.teleport_destination, "Avalon Marsh")
        self.assertNotEqual(route.prefer, "worker ant")

    def test_alb_solo_level_seven_lower_xp_route_uses_target_plan_level(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=14,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            growth_target_plan_override=None,
        )

        with mock.patch.object(
            growth,
            "growth_failed_target_memory_avoid_targets",
            return_value="faerie bell-wether,zombie boar,emerald snake",
        ):
            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 7, 1)

        self.assertEqual(growth.target_levels(7, 1, "alb"), (5, 5, 0))
        self.assertEqual(route.prefer, "rot worm")
        self.assertEqual(route.mob_level, 5)
        self.assertEqual(route.teleport_destination, "Avalon Marsh")

    def test_alb_solo_level_seven_static_route_replaces_failed_rot_worm_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
        )

        with mock.patch.object(
            growth,
            "growth_failed_target_memory_avoid_targets",
            return_value="rot worm,노련한 rot worm",
        ):
            route = growth.low_alb_solo_level_seven_route(args, 7, 1)

        self.assertEqual(route.prefer, "emerald snake")
        self.assertEqual(route.mob_level, 5)
        self.assertEqual(route.teleport_destination, "Campacorentin Station")
        self.assertEqual((route.x, route.y, route.z), (491304, 592010, 1793))
        self.assertEqual(route.source, "hunting-index")
        self.assertIn("rot worm", route.avoid.split(","))
        self.assertIn("faerie bell-wether", route.avoid.split(","))

    def test_alb_solo_level_seven_repeated_no_engagement_uses_emerald_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-05T00:00:00Z,alb-p1,alb,1,15,7,no_engagement,downgrade_target_plan,,,timeline,18\n"
                "2026-07-05T00:05:00Z,alb-p1,alb,1,16,7,no_engagement,downgrade_target_plan,,,timeline,19\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index="",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_level_is_carry_target=False,
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=18,
            )

            route = growth.low_alb_solo_level_seven_route(args, 7, 1)

        self.assertEqual(route.prefer, "emerald snake")
        self.assertEqual((route.x, route.y, route.z), (491304, 592010, 1793))
        self.assertIn("rot worm", route.avoid.split(","))

    def test_alb_solo_level_seven_failed_prefixed_emerald_uses_dragon_ant_worker_fallback(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
        )

        with mock.patch.object(
            growth,
            "growth_failed_target_memory_avoid_targets",
            return_value="emerald snake,노련한 emerald snake,rot worm",
        ):
            route = growth.low_alb_solo_level_seven_route(args, 7, 1)

        self.assertEqual(route.prefer, "dragon ant worker")
        self.assertEqual(route.mob_level, 5)
        self.assertEqual(route.teleport_destination, "Castle Sauvage")
        self.assertEqual((route.x, route.y, route.z), (595117, 506793, 2562))
        self.assertIn("dragon ant soldier", route.avoid.split(","))
        self.assertIn("emerald snake", route.avoid.split(","))
        self.assertIn("rot worm", route.avoid.split(","))

    def test_alb_solo_level_seven_failed_rot_worm_command_targets_live_emerald_snake(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=300,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            growth_hunting_index="",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
            growth_failure_target_memory=True,
        )

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            growth,
            "growth_failed_target_memory_avoid_targets",
            return_value="rot worm,노련한 rot worm",
        ):
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=15,
                party_size=1,
                current_level=7,
                path_graph=Path("graph.json"),
            )
            payload = json.loads((case_dir / "live-control.json").read_text(encoding="utf-8"))

        self.assertNotIn("--startup-teleport-destination", command)
        self.assertEqual(command[command.index("--startup-route-home-after-services") + 1], "493679,591770,1822")
        self.assertEqual(command[command.index("--required-target-home") + 1], "491304,592010,1793")
        self.assertEqual(command[command.index("--require-target-name") + 1], "emerald snake")
        self.assertNotIn("--require-target-name-exact", command)
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "emerald snake")
        self.assertGreaterEqual(float(command[command.index("--max-target-distance") + 1]), 6500.0)
        self.assertGreaterEqual(float(command[command.index("--target-home-max-distance") + 1]), 6500.0)
        self.assertGreaterEqual(float(command[command.index("--required-target-home-hunt-distance") + 1]), 6500.0)
        self.assertEqual(command[command.index("--min-target-level") + 1], "5")
        self.assertEqual(command[command.index("--max-target-level") + 1], "5")
        self.assertEqual(payload["baseline_min_target_level"], 5)
        self.assertEqual(payload["baseline_max_target_level"], 5)

    def test_alb_solo_level_seven_emerald_route_stages_before_required_home(self) -> None:
        route = growth.route_point(
            7,
            491304,
            592010,
            1793,
            "emerald snake",
            "rot worm,brownie nomad",
            "Campacorentin Station",
            source="hunting-index",
            mob_level=5,
            mob_count=20,
        )

        staged = growth.startup_route_home_after_services_point(
            growth.REALMS["alb"],
            route,
            current_level=7,
            party_size=1,
        )

        self.assertEqual((staged.x, staged.y, staged.z), (493679, 591770, 1819))
        self.assertEqual((route.x, route.y, route.z), (491304, 592010, 1793))
        self.assertEqual(
            growth.route_home_string_for_point(growth.REALMS["alb"], route, ground_z_offset=0),
            "491304,592010,1793",
        )

    def test_alb_solo_level_seven_selected_route_prefer_is_removed_from_failure_avoid(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=300,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            growth_hunting_index="",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
            growth_failure_target_memory=True,
        )

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            growth,
            "growth_failed_target_memory_avoid_targets",
            return_value="emerald snake,large skeleton,rot worm",
        ):
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=15,
                party_size=1,
                current_level=7,
                path_graph=Path("graph.json"),
            )

        self.assertEqual(command[command.index("--prefer-target-name") + 1], "dragon ant worker")
        self.assertNotIn("dragon ant worker", command[command.index("--avoid-target-name") + 1].split(","))
        self.assertIn("emerald snake", command[command.index("--avoid-target-name") + 1].split(","))
        self.assertIn("dragon ant soldier", command[command.index("--avoid-target-name") + 1].split(","))
        self.assertIn("large skeleton", command[command.index("--avoid-target-name") + 1].split(","))

    def test_alb_duo_level_six_uses_rot_worm_after_faerie_deaths(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=10,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["alb"], 6, 2)

        self.assertEqual(route.prefer, "rot worm")
        self.assertEqual(route.mob_level, 5)
        self.assertEqual(route.teleport_destination, "Avalon Marsh")
        self.assertIn(
            "faerie bell-wether",
            growth.growth_avoid_targets_for_current_context(route, "alb", 6, 2).split(","),
        )

    def test_hib_solo_level_four_routes_to_safe_level_two_hunting_index_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=7,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
        )

        route = growth.select_growth_route_point(args, growth.REALMS["hib"], 4, 1)

        self.assertEqual(growth.target_levels(4, 1, "hib"), (2, 2, 0))
        self.assertEqual(route.prefer, "lough wolf cadger")
        self.assertEqual(route.mob_level, 2)
        self.assertEqual(route.teleport_destination, "Mag Mell")

    def test_hib_solo_level_four_command_does_not_self_block_failed_prefer_target(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=150,
            safe_exit_max_seconds=25,
            safe_exit_recent_damage_grace=5,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=6200.0,
            combat_home_leash_distance=6200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            party_external_member_names="",
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=7,
            growth_fast_travel="route-home",
            growth_route_preflight=False,
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            dry_run=False,
            run_dir="",
            case_name="solo-s150-r2-hib-r002",
        )
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            growth,
            "growth_failed_target_memory_avoid_targets",
            return_value="small freshwater crab,lough wolf",
        ):
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["hib"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=6,
                party_size=1,
                current_level=4,
                path_graph=Path("graph.json"),
            )

        self.assertIn("--prefer-target-name", command)
        preferred_target = command[command.index("--prefer-target-name") + 1]
        self.assertEqual(preferred_target, "minor changeling")
        avoid_targets = command[command.index("--avoid-target-name") + 1]
        self.assertIn("small freshwater crab", avoid_targets.split(","))
        self.assertNotIn("lough wolf cadger", avoid_targets.split(","))
        self.assertNotIn(preferred_target, avoid_targets.split(","))

    def test_failed_target_memory_overrides_required_and_preferred_route_target(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=150,
            safe_exit_max_seconds=25,
            safe_exit_recent_damage_grace=5,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=6200.0,
            combat_home_leash_distance=6200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            party_external_member_names="",
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_preflight=False,
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            dry_run=False,
            run_dir="",
            case_name="solo-s150-r2-alb-r002",
        )
        dangerous_route = growth.route_point(
            8,
            462144,
            633058,
            1739,
            "faerie bell-wether",
            "",
            "Avalon Marsh",
            source="hunting-index",
            mob_level=6,
            mob_count=12,
        )
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            growth,
            "select_growth_route_point",
            return_value=dangerous_route,
        ), mock.patch.object(
            growth,
            "growth_failed_target_memory_avoid_targets",
            return_value="faerie bell-wether",
        ):
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=16,
                party_size=1,
                current_level=8,
                path_graph=Path("graph.json"),
            )

        self.assertNotIn("--require-target-name", command)
        self.assertNotIn("--prefer-target-name", command)
        avoid_targets = command[command.index("--avoid-target-name") + 1]
        self.assertIn("faerie bell-wether", avoid_targets.split(","))

    def test_live_anchor_route_prefer_survives_transient_failed_memory(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=150,
            safe_exit_max_seconds=25,
            safe_exit_recent_damage_grace=5,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=6500.0,
            target_home_max_distance=10000.0,
            combat_home_leash_distance=10000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            party_external_member_names="",
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_preflight=True,
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            dry_run=False,
            run_dir="",
            case_name="duo-s150-hib-r001",
        )
        live_route = growth.route_point(
            5,
            348164,
            498725,
            4598,
            "water beetle collector",
            "",
            "Mag Mell",
            source="hunting-index",
            mob_level=5,
            mob_count=18,
            live_anchor_z=True,
        )
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            growth,
            "select_growth_route_point",
            return_value=live_route,
        ), mock.patch.object(
            growth,
            "growth_route_blocked_by_failed_target_memory",
            return_value=False,
        ), mock.patch.object(
            growth,
            "growth_failed_target_memory_avoid_targets",
            return_value="water beetle collector",
        ):
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["hib"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=32,
                party_size=2,
                current_level=5,
                path_graph=Path("graph.json"),
            )

        self.assertIn("--prefer-target-name", command)
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "water beetle collector")
        self.assertIn("--avoid-target-name", command)
        avoid_targets = command[command.index("--avoid-target-name") + 1]
        self.assertNotIn("water beetle collector", avoid_targets.split(","))

    def test_failed_target_memory_replaces_blocked_static_route_before_launch(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=150,
            safe_exit_max_seconds=25,
            safe_exit_recent_damage_grace=5,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=6200.0,
            combat_home_leash_distance=6200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            party_external_member_names="",
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_preflight=False,
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            dry_run=False,
            run_dir="",
            case_name="duo-s150-mid-r001",
        )
        blocked_route = growth.route_point(
            7,
            783318,
            718641,
            4804,
            "wood-eater royal guard",
            "",
            "Mularn",
            source="hunting-index",
            mob_level=16,
            mob_count=3,
        )
        safe_route = growth.route_point(
            7,
            772957,
            725582,
            4754,
            "vein spider",
            "",
            "Mularn",
            source="hunting-index",
            mob_level=5,
            mob_count=25,
        )
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            growth,
            "select_growth_route_point",
            return_value=blocked_route,
        ), mock.patch.object(
            growth,
            "select_growth_hunting_index_point_for_target",
            return_value=safe_route,
        ), mock.patch.object(
            growth,
            "growth_failed_target_memory_avoid_targets",
            return_value="wood-eater royal guard",
        ):
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["mid"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=23,
                party_size=1,
                current_level=7,
                path_graph=Path("graph.json"),
            )

        self.assertIn("--prefer-target-name", command)
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "vein spider")
        route_home = command[command.index("--startup-route-home-after-services") + 1]
        self.assertIn("772957", route_home)

    def test_target_memory_matching_handles_veteran_and_corrupt_prefixes(self) -> None:
        self.assertTrue(
            growth.target_name_matches_any(
                "faerie bell-wether",
                growth.preferred_target_tokens("노련한 faerie bell-wether"),
            )
        )
        self.assertTrue(
            growth.target_name_matches_any(
                "노련한 faerie bell-wether",
                growth.preferred_target_tokens("faerie bell-wether"),
            )
        )
        self.assertTrue(
            growth.target_name_matches_any(
                "����� wood-eater king",
                growth.preferred_target_tokens("wood-eater"),
            )
        )

    def test_failed_target_memory_does_not_block_route_with_failed_hazard_only_in_avoid_list(self) -> None:
        route = growth.route_point(
            7,
            573000,
            500000,
            2600,
            "emerald snake",
            "faerie bell-wether,bandit",
            "Cotswold Village",
            source="hunting-index",
            mob_level=5,
        )
        with mock.patch.object(
            growth,
            "growth_failed_target_memory_avoid_targets",
            return_value="노련한 faerie bell-wether",
        ):
            blocked = growth.growth_route_blocked_by_failed_target_memory(
                SimpleNamespace(),
                route,
                "alb",
                7,
                1,
            )

        self.assertFalse(blocked)

    def test_alb_party4_level_six_and_seven_use_xp_eligible_non_tree_spirit_camps(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=13,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
        )

        level_six = growth.select_growth_route_point(args, growth.REALMS["alb"], 6, 4)
        level_seven = growth.select_growth_route_point(args, growth.REALMS["alb"], 7, 4)

        self.assertEqual(growth.target_levels(7, 4, "alb"), (5, 6, 1))
        self.assertEqual(level_six.prefer, "emerald snake")
        self.assertEqual(level_seven.prefer, "emerald snake")
        self.assertEqual(level_six.mob_level, 5)
        self.assertEqual(level_seven.mob_level, 5)
        self.assertGreaterEqual(level_six.mob_count, 16)
        self.assertNotEqual(level_six.prefer, "tree spirit")
        self.assertNotEqual(level_seven.prefer, "tree spirit")
        self.assertIn("dappled lynx cub", growth.growth_hunting_index_avoid_targets("alb", 6, 4).split(","))

    def test_hib_low_non_carry_parties_use_safer_growth_routes(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=16,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
            growth_party_carry_count=0,
        )

        duo_level_three = growth.select_growth_route_point(args, growth.REALMS["hib"], 3, 2)
        party4_level_four = growth.select_growth_route_point(args, growth.REALMS["hib"], 4, 4)

        self.assertEqual(duo_level_three.prefer, "feccan")
        self.assertNotIn("villainous youth", duo_level_three.prefer)
        self.assertEqual(duo_level_three.teleport_destination, "Shannon Estuary")
        self.assertEqual(party4_level_four.prefer, "mudman")
        self.assertEqual(party4_level_four.mob_level, 4)
        self.assertEqual(party4_level_four.teleport_destination, "Connla")
        self.assertNotIn("mudman", party4_level_four.avoid.split(","))

    def test_low_alb_party8_carry_routes_avoid_tree_spirit_aggro_camps(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )
        live_scan_empty_args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=17,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            case_name="party8-s240-alb-r001",
        )

        level_one_target = growth.growth_party_carry_target_level(1, 8)
        level_three_target = growth.growth_party_carry_target_level(3, 8)
        level_four_target = growth.growth_party_carry_target_level(4, 8)
        level_one_route = growth.select_growth_route_point(args, growth.REALMS["alb"], level_one_target, 8)
        level_three_route = growth.select_growth_route_point(args, growth.REALMS["alb"], level_three_target, 8)
        level_four_route = growth.select_growth_route_point(
            live_scan_empty_args,
            growth.REALMS["alb"],
            level_four_target,
            8,
        )

        self.assertEqual(level_one_target, 6)
        self.assertEqual(level_one_route.prefer, "ant drone")
        self.assertNotEqual(level_one_route.prefer, "tree spirit")
        self.assertEqual(level_three_target, 6)
        self.assertEqual(level_three_route.prefer, "ant drone")
        self.assertNotEqual(level_three_route.prefer, "tree spirit")
        self.assertEqual(level_four_target, 7)
        self.assertEqual(level_four_route.prefer, "ant drone")
        self.assertNotEqual(level_four_route.prefer, "tree spirit")

        level_six_target = growth.growth_party_carry_target_level_for_realm(6, 8, "alb")
        level_six_route = growth.select_growth_route_point(
            live_scan_empty_args,
            growth.REALMS["alb"],
            level_six_target,
            8,
        )
        self.assertEqual(level_six_target, 9)
        self.assertEqual(level_six_route.prefer, "wild boar")
        self.assertGreaterEqual(level_six_route.mob_level, level_six_target)
        self.assertNotEqual(level_six_route.prefer, "tree spirit")

    def test_growth_survival_route_override_keeps_current_level_routes(self) -> None:
        self.assertIsNone(growth.growth_survival_route_override("alb", 8, 1))
        self.assertIsNone(growth.growth_survival_route_override("mid", 6, 1))
        self.assertEqual(growth.growth_survival_route_override("mid", 4, 2), (5, 5))

    def test_large_party_effective_level_keeps_observed_level_when_members_lag(self) -> None:
        snapshots = {
            f"acct{index}": growth.CharacterSnapshot(
                account=f"acct{index}",
                name=f"Char{index}",
                character_id=f"id-{index}",
                level=level,
                experience=0,
                realm=1,
                class_id=1,
                specs="",
                region=1,
                x=0,
                y=0,
                z=0,
                deaths=0,
                money_copper=0,
                inventory_rows=0,
                inventory_items=0,
            )
            for index, level in enumerate([6, 5, 4, 4, 2, 1, 3, 2], start=1)
        }

        self.assertEqual(growth.growth_effective_party_level(snapshots, 6, 8), 6)
        self.assertEqual(growth.growth_effective_party_level(snapshots, 6, 2), 6)

        lopsided = {
            account: dataclasses.replace(snapshot, level=level)
            for (account, snapshot), level in zip(snapshots.items(), [9, 8, 8, 8, 8, 7, 1, 1])
        }
        self.assertEqual(growth.growth_effective_party_level(lopsided, 9, 8), 9)
        one_stuck = {
            account: dataclasses.replace(snapshot, level=level)
            for (account, snapshot), level in zip(snapshots.items(), [7, 7, 6, 6, 5, 4, 3, 1])
        }
        self.assertEqual(growth.growth_effective_party_level(one_stuck, 7, 8), 7)

        caught_up = {
            account: dataclasses.replace(snapshot, level=5)
            for account, snapshot in snapshots.items()
        }
        self.assertEqual(growth.growth_effective_party_level(caught_up, 5, 8), 5)
        self.assertEqual(growth.growth_party_combat_level(snapshots, 2, 8), 2)
        self.assertEqual(growth.growth_party_combat_level({}, 2, 8), 2)
        self.assertEqual(growth.growth_party_combat_level(snapshots, 2, 1), 2)
        self.assertIsNone(growth.growth_survival_route_override("hib", 8, 1))
        self.assertIsNone(growth.growth_survival_route_override("mid", 6, 2))
        self.assertEqual(growth.target_levels(7, 4, "mid"), (7, 7, 0))
        self.assertEqual(growth.minimum_growth_effective_target_level(7, 4, "mid"), 7)

    def test_hib_solo_level_five_requires_selected_safe_route_target(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["hib"], 5, 1)

        self.assertEqual(route.prefer, "spraggon")
        self.assertEqual(growth.strict_route_target_name(route, 5, party_size=1, realm_key="hib"), "spraggon")

    def test_party_carry_role_excluded_from_observed_growth_level(self) -> None:
        account_names = ["carry", "tracked1", "tracked2"]
        roles = growth.growth_party_account_roles(account_names, party_size=3)
        snapshots = {
            "carry": growth.CharacterSnapshot("carry", "Carry", "id1", 14, 90000, 1, 2, "", 1, 0, 0, 0, 0, 0, 0, 0),
            "tracked1": growth.CharacterSnapshot("tracked1", "Tracked1", "id2", 7, 30000, 1, 2, "", 1, 0, 0, 0, 0, 0, 0, 0),
            "tracked2": growth.CharacterSnapshot("tracked2", "Tracked2", "id3", 6, 25000, 1, 2, "", 1, 0, 0, 0, 0, 0, 0, 0),
        }

        observed = growth.observed_growth_level(snapshots, account_names, roles, checkpoint_level=None)

        self.assertEqual(roles["carry"], "carry")
        self.assertEqual(roles["tracked1"], "carry")
        self.assertEqual(roles["tracked2"], "tracked")
        self.assertEqual(observed, 6)

    def test_party8_observed_growth_level_uses_highest_tracked_member(self) -> None:
        account_names = [f"member{index}" for index in range(1, 9)]
        roles = growth.growth_party_account_roles(account_names, party_size=8, carry_count_override=0)
        levels = [4, 3, 4, 4, 4, 3, 1, 3]
        snapshots = {
            account: growth.CharacterSnapshot(account, account.title(), f"id{index}", level, 0, 1, 2, "", 1, 0, 0, 0, 0, 0, 0, 0)
            for index, (account, level) in enumerate(zip(account_names, levels), start=1)
        }

        party8_observed = growth.observed_growth_level(
            snapshots,
            account_names,
            roles,
            checkpoint_level=None,
            party_size=8,
        )
        party4_observed = growth.observed_growth_level(
            snapshots,
            account_names[:4],
            {account: roles[account] for account in account_names[:4]},
            checkpoint_level=None,
            party_size=4,
        )

        self.assertEqual(party8_observed, 4)
        self.assertEqual(party4_observed, 3)

    def test_party_carry_count_zero_tracks_every_party_member(self) -> None:
        account_names = ["member1", "member2", "member3"]
        roles = growth.growth_party_account_roles(account_names, party_size=3, carry_count_override=0)

        self.assertEqual(roles, {"member1": "tracked", "member2": "tracked", "member3": "tracked"})
        self.assertFalse(
            growth.growth_party_uses_carry_tuning(
                SimpleNamespace(growth_party_carry_count=0),
                level=6,
                party_size=3,
            )
        )

    def test_growth_target_plan_rejects_no_xp_low_level_routes(self) -> None:
        with self.assertRaisesRegex(ValueError, "route_level=1"):
            growth.validate_growth_target_plan(
                realm_key="mid",
                current_level=6,
                party_size=1,
                route_level=1,
                min_target=1,
                ideal_target=1,
                max_delta=0,
            )

        with self.assertRaisesRegex(ValueError, "route_level=4"):
            growth.validate_growth_target_plan(
                realm_key="alb",
                current_level=8,
                party_size=1,
                route_level=4,
                min_target=4,
                ideal_target=4,
                max_delta=0,
            )

        growth.validate_growth_target_plan(
            realm_key="alb",
            current_level=8,
            party_size=1,
            route_level=8,
            min_target=6,
            ideal_target=6,
            max_delta=0,
        )

    def test_level_one_solo_uses_lower_growth_survival_thresholds(self) -> None:
        self.assertEqual(growth.growth_low_health_rest_percent(1, 1), 30)
        self.assertEqual(growth.growth_low_health_rest_resume_percent(1, 1), 75)
        self.assertEqual(growth.growth_required_target_recover_before_hunt_endurance_percent(1, 1), 0)
        self.assertEqual(growth.growth_flee_health_percent(1, 1), 30)
        self.assertEqual(growth.growth_flee_critical_health_percent(1, 1), 20)
        self.assertEqual(growth.growth_flee_melee_counterattack_health_floor(1, 1), 20)
        self.assertEqual(growth.growth_required_target_tank_commit_health_percent(1, 1), 10)

        self.assertEqual(growth.growth_low_health_rest_percent(1, 2), 30)
        self.assertEqual(growth.growth_low_health_rest_resume_percent(1, 2), 75)
        self.assertEqual(growth.growth_required_target_recover_before_home_health_percent(1, 2), 30)
        self.assertEqual(growth.growth_flee_health_percent(1, 2), 30)
        self.assertEqual(growth.growth_flee_pressure_health_percent(1, 2), 30)
        self.assertEqual(growth.growth_flee_critical_health_percent(1, 2), 20)
        self.assertEqual(growth.growth_flee_melee_counterattack_health_floor(1, 2), 20)
        self.assertEqual(growth.growth_flee_health_percent(2, 1), 55)

    def test_level_four_plus_solo_uses_growth_survival_thresholds(self) -> None:
        self.assertEqual(growth.growth_low_health_rest_percent(4, 1, "hib"), 30)
        self.assertEqual(growth.growth_low_health_rest_resume_percent(4, 1, "hib"), 75)
        self.assertEqual(growth.growth_flee_health_percent(4, 1, "hib"), 30)
        self.assertEqual(growth.growth_flee_pressure_health_percent(4, 1, "hib"), 30)
        self.assertEqual(growth.growth_flee_critical_health_percent(4, 1, "hib"), 20)
        self.assertEqual(growth.growth_flee_melee_counterattack_health_floor(4, 1, "hib"), 20)
        self.assertEqual(growth.growth_required_target_tank_commit_health_percent(4, 1, "hib"), 10)

        self.assertEqual(growth.growth_low_health_rest_percent(6, 1), 60)
        self.assertEqual(growth.growth_low_health_rest_resume_percent(6, 1), 70)
        self.assertEqual(growth.growth_flee_health_percent(6, 1), 55)
        self.assertEqual(growth.growth_flee_pressure_health_percent(6, 1), 85)
        self.assertEqual(growth.growth_flee_critical_health_percent(6, 1), 45)
        self.assertEqual(growth.growth_flee_melee_counterattack_health_floor(6, 1), 55)
        self.assertEqual(growth.growth_required_target_tank_commit_health_percent(6, 1), 55)
        self.assertEqual(growth.growth_required_target_recover_before_hunt_endurance_percent(6, 1), 40)
        self.assertEqual(growth.growth_required_target_recover_before_home_health_percent(6, 4), 30)
        self.assertEqual(growth.growth_low_health_rest_percent(8, 1), 60)
        self.assertEqual(growth.growth_low_health_rest_resume_percent(8, 1), 70)
        self.assertEqual(growth.growth_flee_health_percent(8, 1), 55)
        self.assertEqual(growth.growth_flee_pressure_health_percent(8, 1), 85)
        self.assertEqual(growth.growth_flee_critical_health_percent(8, 1), 45)
        self.assertEqual(growth.growth_flee_melee_counterattack_health_floor(8, 1), 55)
        self.assertEqual(growth.growth_required_target_tank_commit_health_percent(8, 1), 55)
        self.assertEqual(growth.growth_required_target_recover_before_hunt_endurance_percent(8, 1), 40)
        self.assertEqual(growth.growth_required_target_recover_before_hunt_endurance_percent(10, 1), 40)
        self.assertEqual(growth.growth_required_target_recover_before_home_health_percent(10, 1, "alb"), 95)
        self.assertEqual(growth.growth_flee_critical_health_percent(10, 1, "alb"), 45)

        self.assertEqual(growth.growth_low_health_rest_percent(5, 1, "hib"), 60)
        self.assertEqual(growth.growth_low_health_rest_resume_percent(5, 1, "hib"), 70)
        self.assertEqual(growth.growth_low_health_rest_percent(6, 1, "hib"), 60)
        self.assertEqual(growth.growth_flee_health_percent(5, 1, "hib"), 55)
        self.assertEqual(growth.growth_flee_pressure_health_percent(5, 1, "hib"), 85)
        self.assertEqual(growth.growth_low_health_rest_resume_percent(6, 1, "hib"), 70)
        self.assertEqual(growth.growth_flee_health_percent(6, 1, "hib"), 55)
        self.assertEqual(growth.growth_flee_pressure_health_percent(6, 1, "hib"), 85)
        self.assertEqual(growth.growth_flee_critical_health_percent(6, 1, "hib"), 45)
        self.assertEqual(growth.growth_flee_melee_counterattack_health_floor(6, 1, "hib"), 55)
        self.assertEqual(growth.growth_required_target_tank_commit_health_percent(6, 1, "hib"), 55)

        self.assertEqual(growth.growth_flee_health_percent(6, 2, "hib"), 30)

    def test_paladin_growth_promotion_equips_only_weaker_right_hand_weapon(self) -> None:
        self.assertEqual(growth.promotion_right_hand_weapon_template_id(1, "Slash|39;Chants|48"), "slash_sword_item")
        self.assertEqual(growth.promotion_right_hand_weapon_template_id(22, "Hammer|50;Parry|28"), "bronze_battle_hammer2")
        self.assertEqual(growth.promotion_right_hand_weapon_template_id(44, "Blades|50;Shields|42"), "bastard_sword")
        self.assertEqual(growth.promotion_right_hand_weapon_template_id(6, "Rejuvenation|40"), "")

        sql = growth.promotion_right_hand_weapon_sql("growthalb001", 1, "slash_sword_item")

        self.assertIn("inv.SlotPosition = 10", sql)
        self.assertIn("COALESCE(current_item.DPS_AF, 0) < gift.DPS_AF", sql)
        self.assertIn("ActiveWeaponSlot = 0", sql)

    def test_target_max_level_clamps_exact_solo_recovery_targets(self) -> None:
        self.assertEqual(growth.target_max_level(1, 0, 0), 0)
        self.assertEqual(growth.target_max_level(6, 5, 0), 5)
        self.assertEqual(growth.target_max_level(20, 21, 2), 22)
        self.assertEqual(growth.target_max_level(50, 47, 1), 48)
        self.assertEqual(growth.target_max_level(49, 50, 5), 50)

    def test_sub_five_growth_stays_on_starter_route_variant(self) -> None:
        route = growth.select_route_point(growth.REALMS["mid"], level=4, party_size=1)
        self.assertEqual((route.x, route.y, route.z), (767400, 745984, 4542))
        self.assertIn("young lynx", route.prefer)
        self.assertIn("thrall", route.avoid)

    def test_mid_level_four_duo_uses_plain_mularn_wood_eater_before_workers(self) -> None:
        route = growth.select_route_point(growth.REALMS["mid"], level=4, party_size=2)

        self.assertEqual(growth.target_levels(4, 2, "mid"), (3, 3, 0))
        self.assertEqual((route.x, route.y, route.z), (788300, 723100, 4672))
        self.assertEqual(route.teleport_destination, "Mularn")
        self.assertEqual(route.prefer, "wood-eater")
        self.assertIn("wood-eater worker", route.avoid)
        self.assertNotIn("wood-eater,", route.avoid)
        self.assertIn("hill person", route.avoid)

    def test_mid_level_four_larger_parties_use_mularn_worker_cluster(self) -> None:
        for party_size in (4, 8):
            route = growth.select_route_point(growth.REALMS["mid"], level=4, party_size=party_size)

            self.assertEqual((route.x, route.y, route.z), (786637, 723034, 4722))
            self.assertEqual(route.teleport_destination, "Mularn")
            self.assertEqual(route.prefer, "wood-eater worker,wood-eater")
            self.assertNotIn("wood-eater worker", route.avoid)

    def test_albion_level_two_three_solo_prefers_killable_black_wolf_pups(self) -> None:
        for level in (2, 3):
            route = growth.select_route_point(growth.REALMS["alb"], level=level, party_size=1)
            self.assertEqual(route.prefer, "black wolf pup")
            self.assertIn("small gray wolf", route.avoid)

    def test_albion_level_four_solo_uses_xp_eligible_level_two_targets(self) -> None:
        route = growth.select_route_point(growth.REALMS["alb"], level=4, party_size=1)

        self.assertEqual(route.prefer, "skeleton,bear cub,wild sow")
        self.assertIn("small gray wolf", route.avoid)
        self.assertIn("black wolf pup", route.avoid)

    def test_hib_level_four_solo_uses_preferred_target_fallback(self) -> None:
        route = growth.select_route_point(growth.REALMS["hib"], level=4, party_size=1)

        self.assertEqual(growth.target_levels(4, 1, "hib"), (2, 2, 0))
        self.assertEqual((route.x, route.y, route.z), (345935, 470831, 6032))
        self.assertEqual(route.teleport_destination, "Mag Mell")
        self.assertEqual(route.prefer, "skeletal pawn")
        self.assertNotIn("skeletal pawn", route.avoid)
        self.assertIn("mudman", route.avoid)
        self.assertIn("water beetle larva", route.avoid)
        self.assertEqual(
            growth.strict_route_target_name(route, 4, party_size=1, realm_key="hib"),
            "",
        )

    def test_hib_level_four_solo_growth_command_disables_avoid_fallback(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=2200,
            target_home_max_distance=6200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["hib"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=4,
                party_size=1,
                current_level=4,
                path_graph=Path("graph.json"),
            )

        self.assertNotIn("--allow-avoid-target-fallback", command)
        self.assertIn("--prefer-target-name", command)
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "skeletal pawn")
        self.assertEqual(command[command.index("--startup-teleport-destination") + 1], "Mag Mell")
        self.assertIn("--avoid-target-name", command)
        self.assertNotIn("skeletal pawn", command[command.index("--avoid-target-name") + 1])
        self.assertEqual(command[command.index("--min-target-level") + 1], "2")
        self.assertEqual(command[command.index("--max-target-level") + 1], "2")

    def test_hib_level_four_solo_hunting_index_uses_live_target_radius(self) -> None:
        args = SimpleNamespace(
            growth_fast_travel="route-home",
            growth_route_preflight=True,
            growth_route_preflight_radius=0,
            growth_route_preflight_low_solo_radius=2500,
            max_target_distance=1500.0,
        )
        route = growth.route_point(
            4,
            345177,
            491014,
            5259,
            "lough wolf cadger",
            "mudman,feccan",
            "",
            source="hunting-index",
            mob_level=2,
            mob_count=16,
        )

        self.assertGreaterEqual(
            growth.growth_route_preflight_radius(
                args,
                route,
                realm_key="hib",
                current_level=4,
                party_size=1,
            ),
            5000,
        )
        self.assertGreaterEqual(
            growth.growth_hunter_target_api_radius(args, 4, 1, "hib", route),
            5000.0,
        )
        self.assertGreaterEqual(
            growth.growth_combat_chase_max_distance(4, 1, args, "hib", route),
            5000.0,
        )

    def test_hib_level_four_solo_gets_longer_segment_hold_for_slow_xp_kill(self) -> None:
        args = SimpleNamespace(segment_seconds=150)

        self.assertEqual(growth.growth_segment_hold_seconds(args, 4, 1, "hib"), 300)
        self.assertEqual(growth.growth_segment_hold_seconds(args, 4, 2, "hib"), 300)
        self.assertEqual(growth.growth_segment_hold_seconds(args, 5, 1, "hib"), 150)

    def test_low_level_parties_get_longer_segment_hold_for_startup_and_assist(self) -> None:
        args = SimpleNamespace(segment_seconds=150)

        self.assertEqual(growth.growth_segment_hold_seconds(args, 2, 2, "alb"), 300)
        self.assertEqual(growth.growth_segment_hold_seconds(args, 4, 4, "mid"), 360)
        self.assertEqual(growth.growth_segment_hold_seconds(args, 5, 4, "mid"), 150)

    def test_watcher_low_solo_checkpoint_gets_longer_segment_hold(self) -> None:
        self.assertEqual(growth.growth_segment_hold_seconds(SimpleNamespace(segment_seconds=180, watch_movement=True), 6, 1, "alb"), 240)
        self.assertEqual(growth.growth_segment_hold_seconds(SimpleNamespace(segment_seconds=180, watch_movement=True), 10, 1, "hib"), 240)
        self.assertEqual(growth.growth_segment_hold_seconds(SimpleNamespace(segment_seconds=180, watch_movement=False), 6, 1, "alb"), 180)

    def test_albion_level_five_solo_uses_xp_eligible_small_gray_wolves(self) -> None:
        route = growth.select_route_point(growth.REALMS["alb"], level=5, party_size=1)

        self.assertEqual(growth.target_levels(5, 1, "alb"), (3, 3, 0))
        self.assertEqual(route.prefer, "small gray wolf")
        self.assertEqual((route.x, route.y, route.z), (534900, 478900, 2310))
        self.assertIn("skeleton", route.avoid)
        self.assertIn("weak skeleton", route.avoid)
        self.assertIn("shady pilferer", route.avoid)

    def test_albion_level_six_solo_uses_prydwen_small_bear_cluster(self) -> None:
        route = growth.select_route_point(growth.REALMS["alb"], level=6, party_size=1)

        self.assertEqual(growth.target_levels(6, 1, "alb"), (4, 4, 0))
        self.assertEqual(route.prefer, "small bear")
        self.assertEqual((route.x, route.y, route.z), (591020, 532686, 2342))
        self.assertEqual(route.teleport_destination, "Prydwen Keep")
        self.assertIn("goblin fisherman", route.avoid)
        self.assertEqual(growth.growth_hunter_target_max_ground_z_delta(6, 1, "alb"), 650)
        self.assertEqual(growth.growth_hunter_target_max_attack_z_delta(6, 1, "alb"), 650)
        self.assertEqual(growth.growth_hunter_target_max_attack_z_delta(6, 2, "alb"), 220)
        self.assertEqual(growth.growth_hunter_target_max_attack_z_delta(9, 1, "alb"), 360)
        self.assertEqual(growth.growth_hunter_target_max_attack_z_delta(9, 2, "alb"), 220)

    def test_hib_level_five_solo_uses_verified_mudman_xp_target(self) -> None:
        route = growth.select_route_point(growth.REALMS["hib"], level=5, party_size=1)

        self.assertEqual(growth.target_levels(5, 1, "hib"), (4, 4, 0))
        self.assertEqual(growth.growth_hunter_target_max_ground_z_delta(5, 1, "hib"), 500)
        self.assertEqual(growth.growth_hunter_target_max_ground_z_delta(5, 2, "hib"), 500)
        self.assertEqual(route.prefer, "mudman")
        self.assertIn("eirebug", route.avoid)
        self.assertIn("spraggon", route.avoid)
        self.assertIn("villainous youth", route.avoid)

    def test_live_anchor_route_expands_hunter_ground_z_delta_from_sampled_mismatch(self) -> None:
        args = SimpleNamespace(ground_z_offset=0)
        route = growth.route_point(5, 348164, 498725, 4598, "water beetle collector", live_anchor_z=True)

        with mock.patch.object(growth, "sample_route_z", return_value=3500):
            self.assertEqual(
                growth.growth_hunter_target_max_ground_z_delta_for_route(
                    args,
                    5,
                    2,
                    growth.REALMS["hib"],
                    route,
                ),
                1178,
            )

    def test_mid_early_gear_route_uses_mularn_worker_cluster(self) -> None:
        route = growth.select_route_point(growth.REALMS["mid"], level=6, party_size=1)

        self.assertEqual(growth.target_levels(6, 1, "mid"), (4, 4, 0))
        self.assertEqual(route.teleport_destination, "Mularn")
        self.assertIn("wood-eater worker", route.prefer)
        self.assertIn("vein spider", route.avoid)
        self.assertIn("small hill cat", route.avoid)
        self.assertEqual((route.x, route.y, route.z), (786637, 723034, 4722))
        self.assertLess(math.hypot(803612 - route.x, 726671 - route.y), 18000)

    def test_mid_level_seven_route_uses_level_six_gotar_cluster(self) -> None:
        route = growth.select_route_point(growth.REALMS["mid"], level=7, party_size=1)

        self.assertEqual(growth.target_levels(7, 1, "mid"), (6, 6, 0))
        self.assertEqual(route.level, 7)
        self.assertEqual(route.teleport_destination, "Gotar")
        self.assertEqual(route.prefer, "carrion crawler")
        self.assertNotIn("young grendelorm", route.prefer)
        self.assertIn("vein spider", route.avoid)
        self.assertIn("young grendelorm", route.avoid)
        self.assertEqual((route.x, route.y, route.z), (787192, 868637, 6698))

    def test_alb_level_eight_uses_xp_eligible_level_six_route_while_mid_uses_level_six_cluster(self) -> None:
        alb = growth.select_route_point(growth.REALMS["alb"], level=8, party_size=1)
        mid = growth.select_route_point(growth.REALMS["mid"], level=8, party_size=1)

        self.assertEqual(alb.level, 8)
        self.assertEqual(alb.teleport_destination, "Campacorentin Station")
        self.assertIn("giant spider", alb.prefer)
        self.assertNotIn("shady pilferer", alb.prefer)
        self.assertEqual((alb.x, alb.y), (498052, 592067))

        self.assertEqual(mid.level, 8)
        self.assertEqual(mid.teleport_destination, "Audliten")
        self.assertIn("army ant worker", mid.prefer)
        self.assertNotIn("vein spider", mid.prefer)
        self.assertEqual((mid.x, mid.y), (719301, 770132))

    def test_level_eight_route_requires_preferred_target_to_avoid_wrong_npcs(self) -> None:
        alb = growth.select_route_point(growth.REALMS["alb"], level=8, party_size=1)
        mid = growth.select_route_point(growth.REALMS["mid"], level=8, party_size=1)

        self.assertEqual(growth.strict_route_target_name(alb, 8), "giant spider")
        self.assertEqual(growth.strict_route_target_name(mid, 8), "army ant worker")

    def test_mid_level_five_train_route_uses_db_backed_dense_worker_cluster(self) -> None:
        route = growth.select_route_point(growth.REALMS["mid"], level=5, party_size=1)

        self.assertEqual(route.teleport_destination, "Mularn")
        self.assertIn("wood-eater", route.prefer)
        self.assertIn("wood-eater worker", route.avoid)
        self.assertIn("hill person", route.avoid)
        self.assertIn("young grendelorm", route.avoid)
        self.assertEqual((route.x, route.y, route.z), (786637, 723034, 4722))
        self.assertLess(math.hypot(803612 - route.x, 726671 - route.y), 18000)

    def test_hib_level_one_route_prefers_level_zero_badger_cubs(self) -> None:
        route = growth.select_route_point(growth.REALMS["hib"], level=1, party_size=1)

        self.assertIn("badger cub", route.prefer)
        self.assertIn("large frog", route.prefer)
        self.assertIn("annoying lucradan", route.prefer)
        self.assertIn("water beetle larva", route.avoid)
        self.assertEqual((route.x, route.y, route.z), (344500, 474500, 5372))

    def test_hib_level_one_and_two_shortage_recovery_targets_level_zero_mobs(self) -> None:
        args = SimpleNamespace(growth_allow_lower_xp_gear_farm=True)
        item_plans = {
            "growthhib00001": growth.GrowthItemPlan(
                equip_slots=[],
                sell_slots=[],
                buy_shortage_copper=110,
            )
        }

        for current_level in (1, 2):
            with self.subTest(current_level=current_level):
                behavior_args = SimpleNamespace()
                override = growth.growth_shortage_recovery_route_override(
                    args,
                    growth.REALMS["hib"],
                    current_level=current_level,
                    party_size=1,
                    item_plans=item_plans,
                )
                applied = growth.apply_growth_shortage_recovery_route_override(
                    behavior_args,
                    args,
                    growth.REALMS["hib"],
                    current_level=current_level,
                    party_size=1,
                    item_plans=item_plans,
                )

                self.assertEqual(override, (1, 1))
                self.assertTrue(applied)
                self.assertEqual(behavior_args.growth_route_level_override, 1)
                self.assertEqual(behavior_args.growth_target_level_override, 1)
                self.assertEqual(behavior_args.growth_target_plan_override, (0, 0, 0))
                self.assertTrue(behavior_args.growth_allow_lower_xp_target_plan)

    def test_alb_hib_early_gear_routes_use_reachable_xp_eligible_mobs(self) -> None:
        expected = {
            "alb": "small bear",
            "hib": "mudman",
        }
        for realm_key, preferred_name in expected.items():
            with self.subTest(realm=realm_key):
                realm = growth.REALMS[realm_key]
                route = growth.select_route_point(realm, level=6, party_size=1)
                self.assertIn(preferred_name, route.prefer)
                if realm_key == "alb":
                    self.assertNotIn("skeleton", route.prefer)
                    self.assertIn("Pebble", route.avoid)
                    self.assertIn("shady pilferer", route.avoid)
                    self.assertEqual((route.x, route.y, route.z), (591020, 532686, 2342))
                    self.assertEqual(route.teleport_destination, "Prydwen Keep")
                if realm_key == "hib":
                    self.assertEqual(growth.target_levels(6, 1, "hib"), (4, 4, 0))
                    self.assertEqual(growth.growth_hunter_target_max_ground_z_delta(6, 1, "hib"), 500)
                    self.assertEqual(
                        growth.strict_route_target_name(route, 6, party_size=1, realm_key="hib"),
                        "mudman",
                    )
                    self.assertEqual(route.teleport_destination, "")
                    self.assertIn("skeletal minion", route.avoid)
                    self.assertIn("spraggon", route.avoid)
                    self.assertEqual((route.x, route.y, route.z), (348637, 479175, 5742))

    def test_hib_level_eight_route_uses_db_backed_shannon_hill_toads(self) -> None:
        route = growth.select_route_point(growth.REALMS["hib"], level=8, party_size=1)

        self.assertEqual(route.teleport_destination, "Shannon Estuary")
        self.assertIn("hill toad", route.prefer)
        self.assertNotIn("water beetle", route.prefer)
        self.assertLess(math.hypot(route.x - 309663, route.y - 647096), 2500)

    def test_hib_level_ten_route_uses_db_backed_tir_na_mbeo_water_beetles(self) -> None:
        route = growth.select_route_point(growth.REALMS["hib"], level=10, party_size=1)

        self.assertEqual(route.teleport_destination, "Tir na mBeo")
        self.assertIn("water beetle", route.prefer)
        self.assertIn("water beetle collector", route.avoid)
        self.assertLess(math.hypot(route.x - 350899, route.y - 531716), 2500)

    def test_albion_level_fifty_route_uses_hazard_scored_moorlich_cluster(self) -> None:
        route = growth.select_route_point(growth.REALMS["alb"], level=50, party_size=2)

        self.assertEqual(route.teleport_destination, "Yarley's Farm")
        self.assertIn("moorlich", route.prefer)
        self.assertIn("gabriel hound", route.avoid)
        self.assertLess(math.hypot(route.x - 332701, route.y - 669142), 2500)

    def test_mid_hib_level_fifty_routes_use_existing_reachable_teleports(self) -> None:
        mid = growth.select_route_point(growth.REALMS["mid"], level=50, party_size=2)
        hib = growth.select_route_point(growth.REALMS["hib"], level=50, party_size=2)

        self.assertEqual(mid.teleport_destination, "Svasud Faste")
        self.assertIn("savage wyvern", mid.prefer)
        self.assertEqual(mid.objective_adds, "")
        self.assertLess(math.hypot(mid.x - 742631, mid.y - 668137), 2500)
        self.assertIn("winter wolf", mid.avoid)
        self.assertEqual(hib.teleport_destination, "Innis Carthaig")
        self.assertIn("far darrig", hib.prefer)
        self.assertIn("melancholic fairy", hib.avoid)
        self.assertLess(math.hypot(hib.x - 332526, hib.y - 733763), 2500)

    def test_hunting_ground_analyzer_clusters_same_name_mobs_by_area(self) -> None:
        args = SimpleNamespace(
            party_size=2,
            min_cluster_count=2,
            top=5,
            cluster_size=20000,
        )
        captured_sql = []

        def fake_run_mysql(_args, sql):
            captured_sql.append(sql)
            return (
                "Name\tLevel\tgrid_x\tgrid_y\tmob_count\tavg_x\tavg_y\tavg_z\t"
                "min_aggro\tmax_aggro_range\tspan_x\tspan_y\n"
                "icestrider interceptor\t47\t33\t32\t17\t660990\t647035\t9455\t80\t500\t1700\t1200\n"
            )

        original_run_mysql = hunting_analyzer.growth.run_mysql
        original_teleport = hunting_analyzer.nearest_teleporter
        try:
            hunting_analyzer.growth.run_mysql = fake_run_mysql
            hunting_analyzer.nearest_teleporter = lambda _realm_key, _x, _y: ("Vindsaul Faste", 50000.0)

            rows = hunting_analyzer.candidate_rows(args, "mid", 50)
        finally:
            hunting_analyzer.growth.run_mysql = original_run_mysql
            hunting_analyzer.nearest_teleporter = original_teleport

        self.assertEqual(rows[0]["x"], 660990)
        self.assertEqual(rows[0]["y"], 647035)
        self.assertEqual(rows[0]["party_size"], 2)
        self.assertIn("FLOOR(X / 20000)", captured_sql[0])
        self.assertIn("AND Realm <> 2", captured_sql[0])
        self.assertIn("LOWER(Name) NOT LIKE '%dummy%'", captured_sql[0])
        self.assertIn("LOWER(Name) NOT LIKE 'total:%'", captured_sql[0])
        self.assertIn("GROUP BY Name, Level, grid_x, grid_y", captured_sql[0])

    def test_hunting_ground_analyzer_uses_party_carry_target_plan_for_mid_duo_l10(self) -> None:
        args = SimpleNamespace(
            party_size=2,
            min_cluster_count=2,
            top=5,
            cluster_size=20000,
        )
        captured_sql = []

        def fake_run_mysql(_args, sql):
            captured_sql.append(sql)
            return (
                "Name\tLevel\tgrid_x\tgrid_y\tmob_count\tavg_x\tavg_y\tavg_z\t"
                "neutral_count\tmin_aggro\tmax_aggro\tmax_aggro_range\tspan_x\tspan_y\n"
                "svartalf outcast\t8\t36\t41\t20\t732369\t834240\t4792\t20\t0\t0\t500\t2000\t2000\n"
            )

        original_run_mysql = hunting_analyzer.growth.run_mysql
        original_teleport = hunting_analyzer.nearest_teleporter
        try:
            hunting_analyzer.growth.run_mysql = fake_run_mysql
            hunting_analyzer.nearest_teleporter = lambda _realm_key, _x, _y: ("Gotar", 3000.0)

            rows = hunting_analyzer.candidate_rows(args, "mid", 10, 2)
        finally:
            hunting_analyzer.growth.run_mysql = original_run_mysql
            hunting_analyzer.nearest_teleporter = original_teleport

        self.assertEqual(rows[0]["target_min"], 8)
        self.assertEqual(rows[0]["target_ideal"], 9)
        self.assertEqual(rows[0]["target_max"], 10)
        self.assertIn("Level BETWEEN 8 AND 10", captured_sql[0])

    def test_hunting_ground_analyzer_excludes_suite_static_avoid_candidates(self) -> None:
        args = SimpleNamespace(
            party_size=2,
            min_cluster_count=2,
            top=5,
            cluster_size=20000,
        )

        def fake_run_mysql(_args, _sql):
            return (
                "Name\tLevel\tgrid_x\tgrid_y\tmob_count\tavg_x\tavg_y\tavg_z\t"
                "neutral_count\tmin_aggro\tmax_aggro\tmax_aggro_range\tspan_x\tspan_y\n"
                "wind wisp\t9\t36\t39\t4\t723284\t786268\t4602\t0\t200\t200\t500\t1000\t1000\n"
                "army ant soldier\t8\t36\t39\t12\t739371\t789159\t4714\t12\t0\t0\t500\t1000\t1000\n"
            )

        original_run_mysql = hunting_analyzer.growth.run_mysql
        original_teleport = hunting_analyzer.nearest_teleporter
        try:
            hunting_analyzer.growth.run_mysql = fake_run_mysql
            hunting_analyzer.nearest_teleporter = lambda _realm_key, _x, _y: ("Huginfell", 1200.0)

            rows = hunting_analyzer.candidate_rows(args, "mid", 10, 2)
        finally:
            hunting_analyzer.growth.run_mysql = original_run_mysql
            hunting_analyzer.nearest_teleporter = original_teleport

        self.assertEqual([row["name"] for row in rows], ["army ant soldier"])

    def test_hunting_ground_analyzer_keeps_route_candidate_pool(self) -> None:
        rows = [{"name": f"candidate-{index}"} for index in range(5)]

        default_args = SimpleNamespace(top=4, route_top=0)
        limited_args = SimpleNamespace(top=5, route_top=2)

        self.assertEqual(
            [row["name"] for row in hunting_analyzer.route_recommendation_rows(default_args, rows)],
            ["candidate-0", "candidate-1", "candidate-2", "candidate-3"],
        )
        self.assertEqual(
            [row["name"] for row in hunting_analyzer.route_recommendation_rows(limited_args, rows)],
            ["candidate-0", "candidate-1"],
        )

    def test_hunting_ground_analyzer_live_preflight_filters_unsafe_candidates(self) -> None:
        args = SimpleNamespace(
            live_preflight=True,
            live_preflight_filter=True,
            live_api_url="http://127.0.0.1:5000",
            api_host="127.0.0.1",
            api_port=5000,
            live_preflight_log_dir="",
            live_preflight_current_level=10,
            live_preflight_timeout=0.1,
            live_preflight_radius=6500.0,
            live_preflight_limit=10,
            live_preflight_min_available_targets=0,
            live_preflight_hazard_radius=2500.0,
            live_preflight_hazard_limit=3,
            live_preflight_hazard_token_limit=12,
        )
        rows = [
            {
                "realm": "mid",
                "party_size": 2,
                "player_level": 8,
                "target_min": 7,
                "target_ideal": 7,
                "target_max": 10,
                "name": "unsafe camp",
                "mob_level": 7,
                "mob_count": 8,
                "x": 700000,
                "y": 700000,
                "z": 4500,
                "nearest_teleporter": "Gotar",
                "score": 10.0,
            },
            {
                "realm": "mid",
                "party_size": 2,
                "player_level": 9,
                "target_min": 7,
                "target_ideal": 7,
                "target_max": 10,
                "name": "safe camp",
                "mob_level": 7,
                "mob_count": 8,
                "x": 710000,
                "y": 710000,
                "z": 4550,
                "nearest_teleporter": "Gotar",
                "score": 9.0,
            },
        ]
        calls: list[tuple[str, bool, int, int]] = []

        def fake_checked_route(preflight_args, route, *, realm, current_level, party_size):
            self.assertEqual(realm.key, "mid")
            calls.append(
                (
                    route.prefer,
                    bool(preflight_args.growth_route_level_is_carry_target),
                    int(preflight_args.growth_route_player_level),
                    int(party_size),
                    tuple(preflight_args.growth_target_plan_override),
                    int(preflight_args.growth_target_level_override),
                )
            )
            self.assertEqual(preflight_args.growth_fast_travel, "route-home")
            self.assertFalse(preflight_args.dry_run)
            self.assertEqual(current_level, 10)
            return route if route.prefer == "safe camp" else None

        original_checked_route = hunting_analyzer.growth.growth_route_preflight_checked_route
        try:
            hunting_analyzer.growth.growth_route_preflight_checked_route = fake_checked_route
            filtered = hunting_analyzer.apply_live_preflight_to_rows(args, [dict(row) for row in rows])
        finally:
            hunting_analyzer.growth.growth_route_preflight_checked_route = original_checked_route

        self.assertEqual([row["name"] for row in filtered], ["safe camp"])
        self.assertEqual(filtered[0]["live_preflight_status"], "ok")
        self.assertEqual(
            calls,
            [
                ("unsafe camp", True, 10, 2, (8, 9, 1), 10),
                ("safe camp", True, 10, 2, (8, 9, 1), 10),
            ],
        )

    def test_hunting_ground_analyzer_live_preflight_can_annotate_without_filtering(self) -> None:
        args = SimpleNamespace(
            live_preflight=True,
            live_preflight_filter=False,
            live_api_url="http://127.0.0.1:5000",
            api_host="127.0.0.1",
            api_port=5000,
            live_preflight_log_dir="",
            live_preflight_timeout=0.1,
            live_preflight_radius=6500.0,
            live_preflight_limit=10,
            live_preflight_min_available_targets=0,
            live_preflight_hazard_radius=2500.0,
            live_preflight_hazard_limit=3,
            live_preflight_hazard_token_limit=12,
        )
        rows = [
            {
                "realm": "mid",
                "party_size": 2,
                "player_level": 10,
                "target_min": 7,
                "target_ideal": 7,
                "target_max": 10,
                "name": "unsafe camp",
                "mob_level": 7,
                "mob_count": 8,
                "x": 700000,
                "y": 700000,
                "z": 4500,
                "nearest_teleporter": "Gotar",
                "score": 10.0,
            },
        ]

        original_checked_route = hunting_analyzer.growth.growth_route_preflight_checked_route
        try:
            hunting_analyzer.growth.growth_route_preflight_checked_route = lambda *_args, **_kwargs: None
            filtered = hunting_analyzer.apply_live_preflight_to_rows(args, [dict(row) for row in rows])
        finally:
            hunting_analyzer.growth.growth_route_preflight_checked_route = original_checked_route

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["live_preflight_status"], "skip")

    def test_hunting_ground_analyzer_rechecks_adjusted_route_before_output(self) -> None:
        args = SimpleNamespace(
            live_preflight=True,
            live_preflight_filter=True,
            live_api_url="http://127.0.0.1:5000",
            api_host="127.0.0.1",
            api_port=5000,
            live_preflight_log_dir="",
            live_preflight_current_level=10,
            live_preflight_timeout=0.1,
            live_preflight_radius=6500.0,
            live_preflight_limit=10,
            live_preflight_min_available_targets=2,
            live_preflight_hazard_radius=2500.0,
            live_preflight_hazard_limit=3,
            live_preflight_hazard_token_limit=12,
        )
        row = {
            "realm": "mid",
            "party_size": 2,
            "player_level": 10,
            "target_min": 8,
            "target_ideal": 9,
            "target_max": 10,
            "name": "lake serpent",
            "mob_level": 10,
            "mob_count": 8,
            "x": 713945,
            "y": 769705,
            "z": 4191,
            "nearest_teleporter": "Huginfell",
            "score": 9.0,
        }
        calls: list[tuple[int, int, int]] = []

        def fake_checked_route(_preflight_args, route, *, realm, current_level, party_size):
            self.assertEqual(realm.key, "mid")
            self.assertEqual(current_level, 10)
            self.assertEqual(party_size, 2)
            calls.append((route.x, route.y, route.z))
            if (route.x, route.y, route.z) == (713945, 769705, 4191):
                return dataclasses.replace(route, x=717377, y=767286, z=4090)
            return None

        original_checked_route = hunting_analyzer.growth.growth_route_preflight_checked_route
        try:
            hunting_analyzer.growth.growth_route_preflight_checked_route = fake_checked_route
            filtered = hunting_analyzer.apply_live_preflight_to_rows(args, [dict(row)])
        finally:
            hunting_analyzer.growth.growth_route_preflight_checked_route = original_checked_route

        self.assertEqual(filtered, [])
        self.assertEqual(calls, [(713945, 769705, 4191), (717377, 767286, 4090)])

    def test_growth_hunting_index_spreads_cases_across_candidate_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "alb,1,3,1,2,2,far spriggarn,2,39,9000,9000,300,39,0,0,0,Cotswold Village,12446,500\n"
                "alb,1,20,19,20,21,adder,19,12,1000,2000,300,12,0,0,0,Prydwen Keep,500,100\n"
                "alb,1,20,19,20,21,wild boar,19,10,5000,6000,700,10,0,0,0,Caer Ulfwych,800,90\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(growth_hunting_index=str(index_path), growth_route_case_index=0)

            early = growth.select_growth_route_point(args, growth.REALMS["alb"], 3, 1)
            route_home_args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )
            route_home_early = growth.select_growth_route_point(route_home_args, growth.REALMS["alb"], 3, 1)
            first = growth.select_growth_route_point(args, growth.REALMS["alb"], 20, 1)
            args.growth_route_case_index = 1
            second = growth.select_growth_route_point(args, growth.REALMS["alb"], 20, 1)

        self.assertNotEqual(early.prefer, "far spriggarn")
        self.assertEqual(route_home_early.prefer, "far spriggarn")
        self.assertEqual((first.x, first.y, first.prefer, first.teleport_destination), (1000, 2000, "adder", "Prydwen Keep"))
        self.assertEqual((second.x, second.y, second.prefer, second.teleport_destination), (5000, 6000, "wild boar", "Caer Ulfwych"))
        self.assertEqual(first.source, "hunting-index")
        self.assertEqual(growth.strict_route_target_name(first, 20, party_size=1, realm_key="alb"), "adder")
        distance_args = SimpleNamespace(max_target_distance=1500)
        self.assertEqual(growth.growth_max_target_distance(distance_args, 1, 1, "alb"), 1500.0)
        self.assertEqual(growth.growth_max_target_distance(distance_args, 1, 1, "alb", first), 5200.0)
        home_args = SimpleNamespace(max_target_distance=1500, combat_home_leash_distance=1200)
        self.assertEqual(growth.growth_required_target_home_hunt_distance(home_args, 1, 1, "alb"), 6200.0)
        self.assertEqual(growth.growth_required_target_home_hunt_distance(home_args, 1, 1, "alb", first), 6200.0)
        self.assertEqual(growth.growth_combat_direct_move_distance(distance_args, 1, 1, "alb"), 1500.0)
        self.assertEqual(growth.growth_combat_direct_move_distance(distance_args, 1, 1, "alb", first), 5200.0)

    def test_growth_hunting_index_skips_sparse_low_level_party_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,4,2,2,4,4,sparse camp,4,3,1000,2000,300,3,0,0,0,Audliten,100,2000\n"
                "mid,4,2,2,4,4,dense camp,4,12,5000,6000,700,12,0,0,0,Fort Atla,17000,1000\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["mid"], 3, 4)

        self.assertEqual(route.prefer, "dense camp")
        distance_args = SimpleNamespace(max_target_distance=1500)
        self.assertEqual(growth.growth_max_target_distance(distance_args, 3, 4, "mid", route), 6500.0)

    def test_growth_fast_travel_options_parse_for_hunting_index_runs(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--growth-hunting-index",
                "tools/test-output/index.csv",
                "--growth-fast-travel",
                "route-home",
            ]
        )

        self.assertEqual(args.growth_hunting_index, "tools/test-output/index.csv")
        self.assertEqual(args.growth_fast_travel, "route-home")

        teleport_alias = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--growth-fast-travel",
                "teleport",
            ]
        )

        self.assertEqual(teleport_alias.growth_fast_travel, "route-home")

    def test_l10_clean_checkpoint_defaults_to_complete_route_home_fast_travel(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--reset-level",
                "10",
                "--max-level",
                "11",
                "--max-segments",
                "1",
            ]
        )

        self.assertEqual(args.growth_fast_travel, "route-home")
        self.assertEqual(args.checkpoint_start_location, "route-home")

    def test_l10_clean_checkpoint_respects_explicit_realm_start(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--reset-level",
                "10",
                "--max-level",
                "11",
                "--checkpoint-start-location",
                "realm-start",
                "--growth-fast-travel",
                "off",
            ]
        )

        self.assertEqual(args.growth_fast_travel, "off")
        self.assertEqual(args.checkpoint_start_location, "realm-start")

    def test_hunting_ground_analyzer_prefers_reachable_dense_targets_in_level_range(self) -> None:
        exact_but_far = hunting_analyzer.score_candidate(
            target_level=47,
            candidate_level=47,
            count=6,
            teleporter_distance=52392,
        )
        nearby_dense_in_range = hunting_analyzer.score_candidate(
            target_level=47,
            candidate_level=48,
            count=8,
            teleporter_distance=40991,
        )

        self.assertGreater(nearby_dense_in_range, exact_but_far)

    def test_high_level_growth_uses_longer_flee_safe_points(self) -> None:
        self.assertLess(growth.growth_flee_safe_point_distance(10), growth.growth_flee_safe_point_distance(50))
        self.assertGreaterEqual(growth.growth_flee_safe_point_distance(50), 9000)
        self.assertGreaterEqual(growth.growth_flee_critical_safe_point_distance(50), 14000)

    def test_albion_growth_two_player_party_starts_with_tank_and_healer(self) -> None:
        realm = growth.REALMS["alb"]

        self.assertTrue(realm.growth_class_cycle.startswith("1|6|"))
        self.assertTrue(realm.growth_spec_cycle.startswith("Slash|39"))
        self.assertIn("Rejuvenation|40", realm.growth_spec_cycle.split("||")[1])

    def test_albion_growth_theurgist_trains_wind_damage_before_earth_utility(self) -> None:
        realm = growth.REALMS["alb"]
        growth_specs = growth.split_spec_cycle(realm.growth_spec_cycle)

        self.assertEqual(growth.growth_cycle(realm.growth_class_cycle, realm.class_cycle).split("|")[6], "5")
        self.assertTrue(growth_specs[6].startswith("Wind Magic|45"))
        self.assertIn("Earth Magic|25", growth_specs[6])

    def test_mid_hib_growth_two_player_parties_start_with_tank_and_healer(self) -> None:
        mid = growth.REALMS["mid"]
        hib = growth.REALMS["hib"]

        self.assertTrue(mid.growth_class_cycle.startswith("22|26|"))
        self.assertIn("Mending|40", mid.growth_spec_cycle.split("||")[1])
        self.assertEqual(growth.growth_cycle(mid.growth_class_cycle, mid.class_cycle).split("|")[:4], ["22", "26", "31", "22"])
        self.assertIn("Shields|42", growth.split_spec_cycle(mid.growth_spec_cycle)[3])
        self.assertIn("Hammer|50", growth.split_spec_cycle(mid.growth_spec_cycle)[3])
        self.assertTrue(hib.growth_class_cycle.startswith("44|47|"))
        self.assertIn("Regrowth|40", hib.growth_spec_cycle.split("||")[1])
        self.assertEqual(growth.growth_cycle(hib.growth_class_cycle, hib.class_cycle).split("|")[:4], ["44", "47", "43", "43"])
        self.assertIn("Celtic Dual|50", growth.split_spec_cycle(hib.growth_spec_cycle)[3])

    def test_level_fifty_two_player_party_uses_high_forties_targets(self) -> None:
        self.assertEqual(growth.target_levels(50, 2), (46, 47, 1))

    def test_level_fifty_large_party_uses_high_forties_with_level_fifty_ceiling(self) -> None:
        self.assertEqual(growth.target_levels(50, 4), (46, 48, 2))
        self.assertEqual(growth.target_levels(50, 8), (46, 48, 2))
        self.assertEqual(growth.target_max_level(50, 48, 2), 50)

    def test_growth_route_points_stay_inside_client_zone_bounds(self) -> None:
        for realm_key, realm in growth.REALMS.items():
            with open(realm.ground_z_map, encoding="utf-8") as handle:
                zone_config = json.load(handle)

            for route in realm.points:
                with self.subTest(realm=realm_key, level=route.level):
                    self.assertTrue(
                        route_point_inside_zone_config(route, zone_config),
                        f"{realm_key} level {route.level} route point is outside client zone bounds: "
                        f"{route.x},{route.y},{route.z}",
                    )

    def test_low_level_waypoints_stay_near_starter_hunt_area(self) -> None:
        offsets = growth.waypoint_offsets(3)

        self.assertNotIn((5200, 0), offsets)
        self.assertLessEqual(max(abs(x) for x, _y in offsets), 2400)
        self.assertLessEqual(max(abs(y) for _x, y in offsets), 2400)

    def test_early_gear_growth_can_hunt_across_wide_index_camp_radius(self) -> None:
        args = SimpleNamespace(combat_home_leash_distance=1200.0)

        self.assertEqual(growth.growth_combat_home_leash_distance(args, 6), 10000.0)

    def test_high_level_party_growth_can_chase_within_large_hunting_camp(self) -> None:
        args = SimpleNamespace(target_home_max_distance=1400.0, combat_home_leash_distance=1200.0)

        self.assertEqual(growth.growth_target_home_max_distance(args, 50), 2800.0)
        self.assertEqual(growth.growth_combat_home_leash_distance(args, 50), 2800.0)

    def test_level_ten_solo_checkpoint_targets_lower_con_for_gear_stage(self) -> None:
        self.assertEqual(growth.target_levels(10, 1), (7, 8, 1))
        self.assertEqual(growth.target_levels(10, 1, "alb"), (7, 7, 0))
        self.assertEqual(growth.target_max_level(10, 8, 1), 9)

    def test_level_ten_routes_start_near_teleporter_hunting_clusters(self) -> None:
        mid = growth.select_route_point(growth.REALMS["mid"], level=10, party_size=1)
        hib = growth.select_route_point(growth.REALMS["hib"], level=10, party_size=1)
        alb = growth.select_route_point(growth.REALMS["alb"], level=10, party_size=1)

        self.assertEqual(alb.teleport_destination, "Castle Sauvage")
        self.assertIn("adder", alb.prefer)
        self.assertIn("dragon ant soldier", alb.avoid)
        self.assertNotIn("veteran adder", alb.avoid)
        self.assertIn("giant spider", alb.avoid)
        self.assertIn("bandit", alb.avoid)
        self.assertEqual(mid.teleport_destination, "Fort Veldon")
        self.assertIn("young grendelorm", mid.prefer)
        self.assertIn("small hill cat", mid.avoid)
        self.assertIn("wolf spiderling", mid.avoid)
        self.assertEqual(hib.teleport_destination, "Tir na mBeo")
        self.assertIn("water beetle", hib.prefer)
        self.assertIn("water beetle collector", hib.avoid)
        self.assertEqual((alb.x, alb.y, alb.z), (594457, 499932, 2057))
        self.assertEqual((mid.x, mid.y, mid.z), (809316, 678732, 5003))
        self.assertEqual((hib.x, hib.y, hib.z), (350899, 531716, 3637))

        teleporter = next(
            point
            for point in growth.TELEPORT_DESTINATIONS["hib"]
            if point[0] == hib.teleport_destination
        )
        self.assertLessEqual(math.hypot(hib.x - teleporter[1], hib.y - teleporter[2]), 15000.0)

    def test_alb_level_ten_solo_route_keeps_live_castle_adders_in_xp_band(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=180,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=2200,
            target_home_max_distance=6200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=1,
                party_size=1,
                current_level=10,
                path_graph=Path("graph.json"),
            )
            payload = json.loads((case_dir / "live-control.json").read_text(encoding="utf-8"))

        self.assertEqual(growth.minimum_growth_effective_target_level(10, 1, "alb"), 7)
        self.assertEqual(payload["baseline_min_target_level"], 7)
        self.assertEqual(payload["baseline_max_target_level"], 8)
        self.assertEqual(command[command.index("--startup-teleport-destination") + 1], "Castle Sauvage")
        self.assertEqual(command[command.index("--required-target-home") + 1], "594457,499932,2059")
        self.assertEqual(command[command.index("--require-target-name") + 1], "adder")
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "adder")
        self.assertIn("dragon ant soldier", command[command.index("--avoid-target-name") + 1])
        self.assertNotIn("veteran adder", command[command.index("--avoid-target-name") + 1])
        self.assertNotIn("노련한 adder", command[command.index("--avoid-target-name") + 1])
        self.assertEqual(command[command.index("--objective-entry-aggro-avoid-radius") + 1], "2200")
        self.assertEqual(command[command.index("--flee-critical-health-percent") + 1], "45")
        self.assertEqual(command[command.index("--flee-step") + 1], "1600")
        self.assertEqual(command[command.index("--flee-movement-speed") + 1], "360")
        self.assertEqual(command[command.index("--min-target-level") + 1], "7")
        self.assertEqual(command[command.index("--max-target-level") + 1], "8")
        self.assertTrue(growth.watcher_observer_home_string(growth.REALMS["alb"], 10, 1).startswith("590500,499932,"))

    def test_alb_level_ten_clean_checkpoint_starts_on_rotting_zombie_baseline(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--realms",
                "alb",
                "--party-sizes",
                "1",
                "--checkpoint-levels",
                "10",
                "--checkpoint-start-location",
                "route-home",
                "--growth-fast-travel",
                "route-home",
            ]
        )
        args.growth_current_segment_index = 1

        route = growth.select_growth_route_point(args, growth.REALMS["alb"], 10, 1)
        point = growth.checkpoint_start_point(args, growth.REALMS["alb"], 10, 1)
        start_x, start_y, start_z = growth.REALMS["alb"].start

        self.assertEqual(route.prefer, "rotting zombie")
        self.assertEqual(route.mob_level, 7)
        self.assertEqual((route.x, route.y, route.z, route.teleport_destination), (527242, 624780, 1971, "Caer Ulfwych"))
        self.assertIn("death grip vines", route.avoid)
        self.assertIn("river racer", route.avoid)
        self.assertEqual((point.x, point.y, point.z), (start_x, start_y, start_z))
        self.assertEqual(growth.growth_target_nearby_avoid_names_for_route(10, 1, "alb", route), "")

    def test_alb_level_ten_solo_adder_failure_uses_rotting_zombie_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-05T00:00:00Z,alb-p1,alb,1,64,10,combat_no_kill;death_pressure,avoid_target,노련한 adder,8,combat_csv,67\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=64,
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 10, 1)

        self.assertEqual(route.prefer, "rotting zombie")
        self.assertEqual(route.mob_level, 7)
        self.assertEqual((route.x, route.y, route.teleport_destination), (527242, 624780, "Caer Ulfwych"))
        self.assertEqual(growth.growth_objective_entry_aggro_avoid_radius(10, 1, "alb", route), 2200.0)

    def test_alb_level_ten_rotting_behavior_lands_safe_but_keeps_target_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-05T00:00:00Z,alb-p1,alb,1,64,10,combat_no_kill;death_pressure,avoid_target,노련한 adder,8,combat_csv,67\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                host="127.0.0.1",
                port=10300,
                segment_seconds=45,
                ramp_up=2,
                login_retries=5,
                login_retry_delay=3.0,
                api_port=5000,
                max_target_distance=2200,
                target_home_max_distance=6200.0,
                target_timeout=65,
                combat_interval=1.5,
                target_pool=5,
                smooth_move_interval=0.2,
                movement_speed=191.0,
                path_last_mile_distance=1200.0,
                ground_z_offset=0,
                encounter_log_interval=3.0,
                nav_api_url="http://127.0.0.1:5000",
                live_api_url="",
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=64,
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                safe_exit_max_seconds=90,
            )
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()

            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=64,
                party_size=1,
                current_level=10,
                path_graph=Path("graph.json"),
            )

        startup_home = command[command.index("--startup-route-home-after-services") + 1]
        required_home = command[command.index("--required-target-home") + 1]
        start_x, start_y, start_z = (int(part) for part in startup_home.split(","))

        self.assertNotEqual(startup_home, required_home)
        self.assertTrue(required_home.startswith("527242,624780,"))
        self.assertEqual(start_x, 527242)
        self.assertEqual(624780 - start_y, 1300)
        self.assertLessEqual(abs(start_z - 1965), 220)
        self.assertLess(math.hypot(start_x - 521393, start_y - 616461), math.hypot(527242 - 521393, 624780 - 616461))

    def test_alb_level_ten_solo_rotting_zombie_failure_uses_forest_lion_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-06T00:21:15Z,alb-p1,alb,1,71,10,combat_no_kill,avoid_target,노련한 rotting zombie,7,combat_csv,74\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=71,
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 10, 1)

        self.assertEqual(route.prefer, "forest lion")
        self.assertEqual(route.mob_level, 7)
        self.assertEqual(route.mob_count, 3)
        self.assertEqual((route.x, route.y, route.teleport_destination), (496809, 640112, "Caer Ulfwych"))
        self.assertEqual(growth.growth_objective_entry_aggro_avoid_radius(10, 1, "alb", route), 0.0)

    def test_alb_level_ten_solo_forest_lion_failure_uses_bear_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-06T03:50:33Z,alb-p1,alb,1,85,10,combat_no_kill,avoid_target,노련한 forest lion,7,combat_csv,88\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=85,
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 10, 1)

        self.assertEqual(route.prefer, "bear")
        self.assertEqual(route.mob_level, 8)
        self.assertEqual(route.mob_count, 10)
        self.assertEqual((route.x, route.y, route.z, route.teleport_destination), (552382, 557133, 3149, "Prydwen Keep"))
        self.assertIn("forest lion", route.avoid)
        self.assertNotIn("forest bear", route.avoid)
        self.assertEqual(growth.growth_objective_entry_aggro_avoid_radius(10, 1, "alb", route), 0.0)

    def test_alb_level_ten_solo_bear_failure_uses_river_racer_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-06T03:50:33Z,alb-p1,alb,1,85,10,combat_no_kill,avoid_target,노련한 forest lion,7,combat_csv,88\n"
                "2026-07-06T04:45:16Z,alb-p1,alb,1,90,10,combat_no_kill,avoid_target,bear,8,combat_csv,93\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=90,
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )

            route = growth.select_growth_route_point(args, growth.REALMS["alb"], 10, 1)

        self.assertEqual(route.prefer, "river racer")
        self.assertEqual(route.mob_level, 7)
        self.assertEqual((route.x, route.y, route.z, route.teleport_destination), (440220, 619503, 1863, "Caer Ulfwych"))
        self.assertIn("bear", route.avoid)
        self.assertEqual(growth.growth_target_nearby_avoid_names_for_route(10, 1, "alb", route), "river racer")

    def test_hib_level_nine_ten_solo_allows_water_beetle_z_delta(self) -> None:
        self.assertEqual(growth.growth_hunter_target_max_ground_z_delta(9, 1, "hib"), 1200)
        self.assertEqual(growth.growth_hunter_target_max_ground_z_delta(10, 1, "hib"), 1200)
        self.assertEqual(growth.growth_hunter_target_max_ground_z_delta(8, 1, "hib"), 1200)
        self.assertEqual(growth.growth_hunter_target_max_ground_z_delta(10, 2, "hib"), 1200)
        self.assertEqual(growth.growth_hunter_target_max_attack_z_delta(10, 1, "hib"), 360)
        self.assertEqual(growth.growth_hunter_target_max_attack_z_delta(10, 2, "hib"), 220)

    def test_hib_level_ten_solo_hunting_index_uses_wider_ground_target_scan(self) -> None:
        args = SimpleNamespace(max_target_distance=2200.0)
        route = growth.RoutePoint(10, 349869, 494579, 5191, "lough wolf", "water beetle", "Mag Mell", source="hunting-index")

        self.assertEqual(growth.growth_max_target_distance(args, 10, 1, "hib", route), 5200.0)
        self.assertEqual(growth.growth_hunter_target_api_radius(args, 10, 1, "hib", route), 5200.0)
        self.assertEqual(growth.growth_hunter_target_api_engage_distance(args, 10, 1, "hib", route), 5200.0)

    def test_hib_level_ten_solo_growth_route_starts_on_water_beetle_cluster(self) -> None:
        route = growth.select_growth_route_point(SimpleNamespace(), growth.REALMS["hib"], 10, 1)

        self.assertEqual(route.prefer, "water beetle")
        self.assertEqual(route.mob_level, 7)
        self.assertEqual((route.x, route.y, route.z), (352178, 532352, 4598))
        self.assertNotIn("water beetle collector", route.avoid)
        self.assertNotIn("water beetle collector", growth.growth_avoid_targets_for_current_context(route, "hib", 10, 1))

    def test_hib_level_four_solo_route_home_uses_matching_scan_and_engage_radius(self) -> None:
        args = SimpleNamespace(max_target_distance=2200.0, growth_fast_travel="route-home")
        route = growth.RoutePoint(5, 361545, 491812, 4659, "small freshwater crab", "", "Mag Mell", source="hunting-index")

        self.assertEqual(growth.growth_hunter_target_api_radius(args, 4, 1, "hib", route), 6500.0)
        self.assertEqual(growth.growth_hunter_target_api_engage_distance(args, 4, 1, "hib", route), 6500.0)

    def test_alb_mid_level_five_six_solo_hunting_index_uses_wider_target_scan(self) -> None:
        args = SimpleNamespace(max_target_distance=2200.0)
        alb_route = growth.RoutePoint(5, 497150, 595621, 2039, "scrawny red lion", "", "Campacorentin Station", source="hunting-index")
        mid_route = growth.RoutePoint(5, 786637, 723034, 4722, "wood-eater worker", "", "Mularn", source="hunting-index")

        self.assertEqual(growth.growth_max_target_distance(args, 5, 1, "alb", alb_route), 6500.0)
        self.assertEqual(growth.growth_hunter_target_api_radius(args, 5, 1, "alb", alb_route), 6500.0)
        self.assertEqual(growth.growth_hunter_target_api_engage_distance(args, 6, 1, "mid", mid_route), 6500.0)

    def test_mid_low_duo_route_home_keeps_combat_leash_inside_scan_radius(self) -> None:
        args = SimpleNamespace(
            max_target_distance=5200.0,
            combat_home_leash_distance=1200.0,
            growth_fast_travel="route-home",
        )
        route = growth.RoutePoint(5, 786637, 723034, 4722, "wood-eater worker", "", "Mularn", source="hunting-index")

        self.assertEqual(growth.growth_max_target_distance(args, 4, 2, "mid", route), 6500.0)
        self.assertEqual(growth.growth_combat_home_leash_distance_for_route(args, 4, 2, "mid", route), 6500.0)
        self.assertEqual(growth.growth_required_target_home_hunt_distance(args, 4, 2, "mid", route), 6500.0)

    def test_low_small_party_growth_commits_before_fleeing(self) -> None:
        self.assertEqual(growth.growth_flee_health_percent(6, 2, "mid"), 30)
        self.assertEqual(growth.growth_flee_pressure_health_percent(5, 4, "alb"), 30)
        self.assertEqual(growth.growth_flee_critical_health_percent(4, 2, "hib"), 20)
        self.assertEqual(growth.growth_required_target_tank_commit_health_percent(7, 2, "alb"), 10)
        self.assertEqual(growth.growth_flee_pressure_health_percent(7, 8, "alb"), 85)
        self.assertEqual(growth.growth_flee_health_percent(10, 1, "hib"), 55)

    def test_level_ten_party_routes_use_party_sized_hunting_camps(self) -> None:
        alb = growth.select_route_point(growth.REALMS["alb"], level=10, party_size=2)
        mid = growth.select_route_point(growth.REALMS["mid"], level=10, party_size=4)
        hib = growth.select_route_point(growth.REALMS["hib"], level=10, party_size=8)

        self.assertEqual(alb.teleport_destination, "Campacorentin Station")
        self.assertIn("giant spider", alb.prefer)
        self.assertEqual((alb.x, alb.y, alb.z), (496426, 593548, 1904))
        self.assertEqual(mid.teleport_destination, "Gotar")
        self.assertEqual(mid.prefer, "hobgoblin prowler")
        self.assertEqual(mid.level, 10)
        self.assertEqual(mid.mob_level, 8)
        self.assertIn("ghost light", mid.avoid)
        self.assertEqual((mid.x, mid.y, mid.z), (747600, 855000, 4760))
        self.assertEqual(hib.teleport_destination, "Tir na mBeo")
        self.assertEqual(hib.prefer, "lough wolf")
        self.assertIn("red wolfhound", hib.avoid)
        self.assertIn("wild lucradan", hib.avoid)
        self.assertEqual((hib.x, hib.y, hib.z), (336157, 532604, 5556))

    def test_level_ten_two_player_growth_keeps_targets_at_or_below_player_level(self) -> None:
        self.assertEqual(growth.target_levels(10, 2), (7, 7, 0))
        self.assertEqual(growth.target_levels(10, 4), (8, 8, 0))
        self.assertEqual(growth.target_levels(10, 4, "hib"), (10, 10, 0))

    def test_level_ten_party_growth_keeps_home_gate_near_camp(self) -> None:
        args = SimpleNamespace(
            max_target_distance=2200.0,
            target_home_max_distance=6200.0,
            combat_home_leash_distance=6200.0,
        )

        self.assertEqual(growth.growth_target_home_max_distance(args, 10, party_size=2), 1800.0)
        self.assertEqual(growth.growth_combat_home_leash_distance(args, 10, party_size=2), 1800.0)
        self.assertEqual(growth.growth_required_target_home_hunt_distance(args, 10, party_size=2), 1800.0)
        self.assertEqual(growth.growth_target_home_max_distance(args, 10, party_size=1), 6200.0)

    def test_level_ten_hib_route_uses_heightmap_aligned_water_beetles(self) -> None:
        hib = growth.select_route_point(growth.REALMS["hib"], level=10, party_size=1)
        sampled_z = growth.sample_route_z(
            growth.REALMS["hib"],
            growth.build_realm_height_samplers(),
            hib.x,
            hib.y,
            hib.z,
            ground_z_offset=0,
        )

        self.assertLess(abs(sampled_z - hib.z), 120)

    def test_level_ten_mid_watcher_observer_uses_teleporter_side_safe_point(self) -> None:
        observer_home = growth.watcher_observer_home_string(
            growth.REALMS["mid"],
            level=10,
            party_size=1,
            observer_distance=8000.0,
            ground_z_offset=0,
        )
        x, y, _z = [int(part) for part in observer_home.split(",")]

        self.assertLess(math.hypot(x - 803114, y - 678624), 80.0)
        self.assertLess(math.hypot(x - 801046, y - 678588), 2200.0)
        self.assertGreater(y, 678000)
        self.assertLess(y, 679500)

    def test_experience_floor_matches_server_level_table(self) -> None:
        self.assertEqual(growth.experience_floor_for_level(1), 0)
        self.assertEqual(growth.experience_floor_for_level(3), 250)
        self.assertEqual(growth.experience_floor_for_level(5), 2300)

    def test_early_growth_parties_preserve_support_slot_rotations(self) -> None:
        self.assertEqual(growth.early_growth_party_slot_rotations(1, 2), "melee-burst,healer-support")
        self.assertEqual(
            growth.early_growth_party_slot_rotations(1, 4),
            "melee-burst,melee-basic,melee-basic,none",
        )
        self.assertEqual(
            growth.early_growth_party_slot_rotations(4, 8),
            "melee-burst,healer-support,melee-basic,melee-basic,melee-basic,healer-support,caster-basic,none",
        )
        self.assertEqual(
            growth.early_growth_party_slot_rotations(4, 8, carry_tuning=False),
            "melee-burst,healer-support,melee-basic,melee-basic,melee-basic,healer-support,caster-basic,melee-basic",
        )
        self.assertEqual(
            growth.early_growth_party_slot_rotations(5, 8),
            "melee-burst,healer-support,melee-basic,melee-basic,melee-basic,healer-support,caster-basic,none",
        )
        self.assertEqual(
            growth.early_growth_party_slot_rotations(10, 8),
            "melee-burst,healer-support,melee-basic,melee-basic,melee-basic,healer-support,caster-basic,none",
        )
        self.assertEqual(
            growth.early_growth_party_slot_rotations(9, 4),
            "melee-burst,melee-basic,melee-basic,none",
        )
        self.assertEqual(
            growth.early_growth_party_slot_rotations(11, 8),
            "melee-burst,healer-support,melee-basic,melee-basic,melee-basic,healer-support,caster-basic,none",
        )
        self.assertEqual(growth.early_growth_party_slot_rotations(1, 1), "")

    def test_early_growth_large_parties_start_after_tracked_member_ready(self) -> None:
        self.assertEqual(growth.party_min_ready(1, 8), 8)
        self.assertEqual(growth.party_min_ready(4, 8), 8)
        self.assertEqual(growth.party_min_ready(4, 8, carry_tuning=False), 8)
        self.assertEqual(growth.party_min_ready(5, 8), 8)
        self.assertEqual(growth.party_min_ready(9, 4), 4)
        self.assertEqual(growth.party_min_ready(1, 2), 2)
        self.assertEqual(growth.party_min_ready(50, 8), 8)
        self.assertEqual(growth.growth_party_assist_interval(1, 4), "0.6")
        self.assertEqual(growth.growth_party_assist_interval(4, 8), "0.6")
        self.assertEqual(growth.growth_party_assist_interval(5, 8), "0.6")
        self.assertEqual(growth.growth_party_assist_interval(50, 4, level50_boss_party=True), "0.6")
        self.assertEqual(growth.growth_attack_target_in_view_prime_delay(1, 4), "0.0")
        self.assertEqual(growth.growth_attack_target_in_view_prime_delay(5, 4), "0.0")
        self.assertEqual(growth.growth_party_ready_max_leader_distance(1, 4), "1800")
        self.assertEqual(growth.growth_party_ready_max_leader_distance(9, 8), "1800")
        self.assertEqual(growth.growth_party_ready_max_leader_distance(1, 2), "1800")
        self.assertEqual(growth.growth_party_pre_pull_home_stop_distance(1, 4), "1600")
        self.assertEqual(growth.growth_party_pre_pull_home_stop_distance(9, 8), "1600")
        self.assertEqual(growth.growth_party_pre_pull_home_stop_distance(1, 2), "1600")

    def test_growth_watcher_count_is_one_per_party(self) -> None:
        self.assertEqual(growth.watcher_count_for_party(SimpleNamespace(watch_movement=True), 1), 1)
        self.assertEqual(growth.watcher_count_for_party(SimpleNamespace(watch_movement=True), 8), 1)
        self.assertEqual(growth.watcher_count_for_party(SimpleNamespace(watch_movement=False), 8), 0)

    def test_watcher_character_name_contains_korean_marker(self) -> None:
        self.assertEqual(growth.watcher_character_name("growthalb701"), "\uac10\uc2dc\uc790GrowthAlb701")

    def test_inter_segment_delay_defaults_to_session_cooldown(self) -> None:
        args = growth.parse_args_for_tests(["--dry-run"])

        self.assertEqual(args.inter_segment_delay, 75.0)

    def test_growth_stage_defaults_define_ordered_growth_checkpoints(self) -> None:
        self.assertEqual(growth.growth_stage_for_level(1), "stabilize")
        self.assertEqual(growth.growth_stage_for_level(5), "train")
        self.assertEqual(growth.growth_stage_for_level(8), "gear")
        self.assertEqual(growth.growth_stage_for_level(40), "long")

    def test_growth_stage_argument_applies_checkpoint_defaults(self) -> None:
        args = growth.parse_args_for_tests(["--dry-run", "--growth-stage", "train"])

        self.assertEqual(args.reset_level, 5)
        self.assertEqual(args.max_level, 6)
        self.assertEqual(args.max_segments, 2)
        self.assertEqual(args.segment_seconds, 120)

    def test_explicit_level_bounds_override_growth_stage_defaults(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--growth-stage",
                "long",
                "--reset-level",
                "50",
                "--max-level",
                "51",
                "--segment-seconds",
                "420",
            ]
        )

        self.assertEqual(args.reset_level, 50)
        self.assertEqual(args.max_level, 51)
        self.assertEqual(args.segment_seconds, 420)

    def test_explicit_max_segments_overrides_growth_stage_defaults(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--growth-stage",
                "stabilize",
                "--checkpoint-levels",
                "1,4",
                "--max-segments",
                "2",
            ]
        )

        self.assertEqual(args.checkpoint_levels_parsed, [1, 4])
        self.assertEqual(args.max_segments, 2)

    def test_fast_balance_speed_profile_shortens_batch_collection_defaults(self) -> None:
        args = growth.parse_args_for_tests(
            ["--dry-run", "--growth-stage", "gear", "--growth-speed-profile", "fast-balance"]
        )

        self.assertEqual(args.segment_seconds, 180)
        self.assertEqual(args.startup_delay, 4.0)
        self.assertEqual(args.post_segment_snapshot_delay, 0.5)
        self.assertEqual(args.post_segment_snapshot_timeout, 15.0)
        self.assertEqual(args.post_segment_snapshot_poll_interval, 0.5)
        self.assertEqual(args.inter_segment_delay, 5.0)
        self.assertEqual(args.safe_exit_max_seconds, 25.0)
        self.assertEqual(args.safe_exit_recent_damage_grace, 5.0)
        self.assertFalse(args.watch_movement)
        self.assertFalse(args.live_supervisor)
        self.assertFalse(args.fail_on_regression)
        self.assertFalse(args.require_segment_kill)
        self.assertFalse(args.require_segment_xp)

    def test_route_home_fast_balance_preserves_safe_exit_recovery_defaults(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--growth-stage",
                "gear",
                "--growth-speed-profile",
                "fast-balance",
                "--growth-fast-travel",
                "route-home",
            ]
        )

        self.assertEqual(args.safe_exit_max_seconds, growth.GROWTH_SAFE_EXIT_MAX_SECONDS)
        self.assertEqual(args.safe_exit_recent_damage_grace, growth.GROWTH_SAFE_EXIT_RECENT_DAMAGE_GRACE)

    def test_fast_balance_speed_profile_preserves_explicit_timing_and_strictness(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--growth-stage",
                "gear",
                "--growth-speed-profile",
                "fast-balance",
                "--segment-seconds",
                "240",
                "--inter-segment-delay",
                "9",
                "--safe-exit-max-seconds",
                "40",
                "--safe-exit-recent-damage-grace",
                "8",
                "--watch-movement",
                "--live-supervisor",
                "--fail-on-regression",
                "--require-segment-kill",
                "--require-segment-xp",
            ]
        )

        self.assertEqual(args.segment_seconds, 240)
        self.assertEqual(args.inter_segment_delay, 9.0)
        self.assertEqual(args.safe_exit_max_seconds, 40.0)
        self.assertEqual(args.safe_exit_recent_damage_grace, 8.0)
        self.assertTrue(args.watch_movement)
        self.assertTrue(args.live_supervisor)
        self.assertTrue(args.fail_on_regression)
        self.assertTrue(args.require_segment_kill)
        self.assertTrue(args.require_segment_xp)

    def test_fast_balance_can_skip_startup_teleport_when_resuming_near_route_home(self) -> None:
        args = growth.parse_args_for_tests(
            ["--dry-run", "--growth-stage", "gear", "--growth-speed-profile", "fast-balance"]
        )
        args.growth_auto_equip_slots = []
        route = growth.select_growth_route_point(args, growth.REALMS["alb"], level=9, party_size=1)
        snapshot = growth.CharacterSnapshot(
            "growthalb1501",
            "GrowthAlb1501",
            "id",
            9,
            0,
            1,
            1,
            "Slash|9;Chants|9",
            growth.REALMS["alb"].region,
            route.x + 100,
            route.y + 100,
            route.z,
            0,
            0,
            0,
            0,
        )

        self.assertTrue(
            growth.should_skip_growth_startup_teleport_near_route_home(
                args,
                {"growthalb1501": snapshot},
                realm=growth.REALMS["alb"],
                route_level=9,
                current_level=9,
                party_size=1,
            )
        )
        self.assertFalse(
            growth.should_skip_growth_startup_teleport_near_route_home(
                args,
                {"growthalb1501": snapshot},
                realm=growth.REALMS["alb"],
                route_level=9,
                current_level=9,
                party_size=1,
                previous_segment_leveled=True,
            )
        )
        self.assertFalse(
            growth.should_skip_growth_startup_teleport_near_route_home(
                args,
                {"growthalb1501": snapshot},
                realm=growth.REALMS["alb"],
                route_level=9,
                current_level=9,
                party_size=1,
                planned_merchant_transaction=True,
            )
        )
        args.growth_auto_equip_slots = [43]
        self.assertFalse(
            growth.should_skip_growth_startup_teleport_near_route_home(
                args,
                {"growthalb1501": snapshot},
                realm=growth.REALMS["alb"],
                route_level=9,
                current_level=9,
                party_size=1,
            )
        )

    def test_low_level_teleport_route_uses_destination_as_flee_home(self) -> None:
        self.assertEqual(
            growth.growth_flee_home_string(growth.REALMS["alb"], 7, 1),
            "462144,633058,1739",
        )

    def test_hunting_index_route_without_teleporter_uses_route_as_flee_home(self) -> None:
        route = growth.route_point(
            6,
            331797,
            467208,
            5247,
            "eirebug",
            source="hunting-index",
            mob_level=5,
        )

        self.assertEqual(
            growth.growth_flee_home_string_for_route(growth.REALMS["hib"], route, ground_z_offset=0),
            "331797,467208,5248",
        )

    def test_checkpoint_levels_parse_as_ordered_short_live_probe(self) -> None:
        args = growth.parse_args_for_tests(["--dry-run", "--checkpoint-levels", "1,5,6,10,20,35,49"])

        self.assertEqual(args.checkpoint_levels_parsed, [1, 5, 6, 10, 20, 35, 49])
        self.assertEqual(args.max_segments, 7)
        self.assertEqual(args.inter_segment_delay, 0.0)

    def test_checkpoint_levels_run_one_segment_at_each_forced_level(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--checkpoint-levels",
                "1,5,10",
                "--realms",
                "alb",
                "--party-sizes",
                "1",
                "--no-watch-movement",
                "--no-fail-on-regression",
            ]
        )
        captured_levels: list[int] = []
        original_build_behavior_command = growth.build_behavior_command
        original_run_commands_concurrently = growth.run_commands_concurrently
        try:
            def fake_build_behavior_command(**kwargs):
                captured_levels.append(kwargs["current_level"])
                return ["behavior", str(kwargs["current_level"])]

            growth.build_behavior_command = fake_build_behavior_command
            growth.run_commands_concurrently = lambda _commands, _dry_run: 0

            with tempfile.TemporaryDirectory() as temp_dir:
                rc = growth.run_case(
                    args,
                    growth.REALMS["alb"],
                    party_size=1,
                    case_index=0,
                    output_dir=Path(temp_dir),
                    path_graph=Path(temp_dir) / "growth-route-graph.json",
                    timeline_csv=Path(temp_dir) / "timeline.csv",
                )
        finally:
            growth.build_behavior_command = original_build_behavior_command
            growth.run_commands_concurrently = original_run_commands_concurrently

        self.assertEqual(rc, 0)
        self.assertEqual(captured_levels, [1, 5, 10])

    def test_checkpoint_levels_reuse_same_accounts_for_player_growth_identity(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--checkpoint-levels",
                "6,10,15",
                "--realms",
                "alb",
                "--party-sizes",
                "1",
                "--no-watch-movement",
                "--no-fail-on-regression",
            ]
        )
        captured_accounts: list[list[str]] = []
        original_build_behavior_command = growth.build_behavior_command
        original_run_commands_concurrently = growth.run_commands_concurrently
        try:
            def fake_build_behavior_command(**kwargs):
                captured_accounts.append(
                    [row["username"] for row in growth.read_accounts(kwargs["accounts_csv"])]
                )
                return ["behavior", str(kwargs["current_level"])]

            growth.build_behavior_command = fake_build_behavior_command
            growth.run_commands_concurrently = lambda _commands, _dry_run: 0

            with tempfile.TemporaryDirectory() as temp_dir:
                rc = growth.run_case(
                    args,
                    growth.REALMS["alb"],
                    party_size=1,
                    case_index=0,
                    output_dir=Path(temp_dir),
                    path_graph=Path(temp_dir) / "growth-route-graph.json",
                    timeline_csv=Path(temp_dir) / "timeline.csv",
                )
        finally:
            growth.build_behavior_command = original_build_behavior_command
            growth.run_commands_concurrently = original_run_commands_concurrently

        self.assertEqual(rc, 0)
        self.assertEqual(captured_accounts, [["growthalb701"], ["growthalb701"], ["growthalb701"]])

    def test_checkpoint_route_home_with_watcher_writes_checkpoint_watcher_accounts(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--checkpoint-levels",
                "4",
                "--checkpoint-start-location",
                "route-home",
                "--realms",
                "mid",
                "--party-sizes",
                "2",
                "--no-fail-on-regression",
            ]
        )

        original_run_commands_concurrently = growth.run_commands_concurrently
        try:
            growth.run_commands_concurrently = lambda _commands, _dry_run: 0

            with tempfile.TemporaryDirectory() as temp_dir:
                output_dir = Path(temp_dir)
                rc = growth.run_case(
                    args,
                    growth.REALMS["mid"],
                    party_size=2,
                    case_index=0,
                    output_dir=output_dir,
                    path_graph=output_dir / "growth-route-graph.json",
                    timeline_csv=output_dir / "timeline.csv",
                )
                watcher_csv = output_dir / "mid-p2" / "watcher-accounts" / "watcher-accounts.csv"
                rows = growth.read_accounts(watcher_csv)
        finally:
            growth.run_commands_concurrently = original_run_commands_concurrently

        self.assertEqual(rc, 0)
        self.assertEqual([row["username"] for row in rows], ["growthmid703"])

    def test_fast_flee_debug_preset_shortens_live_repro_loop(self) -> None:
        args = growth.parse_args_for_tests(["--dry-run", "--growth-stage", "gear", "--realms", "hib", "--fast-flee-debug"])

        self.assertEqual(args.realms, "hib")
        self.assertEqual(args.party_sizes, "1")
        self.assertEqual(args.segment_seconds, 90)
        self.assertEqual(args.max_segments, 1)
        self.assertTrue(args.once)
        self.assertEqual(args.parallel_cases, 1)
        self.assertFalse(args.watch_movement)
        self.assertFalse(args.live_supervisor)
        self.assertFalse(args.require_segment_kill)
        self.assertEqual(args.post_segment_snapshot_delay, 0.0)
        self.assertEqual(args.post_segment_snapshot_timeout, 0.0)
        self.assertEqual(args.ramp_up, 2)
        self.assertEqual(args.startup_delay, 4.0)

    def test_fast_flee_debug_preserves_explicit_segment_seconds(self) -> None:
        args = growth.parse_args_for_tests(
            ["--dry-run", "--growth-stage", "gear", "--fast-flee-debug", "--segment-seconds", "180"]
        )

        self.assertEqual(args.segment_seconds, 180)

    def test_growth_suite_rejects_windows_runtime_for_live_runs(self) -> None:
        args = growth.parse_args_for_tests(["--growth-stage", "train"])

        with self.assertRaisesRegex(SystemExit, "Run dummy growth suites from WSL bash"):
            growth.validate_growth_suite_runtime(args, platform="win32")

    def test_growth_suite_allows_windows_runtime_for_dry_run(self) -> None:
        args = growth.parse_args_for_tests(["--dry-run", "--growth-stage", "train"])

        growth.validate_growth_suite_runtime(args, platform="win32")

    def test_growth_segment_regression_fails_on_no_progress_and_records_progress_deaths(self) -> None:
        self.assertFalse(
            growth.segment_regression_passed(
                {"player_deaths": 1, "target_removed": 0, "movement_failures": 0},
                require_kill=True,
            )
        )
        self.assertTrue(
            growth.segment_regression_passed(
                {"player_deaths": 1, "target_removed": 3, "movement_failures": 0},
                require_kill=True,
            )
        )
        self.assertFalse(
            growth.segment_regression_passed(
                {"player_deaths": 0, "target_removed": 0, "movement_failures": 0},
                require_kill=True,
            )
        )
        self.assertTrue(
            growth.segment_regression_passed(
                {"player_deaths": 0, "target_removed": 1, "movement_failures": 0},
                require_kill=True,
            )
        )
        self.assertTrue(
            growth.segment_regression_passed(
                {"player_deaths": 0, "target_removed": 1, "movement_failures": 12},
                require_kill=True,
            )
        )
        self.assertFalse(
            growth.segment_regression_passed(
                {"player_deaths": 0, "target_removed": 0, "movement_failures": 12},
                require_kill=True,
            )
        )

    def test_growth_segment_regression_fails_on_target_timeouts(self) -> None:
        self.assertFalse(
            growth.segment_regression_passed(
                {"player_deaths": 0, "target_removed": 1, "target_timeouts": 1, "movement_failures": 0},
                require_kill=True,
            )
        )

    def test_growth_segment_regression_fails_on_combat_failures(self) -> None:
        self.assertFalse(
            growth.segment_regression_passed(
                {
                    "player_deaths": 0,
                    "target_removed": 1,
                    "target_timeouts": 0,
                    "movement_failures": 0,
                    "combat_failures": 1,
                },
                require_kill=True,
            )
        )

    def test_growth_segment_regression_allows_recovered_server_los_retry(self) -> None:
        self.assertTrue(
            growth.segment_regression_passed(
                {
                    "player_deaths": 0,
                    "target_removed": 1,
                    "target_timeouts": 0,
                    "movement_failures": 0,
                    "combat_failures": 1,
                    "server_los_failures": 1,
                    "target_home_leashes": 0,
                },
                require_kill=True,
            )
        )

    def test_growth_segment_regression_allows_safe_leash_when_segment_has_kill(self) -> None:
        self.assertTrue(
            growth.segment_regression_passed(
                {
                    "player_deaths": 0,
                    "target_removed": 1,
                    "target_timeouts": 0,
                    "movement_failures": 0,
                    "combat_failures": 2,
                    "server_los_failures": 0,
                    "target_home_leashes": 2,
                },
                require_kill=True,
            )
        )

    def test_aggregate_combat_metrics_counts_server_los_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "combat.csv"
            path.write_text(
                "username,round,target_id,target_name,outcome\n"
                "growthhib,1,1,water beetle,server_los_failure\n"
                "growthhib,1,2,water beetle,target_removed\n",
                encoding="utf-8",
            )

            metrics = growth.aggregate_combat_metrics(path)

        self.assertEqual(metrics["combat_failures"], 1)
        self.assertEqual(metrics["server_los_failures"], 1)

    def test_aggregate_combat_metrics_treats_flee_as_measured_recovery_not_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "combat.csv"
            path.write_text(
                "username,round,target_id,target_name,outcome\n"
                "growthalb,1,1,giant spider,target_removed\n"
                "growthalb,1,2,giant spider,flee\n",
                encoding="utf-8",
            )

            metrics = growth.aggregate_combat_metrics(path)

        self.assertEqual(metrics["combat_failures"], 0)
        self.assertTrue(
            growth.segment_regression_passed(
                {
                    "player_deaths": 0,
                    "target_removed": 1,
                    "target_timeouts": 0,
                    "movement_failures": 0,
                    **metrics,
                },
                require_kill=True,
            )
        )

    def test_level_five_train_checkpoint_does_not_require_kill(self) -> None:
        args = SimpleNamespace(require_segment_kill=True)

        self.assertFalse(growth.segment_requires_kill(args, 5))
        self.assertTrue(growth.segment_requires_kill(args, 6))

    def test_route_home_growth_still_requires_kill_and_xp(self) -> None:
        args = SimpleNamespace(require_segment_kill=True, require_segment_xp=True, growth_fast_travel="route-home")

        self.assertTrue(growth.segment_requires_kill(args, 8))
        self.assertTrue(growth.segment_requires_xp(args, 8))

    def test_explicit_route_home_growth_can_require_kill_and_xp(self) -> None:
        args = SimpleNamespace(
            require_segment_kill=True,
            require_segment_xp=True,
            growth_fast_travel="route-home",
            explicit_options={"require_segment_kill", "require_segment_xp"},
        )

        self.assertTrue(growth.segment_requires_kill(args, 10))
        self.assertTrue(growth.segment_requires_xp(args, 10))

    def test_parse_args_tracks_explicit_route_home_growth_requirements(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--growth-fast-travel",
                "route-home",
                "--require-segment-kill",
                "--require-segment-xp",
            ]
        )

        self.assertIn("require_segment_kill", args.explicit_options)
        self.assertIn("require_segment_xp", args.explicit_options)
        self.assertTrue(growth.segment_requires_kill(args, 10))
        self.assertTrue(growth.segment_requires_xp(args, 10))

    def test_continuous_progression_forces_natural_party_and_single_session_defaults(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--continuous-progression",
                "--party-sizes",
                "4",
            ]
        )

        self.assertTrue(args.continuous_progression)
        self.assertEqual(args.reset_level, 1)
        self.assertEqual(args.growth_party_carry_count, 0)
        self.assertFalse(args.growth_start_base_classes)
        self.assertFalse(args.watch_movement)
        self.assertFalse(args.live_supervisor)
        self.assertEqual(args.growth_fast_travel, "route-home")
        self.assertTrue(args.continuous_dynamic_quests)

    def test_continuous_progression_rejects_forced_checkpoint_levels(self) -> None:
        with self.assertRaisesRegex(SystemExit, "cannot be combined"):
            growth.parse_args_for_tests(
                [
                    "--dry-run",
                    "--continuous-progression",
                    "--checkpoint-levels",
                    "1,5,10",
                ]
            )

    def test_continuous_service_point_uses_exact_live_npc_match(self) -> None:
        args = SimpleNamespace(
            dry_run=False,
            nav_api_url="http://dummy-api:5000",
            host="127.0.0.1",
            api_port=5000,
            continuous_api_timeout=2.0,
        )
        payload = [
            {"name": "Auda", "region": 100, "x": 1, "y": 2, "z": 3, "objectId": 1},
            {
                "name": "Aud",
                "region": 100,
                "x": 774764,
                "y": 757457,
                "z": 4639,
                "objectId": 3220,
            },
        ]

        with mock.patch.object(
            growth,
            "fetch_growth_route_preflight_payload",
            return_value=payload,
        ) as fetch:
            point = growth.resolve_continuous_service_point(args, growth.REALMS["mid"])

        self.assertEqual((point.x, point.y, point.z), (774764, 757457, 4639))
        self.assertEqual(point.source, "live-service-npc")
        self.assertTrue(point.live_anchor_z)
        self.assertIn("name=Aud", fetch.call_args.args[0])

    def test_continuous_service_point_fails_before_login_when_npc_is_missing(self) -> None:
        args = SimpleNamespace(
            dry_run=False,
            nav_api_url="http://dummy-api:5000",
            host="127.0.0.1",
            api_port=5000,
            continuous_api_timeout=2.0,
        )

        with mock.patch.object(
            growth,
            "fetch_growth_route_preflight_payload",
            return_value=[],
        ):
            with self.assertRaisesRegex(RuntimeError, "continuous service NPC not found"):
                growth.resolve_continuous_service_point(args, growth.REALMS["alb"])

    def test_continuous_api_password_falls_back_to_server_property_without_logging_it(self) -> None:
        args = SimpleNamespace(continuous_api_password="", dry_run=False)

        with mock.patch.object(
            growth,
            "run_mysql",
            return_value="Value\nlocal-secret\n",
        ):
            growth.resolve_continuous_api_password(args)

        self.assertEqual(args.continuous_api_password, "local-secret")

    def test_continuous_case_starts_at_live_service_and_preserves_level_zero_hunt_band(self) -> None:
        service_point = growth.RoutePoint(
            level=0,
            x=518933,
            y=494112,
            z=3352,
            source="live-service-npc",
            live_anchor_z=True,
        )
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            args = growth.parse_args_for_tests(
                [
                    "--dry-run",
                    "--continuous-progression",
                    "--realms",
                    "alb",
                    "--party-sizes",
                    "1",
                ]
            )
            with mock.patch.object(
                growth,
                "resolve_continuous_service_point",
                return_value=service_point,
            ):
                rc = growth.run_continuous_case(
                    args,
                    growth.REALMS["alb"],
                    1,
                    0,
                    output_dir,
                    output_dir / "graph.json",
                    output_dir / "timeline.csv",
                )

            case_dir = output_dir / "alb-p1"
            metadata = json.loads(
                (case_dir / "continuous-command.json").read_text(encoding="utf-8")
            )
            command = metadata["behaviorCommand"]
            account = growth.read_accounts(case_dir / "primary-accounts.csv")[0]

        self.assertEqual(rc, 0)
        self.assertEqual(growth.command_option_value(command, "--ideal-target-level"), "0")
        self.assertEqual(growth.command_option_value(command, "--min-target-level"), "0")
        self.assertEqual(growth.command_option_value(command, "--max-target-level"), "1")
        self.assertIn("--no-force-nav-target-routes", command)
        self.assertNotIn("--dynamic-quest-observe-final-progress", command)
        self.assertIn("--no-dynamic-quest-final-validation", command)
        self.assertEqual(
            growth.command_option_value(command, "--dynamic-quest-return-home"),
            "518933,494112,3352",
        )
        self.assertEqual(
            (account["start_x"], account["start_y"], account["start_z"]),
            ("518933", "494112", "3352"),
        )
        self.assertEqual(metadata["servicePoint"]["source"], "live-service-npc")

    def test_continuous_mercenary_requires_solo_owner_and_disables_model_service_flags(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--continuous-progression",
                "--continuous-mercenary",
                "--party-sizes",
                "1",
            ]
        )
        service_command = growth.build_continuous_mercenary_service_command(
            args,
            accounts_csv=Path("mercenary.csv"),
            run_directory=Path("service"),
            max_runtime_seconds=600,
        )

        self.assertTrue(args.continuous_mercenary)
        self.assertEqual(args.continuous_mercenary_contract_tier, "legendary")
        self.assertNotIn("--dialogue-enabled", service_command)
        self.assertNotIn("--ai-gateway-model-alias", service_command)
        self.assertEqual(
            growth.command_option_value(service_command, "--nav-api-url"),
            growth.continuous_progression_api_base(args),
        )
        self.assertIn("--no-force-nav-target-routes", service_command)
        self.assertEqual(
            growth.command_option_value(service_command, "--party-size"),
            "2",
        )

    def test_continuous_mercenary_keeps_owner_concurrency_separate_from_party_size(self) -> None:
        service_point = growth.RoutePoint(
            level=0,
            x=518933,
            y=494112,
            z=3352,
            source="live-service-npc",
            live_anchor_z=True,
        )
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            args = growth.parse_args_for_tests(
                [
                    "--dry-run",
                    "--continuous-progression",
                    "--continuous-mercenary",
                    "--realms",
                    "alb",
                    "--party-sizes",
                    "1",
                ]
            )
            with mock.patch.object(
                growth,
                "resolve_continuous_service_point",
                return_value=service_point,
            ):
                rc = growth.run_continuous_case(
                    args,
                    growth.REALMS["alb"],
                    1,
                    0,
                    output_dir,
                    output_dir / "graph.json",
                    output_dir / "timeline.csv",
                )
            metadata = json.loads(
                (
                    output_dir
                    / "alb-p1-mercenary"
                    / "continuous-command.json"
                ).read_text(encoding="utf-8")
            )
            command = metadata["behaviorCommand"]

        self.assertEqual(rc, 0)
        self.assertEqual(growth.command_option_value(command, "--concurrency"), "1")
        self.assertEqual(growth.command_option_value(command, "--party-size"), "2")

    def test_continuous_mercenary_rejects_natural_party_size(self) -> None:
        with self.assertRaisesRegex(SystemExit, "requires --party-sizes 1"):
            growth.parse_args_for_tests(
                [
                    "--dry-run",
                    "--continuous-progression",
                    "--continuous-mercenary",
                    "--party-sizes",
                    "2",
                ]
            )

    def test_continuous_summary_merges_case_timelines_and_quest_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = root / "alb-p1"
            case.mkdir()
            (case / "continuous-timeline.csv").write_text(
                "case,account,level_service_end\nalb-p1,growthalb001,2\n",
                encoding="utf-8",
            )
            (case / "dynamic-quest-timeline.csv").write_text(
                "case,outcome\nalb-p1,difficulty_skip\nalb-p1,completed\n",
                encoding="utf-8",
            )
            (case / "mercenary-timeline.csv").write_text(
                "case,outcome,level_delta\nalb-p1,requested,0\nalb-p1,active,1\n",
                encoding="utf-8",
            )
            (case / "continuous-result.json").write_text(
                json.dumps(
                    {
                        "ok": True,
                        "completed_level": 2,
                        "checkpoints": 1,
                        "anomalies": [],
                        "error": "",
                    }
                ),
                encoding="utf-8",
            )

            growth.write_continuous_run_summary(root)

            summary = (root / "continuous-summary.md").read_text(encoding="utf-8")

        self.assertIn("difficulty_skip: `1`", summary)
        self.assertIn("completed: `1`", summary)
        self.assertIn("active: `1`", summary)
        self.assertIn("Maximum owner/mercenary level delta: `1`", summary)

    def test_growth_segment_xp_regression_fails_when_required_xp_is_zero(self) -> None:
        self.assertFalse(growth.segment_xp_regression_passed(0, require_xp=True))
        self.assertTrue(growth.segment_xp_regression_passed(1, require_xp=True))
        self.assertTrue(growth.segment_xp_regression_passed(0, require_xp=False))

    def test_growth_segment_account_xp_regression_requires_each_account(self) -> None:
        self.assertFalse(
            growth.segment_account_xp_regression_passed(
                {"growthmid001": 50, "growthmid002": 0},
                require_xp=True,
            )
        )
        self.assertTrue(
            growth.segment_account_xp_regression_passed(
                {"growthmid001": 50, "growthmid002": 50},
                require_xp=True,
            )
        )
        self.assertTrue(
            growth.segment_account_xp_regression_passed(
                {"growthmid001": 0},
                require_xp=False,
            )
        )

    def test_train_and_max_level_checkpoints_do_not_require_xp_progress(self) -> None:
        args = SimpleNamespace(require_segment_xp=True, max_level=50)

        self.assertFalse(growth.segment_requires_xp(args, 5))
        self.assertTrue(growth.segment_requires_xp(args, 10))
        self.assertFalse(growth.segment_requires_xp(args, 50))

    def test_merchant_buy_or_sell_segment_can_skip_xp_requirement(self) -> None:
        self.assertFalse(growth.growth_item_plans_have_merchant_transaction({}))
        self.assertFalse(
            growth.growth_item_plans_have_merchant_transaction(
                {"growthalb": growth.GrowthItemPlan(equip_slots=[40], sell_slots=[])}
            )
        )
        self.assertTrue(
            growth.growth_item_plans_have_merchant_transaction(
                {"growthalb": growth.GrowthItemPlan(equip_slots=[], sell_slots=[40])}
            )
        )
        self.assertTrue(
            growth.growth_item_plans_have_merchant_transaction(
                {"growthalb": growth.GrowthItemPlan(equip_slots=[], sell_slots=[], buy_slots=[18])}
            )
        )
        self.assertTrue(growth.segment_regression_passed({"target_removed": 0}, require_kill=False))

    def test_sell_only_solo_plan_is_executable_merchant_transaction(self) -> None:
        item_plans = {
            "growthalb": growth.GrowthItemPlan(
                equip_slots=[],
                sell_slots=[42, 48],
                merchant_npc_name="Leshorm Hael",
                buy_reason="sell_only:no_safe_upgrade",
            )
        }

        self.assertTrue(
            growth.growth_item_plans_have_executable_merchant_transaction(
                item_plans,
                party_size=1,
                planned_party_merchant_maps=False,
            )
        )

    def test_sell_only_party_plan_requires_party_merchant_map(self) -> None:
        item_plans = {
            "growthalb701": growth.GrowthItemPlan(
                equip_slots=[],
                sell_slots=[42],
                merchant_npc_name="Leshorm Hael",
            )
        }

        self.assertFalse(
            growth.growth_item_plans_have_executable_merchant_transaction(
                item_plans,
                party_size=4,
                planned_party_merchant_maps=False,
            )
        )
        self.assertTrue(
            growth.growth_item_plans_have_executable_merchant_transaction(
                item_plans,
                party_size=4,
                planned_party_merchant_maps=True,
            )
        )

    def test_planned_merchant_execution_requires_merchant_action_seen(self) -> None:
        metrics = growth.empty_metric_summary()

        self.assertTrue(
            growth.growth_merchant_transaction_regression_passed(
                metrics,
                planned_merchant_execution=False,
            )
        )
        self.assertFalse(
            growth.growth_merchant_transaction_regression_passed(
                metrics,
                planned_merchant_execution=True,
            )
        )

        metrics["startup_merchant_sell"] = 1
        self.assertTrue(
            growth.growth_merchant_transaction_regression_passed(
                metrics,
                planned_merchant_execution=True,
            )
        )

    def test_failure_reproduction_command_pins_case_level_and_start(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            api_port=5000,
            nav_api_url="http://127.0.0.1:5000",
            db_host="127.0.0.1",
            db_port=3306,
            db_name="opendaoc",
            db_user="root",
            db_password="secret",
            template_account="dummy040",
            template_character="Dummy040",
            password="dummy-pass",
            segment_seconds=90,
            start=700,
            start_stride=20,
            run_dir=Path("run"),
            growth_stage="custom",
        )

        command = growth.build_failure_reproduction_command(
            args,
            realm=growth.REALMS["hib"],
            party_size=8,
            case_index=2,
            current_level=3,
            output_dir=Path("run"),
        )

        self.assertIn("--realms hib", command)
        self.assertIn("--party-sizes 8", command)
        self.assertIn("--start 740", command)
        self.assertIn("--reset-level 3", command)
        self.assertIn("--max-level 4", command)
        self.assertIn("--parallel-cases 1", command)
        self.assertIn("failure-repro-hib-p8-l3", command)

    def test_parse_slot_list_accepts_ranges(self) -> None:
        self.assertEqual(growth.parse_slot_list("40-42,45"), [40, 41, 42, 45])

    def test_class_allows_item_accepts_empty_zero_and_lists(self) -> None:
        self.assertTrue(growth.class_allows_item("", 11))
        self.assertTrue(growth.class_allows_item("0", 11))
        self.assertTrue(growth.class_allows_item("1;11;13", 11))
        self.assertTrue(growth.class_allows_item("1,11,13", 11))
        self.assertFalse(growth.class_allows_item("1;13", 11))

    def test_growth_equipment_plan_equips_only_better_allowed_backpack_items(self) -> None:
        items = [
            growth.InventoryItem(
                account="growthalb701",
                slot=10,
                template_id="old_armor",
                name="Old Armor",
                level=1,
                dps_af=12,
                spd_abs=30,
                object_type=31,
                item_type=25,
                quality=90,
                bonus=0,
                allowed_classes="11",
                count=1,
                sell_price=0,
            ),
            growth.InventoryItem(
                account="growthalb701",
                slot=40,
                template_id="new_armor",
                name="New Armor",
                level=3,
                dps_af=24,
                spd_abs=30,
                object_type=31,
                item_type=25,
                quality=94,
                bonus=2,
                allowed_classes="11",
                count=1,
                sell_price=10,
            ),
            growth.InventoryItem(
                account="growthalb701",
                slot=41,
                template_id="wrong_class_staff",
                name="Wrong Class Staff",
                level=3,
                dps_af=80,
                spd_abs=40,
                object_type=8,
                item_type=12,
                quality=100,
                bonus=10,
                allowed_classes="7",
                count=1,
                sell_price=10,
            ),
        ]

        plan = growth.build_growth_item_plan(items, class_id=11, level=5)

        self.assertEqual(plan.equip_slots, [40])
        self.assertEqual(plan.sell_slots, [41])

    def test_growth_equipment_plan_holds_worse_zero_value_armor(self) -> None:
        items = [
            growth.InventoryItem(
                account="growthmid50121",
                slot=11,
                template_id="small_training_shield",
                name="small training shield",
                level=2,
                dps_af=10,
                spd_abs=0,
                object_type=42,
                item_type=11,
                quality=100,
                bonus=0,
                allowed_classes="11",
                count=1,
                sell_price=0,
            ),
            growth.InventoryItem(
                account="growthmid50121",
                slot=40,
                template_id="rowan_round_shield",
                name="rowan round shield",
                level=2,
                dps_af=10,
                spd_abs=0,
                object_type=42,
                item_type=11,
                quality=85,
                bonus=0,
                allowed_classes="11",
                count=1,
                sell_price=0,
            ),
        ]

        plan = growth.build_growth_item_plan(items, class_id=11, level=8)

        self.assertEqual(plan.equip_slots, [])
        self.assertEqual(plan.sell_slots, [])
        self.assertIn("worse_zero_value_hold", plan.sell_reason)

    def test_growth_item_plan_sells_sellable_junk_and_keeps_zero_value_junk(self) -> None:
        items = [
            growth.InventoryItem(
                account="growthalb701",
                slot=40,
                template_id="rat_tail",
                name="Rat Tail",
                level=1,
                dps_af=0,
                spd_abs=0,
                object_type=0,
                item_type=0,
                quality=0,
                bonus=0,
                allowed_classes="",
                count=1,
                sell_price=3,
            ),
            growth.InventoryItem(
                account="growthalb701",
                slot=41,
                template_id="broken_claw",
                name="Broken Claw",
                level=1,
                dps_af=0,
                spd_abs=0,
                object_type=0,
                item_type=0,
                quality=0,
                bonus=0,
                allowed_classes="",
                count=1,
                sell_price=0,
            ),
        ]

        plan = growth.build_growth_item_plan(items, class_id=11, level=5)

        self.assertEqual(plan.equip_slots, [])
        self.assertEqual(plan.sell_slots, [40])
        self.assertIn("junk", plan.sell_reason)

    def test_growth_equipment_plan_equips_safe_matching_weapon_drop(self) -> None:
        items = [
            growth.InventoryItem(
                account="growthalb701",
                slot=10,
                template_id="old_sword",
                name="Old Sword",
                level=1,
                dps_af=12,
                spd_abs=30,
                object_type=3,
                item_type=10,
                quality=90,
                bonus=0,
                allowed_classes="11",
                count=1,
                sell_price=0,
            ),
            growth.InventoryItem(
                account="growthalb701",
                slot=40,
                template_id="short_bow",
                name="Short Bow",
                level=3,
                dps_af=40,
                spd_abs=30,
                object_type=18,
                item_type=12,
                quality=100,
                bonus=5,
                allowed_classes="11",
                count=1,
                sell_price=10,
            ),
        ]

        plan = growth.build_growth_item_plan(items, class_id=11, level=5)

        self.assertEqual(plan.equip_slots, [40])
        self.assertEqual(plan.sell_slots, [])
        self.assertIn("40->12", plan.equip_reason)

    def test_growth_equipment_plan_sells_weapon_without_required_ability(self) -> None:
        items = [
            growth.InventoryItem(
                account="growthalb701",
                slot=10,
                template_id="old_sword",
                name="Old Sword",
                level=1,
                dps_af=12,
                spd_abs=30,
                object_type=3,
                item_type=10,
                quality=90,
                bonus=0,
                allowed_classes="11",
                count=1,
                sell_price=0,
            ),
            growth.InventoryItem(
                account="growthalb701",
                slot=40,
                template_id="rowan_hunting_bow",
                name="rowan hunting bow",
                level=5,
                dps_af=40,
                spd_abs=30,
                object_type=9,
                item_type=13,
                quality=85,
                bonus=0,
                allowed_classes="11",
                count=1,
                sell_price=10,
            ),
        ]

        plan = growth.build_growth_item_plan(
            items,
            class_id=11,
            level=5,
            realm_id=1,
            serialized_abilities="Sprint|0;AlbArmor|3;Shield|1;Weaponry: Slashing|1",
        )

        self.assertEqual(plan.equip_slots, [])
        self.assertEqual(plan.sell_slots, [40])
        self.assertIn("equipment_ability", plan.sell_reason)

    def test_growth_equipment_plan_uses_weapon_when_required_ability_exists(self) -> None:
        items = [
            growth.InventoryItem(
                account="growthalb701",
                slot=10,
                template_id="old_sword",
                name="Old Sword",
                level=1,
                dps_af=12,
                spd_abs=30,
                object_type=3,
                item_type=10,
                quality=90,
                bonus=0,
                allowed_classes="11",
                count=1,
                sell_price=0,
            ),
            growth.InventoryItem(
                account="growthalb701",
                slot=40,
                template_id="new_sword",
                name="New Sword",
                level=5,
                dps_af=40,
                spd_abs=30,
                object_type=3,
                item_type=10,
                quality=100,
                bonus=5,
                allowed_classes="11",
                count=1,
                sell_price=10,
            ),
        ]

        plan = growth.build_growth_item_plan(
            items,
            class_id=11,
            level=5,
            realm_id=1,
            serialized_abilities="Sprint|0;AlbArmor|3;Shield|1;Weaponry: Slashing|1",
        )

        self.assertEqual(plan.equip_slots, [40])
        self.assertEqual(plan.sell_slots, [])

    def test_growth_equipment_plan_sells_shield_above_ability_size(self) -> None:
        items = [
            growth.InventoryItem(
                account="growthalb701",
                slot=11,
                template_id="small_training_shield",
                name="small training shield",
                level=2,
                dps_af=10,
                spd_abs=0,
                object_type=42,
                item_type=11,
                quality=100,
                bonus=0,
                allowed_classes="11",
                count=1,
                sell_price=0,
                realm=1,
                type_damage=1,
            ),
            growth.InventoryItem(
                account="growthalb701",
                slot=40,
                template_id="large_shield",
                name="large shield",
                level=3,
                dps_af=30,
                spd_abs=0,
                object_type=42,
                item_type=11,
                quality=95,
                bonus=5,
                allowed_classes="11",
                count=1,
                sell_price=10,
                realm=1,
                type_damage=3,
            ),
        ]

        plan = growth.build_growth_item_plan(
            items,
            class_id=11,
            level=5,
            realm_id=1,
            serialized_abilities="Sprint|0;AlbArmor|3;Shield|1;Weaponry: Slashing|1",
        )

        self.assertEqual(plan.equip_slots, [])
        self.assertEqual(plan.sell_slots, [40])
        self.assertIn("equipment_ability", plan.sell_reason)

    def test_growth_equipment_plan_sells_offhand_weapon_without_dual_wield(self) -> None:
        items = [
            growth.InventoryItem(
                account="growthalb701",
                slot=11,
                template_id="small_training_shield",
                name="small training shield",
                level=2,
                dps_af=12,
                spd_abs=40,
                object_type=42,
                item_type=11,
                quality=100,
                bonus=0,
                allowed_classes="0",
                count=1,
                sell_price=0,
                realm=1,
            ),
            growth.InventoryItem(
                account="growthalb701",
                slot=40,
                template_id="bronze_dirk",
                name="bronze dirk",
                level=1,
                dps_af=15,
                spd_abs=28,
                object_type=3,
                item_type=11,
                quality=85,
                bonus=0,
                allowed_classes="0",
                count=1,
                sell_price=73,
                realm=1,
            ),
        ]

        plan = growth.build_growth_item_plan(
            items,
            class_id=1,
            level=7,
            realm_id=1,
            serialized_abilities="Sprint|0;Shield|2;AlbArmor|3;Weaponry: Slashing|0",
        )

        self.assertEqual(plan.equip_slots, [])
        self.assertEqual(plan.sell_slots, [40])
        self.assertIn("offhand_ability", plan.sell_reason)

    def test_growth_equipment_plan_sells_weapon_that_does_not_match_trained_spec(self) -> None:
        items = [
            growth.InventoryItem(
                account="growthmid60121",
                slot=10,
                template_id="bronze_battle_hammer",
                name="bronze battle hammer",
                level=5,
                dps_af=27,
                spd_abs=41,
                object_type=12,
                item_type=10,
                quality=85,
                bonus=0,
                allowed_classes="0",
                count=1,
                sell_price=303,
                realm=2,
            ),
            growth.InventoryItem(
                account="growthmid60121",
                slot=40,
                template_id="bronze_shod_staff",
                name="bronze shod staff",
                level=3,
                dps_af=21,
                spd_abs=45,
                object_type=8,
                item_type=12,
                quality=85,
                bonus=0,
                allowed_classes="0",
                count=1,
                sell_price=137,
                realm=2,
            ),
        ]

        plan = growth.build_growth_item_plan(
            items,
            class_id=22,
            level=9,
            realm_id=2,
            serialized_abilities="Sprint|0;Shield|2;MidArmor|3;Weaponry: Hammers|0;Weaponry: Staves|0",
            specs="Hammer|9;Sword|1;Axe|1;Thrown Weapons|1;Shields|7",
        )

        self.assertEqual(plan.equip_slots, [])
        self.assertEqual(plan.sell_slots, [40])
        self.assertIn("weapon_spec", plan.sell_reason)

    def test_growth_equipment_plan_rejects_too_high_level_upgrade(self) -> None:
        items = [
            growth.InventoryItem(
                account="growthalb701",
                slot=10,
                template_id="old_sword",
                name="Old Sword",
                level=1,
                dps_af=12,
                spd_abs=30,
                object_type=3,
                item_type=10,
                quality=90,
                bonus=0,
                allowed_classes="11",
                count=1,
                sell_price=0,
            ),
            growth.InventoryItem(
                account="growthalb701",
                slot=40,
                template_id="future_sword",
                name="Future Sword",
                level=20,
                dps_af=80,
                spd_abs=30,
                object_type=3,
                item_type=10,
                quality=100,
                bonus=10,
                allowed_classes="11",
                count=1,
                sell_price=10,
            ),
        ]

        plan = growth.build_growth_item_plan(items, class_id=11, level=5)

        self.assertEqual(plan.equip_slots, [])
        self.assertEqual(plan.sell_slots, [])

    def test_party_share_plan_holds_item_that_upgrades_party_member(self) -> None:
        snapshots = {
            "growthalb701": growth.CharacterSnapshot(
                "growthalb701", "GrowthAlb701", "id1", 5, 0, 1, 11, "Slash|5", 1, 0, 0, 0, 0, 0, 1, 1
            ),
            "growthalb702": growth.CharacterSnapshot(
                "growthalb702", "GrowthAlb702", "id2", 5, 0, 1, 7, "Staff|5", 1, 0, 0, 0, 0, 0, 1, 1
            ),
        }
        inventory_by_account = {
            "growthalb701": [
                growth.InventoryItem(
                    account="growthalb701",
                    slot=40,
                    template_id="staff_drop",
                    name="Staff Drop",
                    level=4,
                    dps_af=55,
                    spd_abs=40,
                    object_type=8,
                    item_type=10,
                    quality=100,
                    bonus=5,
                    allowed_classes="7",
                    count=1,
                    sell_price=100,
                    realm=1,
                )
            ],
            "growthalb702": [
                growth.InventoryItem(
                    account="growthalb702",
                    slot=10,
                    template_id="old_staff",
                    name="Old Staff",
                    level=1,
                    dps_af=10,
                    spd_abs=40,
                    object_type=8,
                    item_type=10,
                    quality=80,
                    bonus=0,
                    allowed_classes="7",
                    count=1,
                    sell_price=0,
                    realm=1,
                )
            ],
        }
        plans = {
            "growthalb701": growth.build_growth_item_plan(
                inventory_by_account["growthalb701"],
                class_id=11,
                level=5,
                realm_id=1,
            ),
            "growthalb702": growth.build_growth_item_plan(
                inventory_by_account["growthalb702"],
                class_id=7,
                level=5,
                realm_id=1,
            ),
        }

        updated = growth.apply_party_share_growth_item_plans(
            inventory_by_account,
            snapshots,
            plans,
            realm_id=1,
        )

        self.assertEqual(updated["growthalb701"].party_share_slots, [40])
        self.assertEqual(updated["growthalb701"].sell_slots, [])
        self.assertIn("growthalb702", updated["growthalb701"].party_share_reason)
        self.assertEqual(len(updated["growthalb701"].party_share_transfers), 1)
        transfer = updated["growthalb701"].party_share_transfers[0]
        self.assertEqual(transfer.source_slot, 40)
        self.assertEqual(transfer.target_account, "growthalb702")
        self.assertEqual(transfer.target_slot, 40)
        self.assertEqual(transfer.target_equip_slot, 10)

    def test_party_share_execution_moves_existing_drop_and_targets_receiver_equip(self) -> None:
        snapshots = {
            "growthalb701": growth.CharacterSnapshot(
                "growthalb701", "GrowthAlb701", "id1", 5, 0, 1, 11, "Slash|5", 1, 0, 0, 0, 0, 0, 1, 1
            ),
            "growthalb702": growth.CharacterSnapshot(
                "growthalb702", "GrowthAlb702", "id2", 5, 0, 1, 7, "Staff|5", 1, 0, 0, 0, 0, 0, 1, 1
            ),
        }
        transfer = growth.GrowthPartyShareTransfer(
            source_account="growthalb701",
            source_slot=40,
            target_account="growthalb702",
            target_slot=41,
            target_equip_slot=10,
            item_name="Staff Drop",
            candidate_score=100,
            equipped_score=10,
        )
        plans = {
            "growthalb701": growth.GrowthItemPlan(
                equip_slots=[],
                sell_slots=[],
                party_share_slots=[40],
                party_share_transfers=[transfer],
            ),
            "growthalb702": growth.GrowthItemPlan(
                equip_slots=[],
                sell_slots=[],
                buy_slots=[5],
                buy_inventory_slots=[41],
                buy_reason="5:Merchant Staff:merchant=Alburn Hale:target_slot=10:price=50",
                buy_shortage_copper=0,
            ),
        }
        captured_sql: list[str] = []

        def fake_run_mysql(_args, sql):
            captured_sql.append(sql)
            return ""

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(growth, "run_mysql", fake_run_mysql):
            updated = growth.execute_growth_party_share_transfers(
                SimpleNamespace(dry_run=False),
                plans,
                snapshots,
                Path(temp_dir) / "party-share.csv",
            )

        self.assertIn("UPDATE inventory", captured_sql[0])
        self.assertIn("OwnerID = 'id2'", captured_sql[0])
        self.assertIn("SlotPosition = 41", captured_sql[0])
        self.assertIn("OwnerID = 'id1'", captured_sql[0])
        self.assertEqual(updated["growthalb701"].party_share_slots, [])
        self.assertEqual(updated["growthalb701"].party_share_executed_slots, [40])
        self.assertEqual(updated["growthalb702"].equip_slots, [41])
        self.assertEqual(updated["growthalb702"].party_share_received_slots, [41])
        self.assertEqual(updated["growthalb702"].buy_slots, [])
        self.assertEqual(updated["growthalb702"].buy_inventory_slots, [])
        self.assertEqual(growth.growth_party_share_status(updated["growthalb701"]), "executed_db_transfer")

    def test_metrics_by_account_records_random_loot_tiers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metrics_path = Path(temp_dir) / "segment-001-metrics.csv"
            with metrics_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "username",
                        "ok",
                        "elapsed_seconds",
                        "actions",
                        "combat_engagements",
                        "target_removed",
                        "player_deaths",
                        "target_timeouts",
                        "movement_failures",
                        "loot_acquired",
                        "damage_done",
                        "damage_taken",
                        "healing_done",
                        "healing_received",
                        "action_loot_tier_일반",
                        "action_loot_tier_마력",
                        "action_loot_tier_희귀",
                        "action_startup_service_dialog_settle",
                        "action_startup_service_equip",
                        "action_startup_merchant_sell",
                        "action_startup_merchant_buy",
                        "action_startup_merchant_equip",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "growthalb701",
                        "ok": "true",
                        "elapsed_seconds": "10",
                        "actions": "1",
                        "combat_engagements": "1",
                        "target_removed": "1",
                        "player_deaths": "0",
                        "target_timeouts": "0",
                        "movement_failures": "0",
                        "loot_acquired": "3",
                        "damage_done": "123",
                        "damage_taken": "45",
                        "healing_done": "67",
                        "healing_received": "8",
                        "action_loot_tier_일반": "1",
                        "action_loot_tier_마력": "1",
                        "action_loot_tier_희귀": "1",
                        "action_startup_service_dialog_settle": "1",
                        "action_startup_service_equip": "2",
                        "action_startup_merchant_sell": "3",
                        "action_startup_merchant_buy": "4",
                        "action_startup_merchant_equip": "5",
                    }
                )

            account_metrics = growth.metrics_by_account(metrics_path)["growthalb701"]
            aggregate = growth.aggregate_metrics(metrics_path)

        self.assertEqual(account_metrics["loot_tier_common"], 1)
        self.assertEqual(account_metrics["loot_tier_magic"], 1)
        self.assertEqual(account_metrics["loot_tier_rare"], 1)
        self.assertEqual(account_metrics["random_loot_total"], 3)
        self.assertEqual(account_metrics["startup_service_dialog_settle"], 1)
        self.assertEqual(account_metrics["startup_service_equip"], 2)
        self.assertEqual(account_metrics["startup_merchant_sell"], 3)
        self.assertEqual(account_metrics["startup_merchant_buy"], 4)
        self.assertEqual(account_metrics["startup_merchant_equip"], 5)
        self.assertEqual(aggregate["damage_done"], 123)
        self.assertEqual(aggregate["damage_taken"], 45)
        self.assertEqual(aggregate["healing_done"], 67)
        self.assertEqual(aggregate["healing_received"], 8)
        self.assertEqual(aggregate["random_loot_total"], 3)
        self.assertEqual(aggregate["startup_service_dialog_settle"], 1)
        self.assertEqual(aggregate["startup_service_equip"], 2)
        self.assertEqual(aggregate["startup_merchant_sell"], 3)
        self.assertEqual(aggregate["startup_merchant_buy"], 4)
        self.assertEqual(aggregate["startup_merchant_equip"], 5)

    def test_growth_item_economy_status_records_pending_party_and_zero_value_junk(self) -> None:
        plan = growth.GrowthItemPlan(
            equip_slots=[],
            sell_slots=[40],
            party_share_slots=[41],
            buy_reason="party_merchant_routing_pending",
            buy_shortage_copper=75,
        )
        metrics = growth.empty_metric_summary()

        flags = growth.growth_data_integrity_flags(
            SimpleNamespace(no_starter_equipment=False),
            plan,
            party_size=2,
            promoted_count=1,
            equipped_growth_party_carry_gear=True,
            equipped_growth_checkpoint_gear=True,
            equipped_level50_party_gear=False,
        )
        bottleneck = growth.growth_bottleneck_reason(
            plan,
            {
                "zero_value_junk_items_after": 2,
                "sellable_junk_value_copper_after": 0,
            },
            metrics,
            party_size=2,
            xp_effective_delta=0,
            effective_death_delta=0,
            planned_merchant_transaction=False,
        )

        self.assertEqual(growth.growth_party_share_status(plan), "pending_hold_not_traded")
        self.assertEqual(
            growth.growth_merchant_transaction_status(plan, metrics, party_size=2),
            "shortage",
        )
        self.assertIn("party_share_pending_hold", flags)
        self.assertIn("party_merchant_pending", flags)
        self.assertIn("injected_carry_gear", flags)
        self.assertIn("injected_checkpoint_gear", flags)
        self.assertIn("gear_money_shortage_zero_value_junk", bottleneck)
        self.assertIn("party_share_pending", bottleneck)
        self.assertIn("party_merchant_pending", bottleneck)

    def test_growth_bottleneck_records_untracked_combat_pressure(self) -> None:
        plan = growth.GrowthItemPlan(equip_slots=[], sell_slots=[])
        metrics = growth.empty_metric_summary()
        metrics["combat_engagements"] = 0
        metrics["target_removed"] = 0
        metrics["damage_done"] = 23
        metrics["damage_taken"] = 88
        metrics["action_attack_off"] = 38

        bottleneck = growth.growth_bottleneck_reason(
            plan,
            {},
            metrics,
            party_size=1,
            xp_effective_delta=0,
            effective_death_delta=0,
            planned_merchant_transaction=False,
        )

        self.assertIn("combat_pressure_no_kill", bottleneck)
        self.assertNotIn("no_engagement", bottleneck)

    def test_growth_bottleneck_records_no_reward_target_removed_as_xp_void(self) -> None:
        plan = growth.GrowthItemPlan(equip_slots=[], sell_slots=[])
        metrics = growth.empty_metric_summary()
        metrics["target_removed"] = 0
        metrics["target_removed_no_reward"] = 3

        bottleneck = growth.growth_bottleneck_reason(
            plan,
            {},
            metrics,
            party_size=1,
            xp_effective_delta=0,
            effective_death_delta=0,
            planned_merchant_transaction=False,
        )

        self.assertIn("target_removed_no_xp", bottleneck)
        self.assertNotIn("combat_no_kill", bottleneck)
        self.assertNotIn("no_engagement", bottleneck)

    def test_growth_bottleneck_allows_party_xp_without_personal_engagement(self) -> None:
        plan = growth.GrowthItemPlan(equip_slots=[], sell_slots=[])
        metrics = growth.empty_metric_summary()
        metrics["combat_engagements"] = 0
        metrics["target_removed"] = 0

        bottleneck = growth.growth_bottleneck_reason(
            plan,
            {},
            metrics,
            party_size=2,
            xp_effective_delta=32432,
            effective_death_delta=0,
            planned_merchant_transaction=False,
        )

        self.assertEqual(bottleneck, "none")

    def test_growth_bottleneck_does_not_hide_idle_segment_for_unexecuted_merchant_plan(self) -> None:
        plan = growth.GrowthItemPlan(equip_slots=[], sell_slots=[], buy_shortage_copper=100)
        metrics = growth.empty_metric_summary()

        bottleneck = growth.growth_bottleneck_reason(
            plan,
            {
                "zero_value_junk_items_after": 1,
                "sellable_junk_value_copper_after": 0,
            },
            metrics,
            party_size=1,
            xp_effective_delta=0,
            effective_death_delta=0,
            planned_merchant_transaction=True,
        )

        self.assertIn("gear_money_shortage_zero_value_junk", bottleneck)
        self.assertIn("no_engagement", bottleneck)

    def test_growth_equipment_plan_sells_other_realm_item(self) -> None:
        items = [
            growth.InventoryItem(
                account="growthmid701",
                slot=41,
                template_id="rowan_round_shield",
                name="Rowan Round Shield",
                level=2,
                dps_af=165,
                spd_abs=50,
                object_type=42,
                item_type=11,
                quality=85,
                bonus=0,
                allowed_classes="0",
                count=1,
                sell_price=15,
                realm=1,
            )
        ]

        plan = growth.build_growth_item_plan(items, class_id=22, level=9, realm_id=2)

        self.assertEqual(plan.equip_slots, [])
        self.assertEqual(plan.sell_slots, [41])
        self.assertIn("realm", plan.sell_reason)

    def test_growth_equipment_plan_sells_armor_above_character_ability(self) -> None:
        items = [
            growth.InventoryItem(
                account="growthmid60121",
                slot=22,
                template_id="bronze_stelskodd_gloves",
                name="bronze stelskodd gloves",
                level=2,
                dps_af=20,
                spd_abs=19,
                object_type=34,
                item_type=22,
                quality=85,
                bonus=0,
                allowed_classes="0",
                count=1,
                sell_price=0,
                realm=2,
            ),
            growth.InventoryItem(
                account="growthmid60121",
                slot=41,
                template_id="bronze_svarkedja_gloves",
                name="bronze svarkedja gloves",
                level=4,
                dps_af=34,
                spd_abs=27,
                object_type=35,
                item_type=22,
                quality=85,
                bonus=0,
                allowed_classes="0",
                count=1,
                sell_price=21,
                realm=2,
            ),
        ]

        plan = growth.build_growth_item_plan(
            items,
            class_id=22,
            level=7,
            realm_id=2,
            serialized_abilities="Sprint|0;Shield|2;MidArmor|3",
        )

        self.assertEqual(plan.equip_slots, [])
        self.assertEqual(plan.sell_slots, [41])
        self.assertIn("armor_ability", plan.sell_reason)

    def test_snapshot_inventory_items_reads_unique_templates(self) -> None:
        captured = {}

        def fake_run_mysql(_args, sql):
            captured["sql"] = sql
            return (
                "AccountName\tSlotPosition\tTemplateId\tItemName\tItemLevel\tDpsAf\tSpdAbs\tTypeDamage\tObjectType\t"
                "ItemType\tQuality\tBonus\tAllowedClasses\tRealm\tItemCount\tSellPrice\n"
                "growthalb701\t40\tunique_sword\tUnique Sword\t5\t36\t30\t2\t3\t10\t99\t4\t11\t1\t1\t25\n"
            )

        original_run_mysql = growth.run_mysql
        growth.run_mysql = fake_run_mysql
        try:
            rows = growth.snapshot_inventory_items(SimpleNamespace(), ["growthalb701"])
        finally:
            growth.run_mysql = original_run_mysql

        self.assertIn("itemunique", captured["sql"].lower())
        self.assertIn("UTemplate_Id", captured["sql"])
        self.assertIn("Type_Damage", captured["sql"])
        self.assertIn("Realm", captured["sql"])
        self.assertIn("NULLIF(inv.SellPrice, 0)", captured["sql"])
        self.assertIn("NULLIF(iu.Price, 0)", captured["sql"])
        self.assertEqual(rows["growthalb701"][0].template_id, "unique_sword")
        self.assertEqual(rows["growthalb701"][0].dps_af, 36)
        self.assertEqual(rows["growthalb701"][0].type_damage, 2)
        self.assertEqual(rows["growthalb701"][0].realm, 1)

    def test_growth_merchant_plan_buys_affordable_safe_upgrade_after_selling_junk(self) -> None:
        snapshot = growth.CharacterSnapshot(
            "growthalb701", "GrowthAlb701", "id", 5, 0, 1, 11, "Slash|5", 1, 534900, 477500, 2200, 0, 100, 2, 2
        )
        items = [
            growth.InventoryItem(
                account="growthalb701",
                slot=25,
                template_id="old_armor",
                name="Old Armor",
                level=1,
                dps_af=10,
                spd_abs=30,
                object_type=31,
                item_type=25,
                quality=90,
                bonus=0,
                allowed_classes="11",
                count=1,
                sell_price=0,
            ),
            growth.InventoryItem(
                account="growthalb701",
                slot=40,
                template_id="wrong_class_staff",
                name="Wrong Class Staff",
                level=3,
                dps_af=80,
                spd_abs=40,
                object_type=8,
                item_type=12,
                quality=100,
                bonus=10,
                allowed_classes="7",
                count=1,
                sell_price=1000,
            ),
        ]
        base_plan = growth.build_growth_item_plan(items, class_id=11, level=5)
        captured_sql = {}

        def fake_run_mysql(_args, sql):
            if "JOIN merchantitem" in sql:
                captured_sql["merchant"] = sql
                return (
                    "MerchantName\tItemListID\tPageNumber\tSlotPosition\tTemplateId\tItemName\tItemLevel\t"
                    "DpsAf\tSpdAbs\tObjectType\tItemType\tQuality\tBonus\tAllowedClasses\tPrice\tDistanceSquared\n"
                    "Alburn Hale\tAlbStuddedBoned\t0\t7\tnew_armor\tNew Armor\t5\t25\t30\t31\t25\t94\t2\t11\t500\t100\n"
                )
            return "MerchantName\tDistanceSquared\nAlburn Hale\t100\n"

        original_run_mysql = growth.run_mysql
        growth.run_mysql = fake_run_mysql
        try:
            plan = growth.build_growth_merchant_item_plan(
                SimpleNamespace(growth_merchant_max_distance=8000.0, growth_merchant_sell_ratio_percent=50),
                growth.REALMS["alb"],
                snapshot,
                items,
                base_plan,
                current_level=5,
                party_size=1,
            )
        finally:
            growth.run_mysql = original_run_mysql

        self.assertEqual(plan.merchant_npc_name, "Alburn Hale")
        self.assertEqual(plan.buy_slots, [7])
        self.assertEqual(plan.buy_inventory_slots, [40])
        self.assertIn("have_after_sell=600", plan.buy_reason)
        self.assertIn("COALESCE(it.Realm, 0) IN (0, 1)", captured_sql["merchant"])

    def test_alb_level_ten_checkpoint_gear_replaces_equipped_lower_score_items(self) -> None:
        args = SimpleNamespace(
            dry_run=False,
            checkpoint_levels_parsed=[10],
            checkpoint_start_location="route-home",
            growth_fast_travel="route-home",
            growth_merchant_max_distance=8000.0,
        )
        snapshot = growth.CharacterSnapshot(
            "growthalb701", "GrowthAlb701", "id", 10, 0, 1, 11, "Slash|10", 1, 534900, 477500, 2200, 0, 100, 1, 1
        )
        equipped = [
            growth.InventoryItem(
                account="growthalb701",
                slot=25,
                template_id="old_armor",
                name="Old Armor",
                level=1,
                dps_af=10,
                spd_abs=30,
                object_type=31,
                item_type=25,
                quality=90,
                bonus=0,
                allowed_classes="11",
                count=1,
                sell_price=0,
                realm=1,
            )
        ]
        candidate = growth.MerchantItemCandidate(
            merchant_name="Alburn Hale",
            item_list_id="AlbStuddedBoned",
            buy_slot=63,
            template_id="bronze_lamellar_gauntlets",
            name="bronze lamellar gauntlets",
            level=10,
            dps_af=28,
            spd_abs=30,
            object_type=31,
            item_type=25,
            quality=90,
            bonus=0,
            allowed_classes="11",
            price=60,
            distance=100,
            realm=1,
        )
        captured: dict[str, object] = {}

        original_query = growth.query_growth_merchant_item_candidates
        original_run_mysql = growth.run_mysql
        def fake_query(*_args, **kwargs):
            captured["max_distance"] = kwargs.get("max_distance")
            return [candidate]

        growth.query_growth_merchant_item_candidates = fake_query
        growth.run_mysql = lambda _args, sql: captured.setdefault("sql", sql) or ""
        try:
            updated = growth.equip_growth_checkpoint_gear(
                args,
                growth.REALMS["alb"],
                {"growthalb701": snapshot},
                {"growthalb701": equipped},
                current_level=10,
                party_size=1,
            )
        finally:
            growth.query_growth_merchant_item_candidates = original_query
            growth.run_mysql = original_run_mysql

        self.assertEqual(updated, 1)
        self.assertEqual(captured["max_distance"], 30000.0)
        self.assertIn("UPDATE inventory inv", captured["sql"])
        self.assertIn("c.AccountName = 'growthalb701'", captured["sql"])
        self.assertIn("gift.Id_nb = 'bronze_lamellar_gauntlets'", captured["sql"])
        self.assertIn("inv.SlotPosition = 25", captured["sql"])
        self.assertIn("checkpoint-gear", captured["sql"])

    def test_checkpoint_gear_uses_trained_armor_ability_floor_for_mid(self) -> None:
        args = SimpleNamespace(
            dry_run=False,
            checkpoint_levels_parsed=[10],
            checkpoint_start_location="route-home",
            growth_fast_travel="route-home",
            growth_merchant_max_distance=8000.0,
        )
        snapshot = growth.CharacterSnapshot(
            "growthmid701",
            "GrowthMid701",
            "id",
            10,
            0,
            2,
            22,
            "Hammer|10;Shields|8",
            100,
            773327,
            749653,
            4552,
            0,
            0,
            1,
            1,
            serialized_abilities="Sprint|0;MidArmor|1;Shield|3",
        )
        equipped = [
            growth.InventoryItem(
                account="growthmid701",
                slot=10,
                template_id="bronze_battle_hammer2",
                name="bronze battle hammer",
                level=5,
                dps_af=27,
                spd_abs=41,
                object_type=12,
                item_type=10,
                quality=85,
                bonus=0,
                allowed_classes="0",
                count=1,
                sell_price=0,
                realm=2,
                type_damage=1,
            ),
            growth.InventoryItem(
                account="growthmid701",
                slot=25,
                template_id="bronze_stelskodd_jerkin",
                name="bronze stelskodd jerkin",
                level=2,
                dps_af=4,
                spd_abs=19,
                object_type=34,
                item_type=25,
                quality=85,
                bonus=0,
                allowed_classes="0",
                count=1,
                sell_price=0,
                realm=2,
            )
        ]
        armor_candidate = growth.MerchantItemCandidate(
            merchant_name="Baldus",
            item_list_id="MidStudded",
            buy_slot=7,
            template_id="steel_stelskodd_jerkin",
            name="steel stelskodd jerkin",
            level=10,
            dps_af=20,
            spd_abs=19,
            object_type=34,
            item_type=25,
            quality=85,
            bonus=0,
            allowed_classes="0",
            price=2000,
            distance=100,
            realm=2,
        )
        weapon_candidate = growth.MerchantItemCandidate(
            merchant_name="Burl",
            item_list_id="MidHammer",
            buy_slot=8,
            template_id="iron_war_hammer2",
            name="iron war hammer",
            level=8,
            dps_af=36,
            spd_abs=35,
            object_type=12,
            item_type=10,
            quality=85,
            bonus=0,
            allowed_classes="0",
            price=500,
            distance=100,
            realm=2,
            type_damage=1,
        )
        captured: dict[str, str] = {}

        original_query = growth.query_growth_merchant_item_candidates
        original_run_mysql = growth.run_mysql
        growth.query_growth_merchant_item_candidates = lambda *_args, **_kwargs: [armor_candidate, weapon_candidate]
        growth.run_mysql = lambda _args, sql: captured.setdefault("sql", sql) or ""
        try:
            updated = growth.equip_growth_checkpoint_gear(
                args,
                growth.REALMS["mid"],
                {"growthmid701": snapshot},
                {"growthmid701": equipped},
                current_level=10,
                party_size=1,
            )
        finally:
            growth.query_growth_merchant_item_candidates = original_query
            growth.run_mysql = original_run_mysql

        self.assertEqual(updated, 2)
        self.assertIn("gift.Id_nb = 'steel_stelskodd_jerkin'", captured["sql"])
        self.assertIn("gift.Id_nb = 'iron_war_hammer2'", captured["sql"])
        self.assertIn("inv.SlotPosition = 10", captured["sql"])
        self.assertIn("inv.SlotPosition = 25", captured["sql"])

    def test_checkpoint_gear_is_limited_to_solo_checkpoints_and_level_seven_gear_stage(self) -> None:
        base_args = SimpleNamespace(dry_run=False, checkpoint_levels_parsed=[6, 10], growth_stage="custom")

        self.assertTrue(
            growth.should_equip_growth_checkpoint_gear(
                base_args,
                growth.REALMS["alb"],
                current_level=10,
                party_size=1,
            )
        )
        self.assertTrue(
            growth.should_equip_growth_checkpoint_gear(
                base_args,
                growth.REALMS["alb"],
                current_level=6,
                party_size=1,
            )
        )
        self.assertTrue(
            growth.should_equip_growth_checkpoint_gear(
                base_args,
                growth.REALMS["mid"],
                current_level=10,
                party_size=1,
            )
        )
        self.assertTrue(
            growth.should_equip_growth_checkpoint_gear(
                base_args,
                growth.REALMS["hib"],
                current_level=6,
                party_size=1,
            )
        )
        self.assertFalse(
            growth.should_equip_growth_checkpoint_gear(
                base_args,
                growth.REALMS["alb"],
                current_level=7,
                party_size=1,
            )
        )
        self.assertTrue(
            growth.should_equip_growth_checkpoint_gear(
                SimpleNamespace(dry_run=False, checkpoint_levels_parsed=[], growth_stage="gear"),
                growth.REALMS["alb"],
                current_level=7,
                party_size=1,
            )
        )
        self.assertTrue(
            growth.should_equip_growth_checkpoint_gear(
                SimpleNamespace(dry_run=False, checkpoint_levels_parsed=[], growth_stage="custom", reset_level=10),
                growth.REALMS["alb"],
                current_level=10,
                party_size=1,
            )
        )
        self.assertFalse(
            growth.should_equip_growth_checkpoint_gear(
                SimpleNamespace(dry_run=False, checkpoint_levels_parsed=[], growth_stage="gear"),
                growth.REALMS["alb"],
                current_level=7,
                party_size=4,
            )
        )
        self.assertFalse(
            growth.should_equip_growth_checkpoint_gear(
                base_args,
                growth.REALMS["alb"],
                current_level=10,
                party_size=4,
            )
        )
        self.assertFalse(
            growth.should_equip_growth_checkpoint_gear(
                SimpleNamespace(dry_run=True, checkpoint_levels_parsed=[10]),
                growth.REALMS["alb"],
                current_level=10,
                party_size=1,
            )
        )
        self.assertFalse(
            growth.should_equip_growth_checkpoint_gear(
                SimpleNamespace(dry_run=False, checkpoint_levels_parsed=[6]),
                growth.REALMS["alb"],
                current_level=10,
                party_size=1,
            )
        )

    def test_alb_level_seven_checkpoint_gear_searches_start_service_merchants(self) -> None:
        args = SimpleNamespace(
            dry_run=False,
            checkpoint_levels_parsed=[],
            growth_stage="gear",
            growth_merchant_max_distance=8000.0,
            checkpoint_start_location="route-home",
            growth_fast_travel="route-home",
        )
        snapshot = growth.CharacterSnapshot(
            "growthalb701",
            "GrowthAlb701",
            "id",
            7,
            0,
            1,
            1,
            "Slash|5;Thrust|1;Crush|1;Two Handed|1;Chants|4;Shields|5;Parry|1",
            1,
            595117,
            506793,
            2560,
            0,
            53,
            1,
            1,
            serialized_abilities="Sprint|0;Shield|2;AlbArmor|3",
        )
        equipped = [
            growth.InventoryItem(
                account="growthalb701",
                slot=25,
                template_id="bronze_studded_vest",
                name="bronze studded vest",
                level=2,
                dps_af=4,
                spd_abs=19,
                object_type=34,
                item_type=25,
                quality=85,
                bonus=0,
                allowed_classes="0",
                count=1,
                sell_price=0,
                realm=1,
            )
        ]
        candidate = growth.MerchantItemCandidate(
            merchant_name="Farl Dalston",
            item_list_id="AlbChain",
            buy_slot=0,
            template_id="iron_chain_hauberk",
            name="iron chain hauberk",
            level=5,
            dps_af=10,
            spd_abs=27,
            object_type=35,
            item_type=25,
            quality=85,
            bonus=0,
            allowed_classes="0",
            price=3420,
            distance=3800,
            realm=1,
        )
        captured: dict[str, object] = {}

        def fake_query(_args, _realm, *, x, y, level, max_distance):
            captured["x"] = x
            captured["y"] = y
            captured["level"] = level
            captured["max_distance"] = max_distance
            return [candidate]

        original_query = growth.query_growth_merchant_item_candidates
        original_run_mysql = growth.run_mysql
        growth.query_growth_merchant_item_candidates = fake_query
        growth.run_mysql = lambda _args, sql: captured.setdefault("sql", sql) or ""
        try:
            updated = growth.equip_growth_checkpoint_gear(
                args,
                growth.REALMS["alb"],
                {"growthalb701": snapshot},
                {"growthalb701": equipped},
                current_level=7,
                party_size=1,
            )
        finally:
            growth.query_growth_merchant_item_candidates = original_query
            growth.run_mysql = original_run_mysql

        self.assertEqual(updated, 1)
        self.assertEqual((captured["x"], captured["y"]), growth.REALMS["alb"].start[:2])
        self.assertEqual(captured["level"], 7)
        self.assertEqual(captured["max_distance"], 30000.0)
        self.assertIn("gift.Id_nb = 'iron_chain_hauberk'", str(captured["sql"]))

    def test_mid_level_ten_shortage_recovery_uses_level_seven_target(self) -> None:
        plan = growth.GrowthItemPlan(
            equip_slots=[],
            sell_slots=[],
            buy_reason="shortage:buckler",
            buy_shortage_copper=50,
        )

        self.assertEqual(
            growth.growth_shortage_recovery_route_override(
                SimpleNamespace(growth_allow_lower_xp_gear_farm=True),
                growth.REALMS["mid"],
                current_level=10,
                party_size=1,
                item_plans={"growthmid701": plan},
            ),
            (10, 7),
        )

    def test_growth_merchant_plan_skips_armor_above_character_ability(self) -> None:
        snapshot = growth.CharacterSnapshot(
            "growthmid60121",
            "GrowthMid60121",
            "id",
            7,
            0,
            2,
            22,
            "Hammer|7",
            1,
            730444,
            812140,
            5434,
            0,
            500,
            1,
            1,
            serialized_abilities="Sprint|0;Shield|2;MidArmor|3",
        )
        items = [
            growth.InventoryItem(
                account="growthmid60121",
                slot=22,
                template_id="bronze_stelskodd_gloves",
                name="bronze stelskodd gloves",
                level=2,
                dps_af=20,
                spd_abs=19,
                object_type=34,
                item_type=22,
                quality=85,
                bonus=0,
                allowed_classes="0",
                count=1,
                sell_price=0,
                realm=2,
            ),
        ]
        base_plan = growth.build_growth_item_plan(
            items,
            class_id=22,
            level=7,
            realm_id=2,
            serialized_abilities=snapshot.serialized_abilities,
        )

        def fake_run_mysql(_args, sql):
            if "JOIN merchantitem" in sql:
                return (
                    "MerchantName\tItemListID\tPageNumber\tSlotPosition\tTemplateId\tItemName\tItemLevel\t"
                    "DpsAf\tSpdAbs\tObjectType\tItemType\tQuality\tBonus\tAllowedClasses\tPrice\tDistanceSquared\n"
                    "Vers\tMidChain\t0\t4\tbronze_svarkedja_gloves\tbronze svarkedja gloves\t4\t34\t27\t35\t22\t85\t0\t0\t100\t100\n"
                    "Vers\tMidStudded\t0\t5\tbronze_stelskodd_gloves2\tbronze stelskodd gloves\t4\t28\t19\t34\t22\t85\t0\t0\t80\t100\n"
                )
            return "MerchantName\tDistanceSquared\nVers\t100\n"

        original_run_mysql = growth.run_mysql
        growth.run_mysql = fake_run_mysql
        try:
            plan = growth.build_growth_merchant_item_plan(
                SimpleNamespace(growth_merchant_max_distance=8000.0, growth_merchant_sell_ratio_percent=50),
                growth.REALMS["mid"],
                snapshot,
                items,
                base_plan,
                current_level=7,
                party_size=1,
            )
        finally:
            growth.run_mysql = original_run_mysql

        self.assertEqual(plan.merchant_npc_name, "Vers")
        self.assertEqual(plan.buy_slots, [5])
        self.assertIn("bronze stelskodd gloves", plan.buy_reason)
        self.assertNotIn("svarkedja", plan.buy_reason)

    def test_growth_merchant_plan_records_shortage_without_free_gear(self) -> None:
        snapshot = growth.CharacterSnapshot(
            "growthalb701", "GrowthAlb701", "id", 5, 0, 1, 11, "Slash|5", 1, 534900, 477500, 2200, 0, 100, 1, 1
        )
        items = [
            growth.InventoryItem(
                account="growthalb701",
                slot=25,
                template_id="old_armor",
                name="Old Armor",
                level=1,
                dps_af=10,
                spd_abs=30,
                object_type=31,
                item_type=25,
                quality=90,
                bonus=0,
                allowed_classes="11",
                count=1,
                sell_price=0,
            )
        ]
        base_plan = growth.build_growth_item_plan(items, class_id=11, level=5)

        def fake_run_mysql(_args, sql):
            if "JOIN merchantitem" in sql:
                return (
                    "MerchantName\tItemListID\tPageNumber\tSlotPosition\tTemplateId\tItemName\tItemLevel\t"
                    "DpsAf\tSpdAbs\tObjectType\tItemType\tQuality\tBonus\tAllowedClasses\tPrice\tDistanceSquared\n"
                    "Alburn Hale\tAlbStuddedBoned\t0\t7\tnew_armor\tNew Armor\t5\t25\t30\t31\t25\t94\t2\t11\t500\t100\n"
                )
            return "MerchantName\tDistanceSquared\nAlburn Hale\t100\n"

        original_run_mysql = growth.run_mysql
        growth.run_mysql = fake_run_mysql
        try:
            plan = growth.build_growth_merchant_item_plan(
                SimpleNamespace(growth_merchant_max_distance=8000.0, growth_merchant_sell_ratio_percent=50),
                growth.REALMS["alb"],
                snapshot,
                items,
                base_plan,
                current_level=5,
                party_size=1,
            )
        finally:
            growth.run_mysql = original_run_mysql

        self.assertEqual(plan.buy_slots, [])
        self.assertEqual(plan.buy_shortage_copper, 400)
        self.assertIn("shortage:New Armor", plan.buy_reason)

    def test_growth_merchant_plan_skips_offhand_weapon_for_shield_class(self) -> None:
        snapshot = growth.CharacterSnapshot(
            "growthalb701",
            "GrowthAlb701",
            "id",
            7,
            0,
            1,
            1,
            "Slash|7;Chants|4;Shields|2",
            1,
            534900,
            477500,
            2200,
            0,
            0,
            1,
            1,
            serialized_abilities="Sprint|0;Shield|2;AlbArmor|3;Weaponry: Slashing|0",
        )
        items = [
            growth.InventoryItem(
                account="growthalb701",
                slot=11,
                template_id="small_training_shield",
                name="small training shield",
                level=2,
                dps_af=12,
                spd_abs=40,
                object_type=42,
                item_type=11,
                quality=100,
                bonus=0,
                allowed_classes="0",
                count=1,
                sell_price=0,
                realm=1,
            )
        ]
        base_plan = growth.build_growth_item_plan(
            items,
            class_id=1,
            level=7,
            realm_id=1,
            serialized_abilities=snapshot.serialized_abilities,
        )

        def fake_run_mysql(_args, sql):
            if "JOIN merchantitem" in sql:
                return (
                    "MerchantName\tItemListID\tPageNumber\tSlotPosition\tTemplateId\tItemName\tItemLevel\t"
                    "DpsAf\tSpdAbs\tTypeDamage\tObjectType\tItemType\tQuality\tBonus\tRealm\tAllowedClasses\tPrice\tDistanceSquared\n"
                    "Sywno\tAlbWeapons\t0\t7\tbronze_dirk\tbronze dirk\t1\t15\t28\t0\t3\t11\t85\t0\t1\t0\t73\t100\n"
                    "Calldir Edyn\tAlbStudded\t0\t8\tbronze_lamellar_gauntlets\tbronze lamellar gauntlets\t5\t10\t19\t0\t34\t22\t85\t0\t1\t0\t60\t100\n"
                )
            return "MerchantName\tDistanceSquared\nSywno\t100\n"

        original_run_mysql = growth.run_mysql
        growth.run_mysql = fake_run_mysql
        try:
            plan = growth.build_growth_merchant_item_plan(
                SimpleNamespace(growth_merchant_max_distance=8000.0, growth_merchant_sell_ratio_percent=50),
                growth.REALMS["alb"],
                snapshot,
                items,
                base_plan,
                current_level=7,
                party_size=1,
            )
        finally:
            growth.run_mysql = original_run_mysql

        self.assertEqual(plan.buy_slots, [])
        self.assertEqual(plan.buy_shortage_copper, 60)
        self.assertIn("bronze lamellar gauntlets", plan.buy_reason)
        self.assertNotIn("bronze dirk", plan.buy_reason)

    def test_growth_merchant_plan_skips_weapon_that_does_not_match_trained_spec(self) -> None:
        snapshot = growth.CharacterSnapshot(
            "growthmid60121",
            "GrowthMid60121",
            "id",
            9,
            0,
            2,
            22,
            "Hammer|9;Sword|1;Axe|1;Thrown Weapons|1;Shields|7",
            100,
            773327,
            749653,
            4600,
            0,
            195,
            1,
            1,
            serialized_abilities="Sprint|0;Shield|2;MidArmor|3;Weaponry: Hammers|0;Weaponry: Staves|0",
        )
        items = [
            growth.InventoryItem(
                account="growthmid60121",
                slot=12,
                template_id="rowan_staff",
                name="rowan staff",
                level=1,
                dps_af=15,
                spd_abs=45,
                object_type=8,
                item_type=12,
                quality=85,
                bonus=0,
                allowed_classes="0",
                count=1,
                sell_price=110,
                realm=2,
            )
        ]
        base_plan = growth.build_growth_item_plan(
            items,
            class_id=22,
            level=9,
            realm_id=2,
            serialized_abilities=snapshot.serialized_abilities,
            specs=snapshot.specs,
        )

        def fake_run_mysql(_args, sql):
            if "JOIN merchantitem" in sql:
                return (
                    "MerchantName\tItemListID\tPageNumber\tSlotPosition\tTemplateId\tItemName\tItemLevel\t"
                    "DpsAf\tSpdAbs\tTypeDamage\tObjectType\tItemType\tQuality\tBonus\tRealm\tAllowedClasses\tPrice\tDistanceSquared\n"
                    "Mildri\tMidStaves\t0\t7\tbronze_shod_staff\tbronze shod staff\t3\t21\t45\t0\t8\t12\t85\t0\t2\t0\t275\t100\n"
                    "Ragnar\tMidStudded\t0\t8\tbronze_svarskodd_jerkin\tbronze svarskodd jerkin\t3\t6\t19\t0\t34\t25\t85\t0\t2\t0\t262\t100\n"
                )
            return "MerchantName\tDistanceSquared\nMildri\t100\n"

        original_run_mysql = growth.run_mysql
        growth.run_mysql = fake_run_mysql
        try:
            plan = growth.build_growth_merchant_item_plan(
                SimpleNamespace(growth_merchant_max_distance=8000.0, growth_merchant_sell_ratio_percent=50),
                growth.REALMS["mid"],
                snapshot,
                items,
                base_plan,
                current_level=9,
                party_size=1,
            )
        finally:
            growth.run_mysql = original_run_mysql

        self.assertEqual(plan.buy_slots, [])
        self.assertEqual(plan.buy_shortage_copper, 67)
        self.assertIn("bronze svarskodd jerkin", plan.buy_reason)
        self.assertNotIn("bronze shod staff", plan.buy_reason)

    def test_growth_merchant_search_uses_route_teleporter_for_realm_start_segments(self) -> None:
        snapshot = growth.CharacterSnapshot(
            "growthalb701", "GrowthAlb701", "id", 6, 0, 1, 11, "Slash|6", 1, 523851, 476161, 3339, 0, 37, 8, 8
        )

        self.assertEqual(
            growth.growth_merchant_search_point(
                SimpleNamespace(checkpoint_start_location="realm-start"),
                growth.REALMS["alb"],
                snapshot,
                current_level=6,
                party_size=1,
            ),
            growth.teleport_destination_point(growth.REALMS["alb"], "Prydwen Keep"),
        )

    def test_growth_merchant_search_uses_realm_start_during_route_home_fast_travel(self) -> None:
        snapshot = growth.CharacterSnapshot(
            "growthalb701", "GrowthAlb701", "id", 7, 0, 1, 1, "Slash|7", 1, 491813, 601083, 1873, 0, 0, 8, 8
        )

        self.assertEqual(
            growth.growth_merchant_search_point(
                SimpleNamespace(checkpoint_start_location="route-home", growth_fast_travel="route-home"),
                growth.REALMS["alb"],
                snapshot,
                current_level=7,
                party_size=1,
            ),
            growth.REALMS["alb"].start,
        )

    def test_l10_reset_checkpoint_gear_search_uses_realm_start_even_when_route_home_start(self) -> None:
        snapshot = growth.CharacterSnapshot(
            "growthhib060", "GrowthHib060", "id", 10, 0, 3, 44, "Blades|10", 20, 350899, 531716, 3637, 0, 0, 1, 1
        )

        self.assertEqual(
            growth.growth_merchant_search_point(
                SimpleNamespace(
                    checkpoint_start_location="route-home",
                    growth_fast_travel="off",
                    reset_level=10,
                    checkpoint_levels_parsed=[],
                ),
                growth.REALMS["hib"],
                snapshot,
                current_level=10,
                party_size=1,
            ),
            growth.REALMS["hib"].start,
        )

    def test_case_plan_assigns_unique_case_indexes(self) -> None:
        cases = growth.build_case_plan(["alb", "mid"], [1, 4])

        self.assertEqual(
            [
                (realm.key, party_size, case_index, repeat_index, case_repeats)
                for realm, party_size, case_index, repeat_index, case_repeats in cases
            ],
            [
                ("alb", 1, 0, 0, 1),
                ("alb", 4, 1, 0, 1),
                ("mid", 1, 2, 0, 1),
                ("mid", 4, 3, 0, 1),
            ],
        )

    def test_case_plan_repeats_each_realm_party_case(self) -> None:
        cases = growth.build_case_plan(["alb", "mid"], [1], case_repeats=2)

        self.assertEqual(
            [
                (realm.key, party_size, case_index, repeat_index, case_repeats)
                for realm, party_size, case_index, repeat_index, case_repeats in cases
            ],
            [
                ("alb", 1, 0, 0, 2),
                ("alb", 1, 1, 1, 2),
                ("mid", 1, 2, 0, 2),
                ("mid", 1, 3, 1, 2),
            ],
        )

    def test_growth_case_name_suffixes_repeated_cases_only(self) -> None:
        realm = growth.REALMS["alb"]

        self.assertEqual(growth.growth_case_name(realm, 1), "alb-p1")
        self.assertEqual(growth.growth_case_name(realm, 1, repeat_index=4, case_repeats=100), "alb-p1-r005")

    def test_case_name_override_requires_single_case(self) -> None:
        with self.assertRaisesRegex(SystemExit, "--case-name requires exactly one"):
            growth.parse_args_for_tests(["--dry-run", "--case-name", "case-a"])

    def test_case_name_override_is_used_for_case_directory(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--case-name",
                "case-alb-solo-001",
                "--realms",
                "alb",
                "--party-sizes",
                "1",
                "--max-segments",
                "1",
                "--no-watch-movement",
                "--no-fail-on-regression",
            ]
        )
        captured_case_dirs: list[str] = []
        original_build_behavior_command = growth.build_behavior_command
        original_run_commands_concurrently = growth.run_commands_concurrently
        try:
            def fake_build_behavior_command(**kwargs):
                captured_case_dirs.append(kwargs["case_dir"].name)
                return ["behavior", kwargs["case_dir"].name]

            growth.build_behavior_command = fake_build_behavior_command
            growth.run_commands_concurrently = lambda _commands, _dry_run: 0

            with tempfile.TemporaryDirectory() as temp_dir:
                output_dir = Path(temp_dir)
                rc = growth.run_case(
                    args,
                    growth.REALMS["alb"],
                    party_size=1,
                    case_index=0,
                    output_dir=output_dir,
                    path_graph=output_dir / "growth-route-graph.json",
                    timeline_csv=output_dir / "timeline.csv",
                )
        finally:
            growth.build_behavior_command = original_build_behavior_command
            growth.run_commands_concurrently = original_run_commands_concurrently

        self.assertEqual(rc, 0)
        self.assertEqual(captured_case_dirs, ["case-alb-solo-001"])

    def test_first_segment_starts_explicit_segment_window(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--first-segment",
                "7",
                "--realms",
                "alb",
                "--party-sizes",
                "1",
                "--max-segments",
                "2",
                "--inter-segment-delay",
                "0",
                "--no-watch-movement",
                "--no-fail-on-regression",
            ]
        )
        captured_segments: list[int] = []
        original_build_behavior_command = growth.build_behavior_command
        original_run_commands_concurrently = growth.run_commands_concurrently
        try:
            def fake_build_behavior_command(**kwargs):
                captured_segments.append(kwargs["segment_index"])
                return ["behavior", str(kwargs["segment_index"])]

            growth.build_behavior_command = fake_build_behavior_command
            growth.run_commands_concurrently = lambda _commands, _dry_run: 0

            with tempfile.TemporaryDirectory() as temp_dir:
                output_dir = Path(temp_dir)
                rc = growth.run_case(
                    args,
                    growth.REALMS["alb"],
                    party_size=1,
                    case_index=0,
                    output_dir=output_dir,
                    path_graph=output_dir / "growth-route-graph.json",
                    timeline_csv=output_dir / "timeline.csv",
                )
        finally:
            growth.build_behavior_command = original_build_behavior_command
            growth.run_commands_concurrently = original_run_commands_concurrently

        self.assertEqual(rc, 0)
        self.assertEqual(captured_segments, [7, 8])

    def test_level_one_preferred_route_targets_are_not_required(self) -> None:
        route = growth.select_route_point(growth.REALMS["alb"], 1)
        solo_route = growth.select_route_point(growth.REALMS["alb"], 1, party_size=1)
        hib_route = growth.select_route_point(growth.REALMS["hib"], 1, party_size=1)

        self.assertEqual(growth.strict_route_target_name(route, 1), "")
        self.assertEqual(growth.strict_route_target_name(route, 2), "")
        self.assertEqual(growth.strict_route_target_name(solo_route, 1, party_size=1), "green snake")
        self.assertEqual(growth.strict_route_target_name(hib_route, 1, party_size=1, realm_key="hib"), "")
        self.assertEqual(growth.strict_route_target_name(hib_route, 2, party_size=1, realm_key="hib"), "")

    def test_mid_level_one_route_uses_dense_parallel_target_cluster(self) -> None:
        route = growth.select_route_point(growth.REALMS["mid"], 1)

        self.assertEqual((route.x, route.y, route.z), (770900, 746700, 4620))
        self.assertEqual(
            growth.strict_route_target_name(route, 1),
            "",
        )

    def test_level_one_party_routes_disperse_parallel_cases(self) -> None:
        alb_p8 = growth.select_route_point(growth.REALMS["alb"], 1, party_size=8)
        alb_p4 = growth.select_route_point(growth.REALMS["alb"], 1, party_size=4)
        mid_p1 = growth.select_route_point(growth.REALMS["mid"], 1, party_size=1)
        mid_p2 = growth.select_route_point(growth.REALMS["mid"], 1, party_size=2)
        mid_p4 = growth.select_route_point(growth.REALMS["mid"], 1, party_size=4)
        mid_p8 = growth.select_route_point(growth.REALMS["mid"], 1, party_size=8)

        self.assertEqual((alb_p8.x, alb_p8.y, alb_p8.z), (534650, 477500, 2200))
        self.assertIn("green snake", alb_p4.prefer)
        self.assertIn("black wolf pup", alb_p4.prefer)
        self.assertIn("weak skeleton", alb_p4.avoid)
        self.assertEqual(growth.strict_route_target_name(alb_p8, 1), "")
        self.assertIn("young cutpurse", alb_p8.avoid)
        self.assertEqual((mid_p1.x, mid_p1.y, mid_p1.z), (770900, 746700, 4620))
        self.assertEqual(mid_p1.prefer, "lupine gnawer")
        self.assertIn("young sveawolf", mid_p1.avoid)
        self.assertEqual((mid_p2.x, mid_p2.y, mid_p2.z), (773538, 749971, 4552))
        self.assertIn("vein spiderling", mid_p2.prefer)
        self.assertIn("soft-shelled crab", mid_p2.avoid)
        self.assertEqual((mid_p4.x, mid_p4.y, mid_p4.z), (774968, 748210, 4695))
        self.assertIn("tawny lynx cub", mid_p4.prefer)
        self.assertIn("soft-shelled crab", mid_p4.avoid)
        self.assertIn("wildling", mid_p4.avoid)
        self.assertEqual(
            growth.strict_route_target_name(mid_p1, 1),
            "",
        )
        self.assertEqual(growth.strict_route_target_name(mid_p2, 1), "")
        self.assertEqual(growth.strict_route_target_name(mid_p4, 1, 4, "mid"), "tawny lynx cub")
        self.assertEqual(growth.strict_route_target_name(mid_p8, 1), "")

    def test_alb_level_one_p4_carry_route_allows_nearby_small_gray_wolves(self) -> None:
        route = growth.select_route_point(growth.REALMS["alb"], 2, party_size=4)

        self.assertIn("small gray wolf", route.prefer)
        self.assertNotIn("small gray wolf", route.avoid)
        self.assertEqual((route.x, route.y, route.z), (534900, 478900, 2310))

    def test_alb_level_one_p4_carry_command_does_not_avoid_small_gray_wolves(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=1500,
            target_home_max_distance=6200.0,
            combat_home_leash_distance=6200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            startup_delay=0.0,
            party_external_member_names="",
            growth_fast_travel="off",
            growth_allow_lower_xp_gear_farm=False,
            growth_route_level_override=2,
            growth_route_level_is_carry_target=True,
            growth_target_level_override=1,
            growth_target_plan_override=(2, 2, 1),
            growth_equip_party_carry_gear=False,
        )
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=1,
                party_size=4,
                current_level=1,
                path_graph=Path("graph.json"),
            )

        self.assertIn("--prefer-target-name", command)
        self.assertIn("small gray wolf", command[command.index("--prefer-target-name") + 1])
        self.assertIn("--avoid-target-name", command)
        self.assertNotIn("small gray wolf", command[command.index("--avoid-target-name") + 1])
        self.assertEqual(command[command.index("--party-min-ready") + 1], "4")

    def test_index_routes_do_not_force_stale_strict_targets(self) -> None:
        mid_index_route = growth.route_point(1, 747816, 827409, 4786, "wolf nipper", "", "Fort Atla")
        hib_index_route = growth.route_point(6, 305916, 630238, 5710, "spraggon", "", "Shannon Estuary")

        self.assertEqual(growth.strict_route_target_name(mid_index_route, 1, 4, "mid"), "")
        self.assertEqual(growth.strict_route_target_name(hib_index_route, 6, 1, "hib"), "")

        hib_p4 = growth.select_route_point(growth.REALMS["hib"], 1, party_size=4)
        hib_p2 = growth.select_route_point(growth.REALMS["hib"], 1, party_size=2)
        self.assertEqual((hib_p2.x, hib_p2.y, hib_p2.z), (344500, 474500, 5372))
        self.assertIn("annoying lucradan", hib_p2.prefer)
        self.assertIn("badger cub", hib_p2.prefer)
        self.assertIn("large frog", hib_p2.prefer)
        self.assertNotIn("annoying lucradan", hib_p2.avoid)
        self.assertIn("water beetle larva", hib_p2.avoid)
        self.assertIn("annoying lucradan", hib_p4.prefer)
        self.assertIn("badger cub", hib_p4.prefer)
        self.assertNotIn("water beetle larva", hib_p4.prefer)
        self.assertIn("water beetle larva", hib_p4.avoid)

    def test_waypoints_use_neighboring_route_points(self) -> None:
        realm = growth.REALMS["alb"]

        waypoints = growth.waypoint_string(realm, 10)

        self.assertRegex(waypoints, r"594457,499932,\d+")
        self.assertRegex(waypoints, r"594817,499932,\d+")
        self.assertRegex(waypoints, r"594817,500292,\d+")

    def test_early_level_waypoints_sweep_wider_hunt_area(self) -> None:
        realm = growth.REALMS["alb"]

        waypoints = growth.waypoint_string(realm, 1)

        self.assertRegex(waypoints, r"534650,477500,\d+")
        self.assertRegex(waypoints, r"537050,477500,\d+")
        self.assertRegex(waypoints, r"534650,479900,\d+")

    def test_growth_path_graph_contains_all_realm_regions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "growth-route-graph.json"
            growth.write_growth_path_graph(path)
            payload = path.read_text(encoding="utf-8")

        self.assertIn('"1"', payload)
        self.assertIn('"100"', payload)
        self.assertIn('"200"', payload)
        self.assertIn('"alb_1"', payload)
        self.assertIn('"alb_start"', payload)
        self.assertIn('"alb_teleport_caer_ulfwych"', payload)
        self.assertIn('"mid_50"', payload)
        self.assertIn('"hib_50"', payload)

    def test_growth_path_graph_includes_hunting_index_local_centers(self) -> None:
        import dummy_pathing

        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            with index_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["realm", "party_size", "player_level", "x", "y", "z", "name", "nearest_teleporter"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "realm": "hib",
                        "party_size": "1",
                        "player_level": "4",
                        "x": "345935",
                        "y": "470831",
                        "z": "6032",
                        "name": "skeletal pawn",
                        "nearest_teleporter": "",
                    }
                )
            path = Path(temp_dir) / "growth-route-graph.json"
            growth.write_growth_path_graph(path, growth_hunting_index=str(index_path))
            payload = json.loads(path.read_text(encoding="utf-8"))
            graph = dummy_pathing.PathGraph.from_file(path)

        nodes = payload["regions"]["200"]["nodes"]
        node_ids = {node["id"] for node in nodes}
        self.assertIn("hib_hunting_index_4_0", node_ids)
        self.assertIn("hib_hunting_index_4_0_w_2", node_ids)
        self.assertTrue(any(node["x"] == 345935 and node["y"] == 470831 for node in nodes))
        safety = dummy_pathing.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=2500)
        self.assertTrue(graph.astar("hib_4_g_350_0", "hib_hunting_index_4_0_w_2", safety).ok)

    def test_growth_path_graph_routes_between_level_hubs(self) -> None:
        import dummy_pathing

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "growth-route-graph.json"
            growth.write_growth_path_graph(path)
            graph = dummy_pathing.PathGraph.from_file(path)

        safety = dummy_pathing.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=2500)
        self.assertTrue(graph.astar("alb_start", "alb_5", safety).ok)
        self.assertTrue(graph.astar("mid_start", "mid_5", safety).ok)
        self.assertTrue(graph.astar("hib_start", "hib_5", safety).ok)
        self.assertTrue(graph.astar("alb_teleport_caer_ulfwych", "alb_10", safety).ok)
        self.assertTrue(graph.astar("mid_start", "mid_6", safety).ok)
        self.assertTrue(graph.astar("mid_teleport_fort_veldon", "mid_10", safety).ok)
        self.assertTrue(graph.astar("hib_teleport_connla", "hib_10", safety).ok)

    def test_growth_path_graph_routes_mid_six_through_stable_mularn_worker_hub(self) -> None:
        import dummy_pathing

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "growth-route-graph.json"
            growth.write_growth_path_graph(path)
            graph = dummy_pathing.PathGraph.from_file(path)

        safety = dummy_pathing.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=2500)
        route = graph.astar("mid_start", "mid_6", safety)
        node_ids = [node.id for node in route.nodes]

        self.assertTrue(route.ok)
        self.assertIn("mid_5", node_ids)
        self.assertEqual(node_ids[-1], "mid_6")

    def test_growth_path_graph_routes_to_level_ten_party_variants(self) -> None:
        import dummy_pathing

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "growth-route-graph.json"
            growth.write_growth_path_graph(path)
            graph = dummy_pathing.PathGraph.from_file(path)
            payload = json.loads(path.read_text(encoding="utf-8"))

        safety = dummy_pathing.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=2500)
        self.assertTrue(graph.astar("mid_teleport_gotar", "mid_10_780000_850000", safety).ok)
        self.assertTrue(graph.astar("hib_teleport_tir_na_mbeo", "hib_10_336157_532604", safety).ok)
        mid_nodes = payload["regions"]["100"]["nodes"]
        self.assertTrue(any(node["id"] == "mid_10_780000_850000_g_0_2100" for node in mid_nodes))
        route = graph.route_between_points(
            100,
            dummy_pathing.PathPoint(780000, 850000, 4820),
            dummy_pathing.PathPoint(780000, 850000, 4820),
            max_node_distance=1200.0,
            safety=safety,
        )
        self.assertTrue(route.ok, route.reason)
        self.assertLess(math.hypot(route.nodes[-1].x - 780000, route.nodes[-1].y - 850000), 450.0)

    def test_hib_level_ten_party_route_detours_around_lucradan_field(self) -> None:
        import dummy_pathing

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "growth-route-graph.json"
            growth.write_growth_path_graph(path)
            graph = dummy_pathing.PathGraph.from_file(path)

        safety = dummy_pathing.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=2500)
        route = graph.astar("hib_teleport_tir_na_mbeo", "hib_10_336157_532604", safety)
        node_ids = [node.id for node in route.nodes]

        self.assertIn("hib_hib_teleport_tir_na_mbeo_336157_532604_detour_1", node_ids)
        self.assertIn("hib_hib_teleport_tir_na_mbeo_336157_532604_detour_2", node_ids)

    def test_growth_path_graph_samples_midpoint_ground_height_on_long_albion_level_fifty_routes(self) -> None:
        import dummy_pathing

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "growth-route-graph.json"
            growth.write_growth_path_graph(path)
            graph = dummy_pathing.PathGraph.from_file(path)

        detour_path_nodes = [
            node
            for node_id, node in graph.nodes.items()
            if node_id.startswith("alb_alb_teleport_yarley_s_farm_332701_669142_detour_1_path_")
        ]
        self.assertTrue(detour_path_nodes)
        node = detour_path_nodes[len(detour_path_nodes) // 2]
        sampled_z = growth.sample_route_z(
            growth.REALMS["alb"],
            growth.build_realm_height_samplers(),
            node.x,
            node.y,
            0,
        )

        self.assertEqual(node.z, sampled_z)
        self.assertGreater(node.z, 0)

    def test_albion_level_fifty_route_detours_around_cornish_giant_and_hamadryad_fields(self) -> None:
        import dummy_pathing

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "growth-route-graph.json"
            growth.write_growth_path_graph(path)
            graph = dummy_pathing.PathGraph.from_file(path)

        safety = dummy_pathing.PathSafety(max_direct_distance=150.0, max_edge_length=1800.0, max_height_delta=900)
        route = graph.astar("alb_teleport_yarley_s_farm", "alb_50", safety)
        node_ids = [node.id for node in route.nodes]

        self.assertTrue(route.ok, route.reason)
        self.assertIn("alb_alb_teleport_yarley_s_farm_332701_669142_detour_1", node_ids)
        self.assertIn("alb_alb_teleport_yarley_s_farm_332701_669142_detour_2", node_ids)
        self.assertIn("alb_alb_teleport_yarley_s_farm_332701_669142_detour_3", node_ids)
        self.assertIn("alb_alb_teleport_yarley_s_farm_332701_669142_detour_4", node_ids)
        self.assertGreater(
            min(math.hypot(node.x - 357435, node.y - 676520) for node in route.nodes),
            5000,
        )
        self.assertGreater(
            min(math.hypot(node.x - 350735, node.y - 681041) for node in route.nodes),
            9000,
        )
        self.assertGreater(
            min(math.hypot(node.x - 341378, node.y - 677453) for node in route.nodes),
            7000,
        )

    def test_mid_level_five_return_route_does_not_detour_through_level_one_variant_grid(self) -> None:
        import dummy_pathing

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "growth-route-graph.json"
            growth.write_growth_path_graph(path)
            graph = dummy_pathing.PathGraph.from_file(path)

        safety = dummy_pathing.PathSafety(max_direct_distance=1200.0, max_edge_length=1500.0, max_height_delta=900)
        route = graph.route_between_points(
            100,
            dummy_pathing.PathPoint(771013, 746838, 4634),
            dummy_pathing.PathPoint(766413, 742742, 5532),
            max_node_distance=1200.0,
            safety=safety,
        )

        self.assertTrue(route.ok)
        self.assertFalse(any(node.id.startswith("mid_1_775217_751401_g_") for node in route.nodes))
        self.assertLess(len(route.nodes), 35)

    def test_behavior_command_uses_path_graph_and_waypoints(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            party_external_member_names="RealTank,RealHealer",
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["hib"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=1,
            party_size=4,
            current_level=15,
            path_graph=Path("graph.json"),
        )

        self.assertIn("--path-graph", command)
        self.assertIn("graph.json", command)
        self.assertIn("--path-region", command)
        self.assertIn("200", command)
        self.assertIn("--path-last-mile-distance", command)
        self.assertEqual(command[command.index("--path-last-mile-distance") + 1], "1200.0")
        self.assertIn("--path-waypoint-ground-z-skip-delta", command)
        self.assertEqual(command[command.index("--path-waypoint-ground-z-skip-delta") + 1], "500")
        self.assertIn("--path-max-height-delta", command)
        self.assertEqual(command[command.index("--path-max-height-delta") + 1], "900")
        self.assertEqual(command[command.index("--attack-range") + 1], "350")
        self.assertEqual(command[command.index("--combat-direct-move-distance") + 1], "1500.0")
        self.assertEqual(command[command.index("--attack-target-in-view-prime-delay") + 1], "0.0")
        self.assertEqual(command[command.index("--party-external-member-names") + 1], "RealTank|RealHealer")
        self.assertIn("--melee-stick-attack", command)
        self.assertEqual(command[command.index("--melee-stick-attack-distance") + 1], "1800")
        self.assertEqual(command[command.index("--target-face-command-interval") + 1], "0.8")
        self.assertEqual(command[command.index("--melee-range-buffer") + 1], "300")
        self.assertEqual(command[command.index("--minimum-melee-stop-distance") + 1], "60")
        self.assertEqual(command[command.index("--movement-speed") + 1], "191.0")
        self.assertEqual(command[command.index("--target-loss-grace") + 1], "1")
        self.assertIn("--combat-home-leash-distance", command)
        self.assertEqual(command[command.index("--combat-home-leash-distance") + 1], "1200.0")
        self.assertNotIn("--allow-avoid-target-fallback", command)
        self.assertIn("--current-target-api-refresh", command)
        self.assertIn("--hunter-target-api-scout", command)
        self.assertEqual(command[command.index("--hunter-target-api-radius") + 1], "2200.0")
        self.assertEqual(command[command.index("--hunter-target-api-engage-distance") + 1], "1500.0")
        self.assertEqual(command[command.index("--hunter-target-max-ground-z-delta") + 1], "220")
        self.assertEqual(command[command.index("--hunter-target-max-attack-z-delta") + 1], "220")
        self.assertEqual(command[command.index("--hunter-min-time-left-for-new-target") + 1], "55")

        route_home_args = SimpleNamespace(**vars(args), growth_fast_travel="route-home")
        route_home_command = growth.build_behavior_command(
            args=route_home_args,
            realm=growth.REALMS["hib"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case-route-home"),
            segment_index=1,
            party_size=4,
            current_level=15,
            path_graph=Path("graph.json"),
        )
        self.assertNotIn("--startup-teleport-destination", route_home_command)
        self.assertIn("--startup-route-home-after-services", route_home_command)
        self.assertIn("--allow-network-disconnect-success", route_home_command)
        self.assertIn("--allow-party-safe-exit-partial-success", route_home_command)
        self.assertIn("--round-wall-timeout-seconds", route_home_command)
        self.assertIn("--allow-round-wall-timeout-success", route_home_command)
        self.assertEqual(
            route_home_command[route_home_command.index("--round-wall-timeout-seconds") + 1],
            str(int(args.segment_seconds + min(float(getattr(args, "safe_exit_max_seconds", 0.0) or 0.0), 30.0) + 20.0)),
        )
        self.assertEqual(
            route_home_command[route_home_command.index("--startup-route-home-after-services") + 1],
            "339898,516372,5199",
        )
        self.assertEqual(route_home_command[route_home_command.index("--route-home-api-retries") + 1], "5")
        self.assertEqual(route_home_command[route_home_command.index("--route-home-api-retry-delay") + 1], "1.0")
        self.assertEqual(route_home_command[route_home_command.index("--target-loss-grace") + 1], "1")
        low_route_home_args = SimpleNamespace(**vars(args), growth_fast_travel="route-home")
        self.assertEqual(growth.growth_target_loss_grace(low_route_home_args, 6, 2), "24")

        self.assertEqual(command[command.index("--max-target-level") + 1], "20")
        self.assertEqual(command[command.index("--max-target-level-delta") + 1], "3")
        self.assertIn("--reject-target-on-server-los-failure", command)
        self.assertEqual(command[command.index("--server-los-failure-target-cooldown") + 1], "45")
        self.assertEqual(command[command.index("--server-los-failure-kind-cooldown") + 1], "20")
        self.assertEqual(command[command.index("--server-los-failure-grace") + 1], "10")
        self.assertNotIn("--npc-max-age", command)
        self.assertIn("--live-control-file", command)
        self.assertEqual(command[command.index("--live-control-file") + 1], str(Path("case") / "live-control.json"))
        self.assertIn("--live-control-interval", command)
        self.assertEqual(command[command.index("--live-control-interval") + 1], "1.0")
        self.assertIn("--flee-use-sprint", command)
        self.assertEqual(command[command.index("--flee-health-percent") + 1], "15")
        self.assertEqual(command[command.index("--flee-pressure-health-percent") + 1], "20")
        self.assertEqual(command[command.index("--flee-step") + 1], "900")
        self.assertEqual(command[command.index("--flee-movement-speed") + 1], "280")
        self.assertIn("--flee-home", command)
        self.assertEqual(command[command.index("--flee-home") + 1], "345698,528897,5448")
        self.assertEqual(command[command.index("--flee-home-stop-distance") + 1], "120")
        self.assertIn("--flee-dynamic-safe-point", command)
        self.assertEqual(command[command.index("--flee-safe-threat-radius") + 1], "6000")
        self.assertEqual(command[command.index("--flee-safe-point-distance") + 1], "5200")

        self.assertEqual(command[command.index("--flee-critical-health-percent") + 1], "5")
        self.assertEqual(command[command.index("--flee-critical-safe-point-distance") + 1], "9000")
        self.assertIn("--flee-safe-api-scout", command)
        self.assertEqual(command[command.index("--flee-safe-replan-damage-grace") + 1], "6")
        self.assertEqual(command[command.index("--safe-exit-max-seconds") + 1], "90")
        self.assertEqual(command[command.index("--safe-exit-recent-damage-grace") + 1], "12")
        self.assertIn("--no-safe-exit-disengage-current-target", command)
        self.assertEqual(command[command.index("--required-target-recover-before-hunt-endurance-percent") + 1], "40")
        self.assertEqual(command[command.index("--flee-town-health-percent") + 1], "99")
        self.assertEqual(command[command.index("--flee-min-combat-seconds") + 1], "4")
        self.assertEqual(command[command.index("--flee-melee-counterattack-min-attacks") + 1], "3")
        self.assertEqual(command[command.index("--flee-melee-counterattack-health-floor") + 1], "5")
        self.assertEqual(command[command.index("--flee-melee-counterattack-max-distance") + 1], "1800")
        self.assertIn("--ground-z-map", command)
        self.assertIn(growth.REALMS["hib"].ground_z_map, command)
        self.assertIn("--waypoints", command)
        waypoints = command[command.index("--waypoints") + 1]
        self.assertRegex(waypoints, r"339898,516372,\d+")
        self.assertRegex(waypoints, r"340258,516732,\d+")
        self.assertIn("--required-target-home", command)
        self.assertRegex(command[command.index("--required-target-home") + 1], r"339898,516372,\d+")
        self.assertEqual(command[command.index("--required-target-home-stop-distance") + 1], "900")
        self.assertEqual(command[command.index("--required-target-home-hunt-distance") + 1], "1200.0")
        self.assertIn("--auto-loot", command)
        self.assertIn("--startup-command", command)
        startup_commands = [
            command[index + 1]
            for index, value in enumerate(command)
            if value == "--startup-command"
        ]
        self.assertEqual(startup_commands, ["/bind", "/sprint"])
        self.assertEqual(command[command.index("--party-follow-interval") + 1], "0.2")
        self.assertIn("--startup-service-npc-name", command)
        self.assertIn(growth.REALMS["hib"].startup_service_npc_name, command)
        self.assertIn("--startup-teleport-destination", command)
        self.assertEqual(command[command.index("--startup-teleport-destination") + 1], "Tir na mBeo")
        self.assertIn("--startup-teleport-warmup-whisper", command)
        self.assertEqual(command[command.index("--startup-teleport-warmup-whisper") + 1], "towns")
        self.assertIn("--startup-teleport-warmup-delay", command)
        self.assertEqual(command[command.index("--startup-teleport-warmup-delay") + 1], "1.6")
        self.assertIn("--startup-teleporter-npc-name", command)
        self.assertEqual(command[command.index("--startup-teleport-approach-distance") + 1], "80.0")
        self.assertIn("--login-retries", command)
        self.assertEqual(command[command.index("--login-retries") + 1], "5")
        self.assertIn("--party-assist-only", command)
        self.assertEqual(command[command.index("--party-invite-interval") + 1], "1")
        self.assertEqual(command[command.index("--party-accept-interval") + 1], "0.5")
        self.assertEqual(command[command.index("--party-min-ready") + 1], "4")
        self.assertNotIn("--party-require-leader-engaged", command)
        self.assertIn("--party-mark-pull-engaged", command)
        self.assertEqual(command[command.index("--party-pull-engage-distance") + 1], "1800")
        self.assertNotIn("--party-block-solo-required-retaliation", command)
        self.assertEqual(command[command.index("--party-pre-pull-home-stop-distance") + 1], "1600")
        self.assertIn("--party-rescue-aggro", command)
        self.assertIn("--party-rescue-before-objective-engaged", command)
        self.assertNotIn("--party-clear-objective-adds-before-engage", command)
        self.assertIn("--party-local-rescue-target", command)
        self.assertEqual(command[command.index("--party-local-rescue-max-distance") + 1], "1200")
        self.assertEqual(command[command.index("--party-healer-local-rescue-health-percent") + 1], "45")
        self.assertEqual(command[command.index("--party-rescue-objective-max-distance") + 1], "2400")
        self.assertEqual(command[command.index("--party-rescue-assist-after") + 1], "6")
        self.assertEqual(command[command.index("--party-rescue-emergency-assist-after") + 1], "2.0")
        self.assertNotIn("--start-x", command)
        self.assertNotIn("--start-y", command)

    def test_preservice_supervisor_does_not_quarantine_solo_after_one_death_by_default(self) -> None:
        args = preservice_supervisor.parse_args([])

        self.assertEqual(args.live_solo_death_no_progress_fatal_count, 3)
        self.assertEqual(args.live_death_loop_fatal_count, 3)

    def test_preservice_supervisor_rejects_disabling_completed_stall_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            args = preservice_supervisor.parse_args(["--base-run-dir", tmpdir])
            supervisor = preservice_supervisor.CaseSupervisor(args, [])
            Path(tmpdir, "control").mkdir(parents=True, exist_ok=True)
            args.completed_stall_fatal_segments = 2

            supervisor.handle_command({"command": "set_completed_stall_fatal_segments", "value": 0})

            self.assertEqual(args.completed_stall_fatal_segments, 2)
            events = Path(tmpdir, "case-events.jsonl").read_text(encoding="utf-8")
            self.assertIn("command_rejected", events)
            self.assertIn("completed_stall_fatal_segments must be at least 1", events)

    def test_growth_behavior_command_shortens_death_and_retreat_target_kind_cooldowns(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=150,
            ramp_up=0,
            login_retries=2,
            login_retry_delay=1.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            party_external_member_names="",
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["mid"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=16,
            party_size=1,
            current_level=7,
            path_graph=Path("graph.json"),
        )

        self.assertEqual(command[command.index("--target-death-cooldown") + 1], "24")
        self.assertEqual(command[command.index("--target-retreat-cooldown") + 1], "18")

    def test_behavior_command_can_skip_startup_teleport_for_fast_balance_resume(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=180,
            safe_exit_max_seconds=25,
            safe_exit_recent_damage_grace=5,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=2800,
            target_home_max_distance=6200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            party_external_member_names="",
            growth_skip_startup_teleport=True,
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=38,
            party_size=1,
            current_level=9,
            path_graph=Path("graph.json"),
        )

        self.assertNotIn("--startup-teleport-destination", command)
        self.assertNotIn("--startup-teleporter-npc-name", command)
        self.assertIn("--required-target-home", command)
        self.assertEqual(command[command.index("--safe-exit-max-seconds") + 1], "25")

    def test_merchant_only_route_home_segment_skips_hunting_and_startup_teleport(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=180,
            safe_exit_max_seconds=25,
            safe_exit_recent_damage_grace=5,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=2800,
            target_home_max_distance=6200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            party_external_member_names="",
            growth_fast_travel="route-home",
            growth_skip_startup_teleport=True,
            growth_merchant_only_segment=True,
            growth_merchant_npc_name="Leshorm Hael",
            growth_merchant_buy_slots=[9],
            growth_merchant_equip_slots=[40],
            growth_auto_sell_slots=[],
            growth_merchant_sell_party_slot_maps=[],
            growth_merchant_buy_party_slot_maps=[],
            growth_merchant_equip_party_slot_maps=[],
            growth_merchant_scan_seconds=1.0,
            growth_merchant_approach_distance=150.0,
            growth_merchant_approach_timeout=90.0,
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=20,
            party_size=1,
            current_level=7,
            path_graph=Path("graph.json"),
        )

        self.assertNotIn("--hunter", command)
        self.assertEqual(command[command.index("--behavior-profile") + 1], "custom")
        self.assertNotIn("--startup-teleport-destination", command)
        self.assertNotIn("--startup-teleporter-npc-name", command)
        self.assertNotIn("--startup-route-home-after-services", command)
        self.assertIn("--startup-merchant-npc-name", command)
        self.assertEqual(command[command.index("--startup-merchant-npc-name") + 1], "Leshorm Hael")
        self.assertEqual(command[command.index("--startup-merchant-buy-slot") + 1], "9")
        self.assertEqual(command[command.index("--startup-merchant-equip-slot") + 1], "40")

    def test_merchant_only_segment_skips_startup_teleport_without_route_home(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=180,
            safe_exit_max_seconds=25,
            safe_exit_recent_damage_grace=5,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=2800,
            target_home_max_distance=6200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            party_external_member_names="",
            growth_fast_travel="off",
            growth_skip_startup_teleport=True,
            growth_merchant_only_segment=True,
            growth_merchant_npc_name="Leshorm Hael",
            growth_merchant_buy_slots=[9],
            growth_merchant_equip_slots=[40],
            growth_auto_sell_slots=[],
            growth_merchant_sell_party_slot_maps=[],
            growth_merchant_buy_party_slot_maps=[],
            growth_merchant_equip_party_slot_maps=[],
            growth_merchant_scan_seconds=1.0,
            growth_merchant_approach_distance=150.0,
            growth_merchant_approach_timeout=90.0,
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=20,
            party_size=1,
            current_level=7,
            path_graph=Path("graph.json"),
        )

        self.assertNotIn("--hunter", command)
        self.assertEqual(command[command.index("--behavior-profile") + 1], "custom")
        self.assertNotIn("--startup-teleport-destination", command)
        self.assertNotIn("--startup-teleporter-npc-name", command)
        self.assertNotIn("--startup-route-home-after-services", command)
        self.assertIn("--startup-merchant-npc-name", command)

    def test_alb_level_seven_solo_routes_to_avalon_rot_worm_camp(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=2200,
            target_home_max_distance=6200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=3,
                party_size=1,
                current_level=7,
                path_graph=Path("graph.json"),
            )
            payload = json.loads((case_dir / "live-control.json").read_text(encoding="utf-8"))

        self.assertEqual(growth.target_levels(7, 1, "alb"), (5, 5, 0))
        self.assertEqual(payload["baseline_min_target_level"], 5)
        self.assertEqual(payload["baseline_max_target_level"], 6)
        self.assertIn("--startup-teleport-destination", command)
        self.assertEqual(command[command.index("--startup-teleport-destination") + 1], "Avalon Marsh")
        self.assertEqual(command[command.index("--require-target-name") + 1], "rot worm")
        self.assertNotIn("--require-target-name-exact", command)
        self.assertIn("--prefer-target-name", command)
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "rot worm")
        self.assertIn("--avoid-target-name", command)
        self.assertIn("faerie bell-wether", command[command.index("--avoid-target-name") + 1].split(","))
        self.assertIn("emerald snake", command[command.index("--avoid-target-name") + 1].split(","))
        self.assertGreaterEqual(float(command[command.index("--target-home-max-distance") + 1]), 9000.0)
        self.assertGreaterEqual(float(command[command.index("--required-target-home-hunt-distance") + 1]), 9000.0)
        self.assertEqual(command[command.index("--min-target-level") + 1], "5")
        self.assertEqual(command[command.index("--max-target-level") + 1], "6")
        self.assertNotIn("--target-auto-lowest-visible-level", command)
        self.assertNotIn("--allow-preferred-low-con-fallback", command)
        self.assertEqual(command[command.index("--low-health-rest-percent") + 1], "60")
        self.assertEqual(command[command.index("--low-health-rest-resume-percent") + 1], "70")
        self.assertEqual(command[command.index("--flee-health-percent") + 1], "55")
        self.assertEqual(command[command.index("--flee-critical-health-percent") + 1], "45")
        self.assertEqual(command[command.index("--flee-melee-counterattack-health-floor") + 1], "55")

    def test_explicit_xp_required_disables_alb_l6_preferred_low_con_fallback(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=180,
            ramp_up=5,
            login_retries=12,
            login_retry_delay=5.0,
            api_port=5000,
            max_target_distance=2800.0,
            target_home_max_distance=10000.0,
            combat_home_leash_distance=10000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            startup_delay=12.0,
            growth_fast_travel="route-home",
            growth_allow_lower_xp_gear_farm=True,
            growth_allow_lower_xp_target_plan=False,
            require_segment_xp=True,
            explicit_options={"require_segment_xp"},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=1,
                party_size=1,
                current_level=6,
                path_graph=Path("graph.json"),
            )

        self.assertEqual(command[command.index("--min-target-level") + 1], "4")
        self.assertEqual(command[command.index("--max-target-level") + 1], "4")
        self.assertIn("--prefer-target-name", command)
        self.assertNotIn("--target-auto-lowest-visible-level", command)
        self.assertNotIn("--allow-preferred-low-con-fallback", command)
        self.assertNotIn("--preferred-low-con-min-level", command)

    def test_low_party_growth_command_uses_carry_target_commit_rules(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=180,
            safe_exit_max_seconds=25,
            safe_exit_recent_damage_grace=5,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=2800,
            target_home_max_distance=6200.0,
            combat_home_leash_distance=1200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            startup_delay=0.0,
            growth_fast_travel="route-home",
            growth_allow_lower_xp_gear_farm=False,
            growth_route_level_override=17,
            growth_route_level_is_carry_target=True,
            growth_target_level_override=9,
            growth_target_plan_override=growth.growth_party_carry_target_plan(9, 4),
            growth_equip_party_carry_gear=True,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["mid"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=60,
                party_size=4,
                current_level=9,
                path_graph=Path("graph.json"),
            )

        self.assertNotIn("--require-target-name", command)
        self.assertNotIn("--prefer-target-name", command)
        self.assertEqual(command[command.index("--max-target-level") + 1], "16")
        self.assertNotIn("--allow-avoid-target-fallback", command)
        self.assertEqual(command[command.index("--party-min-ready") + 1], "4")
        self.assertEqual(command[command.index("--party-assist-interval") + 1], "0.6")
        self.assertEqual(command[command.index("--party-assist-attack-delay") + 1], "0.0")
        self.assertNotIn("--party-require-leader-engaged", command)
        self.assertNotIn("--party-block-solo-required-retaliation", command)
        self.assertIn("--party-rescue-aggro", command)
        self.assertIn("--party-rescue-before-objective-engaged", command)
        self.assertNotIn("--party-clear-objective-adds-before-engage", command)
        self.assertIn("--party-local-rescue-target", command)
        self.assertEqual(command[command.index("--party-rescue-max-distance") + 1], "2200")
        self.assertEqual(command[command.index("--party-rescue-engaged-distance") + 1], "650")
        self.assertEqual(command[command.index("--party-rescue-objective-max-distance") + 1], "2400")
        self.assertEqual(command[command.index("--party-local-rescue-max-distance") + 1], "1200")
        self.assertEqual(command[command.index("--party-healer-local-rescue-health-percent") + 1], "45")
        self.assertIn("--party-disable-required-home-anchor-defer", command)
        self.assertEqual(command[command.index("--companion-initial-command-mode") + 1], "attack")
        self.assertEqual(command[command.index("--party-resurrect-interval") + 1], "0")
        self.assertEqual(
            command[command.index("--party-slot-rotations") + 1],
            "melee-burst,melee-basic,melee-basic,none",
        )
        self.assertEqual(command[command.index("--startup-train-level") + 1], "18")
        self.assertIn("--startup-service-equip-slot", command)
        self.assertIn("41", command[command.index("--startup-service-equip-slot") + 1].split(","))
        self.assertEqual(command[command.index("--startup-service-equip-party-slot") + 1], "0,1,2")
        self.assertEqual(command[command.index("--party-follow-distance") + 1], "600")
        self.assertEqual(command[command.index("--passive-xp-leech-follow-distance") + 1], "1200")
        self.assertEqual(command[command.index("--party-follow-teleport-distance") + 1], "0")
        self.assertEqual(command[command.index("--party-follow-teleport-stop-distance") + 1], "1200")
        self.assertIn("--party-carry-counterattack-travel-aggro", command)
        self.assertEqual(command[command.index("--party-ready-max-leader-distance") + 1], "1800")
        self.assertEqual(command[command.index("--party-pre-pull-home-stop-distance") + 1], "1600")
        self.assertEqual(command[command.index("--flee-health-percent") + 1], "15")
        self.assertEqual(command[command.index("--flee-pressure-health-percent") + 1], "20")
        self.assertEqual(command[command.index("--flee-critical-health-percent") + 1], "5")
        self.assertEqual(command[command.index("--required-target-tank-commit-health-percent") + 1], "5")

    def test_route_and_combat_overrides_bound_target_ceiling(self) -> None:
        self.assertEqual(growth.growth_passive_xp_leech_follow_distance(1, 8), 1400)
        self.assertEqual(growth.growth_passive_xp_leech_follow_distance(9, 4), 1200)
        self.assertEqual(growth.growth_passive_xp_leech_follow_distance(4, 2), 900)
        self.assertEqual(growth.growth_party_carry_target_plan(1, 2), (2, 3, 1))
        self.assertEqual(growth.growth_party_carry_target_plan(1, 4), (4, 4, 1))
        self.assertEqual(growth.growth_party_carry_target_plan(1, 8), (6, 6, 1))
        self.assertEqual(growth.growth_party_carry_target_plan(3, 2), (3, 4, 1))
        self.assertEqual(growth.growth_party_carry_target_plan(3, 8), (6, 6, 1))
        self.assertEqual(growth.growth_party_carry_target_plan(5, 2), (5, 6, 1))
        self.assertEqual(growth.growth_party_carry_target_plan(7, 2), (8, 9, 2))
        self.assertEqual(growth.growth_party_carry_target_plan(8, 8), (12, 12, 2))
        self.assertEqual(growth.growth_party_carry_target_plan_for_combat_level((6, 7, 1), 13), (8, 8, 1))
        self.assertEqual(growth.growth_party_carry_target_plan_for_combat_level((8, 9, 2), 13), (8, 9, 2))
        self.assertEqual(
            growth.capped_specs_for_level("Hammer|50;Shields|42;Parry|39;Sword|1", 10),
            "Hammer|10;Shields|10;Parry|10;Sword|1",
        )
        self.assertEqual(
            growth.low_level_tank_growth_specs(
                "Slash|39;Thrust|1;Crush|1;Two Handed|1;Chants|48;Shields|42;Parry|13",
                realm_key="alb",
                class_id=1,
                level=7,
                party_size=1,
                growth_stage="gear",
            ),
            "Slash|5;Thrust|1;Crush|1;Two Handed|1;Chants|4;Shields|5;Parry|1",
        )
        self.assertEqual(growth.growth_party_carry_level_for_party(7, 2), 14)
        self.assertEqual(growth.growth_party_carry_level_for_party(9, 4), 18)
        self.assertEqual(growth.growth_party_carry_level_for_party(6, 8), 15)
        self.assertEqual(growth.growth_party_carry_party_slots(4), [0, 1, 2])
        self.assertEqual(
            growth.growth_party_carry_level(
                SimpleNamespace(growth_party_carry_level_offset=2, current_party_size=8),
                1,
            ),
            8,
        )
        self.assertEqual(
            growth.growth_party_carry_level(
                SimpleNamespace(growth_party_carry_level_offset=0, current_party_size=2),
                4,
            ),
            6,
        )
        self.assertEqual(
            growth.growth_party_carry_level(
                SimpleNamespace(growth_party_carry_level_offset=0, current_party_size=4),
                3,
            ),
            7,
        )
        self.assertEqual(
            growth.growth_party_carry_level(
                SimpleNamespace(growth_party_carry_level_offset=12, current_party_size=4),
                6,
            ),
            13,
        )
        self.assertEqual(growth.growth_party_carry_max_non_grey_level_for_target(4), 6)
        self.assertEqual(growth.growth_party_carry_max_non_grey_level_for_target(5), 7)
        self.assertEqual(growth.growth_party_carry_max_non_grey_level_for_target(6), 8)
        self.assertEqual(growth.growth_party_carry_max_non_grey_level_for_target(7), 12)
        self.assertEqual(growth.growth_party_carry_max_non_grey_level_for_target(12), 17)
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=180,
            safe_exit_max_seconds=25,
            safe_exit_recent_damage_grace=5,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=2800,
            target_home_max_distance=6200.0,
            combat_home_leash_distance=1200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            startup_delay=0.0,
            growth_fast_travel="route-home",
            growth_allow_lower_xp_gear_farm=False,
            growth_route_level_override=5,
            growth_target_level_override=3,
            growth_target_plan_override=growth.growth_party_carry_target_plan(3, 8),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=54,
                party_size=8,
                current_level=3,
                path_graph=Path("graph.json"),
            )

        self.assertEqual(command[command.index("--player-level") + 1], "3")
        self.assertEqual(command[command.index("--ideal-target-level") + 1], "5")
        self.assertEqual(command[command.index("--min-target-level") + 1], "5")
        self.assertEqual(command[command.index("--max-target-level") + 1], "7")

    def test_mid_party8_level_two_carry_plan_uses_xp_eligible_band(self) -> None:
        self.assertEqual(growth.growth_party_carry_target_level_for_realm(2, 8, "mid"), 4)
        self.assertEqual(growth.growth_party_carry_target_plan_for_realm(2, 8, "mid"), (3, 4, 1))
        self.assertEqual(growth.growth_party_carry_target_plan_for_realm(2, 8, "hib"), (7, 7, 3))
        self.assertEqual(growth.growth_party_carry_target_plan_for_realm(2, 8, "alb"), (7, 7, 1))

    def test_ungeared_party8_carry_level_stays_xp_eligible_for_low_target_band(self) -> None:
        args = SimpleNamespace(
            growth_party_carry_level_offset=12,
            current_party_size=8,
            growth_equip_party_carry_gear=False,
        )

        self.assertEqual(growth.growth_party_carry_level_for_realm(args, 2, 8, "alb"), 6)
        self.assertEqual(growth.growth_party_carry_level_for_realm(args, 2, 8, "mid"), 5)

    def test_mid_duo_low_carry_plan_caps_target_ceiling(self) -> None:
        self.assertEqual(growth.growth_party_carry_target_level_for_realm(5, 2, "mid"), 5)
        self.assertEqual(growth.growth_party_carry_target_plan_for_realm(5, 2, "mid"), (4, 5, 1))
        self.assertEqual(growth.growth_party_carry_target_level_for_realm(6, 2, "mid"), 5)
        self.assertEqual(growth.growth_party_carry_target_plan_for_realm(6, 2, "mid"), (4, 5, 1))
        self.assertEqual(growth.growth_party_carry_target_level_for_realm(7, 2, "mid"), 6)
        self.assertEqual(growth.growth_party_carry_target_plan_for_realm(7, 2, "mid"), (5, 6, 1))
        self.assertEqual(
            growth.growth_party_carry_level_for_realm(
                SimpleNamespace(
                    growth_party_carry_level_offset=12,
                    current_party_size=2,
                    growth_equip_party_carry_gear=True,
                ),
                7,
                2,
                "mid",
            ),
            18,
        )
        self.assertEqual(
            growth.growth_party_carry_target_plan_for_combat_level((5, 6, 1), 18),
            (13, 13, 1),
        )

    def test_hib_duo_low_carry_plan_stays_within_carry_capacity(self) -> None:
        self.assertEqual(growth.growth_party_carry_target_level_for_realm(1, 2, "hib"), 1)
        self.assertEqual(growth.growth_party_carry_target_plan_for_realm(1, 2, "hib"), (1, 1, 0))
        self.assertEqual(growth.growth_party_carry_target_level_for_realm(2, 2, "hib"), 2)
        self.assertEqual(growth.growth_party_carry_target_plan_for_realm(2, 2, "hib"), (1, 2, 0))
        self.assertEqual(
            growth.growth_party_carry_level_for_realm(
                SimpleNamespace(
                    growth_party_carry_level_offset=12,
                    current_party_size=2,
                    growth_equip_party_carry_gear=True,
                ),
                1,
                2,
                "hib",
            ),
            13,
        )
        self.assertEqual(growth.growth_low_health_rest_percent(1, 2, "hib"), 25)
        self.assertEqual(growth.growth_low_health_rest_resume_percent(1, 2, "hib"), 65)
        self.assertEqual(growth.growth_flee_health_percent(1, 2, "hib"), 15)
        self.assertEqual(growth.growth_flee_pressure_health_percent(1, 2, "hib"), 20)
        self.assertEqual(growth.growth_flee_critical_health_percent(1, 2, "hib"), 5)
        self.assertEqual(growth.growth_required_target_tank_commit_health_percent(1, 2, "hib"), 55)
        self.assertEqual(growth.growth_party_carry_target_level_for_realm(5, 2, "hib"), 6)
        self.assertEqual(growth.growth_party_carry_target_plan_for_realm(5, 2, "hib"), (5, 6, 1))
        self.assertEqual(growth.growth_party_carry_target_level_for_realm(6, 2, "hib"), 7)
        self.assertEqual(growth.growth_party_carry_target_plan_for_realm(6, 2, "hib"), (6, 7, 1))

    def test_hib_duo_ungeared_carry_plan_keeps_plus_one_target_band(self) -> None:
        plan = growth.growth_ungeared_party_carry_target_plan(6, 2, "hib", (6, 7, 1))
        self.assertEqual(plan, (6, 7, 1))

    def test_hib_duo_ungeared_level_two_stays_exact_level_safe(self) -> None:
        plan = growth.growth_ungeared_party_carry_target_plan(2, 2, "hib", (1, 2, 0))
        self.assertEqual(plan, (1, 2, 0))

    def test_hib_duo_level_one_command_caps_target_ceiling(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=150,
            safe_exit_max_seconds=25,
            safe_exit_recent_damage_grace=5,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=6500.0,
            combat_home_leash_distance=1200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            party_external_member_names="",
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=29,
            growth_fast_travel="route-home",
            growth_route_preflight=False,
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            growth_route_level_is_carry_target=True,
            growth_party_carry_level_offset=3,
            growth_route_level_override=1,
            growth_target_level_override=1,
            growth_target_plan_override=(1, 1, 0),
            dry_run=False,
            run_dir="",
        )
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["hib"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=7,
                party_size=2,
                current_level=1,
                path_graph=Path("graph.json"),
            )

        self.assertEqual(command[command.index("--min-target-level") + 1], "1")
        self.assertEqual(command[command.index("--ideal-target-level") + 1], "1")
        self.assertEqual(command[command.index("--max-target-level") + 1], "1")
        self.assertEqual(command[command.index("--low-health-rest-percent") + 1], "25")
        self.assertEqual(command[command.index("--flee-health-percent") + 1], "15")
        self.assertEqual(command[command.index("--flee-pressure-health-percent") + 1], "20")
        self.assertEqual(command[command.index("--flee-critical-health-percent") + 1], "5")

    def test_hib_duo_level_one_carry_route_uses_safe_non_gray_starter_band(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )

        target = growth.growth_party_carry_target_level_for_realm(1, 2, "hib")
        route = growth.select_growth_route_point(args, growth.REALMS["hib"], target, 2)

        self.assertEqual(target, 1)
        self.assertIn(route.prefer, {"large frog", "water beetle larva", "badger cub"})
        self.assertGreaterEqual(route.mob_level, 1)
        self.assertGreaterEqual(route.mob_count, 10)

    def test_hib_duo_level_seven_carry_uses_dense_non_gray_water_beetle_band(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=27,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
        )

        target = growth.growth_party_carry_target_level_for_realm(7, 2, "hib")
        plan = growth.growth_party_carry_target_plan_for_realm(7, 2, "hib")
        route = growth.select_growth_route_point(args, growth.REALMS["hib"], target, 2)

        self.assertEqual(target, 9)
        self.assertEqual(plan, (8, 9, 2))
        self.assertEqual(route.prefer, "water beetle")
        self.assertEqual(route.mob_level, 7)
        self.assertNotIn(route.prefer, route.avoid.split(","))
        self.assertEqual(route.teleport_destination, "Tir na mBeo")
        self.assertGreaterEqual(route.mob_count, 10)

    def test_mid_party8_level_two_route_uses_highest_level_xp_camp(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            growth_route_player_level=2,
            growth_target_level_override=2,
            growth_target_plan_override=growth.growth_party_carry_target_plan_for_realm(2, 8, "mid"),
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 4, 8)

        self.assertEqual(route.prefer, "wood-eater worker")
        self.assertEqual(route.mob_level, 4)
        self.assertNotEqual(route.prefer, "ghost light")

    def test_hib_level_eleven_solo_hill_toad_route_allows_z_and_home_spread(self) -> None:
        args = SimpleNamespace(
            max_target_distance=2200.0,
            target_home_max_distance=1400.0,
            growth_fast_travel="route-home",
        )
        route = growth.select_growth_route_point(args, growth.REALMS["hib"], 11, 1)

        self.assertEqual(route.prefer, "hill toad")
        self.assertEqual(
            growth.growth_target_home_max_distance(args, 11, 1, "hib"),
            6500.0,
        )
        self.assertEqual(
            growth.growth_max_target_distance(args, 11, 1, "hib", route),
            5200.0,
        )
        self.assertEqual(growth.growth_hunter_target_max_ground_z_delta(11, 1, "hib"), 1200)

    def test_alb_level_eight_solo_routes_to_non_grey_cutpurse_fallback(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=2200,
            target_home_max_distance=6200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=4,
                party_size=1,
                current_level=8,
                path_graph=Path("graph.json"),
            )
            payload = json.loads((case_dir / "live-control.json").read_text(encoding="utf-8"))

        self.assertEqual(growth.target_levels(8, 1, "alb"), (6, 6, 0))
        self.assertEqual(payload["baseline_min_target_level"], 6)
        self.assertEqual(payload["baseline_max_target_level"], 6)
        self.assertEqual(command[command.index("--startup-teleport-destination") + 1], "Campacorentin Station")
        self.assertEqual(command[command.index("--require-target-name") + 1], "rot worm")
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "rot worm")
        self.assertEqual(command[command.index("--min-target-level") + 1], "6")
        self.assertEqual(command[command.index("--max-target-level") + 1], "6")
        self.assertEqual(command[command.index("--required-target-recover-before-home-health-percent") + 1], "60")
        self.assertEqual(command[command.index("--low-health-rest-percent") + 1], "60")
        self.assertEqual(command[command.index("--low-health-rest-resume-percent") + 1], "70")
        self.assertEqual(command[command.index("--flee-health-percent") + 1], "55")

    def test_alb_level_nine_solo_targets_safe_live_level_seven_adders(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=2200,
            target_home_max_distance=6200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=5,
                party_size=1,
                current_level=9,
                path_graph=Path("graph.json"),
            )
            payload = json.loads((case_dir / "live-control.json").read_text(encoding="utf-8"))

        self.assertEqual(growth.target_levels(9, 1, "alb"), (7, 7, 0))
        self.assertEqual(payload["baseline_min_target_level"], 7)
        self.assertEqual(payload["baseline_max_target_level"], 7)
        self.assertEqual(command[command.index("--startup-teleport-destination") + 1], "Prydwen Keep")
        self.assertEqual(command[command.index("--required-target-home") + 1], "592858,549006,2764")
        self.assertIn("592858,549006,2764", command[command.index("--waypoints") + 1])
        self.assertNotIn("595800,526000", command[command.index("--waypoints") + 1])
        self.assertEqual(command[command.index("--require-target-name") + 1], "river racer")
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "river racer")
        self.assertIn("adder", command[command.index("--avoid-target-name") + 1].split(","))
        self.assertNotIn("river racer", command[command.index("--avoid-target-name") + 1].split(","))
        self.assertNotIn("bear", command[command.index("--avoid-target-name") + 1].split(","))
        self.assertNotIn("boar", command[command.index("--avoid-target-name") + 1].split(","))
        self.assertIn("large skeleton", command[command.index("--avoid-target-name") + 1])
        self.assertIn("rot worm", command[command.index("--avoid-target-name") + 1].split(","))
        self.assertIn("filidh", command[command.index("--avoid-target-name") + 1].split(","))
        self.assertEqual(command[command.index("--target-nearby-avoid-name") + 1], "river racer")
        self.assertEqual(command[command.index("--objective-entry-aggro-avoid-radius") + 1], "1800")
        self.assertEqual(command[command.index("--hunter-target-max-attack-z-delta") + 1], "360")
        self.assertEqual(command[command.index("--min-target-level") + 1], "7")
        self.assertEqual(command[command.index("--max-target-level") + 1], "7")
        self.assertEqual(command[command.index("--travel-aggro-avoid-seconds") + 1], "30")
        self.assertEqual(command[command.index("--flee-health-percent") + 1], "55")
        self.assertEqual(command[command.index("--flee-critical-health-percent") + 1], "35")

    def test_alb_level_nine_rotting_zombie_command_uses_narrow_entry_avoidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "runtime-failure-memory.csv"
            memory_path.write_text(
                "timestamp_utc,case,realm,party_size,segment,level,reason,action,target_name,target_level,source,expires_segment\n"
                "2026-07-05T00:00:00Z,alb-p1,alb,1,56,9,combat_no_kill,avoid_target,river racer,7,combat_csv,59\n"
                "2026-07-05T00:01:00Z,alb-p1,alb,1,58,9,combat_no_kill,avoid_target,undead filidh,7,combat_csv,61\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                host="127.0.0.1",
                port=10300,
                segment_seconds=45,
                ramp_up=2,
                login_retries=5,
                login_retry_delay=3.0,
                api_port=5000,
                max_target_distance=2200,
                target_home_max_distance=6200.0,
                target_timeout=65,
                combat_interval=1.5,
                target_pool=5,
                smooth_move_interval=0.2,
                movement_speed=191.0,
                path_last_mile_distance=1200.0,
                ground_z_offset=0,
                encounter_log_interval=3.0,
                nav_api_url="http://127.0.0.1:5000",
                live_api_url="",
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(memory_path),
                growth_current_segment_index=59,
                growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
                growth_route_case_index=0,
                growth_fast_travel="route-home",
            )
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=59,
                party_size=1,
                current_level=9,
                path_graph=Path("graph.json"),
            )

        self.assertEqual(command[command.index("--startup-route-home-after-services") + 1], "527242,624780,1965")
        self.assertEqual(command[command.index("--require-target-name") + 1], "rotting zombie")
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "rotting zombie")
        self.assertEqual(command[command.index("--objective-entry-aggro-avoid-radius") + 1], "2200")
        avoid_targets = command[command.index("--avoid-target-name") + 1].split(",")
        self.assertIn("devout filidh", avoid_targets)
        self.assertIn("pixie scout", avoid_targets)
        self.assertIn("픽시 정찰병", avoid_targets)
        self.assertNotIn("rotting zombie", avoid_targets)

    def test_alb_level_nine_shortage_recovery_uses_level_six_gear_route(self) -> None:
        args = SimpleNamespace(growth_allow_lower_xp_gear_farm=True)
        plans = {"growthalb": growth.GrowthItemPlan([], [], buy_shortage_copper=2278)}

        self.assertEqual(
            growth.growth_shortage_recovery_route_override(
                args,
                growth.REALMS["alb"],
                current_level=9,
                party_size=1,
                item_plans=plans,
            ),
            (8, 6),
        )
        behavior_args = SimpleNamespace()
        self.assertTrue(
            growth.apply_growth_shortage_recovery_route_override(
                behavior_args,
                args,
                growth.REALMS["alb"],
                current_level=9,
                party_size=1,
                item_plans=plans,
            )
        )
        self.assertEqual(behavior_args.growth_route_level_override, 8)
        self.assertEqual(behavior_args.growth_target_level_override, 6)
        self.assertEqual(behavior_args.growth_target_plan_override, (6, 6, 0))

    def test_checkpoint_route_home_updates_account_csv_start_position(self) -> None:
        args = SimpleNamespace(checkpoint_start_location="route-home", position_step=80)
        rows = [
            {
                "username": "growthalb2101",
                "start_x": "534900",
                "start_y": "477500",
                "start_z": "2200",
                "zone_id": "1",
            },
            {
                "username": "growthalb2102",
                "start_x": "534900",
                "start_y": "477500",
                "start_z": "2200",
                "zone_id": "1",
            },
        ]

        growth.apply_checkpoint_start_to_account_rows(args, rows, growth.REALMS["alb"], 9, 1)

        self.assertEqual(rows[0]["start_x"], "592858")
        self.assertEqual(rows[0]["start_y"], "549006")
        self.assertEqual(rows[0]["start_z"], "2764")
        self.assertEqual(rows[0]["zone_id"], "1")
        self.assertEqual(rows[1]["start_x"], "592938")
        self.assertEqual(rows[1]["start_y"], "549086")

    def test_checkpoint_route_home_uses_hunting_index_start_position(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "alb,1,20,19,20,21,bandit,19,7,526821,614578,1847,6,0,100,500,Caer Ulfwych,5745,216\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                checkpoint_start_location="route-home",
                position_step=80,
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_route_preflight=False,
                growth_allow_lower_xp_target_plan=True,
                growth_allow_lower_xp_gear_farm=True,
            )
            rows = [
                {
                    "username": "growthalb2101",
                    "start_x": "534900",
                    "start_y": "477500",
                    "start_z": "2200",
                    "zone_id": "1",
                }
            ]

            growth.apply_checkpoint_start_to_account_rows(args, rows, growth.REALMS["alb"], 20, 1)

        self.assertEqual(rows[0]["start_x"], "526821")
        self.assertEqual(rows[0]["start_y"], "614578")
        self.assertEqual(rows[0]["start_z"], "1841")
        self.assertEqual(rows[0]["zone_id"], "1")

    def test_party_carry_route_home_stages_tracked_leech_inside_xp_range(self) -> None:
        args = SimpleNamespace(checkpoint_start_location="route-home", position_step=80, ground_z_offset=0)
        route = growth.RoutePoint(level=11, x=100000, y=200000, z=3000)
        rows = [
            {"username": f"growthalb24{i}", "growth_role": "carry" if i < 8 else "tracked"}
            for i in range(1, 9)
        ]

        growth.apply_checkpoint_start_to_account_rows(
            args,
            rows,
            growth.REALMS["alb"],
            8,
            8,
            start_point=route,
        )

        self.assertEqual(rows[0]["start_x"], "100000")
        self.assertEqual(rows[0]["start_y"], "200000")
        self.assertEqual(rows[6]["start_x"], "100480")
        self.assertEqual(rows[6]["start_y"], "200480")
        self.assertEqual(rows[7]["start_x"], "100450")
        self.assertEqual(rows[7]["start_y"], "200000")
        self.assertEqual(rows[7]["zone_id"], "1")

    def test_alb_level_eight_shortage_farm_uses_non_grey_targets_for_gear_money(self) -> None:
        self.assertTrue(
            growth.should_use_growth_gear_farm_route(
                SimpleNamespace(growth_allow_lower_xp_gear_farm=True),
                growth.REALMS["alb"],
                current_level=8,
                party_size=1,
                item_plans={"growthalb1501": growth.GrowthItemPlan([], [], buy_shortage_copper=48)},
            )
        )
        self.assertFalse(
            growth.should_use_growth_gear_farm_route(
                SimpleNamespace(growth_allow_lower_xp_gear_farm=True),
                growth.REALMS["alb"],
                current_level=8,
                party_size=1,
                item_plans={"growthalb1501": growth.GrowthItemPlan([], [], buy_shortage_copper=0)},
            )
        )
        self.assertFalse(
            growth.should_use_growth_gear_farm_route(
                SimpleNamespace(growth_allow_lower_xp_gear_farm=True),
                growth.REALMS["alb"],
                current_level=8,
                party_size=1,
                item_plans={"growthalb1501": growth.GrowthItemPlan([], [], buy_shortage_copper=48)},
                snapshots={
                    "growthalb1501": growth.CharacterSnapshot(
                        account="growthalb1501",
                        name="GrowthAlb1501",
                        character_id="char-1",
                        level=8,
                        experience=0,
                        realm=1,
                        class_id=1,
                        specs="Slash|8;Shields|6",
                        region=1,
                        x=0,
                        y=0,
                        z=0,
                        deaths=0,
                        money_copper=2,
                        inventory_rows=0,
                        inventory_items=0,
                    )
                },
            )
        )

        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=2200,
            target_home_max_distance=6200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            growth_route_level_override=8,
            growth_target_level_override=8,
            growth_target_plan_override=(6, 6, 0),
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=5,
                party_size=1,
                current_level=8,
                path_graph=Path("graph.json"),
            )
            payload = json.loads((case_dir / "live-control.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["baseline_player_level"], 8)
        self.assertEqual(payload["baseline_min_target_level"], 6)
        self.assertEqual(payload["baseline_max_target_level"], 6)
        self.assertEqual(command[command.index("--player-level") + 1], "8")
        self.assertEqual(command[command.index("--startup-teleport-destination") + 1], "Campacorentin Station")
        self.assertIn("486334,592350", command[command.index("--waypoints") + 1])
        self.assertTrue(command[command.index("--required-target-home") + 1].startswith("486334,592350,"))
        self.assertEqual(command[command.index("--require-target-name") + 1], "rot worm")
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "rot worm")
        self.assertEqual(command[command.index("--min-target-level") + 1], "6")
        self.assertEqual(command[command.index("--max-target-level") + 1], "6")

    def test_level_seven_solo_buy_shortage_uses_recovery_targets_without_free_gear(self) -> None:
        args = SimpleNamespace(growth_allow_lower_xp_gear_farm=True)
        plans = {"growthmid": growth.GrowthItemPlan([], [], buy_shortage_copper=16)}

        self.assertEqual(
            growth.growth_shortage_recovery_route_override(
                args,
                growth.REALMS["mid"],
                current_level=7,
                party_size=1,
                item_plans=plans,
            ),
            (7, 5),
        )
        self.assertEqual(
            growth.growth_shortage_recovery_route_override(
                args,
                growth.REALMS["mid"],
                current_level=9,
                party_size=1,
                item_plans={"growthmid": growth.GrowthItemPlan([], [41], buy_shortage_copper=67)},
            ),
            (9, 7),
        )
        self.assertEqual(
            growth.growth_shortage_recovery_route_override(
                args,
                growth.REALMS["alb"],
                current_level=7,
                party_size=1,
                item_plans={"growthalb": growth.GrowthItemPlan([], [], buy_shortage_copper=25)},
            ),
            (7, 5),
        )
        self.assertEqual(
            growth.growth_shortage_recovery_route_override(
                args,
                growth.REALMS["hib"],
                current_level=7,
                party_size=1,
                item_plans={"growthhib": growth.GrowthItemPlan([], [], buy_shortage_copper=25)},
            ),
            (7, 5),
        )
        self.assertEqual(
            growth.growth_shortage_recovery_route_override(
                args,
                growth.REALMS["mid"],
                current_level=8,
                party_size=1,
                item_plans={"growthmid": growth.GrowthItemPlan([], [], buy_shortage_copper=19)},
            ),
            (8, 6),
        )
        self.assertEqual(
            growth.growth_shortage_recovery_route_override(
                args,
                growth.REALMS["alb"],
                current_level=8,
                party_size=1,
                item_plans={"growthalb": growth.GrowthItemPlan([], [], buy_shortage_copper=32)},
            ),
            (8, 6),
        )
        self.assertIsNone(
            growth.growth_shortage_recovery_route_override(
                args,
                growth.REALMS["hib"],
                current_level=4,
                party_size=1,
                item_plans={"growthhib": growth.GrowthItemPlan([], [], buy_shortage_copper=3)},
            )
        )
        self.assertEqual(
            growth.growth_shortage_recovery_route_override(
                args,
                growth.REALMS["mid"],
                current_level=7,
                party_size=1,
                item_plans={"growthmid": growth.GrowthItemPlan([], [40], buy_shortage_copper=16)},
            ),
            (7, 5),
        )
        self.assertIsNone(
            growth.growth_shortage_recovery_route_override(
                args,
                growth.REALMS["mid"],
                current_level=7,
                party_size=1,
                item_plans={
                    "growthmid": growth.GrowthItemPlan(
                        [],
                        [40],
                        buy_slots=[3],
                        buy_shortage_copper=16,
                    )
                },
            )
        )
        self.assertIsNone(
            growth.growth_shortage_recovery_route_override(
                args,
                growth.REALMS["mid"],
                current_level=7,
                party_size=2,
                item_plans=plans,
            )
        )

        behavior_args = SimpleNamespace()
        self.assertTrue(
            growth.apply_growth_shortage_recovery_route_override(
                behavior_args,
                args,
                growth.REALMS["mid"],
                current_level=7,
                party_size=1,
                item_plans=plans,
            )
        )
        self.assertEqual(behavior_args.growth_route_level_override, 7)
        self.assertEqual(behavior_args.growth_target_level_override, 5)
        self.assertTrue(behavior_args.growth_allow_lower_xp_target_plan)
        self.assertEqual(behavior_args.growth_shortage_recovery_player_level, 7)
        self.assertEqual(behavior_args.growth_target_plan_override, (5, 5, 0))

        self.assertEqual(
            growth.growth_shortage_recovery_route_override(
                args,
                growth.REALMS["alb"],
                current_level=9,
                party_size=1,
                item_plans={"growthalb": growth.GrowthItemPlan([], [], buy_shortage_copper=2278)},
            ),
            (8, 6),
        )
        behavior_args = SimpleNamespace()
        self.assertTrue(
            growth.apply_growth_shortage_recovery_route_override(
                behavior_args,
                args,
                growth.REALMS["alb"],
                current_level=9,
                party_size=1,
                item_plans={"growthalb": growth.GrowthItemPlan([], [], buy_shortage_copper=2278)},
            )
        )
        self.assertEqual(behavior_args.growth_route_level_override, 8)
        self.assertEqual(behavior_args.growth_target_level_override, 6)
        self.assertEqual(behavior_args.growth_target_plan_override, (6, 6, 0))

        behavior_args = SimpleNamespace()
        self.assertTrue(
            growth.apply_growth_shortage_recovery_route_override(
                behavior_args,
                args,
                growth.REALMS["mid"],
                current_level=9,
                party_size=1,
                item_plans={"growthmid": growth.GrowthItemPlan([], [41], buy_shortage_copper=67)},
            )
        )
        self.assertEqual(behavior_args.growth_route_level_override, 9)
        self.assertEqual(behavior_args.growth_target_level_override, 7)
        self.assertTrue(behavior_args.growth_allow_lower_xp_target_plan)
        self.assertEqual(behavior_args.growth_shortage_recovery_player_level, 9)
        self.assertEqual(behavior_args.growth_target_plan_override, (7, 7, 0))

        route_args = SimpleNamespace(
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=0,
            growth_fast_travel="route-home",
            growth_shortage_recovery_player_level=9,
            growth_target_level_override=7,
            growth_target_plan_override=(7, 7, 0),
        )
        mid_level_nine_route = growth.select_growth_route_point(route_args, growth.REALMS["mid"], 9, 1)
        self.assertEqual(mid_level_nine_route.prefer, "army ant worker")
        self.assertEqual(mid_level_nine_route.mob_level, 7)
        self.assertEqual((mid_level_nine_route.x, mid_level_nine_route.y), (719301, 770132))

        behavior_args = SimpleNamespace()
        self.assertTrue(
            growth.apply_growth_shortage_recovery_route_override(
                behavior_args,
                args,
                growth.REALMS["mid"],
                current_level=8,
                party_size=1,
                item_plans={"growthmid": growth.GrowthItemPlan([], [], buy_shortage_copper=19)},
            )
        )
        self.assertEqual(behavior_args.growth_route_level_override, 8)
        self.assertEqual(behavior_args.growth_target_level_override, 6)
        self.assertTrue(behavior_args.growth_allow_lower_xp_target_plan)
        self.assertEqual(behavior_args.growth_shortage_recovery_player_level, 8)
        self.assertEqual(behavior_args.growth_target_plan_override, (6, 6, 1))

        behavior_args = SimpleNamespace()
        self.assertTrue(
            growth.apply_growth_shortage_recovery_route_override(
                behavior_args,
                args,
                growth.REALMS["alb"],
                current_level=8,
                party_size=1,
                item_plans={"growthalb": growth.GrowthItemPlan([], [], buy_shortage_copper=32)},
            )
        )
        self.assertEqual(behavior_args.growth_route_level_override, 8)
        self.assertEqual(behavior_args.growth_target_level_override, 6)
        self.assertTrue(behavior_args.growth_allow_lower_xp_target_plan)
        self.assertEqual(behavior_args.growth_shortage_recovery_player_level, 8)
        self.assertEqual(behavior_args.growth_target_plan_override, (6, 6, 0))

        alb_level_eight_route_args = SimpleNamespace(
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=27,
            case_name="solo-s150-r2-alb-r001",
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
            growth_route_preflight=False,
            growth_shortage_recovery_player_level=8,
            growth_target_level_override=6,
            growth_target_plan_override=(6, 6, 0),
        )
        alb_level_eight_recovery_route = growth.select_growth_route_point(
            alb_level_eight_route_args,
            growth.REALMS["alb"],
            8,
            1,
        )
        self.assertEqual(alb_level_eight_recovery_route.prefer, "undead filidh")
        self.assertEqual(alb_level_eight_recovery_route.mob_level, 6)
        self.assertEqual(alb_level_eight_recovery_route.level, 8)

        behavior_args = SimpleNamespace()
        self.assertTrue(
            growth.apply_growth_shortage_recovery_route_override(
                behavior_args,
                args,
                growth.REALMS["alb"],
                current_level=7,
                party_size=1,
                item_plans={"growthalb": growth.GrowthItemPlan([], [], buy_shortage_copper=25)},
            )
        )
        self.assertEqual(behavior_args.growth_route_level_override, 7)
        self.assertEqual(behavior_args.growth_target_level_override, 5)
        self.assertTrue(behavior_args.growth_allow_lower_xp_target_plan)
        self.assertEqual(behavior_args.growth_shortage_recovery_player_level, 7)
        self.assertEqual(behavior_args.growth_target_plan_override, (5, 5, 1))

        behavior_args = SimpleNamespace()
        self.assertTrue(
            growth.apply_growth_shortage_recovery_route_override(
                behavior_args,
                args,
                growth.REALMS["hib"],
                current_level=7,
                party_size=1,
                item_plans={"growthhib": growth.GrowthItemPlan([], [], buy_shortage_copper=25)},
            )
        )
        self.assertEqual(behavior_args.growth_route_level_override, 7)
        self.assertEqual(behavior_args.growth_target_level_override, 5)
        self.assertTrue(behavior_args.growth_allow_lower_xp_target_plan)
        self.assertEqual(behavior_args.growth_shortage_recovery_player_level, 7)
        self.assertEqual(behavior_args.growth_target_plan_override, (5, 5, 0))

    def test_mid_level_five_small_party_filters_hunting_index_below_command_band(self) -> None:
        args = SimpleNamespace(
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            growth_target_level_override=0,
            growth_target_plan_override=None,
        )
        candidates = [
            growth.route_point(5, 810920, 726686, 4729, "wood-eater", "", "", source="hunting-index", mob_level=3),
            growth.route_point(5, 786637, 723034, 4722, "wood-eater worker", "", "", source="hunting-index", mob_level=4),
            growth.route_point(5, 772957, 725582, 4754, "vein spider", "", "", source="hunting-index", mob_level=5),
        ]

        filtered = growth.filter_growth_hunting_index_candidates_for_target_band(
            args,
            candidates,
            realm_key="mid",
            level=5,
            party_size=2,
        )

        self.assertNotIn("wood-eater", {route.prefer for route in filtered})
        self.assertIn("wood-eater worker", {route.prefer for route in filtered})
        self.assertIn("vein spider", {route.prefer for route in filtered})

    def test_party_item_plan_includes_carry_members(self) -> None:
        accounts = ["carry1", "carry2", "tracked1"]
        tracked = ["tracked1"]

        self.assertEqual(
            growth.growth_item_plan_account_names(accounts, tracked, 3),
            accounts,
        )
        self.assertEqual(
            growth.growth_item_plan_account_names(accounts, tracked, 1),
            tracked,
        )

    def test_mid_level_five_small_party_uses_safe_worker_route_without_carry_tuning(self) -> None:
        args = SimpleNamespace(
            growth_hunting_index="tools/test-output/preservice-growth-hunting-index-latest.csv",
            growth_route_case_index=16,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=False,
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            growth_party_carry_count=0,
        )

        duo_route = growth.select_growth_route_point(args, growth.REALMS["mid"], 5, 2)
        duo_level_six_route = growth.select_growth_route_point(args, growth.REALMS["mid"], 6, 2)
        party4_route = growth.select_growth_route_point(args, growth.REALMS["mid"], 5, 4)
        party4_level_six_route = growth.select_growth_route_point(args, growth.REALMS["mid"], 6, 4)

        self.assertEqual(duo_route.prefer, "young grendelorm")
        self.assertEqual(duo_route.mob_level, 5)
        self.assertIn("vein spider", duo_route.avoid.split(","))
        self.assertEqual(duo_level_six_route.prefer, "carrion crawler")
        self.assertEqual(duo_level_six_route.mob_level, 6)
        self.assertIn("wood-eater hunter", duo_level_six_route.avoid.split(","))
        self.assertIn("wood-eater worker", duo_level_six_route.avoid.split(","))
        self.assertEqual(party4_route.prefer, "carrion crawler")
        self.assertEqual(party4_route.mob_level, 6)
        self.assertIn("vein spider", party4_route.avoid.split(","))
        self.assertEqual(party4_level_six_route.prefer, "carrion crawler")
        self.assertEqual(party4_level_six_route.mob_level, 6)
        self.assertIn("vein spider", party4_level_six_route.avoid.split(","))

    def test_mid_level_seven_shortage_recovery_does_not_avoid_selected_reward_candidate(self) -> None:
        args = SimpleNamespace(
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            growth_shortage_recovery_player_level=7,
        )
        route = growth.route_point(
            7,
            813800,
            688337,
            4842,
            "vein spider",
            "",
            "",
            source="hunting-index",
            mob_level=5,
            mob_count=9,
        )

        filtered = growth.growth_filter_shortage_recovery_failed_avoid_targets(
            args,
            "dryad sprig,vein spider,wayward ghoul",
            "mid",
            7,
            1,
            route=route,
        )

        self.assertNotIn("vein spider", filtered)
        self.assertIn("dryad sprig", filtered)
        self.assertIn("wayward ghoul", filtered)

    def test_level_ten_behavior_command_resets_live_control_and_paths_to_safe_teleporter_hub(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=2200,
            target_home_max_distance=6200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            (case_dir / "live-control.json").write_text('{"min_target_level": 1}\n', encoding="utf-8")
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=3,
                party_size=1,
                current_level=10,
                path_graph=Path("graph.json"),
            )
            payload = json.loads((case_dir / "live-control.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["baseline_min_target_level"], 7)
        self.assertEqual(payload["baseline_max_target_level"], 8)
        self.assertIn("--startup-teleporter-home", command)
        self.assertEqual(command[command.index("--startup-teleporter-home") + 1], growth.startup_teleporter_home(growth.REALMS["alb"]))
        self.assertIn("--startup-teleport-destination", command)
        self.assertEqual(command[command.index("--startup-teleport-destination") + 1], "Castle Sauvage")
        self.assertIn("--require-target-name", command)
        self.assertIn("adder", command[command.index("--require-target-name") + 1])
        self.assertIn("--avoid-target-name", command)
        self.assertIn("giant spider", command[command.index("--avoid-target-name") + 1])
        self.assertIn("bandit henchman", command[command.index("--avoid-target-name") + 1])
        self.assertNotIn("--allow-preferred-low-con-fallback", command)
        self.assertNotIn("--preferred-low-con-min-level", command)
        self.assertEqual(command[command.index("--flee-home") + 1], "584151,477177,2600")
        self.assertEqual(command[command.index("--flee-home-stop-distance") + 1], "120")
        self.assertEqual(command[command.index("--flee-town-health-percent") + 1], "99")

    def test_level_ten_party_flees_to_route_teleport_town(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=2200,
            target_home_max_distance=6200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["mid"],
                accounts_csv=Path("accounts.csv"),
                case_dir=case_dir,
                segment_index=1,
                party_size=2,
                current_level=10,
                path_graph=Path("graph.json"),
            )

        self.assertEqual(command[command.index("--startup-teleport-destination") + 1], "Gotar")
        self.assertEqual(command[command.index("--flee-home") + 1], "771152,836380,4624")
        self.assertEqual(command[command.index("--flee-home-stop-distance") + 1], "120")
        self.assertEqual(command[command.index("--flee-town-health-percent") + 1], "99")
        self.assertEqual(command[command.index("--required-target-tank-commit-health-percent") + 1], "5")
        self.assertEqual(command[command.index("--max-target-distance") + 1], "2200.0")
        self.assertEqual(command[command.index("--target-home-max-distance") + 1], "2200.0")
        self.assertEqual(command[command.index("--combat-home-leash-distance") + 1], "2200.0")
        self.assertEqual(command[command.index("--required-target-home-hunt-distance") + 1], "2200.0")

    def test_early_growth_direct_combat_move_uses_safe_level_six_minimum_scan_radius(self):
        args = SimpleNamespace(
            target_home_max_distance=1400.0,
            max_target_distance=2200.0,
            combat_home_leash_distance=1200.0,
        )

        self.assertEqual(growth.growth_max_target_distance(args, 6), 2800.0)
        self.assertEqual(growth.growth_max_target_distance(args, 5, 1, "hib"), 5200.0)
        self.assertEqual(growth.growth_combat_direct_move_distance(args, 6), 2800.0)
        self.assertEqual(growth.growth_combat_direct_move_distance(args, 15), 1500.0)

    def test_albion_behavior_command_uses_ground_z_sampler(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=1,
            party_size=1,
            current_level=1,
            path_graph=Path("graph.json"),
        )

        self.assertIn("--ground-z-map", command)
        self.assertIn(growth.REALMS["alb"].ground_z_map, command)
        self.assertIn("--require-target-name", command)
        self.assertEqual(command[command.index("--require-target-name") + 1], "green snake")
        self.assertIn("--prefer-target-name", command)
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "green snake")
        self.assertNotIn("--target-auto-lowest-visible-level", command)
        self.assertIn("--avoid-target-name", command)
        self.assertIn("young cutpurse", command[command.index("--avoid-target-name") + 1])
        self.assertIn("boar piglet", command[command.index("--avoid-target-name") + 1])
        self.assertEqual(command[command.index("--min-target-level") + 1], "0")
        self.assertEqual(command[command.index("--max-target-level") + 1], "1")
        self.assertEqual(command[command.index("--max-target-level-delta") + 1], "1")
        self.assertIn("--server-correction-smoothing", command)
        self.assertNotIn("--party-assist-only", command)
        self.assertEqual(command[command.index("--target-home-max-distance") + 1], "6200.0")
        self.assertEqual(command[command.index("--combat-home-leash-distance") + 1], "6200.0")
        self.assertEqual(command[command.index("--combat-chase-max-distance") + 1], "2200.0")
        self.assertEqual(command[command.index("--max-target-distance") + 1], "1500.0")
        self.assertEqual(command[command.index("--low-health-rest-percent") + 1], "30")
        self.assertEqual(command[command.index("--low-health-rest-resume-percent") + 1], "75")
        self.assertEqual(command[command.index("--flee-health-percent") + 1], "30")
        self.assertEqual(command[command.index("--flee-critical-health-percent") + 1], "20")
        self.assertEqual(command[command.index("--flee-melee-counterattack-health-floor") + 1], "20")
        self.assertEqual(command[command.index("--required-target-tank-commit-health-percent") + 1], "10")
        self.assertEqual(command[command.index("--flee-safe-point-distance") + 1], "5200")
        self.assertEqual(command[command.index("--flee-critical-safe-point-distance") + 1], "9000")
        self.assertIn("--allow-avoid-target-fallback", command)
        self.assertIn("--current-target-api-refresh", command)
        self.assertIn("--hunter-target-api-scout", command)

    def test_hib_level_five_solo_growth_command_rejects_no_xp_low_con_fallback(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["hib"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=1,
            party_size=1,
            current_level=5,
            path_graph=Path("graph.json"),
        )

        self.assertIn("--prefer-target-name", command)
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "mudman")
        self.assertEqual(command[command.index("--ideal-target-level") + 1], "4")
        self.assertEqual(command[command.index("--min-target-level") + 1], "4")
        self.assertEqual(command[command.index("--max-target-level") + 1], "4")
        self.assertEqual(command[command.index("--max-target-level-delta") + 1], "0")
        self.assertNotIn("--target-auto-lowest-visible-level", command)
        self.assertNotIn("--allow-preferred-low-con-fallback", command)
        self.assertNotIn("--preferred-low-con-min-level", command)

    def test_hib_level_six_solo_growth_command_rejects_no_xp_low_con_fallback(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["hib"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=1,
            party_size=1,
            current_level=6,
            path_graph=Path("graph.json"),
        )

        self.assertEqual(command[command.index("--ideal-target-level") + 1], "4")
        self.assertEqual(command[command.index("--min-target-level") + 1], "4")
        self.assertEqual(command[command.index("--max-target-level") + 1], "4")
        self.assertEqual(command[command.index("--max-target-level-delta") + 1], "0")
        self.assertEqual(command[command.index("--max-target-distance") + 1], "3600.0")
        self.assertEqual(command[command.index("--combat-direct-move-distance") + 1], "3600.0")
        self.assertEqual(command[command.index("--hunter-target-api-radius") + 1], "3600.0")
        self.assertEqual(command[command.index("--hunter-target-api-engage-distance") + 1], "3600.0")
        self.assertEqual(command[command.index("--hunter-target-max-ground-z-delta") + 1], "500")
        self.assertEqual(command[command.index("--target-home-max-distance") + 1], "10000.0")
        self.assertEqual(command[command.index("--low-health-rest-percent") + 1], "60")
        self.assertEqual(command[command.index("--low-health-rest-resume-percent") + 1], "70")
        self.assertNotIn("--target-auto-lowest-visible-level", command)
        self.assertNotIn("--allow-preferred-low-con-fallback", command)
        self.assertNotIn("--preferred-low-con-min-level", command)

    def test_level_six_live_supervisor_keeps_bounded_engage_limit(self) -> None:
        args = SimpleNamespace(
            live_supervisor_interval=3.0,
            live_supervisor_step=350.0,
            live_supervisor_max_engage=2800.0,
            live_supervisor_max_radius=5200.0,
            segment_seconds=120.0,
            startup_delay=12.0,
            max_target_distance=2200.0,
        )

        command = growth.build_live_supervisor_command(args, Path("case"), current_level=6)

        self.assertEqual(command[command.index("--max-engage") + 1], "2800.0")
        self.assertEqual(command[command.index("--hold") + 1], "320.0")

    def test_hibernia_level_five_live_supervisor_keeps_route_engage_limit(self) -> None:
        args = SimpleNamespace(
            live_supervisor_interval=3.0,
            live_supervisor_step=350.0,
            live_supervisor_max_engage=2800.0,
            live_supervisor_max_radius=5200.0,
            segment_seconds=120.0,
            startup_delay=12.0,
            max_target_distance=2200.0,
        )

        command = growth.build_live_supervisor_command(
            args,
            Path("case"),
            current_level=5,
            party_size=1,
            realm_key="hib",
        )

        self.assertEqual(command[command.index("--max-engage") + 1], "5200.0")

    def test_mid_duo_level_ten_live_supervisor_uses_selected_route_engage_limit(self) -> None:
        args = SimpleNamespace(
            live_supervisor_interval=3.0,
            live_supervisor_step=350.0,
            live_supervisor_max_engage=2800.0,
            live_supervisor_max_radius=5200.0,
            segment_seconds=120.0,
            startup_delay=12.0,
            max_target_distance=2200.0,
            growth_fast_travel="route-home",
        )
        route = growth.route_point(
            10,
            754088,
            782578,
            4778,
            "silverscale drakeling",
            source="hunting-index",
            mob_level=9,
            mob_count=5,
        )

        command = growth.build_live_supervisor_command(
            args,
            Path("case"),
            current_level=10,
            party_size=2,
            realm_key="mid",
            selected_route=route,
        )

        self.assertEqual(command[command.index("--max-engage") + 1], "2200.0")

    def test_live_monitor_flags_rest_recover_under_damage_no_progress(self) -> None:
        rows = [
            {
                "elapsed": 42.0,
                "event": "behavior_state_change",
                "behavior_state": "RestRecover",
                "behavior_state_age": 0.0,
                "damage_taken": 0,
                "damage_done": 0,
                "current_target": 0,
                "leader_engaged": False,
            },
            {
                "elapsed": 50.0,
                "event": "server_message",
                "behavior_state": "RestRecover",
                "behavior_state_age": 8.0,
                "damage_taken": 10,
                "damage_done": 0,
                "current_target": 0,
                "categories": ["damage_taken"],
            },
            {
                "elapsed": 63.0,
                "event": "server_message",
                "behavior_state": "RestRecover",
                "behavior_state_age": 21.0,
                "damage_taken": 20,
                "damage_done": 0,
                "current_target": 0,
                "categories": ["damage_taken"],
            },
            {
                "elapsed": 70.0,
                "event": "server_message",
                "behavior_state": "RestRecover",
                "behavior_state_age": 28.0,
                "damage_taken": 32,
                "damage_done": 0,
                "current_target": 0,
                "categories": ["damage_taken"],
                "health_percent": 82,
                "rescue_target_name": "rotting zombie",
            },
        ]

        fatal = live_monitor.detect_fatal_stall(rows, min_elapsed=60.0)

        self.assertIsNotNone(fatal)
        reason, details = fatal
        self.assertEqual(reason, "rest_recover_under_damage_no_progress")
        self.assertEqual(details["rest_damage_events"], 3)

    def test_live_monitor_does_not_abort_active_combat(self) -> None:
        rows = [
            {
                "elapsed": 90.0,
                "event": "server_message",
                "behavior_state": "RestRecover",
                "behavior_state_age": 35.0,
                "damage_taken": 60,
                "damage_done": 20,
                "current_target": 123,
                "categories": ["damage_taken"],
            }
        ]

        self.assertIsNone(live_monitor.detect_fatal_stall(rows, min_elapsed=60.0))

    def test_live_monitor_does_not_abort_recent_flee_recovery_progress(self) -> None:
        rows = []
        for index in range(11):
            rows.append(
                {
                    "elapsed": 40.0 + index * 3.0,
                    "event": "encounter_tick",
                    "behavior_state": "TravelToObjective",
                    "damage_taken": 34,
                    "damage_done": 0,
                    "current_target": 0,
                    "leader_engaged": False,
                    "x": 485000 + index * 120,
                    "y": 598000,
                }
            )
        rows.extend(
            [
                {
                    "elapsed": 73.0,
                    "event": "flee_extend",
                    "behavior_state": "DropAggroAndRecover",
                    "damage_taken": 34,
                    "damage_done": 0,
                    "current_target": 0,
                    "leader_engaged": False,
                    "destination": "flee-home",
                },
                {
                    "elapsed": 86.0,
                    "event": "encounter_tick",
                    "behavior_state": "DropAggroAndRecover",
                    "behavior_state_age": 35.0,
                    "damage_taken": 34,
                    "damage_done": 0,
                    "current_target": 0,
                    "leader_engaged": False,
                    "health_percent": 95,
                },
            ]
        )

        self.assertIsNone(live_monitor.detect_fatal_stall(rows, min_elapsed=60.0))

    def test_live_monitor_aborts_objective_recovery_without_recent_flee_progress(self) -> None:
        rows = [
            {
                "elapsed": 40.0 + index * 4.0,
                "event": "encounter_tick",
                "behavior_state": "DropAggroAndRecover" if index % 2 else "TravelToObjective",
                "damage_taken": 34,
                "damage_done": 0,
                "current_target": 0,
                "leader_engaged": False,
            }
            for index in range(14)
        ]

        fatal = live_monitor.detect_fatal_stall(rows, min_elapsed=60.0)

        self.assertIsNotNone(fatal)
        self.assertEqual(fatal[0], "objective_recovery_loop_no_progress")

    def test_segment_summary_records_live_abort_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            summary_path = base / "segment-001-summary.json"
            combat_path = base / "segment-001-combat.csv"
            combat_path.write_text("username,round,target_id,target_name,outcome\n", encoding="utf-8")
            args = SimpleNamespace(
                growth_failure_target_memory=True,
                growth_runtime_failure_memory_csv=str(base / "runtime-failure-memory.csv"),
                growth_current_segment_index=1,
            )

            bottlenecks = {"no_engagement", growth.live_abort_bottleneck_reason("rest_recover_under_damage_no_progress")}
            growth.write_growth_segment_summary_json(
                summary_path,
                args=args,
                case_name="alb-p1",
                realm=growth.REALMS["alb"],
                party_size=1,
                segment_index=1,
                current_level=10,
                route_level=10,
                route=growth.route_point(10, 1, 2, 3, "rotting zombie"),
                metrics=growth.empty_metric_summary(),
                combat_csv=combat_path,
                bottleneck_reasons=bottlenecks,
                xp_effective_delta=0,
                xp_effective_by_account={"growthalb040": 0},
                require_kill=True,
                require_xp=True,
                aggregate_xp_ok=False,
                account_xp_ok=True,
                rc=2,
                live_abort_reason="rest_recover_under_damage_no_progress",
            )
            payload = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["result"]["live_abort_reason"], "rest_recover_under_damage_no_progress")
        self.assertIn("live_abort_rest_recover_under_damage_no_progress", payload["bottleneck_reasons"])
        self.assertEqual(payload["next_recommendation"], "inspect_live_abort_json_and_fix_root_cause_before_rerun")

    def test_run_commands_concurrently_terminates_on_live_abort_file(self) -> None:
        class FakeProcess:
            instances: list["FakeProcess"] = []

            def __init__(self, command: list[str]) -> None:
                self.command = command
                self.returncode: int | None = None
                self.terminated = False
                FakeProcess.instances.append(self)

            def poll(self) -> int | None:
                return self.returncode

            def terminate(self) -> None:
                self.terminated = True
                self.returncode = -15

            def wait(self, timeout: float | None = None) -> int:
                if self.returncode is None:
                    self.returncode = 0
                return self.returncode

            def kill(self) -> None:
                self.returncode = -9

        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            (case_dir / "live-abort.json").write_text(
                json.dumps({"reason": "rest_recover_under_damage_no_progress"}) + "\n",
                encoding="utf-8",
            )
            commands = [
                [sys.executable, "behavior-dummy-client.py"],
                [sys.executable, "monitor-dummy-growth-live.py", "--case-dir", str(case_dir)],
            ]
            original_popen = growth.subprocess.Popen
            try:
                growth.subprocess.Popen = FakeProcess
                rc = growth.run_commands_concurrently(commands, dry_run=False)
            finally:
                growth.subprocess.Popen = original_popen

        self.assertEqual(rc, 1)
        self.assertTrue(all(process.terminated for process in FakeProcess.instances))

    def test_route_home_low_party_uses_wide_target_radius(self) -> None:
        args = SimpleNamespace(
            growth_fast_travel="route-home",
            max_target_distance=1500.0,
            growth_route_level_is_carry_target=True,
        )
        route = growth.route_point(12, 807490, 680515, 5000, "small hill cat")

        self.assertEqual(growth.growth_max_target_distance(args, 1, 8, "mid", route), 6500.0)
        self.assertEqual(growth.growth_hunter_target_api_radius(args, 1, 8, "mid", route), 6500.0)
        self.assertEqual(growth.growth_hunter_target_api_engage_distance(args, 1, 8, "mid", route), 6500.0)
        self.assertEqual(growth.growth_combat_chase_max_distance(1, 8, args, "mid", route), 6500.0)

    def test_party_carry_route_fallback_lowers_target_plan_to_route_mob_band(self) -> None:
        args = SimpleNamespace(
            growth_target_plan_override=(11, 12, 1),
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            growth_route_player_level=1,
        )
        route = growth.route_point(
            5,
            807349,
            679515,
            4949,
            "small hill cat",
            source="hunting-index",
            mob_level=8,
        )

        adjusted = growth.adjust_party_carry_target_plan_for_route_fallback(
            route,
            current_level=1,
            party_size=8,
            realm_key="mid",
            min_target=11,
            ideal_target=12,
            max_delta=1,
        )
        preflight_min, preflight_max = growth.growth_route_preflight_level_band(
            args,
            route,
            realm_key="mid",
            current_level=1,
            party_size=8,
        )

        self.assertEqual(adjusted, (4, 8, 2))
        self.assertEqual((preflight_min, preflight_max), (4, 10))

    def test_party_carry_route_fallback_ignores_mobs_below_tracked_level(self) -> None:
        route = growth.route_point(
            2,
            808982,
            727923,
            4720,
            "water strider",
            source="hunting-index",
            mob_level=1,
        )

        adjusted = growth.adjust_party_carry_target_plan_for_route_fallback(
            route,
            current_level=2,
            party_size=8,
            realm_key="mid",
            min_target=3,
            ideal_target=4,
            max_delta=1,
        )

        self.assertEqual(adjusted, (3, 4, 1))

    def test_party_carry_static_route_fallback_lowers_mid_small_hill_cat_band(self) -> None:
        args = SimpleNamespace(
            growth_target_plan_override=(11, 12, 1),
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            growth_fast_travel="route-home",
            growth_route_level_is_carry_target=True,
            growth_route_player_level=1,
        )
        route = growth.route_point(
            10,
            807285,
            680511,
            5000,
            "small hill cat",
            "wolf spiderling,hill person,huldu stalker",
            teleport_destination="Fort Veldon",
            mob_level=8,
        )

        adjusted = growth.adjust_party_carry_target_plan_for_route_fallback(
            route,
            current_level=1,
            party_size=8,
            realm_key="mid",
            min_target=11,
            ideal_target=12,
            max_delta=1,
        )
        preflight_min, preflight_max = growth.growth_route_preflight_level_band(
            args,
            route,
            realm_key="mid",
            current_level=1,
            party_size=8,
        )

        self.assertEqual(adjusted, (4, 8, 2))
        self.assertEqual((preflight_min, preflight_max), (4, 10))

    def test_party_carry_route_fallback_reapplies_carry_non_grey_floor_and_ceiling(self) -> None:
        args = SimpleNamespace(
            growth_party_carry_level_offset=12,
            current_party_size=2,
            growth_equip_party_carry_gear=True,
        )

        self.assertEqual(
            growth.enforce_party_carry_non_grey_target_plan(args, 4, 2, 1, 3, 1),
            (12, 12, 6),
        )
        self.assertEqual(
            growth.enforce_party_carry_non_grey_target_plan(args, 7, 2, 5, 6, 1, "mid"),
            (13, 13, 1),
        )

    def test_party_carry_behavior_plan_drives_route_level_override(self) -> None:
        cases = (
            ("alb", 2, 7, (13, 13, 1), 13, 14),
            ("mid", 4, 8, (15, 15, 2), 15, 17),
            ("hib", 4, 7, (14, 14, 2), 14, 16),
            ("hib", 2, 3, (11, 11, 6), 11, 17),
        )
        for realm_key, party_size, level, expected_plan, expected_route, expected_max in cases:
            with self.subTest(realm=realm_key, party=party_size, level=level):
                args = SimpleNamespace(
                    growth_party_carry_level_offset=12,
                    current_party_size=party_size,
                    growth_party_carry_count=-1,
                    growth_equip_party_carry_gear=True,
                    growth_failure_target_memory=False,
                )

                plan = growth.growth_party_behavior_carry_target_plan(args, level, party_size, realm_key, level)

                self.assertEqual(plan, expected_plan)
                self.assertEqual(max(1, int(plan[1])), expected_route)
                self.assertEqual(
                    growth.growth_command_max_target_level(level, int(plan[1]), int(plan[2]), party_size),
                    expected_max,
                )

    def test_ungeared_party_carry_behavior_uses_tracked_xp_target_band(self) -> None:
        args = SimpleNamespace(
            growth_party_carry_level_offset=12,
            current_party_size=4,
            growth_party_carry_count=-1,
            growth_equip_party_carry_gear=False,
            growth_failure_target_memory=False,
        )

        plan = growth.growth_party_behavior_carry_target_plan(args, 6, 4, "alb", 18)

        self.assertEqual(plan, (5, 6, 1))

    def test_party_carry_preflight_uses_behavior_target_floor_for_route_level_override(self) -> None:
        args = SimpleNamespace(
            growth_target_level_override=5,
            growth_target_plan_override=(5, 6, 1),
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            growth_fast_travel="route-home",
            growth_party_carry_level_offset=12,
            current_party_size=2,
            growth_equip_party_carry_gear=True,
        )
        route = growth.route_point(
            5,
            810246,
            727005,
            4680,
            "wood-eater",
            source="hunting-index",
            mob_level=3,
        )

        preflight_min, preflight_max = growth.growth_route_preflight_level_band(
            args,
            route,
            realm_key="mid",
            current_level=6,
            party_size=2,
        )

        self.assertEqual((preflight_min, preflight_max), (12, 18))

    def test_ungeared_party_carry_preflight_keeps_tracked_xp_target_band(self) -> None:
        args = SimpleNamespace(
            growth_target_level_override=6,
            growth_target_plan_override=(5, 6, 1),
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            growth_fast_travel="route-home",
            growth_party_carry_level_offset=12,
            current_party_size=4,
            growth_party_carry_count=-1,
            growth_equip_party_carry_gear=False,
        )
        route = growth.route_point(
            6,
            572918,
            525352,
            2466,
            "small bear",
            source="hunting-index",
            mob_level=6,
        )

        preflight_min, preflight_max = growth.growth_route_preflight_level_band(
            args,
            route,
            realm_key="alb",
            current_level=6,
            party_size=4,
        )

        self.assertEqual((preflight_min, preflight_max), (5, 7))

    def test_mid_duo_level_ten_carry_preflight_uses_carry_reward_floor(self) -> None:
        args = SimpleNamespace(
            growth_target_level_override=10,
            growth_target_plan_override=(8, 9, 1),
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            growth_fast_travel="route-home",
            growth_route_preflight=True,
            dry_run=False,
            growth_route_level_is_carry_target=True,
            growth_route_player_level=10,
            growth_party_carry_level_offset=12,
            current_party_size=2,
            growth_party_carry_count=-1,
            growth_equip_party_carry_gear=False,
        )
        route = growth.route_point(
            9,
            781363,
            700754,
            5246,
            "young grendelorm",
            source="hunting-index",
            mob_level=7,
        )

        carry_level = growth.growth_party_carry_level_for_realm(args, 10, 2, "mid")
        carry_floor = growth.growth_party_carry_reward_floor(args, 10, 2, "mid")
        verified_floor = growth.growth_party_carry_verified_route_reward_floor(args, 10, 2, "mid", route)
        preflight_min, preflight_max = growth.growth_route_preflight_level_band(
            args,
            route,
            realm_key="mid",
            current_level=10,
            party_size=2,
        )

        self.assertEqual(carry_level, 13)
        self.assertEqual(carry_floor, 8)
        self.assertEqual(verified_floor, 8)
        self.assertEqual((preflight_min, preflight_max), (8, 10))

    def test_mid_duo_level_ten_carry_index_does_not_fallback_below_carry_floor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "hunting-index.csv"
            index_path.write_text(
                "realm,party_size,player_level,target_min,target_ideal,target_max,name,mob_level,mob_count,x,y,z,"
                "neutral_count,min_aggro,max_aggro,max_aggro_range,nearest_teleporter,teleporter_distance,score\n"
                "mid,2,10,8,9,10,young grendelorm,7,12,781363,700754,5246,12,0,0,0,Fort Veldon,1200,999\n"
                "mid,2,10,8,9,10,노련한 young grendelorm,8,12,781263,700654,5246,12,0,0,0,Fort Veldon,1200,500\n"
                "mid,2,10,8,9,10,small hill cat,8,12,807490,680515,5000,12,0,0,0,Fort Veldon,1200,100\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                growth_hunting_index=str(index_path),
                growth_route_case_index=0,
                growth_fast_travel="route-home",
                growth_route_preflight=False,
                dry_run=True,
                growth_target_level_override=10,
                growth_target_plan_override=(8, 9, 1),
                growth_allow_lower_xp_target_plan=False,
                growth_allow_lower_xp_gear_farm=True,
                growth_route_level_is_carry_target=True,
                growth_route_player_level=10,
                growth_shortage_recovery_player_level=0,
                growth_party_carry_level_offset=12,
                current_party_size=2,
                growth_party_carry_count=-1,
                growth_equip_party_carry_gear=False,
                growth_failure_target_memory=False,
                case_name="",
            )

            route = growth.select_growth_hunting_index_point_for_target(
                args,
                "mid",
                9,
                2,
                caller_player_level=10,
                allow_player_reward_floor_fallback=True,
            )

        self.assertIsNotNone(route)
        self.assertGreaterEqual(route.mob_level, 8)
        self.assertNotEqual(route.prefer, "young grendelorm")

    def test_behavior_command_includes_verified_hunting_index_mob_level(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            growth_target_plan_override=(6, 6, 0),
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            growth_failure_target_memory=False,
            growth_fast_travel="route-home",
        )
        route = growth.route_point(
            8,
            486154,
            592482,
            1852,
            "rot worm",
            source="hunting-index",
            mob_level=5,
        )

        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            with mock.patch.object(growth, "select_growth_route_point", return_value=route):
                command = growth.build_behavior_command(
                    args=args,
                    realm=growth.REALMS["mid"],
                    accounts_csv=Path("accounts.csv"),
                    case_dir=case_dir,
                    segment_index=23,
                    party_size=1,
                    current_level=8,
                    path_graph=Path("graph.json"),
                )
            payload = json.loads((case_dir / "live-control.json").read_text(encoding="utf-8"))

        self.assertEqual(command[command.index("--min-target-level") + 1], "5")
        self.assertEqual(command[command.index("--max-target-level") + 1], "6")
        self.assertEqual(payload["baseline_min_target_level"], 5)
        self.assertEqual(payload["baseline_max_target_level"], 6)

    def test_behavior_command_uses_selected_route_without_reselecting(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            growth_fast_travel="route-home",
        )
        route = growth.route_point(
            9,
            759796,
            739453,
            5381,
            "roaming dirge",
            source="hunting-index",
            mob_level=8,
        )

        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            with mock.patch.object(
                growth,
                "select_growth_segment_route",
                side_effect=AssertionError("route should be selected by run_case once"),
            ):
                command = growth.build_behavior_command(
                    args=args,
                    realm=growth.REALMS["mid"],
                    accounts_csv=Path("accounts.csv"),
                    case_dir=case_dir,
                    segment_index=24,
                    party_size=2,
                    current_level=10,
                    path_graph=Path("graph.json"),
                    selected_route=route,
                )

        self.assertEqual(
            command[command.index("--required-target-home") + 1],
            growth.route_home_string_for_point(growth.REALMS["mid"], route, ground_z_offset=0),
        )
        self.assertEqual(command[command.index("--target-pool") + 1], "5")

    def test_route_home_fast_travel_reuses_segment_route_for_behavior_command(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--checkpoint-levels",
                "10",
                "--realms",
                "mid",
                "--party-sizes",
                "2",
                "--growth-fast-travel",
                "route-home",
                "--no-watch-movement",
                "--no-fail-on-regression",
            ]
        )
        route = growth.route_point(
            9,
            759796,
            739453,
            5381,
            "roaming dirge",
            source="hunting-index",
            mob_level=8,
        )
        selected_routes: list[growth.RoutePoint] = []
        select_count = 0

        original_select = growth.select_growth_segment_route
        original_build_behavior_command = growth.build_behavior_command
        original_run_commands_concurrently = growth.run_commands_concurrently
        try:
            def fake_select(*_args, **_kwargs):
                nonlocal select_count
                select_count += 1
                return route

            def fake_build_behavior_command(**kwargs):
                selected_routes.append(kwargs["selected_route"])
                return ["behavior", kwargs["selected_route"].prefer]

            growth.select_growth_segment_route = fake_select
            growth.build_behavior_command = fake_build_behavior_command
            growth.run_commands_concurrently = lambda _commands, _dry_run: 0

            with tempfile.TemporaryDirectory() as temp_dir:
                output_dir = Path(temp_dir)
                rc = growth.run_case(
                    args,
                    growth.REALMS["mid"],
                    party_size=2,
                    case_index=0,
                    output_dir=output_dir,
                    path_graph=output_dir / "growth-route-graph.json",
                    timeline_csv=output_dir / "timeline.csv",
                )
                primary_rows = growth.read_accounts(output_dir / "mid-p2" / "primary-accounts.csv")
        finally:
            growth.select_growth_segment_route = original_select
            growth.build_behavior_command = original_build_behavior_command
            growth.run_commands_concurrently = original_run_commands_concurrently

        self.assertEqual(rc, 0)
        self.assertEqual(select_count, 1)
        self.assertEqual(selected_routes, [route])
        self.assertEqual(primary_rows[0]["start_x"], str(route.x))
        self.assertEqual(primary_rows[0]["start_y"], str(route.y))

    def test_behavior_command_does_not_lower_verified_mob_below_xp_floor(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            growth_target_plan_override=(4, 5, 1),
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            growth_failure_target_memory=False,
            growth_fast_travel="route-home",
            growth_party_carry_level_offset=12,
            current_party_size=2,
            growth_party_carry_count=-1,
            growth_equip_party_carry_gear=False,
        )
        route = growth.route_point(
            5,
            810238,
            727088,
            4688,
            "wood-eater",
            source="hunting-index",
            mob_level=3,
        )

        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            with mock.patch.object(growth, "select_growth_route_point", return_value=route):
                with self.assertRaisesRegex(RuntimeError, "below reward floor"):
                    growth.build_behavior_command(
                        args=args,
                        realm=growth.REALMS["mid"],
                        accounts_csv=Path("accounts.csv"),
                        case_dir=case_dir,
                        segment_index=25,
                        party_size=2,
                        current_level=5,
                        path_graph=Path("graph.json"),
                    )

    def test_hib_duo_low_gear_farm_includes_verified_route_mob_band(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            growth_target_plan_override=(5, 5, 0),
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            growth_route_level_is_carry_target=True,
            growth_failure_target_memory=False,
            growth_fast_travel="route-home",
            growth_party_carry_level_offset=12,
            current_party_size=2,
            growth_party_carry_count=-1,
            growth_equip_party_carry_gear=False,
        )
        route = growth.route_point(
            5,
            361545,
            491812,
            4659,
            "small freshwater crab",
            source="hunting-index",
            mob_level=4,
        )

        preflight_min, preflight_max = growth.growth_route_preflight_level_band(
            args,
            route,
            realm_key="hib",
            current_level=5,
            party_size=2,
        )
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            with mock.patch.object(growth, "select_growth_route_point", return_value=route):
                with self.assertRaisesRegex(RuntimeError, "below reward floor"):
                    growth.build_behavior_command(
                        args=args,
                        realm=growth.REALMS["hib"],
                        accounts_csv=Path("accounts.csv"),
                        case_dir=case_dir,
                        segment_index=30,
                        party_size=2,
                        current_level=5,
                        path_graph=Path("graph.json"),
                    )

        self.assertEqual((preflight_min, preflight_max), (5, 5))

    def test_behavior_command_keeps_party_carry_target_above_tracked_level(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            growth_target_plan_override=(3, 4, 1),
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            growth_failure_target_memory=False,
            growth_fast_travel="route-home",
            growth_party_carry_level_offset=12,
            current_party_size=8,
            growth_party_carry_count=-1,
            growth_equip_party_carry_gear=False,
        )
        route = growth.route_point(
            2,
            786637,
            723034,
            4722,
            "wood-eater worker",
            source="hunting-index",
            mob_level=4,
        )

        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            with mock.patch.object(growth, "select_growth_route_point", return_value=route):
                command = growth.build_behavior_command(
                    args=args,
                    realm=growth.REALMS["mid"],
                    accounts_csv=Path("accounts.csv"),
                    case_dir=case_dir,
                    segment_index=16,
                    party_size=8,
                    current_level=2,
                    path_graph=Path("graph.json"),
                )
            payload = json.loads((case_dir / "live-control.json").read_text(encoding="utf-8"))

        self.assertEqual(command[command.index("--min-target-level") + 1], "3")
        self.assertEqual(payload["baseline_min_target_level"], 3)

    def test_alb_solo_level_seven_hunting_index_route_requires_exact_target(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            growth_target_plan_override=(5, 5, 1),
            growth_failure_target_memory=False,
            growth_fast_travel="route-home",
        )
        route = growth.route_point(
            7,
            491992,
            600866,
            1837,
            "emerald snake",
            source="hunting-index",
            mob_level=6,
        )

        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            with mock.patch.object(growth, "select_growth_route_point", return_value=route):
                command = growth.build_behavior_command(
                    args=args,
                    realm=growth.REALMS["alb"],
                    accounts_csv=Path("accounts.csv"),
                    case_dir=case_dir,
                    segment_index=15,
                    party_size=1,
                    current_level=7,
                    path_graph=Path("graph.json"),
                )

        self.assertEqual(command[command.index("--require-target-name") + 1], "emerald snake")
        self.assertIn("--require-target-name-exact", command)

    def test_alb_solo_level_ten_hunting_index_route_allows_localized_prefix_target(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=180,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=6200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            growth_allow_lower_xp_target_plan=True,
            growth_allow_lower_xp_gear_farm=True,
            growth_target_plan_override=(7, 7, 0),
            growth_failure_target_memory=False,
            growth_fast_travel="route-home",
        )
        route = growth.route_point(
            10,
            526821,
            614578,
            1847,
            "bandit",
            teleport_destination="Caer Ulfwych",
            source="hunting-index",
            mob_level=7,
        )

        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            with mock.patch.object(growth, "select_growth_route_point", return_value=route):
                command = growth.build_behavior_command(
                    args=args,
                    realm=growth.REALMS["alb"],
                    accounts_csv=Path("accounts.csv"),
                    case_dir=case_dir,
                    segment_index=15,
                    party_size=1,
                    current_level=10,
                    path_graph=Path("graph.json"),
                )

        self.assertEqual(command[command.index("--require-target-name") + 1], "bandit")
        self.assertNotIn("--require-target-name-exact", command)

    def test_mid_solo_level_ten_small_hill_cat_keeps_level_seven_target_band(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=180,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=6200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=240.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            growth_target_plan_override=(7, 7, 0),
            growth_failure_target_memory=False,
            growth_fast_travel="route-home",
        )
        route = growth.route_point(
            10,
            807285,
            680511,
            5434,
            "small hill cat",
            source="hunting-index",
            mob_level=8,
        )

        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case"
            case_dir.mkdir()
            with mock.patch.object(growth, "select_growth_route_point", return_value=route):
                command = growth.build_behavior_command(
                    args=args,
                    realm=growth.REALMS["mid"],
                    accounts_csv=Path("accounts.csv"),
                    case_dir=case_dir,
                    segment_index=15,
                    party_size=1,
                    current_level=10,
                    path_graph=Path("graph.json"),
                )

        self.assertEqual(command[command.index("--require-target-name") + 1], "small hill cat")
        self.assertEqual(command[command.index("--min-target-level") + 1], "7")
        self.assertEqual(command[command.index("--ideal-target-level") + 1], "7")
        self.assertEqual(command[command.index("--max-target-level") + 1], "7")

    def test_mid_solo_level_ten_uses_isolated_nordic_dirge_route(self) -> None:
        args = SimpleNamespace(
            growth_allow_lower_xp_target_plan=False,
            growth_allow_lower_xp_gear_farm=True,
            growth_hunting_index="",
            growth_route_preflight=False,
            growth_failure_target_memory=False,
            growth_fast_travel="route-home",
        )

        route = growth.select_growth_route_point(args, growth.REALMS["mid"], 10, 1)

        self.assertEqual(route.prefer, "nordic dirge")
        self.assertEqual(route.mob_level, 7)
        self.assertEqual((route.x, route.y, route.z), (721568, 750610, 4552))
        self.assertEqual(
            growth.growth_target_nearby_avoid_names_for_route(10, 1, "mid", route),
            "roaming dirge,lake serpent,rock crab,black mauler juvenile",
        )
        self.assertEqual(growth.growth_objective_entry_aggro_avoid_radius(10, 1, "mid", route), 0.0)
        self.assertEqual(growth.growth_path_last_mile_distance(SimpleNamespace(path_last_mile_distance=1200), 10, 1, "mid", route), 1200.0)

    def test_mid_level_ten_nordic_dirge_route_home_uses_safe_landing(self) -> None:
        route = growth.select_growth_route_point(
            SimpleNamespace(growth_hunting_index="", growth_route_case_index=0),
            growth.REALMS["mid"],
            10,
            1,
        )

        safe = growth.startup_route_home_after_services_point(
            growth.REALMS["mid"],
            route,
            current_level=10,
            party_size=1,
            ground_z_offset=0,
        )

        self.assertEqual((route.x, route.y, route.z), (721568, 750610, 4552))
        self.assertEqual((safe.x, safe.y, safe.z), (722807, 752180, 4574))
        self.assertEqual(safe.prefer, "nordic dirge")

    def test_two_player_growth_party_uses_carry_roles(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["mid"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=1,
            party_size=2,
            current_level=1,
            path_graph=Path("graph.json"),
        )

        self.assertEqual(command[command.index("--action-rotation") + 1], "auto")
        self.assertEqual(command[command.index("--party-role-strategy") + 1], "mixed")
        self.assertIn("--party-assist-only", command)
        self.assertEqual(command[command.index("--party-assist-interval") + 1], "0.6")
        self.assertEqual(command[command.index("--party-assist-attack-delay") + 1], "0.0")
        self.assertEqual(command[command.index("--attack-target-in-view-prime-delay") + 1], "0.0")
        self.assertEqual(command[command.index("--party-min-ready") + 1], "2")
        self.assertNotIn("--party-require-leader-engaged", command)
        self.assertIn("--party-mark-pull-engaged", command)
        self.assertEqual(command[command.index("--party-pull-engage-distance") + 1], "1800")
        self.assertNotIn("--party-block-solo-required-retaliation", command)
        self.assertEqual(command[command.index("--party-pre-pull-home-stop-distance") + 1], "1600")
        self.assertIn("--party-rescue-aggro", command)
        self.assertIn("--party-rescue-before-objective-engaged", command)
        self.assertNotIn("--party-clear-objective-adds-before-engage", command)
        self.assertIn("--party-local-rescue-target", command)
        self.assertEqual(command[command.index("--party-local-rescue-max-distance") + 1], "1200")
        self.assertEqual(command[command.index("--party-healer-local-rescue-health-percent") + 1], "45")
        self.assertEqual(command[command.index("--party-rescue-objective-max-distance") + 1], "2400")
        self.assertEqual(command[command.index("--party-rescue-assist-after") + 1], "6")
        self.assertEqual(command[command.index("--party-rescue-emergency-assist-after") + 1], "2.0")
        self.assertEqual(command[command.index("--party-slot-rotations") + 1], "melee-burst,healer-support")
        self.assertIn("--allow-unvalidated-skills", command)

    def test_growth_party_carry_count_zero_uses_equal_party_command_rules(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            growth_party_carry_count=0,
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["mid"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=1,
            party_size=2,
            current_level=1,
            path_graph=Path("graph.json"),
        )

        self.assertIn("--party-require-leader-engaged", command)
        self.assertIn("--party-block-solo-required-retaliation", command)
        self.assertEqual(command[command.index("--party-assist-interval") + 1], "0.4")
        self.assertEqual(command[command.index("--party-follow-distance") + 1], "500")
        self.assertEqual(command[command.index("--party-pre-pull-home-stop-distance") + 1], "1800")
        self.assertNotIn("--party-carry-counterattack-travel-aggro", command)
        self.assertNotIn("--passive-xp-leech-follow-distance", command)
        self.assertNotIn("--startup-service-equip-party-slot", command)
        self.assertEqual(command[command.index("--party-form-up-timeout") + 1], "25")
        self.assertEqual(command[command.index("--party-slot-rotations") + 1], "melee-basic,healer-support")

    def test_large_growth_party_uses_fast_invite_cadence_without_carry_tuning(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=120,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            growth_party_carry_count=0,
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["hib"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=1,
            party_size=8,
            current_level=1,
            path_graph=Path("graph.json"),
        )

        self.assertEqual(command[command.index("--party-invite-interval") + 1], "1")
        self.assertEqual(command[command.index("--party-accept-interval") + 1], "0.5")

    def test_level_fifty_large_party_reuses_boss_party_survival_rules(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=120,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=1,
            party_size=4,
            current_level=50,
            path_graph=Path("graph.json"),
        )

        self.assertTrue(growth.level50_party_boss_rules_enabled(50, 4))
        self.assertIn("--party-encounter-mode", command)
        self.assertEqual(command[command.index("--party-encounter-mode") + 1], "boss")
        self.assertEqual(command[command.index("--party-assist-interval") + 1], "0.6")
        self.assertEqual(command[command.index("--party-form-up-delay") + 1], "8")
        self.assertEqual(command[command.index("--party-rescue-max-age") + 1], "14")
        self.assertEqual(command[command.index("--party-rescue-assist-after") + 1], "3")
        self.assertIn("--boss-ranged-safe-distance", command)
        self.assertEqual(command[command.index("--boss-ranged-safe-distance") + 1], "1000")
        self.assertIn("--boss-hazard-message-backoff-duration", command)
        self.assertEqual(command[command.index("--boss-hazard-message-backoff-distance") + 1], "2400")
        self.assertIn("--party-focus-target-backoff", command)
        self.assertIn("--party-melee-survival-health-percent", command)
        self.assertEqual(command[command.index("--party-melee-survival-health-percent") + 1], "45")
        self.assertIn("--party-survival-death-count", command)
        self.assertEqual(command[command.index("--party-survival-active-tank-health-percent") + 1], "35")
        self.assertIn("--stop-after-required-target-removed", command)
        self.assertEqual(command[command.index("--party-slot-rotations") + 1], "melee-basic,healer-support,melee-basic,melee-burst")

    def test_level_fifty_two_player_party_keeps_growth_party_rules(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=120,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=1,
            party_size=2,
            current_level=50,
            path_graph=Path("graph.json"),
        )

        self.assertFalse(growth.level50_party_boss_rules_enabled(50, 2))
        self.assertNotIn("--party-encounter-mode", command)
        self.assertEqual(command[command.index("--party-assist-interval") + 1], "0.6")
        self.assertEqual(command[command.index("--party-form-up-delay") + 1], "4")
        self.assertEqual(command[command.index("--party-rescue-assist-after") + 1], "6")

    def test_level_one_large_party_uses_support_slot_rotations(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["hib"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=1,
            party_size=8,
            current_level=1,
            path_graph=Path("graph.json"),
        )

        self.assertEqual(
            command[command.index("--party-slot-rotations") + 1],
            "melee-burst,healer-support,melee-basic,melee-basic,melee-basic,healer-support,caster-basic,none",
        )
        self.assertEqual(command[command.index("--party-assist-interval") + 1], "0.6")
        self.assertEqual(command[command.index("--party-assist-attack-delay") + 1], "0.0")
        self.assertEqual(command[command.index("--attack-target-in-view-prime-delay") + 1], "0.0")
        self.assertIn("--allow-unvalidated-skills", command)

    def test_solo_growth_allows_unvalidated_skills_for_melee_styles(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=1,
            party_size=1,
            current_level=10,
            path_graph=Path("graph.json"),
        )

        self.assertIn("--allow-unvalidated-skills", command)

    def test_growth_command_trains_after_level_up_from_level_two(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=2,
            party_size=1,
            current_level=2,
            path_graph=Path("graph.json"),
        )

        self.assertNotIn("--startup-auto-train", command)
        self.assertEqual(command[command.index("--required-target-recover-before-hunt-endurance-percent") + 1], "0")
        self.assertIn("--startup-train-full-specs", command)
        self.assertIn("--startup-train-level", command)
        self.assertEqual(command[command.index("--startup-train-level") + 1], "2")
        self.assertIn("--combat-usable-api", command)
        self.assertEqual(command[command.index("--ideal-target-level") + 1], "1")
        self.assertEqual(command[command.index("--min-target-level") + 1], "1")
        self.assertEqual(command[command.index("--max-target-level") + 1], "1")
        self.assertEqual(command[command.index("--max-target-level-delta") + 1], "0")
        self.assertIn("--greet-nearby-player", command)
        self.assertNotIn("--speak-state-changes", command)
        self.assertNotIn("--state-speech-min-interval", command)

    def test_solo_magic_checkpoint_uses_caster_rotation_from_account_specs(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            accounts_csv = Path(temp_dir) / "accounts.csv"
            accounts_csv.write_text(
                "username,password,realm,char_index,class_id,specs\n"
                "growthalb001,dummy-pass,1,0,5,Earth Magic|45;Cold Magic|25;Wind Magic|8\n",
                encoding="utf-8",
            )

            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=accounts_csv,
                case_dir=Path(temp_dir) / "case",
                segment_index=4,
                party_size=1,
                current_level=10,
                path_graph=Path("graph.json"),
            )

        self.assertEqual(command[command.index("--action-rotation") + 1], "caster-basic")
        self.assertIn("--stationary-cast-actions", command)
        self.assertEqual(command[command.index("--cast-action-hold") + 1], "3.4")

    def test_solo_healing_checkpoint_uses_healer_support_from_account_specs(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            accounts_csv = Path(temp_dir) / "accounts.csv"
            accounts_csv.write_text(
                "username,password,realm,char_index,class_id,specs\n"
                "growthalb001,dummy-pass,1,0,6,Smite|1;Rejuvenation|40;Enhancement|36\n",
                encoding="utf-8",
            )

            command = growth.build_behavior_command(
                args=args,
                realm=growth.REALMS["alb"],
                accounts_csv=accounts_csv,
                case_dir=Path(temp_dir) / "case",
                segment_index=2,
                party_size=1,
                current_level=5,
                path_graph=Path("graph.json"),
            )

        self.assertEqual(command[command.index("--action-rotation") + 1], "healer-support")
        self.assertIn("--stationary-cast-actions", command)
        self.assertEqual(command[command.index("--support-spell-chance") + 1], "1.0")
        self.assertEqual(command[command.index("--healer-self-health-percent") + 1], "80")

    def test_growth_command_continues_training_after_level_five(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=3,
            party_size=1,
            current_level=6,
            path_graph=Path("graph.json"),
        )

        self.assertNotIn("--startup-auto-train", command)
        self.assertIn("--startup-train-full-specs", command)
        self.assertIn("--startup-train-level", command)
        self.assertEqual(command[command.index("--startup-train-level") + 1], "6")
        self.assertEqual(command[command.index("--hunter-min-time-left-for-new-target") + 1], "75")

    def test_growth_command_does_not_train_at_level_one(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=1,
            party_size=1,
            current_level=1,
            path_graph=Path("graph.json"),
        )

        self.assertNotIn("--startup-auto-train", command)

    def test_growth_command_does_not_train_at_level_fifty_checkpoint(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=1,
            party_size=4,
            current_level=50,
            path_graph=Path("graph.json"),
        )

        self.assertNotIn("--startup-auto-train", command)
        self.assertIn("--startup-train-full-specs", command)
        self.assertNotIn("--startup-service-accept-dialog", command)

    def test_reset_level_argument_sets_starting_character_level(self) -> None:
        args = growth.parse_args_for_tests(["--reset-level", "5", "--dry-run"])

        self.assertEqual(args.reset_level, 5)

    def test_post_segment_snapshot_delay_defaults_to_db_settle_wait(self) -> None:
        args = growth.parse_args_for_tests(["--dry-run"])

        self.assertGreater(args.post_segment_snapshot_delay, 0)
        self.assertEqual(args.post_segment_snapshot_timeout, 90.0)
        self.assertEqual(args.post_segment_snapshot_poll_interval, 2.0)

    def test_train_verified_requires_actual_class_or_spec_change(self) -> None:
        before = growth.CharacterSnapshot(
            "growthalb001", "GrowthAlb001", "id", 5, 0, 1, 1, "Slash|1;Chants|1", 1, 2, 3, 4, 0, 0, 0, 0
        )
        after = growth.CharacterSnapshot(
            "growthalb001", "GrowthAlb001", "id", 5, 0, 1, 1, "Slash|1;Chants|5", 1, 2, 3, 4, 0, 0, 0, 0
        )

        self.assertEqual(growth.spec_gain_summary(before.specs, after.specs), "Chants+4")
        self.assertTrue(growth.train_verified(before, after, 5))
        self.assertTrue(growth.train_verified(before, after, 6))
        self.assertTrue(growth.train_verified(before, after, 4))
        self.assertFalse(growth.train_verified(before, before, 5))
        self.assertFalse(growth.train_verified(before, after, 1))

    def test_baseline_specs_resets_all_lines_to_one(self) -> None:
        self.assertEqual(
            growth.baseline_specs("Slash|39;Thrust|1;Chants|48;Shields|42"),
            "Slash|1;Thrust|1;Chants|1;Shields|1",
        )

    def test_snapshot_deltas_cover_text_xp_waits_for_persisted_xp(self) -> None:
        before = {
            "growthmid001": growth.CharacterSnapshot(
                "growthmid001", "GrowthMid001", "id", 1, 0, 2, 22, "Hammer|1", 100, 1, 2, 3, 0, 0, 0, 0
            )
        }
        short_after = {
            "growthmid001": growth.CharacterSnapshot(
                "growthmid001", "GrowthMid001", "id", 1, 10, 2, 22, "Hammer|1", 100, 1, 2, 3, 0, 0, 0, 0
            )
        }
        full_after = {
            "growthmid001": growth.CharacterSnapshot(
                "growthmid001", "GrowthMid001", "id", 1, 14, 2, 22, "Hammer|1", 100, 1, 2, 3, 0, 0, 0, 0
            )
        }
        text_metrics = {"growthmid001": {"text_xp_delta": 14, "text_xp_messages": 1}}

        self.assertFalse(growth.snapshot_deltas_cover_text_xp(before, short_after, text_metrics))
        self.assertTrue(growth.snapshot_deltas_cover_text_xp(before, full_after, text_metrics))

    def test_growth_command_attempts_backpack_auto_equip_slots(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            growth_auto_equip_slots=[40, 41, 42],
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=2,
            party_size=1,
            current_level=5,
            path_graph=Path("graph.json"),
        )

        self.assertIn("--startup-service-equip-slot", command)
        self.assertEqual(command[command.index("--startup-service-equip-slot") + 1], "40,41,42")

    def test_growth_command_routes_sell_and_buy_slots_through_startup_merchant(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            growth_auto_equip_slots=[],
            growth_auto_sell_slots=[40],
            growth_merchant_npc_name="Alburn Hale",
            growth_merchant_buy_slots=[7],
            growth_merchant_equip_slots=[40],
            growth_merchant_scan_seconds=0.5,
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=2,
            party_size=1,
            current_level=5,
            path_graph=Path("graph.json"),
        )

        self.assertNotIn("--startup-service-sell-slot", command)
        self.assertIn("--startup-merchant-npc-name", command)
        self.assertEqual(command[command.index("--startup-merchant-npc-name") + 1], "Alburn Hale")
        self.assertEqual(command[command.index("--startup-merchant-sell-slot") + 1], "40")
        self.assertEqual(command[command.index("--startup-merchant-buy-slot") + 1], "7")
        self.assertEqual(command[command.index("--startup-merchant-equip-slot") + 1], "40")

    def test_growth_command_routes_party_item_actions_through_party_slot_maps(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            growth_auto_equip_slots=[],
            growth_auto_equip_party_slot_maps=["0:40", "1:41"],
            growth_auto_sell_slots=[],
            growth_merchant_npc_name="Alburn Hale",
            growth_merchant_buy_slots=[],
            growth_merchant_equip_slots=[],
            growth_merchant_sell_party_slot_maps=["0:42"],
            growth_merchant_buy_party_slot_maps=["1:7"],
            growth_merchant_equip_party_slot_maps=["1:43"],
            growth_merchant_scan_seconds=0.5,
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=2,
            party_size=2,
            current_level=5,
            path_graph=Path("graph.json"),
        )

        self.assertEqual(command[command.index("--startup-service-equip-party-slot-map") + 1], "0:40")
        self.assertIn("--startup-merchant-sell-party-slot", command)
        self.assertIn("--startup-merchant-buy-party-slot", command)
        self.assertIn("--startup-merchant-equip-party-slot", command)
        self.assertEqual(command[command.index("--startup-merchant-sell-party-slot") + 1], "0:42")
        self.assertEqual(command[command.index("--startup-merchant-buy-party-slot") + 1], "1:7")
        self.assertEqual(command[command.index("--startup-merchant-equip-party-slot") + 1], "1:43")
        self.assertNotIn("--startup-merchant-sell-slot", command)
        self.assertNotIn("--startup-merchant-buy-slot", command)

    def test_level50_party_gear_command_reuses_boss_gear_equipper(self) -> None:
        args = SimpleNamespace(
            mysql_bin="mysql",
            db_host="127.0.0.1",
            db_port=3306,
            db_name="dol",
            db_user="root",
            db_password="pw",
            level50_party_gear=True,
        )

        self.assertTrue(growth.should_equip_level50_party_gear(args, current_level=50, party_size=2))
        self.assertFalse(growth.should_equip_level50_party_gear(args, current_level=49, party_size=2))
        self.assertFalse(growth.should_equip_level50_party_gear(args, current_level=50, party_size=1))

        command = growth.build_level50_party_gear_command(args, Path("primary-accounts.csv"))

        self.assertIn("equip-dummy-boss-gear.py", command[1])
        self.assertIn("primary-accounts.csv", command)
        self.assertNotIn("--template-level-cap", command)

        carry_command = growth.build_growth_party_carry_gear_command(args, Path("carry-accounts.csv"), 13)
        self.assertIn("carry-accounts.csv", carry_command)
        self.assertEqual(carry_command[carry_command.index("--template-level-cap") + 1], "13")

    def test_injected_party_gear_is_disabled_by_default_for_official_growth(self) -> None:
        args = SimpleNamespace()

        self.assertFalse(growth.should_equip_level50_party_gear(args, current_level=50, party_size=2))
        self.assertFalse(growth.should_equip_growth_party_carry_gear(args, carry_level=13, party_size=4))

        enabled = SimpleNamespace(level50_party_gear=True, growth_equip_party_carry_gear=True)
        self.assertTrue(growth.should_equip_level50_party_gear(enabled, current_level=50, party_size=2))
        self.assertTrue(growth.should_equip_growth_party_carry_gear(enabled, carry_level=13, party_size=4))

    def test_growth_character_name_from_account_preserves_realm_prefix_case(self) -> None:
        self.assertEqual(growth.character_name_from_account("growthalb61242"), "GrowthAlb61242")
        self.assertEqual(growth.character_name_from_account("growthmid61081"), "GrowthMid61081")
        self.assertEqual(growth.character_name_from_account("growthhib61161"), "GrowthHib61161")
        self.assertEqual(growth.character_name_from_account("dummy001"), "Dummy001")

    def test_provision_command_uses_growth_balanced_class_cycles(self) -> None:
        args = SimpleNamespace(
            mysql_bin="mysql",
            db_host="127.0.0.1",
            db_port=3306,
            db_name="dol",
            db_user="user",
            db_password="pw",
            template_account="template",
            template_character="Template",
            password="pw",
            position_step=10,
            replace=False,
            no_starter_equipment=False,
            reset_level=1,
            growth_start_base_classes=False,
        )

        command = growth.build_provision_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            count=4,
            start=1001,
        )

        self.assertEqual(command[command.index("--class-cycle") + 1].split("|")[:4], ["1", "6", "2", "11"])
        self.assertEqual(command[command.index("--class-cycle") + 1].split("|")[7], "6")
        self.assertEqual(command[command.index("--race-cycle") + 1].split("|")[:2], ["1", "3"])
        self.assertIn("Rejuvenation|40", command[command.index("--spec-cycle") + 1])
        self.assertEqual(command[command.index("--start-x") + 1], "534900")
        self.assertEqual(command[command.index("--start-y") + 1], "477500")

    def test_provision_command_starts_from_bind_even_for_later_growth_stage(self) -> None:
        args = SimpleNamespace(
            mysql_bin="mysql",
            db_host="127.0.0.1",
            db_port=3306,
            db_name="dol",
            db_user="user",
            db_password="pw",
            template_account="template",
            template_character="Template",
            password="pw",
            position_step=10,
            replace=False,
            no_starter_equipment=False,
            reset_level=5,
            growth_start_base_classes=False,
        )

        command = growth.build_provision_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            count=2,
            start=1001,
        )

        self.assertEqual(command[command.index("--start-x") + 1], str(growth.REALMS["alb"].start[0]))
        self.assertEqual(command[command.index("--start-y") + 1], str(growth.REALMS["alb"].start[1]))

    def test_checkpoint_reset_moves_characters_back_to_bind(self) -> None:
        args = SimpleNamespace(position_step=80)
        calls: list[str] = []
        original_run_mysql = growth.run_mysql
        try:
            def fake_run_mysql(_args, sql):
                calls.append(sql)
                if "SELECT AccountName, SerializedSpecs" in sql:
                    return "AccountName\tSerializedSpecs\n"
                return ""

            growth.run_mysql = fake_run_mysql
            growth.reset_growth_characters(args, ["growthalb100", "growthalb101"], level=6, realm=growth.REALMS["alb"])
        finally:
            growth.run_mysql = original_run_mysql

        reset_sql = calls[0]
        self.assertIn("Level = 6", reset_sql)
        self.assertIn("Xpos = CASE AccountName", reset_sql)
        self.assertIn("WHEN 'growthalb100' THEN 534900", reset_sql)
        self.assertIn("WHEN 'growthalb101' THEN 534980", reset_sql)
        self.assertIn("Ypos = CASE AccountName", reset_sql)
        self.assertIn("Zpos = 2200", reset_sql)
        self.assertIn("Region = 1", reset_sql)

    def test_checkpoint_route_home_start_resets_characters_near_selected_route_point(self) -> None:
        args = SimpleNamespace(position_step=80, checkpoint_start_location="route-home")
        calls: list[str] = []
        original_run_mysql = growth.run_mysql
        try:
            def fake_run_mysql(_args, sql):
                calls.append(sql)
                if "SELECT AccountName, SerializedSpecs" in sql:
                    return "AccountName\tSerializedSpecs\n"
                return ""

            growth.run_mysql = fake_run_mysql
            growth.reset_growth_characters(
                args,
                ["growthalb100", "growthalb101"],
                level=50,
                realm=growth.REALMS["alb"],
                party_size=4,
            )
        finally:
            growth.run_mysql = original_run_mysql

        route = growth.select_route_point(growth.REALMS["alb"], 50, 4)
        reset_sql = calls[0]
        self.assertIn(f"WHEN 'growthalb100' THEN {route.x}", reset_sql)
        self.assertIn(f"WHEN 'growthalb101' THEN {route.x + 80}", reset_sql)
        self.assertIn(f"WHEN 'growthalb100' THEN {route.y}", reset_sql)
        self.assertIn(f"Zpos = {route.z}", reset_sql)

    def test_route_home_fast_travel_stages_train_checkpoint_at_realm_start(self) -> None:
        args = SimpleNamespace(
            position_step=80,
            checkpoint_start_location="route-home",
            growth_fast_travel="route-home",
        )
        calls: list[str] = []
        original_run_mysql = growth.run_mysql
        try:
            def fake_run_mysql(_args, sql):
                calls.append(sql)
                if "SELECT AccountName, SerializedSpecs" in sql:
                    return "AccountName\tSerializedSpecs\n"
                return ""

            growth.run_mysql = fake_run_mysql
            growth.reset_growth_characters(
                args,
                ["growthhib1741"],
                level=5,
                realm=growth.REALMS["hib"],
                party_size=1,
            )
        finally:
            growth.run_mysql = original_run_mysql

        start_x, start_y, start_z = growth.REALMS["hib"].start
        route = growth.select_route_point(growth.REALMS["hib"], 5, 1)
        reset_sql = calls[0]
        self.assertIn(f"WHEN 'growthhib1741' THEN {start_x}", reset_sql)
        self.assertIn(f"WHEN 'growthhib1741' THEN {start_y}", reset_sql)
        self.assertIn(f"Zpos = {start_z}", reset_sql)
        self.assertNotIn(f"WHEN 'growthhib1741' THEN {route.x}", reset_sql)
        self.assertNotIn(f"Zpos = {route.z}", reset_sql)

    def test_route_home_fast_travel_keeps_level50_direct_route_start(self) -> None:
        args = SimpleNamespace(
            position_step=80,
            checkpoint_start_location="route-home",
            growth_fast_travel="route-home",
        )

        point = growth.checkpoint_start_point(args, growth.REALMS["alb"], 50, 4)
        route = growth.select_route_point(growth.REALMS["alb"], 50, 4)

        self.assertEqual((point.x, point.y, point.z), (route.x, route.y, route.z))

    def test_alb_level_ten_solo_route_home_starts_from_safe_adder_anchor(self) -> None:
        args = SimpleNamespace(
            position_step=80,
            checkpoint_start_location="route-home",
            growth_fast_travel="off",
            ground_z_offset=0,
        )

        point = growth.checkpoint_start_point(args, growth.REALMS["alb"], 10, 1)
        route = growth.select_route_point(growth.REALMS["alb"], 10, 1)

        self.assertEqual((point.x, point.y), (593200, 499000))
        self.assertNotEqual((point.x, point.y), (route.x, route.y))
        self.assertIn("adder", point.prefer)

    def test_growth_api_defaults_follow_non_loopback_host(self) -> None:
        args = growth.parse_args_for_tests(["--dry-run", "--host", "192.168.0.4"])

        self.assertEqual(args.nav_api_url, "http://192.168.0.4:5000")

    def test_growth_api_defaults_keep_explicit_nav_api_url(self) -> None:
        args = growth.parse_args_for_tests(
            [
                "--dry-run",
                "--host",
                "192.168.0.4",
                "--nav-api-url",
                "http://10.0.0.10:5000",
            ]
        )

        self.assertEqual(args.nav_api_url, "http://10.0.0.10:5000")

    def test_route_home_relocation_uses_same_sampled_z_as_startup_rows(self) -> None:
        args = SimpleNamespace(position_step=80, dry_run=False, ground_z_offset=0)
        route = growth.route_point(
            5,
            350688,
            534196,
            4598,
            "water beetle collector",
            source="hunting-index",
            mob_level=5,
        )
        calls: list[str] = []

        def fake_run_mysql(_args, sql):
            calls.append(sql)
            return ""

        with (
            mock.patch.object(growth, "run_mysql", side_effect=fake_run_mysql),
            mock.patch.object(growth, "sample_route_z", return_value=3586),
        ):
            growth.relocate_growth_characters_to_route(
                args,
                ["growthhib70481", "growthhib70482"],
                growth.REALMS["hib"],
                route,
            )

        reset_sql = calls[0]
        self.assertIn("WHEN 'growthhib70481' THEN 350688", reset_sql)
        self.assertIn("WHEN 'growthhib70482' THEN 350768", reset_sql)
        self.assertIn("Zpos = 3586", reset_sql)
        self.assertIn("BindZpos = 3586", reset_sql)
        self.assertNotIn("Zpos = 4598", reset_sql)

    def test_route_home_relocation_preserves_live_anchor_z(self) -> None:
        args = SimpleNamespace(position_step=80, dry_run=False, ground_z_offset=0)
        route = growth.route_point(
            5,
            350688,
            534196,
            4598,
            "water beetle collector",
            source="hunting-index",
            mob_level=5,
            live_anchor_z=True,
        )
        calls: list[str] = []

        def fake_run_mysql(_args, sql):
            calls.append(sql)
            return ""

        with (
            mock.patch.object(growth, "run_mysql", side_effect=fake_run_mysql),
            mock.patch.object(growth, "sample_route_z", return_value=3586),
        ):
            growth.relocate_growth_characters_to_route(
                args,
                ["growthhib70481", "growthhib70482"],
                growth.REALMS["hib"],
                route,
            )

        reset_sql = calls[0]
        self.assertIn("Zpos = 4598", reset_sql)
        self.assertIn("BindZpos = 4598", reset_sql)
        self.assertNotIn("Zpos = 3586", reset_sql)

    def test_reset_growth_characters_can_use_explicit_watcher_observer_start(self) -> None:
        args = SimpleNamespace(position_step=80, checkpoint_start_location="route-home")
        calls: list[str] = []
        original_run_mysql = growth.run_mysql
        try:
            def fake_run_mysql(_args, sql):
                calls.append(sql)
                if "SELECT AccountName, SerializedSpecs" in sql:
                    return "AccountName\tSerializedSpecs\n"
                return ""

            growth.run_mysql = fake_run_mysql
            observer = growth.RoutePoint(level=0, x=340397, y=671327, z=2498)
            growth.reset_growth_characters(
                args,
                ["growthalb109"],
                level=50,
                realm=growth.REALMS["alb"],
                party_size=4,
                start_point=observer,
            )
        finally:
            growth.run_mysql = original_run_mysql

        reset_sql = calls[0]
        self.assertIn("WHEN 'growthalb109' THEN 340397", reset_sql)
        self.assertIn("WHEN 'growthalb109' THEN 671327", reset_sql)
        self.assertIn("Zpos = 2498", reset_sql)

    def test_checkpoint_route_home_start_skips_startup_teleport_but_keeps_boss_rules(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=120,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            max_target_distance=5200,
            target_home_max_distance=3000.0,
            combat_home_leash_distance=1200.0,
            target_timeout=65,
            combat_interval=1.5,
            target_pool=5,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            checkpoint_start_location="route-home",
        )

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=1,
            party_size=4,
            current_level=50,
            path_graph=Path("graph.json"),
        )

        self.assertNotIn("--startup-teleport-destination", command)
        self.assertNotIn("--startup-teleporter-home", command)
        self.assertIn("--party-encounter-mode", command)
        self.assertEqual(command[command.index("--party-encounter-mode") + 1], "boss")
        self.assertEqual(command[command.index("--rest-chance") + 1], "0")

    def test_default_checkpoint_start_keeps_realm_start_and_startup_teleport(self) -> None:
        args = growth.parse_args_for_tests(["--checkpoint-levels", "50", "--dry-run"])

        self.assertEqual(args.checkpoint_start_location, "realm-start")

        command = growth.build_behavior_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            case_dir=Path("case"),
            segment_index=1,
            party_size=4,
            current_level=50,
            path_graph=Path("graph.json"),
        )

        self.assertIn("--startup-teleport-destination", command)
        self.assertEqual(command[command.index("--startup-teleport-destination") + 1], "Yarley's Farm")

    def test_provision_command_uses_base_classes_for_pre_five_growth(self) -> None:
        args = SimpleNamespace(
            mysql_bin="mysql",
            db_host="127.0.0.1",
            db_port=3306,
            db_name="dol",
            db_user="user",
            db_password="pw",
            template_account="template",
            template_character="Template",
            password="pw",
            position_step=10,
            replace=False,
            no_starter_equipment=False,
            reset_level=1,
            growth_start_base_classes=True,
        )

        command = growth.build_provision_command(
            args=args,
            realm=growth.REALMS["alb"],
            accounts_csv=Path("accounts.csv"),
            count=6,
            start=1001,
        )

        self.assertEqual(command[command.index("--class-cycle") + 1].split("|")[:6], ["14", "16", "14", "14", "16", "15"])
        self.assertEqual(command[command.index("--csv-class-cycle") + 1].split("|")[:6], ["1", "6", "2", "11", "10", "7"])

    def test_provision_command_uses_target_classes_for_post_five_checkpoints(self) -> None:
        args = SimpleNamespace(
            mysql_bin="mysql",
            db_host="127.0.0.1",
            db_port=3306,
            db_name="dol",
            db_user="user",
            db_password="pw",
            template_account="template",
            template_character="Template",
            password="pw",
            position_step=10,
            replace=False,
            no_starter_equipment=False,
            reset_level=1,
            checkpoint_levels_parsed=[5, 6],
            growth_start_base_classes=True,
        )

        command = growth.build_provision_command(
            args=args,
            realm=growth.REALMS["hib"],
            accounts_csv=Path("accounts.csv"),
            count=3,
            start=1001,
        )

        self.assertEqual(command[command.index("--class-cycle") + 1].split("|")[:3], ["44", "47", "43"])
        self.assertEqual(command[command.index("--csv-class-cycle") + 1].split("|")[:3], ["44", "47", "43"])

    def test_promote_growth_classes_for_level_updates_base_class_to_target(self) -> None:
        captured = {}

        def fake_run_mysql(_args, sql):
            captured["sql"] = sql
            return ""

        original = growth.run_mysql
        try:
            growth.run_mysql = fake_run_mysql
            rows = [
                {"username": "growthalb001", "class_id": "11", "specs": "Slash|39;Dual Wield|50;Parry|28"},
                {"username": "growthalb002", "class_id": "14", "specs": "Slash|1"},
            ]

            promoted = growth.promote_growth_classes_for_level(SimpleNamespace(dry_run=False), rows, current_level=5)
        finally:
            growth.run_mysql = original

        self.assertEqual(promoted, 1)
        self.assertIn("Class = 11", captured["sql"])
        self.assertIn("SerializedSpecs = 'Slash|1;Dual Wield|1;Parry|1'", captured["sql"])
        self.assertIn("growthalb001", captured["sql"])
        self.assertNotIn("growthalb002", captured["sql"])

    def test_apply_low_level_tank_spec_plan_updates_specs_without_shield_size_rewrite(self) -> None:
        captured = {}
        rows = [
            {
                "username": "growthalb701",
                "class_id": "1",
                "specs": "Slash|39;Thrust|1;Crush|1;Two Handed|1;Chants|48;Shields|42;Parry|13",
            }
        ]
        snapshots = {
            "growthalb701": growth.CharacterSnapshot(
                "growthalb701",
                "GrowthAlb701",
                "id",
                7,
                0,
                1,
                1,
                "Slash|7;Chants|4;Shields|2",
                1,
                493679,
                591770,
                1822,
                0,
                53,
                1,
                1,
                serialized_abilities="Sprint|0;Shield|2;AlbArmor|3",
            )
        }

        def fake_run_mysql(_args, sql):
            captured["sql"] = sql
            return ""

        original = growth.run_mysql
        try:
            growth.run_mysql = fake_run_mysql
            changed = growth.apply_growth_low_level_spec_plan(
                SimpleNamespace(dry_run=False, growth_stage="gear"),
                rows,
                snapshots,
                realm=growth.REALMS["alb"],
                current_level=7,
                party_size=1,
            )
        finally:
            growth.run_mysql = original

        self.assertEqual(changed, 1)
        self.assertEqual(
            rows[0]["specs"],
            "Slash|5;Thrust|1;Crush|1;Two Handed|1;Chants|4;Shields|5;Parry|1",
        )
        self.assertIn("SerializedSpecs = 'Slash|5;Thrust|1;Crush|1;Two Handed|1;Chants|4;Shields|5;Parry|1'", captured["sql"])
        self.assertIn("SerializedAbilities = 'Sprint|0;Shield|2;AlbArmor|3'", captured["sql"])

    def test_reset_growth_characters_sets_cumulative_xp_floor(self) -> None:
        captured = []

        def fake_run_mysql(_args, sql):
            captured.append(sql)
            if "SELECT AccountName" in sql:
                return "AccountName\tSerializedSpecs\ngrowthalb001\tSlash|39;Parry|10\n"
            return ""

        original = growth.run_mysql
        try:
            growth.run_mysql = fake_run_mysql
            growth.reset_growth_characters(SimpleNamespace(), ["growthalb001"], level=5)
        finally:
            growth.run_mysql = original

        self.assertIn("Level = 5", captured[0])
        self.assertIn("Experience = 2300", captured[0])

    def test_reset_growth_characters_applies_level50_growth_specs(self) -> None:
        captured = []

        def fake_run_mysql(_args, sql):
            captured.append(sql)
            if "SELECT AccountName, SerializedSpecs" in sql:
                return (
                    "AccountName\tSerializedSpecs\n"
                    "growthalb001\tSlash|1;Thrust|1;Crush|1;Two Handed|1;Chants|1;Shields|1;Parry|1\n"
                    "growthalb002\tSmite|1;Rejuvenation|1;Enhancement|1\n"
                    "growthalb003\tSlash|1;Thrust|1;Crush|1;Polearm|1;Shields|1;Two Handed|1;Parry|1;Crossbows|1\n"
                    "growthalb004\tSlash|1;Thrust|1;Crush|1;Dual Wield|1;Parry|1\n"
                )
            return ""

        original = growth.run_mysql
        try:
            growth.run_mysql = fake_run_mysql
            growth.reset_growth_characters(
                SimpleNamespace(position_step=0),
                ["growthalb001", "growthalb002", "growthalb003", "growthalb004"],
                level=50,
                realm=growth.REALMS["alb"],
            )
        finally:
            growth.run_mysql = original

        update_sql = captured[-1]
        self.assertIn("SerializedSpecs = 'Slash|39;Thrust|1;Crush|1;Two Handed|1;Chants|48;Shields|42;Parry|13'", update_sql)
        self.assertIn("SerializedSpecs = 'Smite|1;Rejuvenation|40;Enhancement|36'", update_sql)
        self.assertIn("SerializedSpecs = 'Slash|1;Thrust|1;Crush|50;Polearm|1;Shields|42;Two Handed|1;Parry|39;Crossbows|1'", update_sql)
        self.assertIn("SerializedSpecs = 'Slash|50;Thrust|1;Crush|1;Dual Wield|50;Parry|28'", update_sql)

    def test_reset_growth_characters_refills_resources_for_checkpoint_runs(self) -> None:
        captured = []

        def fake_run_mysql(_args, sql):
            captured.append(sql)
            if "SELECT AccountName" in sql:
                return "AccountName\tSerializedSpecs\ngrowthalb001\tSlash|39;Parry|10\n"
            return ""

        original = growth.run_mysql
        try:
            growth.run_mysql = fake_run_mysql
            growth.reset_growth_characters(SimpleNamespace(), ["growthalb001"], level=6)
        finally:
            growth.run_mysql = original

        self.assertIn("Health = 1000000", captured[0])
        self.assertIn("Mana = 1000000", captured[0])
        self.assertIn("Endurance = 1000000", captured[0])
        self.assertIn("MaxEndurance = GREATEST(MaxEndurance, 100)", captured[0])
        self.assertIn("GainXP = 1", captured[0])

    def test_reset_growth_characters_can_preserve_money_for_carry_relevel(self) -> None:
        captured = []

        def fake_run_mysql(_args, sql):
            captured.append(sql)
            if "SELECT AccountName" in sql:
                return "AccountName\tSerializedSpecs\ngrowthalb001\tSlash|39;Parry|10\n"
            return ""

        original = growth.run_mysql
        try:
            growth.run_mysql = fake_run_mysql
            growth.reset_growth_characters(
                SimpleNamespace(position_step=0),
                ["growthalb001"],
                level=12,
                realm=growth.REALMS["alb"],
                reset_money=False,
            )
        finally:
            growth.run_mysql = original

        self.assertIn("Level = 12", captured[0])
        self.assertNotIn("Copper = 0", captured[0])
        self.assertNotIn("Silver = 0", captured[0])
        self.assertNotIn("Gold = 0", captured[0])
        self.assertNotIn("Platinum = 0", captured[0])

    def test_rename_watcher_characters_marks_watcher_name(self) -> None:
        captured = {}

        def fake_run_mysql(_args, sql):
            captured["sql"] = sql
            return ""

        original = growth.run_mysql
        try:
            growth.run_mysql = fake_run_mysql
            growth.rename_watcher_characters(SimpleNamespace(dry_run=False), ["growthalb701"])
        finally:
            growth.run_mysql = original

        self.assertIn("growthalb701", captured["sql"])
        self.assertIn("\uac10\uc2dc\uc790GrowthAlb701", captured["sql"])

    def test_watcher_command_follows_named_primary_without_combat(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            watcher_follow_interval=0.4,
            watcher_follow_distance=550.0,
            watcher_follow_max_distance=9000.0,
            watcher_movement_speed=150.0,
        )

        command = growth.build_watcher_command(
            args=args,
            realm=growth.REALMS["alb"],
            watcher_csv=Path("watcher.csv"),
            case_dir=Path("case"),
            segment_index=1,
            watcher_index=0,
            primary_account="growthalb701",
            current_level=1,
            path_graph=Path("graph.json"),
        )

        self.assertIn("--follow-nearby-player", command)
        self.assertIn("--follow-player-name", command)
        self.assertEqual(command[command.index("--follow-player-name") + 1], "GrowthAlb701")
        self.assertIn("--trace-observed-player-positions", command)
        self.assertIn("--move", command)
        self.assertIn("--required-target-home", command)
        self.assertEqual(command[command.index("--movement-speed") + 1], "240.0")
        self.assertEqual(command[command.index("--required-target-home-stop-distance") + 1], "8000.0")
        self.assertEqual(command[command.index("--player-follow-distance") + 1], "8000.0")
        self.assertEqual(command[command.index("--player-follow-step") + 1], "240")
        self.assertEqual(command[command.index("--follow-player-max-distance") + 1], "60000.0")
        self.assertIn("--follow-player-hold-allows-waypoint", command)
        self.assertEqual(command[command.index("--player-state-max-age") + 1], "60")
        self.assertIn("--flee-health-percent", command)
        self.assertEqual(command[command.index("--flee-health-percent") + 1], "90")
        self.assertEqual(command[command.index("--flee-pressure-health-percent") + 1], "99")
        self.assertEqual(command[command.index("--flee-step") + 1], "1200")
        self.assertEqual(command[command.index("--flee-movement-speed") + 1], "240.0")
        self.assertIn("--flee-home", command)
        self.assertIn("--flee-dynamic-safe-point", command)
        self.assertEqual(command[command.index("--flee-critical-health-percent") + 1], "90")
        self.assertEqual(command[command.index("--flee-critical-safe-point-distance") + 1], "10000")
        self.assertIn("--flee-safe-api-scout", command)
        self.assertEqual(command[command.index("--flee-safe-replan-damage-grace") + 1], "6")
        self.assertEqual(command[command.index("--flee-town-health-percent") + 1], "10")
        self.assertIn("--waypoints", command)
        self.assertEqual(command[command.index("--waypoints") + 1], command[command.index("--required-target-home") + 1])
        self.assertNotEqual(
            command[command.index("--required-target-home") + 1],
            growth.route_home_string(growth.REALMS["alb"], 1, ground_z_offset=0),
        )
        self.assertEqual(command[command.index("--path-last-mile-distance") + 1], "8000.0")
        self.assertEqual(command[command.index("--path-max-height-delta") + 1], "900")
        self.assertEqual(command[command.index("--startup-command") + 1], "/sprint")
        self.assertEqual(command[command.index("--startup-delay") + 1], "0.5")
        self.assertNotIn("--waypoint-continuous-turns", command)
        self.assertNotIn("--hunter", command)
        self.assertNotIn("--combat", command)

    def test_level_ten_watcher_uses_same_startup_teleporter_flow(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            segment_seconds=45,
            ramp_up=2,
            login_retries=5,
            login_retry_delay=3.0,
            api_port=5000,
            smooth_move_interval=0.2,
            movement_speed=191.0,
            path_last_mile_distance=1200.0,
            ground_z_offset=0,
            encounter_log_interval=3.0,
            nav_api_url="http://127.0.0.1:5000",
            live_api_url="",
            watcher_follow_interval=0.4,
            watcher_follow_distance=550.0,
            watcher_follow_max_distance=9000.0,
            watcher_movement_speed=150.0,
        )

        command = growth.build_watcher_command(
            args=args,
            realm=growth.REALMS["alb"],
            watcher_csv=Path("watcher.csv"),
            case_dir=Path("case"),
            segment_index=1,
            watcher_index=0,
            primary_account="growthalb701",
            current_level=10,
            path_graph=Path("graph.json"),
        )

        self.assertIn("--startup-teleport-destination", command)
        self.assertEqual(command[command.index("--startup-teleport-destination") + 1], "Castle Sauvage")
        self.assertIn("--startup-teleport-warmup-whisper", command)
        self.assertEqual(command[command.index("--startup-teleport-warmup-whisper") + 1], "towns")

    def test_watcher_pair_summary_flags_large_z_and_rewind(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            primary = root / "primary.jsonl"
            watcher = root / "watcher.jsonl"
            primary.write_text(
                "\n".join(
                    [
                        '{"event":"move_step","x":0,"y":0,"z":100}',
                        '{"event":"move_step","x":1000,"y":0,"z":100}',
                        '{"event":"move_step","x":0,"y":0,"z":100}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            watcher.write_text(
                "\n".join(
                    [
                        '{"event":"move_step","x":0,"y":0,"z":500}',
                        '{"event":"move_step","x":1000,"y":0,"z":500}',
                        '{"event":"move_step","x":0,"y":0,"z":500}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.compare_watcher_pair(
                primary,
                watcher,
                z_warn_delta=180.0,
                xy_warn_delta=1800.0,
                rewind_warn_distance=650.0,
                z_compare_xy_distance=850.0,
            )

        self.assertEqual(summary["samples"], 3)
        self.assertEqual(summary["watcher_status"], "ok")
        self.assertEqual(summary["z_status"], "warn")
        self.assertEqual(summary["rewind_status"], "warn")

    def test_watcher_pair_summary_accepts_stationary_observer_positions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            primary = root / "primary.jsonl"
            watcher = root / "watcher.jsonl"
            primary.write_text(
                "\n".join(
                    [
                        '{"t":1.0,"event":"move_step","x":0,"y":0,"z":100}',
                        '{"t":2.0,"event":"move_step","x":100,"y":0,"z":100}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            watcher.write_text(
                "\n".join(
                    [
                        '{"t":1.0,"event":"send_position","x":0,"y":0,"z":100,"speed":"0.000"}',
                        '{"t":2.0,"event":"send_position","x":0,"y":0,"z":100,"speed":"0.000"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.compare_watcher_pair(
                primary,
                watcher,
                z_warn_delta=180.0,
                xy_warn_delta=18000.0,
                rewind_warn_distance=650.0,
                z_compare_xy_distance=5600.0,
            )

        self.assertEqual(summary["samples"], 2)
        self.assertEqual(summary["watcher_moves"], 0)
        self.assertEqual(summary["watcher_status"], "ok")
        self.assertEqual(summary["z_status"], "ok")

    def test_primary_anomaly_ignores_scan_empty_after_target_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            primary = root / "primary.jsonl"
            watcher = root / "watcher.jsonl"
            encounter = root / "encounter.jsonl"
            primary.write_text(
                "\n".join(
                    [
                        '{"t":1.0,"event":"move_step","x":0,"y":0,"z":100}',
                        '{"t":2.0,"event":"move_step","x":100,"y":0,"z":100}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            watcher.write_text(
                "\n".join(
                    [
                        '{"t":1.0,"event":"send_position","x":0,"y":0,"z":100,"speed":"0.000"}',
                        '{"t":2.0,"event":"send_position","x":0,"y":0,"z":100,"speed":"0.000"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            encounter.write_text(
                "\n".join(
                    [
                        '{"t":5.0,"event":"combat_finish","outcome":"target_removed","target_name":"small bear"}',
                        '{"t":10.0,"event":"hunter_target_scan_empty","hunter_visible_npcs":12,"hunter_eligible_npcs":0,"hunter_reject_counts":{"level":12}}',
                        '{"t":11.0,"event":"hunter_target_scan_empty","hunter_visible_npcs":12,"hunter_eligible_npcs":0,"hunter_reject_counts":{"level":12}}',
                        '{"t":12.0,"event":"hunter_target_scan_empty","hunter_visible_npcs":12,"hunter_eligible_npcs":0,"hunter_reject_counts":{"level":12}}',
                        '{"t":13.0,"event":"encounter_tick","current_target":0,"health_percent":100,"is_dead":false}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.compare_watcher_pair(
                primary,
                watcher,
                primary_encounter_path=encounter,
                z_warn_delta=180.0,
                xy_warn_delta=18000.0,
                rewind_warn_distance=650.0,
                z_compare_xy_distance=5600.0,
            )

        self.assertEqual(summary["primary_anomaly_status"], "ok")
        self.assertEqual(summary["primary_anomaly_reason"], "")

    def test_watcher_pair_summary_does_not_flag_startup_teleport_as_rewind(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            primary = root / "primary.jsonl"
            watcher = root / "watcher.jsonl"
            content = (
                '{"t":1.0,"event":"move_step","x":1000,"y":1000,"z":100}\n'
                '{"t":2.0,"event":"startup_teleport_sync","x":50000,"y":50000,"z":100}\n'
                '{"t":3.0,"event":"move_step","x":50100,"y":50100,"z":100,"sampled_ground_z":100}\n'
                '{"t":4.0,"event":"move_step","x":50200,"y":50200,"z":100,"sampled_ground_z":100}\n'
            )
            primary.write_text(content, encoding="utf-8")
            watcher.write_text(content, encoding="utf-8")

            summary = growth.compare_watcher_pair(
                primary,
                watcher,
                z_warn_delta=180.0,
                xy_warn_delta=18000.0,
                rewind_warn_distance=650.0,
                z_compare_xy_distance=5600.0,
            )

        self.assertEqual(summary["rewind_status"], "ok")
        self.assertEqual(summary["rewind_events"], 0)

    def test_watcher_pair_summary_does_not_flag_pre_teleport_pair_gap_as_xy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            primary = root / "primary.jsonl"
            watcher = root / "watcher.jsonl"
            primary.write_text(
                "\n".join(
                    [
                        '{"t":1.0,"event":"move_step","x":0,"y":0,"z":100}',
                        '{"t":5.0,"event":"move_step","x":100,"y":0,"z":100}',
                        '{"t":10.0,"event":"startup_teleport_sync","x":50000,"y":50000,"z":100}',
                        '{"t":11.0,"event":"move_step","x":50020,"y":50000,"z":100,"sampled_ground_z":100}',
                        '{"t":12.0,"event":"move_step","x":50100,"y":50000,"z":100,"sampled_ground_z":100}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            watcher.write_text(
                "\n".join(
                    [
                        '{"t":1.0,"event":"move_step","x":0,"y":10,"z":100}',
                        '{"t":4.0,"event":"startup_teleport_sync","x":50000,"y":50000,"z":100}',
                        '{"t":6.0,"event":"move_step","x":50010,"y":50000,"z":100,"sampled_ground_z":100}',
                        '{"t":7.0,"event":"move_step","x":50020,"y":50000,"z":100,"sampled_ground_z":100}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.compare_watcher_pair(
                primary,
                watcher,
                z_warn_delta=180.0,
                xy_warn_delta=18000.0,
                rewind_warn_distance=650.0,
                z_compare_xy_distance=5600.0,
            )

        self.assertEqual(summary["samples"], 2)
        self.assertLess(summary["max_xy_delta"], 200.0)
        self.assertEqual(summary["xy_status"], "ok")

    def test_watcher_z_status_only_uses_close_xy_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            primary = root / "primary.jsonl"
            watcher = root / "watcher.jsonl"
            primary.write_text(
                "\n".join(
                    [
                        '{"event":"move_step","x":0,"y":0,"z":100}',
                        '{"event":"move_step","x":5000,"y":0,"z":100}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            watcher.write_text(
                "\n".join(
                    [
                        '{"event":"move_step","x":50,"y":0,"z":110}',
                        '{"event":"move_step","x":8000,"y":0,"z":1000}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.compare_watcher_pair(
                primary,
                watcher,
                z_warn_delta=180.0,
                xy_warn_delta=4000.0,
                rewind_warn_distance=6500.0,
                z_compare_xy_distance=850.0,
            )

        self.assertEqual(summary["close_xy_samples"], 1)
        self.assertEqual(summary["max_abs_z_delta"], 900.0)
        self.assertEqual(summary["max_close_abs_z_delta"], 10.0)
        self.assertEqual(summary["watcher_status"], "ok")
        self.assertEqual(summary["z_status"], "ok")

    def test_watcher_z_status_prefers_ground_sampler_delta(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            primary = root / "primary.jsonl"
            watcher = root / "watcher.jsonl"
            primary.write_text(
                "\n".join(
                    [
                        '{"event":"move_step","x":0,"y":0,"z":100,"sampled_ground_z":100,"z_source":"ground_z_sampler"}',
                        '{"event":"move_step","x":100,"y":0,"z":105,"sampled_ground_z":105,"z_source":"ground_z_sampler"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            watcher.write_text(
                "\n".join(
                    [
                        '{"event":"move_step","x":50,"y":0,"z":420,"sampled_ground_z":420,"z_source":"ground_z_sampler"}',
                        '{"event":"move_step","x":150,"y":0,"z":425,"sampled_ground_z":425,"z_source":"ground_z_sampler"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.compare_watcher_pair(
                primary,
                watcher,
                z_warn_delta=180.0,
                xy_warn_delta=1800.0,
                rewind_warn_distance=6500.0,
                z_compare_xy_distance=850.0,
            )

        self.assertEqual(summary["max_close_abs_z_delta"], 320.0)
        self.assertEqual(summary["max_ground_abs_z_delta"], 0.0)
        self.assertEqual(summary["ground_z_delta_samples"], 4)
        self.assertEqual(summary["z_status"], "ok")

    def test_watcher_z_status_ignores_blank_ground_sampler_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            primary = root / "primary.jsonl"
            watcher = root / "watcher.jsonl"
            primary.write_text(
                '{"event":"move_step","x":0,"y":0,"z":11462,"sampled_ground_z":"","z_source":"interpolated"}\n',
                encoding="utf-8",
            )
            watcher.write_text(
                '{"event":"move_step","x":10,"y":0,"z":11462,"sampled_ground_z":"","z_source":"interpolated"}\n',
                encoding="utf-8",
            )

            summary = growth.compare_watcher_pair(
                primary,
                watcher,
                z_warn_delta=180.0,
                xy_warn_delta=1800.0,
                rewind_warn_distance=6500.0,
                z_compare_xy_distance=850.0,
            )

        self.assertEqual(summary["ground_z_delta_samples"], 0)
        self.assertEqual(summary["max_ground_abs_z_delta"], 0.0)
        self.assertEqual(summary["z_status"], "ok")

    def test_watcher_pair_summary_matches_samples_by_time_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            primary = root / "primary.jsonl"
            watcher = root / "watcher.jsonl"
            primary.write_text(
                "\n".join(
                    [
                        '{"t":10.0,"event":"move_step","x":1000,"y":0,"z":100}',
                        '{"t":20.0,"event":"move_step","x":2000,"y":0,"z":100}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            watcher.write_text(
                "\n".join(
                    [
                        '{"t":1.0,"event":"move_step","x":9000,"y":0,"z":100}',
                        '{"t":10.1,"event":"move_step","x":1010,"y":0,"z":100}',
                        '{"t":20.1,"event":"move_step","x":2010,"y":0,"z":100}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.compare_watcher_pair(
                primary,
                watcher,
                z_warn_delta=180.0,
                xy_warn_delta=1800.0,
                rewind_warn_distance=6500.0,
                z_compare_xy_distance=850.0,
            )

        self.assertEqual(summary["samples"], 2)
        self.assertEqual(summary["max_xy_delta"], 10.0)
        self.assertEqual(summary["xy_status"], "ok")

    def test_watcher_pair_summary_ignores_primary_recovery_return_for_xy_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            primary = root / "primary.jsonl"
            watcher = root / "watcher.jsonl"
            encounter = root / "primary-encounter.jsonl"
            primary.write_text(
                "\n".join(
                    [
                        '{"t":10.0,"event":"move_step","x":25000,"y":0,"z":100}',
                        '{"t":20.0,"event":"move_step","x":100,"y":0,"z":100}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            watcher.write_text(
                "\n".join(
                    [
                        '{"t":10.0,"event":"move_step","x":0,"y":0,"z":100}',
                        '{"t":20.0,"event":"move_step","x":0,"y":0,"z":100}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            encounter.write_text(
                "\n".join(
                    [
                        '{"t":9.0,"event":"behavior_state_change","behavior_state":"ReturnToObjective"}',
                        '{"t":19.0,"event":"behavior_state_change","behavior_state":"HuntObjective"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.compare_watcher_pair(
                primary,
                watcher,
                primary_encounter_path=encounter,
                z_warn_delta=180.0,
                xy_warn_delta=18000.0,
                rewind_warn_distance=6500.0,
                z_compare_xy_distance=850.0,
            )

        self.assertGreater(summary["max_xy_delta"], 18000.0)
        self.assertEqual(summary["xy_status"], "ok")

    def test_watcher_summary_flags_primary_idle_with_visible_but_ineligible_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            primary = root / "primary.jsonl"
            watcher = root / "watcher.jsonl"
            encounter = root / "primary-encounter.jsonl"
            primary.write_text(
                "\n".join(
                    [
                        '{"t":1.0,"event":"move_step","x":0,"y":0,"z":100}',
                        '{"t":2.0,"event":"move_step","x":100,"y":0,"z":100}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            watcher.write_text(
                "\n".join(
                    [
                        '{"t":1.0,"event":"move_step","x":10,"y":0,"z":100}',
                        '{"t":2.0,"event":"move_step","x":110,"y":0,"z":100}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            encounter.write_text(
                "\n".join(
                    [
                        '{"t":15.0,"event":"encounter_tick","current_target":0,"health_percent":100,"is_dead":false}',
                        '{"t":18.0,"event":"encounter_tick","current_target":0,"health_percent":100,"is_dead":false}',
                        '{"t":21.0,"event":"encounter_tick","current_target":0,"health_percent":100,"is_dead":false}',
                        '{"t":22.0,"event":"hunter_target_scan_empty","hunter_visible_npcs":8,"hunter_eligible_npcs":0,"hunter_reject_counts":{"visible":8,"eligible":0,"level":7,"distance":1}}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.compare_watcher_pair(
                primary,
                watcher,
                primary_encounter_path=encounter,
                z_warn_delta=180.0,
                xy_warn_delta=1800.0,
                rewind_warn_distance=6500.0,
                z_compare_xy_distance=850.0,
            )

        self.assertEqual(summary["primary_scan_empty_eligible_zero_events"], 1)
        self.assertEqual(summary["primary_scan_empty_top_reason"], "level")
        self.assertEqual(summary["primary_anomaly_status"], "warn")
        self.assertIn("scan_empty:level", summary["primary_anomaly_reason"])

    def test_watcher_summary_escalates_repeated_scan_empty_to_critical(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            primary = root / "primary.jsonl"
            watcher = root / "watcher.jsonl"
            encounter = root / "primary-encounter.jsonl"
            primary.write_text('{"t":1.0,"event":"move_step","x":0,"y":0,"z":100}\n', encoding="utf-8")
            watcher.write_text('{"t":1.0,"event":"move_step","x":10,"y":0,"z":100}\n', encoding="utf-8")
            encounter.write_text(
                "\n".join(
                    [
                        '{"t":11.0,"event":"encounter_tick","current_target":0,"health_percent":100,"is_dead":false}',
                        '{"t":12.0,"event":"hunter_target_scan_empty","hunter_visible_npcs":8,"hunter_eligible_npcs":0,"hunter_reject_counts":{"visible":8,"eligible":0,"level":8}}',
                        '{"t":14.0,"event":"encounter_tick","current_target":0,"health_percent":100,"is_dead":false}',
                        '{"t":15.0,"event":"hunter_target_scan_empty","hunter_visible_npcs":8,"hunter_eligible_npcs":0,"hunter_reject_counts":{"visible":8,"eligible":0,"level":8}}',
                        '{"t":17.0,"event":"encounter_tick","current_target":0,"health_percent":100,"is_dead":false}',
                        '{"t":18.0,"event":"hunter_target_scan_empty","hunter_visible_npcs":8,"hunter_eligible_npcs":0,"hunter_reject_counts":{"visible":8,"eligible":0,"level":8}}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.compare_watcher_pair(
                primary,
                watcher,
                primary_encounter_path=encounter,
                z_warn_delta=180.0,
                xy_warn_delta=1800.0,
                rewind_warn_distance=6500.0,
                z_compare_xy_distance=850.0,
            )

        self.assertEqual(summary["primary_scan_empty_eligible_zero_events"], 3)
        self.assertEqual(summary["primary_anomaly_status"], "critical")
        self.assertIn("scan_empty:level", summary["primary_anomaly_reason"])

    def test_watcher_summary_ignores_trailing_post_combat_gap_without_scan_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            primary = root / "primary.jsonl"
            watcher = root / "watcher.jsonl"
            encounter = root / "primary-encounter.jsonl"
            primary.write_text('{"t":1.0,"event":"move_step","x":0,"y":0,"z":100}\n', encoding="utf-8")
            watcher.write_text('{"t":1.0,"event":"move_step","x":10,"y":0,"z":100}\n', encoding="utf-8")
            encounter.write_text(
                "\n".join(
                    [
                        '{"t":10.0,"event":"combat_finish","outcome":"target_removed"}',
                        '{"t":35.0,"event":"encounter_tick","current_target":0,"health_percent":70,"is_dead":false}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.compare_watcher_pair(
                primary,
                watcher,
                primary_encounter_path=encounter,
                z_warn_delta=180.0,
                xy_warn_delta=1800.0,
                rewind_warn_distance=6500.0,
                z_compare_xy_distance=850.0,
            )

        self.assertEqual(summary["primary_combat_gap_max_seconds"], 0.0)
        self.assertEqual(summary["primary_anomaly_status"], "ok")

    def test_watcher_behavior_summary_flags_flee_threat_still_aggroed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "encounter.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"t":10.0,"event":"flee_start","character":"GrowthMid701","reason":"multi_aggro","health_percent":72}',
                        '{"t":28.5,"event":"flee_threat_pressure","character":"GrowthMid701","flee_threat_name":"huldu hunter","flee_threat_distance":680,"flee_threat_active":true,"flee_threat_target":"GrowthMid701"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.primary_behavior_anomaly_summary(path, prefer_target_name="huldu hunter")

        self.assertEqual(summary["primary_behavior_anomaly_status"], "critical")
        self.assertIn("aggro_not_dropped", summary["primary_behavior_anomaly_reason"])
        self.assertIn("flee_too_short", summary["primary_behavior_anomaly_reason"])

    def test_watcher_behavior_summary_does_not_flag_recovered_flee_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "encounter.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"t":10.0,"event":"flee_start","character":"GrowthMid701","health_percent":80}',
                        '{"t":28.5,"event":"flee_threat_pressure","character":"GrowthMid701","flee_threat_name":"huldu hunter","flee_threat_distance":680,"flee_threat_active":true,"flee_threat_target":"GrowthMid701"}',
                        '{"t":58.5,"event":"flee_recovered","character":"GrowthMid701","health_percent":82}',
                        '{"t":70.0,"event":"flee_finished","character":"GrowthMid701","health_percent":88}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.primary_behavior_anomaly_summary(path, prefer_target_name="huldu hunter")

        self.assertEqual(summary["primary_behavior_anomaly_status"], "ok")
        self.assertEqual(summary["primary_behavior_anomaly_reason"], "")

    def test_watcher_behavior_summary_allows_open_far_flee_window_under_clear_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "encounter.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"t":10.0,"event":"flee_start","character":"GrowthMid701","health_percent":77,"x":1000,"y":1000}',
                        '{"t":36.0,"event":"flee_threat_pressure","character":"GrowthMid701","flee_threat_name":"huldu hunter","flee_threat_distance":2845,"flee_threat_active":true,"flee_threat_target":"GrowthMid701","x":4500,"y":5200}',
                        '{"t":40.0,"event":"encounter_tick","character":"GrowthMid701","health_percent":70,"current_target":0,"target_visible":false}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.primary_behavior_anomaly_summary(path, prefer_target_name="huldu hunter")

        self.assertEqual(summary["primary_behavior_anomaly_status"], "ok")
        self.assertEqual(summary["primary_behavior_anomaly_reason"], "")

    def test_watcher_behavior_summary_flags_finished_far_active_flee_without_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "encounter.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"t":10.0,"event":"flee_start","character":"GrowthMid701","health_percent":77,"x":1000,"y":1000}',
                        '{"t":36.0,"event":"flee_threat_pressure","character":"GrowthMid701","flee_threat_name":"huldu hunter","flee_threat_distance":2845,"flee_threat_active":true,"flee_threat_target":"GrowthMid701","x":4500,"y":5200}',
                        '{"t":45.0,"event":"flee_finished","character":"GrowthMid701","health_percent":74}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.primary_behavior_anomaly_summary(path, prefer_target_name="huldu hunter")

        self.assertEqual(summary["primary_behavior_anomaly_status"], "critical")
        self.assertIn("aggro_not_dropped", summary["primary_behavior_anomaly_reason"])

    def test_watcher_behavior_summary_treats_safe_low_health_rest_as_aggro_clear(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "encounter.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"t":10.0,"event":"flee_start","character":"GrowthMid701","health_percent":56}',
                        '{"t":28.5,"event":"flee_threat_pressure","character":"GrowthMid701","flee_threat_name":"wildling","flee_threat_distance":680,"flee_threat_active":true,"flee_threat_target":"GrowthMid701"}',
                        '{"t":58.5,"event":"low_health_rest","character":"GrowthMid701","health_percent":30,"current_target":0,"target_visible":false}',
                        '{"t":70.0,"event":"encounter_tick","character":"GrowthMid701","health_percent":38,"current_target":0,"target_visible":false}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.primary_behavior_anomaly_summary(path, prefer_target_name="wildling")

        self.assertEqual(summary["primary_behavior_anomaly_status"], "ok")
        self.assertEqual(summary["primary_behavior_anomaly_reason"], "")

    def test_watcher_behavior_summary_flags_stuck_and_bad_target_choice(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "encounter.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"t":5.0,"event":"combat_start","target_name":"huldu stalker","target_level":5,"health_percent":100}',
                        '{"t":24.0,"event":"combat_finish","outcome":"flee","target_name":"huldu stalker","target_level":5,"duration_seconds":19.0,"damage_done":8,"damage_taken":96}',
                        '{"t":30.0,"event":"combat_start","target_name":"huldu stalker","target_level":5,"health_percent":95}',
                        '{"t":50.0,"event":"combat_finish","outcome":"flee","target_name":"huldu stalker","target_level":5,"duration_seconds":20.0,"damage_done":10,"damage_taken":110}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.primary_behavior_anomaly_summary(path, prefer_target_name="huldu hunter,phantom hound")

        self.assertEqual(summary["primary_behavior_anomaly_status"], "critical")
        self.assertIn("target_stuck", summary["primary_behavior_anomaly_reason"])
        self.assertIn("bad_target_choice", summary["primary_behavior_anomaly_reason"])

    def test_watcher_behavior_summary_allows_weak_flee_then_successful_recovery_kill(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "encounter.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"t":5.0,"event":"combat_start","target_name":"rock imp","target_level":5,"health_percent":100}',
                        '{"t":32.0,"event":"combat_finish","outcome":"flee","target_name":"rock imp","target_level":5,"duration_seconds":27.0,"damage_done":30,"damage_taken":120}',
                        '{"t":33.0,"event":"flee_start","character":"GrowthAlb701","health_percent":67}',
                        '{"t":70.0,"event":"flee_recovered","character":"GrowthAlb701","health_percent":88}',
                        '{"t":90.0,"event":"combat_start","target_name":"rock imp","target_level":4,"health_percent":95}',
                        '{"t":132.0,"event":"combat_finish","outcome":"target_removed","target_name":"rock imp","target_level":4,"duration_seconds":42.0,"damage_done":90,"damage_taken":36}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.primary_behavior_anomaly_summary(path, prefer_target_name="rock imp")

        self.assertEqual(summary["primary_behavior_anomaly_status"], "ok")
        self.assertEqual(summary["primary_behavior_anomaly_reason"], "")
        self.assertEqual(summary["primary_behavior_target_stuck"], 0)

    def test_watcher_behavior_summary_allows_single_unpreferred_target_without_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "encounter.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"t":5.0,"event":"combat_start","target_name":"huldu stalker","target_level":5,"health_percent":100}',
                        '{"t":11.0,"event":"combat_finish","outcome":"target_removed","target_name":"huldu stalker","target_level":5,"duration_seconds":6.0,"damage_done":80,"damage_taken":12}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.primary_behavior_anomaly_summary(path, prefer_target_name="huldu hunter,phantom hound")

        self.assertEqual(summary["primary_behavior_anomaly_status"], "ok")
        self.assertEqual(summary["primary_behavior_anomaly_reason"], "")

    def test_watcher_behavior_summary_flags_safe_exit_deadline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "encounter.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"t":5.0,"event":"combat_finish","outcome":"target_removed","active_target_name":"moorlich","duration_seconds":18.0}',
                        '{"t":70.0,"event":"safe_exit_complete","safe_exit_deadline_reached":true,"health_percent":75,"behavior_state":"RestRecover"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.primary_behavior_anomaly_summary(path, prefer_target_name="moorlich")

        self.assertEqual(summary["primary_behavior_anomaly_status"], "critical")
        self.assertIn("safe_exit_deadline", summary["primary_behavior_anomaly_reason"])
        self.assertEqual(summary["primary_behavior_safe_exit_deadline"], 1)

    def test_watcher_behavior_summary_allows_deadline_recovered_safe_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "encounter.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"t":5.0,"event":"combat_finish","outcome":"target_removed","active_target_name":"moorlich","duration_seconds":18.0}',
                        '{"t":70.0,"event":"safe_exit_complete","safe_exit_deadline_reached":true,"safe_exit_deadline_completed_recovered":true,"health_percent":88,"behavior_state":"RestRecover"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.primary_behavior_anomaly_summary(path, prefer_target_name="moorlich")

        self.assertEqual(summary["primary_behavior_anomaly_status"], "ok")
        self.assertEqual(summary["primary_behavior_anomaly_reason"], "")
        self.assertEqual(summary["primary_behavior_safe_exit_deadline"], 0)

    def test_watcher_behavior_summary_flags_pressure_after_target_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "encounter.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"t":5.0,"event":"combat_finish","outcome":"target_removed","active_target_name":"moorlich","duration_seconds":18.0}',
                        '{"t":20.0,"event":"flee_start","character":"GrowthAlb1201","reason":"untracked_damage","health_percent":42}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.primary_behavior_anomaly_summary(path, prefer_target_name="moorlich")

        self.assertEqual(summary["primary_behavior_anomaly_status"], "critical")
        self.assertIn("post_target_removed_pressure", summary["primary_behavior_anomaly_reason"])
        self.assertEqual(summary["primary_behavior_post_target_removed_pressure"], 1)

    def test_watcher_behavior_summary_allows_required_target_safe_exit_after_target_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "encounter.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"t":5.0,"event":"combat_finish","outcome":"target_removed","active_target_name":"moorlich","duration_seconds":18.0}',
                        '{"t":5.1,"event":"required_target_complete_pending_safe_exit","active_target_name":"moorlich"}',
                        '{"t":5.2,"event":"flee_start","character":"GrowthAlb1201","reason":"required_target_complete","health_percent":54}',
                        '{"t":7.0,"event":"server_message","text":"A dead enemy hit you for 62 damage."}',
                        '{"t":7.5,"event":"required_target_complete_shared","active_target_name":"moorlich"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.primary_behavior_anomaly_summary(path, prefer_target_name="moorlich")

        self.assertEqual(summary["primary_behavior_anomaly_status"], "ok")
        self.assertEqual(summary["primary_behavior_anomaly_reason"], "")
        self.assertEqual(summary["primary_behavior_post_target_removed_pressure"], 0)

    def test_watcher_behavior_summary_allows_safe_recovery_after_target_removed_pressure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "encounter.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"t":5.0,"event":"combat_finish","outcome":"target_removed","active_target_name":"black wolf pup","duration_seconds":18.0}',
                        '{"t":20.0,"event":"flee_start","character":"GrowthAlb1201","reason":"critical_health_drop_aggro","health_percent":42}',
                        '{"t":58.0,"event":"flee_recovered","character":"GrowthAlb1201","health_percent":54}',
                        '{"t":60.0,"event":"low_health_rest","character":"GrowthAlb1201","health_percent":54,"current_target":0,"target_visible":false}',
                        '{"t":95.0,"event":"encounter_tick","character":"GrowthAlb1201","health_percent":88,"current_target":0,"target_visible":false}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = growth.primary_behavior_anomaly_summary(path, prefer_target_name="black wolf pup")

        self.assertEqual(summary["primary_behavior_anomaly_status"], "ok")
        self.assertEqual(summary["primary_behavior_anomaly_reason"], "")
        self.assertEqual(summary["primary_behavior_post_target_removed_pressure"], 0)

    def test_watcher_regression_fails_on_primary_behavior_anomaly_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            metrics = root / "segment-001-watcher-01-metrics.csv"
            metrics.write_text(
                "username,ok,elapsed_seconds,actions,combat_engagements,target_removed,player_deaths,target_timeouts,movement_failures,loot_acquired\n"
                "watcher,true,1.0,1,0,0,0,0,0,0\n",
                encoding="utf-8",
            )
            summary = root / "watcher-movement-summary.csv"
            summary.write_text(
                "case,segment,primary_account,watcher_account,primary_behavior_anomaly_status,primary_behavior_anomaly_reason\n"
                "mid-p1,1,primary,watcher,critical,aggro_not_dropped\n",
                encoding="utf-8",
            )

            ok = growth.watcher_regression_passed(
                root,
                1,
                [("primary", "watcher", root / "watcher.csv")],
            )

        self.assertFalse(ok)

    def test_watcher_regression_allows_post_target_pressure_after_successful_segment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            root = output / "alb-p1"
            root.mkdir()
            (output / "timeline.csv").write_text(
                "case,segment,target_removed,xp_effective_delta,death_delta,movement_failures,bottleneck_reason\n"
                "alb-p1,1,3,12126,0,0,none\n",
                encoding="utf-8",
            )
            metrics = root / "segment-001-watcher-01-metrics.csv"
            metrics.write_text(
                "username,ok,elapsed_seconds,actions,combat_engagements,target_removed,player_deaths,target_timeouts,movement_failures,loot_acquired\n"
                "watcher,true,1.0,1,0,0,0,0,0,0\n",
                encoding="utf-8",
            )
            summary = root / "watcher-movement-summary.csv"
            summary.write_text(
                "case,segment,primary_account,watcher_account,primary_behavior_anomaly_status,primary_behavior_anomaly_reason\n"
                "alb-p1,1,primary,watcher,critical,flee_too_short;post_target_removed_pressure\n",
                encoding="utf-8",
            )

            ok = growth.watcher_regression_passed(
                root,
                1,
                [("primary", "watcher", root / "watcher.csv")],
            )

        self.assertTrue(ok)

    def test_watcher_regression_fails_on_watcher_death(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            metrics = root / "segment-001-watcher-01-metrics.csv"
            metrics.write_text(
                "username,ok,elapsed_seconds,actions,combat_engagements,target_removed,player_deaths,target_timeouts,movement_failures,loot_acquired\n"
                "watcher,true,1.0,1,0,0,1,0,0,0\n",
                encoding="utf-8",
            )

            ok = growth.watcher_regression_passed(
                root,
                1,
                [("primary", "watcher", root / "watcher.csv")],
            )

        self.assertFalse(ok)

    def test_movement_trace_death_updates_segment_metrics_for_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            movement_dir = root / "movement"
            movement_dir.mkdir()
            (movement_dir / "segment-016-growthmid60121-1.jsonl").write_text(
                '{"t":55.0,"event":"player_death","character":"growthmid60121"}\n',
                encoding="utf-8",
            )
            metrics_by_user = {"growthmid60121": growth.empty_metric_summary()}
            fallback_metrics = growth.empty_metric_summary()

            deaths_by_account = growth.apply_movement_trace_deaths_to_metrics(
                metrics_by_user,
                fallback_metrics,
                root,
                16,
                ["growthmid60121"],
            )

        self.assertEqual(deaths_by_account, {"growthmid60121": 1})
        self.assertEqual(metrics_by_user["growthmid60121"]["player_deaths"], 1)
        self.assertEqual(fallback_metrics["player_deaths"], 1)
        self.assertFalse(growth.segment_regression_passed(fallback_metrics, require_kill=False))

    def test_timeline_rows_include_growth_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "timeline.csv"
            growth.write_timeline_row(
                path,
                {
                    "timestamp_utc": "2026-05-21T00:00:00+00:00",
                    "case": "alb-p1",
                    "realm": "alb",
                    "party_size": 1,
                    "segment": 1,
                    "account": "growthalb701",
                    "character": "GrowthAlb701",
                    "growth_role": "tracked",
                    "class_id": 1,
                    "specs_before": "Slash|1",
                    "specs_after": "Slash|2",
                    "spec_gain": "Slash+1",
                    "level_before": 1,
                    "level_after": 2,
                    "level_delta": 1,
                    "xp_before": 0,
                    "xp_after": 100,
                    "xp_delta": 100,
                    "text_xp_delta": 100,
                    "text_xp_messages": 1,
                    "xp_effective_delta": 100,
                    "xp_persist_lag": 0,
                    "xp_persist_status": "synced",
                    "money_before_copper": 0,
                    "money_after_copper": 12,
                    "money_delta_copper": 12,
                    "inventory_rows_before": 1,
                    "inventory_rows_after": 2,
                    "inventory_rows_delta": 1,
                    "inventory_items_before": 1,
                    "inventory_items_after": 3,
                    "inventory_items_delta": 2,
                    "train_command_sent": 1,
                    "train_verified": 1,
                    "death_before": 0,
                    "death_after": 0,
                    "death_delta": 0,
                    "region_after": 1,
                    "x_after": 1,
                    "y_after": 2,
                    "z_after": 3,
                    "metric_rows": 1,
                    "ok_rows": 1,
                    "actions": 10,
                    "elapsed_seconds": "60.000",
                    "combat_engagements": 2,
                    "target_removed": 1,
                    "target_removed_no_reward": 0,
                    "player_deaths": 0,
                    "target_timeouts": 0,
                    "movement_failures": 0,
                    "loot_acquired": 1,
                    "startup_service_dialog_settle": 1,
                    "startup_service_equip": 2,
                    "startup_service_equip_skipped_party_slot": 3,
                    "levels_per_hour": "60.000",
                    "xp_per_hour": "6000.000",
                    "text_xp_per_hour": "6000.000",
                    "xp_effective_per_hour": "6000.000",
                    "money_copper_per_hour": "720.000",
                    "inventory_items_per_hour": "120.000",
                    "target_removed_per_hour": "60.000",
                    "deaths_per_hour": "0.000",
                },
            )
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(rows[0]["xp_delta"], "100")
        self.assertEqual(rows[0]["text_xp_delta"], "100")
        self.assertEqual(rows[0]["xp_effective_delta"], "100")
        self.assertEqual(rows[0]["xp_persist_lag"], "0")
        self.assertEqual(rows[0]["xp_persist_status"], "synced")
        self.assertEqual(rows[0]["money_delta_copper"], "12")
        self.assertEqual(rows[0]["inventory_items_delta"], "2")
        self.assertEqual(rows[0]["train_verified"], "1")
        self.assertEqual(rows[0]["spec_gain"], "Slash+1")
        self.assertEqual(rows[0]["xp_per_hour"], "6000.000")
        self.assertEqual(rows[0]["growth_role"], "tracked")
        self.assertEqual(rows[0]["target_removed_no_reward"], "0")

    def test_timeline_writer_extends_header_for_new_row_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "timeline.csv"

            growth.write_timeline_row(
                path,
                {
                    "timestamp_utc": "2026-05-21T00:00:00+00:00",
                    "case": "alb-p1",
                    "runtime_extra_metric": 7,
                },
            )
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(rows[0]["runtime_extra_metric"], "7")

    def test_metrics_by_account_keeps_party_rows_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "metrics.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "username",
                        "ok",
                        "actions",
                        "elapsed_seconds",
                        "combat_engagements",
                        "target_removed",
                        "target_removed_no_reward",
                        "player_deaths",
                        "target_timeouts",
                        "movement_failures",
                        "loot_acquired",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "growthalb001",
                        "ok": "true",
                        "actions": "10",
                        "elapsed_seconds": "30",
                        "combat_engagements": "2",
                        "target_removed": "1",
                        "target_removed_no_reward": "0",
                        "player_deaths": "0",
                        "target_timeouts": "0",
                        "movement_failures": "0",
                        "loot_acquired": "1",
                    }
                )
                writer.writerow(
                    {
                        "username": "growthalb002",
                        "ok": "true",
                        "actions": "7",
                        "elapsed_seconds": "20",
                        "combat_engagements": "1",
                        "target_removed": "0",
                        "target_removed_no_reward": "2",
                        "player_deaths": "0",
                        "target_timeouts": "0",
                        "movement_failures": "2",
                        "loot_acquired": "0",
                    }
                )

            summaries = growth.metrics_by_account(path)

        self.assertEqual(summaries["growthalb001"]["actions"], 10)
        self.assertEqual(summaries["growthalb001"]["target_removed"], 1)
        self.assertEqual(summaries["growthalb002"]["actions"], 7)
        self.assertEqual(summaries["growthalb002"]["movement_failures"], 2)
        self.assertEqual(summaries["growthalb002"]["target_removed_no_reward"], 2)

    def test_encounter_text_metrics_counts_korean_and_mojibake_xp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir)
            encounter_dir = case_dir / "encounters"
            encounter_dir.mkdir()
            path = encounter_dir / "segment-001-growthmid001-1.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"event":"server_message","text":"경험치 14점을 얻었습니다. (4 캠프 보너스)"}',
                        '{"event":"server_message","text":"寃쏀뿕移?16?먯쓣 ?살뿀?듬땲?? (4 罹좏봽 蹂대꼫??"}',
                        '{"event":"server_message","text":"보너스 지역이 갱신되었습니다."}',
                        '{"event":"target_object_removed","text":"경험치 999점을 얻었습니다."}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            metrics = growth.encounter_text_metrics(case_dir, 1, "growthmid001")

        self.assertEqual(metrics["text_xp_delta"], 30)
        self.assertEqual(metrics["text_xp_messages"], 2)

    def test_case_summary_writes_per_hour_rates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            timeline = Path(temp_dir) / "timeline.csv"
            summary = Path(temp_dir) / "case-summary.csv"
            growth.write_timeline_row(
                timeline,
                {
                    "timestamp_utc": "2026-05-21T00:00:00+00:00",
                    "case": "alb-p1",
                    "realm": "alb",
                    "party_size": 1,
                    "segment": 1,
                    "account": "growthalb701",
                    "character": "GrowthAlb701",
                    "class_id": 1,
                    "specs_before": "Slash|1",
                    "specs_after": "Slash|2",
                    "spec_gain": "Slash+1",
                    "level_before": 1,
                    "level_after": 2,
                    "level_delta": 1,
                    "xp_before": 0,
                    "xp_after": 100,
                    "xp_delta": 100,
                    "text_xp_delta": 120,
                    "text_xp_messages": 2,
                    "xp_effective_delta": 120,
                    "xp_persist_lag": 20,
                    "xp_persist_status": "lagging",
                    "money_before_copper": 0,
                    "money_after_copper": 12,
                    "money_delta_copper": 12,
                    "inventory_rows_before": 1,
                    "inventory_rows_after": 2,
                    "inventory_rows_delta": 1,
                    "inventory_items_before": 1,
                    "inventory_items_after": 3,
                    "inventory_items_delta": 2,
                    "train_command_sent": 1,
                    "train_verified": 1,
                    "death_before": 0,
                    "death_after": 0,
                    "death_delta": 0,
                    "region_after": 1,
                    "x_after": 1,
                    "y_after": 2,
                    "z_after": 3,
                    "metric_rows": 1,
                    "ok_rows": 1,
                    "actions": 10,
                    "elapsed_seconds": "60.000",
                    "combat_engagements": 2,
                    "target_removed": 1,
                    "player_deaths": 0,
                    "target_timeouts": 0,
                    "movement_failures": 0,
                    "loot_acquired": 1,
                    "startup_service_dialog_settle": 1,
                    "startup_service_equip": 2,
                    "startup_service_equip_skipped_party_slot": 3,
                    "levels_per_hour": "60.000",
                    "xp_per_hour": "6000.000",
                    "text_xp_per_hour": "7200.000",
                    "xp_effective_per_hour": "7200.000",
                    "money_copper_per_hour": "720.000",
                    "inventory_items_per_hour": "120.000",
                    "target_removed_per_hour": "60.000",
                    "deaths_per_hour": "0.000",
                },
            )
            growth.write_case_summary(summary, timeline)
            with summary.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(rows[0]["case"], "alb-p1")
        self.assertEqual(rows[0]["xp_per_hour"], "6000.000")
        self.assertEqual(rows[0]["text_xp_delta"], "120")
        self.assertEqual(rows[0]["xp_persist_lag"], "20")
        self.assertEqual(rows[0]["xp_effective_per_hour"], "7200.000")
        self.assertEqual(rows[0]["money_copper_per_hour"], "720.000")
        self.assertEqual(rows[0]["train_verified"], "1")
        self.assertEqual(rows[0]["startup_service_dialog_settle"], "1")
        self.assertEqual(rows[0]["startup_service_equip"], "2")
        self.assertEqual(rows[0]["startup_service_equip_skipped_party_slot"], "3")

    def test_next_segment_index_skips_existing_segment_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir)
            (case_dir / "segment-001-metrics.csv").write_text("username\n", encoding="utf-8")
            (case_dir / "segment-003-metrics.csv").write_text("username\n", encoding="utf-8")
            (case_dir / "segment-bad-metrics.csv").write_text("username\n", encoding="utf-8")

            self.assertEqual(growth.next_segment_index(case_dir), 4)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
