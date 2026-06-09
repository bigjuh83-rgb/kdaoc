# OpenDAoC-Core Growth Test Thread

## Scope

- L1-L50 dummy growth
- L5 train/class/spec verification
- Gear replacement
- Item/gold/sell checks
- Party behavior during leveling
- Death/release/recover
- Growth monster regression

## Rules

- Do not waste time with blind long runs.
- First inspect source, DB, and logs for predictable failure conditions.
- Use this sequence:
  1. single failure reproduction
  2. log root cause
  3. unit test
  4. single revalidation
  5. reduced matrix
  6. full matrix

## Main Files

- `tools/run-dummy-growth-suite.py`
- `tools/summarize-dummy-growth-run.py`
- `tools/test_dummy_growth_suite.py`
- `tools/test_operational_scripts.py`

## Completed

- Growth-stage presets:
  - `stabilize`: L1-L4
  - `train`: L5 train/class/spec
  - `gear`: L6-L10
  - `long`: L10-L50
- Failure reproduction command output was added.
- Summary script reports death, target removed, timeout, flee, watcher XY/Z/rewind.

## Next Work

1. Preselect hunting spots per level from DB.
2. Run fast L1/L6/L10 checkpoints.
3. Run L50 party boss after L10 stability.
4. Only then move to RvR/frontier smoke.

## Useful Commands

```bash
python3 -m unittest tools.test_dummy_growth_suite tools.test_operational_scripts
python3 tools/run-dummy-growth-suite.py --growth-stage train
python3 tools/summarize-dummy-growth-run.py <run-dir>
```
