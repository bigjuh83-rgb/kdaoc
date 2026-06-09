# Dynamic Quest LLM Story Quality Design

## Goal

Dynamic quest story generation should move from "LLM text is cached" to a measurable story quality pipeline. The runtime quest must still be volatile and rebindable: story text can be stored in DB, but live NPCs, locations, targets, bindings, and active progress remain server-owned and may change on restart, seed tick, or world revision change.

This design improves story quality before adding more quest node types. The immediate target is not to let the LLM mutate the world. The target is to produce, score, cache, compare, observe, prune, and replace story templates in a way that steadily raises the quality of dynamic quests while preserving deterministic gameplay.

## Current State

The current system already has these foundations:

- `DynamicQuestStoryService` calls providers in configured order: `main-local`, `gemini`, `secondary-local`.
- Gemini defaults to `gemini-3.5-flash` and uses conservative server-side RPM/RPD guards.
- Story text is stored in `dynamic_quest_template` through `DbDynamicQuestTemplate`.
- Each row stores `StoryProvider`, `StoryModel`, `StoryQualityScore`, `StoryGeneratedAt`, and `StoryLastUsedAt`.
- Runtime binding is separate from story storage, so cached stories can be rebound to current world NPCs and targets.
- Cache prefill can derive extra `AutoAccept` candidates from current world monsters and mob-growth signals.
- Cache offers prefer starter-level, NPC-less rows first, then realm round-robin.
- Full-cache cleanup runs only after the Gemini daily reset delay/window and prunes low-score rows.
- `story-cache` and `story-config` APIs expose read-only operational state without revealing secrets.

The main gaps are:

- `StoryQualityScore` is a single opaque number. It is useful for sorting, but it does not explain why a story is good, which provider produced better text, whether the story is reusable after rebinding, or which templates should be replaced first when the cache is full.
- Existing generated story text is too flat for Skyrim-like pacing. It can describe a quest, but it does not yet provide longer scene prose, journal continuity, or emotional presentation at key steps.

## Chosen Approach

Add a server-side story quality evaluator and cache policy layer without changing quest runtime progression.

Rejected alternatives:

- LLM judge-only scoring: better taste, but it burns Gemini quota and makes tests nondeterministic.
- Provider tournament on every template: good comparison data, but too expensive under free quota and too slow for server startup.
- Rewrite the quest generator around full LLM graphs first: tempting, but risky while dummy E2E is still the source of truth.

The chosen approach keeps generation cheap and deterministic by default, then uses optional provider comparison only in controlled prefill batches.

## Story Quality Model

Introduce a structured evaluation object:

```text
DynamicQuestStoryQuality
```

Fields:

- `TotalScore`: `0..100`, still copied into `StoryQualityScore` for existing sorting.
- `StructureScore`: title, offer, progress, finish are present and valid.
- `KoreanScore`: natural Hangul, no English operational leakage.
- `ObjectiveScore`: text clearly matches the server objective, count, kill intent, and target placeholder.
- `ImmersionScore`: has a local reason, atmosphere, and consequence, not just "kill target".
- `NarrativeScore`: includes memorable scene prose, setup, stakes, discovery, return, and aftermath.
- `PresentationScore`: includes usable dialogue/emotion beats for NPC interactions without forcing runtime mutation.
- `RebindabilityScore`: uses `{{target}}` and avoids hardcoded coordinates, stale NPC ids, or concrete targets outside placeholders.
- `SafetyScore`: no command, SQL, reward, spawn, delete, key, API, or admin text.
- `DiversityScore`: avoids repeated generic phrases already common in active cache.
- `Reasons`: short machine-readable reason codes, for example `missing_finish`, `weak_immersion`, `target_not_placeholderized`.

The evaluator must be deterministic and unit-testable. It should not call an LLM. It can use simple text heuristics first, because the score is for cache ranking and operator visibility, not player-facing prose.

## Persistence

Keep `StoryQualityScore` as the indexed primary score.

Add one DB field:

```text
StoryQualityJson
```

