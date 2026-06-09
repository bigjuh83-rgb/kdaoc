# Dynamic Quest Graph Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first deterministic Dynamic Quest Graph Engine so starter dynamic quests can run as `Talk -> Kill -> ReturnToNpc -> Choice -> Complete` while preserving the existing single-kill quest flow and dummy E2E behavior.

**Architecture:** Add graph model classes beside the existing runtime, keep legacy fields as compatibility data, and teach `DynamicQuestRuntimeService` to materialize legacy quests into graph nodes. Runtime progression remains deterministic; LLM output is not executed yet. Read-only progress snapshots become the canonical test and dummy observation surface.

**Tech Stack:** C#/.NET GameServer, NUnit unit tests in `Tests/UnitTests/WorldAI`, existing Python dummy clients for E2E verification, existing ASP.NET minimal API routes.

---

## File Structure

- Create `GameServer/WorldAI/DynamicQuestGraph.cs`
  - Holds graph enums and data classes only: node type, edge condition, objective payload, reward definition, node, edge, choice.
- Modify `GameServer/WorldAI/DynamicQuestRuntimeService.cs`
  - Keeps quest storage and runtime handlers.
  - Adds graph validation, compatibility materialization, node progression, reward step bonus, and richer progress snapshot.
- Modify `GameServer/WorldAI/DynamicQuestSeedService.cs`
  - Builds starter realm graph quests while preserving legacy `TargetName` and `TargetCount`.
- Create `Tests/UnitTests/WorldAI/UT_DynamicQuestRuntimeService.cs`
  - Focused runtime unit tests for graph validation, compatibility, kill progression, return node, choice, completion, and snapshot shape.
- Modify `Tests/UnitTests/WorldAI/UT_DynamicQuestSeedService.cs`
  - Keeps existing seed tests and adds graph-shape assertions for deterministic seed quests.
- Modify `tools/behavior-dummy-client.py`
  - Adds optional graph progress observation helpers only if E2E needs them; existing dynamic quest return flow must continue to work.
- Modify `tools/test_behavior_player_follow.py`
  - Adds small tests for graph progress parsing if dummy code changes.
- Modify `docs/kdaoc-dynamic-quest-runtime.md`
  - Documents graph progress API, v1 node types, and deterministic starter graph shape.

## Task 1: Add Graph Model Types

**Files:**
- Create: `GameServer/WorldAI/DynamicQuestGraph.cs`
- Modify: `GameServer/WorldAI/DynamicQuestRuntimeService.cs`
- Test: `Tests/UnitTests/WorldAI/UT_DynamicQuestRuntimeService.cs`

- [ ] **Step 1: Write failing graph model tests**

Create `Tests/UnitTests/WorldAI/UT_DynamicQuestRuntimeService.cs`:

```csharp
using System.Linq;
using DOL.GS.ServerProperties;
using DOL.GS.WorldAI;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_DynamicQuestRuntimeService
    {
        [SetUp]
        public void SetUp()
        {
            Properties.KDAOC_DYNAMIC_QUEST_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_MAX_ACTIVE_PER_PLAYER = 1;
            Properties.KDAOC_DYNAMIC_QUEST_MAX_ACTIVE_PER_NPC = 3;
            Properties.KDAOC_DYNAMIC_QUEST_MAX_KILL_COUNT = 20;
            Properties.KDAOC_DYNAMIC_QUEST_REWARD_XP_MULTIPLIER = 1.0;
            Properties.KDAOC_DYNAMIC_QUEST_REWARD_MONEY_MULTIPLIER = 1.0;
            DynamicQuestRuntimeService.Instance.ClearAll();
        }

        [TearDown]
        public void TearDown()
        {
            DynamicQuestRuntimeService.Instance.ClearAll();
            Properties.KDAOC_DYNAMIC_QUEST_ENABLED = false;
        }

        [Test]
        public void NormalizeQuestForTest_MaterializesLegacyKillQuestAsGraph()
        {
            DynamicQuestDefinition quest = LegacyQuest();

            DynamicQuestDefinition normalized = DynamicQuestRuntimeService.Instance.NormalizeQuestForTest(quest);

            Assert.Multiple(() =>
            {
                Assert.That(normalized.GraphVersion, Is.EqualTo(1));
                Assert.That(normalized.Nodes.Select(node => node.Type), Is.EqualTo(new[]
                {
                    DynamicQuestNodeType.Kill,
                    DynamicQuestNodeType.ReturnToNpc,
                    DynamicQuestNodeType.Complete
                }));
                Assert.That(normalized.StartNodeId, Is.EqualTo("kill"));
                Assert.That(normalized.Nodes.Single(node => node.Id == "kill").Objective.TargetName, Is.EqualTo("black wolf pup"));
                Assert.That(normalized.Nodes.Single(node => node.Id == "kill").Objective.TargetCount, Is.EqualTo(2));
            });
        }

        private static DynamicQuestDefinition LegacyQuest()
        {
            return new DynamicQuestDefinition
            {
                Id = "quest-legacy",
                Title = "검은 늑대 새끼 처치",
                OfferText = "도와주겠습니까?",
                ProgressText = "검은 늑대 새끼를 처치하세요.",
                FinishText = "고맙습니다.",
                StartNpcInternalId = "seed-npc-1",
                StartNpcName = "Brother Penric",
                StartRegionId = 1,
                TargetName = "black wolf pup",
                TargetCount = 2,
                MinLevel = 1,
                MaxLevel = 5
            };
        }
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec /home/bigjuh/.dotnet/dotnet test Tests/Tests.csproj -c Debug --no-restore --filter UT_DynamicQuestRuntimeService
```

Expected: FAIL because `DynamicQuestNodeType`, graph fields, and `NormalizeQuestForTest` do not exist.

- [ ] **Step 3: Add graph data classes**

Create `GameServer/WorldAI/DynamicQuestGraph.cs`:

```csharp
using System;
using System.Collections.Generic;

namespace DOL.GS.WorldAI
{
    public enum DynamicQuestNodeType
    {
        Talk,
        Kill,
        ReturnToNpc,
        Choice,
        Complete,
        Fail
    }

    public enum DynamicQuestEdgeCondition
    {
        Always,
        ObjectiveComplete,
        ChoiceSelected,
        PlayerDied,
        TimedOut,
        PartySizeAtLeast,
        WorldSignal
    }

    public sealed class DynamicQuestChoice
    {
        public string Id { get; set; } = string.Empty;
        public string Label { get; set; } = string.Empty;
        public string Text { get; set; } = string.Empty;
    }

    public sealed class DynamicQuestObjective
    {
        public string TargetName { get; set; } = string.Empty;
        public int TargetCount { get; set; } = 1;
        public int MinLevel { get; set; } = 1;
        public int MaxLevel { get; set; } = 50;
        public ushort RegionId { get; set; }
        public bool AllowGroupCredit { get; set; }
        public string NpcInternalId { get; set; } = string.Empty;
        public string NpcName { get; set; } = string.Empty;
        public IList<DynamicQuestChoice> Choices { get; set; } = Array.Empty<DynamicQuestChoice>();
    }

    public sealed class DynamicQuestEdge
    {
        public string ToNodeId { get; set; } = string.Empty;
        public DynamicQuestEdgeCondition Condition { get; set; } = DynamicQuestEdgeCondition.Always;
        public string ConditionValue { get; set; } = string.Empty;
        public int Priority { get; set; }
    }

    public sealed class DynamicQuestNode
    {
        public string Id { get; set; } = string.Empty;
        public DynamicQuestNodeType Type { get; set; }
        public string Title { get; set; } = string.Empty;
        public string Text { get; set; } = string.Empty;
        public DynamicQuestObjective Objective { get; set; } = new();
        public IList<DynamicQuestEdge> Edges { get; set; } = Array.Empty<DynamicQuestEdge>();
    }

    public sealed class DynamicQuestRewardDefinition
    {
        public double XpMultiplier { get; set; } = 1.0;
        public double MoneyMultiplier { get; set; } = 1.0;
        public double StepBonusMultiplier { get; set; } = 1.0;
        public double PartyBonusMultiplier { get; set; } = 1.0;
        public string ChoiceBonusKey { get; set; } = string.Empty;
    }
}
```

- [ ] **Step 4: Add graph fields and compatibility materialization**

Modify `DynamicQuestDefinition` in `GameServer/WorldAI/DynamicQuestRuntimeService.cs`:

```csharp
public int GraphVersion { get; set; } = 1;
public string StartNodeId { get; set; } = string.Empty;
public IList<DynamicQuestNode> Nodes { get; set; } = Array.Empty<DynamicQuestNode>();
public DynamicQuestRewardDefinition Reward { get; set; } = new();
public IList<string> Tags { get; set; } = Array.Empty<string>();
```

Add this method in `DynamicQuestRuntimeService`:

```csharp
internal DynamicQuestDefinition NormalizeQuestForTest(DynamicQuestDefinition quest)
{
    return NormalizeQuest(quest);
}

private static DynamicQuestDefinition NormalizeQuest(DynamicQuestDefinition quest)
{
    if (quest == null)
        return null;

    if (quest.Nodes != null && quest.Nodes.Count > 0)
        return quest;

    quest.GraphVersion = Math.Max(1, quest.GraphVersion);
    quest.StartNodeId = "kill";
    quest.Nodes = new List<DynamicQuestNode>
    {
        new()
        {
            Id = "kill",
            Type = DynamicQuestNodeType.Kill,
            Title = quest.Title,
            Text = quest.ProgressText,
            Objective = new DynamicQuestObjective
            {
                TargetName = quest.TargetName,
                TargetCount = quest.TargetCount,
                MinLevel = quest.MinLevel,
                MaxLevel = quest.MaxLevel,
                RegionId = quest.StartRegionId
            },
            Edges = new[]
            {
                new DynamicQuestEdge { ToNodeId = "return", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
            }
        },
        new()
        {
            Id = "return",
            Type = DynamicQuestNodeType.ReturnToNpc,
            Title = "보고",
            Text = $"{quest.StartNpcName}에게 돌아가세요.",
            Objective = new DynamicQuestObjective
            {
                NpcInternalId = quest.StartNpcInternalId,
                NpcName = quest.StartNpcName,
                RegionId = quest.StartRegionId
            },
            Edges = new[]
            {
                new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
            }
        },
        new()
        {
            Id = "complete",
            Type = DynamicQuestNodeType.Complete,
            Title = "완료",
            Text = quest.FinishText
        }
    };

    return quest;
}
```

- [ ] **Step 5: Run model test to verify it passes**

Run the same `dotnet test` command. Expected: PASS for `NormalizeQuestForTest_MaterializesLegacyKillQuestAsGraph`.

- [ ] **Step 6: Commit**

```powershell
git add GameServer/WorldAI/DynamicQuestGraph.cs GameServer/WorldAI/DynamicQuestRuntimeService.cs Tests/UnitTests/WorldAI/UT_DynamicQuestRuntimeService.cs
git commit -m "feat: add dynamic quest graph model"
```

## Task 2: Graph Validation

**Files:**
- Modify: `GameServer/WorldAI/DynamicQuestRuntimeService.cs`
- Test: `Tests/UnitTests/WorldAI/UT_DynamicQuestRuntimeService.cs`

- [ ] **Step 1: Add failing validation tests**

Append to `UT_DynamicQuestRuntimeService`:

