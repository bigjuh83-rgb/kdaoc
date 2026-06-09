using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using DOL.Database;

namespace DOL.GS.WorldAI
{
    public static class WorldAiJobTypes
    {
        public const string WorldNews = "WorldNews";
        public const string ChronicleEntry = "ChronicleEntry";
    }

    public static class WorldAiJobStatuses
    {
        public const string Pending = "Pending";
        public const string Claimed = "Claimed";
        public const string Completed = "Completed";
        public const string Failed = "Failed";
        public const string Rejected = "Rejected";
    }

    public static class WorldAiValidationStatuses
    {
        public const string Valid = "Valid";
        public const string Rejected = "Rejected";
    }

    public static class WorldAiEventTypes
    {
        public const string BossBorn = "bossborn";
        public const string MobAscended = "mobascended";
        public const string MobMutated = "mobmutated";
    }

    public static class WorldAiImportance
    {
        public const string Minor = "Minor";
        public const string Normal = "Normal";
        public const string Major = "Major";
        public const string Legendary = "Legendary";
    }

    public interface IWorldEventRepository
    {
        bool Add(DbWorldEventLog row);
        DbWorldEventLog Find(string eventId);
        DbWorldEventLog GetLatestEventByType(string eventType);
        IList<DbWorldEventLog> GetPendingApprovalEvents(int limit);
        IList<DbWorldEventLog> GetPublicEvents(int limit);
        bool Save(DbWorldEventLog row);
    }

    public interface ILlmJobRepository
    {
        bool Add(DbLlmJob row);
        DbLlmJob Find(string jobId);
        IDictionary<string, int> CountByStatus();
        IList<DbLlmJob> GetJobs(int limit);
        IList<DbLlmJob> GetJobsByEvent(string eventId);
        IList<DbLlmJob> GetPendingJobs(int limit);
        bool Save(DbLlmJob row);
    }

    public interface ILlmResultRepository
    {
        bool Add(DbLlmResult row);
        IList<DbLlmResult> GetByJob(string jobId);
    }

    public interface ILlmResultGenerator
    {
        string Generate(DbLlmJob job, DbWorldEventLog worldEvent);
    }

    public sealed class LlmValidationResult
    {
        public LlmValidationResult(bool isValid, IList<string> errors)
        {
            IsValid = isValid;
            Errors = errors ?? Array.Empty<string>();
        }

        public bool IsValid { get; }
        public IList<string> Errors { get; }
    }

    public sealed class LlmJobProcessingSummary
    {
        public int Processed { get; set; }
        public int Completed { get; set; }
        public int Rejected { get; set; }
        public int Failed { get; set; }
    }

    public sealed class LlmWorkItem
    {
        public string JobId { get; set; }
        public string JobType { get; set; }
        public string EventId { get; set; }
        public string Language { get; set; }
        public string PayloadJson { get; set; }
        public string SchemaJson { get; set; }
        public string Instructions { get; set; }
        public DateTime CreatedAt { get; set; }
    }

    public sealed class LlmJobSubmissionResult
    {
        public bool Accepted { get; set; }
        public string JobId { get; set; }
        public string Status { get; set; }
        public IList<string> Errors { get; set; } = Array.Empty<string>();
        public string Message { get; set; }
    }

    public sealed class LlmConnectionCheckResult
    {
        public bool IsAvailable { get; set; }
        public string ApiUrl { get; set; }
        public string Model { get; set; }
        public IList<string> AvailableModels { get; set; } = Array.Empty<string>();
        public string Error { get; set; }
    }

    public sealed class LlmQueueHealth
    {
        public IDictionary<string, int> Counts { get; set; } = new Dictionary<string, int>();
        public int ActiveJobs { get; set; }
        public int OldestPendingAgeSeconds { get; set; }
        public int OldestClaimedAgeSeconds { get; set; }
    }

    public sealed class LlmJobDetail
    {
        public string JobId { get; set; }
        public string JobType { get; set; }
        public string Status { get; set; }
        public string EventId { get; set; }
        public string EventType { get; set; }
        public string ActorName { get; set; }
        public string Region { get; set; }
        public string Language { get; set; }
        public int AttemptCount { get; set; }
        public string LastError { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
    }

    public sealed class WorldEventLocation
    {
        public string Name { get; set; }
        public string ActorName { get; set; }
        public ushort RegionId { get; set; }
        public int X { get; set; }
        public int Y { get; set; }
        public int Z { get; set; }
        public ushort Heading { get; set; }
    }

    public sealed class WorldEventSeedResult
    {
        public WorldEventSeedResult(DbWorldEventLog worldEvent, IList<DbLlmJob> jobs)
        {
            Event = worldEvent;
            Jobs = jobs ?? Array.Empty<DbLlmJob>();
        }

        public DbWorldEventLog Event { get; }
        public IList<DbLlmJob> Jobs { get; }
    }

    public sealed class WorldEventRecordRequest
    {
        public string EventType { get; set; }
        public string Region { get; set; }
        public string ActorName { get; set; }
        public string Language { get; set; }
        public string RawDataJson { get; set; }
        public int AliveDays { get; set; }
        public int Kills { get; set; }
        public ushort RegionId { get; set; }
        public int X { get; set; }
        public int Y { get; set; }
        public int Z { get; set; }
        public ushort Heading { get; set; }
        public bool RequiresGmApproval { get; set; }
    }

    public sealed class WorldNewsItem
    {
        public string EventId { get; set; }
        public string Title { get; set; }
        public string Body { get; set; }
        public string Importance { get; set; }
        public DateTime CreatedAt { get; set; }
    }

    public sealed class WorldEventItem
    {
        public string EventId { get; set; }
        public string EventType { get; set; }
        public string Importance { get; set; }
        public string Region { get; set; }
        public string ActorName { get; set; }
        public string Title { get; set; }
        public string PublicText { get; set; }
        public string Chronicle { get; set; }
        public DateTime CreatedAt { get; set; }
    }

    public sealed class LlmResultValidationService
    {
        private static readonly HashSet<string> AllowedImportances = new(StringComparer.OrdinalIgnoreCase)
        {
            WorldAiImportance.Minor,
            WorldAiImportance.Normal,
            WorldAiImportance.Major,
            WorldAiImportance.Legendary
        };

        private static readonly HashSet<string> ForbiddenFields = new(StringComparer.OrdinalIgnoreCase)
        {
            "hp",
            "damage",
            "reward",
            "gold",
            "realm_points",
            "drop_rate",
            "spawn_count",
            "cooldown",
            "ban",
            "command"
        };

