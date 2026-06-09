# Dynamic Quest LLM Story Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured story quality scoring, immersive narrative scenes, journal text, and safe NPC emotion/emote presentation to generated dynamic quest stories.

**Architecture:** Keep quest runtime state server-authoritative. Store generated story metadata on `dynamic_quest_template`, deserialize it into `DynamicQuestTemplate`, expose redacted read-only snapshots, and play cosmetic narrative/presentation beats from runtime interaction points without advancing progress.

**Tech Stack:** C#/.NET, DOL database `DataObject` tables, `System.Text.Json`, NUnit unit tests, existing dynamic quest runtime/seed services.

---

## File Map

- Modify `CoreDatabase/Tables/DbDynamicQuestTemplate.cs`: add `StoryQualityJson`, `StoryNarrativeJson`, and `StoryPresentationJson`.
- Modify `GameServer/WorldAI/DynamicQuestStoryService.cs`: add quality/narrative/presentation DTOs, parsing, validation, scoring, prompt/schema updates, and provider comparison support only through service APIs.
- Modify `GameServer/WorldAI/DynamicQuestTemplateService.cs`: round-trip narrative/presentation JSON between DB rows and `DynamicQuestTemplate`.
- Modify `GameServer/WorldAI/DynamicQuestSeedService.cs`: expose snapshot redaction, save/copy new JSON fields, prune with safety/structure tie-breakers.
- Modify `GameServer/WorldAI/DynamicQuestRuntimeService.cs`: trigger read-only/cosmetic scene and NPC emote beats at accept, NPC interaction, choice, and completion paths.
- Modify `GameServer/API/WorldAI/WorldAiRoutes.cs`: include new story-config fields.
- Modify `GameServer/serverproperty/ServerProperties.cs`: add comparison/min-score config fields.
- Modify tests under `Tests/UnitTests/WorldAI`: add and extend story, template, seed/cache, runtime tests.
- Modify `docs/kdaoc-dynamic-quest-runtime.md`: document quality/narrative/presentation cache metadata and redaction behavior.

## Task 1: Quality DTO And Scoring

**Files:**
- Modify: `GameServer/WorldAI/DynamicQuestStoryService.cs`
- Test: `Tests/UnitTests/WorldAI/UT_DynamicQuestStoryService.cs`

- [ ] **Step 1: Write failing quality tests**

Add tests that call new test hooks:

```csharp
[Test]
public void EvaluateQuality_ReturnsBreakdownForImmersiveStory()
{
    DynamicQuestStoryText story = Story();
    story.NarrativeScenes = new[]
    {
        new DynamicQuestNarrativeScene
        {
            NodeId = "talk",
            SceneType = "Intro",
            Title = "숲의 숨죽임",
            Body = "해가 지자 숲 가장자리의 울타리가 한 번 더 찢겼습니다.\n\n마을 사람들은 {{target}}의 울음이 전보다 가까워졌다고 말합니다.",
            JournalEntry = "Brother Penric은 숲 가장자리의 변화가 마을로 번질까 두려워했다.",
            Mood = "ominous",
            RevealPolicy = "FirstSeenOnly"
        }
    };
    story.PresentationBeats = new[]
    {
        new DynamicQuestPresentationBeat
        {
            NodeId = "talk",
            Trigger = "OnNpcInteract",
            Speaker = "StartNpc",
            Text = "저 숲이 오늘은 숨을 죽인 것 같군요.",
            Emotion = "fear",
            Emote = "Shiver"
        }
    };

    DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForTest(Request(), story);

    Assert.Multiple(() =>
    {
        Assert.That(quality.TotalScore, Is.GreaterThanOrEqualTo(80));
        Assert.That(quality.NarrativeScore, Is.GreaterThan(0));
        Assert.That(quality.PresentationScore, Is.GreaterThan(0));
        Assert.That(quality.Reasons, Does.Contain("narrative_scene"));
        Assert.That(quality.Reasons, Does.Contain("presentation_beat"));
    });
}

[Test]
public void ValidatePresentation_StripsRawEmoteIdsAndUnsafeTriggers()
{
    DynamicQuestStoryText story = Story();
    story.PresentationBeats = new[]
    {
        new DynamicQuestPresentationBeat
        {
            NodeId = "talk",
            Trigger = "RunCommand",
            Speaker = "StartNpc",
            Text = "spawn now",
            Emotion = "fear",
            Emote = "999"
        }
    };

    DynamicQuestStoryText sanitized = DynamicQuestStoryService.SanitizeStoryForTest(Request(), story);
    DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForTest(Request(), sanitized);

    Assert.Multiple(() =>
    {
        Assert.That(sanitized.PresentationBeats, Is.Empty);
        Assert.That(quality.SafetyScore, Is.LessThan(15));
    });
}
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec /home/bigjuh/.dotnet/dotnet test Tests/Tests.csproj -c Debug --no-restore --filter "FullyQualifiedName~UT_DynamicQuestStoryService"
```