```csharp
[Test]
public void AddQuest_RejectsGraphWithMissingEdgeTarget()
{
    DynamicQuestDefinition quest = LegacyQuest();
    quest.StartNodeId = "start";
    quest.Nodes = new[]
    {
        new DynamicQuestNode
        {
            Id = "start",
            Type = DynamicQuestNodeType.Talk,
            Title = "시작",
            Text = "시작합니다.",
            Objective = new DynamicQuestObjective
            {
                NpcInternalId = "seed-npc-1",
                NpcName = "Brother Penric",
                RegionId = 1
            },
            Edges = new[] { new DynamicQuestEdge { ToNodeId = "missing", Condition = DynamicQuestEdgeCondition.ObjectiveComplete } }
        },
        new DynamicQuestNode { Id = "complete", Type = DynamicQuestNodeType.Complete, Title = "완료", Text = "완료" }
    };

    DynamicQuestResult result = DynamicQuestRuntimeService.Instance.AddQuest(quest);

    Assert.Multiple(() =>
    {
        Assert.That(result.Success, Is.False);
        Assert.That(result.Message, Does.Contain("edge target"));
    });
}

[Test]
public void AddQuest_AcceptsValidTalkKillReturnChoiceCompleteGraph()
{
    DynamicQuestDefinition quest = GraphQuest();

    DynamicQuestResult result = DynamicQuestRuntimeService.Instance.AddQuest(quest);

    Assert.Multiple(() =>
    {
        Assert.That(result.Success, Is.True);
        Assert.That(DynamicQuestRuntimeService.Instance.GetQuests(), Has.Count.EqualTo(1));
    });
}

private static DynamicQuestDefinition GraphQuest()
{
    DynamicQuestDefinition quest = LegacyQuest();
    quest.Id = "quest-graph";
    quest.StartNodeId = "talk";
    quest.Nodes = new[]
    {
        new DynamicQuestNode
        {
            Id = "talk",
            Type = DynamicQuestNodeType.Talk,
            Title = "부탁",
            Text = "마을 주변의 흔적을 확인해 주세요.",
            Objective = new DynamicQuestObjective { NpcInternalId = "seed-npc-1", NpcName = "Brother Penric", RegionId = 1 },
            Edges = new[] { new DynamicQuestEdge { ToNodeId = "kill", Condition = DynamicQuestEdgeCondition.ObjectiveComplete } }
        },
        new DynamicQuestNode
        {
            Id = "kill",
            Type = DynamicQuestNodeType.Kill,
            Title = "위협 제거",
            Text = "검은 늑대 새끼를 처치하세요.",
            Objective = new DynamicQuestObjective { TargetName = "black wolf pup", TargetCount = 1, MinLevel = 1, MaxLevel = 5, RegionId = 1 },
            Edges = new[] { new DynamicQuestEdge { ToNodeId = "return", Condition = DynamicQuestEdgeCondition.ObjectiveComplete } }
        },
        new DynamicQuestNode
        {
            Id = "return",
            Type = DynamicQuestNodeType.ReturnToNpc,
            Title = "보고",
            Text = "Brother Penric에게 돌아가세요.",
            Objective = new DynamicQuestObjective { NpcInternalId = "seed-npc-1", NpcName = "Brother Penric", RegionId = 1 },
            Edges = new[] { new DynamicQuestEdge { ToNodeId = "choice", Condition = DynamicQuestEdgeCondition.ObjectiveComplete } }
        },
        new DynamicQuestNode
        {
            Id = "choice",
            Type = DynamicQuestNodeType.Choice,
            Title = "결정",
            Text = "어떻게 마무리하시겠습니까?",
            Objective = new DynamicQuestObjective
            {
                Choices = new[]
                {
                    new DynamicQuestChoice { Id = "safe", Label = "마을 안전을 우선한다", Text = "마을 안전을 우선한다." },
                    new DynamicQuestChoice { Id = "followup", Label = "더 큰 위협을 추적한다", Text = "더 큰 위협을 추적한다." }
                }
            },
            Edges = new[]
            {
                new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "safe", Priority = 0 },
                new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "followup", Priority = 1 }
            }
        },
        new DynamicQuestNode { Id = "complete", Type = DynamicQuestNodeType.Complete, Title = "완료", Text = "고맙습니다." }
    };
    return quest;
}
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec /home/bigjuh/.dotnet/dotnet test Tests/Tests.csproj -c Debug --no-restore --filter UT_DynamicQuestRuntimeService
```

Expected: missing-edge test currently passes incorrectly or valid graph fails because graph validation is incomplete.

- [ ] **Step 3: Implement graph validation**

Extend `Validate(DynamicQuestDefinition quest)` in `DynamicQuestRuntimeService.cs` with:

```csharp
DynamicQuestDefinition normalized = NormalizeQuest(quest);
IList<DynamicQuestNode> nodes = normalized.Nodes ?? Array.Empty<DynamicQuestNode>();
if (nodes.Count == 0)
{
    errors.Add("graph has no nodes");
    return errors;
}

HashSet<string> nodeIds = new(StringComparer.OrdinalIgnoreCase);
foreach (DynamicQuestNode node in nodes)
{
    if (string.IsNullOrWhiteSpace(node.Id))
        errors.Add("graph node id is empty");
    else if (!nodeIds.Add(node.Id))
        errors.Add($"duplicate graph node id: {node.Id}");

    if (string.IsNullOrWhiteSpace(node.Title) || node.Title.Length > 80)
        errors.Add($"graph node title is invalid: {node.Id}");
    if ((node.Text ?? string.Empty).Length > 500)
        errors.Add($"graph node text is too long: {node.Id}");
}

if (string.IsNullOrWhiteSpace(normalized.StartNodeId) || !nodeIds.Contains(normalized.StartNodeId))
    errors.Add("graph start node is missing");

if (!nodes.Any(node => node.Type is DynamicQuestNodeType.Complete or DynamicQuestNodeType.Fail))
    errors.Add("graph terminal node is missing");

foreach (DynamicQuestNode node in nodes)
{
    if (node.Type is not DynamicQuestNodeType.Complete and not DynamicQuestNodeType.Fail &&
        (node.Edges == null || node.Edges.Count == 0))
    {
        errors.Add($"graph non-terminal node has no edge: {node.Id}");
    }

    foreach (DynamicQuestEdge edge in node.Edges ?? Array.Empty<DynamicQuestEdge>())
    {
        if (string.IsNullOrWhiteSpace(edge.ToNodeId) || !nodeIds.Contains(edge.ToNodeId))
            errors.Add($"graph edge target is missing: {node.Id}->{edge.ToNodeId}");
    }

    ValidateNodeObjective(errors, node);
}
```

Add helper:

```csharp
private static void ValidateNodeObjective(List<string> errors, DynamicQuestNode node)
{
    DynamicQuestObjective objective = node.Objective ?? new DynamicQuestObjective();
    switch (node.Type)
    {
        case DynamicQuestNodeType.Kill:
            if (string.IsNullOrWhiteSpace(objective.TargetName))
                errors.Add($"kill node target is missing: {node.Id}");
            if (objective.TargetCount < 1 || objective.TargetCount > Math.Max(1, Properties.KDAOC_DYNAMIC_QUEST_MAX_KILL_COUNT))
                errors.Add($"kill node target count is invalid: {node.Id}");
            break;
        case DynamicQuestNodeType.Talk:
        case DynamicQuestNodeType.ReturnToNpc:
            if (string.IsNullOrWhiteSpace(objective.NpcInternalId))
                errors.Add($"npc node target is missing: {node.Id}");
            break;
        case DynamicQuestNodeType.Choice:
            if (objective.Choices == null || objective.Choices.Count < 1)
                errors.Add($"choice node has no choices: {node.Id}");
            break;
    }
}
```

- [ ] **Step 4: Run validation tests**

Run the same `dotnet test` command. Expected: all `UT_DynamicQuestRuntimeService` tests pass.

- [ ] **Step 5: Commit**

```powershell
git add GameServer/WorldAI/DynamicQuestRuntimeService.cs Tests/UnitTests/WorldAI/UT_DynamicQuestRuntimeService.cs
git commit -m "feat: validate dynamic quest graphs"
```

## Task 3: Extend Progress Snapshot Shape

**Files:**
- Modify: `GameServer/WorldAI/DynamicQuestRuntimeService.cs`
- Test: `Tests/UnitTests/WorldAI/UT_DynamicQuestRuntimeService.cs`

- [ ] **Step 1: Add failing snapshot test**

Append:

