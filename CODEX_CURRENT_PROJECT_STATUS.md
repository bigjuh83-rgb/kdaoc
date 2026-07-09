# OpenDAoC-Core Current Project Status

Use this as the compact project snapshot when opening a new topic thread.

## Global Operating Rules

- Codex is the primary operator.
- Codex subagents may be used for parallel read-only investigations or disjoint bounded implementation tasks.
- Cursor and Antigravity are fallback workers only when Codex quota is low or when explicitly requested.
- Main server start/restart standard: `start-main-server-visible.bat`.
- Fast server check: `tools/check-main-server-fast.sh` or `check-main-server-fast.bat`.
- Do not print or commit secrets.
- Codex execution-prompt fix applied in `C:\Users\uihan\.codex\config.toml`: `approval_policy = "never"`, `sandbox_mode = "danger-full-access"`, and `[windows] sandbox = "elevated"`. Current already-running tool host can remain non-admin until Codex is restarted.

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

Status: L1 reduced matrix data captured; early checkpoint stabilization continues.

Completed:
- `tools/run-dummy-growth-suite.py` growth-stage presets:
  - stabilize: L1-L4
  - train: L5 train/class/spec
  - gear: L6-L10
  - long: L10-L50
- `tools/summarize-dummy-growth-run.py` added.
- HIB L6 solo mudman checkpoint stabilized for 50x pre-service growth:
  - exact L4 mudman target only, no low-con/no-XP fallback.
  - route/API/direct move distance verified by `test-output/preservice-growth-50x-hib-l6-distance3600-suite-smoke`.
  - smoke result: XP `6350 -> 10394`, target_removed `1`, deaths `0`, no no-XP message.
- Reduced L1 realm/party matrix completed:
  - Run: `test-output/preservice-growth-50x-reduced-l1-l6-l10-rp124-s1001`.
  - Scope actually executed: L1 only, because `--checkpoint-levels 1,6,10` was combined with explicit `--max-segments 1`.
  - All 9 cases exited ok with deaths `0` and movement failures `0`.
  - ALB L1 gained XP across p1/p2/p4; HIB p1/p2 gained XP; MID p1/p2/p4 and HIB p4 ended with XP `0`.
  - HIB provisioning showed low equipment coverage compared with ALB/MID: p1 `2` items, p2 `10` items, p4 `14` items.
- L1 MID/HIB route and party XP stabilization completed:
  - MID p1 switched to level 0 `lupine gnawer`; MID p2/p4 moved to level 0 spider/wildling/mud snake clusters.
  - L1 MID/HIB p1/p2/p4 target bands now stay at level 0 to avoid early no-XP/death/flee cases.
  - L1-L4 party assist interval reduced to `0.4s` and target-in-view attack prime reduced to `0.0s`.
  - HIB p4 fourth growth slot changed from Champion/Large Weapons to Blademaster/Blades because Champion produced `0` damage at L1.
  - Full MID/HIB L1 p1/p2/p4 smoke before the HIB slot change: `test-output/preservice-growth-50x-l1-mid-hib-fastassist-s1201`, 6 cases ok, deaths `0`, movement failures `0`, MID p4 all accounts gained XP.
  - HIB p4 focused revalidation after the slot change: `test-output/preservice-growth-50x-l1-hib-p4-blademaster-s1201`, 4/4 accounts gained XP `50`, deaths `0`, movement failures `0`.
- L1 start-position fallback and no-watcher matrix completed:
  - `tools/provision-dummy-accounts.py` writes start coordinates and zone to CSV for client spawn fallback.
  - Regression test covers the new CSV fields.
  - No-watcher matrix: `test-output/preservice-growth-50x-l1-default-rp124-nowatch-s1201`, 9/9 cases ok, deaths `0`, movement failures `0`.
  - Solo/p2 accounts all gained XP; p4 had one zero-XP account per realm (`growthalb744`, `growthmid804`, `growthhib863`).
  - Watcher-enabled ALB p4 still has watcher aggro risk; use no-watcher for player XP collection until watcher behavior is hardened.
- L5/L6 solo checkpoint gate root cause fixed:
  - Live supervisor now respects realm/level growth distance caps instead of narrowing HIB L5 from `5200` back to the generic cap.
  - Flee outcomes are recorded as balance/recovery data, not hard regression failures by themselves.
  - Revalidation: `test-output/preservice-growth-50x-train-l5-l6-p1-rootcausefix-s1201`, exit `0`, no failure reproduction files.
  - ALB L5/L6 XP `2021/4044`, MID L5/L6 XP `2019/4044`, HIB L5/L6 XP `0/4044`; deaths `0`, movement failures `0`.

Known remaining:
- Run L6/L10 checkpoint matrix separately now that L5/L6 solo no longer aborts.
- DB-based hunting spot preselection for remaining weak levels, starting with HIB L5 XP `0`.
- Decide whether p4 zero-XP accounts are acceptable balance data or should be fixed before L1-L50.
- Re-run watcher-enabled L1 matrix only after watcher aggro behavior is safe.
- Full L1-L50 long matrix after early checkpoints are stable.
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
