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
        public int MissingNarrative { get; set; }
        public int MissingPresentation { get; set; }
        public int Returned { get; set; }
        public bool IncludeText { get; set; }
        public IDictionary<string, int> ByRealm { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IDictionary<string, int> ByProvider { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IDictionary<string, int> ByModel { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IDictionary<string, int> ByStartMode { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IDictionary<string, int> NotReadyByReason { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
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
        public int Count { get; set; }
        public int MinLevel { get; set; }
        public int MaxLevel { get; set; }
        public string Source { get; set; } = string.Empty;
        public IList<string> Tags { get; set; } = Array.Empty<string>();
        public string BranchWorldSignal { get; set; } = string.Empty;
        public string StoryProvider { get; set; } = string.Empty;
        public string StoryModel { get; set; } = string.Empty;
        public int StoryQualityScore { get; set; }
        public bool ReadyForUse { get; set; }
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
        private const int MaxNearbyStartCandidatesToEvaluate = 32;
        private const int MaxNearbyTargetCandidatesToRank = 16;
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

            if (options.UseLlm && options.UseStoryCacheOffers && summary.Created < Math.Max(1, options.MaxQuests))
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

            summary.CancelledStaleProgress = DynamicQuestRuntimeService.Instance
                .CancelActiveProgressForMissingRuntimeQuests("runtime_offer_removed");
            if (summary.CancelledStaleProgress > 0)
                summary.Messages.Add($"runtime removed stale active progress: {summary.CancelledStaleProgress}");

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

            if (!options.Enabled || !Properties.KDAOC_DYNAMIC_QUEST_ENABLED || !options.UseLlm)
                return summary;

            summary.StoryCachePrefilled = PrefillStoryCache(npcList, options, worldRevision, storyPrefillDefinitions, summary);
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
            IList<DynamicQuestSeedDefinition> candidates = BuildStoryCachePrefillDefinitions(npcList, options);
            int existingDefinitions = options.Definitions?.Count ?? 0;
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
                MissingNarrative = rows.Count(row => ParseStoryCacheNarrativeScenes(row.StoryNarrativeJson, includeText: false).Count == 0),
                MissingPresentation = rows.Count(row => ParseStoryCachePresentationBeats(row.StoryPresentationJson, includeText: false).Count == 0),
                Returned = items.Count,
                IncludeText = includeText,
                ByRealm = CountBy(rows, row => RealmNameForRegion(row.PreferredRegionId)),
                ByProvider = CountBy(rows, row => row.StoryProvider),
                ByModel = CountBy(rows, row => row.StoryModel),
                ByStartMode = CountBy(rows, row => ParseStoryCacheStartMode(row.StartMode).ToString()),
                NotReadyByReason = CountStoryCacheNotReadyReasons(rows),
                Items = items
            };
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
            return DynamicQuestRuntimeService.Instance.GetQuests().Any(quest =>
                string.Equals(quest.Id, templateId, StringComparison.OrdinalIgnoreCase) &&
                string.Equals(NormalizeWorldRevision(quest.WorldRevision), NormalizeWorldRevision(worldRevision), StringComparison.OrdinalIgnoreCase));
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
            return ContainsAny(normalized, "large ant", "dragon ant", "giant", "massive", "elder", "ancient", "raider", "brawler", "bandit", "nuisance");
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
                    template = DynamicQuestStoryService.ApplyStory(baseTemplate, generated.Story, generated.ProviderName, generated.ModelName);
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
            string target = "{{target}}";
            string startName = string.IsNullOrWhiteSpace(template?.PreferredStartNpcName)
                ? "지역 주민"
                : "{{start_npc}}";
            string speaker = string.IsNullOrWhiteSpace(template?.PreferredStartNpcName) ? "System" : "StartNpc";
            string location = RealmNameForRegion(template?.PreferredRegionId ?? 0);
            string realmName = string.Equals(location, "Unknown", StringComparison.OrdinalIgnoreCase)
                ? "마을 외곽"
                : "{{realm}}";
            string realmTexture = RealmTextureForStory(location);

            return new DynamicQuestStoryText
            {
                Title = string.IsNullOrWhiteSpace(template?.Title) || HasFallbackScaffoldTitle(template.Title)
                    ? $"{startName}의 {realmTexture} 경고"
                    : template.Title,
                OfferText = string.IsNullOrWhiteSpace(template?.OfferText)
                    ? $"{startName}이 {realmTexture} 근처에서 번지는 {target} 위협을 막아 달라고 부탁합니다."
                    : template.OfferText,
                ProgressText = string.IsNullOrWhiteSpace(template?.ProgressText)
                    ? $"{realmTexture}에 남은 {target}의 흔적을 따라가 위협을 제압하세요."
                    : template.ProgressText,
                FinishText = string.IsNullOrWhiteSpace(template?.FinishText)
                    ? $"{target} 위협이 사라지고 {realmTexture} 주변의 긴장이 잠시 풀립니다."
                    : template.FinishText,
                NarrativeScenes = new[]
                {
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "talk",
                        SceneType = "Intro",
                        Title = $"{realmTexture}의 낮은 경고",
                        Body = $"{startName}은 {realmName} {realmTexture} 가장자리에서 발견된 발자국과 찢긴 장비 조각을 보여 줍니다. {target}의 움직임은 단순한 소란이 아니라 통행로를 잠그기 시작한 징후입니다.",
                        JournalEntry = $"{startName}은 {realmTexture} 주변에서 {target} 위협이 커지고 있다고 기록해 달라고 했다.",
                        Mood = "urgent",
                        RevealPolicy = "FirstSeenOnly"
                    },
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "explore",
                        SceneType = "Discovery",
                        Title = $"{realmTexture}에 남은 자국",
                        Body = $"{realmTexture} 바닥에는 최근에 끌린 피 묻은 자국과 급히 꺼진 모닥불의 재가 남아 있습니다. {target}를 여기서 끊어내지 못하면 다음 피해자는 지나가던 정찰병이나 짐꾼이 될 것입니다.",
                        JournalEntry = $"{realmTexture}에서 {target}가 남긴 피해의 흔적을 확인했다.",
                        Mood = "ominous",
                        RevealPolicy = "FirstSeenOnly"
                    },
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "complete",
                        SceneType = "Completion",
                        Title = $"{realmTexture}의 짧은 숨",
                        Body = $"{target}를 쓰러뜨린 뒤 {realmTexture} 주변의 소음이 조금씩 돌아옵니다. {startName}은 이 평온이 오래가지 않을 수 있다는 것을 알면서도, 오늘 밤만큼은 사람들이 문을 덜 세게 걸어 잠글 것이라고 말합니다.",
                        JournalEntry = $"{target} 위협을 제압했고 {startName}은 {realmTexture} 주변의 경계를 늦추지 않겠다고 했다.",
                        Mood = "relieved",
                        RevealPolicy = "FirstSeenOnly"
                    }
                },
                PresentationBeats = new[]
                {
                    new DynamicQuestPresentationBeat
                    {
                        NodeId = "talk",
                        Trigger = "OnNpcInteract",
                        Speaker = speaker,
                        Text = $"{realmTexture} 쪽에서 돌아오지 못한 이들이 있습니다. 서둘러 주십시오.",
                        Emotion = "fear",
                        Emote = "Shiver"
                    },
                    new DynamicQuestPresentationBeat
                    {
                        NodeId = "complete",
                        Trigger = "OnComplete",
                        Speaker = speaker,
                        Text = $"{realmTexture}에 다시 발자국 소리가 들리는군요. 오늘 일은 잊지 않겠습니다.",
                        Emotion = "gratitude",
                        Emote = "Bow"
                    }
                }
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
            if (!tags.Any(tag => string.Equals(tag, "story-fallback", StringComparison.OrdinalIgnoreCase)))
                tags.Add("story-fallback");

            template.Tags = tags;
            template.Source = "fallback";
            template.StoryQualityScore = 0;
            template.StoryQualityJson = string.Empty;
            return template;
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

        private static bool HasFallbackScaffoldTitle(string title)
        {
            string value = title ?? string.Empty;
            string[] terms = { "지역 분위기", "불안한 부탁", "흔적의 방향", "잠잠해진 길목" };
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

                DynamicQuestTemplate storyTemplate = DynamicQuestStoryService.ApplyStory(
                    baseTemplate,
                    generated.Story,
                    generated.ProviderName,
                    generated.ModelName);

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
                DynamicQuestTemplateBindingResult binding = new DynamicQuestTemplateService()
                    .BindTemplate(template, npcs);

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

        private int UpgradeLegacyStoryCacheRows()
        {
            int upgraded = 0;
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

            DynamicQuestStoryText scaffold = BuildDeterministicFallbackStory(template);
            DynamicQuestTemplate upgraded = DynamicQuestStoryService.ApplyStory(
                template,
                scaffold,
                string.IsNullOrWhiteSpace(template.StoryProvider) ? "deterministic-fallback" : template.StoryProvider,
                string.IsNullOrWhiteSpace(template.StoryModel) ? "legacy-scaffold-v1" : template.StoryModel);

            List<string> tags = new(upgraded.Tags ?? Array.Empty<string>());
            if (!tags.Contains("story-scaffold-upgraded", StringComparer.OrdinalIgnoreCase))
                tags.Add("story-scaffold-upgraded");
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

        private static bool NeedsStoryCacheScaffoldUpgrade(DbDynamicQuestTemplate row)
        {
            return IsActiveStoryCacheRow(row) &&
                   !string.IsNullOrWhiteSpace(row.TemplateId) &&
                   !string.IsNullOrWhiteSpace(row.TargetNameHint) &&
                   (ParseStoryCacheNarrativeScenes(row.StoryNarrativeJson, includeText: false).Count == 0 ||
                    ParseStoryCachePresentationBeats(row.StoryPresentationJson, includeText: false).Count == 0);
        }

        private IEnumerable<DbDynamicQuestTemplate> SelectStoryCacheOfferRows(
            ISet<string> npcOfferCoveredRealms = null,
            ISet<string> autoAcceptCoveredRealms = null,
            int maxOffers = 0)
        {
            List<DbDynamicQuestTemplate> rows = GetActiveStoryCacheRows()
                .Where(row => !string.IsNullOrWhiteSpace(row.TemplateId))
                .Where(IsStoryCacheReadyForUse)
                .OrderBy(row => StoryCacheOfferLevelBucket(row))
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

        private static DynamicQuestStoryCacheItem BuildStoryCacheItem(DbDynamicQuestTemplate row, bool includeText)
        {
            IList<string> tags = DeserializeStoryCacheTags(row.TagsJson);
            DynamicQuestStoryQuality currentQuality = DynamicQuestStoryService.EvaluateQualityDetailsForCache(
                BuildStoryQualityRequest(row),
                BuildStoryQualityText(row));
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
                Count = row.Count,
                MinLevel = row.MinLevel,
                MaxLevel = row.MaxLevel,
                Source = row.Source ?? string.Empty,
                Tags = tags,
                BranchWorldSignal = ExtractBranchWorldSignal(tags),
                StoryProvider = row.StoryProvider ?? string.Empty,
                StoryModel = row.StoryModel ?? string.Empty,
                StoryQualityScore = Math.Clamp(row.StoryQualityScore, 0, 100),
                ReadyForUse = IsStoryCacheReadyForUse(row),
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
                        Emote = GetJsonString(element, "emote", "Emote")
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

            DynamicQuestStoryCacheQuality quality = ParseStoryCacheQuality(row.StoryQualityJson, row.StoryQualityScore);
            return quality.NarrativeScore > 0 &&
                   quality.PresentationScore > 0 &&
                   ParseStoryCacheNarrativeScenes(row.StoryNarrativeJson, includeText: false).Count > 0 &&
                   ParseStoryCachePresentationBeats(row.StoryPresentationJson, includeText: false).Count > 0 &&
                   DynamicQuestStoryService.IsStoryQualityAcceptableForCache(
                       BuildStoryQualityRequest(row),
                       BuildStoryQualityText(row));
        }

        private static bool IsStoryTemplateReadyForCache(DynamicQuestTemplate template)
        {
            if (template == null)
                return false;

            DynamicQuestStoryCacheQuality quality = ParseStoryCacheQuality(template.StoryQualityJson, template.StoryQualityScore);
            return quality.NarrativeScore > 0 &&
                   quality.PresentationScore > 0 &&
                   DeserializeStoryQualityArray<DynamicQuestNarrativeScene>(template.StoryNarrativeJson).Count > 0 &&
                   DeserializeStoryQualityArray<DynamicQuestPresentationBeat>(template.StoryPresentationJson).Count > 0 &&
                   DynamicQuestStoryService.IsStoryQualityAcceptableForCache(
                       BuildStoryQualityRequest(template),
                       BuildStoryQualityText(template));
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

        private static string GetJsonString(JsonElement root, params string[] names)
        {
            foreach (string name in names)
            {
                if (root.TryGetProperty(name, out JsonElement element) && element.ValueKind == JsonValueKind.String)
                    return element.GetString() ?? string.Empty;
            }

            return string.Empty;
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

        private static IDictionary<string, int> CountStoryCacheNotReadyReasons(IEnumerable<DbDynamicQuestTemplate> rows)
        {
            Dictionary<string, int> counters = new(StringComparer.OrdinalIgnoreCase);
            foreach (DbDynamicQuestTemplate row in rows ?? Array.Empty<DbDynamicQuestTemplate>())
            {
                if (IsStoryCacheReadyForUse(row))
                    continue;

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
                .Where(IsLikelyWorldQuestTarget)
                .Where(npc => npc.RegionId > 0)
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
            if (options == null || !options.UseLlm)
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

            return new DynamicQuestSeedDefinition
            {
                StartNpcName = string.Empty,
                RegionId = npc.RegionId,
                TargetName = npc.Name.Trim(),
                Count = level <= 5 ? 1 : level <= 20 ? 2 : 3,
                MinLevel = minLevel,
                MaxLevel = maxLevel,
                StartMode = DynamicQuestStartMode.AutoAccept,
                Trigger = BuildWorldPrefillTrigger(npc.RegionId),
                BranchWorldSignal = BuildWorldPrefillBranchWorldSignal(npc.RegionId)
            };
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
            if (!string.IsNullOrWhiteSpace(explicitSignal))
                return explicitSignal;

            if (!ShouldAttachDefaultMobGrowthBranch(definition, targetRegion))
                return string.Empty;

            return BuildMobGrowthRegionSignal(targetRegion);
        }

        private static bool ShouldAttachDefaultMobGrowthBranch(DynamicQuestSeedDefinition definition, ushort targetRegion)
        {
            return definition != null &&
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
                "starter",
                $"realm:{realm}",
                $"region:{targetRegion}",
                $"target:{definition.TargetName}",
                $"start-mode:{definition.StartMode}",
                "llm-ready"
            };

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

            return "branch:world-signal";
        }

        private static string BuildWorldPrefillTrigger(ushort regionId)
        {
            return RealmNameForRegion(regionId) switch
            {
                "Midgard" => "time-window:night",
                "Hibernia" => "time-window:dawn",
                "Unknown" => "time-window:dusk",
                _ => string.Empty
            };
        }

        private static string BuildWorldPrefillBranchWorldSignal(ushort regionId)
        {
            return RealmNameForRegion(regionId) switch
            {
                "Midgard" => "time-window:night",
                "Hibernia" => "item-acquired",
                "Unknown" => "time-window:dusk",
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
                Tags = new[]
                {
                    "starter",
                    $"realm:{RealmNameForRegion(TargetRegion(npc, definition))}",
                    $"region:{TargetRegion(npc, definition)}",
                    $"target:{definition.TargetName}",
                    "llm-ready"
                }
            };
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
                        new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "safe", Priority = 0 },
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

            return "성장 위협 관측";
        }

        private static string BranchObservationText(string targetName, string branchWorldSignal)
        {
            string signal = (branchWorldSignal ?? string.Empty).Trim();
            if (signal.StartsWith("time-window", StringComparison.OrdinalIgnoreCase))
                return $"{targetName} 주변의 기척이 특정 시간대에 다시 흔들리는지 지켜보세요.";
            if (signal.StartsWith("item-acquired", StringComparison.OrdinalIgnoreCase))
                return $"{targetName} 흔적과 이어지는 단서를 확보하세요.";

            return $"{targetName} 주변에서 성장한 위협이 쓰러지는지 지켜보세요.";
        }

        private static string BranchObservationLocation(string targetName, string branchWorldSignal)
        {
            string signal = (branchWorldSignal ?? string.Empty).Trim();
            if (signal.StartsWith("time-window", StringComparison.OrdinalIgnoreCase))
                return $"{targetName} 시간 징후";
            if (signal.StartsWith("item-acquired", StringComparison.OrdinalIgnoreCase))
                return $"{targetName} 단서";

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