        public LlmValidationResult Validate(string jobType, string json)
        {
            List<string> errors = new();

            if (string.IsNullOrWhiteSpace(json))
                return new LlmValidationResult(false, new[] { "JSON is empty." });

            try
            {
                using JsonDocument document = JsonDocument.Parse(json);

                if (document.RootElement.ValueKind != JsonValueKind.Object)
                {
                    errors.Add("JSON root must be an object.");
                    return new LlmValidationResult(false, errors);
                }

                CollectForbiddenFields(document.RootElement, errors);

                switch (jobType)
                {
                    case WorldAiJobTypes.WorldNews:
                        ValidateWorldNews(document.RootElement, errors);
                        break;
                    case WorldAiJobTypes.ChronicleEntry:
                        ValidateChronicleEntry(document.RootElement, errors);
                        break;
                    default:
                        errors.Add($"Unknown job type: {jobType}");
                        break;
                }
            }
            catch (JsonException e)
            {
                errors.Add($"Invalid JSON: {e.Message}");
            }

            return new LlmValidationResult(errors.Count == 0, errors);
        }

        private static void ValidateWorldNews(JsonElement root, IList<string> errors)
        {
            ValidateRequiredString(root, "title", 120, errors);
            ValidateRequiredString(root, "body", 500, errors);

            if (!TryGetNonEmptyString(root, "importance", out string importance))
            {
                errors.Add("Missing required field: importance");
                return;
            }

            if (!AllowedImportances.Contains(importance))
                errors.Add("Invalid importance.");
        }

        private static void ValidateChronicleEntry(JsonElement root, IList<string> errors)
        {
            ValidateRequiredString(root, "summary", 200, errors);
            ValidateRequiredString(root, "chronicle", 1000, errors);
        }

        private static void ValidateRequiredString(JsonElement root, string field, int maxLength, IList<string> errors)
        {
            if (!TryGetNonEmptyString(root, field, out string value))
            {
                errors.Add($"Missing required field: {field}");
                return;
            }

            if (value.Length > maxLength)
                errors.Add($"Field too long: {field}");
        }

        private static bool TryGetNonEmptyString(JsonElement root, string field, out string value)
        {
            value = string.Empty;

            if (!root.TryGetProperty(field, out JsonElement element) || element.ValueKind != JsonValueKind.String)
                return false;

            value = element.GetString() ?? string.Empty;
            return !string.IsNullOrWhiteSpace(value);
        }

        private static void CollectForbiddenFields(JsonElement element, IList<string> errors)
        {
            HashSet<string> found = new(StringComparer.OrdinalIgnoreCase);
            CollectForbiddenFields(element, found);

            foreach (string field in found.OrderBy(field => field))
                errors.Add($"Forbidden field: {field}");
        }

        private static void CollectForbiddenFields(JsonElement element, ISet<string> found)
        {
            switch (element.ValueKind)
            {
                case JsonValueKind.Object:
                    foreach (JsonProperty property in element.EnumerateObject())
                    {
                        if (ForbiddenFields.Contains(property.Name))
                            found.Add(property.Name);

                        CollectForbiddenFields(property.Value, found);
                    }
                    break;
                case JsonValueKind.Array:
                    foreach (JsonElement item in element.EnumerateArray())
                        CollectForbiddenFields(item, found);
                    break;
            }
        }
    }

    public sealed class FakeLlmResultGenerator : ILlmResultGenerator
    {
        public string Generate(DbLlmJob job, DbWorldEventLog worldEvent)
        {
            if (job.JobType == WorldAiJobTypes.ChronicleEntry)
            {
                return JsonSerializer.Serialize(new
                {
                    summary = $"{worldEvent.ActorName}의 출현",
                    chronicle = $"{worldEvent.Region}에서 {worldEvent.ActorName}이 세력을 모으기 시작했다. 아직 세계를 바꾸는 효과는 적용되지 않았지만, 이 사건은 서버 역사에 기록되었다."
                });
            }

            return JsonSerializer.Serialize(new
            {
                title = $"{worldEvent.ActorName} 출현",
                body = $"{worldEvent.Region}에서 새로운 위협이 보고되었습니다. 모험가들은 이 소식을 서버 뉴스에서 확인할 수 있습니다.",
                importance = string.IsNullOrWhiteSpace(worldEvent.Importance) ? WorldAiImportance.Normal : worldEvent.Importance
            });
        }
    }

    public sealed class OpenAiCompatibleLlmResultGenerator : ILlmResultGenerator
    {
        private readonly HttpClient m_httpClient;
        private readonly string m_model;

        public OpenAiCompatibleLlmResultGenerator(string baseUrl, string model, int timeoutSeconds)
            : this(CreateHttpClient(baseUrl, timeoutSeconds), model)
        {
        }

        public OpenAiCompatibleLlmResultGenerator(HttpClient httpClient, string model)
        {
            m_httpClient = httpClient ?? throw new ArgumentNullException(nameof(httpClient));
            m_model = string.IsNullOrWhiteSpace(model) ? "gemma-4-e4b-it" : model;
        }

        public string Generate(DbLlmJob job, DbWorldEventLog worldEvent)
        {
            return GenerateAsync(job, worldEvent).GetAwaiter().GetResult();
        }

        public LlmConnectionCheckResult CheckConnection(string apiUrl)
        {
            try
            {
                string responseJson = m_httpClient.GetStringAsync("v1/models").GetAwaiter().GetResult();
                List<string> models = ExtractModelIds(responseJson);

                return new LlmConnectionCheckResult
                {
                    IsAvailable = true,
                    ApiUrl = apiUrl,
                    Model = m_model,
                    AvailableModels = models,
                    Error = string.Empty
                };
            }
            catch (Exception e)
            {
                return new LlmConnectionCheckResult
                {
                    IsAvailable = false,
                    ApiUrl = apiUrl,
                    Model = m_model,
                    AvailableModels = Array.Empty<string>(),
                    Error = e.Message
                };
            }
        }

