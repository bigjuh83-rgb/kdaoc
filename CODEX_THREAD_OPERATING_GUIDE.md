# OpenDAoC-Core Thread Operating Guide

## Core Rule

Codex is the primary operator.

Cursor and Antigravity are fallback workers only when Codex quota is low or when the user explicitly asks to hand work off. Normal work should stay in Codex, using Codex subagents for parallel investigation or bounded implementation tasks.

## Thread Layout

### 1. Control Thread

Purpose:
- Overall priority
- Task split
- Final reports
- Cross-thread decisions
- Cursor/Antigravity handoff only when needed

Use this thread for:
- "다음은?"
- "우선순위 정리해줘"
- "작업 나눠줘"
- "보고서 확인해줘"

Do not use this thread for long debug logs or long implementation transcripts.

### 2. Companion System Thread

Scope:
- Live companion service
- Companion recruiter NPC
- Companion commands
- Companion dialogue
- Real player + companion party behavior
- LiteLLM dialogue integration

Main files:
- `tools/dummy-companion-service.py`
- `tools/behavior-dummy-client.py`
- `tools/run-live-companion-party-smoke.py`
- `tools/companion-dialogue-pools.json`
- `GameServer/API/DummyCompanion/*`
- `GameServer/commands/gmcommands/dummy.cs`

### 3. Movement And Rewind Thread

Scope:
- Rewind symptoms
- Floating/Z mismatch
- Follow/catchup/teleport policy
- Movement audit logs
- Client movement packet speed and smoothing

Main files:
- `tools/headless-daoc-client.py`
- `tools/behavior-dummy-client.py`
- `tools/run-multi-dummy-movement-session.py`
- `GameServer/packets/Client/168/PlayerPositionUpdateHandler.cs`
- `GameServer/packets/Client/168/PlayerHeadingUpdateHandler.cs`
- `GameServer/packets/Server/PacketLib168.cs`

Rule:
- Confirm with logs before changing movement behavior.
- Do not tune server movement rules casually.

### 4. Combat AI And FSM Thread

Scope:
- FSM ownership
- Target gate
- Aggro handling
- Flee/recover behavior
- Healer/tank/DPS/support combat logic
- Skill, spell, CC, cure, resurrection use

Main files:
- `tools/behavior-dummy-client.py`
- `tools/test_behavior_player_follow.py`

Rule:
- No workaround hunting spots.
- Behavior must look like a player.

### 5. Growth Test Thread

Scope:
- L1-L50 dummy growth
- Train stage
- Gear/sell/gold/item checks
- Death/release/recover
- Growth monster regression

Main files:
- `tools/run-dummy-growth-suite.py`
- `tools/summarize-dummy-growth-run.py`
- `tools/test_dummy_growth_suite.py`

Rule:
- Source/DB/log prediction first, then minimal reproduction test.

### 6. RvR And Frontier Thread

Scope:
- Realm-vs-realm smoke
- Frontier behavior
- Siege/castle behavior
- Realm targeting safety
- RP/kill-credit policy

Rule:
- Companions must never target party members or same-realm allies as hostile targets.

### 7. Korean Client UI Thread

Scope:
- Korean UI font fallback
- `@` glyph replacement
- UI assets XML
- CP949/client text display checks

Main files:
- `ui/custom/assets.xml`
- `ui/atlantis/assets.xml`
- `ui/isles/assets.xml`

Rule:
- Do not touch `game.dll`, glyph warmup, or `0x488b8e` patches unless that thread explicitly changes scope.

### 8. Operations And API Thread

Scope:
- WSL stability
- Server startup scripts
- Companion service startup
- LiteLLM/OpenAI/Gemini routing
- API free quota and cost guardrails
- Secret handling

Main files:
- `start-main-server-visible.bat`
- `start-live-companion-service-visible.bat`
- `tools/start-main-visible-server.sh`
- `tools/start-live-companion-service.sh`
- `tools/opendaoc-ai-gateway.py`
- `tools/opendaoc-ai-gateway.json`

Rule:
- Never print or commit API keys, tokens, passwords, or secrets.
- Paid API use must stay under free quota or be disabled.

## Codex Subagent Policy

Use subagents inside Codex when work can be split safely.

Good subagent tasks:
- One agent reads logs and identifies root cause.
- One agent inspects source paths for a specific code path.
- One agent checks tests and existing coverage.
- One agent runs a bounded smoke or summarizes output.

Avoid subagents when:
- The next step is a direct edit in one hot file.
- Multiple agents would touch the same file.
- The work needs live server control and ordering matters.

Default pattern:
1. Codex main decides the critical path.
2. Subagents handle independent read-only or disjoint work.
3. Codex main integrates results.
4. Codex main runs final verification.
5. Codex main closes subagents.

## External Worker Policy

Cursor and Antigravity are used only when:
- Codex quota is low.
- The user explicitly asks to hand work off.
- A long-running side investigation is useful while Codex is unavailable.

When handing off:
1. Create a short one-line instruction file if needed.
2. Create a detailed handoff markdown only for non-trivial tasks.
3. Tell external workers to report back with changed files, tests run, and unresolved risks.
4. Codex reviews the final report before accepting the work.

## Report Template

Use this for thread-to-control reports:

```text
## Topic

## Changed files

## Tests run

## Result

## Remaining risk

## Recommended next step
```

## Standard Server Rules

- Start/restart main server only with `start-main-server-visible.bat`.
- Check server with `tools/check-main-server-fast.sh` or `check-main-server-fast.bat`.
- Temporary direct `dotnet CoreServer.dll --start` is only for short diagnostics and must be cleaned up.
- Repeated operational commands should use scripts, not fragile inline shell quoting.
