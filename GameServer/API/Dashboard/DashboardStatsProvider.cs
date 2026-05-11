using System;
using System.Collections.Generic;
using System.Linq;
using DOL.Database;

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

        private DashboardLiveResponse m_live;
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
                    return cached.Value;

                DateTime now = DateTime.Now;
                DateTime start = now.Add(-duration);
                IList<DbServerStat> rows = GameServer.Database.SelectObjects<DbServerStat>(DB.Column("StatDate").IsGreaterThan(start));
                DashboardHistoryResponse response = new(
                    rangeName,
                    DashboardAggregation.NormalizeHistory(rows, now, duration),
                    nowUtc);

                m_historyCache[rangeName] = new CacheEntry<DashboardHistoryResponse>(response, nowUtc.Add(DataCacheDuration));
                return response;
            }
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
                IList<DbDashboardRealmActivity> rows = GameServer.Database.SelectObjects<DbDashboardRealmActivity>(DB.Column("BucketStart").IsGreaterThan(start));
                DashboardRealmActivityResponse response = new(
                    rangeName,
                    DashboardAggregation.BuildRealmActivitySeries(rows, now, duration),
                    now);

                m_realmActivityCache[rangeName] = new CacheEntry<DashboardRealmActivityResponse>(response, now.Add(DataCacheDuration));
                return response;
            }
        }

        private static List<GamePlayer> GetPlayersOfRealm(eRealm realm)
        {
            return ClientService.Instance.GetPlayersOfRealm(realm)
                .Where(player => player != null)
                .ToList();
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
                characterClass.ID,
                characterClass.Name ?? $"Class {characterClass.ID}");
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