        private async System.Threading.Tasks.Task<string> GenerateAsync(DbLlmJob job, DbWorldEventLog worldEvent)
        {
            object request = new
            {
                model = m_model,
                messages = new[]
                {
                    new
                    {
                        role = "system",
                        content = "You are a JSON-only MMORPG world writer. Return exactly one valid JSON object. Do not use markdown. Do not include hp, damage, reward, gold, realm_points, drop_rate, spawn_count, cooldown, ban, or command fields."
                    },
                    new
                    {
                        role = "user",
                        content = BuildPrompt(job, worldEvent)
                    }
                },
                temperature = 0.4,
                max_tokens = job.JobType == WorldAiJobTypes.ChronicleEntry ? 700 : 350
            };

            string requestJson = JsonSerializer.Serialize(request);
            using StringContent content = new(requestJson, Encoding.UTF8, "application/json");
            using HttpResponseMessage response = await m_httpClient.PostAsync("v1/chat/completions", content).ConfigureAwait(false);
            string body = await response.Content.ReadAsStringAsync().ConfigureAwait(false);

            if (!response.IsSuccessStatusCode)
                throw new InvalidOperationException($"LLM server returned {(int)response.StatusCode}: {body}");

            return NormalizeJsonContent(ExtractAssistantContent(body));
        }

        private static HttpClient CreateHttpClient(string baseUrl, int timeoutSeconds)
        {
            if (string.IsNullOrWhiteSpace(baseUrl))
                throw new ArgumentException("LLM API URL is empty.", nameof(baseUrl));

            string normalized = baseUrl.TrimEnd('/') + "/";

            return new HttpClient
            {
                BaseAddress = new Uri(normalized),
                Timeout = TimeSpan.FromSeconds(timeoutSeconds <= 0 ? 30 : timeoutSeconds)
            };
        }

        private static string BuildPrompt(DbLlmJob job, DbWorldEventLog worldEvent)
        {
            string schemaDescription = job.JobType == WorldAiJobTypes.ChronicleEntry
                ? "Required JSON fields: summary(string, Korean, max 200 chars), chronicle(string, Korean, max 1000 chars)."
                : "Required JSON fields: title(string, Korean, max 120 chars), body(string, Korean, max 500 chars), importance(one of Minor, Normal, Major, Legendary).";

            return string.Join("\n", new[]
            {
                schemaDescription,
                "Write naturally in Korean for a Dark Age of Camelot private server.",
                "This is narrative/news text only. Do not invent gameplay rewards or numeric balance.",
                $"Job type: {job.JobType}",
                $"Language: {job.Language}",
                $"Event type: {worldEvent.EventType}",
                $"Actor: {worldEvent.ActorName}",
                $"Region: {worldEvent.Region}",
                $"Importance: {worldEvent.Importance}",
                $"Raw event JSON: {job.PayloadJson}"
            });
        }

        private static string ExtractAssistantContent(string responseJson)
        {
            using JsonDocument document = JsonDocument.Parse(responseJson);
            JsonElement root = document.RootElement;

            if (!root.TryGetProperty("choices", out JsonElement choices) ||
                choices.ValueKind != JsonValueKind.Array ||
                choices.GetArrayLength() == 0)
                throw new InvalidOperationException("LLM response did not contain choices.");

            JsonElement choice = choices[0];

            if (choice.TryGetProperty("message", out JsonElement message) &&
                message.TryGetProperty("content", out JsonElement content) &&
                content.ValueKind == JsonValueKind.String)
                return content.GetString() ?? string.Empty;

            if (choice.TryGetProperty("text", out JsonElement text) &&
                text.ValueKind == JsonValueKind.String)
                return text.GetString() ?? string.Empty;

            throw new InvalidOperationException("LLM response did not contain assistant content.");
        }

        private static string NormalizeJsonContent(string content)
        {
            if (string.IsNullOrWhiteSpace(content))
                return string.Empty;

            string trimmed = content.Trim();

            if (trimmed.StartsWith("```", StringComparison.Ordinal))
            {
                int firstLine = trimmed.IndexOf('\n');
                int lastFence = trimmed.LastIndexOf("```", StringComparison.Ordinal);

                if (firstLine >= 0 && lastFence > firstLine)
                    trimmed = trimmed.Substring(firstLine + 1, lastFence - firstLine - 1).Trim();
            }

            return trimmed;
        }

        private static List<string> ExtractModelIds(string responseJson)
        {
            List<string> models = new();

            using JsonDocument document = JsonDocument.Parse(responseJson);

            if (!document.RootElement.TryGetProperty("data", out JsonElement data) ||
                data.ValueKind != JsonValueKind.Array)
                return models;

            foreach (JsonElement model in data.EnumerateArray())
            {
                if (model.TryGetProperty("id", out JsonElement id) &&
                    id.ValueKind == JsonValueKind.String &&
                    !string.IsNullOrWhiteSpace(id.GetString()))
                    models.Add(id.GetString());
            }

            return models;
        }
    }

    public sealed class LlmJobQueueService
    {
        private const int DefaultProcessLimit = 10;
        private const int MaxProcessLimit = 100;

        public static LlmJobQueueService Instance { get; } = new(
            new DatabaseWorldEventRepository(),
            new DatabaseLlmJobRepository(),
            new DatabaseLlmResultRepository(),
            new LlmResultValidationService(),
            new FakeLlmResultGenerator());

        private readonly IWorldEventRepository m_events;
        private readonly ILlmJobRepository m_jobs;
        private readonly ILlmResultRepository m_results;
        private readonly LlmResultValidationService m_validator;
        private readonly ILlmResultGenerator m_generator;

        public LlmJobQueueService(
            IWorldEventRepository events,
            ILlmJobRepository jobs,
            ILlmResultRepository results,
            LlmResultValidationService validator,
            ILlmResultGenerator generator)
        {
            m_events = events ?? throw new ArgumentNullException(nameof(events));
            m_jobs = jobs ?? throw new ArgumentNullException(nameof(jobs));
            m_results = results ?? throw new ArgumentNullException(nameof(results));
            m_validator = validator ?? throw new ArgumentNullException(nameof(validator));
            m_generator = generator ?? throw new ArgumentNullException(nameof(generator));
        }

        public DbLlmJob Enqueue(string jobType, string eventId, string language, string payloadJson)
        {
            DateTime now = DateTime.UtcNow;
            DbLlmJob job = new()
            {
                JobId = Guid.NewGuid().ToString("N"),
                JobType = jobType ?? string.Empty,
                Status = WorldAiJobStatuses.Pending,
                EventId = eventId ?? string.Empty,
                Language = string.IsNullOrWhiteSpace(language) ? "kr" : language,
                PayloadJson = string.IsNullOrWhiteSpace(payloadJson) ? "{}" : payloadJson,
                AttemptCount = 0,
                LastError = string.Empty,
                CreatedAt = now,
                UpdatedAt = now
            };

            if (!m_jobs.Add(job))
                throw new InvalidOperationException("Failed to enqueue LLM job.");

            return job;
        }

