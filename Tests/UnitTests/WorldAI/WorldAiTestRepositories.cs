using System;
using System.Collections.Generic;
using System.Linq;
using DOL.Database;
using DOL.GS.WorldAI;

namespace DOL.GS.Tests
{
    internal sealed class FakeWorldEventRepository : IWorldEventRepository
    {
        public readonly Dictionary<string, DbWorldEventLog> Rows = new();

        public bool Add(DbWorldEventLog row)
        {
            Rows[row.EventId] = row;
            return true;
        }

        public DbWorldEventLog Find(string eventId)
        {
            Rows.TryGetValue(eventId, out DbWorldEventLog row);
            return row;
        }

        public DbWorldEventLog GetLatestEventByType(string eventType)
        {
            return Rows.Values
                .Where(row => row.EventType == eventType)
                .OrderByDescending(row => row.CreatedAt)
                .FirstOrDefault();
        }

        public IList<DbWorldEventLog> GetPublicEvents(int limit)
        {
            return Rows.Values
                .Where(row => row.IsPublic)
                .OrderByDescending(row => row.CreatedAt)
                .Take(limit)
                .ToList();
        }

        public IList<DbWorldEventLog> GetPendingApprovalEvents(int limit)
        {
            return Rows.Values
                .Where(row => row.RequiresGmApproval && !row.IsPublic && !string.IsNullOrWhiteSpace(row.PublicText))
                .OrderByDescending(row => row.UpdatedAt)
                .Take(limit)
                .ToList();
        }

        public bool Save(DbWorldEventLog row)
        {
            Rows[row.EventId] = row;
            return true;
        }
    }

    internal sealed class FakeLlmJobRepository : ILlmJobRepository
    {
        public readonly Dictionary<string, DbLlmJob> Rows = new();

        public bool Add(DbLlmJob row)
        {
            Rows[row.JobId] = row;
            return true;
        }

        public DbLlmJob Find(string jobId)
        {
            Rows.TryGetValue(jobId, out DbLlmJob row);
            return row;
        }

        public IDictionary<string, int> CountByStatus()
        {
            return Rows.Values
                .GroupBy(row => row.Status)
                .ToDictionary(group => group.Key, group => group.Count());
        }

        public IList<DbLlmJob> GetJobs(int limit)
        {
            return Rows.Values
                .OrderByDescending(row => row.UpdatedAt)
                .Take(limit)
                .ToList();
        }

        public IList<DbLlmJob> GetJobsByEvent(string eventId)
        {
            return Rows.Values
                .Where(row => row.EventId == eventId)
                .OrderBy(row => row.CreatedAt)
                .ToList();
        }

        public IList<DbLlmJob> GetPendingJobs(int limit)
        {
            return Rows.Values
                .Where(row => row.Status == WorldAiJobStatuses.Pending)
                .OrderBy(row => row.CreatedAt)
                .Take(limit)
                .ToList();
        }

        public bool Save(DbLlmJob row)
        {
            Rows[row.JobId] = row;
            return true;
        }
    }

    internal sealed class FakeLlmResultRepository : ILlmResultRepository
    {
        public readonly Dictionary<string, DbLlmResult> Rows = new();

        public bool Add(DbLlmResult row)
        {
            Rows[row.ResultId] = row;
            return true;
        }

        public IList<DbLlmResult> GetByJob(string jobId)
        {
            return Rows.Values
                .Where(row => row.JobId == jobId)
                .OrderBy(row => row.CreatedAt)
                .ToList();
        }
    }

    internal sealed class FakeDynamicQuestProgressRepository : IDynamicQuestProgressRepository
    {
        public readonly Dictionary<string, DbDynamicQuestProgress> Rows = new();

        public bool Add(DbDynamicQuestProgress row)
        {
            Rows[row.ProgressId] = row;
            return true;
        }

        public DbDynamicQuestProgress Find(string progressId)
        {
            Rows.TryGetValue(progressId, out DbDynamicQuestProgress row);
            return row;
        }

        public IList<DbDynamicQuestProgress> GetActive(int limit)
        {
            limit = Math.Clamp(limit <= 0 ? 100 : limit, 1, 500);
            return Rows.Values
                .Where(row => row.IsActive && !row.Failed)
                .OrderByDescending(row => row.UpdatedAt)
                .Take(limit)
                .ToList();
        }

        public IList<DbDynamicQuestProgress> GetActiveForDifferentWorldRevision(string currentWorldRevision)
        {
            return Rows.Values
                .Where(row =>
                    row.IsActive &&
                    !row.Failed &&
                    !string.IsNullOrWhiteSpace(row.WorldRevision) &&
                    !string.Equals(row.WorldRevision, currentWorldRevision, StringComparison.OrdinalIgnoreCase))
                .OrderBy(row => row.AcceptedAt)
                .ToList();
        }

        public IList<DbDynamicQuestProgress> GetActiveForMissingQuestIds(ISet<string> activeQuestIds)
        {
            HashSet<string> normalizedActiveQuestIds = new(activeQuestIds ?? new HashSet<string>(), StringComparer.OrdinalIgnoreCase);
            return Rows.Values
                .Where(row =>
                    row.IsActive &&
                    !row.Failed &&
                    !string.IsNullOrWhiteSpace(row.QuestId) &&
                    !normalizedActiveQuestIds.Contains(row.QuestId))
                .OrderBy(row => row.AcceptedAt)
                .ToList();
        }

        public IList<DbDynamicQuestProgress> GetByPlayer(string playerKey)
        {
            return Rows.Values
                .Where(row => string.Equals(row.PlayerKey, playerKey, StringComparison.OrdinalIgnoreCase))
                .OrderBy(row => row.AcceptedAt)
                .ToList();
        }

        public bool Save(DbDynamicQuestProgress row)
        {
            Rows[row.ProgressId] = row;
            return true;
        }
    }

    internal sealed class InvalidLlmResultGenerator : ILlmResultGenerator
    {
        public string Generate(DbLlmJob job, DbWorldEventLog worldEvent)
        {
            return "{\"title\":\"깨진 결과\",\"body\":\"보상 수치가 들어간 결과입니다.\",\"importance\":\"Normal\",\"gold\":100}";
        }
    }

    internal static class WorldAiTestData
    {
        public static DbWorldEventLog CreateEvent(DateTime? createdAt = null, bool isPublic = false)
        {
            return new DbWorldEventLog
            {
                EventId = Guid.NewGuid().ToString("N"),
                EventType = WorldAiEventTypes.BossBorn,
                Importance = WorldAiImportance.Major,
                Region = "북부 숲",
                ActorName = "붉은 송곳니 그락",
                Language = "kr",
                RawDataJson = "{\"source\":\"unit-test\"}",
                PublicTitle = isPublic ? "붉은 송곳니 그락 출현" : string.Empty,
                PublicText = isPublic ? "북부 숲에서 새로운 위협이 발견되었습니다." : string.Empty,
                ChronicleText = isPublic ? "붉은 송곳니 그락이 북부 숲의 역사에 이름을 남겼습니다." : string.Empty,
                GmNote = "GM only",
                IsPublic = isPublic,
                RequiresGmApproval = false,
                CreatedAt = createdAt ?? DateTime.UtcNow,
                UpdatedAt = createdAt ?? DateTime.UtcNow
            };
        }
    }
}
