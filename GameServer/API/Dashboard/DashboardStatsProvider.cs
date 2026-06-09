using System;
using System.Collections.Generic;
using System.Linq;
using DOL.Database;
using DOL.GS.Keeps;
using DOL.GS.ServerRules;

namespace DOL.GS.API.Dashboard
{
    internal sealed class DashboardStatsProvider
    {
        private static readonly TimeSpan LiveCacheDuration = TimeSpan.FromSeconds(15);
        private static readonly TimeSpan DataCacheDuration = TimeSpan.FromSeconds(60);

        private readonly object m_cacheLock = new();
        private readonly DashboardPerformanceSampler m_performanceSampler = new();
        private readonly Dictionary<string, CacheEntry<DashboardHistoryResponse>> m_historyCache = new();
        private readonly Dictionary<string, CacheEntry<DashboardRealmActivityResponse>> m_realmActivityCache = new();
        private readonly Dictionary<string, CacheEntry<DashboardClassHistoryResponse>> m_classHistoryCache = new();

        private DashboardLiveResponse m_live;
        private CacheEntry<DashboardHeraldResponse> m_heraldCache;
        private CacheEntry<DashboardOperatorStatusResponse> m_operatorCache;
        private DateTime m_liveExpiresAt;

        public DashboardLiveResponse GetLive()
        {
            DateTime now = DateTime.UtcNow;

            lock (m_cacheLock)
            {
                if (m_live != null && now < m_liveExpiresAt)
                    return m_live;

                List<GamePlayer> albionPlayers = GetPlayersOfRealm(eRealm.Albion);
                List<GamePlayer> midgardPlayers = GetPlayersOfRealm(eRealm.Midgard);
                List<GamePlayer> hiberniaPlayers = GetPlayersOfRealm(eRealm.Hibernia);
                IEnumerable<GamePlayer> onlinePlayers = GetOnlinePlayers(albionPlayers, midgardPlayers, hiberniaPlayers);

                IEnumerable<DashboardClassSample> classSamples = onlinePlayers
                    .Select(CreateClassSample)
                    .Where(sample => sample != null);

                DateTime startedAt = GameServer.Instance.StartupTime;
                m_live = new DashboardLiveResponse(
                    ClientService.Instance.ClientCount,
                    DashboardAggregation.BuildRealmStats(albionPlayers.Count, midgardPlayers.Count, hiberniaPlayers.Count),
                    DashboardAggregation.BuildClassStats(classSamples),
                    m_performanceSampler.GetSnapshot(),
                    new Utils().GetUptime(startedAt).Uptime,
                    startedAt,
                    now);
                m_liveExpiresAt = now.Add(LiveCacheDuration);

                return m_live;
            }
        }

        public DashboardHistoryResponse GetHistory(string range)
        {
            TimeSpan duration = ParseRange(range, TimeSpan.FromHours(24));
            string rangeName = ToRangeName(duration);
            DateTime nowUtc = DateTime.UtcNow;

            lock (m_cacheLock)
            {
                if (m_historyCache.TryGetValue(rangeName, out CacheEntry<DashboardHistoryResponse> cached) && nowUtc < cached.ExpiresAt)
                    return WithCurrentHistoryPoint(cached.Value, GetLive(), nowUtc);

                DateTime now = DateTime.Now;
                DateTime start = now.Add(-duration);
                IList<DbServerStat> rows = GameServer.Database.SelectObjects<DbServerStat>(DB.Column("StatDate").IsGreaterThan(start));
                DashboardLiveResponse live = GetLive();
                List<DashboardHistoryPoint> points = DashboardAggregation.NormalizeHistory(rows, now, duration).ToList();
                points.Add(CreateCurrentHistoryPoint(live, nowUtc));

                DashboardHistoryResponse response = CreateHistoryResponse(rangeName, points, nowUtc);

                m_historyCache[rangeName] = new CacheEntry<DashboardHistoryResponse>(response, nowUtc.Add(DataCacheDuration));
                return response;
            }
        }