        public IDictionary<string, int> CountByStatus()
        {
            Dictionary<string, int> counts = new(StringComparer.OrdinalIgnoreCase)
            {
                [WorldAiJobStatuses.Pending] = 0,
                [WorldAiJobStatuses.Claimed] = 0,
                [WorldAiJobStatuses.Completed] = 0,
                [WorldAiJobStatuses.Failed] = 0,
                [WorldAiJobStatuses.Rejected] = 0
            };

            foreach (KeyValuePair<string, int> pair in m_jobs.CountByStatus())
                counts[pair.Key] = pair.Value;

            return counts;
        }

        public IList<LlmWorkItem> GetPendingWorkItems(int count)
        {
            int limit = ClampLimit(count, DefaultProcessLimit, MaxProcessLimit);

            return m_jobs.GetPendingJobs(limit)
                .Select(ToWorkItem)
                .ToList();
        }

        public IList<LlmWorkItem> ClaimPendingWorkItems(int count)
        {
            int limit = ClampLimit(count, DefaultProcessLimit, MaxProcessLimit);
            DateTime now = DateTime.UtcNow;
            List<LlmWorkItem> claimed = new();

            foreach (DbLlmJob job in m_jobs.GetPendingJobs(limit))
            {
                job.Status = WorldAiJobStatuses.Claimed;
                job.UpdatedAt = now;
                m_jobs.Save(job);
                claimed.Add(ToWorkItem(job));
            }

            return claimed;
        }

        public IList<LlmJobDetail> GetJobDetails(int count)
        {
            int limit = ClampLimit(count, DefaultProcessLimit, MaxProcessLimit);

            return m_jobs.GetJobs(limit)
                .Select(ToJobDetail)
                .ToList();
        }

        public IList<DbLlmJob> GetJobsByEvent(string eventId)
        {
            if (string.IsNullOrWhiteSpace(eventId))
                return Array.Empty<DbLlmJob>();

            return m_jobs.GetJobsByEvent(eventId);
        }

        public LlmQueueHealth GetQueueHealth()
        {
            DateTime now = DateTime.UtcNow;
            IDictionary<string, int> counts = CountByStatus();
            IList<DbLlmJob> jobs = m_jobs.GetJobs(MaxProcessLimit);

            DateTime? oldestPending = jobs
                .Where(job => job.Status == WorldAiJobStatuses.Pending)
                .OrderBy(job => job.CreatedAt)
                .Select(job => (DateTime?)job.CreatedAt)
                .FirstOrDefault();
            DateTime? oldestClaimed = jobs
                .Where(job => job.Status == WorldAiJobStatuses.Claimed)
                .OrderBy(job => job.UpdatedAt)
                .Select(job => (DateTime?)job.UpdatedAt)
                .FirstOrDefault();

            return new LlmQueueHealth
            {
                Counts = counts,
                ActiveJobs = GetCount(counts, WorldAiJobStatuses.Pending) + GetCount(counts, WorldAiJobStatuses.Claimed) + GetCount(counts, WorldAiJobStatuses.Failed),
                OldestPendingAgeSeconds = AgeSeconds(now, oldestPending),
                OldestClaimedAgeSeconds = AgeSeconds(now, oldestClaimed)
            };
        }

        public int ReclaimStaleClaimedJobs(int olderThanMinutes)
        {
            int minutes = olderThanMinutes <= 0 ? 15 : Math.Min(olderThanMinutes, 1440);
            DateTime cutoff = DateTime.UtcNow.AddMinutes(-minutes);
            List<DbLlmJob> staleJobs = m_jobs.GetJobs(MaxProcessLimit)
                .Where(job => job.Status == WorldAiJobStatuses.Claimed && job.UpdatedAt <= cutoff)
                .ToList();

            foreach (DbLlmJob job in staleJobs)
            {
                job.Status = WorldAiJobStatuses.Pending;
                job.LastError = $"Reclaimed from stale Claimed state after {minutes} minutes.";
                job.UpdatedAt = DateTime.UtcNow;
                m_jobs.Save(job);
            }

            return staleJobs.Count;
        }

        public int RejectDuplicateActiveJobs(string eventType, string actorName)
        {
            List<DbLlmJob> duplicateCandidates = m_jobs.GetJobs(MaxProcessLimit)
                .Where(job => job.Status == WorldAiJobStatuses.Pending || job.Status == WorldAiJobStatuses.Claimed)
                .Where(job =>
                {
                    DbWorldEventLog worldEvent = m_events.Find(job.EventId);
                    return worldEvent != null &&
                        worldEvent.EventType == eventType &&
                        worldEvent.ActorName == actorName;
                })
                .GroupBy(job => job.JobType)
                .SelectMany(group => group
                    .OrderByDescending(job => job.UpdatedAt)
                    .Skip(1))
                .ToList();

            foreach (DbLlmJob job in duplicateCandidates)
            {
                job.Status = WorldAiJobStatuses.Rejected;
                job.LastError = "Rejected as duplicate sample job.";
                job.UpdatedAt = DateTime.UtcNow;
                m_jobs.Save(job);
            }

            return duplicateCandidates.Count;
        }

        public LlmJobSubmissionResult SubmitExternalResult(string jobId, string resultJson)
        {
            if (string.IsNullOrWhiteSpace(jobId))
            {
                return new LlmJobSubmissionResult
                {
                    Accepted = false,
                    JobId = string.Empty,
                    Status = WorldAiJobStatuses.Failed,
                    Errors = new[] { "Job id is required." },
                    Message = "Job id is required."
                };
            }

            DbLlmJob job = m_jobs.Find(jobId);

            if (job == null)
            {
                return new LlmJobSubmissionResult
                {
                    Accepted = false,
                    JobId = jobId,
                    Status = WorldAiJobStatuses.Failed,
                    Errors = new[] { "Job was not found." },
                    Message = "Job was not found."
                };
            }

            if (job.Status != WorldAiJobStatuses.Pending && job.Status != WorldAiJobStatuses.Claimed)
            {
                return new LlmJobSubmissionResult
                {
                    Accepted = false,
                    JobId = job.JobId,
                    Status = job.Status,
                    Errors = new[] { "Job cannot accept a result in its current status." },
                    Message = "Job cannot accept a result in its current status."
                };
            }

            DbWorldEventLog worldEvent = m_events.Find(job.EventId);

            if (worldEvent == null)
            {
                MarkFailed(job, "World event was not found.");
                return new LlmJobSubmissionResult
                {
                    Accepted = false,
                    JobId = job.JobId,
                    Status = WorldAiJobStatuses.Failed,
                    Errors = new[] { "World event was not found." },
                    Message = "World event was not found."
                };
            }

            return ProcessJobResult(job, worldEvent, resultJson);
        }

