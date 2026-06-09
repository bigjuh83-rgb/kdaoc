# OpenDAoC-Core RvR And Frontier Thread

## Scope

- Three-realm RvR smoke
- Frontier movement/combat
- Siege/castle behavior
- Enemy realm target selection
- Same-realm and party-member target safety
- Companion RP/kill-credit restrictions

## Rules

- Companions must never target party members or same-realm allies as hostile.
- RvR contribution must be limited and tracked separately.
- Do not mix PvE reward policy with RvR reward policy.

## Main Files

- `tools/behavior-dummy-client.py`
- `tools/run-live-companion-role-matrix.py`
- RvR smoke files to be added

## Known Goals

- Test Albion/Midgard/Hibernia smoke.
- Verify party/same-realm safety.
- Verify companions only engage valid enemy realm targets.
- Define reward marker policy for companion participation.

## Next Work

1. Add three-realm smoke scaffold.
2. Add same-realm target rejection tests.
3. Add frontier position/teleport safety checks.
4. Define RP/kill-credit policy.

## Progress

- `tools/run-dummy-rvr-smoke.py` is the three-realm RvR scaffold. Default realms are Albion, Midgard, and Hibernia, staged in New Frontiers region 163 around shared observation-range meet points.
- Dry-run RvR scaffold checks now work without pre-existing account CSVs when `--dry-run --skip-provision` is used, so command generation can be verified before provisioning.
- Same-realm and party-member hostile target safety is covered in `tools/test_behavior_player_follow.py` through `choose_rvr_enemy_player` and `target_id_is_party_member` tests.
- Frontier patrol safety is covered in `tools/test_operational_scripts.py`: realm meet points stay within observation range and generated patrol waypoints stay within the intended frontier patrol envelope.

## RP/Kill-Credit Policy

- Active live companions do not receive normal PvE/RvR rewards while serving a request.
- Suppressed realm points are tracked separately as `realm_points` in `SuppressedRealmPoints`.
- Suppressed RvR kill credit is tracked separately as `rvr_kill_credit` in `SuppressedKillCredits`.
- PvE reward suppression markers (`bounty_points`, `money`) remain separate from RvR reward and kill-credit markers.
