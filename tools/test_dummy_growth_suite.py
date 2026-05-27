#!/usr/bin/env python3
"""Unit checks for the dummy growth-suite runner."""

from __future__ import annotations

import csv
import importlib.util
import json
import math
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


def load_hunting_ground_analyzer():
    module_path = Path(__file__).with_name("analyze-dummy-growth-hunting-grounds.py")
    spec = importlib.util.spec_from_file_location("analyze_dummy_growth_hunting_grounds_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


growth = load_module()
hunting_analyzer = load_hunting_ground_analyzer()


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

    def test_target_levels_scale_with_party_size(self) -> None:
        self.assertEqual(growth.target_levels(1, 1), (1, 1, 0))
        self.assertEqual(growth.target_levels(1, 2), (1, 2, 1))
        self.assertEqual(growth.target_levels(1, 4), (1, 3, 2))
        self.assertEqual(growth.target_levels(1, 8), (1, 4, 3))
        self.assertEqual(growth.target_levels(3, 1), (1, 3, 0))
        self.assertEqual(growth.target_levels(3, 2), (2, 4, 1))
        self.assertEqual(growth.target_levels(3, 4), (2, 5, 2))
        self.assertEqual(growth.target_levels(3, 8), (2, 6, 3))
        self.assertEqual(growth.target_levels(5, 1), (4, 5, 1))
        self.assertEqual(growth.target_levels(6, 1), (4, 5, 1))
        self.assertEqual(growth.target_levels(7, 1), (6, 6, 0))
        self.assertEqual(growth.target_levels(8, 1), (6, 6, 1))
        self.assertEqual(growth.target_levels(20, 2), (19, 21, 2))
        self.assertEqual(growth.target_levels(20, 4), (19, 22, 3))
        self.assertEqual(growth.target_levels(49, 8), (48, 50, 5))

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

    def test_mid_early_gear_route_uses_api_visible_neutral_spider_cluster(self) -> None:
        route = growth.select_route_point(growth.REALMS["mid"], level=6, party_size=1)

        self.assertEqual(route.teleport_destination, "")
        self.assertIn("vein spider", route.prefer)
        self.assertIn("small hill cat", route.avoid)
        self.assertEqual((route.x, route.y), (783163, 751764))
        self.assertLess(math.hypot(growth.REALMS["mid"].start[0] - route.x, growth.REALMS["mid"].start[1] - route.y), 10500)

    def test_alb_mid_level_eight_routes_use_xp_eligible_level_six_clusters(self) -> None:
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
        self.assertIn("wood-eater worker", route.prefer)
        self.assertIn("hill person", route.avoid)
        self.assertIn("young grendelorm", route.avoid)
        self.assertEqual((route.x, route.y, route.z), (786637, 723034, 4722))
        self.assertLess(math.hypot(803612 - route.x, 726671 - route.y), 18000)

    def test_alb_hib_early_gear_routes_use_nearby_level_five_mobs(self) -> None:
        expected = {
            "alb": "shady pilferer",
            "hib": "eirebug",
        }
        for realm_key, preferred_name in expected.items():
            with self.subTest(realm=realm_key):
                realm = growth.REALMS[realm_key]
                route = growth.select_route_point(realm, level=6, party_size=1)
                distance = math.hypot(realm.start[0] - route.x, realm.start[1] - route.y)

                self.assertLessEqual(distance, 10000)
                self.assertIn(preferred_name, route.prefer)

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

    def test_albion_level_fifty_route_uses_db_backed_tylwyth_cluster_away_from_sages(self) -> None:
        route = growth.select_route_point(growth.REALMS["alb"], level=50, party_size=2)

        self.assertEqual(route.teleport_destination, "Snowdonia Fortress")
        self.assertIn("Tylwyth Teg ranger", route.prefer)
        self.assertIn("ellyll sage", route.avoid)
        self.assertIn("cyhraeth", route.avoid)
        self.assertLess(math.hypot(route.x - 504923, route.y - 344510), 2500)

    def test_mid_hib_level_fifty_routes_use_existing_reachable_teleports(self) -> None:
        mid = growth.select_route_point(growth.REALMS["mid"], level=50, party_size=2)
        hib = growth.select_route_point(growth.REALMS["hib"], level=50, party_size=2)

        self.assertEqual(mid.teleport_destination, "Vindsaul Faste")
        self.assertIn("fenrir tracker", mid.prefer)
        self.assertIn("fenrir snowscout", mid.objective_adds)
        self.assertLess(math.hypot(mid.x - 664136, mid.y - 726812), 2500)
        self.assertIn("wyvern", mid.avoid)
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
        self.assertIn("FLOOR(X / 20000)", captured_sql[0])
        self.assertIn("AND Realm <> 2", captured_sql[0])
        self.assertIn("GROUP BY Name, Level, grid_x, grid_y", captured_sql[0])

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
        self.assertTrue(hib.growth_class_cycle.startswith("44|47|"))
        self.assertIn("Regrowth|40", hib.growth_spec_cycle.split("||")[1])

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

    def test_early_gear_growth_can_hunt_while_walking_into_camp_radius(self) -> None:
        args = SimpleNamespace(combat_home_leash_distance=1200.0)

        self.assertEqual(growth.growth_combat_home_leash_distance(args, 6), 6200.0)

    def test_high_level_party_growth_can_chase_within_large_hunting_camp(self) -> None:
        args = SimpleNamespace(target_home_max_distance=1400.0, combat_home_leash_distance=1200.0)

        self.assertEqual(growth.growth_target_home_max_distance(args, 50), 2800.0)
        self.assertEqual(growth.growth_combat_home_leash_distance(args, 50), 2800.0)

    def test_level_ten_solo_checkpoint_targets_lower_con_for_gear_stage(self) -> None:
        self.assertEqual(growth.target_levels(10, 1), (7, 8, 1))
        self.assertEqual(growth.target_max_level(10, 8, 1), 9)

    def test_level_ten_routes_start_near_teleporter_hunting_clusters(self) -> None:
        mid = growth.select_route_point(growth.REALMS["mid"], level=10, party_size=1)
        hib = growth.select_route_point(growth.REALMS["hib"], level=10, party_size=1)
        alb = growth.select_route_point(growth.REALMS["alb"], level=10, party_size=1)

        self.assertEqual(alb.teleport_destination, "Campacorentin Station")
        self.assertIn("giant spider", alb.prefer)
        self.assertIn("tree spirit", alb.avoid)
        self.assertIn("spriggarn stalker", alb.avoid)
        self.assertEqual(mid.teleport_destination, "Fort Veldon")
        self.assertIn("small hill cat", mid.prefer)
        self.assertIn("wolf spiderling", mid.avoid)
        self.assertEqual(hib.teleport_destination, "Tir na mBeo")
        self.assertIn("water beetle", hib.prefer)
        self.assertIn("water beetle collector", hib.avoid)
        self.assertEqual((alb.x, alb.y, alb.z), (496426, 593548, 1904))
        self.assertEqual((mid.x, mid.y, mid.z), (807285, 680511, 5000))
        self.assertEqual((hib.x, hib.y, hib.z), (350899, 531716, 3637))

        teleporter = next(
            point
            for point in growth.TELEPORT_DESTINATIONS["hib"]
            if point[0] == hib.teleport_destination
        )
        self.assertLessEqual(math.hypot(hib.x - teleporter[1], hib.y - teleporter[2]), 15000.0)

    def test_level_ten_party_routes_use_party_sized_hunting_camps(self) -> None:
        alb = growth.select_route_point(growth.REALMS["alb"], level=10, party_size=2)
        mid = growth.select_route_point(growth.REALMS["mid"], level=10, party_size=4)
        hib = growth.select_route_point(growth.REALMS["hib"], level=10, party_size=8)

        self.assertEqual(alb.teleport_destination, "Campacorentin Station")
        self.assertIn("giant spider", alb.prefer)
        self.assertEqual((alb.x, alb.y, alb.z), (496426, 593548, 1904))
        self.assertEqual(mid.teleport_destination, "Gotar")
        self.assertIn("spindly rock crab", mid.prefer)
        self.assertIn("perfidious pook", mid.avoid)
        self.assertEqual((mid.x, mid.y, mid.z), (772717, 833982, 4374))
        self.assertEqual(hib.teleport_destination, "Tir na mBeo")
        self.assertEqual(hib.prefer, "lough wolf")
        self.assertIn("red wolfhound", hib.avoid)
        self.assertIn("wild lucradan", hib.avoid)
        self.assertEqual((hib.x, hib.y, hib.z), (336157, 532604, 5556))

    def test_level_ten_two_player_growth_keeps_targets_at_or_below_player_level(self) -> None:
        self.assertEqual(growth.target_levels(10, 2), (8, 9, 0))

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

        self.assertLess(math.hypot(x - 802606, y - 679069), 80.0)
        self.assertLess(math.hypot(x - 801046, y - 678588), 1700.0)
        self.assertGreater(y, 678000)
        self.assertLess(y, 679500)

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

    def test_checkpoint_levels_use_fresh_accounts_per_forced_level(self) -> None:
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
        self.assertEqual(captured_accounts, [["growthalb701"], ["growthalb702"], ["growthalb703"]])

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

    def test_level_five_train_checkpoint_does_not_require_kill(self) -> None:
        args = SimpleNamespace(require_segment_kill=True)

        self.assertFalse(growth.segment_requires_kill(args, 5))
        self.assertTrue(growth.segment_requires_kill(args, 6))

    def test_growth_segment_xp_regression_fails_when_required_xp_is_zero(self) -> None:
        self.assertFalse(growth.segment_xp_regression_passed(0, require_xp=True))
        self.assertTrue(growth.segment_xp_regression_passed(1, require_xp=True))
        self.assertTrue(growth.segment_xp_regression_passed(0, require_xp=False))

    def test_train_and_max_level_checkpoints_do_not_require_xp_progress(self) -> None:
        args = SimpleNamespace(require_segment_xp=True, max_level=50)

        self.assertFalse(growth.segment_requires_xp(args, 5))
        self.assertTrue(growth.segment_requires_xp(args, 10))
        self.assertFalse(growth.segment_requires_xp(args, 50))

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

        self.assertRegex(waypoints, r"496426,593548,\d+")
        self.assertRegex(waypoints, r"496786,593548,\d+")
        self.assertRegex(waypoints, r"496786,593908,\d+")

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

    def test_growth_path_graph_routes_nearby_mid_six_without_remote_level_five_hub(self) -> None:
        import dummy_pathing

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "growth-route-graph.json"
            growth.write_growth_path_graph(path)
            graph = dummy_pathing.PathGraph.from_file(path)

        safety = dummy_pathing.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=2500)
        route = graph.astar("mid_start", "mid_6", safety)
        node_ids = [node.id for node in route.nodes]

        self.assertTrue(route.ok)
        self.assertNotIn("mid_5", node_ids)
        self.assertLess(len(route.nodes), 50)

    def test_growth_path_graph_routes_to_level_ten_party_variants(self) -> None:
        import dummy_pathing

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "growth-route-graph.json"
            growth.write_growth_path_graph(path)
            graph = dummy_pathing.PathGraph.from_file(path)

        safety = dummy_pathing.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=2500)
        self.assertTrue(graph.astar("mid_teleport_gotar", "mid_10_772717_833982", safety).ok)
        self.assertTrue(graph.astar("hib_teleport_tir_na_mbeo", "hib_10_336157_532604", safety).ok)

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

    def test_growth_path_graph_samples_midpoint_ground_height_on_steep_routes(self) -> None:
        import dummy_pathing

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "growth-route-graph.json"
            growth.write_growth_path_graph(path)
            graph = dummy_pathing.PathGraph.from_file(path)

        node = graph.nodes["alb_teleport_snowdonia_fortress_50_8"]
        sampled_z = growth.sample_route_z(
            growth.REALMS["alb"],
            growth.build_realm_height_samplers(),
            node.x,
            node.y,
            0,
        )

        self.assertEqual(node.z, sampled_z)
        self.assertGreater(node.z, 0)

    def test_growth_path_graph_routes_through_snowdonia_steep_height_samples(self) -> None:
        import dummy_pathing

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "growth-route-graph.json"
            growth.write_growth_path_graph(path)
            graph = dummy_pathing.PathGraph.from_file(path)

        safety = dummy_pathing.PathSafety(max_direct_distance=150.0, max_edge_length=1800.0, max_height_delta=900)
        route = graph.astar("alb_teleport_snowdonia_fortress", "alb_50", safety)

        self.assertTrue(route.ok, route.reason)

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
        self.assertEqual(command[command.index("--attack-target-in-view-prime-delay") + 1], "1.1")
        self.assertIn("--melee-stick-attack", command)
        self.assertEqual(command[command.index("--melee-stick-attack-distance") + 1], "1800")
        self.assertEqual(command[command.index("--target-face-command-interval") + 1], "0.8")
        self.assertEqual(command[command.index("--melee-range-buffer") + 1], "300")
        self.assertEqual(command[command.index("--minimum-melee-stop-distance") + 1], "60")
        self.assertEqual(command[command.index("--movement-speed") + 1], "191.0")
        self.assertEqual(command[command.index("--target-loss-grace") + 1], "1")
        self.assertIn("--combat-home-leash-distance", command)
        self.assertEqual(command[command.index("--combat-home-leash-distance") + 1], "1200.0")
        self.assertIn("--allow-avoid-target-fallback", command)
        self.assertIn("--current-target-api-refresh", command)
        self.assertIn("--hunter-target-api-scout", command)
        self.assertEqual(command[command.index("--hunter-target-api-radius") + 1], "2200.0")
        self.assertEqual(command[command.index("--hunter-target-api-engage-distance") + 1], "1500.0")
        self.assertEqual(command[command.index("--hunter-target-max-ground-z-delta") + 1], "220")
        self.assertEqual(command[command.index("--hunter-min-time-left-for-new-target") + 1], "55")

        self.assertEqual(command[command.index("--max-target-level") + 1], "18")
        self.assertEqual(command[command.index("--max-target-level-delta") + 1], "3")
        self.assertIn("--reject-target-on-server-los-failure", command)
        self.assertEqual(command[command.index("--server-los-failure-target-cooldown") + 1], "4")
        self.assertEqual(command[command.index("--server-los-failure-grace") + 1], "10")
        self.assertNotIn("--npc-max-age", command)
        self.assertIn("--live-control-file", command)
        self.assertEqual(command[command.index("--live-control-file") + 1], str(Path("case") / "live-control.json"))
        self.assertIn("--live-control-interval", command)
        self.assertEqual(command[command.index("--live-control-interval") + 1], "1.0")
        self.assertIn("--flee-use-sprint", command)
        self.assertEqual(command[command.index("--flee-health-percent") + 1], "55")
        self.assertEqual(command[command.index("--flee-pressure-health-percent") + 1], "85")
        self.assertEqual(command[command.index("--flee-step") + 1], "900")
        self.assertEqual(command[command.index("--flee-movement-speed") + 1], "360")
        self.assertIn("--flee-home", command)
        self.assertEqual(command[command.index("--flee-home") + 1], "345698,528897,5448")
        self.assertEqual(command[command.index("--flee-home-stop-distance") + 1], "120")
        self.assertIn("--flee-dynamic-safe-point", command)
        self.assertEqual(command[command.index("--flee-safe-threat-radius") + 1], "6000")
        self.assertEqual(command[command.index("--flee-safe-point-distance") + 1], "5200")
        self.assertEqual(command[command.index("--flee-critical-health-percent") + 1], "45")
        self.assertEqual(command[command.index("--flee-critical-safe-point-distance") + 1], "9000")
        self.assertIn("--flee-safe-api-scout", command)
        self.assertEqual(command[command.index("--flee-safe-replan-damage-grace") + 1], "6")
        self.assertEqual(command[command.index("--flee-town-health-percent") + 1], "99")
        self.assertEqual(command[command.index("--flee-min-combat-seconds") + 1], "4")
        self.assertEqual(command[command.index("--flee-melee-counterattack-min-attacks") + 1], "3")
        self.assertEqual(command[command.index("--flee-melee-counterattack-health-floor") + 1], "55")
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
        self.assertEqual(command[command.index("--party-min-ready") + 1], "4")
        self.assertIn("--party-require-leader-engaged", command)
        self.assertIn("--party-mark-pull-engaged", command)
        self.assertEqual(command[command.index("--party-pull-engage-distance") + 1], "1800")
        self.assertIn("--party-block-solo-required-retaliation", command)
        self.assertEqual(command[command.index("--party-pre-pull-home-stop-distance") + 1], "1800")
        self.assertIn("--party-rescue-aggro", command)
        self.assertIn("--party-rescue-before-objective-engaged", command)
        self.assertIn("--party-clear-objective-adds-before-engage", command)
        self.assertIn("--party-local-rescue-target", command)
        self.assertEqual(command[command.index("--party-local-rescue-max-distance") + 1], "900")
        self.assertEqual(command[command.index("--party-healer-local-rescue-health-percent") + 1], "35")
        self.assertEqual(command[command.index("--party-rescue-objective-max-distance") + 1], "1800")
        self.assertEqual(command[command.index("--party-rescue-assist-after") + 1], "6")
        self.assertEqual(command[command.index("--party-rescue-emergency-assist-after") + 1], "2")
        self.assertNotIn("--start-x", command)
        self.assertNotIn("--start-y", command)

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
        self.assertEqual(payload["baseline_max_target_level"], 9)
        self.assertIn("--startup-teleporter-home", command)
        self.assertEqual(command[command.index("--startup-teleporter-home") + 1], growth.startup_teleporter_home(growth.REALMS["alb"]))
        self.assertIn("--startup-teleport-destination", command)
        self.assertEqual(command[command.index("--startup-teleport-destination") + 1], "Campacorentin Station")
        self.assertIn("--require-target-name", command)
        self.assertIn("giant spider", command[command.index("--require-target-name") + 1])
        self.assertIn("--avoid-target-name", command)
        self.assertIn("tree spirit", command[command.index("--avoid-target-name") + 1])
        self.assertIn("spriggarn stalker", command[command.index("--avoid-target-name") + 1])
        self.assertIn("--allow-preferred-low-con-fallback", command)
        self.assertEqual(command[command.index("--preferred-low-con-min-level") + 1], "7")
        self.assertEqual(command[command.index("--flee-home") + 1], "493679,591770,1819")
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
        self.assertEqual(command[command.index("--required-target-tank-commit-health-percent") + 1], "70")
        self.assertEqual(command[command.index("--max-target-distance") + 1], "1500.0")
        self.assertEqual(command[command.index("--target-home-max-distance") + 1], "1800.0")
        self.assertEqual(command[command.index("--combat-home-leash-distance") + 1], "1800.0")
        self.assertEqual(command[command.index("--required-target-home-hunt-distance") + 1], "1800.0")

    def test_early_growth_direct_combat_move_uses_safe_level_six_minimum_scan_radius(self):
        args = SimpleNamespace(
            target_home_max_distance=1400.0,
            max_target_distance=2200.0,
            combat_home_leash_distance=1200.0,
        )

        self.assertEqual(growth.growth_max_target_distance(args, 6), 2800.0)
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
        self.assertNotIn("--require-target-name", command)
        self.assertIn("--prefer-target-name", command)
        self.assertEqual(command[command.index("--prefer-target-name") + 1], "black wolf pup")
        self.assertIn("--target-auto-lowest-visible-level", command)
        self.assertIn("--avoid-target-name", command)
        self.assertIn("young cutpurse", command[command.index("--avoid-target-name") + 1])
        self.assertIn("--server-correction-smoothing", command)
        self.assertNotIn("--party-assist-only", command)
        self.assertEqual(command[command.index("--target-home-max-distance") + 1], "6200.0")
        self.assertEqual(command[command.index("--combat-home-leash-distance") + 1], "6200.0")
        self.assertEqual(command[command.index("--combat-chase-max-distance") + 1], "2200.0")
        self.assertEqual(command[command.index("--max-target-distance") + 1], "1500.0")
        self.assertEqual(command[command.index("--flee-safe-point-distance") + 1], "2400")
        self.assertEqual(command[command.index("--flee-critical-safe-point-distance") + 1], "4200")
        self.assertIn("--allow-avoid-target-fallback", command)
        self.assertIn("--current-target-api-refresh", command)
        self.assertIn("--hunter-target-api-scout", command)

    def test_level_six_solo_growth_command_uses_green_to_blue_targets(self) -> None:
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

        self.assertEqual(command[command.index("--ideal-target-level") + 1], "5")
        self.assertEqual(command[command.index("--min-target-level") + 1], "4")
        self.assertEqual(command[command.index("--max-target-level") + 1], "6")
        self.assertEqual(command[command.index("--max-target-level-delta") + 1], "1")
        self.assertEqual(command[command.index("--max-target-distance") + 1], "2800.0")
        self.assertEqual(command[command.index("--combat-direct-move-distance") + 1], "2800.0")
        self.assertEqual(command[command.index("--hunter-target-api-radius") + 1], "2800.0")
        self.assertEqual(command[command.index("--hunter-target-api-engage-distance") + 1], "2800.0")
        self.assertEqual(command[command.index("--target-home-max-distance") + 1], "6200.0")
        self.assertIn("--allow-preferred-low-con-fallback", command)
        self.assertEqual(command[command.index("--preferred-low-con-min-level") + 1], "4")

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
        self.assertIn("--party-require-leader-engaged", command)
        self.assertIn("--party-mark-pull-engaged", command)
        self.assertEqual(command[command.index("--party-pull-engage-distance") + 1], "1800")
        self.assertIn("--party-block-solo-required-retaliation", command)
        self.assertEqual(command[command.index("--party-pre-pull-home-stop-distance") + 1], "1800")
        self.assertIn("--party-rescue-aggro", command)
        self.assertIn("--party-rescue-before-objective-engaged", command)
        self.assertIn("--party-clear-objective-adds-before-engage", command)
        self.assertIn("--party-local-rescue-target", command)
        self.assertEqual(command[command.index("--party-local-rescue-max-distance") + 1], "900")
        self.assertEqual(command[command.index("--party-healer-local-rescue-health-percent") + 1], "35")
        self.assertEqual(command[command.index("--party-rescue-objective-max-distance") + 1], "1800")
        self.assertEqual(command[command.index("--party-rescue-assist-after") + 1], "6")
        self.assertEqual(command[command.index("--party-rescue-emergency-assist-after") + 1], "2")
        self.assertEqual(command[command.index("--party-slot-rotations") + 1], "melee-basic,melee-burst")
        self.assertIn("--allow-unvalidated-skills", command)

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
        self.assertEqual(command[command.index("--party-assist-interval") + 1], "3")
        self.assertEqual(command[command.index("--party-form-up-delay") + 1], "4")
        self.assertEqual(command[command.index("--party-rescue-assist-after") + 1], "6")

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
        self.assertEqual(command[command.index("--ideal-target-level") + 1], "5")
        self.assertEqual(command[command.index("--min-target-level") + 1], "4")
        self.assertEqual(command[command.index("--max-target-level") + 1], "6")
        self.assertEqual(command[command.index("--max-target-level-delta") + 1], "1")
        self.assertIn("--greet-nearby-player", command)
        self.assertIn("--speak-state-changes", command)
        self.assertEqual(command[command.index("--state-speech-min-interval") + 1], "3.0")

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

        self.assertIn("--startup-auto-train", command)
        self.assertIn("--startup-train-level", command)
        self.assertEqual(command[command.index("--startup-train-level") + 1], "6")
        self.assertNotIn("--startup-train-full-specs", command)

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
        self.assertEqual(command[command.index("--startup-teleport-destination") + 1], "Campacorentin Station")
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
