import unittest
import csv
import importlib.util
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


class OperationalScriptTests(unittest.TestCase):
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
                writer = csv.DictWriter(handle, fieldnames=["xy_status", "z_status", "rewind_status"])
                writer.writeheader()
                writer.writerow({"xy_status": "warn", "z_status": "ok", "rewind_status": "warn"})

            rows = summarize_dummy_growth_run.summarize_run(root)

        self.assertEqual(rows[0]["flee_events"], 4)
        self.assertEqual(rows[0]["watcher_xy_warn"], 1)
        self.assertEqual(rows[0]["watcher_z_warn"], 0)
        self.assertEqual(rows[0]["watcher_rewind_warn"], 1)

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
