# Dynamic Quest Explore v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a server-authoritative `Explore` node to dynamic quests and prove it through unit tests, build, and live dummy E2E.

**Architecture:** `Explore` is a first-class graph node with location fields on `DynamicQuestObjective`. Runtime progress is advanced only by server-observed player position updates; dummy clients only read the progress API and move.

**Tech Stack:** C# OpenDAoC game server, NUnit unit tests, Python dummy automation, read-only WorldAI API.

---

### Task 1: Runtime Model And Validation

**Files:**
- Modify: `GameServer/WorldAI/DynamicQuestGraph.cs`
- Modify: `GameServer/WorldAI/DynamicQuestRuntimeService.cs`
- Test: `Tests/UnitTests/WorldAI/UT_DynamicQuestRuntimeService.cs`

- [ ] **Step 1: Write failing tests**

Add tests that a `Talk -> Explore -> Kill -> ReturnToNpc -> Choice -> Complete` graph is accepted, invalid Explore objectives are rejected, Explore progress outside radius does not advance, and Explore progress inside radius advances to Kill.

- [ ] **Step 2: Run focused tests**

Run: `wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec /home/bigjuh/.dotnet/dotnet test Tests/Tests.csproj -c Debug --no-restore --filter UT_DynamicQuestRuntimeService`

Expected before implementation: failures mentioning missing `Explore` enum/objective/progress support.

- [ ] **Step 3: Add model fields**

Add `Explore` to `DynamicQuestNodeType` and add `LocationName`, `X`, `Y`, `Z`, `Radius` to `DynamicQuestObjective`.

- [ ] **Step 4: Add validation**

In `ValidateNodeObjective`, reject `Explore` nodes when `LocationName` is empty or over 80 chars, `RegionId == 0`, `X <= 0`, `Y <= 0`, or `Radius < 64 || Radius > 2000`.

- [ ] **Step 5: Add progression**

Add `RecordExploreProgressForTest(playerKey, regionId, x, y)` and locked runtime logic that advances only when the current node is `Explore`, region matches, and horizontal distance is inside radius.

- [ ] **Step 6: Run focused tests**

Run the same `UT_DynamicQuestRuntimeService` command. Expected: runtime tests pass.

### Task 2: Server Position Hook

**Files:**
- Modify: `GameServer/WorldAI/DynamicQuestRuntimeService.cs`
- Modify: `GameServer/gameobjects/GamePlayer.cs`

- [ ] **Step 1: Add live runtime entrypoint**

Add `HandlePlayerPositionUpdated(GamePlayer player)`. It returns immediately when dynamic quests are disabled or player is null, loads player progress, calls locked Explore progression with `player.CurrentRegionID`, `player.X`, `player.Y`, then sends the next objective message only if the node advanced.

- [ ] **Step 2: Hook player movement packet**

Call `DynamicQuestRuntimeService.Instance.HandlePlayerPositionUpdated(this)` after `movementComponent.OnPositionUpdate()` in `GamePlayer.OnPositionUpdateFromPacket()`.

- [ ] **Step 3: Compile focused server tests**

Run: `wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec /home/bigjuh/.dotnet/dotnet test Tests/Tests.csproj -c Debug --no-restore --filter UT_DynamicQuestRuntimeService`

Expected: pass.

### Task 3: Deterministic Seeder Graph

**Files:**
- Modify: `GameServer/WorldAI/DynamicQuestSeedService.cs`
- Test: `Tests/UnitTests/WorldAI/UT_DynamicQuestSeedService.cs`

- [ ] **Step 1: Write failing seed tests**

Update seed tests to expect `Talk, Explore, Kill, ReturnToNpc, Choice, Complete` and assert Explore objective has target NPC region, target NPC coordinates, location name, and radius `450`.

- [ ] **Step 2: Add seed NPC coordinates**

Add `X`, `Y`, and `Z` to `DynamicQuestSeedNpc`; populate them from `GameNPC.X/Y/Z` in `Seed(IEnumerable<GameNPC>, ...)`; update test helper defaults.

- [ ] **Step 3: Build Explore node**

Find the target NPC sample for each definition, pass it into `BuildQuest`, add an `explore` node between `talk` and `kill`, and make the `talk` edge point to `explore`.

- [ ] **Step 4: Run seed tests**

Run: `wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec /home/bigjuh/.dotnet/dotnet test Tests/Tests.csproj -c Debug --no-restore --filter UT_DynamicQuestSeedService`

Expected: pass.

### Task 4: Safe LLM Parser Support

**Files:**
- Modify: `GameServer/WorldAI/DynamicQuestRuntimeService.cs`
- Test: `Tests/UnitTests/WorldAI/UT_DynamicQuestRuntimeService.cs`

- [ ] **Step 1: Write parser tests**

Add a parser test where an LLM graph includes `Explore` with text only and the parser fills server-owned safe objective fields from the quest fallback.

- [ ] **Step 2: Implement parser branch**

In `ParseLlmObjective`, return a safe `Explore` objective with sanitized `LocationName`, `RegionId = quest.StartRegionId`, positive fallback `X/Y/Z`, and `Radius = 450`; ignore LLM coordinates.

- [ ] **Step 3: Run parser tests**

Run `UT_DynamicQuestRuntimeService`. Expected: pass.

### Task 5: Dummy Explore Automation

**Files:**
- Modify: `tools/behavior-dummy-client.py`
- Modify: `tools/headless-daoc-client.py` only if dialog opcode or movement support is missing
- Test: relevant Python unit tests for headless dialog/progress parsing

- [ ] **Step 1: Confirm custom dialog opcode**

Verify `accept_custom_dialog()` sends `0x06`, not `0x01`.

- [ ] **Step 2: Add Explore snapshot parsing**

Add helpers that detect `currentNodeType == Explore` or string `"Explore"` and extract `currentObjective.regionId/x/y/z/radius/locationName`.

- [ ] **Step 3: Add movement before kill**

When dynamic quest E2E is enabled and the current node is Explore, set the active movement destination to the Explore coordinates and wait for the read-only API to report the next node before hunting the required target.

- [ ] **Step 4: Run Python checks**

Run: `python -m py_compile tools/behavior-dummy-client.py tools/headless-daoc-client.py`

Expected: pass.

### Task 6: Build And Live Verification

**Files:**
- No planned source edits unless tests expose a bug.

- [ ] **Step 1: Run combined unit tests**

Run: `wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec /home/bigjuh/.dotnet/dotnet test Tests/Tests.csproj -c Debug --no-restore --filter "UT_DynamicQuestRuntimeService|UT_DynamicQuestSeedService"`

Expected: pass.

- [ ] **Step 2: Build server**

Run: `cmd /c build-server.bat`

Expected: build success.

- [ ] **Step 3: Restart visible server**

Run: `cmd /c start-main-server-visible.bat`

Expected: visible server starts using the project standard script.

- [ ] **Step 4: Fast server check**

Run: `cmd /c check-main-server-fast.bat`

Expected: TCP 10300, UDP 10400, and DB 3306 checks pass.

- [ ] **Step 5: Live dummy E2E**

Run the existing dynamic quest party command with no GM commands. Expected: both dummy characters accept, complete Explore, kill required target, return, select completion dialog, observe reward, and end with inactive progress.