```csharp
[Test]
public void ProgressSnapshot_IncludesGraphNodeState()
{
    DynamicQuestRuntimeService.Instance.AddQuest(GraphQuest());
    DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
        playerKey: "DummyQuest001",
        questId: "quest-graph",
        currentNodeId: "kill",
        completedNodeIds: new[] { "talk" },
        nodeCounters: new System.Collections.Generic.Dictionary<string, int> { ["kill"] = 0 });

    DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);
    DynamicQuestProgressItem item = snapshot.Active.Single();

    Assert.Multiple(() =>
    {
        Assert.That(item.CurrentNodeId, Is.EqualTo("kill"));
        Assert.That(item.CurrentNodeType, Is.EqualTo(DynamicQuestNodeType.Kill));
        Assert.That(item.CurrentObjective.TargetName, Is.EqualTo("black wolf pup"));
        Assert.That(item.CompletedNodeIds, Is.EqualTo(new[] { "talk" }));
        Assert.That(item.Nodes.Select(node => node.Id), Does.Contain("choice"));
    });
}
```

- [ ] **Step 2: Run test to verify failure**

Run the `UT_DynamicQuestRuntimeService` filter. Expected: FAIL because snapshot fields and `RecordGraphProgressForTest` do not exist.

- [ ] **Step 3: Add progress and snapshot fields**

Modify `DynamicQuestProgress`:

```csharp
public string CurrentNodeId { get; set; } = string.Empty;
public Dictionary<string, int> NodeCounters { get; set; } = new(StringComparer.OrdinalIgnoreCase);
public HashSet<string> CompletedNodeIds { get; set; } = new(StringComparer.OrdinalIgnoreCase);
public Dictionary<string, string> ChoiceHistory { get; set; } = new(StringComparer.OrdinalIgnoreCase);
public bool Failed { get; set; }
public bool Completed { get; set; }
public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
```

Modify `DynamicQuestProgressItem`:

```csharp
public string CurrentNodeId { get; set; } = string.Empty;
public DynamicQuestNodeType CurrentNodeType { get; set; }
public DynamicQuestObjective CurrentObjective { get; set; } = new();
public IList<DynamicQuestNode> Nodes { get; set; } = Array.Empty<DynamicQuestNode>();
public IList<string> CompletedNodeIds { get; set; } = Array.Empty<string>();
public IList<DynamicQuestChoice> Choices { get; set; } = Array.Empty<DynamicQuestChoice>();
public bool Failed { get; set; }
```

Add test helper:

```csharp
internal void RecordGraphProgressForTest(
    string playerKey,
    string questId,
    string currentNodeId,
    IEnumerable<string> completedNodeIds,
    Dictionary<string, int> nodeCounters)
{
    lock (m_lock)
    {
        if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
        {
            progressList = new List<DynamicQuestProgress>();
            m_playerProgress[playerKey] = progressList;
        }

        progressList.Add(new DynamicQuestProgress
        {
            QuestId = questId,
            CurrentNodeId = currentNodeId,
            CompletedNodeIds = new HashSet<string>(completedNodeIds ?? Array.Empty<string>(), StringComparer.OrdinalIgnoreCase),
            NodeCounters = nodeCounters ?? new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase)
        });
    }
}
```

When building `DynamicQuestProgressItem`, normalize quest, resolve current node, and set graph fields:

```csharp
DynamicQuestDefinition normalizedQuest = NormalizeQuest(quest);
DynamicQuestNode currentNode = GetCurrentNode(normalizedQuest, progress);
active.Add(new DynamicQuestProgressItem
{
    QuestId = progress.QuestId,
    Title = normalizedQuest.Title,
    StartNpcName = normalizedQuest.StartNpcName,
    StartRegionId = normalizedQuest.StartRegionId,
    TargetName = normalizedQuest.TargetName,
    TargetCount = normalizedQuest.TargetCount,
    Count = progress.Count,
    IsComplete = progress.IsComplete || progress.Completed,
    AcceptedAt = progress.AcceptedAt,
    CurrentNodeId = currentNode?.Id ?? string.Empty,
    CurrentNodeType = currentNode?.Type ?? DynamicQuestNodeType.Kill,
    CurrentObjective = currentNode?.Objective ?? new DynamicQuestObjective(),
    Nodes = normalizedQuest.Nodes.ToList(),
    CompletedNodeIds = progress.CompletedNodeIds.OrderBy(id => id).ToList(),
    Choices = currentNode?.Type == DynamicQuestNodeType.Choice
        ? (currentNode.Objective?.Choices ?? Array.Empty<DynamicQuestChoice>()).ToList()
        : Array.Empty<DynamicQuestChoice>(),
    Failed = progress.Failed
});
```

Add helper:

```csharp
private static DynamicQuestNode GetCurrentNode(DynamicQuestDefinition quest, DynamicQuestProgress progress)
{
    string nodeId = string.IsNullOrWhiteSpace(progress.CurrentNodeId) ? quest.StartNodeId : progress.CurrentNodeId;
    return (quest.Nodes ?? Array.Empty<DynamicQuestNode>())
        .FirstOrDefault(node => string.Equals(node.Id, nodeId, StringComparison.OrdinalIgnoreCase));
}
```

- [ ] **Step 4: Run snapshot test**

Run the `UT_DynamicQuestRuntimeService` filter. Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add GameServer/WorldAI/DynamicQuestRuntimeService.cs Tests/UnitTests/WorldAI/UT_DynamicQuestRuntimeService.cs
git commit -m "feat: expose dynamic quest graph progress"
```

## Task 4: Implement Graph Runtime Progression

**Files:**
- Modify: `GameServer/WorldAI/DynamicQuestRuntimeService.cs`
- Test: `Tests/UnitTests/WorldAI/UT_DynamicQuestRuntimeService.cs`

- [ ] **Step 1: Add failing progression tests**

Append:

```csharp
[Test]
public void RecordKillProgressForTest_AdvancesKillNodeToReturnNode()
{
    DynamicQuestRuntimeService.Instance.AddQuest(GraphQuest());
    DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
        "DummyQuest001",
        "quest-graph",
        "kill",
        new[] { "talk" },
        new System.Collections.Generic.Dictionary<string, int>());

    bool advanced = DynamicQuestRuntimeService.Instance.RecordKillProgressForTest(
        "DummyQuest001",
        "black wolf pup",
        1,
        1);

    DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();

    Assert.Multiple(() =>
    {
        Assert.That(advanced, Is.True);
        Assert.That(item.CurrentNodeId, Is.EqualTo("return"));
        Assert.That(item.CompletedNodeIds, Does.Contain("kill"));
    });
}