        public LlmJobSubmissionResult RetryJob(string jobId)
        {
            DbLlmJob job = m_jobs.Find(jobId);

            if (job == null)
            {
                return new LlmJobSubmissionResult
                {
                    Accepted = false,
                    JobId = jobId ?? string.Empty,
                    Status = WorldAiJobStatuses.Failed,
                    Errors = new[] { "Job was not found." },
                    Message = "Job was not found."
                };
            }

            if (job.Status == WorldAiJobStatuses.Completed)
            {
                return new LlmJobSubmissionResult
                {
                    Accepted = false,
                    JobId = job.JobId,
                    Status = job.Status,
                    Errors = new[] { "Completed jobs cannot be retried." },
                    Message = "Completed jobs cannot be retried."
                };
            }

            job.Status = WorldAiJobStatuses.Pending;
            job.LastError = string.Empty;
            job.UpdatedAt = DateTime.UtcNow;
            m_jobs.Save(job);

            return new LlmJobSubmissionResult
            {
                Accepted = true,
                JobId = job.JobId,
                Status = job.Status,
                Errors = Array.Empty<string>(),
                Message = "Job returned to Pending."
            };
        }

        public LlmJobSubmissionResult RejectJob(string jobId, string reason)
        {
            DbLlmJob job = m_jobs.Find(jobId);

            if (job == null)
            {
                return new LlmJobSubmissionResult
                {
                    Accepted = false,
                    JobId = jobId ?? string.Empty,
                    Status = WorldAiJobStatuses.Failed,
                    Errors = new[] { "Job was not found." },
                    Message = "Job was not found."
                };
            }

            if (job.Status == WorldAiJobStatuses.Completed)
            {
                return new LlmJobSubmissionResult
                {
                    Accepted = false,
                    JobId = job.JobId,
                    Status = job.Status,
                    Errors = new[] { "Completed jobs cannot be rejected." },
                    Message = "Completed jobs cannot be rejected."
                };
            }

            job.Status = WorldAiJobStatuses.Rejected;
            job.LastError = string.IsNullOrWhiteSpace(reason) ? "Rejected by GM." : reason;
            job.UpdatedAt = DateTime.UtcNow;
            m_jobs.Save(job);

            return new LlmJobSubmissionResult
            {
                Accepted = true,
                JobId = job.JobId,
                Status = job.Status,
                Errors = Array.Empty<string>(),
                Message = "Job rejected."
            };
        }

        public LlmJobProcessingSummary ProcessFake(int count)
        {
            return ProcessWithGenerator(count, m_generator);
        }

        public LlmJobProcessingSummary ProcessWithGenerator(int count, ILlmResultGenerator generator)
        {
            if (generator == null)
                throw new ArgumentNullException(nameof(generator));

            int limit = ClampLimit(count, DefaultProcessLimit, MaxProcessLimit);
            LlmJobProcessingSummary summary = new();

            foreach (LlmWorkItem workItem in ClaimPendingWorkItems(limit))
            {
                summary.Processed++;
                DbLlmJob job = m_jobs.Find(workItem.JobId);

                try
                {
                    DbWorldEventLog worldEvent = m_events.Find(job.EventId);

                    if (worldEvent == null)
                    {
                        MarkFailed(job, "World event was not found.");
                        summary.Failed++;
                        continue;
                    }

                    string json = generator.Generate(job, worldEvent);
                    LlmJobSubmissionResult result = ProcessJobResult(job, worldEvent, json);

                    if (result.Status == WorldAiJobStatuses.Completed)
                        summary.Completed++;
                    else if (result.Status == WorldAiJobStatuses.Rejected)
                        summary.Rejected++;
                    else
                        summary.Failed++;
                }
                catch (Exception e)
                {
                    MarkFailed(job, e.Message);
                    summary.Failed++;
                }
            }

            return summary;
        }

        private LlmJobDetail ToJobDetail(DbLlmJob job)
        {
            DbWorldEventLog worldEvent = m_events.Find(job.EventId);

            return new LlmJobDetail
            {
                JobId = job.JobId,
                JobType = job.JobType,
                Status = job.Status,
                EventId = job.EventId,
                EventType = worldEvent?.EventType ?? string.Empty,
                ActorName = worldEvent?.ActorName ?? string.Empty,
                Region = worldEvent?.Region ?? string.Empty,
                Language = job.Language,
                AttemptCount = job.AttemptCount,
                LastError = job.LastError,
                CreatedAt = job.CreatedAt,
                UpdatedAt = job.UpdatedAt
            };
        }

        private LlmJobSubmissionResult ProcessJobResult(DbLlmJob job, DbWorldEventLog worldEvent, string json)
        {
            job.AttemptCount++;
            job.UpdatedAt = DateTime.UtcNow;

            LlmValidationResult validation = m_validator.Validate(job.JobType, json);
            DbLlmResult result = CreateResult(job, json, validation);

            if (!m_results.Add(result))
            {
                MarkFailed(job, "Failed to save LLM result.");
                return new LlmJobSubmissionResult
                {
                    Accepted = false,
                    JobId = job.JobId,
                    Status = WorldAiJobStatuses.Failed,
                    Errors = new[] { "Failed to save LLM result." },
                    Message = "Failed to save LLM result."
                };
            }

            if (!validation.IsValid)
            {
                job.Status = WorldAiJobStatuses.Rejected;
                job.LastError = string.Join("; ", validation.Errors);
                job.UpdatedAt = DateTime.UtcNow;
                m_jobs.Save(job);

                return new LlmJobSubmissionResult
                {
                    Accepted = false,
                    JobId = job.JobId,
                    Status = WorldAiJobStatuses.Rejected,
                    Errors = validation.Errors,
                    Message = "LLM result was rejected by validation."
                };
            }

            ApplyValidResult(job, worldEvent, json);
            job.Status = WorldAiJobStatuses.Completed;
            job.LastError = string.Empty;
            job.UpdatedAt = DateTime.UtcNow;
            m_events.Save(worldEvent);
            m_jobs.Save(job);

            return new LlmJobSubmissionResult
            {
                Accepted = true,
                JobId = job.JobId,
                Status = WorldAiJobStatuses.Completed,
                Errors = Array.Empty<string>(),
                Message = "LLM result accepted."
            };
        }

