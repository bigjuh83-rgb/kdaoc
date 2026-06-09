# OpenDAoC-Core Codex Thread Map

This folder contains one-file handoffs for topic-specific Codex threads.

## How To Use

1. Open a new Codex thread.
2. Paste this sentence:

```text
OpenDAoC-Core 작업을 이어간다. 먼저 CODEX_THREADS/<file>.md를 읽고 그 범위만 진행해줘.
```

3. Replace `<file>.md` with the topic file below.

## Topic Files

- `00-control.md`: overall priority, task routing, final reports.
- `01-companion-system.md`: live companion service, recruiter NPC, commands, dialogue, real-player party behavior.
- `02-movement-rewind.md`: rewind, floating/Z mismatch, follow/catchup/teleport, movement audit.
- `03-combat-ai-fsm.md`: FSM, target gate, aggro, flee, skills, healer/tank/DPS/support combat logic.
- `04-growth-tests.md`: L1-L50 growth, train, gear, death/recover, growth monster regression.
- `05-rvr-frontier.md`: RvR, frontier, siege, realm target safety, reward policy.
- `06-korean-client-ui.md`: Korean UI fonts, `@` glyph replacement, assets XML.
- `07-operations-api.md`: WSL, startup scripts, LiteLLM, API quota/security.

## Global Rules

- Codex is the primary operator.
- Codex may use subagents for independent read-only or disjoint implementation work.
- Cursor and Antigravity are fallback workers only when Codex quota is low or the user explicitly asks.
- Start/restart the main server only with `start-main-server-visible.bat`.
- Check server readiness with `tools/check-main-server-fast.sh` or `check-main-server-fast.bat`.
- Never print or commit API keys, passwords, tokens, or secrets.