        private static DashboardHistoryPoint CreateCurrentHistoryPoint(DashboardLiveResponse live, DateTime now)
        {
            IReadOnlyList<DashboardRealmStats> realms = live?.Realms ?? Array.Empty<DashboardRealmStats>();

            return new DashboardHistoryPoint(
                now,
                Math.Max(0, live?.TotalPlayers ?? 0),
                Math.Max(0, realms.FirstOrDefault(realm => realm.RealmId == (int)eRealm.Albion)?.Players ?? 0),
                Math.Max(0, realms.FirstOrDefault(realm => realm.RealmId == (int)eRealm.Midgard)?.Players ?? 0),
                Math.Max(0, realms.FirstOrDefault(realm => realm.RealmId == (int)eRealm.Hibernia)?.Players ?? 0),
                Math.Max(0, live?.Performance?.CpuPercent ?? 0),
                Math.Max(0, live?.Performance?.MemoryKb ?? 0),
                Math.Max(0, live?.Performance?.NetworkReceivedKbps ?? 0),
                Math.Max(0, live?.Performance?.NetworkSentKbps ?? 0));
        }

        private static DashboardHistoryResponse WithCurrentHistoryPoint(
            DashboardHistoryResponse response,
            DashboardLiveResponse live,
            DateTime nowUtc)
        {
            List<DashboardHistoryPoint> points = (response?.Points ?? Array.Empty<DashboardHistoryPoint>()).ToList();
            points.Add(CreateCurrentHistoryPoint(live, nowUtc));
            return CreateHistoryResponse(response?.Range ?? "24h", points, nowUtc);
        }

        private static DashboardHistoryResponse CreateHistoryResponse(
            string rangeName,
            IEnumerable<DashboardHistoryPoint> points,
            DateTime updatedAt)
        {
            return new DashboardHistoryResponse(
                rangeName,
                (points ?? Enumerable.Empty<DashboardHistoryPoint>())
                    .GroupBy(point => point.Bucket)
                    .Select(group => group.Last())
                    .OrderBy(point => point.Bucket)
                    .ToList(),
                updatedAt);
        }

        public DashboardRealmActivityResponse GetRealmActivity(string range)
        {
            TimeSpan duration = ParseRange(range, TimeSpan.FromDays(7));
            string rangeName = ToRangeName(duration);
            DateTime now = DateTime.UtcNow;

            lock (m_cacheLock)
            {
                if (m_realmActivityCache.TryGetValue(rangeName, out CacheEntry<DashboardRealmActivityResponse> cached) && now < cached.ExpiresAt)
                    return cached.Value;

                DateTime start = DashboardAggregation.GetHourBucket(now.Add(-duration));
                IList<DbDashboardRealmActivity> rows = GameServer.Database.SelectObjects<DbDashboardRealmActivity>(DB.Column("BucketStart").IsGreaterOrEqualTo(start));
                DashboardRealmActivityResponse response = new(
                    rangeName,
                    DashboardAggregation.BuildRealmActivitySeries(rows, now, duration),
                    now);

                m_realmActivityCache[rangeName] = new CacheEntry<DashboardRealmActivityResponse>(response, now.Add(DataCacheDuration));
                return response;
            }
        }

        public DashboardClassHistoryResponse GetClassHistory(string range)
        {
            TimeSpan duration = ParseRange(range, TimeSpan.FromHours(24));
            string rangeName = ToRangeName(duration);
            DateTime now = DateTime.UtcNow;

            lock (m_cacheLock)
            {
                if (m_classHistoryCache.TryGetValue(rangeName, out CacheEntry<DashboardClassHistoryResponse> cached) && now < cached.ExpiresAt)
                    return cached.Value;

                DateTime start = DashboardAggregation.GetMinuteBucket(now.Add(-duration));
                IList<DbDashboardClassSnapshot> rows = GameServer.Database.SelectObjects<DbDashboardClassSnapshot>(DB.Column("BucketStart").IsGreaterOrEqualTo(start));
                DashboardClassHistoryResponse response = new(
                    rangeName,
                    DashboardAggregation.BuildClassHistoryStats(rows, now, duration),
                    now);

                m_classHistoryCache[rangeName] = new CacheEntry<DashboardClassHistoryResponse>(response, now.Add(DataCacheDuration));
                return response;
            }
        }

