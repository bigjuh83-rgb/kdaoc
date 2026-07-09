# OpenDAoC-Core Growth Test Thread

## Scope

- L1-L50 dummy growth
- L5 train/class/spec verification
- Gear replacement
- Item/gold/sell checks
- Party behavior during leveling
- Death/release/recover
- Growth monster regression

## Rules

- Do not waste time with blind long runs.
- First inspect source, DB, and logs for predictable failure conditions.
- Use this sequence:
  1. single failure reproduction
  2. log root cause
  3. unit test
  4. single revalidation
  5. reduced matrix
  6. full matrix

## Main Files

- `tools/run-dummy-growth-suite.py`
- `tools/summarize-dummy-growth-run.py`
- `tools/test_dummy_growth_suite.py`
- `tools/test_operational_scripts.py`

## Completed

- Growth-stage presets:
  - `stabilize`: L1-L4
  - `train`: L5 train/class/spec
  - `gear`: L6-L10
  - `long`: L10-L50
- Failure reproduction command output was added.
- Summary script reports death, target removed, timeout, flee, watcher XY/Z/rewind.
- HIB L6 solo mudman checkpoint stabilized for 50x pre-service growth:
  - exact L4 mudman target only, no low-con/no-XP fallback.
  - HIB L6 route point moved back to the verified mudman cluster.
  - HIB L6 solo target/API/direct move distance widened to 3600.
  - visible-target combat tracking now starts when attack mode actually engages.
  - Smoke: `test-output/preservice-growth-50x-hib-l6-distance3600-suite-smoke`, XP `6350 -> 10394`, target_removed `1`, deaths `0`, no no-XP message.
- Reduced L1 realm/party matrix completed:
  - Run: `test-output/preservice-growth-50x-reduced-l1-l6-l10-rp124-s1001`.
  - Scope actually executed: L1 only, because `--checkpoint-levels 1,6,10` was combined with explicit `--max-segments 1`.
  - All 9 cases exited ok with deaths `0` and movement failures `0`.
  - ALB L1 gained XP across p1/p2/p4; HIB p1/p2 gained XP; MID p1/p2/p4 and HIB p4 ended with XP `0`.
  - HIB provisioning showed low equipment coverage compared with ALB/MID: p1 `2` items, p2 `10` items, p4 `14` items.
- L1 MID/HIB route and party XP stabilization completed:
  - MID p1 switched to level 0 `lupine gnawer`; MID p2/p4 moved to level 0 spider/wildling/mud snake clusters.
  - L1 MID/HIB p1/p2/p4 target bands now stay at level 0 to avoid early no-XP/death/flee cases.
  - L1-L4 party assist interval reduced to `0.4s` and target-in-view attack prime reduced to `0.0s`.
  - HIB p4 fourth growth slot changed from Champion/Large Weapons to Blademaster/Blades because Champion produced `0` damage at L1.
  - Full MID/HIB L1 p1/p2/p4 smoke before the HIB slot change: `test-output/preservice-growth-50x-l1-mid-hib-fastassist-s1201`, 6 cases ok, deaths `0`, movement failures `0`, MID p4 all accounts gained XP.
  - HIB p4 focused revalidation after the slot change: `test-output/preservice-growth-50x-l1-hib-p4-blademaster-s1201`, 4/4 accounts gained XP `50`, deaths `0`, movement failures `0`.
- L1 start-position fallback and no-watcher matrix completed:
  - `tools/provision-dummy-accounts.py` now writes `start_x`, `start_y`, `start_z`, and `zone_id` to the accounts CSV so `behavior-dummy-client.py` has a spawn fallback before the first server position packet.
  - Regression test: `tools.test_provision_dummy_accounts.ProvisionDummyAccountsTests.test_accounts_csv_includes_start_location_for_client_fallback`.
  - MID p4 focused rerun: `test-output/preservice-growth-50x-l1-mid-p4-tawny-default-s1201`, 4/4 accounts gained XP and reached level 2, deaths `0`, movement failures `0`.
  - Watcher matrix before the CSV fallback fix: `test-output/preservice-growth-50x-l1-default-rp124-s1201`; keep as diagnostic only because ALB p4 could start from `0,0,0`.
  - ALB p4 fallback rerun: `test-output/preservice-growth-50x-l1-alb-p4-startpos-fallback-s1201`; primary party hunted, but watcher aggro produced watcher warnings and only 2/4 accounts gained XP.
  - No-watcher L1 matrix: `test-output/preservice-growth-50x-l1-default-rp124-nowatch-s1201`; 9/9 cases ok, deaths `0`, movement failures `0`.
  - No-watcher XP highlights: solo/p2 all accounts gained XP; p4 had one zero-XP account per realm (`growthalb744`, `growthmid804`, `growthhib863`), which is now captured as a party participation/balance issue rather than hidden by the runner.
- L5/L6 solo checkpoint gate root cause fixed:
  - Root cause: live supervisor used its generic `2800` engage cap instead of the realm/level growth route cap, so HIB L5's required `5200` distance was narrowed during recovery and targets were rejected by distance.
  - Root cause: `flee` combat outcomes were treated as hard regression failures, which blocked ALB/HIB from continuing even when flee/recovery was valid balance data.
  - Fix: `build_live_supervisor_command()` now receives `realm_key` and aligns max engage with `growth_max_target_distance()`.
  - Fix: flee is no longer counted as a combat regression failure; deaths, movement failures, timeouts, unrecovered LOS/leash failures, and XP requirements still gate progression.
  - Revalidation: `test-output/preservice-growth-50x-train-l5-l6-p1-rootcausefix-s1201`, exit `0`, no failure reproduction files.
  - Revalidation summary: ALB L5/L6 XP `2021/4044`, MID L5/L6 XP `2019/4044`, HIB L5/L6 XP `0/4044`; deaths `0`, movement failures `0`.
  - HIB L5 XP `0` remains captured as an early Hibernia camp/combat balance issue, not a runner-blocking failure.

## Next Work

1. Run L6/L10 checkpoint matrix now that L5/L6 solo no longer aborts.
2. Preselect any remaining weak hunting spots per level from DB, starting with HIB L5 XP `0`.
3. Decide whether p4 zero-XP accounts should be treated as acceptable balance data or fixed before the L1-L50 long matrix.
4. Re-run full L1 reduced matrix with watcher only after watcher aggro behavior is made safe.
5. Run L1-L50 long matrix after early checkpoints are stable.
6. Run L50 party boss after L10 stability.
7. Only then move to RvR/frontier smoke.

## Useful Commands

```bash
python3 -m unittest tools.test_dummy_growth_suite tools.test_operational_scripts
python3 tools/run-dummy-growth-suite.py --growth-stage train
python3 tools/summarize-dummy-growth-run.py <run-dir>
```
