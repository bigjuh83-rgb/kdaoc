using System.Linq;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;
using DOL.Database;
using DOL.GS;
using DOL.GS.ServerProperties;
using DOL.GS.WorldAI;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace DOL.GS.API.WorldAI
{
    internal static class WorldAiRoutes
    {
        public static void MapWorldAiRoutes(this WebApplication api)
        {
            WorldNewsService provider = WorldNewsService.Instance;

            api.MapGet("/api/world/events", (HttpContext context) =>
                Results.Ok(provider.GetEvents(ReadLimit(context, 20))));

            api.MapGet("/api/world/news", (HttpContext context) =>
                Results.Ok(provider.GetNews(ReadLimit(context, 10))));

            api.MapGet("/api/world/llm/jobs", (HttpContext context) =>
                Results.Ok(LlmJobQueueService.Instance.GetPendingWorkItems(ReadLimit(context, 10))));

            api.MapGet("/api/world/llm/jobs/detail", (HttpContext context) =>
                Results.Ok(LlmJobQueueService.Instance.GetJobDetails(ReadLimit(context, 20))));

            api.MapGet("/api/world/llm/health", () =>
                Results.Ok(LlmJobQueueService.Instance.GetQueueHealth()));

            api.MapGet("/api/world/mob-growth/summary", (HttpContext context) =>
                Results.Ok(MobGrowthService.Instance.GetSummary(
                    ReadLimit(context, 20),
                    ReadUShort(context, "region"))));

            api.MapGet("/api/world/dynamic-quests", () =>
                Results.Ok(new
                {
                    enabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                    quests = DynamicQuestRuntimeService.Instance.GetQuests()
                }));

            api.MapGet("/api/world/dynamic-quests/progress", (HttpContext context) =>
            {
                string playerName = Query(context, "player", Query(context, "name"));
                string account = Query(context, "account");

                if (string.IsNullOrWhiteSpace(playerName) && string.IsNullOrWhiteSpace(account))
                    return Results.BadRequest(new { error = "MissingPlayer" });

                PlayerProgressLookup player = FindPlayerProgressLookup(playerName, account);
                if (player == null)
                    return Results.NotFound(new { error = "PlayerNotFound", player = playerName, account });

                return player.Online
                    ? Results.Ok(DynamicQuestRuntimeService.Instance.GetProgressSnapshot(player.OnlinePlayer))
                    : Results.Ok(DynamicQuestRuntimeService.Instance.GetProgressSnapshot(player.PlayerKey, player.PlayerName, false));
            });

            api.MapGet("/api/world/dynamic-quests/progress/summary", (HttpContext context) =>
                Results.Ok(DynamicQuestRuntimeService.Instance.GetProgressSummary(ReadLimit(context, 100))));

            api.MapGet("/api/world/dynamic-quests/progress/cleanup-plan", (HttpContext context) =>
                Results.Ok(DynamicQuestRuntimeService.Instance.GetProgressCleanupPlan(
                    ReadLimit(context, 100),
                    ReadSeconds(context, "staleSeconds", 3600))));

            api.MapPost("/api/world/dynamic-quests/progress/cleanup-plan/cancel-completed", (HttpContext context) =>
                Results.Ok(DynamicQuestRuntimeService.Instance.CancelCompletedCleanupCandidates(
                    ReadLimit(context, 100),
                    ReadSeconds(context, "staleSeconds", 3600),
                    Query(context, "reason", "cleanup_completed_active_progress"))));

            api.MapPost("/api/world/dynamic-quests/progress/cleanup-plan/advance-timeouts", (HttpContext context) =>
                Results.Ok(DynamicQuestRuntimeService.Instance.AdvanceTimedOutCleanupCandidates(
                    ReadLimit(context, 100),
                    Query(context, "reason", "cleanup_timeout"))));

            api.MapPost("/api/world/dynamic-quests/progress/cancel", (HttpContext context) =>
            {
                string playerName = Query(context, "player", Query(context, "name"));
                string account = Query(context, "account");
                string reason = Query(context, "reason", "dummy_test_cleanup");

                if (string.IsNullOrWhiteSpace(playerName) && string.IsNullOrWhiteSpace(account))
                    return Results.BadRequest(new { error = "MissingPlayer" });

                PlayerProgressLookup player = FindPlayerProgressLookup(playerName, account);
                if (player == null)
                    return Results.NotFound(new { error = "PlayerNotFound", player = playerName, account });

                int cancelled = DynamicQuestRuntimeService.Instance.CancelActiveProgressForPlayer(
                    player.PlayerKey,
                    player.PlayerName,
                    reason);

                return Results.Ok(new
                {
                    player = player.PlayerName,
                    playerKey = player.PlayerKey,
                    account,
                    reason,
                    cancelled,
                    progress = player.Online
                        ? DynamicQuestRuntimeService.Instance.GetProgressSnapshot(player.OnlinePlayer)
                        : DynamicQuestRuntimeService.Instance.GetProgressSnapshot(player.PlayerKey, player.PlayerName, false)
                });
            });

            api.MapGet("/api/world/dynamic-quests/timeline", (HttpContext context) =>
            {
                string playerName = Query(context, "player", Query(context, "name"));
                string account = Query(context, "account");

                if (string.IsNullOrWhiteSpace(playerName) && string.IsNullOrWhiteSpace(account))
                    return Results.BadRequest(new { error = "MissingPlayer" });

                PlayerProgressLookup player = FindPlayerProgressLookup(playerName, account);
                if (player == null)
                    return Results.NotFound(new { error = "PlayerNotFound", player = playerName, account });

                int limit = ReadLimit(context, 50);
                return player.Online
                    ? Results.Ok(DynamicQuestRuntimeService.Instance.GetTimelineSnapshot(player.OnlinePlayer, limit))
                    : Results.Ok(DynamicQuestRuntimeService.Instance.GetTimelineSnapshot(player.PlayerKey, player.PlayerName, false, limit));
            });

            api.MapGet("/api/world/dynamic-quests/story-cache", (HttpContext context) =>
                Results.Ok(DynamicQuestSeedService.Instance.GetStoryCacheSnapshot(
                    ReadLimit(context, 50),
                    ReadBool(context, "includeText"))));

            api.MapGet("/api/world/dynamic-quests/story-cache/prefill-plan", (HttpContext context) =>
                Results.Ok(DynamicQuestSeedService.Instance.GetStoryCachePrefillPlanSnapshotFromWorld(
                    ReadLimit(context, 20))));

            api.MapGet("/api/world/dynamic-quests/story-config", () =>
            {
                DynamicQuestSeedOptions seedOptions = DynamicQuestSeedOptions.FromProperties();

                return Results.Ok(new
                {
                    autoSeed = new
                    {
                        enabled = Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_ENABLED,
                        useLlm = Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_USE_LLM,
                        configuredMaxQuests = Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_MAX_QUESTS,
                        effectiveMaxQuests = seedOptions.MaxQuests,
                        definitionCount = seedOptions.Definitions.Count
                    },
                    providerOrder = Properties.KDAOC_DYNAMIC_QUEST_STORY_PROVIDER_ORDER,
                    minimumScore = Properties.KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE,
                    compareProviders = new
                    {
                        enabled = Properties.KDAOC_DYNAMIC_QUEST_STORY_COMPARE_PROVIDERS_ENABLED,
                        maxPerPrefill = Properties.KDAOC_DYNAMIC_QUEST_STORY_COMPARE_MAX_PER_PREFILL
                    },
                    mainLocal = new
                    {
                        apiUrl = Properties.WORLDAI_LLM_API_URL,
                        model = Properties.WORLDAI_LLM_MODEL,
                        timeoutSeconds = Properties.WORLDAI_LLM_TIMEOUT_SECONDS
                    },
                    openai = new
                    {
                        model = Properties.KDAOC_DYNAMIC_QUEST_STORY_OPENAI_MODEL,
                        perMinuteLimit = Properties.KDAOC_DYNAMIC_QUEST_STORY_OPENAI_PER_MINUTE_LIMIT,
                        dailyLimit = Properties.KDAOC_DYNAMIC_QUEST_STORY_OPENAI_DAILY_LIMIT,
                        dailyTokenLimit = Properties.KDAOC_DYNAMIC_QUEST_STORY_OPENAI_DAILY_TOKEN_LIMIT
                    },
                    gemini = new
                    {
                        model = Properties.KDAOC_DYNAMIC_QUEST_STORY_GEMINI_MODEL,
                        perMinuteLimit = Properties.KDAOC_DYNAMIC_QUEST_STORY_GEMINI_PER_MINUTE_LIMIT,
                        dailyLimit = Properties.KDAOC_DYNAMIC_QUEST_STORY_GEMINI_DAILY_LIMIT,
                        dailyTokenLimit = Properties.KDAOC_DYNAMIC_QUEST_STORY_GEMINI_DAILY_TOKEN_LIMIT,
                        resetDelayMinutes = Properties.KDAOC_DYNAMIC_QUEST_STORY_GEMINI_RESET_DELAY_MINUTES,
                        resetWindowMinutes = Properties.KDAOC_DYNAMIC_QUEST_STORY_GEMINI_RESET_WINDOW_MINUTES
                    },
                    secondaryLocal = new
                    {
                        apiUrl = Properties.KDAOC_DYNAMIC_QUEST_STORY_SECONDARY_LLM_API_URL,
                        model = Properties.KDAOC_DYNAMIC_QUEST_STORY_SECONDARY_LLM_MODEL
                    },
                    quotaUsage = new
                    {
                        openai = ReadDailyQuotaUsage("openai"),
                        gemini = ReadDailyQuotaUsage("gemini")
                    },
                    cache = new
                    {
                        maxTemplates = Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_MAX_TEMPLATES,
                        pruneCount = Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PRUNE_COUNT,
                        prefillBatchSize = Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE,
                        worldPrefillEnabled = Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED,
                        worldPrefillMaxCandidates = Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_MAX_CANDIDATES,
                        offerEnabled = Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_OFFER_ENABLED,
                        offerMinSlots = Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_OFFER_MIN_SLOTS
                    }
                });
            });

            api.MapGet("/api/world/dynamic-quests/seed/status", () =>
                Results.Ok(DynamicQuestSeedRuntime.LastSummary ?? new DynamicQuestSeedSummary
                {
                    Enabled = Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_ENABLED,
                    DynamicQuestEnabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED
                }));

            api.MapGet("/api/world/llm/config", () =>
                Results.Ok(new
                {
                    apiUrl = Properties.WORLDAI_LLM_API_URL,
                    model = Properties.WORLDAI_LLM_MODEL,
                    timeoutSeconds = Properties.WORLDAI_LLM_TIMEOUT_SECONDS
                }));

            api.MapGet("/api/world/llm/check", () =>
            {
                OpenAiCompatibleLlmResultGenerator generator = new(
                    Properties.WORLDAI_LLM_API_URL,
                    Properties.WORLDAI_LLM_MODEL,
                    Properties.WORLDAI_LLM_TIMEOUT_SECONDS);
                return Results.Ok(generator.CheckConnection(Properties.WORLDAI_LLM_API_URL));
            });

            api.MapPost("/api/world/llm/jobs/claim", (HttpContext context) =>
                Results.Ok(LlmJobQueueService.Instance.ClaimPendingWorkItems(ReadLimit(context, 10))));

            api.MapPost("/api/world/llm/jobs/reclaim", (HttpContext context) =>
                Results.Ok(new
                {
                    reclaimed = LlmJobQueueService.Instance.ReclaimStaleClaimedJobs(ReadMinutes(context, 15))
                }));

            api.MapPost("/api/world/llm/jobs/{jobId}/result", SubmitLlmJobResult);

            api.MapPost("/api/world/llm/jobs/{jobId}/retry", (string jobId) =>
            {
                LlmJobSubmissionResult result = LlmJobQueueService.Instance.RetryJob(jobId);
                return result.Accepted ? Results.Ok(result) : Results.BadRequest(result);
            });

            api.MapPost("/api/world/llm/jobs/{jobId}/reject", RejectLlmJob);
        }

        private static object ReadDailyQuotaUsage(string providerName)
        {
            string safeProvider = SanitizeQuotaProviderName(providerName);
            string callKey = $"kdaoc_dynamic_quest_story_quota_{safeProvider}_daily_usage";
            string tokenKey = $"kdaoc_dynamic_quest_story_quota_{safeProvider}_daily_tokens";
            (string callDay, int calls) = ReadQuotaRow(callKey);
            (string tokenDay, int tokens) = ReadQuotaRow(tokenKey);

            return new
            {
                callKey,
                callDay,
                calls,
                tokenKey,
                tokenDay,
                tokens
            };
        }

        private static (string day, int used) ReadQuotaRow(string key)
        {
            DbServerProperty row = GameServer.Database?.SelectObject<DbServerProperty>(DB.Column("`Key`").IsEqualTo(key));
            string day = string.Empty;
            int used = 0;
            string[] parts = (row?.Value ?? string.Empty).Split('|');
            if (parts.Length == 2)
            {
                day = parts[0].Trim();
                int.TryParse(parts[1], out used);
            }

            return (day, used);
        }

        private static string SanitizeQuotaProviderName(string providerName)
        {
            System.Text.StringBuilder builder = new();
            foreach (char c in (providerName ?? string.Empty).Trim().ToLowerInvariant())
            {
                if ((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9'))
                    builder.Append(c);
                else if (c == '-' || c == '_')
                    builder.Append('_');
            }

            return builder.ToString().Trim('_');
        }

        private static int ReadLimit(HttpContext context, int defaultLimit)
        {
            string raw = context.Request.Query["limit"].FirstOrDefault();

            if (!int.TryParse(raw, out int limit))
                return defaultLimit;

            return limit;
        }

        private static ushort ReadUShort(HttpContext context, string key, ushort defaultValue = 0)
        {
            string raw = context.Request.Query[key].FirstOrDefault();

            if (!ushort.TryParse(raw, out ushort value))
                return defaultValue;

            return value;
        }

        private static bool ReadBool(HttpContext context, string key, bool defaultValue = false)
        {
            string raw = context.Request.Query[key].FirstOrDefault();
            if (string.IsNullOrWhiteSpace(raw))
                return defaultValue;

            string value = raw.Trim();
            if (bool.TryParse(value, out bool parsed))
                return parsed;

            return string.Equals(value, "1", System.StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "yes", System.StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "y", System.StringComparison.OrdinalIgnoreCase);
        }

        private static int ReadMinutes(HttpContext context, int defaultMinutes)
        {
            string raw = context.Request.Query["minutes"].FirstOrDefault();

            if (!int.TryParse(raw, out int minutes))
                return defaultMinutes;

            return minutes;
        }

        private static int ReadSeconds(HttpContext context, string key, int defaultSeconds)
        {
            string raw = context.Request.Query[key].FirstOrDefault();

            if (!int.TryParse(raw, out int seconds))
                return defaultSeconds;

            return seconds;
        }

        private static string Query(HttpContext context, string key, string defaultValue = "")
        {
            string value = context.Request.Query[key].FirstOrDefault();
            return string.IsNullOrWhiteSpace(value) ? defaultValue : value.Trim();
        }

        private static PlayerProgressLookup FindPlayerProgressLookup(string name, string account)
        {
            GamePlayer onlinePlayer = FindPlayer(name, account);
            if (onlinePlayer != null)
            {
                return new PlayerProgressLookup
                {
                    Online = true,
                    OnlinePlayer = onlinePlayer,
                    PlayerName = onlinePlayer.Name ?? string.Empty,
                    PlayerKey = !string.IsNullOrWhiteSpace(onlinePlayer.InternalID)
                        ? onlinePlayer.InternalID
                        : onlinePlayer.Name ?? string.Empty
                };
            }

            DbCoreCharacter character = FindOfflineCharacter(name, account);
            if (character == null)
                return null;

            return new PlayerProgressLookup
            {
                Online = false,
                PlayerName = character.Name ?? string.Empty,
                PlayerKey = !string.IsNullOrWhiteSpace(character.ObjectId)
                    ? character.ObjectId
                    : character.Name ?? string.Empty
            };
        }

        private static GamePlayer FindPlayer(string name, string account)
        {
            if (!string.IsNullOrWhiteSpace(name))
            {
                GamePlayer player = ClientService.Instance.GetPlayerByExactName(name);

                if (IsUsablePlayer(player))
                    return player;
            }

            return ClientService.Instance.GetClients()
                .Select(client => client.Player)
                .FirstOrDefault(player =>
                    IsUsablePlayer(player) &&
                    ((!string.IsNullOrWhiteSpace(name) && string.Equals(player.Name, name, System.StringComparison.OrdinalIgnoreCase)) ||
                     (!string.IsNullOrWhiteSpace(account) && string.Equals(player.Client?.Account?.Name, account, System.StringComparison.OrdinalIgnoreCase))));
        }

        private static DbCoreCharacter FindOfflineCharacter(string name, string account)
        {
            if (!string.IsNullOrWhiteSpace(name))
            {
                DbCoreCharacter byName = DOLDB<DbCoreCharacter>.SelectObject(DB.Column("Name").IsEqualTo(name));
                if (byName != null &&
                    (string.IsNullOrWhiteSpace(account) ||
                     string.Equals(byName.AccountName, account, System.StringComparison.OrdinalIgnoreCase)))
                    return byName;
            }

            if (string.IsNullOrWhiteSpace(account))
                return null;

            return DOLDB<DbCoreCharacter>
                .SelectObjects(DB.Column("AccountName").IsEqualTo(account))
                .OrderByDescending(character => character.LastPlayed)
                .FirstOrDefault();
        }

        private static bool IsUsablePlayer(GamePlayer player)
        {
            return player != null &&
                   player.ObjectState is GameObject.eObjectState.Active &&
                   player.Client?.ClientState is GameClient.eClientState.Playing;
        }

        private sealed class PlayerProgressLookup
        {
            public bool Online { get; set; }
            public GamePlayer OnlinePlayer { get; set; }
            public string PlayerName { get; set; } = string.Empty;
            public string PlayerKey { get; set; } = string.Empty;
        }

        private static async Task<IResult> SubmitLlmJobResult(HttpContext context, string jobId)
        {
            using JsonDocument document = await JsonDocument.ParseAsync(context.Request.Body);
            string resultJson = ExtractResultJson(document.RootElement);
            LlmJobSubmissionResult result = LlmJobQueueService.Instance.SubmitExternalResult(jobId, resultJson);

            return result.Accepted ? Results.Ok(result) : Results.BadRequest(result);
        }

        private static async Task<IResult> RejectLlmJob(HttpContext context, string jobId)
        {
            using StreamReader reader = new(context.Request.Body);
            string reason = ExtractReason(await reader.ReadToEndAsync());
            LlmJobSubmissionResult result = LlmJobQueueService.Instance.RejectJob(jobId, reason);

            return result.Accepted ? Results.Ok(result) : Results.BadRequest(result);
        }

        private static string ExtractResultJson(JsonElement root)
        {
            if (root.ValueKind == JsonValueKind.Object &&
                root.TryGetProperty("resultJson", out JsonElement resultJson) &&
                resultJson.ValueKind == JsonValueKind.String)
                return resultJson.GetString() ?? string.Empty;

            return root.GetRawText();
        }

        private static string ExtractReason(string body)
        {
            if (string.IsNullOrWhiteSpace(body))
                return "Rejected by API.";

            try
            {
                using JsonDocument document = JsonDocument.Parse(body);

                if (document.RootElement.ValueKind == JsonValueKind.Object &&
                    document.RootElement.TryGetProperty("reason", out JsonElement reason) &&
                    reason.ValueKind == JsonValueKind.String)
                    return reason.GetString() ?? "Rejected by API.";
            }
            catch (JsonException)
            {
                // Plain text bodies are accepted for quick local operator scripts.
            }

            return body.Trim();
        }
    }
}
