# OpenDAoC-Core Current Project Status

Use this as the compact project snapshot when opening a new topic thread.

## Global Operating Rules

- Codex is the primary operator.
- Codex subagents may be used for parallel read-only investigations or disjoint bounded implementation tasks.
- Cursor and Antigravity are fallback workers only when Codex quota is low or when explicitly requested.
- Main server start/restart standard: `start-main-server-visible.bat`.
- Fast server check: `tools/check-main-server-fast.sh` or `check-main-server-fast.bat`.
- Do not print or commit secrets.

## Companion System

Status: mostly complete, now in polish/stabilization.

Completed:
- Player-facing term is `용병`.
- Internal `dummy` naming remains for code/tools.
- `/dummy` is GM-only test command.
- Companion recruiter NPC route exists.
- Live companion service exists.
- Player command smoke exists.
- `player-command-modes` smoke passed.
- `player-command-all-roles` smoke passed.
- Companion dialogue pools now include:
  - Global repeated situations: 14 categories, 32 lines each.
  - 8 personalities.
  - Personality chat: 18 categories, at least 12 lines each.
  - Personality state speech: 7 categories, at least 10 lines each.

Known remaining polish:
- Service startup should wait/retry until server API is ready.
- Recruiter UX should be checked in-game.
- Real player joins should release lower-priority companions safely.

## Movement/Rewind

Status: still needs focused work.

Known facts:
- Large 48896 jumps matched packet/world speed confusion.
- Movement still has reported visible rewind/floating/Z mismatch symptoms.
- User wants close follow during movement.
- Noncombat catchup speed and teleport are allowed when far behind.
- Combat catchup speed/teleport are forbidden.
- Teleport threshold should be around 2500+, not 4500+.

Recommended next:
- Create movement-command smoke separate from combat smoke.
- Validate `따라와`, `대기`, `여기로`, `소환`.
- Summarize movement audit + client movement JSONL automatically.

## Combat AI/FSM

Status: skeleton and policy layers exist; continue incremental hardening.

Completed:
- FSM skeleton introduced.
- Target intent/source/decision skeleton introduced.
- Hostile target gate started.
- Companion command modes introduced.
- Healer one-shot attack behavior exists for `ㄱㄱ`, then returns to healing/support.

Known remaining:
- Full class-specific skill/spell behavior is not exhaustive.
- Healer aggro handling should orbit around party/tank instead of straight-line flee.
- CC/mez/stun conditions need deeper role/class coverage.

## Growth Tests

Status: paused.

Completed:
- `tools/run-dummy-growth-suite.py` growth-stage presets:
  - stabilize: L1-L4
  - train: L5 train/class/spec
  - gear: L6-L10
  - long: L10-L50
- `tools/summarize-dummy-growth-run.py` added.

Known remaining:
- DB-based hunting spot preselection per level.
- Fast L1/L6/L10 checkpoints.
- L50 party boss after early growth.

## RvR/Frontier

Status: planned.

Known goals:
- Three-realm RvR smoke.
- Frontier tests.
- Same-realm/party member hostile target prevention.
- Companion reward/RP/kill-credit limitations.

## Korean Client UI

Status: user-side visual confirmation pending.

Known work:
- Korean UI font fallback focus:
  - `ui/custom/assets.xml`
  - `ui/atlantis/assets.xml`
  - `ui/isles/assets.xml`
- Target aliases:
  - `arial9`
  - `arial11`
  - `font_memo`
  - `Font_Memo`
- Prefer `GdiFont + Gulim + Charset 129` for Korean UI.
- Do not touch `game.dll`/glyph warmup unless explicitly scoped.

## Operations/API

Status: partially stabilized, still needs startup polish.

Known facts:
- WSL service on current machine is `WSLService`, not `LxssManager`.
- API keys must not be written into public repo docs.
- LiteLLM is planned as the routing layer.
- Companion service previously failed with `ConnectionRefusedError` when it started before server API was ready.

Recommended next:
- Add companion service API wait/retry.
- Confirm visible server batch starts companion service after API readiness.
- Keep API usage below free quota.