[Test]
public void RecordNpcInteractionForTest_AdvancesReturnNodeToChoiceNode()
{
    DynamicQuestRuntimeService.Instance.AddQuest(GraphQuest());
    DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
        "DummyQuest001",
        "quest-graph",
        "return",
        new[] { "talk", "kill" },
        new System.Collections.Generic.Dictionary<string, int>());

    bool advanced = DynamicQuestRuntimeService.Instance.RecordNpcInteractionForTest(
        "DummyQuest001",
        "seed-npc-1",
        1);

    DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();

    Assert.Multiple(() =>
    {
        Assert.That(advanced, Is.True);
        Assert.That(item.CurrentNodeId, Is.EqualTo("choice"));
        Assert.That(item.Choices.Select(choice => choice.Id), Is.EqualTo(new[] { "safe", "followup" }));
    });
}

[Test]
public void SelectChoiceForTest_AdvancesChoiceToComplete()
{
    DynamicQuestRuntimeService.Instance.AddQuest(GraphQuest());
    DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
        "DummyQuest001",
        "quest-graph",
        "choice",
        new[] { "talk", "kill", "return" },
        new System.Collections.Generic.Dictionary<string, int>());

    bool advanced = DynamicQuestRuntimeService.Instance.SelectChoiceForTest("DummyQuest001", "quest-graph", "safe");

    DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();

    Assert.Multiple(() =>
    {
        Assert.That(advanced, Is.True);
        Assert.That(item.CurrentNodeId, Is.EqualTo("complete"));
        Assert.That(item.IsComplete, Is.True);
    });
}
```

- [ ] **Step 2: Run tests to verify failure**

Run the runtime test filter. Expected: FAIL because progression helpers do not exist.

- [ ] **Step 3: Implement node advancement helpers**

Add internal helpers:

```csharp
internal bool RecordKillProgressForTest(string playerKey, string enemyName, int enemyLevel, ushort regionId)
{
    lock (m_lock)
        return RecordKillProgressLocked(playerKey, enemyName, enemyLevel, regionId, out _);
}

internal bool RecordNpcInteractionForTest(string playerKey, string npcInternalId, ushort regionId)
{
    lock (m_lock)
        return RecordNpcInteractionLocked(playerKey, npcInternalId, regionId, out _);
}

internal bool SelectChoiceForTest(string playerKey, string questId, string choiceId)
{
    lock (m_lock)
        return SelectChoiceLocked(playerKey, questId, choiceId, out _);
}
```

Add core helpers:

```csharp
private bool RecordKillProgressLocked(string playerKey, string enemyName, int enemyLevel, ushort regionId, out DynamicQuestDefinition matchingQuest)
{
    matchingQuest = null;
    if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
        return false;

    foreach (DynamicQuestProgress progress in progressList)
    {
        if (!TryGetQuest(progress.QuestId, out DynamicQuestDefinition quest))
            continue;

        DynamicQuestDefinition normalized = NormalizeQuest(quest);
        DynamicQuestNode node = GetCurrentNode(normalized, progress);
        if (node?.Type != DynamicQuestNodeType.Kill)
            continue;

        DynamicQuestObjective objective = node.Objective ?? new DynamicQuestObjective();
        if (!NameMatches(enemyName, objective.TargetName))
            continue;
        if (objective.RegionId != 0 && objective.RegionId != regionId)
            continue;
        if (enemyLevel < objective.MinLevel || enemyLevel > objective.MaxLevel)
            continue;

        int count = progress.NodeCounters.TryGetValue(node.Id, out int existing) ? existing : 0;
        count = Math.Min(objective.TargetCount, count + 1);
        progress.NodeCounters[node.Id] = count;
        progress.Count = count;
        progress.UpdatedAt = DateTime.UtcNow;

        if (count >= objective.TargetCount)
            AdvanceFromNode(progress, normalized, node, DynamicQuestEdgeCondition.ObjectiveComplete, string.Empty);

        matchingQuest = normalized;
        return true;
    }

    return false;
}
```

Add `RecordNpcInteractionLocked`, `SelectChoiceLocked`, and `AdvanceFromNode`:

```csharp
private bool RecordNpcInteractionLocked(string playerKey, string npcInternalId, ushort regionId, out DynamicQuestDefinition matchingQuest)
{
    matchingQuest = null;
    if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
        return false;

    foreach (DynamicQuestProgress progress in progressList)
    {
        if (!TryGetQuest(progress.QuestId, out DynamicQuestDefinition quest))
            continue;

        DynamicQuestDefinition normalized = NormalizeQuest(quest);
        DynamicQuestNode node = GetCurrentNode(normalized, progress);
        if (node == null || node.Type is not (DynamicQuestNodeType.Talk or DynamicQuestNodeType.ReturnToNpc))
            continue;

        DynamicQuestObjective objective = node.Objective ?? new DynamicQuestObjective();
        if (!string.Equals(objective.NpcInternalId, npcInternalId, StringComparison.OrdinalIgnoreCase))
            continue;
        if (objective.RegionId != 0 && objective.RegionId != regionId)
            continue;

        AdvanceFromNode(progress, normalized, node, DynamicQuestEdgeCondition.ObjectiveComplete, string.Empty);
        matchingQuest = normalized;
        return true;
    }

    return false;
}

private bool SelectChoiceLocked(string playerKey, string questId, string choiceId, out DynamicQuestDefinition matchingQuest)
{
    matchingQuest = null;
    if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
        return false;

    DynamicQuestProgress progress = progressList.FirstOrDefault(item => string.Equals(item.QuestId, questId, StringComparison.OrdinalIgnoreCase));
    if (progress == null || !TryGetQuest(progress.QuestId, out DynamicQuestDefinition quest))
        return false;

    DynamicQuestDefinition normalized = NormalizeQuest(quest);
    DynamicQuestNode node = GetCurrentNode(normalized, progress);
    if (node?.Type != DynamicQuestNodeType.Choice)
        return false;

    if (!(node.Objective?.Choices ?? Array.Empty<DynamicQuestChoice>()).Any(choice => string.Equals(choice.Id, choiceId, StringComparison.OrdinalIgnoreCase)))
        return false;

    progress.ChoiceHistory[node.Id] = choiceId;
    AdvanceFromNode(progress, normalized, node, DynamicQuestEdgeCondition.ChoiceSelected, choiceId);
    matchingQuest = normalized;
    return true;
}

