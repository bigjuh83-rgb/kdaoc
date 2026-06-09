# Codex → Antigravity: Dummy Teleport Forensic Request

Updated: 2026-05-29  
Branch: `bugfix/runtime-stability`  
Status: **analysis delegated to Antigravity** (Cursor execution stopped at handoff)

## User Report

- Party hunt dummies (`parthunt001–004`, chars 가온/라온/이든/하람) appear to **teleport** instead of running naturally.
- Movement audit was enabled on **가온** (`/movementaudit`, GM priv 2).
- User asked Cursor to stop deep analysis and **hand forensic work to Antigravity**.

## Current Operational State

- All movement test dummies were disconnected and DB accounts removed via `tools/cleanup-movement-dummies.py` (prefixes: `movhunt`, `movdummy`, `parthunt`).
- Server-side audit log for 가온 remains on disk for review.

## Primary Evidence File

`Debug/logs/movement-audit-가온.jsonl`

Quick stats (Cursor pre-scan via `tools/analyze-movement-audit.py`):

| Metric | Value |
|--------|-------|
| Total events | 218 |
| `c2s_position` | 160 |
| Moving `c2s_position` (delta>0) | 74 |
| Large jumps (>500 world units) | **2** |
| Typical step after jumps | **~220** world units |
| Packet `speed` field when moving | **48896** (= 191 × 256) |
| `s2c` position corrections (non-heading) | **0** |

### Critical jump events (lines ~98, ~104)

1. `(525160,490319)` → `(489420,456950)` — `horizontalDelta` **48896.19**, `speed=48896`, `TARGET_IN_VIEW`
2. `(489420,456950)` → `(453680,423581)` — `horizontalDelta` **48896.19**, `speed=48896`, `TARGET_IN_VIEW`

Note: **48896 = 191 × 256** (world run speed 191, packet scale 256). Hypothesis for Antigravity: a dummy client code path may be using **packet-scale speed as travel distance** on first chase moves, or batching/waypoint geometry produces two giant C2S steps before ~220-unit steps stabilize.

After the two jumps, movement settles to ~219–221 world units per C2S packet at ~2s game-loop intervals (still looks like snap/teleport to observers, not smooth run animation cadence).

### Idle window before first jump

Lines 1–97: standing at spawn `(525160,490319)`, repeated `c2s_position` with `speed=0`, `horizontalDelta=0`.

## Session Context

Launch profile (intended):

- `tools/run-multi-dummy-movement-session.py --party-hunt --count 4 --hold 600 --audit`
- Defaults: `--visible-movement`, `--movement-update-interval 0`, `--movement-speed 191`, `--combat-direct-move-distance 180`, `--path-max-edge-length 220`
- `--smooth-movement` enabled in behavior command builder
- Path graph **disabled** when `visible_movement=True`

Account: `parthunt001` / character **가온** / objectId 23188

## Questions For Antigravity

1. Do the two **48896** jumps prove packet-speed-as-distance bug, path-graph long edge, `combat_direct_move`, or send batching?
2. Why does post-jump cadence show **~220** delta (matches `path_max_edge_length`) if path graph was disabled?
3. Is server accepting these jumps without S2C correction (0 non-heading S2C jumps in capture)?
4. Which **dummy-only** code paths in `tools/behavior-dummy-client.py` / `tools/headless-daoc-client.py` best explain the pattern?
5. Smallest **client-side** fix (no server movement tuning) to make dummies run visibly?

## Files To Read

- `Debug/logs/movement-audit-가온.jsonl`
- `tools/analyze-movement-audit.py` (Cursor helper)
- `tools/run-multi-dummy-movement-session.py` (launch flags)
- `tools/behavior-dummy-client.py` — `dummy_movement_kwargs`, `move_towards_destination`, combat chase ~L22256
- `tools/headless-daoc-client.py` — `move_towards_position` travel_limit logic
- `CODEX_MOVEMENT_FINAL_REPORT.md` (prior dummy probe baseline)
- `ANTIGRAVITY_MOVEMENT_ANALYSIS_HANDOFF.md`

## Hard Boundaries

- No companion matrix work
- No server movement tuning / handler changes
- Forensic + dummy-client fix design only
- Do not rerun live dummies unless needed for one tiny validation

## Expected Deliverable

Write review to:

`tools/test-output/antigravity-review/<timestamp>-CODEX_DUMMY_TELEPORT_FORENSIC_REQUEST-review.md`

Include: evidence summary, observed pattern, primary/secondary hypothesis, confidence, smallest next probe, recommended dummy-client fix scope.
