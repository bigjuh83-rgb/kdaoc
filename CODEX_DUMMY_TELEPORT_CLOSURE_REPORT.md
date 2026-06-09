# Dummy 48896 Teleport Closure Report

Updated: 2026-05-29  
Branch: `bugfix/runtime-stability`  
Status: **CLOSED (dummy-client fix verified)**

## Summary

Party-hunt dummy teleport caused by **packet-scaled speed (48896) leaking into local travel math** is fixed and verified. A follow-up fix also corrected the animation-breaking assumption that the modern 1.124+ C2S speed field should be 256x encoded. Post-fix audit shows **max horizontalDelta ~190 world units** (run speed 191), with C2S speed now sent as **191 world units/sec**. No non-heading server S2C position corrections observed.

## Root Cause

- `48896 = 191 × 256` — legacy/packed speed scale accidentally applied to modern float speed paths
- Dummy `move_towards_position()` used a single `movement_speed` for both travel limit and packet send
- Several call sites passed speeds without `packet_speed` split; leaked packet-scale values produced ~48896 world-unit jumps
- Server 1.124+ handlers read C2S speed as `float` and assign it to `CurrentSpeed`; sending 48896 there breaks observer animation instead of producing a normal run.

## Fix (dummy-client only, no server changes)

| File | Change |
|------|--------|
| `tools/headless-daoc-client.py` | `resolve_movement_speeds()` guard; `packet_speed` param retained; both travel and modern send speed are normalized to world speed |
| `tools/behavior-dummy-client.py` | `dummy_coerce_world_movement_speed()`; all `move_towards_position` / `wander` call sites use `dummy_movement_kwargs()` and send world speed |
| `tools/test_dummy_movement_speed_decouple.py` | 6 focused unit tests |

## Tests Run

```
python3 -m py_compile tools/headless-daoc-client.py tools/behavior-dummy-client.py tools/test_dummy_movement_speed_decouple.py
python3 tools/test_dummy_movement_speed_decouple.py -v   → 6/6 OK
```

Follow-up verification after animation-speed correction:

```
python3 -m py_compile tools/headless-daoc-client.py tools/behavior-dummy-client.py tools/test_dummy_movement_speed_decouple.py
python3 tools/test_dummy_movement_speed_decouple.py -v   → 6/6 OK
python3 tools/run-multi-dummy-movement-session.py --party-hunt --count 4 --hold 55 --audit --ramp-up 2 --movement-speed 191 --move-update-interval 0
```

## Reproduction (post-fix)

```bash
python3 tools/run-multi-dummy-movement-session.py --party-hunt --count 4 --hold 90 --audit --ramp-up 5
```

Launch flags: `--movement-speed 191`, `--movement-update-interval 0`, `--visible-movement`, `--smooth-movement`

## Audit Comparison — 가온 (`parthunt001`)

| Metric | Before fix | After fix |
|--------|------------|-----------|
| Max `horizontalDelta` | **48896.19** (×2) | **192.00** |
| Jumps > 500 | 2 | **0** |
| Jumps > 200 | 2 | **0** |
| Typical moving delta | ~220 (post-jump) | ~9–192 |
| C2S `speed` when moving | 48896 | 191 (modern float world speed) |
| S2C correction (non-heading) | 0 | 0 |

Evidence files:
- Before: `Debug/logs/movement-audit-가온.before-fix.jsonl`
- After: `Debug/logs/movement-audit-가온.jsonl`

Latest filtered post-fix window (`timestampUtc >= 2026-05-29T15:10:00`):

- `c2s_position`: 113
- moving speeds: `[191.0]`
- max `horizontalDelta`: `190.38`
- `horizontalDelta > 200`: 0
- near `48896`: 0
- non-heading `s2c_self_position_or_jump`: 0

## Residual ~192 deltas

Expected: `movement_speed=191` with elapsed-time cap (`movement_speed × 1.0s`) allows up to ~191–192 world units per C2S packet. This is normal run-speed stepping, not packet-scale teleport.

## Acceptance

- [x] `48896` horizontal movement jump eliminated
- [x] World speed / packet speed separated at call sites
- [x] Modern C2S speed now sent as world speed (`191`), not packed speed (`48896`)
- [x] Focused unit tests pass
- [x] Party-hunt audit re-run successful
- [x] No server movement handler changes

## Next Gate (separate task)

Real-client movement rewind reproduction with `/movementaudit on <character> full` — not blocked by this dummy fix.