private static void AdvanceFromNode(DynamicQuestProgress progress, DynamicQuestDefinition quest, DynamicQuestNode node, DynamicQuestEdgeCondition condition, string conditionValue)
{
    progress.CompletedNodeIds.Add(node.Id);
    DynamicQuestEdge edge = (node.Edges ?? Array.Empty<DynamicQuestEdge>())
        .OrderBy(item => item.Priority)
        .FirstOrDefault(item =>
            item.Condition == condition &&
            (string.IsNullOrWhiteSpace(item.ConditionValue) ||
             string.Equals(item.ConditionValue, conditionValue, StringComparison.OrdinalIgnoreCase)));

    if (edge == null)
        return;

    progress.CurrentNodeId = edge.ToNodeId;
    DynamicQuestNode next = quest.Nodes.FirstOrDefault(item => string.Equals(item.Id, edge.ToNodeId, StringComparison.OrdinalIgnoreCase));
    if (next?.Type == DynamicQuestNodeType.Complete)
    {
        progress.Completed = true;
        progress.IsComplete = true;
    }
    if (next?.Type == DynamicQuestNodeType.Fail)
    {
        progress.Failed = true;
    }
    progress.UpdatedAt = DateTime.UtcNow;
}
```

- [ ] **Step 4: Run progression tests**

Run runtime test filter. Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add GameServer/WorldAI/DynamicQuestRuntimeService.cs Tests/UnitTests/WorldAI/UT_DynamicQuestRuntimeService.cs
git commit -m "feat: progress dynamic quest graph nodes"
```

## Task 5: Wire Real Runtime Handlers To Graph Progress

**Files:**
- Modify: `GameServer/WorldAI/DynamicQuestRuntimeService.cs`
- Test: `Tests/UnitTests/WorldAI/UT_DynamicQuestRuntimeService.cs`

- [ ] **Step 1: Add handler compatibility tests**

Append:

```csharp
[Test]
public void LegacyProgressSnapshotStillReportsTargetFields()
{
    DynamicQuestRuntimeService.Instance.AddQuest(LegacyQuest());
    DynamicQuestRuntimeService.Instance.RecordProgressForTest("DummyQuest001", "quest-legacy", 1, false);

    DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();

    Assert.Multiple(() =>
    {
        Assert.That(item.TargetName, Is.EqualTo("black wolf pup"));
        Assert.That(item.TargetCount, Is.EqualTo(2));
        Assert.That(item.CurrentNodeId, Is.EqualTo("kill"));
        Assert.That(item.CurrentNodeType, Is.EqualTo(DynamicQuestNodeType.Kill));
    });
}
```

- [ ] **Step 2: Run tests**

Expected: PASS after previous tasks. This guards compatibility before handler edits.

- [ ] **Step 3: Update `AcceptQuest`**

In `AcceptQuest`, replace the progress add with graph-aware progress:

```csharp
DynamicQuestDefinition normalizedQuest = NormalizeQuest(quest);
DynamicQuestProgress progress = new()
{
    QuestId = normalizedQuest.Id,
    CurrentNodeId = normalizedQuest.StartNodeId
};
progressList.Add(progress);
DynamicQuestNode startNode = GetCurrentNode(normalizedQuest, progress);
if (startNode?.Type == DynamicQuestNodeType.Talk && IsNpcObjective(startNode, npc))
    AdvanceFromNode(progress, normalizedQuest, startNode, DynamicQuestEdgeCondition.ObjectiveComplete, string.Empty);
```

Add helper:

```csharp
private static bool IsNpcObjective(DynamicQuestNode node, GameNPC npc)
{
    DynamicQuestObjective objective = node?.Objective;
    return objective != null &&
           objective.RegionId == npc.CurrentRegionID &&
           string.Equals(objective.NpcInternalId, npc.InternalID ?? string.Empty, StringComparison.OrdinalIgnoreCase);
}
```

- [ ] **Step 4: Update `HandleEnemyKilled`**

Replace old `GetProgressForKill` count logic with:

```csharp
string playerKey = GetPlayerKey(player);
DynamicQuestDefinition quest;
bool advanced;
lock (m_lock)
    advanced = RecordKillProgressLocked(playerKey, enemy.Name, (int)enemy.Level, enemy.CurrentRegionID, out quest);

if (!advanced || quest == null)
    return;

DynamicQuestProgressSnapshot snapshot = GetProgressSnapshot(player);
DynamicQuestProgressItem item = snapshot.Active.FirstOrDefault(active => active.QuestId == quest.Id);
if (item == null)
    return;

if (item.IsComplete)
    player.Out.SendMessage($"{quest.Title}: 완료되었습니다. {quest.StartNpcName}에게 돌아가세요.", eChatType.CT_Important, eChatLoc.CL_SystemWindow);
else
    player.Out.SendMessage($"{quest.Title}: {DescribeCurrentObjective(item)}", eChatType.CT_System, eChatLoc.CL_SystemWindow);
```

Add `DescribeCurrentObjective`:

```csharp
private static string DescribeCurrentObjective(DynamicQuestProgressItem item)
{
    if (item.CurrentNodeType == DynamicQuestNodeType.Kill)
        return $"{item.Count}/{Math.Max(1, item.CurrentObjective.TargetCount)}";
    return item.CurrentObjective?.NpcName ?? item.CurrentNodeId;
}
```

- [ ] **Step 5: Update `HandleNpcInteract` for active graph nodes**

Before offering a new quest, if active progress exists for this NPC:

```csharp
DynamicQuestProgress active = GetProgressForStartNpc(player, npc);
if (active != null && TryGetQuest(active.QuestId, out DynamicQuestDefinition activeQuest))
{
    DynamicQuestDefinition normalizedQuest = NormalizeQuest(activeQuest);
    DynamicQuestNode node = GetCurrentNode(normalizedQuest, active);

    if (node?.Type == DynamicQuestNodeType.Choice)
    {
        ShowChoiceDialog(player, npc, normalizedQuest, active, node);
        return true;
    }

    if (node?.Type is DynamicQuestNodeType.Talk or DynamicQuestNodeType.ReturnToNpc && IsNpcObjective(node, npc))
    {
        AdvanceFromNode(active, normalizedQuest, node, DynamicQuestEdgeCondition.ObjectiveComplete, string.Empty);
        node = GetCurrentNode(normalizedQuest, active);
    }

    if (node?.Type == DynamicQuestNodeType.Complete || active.Completed || active.IsComplete)
    {
        FinishQuest(player, npc, normalizedQuest, active);
        return true;
    }

    npc.SayTo(player, node?.Text ?? normalizedQuest.ProgressText);
    return true;
}
```

Add `ShowChoiceDialog`:

```csharp
private void ShowChoiceDialog(GamePlayer player, GameNPC npc, DynamicQuestDefinition quest, DynamicQuestProgress progress, DynamicQuestNode node)
{
    IList<DynamicQuestChoice> choices = node.Objective?.Choices ?? Array.Empty<DynamicQuestChoice>();
    DynamicQuestChoice acceptChoice = choices.FirstOrDefault() ?? new DynamicQuestChoice { Id = "default", Label = "계속한다" };
    DynamicQuestChoice declineChoice = choices.Skip(1).FirstOrDefault() ?? acceptChoice;
    player.Out.SendCustomDialog($"{node.Text}\n\n수락: {acceptChoice.Label}\n거절: {declineChoice.Label}", (dialogPlayer, response) =>
    {
        string selected = response == 0x01 ? acceptChoice.Id : declineChoice.Id;
        lock (m_lock)
            SelectChoiceLocked(GetPlayerKey(dialogPlayer), quest.Id, selected, out _);
        FinishQuest(dialogPlayer, npc, quest, progress);
    });
}
```

