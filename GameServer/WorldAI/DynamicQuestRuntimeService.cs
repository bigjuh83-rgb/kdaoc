using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using DOL.Database;
using DOL.Events;
using DOL.GS.PacketHandler;
using DOL.GS.Quests;
using DOL.GS.ServerProperties;

namespace DOL.GS.WorldAI
{
    public enum DynamicQuestStepType
    {
        Kill,
    }

    public enum DynamicQuestStartMode
    {
        NpcOffer,
        WorldOffer,
        AutoAccept
    }

    public sealed class DynamicQuestDefinition
    {
        public string Id { get; set; } = Guid.NewGuid().ToString("N");
        public string Title { get; set; } = string.Empty;
        public string OfferText { get; set; } = string.Empty;
        public string ProgressText { get; set; } = string.Empty;
        public string FinishText { get; set; } = string.Empty;
        public string StoryNarrativeJson { get; set; } = string.Empty;
        public string StoryPresentationJson { get; set; } = string.Empty;
        public string StartNpcInternalId { get; set; } = string.Empty;
        public string StartNpcName { get; set; } = string.Empty;
        public ushort StartRegionId { get; set; }
        public string Realm { get; set; } = string.Empty;
        public DynamicQuestStartMode StartMode { get; set; } = DynamicQuestStartMode.NpcOffer;
        public DynamicQuestStepType StepType { get; set; } = DynamicQuestStepType.Kill;
        public string TargetName { get; set; } = string.Empty;
        public int TargetCount { get; set; } = 1;
        public int MinLevel { get; set; } = 1;
        public int MaxLevel { get; set; } = 50;
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        public int GraphVersion { get; set; } = 1;
        public string StartNodeId { get; set; } = string.Empty;
        public IList<DynamicQuestNode> Nodes { get; set; } = Array.Empty<DynamicQuestNode>();
        public DynamicQuestRewardDefinition Reward { get; set; } = new();
        public IList<string> Tags { get; set; } = Array.Empty<string>();
        public string BindingKey { get; set; } = string.Empty;
        public string WorldRevision { get; set; } = string.Empty;
    }

    public sealed class DynamicQuestProgress
    {
        public string QuestId { get; set; } = string.Empty;
        public int Count { get; set; }
        public bool IsComplete { get; set; }
        public DateTime AcceptedAt { get; set; } = DateTime.UtcNow;
        public string CurrentNodeId { get; set; } = string.Empty;
        public Dictionary<string, int> NodeCounters { get; set; } = new(StringComparer.OrdinalIgnoreCase);
        public HashSet<string> CompletedNodeIds { get; set; } = new(StringComparer.OrdinalIgnoreCase);
        public Dictionary<string, string> ChoiceHistory { get; set; } = new(StringComparer.OrdinalIgnoreCase);
        public HashSet<string> PendingWorldSignals { get; set; } = new(StringComparer.OrdinalIgnoreCase);
        public DynamicQuestDefinition QuestSnapshot { get; set; }
        public string BindingKey { get; set; } = string.Empty;
        public string WorldRevision { get; set; } = string.Empty;
        public string CancelReason { get; set; } = string.Empty;
        public bool Failed { get; set; }
        public bool Completed { get; set; }
        public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
    }

    public sealed class DynamicQuestResult
    {
        public bool Success { get; set; }
        public string Message { get; set; } = string.Empty;
        public DynamicQuestDefinition Quest { get; set; }

        public static DynamicQuestResult Ok(DynamicQuestDefinition quest, string message)
        {
            return new DynamicQuestResult { Success = true, Quest = quest, Message = message };
        }

        public static DynamicQuestResult Fail(string message)
        {
            return new DynamicQuestResult { Success = false, Message = message };
        }
    }

    public sealed class DynamicQuestProgressItem
    {
        public string QuestId { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public string StartNpcName { get; set; } = string.Empty;
        public ushort StartRegionId { get; set; }
        public string TargetName { get; set; } = string.Empty;
        public int TargetCount { get; set; }
        public int Count { get; set; }
        public bool IsComplete { get; set; }
        public DateTime AcceptedAt { get; set; }
        public string CurrentNodeId { get; set; } = string.Empty;
        public DynamicQuestNodeType CurrentNodeType { get; set; }
        public DynamicQuestObjective CurrentObjective { get; set; } = new();
        public IList<DynamicQuestNode> Nodes { get; set; } = Array.Empty<DynamicQuestNode>();
        public IList<string> CompletedNodeIds { get; set; } = Array.Empty<string>();
        public IList<DynamicQuestChoice> Choices { get; set; } = Array.Empty<DynamicQuestChoice>();
        public string BindingKey { get; set; } = string.Empty;
        public string WorldRevision { get; set; } = string.Empty;
        public string CancelReason { get; set; } = string.Empty;
        public bool Failed { get; set; }
        public DateTime UpdatedAt { get; set; }
        public DateTime CurrentNodeEnteredAt { get; set; }
        public int CurrentNodeElapsedSeconds { get; set; }
        public IList<string> PendingWorldSignals { get; set; } = Array.Empty<string>();
        public string LastEventType { get; set; } = string.Empty;
        public DateTime LastEventAt { get; set; }
        public string LastEventNodeId { get; set; } = string.Empty;
        public string LastEventDetail { get; set; } = string.Empty;
        public string StalledReason { get; set; } = string.Empty;
        public IList<DynamicQuestJournalEntry> JournalEntries { get; set; } = Array.Empty<DynamicQuestJournalEntry>();
    }

    public sealed class DynamicQuestJournalEntry
    {
        public string NodeId { get; set; } = string.Empty;
        public string SceneType { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public string JournalEntry { get; set; } = string.Empty;
        public string Mood { get; set; } = string.Empty;
        public bool Current { get; set; }
    }

    public sealed class DynamicQuestProgressSnapshot
    {
        public bool Enabled { get; set; }
        public string Player { get; set; } = string.Empty;
        public string PlayerKey { get; set; } = string.Empty;
        public bool Online { get; set; }
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public IList<DynamicQuestProgressItem> Active { get; set; } = Array.Empty<DynamicQuestProgressItem>();
        public IList<string> CompletedQuestIds { get; set; } = Array.Empty<string>();
    }

    public interface IDynamicQuestJournalAdapter
    {
        string DynamicProgressId { get; }
    }

    public sealed class DynamicQuestJournalAdapter : AbstractQuest, IDynamicQuestJournalAdapter
    {
        public DynamicQuestJournalAdapter(
            string playerKey,
            string questId,
            ushort startRegionId,
            string title,
            string description,
            int level,
            int step)
        {
            PlayerKey = (playerKey ?? string.Empty).Trim();
            QuestId = (questId ?? string.Empty).Trim();
            StartRegionId = startRegionId;
            Update(title, description, level, step);
        }

        public string PlayerKey { get; }
        public string QuestId { get; }
        public ushort StartRegionId { get; }
        public string DynamicProgressId => DynamicQuestRuntimeService.BuildJournalProgressId(PlayerKey, QuestId);
        public override string Name => m_title;
        public override string Description => m_description;
        public override int Level
        {
            get => m_level;
            set => m_level = Math.Clamp(value, 1, 50);
        }
        public override int Step
        {
            get => m_step;
            set => m_step = value;
        }

        private string m_title = "Dynamic Quest";
        private string m_description = string.Empty;
        private int m_level = 1;
        private int m_step = 1;

        public void Update(string title, string description, int level, int step)
        {
            m_title = string.IsNullOrWhiteSpace(title) ? "Dynamic Quest" : title.Trim();
            m_description = string.IsNullOrWhiteSpace(description) ? "동적 퀘스트 진행 중입니다." : description.Trim();
            m_level = Math.Clamp(level, 1, 50);
            m_step = Math.Max(1, step);
        }

        public override void SaveIntoDatabase()
        {
        }

        public override void DeleteFromDatabase()
        {
        }

        public override bool IsDoingQuest()
        {
            return true;
        }

        public override bool CheckQuestQualification(GamePlayer player)
        {
            return player != null;
        }

        public override void Notify(DOLEvent e, object sender, EventArgs args)
        {
        }

        public override void OnQuestAssigned(GamePlayer player)
        {
            m_questPlayer = player;
        }

        public override void FinishQuest()
        {
            RemoveFromQuestList(sendRemove: true);
        }

        public override void AbortQuest()
        {
            if (m_questPlayer != null &&
                DynamicQuestRuntimeService.Instance.CancelActiveProgressForPlayerQuest(
                    m_questPlayer,
                    QuestId,
                    "client_journal_abort"))
            {
                return;
            }

            RemoveFromQuestList(sendRemove: true);
        }

        private void RemoveFromQuestList(bool sendRemove)
        {
            if (m_questPlayer == null)
                return;

            if (m_questPlayer.QuestList.TryRemove(this, out byte index))
            {
                m_questPlayer.AvailableQuestIndexes.Enqueue(index);
                if (sendRemove)
                    m_questPlayer.Out.SendQuestRemove(index);
            }
        }
    }

    public sealed class DynamicQuestWorldMemorySnapshot
    {
        public bool Enabled { get; set; }
        public string Player { get; set; } = string.Empty;
        public string PlayerKey { get; set; } = string.Empty;
        public bool Online { get; set; }
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public IList<string> CompletedQuestIds { get; set; } = Array.Empty<string>();
        public IList<string> CompletedStoryFamilyIds { get; set; } = Array.Empty<string>();
        public IList<string> Signals { get; set; } = Array.Empty<string>();
    }

    public sealed class DynamicQuestProgressSummary
    {
        public bool Enabled { get; set; }
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public int Limit { get; set; }
        public int LoadedPlayerCount { get; set; }
        public int ActiveProgressCount { get; set; }
        public IList<DynamicQuestProgressSummaryItem> Active { get; set; } = Array.Empty<DynamicQuestProgressSummaryItem>();
        public IDictionary<string, int> ByStalledReason { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        public IDictionary<string, int> ByNodeType { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
    }

    public sealed class DynamicQuestProgressSummaryItem
    {
        public string Player { get; set; } = string.Empty;
        public string PlayerKey { get; set; } = string.Empty;
        public string QuestId { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public string CurrentNodeId { get; set; } = string.Empty;
        public DynamicQuestNodeType CurrentNodeType { get; set; }
        public string StalledReason { get; set; } = string.Empty;
        public string LastEventType { get; set; } = string.Empty;
        public int CurrentNodeElapsedSeconds { get; set; }
        public DateTime UpdatedAt { get; set; }
        public IList<string> PendingWorldSignals { get; set; } = Array.Empty<string>();
    }

    public sealed class DynamicQuestProgressCleanupPlan
    {
        public bool Enabled { get; set; }
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public int Limit { get; set; }
        public int StaleThresholdSeconds { get; set; }
        public int CandidateCount { get; set; }
        public int CancelCandidateCount { get; set; }
        public IList<DynamicQuestProgressCleanupPlanItem> Candidates { get; set; } = Array.Empty<DynamicQuestProgressCleanupPlanItem>();
        public IDictionary<string, int> ByActionHint { get; set; } = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
    }

    public sealed class DynamicQuestProgressCleanupPlanItem
    {
        public string Player { get; set; } = string.Empty;
        public string PlayerKey { get; set; } = string.Empty;
        public string QuestId { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public string CurrentNodeId { get; set; } = string.Empty;
        public DynamicQuestNodeType CurrentNodeType { get; set; }
        public string StalledReason { get; set; } = string.Empty;
        public int CurrentNodeElapsedSeconds { get; set; }
        public bool Stale { get; set; }
        public bool ShouldCancel { get; set; }
        public string ActionHint { get; set; } = string.Empty;
        public DateTime UpdatedAt { get; set; }
        public IList<string> PendingWorldSignals { get; set; } = Array.Empty<string>();
    }

    public sealed class DynamicQuestProgressCleanupCancelResult
    {
        public bool Enabled { get; set; }
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public int Limit { get; set; }
        public int StaleThresholdSeconds { get; set; }
        public string Reason { get; set; } = string.Empty;
        public int CancelledCount { get; set; }
        public IList<DynamicQuestProgressCleanupPlanItem> Cancelled { get; set; } = Array.Empty<DynamicQuestProgressCleanupPlanItem>();
    }

    public sealed class DynamicQuestProgressCleanupAdvanceResult
    {
        public bool Enabled { get; set; }
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public int Limit { get; set; }
        public string Reason { get; set; } = string.Empty;
        public int AdvancedCount { get; set; }
        public IList<DynamicQuestProgressCleanupPlanItem> Advanced { get; set; } = Array.Empty<DynamicQuestProgressCleanupPlanItem>();
    }

    public sealed class DynamicQuestWorldImpactSummary
    {
        public bool Enabled { get; set; }
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public int Limit { get; set; }
        public int TotalRecorded { get; set; }
        public IList<DynamicQuestWorldImpactRegionSummary> ByRegion { get; set; } = Array.Empty<DynamicQuestWorldImpactRegionSummary>();
        public IList<DynamicQuestWorldImpactRecord> Recent { get; set; } = Array.Empty<DynamicQuestWorldImpactRecord>();
    }

    public sealed class DynamicQuestWorldImpactRegionSummary
    {
        public ushort RegionId { get; set; }
        public string Realm { get; set; } = string.Empty;
        public int CompletionCount { get; set; }
        public DateTime LastImpactAt { get; set; }
    }

    public sealed class DynamicQuestWorldImpactRecord
    {
        public DateTime At { get; set; } = DateTime.UtcNow;
        public string QuestId { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public string PlayerName { get; set; } = string.Empty;
        public string Realm { get; set; } = string.Empty;
        public ushort RegionId { get; set; }
        public string TargetName { get; set; } = string.Empty;
        public string ImpactType { get; set; } = "region_stabilized";
        public string ChoiceId { get; set; } = string.Empty;
        public string ChoiceConsequence { get; set; } = string.Empty;
        public string Summary { get; set; } = string.Empty;
        public IList<string> Signals { get; set; } = Array.Empty<string>();
    }

    public sealed class DynamicQuestValidationSnapshot
    {
        public bool Enabled { get; set; }
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public int Limit { get; set; }
        public int TotalQuests { get; set; }
        public int ValidQuests { get; set; }
        public int InvalidQuests { get; set; }
        public IList<DynamicQuestValidationItem> Items { get; set; } = Array.Empty<DynamicQuestValidationItem>();
    }

    public sealed class DynamicQuestValidationItem
    {
        public string QuestId { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public string Realm { get; set; } = string.Empty;
        public ushort StartRegionId { get; set; }
        public string StartMode { get; set; } = string.Empty;
        public string TargetName { get; set; } = string.Empty;
        public string BindingKey { get; set; } = string.Empty;
        public string WorldRevision { get; set; } = string.Empty;
        public bool Valid { get; set; }
        public IList<string> Errors { get; set; } = Array.Empty<string>();
        public IList<string> Warnings { get; set; } = Array.Empty<string>();
        public int EstimatedPlayableSteps { get; set; }
        public int EstimatedMinutes { get; set; }
        public int RewardDifficultyIndex { get; set; }
        public string RewardLengthTier { get; set; } = string.Empty;
        public string RewardDifficultyTier { get; set; } = string.Empty;
        public string SuggestedRewardTier { get; set; } = string.Empty;
        public double SuggestedRewardScale { get; set; }
    }

    public sealed class DynamicQuestTimelineEvent
    {
        public DateTime At { get; set; } = DateTime.UtcNow;
        public string PlayerKey { get; set; } = string.Empty;
        public string PlayerName { get; set; } = string.Empty;
        public string QuestId { get; set; } = string.Empty;
        public string EventType { get; set; } = string.Empty;
        public string NodeId { get; set; } = string.Empty;
        public string FromNodeId { get; set; } = string.Empty;
        public string ToNodeId { get; set; } = string.Empty;
        public string Detail { get; set; } = string.Empty;
        public string ChoiceId { get; set; } = string.Empty;
        public int Count { get; set; }
    }

    public sealed class DynamicQuestPresentationBeatObservation
    {
        public DateTime At { get; set; } = DateTime.UtcNow;
        public string QuestId { get; set; } = string.Empty;
        public string NodeId { get; set; } = string.Empty;
        public string Trigger { get; set; } = string.Empty;
        public string Speaker { get; set; } = string.Empty;
        public string Emotion { get; set; } = string.Empty;
        public string Emote { get; set; } = string.Empty;
        public string Text { get; set; } = string.Empty;
        public string CinematicAction { get; set; } = string.Empty;
        public string SceneRole { get; set; } = string.Empty;
        public string Formation { get; set; } = string.Empty;
        public int ActorCount { get; set; }
        public int DelayMs { get; set; }
    }

    public sealed class DynamicQuestTimelineSnapshot
    {
        public bool Enabled { get; set; }
        public string Player { get; set; } = string.Empty;
        public string PlayerKey { get; set; } = string.Empty;
        public bool Online { get; set; }
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public IList<DynamicQuestTimelineEvent> Events { get; set; } = Array.Empty<DynamicQuestTimelineEvent>();
        public IList<DynamicQuestPresentationBeatObservation> PresentationBeats { get; set; } = Array.Empty<DynamicQuestPresentationBeatObservation>();
    }

    public sealed class DynamicQuestCinematicCatalogSnapshot
    {
        public bool Enabled { get; set; }
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public int Limit { get; set; }
        public int PropCount { get; set; }
        public int NpcCount { get; set; }
        public IList<DynamicQuestCinematicCatalogItem> Props { get; set; } = Array.Empty<DynamicQuestCinematicCatalogItem>();
        public IList<DynamicQuestCinematicCatalogItem> Npcs { get; set; } = Array.Empty<DynamicQuestCinematicCatalogItem>();
    }

    public sealed class DynamicQuestCinematicCatalogItem
    {
        public ushort Model { get; set; }
        public string Label { get; set; } = string.Empty;
        public string Source { get; set; } = string.Empty;
        public string Category { get; set; } = string.Empty;
        public IList<string> Tags { get; set; } = Array.Empty<string>();
    }

    public sealed class DynamicQuestCinematicPlanSnapshot
    {
        public bool Enabled { get; set; }
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public bool Found { get; set; }
        public string QuestId { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public string Realm { get; set; } = string.Empty;
        public ushort StartRegionId { get; set; }
        public int NodeCount { get; set; }
        public int ActionCount { get; set; }
        public int TotalActorCount { get; set; }
        public int MaxActorsPerAction { get; set; }
        public IList<DynamicQuestCinematicPlanItem> Actions { get; set; } = Array.Empty<DynamicQuestCinematicPlanItem>();
    }

        public sealed class DynamicQuestCinematicPlanItem
        {
            public string NodeId { get; set; } = string.Empty;
            public string NodeTitle { get; set; } = string.Empty;
            public DynamicQuestNodeType NodeType { get; set; }
        public string Trigger { get; set; } = string.Empty;
        public string Kind { get; set; } = string.Empty;
        public string Detail { get; set; } = string.Empty;
        public bool SpawnMarker { get; set; }
        public string MarkerName { get; set; } = string.Empty;
        public ushort MarkerModel { get; set; }
        public bool SpawnNpcActor { get; set; }
        public string NpcAction { get; set; } = string.Empty;
            public string ActorName { get; set; } = string.Empty;
            public ushort NpcModel { get; set; }
            public string NpcRoleCategory { get; set; } = string.Empty;
            public int ActorCount { get; set; }
            public int SceneBeatIndex { get; set; }
            public int SceneDelayMs { get; set; }
        public string SceneRole { get; set; } = string.Empty;
        public string Formation { get; set; } = string.Empty;
        public string MotionPattern { get; set; } = string.Empty;
        public int MotionDistance { get; set; }
        public int MotionLateral { get; set; }
        public int MotionSpeed { get; set; }
        public int MotionStaggerMs { get; set; }
        public string FocalPoint { get; set; } = string.Empty;
        public string ActorRole { get; set; } = string.Empty;
        public string InteractionStyle { get; set; } = string.Empty;
        public string TacticalRole { get; set; } = string.Empty;
        public int ChoreographyPhases { get; set; } = 1;
        public bool CleanupMarkers { get; set; }
        public string Emote { get; set; } = string.Empty;
    }

    public sealed class DynamicQuestRuntimeRemovalResult
    {
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
        public string TemplateId { get; set; } = string.Empty;
        public string Reason { get; set; } = string.Empty;
        public int RemovedQuests { get; set; }
        public int CancelledProgress { get; set; }
        public IList<string> RemovedQuestIds { get; set; } = Array.Empty<string>();
    }

    public interface IDynamicQuestProgressRepository
    {
        bool Add(DbDynamicQuestProgress row);
        IList<DbDynamicQuestProgress> GetActive(int limit);
        IList<DbDynamicQuestProgress> GetActiveForDifferentWorldRevision(string currentWorldRevision);
        IList<DbDynamicQuestProgress> GetActiveForMissingQuestIds(ISet<string> activeQuestIds);
        DbDynamicQuestProgress Find(string progressId);
        IList<DbDynamicQuestProgress> GetByPlayer(string playerKey);
        bool Save(DbDynamicQuestProgress row);
    }

    public sealed class DynamicQuestRuntimeService
    {
        private static readonly Logging.Logger Log = Logging.LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);
        private const string PendingWorldSignalCounterPrefix = "__pending_world_signal__:";
        private const string CurrentNodeEnteredAtCounterKey = "__current_node_entered_at_seconds_since_2020__";
        private const double ChoiceRewardBonusMultiplier = 1.15;
        private const int MaxCinematicActorsPerAction = 100;
        private static readonly DateTime RuntimeClockEpochUtc = new(2020, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        private static readonly JsonSerializerOptions StoryJsonOptions = new()
        {
            PropertyNameCaseInsensitive = true
        };
        private enum WorldSignalRecordResult
        {
            Ignored,
            Pending,
            Advanced
        }

        private sealed class DynamicQuestJournalSnapshot
        {
            public string PlayerKey { get; set; } = string.Empty;
            public string QuestId { get; set; } = string.Empty;
            public string ProgressId { get; set; } = string.Empty;
            public ushort StartRegionId { get; set; }
            public string Title { get; set; } = string.Empty;
            public string Description { get; set; } = string.Empty;
            public int Level { get; set; }
            public int Step { get; set; }
        }

        private sealed class DynamicQuestCinematicAction
        {
            public string Kind { get; set; } = string.Empty;
            public string Detail { get; set; } = string.Empty;
            public string MarkerName { get; set; } = string.Empty;
            public ushort MarkerModel { get; set; }
            public DynamicQuestObjective Objective { get; set; }
            public bool SpawnMarker { get; set; }
            public bool FocusNpc { get; set; }
            public string NpcAction { get; set; } = string.Empty;
            public ushort NpcModel { get; set; }
            public string NpcRoleCategory { get; set; } = string.Empty;
            public string ActorName { get; set; } = string.Empty;
            public int ActorCount { get; set; } = 1;
            public int SceneBeatIndex { get; set; }
            public int SceneDelayMs { get; set; }
            public string SceneRole { get; set; } = string.Empty;
            public string Formation { get; set; } = string.Empty;
            public string MotionPattern { get; set; } = string.Empty;
            public int MotionDistance { get; set; }
            public int MotionLateral { get; set; }
            public int MotionSpeed { get; set; }
            public int MotionStaggerMs { get; set; }
            public string FocalPoint { get; set; } = string.Empty;
            public string ActorRole { get; set; } = string.Empty;
            public string InteractionStyle { get; set; } = string.Empty;
            public string TacticalRole { get; set; } = string.Empty;
            public int ChoreographyPhases { get; set; } = 1;
            public bool SpawnNpcActor { get; set; }
            public bool CleanupMarkers { get; set; }
            public eEmote? Emote { get; set; }
        }

        private const int MaxPlayerTimelineEvents = 500;

        private readonly object m_lock = new();
        private readonly Dictionary<string, DynamicQuestDefinition> m_quests = new(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, List<DynamicQuestProgress>> m_playerProgress = new(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, HashSet<string>> m_playerCompletedQuestIds = new(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, HashSet<string>> m_playerCompletedStoryFamilyIds = new(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, HashSet<string>> m_playerWorldMemorySignals = new(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, List<DynamicQuestTimelineEvent>> m_playerTimeline = new(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, List<GameStaticItem>> m_cinematicMarkers = new(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, List<GameNPC>> m_cinematicActors = new(StringComparer.OrdinalIgnoreCase);
        private readonly List<DynamicQuestWorldImpactRecord> m_worldImpactRecords = new();
        private readonly HashSet<string> m_loadedPlayerKeys = new(StringComparer.OrdinalIgnoreCase);
        private readonly IDynamicQuestProgressRepository m_progressRepository;
        private bool m_cancelMissingRuntimeProgressOnLoad;

        public static DynamicQuestRuntimeService Instance { get; } = new();

        public DynamicQuestRuntimeService()
            : this(new DatabaseDynamicQuestProgressRepository())
        {
        }

        internal DynamicQuestRuntimeService(IDynamicQuestProgressRepository progressRepository)
        {
            m_progressRepository = progressRepository ?? new DatabaseDynamicQuestProgressRepository();
        }

        public DynamicQuestResult AddQuest(DynamicQuestDefinition quest)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED)
                return DynamicQuestResult.Fail("동적 퀘스트가 비활성화되어 있습니다. kdaoc_dynamic_quest_enabled를 켜세요.");

            quest = NormalizeQuest(quest);
            List<string> errors = Validate(quest);
            if (errors.Count > 0)
                return DynamicQuestResult.Fail(string.Join(" / ", errors));

            DynamicQuestEvaluationResult operationalEvaluation = DynamicQuestOperationalEvaluator.Instance.Evaluate(quest);
            if (!operationalEvaluation.Passed)
                return DynamicQuestResult.Fail($"운영 평가 실패: {string.Join(" / ", operationalEvaluation.FailReasons)}");

            lock (m_lock)
            {
                if (RequiresStartNpc(quest))
                {
                    int npcQuestCount = m_quests.Values.Count(existing =>
                        RequiresStartNpc(existing) &&
                        !string.Equals(existing.Id, quest.Id, StringComparison.OrdinalIgnoreCase) &&
                        existing.StartNpcInternalId == quest.StartNpcInternalId &&
                        existing.StartRegionId == quest.StartRegionId);

                    if (npcQuestCount >= Math.Max(1, Properties.KDAOC_DYNAMIC_QUEST_MAX_ACTIVE_PER_NPC))
                        return DynamicQuestResult.Fail("해당 NPC에 이미 동적 퀘스트가 있습니다.");
                }

                m_quests[quest.Id] = quest;
            }

            return DynamicQuestResult.Ok(quest, $"동적 퀘스트 생성: {quest.Title}");
        }

        public DynamicQuestResult CreateKillQuest(GameNPC startNpc, string targetName, int count, int minLevel = 1, int maxLevel = 50)
        {
            if (startNpc == null)
                return DynamicQuestResult.Fail("시작 NPC가 없습니다.");

            count = Math.Clamp(count, 1, Math.Max(1, Properties.KDAOC_DYNAMIC_QUEST_MAX_KILL_COUNT));

            DynamicQuestDefinition quest = new()
            {
                Title = $"{targetName} 처치 요청",
                OfferText = $"{targetName} 때문에 이 근처가 어수선합니다. {count}마리만 처리해 주시겠습니까?",
                ProgressText = $"아직 {targetName} 위협이 남아 있습니다.",
                FinishText = "좋습니다. 덕분에 이 지역이 한결 안전해졌습니다.",
                StartNpcInternalId = startNpc.InternalID ?? string.Empty,
                StartNpcName = startNpc.Name ?? string.Empty,
                StartRegionId = startNpc.CurrentRegionID,
                StepType = DynamicQuestStepType.Kill,
                TargetName = targetName,
                TargetCount = count,
                MinLevel = minLevel,
                MaxLevel = maxLevel,
            };

            return AddQuest(quest);
        }

        public DynamicQuestResult CreateKillQuestFromLlm(GameNPC startNpc, string seed)
        {
            if (startNpc == null)
                return DynamicQuestResult.Fail("시작 NPC가 없습니다.");

            try
            {
                string json = GenerateQuestJson(startNpc, seed);
                DynamicQuestDefinition quest = ParseLlmQuest(startNpc, json);
                return AddQuest(quest);
            }
            catch (Exception e)
            {
                Log.Error("Dynamic quest LLM generation failed.", e);
                return DynamicQuestResult.Fail(e.Message);
            }
        }

        public bool HandleNpcInteract(GameNPC npc, GamePlayer player)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED || npc == null || player == null)
                return false;

            string playerKey = GetPlayerKey(player);
            EnsurePlayerProgressLoaded(playerKey, player.Name ?? string.Empty);

            DynamicQuestProgress active = GetProgressForStartNpc(player, npc);
            if (active != null && TryGetQuestForProgress(active, out DynamicQuestDefinition activeQuest))
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
                    string fromNodeId = node.Id;
                    RecordPresentationBeatsLocked(
                        playerKey,
                        player.Name ?? string.Empty,
                        normalizedQuest,
                        node.Id,
                        player,
                        npc,
                        "OnNpcInteract");
                    AdvanceFromNode(active, normalizedQuest, node, DynamicQuestEdgeCondition.ObjectiveComplete, string.Empty);
                    RecordNodeTransitionLocked(playerKey, player.Name ?? string.Empty, normalizedQuest.Id, active, fromNodeId, "npc_interaction");
                    RecordStoryNodeEnteredLocked(playerKey, player.Name ?? string.Empty, normalizedQuest, active, player, npc, "OnNodeEnter");
                    TryConsumePendingWorldSignalsLocked(playerKey, player.Name ?? string.Empty, normalizedQuest, active, player, npc);
                    TryAutoAdvanceFromCurrentNodeLocked(playerKey, player.Name ?? string.Empty, normalizedQuest, active, "npc_interaction", GetPlayerPartySize(player), player: player, npc: npc);
                    SaveProgress(playerKey, player.Name ?? string.Empty, active);
                    node = GetCurrentNode(normalizedQuest, active);

                    if (node?.Type == DynamicQuestNodeType.Choice)
                    {
                        ShowChoiceDialog(player, npc, normalizedQuest, active, node);
                        return true;
                    }
                }

                if (node?.Type == DynamicQuestNodeType.Complete || active.Completed || active.IsComplete)
                {
                    FinishQuest(player, npc, normalizedQuest, active);
                    return true;
                }

                npc.SayTo(player, node?.Text ?? normalizedQuest.ProgressText);
                return true;
            }

            DynamicQuestDefinition offer = GetAvailableQuest(npc, player);
            if (offer == null)
                return false;

            player.Out.SendCustomDialog($"{offer.OfferText}\n\n목표: {offer.TargetName} {offer.TargetCount}마리 처치", (dialogPlayer, response) =>
            {
                if (response != 0x01)
                {
                    npc.SayTo(dialogPlayer, "마음이 바뀌면 다시 찾아오세요.");
                    return;
                }

                AcceptQuest(dialogPlayer, npc, offer);
            });

            return true;
        }

        public eQuestIndicator GetQuestIndicator(GameNPC npc, GamePlayer player)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED || npc == null || player == null)
                return eQuestIndicator.None;

            EnsurePlayerProgressLoaded(GetPlayerKey(player), player.Name ?? string.Empty);

            DynamicQuestProgress active = GetProgressForStartNpc(player, npc);
            if (active != null && TryGetQuestForProgress(active, out DynamicQuestDefinition activeQuest) && IsStartNpc(activeQuest, npc))
            {
                DynamicQuestDefinition normalizedQuest = NormalizeQuest(activeQuest);
                DynamicQuestNode node = GetCurrentNode(normalizedQuest, active);
                return active.IsComplete || active.Completed || node?.Type is DynamicQuestNodeType.ReturnToNpc or DynamicQuestNodeType.Choice or DynamicQuestNodeType.Complete
                    ? eQuestIndicator.Finish
                    : eQuestIndicator.Pending;
            }

            return GetAvailableQuest(npc, player) != null ? eQuestIndicator.Available : eQuestIndicator.None;
        }

        public void HandleEnemyKilled(GamePlayer player, GameLiving enemy)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED || player == null || enemy == null)
                return;

            IList<string> worldSignals = enemy is GameNPC npc && Properties.WORLDAI_MOB_GROWTH_ENABLED
                ? MobGrowthService.Instance.BuildQuestKillSignals(npc)
                : Array.Empty<string>();

            foreach (GamePlayer creditPlayer in GetKillCreditPlayers(player, enemy))
            {
                string playerKey = GetPlayerKey(creditPlayer);
                string playerName = creditPlayer.Name ?? string.Empty;
                EnsurePlayerProgressLoaded(playerKey, playerName);
                bool groupCredit = !ReferenceEquals(creditPlayer, player);
                DynamicQuestDefinition quest;
                bool advanced;
                lock (m_lock)
                    advanced = RecordKillProgressLocked(playerKey, playerName, enemy.Name, (int)enemy.Level, enemy.CurrentRegionID, groupCredit, creditPlayer, null, out quest);

                if (advanced && quest != null)
                {
                    bool finishedNpcLess = TryFinishCompletedNpcLessQuest(creditPlayer, playerKey, playerName, quest);
                    if (!finishedNpcLess)
                        NotifyKillProgress(creditPlayer, quest);
                }

                if (worldSignals.Count > 0)
                    RecordFirstWorldSignalForPlayer(creditPlayer, playerKey, playerName, worldSignals);
            }
        }

        public void HandlePlayerPositionUpdated(GamePlayer player)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED || player == null)
                return;

            string playerKey = GetPlayerKey(player);
            string playerName = player.Name ?? string.Empty;
            EnsurePlayerProgressLoaded(playerKey, playerName);
            TryAcceptRegionalAutoQuest(player);
            foreach (string signal in BuildRegionEnteredSignals(player.CurrentRegionID))
                TryAcceptAvailableWorldQuest(player, signal, showFailureMessage: false, includeAutoAccept: false);
            RecordFirstWorldSignalForPlayer(player, playerKey, playerName, BuildRegionEnteredSignals(player.CurrentRegionID));
            RecordFirstWorldSignalForPlayer(player, playerKey, playerName, BuildTimeWindowSignals(DateTime.UtcNow));

            DynamicQuestDefinition quest;
            bool advanced;
            lock (m_lock)
                advanced = RecordExploreProgressLocked(playerKey, playerName, player.CurrentRegionID, player.X, player.Y, player, out quest);

            if (!advanced || quest == null)
                return;

            if (TryFinishCompletedNpcLessQuest(player, playerKey, player.Name ?? string.Empty, quest))
                return;

            DynamicQuestProgressItem item = GetProgressSnapshot(player).Active.FirstOrDefault(active => active.QuestId == quest.Id);
            if (item == null)
                return;

            player.Out.SendMessage($"{quest.Title}: {DescribeCurrentObjective(item)}", eChatType.CT_System, eChatLoc.CL_SystemWindow);
            SyncDynamicQuestJournal(player);
        }

        public bool RecordWorldSignal(GamePlayer player, string signal)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED || player == null || string.IsNullOrWhiteSpace(signal))
                return false;

            string playerKey = GetPlayerKey(player);
            string playerName = player.Name ?? string.Empty;
            EnsurePlayerProgressLoaded(playerKey, playerName);

            return RecordWorldSignalForPlayer(player, playerKey, playerName, signal);
        }

        public bool HandleItemAcquired(GamePlayer player, DbInventoryItem item)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED || player == null || item == null)
                return false;

            IList<string> signals = BuildItemAcquiredSignals(item).ToList();
            if (signals.Count == 0)
                return false;

            bool handled = false;
            foreach (GamePlayer creditPlayer in GetItemAcquiredSignalCreditPlayers(player))
            {
                string playerKey = GetPlayerKey(creditPlayer);
                string playerName = creditPlayer.Name ?? string.Empty;
                EnsurePlayerProgressLoaded(playerKey, playerName);

                foreach (string signal in signals)
                {
                    if (ReferenceEquals(creditPlayer, player))
                        handled |= TryAcceptAvailableWorldQuest(player, signal, showFailureMessage: false);

                    handled |= RecordWorldSignalForPlayer(creditPlayer, playerKey, playerName, signal);
                }
            }

            return handled;
        }

        public DbItemTemplate BuildItemAcquiredBranchClueDrop(GameNPC killedNpc, GamePlayer player)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED || killedNpc == null || player == null)
                return null;

            string playerKey = GetPlayerKey(player);
            EnsurePlayerProgressLoaded(playerKey, player.Name ?? string.Empty);

            lock (m_lock)
            {
                return BuildItemAcquiredBranchClueDropLocked(
                    playerKey,
                    killedNpc.Name ?? string.Empty,
                    killedNpc.Level,
                    killedNpc.CurrentRegionID);
            }
        }

        private bool RecordFirstWorldSignalForPlayer(GamePlayer player, string playerKey, string playerName, IEnumerable<string> signals)
        {
            foreach (string signal in signals ?? Array.Empty<string>())
            {
                if (RecordWorldSignalForPlayer(player, playerKey, playerName, signal))
                    return true;
            }

            return false;
        }

        private bool RecordWorldSignalForPlayer(GamePlayer player, string playerKey, string playerName, string signal)
        {
            if (player == null || string.IsNullOrWhiteSpace(playerKey) || string.IsNullOrWhiteSpace(signal))
                return false;

            DynamicQuestDefinition quest;
            WorldSignalRecordResult result;
            lock (m_lock)
                result = RecordWorldSignalLocked(playerKey, playerName, signal, player, out quest);

            if (result == WorldSignalRecordResult.Ignored || quest == null)
                return false;

            if (result == WorldSignalRecordResult.Pending)
                return true;

            if (TryFinishCompletedNpcLessQuest(player, playerKey, playerName, quest))
                return true;

            DynamicQuestProgressItem item = GetProgressSnapshot(player).Active
                .FirstOrDefault(active => string.Equals(active.QuestId, quest.Id, StringComparison.OrdinalIgnoreCase));
            if (item != null)
                player.Out.SendMessage($"{quest.Title}: {DescribeCurrentObjective(item)}", eChatType.CT_System, eChatLoc.CL_SystemWindow);

            return true;
        }

        public IList<DynamicQuestDefinition> GetQuests()
        {
            lock (m_lock)
                return m_quests.Values.OrderBy(quest => quest.CreatedAt).ToList();
        }

        public object GetAutoAcceptDiagnostics(
            string playerKey,
            string playerName,
            int playerLevel,
            ushort regionId,
            int x,
            int y)
        {
            playerKey = (playerKey ?? string.Empty).Trim();
            playerName = (playerName ?? string.Empty).Trim();
            EnsurePlayerProgressLoaded(playerKey, playerName);

            List<object> triggers = new();
            lock (m_lock)
            {
                foreach (string trigger in BuildAutoAcceptTriggers(regionId, DateTime.UtcNow))
                {
                    string capturedTrigger = trigger;
                    List<object> candidates = m_quests.Values
                        .Where(quest => !RequiresStartNpc(quest) && quest.StartMode == DynamicQuestStartMode.AutoAccept)
                        .OrderBy(quest => quest.CreatedAt)
                        .Select(quest => new
                        {
                            questId = quest.Id ?? string.Empty,
                            quest.Title,
                            quest.TargetName,
                            quest.MinLevel,
                            quest.MaxLevel,
                            quest.CreatedAt,
                            triggerMatches = QuestTriggerMatches(quest, capturedTrigger),
                            playerLevelMatches = PlayerLevelMatchesQuest(quest, playerLevel),
                            hasCompleted = HasCompletedQuest(playerKey, quest.Id),
                            hasCompletedStoryFamily = HasCompletedStoryFamily(playerKey, quest),
                            hasProgress = HasProgress(playerKey, quest.Id),
                            hasActiveStoryFamily = HasActiveStoryFamily(playerKey, quest),
                            insideStartScope = IsInsideAutoAcceptStartScope(quest, regionId, x, y),
                            startScopes = EnumerateAutoAcceptStartObjectives(NormalizeQuest(quest))
                                .Where(objective => objective != null)
                                .Select(objective => new
                                {
                                    regionId = objective.RegionId,
                                    x = objective.X,
                                    y = objective.Y,
                                    z = objective.Z,
                                    radius = objective.Radius,
                                    locationName = objective.LocationName
                                })
                                .ToList(),
                            offerBlockedReasons = BuildAutoAcceptOfferBlockReasons(playerKey, quest, playerLevel, regionId, x, y, capturedTrigger),
                            tags = quest.Tags ?? Array.Empty<string>()
                        })
                        .Cast<object>()
                        .ToList();

                    triggers.Add(new
                    {
                        trigger = capturedTrigger,
                        candidates
                    });
                }
            }

            return new
            {
                enabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                playerKey,
                playerName,
                playerLevel,
                regionId,
                x,
                y,
                triggers
            };
        }

        public DynamicQuestProgressSnapshot GetProgressSnapshot(GamePlayer player)
        {
            if (player == null)
                return GetProgressSnapshot(string.Empty, string.Empty, false);

            return GetProgressSnapshot(GetPlayerKey(player), player.Name ?? string.Empty, true);
        }

        public DynamicQuestProgressSnapshot GetProgressSnapshot(string playerKey, string playerName = "", bool online = false)
        {
            playerKey = (playerKey ?? string.Empty).Trim();
            playerName = (playerName ?? string.Empty).Trim();
            EnsurePlayerProgressLoaded(playerKey, playerName);

            List<DynamicQuestProgressItem> active = new();
            List<string> completedQuestIds = new();

            lock (m_lock)
            {
                if (!string.IsNullOrWhiteSpace(playerKey) &&
                    m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                {
                    foreach (DynamicQuestProgress progress in progressList)
                    {
                        if (!TryGetQuestForProgress(progress, out DynamicQuestDefinition quest))
                            continue;

                        DynamicQuestDefinition normalizedQuest = NormalizeQuest(quest);
                        if (ShouldHideProgressFromActiveSnapshot(normalizedQuest, progress))
                            continue;

                        active.Add(BuildProgressItemLocked(playerKey, normalizedQuest, progress, DateTime.UtcNow));
                    }
                }

                if (!string.IsNullOrWhiteSpace(playerKey) &&
                    m_playerCompletedQuestIds.TryGetValue(playerKey, out HashSet<string> completed))
                {
                    completedQuestIds = completed
                        .Where(id => !string.IsNullOrWhiteSpace(id))
                        .OrderBy(id => id, StringComparer.OrdinalIgnoreCase)
                        .ToList();
                }
            }

            return new DynamicQuestProgressSnapshot
            {
                Enabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                Player = string.IsNullOrWhiteSpace(playerName) ? playerKey : playerName,
                PlayerKey = playerKey,
                Online = online,
                GeneratedAt = DateTime.UtcNow,
                Active = active.OrderBy(item => item.AcceptedAt).ToList(),
                CompletedQuestIds = completedQuestIds
            };
        }

        public DynamicQuestWorldMemorySnapshot GetWorldMemorySnapshot(GamePlayer player)
        {
            if (player == null)
                return GetWorldMemorySnapshot(string.Empty, string.Empty, false);

            return GetWorldMemorySnapshot(GetPlayerKey(player), player.Name ?? string.Empty, true);
        }

        public DynamicQuestWorldMemorySnapshot GetWorldMemorySnapshot(string playerKey, string playerName = "", bool online = false)
        {
            playerKey = (playerKey ?? string.Empty).Trim();
            playerName = (playerName ?? string.Empty).Trim();
            EnsurePlayerProgressLoaded(playerKey, playerName);

            List<string> completedQuestIds = new();
            List<string> completedStoryFamilyIds = new();
            List<string> signals = new();

            lock (m_lock)
            {
                if (!string.IsNullOrWhiteSpace(playerKey) &&
                    m_playerCompletedQuestIds.TryGetValue(playerKey, out HashSet<string> completed))
                {
                    completedQuestIds = completed
                        .Where(id => !string.IsNullOrWhiteSpace(id))
                        .OrderBy(id => id, StringComparer.OrdinalIgnoreCase)
                        .ToList();
                }

                if (!string.IsNullOrWhiteSpace(playerKey) &&
                    m_playerCompletedStoryFamilyIds.TryGetValue(playerKey, out HashSet<string> completedFamilies))
                {
                    completedStoryFamilyIds = completedFamilies
                        .Where(id => !string.IsNullOrWhiteSpace(id))
                        .OrderBy(id => id, StringComparer.OrdinalIgnoreCase)
                        .ToList();
                }

                if (!string.IsNullOrWhiteSpace(playerKey) &&
                    m_playerWorldMemorySignals.TryGetValue(playerKey, out HashSet<string> memorySignals))
                {
                    signals = memorySignals
                        .Where(signal => !string.IsNullOrWhiteSpace(signal))
                        .OrderBy(signal => signal, StringComparer.OrdinalIgnoreCase)
                        .ToList();
                }
            }

            return new DynamicQuestWorldMemorySnapshot
            {
                Enabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                Player = string.IsNullOrWhiteSpace(playerName) ? playerKey : playerName,
                PlayerKey = playerKey,
                Online = online,
                GeneratedAt = DateTime.UtcNow,
                CompletedQuestIds = completedQuestIds,
                CompletedStoryFamilyIds = completedStoryFamilyIds,
                Signals = signals
            };
        }

        public DynamicQuestWorldImpactSummary GetWorldImpactSummary(int limit = 50)
        {
            int safeLimit = Math.Clamp(limit <= 0 ? 50 : limit, 1, 500);

            lock (m_lock)
            {
                List<DynamicQuestWorldImpactRecord> recent = m_worldImpactRecords
                    .OrderByDescending(record => record.At)
                    .Take(safeLimit)
                    .Select(CloneWorldImpactRecord)
                    .ToList();

                return new DynamicQuestWorldImpactSummary
                {
                    Enabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                    GeneratedAt = DateTime.UtcNow,
                    Limit = safeLimit,
                    TotalRecorded = m_worldImpactRecords.Count,
                    ByRegion = m_worldImpactRecords
                        .GroupBy(record => new { record.RegionId, record.Realm })
                        .OrderByDescending(group => group.Max(record => record.At))
                        .ThenBy(group => group.Key.RegionId)
                        .Take(safeLimit)
                        .Select(group => new DynamicQuestWorldImpactRegionSummary
                        {
                            RegionId = group.Key.RegionId,
                            Realm = group.Key.Realm,
                            CompletionCount = group.Count(),
                            LastImpactAt = group.Max(record => record.At)
                        })
                        .ToList(),
                    Recent = recent
                };
            }
        }

        public DynamicQuestValidationSnapshot GetValidationSnapshot(int limit = 100)
        {
            limit = Math.Clamp(limit <= 0 ? 100 : limit, 1, 500);
            List<DynamicQuestDefinition> quests;

            lock (m_lock)
                quests = m_quests.Values.ToList();

            List<DynamicQuestValidationItem> items = quests
                .OrderBy(quest => quest.StartRegionId)
                .ThenBy(quest => quest.Title, StringComparer.OrdinalIgnoreCase)
                .Take(limit)
                .Select(BuildValidationItem)
                .ToList();

            return new DynamicQuestValidationSnapshot
            {
                Enabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                GeneratedAt = DateTime.UtcNow,
                Limit = limit,
                TotalQuests = quests.Count,
                ValidQuests = items.Count(item => item.Valid),
                InvalidQuests = items.Count(item => !item.Valid),
                Items = items
            };
        }

        public DynamicQuestCinematicCatalogSnapshot GetCinematicCatalogSnapshot(int limit = 80)
        {
            limit = Math.Clamp(limit <= 0 ? 80 : limit, 1, 500);
            DynamicQuestCinematicModelEntry[] props = DynamicQuestCinematicCatalog.BuildPropCatalogSnapshot();
            DynamicQuestCinematicModelEntry[] npcs = DynamicQuestCinematicCatalog.BuildNpcCatalogSnapshot();

            return new DynamicQuestCinematicCatalogSnapshot
            {
                Enabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                GeneratedAt = DateTime.UtcNow,
                Limit = limit,
                PropCount = props.Length,
                NpcCount = npcs.Length,
                Props = props
                    .OrderByDescending(entry => string.Equals(entry.Source, "default_prop", StringComparison.OrdinalIgnoreCase))
                    .ThenBy(entry => entry.Category, StringComparer.OrdinalIgnoreCase)
                    .ThenBy(entry => entry.Model)
                    .Take(limit)
                    .Select(ToCinematicCatalogItem)
                    .ToList(),
                Npcs = npcs
                    .OrderByDescending(entry => string.Equals(entry.Source, "default_npc", StringComparison.OrdinalIgnoreCase))
                    .ThenBy(entry => entry.Category, StringComparer.OrdinalIgnoreCase)
                    .ThenBy(entry => entry.Model)
                    .Take(limit)
                    .Select(ToCinematicCatalogItem)
                    .ToList()
            };
        }

        public DynamicQuestCinematicPlanSnapshot GetCinematicPlanSnapshot(string questId)
        {
            questId = (questId ?? string.Empty).Trim();
            DynamicQuestDefinition quest = null;
            lock (m_lock)
            {
                if (!string.IsNullOrWhiteSpace(questId) &&
                    m_quests.TryGetValue(questId, out DynamicQuestDefinition found))
                {
                    quest = NormalizeQuest(found);
                }
            }

            if (quest == null)
            {
                return new DynamicQuestCinematicPlanSnapshot
                {
                    Enabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                    GeneratedAt = DateTime.UtcNow,
                    Found = false,
                    QuestId = questId
                };
            }

            List<DynamicQuestCinematicPlanItem> actions = BuildCinematicPlanItems(quest);
            return new DynamicQuestCinematicPlanSnapshot
            {
                Enabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                GeneratedAt = DateTime.UtcNow,
                Found = true,
                QuestId = quest.Id ?? string.Empty,
                Title = quest.Title ?? string.Empty,
                Realm = quest.Realm ?? string.Empty,
                StartRegionId = quest.StartRegionId,
                NodeCount = (quest.Nodes ?? Array.Empty<DynamicQuestNode>()).Count(node => node != null),
                ActionCount = actions.Count,
                TotalActorCount = actions.Where(action => action.SpawnNpcActor).Sum(action => Math.Max(0, action.ActorCount)),
                MaxActorsPerAction = GetConfiguredCinematicMaxActorsPerAction(),
                Actions = actions
            };
        }

        public DynamicQuestProgressSummary GetProgressSummary(int limit = 100)
        {
            limit = Math.Clamp(limit <= 0 ? 100 : limit, 1, 500);
            DateTime generatedAt = DateTime.UtcNow;
            List<DynamicQuestProgressSummaryItem> active = new();
            int loadedPlayerCount;

            IList<DbDynamicQuestProgress> rows = m_progressRepository.GetActive(limit) ?? Array.Empty<DbDynamicQuestProgress>();
            lock (m_lock)
            {
                loadedPlayerCount = m_loadedPlayerKeys.Count;
                foreach (DbDynamicQuestProgress row in rows)
                {
                    if (row == null || string.IsNullOrWhiteSpace(row.PlayerKey) || string.IsNullOrWhiteSpace(row.QuestId))
                        continue;

                    DynamicQuestProgress progress = FromRow(row);
                    if (!TryGetQuestForProgress(progress, out DynamicQuestDefinition quest))
                        continue;

                    DynamicQuestDefinition normalizedQuest = NormalizeQuest(quest);
                    if (ShouldHideProgressFromActiveSnapshot(normalizedQuest, progress))
                        continue;

                    DynamicQuestProgressItem item = BuildProgressItemLocked(row.PlayerKey, normalizedQuest, progress, generatedAt);
                    active.Add(new DynamicQuestProgressSummaryItem
                    {
                        Player = string.IsNullOrWhiteSpace(row.PlayerName) ? row.PlayerKey : row.PlayerName,
                        PlayerKey = row.PlayerKey,
                        QuestId = item.QuestId,
                        Title = item.Title,
                        CurrentNodeId = item.CurrentNodeId,
                        CurrentNodeType = item.CurrentNodeType,
                        StalledReason = item.StalledReason,
                        LastEventType = item.LastEventType,
                        CurrentNodeElapsedSeconds = item.CurrentNodeElapsedSeconds,
                        UpdatedAt = item.UpdatedAt,
                        PendingWorldSignals = item.PendingWorldSignals
                    });
                }
            }

            return new DynamicQuestProgressSummary
            {
                Enabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                GeneratedAt = generatedAt,
                Limit = limit,
                LoadedPlayerCount = loadedPlayerCount,
                ActiveProgressCount = active.Count,
                Active = active
                    .OrderByDescending(item => item.CurrentNodeElapsedSeconds)
                    .ThenBy(item => item.Player, StringComparer.OrdinalIgnoreCase)
                    .Take(limit)
                    .ToList(),
                ByStalledReason = active
                    .GroupBy(item => string.IsNullOrWhiteSpace(item.StalledReason) ? "unknown" : item.StalledReason, StringComparer.OrdinalIgnoreCase)
                    .OrderByDescending(group => group.Count())
                    .ThenBy(group => group.Key, StringComparer.OrdinalIgnoreCase)
                    .ToDictionary(group => group.Key, group => group.Count(), StringComparer.OrdinalIgnoreCase),
                ByNodeType = active
                    .GroupBy(item => item.CurrentNodeType.ToString(), StringComparer.OrdinalIgnoreCase)
                    .OrderByDescending(group => group.Count())
                    .ThenBy(group => group.Key, StringComparer.OrdinalIgnoreCase)
                    .ToDictionary(group => group.Key, group => group.Count(), StringComparer.OrdinalIgnoreCase)
            };
        }

        public DynamicQuestProgressCleanupPlan GetProgressCleanupPlan(int limit = 100, int staleThresholdSeconds = 3600)
        {
            limit = Math.Clamp(limit <= 0 ? 100 : limit, 1, 500);
            staleThresholdSeconds = Math.Clamp(staleThresholdSeconds <= 0 ? 3600 : staleThresholdSeconds, 60, 604800);

            DynamicQuestProgressSummary summary = GetProgressSummary(limit);
            List<DynamicQuestProgressCleanupPlanItem> candidates = summary.Active
                .Select(item => BuildCleanupPlanItem(item, staleThresholdSeconds))
                .Where(item => item.Stale || item.ShouldCancel || !string.Equals(item.ActionHint, "none", StringComparison.OrdinalIgnoreCase))
                .OrderByDescending(item => item.ShouldCancel)
                .ThenByDescending(item => item.CurrentNodeElapsedSeconds)
                .ThenBy(item => item.Player, StringComparer.OrdinalIgnoreCase)
                .Take(limit)
                .ToList();

            return new DynamicQuestProgressCleanupPlan
            {
                Enabled = summary.Enabled,
                GeneratedAt = summary.GeneratedAt,
                Limit = limit,
                StaleThresholdSeconds = staleThresholdSeconds,
                CandidateCount = candidates.Count,
                CancelCandidateCount = candidates.Count(item => item.ShouldCancel),
                Candidates = candidates,
                ByActionHint = candidates
                    .GroupBy(item => item.ActionHint, StringComparer.OrdinalIgnoreCase)
                    .OrderByDescending(group => group.Count())
                    .ThenBy(group => group.Key, StringComparer.OrdinalIgnoreCase)
                    .ToDictionary(group => group.Key, group => group.Count(), StringComparer.OrdinalIgnoreCase)
            };
        }

        public DynamicQuestProgressCleanupCancelResult CancelCompletedCleanupCandidates(
            int limit = 100,
            int staleThresholdSeconds = 3600,
            string reason = "")
        {
            limit = Math.Clamp(limit <= 0 ? 100 : limit, 1, 500);
            staleThresholdSeconds = Math.Clamp(staleThresholdSeconds <= 0 ? 3600 : staleThresholdSeconds, 60, 604800);
            reason = string.IsNullOrWhiteSpace(reason) ? "cleanup_completed_active_progress" : reason.Trim();
            DateTime generatedAt = DateTime.UtcNow;
            List<DynamicQuestProgressCleanupPlanItem> cancelled = new();
            IList<DbDynamicQuestProgress> rows = m_progressRepository.GetActive(limit) ?? Array.Empty<DbDynamicQuestProgress>();

            lock (m_lock)
            {
                foreach (DbDynamicQuestProgress row in rows)
                {
                    if (row == null || string.IsNullOrWhiteSpace(row.PlayerKey) || string.IsNullOrWhiteSpace(row.QuestId))
                        continue;

                    DynamicQuestProgress progress = FromRow(row);
                    if (!TryGetQuestForProgress(progress, out DynamicQuestDefinition quest))
                        continue;

                    DynamicQuestDefinition normalizedQuest = NormalizeQuest(quest);
                    if (ShouldHideProgressFromActiveSnapshot(normalizedQuest, progress))
                        continue;

                    DynamicQuestProgressItem progressItem = BuildProgressItemLocked(row.PlayerKey, normalizedQuest, progress, generatedAt);
                    DynamicQuestProgressCleanupPlanItem cleanupItem = BuildCleanupPlanItem(new DynamicQuestProgressSummaryItem
                    {
                        Player = string.IsNullOrWhiteSpace(row.PlayerName) ? row.PlayerKey : row.PlayerName,
                        PlayerKey = row.PlayerKey,
                        QuestId = progressItem.QuestId,
                        Title = progressItem.Title,
                        CurrentNodeId = progressItem.CurrentNodeId,
                        CurrentNodeType = progressItem.CurrentNodeType,
                        StalledReason = progressItem.StalledReason,
                        LastEventType = progressItem.LastEventType,
                        CurrentNodeElapsedSeconds = progressItem.CurrentNodeElapsedSeconds,
                        UpdatedAt = progressItem.UpdatedAt,
                        PendingWorldSignals = progressItem.PendingWorldSignals
                    }, staleThresholdSeconds);

                    if (!cleanupItem.ShouldCancel)
                        continue;

                    CancelRepositoryProgressRow(row, reason);
                    if (m_playerProgress.TryGetValue(row.PlayerKey, out List<DynamicQuestProgress> progressList))
                    {
                        progressList.RemoveAll(item =>
                            item == null ||
                            string.Equals(item.QuestId, row.QuestId, StringComparison.OrdinalIgnoreCase));
                    }

                    cancelled.Add(cleanupItem);
                }
            }

            return new DynamicQuestProgressCleanupCancelResult
            {
                Enabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                GeneratedAt = generatedAt,
                Limit = limit,
                StaleThresholdSeconds = staleThresholdSeconds,
                Reason = reason,
                CancelledCount = cancelled.Count,
                Cancelled = cancelled
            };
        }

        public DynamicQuestProgressCleanupAdvanceResult AdvanceTimedOutCleanupCandidates(int limit = 100, string reason = "")
        {
            limit = Math.Clamp(limit <= 0 ? 100 : limit, 1, 500);
            reason = string.IsNullOrWhiteSpace(reason) ? "cleanup_timeout" : reason.Trim();
            DateTime generatedAt = DateTime.UtcNow;
            List<DynamicQuestProgressCleanupPlanItem> advanced = new();
            IList<DbDynamicQuestProgress> rows = m_progressRepository.GetActive(limit) ?? Array.Empty<DbDynamicQuestProgress>();

            foreach (DbDynamicQuestProgress row in rows)
            {
                if (row == null || string.IsNullOrWhiteSpace(row.PlayerKey) || string.IsNullOrWhiteSpace(row.QuestId))
                    continue;

                EnsurePlayerProgressLoaded(row.PlayerKey, row.PlayerName);

                lock (m_lock)
                {
                    if (!m_playerProgress.TryGetValue(row.PlayerKey, out List<DynamicQuestProgress> progressList))
                        continue;

                    DynamicQuestProgress progress = progressList.FirstOrDefault(item =>
                        item != null &&
                        string.Equals(item.QuestId, row.QuestId, StringComparison.OrdinalIgnoreCase));
                    if (progress == null || progress.Failed || progress.Completed || progress.IsComplete)
                        continue;

                    if (!TryGetQuestForProgress(progress, out DynamicQuestDefinition quest))
                        continue;

                    DynamicQuestDefinition normalizedQuest = NormalizeQuest(quest);
                    DynamicQuestNode node = GetCurrentNode(normalizedQuest, progress);
                    DynamicQuestEdge edge = FindAutoAdvanceEdge(node, progress, 1, generatedAt);
                    if (edge?.Condition != DynamicQuestEdgeCondition.TimedOut)
                        continue;

                    DynamicQuestProgressItem progressItem = BuildProgressItemLocked(row.PlayerKey, normalizedQuest, progress, generatedAt);
                    DynamicQuestProgressCleanupPlanItem cleanupItem = BuildCleanupPlanItem(new DynamicQuestProgressSummaryItem
                    {
                        Player = string.IsNullOrWhiteSpace(row.PlayerName) ? row.PlayerKey : row.PlayerName,
                        PlayerKey = row.PlayerKey,
                        QuestId = progressItem.QuestId,
                        Title = progressItem.Title,
                        CurrentNodeId = progressItem.CurrentNodeId,
                        CurrentNodeType = progressItem.CurrentNodeType,
                        StalledReason = progressItem.StalledReason,
                        LastEventType = progressItem.LastEventType,
                        CurrentNodeElapsedSeconds = progressItem.CurrentNodeElapsedSeconds,
                        UpdatedAt = progressItem.UpdatedAt,
                        PendingWorldSignals = progressItem.PendingWorldSignals
                    }, 60);

                    AdvanceWithEdgeLocked(row.PlayerKey, row.PlayerName, normalizedQuest, progress, node, edge, reason);
                    TryAutoAdvanceFromCurrentNodeLocked(row.PlayerKey, row.PlayerName, normalizedQuest, progress, reason);
                    SaveProgress(row.PlayerKey, row.PlayerName, progress);
                    advanced.Add(cleanupItem);
                }
            }

            return new DynamicQuestProgressCleanupAdvanceResult
            {
                Enabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                GeneratedAt = generatedAt,
                Limit = limit,
                Reason = reason,
                AdvancedCount = advanced.Count,
                Advanced = advanced
            };
        }

        private static DynamicQuestProgressCleanupPlanItem BuildCleanupPlanItem(DynamicQuestProgressSummaryItem item, int staleThresholdSeconds)
        {
            bool stale = item.CurrentNodeElapsedSeconds >= staleThresholdSeconds;
            string actionHint = GetCleanupActionHint(item, stale);
            bool shouldCancel = string.Equals(actionHint, "cancel_completed_active_progress", StringComparison.OrdinalIgnoreCase);

            return new DynamicQuestProgressCleanupPlanItem
            {
                Player = item.Player,
                PlayerKey = item.PlayerKey,
                QuestId = item.QuestId,
                Title = item.Title,
                CurrentNodeId = item.CurrentNodeId,
                CurrentNodeType = item.CurrentNodeType,
                StalledReason = item.StalledReason,
                CurrentNodeElapsedSeconds = item.CurrentNodeElapsedSeconds,
                Stale = stale,
                ShouldCancel = shouldCancel,
                ActionHint = actionHint,
                UpdatedAt = item.UpdatedAt,
                PendingWorldSignals = item.PendingWorldSignals
            };
        }

        private static string GetCleanupActionHint(DynamicQuestProgressSummaryItem item, bool stale)
        {
            string stalledReason = item?.StalledReason ?? string.Empty;
            if (string.Equals(stalledReason, "complete", StringComparison.OrdinalIgnoreCase))
                return stale ? "cancel_completed_active_progress" : "wait_for_reward_turnin";

            if (!stale)
                return "none";

            if (string.Equals(stalledReason, "waiting_for_kill_credit", StringComparison.OrdinalIgnoreCase))
                return "inspect_target_or_cancel";
            if (string.Equals(stalledReason, "waiting_for_choice", StringComparison.OrdinalIgnoreCase))
                return "inspect_choice_dialog";
            if (string.Equals(stalledReason, "waiting_for_npc_interaction", StringComparison.OrdinalIgnoreCase))
                return "inspect_npc_interaction";
            if (string.Equals(stalledReason, "waiting_for_location", StringComparison.OrdinalIgnoreCase))
                return "inspect_location_objective";
            if (string.Equals(stalledReason, "waiting_for_timeout", StringComparison.OrdinalIgnoreCase))
                return "advance_timed_out_progress";
            if (stalledReason.StartsWith("waiting_for_world_signal", StringComparison.OrdinalIgnoreCase))
                return "inspect_world_signal";
            if (string.Equals(stalledReason, "pending_world_signal", StringComparison.OrdinalIgnoreCase))
                return "inspect_pending_world_signal";

            return "inspect_progress";
        }

        public DynamicQuestTimelineSnapshot GetTimelineSnapshot(GamePlayer player, int limit = 50)
        {
            if (player == null)
                return GetTimelineSnapshot(string.Empty, string.Empty, false, limit);

            return GetTimelineSnapshot(GetPlayerKey(player), player.Name ?? string.Empty, true, limit);
        }

        public DynamicQuestTimelineSnapshot GetTimelineSnapshot(string playerKey, string playerName = "", bool online = false, int limit = 50)
        {
            playerKey = (playerKey ?? string.Empty).Trim();
            playerName = (playerName ?? string.Empty).Trim();
            EnsurePlayerProgressLoaded(playerKey, playerName);
            limit = Math.Clamp(limit <= 0 ? 50 : limit, 1, MaxPlayerTimelineEvents);

            List<DynamicQuestTimelineEvent> events;
            lock (m_lock)
            {
                events = FindTimelineEventsLocked(playerKey, playerName, limit);
            }

            return new DynamicQuestTimelineSnapshot
            {
                Enabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                Player = string.IsNullOrWhiteSpace(playerName) ? playerKey : playerName,
                PlayerKey = playerKey,
                Online = online,
                GeneratedAt = DateTime.UtcNow,
                Events = events,
                PresentationBeats = BuildPresentationBeatObservations(events)
            };
        }

        private List<DynamicQuestTimelineEvent> FindTimelineEventsLocked(string playerKey, string playerName, int limit)
        {
            IEnumerable<DynamicQuestTimelineEvent> timeline = Array.Empty<DynamicQuestTimelineEvent>();

            if (!string.IsNullOrWhiteSpace(playerKey) &&
                m_playerTimeline.TryGetValue(playerKey, out List<DynamicQuestTimelineEvent> keyedTimeline))
            {
                timeline = keyedTimeline;
            }
            else if (!string.IsNullOrWhiteSpace(playerName) &&
                     m_playerTimeline.TryGetValue(playerName, out List<DynamicQuestTimelineEvent> namedTimeline))
            {
                timeline = namedTimeline;
            }
            else if (!string.IsNullOrWhiteSpace(playerName))
            {
                timeline = m_playerTimeline.Values
                    .SelectMany(items => items)
                    .Where(item => string.Equals(item.PlayerName, playerName, StringComparison.OrdinalIgnoreCase));
            }

            return timeline
                .OrderByDescending(item => item.At)
                .Take(limit)
                .OrderBy(item => item.At)
                .Select(CloneTimelineEvent)
                .ToList();
        }

        public int ClearAll()
        {
            lock (m_lock)
            {
                int count = m_quests.Count;
                m_quests.Clear();
                m_playerProgress.Clear();
                m_playerCompletedQuestIds.Clear();
                m_playerCompletedStoryFamilyIds.Clear();
                m_playerWorldMemorySignals.Clear();
                m_playerTimeline.Clear();
                ClearAllCinematicMarkersLocked();
                m_worldImpactRecords.Clear();
                m_loadedPlayerKeys.Clear();
                return count;
            }
        }

        internal DynamicQuestDefinition NormalizeQuestForTest(DynamicQuestDefinition quest)
        {
            return NormalizeQuest(quest);
        }

        private static DynamicQuestDefinition NormalizeQuest(DynamicQuestDefinition quest)
        {
            if (quest == null)
                return null;

            quest.Realm = ResolveQuestRealm(quest);

            if (quest.Nodes != null && quest.Nodes.Count > 0)
            {
                EnsureWorldSignalFallbackEdges(quest);
                return quest;
            }

            quest.GraphVersion = Math.Max(1, quest.GraphVersion);
            quest.StartNodeId = "kill";
            bool requiresStartNpc = RequiresStartNpc(quest);
            List<DynamicQuestNode> nodes = new()
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
                        new DynamicQuestEdge
                        {
                            ToNodeId = requiresStartNpc ? "return" : "complete",
                            Condition = DynamicQuestEdgeCondition.ObjectiveComplete
                        }
                    }
                }
            };

            if (requiresStartNpc)
            {
                nodes.Add(
                new()
                {
                    Id = "return",
                    Type = DynamicQuestNodeType.ReturnToNpc,
                    Title = "보고",
                    Text = quest.ProgressText,
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
                });
            }

            nodes.Add(
                new()
                {
                    Id = "complete",
                    Type = DynamicQuestNodeType.Complete,
                    Title = "완료",
                    Text = quest.FinishText
                });

            quest.Nodes = nodes;
            EnsureWorldSignalFallbackEdges(quest);

            return quest;
        }

        private static void EnsureWorldSignalFallbackEdges(DynamicQuestDefinition quest)
        {
            if (quest?.Nodes == null)
                return;

            foreach (DynamicQuestNode node in quest.Nodes)
            {
                if (node?.Edges == null || node.Edges.Count == 0)
                    continue;

                if (!node.Edges.Any(edge => edge?.Condition == DynamicQuestEdgeCondition.WorldSignal) ||
                    node.Edges.Any(edge => edge?.Condition == DynamicQuestEdgeCondition.TimedOut))
                {
                    continue;
                }

                int fallbackPriority = node.Edges.Max(edge => edge?.Priority ?? 0) + 1;
                node.Edges = node.Edges.Concat(new[]
                {
                    new DynamicQuestEdge
                    {
                        ToNodeId = "complete",
                        Condition = DynamicQuestEdgeCondition.TimedOut,
                        ConditionValue = DynamicQuestWorldSignalPolicy.FallbackTimeoutSeconds,
                        Priority = fallbackPriority
                    }
                }).ToArray();
            }
        }

        private static string ResolveQuestRealm(DynamicQuestDefinition quest)
        {
            string tagRealm = (quest?.Tags ?? Array.Empty<string>())
                .Select(tag => (tag ?? string.Empty).Trim())
                .Where(tag => tag.StartsWith("realm:", StringComparison.OrdinalIgnoreCase))
                .Select(tag => tag.Substring("realm:".Length).Trim())
                .FirstOrDefault(value => !string.IsNullOrWhiteSpace(value));

            if (!string.IsNullOrWhiteSpace(tagRealm))
                return tagRealm;

            if (!string.IsNullOrWhiteSpace(quest?.Realm))
                return quest.Realm.Trim();

            return quest?.StartRegionId switch
            {
                >= 1 and < 100 => "Albion",
                >= 100 and < 200 => "Midgard",
                >= 200 and < 300 => "Hibernia",
                _ => "Unknown"
            };
        }

        public bool TryAcceptWorldQuest(GamePlayer player, string questId, string source = "world_offer", bool showFailureMessage = true)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED || player == null || string.IsNullOrWhiteSpace(questId))
                return false;

            string playerKey = GetPlayerKey(player);
            EnsurePlayerProgressLoaded(playerKey, player.Name ?? string.Empty);

            if (!TryGetQuest(questId, out DynamicQuestDefinition quest))
                return false;

            DynamicQuestDefinition normalizedQuest = NormalizeQuest(quest);
            if (RequiresStartNpc(normalizedQuest))
                return false;

            bool accepted = AcceptQuestByPlayerKey(
                playerKey,
                player.Name ?? string.Empty,
                player,
                null,
                normalizedQuest,
                source,
                showFailureMessage);

            if (accepted)
            {
                player.Out.SendMessage($"{normalizedQuest.Title}\n\n{normalizedQuest.ProgressText}", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                SyncDynamicQuestJournal(player);
            }

            return accepted;
        }

        public bool TryAcceptAvailableWorldQuest(
            GamePlayer player,
            string trigger,
            bool showFailureMessage = true,
            bool includeAutoAccept = true)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED || player == null)
                return false;

            string playerKey = GetPlayerKey(player);
            EnsurePlayerProgressLoaded(playerKey, player.Name ?? string.Empty);
            DynamicQuestDefinition quest = GetAvailableWorldQuest(playerKey, player.Level, trigger, includeAutoAccept: includeAutoAccept);
            if (quest == null)
                return false;

            return TryAcceptWorldQuest(player, quest.Id, trigger, showFailureMessage);
        }

        private void AcceptQuest(GamePlayer player, GameNPC npc, DynamicQuestDefinition quest)
        {
            bool accepted = AcceptQuestByPlayerKey(
                GetPlayerKey(player),
                player?.Name ?? string.Empty,
                player,
                npc,
                quest,
                "npc_dialog",
                showFailureMessage: true);

            if (!accepted || player == null || npc == null)
                return;

            npc.SayTo(player, $"{quest.Title}\n\n{quest.ProgressText}\n\n목표: {quest.TargetName} {quest.TargetCount}마리 처치");
            player.Out.SendNPCsQuestEffect(npc, GetQuestIndicator(npc, player));
        }

        internal bool AcceptQuestForTest(string playerKey, string playerName, string questId, string source = "test")
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED || string.IsNullOrWhiteSpace(questId))
                return false;

            if (!TryGetQuest(questId, out DynamicQuestDefinition quest))
                return false;

            DynamicQuestDefinition normalizedQuest = NormalizeQuest(quest);
            return AcceptQuestByPlayerKey(
                playerKey,
                playerName,
                null,
                null,
                normalizedQuest,
                source,
                showFailureMessage: true);
        }

        internal bool AcceptAvailableWorldQuestForTest(
            string playerKey,
            string playerName,
            int playerLevel,
            string trigger)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED)
                return false;

            EnsurePlayerProgressLoaded(playerKey, playerName);
            DynamicQuestDefinition quest = GetAvailableWorldQuest(playerKey, playerLevel, trigger);
            if (quest == null)
                return false;

            return AcceptQuestByPlayerKey(
                playerKey,
                playerName,
                null,
                null,
                quest,
                trigger,
                showFailureMessage: false);
        }

        internal IList<string> GetAvailableWorldQuestIdsForTest(
            string playerKey,
            int playerLevel,
            string trigger,
            bool includeAutoAccept = true)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED)
                return Array.Empty<string>();

            EnsurePlayerProgressLoaded(playerKey, playerKey);
            return GetAvailableWorldQuests(
                    playerKey,
                    playerLevel,
                    trigger,
                    autoAcceptOnly: false,
                    includeAutoAccept: includeAutoAccept)
                .Select(quest => quest.Id)
                .ToList();
        }

        internal IList<string> BuildActiveJournalProgressIdsForTest(string playerKey, string playerName)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED)
                return Array.Empty<string>();

            EnsurePlayerProgressLoaded(playerKey, playerName);
            lock (m_lock)
                return BuildActiveJournalSnapshotsLocked(playerKey)
                    .Select(snapshot => snapshot.ProgressId)
                    .ToList();
        }

        internal bool AcceptAvailableRegionalAutoQuestForTest(
            string playerKey,
            string playerName,
            int playerLevel,
            ushort regionId)
        {
            return AcceptAvailableRegionalAutoQuestForTest(
                playerKey,
                playerName,
                playerLevel,
                regionId,
                x: 0,
                y: 0,
                requireStartScope: false);
        }

        internal bool AcceptAvailableRegionalAutoQuestForTest(
            string playerKey,
            string playerName,
            int playerLevel,
            ushort regionId,
            int x,
            int y)
        {
            return AcceptAvailableRegionalAutoQuestForTest(
                playerKey,
                playerName,
                playerLevel,
                regionId,
                x,
                y,
                requireStartScope: true);
        }

        private bool AcceptAvailableRegionalAutoQuestForTest(
            string playerKey,
            string playerName,
            int playerLevel,
            ushort regionId,
            int x,
            int y,
            bool requireStartScope)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED)
                return false;

            EnsurePlayerProgressLoaded(playerKey, playerName);

            foreach (string trigger in BuildAutoAcceptTriggers(regionId, DateTime.UtcNow))
            {
                foreach (DynamicQuestDefinition quest in GetAvailableWorldQuests(playerKey, playerLevel, trigger, autoAcceptOnly: true))
                {
                    if (requireStartScope && !IsInsideAutoAcceptStartScope(quest, regionId, x, y))
                        continue;

                    return AcceptQuestByPlayerKey(
                        playerKey,
                        playerName,
                        null,
                        null,
                        quest,
                        trigger,
                        showFailureMessage: false);
                }
            }

            return false;
        }

        private bool AcceptQuestByPlayerKey(
            string playerKey,
            string playerName,
            GamePlayer player,
            GameNPC npc,
            DynamicQuestDefinition quest,
            string source,
            bool showFailureMessage = true)
        {
            playerKey = (playerKey ?? string.Empty).Trim();
            playerName = (playerName ?? string.Empty).Trim();
            source = string.IsNullOrWhiteSpace(source) ? "quest_accepted" : source.Trim();

            if (string.IsNullOrWhiteSpace(playerKey) || quest == null)
                return false;

            EnsurePlayerProgressLoaded(playerKey, playerName);

            DynamicQuestDefinition normalizedQuest = NormalizeQuest(quest);
            if (RequiresStartNpc(normalizedQuest) && npc == null)
            {
                SendAcceptFailureMessage(player, showFailureMessage, "이 동적 퀘스트는 시작 NPC와 대화해야 합니다.");
                return false;
            }

            lock (m_lock)
            {
                if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                {
                    progressList = new List<DynamicQuestProgress>();
                    m_playerProgress[playerKey] = progressList;
                }

                int maxActive = Math.Max(1, Properties.KDAOC_DYNAMIC_QUEST_MAX_ACTIVE_PER_PLAYER);
                if (HasCompletedQuest(playerKey, normalizedQuest.Id))
                {
                    SendAcceptFailureMessage(player, showFailureMessage, "이미 완료한 동적 퀘스트입니다.");
                    return false;
                }

                if (HasCompletedStoryFamily(playerKey, normalizedQuest))
                {
                    SendAcceptFailureMessage(player, showFailureMessage, "이미 완료한 이야기 계열의 동적 퀘스트입니다.");
                    return false;
                }

                if (!HasStoryPrerequisites(playerKey, normalizedQuest))
                {
                    SendAcceptFailureMessage(player, showFailureMessage, "아직 이 이야기의 이전 단서를 충분히 발견하지 못했습니다.");
                    return false;
                }

                if (HasActiveStoryFamily(playerKey, normalizedQuest))
                {
                    SendAcceptFailureMessage(player, showFailureMessage, "이미 같은 이야기 계열의 동적 퀘스트를 진행 중입니다.");
                    return false;
                }

                if (progressList.Any(progress =>
                    progress != null &&
                    progress.QuestId == normalizedQuest.Id &&
                    IsProgressCountingAgainstActiveLimit(progress)))
                {
                    SendAcceptFailureMessage(player, showFailureMessage, "이미 받은 동적 퀘스트입니다.");
                    return false;
                }

                bool bypassActiveLimitForSameRegion = CanBypassActiveLimitForSameRegion(progressList, normalizedQuest, maxActive);
                if (!bypassActiveLimitForSameRegion && progressList.Count(IsProgressCountingAgainstActiveLimit) >= maxActive)
                    CancelAutoAcceptProgressForManualQuestLocked(playerKey, playerName, progressList, normalizedQuest, maxActive);

                bypassActiveLimitForSameRegion = CanBypassActiveLimitForSameRegion(progressList, normalizedQuest, maxActive);
                if (!bypassActiveLimitForSameRegion && progressList.Count(IsProgressCountingAgainstActiveLimit) >= maxActive)
                {
                    SendAcceptFailureMessage(player, showFailureMessage, "이미 진행 중인 동적 퀘스트가 있습니다.");
                    return false;
                }

                DynamicQuestProgress progress = new()
                {
                    QuestId = normalizedQuest.Id,
                    CurrentNodeId = normalizedQuest.StartNodeId,
                    QuestSnapshot = CloneQuestSnapshot(normalizedQuest),
                    BindingKey = normalizedQuest.BindingKey,
                    WorldRevision = normalizedQuest.WorldRevision
                };
                SetCurrentNodeEnteredAt(progress, DateTime.UtcNow);
                progressList.Add(progress);
                RecordTimelineEventLocked(playerKey, playerName, normalizedQuest.Id, "quest_accepted", nodeId: progress.CurrentNodeId, detail: source);
                RecordPresentationBeatsLocked(
                    playerKey,
                    playerName,
                    normalizedQuest,
                    progress.CurrentNodeId,
                    player,
                    npc,
                    "OnAccept");
                RecordStoryNodeEnteredLocked(
                    playerKey,
                    playerName,
                    normalizedQuest,
                    progress,
                    player,
                    npc,
                    npc != null ? "OnNpcInteract" : "OnNodeEnter");

                DynamicQuestNode startNode = GetCurrentNode(normalizedQuest, progress);
                if (npc != null && startNode?.Type == DynamicQuestNodeType.Talk && IsNpcObjective(startNode, npc))
                {
                    string fromNodeId = startNode.Id;
                    AdvanceFromNode(progress, normalizedQuest, startNode, DynamicQuestEdgeCondition.ObjectiveComplete, string.Empty);
                    RecordNodeTransitionLocked(playerKey, playerName, normalizedQuest.Id, progress, fromNodeId, "quest_accepted");
                    RecordStoryNodeEnteredLocked(playerKey, playerName, normalizedQuest, progress, player, npc, "OnNodeEnter");
                    TryConsumePendingWorldSignalsLocked(playerKey, playerName, normalizedQuest, progress, player, npc);
                }

                TryAutoAdvanceFromCurrentNodeLocked(
                    playerKey,
                    playerName,
                    normalizedQuest,
                    progress,
                    "quest_accepted",
                    GetPlayerPartySize(player),
                    player: player,
                    npc: npc);
                SaveProgress(playerKey, playerName, progress);
                SyncDynamicQuestJournal(player);
                return true;
            }
        }

        private static void SendAcceptFailureMessage(GamePlayer player, bool showFailureMessage, string message)
        {
            if (showFailureMessage && player != null && !string.IsNullOrWhiteSpace(message))
                player.Out.SendMessage(message, eChatType.CT_System, eChatLoc.CL_SystemWindow);
        }

        private bool CanBypassActiveLimitForSameRegion(
            List<DynamicQuestProgress> progressList,
            DynamicQuestDefinition incomingQuest,
            int maxActive)
        {
            if (progressList == null || incomingQuest == null || incomingQuest.StartRegionId == 0 || maxActive <= 0)
                return false;

            List<DynamicQuestDefinition> activeQuests = new();
            foreach (DynamicQuestProgress progress in progressList)
            {
                if (!IsProgressCountingAgainstActiveLimit(progress))
                    continue;

                if (!TryGetQuestForProgress(progress, out DynamicQuestDefinition activeQuest))
                    return false;

                DynamicQuestDefinition normalizedActiveQuest = NormalizeQuest(activeQuest);
                if (normalizedActiveQuest.StartRegionId == 0)
                    return false;

                activeQuests.Add(normalizedActiveQuest);
            }

            if (activeQuests.Count == 0 || activeQuests.Count < maxActive)
                return false;

            int activeRegionCount = activeQuests
                .Select(quest => quest.StartRegionId)
                .Distinct()
                .Count();
            if (activeRegionCount > maxActive)
                return false;

            return activeQuests.Any(quest => quest.StartRegionId == incomingQuest.StartRegionId);
        }

        public void SyncDynamicQuestJournal(GamePlayer player)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED || player == null)
                return;

            string playerKey = GetPlayerKey(player);
            string playerName = player.Name ?? string.Empty;
            EnsurePlayerProgressLoaded(playerKey, playerName);

            List<DynamicQuestJournalSnapshot> activeSnapshots;
            lock (m_lock)
                activeSnapshots = BuildActiveJournalSnapshotsLocked(playerKey);

            Dictionary<string, DynamicQuestJournalSnapshot> snapshotById = activeSnapshots
                .GroupBy(snapshot => snapshot.ProgressId, StringComparer.OrdinalIgnoreCase)
                .ToDictionary(group => group.Key, group => group.First(), StringComparer.OrdinalIgnoreCase);

            foreach (DynamicQuestJournalAdapter adapter in player.QuestList.Keys.OfType<DynamicQuestJournalAdapter>().ToList())
            {
                if (!snapshotById.TryGetValue(adapter.DynamicProgressId, out DynamicQuestJournalSnapshot snapshot))
                {
                    RemoveDynamicQuestJournalAdapter(player, adapter);
                    continue;
                }

                adapter.Update(snapshot.Title, snapshot.Description, snapshot.Level, snapshot.Step);
                player.Out.SendQuestUpdate(adapter);
            }

            HashSet<string> existingIds = player.QuestList.Keys
                .OfType<IDynamicQuestJournalAdapter>()
                .Select(adapter => adapter.DynamicProgressId)
                .ToHashSet(StringComparer.OrdinalIgnoreCase);

            foreach (DynamicQuestJournalSnapshot snapshot in activeSnapshots)
            {
                if (existingIds.Contains(snapshot.ProgressId))
                    continue;

                DynamicQuestJournalAdapter adapter = new(
                    snapshot.PlayerKey,
                    snapshot.QuestId,
                    snapshot.StartRegionId,
                    snapshot.Title,
                    snapshot.Description,
                    snapshot.Level,
                    snapshot.Step);

                player.AddQuest(adapter);
            }
        }

        private List<DynamicQuestJournalSnapshot> BuildActiveJournalSnapshotsLocked(string playerKey)
        {
            List<DynamicQuestJournalSnapshot> snapshots = new();
            if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                return snapshots;

            DateTime generatedAt = DateTime.UtcNow;
            foreach (DynamicQuestProgress progress in progressList)
            {
                if (!IsProgressCountingAgainstActiveLimit(progress) ||
                    !TryGetQuestForProgress(progress, out DynamicQuestDefinition quest))
                {
                    continue;
                }

                DynamicQuestDefinition normalizedQuest = NormalizeQuest(quest);
                DynamicQuestProgressItem item = BuildProgressItemLocked(playerKey, normalizedQuest, progress, generatedAt);
                snapshots.Add(new DynamicQuestJournalSnapshot
                {
                    PlayerKey = playerKey,
                    QuestId = progress.QuestId,
                    ProgressId = BuildJournalProgressId(playerKey, progress.QuestId),
                    StartRegionId = normalizedQuest.StartRegionId,
                    Title = normalizedQuest.Title,
                    Description = BuildJournalDescription(normalizedQuest, item),
                    Level = Math.Clamp(normalizedQuest.MinLevel, 1, 50),
                    Step = Math.Max(1, GetJournalStep(normalizedQuest, item.CurrentNodeId))
                });
            }

            return snapshots;
        }

        private static int GetJournalStep(DynamicQuestDefinition quest, string currentNodeId)
        {
            IList<DynamicQuestNode> nodes = quest?.Nodes ?? Array.Empty<DynamicQuestNode>();
            int index = nodes
                .Select((node, i) => new { node, i })
                .FirstOrDefault(item => string.Equals(item.node?.Id, currentNodeId, StringComparison.OrdinalIgnoreCase))
                ?.i ?? 0;
            return index + 1;
        }

        private static void RemoveDynamicQuestJournalAdapter(GamePlayer player, DynamicQuestJournalAdapter adapter)
        {
            if (player == null || adapter == null)
                return;

            if (player.QuestList.TryRemove(adapter, out byte index))
            {
                player.AvailableQuestIndexes.Enqueue(index);
                player.Out.SendQuestRemove(index);
            }
        }

        public bool CancelActiveProgressForPlayerQuest(GamePlayer player, string questId, string reason = "")
        {
            if (player == null || string.IsNullOrWhiteSpace(questId))
                return false;

            string playerKey = GetPlayerKey(player);
            string playerName = player.Name ?? string.Empty;
            reason = string.IsNullOrWhiteSpace(reason) ? "player_progress_cancelled" : reason.Trim();
            EnsurePlayerProgressLoaded(playerKey, playerName);
            bool cancelled = false;

            lock (m_lock)
            {
                if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                    return false;

                DynamicQuestProgress progress = progressList.FirstOrDefault(item =>
                    item != null &&
                    !item.Failed &&
                    !item.Completed &&
                    !item.IsComplete &&
                    string.Equals(item.QuestId, questId, StringComparison.OrdinalIgnoreCase));
                if (progress == null)
                    return false;

                progress.Failed = true;
                progress.CancelReason = reason;
                progress.UpdatedAt = DateTime.UtcNow;
                SaveProgress(playerKey, playerName, progress);
                RecordTimelineEventLocked(playerKey, playerName, progress.QuestId, "quest_cancelled", nodeId: progress.CurrentNodeId, detail: reason);
                CleanupCinematicMarkersLocked(playerKey, progress.QuestId, playerName, progress.CurrentNodeId, "quest_cancelled");
                progressList.Remove(progress);
                cancelled = true;
            }

            if (cancelled)
                SyncDynamicQuestJournal(player);

            return cancelled;
        }

        private void CancelAutoAcceptProgressForManualQuestLocked(
            string playerKey,
            string playerName,
            List<DynamicQuestProgress> progressList,
            DynamicQuestDefinition incomingQuest,
            int maxActive)
        {
            if (incomingQuest == null ||
                incomingQuest.StartMode == DynamicQuestStartMode.AutoAccept ||
                progressList == null ||
                maxActive <= 0)
                return;

            foreach (DynamicQuestProgress progress in progressList.ToList())
            {
                if (progress == null || !IsProgressCountingAgainstActiveLimit(progress))
                    continue;

                if (!TryGetQuestForProgress(progress, out DynamicQuestDefinition existingQuest) ||
                    NormalizeQuest(existingQuest).StartMode != DynamicQuestStartMode.AutoAccept)
                    continue;

                progress.Failed = true;
                progress.CancelReason = "replaced_by_manual_dynamic_quest";
                progress.UpdatedAt = DateTime.UtcNow;
                SaveProgress(playerKey, playerName, progress);
                RecordTimelineEventLocked(
                    playerKey,
                    playerName,
                    progress.QuestId,
                    "quest_cancelled",
                    nodeId: progress.CurrentNodeId,
                    detail: progress.CancelReason);
                progressList.Remove(progress);

                if (progressList.Count(IsProgressCountingAgainstActiveLimit) < maxActive)
                    return;
            }
        }

        internal void RecordProgressForTest(string playerKey, string questId, int count, bool isComplete)
        {
            lock (m_lock)
            {
                if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                {
                    progressList = new List<DynamicQuestProgress>();
                    m_playerProgress[playerKey] = progressList;
                }

                DynamicQuestProgress progress = new()
                {
                    QuestId = questId,
                    Count = count,
                    IsComplete = isComplete,
                    Completed = isComplete,
                    QuestSnapshot = TryGetQuest(questId, out DynamicQuestDefinition quest)
                        ? CloneQuestSnapshot(NormalizeQuest(quest))
                        : null,
                    UpdatedAt = DateTime.UtcNow
                };
                progressList.Add(progress);
                SaveProgress(playerKey, string.Empty, progress);
            }
        }

        internal void RecordGraphProgressForTest(
            string playerKey,
            string questId,
            string currentNodeId,
            IEnumerable<string> completedNodeIds,
            Dictionary<string, int> nodeCounters,
            string bindingKey = "",
            string worldRevision = "")
        {
            lock (m_lock)
            {
                if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                {
                    progressList = new List<DynamicQuestProgress>();
                    m_playerProgress[playerKey] = progressList;
                }

                DynamicQuestProgress progress = new()
                {
                    QuestId = questId,
                    CurrentNodeId = currentNodeId,
                    CompletedNodeIds = new HashSet<string>(completedNodeIds ?? Array.Empty<string>(), StringComparer.OrdinalIgnoreCase),
                    NodeCounters = nodeCounters ?? new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase),
                    QuestSnapshot = TryGetQuest(questId, out DynamicQuestDefinition quest)
                        ? CloneQuestSnapshot(NormalizeQuest(quest))
                        : null,
                    BindingKey = bindingKey ?? string.Empty,
                    WorldRevision = worldRevision ?? string.Empty,
                    UpdatedAt = DateTime.UtcNow
                };
                SetCurrentNodeEnteredAt(progress, DateTime.UtcNow);
                progress.Count = progress.NodeCounters.TryGetValue(currentNodeId ?? string.Empty, out int count) ? count : 0;
                progressList.Add(progress);
                SaveProgress(playerKey, string.Empty, progress);
            }
        }

        public int CancelActiveProgressForWorldRevision(string currentWorldRevision, string reason)
        {
            currentWorldRevision = (currentWorldRevision ?? string.Empty).Trim();
            reason = string.IsNullOrWhiteSpace(reason) ? "world_changed" : reason.Trim();
            int cancelled = 0;
            HashSet<string> cancelledProgressIds = new(StringComparer.OrdinalIgnoreCase);

            lock (m_lock)
            {
                foreach (KeyValuePair<string, List<DynamicQuestProgress>> pair in m_playerProgress.ToList())
                {
                    string playerKey = pair.Key;
                    foreach (DynamicQuestProgress progress in pair.Value.ToList())
                    {
                        if (progress == null || progress.Failed)
                            continue;

                        if (string.IsNullOrWhiteSpace(progress.WorldRevision) ||
                            string.Equals(progress.WorldRevision, currentWorldRevision, StringComparison.OrdinalIgnoreCase))
                            continue;

                        progress.Failed = true;
                        progress.CancelReason = reason;
                        progress.UpdatedAt = DateTime.UtcNow;
                        SaveProgress(playerKey, string.Empty, progress);
                        cancelledProgressIds.Add(BuildProgressId(playerKey, progress.QuestId));
                        RecordTimelineEventLocked(playerKey, string.Empty, progress.QuestId, "quest_cancelled", nodeId: progress.CurrentNodeId, detail: reason);
                        CleanupCinematicMarkersLocked(playerKey, progress.QuestId, string.Empty, progress.CurrentNodeId, "world_revision_cancelled");
                        cancelled++;
                    }

                    pair.Value.RemoveAll(progress => progress.Failed || progress.Completed || progress.IsComplete);
                }

                foreach (DbDynamicQuestProgress row in m_progressRepository.GetActiveForDifferentWorldRevision(currentWorldRevision))
                {
                    if (row == null || string.IsNullOrWhiteSpace(row.ProgressId) || cancelledProgressIds.Contains(row.ProgressId))
                        continue;

                    row.Failed = true;
                    row.CancelReason = reason;
                    row.IsActive = false;
                    row.UpdatedAt = DateTime.UtcNow;
                    m_progressRepository.Save(row);
                    RecordTimelineEventLocked(row.PlayerKey, row.PlayerName, row.QuestId, "quest_cancelled", nodeId: row.CurrentNodeId, detail: reason);
                    cancelled++;
                }
            }

            return cancelled;
        }

        public int CancelActiveProgressForMissingRuntimeQuests(string reason)
        {
            reason = string.IsNullOrWhiteSpace(reason) ? "runtime_offer_removed" : reason.Trim();
            int cancelled = 0;
            HashSet<string> cancelledProgressIds = new(StringComparer.OrdinalIgnoreCase);
            HashSet<string> activeQuestIds;

            lock (m_lock)
            {
                m_cancelMissingRuntimeProgressOnLoad = true;
                activeQuestIds = new HashSet<string>(m_quests.Keys, StringComparer.OrdinalIgnoreCase);

                foreach (KeyValuePair<string, List<DynamicQuestProgress>> pair in m_playerProgress.ToList())
                {
                    string playerKey = pair.Key;
                    foreach (DynamicQuestProgress progress in pair.Value.ToList())
                    {
                        if (progress == null || progress.Failed || progress.Completed || progress.IsComplete)
                            continue;

                        if (activeQuestIds.Contains(progress.QuestId))
                            continue;

                        progress.Failed = true;
                        progress.CancelReason = reason;
                        progress.UpdatedAt = DateTime.UtcNow;
                        SaveProgress(playerKey, string.Empty, progress);
                        cancelledProgressIds.Add(BuildProgressId(playerKey, progress.QuestId));
                        RecordTimelineEventLocked(playerKey, string.Empty, progress.QuestId, "quest_cancelled", nodeId: progress.CurrentNodeId, detail: reason);
                        CleanupCinematicMarkersLocked(playerKey, progress.QuestId, string.Empty, progress.CurrentNodeId, "missing_runtime_cancelled");
                        cancelled++;
                    }

                    pair.Value.RemoveAll(progress => progress.Failed || progress.Completed || progress.IsComplete);
                }

                foreach (DbDynamicQuestProgress row in m_progressRepository.GetActiveForMissingQuestIds(activeQuestIds))
                {
                    if (row == null || string.IsNullOrWhiteSpace(row.ProgressId) || cancelledProgressIds.Contains(row.ProgressId))
                        continue;

                    row.Failed = true;
                    row.CancelReason = reason;
                    row.IsActive = false;
                    row.UpdatedAt = DateTime.UtcNow;
                    m_progressRepository.Save(row);
                    RecordTimelineEventLocked(row.PlayerKey, row.PlayerName, row.QuestId, "quest_cancelled", nodeId: row.CurrentNodeId, detail: reason);
                    cancelled++;
                }
            }

            return cancelled;
        }

        public string GetTemplateIdForQuest(string questId)
        {
            questId = (questId ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(questId))
                return string.Empty;

            lock (m_lock)
            {
                if (m_quests.TryGetValue(questId, out DynamicQuestDefinition quest))
                {
                    string templateId = ExtractTemplateId(quest);
                    return string.IsNullOrWhiteSpace(templateId) ? quest.Id ?? questId : templateId;
                }
            }

            return questId;
        }

        public string GetTargetNameForQuest(string questId)
        {
            questId = (questId ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(questId))
                return string.Empty;

            lock (m_lock)
                return m_quests.TryGetValue(questId, out DynamicQuestDefinition quest)
                    ? quest?.TargetName ?? string.Empty
                    : string.Empty;
        }

        public string GetTargetNameForTemplate(string templateId)
        {
            templateId = (templateId ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(templateId))
                return string.Empty;

            lock (m_lock)
            {
                DynamicQuestDefinition quest = m_quests.Values
                    .FirstOrDefault(candidate => QuestMatchesTemplate(candidate, templateId));
                return quest?.TargetName ?? string.Empty;
            }
        }

        public DynamicQuestRuntimeRemovalResult RemoveQuestsForTemplate(string templateId, string reason = "")
        {
            templateId = (templateId ?? string.Empty).Trim();
            reason = string.IsNullOrWhiteSpace(reason) ? "dummy_evaluation_below_threshold" : reason.Trim();
            List<string> removedQuestIds = new();
            int cancelled = 0;

            if (!string.IsNullOrWhiteSpace(templateId))
            {
                lock (m_lock)
                {
                    removedQuestIds = m_quests.Values
                        .Where(quest => QuestMatchesTemplate(quest, templateId))
                        .Select(quest => quest.Id)
                        .Where(id => !string.IsNullOrWhiteSpace(id))
                        .Distinct(StringComparer.OrdinalIgnoreCase)
                        .ToList();

                    foreach (string questId in removedQuestIds)
                        m_quests.Remove(questId);

                    if (removedQuestIds.Count > 0)
                    {
                        cancelled = CancelActiveProgressForQuestIdsLocked(
                            new HashSet<string>(removedQuestIds, StringComparer.OrdinalIgnoreCase),
                            reason,
                            "dummy_evaluation_removed");
                    }
                }
            }

            return new DynamicQuestRuntimeRemovalResult
            {
                GeneratedAt = DateTime.UtcNow,
                TemplateId = templateId,
                Reason = reason,
                RemovedQuests = removedQuestIds.Count,
                CancelledProgress = cancelled,
                RemovedQuestIds = removedQuestIds
            };
        }

        public int CancelActiveProgressForPlayer(string playerKey, string playerName = "", string reason = "")
        {
            playerKey = (playerKey ?? string.Empty).Trim();
            playerName = (playerName ?? string.Empty).Trim();
            reason = string.IsNullOrWhiteSpace(reason) ? "player_progress_cancelled" : reason.Trim();
            if (string.IsNullOrWhiteSpace(playerKey))
                return 0;

            EnsurePlayerProgressLoaded(playerKey, playerName);
            int cancelled = 0;

            lock (m_lock)
            {
                if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                    return 0;

                foreach (DynamicQuestProgress progress in progressList.ToList())
                {
                    if (progress == null || progress.Failed || progress.Completed || progress.IsComplete)
                        continue;

                    progress.Failed = true;
                    progress.CancelReason = reason;
                    progress.UpdatedAt = DateTime.UtcNow;
                    SaveProgress(playerKey, playerName, progress);
                    RecordTimelineEventLocked(playerKey, playerName, progress.QuestId, "quest_cancelled", nodeId: progress.CurrentNodeId, detail: reason);
                    CleanupCinematicMarkersLocked(playerKey, progress.QuestId, playerName, progress.CurrentNodeId, "quest_cancelled");
                    cancelled++;
                }

                progressList.RemoveAll(progress => progress.Failed || progress.Completed || progress.IsComplete);
            }

            return cancelled;
        }

        private int CancelActiveProgressForQuestIdsLocked(ISet<string> questIds, string reason, string cleanupReason)
        {
            if (questIds == null || questIds.Count == 0)
                return 0;

            reason = string.IsNullOrWhiteSpace(reason) ? "runtime_offer_removed" : reason.Trim();
            cleanupReason = string.IsNullOrWhiteSpace(cleanupReason) ? "runtime_offer_removed" : cleanupReason.Trim();
            int cancelled = 0;
            HashSet<string> cancelledProgressIds = new(StringComparer.OrdinalIgnoreCase);

            foreach (KeyValuePair<string, List<DynamicQuestProgress>> pair in m_playerProgress.ToList())
            {
                string playerKey = pair.Key;
                foreach (DynamicQuestProgress progress in pair.Value.ToList())
                {
                    if (progress == null || progress.Failed || progress.Completed || progress.IsComplete)
                        continue;

                    if (!questIds.Contains(progress.QuestId))
                        continue;

                    progress.Failed = true;
                    progress.CancelReason = reason;
                    progress.UpdatedAt = DateTime.UtcNow;
                    SaveProgress(playerKey, string.Empty, progress);
                    cancelledProgressIds.Add(BuildProgressId(playerKey, progress.QuestId));
                    RecordTimelineEventLocked(playerKey, string.Empty, progress.QuestId, "quest_cancelled", nodeId: progress.CurrentNodeId, detail: reason);
                    CleanupCinematicMarkersLocked(playerKey, progress.QuestId, string.Empty, progress.CurrentNodeId, cleanupReason);
                    cancelled++;
                }

                pair.Value.RemoveAll(progress => progress.Failed || progress.Completed || progress.IsComplete);
            }

            foreach (DbDynamicQuestProgress row in m_progressRepository.GetActive(10000))
            {
                if (row == null ||
                    string.IsNullOrWhiteSpace(row.ProgressId) ||
                    cancelledProgressIds.Contains(row.ProgressId) ||
                    !questIds.Contains(row.QuestId))
                    continue;

                row.Failed = true;
                row.CancelReason = reason;
                row.IsActive = false;
                row.UpdatedAt = DateTime.UtcNow;
                m_progressRepository.Save(row);
                RecordTimelineEventLocked(row.PlayerKey, row.PlayerName, row.QuestId, "quest_cancelled", nodeId: row.CurrentNodeId, detail: reason);
                cancelled++;
            }

            return cancelled;
        }

        public int RemoveQuestsForDifferentWorldRevision(string currentWorldRevision)
        {
            currentWorldRevision = (currentWorldRevision ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(currentWorldRevision))
                return 0;

            lock (m_lock)
            {
                List<string> staleQuestIds = m_quests.Values
                    .Where(quest => !string.IsNullOrWhiteSpace(quest.WorldRevision) &&
                                    !string.Equals(quest.WorldRevision, currentWorldRevision, StringComparison.OrdinalIgnoreCase))
                    .Select(quest => quest.Id)
                    .ToList();

                foreach (string questId in staleQuestIds)
                    m_quests.Remove(questId);

                return staleQuestIds.Count;
            }
        }

        internal bool RecordKillProgressForTest(string playerKey, string enemyName, int enemyLevel, ushort regionId, bool groupCredit = false)
        {
            lock (m_lock)
            {
                bool advanced = RecordKillProgressLocked(playerKey, string.Empty, enemyName, enemyLevel, regionId, groupCredit, null, null, out DynamicQuestDefinition quest);
                TryMarkCompletedNpcLessQuestRewardedLocked(playerKey, string.Empty, quest);
                return advanced;
            }
        }

        internal int RecordKillProgressForPlayersForTest(IEnumerable<string> playerKeys, string killerPlayerKey, string enemyName, int enemyLevel, ushort regionId)
        {
            int advanced = 0;
            HashSet<string> seenPlayerKeys = new(StringComparer.OrdinalIgnoreCase);
            killerPlayerKey = (killerPlayerKey ?? string.Empty).Trim();

            lock (m_lock)
            {
                foreach (string playerKey in playerKeys ?? Array.Empty<string>())
                {
                    string normalizedPlayerKey = (playerKey ?? string.Empty).Trim();
                    if (string.IsNullOrWhiteSpace(normalizedPlayerKey) || !seenPlayerKeys.Add(normalizedPlayerKey))
                        continue;

                    bool groupCredit = !string.Equals(normalizedPlayerKey, killerPlayerKey, StringComparison.OrdinalIgnoreCase);
                    if (RecordKillProgressLocked(normalizedPlayerKey, string.Empty, enemyName, enemyLevel, regionId, groupCredit, null, null, out _))
                        advanced++;
                }
            }

            return advanced;
        }

        internal bool RecordExploreProgressForTest(string playerKey, ushort regionId, int x, int y)
        {
            lock (m_lock)
            {
                bool advanced = RecordExploreProgressLocked(playerKey, string.Empty, regionId, x, y, null, out DynamicQuestDefinition quest);
                TryMarkCompletedNpcLessQuestRewardedLocked(playerKey, string.Empty, quest);
                return advanced;
            }
        }

        internal bool RecordNpcInteractionForTest(string playerKey, string npcInternalId, ushort regionId)
        {
            lock (m_lock)
                return RecordNpcInteractionLocked(playerKey, npcInternalId, regionId, out _);
        }

        internal bool SelectChoiceForTest(string playerKey, string questId, string choiceId)
        {
            lock (m_lock)
            {
                bool advanced = SelectChoiceLocked(playerKey, questId, choiceId, out DynamicQuestDefinition quest);
                TryMarkCompletedNpcLessQuestRewardedLocked(playerKey, string.Empty, quest);
                return advanced;
            }
        }

        internal bool RecordWorldSignalForTest(string playerKey, string signal)
        {
            return RecordWorldSignalForTest(playerKey, string.Empty, signal);
        }

        internal bool RecordWorldSignalForTest(string playerKey, string playerName, string signal)
        {
            lock (m_lock)
            {
                WorldSignalRecordResult result = RecordWorldSignalLocked(playerKey, playerName, signal, null, out DynamicQuestDefinition quest);
                TryMarkCompletedNpcLessQuestRewardedLocked(playerKey, playerName, quest);
                return result != WorldSignalRecordResult.Ignored;
            }
        }

        internal bool MarkCompletedQuestRewardedForTest(string playerKey, string playerName, string questId)
        {
            lock (m_lock)
            {
                playerKey = (playerKey ?? string.Empty).Trim();
                questId = (questId ?? string.Empty).Trim();
                if (string.IsNullOrWhiteSpace(playerKey) || string.IsNullOrWhiteSpace(questId))
                    return false;

                DynamicQuestProgress progress = FindCompletedProgressLocked(playerKey, questId);
                if (progress == null || !TryGetQuestForProgress(progress, out DynamicQuestDefinition quest))
                    return false;

                MarkCompletedQuestRewardedLocked(playerKey, playerName ?? string.Empty, NormalizeQuest(quest), progress);
                return true;
            }
        }

        internal bool RecordPlayerDiedForTest(string playerKey, string playerName = "")
        {
            lock (m_lock)
            {
                bool advanced = RecordPlayerDiedLocked(playerKey, playerName, out DynamicQuestDefinition quest);
                TryMarkCompletedNpcLessQuestRewardedLocked(playerKey, playerName, quest);
                return advanced;
            }
        }

        internal bool RecordPartySizeChangedForTest(string playerKey, int partySize, string playerName = "")
        {
            lock (m_lock)
            {
                bool advanced = RecordPartySizeChangedLocked(playerKey, playerName, partySize, out DynamicQuestDefinition quest);
                TryMarkCompletedNpcLessQuestRewardedLocked(playerKey, playerName, quest);
                return advanced;
            }
        }

        internal bool RecordTimeoutTickForTest(string playerKey, DateTime nowUtc, string playerName = "")
        {
            lock (m_lock)
            {
                bool advanced = RecordTimedOutLocked(playerKey, playerName, nowUtc, out DynamicQuestDefinition quest);
                TryMarkCompletedNpcLessQuestRewardedLocked(playerKey, playerName, quest);
                return advanced;
            }
        }

        public bool HandlePlayerDied(GamePlayer player, GameObject killer = null)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED || player == null)
                return false;

            string playerKey = GetPlayerKey(player);
            string playerName = player.Name ?? string.Empty;
            EnsurePlayerProgressLoaded(playerKey, playerName);

            DynamicQuestDefinition quest;
            bool advanced;
            lock (m_lock)
                advanced = RecordPlayerDiedLocked(playerKey, playerName, out quest);

            if (!advanced || quest == null)
                return false;

            DynamicQuestProgressItem item = GetProgressSnapshot(player).Active
                .FirstOrDefault(active => string.Equals(active.QuestId, quest.Id, StringComparison.OrdinalIgnoreCase));
            string text = item == null ? quest.ProgressText : DescribeCurrentObjective(item);
            player.Out.SendMessage($"{quest.Title}: {text}", eChatType.CT_System, eChatLoc.CL_SystemWindow);
            return true;
        }

        public bool HandlePartySizeChanged(GamePlayer player)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED || player == null)
                return false;

            string playerKey = GetPlayerKey(player);
            string playerName = player.Name ?? string.Empty;
            EnsurePlayerProgressLoaded(playerKey, playerName);

            DynamicQuestDefinition quest;
            bool advanced;
            lock (m_lock)
                advanced = RecordPartySizeChangedLocked(playerKey, playerName, GetPlayerPartySize(player), out quest);

            if (!advanced || quest == null)
                return false;

            DynamicQuestProgressItem item = GetProgressSnapshot(player).Active
                .FirstOrDefault(active => string.Equals(active.QuestId, quest.Id, StringComparison.OrdinalIgnoreCase));
            string text = item == null ? quest.ProgressText : DescribeCurrentObjective(item);
            player.Out.SendMessage($"{quest.Title}: {text}", eChatType.CT_System, eChatLoc.CL_SystemWindow);
            return true;
        }

        public int TickTimeouts(DateTime nowUtc)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED)
                return 0;

            int advanced = 0;
            lock (m_lock)
            {
                foreach (string playerKey in m_playerProgress.Keys.ToList())
                {
                    if (RecordTimedOutLocked(playerKey, string.Empty, nowUtc, out _))
                        advanced++;
                }
            }

            return advanced;
        }

        private bool TryFinishCompletedNpcLessQuest(GamePlayer player, string playerKey, string playerName, DynamicQuestDefinition quest)
        {
            if (player == null || quest == null)
                return false;

            DynamicQuestDefinition normalizedQuest = NormalizeQuest(quest);
            if (RequiresStartNpc(normalizedQuest))
                return false;

            DynamicQuestProgress progress;
            DynamicQuestProgress choiceProgress;
            DynamicQuestNode choiceNode = null;
            lock (m_lock)
            {
                TryAdvanceDefaultNpcLessChoiceLocked(playerKey, playerName, normalizedQuest);
                progress = FindCompletedProgressLocked(playerKey, normalizedQuest.Id);
                choiceProgress = progress == null
                    ? FindActiveChoiceProgressLocked(playerKey, normalizedQuest, out choiceNode)
                    : null;
            }

            if (progress == null)
            {
                if (choiceProgress != null && choiceNode != null)
                {
                    ShowChoiceDialog(player, null, normalizedQuest, choiceProgress, choiceNode);
                    return true;
                }

                return false;
            }

            FinishQuest(player, null, normalizedQuest, progress);
            return true;
        }

        private bool TryMarkCompletedNpcLessQuestRewardedLocked(string playerKey, string playerName, DynamicQuestDefinition quest)
        {
            if (quest == null)
                return false;

            DynamicQuestDefinition normalizedQuest = NormalizeQuest(quest);
            if (RequiresStartNpc(normalizedQuest))
                return false;

            TryAdvanceDefaultNpcLessChoiceLocked(playerKey, playerName, normalizedQuest);

            DynamicQuestProgress progress = FindCompletedProgressLocked(playerKey, normalizedQuest.Id);
            if (progress == null)
                return false;

            MarkCompletedQuestRewardedLocked(playerKey, playerName, normalizedQuest, progress);
            return true;
        }

        private bool TryAdvanceDefaultNpcLessChoiceLocked(string playerKey, string playerName, DynamicQuestDefinition quest)
        {
            if (quest == null || RequiresStartNpc(quest))
                return false;

            playerKey = (playerKey ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(playerKey) || !m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                return false;

            foreach (DynamicQuestProgress progress in progressList)
            {
                if (progress == null || progress.Completed || progress.Failed || !string.Equals(progress.QuestId, quest.Id, StringComparison.OrdinalIgnoreCase))
                    continue;

                DynamicQuestNode node = GetCurrentNode(quest, progress);
                if (node?.Type != DynamicQuestNodeType.Choice)
                    continue;
                if (RequiresExplicitNpcLessChoice(node))
                    continue;

                DynamicQuestChoice choice = (node.Objective?.Choices ?? Array.Empty<DynamicQuestChoice>())
                    .FirstOrDefault(item => string.Equals(item.Id, "safe", StringComparison.OrdinalIgnoreCase)) ??
                    (node.Objective?.Choices ?? Array.Empty<DynamicQuestChoice>()).FirstOrDefault();
                if (choice == null || string.IsNullOrWhiteSpace(choice.Id))
                    continue;

                progress.ChoiceHistory[node.Id] = choice.Id;
            RecordTimelineEventLocked(playerKey, playerName, quest.Id, "choice_selected", nodeId: node.Id, choiceId: choice.Id);
            RecordChoiceConsequenceLocked(playerKey, playerName, quest.Id, node.Id, choice);
            RecordChoiceOutcomeSetPieceLocked(playerKey, playerName, quest, node, choice, null, null);

            string fromNodeId = node.Id;
            AdvanceFromNode(progress, quest, node, DynamicQuestEdgeCondition.ChoiceSelected, choice.Id);
                RecordNodeTransitionLocked(playerKey, playerName, quest.Id, progress, fromNodeId, "npc_less_default_choice");
                TryConsumePendingWorldSignalsLocked(playerKey, playerName, quest, progress);
                SaveProgress(playerKey, playerName, progress);
                return true;
            }

            return false;
        }

        private DynamicQuestProgress FindActiveChoiceProgressLocked(string playerKey, DynamicQuestDefinition quest, out DynamicQuestNode choiceNode)
        {
            choiceNode = null;
            playerKey = (playerKey ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(playerKey) || quest == null || !m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                return null;

            foreach (DynamicQuestProgress progress in progressList)
            {
                if (progress == null || progress.Completed || progress.Failed || !string.Equals(progress.QuestId, quest.Id, StringComparison.OrdinalIgnoreCase))
                    continue;

                DynamicQuestNode node = GetCurrentNode(quest, progress);
                if (node?.Type != DynamicQuestNodeType.Choice)
                    continue;

                choiceNode = node;
                return progress;
            }

            return null;
        }

        private static bool RequiresExplicitNpcLessChoice(DynamicQuestNode node)
        {
            int choiceCount = node?.Objective?.Choices?.Count ?? 0;
            return choiceCount > 1;
        }

        private DynamicQuestProgress FindCompletedProgressLocked(string playerKey, string questId)
        {
            playerKey = (playerKey ?? string.Empty).Trim();
            questId = (questId ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(playerKey) || string.IsNullOrWhiteSpace(questId))
                return null;

            if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                return null;

            return progressList.FirstOrDefault(progress =>
                progress != null &&
                string.Equals(progress.QuestId, questId, StringComparison.OrdinalIgnoreCase) &&
                (progress.Completed || progress.IsComplete));
        }

        private void MarkCompletedQuestRewarded(string playerKey, string playerName, DynamicQuestDefinition quest, DynamicQuestProgress progress)
        {
            lock (m_lock)
                MarkCompletedQuestRewardedLocked(playerKey, playerName, quest, progress);
        }

        private void MarkCompletedQuestRewardedLocked(string playerKey, string playerName, DynamicQuestDefinition quest, DynamicQuestProgress progress)
        {
            playerKey = (playerKey ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(playerKey) || quest == null || progress == null)
                return;

            progress.Completed = true;
            progress.IsComplete = true;
            progress.UpdatedAt = DateTime.UtcNow;

            MarkQuestCompletedLocked(playerKey, quest.Id);
            MarkStoryFamilyCompletedLocked(playerKey, quest);
            MarkWorldMemoryLocked(playerKey, quest, progress);
            RecordPresentationBeatsLocked(
                playerKey,
                playerName,
                quest,
                progress.CurrentNodeId ?? string.Empty,
                null,
                null,
                "OnComplete");

            if (!HasQuestRewardedTimelineEventLocked(playerKey, quest.Id))
            {
                RecordQuestWorldImpactLocked(playerKey, playerName, quest, progress);

                if (HasSelectedRewardChoice(quest, progress))
                {
                    RecordTimelineEventLocked(
                        playerKey,
                        playerName,
                        quest.Id,
                        "choice_reward_bonus",
                        nodeId: progress.CurrentNodeId ?? string.Empty,
                        detail: quest.Reward?.ChoiceBonusKey ?? string.Empty);
                }

                RecordTimelineEventLocked(
                    playerKey,
                    playerName,
                    quest.Id,
                    "quest_rewarded",
                    nodeId: progress.CurrentNodeId ?? string.Empty);
            }

            if (m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                progressList.Remove(progress);

            CleanupCinematicMarkersLocked(playerKey, quest.Id, playerName, progress.CurrentNodeId, "quest_rewarded");
            SaveProgress(playerKey, playerName, progress);
        }

        private bool IsQuestRewarded(string playerKey, string questId)
        {
            lock (m_lock)
                return HasQuestRewardedTimelineEventLocked(playerKey, questId);
        }

        private void RecordQuestRewardAmount(
            string playerKey,
            string playerName,
            string questId,
            string nodeId,
            long xp,
            long money)
        {
            lock (m_lock)
            {
                RecordTimelineEventLocked(
                    playerKey,
                    playerName,
                    questId,
                    "quest_reward_amount",
                    nodeId: nodeId,
                    detail: $"xp={Math.Max(0, xp)};money_copper={Math.Max(0, money)}");
            }
        }

        private void FinishQuest(GamePlayer player, GameNPC npc, DynamicQuestDefinition quest, DynamicQuestProgress progress)
        {
            if (player == null || quest == null || progress == null)
                return;

            RecordStoryNodeEnteredLocked(
                GetPlayerKey(player),
                player.Name ?? string.Empty,
                quest,
                progress,
                player,
                npc,
                "OnComplete");

            long xp = CalculateRewardXp(player, quest, progress);
            long money = CalculateRewardMoney(player, quest, progress);

            string playerKey = GetPlayerKey(player);
            bool rewardedNow = !IsQuestRewarded(playerKey, quest.Id);
            if (rewardedNow)
            {
                if (xp > 0)
                    player.ForceGainExperience(xp);

                if (money > 0)
                    player.AddMoney(money, "동적 퀘스트 보상으로 {0}을 받았습니다.");
            }

            string playerName = player.Name ?? string.Empty;
            MarkCompletedQuestRewarded(playerKey, playerName, quest, progress);
            if (rewardedNow)
            {
                RecordQuestRewardAmount(
                    playerKey,
                    playerName,
                    quest.Id,
                    progress.CurrentNodeId ?? string.Empty,
                    xp,
                    money);
            }
            SyncDynamicQuestJournal(player);

            if (npc != null)
            {
                npc.SayTo(player, quest.FinishText);
                player.Out.SendNPCsQuestEffect(npc, GetQuestIndicator(npc, player));
            }
            else
            {
                player.Out.SendMessage($"{quest.Title}: {quest.FinishText}", eChatType.CT_Important, eChatLoc.CL_SystemWindow);
            }
        }

        private void ShowChoiceDialog(GamePlayer player, GameNPC npc, DynamicQuestDefinition quest, DynamicQuestProgress progress, DynamicQuestNode node)
        {
            IList<DynamicQuestChoice> choices = node.Objective?.Choices ?? Array.Empty<DynamicQuestChoice>();
            DynamicQuestChoice acceptChoice = choices.FirstOrDefault() ?? new DynamicQuestChoice { Id = "default", Label = "계속한다" };
            DynamicQuestChoice declineChoice = choices.Skip(1).FirstOrDefault() ?? acceptChoice;
            RecordPresentationBeatsLocked(
                GetPlayerKey(player),
                player?.Name ?? string.Empty,
                quest,
                node?.Id,
                player,
                npc,
                "OnChoiceShown");

            player.Out.SendCustomDialog($"{node.Text}\n\n수락: {acceptChoice.Label}\n거절: {declineChoice.Label}", (dialogPlayer, response) =>
            {
                string selected = response == 0x01 ? acceptChoice.Id : declineChoice.Id;
                bool advanced;
                lock (m_lock)
                    advanced = SelectChoiceLocked(GetPlayerKey(dialogPlayer), quest.Id, selected, out _, dialogPlayer, npc);

                if (!advanced)
                {
                    if (npc != null)
                        npc.SayTo(dialogPlayer, node.Text);
                    else
                        dialogPlayer.Out.SendMessage(node.Text, eChatType.CT_System, eChatLoc.CL_SystemWindow);
                    return;
                }

                DynamicQuestNode currentNode = GetCurrentNode(quest, progress);
                if (progress.Completed || progress.IsComplete || currentNode?.Type == DynamicQuestNodeType.Complete)
                    FinishQuest(dialogPlayer, npc, quest, progress);
                else
                {
                    string message = currentNode?.Text ?? quest.ProgressText;
                    if (npc != null)
                        npc.SayTo(dialogPlayer, message);
                    else
                        dialogPlayer.Out.SendMessage($"{quest.Title}: {message}", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                }
            });
        }

        private void RecordChoiceConsequenceLocked(string playerKey, string playerName, string questId, string nodeId, DynamicQuestChoice choice)
        {
            string consequence = BuildChoiceConsequence(choice);
            if (string.IsNullOrWhiteSpace(consequence))
                return;

            RecordTimelineEventLocked(
                playerKey,
                playerName,
                questId,
                "choice_consequence",
                nodeId: nodeId,
                detail: consequence,
                choiceId: choice?.Id ?? string.Empty);
        }

        private void RecordChoiceOutcomeSetPieceLocked(
            string playerKey,
            string playerName,
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            DynamicQuestChoice choice,
            GamePlayer player,
            GameNPC npc)
        {
            if (quest == null || node == null || choice == null)
                return;

            IList<DynamicQuestCinematicAction> actions = BuildChoiceOutcomeSetPieceActions(quest, node, choice);
            if (actions.Count == 0)
                return;

            foreach (DynamicQuestCinematicAction action in actions)
            {
                if (action == null || string.IsNullOrWhiteSpace(action.Detail))
                    continue;

                PlayCinematicActionLocked(playerKey, quest.Id, player, npc, action);
                if (!HasTimelineEventLocked(playerKey, quest.Id, "cinematic_action", node.Id, action.Detail))
                {
                    RecordTimelineEventLocked(
                        playerKey,
                        playerName,
                        quest.Id,
                        "cinematic_action",
                        nodeId: node.Id,
                        detail: action.Detail,
                        choiceId: choice.Id);
                }

                RecordSceneBeatOutcomeLocked(playerKey, playerName, quest, node, action);
            }

            string outcome = ResolveChoiceOutcomeStyle(choice);
            string tactic = ResolveChoiceOutcomeTactic(choice, outcome);
            string detail =
                $"choice_outcome_scene:choice:{SafeSceneBeatToken(choice.Id)}" +
                $":outcome:{SafeSceneBeatToken(outcome)}" +
                $":tactic:{SafeSceneBeatToken(tactic)}";
            if (!HasTimelineEventLocked(playerKey, quest.Id, "choice_outcome_scene", node.Id, detail))
            {
                RecordTimelineEventLocked(
                    playerKey,
                    playerName,
                    quest.Id,
                    "choice_outcome_scene",
                    nodeId: node.Id,
                    detail: detail,
                    choiceId: choice.Id);
            }

            string consequence = BuildChoiceConsequence(choice);
            if (!string.IsNullOrWhiteSpace(consequence) &&
                !HasTimelineEventLocked(playerKey, quest.Id, "choice_consequence", node.Id, consequence))
            {
                RecordTimelineEventLocked(
                    playerKey,
                    playerName,
                    quest.Id,
                    "choice_consequence",
                    nodeId: node.Id,
                    detail: consequence,
                    choiceId: choice.Id);
            }
        }

        private static void PresentChoiceConsequence(GamePlayer player, DynamicQuestNode node, DynamicQuestChoice choice)
        {
            string consequence = BuildChoiceConsequence(choice);
            if (player == null || string.IsNullOrWhiteSpace(consequence))
                return;

            string title = string.IsNullOrWhiteSpace(node?.Title) ? "선택의 결과" : node.Title.Trim();
            player.Out.SendMessage($"{title}: {consequence}", eChatType.CT_System, eChatLoc.CL_SystemWindow);
        }

        private static string BuildChoiceConsequence(DynamicQuestChoice choice)
        {
            string consequence = !string.IsNullOrWhiteSpace(choice?.Consequence)
                ? choice.Consequence
                : choice?.Text;
            return TrimNarrativeText(consequence, 300);
        }

        private static string TrimNarrativeText(string value, int maxLength)
        {
            value = (value ?? string.Empty).Trim();
            if (maxLength <= 0 || value.Length <= maxLength)
                return value;

            return value.Substring(0, maxLength).Trim();
        }

        internal static double CalculateRewardScaleForTest(DynamicQuestDefinition quest, DynamicQuestProgress progress, RewardScaleKind kind)
        {
            return CalculateRewardScale(quest, progress, kind);
        }

        private static long CalculateRewardXp(GamePlayer player, DynamicQuestDefinition quest, DynamicQuestProgress progress)
        {
            int level = Math.Max(1, (int)player.Level);
            double baseXp = level * level * 12.0 * Math.Max(1, quest.TargetCount);
            return (long)Math.Max(0, baseXp * Properties.KDAOC_DYNAMIC_QUEST_REWARD_XP_MULTIPLIER * CalculateRewardScale(quest, progress, RewardScaleKind.Xp));
        }

        private static long CalculateRewardMoney(GamePlayer player, DynamicQuestDefinition quest, DynamicQuestProgress progress)
        {
            int level = Math.Max(1, (int)player.Level);
            double baseCopper = level * 20.0 * Math.Max(1, quest.TargetCount);
            return (long)Math.Max(0, baseCopper * Properties.KDAOC_DYNAMIC_QUEST_REWARD_MONEY_MULTIPLIER * CalculateRewardScale(quest, progress, RewardScaleKind.Money));
        }

        private static double CalculateRewardScale(DynamicQuestDefinition quest, DynamicQuestProgress progress, RewardScaleKind kind)
        {
            DynamicQuestRewardDefinition reward = quest?.Reward ?? new DynamicQuestRewardDefinition();
            double rewardMultiplier = kind == RewardScaleKind.Money ? reward.MoneyMultiplier : reward.XpMultiplier;
            double partyMultiplier = reward.PartyBonusMultiplier <= 0 ? 1.0 : reward.PartyBonusMultiplier;
            int completedPlayableSteps = CountCompletedPlayableSteps(quest, progress);
            double stepScale = 1.0 + Math.Max(0, completedPlayableSteps - 1) * Math.Max(0.0, reward.StepBonusMultiplier);
            double choiceScale = HasSelectedRewardChoice(quest, progress) ? ChoiceRewardBonusMultiplier : 1.0;
            return Math.Max(0.0, rewardMultiplier) * partyMultiplier * Math.Max(1.0, stepScale) * choiceScale;
        }

        private static bool HasSelectedRewardChoice(DynamicQuestDefinition quest, DynamicQuestProgress progress)
        {
            string choiceBonusKey = (quest?.Reward?.ChoiceBonusKey ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(choiceBonusKey) || progress?.ChoiceHistory == null)
                return false;

            return progress.ChoiceHistory.Values.Any(choiceId =>
                string.Equals(choiceId, choiceBonusKey, StringComparison.OrdinalIgnoreCase));
        }

        private static int CountCompletedPlayableSteps(DynamicQuestDefinition quest, DynamicQuestProgress progress)
        {
            if (quest == null || progress?.CompletedNodeIds == null || progress.CompletedNodeIds.Count == 0)
                return 1;

            DynamicQuestDefinition normalized = NormalizeQuest(quest);
            HashSet<string> completedNodeIds = progress.CompletedNodeIds;
            int count = (normalized.Nodes ?? Array.Empty<DynamicQuestNode>())
                .Count(node =>
                    node != null &&
                    node.Type is not DynamicQuestNodeType.Complete and not DynamicQuestNodeType.Fail &&
                    completedNodeIds.Contains(node.Id));

            return Math.Max(1, count);
        }

        private DynamicQuestProgress GetProgressForStartNpc(GamePlayer player, GameNPC npc)
        {
            string playerKey = GetPlayerKey(player);
            lock (m_lock)
            {
                if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                    return null;

                return progressList.FirstOrDefault(progress =>
                    progress != null &&
                    !progress.Failed &&
                    TryGetQuestForProgress(progress, out DynamicQuestDefinition quest) &&
                    IsStartNpc(quest, npc));
            }
        }

        private DynamicQuestProgress GetProgressForKill(GamePlayer player, string enemyName, out DynamicQuestDefinition matchingQuest)
        {
            matchingQuest = null;
            string playerKey = GetPlayerKey(player);
            lock (m_lock)
            {
                if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                    return null;

                foreach (DynamicQuestProgress progress in progressList)
                {
                    if (progress.IsComplete || !TryGetQuestForProgress(progress, out DynamicQuestDefinition quest))
                        continue;

                    if (quest.StepType != DynamicQuestStepType.Kill || !NameMatches(enemyName, quest.TargetName))
                        continue;

                    matchingQuest = quest;
                    return progress;
                }

                return null;
            }
        }

        private bool RecordKillProgressLocked(
            string playerKey,
            string playerName,
            string enemyName,
            int enemyLevel,
            ushort regionId,
            bool groupCredit,
            GamePlayer player,
            GameNPC npc,
            out DynamicQuestDefinition matchingQuest)
        {
            matchingQuest = null;
            if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                return false;

            foreach (DynamicQuestProgress progress in progressList)
            {
                if (progress.Completed || progress.Failed || !TryGetQuestForProgress(progress, out DynamicQuestDefinition quest))
                    continue;

                DynamicQuestDefinition normalized = NormalizeQuest(quest);
                DynamicQuestNode node = GetCurrentNode(normalized, progress);
                if (node?.Type != DynamicQuestNodeType.Kill)
                    continue;

                DynamicQuestObjective objective = node.Objective ?? new DynamicQuestObjective();
                if (groupCredit && !objective.AllowGroupCredit)
                    continue;
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
                RecordTimelineEventLocked(
                    playerKey,
                    playerName,
                    normalized.Id,
                    "kill_progress",
                    nodeId: node.Id,
                    detail: enemyName,
                    count: count);
                RecordPresentationBeatsLocked(playerKey, playerName, normalized, node.Id, player, npc, "OnKill");

                if (count >= objective.TargetCount)
                {
                    string fromNodeId = node.Id;
                    AdvanceFromNode(progress, normalized, node, DynamicQuestEdgeCondition.ObjectiveComplete, string.Empty);
                    RecordNodeTransitionLocked(playerKey, playerName, normalized.Id, progress, fromNodeId, "kill_progress");
                    RecordStoryNodeEnteredLocked(playerKey, playerName, normalized, progress, player, npc);
                    TryConsumePendingWorldSignalsLocked(playerKey, playerName, normalized, progress, player, npc);
                    TryAutoAdvanceFromCurrentNodeLocked(playerKey, playerName, normalized, progress, "kill_progress", player: player, npc: npc);
                }

                SaveProgress(playerKey, playerName, progress);
                matchingQuest = normalized;
                return true;
            }

            return false;
        }

        private bool RecordExploreProgressLocked(string playerKey, string playerName, ushort regionId, int x, int y, GamePlayer player, out DynamicQuestDefinition matchingQuest)
        {
            matchingQuest = null;
            if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList) || progressList.Count == 0)
                return false;

            foreach (DynamicQuestProgress progress in progressList)
            {
                if (progress.Completed || progress.Failed || !TryGetQuestForProgress(progress, out DynamicQuestDefinition quest))
                    continue;

                DynamicQuestDefinition normalized = NormalizeQuest(quest);
                DynamicQuestNode node = GetCurrentNode(normalized, progress);
                if (node?.Type != DynamicQuestNodeType.Explore)
                    continue;
                if (!HasObjectiveCompleteEdge(node))
                    continue;

                DynamicQuestObjective objective = node.Objective ?? new DynamicQuestObjective();
                if (objective.RegionId != regionId)
                    continue;
                if (!IsInsideExploreObjective(objective, x, y))
                    continue;

                RecordTimelineEventLocked(
                    playerKey,
                    playerName,
                    normalized.Id,
                    "explore_complete",
                    nodeId: node.Id,
                    detail: objective.LocationName);
                RecordPresentationBeatsLocked(playerKey, playerName, normalized, node.Id, player, null, "OnExplore");
                string fromNodeId = node.Id;
                AdvanceFromNode(progress, normalized, node, DynamicQuestEdgeCondition.ObjectiveComplete, string.Empty);
                RecordNodeTransitionLocked(playerKey, playerName, normalized.Id, progress, fromNodeId, "explore_complete");
                RecordStoryNodeEnteredLocked(playerKey, playerName, normalized, progress, player, null);
                TryConsumePendingWorldSignalsLocked(playerKey, playerName, normalized, progress, player);
                TryAutoAdvanceFromCurrentNodeLocked(playerKey, playerName, normalized, progress, "explore_complete", player: player);
                SaveProgress(playerKey, playerName, progress);
                matchingQuest = normalized;
                return true;
            }

            return false;
        }

        private bool RecordNpcInteractionLocked(string playerKey, string npcInternalId, ushort regionId, out DynamicQuestDefinition matchingQuest)
        {
            matchingQuest = null;
            if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                return false;

            foreach (DynamicQuestProgress progress in progressList)
            {
                if (progress.Completed || progress.Failed || !TryGetQuestForProgress(progress, out DynamicQuestDefinition quest))
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

                RecordTimelineEventLocked(
                    playerKey,
                    string.Empty,
                    normalized.Id,
                    "npc_interaction",
                    nodeId: node.Id,
                    detail: npcInternalId);
                string fromNodeId = node.Id;
                AdvanceFromNode(progress, normalized, node, DynamicQuestEdgeCondition.ObjectiveComplete, string.Empty);
                RecordNodeTransitionLocked(playerKey, string.Empty, normalized.Id, progress, fromNodeId, "npc_interaction");
                RecordStoryNodeEnteredLocked(playerKey, string.Empty, normalized, progress, null, null);
                TryConsumePendingWorldSignalsLocked(playerKey, string.Empty, normalized, progress);
                TryAutoAdvanceFromCurrentNodeLocked(playerKey, string.Empty, normalized, progress, "npc_interaction");
                SaveProgress(playerKey, string.Empty, progress);
                matchingQuest = normalized;
                return true;
            }

            return false;
        }

        private bool SelectChoiceLocked(string playerKey, string questId, string choiceId, out DynamicQuestDefinition matchingQuest, GamePlayer player = null, GameNPC npc = null)
        {
            matchingQuest = null;
            if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                return false;

            DynamicQuestProgress progress = progressList.FirstOrDefault(item => string.Equals(item.QuestId, questId, StringComparison.OrdinalIgnoreCase));
            if (progress == null || progress.Failed || !TryGetQuestForProgress(progress, out DynamicQuestDefinition quest))
                return false;

            DynamicQuestDefinition normalized = NormalizeQuest(quest);
            DynamicQuestNode node = GetCurrentNode(normalized, progress);
            if (node?.Type != DynamicQuestNodeType.Choice)
                return false;

            DynamicQuestChoice selectedChoice = (node.Objective?.Choices ?? Array.Empty<DynamicQuestChoice>())
                .FirstOrDefault(choice => string.Equals(choice.Id, choiceId, StringComparison.OrdinalIgnoreCase));
            if (selectedChoice == null)
                return false;

            string playerName = player?.Name ?? string.Empty;
            progress.ChoiceHistory[node.Id] = choiceId;
            RecordTimelineEventLocked(
                playerKey,
                playerName,
                normalized.Id,
                "choice_selected",
                nodeId: node.Id,
                choiceId: choiceId);
            RecordChoiceConsequenceLocked(playerKey, playerName, normalized.Id, node.Id, selectedChoice);
            PresentChoiceConsequence(player, node, selectedChoice);
            RecordPresentationBeatsLocked(playerKey, playerName, normalized, node.Id, player, npc, "OnChoiceSelected");
            RecordChoiceOutcomeSetPieceLocked(playerKey, playerName, normalized, node, selectedChoice, player, npc);
            string fromNodeId = node.Id;
            AdvanceFromNode(progress, normalized, node, DynamicQuestEdgeCondition.ChoiceSelected, choiceId);
            RecordNodeTransitionLocked(playerKey, playerName, normalized.Id, progress, fromNodeId, "choice_selected");
            RecordStoryNodeEnteredLocked(playerKey, playerName, normalized, progress, player, npc);
            TryConsumePendingWorldSignalsLocked(playerKey, playerName, normalized, progress, player, npc);
            TryAutoAdvanceFromCurrentNodeLocked(playerKey, playerName, normalized, progress, "choice_selected", player: player, npc: npc);
            SaveProgress(playerKey, playerName, progress);
            matchingQuest = normalized;
            return true;
        }

        private WorldSignalRecordResult RecordWorldSignalLocked(string playerKey, string playerName, string signal, GamePlayer player, out DynamicQuestDefinition matchingQuest)
        {
            matchingQuest = null;
            signal = (signal ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(signal) ||
                !m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
            {
                return WorldSignalRecordResult.Ignored;
            }

            foreach (DynamicQuestProgress progress in progressList)
            {
                if (progress.Completed || progress.Failed || !TryGetQuestForProgress(progress, out DynamicQuestDefinition quest))
                    continue;

                DynamicQuestDefinition normalized = NormalizeQuest(quest);
                DynamicQuestNode node = GetCurrentNode(normalized, progress);
                if (node == null)
                    continue;

                bool hasMatchingWorldSignal = NodeHasMatchingWorldSignalEdge(node, signal);
                if (!hasMatchingWorldSignal)
                {
                    if (QuestCanUseWorldSignalLater(normalized, progress, signal))
                    {
                        string normalizedSignal = NormalizePendingWorldSignal(signal);
                        if (progress.PendingWorldSignals.Add(normalizedSignal))
                        {
                            progress.UpdatedAt = DateTime.UtcNow;
                            RecordTimelineEventLocked(
                                playerKey,
                                playerName,
                                normalized.Id,
                                "world_signal_pending",
                                nodeId: node.Id,
                                detail: normalizedSignal);
                            SaveProgress(playerKey, playerName, progress);
                        }
                        matchingQuest = normalized;
                        return WorldSignalRecordResult.Pending;
                    }

                    continue;
                }

                RecordTimelineEventLocked(
                    playerKey,
                    playerName,
                    normalized.Id,
                    "world_signal",
                    nodeId: node.Id,
                    detail: signal);
                RecordPresentationBeatsLocked(playerKey, playerName, normalized, node.Id, player, null, "OnWorldSignal");
                RecordWorldSignalSceneShiftLocked(playerKey, playerName, normalized, node, signal);
                string fromNodeId = node.Id;
                progress.PendingWorldSignals.Remove(signal);
                AdvanceFromNode(progress, normalized, node, DynamicQuestEdgeCondition.WorldSignal, signal);
                RecordNodeTransitionLocked(playerKey, playerName, normalized.Id, progress, fromNodeId, "world_signal");
                RecordStoryNodeEnteredLocked(playerKey, playerName, normalized, progress, player, null);
                TryConsumePendingWorldSignalsLocked(playerKey, playerName, normalized, progress, player);
                TryAutoAdvanceFromCurrentNodeLocked(playerKey, playerName, normalized, progress, "world_signal", player: player);
                SaveProgress(playerKey, playerName, progress);
                matchingQuest = normalized;
                return WorldSignalRecordResult.Advanced;
            }

            return WorldSignalRecordResult.Ignored;
        }

        private bool RecordPlayerDiedLocked(string playerKey, string playerName, out DynamicQuestDefinition matchingQuest)
        {
            return AdvanceFirstMatchingCurrentNodeLocked(
                playerKey,
                playerName,
                "player_died",
                (edge, _) => edge.Condition == DynamicQuestEdgeCondition.PlayerDied,
                out matchingQuest);
        }

        private bool RecordPartySizeChangedLocked(string playerKey, string playerName, int partySize, out DynamicQuestDefinition matchingQuest)
        {
            partySize = Math.Max(1, partySize);
            return AdvanceFirstMatchingCurrentNodeLocked(
                playerKey,
                playerName,
                "party_size_changed",
                (edge, _) => edge.Condition == DynamicQuestEdgeCondition.PartySizeAtLeast && PartySizeMeetsEdge(edge, partySize),
                out matchingQuest);
        }

        private bool RecordTimedOutLocked(string playerKey, string playerName, DateTime nowUtc, out DynamicQuestDefinition matchingQuest)
        {
            return AdvanceFirstMatchingCurrentNodeLocked(
                playerKey,
                playerName,
                "timed_out",
                (edge, progress) => edge.Condition == DynamicQuestEdgeCondition.TimedOut && TimedOutEdgeHasElapsed(edge, progress, nowUtc),
                out matchingQuest,
                nowUtc);
        }

        private bool AdvanceFirstMatchingCurrentNodeLocked(
            string playerKey,
            string playerName,
            string trigger,
            Func<DynamicQuestEdge, DynamicQuestProgress, bool> edgePredicate,
            out DynamicQuestDefinition matchingQuest,
            DateTime? nowUtc = null)
        {
            matchingQuest = null;
            if (string.IsNullOrWhiteSpace(playerKey) ||
                edgePredicate == null ||
                !m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
            {
                return false;
            }

            foreach (DynamicQuestProgress progress in progressList)
            {
                if (progress.Completed || progress.Failed || !TryGetQuestForProgress(progress, out DynamicQuestDefinition quest))
                    continue;

                DynamicQuestDefinition normalized = NormalizeQuest(quest);
                DynamicQuestNode node = GetCurrentNode(normalized, progress);
                DynamicQuestEdge edge = FindMatchingCurrentEdge(node, edgePredicate, progress, nowUtc);
                if (edge == null)
                    continue;

                AdvanceWithEdgeLocked(playerKey, playerName, normalized, progress, node, edge, trigger);
                TryConsumePendingWorldSignalsLocked(playerKey, playerName, normalized, progress);
                TryAutoAdvanceFromCurrentNodeLocked(playerKey, playerName, normalized, progress, trigger);
                SaveProgress(playerKey, playerName, progress);
                matchingQuest = normalized;
                return true;
            }

            return false;
        }

        private bool TryConsumePendingWorldSignalsLocked(
            string playerKey,
            string playerName,
            DynamicQuestDefinition quest,
            DynamicQuestProgress progress,
            GamePlayer player = null,
            GameNPC npc = null)
        {
            if (progress?.PendingWorldSignals == null || progress.PendingWorldSignals.Count == 0 || quest == null)
                return false;

            bool consumed = false;
            int guard = 0;
            while (!progress.Completed && !progress.Failed && progress.PendingWorldSignals.Count > 0 && guard++ < 16)
            {
                DynamicQuestNode node = GetCurrentNode(quest, progress);
                if (node == null)
                    break;

                string signal = progress.PendingWorldSignals
                    .FirstOrDefault(candidate => NodeHasMatchingWorldSignalEdge(node, candidate));
                if (string.IsNullOrWhiteSpace(signal))
                    break;

                progress.PendingWorldSignals.Remove(signal);
                RecordTimelineEventLocked(
                    playerKey,
                    playerName,
                    quest.Id,
                    "world_signal",
                    nodeId: node.Id,
                    detail: signal);
                RecordPresentationBeatsLocked(playerKey, playerName, quest, node.Id, player, npc, "OnWorldSignal");
                RecordWorldSignalSceneShiftLocked(playerKey, playerName, quest, node, signal);
                string fromNodeId = node.Id;
                AdvanceFromNode(progress, quest, node, DynamicQuestEdgeCondition.WorldSignal, signal);
                RecordNodeTransitionLocked(playerKey, playerName, quest.Id, progress, fromNodeId, "world_signal");
                RecordStoryNodeEnteredLocked(playerKey, playerName, quest, progress, player, npc);
                TryAutoAdvanceFromCurrentNodeLocked(playerKey, playerName, quest, progress, "world_signal", player: player, npc: npc);
                consumed = true;
            }

            return consumed;
        }

        private bool TryAutoAdvanceFromCurrentNodeLocked(
            string playerKey,
            string playerName,
            DynamicQuestDefinition quest,
            DynamicQuestProgress progress,
            string trigger,
            int partySize = 1,
            DateTime? nowUtc = null,
            GamePlayer player = null,
            GameNPC npc = null)
        {
            if (quest == null || progress == null)
                return false;

            bool advanced = false;
            int guard = 0;
            while (!progress.Completed && !progress.Failed && guard++ < 16)
            {
                DynamicQuestNode node = GetCurrentNode(quest, progress);
                DynamicQuestEdge edge = FindAutoAdvanceEdge(node, progress, Math.Max(1, partySize), nowUtc);
                if (edge == null)
                    break;

                AdvanceWithEdgeLocked(playerKey, playerName, quest, progress, node, edge, trigger, player, npc);
                TryConsumePendingWorldSignalsLocked(playerKey, playerName, quest, progress, player, npc);
                advanced = true;
            }

            return advanced;
        }

        private void AdvanceWithEdgeLocked(
            string playerKey,
            string playerName,
            DynamicQuestDefinition quest,
            DynamicQuestProgress progress,
            DynamicQuestNode node,
            DynamicQuestEdge edge,
            string trigger,
            GamePlayer player = null,
            GameNPC npc = null)
        {
            if (quest == null || progress == null || node == null || edge == null)
                return;

            string fromNodeId = node.Id;
            AdvanceFromNode(progress, quest, node, edge);
            RecordNodeTransitionLocked(playerKey, playerName, quest.Id, progress, fromNodeId, trigger);
            RecordStoryNodeEnteredLocked(playerKey, playerName, quest, progress, player, npc);
        }

        private static bool QuestCanUseWorldSignalLater(DynamicQuestDefinition quest, DynamicQuestProgress progress, string signal)
        {
            if (quest == null || progress == null || string.IsNullOrWhiteSpace(signal))
                return false;

            return (quest.Nodes ?? Array.Empty<DynamicQuestNode>())
                .Any(node =>
                    node != null &&
                    !progress.CompletedNodeIds.Contains(node.Id) &&
                    NodeHasMatchingWorldSignalEdge(node, signal));
        }

        private static bool NodeHasMatchingWorldSignalEdge(DynamicQuestNode node, string signal)
        {
            signal = (signal ?? string.Empty).Trim();
            if (node == null || string.IsNullOrWhiteSpace(signal))
                return false;

            return (node.Edges ?? Array.Empty<DynamicQuestEdge>())
                .Any(edge =>
                    edge != null &&
                    edge.Condition == DynamicQuestEdgeCondition.WorldSignal &&
                    (string.IsNullOrWhiteSpace(edge.ConditionValue) ||
                     IsMatchingWorldSignal(edge.ConditionValue, signal)));
        }

        private static bool IsMatchingWorldSignal(string conditionValue, string signal)
        {
            string condition = (conditionValue ?? string.Empty).Trim();
            signal = (signal ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(condition) || string.IsNullOrWhiteSpace(signal))
                return false;

            if (string.Equals(condition, signal, StringComparison.OrdinalIgnoreCase))
                return true;

            bool conditionIsSpecificTimeWindow = condition.StartsWith("time-window:", StringComparison.OrdinalIgnoreCase);
            bool signalIsSpecificTimeWindow = signal.StartsWith("time-window:", StringComparison.OrdinalIgnoreCase);
            if (conditionIsSpecificTimeWindow && string.Equals(signal, "time-window", StringComparison.OrdinalIgnoreCase))
                return true;
            if (string.Equals(condition, "time-window", StringComparison.OrdinalIgnoreCase) && signalIsSpecificTimeWindow)
                return true;

            return false;
        }

        private static DynamicQuestEdge FindMatchingCurrentEdge(
            DynamicQuestNode node,
            Func<DynamicQuestEdge, DynamicQuestProgress, bool> predicate,
            DynamicQuestProgress progress,
            DateTime? nowUtc = null)
        {
            if (node == null || predicate == null)
                return null;

            return (node.Edges ?? Array.Empty<DynamicQuestEdge>())
                .Where(edge => edge != null && predicate(edge, progress))
                .OrderBy(edge => edge.Priority)
                .FirstOrDefault();
        }

        private static DynamicQuestEdge FindAutoAdvanceEdge(DynamicQuestNode node, DynamicQuestProgress progress, int partySize, DateTime? nowUtc)
        {
            if (node == null || progress == null)
                return null;

            return (node.Edges ?? Array.Empty<DynamicQuestEdge>())
                .Where(edge =>
                    edge != null &&
                    (edge.Condition == DynamicQuestEdgeCondition.Always ||
                     (edge.Condition == DynamicQuestEdgeCondition.PartySizeAtLeast && PartySizeMeetsEdge(edge, partySize)) ||
                     (edge.Condition == DynamicQuestEdgeCondition.TimedOut && TimedOutEdgeHasElapsed(edge, progress, nowUtc ?? DateTime.UtcNow))))
                .OrderBy(edge => edge.Priority)
                .FirstOrDefault();
        }

        private static bool HasObjectiveCompleteEdge(DynamicQuestNode node)
        {
            return (node?.Edges ?? Array.Empty<DynamicQuestEdge>())
                .Any(edge => edge?.Condition == DynamicQuestEdgeCondition.ObjectiveComplete);
        }

        private static bool PartySizeMeetsEdge(DynamicQuestEdge edge, int partySize)
        {
            int required = ParsePositiveConditionValue(edge?.ConditionValue, 2);
            return Math.Max(1, partySize) >= required;
        }

        private static bool TimedOutEdgeHasElapsed(DynamicQuestEdge edge, DynamicQuestProgress progress, DateTime nowUtc)
        {
            if (progress == null)
                return false;

            int requiredSeconds = ParsePositiveConditionValue(edge?.ConditionValue, 60);
            DateTime enteredAt = GetCurrentNodeEnteredAt(progress);
            return enteredAt != default && (nowUtc.ToUniversalTime() - enteredAt).TotalSeconds >= requiredSeconds;
        }

        private static int ParsePositiveConditionValue(string value, int fallback)
        {
            return int.TryParse((value ?? string.Empty).Trim(), out int parsed) && parsed > 0
                ? parsed
                : fallback;
        }

        private static void AdvanceFromNode(DynamicQuestProgress progress, DynamicQuestDefinition quest, DynamicQuestNode node, DynamicQuestEdgeCondition condition, string conditionValue)
        {
            DynamicQuestEdge edge = (node.Edges ?? Array.Empty<DynamicQuestEdge>())
                .OrderBy(item => item.Priority)
                .FirstOrDefault(item =>
                    item.Condition == condition &&
                    (string.IsNullOrWhiteSpace(item.ConditionValue) ||
                     (condition == DynamicQuestEdgeCondition.WorldSignal
                         ? IsMatchingWorldSignal(item.ConditionValue, conditionValue)
                         : string.Equals(item.ConditionValue, conditionValue, StringComparison.OrdinalIgnoreCase))));

            AdvanceFromNode(progress, quest, node, edge);
        }

        private static void AdvanceFromNode(DynamicQuestProgress progress, DynamicQuestDefinition quest, DynamicQuestNode node, DynamicQuestEdge edge)
        {
            if (progress == null || node == null)
                return;

            progress.CompletedNodeIds.Add(node.Id);
            if (edge == null)
            {
                progress.UpdatedAt = DateTime.UtcNow;
                return;
            }

            progress.CurrentNodeId = edge.ToNodeId;
            SetCurrentNodeEnteredAt(progress, DateTime.UtcNow);
            DynamicQuestNode next = (quest.Nodes ?? Array.Empty<DynamicQuestNode>())
                .FirstOrDefault(item => string.Equals(item.Id, edge.ToNodeId, StringComparison.OrdinalIgnoreCase));
            if (next?.Type == DynamicQuestNodeType.Complete)
            {
                progress.Completed = true;
                progress.IsComplete = true;
                progress.PendingWorldSignals?.Clear();
            }

            if (next?.Type == DynamicQuestNodeType.Fail)
            {
                progress.Failed = true;
                progress.PendingWorldSignals?.Clear();
            }

            progress.UpdatedAt = DateTime.UtcNow;
        }

        private static void SetCurrentNodeEnteredAt(DynamicQuestProgress progress, DateTime enteredAtUtc)
        {
            if (progress == null)
                return;

            progress.NodeCounters ??= new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
            progress.NodeCounters[CurrentNodeEnteredAtCounterKey] = ToRuntimeClockSeconds(enteredAtUtc);
        }

        private static DateTime GetCurrentNodeEnteredAt(DynamicQuestProgress progress)
        {
            if (progress?.NodeCounters == null ||
                !progress.NodeCounters.TryGetValue(CurrentNodeEnteredAtCounterKey, out int seconds))
            {
                return progress?.UpdatedAt == default ? default : progress.UpdatedAt.ToUniversalTime();
            }

            return RuntimeClockEpochUtc.AddSeconds(Math.Max(0, seconds));
        }

        private static int GetElapsedSeconds(DateTime fromUtc, DateTime toUtc)
        {
            if (fromUtc == default || toUtc == default)
                return 0;

            DateTime from = fromUtc.Kind == DateTimeKind.Utc ? fromUtc : fromUtc.ToUniversalTime();
            DateTime to = toUtc.Kind == DateTimeKind.Utc ? toUtc : toUtc.ToUniversalTime();
            return (int)Math.Clamp((to - from).TotalSeconds, 0, int.MaxValue);
        }

        private static string DescribeProgressStalledReason(DynamicQuestDefinition quest, DynamicQuestProgress progress, DynamicQuestNode currentNode)
        {
            if (progress == null)
                return "missing_progress";

            if (progress.Failed)
                return string.IsNullOrWhiteSpace(progress.CancelReason) ? "failed" : "failed:" + progress.CancelReason;

            if (progress.Completed || progress.IsComplete)
                return "complete";

            if (currentNode == null)
                return string.IsNullOrWhiteSpace(progress.CurrentNodeId) ? "missing_current_node" : "missing_current_node:" + progress.CurrentNodeId;

            if (progress.PendingWorldSignals?.Count > 0)
                return "pending_world_signal";

            if (HasEdgeCondition(currentNode, DynamicQuestEdgeCondition.TimedOut))
                return "waiting_for_timeout";

            if (HasEdgeCondition(currentNode, DynamicQuestEdgeCondition.PartySizeAtLeast))
                return "waiting_for_party_size";

            DynamicQuestEdge worldSignalEdge = GetFirstEdge(currentNode, DynamicQuestEdgeCondition.WorldSignal);
            if (worldSignalEdge != null)
                return string.IsNullOrWhiteSpace(worldSignalEdge.ConditionValue)
                    ? "waiting_for_world_signal"
                    : "waiting_for_world_signal:" + worldSignalEdge.ConditionValue;

            switch (currentNode.Type)
            {
                case DynamicQuestNodeType.Kill:
                    int targetCount = Math.Max(1, currentNode.Objective?.TargetCount ?? quest?.TargetCount ?? 1);
                    return progress.Count >= targetCount ? "target_reached_waiting_for_transition" : "waiting_for_kill_credit";
                case DynamicQuestNodeType.Choice:
                    return "waiting_for_choice";
                case DynamicQuestNodeType.ReturnToNpc:
                    return "waiting_for_npc_interaction";
                case DynamicQuestNodeType.Talk:
                    return string.IsNullOrWhiteSpace(currentNode.Objective?.NpcInternalId)
                        ? "waiting_for_story_transition"
                        : "waiting_for_npc_interaction";
                case DynamicQuestNodeType.Explore:
                    return "waiting_for_location";
                case DynamicQuestNodeType.Complete:
                    return "complete";
                case DynamicQuestNodeType.Fail:
                    return "failed";
                default:
                    return "waiting_for_event";
            }
        }

        private static bool HasEdgeCondition(DynamicQuestNode node, DynamicQuestEdgeCondition condition)
        {
            return GetFirstEdge(node, condition) != null;
        }

        private static DynamicQuestEdge GetFirstEdge(DynamicQuestNode node, DynamicQuestEdgeCondition condition)
        {
            return (node?.Edges ?? Array.Empty<DynamicQuestEdge>())
                .OrderBy(edge => edge.Priority)
                .FirstOrDefault(edge => edge.Condition == condition);
        }

        private static int ToRuntimeClockSeconds(DateTime utc)
        {
            DateTime value = utc.Kind == DateTimeKind.Utc ? utc : utc.ToUniversalTime();
            double seconds = (value - RuntimeClockEpochUtc).TotalSeconds;
            return (int)Math.Clamp(seconds, 0, int.MaxValue);
        }

        private void RecordNodeTransitionLocked(
            string playerKey,
            string playerName,
            string questId,
            DynamicQuestProgress progress,
            string fromNodeId,
            string trigger)
        {
            string toNodeId = progress?.CurrentNodeId ?? string.Empty;
            if (!string.Equals(fromNodeId, toNodeId, StringComparison.OrdinalIgnoreCase))
            {
                RecordTimelineEventLocked(
                    playerKey,
                    playerName,
                    questId,
                    "node_advanced",
                    fromNodeId: fromNodeId,
                    toNodeId: toNodeId,
                    detail: trigger);
            }

            if (progress != null && (progress.Completed || progress.IsComplete))
            {
                if (progress.Completed)
                {
                    MarkQuestCompletedLocked(playerKey, questId);
                    if (TryGetQuestForProgress(progress, out DynamicQuestDefinition completedQuest))
                    {
                        MarkStoryFamilyCompletedLocked(playerKey, completedQuest);
                        MarkWorldMemoryLocked(playerKey, completedQuest, progress);
                    }
                }

                if (HasQuestCompletedTimelineEventLocked(playerKey, questId))
                    return;

                RecordTimelineEventLocked(
                    playerKey,
                    playerName,
                    questId,
                    "quest_completed",
                    nodeId: toNodeId,
                    fromNodeId: fromNodeId,
                    toNodeId: toNodeId,
                    detail: trigger);
            }
        }

        private void RecordStoryNodeEnteredLocked(
            string playerKey,
            string playerName,
            DynamicQuestDefinition quest,
            DynamicQuestProgress progress,
            GamePlayer player,
            GameNPC npc,
            string presentationTrigger = "OnNodeEnter")
        {
            if (quest == null || progress == null)
                return;

            string nodeId = (progress.CurrentNodeId ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(nodeId))
                return;

            foreach (DynamicQuestNarrativeScene scene in ParseNarrativeScenes(quest.StoryNarrativeJson)
                         .Where(scene => string.Equals(scene.NodeId, nodeId, StringComparison.OrdinalIgnoreCase)))
            {
                bool firstSeenOnly = string.Equals(scene.RevealPolicy, "FirstSeenOnly", StringComparison.OrdinalIgnoreCase);
                bool alreadyRecorded = HasTimelineEventLocked(playerKey, quest.Id, "narrative_scene", nodeId);

                string sceneDetail = BuildNarrativeSceneDetail(scene);
                if (!string.IsNullOrWhiteSpace(sceneDetail) && (!firstSeenOnly || !alreadyRecorded))
                {
                    RecordTimelineEventLocked(
                        playerKey,
                        playerName,
                        quest.Id,
                        "narrative_scene",
                        nodeId: nodeId,
                        detail: sceneDetail);
                }

                bool journalAlreadyRecorded = HasTimelineEventLocked(playerKey, quest.Id, "journal_entry", nodeId);
                if (!string.IsNullOrWhiteSpace(scene.JournalEntry) && (!firstSeenOnly || !journalAlreadyRecorded))
                {
                    RecordTimelineEventLocked(
                        playerKey,
                        playerName,
                        quest.Id,
                        "journal_entry",
                        nodeId: nodeId,
                        detail: scene.JournalEntry);
                }

                if (player != null &&
                    !HasTimelineEventLocked(playerKey, quest.Id, "narrative_scene_presented", nodeId))
                {
                    if (PlayNarrativeScene(player, scene))
                    {
                        RecordTimelineEventLocked(
                            playerKey,
                            playerName,
                            quest.Id,
                            "narrative_scene_presented",
                            nodeId: nodeId,
                            detail: scene.Title ?? string.Empty);
                    }
                }
            }

            RecordCinematicActionsLocked(
                playerKey,
                playerName,
                quest,
                GetCurrentNode(quest, progress),
                player,
                npc,
                presentationTrigger);
            RecordPresentationBeatsLocked(playerKey, playerName, quest, nodeId, player, npc, presentationTrigger);
        }

        private void RecordPresentationBeatsLocked(
            string playerKey,
            string playerName,
            DynamicQuestDefinition quest,
            string nodeId,
            GamePlayer player,
            GameNPC npc,
            string presentationTrigger)
        {
            if (quest == null || string.IsNullOrWhiteSpace(nodeId))
                return;

            string normalizedTrigger = string.IsNullOrWhiteSpace(presentationTrigger)
                ? "OnNodeEnter"
                : presentationTrigger.Trim();

            foreach (DynamicQuestPresentationBeat beat in BuildPresentationBeatsForQuest(quest)
                         .Where(beat =>
                             string.Equals(beat.NodeId, nodeId, StringComparison.OrdinalIgnoreCase) &&
                             PresentationTriggerMatches(beat.Trigger, normalizedTrigger)))
            {
                DynamicQuestNode currentNode = (quest.Nodes ?? Array.Empty<DynamicQuestNode>())
                    .FirstOrDefault(node => string.Equals(node?.Id, nodeId, StringComparison.OrdinalIgnoreCase));
                RecordCinematicActionsLocked(playerKey, playerName, quest, currentNode, player, npc, normalizedTrigger);

                string detail = BuildPresentationBeatDetail(beat);
                if (HasTimelineEventLocked(playerKey, quest.Id, "presentation_beat", nodeId, detail))
                    continue;

                RecordTimelineEventLocked(
                    playerKey,
                    playerName,
                    quest.Id,
                    "presentation_beat",
                    nodeId: nodeId,
                    detail: detail);

                if (ShouldSpotlightPresentationBeat(beat) &&
                    !HasTimelineEventLocked(playerKey, quest.Id, "presentation_spotlight", nodeId, detail))
                {
                    RecordTimelineEventLocked(
                        playerKey,
                        playerName,
                        quest.Id,
                        "presentation_spotlight",
                        nodeId: nodeId,
                        detail: detail);
                }

                PlayPresentationBeat(player, npc, beat);
            }
        }

        private void RecordWorldSignalSceneShiftLocked(
            string playerKey,
            string playerName,
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string signal,
            bool includeLocalSceneBeats = false,
            DynamicQuestCinematicAction sourceAction = null)
        {
            if (quest == null || node == null || string.IsNullOrWhiteSpace(node.Id))
                return;

            List<DynamicQuestPresentationBeat> beats = BuildPresentationBeatsForQuest(quest)
                .Where(beat =>
                    beat != null &&
                    string.Equals(beat.NodeId, node.Id, StringComparison.OrdinalIgnoreCase) &&
                    (PresentationTriggerMatches(beat.Trigger, "OnWorldSignal") || includeLocalSceneBeats) &&
                    beat.ActorCount > 0 &&
                    !string.IsNullOrWhiteSpace(beat.CinematicAction) &&
                    !string.IsNullOrWhiteSpace(beat.SceneRole))
                .ToList();
            if (sourceAction != null)
            {
                List<DynamicQuestPresentationBeat> sourceBeats = beats
                    .Where(beat =>
                        string.Equals(beat.CinematicAction, sourceAction.NpcAction, StringComparison.OrdinalIgnoreCase) &&
                        string.Equals(beat.SceneRole, sourceAction.SceneRole, StringComparison.OrdinalIgnoreCase))
                    .ToList();
                if (sourceBeats.Count > 0)
                    beats = sourceBeats;
            }
            if (beats.Count == 0)
                return;

            string primaryAction = beats
                .Select(beat => (beat.CinematicAction ?? string.Empty).Trim())
                .FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? string.Empty;
            string primaryRole = beats
                .Select(beat => (beat.SceneRole ?? string.Empty).Trim())
                .FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? string.Empty;
            int actorCount = beats.Sum(beat => Math.Max(0, beat.ActorCount));
            int actionCount = beats
                .Select(beat => (beat.CinematicAction ?? string.Empty).Trim())
                .Where(value => !string.IsNullOrWhiteSpace(value))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .Count();
            int formationCount = beats
                .Select(beat => (beat.Formation ?? string.Empty).Trim())
                .Where(value => !string.IsNullOrWhiteSpace(value))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .Count();
            string primaryTrigger = beats
                .Select(beat => (beat.Trigger ?? string.Empty).Trim())
                .FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? "OnWorldSignal";
            string sceneShiftPhase = ResolveWorldSignalSceneShiftPhase(signal, primaryAction, primaryRole, node);
            string sceneShiftSource = ResolveWorldSignalSceneShiftSource(signal, sourceAction);
            string sceneShiftTarget = ResolveWorldSignalSceneShiftTarget(node);
            ushort sceneShiftRegion = node.Objective?.RegionId ?? quest.StartRegionId;
            string detail =
                $"world_signal_scene_shift:signal:{SafeSceneBeatToken(signal)}" +
                $":action:{SafeSceneBeatToken(primaryAction)}" +
                $":role:{SafeSceneBeatToken(primaryRole)}" +
                $":beats:{beats.Count}" +
                $":actors:{actorCount}" +
                $":actions:{actionCount}" +
                $":formations:{formationCount}" +
                $":trigger:{SafeSceneBeatToken(primaryTrigger)}" +
                $":phase:{SafeSceneBeatToken(sceneShiftPhase)}" +
                $":source:{SafeSceneBeatToken(sceneShiftSource)}" +
                $":target:{SafeSceneBeatToken(sceneShiftTarget)}" +
                $":region:{sceneShiftRegion}";

            if (HasTimelineEventLocked(playerKey, quest.Id, "world_signal_scene_shift", node.Id, detail))
                return;

            RecordTimelineEventLocked(
                playerKey,
                playerName,
                quest.Id,
                "world_signal_scene_shift",
                nodeId: node.Id,
                detail: detail);
        }

        private static string ResolveWorldSignalSceneShiftPhase(
            string signal,
            string primaryAction,
            string primaryRole,
            DynamicQuestNode node)
        {
            string localContext = $"{primaryAction ?? string.Empty} {primaryRole ?? string.Empty}".ToLowerInvariant();
            if (ContainsCinematicTerm(localContext, "retreat", "lookout", "scout", "pursuit"))
                return "pursuit";
            if (ContainsCinematicTerm(localContext, "intercept", "defend", "guard", "shield", "line", "hold", "block", "counterline", "advance"))
                return "blockade";
            if (ContainsCinematicTerm(localContext, "ambush", "strike", "battle", "combat", "threat", "kill"))
                return "battle";
            if (ContainsCinematicTerm(localContext, "ritual", "interrupt", "break", "disrupt"))
                return "disruption";
            if (ContainsCinematicTerm(localContext, "witness", "clue", "explore", "discovery", "signal", "point"))
                return "discovery";

            string context = string.Join(" ", new[]
            {
                signal,
                primaryAction,
                primaryRole,
                node?.Id,
                node?.Type.ToString()
            }.Where(value => !string.IsNullOrWhiteSpace(value))).ToLowerInvariant();

            if (ContainsCinematicTerm(context, "intercept", "defend", "guard", "shield", "line", "hold", "block", "cutoff", "counterline", "advance"))
                return "blockade";
            if (ContainsCinematicTerm(context, "ambush", "strike", "battle", "combat", "threat", "kill"))
                return "battle";
            if (ContainsCinematicTerm(context, "retreat", "escape", "lookout", "scout", "pursuit"))
                return "pursuit";
            if (ContainsCinematicTerm(context, "ritual", "interrupt", "break", "disrupt"))
                return "disruption";
            if (ContainsCinematicTerm(context, "witness", "clue", "explore", "discovery", "signal", "point"))
                return "discovery";
            if (ContainsCinematicTerm(context, "complete", "return", "aftermath", "consequence", "outcome"))
                return "aftermath";

            return "response";
        }

        private static string ResolveWorldSignalSceneShiftSource(string signal, DynamicQuestCinematicAction sourceAction)
        {
            if (sourceAction != null)
            {
                string source = string.Join("-", new[] { sourceAction.SceneRole, sourceAction.NpcAction }
                    .Where(value => !string.IsNullOrWhiteSpace(value)));
                if (!string.IsNullOrWhiteSpace(source))
                    return source;
            }

            return string.IsNullOrWhiteSpace(signal) ? "world_signal" : signal;
        }

        private static string ResolveWorldSignalSceneShiftTarget(DynamicQuestNode node)
        {
            DynamicQuestObjective objective = node?.Objective;
            if (objective == null)
                return string.IsNullOrWhiteSpace(node?.Id) ? "node" : node.Id;

            if (!string.IsNullOrWhiteSpace(objective.LocationName))
                return objective.LocationName;
            if (!string.IsNullOrWhiteSpace(objective.TargetName))
                return objective.TargetName;
            if (!string.IsNullOrWhiteSpace(objective.NpcName))
                return objective.NpcName;
            if (objective.X != 0 || objective.Y != 0)
                return "objective";

            return string.IsNullOrWhiteSpace(node?.Id) ? "node" : node.Id;
        }

        internal static IList<string> BuildCinematicActionDetailsForTest(
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string presentationTrigger = "OnNodeEnter")
        {
            return BuildCinematicActions(quest, node, presentationTrigger)
                .Select(action => action.Detail)
                .Where(detail => !string.IsNullOrWhiteSpace(detail))
                .ToList();
        }

        internal static DynamicQuestCinematicPlanSnapshot BuildCinematicPlanSnapshotForTest(DynamicQuestDefinition quest)
        {
            DynamicQuestDefinition normalized = NormalizeQuest(quest);
            List<DynamicQuestCinematicPlanItem> actions = BuildCinematicPlanItems(normalized);
            return new DynamicQuestCinematicPlanSnapshot
            {
                Enabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                GeneratedAt = DateTime.UtcNow,
                Found = normalized != null,
                QuestId = normalized?.Id ?? string.Empty,
                Title = normalized?.Title ?? string.Empty,
                Realm = normalized?.Realm ?? string.Empty,
                StartRegionId = normalized?.StartRegionId ?? 0,
                NodeCount = (normalized?.Nodes ?? Array.Empty<DynamicQuestNode>()).Count(node => node != null),
                ActionCount = actions.Count,
                TotalActorCount = actions.Where(action => action.SpawnNpcActor).Sum(action => Math.Max(0, action.ActorCount)),
                MaxActorsPerAction = GetConfiguredCinematicMaxActorsPerAction(),
                Actions = actions
            };
        }

        private static DynamicQuestCinematicCatalogItem ToCinematicCatalogItem(DynamicQuestCinematicModelEntry entry)
        {
            return new DynamicQuestCinematicCatalogItem
            {
                Model = entry?.Model ?? 0,
                Label = entry?.Label ?? string.Empty,
                Source = entry?.Source ?? string.Empty,
                Category = entry?.Category ?? string.Empty,
                Tags = (entry?.Tags ?? Array.Empty<string>())
                    .Where(tag => !string.IsNullOrWhiteSpace(tag))
                    .Take(24)
                    .ToArray()
            };
        }

        private static List<DynamicQuestCinematicPlanItem> BuildCinematicPlanItems(DynamicQuestDefinition quest)
        {
            if (quest == null)
                return new List<DynamicQuestCinematicPlanItem>();

            Dictionary<string, DynamicQuestNode> nodesById = (quest.Nodes ?? Array.Empty<DynamicQuestNode>())
                .Where(node => node != null && !string.IsNullOrWhiteSpace(node.Id))
                .GroupBy(node => node.Id.Trim(), StringComparer.OrdinalIgnoreCase)
                .ToDictionary(group => group.Key, group => group.First(), StringComparer.OrdinalIgnoreCase);

            List<DynamicQuestCinematicPlanItem> items = new();
            HashSet<string> seen = new(StringComparer.OrdinalIgnoreCase);
            foreach (DynamicQuestNode node in nodesById.Values.OrderBy(node => node.Id, StringComparer.OrdinalIgnoreCase))
            {
                foreach (string trigger in BuildCinematicPlanTriggers(quest, node))
                {
                    foreach (DynamicQuestCinematicAction action in BuildCinematicActions(quest, node, trigger))
                    {
                        if (action == null || string.IsNullOrWhiteSpace(action.Detail))
                            continue;

                        string key = $"{node.Id}|{trigger}|{action.Detail}";
                        if (!seen.Add(key))
                            continue;

                        items.Add(new DynamicQuestCinematicPlanItem
                        {
                            NodeId = node.Id ?? string.Empty,
                            NodeTitle = node.Title ?? string.Empty,
                            NodeType = node.Type,
                            Trigger = trigger,
                            Kind = action.Kind ?? string.Empty,
                            Detail = action.Detail ?? string.Empty,
                            SpawnMarker = action.SpawnMarker,
                            MarkerName = action.MarkerName ?? string.Empty,
                            MarkerModel = action.MarkerModel,
                            SpawnNpcActor = action.SpawnNpcActor,
                            NpcAction = action.NpcAction ?? string.Empty,
                            ActorName = action.ActorName ?? string.Empty,
                            NpcModel = action.NpcModel,
                            NpcRoleCategory = action.NpcRoleCategory ?? string.Empty,
                            ActorCount = action.ActorCount,
                            SceneBeatIndex = action.SceneBeatIndex,
                            SceneDelayMs = action.SceneDelayMs,
                            SceneRole = action.SceneRole ?? string.Empty,
                            Formation = action.Formation ?? string.Empty,
                            MotionPattern = action.MotionPattern ?? string.Empty,
                            MotionDistance = action.MotionDistance,
                            MotionLateral = action.MotionLateral,
                            MotionSpeed = action.MotionSpeed,
                            MotionStaggerMs = action.MotionStaggerMs,
                            FocalPoint = action.FocalPoint ?? string.Empty,
                            ActorRole = action.ActorRole ?? string.Empty,
                            InteractionStyle = action.InteractionStyle ?? string.Empty,
                            TacticalRole = action.TacticalRole ?? string.Empty,
                            ChoreographyPhases = Math.Max(1, action.ChoreographyPhases),
                            CleanupMarkers = action.CleanupMarkers,
                            Emote = action.Emote?.ToString() ?? string.Empty
                        });
                    }
                }
            }

            return items;
        }

        private static IList<string> BuildCinematicPlanTriggers(DynamicQuestDefinition quest, DynamicQuestNode node)
        {
            if (quest == null || node == null || string.IsNullOrWhiteSpace(node.Id))
                return Array.Empty<string>();

            HashSet<string> triggers = new(StringComparer.OrdinalIgnoreCase) { "OnNodeEnter" };
            foreach (DynamicQuestPresentationBeat beat in BuildPresentationBeatsForQuest(quest))
            {
                if (beat == null ||
                    !string.Equals(beat.NodeId, node.Id, StringComparison.OrdinalIgnoreCase) ||
                    string.IsNullOrWhiteSpace(beat.Trigger))
                {
                    continue;
                }

                triggers.Add(beat.Trigger.Trim());
            }

            return triggers
                .OrderBy(trigger => trigger, StringComparer.OrdinalIgnoreCase)
                .ToArray();
        }

        private void RecordCinematicActionsLocked(
            string playerKey,
            string playerName,
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            GamePlayer player,
            GameNPC npc,
            string presentationTrigger)
        {
            if (quest == null || node == null || string.IsNullOrWhiteSpace(node.Id))
                return;

            foreach (DynamicQuestCinematicAction action in BuildCinematicActions(quest, node, presentationTrigger))
            {
                if (string.IsNullOrWhiteSpace(action.Detail) ||
                    HasTimelineEventLocked(playerKey, quest.Id, "cinematic_action", node.Id, action.Detail))
                {
                    continue;
                }

                int timelineDelayMs = ResolveCinematicActionTimelineDelayMs(action);
                if (timelineDelayMs > 0 && player != null)
                {
                    QueueDelayedCinematicAction(playerKey, playerName, quest, node, player, npc, action, timelineDelayMs);
                    continue;
                }

                RecordCinematicActionNowLocked(playerKey, playerName, quest, node, player, npc, action);
            }
        }

        internal static int ResolveCinematicActionTimelineDelayMsForTest(string kind, int sceneDelayMs)
        {
            return ResolveCinematicActionTimelineDelayMs(new DynamicQuestCinematicAction
            {
                Kind = kind ?? string.Empty,
                SceneDelayMs = sceneDelayMs
            });
        }

        private static int ResolveCinematicActionTimelineDelayMs(DynamicQuestCinematicAction action)
        {
            if (action == null ||
                !string.Equals(action.Kind, "scene_beat", StringComparison.OrdinalIgnoreCase))
            {
                return 0;
            }

            return Math.Clamp(action.SceneDelayMs, 0, 6000);
        }

        private void QueueDelayedCinematicAction(
            string playerKey,
            string playerName,
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            GamePlayer player,
            GameNPC npc,
            DynamicQuestCinematicAction action,
            int delayMs)
        {
            new ECSGameTimer(player, timer =>
            {
                try
                {
                    lock (m_lock)
                    {
                        if (player.ObjectState == GameObject.eObjectState.Active &&
                            !HasTimelineEventLocked(playerKey, quest.Id, "cinematic_action", node.Id, action.Detail))
                        {
                            RecordCinematicActionNowLocked(playerKey, playerName, quest, node, player, npc, action);
                        }
                    }
                }
                catch (Exception ex)
                {
                    Log.Warn($"Dynamic quest delayed cinematic action failed for quest {quest?.Id}: {ex.Message}");
                }

                timer.Stop();
                return 0;
            }, Math.Clamp(delayMs, 1, 6000));
        }

        private void RecordCinematicActionNowLocked(
            string playerKey,
            string playerName,
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            GamePlayer player,
            GameNPC npc,
            DynamicQuestCinematicAction action)
        {
            if (quest == null ||
                node == null ||
                action == null ||
                string.IsNullOrWhiteSpace(action.Detail) ||
                HasTimelineEventLocked(playerKey, quest.Id, "cinematic_action", node.Id, action.Detail))
            {
                return;
            }

            PlayCinematicActionLocked(playerKey, quest.Id, player, npc, action);
            RecordTimelineEventLocked(
                playerKey,
                playerName,
                quest.Id,
                "cinematic_action",
                nodeId: node.Id,
                detail: action.Detail);

            RecordSceneBeatOutcomeLocked(playerKey, playerName, quest, node, action);
        }

        private void RecordSceneBeatOutcomeLocked(
            string playerKey,
            string playerName,
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            DynamicQuestCinematicAction action)
        {
            if (quest == null ||
                node == null ||
                action == null ||
                !string.Equals(action.Kind, "scene_beat", StringComparison.OrdinalIgnoreCase))
            {
                return;
            }

            string role = (action.SceneRole ?? string.Empty).Trim();
            string npcAction = (action.NpcAction ?? string.Empty).Trim();
            string formation = (action.Formation ?? string.Empty).Trim();
            string motion = string.IsNullOrWhiteSpace(action.MotionPattern)
                ? ResolveCinematicMotionProfile(action.NpcAction, action.Formation, action.SceneRole).Pattern
                : action.MotionPattern.Trim();
            string actorRole = string.IsNullOrWhiteSpace(action.ActorRole)
                ? ResolveCinematicActorRole(action.NpcAction, action.SceneRole, action.Formation)
                : action.ActorRole.Trim();
            string interactionStyle = string.IsNullOrWhiteSpace(action.InteractionStyle)
                ? ResolveCinematicInteractionStyle(action.NpcAction, actorRole, action.SceneRole, action.Formation, action.ActorCount)
                : action.InteractionStyle.Trim();
            string tacticalRole = string.IsNullOrWhiteSpace(action.TacticalRole)
                ? ResolveCinematicTacticalRole(action.NpcAction, actorRole, interactionStyle, action.SceneRole, action.Formation)
                : action.TacticalRole.Trim();
            int choreographyPhases = Math.Max(1, action.ChoreographyPhases);
            string detail =
                $"scene_beat_outcome:role:{SafeSceneBeatToken(role)}" +
                $":action:{SafeSceneBeatToken(npcAction)}" +
                $":formation:{SafeSceneBeatToken(formation)}" +
                $":motion:{SafeSceneBeatToken(motion)}" +
                $":stagger:{Math.Max(0, action.MotionStaggerMs)}" +
                $":focal:{SafeSceneBeatToken(action.FocalPoint)}" +
                $":actorRole:{SafeSceneBeatToken(actorRole)}" +
                $":choreo:{choreographyPhases}" +
                $":interact:{SafeSceneBeatToken(interactionStyle)}" +
                $":tactic:{SafeSceneBeatToken(tacticalRole)}" +
                $":beat:{Math.Max(1, action.SceneBeatIndex)}";

            if (HasTimelineEventLocked(playerKey, quest.Id, "scene_beat_outcome", node.Id, detail))
                return;

            RecordTimelineEventLocked(
                playerKey,
                playerName,
                quest.Id,
                "scene_beat_outcome",
                nodeId: node.Id,
                detail: detail);

            RecordSceneChoreographyPhaseWavesLocked(playerKey, playerName, quest, node, action, role, npcAction, actorRole);
            RecordSceneActorExchangeLocked(playerKey, playerName, quest, node, action, role, npcAction, actorRole, interactionStyle, tacticalRole);
            QueueSceneBeatWorldSignalLocked(playerKey, playerName, quest, node, action);
        }

        private void RecordSceneActorExchangeLocked(
            string playerKey,
            string playerName,
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            DynamicQuestCinematicAction action,
            string role,
            string npcAction,
            string actorRole,
            string interactionStyle,
            string tacticalRole)
        {
            string exchangeKind = ResolveCinematicActorExchangeKind(interactionStyle, tacticalRole, npcAction, actorRole);
            if (string.IsNullOrWhiteSpace(exchangeKind))
                return;

            int actorCount = Math.Clamp(action.ActorCount <= 0 ? 1 : action.ActorCount, 1, GetConfiguredCinematicMaxActorsPerAction());
            int choreographyPhases = Math.Max(1, action.ChoreographyPhases);
            string detail =
                $"scene_actor_exchange:role:{SafeSceneBeatToken(role)}" +
                $":action:{SafeSceneBeatToken(npcAction)}" +
                $":actorRole:{SafeSceneBeatToken(actorRole)}" +
                $":exchange:{SafeSceneBeatToken(exchangeKind)}" +
                $":interact:{SafeSceneBeatToken(interactionStyle)}" +
                $":tactic:{SafeSceneBeatToken(tacticalRole)}" +
                $":actors:{actorCount}" +
                $":choreo:{choreographyPhases}" +
                $":beat:{Math.Max(1, action.SceneBeatIndex)}";

            if (!HasTimelineEventLocked(playerKey, quest.Id, "scene_actor_exchange", node.Id, detail))
            {
                RecordTimelineEventLocked(
                    playerKey,
                    playerName,
                    quest.Id,
                    "scene_actor_exchange",
                    nodeId: node.Id,
                    detail: detail);
            }

            RecordSceneExchangeOutcomeLocked(
                playerKey,
                playerName,
                quest,
                node,
                action,
                role,
                npcAction,
                actorRole,
                exchangeKind,
                interactionStyle,
                tacticalRole);
        }

        private void RecordSceneExchangeOutcomeLocked(
            string playerKey,
            string playerName,
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            DynamicQuestCinematicAction action,
            string role,
            string npcAction,
            string actorRole,
            string exchangeKind,
            string interactionStyle,
            string tacticalRole)
        {
            string outcomeKind = ResolveCinematicExchangeOutcomeKind(exchangeKind, tacticalRole, npcAction, actorRole);
            if (string.IsNullOrWhiteSpace(outcomeKind))
                return;

            int actorCount = Math.Clamp(action.ActorCount <= 0 ? 1 : action.ActorCount, 1, GetConfiguredCinematicMaxActorsPerAction());
            string detail =
                $"scene_exchange_outcome:role:{SafeSceneBeatToken(role)}" +
                $":action:{SafeSceneBeatToken(npcAction)}" +
                $":actorRole:{SafeSceneBeatToken(actorRole)}" +
                $":exchange:{SafeSceneBeatToken(exchangeKind)}" +
                $":outcome:{SafeSceneBeatToken(outcomeKind)}" +
                $":interact:{SafeSceneBeatToken(interactionStyle)}" +
                $":tactic:{SafeSceneBeatToken(tacticalRole)}" +
                $":actors:{actorCount}" +
                $":beat:{Math.Max(1, action.SceneBeatIndex)}";

            if (HasTimelineEventLocked(playerKey, quest.Id, "scene_exchange_outcome", node.Id, detail))
                return;

            RecordTimelineEventLocked(
                playerKey,
                playerName,
                quest.Id,
                "scene_exchange_outcome",
                nodeId: node.Id,
                detail: detail);

            string signal = BuildSceneExchangeOutcomeWorldSignal(outcomeKind);
            RecordSceneConsequenceLocked(playerKey, playerName, quest, node, outcomeKind, signal, actorCount);
            if (!string.IsNullOrWhiteSpace(signal))
                QueueSceneWorldSignalLocked(playerKey, playerName, quest, node, signal, action);
        }

        private void RecordSceneConsequenceLocked(
            string playerKey,
            string playerName,
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string outcomeKind,
            string signal,
            int actorCount)
        {
            string consequenceKind = ResolveCinematicExchangeConsequenceKind(outcomeKind);
            if (string.IsNullOrWhiteSpace(consequenceKind))
                return;

            string detail =
                $"scene_consequence:outcome:{SafeSceneBeatToken(outcomeKind)}" +
                $":consequence:{SafeSceneBeatToken(consequenceKind)}" +
                $":signal:{SafeSceneBeatToken(signal)}" +
                $":actors:{Math.Max(1, actorCount)}";

            if (HasTimelineEventLocked(playerKey, quest.Id, "scene_consequence", node.Id, detail))
                return;

            RecordTimelineEventLocked(
                playerKey,
                playerName,
                quest.Id,
                "scene_consequence",
                nodeId: node.Id,
                detail: detail);
        }

        private void RecordSceneChoreographyPhaseWavesLocked(
            string playerKey,
            string playerName,
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            DynamicQuestCinematicAction action,
            string role,
            string npcAction,
            string actorRole)
        {
            int followUpPhaseCount = ResolveCinematicFollowUpPhaseCount(action.ChoreographyPhases);
            if (followUpPhaseCount <= 0)
                return;

            int actorCount = Math.Clamp(action.ActorCount <= 0 ? 1 : action.ActorCount, 1, GetConfiguredCinematicMaxActorsPerAction());
            for (int phaseIndex = 2; phaseIndex <= followUpPhaseCount + 1; phaseIndex++)
            {
                int firstDelay = BuildCinematicFollowUpActionDelayMs(phaseIndex, 0);
                int lastDelay = BuildCinematicFollowUpActionDelayMs(phaseIndex, actorCount - 1);
                string detail =
                    $"scene_choreography_phase:role:{SafeSceneBeatToken(role)}" +
                    $":action:{SafeSceneBeatToken(npcAction)}" +
                    $":actorRole:{SafeSceneBeatToken(actorRole)}" +
                    $":phase:{phaseIndex}" +
                    $":actors:{actorCount}" +
                    $":delay:{firstDelay}-{lastDelay}";

                if (HasTimelineEventLocked(playerKey, quest.Id, "scene_choreography_phase", node.Id, detail))
                    continue;

                RecordTimelineEventLocked(
                    playerKey,
                    playerName,
                    quest.Id,
                    "scene_choreography_phase",
                    nodeId: node.Id,
                    detail: detail);
            }
        }

        private static string ResolveCinematicActorExchangeKind(
            string interactionStyle,
            string tacticalRole,
            string npcAction,
            string actorRole)
        {
            string interaction = (interactionStyle ?? string.Empty).Trim().ToLowerInvariant();
            string tactic = (tacticalRole ?? string.Empty).Trim().ToLowerInvariant();
            string action = (npcAction ?? string.Empty).Trim().ToLowerInvariant();
            string role = (actorRole ?? string.Empty).Trim().ToLowerInvariant();

            if (interaction is "none" or "signal" || string.IsNullOrWhiteSpace(interaction))
                return string.Empty;

            if (interaction == "clash" || tactic == "flank" || role == "strike")
                return "weapon_clash";
            if (interaction == "block" || tactic == "screen" || role == "defend")
                return "shield_block";
            if (interaction == "interrupt" || tactic == "suppress" || action == "ritual_interrupt" || role == "disrupt")
                return "ritual_break";
            if (interaction == "pursuit" || tactic == "withdraw" || role == "retreat")
                return "pursuit_cutoff";
            if (interaction == "standoff" || tactic == "pressure" || role == "brace")
                return "threat_pressure";

            return "actor_exchange";
        }

        private static string ResolveCinematicExchangeOutcomeKind(
            string exchangeKind,
            string tacticalRole,
            string npcAction,
            string actorRole)
        {
            string exchange = (exchangeKind ?? string.Empty).Trim().ToLowerInvariant();
            string tactic = (tacticalRole ?? string.Empty).Trim().ToLowerInvariant();
            string action = (npcAction ?? string.Empty).Trim().ToLowerInvariant();
            string role = (actorRole ?? string.Empty).Trim().ToLowerInvariant();

            if (exchange == "weapon_clash")
                return tactic == "flank" || role == "strike" ? "line_breached" : "strike_checked";
            if (exchange == "shield_block")
                return "line_held";
            if (exchange == "ritual_break" || action == "ritual_interrupt")
                return "ritual_disrupted";
            if (exchange == "pursuit_cutoff")
                return "escape_cutoff";
            if (exchange == "threat_pressure")
                return "standoff_escalated";
            if (exchange == "actor_exchange")
                return "pressure_shifted";

            return string.Empty;
        }

        private static string ResolveCinematicExchangeConsequenceKind(string outcomeKind)
        {
            string outcome = (outcomeKind ?? string.Empty).Trim().ToLowerInvariant();
            if (outcome == "line_breached")
                return "breach_opens";
            if (outcome == "strike_checked")
                return "threat_checked";
            if (outcome == "line_held")
                return "defense_stabilized";
            if (outcome == "ritual_disrupted")
                return "ritual_fails";
            if (outcome == "escape_cutoff")
                return "escape_route_closed";
            if (outcome == "standoff_escalated")
                return "pressure_mounts";
            if (outcome == "pressure_shifted")
                return "balance_changes";

            return string.Empty;
        }

        private void QueueSceneBeatWorldSignalLocked(
            string playerKey,
            string playerName,
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            DynamicQuestCinematicAction action)
        {
            string signal = BuildSceneBeatWorldSignal(action);
            QueueSceneWorldSignalLocked(playerKey, playerName, quest, node, signal, action);
        }

        private void QueueSceneWorldSignalLocked(
            string playerKey,
            string playerName,
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string signal,
            DynamicQuestCinematicAction sourceAction = null)
        {
            if (string.IsNullOrWhiteSpace(signal) || !DynamicQuestWorldSignalPolicy.IsAllowed(signal))
                return;

            RecordTimelineEventLocked(
                playerKey,
                playerName,
                quest.Id,
                "scene_world_signal",
                nodeId: node.Id,
                detail: signal);

            if (!m_playerProgress.TryGetValue(playerKey ?? string.Empty, out List<DynamicQuestProgress> progressList))
                return;

            DynamicQuestProgress progress = progressList.FirstOrDefault(item =>
                item != null &&
                !item.Completed &&
                !item.Failed &&
                string.Equals(item.QuestId, quest.Id, StringComparison.OrdinalIgnoreCase));
            if (progress == null)
                return;

            DynamicQuestNode currentNode = GetCurrentNode(quest, progress);
            if (NodeHasMatchingWorldSignalEdge(currentNode, signal))
                return;

            if (!QuestCanUseWorldSignalLater(quest, progress, signal))
            {
                RecordWorldSignalSceneShiftLocked(
                    playerKey,
                    playerName,
                    quest,
                    node,
                    signal,
                    includeLocalSceneBeats: true,
                    sourceAction);
                return;
            }

            string normalized = NormalizePendingWorldSignal(signal);
            if (progress.PendingWorldSignals.Add(normalized))
            {
                progress.UpdatedAt = DateTime.UtcNow;
                if (HasTimelineEventLocked(playerKey, quest.Id, "world_signal_pending", node.Id, normalized))
                    return;

                RecordTimelineEventLocked(
                    playerKey,
                    playerName,
                    quest.Id,
                    "world_signal_pending",
                    nodeId: node.Id,
                    detail: normalized);
            }
        }

        private static string BuildSceneBeatWorldSignal(DynamicQuestCinematicAction action)
        {
            string role = SafeSceneBeatToken(action?.SceneRole);
            return string.Equals(role, "unknown", StringComparison.OrdinalIgnoreCase)
                ? string.Empty
                : $"scene:{role}";
        }

        private static string BuildSceneExchangeOutcomeWorldSignal(string outcomeKind)
        {
            string outcome = SafeSceneBeatToken(outcomeKind);
            return string.Equals(outcome, "unknown", StringComparison.OrdinalIgnoreCase)
                ? string.Empty
                : $"scene:{outcome}";
        }

        private static string SafeSceneBeatToken(string value)
        {
            value = (value ?? string.Empty).Trim().ToLowerInvariant();
            if (string.IsNullOrWhiteSpace(value))
                return "unknown";

            char[] chars = value.ToCharArray();
            for (int index = 0; index < chars.Length; index++)
            {
                char ch = chars[index];
                if (!(char.IsLetterOrDigit(ch) || ch == '-' || ch == '_' || ch == '.'))
                    chars[index] = '-';
            }

            return new string(chars);
        }

        private static IList<DynamicQuestCinematicAction> BuildCinematicActions(
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string presentationTrigger)
        {
            if (quest == null || node == null)
                return Array.Empty<DynamicQuestCinematicAction>();

            string trigger = string.IsNullOrWhiteSpace(presentationTrigger) ? "OnNodeEnter" : presentationTrigger.Trim();
            string nodeId = (node.Id ?? string.Empty).Trim();
            string nodeKind = node.Type.ToString().ToLowerInvariant();
            string target = PresentationTargetName(quest, node);
            string location = PresentationLocationName(quest, node);
            string sceneContext = BuildCinematicSceneContext(quest, node, trigger);
            List<DynamicQuestCinematicAction> actions = new();

            if (string.Equals(trigger, "OnComplete", StringComparison.OrdinalIgnoreCase) ||
                node.Type == DynamicQuestNodeType.Complete)
            {
                actions.Add(new DynamicQuestCinematicAction
                {
                    Kind = "cleanup",
                    Detail = $"cleanup:{trigger}:{nodeId}",
                    CleanupMarkers = true
                });
                actions.Add(BuildNpcFocusAction(trigger, nodeKind, eEmote.Bow));
                return actions;
            }

            if (string.Equals(trigger, "OnChoiceSelected", StringComparison.OrdinalIgnoreCase))
            {
                string npcAction = SelectCinematicNpcAction(node, trigger, sceneContext, "guard_advance");
                actions.Add(BuildMarkerAction(quest, node, trigger, nodeKind, BuildContextualMarkerName("Decision echo", location, sceneContext), $"choice signal echo {sceneContext}"));
                actions.Add(BuildNpcAction(quest, node, trigger, nodeKind, npcAction, SelectCinematicEmote(quest, node, trigger, npcAction, eEmote.Point), $"choice guard advance {sceneContext}"));
                actions.AddRange(BuildExplicitPresentationSetPieceActions(quest, node, trigger, nodeKind, sceneContext));
                actions.AddRange(BuildSceneDirectorActions(quest, node, trigger, nodeKind, sceneContext));
                return actions;
            }

            switch (node.Type)
            {
                case DynamicQuestNodeType.Talk:
                    actions.Add(BuildNpcAction(quest, node, trigger, nodeKind, SelectCinematicNpcAction(node, trigger, sceneContext, "challenge"), SelectCinematicEmote(quest, node, trigger, "challenge", eEmote.LetsGo), $"quest giver challenge guard {sceneContext}"));
                    if (SceneSuggestsMarker(sceneContext))
                        actions.Add(BuildMarkerAction(quest, node, trigger, nodeKind, BuildContextualMarkerName("Opening clue", location, sceneContext), $"opening clue {sceneContext}"));
                    break;
                case DynamicQuestNodeType.ReturnToNpc:
                    actions.Add(BuildNpcAction(quest, node, trigger, nodeKind, SelectCinematicNpcAction(node, trigger, sceneContext, "fallback_guard"), SelectCinematicEmote(quest, node, trigger, "fallback_guard", eEmote.BangOnShield), $"return defense guard {sceneContext}"));
                    if (SceneSuggestsMarker(sceneContext))
                        actions.Add(BuildMarkerAction(quest, node, trigger, nodeKind, BuildContextualMarkerName("Return sign", location, sceneContext), $"return sign {sceneContext}"));
                    break;
                case DynamicQuestNodeType.Explore:
                    actions.Add(BuildMarkerAction(quest, node, trigger, nodeKind, BuildContextualMarkerName("Quest trace", location, sceneContext), $"explore trace evidence {sceneContext}"));
                    actions.AddRange(BuildSupplementalMarkerActions(quest, node, trigger, nodeKind, location, sceneContext));
                    if (SceneSuggestsNpcActor(sceneContext))
                    {
                        string npcAction = SelectCinematicNpcAction(node, trigger, sceneContext, "witness_point");
                        actions.Add(BuildNpcAction(quest, node, trigger, nodeKind, npcAction, SelectCinematicEmote(quest, node, trigger, npcAction, eEmote.Point), $"explore scout witness {sceneContext}"));
                    }
                    break;
                case DynamicQuestNodeType.Kill:
                    actions.Add(BuildMarkerAction(quest, node, trigger, nodeKind, BuildContextualMarkerName("Threat sign", target, sceneContext), $"threat battle sign {sceneContext}"));
                    actions.AddRange(BuildSupplementalMarkerActions(quest, node, trigger, nodeKind, target, sceneContext));
                    {
                        string npcAction = SelectCinematicNpcAction(node, trigger, sceneContext, "combat_stance");
                        actions.Add(BuildNpcAction(quest, node, trigger, nodeKind, npcAction, SelectCinematicEmote(quest, node, trigger, npcAction, eEmote.PlayerPrepare), $"combat guard defense {sceneContext}"));
                    }
                    break;
                case DynamicQuestNodeType.Choice:
                    actions.Add(BuildMarkerAction(quest, node, trigger, nodeKind, BuildContextualMarkerName("Decision point", location, sceneContext), $"choice decision signal {sceneContext}"));
                    {
                        string npcAction = SelectCinematicNpcAction(node, trigger, sceneContext, "hold_ground");
                        actions.Add(BuildNpcAction(quest, node, trigger, nodeKind, npcAction, SelectCinematicEmote(quest, node, trigger, npcAction, eEmote.PlayerPrepare), $"choice defense standoff {sceneContext}"));
                    }
                    break;
            }

            actions.AddRange(BuildExplicitPresentationSetPieceActions(quest, node, trigger, nodeKind, sceneContext));
            actions.AddRange(BuildSceneDirectorActions(quest, node, trigger, nodeKind, sceneContext));
            return actions;
        }

        private static IList<DynamicQuestCinematicAction> BuildExplicitPresentationSetPieceActions(
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string trigger,
            string nodeKind,
            string sceneContext)
        {
            if (quest == null || node == null)
                return Array.Empty<DynamicQuestCinematicAction>();

            List<DynamicQuestCinematicAction> actions = new();
            int index = 0;
            foreach (DynamicQuestPresentationBeat beat in BuildMatchingPresentationBeats(quest, node, trigger))
            {
                string npcAction = (beat?.CinematicAction ?? string.Empty).Trim().ToLowerInvariant();
                if (string.IsNullOrWhiteSpace(npcAction))
                    continue;

                index++;
                int actorCount = Math.Clamp(beat.ActorCount <= 0 ? DefaultExplicitActorCount(npcAction) : beat.ActorCount, 1, GetConfiguredCinematicMaxActorsPerAction());
                string role = string.IsNullOrWhiteSpace(beat.SceneRole)
                    ? DefaultSceneRoleForAction(npcAction)
                    : beat.SceneRole;
                string formation = string.IsNullOrWhiteSpace(beat.Formation)
                    ? DefaultFormationForAction(npcAction)
                    : beat.Formation;
                string extraContext = $"explicit presentation set-piece {beat.Text} {beat.Emotion} {sceneContext}";
                actions.Add(BuildSceneBeatAction(
                    quest,
                    node,
                    trigger,
                    nodeKind,
                    20 + index,
                    Math.Clamp(beat.DelayMs, 0, 6000),
                    role,
                    npcAction,
                    formation,
                    actorCount,
                    extraContext));
            }

            return actions;
        }

        private static IList<DynamicQuestCinematicAction> BuildChoiceOutcomeSetPieceActions(
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            DynamicQuestChoice choice)
        {
            if (quest == null || node == null || choice == null)
                return Array.Empty<DynamicQuestCinematicAction>();

            string outcome = ResolveChoiceOutcomeStyle(choice);
            string choiceId = SafeSceneBeatToken(choice.Id);
            string context = $"choice outcome {choiceId} {choice.Label} {choice.Text} {choice.Consequence} {BuildCinematicSceneContext(quest, node, "OnChoiceSelected")}";
            List<DynamicQuestCinematicAction> actions = new()
            {
                BuildSceneBeatAction(
                    quest,
                    node,
                    "OnChoiceSelected",
                    node.Type.ToString().ToLowerInvariant(),
                    40,
                    0,
                    $"choice_{outcome}",
                    ChoiceOutcomePrimaryAction(outcome),
                    ChoiceOutcomeFormation(outcome),
                    ChoiceOutcomeActorCount(outcome),
                    context)
            };

            if (string.Equals(outcome, "pursuit", StringComparison.OrdinalIgnoreCase))
            {
                actions.Add(BuildSceneBeatAction(
                    quest,
                    node,
                    "OnChoiceSelected",
                    node.Type.ToString().ToLowerInvariant(),
                    41,
                    850,
                    "choice_pursuit_witness",
                    "scout_retreat",
                    "escape",
                    2,
                    context));
            }
            else if (string.Equals(outcome, "containment", StringComparison.OrdinalIgnoreCase))
            {
                actions.Add(BuildSceneBeatAction(
                    quest,
                    node,
                    "OnChoiceSelected",
                    node.Type.ToString().ToLowerInvariant(),
                    41,
                    850,
                    "choice_containment_screen",
                    "defender_intercept",
                    "line",
                    3,
                    context));
            }

            return actions;
        }

        private static string ResolveChoiceOutcomeStyle(DynamicQuestChoice choice)
        {
            string choiceId = (choice?.Id ?? string.Empty).Trim().ToLowerInvariant();
            string context = $"{choiceId} {choice?.Label} {choice?.Text} {choice?.Consequence}".ToLowerInvariant();

            if (ContainsCinematicTerm(choiceId, "safe", "secure", "contain", "guard"))
                return "containment";
            if (ContainsCinematicTerm(choiceId, "followup", "hunt", "pursue", "track"))
                return "pursuit";
            if (ContainsCinematicTerm(context, "followup", "추적", "근원", "위협", "hunt", "pursue", "track", "root"))
                return "pursuit";
            if (ContainsCinematicTerm(context, "safe", "안전", "봉합", "보호", "guard", "secure", "contain"))
                return "containment";
            if (ContainsCinematicTerm(context, "truth", "진실", "reveal", "expose", "record", "기록"))
                return "revelation";
            if (ContainsCinematicTerm(context, "mercy", "spare", "살려", "용서"))
                return "mercy";

            return "fallout";
        }

        private static string ResolveChoiceOutcomeTactic(DynamicQuestChoice choice, string outcome)
        {
            return (outcome ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "pursuit" => "withdraw",
                "containment" => "screen",
                "revelation" => "spot",
                "mercy" => "screen",
                _ => "pressure"
            };
        }

        private static string ChoiceOutcomePrimaryAction(string outcome)
        {
            return (outcome ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "pursuit" => "guard_advance",
                "containment" => "defender_intercept",
                "revelation" => "witness_point",
                "mercy" => "fallback_guard",
                _ => "threat_standoff"
            };
        }

        private static string ChoiceOutcomeFormation(string outcome)
        {
            return (outcome ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "pursuit" => "escort",
                "containment" => "line",
                "revelation" => "escort",
                "mercy" => "line",
                _ => "line"
            };
        }

        private static int ChoiceOutcomeActorCount(string outcome)
        {
            return (outcome ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "pursuit" => 4,
                "containment" => 5,
                "revelation" => 3,
                "mercy" => 3,
                _ => 4
            };
        }

        private static IList<DynamicQuestCinematicAction> BuildSceneDirectorActions(
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string trigger,
            string nodeKind,
            string sceneContext)
        {
            if (!ShouldUseSceneDirector(quest, sceneContext))
                return Array.Empty<DynamicQuestCinematicAction>();
            if (ShouldDeferSceneDirectorOnNodeEnter(quest, node, trigger))
                return Array.Empty<DynamicQuestCinematicAction>();

            List<DynamicQuestCinematicAction> actions = new();
            bool ritualSetPiece = ContainsCinematicTerm(sceneContext, "의식", "성물", "룬", "토템", "ritual", "relic", "rune", "totem");
            switch (node.Type)
            {
                case DynamicQuestNodeType.Talk:
                    if (PresentationTriggerMatches("OnNodeEnter", trigger))
                    {
                        actions.Add(BuildSceneBeatAction(quest, node, trigger, nodeKind, 1, 0, "contract", "witness_point", "escort", 1, $"quiet contract witness {sceneContext}"));
                    }
                    break;
                case DynamicQuestNodeType.Explore:
                    if (PresentationTriggerMatches("OnExplore", trigger) || PresentationTriggerMatches("OnNodeEnter", trigger))
                    {
                        actions.Add(BuildSceneBeatAction(quest, node, trigger, nodeKind, 1, 0, "witness", "witness_point", "escort", 1, $"witness points clue route {sceneContext}"));
                        actions.Add(BuildSceneBeatAction(quest, node, trigger, nodeKind, 2, 900, "lookout", "scout_retreat", "patrol", 2, $"lookout retreats from clue route {sceneContext}"));
                        if (ritualSetPiece)
                            actions.Add(BuildSceneBeatAction(quest, node, trigger, nodeKind, 3, 1500, "ritual", "ritual_interrupt", "line", 3, $"ritual guard interrupts relic sign {sceneContext}"));
                        actions.Add(BuildSceneBeatAction(quest, node, trigger, nodeKind, ritualSetPiece ? 4 : 3, ritualSetPiece ? 2300 : 1600, "route_screen", "guard_advance", "escort", 3, $"screening guard advances along clue route {sceneContext}"));
                    }
                    break;
                case DynamicQuestNodeType.Kill:
                    if (PresentationTriggerMatches("OnKill", trigger) || PresentationTriggerMatches("OnNodeEnter", trigger))
                    {
                        int nextBeatIndex = 1;
                        if (!HasExplicitPresentationSetPieceAction(quest, node, "ambush_reveal"))
                            actions.Add(BuildSceneBeatAction(quest, node, trigger, nodeKind, nextBeatIndex++, 0, "ambush", "ambush_reveal", "ambush", 5, $"ambush reveals around assassination target {sceneContext}"));
                        if (!HasExplicitPresentationSetPieceAction(quest, node, "defender_intercept"))
                            actions.Add(BuildSceneBeatAction(quest, node, trigger, nodeKind, nextBeatIndex++, 800, "intercept", "defender_intercept", "line", 4, $"defenders intercept escape path {sceneContext}"));
                        if (!HasExplicitPresentationSetPieceAction(quest, node, "scout_retreat"))
                            actions.Add(BuildSceneBeatAction(quest, node, trigger, nodeKind, nextBeatIndex++, 1700, "witness_escape", "scout_retreat", "escape", 2, $"witness retreats after strike {sceneContext}"));
                        if (ritualSetPiece && !HasExplicitPresentationSetPieceAction(quest, node, "ritual_interrupt"))
                            actions.Add(BuildSceneBeatAction(quest, node, trigger, nodeKind, nextBeatIndex++, 2400, "ritual_break", "ritual_interrupt", "line", 3, $"ritual breaks after target falls {sceneContext}"));
                        if (!HasExplicitPresentationSetPieceAction(quest, node, "combat_stance"))
                            actions.Add(BuildSceneBeatAction(quest, node, trigger, nodeKind, nextBeatIndex++, ritualSetPiece ? 3100 : 2400, "counterline", "combat_stance", "line", 6, $"counterline forms after strike {sceneContext}"));
                        if (!HasExplicitPresentationSetPieceAction(quest, node, "hold_ground"))
                            actions.Add(BuildSceneBeatAction(quest, node, trigger, nodeKind, nextBeatIndex, ritualSetPiece ? 3900 : 3200, "shield_hold", "hold_ground", "line", 5, $"shield line holds ground around aftermath {sceneContext}"));
                    }
                    break;
                case DynamicQuestNodeType.Choice:
                    if (PresentationTriggerMatches("OnChoiceShown", trigger) || PresentationTriggerMatches("OnChoiceSelected", trigger))
                    {
                        actions.Add(BuildSceneBeatAction(quest, node, trigger, nodeKind, 1, 0, "confrontation", "threat_standoff", "line", 4, $"choice confrontation witnesses decision {sceneContext}"));
                        actions.Add(BuildSceneBeatAction(quest, node, trigger, nodeKind, 2, 1000, "fallout", "guard_advance", "escort", 2, $"fallout escort moves after choice {sceneContext}"));
                        actions.Add(BuildSceneBeatAction(quest, node, trigger, nodeKind, 3, 1700, "choice_screen", "defender_intercept", "line", 3, $"choice screen blocks immediate retaliation {sceneContext}"));
                        actions.Add(BuildSceneBeatAction(quest, node, trigger, nodeKind, 4, 2500, "choice_fallback", "fallback_guard", "escort", 2, $"choice fallback guard clears the scene {sceneContext}"));
                    }
                    break;
                case DynamicQuestNodeType.ReturnToNpc:
                    if (PresentationTriggerMatches("OnNodeEnter", trigger))
                    {
                        actions.Add(BuildSceneBeatAction(quest, node, trigger, nodeKind, 1, 0, "debrief", "fallback_guard", "escort", 2, $"debrief guards fall back with report {sceneContext}"));
                    }
                    break;
            }

            return actions;
        }

        private static bool HasExplicitPresentationSetPieceAction(
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string npcAction)
        {
            string normalizedAction = (npcAction ?? string.Empty).Trim();
            if (quest == null ||
                node == null ||
                string.IsNullOrWhiteSpace(node.Id) ||
                string.IsNullOrWhiteSpace(normalizedAction))
            {
                return false;
            }

            return BuildPresentationBeatsForQuest(quest).Any(beat =>
                beat != null &&
                string.Equals(beat.NodeId, node.Id, StringComparison.OrdinalIgnoreCase) &&
                string.Equals(beat.CinematicAction, normalizedAction, StringComparison.OrdinalIgnoreCase));
        }

        private static bool ShouldDeferSceneDirectorOnNodeEnter(
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string trigger)
        {
            if (!PresentationTriggerMatches("OnNodeEnter", trigger) ||
                quest == null ||
                node == null ||
                string.IsNullOrWhiteSpace(node.Id))
            {
                return false;
            }

            if (node.Type is not DynamicQuestNodeType.Explore and
                not DynamicQuestNodeType.Kill and
                not DynamicQuestNodeType.Choice)
            {
                return false;
            }

            return BuildPresentationBeatsForQuest(quest).Any(beat =>
                beat != null &&
                string.Equals(beat.NodeId, node.Id, StringComparison.OrdinalIgnoreCase) &&
                !PresentationTriggerMatches("OnNodeEnter", beat.Trigger) &&
                (!string.IsNullOrWhiteSpace(beat.CinematicAction) ||
                 beat.ActorCount > 0 ||
                 !string.IsNullOrWhiteSpace(beat.SceneRole) ||
                 !string.IsNullOrWhiteSpace(beat.Formation)));
        }

        private static bool ShouldUseSceneDirector(DynamicQuestDefinition quest, string sceneContext)
        {
            string tags = string.Join(" ", quest?.Tags ?? Array.Empty<string>());
            string context = $"{tags} {sceneContext}".ToLowerInvariant();
            return ContainsCinematicTerm(
                context,
                "scene-director",
                "story-cinematic",
                "dark-brotherhood",
                "assassin",
                "assassination",
                "암살",
                "목격",
                "증인",
                "매복",
                "배신",
                "탈출",
                "witness",
                "ambush",
                "betrayal",
                "escape");
        }

        private static string BuildCinematicSceneContext(DynamicQuestDefinition quest, DynamicQuestNode node, string trigger)
        {
            if (quest == null || node == null)
                return string.Empty;

            List<string> parts = new()
            {
                trigger,
                node.Id,
                node.Type.ToString(),
                node.Title,
                node.Text,
                node.Objective?.TargetName,
                node.Objective?.LocationName,
                node.Objective?.NpcName,
                quest.Title,
                quest.Realm,
                string.Join(" ", quest.Tags ?? Array.Empty<string>())
            };

            foreach (DynamicQuestPresentationBeat beat in ParsePresentationBeats(quest.StoryPresentationJson)
                         .Where(beat =>
                             beat != null &&
                             string.Equals(beat.NodeId, node.Id, StringComparison.OrdinalIgnoreCase) &&
                             PresentationTriggerMatches(beat.Trigger, trigger)))
            {
                parts.Add(beat.Speaker);
                parts.Add(beat.Text);
                parts.Add(beat.Emotion);
                parts.Add(beat.Emote);
                parts.Add(beat.CinematicAction);
                parts.Add(beat.SceneRole);
                parts.Add(beat.Formation);
            }

            foreach (DynamicQuestNarrativeScene scene in ParseNarrativeScenes(quest.StoryNarrativeJson)
                         .Where(scene => string.Equals(scene?.NodeId, node.Id, StringComparison.OrdinalIgnoreCase)))
            {
                parts.Add(scene.SceneType);
                parts.Add(scene.Title);
                parts.Add(scene.Body);
                parts.Add(scene.JournalEntry);
                parts.Add(scene.Mood);
            }

            return string.Join(" ", parts.Where(value => !string.IsNullOrWhiteSpace(value)));
        }

        private static int DefaultExplicitActorCount(string npcAction)
        {
            return (npcAction ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "ambush_reveal" => 8,
                "defender_intercept" => 6,
                "ritual_interrupt" => 5,
                "threat_standoff" => 6,
                "combat_stance" => 5,
                "hold_ground" => 4,
                "guard_advance" => 4,
                "scout_retreat" => 3,
                _ => 2
            };
        }

        private static string DefaultSceneRoleForAction(string npcAction)
        {
            return (npcAction ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "ambush_reveal" => "ambush",
                "defender_intercept" => "intercept",
                "scout_retreat" => "lookout",
                "ritual_interrupt" => "ritual",
                "threat_standoff" => "confrontation",
                "combat_stance" => "battle",
                "hold_ground" => "defense",
                "guard_advance" => "fallout",
                "fallback_guard" => "debrief",
                _ => "scene"
            };
        }

        private static string DefaultFormationForAction(string npcAction)
        {
            return (npcAction ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "ambush_reveal" => "ambush",
                "defender_intercept" => "line",
                "scout_retreat" => "escape",
                "ritual_interrupt" => "line",
                "threat_standoff" => "line",
                "guard_advance" => "escort",
                "fallback_guard" => "escort",
                _ => "ring"
            };
        }

        private static IList<DynamicQuestPresentationBeat> BuildMatchingPresentationBeats(
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string trigger)
        {
            if (quest == null || node == null || string.IsNullOrWhiteSpace(node.Id))
                return Array.Empty<DynamicQuestPresentationBeat>();

            return BuildPresentationBeatsForQuest(quest)
                .Where(beat =>
                    beat != null &&
                    string.Equals(beat.NodeId, node.Id, StringComparison.OrdinalIgnoreCase) &&
                    PresentationTriggerMatches(beat.Trigger, trigger))
                .ToArray();
        }

        private static string SelectCinematicNpcAction(
            DynamicQuestNode node,
            string trigger,
            string sceneContext,
            string fallbackAction)
        {
            string context = (sceneContext ?? string.Empty).ToLowerInvariant();
            if (ContainsCinematicTerm(context, "매복", "습격", "기습", "ambush", "reveal", "surprise"))
                return "ambush_reveal";
            if (ContainsCinematicTerm(context, "가로막", "차단", "막아서", "intercept", "block", "cut off"))
                return "defender_intercept";
            if (ContainsCinematicTerm(context, "퇴각", "탈출로", "망보", "물러나는 정찰", "scout retreat", "scout_retreat", "lookout retreat", "escape route"))
                return "scout_retreat";
            if (ContainsCinematicTerm(context, "증인", "목격", "가리", "정찰", "witness", "scout", "guide"))
                return "witness_point";
            if (ContainsCinematicTerm(context, "의식", "ritual", "interrupt"))
                return "ritual_interrupt";
            if (ContainsCinematicTerm(context, "대치", "마주", "standoff", "face off", "confront"))
                return "threat_standoff";
            if (ContainsCinematicTerm(context, "전투", "교전", "습격", "combat", "battle", "attack", "strike", "threat"))
                return "combat_stance";
            if (ContainsCinematicTerm(context, "방어", "막아", "막고", "지켜", "버티", "방패", "defense", "defend", "guard", "shield", "hold ground", "standoff"))
                return "hold_ground";
            if (ContainsCinematicTerm(context, "전진", "다가", "추격", "advance", "approach", "pursue"))
                return "guard_advance";
            if (ContainsCinematicTerm(context, "후퇴", "물러", "fallback", "fall back", "retreat", "withdraw"))
                return "fallback_guard";

            if (node?.Type == DynamicQuestNodeType.Kill)
                return "combat_stance";
            if (string.Equals(trigger, "OnChoiceSelected", StringComparison.OrdinalIgnoreCase))
                return "guard_advance";

            return string.IsNullOrWhiteSpace(fallbackAction) ? "hold_ground" : fallbackAction;
        }

        private static eEmote SelectCinematicEmote(
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string trigger,
            string npcAction,
            eEmote fallback)
        {
            string normalizedAction = (npcAction ?? string.Empty).Trim().ToLowerInvariant();
            if (normalizedAction is "fallback_guard" or "combat_stance" or "hold_ground" or "ambush_reveal" or "defender_intercept" or "scout_retreat" or "ritual_interrupt" or "threat_standoff")
            {
                return normalizedAction switch
                {
                    "fallback_guard" => eEmote.BangOnShield,
                    "combat_stance" => eEmote.PlayerPrepare,
                    "hold_ground" => eEmote.PlayerPrepare,
                    "ambush_reveal" => eEmote.LetsGo,
                    "defender_intercept" => eEmote.BangOnShield,
                    "scout_retreat" => eEmote.Point,
                    "ritual_interrupt" => eEmote.PlayerPrepare,
                    "threat_standoff" => eEmote.PlayerPrepare,
                    _ => fallback
                };
            }

            DynamicQuestPresentationBeat beat = BuildMatchingPresentationBeats(quest, node, trigger)
                .FirstOrDefault(item => TryResolvePresentationEmote(item, out _));
            if (beat != null && TryResolvePresentationEmote(beat, out eEmote emote))
                return emote;

            return normalizedAction switch
            {
                "witness_point" => eEmote.Point,
                "guard_advance" => eEmote.Point,
                "challenge" => eEmote.LetsGo,
                _ => fallback
            };
        }

        private static bool SceneSuggestsMarker(string sceneContext)
        {
            string context = (sceneContext ?? string.Empty).ToLowerInvariant();
            return ContainsCinematicTerm(
                context,
                "흔적",
                "증거",
                "표식",
                "기록",
                "책",
                "성물",
                "룬",
                "토템",
                "불",
                "횃불",
                "무기",
                "화살",
                "문",
                "관문",
                "clue",
                "trace",
                "evidence",
                "record",
                "journal",
                "relic",
                "rune",
                "totem",
                "flame",
                "torch",
                "weapon",
                "arrow",
                "gate",
                "portal");
        }

        private static bool SceneSuggestsNpcActor(string sceneContext)
        {
            string context = (sceneContext ?? string.Empty).ToLowerInvariant();
            return ContainsCinematicTerm(
                context,
                "경비",
                "정찰",
                "증인",
                "목격",
                "방어",
                "전투",
                "후퇴",
                "동료",
                "guard",
                "scout",
                "witness",
                "defense",
                "combat",
                "fallback",
                "companion");
        }

        private static IList<DynamicQuestCinematicAction> BuildSupplementalMarkerActions(
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string trigger,
            string nodeKind,
            string subject,
            string sceneContext)
        {
            List<DynamicQuestCinematicAction> actions = new();
            if (ContainsCinematicTerm(sceneContext, "기록", "책", "문서", "journal", "record", "tome", "book", "written"))
                actions.Add(BuildMarkerAction(quest, node, trigger, nodeKind, BuildCategoryMarkerName("Written record", subject), $"record journal tome written {sceneContext}"));
            if (ContainsCinematicTerm(sceneContext, "성물", "룬", "토템", "의식", "relic", "rune", "totem", "ritual", "pendant"))
                actions.Add(BuildMarkerAction(quest, node, trigger, nodeKind, BuildCategoryMarkerName("Relic sign", subject), $"relic rune totem ritual {sceneContext}"));
            if (ContainsCinematicTerm(sceneContext, "불", "불씨", "횃불", "화염", "flame", "fire", "torch", "campfire", "omen"))
                actions.Add(BuildMarkerAction(quest, node, trigger, nodeKind, BuildCategoryMarkerName("Burning omen", subject), $"flame fire torch campfire omen {sceneContext}"));
            if (ContainsCinematicTerm(sceneContext, "무기", "화살", "전투", "검", "weapon", "arrow", "battle", "combat", "sword"))
                actions.Add(BuildMarkerAction(quest, node, trigger, nodeKind, BuildCategoryMarkerName("Battle sign", subject), $"weapon arrow battle combat {sceneContext}"));
            if (ContainsCinematicTerm(sceneContext, "문", "관문", "성채", "portal", "gate", "keep", "door", "structure"))
                actions.Add(BuildMarkerAction(quest, node, trigger, nodeKind, BuildCategoryMarkerName("Structure sign", subject), $"structure gate portal keep door {sceneContext}"));

            return actions;
        }

        private static string BuildContextualMarkerName(string prefix, string subject, string sceneContext)
        {
            string context = (sceneContext ?? string.Empty).ToLowerInvariant();
            string label = prefix;
            if (ContainsCinematicTerm(context, "기록", "책", "journal", "record", "tome"))
                label = "Written record";
            else if (ContainsCinematicTerm(context, "성물", "룬", "토템", "relic", "rune", "totem", "pendant"))
                label = "Relic sign";
            else if (ContainsCinematicTerm(context, "불", "불씨", "횃불", "flame", "fire", "torch", "campfire"))
                label = "Burning omen";
            else if (ContainsCinematicTerm(context, "무기", "화살", "전투", "weapon", "arrow", "battle", "combat"))
                label = "Battle sign";
            else if (ContainsCinematicTerm(context, "문", "관문", "portal", "gate", "keep"))
                label = "Structure sign";
            else if (ContainsCinematicTerm(context, "흔적", "증거", "표식", "clue", "trace", "evidence", "marker"))
                label = "Quest trace";

            return $"{label}: {SafeCinematicName(subject)}";
        }

        private static string BuildCategoryMarkerName(string label, string subject)
        {
            return $"{label}: {SafeCinematicName(subject)}";
        }

        private static bool ContainsCinematicTerm(string context, params string[] terms)
        {
            if (string.IsNullOrWhiteSpace(context))
                return false;

            return (terms ?? Array.Empty<string>())
                .Any(term => !string.IsNullOrWhiteSpace(term) && context.Contains(term, StringComparison.OrdinalIgnoreCase));
        }

        internal static ushort ResolveCinematicMarkerModelForTest(
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string presentationTrigger = "OnNodeEnter",
            string extraContext = "")
        {
            return ResolveCinematicMarkerModel(quest, node, presentationTrigger, extraContext);
        }

        internal static ushort ResolveCinematicNpcModelForTest(
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string presentationTrigger = "OnNodeEnter",
            string extraContext = "")
        {
            return DynamicQuestCinematicCatalog.ResolveNpcModel(quest, node, presentationTrigger, extraContext);
        }

        private static ushort ResolveCinematicMarkerModel(
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string presentationTrigger,
            string extraContext)
        {
            return DynamicQuestCinematicCatalog.ResolvePropModel(quest, node, presentationTrigger, extraContext);
        }

        private static DynamicQuestCinematicAction BuildMarkerAction(
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string trigger,
            string nodeKind,
            string markerName,
            string extraContext)
        {
            markerName = SafeCinematicName(markerName);
            ushort markerModel = ResolveCinematicMarkerModel(quest, node, trigger, $"{markerName} {extraContext}");
            return new DynamicQuestCinematicAction
            {
                Kind = "marker",
                Detail = $"marker:{trigger}:{nodeKind}:{markerName}:model:{markerModel}",
                MarkerName = markerName,
                MarkerModel = markerModel,
                Objective = node?.Objective,
                SpawnMarker = true
            };
        }

        private static DynamicQuestCinematicAction BuildNpcFocusAction(string trigger, string nodeKind, eEmote emote)
        {
            return new DynamicQuestCinematicAction
            {
                Kind = "npc_action",
                Detail = $"npc_action:{trigger}:{nodeKind}:focus:{emote}",
                FocusNpc = true,
                NpcAction = "focus",
                Emote = emote
            };
        }

        private static DynamicQuestCinematicAction BuildNpcAction(
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string trigger,
            string nodeKind,
            string npcAction,
            eEmote emote,
            string extraContext)
        {
            string modelContext = $"{npcAction} {trigger} {nodeKind}";
            ushort npcModel = DynamicQuestCinematicCatalog.ResolveNpcModel(quest, node, trigger, modelContext);
            int actorCount = ResolveCinematicActorCount(quest, node, npcAction, extraContext, allowTaggedScale: false);
            (string motionPattern, int motionDistance, int motionLateral, int motionSpeed) = ResolveCinematicMotionProfile(npcAction, string.Empty, string.Empty);
            int motionStaggerMs = ResolveCinematicMotionStaggerMs(motionPattern, npcAction, string.Empty, string.Empty);
            string focalPoint = ResolveCinematicFocalPoint(node, npcAction, string.Empty, string.Empty);
            string actorRole = ResolveCinematicActorRole(npcAction, string.Empty, string.Empty);
            string interactionStyle = ResolveCinematicInteractionStyle(npcAction, actorRole, string.Empty, string.Empty, actorCount);
            string tacticalRole = ResolveCinematicTacticalRole(npcAction, actorRole, interactionStyle, string.Empty, string.Empty);
            int choreographyPhases = ResolveCinematicChoreographyPhases(npcAction, actorRole, interactionStyle, actorCount);
            string npcRoleCategory = DynamicQuestCinematicCatalog.ResolveNpcCategoryForModel(npcModel);
            return new DynamicQuestCinematicAction
            {
                Kind = "npc_action",
                Detail = $"npc_action:{trigger}:{nodeKind}:{npcAction}:{emote}:model:{npcModel}:catalogRole:{SafeSceneBeatToken(npcRoleCategory)}:actors:{actorCount}:motion:{motionPattern}:stagger:{motionStaggerMs}:focal:{focalPoint}:actorRole:{actorRole}:choreo:{choreographyPhases}:interact:{interactionStyle}:tactic:{tacticalRole}",
                FocusNpc = true,
                SpawnNpcActor = npcModel != 0 && actorCount > 0,
                Objective = node?.Objective,
                NpcModel = npcModel,
                NpcRoleCategory = npcRoleCategory,
                ActorName = BuildCinematicActorName(node, npcAction),
                ActorCount = actorCount,
                NpcAction = npcAction,
                MotionPattern = motionPattern,
                MotionDistance = motionDistance,
                MotionLateral = motionLateral,
                MotionSpeed = motionSpeed,
                MotionStaggerMs = motionStaggerMs,
                FocalPoint = focalPoint,
                ActorRole = actorRole,
                InteractionStyle = interactionStyle,
                TacticalRole = tacticalRole,
                ChoreographyPhases = choreographyPhases,
                Emote = emote
            };
        }

        private static DynamicQuestCinematicAction BuildSceneBeatAction(
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string trigger,
            string nodeKind,
            int beatIndex,
            int delayMs,
            string sceneRole,
            string npcAction,
            string formation,
            int minimumActors,
            string extraContext)
        {
            ushort npcModel = DynamicQuestCinematicCatalog.ResolveNpcModel(quest, node, trigger, $"{npcAction} {sceneRole} {formation}");
            int actorCount = Math.Max(minimumActors, ResolveCinematicActorCount(quest, node, npcAction, extraContext));
            actorCount = Math.Clamp(actorCount, 1, GetConfiguredCinematicMaxActorsPerAction());
            eEmote emote = SelectCinematicEmote(quest, node, trigger, npcAction, eEmote.PlayerPrepare);
            string role = NormalizeSceneToken(sceneRole, "scene");
            string safeFormation = NormalizeSceneToken(formation, "ring");
            int safeDelayMs = Math.Clamp(delayMs, 0, 6000);
            (string motionPattern, int motionDistance, int motionLateral, int motionSpeed) = ResolveCinematicMotionProfile(npcAction, safeFormation, role);
            int motionStaggerMs = ResolveCinematicMotionStaggerMs(motionPattern, npcAction, safeFormation, role);
            string focalPoint = ResolveCinematicFocalPoint(node, npcAction, safeFormation, role);
            string actorRole = ResolveCinematicActorRole(npcAction, role, safeFormation);
            string interactionStyle = ResolveCinematicInteractionStyle(npcAction, actorRole, role, safeFormation, actorCount);
            string tacticalRole = ResolveCinematicTacticalRole(npcAction, actorRole, interactionStyle, role, safeFormation);
            int choreographyPhases = ResolveCinematicChoreographyPhases(npcAction, actorRole, interactionStyle, actorCount);
            string npcRoleCategory = DynamicQuestCinematicCatalog.ResolveNpcCategoryForModel(npcModel);

            return new DynamicQuestCinematicAction
            {
                Kind = "scene_beat",
                Detail = $"scene_beat:{trigger}:{nodeKind}:beat:{beatIndex}:delay:{safeDelayMs}:role:{role}:action:{npcAction}:formation:{safeFormation}:motion:{motionPattern}:stagger:{motionStaggerMs}:focal:{focalPoint}:actorRole:{actorRole}:choreo:{choreographyPhases}:interact:{interactionStyle}:tactic:{tacticalRole}:model:{npcModel}:catalogRole:{SafeSceneBeatToken(npcRoleCategory)}:actors:{actorCount}",
                FocusNpc = false,
                SpawnNpcActor = npcModel != 0 && actorCount > 0,
                Objective = node?.Objective,
                NpcModel = npcModel,
                NpcRoleCategory = npcRoleCategory,
                ActorName = BuildCinematicSceneActorName(node, role),
                ActorCount = actorCount,
                SceneBeatIndex = Math.Max(1, beatIndex),
                SceneDelayMs = safeDelayMs,
                SceneRole = role,
                Formation = safeFormation,
                NpcAction = npcAction,
                MotionPattern = motionPattern,
                MotionDistance = motionDistance,
                MotionLateral = motionLateral,
                MotionSpeed = motionSpeed,
                MotionStaggerMs = motionStaggerMs,
                FocalPoint = focalPoint,
                ActorRole = actorRole,
                InteractionStyle = interactionStyle,
                TacticalRole = tacticalRole,
                ChoreographyPhases = choreographyPhases,
                Emote = emote
            };
        }

        private static int ResolveCinematicChoreographyPhases(string npcAction, string actorRole, string interactionStyle, int actorCount)
        {
            string role = (actorRole ?? string.Empty).Trim().ToLowerInvariant();
            if (actorCount <= 0)
                return 1;

            if (!string.IsNullOrWhiteSpace(interactionStyle) &&
                !string.Equals(interactionStyle, "none", StringComparison.OrdinalIgnoreCase))
            {
                return 3;
            }

            if (role is "strike" or "defend" or "disrupt" or "retreat" or "spot" or "brace" or "advance")
                return 2;

            string action = (npcAction ?? string.Empty).Trim().ToLowerInvariant();
            return action is "ambush_reveal" or "defender_intercept" or "scout_retreat" or "ritual_interrupt" or "threat_standoff" or "guard_advance"
                ? 2
                : 1;
        }

        private static string ResolveCinematicInteractionStyle(
            string npcAction,
            string actorRole,
            string sceneRole,
            string formation,
            int actorCount)
        {
            if (actorCount <= 1)
                return "none";

            string action = (npcAction ?? string.Empty).Trim().ToLowerInvariant();
            string role = (actorRole ?? string.Empty).Trim().ToLowerInvariant();
            string context = $"{action} {role} {(sceneRole ?? string.Empty).Trim().ToLowerInvariant()} {(formation ?? string.Empty).Trim().ToLowerInvariant()}";

            if (ContainsCinematicTerm(context, "ambush", "strike", "battle", "combat"))
                return "clash";
            if (ContainsCinematicTerm(context, "ritual", "disrupt", "interrupt", "break"))
                return "interrupt";
            if (ContainsCinematicTerm(context, "retreat", "escape", "lookout", "scout"))
                return "pursuit";
            if (ContainsCinematicTerm(context, "standoff", "brace", "confront", "challenge"))
                return "standoff";
            if (ContainsCinematicTerm(context, "intercept", "defend", "guard", "shield", "line", "hold"))
                return "block";
            if (ContainsCinematicTerm(context, "witness", "spot", "clue", "point", "guide"))
                return "signal";

            return "none";
        }

        private static string ResolveCinematicTacticalRole(
            string npcAction,
            string actorRole,
            string interactionStyle,
            string sceneRole,
            string formation)
        {
            string action = (npcAction ?? string.Empty).Trim().ToLowerInvariant();
            string role = (actorRole ?? string.Empty).Trim().ToLowerInvariant();
            string interaction = (interactionStyle ?? string.Empty).Trim().ToLowerInvariant();
            string context = $"{action} {role} {interaction} {(sceneRole ?? string.Empty).Trim().ToLowerInvariant()} {(formation ?? string.Empty).Trim().ToLowerInvariant()}";

            if (ContainsCinematicTerm(context, "ritual", "interrupt", "disrupt", "suppress", "break"))
                return "suppress";
            if (ContainsCinematicTerm(context, "ambush", "strike", "clash", "pincer"))
                return "flank";
            if (ContainsCinematicTerm(context, "standoff", "brace", "confront", "pressure"))
                return "pressure";
            if (ContainsCinematicTerm(context, "retreat", "escape", "pursuit", "lookout", "scout"))
                return "withdraw";
            if (ContainsCinematicTerm(context, "intercept", "defend", "guard", "shield", "line", "hold", "block"))
                return "screen";
            if (ContainsCinematicTerm(context, "witness", "spot", "signal", "clue", "point", "guide"))
                return "spot";
            if (ContainsCinematicTerm(context, "advance", "push", "escort"))
                return "push";

            return "support";
        }

        private static string ResolveCinematicActorRole(string npcAction, string sceneRole, string formation)
        {
            string action = (npcAction ?? string.Empty).Trim().ToLowerInvariant();
            string role = (sceneRole ?? string.Empty).Trim().ToLowerInvariant();
            string context = $"{action} {role} {(formation ?? string.Empty).Trim().ToLowerInvariant()}";

            if (ContainsCinematicTerm(context, "ambush", "attack", "strike", "combat", "battle"))
                return "strike";
            if (ContainsCinematicTerm(context, "intercept", "defender", "defense", "guard", "shield", "hold", "fallback", "debrief"))
                return "defend";
            if (ContainsCinematicTerm(context, "ritual", "interrupt", "break", "signal_reveal"))
                return "disrupt";
            if (ContainsCinematicTerm(context, "retreat", "escape", "lookout", "scout"))
                return "retreat";
            if (ContainsCinematicTerm(context, "witness", "point", "clue", "guide"))
                return "spot";
            if (ContainsCinematicTerm(context, "standoff", "confront", "challenge"))
                return "brace";
            if (ContainsCinematicTerm(context, "advance", "pursue", "fallout"))
                return "advance";

            return "support";
        }

        private static string ResolveCinematicFocalPoint(
            DynamicQuestNode node,
            string npcAction,
            string formation,
            string sceneRole)
        {
            if (!HasObjectiveFocalPoint(node?.Objective))
                return "player";

            string action = (npcAction ?? string.Empty).Trim().ToLowerInvariant();
            string safeFormation = (formation ?? string.Empty).Trim().ToLowerInvariant();
            string role = (sceneRole ?? string.Empty).Trim().ToLowerInvariant();
            if (action is "ambush_reveal" or "defender_intercept" or "ritual_interrupt" or "threat_standoff" or "witness_point")
                return "objective";
            if (safeFormation is "ambush" or "line" || role.Contains("ritual", StringComparison.Ordinal) || role.Contains("clue", StringComparison.Ordinal))
                return "objective";

            return "player";
        }

        private static bool HasObjectiveFocalPoint(DynamicQuestObjective objective)
        {
            return objective != null && (objective.X != 0 || objective.Y != 0);
        }

        private static (string Pattern, int Distance, int Lateral, int Speed) ResolveCinematicMotionProfile(
            string npcAction,
            string formation,
            string sceneRole)
        {
            string action = (npcAction ?? string.Empty).Trim().ToLowerInvariant();
            string safeFormation = (formation ?? string.Empty).Trim().ToLowerInvariant();
            string role = (sceneRole ?? string.Empty).Trim().ToLowerInvariant();

            (string Pattern, int Distance, int Lateral, int Speed) profile = action switch
            {
                "ambush_reveal" => ("pincer", 150, 110, 215),
                "defender_intercept" => ("intercept", 125, 70, 205),
                "scout_retreat" => ("retreat", -170, 95, 220),
                "ritual_interrupt" => ("ritual-break", 95, 85, 190),
                "threat_standoff" => ("standoff", 70, 120, 170),
                "guard_advance" => ("advance", 125, 45, 190),
                "fallback_guard" => ("fall-back", -125, 55, 175),
                "combat_stance" => ("brace", 55, 70, 160),
                "hold_ground" => ("hold", 35, 90, 150),
                "witness_point" => ("point", 45, 35, 145),
                "challenge" => ("challenge", 150, 35, 185),
                _ => ("focus", 0, 0, 150)
            };

            if (safeFormation is "ambush")
                profile = (profile.Pattern == "focus" ? "pincer" : profile.Pattern, Math.Max(profile.Distance, 130), Math.Max(profile.Lateral, 120), Math.Max(profile.Speed, 205));
            else if (safeFormation is "line")
                profile = (profile.Pattern == "focus" ? "line-shift" : profile.Pattern, profile.Distance, Math.Max(profile.Lateral, 80), profile.Speed);
            else if (safeFormation is "escape" or "patrol" || role.Contains("escape", StringComparison.Ordinal))
                profile = ("retreat", Math.Min(profile.Distance, -150), Math.Max(profile.Lateral, 95), Math.Max(profile.Speed, 210));
            else if (safeFormation is "escort")
                profile = (profile.Pattern == "focus" ? "escort" : profile.Pattern, profile.Distance, Math.Max(profile.Lateral, 40), profile.Speed);

            return profile;
        }

        private static int ResolveCinematicMotionStaggerMs(
            string motionPattern,
            string npcAction,
            string formation,
            string sceneRole)
        {
            string pattern = (motionPattern ?? string.Empty).Trim().ToLowerInvariant();
            string action = (npcAction ?? string.Empty).Trim().ToLowerInvariant();
            string safeFormation = (formation ?? string.Empty).Trim().ToLowerInvariant();
            string role = (sceneRole ?? string.Empty).Trim().ToLowerInvariant();

            int stagger = pattern switch
            {
                "pincer" => 90,
                "intercept" => 80,
                "retreat" => 110,
                "ritual-break" => 85,
                "standoff" => 55,
                "advance" => 70,
                "fall-back" => 80,
                "brace" => 50,
                "hold" => 45,
                "point" => 35,
                "challenge" => 45,
                _ => 0
            };

            if (safeFormation is "line")
                stagger = Math.Max(stagger, 75);
            else if (safeFormation is "ambush")
                stagger = Math.Max(stagger, 90);
            else if (safeFormation is "escape" or "patrol" || role.Contains("escape", StringComparison.Ordinal))
                stagger = Math.Max(stagger, 100);

            if (action is "threat_standoff" or "defender_intercept")
                stagger = Math.Max(stagger, 80);

            return Math.Clamp(stagger, 0, 160);
        }

        private static string NormalizeSceneToken(string value, string fallback)
        {
            value = (value ?? string.Empty).Trim().ToLowerInvariant();
            if (value.Length == 0)
                return fallback;

            char[] buffer = value
                .Select(ch => char.IsLetterOrDigit(ch) ? ch : '_')
                .ToArray();
            string normalized = new string(buffer).Trim('_');
            return string.IsNullOrWhiteSpace(normalized) ? fallback : normalized;
        }

        private static int ResolveCinematicActorCount(
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string npcAction,
            string sceneContext,
            bool allowTaggedScale = true)
        {
            int configuredMax = GetConfiguredCinematicMaxActorsPerAction();

            string normalizedAction = (npcAction ?? string.Empty).Trim().ToLowerInvariant();
            int count = normalizedAction switch
            {
                "combat_stance" => 3,
                "ambush_reveal" => 5,
                "defender_intercept" => 4,
                "threat_standoff" => 4,
                "hold_ground" => 3,
                "fallback_guard" => 2,
                "ritual_interrupt" => 3,
                "guard_advance" => 2,
                "scout_retreat" => 2,
                _ => 1
            };

            string context = (sceneContext ?? string.Empty).ToLowerInvariant();
            if (ContainsCinematicTerm(context, "부대", "전열", "battle line", "squad", "warband", "many actors"))
                count = Math.Max(count, 8);
            if (ContainsCinematicTerm(context, "군중", "대규모", "army", "crowd", "mass"))
                count = Math.Max(count, 12);

            if (allowTaggedScale)
            {
                int requested = ResolveTaggedCinematicActorCount(quest, normalizedAction);
                if (requested > 0)
                    count = Math.Max(count, requested);
            }

            return Math.Clamp(count, 1, configuredMax);
        }

        private static int GetConfiguredCinematicMaxActorsPerAction()
        {
            int configured = Properties.KDAOC_DYNAMIC_QUEST_CINEMATIC_MAX_ACTORS_PER_ACTION;
            if (configured <= 0 || configured == 8)
                configured = MaxCinematicActorsPerAction;
            return Math.Clamp(configured, 1, MaxCinematicActorsPerAction);
        }

        private static int ResolveTaggedCinematicActorCount(DynamicQuestDefinition quest, string normalizedAction)
        {
            int best = 0;
            foreach (string tag in quest?.Tags ?? Array.Empty<string>())
            {
                string value = (tag ?? string.Empty).Trim();
                if (value.Length == 0)
                    continue;

                if (TryParseCinematicActorTag(value, "cinematic-actors:", out int genericCount))
                    best = Math.Max(best, genericCount);

                if (!string.IsNullOrWhiteSpace(normalizedAction) &&
                    TryParseCinematicActorTag(value, $"cinematic-actors:{normalizedAction}:", out int actionCount))
                {
                    best = Math.Max(best, actionCount);
                }

                if (string.Equals(value, "mass-cinematic", StringComparison.OrdinalIgnoreCase))
                    best = Math.Max(best, 12);
            }

            return Math.Clamp(best, 0, MaxCinematicActorsPerAction);
        }

        private static bool TryParseCinematicActorTag(string tag, string prefix, out int count)
        {
            count = 0;
            if (string.IsNullOrWhiteSpace(tag) ||
                string.IsNullOrWhiteSpace(prefix) ||
                !tag.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            return int.TryParse(tag.Substring(prefix.Length).Trim(), out count);
        }

        private static string BuildCinematicActorName(DynamicQuestNode node, string npcAction)
        {
            string role = (npcAction ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "challenge" => "Quest Guard",
                "guard_advance" => "Quest Scout",
                "fallback_guard" => "Quest Defender",
                "combat_stance" => "Quest Fighter",
                "hold_ground" => "Quest Defender",
                "witness_point" => "Quest Witness",
                "ambush_reveal" => "Quest Ambusher",
                "defender_intercept" => "Quest Interceptor",
                "scout_retreat" => "Quest Scout",
                "ritual_interrupt" => "Quest Ritual Guard",
                "threat_standoff" => "Quest Standoff Guard",
                _ => "Quest Actor"
            };

            string title = SafeCinematicName(node?.Title);
            return string.IsNullOrWhiteSpace(title) ? role : $"{role}: {title}";
        }

        private static string BuildCinematicSceneActorName(DynamicQuestNode node, string sceneRole)
        {
            string role = (sceneRole ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "contract" => "Quest Contact",
                "witness" => "Quest Witness",
                "lookout" => "Quest Lookout",
                "ambush" => "Quest Ambusher",
                "intercept" => "Quest Interceptor",
                "witness_escape" => "Quest Fleeing Witness",
                "confrontation" => "Quest Confrontation",
                "fallout" => "Quest Fallout Guard",
                "debrief" => "Quest Debrief Guard",
                _ => "Quest Scene Actor"
            };

            string title = SafeCinematicName(node?.Title);
            return string.IsNullOrWhiteSpace(title) ? role : $"{role}: {title}";
        }

        private static string SafeCinematicName(string value)
        {
            value = (value ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(value))
                return "quest clue";

            const int maxLength = 48;
            return value.Length <= maxLength ? value : value.Substring(0, maxLength).TrimEnd();
        }

        private void PlayCinematicActionLocked(
            string playerKey,
            string questId,
            GamePlayer player,
            GameNPC npc,
            DynamicQuestCinematicAction action)
        {
            if (action == null)
                return;

            if (action.CleanupMarkers)
            {
                CleanupCinematicMarkersLocked(playerKey, questId, player?.Name ?? string.Empty, string.Empty, action.Kind);
                return;
            }

            if (action.FocusNpc && player != null && npc != null)
            {
                PlayNpcCinematicAction(player, npc, action);
            }

            if (action.SpawnNpcActor)
                SpawnCinematicActorLocked(playerKey, questId, player, action);

            if (action.SpawnMarker)
                SpawnCinematicMarkerLocked(playerKey, questId, player, action);
        }

        private static void PlayNpcCinematicAction(
            GamePlayer player,
            GameNPC npc,
            DynamicQuestCinematicAction action,
            int actorIndex = 0,
            int actorCount = 1)
        {
            if (player == null || npc == null || action == null)
                return;

            npc.TurnTo(player, 750);
            eEmote? actorEmote = ResolveCinematicActorEmote(action);
            if (actorEmote.HasValue)
                npc.Emote(actorEmote.Value);

            if (npc.CurrentRegionID != player.CurrentRegionID || npc.InCombat)
                return;

            (string _, int profileDistance, int profileLateral, int profileSpeed) = ResolveCinematicMotionProfile(action.NpcAction, action.Formation, action.SceneRole);
            int distance = action.MotionDistance != 0 ? action.MotionDistance : profileDistance;
            int lateral = action.MotionLateral != 0 ? action.MotionLateral : profileLateral;
            int speed = action.MotionSpeed != 0 ? action.MotionSpeed : profileSpeed;

            if (distance == 0 && lateral == 0)
                return;

            Point3D focusPoint = ResolveCinematicActionFocusPoint(player, action);
            if (!TryBuildNpcCinematicStep(npc, player, focusPoint, distance, lateral, actorIndex, actorCount, out Point3D target))
                return;

            try
            {
                npc.WalkTo(target, (short)Math.Clamp(speed, 120, 240));
                ScheduleCinematicActorFollowUpAction(npc, player, action, focusPoint, actorIndex, actorCount);
                new ECSGameTimer(npc, timer =>
                {
                    try
                    {
                        if (npc.ObjectState == GameObject.eObjectState.Active && !npc.InCombat)
                            npc.ReturnToSpawnPoint(180);
                    }
                    catch (Exception ex)
                    {
                        Log.Warn($"Dynamic quest cinematic NPC return failed for {npc.Name}: {ex.Message}");
                    }

                    timer.Stop();
                    return 0;
                }, 2400);
            }
            catch (Exception ex)
            {
                Log.Warn($"Dynamic quest cinematic NPC action failed for {npc.Name}: {ex.Message}");
            }
        }

        private static void ScheduleCinematicActorFollowUpAction(
            GameNPC npc,
            GamePlayer player,
            DynamicQuestCinematicAction action,
            Point3D focusPoint,
            int actorIndex,
            int actorCount)
        {
            if (npc == null || player == null || action == null)
                return;

            int followUpPhaseCount = ResolveCinematicFollowUpPhaseCount(action.ChoreographyPhases);
            if (followUpPhaseCount <= 0)
                return;

            for (int phaseIndex = 2; phaseIndex <= followUpPhaseCount + 1; phaseIndex++)
            {
                int delay = BuildCinematicFollowUpActionDelayMs(phaseIndex, actorIndex);
                ScheduleCinematicActorFollowUpActionPhase(npc, player, action, focusPoint, actorIndex, actorCount, phaseIndex, delay);
            }
        }

        private static void ScheduleCinematicActorFollowUpActionPhase(
            GameNPC npc,
            GamePlayer player,
            DynamicQuestCinematicAction action,
            Point3D focusPoint,
            int actorIndex,
            int actorCount,
            int phaseIndex,
            int delay)
        {
            new ECSGameTimer(npc, timer =>
            {
                try
                {
                    if (npc.ObjectState != GameObject.eObjectState.Active ||
                        npc.InCombat ||
                        npc.CurrentRegionID != player.CurrentRegionID)
                    {
                        timer.Stop();
                        return 0;
                    }

                    Point3D safeFocusPoint = focusPoint ?? new Point3D(player.X, player.Y, player.Z);
                    Point3D interactionPoint = ResolveCinematicInteractionPoint(npc, player, action, safeFocusPoint, actorIndex, actorCount, phaseIndex);
                    npc.TurnTo(interactionPoint.X, interactionPoint.Y, 600);

                    eEmote? emote = ResolveCinematicActorFollowUpEmote(action, phaseIndex);
                    if (emote.HasValue)
                        npc.Emote(emote.Value);

                    (int distance, int lateral, int speed) = ResolveCinematicFollowUpMotion(action, phaseIndex);
                    if ((distance != 0 || lateral != 0) &&
                        TryBuildNpcCinematicStep(npc, player, interactionPoint, distance, lateral, actorIndex, actorCount, out Point3D followUpTarget))
                    {
                        npc.WalkTo(followUpTarget, (short)Math.Clamp(speed, 120, 240));
                    }
                }
                catch (Exception ex)
                {
                    Log.Warn($"Dynamic quest cinematic actor follow-up failed for {npc.Name}: {ex.Message}");
                }

                timer.Stop();
                return 0;
            }, delay);
        }

        private static int ResolveCinematicFollowUpPhaseCount(int choreographyPhases)
        {
            return Math.Clamp(choreographyPhases, 1, 4) - 1;
        }

        internal static IList<int> BuildCinematicFollowUpActionDelaysForTest(int choreographyPhases, int actorIndex)
        {
            int phaseCount = ResolveCinematicFollowUpPhaseCount(choreographyPhases);
            List<int> delays = new(phaseCount);
            for (int phaseIndex = 2; phaseIndex <= phaseCount + 1; phaseIndex++)
                delays.Add(BuildCinematicFollowUpActionDelayMs(phaseIndex, actorIndex));

            return delays;
        }

        private static int BuildCinematicFollowUpActionDelayMs(int phaseIndex, int actorIndex)
        {
            phaseIndex = Math.Clamp(phaseIndex, 2, 4);
            return Math.Clamp(850 + Math.Max(0, actorIndex) * 18 + (phaseIndex - 2) * 700, 650, 3200);
        }

        private static Point3D ResolveCinematicInteractionPoint(
            GameNPC npc,
            GamePlayer player,
            DynamicQuestCinematicAction action,
            Point3D focusPoint,
            int actorIndex,
            int actorCount,
            int phaseIndex = 2)
        {
            if (npc == null || player == null || action == null)
                return focusPoint ?? new Point3D(player.X, player.Y, player.Z);

            string interactionStyle = string.IsNullOrWhiteSpace(action.InteractionStyle)
                ? ResolveCinematicInteractionStyle(action.NpcAction, action.ActorRole, action.SceneRole, action.Formation, actorCount)
                : action.InteractionStyle.Trim().ToLowerInvariant();

            if (string.Equals(interactionStyle, "none", StringComparison.OrdinalIgnoreCase))
                return focusPoint ?? new Point3D(player.X, player.Y, player.Z);

            actorCount = Math.Max(1, actorCount);
            Point3D safeFocusPoint = focusPoint ?? new Point3D(player.X, player.Y, player.Z);
            (double forwardX, double forwardY, double sideX, double sideY) = BuildCinematicFacingVectors(player);
            double normalizedIndex = actorCount <= 1
                ? 0.0
                : (actorIndex - ((actorCount - 1) / 2.0)) / Math.Max(1.0, (actorCount - 1) / 2.0);
            int lane = (actorIndex + Math.Max(0, phaseIndex - 2)) % 2 == 0 ? -1 : 1;
            int forwardOffset;
            int sideOffset;

            switch (interactionStyle)
            {
                case "clash":
                    forwardOffset = lane * 75;
                    sideOffset = (int)Math.Round(normalizedIndex * 140);
                    break;
                case "block":
                    forwardOffset = -40;
                    sideOffset = (int)Math.Round(normalizedIndex * 170);
                    break;
                case "interrupt":
                    forwardOffset = 35;
                    sideOffset = (int)Math.Round(normalizedIndex * 115);
                    break;
                case "pursuit":
                    forwardOffset = -lane * 120;
                    sideOffset = (int)Math.Round(normalizedIndex * 120);
                    break;
                case "standoff":
                    forwardOffset = lane * 95;
                    sideOffset = (int)Math.Round(normalizedIndex * 185);
                    break;
                case "signal":
                    forwardOffset = 20;
                    sideOffset = (int)Math.Round(normalizedIndex * 90);
                    break;
                default:
                    return safeFocusPoint;
            }

            if (phaseIndex >= 3)
            {
                int phaseDrift = Math.Min(phaseIndex - 2, 2);
                forwardOffset += phaseDrift * 35 * Math.Sign(forwardOffset == 0 ? lane : forwardOffset);
                sideOffset = -sideOffset + lane * 30 * phaseDrift;
            }

            int x = safeFocusPoint.X + (int)Math.Round(forwardX * forwardOffset + sideX * sideOffset);
            int y = safeFocusPoint.Y + (int)Math.Round(forwardY * forwardOffset + sideY * sideOffset);
            return new Point3D(x, y, safeFocusPoint.Z);
        }

        private static eEmote? ResolveCinematicActorFollowUpEmote(DynamicQuestCinematicAction action, int phaseIndex = 2)
        {
            if (action == null)
                return null;

            string actorRole = string.IsNullOrWhiteSpace(action.ActorRole)
                ? ResolveCinematicActorRole(action.NpcAction, action.SceneRole, action.Formation)
                : action.ActorRole.Trim().ToLowerInvariant();

            if (phaseIndex >= 3 && action.Emote.HasValue)
                return action.Emote;

            return actorRole switch
            {
                "strike" => eEmote.LetsGo,
                "defend" => eEmote.BangOnShield,
                "disrupt" => eEmote.Point,
                "retreat" => eEmote.Point,
                "spot" => eEmote.Point,
                "brace" => eEmote.BangOnShield,
                "advance" => eEmote.LetsGo,
                _ => action.Emote
            };
        }

        private static (int Distance, int Lateral, int Speed) ResolveCinematicFollowUpMotion(DynamicQuestCinematicAction action, int phaseIndex = 2)
        {
            string actorRole = string.IsNullOrWhiteSpace(action?.ActorRole)
                ? ResolveCinematicActorRole(action?.NpcAction, action?.SceneRole, action?.Formation)
                : action.ActorRole.Trim().ToLowerInvariant();
            string tacticalRole = string.IsNullOrWhiteSpace(action?.TacticalRole)
                ? ResolveCinematicTacticalRole(action?.NpcAction, actorRole, action?.InteractionStyle, action?.SceneRole, action?.Formation)
                : action.TacticalRole.Trim().ToLowerInvariant();

            (int Distance, int Lateral, int Speed) baseMotion;
            switch (tacticalRole)
            {
                case "flank":
                    baseMotion = (135, 70, 235);
                    break;
                case "screen":
                    baseMotion = (-20, 115, 165);
                    break;
                case "suppress":
                    baseMotion = (95, -70, 220);
                    break;
                case "withdraw":
                    baseMotion = (-175, 75, 230);
                    break;
                case "pressure":
                    baseMotion = (35, 105, 175);
                    break;
                case "push":
                    baseMotion = (120, 35, 220);
                    break;
                case "spot":
                    baseMotion = (0, 55, 150);
                    break;
                default:
                    baseMotion = actorRole switch
                    {
                        "strike" => (120, 40, 235),
                        "defend" => (0, 80, 160),
                        "disrupt" => (90, -50, 220),
                        "retreat" => (-160, 70, 230),
                        "spot" => (0, 45, 150),
                        "brace" => (-40, 70, 160),
                        "advance" => (110, 30, 220),
                        _ => (0, 0, 180)
                    };
                    break;
            }

            if (phaseIndex <= 2)
                return baseMotion;

            int phaseDrift = Math.Min(phaseIndex - 2, 2);
            int direction = phaseIndex % 2 == 0 ? 1 : -1;
            int distance = baseMotion.Distance - direction * phaseDrift * 30;
            int lateral = -baseMotion.Lateral + direction * phaseDrift * 35;
            int speed = Math.Clamp(baseMotion.Speed + phaseDrift * 10, 120, 240);
            return (distance, lateral, speed);
        }

        private static int ResolveCinematicMotionCommandCount(DynamicQuestCinematicAction action)
        {
            if (action == null)
                return 0;

            int commandCount = 0;
            (string _, int profileDistance, int profileLateral, int _) = ResolveCinematicMotionProfile(action.NpcAction, action.Formation, action.SceneRole);
            int initialDistance = action.MotionDistance != 0 ? action.MotionDistance : profileDistance;
            int initialLateral = action.MotionLateral != 0 ? action.MotionLateral : profileLateral;
            if (initialDistance != 0 || initialLateral != 0)
                commandCount++;

            int followUpPhaseCount = ResolveCinematicFollowUpPhaseCount(action.ChoreographyPhases);
            for (int phaseIndex = 2; phaseIndex <= followUpPhaseCount + 1; phaseIndex++)
            {
                (int distance, int lateral, int _) = ResolveCinematicFollowUpMotion(action, phaseIndex);
                if (distance != 0 || lateral != 0)
                    commandCount++;
            }

            return commandCount;
        }

        private static (string ExchangeKind, int Pairs, int EngagedActors) ResolveCinematicEngagementSummary(
            DynamicQuestCinematicAction action,
            int spawned)
        {
            if (action == null || spawned < 2)
                return (string.Empty, 0, 0);

            string actorRole = string.IsNullOrWhiteSpace(action.ActorRole)
                ? ResolveCinematicActorRole(action.NpcAction, action.SceneRole, action.Formation)
                : action.ActorRole.Trim();
            string interactionStyle = string.IsNullOrWhiteSpace(action.InteractionStyle)
                ? ResolveCinematicInteractionStyle(action.NpcAction, actorRole, action.SceneRole, action.Formation, spawned)
                : action.InteractionStyle.Trim();
            string tacticalRole = string.IsNullOrWhiteSpace(action.TacticalRole)
                ? ResolveCinematicTacticalRole(action.NpcAction, actorRole, interactionStyle, action.SceneRole, action.Formation)
                : action.TacticalRole.Trim();
            string exchangeKind = ResolveCinematicActorExchangeKind(interactionStyle, tacticalRole, action.NpcAction, actorRole);
            if (string.IsNullOrWhiteSpace(exchangeKind))
                return (string.Empty, 0, 0);

            int engagedActors = Math.Max(2, spawned - spawned % 2);
            return (exchangeKind, engagedActors / 2, engagedActors);
        }

        internal static int ResolveCinematicEngagementPairCountForTest(
            string npcAction,
            string formation,
            string sceneRole,
            int actorCount)
        {
            string actorRole = ResolveCinematicActorRole(npcAction, sceneRole, formation);
            string interactionStyle = ResolveCinematicInteractionStyle(npcAction, actorRole, sceneRole, formation, actorCount);
            string tacticalRole = ResolveCinematicTacticalRole(npcAction, actorRole, interactionStyle, sceneRole, formation);
            (string exchangeKind, int pairs, int _) = ResolveCinematicEngagementSummary(new DynamicQuestCinematicAction
            {
                NpcAction = npcAction ?? string.Empty,
                Formation = formation ?? string.Empty,
                SceneRole = sceneRole ?? string.Empty,
                ActorRole = actorRole,
                InteractionStyle = interactionStyle,
                TacticalRole = tacticalRole,
                ChoreographyPhases = 1
            }, actorCount);

            return string.IsNullOrWhiteSpace(exchangeKind) ? 0 : pairs;
        }

        internal static int ResolveCinematicMotionCommandCountForTest(
            string npcAction,
            string formation,
            string sceneRole,
            int choreographyPhases)
        {
            string actorRole = ResolveCinematicActorRole(npcAction, sceneRole, formation);
            string interactionStyle = ResolveCinematicInteractionStyle(npcAction, actorRole, sceneRole, formation, 1);
            string tacticalRole = ResolveCinematicTacticalRole(npcAction, actorRole, interactionStyle, sceneRole, formation);
            (string motionPattern, int motionDistance, int motionLateral, int motionSpeed) = ResolveCinematicMotionProfile(npcAction, formation, sceneRole);

            return ResolveCinematicMotionCommandCount(new DynamicQuestCinematicAction
            {
                NpcAction = npcAction ?? string.Empty,
                Formation = formation ?? string.Empty,
                SceneRole = sceneRole ?? string.Empty,
                MotionPattern = motionPattern,
                MotionDistance = motionDistance,
                MotionLateral = motionLateral,
                MotionSpeed = motionSpeed,
                ActorRole = actorRole,
                InteractionStyle = interactionStyle,
                TacticalRole = tacticalRole,
                ChoreographyPhases = choreographyPhases
            });
        }

        private static eEmote? ResolveCinematicActorEmote(DynamicQuestCinematicAction action)
        {
            if (action == null)
                return null;

            string actorRole = string.IsNullOrWhiteSpace(action.ActorRole)
                ? ResolveCinematicActorRole(action.NpcAction, action.SceneRole, action.Formation)
                : action.ActorRole.Trim().ToLowerInvariant();

            return actorRole switch
            {
                "strike" => eEmote.PlayerPrepare,
                "defend" => eEmote.BangOnShield,
                "disrupt" => eEmote.PlayerPrepare,
                "retreat" => eEmote.Point,
                "spot" => eEmote.Point,
                "brace" => eEmote.PlayerPrepare,
                "advance" => eEmote.LetsGo,
                _ => action.Emote
            };
        }

        private static bool TryBuildNpcCinematicStep(
            GameNPC npc,
            GamePlayer player,
            Point3D focusPoint,
            int distance,
            int lateral,
            int actorIndex,
            int actorCount,
            out Point3D target)
        {
            target = null;
            int focusX = focusPoint?.X ?? player.X;
            int focusY = focusPoint?.Y ?? player.Y;
            int dx = focusX - npc.X;
            int dy = focusY - npc.Y;
            double length = Math.Sqrt((double)dx * dx + (double)dy * dy);
            if (length < 1)
                return false;

            actorCount = Math.Max(1, actorCount);
            double normalizedIndex = actorCount <= 1
                ? 0.0
                : (actorIndex - ((actorCount - 1) / 2.0)) / Math.Max(1.0, (actorCount - 1) / 2.0);
            double sideX = -dy / length;
            double sideY = dx / length;
            int x = npc.X + (int)Math.Round(dx / length * distance + sideX * lateral * normalizedIndex);
            int y = npc.Y + (int)Math.Round(dy / length * distance + sideY * lateral * normalizedIndex);
            target = new Point3D(x, y, npc.Z);
            return true;
        }

        private static Point3D ResolveCinematicActionFocusPoint(GamePlayer player, DynamicQuestCinematicAction action)
        {
            if (player == null || action == null)
                return null;

            if (!string.Equals(action.FocalPoint, "objective", StringComparison.OrdinalIgnoreCase))
                return new Point3D(player.X, player.Y, player.Z);

            DynamicQuestObjective objective = action.Objective;
            if (!HasObjectiveFocalPoint(objective))
                return new Point3D(player.X, player.Y, player.Z);

            ushort regionId = objective.RegionId != 0 ? objective.RegionId : player.CurrentRegionID;
            if (regionId != player.CurrentRegionID)
                return new Point3D(player.X, player.Y, player.Z);

            int z = objective.Z != 0 ? objective.Z : player.Z;
            return new Point3D(objective.X, objective.Y, z);
        }

        private void SpawnCinematicActorLocked(
            string playerKey,
            string questId,
            GamePlayer player,
            DynamicQuestCinematicAction action)
        {
            if (player == null || player.CurrentRegion == null || action == null || action.NpcModel == 0)
                return;

            int actorCount = Math.Clamp(action.ActorCount <= 0 ? 1 : action.ActorCount, 1, GetConfiguredCinematicMaxActorsPerAction());
            string cinematicKey = BuildProgressId(playerKey, questId);
            if (!m_cinematicActors.TryGetValue(cinematicKey, out List<GameNPC> actors))
            {
                actors = new List<GameNPC>();
                m_cinematicActors[cinematicKey] = actors;
            }

            int spawned = 0;
            int failed = 0;
            int cleanupScheduled = 0;
            for (int index = 0; index < actorCount; index++)
            {
                Point3D anchorPoint = ResolveCinematicActionFocusPoint(player, action) ?? new Point3D(player.X, player.Y, player.Z);
                Point3D spawnPoint = BuildCinematicActorSpawnPoint(player, anchorPoint, index, actorCount, action.Formation, action.NpcAction);
                GameNPC actor = new()
                {
                    CurrentRegion = player.CurrentRegion,
                    Heading = player.Heading,
                    Level = (byte)Math.Clamp((int)player.Level, 1, 50),
                    Realm = player.Realm,
                    Name = SafeCinematicName(actorCount > 1 ? $"{action.ActorName} {index + 1}" : action.ActorName),
                    Model = action.NpcModel,
                    X = spawnPoint.X,
                    Y = spawnPoint.Y,
                    Z = spawnPoint.Z,
                    MaxSpeedBase = 180,
                    GuildName = "Dynamic Quest Scene",
                    Size = 50,
                    RespawnInterval = -1
                };
                actor.Flags |= GameNPC.eFlags.PEACE;

                try
                {
                    if (!actor.AddToWorld())
                    {
                        failed++;
                        continue;
                    }

                    spawned++;
                    actors.Add(actor);
                    PlaySpawnedCinematicActorAction(player, actor, action, index, actorCount);

                    new ECSGameTimer(actor, timer =>
                    {
                        try
                        {
                            if (actor.ObjectState == GameObject.eObjectState.Active)
                                actor.Delete();
                        }
                        catch (Exception ex)
                        {
                            Log.Warn($"Dynamic quest cinematic actor cleanup failed for quest {questId}: {ex.Message}");
                        }

                        timer.Stop();
                        return 0;
                    }, 12000);
                    cleanupScheduled++;
                }
                catch (Exception ex)
                {
                    failed++;
                    Log.Warn($"Dynamic quest cinematic actor spawn failed for quest {questId}: {ex.Message}");
                }
            }

            RecordTimelineEventLocked(
                playerKey,
                player.Name,
                questId,
                "cinematic_actor_spawn_summary",
                detail:
                    $"action:{SafeSceneBeatToken(action.NpcAction)}" +
                    $":role:{SafeSceneBeatToken(action.NpcRoleCategory)}" +
                    $":model:{action.NpcModel}" +
                    $":actors:{actorCount}" +
                    $":spawned:{spawned}" +
                    $":failed:{failed}" +
                    $":cleanup:{cleanupScheduled}" +
                    $":formation:{SafeSceneBeatToken(action.Formation)}");

            int motionCommandsPerActor = ResolveCinematicMotionCommandCount(action);
            int motionCommands = spawned * motionCommandsPerActor;
            if (motionCommands > 0)
            {
                RecordTimelineEventLocked(
                    playerKey,
                    player.Name,
                    questId,
                    "cinematic_actor_motion_summary",
                    detail:
                        $"action:{SafeSceneBeatToken(action.NpcAction)}" +
                        $":role:{SafeSceneBeatToken(action.NpcRoleCategory)}" +
                        $":motion:{SafeSceneBeatToken(action.MotionPattern)}" +
                        $":interact:{SafeSceneBeatToken(action.InteractionStyle)}" +
                        $":tactic:{SafeSceneBeatToken(action.TacticalRole)}" +
                        $":actors:{actorCount}" +
                        $":spawned:{spawned}" +
                        $":commandsPerActor:{motionCommandsPerActor}" +
                        $":commands:{motionCommands}" +
                        $":formation:{SafeSceneBeatToken(action.Formation)}",
                    count: motionCommands);
            }

            (string exchangeKind, int engagementPairs, int engagementActors) = ResolveCinematicEngagementSummary(action, spawned);
            if (engagementPairs > 0)
            {
                RecordTimelineEventLocked(
                    playerKey,
                    player.Name,
                    questId,
                    "cinematic_actor_engagement_summary",
                    detail:
                        $"action:{SafeSceneBeatToken(action.NpcAction)}" +
                        $":role:{SafeSceneBeatToken(action.NpcRoleCategory)}" +
                        $":exchange:{SafeSceneBeatToken(exchangeKind)}" +
                        $":interact:{SafeSceneBeatToken(action.InteractionStyle)}" +
                        $":tactic:{SafeSceneBeatToken(action.TacticalRole)}" +
                        $":actors:{actorCount}" +
                        $":spawned:{spawned}" +
                        $":engagedActors:{engagementActors}" +
                        $":pairs:{engagementPairs}" +
                        $":choreo:{Math.Max(1, action.ChoreographyPhases)}" +
                        $":formation:{SafeSceneBeatToken(action.Formation)}",
                    count: engagementPairs);
            }
        }

        private static void PlaySpawnedCinematicActorAction(
            GamePlayer player,
            GameNPC actor,
            DynamicQuestCinematicAction action,
            int actorIndex,
            int actorCount)
        {
            int actorDelayMs = BuildCinematicActorActionDelayMs(action, actorIndex, actorCount);
            if (actorDelayMs <= 0)
            {
                PlayNpcCinematicAction(player, actor, action, actorIndex, actorCount);
                return;
            }

            new ECSGameTimer(actor, timer =>
            {
                try
                {
                    if (actor.ObjectState == GameObject.eObjectState.Active)
                        PlayNpcCinematicAction(player, actor, action, actorIndex, actorCount);
                }
                catch (Exception ex)
                {
                    Log.Warn($"Dynamic quest scene beat actor action failed for {actor.Name}: {ex.Message}");
                }

                timer.Stop();
                return 0;
            }, actorDelayMs);
        }

        private static int BuildCinematicActorActionDelayMs(
            DynamicQuestCinematicAction action,
            int actorIndex,
            int actorCount)
        {
            if (action == null)
                return 0;

            int delay = Math.Clamp(action.SceneDelayMs, 0, 6000);
            int stagger = Math.Clamp(action.MotionStaggerMs, 0, 160);
            if (stagger <= 0 || actorCount <= 1)
                return delay;

            int waveWidth = ResolveCinematicWaveWidth(action.Formation, action.MotionPattern, actorCount);
            int waveIndex = Math.Max(0, actorIndex) / waveWidth;
            int laneIndex = Math.Max(0, actorIndex) % waveWidth;
            int laneStep = Math.Min(24, Math.Max(8, stagger / 4));
            return Math.Clamp(delay + waveIndex * stagger + laneIndex * laneStep, 0, 9000);
        }

        private static int ResolveCinematicWaveWidth(string formation, string motionPattern, int actorCount)
        {
            string safeFormation = (formation ?? string.Empty).Trim().ToLowerInvariant();
            string pattern = (motionPattern ?? string.Empty).Trim().ToLowerInvariant();
            int width = safeFormation switch
            {
                "line" => 10,
                "escort" => 6,
                "ambush" => 8,
                "escape" => 4,
                "patrol" => 4,
                _ => pattern switch
                {
                    "pincer" => 8,
                    "retreat" => 4,
                    "standoff" => 6,
                    _ => 6
                }
            };

            return Math.Clamp(width, 1, Math.Max(1, actorCount));
        }

        internal static Point3D BuildCinematicActorSpawnPointForTest(
            Point3D anchorPoint,
            ushort heading,
            int index,
            int actorCount,
            string formation = "",
            string npcAction = "")
        {
            return BuildCinematicActorSpawnPoint(anchorPoint, heading, index, actorCount, formation, npcAction);
        }

        private static Point3D BuildCinematicActorSpawnPoint(
            GamePlayer player,
            Point3D anchorPoint,
            int index,
            int actorCount,
            string formation = "",
            string npcAction = "")
        {
            return BuildCinematicActorSpawnPoint(
                anchorPoint ?? new Point3D(player.X, player.Y, player.Z),
                player?.Heading ?? 0,
                index,
                actorCount,
                formation,
                npcAction);
        }

        private static Point3D BuildCinematicActorSpawnPoint(
            Point3D anchor,
            ushort heading,
            int index,
            int actorCount,
            string formation = "",
            string npcAction = "")
        {
            actorCount = Math.Max(1, actorCount);
            anchor ??= new Point3D(0, 0, 0);
            (double forwardX, double forwardY, double sideX, double sideY) = BuildCinematicFacingVectors(heading);
            string normalizedFormation = (formation ?? string.Empty).Trim().ToLowerInvariant();
            if (normalizedFormation is "line" or "escort")
            {
                int row = index / 10;
                int column = index % 10;
                int centerOffset = (Math.Min(actorCount, 10) - 1) * 45 / 2;
                int forwardOffset = -260 - row * 80;
                int sideOffset = column * 45 - centerOffset;
                return BuildCinematicRelativePoint(anchor, forwardX, forwardY, sideX, sideY, forwardOffset, sideOffset);
            }

            if (normalizedFormation is "ambush")
            {
                double sideAngle = -Math.PI / 2.0 + (Math.PI * index / Math.Max(1, actorCount - 1));
                int ambushRadius = 210 + (index % 3) * 35;
                int forwardOffset = (int)Math.Round(Math.Cos(sideAngle) * ambushRadius);
                int sideOffset = (int)Math.Round(Math.Sin(sideAngle) * ambushRadius);
                return BuildCinematicRelativePoint(anchor, forwardX, forwardY, sideX, sideY, forwardOffset, sideOffset);
            }

            if (normalizedFormation is "escape" or "patrol")
            {
                int spread = (index - actorCount / 2) * 55;
                int distance = 260 + index * 40;
                return BuildCinematicRelativePoint(anchor, forwardX, forwardY, sideX, sideY, distance, spread);
            }

            double angle = (Math.PI * 2.0 * index) / actorCount;
            int ring = index / 12;
            int radius = 130 + ring * 85 + (index % 3) * 18;
            int ringForward = (int)Math.Round(Math.Cos(angle) * radius);
            int ringSide = (int)Math.Round(Math.Sin(angle) * radius);
            return BuildCinematicRelativePoint(anchor, forwardX, forwardY, sideX, sideY, ringForward, ringSide);
        }

        private static (double ForwardX, double ForwardY, double SideX, double SideY) BuildCinematicFacingVectors(GamePlayer player)
        {
            return BuildCinematicFacingVectors(player?.Heading ?? 0);
        }

        private static (double ForwardX, double ForwardY, double SideX, double SideY) BuildCinematicFacingVectors(ushort headingValue)
        {
            double heading = (headingValue / 4096.0) * Math.PI * 2.0;
            double forwardX = Math.Cos(heading);
            double forwardY = Math.Sin(heading);
            return (forwardX, forwardY, -forwardY, forwardX);
        }

        private static Point3D BuildCinematicRelativePoint(
            Point3D anchor,
            double forwardX,
            double forwardY,
            double sideX,
            double sideY,
            int forwardOffset,
            int sideOffset)
        {
            int x = anchor.X + (int)Math.Round(forwardX * forwardOffset + sideX * sideOffset);
            int y = anchor.Y + (int)Math.Round(forwardY * forwardOffset + sideY * sideOffset);
            return new Point3D(x, y, anchor.Z);
        }

        private void SpawnCinematicMarkerLocked(
            string playerKey,
            string questId,
            GamePlayer player,
            DynamicQuestCinematicAction action)
        {
            if (player == null || action == null)
                return;

            DynamicQuestObjective objective = action.Objective ?? new DynamicQuestObjective();
            ushort regionId = objective.RegionId != 0 ? objective.RegionId : player.CurrentRegionID;
            Region region = regionId == player.CurrentRegionID ? player.CurrentRegion : WorldMgr.GetRegion(regionId);
            if (region == null)
                return;

            bool hasObjectivePoint = objective.X != 0 || objective.Y != 0;
            GameStaticItem marker = new()
            {
                CurrentRegion = region,
                Heading = player.Heading,
                Level = 1,
                Realm = player.Realm,
                Name = action.MarkerName,
                Model = action.MarkerModel == 0 ? (ushort)488 : action.MarkerModel,
                X = hasObjectivePoint ? objective.X : player.X,
                Y = hasObjectivePoint ? objective.Y : player.Y,
                Z = hasObjectivePoint ? objective.Z + 2 : player.Z + 2,
                RespawnInterval = -1
            };

            try
            {
                if (!marker.AddToWorld())
                    return;

                string cinematicKey = BuildProgressId(playerKey, questId);
                if (!m_cinematicMarkers.TryGetValue(cinematicKey, out List<GameStaticItem> markers))
                {
                    markers = new List<GameStaticItem>();
                    m_cinematicMarkers[cinematicKey] = markers;
                }

                markers.Add(marker);
            }
            catch (Exception ex)
            {
                Log.Warn($"Dynamic quest cinematic marker spawn failed for quest {questId}: {ex.Message}");
            }
        }

        private void CleanupCinematicMarkersLocked(
            string playerKey,
            string questId,
            string playerName,
            string nodeId,
            string reason)
        {
            string cinematicKey = BuildProgressId(playerKey, questId);
            int removed = 0;
            if (m_cinematicMarkers.TryGetValue(cinematicKey, out List<GameStaticItem> markers))
            {
                foreach (GameStaticItem marker in markers.ToList())
                {
                    try
                    {
                        marker?.Delete();
                        removed++;
                    }
                    catch (Exception ex)
                    {
                        Log.Warn($"Dynamic quest cinematic marker cleanup failed for quest {questId}: {ex.Message}");
                    }
                }

                m_cinematicMarkers.Remove(cinematicKey);
            }

            if (m_cinematicActors.TryGetValue(cinematicKey, out List<GameNPC> actors))
            {
                foreach (GameNPC actor in actors.ToList())
                {
                    try
                    {
                        if (actor != null && actor.ObjectState == GameObject.eObjectState.Active)
                            actor.Delete();
                        removed++;
                    }
                    catch (Exception ex)
                    {
                        Log.Warn($"Dynamic quest cinematic actor cleanup failed for quest {questId}: {ex.Message}");
                    }
                }

                m_cinematicActors.Remove(cinematicKey);
            }

            RecordTimelineEventLocked(
                playerKey,
                playerName,
                questId,
                "cinematic_cleanup",
                nodeId: nodeId,
                detail: $"{reason}:{removed}");
        }

        private void ClearAllCinematicMarkersLocked()
        {
            foreach (List<GameStaticItem> markers in m_cinematicMarkers.Values)
            {
                foreach (GameStaticItem marker in markers.ToList())
                {
                    try
                    {
                        marker?.Delete();
                    }
                    catch (Exception ex)
                    {
                        Log.Warn($"Dynamic quest cinematic marker cleanup failed during ClearAll: {ex.Message}");
                    }
                }
            }

            m_cinematicMarkers.Clear();

            foreach (List<GameNPC> actors in m_cinematicActors.Values)
            {
                foreach (GameNPC actor in actors.ToList())
                {
                    try
                    {
                        if (actor != null && actor.ObjectState == GameObject.eObjectState.Active)
                            actor.Delete();
                    }
                    catch (Exception ex)
                    {
                        Log.Warn($"Dynamic quest cinematic actor cleanup failed during ClearAll: {ex.Message}");
                    }
                }
            }

            m_cinematicActors.Clear();
        }

        private static bool PresentationTriggerMatches(string beatTrigger, string activeTrigger)
        {
            string beat = string.IsNullOrWhiteSpace(beatTrigger) ? "OnNodeEnter" : beatTrigger.Trim();
            string active = string.IsNullOrWhiteSpace(activeTrigger) ? "OnNodeEnter" : activeTrigger.Trim();
            return string.Equals(beat, active, StringComparison.OrdinalIgnoreCase);
        }

        private static IList<DynamicQuestNarrativeScene> ParseNarrativeScenes(string json)
        {
            try
            {
                return string.IsNullOrWhiteSpace(json)
                    ? Array.Empty<DynamicQuestNarrativeScene>()
                    : JsonSerializer.Deserialize<List<DynamicQuestNarrativeScene>>(json, StoryJsonOptions) ?? new List<DynamicQuestNarrativeScene>();
            }
            catch (JsonException)
            {
                return Array.Empty<DynamicQuestNarrativeScene>();
            }
        }

        private static IList<DynamicQuestJournalEntry> BuildProgressJournalEntries(
            DynamicQuestDefinition quest,
            DynamicQuestProgress progress)
        {
            if (quest == null || progress == null)
                return Array.Empty<DynamicQuestJournalEntry>();

            string currentNodeId = progress.CurrentNodeId ?? string.Empty;
            HashSet<string> visibleNodeIds = new(progress.CompletedNodeIds ?? new HashSet<string>(StringComparer.OrdinalIgnoreCase), StringComparer.OrdinalIgnoreCase);
            if (!string.IsNullOrWhiteSpace(currentNodeId))
                visibleNodeIds.Add(currentNodeId);

            if (visibleNodeIds.Count == 0)
                return Array.Empty<DynamicQuestJournalEntry>();

            Dictionary<string, int> nodeOrder = (quest.Nodes ?? Array.Empty<DynamicQuestNode>())
                .Where(node => !string.IsNullOrWhiteSpace(node?.Id))
                .Select((node, index) => new { node.Id, index })
                .GroupBy(item => item.Id, StringComparer.OrdinalIgnoreCase)
                .ToDictionary(group => group.Key, group => group.First().index, StringComparer.OrdinalIgnoreCase);

            HashSet<string> seen = new(StringComparer.OrdinalIgnoreCase);
            return ParseNarrativeScenes(quest.StoryNarrativeJson)
                .Select((scene, index) => new { scene, index })
                .Where(item =>
                    item.scene != null &&
                    visibleNodeIds.Contains(item.scene.NodeId ?? string.Empty) &&
                    !string.IsNullOrWhiteSpace(item.scene.JournalEntry))
                .Where(item => seen.Add($"{item.scene.NodeId}:{item.scene.JournalEntry}"))
                .OrderBy(item => nodeOrder.TryGetValue(item.scene.NodeId ?? string.Empty, out int order) ? order : int.MaxValue)
                .ThenBy(item => item.index)
                .Select(item => new DynamicQuestJournalEntry
                {
                    NodeId = item.scene.NodeId ?? string.Empty,
                    SceneType = item.scene.SceneType ?? string.Empty,
                    Title = item.scene.Title ?? string.Empty,
                    JournalEntry = item.scene.JournalEntry ?? string.Empty,
                    Mood = item.scene.Mood ?? string.Empty,
                    Current = string.Equals(item.scene.NodeId, currentNodeId, StringComparison.OrdinalIgnoreCase)
                })
                .ToList();
        }

        private DynamicQuestProgressItem BuildProgressItemLocked(
            string playerKey,
            DynamicQuestDefinition normalizedQuest,
            DynamicQuestProgress progress,
            DateTime generatedAt)
        {
            DynamicQuestNode currentNode = GetCurrentNode(normalizedQuest, progress);
            DateTime nodeEnteredAt = GetCurrentNodeEnteredAt(progress);
            DynamicQuestTimelineEvent lastEvent = GetLastTimelineEventLocked(playerKey, progress.QuestId);

            return new DynamicQuestProgressItem
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
                Nodes = (normalizedQuest.Nodes ?? Array.Empty<DynamicQuestNode>()).ToList(),
                CompletedNodeIds = progress.CompletedNodeIds.OrderBy(id => id).ToList(),
                Choices = currentNode?.Type == DynamicQuestNodeType.Choice
                    ? (currentNode.Objective?.Choices ?? Array.Empty<DynamicQuestChoice>()).ToList()
                    : Array.Empty<DynamicQuestChoice>(),
                BindingKey = progress.BindingKey,
                WorldRevision = progress.WorldRevision,
                CancelReason = progress.CancelReason,
                Failed = progress.Failed,
                UpdatedAt = progress.UpdatedAt,
                CurrentNodeEnteredAt = nodeEnteredAt,
                CurrentNodeElapsedSeconds = GetElapsedSeconds(nodeEnteredAt, generatedAt),
                PendingWorldSignals = (progress.PendingWorldSignals ?? new HashSet<string>(StringComparer.OrdinalIgnoreCase))
                    .OrderBy(signal => signal, StringComparer.OrdinalIgnoreCase)
                    .ToList(),
                LastEventType = lastEvent?.EventType ?? string.Empty,
                LastEventAt = lastEvent?.At ?? default,
                LastEventNodeId = lastEvent?.NodeId ?? string.Empty,
                LastEventDetail = lastEvent?.Detail ?? string.Empty,
                StalledReason = DescribeProgressStalledReason(normalizedQuest, progress, currentNode),
                JournalEntries = BuildProgressJournalEntries(normalizedQuest, progress)
            };
        }

        private static IList<DynamicQuestPresentationBeat> ParsePresentationBeats(string json)
        {
            try
            {
                return string.IsNullOrWhiteSpace(json)
                    ? Array.Empty<DynamicQuestPresentationBeat>()
                    : JsonSerializer.Deserialize<List<DynamicQuestPresentationBeat>>(json, StoryJsonOptions) ?? new List<DynamicQuestPresentationBeat>();
            }
            catch (JsonException)
            {
                return Array.Empty<DynamicQuestPresentationBeat>();
            }
        }

        private static IList<DynamicQuestPresentationBeat> BuildPresentationBeatsForQuest(DynamicQuestDefinition quest)
        {
            if (quest == null)
                return Array.Empty<DynamicQuestPresentationBeat>();

            List<DynamicQuestPresentationBeat> beats = ParsePresentationBeats(quest.StoryPresentationJson)
                .Where(beat => beat != null)
                .ToList();
            foreach (DynamicQuestPresentationBeat fallback in BuildDefaultPresentationBeats(quest))
            {
                if (beats.Any(beat =>
                        string.Equals(beat.NodeId, fallback.NodeId, StringComparison.OrdinalIgnoreCase) &&
                        PresentationTriggerMatches(beat.Trigger, fallback.Trigger)))
                {
                    continue;
                }

                beats.Add(fallback);
            }

            return beats;
        }

        private static IList<DynamicQuestPresentationBeat> BuildDefaultPresentationBeats(DynamicQuestDefinition quest)
        {
            if (quest == null)
                return Array.Empty<DynamicQuestPresentationBeat>();

            List<DynamicQuestPresentationBeat> beats = new();
            string startNodeId = (quest.StartNodeId ?? string.Empty).Trim();
            string speaker = RequiresStartNpc(quest) ? "StartNpc" : "System";

            foreach (DynamicQuestNode node in quest.Nodes ?? Array.Empty<DynamicQuestNode>())
            {
                if (node == null || string.IsNullOrWhiteSpace(node.Id))
                    continue;

                string nodeId = node.Id.Trim();
                bool startNode = string.Equals(nodeId, startNodeId, StringComparison.OrdinalIgnoreCase);
                string target = PresentationTargetName(quest, node);
                string location = PresentationLocationName(quest, node);

                if (startNode)
                {
                    beats.Add(new DynamicQuestPresentationBeat
                    {
                        NodeId = nodeId,
                        Trigger = "OnAccept",
                        Speaker = speaker,
                        Text = RequiresStartNpc(quest)
                            ? $"{target}의 흔적이 가까워졌습니다. 길목의 공기가 심상치 않습니다."
                            : $"{location} 주변의 공기가 낮게 가라앉고 {target}의 흔적이 시야에 잡힙니다.",
                        Emotion = "urgent",
                        Emote = "Point",
                        CinematicAction = "witness_point",
                        SceneRole = "opening_witness",
                        Formation = "escort",
                        ActorCount = 1
                    });

                    if (RequiresStartNpc(quest) && node.Type == DynamicQuestNodeType.Talk)
                    {
                        beats.Add(new DynamicQuestPresentationBeat
                        {
                            NodeId = nodeId,
                            Trigger = "OnNpcInteract",
                            Speaker = "StartNpc",
                            Text = $"{PresentationStartNpcName(quest)}이 주변을 살피며 {target}의 흔적을 낮게 짚어 줍니다.",
                            Emotion = "caution",
                            Emote = "Point",
                            CinematicAction = "witness_point",
                            SceneRole = "quest_giver_warning",
                            Formation = "escort",
                            ActorCount = 1
                        });
                    }
                }

                if ((node.Edges ?? Array.Empty<DynamicQuestEdge>()).Any(edge => edge?.Condition == DynamicQuestEdgeCondition.WorldSignal))
                {
                    beats.Add(new DynamicQuestPresentationBeat
                    {
                        NodeId = nodeId,
                        Trigger = "OnWorldSignal",
                        Speaker = "System",
                        Text = "기다리던 변화가 맞물리며 다음 길이 열립니다.",
                        Emotion = "warning",
                        Emote = "Point",
                        CinematicAction = "defender_intercept",
                        SceneRole = "signal_intercept",
                        Formation = "line",
                        ActorCount = 2
                    });
                }

                switch (node.Type)
                {
                    case DynamicQuestNodeType.Explore:
                        beats.Add(new DynamicQuestPresentationBeat
                        {
                            NodeId = nodeId,
                            Trigger = "OnExplore",
                            Speaker = "System",
                            Text = BuildExplorePresentationText(location),
                            Emotion = "caution",
                            Emote = "Point",
                            CinematicAction = "witness_point",
                            SceneRole = "clue_witness",
                            Formation = "escort",
                            ActorCount = 1
                        });
                        break;
                    case DynamicQuestNodeType.Kill:
                        beats.Add(new DynamicQuestPresentationBeat
                        {
                            NodeId = nodeId,
                            Trigger = "OnKill",
                            Speaker = "System",
                            Text = $"{target} 위협이 쓰러지자 주변의 긴장이 한 겹 풀립니다.",
                            Emotion = "relief",
                            Emote = "Bow",
                            CinematicAction = "ambush_reveal",
                            SceneRole = "threat_fallout",
                            Formation = "ambush",
                            ActorCount = 5
                        });
                        break;
                    case DynamicQuestNodeType.ReturnToNpc:
                        beats.Add(new DynamicQuestPresentationBeat
                        {
                            NodeId = nodeId,
                            Trigger = "OnNodeEnter",
                            Speaker = "System",
                            Text = $"{PresentationStartNpcName(quest)}에게 보고할 차례입니다.",
                            Emotion = "relief",
                            Emote = "Bow"
                        });
                        break;
                    case DynamicQuestNodeType.Choice:
                        beats.Add(new DynamicQuestPresentationBeat
                        {
                            NodeId = nodeId,
                            Trigger = "OnChoiceShown",
                            Speaker = "System",
                            Text = "결정의 순간이 다가옵니다.",
                            Emotion = "warning",
                            Emote = "Ponder",
                            CinematicAction = "threat_standoff",
                            SceneRole = "choice_confrontation",
                            Formation = "line",
                            ActorCount = 2
                        });
                        beats.Add(new DynamicQuestPresentationBeat
                        {
                            NodeId = nodeId,
                            Trigger = "OnChoiceSelected",
                            Speaker = "System",
                            Text = "선택의 여파가 주변에 남습니다.",
                            Emotion = "warning",
                            Emote = "Point",
                            CinematicAction = "guard_advance",
                            SceneRole = "choice_fallout",
                            Formation = "escort",
                            ActorCount = 2
                        });
                        break;
                    case DynamicQuestNodeType.Complete:
                        beats.Add(new DynamicQuestPresentationBeat
                        {
                            NodeId = nodeId,
                            Trigger = "OnComplete",
                            Speaker = speaker,
                            Text = $"{PresentationTargetName(quest, node)} 위협이 잦아들고 주변의 소리가 천천히 돌아옵니다.",
                            Emotion = "gratitude",
                            Emote = "Bow"
                        });
                        break;
                }
            }

            return beats;
        }

        private static string PresentationTargetName(DynamicQuestDefinition quest, DynamicQuestNode node)
        {
            string target = node?.Objective?.TargetName;
            if (string.IsNullOrWhiteSpace(target))
                target = quest?.TargetName;
            return string.IsNullOrWhiteSpace(target) ? "위협" : target.Trim();
        }

        private static string PresentationLocationName(DynamicQuestDefinition quest, DynamicQuestNode node)
        {
            string location = node?.Objective?.LocationName;
            if (string.IsNullOrWhiteSpace(location))
                location = node?.Title;
            if (string.IsNullOrWhiteSpace(location))
                location = quest?.StartNpcName;
            return string.IsNullOrWhiteSpace(location) ? "주변" : location.Trim();
        }

        private static string BuildExplorePresentationText(string location)
        {
            location = string.IsNullOrWhiteSpace(location) ? "주변의 흔적" : location.Trim();
            return location.Contains("흔적", StringComparison.OrdinalIgnoreCase)
                ? $"{location}이 선명해집니다."
                : $"{location}에 남은 흔적이 선명해집니다.";
        }

        private static string PresentationStartNpcName(DynamicQuestDefinition quest)
        {
            string name = quest?.StartNpcName;
            return string.IsNullOrWhiteSpace(name) ? "의뢰인" : name.Trim();
        }

        private static string BuildNarrativeSceneDetail(DynamicQuestNarrativeScene scene)
        {
            if (scene == null)
                return string.Empty;

            return string.Join("\n\n", new[]
                {
                    SanitizeInGameStoryText(scene.Title),
                    SanitizeInGameStoryText(scene.Body)
                }
                .Where(text => !string.IsNullOrWhiteSpace(text))
                .Select(text => text.Trim()));
        }

        internal static string BuildNarrativeSceneMessageForTest(DynamicQuestNarrativeScene scene)
        {
            return BuildNarrativeSceneMessage(scene);
        }

        internal static string BuildNarrativeSceneTitleMessageForTest(DynamicQuestNarrativeScene scene)
        {
            return BuildNarrativeSceneTitleMessage(scene);
        }

        internal static string BuildNarrativeSceneJournalMessageForTest(DynamicQuestNarrativeScene scene)
        {
            return BuildNarrativeSceneJournalMessage(scene);
        }

        private static string BuildNarrativeSceneMessage(DynamicQuestNarrativeScene scene)
        {
            string detail = BuildNarrativeSceneDetail(scene);
            if (string.IsNullOrWhiteSpace(detail))
                return string.Empty;

            string mood = (scene?.Mood ?? string.Empty).Trim();
            return string.IsNullOrWhiteSpace(mood)
                ? detail
                : $"{detail}\n\n분위기: {mood}";
        }

        private static string BuildNarrativeSceneTitleMessage(DynamicQuestNarrativeScene scene)
        {
            string title = SanitizeInGameStoryText(scene?.Title);
            return string.IsNullOrWhiteSpace(title) ? string.Empty : $"[동적 퀘스트] {title}";
        }

        private static string BuildNarrativeSceneJournalMessage(DynamicQuestNarrativeScene scene)
        {
            string journal = SanitizeInGameStoryText(scene?.JournalEntry);
            return string.IsNullOrWhiteSpace(journal) ? string.Empty : $"저널 갱신: {journal}";
        }

        private static bool PlayNarrativeScene(GamePlayer player, DynamicQuestNarrativeScene scene)
        {
            if (player == null || scene == null)
                return false;

            bool sent = false;
            string title = BuildNarrativeSceneTitleMessage(scene);
            if (!string.IsNullOrWhiteSpace(title))
            {
                player.Out.SendMessage(title, eChatType.CT_ScreenCenter, eChatLoc.CL_SystemWindow);
                sent = true;
            }

            string message = BuildNarrativeSceneMessage(scene);
            if (!string.IsNullOrWhiteSpace(message))
            {
                player.Out.SendMessage(message, eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                sent = true;
            }

            string journal = BuildNarrativeSceneJournalMessage(scene);
            if (!string.IsNullOrWhiteSpace(journal))
            {
                player.Out.SendMessage(journal, eChatType.CT_System, eChatLoc.CL_SystemWindow);
                sent = true;
            }

            return sent;
        }

        private static string BuildPresentationBeatDetail(DynamicQuestPresentationBeat beat)
        {
            if (beat == null)
                return string.Empty;

            return string.Join("|", new[]
            {
                beat.Trigger ?? string.Empty,
                beat.Speaker ?? string.Empty,
                beat.Emotion ?? string.Empty,
                beat.Emote ?? string.Empty,
                SanitizeInGameStoryText(beat.Text),
                beat.CinematicAction ?? string.Empty,
                beat.SceneRole ?? string.Empty,
                beat.Formation ?? string.Empty,
                Math.Max(0, beat.ActorCount).ToString(),
                Math.Max(0, beat.DelayMs).ToString()
            });
        }

        internal static bool ShouldSpotlightPresentationBeatForTest(DynamicQuestPresentationBeat beat)
        {
            return ShouldSpotlightPresentationBeat(beat);
        }

        internal static string BuildPresentationSpotlightMessageForTest(DynamicQuestPresentationBeat beat)
        {
            return BuildPresentationSpotlightMessage(beat);
        }

        private static bool ShouldSpotlightPresentationBeat(DynamicQuestPresentationBeat beat)
        {
            if (beat == null)
                return false;

            string trigger = (beat.Trigger ?? string.Empty).Trim();
            if (string.Equals(trigger, "OnChoiceSelected", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(trigger, "OnWorldSignal", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(trigger, "OnComplete", StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            string emotion = (beat.Emotion ?? string.Empty).Trim();
            return string.Equals(emotion, "urgency", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(emotion, "fear", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(emotion, "celebration", StringComparison.OrdinalIgnoreCase);
        }

        private static string BuildPresentationSpotlightMessage(DynamicQuestPresentationBeat beat)
        {
            string text = SanitizeInGameStoryText(beat?.Text);
            if (string.IsNullOrWhiteSpace(text))
                return string.Empty;

            const int maxLength = 140;
            return text.Length <= maxLength ? text : $"{text.Substring(0, maxLength - 1).TrimEnd()}...";
        }

        private static void PlayPresentationBeat(GamePlayer player, GameNPC npc, DynamicQuestPresentationBeat beat)
        {
            if (player == null || beat == null)
                return;

            string speaker = (beat.Speaker ?? string.Empty).Trim();
            string text = SanitizeInGameStoryText(beat.Text);
            bool npcSpeaker =
                string.IsNullOrWhiteSpace(speaker) ||
                string.Equals(speaker, "StartNpc", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(speaker, "Npc", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(speaker, "TargetNpc", StringComparison.OrdinalIgnoreCase);

            if (string.IsNullOrWhiteSpace(text))
            {
                if (npcSpeaker && npc != null && TryResolvePresentationEmote(beat, out eEmote silentEmote))
                    npc.Emote(silentEmote);

                return;
            }

            if (ShouldSpotlightPresentationBeat(beat))
            {
                string spotlight = BuildPresentationSpotlightMessage(beat);
                if (!string.IsNullOrWhiteSpace(spotlight))
                    player.Out.SendMessage(spotlight, eChatType.CT_ScreenCenter, eChatLoc.CL_SystemWindow);
            }

            if (string.Equals(speaker, "System", StringComparison.OrdinalIgnoreCase))
            {
                player.Out.SendMessage(text, eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                return;
            }

            if (npcSpeaker && npc != null)
            {
                npc.SayTo(player, text);

                if (TryResolvePresentationEmote(beat, out eEmote emote))
                    npc.Emote(emote);

                return;
            }

            string label = string.Equals(speaker, "Companion", StringComparison.OrdinalIgnoreCase)
                ? "동료"
                : (string.IsNullOrWhiteSpace(speaker) ? "동적 퀘스트" : speaker);
            player.Out.SendMessage($"{label}: {text}", eChatType.CT_Say, eChatLoc.CL_SystemWindow);
        }

        private static string SanitizeInGameStoryText(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return string.Empty;

            string[] lines = value.Replace("\r\n", "\n").Replace('\r', '\n').Split('\n');
            for (int i = 0; i < lines.Length; i++)
            {
                string line = lines[i].Trim();
                while (line.Length > 0 && IsMarkdownLinePrefix(line[0]))
                    line = line.Substring(1).TrimStart();
                lines[i] = line;
            }

            return string.Join("\n", lines.Where(line => !string.IsNullOrWhiteSpace(line))).Trim();
        }

        private static bool IsMarkdownLinePrefix(char ch)
        {
            return ch == '#' || ch == '>' || ch == '*' || ch == '-';
        }

        internal static bool TryResolvePresentationEmoteForTest(DynamicQuestPresentationBeat beat, out eEmote emote)
        {
            return TryResolvePresentationEmote(beat, out emote);
        }

        private static bool TryResolvePresentationEmote(DynamicQuestPresentationBeat beat, out eEmote emote)
        {
            emote = default;
            if (beat == null)
                return false;

            if (Enum.TryParse(beat.Emote, true, out emote))
                return true;

            string emotion = (beat.Emotion ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(emotion))
                return false;

            switch (emotion.ToLowerInvariant())
            {
                case "fear":
                case "afraid":
                case "ominous":
                case "anxious":
                case "urgent":
                case "urgency":
                    emote = eEmote.Shiver;
                    return true;
                case "anger":
                case "angry":
                    emote = eEmote.Angry;
                    return true;
                case "sad":
                case "grief":
                    emote = eEmote.Cry;
                    return true;
                case "relief":
                case "gratitude":
                case "respect":
                    emote = eEmote.Bow;
                    return true;
                case "joy":
                case "hope":
                case "celebration":
                    emote = eEmote.Cheer;
                    return true;
                case "doubt":
                case "confusion":
                    emote = eEmote.Confused;
                    return true;
                case "warning":
                case "caution":
                case "suspicion":
                    emote = eEmote.Point;
                    return true;
                default:
                    return false;
            }
        }

        private bool HasTimelineEventLocked(string playerKey, string questId, string eventType, string nodeId)
        {
            return m_playerTimeline.TryGetValue(playerKey ?? string.Empty, out List<DynamicQuestTimelineEvent> timeline) &&
                   timeline.Any(evt =>
                       string.Equals(evt.QuestId, questId, StringComparison.OrdinalIgnoreCase) &&
                       string.Equals(evt.EventType, eventType, StringComparison.OrdinalIgnoreCase) &&
                       string.Equals(evt.NodeId, nodeId, StringComparison.OrdinalIgnoreCase));
        }

        private bool HasTimelineEventLocked(string playerKey, string questId, string eventType, string nodeId, string detail)
        {
            return m_playerTimeline.TryGetValue(playerKey ?? string.Empty, out List<DynamicQuestTimelineEvent> timeline) &&
                   timeline.Any(evt =>
                       string.Equals(evt.QuestId, questId, StringComparison.OrdinalIgnoreCase) &&
                       string.Equals(evt.EventType, eventType, StringComparison.OrdinalIgnoreCase) &&
                       string.Equals(evt.NodeId, nodeId, StringComparison.OrdinalIgnoreCase) &&
                       string.Equals(evt.Detail, detail, StringComparison.Ordinal));
        }

        private void RecordTimelineEventLocked(
            string playerKey,
            string playerName,
            string questId,
            string eventType,
            string nodeId = "",
            string fromNodeId = "",
            string toNodeId = "",
            string detail = "",
            string choiceId = "",
            int count = 0)
        {
            playerKey = (playerKey ?? string.Empty).Trim();
            eventType = (eventType ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(playerKey) || string.IsNullOrWhiteSpace(eventType))
                return;

            if (!m_playerTimeline.TryGetValue(playerKey, out List<DynamicQuestTimelineEvent> timeline))
            {
                timeline = new List<DynamicQuestTimelineEvent>();
                m_playerTimeline[playerKey] = timeline;
            }

            timeline.Add(new DynamicQuestTimelineEvent
            {
                At = DateTime.UtcNow,
                PlayerKey = playerKey,
                PlayerName = (playerName ?? string.Empty).Trim(),
                QuestId = (questId ?? string.Empty).Trim(),
                EventType = eventType,
                NodeId = (nodeId ?? string.Empty).Trim(),
                FromNodeId = (fromNodeId ?? string.Empty).Trim(),
                ToNodeId = (toNodeId ?? string.Empty).Trim(),
                Detail = (detail ?? string.Empty).Trim(),
                ChoiceId = (choiceId ?? string.Empty).Trim(),
                Count = count
            });

            if (timeline.Count > MaxPlayerTimelineEvents)
                timeline.RemoveRange(0, timeline.Count - MaxPlayerTimelineEvents);
        }

        private bool HasQuestCompletedTimelineEventLocked(string playerKey, string questId)
        {
            return m_playerTimeline.TryGetValue(playerKey ?? string.Empty, out List<DynamicQuestTimelineEvent> timeline) &&
                   timeline.Any(evt =>
                       string.Equals(evt.QuestId, questId, StringComparison.OrdinalIgnoreCase) &&
                       string.Equals(evt.EventType, "quest_completed", StringComparison.OrdinalIgnoreCase));
        }

        private bool HasQuestRewardedTimelineEventLocked(string playerKey, string questId)
        {
            return m_playerTimeline.TryGetValue(playerKey ?? string.Empty, out List<DynamicQuestTimelineEvent> timeline) &&
                   timeline.Any(evt =>
                       string.Equals(evt.QuestId, questId, StringComparison.OrdinalIgnoreCase) &&
                       string.Equals(evt.EventType, "quest_rewarded", StringComparison.OrdinalIgnoreCase));
        }

        private DynamicQuestTimelineEvent GetLastTimelineEventLocked(string playerKey, string questId)
        {
            playerKey = (playerKey ?? string.Empty).Trim();
            questId = (questId ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(playerKey) ||
                string.IsNullOrWhiteSpace(questId) ||
                !m_playerTimeline.TryGetValue(playerKey, out List<DynamicQuestTimelineEvent> timeline))
            {
                return null;
            }

            return timeline
                .Where(evt => string.Equals(evt.QuestId, questId, StringComparison.OrdinalIgnoreCase))
                .Where(evt => !IsPresentationOnlyTimelineEvent(evt?.EventType))
                .OrderByDescending(evt => evt.At)
                .FirstOrDefault();
        }

        private static bool IsPresentationOnlyTimelineEvent(string eventType)
        {
            switch ((eventType ?? string.Empty).Trim().ToLowerInvariant())
            {
                case "presentation_beat":
                case "presentation_spotlight":
                case "narrative_scene":
                case "narrative_scene_presented":
                case "journal_entry":
                case "cinematic_action":
                case "scene_beat_outcome":
                case "scene_choreography_phase":
                case "scene_actor_exchange":
                case "scene_exchange_outcome":
                case "scene_consequence":
                case "scene_world_signal":
                case "world_signal_scene_shift":
                case "cinematic_cleanup":
                case "cinematic_actor_spawn_summary":
                case "cinematic_actor_motion_summary":
                case "cinematic_actor_engagement_summary":
                case "choice_outcome_scene":
                case "choice_consequence":
                case "world_memory_marked":
                    return true;
                default:
                    return false;
            }
        }

        private static DynamicQuestTimelineEvent CloneTimelineEvent(DynamicQuestTimelineEvent source)
        {
            return new DynamicQuestTimelineEvent
            {
                At = source.At,
                PlayerKey = source.PlayerKey,
                PlayerName = source.PlayerName,
                QuestId = source.QuestId,
                EventType = source.EventType,
                NodeId = source.NodeId,
                FromNodeId = source.FromNodeId,
                ToNodeId = source.ToNodeId,
                Detail = source.Detail,
                ChoiceId = source.ChoiceId,
                Count = source.Count
            };
        }

        private static IList<DynamicQuestPresentationBeatObservation> BuildPresentationBeatObservations(IEnumerable<DynamicQuestTimelineEvent> events)
        {
            if (events == null)
                return Array.Empty<DynamicQuestPresentationBeatObservation>();

            return events
                .Where(evt => string.Equals(evt?.EventType, "presentation_beat", StringComparison.OrdinalIgnoreCase))
                .Select(ParsePresentationBeatObservation)
                .Where(beat => beat != null)
                .ToList();
        }

        private static DynamicQuestPresentationBeatObservation ParsePresentationBeatObservation(DynamicQuestTimelineEvent evt)
        {
            if (evt == null)
                return null;

            string[] parts = (evt.Detail ?? string.Empty).Split('|');
            string trigger = string.Empty;
            string speaker = string.Empty;
            string emotion = string.Empty;
            string emote = string.Empty;
            string text = string.Empty;
            string cinematicAction = string.Empty;
            string sceneRole = string.Empty;
            string formation = string.Empty;
            int actorCount = 0;
            int delayMs = 0;

            if (parts.Length >= 10)
            {
                trigger = parts[0];
                speaker = parts[1];
                emotion = parts[2];
                emote = parts[3];
                text = string.Join("|", parts.Skip(4).Take(parts.Length - 9));
                cinematicAction = parts[parts.Length - 5];
                sceneRole = parts[parts.Length - 4];
                formation = parts[parts.Length - 3];
                int.TryParse(parts[parts.Length - 2], out actorCount);
                int.TryParse(parts[parts.Length - 1], out delayMs);
            }
            else if (parts.Length >= 5)
            {
                trigger = parts[0];
                speaker = parts[1];
                emotion = parts[2];
                emote = parts[3];
                text = string.Join("|", parts.Skip(4));
            }
            else if (parts.Length >= 4)
            {
                speaker = parts[0];
                emotion = parts[1];
                emote = parts[2];
                text = string.Join("|", parts.Skip(3));
            }
            else
            {
                text = evt.Detail ?? string.Empty;
            }

            return new DynamicQuestPresentationBeatObservation
            {
                At = evt.At,
                QuestId = evt.QuestId ?? string.Empty,
                NodeId = evt.NodeId ?? string.Empty,
                Trigger = trigger ?? string.Empty,
                Speaker = speaker ?? string.Empty,
                Emotion = emotion ?? string.Empty,
                Emote = emote ?? string.Empty,
                Text = text ?? string.Empty,
                CinematicAction = cinematicAction ?? string.Empty,
                SceneRole = sceneRole ?? string.Empty,
                Formation = formation ?? string.Empty,
                ActorCount = Math.Max(0, actorCount),
                DelayMs = Math.Max(0, delayMs)
            };
        }

        private void RemoveProgress(GamePlayer player, DynamicQuestProgress progress)
        {
            string playerKey = GetPlayerKey(player);
            lock (m_lock)
            {
                if (m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                    progressList.Remove(progress);

                if (progress != null)
                {
                    progress.Completed = true;
                    progress.IsComplete = true;
                    progress.UpdatedAt = DateTime.UtcNow;
                    SaveProgress(playerKey, player.Name ?? string.Empty, progress);
                }
            }

            SyncDynamicQuestJournal(player);
        }

        private DynamicQuestDefinition GetAvailableQuest(GameNPC npc, GamePlayer player)
        {
            lock (m_lock)
            {
                string playerKey = GetPlayerKey(player);
                return m_quests.Values.FirstOrDefault(quest =>
                    IsStartNpc(quest, npc) &&
                    !HasCompletedQuest(playerKey, quest.Id) &&
                    !HasCompletedStoryFamily(playerKey, quest) &&
                    HasStoryPrerequisites(playerKey, quest) &&
                    !HasActiveStoryFamily(playerKey, quest) &&
                    !HasProgress(playerKey, quest.Id) &&
                    PlayerLevelMatchesQuest(quest, player.Level));
            }
        }

        public bool TryAcceptRegionalAutoQuest(GamePlayer player)
        {
            if (player == null)
                return false;

            string playerKey = GetPlayerKey(player);
            EnsurePlayerProgressLoaded(playerKey, player.Name ?? string.Empty);
            ushort regionId = player.CurrentRegionID;

            foreach (string trigger in BuildAutoAcceptTriggers(regionId, DateTime.UtcNow))
            {
                foreach (DynamicQuestDefinition quest in GetAvailableWorldQuests(playerKey, player.Level, trigger, autoAcceptOnly: true))
                {
                    if (!IsInsideAutoAcceptStartScope(quest, regionId, player.X, player.Y))
                        continue;

                    return TryAcceptWorldQuest(player, quest.Id, trigger, showFailureMessage: false);
                }
            }

            return false;
        }

        private DynamicQuestDefinition GetAvailableWorldQuest(
            string playerKey,
            int playerLevel,
            string trigger,
            bool autoAcceptOnly = false,
            bool includeAutoAccept = true)
        {
            return GetAvailableWorldQuests(playerKey, playerLevel, trigger, autoAcceptOnly, includeAutoAccept).FirstOrDefault();
        }

        private IList<DynamicQuestDefinition> GetAvailableWorldQuests(
            string playerKey,
            int playerLevel,
            string trigger,
            bool autoAcceptOnly = false,
            bool includeAutoAccept = true)
        {
            playerKey = (playerKey ?? string.Empty).Trim();

            lock (m_lock)
            {
                return m_quests.Values
                    .Where(quest =>
                        !RequiresStartNpc(quest) &&
                        (!autoAcceptOnly || quest.StartMode == DynamicQuestStartMode.AutoAccept) &&
                        (includeAutoAccept || quest.StartMode != DynamicQuestStartMode.AutoAccept) &&
                        QuestTriggerMatches(quest, trigger) &&
                        !HasCompletedQuest(playerKey, quest.Id) &&
                        !HasCompletedStoryFamily(playerKey, quest) &&
                        HasStoryPrerequisites(playerKey, quest) &&
                        !HasActiveStoryFamily(playerKey, quest) &&
                        !HasProgress(playerKey, quest.Id) &&
                        PlayerLevelMatchesQuest(quest, playerLevel))
                    .OrderByDescending(quest => quest.StartMode == DynamicQuestStartMode.AutoAccept)
                    .ThenByDescending(IsDummyEvaluationOffer)
                    .ThenBy(quest => quest.CreatedAt)
                    .ToList();
            }
        }

        internal static bool PlayerLevelMatchesQuestForTest(DynamicQuestDefinition quest, int playerLevel)
        {
            return PlayerLevelMatchesQuest(quest, playerLevel);
        }

        private static bool PlayerLevelMatchesQuest(DynamicQuestDefinition quest, int playerLevel)
        {
            if (quest == null || playerLevel < quest.MinLevel)
                return false;

            if (playerLevel <= quest.MaxLevel)
                return true;

            return IsMobGrowthBranchQuest(quest);
        }

        private static bool IsMobGrowthBranchQuest(DynamicQuestDefinition quest)
        {
            return (quest?.Tags ?? Array.Empty<string>()).Any(tag =>
            {
                string value = (tag ?? string.Empty).Trim();
                return string.Equals(value, "branch:mob-growth", StringComparison.OrdinalIgnoreCase) ||
                    value.StartsWith("world-signal:mob-growth:", StringComparison.OrdinalIgnoreCase) ||
                    value.StartsWith("signal:mob-growth:", StringComparison.OrdinalIgnoreCase);
            });
        }

        private static bool IsDummyEvaluationOffer(DynamicQuestDefinition quest)
        {
            return (quest?.Tags ?? Array.Empty<string>()).Any(tag =>
                string.Equals((tag ?? string.Empty).Trim(), "dummy-evaluation-offer", StringComparison.OrdinalIgnoreCase));
        }

        private bool TryGetQuest(string questId, out DynamicQuestDefinition quest)
        {
            lock (m_lock)
                return m_quests.TryGetValue(questId, out quest);
        }

        private bool TryGetQuestForProgress(DynamicQuestProgress progress, out DynamicQuestDefinition quest)
        {
            quest = null;
            if (progress == null)
                return false;

            if (progress.QuestSnapshot != null)
            {
                quest = NormalizeQuest(progress.QuestSnapshot);
                return quest != null;
            }

            return TryGetQuest(progress.QuestId, out quest);
        }

        private static bool IsStartNpc(DynamicQuestDefinition quest, GameNPC npc)
        {
            return quest != null &&
                npc != null &&
                RequiresStartNpc(quest) &&
                quest.StartRegionId == npc.CurrentRegionID &&
                string.Equals(quest.StartNpcInternalId, npc.InternalID ?? string.Empty, StringComparison.OrdinalIgnoreCase);
        }

        private static bool RequiresStartNpc(DynamicQuestDefinition quest)
        {
            return quest == null || quest.StartMode == DynamicQuestStartMode.NpcOffer;
        }

        private static bool QuestTriggerMatches(DynamicQuestDefinition quest, string trigger)
        {
            string value = (trigger ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(value))
                return false;

            if (quest?.StartMode == DynamicQuestStartMode.AutoAccept &&
                IsRegionalAutoAcceptTrigger(value) &&
                HasExplicitNonRegionalAutoAcceptStartTrigger(quest))
                return false;

            string[] acceptedTags =
            {
                value,
                $"trigger:{value}",
                $"world:{value}",
                $"world-signal:{value}",
                $"signal:{value}",
                $"autoaccept:{value}"
            };

            return (quest.Tags ?? Array.Empty<string>()).Any(tag =>
                acceptedTags.Any(accepted => string.Equals(tag, accepted, StringComparison.OrdinalIgnoreCase)));
        }

        private static bool HasExplicitNonRegionalAutoAcceptStartTrigger(DynamicQuestDefinition quest)
        {
            return (quest?.Tags ?? Array.Empty<string>()).Any(tag =>
            {
                string value = (tag ?? string.Empty).Trim();
                string trigger = string.Empty;
                if (value.StartsWith("trigger:", StringComparison.OrdinalIgnoreCase))
                    trigger = value.Substring("trigger:".Length);
                else if (value.StartsWith("autoaccept:", StringComparison.OrdinalIgnoreCase))
                    trigger = value.Substring("autoaccept:".Length);

                return !string.IsNullOrWhiteSpace(trigger) &&
                       !IsRegionalAutoAcceptTrigger(trigger);
            });
        }

        private static bool IsRegionalAutoAcceptTrigger(string trigger)
        {
            string value = (trigger ?? string.Empty).Trim();
            return string.Equals(value, "region-entered", StringComparison.OrdinalIgnoreCase) ||
                   value.StartsWith("region:", StringComparison.OrdinalIgnoreCase) ||
                   value.StartsWith("region-entered:", StringComparison.OrdinalIgnoreCase);
        }

        private static IEnumerable<string> BuildRegionalAutoAcceptTriggers(ushort regionId)
        {
            if (regionId == 0)
                yield break;

            yield return $"region:{regionId}";
            yield return $"region-entered:{regionId}";
            yield return "region-entered";
        }

        private static IEnumerable<string> BuildAutoAcceptTriggers(ushort regionId, DateTime nowUtc)
        {
            foreach (string trigger in BuildRegionalAutoAcceptTriggers(regionId))
                yield return trigger;

            foreach (string trigger in BuildTimeWindowSignals(nowUtc))
                yield return trigger;
        }

        private static IEnumerable<string> BuildTimeWindowSignals(DateTime nowUtc)
        {
            string window = GetTimeWindow(nowUtc);
            yield return "time-window";
            yield return $"time-window:{window}";
        }

        private static IEnumerable<string> BuildRegionEnteredSignals(ushort regionId)
        {
            if (regionId == 0)
                yield break;

            yield return "region-entered";
            yield return $"region-entered:{regionId}";
            yield return $"region:{regionId}";
        }

        private static string GetTimeWindow(DateTime nowUtc)
        {
            int hour = nowUtc.ToUniversalTime().Hour;
            if (hour >= 5 && hour < 7)
                return "dawn";
            if (hour >= 7 && hour < 18)
                return "day";
            if (hour >= 18 && hour < 20)
                return "dusk";

            return "night";
        }

        private static IEnumerable<string> BuildItemAcquiredSignals(DbInventoryItem item)
        {
            if (item == null)
                yield break;

            yield return "item-acquired";

            string id = NormalizeSignalToken(item.Id_nb);
            if (!string.IsNullOrWhiteSpace(id))
                yield return $"item-acquired:id:{id}";

            string name = NormalizeSignalToken(item.Name);
            if (!string.IsNullOrWhiteSpace(name))
                yield return $"item-acquired:name:{name}";
        }

        private static string NormalizeSignalToken(string value)
        {
            value = (value ?? string.Empty).Trim().ToLowerInvariant();
            if (value.Length == 0)
                return string.Empty;

            StringBuilder builder = new();
            foreach (char ch in value)
            {
                if (char.IsLetterOrDigit(ch) || ch == '-' || ch == '_' || ch == '.')
                    builder.Append(ch);
                else if (builder.Length == 0 || builder[builder.Length - 1] != '-')
                    builder.Append('-');

                if (builder.Length >= 80)
                    break;
            }

            return builder.ToString().Trim('-');
        }

        internal static IList<string> BuildTimeWindowSignalsForTest(DateTime nowUtc)
        {
            return BuildTimeWindowSignals(nowUtc).ToList();
        }

        internal static IList<string> BuildRegionEnteredSignalsForTest(ushort regionId)
        {
            return BuildRegionEnteredSignals(regionId).ToList();
        }

        internal static IList<string> BuildItemAcquiredSignalsForTest(DbInventoryItem item)
        {
            return BuildItemAcquiredSignals(item).ToList();
        }

        internal DbItemTemplate BuildItemAcquiredBranchClueDropForTest(string playerKey, string npcName, int npcLevel, ushort regionId)
        {
            lock (m_lock)
                return BuildItemAcquiredBranchClueDropLocked(playerKey, npcName, npcLevel, regionId);
        }

        private DbItemTemplate BuildItemAcquiredBranchClueDropLocked(string playerKey, string npcName, int npcLevel, ushort regionId)
        {
            if (string.IsNullOrWhiteSpace(playerKey) ||
                string.IsNullOrWhiteSpace(npcName) ||
                !m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
            {
                return null;
            }

            foreach (DynamicQuestProgress progress in progressList)
            {
                if (progress == null || progress.Completed || progress.IsComplete || progress.Failed || !TryGetQuestForProgress(progress, out DynamicQuestDefinition quest))
                    continue;

                DynamicQuestDefinition normalized = NormalizeQuest(quest);
                if (!QuestCanUseItemAcquiredBranchSignal(normalized, progress))
                    continue;

                if (!QuestHasMatchingKillObjective(normalized, npcName, npcLevel, regionId))
                    continue;

                return CreateItemAcquiredBranchClueTemplate(normalized, npcName, npcLevel);
            }

            return null;
        }

        private static bool QuestCanUseItemAcquiredBranchSignal(DynamicQuestDefinition quest, DynamicQuestProgress progress)
        {
            if (quest == null || progress == null)
                return false;

            bool tagged = (quest.Tags ?? Array.Empty<string>()).Any(tag =>
            {
                string value = (tag ?? string.Empty).Trim();
                return string.Equals(value, "branch:item-acquired", StringComparison.OrdinalIgnoreCase) ||
                       string.Equals(value, "world-signal:item-acquired", StringComparison.OrdinalIgnoreCase);
            });

            if (!tagged)
                return false;

            DynamicQuestNode currentNode = GetCurrentNode(quest, progress);
            return NodeHasMatchingWorldSignalEdge(currentNode, "item-acquired") ||
                   QuestCanUseWorldSignalLater(quest, progress, "item-acquired");
        }

        private static bool QuestHasMatchingKillObjective(DynamicQuestDefinition quest, string npcName, int npcLevel, ushort regionId)
        {
            if (quest == null || string.IsNullOrWhiteSpace(npcName))
                return false;

            return (quest.Nodes ?? Array.Empty<DynamicQuestNode>())
                .Where(node => node?.Type == DynamicQuestNodeType.Kill)
                .Select(node => node.Objective ?? new DynamicQuestObjective())
                .Any(objective =>
                    NameMatches(npcName, objective.TargetName) &&
                    (objective.RegionId == 0 || objective.RegionId == regionId) &&
                    npcLevel >= objective.MinLevel &&
                    npcLevel <= objective.MaxLevel);
        }

        private static DbItemTemplate CreateItemAcquiredBranchClueTemplate(DynamicQuestDefinition quest, string npcName, int npcLevel)
        {
            string questId = NormalizeSignalToken(quest?.Id);
            string target = NormalizeSignalToken(npcName);
            string id = $"dynamic_quest_clue_{questId}_{target}";
            if (id.Length > 120)
                id = id.Substring(0, 120).TrimEnd('-');

            return new DbItemTemplate
            {
                Id_nb = id,
                Name = $"Quest Clue: {npcName}",
                Level = Math.Clamp(npcLevel, 1, 51),
                Model = 488,
                Object_Type = (int)eObjectType.GenericItem,
                Item_Type = (int)eInventorySlot.Ground,
                Quality = 100,
                Condition = 50000,
                MaxCondition = 50000,
                Durability = 50000,
                MaxDurability = 50000,
                IsPickable = true,
                IsDropable = true,
                CanDropAsLoot = true,
                MaxCount = 1,
                PackSize = 1,
                Price = 0
            };
        }

        private void RecordQuestWorldImpactLocked(string playerKey, string playerName, DynamicQuestDefinition quest, DynamicQuestProgress progress)
        {
            if (quest == null)
                return;

            ushort regionId = ResolveQuestImpactRegion(quest);
            if (regionId == 0)
                return;

            DynamicQuestChoice selectedChoice = FindSelectedChoice(quest, progress, out string selectedChoiceId);
            string consequence = BuildChoiceConsequence(selectedChoice);
            IList<string> sceneConsequences = FindSceneConsequenceKindsLocked(playerKey, quest.Id);
            IList<string> signals = BuildWorldImpactSignals(quest, progress, regionId, selectedChoiceId, sceneConsequences);
            string impactType = ResolveWorldImpactType(selectedChoiceId, signals);
            string summary = BuildWorldImpactSummaryText(
                quest,
                progress,
                regionId,
                selectedChoiceId,
                consequence,
                impactType,
                sceneConsequences);

            DynamicQuestWorldImpactRecord record = new()
            {
                At = DateTime.UtcNow,
                QuestId = quest.Id ?? string.Empty,
                Title = quest.Title ?? string.Empty,
                PlayerName = playerName ?? string.Empty,
                Realm = ResolveQuestRealm(quest),
                RegionId = regionId,
                TargetName = quest.TargetName ?? string.Empty,
                ImpactType = impactType,
                ChoiceId = selectedChoiceId,
                ChoiceConsequence = consequence,
                Summary = summary,
                Signals = signals
            };

            m_worldImpactRecords.Add(record);
            if (m_worldImpactRecords.Count > 500)
                m_worldImpactRecords.RemoveRange(0, m_worldImpactRecords.Count - 500);

            RecordTimelineEventLocked(
                playerKey,
                playerName,
                quest.Id,
                "world_impact",
                nodeId: "complete",
                detail: BuildWorldImpactTimelineDetail(regionId, selectedChoiceId, impactType, signals));

            if (!string.IsNullOrWhiteSpace(summary))
            {
                RecordTimelineEventLocked(
                    playerKey,
                    playerName,
                    quest.Id,
                    "world_impact_summary",
                    nodeId: "complete",
                    detail: summary,
                    choiceId: selectedChoiceId);
            }
        }

        private static DynamicQuestChoice FindSelectedChoice(DynamicQuestDefinition quest, DynamicQuestProgress progress, out string selectedChoiceId)
        {
            selectedChoiceId = string.Empty;
            if (quest?.Nodes == null || progress?.ChoiceHistory == null || progress.ChoiceHistory.Count == 0)
                return null;

            foreach (DynamicQuestNode node in quest.Nodes)
            {
                if (node == null || !progress.ChoiceHistory.TryGetValue(node.Id ?? string.Empty, out string choiceId))
                    continue;

                DynamicQuestChoice choice = (node.Objective?.Choices ?? Array.Empty<DynamicQuestChoice>())
                    .FirstOrDefault(candidate => string.Equals(candidate.Id, choiceId, StringComparison.OrdinalIgnoreCase));
                if (choice == null)
                    continue;

                selectedChoiceId = choice.Id ?? string.Empty;
                return choice;
            }

            selectedChoiceId = progress.ChoiceHistory.Values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? string.Empty;
            return null;
        }

        private IList<string> FindSceneConsequenceKindsLocked(string playerKey, string questId)
        {
            List<string> consequences = new();
            if (string.IsNullOrWhiteSpace(playerKey) ||
                string.IsNullOrWhiteSpace(questId) ||
                !m_playerTimeline.TryGetValue(playerKey, out List<DynamicQuestTimelineEvent> timeline))
            {
                return consequences;
            }

            foreach (DynamicQuestTimelineEvent evt in timeline)
            {
                if (!string.Equals(evt?.QuestId, questId, StringComparison.OrdinalIgnoreCase) ||
                    !string.Equals(evt.EventType, "scene_consequence", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                string kind = ExtractSceneDetailToken(evt.Detail, "consequence");
                if (!string.IsNullOrWhiteSpace(kind) &&
                    !consequences.Contains(kind, StringComparer.OrdinalIgnoreCase))
                {
                    consequences.Add(kind);
                }
            }

            return consequences;
        }

        private static string ExtractSceneDetailToken(string detail, string key)
        {
            if (string.IsNullOrWhiteSpace(detail) || string.IsNullOrWhiteSpace(key))
                return string.Empty;

            string marker = $":{key}:";
            int start = detail.IndexOf(marker, StringComparison.OrdinalIgnoreCase);
            if (start < 0)
                return string.Empty;

            start += marker.Length;
            int end = detail.IndexOf(':', start);
            string token = end < 0 ? detail.Substring(start) : detail.Substring(start, end - start);
            return token.Trim();
        }

        private static IList<string> BuildWorldImpactSignals(
            DynamicQuestDefinition quest,
            DynamicQuestProgress progress,
            ushort regionId,
            string selectedChoiceId,
            IEnumerable<string> sceneConsequences)
        {
            List<string> signals = new()
            {
                "dynamic-quest:completed",
                $"dynamic-quest:completed:region:{regionId}",
                $"region-stabilized:{regionId}"
            };

            foreach (string tag in quest?.Tags ?? Array.Empty<string>())
            {
                string value = (tag ?? string.Empty).Trim();
                if (value.StartsWith("world-signal:", StringComparison.OrdinalIgnoreCase))
                    AddUniqueSignal(signals, value);
                else if (value.StartsWith("branch:", StringComparison.OrdinalIgnoreCase))
                    AddUniqueSignal(signals, value);
            }

            foreach (string nodeId in progress?.CompletedNodeIds ?? new HashSet<string>(StringComparer.OrdinalIgnoreCase))
            {
                if (string.Equals(nodeId, "observe_signal", StringComparison.OrdinalIgnoreCase))
                    AddUniqueSignal(signals, "followup-observed");
            }

            if (string.Equals(selectedChoiceId, "followup", StringComparison.OrdinalIgnoreCase))
                AddUniqueSignal(signals, "followup-observed");

            if (!string.IsNullOrWhiteSpace(selectedChoiceId))
                AddUniqueSignal(signals, $"choice:{selectedChoiceId.Trim()}");

            foreach (string sceneConsequence in sceneConsequences ?? Array.Empty<string>())
            {
                if (!string.IsNullOrWhiteSpace(sceneConsequence))
                    AddUniqueSignal(signals, $"scene-consequence:{sceneConsequence.Trim()}");
            }

            return signals;
        }

        private static void AddUniqueSignal(ICollection<string> signals, string value)
        {
            value = (value ?? string.Empty).Trim();
            if (signals == null || string.IsNullOrWhiteSpace(value))
                return;

            if (!signals.Any(signal => string.Equals(signal, value, StringComparison.OrdinalIgnoreCase)))
                signals.Add(value);
        }

        private static string ResolveWorldImpactType(string selectedChoiceId, IEnumerable<string> signals)
        {
            if (string.Equals(selectedChoiceId, "followup", StringComparison.OrdinalIgnoreCase))
                return "thread_uncovered";
            if ((signals ?? Array.Empty<string>()).Any(signal => signal.Contains("item-acquired", StringComparison.OrdinalIgnoreCase)))
                return "clue_confirmed";
            return "region_stabilized";
        }

        private static string BuildWorldImpactTimelineDetail(
            ushort regionId,
            string selectedChoiceId,
            string impactType,
            IEnumerable<string> signals)
        {
            string choice = string.IsNullOrWhiteSpace(selectedChoiceId) ? "none" : SafeSceneBeatToken(selectedChoiceId);
            string impact = string.IsNullOrWhiteSpace(impactType) ? "region_stabilized" : SafeSceneBeatToken(impactType);
            int signalCount = (signals ?? Array.Empty<string>())
                .Where(signal => !string.IsNullOrWhiteSpace(signal))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .Count();

            return $"impact:{impact}|region:{regionId}|choice:{choice}|signals:{signalCount}";
        }

        private static string BuildWorldImpactSummaryText(
            DynamicQuestDefinition quest,
            DynamicQuestProgress progress,
            ushort regionId,
            string selectedChoiceId,
            string consequence,
            string impactType,
            IEnumerable<string> sceneConsequences)
        {
            string realm = ResolveQuestRealm(quest);
            string target = string.IsNullOrWhiteSpace(quest?.TargetName) ? "위협" : quest.TargetName.Trim();
            string choice = string.IsNullOrWhiteSpace(selectedChoiceId) ? "기록 없음" : selectedChoiceId.Trim();
            string impact = string.Equals(impactType, "thread_uncovered", StringComparison.OrdinalIgnoreCase)
                ? "남은 단서가 더 큰 사건의 실마리로 기록됐다"
                : string.Equals(impactType, "clue_confirmed", StringComparison.OrdinalIgnoreCase)
                    ? "확보한 단서가 지역 기록에 묶였다"
                    : "지역의 즉각적인 위협이 낮아졌다";
            string consequenceText = string.IsNullOrWhiteSpace(consequence)
                ? "선택의 세부 결과는 현장 기록에 남지 않았다."
                : consequence.Trim();
            string sceneConsequenceText = BuildSceneConsequenceSummaryText(sceneConsequences);

            return string.IsNullOrWhiteSpace(sceneConsequenceText)
                ? $"{realm} 지역 {regionId}: {target} 사건 이후 {impact}. 선택={choice}. {consequenceText}"
                : $"{realm} 지역 {regionId}: {target} 사건 이후 {impact}. 선택={choice}. {consequenceText} 현장 여파={sceneConsequenceText}.";
        }

        private static string BuildSceneConsequenceSummaryText(IEnumerable<string> sceneConsequences)
        {
            List<string> labels = (sceneConsequences ?? Array.Empty<string>())
                .Where(value => !string.IsNullOrWhiteSpace(value))
                .Select(SceneConsequenceLabel)
                .Where(value => !string.IsNullOrWhiteSpace(value))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .Take(4)
                .ToList();

            return labels.Count == 0 ? string.Empty : string.Join(", ", labels);
        }

        private static string SceneConsequenceLabel(string kind)
        {
            switch ((kind ?? string.Empty).Trim().ToLowerInvariant())
            {
                case "escape_route_closed":
                    return "탈출로가 닫힘";
                case "ritual_fails":
                    return "의식이 끊김";
                case "breach_opens":
                    return "방어선에 균열 발생";
                case "threat_checked":
                    return "위협 돌파가 저지됨";
                case "defense_stabilized":
                    return "방어선이 안정됨";
                case "pressure_mounts":
                    return "현장 압박 고조";
                case "balance_changes":
                    return "전세 변화";
                default:
                    return kind?.Trim() ?? string.Empty;
            }
        }

        private static DynamicQuestWorldImpactRecord CloneWorldImpactRecord(DynamicQuestWorldImpactRecord record)
        {
            if (record == null)
                return new DynamicQuestWorldImpactRecord();

            return new DynamicQuestWorldImpactRecord
            {
                At = record.At,
                QuestId = record.QuestId,
                Title = record.Title,
                PlayerName = record.PlayerName,
                Realm = record.Realm,
                RegionId = record.RegionId,
                TargetName = record.TargetName,
                ImpactType = record.ImpactType,
                ChoiceId = record.ChoiceId,
                ChoiceConsequence = record.ChoiceConsequence,
                Summary = record.Summary,
                Signals = (record.Signals ?? Array.Empty<string>()).ToList()
            };
        }

        private static ushort ResolveQuestImpactRegion(DynamicQuestDefinition quest)
        {
            if (quest == null)
                return 0;

            if (quest.StartRegionId > 0)
                return quest.StartRegionId;

            foreach (DynamicQuestNode node in quest.Nodes ?? Array.Empty<DynamicQuestNode>())
            {
                ushort regionId = node?.Objective?.RegionId ?? 0;
                if (regionId > 0)
                    return regionId;
            }

            return 0;
        }

        private static bool IsInsideAutoAcceptStartScope(DynamicQuestDefinition quest, ushort regionId, int x, int y)
        {
            DynamicQuestDefinition normalized = NormalizeQuest(quest);
            if (normalized == null || normalized.StartMode != DynamicQuestStartMode.AutoAccept)
                return false;

            foreach (DynamicQuestObjective objective in EnumerateAutoAcceptStartObjectives(normalized))
            {
                if (objective == null)
                    continue;
                if (objective.RegionId != 0 && objective.RegionId != regionId)
                    continue;
                if (IsInsideExploreObjective(objective, x, y))
                    return true;
            }

            return false;
        }

        private static IEnumerable<DynamicQuestObjective> EnumerateAutoAcceptStartObjectives(DynamicQuestDefinition quest)
        {
            DynamicQuestNode startNode = (quest.Nodes ?? Array.Empty<DynamicQuestNode>())
                .FirstOrDefault(node => string.Equals(node.Id, quest.StartNodeId, StringComparison.OrdinalIgnoreCase));

            if (startNode?.Type == DynamicQuestNodeType.Explore)
                yield return startNode.Objective;

            foreach (DynamicQuestNode node in quest.Nodes ?? Array.Empty<DynamicQuestNode>())
            {
                if (ReferenceEquals(node, startNode) || node?.Type != DynamicQuestNodeType.Explore)
                    continue;

                yield return node.Objective;
            }
        }

        private static bool NameMatches(string actualName, string expectedName)
        {
            string actual = (actualName ?? string.Empty).Trim();
            string expected = (expectedName ?? string.Empty).Trim();

            if (string.IsNullOrWhiteSpace(actual) || string.IsNullOrWhiteSpace(expected))
                return false;

            if (string.Equals(actual, expected, StringComparison.OrdinalIgnoreCase))
                return true;

            return string.Equals(StripMobGrowthNamePrefixes(actual), expected, StringComparison.OrdinalIgnoreCase);
        }

        private static string StripMobGrowthNamePrefixes(string name)
        {
            string normalized = (name ?? string.Empty).Trim();
            string[] prefixes =
            {
                "돌연변이 ",
                "노련한 ",
                "흉포한 ",
                "우두머리 "
            };

            bool stripped;
            do
            {
                stripped = false;
                foreach (string prefix in prefixes)
                {
                    if (!normalized.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                        continue;

                    normalized = normalized.Substring(prefix.Length).TrimStart();
                    stripped = true;
                    break;
                }
            }
            while (stripped);

            return normalized;
        }

        private static string GetPlayerKey(GamePlayer player)
        {
            return !string.IsNullOrWhiteSpace(player.InternalID) ? player.InternalID : player.Name;
        }

        private static IEnumerable<GamePlayer> GetKillCreditPlayers(GamePlayer player, GameLiving enemy)
        {
            if (player == null)
                yield break;

            HashSet<string> seenPlayerKeys = new(StringComparer.OrdinalIgnoreCase);
            string playerKey = GetPlayerKey(player);
            if (!string.IsNullOrWhiteSpace(playerKey) && seenPlayerKeys.Add(playerKey))
                yield return player;

            if (player.Group != null)
            {
                foreach (GamePlayer member in player.Group.GetPlayersInTheGroup())
                {
                    if (member == null)
                        continue;

                    string memberKey = GetPlayerKey(member);
                    if (string.IsNullOrWhiteSpace(memberKey) || !seenPlayerKeys.Add(memberKey))
                        continue;

                    yield return member;
                }
            }

            if (enemy == null)
                yield break;

            foreach (GamePlayer nearbyPlayer in enemy.GetPlayersInRadius(WorldMgr.MAX_EXPFORKILL_DISTANCE))
            {
                if (nearbyPlayer == null)
                    continue;

                string nearbyPlayerKey = GetPlayerKey(nearbyPlayer);
                if (string.IsNullOrWhiteSpace(nearbyPlayerKey) || !seenPlayerKeys.Add(nearbyPlayerKey))
                    continue;

                yield return nearbyPlayer;
            }
        }

        private static IEnumerable<GamePlayer> GetItemAcquiredSignalCreditPlayers(GamePlayer player)
        {
            if (player == null)
                yield break;

            HashSet<string> seenPlayerKeys = new(StringComparer.OrdinalIgnoreCase);
            string playerKey = GetPlayerKey(player);
            if (!string.IsNullOrWhiteSpace(playerKey) && seenPlayerKeys.Add(playerKey))
                yield return player;

            if (player.Group != null)
            {
                foreach (GamePlayer member in player.Group.GetPlayersInTheGroup())
                {
                    if (!CanShareItemAcquiredSignal(player, member))
                        continue;

                    string memberKey = GetPlayerKey(member);
                    if (string.IsNullOrWhiteSpace(memberKey) || !seenPlayerKeys.Add(memberKey))
                        continue;

                    yield return member;
                }
            }

            foreach (GamePlayer nearbyPlayer in player.GetPlayersInRadius(WorldMgr.MAX_EXPFORKILL_DISTANCE))
            {
                if (!CanShareItemAcquiredSignal(player, nearbyPlayer))
                    continue;

                string nearbyPlayerKey = GetPlayerKey(nearbyPlayer);
                if (string.IsNullOrWhiteSpace(nearbyPlayerKey) || !seenPlayerKeys.Add(nearbyPlayerKey))
                    continue;

                yield return nearbyPlayer;
            }
        }

        private static bool CanShareItemAcquiredSignal(GamePlayer source, GamePlayer member)
        {
            if (source == null || member == null || ReferenceEquals(source, member))
                return false;

            if (source.Realm != 0 && member.Realm != 0 && source.Realm != member.Realm)
                return false;

            if (source.CurrentRegionID != 0 && member.CurrentRegionID != 0 && source.CurrentRegionID != member.CurrentRegionID)
                return false;

            return true;
        }

        private void NotifyKillProgress(GamePlayer player, DynamicQuestDefinition quest)
        {
            DynamicQuestProgressSnapshot snapshot = GetProgressSnapshot(player);
            DynamicQuestProgressItem item = snapshot.Active.FirstOrDefault(active => active.QuestId == quest.Id);
            if (item == null)
            {
                if (!RequiresStartNpc(quest))
                    player.Out.SendMessage($"{quest.Title}: {quest.FinishText}", eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                return;
            }

            if (item.IsComplete || item.CurrentNodeType == DynamicQuestNodeType.ReturnToNpc)
            {
                string returnNpcName = string.IsNullOrWhiteSpace(item.CurrentObjective?.NpcName) ? quest.StartNpcName : item.CurrentObjective.NpcName;
                player.Out.SendMessage($"{quest.Title}: 완료되었습니다. {returnNpcName}에게 돌아가세요.", eChatType.CT_Important, eChatLoc.CL_SystemWindow);
            }
            else
            {
                player.Out.SendMessage($"{quest.Title}: {DescribeCurrentObjective(item)}", eChatType.CT_System, eChatLoc.CL_SystemWindow);
            }
        }

        private static string DescribeCurrentObjective(DynamicQuestProgressItem item)
        {
            if (item.CurrentNodeType == DynamicQuestNodeType.Kill)
                return $"{item.Count}/{Math.Max(1, item.CurrentObjective.TargetCount)}";

            if (item.CurrentNodeType == DynamicQuestNodeType.Explore)
                return string.IsNullOrWhiteSpace(item.CurrentObjective?.LocationName)
                    ? item.CurrentNodeId
                    : item.CurrentObjective.LocationName;

            if (!string.IsNullOrWhiteSpace(item.CurrentObjective?.NpcName))
                return item.CurrentObjective.NpcName;

            return item.CurrentNodeId;
        }

        private static string BuildJournalDescription(DynamicQuestDefinition quest, DynamicQuestProgressItem item)
        {
            if (item == null)
                return FirstNonEmpty(quest?.ProgressText, "동적 퀘스트 진행 중입니다.");

            List<string> lines = new();
            DynamicQuestObjective objective = item.CurrentObjective ?? new DynamicQuestObjective();
            string targetName = FirstNonEmpty(objective.TargetName, item.TargetName, quest?.TargetName, "대상");
            int targetCount = Math.Max(1, objective.TargetCount > 0 ? objective.TargetCount : Math.Max(item.TargetCount, quest?.TargetCount ?? 1));
            string npcName = FirstNonEmpty(objective.NpcName, item.StartNpcName, quest?.StartNpcName, "의뢰인");
            string locationName = FirstNonEmpty(objective.LocationName, item.CurrentNodeId, "목표 위치");

            if (item.IsComplete || item.CurrentNodeType == DynamicQuestNodeType.ReturnToNpc)
            {
                lines.Add("목표: 완료 보고");
                lines.Add($"힌트: {npcName}에게 돌아가세요.");
                return string.Join(Environment.NewLine, lines);
            }

            switch (item.CurrentNodeType)
            {
                case DynamicQuestNodeType.Kill:
                    lines.Add($"목표: {targetName} 처치");
                    lines.Add($"진행: {Math.Max(0, item.Count)}/{targetCount}");
                    lines.Add("힌트: 이 동적 퀘스트가 시작된 지역 안에서 대상 몬스터를 찾으세요.");
                    break;
                case DynamicQuestNodeType.Explore:
                    lines.Add($"목표: {locationName} 조사");
                    lines.Add("힌트: 퀘스트 지역 안에서 해당 위치로 이동하세요.");
                    break;
                case DynamicQuestNodeType.Talk:
                    lines.Add($"목표: {npcName}와 대화");
                    lines.Add($"힌트: {npcName}를 찾아 대화하세요.");
                    break;
                case DynamicQuestNodeType.Choice:
                    lines.Add("목표: 결정을 내려야 합니다.");
                    lines.Add("힌트: 대화 선택지를 확인하세요.");
                    break;
                case DynamicQuestNodeType.Complete:
                    lines.Add("목표: 완료");
                    lines.Add("힌트: 퀘스트가 완료되었습니다.");
                    break;
                default:
                    lines.Add($"목표: {DescribeCurrentObjective(item)}");
                    lines.Add("힌트: 현재 동적 퀘스트 목표를 진행하세요.");
                    break;
            }

            string progressText = quest?.ProgressText?.Trim() ?? string.Empty;
            if (!string.IsNullOrWhiteSpace(progressText))
                lines.Add($"내용: {progressText}");

            return string.Join(Environment.NewLine, lines);
        }

        private static string FirstNonEmpty(params string[] values)
        {
            if (values == null)
                return string.Empty;

            foreach (string value in values)
            {
                if (!string.IsNullOrWhiteSpace(value))
                    return value.Trim();
            }

            return string.Empty;
        }

        private static int GetPlayerPartySize(GamePlayer player)
        {
            return Math.Max(1, (int)(player?.Group?.MemberCount ?? 1));
        }

        private static bool IsInsideExploreObjective(DynamicQuestObjective objective, int x, int y)
        {
            if (objective == null || objective.Radius <= 0)
                return false;

            long dx = (long)x - objective.X;
            long dy = (long)y - objective.Y;
            long radius = objective.Radius;
            return dx * dx + dy * dy <= radius * radius;
        }

        private static bool IsNpcObjective(DynamicQuestNode node, GameNPC npc)
        {
            DynamicQuestObjective objective = node?.Objective;
            return objective != null &&
                   (objective.RegionId == 0 || objective.RegionId == npc.CurrentRegionID) &&
                   string.Equals(objective.NpcInternalId, npc.InternalID ?? string.Empty, StringComparison.OrdinalIgnoreCase);
        }

        private static DynamicQuestNode GetCurrentNode(DynamicQuestDefinition quest, DynamicQuestProgress progress)
        {
            string nodeId = string.IsNullOrWhiteSpace(progress.CurrentNodeId) ? quest.StartNodeId : progress.CurrentNodeId;
            return (quest.Nodes ?? Array.Empty<DynamicQuestNode>())
                .FirstOrDefault(node => string.Equals(node.Id, nodeId, StringComparison.OrdinalIgnoreCase));
        }

        private bool HasProgress(string playerKey, string questId)
        {
            if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                return false;

            return progressList.Any(progress => string.Equals(progress.QuestId, questId, StringComparison.OrdinalIgnoreCase));
        }

        private bool IsProgressCountingAgainstActiveLimit(DynamicQuestProgress progress)
        {
            if (progress == null || progress.Failed || !TryGetQuestForProgress(progress, out DynamicQuestDefinition quest))
                return false;

            return !ShouldHideProgressFromActiveSnapshot(NormalizeQuest(quest), progress);
        }

        private static bool ShouldHideProgressFromActiveSnapshot(DynamicQuestDefinition quest, DynamicQuestProgress progress)
        {
            if (progress == null || progress.Failed)
                return true;

            if (!progress.Completed && !progress.IsComplete)
                return false;

            return !RequiresStartNpc(quest);
        }

        private bool HasCompletedQuest(string playerKey, string questId)
        {
            return m_playerCompletedQuestIds.TryGetValue(playerKey, out HashSet<string> completedQuestIds) &&
                   completedQuestIds.Contains(questId);
        }

        private bool HasCompletedStoryFamily(string playerKey, DynamicQuestDefinition quest)
        {
            string storyFamilyId = ExtractStoryFamilyId(quest);
            return !string.IsNullOrWhiteSpace(storyFamilyId) &&
                   m_playerCompletedStoryFamilyIds.TryGetValue((playerKey ?? string.Empty).Trim(), out HashSet<string> completedStoryFamilyIds) &&
                   completedStoryFamilyIds.Contains(storyFamilyId);
        }

        private bool HasActiveStoryFamily(string playerKey, DynamicQuestDefinition quest)
        {
            string storyFamilyId = ExtractStoryFamilyId(quest);
            playerKey = (playerKey ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(playerKey) || string.IsNullOrWhiteSpace(storyFamilyId))
                return false;

            if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                return false;

            return progressList.Any(progress =>
            {
                if (!IsProgressCountingAgainstActiveLimit(progress) ||
                    string.Equals(progress.QuestId, quest?.Id, StringComparison.OrdinalIgnoreCase) ||
                    !TryGetQuestForProgress(progress, out DynamicQuestDefinition activeQuest))
                {
                    return false;
                }

                return string.Equals(ExtractStoryFamilyId(activeQuest), storyFamilyId, StringComparison.OrdinalIgnoreCase);
            });
        }

        private List<string> BuildAutoAcceptOfferBlockReasons(
            string playerKey,
            DynamicQuestDefinition quest,
            int playerLevel,
            ushort regionId,
            int x,
            int y,
            string trigger)
        {
            List<string> reasons = new();
            if (!QuestTriggerMatches(quest, trigger))
                reasons.Add("trigger_mismatch");
            if (!PlayerLevelMatchesQuest(quest, playerLevel))
                reasons.Add("player_level_mismatch");
            if (HasCompletedQuest(playerKey, quest?.Id))
                reasons.Add("completed_quest");
            if (HasCompletedStoryFamily(playerKey, quest))
                reasons.Add("completed_story_family");
            if (!HasStoryPrerequisites(playerKey, quest))
                reasons.Add("missing_story_prerequisite");
            if (HasProgress(playerKey, quest?.Id))
                reasons.Add("active_quest");
            if (HasActiveStoryFamily(playerKey, quest))
                reasons.Add("active_story_family");
            if (!IsInsideAutoAcceptStartScope(quest, regionId, x, y))
                reasons.Add("outside_start_scope");
            return reasons;
        }

        private void MarkQuestCompleted(GamePlayer player, string questId)
        {
            string playerKey = GetPlayerKey(player);
            lock (m_lock)
                MarkQuestCompletedLocked(playerKey, questId);
        }

        private void MarkQuestCompletedLocked(string playerKey, string questId)
        {
            playerKey = (playerKey ?? string.Empty).Trim();
            questId = (questId ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(playerKey) || string.IsNullOrWhiteSpace(questId))
                return;

            if (!m_playerCompletedQuestIds.TryGetValue(playerKey, out HashSet<string> completedQuestIds))
            {
                completedQuestIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                m_playerCompletedQuestIds[playerKey] = completedQuestIds;
            }

            completedQuestIds.Add(questId);
        }

        private void MarkStoryFamilyCompletedLocked(string playerKey, DynamicQuestDefinition quest)
        {
            playerKey = (playerKey ?? string.Empty).Trim();
            string storyFamilyId = ExtractStoryFamilyId(quest);
            if (string.IsNullOrWhiteSpace(playerKey) || string.IsNullOrWhiteSpace(storyFamilyId))
                return;

            if (!m_playerCompletedStoryFamilyIds.TryGetValue(playerKey, out HashSet<string> completedStoryFamilyIds))
            {
                completedStoryFamilyIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                m_playerCompletedStoryFamilyIds[playerKey] = completedStoryFamilyIds;
            }

            completedStoryFamilyIds.Add(storyFamilyId);
        }

        private static string ExtractStoryFamilyId(DynamicQuestDefinition quest)
        {
            string prefix = "story-family:";
            string tag = (quest?.Tags ?? Array.Empty<string>())
                .FirstOrDefault(value => (value ?? string.Empty).Trim().StartsWith(prefix, StringComparison.OrdinalIgnoreCase));
            return string.IsNullOrWhiteSpace(tag)
                ? string.Empty
                : tag.Trim().Substring(prefix.Length).Trim();
        }

        private bool HasStoryPrerequisites(string playerKey, DynamicQuestDefinition quest)
        {
            IList<string> requiredSignals = BuildStoryPrerequisiteSignals(quest);
            if (requiredSignals.Count == 0)
                return true;

            playerKey = (playerKey ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(playerKey) ||
                !m_playerWorldMemorySignals.TryGetValue(playerKey, out HashSet<string> signals))
            {
                return false;
            }

            return requiredSignals.All(signal => signals.Contains(signal));
        }

        private static IList<string> BuildStoryPrerequisiteSignals(DynamicQuestDefinition quest)
        {
            List<string> required = new();
            foreach (string tag in quest?.Tags ?? Array.Empty<string>())
            {
                string value = (tag ?? string.Empty).Trim();
                if (value.StartsWith("requires-memory:", StringComparison.OrdinalIgnoreCase))
                    AddUniqueSignal(required, value.Substring("requires-memory:".Length));
                else if (value.StartsWith("requires-story-family:", StringComparison.OrdinalIgnoreCase))
                    AddUniqueSignal(required, $"story-family:{value.Substring("requires-story-family:".Length).Trim()}:completed");
                else if (value.StartsWith("requires-story-archetype:", StringComparison.OrdinalIgnoreCase))
                    AddUniqueSignal(required, $"story-archetype:{value.Substring("requires-story-archetype:".Length).Trim()}:completed");
                else if (value.StartsWith("requires-choice:", StringComparison.OrdinalIgnoreCase))
                    AddUniqueSignal(required, $"choice:{value.Substring("requires-choice:".Length).Trim()}");
            }

            return required
                .Where(signal => !string.IsNullOrWhiteSpace(signal))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();
        }

        private void MarkWorldMemoryLocked(
            string playerKey,
            DynamicQuestDefinition quest,
            DynamicQuestProgress progress = null,
            bool recordTimeline = true)
        {
            playerKey = (playerKey ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(playerKey) || quest == null)
                return;

            if (!m_playerWorldMemorySignals.TryGetValue(playerKey, out HashSet<string> signals))
            {
                signals = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                m_playerWorldMemorySignals[playerKey] = signals;
            }

            int before = signals.Count;
            AddUniqueSignal(signals, $"quest:{quest.Id}:completed");
            string storyFamilyId = ExtractStoryFamilyId(quest);
            if (!string.IsNullOrWhiteSpace(storyFamilyId))
                AddUniqueSignal(signals, $"story-family:{storyFamilyId}:completed");

            foreach (string tag in quest.Tags ?? Array.Empty<string>())
            {
                string value = (tag ?? string.Empty).Trim();
                if (value.StartsWith("story-archetype:", StringComparison.OrdinalIgnoreCase))
                    AddUniqueSignal(signals, $"story-archetype:{value.Substring("story-archetype:".Length).Trim()}:completed");
                else if (value.StartsWith("story-chain:", StringComparison.OrdinalIgnoreCase))
                    AddUniqueSignal(signals, $"story-chain:{value.Substring("story-chain:".Length).Trim()}:progress");
                else if (value.StartsWith("world-signal:", StringComparison.OrdinalIgnoreCase))
                    AddUniqueSignal(signals, $"world-signal:{value.Substring("world-signal:".Length).Trim()}:completed");
                else if (value.StartsWith("branch:", StringComparison.OrdinalIgnoreCase))
                    AddUniqueSignal(signals, $"branch:{value.Substring("branch:".Length).Trim()}:completed");
            }

            foreach (KeyValuePair<string, string> choice in progress?.ChoiceHistory ?? new Dictionary<string, string>())
            {
                if (string.IsNullOrWhiteSpace(choice.Value))
                    continue;

                AddUniqueSignal(signals, $"choice:{choice.Value.Trim()}");
                if (!string.IsNullOrWhiteSpace(choice.Key))
                    AddUniqueSignal(signals, $"choice:{choice.Key.Trim()}:{choice.Value.Trim()}");
                if (string.Equals(choice.Value, "followup", StringComparison.OrdinalIgnoreCase))
                    AddUniqueSignal(signals, "followup-observed");
            }

            int added = signals.Count - before;
            if (recordTimeline && added > 0)
            {
                RecordTimelineEventLocked(
                    playerKey,
                    string.Empty,
                    quest.Id,
                    "world_memory_marked",
                    nodeId: progress?.CurrentNodeId ?? string.Empty,
                    detail: $"signals:{signals.Count}:added:{added}",
                    count: signals.Count);
            }
        }

        private void EnsurePlayerProgressLoaded(string playerKey, string playerName)
        {
            playerKey = (playerKey ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(playerKey))
                return;

            lock (m_lock)
            {
                if (!m_loadedPlayerKeys.Add(playerKey))
                    return;
            }

            IList<DbDynamicQuestProgress> rows = m_progressRepository.GetByPlayer(playerKey) ?? Array.Empty<DbDynamicQuestProgress>();

            lock (m_lock)
            {
                if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                {
                    progressList = new List<DynamicQuestProgress>();
                    m_playerProgress[playerKey] = progressList;
                }

                foreach (DbDynamicQuestProgress row in rows)
                {
                    if (row == null || string.IsNullOrWhiteSpace(row.QuestId))
                        continue;

                    if (row.Completed || row.IsComplete)
                    {
                        if (!m_playerCompletedQuestIds.TryGetValue(playerKey, out HashSet<string> completedQuestIds))
                        {
                            completedQuestIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                            m_playerCompletedQuestIds[playerKey] = completedQuestIds;
                        }

                        completedQuestIds.Add(row.QuestId);

                        DynamicQuestDefinition completedQuest = DeserializeQuestSnapshot(row.QuestSnapshotJson);
                        if (completedQuest == null && m_quests.TryGetValue(row.QuestId, out DynamicQuestDefinition runtimeQuest))
                            completedQuest = runtimeQuest;
                        MarkStoryFamilyCompletedLocked(playerKey, completedQuest);
                        MarkWorldMemoryLocked(playerKey, completedQuest, FromRow(row), recordTimeline: false);
                    }

                    if (!row.IsActive || row.Failed)
                        continue;

                    if (TryGetProgressReloadCancelReason(row, out string cancelReason))
                    {
                        CancelRepositoryProgressRow(row, cancelReason);
                        continue;
                    }

                    if (progressList.Any(progress => string.Equals(progress.QuestId, row.QuestId, StringComparison.OrdinalIgnoreCase)))
                        continue;

                    progressList.Add(FromRow(row));
                }
            }
        }

        private bool TryGetProgressReloadCancelReason(DbDynamicQuestProgress row, out string reason)
        {
            reason = string.Empty;
            if (row == null || string.IsNullOrWhiteSpace(row.QuestId))
                return false;

            m_quests.TryGetValue(row.QuestId, out DynamicQuestDefinition quest);
            quest ??= DeserializeQuestSnapshot(row.QuestSnapshotJson);

            if (HasChangedToken(row.WorldRevision, NormalizeRuntimeWorldRevision(Properties.KDAOC_DYNAMIC_QUEST_WORLD_REVISION)))
            {
                reason = "world_revision_changed";
                return true;
            }

            if (quest != null && HasChangedToken(row.WorldRevision, quest.WorldRevision))
            {
                reason = "world_revision_changed";
                return true;
            }

            if (m_cancelMissingRuntimeProgressOnLoad && !m_quests.ContainsKey(row.QuestId))
            {
                reason = "runtime_offer_removed";
                return true;
            }

            return false;
        }

        private static string NormalizeRuntimeWorldRevision(string worldRevision)
        {
            return (worldRevision ?? string.Empty).Trim();
        }

        private static bool QuestMatchesTemplate(DynamicQuestDefinition quest, string templateId)
        {
            templateId = (templateId ?? string.Empty).Trim();
            if (quest == null || string.IsNullOrWhiteSpace(templateId))
                return false;

            return string.Equals(quest.Id, templateId, StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(ExtractTemplateId(quest), templateId, StringComparison.OrdinalIgnoreCase);
        }

        private static string ExtractTemplateId(DynamicQuestDefinition quest)
        {
            if (quest?.Tags == null)
                return string.Empty;

            foreach (string tag in quest.Tags)
            {
                string value = (tag ?? string.Empty).Trim();
                if (!value.StartsWith("template:", StringComparison.OrdinalIgnoreCase))
                    continue;

                return value.Substring("template:".Length).Trim();
            }

            return string.Empty;
        }

        private void CancelRepositoryProgressRow(DbDynamicQuestProgress row, string reason)
        {
            if (row == null)
                return;

            string cancelReason = string.IsNullOrWhiteSpace(reason) ? "progress_stale" : reason.Trim();
            row.Failed = true;
            row.CancelReason = cancelReason;
            row.IsActive = false;
            row.UpdatedAt = DateTime.UtcNow;
            m_progressRepository.Save(row);
            RecordTimelineEventLocked(row.PlayerKey, row.PlayerName, row.QuestId, "quest_cancelled", nodeId: row.CurrentNodeId, detail: cancelReason);
        }

        private static bool HasChangedToken(string previous, string current)
        {
            previous = (previous ?? string.Empty).Trim();
            current = (current ?? string.Empty).Trim();
            return !string.IsNullOrWhiteSpace(previous) &&
                   !string.IsNullOrWhiteSpace(current) &&
                   !string.Equals(previous, current, StringComparison.OrdinalIgnoreCase);
        }

        private void SaveProgress(string playerKey, string playerName, DynamicQuestProgress progress)
        {
            playerKey = (playerKey ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(playerKey) || progress == null || string.IsNullOrWhiteSpace(progress.QuestId))
                return;

            progress.UpdatedAt = DateTime.UtcNow;
            string progressId = BuildProgressId(playerKey, progress.QuestId);
            DbDynamicQuestProgress row = m_progressRepository.Find(progressId);
            bool isNew = row == null;
            row ??= new DbDynamicQuestProgress
            {
                ProgressId = progressId,
                CreatedAt = DateTime.UtcNow
            };

            string normalizedPlayerName = (playerName ?? string.Empty).Trim();
            row.PlayerKey = playerKey;
            if (!string.IsNullOrWhiteSpace(normalizedPlayerName) || isNew || string.IsNullOrWhiteSpace(row.PlayerName))
                row.PlayerName = normalizedPlayerName;
            row.QuestId = progress.QuestId;
            row.Count = progress.Count;
            row.IsComplete = progress.IsComplete;
            row.CurrentNodeId = progress.CurrentNodeId ?? string.Empty;
            row.NodeCountersJson = SerializeNodeCounters(progress.NodeCounters, progress.PendingWorldSignals);
            row.CompletedNodeIdsJson = SerializeCompletedNodeIds(progress.CompletedNodeIds);
            row.ChoiceHistoryJson = SerializeChoiceHistory(progress.ChoiceHistory);
            if (progress.QuestSnapshot == null && TryGetQuest(progress.QuestId, out DynamicQuestDefinition quest))
                progress.QuestSnapshot = CloneQuestSnapshot(NormalizeQuest(quest));
            row.QuestSnapshotJson = SerializeQuestSnapshot(progress.QuestSnapshot);
            row.BindingKey = progress.BindingKey ?? string.Empty;
            row.WorldRevision = progress.WorldRevision ?? string.Empty;
            row.CancelReason = progress.CancelReason ?? string.Empty;
            row.Failed = progress.Failed;
            row.Completed = progress.Completed;
            row.IsActive = ShouldKeepProgressActiveInRepository(playerKey, progress);
            row.AcceptedAt = progress.AcceptedAt;
            row.UpdatedAt = progress.UpdatedAt;
            if (isNew)
                m_progressRepository.Add(row);
            else
                m_progressRepository.Save(row);
        }

        private bool ShouldKeepProgressActiveInRepository(string playerKey, DynamicQuestProgress progress)
        {
            if (progress == null || progress.Failed)
                return false;

            if (!progress.Completed && !progress.IsComplete)
                return true;

            if (!TryGetQuestForProgress(progress, out DynamicQuestDefinition quest))
                return false;

            return RequiresStartNpc(NormalizeQuest(quest)) &&
                   !HasQuestRewardedTimelineEventLocked(playerKey, progress.QuestId);
        }

        private static DynamicQuestProgress FromRow(DbDynamicQuestProgress row)
        {
            return new DynamicQuestProgress
            {
                QuestId = row.QuestId,
                Count = row.Count,
                IsComplete = row.IsComplete,
                AcceptedAt = row.AcceptedAt,
                CurrentNodeId = row.CurrentNodeId,
                NodeCounters = DeserializeNodeCounters(row.NodeCountersJson),
                CompletedNodeIds = DeserializeCompletedNodeIds(row.CompletedNodeIdsJson),
                ChoiceHistory = DeserializeChoiceHistory(row.ChoiceHistoryJson),
                PendingWorldSignals = DeserializePendingWorldSignals(row.NodeCountersJson),
                QuestSnapshot = DeserializeQuestSnapshot(row.QuestSnapshotJson),
                BindingKey = row.BindingKey ?? string.Empty,
                WorldRevision = row.WorldRevision ?? string.Empty,
                CancelReason = row.CancelReason ?? string.Empty,
                Failed = row.Failed,
                Completed = row.Completed,
                UpdatedAt = row.UpdatedAt
            };
        }

        private static string BuildProgressId(string playerKey, string questId)
        {
            return $"{(playerKey ?? string.Empty).Trim().ToLowerInvariant()}:{(questId ?? string.Empty).Trim().ToLowerInvariant()}";
        }

        public static string BuildJournalProgressId(string playerKey, string questId)
        {
            return BuildProgressId(playerKey, questId);
        }

        private static string SerializeNodeCounters(Dictionary<string, int> counters, HashSet<string> pendingWorldSignals = null)
        {
            Dictionary<string, int> result = new(counters ?? new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase), StringComparer.OrdinalIgnoreCase);
            foreach (string key in result.Keys.Where(IsPendingWorldSignalCounterKey).ToList())
                result.Remove(key);

            foreach (string signal in pendingWorldSignals ?? new HashSet<string>(StringComparer.OrdinalIgnoreCase))
            {
                string normalized = NormalizePendingWorldSignal(signal);
                if (!string.IsNullOrWhiteSpace(normalized))
                    result[$"{PendingWorldSignalCounterPrefix}{normalized}"] = 1;
            }

            return JsonSerializer.Serialize(result);
        }

        private static string SerializeCompletedNodeIds(HashSet<string> completedNodeIds)
        {
            return JsonSerializer.Serialize((completedNodeIds ?? new HashSet<string>(StringComparer.OrdinalIgnoreCase))
                .OrderBy(id => id, StringComparer.OrdinalIgnoreCase)
                .ToList());
        }

        private static string SerializeChoiceHistory(Dictionary<string, string> choiceHistory)
        {
            return JsonSerializer.Serialize(choiceHistory ?? new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase));
        }

        private static string SerializeQuestSnapshot(DynamicQuestDefinition quest)
        {
            return quest == null ? string.Empty : JsonSerializer.Serialize(quest);
        }

        private static DynamicQuestDefinition CloneQuestSnapshot(DynamicQuestDefinition quest)
        {
            return DeserializeQuestSnapshot(SerializeQuestSnapshot(quest));
        }

        private static DynamicQuestDefinition DeserializeQuestSnapshot(string json)
        {
            try
            {
                return string.IsNullOrWhiteSpace(json)
                    ? null
                    : JsonSerializer.Deserialize<DynamicQuestDefinition>(json);
            }
            catch
            {
                return null;
            }
        }

        private static Dictionary<string, int> DeserializeNodeCounters(string json)
        {
            try
            {
                Dictionary<string, int> result = string.IsNullOrWhiteSpace(json)
                    ? null
                    : JsonSerializer.Deserialize<Dictionary<string, int>>(json);
                return result == null
                    ? new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase)
                    : new Dictionary<string, int>(
                        result.Where(pair => !IsPendingWorldSignalCounterKey(pair.Key))
                            .ToDictionary(pair => pair.Key, pair => pair.Value, StringComparer.OrdinalIgnoreCase),
                        StringComparer.OrdinalIgnoreCase);
            }
            catch
            {
                return new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
            }
        }

        private static HashSet<string> DeserializePendingWorldSignals(string json)
        {
            try
            {
                Dictionary<string, int> result = string.IsNullOrWhiteSpace(json)
                    ? null
                    : JsonSerializer.Deserialize<Dictionary<string, int>>(json);
                return new HashSet<string>(
                    (result ?? new Dictionary<string, int>())
                    .Keys
                    .Where(IsPendingWorldSignalCounterKey)
                    .Select(key => NormalizePendingWorldSignal(key.Substring(PendingWorldSignalCounterPrefix.Length)))
                    .Where(signal => !string.IsNullOrWhiteSpace(signal)),
                    StringComparer.OrdinalIgnoreCase);
            }
            catch
            {
                return new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            }
        }

        private static bool IsPendingWorldSignalCounterKey(string key)
        {
            return (key ?? string.Empty).StartsWith(PendingWorldSignalCounterPrefix, StringComparison.OrdinalIgnoreCase);
        }

        private static string NormalizePendingWorldSignal(string signal)
        {
            return (signal ?? string.Empty).Trim().ToLowerInvariant();
        }

        private static HashSet<string> DeserializeCompletedNodeIds(string json)
        {
            try
            {
                List<string> result = string.IsNullOrWhiteSpace(json)
                    ? null
                    : JsonSerializer.Deserialize<List<string>>(json);
                return new HashSet<string>(result ?? new List<string>(), StringComparer.OrdinalIgnoreCase);
            }
            catch
            {
                return new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            }
        }

        private static Dictionary<string, string> DeserializeChoiceHistory(string json)
        {
            try
            {
                Dictionary<string, string> result = string.IsNullOrWhiteSpace(json)
                    ? null
                    : JsonSerializer.Deserialize<Dictionary<string, string>>(json);
                return result == null
                    ? new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                    : new Dictionary<string, string>(result, StringComparer.OrdinalIgnoreCase);
            }
            catch
            {
                return new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            }
        }

        private static List<string> Validate(DynamicQuestDefinition quest)
        {
            List<string> errors = new();

            if (quest == null)
                return new List<string> { "퀘스트가 없습니다." };

            DynamicQuestDefinition normalized = NormalizeQuest(quest);
            if (string.IsNullOrWhiteSpace(normalized.Title) || normalized.Title.Length > 80)
                errors.Add("제목이 비어 있거나 너무 깁니다.");
            if (string.IsNullOrWhiteSpace(normalized.OfferText) || normalized.OfferText.Length > 500)
                errors.Add("수락 대사가 비어 있거나 너무 깁니다.");
            if (string.IsNullOrWhiteSpace(normalized.ProgressText) || normalized.ProgressText.Length > 300)
                errors.Add("진행 대사가 비어 있거나 너무 깁니다.");
            if (string.IsNullOrWhiteSpace(normalized.FinishText) || normalized.FinishText.Length > 300)
                errors.Add("완료 대사가 비어 있거나 너무 깁니다.");
            if (RequiresStartNpc(normalized) && string.IsNullOrWhiteSpace(normalized.StartNpcInternalId))
                errors.Add("시작 NPC 식별자가 없습니다.");
            if (string.IsNullOrWhiteSpace(normalized.TargetName))
                errors.Add("목표 몬스터 이름이 없습니다.");
            if (normalized.TargetCount < 1 || normalized.TargetCount > Math.Max(1, Properties.KDAOC_DYNAMIC_QUEST_MAX_KILL_COUNT))
                errors.Add("목표 처치 수가 허용 범위를 벗어났습니다.");
            if (normalized.MinLevel < 1 || normalized.MaxLevel < normalized.MinLevel || normalized.MaxLevel > 50)
                errors.Add("레벨 범위가 잘못되었습니다.");

            ValidateGraph(errors, normalized);

            return errors;
        }

        private static DynamicQuestValidationItem BuildValidationItem(DynamicQuestDefinition quest)
        {
            DynamicQuestDefinition normalized = NormalizeQuest(quest);
            List<string> errors = Validate(normalized);
            List<string> warnings = BuildValidationWarnings(normalized);
            DynamicQuestEvaluationResult rewardEstimate = DynamicQuestOperationalEvaluator.Instance.Evaluate(normalized);

            return new DynamicQuestValidationItem
            {
                QuestId = normalized?.Id ?? string.Empty,
                Title = normalized?.Title ?? string.Empty,
                Realm = normalized?.Realm ?? string.Empty,
                StartRegionId = normalized?.StartRegionId ?? 0,
                StartMode = normalized?.StartMode.ToString() ?? string.Empty,
                TargetName = normalized?.TargetName ?? string.Empty,
                BindingKey = normalized?.BindingKey ?? string.Empty,
                WorldRevision = normalized?.WorldRevision ?? string.Empty,
                Valid = errors.Count == 0,
                Errors = errors,
                Warnings = warnings,
                EstimatedPlayableSteps = rewardEstimate.EstimatedPlayableSteps,
                EstimatedMinutes = rewardEstimate.EstimatedMinutes,
                RewardDifficultyIndex = rewardEstimate.RewardDifficultyIndex,
                RewardLengthTier = rewardEstimate.RewardLengthTier,
                RewardDifficultyTier = rewardEstimate.RewardDifficultyTier,
                SuggestedRewardTier = rewardEstimate.SuggestedRewardTier,
                SuggestedRewardScale = rewardEstimate.SuggestedRewardScale
            };
        }

        private static List<string> BuildValidationWarnings(DynamicQuestDefinition quest)
        {
            List<string> warnings = new();
            if (quest?.Nodes == null)
                return warnings;

            bool hasWorldSignalEdge = quest.Nodes.Any(node =>
                (node?.Edges ?? Array.Empty<DynamicQuestEdge>())
                .Any(edge => edge?.Condition == DynamicQuestEdgeCondition.WorldSignal));
            bool hasWorldSignalTag = (quest.Tags ?? Array.Empty<string>())
                .Any(tag => (tag ?? string.Empty).StartsWith("world-signal:", StringComparison.OrdinalIgnoreCase));
            if (hasWorldSignalEdge && !hasWorldSignalTag)
                warnings.Add("world signal edge exists without world-signal tag");

            bool acceptsAnyWorldSignal = quest.Nodes.Any(node =>
                (node?.Edges ?? Array.Empty<DynamicQuestEdge>())
                .Any(edge => edge?.Condition == DynamicQuestEdgeCondition.WorldSignal &&
                             string.IsNullOrWhiteSpace(edge.ConditionValue)));
            if (acceptsAnyWorldSignal)
                warnings.Add("world signal edge accepts any signal");

            warnings.AddRange(BuildGraphReachabilityWarnings(quest));

            return warnings;
        }

        private static void ValidateGraph(List<string> errors, DynamicQuestDefinition quest)
        {
            IList<DynamicQuestNode> nodes = quest.Nodes ?? Array.Empty<DynamicQuestNode>();
            if (nodes.Count == 0)
            {
                errors.Add("graph has no nodes");
                return;
            }

            HashSet<string> nodeIds = new(StringComparer.OrdinalIgnoreCase);
            foreach (DynamicQuestNode node in nodes)
            {
                if (node == null)
                {
                    errors.Add("graph node is null");
                    continue;
                }

                if (string.IsNullOrWhiteSpace(node.Id))
                    errors.Add("graph node id is empty");
                else if (!nodeIds.Add(node.Id))
                    errors.Add($"duplicate graph node id: {node.Id}");

                if (string.IsNullOrWhiteSpace(node.Title) || node.Title.Length > 80)
                    errors.Add($"graph node title is invalid: {node.Id}");
                if ((node.Text ?? string.Empty).Length > 500)
                    errors.Add($"graph node text is too long: {node.Id}");
            }

            if (string.IsNullOrWhiteSpace(quest.StartNodeId) || !nodeIds.Contains(quest.StartNodeId))
                errors.Add("graph start node is missing");

            if (!nodes.Any(node => node != null && node.Type is DynamicQuestNodeType.Complete or DynamicQuestNodeType.Fail))
                errors.Add("graph terminal node is missing");

            foreach (DynamicQuestNode node in nodes)
            {
                if (node == null)
                    continue;

                if (node.Type is not DynamicQuestNodeType.Complete and not DynamicQuestNodeType.Fail &&
                    (node.Edges == null || node.Edges.Count == 0))
                {
                    errors.Add($"graph non-terminal node has no edge: {node.Id}");
                }

                if (node.Type is DynamicQuestNodeType.Complete or DynamicQuestNodeType.Fail &&
                    node.Edges != null &&
                    node.Edges.Count > 0)
                {
                    errors.Add($"graph terminal node has edge: {node.Id}");
                }

                foreach (DynamicQuestEdge edge in node.Edges ?? Array.Empty<DynamicQuestEdge>())
                {
                    if (edge == null || string.IsNullOrWhiteSpace(edge.ToNodeId) || !nodeIds.Contains(edge.ToNodeId))
                        errors.Add($"graph edge target is missing: {node.Id}->{edge?.ToNodeId ?? string.Empty}");
                    if (edge != null)
                        ValidateGraphEdgeCondition(errors, node, edge);
                }

                ValidateNodeObjective(errors, node);
            }
        }

        private static void ValidateGraphEdgeCondition(List<string> errors, DynamicQuestNode node, DynamicQuestEdge edge)
        {
            if (edge.Condition == DynamicQuestEdgeCondition.ChoiceSelected)
            {
                if (node.Type != DynamicQuestNodeType.Choice)
                {
                    errors.Add($"choice edge is outside choice node: {node.Id}");
                }
                else
                {
                    string choiceId = (edge.ConditionValue ?? string.Empty).Trim();
                    HashSet<string> choices = new((node.Objective?.Choices ?? Array.Empty<DynamicQuestChoice>())
                        .Select(choice => (choice?.Id ?? string.Empty).Trim())
                        .Where(id => !string.IsNullOrWhiteSpace(id)), StringComparer.OrdinalIgnoreCase);

                    if (string.IsNullOrWhiteSpace(choiceId) || !choices.Contains(choiceId))
                        errors.Add($"choice edge value is invalid: {node.Id}");
                }
            }

            if (edge.Condition == DynamicQuestEdgeCondition.WorldSignal &&
                !string.IsNullOrWhiteSpace(edge.ConditionValue) &&
                !DynamicQuestWorldSignalPolicy.IsAllowed(edge.ConditionValue))
            {
                errors.Add($"graph world signal is invalid: {node.Id}");
            }

            if (edge.Condition is DynamicQuestEdgeCondition.TimedOut or DynamicQuestEdgeCondition.PartySizeAtLeast &&
                (!int.TryParse((edge.ConditionValue ?? string.Empty).Trim(), out int parsed) || parsed <= 0))
            {
                errors.Add($"graph edge condition value is invalid: {node.Id}");
            }
        }

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
                    else
                        ValidateChoiceObjective(errors, node, objective);

                    if (node.Edges == null ||
                        !node.Edges.Any(edge => edge?.Condition == DynamicQuestEdgeCondition.ChoiceSelected))
                    {
                        errors.Add($"choice node has no choice edge: {node.Id}");
                    }
                    break;
                case DynamicQuestNodeType.Explore:
                    if (string.IsNullOrWhiteSpace(objective.LocationName) || objective.LocationName.Length > 80)
                        errors.Add($"explore node location is invalid: {node.Id}");
                    if (objective.RegionId == 0)
                        errors.Add($"explore node region is invalid: {node.Id}");
                    if (objective.X <= 0 || objective.Y <= 0)
                        errors.Add($"explore node coordinate is invalid: {node.Id}");
                    if (objective.Radius < 64 || objective.Radius > 2000)
                        errors.Add($"explore node radius is invalid: {node.Id}");
                    break;
            }
        }

        private static void ValidateChoiceObjective(List<string> errors, DynamicQuestNode node, DynamicQuestObjective objective)
        {
            HashSet<string> choiceIds = new(StringComparer.OrdinalIgnoreCase);
            foreach (DynamicQuestChoice choice in objective.Choices ?? Array.Empty<DynamicQuestChoice>())
            {
                string choiceId = (choice?.Id ?? string.Empty).Trim();
                if (string.IsNullOrWhiteSpace(choiceId) || choiceId.Length > 40)
                {
                    errors.Add($"choice id is invalid: {node.Id}");
                    continue;
                }

                if (!choiceIds.Add(choiceId))
                    errors.Add($"duplicate choice id: {node.Id}:{choiceId}");

                string label = choice?.Label ?? string.Empty;
                if (string.IsNullOrWhiteSpace(label) || label.Length > 80)
                    errors.Add($"choice label is invalid: {node.Id}:{choiceId}");
            }
        }

        private static IList<string> BuildGraphReachabilityWarnings(DynamicQuestDefinition quest)
        {
            IList<DynamicQuestNode> nodes = quest?.Nodes ?? Array.Empty<DynamicQuestNode>();
            HashSet<string> nodeIds = new(
                nodes
                    .Where(node => node != null && !string.IsNullOrWhiteSpace(node.Id))
                    .Select(node => node.Id),
                StringComparer.OrdinalIgnoreCase);
            List<string> warnings = new();
            if (string.IsNullOrWhiteSpace(quest.StartNodeId) || !nodeIds.Contains(quest.StartNodeId))
                return warnings;

            Dictionary<string, DynamicQuestNode> byId = nodes
                .Where(node => node != null && !string.IsNullOrWhiteSpace(node.Id))
                .GroupBy(node => node.Id, StringComparer.OrdinalIgnoreCase)
                .ToDictionary(group => group.Key, group => group.First(), StringComparer.OrdinalIgnoreCase);
            HashSet<string> reachable = new(StringComparer.OrdinalIgnoreCase);
            Queue<string> queue = new();
            queue.Enqueue(quest.StartNodeId);

            while (queue.Count > 0)
            {
                string nodeId = queue.Dequeue();
                if (!reachable.Add(nodeId) || !byId.TryGetValue(nodeId, out DynamicQuestNode node))
                    continue;

                foreach (DynamicQuestEdge edge in node.Edges ?? Array.Empty<DynamicQuestEdge>())
                {
                    if (edge != null && !string.IsNullOrWhiteSpace(edge.ToNodeId) && nodeIds.Contains(edge.ToNodeId))
                        queue.Enqueue(edge.ToNodeId);
                }
            }

            foreach (DynamicQuestNode node in nodes.Where(node => node != null && !reachable.Contains(node.Id)))
                warnings.Add($"graph node is unreachable: {node.Id}");

            return warnings;
        }

        private static string GenerateQuestJson(GameNPC startNpc, string seed)
        {
            using HttpClient client = new()
            {
                BaseAddress = new Uri(Properties.WORLDAI_LLM_API_URL.TrimEnd('/') + "/"),
                Timeout = TimeSpan.FromSeconds(Properties.WORLDAI_LLM_TIMEOUT_SECONDS <= 0 ? 30 : Properties.WORLDAI_LLM_TIMEOUT_SECONDS),
            };

            object request = new
            {
                model = Properties.WORLDAI_LLM_MODEL,
                messages = new[]
                {
                    new
                    {
                        role = "system",
                        content = "You create JSON-only volatile MMORPG quests in Korean. Return exactly one JSON object. Allowed fields: title, offer, progress, finish, target, count, min_level, max_level, graph. The optional graph object may contain start and nodes. Choice objects may contain id, label, text, and consequence, where consequence is a short narrative result only. Node types: Talk, Kill, ReturnToNpc, Choice, Complete, Fail, Explore. Edge conditions: Always, ObjectiveComplete, ChoiceSelected, PlayerDied, TimedOut, PartySizeAtLeast, WorldSignal. TimedOut and PartySizeAtLeast values must be positive integers. WorldSignal values are limited to mob-growth:killed, mob-growth:killed:mutant, mob-growth:killed:elite, mob-growth:killed:champion, mob-growth:killed:boss, mob-growth:killed:stage:elite, mob-growth:killed:stage:champion, mob-growth:killed:stage:boss, mob-growth:killed:region:<id>, region-entered, region-entered:<id>, region:<id>, time-window, time-window:dawn, time-window:day, time-window:dusk, time-window:night, item-acquired, item-acquired:id:<safe-token>, item-acquired:name:<safe-token>, scene:<safe-token>. Do not include reward, gold, realm_points, command, spawn, delete, database, sql, script, or code."
                    },
                    new
                    {
                        role = "user",
                        content = $"Start NPC: {startNpc.Name}, region {startNpc.CurrentRegionID}. Seed: {seed}. Make one deterministic v1 graph quest shaped Talk -> Kill -> ReturnToNpc -> Choice -> Complete. Use the target/count fields for the kill objective."
                    }
                },
                temperature = 0.5,
                max_tokens = 900
            };

            string requestJson = JsonSerializer.Serialize(request);
            using StringContent content = new(requestJson, Encoding.UTF8, "application/json");
            using HttpResponseMessage response = client.PostAsync("v1/chat/completions", content).GetAwaiter().GetResult();
            string body = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();

            if (!response.IsSuccessStatusCode)
                throw new InvalidOperationException($"LLM server returned {(int)response.StatusCode}: {body}");

            using JsonDocument document = JsonDocument.Parse(body);
            string assistant = document.RootElement.GetProperty("choices")[0].GetProperty("message").GetProperty("content").GetString() ?? string.Empty;
            return NormalizeJsonContent(assistant);
        }

        private static DynamicQuestDefinition ParseLlmQuest(GameNPC startNpc, string json)
        {
            return ParseLlmQuest(startNpc.InternalID ?? string.Empty, startNpc.Name ?? string.Empty, startNpc.CurrentRegionID, json);
        }

        internal static DynamicQuestDefinition ParseLlmQuestForTest(string startNpcInternalId, string startNpcName, ushort startRegionId, string json)
        {
            return ParseLlmQuest(startNpcInternalId, startNpcName, startRegionId, json);
        }

        private static DynamicQuestDefinition ParseLlmQuest(string startNpcInternalId, string startNpcName, ushort startRegionId, string json)
        {
            using JsonDocument document = JsonDocument.Parse(json);
            JsonElement root = document.RootElement;

            ForbidLlmField(root, "reward");
            ForbidLlmField(root, "gold");
            ForbidLlmField(root, "realm_points");
            ForbidLlmField(root, "command");
            ForbidLlmField(root, "spawn");
            ForbidLlmField(root, "delete");
            ForbidLlmField(root, "database");
            ForbidLlmField(root, "sql");
            ForbidLlmField(root, "script");
            ForbidLlmField(root, "code");

            DynamicQuestDefinition quest = new()
            {
                Title = GetString(root, "title", 80),
                OfferText = GetString(root, "offer", 500),
                ProgressText = GetString(root, "progress", 300),
                FinishText = GetString(root, "finish", 300),
                TargetName = GetString(root, "target", 80),
                TargetCount = Math.Clamp(GetInt(root, "count", 1), 1, Math.Max(1, Properties.KDAOC_DYNAMIC_QUEST_MAX_KILL_COUNT)),
                MinLevel = Math.Clamp(GetInt(root, "min_level", 1), 1, 50),
                MaxLevel = Math.Clamp(GetInt(root, "max_level", 50), 1, 50),
                StartNpcInternalId = startNpcInternalId ?? string.Empty,
                StartNpcName = startNpcName ?? string.Empty,
                StartRegionId = startRegionId,
            };

            if (root.TryGetProperty("graph", out JsonElement graph) && graph.ValueKind == JsonValueKind.Object)
            {
                quest.StartNodeId = GetStringAny(graph, 40, "start", "start_node_id", "startNodeId");
                if (graph.TryGetProperty("nodes", out JsonElement nodes) && nodes.ValueKind == JsonValueKind.Array)
                    quest.Nodes = ParseLlmGraphNodes(nodes, quest);
            }

            return quest;
        }

        private static IList<DynamicQuestNode> ParseLlmGraphNodes(JsonElement nodesElement, DynamicQuestDefinition quest)
        {
            List<DynamicQuestNode> nodes = new();
            foreach (JsonElement nodeElement in nodesElement.EnumerateArray())
            {
                if (nodeElement.ValueKind != JsonValueKind.Object)
                    throw new InvalidOperationException("LLM graph node must be an object.");

                DynamicQuestNodeType type = ParseLlmNodeType(GetString(nodeElement, "type", 40));
                string id = GetString(nodeElement, "id", 40);
                if (string.IsNullOrWhiteSpace(id))
                    id = type.ToString().ToLowerInvariant();

                DynamicQuestNode node = new()
                {
                    Id = id,
                    Type = type,
                    Title = GetString(nodeElement, "title", 80),
                    Text = GetString(nodeElement, "text", 500),
                    Objective = ParseLlmObjective(nodeElement, type, quest),
                    Edges = ParseLlmEdges(nodeElement)
                };

                if (string.IsNullOrWhiteSpace(node.Title))
                    node.Title = DefaultNodeTitle(type);

                nodes.Add(node);
            }

            return nodes;
        }

        private static DynamicQuestObjective ParseLlmObjective(JsonElement nodeElement, DynamicQuestNodeType type, DynamicQuestDefinition quest)
        {
            JsonElement objective = nodeElement.TryGetProperty("objective", out JsonElement value) && value.ValueKind == JsonValueKind.Object
                ? value
                : default;

            switch (type)
            {
                case DynamicQuestNodeType.Talk:
                case DynamicQuestNodeType.ReturnToNpc:
                    return new DynamicQuestObjective
                    {
                        NpcInternalId = quest.StartNpcInternalId,
                        NpcName = quest.StartNpcName,
                        RegionId = quest.StartRegionId
                    };

                case DynamicQuestNodeType.Kill:
                    string targetName = GetStringAny(objective, 80, "target", "target_name", "targetName", "name");
                    return new DynamicQuestObjective
                    {
                        TargetName = string.IsNullOrWhiteSpace(targetName) ? quest.TargetName : targetName,
                        TargetCount = Math.Clamp(GetIntAny(objective, quest.TargetCount, "count", "target_count", "targetCount"), 1, Math.Max(1, Properties.KDAOC_DYNAMIC_QUEST_MAX_KILL_COUNT)),
                        MinLevel = Math.Clamp(GetIntAny(objective, quest.MinLevel, "min_level", "minLevel"), 1, 50),
                        MaxLevel = Math.Clamp(GetIntAny(objective, quest.MaxLevel, "max_level", "maxLevel"), 1, 50),
                        RegionId = (ushort)Math.Clamp(GetIntAny(objective, quest.StartRegionId, "region_id", "regionId"), 0, ushort.MaxValue),
                        AllowGroupCredit = GetBoolAny(objective, false, "allow_group_credit", "allowGroupCredit")
                    };

                case DynamicQuestNodeType.Choice:
                    return new DynamicQuestObjective
                    {
                        Choices = ParseLlmChoices(nodeElement)
                    };

                case DynamicQuestNodeType.Explore:
                    ForbidLlmExploreServerOwnedField(objective, "x");
                    ForbidLlmExploreServerOwnedField(objective, "y");
                    ForbidLlmExploreServerOwnedField(objective, "z");
                    ForbidLlmExploreServerOwnedField(objective, "radius");
                    ForbidLlmExploreServerOwnedField(objective, "region_id");
                    ForbidLlmExploreServerOwnedField(objective, "regionId");
                    string locationName = GetStringAny(objective, 80, "location_name", "locationName", "name");
                    return new DynamicQuestObjective
                    {
                        LocationName = string.IsNullOrWhiteSpace(locationName) ? "조사 지점" : locationName,
                        RegionId = quest.StartRegionId,
                        X = 1,
                        Y = 1,
                        Z = 0,
                        Radius = 450
                    };

                default:
                    return new DynamicQuestObjective();
            }
        }

        private static IList<DynamicQuestChoice> ParseLlmChoices(JsonElement nodeElement)
        {
            JsonElement choicesElement = default;
            if (nodeElement.TryGetProperty("choices", out JsonElement directChoices) && directChoices.ValueKind == JsonValueKind.Array)
                choicesElement = directChoices;
            else if (nodeElement.TryGetProperty("objective", out JsonElement objective) &&
                     objective.ValueKind == JsonValueKind.Object &&
                     objective.TryGetProperty("choices", out JsonElement objectiveChoices) &&
                     objectiveChoices.ValueKind == JsonValueKind.Array)
                choicesElement = objectiveChoices;

            if (choicesElement.ValueKind != JsonValueKind.Array)
                return Array.Empty<DynamicQuestChoice>();

            List<DynamicQuestChoice> choices = new();
            foreach (JsonElement choiceElement in choicesElement.EnumerateArray().Take(2))
            {
                if (choiceElement.ValueKind != JsonValueKind.Object)
                    continue;

                string id = GetString(choiceElement, "id", 40);
                if (string.IsNullOrWhiteSpace(id))
                    id = $"choice{choices.Count + 1}";

                choices.Add(new DynamicQuestChoice
                {
                    Id = id,
                    Label = GetString(choiceElement, "label", 80),
                    Text = GetString(choiceElement, "text", 300),
                    Consequence = GetStringAny(choiceElement, 300, "consequence", "result", "memory")
                });
            }

            return choices;
        }

        private static IList<DynamicQuestEdge> ParseLlmEdges(JsonElement nodeElement)
        {
            if (!nodeElement.TryGetProperty("edges", out JsonElement edgesElement) || edgesElement.ValueKind != JsonValueKind.Array)
                return Array.Empty<DynamicQuestEdge>();

            List<DynamicQuestEdge> edges = new();
            foreach (JsonElement edgeElement in edgesElement.EnumerateArray())
            {
                if (edgeElement.ValueKind != JsonValueKind.Object)
                    continue;

                DynamicQuestEdgeCondition condition = ParseLlmEdgeCondition(GetString(edgeElement, "condition", 40));
                string conditionValue = ParseLlmEdgeConditionValue(
                    condition,
                    GetStringAny(edgeElement, 96, "value", "condition_value", "conditionValue"));

                edges.Add(new DynamicQuestEdge
                {
                    ToNodeId = GetStringAny(edgeElement, 40, "to", "to_node_id", "toNodeId"),
                    Condition = condition,
                    ConditionValue = conditionValue,
                    Priority = GetInt(edgeElement, "priority", edges.Count)
                });
            }

            return edges;
        }

        private static DynamicQuestNodeType ParseLlmNodeType(string raw)
        {
            if (string.Equals(raw, "Return", StringComparison.OrdinalIgnoreCase))
                return DynamicQuestNodeType.ReturnToNpc;

            if (Enum.TryParse(raw, true, out DynamicQuestNodeType type))
                return type;

            throw new InvalidOperationException($"LLM graph node type is invalid: {raw}");
        }

        private static DynamicQuestEdgeCondition ParseLlmEdgeCondition(string raw)
        {
            if (string.IsNullOrWhiteSpace(raw))
                return DynamicQuestEdgeCondition.ObjectiveComplete;

            if (Enum.TryParse(raw, true, out DynamicQuestEdgeCondition condition))
            {
                if (condition is DynamicQuestEdgeCondition.Always or
                    DynamicQuestEdgeCondition.ObjectiveComplete or
                    DynamicQuestEdgeCondition.ChoiceSelected or
                    DynamicQuestEdgeCondition.PlayerDied or
                    DynamicQuestEdgeCondition.TimedOut or
                    DynamicQuestEdgeCondition.PartySizeAtLeast or
                    DynamicQuestEdgeCondition.WorldSignal)
                {
                    return condition;
                }

                throw new InvalidOperationException($"LLM graph edge condition is unsupported in v1: {raw}");
            }

            throw new InvalidOperationException($"LLM graph edge condition is invalid: {raw}");
        }

        private static string ParseLlmEdgeConditionValue(DynamicQuestEdgeCondition condition, string raw)
        {
            string value = (raw ?? string.Empty).Trim();

            if (condition is DynamicQuestEdgeCondition.TimedOut or DynamicQuestEdgeCondition.PartySizeAtLeast)
            {
                if (!int.TryParse(value, out int parsed) || parsed <= 0)
                    throw new InvalidOperationException($"LLM graph edge condition value must be a positive integer: {condition}");

                return parsed.ToString();
            }

            if (condition != DynamicQuestEdgeCondition.WorldSignal)
                return value;

            if (!IsAllowedLlmWorldSignal(value))
                throw new InvalidOperationException($"LLM graph world signal is unsupported: {value}");

            return value;
        }

        private static bool IsAllowedLlmWorldSignal(string value)
        {
            return DynamicQuestWorldSignalPolicy.IsAllowed(value);
        }

        private static string DefaultNodeTitle(DynamicQuestNodeType type)
        {
            return type switch
            {
                DynamicQuestNodeType.Talk => "대화",
                DynamicQuestNodeType.Kill => "목표 처치",
                DynamicQuestNodeType.ReturnToNpc => "보고",
                DynamicQuestNodeType.Choice => "결정",
                DynamicQuestNodeType.Complete => "완료",
                DynamicQuestNodeType.Fail => "실패",
                DynamicQuestNodeType.Explore => "조사",
                _ => "진행"
            };
        }

        private static void ForbidLlmExploreServerOwnedField(JsonElement element, string forbiddenField)
        {
            if (element.ValueKind == JsonValueKind.Object && element.TryGetProperty(forbiddenField, out _))
                throw new InvalidOperationException($"LLM returned server-owned Explore field: {forbiddenField}");
        }

        private static void ForbidLlmField(JsonElement element, string forbiddenField)
        {
            if (element.ValueKind == JsonValueKind.Object)
            {
                foreach (JsonProperty property in element.EnumerateObject())
                {
                    if (property.NameEquals(forbiddenField))
                        throw new InvalidOperationException($"LLM returned forbidden field: {forbiddenField}");

                    ForbidLlmField(property.Value, forbiddenField);
                }
            }
            else if (element.ValueKind == JsonValueKind.Array)
            {
                foreach (JsonElement child in element.EnumerateArray())
                    ForbidLlmField(child, forbiddenField);
            }
        }

        private static string GetString(JsonElement root, string field, int maxLength)
        {
            if (root.ValueKind != JsonValueKind.Object)
                return string.Empty;

            if (!root.TryGetProperty(field, out JsonElement value) || value.ValueKind != JsonValueKind.String)
                return string.Empty;

            string text = value.GetString()?.Trim() ?? string.Empty;
            return text.Length <= maxLength ? text : text.Substring(0, maxLength);
        }

        private static string GetStringAny(JsonElement root, int maxLength, params string[] fields)
        {
            foreach (string field in fields)
            {
                string value = GetString(root, field, maxLength);
                if (!string.IsNullOrWhiteSpace(value))
                    return value;
            }

            return string.Empty;
        }

        private static int GetInt(JsonElement root, string field, int fallback)
        {
            if (root.ValueKind != JsonValueKind.Object)
                return fallback;

            return root.TryGetProperty(field, out JsonElement value) && value.TryGetInt32(out int result) ? result : fallback;
        }

        private static int GetIntAny(JsonElement root, int fallback, params string[] fields)
        {
            foreach (string field in fields)
            {
                int marker = int.MinValue;
                int value = GetInt(root, field, marker);
                if (value != marker)
                    return value;
            }

            return fallback;
        }

        private static bool GetBoolAny(JsonElement root, bool fallback, params string[] fields)
        {
            if (root.ValueKind != JsonValueKind.Object)
                return fallback;

            foreach (string field in fields)
            {
                if (!root.TryGetProperty(field, out JsonElement value))
                    continue;

                if (value.ValueKind == JsonValueKind.True)
                    return true;
                if (value.ValueKind == JsonValueKind.False)
                    return false;
            }

            return fallback;
        }

        private static string NormalizeJsonContent(string content)
        {
            string trimmed = (content ?? string.Empty).Trim();
            if (!trimmed.StartsWith("```", StringComparison.Ordinal))
                return trimmed;

            int firstLine = trimmed.IndexOf('\n');
            int lastFence = trimmed.LastIndexOf("```", StringComparison.Ordinal);
            return firstLine >= 0 && lastFence > firstLine
                ? trimmed.Substring(firstLine + 1, lastFence - firstLine - 1).Trim()
                : trimmed;
        }
    }

    public sealed class DatabaseDynamicQuestProgressRepository : IDynamicQuestProgressRepository
    {
        private static readonly Logging.Logger Log = Logging.LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);

        public bool Add(DbDynamicQuestProgress row)
        {
            if (row == null || string.IsNullOrWhiteSpace(row.ProgressId))
                return false;

            try
            {
                return GameServer.Database?.AddObject(row) ?? false;
            }
            catch (Exception e)
            {
                if (Log.IsWarnEnabled)
                    Log.Warn($"Dynamic quest progress add failed: {row.ProgressId}", e);
                return false;
            }
        }

        public IList<DbDynamicQuestProgress> GetActive(int limit)
        {
            limit = Math.Clamp(limit <= 0 ? 100 : limit, 1, 500);

            try
            {
                return GameServer.Database?.SelectObjects<DbDynamicQuestProgress>(
                        DB.Column("IsActive").IsEqualTo(1)
                            .And(DB.Column("Failed").IsEqualTo(0)))
                    .OrderByDescending(row => row.UpdatedAt)
                    .Take(limit)
                    .ToList() ?? new List<DbDynamicQuestProgress>();
            }
            catch (Exception e)
            {
                if (Log.IsWarnEnabled)
                    Log.Warn("Dynamic quest active progress summary load failed.", e);
                return Array.Empty<DbDynamicQuestProgress>();
            }
        }

        public IList<DbDynamicQuestProgress> GetActiveForDifferentWorldRevision(string currentWorldRevision)
        {
            currentWorldRevision = (currentWorldRevision ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(currentWorldRevision))
                return Array.Empty<DbDynamicQuestProgress>();

            try
            {
                return GameServer.Database?.SelectObjects<DbDynamicQuestProgress>(
                        DB.Column("IsActive").IsEqualTo(1)
                            .And(DB.Column("Failed").IsEqualTo(0)))
                    .Where(row =>
                        row != null &&
                        !string.IsNullOrWhiteSpace(row.WorldRevision) &&
                        !string.Equals(row.WorldRevision, currentWorldRevision, StringComparison.OrdinalIgnoreCase))
                    .OrderBy(row => row.AcceptedAt)
                    .ToList() ?? new List<DbDynamicQuestProgress>();
            }
            catch (Exception e)
            {
                if (Log.IsWarnEnabled)
                    Log.Warn($"Dynamic quest progress world revision scan failed: {currentWorldRevision}", e);
                return Array.Empty<DbDynamicQuestProgress>();
            }
        }

        public IList<DbDynamicQuestProgress> GetActiveForMissingQuestIds(ISet<string> activeQuestIds)
        {
            HashSet<string> normalizedActiveQuestIds = new(activeQuestIds ?? new HashSet<string>(), StringComparer.OrdinalIgnoreCase);

            try
            {
                return GameServer.Database?.SelectObjects<DbDynamicQuestProgress>(
                        DB.Column("IsActive").IsEqualTo(1)
                            .And(DB.Column("Failed").IsEqualTo(0)))
                    .Where(row =>
                        row != null &&
                        !string.IsNullOrWhiteSpace(row.QuestId) &&
                        !normalizedActiveQuestIds.Contains(row.QuestId))
                    .OrderBy(row => row.AcceptedAt)
                    .ToList() ?? new List<DbDynamicQuestProgress>();
            }
            catch (Exception e)
            {
                if (Log.IsWarnEnabled)
                    Log.Warn("Dynamic quest progress missing runtime scan failed.", e);
                return Array.Empty<DbDynamicQuestProgress>();
            }
        }

        public DbDynamicQuestProgress Find(string progressId)
        {
            if (string.IsNullOrWhiteSpace(progressId))
                return null;

            try
            {
                return GameServer.Database?.FindObjectByKey<DbDynamicQuestProgress>(progressId);
            }
            catch (Exception e)
            {
                if (Log.IsWarnEnabled)
                    Log.Warn($"Dynamic quest progress find failed: {progressId}", e);
                return null;
            }
        }

        public IList<DbDynamicQuestProgress> GetByPlayer(string playerKey)
        {
            if (string.IsNullOrWhiteSpace(playerKey))
                return Array.Empty<DbDynamicQuestProgress>();

            try
            {
                return GameServer.Database?.SelectObjects<DbDynamicQuestProgress>(
                        DB.Column("PlayerKey").IsEqualTo(playerKey))
                    .OrderBy(row => row.AcceptedAt)
                    .ToList() ?? new List<DbDynamicQuestProgress>();
            }
            catch (Exception e)
            {
                if (Log.IsWarnEnabled)
                    Log.Warn($"Dynamic quest progress load failed: {playerKey}", e);
                return Array.Empty<DbDynamicQuestProgress>();
            }
        }

        public bool Save(DbDynamicQuestProgress row)
        {
            if (row == null || string.IsNullOrWhiteSpace(row.ProgressId))
                return false;

            try
            {
                return GameServer.Database?.SaveObject(row) ?? false;
            }
            catch (Exception e)
            {
                if (Log.IsWarnEnabled)
                    Log.Warn($"Dynamic quest progress save failed: {row.ProgressId}", e);
                return false;
            }
        }
    }

}