        public DashboardHeraldResponse GetHerald()
        {
            DateTime now = DateTime.UtcNow;

            lock (m_cacheLock)
            {
                if (m_heraldCache != null && now < m_heraldCache.ExpiresAt)
                    return m_heraldCache.Value;

                DashboardLiveResponse live = GetLive();
                DateTime activityStart = DashboardAggregation.GetHourBucket(now.AddDays(-7));
                DateTime rvrStart = now.AddDays(-2);
                IList<DbCoreCharacter> characters = GameServer.Database.SelectAllObjects<DbCoreCharacter>();
                IList<DbGuild> guilds = GameServer.Database.SelectAllObjects<DbGuild>();
                IList<DbDashboardRealmActivity> activityRows = GameServer.Database.SelectObjects<DbDashboardRealmActivity>(DB.Column("BucketStart").IsGreaterOrEqualTo(activityStart));
                IList<DbDashboardRvrKill> rvrRows = GameServer.Database.SelectObjects<DbDashboardRvrKill>(DB.Column("KilledAt").IsGreaterOrEqualTo(rvrStart));

                DashboardHeraldResponse response = DashboardAggregation.BuildHeraldStats(
                    characters,
                    guilds,
                    live.Realms,
                    GetWarState(),
                    activityRows,
                    now,
                    ResolveClassName,
                    rvrRows);

                m_heraldCache = new CacheEntry<DashboardHeraldResponse>(response, now.Add(DataCacheDuration));
                return response;
            }
        }

        public DashboardHeraldCharacterDetail GetHeraldCharacter(string name)
        {
            if (string.IsNullOrWhiteSpace(name))
                return null;

            lock (m_cacheLock)
            {
                IList<DbCoreCharacter> characters = GameServer.Database.SelectAllObjects<DbCoreCharacter>();
                IList<DbGuild> guilds = GameServer.Database.SelectAllObjects<DbGuild>();

                return DashboardAggregation.BuildHeraldCharacterDetail(name, characters, guilds, ResolveClassName);
            }
        }

        public DashboardHeraldGuildDetail GetHeraldGuild(string name)
        {
            if (string.IsNullOrWhiteSpace(name))
                return null;

            lock (m_cacheLock)
            {
                IList<DbGuild> guilds = GameServer.Database.SelectAllObjects<DbGuild>();
                IList<DbCoreCharacter> characters = GameServer.Database.SelectAllObjects<DbCoreCharacter>();

                return DashboardAggregation.BuildHeraldGuildDetail(name, guilds, characters, ResolveClassName);
            }
        }

        public DashboardOperatorStatusResponse GetOperatorStatus()
        {
            DateTime now = DateTime.UtcNow;

            lock (m_cacheLock)
            {
                if (m_operatorCache != null && now < m_operatorCache.ExpiresAt)
                    return m_operatorCache.Value;

                DashboardLiveResponse live = GetLive();
                DashboardHistoryResponse history = GetHistory("24h");
                List<DashboardServiceCheck> checks = new()
                {
                    BuildGamePortCheck(now),
                    BuildApiCheck(now),
                    BuildDatabaseCheck(now),
                    BuildHistoryCheck(history, now),
                    BuildResourceCheck(live, now)
                };

                string overallStatus = checks.Any(check => check.Status == "danger")
                    ? "danger"
                    : checks.Any(check => check.Status == "warning") ? "warning" : "ok";

                DashboardOperatorStatusResponse response = new(
                    overallStatus,
                    GetOperatorMessage(overallStatus),
                    live,
                    history.Points?.Count ?? 0,
                    history.Points?.LastOrDefault()?.Bucket,
                    checks,
                    now);

                m_operatorCache = new CacheEntry<DashboardOperatorStatusResponse>(response, now.Add(LiveCacheDuration));
                return response;
            }
        }