        private static LlmWorkItem ToWorkItem(DbLlmJob job)
        {
            return new LlmWorkItem
            {
                JobId = job.JobId,
                JobType = job.JobType,
                EventId = job.EventId,
                Language = job.Language,
                PayloadJson = job.PayloadJson,
                SchemaJson = GetSchemaJson(job.JobType),
                Instructions = GetInstructions(job.JobType),
                CreatedAt = job.CreatedAt
            };
        }

        private static string GetSchemaJson(string jobType)
        {
            if (jobType == WorldAiJobTypes.ChronicleEntry)
            {
                return JsonSerializer.Serialize(new
                {
                    type = "object",
                    required = new[] { "summary", "chronicle" },
                    properties = new
                    {
                        summary = new { type = "string", maxLength = 200 },
                        chronicle = new { type = "string", maxLength = 1000 }
                    }
                });
            }

            return JsonSerializer.Serialize(new
            {
                type = "object",
                required = new[] { "title", "body", "importance" },
                properties = new
                {
                    title = new { type = "string", maxLength = 120 },
                    body = new { type = "string", maxLength = 500 },
                    importance = new { type = "string", @enum = new[] { WorldAiImportance.Minor, WorldAiImportance.Normal, WorldAiImportance.Major, WorldAiImportance.Legendary } }
                }
            });
        }

        private static string GetInstructions(string jobType)
        {
            string baseInstruction = "Return only one JSON object. Do not include numeric combat, reward, spawn, ban, or command fields.";

            if (jobType == WorldAiJobTypes.ChronicleEntry)
                return baseInstruction + " Required fields: summary, chronicle.";

            return baseInstruction + " Required fields: title, body, importance.";
        }

        private void MarkFailed(DbLlmJob job, string error)
        {
            job.Status = WorldAiJobStatuses.Failed;
            job.LastError = error ?? string.Empty;
            job.UpdatedAt = DateTime.UtcNow;
            m_jobs.Save(job);
        }

        private static DbLlmResult CreateResult(DbLlmJob job, string json, LlmValidationResult validation)
        {
            DateTime now = DateTime.UtcNow;

            return new DbLlmResult
            {
                ResultId = Guid.NewGuid().ToString("N"),
                JobId = job.JobId,
                Status = validation.IsValid ? WorldAiJobStatuses.Completed : WorldAiJobStatuses.Rejected,
                ResultJson = json ?? string.Empty,
                ValidationStatus = validation.IsValid ? WorldAiValidationStatuses.Valid : WorldAiValidationStatuses.Rejected,
                ValidationErrors = validation.IsValid ? string.Empty : string.Join("\n", validation.Errors),
                CreatedAt = now,
                UpdatedAt = now
            };
        }

        private static void ApplyValidResult(DbLlmJob job, DbWorldEventLog worldEvent, string json)
        {
            using JsonDocument document = JsonDocument.Parse(json);
            JsonElement root = document.RootElement;
            DateTime now = DateTime.UtcNow;

            if (job.JobType == WorldAiJobTypes.ChronicleEntry)
            {
                string summary = GetString(root, "summary");
                string chronicle = GetString(root, "chronicle");

                if (string.IsNullOrWhiteSpace(worldEvent.PublicTitle))
                    worldEvent.PublicTitle = summary;

                if (string.IsNullOrWhiteSpace(worldEvent.PublicText))
                    worldEvent.PublicText = summary;

                worldEvent.ChronicleText = chronicle;
                worldEvent.IsPublic = !worldEvent.RequiresGmApproval;
                worldEvent.UpdatedAt = now;
                return;
            }

            worldEvent.PublicTitle = GetString(root, "title");
            worldEvent.PublicText = GetString(root, "body");
            worldEvent.Importance = GetString(root, "importance");
            worldEvent.IsPublic = !worldEvent.RequiresGmApproval;
            worldEvent.UpdatedAt = now;
        }

        private static string GetString(JsonElement root, string field)
        {
            if (!root.TryGetProperty(field, out JsonElement value) || value.ValueKind != JsonValueKind.String)
                return string.Empty;

            return value.GetString() ?? string.Empty;
        }

        private static int ClampLimit(int count, int defaultLimit, int maxLimit)
        {
            if (count <= 0)
                return defaultLimit;

            return Math.Min(count, maxLimit);
        }

        private static int AgeSeconds(DateTime now, DateTime? value)
        {
            if (!value.HasValue)
                return 0;

            return Math.Max(0, (int)(now - value.Value).TotalSeconds);
        }

        private static int GetCount(IDictionary<string, int> counts, string status)
        {
            return counts.TryGetValue(status, out int value) ? value : 0;
        }
    }

    public sealed class WorldEventService
    {
        private const ushort BossBornSampleRegionId = 1;
        private const int BossBornSampleX = 561443;
        private const int BossBornSampleY = 511128;
        private const int BossBornSampleZ = 2280;
        private const ushort BossBornSampleHeading = 2048;

        public static WorldEventService Instance { get; } = new(new DatabaseWorldEventRepository(), LlmJobQueueService.Instance);

        private readonly IWorldEventRepository m_events;
        private readonly LlmJobQueueService m_queue;

        public WorldEventService(IWorldEventRepository events, LlmJobQueueService queue)
        {
            m_events = events ?? throw new ArgumentNullException(nameof(events));
            m_queue = queue ?? throw new ArgumentNullException(nameof(queue));
        }

        public WorldEventSeedResult SeedBossBornSample()
        {
            DbWorldEventLog existing = m_events.GetLatestEventByType(WorldAiEventTypes.BossBorn);

            if (IsSameBossBornSample(existing))
                return new WorldEventSeedResult(existing, m_queue.GetJobsByEvent(existing.EventId));

            int aliveDays = 12;
            int kills = 83;

            return RecordEvent(new WorldEventRecordRequest
            {
                EventType = WorldAiEventTypes.BossBorn,
                Region = "북부 숲",
                ActorName = "붉은 송곳니 그락",
                Language = "kr",
                AliveDays = aliveDays,
                Kills = kills,
                RegionId = BossBornSampleRegionId,
                X = BossBornSampleX,
                Y = BossBornSampleY,
                Z = BossBornSampleZ,
                Heading = BossBornSampleHeading,
                RawDataJson = JsonSerializer.Serialize(new Dictionary<string, object>
                {
                    ["boss_type"] = "goblin chieftain",
                    ["alive_days"] = aliveDays,
                    ["kills"] = kills,
                    ["region"] = "northern forest",
                    ["player_behavior"] = "ranged heavy",
                    ["location"] = new Dictionary<string, object>
                    {
                        ["name"] = WorldAiEventTypes.BossBorn,
                        ["region_id"] = BossBornSampleRegionId,
                        ["x"] = BossBornSampleX,
                        ["y"] = BossBornSampleY,
                        ["z"] = BossBornSampleZ,
                        ["heading"] = BossBornSampleHeading
                    }
                }),
                RequiresGmApproval = false
            });
        }

