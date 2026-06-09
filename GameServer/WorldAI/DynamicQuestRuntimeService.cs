using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using DOL.Database;
using DOL.GS.PacketHandler;
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

        private readonly object m_lock = new();
        private readonly Dictionary<string, DynamicQuestDefinition> m_quests = new(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, List<DynamicQuestProgress>> m_playerProgress = new(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, HashSet<string>> m_playerCompletedQuestIds = new(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, List<DynamicQuestTimelineEvent>> m_playerTimeline = new(StringComparer.OrdinalIgnoreCase);
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

            string playerKey = GetPlayerKey(player);
            string playerName = player.Name ?? string.Empty;
            EnsurePlayerProgressLoaded(playerKey, playerName);

            bool handled = false;
            foreach (string signal in BuildItemAcquiredSignals(item))
            {
                handled |= TryAcceptAvailableWorldQuest(player, signal);
                handled |= RecordWorldSignalForPlayer(player, playerKey, playerName, signal);
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
            limit = Math.Clamp(limit <= 0 ? 50 : limit, 1, 200);

            List<DynamicQuestTimelineEvent> events;
            lock (m_lock)
            {
                events = !string.IsNullOrWhiteSpace(playerKey) &&
                         m_playerTimeline.TryGetValue(playerKey, out List<DynamicQuestTimelineEvent> timeline)
                    ? timeline
                        .OrderByDescending(item => item.At)
                        .Take(limit)
                        .OrderBy(item => item.At)
                        .Select(CloneTimelineEvent)
                        .ToList()
                    : new List<DynamicQuestTimelineEvent>();
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

        public int ClearAll()
        {
            lock (m_lock)
            {
                int count = m_quests.Count;
                m_quests.Clear();
                m_playerProgress.Clear();
                m_playerCompletedQuestIds.Clear();
                m_playerTimeline.Clear();
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

        public bool TryAcceptWorldQuest(GamePlayer player, string questId, string source = "world_offer")
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
                source);

            if (accepted)
                player.Out.SendMessage($"{normalizedQuest.Title}\n\n{normalizedQuest.ProgressText}", eChatType.CT_System, eChatLoc.CL_SystemWindow);

            return accepted;
        }

        public bool TryAcceptAvailableWorldQuest(GamePlayer player, string trigger)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED || player == null)
                return false;

            string playerKey = GetPlayerKey(player);
            EnsurePlayerProgressLoaded(playerKey, player.Name ?? string.Empty);
            DynamicQuestDefinition quest = GetAvailableWorldQuest(playerKey, player.Level, trigger);
            if (quest == null)
                return false;

            return TryAcceptWorldQuest(player, quest.Id, trigger);
        }

        private void AcceptQuest(GamePlayer player, GameNPC npc, DynamicQuestDefinition quest)
        {
            bool accepted = AcceptQuestByPlayerKey(
                GetPlayerKey(player),
                player?.Name ?? string.Empty,
                player,
                npc,
                quest,
                "npc_dialog");

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
                source);
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
                trigger);
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
                DynamicQuestDefinition quest = GetAvailableWorldQuest(playerKey, playerLevel, trigger, autoAcceptOnly: true);
                if (quest == null)
                    continue;
                if (requireStartScope && !IsInsideAutoAcceptStartScope(quest, regionId, x, y))
                    continue;

                return AcceptQuestByPlayerKey(
                    playerKey,
                    playerName,
                    null,
                    null,
                    quest,
                    trigger);
            }

            return false;
        }

        private bool AcceptQuestByPlayerKey(
            string playerKey,
            string playerName,
            GamePlayer player,
            GameNPC npc,
            DynamicQuestDefinition quest,
            string source)
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
                player?.Out.SendMessage("이 동적 퀘스트는 시작 NPC와 대화해야 합니다.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
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
                    player?.Out.SendMessage("이미 완료한 동적 퀘스트입니다.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                    return false;
                }

                if (progressList.Count(IsProgressCountingAgainstActiveLimit) >= maxActive)
                    CancelAutoAcceptProgressForManualQuestLocked(playerKey, playerName, progressList, normalizedQuest, maxActive);

                if (progressList.Count(IsProgressCountingAgainstActiveLimit) >= maxActive)
                {
                    player?.Out.SendMessage("이미 진행 중인 동적 퀘스트가 있습니다.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                    return false;
                }

                if (progressList.Any(progress =>
                    progress != null &&
                    progress.QuestId == normalizedQuest.Id &&
                    IsProgressCountingAgainstActiveLimit(progress)))
                {
                    player?.Out.SendMessage("이미 받은 동적 퀘스트입니다.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
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
                return true;
            }
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
                    cancelled++;
                }

                progressList.RemoveAll(progress => progress.Failed || progress.Completed || progress.IsComplete);
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

            SaveProgress(playerKey, playerName, progress);
        }

        private bool IsQuestRewarded(string playerKey, string questId)
        {
            lock (m_lock)
                return HasQuestRewardedTimelineEventLocked(playerKey, questId);
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

            if (!IsQuestRewarded(GetPlayerKey(player), quest.Id))
            {
                if (xp > 0)
                    player.ForceGainExperience(xp);

                if (money > 0)
                    player.AddMoney(money, "동적 퀘스트 보상으로 {0}을 받았습니다.");
            }

            MarkCompletedQuestRewarded(GetPlayerKey(player), player.Name ?? string.Empty, quest, progress);

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
                        progress.PendingWorldSignals.Add(NormalizePendingWorldSignal(signal));
                        progress.UpdatedAt = DateTime.UtcNow;
                        RecordTimelineEventLocked(
                            playerKey,
                            playerName,
                            normalized.Id,
                            "world_signal_pending",
                            nodeId: node.Id,
                            detail: signal);
                        SaveProgress(playerKey, playerName, progress);
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
                     string.Equals(edge.ConditionValue, signal, StringComparison.OrdinalIgnoreCase)));
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
                     string.Equals(item.ConditionValue, conditionValue, StringComparison.OrdinalIgnoreCase)));

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
                    MarkQuestCompletedLocked(playerKey, questId);

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
                    string message = BuildNarrativeSceneMessage(scene);
                    if (!string.IsNullOrWhiteSpace(message))
                    {
                        player.Out.SendMessage(message, eChatType.CT_Important, eChatLoc.CL_SystemWindow);
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

            foreach (DynamicQuestPresentationBeat beat in ParsePresentationBeats(quest.StoryPresentationJson)
                         .Where(beat =>
                             string.Equals(beat.NodeId, nodeId, StringComparison.OrdinalIgnoreCase) &&
                             PresentationTriggerMatches(beat.Trigger, normalizedTrigger)))
            {
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

                PlayPresentationBeat(player, npc, beat);
            }
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

        private static string BuildNarrativeSceneDetail(DynamicQuestNarrativeScene scene)
        {
            if (scene == null)
                return string.Empty;

            return string.Join("\n\n", new[]
                {
                    scene.Title,
                    scene.Body
                }
                .Where(text => !string.IsNullOrWhiteSpace(text))
                .Select(text => text.Trim()));
        }

        internal static string BuildNarrativeSceneMessageForTest(DynamicQuestNarrativeScene scene)
        {
            return BuildNarrativeSceneMessage(scene);
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
                beat.Text ?? string.Empty
            });
        }

        private static void PlayPresentationBeat(GamePlayer player, GameNPC npc, DynamicQuestPresentationBeat beat)
        {
            if (player == null || beat == null)
                return;

            string speaker = (beat.Speaker ?? string.Empty).Trim();
            string text = (beat.Text ?? string.Empty).Trim();
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
                    emote = eEmote.Cheer;
                    return true;
                case "doubt":
                case "confusion":
                    emote = eEmote.Confused;
                    return true;
                case "warning":
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

            if (timeline.Count > 200)
                timeline.RemoveRange(0, timeline.Count - 200);
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
                .OrderByDescending(evt => evt.At)
                .FirstOrDefault();
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

            if (parts.Length >= 5)
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
                Text = text ?? string.Empty
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
        }

        private DynamicQuestDefinition GetAvailableQuest(GameNPC npc, GamePlayer player)
        {
            lock (m_lock)
            {
                return m_quests.Values.FirstOrDefault(quest =>
                    IsStartNpc(quest, npc) &&
                    !HasCompletedQuest(GetPlayerKey(player), quest.Id) &&
                    !HasProgress(GetPlayerKey(player), quest.Id) &&
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
                DynamicQuestDefinition quest = GetAvailableWorldQuest(playerKey, player.Level, trigger, autoAcceptOnly: true);
                if (quest == null)
                    continue;
                if (!IsInsideAutoAcceptStartScope(quest, regionId, player.X, player.Y))
                    continue;

                return TryAcceptWorldQuest(player, quest.Id, trigger);
            }

            return false;
        }

        private DynamicQuestDefinition GetAvailableWorldQuest(string playerKey, int playerLevel, string trigger, bool autoAcceptOnly = false)
        {
            playerKey = (playerKey ?? string.Empty).Trim();

            lock (m_lock)
            {
                return m_quests.Values
                    .Where(quest =>
                        !RequiresStartNpc(quest) &&
                        (!autoAcceptOnly || quest.StartMode == DynamicQuestStartMode.AutoAccept) &&
                        QuestTriggerMatches(quest, trigger) &&
                        !HasCompletedQuest(playerKey, quest.Id) &&
                        !HasProgress(playerKey, quest.Id) &&
                        PlayerLevelMatchesQuest(quest, playerLevel))
                    .OrderByDescending(quest => quest.StartMode == DynamicQuestStartMode.AutoAccept)
                    .ThenBy(quest => quest.CreatedAt)
                    .FirstOrDefault();
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
                        content = "You create JSON-only volatile MMORPG quests in Korean. Return exactly one JSON object. Allowed fields: title, offer, progress, finish, target, count, min_level, max_level, graph. The optional graph object may contain start and nodes. Choice objects may contain id, label, text, and consequence, where consequence is a short narrative result only. Node types: Talk, Kill, ReturnToNpc, Choice, Complete, Fail, Explore. Edge conditions: Always, ObjectiveComplete, ChoiceSelected, PlayerDied, TimedOut, PartySizeAtLeast, WorldSignal. TimedOut and PartySizeAtLeast values must be positive integers. WorldSignal values are limited to mob-growth:killed, mob-growth:killed:mutant, mob-growth:killed:elite, mob-growth:killed:champion, mob-growth:killed:boss, mob-growth:killed:stage:elite, mob-growth:killed:stage:champion, mob-growth:killed:stage:boss, mob-growth:killed:region:<id>, region-entered, region-entered:<id>, region:<id>, time-window, time-window:dawn, time-window:day, time-window:dusk, time-window:night, item-acquired, item-acquired:id:<safe-token>, item-acquired:name:<safe-token>. Do not include reward, gold, realm_points, command, spawn, delete, database, sql, script, or code."
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