        public DashboardStatusSummaryResponse GetStatusSummary()
        {
            DashboardLiveResponse live = GetLive();
            DashboardHistoryResponse history = GetHistory("24h");
            int peakPlayers = Math.Max(live.TotalPlayers, history.Points?.Max(point => point.TotalPlayers) ?? 0);
            string status = live.Performance.CpuPercent >= 90 || live.Performance.MemoryKb >= 3_500_000
                ? "warning"
                : "online";

            return new DashboardStatusSummaryResponse(
                status,
                live.TotalPlayers,
                peakPlayers,
                live.Realms,
                live.Performance,
                live.Uptime,
                live.UpdatedAt,
                "/status/badge.png",
                "/dashboard#live");
        }

        private static List<GamePlayer> GetPlayersOfRealm(eRealm realm)
        {
            return ClientService.Instance.GetPlayersOfRealm(realm)
                .Where(player => player != null)
                .ToList();
        }

        private static DashboardServiceCheck BuildGamePortCheck(DateTime now)
        {
            int clients = Math.Max(0, ClientService.Instance.ClientCount);
            return new DashboardServiceCheck(
                "게임 포트",
                "ok",
                $"10300 대기 중 · 접속 {clients}",
                now);
        }

        private static DashboardServiceCheck BuildApiCheck(DateTime now)
        {
            return new DashboardServiceCheck(
                "대시보드 API",
                "ok",
                "5000 응답 중",
                now);
        }

        private static DashboardServiceCheck BuildDatabaseCheck(DateTime now)
        {
            try
            {
                GameServer.Database.SelectObjects<DbServerStat>(DB.Column("StatDate").IsGreaterThan(DateTime.Now.AddMinutes(-10)));
                return new DashboardServiceCheck("데이터베이스", "ok", "최근 통계 조회 성공", now);
            }
            catch (Exception ex)
            {
                return new DashboardServiceCheck("데이터베이스", "danger", $"통계 조회 실패: {ex.GetType().Name}", now);
            }
        }

        private static DashboardServiceCheck BuildHistoryCheck(DashboardHistoryResponse history, DateTime now)
        {
            int count = history.Points?.Count ?? 0;
            DateTime? latest = history.Points?.LastOrDefault()?.Bucket;
            string status = count > 1 ? "ok" : "warning";
            string detail = latest.HasValue
                ? $"24시간 샘플 {count}개 · 최근 {latest.Value.ToLocalTime():HH:mm}"
                : "24시간 샘플 없음";

            return new DashboardServiceCheck("히스토리 수집", status, detail, now);
        }

        private static DashboardServiceCheck BuildResourceCheck(DashboardLiveResponse live, DateTime now)
        {
            float cpu = Math.Max(0, live?.Performance?.CpuPercent ?? 0);
            long memoryMb = Math.Max(0, (live?.Performance?.MemoryKb ?? 0) / 1024);
            string status = cpu >= 90 || memoryMb >= 3500 ? "danger" : cpu >= 75 || memoryMb >= 2800 ? "warning" : "ok";

            double receivedKbps = Math.Max(0, live?.Performance?.NetworkReceivedKbps ?? 0);
            double sentKbps = Math.Max(0, live?.Performance?.NetworkSentKbps ?? 0);

            return new DashboardServiceCheck(
                "서버 리소스",
                status,
                $"CPU {cpu:0.0}% · RAM {memoryMb:n0} MB · ↓ {receivedKbps:n1} KB/s · ↑ {sentKbps:n1} KB/s",
                now);
        }

        private static string GetOperatorMessage(string status)
        {
            switch (status)
            {
                case "danger":
                    return "즉시 확인이 필요한 항목이 있습니다";
                case "warning":
                    return "주의 항목이 있어 추이를 지켜보세요";
                default:
                    return "주요 서비스가 정상입니다";
            }
        }

        private static IEnumerable<GamePlayer> GetOnlinePlayers(params IEnumerable<GamePlayer>[] realmPlayers)
        {
            return realmPlayers
                .Where(players => players != null)
                .SelectMany(players => players)
                .Where(player => player != null);
        }

