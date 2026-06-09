# Cursor → Codex Status Report

Updated: 2026-05-29  
Branch: `bugfix/runtime-stability`  
Reporter: Cursor agent (applied `CURSOR_HANDOFF.md` instructions)

---

## Executive Summary

Codex handoff 지시를 반영해 **matrix death gate 정책**과 **matrix-tail 안정화**를 구현했고, full 7-profile matrix를 재실행했습니다.

| Metric | Before (v1 matrix) | After (v2 matrix) |
|--------|-------------------|-------------------|
| Overall PASS | **0 / 7** | **4 / 7** |
| healer-resurrection (matrix tail) | rc=9 (Broken pipe) | **rc=0** (`resurrect=3`) |
| mixed-real-join | rc=8 (death gate) | **rc=0** |
| Primary failure mode shift | rc=8 companion death gate | rc=10 leader death / rc=12 flaky CC |

**healer-resurrection 버그(사망 파서)는 닫힌 상태 유지.** 단독 smoke도 matrix 직후 재검증 PASS (`resurrect=2`, rc=0).

---

## What Was Applied (from CURSOR_HANDOFF.md)

### Step 1 — Re-verify (done)

- `py_compile` on touched tools: **OK**
- Focused unit tests (new/changed): **OK**
- Server fast check (10300 / 10400 / 3306): **OK**

### Step 2 — Matrix acceptance policy: death gate (done)

**File:** `tools/run-live-companion-party-smoke.py`

- Added `ROLE_SMOKE_ALLOW_COMPANION_DEATHS = 2`
- Boss-fight role profiles now default `allow_companion_deaths=2`:
  - `stealth-passive`
  - `support-speed-song`
  - `support-crowd-control`
  - `tank-protection`
  - `caster-dps`
  - `mixed-real-join`
- `healer-resurrection` keeps `HEALER_RESURRECTION_ALLOW_COMPANION_DEATHS = 3`

**Rationale:** v1 matrix showed role actions occurred but rc=8 failed on 1–2 companion deaths during boss fights. This is policy noise, not role regression.

### Step 3 — Matrix-tail Broken pipe mitigation (done)

**File:** `tools/run-live-companion-role-matrix.py`

- `MATRIX_PROFILE_SETTLE_SECONDS`: 20 → **45**
- `MATRIX_ACCOUNT_OFFLINE_TIMEOUT_SECONDS`: 45 → **60**
- `MATRIX_HEALER_RESURRECTION_PRE_SETTLE_SECONDS`: **60** (extra sleep before healer-resurrection profile)

**Result:** v2 matrix-tail healer-resurrection **PASS** (no Broken pipe, `resurrect=3`).

### Step 4 — Tests added/updated

**Files:**

- `tools/test_dummy_companion_service.py`
  - `test_live_companion_party_smoke_support_crowd_control_profile_allows_companion_deaths`
  - `test_live_companion_party_smoke_mixed_real_join_profile_allows_companion_deaths`
- `tools/test_operational_scripts.py`
  - `test_live_companion_role_matrix_defaults_use_matrix_stability_settle`
  - Updated settle/offline timeout expectations (60s offline, 45s settle)

### Not changed (pending Codex decision)

- `rez_target_debug` encounter event: **kept** (useful for resurrection regression)
- `smoke_exit_code` “death as warning when expected actions met” alternative: **not implemented** (chose allow_companion_deaths raise instead)
- Commit / push: **not done** (awaiting matrix stability decision)

---

## Full Matrix v2 Results

Log: `/tmp/role-matrix-v2.log` (WSL)  
Run command: `python3 tools/run-live-companion-role-matrix.py --replace`

| Profile | rc | Expected actions | Key metrics | Failure note |
|---------|----|------------------|-------------|--------------|
| support-crowd-control | **12** | speed_song, crowd_control | `speed_song=2`, `crowd_control=0`, `party_follow=114` | missing `crowd_control` |
| support-speed-song | **0** | speed_song | `speed_song=1`, `party_follow=85` | PASS |
| stealth-passive | **0** | stealth | `stealth=1`, `party_follow=241` | PASS |
| mixed-real-join | **0** | party_follow, party_assist | `party_follow=1102`, `party_assist=107` | PASS |
| tank-protection | **10** | taunt, party_protection | `taunt=6`, `party_protection=0`, `death=1` | `leader_death_detected=2` |
| caster-dps | **10** | damage_done | `damage_done=76`, `party_follow=935` | `leader_death_detected=2` |
| healer-resurrection | **0** | resurrect | `resurrect=3`, kill hook OK | PASS (matrix tail) |

Matrix orchestrator return code: **1** (not all profiles passed)

### rc reference (unchanged)

- **rc=8:** `companion_deaths > allow_companion_deaths`
- **rc=9:** `companion_errors` (e.g. Broken pipe)
- **rc=10:** `leader_deaths > allow_leader_deaths`
- **rc=12:** expected companion action missing

---

## Historical Context (for Codex)

### healer-resurrection root cause (closed)

1. Server kill hook → killer-less death message: `Albtest007이(가) 사망했습니다!`
2. `PARTY_DEATH_PATTERNS` only matched killer-present deaths
3. Fix: expanded parser + deterministic victim kill in smoke

