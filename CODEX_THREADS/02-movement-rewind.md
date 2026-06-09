# OpenDAoC-Core Movement And Rewind Thread

## Scope

- Rewind symptoms
- Floating/Z mismatch
- Visible teleport-like movement
- Follow/catchup/teleport policy
- Movement audit logs
- Client movement packet speed/smoothing

## Rules

- Confirm with logs before changing movement behavior.
- Do not casually tune server movement rules.
- Use server movement audit + dummy client movement JSONL together.
- Noncombat far catchup may use speed boost and teleport.
- Combat catchup speed and teleport are forbidden.
- Teleport threshold should be about 2500+, not 4500+.
- During normal travel, companions should stay close to the leader.

## Main Files

- `tools/headless-daoc-client.py`
- `tools/behavior-dummy-client.py`
- `tools/run-multi-dummy-movement-session.py`
- `tools/test_headless_player_observation.py`
- `tools/test_dummy_movement_speed_decouple.py`
- `tools/test_dummy_movement_speed_state.py`
- `GameServer/packets/Client/168/PlayerPositionUpdateHandler.cs`
- `GameServer/packets/Client/168/PlayerHeadingUpdateHandler.cs`
- `GameServer/packets/Server/PacketLib168.cs`

## Known Findings

- Large 48896 movement jumps matched packet/world speed confusion.
- 48896 = 191 world run speed * 256 legacy packet scale.
- Some visible rewind/floating/Z mismatch symptoms remain.
- User observed that short runs show movement animation, but it may still not be true client-like movement.

## Next Work

1. Create movement-command smoke separate from combat smoke.
2. Validate `따라와`, `대기`, `여기로`, `소환`.
3. Fail on:
   - near follow teleport
   - stay mode following
   - combat teleport/catchup
   - large repeated rewind
   - excessive Z mismatch
4. Add movement audit/client JSONL summary.

## Useful Commands

```bash
python3 -m unittest tools.test_headless_player_observation tools.test_dummy_movement_speed_decouple tools.test_dummy_movement_speed_state
python3 tools/run-multi-dummy-movement-session.py --party-hunt --audit
```