- [ ] **Step 6: Run runtime and seed tests**

Run:

```powershell
wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec /home/bigjuh/.dotnet/dotnet test Tests/Tests.csproj -c Debug --no-restore --filter "DynamicQuest"
```

Expected: PASS for runtime and seed tests.

- [ ] **Step 7: Commit**

```powershell
git add GameServer/WorldAI/DynamicQuestRuntimeService.cs Tests/UnitTests/WorldAI/UT_DynamicQuestRuntimeService.cs
git commit -m "feat: wire dynamic quest graph runtime"
```

## Task 6: Seed Starter Realm Graph Quests

**Files:**
- Modify: `GameServer/WorldAI/DynamicQuestSeedService.cs`
- Modify: `Tests/UnitTests/WorldAI/UT_DynamicQuestSeedService.cs`

- [ ] **Step 1: Add failing seed graph assertion**

In `Seed_DeterministicDefinitionCreatesOneRuntimeQuest`, add:

```csharp
Assert.That(quest.Nodes.Select(node => node.Type), Is.EqualTo(new[]
{
    DynamicQuestNodeType.Talk,
    DynamicQuestNodeType.Kill,
    DynamicQuestNodeType.ReturnToNpc,
    DynamicQuestNodeType.Choice,
    DynamicQuestNodeType.Complete
}));
Assert.That(quest.StartNodeId, Is.EqualTo("talk"));
Assert.That(quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Choice).Objective.Choices.Select(choice => choice.Id),
    Is.EqualTo(new[] { "safe", "followup" }));
```

- [ ] **Step 2: Run seed tests to verify failure**

Run:

```powershell
wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec /home/bigjuh/.dotnet/dotnet test Tests/Tests.csproj -c Debug --no-restore --filter DynamicQuestSeed
```

Expected: FAIL because seeded quests still have no graph nodes.

- [ ] **Step 3: Update `BuildQuest` in `DynamicQuestSeedService.cs`**

After constructing legacy fields, add graph fields:

```csharp
StartNodeId = "talk",
Nodes = BuildStarterGraph(npc, definition),
Reward = new DynamicQuestRewardDefinition
{
    XpMultiplier = 1.0,
    MoneyMultiplier = 1.0,
    StepBonusMultiplier = 0.25,
    PartyBonusMultiplier = 1.0
},
Tags = new[] { $"region:{definition.RegionId}", $"target:{definition.TargetName}" }
```

Add helper:

```csharp
private static IList<DynamicQuestNode> BuildStarterGraph(DynamicQuestSeedNpc npc, DynamicQuestSeedDefinition definition)
{
    return new[]
    {
        new DynamicQuestNode
        {
            Id = "talk",
            Type = DynamicQuestNodeType.Talk,
            Title = "부탁",
            Text = $"{definition.TargetName} 때문에 이 근처가 어수선합니다.",
            Objective = new DynamicQuestObjective { NpcInternalId = npc.InternalID, NpcName = npc.Name, RegionId = npc.RegionId },
            Edges = new[] { new DynamicQuestEdge { ToNodeId = "kill", Condition = DynamicQuestEdgeCondition.ObjectiveComplete } }
        },
        new DynamicQuestNode
        {
            Id = "kill",
            Type = DynamicQuestNodeType.Kill,
            Title = "위협 제거",
            Text = $"{definition.TargetName} {definition.Count}마리를 처치하세요.",
            Objective = new DynamicQuestObjective
            {
                TargetName = definition.TargetName,
                TargetCount = definition.Count,
                MinLevel = definition.MinLevel,
                MaxLevel = definition.MaxLevel,
                RegionId = TargetRegion(npc, definition)
            },
            Edges = new[] { new DynamicQuestEdge { ToNodeId = "return", Condition = DynamicQuestEdgeCondition.ObjectiveComplete } }
        },
        new DynamicQuestNode
        {
            Id = "return",
            Type = DynamicQuestNodeType.ReturnToNpc,
            Title = "보고",
            Text = $"{npc.Name}에게 돌아가세요.",
            Objective = new DynamicQuestObjective { NpcInternalId = npc.InternalID, NpcName = npc.Name, RegionId = npc.RegionId },
            Edges = new[] { new DynamicQuestEdge { ToNodeId = "choice", Condition = DynamicQuestEdgeCondition.ObjectiveComplete } }
        },
        new DynamicQuestNode
        {
            Id = "choice",
            Type = DynamicQuestNodeType.Choice,
            Title = "결정",
            Text = "이 일을 어떻게 마무리하시겠습니까?",
            Objective = new DynamicQuestObjective
            {
                Choices = new[]
                {
                    new DynamicQuestChoice { Id = "safe", Label = "마을 안전을 우선한다", Text = "마을 안전을 우선한다." },
                    new DynamicQuestChoice { Id = "followup", Label = "더 큰 위협을 추적한다", Text = "더 큰 위협을 추적한다." }
                }
            },
            Edges = new[]
            {
                new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "safe", Priority = 0 },
                new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "followup", Priority = 1 }
            }
        },
        new DynamicQuestNode
        {
            Id = "complete",
            Type = DynamicQuestNodeType.Complete,
            Title = "완료",
            Text = "좋습니다. 덕분에 이 지역이 한결 안전해졌습니다."
        }
    };
}
```

- [ ] **Step 4: Run seed tests**

Expected: `DynamicQuestSeed` tests pass.

- [ ] **Step 5: Commit**

```powershell
git add GameServer/WorldAI/DynamicQuestSeedService.cs Tests/UnitTests/WorldAI/UT_DynamicQuestSeedService.cs
git commit -m "feat: seed starter dynamic quest graphs"
```

## Task 7: Dummy E2E And Read-Only Graph Verification

**Files:**
- Modify: `tools/behavior-dummy-client.py`
- Modify: `tools/test_behavior_player_follow.py`

- [ ] **Step 1: Add graph progress parsing tests only if dummy changes are needed**

If the current dummy flow can finish the choice custom dialog with existing `accept_custom_dialog`, no Python code change is needed. If graph verification needs parsing, add:

```python
def test_dynamic_quest_progress_snapshot_reads_current_node():
    snapshot = {
        "active": [
            {
                "questId": "quest-graph",
                "currentNodeId": "kill",
                "currentNodeType": "Kill",
                "currentObjective": {"targetName": "black wolf pup", "targetCount": 1},
                "completedNodeIds": ["talk"],
                "choices": [],
            }
        ]
    }

    active = behavior.dynamic_quest_progress_active_items(snapshot)

    self.assertEqual(active[0]["currentNodeId"], "kill")
```

