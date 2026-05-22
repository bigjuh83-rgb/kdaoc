using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using DOL.GS.PacketHandler;
using DOL.GS.ServerProperties;

namespace DOL.GS.WorldAI
{
    public enum DynamicQuestStepType
    {
        Kill,
    }

    public sealed class DynamicQuestDefinition
    {
        public string Id { get; set; } = Guid.NewGuid().ToString("N");
        public string Title { get; set; } = string.Empty;
        public string OfferText { get; set; } = string.Empty;
        public string ProgressText { get; set; } = string.Empty;
        public string FinishText { get; set; } = string.Empty;
        public string StartNpcInternalId { get; set; } = string.Empty;
        public string StartNpcName { get; set; } = string.Empty;
        public ushort StartRegionId { get; set; }
        public DynamicQuestStepType StepType { get; set; } = DynamicQuestStepType.Kill;
        public string TargetName { get; set; } = string.Empty;
        public int TargetCount { get; set; } = 1;
        public int MinLevel { get; set; } = 1;
        public int MaxLevel { get; set; } = 50;
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    }

    public sealed class DynamicQuestProgress
    {
        public string QuestId { get; set; } = string.Empty;
        public int Count { get; set; }
        public bool IsComplete { get; set; }
        public DateTime AcceptedAt { get; set; } = DateTime.UtcNow;
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

    public sealed class DynamicQuestRuntimeService
    {
        private static readonly Logging.Logger Log = Logging.LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);

        private readonly object m_lock = new();
        private readonly Dictionary<string, DynamicQuestDefinition> m_quests = new(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, List<DynamicQuestProgress>> m_playerProgress = new(StringComparer.OrdinalIgnoreCase);

        public static DynamicQuestRuntimeService Instance { get; } = new();

        public DynamicQuestResult AddQuest(DynamicQuestDefinition quest)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED)
                return DynamicQuestResult.Fail("동적 퀘스트가 비활성화되어 있습니다. kdaoc_dynamic_quest_enabled를 켜세요.");

            List<string> errors = Validate(quest);
            if (errors.Count > 0)
                return DynamicQuestResult.Fail(string.Join(" / ", errors));

            lock (m_lock)
            {
                int npcQuestCount = m_quests.Values.Count(existing =>
                    existing.StartNpcInternalId == quest.StartNpcInternalId &&
                    existing.StartRegionId == quest.StartRegionId);

                if (npcQuestCount >= Math.Max(1, Properties.KDAOC_DYNAMIC_QUEST_MAX_ACTIVE_PER_NPC))
                    return DynamicQuestResult.Fail("해당 NPC에 이미 동적 퀘스트가 있습니다.");

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

            DynamicQuestProgress active = GetActiveProgress(player);
            if (active != null && TryGetQuest(active.QuestId, out DynamicQuestDefinition activeQuest) && IsStartNpc(activeQuest, npc))
            {
                if (active.IsComplete)
                {
                    FinishQuest(player, npc, activeQuest, active);
                    return true;
                }

                npc.SayTo(player, $"{activeQuest.ProgressText}\n\n진행: {active.Count}/{activeQuest.TargetCount}");
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

            DynamicQuestProgress active = GetActiveProgress(player);
            if (active != null && TryGetQuest(active.QuestId, out DynamicQuestDefinition activeQuest) && IsStartNpc(activeQuest, npc))
                return active.IsComplete ? eQuestIndicator.Finish : eQuestIndicator.Pending;

            return GetAvailableQuest(npc, player) != null ? eQuestIndicator.Available : eQuestIndicator.None;
        }

        public void HandleEnemyKilled(GamePlayer player, GameLiving enemy)
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED || player == null || enemy == null)
                return;

            DynamicQuestProgress active = GetActiveProgress(player);
            if (active == null || active.IsComplete || !TryGetQuest(active.QuestId, out DynamicQuestDefinition quest))
                return;

            if (quest.StepType != DynamicQuestStepType.Kill || !NameMatches(enemy.Name, quest.TargetName))
                return;

            active.Count = Math.Min(quest.TargetCount, active.Count + 1);

