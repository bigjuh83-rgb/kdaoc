# OpenDAoC-Core Combat AI And FSM Thread

## Scope

- FSM ownership
- Target gate
- Travel aggro
- Drop aggro/recover
- Flee behavior
- Healer/tank/DPS/support combat behavior
- Skills/spells/CC/cure/resurrection

## Rules

- Do not hide failures by changing hunting coordinates.
- Behavior should look like a human player.
- If a problem repeats, centralize the decision in a gate/policy/test.
- Avoid full behavior-tree rewrites unless explicitly scoped.

## Main Files

- `tools/behavior-dummy-client.py`
- `tools/test_behavior_player_follow.py`

## Completed

- `DummyBehaviorState` exists.
- `TargetIntent`, `TargetSource`, `EngagementCandidate`, `EngagementContext`, and target decision skeletons exist.
- Companion command modes exist.
- Healer `ㄱㄱ` one-shot attack behavior exists and should return to support behavior afterward.
- Party-member hostile target rejection has tests.

## Known Remaining

- Class-specific skill/spell use is not exhaustive.
- Healer aggro should orbit around party/tank and request peel, not straight-line flee forever.
- CC/mez/stun needs deeper condition coverage.
- Tank peel/taunt and support speed/CC should keep being checked by smoke tests.

## Next Work

1. Build/verify class capability table.
2. Add tests for healer aggro peel request and orbit behavior.
3. Add CC/mez/stun multi-add tests.
4. Keep target gate as the only hostile commit path.

## Useful Commands

```bash
python3 -m unittest tools.test_behavior_player_follow
python3 tools/run-live-companion-party-smoke.py --smoke-profile tank-protection --replace --skip-gear
python3 tools/run-live-companion-party-smoke.py --smoke-profile support-crowd-control --replace --skip-gear
```
