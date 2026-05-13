# Hunter Dummy Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a beginner-hunter dummy mode that selects level-appropriate NPCs, approaches them, attacks, gives up on stuck targets, and wanders when no target exists.

**Architecture:** Keep the behavior in `tools/behavior-dummy-client.py` and reuse `HeadlessDaocClient` movement, NPC tracking, targeting, and combat packet helpers. Add small helper functions for target selection and wandering instead of creating a new framework.

**Tech Stack:** Python 3 standard library, OpenDAoC TCP packet helpers in `tools/headless-daoc-client.py`.

---

### Task 1: Hunter Targeting And Wandering

**Files:**
- Modify: `tools/behavior-dummy-client.py`
- Modify: `docs/headless-dummy-client.md`

- [ ] Add `--hunter`, level filter, target timeout, wandering, rest chance, and think delay options.
- [ ] In hunter mode, choose NPCs within configured level range, avoid peace NPCs by default, approach with existing movement packets, attack inside range, and switch targets when stuck.
- [ ] When no target exists, optionally wander with simple position packets.
- [ ] Document the beginner hunter command.
- [ ] Verify with `python3 -m py_compile tools/behavior-dummy-client.py tools/headless-daoc-client.py`.
- [ ] Run 1 dummy hunter for 45 seconds.
- [ ] Run 3 dummy hunters for 45 seconds.
