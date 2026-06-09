# Codex → Antigravity: Dummy Heading / Turn-Motion Forensic Handoff

Updated: 2026-05-29  
Branch: `bugfix/runtime-stability`  
Status: **analysis delegated to Antigravity** (Cursor execution paused pending next directive)

## Executive Summary

User observed two related visual defects on observation dummies (reported on **솔온** / `solohunt001`):

1. **Direction changes snap instantly** — no visible turn animation when heading changes.
2. **Follow-camera dizziness** — while a real player uses follow on a dummy, the dummy intermittently appears to face **opposite** to travel direction, then snaps back.

Cursor traced both symptoms to **dummy-client heading packet policy**, not server movement correction, not 48896 speed leak, not GM stealth.

Cursor recommends Antigravity validate the dual-packet heading conflict hypothesis and propose a minimal fix policy before Cursor implements.

## Evidence Available

| Artifact | Path | Notes |
|----------|------|-------|
| 솔온 session verbose log | `tools/test-output/observation-dummies/solohunt-session.log` | 607s run, 4705 actions, ok=2/2 |
| Solo accounts CSV | `tools/test-output/multi-dummy-movement/solohunt-accounts.csv` | `solohunt001` → character **솔온** |
| Party/boss observation logs | `tools/test-output/observation-dummies/parthunt-session.log`, `bosshunt-session.log` | same class of BA/A9 interleave |
| Movement audit (솔온) | **none** | observation run did not use `--audit` |
| Prior speed audit | `Debug/logs/movement-audit-가온.jsonl` | 48896 issue closed; not heading-focused |

### Log pattern (솔온)

During movement, verbose drain shows **0xBA (PlayerHeading)** and **PlayerPosition (0xA9)** interleaved:

```
PlayerPosition, 0xBA, PlayerPosition, 0xBA, PlayerPosition ...
```

This matches code sending **different headings on two channels in the same tick window**.

Launch settings for observation dummies:

- `--priv-level 1` (no GM auto-stealth)
- `--target-face-command-interval 0` (no `/facegloc`)
- `--movement-update-interval 0` (position every move step)
- `--visible-movement`, `--ground-z-map`, no path-graph snap

## Cursor Root-Cause Analysis

### Cause A — Instant heading snap on path change

File: `tools/headless-daoc-client.py` → `move_towards_position`

- On each move step: `self.heading = heading_from_delta(dx, dy)` then single `send_position_update(...)`.
- No intermediate `send_heading` steps for large angle changes.
- Real clients typically emit **heading turn packets (0xBA)** before/during direction change; dummy skips turn motion.

**Symptom:** observer sees body orientation teleport to new direction.

### Cause B — Travel heading vs combat facing heading conflict (primary follow-camera issue)

File: `tools/behavior-dummy-client.py`

Combat chase loop (every smooth-move tick while closing on target):

1. `face_target_for_attack(client, target_npc)` → **`send_heading` (0xBA)** toward NPC
2. `move_towards_position(...)` → **position (0xA9)** with **travel heading** embedded
3. If in attack range: `face_target_for_attack` again + `send_position_update(speed=0, target_in_view=True)`

`face_target_for_attack` / `face_point_for_attack` always call:

```python
client.send_heading(client.heading, drain_after=False)
```

When chasing from the side or overshooting, **travel heading** and **target-facing heading** can differ by **90°–180°**.

Server broadcasts heading (0xBA UDP) and position (0xA9 UDP) separately (`PlayerHeadingUpdateHandler.BroadcastHeading`, `PlayerPositionUpdateHandler.BroadcastPosition`).

**Symptom for follow client:** dummy alternates between “running forward” and “facing backward/sideways at mob” — looks like intermittent reverse facing.

This persists even with `/facegloc` disabled because **`face_target_for_attack` still sends 0xBA**.

### Cause C — S2C self-position correction overwrites heading

File: `tools/headless-daoc-client.py` → `observe_position_and_object_id`

- On server correction packet (0x20): `self.heading = server_heading`
- If server heading lags last C2S heading (especially after separate 0xBA), next outbound packet can briefly disagree with what observers last saw.

**Symptom:** occasional extra flicker; likely secondary to Cause B.

## What This Is NOT

- Not the closed **48896 = 191×256** packet-speed travel bug (`CODEX_DUMMY_TELEPORT_CLOSURE_REPORT.md`)
- Not GM auto-stealth / PrivLevel=2 speed observation skew (fixed: default `--priv-level 1`)
- Not `/facegloc` heading jump (disabled in observation runs via `--target-face-command-interval 0`)
- Not server movement correction / rewind (no audit evidence of S2C snap for 솔온; no audit file captured)

## Cursor Completed (same sprint, separate track)

Dummy movement **speed state** handling per `CURSOR_MOVEMENT_SPEED_STATE_HANDOFF.md`:

- `max_speed_percent` cap + flee/chase clamp in `behavior-dummy-client.py`
- `--priv-level 1` default + audit GM-bump guard in `run-multi-dummy-movement-session.py`
- Tests: `test_dummy_movement_speed_state.py` + decouple/session tests **17/17 PASS**

Speed state work is done; **heading/turn policy is the new open item**.

## Questions For Antigravity

1. **Packet authority:** While moving, should observers see travel heading only, or is target-facing 0xBA ever correct before melee range?
2. **Turn motion:** What heading step rate (units/tick) best matches real 1.124+ client turn animation for ~90° and ~180° changes?
3. **Dual-packet conflict:** Confirm that alternating 0xBA (face target) + 0xA9 (move heading) explains follow-camera reverse-facing on 솔온 log pattern.
4. **Server state:** Does `Player.Heading` after 0xBA vs after 0xA9 explain S2C broadcast order observers receive?
5. **Fix policy:** Recommend minimal dummy-side policy:
   - suppress `send_heading` while moving outside melee range?
   - stepwise `rotate_heading_towards` before position send on large delta?
   - unify heading source so 0xBA and 0xA9 never disagree same tick?
6. **Verification:** Should next capture use `--trace-movement-log` per dummy + optional `/movementaudit on 솔온 full` from server side (without raising dummy PrivLevel)?

## Suggested Fix Direction (Cursor draft — needs Antigravity sign-off)

1. **Single heading source while moving:** travel heading in both local state and outbound packets; no separate `face_target` 0xBA until stopped or within melee stop distance.
2. **Gradual turn:** if `abs(heading_delta) > threshold`, emit stepped 0xBA turns over 1–N ticks before/with position update.
3. **Combat exception:** in melee range, facing heading may override travel heading, but still avoid sending conflicting 0xBA and 0xA9 in same tick.

Do **not** re-enable `/facegloc` for observation runs.

## Recommended Antigravity Deliverable

Short report answering questions 1–6 with:

- classification: dummy-client heading policy bug
- whether Cause B is sufficient to explain user follow-camera symptom
- approved fix policy (bullet list)
- optional: analyze `solohunt-session.log` BA/A9 cadence if helpful

## Recommended Next Cursor Step (after Antigravity reply)

Implement approved heading policy in:

- `tools/headless-daoc-client.py` (turn stepping, unified send)
- `tools/behavior-dummy-client.py` (suppress/move-gated `face_target_for_attack`)
- focused unit tests for heading delta / no dual-packet conflict
- re-run observation session (솔온 solo + follow visual check)

## Hard Boundaries (unchanged)

1. No companion matrix work.
2. No server movement tuning unless Antigravity proves server-side defect.
3. Preserve: C2S world float speed 191, ground-z-map, no path-graph snap in visible movement, PrivLevel=1 for visual tests.
