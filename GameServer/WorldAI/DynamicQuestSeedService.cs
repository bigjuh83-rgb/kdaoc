using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using DOL.AI.Brain;
using DOL.Database;
using DOL.GS.ServerProperties;

namespace DOL.GS.WorldAI
{
    public sealed class DynamicQuestSeedDefinition
    {
        public string StartNpcName { get; set; } = string.Empty;
        public ushort RegionId { get; set; }
        public string TargetName { get; set; } = string.Empty;
        public int Count { get; set; } = 1;
        public int MinLevel { get; set; } = 1;
        public int MaxLevel { get; set; } = 50;
        public DynamicQuestStartMode StartMode { get; set; } = DynamicQuestStartMode.NpcOffer;
        public string Trigger { get; set; } = string.Empty;
        public string StartSelector { get; set; } = string.Empty;
        public string TargetSelector { get; set; } = string.Empty;
        public string BranchWorldSignal { get; set; } = string.Empty;
    }

    public sealed class DynamicQuestSeedNpc
    {
        public string Name { get; set; } = string.Empty;
        public string RawName { get; set; } = string.Empty;
        public string InternalID { get; set; } = string.Empty;
        public ushort RegionId { get; set; }
        public int Level { get; set; }
        public int X { get; set; }
        public int Y { get; set; }
        public int Z { get; set; }
        public GameNPC SourceNpc { get; set; }
        public bool HasSourceNpcMetadata { get; set; }
        public eRealm SourceRealm { get; set; } = eRealm.None;
        public GameNPC.eFlags SourceFlags { get; set; }
        public bool SourceIsAlive { get; set; } = true;
        public string SourceTypeName { get; set; } = string.Empty;
        public int SourceAggroLevel { get; set; }
        public int SourceAggroRange { get; set; }
        public bool HasGrowthState { get; set; }
        public string GrowthStage { get; set; } = string.Empty;
        public int GrowthScore { get; set; }
        public int GrowthLevel { get; set; }
        public int GrowthEffectiveLevel { get; set; }
        public int GrowthPlayerKills { get; set; }
        public bool GrowthIsMutant { get; set; }
        public bool GrowthMutationPending { get; set; }
        public int NameGrowthThreatCount { get; set; }
        public int NameGrowthMaxScore { get; set; }
        public int NameGrowthMaxEffectiveLevel { get; set; }
        public int NameGrowthPlayerKills { get; set; }
    }

    public sealed class DynamicQuestSeedOptions
    {
        public const string LegacySingleRealmDefinitions = "Brother Penric|1|black wolf pup|1|1|5";
        public const string LegacyBalancedDefinitions =
            "Brother Penric|1|black wolf pup|1|1|5;Aud|100|young sveawolf|1|1|5;Ionhar|200|water beetle larva|1|1|5";
        public const string DefaultDeterministicDefinitions =
            "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer||mob-growth:killed:region:1;selector:town-npc|100|selector:hostile-near-start|1|1|5|NpcOffer||time-window:night;selector:town-npc|200|selector:hostile-near-start|1|1|5|NpcOffer||item-acquired";

        public bool Enabled { get; set; }
        public bool UseLlm { get; set; }
        public bool UseCodexCuratedStories { get; set; }
        public bool UseStoryCacheOffers { get; set; }
        public bool GenerateMissingStoriesInline { get; set; } = true;
        public bool PrefillStoryCacheInline { get; set; } = true;
        public string LlmSeed { get; set; } = string.Empty;
        public string WorldRevision { get; set; } = "default";
        public int MaxQuests { get; set; } = 3;
        public IList<DynamicQuestSeedDefinition> Definitions { get; set; } = Array.Empty<DynamicQuestSeedDefinition>();

        public static DynamicQuestSeedOptions FromProperties()
        {
            string rawDefinitions = Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_DEFINITIONS;
            IList<DynamicQuestSeedDefinition> definitions = ParseDefinitions(ResolveDefinitions(rawDefinitions));
            int maxQuests = Math.Max(1, Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_MAX_QUESTS);
            if (ShouldUseBalancedDefault(rawDefinitions) || IsBalancedDefaultDefinitions(definitions))
                maxQuests = Math.Max(maxQuests, definitions.Count);
            if (Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_USE_LLM &&
                Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_OFFER_ENABLED)
            {
                int storyCacheOfferSlots = Math.Max(0, Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_OFFER_MIN_SLOTS);
                maxQuests = Math.Max(maxQuests, definitions.Count + storyCacheOfferSlots);
            }

            return new DynamicQuestSeedOptions
            {
                Enabled = Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_ENABLED,
                UseLlm = Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_USE_LLM,
                UseCodexCuratedStories = !Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_USE_LLM,
                UseStoryCacheOffers = Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_OFFER_ENABLED,
                GenerateMissingStoriesInline = false,
                PrefillStoryCacheInline = false,
                LlmSeed = Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_LLM_SEED ?? string.Empty,
                WorldRevision = NormalizeWorldRevision(Properties.KDAOC_DYNAMIC_QUEST_WORLD_REVISION),
                MaxQuests = maxQuests,
                Definitions = definitions
            };
        }

        public static DynamicQuestSeedOptions DefaultForTests(string definitions)
        {
            return new DynamicQuestSeedOptions
            {
                Enabled = true,
                UseLlm = false,
                UseCodexCuratedStories = false,
                UseStoryCacheOffers = false,
                WorldRevision = "test",
                MaxQuests = 20,
                Definitions = ParseDefinitions(definitions)
            };
        }

        public static IList<DynamicQuestSeedDefinition> ParseDefinitions(string raw)
        {
            if (string.IsNullOrWhiteSpace(raw))
                return Array.Empty<DynamicQuestSeedDefinition>();

            List<DynamicQuestSeedDefinition> definitions = new();

            foreach (string entry in raw.Split(new[] { ';' }, StringSplitOptions.RemoveEmptyEntries))
            {
                string[] parts = entry.Split('|').Select(part => part.Trim()).ToArray();
                if (parts.Length < 3)
                    continue;

                ushort.TryParse(parts.ElementAtOrDefault(1), out ushort regionId);
                int count = ParseInt(parts.ElementAtOrDefault(3), 1);
                int minLevel = ParseInt(parts.ElementAtOrDefault(4), 1);
                int maxLevel = ParseInt(parts.ElementAtOrDefault(5), 50);
                DynamicQuestStartMode startMode = ParseStartMode(parts.ElementAtOrDefault(6));
                string branchWorldSignal = NormalizeBranchWorldSignal(parts.ElementAtOrDefault(8));

                if (maxLevel < minLevel)
                    maxLevel = minLevel;

                definitions.Add(new DynamicQuestSeedDefinition
                {
                    StartNpcName = parts[0],
                    RegionId = regionId,
                    TargetName = parts[2],
                    Count = Math.Max(1, count),
                    MinLevel = Math.Clamp(minLevel, 1, 50),
                    MaxLevel = Math.Clamp(maxLevel, 1, 50),
                    StartMode = startMode,
                    Trigger = parts.ElementAtOrDefault(7) ?? string.Empty,
                    StartSelector = SelectorToken(parts[0]),
                    TargetSelector = SelectorToken(parts[2]),
                    BranchWorldSignal = branchWorldSignal
                });
            }

            return definitions;
        }

        private static string NormalizeWorldRevision(string worldRevision)
        {
            string value = (worldRevision ?? string.Empty).Trim();
            return string.IsNullOrWhiteSpace(value) ? "default" : value;
        }

        private static string ResolveDefinitions(string raw)
        {
            string value = (raw ?? string.Empty).Trim();
            if (ShouldUseBalancedDefault(value))
                return DefaultDeterministicDefinitions;

            return value;
        }

        private static bool ShouldUseBalancedDefault(string raw)
        {
            string value = (raw ?? string.Empty).Trim();
            return string.IsNullOrWhiteSpace(value) ||
                   string.Equals(value, LegacySingleRealmDefinitions, StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, LegacyBalancedDefinitions, StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsBalancedDefaultDefinitions(IList<DynamicQuestSeedDefinition> definitions)
        {
            return definitions != null &&
                   definitions.Count == 3 &&
                   HasDefaultDefinition(definitions, 1, "Brother Penric", "black wolf pup") &&
                   HasDefaultDefinition(definitions, 100, "Aud", "young sveawolf") &&
                   HasDefaultDefinition(definitions, 200, "Ionhar", "water beetle larva");
        }

        private static bool HasDefaultDefinition(
            IEnumerable<DynamicQuestSeedDefinition> definitions,
            ushort regionId,
            string legacyStartNpcName,
            string targetName)
        {
            return definitions.Any(definition =>
                definition.RegionId == regionId &&
                definition.Count == 1 &&
                definition.MinLevel == 1 &&
                definition.MaxLevel == 5 &&
                definition.StartMode == DynamicQuestStartMode.NpcOffer &&
                string.IsNullOrWhiteSpace(definition.Trigger) &&
                (IsDefaultSelectorDefinition(definition) ||
                 (string.Equals(definition.StartNpcName, legacyStartNpcName, StringComparison.OrdinalIgnoreCase) &&
                  string.Equals(definition.TargetName, targetName, StringComparison.OrdinalIgnoreCase))));
        }

        private static bool IsDefaultSelectorDefinition(DynamicQuestSeedDefinition definition)
        {
            return string.Equals(definition.StartSelector, "town-npc", StringComparison.OrdinalIgnoreCase) &&
                   string.Equals(definition.TargetSelector, "hostile-near-start", StringComparison.OrdinalIgnoreCase);
        }

        private static int ParseInt(string value, int fallback)
        {
            return int.TryParse(value, out int parsed) ? parsed : fallback;
        }

        private static DynamicQuestStartMode ParseStartMode(string value)
        {
            return Enum.TryParse(value, true, out DynamicQuestStartMode parsed)
                ? parsed
                : DynamicQuestStartMode.NpcOffer;
        }

        private static string SelectorToken(string value)
        {
            string text = (value ?? string.Empty).Trim();
            const string prefix = "selector:";
            return text.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)
                ? text.Substring(prefix.Length).Trim().ToLowerInvariant()
                : string.Empty;
        }

        private static string NormalizeBranchWorldSignal(string value)
        {
            value = (value ?? string.Empty).Trim().ToLowerInvariant();
            return DynamicQuestWorldSignalPolicy.IsAllowed(value) ? value : string.Empty;
        }
    }

    public sealed class DynamicQuestSeedSummary
    {
        public bool Enabled { get; set; }
        public bool DynamicQuestEnabled { get; set; }
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public int Definitions { get; set; }
        public int ScannedNpcs { get; set; }
        public int Created { get; set; }
        public int Skipped { get; set; }
        public int Failed { get; set; }
        public int StoryCachePrefilled { get; set; }
        public int StoryCachePrefillCandidates { get; set; }
        public int StoryCachePrefillAttempted { get; set; }
        public int StoryCachePrefillAlreadyReady { get; set; }
        public int StoryCachePrefillResolveSkipped { get; set; }
        public int StoryCachePrefillGenerationFailed { get; set; }
        public int StoryCachePrefillQualityRejected { get; set; }
        public int StoryCacheOffered { get; set; }
        public int CancelledByWorldRevision { get; set; }
        public int CancelledStaleProgress { get; set; }
        public int RemovedStaleOffers { get; set; }
        public string WorldRevision { get; set; } = string.Empty;
        public IDictionary<string, int> CreatedByRealm { get; set; } = NewRealmCounters();
        public IDictionary<string, int> SkippedByRealm { get; set; } = NewRealmCounters();
        public IDictionary<string, int> FailedByRealm { get; set; } = NewRealmCounters();
        public IDictionary<string, int> StoryCachePrefillGenerationErrors { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IList<string> Messages { get; set; } = new List<string>();

        private static IDictionary<string, int> NewRealmCounters()
        {
            return new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase)
            {
                ["Albion"] = 0,
                ["Midgard"] = 0,
                ["Hibernia"] = 0,
                ["Unknown"] = 0
            };
        }
    }

    public sealed class DynamicQuestStoryCacheSnapshot
    {
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public int Limit { get; set; }
        public int TotalActive { get; set; }
        public int ReadyActive { get; set; }
        public int OfferEligibleActive { get; set; }
        public int DummyUnevaluatedOfferBlocked { get; set; }
        public int MissingNarrative { get; set; }
        public int MissingPresentation { get; set; }
        public int DummyEvaluatedActive { get; set; }
        public int DummyEvaluatedReady { get; set; }
        public int DummyUnevaluatedReady { get; set; }
        public int DummyFailedActive { get; set; }
        public int Returned { get; set; }
        public bool IncludeText { get; set; }
        public IDictionary<string, int> ByRealm { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IDictionary<string, int> ByProvider { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IDictionary<string, int> ByModel { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IDictionary<string, int> ByStartMode { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IDictionary<string, int> ByArchetype { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IDictionary<string, int> ReadyByArchetype { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IDictionary<string, int> OfferEligibleByArchetype { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IDictionary<string, int> DummyUnevaluatedOfferBlockedByArchetype { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IDictionary<string, int> NotReadyByReason { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IDictionary<string, int> WarningsByReason { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IList<DynamicQuestStoryCacheItem> Items { get; set; } = Array.Empty<DynamicQuestStoryCacheItem>();
    }

    public sealed class DynamicQuestStoryCachePrefillPlanSnapshot
    {
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public bool Enabled { get; set; }
        public bool DynamicQuestEnabled { get; set; }
        public bool UseLlm { get; set; }
        public bool WorldPrefillEnabled { get; set; }
        public bool CanGenerateNewStory { get; set; }
        public int ScannedNpcs { get; set; }
        public int ExistingDefinitions { get; set; }
        public int WorldCandidates { get; set; }
        public int TotalCandidates { get; set; }
        public int BatchSize { get; set; }
        public int MaxTemplates { get; set; }
        public int ActiveTemplates { get; set; }
        public int ReadyActiveTemplates { get; set; }
        public int MaxWorldCandidates { get; set; }
        public IDictionary<string, int> ByRealm { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IDictionary<string, int> ByStartMode { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IList<string> Reasons { get; set; } = new List<string>();
        public IList<DynamicQuestStoryCachePrefillCandidate> Samples { get; set; } = Array.Empty<DynamicQuestStoryCachePrefillCandidate>();
    }

    public sealed class DynamicQuestStoryCachePrefillCandidate
    {
        public string StartNpcName { get; set; } = string.Empty;
        public ushort RegionId { get; set; }
        public string Realm { get; set; } = string.Empty;
        public string TargetName { get; set; } = string.Empty;
        public int Count { get; set; }
        public int MinLevel { get; set; }
        public int MaxLevel { get; set; }
        public string StartMode { get; set; } = string.Empty;
        public string BranchWorldSignal { get; set; } = string.Empty;
    }

    public sealed class DynamicQuestStoryCacheItem
    {
        public string TemplateId { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public string StorySeed { get; set; } = string.Empty;
        public string OfferText { get; set; } = string.Empty;
        public string ProgressText { get; set; } = string.Empty;
        public string FinishText { get; set; } = string.Empty;
        public string Realm { get; set; } = string.Empty;
        public string PreferredStartNpcName { get; set; } = string.Empty;
        public ushort PreferredRegionId { get; set; }
        public string TargetNameHint { get; set; } = string.Empty;
        public string RuntimeTargetName { get; set; } = string.Empty;
        public string DummyEvaluationTargetName { get; set; } = string.Empty;
        public string EffectiveTargetName { get; set; } = string.Empty;
        public int Count { get; set; }
        public int MinLevel { get; set; }
        public int MaxLevel { get; set; }
        public string Source { get; set; } = string.Empty;
        public IList<string> Tags { get; set; } = Array.Empty<string>();
        public string BranchWorldSignal { get; set; } = string.Empty;
        public IList<string> Warnings { get; set; } = Array.Empty<string>();
        public string StoryProvider { get; set; } = string.Empty;
        public string StoryModel { get; set; } = string.Empty;
        public int StoryQualityScore { get; set; }
        public int DummyEvaluationScore { get; set; }
        public int DummyEvaluationCount { get; set; }
        public string DummyEvaluationJson { get; set; } = string.Empty;
        public DateTime DummyEvaluatedAt { get; set; } = DateTime.MinValue;
        public int DummyOperationalScore { get; set; }
        public string DummyOperationalGrade { get; set; } = string.Empty;
        public bool DummyOperationalPassed { get; set; }
        public string DummyFailureCategory { get; set; } = string.Empty;
        public int DummyActionSceneCohesionScore { get; set; }
        public int DummyCinematicCatalogRoleVariety { get; set; }
        public int DummyCinematicModelRoleFitScore { get; set; }
        public bool ReadyForUse { get; set; }
        public bool OfferEligible { get; set; }
        public IList<string> OfferBlockReasons { get; set; } = Array.Empty<string>();
        public DynamicQuestStoryCacheQuality Quality { get; set; } = DynamicQuestStoryCacheQuality.Empty;
        public DynamicQuestStoryCacheQuality CurrentQuality { get; set; } = DynamicQuestStoryCacheQuality.Empty;
        public IList<DynamicQuestStoryCacheNarrativeScene> NarrativeScenes { get; set; } = Array.Empty<DynamicQuestStoryCacheNarrativeScene>();
        public IList<DynamicQuestStoryCachePresentationBeat> PresentationBeats { get; set; } = Array.Empty<DynamicQuestStoryCachePresentationBeat>();
        public DateTime StoryGeneratedAt { get; set; }
        public DateTime StoryLastUsedAt { get; set; }
        public string StartMode { get; set; } = string.Empty;
        public string Trigger { get; set; } = string.Empty;
        public string LastBindingKey { get; set; } = string.Empty;
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
    }

    public sealed class DynamicQuestStoryCacheEvaluationOfferResult
    {
        public bool Success { get; set; }
        public bool Existing { get; set; }
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public string TemplateId { get; set; } = string.Empty;
        public string QuestId { get; set; } = string.Empty;
        public string Message { get; set; } = string.Empty;
        public IList<string> OfferBlockReasons { get; set; } = Array.Empty<string>();
        public DynamicQuestDefinition Quest { get; set; }
    }

    public sealed class DynamicQuestDummyEvaluationRequest
    {
        public string QuestId { get; set; } = string.Empty;
        public string TemplateId { get; set; } = string.Empty;
        public string Player { get; set; } = string.Empty;
        public string Account { get; set; } = string.Empty;
        public string Source { get; set; } = string.Empty;
        public string TargetName { get; set; } = string.Empty;
        public int Score { get; set; }
        public int MinimumScore { get; set; }
        public bool Passed { get; set; }
        public bool Completed { get; set; }
        public int Players { get; set; }
        public int OkPlayers { get; set; }
        public bool InitialTimelineObservationGapAccepted { get; set; }
        public int PlayerDeaths { get; set; }
        public int TargetRemoved { get; set; }
        public int KillConfirmed { get; set; }
        public bool BranchChoiceExpected { get; set; }
        public int ChoiceSelected { get; set; }
        public int ChoiceOutcomeScene { get; set; }
        public int ChoiceConsequence { get; set; }
        public bool WorldSignalExpected { get; set; }
        public int WorldSignal { get; set; }
        public int PresentationBeat { get; set; }
        public int PresentationSpeakerVariety { get; set; } = -1;
        public int PresentationStagedBeat { get; set; } = -1;
        public int PresentationStagedActorTotal { get; set; } = -1;
        public int PresentationStagedActorPeak { get; set; } = -1;
        public int PresentationStagedActionVariety { get; set; } = -1;
        public int PresentationStagedRoleVariety { get; set; } = -1;
        public int PresentationStagedFormationVariety { get; set; } = -1;
        public int PresentationStagedDelayedBeat { get; set; } = -1;
        public int WorldImpact { get; set; }
        public int WorldImpactSummary { get; set; }
        public int WorldMemoryMarked { get; set; }
        public int NarrativeScene { get; set; }
        public int CinematicAction { get; set; }
        public int MinNarrativeScenePerPlayer { get; set; } = -1;
        public int MinPresentationBeatPerPlayer { get; set; } = -1;
        public int MinCinematicActionPerPlayer { get; set; } = -1;
        public int CinematicVariety { get; set; }
        public int CinematicMotionVariety { get; set; }
        public int CinematicStaggeredScene { get; set; }
        public int CinematicObjectiveFocalScene { get; set; }
        public int CinematicActorRoleVariety { get; set; }
        public int CinematicChoreographedScene { get; set; }
        public int CinematicInteractionScene { get; set; }
        public int CinematicTacticVariety { get; set; }
        public int CinematicActorInstances { get; set; }
        public int CinematicActorPeak { get; set; }
        public int CinematicActorBudgetScore { get; set; }
        public int ActionSceneCohesionScore { get; set; }
        public int CinematicCatalogRoleVariety { get; set; } = -1;
        public int CinematicModelRoleFitScore { get; set; } = -1;
        public int CinematicMarkerScene { get; set; } = -1;
        public int CinematicMarkerVariety { get; set; } = -1;
        public int CinematicPhaseCoverage { get; set; } = -1;
        public int CinematicSetpiecePhaseCoverage { get; set; } = -1;
        public int CinematicMarkerPhaseCoverage { get; set; } = -1;
        public int CinematicStoryChain { get; set; } = -1;
        public int SceneDirectorBeat { get; set; }
        public int SceneBeatOutcome { get; set; }
        public int SceneChoreographyPhase { get; set; }
        public int SceneActorExchange { get; set; }
        public int SceneExchangeOutcome { get; set; }
        public int SceneOutcomeSignal { get; set; }
        public int SceneConsequence { get; set; }
        public int SceneWorldSignal { get; set; }
        public int WorldSignalSceneShift { get; set; }
        public int WorldSignalSceneShiftDetail { get; set; } = -1;
        public int WorldSignalSceneShiftPhaseVariety { get; set; } = -1;
        public int WorldSignalSceneShiftSourceVariety { get; set; } = -1;
        public int WorldSignalSceneShiftTargetVariety { get; set; } = -1;
        public int CinematicCleanup { get; set; }
        public int FollowupHuntStart { get; set; }
        public int CinematicDensityScore { get; set; }
        public int StoryContinuityScore { get; set; }
        public int StoryArchetypeScore { get; set; }
        public int SkyrimGradeScore { get; set; }
        public DynamicQuestDummyOperationalEvaluation OperationalEvaluation { get; set; } = DynamicQuestDummyOperationalEvaluation.Empty;
        public string FailureCategory { get; set; } = string.Empty;
        public double ElapsedSeconds { get; set; }
        public string Details { get; set; } = string.Empty;
    }

    public sealed class DynamicQuestDummyOperationalEvaluation
    {
        public static DynamicQuestDummyOperationalEvaluation Empty { get; } = new();

        public int TotalScore { get; set; }
        public string Grade { get; set; } = string.Empty;
        public bool Passed { get; set; }
        public int FeasibilityScore { get; set; }
        public int DifficultyScore { get; set; }
        public int RewardBalanceScore { get; set; }
        public int RouteScore { get; set; }
        public int VarietyScore { get; set; }
        public int LoreScore { get; set; }
        public int ExploitPenalty { get; set; }
        public IList<string> FailReasons { get; set; } = Array.Empty<string>();
        public IList<string> Warnings { get; set; } = Array.Empty<string>();
        public IList<string> SuggestedFixes { get; set; } = Array.Empty<string>();
    }

    public sealed class DynamicQuestDummyEvaluationResult
    {
        public bool Enabled { get; set; }
        public bool Accepted { get; set; }
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public string QuestId { get; set; } = string.Empty;
        public string TemplateId { get; set; } = string.Empty;
        public int Score { get; set; }
        public int MinimumScore { get; set; }
        public bool BelowThreshold { get; set; }
        public bool Deactivated { get; set; }
        public int RemovedRuntimeQuests { get; set; }
        public int CancelledProgress { get; set; }
        public string Message { get; set; } = string.Empty;
    }

    public sealed class DynamicQuestStoryCacheQuality
    {
        public static DynamicQuestStoryCacheQuality Empty { get; } = new();

        public int TotalScore { get; set; }
        public int StructureScore { get; set; }
        public int KoreanScore { get; set; }
        public int ObjectiveScore { get; set; }
        public int ImmersionScore { get; set; }
        public int NarrativeScore { get; set; }
        public int PresentationScore { get; set; }
        public int RebindabilityScore { get; set; }
        public int SafetyScore { get; set; }
        public int DiversityScore { get; set; }
        public IList<string> Reasons { get; set; } = Array.Empty<string>();
    }

    public sealed class DynamicQuestStoryCacheNarrativeScene
    {
        public string NodeId { get; set; } = string.Empty;
        public string SceneType { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public string Body { get; set; } = string.Empty;
        public string JournalEntry { get; set; } = string.Empty;
        public string Mood { get; set; } = string.Empty;
        public string RevealPolicy { get; set; } = string.Empty;
    }

    public sealed class DynamicQuestStoryCachePresentationBeat
    {
        public string NodeId { get; set; } = string.Empty;
        public string Trigger { get; set; } = string.Empty;
        public string Speaker { get; set; } = string.Empty;
        public string Text { get; set; } = string.Empty;
        public string Emotion { get; set; } = string.Empty;
        public string Emote { get; set; } = string.Empty;
        public string CinematicAction { get; set; } = string.Empty;
        public string SceneRole { get; set; } = string.Empty;
        public string Formation { get; set; } = string.Empty;
        public int ActorCount { get; set; }
        public int DelayMs { get; set; }
    }

    internal sealed class DynamicQuestSeedResolveResult
    {
        public bool Success { get; private set; }
        public DynamicQuestSeedDefinition Definition { get; private set; }
        public DynamicQuestSeedNpc StartNpc { get; private set; }
        public DynamicQuestSeedNpc TargetNpc { get; private set; }
        public string Message { get; private set; } = string.Empty;

        public static DynamicQuestSeedResolveResult Ok(
            DynamicQuestSeedDefinition definition,
            DynamicQuestSeedNpc startNpc,
            DynamicQuestSeedNpc targetNpc = null)
        {
            return new DynamicQuestSeedResolveResult
            {
                Success = true,
                Definition = definition,
                StartNpc = startNpc,
                TargetNpc = targetNpc
            };
        }

        public static DynamicQuestSeedResolveResult Skip(DynamicQuestSeedDefinition definition, string message)
        {
            return new DynamicQuestSeedResolveResult
            {
                Success = false,
                Definition = definition,
                Message = message ?? string.Empty
            };
        }
    }

    public sealed class DynamicQuestSeedService
    {
        private static readonly Logging.Logger Log = Logging.LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);
        private const int NearStartPreferredRadius = 5000;
        private const int NearStartExpandedSafeRadius = 12000;
        private const int NearStartMinimumSafeTargetDistance = 1500;
        private const int StarterMaxSoloSafeTargetLevel = 2;
        private const int TargetAreaThreatRadius = 900;
        private const int TargetRouteThreatRadius = 1200;
        private const int StoryCacheAutoAcceptScopeRadius = 6500;
        private const int MaxNearbyStartCandidatesToEvaluate = 32;
        private const int MaxNearbyTargetCandidatesToRank = 16;
        private const string CodexCuratedStoryProvider = "codex-curated";
        private const string CodexCuratedStoryModel = "hand-authored-cinematic-v15";
        private static readonly object StoryCacheCleanupLock = new();
        private static DateTime s_lastStoryCacheCleanupQuotaDate = DateTime.MinValue;
        private static Func<DateTime> s_utcNow = () => DateTime.UtcNow;
        private static readonly JsonSerializerOptions StoryCacheJsonOptions = new()
        {
            PropertyNameCaseInsensitive = true
        };

        private readonly IDynamicQuestTemplateRepository m_templateRepository;
        private readonly DynamicQuestStoryService m_storyService;

        public static DynamicQuestSeedService Instance { get; } = new();

        public DynamicQuestSeedService()
            : this(new DatabaseDynamicQuestTemplateRepository(), DynamicQuestStoryService.FromProperties())
        {
        }

        public DynamicQuestSeedService(IDynamicQuestTemplateRepository templateRepository, DynamicQuestStoryService storyService)
        {
            m_templateRepository = templateRepository ?? new DatabaseDynamicQuestTemplateRepository();
            m_storyService = storyService ?? DynamicQuestStoryService.FromProperties();
        }

        internal static void ResetStoryCacheCleanupForTest()
        {
            lock (StoryCacheCleanupLock)
            {
                s_lastStoryCacheCleanupQuotaDate = DateTime.MinValue;
            }
        }

        internal static void SetClockForTest(Func<DateTime> utcNow)
        {
            lock (StoryCacheCleanupLock)
            {
                s_utcNow = utcNow ?? (() => DateTime.UtcNow);
                s_lastStoryCacheCleanupQuotaDate = DateTime.MinValue;
            }
        }

        public DynamicQuestSeedSummary SeedFromWorld()
        {
            IEnumerable<GameNPC> npcs = WorldMgr.GetAllRegions()
                .SelectMany(region => region.Objects.OfType<GameNPC>());

            return Seed(npcs, DynamicQuestSeedOptions.FromProperties());
        }

        public DynamicQuestSeedSummary PrefillStoryCacheFromWorld()
        {
            GrowthStateIndex growthStates = LoadGrowthStatesForSeed();
            IEnumerable<DynamicQuestSeedNpc> seedNpcs = WorldMgr.GetAllRegions()
                .SelectMany(region => region.Objects.OfType<GameNPC>())
                .Where(IsUsableSeedNpc)
                .Select(npc => CreateSeedNpc(npc, growthStates));

            return PrefillStoryCache(seedNpcs, DynamicQuestSeedOptions.FromProperties());
        }

        public DynamicQuestStoryCachePrefillPlanSnapshot GetStoryCachePrefillPlanSnapshotFromWorld(int sampleLimit = 20)
        {
            GrowthStateIndex growthStates = LoadGrowthStatesForSeed();
            IEnumerable<DynamicQuestSeedNpc> seedNpcs = WorldMgr.GetAllRegions()
                .SelectMany(region => region.Objects.OfType<GameNPC>())
                .Where(IsUsableSeedNpc)
                .Select(npc => CreateSeedNpc(npc, growthStates));

            return GetStoryCachePrefillPlanSnapshot(seedNpcs, DynamicQuestSeedOptions.FromProperties(), sampleLimit);
        }

        public DynamicQuestStoryCacheEvaluationOfferResult OfferStoryCacheTemplateForEvaluationFromWorld(
            string templateId,
            string worldRevision = "",
            bool allowFailedDummyEvaluation = false)
        {
            string normalizedTemplateId = (templateId ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(normalizedTemplateId))
                return OfferStoryCacheTemplateForEvaluation(Array.Empty<DynamicQuestSeedNpc>(), normalizedTemplateId, worldRevision, allowFailedDummyEvaluation);

            UpgradeLegacyStoryCacheRows();
            DbDynamicQuestTemplate row = m_templateRepository.Find(normalizedTemplateId);
            if (row == null)
                return OfferStoryCacheTemplateForEvaluation(Array.Empty<DynamicQuestSeedNpc>(), normalizedTemplateId, worldRevision, allowFailedDummyEvaluation);

            GrowthStateIndex growthStates = LoadGrowthStatesForSeed();
            IEnumerable<GameNPC> worldNpcs = row.PreferredRegionId > 0
                ? WorldMgr.GetNPCsFromRegion(row.PreferredRegionId)
                : WorldMgr.GetAllRegions().SelectMany(region => region.Objects.OfType<GameNPC>());
            IEnumerable<DynamicQuestSeedNpc> seedNpcs = worldNpcs
                .Where(IsUsableSeedNpc)
                .Select(npc => CreateSeedNpc(npc, growthStates));

            return OfferStoryCacheTemplateForEvaluation(seedNpcs, normalizedTemplateId, worldRevision, allowFailedDummyEvaluation);
        }

        public DynamicQuestStoryCacheEvaluationOfferResult OfferStoryCacheTemplateForEvaluation(
            IEnumerable<DynamicQuestSeedNpc> npcs,
            string templateId,
            string worldRevision = "",
            bool allowFailedDummyEvaluation = false)
        {
            templateId = (templateId ?? string.Empty).Trim();
            string normalizedWorldRevision = NormalizeWorldRevision(string.IsNullOrWhiteSpace(worldRevision)
                ? Properties.KDAOC_DYNAMIC_QUEST_WORLD_REVISION
                : worldRevision);
            DynamicQuestStoryCacheEvaluationOfferResult result = new()
            {
                GeneratedAt = UtcNow(),
                TemplateId = templateId
            };

            if (string.IsNullOrWhiteSpace(templateId))
            {
                result.Message = "missing template id";
                return result;
            }

            UpgradeLegacyStoryCacheRows();

            DbDynamicQuestTemplate row = m_templateRepository.Find(templateId);
            if (row == null)
            {
                result.Message = "template not found";
                return result;
            }

            result.TemplateId = row.TemplateId ?? templateId;
            result.OfferBlockReasons = BuildStoryCacheOfferBlockReasons(row);

            if (!IsActiveStoryCacheRow(row))
            {
                result.Message = "template is not active";
                return result;
            }

            IList<string> readyBlockReasons = BuildStoryCacheReadyBlockReasons(row);
            if (allowFailedDummyEvaluation)
            {
                readyBlockReasons = readyBlockReasons
                    .Where(reason => !IsDummyEvaluationReevaluationBlockReason(reason))
                    .ToList();
            }
            if (readyBlockReasons.Count > 0)
            {
                result.OfferBlockReasons = readyBlockReasons;
                result.Message = $"template is not ready: {string.Join(",", readyBlockReasons)}";
                return result;
            }

            IList<string> unsafeOfferBlockReasons = result.OfferBlockReasons
                .Where(reason =>
                    !string.Equals(reason, "dummy_evaluation_required", StringComparison.OrdinalIgnoreCase) &&
                    !(allowFailedDummyEvaluation && IsDummyEvaluationReevaluationBlockReason(reason)))
                .ToList();
            if (unsafeOfferBlockReasons.Count > 0)
            {
                if (unsafeOfferBlockReasons.Contains("dummy_evaluation_target_difficulty_history", StringComparer.OrdinalIgnoreCase))
                {
                    MarkStoryCacheTargetDifficultyHistory(
                        row,
                        DynamicQuestRuntimeService.Instance.GetTargetNameForTemplate(row.TemplateId));
                }
                result.Message = $"template is blocked for evaluation offer: {string.Join(",", unsafeOfferBlockReasons)}";
                return result;
            }

            DynamicQuestDefinition existing = FindRuntimeQuestForTemplate(row.TemplateId, normalizedWorldRevision);
            if (existing != null)
            {
                EnsureEvaluationOfferAutoAcceptRegionTrigger(existing, row);
                result.Success = true;
                result.Existing = true;
                result.QuestId = existing.Id ?? string.Empty;
                result.Quest = existing;
                result.Message = "existing evaluation offer found";
                return result;
            }

            DynamicQuestTemplate template = DynamicQuestTemplateService.FromRowForCache(row);
            if (template == null || string.IsNullOrWhiteSpace(template.TemplateId))
            {
                result.Message = "template conversion failed";
                return result;
            }

            template.WorldRevision = normalizedWorldRevision;
            IList<DynamicQuestSeedNpc> scopedNpcs = ScopeStoryCacheBindingNpcs(npcs, row);
            Stopwatch bindingStopwatch = Stopwatch.StartNew();
            DynamicQuestTemplateBindingResult binding = new DynamicQuestTemplateService()
                .BindTemplate(template, scopedNpcs);
            if (Log.IsInfoEnabled)
            {
                Log.Info(
                    $"Dynamic quest story cache evaluation offer bind template={template.TemplateId} region={row.PreferredRegionId} npcs={scopedNpcs.Count} success={binding.Success} elapsed={bindingStopwatch.ElapsedMilliseconds}ms message={binding.Message}");
            }
            if (!binding.Success)
            {
                if (IsTemplateTargetMissing(binding.Message))
                {
                    MarkStoryCacheTargetMissing(row, binding.Message);
                    result.OfferBlockReasons = BuildStoryCacheOfferBlockReasons(row);
                }
                result.Message = binding.Message;
                return result;
            }

            if (!allowFailedDummyEvaluation &&
                HasRelatedAutoAcceptDummyDifficultyFailure(row, binding.Quest?.TargetName))
            {
                MarkStoryCacheTargetDifficultyHistory(row, binding.Quest?.TargetName);
                result.OfferBlockReasons = new[] { "dummy_evaluation_target_difficulty_history" };
                result.Message = "template is blocked for evaluation offer: dummy_evaluation_target_difficulty_history";
                return result;
            }

            List<string> tags = new(binding.Quest.Tags ?? Array.Empty<string>());
            AddPrimaryTemplateTag(tags, row.TemplateId ?? templateId);
            if (!tags.Contains("dummy-evaluation-offer", StringComparer.OrdinalIgnoreCase))
                tags.Add("dummy-evaluation-offer");
            binding.Quest.Tags = tags;
            EnsureEvaluationOfferAutoAcceptRegionTrigger(binding.Quest, row);

            DynamicQuestResult addResult = DynamicQuestRuntimeService.Instance.AddQuest(binding.Quest);
            result.Success = addResult.Success;
            result.Message = addResult.Message;
            result.Quest = addResult.Quest;
            result.QuestId = addResult.Quest?.Id ?? string.Empty;
            if (addResult.Success)
                TouchStoryTemplate(template.TemplateId, binding.BindingKey);

            return result;
        }

        private static void EnsureEvaluationOfferAutoAcceptRegionTrigger(DynamicQuestDefinition quest, DbDynamicQuestTemplate row)
        {
            if (quest == null || row == null || quest.StartMode != DynamicQuestStartMode.AutoAccept)
                return;

            ushort regionId = ResolveEvaluationOfferRegion(quest, row);
            if (regionId == 0)
                return;

            List<string> tags = new(quest.Tags ?? Array.Empty<string>());
            tags.RemoveAll(IsNonRegionalAutoAcceptStartTriggerTag);
            AddPrimaryTemplateTag(tags, row.TemplateId);
            AddTagIfMissing(tags, "dummy-evaluation-offer");
            AddTagIfMissing(tags, $"region:{regionId}");
            AddTagIfMissing(tags, $"trigger:region:{regionId}");
            quest.Tags = tags;
        }

        private static bool IsNonRegionalAutoAcceptStartTriggerTag(string tag)
        {
            string value = (tag ?? string.Empty).Trim();
            string trigger = string.Empty;
            if (value.StartsWith("trigger:", StringComparison.OrdinalIgnoreCase))
                trigger = value.Substring("trigger:".Length);
            else if (value.StartsWith("autoaccept:", StringComparison.OrdinalIgnoreCase))
                trigger = value.Substring("autoaccept:".Length);

            return !string.IsNullOrWhiteSpace(trigger) &&
                   !IsRegionalAutoAcceptStartTrigger(trigger);
        }

        private bool MarkStoryCacheTargetMissing(DbDynamicQuestTemplate row, string message)
        {
            if (row == null)
                return false;

            DateTime now = UtcNow();
            int minimumScore = Math.Clamp(Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE, 1, 100);
            row.IsActive = false;
            row.DummyEvaluationScore = 0;
            row.DummyEvaluationCount = Math.Max(0, row.DummyEvaluationCount) + 1;
            row.DummyEvaluatedAt = now;
            row.UpdatedAt = now;
            row.DummyEvaluationJson = JsonSerializer.Serialize(new
            {
                score = 0,
                minimumScore,
                belowThreshold = true,
                passed = false,
                completed = false,
                failureCategory = "target_missing",
                message = message ?? string.Empty,
                generatedAt = now
            });

            return m_templateRepository.Save(row);
        }

        private bool MarkStoryCacheTargetDifficultyHistory(DbDynamicQuestTemplate row, string targetName)
        {
            if (row == null)
                return false;

            DateTime now = UtcNow();
            int minimumScore = Math.Clamp(Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE, 1, 100);
            row.DummyEvaluationScore = 0;
            row.DummyEvaluationCount = Math.Max(0, row.DummyEvaluationCount) + 1;
            row.DummyEvaluatedAt = now;
            row.UpdatedAt = now;
            row.DummyEvaluationJson = JsonSerializer.Serialize(new
            {
                score = 0,
                minimumScore,
                belowThreshold = true,
                passed = false,
                completed = false,
                failureCategory = "dummy_difficulty",
                targetName = targetName ?? string.Empty,
                message = "blocked by related autoaccept target difficulty history",
                generatedAt = now
            });

            return m_templateRepository.Save(row);
        }

        private static bool IsRegionalAutoAcceptStartTrigger(string trigger)
        {
            string value = (trigger ?? string.Empty).Trim();
            return string.Equals(value, "region-entered", StringComparison.OrdinalIgnoreCase) ||
                   value.StartsWith("region:", StringComparison.OrdinalIgnoreCase) ||
                   value.StartsWith("region-entered:", StringComparison.OrdinalIgnoreCase);
        }

        private static void AddPrimaryTemplateTag(IList<string> tags, string templateId)
        {
            if (tags == null)
                return;

            templateId = (templateId ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(templateId))
                return;

            string tag = $"template:{templateId}";
            for (int i = 0; i < tags.Count; i++)
            {
                if (!string.Equals(tags[i], tag, StringComparison.OrdinalIgnoreCase))
                    continue;

                if (i > 0)
                {
                    tags.RemoveAt(i);
                    tags.Insert(0, tag);
                }
                return;
            }

            tags.Insert(0, tag);
        }

        private static bool IsDummyEvaluationReevaluationBlockReason(string reason)
        {
            string value = (reason ?? string.Empty).Trim();
            return value.StartsWith("dummy_evaluation_", StringComparison.OrdinalIgnoreCase);
        }

        private static ushort ResolveEvaluationOfferRegion(DynamicQuestDefinition quest, DbDynamicQuestTemplate row)
        {
            if (row?.PreferredRegionId > 0)
                return row.PreferredRegionId;

            ushort objectiveRegion = (quest?.Nodes ?? Array.Empty<DynamicQuestNode>())
                .Select(node => node?.Objective?.RegionId ?? 0)
                .FirstOrDefault(region => region > 0);
            if (objectiveRegion > 0)
                return objectiveRegion;

            return quest?.StartRegionId ?? 0;
        }

        private static void AddTagIfMissing(IList<string> tags, string tag)
        {
            if (tags == null || string.IsNullOrWhiteSpace(tag))
                return;

            if (!tags.Contains(tag, StringComparer.OrdinalIgnoreCase))
                tags.Add(tag);
        }

        public DynamicQuestSeedSummary Seed(IEnumerable<GameNPC> npcs, DynamicQuestSeedOptions options)
        {
            GrowthStateIndex growthStates = LoadGrowthStatesForSeed();
            IEnumerable<DynamicQuestSeedNpc> seedNpcs = (npcs ?? Array.Empty<GameNPC>())
                .Where(IsUsableSeedNpc)
                .Select(npc => CreateSeedNpc(npc, growthStates));

            return Seed(seedNpcs, options);
        }

        private static DynamicQuestSeedNpc CreateSeedNpc(GameNPC npc, GrowthStateIndex growthStates = null)
        {
            IOldAggressiveBrain aggressiveBrain = npc.Brain as IOldAggressiveBrain;
            DbMobGrowthState growth = null;
            if (!string.IsNullOrWhiteSpace(npc.InternalID))
                growthStates?.ByMobId.TryGetValue(npc.InternalID, out growth);

            string seedName = string.IsNullOrWhiteSpace(growth?.BaseName) ? npc.Name ?? string.Empty : growth.BaseName;
            GrowthNameRisk nameRisk = growthStates?.FindNameRisk(npc.CurrentRegionID, seedName) ?? GrowthNameRisk.Empty;

            return new DynamicQuestSeedNpc
            {
                Name = seedName,
                RawName = npc.Name ?? string.Empty,
                InternalID = npc.InternalID ?? string.Empty,
                RegionId = npc.CurrentRegionID,
                Level = npc.Level,
                X = npc.X,
                Y = npc.Y,
                Z = npc.Z,
                SourceNpc = npc,
                HasSourceNpcMetadata = true,
                SourceRealm = npc.Realm,
                SourceFlags = npc.Flags,
                SourceIsAlive = npc.IsAlive,
                SourceTypeName = npc.GetType().Name,
                SourceAggroLevel = aggressiveBrain?.AggroLevel ?? 0,
                SourceAggroRange = aggressiveBrain?.AggroRange ?? 0,
                HasGrowthState = growth != null,
                GrowthStage = growth?.Stage ?? string.Empty,
                GrowthScore = growth?.GrowthScore ?? 0,
                GrowthLevel = growth?.GrowthLevel ?? 0,
                GrowthEffectiveLevel = growth?.EffectiveLevel ?? 0,
                GrowthPlayerKills = growth?.PlayerKills ?? 0,
                GrowthIsMutant = growth?.IsMutant ?? false,
                GrowthMutationPending = growth?.MutationPending ?? false,
                NameGrowthThreatCount = nameRisk.ThreatCount,
                NameGrowthMaxScore = nameRisk.MaxScore,
                NameGrowthMaxEffectiveLevel = nameRisk.MaxEffectiveLevel,
                NameGrowthPlayerKills = nameRisk.PlayerKills
            };
        }

        private sealed class GrowthStateIndex
        {
            public static readonly GrowthStateIndex Empty = new(
                new Dictionary<string, DbMobGrowthState>(StringComparer.OrdinalIgnoreCase),
                new Dictionary<string, GrowthNameRisk>(StringComparer.OrdinalIgnoreCase));

            public GrowthStateIndex(
                IReadOnlyDictionary<string, DbMobGrowthState> byMobId,
                IReadOnlyDictionary<string, GrowthNameRisk> byRegionName)
            {
                ByMobId = byMobId ?? Empty.ByMobId;
                ByRegionName = byRegionName ?? Empty.ByRegionName;
            }

            public IReadOnlyDictionary<string, DbMobGrowthState> ByMobId { get; }
            public IReadOnlyDictionary<string, GrowthNameRisk> ByRegionName { get; }

            public GrowthNameRisk FindNameRisk(ushort regionId, string name)
            {
                if (regionId <= 0 || string.IsNullOrWhiteSpace(name))
                    return GrowthNameRisk.Empty;

                return ByRegionName.TryGetValue(GrowthNameRiskKey(regionId, name), out GrowthNameRisk risk)
                    ? risk
                    : GrowthNameRisk.Empty;
            }
        }

        private sealed class GrowthNameRisk
        {
            public static readonly GrowthNameRisk Empty = new();

            public int ThreatCount { get; set; }
            public int MaxScore { get; set; }
            public int MaxEffectiveLevel { get; set; }
            public int PlayerKills { get; set; }

            public void Add(DbMobGrowthState row)
            {
                if (row == null || !IsStarterSevereGrowthStateThreat(row))
                    return;

                ThreatCount++;
                MaxScore = Math.Max(MaxScore, row.GrowthScore);
                MaxEffectiveLevel = Math.Max(MaxEffectiveLevel, row.EffectiveLevel);
                PlayerKills += Math.Max(0, row.PlayerKills);
            }

            public void Add(DynamicQuestSeedNpc npc)
            {
                if (npc == null)
                    return;

                ThreatCount++;
                MaxScore = Math.Max(MaxScore, Math.Max(100, npc.GrowthScore));
                MaxEffectiveLevel = Math.Max(MaxEffectiveLevel, Math.Max(npc.Level, npc.GrowthEffectiveLevel));
                PlayerKills += Math.Max(0, npc.GrowthPlayerKills);
            }
        }

        private static GrowthStateIndex LoadGrowthStatesForSeed()
        {
            if (!Properties.WORLDAI_MOB_GROWTH_ENABLED)
                return GrowthStateIndex.Empty;

            try
            {
                IList<DbMobGrowthState> activeStates = MobGrowthService.Instance.GetActive(10000);
                Dictionary<string, DbMobGrowthState> byMobId = activeStates
                    .Where(row => row != null && !string.IsNullOrWhiteSpace(row.MobId))
                    .GroupBy(row => row.MobId, StringComparer.OrdinalIgnoreCase)
                    .ToDictionary(group => group.Key, group => group.First(), StringComparer.OrdinalIgnoreCase);

                Dictionary<string, GrowthNameRisk> byRegionName = new(StringComparer.OrdinalIgnoreCase);
                foreach (DbMobGrowthState row in activeStates.Where(row => row != null && row.RegionId > 0))
                {
                    foreach (string name in GrowthRiskNames(row))
                    {
                        string key = GrowthNameRiskKey(row.RegionId, name);
                        if (!byRegionName.TryGetValue(key, out GrowthNameRisk risk))
                        {
                            risk = new GrowthNameRisk();
                            byRegionName[key] = risk;
                        }

                        risk.Add(row);
                    }
                }

                return new GrowthStateIndex(byMobId, byRegionName);
            }
            catch (Exception ex)
            {
                if (Log.IsWarnEnabled)
                    Log.Warn("Dynamic quest seed could not load mob growth state; continuing without growth risk ranks.", ex);
                return GrowthStateIndex.Empty;
            }
        }

        private static IEnumerable<string> GrowthRiskNames(DbMobGrowthState row)
        {
            if (row == null)
                yield break;

            foreach (string name in new[] { row.BaseName, row.CurrentName })
            {
                foreach (string normalized in GrowthRiskNameVariants(name))
                    yield return normalized;
            }
        }

        private static IEnumerable<string> GrowthRiskNameVariants(string name)
        {
            string normalized = NormalizeGrowthRiskName(name);
            if (string.IsNullOrWhiteSpace(normalized))
                yield break;

            yield return normalized;

            string stripped = StripMobGrowthNamePrefix(normalized);
            if (!string.Equals(stripped, normalized, StringComparison.OrdinalIgnoreCase))
                yield return stripped;
        }

        private static string GrowthNameRiskKey(ushort regionId, string name)
        {
            return $"{regionId}:{NormalizeGrowthRiskName(name)}";
        }

        private static string NormalizeGrowthRiskName(string name)
        {
            return (name ?? string.Empty).Trim().ToLowerInvariant();
        }

        private static string StripMobGrowthNamePrefix(string name)
        {
            string normalized = NormalizeGrowthRiskName(name);
            bool changed;

            do
            {
                changed = false;
                foreach (string prefix in new[] { "돌연변이 ", "흉포한 ", "챔피언 ", "노련한 ", "정예 ", "우두머리 " })
                {
                    if (normalized.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                    {
                        normalized = normalized.Substring(prefix.Length).TrimStart();
                        changed = true;
                    }
                }
            }
            while (changed);

            if (normalized.EndsWith(" 우두머리", StringComparison.OrdinalIgnoreCase))
                normalized = normalized.Substring(0, normalized.Length - " 우두머리".Length).TrimEnd();

            return normalized;
        }

        private static bool HasSevereGrowthNamePrefix(string name)
        {
            string normalized = (name ?? string.Empty).Trim();
            return normalized.StartsWith("돌연변이 ", StringComparison.OrdinalIgnoreCase) ||
                   normalized.StartsWith("흉포한 ", StringComparison.OrdinalIgnoreCase) ||
                   normalized.StartsWith("챔피언 ", StringComparison.OrdinalIgnoreCase) ||
                   normalized.StartsWith("정예 ", StringComparison.OrdinalIgnoreCase) ||
                   normalized.StartsWith("우두머리 ", StringComparison.OrdinalIgnoreCase) ||
                   normalized.EndsWith(" 우두머리", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsStarterGrowthStateThreat(DbMobGrowthState row)
        {
            if (row == null)
                return false;

            if (row.IsMutant || row.MutationPending || row.PlayerKills > 0 || row.GrowthLevel > 0)
                return true;

            if (!string.IsNullOrWhiteSpace(row.Stage) &&
                !string.Equals(row.Stage, MobGrowthStages.Normal, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            return row.EffectiveLevel > 5 || row.GrowthScore >= 20;
        }

        private static bool IsStarterSevereGrowthStateThreat(DbMobGrowthState row)
        {
            if (row == null)
                return false;

            if (row.IsMutant || row.MutationPending || row.PlayerKills > 0)
                return true;

            if (!string.IsNullOrWhiteSpace(row.Stage) &&
                !string.Equals(row.Stage, MobGrowthStages.Normal, StringComparison.OrdinalIgnoreCase) &&
                HasSevereGrowthNamePrefix(row.CurrentName))
            {
                return true;
            }

            return row.EffectiveLevel > StarterMaxSoloSafeTargetLevel;
        }

        private static void AnnotateLiveNameGrowthThreats(IList<DynamicQuestSeedNpc> npcs)
        {
            if (npcs == null || npcs.Count == 0)
                return;

            Dictionary<string, GrowthNameRisk> liveRisks = new(StringComparer.OrdinalIgnoreCase);
            foreach (DynamicQuestSeedNpc npc in npcs)
            {
                if (npc == null || !npc.HasSourceNpcMetadata || npc.RegionId <= 0 || npc.Level <= 0 || npc.Level >= 75)
                    continue;

                string liveName = string.IsNullOrWhiteSpace(npc.RawName) ? npc.Name : npc.RawName;
                string normalized = NormalizeGrowthRiskName(liveName);
                string stripped = StripMobGrowthNamePrefix(normalized);
                bool hasGrowthNamePrefix = !string.Equals(normalized, stripped, StringComparison.OrdinalIgnoreCase);
                if (!hasGrowthNamePrefix && !IsStarterGrowthThreat(npc))
                    continue;

                if (!IsStarterSevereGrowthNameRisk(npc, normalized, hasGrowthNamePrefix))
                    continue;

                string key = GrowthNameRiskKey(npc.RegionId, stripped);
                if (!liveRisks.TryGetValue(key, out GrowthNameRisk risk))
                {
                    risk = new GrowthNameRisk();
                    liveRisks[key] = risk;
                }

                risk.Add(npc);
            }

            if (liveRisks.Count == 0)
                return;

            foreach (DynamicQuestSeedNpc npc in npcs)
            {
                if (npc == null || npc.RegionId <= 0)
                    continue;

                if (!liveRisks.TryGetValue(GrowthNameRiskKey(npc.RegionId, npc.Name), out GrowthNameRisk risk))
                    continue;

                npc.NameGrowthThreatCount += risk.ThreatCount;
                npc.NameGrowthMaxScore = Math.Max(npc.NameGrowthMaxScore, risk.MaxScore);
                npc.NameGrowthMaxEffectiveLevel = Math.Max(npc.NameGrowthMaxEffectiveLevel, risk.MaxEffectiveLevel);
                npc.NameGrowthPlayerKills += risk.PlayerKills;
            }
        }

        public DynamicQuestSeedSummary Seed(IEnumerable<DynamicQuestSeedNpc> npcs, DynamicQuestSeedOptions options)
        {
            Stopwatch stopwatch = Stopwatch.StartNew();
            options ??= DynamicQuestSeedOptions.FromProperties();
            string worldRevision = NormalizeWorldRevision(options.WorldRevision);
            if (Log.IsInfoEnabled)
                Log.Info("Dynamic quest seed stage: scan start.");

            List<DynamicQuestSeedNpc> npcList = (npcs ?? Array.Empty<DynamicQuestSeedNpc>())
                .Where(IsUsableSeedNpc)
                .ToList();
            AnnotateLiveNameGrowthThreats(npcList);
            if (Log.IsInfoEnabled)
                Log.Info($"Dynamic quest seed stage: scan complete npcs={npcList.Count} elapsed={stopwatch.ElapsedMilliseconds}ms.");

            DynamicQuestSeedSummary summary = new()
            {
                Enabled = options.Enabled,
                DynamicQuestEnabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                Definitions = options.Definitions.Count,
                ScannedNpcs = npcList.Count,
                WorldRevision = worldRevision
            };

            if (!options.Enabled)
                return summary;

            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED)
            {
                summary.Failed = options.Definitions.Count;
                summary.Messages.Add("dynamic quest runtime disabled");
                return summary;
            }

            if (Log.IsInfoEnabled)
                Log.Info($"Dynamic quest seed stage: world revision cleanup start revision={worldRevision} elapsed={stopwatch.ElapsedMilliseconds}ms.");
            summary.CancelledByWorldRevision = DynamicQuestRuntimeService.Instance
                .CancelActiveProgressForWorldRevision(worldRevision, "world_revision_changed");
            summary.RemovedStaleOffers = DynamicQuestRuntimeService.Instance
                .RemoveQuestsForDifferentWorldRevision(worldRevision);
            if (Log.IsInfoEnabled)
                Log.Info($"Dynamic quest seed stage: world revision cleanup complete cancelled={summary.CancelledByWorldRevision} removed={summary.RemovedStaleOffers} elapsed={stopwatch.ElapsedMilliseconds}ms.");

            if (summary.CancelledByWorldRevision > 0)
                summary.Messages.Add($"world revision cancelled active progress: {summary.CancelledByWorldRevision}");
            if (summary.RemovedStaleOffers > 0)
                summary.Messages.Add($"world revision removed stale offers: {summary.RemovedStaleOffers}");

            if (options.UseLlm && options.PrefillStoryCacheInline)
            {
                IList<DynamicQuestSeedDefinition> storyPrefillDefinitions = BuildStoryCachePrefillDefinitions(npcList, options);
                summary.StoryCachePrefillCandidates = storyPrefillDefinitions.Count;
                summary.StoryCachePrefilled = PrefillStoryCache(npcList, options, worldRevision, storyPrefillDefinitions, summary);
                AddStoryCachePrefillSummaryMessages(summary);
            }
            else if (options.UseCodexCuratedStories && Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED)
            {
                IList<DynamicQuestSeedDefinition> storyPrefillDefinitions = BuildStoryCachePrefillDefinitions(npcList, options);
                summary.StoryCachePrefillCandidates = storyPrefillDefinitions.Count;
                summary.StoryCachePrefilled = PrefillCodexCuratedStoryCache(npcList, options, worldRevision, storyPrefillDefinitions, summary);
                AddStoryCachePrefillSummaryMessages(summary);
            }

            int processedDefinitions = 0;
            foreach (DynamicQuestSeedDefinition definition in options.Definitions)
            {
                if (Log.IsInfoEnabled)
                    Log.Info($"Dynamic quest seed stage: definition start index={processedDefinitions + 1}/{options.Definitions.Count} region={definition.RegionId} start={definition.StartNpcName} selector={definition.StartSelector} target={definition.TargetName} targetSelector={definition.TargetSelector} elapsed={stopwatch.ElapsedMilliseconds}ms.");

                if (summary.Created >= Math.Max(1, options.MaxQuests))
                {
                    int remaining = Math.Max(0, options.Definitions.Count - processedDefinitions);
                    summary.Skipped += remaining;
                    foreach (DynamicQuestSeedDefinition remainingDefinition in options.Definitions.Skip(processedDefinitions))
                        IncrementRealm(summary.SkippedByRealm, RealmNameForRegion(remainingDefinition.RegionId));
                    summary.Messages.Add($"max quests reached: {options.MaxQuests}");
                    break;
                }

                processedDefinitions++;

                DynamicQuestSeedResolveResult resolved = ResolveDefinition(npcList, definition);
                DynamicQuestSeedDefinition activeDefinition = resolved.Definition ?? definition;
                bool requiresStartNpc = RequiresStartNpc(activeDefinition);
                DynamicQuestSeedNpc npc = resolved.StartNpc ?? (requiresStartNpc ? FindSeedNpc(npcList, activeDefinition) : null);
                ushort targetRegion = TargetRegion(npc, activeDefinition);

                if (requiresStartNpc && npc == null)
                {
                    summary.Skipped++;
                    IncrementRealm(summary.SkippedByRealm, RealmNameForRegion(activeDefinition.RegionId));
                    summary.Messages.Add(string.IsNullOrWhiteSpace(resolved.Message)
                        ? $"npc not found: {activeDefinition.StartNpcName} region={activeDefinition.RegionId}"
                        : resolved.Message);
                    continue;
                }

                if (!resolved.Success)
                {
                    summary.Skipped++;
                    IncrementRealm(summary.SkippedByRealm, RealmNameForRegion(targetRegion));
                    summary.Messages.Add(resolved.Message);
                    continue;
                }

                if (!ShouldRebindOnSeed(activeDefinition) && HasExistingQuestForDefinition(npc, activeDefinition, worldRevision))
                {
                    summary.Skipped++;
                    IncrementRealm(summary.SkippedByRealm, RealmNameForRegion(targetRegion));
                    continue;
                }

                DynamicQuestResult result = options.UseLlm
                    ? AddStoryTemplateBoundQuest(npcList, npc, resolved.TargetNpc, activeDefinition, worldRevision, options)
                    : options.UseCodexCuratedStories
                        ? AddCodexCuratedStoryTemplateBoundQuest(npcList, npc, resolved.TargetNpc, activeDefinition, worldRevision)
                        : AddTemplateBoundQuest(npcList, npc, resolved.TargetNpc, activeDefinition, worldRevision);
                if (Log.IsInfoEnabled)
                    Log.Info($"Dynamic quest seed stage: definition result success={result.Success} message={result.Message} elapsed={stopwatch.ElapsedMilliseconds}ms.");

                if (result.Success)
                {
                    summary.Created++;
                    IncrementRealm(summary.CreatedByRealm, RealmNameForRegion(targetRegion));
                    summary.Messages.Add(result.Message);
                }
                else if (!options.UseLlm && IsTemplateBindingSkip(result.Message))
                {
                    summary.Skipped++;
                    IncrementRealm(summary.SkippedByRealm, RealmNameForRegion(targetRegion));
                    summary.Messages.Add(result.Message);
                }
                else
                {
                    summary.Failed++;
                    IncrementRealm(summary.FailedByRealm, RealmNameForRegion(targetRegion));
                    summary.Messages.Add(result.Message);
                }
            }

            if ((options.UseLlm || options.UseCodexCuratedStories) &&
                options.UseStoryCacheOffers &&
                summary.Created < Math.Max(1, options.MaxQuests))
            {
                if (Log.IsInfoEnabled)
                    Log.Info($"Dynamic quest seed stage: story cache offers start slots={Math.Max(1, options.MaxQuests) - summary.Created} elapsed={stopwatch.ElapsedMilliseconds}ms.");
                int remainingSlots = Math.Max(1, options.MaxQuests) - summary.Created;
                summary.StoryCacheOffered = OfferCachedStoryTemplates(npcList, worldRevision, remainingSlots, summary);
                if (Log.IsInfoEnabled)
                    Log.Info($"Dynamic quest seed stage: story cache offers complete offered={summary.StoryCacheOffered} elapsed={stopwatch.ElapsedMilliseconds}ms.");
                if (summary.StoryCacheOffered > 0)
                    summary.Messages.Add($"story cache offers created: {summary.StoryCacheOffered}");
            }

            int cancelledMissingRuntimeProgress = DynamicQuestRuntimeService.Instance
                .CancelActiveProgressForMissingRuntimeQuests("runtime_offer_removed");
            summary.CancelledStaleProgress += cancelledMissingRuntimeProgress;
            if (cancelledMissingRuntimeProgress > 0)
                summary.Messages.Add($"runtime removed stale active progress: {cancelledMissingRuntimeProgress}");

            if (Log.IsInfoEnabled && summary.Created > 0)
                Log.Info($"Dynamic quest auto seed created {summary.Created} quests.");

            return summary;
        }

        public DynamicQuestSeedSummary PrefillStoryCache(IEnumerable<DynamicQuestSeedNpc> npcs, DynamicQuestSeedOptions options)
        {
            options ??= DynamicQuestSeedOptions.FromProperties();
            string worldRevision = NormalizeWorldRevision(options.WorldRevision);
            List<DynamicQuestSeedNpc> npcList = (npcs ?? Array.Empty<DynamicQuestSeedNpc>())
                .Where(IsUsableSeedNpc)
                .ToList();
            IList<DynamicQuestSeedDefinition> storyPrefillDefinitions = BuildStoryCachePrefillDefinitions(npcList, options);

            DynamicQuestSeedSummary summary = new()
            {
                Enabled = options.Enabled,
                DynamicQuestEnabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                Definitions = options.Definitions.Count,
                ScannedNpcs = npcList.Count,
                StoryCachePrefillCandidates = storyPrefillDefinitions.Count,
                WorldRevision = worldRevision
            };

            if (!options.Enabled || !Properties.KDAOC_DYNAMIC_QUEST_ENABLED ||
                (!options.UseLlm && !options.UseCodexCuratedStories))
                return summary;

            summary.StoryCachePrefilled = options.UseLlm
                ? PrefillStoryCache(npcList, options, worldRevision, storyPrefillDefinitions, summary)
                : PrefillCodexCuratedStoryCache(npcList, options, worldRevision, storyPrefillDefinitions, summary);
            AddStoryCachePrefillSummaryMessages(summary);

            return summary;
        }

        public DynamicQuestStoryCachePrefillPlanSnapshot GetStoryCachePrefillPlanSnapshot(
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedOptions options,
            int sampleLimit = 20)
        {
            options ??= DynamicQuestSeedOptions.FromProperties();
            List<DynamicQuestSeedNpc> npcList = (npcs ?? Array.Empty<DynamicQuestSeedNpc>())
                .Where(IsUsableSeedNpc)
                .ToList();
            IList<DynamicQuestSeedDefinition> rawCandidates = BuildStoryCachePrefillDefinitions(npcList, options);
            int configuredDefinitions = options.Definitions?.Count ?? 0;
            List<DynamicQuestSeedDefinition> candidates = rawCandidates
                .Where(definition => !HasAutoAcceptDummyDifficultyFailure(definition))
                .ToList();
            int existingDefinitions = rawCandidates
                .Take(configuredDefinitions)
                .Count(definition => !HasAutoAcceptDummyDifficultyFailure(definition));
            int worldCandidates = Math.Max(0, candidates.Count - existingDefinitions);
            List<DbDynamicQuestTemplate> activeRows = GetActiveStoryCacheRows().ToList();
            bool canGenerate = activeRows.Count < StoryCacheMaxTemplates();
            List<string> reasons = BuildStoryCachePrefillPlanReasons(options, npcList.Count, candidates.Count, worldCandidates, canGenerate);

            int normalizedSampleLimit = Math.Clamp(sampleLimit <= 0 ? 20 : sampleLimit, 1, 100);
            return new DynamicQuestStoryCachePrefillPlanSnapshot
            {
                Enabled = options.Enabled,
                DynamicQuestEnabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                UseLlm = options.UseLlm,
                WorldPrefillEnabled = Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED,
                CanGenerateNewStory = canGenerate,
                ScannedNpcs = npcList.Count,
                ExistingDefinitions = existingDefinitions,
                WorldCandidates = worldCandidates,
                TotalCandidates = candidates.Count,
                BatchSize = StoryCachePrefillBatchSize(),
                MaxTemplates = StoryCacheMaxTemplates(),
                ActiveTemplates = activeRows.Count,
                ReadyActiveTemplates = activeRows.Count(IsStoryCacheReadyForUse),
                MaxWorldCandidates = StoryCacheWorldPrefillMaxCandidates(),
                ByRealm = CountBy(candidates, definition => RealmNameForRegion(definition.RegionId)),
                ByStartMode = CountBy(candidates, definition => definition.StartMode.ToString()),
                Reasons = reasons,
                Samples = candidates
                    .Take(normalizedSampleLimit)
                    .Select(BuildStoryCachePrefillCandidate)
                    .ToList()
            };
        }

        public DynamicQuestStoryCacheSnapshot GetStoryCacheSnapshot(int limit, bool includeText = false)
        {
            int normalizedLimit = Math.Clamp(limit <= 0 ? 50 : limit, 1, StoryCacheMaxTemplates());
            List<DbDynamicQuestTemplate> rows = GetActiveStoryCacheRows().ToList();
            List<DynamicQuestStoryCacheItem> items = rows
                .OrderBy(StoryCacheCurrentQualityScore)
                .ThenBy(row => EffectiveLastUsed(row))
                .ThenBy(row => row.TemplateId, StringComparer.OrdinalIgnoreCase)
                .Take(normalizedLimit)
                .Select(row => BuildStoryCacheItem(row, includeText))
                .ToList();

            return new DynamicQuestStoryCacheSnapshot
            {
                GeneratedAt = UtcNow(),
                Limit = normalizedLimit,
                TotalActive = rows.Count,
                ReadyActive = rows.Count(IsStoryCacheReadyForUse),
                OfferEligibleActive = rows.Count(IsStoryCacheOfferEligibleForRepository),
                DummyUnevaluatedOfferBlocked = rows.Count(row =>
                    row.DummyEvaluationCount <= 0 &&
                    IsStoryCacheReadyForUse(row) &&
                    !IsStoryCacheOfferEligibleForRepository(row)),
                MissingNarrative = rows.Count(row => ParseStoryCacheNarrativeScenes(row.StoryNarrativeJson, includeText: false).Count == 0),
                MissingPresentation = rows.Count(row => ParseStoryCachePresentationBeats(row.StoryPresentationJson, includeText: false).Count == 0),
                DummyEvaluatedActive = rows.Count(row => row.DummyEvaluationCount > 0),
                DummyEvaluatedReady = rows.Count(row => row.DummyEvaluationCount > 0 && IsStoryCacheReadyForUse(row)),
                DummyUnevaluatedReady = rows.Count(row => row.DummyEvaluationCount <= 0 && IsStoryCacheReadyForUse(row)),
                DummyFailedActive = rows.Count(HasFailedDummyEvaluation),
                Returned = items.Count,
                IncludeText = includeText,
                ByRealm = CountBy(rows, row => RealmNameForRegion(row.PreferredRegionId)),
                ByProvider = CountBy(rows, row => row.StoryProvider),
                ByModel = CountBy(rows, row => row.StoryModel),
                ByStartMode = CountBy(rows, row => ParseStoryCacheStartMode(row.StartMode).ToString()),
                ByArchetype = CountStoryCacheByArchetype(rows),
                ReadyByArchetype = CountStoryCacheByArchetype(rows, IsStoryCacheReadyForUse),
                OfferEligibleByArchetype = CountStoryCacheByArchetype(rows, IsStoryCacheOfferEligibleForRepository),
                DummyUnevaluatedOfferBlockedByArchetype = CountStoryCacheByArchetype(rows, row =>
                    row.DummyEvaluationCount <= 0 &&
                    IsStoryCacheReadyForUse(row) &&
                    !IsStoryCacheOfferEligibleForRepository(row)),
                NotReadyByReason = CountStoryCacheNotReadyReasons(rows),
                WarningsByReason = CountStoryCacheWarnings(rows),
                Items = items
            };
        }

        public DynamicQuestDummyEvaluationResult SubmitDummyEvaluation(DynamicQuestDummyEvaluationRequest request)
        {
            request ??= new DynamicQuestDummyEvaluationRequest();
            bool enabled = Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED;
            int minimumScore = request.MinimumScore > 0
                ? Math.Clamp(request.MinimumScore, 1, 100)
                : Math.Clamp(Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE, 1, 100);
            int score = Math.Clamp(request.Score, 0, 100);
            int skyrimGradeScore = Math.Clamp(request.SkyrimGradeScore, 0, 100);
            int cinematicDensityScore = Math.Clamp(request.CinematicDensityScore, 0, 100);
            bool belowThreshold = score < minimumScore ||
                                  (request.SkyrimGradeScore > 0 && skyrimGradeScore < minimumScore) ||
                                  (request.CinematicDensityScore > 0 && cinematicDensityScore < minimumScore);
            string questId = (request.QuestId ?? string.Empty).Trim();
            string templateId = (request.TemplateId ?? string.Empty).Trim();

            if (string.IsNullOrWhiteSpace(templateId) && !string.IsNullOrWhiteSpace(questId))
                templateId = DynamicQuestRuntimeService.Instance.GetTemplateIdForQuest(questId);

            DynamicQuestDummyEvaluationResult result = new()
            {
                Enabled = enabled,
                Accepted = false,
                GeneratedAt = UtcNow(),
                QuestId = questId,
                TemplateId = templateId,
                Score = score,
                MinimumScore = minimumScore,
                BelowThreshold = belowThreshold
            };

            if (!enabled)
            {
                result.Message = "dummy evaluation is disabled";
                return result;
            }

            if (string.IsNullOrWhiteSpace(templateId))
            {
                result.Message = "missing template id";
                return result;
            }

            DbDynamicQuestTemplate row = m_templateRepository.Find(templateId);
            if (row == null && !string.Equals(templateId, questId, StringComparison.OrdinalIgnoreCase))
                row = m_templateRepository.Find(questId);

            if (row == null)
            {
                result.Message = "template not found";
                return result;
            }

            DateTime now = UtcNow();
            row.DummyEvaluationScore = score;
            row.DummyEvaluationCount = Math.Max(0, row.DummyEvaluationCount) + 1;
            row.DummyEvaluationJson = BuildDummyEvaluationJson(request, score, minimumScore, now);
            row.DummyEvaluatedAt = now;
            row.UpdatedAt = now;

            DynamicQuestRuntimeRemovalResult removal = null;
            string runtimeTargetName = string.IsNullOrWhiteSpace(request.TargetName)
                ? DynamicQuestRuntimeService.Instance.GetTargetNameForQuest(questId)
                : request.TargetName.Trim();
            bool infrastructureFailure = IsInfrastructureOrNoFreshDummyEvaluation(request.FailureCategory);
            bool runtimeBlockingFailure = !infrastructureFailure && IsRuntimeBlockingDummyEvaluation(request);
            string dummyEvaluationBlockReason = DummyEvaluationBlockReason(row);
            if (belowThreshold && !infrastructureFailure)
            {
                row.IsActive = false;
                removal = DynamicQuestRuntimeService.Instance.RemoveQuestsForTemplate(
                    row.TemplateId,
                    $"dummy_evaluation_below_threshold:{score}/{minimumScore}:skyrim:{skyrimGradeScore}/{minimumScore}:cinematic:{cinematicDensityScore}/{minimumScore}");
            }
            else if (runtimeBlockingFailure)
            {
                string runtimeBlockReason = DummyEvaluationRuntimeBlockReason(request.FailureCategory);
                removal = DynamicQuestRuntimeService.Instance.RemoveQuestsForTemplate(
                    row.TemplateId,
                    $"{runtimeBlockReason}:{request.FailureCategory ?? string.Empty}");
                if (string.Equals(runtimeBlockReason, "dummy_evaluation_difficulty_failed", StringComparison.OrdinalIgnoreCase))
                {
                    removal = MergeRuntimeRemovalResults(
                        removal,
                        RemoveRelatedAutoAcceptDifficultyRuntimeOffers(row, runtimeBlockReason, runtimeTargetName),
                        row.TemplateId,
                        runtimeBlockReason);
                }
            }
            else if (!string.IsNullOrWhiteSpace(dummyEvaluationBlockReason))
            {
                removal = DynamicQuestRuntimeService.Instance.RemoveQuestsForTemplate(
                    row.TemplateId,
                    dummyEvaluationBlockReason);
            }

            bool saved = m_templateRepository.Save(row);
            result.Accepted = saved;
            result.TemplateId = row.TemplateId ?? templateId;
            result.Deactivated = row.IsActive == false;
            result.RemovedRuntimeQuests = removal?.RemovedQuests ?? 0;
            result.CancelledProgress = removal?.CancelledProgress ?? 0;
            result.Message = saved
                ? result.BelowThreshold ? "dummy evaluation accepted; template deactivated" : "dummy evaluation accepted"
                : "template save failed";
            return result;
        }

        private static bool IsUsableSeedNpc(GameNPC npc)
        {
            return npc != null &&
                   npc.ObjectState is GameObject.eObjectState.Active &&
                   !string.IsNullOrWhiteSpace(npc.Name) &&
                   !string.IsNullOrWhiteSpace(npc.InternalID);
        }

        private static bool IsUsableSeedNpc(DynamicQuestSeedNpc npc)
        {
            return npc != null &&
                   !string.IsNullOrWhiteSpace(npc.Name) &&
                   !string.IsNullOrWhiteSpace(npc.InternalID);
        }

        private static DynamicQuestSeedNpc FindSeedNpc(IEnumerable<DynamicQuestSeedNpc> npcs, DynamicQuestSeedDefinition definition)
        {
            return npcs.FirstOrDefault(npc =>
                (definition.RegionId <= 0 || npc.RegionId == definition.RegionId) &&
                string.Equals(npc.Name, definition.StartNpcName, StringComparison.OrdinalIgnoreCase));
        }

        private static bool HasExistingQuestForDefinition(
            DynamicQuestSeedNpc npc,
            DynamicQuestSeedDefinition definition,
            string worldRevision)
        {
            string questId = BuildStableQuestId(npc, definition);
            return HasExistingQuestForTemplate(questId, worldRevision);
        }

        private static bool ShouldRebindOnSeed(DynamicQuestSeedDefinition definition)
        {
            return definition != null &&
                   (!string.IsNullOrWhiteSpace(definition.StartSelector) ||
                    !string.IsNullOrWhiteSpace(definition.TargetSelector));
        }

        private static bool HasExistingQuestForTemplate(string templateId, string worldRevision)
        {
            return FindRuntimeQuestForTemplate(templateId, worldRevision) != null;
        }

        private static DynamicQuestDefinition FindRuntimeQuestForTemplate(string templateId, string worldRevision)
        {
            templateId = (templateId ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(templateId))
                return null;

            string normalizedWorldRevision = NormalizeWorldRevision(worldRevision);
            return DynamicQuestRuntimeService.Instance.GetQuests().FirstOrDefault(quest =>
                QuestMatchesTemplate(quest, templateId) &&
                string.Equals(NormalizeWorldRevision(quest.WorldRevision), normalizedWorldRevision, StringComparison.OrdinalIgnoreCase));
        }

        private static bool QuestMatchesTemplate(DynamicQuestDefinition quest, string templateId)
        {
            if (quest == null || string.IsNullOrWhiteSpace(templateId))
                return false;

            if (string.Equals(quest.Id, templateId, StringComparison.OrdinalIgnoreCase))
                return true;

            return (quest.Tags ?? Array.Empty<string>()).Any(tag =>
                string.Equals(tag, $"template:{templateId}", StringComparison.OrdinalIgnoreCase));
        }

        private static DynamicQuestSeedNpc FindTargetNpc(IEnumerable<DynamicQuestSeedNpc> npcs, DynamicQuestSeedNpc startNpc, DynamicQuestSeedDefinition definition)
        {
            ushort targetRegion = TargetRegion(startNpc, definition);
            IEnumerable<DynamicQuestSeedNpc> candidates = NpcsOrEmpty(npcs)
                .Where(npc => npc.RegionId == targetRegion)
                .Where(npc => startNpc == null || !string.Equals(npc.InternalID, startNpc.InternalID, StringComparison.OrdinalIgnoreCase))
                .Where(npc => string.Equals(npc.Name, definition.TargetName, StringComparison.OrdinalIgnoreCase))
                .Where(npc => IsLevelInDefinition(npc, definition));
            IEnumerable<DynamicQuestSeedNpc> likelyTargets = candidates.Where(IsLikelyWorldQuestTarget);
            if (likelyTargets.Any())
                candidates = likelyTargets;

            return RankTargetCandidates(candidates, npcs, startNpc, definition)
                .FirstOrDefault();
        }

        private static DynamicQuestSeedResolveResult ResolveDefinition(
            IList<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedDefinition definition)
        {
            DynamicQuestSeedDefinition resolved = CopyDefinition(definition);
            DynamicQuestSeedNpc startNpc = null;

            if (RequiresStartNpc(resolved))
            {
                if (ShouldSelectNearbyStartTargetPair(resolved))
                {
                    (DynamicQuestSeedNpc pairStart, DynamicQuestSeedNpc pairTarget, string pairMessage) = SelectNearbyStartTargetPair(npcs, resolved);
                    if (pairStart == null)
                        return DynamicQuestSeedResolveResult.Skip(
                            resolved,
                            string.IsNullOrWhiteSpace(pairMessage)
                                ? $"selector start npc not found: {resolved.StartNpcName} region={resolved.RegionId}"
                                : pairMessage);
                    if (pairTarget == null)
                        return DynamicQuestSeedResolveResult.Skip(
                            resolved,
                            string.IsNullOrWhiteSpace(pairMessage)
                                ? $"selector target npc not found: {resolved.TargetName} region={TargetRegion(pairStart, resolved)}"
                                : pairMessage);

                    startNpc = pairStart;
                    resolved.StartNpcName = pairStart.Name ?? string.Empty;
                    resolved.TargetName = pairTarget.Name ?? string.Empty;
                    return DynamicQuestSeedResolveResult.Ok(resolved, startNpc, pairTarget);
                }

                startNpc = !string.IsNullOrWhiteSpace(resolved.StartSelector)
                    ? SelectStartNpcForSelector(npcs, resolved)
                    : FindSeedNpc(npcs, resolved);
                if (startNpc == null)
                    return DynamicQuestSeedResolveResult.Skip(
                        resolved,
                        $"selector start npc not found: {resolved.StartNpcName} region={resolved.RegionId}");

                resolved.StartNpcName = startNpc.Name ?? string.Empty;
            }
            else if (!string.IsNullOrWhiteSpace(resolved.StartSelector))
            {
                resolved.StartNpcName = string.Empty;
            }

            if (!string.IsNullOrWhiteSpace(resolved.TargetSelector))
            {
                DynamicQuestSeedNpc targetNpc = SelectTargetNpcForSelector(npcs, startNpc, resolved);
                if (targetNpc == null)
                    return DynamicQuestSeedResolveResult.Skip(
                        resolved,
                        $"selector target npc not found: {resolved.TargetName} region={TargetRegion(startNpc, resolved)}");

                resolved.TargetName = targetNpc.Name ?? string.Empty;
                return DynamicQuestSeedResolveResult.Ok(resolved, startNpc, targetNpc);
            }

            DynamicQuestSeedNpc fixedTargetNpc = FindTargetNpc(npcs, startNpc, resolved);
            return DynamicQuestSeedResolveResult.Ok(resolved, startNpc, fixedTargetNpc);
        }

        private static bool ShouldSelectNearbyStartTargetPair(DynamicQuestSeedDefinition definition)
        {
            return RequiresStartNpc(definition) &&
                   !string.IsNullOrWhiteSpace(definition.StartSelector) &&
                   NormalizeSelector(definition.TargetSelector) is "hostile-near-start" or "near-start";
        }

        private static DynamicQuestSeedDefinition CopyDefinition(DynamicQuestSeedDefinition definition)
        {
            if (definition == null)
                return new DynamicQuestSeedDefinition();

            return new DynamicQuestSeedDefinition
            {
                StartNpcName = definition.StartNpcName ?? string.Empty,
                RegionId = definition.RegionId,
                TargetName = definition.TargetName ?? string.Empty,
                Count = definition.Count,
                MinLevel = definition.MinLevel,
                MaxLevel = definition.MaxLevel,
                StartMode = definition.StartMode,
                Trigger = definition.Trigger ?? string.Empty,
                StartSelector = definition.StartSelector ?? string.Empty,
                TargetSelector = definition.TargetSelector ?? string.Empty,
                BranchWorldSignal = definition.BranchWorldSignal ?? string.Empty
            };
        }

        private static DynamicQuestSeedNpc SelectStartNpcForSelector(
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedDefinition definition)
        {
            string selector = NormalizeSelector(definition.StartSelector);
            List<DynamicQuestSeedNpc> candidates = StartNpcCandidatesForSelector(npcs, definition).ToList();

            if (StartSelectorRequiresQuestGiver(selector))
            {
                List<DynamicQuestSeedNpc> likelyQuestGivers = candidates.Where(IsLikelyDynamicQuestStartNpc).ToList();
                List<DynamicQuestSeedNpc> fallbackQuestGivers = candidates
                    .Where(IsLikelyQuestGiver)
                    .Where(npc => likelyQuestGivers.All(preferred =>
                        !string.Equals(preferred.InternalID, npc.InternalID, StringComparison.OrdinalIgnoreCase)))
                    .ToList();
                if (likelyQuestGivers.Count == 0 && fallbackQuestGivers.Count == 0)
                    return null;

                candidates = likelyQuestGivers.Count > 0
                    ? likelyQuestGivers
                    : fallbackQuestGivers;
                candidates = PreferSafeStartNpcs(candidates, npcs).ToList();

                return candidates
                    .OrderByDescending(npc => npc.Level)
                    .ThenBy(npc => npc.Name, StringComparer.OrdinalIgnoreCase)
                    .ThenBy(npc => npc.InternalID, StringComparer.OrdinalIgnoreCase)
                    .FirstOrDefault();
            }

            return candidates
                .OrderBy(npc => npc.Name, StringComparer.OrdinalIgnoreCase)
                .ThenBy(npc => npc.InternalID, StringComparer.OrdinalIgnoreCase)
                .FirstOrDefault();
        }

        private static IEnumerable<DynamicQuestSeedNpc> StartNpcCandidatesForSelector(
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedDefinition definition)
        {
            return NpcsOrEmpty(npcs)
                .Where(npc => definition.RegionId <= 0 || npc.RegionId == definition.RegionId);
        }

        private static (DynamicQuestSeedNpc StartNpc, DynamicQuestSeedNpc TargetNpc, string Message) SelectNearbyStartTargetPair(
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedDefinition definition)
        {
            List<DynamicQuestSeedNpc> npcList = NpcsOrEmpty(npcs).ToList();
            List<DynamicQuestSeedNpc> startCandidates = StartNpcCandidatesForSelector(npcs, definition).ToList();
            List<DynamicQuestSeedNpc> likelyQuestGivers = startCandidates.Where(IsLikelyDynamicQuestStartNpc).ToList();
            List<DynamicQuestSeedNpc> fallbackQuestGivers = startCandidates
                .Where(IsLikelyQuestGiver)
                .Where(npc => likelyQuestGivers.All(preferred =>
                    !string.Equals(preferred.InternalID, npc.InternalID, StringComparison.OrdinalIgnoreCase)))
                .ToList();
            if (StartSelectorRequiresQuestGiver(definition.StartSelector))
            {
                if (likelyQuestGivers.Count == 0 && fallbackQuestGivers.Count == 0)
                    return (null, null, $"selector start npc not found: {definition.StartNpcName} region={definition.RegionId} startCandidates={startCandidates.Count} likelyQuestGivers=0 fallbackQuestGivers=0");

                if (likelyQuestGivers.Count > 0)
                {
                    List<DynamicQuestSeedNpc> safeStartCandidates = likelyQuestGivers
                        .Where(candidate => IsSafeStartNpc(candidate, npcList))
                        .ToList();
                    if (safeStartCandidates.Count > 0)
                    {
                        var safePair = SelectBestNearbyStartTargetPair(npcList, definition, safeStartCandidates);
                        if (safePair.StartNpc != null)
                            return (safePair.StartNpc, safePair.TargetNpc, string.Empty);
                    }

                    var preferredPair = SelectBestNearbyStartTargetPair(npcList, definition, likelyQuestGivers);
                    if (preferredPair.StartNpc != null)
                        return (preferredPair.StartNpc, preferredPair.TargetNpc, string.Empty);

                    if (fallbackQuestGivers.Count == 0)
                        return (null, null, DescribeNearbyStartTargetPairMiss(npcList, definition, likelyQuestGivers, likelyQuestGivers.Count, fallbackQuestGivers.Count, 0));
                }

                startCandidates = fallbackQuestGivers;
            }
            else if (likelyQuestGivers.Count > 0)
            {
                startCandidates = likelyQuestGivers;
            }

            startCandidates = OrderStartCandidatesWithSafePreferred(startCandidates, npcs).ToList();
            var selectedPair = SelectBestNearbyStartTargetPair(npcList, definition, startCandidates);
            if (selectedPair.StartNpc != null)
                return (selectedPair.StartNpc, selectedPair.TargetNpc, string.Empty);

            return (null, null, DescribeNearbyStartTargetPairMiss(npcList, definition, startCandidates, likelyQuestGivers.Count, fallbackQuestGivers.Count, 0));
        }

        private static (DynamicQuestSeedNpc StartNpc, DynamicQuestSeedNpc TargetNpc) SelectBestNearbyStartTargetPair(
            IList<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedDefinition definition,
            IList<DynamicQuestSeedNpc> startCandidates)
        {
            var pairs = (startCandidates ?? Array.Empty<DynamicQuestSeedNpc>())
                .Select(startNpc => new
                {
                    StartNpc = startNpc,
                    TargetNpc = SelectTargetNpcForSelector(npcs, startNpc, definition)
                })
                .ToList();

            var bestPair = pairs
                .Where(pair => pair.TargetNpc != null)
                .OrderBy(pair => TargetStarterUnsafeNameRank(pair.TargetNpc, definition))
                .ThenBy(pair => TargetGrowthRiskRank(pair.TargetNpc, definition))
                .ThenBy(pair => TargetAggressionRank(pair.TargetNpc, definition))
                .ThenBy(pair => TargetAreaThreatRank(npcs, pair.TargetNpc, definition))
                .ThenBy(pair => TargetRouteThreatRank(npcs, pair.StartNpc, pair.TargetNpc, definition))
                .ThenBy(pair => TargetStartDistanceRank(pair.StartNpc, pair.TargetNpc))
                .ThenBy(pair => TargetStarterPreyNameRank(pair.TargetNpc, definition))
                .ThenBy(pair => DistanceSquared(pair.StartNpc, pair.TargetNpc))
                .ThenByDescending(pair => pair.StartNpc.Level)
                .ThenBy(pair => pair.StartNpc.Name, StringComparer.OrdinalIgnoreCase)
                .ThenBy(pair => pair.StartNpc.InternalID, StringComparer.OrdinalIgnoreCase)
                .FirstOrDefault();

            return bestPair == null
                ? (null, null)
                : (bestPair.StartNpc, bestPair.TargetNpc);
        }

        private static string DescribeNearbyStartTargetPairMiss(
            IList<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedDefinition definition,
            IList<DynamicQuestSeedNpc> startCandidates,
            int likelyQuestGiverCount,
            int fallbackQuestGiverCount,
            int startsWithTargets)
        {
            StringBuilder builder = new();
            builder.Append("selector near-start pair not found");
            builder.Append($" region={definition.RegionId}");
            builder.Append($" startCandidates={startCandidates?.Count ?? 0}");
            builder.Append($" likelyQuestGivers={likelyQuestGiverCount}");
            builder.Append($" fallbackQuestGivers={fallbackQuestGiverCount}");
            builder.Append($" startsWithTargets={startsWithTargets}");

            if (startCandidates == null || startCandidates.Count == 0)
                return builder.ToString();

            builder.Append(" samples=");
            builder.Append(string.Join("; ", startCandidates.Take(5).Select(startNpc =>
            {
                NearbyTargetCandidateStats stats = CountNearbyTargetCandidateStats(npcs, startNpc, definition);
                return $"{startNpc.Name}@{startNpc.X},{startNpc.Y}:candidates={stats.Candidates},likely={stats.LikelyTargets},near={stats.Nearby},safe={stats.NearbySafe},expandedSafe={stats.ExpandedSafe}";
            })));
            return builder.ToString();
        }

        private readonly struct NearbyTargetCandidateStats
        {
            public NearbyTargetCandidateStats(int candidates, int likelyTargets, int nearby, int nearbySafe, int expandedSafe)
            {
                Candidates = candidates;
                LikelyTargets = likelyTargets;
                Nearby = nearby;
                NearbySafe = nearbySafe;
                ExpandedSafe = expandedSafe;
            }

            public int Candidates { get; }
            public int LikelyTargets { get; }
            public int Nearby { get; }
            public int NearbySafe { get; }
            public int ExpandedSafe { get; }
        }

        private static NearbyTargetCandidateStats CountNearbyTargetCandidateStats(
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedNpc startNpc,
            DynamicQuestSeedDefinition definition)
        {
            ushort targetRegion = TargetRegion(startNpc, definition);
            List<DynamicQuestSeedNpc> candidates = NpcsOrEmpty(npcs)
                .Where(npc => targetRegion == 0 || npc.RegionId == targetRegion)
                .Where(npc => startNpc == null || !string.Equals(npc.InternalID, startNpc.InternalID, StringComparison.OrdinalIgnoreCase))
                .Where(npc => IsLevelInDefinition(npc, definition))
                .ToList();
            List<DynamicQuestSeedNpc> likelyTargets = candidates.Where(IsLikelyWorldQuestTarget).ToList();
            List<DynamicQuestSeedNpc> effectiveCandidates = likelyTargets.Count > 0 ? likelyTargets : candidates;
            List<DynamicQuestSeedNpc> nearby = RequireTargetsNearStart(effectiveCandidates, startNpc).ToList();
            List<DynamicQuestSeedNpc> expanded = RequireTargetsNearStart(effectiveCandidates, startNpc, NearStartExpandedSafeRadius).ToList();
            ISet<string> severeNameKeys = StarterSevereNameKeys(nearby.Concat(expanded));
            int nearbySafe = nearby.Count(npc => IsStarterTargetSafeForSolo(npc, definition, npcs, startNpc, severeNameKeys));
            int expandedSafe = expanded.Count(npc => IsStarterTargetSafeForSolo(npc, definition, npcs, startNpc, severeNameKeys));

            return new NearbyTargetCandidateStats(
                candidates.Count,
                likelyTargets.Count,
                nearby.Count,
                nearbySafe,
                expandedSafe);
        }

        private static DynamicQuestSeedNpc SelectTargetNpcForSelector(
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedNpc startNpc,
            DynamicQuestSeedDefinition definition)
        {
            string selector = NormalizeSelector(definition.TargetSelector);
            ushort targetRegion = TargetRegion(startNpc, definition);
            IEnumerable<DynamicQuestSeedNpc> candidates = NpcsOrEmpty(npcs)
                .Where(npc => targetRegion == 0 || npc.RegionId == targetRegion)
                .Where(npc => startNpc == null || !string.Equals(npc.InternalID, startNpc.InternalID, StringComparison.OrdinalIgnoreCase))
                .Where(npc => IsLevelInDefinition(npc, definition));
            IEnumerable<DynamicQuestSeedNpc> likelyTargets = candidates.Where(IsLikelyWorldQuestTarget);
            if (likelyTargets.Any())
                candidates = likelyTargets;

            if (selector is "hostile-near-start" or "near-start")
            {
                return NearbyTargetCandidatesToRank(candidates, npcs, startNpc, definition)
                    .OrderBy(npc => TargetStarterUnsafeNameRank(npc, definition))
                    .ThenBy(npc => TargetGrowthRiskRank(npc, definition))
                    .ThenBy(npc => TargetSafetyRankLevel(npc, definition))
                    .ThenBy(npc => TargetAggressionRank(npc, definition))
                    .ThenBy(npc => TargetAreaThreatRank(npcs, npc, definition))
                    .ThenBy(npc => TargetRouteThreatRank(npcs, startNpc, npc, definition))
                    .ThenBy(npc => TargetStartDistanceRank(startNpc, npc))
                    .ThenBy(npc => TargetStarterPreyNameRank(npc, definition))
                    .ThenBy(npc => startNpc == null ? 0 : DistanceSquared(startNpc, npc))
                    .ThenBy(npc => npc.Name, StringComparer.OrdinalIgnoreCase)
                    .ThenBy(npc => npc.InternalID, StringComparer.OrdinalIgnoreCase)
                    .FirstOrDefault();
            }

            return RankTargetCandidates(candidates, npcs, startNpc, definition)
                .FirstOrDefault();
        }

        private static IOrderedEnumerable<DynamicQuestSeedNpc> RankTargetCandidates(
            IEnumerable<DynamicQuestSeedNpc> candidates,
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedNpc startNpc,
            DynamicQuestSeedDefinition definition)
        {
            return (candidates ?? Array.Empty<DynamicQuestSeedNpc>())
                .OrderBy(npc => TargetStarterUnsafeNameRank(npc, definition))
                .ThenBy(npc => TargetGrowthRiskRank(npc, definition))
                .ThenBy(npc => TargetSafetyRankLevel(npc, definition))
                .ThenBy(npc => TargetAggressionRank(npc, definition))
                .ThenBy(npc => TargetAreaThreatRank(npcs, npc, definition))
                .ThenBy(npc => TargetRouteThreatRank(npcs, startNpc, npc, definition))
                .ThenBy(npc => TargetStartDistanceRank(startNpc, npc))
                .ThenBy(npc => TargetStarterPreyNameRank(npc, definition))
                .ThenBy(npc => startNpc == null ? 0 : DistanceSquared(startNpc, npc))
                .ThenBy(npc => npc.Name, StringComparer.OrdinalIgnoreCase)
                .ThenBy(npc => npc.InternalID, StringComparer.OrdinalIgnoreCase);
        }

        private static int TargetSafetyRankLevel(DynamicQuestSeedNpc npc, DynamicQuestSeedDefinition definition)
        {
            int minLevel = Math.Clamp(definition?.MinLevel ?? 1, 1, 50);
            int effectiveLevel = EffectiveQuestLevel(npc);
            return Math.Abs((effectiveLevel <= 0 ? minLevel : effectiveLevel) - minLevel);
        }

        private static bool IsLevelInDefinition(DynamicQuestSeedNpc npc, DynamicQuestSeedDefinition definition)
        {
            if (npc == null || definition == null)
                return false;

            int level = EffectiveQuestLevel(npc);
            return level <= 0 || (level >= definition.MinLevel && level <= definition.MaxLevel);
        }

        private static int EffectiveQuestLevel(DynamicQuestSeedNpc npc)
        {
            if (npc == null)
                return 0;

            return npc.GrowthEffectiveLevel > 0 ? npc.GrowthEffectiveLevel : npc.Level;
        }

        private static IEnumerable<DynamicQuestSeedNpc> RequireTargetsNearStart(
            IEnumerable<DynamicQuestSeedNpc> candidates,
            DynamicQuestSeedNpc startNpc)
        {
            return RequireTargetsNearStart(candidates, startNpc, NearStartPreferredRadius);
        }

        private static IEnumerable<DynamicQuestSeedNpc> RequireTargetsNearStart(
            IEnumerable<DynamicQuestSeedNpc> candidates,
            DynamicQuestSeedNpc startNpc,
            int radius)
        {
            if (startNpc == null)
                return candidates;

            long preferredRadiusSquared = (long)Math.Max(1, radius) * Math.Max(1, radius);
            return (candidates ?? Array.Empty<DynamicQuestSeedNpc>())
                .Where(npc => DistanceSquared(startNpc, npc) <= preferredRadiusSquared);
        }

        private static IList<DynamicQuestSeedNpc> NearbyTargetCandidatesToRank(
            IEnumerable<DynamicQuestSeedNpc> candidates,
            IEnumerable<DynamicQuestSeedNpc> allNpcs,
            DynamicQuestSeedNpc startNpc,
            DynamicQuestSeedDefinition definition)
        {
            List<DynamicQuestSeedNpc> candidateList = (candidates ?? Array.Empty<DynamicQuestSeedNpc>()).ToList();
            List<DynamicQuestSeedNpc> nearbyCandidates = RequireTargetsNearStart(candidateList, startNpc).ToList();
            if (IsStarterBand(definition) && startNpc != null)
            {
                List<DynamicQuestSeedNpc> expandedCandidates = RequireTargetsNearStart(candidateList, startNpc, NearStartExpandedSafeRadius).ToList();
                ISet<string> severeNameKeys = StarterSevereNameKeys(nearbyCandidates.Concat(expandedCandidates));
                List<DynamicQuestSeedNpc> nearbySafeCandidates = nearbyCandidates
                    .Where(npc => IsStarterTargetSafeForSolo(npc, definition, allNpcs, startNpc, severeNameKeys))
                    .ToList();

                List<DynamicQuestSeedNpc> expandedSafeCandidates = expandedCandidates
                    .Where(npc => IsStarterTargetSafeForSolo(npc, definition, allNpcs, startNpc, severeNameKeys))
                    .ToList();
                List<DynamicQuestSeedNpc> safeCandidates = nearbySafeCandidates
                    .Concat(expandedSafeCandidates)
                    .GroupBy(npc => npc.InternalID ?? string.Empty, StringComparer.OrdinalIgnoreCase)
                    .Select(group => group.First())
                    .ToList();
                if (safeCandidates.Count > 0)
                    return safeCandidates;

                if (nearbyCandidates.Count > 0)
                {
                    return Array.Empty<DynamicQuestSeedNpc>();
                }
            }

            if (nearbyCandidates.Count <= MaxNearbyTargetCandidatesToRank)
                return nearbyCandidates;

            return nearbyCandidates
                .OrderBy(npc => TargetStarterUnsafeNameRank(npc, definition))
                .ThenBy(npc => TargetGrowthRiskRank(npc, definition))
                .ThenBy(npc => Math.Abs((npc.Level <= 0 ? definition.MinLevel : npc.Level) - definition.MinLevel))
                .ThenBy(npc => TargetStartDistanceRank(startNpc, npc))
                .ThenBy(npc => TargetStarterPreyNameRank(npc, definition))
                .ThenBy(npc => TargetAggressionRank(npc, definition))
                .ThenBy(npc => startNpc == null ? 0 : DistanceSquared(startNpc, npc))
                .ThenBy(npc => npc.Name, StringComparer.OrdinalIgnoreCase)
                .ThenBy(npc => npc.InternalID, StringComparer.OrdinalIgnoreCase)
                .Take(MaxNearbyTargetCandidatesToRank)
                .ToList();
        }

        private static IEnumerable<DynamicQuestSeedNpc> PreferSafeStartNpcs(
            IEnumerable<DynamicQuestSeedNpc> startCandidates,
            IEnumerable<DynamicQuestSeedNpc> npcs)
        {
            List<DynamicQuestSeedNpc> candidates = (startCandidates ?? Array.Empty<DynamicQuestSeedNpc>()).ToList();
            if (candidates.Count <= 1)
                return candidates;

            List<DynamicQuestSeedNpc> safeCandidates = candidates
                .Where(candidate => IsSafeStartNpc(candidate, npcs))
                .ToList();

            return safeCandidates.Count > 0 ? safeCandidates : candidates;
        }

        private static IEnumerable<DynamicQuestSeedNpc> OrderStartCandidatesWithSafePreferred(
            IEnumerable<DynamicQuestSeedNpc> startCandidates,
            IEnumerable<DynamicQuestSeedNpc> npcs)
        {
            List<DynamicQuestSeedNpc> candidates = (startCandidates ?? Array.Empty<DynamicQuestSeedNpc>()).ToList();
            if (candidates.Count <= 1)
                return candidates;

            List<DynamicQuestSeedNpc> safeCandidates = candidates
                .Where(candidate => IsSafeStartNpc(candidate, npcs))
                .ToList();
            if (safeCandidates.Count == 0)
                return candidates;

            HashSet<string> safeIds = new(safeCandidates.Select(candidate => candidate.InternalID), StringComparer.OrdinalIgnoreCase);
            return safeCandidates.Concat(candidates.Where(candidate => !safeIds.Contains(candidate.InternalID)));
        }

        private static bool IsSafeStartNpc(DynamicQuestSeedNpc startNpc, IEnumerable<DynamicQuestSeedNpc> npcs)
        {
            if (startNpc == null)
                return false;

            long clearRadiusSquared = (long)NearStartMinimumSafeTargetDistance * NearStartMinimumSafeTargetDistance;
            return !NpcsOrEmpty(npcs).Any(npc =>
                npc != null &&
                !string.Equals(npc.InternalID, startNpc.InternalID, StringComparison.OrdinalIgnoreCase) &&
                npc.RegionId == startNpc.RegionId &&
                DistanceSquared(startNpc, npc) <= clearRadiusSquared &&
                IsLikelyStartAreaThreat(npc));
        }

        private static bool IsLikelyStartAreaThreat(DynamicQuestSeedNpc npc)
        {
            return IsLikelyWorldQuestTarget(npc) && !IsLikelyQuestGiver(npc);
        }

        private static int TargetAggressionRank(DynamicQuestSeedNpc targetNpc, DynamicQuestSeedDefinition definition)
        {
            if (targetNpc == null || definition == null)
                return 0;

            if (definition.MinLevel > 1 || definition.MaxLevel > 5)
                return 0;

            int rank = 0;
            if (targetNpc.SourceAggroLevel > 0)
                rank += 10 + Math.Clamp(targetNpc.SourceAggroLevel, 0, 100);
            if (targetNpc.SourceAggroRange > 0)
                rank += Math.Min(10, targetNpc.SourceAggroRange / 100);
            return rank;
        }

        private static int TargetStarterUnsafeNameRank(DynamicQuestSeedNpc targetNpc, DynamicQuestSeedDefinition definition)
        {
            if (targetNpc == null || definition == null || definition.MinLevel > 1 || definition.MaxLevel > 5)
                return 0;

            string name = NormalizeNameForSafetyRank(targetNpc.Name);
            if (string.IsNullOrWhiteSpace(name))
                return 0;

            if (IsStarterUnsafeName(name))
                return 30;

            return 0;
        }

        private static bool IsStarterBand(DynamicQuestSeedDefinition definition)
        {
            return definition != null && definition.MinLevel <= 1 && definition.MaxLevel <= 5;
        }

        private static bool IsStarterSevereTargetRisk(DynamicQuestSeedNpc targetNpc, DynamicQuestSeedDefinition definition)
        {
            return IsStarterSevereTargetRisk(targetNpc, definition, null);
        }

        private static bool IsStarterSevereTargetRisk(
            DynamicQuestSeedNpc targetNpc,
            DynamicQuestSeedDefinition definition,
            ISet<string> severeNameKeys)
        {
            if (targetNpc == null || !IsStarterBand(definition))
                return false;

            if (severeNameKeys != null)
            {
                string liveName = string.IsNullOrWhiteSpace(targetNpc.RawName) ? targetNpc.Name : targetNpc.RawName;
                string normalized = NormalizeGrowthRiskName(liveName);
                string stripped = StripMobGrowthNamePrefix(normalized);
                if (severeNameKeys.Contains(GrowthNameRiskKey(targetNpc.RegionId, normalized)) ||
                    (!string.IsNullOrWhiteSpace(stripped) &&
                     severeNameKeys.Contains(GrowthNameRiskKey(targetNpc.RegionId, stripped))))
                {
                    return true;
                }
            }

            if (targetNpc.Level > StarterMaxSoloSafeTargetLevel)
                return true;

            return IsStarterUnsafeName(targetNpc.Name) ||
                   TargetAggressionRank(targetNpc, definition) > 0 ||
                   IsStarterActiveGrowthThreat(targetNpc) ||
                   HasStarterSevereNameGrowthStats(targetNpc);
        }

        private static ISet<string> StarterSevereNameKeys(IEnumerable<DynamicQuestSeedNpc> candidates)
        {
            HashSet<string> keys = new(StringComparer.OrdinalIgnoreCase);
            foreach (DynamicQuestSeedNpc npc in candidates ?? Array.Empty<DynamicQuestSeedNpc>())
            {
                if (npc == null || npc.RegionId <= 0)
                    continue;

                string liveName = string.IsNullOrWhiteSpace(npc.RawName) ? npc.Name : npc.RawName;
                string normalized = NormalizeGrowthRiskName(liveName);
                string stripped = StripMobGrowthNamePrefix(normalized);
                bool hasGrowthNamePrefix = !string.Equals(normalized, stripped, StringComparison.OrdinalIgnoreCase);
                if (!IsStarterLocalSevereNameKeyRisk(npc, normalized, hasGrowthNamePrefix))
                    continue;

                keys.Add(GrowthNameRiskKey(npc.RegionId, stripped));
            }

            return keys;
        }

        private static bool IsStarterLocalSevereNameKeyRisk(DynamicQuestSeedNpc npc, string normalizedName, bool hasGrowthNamePrefix)
        {
            if (npc == null)
                return false;

            int effectiveLevel = npc.GrowthEffectiveLevel > 0 ? npc.GrowthEffectiveLevel : npc.Level;
            if (npc.Level > StarterMaxSoloSafeTargetLevel || effectiveLevel > StarterMaxSoloSafeTargetLevel)
                return true;

            if (npc.GrowthIsMutant || npc.GrowthMutationPending || npc.GrowthPlayerKills > 0)
                return true;

            if (!string.IsNullOrWhiteSpace(npc.GrowthStage) &&
                !string.Equals(npc.GrowthStage, MobGrowthStages.Normal, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            if (HasStarterSevereNameGrowthStats(npc))
                return true;

            return hasGrowthNamePrefix && HasSevereGrowthNamePrefix(normalizedName);
        }

        private static bool IsStarterSevereGrowthNameRisk(DynamicQuestSeedNpc npc, string normalizedName, bool hasGrowthNamePrefix)
        {
            if (npc == null)
                return false;

            int effectiveLevel = npc.GrowthEffectiveLevel > 0 ? npc.GrowthEffectiveLevel : npc.Level;
            if (npc.GrowthIsMutant ||
                npc.GrowthMutationPending ||
                npc.GrowthPlayerKills > 0 ||
                effectiveLevel > StarterMaxSoloSafeTargetLevel)
            {
                return true;
            }

            return hasGrowthNamePrefix && HasSevereGrowthNamePrefix(normalizedName);
        }

        private static bool HasStarterSevereNameGrowthStats(DynamicQuestSeedNpc npc)
        {
            return npc != null &&
                   (npc.NameGrowthPlayerKills > 0 ||
                    npc.NameGrowthMaxEffectiveLevel > StarterMaxSoloSafeTargetLevel);
        }

        private static int TargetGrowthRiskRank(DynamicQuestSeedNpc targetNpc, DynamicQuestSeedDefinition definition)
        {
            if (targetNpc == null || definition == null)
                return 0;

            int effectiveLevel = targetNpc.GrowthEffectiveLevel > 0 ? targetNpc.GrowthEffectiveLevel : targetNpc.Level;
            bool starterBand = definition.MinLevel <= 1 && definition.MaxLevel <= 5;
            int rank = 0;

            if (targetNpc.HasGrowthState)
            {
                if (!string.IsNullOrWhiteSpace(targetNpc.GrowthStage) &&
                    !string.Equals(targetNpc.GrowthStage, MobGrowthStages.Normal, StringComparison.OrdinalIgnoreCase))
                {
                    rank += starterBand ? 180 : 40;
                }

                if (targetNpc.GrowthIsMutant || targetNpc.GrowthMutationPending)
                    rank += starterBand ? 220 : 60;

                if (effectiveLevel > definition.MaxLevel)
                    rank += (starterBand ? 140 : 30) + Math.Min(100, (effectiveLevel - definition.MaxLevel) * 20);

                if (targetNpc.GrowthLevel > 0)
                    rank += (starterBand ? 60 : 10) + Math.Min(80, targetNpc.GrowthLevel * 12);

                if (targetNpc.GrowthPlayerKills > 0)
                    rank += (starterBand ? 160 : 40) + Math.Min(120, targetNpc.GrowthPlayerKills * 20);

                if (starterBand && targetNpc.GrowthScore >= 20)
                    rank += Math.Min(80, targetNpc.GrowthScore / 2);
            }

            if (targetNpc.NameGrowthThreatCount > 0)
            {
                rank += starterBand ? 260 : 50;
                rank += Math.Min(starterBand ? 180 : 60, targetNpc.NameGrowthThreatCount * (starterBand ? 25 : 8));

                if (targetNpc.NameGrowthMaxEffectiveLevel > definition.MaxLevel)
                    rank += (starterBand ? 120 : 25) + Math.Min(80, (targetNpc.NameGrowthMaxEffectiveLevel - definition.MaxLevel) * 15);

                if (targetNpc.NameGrowthPlayerKills > 0)
                    rank += (starterBand ? 120 : 30) + Math.Min(100, targetNpc.NameGrowthPlayerKills * 12);

                if (starterBand && targetNpc.NameGrowthMaxScore >= 20)
                    rank += Math.Min(120, targetNpc.NameGrowthMaxScore / 12);
            }

            return rank;
        }

        private static int TargetStarterPreyNameRank(DynamicQuestSeedNpc targetNpc, DynamicQuestSeedDefinition definition)
        {
            if (targetNpc == null || definition == null || definition.MinLevel > 1 || definition.MaxLevel > 5)
                return 0;

            string name = NormalizeNameForSafetyRank(targetNpc.Name);
            if (string.IsNullOrWhiteSpace(name))
                return 10;

            if (ContainsAny(name, "pup", "piglet", "larva", "young ", "soft-shelled", "beetle larva"))
                return 0;

            return 10;
        }

        private static string NormalizeNameForSafetyRank(string name)
        {
            return $" {(name ?? string.Empty).Trim().ToLowerInvariant()} ";
        }

        private static bool IsStarterUnsafeName(string name)
        {
            string normalized = NormalizeNameForSafetyRank(name);
            return ContainsAny(normalized, "large ant", "dragon ant", "giant", "massive", "elder", "ancient", "raider", "brawler", "bandit", "nuisance", "lough wolf cadger", "lynx", "water goblin", "wild hog", "vendo grunt", "hobgoblin", "huldu outcast", "meandering spirit");
        }

        private static bool ContainsAny(string value, params string[] needles)
        {
            return needles.Any(needle => value.Contains(needle, StringComparison.OrdinalIgnoreCase));
        }

        private static int TargetAreaThreatRank(
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedNpc targetNpc,
            DynamicQuestSeedDefinition definition,
            DynamicQuestSeedNpc excludedNpc = null)
        {
            if (targetNpc == null)
                return 0;

            int targetLevel = targetNpc.Level > 0 ? targetNpc.Level : Math.Max(1, definition?.MinLevel ?? 1);
            long radiusSquared = (long)TargetAreaThreatRadius * TargetAreaThreatRadius;
            return NpcsOrEmpty(npcs).Count(npc =>
                !IsSameNpc(npc, excludedNpc) &&
                IsLikelyTargetAreaThreat(npc, targetNpc, targetLevel, definition) &&
                DistanceSquared(targetNpc, npc) <= radiusSquared);
        }

        private static int TargetRouteThreatRank(
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedNpc startNpc,
            DynamicQuestSeedNpc targetNpc,
            DynamicQuestSeedDefinition definition)
        {
            if (startNpc == null || targetNpc == null || definition == null ||
                definition.MinLevel > 1 || definition.MaxLevel > 5)
            {
                return 0;
            }

            int targetLevel = targetNpc.Level > 0 ? targetNpc.Level : Math.Max(1, definition.MinLevel);
            double radiusSquared = TargetRouteThreatRadius * TargetRouteThreatRadius;
            return NpcsOrEmpty(npcs).Count(npc =>
                IsLikelyTargetRouteThreat(npc, startNpc, targetNpc, targetLevel) &&
                DistanceSquaredToSegment(npc, startNpc, targetNpc) <= radiusSquared);
        }

        private static bool IsLikelyTargetRouteThreat(
            DynamicQuestSeedNpc npc,
            DynamicQuestSeedNpc startNpc,
            DynamicQuestSeedNpc targetNpc,
            int targetLevel)
        {
            return npc != null &&
                   startNpc != null &&
                   targetNpc != null &&
                   npc.RegionId == targetNpc.RegionId &&
                   !string.Equals(npc.InternalID, startNpc.InternalID, StringComparison.OrdinalIgnoreCase) &&
                   !string.Equals(npc.InternalID, targetNpc.InternalID, StringComparison.OrdinalIgnoreCase) &&
                   (!string.Equals(npc.Name, targetNpc.Name, StringComparison.OrdinalIgnoreCase) || IsStarterActiveGrowthThreat(npc)) &&
                   npc.HasSourceNpcMetadata &&
                   IsLikelyStarterHostileThreat(npc) &&
                   IsStarterDangerousActiveGrowthThreat(npc, Math.Max(targetLevel, StarterMaxSoloSafeTargetLevel));
        }

        private static bool IsLikelyTargetAreaThreat(DynamicQuestSeedNpc npc, DynamicQuestSeedNpc targetNpc, int targetLevel, DynamicQuestSeedDefinition definition)
        {
            bool starterBand = IsStarterBand(definition);
            int threatLevelFloor = starterBand
                ? Math.Max(targetLevel, StarterMaxSoloSafeTargetLevel)
                : targetLevel;

            return npc != null &&
                   targetNpc != null &&
                   npc.RegionId == targetNpc.RegionId &&
                   !string.Equals(npc.InternalID, targetNpc.InternalID, StringComparison.OrdinalIgnoreCase) &&
                   (!string.Equals(npc.Name, targetNpc.Name, StringComparison.OrdinalIgnoreCase) || IsStarterActiveGrowthThreat(npc)) &&
                   IsLikelyStarterHostileThreat(npc) &&
                   (npc.Level > threatLevelFloor ||
                    (starterBand && IsStarterDangerousActiveGrowthThreat(npc, threatLevelFloor)) ||
                    (!starterBand && IsStarterActiveGrowthThreat(npc)));
        }

        private static bool IsStarterTargetSafeForSolo(
            DynamicQuestSeedNpc targetNpc,
            DynamicQuestSeedDefinition definition,
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedNpc startNpc,
            ISet<string> severeNameKeys)
        {
            if (!IsStarterBand(definition))
                return true;

            return !IsStarterSevereTargetRisk(targetNpc, definition, severeNameKeys) &&
                   TargetAreaThreatRank(npcs, targetNpc, definition, startNpc) == 0 &&
                   TargetRouteThreatRank(npcs, startNpc, targetNpc, definition) == 0;
        }

        private static bool IsLikelyStarterHostileThreat(DynamicQuestSeedNpc npc)
        {
            if (npc == null)
                return false;

            if (!npc.HasSourceNpcMetadata)
                return IsLikelyStartAreaThreat(npc);

            return npc.SourceIsAlive &&
                   !npc.SourceFlags.HasFlag(GameNPC.eFlags.PEACE) &&
                   !npc.SourceFlags.HasFlag(GameNPC.eFlags.CANTTARGET);
        }

        private static bool IsSameNpc(DynamicQuestSeedNpc left, DynamicQuestSeedNpc right)
        {
            return left != null &&
                   right != null &&
                   !string.IsNullOrWhiteSpace(left.InternalID) &&
                   string.Equals(left.InternalID, right.InternalID, StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsStarterGrowthThreat(DynamicQuestSeedNpc npc)
        {
            if (npc == null)
                return false;

            if (npc.NameGrowthThreatCount > 0)
                return true;

            return IsStarterActiveGrowthThreat(npc);
        }

        private static bool IsStarterActiveGrowthThreat(DynamicQuestSeedNpc npc)
        {
            if (npc == null)
                return false;

            string liveName = string.IsNullOrWhiteSpace(npc.RawName) ? npc.Name : npc.RawName;
            string normalized = NormalizeGrowthRiskName(liveName);
            if (!string.IsNullOrWhiteSpace(normalized) &&
                !string.Equals(StripMobGrowthNamePrefix(normalized), normalized, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            if (!npc.HasGrowthState)
                return false;

            if (npc.GrowthIsMutant || npc.GrowthMutationPending || npc.GrowthPlayerKills > 0 || npc.GrowthLevel > 0)
            {
                return true;
            }

            if (!string.IsNullOrWhiteSpace(npc.GrowthStage) &&
                !string.Equals(npc.GrowthStage, MobGrowthStages.Normal, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            return npc.GrowthEffectiveLevel > 5 || npc.GrowthScore >= 20;
        }

        private static bool IsStarterDangerousActiveGrowthThreat(DynamicQuestSeedNpc npc, int threatLevelFloor)
        {
            if (!IsStarterActiveGrowthThreat(npc))
                return false;

            int effectiveLevel = npc.GrowthEffectiveLevel > 0 ? npc.GrowthEffectiveLevel : npc.Level;
            return npc.GrowthIsMutant ||
                   npc.GrowthMutationPending ||
                   npc.GrowthPlayerKills > 0 ||
                   effectiveLevel > threatLevelFloor;
        }

        private static int TargetStartDistanceRank(DynamicQuestSeedNpc startNpc, DynamicQuestSeedNpc targetNpc)
        {
            if (startNpc == null || targetNpc == null)
                return 0;

            long distanceSquared = DistanceSquared(startNpc, targetNpc);
            long minimumSafeSquared = (long)NearStartMinimumSafeTargetDistance * NearStartMinimumSafeTargetDistance;
            long preferredRadiusSquared = (long)NearStartPreferredRadius * NearStartPreferredRadius;

            if (distanceSquared < minimumSafeSquared)
                return 1;

            return distanceSquared <= preferredRadiusSquared ? 0 : 2;
        }

        private static long DistanceSquared(DynamicQuestSeedNpc a, DynamicQuestSeedNpc b)
        {
            long dx = (long)a.X - b.X;
            long dy = (long)a.Y - b.Y;
            return dx * dx + dy * dy;
        }

        private static double DistanceSquaredToSegment(
            DynamicQuestSeedNpc point,
            DynamicQuestSeedNpc segmentStart,
            DynamicQuestSeedNpc segmentEnd)
        {
            double x = point.X;
            double y = point.Y;
            double x1 = segmentStart.X;
            double y1 = segmentStart.Y;
            double x2 = segmentEnd.X;
            double y2 = segmentEnd.Y;
            double dx = x2 - x1;
            double dy = y2 - y1;
            double lengthSquared = dx * dx + dy * dy;
            if (lengthSquared <= double.Epsilon)
                return DistanceSquared(point, segmentStart);

            double t = ((x - x1) * dx + (y - y1) * dy) / lengthSquared;
            t = Math.Clamp(t, 0.0, 1.0);
            double projectionX = x1 + t * dx;
            double projectionY = y1 + t * dy;
            double px = x - projectionX;
            double py = y - projectionY;
            return px * px + py * py;
        }

        private DynamicQuestResult AddStoryTemplateBoundQuest(
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedNpc npc,
            DynamicQuestSeedNpc targetNpc,
            DynamicQuestSeedDefinition definition,
            string worldRevision,
            DynamicQuestSeedOptions options)
        {
            DynamicQuestTemplate baseTemplate = BuildTemplate(npc, targetNpc, definition, worldRevision);
            baseTemplate.Source = "llm";
            CleanupStoryCacheIfNeeded();

            DynamicQuestTemplate template = LoadCachedStoryTemplate(baseTemplate.TemplateId, baseTemplate);
            if (template == null && options.GenerateMissingStoriesInline && CanGenerateNewStory())
            {
                DynamicQuestStoryGenerationResult generated = m_storyService.TryGenerate(BuildStoryRequest(baseTemplate, options));
                if (generated.Success)
                {
                    template = ApplyGeneratedStoryOrCacheReadyFallback(baseTemplate, generated);
                    SaveStoryTemplate(template, string.Empty);
                }
                else
                {
                    if (Log.IsWarnEnabled)
                        Log.Warn($"Dynamic quest story generation failed for {baseTemplate.TemplateId}: {generated.Error}");

                    template = ApplyDeterministicFallbackStory(baseTemplate);
                }
            }

            if (template == null)
            {
                template = ApplyDeterministicFallbackStory(baseTemplate);
            }

            template.WorldRevision = worldRevision;

            DynamicQuestTemplateBindingResult binding = new DynamicQuestTemplateService()
                .BindTemplate(template, npcs);

            if (!binding.Success)
                return DynamicQuestResult.Fail($"{binding.Message}; {DescribeSeedBindingContext(npc, targetNpc)}");

            TouchStoryTemplate(template.TemplateId, binding.BindingKey);
            return DynamicQuestRuntimeService.Instance.AddQuest(binding.Quest);
        }

        private DynamicQuestResult AddCodexCuratedStoryTemplateBoundQuest(
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedNpc npc,
            DynamicQuestSeedNpc targetNpc,
            DynamicQuestSeedDefinition definition,
            string worldRevision)
        {
            DynamicQuestTemplate baseTemplate = BuildTemplate(npc, targetNpc, definition, worldRevision);
            baseTemplate.Source = "codex-curated";
            CleanupStoryCacheIfNeeded();

            DynamicQuestTemplate template = LoadCachedStoryTemplate(baseTemplate.TemplateId, baseTemplate);
            if (template == null)
            {
                template = ApplyCodexCuratedStory(baseTemplate);
                if (IsStoryTemplateReadyForCache(template))
                    SaveStoryTemplate(template, string.Empty);
            }

            template.WorldRevision = worldRevision;

            DynamicQuestTemplateBindingResult binding = new DynamicQuestTemplateService()
                .BindTemplate(template, npcs);

            if (!binding.Success)
                return DynamicQuestResult.Fail($"{binding.Message}; {DescribeSeedBindingContext(npc, targetNpc)}");

            TouchStoryTemplate(template.TemplateId, binding.BindingKey);
            return DynamicQuestRuntimeService.Instance.AddQuest(binding.Quest);
        }

        private static string DescribeSeedBindingContext(DynamicQuestSeedNpc startNpc, DynamicQuestSeedNpc targetNpc)
        {
            if (startNpc == null && targetNpc == null)
                return "seedBindingContext=start:null target:null";

            string start = startNpc == null
                ? "null"
                : $"{startNpc.Name}@r{startNpc.RegionId}:{startNpc.X},{startNpc.Y},z{startNpc.Z},lvl{startNpc.Level},id={startNpc.InternalID}";
            string target = targetNpc == null
                ? "null"
                : $"{targetNpc.Name}@r{targetNpc.RegionId}:{targetNpc.X},{targetNpc.Y},z{targetNpc.Z},lvl{targetNpc.Level},id={targetNpc.InternalID}";
            string distance = startNpc == null || targetNpc == null
                ? "n/a"
                : Math.Sqrt(DistanceSquared(startNpc, targetNpc)).ToString("0");
            return $"seedBindingContext=start:{start} target:{target} distance:{distance}";
        }

        private static DynamicQuestStoryText BuildDeterministicFallbackStory(DynamicQuestTemplate template)
        {
            return BuildCodexCuratedStory(template);
        }

        private static DynamicQuestStoryText BuildCodexCuratedStory(DynamicQuestTemplate template)
        {
            string target = "{{target}}";
            bool hasStartNpc = !string.IsNullOrWhiteSpace(template?.PreferredStartNpcName);
            string startLabel = hasStartNpc ? "의뢰인 {{start_npc}}" : "현장 목격자";
            string startPossessive = hasStartNpc ? "의뢰인 {{start_npc}}의" : "목격자의";
            string startSource = hasStartNpc ? "의뢰인 {{start_npc}}에게서" : "현장 목격자에게서";
            string startDative = hasStartNpc ? "의뢰인 {{start_npc}}에게" : "현장 목격자에게";
            string speaker = string.IsNullOrWhiteSpace(template?.PreferredStartNpcName) ? "System" : "StartNpc";
            string location = RealmNameForRegion(template?.PreferredRegionId ?? 0);
            string realmName = string.Equals(location, "Unknown", StringComparison.OrdinalIgnoreCase)
                ? "이 지역"
                : "{{realm}}";
            string realmTexture = RealmTextureForStory(location);
            string omen = RealmOmenForStory(location);
            string relic = RealmRelicForStory(location);
            string branchWorldSignal = BranchWorldSignalForStory(template);
            bool hasBranch = !string.IsNullOrWhiteSpace(branchWorldSignal);
            string storyArchetype = CodexStoryArchetype(template);
            string archetypeMotive = CodexStoryArchetypeMotive(storyArchetype, realmTexture, target);
            string archetypeConflict = CodexStoryArchetypeConflict(storyArchetype, realmTexture, target);
            string archetypeResolution = CodexStoryArchetypeResolution(storyArchetype, realmTexture, target);
            string storyTitle = CodexStoryTitle(template, storyArchetype, branchWorldSignal, realmTexture);
            string dramaticSecret = CodexStoryDramaticSecret(storyArchetype, realmTexture, target);
            string dramaticPressure = CodexStoryDramaticPressure(storyArchetype, realmTexture, target);
            string dramaticAction = CodexStoryDramaticAction(storyArchetype, realmTexture, target);
            string dramaticChoice = CodexStoryDramaticChoice(storyArchetype, realmTexture, target);
            string dramaticAftermath = CodexStoryDramaticAftermath(storyArchetype, realmTexture, target);
            string openingBeat = CodexStoryOpeningBeat(storyArchetype, realmTexture, target);
            string choiceBeat = CodexStoryChoiceBeat(storyArchetype, realmTexture, target);
            CodexStoryCinematicProfile cinematic = CodexStoryCinematicProfileFor(storyArchetype, realmTexture, target);
            string castWitness = cinematic.WitnessName;
            string castAntagonist = cinematic.AntagonistName;
            string castEvidence = cinematic.EvidenceName;
            bool hasStoryTitleVariantV3 = (template?.Tags ?? Array.Empty<string>())
                .Contains("story-title-variant:v3", StringComparer.OrdinalIgnoreCase);

            List<DynamicQuestNarrativeScene> scenes = new()
            {
                new DynamicQuestNarrativeScene
                {
                    NodeId = "talk",
                    SceneType = "Intro",
                    Title = CodexStorySceneTitle(storyArchetype, "talk", realmTexture),
                    Body = $"{startSource} 받은 증거는 '{castEvidence}' 단서, 피 묻은 끈 하나와 {relic}에 긁힌 낯선 의식 표식이다. {archetypeMotive} {dramaticSecret} 기록에는 '{castWitness}'라는 목격자 이름이 남아 있고, 증인은 망보던 그림자가 탈출로 쪽으로 후퇴하며 '{castAntagonist}' 이름을 남겼다고 떨리는 목소리로 덧붙인다. 이 위협은 먹이를 찾는 짐승처럼 지나간 것이 아니라, 누가 어느 길을 쓰는지 기억한 채 되돌아온 것처럼 보인다.",
                    JournalEntry = $"{startSource} {realmTexture} 주변의 사건을 조사해 달라는 부탁을 받았다. 증거에는 단서 '{castEvidence}', 목격자 '{castWitness}'의 증언, 그리고 {dramaticSecret} 단서가 있다.",
                    Mood = "ominous",
                    RevealPolicy = "FirstSeenOnly"
                },
                new DynamicQuestNarrativeScene
                {
                    NodeId = "explore",
                    SceneType = "Discovery",
                    Title = CodexStorySceneTitle(storyArchetype, "explore", realmTexture),
                    Body = $"{realmTexture}에는 급히 꺼진 모닥불, 밟혀 깨진 화살촉, 한 번 지나간 뒤 다시 돌아온 발자국이 겹쳐 있다. {omen} 사이로 남은 길은 그 무리가 우연히 떠돈 것이 아니라 누군가를 몰아낸 자리를 지키고 있음을 보여 준다. {archetypeConflict} {dramaticPressure} '{castWitness}'라는 이름의 목격자가 '{castEvidence}' 단서를 들어 올리자 전열을 세운 경비들이 의식 표식을 끊으려 다가가고, '{castAntagonist}' 쪽 망보는 자가 탈출로로 물러난다.",
                    JournalEntry = $"{realmTexture}에서 위협의 이동 경로를 확인했다. 흔적은 단순한 사냥감이 아니라 {dramaticPressure} 상황에 가깝다.",
                    Mood = "urgent",
                    RevealPolicy = "FirstSeenOnly"
                },
                new DynamicQuestNarrativeScene
                {
                    NodeId = "kill",
                    SceneType = "Threat",
                    Title = CodexStorySceneTitle(storyArchetype, "kill", realmTexture),
                    Body = $"{target} 위협이 모습을 드러내자 주변의 작은 소리들이 먼저 사라진다. {dramaticAction} 칼을 뽑는 순간 '{castAntagonist}' 이름 아래 모인 매복 병력이 숨어 있던 자리에서 일어나고, 방패 든 경비들이 탈출 경로를 가로막는다. 이 싸움은 숫자를 채우는 일이 아니라 사람들이 {realmTexture}에서 다시 서로의 이름을 부르며 지날 수 있게 만드는 일이 된다.",
                    JournalEntry = $"매복과 차단을 뚫고 이 위협을 제압해야 적장 '{castAntagonist}'의 공포가 풀린다.",
                    Mood = "grim",
                    RevealPolicy = "FirstSeenOnly"
                },
                new DynamicQuestNarrativeScene
                {
                    NodeId = "return",
                    SceneType = "Return",
                    Title = CodexStorySceneTitle(storyArchetype, "return", realmTexture),
                    Body = $"전투는 끝났지만 '{castEvidence}' 단서와 {relic}에 남은 표식은 사라지지 않는다. {dramaticAftermath} {startDative} 돌아가면 사람들은 살아남은 숫자보다 '{castWitness}'라는 이름으로 기록된 목격자가 아직 안전한지, 그리고 '{castAntagonist}' 이름이 정말 끝난 것인지 먼저 물을 것이다.",
                    JournalEntry = $"{startDative} 돌아가 단서 '{castEvidence}', 남은 표식, {dramaticAftermath} 상황을 보고해야 한다.",
                    Mood = "relieved",
                    RevealPolicy = "FirstSeenOnly"
                },
                new DynamicQuestNarrativeScene
                {
                    NodeId = "choice",
                    SceneType = "Choice",
                    Title = CodexStorySceneTitle(storyArchetype, "choice", realmTexture),
                    Body = $"{startLabel}의 표정에는 안도와 두려움이 함께 남아 있다. 지금 사람들에게 필요한 것은 잠잘 수 있는 밤이지만, {realmTexture}의 표식은 더 깊은 원인을 가리킨다. {archetypeResolution} {dramaticChoice} '{castWitness}'라는 이름의 목격자를 둘러싸고 경비가 서로 마주 서며, 기록에 '{castAntagonist}' 이름을 남길지 묻는 대치 속에서 플레이어의 선택이 이 사건의 마지막 문장이 된다.",
                    JournalEntry = $"{realmTexture}의 직접적인 위협은 줄었다. 대치가 길어지기 전에 안전을 확정할지, 남은 표식을 따라 더 깊은 원인을 확인할지 선택해야 한다.",
                    Mood = "mysterious",
                    RevealPolicy = "FirstSeenOnly"
                }
            };

            if (hasBranch)
            {
                scenes.Add(new DynamicQuestNarrativeScene
                {
                    NodeId = "observe_signal",
                    SceneType = "Aftermath",
                    Title = BranchStoryTitle(branchWorldSignal),
                    Body = $"{BranchStoryBody(realmTexture, target, branchWorldSignal)} 단서 '{castEvidence}'가 다시 반응하고, 목격자 '{castWitness}'의 증언은 이 후속 신호가 처음 사건과 같은 손에서 나왔음을 보여 준다.",
                    JournalEntry = BranchStoryJournal(realmTexture, target, branchWorldSignal),
                    Mood = "mysterious",
                    RevealPolicy = "FirstSeenOnly"
                });
            }

            scenes.Add(new DynamicQuestNarrativeScene
            {
                NodeId = "complete",
                SceneType = "Completion",
                Title = CodexStorySceneTitle(storyArchetype, "complete", realmTexture),
                Body = $"{realmName}의 길목에 생활의 소리가 천천히 돌아온다. {startPossessive} 기록에는 위협을 끝낸 이름뿐 아니라, 목격자 '{castWitness}', 단서 '{castEvidence}', 그리고 선택의 이유도 함께 적힌다. {dramaticAftermath} 이 결말은 거대한 승전가가 아니라, 한 지역이 오늘 밤 문을 조금 늦게 잠가도 된다는 작은 변화다.",
                JournalEntry = $"사건을 마무리했다. {startPossessive} 기록에는 {realmTexture}의 위협, 목격자 '{castWitness}'의 증언, 단서 '{castEvidence}', 그리고 선택의 결과가 남았다.",
                Mood = "hopeful",
                RevealPolicy = "FirstSeenOnly"
            });

            List<DynamicQuestPresentationBeat> beats = new()
            {
                new DynamicQuestPresentationBeat
                {
                    NodeId = "talk",
                    Trigger = "OnAccept",
                    Speaker = speaker,
                    Text = openingBeat,
                    Emotion = "fear",
                    Emote = "Shiver",
                    CinematicAction = "witness_point",
                    SceneRole = cinematic.AcceptSceneRole,
                    Formation = cinematic.AcceptFormation,
                    ActorCount = cinematic.AcceptActorCount
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "talk",
                    Trigger = "OnNpcInteract",
                    Speaker = speaker,
                    Text = cinematic.InteractText,
                    Emotion = "caution",
                    Emote = "No"
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "explore",
                    Trigger = "OnNodeEnter",
                    Speaker = "System",
                    Text = cinematic.ExploreEnterText,
                    Emotion = "suspicion",
                    Emote = "Ponder"
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "explore",
                    Trigger = "OnExplore",
                    Speaker = "System",
                    Text = cinematic.ScoutText,
                    Emotion = "suspicion",
                    Emote = "Ponder",
                    CinematicAction = "scout_retreat",
                    SceneRole = cinematic.ScoutSceneRole,
                    Formation = cinematic.ScoutFormation,
                    ActorCount = cinematic.ScoutActorCount,
                    DelayMs = 900
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "explore",
                    Trigger = "OnExplore",
                    Speaker = "System",
                    Text = cinematic.RitualText,
                    Emotion = "caution",
                    Emote = "Point",
                    CinematicAction = "ritual_interrupt",
                    SceneRole = cinematic.RitualSceneRole,
                    Formation = cinematic.RitualFormation,
                    ActorCount = cinematic.RitualActorCount,
                    DelayMs = 1500
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "kill",
                    Trigger = "OnKill",
                    Speaker = "System",
                    Text = cinematic.AmbushText,
                    Emotion = "urgency",
                    Emote = "Point",
                    CinematicAction = "ambush_reveal",
                    SceneRole = cinematic.AmbushSceneRole,
                    Formation = cinematic.AmbushFormation,
                    ActorCount = cinematic.AmbushActorCount
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "kill",
                    Trigger = "OnKill",
                    Speaker = "Companion",
                    Text = cinematic.InterceptText,
                    Emotion = "suspicion",
                    Emote = "Ponder",
                    CinematicAction = "defender_intercept",
                    SceneRole = cinematic.InterceptSceneRole,
                    Formation = cinematic.InterceptFormation,
                    ActorCount = cinematic.InterceptActorCount,
                    DelayMs = 800
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "kill",
                    Trigger = "OnKill",
                    Speaker = "System",
                    Text = cinematic.CombatText,
                    Emotion = "caution",
                    Emote = "Point",
                    CinematicAction = "combat_stance",
                    SceneRole = cinematic.CombatSceneRole,
                    Formation = cinematic.CombatFormation,
                    ActorCount = cinematic.CombatActorCount,
                    DelayMs = 1600
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "return",
                    Trigger = "OnNodeEnter",
                    Speaker = "System",
                    Text = $"보고할 증거를 손에 쥐자 {realmTexture}의 바람이 등 뒤에서 방향을 바꿉니다.",
                    Emotion = "caution",
                    Emote = "Point"
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "choice",
                    Trigger = "OnChoiceShown",
                    Speaker = speaker,
                    Text = choiceBeat,
                    Emotion = "suspicion",
                    Emote = "Ponder",
                    CinematicAction = "threat_standoff",
                    SceneRole = cinematic.ChoiceConfrontationRole,
                    Formation = cinematic.ChoiceFormation,
                    ActorCount = cinematic.ChoiceActorCount
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "choice",
                    Trigger = "OnChoiceSelected",
                    Speaker = speaker,
                    Text = cinematic.ChoiceRecordText,
                    Emotion = "pride",
                    Emote = "Salute"
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "choice",
                    Trigger = "OnChoiceSelected",
                    Speaker = "System",
                    Text = cinematic.ChoiceFalloutText,
                    Emotion = "suspicion",
                    Emote = "Ponder",
                    CinematicAction = "guard_advance",
                    SceneRole = cinematic.ChoiceFalloutRole,
                    Formation = cinematic.ChoiceFalloutFormation,
                    ActorCount = cinematic.ChoiceFalloutActorCount,
                    DelayMs = 1000
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "choice",
                    Trigger = "OnChoiceSelected",
                    Speaker = "System",
                    Text = cinematic.HoldText,
                    Emotion = "caution",
                    Emote = "Point",
                    CinematicAction = "hold_ground",
                    SceneRole = cinematic.HoldRole,
                    Formation = cinematic.HoldFormation,
                    ActorCount = cinematic.HoldActorCount,
                    DelayMs = 1700
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "complete",
                    Trigger = "OnComplete",
                    Speaker = speaker,
                    Text = cinematic.CompleteText,
                    Emotion = "gratitude",
                    Emote = "Bow"
                }
            };

            if (hasBranch)
            {
                DynamicQuestPresentationBeat branchBeat = BuildWorldSignalSetPieceBeat(branchWorldSignal);
                branchBeat.Text = $"{BranchStoryBeat(realmTexture, target, branchWorldSignal)} {branchBeat.Text}";
                branchBeat.ActorCount = Math.Max(branchBeat.ActorCount, cinematic.BranchActorCount);
                branchBeat.DelayMs = 600;
                beats.Insert(beats.Count - 1, branchBeat);
                beats.Insert(beats.Count - 1, new DynamicQuestPresentationBeat
                {
                    NodeId = "observe_signal",
                    Trigger = "OnWorldSignal",
                    Speaker = "Companion",
                    Text = cinematic.BranchCompanionText,
                    Emotion = "suspicion",
                    Emote = "Ponder",
                    CinematicAction = "witness_point",
                    SceneRole = cinematic.BranchCompanionRole,
                    Formation = cinematic.BranchCompanionFormation,
                    ActorCount = cinematic.BranchCompanionActorCount,
                    DelayMs = 1200
                });
            }

            return new DynamicQuestStoryText
            {
                Title = !hasStoryTitleVariantV3 || string.IsNullOrWhiteSpace(template?.Title) || HasFallbackScaffoldTitle(template.Title)
                    ? storyTitle
                    : template.Title,
                OfferText = $"{startPossessive} 부탁은 단순한 사냥 의뢰가 아니다. {realmName} {realmTexture}에는 '{castEvidence}' 단서와 되돌아온 발자국이 남아 있고, {target} 위협 뒤에 목격자 '{castWitness}', 그리고 '{castAntagonist}' 이름이 얽힌 사건이 있음을 보여 준다.",
                ProgressText = $"{realmTexture}의 증거를 따라가 {target} 위협을 끊고, 남은 표식이 무엇을 가리키는지 확인해야 한다.",
                FinishText = $"{realmTexture} 주변의 길이 다시 열린다. {startPossessive} 기록에는 목격자 '{castWitness}', 단서 '{castEvidence}', 오늘의 선택과 남은 표식의 의미가 함께 적힌다.",
                NarrativeScenes = scenes,
                PresentationBeats = beats
            };
        }

        private sealed class CodexStoryCinematicProfile
        {
            public string WitnessName { get; set; } = "Mairwen";
            public string AntagonistName { get; set; } = "the Black Ledger";
            public string EvidenceName { get; set; } = "검은 밀랍 인장";
            public string AcceptSceneRole { get; set; } = "contract_witness";
            public string AcceptFormation { get; set; } = "escort";
            public int AcceptActorCount { get; set; } = 4;
            public string InteractText { get; set; } = string.Empty;
            public string ExploreEnterText { get; set; } = string.Empty;
            public string ScoutText { get; set; } = string.Empty;
            public string ScoutSceneRole { get; set; } = "lookout_escape";
            public string ScoutFormation { get; set; } = "escape";
            public int ScoutActorCount { get; set; } = 12;
            public string RitualText { get; set; } = string.Empty;
            public string RitualSceneRole { get; set; } = "ritual_break";
            public string RitualFormation { get; set; } = "line";
            public int RitualActorCount { get; set; } = 20;
            public string AmbushText { get; set; } = string.Empty;
            public string AmbushSceneRole { get; set; } = "ambush_wave";
            public string AmbushFormation { get; set; } = "ambush";
            public int AmbushActorCount { get; set; } = 100;
            public string InterceptText { get; set; } = string.Empty;
            public string InterceptSceneRole { get; set; } = "escape_intercept";
            public string InterceptFormation { get; set; } = "line";
            public int InterceptActorCount { get; set; } = 32;
            public string CombatText { get; set; } = string.Empty;
            public string CombatSceneRole { get; set; } = "counterline";
            public string CombatFormation { get; set; } = "line";
            public int CombatActorCount { get; set; } = 24;
            public string ChoiceConfrontationRole { get; set; } = "choice_confrontation";
            public string ChoiceFormation { get; set; } = "line";
            public int ChoiceActorCount { get; set; } = 48;
            public string ChoiceRecordText { get; set; } = string.Empty;
            public string ChoiceFalloutText { get; set; } = string.Empty;
            public string ChoiceFalloutRole { get; set; } = "choice_fallout";
            public string ChoiceFalloutFormation { get; set; } = "escort";
            public int ChoiceFalloutActorCount { get; set; } = 24;
            public string HoldText { get; set; } = string.Empty;
            public string HoldRole { get; set; } = "shield_hold";
            public string HoldFormation { get; set; } = "line";
            public int HoldActorCount { get; set; } = 36;
            public string CompleteText { get; set; } = string.Empty;
            public int BranchActorCount { get; set; } = 40;
            public string BranchCompanionText { get; set; } = string.Empty;
            public string BranchCompanionRole { get; set; } = "signal_witness";
            public string BranchCompanionFormation { get; set; } = "escort";
            public int BranchCompanionActorCount { get; set; } = 12;
        }

        private static CodexStoryCinematicProfile CodexStoryCinematicProfileFor(string archetype, string realmTexture, string target)
        {
            string key = (archetype ?? string.Empty).Trim().ToLowerInvariant();
            CodexStoryCinematicProfile profile = new()
            {
                InteractText = "말을 낮춰 주십시오. 저것은 발소리보다 먼저 두려움을 배운 듯합니다.",
                ExploreEnterText = $"{realmTexture}에 긁힌 의식 표식이 의뢰인이 건넨 증거와 맞아떨어집니다.",
                ScoutText = "목격자가 꺼진 불씨를 가리키자 망보던 자가 탈출로로 후퇴하고, 되돌아온 발자국이 숨은 길을 드러냅니다.",
                RitualText = $"{realmTexture}의 표식이 흔들립니다. 경비들이 전열을 세우고 한 명이 의식을 끊으려 다가갑니다.",
                AmbushText = "위협이 쓰러지자 매복 병력이 모습을 드러내고, 방패 든 경비가 탈출 경로를 가로막습니다.",
                InterceptText = "끝난 것처럼 보여도, 이런 표식은 그냥 남지 않습니다. 저 증인은 아직 도망칠지 말할지 대치하고 있습니다.",
                CombatText = "살아남은 전투원들이 반원으로 자세를 낮추고, 마지막 소란이 진짜 끝났는지 확인합니다.",
                ChoiceRecordText = "좋습니다. 마을 안전을 먼저 확정할지, 더 큰 위협을 추적할지 선택한 이유까지 기록하겠습니다. 언젠가 누군가 이 밤을 다시 읽게 될 테니까요.",
                ChoiceFalloutText = "선택의 여운이 남은 표식 위로 내려앉습니다.",
                HoldText = "경비들이 흩어지지 않고 자리를 지키며, 선택이 현장의 안전으로 이어질 때까지 길목을 막아섭니다.",
                CompleteText = $"{realmTexture}에 다시 평범한 발소리가 돌아왔습니다. 오늘의 결정은 조용히 오래 남을 겁니다.",
                BranchCompanionText = "이건 우연한 단서가 아닙니다. 누군가 다음 길을 보여 주고 있습니다."
            };

            switch (key)
            {
                case "black-contract":
                    profile.WitnessName = "Sable Mara";
                    profile.AntagonistName = "the Veiled Broker";
                    profile.EvidenceName = "검은 밀랍이 묻은 계약서";
                    profile.AcceptSceneRole = "contract_witness";
                    profile.AcceptFormation = "escort";
                    profile.ScoutSceneRole = "contract_lookout_escape";
                    profile.ScoutFormation = "escape";
                    profile.RitualSceneRole = "contract_mark_break";
                    profile.RitualFormation = "ring";
                    profile.AmbushSceneRole = "contract_blade_ambush";
                    profile.AmbushFormation = "ambush";
                    profile.InterceptSceneRole = "witness_escape_intercept";
                    profile.InterceptFormation = "line";
                    profile.CombatSceneRole = "contract_counterline";
                    profile.ChoiceConfrontationRole = "contract_trial_standoff";
                    profile.ChoiceFalloutRole = "contract_fallout";
                    profile.HoldRole = "witness_screen";
                    profile.BranchCompanionRole = "contract_signal_witness";
                    profile.ScoutActorCount = 18;
                    profile.AmbushActorCount = 100;
                    profile.InterceptActorCount = 40;
                    profile.ChoiceActorCount = 52;
                    profile.ScoutText = "목격자가 탈출로로 뛰자 망보던 자들이 양쪽 길을 막고, 검은 계약 표식이 젖은 흙 위에 드러납니다.";
                    profile.RitualText = $"{realmTexture}의 계약 표식이 찢기자 경비들이 원을 깨고, 숨겨진 대가를 적은 조각을 들어 올립니다.";
                    profile.AmbushText = "위협이 쓰러지자 계약자의 칼잡이들이 어둠에서 일어나고, 방패 든 경비가 목격자의 퇴로를 막습니다.";
                    profile.InterceptText = "계약은 끝난 척하지만, 칼잡이들은 아직 목격자의 길을 보고 있습니다. 방패선을 앞으로 당겨야 합니다.";
                    profile.ChoiceFalloutText = "선택이 내려지자 계약서 조각이 경비 손으로 넘어가고, 목격자를 둘러싼 대치선이 새 방향으로 꺾입니다.";
                    profile.HoldText = "방패 든 경비들이 목격자 앞에 두 겹으로 서고, 남은 칼잡이들이 더 가까이 오지 못하게 버팁니다.";
                    profile.BranchCompanionText = "계약서 조각이 다음 길을 가리킵니다. 이건 사냥이 아니라 값을 치른 침묵입니다.";
                    profile.CompleteText = $"{realmTexture}에 칼날 소리가 멎습니다. 계약서는 찢겼지만, 그 값을 낸 이름은 아직 낮은 소문으로 남습니다.";
                    break;
                case "witness-conspiracy":
                    profile.WitnessName = "Mairwen";
                    profile.AntagonistName = "Captain Rhedan";
                    profile.EvidenceName = "빠진 이름이 남은 순찰 명부";
                    profile.AcceptSceneRole = "hidden_witness_ring";
                    profile.AcceptFormation = "wedge";
                    profile.ScoutSceneRole = "silenced_runner";
                    profile.ScoutFormation = "escape";
                    profile.RitualSceneRole = "false_testimony_break";
                    profile.RitualFormation = "ring";
                    profile.AmbushSceneRole = "mouthpiece_ambush";
                    profile.AmbushFormation = "ambush";
                    profile.InterceptSceneRole = "witness_guard";
                    profile.InterceptFormation = "escort";
                    profile.CombatSceneRole = "testimony_counterline";
                    profile.ChoiceConfrontationRole = "witness_crossfire";
                    profile.ChoiceFalloutRole = "truth_fallout";
                    profile.HoldRole = "witness_screen";
                    profile.BranchCompanionRole = "hidden_name_witness";
                    profile.ScoutText = "빠진 이름을 아는 목격자가 뒷길로 물러나자, 입막음꾼들이 발자국을 지우며 흩어집니다.";
                    profile.RitualText = $"{realmTexture}의 거짓 표식 앞에서 경비들이 증언을 맞대고, 한 사람이 숨긴 이름을 향해 손을 듭니다.";
                    profile.AmbushText = "위협이 쓰러지자 입막음꾼들이 모습을 드러내고, 방패 든 경비가 탈출 경로를 가로막습니다.";
                    profile.ChoiceFalloutText = "선택이 내려지자 증인과 경비 사이에 남아 있던 침묵이 현장의 방향을 바꿉니다.";
                    break;
                case "oath-breach":
                    profile.WitnessName = "Caelric";
                    profile.AntagonistName = "Sergeant Odran";
                    profile.EvidenceName = "찢긴 서약장";
                    profile.AcceptSceneRole = "broken_oath_witness";
                    profile.AcceptFormation = "escort";
                    profile.ScoutSceneRole = "oathbreaker_lookout";
                    profile.ScoutFormation = "patrol";
                    profile.RitualSceneRole = "oath_knot_break";
                    profile.RitualFormation = "line";
                    profile.AmbushSceneRole = "traitor_signal_wave";
                    profile.AmbushFormation = "ambush";
                    profile.InterceptSceneRole = "shield_oath_intercept";
                    profile.InterceptFormation = "line";
                    profile.CombatSceneRole = "oath_counterline";
                    profile.ChoiceConfrontationRole = "shield_oath_trial";
                    profile.ChoiceFalloutRole = "oath_fallout";
                    profile.HoldRole = "renewed_shield_hold";
                    profile.BranchCompanionRole = "oath_signal_witness";
                    profile.ScoutText = "찢긴 서약끈을 본 망보는 자가 초소 뒤로 빠지고, 남은 경비들이 서로의 방패를 의심하며 전열을 좁힙니다.";
                    profile.RitualText = $"{realmTexture}의 매듭 표식이 흔들리자 경비 하나가 부러진 서약끈을 들어 올리고 방패선이 갈라집니다.";
                    profile.AmbushText = "위협이 쓰러지자 배신자의 신호를 받은 매복이 일어나고, 남은 방패선이 탈출 경로를 가로막습니다.";
                    profile.HoldText = "경비들이 새로 묶은 서약끈 앞에서 흩어지지 않고 서며, 선택이 안전으로 이어질 때까지 방패를 내리지 않습니다.";
                    break;
                case "relic-echo":
                    profile.WitnessName = "Eleri";
                    profile.AntagonistName = "Prior Veyr";
                    profile.EvidenceName = "울림이 남은 성물함";
                    profile.AcceptSceneRole = "relic_witness_circle";
                    profile.AcceptFormation = "ring";
                    profile.ScoutSceneRole = "echo_lookout";
                    profile.ScoutFormation = "ring";
                    profile.RitualSceneRole = "echo_circle_break";
                    profile.RitualFormation = "ring";
                    profile.AmbushSceneRole = "relic_echo_wave";
                    profile.AmbushFormation = "ambush";
                    profile.InterceptSceneRole = "relic_guard_intercept";
                    profile.InterceptFormation = "wedge";
                    profile.CombatSceneRole = "echo_counterline";
                    profile.ChoiceConfrontationRole = "relic_reading_circle";
                    profile.ChoiceFalloutRole = "echo_fallout";
                    profile.HoldRole = "relic_silence_hold";
                    profile.BranchCompanionRole = "echo_signal_witness";
                    profile.ScoutText = "성물의 낮은 울림을 따라 망보는 자가 원 바깥으로 물러나고, 되풀이되는 발자국이 숨은 길을 드러냅니다.";
                    profile.RitualText = $"{realmTexture}의 원형 표식이 빛나자 경비들이 둘레를 끊고, 성물의 마지막 메아리가 전장 위로 번집니다.";
                    profile.AmbushText = "위협이 쓰러지자 성물의 메아리를 좇던 매복이 고개를 들고, 방패 든 경비가 탈출 경로를 가로막습니다.";
                    profile.CompleteText = $"{realmTexture}에 울림이 잦아들고 평범한 발소리가 돌아옵니다. 오늘의 결정은 낮은 메아리처럼 오래 남을 겁니다.";
                    break;
                case "blood-price":
                    profile.WitnessName = "Brannoc";
                    profile.AntagonistName = "Mael the Collector";
                    profile.EvidenceName = "붉은 채무 장부";
                    profile.AcceptSceneRole = "ledger_witness";
                    profile.AcceptFormation = "escort";
                    profile.ScoutSceneRole = "debt_collector_retreat";
                    profile.ScoutFormation = "wedge";
                    profile.RitualSceneRole = "ledger_mark_break";
                    profile.RitualFormation = "line";
                    profile.AmbushSceneRole = "collector_ambush";
                    profile.AmbushFormation = "ambush";
                    profile.InterceptSceneRole = "ledger_intercept";
                    profile.InterceptFormation = "line";
                    profile.CombatSceneRole = "debt_counterline";
                    profile.ChoiceConfrontationRole = "ledger_trial";
                    profile.ChoiceFalloutRole = "debt_fallout";
                    profile.HoldRole = "ledger_guard_hold";
                    profile.BranchCompanionRole = "ledger_signal_witness";
                    profile.ScoutText = "붉은 장부를 든 전령이 뒷길로 물러나자, 빚을 걷는 자들이 이름 적힌 표식을 감추려 흩어집니다.";
                    profile.RitualText = $"{realmTexture}의 장부 표식이 흔들리자 경비들이 다음 이름이 적힌 줄을 막고, 채권자의 표식이 찢깁니다.";
                    profile.AmbushText = "위협이 쓰러지자 피값을 걷는 매복이 장부를 닫고 달려들며, 방패 든 경비가 탈출 경로를 가로막습니다.";
                    profile.ChoiceFalloutText = "선택이 내려지자 젖은 잉크가 표식 위에서 번지고, 다음 이름을 둘러싼 압박이 현장을 바꿉니다.";
                    break;
                case "border-omen":
                    profile.WitnessName = "Talan";
                    profile.AntagonistName = "Gatewarden Eoric";
                    profile.EvidenceName = "안쪽에서 긁힌 경계석 조각";
                    profile.AcceptSceneRole = "border_watch";
                    profile.AcceptFormation = "patrol";
                    profile.ScoutSceneRole = "inner_gate_scout";
                    profile.ScoutFormation = "patrol";
                    profile.RitualSceneRole = "border_mark_break";
                    profile.RitualFormation = "line";
                    profile.AmbushSceneRole = "breach_wave";
                    profile.AmbushFormation = "ambush";
                    profile.InterceptSceneRole = "gate_intercept";
                    profile.InterceptFormation = "line";
                    profile.CombatSceneRole = "border_counterline";
                    profile.ChoiceConfrontationRole = "gate_standoff";
                    profile.ChoiceFalloutRole = "border_fallout";
                    profile.HoldRole = "gate_hold";
                    profile.BranchCompanionRole = "border_signal_witness";
                    profile.ScoutActorCount = 16;
                    profile.InterceptActorCount = 36;
                    profile.HoldActorCount = 40;
                    profile.ScoutText = "안쪽 길목에 난 같은 흠집을 본 정찰자가 경계 바깥으로 후퇴하고, 순찰대가 길 전체를 봉쇄합니다.";
                    profile.RitualText = $"{realmTexture}의 경계 표식이 안쪽으로 번지자 경비들이 문턱을 가로지르고, 열린 길을 다시 닫기 시작합니다.";
                    profile.AmbushText = "위협이 쓰러지자 경계 안쪽에 숨어 있던 침입자들이 일어나고, 방패 든 경비가 탈출 경로를 가로막습니다.";
                    profile.CompleteText = $"{realmTexture}에 경계의 소리가 돌아옵니다. 오늘의 결정은 닫힌 문과 남은 흠집 사이에 오래 남을 겁니다.";
                    break;
                case "lost-heirloom":
                    profile.WitnessName = "Nessa";
                    profile.AntagonistName = "Harrow Vale";
                    profile.EvidenceName = "숨은 이름이 새겨진 유품";
                    profile.AcceptSceneRole = "heirloom_witness";
                    profile.AcceptFormation = "escort";
                    profile.ScoutSceneRole = "heirloom_thief_retreat";
                    profile.ScoutFormation = "escape";
                    profile.RitualSceneRole = "hidden_owner_reveal";
                    profile.RitualFormation = "ring";
                    profile.AmbushSceneRole = "heirloom_ambush";
                    profile.AmbushFormation = "ambush";
                    profile.InterceptSceneRole = "heirloom_guard_intercept";
                    profile.InterceptFormation = "wedge";
                    profile.CombatSceneRole = "heirloom_counterline";
                    profile.ChoiceConfrontationRole = "owner_name_standoff";
                    profile.ChoiceFalloutRole = "heirloom_fallout";
                    profile.HoldRole = "heirloom_guard_hold";
                    profile.BranchCompanionRole = "heirloom_signal_witness";
                    profile.RitualActorCount = 18;
                    profile.ChoiceActorCount = 44;
                    profile.ScoutText = "유품을 숨긴 자가 뒷길로 빠지자, 오래된 주인의 표식과 되돌아온 발자국이 서로 다른 방향을 가리킵니다.";
                    profile.RitualText = $"{realmTexture}의 숨은 이름이 드러나자 경비들이 유품을 둘러싸고, 감춰 둔 보호자의 표식이 끊어집니다.";
                    profile.AmbushText = "위협이 쓰러지자 유품을 노린 매복이 모습을 드러내고, 방패 든 경비가 탈출 경로를 가로막습니다.";
                    profile.BranchCompanionText = "이건 우연한 단서가 아닙니다. 유품이 숨긴 이름과 다음 길을 동시에 보여 주고 있습니다.";
                    break;
                case "hostage-rescue":
                    profile.WitnessName = "Aline";
                    profile.AntagonistName = "Varro the Binder";
                    profile.EvidenceName = "피 묻은 결박끈";
                    profile.AcceptSceneRole = "bound_witness_guard";
                    profile.AcceptFormation = "escort";
                    profile.ScoutSceneRole = "hostage_runner_retreat";
                    profile.ScoutFormation = "escape";
                    profile.RitualSceneRole = "binding_circle_cut";
                    profile.RitualFormation = "ring";
                    profile.AmbushSceneRole = "captor_ambush_wave";
                    profile.AmbushFormation = "ambush";
                    profile.InterceptSceneRole = "rescue_screen";
                    profile.InterceptFormation = "wedge";
                    profile.CombatSceneRole = "extraction_counterline";
                    profile.ChoiceConfrontationRole = "hostage_exchange_standoff";
                    profile.ChoiceFalloutRole = "witness_extraction";
                    profile.HoldRole = "safe_corridor_hold";
                    profile.BranchCompanionRole = "rescued_signal_witness";
                    profile.AcceptActorCount = 6;
                    profile.ScoutActorCount = 20;
                    profile.RitualActorCount = 28;
                    profile.InterceptActorCount = 44;
                    profile.ChoiceActorCount = 56;
                    profile.ChoiceFalloutActorCount = 32;
                    profile.HoldActorCount = 48;
                    profile.ScoutText = "묶인 증인이 몸을 틀어 탈출 신호를 보내자, 감시병들이 양쪽 길을 막으며 후퇴로를 좁힙니다.";
                    profile.RitualText = $"{realmTexture}의 결박 표식이 끊기자 경비들이 원을 벌리고, 포로를 빼낼 좁은 통로를 만들기 시작합니다.";
                    profile.AmbushText = "위협이 쓰러지자 포로를 지키던 감시병들이 일제히 달려들고, 방패선이 증인과 칼날 사이를 가릅니다.";
                    profile.InterceptText = "포로는 아직 뛰지 못합니다. 방패선을 앞으로 밀어 안전한 통로를 만들어야 합니다.";
                    profile.CombatText = "구출대가 반원으로 물러서며 포로를 뒤로 보내고, 남은 감시병들은 끊긴 결박끈을 되찾으려 돌진합니다.";
                    profile.ChoiceFalloutText = "선택이 내려지자 증인은 방패 뒤로 옮겨지고, 추격자들이 막힌 길목에서 서로 다른 명령을 기다립니다.";
                    profile.HoldText = "경비들이 통로 양끝에 버티고 서서, 포로가 숨을 고를 시간까지 길목을 내주지 않습니다.";
                    profile.BranchCompanionText = "결박끈의 매듭은 다음 감금 장소를 가리킵니다. 이 구출은 끝이 아니라 다른 포로들의 시작입니다.";
                    profile.CompleteText = $"{realmTexture}에 묶인 숨소리 대신 낮은 대화가 돌아옵니다. 살아남은 증언은 이제 걸어서 돌아갈 수 있습니다.";
                    break;
                case "siege-break":
                    profile.WitnessName = "Rowan";
                    profile.AntagonistName = "Marshal Cailan";
                    profile.EvidenceName = "불탄 보급 표식";
                    profile.AcceptSceneRole = "siege_watch";
                    profile.AcceptFormation = "line";
                    profile.ScoutSceneRole = "blockade_scout_line";
                    profile.ScoutFormation = "patrol";
                    profile.RitualSceneRole = "supply_mark_break";
                    profile.RitualFormation = "line";
                    profile.AmbushSceneRole = "blockade_wave";
                    profile.AmbushFormation = "ambush";
                    profile.InterceptSceneRole = "breach_shield_push";
                    profile.InterceptFormation = "wedge";
                    profile.CombatSceneRole = "breach_counterline";
                    profile.ChoiceConfrontationRole = "opened_gate_standoff";
                    profile.ChoiceFalloutRole = "supply_route_advance";
                    profile.HoldRole = "breach_hold";
                    profile.BranchCompanionRole = "route_signal_runner";
                    profile.AcceptActorCount = 8;
                    profile.ScoutActorCount = 24;
                    profile.RitualActorCount = 36;
                    profile.AmbushActorCount = 100;
                    profile.InterceptActorCount = 50;
                    profile.CombatActorCount = 36;
                    profile.ChoiceActorCount = 60;
                    profile.HoldActorCount = 52;
                    profile.ScoutText = "불탄 수레 뒤에서 정찰대가 포위 말뚝 사이를 재고, 막힌 길 전체가 전투선처럼 드러납니다.";
                    profile.RitualText = $"{realmTexture}의 보급 표식이 찢기자 경비들이 말뚝을 밀어내고, 첫 번째 틈을 향해 방패를 맞댑니다.";
                    profile.AmbushText = "위협이 쓰러지자 포위선 뒤의 병력이 파도처럼 일어나고, 방패 든 경비들이 열린 틈을 지키러 전진합니다.";
                    profile.InterceptText = "지금 물러서면 길은 다시 닫힙니다. 방패 쐐기를 밀어 넣어 포위선을 깨야 합니다.";
                    profile.CombatText = "전열이 쐐기처럼 벌어지며 보급로를 열고, 후방의 전투원들이 뒤따라오는 적을 밀어냅니다.";
                    profile.ChoiceFalloutText = "선택이 내려지자 보급 표식이 새 방향으로 세워지고, 열린 길목을 따라 경비들이 한 걸음씩 전진합니다.";
                    profile.HoldText = "경비들이 포위선의 틈을 몸으로 붙잡고, 마지막 수레가 지나갈 때까지 길을 닫히지 않게 버팁니다.";
                    profile.BranchCompanionText = "불탄 표식은 두 번째 봉쇄 지점을 가리킵니다. 길은 열렸지만 포위는 아직 끝나지 않았습니다.";
                    profile.CompleteText = $"{realmTexture}에 막혔던 수레바퀴 소리가 돌아옵니다. 오늘 열린 길은 싸움보다 오래 사람들을 살릴 겁니다.";
                    break;
                case "turncoat-parley":
                    profile.WitnessName = "Iseult";
                    profile.AntagonistName = "Envoy Marric";
                    profile.EvidenceName = "반쪽으로 접힌 전령 표식";
                    profile.AcceptSceneRole = "turncoat_witness";
                    profile.AcceptFormation = "wedge";
                    profile.ScoutSceneRole = "parley_runner_retreat";
                    profile.ScoutFormation = "escape";
                    profile.RitualSceneRole = "false_banner_lowered";
                    profile.RitualFormation = "line";
                    profile.AmbushSceneRole = "double_cross_ambush";
                    profile.AmbushFormation = "ambush";
                    profile.InterceptSceneRole = "parley_guard_split";
                    profile.InterceptFormation = "line";
                    profile.CombatSceneRole = "parley_counterline";
                    profile.ChoiceConfrontationRole = "turncoat_trial_standoff";
                    profile.ChoiceFalloutRole = "banner_fallout";
                    profile.HoldRole = "two_banner_hold";
                    profile.BranchCompanionRole = "turncoat_signal_witness";
                    profile.ScoutActorCount = 18;
                    profile.RitualActorCount = 30;
                    profile.InterceptActorCount = 42;
                    profile.ChoiceActorCount = 64;
                    profile.ChoiceFalloutActorCount = 30;
                    profile.HoldActorCount = 46;
                    profile.ScoutText = "전령이 접힌 표식을 떨어뜨리자 양쪽 경비가 동시에 움직이고, 협상 자리가 좁은 전장으로 변합니다.";
                    profile.RitualText = $"{realmTexture}의 거짓 깃발이 내려가자 경비들이 서로를 겨누고, 누가 먼저 속였는지 묻는 침묵이 깔립니다.";
                    profile.AmbushText = "위협이 쓰러지자 협상 뒤에 숨은 이중 매복이 드러나고, 방패 든 경비들이 두 깃발 사이를 갈라섭니다.";
                    profile.InterceptText = "전령을 죽이면 말은 사라지고, 믿으면 칼이 등 뒤로 올 수 있습니다. 대치선을 유지해야 합니다.";
                    profile.CombatText = "양쪽 전열이 한 걸음씩 물러서며 숨은 칼잡이를 가르고, 협상장은 가까스로 전투와 증언 사이에 머뭅니다.";
                    profile.ChoiceFalloutText = "선택이 내려지자 접힌 표식이 펼쳐지고, 두 깃발 아래의 경비들이 서로 다른 명령을 기다립니다.";
                    profile.HoldText = "방패선이 두 깃발 사이를 갈라 선 채, 배신자의 말이 기록될 때까지 누구도 먼저 칼을 들지 못하게 막습니다.";
                    profile.BranchCompanionText = "전령 표식의 접힌 선은 다음 배신자를 가리킵니다. 협상은 끝났지만 균열은 남아 있습니다.";
                    profile.CompleteText = $"{realmTexture}에 낮은 협상 소리가 남습니다. 오늘 믿은 말은 내일의 방패가 될 수도, 상처가 될 수도 있습니다.";
                    break;
            }

            return profile;
        }

        private static string CodexStorySceneTitle(string archetype, string nodeId, string realmTexture)
        {
            string key = $"{(archetype ?? string.Empty).Trim().ToLowerInvariant()}:{(nodeId ?? string.Empty).Trim().ToLowerInvariant()}";
            return key switch
            {
                "black-contract:talk" => $"{realmTexture}의 검은 계약",
                "black-contract:explore" => "탈출로에 남은 두 번째 이름",
                "black-contract:kill" => "계약자가 보낸 매복",
                "black-contract:return" => "찢긴 계약서를 든 귀환",
                "black-contract:choice" => "목격자를 숨길지 계약자를 밝힐지",
                "black-contract:complete" => $"{realmTexture}에 남은 침묵값",

                "witness-conspiracy:talk" => $"{realmTexture}의 맞지 않는 증언",
                "witness-conspiracy:explore" => "두 목격자가 가리킨 다른 길",
                "witness-conspiracy:kill" => "입막음꾼이 드러난 순간",
                "witness-conspiracy:return" => "숨긴 이름을 들고 돌아가는 길",
                "witness-conspiracy:choice" => "증인을 살릴 침묵과 진실",
                "witness-conspiracy:complete" => $"{realmTexture}에 남은 두 번째 진술",

                "oath-breach:talk" => $"{realmTexture}의 깨진 보호 맹세",
                "oath-breach:explore" => "찢긴 서약끈과 빈 초소",
                "oath-breach:kill" => "방패선 앞의 배신자들",
                "oath-breach:return" => "맹세의 조각을 든 귀환",
                "oath-breach:choice" => "안전한 거짓과 오래된 책임",
                "oath-breach:complete" => $"{realmTexture}에 다시 묶인 서약",

                "relic-echo:talk" => $"{realmTexture}의 울리는 성물",
                "relic-echo:explore" => "같은 문장을 되뇌는 표식",
                "relic-echo:kill" => "성물함 앞에 선 매복",
                "relic-echo:return" => "메아리를 품은 귀환",
                "relic-echo:choice" => "성물을 봉할지 읽을지",
                "relic-echo:complete" => $"{realmTexture}에 잦아든 울림",

                "blood-price:talk" => $"{realmTexture}의 피값 장부",
                "blood-price:explore" => "붉은 채무자의 길",
                "blood-price:kill" => "빚을 걷는 칼날들",
                "blood-price:return" => "닫히지 않은 장부",
                "blood-price:choice" => "빚을 묻을지 이름을 밝힐지",
                "blood-price:complete" => $"{realmTexture}에서 지워진 다음 이름",

                "border-omen:talk" => $"{realmTexture}의 경계 징조",
                "border-omen:explore" => "안쪽 길까지 번진 흠집",
                "border-omen:kill" => "문턱을 넘은 습격",
                "border-omen:return" => "경계석의 증거",
                "border-omen:choice" => "문을 봉할지 흔적을 따를지",
                "border-omen:complete" => $"{realmTexture}에 다시 세운 경계",

                "lost-heirloom:talk" => $"{realmTexture}의 사라진 유품",
                "lost-heirloom:explore" => "주인을 숨긴 물건",
                "lost-heirloom:kill" => "유품을 노린 매복",
                "lost-heirloom:return" => "돌아온 표식과 숨은 이름",
                "lost-heirloom:choice" => "구원할 사람과 무너질 거짓",
                "lost-heirloom:complete" => $"{realmTexture}에 돌아온 작은 유산",

                "hostage-rescue:talk" => $"{realmTexture}의 붙잡힌 증인",
                "hostage-rescue:explore" => "묶인 손이 남긴 신호",
                "hostage-rescue:kill" => "구출 통로를 여는 전투",
                "hostage-rescue:return" => "결박끈을 든 귀환",
                "hostage-rescue:choice" => "증인을 빼낼지 배후를 쫓을지",
                "hostage-rescue:complete" => $"{realmTexture}에 돌아온 숨소리",

                "siege-break:talk" => $"{realmTexture}의 막힌 길목",
                "siege-break:explore" => "불탄 수레와 포위 말뚝",
                "siege-break:kill" => "포위선을 깨는 순간",
                "siege-break:return" => "열린 보급로의 보고",
                "siege-break:choice" => "길을 지킬지 본대를 쫓을지",
                "siege-break:complete" => $"{realmTexture}에 다시 구르는 수레",

                "turncoat-parley:talk" => $"{realmTexture}의 배신자 협상",
                "turncoat-parley:explore" => "접힌 표식과 거짓 깃발",
                "turncoat-parley:kill" => "협상을 깨는 이중 매복",
                "turncoat-parley:return" => "전령 표식을 든 귀환",
                "turncoat-parley:choice" => "배신자를 믿을지 넘길지",
                "turncoat-parley:complete" => $"{realmTexture}에 남은 두 깃발",

                _ => nodeId switch
                {
                    "explore" => "꺼진 불씨와 되돌아온 흔적",
                    "kill" => "침묵이 몸을 얻는 순간",
                    "return" => "증거를 쥔 귀환",
                    "choice" => "마을이 원하는 결말과 길이 원하는 진실",
                    "complete" => $"{realmTexture}에 남은 작은 변화",
                    _ => $"{realmTexture}의 사라진 발자국"
                }
            };
        }

        private static string CodexStoryDramaticSecret(string archetype, string realmTexture, string target)
        {
            return (archetype ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "black-contract" => "찢긴 계약서에는 목표 이름보다 먼저 목격자의 이동 경로가 적혀 있어, 살인은 아직 끝나지 않았음을 말한다.",
                "witness-conspiracy" => "두 목격자는 같은 밤을 봤다고 말하지만, 한 사람의 진술만 유독 이름 하나를 비워 둔다.",
                "oath-breach" => "찢긴 서약끈에는 안쪽 초소의 매듭법이 남아 있어, 배신이 바깥에서만 온 것이 아님을 말한다.",
                "relic-echo" => "성물의 울림은 사람의 목소리처럼 낮게 되돌아오며, 같은 이름을 세 번 삼킨다.",
                "blood-price" => "장부의 마지막 줄은 아직 마르지 않았고, 다음 채무자로 적힌 이름은 살아 있는 사람의 것이다.",
                "border-omen" => "경계석의 흠집은 바깥에서 안쪽으로 난 것이 아니라, 안쪽 사람이 길을 열어 준 모양으로 새겨져 있다.",
                "lost-heirloom" => "유품 안쪽의 낡은 표식은 도난품의 소유자가 아니라 숨겨진 보호자의 이름을 가리킨다.",
                "hostage-rescue" => "결박끈의 매듭은 포로가 버틴 시간이 아니라, 감시병이 교대하는 정확한 순서를 남기고 있다.",
                "siege-break" => "불탄 보급 표식은 공격자의 것이 아니라 안쪽 사람이 길을 막기 위해 넘겨 준 물자표와 맞아떨어진다.",
                "turncoat-parley" => "전령 표식의 접힌 면 안쪽에는 협상 장소보다 먼저 매복 위치가 표시되어 있다.",
                _ => $"{target} 뒤에는 아직 말하지 않은 손길이 남아 있다."
            };
        }

        private static string CodexStoryDramaticPressure(string archetype, string realmTexture, string target)
        {
            return (archetype ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "black-contract" => "망보는 자들이 탈출로를 닫기 전에 목격자를 찾지 못하면, 계약자는 증거와 사람을 같은 밤에 지울 것이다.",
                "witness-conspiracy" => "도망치려는 증인을 입막음꾼들이 좁은 길로 몰고 있어, 진술이 사라지기 전에 움직여야 한다.",
                "oath-breach" => "무너진 초소의 경비들은 서로를 의심한 채 방패선을 세우고, 누가 문을 열었는지 밝히기를 두려워한다.",
                "relic-echo" => "성물의 울림이 커질수록 바닥의 표식은 원을 만들고, 원 안의 사람들은 같은 말을 반복하기 시작한다.",
                "blood-price" => "채무자의 표식은 마을 안쪽으로 이어지고, 빚을 걷는 자들은 살아 있는 사람을 담보처럼 부른다.",
                "border-omen" => "표식은 경계 바깥이 아니라 안쪽 길목마다 반복되어, 이미 침범이 시작됐다는 압박을 남긴다.",
                "lost-heirloom" => "물건을 숨긴 사람은 도둑이 아니라 누군가를 보호한 증인일 수 있어, 추적 자체가 사람을 위험하게 만든다.",
                "hostage-rescue" => "감시병들이 포로를 옮기기 전까지 시간이 많지 않고, 성급한 돌입은 포로를 방패막이로 만들 수 있다.",
                "siege-break" => "포위선은 점점 좁아지고 보급로는 끊겨 있어, 길을 열지 못하면 싸우기 전에 지역이 굶주린다.",
                "turncoat-parley" => "협상 자리에 모인 양쪽 경비가 서로를 겨누고 있어, 숨은 칼잡이를 드러내기 전에는 말도 칼도 위험하다.",
                _ => $"{target}의 흔적은 단순한 습격보다 오래된 의도를 품고 있다."
            };
        }

        private static string CodexStoryDramaticAction(string archetype, string realmTexture, string target)
        {
            return (archetype ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "black-contract" => "계약자의 표식이 드러나는 순간 숨어 있던 칼잡이들이 일어나고, 도망치던 목격자를 향한 추격전이 전투로 번진다.",
                "witness-conspiracy" => "입막음꾼들이 증인의 퇴로를 끊으며 튀어나오고, 거짓 진술을 지키려는 칼날이 먼저 달려든다.",
                "oath-breach" => "배신한 경비의 신호에 맞춰 매복 병력이 일어나고, 남은 방패선은 무너진 서약을 몸으로 막아 낸다.",
                "relic-echo" => "성물의 울림이 갑자기 끊기자 숨어 있던 추종자들이 동시에 고개를 들고, 표식의 원이 전장처럼 열린다.",
                "blood-price" => "빚을 걷는 자들이 장부를 닫으며 달려들고, 다음 이름을 지우지 못하게 막으려는 싸움이 벌어진다.",
                "border-omen" => "경계 안쪽에서 숨어 있던 침입자가 신호를 올리고, 길목 전체가 한순간 전투선으로 바뀐다.",
                "lost-heirloom" => "유품을 노린 자들이 물건이 드러나는 순간 움직이고, 보호받던 이름을 지우려는 매복이 시작된다.",
                "hostage-rescue" => "결박 표식이 끊기는 순간 감시병들이 포로를 향해 달려들고, 구출 통로를 지키는 싸움이 시작된다.",
                "siege-break" => "포위 말뚝이 쓰러지자 막고 있던 병력이 파도처럼 일어나고, 방패 쐐기가 열린 틈을 밀고 들어간다.",
                "turncoat-parley" => "거짓 깃발이 내려가는 순간 이중 매복이 뛰쳐나오고, 협상장은 증언과 배신 사이의 전장으로 뒤집힌다.",
                _ => $"{target} 위협을 지키던 매복이 동시에 움직인다."
            };
        }

        private static string CodexStoryDramaticChoice(string archetype, string realmTexture, string target)
        {
            return (archetype ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "black-contract" => "목격자를 숨기면 계약의 배후는 남지만 한 생명은 살고, 계약서를 공개하면 더 큰 칼날이 마을을 향할 수 있다.",
                "witness-conspiracy" => "증인을 공개하면 진실은 살아나지만 누군가는 곧바로 사냥감이 되고, 숨기면 거짓 기록이 다시 힘을 얻는다.",
                "oath-breach" => "배신자를 밝히면 초소는 흔들리지만 맹세를 다시 묶을 수 있고, 덮으면 오늘 밤의 안전만 남는다.",
                "relic-echo" => "성물을 봉하면 울림은 멎지만 원인은 묻히고, 문장을 끝까지 읽으면 더 오래된 이름이 깨어날 수 있다.",
                "blood-price" => "장부를 태우면 다음 희생자는 살지만 배후는 어둠에 남고, 공개하면 마을 전체가 빚의 원한을 마주한다.",
                "border-omen" => "문을 봉하면 침범은 멈추지만 길을 연 사람은 숨고, 흔적을 따르면 안쪽 배신까지 드러난다.",
                "lost-heirloom" => "목격자를 먼저 숨기면 피난길은 안전해지고, 장부를 열면 유품을 빼앗은 손이 드러난다.",
                "hostage-rescue" => "증인을 바로 빼내면 생명은 지키지만 배후는 달아나고, 추격하면 구출한 사람이 다시 표적이 된다.",
                "siege-break" => "열린 길을 지키면 사람들은 살지만 적장은 물러나고, 본대를 쫓으면 보급로가 다시 닫힐 수 있다.",
                "turncoat-parley" => "배신자의 말을 받아들이면 숨은 이름을 얻지만 신뢰가 무너지고, 넘기면 오늘의 피는 줄어도 진실이 닫힌다.",
                _ => "안전을 택할지 진실을 택할지 결정해야 한다."
            };
        }

        private static string CodexStoryDramaticAftermath(string archetype, string realmTexture, string target)
        {
            return (archetype ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "black-contract" => "계약서는 찢겼지만, 그 이름을 쓴 손이 아직 완전히 사라진 것은 아니다.",
                "witness-conspiracy" => "살아남은 증언은 이제 기록이 되었지만, 그 기록을 두려워하는 사람도 함께 남았다.",
                "oath-breach" => "찢긴 서약끈은 다시 묶였지만, 누가 처음 끊었는지에 대한 의심은 오래 남을 것이다.",
                "relic-echo" => "성물의 울림은 잦아들었지만, 마지막 메아리는 아직 완전히 사라지지 않았다.",
                "blood-price" => "장부에서 다음 이름은 지워졌지만, 피값을 받으러 온 손길은 언젠가 다른 문을 두드릴 수 있다.",
                "border-omen" => "경계는 다시 세워졌지만, 안쪽에서 열린 길의 흔적은 오래 감시해야 한다.",
                "lost-heirloom" => "유품은 돌아왔지만, 그 물건이 지킨 사람과 드러낸 거짓은 서로 다른 무게로 남았다.",
                "hostage-rescue" => "증인은 살아 돌아왔지만, 결박끈의 매듭을 아는 손은 아직 다른 어딘가에 남아 있다.",
                "siege-break" => "길은 열렸지만 포위선을 세운 명령은 아직 완전히 사라지지 않았다.",
                "turncoat-parley" => "협상은 살아남았지만, 배신자의 말이 누구를 살리고 누구를 무너뜨릴지는 오래 남을 것이다.",
                _ => $"{realmTexture}에는 사건의 흔적이 낮은 소문처럼 남는다."
            };
        }

        private static string CodexStoryOpeningBeat(string archetype, string realmTexture, string target)
        {
            return (archetype ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "black-contract" => $"{realmTexture}에 검은 계약 표식이 남았습니다. 목표보다 먼저 목격자가 사라지기 전에 움직여야 합니다.",
                "witness-conspiracy" => $"{realmTexture}의 증언이 서로 맞지 않습니다. 한 이름만 빠져 있고, 그 이름을 아는 사람이 지금 사라지려 합니다.",
                "oath-breach" => $"{realmTexture}의 보호 맹세가 안쪽 매듭으로 찢겼습니다. 바깥 적보다 문을 연 사람이 더 위험합니다.",
                "relic-echo" => $"{realmTexture}의 성물이 같은 말을 되풀이합니다. 울림이 커지기 전에 표식을 끊어야 합니다.",
                "blood-price" => $"{realmTexture}의 장부에 다음 이름이 적혔습니다. {target} 뒤의 채권자들이 오늘 밤 값을 받으러 옵니다.",
                "border-omen" => $"{realmTexture}의 경계가 바깥이 아니라 안쪽에서 긁혔습니다. 침범은 이미 시작됐습니다.",
                "lost-heirloom" => $"{realmTexture}에서 사라진 유품이 돌아왔지만, 진짜 주인의 이름은 아직 숨겨져 있습니다.",
                "hostage-rescue" => $"{realmTexture}의 포로가 아직 살아 있습니다. 감시병 교대 전에 구출 통로를 열어야 합니다.",
                "siege-break" => $"{realmTexture}의 길이 포위 말뚝으로 막혔습니다. 보급로가 닫히기 전에 전선을 깨야 합니다.",
                "turncoat-parley" => $"{realmTexture}에서 배신자가 협상을 청했습니다. 말이 끝나기 전에 숨은 매복을 드러내야 합니다.",
                _ => $"{realmTexture} 쪽의 침묵이 너무 깊습니다. 목격자가 탈출로로 후퇴하는 그림자를 봤습니다."
            };
        }

        private static string CodexStoryChoiceBeat(string archetype, string realmTexture, string target)
        {
            return (archetype ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "black-contract" => "계약서는 찢을 수 있습니다. 하지만 누가 값을 치렀는지 밝히면 더 큰 칼날이 움직입니다.",
                "witness-conspiracy" => "사람들은 끝났다는 말을 원하지만, 증인은 아직 이름 하나를 삼키고 있습니다. 말하게 할지 숨겨 줄지 정해야 합니다.",
                "oath-breach" => "방패선은 다시 섰지만 맹세를 깬 손은 남아 있습니다. 오늘의 안전을 택할지 책임을 밝힐지 정해야 합니다.",
                "relic-echo" => "성물은 조용해졌지만 마지막 문장은 아직 남았습니다. 봉할지 읽을지 지금 결정해야 합니다.",
                "blood-price" => "장부는 닫혔지만 다음 이름의 잉크가 아직 젖어 있습니다. 태울지 공개할지 선택해야 합니다.",
                "border-omen" => "경계는 닫을 수 있습니다. 하지만 누가 안쪽에서 길을 열었는지는 지금 묻지 않으면 사라집니다.",
                "lost-heirloom" => "유품은 돌려줄 수 있습니다. 그러나 진짜 주인을 밝히면 이 마을의 오래된 거짓도 함께 무너집니다.",
                "hostage-rescue" => "증인은 숨길 수 있습니다. 하지만 결박끈의 주인을 쫓으면 다른 포로의 길도 열릴 수 있습니다.",
                "siege-break" => "길은 열렸습니다. 지금 지키면 사람들은 살고, 쫓아가면 포위 명령의 주인을 찾을 수 있습니다.",
                "turncoat-parley" => "배신자는 말할 준비가 됐습니다. 믿으면 균열이 생기고, 넘기면 진실이 닫힙니다.",
                _ => "사람들은 끝났다는 말을 원합니다. 하지만 표식은 아직 답을 주지 않았고, 증인과 경비가 서로 마주 서 있습니다."
            };
        }

        private static DynamicQuestTemplate ApplyDeterministicFallbackStory(DynamicQuestTemplate baseTemplate)
        {
            DynamicQuestTemplate template = DynamicQuestStoryService.ApplyStory(
                baseTemplate,
                BuildDeterministicFallbackStory(baseTemplate),
                "deterministic-fallback",
                "structured-scaffold-v1");

            List<string> tags = new(template.Tags ?? Array.Empty<string>());
            tags.RemoveAll(tag => string.Equals(tag, "llm-ready", StringComparison.OrdinalIgnoreCase));
            tags.RemoveAll(IsStoryArchetypeTag);
            AddTagIfMissing(tags, "story-fallback");
            AddTagIfMissing(tags, $"story-archetype:{CodexStoryArchetype(baseTemplate)}");
            AddSignatureStoryArcTags(tags, template, CodexStoryArchetype(baseTemplate));
            AddStoryCinematicTags(tags);

            template.Tags = tags;
            template.Source = "fallback";
            template.StoryQualityScore = 0;
            template.StoryQualityJson = string.Empty;
            return template;
        }

        private static DynamicQuestTemplate ApplyGeneratedStoryOrCacheReadyFallback(
            DynamicQuestTemplate baseTemplate,
            DynamicQuestStoryGenerationResult generated)
        {
            DynamicQuestTemplate generatedTemplate = DynamicQuestStoryService.ApplyStory(
                baseTemplate,
                generated.Story,
                generated.ProviderName,
                generated.ModelName);
            generatedTemplate = EnsureBranchNarrativeScenes(generatedTemplate);
            generatedTemplate = EnsureChoiceSelectedSetPiece(generatedTemplate);
            generatedTemplate = EnsureWorldSignalSetPiece(generatedTemplate);
            if (IsStoryTemplateReadyForCache(generatedTemplate) &&
                !NeedsCinematicRuntimeFallback(generatedTemplate))
            {
                return generatedTemplate;
            }

            DynamicQuestTemplate fallback = DynamicQuestStoryService.ApplyStory(
                baseTemplate,
                BuildDeterministicFallbackStory(baseTemplate),
                generated.ProviderName,
                generated.ModelName);
            fallback = EnsureBranchNarrativeScenes(fallback);
            fallback = EnsureChoiceSelectedSetPiece(fallback);
            fallback = EnsureWorldSignalSetPiece(fallback);

            List<string> tags = new(fallback.Tags ?? Array.Empty<string>());
            tags.RemoveAll(IsStoryArchetypeTag);
            AddTagIfMissing(tags, $"story-archetype:{CodexStoryArchetype(baseTemplate)}");
            AddSignatureStoryArcTags(tags, fallback, CodexStoryArchetype(baseTemplate));
            AddStoryCinematicTags(tags);
            if (!tags.Contains("story-generated-fallback-upgraded", StringComparer.OrdinalIgnoreCase))
                tags.Add("story-generated-fallback-upgraded");
            fallback.Tags = tags;
            return fallback;
        }

        private static DynamicQuestTemplate ApplyCodexCuratedStory(DynamicQuestTemplate baseTemplate)
        {
            DynamicQuestTemplate template = DynamicQuestStoryService.ApplyStory(
                baseTemplate,
                BuildCodexCuratedStory(baseTemplate),
                CodexCuratedStoryProvider,
                CodexCuratedStoryModel);
            string storyArchetype = CodexStoryArchetype(baseTemplate);

            List<string> tags = new(template.Tags ?? Array.Empty<string>());
            tags.RemoveAll(tag => string.Equals(tag, "llm-ready", StringComparison.OrdinalIgnoreCase));
            if (!IsStarterLevelRange(template))
                tags.RemoveAll(tag => string.Equals(tag, "starter", StringComparison.OrdinalIgnoreCase));
            tags.RemoveAll(tag => (tag ?? string.Empty).StartsWith("llm-provider:", StringComparison.OrdinalIgnoreCase));
            tags.RemoveAll(tag => (tag ?? string.Empty).StartsWith("llm-model:", StringComparison.OrdinalIgnoreCase));
            tags.RemoveAll(IsStoryArchetypeTag);
            tags.RemoveAll(tag => (tag ?? string.Empty).StartsWith("story-title-variant:", StringComparison.OrdinalIgnoreCase));
            AddTagIfMissing(tags, $"llm-provider:{CodexCuratedStoryProvider}");
            AddTagIfMissing(tags, $"llm-model:{CodexCuratedStoryModel}");
            AddTagIfMissing(tags, "story-cache");
            AddTagIfMissing(tags, "codex-curated");
            AddTagIfMissing(tags, $"story-archetype:{storyArchetype}");
            AddTagIfMissing(tags, StoryFamilyTagForTemplate(template));
            AddSignatureStoryArcTags(tags, template, storyArchetype);
            AddStoryCinematicTags(tags, largeSetPieces: true);
            AddTagIfMissing(tags, "story-title-variant:v3");

            template.Tags = tags;
            template.Source = "codex-curated";
            return template;
        }

        private static void AddStoryCinematicTags(ICollection<string> tags, bool largeSetPieces = false)
        {
            AddTagIfMissing(tags, "story-cinematic");
            AddTagIfMissing(tags, "scene-director");
            AddTagIfMissing(tags, "story-title-variant:v3");
            AddTagIfMissing(tags, "story-arc:motive");
            AddTagIfMissing(tags, "story-arc:conflict");
            AddTagIfMissing(tags, "story-arc:reversal");
            AddTagIfMissing(tags, "story-arc:consequence");
            AddTagIfMissing(tags, "cinematic-actors:ambush_reveal:8");
            AddTagIfMissing(tags, "cinematic-actors:defender_intercept:6");
            AddTagIfMissing(tags, "cinematic-actors:threat_standoff:6");
            AddTagIfMissing(tags, "cinematic-actors:ritual_interrupt:5");
            AddTagIfMissing(tags, "cinematic-actors:scout_retreat:3");
            AddTagIfMissing(tags, "cinematic-actors:guard_advance:4");
            AddTagIfMissing(tags, "cinematic-actors:combat_stance:5");
            AddTagIfMissing(tags, "cinematic-actors:hold_ground:4");

            if (!largeSetPieces)
                return;

            AddTagIfMissing(tags, "mass-cinematic");
            AddTagIfMissing(tags, "cinematic-actors:ambush_reveal:100");
            AddTagIfMissing(tags, "cinematic-actors:defender_intercept:32");
            AddTagIfMissing(tags, "cinematic-actors:threat_standoff:48");
            AddTagIfMissing(tags, "cinematic-actors:ritual_interrupt:40");
            AddTagIfMissing(tags, "cinematic-actors:guard_advance:24");
            AddTagIfMissing(tags, "cinematic-actors:combat_stance:24");
            AddTagIfMissing(tags, "cinematic-actors:hold_ground:36");
        }

        private static void AddTagIfMissing(ICollection<string> tags, string value)
        {
            if (tags == null || string.IsNullOrWhiteSpace(value))
                return;

            if (!tags.Any(tag => string.Equals(tag, value, StringComparison.OrdinalIgnoreCase)))
                tags.Add(value);
        }

        private static string BranchWorldSignalForStory(DynamicQuestTemplate template)
        {
            string tag = (template?.Tags ?? Array.Empty<string>())
                .FirstOrDefault(value => (value ?? string.Empty).StartsWith("world-signal:", StringComparison.OrdinalIgnoreCase));
            if (string.IsNullOrWhiteSpace(tag))
                return string.Empty;

            return tag.Substring("world-signal:".Length).Trim();
        }

        private static string CodexStoryArchetype(DynamicQuestTemplate template)
        {
            string branchWorldSignal = BranchWorldSignalForStory(template);
            string branchArchetype = CodexStoryArchetypeForWorldSignal(branchWorldSignal, template);
            if (!string.IsNullOrWhiteSpace(branchArchetype))
                return branchArchetype;

            string raw = string.Join("|", new[]
            {
                template?.TemplateId ?? string.Empty,
                template?.Realm ?? string.Empty,
                (template?.PreferredRegionId ?? 0).ToString(),
                template?.TargetNameHint ?? string.Empty,
                template?.Trigger ?? string.Empty,
                branchWorldSignal
            });

            byte[] hash = SHA256.HashData(Encoding.UTF8.GetBytes(raw.ToLowerInvariant()));
            return PickCodexStoryArchetype(hash[0], new[]
            {
                "black-contract",
                "witness-conspiracy",
                "oath-breach",
                "relic-echo",
                "blood-price",
                "border-omen",
                "lost-heirloom",
                "hostage-rescue",
                "siege-break",
                "turncoat-parley"
            });
        }

        private static string PickCodexStoryArchetype(byte seed, IReadOnlyList<string> candidates)
        {
            if (candidates == null || candidates.Count == 0)
                return "witness-conspiracy";

            return candidates[seed % candidates.Count];
        }

        private static string CodexStoryArchetypeForWorldSignal(string branchWorldSignal, DynamicQuestTemplate template)
        {
            string signal = branchWorldSignal ?? string.Empty;
            if (string.IsNullOrWhiteSpace(signal))
                return string.Empty;

            string raw = string.Join("|", new[]
            {
                template?.TemplateId ?? string.Empty,
                template?.Realm ?? string.Empty,
                (template?.PreferredRegionId ?? 0).ToString(),
                template?.TargetNameHint ?? string.Empty,
                signal
            });
            byte[] hash = SHA256.HashData(Encoding.UTF8.GetBytes(raw.ToLowerInvariant()));

            if (signal.StartsWith("time-window", StringComparison.OrdinalIgnoreCase))
            {
                return PickCodexStoryArchetype(hash[0], new[]
                {
                    "black-contract",
                    "witness-conspiracy",
                    "border-omen",
                    "lost-heirloom",
                    "hostage-rescue",
                    "turncoat-parley"
                });
            }
            if (signal.StartsWith("mob-growth", StringComparison.OrdinalIgnoreCase))
            {
                return PickCodexStoryArchetype(hash[0], new[]
                {
                    "oath-breach",
                    "blood-price",
                    "border-omen",
                    "siege-break"
                });
            }
            if (signal.StartsWith("item-acquired", StringComparison.OrdinalIgnoreCase))
            {
                return PickCodexStoryArchetype(hash[0], new[]
                {
                    "black-contract",
                    "relic-echo",
                    "lost-heirloom",
                    "blood-price",
                    "hostage-rescue"
                });
            }
            if (signal.StartsWith("region-entered", StringComparison.OrdinalIgnoreCase))
            {
                return PickCodexStoryArchetype(hash[0], new[]
                {
                    "border-omen",
                    "black-contract",
                    "witness-conspiracy",
                    "oath-breach",
                    "siege-break",
                    "turncoat-parley"
                });
            }

            return string.Empty;
        }

        private static string CodexStoryArchetypeForWorldSignal(string branchWorldSignal)
        {
            string signal = branchWorldSignal ?? string.Empty;
            if (signal.StartsWith("time-window", StringComparison.OrdinalIgnoreCase))
                return "witness-conspiracy";
            if (signal.StartsWith("mob-growth", StringComparison.OrdinalIgnoreCase))
                return "oath-breach";
            if (signal.StartsWith("item-acquired", StringComparison.OrdinalIgnoreCase))
                return "relic-echo";

            return string.Empty;
        }

        private static string CodexStoryTitle(DynamicQuestTemplate template, string archetype, string branchWorldSignal, string realmTexture)
        {
            string signal = branchWorldSignal ?? string.Empty;
            if (signal.StartsWith("time-window", StringComparison.OrdinalIgnoreCase))
                return PickCodexStoryTitle(template, realmTexture, new[]
                {
                    "정해진 밤",
                    "두 번째 종소리",
                    "은빛으로 뜬 발자국",
                    "꺼지지 않는 시간의 흔적"
                });
            if (signal.StartsWith("item-acquired", StringComparison.OrdinalIgnoreCase))
                return PickCodexStoryTitle(template, realmTexture, new[]
                {
                    "손안에 남은 표식",
                    "피 묻은 단서",
                    "성물이 가리킨 길",
                    "주머니 속의 낮은 울림"
                });
            if (signal.StartsWith("mob-growth", StringComparison.OrdinalIgnoreCase))
                return PickCodexStoryTitle(template, realmTexture, new[]
                {
                    "자라난 그림자",
                    "무거워진 발자국",
                    "되돌아온 사냥길",
                    "커져 가는 맹세의 상처"
                });
            if (signal.StartsWith("region-entered", StringComparison.OrdinalIgnoreCase))
                return PickCodexStoryTitle(template, realmTexture, new[]
                {
                    "너머의 같은 발자국",
                    "경계 밖의 표식",
                    "바람이 바뀐 길",
                    "다른 문에 남은 흠집"
                });

            return archetype switch
            {
                "black-contract" => PickCodexStoryTitle(template, realmTexture, new[] { "검은 계약", "침묵값의 밤", "탈출로의 이름", "계약서에 없는 목격자" }),
                "witness-conspiracy" => PickCodexStoryTitle(template, realmTexture, new[] { "숨긴 증언", "닫힌 입술의 밤", "증인이 버린 길", "거짓 불빛" }),
                "oath-breach" => PickCodexStoryTitle(template, realmTexture, new[] { "깨진 맹세", "찢긴 보호끈", "돌아오지 않은 서약", "방패 아래의 균열" }),
                "relic-echo" => PickCodexStoryTitle(template, realmTexture, new[] { "울리는 성물", "돌아오는 메아리", "성물함의 낮은 말", "고리 속의 잔향" }),
                "blood-price" => PickCodexStoryTitle(template, realmTexture, new[] { "피값의 장부", "붉게 접힌 약속", "빚으로 남은 밤", "되갚을 이름" }),
                "border-omen" => PickCodexStoryTitle(template, realmTexture, new[] { "경계의 징조", "바람이 바뀐 길", "깃발 아래의 흠집", "문턱에 선 그림자" }),
                "lost-heirloom" => PickCodexStoryTitle(template, realmTexture, new[] { "잃어버린 유품", "돌아오지 않은 표식", "주인 없는 성물함", "가문이 숨긴 물건" }),
                "hostage-rescue" => PickCodexStoryTitle(template, realmTexture, new[] { "붙잡힌 증인", "방패 뒤의 구출", "묶인 손의 신호", "탈출로의 방패선" }),
                "siege-break" => PickCodexStoryTitle(template, realmTexture, new[] { "막힌 길목", "부서지는 포위선", "문턱의 돌파", "불탄 수레의 전선" }),
                "turncoat-parley" => PickCodexStoryTitle(template, realmTexture, new[] { "배신자의 협상", "두 깃발 아래의 약속", "말보다 빠른 칼", "뒤집힌 전령의 표식" }),
                _ => PickCodexStoryTitle(template, realmTexture, new[] { "사라진 발자국", "꺼진 불씨", "낮게 접힌 길", "마지막 목격" })
            };
        }

        private static string PickCodexStoryTitle(DynamicQuestTemplate template, string realmTexture, IReadOnlyList<string> variants)
        {
            if (variants == null || variants.Count == 0)
                return $"{realmTexture}의 사라진 발자국";

            string raw = string.Join("|", new[]
            {
                template?.TemplateId ?? string.Empty,
                template?.Realm ?? string.Empty,
                template?.TargetNameHint ?? string.Empty,
                template?.Trigger ?? string.Empty,
                template?.PreferredRegionId.ToString() ?? string.Empty
            });
            byte[] hash = SHA256.HashData(Encoding.UTF8.GetBytes(raw.ToLowerInvariant()));
            string suffix = variants[hash[0] % variants.Count];
            return suffix.StartsWith("너머", StringComparison.OrdinalIgnoreCase)
                ? $"{realmTexture} {suffix}"
                : $"{realmTexture}의 {suffix}";
        }

        private static string CodexStoryArchetypeMotive(string archetype, string realmTexture, string target)
        {
            return archetype switch
            {
                "black-contract" => $"{realmTexture}에 남은 계약 표식은 목표보다 목격자를 먼저 지우려는 손길을 가리킨다.",
                "witness-conspiracy" => "증언은 서로 맞지 않고, 누군가는 일부러 같은 의식 표식을 다른 방향에 두었다.",
                "oath-breach" => $"오래전 {realmTexture} 경비들이 세운 보호 맹세의 끈이 찢긴 채 발견되었고, 누군가 그 맹세를 깨뜨렸다.",
                "relic-echo" => "성물에 남은 울림이 같은 문장을 반복하고, 의식 표식은 지나간 길마다 그 울림을 따라 새겨져 있다.",
                "blood-price" => $"{target} 뒤에는 오래된 피값 장부가 남아 있고, 이름 없는 채무자가 그 빚을 다른 사람의 목숨으로 갚으려 한다.",
                "border-omen" => $"{realmTexture}의 경계석마다 같은 흠집이 생겼고, 그 방향은 단순한 습격보다 넓은 침범을 가리킨다.",
                "lost-heirloom" => "사라진 유품 하나가 여러 손을 거쳐 돌아왔고, 그 물건을 숨긴 사람은 아직 살아 있는 누군가를 지키려 한다.",
                "hostage-rescue" => $"{realmTexture}에 남은 묶인 손자국은 증인이 살아 있으며, 적이 그 사람을 미끼로 길목을 닫고 있음을 가리킨다.",
                "siege-break" => $"{realmTexture}의 수레와 말뚝이 일부러 불타 길을 막았고, 포위선은 마을보다 먼저 지원군의 길을 끊으려 한다.",
                "turncoat-parley" => "도망친 전령이 같은 표식을 두 번 남겼고, 하나는 도움을 청하지만 다른 하나는 매복 신호처럼 꺾여 있다.",
                _ => "증거들은 같은 장소를 가리키지만 서로 다른 손에 의해 놓인 것처럼 어긋나 있다."
            };
        }

        private static string CodexStoryArchetypeConflict(string archetype, string realmTexture, string target)
        {
            return archetype switch
            {
                "black-contract" => "계약자는 이름 없는 대가를 요구하고, 목격자는 살아남으려 탈출로와 거짓 표식 사이를 헤맨다.",
                "witness-conspiracy" => "목격자는 도망친 사람을 숨기려 하고, 경비는 그 이름을 지금 말하라고 압박한다.",
                "oath-breach" => "무너진 약속을 지키려는 경비와 살아남은 증인이 서로 다른 길을 가리킨다.",
                "relic-echo" => "울림이 거세지자 망보는 자들은 후퇴하고, 매복 병력은 더 좁은 고리로 다가온다.",
                "blood-price" => "채권자의 전령은 대가를 요구하고, 마을 사람들은 그 장부가 다시 열리면 다음 희생자가 생긴다고 두려워한다.",
                "border-omen" => "경계 순찰대는 지금 물러서야 한다고 말하지만, 현장의 표식은 이미 안쪽 길까지 번져 있다.",
                "lost-heirloom" => "유품을 돌려주면 한 집안은 살아나지만, 숨겨진 이름을 밝히면 오래 묻힌 배신도 함께 드러난다.",
                "hostage-rescue" => "구출을 서두르면 포로는 살 수 있지만 매복이 닫히고, 늦추면 증언이 적의 입맞춤으로 바뀔 수 있다.",
                "siege-break" => "포위선은 싸움을 기다리는 것이 아니라 굶주림을 기다리고 있어, 길을 열지 못하면 싸우지 않고도 사람들이 무너진다.",
                "turncoat-parley" => "전령은 배신을 고백하려 하지만 양쪽 경비가 서로를 겨누고 있어, 말 한마디가 전투를 시작할 수 있다.",
                _ => $"{realmTexture}에 남은 흔적은 더 오래된 갈등을 가리킨다."
            };
        }

        private static string CodexStoryArchetypeResolution(string archetype, string realmTexture, string target)
        {
            return archetype switch
            {
                "witness-conspiracy" => "진실을 밝히면 누군가가 위험해지고, 덮으면 같은 의식 표식이 다시 나타날 수 있다.",
                "oath-breach" => "안전을 택하면 오늘의 문은 닫히고, 맹세의 근원을 따지면 오래된 책임이 드러난다.",
                "relic-echo" => "성물의 메아리를 끊으면 길은 조용해지지만, 남은 표식을 읽으면 더 오래된 원인이 열린다.",
                "blood-price" => "빚을 끊으면 당장의 피는 멎지만, 장부를 공개하면 더 큰 배후가 칼을 들 수 있다.",
                "border-omen" => "경계를 봉하면 오늘의 침범은 멈추지만, 표식을 따라가면 누가 길을 열었는지 드러난다.",
                "lost-heirloom" => "유품을 조용히 돌려주면 한 사람은 구원받지만, 진짜 주인을 밝히면 마을의 오래된 거짓말이 무너진다.",
                "hostage-rescue" => "포로를 먼저 빼내면 증언은 살아남지만 배후는 흩어지고, 추격하면 구출한 사람이 다시 위험해질 수 있다.",
                "siege-break" => "포위선을 깨면 길은 열리지만 적의 본대가 움직이고, 기다리면 오늘 밤의 안전 대신 내일의 고립이 남는다.",
                "turncoat-parley" => "배신자를 받아들이면 내부의 이름을 얻지만 신뢰는 흔들리고, 넘기면 전투는 줄어도 진실이 묻힌다.",
                _ => $"전투를 끝내도 {realmTexture}에 남은 표식은 마지막 결정을 요구한다."
            };
        }

        private static string BranchStoryTitle(string branchWorldSignal)
        {
            string signal = branchWorldSignal ?? string.Empty;
            if (signal.StartsWith("time-window", StringComparison.OrdinalIgnoreCase))
                return "정해진 시각에 열린 두 번째 흔적";
            if (signal.StartsWith("item-acquired", StringComparison.OrdinalIgnoreCase))
                return "손안의 단서가 밝히는 다음 길";
            if (signal.StartsWith("mob-growth", StringComparison.OrdinalIgnoreCase))
                return "더 커진 위협의 그림자";
            if (signal.StartsWith("region-entered", StringComparison.OrdinalIgnoreCase))
                return "경계 너머에서 되살아난 발자국";

            return "남은 표식이 흔들리는 순간";
        }

        private static string BranchStoryBody(string realmTexture, string target, string branchWorldSignal)
        {
            string signal = branchWorldSignal ?? string.Empty;
            if (signal.StartsWith("time-window", StringComparison.OrdinalIgnoreCase))
                return $"{realmTexture}에 어둠이 내려앉자 낮에는 보이지 않던 자국이 은빛으로 떠오른다. 이 사건은 시간에 맞춰 움직이는 더 큰 흐름의 일부였다.";
            if (signal.StartsWith("item-acquired", StringComparison.OrdinalIgnoreCase))
                return $"손에 넣은 단서가 {realmTexture}의 오래된 표식과 맞물린다. 둘러싼 위협은 우연히 흘린 흔적이 아니라 누군가 남긴 길잡이처럼 보인다.";
            if (signal.StartsWith("mob-growth", StringComparison.OrdinalIgnoreCase))
                return $"더 무거운 발자국이 {realmTexture} 깊은 곳으로 이어진다. 오늘 제압한 위협은 더 큰 사냥감이 남긴 그림자였을지도 모른다.";
            if (signal.StartsWith("region-entered", StringComparison.OrdinalIgnoreCase))
                return $"{realmTexture}의 경계를 넘자 바람이 바뀌고, 같은 표식이 다시 나타난다. 이 사건은 한 길목에 머무르지 않고 지역 전체로 번질 수 있다.";

            return $"{realmTexture}에 남은 표식이 떨리며 새로운 방향을 가리킨다. 사건 뒤에는 아직 설명되지 않은 침묵이 남아 있다.";
        }

        private static string BranchStoryJournal(string realmTexture, string target, string branchWorldSignal)
        {
            string signal = branchWorldSignal ?? string.Empty;
            if (signal.StartsWith("time-window", StringComparison.OrdinalIgnoreCase))
                return $"{realmTexture}에서 특정 시간에만 드러나는 숨은 흔적을 확인했다.";
            if (signal.StartsWith("item-acquired", StringComparison.OrdinalIgnoreCase))
                return $"손안의 단서가 {realmTexture}의 다음 흔적을 가리킨다는 사실을 확인했다.";
            if (signal.StartsWith("mob-growth", StringComparison.OrdinalIgnoreCase))
                return "위협 뒤에 더 커진 발자국이 남아 있음을 확인했다.";
            if (signal.StartsWith("region-entered", StringComparison.OrdinalIgnoreCase))
                return $"{realmTexture} 바깥에서도 같은 사건과 이어진 표식을 발견했다.";

            return $"{realmTexture}의 남은 표식이 다음 단서를 가리켰다.";
        }

        private static string BranchStoryBeat(string realmTexture, string target, string branchWorldSignal)
        {
            string signal = branchWorldSignal ?? string.Empty;
            if (signal.StartsWith("time-window", StringComparison.OrdinalIgnoreCase))
                return $"정해진 시각이 되자 {realmTexture}의 숨은 자국이 드러납니다.";
            if (signal.StartsWith("item-acquired", StringComparison.OrdinalIgnoreCase))
                return "손에 든 단서가 다음 방향을 가리킵니다.";
            if (signal.StartsWith("mob-growth", StringComparison.OrdinalIgnoreCase))
                return $"{realmTexture} 깊은 곳에서 더 무거운 발자국이 이어집니다.";
            if (signal.StartsWith("region-entered", StringComparison.OrdinalIgnoreCase))
                return $"경계를 넘자 {target} 사건과 같은 표식이 다시 나타납니다.";

            return $"{realmTexture}의 표식이 새로운 방향으로 흔들립니다.";
        }

        private static string RealmTextureForStory(string realm)
        {
            if (string.Equals(realm, "Albion", StringComparison.OrdinalIgnoreCase))
                return "수도원 길목";
            if (string.Equals(realm, "Midgard", StringComparison.OrdinalIgnoreCase))
                return "롱하우스 바깥 눈길";
            if (string.Equals(realm, "Hibernia", StringComparison.OrdinalIgnoreCase))
                return "고리석 숲길";
            return "마을 외곽 길목";
        }

        private static string RealmOmenForStory(string realm)
        {
            if (string.Equals(realm, "Albion", StringComparison.OrdinalIgnoreCase))
                return "젖은 종소리와 진흙 묻은 성벽 그림자";
            if (string.Equals(realm, "Midgard", StringComparison.OrdinalIgnoreCase))
                return "얼어붙은 숨결과 룬 새긴 말뚝";
            if (string.Equals(realm, "Hibernia", StringComparison.OrdinalIgnoreCase))
                return "이끼 낀 돌문양과 드루이드 매듭";
            return "부러진 수레바퀴와 오래된 발자국";
        }

        private static string RealmRelicForStory(string realm)
        {
            if (string.Equals(realm, "Albion", StringComparison.OrdinalIgnoreCase))
                return "작은 성물함";
            if (string.Equals(realm, "Midgard", StringComparison.OrdinalIgnoreCase))
                return "룬이 새겨진 뼛조각";
            if (string.Equals(realm, "Hibernia", StringComparison.OrdinalIgnoreCase))
                return "이끼 낀 고리석";
            return "낡은 이정표";
        }

        private static bool HasFallbackScaffoldTitle(string title)
        {
            string value = title ?? string.Empty;
            string[] terms = { "지역 분위기", "불안한 부탁", "흔적의 방향", "잠잠해진 길목", "처치 요청", "{{target}}" };
            return terms.Any(term => value.Contains(term, StringComparison.OrdinalIgnoreCase));
        }

        private static DynamicQuestResult AddTemplateBoundQuest(
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedNpc npc,
            DynamicQuestSeedNpc targetNpc,
            DynamicQuestSeedDefinition definition,
            string worldRevision)
        {
            DynamicQuestTemplateBindingResult binding = new DynamicQuestTemplateService()
                .BindTemplate(BuildTemplate(npc, targetNpc, definition, worldRevision), npcs);

            if (!binding.Success)
                return DynamicQuestResult.Fail($"{binding.Message}; {DescribeSeedBindingContext(npc, targetNpc)}");

            return DynamicQuestRuntimeService.Instance.AddQuest(binding.Quest);
        }

        private DynamicQuestTemplate LoadCachedStoryTemplate(string templateId, DynamicQuestTemplate baseTemplate)
        {
            DbDynamicQuestTemplate row = m_templateRepository.Find(templateId);
            if (!IsStoryCacheReadyForUse(row))
                return null;

            DynamicQuestTemplate cached = DynamicQuestTemplateService.FromRowForCache(row);
            RebindCachedStoryText(cached, baseTemplate.TargetNameHint);
            cached.Realm = baseTemplate.Realm;
            cached.PreferredStartNpcName = baseTemplate.PreferredStartNpcName;
            cached.PreferredStartNpcInternalId = baseTemplate.PreferredStartNpcInternalId;
            cached.PreferredRegionId = baseTemplate.PreferredRegionId;
            cached.TargetNameHint = baseTemplate.TargetNameHint;
            cached.PreferredTargetNpcInternalId = baseTemplate.PreferredTargetNpcInternalId;
            cached.Count = baseTemplate.Count;
            cached.MinLevel = baseTemplate.MinLevel;
            cached.MaxLevel = baseTemplate.MaxLevel;
            cached.StartMode = baseTemplate.StartMode;
            cached.Trigger = baseTemplate.Trigger;
            cached.WorldRevision = baseTemplate.WorldRevision;
            cached.Tags = MergeTags(baseTemplate.Tags, cached.Tags);
            return cached;
        }

        private static void RebindCachedStoryText(DynamicQuestTemplate cached, string currentTargetName)
        {
            if (cached == null || string.IsNullOrWhiteSpace(cached.TargetNameHint) ||
                string.IsNullOrWhiteSpace(currentTargetName) ||
                string.Equals(cached.TargetNameHint, currentTargetName, StringComparison.OrdinalIgnoreCase))
            {
                return;
            }

            cached.Title = ReplaceLiteralTargetWithPlaceholder(cached.Title, cached.TargetNameHint);
            cached.StorySeed = ReplaceLiteralTargetWithPlaceholder(cached.StorySeed, cached.TargetNameHint);
            cached.OfferText = ReplaceLiteralTargetWithPlaceholder(cached.OfferText, cached.TargetNameHint);
            cached.ProgressText = ReplaceLiteralTargetWithPlaceholder(cached.ProgressText, cached.TargetNameHint);
            cached.FinishText = ReplaceLiteralTargetWithPlaceholder(cached.FinishText, cached.TargetNameHint);
            cached.StoryNarrativeJson = ReplaceLiteralTargetWithPlaceholder(cached.StoryNarrativeJson, cached.TargetNameHint);
            cached.StoryPresentationJson = ReplaceLiteralTargetWithPlaceholder(cached.StoryPresentationJson, cached.TargetNameHint);
        }

        private static string ReplaceLiteralTargetWithPlaceholder(string value, string oldTargetName)
        {
            if (string.IsNullOrWhiteSpace(value) || string.IsNullOrWhiteSpace(oldTargetName) ||
                value.Contains("{{target}}", StringComparison.OrdinalIgnoreCase))
            {
                return value ?? string.Empty;
            }

            return value.Replace(oldTargetName, "{{target}}", StringComparison.OrdinalIgnoreCase);
        }

        private void SaveStoryTemplate(DynamicQuestTemplate template, string lastBindingKey)
        {
            DbDynamicQuestTemplate row = DynamicQuestTemplateService.ToRowForCache(template, lastBindingKey);
            DbDynamicQuestTemplate existing = m_templateRepository.Find(row.TemplateId);
            if (existing == null)
            {
                m_templateRepository.Add(row);
                return;
            }

            CopyTemplateRow(row, existing);
            existing.IsActive = true;
            m_templateRepository.Save(existing);
        }

        private void TouchStoryTemplate(string templateId, string bindingKey)
        {
            DbDynamicQuestTemplate row = m_templateRepository.Find(templateId);
            if (!IsActiveStoryCacheRow(row))
                return;

            row.LastBindingKey = bindingKey ?? string.Empty;
            DateTime now = UtcNow();
            row.StoryLastUsedAt = now;
            row.UpdatedAt = now;
            m_templateRepository.Save(row);
        }

        private void CleanupStoryCacheIfNeeded()
        {
            DeactivateUnknownRealmStoryRows();
            DeactivateMissingTargetStoryRows();
            DeactivateUnsafeHighLevelWorldPrefillRows();
            MarkRelatedDifficultyHistoryStoryRows();
            DeactivateStaleCodexCuratedStoryRows();

            DateTime now = UtcNow();
            if (!IsAfterGeminiDailyQuotaReset(now))
                return;

            DateTime quotaDate = DynamicQuestGeminiQuotaClock.PacificDate(now);
            int maxTemplates = StoryCacheMaxTemplates();
            List<DbDynamicQuestTemplate> storyRows = GetActiveStoryCacheRows().ToList();
            if (storyRows.Count < maxTemplates)
                return;

            lock (StoryCacheCleanupLock)
            {
                if (s_lastStoryCacheCleanupQuotaDate == quotaDate)
                    return;

                s_lastStoryCacheCleanupQuotaDate = quotaDate;
            }

            int pruneCount = Math.Clamp(StoryCachePruneCount(), 1, Math.Max(1, storyRows.Count));
            foreach (DbDynamicQuestTemplate row in storyRows
                         .OrderBy(row => IsStoryCacheReadyForUse(row) ? 1 : 0)
                         .ThenBy(StoryCacheCurrentQualityScore)
                         .ThenBy(row => StoryCacheSafetyScore(row))
                         .ThenBy(row => StoryCacheStructureScore(row))
                         .ThenBy(row => EffectiveLastUsed(row))
                         .Take(pruneCount))
            {
                row.IsActive = false;
                row.UpdatedAt = now;
                m_templateRepository.Save(row);
            }
        }

        private void DeactivateMissingTargetStoryRows()
        {
            DateTime now = UtcNow();
            foreach (DbDynamicQuestTemplate row in GetActiveStoryCacheRows()
                         .Where(row => string.Equals(
                             DummyEvaluationBlockReason(row),
                             "dummy_evaluation_target_missing",
                             StringComparison.OrdinalIgnoreCase))
                         .ToList())
            {
                row.IsActive = false;
                row.UpdatedAt = now;
                m_templateRepository.Save(row);
            }
        }

        private void DeactivateUnsafeHighLevelWorldPrefillRows()
        {
            DateTime now = UtcNow();
            foreach (DbDynamicQuestTemplate row in GetActiveStoryCacheRows()
                         .Where(IsUnsafeHighLevelWorldPrefillRow)
                         .ToList())
            {
                row.IsActive = false;
                row.UpdatedAt = now;
                m_templateRepository.Save(row);
            }
        }

        private static bool IsUnsafeHighLevelWorldPrefillRow(DbDynamicQuestTemplate row)
        {
            if (row == null ||
                row.DummyEvaluationCount > 0 ||
                row.MinLevel < 36 ||
                !string.Equals(row.StoryProvider, CodexCuratedStoryProvider, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            IList<string> tags = DeserializeStoryCacheTags(row.TagsJson);
            return tags.Contains("story-cache", StringComparer.OrdinalIgnoreCase) &&
                   tags.Contains("selector:start:quest-giver", StringComparer.OrdinalIgnoreCase);
        }

        private void DeactivateUnknownRealmStoryRows()
        {
            DateTime now = UtcNow();
            foreach (DbDynamicQuestTemplate row in GetActiveStoryCacheRows()
                         .Where(row => !IsStarterRealm(RealmNameForRegion(row.PreferredRegionId)))
                         .ToList())
            {
                row.IsActive = false;
                row.UpdatedAt = now;
                m_templateRepository.Save(row);
            }
        }

        private void MarkRelatedDifficultyHistoryStoryRows()
        {
            foreach (DbDynamicQuestTemplate row in GetActiveStoryCacheRows()
                         .Where(row => row.DummyEvaluationCount <= 0)
                         .Where(row => HasRelatedAutoAcceptDummyDifficultyFailure(row))
                         .ToList())
            {
                MarkStoryCacheTargetDifficultyHistory(
                    row,
                    DynamicQuestRuntimeService.Instance.GetTargetNameForTemplate(row.TemplateId));
            }
        }

        private void DeactivateStaleCodexCuratedStoryRows()
        {
            DateTime now = UtcNow();
            foreach (DbDynamicQuestTemplate row in GetActiveStoryCacheRows()
                         .Where(row => string.Equals(row.StoryProvider, CodexCuratedStoryProvider, StringComparison.OrdinalIgnoreCase))
                         .Where(row => !string.Equals(row.StoryModel, CodexCuratedStoryModel, StringComparison.OrdinalIgnoreCase))
                         .Where(row => !NeedsStoryCacheMetadataRepair(row))
                         .Where(row => !NeedsStoryCacheScaffoldUpgrade(row))
                         .ToList())
            {
                row.IsActive = false;
                row.UpdatedAt = now;
                m_templateRepository.Save(row);
            }
        }

        private static bool IsAfterGeminiDailyQuotaReset(DateTime utcNow)
        {
            int delayMinutes = Math.Clamp(Properties.KDAOC_DYNAMIC_QUEST_STORY_GEMINI_RESET_DELAY_MINUTES, 0, 1439);
            int windowMinutes = Properties.KDAOC_DYNAMIC_QUEST_STORY_GEMINI_RESET_WINDOW_MINUTES > 0
                ? Math.Clamp(Properties.KDAOC_DYNAMIC_QUEST_STORY_GEMINI_RESET_WINDOW_MINUTES, 1, 1440)
                : 360;
            double startMinutes = delayMinutes;
            double endMinutes = startMinutes + windowMinutes;
            double currentMinutes = DynamicQuestGeminiQuotaClock.PacificTimeOfDay(utcNow).TotalMinutes;

            if (endMinutes >= 1440)
                return currentMinutes >= startMinutes || currentMinutes < endMinutes - 1440;

            return currentMinutes >= startMinutes && currentMinutes < endMinutes;
        }

        private bool CanGenerateNewStory()
        {
            return GetActiveStoryCacheRows().Count() < StoryCacheMaxTemplates();
        }

        private int PrefillStoryCache(
            IList<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedOptions options,
            string worldRevision,
            IList<DynamicQuestSeedDefinition> definitions,
            DynamicQuestSeedSummary summary = null)
        {
            CleanupStoryCacheIfNeeded();
            UpgradeLegacyStoryCacheRows();

            int batchSize = StoryCachePrefillBatchSize();
            if (batchSize <= 0)
                return 0;

            int generatedCount = 0;
            int attemptedCount = 0;
            foreach (DynamicQuestSeedDefinition definition in definitions ?? Array.Empty<DynamicQuestSeedDefinition>())
            {
                if (generatedCount >= batchSize || attemptedCount >= batchSize || !CanGenerateNewStory())
                    break;

                DynamicQuestSeedResolveResult resolved = ResolveDefinition(npcs, definition);
                DynamicQuestSeedDefinition activeDefinition = resolved.Definition ?? definition;
                bool requiresStartNpc = RequiresStartNpc(activeDefinition);
                DynamicQuestSeedNpc npc = resolved.StartNpc ?? (requiresStartNpc ? FindSeedNpc(npcs, activeDefinition) : null);
                if (!resolved.Success || (requiresStartNpc && npc == null))
                {
                    if (summary != null)
                        summary.StoryCachePrefillResolveSkipped++;
                    continue;
                }

                if (HasAutoAcceptDummyDifficultyFailure(activeDefinition))
                {
                    if (summary != null)
                        summary.StoryCachePrefillResolveSkipped++;
                    continue;
                }

                DynamicQuestTemplate baseTemplate = BuildTemplate(npc, resolved.TargetNpc, activeDefinition, worldRevision);
                baseTemplate.Source = "llm";

                if (IsStoryCacheReadyForUse(m_templateRepository.Find(baseTemplate.TemplateId)))
                {
                    if (summary != null)
                        summary.StoryCachePrefillAlreadyReady++;
                    continue;
                }

                attemptedCount++;
                if (summary != null)
                    summary.StoryCachePrefillAttempted++;
                DynamicQuestStoryGenerationResult generated = m_storyService.TryGenerate(BuildStoryRequest(baseTemplate, options));
                if (!generated.Success)
                {
                    if (summary != null)
                    {
                        if ((generated.Error ?? string.Empty).Contains("quality_below_minimum", StringComparison.OrdinalIgnoreCase))
                        {
                            summary.StoryCachePrefillQualityRejected++;
                        }
                        else
                        {
                            summary.StoryCachePrefillGenerationFailed++;
                            AddPrefillGenerationErrors(summary, generated.Error);
                        }
                    }
                    if (Log.IsWarnEnabled)
                        Log.Warn($"Dynamic quest story cache prefill failed for {baseTemplate.TemplateId}: {generated.Error}");
                    continue;
                }

                DynamicQuestTemplate storyTemplate = ApplyGeneratedStoryOrCacheReadyFallback(baseTemplate, generated);

                if (!IsStoryTemplateReadyForCache(storyTemplate))
                {
                    if (summary != null)
                        summary.StoryCachePrefillQualityRejected++;
                    if (Log.IsWarnEnabled)
                        Log.Warn($"Dynamic quest story cache prefill rejected below cache quality gate for {baseTemplate.TemplateId}: score={storyTemplate.StoryQualityScore}");
                    continue;
                }

                SaveStoryTemplate(storyTemplate, string.Empty);
                generatedCount++;
            }

            return generatedCount;
        }

        private int PrefillCodexCuratedStoryCache(
            IList<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedOptions options,
            string worldRevision,
            IList<DynamicQuestSeedDefinition> definitions,
            DynamicQuestSeedSummary summary = null)
        {
            CleanupStoryCacheIfNeeded();
            UpgradeLegacyStoryCacheRows();

            int batchSize = StoryCachePrefillBatchSize();
            if (batchSize <= 0)
                return 0;

            int generatedCount = 0;
            int attemptedCount = 0;
            foreach (DynamicQuestSeedDefinition definition in definitions ?? Array.Empty<DynamicQuestSeedDefinition>())
            {
                if (generatedCount >= batchSize || attemptedCount >= batchSize || !CanGenerateNewStory())
                    break;

                DynamicQuestSeedResolveResult resolved = ResolveDefinition(npcs, definition);
                DynamicQuestSeedDefinition activeDefinition = resolved.Definition ?? definition;
                bool requiresStartNpc = RequiresStartNpc(activeDefinition);
                DynamicQuestSeedNpc npc = resolved.StartNpc ?? (requiresStartNpc ? FindSeedNpc(npcs, activeDefinition) : null);
                if (!resolved.Success || (requiresStartNpc && npc == null))
                {
                    if (summary != null)
                        summary.StoryCachePrefillResolveSkipped++;
                    continue;
                }

                if (HasAutoAcceptDummyDifficultyFailure(activeDefinition))
                {
                    if (summary != null)
                        summary.StoryCachePrefillResolveSkipped++;
                    continue;
                }

                DynamicQuestTemplate baseTemplate = BuildTemplate(npc, resolved.TargetNpc, activeDefinition, worldRevision);
                baseTemplate.Source = "codex-curated";

                if (IsStoryCacheReadyForUse(m_templateRepository.Find(baseTemplate.TemplateId)))
                {
                    if (summary != null)
                        summary.StoryCachePrefillAlreadyReady++;
                    continue;
                }

                attemptedCount++;
                if (summary != null)
                    summary.StoryCachePrefillAttempted++;

                DynamicQuestTemplate storyTemplate = ApplyCodexCuratedStory(baseTemplate);
                storyTemplate = EnsureBranchNarrativeScenes(storyTemplate);
                storyTemplate = EnsureChoiceSelectedSetPiece(storyTemplate);
                storyTemplate = EnsureWorldSignalSetPiece(storyTemplate);
                if (!IsStoryTemplateReadyForCache(storyTemplate))
                {
                    if (summary != null)
                        summary.StoryCachePrefillQualityRejected++;
                    if (Log.IsWarnEnabled)
                        Log.Warn($"Dynamic quest codex story cache prefill rejected below cache quality gate for {baseTemplate.TemplateId}: score={storyTemplate.StoryQualityScore}");
                    continue;
                }

                SaveStoryTemplate(storyTemplate, string.Empty);
                generatedCount++;
            }

            return generatedCount;
        }

        private static void AddStoryCachePrefillSummaryMessages(DynamicQuestSeedSummary summary)
        {
            if (summary == null)
                return;

            if (summary.StoryCachePrefilled > 0)
                AddUniqueSummaryMessage(summary, $"story cache prefilled: {summary.StoryCachePrefilled}");
            if (summary.StoryCachePrefillAttempted > 0)
                AddUniqueSummaryMessage(summary, $"story cache prefill attempted: {summary.StoryCachePrefillAttempted}");
            if (summary.StoryCachePrefillGenerationFailed > 0)
                AddUniqueSummaryMessage(summary, $"story cache prefill generation failed: {summary.StoryCachePrefillGenerationFailed}");
            foreach (KeyValuePair<string, int> pair in (summary.StoryCachePrefillGenerationErrors ?? new Dictionary<string, int>())
                         .OrderBy(pair => pair.Key, StringComparer.OrdinalIgnoreCase))
            {
                if (pair.Value > 0)
                    AddUniqueSummaryMessage(summary, $"story cache prefill error {pair.Key}: {pair.Value}");
            }
            if (summary.StoryCachePrefillQualityRejected > 0)
                AddUniqueSummaryMessage(summary, $"story cache prefill rejected by quality gate: {summary.StoryCachePrefillQualityRejected}");
            if (summary.StoryCachePrefillResolveSkipped > 0)
                AddUniqueSummaryMessage(summary, $"story cache prefill resolve skipped: {summary.StoryCachePrefillResolveSkipped}");
            if (summary.StoryCachePrefillAlreadyReady > 0)
                AddUniqueSummaryMessage(summary, $"story cache prefill already ready: {summary.StoryCachePrefillAlreadyReady}");
        }

        private static void AddUniqueSummaryMessage(DynamicQuestSeedSummary summary, string message)
        {
            if (summary?.Messages == null || string.IsNullOrWhiteSpace(message))
                return;

            if (!summary.Messages.Contains(message))
                summary.Messages.Add(message);
        }

        private bool HasAutoAcceptDummyDifficultyFailure(DynamicQuestSeedDefinition definition)
        {
            if (definition == null ||
                string.IsNullOrWhiteSpace(definition.TargetName))
            {
                return false;
            }

            IList<string> definitionTargets = BuildAutoAcceptDifficultyTargetNames(definition);
            return GetActiveStoryCacheRows().Any(row =>
                AnyTargetFamilyMatches(
                    definition.RegionId,
                    definitionTargets,
                    BuildAutoAcceptDifficultyTargetNames(
                        row,
                        DynamicQuestRuntimeService.Instance.GetTargetNameForTemplate(row.TemplateId))) &&
                string.Equals(DummyEvaluationBlockReason(row), "dummy_evaluation_difficulty_failed", StringComparison.OrdinalIgnoreCase));
        }

        private bool HasRelatedAutoAcceptDummyDifficultyFailure(DbDynamicQuestTemplate row, string runtimeTargetName = "")
        {
            if (row == null ||
                string.IsNullOrWhiteSpace(row.TargetNameHint))
            {
                return false;
            }

            string templateId = row.TemplateId ?? string.Empty;
            IList<string> rowTargets = BuildAutoAcceptDifficultyTargetNames(
                row,
                string.IsNullOrWhiteSpace(runtimeTargetName)
                    ? DynamicQuestRuntimeService.Instance.GetTargetNameForTemplate(templateId)
                    : runtimeTargetName);
            return GetActiveStoryCacheRows().Any(candidate =>
                !string.Equals(candidate.TemplateId ?? string.Empty, templateId, StringComparison.OrdinalIgnoreCase) &&
                AnyTargetFamilyMatches(
                    row.PreferredRegionId,
                    rowTargets,
                    BuildAutoAcceptDifficultyTargetNames(
                        candidate,
                        DynamicQuestRuntimeService.Instance.GetTargetNameForTemplate(candidate.TemplateId))) &&
                string.Equals(DummyEvaluationBlockReason(candidate), "dummy_evaluation_difficulty_failed", StringComparison.OrdinalIgnoreCase));
        }

        private DynamicQuestRuntimeRemovalResult RemoveRelatedAutoAcceptDifficultyRuntimeOffers(
            DbDynamicQuestTemplate row,
            string reason,
            string runtimeTargetName = "")
        {
            DynamicQuestRuntimeRemovalResult total = new()
            {
                TemplateId = row?.TemplateId ?? string.Empty,
                Reason = reason ?? string.Empty
            };
            if (row == null ||
                ParseStoryCacheStartMode(row.StartMode) != DynamicQuestStartMode.AutoAccept ||
                string.IsNullOrWhiteSpace(row.TargetNameHint))
            {
                return total;
            }

            string templateId = row.TemplateId ?? string.Empty;
            IList<string> rowTargets = BuildAutoAcceptDifficultyTargetNames(row, runtimeTargetName);
            foreach (DbDynamicQuestTemplate related in GetActiveStoryCacheRows()
                         .Where(candidate =>
                             !string.Equals(candidate.TemplateId ?? string.Empty, templateId, StringComparison.OrdinalIgnoreCase) &&
                             IsSameAutoAcceptTargetFamily(row, candidate, rowTargets)))
            {
                DynamicQuestRuntimeRemovalResult removed = DynamicQuestRuntimeService.Instance.RemoveQuestsForTemplate(
                    related.TemplateId,
                    $"{reason}:related_target_family:{(string.IsNullOrWhiteSpace(runtimeTargetName) ? row.TargetNameHint : runtimeTargetName)}");
                total = MergeRuntimeRemovalResults(total, removed, row.TemplateId, reason);
            }

            return total;
        }

        private static bool IsSameAutoAcceptTargetFamily(
            DbDynamicQuestTemplate row,
            DbDynamicQuestTemplate candidate,
            IList<string> rowTargets = null)
        {
            if (row == null ||
                candidate == null ||
                ParseStoryCacheStartMode(candidate.StartMode) != DynamicQuestStartMode.AutoAccept)
            {
                return false;
            }

            rowTargets ??= BuildAutoAcceptDifficultyTargetNames(row);
            return AnyTargetFamilyMatches(
                row.PreferredRegionId,
                rowTargets,
                BuildAutoAcceptDifficultyTargetNames(
                    candidate,
                    DynamicQuestRuntimeService.Instance.GetTargetNameForTemplate(candidate.TemplateId)));
        }

        private static bool AnyTargetFamilyMatches(ushort regionId, IEnumerable<string> leftTargets, IEnumerable<string> rightTargets)
        {
            List<(string Exact, string Family)> left = BuildTargetFamilyFingerprints(regionId, leftTargets);
            List<(string Exact, string Family)> right = BuildTargetFamilyFingerprints(regionId, rightTargets);
            return left.Any(leftTarget => right.Any(rightTarget =>
                string.Equals(leftTarget.Exact, rightTarget.Exact, StringComparison.OrdinalIgnoreCase) ||
                (!string.IsNullOrWhiteSpace(leftTarget.Family) &&
                 string.Equals(leftTarget.Family, rightTarget.Family, StringComparison.OrdinalIgnoreCase))));
        }

        private static List<(string Exact, string Family)> BuildTargetFamilyFingerprints(ushort regionId, IEnumerable<string> targets)
        {
            return (targets ?? Array.Empty<string>())
                .Select(target => (target ?? string.Empty).Trim())
                .Where(target => !string.IsNullOrWhiteSpace(target))
                .Select(target => (
                    Exact: TargetFingerprint(regionId, target),
                    Family: TargetFamilyFingerprint(regionId, target)))
                .Where(item => !string.IsNullOrWhiteSpace(item.Exact))
                .Distinct()
                .ToList();
        }

        private static IList<string> BuildAutoAcceptDifficultyTargetNames(DbDynamicQuestTemplate row, string runtimeTargetName = "")
        {
            List<string> targets = new();
            AddUniqueTargetName(targets, row?.TargetNameHint);
            AddUniqueTargetName(targets, runtimeTargetName);
            AddUniqueTargetName(targets, DummyEvaluationTargetName(row));
            return targets;
        }

        private static IList<string> BuildAutoAcceptDifficultyTargetNames(DynamicQuestSeedDefinition definition)
        {
            List<string> targets = new();
            AddUniqueTargetName(targets, definition?.TargetName);
            return targets;
        }

        private static void AddUniqueTargetName(IList<string> targets, string targetName)
        {
            targetName = (targetName ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(targetName) ||
                targets.Any(existing => string.Equals(existing, targetName, StringComparison.OrdinalIgnoreCase)))
            {
                return;
            }

            targets.Add(targetName);
        }

        private static string DummyEvaluationTargetName(DbDynamicQuestTemplate row)
        {
            if (row == null || string.IsNullOrWhiteSpace(row.DummyEvaluationJson))
                return string.Empty;

            try
            {
                using JsonDocument document = JsonDocument.Parse(row.DummyEvaluationJson);
                JsonElement root = document.RootElement;
                return GetJsonString(root, "targetName", "TargetName");
            }
            catch
            {
                return string.Empty;
            }
        }

        private static DynamicQuestRuntimeRemovalResult MergeRuntimeRemovalResults(
            DynamicQuestRuntimeRemovalResult first,
            DynamicQuestRuntimeRemovalResult second,
            string templateId,
            string reason)
        {
            if (first == null)
                return second;
            if (second == null)
                return first;

            return new DynamicQuestRuntimeRemovalResult
            {
                GeneratedAt = DateTime.UtcNow,
                TemplateId = templateId ?? first.TemplateId ?? second.TemplateId ?? string.Empty,
                Reason = reason ?? first.Reason ?? second.Reason ?? string.Empty,
                RemovedQuests = Math.Max(0, first.RemovedQuests) + Math.Max(0, second.RemovedQuests),
                CancelledProgress = Math.Max(0, first.CancelledProgress) + Math.Max(0, second.CancelledProgress),
                RemovedQuestIds = (first.RemovedQuestIds ?? Array.Empty<string>())
                    .Concat(second.RemovedQuestIds ?? Array.Empty<string>())
                    .Where(id => !string.IsNullOrWhiteSpace(id))
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .ToList()
            };
        }

        private static void AddPrefillGenerationErrors(DynamicQuestSeedSummary summary, string error)
        {
            if (summary == null || string.IsNullOrWhiteSpace(error))
                return;

            summary.StoryCachePrefillGenerationErrors ??= new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
            foreach (string part in error.Split(new[] { '|' }, StringSplitOptions.RemoveEmptyEntries))
            {
                string key = NormalizePrefillGenerationError(part);
                if (string.IsNullOrWhiteSpace(key))
                    continue;

                summary.StoryCachePrefillGenerationErrors[key] =
                    summary.StoryCachePrefillGenerationErrors.TryGetValue(key, out int count) ? count + 1 : 1;
            }
        }

        private static string NormalizePrefillGenerationError(string error)
        {
            string text = (error ?? string.Empty).Trim();
            if (text.Length == 0)
                return string.Empty;

            string[] parts = text.Split(':', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            if (parts.Length >= 2)
                return $"{parts[0]}:{parts[1]}";

            return text.Length <= 80 ? text : text.Substring(0, 80);
        }

        private int OfferCachedStoryTemplates(
            IList<DynamicQuestSeedNpc> npcs,
            string worldRevision,
            int maxOffers,
            DynamicQuestSeedSummary summary)
        {
            if (maxOffers <= 0)
                return 0;

            UpgradeLegacyStoryCacheRows();
            DynamicQuestRuntimeRemovalResult removedIneligibleOffers =
                RemoveIneligibleStoryCacheRuntimeOffers(worldRevision);
            if (removedIneligibleOffers.RemovedQuests > 0)
            {
                summary.RemovedStaleOffers += removedIneligibleOffers.RemovedQuests;
                summary.CancelledStaleProgress += removedIneligibleOffers.CancelledProgress;
                summary.Messages.Add($"story cache removed ineligible offers: {removedIneligibleOffers.RemovedQuests}");
            }

            int offered = 0;
            List<DynamicQuestDefinition> currentQuests = DynamicQuestRuntimeService.Instance.GetQuests()
                .Where(quest => quest != null &&
                                string.Equals(NormalizeWorldRevision(quest.WorldRevision), NormalizeWorldRevision(worldRevision), StringComparison.OrdinalIgnoreCase))
                .ToList();
            HashSet<string> npcOfferCoveredRealms = currentQuests
                .Where(quest => quest.StartMode == DynamicQuestStartMode.NpcOffer)
                .Select(quest => RealmNameForRegion(quest.StartRegionId))
                .Where(IsStarterRealm)
                .ToHashSet(StringComparer.OrdinalIgnoreCase);
            HashSet<string> autoAcceptCoveredRealms = currentQuests
                .Where(quest => quest.StartMode == DynamicQuestStartMode.AutoAccept)
                .Select(quest => RealmNameForRegion(quest.StartRegionId))
                .Where(IsStarterRealm)
                .ToHashSet(StringComparer.OrdinalIgnoreCase);

            foreach (DbDynamicQuestTemplate row in SelectStoryCacheOfferRows(npcOfferCoveredRealms, autoAcceptCoveredRealms, maxOffers))
            {
                if (offered >= maxOffers)
                    break;

                if (row == null || HasExistingQuestForTemplate(row.TemplateId, worldRevision))
                    continue;

                DynamicQuestTemplate template = DynamicQuestTemplateService.FromRowForCache(row);
                if (template == null || string.IsNullOrWhiteSpace(template.TemplateId))
                    continue;

                template.WorldRevision = worldRevision;
                IList<DynamicQuestSeedNpc> scopedNpcs = ScopeStoryCacheBindingNpcs(npcs, row);
                Stopwatch bindingStopwatch = Stopwatch.StartNew();
                DynamicQuestTemplateBindingResult binding = new DynamicQuestTemplateService()
                    .BindTemplate(template, scopedNpcs);
                if (Log.IsInfoEnabled)
                {
                    Log.Info(
                        $"Dynamic quest story cache offer bind template={template.TemplateId} region={row.PreferredRegionId} npcs={scopedNpcs.Count} success={binding.Success} elapsed={bindingStopwatch.ElapsedMilliseconds}ms message={binding.Message}");
                }

                if (!binding.Success)
                {
                    summary.Skipped++;
                    IncrementRealm(summary.SkippedByRealm, RealmNameForRegion(template.PreferredRegionId));
                    summary.Messages.Add($"story cache skipped: {template.TemplateId}: {binding.Message}");
                    continue;
                }

                DynamicQuestResult result = DynamicQuestRuntimeService.Instance.AddQuest(binding.Quest);
                if (result.Success)
                {
                    offered++;
                    summary.Created++;
                    IncrementRealm(summary.CreatedByRealm, RealmNameForRegion(binding.Quest.StartRegionId));
                    summary.Messages.Add(result.Message);
                    TouchStoryTemplate(template.TemplateId, binding.BindingKey);
                }
                else
                {
                    summary.Failed++;
                    IncrementRealm(summary.FailedByRealm, RealmNameForRegion(binding.Quest.StartRegionId));
                    summary.Messages.Add(result.Message);
                }
            }

            return offered;
        }

        private DynamicQuestRuntimeRemovalResult RemoveIneligibleStoryCacheRuntimeOffers(string worldRevision)
        {
            DynamicQuestRuntimeRemovalResult total = new()
            {
                Reason = "story_cache_offer_ineligible"
            };
            string normalizedWorldRevision = NormalizeWorldRevision(worldRevision);

            foreach (DbDynamicQuestTemplate row in GetActiveStoryCacheRows())
            {
                if (row == null ||
                    string.IsNullOrWhiteSpace(row.TemplateId) ||
                    IsStoryCacheOfferEligibleForRepository(row) ||
                    FindRuntimeQuestForTemplate(row.TemplateId, normalizedWorldRevision) == null)
                {
                    continue;
                }

                IList<string> reasons = BuildStoryCacheOfferBlockReasons(row);
                string reason = reasons.Count > 0
                    ? $"story_cache_offer_ineligible:{string.Join(",", reasons)}"
                    : "story_cache_offer_ineligible";
                DynamicQuestRuntimeRemovalResult removed =
                    DynamicQuestRuntimeService.Instance.RemoveQuestsForTemplate(row.TemplateId, reason);
                total = MergeRuntimeRemovalResults(total, removed, row.TemplateId, "story_cache_offer_ineligible");
            }

            return total;
        }

        private static IList<DynamicQuestSeedNpc> ScopeStoryCacheBindingNpcs(
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DbDynamicQuestTemplate row)
        {
            IEnumerable<DynamicQuestSeedNpc> source = npcs ?? Array.Empty<DynamicQuestSeedNpc>();
            ushort preferredRegionId = row?.PreferredRegionId ?? 0;
            List<DynamicQuestSeedNpc> scoped = preferredRegionId > 0
                ? source.Where(npc => npc != null && npc.RegionId == preferredRegionId).ToList()
                : source.Where(npc => npc != null).ToList();

            if (row != null &&
                ParseStoryCacheStartMode(row.StartMode) == DynamicQuestStartMode.AutoAccept &&
                !string.IsNullOrWhiteSpace(row.TargetNameHint))
            {
                List<DynamicQuestSeedNpc> exactTargets = scoped
                    .Where(npc => string.Equals(npc.Name, row.TargetNameHint, StringComparison.OrdinalIgnoreCase))
                    .ToList();
                if (exactTargets.Count > 0)
                {
                    long radiusSquared = (long)StoryCacheAutoAcceptScopeRadius * StoryCacheAutoAcceptScopeRadius;
                    scoped = scoped
                        .Where(npc => exactTargets.Any(target => DistanceSquared(target, npc) <= radiusSquared))
                        .ToList();
                }
            }

            return scoped;
        }

        private int UpgradeLegacyStoryCacheRows()
        {
            int upgraded = 0;
            foreach (DbDynamicQuestTemplate row in GetActiveStoryCacheRows()
                         .Where(NeedsStoryCacheMetadataRepair)
                         .OrderByDescending(row => Math.Clamp(row.StoryQualityScore, 0, 100))
                         .ThenBy(row => EffectiveLastUsed(row))
                         .ToList())
            {
                if (TryRepairLegacyStoryCacheMetadata(row))
                    upgraded++;
            }

            foreach (DbDynamicQuestTemplate row in GetActiveStoryCacheRows()
                         .Where(NeedsStoryCacheScaffoldUpgrade)
                         .OrderByDescending(row => Math.Clamp(row.StoryQualityScore, 0, 100))
                         .ThenBy(row => EffectiveLastUsed(row))
                         .ToList())
            {
                if (TryUpgradeLegacyStoryCacheRow(row))
                    upgraded++;
            }

            return upgraded;
        }

        private bool TryUpgradeLegacyStoryCacheRow(DbDynamicQuestTemplate row)
        {
            if (!NeedsStoryCacheScaffoldUpgrade(row))
                return false;

            DynamicQuestTemplate template = DynamicQuestTemplateService.FromRowForCache(row);
            if (template == null || string.IsNullOrWhiteSpace(template.TemplateId))
                return false;

            DynamicQuestTemplate upgraded;
            if (IsCodexCuratedStoryCacheRow(row))
            {
                upgraded = ApplyCodexCuratedStory(template);
            }
            else
            {
                DynamicQuestStoryText scaffold = BuildDeterministicFallbackStory(template);
                upgraded = DynamicQuestStoryService.ApplyStory(
                    template,
                    scaffold,
                    string.IsNullOrWhiteSpace(template.StoryProvider) ? "deterministic-fallback" : template.StoryProvider,
                    string.IsNullOrWhiteSpace(template.StoryModel) ? "legacy-scaffold-v1" : template.StoryModel);
            }
            upgraded = EnsureBranchNarrativeScenes(upgraded);
            upgraded = EnsureChoiceSelectedSetPiece(upgraded);
            upgraded = EnsureWorldSignalSetPiece(upgraded);

            List<string> tags = new(upgraded.Tags ?? Array.Empty<string>());
            AddStoryCinematicTags(tags, largeSetPieces: IsCodexCuratedStoryCacheRow(row));
            tags.RemoveAll(IsStoryArchetypeTag);
            string storyArchetypeTag = CodexStoryArchetypeTagForRow(row, tags);
            if (!string.IsNullOrWhiteSpace(storyArchetypeTag))
                tags.Add(storyArchetypeTag);
            AddTagIfMissing(tags, StoryFamilyTagForTemplate(upgraded));
            AddSignatureStoryArcTags(tags, upgraded, StoryArchetypeFromTag(storyArchetypeTag));
            if (!tags.Contains("story-scaffold-upgraded", StringComparer.OrdinalIgnoreCase))
                tags.Add("story-scaffold-upgraded");
            if (!tags.Contains("story-title-variant:v3", StringComparer.OrdinalIgnoreCase))
                tags.Add("story-title-variant:v3");
            upgraded.Tags = tags;
            upgraded.StoryLastUsedAt = row.StoryLastUsedAt;
            upgraded.CreatedAt = row.CreatedAt;

            DbDynamicQuestTemplate upgradedRow = DynamicQuestTemplateService.ToRowForCache(upgraded, row.LastBindingKey);
            CopyTemplateRow(upgradedRow, row);
            row.IsActive = true;
            row.UpdatedAt = UtcNow();
            m_templateRepository.Save(row);
            return IsStoryCacheReadyForUse(row);
        }

        private bool TryRepairLegacyStoryCacheMetadata(DbDynamicQuestTemplate row)
        {
            if (!NeedsStoryCacheMetadataRepair(row))
                return false;

            IList<string> tags = DeserializeStoryCacheTags(row.TagsJson);
            string worldSignal = ExtractBranchWorldSignal(tags);
            string expectedBranchTag = BranchTagForWorldSignal(worldSignal);
            List<string> normalizedTags = tags
                .Where(tag => !string.IsNullOrWhiteSpace(tag))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();
            bool changed = false;
            bool replacedDisabledMobGrowthBranch = false;

            if (IsMobGrowthSignal(worldSignal) && !Properties.WORLDAI_MOB_GROWTH_ENABLED)
            {
                normalizedTags.RemoveAll(IsWorldSignalTag);
                normalizedTags.RemoveAll(IsKnownBranchTag);
                normalizedTags.Add("branch:time-window");
                normalizedTags.Add("world-signal:time-window");
                worldSignal = "time-window";
                expectedBranchTag = "branch:time-window";
                replacedDisabledMobGrowthBranch = true;
                changed = true;

                if (ParseStoryCacheStartMode(row.StartMode) == DynamicQuestStartMode.AutoAccept &&
                    !string.Equals(row.Trigger, "time-window", StringComparison.OrdinalIgnoreCase))
                {
                    row.Trigger = "time-window";
                }
                else if (ParseStoryCacheStartMode(row.StartMode) != DynamicQuestStartMode.AutoAccept &&
                         IsMobGrowthSignal(row.Trigger))
                {
                    row.Trigger = string.Empty;
                }
            }

            if (IsCodexCuratedStoryCacheRow(row))
            {
                if (!IsStarterLevelRange(row))
                    normalizedTags.RemoveAll(tag => string.Equals(tag, "starter", StringComparison.OrdinalIgnoreCase));
                normalizedTags.RemoveAll(tag => (tag ?? string.Empty).StartsWith("llm-provider:", StringComparison.OrdinalIgnoreCase));
                normalizedTags.RemoveAll(tag => (tag ?? string.Empty).StartsWith("llm-model:", StringComparison.OrdinalIgnoreCase));
                normalizedTags.RemoveAll(tag => (tag ?? string.Empty).StartsWith("story-title-variant:", StringComparison.OrdinalIgnoreCase));
                normalizedTags.Add($"llm-provider:{CodexCuratedStoryProvider}");
                normalizedTags.Add($"llm-model:{CodexCuratedStoryModel}");
                normalizedTags.Add("story-title-variant:v3");
                AddStoryCinematicTags(normalizedTags);
            }

            if (IsKnownBranchTag(expectedBranchTag))
            {
                normalizedTags = normalizedTags
                    .Where(tag => !IsKnownBranchTag(tag) ||
                                  string.Equals(tag, expectedBranchTag, StringComparison.OrdinalIgnoreCase))
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .ToList();
                if (!normalizedTags.Contains(expectedBranchTag, StringComparer.OrdinalIgnoreCase))
                    normalizedTags.Add(expectedBranchTag);
            }

            string expectedArchetypeTag = CodexStoryArchetypeTagForRow(row, normalizedTags);
            if (!string.IsNullOrWhiteSpace(expectedArchetypeTag))
            {
                normalizedTags.RemoveAll(IsStoryArchetypeTag);
                normalizedTags.Add(expectedArchetypeTag);
            }

            string expectedStoryFamilyTag = StoryFamilyTagForRow(row);
            if (!string.IsNullOrWhiteSpace(expectedStoryFamilyTag) &&
                !normalizedTags.Contains(expectedStoryFamilyTag, StringComparer.OrdinalIgnoreCase))
            {
                normalizedTags.Add(expectedStoryFamilyTag);
                changed = true;
            }

            AddSignatureStoryArcTags(
                normalizedTags,
                DynamicQuestTemplateService.FromRowForCache(row),
                StoryArchetypeFromTag(expectedArchetypeTag));

            if (ShouldNormalizeAutoAcceptTimeWindowStoryCache(row, worldSignal))
            {
                normalizedTags.RemoveAll(IsWorldSignalTag);
                normalizedTags.Add("world-signal:time-window");
                if (!string.Equals(row.Trigger, "time-window", StringComparison.OrdinalIgnoreCase))
                {
                    row.Trigger = "time-window";
                    changed = true;
                }
            }

            if (!tags.SequenceEqual(normalizedTags, StringComparer.OrdinalIgnoreCase))
            {
                row.TagsJson = JsonSerializer.Serialize(normalizedTags);
                changed = true;
            }

            if (ParseStoryCacheStartMode(row.StartMode) == DynamicQuestStartMode.AutoAccept &&
                IsItemAcquiredSignal(worldSignal) &&
                (IsItemAcquiredSignal(row.Trigger) || IsTimeWindowSignal(row.Trigger)))
            {
                row.Trigger = string.Empty;
                changed = true;
            }

            if (replacedDisabledMobGrowthBranch)
            {
                RebuildDisabledMobGrowthStoryCacheRow(row, normalizedTags);
                ResetStoryCacheDummyEvaluation(row);
                changed = true;
            }

            if (!changed)
                return false;

            row.UpdatedAt = UtcNow();
            m_templateRepository.Save(row);
            return !HasBlockingStoryCacheWarnings(row);
        }

        private static void RebuildDisabledMobGrowthStoryCacheRow(DbDynamicQuestTemplate row, IList<string> normalizedTags)
        {
            DynamicQuestTemplate template = DynamicQuestTemplateService.FromRowForCache(row);
            if (template == null)
            {
                row.TagsJson = JsonSerializer.Serialize(normalizedTags);
                return;
            }

            template.Tags = normalizedTags ?? Array.Empty<string>();
            template.Trigger = row.Trigger ?? string.Empty;
            DynamicQuestTemplate repaired = ApplyCodexCuratedStory(template);
            repaired = EnsureBranchNarrativeScenes(repaired);
            repaired = EnsureChoiceSelectedSetPiece(repaired);
            repaired = EnsureWorldSignalSetPiece(repaired);
            repaired.StoryLastUsedAt = row.StoryLastUsedAt;
            repaired.CreatedAt = row.CreatedAt;

            DbDynamicQuestTemplate repairedRow = DynamicQuestTemplateService.ToRowForCache(repaired, string.Empty);
            CopyTemplateRow(repairedRow, row);
        }

        private static void ResetStoryCacheDummyEvaluation(DbDynamicQuestTemplate row)
        {
            if (row == null)
                return;

            row.DummyEvaluationScore = 0;
            row.DummyEvaluationCount = 0;
            row.DummyEvaluationJson = string.Empty;
            row.DummyEvaluatedAt = DateTime.MinValue;
        }

        private static bool NeedsStoryCacheMetadataRepair(DbDynamicQuestTemplate row)
        {
            return IsActiveStoryCacheRow(row) &&
                   (BuildStoryCacheWarnings(row, DeserializeStoryCacheTags(row?.TagsJson)).Any(IsBlockingStoryCacheWarning) ||
                    NeedsCodexCuratedStoryArchetypeRepair(row) ||
                    NeedsStoryFamilyRepair(row) ||
                    NeedsCodexCuratedStoryTagRepair(row) ||
                    NeedsAutoAcceptTimeWindowStoryCacheRepair(row));
        }

        private static bool NeedsStoryFamilyRepair(DbDynamicQuestTemplate row)
        {
            if (!IsActiveStoryCacheRow(row))
                return false;

            IList<string> tags = DeserializeStoryCacheTags(row.TagsJson);
            return !tags.Any(IsStoryFamilyTag);
        }

        private static bool NeedsCodexCuratedStoryTagRepair(DbDynamicQuestTemplate row)
        {
            if (!IsCodexCuratedStoryCacheRow(row))
                return false;

            IList<string> tags = DeserializeStoryCacheTags(row.TagsJson);
            int currentProviderTags = tags.Count(tag => string.Equals(tag, $"llm-provider:{CodexCuratedStoryProvider}", StringComparison.OrdinalIgnoreCase));
            int currentModelTags = tags.Count(tag => string.Equals(tag, $"llm-model:{CodexCuratedStoryModel}", StringComparison.OrdinalIgnoreCase));
            int currentTitleVariantTags = tags.Count(tag => string.Equals(tag, "story-title-variant:v3", StringComparison.OrdinalIgnoreCase));
            int archetypeTags = tags.Count(IsStoryArchetypeTag);

            return currentProviderTags != 1 ||
                   currentModelTags != 1 ||
                   currentTitleVariantTags != 1 ||
                   archetypeTags != 1 ||
                   !tags.Contains("story-arc:motive", StringComparer.OrdinalIgnoreCase) ||
                   !tags.Contains("story-arc:conflict", StringComparer.OrdinalIgnoreCase) ||
                   !tags.Contains("story-arc:reversal", StringComparer.OrdinalIgnoreCase) ||
                   !tags.Contains("story-arc:consequence", StringComparer.OrdinalIgnoreCase) ||
                   (!IsStarterLevelRange(row) &&
                    tags.Any(tag => string.Equals(tag, "starter", StringComparison.OrdinalIgnoreCase))) ||
                   tags.Any(tag => (tag ?? string.Empty).StartsWith("llm-provider:", StringComparison.OrdinalIgnoreCase) &&
                                   !string.Equals(tag, $"llm-provider:{CodexCuratedStoryProvider}", StringComparison.OrdinalIgnoreCase)) ||
                   tags.Any(tag => (tag ?? string.Empty).StartsWith("llm-model:", StringComparison.OrdinalIgnoreCase) &&
                                   !string.Equals(tag, $"llm-model:{CodexCuratedStoryModel}", StringComparison.OrdinalIgnoreCase)) ||
                   tags.Any(tag => (tag ?? string.Empty).StartsWith("story-title-variant:", StringComparison.OrdinalIgnoreCase) &&
                                   !string.Equals(tag, "story-title-variant:v3", StringComparison.OrdinalIgnoreCase));
        }

        private static bool NeedsCodexCuratedStoryArchetypeRepair(DbDynamicQuestTemplate row)
        {
            if (!IsCodexCuratedStoryCacheRow(row))
                return false;

            IList<string> tags = DeserializeStoryCacheTags(row.TagsJson);
            return !tags.Any(IsStoryArchetypeTag);
        }

        private static bool IsCodexCuratedStoryCacheRow(DbDynamicQuestTemplate row)
        {
            return IsActiveStoryCacheRow(row) &&
                   (string.Equals(row.StoryProvider, CodexCuratedStoryProvider, StringComparison.OrdinalIgnoreCase) ||
                    string.Equals(row.StoryModel, CodexCuratedStoryModel, StringComparison.OrdinalIgnoreCase));
        }

        private static bool IsStoryArchetypeTag(string tag)
        {
            return (tag ?? string.Empty).StartsWith("story-archetype:", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsStoryFamilyTag(string tag)
        {
            return (tag ?? string.Empty).StartsWith("story-family:", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsStoryChainTag(string tag)
        {
            return (tag ?? string.Empty).StartsWith("story-chain:", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsStoryEpisodeTag(string tag)
        {
            string value = tag ?? string.Empty;
            return value.StartsWith("story-episode:", StringComparison.OrdinalIgnoreCase) ||
                   value.StartsWith("arc-step:", StringComparison.OrdinalIgnoreCase);
        }

        private static void AddSignatureStoryArcTags(
            ICollection<string> tags,
            DynamicQuestTemplate template,
            string archetype)
        {
            if (tags == null || template == null)
                return;

            if (!tags.Any(IsStoryFamilyTag))
                AddTagIfMissing(tags, StoryFamilyTagForTemplate(template));
            if (!tags.Any(IsStoryChainTag))
                AddTagIfMissing(tags, StoryChainTagForTemplate(template, archetype));
            if (!tags.Any(tag => (tag ?? string.Empty).StartsWith("story-episode:", StringComparison.OrdinalIgnoreCase)))
                AddTagIfMissing(tags, "story-episode:1/3");
            if (!tags.Any(tag => (tag ?? string.Empty).StartsWith("arc-step:", StringComparison.OrdinalIgnoreCase)))
                AddTagIfMissing(tags, "arc-step:1/3");
        }

        private static string StoryArchetypeFromTag(string tag)
        {
            string value = (tag ?? string.Empty).Trim();
            return value.StartsWith("story-archetype:", StringComparison.OrdinalIgnoreCase)
                ? value.Substring("story-archetype:".Length).Trim()
                : string.Empty;
        }

        private static string StoryFamilyTagForTemplate(DynamicQuestTemplate template)
        {
            string templateId = (template?.TemplateId ?? string.Empty).Trim();
            return string.IsNullOrWhiteSpace(templateId)
                ? string.Empty
                : $"story-family:{templateId}";
        }

        private static string StoryChainTagForTemplate(DynamicQuestTemplate template, string archetype)
        {
            if (template == null)
                return string.Empty;

            string realm = !string.IsNullOrWhiteSpace(template.Realm)
                ? template.Realm
                : RealmNameForRegion(template.PreferredRegionId);
            string chain = NormalizeStoryTagToken($"{realm}-{archetype}-{template.StartMode}");
            return string.IsNullOrWhiteSpace(chain)
                ? string.Empty
                : $"story-chain:{chain}";
        }

        private static string NormalizeStoryTagToken(string value)
        {
            value = (value ?? string.Empty).Trim().ToLowerInvariant();
            if (string.IsNullOrWhiteSpace(value))
                return string.Empty;

            StringBuilder builder = new(value.Length);
            bool previousDash = false;
            foreach (char ch in value)
            {
                bool allowed = (ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9');
                if (allowed)
                {
                    builder.Append(ch);
                    previousDash = false;
                    continue;
                }

                if (!previousDash)
                {
                    builder.Append('-');
                    previousDash = true;
                }
            }

            return builder.ToString().Trim('-');
        }

        private static string StoryFamilyTagForRow(DbDynamicQuestTemplate row)
        {
            string templateId = (row?.TemplateId ?? string.Empty).Trim();
            return string.IsNullOrWhiteSpace(templateId)
                ? string.Empty
                : $"story-family:{templateId}";
        }

        private static bool IsStarterLevelRange(DynamicQuestTemplate template)
        {
            return template != null && template.MinLevel <= 1 && template.MaxLevel <= 5;
        }

        private static bool IsStarterLevelRange(DbDynamicQuestTemplate row)
        {
            return row != null && row.MinLevel <= 1 && row.MaxLevel <= 5;
        }

        private static bool IsWorldSignalTag(string tag)
        {
            return (tag ?? string.Empty).StartsWith("world-signal:", StringComparison.OrdinalIgnoreCase);
        }

        private static bool NeedsAutoAcceptTimeWindowStoryCacheRepair(DbDynamicQuestTemplate row)
        {
            if (!IsActiveStoryCacheRow(row) ||
                ParseStoryCacheStartMode(row.StartMode) != DynamicQuestStartMode.AutoAccept)
                return false;

            IList<string> tags = DeserializeStoryCacheTags(row.TagsJson);
            return ShouldNormalizeAutoAcceptTimeWindowStoryCache(row, ExtractBranchWorldSignal(tags));
        }

        private static bool ShouldNormalizeAutoAcceptTimeWindowStoryCache(DbDynamicQuestTemplate row, string worldSignal)
        {
            if (row == null ||
                ParseStoryCacheStartMode(row.StartMode) != DynamicQuestStartMode.AutoAccept ||
                !IsTimeWindowSignal(worldSignal))
                return false;

            string signal = (worldSignal ?? string.Empty).Trim();
            string trigger = (row.Trigger ?? string.Empty).Trim();
            return !string.Equals(signal, "time-window", StringComparison.OrdinalIgnoreCase) ||
                   !string.Equals(trigger, "time-window", StringComparison.OrdinalIgnoreCase);
        }

        private static string CodexStoryArchetypeTagForRow(DbDynamicQuestTemplate row, IEnumerable<string> tags)
        {
            if (!IsCodexCuratedStoryCacheRow(row))
                return string.Empty;

            string worldSignalArchetype = CodexStoryArchetypeForWorldSignal(ExtractBranchWorldSignal((tags ?? Array.Empty<string>()).ToList()));
            if (!string.IsNullOrWhiteSpace(worldSignalArchetype))
                return $"story-archetype:{worldSignalArchetype}";

            DynamicQuestTemplate template = DynamicQuestTemplateService.FromRowForCache(row);
            string archetype = template == null
                ? string.Empty
                : CodexStoryArchetype(template);

            return string.IsNullOrWhiteSpace(archetype)
                ? string.Empty
                : $"story-archetype:{archetype}";
        }

        private static bool NeedsStoryCacheScaffoldUpgrade(DbDynamicQuestTemplate row)
        {
            if (!IsActiveStoryCacheRow(row) ||
                string.IsNullOrWhiteSpace(row.TemplateId) ||
                string.IsNullOrWhiteSpace(row.TargetNameHint))
                return false;

            if (ParseStoryCacheNarrativeScenes(row.StoryNarrativeJson, includeText: false).Count == 0 ||
                ParseStoryCachePresentationBeats(row.StoryPresentationJson, includeText: false).Count == 0)
                return true;

            if (RequiresChoiceSelectedSetPiece(row) &&
                !HasChoiceSelectedSetPiece(ParseStoryCachePresentationBeats(row.StoryPresentationJson, includeText: false)))
            {
                return true;
            }
            if (RequiresWorldSignalSetPiece(row) &&
                !HasWorldSignalSetPiece(ParseStoryCachePresentationBeats(row.StoryPresentationJson, includeText: false)))
            {
                return true;
            }
            if (RequiresChoiceSelectedSetPiece(row) &&
                !HasNarrativeScene(ParseStoryCacheNarrativeScenes(row.StoryNarrativeJson, includeText: false), "choice"))
            {
                return true;
            }
            if (RequiresWorldSignalSetPiece(row) &&
                !HasNarrativeScene(ParseStoryCacheNarrativeScenes(row.StoryNarrativeJson, includeText: false), "observe_signal"))
            {
                return true;
            }

            if (!IsCodexCuratedStoryCacheRow(row))
                return false;

            if (!string.Equals(row.StoryModel, CodexCuratedStoryModel, StringComparison.OrdinalIgnoreCase))
                return true;

            DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForCache(
                BuildStoryQualityRequest(row),
                BuildStoryQualityText(row));
            IList<string> tags = DeserializeStoryCacheTags(row.TagsJson);
            return HasFallbackScaffoldTitle(row.Title) ||
                   (quality?.Reasons ?? Array.Empty<string>()).Contains("generic_repetition", StringComparer.OrdinalIgnoreCase) ||
                   (quality?.Reasons ?? Array.Empty<string>()).Contains("awkward_korean_particle", StringComparer.OrdinalIgnoreCase) ||
                   (quality?.Reasons ?? Array.Empty<string>()).Contains("repetitive_sentence_opening", StringComparer.OrdinalIgnoreCase) ||
                   !tags.Contains("story-title-variant:v3", StringComparer.OrdinalIgnoreCase);
        }

        private IEnumerable<DbDynamicQuestTemplate> SelectStoryCacheOfferRows(
            ISet<string> npcOfferCoveredRealms = null,
            ISet<string> autoAcceptCoveredRealms = null,
            int maxOffers = 0)
        {
            List<DbDynamicQuestTemplate> rows = GetActiveStoryCacheRows()
                .Where(row => !string.IsNullOrWhiteSpace(row.TemplateId))
                .Where(IsStoryCacheOfferEligibleForRepository)
                .OrderBy(row => StoryCacheOfferLevelBucket(row))
                .ThenByDescending(StoryCacheDummyEvaluationPriorityScore)
                .ThenByDescending(StoryCacheCurrentQualityScore)
                .ThenBy(row => EffectiveLastUsed(row))
                .ThenBy(row => row.TemplateId, StringComparer.OrdinalIgnoreCase)
                .ToList();

            HashSet<string> yielded = new(StringComparer.OrdinalIgnoreCase);
            if (maxOffers > 0)
            {
                HashSet<string> npcCoveredRealms = new(
                    npcOfferCoveredRealms ?? Enumerable.Empty<string>(),
                    StringComparer.OrdinalIgnoreCase);
                List<DbDynamicQuestTemplate> missingRealmNpcOfferRows = RoundRobinRowsByRealm(rows
                        .Where(row => ParseStoryCacheStartMode(row.StartMode) == DynamicQuestStartMode.NpcOffer)
                        .Where(row => IsStarterRealm(RealmNameForRegion(row.PreferredRegionId)))
                        .Where(row => !npcCoveredRealms.Contains(RealmNameForRegion(row.PreferredRegionId))))
                    .ToList();

                foreach (DbDynamicQuestTemplate row in missingRealmNpcOfferRows)
                {
                    string realm = RealmNameForRegion(row.PreferredRegionId);
                    if (npcCoveredRealms.Contains(realm))
                        continue;

                    yielded.Add(row.TemplateId);
                    npcCoveredRealms.Add(realm);
                    yield return row;
                }

                HashSet<string> coveredRealms = new(
                    autoAcceptCoveredRealms ?? Enumerable.Empty<string>(),
                    StringComparer.OrdinalIgnoreCase);
                List<DbDynamicQuestTemplate> missingRealmAutoAcceptRows = RoundRobinRowsByRealm(rows
                        .Where(row => ParseStoryCacheStartMode(row.StartMode) == DynamicQuestStartMode.AutoAccept)
                        .Where(row => IsStarterRealm(RealmNameForRegion(row.PreferredRegionId)))
                        .Where(row => !coveredRealms.Contains(RealmNameForRegion(row.PreferredRegionId))))
                    .ToList();

                foreach (DbDynamicQuestTemplate row in missingRealmAutoAcceptRows)
                {
                    string realm = RealmNameForRegion(row.PreferredRegionId);
                    if (coveredRealms.Contains(realm))
                        continue;

                    yielded.Add(row.TemplateId);
                    coveredRealms.Add(realm);
                    yield return row;
                }
            }

            DynamicQuestStartMode[] startModeOrder = StoryCacheOfferStartModeOrder().ToArray();
            Dictionary<DynamicQuestStartMode, Queue<DbDynamicQuestTemplate>> queues = startModeOrder
                .ToDictionary(
                    startMode => startMode,
                    startMode => new Queue<DbDynamicQuestTemplate>(RoundRobinRowsByRealm(rows
                        .Where(row => ParseStoryCacheStartMode(row.StartMode) == startMode)
                        .Where(row => !yielded.Contains(row.TemplateId)))));

            while (queues.Values.Any(queue => queue.Count > 0))
            {
                foreach (DynamicQuestStartMode startMode in startModeOrder)
                {
                    if (!queues.TryGetValue(startMode, out Queue<DbDynamicQuestTemplate> queue) || queue.Count == 0)
                        continue;

                    yield return queue.Dequeue();
                }
            }
        }

        private static IEnumerable<DynamicQuestStartMode> StoryCacheOfferStartModeOrder()
        {
            yield return DynamicQuestStartMode.NpcOffer;
            yield return DynamicQuestStartMode.AutoAccept;
            yield return DynamicQuestStartMode.WorldOffer;
        }

        private static int StoryCacheOfferLevelBucket(DbDynamicQuestTemplate row)
        {
            if (row == null)
                return 3;

            int minLevel = Math.Clamp(row.MinLevel <= 0 ? 1 : row.MinLevel, 1, 50);
            int maxLevel = Math.Clamp(row.MaxLevel <= 0 ? minLevel : row.MaxLevel, minLevel, 50);
            int count = Math.Max(1, row.Count);
            if (maxLevel <= 20 && count <= 2)
                return 0;
            if (maxLevel <= 35 && count <= 3)
                return 1;
            if (maxLevel <= 45 && count <= 3)
                return 2;
            return 3;
        }

        private static int StoryCacheDummyEvaluationPriorityScore(DbDynamicQuestTemplate row)
        {
            if (row == null || row.DummyEvaluationCount <= 0)
                return -1;

            return Math.Clamp(row.DummyEvaluationScore, 0, 100);
        }

        private bool IsStoryCacheOfferEligibleForRepository(DbDynamicQuestTemplate row)
        {
            if (!IsStoryCacheReadyForUse(row))
                return false;

            if (!HasPassingDummyEvaluation(row) &&
                HasRelatedAutoAcceptDummyDifficultyFailure(row))
                return false;

            return !Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS ||
                   HasPassingDummyEvaluation(row);
        }

        private IList<string> BuildStoryCacheOfferBlockReasons(DbDynamicQuestTemplate row)
        {
            if (row == null)
                return Array.Empty<string>();

            List<string> reasons = new();
            if (!IsStoryCacheReadyForUse(row))
            {
                reasons.AddRange(BuildStoryCacheReadyBlockReasons(row));
                if (reasons.Count == 0)
                    reasons.Add("story_cache_not_ready");
            }

            if (Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS &&
                !HasPassingDummyEvaluation(row))
            {
                reasons.Add(row.DummyEvaluationCount <= 0
                    ? "dummy_evaluation_required"
                    : HasInconclusiveDummyEvaluation(row)
                        ? "dummy_evaluation_inconclusive"
                        : "dummy_evaluation_not_passing");
            }
            if (!HasPassingDummyEvaluation(row) &&
                HasRelatedAutoAcceptDummyDifficultyFailure(row))
                reasons.Add("dummy_evaluation_target_difficulty_history");

            return reasons
                .Where(reason => !string.IsNullOrWhiteSpace(reason))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();
        }

        private static bool HasPassingDummyEvaluation(DbDynamicQuestTemplate row)
        {
            return row != null &&
                   row.DummyEvaluationCount > 0 &&
                   !HasInconclusiveDummyEvaluation(row) &&
                   string.IsNullOrWhiteSpace(DummyEvaluationBlockReason(row));
        }

        private static bool HasInconclusiveDummyEvaluation(DbDynamicQuestTemplate row)
        {
            if (row == null ||
                row.DummyEvaluationCount <= 0 ||
                string.IsNullOrWhiteSpace(row.DummyEvaluationJson))
            {
                return false;
            }

            try
            {
                using JsonDocument document = JsonDocument.Parse(row.DummyEvaluationJson);
                string failureCategory = GetJsonString(document.RootElement, "failureCategory", "FailureCategory", "failure_category");
                return IsInfrastructureOrNoFreshDummyEvaluation(failureCategory);
            }
            catch (JsonException)
            {
                return false;
            }
        }

        private static DynamicQuestStartMode ParseStoryCacheStartMode(string value)
        {
            return Enum.TryParse(value, true, out DynamicQuestStartMode parsed)
                ? parsed
                : DynamicQuestStartMode.NpcOffer;
        }

        private static IEnumerable<DbDynamicQuestTemplate> RoundRobinRowsByRealm(IEnumerable<DbDynamicQuestTemplate> rows)
        {
            Dictionary<string, Queue<DbDynamicQuestTemplate>> queues = (rows ?? Array.Empty<DbDynamicQuestTemplate>())
                .GroupBy(row => RealmNameForRegion(row.PreferredRegionId), StringComparer.OrdinalIgnoreCase)
                .ToDictionary(
                    group => group.Key,
                    group => new Queue<DbDynamicQuestTemplate>(group),
                    StringComparer.OrdinalIgnoreCase);
            string[] order = { "Albion", "Midgard", "Hibernia", "Unknown" };

            while (queues.Values.Any(queue => queue.Count > 0))
            {
                foreach (string realm in order)
                {
                    if (!queues.TryGetValue(realm, out Queue<DbDynamicQuestTemplate> queue) || queue.Count == 0)
                        continue;

                    yield return queue.Dequeue();
                }
            }
        }

        private DynamicQuestStoryCacheItem BuildStoryCacheItem(DbDynamicQuestTemplate row, bool includeText)
        {
            IList<string> tags = DeserializeStoryCacheTags(row.TagsJson);
            DynamicQuestStoryQuality currentQuality = DynamicQuestStoryService.EvaluateQualityDetailsForCache(
                BuildStoryQualityRequest(row),
                BuildStoryQualityText(row));
            IList<string> warnings = BuildStoryCacheWarnings(row, tags);
            DynamicQuestStoryCacheDummyEvaluationSummary dummySummary = ParseDummyEvaluationSummary(row.DummyEvaluationJson);
            string runtimeTargetName = DynamicQuestRuntimeService.Instance.GetTargetNameForTemplate(row.TemplateId);
            string dummyEvaluationTargetName = DummyEvaluationTargetName(row);
            return new DynamicQuestStoryCacheItem
            {
                TemplateId = row.TemplateId ?? string.Empty,
                Title = row.Title ?? string.Empty,
                StorySeed = includeText ? row.StorySeed ?? string.Empty : string.Empty,
                OfferText = includeText ? row.OfferText ?? string.Empty : string.Empty,
                ProgressText = includeText ? row.ProgressText ?? string.Empty : string.Empty,
                FinishText = includeText ? row.FinishText ?? string.Empty : string.Empty,
                Realm = row.Realm ?? string.Empty,
                PreferredStartNpcName = row.PreferredStartNpcName ?? string.Empty,
                PreferredRegionId = row.PreferredRegionId,
                TargetNameHint = row.TargetNameHint ?? string.Empty,
                RuntimeTargetName = runtimeTargetName,
                DummyEvaluationTargetName = dummyEvaluationTargetName,
                EffectiveTargetName = FirstNonEmpty(runtimeTargetName, dummyEvaluationTargetName, row.TargetNameHint),
                Count = row.Count,
                MinLevel = row.MinLevel,
                MaxLevel = row.MaxLevel,
                Source = row.Source ?? string.Empty,
                Tags = tags,
                BranchWorldSignal = ExtractBranchWorldSignal(tags),
                Warnings = warnings,
                StoryProvider = row.StoryProvider ?? string.Empty,
                StoryModel = row.StoryModel ?? string.Empty,
                StoryQualityScore = Math.Clamp(row.StoryQualityScore, 0, 100),
                DummyEvaluationScore = Math.Clamp(row.DummyEvaluationScore, 0, 100),
                DummyEvaluationCount = Math.Max(0, row.DummyEvaluationCount),
                DummyEvaluationJson = includeText ? row.DummyEvaluationJson ?? string.Empty : string.Empty,
                DummyEvaluatedAt = row.DummyEvaluatedAt,
                DummyOperationalScore = dummySummary.OperationalScore,
                DummyOperationalGrade = dummySummary.OperationalGrade,
                DummyOperationalPassed = dummySummary.OperationalPassed,
                DummyFailureCategory = dummySummary.FailureCategory,
                DummyActionSceneCohesionScore = dummySummary.ActionSceneCohesionScore,
                DummyCinematicCatalogRoleVariety = dummySummary.CinematicCatalogRoleVariety,
                DummyCinematicModelRoleFitScore = dummySummary.CinematicModelRoleFitScore,
                ReadyForUse = IsStoryCacheReadyForUse(row),
                OfferEligible = IsStoryCacheOfferEligibleForRepository(row),
                OfferBlockReasons = BuildStoryCacheOfferBlockReasons(row),
                Quality = ParseStoryCacheQuality(row.StoryQualityJson, row.StoryQualityScore),
                CurrentQuality = ToStoryCacheQuality(currentQuality),
                NarrativeScenes = ParseStoryCacheNarrativeScenes(row.StoryNarrativeJson, includeText),
                PresentationBeats = ParseStoryCachePresentationBeats(row.StoryPresentationJson, includeText),
                StoryGeneratedAt = row.StoryGeneratedAt,
                StoryLastUsedAt = row.StoryLastUsedAt,
                StartMode = row.StartMode.ToString(),
                Trigger = row.Trigger ?? string.Empty,
                LastBindingKey = row.LastBindingKey ?? string.Empty,
                CreatedAt = row.CreatedAt,
                UpdatedAt = row.UpdatedAt
            };
        }

        private static string FirstNonEmpty(params string[] values)
        {
            foreach (string value in values ?? Array.Empty<string>())
            {
                string trimmed = (value ?? string.Empty).Trim();
                if (!string.IsNullOrWhiteSpace(trimmed))
                    return trimmed;
            }

            return string.Empty;
        }

        private static string BuildDummyEvaluationJson(
            DynamicQuestDummyEvaluationRequest request,
            int score,
            int minimumScore,
            DateTime evaluatedAt)
        {
            int skyrimGradeScore = Math.Clamp(request.SkyrimGradeScore, 0, 100);
            int cinematicDensityScore = Math.Clamp(request.CinematicDensityScore, 0, 100);
            int actionSceneCohesionScore = Math.Clamp(request.ActionSceneCohesionScore, 0, 100);
            int cinematicCatalogRoleVariety = Math.Max(-1, request.CinematicCatalogRoleVariety);
            int cinematicModelRoleFitScore = request.CinematicModelRoleFitScore < 0
                ? -1
                : Math.Clamp(request.CinematicModelRoleFitScore, 0, 100);
            int storyContinuityScore = Math.Clamp(request.StoryContinuityScore, 0, 100);
            int storyArchetypeScore = Math.Clamp(request.StoryArchetypeScore, 0, 100);
            DynamicQuestDummyOperationalEvaluation operationalEvaluation =
                HasMeaningfulOperationalEvaluation(request.OperationalEvaluation)
                    ? request.OperationalEvaluation
                    : null;
            return JsonSerializer.Serialize(new
            {
                questId = request.QuestId ?? string.Empty,
                templateId = request.TemplateId ?? string.Empty,
                player = request.Player ?? string.Empty,
                account = request.Account ?? string.Empty,
                source = request.Source ?? string.Empty,
                targetName = request.TargetName ?? string.Empty,
                score,
                minimumScore,
                passed = request.Passed,
                completed = request.Completed,
                belowThreshold = score < minimumScore ||
                                 (request.SkyrimGradeScore > 0 && skyrimGradeScore < minimumScore) ||
                                 (request.CinematicDensityScore > 0 && cinematicDensityScore < minimumScore),
                players = Math.Max(0, request.Players),
                okPlayers = Math.Max(0, request.OkPlayers),
                initialTimelineObservationGapAccepted = request.InitialTimelineObservationGapAccepted,
                playerDeaths = Math.Max(0, request.PlayerDeaths),
                targetRemoved = Math.Max(0, request.TargetRemoved),
                killConfirmed = Math.Max(0, request.KillConfirmed),
                branchChoiceExpected = request.BranchChoiceExpected,
                choiceSelected = Math.Max(0, request.ChoiceSelected),
                choiceOutcomeScene = Math.Max(0, request.ChoiceOutcomeScene),
                choiceConsequence = Math.Max(0, request.ChoiceConsequence),
                worldSignalExpected = request.WorldSignalExpected,
                worldSignal = Math.Max(0, request.WorldSignal),
                presentationBeat = Math.Max(0, request.PresentationBeat),
                presentationSpeakerVariety = Math.Max(-1, request.PresentationSpeakerVariety),
                presentationStagedBeat = Math.Max(-1, request.PresentationStagedBeat),
                presentationStagedActorTotal = Math.Max(-1, request.PresentationStagedActorTotal),
                presentationStagedActorPeak = Math.Max(-1, request.PresentationStagedActorPeak),
                presentationStagedActionVariety = Math.Max(-1, request.PresentationStagedActionVariety),
                presentationStagedRoleVariety = Math.Max(-1, request.PresentationStagedRoleVariety),
                presentationStagedFormationVariety = Math.Max(-1, request.PresentationStagedFormationVariety),
                presentationStagedDelayedBeat = Math.Max(-1, request.PresentationStagedDelayedBeat),
                worldImpact = Math.Max(0, request.WorldImpact),
                worldImpactSummary = Math.Max(0, request.WorldImpactSummary),
                worldMemoryMarked = Math.Max(0, request.WorldMemoryMarked),
                narrativeScene = Math.Max(0, request.NarrativeScene),
                cinematicAction = Math.Max(0, request.CinematicAction),
                minNarrativeScenePerPlayer = Math.Max(-1, request.MinNarrativeScenePerPlayer),
                minPresentationBeatPerPlayer = Math.Max(-1, request.MinPresentationBeatPerPlayer),
                minCinematicActionPerPlayer = Math.Max(-1, request.MinCinematicActionPerPlayer),
                cinematicVariety = Math.Max(0, request.CinematicVariety),
                cinematicMotionVariety = Math.Max(0, request.CinematicMotionVariety),
                cinematicStaggeredScene = Math.Max(0, request.CinematicStaggeredScene),
                cinematicObjectiveFocalScene = Math.Max(0, request.CinematicObjectiveFocalScene),
                cinematicActorRoleVariety = Math.Max(0, request.CinematicActorRoleVariety),
                cinematicChoreographedScene = Math.Max(0, request.CinematicChoreographedScene),
                cinematicInteractionScene = Math.Max(0, request.CinematicInteractionScene),
                cinematicTacticVariety = Math.Max(0, request.CinematicTacticVariety),
                cinematicActorInstances = Math.Max(0, request.CinematicActorInstances),
                cinematicActorPeak = Math.Max(0, request.CinematicActorPeak),
                cinematicActorBudgetScore = Math.Clamp(request.CinematicActorBudgetScore, 0, 100),
                actionSceneCohesionScore,
                cinematicCatalogRoleVariety,
                cinematicModelRoleFitScore,
                cinematicMarkerScene = Math.Max(-1, request.CinematicMarkerScene),
                cinematicMarkerVariety = Math.Max(-1, request.CinematicMarkerVariety),
                cinematicPhaseCoverage = Math.Max(-1, request.CinematicPhaseCoverage),
                cinematicSetpiecePhaseCoverage = Math.Max(-1, request.CinematicSetpiecePhaseCoverage),
                cinematicMarkerPhaseCoverage = Math.Max(-1, request.CinematicMarkerPhaseCoverage),
                cinematicStoryChain = Math.Max(-1, request.CinematicStoryChain),
                sceneDirectorBeat = Math.Max(0, request.SceneDirectorBeat),
                sceneBeatOutcome = Math.Max(0, request.SceneBeatOutcome),
                sceneChoreographyPhase = Math.Max(0, request.SceneChoreographyPhase),
                sceneActorExchange = Math.Max(0, request.SceneActorExchange),
                sceneExchangeOutcome = Math.Max(0, request.SceneExchangeOutcome),
                sceneOutcomeSignal = Math.Max(0, request.SceneOutcomeSignal),
                sceneConsequence = Math.Max(0, request.SceneConsequence),
                sceneWorldSignal = Math.Max(0, request.SceneWorldSignal),
                worldSignalSceneShift = Math.Max(0, request.WorldSignalSceneShift),
                worldSignalSceneShiftDetail = Math.Max(-1, request.WorldSignalSceneShiftDetail),
                worldSignalSceneShiftPhaseVariety = Math.Max(-1, request.WorldSignalSceneShiftPhaseVariety),
                worldSignalSceneShiftSourceVariety = Math.Max(-1, request.WorldSignalSceneShiftSourceVariety),
                worldSignalSceneShiftTargetVariety = Math.Max(-1, request.WorldSignalSceneShiftTargetVariety),
                cinematicCleanup = Math.Max(0, request.CinematicCleanup),
                followupHuntStart = Math.Max(0, request.FollowupHuntStart),
                cinematicDensityScore,
                storyContinuityScore,
                storyArchetypeScore,
                skyrimGradeScore,
                operationalEvaluation,
                failureCategory = request.FailureCategory ?? string.Empty,
                elapsedSeconds = Math.Max(0.0, request.ElapsedSeconds),
                details = request.Details ?? string.Empty,
                evaluatedAt
            }, StoryCacheJsonOptions);
        }

        private static DynamicQuestStoryCacheQuality ToStoryCacheQuality(DynamicQuestStoryQuality quality)
        {
            if (quality == null)
                return DynamicQuestStoryCacheQuality.Empty;

            return new DynamicQuestStoryCacheQuality
            {
                TotalScore = quality.TotalScore,
                StructureScore = quality.StructureScore,
                KoreanScore = quality.KoreanScore,
                ObjectiveScore = quality.ObjectiveScore,
                ImmersionScore = quality.ImmersionScore,
                NarrativeScore = quality.NarrativeScore,
                PresentationScore = quality.PresentationScore,
                RebindabilityScore = quality.RebindabilityScore,
                SafetyScore = quality.SafetyScore,
                DiversityScore = quality.DiversityScore,
                Reasons = quality.Reasons ?? Array.Empty<string>()
            };
        }

        private static DynamicQuestStoryCacheDummyEvaluationSummary ParseDummyEvaluationSummary(string evaluationJson)
        {
            if (string.IsNullOrWhiteSpace(evaluationJson))
                return DynamicQuestStoryCacheDummyEvaluationSummary.Empty;

            try
            {
                using JsonDocument document = JsonDocument.Parse(evaluationJson);
                JsonElement root = document.RootElement;
                string failureCategory = GetJsonString(root, "failureCategory", "FailureCategory", "failure_category");
                int actionSceneCohesionScore = Math.Clamp(
                    GetJsonInt(root, 0, "actionSceneCohesionScore", "ActionSceneCohesionScore", "action_scene_cohesion_score"),
                    0,
                    100);
                int cinematicCatalogRoleVariety = Math.Max(
                    0,
                    GetJsonInt(root, 0, "cinematicCatalogRoleVariety", "CinematicCatalogRoleVariety", "cinematic_catalog_role_variety"));
                int cinematicModelRoleFitScore = Math.Clamp(
                    GetJsonInt(root, 0, "cinematicModelRoleFitScore", "CinematicModelRoleFitScore", "cinematic_model_role_fit_score"),
                    0,
                    100);
                if (!root.TryGetProperty("operationalEvaluation", out JsonElement operational) ||
                    operational.ValueKind != JsonValueKind.Object ||
                    !HasMeaningfulOperationalEvaluation(operational))
                {
                    return new DynamicQuestStoryCacheDummyEvaluationSummary
                    {
                        FailureCategory = failureCategory,
                        ActionSceneCohesionScore = actionSceneCohesionScore,
                        CinematicCatalogRoleVariety = cinematicCatalogRoleVariety,
                        CinematicModelRoleFitScore = cinematicModelRoleFitScore
                    };
                }

                return new DynamicQuestStoryCacheDummyEvaluationSummary
                {
                    OperationalScore = Math.Clamp(GetJsonInt(operational, 0, "totalScore", "TotalScore", "total_score"), 0, 100),
                    OperationalGrade = GetJsonString(operational, "grade", "Grade"),
                    OperationalPassed = GetJsonBool(operational, false, "passed", "Passed"),
                    FailureCategory = failureCategory,
                    ActionSceneCohesionScore = actionSceneCohesionScore,
                    CinematicCatalogRoleVariety = cinematicCatalogRoleVariety,
                    CinematicModelRoleFitScore = cinematicModelRoleFitScore
                };
            }
            catch (JsonException)
            {
                return DynamicQuestStoryCacheDummyEvaluationSummary.Empty;
            }
        }

        private static DynamicQuestStoryCacheQuality ParseStoryCacheQuality(string qualityJson, int fallbackTotalScore)
        {
            DynamicQuestStoryCacheQuality fallback = new()
            {
                TotalScore = Math.Clamp(fallbackTotalScore, 0, 100),
                StructureScore = 20,
                SafetyScore = 20
            };

            if (string.IsNullOrWhiteSpace(qualityJson))
                return fallback;

            try
            {
                using JsonDocument document = JsonDocument.Parse(qualityJson);
                JsonElement root = document.RootElement;
                return new DynamicQuestStoryCacheQuality
                {
                    TotalScore = Math.Clamp(GetJsonInt(root, fallback.TotalScore, "totalScore", "TotalScore"), 0, 100),
                    StructureScore = Math.Clamp(GetJsonInt(root, fallback.StructureScore, "structureScore", "StructureScore"), 0, 20),
                    KoreanScore = Math.Clamp(GetJsonInt(root, 0, "koreanScore", "KoreanScore"), 0, 10),
                    ObjectiveScore = Math.Clamp(GetJsonInt(root, 0, "objectiveScore", "ObjectiveScore"), 0, 15),
                    ImmersionScore = Math.Clamp(GetJsonInt(root, 0, "immersionScore", "ImmersionScore"), 0, 15),
                    NarrativeScore = Math.Clamp(GetJsonInt(root, 0, "narrativeScore", "NarrativeScore"), 0, 10),
                    PresentationScore = Math.Clamp(GetJsonInt(root, 0, "presentationScore", "PresentationScore"), 0, 10),
                    RebindabilityScore = Math.Clamp(GetJsonInt(root, 0, "rebindabilityScore", "RebindabilityScore"), 0, 10),
                    SafetyScore = Math.Clamp(GetJsonInt(root, fallback.SafetyScore, "safetyScore", "SafetyScore"), 0, 20),
                    DiversityScore = Math.Clamp(GetJsonInt(root, 0, "diversityScore", "DiversityScore"), 0, 10),
                    Reasons = GetJsonStringArray(root, "reasons", "Reasons")
                };
            }
            catch (JsonException)
            {
                return fallback;
            }
        }

        private static IList<DynamicQuestStoryCacheNarrativeScene> ParseStoryCacheNarrativeScenes(string scenesJson, bool includeText)
        {
            if (string.IsNullOrWhiteSpace(scenesJson))
                return Array.Empty<DynamicQuestStoryCacheNarrativeScene>();

            try
            {
                using JsonDocument document = JsonDocument.Parse(scenesJson);
                if (document.RootElement.ValueKind != JsonValueKind.Array)
                    return Array.Empty<DynamicQuestStoryCacheNarrativeScene>();

                return document.RootElement.EnumerateArray()
                    .Where(element => element.ValueKind == JsonValueKind.Object)
                    .Select(element => new DynamicQuestStoryCacheNarrativeScene
                    {
                        NodeId = GetJsonString(element, "nodeId", "NodeId", "node_id"),
                        SceneType = GetJsonString(element, "sceneType", "SceneType", "scene_type"),
                        Title = GetJsonString(element, "title", "Title"),
                        Body = includeText ? GetJsonString(element, "body", "Body") : string.Empty,
                        JournalEntry = includeText ? GetJsonString(element, "journalEntry", "JournalEntry", "journal_entry") : string.Empty,
                        Mood = GetJsonString(element, "mood", "Mood"),
                        RevealPolicy = GetJsonString(element, "revealPolicy", "RevealPolicy", "reveal_policy")
                    })
                    .ToList();
            }
            catch (JsonException)
            {
                return Array.Empty<DynamicQuestStoryCacheNarrativeScene>();
            }
        }

        private static IList<DynamicQuestStoryCachePresentationBeat> ParseStoryCachePresentationBeats(string beatsJson, bool includeText)
        {
            if (string.IsNullOrWhiteSpace(beatsJson))
                return Array.Empty<DynamicQuestStoryCachePresentationBeat>();

            try
            {
                using JsonDocument document = JsonDocument.Parse(beatsJson);
                if (document.RootElement.ValueKind != JsonValueKind.Array)
                    return Array.Empty<DynamicQuestStoryCachePresentationBeat>();

                return document.RootElement.EnumerateArray()
                    .Where(element => element.ValueKind == JsonValueKind.Object)
                    .Select(element => new DynamicQuestStoryCachePresentationBeat
                    {
                        NodeId = GetJsonString(element, "nodeId", "NodeId", "node_id"),
                        Trigger = GetJsonString(element, "trigger", "Trigger"),
                        Speaker = GetJsonString(element, "speaker", "Speaker"),
                        Text = includeText ? GetJsonString(element, "text", "Text") : string.Empty,
                        Emotion = GetJsonString(element, "emotion", "Emotion"),
                        Emote = GetJsonString(element, "emote", "Emote"),
                        CinematicAction = GetJsonString(element, "cinematicAction", "CinematicAction", "cinematic_action"),
                        SceneRole = GetJsonString(element, "sceneRole", "SceneRole", "scene_role"),
                        Formation = GetJsonString(element, "formation", "Formation"),
                        ActorCount = Math.Clamp(GetJsonInt(element, 0, "actorCount", "ActorCount", "actor_count"), 0, 100),
                        DelayMs = Math.Clamp(GetJsonInt(element, 0, "delayMs", "DelayMs", "delay_ms"), 0, 6000)
                    })
                    .ToList();
            }
            catch (JsonException)
            {
                return Array.Empty<DynamicQuestStoryCachePresentationBeat>();
            }
        }

        private static int StoryCacheSafetyScore(DbDynamicQuestTemplate row)
        {
            return ParseStoryCacheQuality(row?.StoryQualityJson, row?.StoryQualityScore ?? 0).SafetyScore;
        }

        private static int StoryCacheStructureScore(DbDynamicQuestTemplate row)
        {
            return ParseStoryCacheQuality(row?.StoryQualityJson, row?.StoryQualityScore ?? 0).StructureScore;
        }

        private static int StoryCacheCurrentQualityScore(DbDynamicQuestTemplate row)
        {
            if (row == null)
                return 0;

            DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForCache(
                BuildStoryQualityRequest(row),
                BuildStoryQualityText(row));
            return Math.Clamp(quality.TotalScore, 0, 100);
        }

        private static bool IsStoryCacheReadyForUse(DbDynamicQuestTemplate row)
        {
            if (!IsActiveStoryCacheRow(row))
                return false;

            if (BuildStoryCacheReadyBlockReasons(row).Count > 0)
                return false;

            if (string.Equals(row.StoryProvider, CodexCuratedStoryProvider, StringComparison.OrdinalIgnoreCase) &&
                !string.Equals(row.StoryModel, CodexCuratedStoryModel, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            DynamicQuestStoryCacheQuality quality = ParseStoryCacheQuality(row.StoryQualityJson, row.StoryQualityScore);
            return quality.NarrativeScore > 0 &&
                   quality.PresentationScore > 0 &&
                   ParseStoryCacheNarrativeScenes(row.StoryNarrativeJson, includeText: false).Count > 0 &&
                   ParseStoryCachePresentationBeats(row.StoryPresentationJson, includeText: false).Count > 0 &&
                   DynamicQuestStoryService.IsStoryQualityAcceptableForCache(
                       BuildStoryQualityRequest(row),
                       BuildStoryQualityText(row));
        }

        private static IList<string> BuildStoryCacheReadyBlockReasons(DbDynamicQuestTemplate row)
        {
            if (row == null)
                return Array.Empty<string>();

            List<string> reasons = BuildStoryCacheWarnings(row, DeserializeStoryCacheTags(row.TagsJson))
                .Where(IsBlockingStoryCacheWarning)
                .ToList();
            string dummyEvaluationBlockReason = DummyEvaluationBlockReason(row);
            if (!string.IsNullOrWhiteSpace(dummyEvaluationBlockReason))
                reasons.Add(dummyEvaluationBlockReason);
            if (RequiresChoiceSelectedSetPiece(row) &&
                !HasChoiceSelectedSetPiece(ParseStoryCachePresentationBeats(row.StoryPresentationJson, includeText: false)))
            {
                reasons.Add("choice_presentation_setpiece_missing");
            }
            if (RequiresWorldSignalSetPiece(row) &&
                !HasWorldSignalSetPiece(ParseStoryCachePresentationBeats(row.StoryPresentationJson, includeText: false)))
            {
                reasons.Add("world_signal_presentation_setpiece_missing");
            }
            if (RequiresChoiceSelectedSetPiece(row) &&
                !HasNarrativeScene(ParseStoryCacheNarrativeScenes(row.StoryNarrativeJson, includeText: false), "choice"))
            {
                reasons.Add("choice_narrative_scene_missing");
            }
            if (RequiresWorldSignalSetPiece(row) &&
                !HasNarrativeScene(ParseStoryCacheNarrativeScenes(row.StoryNarrativeJson, includeText: false), "observe_signal"))
            {
                reasons.Add("world_signal_narrative_scene_missing");
            }
            if (RequiresCinematicSetPieceCoverage(row))
            {
                foreach (string reason in BuildCinematicSetPieceCoverageBlockReasons(ParseStoryCachePresentationBeats(row.StoryPresentationJson, includeText: false)))
                    reasons.Add(reason);
            }

            return reasons
                .Where(reason => !string.IsNullOrWhiteSpace(reason))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();
        }

        private static bool HasBlockingStoryCacheWarnings(DbDynamicQuestTemplate row)
        {
            return BuildStoryCacheWarnings(row, DeserializeStoryCacheTags(row?.TagsJson)).Any(IsBlockingStoryCacheWarning);
        }

        private static bool IsBlockingStoryCacheWarning(string warning)
        {
            return string.Equals(warning, "autoaccept_item_acquired_legacy_trigger", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(warning, "branch_world_signal_mismatch", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(warning, "story_cache_unknown_realm", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(warning, "mob_growth_disabled", StringComparison.OrdinalIgnoreCase);
        }

        private static bool HasFailedDummyEvaluation(DbDynamicQuestTemplate row)
        {
            return !string.IsNullOrWhiteSpace(DummyEvaluationBlockReason(row));
        }

        private static string DummyEvaluationBlockReason(DbDynamicQuestTemplate row)
        {
            if (row == null || row.DummyEvaluationCount <= 0)
                return string.Empty;

            int fallbackMinimum = Math.Clamp(Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE, 1, 100);
            int score = Math.Clamp(row.DummyEvaluationScore, 0, 100);
            if (string.IsNullOrWhiteSpace(row.DummyEvaluationJson))
                return score < fallbackMinimum ? "dummy_evaluation_below_threshold" : string.Empty;

            try
            {
                using JsonDocument document = JsonDocument.Parse(row.DummyEvaluationJson);
                JsonElement root = document.RootElement;
                string failureCategory = GetJsonString(root, "failureCategory", "FailureCategory", "failure_category");
                string evaluationSource = GetJsonString(root, "source", "Source");
                if (IsTargetMissingDummyEvaluation(failureCategory))
                    return "dummy_evaluation_target_missing";

                bool infrastructureFailure = IsInfrastructureOrNoFreshDummyEvaluation(failureCategory);
                bool jsonBelowThreshold = GetJsonBool(root, false, "belowThreshold", "BelowThreshold");

                int minimumScore = Math.Clamp(GetJsonInt(root, fallbackMinimum, "minimumScore", "MinimumScore"), 1, 100);
                int evaluatedScore = Math.Clamp(GetJsonInt(root, score, "score", "Score"), 0, 100);
                int skyrimGradeScore = Math.Clamp(GetJsonInt(root, 0, "skyrimGradeScore", "SkyrimGradeScore"), 0, 100);
                int cinematicDensityScore = Math.Clamp(GetJsonInt(root, 0, "cinematicDensityScore", "CinematicDensityScore"), 0, 100);
                int storyContinuityScore = Math.Clamp(GetJsonInt(root, 0, "storyContinuityScore", "StoryContinuityScore", "story_continuity_score"), 0, 100);
                int storyArchetypeScore = Math.Clamp(GetJsonInt(root, 0, "storyArchetypeScore", "StoryArchetypeScore", "story_archetype_score"), 0, 100);
                int actionSceneCohesionScore = Math.Clamp(GetJsonInt(root, 0, "actionSceneCohesionScore", "ActionSceneCohesionScore", "action_scene_cohesion_score"), 0, 100);
                int rawCinematicCatalogRoleVariety = GetJsonInt(root, -1, "cinematicCatalogRoleVariety", "CinematicCatalogRoleVariety", "cinematic_catalog_role_variety");
                int rawCinematicModelRoleFitScore = GetJsonInt(root, -1, "cinematicModelRoleFitScore", "CinematicModelRoleFitScore", "cinematic_model_role_fit_score");
                int cinematicCatalogRoleVariety = Math.Max(0, rawCinematicCatalogRoleVariety);
                int cinematicModelRoleFitScore = Math.Clamp(rawCinematicModelRoleFitScore, 0, 100);
                bool hasOperationalEvaluation =
                    root.TryGetProperty("operationalEvaluation", out JsonElement operationalEvaluation) &&
                    operationalEvaluation.ValueKind == JsonValueKind.Object &&
                    HasMeaningfulOperationalEvaluation(operationalEvaluation);
                bool operationalPassed = hasOperationalEvaluation && GetJsonBool(operationalEvaluation, true, "passed", "Passed");
                string operationalGrade = hasOperationalEvaluation
                    ? GetJsonString(operationalEvaluation, "grade", "Grade")
                    : string.Empty;
                int sceneDirectorBeat = Math.Max(0, GetJsonInt(root, 0, "sceneDirectorBeat", "SceneDirectorBeat", "scene_director_beat"));
                int sceneBeatOutcome = Math.Max(0, GetJsonInt(root, 0, "sceneBeatOutcome", "SceneBeatOutcome", "scene_beat_outcome"));
                int sceneChoreographyPhase = Math.Max(0, GetJsonInt(root, 0, "sceneChoreographyPhase", "SceneChoreographyPhase", "scene_choreography_phase"));
                int choiceSelected = Math.Max(0, GetJsonInt(root, 0, "choiceSelected", "ChoiceSelected", "choice_selected"));
                int choiceOutcomeScene = Math.Max(0, GetJsonInt(root, 0, "choiceOutcomeScene", "ChoiceOutcomeScene", "choice_outcome_scene"));
                int choiceConsequence = Math.Max(0, GetJsonInt(root, 0, "choiceConsequence", "ChoiceConsequence", "choice_consequence"));
                int presentationBeat = Math.Max(0, GetJsonInt(root, 0, "presentationBeat", "PresentationBeat", "presentation_beat"));
                int presentationSpeakerVariety = GetJsonInt(root, -1, "presentationSpeakerVariety", "PresentationSpeakerVariety", "presentation_speaker_variety");
                int presentationStagedBeat = GetJsonInt(root, -1, "presentationStagedBeat", "PresentationStagedBeat", "presentation_staged_beat");
                int presentationStagedActionVariety = GetJsonInt(root, -1, "presentationStagedActionVariety", "PresentationStagedActionVariety", "presentation_staged_action_variety");
                int presentationStagedRoleVariety = GetJsonInt(root, -1, "presentationStagedRoleVariety", "PresentationStagedRoleVariety", "presentation_staged_role_variety");
                int worldImpactSummary = Math.Max(0, GetJsonInt(root, 0, "worldImpactSummary", "WorldImpactSummary", "world_impact_summary"));
                int worldMemoryMarked = Math.Max(0, GetJsonInt(root, 0, "worldMemoryMarked", "WorldMemoryMarked", "world_memory_marked"));
                int cinematicVariety = Math.Max(0, GetJsonInt(root, 0, "cinematicVariety", "CinematicVariety", "cinematic_variety"));
                int cinematicMotionVariety = Math.Max(0, GetJsonInt(root, 0, "cinematicMotionVariety", "CinematicMotionVariety", "cinematic_motion_variety"));
                int cinematicStaggeredScene = Math.Max(0, GetJsonInt(root, 0, "cinematicStaggeredScene", "CinematicStaggeredScene", "cinematic_staggered_scene"));
                int cinematicObjectiveFocalScene = Math.Max(0, GetJsonInt(root, 0, "cinematicObjectiveFocalScene", "CinematicObjectiveFocalScene", "cinematic_objective_focal_scene"));
                int cinematicActorRoleVariety = Math.Max(0, GetJsonInt(root, 0, "cinematicActorRoleVariety", "CinematicActorRoleVariety", "cinematic_actor_role_variety"));
                int cinematicChoreographedScene = Math.Max(0, GetJsonInt(root, 0, "cinematicChoreographedScene", "CinematicChoreographedScene", "cinematic_choreographed_scene"));
                int cinematicInteractionScene = Math.Max(0, GetJsonInt(root, 0, "cinematicInteractionScene", "CinematicInteractionScene", "cinematic_interaction_scene"));
                int cinematicTacticVariety = Math.Max(0, GetJsonInt(root, 0, "cinematicTacticVariety", "CinematicTacticVariety", "cinematic_tactic_variety"));
                int cinematicActorInstances = Math.Max(0, GetJsonInt(root, 0, "cinematicActorInstances", "CinematicActorInstances", "cinematic_actor_instances"));
                int cinematicActorPeak = Math.Max(0, GetJsonInt(root, 0, "cinematicActorPeak", "CinematicActorPeak", "cinematic_actor_peak"));
                int cinematicActorBudgetScore = Math.Clamp(GetJsonInt(root, 0, "cinematicActorBudgetScore", "CinematicActorBudgetScore", "cinematic_actor_budget_score"), 0, 100);
                int cinematicMarkerScene = GetJsonInt(root, -1, "cinematicMarkerScene", "CinematicMarkerScene", "cinematic_marker_scene");
                int cinematicMarkerVariety = GetJsonInt(root, -1, "cinematicMarkerVariety", "CinematicMarkerVariety", "cinematic_marker_variety");
                int cinematicPhaseCoverage = GetJsonInt(root, -1, "cinematicPhaseCoverage", "CinematicPhaseCoverage", "cinematic_phase_coverage");
                int cinematicSetpiecePhaseCoverage = GetJsonInt(root, -1, "cinematicSetpiecePhaseCoverage", "CinematicSetpiecePhaseCoverage", "cinematic_setpiece_phase_coverage");
                int cinematicMarkerPhaseCoverage = GetJsonInt(root, -1, "cinematicMarkerPhaseCoverage", "CinematicMarkerPhaseCoverage", "cinematic_marker_phase_coverage");
                int cinematicStoryChain = GetJsonInt(root, -1, "cinematicStoryChain", "CinematicStoryChain", "cinematic_story_chain");
                int sceneActorExchange = Math.Max(0, GetJsonInt(root, 0, "sceneActorExchange", "SceneActorExchange", "scene_actor_exchange"));
                int sceneExchangeOutcome = Math.Max(0, GetJsonInt(root, 0, "sceneExchangeOutcome", "SceneExchangeOutcome", "scene_exchange_outcome"));
                int sceneOutcomeSignal = Math.Max(0, GetJsonInt(root, 0, "sceneOutcomeSignal", "SceneOutcomeSignal", "scene_outcome_signal"));
                int sceneConsequence = Math.Max(0, GetJsonInt(root, 0, "sceneConsequence", "SceneConsequence", "scene_consequence"));
                bool hasBranchChoiceExpectedMetric = HasJsonProperty(root, "branchChoiceExpected", "BranchChoiceExpected", "branch_choice_expected");
                bool branchChoiceExpected = hasBranchChoiceExpectedMetric &&
                                            GetJsonBool(root, false, "branchChoiceExpected", "BranchChoiceExpected", "branch_choice_expected");
                bool hasWorldSignalExpectedMetric = HasJsonProperty(root, "worldSignalExpected", "WorldSignalExpected", "world_signal_expected");
                bool worldSignalExpected = hasWorldSignalExpectedMetric &&
                                           GetJsonBool(root, false, "worldSignalExpected", "WorldSignalExpected", "world_signal_expected");
                int worldSignal = Math.Max(0, GetJsonInt(root, 0, "worldSignal", "WorldSignal", "world_signal"));
                int worldSignalSceneShift = Math.Max(0, GetJsonInt(root, 0, "worldSignalSceneShift", "WorldSignalSceneShift", "world_signal_scene_shift"));
                int worldSignalSceneShiftDetail = GetJsonInt(root, -1, "worldSignalSceneShiftDetail", "WorldSignalSceneShiftDetail", "world_signal_scene_shift_detail");
                int worldSignalSceneShiftPhaseVariety = GetJsonInt(root, -1, "worldSignalSceneShiftPhaseVariety", "WorldSignalSceneShiftPhaseVariety", "world_signal_scene_shift_phase_variety");
                int worldSignalSceneShiftSourceVariety = GetJsonInt(root, -1, "worldSignalSceneShiftSourceVariety", "WorldSignalSceneShiftSourceVariety", "world_signal_scene_shift_source_variety");
                int worldSignalSceneShiftTargetVariety = GetJsonInt(root, -1, "worldSignalSceneShiftTargetVariety", "WorldSignalSceneShiftTargetVariety", "world_signal_scene_shift_target_variety");
                int cinematicCleanup = Math.Max(0, GetJsonInt(root, 0, "cinematicCleanup", "CinematicCleanup", "cinematic_cleanup"));
                int minNarrativeScenePerPlayer = GetJsonInt(root, -1, "minNarrativeScenePerPlayer", "MinNarrativeScenePerPlayer", "min_narrative_scene_per_player");
                int minPresentationBeatPerPlayer = GetJsonInt(root, -1, "minPresentationBeatPerPlayer", "MinPresentationBeatPerPlayer", "min_presentation_beat_per_player");
                int minCinematicActionPerPlayer = GetJsonInt(root, -1, "minCinematicActionPerPlayer", "MinCinematicActionPerPlayer", "min_cinematic_action_per_player");
                bool hasSceneBeatOutcomeMetric = HasJsonProperty(root, "sceneBeatOutcome", "SceneBeatOutcome", "scene_beat_outcome");
                bool hasSceneChoreographyPhaseMetric = HasJsonProperty(root, "sceneChoreographyPhase", "SceneChoreographyPhase", "scene_choreography_phase");
                bool hasWorldImpactSummaryMetric = HasJsonProperty(root, "worldImpactSummary", "WorldImpactSummary", "world_impact_summary");
                bool hasChoiceOutcomeSceneMetric = HasJsonProperty(root, "choiceOutcomeScene", "ChoiceOutcomeScene", "choice_outcome_scene");
                bool hasChoiceConsequenceMetric = HasJsonProperty(root, "choiceConsequence", "ChoiceConsequence", "choice_consequence");
                bool hasWorldMemoryMarkedMetric = HasJsonProperty(root, "worldMemoryMarked", "WorldMemoryMarked", "world_memory_marked");
                bool hasPresentationSpeakerVarietyMetric = HasJsonProperty(root, "presentationSpeakerVariety", "PresentationSpeakerVariety", "presentation_speaker_variety");
                bool hasPresentationStagedBeatMetric = HasJsonProperty(root, "presentationStagedBeat", "PresentationStagedBeat", "presentation_staged_beat");
                bool hasPresentationStagedActionVarietyMetric = HasJsonProperty(root, "presentationStagedActionVariety", "PresentationStagedActionVariety", "presentation_staged_action_variety");
                bool hasPresentationStagedRoleVarietyMetric = HasJsonProperty(root, "presentationStagedRoleVariety", "PresentationStagedRoleVariety", "presentation_staged_role_variety");
                bool hasCinematicVarietyMetric = HasJsonProperty(root, "cinematicVariety", "CinematicVariety", "cinematic_variety");
                bool hasCinematicMotionVarietyMetric = HasJsonProperty(root, "cinematicMotionVariety", "CinematicMotionVariety", "cinematic_motion_variety");
                bool hasCinematicStaggeredSceneMetric = HasJsonProperty(root, "cinematicStaggeredScene", "CinematicStaggeredScene", "cinematic_staggered_scene");
                bool hasCinematicObjectiveFocalSceneMetric = HasJsonProperty(root, "cinematicObjectiveFocalScene", "CinematicObjectiveFocalScene", "cinematic_objective_focal_scene");
                bool hasCinematicActorRoleVarietyMetric = HasJsonProperty(root, "cinematicActorRoleVariety", "CinematicActorRoleVariety", "cinematic_actor_role_variety");
                bool hasCinematicChoreographedSceneMetric = HasJsonProperty(root, "cinematicChoreographedScene", "CinematicChoreographedScene", "cinematic_choreographed_scene");
                bool hasCinematicInteractionSceneMetric = HasJsonProperty(root, "cinematicInteractionScene", "CinematicInteractionScene", "cinematic_interaction_scene");
                bool hasCinematicTacticVarietyMetric = HasJsonProperty(root, "cinematicTacticVariety", "CinematicTacticVariety", "cinematic_tactic_variety");
                bool hasCinematicActorInstancesMetric = HasJsonProperty(root, "cinematicActorInstances", "CinematicActorInstances", "cinematic_actor_instances");
                bool hasCinematicActorPeakMetric = HasJsonProperty(root, "cinematicActorPeak", "CinematicActorPeak", "cinematic_actor_peak");
                bool hasCinematicActorBudgetScoreMetric = HasJsonProperty(root, "cinematicActorBudgetScore", "CinematicActorBudgetScore", "cinematic_actor_budget_score");
                bool hasActionSceneCohesionScoreMetric = HasJsonProperty(root, "actionSceneCohesionScore", "ActionSceneCohesionScore", "action_scene_cohesion_score");
                bool hasCinematicCatalogRoleVarietyMetric =
                    rawCinematicCatalogRoleVariety >= 0 &&
                    HasJsonProperty(root, "cinematicCatalogRoleVariety", "CinematicCatalogRoleVariety", "cinematic_catalog_role_variety");
                bool hasCinematicModelRoleFitScoreMetric =
                    rawCinematicModelRoleFitScore >= 0 &&
                    HasJsonProperty(root, "cinematicModelRoleFitScore", "CinematicModelRoleFitScore", "cinematic_model_role_fit_score");
                bool hasCinematicMarkerSceneMetric = HasJsonProperty(root, "cinematicMarkerScene", "CinematicMarkerScene", "cinematic_marker_scene");
                bool hasCinematicMarkerVarietyMetric = HasJsonProperty(root, "cinematicMarkerVariety", "CinematicMarkerVariety", "cinematic_marker_variety");
                bool hasCinematicPhaseCoverageMetric = HasJsonProperty(root, "cinematicPhaseCoverage", "CinematicPhaseCoverage", "cinematic_phase_coverage");
                bool hasCinematicSetpiecePhaseCoverageMetric = HasJsonProperty(root, "cinematicSetpiecePhaseCoverage", "CinematicSetpiecePhaseCoverage", "cinematic_setpiece_phase_coverage");
                bool hasCinematicMarkerPhaseCoverageMetric = HasJsonProperty(root, "cinematicMarkerPhaseCoverage", "CinematicMarkerPhaseCoverage", "cinematic_marker_phase_coverage");
                bool hasCinematicStoryChainMetric = HasJsonProperty(root, "cinematicStoryChain", "CinematicStoryChain", "cinematic_story_chain");
                bool hasSceneExchangeOutcomeMetric = HasJsonProperty(root, "sceneExchangeOutcome", "SceneExchangeOutcome", "scene_exchange_outcome");
                bool hasSceneOutcomeSignalMetric = HasJsonProperty(root, "sceneOutcomeSignal", "SceneOutcomeSignal", "scene_outcome_signal");
                bool hasSceneConsequenceMetric = HasJsonProperty(root, "sceneConsequence", "SceneConsequence", "scene_consequence");
                bool hasWorldSignalSceneShiftMetric = HasJsonProperty(root, "worldSignalSceneShift", "WorldSignalSceneShift", "world_signal_scene_shift");
                bool hasWorldSignalSceneShiftDetailMetric = HasJsonProperty(root, "worldSignalSceneShiftDetail", "WorldSignalSceneShiftDetail", "world_signal_scene_shift_detail");
                bool hasWorldSignalSceneShiftPhaseVarietyMetric = HasJsonProperty(root, "worldSignalSceneShiftPhaseVariety", "WorldSignalSceneShiftPhaseVariety", "world_signal_scene_shift_phase_variety");
                bool hasWorldSignalSceneShiftSourceVarietyMetric = HasJsonProperty(root, "worldSignalSceneShiftSourceVariety", "WorldSignalSceneShiftSourceVariety", "world_signal_scene_shift_source_variety");
                bool hasWorldSignalSceneShiftTargetVarietyMetric = HasJsonProperty(root, "worldSignalSceneShiftTargetVariety", "WorldSignalSceneShiftTargetVariety", "world_signal_scene_shift_target_variety");
                bool hasStoryContinuityScoreMetric = HasJsonProperty(root, "storyContinuityScore", "StoryContinuityScore", "story_continuity_score");
                bool hasStoryArchetypeScoreMetric = HasJsonProperty(root, "storyArchetypeScore", "StoryArchetypeScore", "story_archetype_score");
                bool hasMinNarrativeScenePerPlayerMetric = HasJsonProperty(root, "minNarrativeScenePerPlayer", "MinNarrativeScenePerPlayer", "min_narrative_scene_per_player");
                bool hasMinPresentationBeatPerPlayerMetric = HasJsonProperty(root, "minPresentationBeatPerPlayer", "MinPresentationBeatPerPlayer", "min_presentation_beat_per_player");
                bool hasMinCinematicActionPerPlayerMetric = HasJsonProperty(root, "minCinematicActionPerPlayer", "MinCinematicActionPerPlayer", "min_cinematic_action_per_player");
                if (infrastructureFailure)
                    return string.Empty;

                if (HasBlockingStoryCacheWarnings(row) &&
                    string.Equals(failureCategory, "quest_runtime", StringComparison.OrdinalIgnoreCase))
                {
                    return string.Empty;
                }

                int players = Math.Max(0, GetJsonInt(root, 0, "players", "Players"));
                int okPlayers = Math.Max(0, GetJsonInt(root, 0, "okPlayers", "OkPlayers", "ok_players"));
                int playerDeaths = Math.Max(0, GetJsonInt(root, 0, "playerDeaths", "PlayerDeaths", "player_deaths"));
                bool initialTimelineObservationGapAccepted = GetJsonBool(
                    root,
                    false,
                    "initialTimelineObservationGapAccepted",
                    "InitialTimelineObservationGapAccepted",
                    "initial_timeline_observation_gap_accepted");
                bool passed = GetJsonBool(root, true, "passed", "Passed");
                bool completed = GetJsonBool(root, true, "completed", "Completed");
                bool okPlayerMismatchAllowed =
                    initialTimelineObservationGapAccepted &&
                    passed &&
                    completed &&
                    playerDeaths <= 0;
                bool runtimeMismatch =
                    !completed ||
                    playerDeaths > 0 ||
                    (players > 0 && okPlayers < players && !okPlayerMismatchAllowed);
                if (runtimeMismatch)
                    return DummyEvaluationRuntimeMismatchBlockReason(failureCategory);

                if (!passed)
                {
                    return DummyEvaluationRuntimeBlockReason(failureCategory);
                }

                if (hasOperationalEvaluation &&
                    (!operationalPassed ||
                     string.Equals(operationalGrade, "discard", StringComparison.OrdinalIgnoreCase)))
                {
                    return "dummy_evaluation_operational_failed";
                }

                if (IsRuntimeDummyMatrixEvaluationSource(evaluationSource) &&
                    completed &&
                    (!hasActionSceneCohesionScoreMetric ||
                     !hasCinematicCatalogRoleVarietyMetric ||
                     !hasCinematicModelRoleFitScoreMetric))
                {
                    return "dummy_evaluation_cinematic_metrics_missing";
                }

                if (hasSceneBeatOutcomeMetric && sceneDirectorBeat > 0 && sceneBeatOutcome <= 0)
                    return "dummy_evaluation_scene_beat_outcome_missing";
                if (hasSceneExchangeOutcomeMetric && sceneActorExchange > 0 && sceneExchangeOutcome <= 0)
                    return "dummy_evaluation_scene_exchange_outcome_missing";
                if (hasSceneOutcomeSignalMetric && sceneExchangeOutcome > 0 && sceneOutcomeSignal <= 0)
                    return "dummy_evaluation_scene_outcome_signal_missing";
                if (hasSceneConsequenceMetric && sceneExchangeOutcome > 0 && sceneConsequence <= 0)
                    return "dummy_evaluation_scene_consequence_missing";
                if (branchChoiceExpected && completed && choiceSelected <= 0)
                    return "dummy_evaluation_branch_choice_missing";
                if (hasChoiceOutcomeSceneMetric && choiceSelected >= Math.Max(1, players) && choiceOutcomeScene <= 0)
                    return "dummy_evaluation_choice_outcome_scene_missing";
                if (IsRuntimeDummyMatrixEvaluationSource(evaluationSource) &&
                    hasChoiceConsequenceMetric &&
                    choiceSelected >= Math.Max(1, players) &&
                    choiceOutcomeScene > 0 &&
                    choiceConsequence <= 0)
                {
                    return "dummy_evaluation_choice_consequence_missing";
                }
                if (hasPresentationSpeakerVarietyMetric &&
                    completed &&
                    presentationBeat >= Math.Max(2, players) &&
                    presentationSpeakerVariety >= 0 &&
                    presentationSpeakerVariety <= 1)
                {
                    return "dummy_evaluation_presentation_speaker_variety_low";
                }
                if (hasPresentationStagedBeatMetric &&
                    completed &&
                    presentationBeat >= Math.Max(3, players) &&
                    presentationStagedBeat >= 0 &&
                    presentationStagedBeat <= 0)
                {
                    return "dummy_evaluation_presentation_staging_missing";
                }
                if (hasPresentationStagedActionVarietyMetric &&
                    presentationStagedBeat >= Math.Max(3, players) &&
                    presentationStagedActionVariety >= 0 &&
                    presentationStagedActionVariety <= 1)
                {
                    return "dummy_evaluation_presentation_staged_action_variety_low";
                }
                if (hasPresentationStagedRoleVarietyMetric &&
                    presentationStagedBeat >= Math.Max(3, players) &&
                    presentationStagedRoleVariety >= 0 &&
                    presentationStagedRoleVariety <= 1)
                {
                    return "dummy_evaluation_presentation_staged_role_variety_low";
                }
                if (hasWorldImpactSummaryMetric && completed && worldImpactSummary <= 0)
                    return "dummy_evaluation_world_impact_summary_missing";
                if (IsRuntimeDummyMatrixEvaluationSource(evaluationSource) &&
                    hasWorldMemoryMarkedMetric &&
                    completed &&
                    worldMemoryMarked <= 0)
                {
                    return "dummy_evaluation_world_memory_missing";
                }
                if (hasCinematicVarietyMetric && sceneDirectorBeat >= Math.Max(3, players) && cinematicVariety <= 1)
                    return "dummy_evaluation_cinematic_variety_low";
                if (hasCinematicMotionVarietyMetric && sceneDirectorBeat >= Math.Max(3, players) && cinematicMotionVariety <= 1)
                    return "dummy_evaluation_cinematic_motion_variety_low";
                if (hasCinematicStaggeredSceneMetric && sceneDirectorBeat >= Math.Max(3, players) && cinematicStaggeredScene <= 0)
                    return "dummy_evaluation_cinematic_stagger_missing";
                if (hasCinematicObjectiveFocalSceneMetric && sceneDirectorBeat >= Math.Max(3, players) && cinematicObjectiveFocalScene <= 0)
                    return "dummy_evaluation_cinematic_objective_focal_missing";
                if (hasCinematicMarkerSceneMetric &&
                    sceneDirectorBeat >= Math.Max(3, players) &&
                    cinematicMarkerScene >= 0 &&
                    cinematicMarkerScene <= 0)
                {
                    return "dummy_evaluation_cinematic_marker_missing";
                }
                if (hasCinematicMarkerVarietyMetric &&
                    cinematicMarkerScene >= Math.Max(3, players) &&
                    cinematicMarkerVariety >= 0 &&
                    cinematicMarkerVariety <= 1)
                {
                    return "dummy_evaluation_cinematic_marker_variety_low";
                }
                if (hasCinematicPhaseCoverageMetric &&
                    sceneDirectorBeat >= Math.Max(3, players) &&
                    cinematicPhaseCoverage >= 0 &&
                    cinematicPhaseCoverage < 3)
                {
                    return "dummy_evaluation_cinematic_phase_coverage_low";
                }
                if (hasCinematicStoryChainMetric &&
                    sceneDirectorBeat >= Math.Max(3, players) &&
                    cinematicStoryChain >= 0 &&
                    cinematicStoryChain < 3)
                {
                    return "dummy_evaluation_cinematic_story_chain_low";
                }
                if (hasCinematicSetpiecePhaseCoverageMetric &&
                    sceneDirectorBeat >= Math.Max(3, players) &&
                    cinematicSetpiecePhaseCoverage >= 0 &&
                    cinematicSetpiecePhaseCoverage < 2)
                {
                    return "dummy_evaluation_cinematic_setpiece_phase_coverage_low";
                }
                if (hasCinematicMarkerPhaseCoverageMetric &&
                    cinematicMarkerScene >= Math.Max(3, players) &&
                    cinematicMarkerPhaseCoverage >= 0 &&
                    cinematicMarkerPhaseCoverage < 2)
                {
                    return "dummy_evaluation_cinematic_marker_phase_coverage_low";
                }
                if (hasCinematicActorRoleVarietyMetric && sceneDirectorBeat >= Math.Max(3, players) && cinematicActorRoleVariety <= 1)
                    return "dummy_evaluation_cinematic_actor_role_variety_low";
                if (hasCinematicChoreographedSceneMetric && sceneDirectorBeat >= Math.Max(3, players) && cinematicChoreographedScene <= 0)
                    return "dummy_evaluation_cinematic_choreography_missing";
                if (hasSceneChoreographyPhaseMetric && cinematicChoreographedScene > 0 && sceneChoreographyPhase <= 0)
                    return "dummy_evaluation_scene_choreography_phase_missing";
                if (hasCinematicInteractionSceneMetric && sceneDirectorBeat >= Math.Max(3, players) && cinematicInteractionScene <= 0)
                    return "dummy_evaluation_cinematic_interaction_missing";
                if (hasCinematicTacticVarietyMetric && sceneDirectorBeat >= Math.Max(3, players) && cinematicTacticVariety <= 1)
                    return "dummy_evaluation_cinematic_tactic_variety_low";
                if (hasCinematicActorPeakMetric && cinematicActorPeak > 100)
                    return "dummy_evaluation_cinematic_actor_budget_exceeded";
                if (hasCinematicActorInstancesMetric &&
                    cinematicActorInstances >= Math.Max(1, players) * 80 &&
                    cinematicCleanup <= 0)
                {
                    return "dummy_evaluation_cinematic_cleanup_missing";
                }
                if (hasCinematicActorBudgetScoreMetric && cinematicActorBudgetScore > 0 && cinematicActorBudgetScore < minimumScore)
                    return "dummy_evaluation_cinematic_actor_budget_low";
                if (hasActionSceneCohesionScoreMetric &&
                    sceneDirectorBeat >= Math.Max(3, players) &&
                    (actionSceneCohesionScore > 0 ||
                     string.Equals(failureCategory, "quest_quality", StringComparison.OrdinalIgnoreCase)) &&
                    actionSceneCohesionScore < minimumScore)
                {
                    return "dummy_evaluation_action_scene_cohesion_low";
                }
                if (hasCinematicCatalogRoleVarietyMetric &&
                    sceneDirectorBeat >= Math.Max(3, players) &&
                    cinematicCatalogRoleVariety < 2)
                {
                    return "dummy_evaluation_cinematic_catalog_role_variety_low";
                }
                if (hasCinematicModelRoleFitScoreMetric &&
                    sceneDirectorBeat >= Math.Max(3, players) &&
                    cinematicModelRoleFitScore < minimumScore)
                {
                    return "dummy_evaluation_cinematic_model_role_fit_low";
                }
                if (worldSignalExpected && completed && worldSignal <= 0)
                    return "dummy_evaluation_expected_world_signal_missing";
                if (hasWorldSignalSceneShiftMetric && worldSignal > 0 && worldSignalSceneShift <= 0)
                    return "dummy_evaluation_world_signal_scene_shift_missing";
                if (hasWorldSignalSceneShiftDetailMetric &&
                    worldSignalSceneShift > 0 &&
                    worldSignalSceneShiftDetail >= 0 &&
                    HasLowWorldSignalSceneShiftDetailCoverage(worldSignalSceneShift, worldSignalSceneShiftDetail))
                {
                    return "dummy_evaluation_world_signal_scene_shift_detail_low";
                }
                if (hasWorldSignalSceneShiftPhaseVarietyMetric &&
                    worldSignalSceneShift >= 2 &&
                    worldSignalSceneShiftPhaseVariety >= 0 &&
                    worldSignalSceneShiftPhaseVariety <= 1)
                {
                    return "dummy_evaluation_world_signal_scene_shift_phase_variety_low";
                }
                if (hasWorldSignalSceneShiftSourceVarietyMetric &&
                    worldSignalSceneShift >= 2 &&
                    worldSignalSceneShiftSourceVariety >= 0 &&
                    worldSignalSceneShiftSourceVariety <= 1)
                {
                    return "dummy_evaluation_world_signal_scene_shift_source_variety_low";
                }
                if (hasWorldSignalSceneShiftTargetVarietyMetric &&
                    worldSignalSceneShift >= 2 &&
                    worldSignalSceneShiftTargetVariety >= 0 &&
                    worldSignalSceneShiftTargetVariety <= 1)
                {
                    return "dummy_evaluation_world_signal_scene_shift_target_variety_low";
                }
                if (hasStoryContinuityScoreMetric && completed && storyContinuityScore < minimumScore)
                    return "dummy_evaluation_story_continuity_low";
                if (hasStoryArchetypeScoreMetric && completed && storyArchetypeScore < minimumScore)
                    return "dummy_evaluation_story_archetype_low";
                if (completed && players >= 2 &&
                    hasMinNarrativeScenePerPlayerMetric &&
                    minNarrativeScenePerPlayer >= 0 &&
                    minNarrativeScenePerPlayer < 2)
                {
                    return "dummy_evaluation_party_narrative_coverage_low";
                }
                if (completed && players >= 2 &&
                    hasMinPresentationBeatPerPlayerMetric &&
                    minPresentationBeatPerPlayer >= 0 &&
                    minPresentationBeatPerPlayer < 3)
                {
                    return "dummy_evaluation_party_presentation_coverage_low";
                }
                if (completed && players >= 2 &&
                    hasMinCinematicActionPerPlayerMetric &&
                    minCinematicActionPerPlayer >= 0 &&
                    minCinematicActionPerPlayer < 3)
                {
                    return "dummy_evaluation_party_cinematic_coverage_low";
                }

                return jsonBelowThreshold ||
                       evaluatedScore < minimumScore ||
                       (skyrimGradeScore > 0 && skyrimGradeScore < minimumScore) ||
                       (cinematicDensityScore > 0 && cinematicDensityScore < minimumScore)
                    ? "dummy_evaluation_below_threshold"
                    : string.Empty;
            }
            catch (JsonException)
            {
                return score < fallbackMinimum ? "dummy_evaluation_below_threshold" : string.Empty;
            }
        }

        private static bool IsRuntimeDummyMatrixEvaluationSource(string source)
        {
            string value = (source ?? string.Empty).Trim();
            return string.Equals(value, "run-dummy-dynamic-quest-matrix", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsInfrastructureOrNoFreshDummyEvaluation(string failureCategory)
        {
            return string.Equals(failureCategory, "infrastructure", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(failureCategory, "setup", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(failureCategory, "no_fresh_quest_attempt", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsTargetMissingDummyEvaluation(string failureCategory)
        {
            return string.Equals(failureCategory, "target_missing", StringComparison.OrdinalIgnoreCase);
        }

        private static string DummyEvaluationRuntimeBlockReason(string failureCategory)
        {
            string value = (failureCategory ?? string.Empty).Trim();
            if (string.Equals(value, "dummy_difficulty", StringComparison.OrdinalIgnoreCase))
                return "dummy_evaluation_difficulty_failed";
            if (string.Equals(value, "quest_quality", StringComparison.OrdinalIgnoreCase))
                return "dummy_evaluation_quality_failed";

            return "dummy_evaluation_runtime_failed";
        }

        private static string DummyEvaluationRuntimeMismatchBlockReason(string failureCategory)
        {
            string value = (failureCategory ?? string.Empty).Trim();
            if (string.Equals(value, "dummy_difficulty", StringComparison.OrdinalIgnoreCase))
                return "dummy_evaluation_difficulty_failed";
            if (string.Equals(value, "quest_quality", StringComparison.OrdinalIgnoreCase))
                return "dummy_evaluation_runtime_failed";

            return DummyEvaluationRuntimeBlockReason(value);
        }

        private static bool IsRuntimeBlockingDummyEvaluation(DynamicQuestDummyEvaluationRequest request)
        {
            if (request == null)
                return false;

            int players = Math.Max(0, request.Players);
            int okPlayers = Math.Max(0, request.OkPlayers);
            bool okPlayerMismatchAllowed =
                request.InitialTimelineObservationGapAccepted &&
                request.Passed &&
                request.Completed &&
                Math.Max(0, request.PlayerDeaths) <= 0;
            return !request.Passed ||
                   !request.Completed ||
                   Math.Max(0, request.PlayerDeaths) > 0 ||
                   (players > 0 && okPlayers < players && !okPlayerMismatchAllowed);
        }

        private static bool HasLowWorldSignalSceneShiftDetailCoverage(int sceneShiftCount, int detailedSceneShiftCount)
        {
            int total = Math.Max(0, sceneShiftCount);
            int detailed = Math.Max(0, detailedSceneShiftCount);
            if (total <= 0)
                return false;

            int required = Math.Max(1, (int)Math.Ceiling(total * 0.9));
            return detailed < required;
        }

        private static bool HasMeaningfulOperationalEvaluation(DynamicQuestDummyOperationalEvaluation evaluation)
        {
            if (evaluation == null)
                return false;

            return evaluation.TotalScore > 0 ||
                   !string.IsNullOrWhiteSpace(evaluation.Grade) ||
                   evaluation.FeasibilityScore > 0 ||
                   evaluation.DifficultyScore > 0 ||
                   evaluation.RewardBalanceScore > 0 ||
                   evaluation.RouteScore > 0 ||
                   evaluation.VarietyScore > 0 ||
                   evaluation.LoreScore > 0 ||
                   evaluation.ExploitPenalty > 0 ||
                   (evaluation.FailReasons?.Count ?? 0) > 0 ||
                   (evaluation.Warnings?.Count ?? 0) > 0 ||
                   (evaluation.SuggestedFixes?.Count ?? 0) > 0;
        }

        private static bool HasMeaningfulOperationalEvaluation(JsonElement operational)
        {
            if (operational.ValueKind != JsonValueKind.Object)
                return false;

            return GetJsonInt(operational, 0, "totalScore", "TotalScore", "total_score") > 0 ||
                   !string.IsNullOrWhiteSpace(GetJsonString(operational, "grade", "Grade")) ||
                   GetJsonInt(operational, 0, "feasibilityScore", "FeasibilityScore", "feasibility_score") > 0 ||
                   GetJsonInt(operational, 0, "difficultyScore", "DifficultyScore", "difficulty_score") > 0 ||
                   GetJsonInt(operational, 0, "rewardBalanceScore", "RewardBalanceScore", "reward_balance_score") > 0 ||
                   GetJsonInt(operational, 0, "routeScore", "RouteScore", "route_score") > 0 ||
                   GetJsonInt(operational, 0, "varietyScore", "VarietyScore", "variety_score") > 0 ||
                   GetJsonInt(operational, 0, "loreScore", "LoreScore", "lore_score") > 0 ||
                   GetJsonInt(operational, 0, "exploitPenalty", "ExploitPenalty", "exploit_penalty") > 0 ||
                   GetJsonStringArray(operational, "failReasons", "FailReasons", "fail_reasons").Count > 0 ||
                   GetJsonStringArray(operational, "warnings", "Warnings").Count > 0 ||
                   GetJsonStringArray(operational, "suggestedFixes", "SuggestedFixes", "suggested_fixes").Count > 0;
        }

        private static bool IsStoryTemplateReadyForCache(DynamicQuestTemplate template)
        {
            if (template == null)
                return false;

            DynamicQuestStoryCacheQuality quality = ParseStoryCacheQuality(template.StoryQualityJson, template.StoryQualityScore);
            if (RequiresChoiceSelectedSetPiece(template) &&
                !HasChoiceSelectedSetPiece(DeserializeStoryQualityArray<DynamicQuestPresentationBeat>(template.StoryPresentationJson)))
            {
                return false;
            }
            if (RequiresWorldSignalSetPiece(template) &&
                !HasWorldSignalSetPiece(DeserializeStoryQualityArray<DynamicQuestPresentationBeat>(template.StoryPresentationJson)))
            {
                return false;
            }
            if (RequiresChoiceSelectedSetPiece(template) &&
                !HasNarrativeScene(DeserializeStoryQualityArray<DynamicQuestNarrativeScene>(template.StoryNarrativeJson), "choice"))
            {
                return false;
            }
            if (RequiresWorldSignalSetPiece(template) &&
                !HasNarrativeScene(DeserializeStoryQualityArray<DynamicQuestNarrativeScene>(template.StoryNarrativeJson), "observe_signal"))
            {
                return false;
            }
            if (RequiresCinematicSetPieceCoverage(template) &&
                BuildCinematicSetPieceCoverageBlockReasons(DeserializeStoryQualityArray<DynamicQuestPresentationBeat>(template.StoryPresentationJson)).Count > 0)
            {
                return false;
            }

            return quality.NarrativeScore > 0 &&
                   quality.PresentationScore > 0 &&
                   DeserializeStoryQualityArray<DynamicQuestNarrativeScene>(template.StoryNarrativeJson).Count > 0 &&
                   DeserializeStoryQualityArray<DynamicQuestPresentationBeat>(template.StoryPresentationJson).Count > 0 &&
                   DynamicQuestStoryService.IsStoryQualityAcceptableForCache(
                       BuildStoryQualityRequest(template),
                       BuildStoryQualityText(template));
        }

        private static bool NeedsCinematicRuntimeFallback(DynamicQuestTemplate template)
        {
            if (template == null)
                return false;

            IList<DynamicQuestPresentationBeat> beats = DeserializeStoryQualityArray<DynamicQuestPresentationBeat>(template.StoryPresentationJson);
            bool hasCinematicIntent = beats.Any(beat =>
                beat != null &&
                (!string.IsNullOrWhiteSpace(beat.CinematicAction) ||
                 !string.IsNullOrWhiteSpace(beat.SceneRole) ||
                 !string.IsNullOrWhiteSpace(beat.Formation) ||
                 beat.ActorCount > 0));
            return hasCinematicIntent &&
                   BuildCinematicSetPieceCoverageBlockReasons(beats).Count > 0;
        }

        private static DynamicQuestTemplate EnsureBranchNarrativeScenes(DynamicQuestTemplate template)
        {
            if (template == null ||
                (!RequiresChoiceSelectedSetPiece(template) && !RequiresWorldSignalSetPiece(template)))
            {
                return template;
            }

            List<DynamicQuestNarrativeScene> scenes = DeserializeStoryQualityArray<DynamicQuestNarrativeScene>(template.StoryNarrativeJson)
                .Where(scene => scene != null)
                .ToList();
            bool changed = false;
            if (RequiresChoiceSelectedSetPiece(template) && !HasNarrativeScene(scenes, "choice"))
            {
                scenes.Add(new DynamicQuestNarrativeScene
                {
                    NodeId = "choice",
                    SceneType = "Choice",
                    Title = "선택 앞에 선 증인과 경비",
                    Body = "직접적인 위협은 줄었지만 현장에는 아직 설명되지 않은 표식이 남아 있다. 증인과 경비가 서로 다른 결말을 원하고, 플레이어의 선택이 이 사건의 다음 문장을 정한다.",
                    JournalEntry = "위협을 정리한 뒤 남은 표식을 어떻게 다룰지 선택해야 한다.",
                    Mood = "mysterious",
                    RevealPolicy = "FirstSeenOnly"
                });
                changed = true;
            }

            if (RequiresWorldSignalSetPiece(template) && !HasNarrativeScene(scenes, "observe_signal"))
            {
                scenes.Add(new DynamicQuestNarrativeScene
                {
                    NodeId = "observe_signal",
                    SceneType = "Aftermath",
                    Title = "현장을 흔드는 두 번째 신호",
                    Body = "기다리던 변화가 일어나자 숨겨져 있던 흔적이 다음 길을 드러낸다. 이 신호는 우연한 소음이 아니라 사건의 배후가 아직 움직이고 있다는 증거다.",
                    JournalEntry = "월드 신호가 발생했고, 남은 흔적을 따라 후속 상황을 확인해야 한다.",
                    Mood = "mysterious",
                    RevealPolicy = "FirstSeenOnly"
                });
                changed = true;
            }

            if (!changed)
                return template;

            template.StoryNarrativeJson = JsonSerializer.Serialize(scenes, StoryCacheJsonOptions);
            List<string> tags = new(template.Tags ?? Array.Empty<string>());
            if (!tags.Contains("story-branch-narrative-repaired", StringComparer.OrdinalIgnoreCase))
                tags.Add("story-branch-narrative-repaired");
            template.Tags = tags;
            return template;
        }

        private static DynamicQuestTemplate EnsureChoiceSelectedSetPiece(DynamicQuestTemplate template)
        {
            if (template == null ||
                !RequiresChoiceSelectedSetPiece(template) ||
                HasChoiceSelectedSetPiece(DeserializeStoryQualityArray<DynamicQuestPresentationBeat>(template.StoryPresentationJson)))
            {
                return template;
            }

            List<DynamicQuestPresentationBeat> beats = DeserializeStoryQualityArray<DynamicQuestPresentationBeat>(template.StoryPresentationJson)
                .Where(beat => beat != null)
                .ToList();
            if (!beats.Any(beat => IsChoiceNode(beat.NodeId) &&
                                   string.Equals(beat.Trigger, "OnChoiceShown", StringComparison.OrdinalIgnoreCase)))
            {
                beats.Add(new DynamicQuestPresentationBeat
                {
                    NodeId = "choice",
                    Trigger = "OnChoiceShown",
                    Speaker = "StartNpc",
                    Text = "증인과 경비가 서로 마주 선 채 다음 결정을 기다립니다.",
                    Emotion = "suspicion",
                    Emote = "Ponder",
                    CinematicAction = "threat_standoff",
                    SceneRole = "choice_confrontation",
                    Formation = "line",
                    ActorCount = 6
                });
            }

            beats.Add(new DynamicQuestPresentationBeat
            {
                NodeId = "choice",
                Trigger = "OnChoiceSelected",
                Speaker = "System",
                Text = "선택이 내려지자 경비들이 전열을 바꾸고, 증인은 남은 표식을 가리킵니다.",
                Emotion = "urgency",
                Emote = "Point",
                CinematicAction = "defender_intercept",
                SceneRole = "choice_fallout",
                Formation = "escort",
                ActorCount = 6,
                DelayMs = 900
            });

            template.StoryPresentationJson = JsonSerializer.Serialize(beats, StoryCacheJsonOptions);
            List<string> tags = new(template.Tags ?? Array.Empty<string>());
            if (!tags.Contains("story-choice-setpiece-repaired", StringComparer.OrdinalIgnoreCase))
                tags.Add("story-choice-setpiece-repaired");
            template.Tags = tags;
            return template;
        }

        private static DynamicQuestTemplate EnsureWorldSignalSetPiece(DynamicQuestTemplate template)
        {
            if (template == null ||
                !RequiresWorldSignalSetPiece(template) ||
                HasWorldSignalSetPiece(DeserializeStoryQualityArray<DynamicQuestPresentationBeat>(template.StoryPresentationJson)))
            {
                return template;
            }

            List<DynamicQuestPresentationBeat> beats = DeserializeStoryQualityArray<DynamicQuestPresentationBeat>(template.StoryPresentationJson)
                .Where(beat => beat != null)
                .ToList();
            beats.Add(BuildWorldSignalSetPieceBeat(ExtractBranchWorldSignal(template.Tags ?? Array.Empty<string>())));

            template.StoryPresentationJson = JsonSerializer.Serialize(beats, StoryCacheJsonOptions);
            List<string> tags = new(template.Tags ?? Array.Empty<string>());
            if (!tags.Contains("story-world-signal-setpiece-repaired", StringComparer.OrdinalIgnoreCase))
                tags.Add("story-world-signal-setpiece-repaired");
            template.Tags = tags;
            return template;
        }

        private static DynamicQuestPresentationBeat BuildWorldSignalSetPieceBeat(string branchWorldSignal)
        {
            string signal = (branchWorldSignal ?? string.Empty).Trim();
            if (IsMobGrowthSignal(signal))
            {
                return new DynamicQuestPresentationBeat
                {
                    NodeId = "observe_signal",
                    Trigger = "OnWorldSignal",
                    Speaker = "System",
                    Text = "성장한 위협의 흔적이 움직이자 경비들이 방패선을 앞으로 밀고, 길목의 압박이 한순간에 바뀝니다.",
                    Emotion = "urgency",
                    Emote = "Point",
                    CinematicAction = "guard_advance",
                    SceneRole = "growth_counterline",
                    Formation = "line",
                    ActorCount = 7,
                    DelayMs = 600
                };
            }

            if (IsItemAcquiredSignal(signal))
            {
                return new DynamicQuestPresentationBeat
                {
                    NodeId = "observe_signal",
                    Trigger = "OnWorldSignal",
                    Speaker = "Companion",
                    Text = "확보한 단서가 빛을 머금자 목격자가 손을 들어 숨겨진 경로와 다음 증거를 동시에 가리킵니다.",
                    Emotion = "suspicion",
                    Emote = "Ponder",
                    CinematicAction = "witness_point",
                    SceneRole = "clue_witness",
                    Formation = "escort",
                    ActorCount = 4,
                    DelayMs = 700
                };
            }

            return new DynamicQuestPresentationBeat
            {
                NodeId = "observe_signal",
                Trigger = "OnWorldSignal",
                Speaker = "System",
                Text = "정해진 시각의 신호가 현장을 흔들고, 의식 표식이 끊기며 다음 길이 드러납니다.",
                Emotion = "urgency",
                Emote = "Point",
                CinematicAction = "ritual_interrupt",
                SceneRole = "signal_reveal",
                Formation = "ring",
                ActorCount = 5,
                DelayMs = 600
            };
        }

        private static bool RequiresChoiceSelectedSetPiece(DbDynamicQuestTemplate row)
        {
            if (row == null)
                return false;

            IList<string> tags = DeserializeStoryCacheTags(row.TagsJson);
            return tags.Any(IsKnownBranchTag) ||
                   !string.IsNullOrWhiteSpace(ExtractBranchWorldSignal(tags)) ||
                   ParseStoryCacheNarrativeScenes(row.StoryNarrativeJson, includeText: false)
                       .Any(scene => IsChoiceNode(scene.NodeId)) ||
                   ParseStoryCachePresentationBeats(row.StoryPresentationJson, includeText: false)
                       .Any(beat => IsChoiceNode(beat.NodeId) ||
                                    string.Equals(beat.Trigger, "OnChoiceShown", StringComparison.OrdinalIgnoreCase));
        }

        private static bool RequiresChoiceSelectedSetPiece(DynamicQuestTemplate template)
        {
            if (template == null)
                return false;

            return (template.Tags ?? Array.Empty<string>()).Any(IsKnownBranchTag) ||
                   (template.Tags ?? Array.Empty<string>()).Any(tag =>
                       (tag ?? string.Empty).StartsWith("world-signal:", StringComparison.OrdinalIgnoreCase)) ||
                   DeserializeStoryQualityArray<DynamicQuestNarrativeScene>(template.StoryNarrativeJson)
                       .Any(scene => IsChoiceNode(scene.NodeId)) ||
                   DeserializeStoryQualityArray<DynamicQuestPresentationBeat>(template.StoryPresentationJson)
                       .Any(beat => IsChoiceNode(beat.NodeId) ||
                                    string.Equals(beat.Trigger, "OnChoiceShown", StringComparison.OrdinalIgnoreCase));
        }

        private static bool RequiresWorldSignalSetPiece(DbDynamicQuestTemplate row)
        {
            if (row == null)
                return false;

            return !string.IsNullOrWhiteSpace(ExtractBranchWorldSignal(DeserializeStoryCacheTags(row.TagsJson)));
        }

        private static bool RequiresWorldSignalSetPiece(DynamicQuestTemplate template)
        {
            if (template == null)
                return false;

            return (template.Tags ?? Array.Empty<string>()).Any(tag =>
                (tag ?? string.Empty).StartsWith("world-signal:", StringComparison.OrdinalIgnoreCase));
        }

        private static bool RequiresCinematicSetPieceCoverage(DbDynamicQuestTemplate row)
        {
            return DeserializeStoryCacheTags(row?.TagsJson).Any(IsCinematicIntentTag);
        }

        private static bool RequiresCinematicSetPieceCoverage(DynamicQuestTemplate template)
        {
            return (template?.Tags ?? Array.Empty<string>()).Any(IsCinematicIntentTag);
        }

        private static bool IsCinematicIntentTag(string tag)
        {
            string value = (tag ?? string.Empty).Trim();
            return string.Equals(value, "story-cinematic", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "scene-director", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "dark-brotherhood", StringComparison.OrdinalIgnoreCase) ||
                   value.StartsWith("cinematic-actors:", StringComparison.OrdinalIgnoreCase);
        }

        private static IList<string> BuildCinematicSetPieceCoverageBlockReasons(IEnumerable<DynamicQuestStoryCachePresentationBeat> beats)
        {
            return BuildCinematicSetPieceCoverageBlockReasons(
                (beats ?? Array.Empty<DynamicQuestStoryCachePresentationBeat>())
                    .Where(beat => beat != null)
                    .Select(beat => new CinematicSetPieceSignal
                    {
                        Trigger = beat.Trigger,
                        Action = beat.CinematicAction,
                        SceneRole = beat.SceneRole,
                        Formation = beat.Formation,
                        ActorCount = beat.ActorCount,
                        DelayMs = beat.DelayMs
                    }));
        }

        private static IList<string> BuildCinematicSetPieceCoverageBlockReasons(IEnumerable<DynamicQuestPresentationBeat> beats)
        {
            return BuildCinematicSetPieceCoverageBlockReasons(
                (beats ?? Array.Empty<DynamicQuestPresentationBeat>())
                    .Where(beat => beat != null)
                    .Select(beat => new CinematicSetPieceSignal
                    {
                        Trigger = beat.Trigger,
                        Action = beat.CinematicAction,
                        SceneRole = beat.SceneRole,
                        Formation = beat.Formation,
                        ActorCount = beat.ActorCount,
                        DelayMs = beat.DelayMs
                    }));
        }

        private static IList<string> BuildCinematicSetPieceCoverageBlockReasons(IEnumerable<CinematicSetPieceSignal> signals)
        {
            List<CinematicSetPieceSignal> staged = (signals ?? Array.Empty<CinematicSetPieceSignal>())
                .Where(signal =>
                    signal != null &&
                    signal.ActorCount > 0 &&
                    !string.IsNullOrWhiteSpace(signal.Action) &&
                    !string.IsNullOrWhiteSpace(signal.SceneRole) &&
                    !string.IsNullOrWhiteSpace(signal.Formation))
                .ToList();
            HashSet<string> actions = new(staged.Select(signal => signal.Action.Trim()), StringComparer.OrdinalIgnoreCase);
            HashSet<string> triggers = new(
                staged
                    .Select(signal => (signal.Trigger ?? string.Empty).Trim())
                    .Where(trigger => !string.IsNullOrWhiteSpace(trigger)),
                StringComparer.OrdinalIgnoreCase);
            HashSet<string> formations = new(staged.Select(signal => signal.Formation.Trim()), StringComparer.OrdinalIgnoreCase);
            HashSet<string> roles = new(staged.Select(signal => signal.SceneRole.Trim()), StringComparer.OrdinalIgnoreCase);
            int maxActors = staged.Count == 0 ? 0 : staged.Max(signal => Math.Max(0, signal.ActorCount));
            bool hasDelayedBeat = staged.Any(signal => signal.DelayMs > 0);
            bool hasActionScene = actions.Any(IsActionSceneCinematicAction);

            List<string> reasons = new();
            if (staged.Count < 4)
                reasons.Add("cinematic_set_piece_count_missing");
            if (actions.Count < 3)
                reasons.Add("cinematic_action_variety_missing");
            if (triggers.Count < 3)
                reasons.Add("cinematic_trigger_variety_missing");
            if (formations.Count < 2)
                reasons.Add("cinematic_formation_variety_missing");
            if (roles.Count < 3)
                reasons.Add("cinematic_scene_role_variety_missing");
            if (maxActors < 4)
                reasons.Add("cinematic_actor_scale_missing");
            if (!hasDelayedBeat)
                reasons.Add("cinematic_delayed_beat_missing");
            if (!hasActionScene)
                reasons.Add("cinematic_action_scene_missing");
            return reasons;
        }

        private static bool IsActionSceneCinematicAction(string action)
        {
            string value = (action ?? string.Empty).Trim();
            return string.Equals(value, "ambush_reveal", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "defender_intercept", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "scout_retreat", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "ritual_interrupt", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "threat_standoff", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "combat_stance", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "hold_ground", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "guard_advance", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "fallback_guard", StringComparison.OrdinalIgnoreCase);
        }

        private sealed class CinematicSetPieceSignal
        {
            public string Trigger { get; set; } = string.Empty;
            public string Action { get; set; } = string.Empty;
            public string SceneRole { get; set; } = string.Empty;
            public string Formation { get; set; } = string.Empty;
            public int ActorCount { get; set; }
            public int DelayMs { get; set; }
        }

        private sealed class DynamicQuestStoryCacheDummyEvaluationSummary
        {
            public static DynamicQuestStoryCacheDummyEvaluationSummary Empty { get; } = new();

            public int OperationalScore { get; set; }
            public string OperationalGrade { get; set; } = string.Empty;
            public bool OperationalPassed { get; set; }
            public string FailureCategory { get; set; } = string.Empty;
            public int ActionSceneCohesionScore { get; set; }
            public int CinematicCatalogRoleVariety { get; set; }
            public int CinematicModelRoleFitScore { get; set; }
        }

        private static bool HasChoiceSelectedSetPiece(IEnumerable<DynamicQuestStoryCachePresentationBeat> beats)
        {
            return (beats ?? Array.Empty<DynamicQuestStoryCachePresentationBeat>()).Any(beat =>
                IsChoiceNode(beat.NodeId) &&
                string.Equals(beat.Trigger, "OnChoiceSelected", StringComparison.OrdinalIgnoreCase) &&
                beat.ActorCount > 0 &&
                !string.IsNullOrWhiteSpace(beat.CinematicAction) &&
                !string.IsNullOrWhiteSpace(beat.SceneRole));
        }

        private static bool HasChoiceSelectedSetPiece(IEnumerable<DynamicQuestPresentationBeat> beats)
        {
            return (beats ?? Array.Empty<DynamicQuestPresentationBeat>()).Any(beat =>
                IsChoiceNode(beat.NodeId) &&
                string.Equals(beat.Trigger, "OnChoiceSelected", StringComparison.OrdinalIgnoreCase) &&
                beat.ActorCount > 0 &&
                !string.IsNullOrWhiteSpace(beat.CinematicAction) &&
                !string.IsNullOrWhiteSpace(beat.SceneRole));
        }

        private static bool HasWorldSignalSetPiece(IEnumerable<DynamicQuestStoryCachePresentationBeat> beats)
        {
            return (beats ?? Array.Empty<DynamicQuestStoryCachePresentationBeat>()).Any(beat =>
                string.Equals(beat.Trigger, "OnWorldSignal", StringComparison.OrdinalIgnoreCase) &&
                beat.ActorCount > 0 &&
                !string.IsNullOrWhiteSpace(beat.CinematicAction) &&
                !string.IsNullOrWhiteSpace(beat.SceneRole));
        }

        private static bool HasWorldSignalSetPiece(IEnumerable<DynamicQuestPresentationBeat> beats)
        {
            return (beats ?? Array.Empty<DynamicQuestPresentationBeat>()).Any(beat =>
                string.Equals(beat.Trigger, "OnWorldSignal", StringComparison.OrdinalIgnoreCase) &&
                beat.ActorCount > 0 &&
                !string.IsNullOrWhiteSpace(beat.CinematicAction) &&
                !string.IsNullOrWhiteSpace(beat.SceneRole));
        }

        private static bool HasNarrativeScene(IEnumerable<DynamicQuestStoryCacheNarrativeScene> scenes, string nodeId)
        {
            return (scenes ?? Array.Empty<DynamicQuestStoryCacheNarrativeScene>()).Any(scene =>
                string.Equals((scene?.NodeId ?? string.Empty).Trim(), nodeId, StringComparison.OrdinalIgnoreCase));
        }

        private static bool HasNarrativeScene(IEnumerable<DynamicQuestNarrativeScene> scenes, string nodeId)
        {
            return (scenes ?? Array.Empty<DynamicQuestNarrativeScene>()).Any(scene =>
                string.Equals((scene?.NodeId ?? string.Empty).Trim(), nodeId, StringComparison.OrdinalIgnoreCase));
        }

        private static bool IsChoiceNode(string nodeId)
        {
            return string.Equals((nodeId ?? string.Empty).Trim(), "choice", StringComparison.OrdinalIgnoreCase);
        }

        private static DynamicQuestStoryRequest BuildStoryQualityRequest(DbDynamicQuestTemplate row)
        {
            return new DynamicQuestStoryRequest
            {
                TemplateId = row?.TemplateId ?? string.Empty,
                Realm = row?.Realm ?? string.Empty,
                StartNpcName = row?.PreferredStartNpcName ?? string.Empty,
                RegionId = row?.PreferredRegionId ?? 0,
                TargetName = row?.TargetNameHint ?? string.Empty,
                Count = Math.Max(1, row?.Count ?? 1),
                MinLevel = Math.Max(1, row?.MinLevel ?? 1),
                MaxLevel = Math.Max(1, row?.MaxLevel ?? 50),
                StorySeed = row?.StorySeed ?? string.Empty
            };
        }

        private static DynamicQuestStoryRequest BuildStoryQualityRequest(DynamicQuestTemplate template)
        {
            return new DynamicQuestStoryRequest
            {
                TemplateId = template?.TemplateId ?? string.Empty,
                Realm = template?.Realm ?? string.Empty,
                StartNpcName = template?.PreferredStartNpcName ?? string.Empty,
                RegionId = template?.PreferredRegionId ?? 0,
                TargetName = template?.TargetNameHint ?? string.Empty,
                Count = Math.Max(1, template?.Count ?? 1),
                MinLevel = Math.Max(1, template?.MinLevel ?? 1),
                MaxLevel = Math.Max(1, template?.MaxLevel ?? 50),
                StorySeed = template?.StorySeed ?? string.Empty
            };
        }

        private static DynamicQuestStoryText BuildStoryQualityText(DbDynamicQuestTemplate row)
        {
            return new DynamicQuestStoryText
            {
                Title = row?.Title ?? string.Empty,
                OfferText = row?.OfferText ?? string.Empty,
                ProgressText = row?.ProgressText ?? string.Empty,
                FinishText = row?.FinishText ?? string.Empty,
                QualityScore = Math.Clamp(row?.StoryQualityScore ?? 0, 0, 100),
                NarrativeScenes = DeserializeStoryQualityArray<DynamicQuestNarrativeScene>(row?.StoryNarrativeJson),
                PresentationBeats = DeserializeStoryQualityArray<DynamicQuestPresentationBeat>(row?.StoryPresentationJson)
            };
        }

        private static DynamicQuestStoryText BuildStoryQualityText(DynamicQuestTemplate template)
        {
            return new DynamicQuestStoryText
            {
                Title = template?.Title ?? string.Empty,
                OfferText = template?.OfferText ?? string.Empty,
                ProgressText = template?.ProgressText ?? string.Empty,
                FinishText = template?.FinishText ?? string.Empty,
                QualityScore = Math.Clamp(template?.StoryQualityScore ?? 0, 0, 100),
                NarrativeScenes = DeserializeStoryQualityArray<DynamicQuestNarrativeScene>(template?.StoryNarrativeJson),
                PresentationBeats = DeserializeStoryQualityArray<DynamicQuestPresentationBeat>(template?.StoryPresentationJson)
            };
        }

        private static IList<T> DeserializeStoryQualityArray<T>(string json)
        {
            if (string.IsNullOrWhiteSpace(json))
                return Array.Empty<T>();

            try
            {
                List<T> values = JsonSerializer.Deserialize<List<T>>(json, StoryCacheJsonOptions);
                return values != null ? values : Array.Empty<T>();
            }
            catch (JsonException)
            {
                return Array.Empty<T>();
            }
        }

        private static int GetJsonInt(JsonElement root, int fallback, params string[] names)
        {
            foreach (string name in names)
            {
                if (!root.TryGetProperty(name, out JsonElement element))
                    continue;
                if (element.ValueKind == JsonValueKind.Number && element.TryGetInt32(out int value))
                    return value;
                if (element.ValueKind == JsonValueKind.String && int.TryParse(element.GetString(), out value))
                    return value;
            }

            return fallback;
        }

        private static bool HasJsonProperty(JsonElement root, params string[] names)
        {
            foreach (string name in names)
            {
                if (root.TryGetProperty(name, out _))
                    return true;
            }

            return false;
        }

        private static string GetJsonString(JsonElement root, params string[] names)
        {
            foreach (string name in names)
            {
                if (root.TryGetProperty(name, out JsonElement element) && element.ValueKind == JsonValueKind.String)
                    return element.GetString() ?? string.Empty;
            }

            return string.Empty;
        }

        private static bool GetJsonBool(JsonElement root, bool fallback, params string[] names)
        {
            foreach (string name in names)
            {
                if (!root.TryGetProperty(name, out JsonElement element))
                    continue;
                if (element.ValueKind == JsonValueKind.True)
                    return true;
                if (element.ValueKind == JsonValueKind.False)
                    return false;
                if (element.ValueKind == JsonValueKind.String && bool.TryParse(element.GetString(), out bool value))
                    return value;
            }

            return fallback;
        }

        private static IList<string> GetJsonStringArray(JsonElement root, params string[] names)
        {
            foreach (string name in names)
            {
                if (!root.TryGetProperty(name, out JsonElement element) || element.ValueKind != JsonValueKind.Array)
                    continue;

                return element.EnumerateArray()
                    .Where(item => item.ValueKind == JsonValueKind.String)
                    .Select(item => item.GetString() ?? string.Empty)
                    .Where(item => !string.IsNullOrWhiteSpace(item))
                    .ToList();
            }

            return Array.Empty<string>();
        }

        private static IDictionary<string, int> CountBy<T>(
            IEnumerable<T> rows,
            Func<T, string> selector)
        {
            Dictionary<string, int> counters = new(StringComparer.OrdinalIgnoreCase);
            foreach (T row in rows ?? Array.Empty<T>())
            {
                string key = SnapshotKey(selector?.Invoke(row));
                counters[key] = counters.TryGetValue(key, out int count) ? count + 1 : 1;
            }

            return counters;
        }

        private static IDictionary<string, int> CountStoryCacheByArchetype(
            IEnumerable<DbDynamicQuestTemplate> rows,
            Func<DbDynamicQuestTemplate, bool> predicate = null)
        {
            return CountBy(
                (rows ?? Array.Empty<DbDynamicQuestTemplate>())
                    .Where(row => predicate == null || predicate(row)),
                row => ExtractStoryArchetype(DeserializeStoryCacheTags(row?.TagsJson)));
        }

        private static IDictionary<string, int> CountStoryCacheNotReadyReasons(IEnumerable<DbDynamicQuestTemplate> rows)
        {
            Dictionary<string, int> counters = new(StringComparer.OrdinalIgnoreCase);
            foreach (DbDynamicQuestTemplate row in rows ?? Array.Empty<DbDynamicQuestTemplate>())
            {
                if (IsStoryCacheReadyForUse(row))
                    continue;

                IList<string> blockingReasons = BuildStoryCacheReadyBlockReasons(row);
                if (blockingReasons.Count > 0)
                {
                    foreach (string reason in blockingReasons)
                    {
                        string key = SnapshotKey(reason);
                        counters[key] = counters.TryGetValue(key, out int count) ? count + 1 : 1;
                    }

                    continue;
                }

                DynamicQuestStoryCacheQuality current = ToStoryCacheQuality(
                    DynamicQuestStoryService.EvaluateQualityDetailsForCache(
                        BuildStoryQualityRequest(row),
                        BuildStoryQualityText(row)));
                List<string> negativeReasons = (current.Reasons ?? Array.Empty<string>())
                    .Where(IsStoryCacheNotReadyReason)
                    .ToList();
                IList<string> reasons = negativeReasons.Count == 0
                    ? new[] { "quality_below_gate" }
                    : negativeReasons;
                foreach (string reason in reasons)
                {
                    string key = SnapshotKey(reason);
                    counters[key] = counters.TryGetValue(key, out int count) ? count + 1 : 1;
                }
            }

            return counters;
        }

        private static IDictionary<string, int> CountStoryCacheWarnings(IEnumerable<DbDynamicQuestTemplate> rows)
        {
            Dictionary<string, int> counters = new(StringComparer.OrdinalIgnoreCase);
            foreach (DbDynamicQuestTemplate row in rows ?? Array.Empty<DbDynamicQuestTemplate>())
            {
                IList<string> tags = DeserializeStoryCacheTags(row?.TagsJson);
                foreach (string warning in BuildStoryCacheWarnings(row, tags))
                {
                    string key = SnapshotKey(warning);
                    counters[key] = counters.TryGetValue(key, out int count) ? count + 1 : 1;
                }
            }

            return counters;
        }

        private static IList<string> BuildStoryCacheWarnings(DbDynamicQuestTemplate row, IList<string> tags)
        {
            if (row == null)
                return Array.Empty<string>();

            List<string> warnings = new();
            tags ??= Array.Empty<string>();
            string trigger = (row.Trigger ?? string.Empty).Trim();
            string worldSignal = ExtractBranchWorldSignal(tags);
            DynamicQuestStartMode startMode = ParseStoryCacheStartMode(row.StartMode);

            if (!IsStarterRealm(RealmNameForRegion(row.PreferredRegionId)))
                warnings.Add("story_cache_unknown_realm");

            if (startMode == DynamicQuestStartMode.AutoAccept &&
                IsItemAcquiredSignal(worldSignal) &&
                (IsItemAcquiredSignal(trigger) || IsTimeWindowSignal(trigger)))
            {
                warnings.Add("autoaccept_item_acquired_legacy_trigger");
            }

            string expectedBranchTag = BranchTagForWorldSignal(worldSignal);
            if (!string.IsNullOrWhiteSpace(expectedBranchTag))
            {
                string mismatchedBranch = tags.FirstOrDefault(tag =>
                    IsKnownBranchTag(tag) &&
                    !string.Equals(tag, expectedBranchTag, StringComparison.OrdinalIgnoreCase));
                if (!string.IsNullOrWhiteSpace(mismatchedBranch))
                    warnings.Add("branch_world_signal_mismatch");
            }

            if (IsMobGrowthSignal(worldSignal) && !Properties.WORLDAI_MOB_GROWTH_ENABLED)
                warnings.Add("mob_growth_disabled");

            return warnings
                .Where(item => !string.IsNullOrWhiteSpace(item))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();
        }

        private static bool IsKnownBranchTag(string tag)
        {
            string value = (tag ?? string.Empty).Trim();
            return string.Equals(value, "branch:mob-growth", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "branch:time-window", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "branch:item-acquired", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "branch:region-entered", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsItemAcquiredSignal(string signal)
        {
            return (signal ?? string.Empty).Trim().StartsWith("item-acquired", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsTimeWindowSignal(string signal)
        {
            return (signal ?? string.Empty).Trim().StartsWith("time-window", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsMobGrowthSignal(string signal)
        {
            return (signal ?? string.Empty).Trim().StartsWith("mob-growth", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsStoryCacheNotReadyReason(string reason)
        {
            string value = (reason ?? string.Empty).Trim();
            if (value.Length == 0)
                return false;

            return !value.Equals("narrative_scene", StringComparison.OrdinalIgnoreCase) &&
                   !value.Equals("presentation_beat", StringComparison.OrdinalIgnoreCase);
        }

        private static IList<string> DeserializeStoryCacheTags(string tagsJson)
        {
            if (string.IsNullOrWhiteSpace(tagsJson))
                return Array.Empty<string>();

            try
            {
                return JsonSerializer.Deserialize<List<string>>(tagsJson)
                    ?.Where(tag => !string.IsNullOrWhiteSpace(tag))
                    .Select(tag => tag.Trim())
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .ToList() ?? new List<string>();
            }
            catch (JsonException)
            {
                return Array.Empty<string>();
            }
        }

        private static string SnapshotKey(string value)
        {
            string key = (value ?? string.Empty).Trim();
            return string.IsNullOrWhiteSpace(key) ? "Unknown" : key;
        }

        private static IList<DynamicQuestSeedDefinition> BuildStoryCachePrefillDefinitions(
            IList<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedOptions options)
        {
            List<DynamicQuestSeedDefinition> definitions = new(options.Definitions ?? Array.Empty<DynamicQuestSeedDefinition>());

            if (!Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED)
                return definitions;

            int maxWorldCandidates = StoryCacheWorldPrefillMaxCandidates();
            if (maxWorldCandidates <= 0)
                return definitions;

            HashSet<string> seenDefinitions = definitions
                .Select(DefinitionFingerprint)
                .ToHashSet(StringComparer.OrdinalIgnoreCase);
            HashSet<string> configuredTargets = definitions
                .Where(definition => !string.IsNullOrWhiteSpace(definition.TargetName))
                .Select(definition => TargetFingerprint(definition.RegionId, definition.TargetName))
                .ToHashSet(StringComparer.OrdinalIgnoreCase);
            HashSet<string> configuredStartNames = definitions
                .Where(definition => !string.IsNullOrWhiteSpace(definition.StartNpcName))
                .Select(definition => definition.StartNpcName.Trim())
                .ToHashSet(StringComparer.OrdinalIgnoreCase);

            List<DynamicQuestSeedDefinition> growthBranchCandidates = NpcsOrEmpty(npcs)
                .Where(IsGrowthBranchWorldTarget)
                .Where(npc => npc.RegionId > 0)
                .Where(npc => IsStarterRealm(RealmNameForRegion(npc.RegionId)))
                .Where(npc => HasLikelyGrowthQuestGiver(npcs, npc.RegionId))
                .Where(npc => !configuredTargets.Contains(TargetFingerprint(npc.RegionId, npc.Name)))
                .GroupBy(npc => TargetFingerprint(npc.RegionId, npc.Name), StringComparer.OrdinalIgnoreCase)
                .Select(group => group
                    .OrderByDescending(npc => Math.Clamp(EffectiveQuestLevel(npc), 1, 50))
                    .ThenByDescending(npc => npc.GrowthScore)
                    .ThenBy(npc => npc.Name, StringComparer.OrdinalIgnoreCase)
                    .ThenBy(npc => npc.InternalID, StringComparer.OrdinalIgnoreCase)
                    .First())
                .Select(CreateGrowthBranchPrefillDefinition)
                .Where(definition => definition != null)
                .Where(definition => seenDefinitions.Add(DefinitionFingerprint(definition)))
                .OrderBy(definition => RealmSortKey(RealmNameForRegion(definition.RegionId)))
                .ThenBy(definition => definition.RegionId)
                .ThenBy(definition => definition.TargetName, StringComparer.OrdinalIgnoreCase)
                .ToList();
            HashSet<string> growthBranchTargets = growthBranchCandidates
                .Select(definition => TargetFingerprint(definition.RegionId, definition.TargetName))
                .ToHashSet(StringComparer.OrdinalIgnoreCase);

            int maxGrowthBranchCandidates = GrowthBranchPrefillSlotLimit(maxWorldCandidates);
            int addedWorldCandidates = 0;
            foreach (DynamicQuestSeedDefinition definition in RoundRobinByRealm(growthBranchCandidates).Take(maxGrowthBranchCandidates))
            {
                definitions.Add(definition);
                addedWorldCandidates++;
            }

            int remainingWorldCandidates = Math.Max(0, maxWorldCandidates - addedWorldCandidates);
            if (remainingWorldCandidates <= 0)
                return definitions;

            List<DynamicQuestSeedDefinition> worldCandidates = NpcsOrEmpty(npcs)
                .Where(IsLikelyWorldPrefillAutoAcceptTarget)
                .Where(npc => npc.RegionId > 0)
                .Where(npc => IsStarterRealm(RealmNameForRegion(npc.RegionId)))
                .Where(IsSafeWorldPrefillLevel)
                .Where(npc => !configuredStartNames.Contains(npc.Name ?? string.Empty))
                .Where(npc => !configuredTargets.Contains(TargetFingerprint(npc.RegionId, npc.Name)))
                .Where(npc => !growthBranchTargets.Contains(TargetFingerprint(npc.RegionId, npc.Name)))
                .GroupBy(npc => TargetFingerprint(npc.RegionId, npc.Name), StringComparer.OrdinalIgnoreCase)
                .Select(group => group
                    .OrderBy(npc => Math.Clamp(EffectiveQuestLevel(npc) <= 0 ? 1 : EffectiveQuestLevel(npc), 1, 50))
                    .ThenBy(npc => npc.Name, StringComparer.OrdinalIgnoreCase)
                    .ThenBy(npc => npc.InternalID, StringComparer.OrdinalIgnoreCase)
                    .First())
                .Select(CreateWorldPrefillDefinition)
                .Where(definition => definition != null)
                .Where(definition => seenDefinitions.Add(DefinitionFingerprint(definition)))
                .OrderBy(definition => RealmSortKey(RealmNameForRegion(definition.RegionId)))
                .ThenBy(definition => definition.RegionId)
                .ThenBy(definition => definition.TargetName, StringComparer.OrdinalIgnoreCase)
                .ToList();

            foreach (DynamicQuestSeedDefinition definition in RoundRobinByRealm(worldCandidates).Take(remainingWorldCandidates))
                definitions.Add(definition);

            return definitions;
        }

        private static List<string> BuildStoryCachePrefillPlanReasons(
            DynamicQuestSeedOptions options,
            int scannedNpcs,
            int totalCandidates,
            int worldCandidates,
            bool canGenerate)
        {
            List<string> reasons = new();
            if (options == null || !options.Enabled)
                reasons.Add("seed_disabled");
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED)
                reasons.Add("dynamic_quest_disabled");
            if (options == null || (!options.UseLlm && !options.UseCodexCuratedStories))
                reasons.Add("llm_disabled");
            if (StoryCachePrefillBatchSize() <= 0)
                reasons.Add("prefill_batch_disabled");
            if (!Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED)
                reasons.Add("world_prefill_disabled");
            if (StoryCacheWorldPrefillMaxCandidates() <= 0)
                reasons.Add("world_prefill_max_candidates_zero");
            if (!canGenerate)
                reasons.Add("story_cache_full");
            if (scannedNpcs <= 0)
                reasons.Add("no_usable_npcs");
            if (totalCandidates <= 0)
                reasons.Add("no_prefill_candidates");
            if (Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED &&
                scannedNpcs > 0 &&
                worldCandidates <= 0)
                reasons.Add("no_world_candidates");

            return reasons;
        }

        private static DynamicQuestStoryCachePrefillCandidate BuildStoryCachePrefillCandidate(DynamicQuestSeedDefinition definition)
        {
            return new DynamicQuestStoryCachePrefillCandidate
            {
                StartNpcName = definition?.StartNpcName ?? string.Empty,
                RegionId = definition?.RegionId ?? 0,
                Realm = RealmNameForRegion(definition?.RegionId ?? 0),
                TargetName = definition?.TargetName ?? string.Empty,
                Count = Math.Max(1, definition?.Count ?? 1),
                MinLevel = Math.Max(1, definition?.MinLevel ?? 1),
                MaxLevel = Math.Max(1, definition?.MaxLevel ?? 50),
                StartMode = (definition?.StartMode ?? DynamicQuestStartMode.NpcOffer).ToString(),
                BranchWorldSignal = ResolveBranchWorldSignal(definition, definition?.RegionId ?? 0)
            };
        }

        private static DynamicQuestSeedDefinition CreateWorldPrefillDefinition(DynamicQuestSeedNpc npc)
        {
            if (npc == null || string.IsNullOrWhiteSpace(npc.Name))
                return null;

            int level = Math.Clamp(EffectiveQuestLevel(npc) <= 0 ? 1 : EffectiveQuestLevel(npc), 1, 50);
            int minLevel = Math.Max(1, level - 2);
            int maxLevel = Math.Min(50, level + 2);
            bool useNpcOffer = ShouldUseNpcOfferForWorldPrefill(level);

            return new DynamicQuestSeedDefinition
            {
                StartNpcName = useNpcOffer ? "selector:quest-giver" : string.Empty,
                RegionId = npc.RegionId,
                TargetName = npc.Name.Trim(),
                Count = useNpcOffer ? 1 : level <= 5 ? 1 : level <= 20 ? 2 : 3,
                MinLevel = minLevel,
                MaxLevel = maxLevel,
                StartMode = useNpcOffer ? DynamicQuestStartMode.NpcOffer : DynamicQuestStartMode.AutoAccept,
                Trigger = useNpcOffer ? string.Empty : BuildWorldPrefillTrigger(npc.RegionId),
                StartSelector = useNpcOffer ? "quest-giver" : string.Empty,
                BranchWorldSignal = BuildWorldPrefillBranchWorldSignal(npc.RegionId)
            };
        }

        private static bool ShouldUseNpcOfferForWorldPrefill(int level)
        {
            return level >= 36;
        }

        private static bool IsSafeWorldPrefillLevel(DynamicQuestSeedNpc npc)
        {
            int level = Math.Clamp(EffectiveQuestLevel(npc) <= 0 ? 1 : EffectiveQuestLevel(npc), 1, 50);
            return level <= 35;
        }

        private static int GrowthBranchPrefillSlotLimit(int maxWorldCandidates)
        {
            if (maxWorldCandidates <= 1)
                return Math.Max(0, maxWorldCandidates);

            return Math.Max(1, maxWorldCandidates / 2);
        }

        private static DynamicQuestSeedDefinition CreateGrowthBranchPrefillDefinition(DynamicQuestSeedNpc npc)
        {
            if (npc == null || string.IsNullOrWhiteSpace(npc.Name))
                return null;

            int level = Math.Clamp(EffectiveQuestLevel(npc) <= 0 ? 1 : EffectiveQuestLevel(npc), 1, 50);
            return new DynamicQuestSeedDefinition
            {
                StartNpcName = "selector:quest-giver",
                RegionId = npc.RegionId,
                TargetName = npc.Name.Trim(),
                Count = 1,
                MinLevel = Math.Max(1, level - 1),
                MaxLevel = Math.Min(50, level + 1),
                StartMode = DynamicQuestStartMode.NpcOffer,
                Trigger = string.Empty,
                StartSelector = "quest-giver",
                BranchWorldSignal = BuildMobGrowthRegionSignal(npc.RegionId)
            };
        }

        private static bool IsGrowthBranchWorldTarget(DynamicQuestSeedNpc npc)
        {
            if (!IsLikelyWorldQuestTarget(npc) || !npc.HasGrowthState)
                return false;

            int effectiveLevel = EffectiveQuestLevel(npc);
            return npc.GrowthScore > 0 ||
                   npc.GrowthLevel > 0 ||
                   npc.GrowthPlayerKills > 0 ||
                   npc.GrowthIsMutant ||
                   npc.GrowthMutationPending ||
                   effectiveLevel > Math.Max(0, npc.Level) ||
                   (!string.IsNullOrWhiteSpace(npc.GrowthStage) &&
                    !string.Equals(npc.GrowthStage, MobGrowthStages.Normal, StringComparison.OrdinalIgnoreCase));
        }

        private static bool HasLikelyGrowthQuestGiver(IEnumerable<DynamicQuestSeedNpc> npcs, ushort regionId)
        {
            return NpcsOrEmpty(npcs).Any(npc =>
                npc != null &&
                npc.RegionId == regionId &&
                IsLikelyDynamicQuestStartNpc(npc));
        }

        private static IEnumerable<DynamicQuestSeedDefinition> RoundRobinByRealm(IList<DynamicQuestSeedDefinition> candidates)
        {
            if (candidates == null || candidates.Count == 0)
                yield break;

            Dictionary<string, Queue<DynamicQuestSeedDefinition>> queues = candidates
                .GroupBy(definition => RealmNameForRegion(definition.RegionId), StringComparer.OrdinalIgnoreCase)
                .ToDictionary(
                    group => group.Key,
                    group => new Queue<DynamicQuestSeedDefinition>(group),
                    StringComparer.OrdinalIgnoreCase);
            string[] order = { "Albion", "Midgard", "Hibernia", "Unknown" };

            while (queues.Values.Any(queue => queue.Count > 0))
            {
                foreach (string realm in order)
                {
                    if (!queues.TryGetValue(realm, out Queue<DynamicQuestSeedDefinition> queue) || queue.Count == 0)
                        continue;

                    yield return queue.Dequeue();
                }
            }
        }

        internal static bool IsLikelyWorldQuestTarget(DynamicQuestSeedNpc npc)
        {
            if (npc == null || string.IsNullOrWhiteSpace(npc.Name) || string.IsNullOrWhiteSpace(npc.InternalID))
                return false;

            if (npc.Level <= 0 || npc.Level >= 75)
                return false;

            if (!npc.HasSourceNpcMetadata)
                return true;

            return npc.SourceIsAlive &&
                   npc.SourceRealm == eRealm.None &&
                   !npc.SourceFlags.HasFlag(GameNPC.eFlags.PEACE) &&
                   !npc.SourceFlags.HasFlag(GameNPC.eFlags.CANTTARGET);
        }

        private static bool IsLikelyWorldPrefillAutoAcceptTarget(DynamicQuestSeedNpc npc)
        {
            if (!IsLikelyWorldQuestTarget(npc))
                return false;

            if (!npc.HasSourceNpcMetadata ||
                !IsLikelyProperNameTarget(npc.Name) ||
                npc.HasGrowthState)
            {
                return true;
            }

            return npc.SourceAggroLevel > 0 || npc.SourceAggroRange > 0;
        }

        private static bool IsLikelyProperNameTarget(string name)
        {
            string[] tokens = (name ?? string.Empty)
                .Trim()
                .Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
            if (tokens.Length == 0)
                return false;

            if (tokens.Length == 1)
                return IsTitleCaseToken(tokens[0]);

            return tokens.Any(IsTitleCaseToken);
        }

        private static bool IsTitleCaseToken(string token)
        {
            token = (token ?? string.Empty).Trim();
            return token.Length >= 3 &&
                   char.IsLetter(token[0]) &&
                   char.IsUpper(token[0]) &&
                   token.Skip(1).Any(char.IsLower);
        }

        private static bool IsLikelyQuestGiver(DynamicQuestSeedNpc npc)
        {
            if (npc == null)
                return false;

            if (IsLikelyAmbientNpcName(npc.Name))
                return false;

            if (IsDisallowedQuestGiverName(npc.Name))
                return false;

            if (npc.Level <= 0)
                return false;

            if (npc.HasSourceNpcMetadata)
            {
                if (IsLikelyWorldQuestTarget(npc))
                    return false;

                if (IsDisallowedQuestGiverType(npc.SourceTypeName))
                    return false;

                if (IsLikelyServiceNpcType(npc.SourceTypeName))
                    return true;

                return npc.SourceRealm != eRealm.None &&
                       npc.SourceFlags.HasFlag(GameNPC.eFlags.PEACE) &&
                       npc.Level >= 20;
            }

            return npc.Level >= 20;
        }

        internal static bool IsLikelyDynamicQuestStartNpc(DynamicQuestSeedNpc npc)
        {
            if (!IsLikelyQuestGiver(npc))
                return false;

            return npc == null ||
                   !npc.HasSourceNpcMetadata ||
                   !IsLikelyServiceNpcType(npc.SourceTypeName);
        }

        private static bool IsLikelyAmbientNpcName(string name)
        {
            string value = (name ?? string.Empty).Trim();
            return value.StartsWith("ambient ", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsDisallowedQuestGiverName(string name)
        {
            string value = (name ?? string.Empty).Trim();
            return string.Equals(value, "horse", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "pony", StringComparison.OrdinalIgnoreCase) ||
                   value.EndsWith(" horse", StringComparison.OrdinalIgnoreCase) ||
                   value.EndsWith(" pony", StringComparison.OrdinalIgnoreCase);
        }

        private static bool StartSelectorRequiresQuestGiver(string selector)
        {
            return NormalizeSelector(selector) is "town-npc" or "quest-giver" or "npc";
        }

        private static bool IsDisallowedQuestGiverType(string typeName)
        {
            if (string.IsNullOrWhiteSpace(typeName))
                return false;

            string value = typeName.Trim();
            return string.Equals(value, "GameGuard", StringComparison.OrdinalIgnoreCase) ||
                   value.EndsWith(".GameGuard", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsLikelyServiceNpcType(string typeName)
        {
            if (string.IsNullOrWhiteSpace(typeName))
                return false;

            return typeName.Contains("Merchant", StringComparison.OrdinalIgnoreCase) ||
                   typeName.Contains("Hastener", StringComparison.OrdinalIgnoreCase) ||
                   typeName.Contains("Buff", StringComparison.OrdinalIgnoreCase) ||
                   typeName.Contains("Healer", StringComparison.OrdinalIgnoreCase) ||
                   typeName.Contains("Trainer", StringComparison.OrdinalIgnoreCase) ||
                   typeName.Contains("Stable", StringComparison.OrdinalIgnoreCase) ||
                   typeName.Contains("Teleporter", StringComparison.OrdinalIgnoreCase) ||
                   typeName.Contains("Channeler", StringComparison.OrdinalIgnoreCase);
        }

        private static string DefinitionFingerprint(DynamicQuestSeedDefinition definition)
        {
            if (definition == null)
                return string.Empty;

            return string.Join("|", new[]
            {
                definition.StartNpcName ?? string.Empty,
                definition.StartSelector ?? string.Empty,
                definition.RegionId.ToString(),
                definition.TargetName ?? string.Empty,
                definition.TargetSelector ?? string.Empty,
                Math.Max(1, definition.Count).ToString(),
                Math.Clamp(definition.MinLevel, 1, 50).ToString(),
                Math.Clamp(Math.Max(definition.MaxLevel, definition.MinLevel), 1, 50).ToString(),
                definition.StartMode.ToString(),
                definition.Trigger ?? string.Empty,
                ResolveBranchWorldSignal(definition, definition.RegionId)
            }).ToLowerInvariant();
        }

        private static string TargetFingerprint(ushort regionId, string targetName)
        {
            return $"{regionId}|{(targetName ?? string.Empty).Trim()}".ToLowerInvariant();
        }

        private static string TargetFamilyFingerprint(ushort regionId, string targetName)
        {
            string value = (targetName ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(value))
                return string.Empty;

            string firstToken = value
                .Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries)
                .FirstOrDefault() ?? string.Empty;
            firstToken = firstToken.Trim();
            return firstToken.Length >= 5 && !IsGenericTargetFamilyToken(firstToken)
                ? $"{regionId}|{firstToken}".ToLowerInvariant()
                : string.Empty;
        }

        private static bool IsGenericTargetFamilyToken(string token)
        {
            string value = (token ?? string.Empty).Trim();
            return string.Equals(value, "aged", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "ancient", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "elder", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "great", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "greater", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "large", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "lesser", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "old", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "veteran", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "young", StringComparison.OrdinalIgnoreCase);
        }

        private static string NormalizeSelector(string selector)
        {
            return (selector ?? string.Empty).Trim().ToLowerInvariant();
        }

        private static string BuildMobGrowthRegionSignal(ushort regionId)
        {
            return regionId > 0
                ? $"mob-growth:killed:region:{regionId}"
                : "mob-growth:killed";
        }

        private static string NormalizeBranchWorldSignal(string value)
        {
            value = (value ?? string.Empty).Trim().ToLowerInvariant();
            return DynamicQuestWorldSignalPolicy.IsAllowed(value) ? value : string.Empty;
        }

        private static string ResolveBranchWorldSignal(DynamicQuestSeedDefinition definition, ushort targetRegion)
        {
            string explicitSignal = NormalizeBranchWorldSignal(definition?.BranchWorldSignal);
            if (IsMobGrowthSignal(explicitSignal) && !Properties.WORLDAI_MOB_GROWTH_ENABLED)
                return string.Empty;

            if (!string.IsNullOrWhiteSpace(explicitSignal))
                return explicitSignal;

            if (!ShouldAttachDefaultMobGrowthBranch(definition, targetRegion))
                return string.Empty;

            return BuildMobGrowthRegionSignal(targetRegion);
        }

        private static bool ShouldAttachDefaultMobGrowthBranch(DynamicQuestSeedDefinition definition, ushort targetRegion)
        {
            return definition != null &&
                   Properties.WORLDAI_MOB_GROWTH_ENABLED &&
                   targetRegion > 0 &&
                   !string.IsNullOrWhiteSpace(definition.TargetSelector);
        }

        private static string ExtractBranchWorldSignal(IEnumerable<string> tags)
        {
            const string prefix = "world-signal:";
            foreach (string tag in tags ?? Array.Empty<string>())
            {
                string value = (tag ?? string.Empty).Trim();
                if (!value.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                    continue;

                string signal = NormalizeBranchWorldSignal(value.Substring(prefix.Length));
                if (!string.IsNullOrWhiteSpace(signal))
                    return signal;
            }

            return string.Empty;
        }

        private static string ExtractStoryArchetype(IEnumerable<string> tags)
        {
            const string prefix = "story-archetype:";
            foreach (string tag in tags ?? Array.Empty<string>())
            {
                string value = (tag ?? string.Empty).Trim();
                if (!value.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                    continue;

                string archetype = value.Substring(prefix.Length).Trim();
                if (!string.IsNullOrWhiteSpace(archetype))
                    return archetype;
            }

            return string.Empty;
        }

        private IEnumerable<DbDynamicQuestTemplate> GetActiveStoryCacheRows()
        {
            return (m_templateRepository.GetActive() ?? Array.Empty<DbDynamicQuestTemplate>())
                .Where(IsActiveStoryCacheRow);
        }

        private static bool IsActiveStoryCacheRow(DbDynamicQuestTemplate row)
        {
            return row != null &&
                   row.IsActive &&
                   (!string.IsNullOrWhiteSpace(row.StoryProvider) ||
                    (row.TagsJson ?? string.Empty).Contains("llm-story", StringComparison.OrdinalIgnoreCase));
        }

        private static DateTime EffectiveLastUsed(DbDynamicQuestTemplate row)
        {
            if (row.StoryLastUsedAt > DateTime.MinValue)
                return row.StoryLastUsedAt;
            if (row.UpdatedAt > DateTime.MinValue)
                return row.UpdatedAt;
            return row.CreatedAt;
        }

        private static int StoryCacheMaxTemplates()
        {
            return Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_MAX_TEMPLATES > 0
                ? Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_MAX_TEMPLATES
                : 500;
        }

        private static int StoryCachePruneCount()
        {
            return Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PRUNE_COUNT > 0
                ? Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PRUNE_COUNT
                : 50;
        }

        private static int StoryCachePrefillBatchSize()
        {
            return Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE > 0
                ? Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE
                : 5;
        }

        private static int StoryCacheWorldPrefillMaxCandidates()
        {
            return Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_MAX_CANDIDATES > 0
                ? Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_MAX_CANDIDATES
                : 60;
        }

        private static DateTime UtcNow()
        {
            DateTime now = s_utcNow();
            return now.Kind == DateTimeKind.Utc
                ? now
                : now.ToUniversalTime();
        }

        private static DynamicQuestStoryRequest BuildStoryRequest(
            DynamicQuestTemplate template,
            DynamicQuestSeedOptions options)
        {
            return new DynamicQuestStoryRequest
            {
                TemplateId = template.TemplateId,
                Realm = template.Realm,
                StartNpcName = template.PreferredStartNpcName,
                RegionId = template.PreferredRegionId,
                TargetName = template.TargetNameHint,
                Count = template.Count,
                MinLevel = template.MinLevel,
                MaxLevel = template.MaxLevel,
                StorySeed = BuildLlmSeed(options, new DynamicQuestSeedDefinition
                {
                    StartNpcName = template.PreferredStartNpcName,
                    RegionId = template.PreferredRegionId,
                    TargetName = template.TargetNameHint,
                    Count = template.Count,
                    MinLevel = template.MinLevel,
                    MaxLevel = template.MaxLevel,
                    StartMode = template.StartMode,
                    Trigger = template.Trigger,
                    BranchWorldSignal = ExtractBranchWorldSignal(template.Tags)
                })
            };
        }

        private static IList<string> MergeTags(IList<string> first, IList<string> second)
        {
            return (first ?? Array.Empty<string>())
                .Concat(second ?? Array.Empty<string>())
                .Where(tag => !string.IsNullOrWhiteSpace(tag))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();
        }

        private static void CopyTemplateRow(DbDynamicQuestTemplate source, DbDynamicQuestTemplate target)
        {
            target.Title = source.Title;
            target.StorySeed = source.StorySeed;
            target.OfferText = source.OfferText;
            target.ProgressText = source.ProgressText;
            target.FinishText = source.FinishText;
            target.Realm = source.Realm;
            target.PreferredStartNpcName = source.PreferredStartNpcName;
            target.PreferredRegionId = source.PreferredRegionId;
            target.TargetNameHint = source.TargetNameHint;
            target.Count = source.Count;
            target.MinLevel = source.MinLevel;
            target.MaxLevel = source.MaxLevel;
            target.Source = source.Source;
            target.TagsJson = source.TagsJson;
            target.StoryProvider = source.StoryProvider;
            target.StoryModel = source.StoryModel;
            target.StoryQualityScore = source.StoryQualityScore;
            target.StoryQualityJson = source.StoryQualityJson;
            target.StoryNarrativeJson = source.StoryNarrativeJson;
            target.StoryPresentationJson = source.StoryPresentationJson;
            target.StoryGeneratedAt = source.StoryGeneratedAt;
            target.StoryLastUsedAt = source.StoryLastUsedAt;
            target.StartMode = source.StartMode;
            target.Trigger = source.Trigger;
            target.StartNpcInternalId = source.StartNpcInternalId;
            target.LastBindingKey = source.LastBindingKey;
            target.UpdatedAt = source.UpdatedAt;
        }

        private static bool IsTemplateBindingSkip(string message)
        {
            return !string.IsNullOrWhiteSpace(message) &&
                   (message.StartsWith("start npc not found for template:", StringComparison.OrdinalIgnoreCase) ||
                    message.StartsWith("target npc not found for template:", StringComparison.OrdinalIgnoreCase));
        }

        private static bool IsTemplateTargetMissing(string message)
        {
            return !string.IsNullOrWhiteSpace(message) &&
                   message.StartsWith("target npc not found for template:", StringComparison.OrdinalIgnoreCase);
        }

        private static DynamicQuestTemplate BuildTemplate(
            DynamicQuestSeedNpc npc,
            DynamicQuestSeedNpc targetNpc,
            DynamicQuestSeedDefinition definition,
            string worldRevision)
        {
            ushort targetRegion = TargetRegion(npc, definition);
            string realm = RealmNameForRegion(targetRegion);
            return new DynamicQuestTemplate
            {
                TemplateId = BuildStableQuestId(npc, definition),
                Title = "{{target}} 처치 요청",
                StorySeed = "{{target}} 때문에 이 근처가 어수선합니다.",
                OfferText = "{{target}} 때문에 이 근처가 어수선합니다. {{count}}마리만 처리해 주시겠습니까?",
                ProgressText = "아직 {{target}} 위협이 남아 있습니다.",
                FinishText = "좋습니다. 덕분에 이 지역이 한결 안전해졌습니다.",
                Realm = realm,
                PreferredStartNpcName = RequiresStartNpc(definition) ? npc.Name ?? string.Empty : definition.StartNpcName ?? string.Empty,
                PreferredRegionId = targetRegion,
                TargetNameHint = definition.TargetName,
                Count = definition.Count,
                MinLevel = definition.MinLevel,
                MaxLevel = definition.MaxLevel,
                Source = "auto_seed",
                StartMode = definition.StartMode,
                Trigger = definition.Trigger ?? string.Empty,
                WorldRevision = worldRevision,
                Tags = BuildTemplateTags(definition, realm, targetRegion),
                PreferredStartNpcInternalId = npc?.InternalID ?? string.Empty,
                PreferredTargetNpcInternalId = targetNpc?.InternalID ?? string.Empty
            };
        }

        private static IList<string> BuildTemplateTags(
            DynamicQuestSeedDefinition definition,
            string realm,
            ushort targetRegion)
        {
            List<string> tags = new()
            {
                $"realm:{realm}",
                $"region:{targetRegion}",
                $"target:{definition.TargetName}",
                $"start-mode:{definition.StartMode}",
                "llm-ready"
            };
            if (IsStarterBand(definition))
                tags.Insert(0, "starter");

            if (!string.IsNullOrWhiteSpace(definition.StartSelector))
                tags.Add($"selector:start:{NormalizeSelector(definition.StartSelector)}");
            if (!string.IsNullOrWhiteSpace(definition.TargetSelector))
                tags.Add($"selector:target:{NormalizeSelector(definition.TargetSelector)}");

            string branchWorldSignal = ResolveBranchWorldSignal(definition, targetRegion);
            if (!string.IsNullOrWhiteSpace(branchWorldSignal))
            {
                tags.Add(BranchTagForWorldSignal(branchWorldSignal));
                tags.Add($"world-signal:{branchWorldSignal}");
            }

            return tags;
        }

        private static string BranchTagForWorldSignal(string signal)
        {
            signal = (signal ?? string.Empty).Trim().ToLowerInvariant();
            if (signal.StartsWith("mob-growth:", StringComparison.OrdinalIgnoreCase))
                return "branch:mob-growth";
            if (signal.StartsWith("time-window", StringComparison.OrdinalIgnoreCase))
                return "branch:time-window";
            if (signal.StartsWith("item-acquired", StringComparison.OrdinalIgnoreCase))
                return "branch:item-acquired";
            if (signal.StartsWith("region-entered", StringComparison.OrdinalIgnoreCase) ||
                signal.StartsWith("region:", StringComparison.OrdinalIgnoreCase))
            {
                return "branch:region-entered";
            }

            return "branch:world-signal";
        }

        private static string BuildWorldPrefillTrigger(ushort regionId)
        {
            return RealmNameForRegion(regionId) switch
            {
                "Midgard" => "time-window",
                "Unknown" => "time-window",
                _ => string.Empty
            };
        }

        private static string BuildWorldPrefillBranchWorldSignal(ushort regionId)
        {
            return RealmNameForRegion(regionId) switch
            {
                "Midgard" => "time-window",
                "Hibernia" => "item-acquired",
                "Unknown" => "time-window",
                _ => BuildMobGrowthRegionSignal(regionId)
            };
        }

        private static IEnumerable<DynamicQuestSeedNpc> NpcsOrEmpty(IEnumerable<DynamicQuestSeedNpc> npcs)
        {
            return npcs ?? Array.Empty<DynamicQuestSeedNpc>();
        }

        private static ushort TargetRegion(DynamicQuestSeedNpc startNpc, DynamicQuestSeedDefinition definition)
        {
            return definition.RegionId > 0 ? definition.RegionId : startNpc?.RegionId ?? (ushort)0;
        }

        private static DynamicQuestDefinition BuildQuest(DynamicQuestSeedNpc npc, DynamicQuestSeedNpc targetNpc, DynamicQuestSeedDefinition definition)
        {
            return new DynamicQuestDefinition
            {
                Id = BuildStableQuestId(npc, definition),
                Title = $"{definition.TargetName} 처치 요청",
                OfferText = $"{definition.TargetName} 때문에 이 근처가 어수선합니다. {definition.Count}마리만 처리해 주시겠습니까?",
                ProgressText = $"아직 {definition.TargetName} 위협이 남아 있습니다.",
                FinishText = "좋습니다. 덕분에 이 지역이 한결 안전해졌습니다.",
                StartNpcInternalId = npc.InternalID ?? string.Empty,
                StartNpcName = npc.Name ?? string.Empty,
                StartRegionId = npc.RegionId,
                StepType = DynamicQuestStepType.Kill,
                TargetName = definition.TargetName,
                TargetCount = definition.Count,
                MinLevel = definition.MinLevel,
                MaxLevel = definition.MaxLevel,
                StartNodeId = "talk",
                Nodes = BuildStarterGraph(npc, targetNpc, definition),
                Reward = new DynamicQuestRewardDefinition
                {
                    XpMultiplier = 1.0,
                    MoneyMultiplier = 1.0,
                    StepBonusMultiplier = 0.25,
                    PartyBonusMultiplier = 1.0
                },
                Tags = BuildRuntimeQuestTags(definition, TargetRegion(npc, definition))
            };
        }

        private static IList<string> BuildRuntimeQuestTags(DynamicQuestSeedDefinition definition, ushort targetRegion)
        {
            List<string> tags = new()
            {
                $"realm:{RealmNameForRegion(targetRegion)}",
                $"region:{targetRegion}",
                $"target:{definition.TargetName}",
                "llm-ready"
            };
            if (IsStarterBand(definition))
                tags.Insert(0, "starter");

            return tags;
        }

        private static void IncrementRealm(IDictionary<string, int> counters, string realm)
        {
            realm = string.IsNullOrWhiteSpace(realm) ? "Unknown" : realm;
            if (!counters.ContainsKey(realm))
                counters[realm] = 0;

            counters[realm]++;
        }

        private static bool IsStarterRealm(string realm)
        {
            return string.Equals(realm, "Albion", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(realm, "Midgard", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(realm, "Hibernia", StringComparison.OrdinalIgnoreCase);
        }

        private static string RealmNameForRegion(ushort regionId)
        {
            return regionId switch
            {
                >= 1 and < 100 => "Albion",
                >= 100 and < 200 => "Midgard",
                >= 200 and < 300 => "Hibernia",
                _ => "Unknown"
            };
        }

        private static int RealmSortKey(string realm)
        {
            return realm switch
            {
                "Albion" => 0,
                "Midgard" => 1,
                "Hibernia" => 2,
                _ => 3
            };
        }

        private static string BuildStableQuestId(DynamicQuestSeedNpc npc, DynamicQuestSeedDefinition definition)
        {
            ushort targetRegion = TargetRegion(npc, definition);
            string startSelector = NormalizeSelector(definition.StartSelector);
            string targetSelector = NormalizeSelector(definition.TargetSelector);
            if (!string.IsNullOrWhiteSpace(startSelector) || !string.IsNullOrWhiteSpace(targetSelector))
            {
                string rawSelector = string.Join("|", new[]
                {
                    "seed-selector",
                    targetRegion.ToString(),
                    $"start:{startSelector}",
                    $"target:{(string.IsNullOrWhiteSpace(targetSelector) ? definition.TargetName ?? string.Empty : targetSelector)}",
                    Math.Max(1, definition.Count).ToString(),
                    Math.Clamp(definition.MinLevel, 1, 50).ToString(),
                    Math.Clamp(Math.Max(definition.MaxLevel, definition.MinLevel), 1, 50).ToString(),
                    definition.StartMode.ToString(),
                    definition.Trigger ?? string.Empty,
                    ResolveBranchWorldSignal(definition, targetRegion)
                }).ToLowerInvariant();
                byte[] selectorHash = SHA256.HashData(Encoding.UTF8.GetBytes(rawSelector));
                string selectorSuffix = Convert.ToHexString(selectorHash).Substring(0, 16).ToLowerInvariant();
                return $"seed-{targetRegion}-{selectorSuffix}";
            }

            string raw = RequiresStartNpc(definition)
                ? string.Join("|", new[]
                {
                    "seed",
                    npc?.RegionId.ToString() ?? string.Empty,
                    npc?.InternalID ?? string.Empty,
                    npc?.Name ?? string.Empty,
                    targetRegion.ToString(),
                    definition.TargetName ?? string.Empty,
                    definition.Count.ToString(),
                    definition.MinLevel.ToString(),
                    definition.MaxLevel.ToString(),
                    ResolveBranchWorldSignal(definition, targetRegion)
                }).ToLowerInvariant()
                : string.Join("|", new[]
                {
                    "seed-world",
                    targetRegion.ToString(),
                    definition.TargetName ?? string.Empty,
                    definition.Count.ToString(),
                    definition.MinLevel.ToString(),
                    definition.MaxLevel.ToString(),
                    definition.StartMode.ToString(),
                    definition.Trigger ?? string.Empty,
                    ResolveBranchWorldSignal(definition, targetRegion)
                }).ToLowerInvariant();
            byte[] hash = SHA256.HashData(Encoding.UTF8.GetBytes(raw));
            string suffix = Convert.ToHexString(hash).Substring(0, 16).ToLowerInvariant();
            return $"seed-{targetRegion}-{suffix}";
        }

        private static bool RequiresStartNpc(DynamicQuestSeedDefinition definition)
        {
            return definition == null || definition.StartMode == DynamicQuestStartMode.NpcOffer;
        }

        private static IList<DynamicQuestNode> BuildStarterGraph(DynamicQuestSeedNpc npc, DynamicQuestSeedNpc targetNpc, DynamicQuestSeedDefinition definition)
        {
            ushort targetRegion = TargetRegion(npc, definition);
            string branchWorldSignal = ResolveBranchWorldSignal(definition, targetRegion);
            bool hasFollowupSignal = !string.IsNullOrWhiteSpace(branchWorldSignal);
            string followupNodeId = hasFollowupSignal ? "observe_signal" : "complete";
            List<DynamicQuestNode> nodes = new List<DynamicQuestNode>
            {
                new DynamicQuestNode
                {
                    Id = "talk",
                    Type = DynamicQuestNodeType.Talk,
                    Title = "부탁",
                    Text = $"{definition.TargetName} 때문에 이 근처가 어수선합니다.",
                    Objective = new DynamicQuestObjective
                    {
                        NpcInternalId = npc.InternalID,
                        NpcName = npc.Name,
                        RegionId = npc.RegionId
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge { ToNodeId = "explore", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
                    }
                },
                new DynamicQuestNode
                {
                    Id = "explore",
                    Type = DynamicQuestNodeType.Explore,
                    Title = "흔적 조사",
                    Text = $"{definition.TargetName} 흔적을 조사하세요.",
                    Objective = new DynamicQuestObjective
                    {
                        LocationName = $"{definition.TargetName} 흔적",
                        RegionId = targetRegion,
                        X = Math.Max(1, targetNpc?.X ?? 1),
                        Y = Math.Max(1, targetNpc?.Y ?? 1),
                        Z = Math.Max(0, targetNpc?.Z ?? 0),
                        Radius = 450
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge { ToNodeId = "kill", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
                    }
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
                        RegionId = targetRegion,
                        X = Math.Max(1, targetNpc?.X ?? 1),
                        Y = Math.Max(1, targetNpc?.Y ?? 1),
                        Z = Math.Max(0, targetNpc?.Z ?? 0),
                        Radius = 6500,
                        AllowGroupCredit = true
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge { ToNodeId = "return", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
                    }
                },
                new DynamicQuestNode
                {
                    Id = "return",
                    Type = DynamicQuestNodeType.ReturnToNpc,
                    Title = "보고",
                    Text = $"{npc.Name}에게 돌아가세요.",
                    Objective = new DynamicQuestObjective
                    {
                        NpcInternalId = npc.InternalID,
                        NpcName = npc.Name,
                        RegionId = npc.RegionId
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge { ToNodeId = "choice", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
                    }
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
                            new DynamicQuestChoice { Id = "safe", Label = "마을 안전을 우선한다", Text = "마을 안전을 우선한다.", Consequence = "지역 주민들은 당장의 위협에서 숨을 돌리지만, 남은 흔적은 경계 기록에 보존된다." },
                            new DynamicQuestChoice { Id = "followup", Label = "더 큰 위협을 추적한다", Text = "더 큰 위협을 추적한다.", Consequence = "눈앞의 평온보다 근원을 추적하기로 하며, 다음 세계 신호가 오기 전까지 긴장이 유지된다." }
                        }
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge { ToNodeId = followupNodeId, Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "safe", Priority = 0 },
                        new DynamicQuestEdge { ToNodeId = followupNodeId, Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "followup", Priority = 1 }
                    }
                },
            };
            if (hasFollowupSignal)
            {
                nodes.Add(new DynamicQuestNode
                {
                    Id = "observe_signal",
                    Type = DynamicQuestNodeType.Explore,
                    Title = BranchObservationTitle(branchWorldSignal),
                    Text = BranchObservationText(definition.TargetName, branchWorldSignal),
                    Objective = new DynamicQuestObjective
                    {
                        LocationName = BranchObservationLocation(definition.TargetName, branchWorldSignal),
                        RegionId = targetRegion,
                        X = Math.Max(1, targetNpc?.X ?? 1),
                        Y = Math.Max(1, targetNpc?.Y ?? 1),
                        Z = Math.Max(0, targetNpc?.Z ?? 0),
                        Radius = 650
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge
                        {
                            ToNodeId = "complete",
                            Condition = DynamicQuestEdgeCondition.WorldSignal,
                            ConditionValue = branchWorldSignal
                        },
                        new DynamicQuestEdge
                        {
                            ToNodeId = "complete",
                            Condition = DynamicQuestEdgeCondition.TimedOut,
                            ConditionValue = DynamicQuestWorldSignalPolicy.FallbackTimeoutSeconds,
                            Priority = 1
                        }
                    }
                });
            }

            nodes.Add(new DynamicQuestNode
            {
                Id = "complete",
                Type = DynamicQuestNodeType.Complete,
                Title = "완료",
                Text = "좋습니다. 덕분에 이 지역이 한결 안전해졌습니다."
            });

            return nodes;
        }

        private static string BranchObservationTitle(string branchWorldSignal)
        {
            string signal = (branchWorldSignal ?? string.Empty).Trim();
            if (signal.StartsWith("time-window", StringComparison.OrdinalIgnoreCase))
                return "시간의 징후 관측";
            if (signal.StartsWith("item-acquired", StringComparison.OrdinalIgnoreCase))
                return "단서 확보";
            if (signal.StartsWith("region-entered", StringComparison.OrdinalIgnoreCase) ||
                signal.StartsWith("region:", StringComparison.OrdinalIgnoreCase))
            {
                return "지역 정찰";
            }

            return "성장 위협 관측";
        }

        private static string BranchObservationText(string targetName, string branchWorldSignal)
        {
            string signal = (branchWorldSignal ?? string.Empty).Trim();
            if (signal.StartsWith("time-window", StringComparison.OrdinalIgnoreCase))
                return $"{targetName} 주변의 기척이 특정 시간대에 다시 흔들리는지 지켜보세요.";
            if (signal.StartsWith("item-acquired", StringComparison.OrdinalIgnoreCase))
                return $"{targetName} 흔적과 이어지는 단서를 확보하세요.";
            if (signal.StartsWith("region-entered", StringComparison.OrdinalIgnoreCase) ||
                signal.StartsWith("region:", StringComparison.OrdinalIgnoreCase))
            {
                return $"{targetName} 흔적이 이어진 지역으로 이동해 현장을 확인하세요.";
            }

            return $"{targetName} 주변에서 성장한 위협이 쓰러지는지 지켜보세요.";
        }

        private static string BranchObservationLocation(string targetName, string branchWorldSignal)
        {
            string signal = (branchWorldSignal ?? string.Empty).Trim();
            if (signal.StartsWith("time-window", StringComparison.OrdinalIgnoreCase))
                return $"{targetName} 시간 징후";
            if (signal.StartsWith("item-acquired", StringComparison.OrdinalIgnoreCase))
                return $"{targetName} 단서";
            if (signal.StartsWith("region-entered", StringComparison.OrdinalIgnoreCase) ||
                signal.StartsWith("region:", StringComparison.OrdinalIgnoreCase))
            {
                return $"{targetName} 현장 정찰";
            }

            return $"{targetName} 성장 징후";
        }

        private static string BuildLlmSeed(DynamicQuestSeedOptions options, DynamicQuestSeedDefinition definition)
        {
            string prefix = string.IsNullOrWhiteSpace(options.LlmSeed)
                ? "지역 분위기에 맞는 짧은 처치 의뢰"
                : options.LlmSeed.Trim();

            string branchWorldSignal = ResolveBranchWorldSignal(definition, definition.RegionId);
            string branchHint = string.IsNullOrWhiteSpace(branchWorldSignal)
                ? string.Empty
                : $" Optional follow-up branch waits for world signal: {branchWorldSignal}.";

            return $"{prefix}. Target hint: {definition.TargetName}. Level range: {definition.MinLevel}-{definition.MaxLevel}.{branchHint}";
        }

        private static string NormalizeWorldRevision(string worldRevision)
        {
            string value = (worldRevision ?? string.Empty).Trim();
            return string.IsNullOrWhiteSpace(value) ? "default" : value;
        }
    }
}