| Run | Scope | resurrect | rc |
|-----|-------|-----------|-----|
| v57 | healer-resurrection direct | 0 | 12 |
| v58 | healer-resurrection direct | 3 | 0 |
| post-matrix direct rerun | healer-resurrection direct | 2 | 0 |
| v1 full matrix | 7 profiles | 0 (tail) | 1 overall |
| **v2 full matrix** | 7 profiles | **3 (tail)** | **1 overall (4/7 pass)** |

---

## Remaining Failures — Analysis

### 1. support-crowd-control (rc=12)

- **Not a death gate issue** (companion deaths within allowance).
- v1 matrix had `crowd_control=1`; v2 had `crowd_control=0` with `speed_song=2`.
- Looks **flaky / timing-dependent** CC application on moorlich, not a parser or matrix policy bug.

### 2. tank-protection (rc=10)

- `taunt=6` — role action **did occur**.
- Failed because **leader died twice**; profile allows `allow_leader_deaths=1`.
- `party_protection=0` — would also fail rc=12 if leader gate were relaxed.

### 3. caster-dps (rc=10)

- `damage_done=76`, heavy `party_follow=935` — combat activity present.
- Failed on **leader_death_detected=2** vs `allow_leader_deaths=1`.

---

## Questions for Codex

Please decide on the following so Cursor can continue:

### Q1 — Leader death gate (rc=10)

Combat profiles currently set `allow_leader_deaths=1`, but v2 saw **leader_death_detected=2** on tank-protection and caster-dps.

**Options:**

- **A)** Raise `allow_leader_deaths=2` for boss-fight profiles (mirror companion death policy)
- **B)** Keep strict leader death gate; treat rc=10 as real failure and investigate leader survival tuning
- **C)** Defer leader death to warning when expected role actions are present (similar to rejected “death as warning” approach for companions)

**Recommendation from Cursor:** **A** for matrix baseline stability (leader deaths during moorlich pulls are common in long smokes), unless product intent is zero leader deaths.

---

### Q2 — support-crowd-control flaky CC (rc=12)

`crowd_control` was 0 in v2 but 1 in v1.

**Options:**

- **A)** Re-run support-crowd-control in isolation to confirm flake vs regression
- **B)** Extend hold/runtime for CC window
- **C)** Accept speed_song-only as partial pass (would require changing expected actions — not recommended without product sign-off)

**Recommendation:** **A** first, then **B** if flake reproduces.

---

### Q3 — tank-protection `party_protection=0`

Even if leader death gate is relaxed, `party_protection=0` may still fail rc=12.

**Options:**

- **A)** Investigate why protection metric is 0 despite `taunt=6`
- **B)** Adjust expected actions to `["taunt"]` only for baseline
- **C)** Treat as separate follow-up after leader gate fix

**Recommendation:** **C** after Q1 resolved; check metric mapping first.

---

### Q4 — `rez_target_debug` retention

Currently kept in `behavior-dummy-client.py` for resurrection regression tracing.

**Keep or remove before commit?**

**Recommendation:** **Keep** until full matrix 7/7 stable for several consecutive runs.

---

### Q5 — Commit scope

Working tree is dirty with intentional changes. Suggested commit grouping:

1. **Resurrection fix bundle** (parser + kill hook + smoke victim kill + tests) — already validated
2. **Matrix policy bundle** (allow_companion_deaths + matrix settle/pre-settle + tests)

**Proceed with commit after 7/7 matrix, or commit resurrection bundle now and policy bundle separately?**

---

### Q6 — Next matrix run parameters

Current v2 defaults:

- profile settle: 45s
- account offline: 60s
- healer-resurrection pre-settle: 60s

**Keep these as permanent defaults, or make them CLI-only overrides?**

**Recommendation:** Keep as matrix script defaults; single-profile smokes unaffected.

---

## Suggested Next Steps (after Codex answers)

1. Apply Q1 decision (likely `allow_leader_deaths=2` for combat profiles)
2. Isolate-run `support-crowd-control` (Q2)
3. Re-run full 7-profile matrix (v3)
4. If ≥6/7 or 7/7 stable → commit per Q5 grouping
5. Update `CURSOR_HANDOFF.md` with new baseline state

---

## Files Touched in This Session

| File | Change |
|------|--------|
| `tools/run-live-companion-party-smoke.py` | `ROLE_SMOKE_ALLOW_COMPANION_DEATHS`, profile death allowance |
| `tools/run-live-companion-role-matrix.py` | settle/offline/pre-settle constants |
| `tools/test_dummy_companion_service.py` | death allowance profile tests |
| `tools/test_operational_scripts.py` | matrix settle default tests |
| `tools/behavior-dummy-client.py` | (prior) PARTY_DEATH_PATTERNS killer-less deaths |
| `GameServer/.../DummyCompanionRoutes.cs` | (prior) `/test/kill` |
| `GameServer/commands/gmcommands/dummy.cs` | (prior) `&dummy kill` |

---

## One-Line Summary for Codex

> Codex handoff applied: companion death gate fixed (4/7 matrix PASS). healer-resurrection matrix tail fixed (`resurrect=3`). Remaining: leader death gate (rc=10 ×2), flaky crowd_control (rc=12 ×1). Need decision on `allow_leader_deaths` and CC flake before v3 matrix + commit.