This field stores the structured breakdown and reason codes. The C-phase implementation should not store score breakdown in `TagsJson`, because tags are already used for runtime binding, provider, model, branch, and world-signal metadata.

Add one presentation DB field:

```text
StoryPresentationJson
```

This field stores optional dialogue and emotion beats. It is separate from `StoryQualityJson` because it is player-facing story material, not operator scoring metadata.

Add one narrative DB field:

```text
StoryNarrativeJson
```

This field stores longer scene and journal material. It is separate from `OfferText`, `ProgressText`, and `FinishText` because those fields are short compatibility text used by existing quest flow. The narrative JSON gives the runtime richer prose without forcing every NPC interaction to become long.

Rows generated before this change remain valid:

- Missing `StoryQualityJson` means legacy score only.
- Missing `StoryPresentationJson` means the quest uses existing node text only.
- Missing `StoryNarrativeJson` means the quest uses existing short story text only.
- Snapshot APIs return an empty breakdown for old rows.
- Cleanup still works from `StoryQualityScore`.

## Narrative Scene Layer

Dynamic quests should support both fast gameplay text and immersive story text.

```text
DynamicQuestNarrativeScene
```

Fields:

- `NodeId`: stable graph node id such as `talk`, `explore`, `kill`, `return`, `choice`, or `complete`.
- `SceneType`: `Intro`, `Discovery`, `Threat`, `Return`, `Choice`, `Completion`, or `Aftermath`.
- `Title`: short scene title for custom text windows and read-only API.
- `Body`: 2 to 5 short Korean paragraphs. This is the immersive scene prose.
- `JournalEntry`: 1 to 3 Korean sentences suitable for a quest journal or timeline.
- `Mood`: controlled label such as `ominous`, `urgent`, `tragic`, `hopeful`, `grim`, `mysterious`, `relieved`, or `neutral`.
- `RevealPolicy`: `FirstSeenOnly`, `EveryInteraction`, or `ManualReviewOnly`.

Runtime behavior:

1. Short node text remains the default objective instruction.
2. Long scene text is shown only at key moments: acceptance, explore completion, return, choice, completion, or explicitly configured node entry.
3. The same scene should not spam the player repeatedly; `FirstSeenOnly` records that the player has seen it.
4. Journal entries are persisted with progress/timeline so a reconnecting player can still understand the quest.
5. NPC-less quests can still use scene text and journal entries, but skip NPC emote beats.

This layer is how the system gets more than short task text. The LLM can write a small story arc, while the server still owns location, target, rewards, state transitions, and cancellation on world revision changes.

Example shape:

```text
Intro: the NPC tells why the place matters and what changed.
Discovery: the player reaches the location and sees the consequence.
Threat: the target is framed as part of a local problem, not a generic kill count.
Return: the NPC reacts to what the player reports.
Completion: the local situation changes or remains uneasy.
Aftermath: journal note ties the quest to future dynamic offers.
```

## Dialogue And Emote Beats

Dynamic quests should support small directed moments during step transitions and NPC interactions:

```text
DynamicQuestPresentationBeat
```

Fields:

- `NodeId`: stable graph node id such as `talk`, `return`, `choice`, or `complete`.
- `Trigger`: `OnNodeEnter`, `OnNpcInteract`, `OnChoiceShown`, or `OnComplete`.
- `Speaker`: `StartNpc`, `TargetNpc`, `System`, or future `Companion`.
- `Text`: short Korean line rendered through the same placeholder rules as story text.
- `Emotion`: controlled label such as `fear`, `urgency`, `relief`, `anger`, `sorrow`, `suspicion`, `pride`, `caution`, `gratitude`, or `neutral`.
- `Emote`: optional safe alias chosen from an allowlist, not a raw numeric id.

Runtime behavior:

1. When a beat is triggered and the speaker NPC is present, the NPC uses `SayTo(player, text)` and then plays the mapped `eEmote`.
2. If the speaker is absent because the quest is NPC-less or the world was rebound, the server skips the NPC emote and may show only system text.
3. Only one presentation beat should play per interaction by default to avoid chat or animation spam.
4. Presentation beats never advance progress, grant rewards, spawn objects, change AI, or mutate the world.

