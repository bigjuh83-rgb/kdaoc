# Dynamic Quest Explore v2 Design

## Goal

Dynamic quest v2 adds a server-authoritative `Explore` graph node. The node lets a quest ask the player to discover, inspect, or approach a world location before continuing to later objectives such as kill, return, choice, and completion.

The first implementation is intentionally deterministic. It must support dummy E2E testing without GM commands and without mutating progress through APIs. LLM output may provide prose and location intent, but the server owns coordinate selection, validation, progression, and rewards.

## Current State

Dynamic quest graph v1 supports `Talk`, `Kill`, `ReturnToNpc`, `Choice`, `Complete`, and `Fail`. Deterministic starter quests currently run as:

```text
Talk -> Kill -> ReturnToNpc -> Choice -> Complete
```

Read-only progress APIs expose the current node, current objective, completed node ids, choices, and full node list. Dummy clients can observe this state and complete the quest through real NPC interaction, combat, and custom dialog acceptance.

The missing piece for Skyrim-like pacing is an objective that asks the player to move through the world before combat or hand-in. `Explore` fills that gap.

## Approved Approach

Use server-authoritative location progress.

`Explore` is complete only when the server observes that the player's current region and position are inside the configured objective radius. The dummy client may read the target coordinates from the read-only progress API and move there, but it must not call a progress mutation API.

## Graph Shape

Starter v2 quests use this deterministic shape:

```text
Talk -> Explore -> Kill -> ReturnToNpc -> Choice -> Complete
```

The `Explore` node should be placed after `Talk` and before `Kill` so the player first investigates the area, then finds or confirms the threat, then fights. This gives the graph a story beat without depending on LLM-generated state changes.

## Data Model

`DynamicQuestNodeType` gains:

```text
Explore
```

`DynamicQuestObjective` gains location fields:

```text
LocationName: short display/API label
X: world X coordinate
Y: world Y coordinate
Z: world Z coordinate
Radius: completion radius in world units
```

`RegionId` remains the shared region field. For `Explore`, `RegionId` is required and must be non-zero.

Suggested validation limits:

- `LocationName`: required, max 80 characters.
- `RegionId`: required, non-zero.
- `X`, `Y`: required, positive.
- `Z`: optional for completion math, but retained for dummy movement destination and diagnostics.
- `Radius`: required, rejected outside `64..2000`; deterministic seed should use `450`.

## Runtime Progression

The runtime adds a progress path equivalent to kill and NPC interaction progression:

```text
RecordExploreProgress(player)
```

Behavior:

1. Find active progress whose current node type is `Explore`.
2. Check the player is in `objective.RegionId`.
3. Compute horizontal distance from player `X/Y` to objective `X/Y`.
4. If distance is greater than `objective.Radius`, do nothing.
5. If inside radius, mark the `Explore` node complete.
6. Advance along the first `ObjectiveComplete` edge by priority.
7. Save progress.
8. Send the next objective text to the player.

Completion uses horizontal distance only. `Z` is exposed for movement and diagnostics, but it must not block completion because terrain, water, bridges, and client/server Z reconciliation can vary.

## Server Trigger

The server should call explore progress from `GamePlayer.OnPositionUpdateFromPacket()` after the existing movement component update. The runtime entrypoint should be `DynamicQuestRuntimeService.HandlePlayerPositionUpdated(GamePlayer player)`. The call must be cheap and guarded:

- Return immediately if dynamic quests are disabled.
- Return immediately if the player has no active dynamic quest progress loaded.
- Only evaluate current `Explore` nodes.
- Avoid scanning all quests when the player has no progress.

No GM command and no write API should advance `Explore` during E2E tests.

## Read-Only API

The existing progress API remains the canonical observation surface:

```text
GET /api/world/dynamic-quests/progress?player=<character>
```

For an active `Explore` node, `active[].currentObjective` includes:

```json
{
  "locationName": "찢긴 울타리",
  "regionId": 1,
  "x": 522379,
  "y": 492185,
  "z": 2954,
  "radius": 450
}
```

The API is read-only. Dummy automation may use these fields as movement targets and verify the node changes to `Kill`, `ReturnToNpc`, or another configured next node.

## Deterministic Seed

`DynamicQuestSeedService` should generate one `Explore` node for each starter realm quest. For v2, the explore location can be derived from the selected target NPC sample:

- Use the target NPC's region and coordinates.
- Use a readable location label derived from the target name, for example `<targetName> 흔적`.
- Use a radius large enough for dummy movement tolerance, recommended `450`.

This keeps the seed deterministic and ensures the explore objective points near real world content.

The seed graph becomes:

```text
talk -> explore -> kill -> return -> choice -> complete
```

## LLM Role

LLM may suggest:

- `LocationName`
- node title and text
- narrative reason for the investigation
- choice prose after the return node

LLM must not own:

- coordinates
- radius
- rewards
- completion state
- DB changes
- commands
- spawned entities

If LLM graph parsing accepts an `Explore` node, the parser should ignore or sanitize LLM-provided coordinates unless a future server-owned resolver explicitly validates them. For v2, deterministic seed is the primary Explore source; LLM Explore support can be limited to text and node structure.

## Dummy E2E

Dummy behavior should use the existing read-only progress endpoint:

1. Accept the quest through NPC interaction and custom dialog.
2. Observe `currentNodeType == Explore`.
3. Move toward `currentObjective.regionId/x/y/z`.
4. Wait until the API reports that the active node advanced.
5. Continue existing required target kill, return to NPC, choice, and reward verification.

The E2E report should preserve the same difficulty metrics already used for dynamic quest tests:

- deaths
- elapsed time
- target removed
- completion rate
- return interaction
- reward observed
- final inactive

Add `dynamic_quest_explore_complete` and movement samples if dummy changes are needed.

## Tests

Runtime tests:

- A graph with `Talk -> Explore -> Kill -> ReturnToNpc -> Choice -> Complete` is accepted.
- `Explore` node validation rejects missing region, missing location name, invalid coordinates, or invalid radius.
- `RecordExploreProgressForTest` does not advance outside the radius.
- `RecordExploreProgressForTest` advances inside the radius and persists current node as the next node.
- Completed playable step count includes `Explore` in step reward scaling.

Seed tests:

- Deterministic seed contains `Explore` between `Talk` and `Kill`.
- Explore objective has region, location name, coordinates, and valid radius.

Parser tests:

- LLM graph parser recognizes `Explore` only within the safe v2 rules.
- Forbidden LLM fields remain rejected inside Explore nodes.

Dummy tests:

- Progress snapshot parsing recognizes `Explore` objective coordinates.
- Dummy E2E can move to Explore objective and then continue to kill/return/choice.

## Non-Goals

Explore v2 does not add hidden map discovery, object spawning, item collection, escort behavior, timed failure, phased NPCs, or direct LLM world mutation. Those are future graph extensions after server-authoritative node progression is stable.

## Acceptance Criteria

Explore v2 is complete when:

1. Unit tests prove graph validation, server-authoritative explore progression, reward step counting, seed graph shape, and safe LLM parsing.
2. The read-only progress API exposes Explore destination fields.
3. Dummy automation completes a live dynamic quest through `Talk -> Explore -> Kill -> ReturnToNpc -> Choice -> Complete`.
4. No GM command or write API is used for live Explore completion.
5. Existing dynamic quest party E2E remains passing with the new graph shape.
