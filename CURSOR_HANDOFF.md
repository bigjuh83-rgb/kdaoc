# Cursor Handoff

Updated: 2026-05-29
Branch: `bugfix/runtime-stability`
HEAD: `2ce671324 Improve live companion operations flow`

## Current State

- `healer-resurrection` is fixed at the direct smoke level and is no longer the main unresolved bug.
- The remaining work is on the full live companion role matrix:
  - `rc=8` failures are mostly exit-policy `death gate` failures, not missing role actions.
  - `rc=9` on matrix-tail `healer-resurrection` is a `Broken pipe` stability issue that appears in matrix sequencing, not in isolated healer smoke.

## Key Conclusion

The old handoff that said "healer-resurrection is unresolved" is obsolete.

The real root cause was the death-detection pipeline:

1. Server kill hook generated killer-less death messages such as:
   - `Albtest007이(가) 사망했습니다!`
2. `tools/behavior-dummy-client.py` only recognized killer-present death patterns.
3. Result:
   - death chat arrived
   - `party_member_death_message` did not register
   - resurrection target was never created
   - `resurrect=0`

That bug is now fixed.

## Implemented Fixes

### Server

- `GameServer/API/DummyCompanion/DummyCompanionRoutes.cs`
  - Added `POST /api/dummy/companions/test/kill?player=&account=`
- `GameServer/commands/gmcommands/dummy.cs`
  - Added `&dummy kill <playerName>`

### Smoke Harness

- `tools/run-live-companion-party-smoke.py`
  - Added deterministic victim kill scheduling for `healer-resurrection`
  - Added joiner heal-exclude plumbing so the victim remains a valid resurrection target

### Client Parser

- `tools/behavior-dummy-client.py`
  - Expanded `PARTY_DEATH_PATTERNS` to include killer-less Korean and English death messages

### Regression Tests

- `tools/test_behavior_player_follow.py`
  - Added parser tests for killer-less death messages
  - Added self-release non-matching protection

## Verification History

| Run | Scope | resurrect | return_code | Notes |
| --- | --- | ---: | ---: | --- |
| v57 | healer-resurrection direct | 0 | 12 | kill hook present, parser not fixed |
| v58 | healer-resurrection direct | 3 | 0 | PASS |
| full matrix | 7 profiles | healer 0 in matrix tail | 1 overall | see failure analysis below |
| post-matrix direct rerun | healer-resurrection direct | 2 | 0 | PASS again |

Interpretation:

- `healer-resurrection` itself is stable enough in isolated runs.
- The unresolved work is matrix policy/stability.

## Full Matrix Failure Analysis

### Summary

- `support-crowd-control`: role action occurred, failed at companion death gate
- `support-speed-song`: role action occurred, failed at companion death gate
- `stealth-passive`: role action occurred, failed at companion death gate
- `mixed-real-join`: role actions occurred, failed at companion death gate
- `tank-protection`: death gate hit before meaningful acceptance
- `caster-dps`: damage/heal happened, failed at companion death gate
- `healer-resurrection`: matrix-tail healer `Broken pipe`, not the old resurrection parsing bug

### rc Meanings

- `rc=8`: `companion_deaths > allow_companion_deaths`
- `rc=9`: `companion_errors` present
- `rc=12`: expected companion action missing

### Operational Interpretation

Most matrix failures are not role-behavior regressions. They are policy failures caused by `allow_companion_deaths=0` in scenarios where one or two companion deaths may be acceptable for the smoke goal.

The remaining technical instability is the matrix-tail `Broken pipe` in `healer-resurrection`.

## Files Most Relevant Now

- `tools/run-live-companion-role-matrix.py`
- `tools/run-live-companion-party-smoke.py`
- `tools/dummy-companion-service.py`
- `tools/behavior-dummy-client.py`
- `tools/test_behavior_player_follow.py`
- `tools/test_dummy_companion_service.py`
- `tools/test_operational_scripts.py`

## Current Working Tree Notes

Working tree is dirty. Do not revert unrelated modifications.

Notable modified/untracked files observed in this line of work:

- `tools/behavior-dummy-client.py`
- `tools/dummy-companion-service.py`
- `tools/dummy-party-albion-pve8.csv`
- `tools/headless-daoc-client.py`
- `tools/run-live-companion-party-smoke.py`
- `tools/test_behavior_player_follow.py`
- `tools/test_dummy_companion_service.py`
- `tools/test_operational_scripts.py`
- `tools/run-live-companion-role-matrix.py` (untracked in prior status)

There are also noise/untracked paths like:

- `case/`
- `nul`
- `test-output/`
- `tools/test-output/`
- `wsl_err.txt`
- `wsl_out.bin`

Do not bulk-clean the tree unless you inspect ownership first.

## Standard Operating Rules

- Start/restart the main server only with:
  - `C:\Users\uihan\Desktop\다옥프리서버\OpenDAoC-Core\start-main-server-visible.bat`
- Fast server check only with:
  - `C:\Users\uihan\Desktop\다옥프리서버\OpenDAoC-Core\check-main-server-fast.bat`
  - or `tools/check-main-server-fast.sh`
- Use one WSL route:
  - `wsl.exe --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec ...`
- Do not expose tokens, keys, or passwords.

## Next Priority