Expected: compile failure because `DynamicQuestNarrativeScene`, `DynamicQuestPresentationBeat`, `DynamicQuestStoryQuality`, and the test hooks do not exist.

- [ ] **Step 3: Implement DTOs and deterministic evaluator**

Add public sealed DTOs near `DynamicQuestStoryText`. Extend `DynamicQuestStoryText` with:

```csharp
public IList<DynamicQuestNarrativeScene> NarrativeScenes { get; set; } = Array.Empty<DynamicQuestNarrativeScene>();
public IList<DynamicQuestPresentationBeat> PresentationBeats { get; set; } = Array.Empty<DynamicQuestPresentationBeat>();
public DynamicQuestStoryQuality Quality { get; set; } = DynamicQuestStoryQuality.Empty;
```

Implement `EvaluateQualityDetails`, `SanitizeStory`, allowlists for node ids, scene types, reveal policies, moods, triggers, speakers, emotions, and emotes. Keep the old `EvaluateQuality` as `EvaluateQualityDetails(...).TotalScore`.

- [ ] **Step 4: Run tests and verify GREEN**

Run the same `dotnet test` filter. Expected: story service tests pass.

## Task 2: JSON Parsing, Prompt, And Schema

**Files:**
- Modify: `GameServer/WorldAI/DynamicQuestStoryService.cs`
- Test: `Tests/UnitTests/WorldAI/UT_DynamicQuestStoryService.cs`

- [ ] **Step 1: Write failing parse/schema tests**

Add tests:

```csharp
[Test]
public void ParseStoryJson_ReadsNarrativeAndPresentationArrays()
{
    string json = """
    {
      "title": "숲속의 작은 위협",
      "offer": "Brother Penric이 {{target}} 처치를 부탁합니다.",
      "progress": "{{target}} 흔적을 따라가야 합니다.",
      "finish": "{{target}} 위협이 사라졌습니다.",
      "target": "black wolf pup",
      "count": 1,
      "min_level": 1,
      "max_level": 5,
      "narrative_scenes": [
        {
          "node_id": "talk",
          "scene_type": "Intro",
          "title": "숲의 숨죽임",
          "body": "숲 가장자리의 울타리가 찢겼습니다.\n\n마을 사람들은 밤마다 울음소리를 듣습니다.",
          "journal_entry": "Brother Penric은 숲의 변화가 마을로 번질까 걱정했다.",
          "mood": "ominous",
          "reveal_policy": "FirstSeenOnly"
        }
      ],
      "presentation_beats": [
        {
          "node_id": "talk",
          "trigger": "OnNpcInteract",
          "speaker": "StartNpc",
          "text": "저 소리를 들으셨습니까?",
          "emotion": "fear",
          "emote": "Shiver"
        }
      ]
    }
    """;

    DynamicQuestStoryText parsed = DynamicQuestStoryService.ParseStoryJsonForTest(json, Request());

    Assert.Multiple(() =>
    {
        Assert.That(parsed.NarrativeScenes, Has.Count.EqualTo(1));
        Assert.That(parsed.PresentationBeats, Has.Count.EqualTo(1));
        Assert.That(parsed.NarrativeScenes[0].Body, Does.Contain("울타리"));
    });
}

[Test]
public void OpenAiSchema_IncludesNarrativeAndPresentationFields()
{
    string payload = DynamicQuestStoryService.BuildOpenAiRequestJsonForTest("model-test", Request());

    Assert.Multiple(() =>
    {
        Assert.That(payload, Does.Contain("narrative_scenes"));
        Assert.That(payload, Does.Contain("presentation_beats"));
        Assert.That(payload, Does.Contain("Do not output raw emote ids"));
    });
}
```

- [ ] **Step 2: Run tests and verify RED**

Expected: missing `BuildOpenAiRequestJsonForTest` or schema fields.

- [ ] **Step 3: Implement parser/schema/prompt**

Parse `narrative_scenes` and `presentation_beats`, sanitize arrays, cap lengths, and add schema properties. Add test hook:

```csharp
internal static string BuildOpenAiRequestJsonForTest(string model, DynamicQuestStoryRequest request)
{
    return JsonSerializer.Serialize(BuildOpenAiRequest(model, request));
}
```

- [ ] **Step 4: Run tests and verify GREEN**

Run story service tests.

## Task 3: DB And Template Round Trip

**Files:**
- Modify: `CoreDatabase/Tables/DbDynamicQuestTemplate.cs`
- Modify: `GameServer/WorldAI/DynamicQuestTemplateService.cs`
- Test: `Tests/UnitTests/WorldAI/UT_DynamicQuestTemplateService.cs`

- [ ] **Step 1: Write failing round-trip test**

Add to `TemplateRepository_RoundTripsStoryWithoutConcreteBinding` or a new test:

```csharp
[Test]
public void TemplateRepository_RoundTripsQualityNarrativeAndPresentationJson()
{
    DynamicQuestTemplate template = StoryTemplate();
    template.StoryQualityJson = "{\"totalScore\":91}";
    template.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"title\":\"숲의 숨죽임\"}]";
    template.StoryPresentationJson = "[{\"nodeId\":\"talk\",\"emotion\":\"fear\",\"emote\":\"Shiver\"}]";
    FakeDynamicQuestTemplateRepository repository = new();

    repository.Add(DynamicQuestTemplateService.ToRowForTest(template));
    DynamicQuestTemplate loaded = DynamicQuestTemplateService.FromRowForTest(repository.GetActive().Single());

    Assert.Multiple(() =>
    {
        Assert.That(loaded.StoryQualityJson, Does.Contain("totalScore"));
        Assert.That(loaded.StoryNarrativeJson, Does.Contain("숲의 숨죽임"));
        Assert.That(loaded.StoryPresentationJson, Does.Contain("Shiver"));
    });
}
```

- [ ] **Step 2: Run tests and verify RED**

Expected: missing properties.

- [ ] **Step 3: Implement row/template fields**

Add string fields/properties to `DbDynamicQuestTemplate` with `[DataElement(AllowDbNull = false)]`. Add matching properties to `DynamicQuestTemplate`, then map them in `ToRow` and `FromRow`.

- [ ] **Step 4: Run tests and verify GREEN**

Run template service tests.

## Task 4: Seed Cache Snapshot And Pruning

**Files:**
- Modify: `GameServer/WorldAI/DynamicQuestSeedService.cs`
- Test: `Tests/UnitTests/WorldAI/UT_DynamicQuestSeedService.cs`

- [ ] **Step 1: Write failing snapshot/prune tests**

Extend `StoryCacheSnapshot_ReadsScoredTemplatesAndBranchTagsWithoutMutation`:

```csharp
repository.Rows["story-high-branch"].StoryQualityJson = "{\"totalScore\":94,\"safetyScore\":15,\"structureScore\":15}";
repository.Rows["story-high-branch"].StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"title\":\"숲의 숨죽임\",\"body\":\"숨겨진 본문\",\"journalEntry\":\"숨겨진 저널\",\"mood\":\"ominous\"}]";
repository.Rows["story-high-branch"].StoryPresentationJson = "[{\"nodeId\":\"talk\",\"text\":\"숨겨진 대사\",\"emotion\":\"fear\",\"emote\":\"Shiver\"}]";
```

Assert `includeText:false` hides body/journal/text but returns mood/emotion/emote; `includeText:true` returns text.

Add prune test with equal `StoryQualityScore` but one row has `safetyScore:0`; unsafe row is pruned first.

- [ ] **Step 2: Run tests and verify RED**

Expected: missing snapshot fields.

- [ ] **Step 3: Implement snapshot DTO fields and redaction**

Add `StoryQualityJson`, `StoryNarrative`, and `StoryPresentation` fields to cache item DTO. Deserialize into safe summary DTOs; redact narrative `Body`/`JournalEntry` and presentation `Text` unless `includeText=true`.

- [ ] **Step 4: Implement pruning tie-breaker**

Add helpers that parse `StoryQualityJson` for `safetyScore` and `structureScore`. Order cleanup by invalid/safety/structure before total score.

- [ ] **Step 5: Run tests and verify GREEN**

Run seed service tests.

## Task 5: Runtime Cosmetic Playback

**Files:**
- Modify: `GameServer/WorldAI/DynamicQuestRuntimeService.cs`
- Test: `Tests/UnitTests/WorldAI/UT_DynamicQuestRuntimeService.cs`

- [ ] **Step 1: Write failing runtime tests**