        private static DashboardClassSample CreateClassSample(GamePlayer player)
        {
            ICharacterClass characterClass = player.CharacterClass;

            if (characterClass == null)
                return null;

            return new DashboardClassSample(
                (int)player.Realm,
                DOL.GS.GlobalConstants.RealmToName(player.Realm),
                characterClass.ID,
                characterClass.Name ?? $"Class {characterClass.ID}");
        }

        private static string ResolveClassName(int classId)
        {
            ICharacterClass characterClass = ScriptMgr.FindCharacterClass(classId);
            return characterClass?.Name ?? $"Class {classId}";
        }

        private static DashboardHeraldWarState GetWarState()
        {
            string darknessFallsOwner = DOL.GS.GlobalConstants.RealmToName(DFEnterJumpPoint.DarknessFallOwner);
            IEnumerable<DashboardHeraldKeepSample> keepSamples = GetKeepSamples();
            IEnumerable<DashboardHeraldRelicStatus> relicStatuses = GetRelicStatuses();

            return DashboardAggregation.BuildHeraldWarState(darknessFallsOwner, keepSamples, relicStatuses);
        }

        private static IEnumerable<DashboardHeraldKeepSample> GetKeepSamples()
        {
            ICollection<AbstractGameKeep> keeps = GameServer.KeepManager?.GetAllKeeps();

            if (keeps == null)
                return Enumerable.Empty<DashboardHeraldKeepSample>();

            return keeps
                .Where(IsHeraldKeep)
                .Select(keep => new DashboardHeraldKeepSample((int)keep.Realm, keep is GameKeepTower, keep.InCombat))
                .ToList();
        }

        private static IEnumerable<DashboardHeraldRelicStatus> GetRelicStatuses()
        {
            return RelicMgr.GetRelics()
                .Where(relic => relic != null)
                .Select(relic => new DashboardHeraldRelicStatus(
                    relic.Name,
                    relic.RelicType.ToString(),
                    (int)relic.OriginalRealm,
                    DOL.GS.GlobalConstants.RealmToName(relic.OriginalRealm),
                    (int)relic.Realm,
                    DOL.GS.GlobalConstants.RealmToName(relic.Realm),
                    relic.Realm != relic.OriginalRealm))
                .ToList();
        }

        private static bool IsHeraldKeep(AbstractGameKeep keep)
        {
            if (keep == null)
                return false;

            if (keep.Region is 250 or 251 or 252 or 253 or 165)
                return false;

            if (keep is GameKeep gameKeep && gameKeep.IsPortalKeep)
                return false;

            if (keep.Name.Contains("dagda", StringComparison.OrdinalIgnoreCase)
                || keep.Name.Contains("lamfhota", StringComparison.OrdinalIgnoreCase)
                || keep.Name.Contains("grallarhorn", StringComparison.OrdinalIgnoreCase)
                || keep.Name.Contains("mjollner", StringComparison.OrdinalIgnoreCase)
                || keep.Name.Contains("myrddin", StringComparison.OrdinalIgnoreCase)
                || keep.Name.Contains("excalibur", StringComparison.OrdinalIgnoreCase)
                || keep.Name.Contains("portal", StringComparison.OrdinalIgnoreCase))
                return false;

            return keep.Realm == eRealm.Albion
                || keep.Realm == eRealm.Midgard
                || keep.Realm == eRealm.Hibernia;
        }

        private static TimeSpan ParseRange(string range, TimeSpan defaultRange)
        {
            if (string.IsNullOrWhiteSpace(range))
                return defaultRange;

            switch (range.Trim().ToLowerInvariant())
            {
                case "7d":
                case "7day":
                case "7days":
                    return TimeSpan.FromDays(7);
                case "24h":
                case "24hr":
                case "24hrs":
                case "24hour":
                case "24hours":
                    return TimeSpan.FromHours(24);
                default:
                    return defaultRange;
            }
        }

        private static string ToRangeName(TimeSpan range)
        {
            return range >= TimeSpan.FromDays(7) ? "7d" : "24h";
        }

        private sealed class CacheEntry<T>
        {
            public CacheEntry(T value, DateTime expiresAt)
            {
                Value = value;
                ExpiresAt = expiresAt;
            }

            public T Value { get; }
            public DateTime ExpiresAt { get; }
        }
    }
}
