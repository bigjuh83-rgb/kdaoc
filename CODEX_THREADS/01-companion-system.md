# OpenDAoC-Core Companion System Thread

## Scope

- Companion recruiter NPC
- Live companion service
- Companion commands
- Companion dialogue
- Role behavior for healer/tank/DPS/support
- Real player + companion party behavior
- LiteLLM dialogue integration

## Current Policy

- Player-facing term: `용병`.
- Internal code/test term: `dummy`.
- No player slash command for summoning companions.
- `/dummy` remains GM-only for testing.
- Companions should help fill party gaps, not replace real players.
- Real player joining should safely release lower-priority companions when needed.

## Main Files

- `tools/dummy-companion-service.py`
- `tools/behavior-dummy-client.py`
- `tools/run-live-companion-party-smoke.py`
- `tools/run-live-companion-player-driver-smoke.py`
- `tools/companion-dialogue-pools.json`
- `tools/test_dummy_companion_service.py`
- `tools/test_behavior_player_follow.py`
- `GameServer/API/DummyCompanion/*`
- `GameServer/commands/gmcommands/dummy.cs`

## Completed

- GM `/dummy` command path exists.
- Companion request API/service exists.
- Companion service startup waits/retries until the server API is ready.
- Player command smoke exists.
- `player-command-modes` smoke passed.
- `player-command-all-roles` smoke passed.
- Companion dialogue catalog has:
  - global repeated situations: 14 categories, 32 lines each
  - 8 personalities
  - personality chat: 18 categories, at least 12 lines each
  - personality state speech: 7 categories, at least 10 lines each
- RX7600 vLLM local AI experiment is closed as a failed path. Qwen2.5 3B worked but had weak concurrency and occasional Hanja; Gemma 4 E4B failed via GGUF invalid output and AWQ VRAM OOM. See `docs/companion-local-ai-vllm-rx7600-failure.md`.
- RX7600 llama.cpp local AI path is active. Gemma 4 E4B Q4_K_M runs via `llama-server` on `http://192.168.0.28:8001` as `local-gemma-4-e4b-it`; 4 slots and 8 queued client requests passed short Korean smoke tests. See `docs/companion-local-ai-llamacpp-rx7600.md`.
- AI Gateway supports `hybrid` provider routing. Recommended paid/free operating config is `tools/opendaoc-ai-gateway.hybrid-openai-local.json`: OpenAI small model first, local llama.cpp fallback second, Gemini emergency fallback third. Local `openai_compatible/` aliases are unmetered in the ledger so they do not block the OpenAI Tier 3 data-sharing 10M tokens/day small-model budget.
- One mercenary in a mostly real-player party keeps short guide/persona memory per speaker, not globally. While one AI answer is pending, new explicit questions get a personality-specific “one at a time” busy line instead of starting another provider call; combat commands such as `ㄱㄱ` still bypass the busy reply.

## Next Work

1. Check recruiter NPC UX in game.
2. Verify real player join release policy.
3. Keep role matrix short and diagnostic.
4. Wire live companion service to `tools/opendaoc-ai-gateway.hybrid-openai-local.json` after confirming which live service launcher should own `OPENDAOC_AI_GATEWAY_CONFIG`.

## Useful Commands

```bash
python3 -m unittest tools.test_dummy_companion_service tools.test_behavior_player_follow.AccountCsvTests
python3 tools/run-live-companion-party-smoke.py --smoke-profile player-command-modes --run-dir test-output/live-companion-selftest/player-command-modes --replace --skip-gear
python3 tools/run-live-companion-party-smoke.py --smoke-profile player-command-all-roles --run-dir test-output/live-companion-selftest/player-command-all-roles --replace --skip-gear
```