Add tests that build a graph quest with `StoryNarrativeJson` and `StoryPresentationJson`, accept/interact through test hooks, then assert timeline contains scene/journal entries and presentation beat events. Use fake runtime hooks if direct packet verification is not possible.

Expected event names:

```text
narrative_scene
journal_entry
presentation_beat
```

- [ ] **Step 2: Run tests and verify RED**

Expected: timeline events do not exist.

- [ ] **Step 3: Implement cosmetic trigger helpers**

Add helpers:

```csharp
private void PlayNarrativeScene(GamePlayer player, DynamicQuestDefinition quest, string nodeId, string trigger)
private void PlayPresentationBeat(GamePlayer player, DynamicQuestDefinition quest, GameNPC npc, string nodeId, string trigger)
private static eEmote? ResolvePresentationEmote(string emotion, string emote)
```

Call these from acceptance, NPC interaction, choice display, explore completion, and completion paths. Do not advance graph state from these helpers.

- [ ] **Step 4: Run tests and verify GREEN**

Run runtime service tests.

## Task 6: Config And API

**Files:**
- Modify: `GameServer/serverproperty/ServerProperties.cs`
- Modify: `GameServer/API/WorldAI/WorldAiRoutes.cs`
- Modify: `docs/kdaoc-dynamic-quest-runtime.md`
- Test: `Tests/UnitTests/WorldAI/UT_DynamicQuestStoryService.cs`

- [ ] **Step 1: Write failing config/API assertions**

Use existing API route tests if available; otherwise add unit coverage for `FromProperties` and story config DTO if test seam exists. Expected fields:

```text
compareProvidersEnabled
compareMaxPerPrefill
minimumAcceptedStoryScore
```

- [ ] **Step 2: Add properties**

Add:

```csharp
[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_compare_providers_enabled", "KDAOC: Compare a limited number of local and Gemini story generations during prefill.", false)]
public static bool KDAOC_DYNAMIC_QUEST_STORY_COMPARE_PROVIDERS_ENABLED;

[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_compare_max_per_prefill", "KDAOC: Maximum provider comparison calls per story cache prefill pass.", 1)]
public static int KDAOC_DYNAMIC_QUEST_STORY_COMPARE_MAX_PER_PREFILL;

[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_minimum_score", "KDAOC: Minimum accepted generated story quality score. Zero stores all structurally valid safe stories.", 0)]
public static int KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE;
```

- [ ] **Step 3: Expose redacted config and docs**

Update story-config and docs without exposing keys.

- [ ] **Step 4: Run tests**

Run focused unit tests.

## Task 7: Verification

**Files:**
- Existing code and tests only.

- [ ] **Step 1: Run focused unit tests**

```powershell
wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec /home/bigjuh/.dotnet/dotnet test Tests/Tests.csproj -c Debug --no-restore --filter "FullyQualifiedName~UT_DynamicQuestStoryService|FullyQualifiedName~UT_DynamicQuestTemplateService|FullyQualifiedName~UT_DynamicQuestSeedService|FullyQualifiedName~UT_DynamicQuestRuntimeService"
```

Expected: all pass.

- [ ] **Step 2: Compile server**

```powershell
wsl --cd '/mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core' --exec /home/bigjuh/.dotnet/dotnet build GameServer/GameServer.csproj -c Debug --no-restore -v:q -clp:ErrorsOnly
```

Expected: build succeeds.

- [ ] **Step 3: Check visible server status**

Use the project standard:

```powershell
.\check-main-server-fast.bat
```

Expected: TCP/UDP/API/DB checks OK.

- [ ] **Step 4: Run dynamic quest dummy smoke**

Use the existing dynamic quest matrix runner without GM commands. Choose the same quick NPC smoke command that is currently passing in this workspace, with melee rotation default:

```powershell
python .\tools\run-dummy-dynamic-quest-matrix.py --matrix quick --party-sizes 1 --player-level 40 --min-target-level 1 --max-target-level 10
```

Expected: one dummy accepts through NPC/custom dialog, completes explore/kill/return/choice, no deaths, final inactive.

## Self-Review Notes

- Spec coverage: quality, narrative, presentation, cache redaction, pruning, config, runtime cosmetic playback, and tests are covered.
- No raw LLM control of graph, rewards, state, spawn, DB mutation, or raw emote ids is planned.
- The plan preserves legacy rows by treating missing JSON fields as empty metadata.
- The riskiest area is runtime packet/emote verification; tests should assert internal timeline events and rely on existing `GameLiving.Emote(eEmote)` integration for packet delivery.
