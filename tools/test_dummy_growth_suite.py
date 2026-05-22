#!/usr/bin/env python3
"""Unit checks for the dummy growth-suite runner."""

from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


def load_module():
    module_path = Path(__file__).with_name("run-dummy-growth-suite.py")
    spec = importlib.util.spec_from_file_location("run_dummy_growth_suite_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


growth = load_module()


class DummyGrowthSuiteTests(unittest.TestCase):
    def test_money_to_copper_uses_daoc_coin_scale(self) -> None:
        row = {"Copper": "7", "Silver": "6", "Gold": "5", "Platinum": "4"}

        self.assertEqual(growth.money_to_copper(row), 40_050_607)

    def test_target_levels_scale_with_party_size(self) -> None:
        self.assertEqual(growth.target_levels(1, 1), (1, 1, 0))
        self.assertEqual(growth.target_levels(1, 2), (1, 2, 1))
        self.assertEqual(growth.target_levels(1, 4), (1, 3, 2))
        self.assertEqual(growth.target_levels(1, 8), (1, 4, 3))
        self.assertEqual(growth.target_levels(3, 1), (1, 3, 0))
        self.assertEqual(growth.target_levels(3, 2), (2, 4, 1))
        self.assertEqual(growth.target_levels(3, 4), (2, 5, 2))
        self.assertEqual(growth.target_levels(3, 8), (2, 6, 3))
        self.assertEqual(growth.target_levels(5, 1), (3, 5, 0))
        self.assertEqual(growth.target_levels(20, 2), (19, 21, 2))
        self.assertEqual(growth.target_levels(20, 4), (19, 22, 3))
        self.assertEqual(growth.target_levels(49, 8), (48, 50, 5))

    def test_sub_five_growth_stays_on_starter_route_variant(self) -> None:
        route = growth.select_route_point(growth.REALMS["mid"], level=4, party_size=1)
        self.assertEqual((route.x, route.y, route.z), (767400, 745984, 4542))
        self.assertIn("young lynx", route.prefer)
        self.assertIn("thrall", route.avoid)

    def test_low_level_waypoints_stay_near_starter_hunt_area(self) -> None:
        offsets = growth.waypoint_offsets(3)

        self.assertNotIn((5200, 0), offsets)
        self.assertLessEqual(max(abs(x) for x, _y in offsets), 2400)
        self.assertLessEqual(max(abs(y) for _x, y in offsets), 2400)

    def test_experience_floor_matches_server_level_table(self) -> None:
        self.assertEqual(growth.experience_floor_for_level(1), 0)
        self.assertEqual(growth.experience_floor_for_level(3), 250)
        self.assertEqual(growth.experience_floor_for_level(5), 2300)

    def test_early_growth_parties_use_melee_slot_rotations(self) -> None:
        self.assertEqual(growth.early_growth_party_slot_rotations(1, 4), "melee-basic,melee-burst")
        self.assertEqual(growth.early_growth_party_slot_rotations(4, 8), "melee-basic,melee-burst")
        self.assertEqual(growth.early_growth_party_slot_rotations(5, 8), "")
        self.assertEqual(growth.early_growth_party_slot_rotations(1, 1), "")

    def test_early_growth_large_parties_start_after_core_ready(self) -> None:
        self.assertEqual(growth.party_min_ready(1, 8), 4)
        self.assertEqual(growth.party_min_ready(4, 8), 4)
        self.assertEqual(growth.party_min_ready(5, 8), 8)
        self.assertEqual(growth.party_min_ready(1, 2), 2)

    def test_growth_watcher_count_is_one_per_party(self) -> None:
        self.assertEqual(growth.watcher_count_for_party(SimpleNamespace(watch_movement=True), 1), 1)
        self.assertEqual(growth.watcher_count_for_party(SimpleNamespace(watch_movement=True), 8), 1)
        self.assertEqual(growth.watcher_count_for_party(SimpleNamespace(watch_movement=False), 8), 0)

    def test_watcher_character_name_contains_korean_marker(self) -> None:
        self.assertEqual(growth.watcher_character_name("growthalb701"), "\uac10\uc2dc\uc790Growthalb701")

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

    def test_growth_suite_rejects_windows_runtime_for_live_runs(self) -> None:
        args = growth.parse_args_for_tests(["--growth-stage", "train"])

        with self.assertRaisesRegex(SystemExit, "Run dummy growth suites from WSL bash"):
            growth.validate_growth_suite_runtime(args, platform="win32")

    def test_growth_suite_allows_windows_runtime_for_dry_run(self) -> None:
        args = growth.parse_args_for_tests(["--dry-run", "--growth-stage", "train"])

        growth.validate_growth_suite_runtime(args, platform="win32")

    def test_growth_segment_regression_fails_on_deaths_or_no_kills(self) -> None:
        self.assertFalse(
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

    def test_growth_equipment_plan_defers_weapon_auto_equip_for_manual_validation(self) -> None:
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

        self.assertEqual(plan.equip_slots, [])
        self.assertEqual(plan.sell_slots, [])
        self.assertIn("manual_weapon_check", plan.sell_reason)

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

    def test_snapshot_inventory_items_reads_unique_templates(self) -> None:
        captured = {}

        def fake_run_mysql(_args, sql):
            captured["sql"] = sql
            return (
                "AccountName\tSlotPosition\tTemplateId\tItemName\tItemLevel\tDpsAf\tSpdAbs\tObjectType\t"
                "ItemType\tQuality\tBonus\tAllowedClasses\tItemCount\tSellPrice\n"
                "growthalb701\t40\tunique_sword\tUnique Sword\t5\t36\t30\t3\t10\t99\t4\t11\t1\t25\n"
            )

        original_run_mysql = growth.run_mysql
        growth.run_mysql = fake_run_mysql
        try:
            rows = growth.snapshot_inventory_items(SimpleNamespace(), ["growthalb701"])
        finally:
            growth.run_mysql = original_run_mysql

        self.assertIn("itemunique", captured["sql"].lower())
        self.assertIn("UTemplate_Id", captured["sql"])
        self.assertEqual(rows["growthalb701"][0].template_id, "unique_sword")
        self.assertEqual(rows["growthalb701"][0].dps_af, 36)

    def test_case_plan_assigns_unique_case_indexes(self) -> None:
        cases = growth.build_case_plan(["alb", "mid"], [1, 4])

        self.assertEqual(
            [(realm.key, party_size, case_index) for realm, party_size, case_index in cases],
            [("alb", 1, 0), ("alb", 4, 1), ("mid", 1, 2), ("mid", 4, 3)],
        )

    def test_level_one_preferred_route_targets_are_not_required(self) -> None:
        route = growth.select_route_point(growth.REALMS["alb"], 1)

        self.assertEqual(growth.strict_route_target_name(route, 1), "")
        self.assertEqual(growth.strict_route_target_name(route, 2), "")

    def test_mid_level_one_route_uses_dense_parallel_target_cluster(self) -> None:
        route = growth.select_route_point(growth.REALMS["mid"], 1)

        self.assertEqual((route.x, route.y, route.z), (770900, 746700, 4620))
        self.assertEqual(
            growth.strict_route_target_name(route, 1),
            "",
        )

    def test_level_one_party_routes_disperse_parallel_cases(self) -> None:
        alb_p8 = growth.select_route_point(growth.REALMS["alb"], 1, party_size=8)
        mid_p1 = growth.select_route_point(growth.REALMS["mid"], 1, party_size=1)
        mid_p2 = growth.select_route_point(growth.REALMS["mid"], 1, party_size=2)
        mid_p4 = growth.select_route_point(growth.REALMS["mid"], 1, party_size=4)
        mid_p8 = growth.select_route_point(growth.REALMS["mid"], 1, party_size=8)

        self.assertEqual((alb_p8.x, alb_p8.y, alb_p8.z), (534650, 477500, 2200))
        self.assertEqual(growth.strict_route_target_name(alb_p8, 1), "")
        self.assertIn("young cutpurse", alb_p8.avoid)
        self.assertEqual((mid_p1.x, mid_p1.y, mid_p1.z), (770900, 746700, 4620))
        self.assertEqual((mid_p2.x, mid_p2.y, mid_p2.z), (775980, 751320, 4538))
        self.assertEqual((mid_p4.x, mid_p4.y, mid_p4.z), (775217, 751401, 4390))
        self.assertEqual(
            growth.strict_route_target_name(mid_p1, 1),
            "",
        )
        self.assertEqual(growth.strict_route_target_name(mid_p2, 1), "")
        self.assertEqual(growth.strict_route_target_name(mid_p4, 1), "")
        self.assertEqual(growth.strict_route_target_name(mid_p8, 1), "")

    def test_waypoints_use_neighboring_route_points(self) -> None:
        realm = growth.REALMS["alb"]

        waypoints = growth.waypoint_string(realm, 10)

        self.assertRegex(waypoints, r"522181,564087,\d+")
        self.assertRegex(waypoints, r"522541,564087,\d+")
        self.assertRegex(waypoints, r"522541,564447,\d+")

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
        self.assertIn('"mid_50"', payload)
        self.assertIn('"hib_50"', payload)

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
        self.assertEqual(command[command.index("--combat-direct-move-distance") + 1], "1500")
        self.assertEqual(command[command.index("--attack-target-in-view-prime-delay") + 1], "1.1")
        self.assertEqual(command[command.index("--target-face-command-interval") + 1], "0")
        self.assertEqual(command[command.index("--melee-range-buffer") + 1], "300")
        self.assertEqual(command[command.index("--minimum-melee-stop-distance") + 1], "60")
        self.assertEqual(command[command.index("--target-loss-grace") + 1], "1")
        self.assertIn("--combat-home-leash-distance", command)
        self.assertEqual(command[command.index("--combat-home-leash-distance") + 1], "1200.0")
        self.assertIn("--allow-avoid-target-fallback", command)
        self.assertIn("--current-target-api-refresh", command)
        self.assertIn("--hunter-target-api-scout", command)
        self.assertEqual(command[command.index("--hunter-target-api-radius") + 1], "2200")
        self.assertEqual(command[command.index("--hunter-target-api-engage-distance") + 1], "1500")
        self.assertIn("--reject-target-on-server-los-failure", command)
        self.assertEqual(command[command.index("--server-los-failure-target-cooldown") + 1], "4")
        self.assertEqual(command[command.index("--server-los-failure-grace") + 1], "3")
        self.assertNotIn("--npc-max-age", command)
        self.assertIn("--live-control-file", command)
        self.assertEqual(command[command.index("--live-control-file") + 1], str(Path("case") / "live-control.json"))
        self.assertIn("--live-control-interval", command)
        self.assertEqual(command[command.index("--live-control-interval") + 1], "1.0")
        self.assertIn("--flee-use-sprint", command)
        self.assertEqual(command[command.index("--flee-health-percent") + 1], "55")
        self.assertEqual(command[command.index("--flee-movement-speed") + 1], "360")
        self.assertIn("--flee-home", command)
        self.assertEqual(command[command.index("--flee-home") + 1], "344500,474500,5372")
        self.assertEqual(command[command.index("--flee-home-stop-distance") + 1], "900")
        self.assertIn("--flee-dynamic-safe-point", command)
        self.assertEqual(command[command.index("--flee-safe-threat-radius") + 1], "3200")
        self.assertEqual(command[command.index("--flee-safe-point-distance") + 1], "2200")
        self.assertIn("--flee-safe-api-scout", command)
        self.assertEqual(command[command.index("--flee-min-combat-seconds") + 1], "4")
        self.assertIn("--ground-z-map", command)
        self.assertIn(growth.REALMS["hib"].ground_z_map, command)
        self.assertIn("--waypoints", command)
        waypoints = command[command.index("--waypoints") + 1]
        self.assertRegex(waypoints, r"339898,516372,\d+")
        self.assertRegex(waypoints, r"340258,516732,\d+")
        self.assertIn("--required-target-home", command)
        self.assertRegex(command[command.index("--required-target-home") + 1], r"339898,516372,\d+")
        self.assertEqual(command[command.index("--required-target-home-stop-distance") + 1], "900")
        self.assertEqual(command[command.index("--required-target-home-hunt-distance") + 1], "6200")
        self.assertIn("--auto-loot", command)
        self.assertIn("--startup-command", command)
        self.assertEqual(command[command.index("--startup-command") + 1], "/bind")
        self.assertIn("--startup-service-npc-name", command)
        self.assertIn(growth.REALMS["hib"].startup_service_npc_name, command)
        self.assertIn("--login-retries", command)
        self.assertEqual(command[command.index("--login-retries") + 1], "5")
        self.assertIn("--party-assist-only", command)
        self.assertEqual(command[command.index("--party-min-ready") + 1], "4")
        self.assertIn("--party-rescue-aggro", command)
        self.assertNotIn("--start-x", command)
        self.assertNotIn("--start-y", command)

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
        self.assertNotIn("--require-target-name", command)
        self.assertIn("--prefer-target-name", command)
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "black wolf pup")
        self.assertIn("--avoid-target-name", command)
        self.assertIn("young cutpurse", command[command.index("--avoid-target-name") + 1])
        self.assertIn("--server-correction-smoothing", command)
        self.assertNotIn("--party-assist-only", command)
        self.assertEqual(command[command.index("--target-home-max-distance") + 1], "6200.0")
        self.assertEqual(command[command.index("--combat-home-leash-distance") + 1], "6200.0")
        self.assertEqual(command[command.index("--combat-chase-max-distance") + 1], "2200.0")
        self.assertEqual(command[command.index("--max-target-distance") + 1], "1500.0")
        self.assertIn("--allow-avoid-target-fallback", command)
        self.assertIn("--current-target-api-refresh", command)
        self.assertIn("--hunter-target-api-scout", command)

    def test_two_player_growth_party_uses_mixed_roles(self) -> None:
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
        self.assertEqual(command[command.index("--party-min-ready") + 1], "2")
        self.assertIn("--party-rescue-aggro", command)
        self.assertEqual(command[command.index("--party-slot-rotations") + 1], "melee-basic,melee-burst")
        self.assertIn("--allow-unvalidated-skills", command)

    def test_level_one_large_party_uses_melee_slot_rotations(self) -> None:
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

        self.assertEqual(command[command.index("--party-slot-rotations") + 1], "melee-basic,melee-burst")
        self.assertIn("--allow-unvalidated-skills", command)

    def test_growth_command_trains_after_level_five(self) -> None:
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
            current_level=5,
            path_graph=Path("graph.json"),
        )

        self.assertIn("--startup-auto-train", command)
        self.assertIn("--startup-train-level", command)
        self.assertIn("5", command)
        self.assertIn("--greet-nearby-player", command)
        self.assertIn("--speak-state-changes", command)
        self.assertEqual(command[command.index("--state-speech-min-interval") + 1], "3.0")

    def test_growth_command_does_not_train_before_level_five(self) -> None:
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
            current_level=4,
            path_graph=Path("graph.json"),
        )

        self.assertNotIn("--startup-auto-train", command)

    def test_reset_level_argument_sets_starting_character_level(self) -> None:
        args = growth.parse_args_for_tests(["--reset-level", "5", "--dry-run"])

        self.assertEqual(args.reset_level, 5)

    def test_post_segment_snapshot_delay_defaults_to_db_settle_wait(self) -> None:
        args = growth.parse_args_for_tests(["--dry-run"])

        self.assertGreater(args.post_segment_snapshot_delay, 0)
        self.assertEqual(args.post_segment_snapshot_timeout, 45.0)
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
        self.assertFalse(growth.train_verified(before, before, 5))
        self.assertFalse(growth.train_verified(before, after, 4))

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

        self.assertEqual(command[command.index("--class-cycle") + 1].split("|")[:4], ["1", "2", "11", "6"])
        self.assertEqual(command[command.index("--class-cycle") + 1].split("|")[7], "6")
        self.assertEqual(command[command.index("--race-cycle") + 1].split("|")[:2], ["1", "3"])
        self.assertIn("Rejuvenation|40", command[command.index("--spec-cycle") + 1])
        self.assertEqual(command[command.index("--start-x") + 1], "534900")
        self.assertEqual(command[command.index("--start-y") + 1], "477500")

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

        self.assertEqual(command[command.index("--class-cycle") + 1].split("|")[:6], ["14", "14", "14", "16", "16", "15"])
        self.assertEqual(command[command.index("--csv-class-cycle") + 1].split("|")[:6], ["1", "2", "11", "6", "10", "7"])

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
        self.assertIn("\uac10\uc2dc\uc790Growthalb701", captured["sql"])

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
        self.assertEqual(command[command.index("--follow-player-name") + 1], "Growthalb701")
        self.assertIn("--trace-observed-player-positions", command)
        self.assertIn("--move", command)
        self.assertIn("--required-target-home", command)
        self.assertEqual(command[command.index("--movement-speed") + 1], "150.0")
        self.assertEqual(command[command.index("--required-target-home-stop-distance") + 1], "900.0")
        self.assertIn("--waypoints", command)
        self.assertEqual(command[command.index("--waypoints") + 1], command[command.index("--required-target-home") + 1])
        self.assertNotIn("--waypoint-continuous-turns", command)
        self.assertNotIn("--hunter", command)
        self.assertNotIn("--combat", command)

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
                        '{"t":10.0,"event":"combat_finish","outcome":"target_removed"}',
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
                    "player_deaths": 0,
                    "target_timeouts": 0,
                    "movement_failures": 0,
                    "loot_acquired": 1,
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

    def test_next_segment_index_skips_existing_segment_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir)
            (case_dir / "segment-001-metrics.csv").write_text("username\n", encoding="utf-8")
            (case_dir / "segment-003-metrics.csv").write_text("username\n", encoding="utf-8")
            (case_dir / "segment-bad-metrics.csv").write_text("username\n", encoding="utf-8")

            self.assertEqual(growth.next_segment_index(case_dir), 4)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