        public int RejectDuplicateBossBornSampleJobs()
        {
            return m_queue.RejectDuplicateActiveJobs(WorldAiEventTypes.BossBorn, "붉은 송곳니 그락");
        }

        public WorldEventSeedResult RecordEvent(WorldEventRecordRequest request)
        {
            if (request == null)
                throw new ArgumentNullException(nameof(request));

            DateTime now = DateTime.UtcNow;
            DbWorldEventLog worldEvent = new()
            {
                EventId = Guid.NewGuid().ToString("N"),
                EventType = Normalize(request.EventType, "world_event"),
                Importance = CalculateImportance(request.AliveDays, request.Kills),
                Region = Normalize(request.Region, "알 수 없는 지역"),
                ActorName = Normalize(request.ActorName, "이름 없는 존재"),
                Language = Normalize(request.Language, "kr"),
                RawDataJson = Normalize(request.RawDataJson, "{}"),
                PublicTitle = string.Empty,
                PublicText = string.Empty,
                ChronicleText = string.Empty,
                GmNote = request.EventType == WorldAiEventTypes.BossBorn
                    ? "Seeded by /worldai seed bossborn."
                    : "Recorded by WorldEventService.",
                IsPublic = false,
                RequiresGmApproval = request.RequiresGmApproval,
                CreatedAt = now,
                UpdatedAt = now
            };

            if (!m_events.Add(worldEvent))
                throw new InvalidOperationException("Failed to save world event.");

            List<DbLlmJob> jobs = new()
            {
                m_queue.Enqueue(WorldAiJobTypes.WorldNews, worldEvent.EventId, "kr", worldEvent.RawDataJson),
                m_queue.Enqueue(WorldAiJobTypes.ChronicleEntry, worldEvent.EventId, "kr", worldEvent.RawDataJson)
            };

            return new WorldEventSeedResult(worldEvent, jobs);
        }

        public bool TryGetLatestEventLocation(string eventType, out WorldEventLocation location)
        {
            location = null;

            if (string.IsNullOrWhiteSpace(eventType))
                return false;

            DbWorldEventLog worldEvent = m_events.GetLatestEventByType(eventType);

            if (worldEvent == null || !TryReadLocation(worldEvent.RawDataJson, out location))
                return false;

            location.ActorName = worldEvent.ActorName;
            return true;
        }

        public IList<DbWorldEventLog> GetPendingApprovalEvents(int limit)
        {
            return m_events.GetPendingApprovalEvents(ClampLimit(limit, 20, 100));
        }

        public bool ApprovePublicEvent(string eventIdOrPrefix)
        {
            DbWorldEventLog worldEvent = ResolvePendingApprovalEvent(eventIdOrPrefix);

            if (worldEvent == null || string.IsNullOrWhiteSpace(worldEvent.PublicText))
                return false;

            worldEvent.IsPublic = true;
            worldEvent.RequiresGmApproval = false;
            worldEvent.UpdatedAt = DateTime.UtcNow;
            return m_events.Save(worldEvent);
        }

        public string CalculateImportance(int aliveDays, int kills)
        {
            if (aliveDays >= 30 || kills >= 200)
                return WorldAiImportance.Legendary;

            if (aliveDays >= 7 || kills >= 50)
                return WorldAiImportance.Major;

            if (aliveDays >= 1 || kills >= 10)
                return WorldAiImportance.Normal;

            return WorldAiImportance.Minor;
        }

        private DbWorldEventLog ResolvePendingApprovalEvent(string eventIdOrPrefix)
        {
            if (string.IsNullOrWhiteSpace(eventIdOrPrefix))
                return null;

            DbWorldEventLog exact = m_events.Find(eventIdOrPrefix);

            if (exact != null)
                return exact;

            return m_events.GetPendingApprovalEvents(100)
                .FirstOrDefault(row => row.EventId.StartsWith(eventIdOrPrefix, StringComparison.OrdinalIgnoreCase));
        }

        private static bool IsSameBossBornSample(DbWorldEventLog worldEvent)
        {
            if (worldEvent == null ||
                worldEvent.EventType != WorldAiEventTypes.BossBorn ||
                worldEvent.ActorName != "붉은 송곳니 그락" ||
                !TryReadLocation(worldEvent.RawDataJson, out WorldEventLocation location))
                return false;

            return location.RegionId == BossBornSampleRegionId &&
                location.X == BossBornSampleX &&
                location.Y == BossBornSampleY &&
                location.Z == BossBornSampleZ;
        }

        private static string Normalize(string value, string fallback)
        {
            return string.IsNullOrWhiteSpace(value) ? fallback : value;
        }

        private static bool TryReadLocation(string rawDataJson, out WorldEventLocation location)
        {
            location = null;

            if (string.IsNullOrWhiteSpace(rawDataJson))
                return false;

            try
            {
                using JsonDocument document = JsonDocument.Parse(rawDataJson);

                if (!document.RootElement.TryGetProperty("location", out JsonElement locationElement) ||
                    locationElement.ValueKind != JsonValueKind.Object)
                    return false;

                if (!TryGetUInt16(locationElement, "region_id", out ushort regionId) &&
                    !TryGetUInt16(locationElement, "regionId", out regionId))
                    return false;

                if (!TryGetInt(locationElement, "x", out int x) ||
                    !TryGetInt(locationElement, "y", out int y) ||
                    !TryGetInt(locationElement, "z", out int z))
                    return false;

                TryGetUInt16(locationElement, "heading", out ushort heading);

                location = new WorldEventLocation
                {
                    Name = TryGetString(locationElement, "name", out string name) ? name : string.Empty,
                    RegionId = regionId,
                    X = x,
                    Y = y,
                    Z = z,
                    Heading = heading
                };

                return true;
            }
            catch (JsonException)
            {
                return false;
            }
        }