1. Re-verify the current working tree:
   - `py_compile`
   - focused unit tests
   - fast server check
2. Fix matrix acceptance policy:
   - decide whether profile-level `allow_companion_deaths` should be raised
   - or whether some profiles should accept deaths as warnings when expected actions occurred
3. Investigate matrix-tail `healer-resurrection` `Broken pipe`:
   - likely sequencing, cooldown, or profile-to-profile contamination
4. Re-run the full 7-profile matrix
5. Decide whether to keep or remove `rez_target_debug`
6. Commit and push after matrix verification is stable

## Suggested Commands

### Re-verify

```powershell
wsl.exe --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m py_compile tools/behavior-dummy-client.py tools/dummy-companion-service.py tools/run-live-companion-party-smoke.py tools/run-live-companion-role-matrix.py tools/test_behavior_player_follow.py tools/test_dummy_companion_service.py tools/test_operational_scripts.py
```

```powershell
wsl.exe --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_behavior_player_follow tools.test_dummy_companion_service tools.test_operational_scripts
```

```powershell
wsl.exe --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec bash tools/check-main-server-fast.sh
```

### Re-run Full Matrix

```powershell
wsl.exe --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 tools/run-live-companion-role-matrix.py --replace
```

## One-Line Summary

`healer-resurrection` is fixed and passes in isolated smoke. The remaining work is full-matrix acceptance/stability: mainly `death gate` policy (`rc=8`) and matrix-tail healer `Broken pipe` (`rc=9`), not a role AI regression.

## Codex Decisions After Cursor v2 Report

The latest Cursor report changed the priority. Use these decisions for the next pass.

### 1. Do not widen leader death gate yet

- Keep `allow_leader_deaths` strict for now.
- Do **not** immediately raise it from `1` to `2` just to make the matrix greener.
- Reason: companion death gate was policy noise, but `leader_death_detected=2` on `tank-protection` and `caster-dps` is still strong enough to treat as a real survivability signal until isolated evidence says otherwise.

### 2. Keep the companion death allowance changes

- Keep the already-added role-profile `allow_companion_deaths` baseline.
- That change is acceptable for the boss-fight role matrix because it removed obvious rc=8 policy noise without hiding missing role actions.

### 3. Keep `rez_target_debug`

- Keep resurrection debug instrumentation for now.
- Remove it only after the role matrix is stable across several consecutive runs.

### 4. Keep the matrix settle defaults

- Keep these as script defaults for now:
  - `MATRIX_PROFILE_SETTLE_SECONDS = 45`
  - `MATRIX_ACCOUNT_OFFLINE_TIMEOUT_SECONDS = 60`
  - `MATRIX_HEALER_RESURRECTION_PRE_SETTLE_SECONDS = 60`
- Single-profile smokes are unaffected, and the matrix-tail healer stabilization was useful.

### 5. Do not commit yet

- Hold commits until the remaining failures are narrowed further.
- Next target is not “make 7/7 green by relaxing every gate”.
- Next target is “prove whether the remaining 3 failures are survivability defects, flaky timing, or metric gaps”.

## Immediate Cursor Tasks

Use Cursor for bounded, low-ambiguity verification and narrow fixes. Avoid large redesigns.

### Task A — isolate `support-crowd-control`

Goal:
- determine whether `crowd_control=0` in matrix v2 is a real regression or a flake

Do:
1. run `support-crowd-control` in isolation at least twice with current defaults
2. compare:
   - `crowd_control`
   - `speed_song`
   - `party_follow`
   - `target_rejected`
   - leader deaths / companion deaths
3. inspect the service report + encounters timeline if one run passes and one fails

Decision rule:
- if isolated runs are consistently green, classify this as matrix flake/timing
- if isolated runs still miss `crowd_control`, treat it as a real support CC behavior issue

### Task B — isolate `tank-protection`

Goal:
- determine whether `rc=10` is just harsh policy or whether the leader is dying for a real tactical reason

Do:
1. run `tank-protection` in isolation with current defaults
2. inspect:
   - `leader_death_detected`
   - `taunt`
   - `party_protection`
   - whether `party_protection=0` is a metric gap or a true missing behavior
3. if `taunt` fires but `party_protection` stays zero, inspect the metric mapping before changing expectations

Do not:
- change expected actions to `["taunt"]` only yet

### Task C — isolate `caster-dps`

Goal:
- determine whether the remaining `rc=10` is a genuine leader survival issue or just matrix fatigue

Do:
1. run `caster-dps` in isolation with current defaults
2. inspect:
   - `damage_done`
   - `leader_death_detected`
   - leader report / encounters around death
3. compare against matrix artifact to see whether the same death pattern reproduces outside the matrix

### Task D — only then decide the next matrix action

After A/B/C:
- if `support-crowd-control`, `tank-protection`, and `caster-dps` are green in isolation but red in matrix, classify the remaining issue as matrix sequencing/stability
- if one or more fail in isolation, keep focus on that specific behavior instead of widening gates

## Preferred Short-Term Outcome

The next useful checkpoint is:
- `healer-resurrection` still green
- clear classification for the remaining 3 red profiles:
  - real behavior issue
  - metric gap
  - matrix-only flake

That is more valuable than a quick 7/7 obtained by relaxing leader-death policy too early.
