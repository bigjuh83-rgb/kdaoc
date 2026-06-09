# Cursor Status: Dummy Heading Investigation → Antigravity Handoff

Updated: 2026-05-29  
Branch: `bugfix/runtime-stability`

## User Report

- Dummies snap heading instantly on direction change (no turn motion).
- Real player following a dummy (솔온) sees intermittent **reverse/opposite facing** during movement — follow camera feels dizzy.

## Cursor Actions Taken

1. Reviewed `tools/test-output/observation-dummies/solohunt-session.log` (솔온 / `solohunt001`, 607s, ok).
2. Traced code paths in `headless-daoc-client.py` and `behavior-dummy-client.py`.
3. Identified dual-packet heading conflict (0xBA face-target vs 0xA9 travel heading).
4. Wrote Antigravity handoff: `CODEX_DUMMY_HEADING_ANTIGRAVITY_HANDOFF.md`.
5. **Implemented** approved heading policy — see `CODEX_DUMMY_HEADING_FIX_DIRECTIVE.md`.

## Implemented (2026-05-29)

- `behavior-dummy-client.py`: suppress combat `send_heading` while moving / outside melee; dual-packet guard via policy
- `headless-daoc-client.py`: gradual turn-in-place for >90° changes; `send_heading` conflict skip within 50ms of conflicting position packet
- `tools/test_dummy_heading_policy.py`: 8 tests
- All movement/heading unit tests: **25/25 PASS**

## Findings (short)

| ID | Cause | Location |
|----|-------|----------|
| A | Instant heading snap, no turn steps | `move_towards_position` |
| B | Travel vs combat facing sent on different packets same tick | `face_target_for_attack` + combat chase loop |
| C | S2C correction overwrites heading | `observe_position_and_object_id` |

Not related to closed 48896 teleport bug or GM stealth priv issue.

## Parallel Work Completed (speed state)

Per `CURSOR_MOVEMENT_SPEED_STATE_HANDOFF.md` — **done**, tests green (17/17).

## Cursor State

**Heading fix IMPLEMENTED** per `CODEX_DUMMY_HEADING_FIX_DIRECTIVE.md` (Antigravity approved).

## Files For Antigravity

- `CODEX_DUMMY_HEADING_ANTIGRAVITY_HANDOFF.md` ← start here
- `tools/test-output/observation-dummies/solohunt-session.log`
- `tools/headless-daoc-client.py` (`move_towards_position`, `send_heading`)
- `tools/behavior-dummy-client.py` (`face_target_for_attack`, combat chase ~22209–22358)

## Stop / Cleanup

Observation dummies may still be running from last session. Stop with:

```bash
python3 tools/cleanup-movement-dummies.py
```