            if (active.Count >= quest.TargetCount)
            {
                active.IsComplete = true;
                player.Out.SendMessage($"{quest.Title}: 완료되었습니다. {quest.StartNpcName}에게 돌아가세요.", eChatType.CT_Important, eChatLoc.CL_SystemWindow);
            }
            else
            {
                player.Out.SendMessage($"{quest.Title}: {active.Count}/{quest.TargetCount}", eChatType.CT_System, eChatLoc.CL_SystemWindow);
            }
        }

        public IList<DynamicQuestDefinition> GetQuests()
        {
            lock (m_lock)
                return m_quests.Values.OrderBy(quest => quest.CreatedAt).ToList();
        }

        public int ClearAll()
        {
            lock (m_lock)
            {
                int count = m_quests.Count;
                m_quests.Clear();
                m_playerProgress.Clear();
                return count;
            }
        }

        private void AcceptQuest(GamePlayer player, GameNPC npc, DynamicQuestDefinition quest)
        {
            string playerKey = GetPlayerKey(player);
            lock (m_lock)
            {
                if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                {
                    progressList = new List<DynamicQuestProgress>();
                    m_playerProgress[playerKey] = progressList;
                }

                int maxActive = Math.Max(1, Properties.KDAOC_DYNAMIC_QUEST_MAX_ACTIVE_PER_PLAYER);
                if (progressList.Count(progress => !progress.IsComplete) >= maxActive)
                {
                    player.Out.SendMessage("이미 진행 중인 동적 퀘스트가 있습니다.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                    return;
                }

                if (progressList.Any(progress => progress.QuestId == quest.Id))
                {
                    player.Out.SendMessage("이미 받은 동적 퀘스트입니다.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                    return;
                }

                progressList.Add(new DynamicQuestProgress { QuestId = quest.Id });
            }

            npc.SayTo(player, $"{quest.Title}\n\n{quest.ProgressText}\n\n목표: {quest.TargetName} {quest.TargetCount}마리 처치");
            player.Out.SendNPCsQuestEffect(npc, GetQuestIndicator(npc, player));
        }

        private void FinishQuest(GamePlayer player, GameNPC npc, DynamicQuestDefinition quest, DynamicQuestProgress progress)
        {
            long xp = CalculateRewardXp(player, quest);
            long money = CalculateRewardMoney(player, quest);

            if (xp > 0)
                player.ForceGainExperience(xp);

            if (money > 0)
                player.AddMoney(money, "동적 퀘스트 보상으로 {0}을 받았습니다.");

            RemoveProgress(player, progress);
            npc.SayTo(player, quest.FinishText);
            player.Out.SendNPCsQuestEffect(npc, GetQuestIndicator(npc, player));
        }

        private static long CalculateRewardXp(GamePlayer player, DynamicQuestDefinition quest)
        {
            int level = Math.Max(1, (int)player.Level);
            double baseXp = level * level * 12.0 * Math.Max(1, quest.TargetCount);
            return (long)Math.Max(0, baseXp * Properties.KDAOC_DYNAMIC_QUEST_REWARD_XP_MULTIPLIER);
        }

        private static long CalculateRewardMoney(GamePlayer player, DynamicQuestDefinition quest)
        {
            int level = Math.Max(1, (int)player.Level);
            double baseCopper = level * 20.0 * Math.Max(1, quest.TargetCount);
            return (long)Math.Max(0, baseCopper * Properties.KDAOC_DYNAMIC_QUEST_REWARD_MONEY_MULTIPLIER);
        }

        private DynamicQuestProgress GetActiveProgress(GamePlayer player)
        {
            string playerKey = GetPlayerKey(player);
            lock (m_lock)
            {
                if (!m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                    return null;

                return progressList.FirstOrDefault(progress => TryGetQuest(progress.QuestId, out _));
            }
        }

        private void RemoveProgress(GamePlayer player, DynamicQuestProgress progress)
        {
            string playerKey = GetPlayerKey(player);
            lock (m_lock)
            {
                if (m_playerProgress.TryGetValue(playerKey, out List<DynamicQuestProgress> progressList))
                    progressList.Remove(progress);
            }
        }

        private DynamicQuestDefinition GetAvailableQuest(GameNPC npc, GamePlayer player)
        {
            lock (m_lock)
            {
                return m_quests.Values.FirstOrDefault(quest =>
                    IsStartNpc(quest, npc) &&
                    player.Level >= quest.MinLevel &&
                    player.Level <= quest.MaxLevel);
            }
        }

        private bool TryGetQuest(string questId, out DynamicQuestDefinition quest)
        {
            lock (m_lock)
                return m_quests.TryGetValue(questId, out quest);
        }

        private static bool IsStartNpc(DynamicQuestDefinition quest, GameNPC npc)
        {
            return quest.StartRegionId == npc.CurrentRegionID &&
                string.Equals(quest.StartNpcInternalId, npc.InternalID ?? string.Empty, StringComparison.OrdinalIgnoreCase);
        }

        private static bool NameMatches(string actualName, string expectedName)
        {
            return string.Equals(actualName?.Trim(), expectedName?.Trim(), StringComparison.OrdinalIgnoreCase);
        }

        private static string GetPlayerKey(GamePlayer player)
        {
            return !string.IsNullOrWhiteSpace(player.InternalID) ? player.InternalID : player.Name;
        }

        private static List<string> Validate(DynamicQuestDefinition quest)
        {
            List<string> errors = new();

            if (quest == null)
                return new List<string> { "퀘스트가 없습니다." };
            if (string.IsNullOrWhiteSpace(quest.Title) || quest.Title.Length > 80)
                errors.Add("제목이 비어 있거나 너무 깁니다.");
            if (string.IsNullOrWhiteSpace(quest.OfferText) || quest.OfferText.Length > 500)
                errors.Add("수락 대사가 비어 있거나 너무 깁니다.");
            if (string.IsNullOrWhiteSpace(quest.ProgressText) || quest.ProgressText.Length > 300)
                errors.Add("진행 대사가 비어 있거나 너무 깁니다.");
            if (string.IsNullOrWhiteSpace(quest.FinishText) || quest.FinishText.Length > 300)
                errors.Add("완료 대사가 비어 있거나 너무 깁니다.");
            if (string.IsNullOrWhiteSpace(quest.StartNpcInternalId))
                errors.Add("시작 NPC 식별자가 없습니다.");
            if (string.IsNullOrWhiteSpace(quest.TargetName))
                errors.Add("목표 몬스터 이름이 없습니다.");
            if (quest.TargetCount < 1 || quest.TargetCount > Math.Max(1, Properties.KDAOC_DYNAMIC_QUEST_MAX_KILL_COUNT))
                errors.Add("목표 처치 수가 허용 범위를 벗어났습니다.");
            if (quest.MinLevel < 1 || quest.MaxLevel < quest.MinLevel || quest.MaxLevel > 50)
                errors.Add("레벨 범위가 잘못되었습니다.");

            return errors;
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
                        content = "You create JSON-only volatile MMORPG quests in Korean. Return exactly one JSON object. Allowed fields: title, offer, progress, finish, target, count, min_level, max_level. Do not include reward, gold, realm_points, command, spawn, delete, database, sql, script, or code."
                    },
                    new
                    {
                        role = "user",
                        content = $"Start NPC: {startNpc.Name}, region {startNpc.CurrentRegionID}. Seed: {seed}. Make one simple kill quest."
                    }
                },
                temperature = 0.5,
                max_tokens = 500
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

            return new DynamicQuestDefinition
            {
                Title = GetString(root, "title", 80),
                OfferText = GetString(root, "offer", 500),
                ProgressText = GetString(root, "progress", 300),
                FinishText = GetString(root, "finish", 300),
                TargetName = GetString(root, "target", 80),
                TargetCount = Math.Clamp(GetInt(root, "count", 1), 1, Math.Max(1, Properties.KDAOC_DYNAMIC_QUEST_MAX_KILL_COUNT)),
                MinLevel = Math.Clamp(GetInt(root, "min_level", 1), 1, 50),
                MaxLevel = Math.Clamp(GetInt(root, "max_level", 50), 1, 50),
                StartNpcInternalId = startNpc.InternalID ?? string.Empty,
                StartNpcName = startNpc.Name ?? string.Empty,
                StartRegionId = startNpc.CurrentRegionID,
            };
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
            if (!root.TryGetProperty(field, out JsonElement value) || value.ValueKind != JsonValueKind.String)
                return string.Empty;

            string text = value.GetString()?.Trim() ?? string.Empty;
            return text.Length <= maxLength ? text : text.Substring(0, maxLength);
        }

        private static int GetInt(JsonElement root, string field, int fallback)
        {
            return root.TryGetProperty(field, out JsonElement value) && value.TryGetInt32(out int result) ? result : fallback;
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
}