The server owns emotion-to-emote mapping. The LLM may request `Emotion = fear`, but the server decides that this maps to a safe animation such as `Shiver`, `Cower`, or no emote depending on actor type and client support.

Initial allowlist:

```text
neutral -> no emote
fear -> Shiver
urgency -> Point
relief -> Smile
anger -> Angry
sorrow -> Cry
suspicion -> Ponder
pride -> Salute
caution -> No
gratitude -> Bow
celebration -> Cheer
```

This uses existing server support for `GameLiving.Emote(eEmote)` and NPC `SayTo(...)`. It should not introduce GM commands or custom client opcodes.

## Generation Flow

Story generation remains provider ordered:

```text
main-local -> gemini -> secondary-local
```

Operational policy:

- If the main local LLM is on, use it first.
- If main local fails or returns invalid JSON, use Gemini `gemini-3.5-flash`.
- If Gemini quota is exhausted or the API fails, use secondary local.
- Never block server startup on slow story generation.
- Unit tests use fake providers only.

After parsing a provider response:

1. Validate exact target/count/level fields.
2. Normalize JSON and placeholderize target text.
3. Evaluate story quality with the structured evaluator.
4. Reject stories with invalid structure or safety score `0`; otherwise store them with their computed score.
5. Validate optional narrative scenes against node, scene type, length, reveal policy, and safety rules.
6. Validate optional presentation beats against the safe trigger/speaker/emotion/emote allowlists.
7. Store provider, model, total score, breakdown JSON, narrative JSON, presentation JSON, and generated timestamp.

## Optional Provider Comparison

Provider comparison should be limited and quota-aware.

Add a mode for controlled prefill only:

```text
kdaoc_dynamic_quest_story_compare_providers_enabled = false
kdaoc_dynamic_quest_story_compare_max_per_prefill = 1
```

When enabled and budget allows:

1. Generate the same story request from the first available local provider.
2. Generate the same request from Gemini.
3. Score both deterministically.
4. Store the higher-scoring story.
5. Add metadata showing compared providers and scores.

This is not used for every quest. It is a sampling tool to help local models improve cache quality without exceeding Gemini limits.

## Cache Replacement Policy

Current full-cache pruning should stay anchored to Gemini daily reset time. The ranking should become:

1. Inactive or invalid story rows first.
2. Lower `SafetyScore` or invalid structure.
3. Lower `TotalScore`.
4. Lower `DiversityScore`.
5. Older `StoryLastUsedAt`.
6. Provider/model rows that are overrepresented when realm coverage is already balanced.

The C-phase implementation should at least add safety/structure tie-breakers to the existing low-total-score pruning. Diversity and provider/model overrepresentation are part of the scoring metadata and API visibility in this phase, but they do not have to drive pruning until a later cache-balancing pass.

When the cache has room after pruning, prefill should continue using the existing batch size and world candidate cap. It should not immediately spend the whole Gemini daily quota.

## APIs

Extend the read-only story cache item:

```json
{
  "storyQualityScore": 87,
  "storyQuality": {
    "structureScore": 15,
    "koreanScore": 15,
    "objectiveScore": 18,
    "immersionScore": 14,
    "narrativeScore": 12,
    "rebindabilityScore": 15,
    "safetyScore": 15,
    "presentationScore": 8,
    "diversityScore": 10,
    "reasons": ["strong_rebindability", "local_consequence"]
  }
}
```

`includeText=false` remains the default. Quality breakdown is safe to show because it contains no API keys and no full story body. Narrative scene bodies, journal entries, and presentation beat text are story text, so they are hidden unless `includeText=true`; mood, emotion labels, reveal policy, and emote aliases can be shown without text.

Extend `story-config` with:

- comparison enabled flag
- comparison max per prefill
- minimum accepted story score, default `0`

## Prompt Direction

Keep the JSON schema small, but improve the prompt requirements:

- Korean text must feel like an in-world quest, not an admin task.
- Every story should include a local cause and a consequence.
- Include optional narrative scenes for intro, discovery, return, and completion. These may be longer than objective text, but must remain concise enough for a game text window.
- Include journal entries that summarize what the player learned, not only what they must do next.
- When an NPC is involved, include short optional presentation beats with emotion labels for offer, return, and completion moments.
- Use `{{target}}` only for the actual target reference.
- Do not mention rewards, commands, database, scripts, spawning, deletion, or API keys.
- Do not hardcode coordinates or mutable runtime binding details.
- Do not output raw emote ids, packet names, opcodes, or arbitrary animation numbers.
- Keep offer/progress/finish short enough for game UI and dummy logs.

The prompt should not ask the LLM for graph nodes, rewards, completion, branching, or world mutation in this phase. Presentation beats are cosmetic only.

## Tests

Story service tests:

- High-quality Korean story receives a high score and structured reasons.
- Missing finish/progress fields lower structure score.
- English operational leakage lowers Korean/safety score.
- Missing `{{target}}` lowers rebindability and objective score.
- Forbidden command/reward/SQL terms lower safety score.
- Valid NPC dialogue/emotion beats raise presentation score.
- Valid immersive scene prose and journal entries raise narrative score.
- Unsafe, overly long, repetitive, or objective-contradicting narrative scenes lower score or are stripped.
- Raw emote ids, unknown emotions, or unsafe beat triggers are rejected or stripped.
- Gemini payload still uses `maxOutputTokens = 2048` and JSON response mode.
- Gemini default model remains `gemini-3.5-flash`.

Template persistence tests:

- `StoryQualityJson` round-trips through `DbDynamicQuestTemplate`.
- `StoryNarrativeJson` round-trips through `DbDynamicQuestTemplate`.
- `StoryPresentationJson` round-trips through `DbDynamicQuestTemplate`.
- Legacy rows without quality JSON still load with `StoryQualityScore`.
- Legacy rows without narrative JSON still bind and complete normally.
- Legacy rows without presentation JSON still bind and complete normally.
- Final quest tags still include provider/model/score.

Seed/cache tests:

- Prefill saves score breakdown with generated rows.
- Story cache snapshot returns quality breakdown without mutating rows.
- Story cache snapshot hides narrative body/journal text unless `includeText=true`.
- Story cache snapshot hides presentation text unless `includeText=true`.
- `includeText=false` still hides story text.
- Full cache pruning prefers invalid/unsafe/low-score rows after Gemini reset window.
- Provider comparison, if enabled, stores the higher-scoring fake-provider result and respects max comparison count.
- Provider comparison does not call Gemini when quota is exhausted.

E2E smoke:

- Existing NPC dynamic quest smoke still completes.
- Existing NPC-less AutoAccept smoke still completes.
- No GM command is used.
- Quality metadata appears in read-only API after generation.
- Narrative scene metadata appears in read-only API without body text by default.
- NPC offer/return/completion interactions can play a safe mapped emote without affecting completion.

## Non-Goals

This phase does not add LLM-owned quest graphs, new rewards, spawned entities, object collection, escorting, companion dialogue ownership, or live world mutation. It does not add a full quest journal UI in the game client; it stores and exposes journal entries through server progress/timeline/read-only APIs first. It also does not require a Gemini call in automated tests.

## Acceptance Criteria

The C-phase is complete when:

1. Story quality has a structured deterministic breakdown stored with new generated templates.
2. Existing `StoryQualityScore` sorting and cache pruning remain backward compatible.
3. Optional narrative scenes store longer scene prose and journal entries while preserving short objective text.
4. Optional presentation beats store NPC dialogue, emotion labels, and safe emote aliases without raw animation ids.
5. Read-only APIs expose quality metadata without exposing story text by default.
6. Gemini remains `gemini-3.5-flash`, quota-guarded, and optional behind fallback/comparison policy.
7. Unit tests prove scoring, persistence, snapshot behavior, pruning priority, narrative validation, presentation beat validation, and provider comparison guards.
8. Current dynamic quest dummy smoke paths still pass without GM commands.
