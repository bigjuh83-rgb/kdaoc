using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using DOL.Database;

namespace DOL.GS.API.Dashboard
{
    public static class DashboardAggregation
    {
        public static IReadOnlyList<DashboardRealmStats> BuildRealmStats(int albion, int midgard, int hibernia)
        {
            return new List<DashboardRealmStats>
            {
                new((int)eRealm.Albion, "Albion", Math.Max(0, albion)),
                new((int)eRealm.Midgard, "Midgard", Math.Max(0, midgard)),
                new((int)eRealm.Hibernia, "Hibernia", Math.Max(0, hibernia))
            };
        }

        public static IReadOnlyList<DashboardClassStats> BuildClassStats(IEnumerable<DashboardClassSample> samples)
        {
            return (samples ?? Enumerable.Empty<DashboardClassSample>())
                .Where(sample => sample != null && sample.ClassId > 0 && !string.IsNullOrWhiteSpace(sample.ClassName))
                .GroupBy(sample => new { sample.ClassId, sample.ClassName })
                .Select(group => new DashboardClassStats(group.Key.ClassId, group.Key.ClassName, group.Count()))
                .OrderByDescending(stat => stat.Players)
                .ThenBy(stat => stat.ClassName, StringComparer.Ordinal)
                .ToList();
        }

        public static IReadOnlyList<DashboardHistoryPoint> NormalizeHistory(IEnumerable<DbServerStat> rows, DateTime now, TimeSpan range)
        {
            DateTime end = ToUtcAssumeLocal(now);
            DateTime start = end - range;

            return (rows ?? Enumerable.Empty<DbServerStat>())
                .Where(row => row != null)
                .Select(row => new { Row = row, StatDate = ToUtcAssumeLocal(row.StatDate) })
                .Where(row => row.StatDate >= start && row.StatDate <= end)
                .OrderBy(row => row.StatDate)
                .Select(row => new DashboardHistoryPoint(
                    row.StatDate,
                    row.Row.Clients,
                    row.Row.AlbionPlayers,
                    row.Row.MidgardPlayers,
                    row.Row.HiberniaPlayers,
                    row.Row.CPU,
                    row.Row.Memory))
                .ToList();
        }

        public static DateTime GetHourBucket(DateTime time)
        {
            DateTime utcTime = ToUtcAssumeUtc(time);
            return new DateTime(utcTime.Year, utcTime.Month, utcTime.Day, utcTime.Hour, 0, 0, DateTimeKind.Utc);
        }

        public static string BuildActivityKey(DateTime bucketStart, eRealm realm)
        {
            return GetHourBucket(bucketStart).ToString("yyyyMMddHH", CultureInfo.InvariantCulture) + "|" + (int)realm;
        }

        public static IReadOnlyList<DashboardRealmActivityPoint> BuildRealmActivitySeries(
            IEnumerable<DbDashboardRealmActivity> rows,
            DateTime now,
            TimeSpan range)
        {
            if (range < TimeSpan.Zero)
                range = TimeSpan.Zero;

            DateTime end = GetHourBucket(now);
            DateTime start = GetHourBucket(end - range);
            Dictionary<DateTime, ActivityTotals> buckets = new();

            for (DateTime bucket = start; bucket <= end; bucket = bucket.AddHours(1))
                buckets[bucket] = new ActivityTotals();

            foreach (DbDashboardRealmActivity row in rows ?? Enumerable.Empty<DbDashboardRealmActivity>())
            {
                if (row == null)
                    continue;

                DateTime bucket = GetHourBucket(row.BucketStart);

                if (!buckets.TryGetValue(bucket, out ActivityTotals totals))
                    continue;

                long gold = Math.Max(0, row.ServerIssuedGold);
                long realmPoints = Math.Max(0, row.ServerIssuedRealmPoints);

                switch (row.Realm)
                {
                    case (int)eRealm.Albion:
                        totals.AlbionGold += gold;
                        totals.AlbionRealmPoints += realmPoints;
                        break;
                    case (int)eRealm.Midgard:
                        totals.MidgardGold += gold;
                        totals.MidgardRealmPoints += realmPoints;
                        break;
                    case (int)eRealm.Hibernia:
                        totals.HiberniaGold += gold;
                        totals.HiberniaRealmPoints += realmPoints;
                        break;
                }
            }

            return buckets
                .OrderBy(bucket => bucket.Key)
                .Select(bucket => new DashboardRealmActivityPoint(
                    bucket.Key,
                    bucket.Value.AlbionGold,
                    bucket.Value.MidgardGold,
                    bucket.Value.HiberniaGold,
                    bucket.Value.AlbionRealmPoints,
                    bucket.Value.MidgardRealmPoints,
                    bucket.Value.HiberniaRealmPoints))
                .ToList();
        }

        private static DateTime ToUtcAssumeLocal(DateTime time)
        {
            return time.Kind switch
            {
                DateTimeKind.Utc => time,
                DateTimeKind.Local => time.ToUniversalTime(),
                _ => DateTime.SpecifyKind(time, DateTimeKind.Local).ToUniversalTime()
            };
        }

        private static DateTime ToUtcAssumeUtc(DateTime time)
        {
            return time.Kind switch
            {
                DateTimeKind.Utc => time,
                DateTimeKind.Local => time.ToUniversalTime(),
                _ => DateTime.SpecifyKind(time, DateTimeKind.Utc)
            };
        }

        private sealed class ActivityTotals
        {
            public long AlbionGold { get; set; }
            public long MidgardGold { get; set; }
            public long HiberniaGold { get; set; }
            public long AlbionRealmPoints { get; set; }
            public long MidgardRealmPoints { get; set; }
            public long HiberniaRealmPoints { get; set; }
        }
    }
}
