# Dynamic Quest Graph Engine Design

## Goal

OpenDAoC-Core dynamic quests should grow from single kill tasks into a deterministic quest graph engine that can support Skyrim-like quest pacing: multi-step objectives, NPC hand-ins, player choices, conditional branches, meaningful rewards, and later LLM-written dialogue. The first implementation must prioritize gameplay correctness over prose generation, because dummy clients must be able to accept, execute, complete, and verify quests without GM commands.

The v1 target is a graph-backed quest runtime that preserves the current working dynamic quest flow while adding enough structure for future story, branch, reward, monster-growth, and companion hooks.

## Current State

`DynamicQuestRuntimeService` currently stores one `DynamicQuestDefinition` per NPC. A definition has one `DynamicQuestStepType.Kill`, one `TargetName`, one `TargetCount`, and one start NPC. Player progress stores `QuestId`, `Count`, `IsComplete`, and `AcceptedAt`. NPC interaction offers the quest, kill events increment the counter, and returning to the start NPC grants XP and money.

The current system already has important production foundations:

- Automatic deterministic seeding across Albion, Midgard, and Hibernia.
- NPC interaction and custom dialog acceptance.
- Read-only progress API for dummy verification.
- Dummy E2E completion through NPC hand-in.
- Completion tracking to prevent immediate repeat acceptance.

The missing piece is not LLM text. The missing piece is a richer deterministic model for quest steps and transitions.

## Design Principles

1. Server rules are deterministic. LLM output may propose text or graph data, but runtime progression is validated and executed by server rules.
2. Compatibility is preserved. Existing single-step kill quests are treated as a simple graph.
3. Every graph state is observable through a read-only API so dummy tests can verify progress without mutating state.
4. The graph model is small enough for unit tests and E2E tests before adding LLM generation.
5. Story immersion comes from consequences and pacing, not only from generated prose.

## Quest Graph Model

### DynamicQuestDefinition

`DynamicQuestDefinition` remains the root quest object, but gains graph fields:

- `GraphVersion`: integer schema version, initially `1`.
- `StartNodeId`: first node after acceptance.
- `Nodes`: ordered list of `DynamicQuestNode`.
- `Reward`: `DynamicQuestRewardDefinition`.
- `Tags`: optional string list for realm, region, target family, danger type, story theme, or future LLM hints.

Legacy fields such as `StepType`, `TargetName`, and `TargetCount` remain during migration. When `Nodes` is empty, the runtime materializes a compatibility graph equivalent to the old kill quest.

### DynamicQuestNode

A node describes one playable objective or narrative beat.

Required fields:

- `Id`: stable node id inside the quest.
- `Type`: `Talk`, `Kill`, `ReturnToNpc`, `Choice`, `Complete`, or `Fail`.
- `Title`: short UI/API label.
- `Text`: NPC/system text shown when the node becomes active.
- `Objective`: type-specific payload.
- `Edges`: list of possible transitions.

Initial node types:

- `Talk`: player must interact with an NPC. Used for setup, investigation, and hand-ins.
- `Kill`: player must kill one or more matching NPCs.
- `ReturnToNpc`: player must return to a specific NPC after objectives.
- `Choice`: player chooses one of several deterministic options.
- `Complete`: terminal success node.
- `Fail`: terminal failure node.

Deferred node types for later versions:

- `Explore`: reach a region/coordinate radius.
- `Collect`: acquire item or loot category.
- `Escort`: keep NPC/companion near a destination.
- `Survive`: remain alive during an encounter window.
- `BossKill`: kill a named or growth-evolved target.

### DynamicQuestObjective

The objective payload is validated by node type.

Kill payload:

- `TargetName`
- `TargetCount`
- `MinLevel`
- `MaxLevel`
- `RegionId`
- `AllowGroupCredit`

Talk and ReturnToNpc payload:

- `NpcInternalId`
- `NpcName`
- `RegionId`

Choice payload:

- `Choices`: list of `DynamicQuestChoice`

### DynamicQuestEdge

Edges control transitions.

Fields:

- `ToNodeId`
- `Condition`: `Always`, `ObjectiveComplete`, `ChoiceSelected`, `PlayerDied`, `TimedOut`, `PartySizeAtLeast`, or `WorldSignal`
- `ConditionValue`: optional string for choice id, world signal, or threshold.
- `Priority`: deterministic tie-breaker.

The runtime evaluates edges in priority order. A node can auto-transition when its objective completes, or it can wait for an NPC interaction or player choice.

## Player Progress Model

`DynamicQuestProgress` gains graph state:

- `CurrentNodeId`
- `NodeCounters`: per-node integer counters for kill and future collect objectives.
- `CompletedNodeIds`
- `ChoiceHistory`: selected choice ids by node id.
- `Failed`
- `Completed`
- `UpdatedAt`

`IsComplete` remains as a compatibility alias for terminal success. Old progress records still work for old quests.

## Runtime Flow

### Accept

When a player accepts a graph quest:

1. Validate the player does not already have or has not completed the quest.
2. Create `DynamicQuestProgress` with `CurrentNodeId = StartNodeId`.
3. If the current node is `Talk` and its condition is already satisfied by the accepting NPC, advance to the next node.
4. Send the active objective text and update the NPC quest indicator.

### NPC Interaction

On NPC interact:

1. Check whether the player has active progress for a quest involving this NPC.
2. If the current node is `Talk` or `ReturnToNpc` and the NPC matches, mark the node complete.
3. Evaluate outgoing edges.
4. If the new node is `Choice`, show a custom dialog or deterministic choice prompt.
5. If the new node is `Complete`, grant rewards and mark completion.
6. If no active progress exists, offer available quests as before.

### Enemy Killed

On enemy killed:

1. Find active progress where current node type is `Kill`.
2. Match target name, level range, and region.
3. Increment the current node counter.
4. When the node counter reaches the objective count, mark node complete.
5. Evaluate edges and send the next objective text.

### Choice

Choice nodes must be deterministic and dummy-friendly. The first implementation supports custom dialog accept/decline style choices, then expands to indexed choices.

For v1, choice nodes support two options:

- Accept/continue branch.
- Decline/safe completion branch.

The progress API exposes pending choices so dummy automation can choose by id or label later.

## Rewards

`DynamicQuestRewardDefinition` controls completion rewards:

- `XpMultiplier`
- `MoneyMultiplier`
- `StepBonusMultiplier`
- `PartyBonusMultiplier`
- `ChoiceBonusKey`

The v1 formula remains compatible with current XP/money rewards, then adds an explicit step-count bonus:

`baseReward * rewardMultiplier * partyMultiplier * (1 + max(0, completedPlayableStepCount - 1) * stepBonusMultiplier)`

Item, reputation, faction, and world-state rewards are deferred until graph progression is stable.

## Read-Only API

The existing progress API expands without changing its read-only behavior.

`/api/world/dynamic-quests/progress?account=...` returns:

- `active[].currentNodeId`
- `active[].currentNodeType`
- `active[].currentObjective`
- `active[].nodes[]`
- `active[].completedNodeIds[]`
- `active[].choices[]`
- `active[].isComplete`
- `active[].failed`

This API is the canonical dummy-test observation surface.

## Seeded v1 Quest Shape

The deterministic starter realm quests become graph quests:

1. `Talk`: start NPC offers the local threat.
2. `Kill`: kill the target NPC count.
3. `ReturnToNpc`: return to the start NPC.
4. `Choice`: choose safe completion or follow-up hook.
5. `Complete`: grant reward and mark quest complete.

For v1 E2E, the follow-up hook records the selected branch but does not spawn a second quest yet. This keeps tests deterministic while proving branch state works.

## LLM Role

LLM graph generation is allowed only as a constrained v1 graph template. LLM output is parsed into server-owned graph objects, then the same graph validator used by deterministic quests decides whether the definition may run.

Allowed LLM responsibilities:

- Generate title and NPC text.
- Suggest node labels and choice prose.
- Fill a deterministic `Talk -> Kill -> ReturnToNpc -> Choice -> Complete` graph template.
- Suggest follow-up quest seeds.

Disallowed LLM responsibilities:

- Grant rewards directly.
- Mark progress complete.
- Choose hidden branch outcomes outside server conditions.
- Create unvalidated target NPC names or impossible objectives.
- Override server-owned Talk/ReturnToNpc NPC identifiers.

## Monster Growth And Companion Hooks

Graph edges leave room for `WorldSignal` conditions. Later versions can connect these signals to:

- Mob-growth danger level in a region.
- Recently evolved monster families.
- Companion relationship or party composition.
- Player failure history, deaths, or repeated flee events.

The first graph implementation only records tags and branch choices. It does not mutate monster-growth state yet.

## Error Handling

Invalid graph definitions are rejected at `AddQuest`.

Validation rules:

- Unique node ids.
- Existing `StartNodeId`.
- Every edge target exists.
- Exactly one or more terminal nodes.
- Every non-terminal node has at least one outgoing edge.
- Objective payload required by node type.
- Text length limits compatible with DAoC client dialogs.
- Kill counts bounded by `KDAOC_DYNAMIC_QUEST_MAX_KILL_COUNT`.

Runtime failures should fail closed:

- Unknown current node: show a diagnostic message and do not advance.
- Invalid edge: skip and log warning.
- Missing reward definition: use default XP/money multipliers.
- LLM graph parse failure: reject the quest before it becomes active.

## Testing Strategy

Unit tests:

- Legacy kill quest materializes into a graph.
- Graph validation rejects missing nodes and bad edges.
- Kill node increments only matching NPCs.
- ReturnToNpc advances only on matching NPC.
- Choice node records selected branch.
- Complete node grants reward and clears progress.
- Progress snapshot exposes current node and completed nodes.

Dummy E2E tests:

- Existing dynamic quest E2E continues to pass.
- New graph quest E2E accepts, kills, returns, chooses default branch, completes.
- Read-only progress API reports current node after each phase.
- No GM command is used.

Regression tests:

- `accept_custom_dialog` remains `messageType=0x06`, `response=0x01`.
- Disconnect before NPC hand-in is not success.
- Party dummy reduced matrix remains stable after runtime changes.

## Implementation Phases

### Phase 1: Graph Data And Compatibility

Add graph model classes, validation, and compatibility graph materialization. Existing quests continue to behave the same.

### Phase 2: Runtime Progression

Refactor accept, NPC interact, kill handling, finish, and progress snapshot to use current graph node.

### Phase 3: Deterministic Seed Graph

Update starter realm auto-seeded quests to generate the v1 graph shape. Keep legacy kill fields populated for API compatibility during transition.

### Phase 4: Dummy E2E

Update dynamic quest dummy flow to observe graph progress and complete the default branch. Add focused unit tests and one E2E run.

### Phase 5: LLM Schema Preparation

Add JSON schema validation and documentation for LLM-generated quest graphs, without enabling LLM generation by default.

## Success Criteria

The first graph implementation is successful when:

- Existing dynamic quest E2E still passes.
- A graph quest with Talk, Kill, ReturnToNpc, Choice, and Complete passes through dummy automation.
- Progress API exposes enough state to verify each step without mutation.
- Starter realm seed quests remain balanced across Albion, Midgard, and Hibernia.
- GameServer builds with zero errors.
- Focused unit tests cover validation, progression, rewards, and API snapshots.