        private static bool TryGetString(JsonElement element, string field, out string value)
        {
            value = string.Empty;

            if (!element.TryGetProperty(field, out JsonElement property) || property.ValueKind != JsonValueKind.String)
                return false;

            value = property.GetString() ?? string.Empty;
            return !string.IsNullOrWhiteSpace(value);
        }

        private static bool TryGetInt(JsonElement element, string field, out int value)
        {
            value = 0;

            if (!element.TryGetProperty(field, out JsonElement property))
                return false;

            return property.ValueKind == JsonValueKind.Number && property.TryGetInt32(out value);
        }

        private static bool TryGetUInt16(JsonElement element, string field, out ushort value)
        {
            value = 0;

            if (!TryGetInt(element, field, out int parsed) || parsed < ushort.MinValue || parsed > ushort.MaxValue)
                return false;

            value = (ushort)parsed;
            return true;
        }

        private static int ClampLimit(int value, int defaultValue, int maxValue)
        {
            if (value <= 0)
                return defaultValue;

            return Math.Min(value, maxValue);
        }
    }

    public sealed class WorldNewsService
    {
        private const int DefaultNewsLimit = 10;
        private const int DefaultEventLimit = 20;
        private const int MaxLimit = 100;

        public static WorldNewsService Instance { get; } = new(new DatabaseWorldEventRepository());

        private readonly IWorldEventRepository m_events;

        public WorldNewsService(IWorldEventRepository events)
        {
            m_events = events ?? throw new ArgumentNullException(nameof(events));
        }

        public IList<WorldNewsItem> GetNews(int limit)
        {
            return m_events.GetPublicEvents(ClampLimit(limit, DefaultNewsLimit))
                .Where(row => !string.IsNullOrWhiteSpace(row.PublicText))
                .Select(row => new WorldNewsItem
                {
                    EventId = row.EventId,
                    Title = row.PublicTitle,
                    Body = row.PublicText,
                    Importance = row.Importance,
                    CreatedAt = row.CreatedAt
                })
                .ToList();
        }

        public IList<WorldEventItem> GetEvents(int limit)
        {
            return m_events.GetPublicEvents(ClampLimit(limit, DefaultEventLimit))
                .Select(ToEventItem)
                .ToList();
        }

        public IList<WorldEventItem> GetHistory(int limit)
        {
            return m_events.GetPublicEvents(ClampLimit(limit, DefaultEventLimit))
                .Where(row => !string.IsNullOrWhiteSpace(row.ChronicleText))
                .Select(ToEventItem)
                .ToList();
        }

        private static WorldEventItem ToEventItem(DbWorldEventLog row)
        {
            return new WorldEventItem
            {
                EventId = row.EventId,
                EventType = row.EventType,
                Importance = row.Importance,
                Region = row.Region,
                ActorName = row.ActorName,
                Title = row.PublicTitle,
                PublicText = row.PublicText,
                Chronicle = row.ChronicleText,
                CreatedAt = row.CreatedAt
            };
        }

        private static int ClampLimit(int limit, int defaultLimit)
        {
            if (limit <= 0)
                return defaultLimit;

            return Math.Min(limit, MaxLimit);
        }
    }

    public sealed class DatabaseWorldEventRepository : IWorldEventRepository
    {
        public bool Add(DbWorldEventLog row)
        {
            return GameServer.Database.AddObject(row);
        }

        public DbWorldEventLog Find(string eventId)
        {
            return GameServer.Database.FindObjectByKey<DbWorldEventLog>(eventId);
        }

        public DbWorldEventLog GetLatestEventByType(string eventType)
        {
            return GameServer.Database.SelectAllObjects<DbWorldEventLog>()
                .Where(row => row.EventType == eventType)
                .OrderByDescending(row => row.CreatedAt)
                .FirstOrDefault();
        }

        public IList<DbWorldEventLog> GetPendingApprovalEvents(int limit)
        {
            return GameServer.Database.SelectAllObjects<DbWorldEventLog>()
                .Where(row => row.RequiresGmApproval && !row.IsPublic && !string.IsNullOrWhiteSpace(row.PublicText))
                .OrderByDescending(row => row.UpdatedAt)
                .Take(limit)
                .ToList();
        }

        public IList<DbWorldEventLog> GetPublicEvents(int limit)
        {
            return GameServer.Database.SelectAllObjects<DbWorldEventLog>()
                .Where(row => row.IsPublic)
                .OrderByDescending(row => row.CreatedAt)
                .Take(limit)
                .ToList();
        }

        public bool Save(DbWorldEventLog row)
        {
            return GameServer.Database.SaveObject(row);
        }
    }

    public sealed class DatabaseLlmJobRepository : ILlmJobRepository
    {
        public bool Add(DbLlmJob row)
        {
            return GameServer.Database.AddObject(row);
        }

        public DbLlmJob Find(string jobId)
        {
            return GameServer.Database.FindObjectByKey<DbLlmJob>(jobId);
        }

        public IDictionary<string, int> CountByStatus()
        {
            return GameServer.Database.SelectAllObjects<DbLlmJob>()
                .GroupBy(row => row.Status)
                .ToDictionary(group => group.Key, group => group.Count());
        }

        public IList<DbLlmJob> GetJobs(int limit)
        {
            return GameServer.Database.SelectAllObjects<DbLlmJob>()
                .OrderByDescending(row => row.UpdatedAt)
                .Take(limit)
                .ToList();
        }

        public IList<DbLlmJob> GetJobsByEvent(string eventId)
        {
            return GameServer.Database.SelectAllObjects<DbLlmJob>()
                .Where(row => row.EventId == eventId)
                .OrderBy(row => row.CreatedAt)
                .ToList();
        }

        public IList<DbLlmJob> GetPendingJobs(int limit)
        {
            return GameServer.Database.SelectAllObjects<DbLlmJob>()
                .Where(row => row.Status == WorldAiJobStatuses.Pending)
                .OrderBy(row => row.CreatedAt)
                .Take(limit)
                .ToList();
        }

        public bool Save(DbLlmJob row)
        {
            return GameServer.Database.SaveObject(row);
        }
    }

    public sealed class DatabaseLlmResultRepository : ILlmResultRepository
    {
        public bool Add(DbLlmResult row)
        {
            return GameServer.Database.AddObject(row);
        }

        public IList<DbLlmResult> GetByJob(string jobId)
        {
            return GameServer.Database.SelectAllObjects<DbLlmResult>()
                .Where(row => row.JobId == jobId)
                .OrderBy(row => row.CreatedAt)
                .ToList();
        }
    }
}