- [ ] **Step 2: Run Python tests**

Run:

```powershell
wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m py_compile tools/behavior-dummy-client.py tools/test_behavior_player_follow.py
wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_headless_custom_dialog tools.test_behavior_player_follow.BehaviorPlayerFollowTests.test_dynamic_quest_return_disconnect_is_not_completed_before_verification
```

Expected: PASS.

- [ ] **Step 3: Restart server with standard script**

Run:

```powershell
.\start-main-server-visible.bat
.\check-main-server-fast.bat
```

Expected: TCP `10300`, UDP `10400`, DB `3306` OK.

- [ ] **Step 4: Confirm seed status**

Run:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:5000/api/world/dynamic-quests/seed/status' -TimeoutSec 5 | ConvertTo-Json -Depth 8
Invoke-RestMethod -Uri 'http://127.0.0.1:5000/api/world/dynamic-quests' -TimeoutSec 5 | ConvertTo-Json -Depth 10
```

Expected:

- `created` is `3` on a fresh server seed.
- Quest objects include graph `nodes`.
- Starter regions include `1`, `100`, and `200`.

- [ ] **Step 5: Run dynamic quest E2E**

Use the existing deterministic Albion flow, with a new output directory:

```powershell
wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 tools/behavior-dummy-client.py --host 127.0.0.1 --port 10300 --api-port 5000 --accounts test-output/dynamic-quest-flow-8/accounts.csv --concurrency 1 --rounds 1 --hold 150 --safe-exit-max-seconds 90 --hunter --combat --player-level 1 --min-target-level 1 --max-target-level 1 --target-selection nearest --target-pool 1 --max-target-distance 6500 --target-timeout 70 --combat-interval 1.5 --require-target-name 'black wolf pup' --stop-after-required-target-removed --no-required-target-removed-api-confirm --dynamic-quest-return-after-required-target --dynamic-quest-return-npc-name 'Brother Penric' --dynamic-quest-return-home 518850,494050,3352 --dynamic-quest-return-complete-wait 2 --startup-service-npc-name 'Brother Penric' --startup-service-scan-seconds 2 --startup-service-interact --startup-service-accept-dialog --movement-speed 240 --smooth-move-interval 0.20 --encounter-log-interval 1 --metrics-csv test-output/dynamic-quest-graph-flow-1/metrics.csv --combat-csv test-output/dynamic-quest-graph-flow-1/combat.csv --report-md test-output/dynamic-quest-graph-flow-1/report.md --encounter-log 'test-output/dynamic-quest-graph-flow-1/encounters-{username}-{round}.jsonl' --verbose
```

Expected:

- `dummy run completed: ok=1/1`.
- `target_removed` >= `1`.
- `dynamic_quest_return_interact` exists.
- `dynamic_quest_complete_verified` exists.
- Read-only progress API returns `active: []`.

- [ ] **Step 6: Commit dummy changes if any**

If Python files changed:

```powershell
git add tools/behavior-dummy-client.py tools/test_behavior_player_follow.py
git commit -m "test: verify dynamic quest graph dummy flow"
```

If Python files did not change, skip commit.

## Task 8: Documentation And Final Verification

**Files:**
- Modify: `docs/kdaoc-dynamic-quest-runtime.md`

- [ ] **Step 1: Update runtime docs**

Add a section:

```markdown
## Quest Graph v1

Dynamic quests now support graph-backed progression. Legacy kill quests are materialized into a compatibility graph, and deterministic starter quests use:

`Talk -> Kill -> ReturnToNpc -> Choice -> Complete`

The read-only progress API exposes `currentNodeId`, `currentNodeType`, `currentObjective`, `completedNodeIds`, `nodes`, and pending `choices`. Dummy tests should use this API for observation only and must not use GM commands for state changes.

LLM generation is not a runtime authority. LLM output may fill quest titles, text, and validated graph templates only after server-side graph validation passes.
```

- [ ] **Step 2: Run full focused verification**

Run:

```powershell
wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m py_compile tools/behavior-dummy-client.py tools/headless-daoc-client.py tools/test_behavior_player_follow.py tools/test_headless_custom_dialog.py
wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec python3 -m unittest tools.test_headless_custom_dialog tools.test_behavior_player_follow.BehaviorPlayerFollowTests.test_dynamic_quest_return_disconnect_is_not_completed_before_verification tools.test_behavior_player_follow.BehaviorPlayerFollowTests.test_melee_out_of_range_feedback_blocks_attack_until_retry_stop_distance
wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec /home/bigjuh/.dotnet/dotnet test Tests/Tests.csproj -c Debug --no-restore --filter "DynamicQuest"
wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec /home/bigjuh/.dotnet/dotnet build GameServer/GameServer.csproj -c Debug --no-restore -v:q -clp:ErrorsOnly
.\check-main-server-fast.bat
```

Expected:

- Python tests PASS.
- DynamicQuest .NET tests PASS.
- GameServer build has `0 Error(s)`.
- Server check reports TCP `10300`, UDP `10400`, DB `3306` OK.

- [ ] **Step 3: Commit docs**

```powershell
git add docs/kdaoc-dynamic-quest-runtime.md
git commit -m "docs: document dynamic quest graph runtime"
```

- [ ] **Step 4: Final report**

Report:

- Graph node types implemented.
- Existing kill quest compatibility preserved.
- Starter realm quests are graph-backed.
- Dynamic quest E2E result path and metrics.
- Focused test/build commands and outcomes.
- Any known deferred items: Explore/Collect/Escort/BossKill, item rewards, reputation, monster-growth mutation, LLM graph generation.

## Self-Review

Spec coverage:

- Quest graph model: Tasks 1 and 2.
- Player progress graph state: Task 3.
- Accept/NPC/Kill/Choice/Complete runtime: Tasks 4 and 5.
- Seeded starter graph: Task 6.
- Read-only API graph shape: Task 3 and Task 7.
- Dummy E2E: Task 7.
- Documentation and final verification: Task 8.
- LLM role and monster-growth hooks are explicitly deferred in the spec and represented as tags/validated graph extension points.

Placeholder scan:

- This plan contains no incomplete-marker text or vague future work markers.

Type consistency:

- `DynamicQuestNodeType`, `DynamicQuestEdgeCondition`, `DynamicQuestObjective`, `DynamicQuestNode`, `DynamicQuestEdge`, `DynamicQuestChoice`, and `DynamicQuestRewardDefinition` are defined in Task 1 and reused consistently in later tasks.
