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
                .Where(sample =>
                    sample != null
                    && sample.RealmId > 0
                    && !string.IsNullOrWhiteSpace(sample.RealmName)
                    && sample.ClassId > 0
                    && !string.IsNullOrWhiteSpace(sample.ClassName))
                .GroupBy(sample => new { sample.RealmId, sample.RealmName, sample.ClassId, sample.ClassName })
                .Select(group => new DashboardClassStats(
                    group.Key.RealmId,
                    group.Key.RealmName,
                    group.Key.ClassId,
                    group.Key.ClassName,
                    group.Count()))
                .OrderBy(stat => stat.RealmId)
                .ThenByDescending(stat => stat.Players)
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
                    row.Row.Memory,
                    0,
                    0))
                .ToList();
        }

        public static DateTime GetHourBucket(DateTime time)
        {
            DateTime utcTime = ToUtcAssumeUtc(time);
            return new DateTime(utcTime.Year, utcTime.Month, utcTime.Day, utcTime.Hour, 0, 0, DateTimeKind.Utc);
        }

        public static DateTime GetMinuteBucket(DateTime time)
        {
            DateTime utcTime = ToUtcAssumeUtc(time);
            return new DateTime(utcTime.Year, utcTime.Month, utcTime.Day, utcTime.Hour, utcTime.Minute, 0, DateTimeKind.Utc);
        }

        public static string BuildActivityKey(DateTime bucketStart, eRealm realm)
        {
            return GetHourBucket(bucketStart).ToString("yyyyMMddHH", CultureInfo.InvariantCulture) + "|" + (int)realm;
        }

        public static string BuildClassSnapshotKey(DateTime bucketStart, int realmId, int classId)
        {
            return GetMinuteBucket(bucketStart).ToString("yyyyMMddHHmm", CultureInfo.InvariantCulture)
                + "|"
                + realmId.ToString(CultureInfo.InvariantCulture)
                + "|"
                + classId.ToString(CultureInfo.InvariantCulture);
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

        public static IReadOnlyList<DashboardClassHistoryStats> BuildClassHistoryStats(
            IEnumerable<DbDashboardClassSnapshot> rows,
            DateTime now,
            TimeSpan range)
        {
            if (range < TimeSpan.Zero)
                range = TimeSpan.Zero;

            DateTime end = GetMinuteBucket(now);
            DateTime start = GetMinuteBucket(end - range);

            List<DbDashboardClassSnapshot> filteredRows = (rows ?? Enumerable.Empty<DbDashboardClassSnapshot>())
                .Where(row => row != null)
                .Select(row => new
                {
                    Row = row,
                    Bucket = GetMinuteBucket(row.BucketStart)
                })
                .Where(row => row.Bucket >= start && row.Bucket <= end)
                .Select(row => row.Row)
                .ToList();

            Dictionary<int, int> realmSampleCounts = filteredRows
                .Where(row => row.ClassId == 0 && IsTrackedRealm(row.Realm))
                .GroupBy(row => row.Realm)
                .ToDictionary(
                    group => group.Key,
                    group => group.Select(row => GetMinuteBucket(row.BucketStart)).Distinct().Count());

            return filteredRows
                .Where(row => row.ClassId > 0 && row.Players > 0 && IsTrackedRealm(row.Realm) && !string.IsNullOrWhiteSpace(row.ClassName))
                .GroupBy(row => new { row.Realm, row.RealmName, row.ClassId, row.ClassName })
                .Select(group =>
                {
                    int sampleCount = realmSampleCounts.TryGetValue(group.Key.Realm, out int count) && count > 0
                        ? count
                        : Math.Max(1, group.Select(row => GetMinuteBucket(row.BucketStart)).Distinct().Count());

                    return new DashboardClassHistoryStats(
                        group.Key.Realm,
                        string.IsNullOrWhiteSpace(group.Key.RealmName) ? RealmName(group.Key.Realm) : group.Key.RealmName,
                        group.Key.ClassId,
                        group.Key.ClassName,
                        Math.Round(group.Sum(row => Math.Max(0, row.Players)) / (double)sampleCount, 2),
                        group.Max(row => Math.Max(0, row.Players)));
                })
                .Where(stat => stat.AveragePlayers > 0)
                .OrderBy(stat => stat.RealmId)
                .ThenByDescending(stat => stat.AveragePlayers)
                .ThenBy(stat => stat.ClassName, StringComparer.Ordinal)
                .ToList();
        }

        public static DashboardHeraldResponse BuildHeraldStats(
            IEnumerable<DbCoreCharacter> characters,
            IEnumerable<DbGuild> guilds,
            IReadOnlyList<DashboardRealmStats> liveRealms,
            DashboardHeraldWarState war,
            IEnumerable<DbDashboardRealmActivity> activityRows,
            DateTime now,
            Func<int, string> classNameResolver,
            IEnumerable<DbDashboardRvrKill> rvrKillRows = null)
        {
            DateTime updatedAt = ToUtcAssumeUtc(now);
            IReadOnlyList<DashboardRealmStats> realms = liveRealms ?? BuildRealmStats(0, 0, 0);

            List<DbCoreCharacter> publicCharacters = (characters ?? Enumerable.Empty<DbCoreCharacter>())
                .Where(IsPublicHeraldCharacter)
                .ToList();

            List<DbGuild> publicGuilds = (guilds ?? Enumerable.Empty<DbGuild>())
                .Where(IsPublicHeraldGuild)
                .ToList();

            Dictionary<string, DbGuild> guildsById = publicGuilds
                .Where(guild => !string.IsNullOrWhiteSpace(guild.GuildID))
                .GroupBy(guild => guild.GuildID, StringComparer.OrdinalIgnoreCase)
                .ToDictionary(group => group.Key, group => group.First(), StringComparer.OrdinalIgnoreCase);

            IReadOnlyList<DashboardHeraldRealmSummary> realmSummaries = BuildHeraldRealmSummaries(realms, publicCharacters, publicGuilds);
            List<DbCoreCharacter> rankedCharacterCandidates = publicCharacters
                .OrderByDescending(character => Math.Max(0, character.RealmPoints))
                .ThenByDescending(character => Math.Max(0, character.RealmLevel))
                .ThenByDescending(character => ToUtcAssumeLocal(character.LastPlayed))
                .ThenBy(character => character.Name, StringComparer.Ordinal)
                .Take(20)
                .Concat(publicCharacters
                    .OrderByDescending(character => Math.Max(0, character.BountyPoints))
                    .ThenByDescending(character => Math.Max(0, character.RealmPoints))
                    .ThenBy(character => character.Name, StringComparer.Ordinal)
                    .Take(20))
                .Concat(publicCharacters
                    .OrderByDescending(GetTotalPlayerKills)
                    .ThenByDescending(character => Math.Max(0, character.RealmPoints))
                    .ThenBy(character => character.Name, StringComparer.Ordinal)
                    .Take(20))
                .Concat(publicCharacters
                    .OrderByDescending(GetTotalDeathBlows)
                    .ThenByDescending(character => Math.Max(0, character.RealmPoints))
                    .ThenBy(character => character.Name, StringComparer.Ordinal)
                    .Take(20))
                .Concat(publicCharacters
                    .OrderByDescending(GetTotalSoloKills)
                    .ThenByDescending(character => Math.Max(0, character.RealmPoints))
                    .ThenBy(character => character.Name, StringComparer.Ordinal)
                    .Take(20))
                .Concat(publicCharacters
                    .OrderByDescending(character => Math.Max(0, character.DeathsPvP))
                    .ThenByDescending(character => Math.Max(0, character.RealmPoints))
                    .ThenBy(character => character.Name, StringComparer.Ordinal)
                    .Take(20))
                .GroupBy(GetCharacterRankKey, StringComparer.OrdinalIgnoreCase)
                .Select(group => group.First())
                .ToList();

            IReadOnlyList<DashboardHeraldCharacterRank> topCharacters = rankedCharacterCandidates
                .OrderByDescending(character => Math.Max(0, character.RealmPoints))
                .ThenByDescending(character => Math.Max(0, character.RealmLevel))
                .ThenByDescending(character => ToUtcAssumeLocal(character.LastPlayed))
                .ThenBy(character => character.Name, StringComparer.Ordinal)
                .Select((character, index) => new DashboardHeraldCharacterRank(
                    index + 1,
                    character.Name.Trim(),
                    character.Realm,
                    RealmName(character.Realm),
                    Math.Max(0, character.Level),
                    Math.Max(0, character.Class),
                    ResolveClassName(character.Class, classNameResolver),
                    Math.Max(0, character.RealmPoints),
                    Math.Max(0, character.BountyPoints),
                    Math.Max(0, character.RealmLevel),
                    ResolveGuildName(character.GuildID, guildsById),
                    ToUtcAssumeLocal(character.LastPlayed),
                    GetTotalPlayerKills(character),
                    GetTotalDeathBlows(character),
                    GetTotalSoloKills(character),
                    Math.Max(0, character.DeathsPvP)))
                .ToList();

            IReadOnlyList<DashboardHeraldGuildRank> topGuilds = publicGuilds
                .OrderByDescending(guild => Math.Max(0, guild.RealmPoints))
                .ThenByDescending(guild => Math.Max(0, guild.BountyPoints))
                .ThenBy(guild => guild.GuildName, StringComparer.Ordinal)
                .Take(20)
                .Select((guild, index) => new DashboardHeraldGuildRank(
                    index + 1,
                    guild.GuildName.Trim(),
                    guild.Realm,
                    RealmName(guild.Realm),
                    Math.Max(0, guild.RealmPoints),
                    Math.Max(0, guild.BountyPoints),
                    Math.Max(0, guild.GuildLevel)))
                .ToList();

            return new DashboardHeraldResponse(
                realms,
                realmSummaries,
                war ?? BuildHeraldWarState("None", null, null),
                topCharacters,
                topGuilds,
                BuildHeraldRvrActivity(rvrKillRows, updatedAt, TimeSpan.FromDays(2)),
                BuildHeraldActivityItems(activityRows, updatedAt, TimeSpan.FromDays(7)),
                updatedAt);
        }

        public static IReadOnlyList<DashboardHeraldRvrActivityItem> BuildHeraldRvrActivity(
            IEnumerable<DbDashboardRvrKill> rows,
            DateTime now,
            TimeSpan range)
        {
            DateTime end = ToUtcAssumeUtc(now);
            DateTime start = end - range;

            return (rows ?? Enumerable.Empty<DbDashboardRvrKill>())
                .Where(row => row != null)
                .Select(row => new
                {
                    Row = row,
                    KilledAt = ToUtcAssumeUtc(row.KilledAt)
                })
                .Where(item => item.KilledAt >= start && item.KilledAt <= end)
                .Where(item => IsTrackedRealm(item.Row.KillerRealm)
                    && IsTrackedRealm(item.Row.VictimRealm)
                    && item.Row.KillerRealm != item.Row.VictimRealm
                    && !string.IsNullOrWhiteSpace(item.Row.KillerName)
                    && !string.IsNullOrWhiteSpace(item.Row.VictimName))
                .OrderByDescending(item => item.KilledAt)
                .ThenBy(item => item.Row.KillerName, StringComparer.Ordinal)
                .Take(20)
                .Select(item => new DashboardHeraldRvrActivityItem(
                    item.KilledAt,
                    item.Row.KillerName.Trim(),
                    item.Row.KillerRealm,
                    RealmName(item.Row.KillerRealm),
                    Math.Max(0, item.Row.KillerClassId),
                    TrimOrUnknown(item.Row.KillerClassName),
                    TrimOrEmpty(item.Row.KillerGuildName),
                    item.Row.VictimName.Trim(),
                    item.Row.VictimRealm,
                    RealmName(item.Row.VictimRealm),
                    Math.Max(0, item.Row.VictimClassId),
                    TrimOrUnknown(item.Row.VictimClassName),
                    TrimOrEmpty(item.Row.VictimGuildName),
                    TrimOrEmpty(item.Row.RegionName),
                    Math.Max(0, item.Row.RealmPoints),
                    item.Row.SoloKill))
                .ToList();
        }

        public static DashboardHeraldWarState BuildHeraldWarState(
            string darknessFallsOwnerRealmName,
            IEnumerable<DashboardHeraldKeepSample> keeps,
            IEnumerable<DashboardHeraldRelicStatus> relics)
        {
            int darknessFallsOwnerRealmId = RealmIdFromName(darknessFallsOwnerRealmName);
            string darknessFallsOwnerName = darknessFallsOwnerRealmId == 0 ? "None" : RealmName(darknessFallsOwnerRealmId);
            List<DashboardHeraldKeepSample> trackedKeeps = (keeps ?? Enumerable.Empty<DashboardHeraldKeepSample>())
                .Where(keep => keep != null && IsTrackedRealm(keep.RealmId))
                .ToList();
            List<DashboardHeraldRelicStatus> trackedRelics = (relics ?? Enumerable.Empty<DashboardHeraldRelicStatus>())
                .Where(relic => relic != null)
                .ToList();

            IReadOnlyList<DashboardHeraldWarRealmSummary> summaries = BuildRealmStats(0, 0, 0)
                .Select(realm =>
                {
                    int realmId = realm.RealmId;
                    return new DashboardHeraldWarRealmSummary(
                        realmId,
                        realm.RealmName,
                        trackedKeeps.Count(keep => keep.RealmId == realmId && !keep.IsTower),
                        trackedKeeps.Count(keep => keep.RealmId == realmId && keep.IsTower),
                        trackedRelics.Count(relic => relic.CurrentRealmId == realmId),
                        trackedKeeps.Count(keep => keep.RealmId == realmId && keep.IsUnderSiege));
                })
                .ToList();

            return new DashboardHeraldWarState(
                darknessFallsOwnerRealmId,
                darknessFallsOwnerName,
                summaries,
                trackedRelics
                    .OrderBy(relic => relic.OriginalRealmId)
                    .ThenBy(relic => relic.Type, StringComparer.Ordinal)
                    .ThenBy(relic => relic.Name, StringComparer.Ordinal)
                    .ToList());
        }

        public static DashboardHeraldCharacterDetail BuildHeraldCharacterDetail(
            string characterName,
            IEnumerable<DbCoreCharacter> characters,
            IEnumerable<DbGuild> guilds,
            Func<int, string> classNameResolver)
        {
            if (string.IsNullOrWhiteSpace(characterName))
                return null;

            List<DbGuild> publicGuilds = (guilds ?? Enumerable.Empty<DbGuild>())
                .Where(IsPublicHeraldGuild)
                .ToList();
            Dictionary<string, DbGuild> guildsById = publicGuilds
                .Where(guild => !string.IsNullOrWhiteSpace(guild.GuildID))
                .GroupBy(guild => guild.GuildID, StringComparer.OrdinalIgnoreCase)
                .ToDictionary(group => group.Key, group => group.First(), StringComparer.OrdinalIgnoreCase);

            DbCoreCharacter character = (characters ?? Enumerable.Empty<DbCoreCharacter>())
                .Where(IsPublicHeraldCharacter)
                .FirstOrDefault(row => string.Equals(row.Name?.Trim(), characterName.Trim(), StringComparison.OrdinalIgnoreCase));

            if (character == null)
                return null;

            return new DashboardHeraldCharacterDetail(
                character.Name.Trim(),
                character.Realm,
                RealmName(character.Realm),
                Math.Max(0, character.Level),
                Math.Max(0, character.Class),
                ResolveClassName(character.Class, classNameResolver),
                Math.Max(0, character.RealmPoints),
                Math.Max(0, character.BountyPoints),
                Math.Max(0, character.RealmLevel),
                FormatRealmRank(character.RealmLevel),
                ResolveGuildName(character.GuildID, guildsById),
                ToUtcAssumeLocal(character.LastPlayed),
                GetTotalPlayerKills(character),
                GetTotalDeathBlows(character),
                GetTotalSoloKills(character),
                Math.Max(0, character.DeathsPvP));
        }

        public static DashboardHeraldGuildDetail BuildHeraldGuildDetail(
            string guildName,
            IEnumerable<DbGuild> guilds,
            IEnumerable<DbCoreCharacter> characters,
            Func<int, string> classNameResolver)
        {
            if (string.IsNullOrWhiteSpace(guildName))
                return null;

            DbGuild guild = (guilds ?? Enumerable.Empty<DbGuild>())
                .Where(IsPublicHeraldGuild)
                .FirstOrDefault(row => string.Equals(row.GuildName?.Trim(), guildName.Trim(), StringComparison.OrdinalIgnoreCase));

            if (guild == null)
                return null;

            List<DbCoreCharacter> members = (characters ?? Enumerable.Empty<DbCoreCharacter>())
                .Where(IsPublicHeraldCharacter)
                .Where(character => string.Equals(character.GuildID, guild.GuildID, StringComparison.OrdinalIgnoreCase))
                .ToList();

            IReadOnlyList<DashboardHeraldGuildMemberSummary> topMembers = members
                .OrderByDescending(character => Math.Max(0, character.RealmPoints))
                .ThenByDescending(character => Math.Max(0, character.RealmLevel))
                .ThenBy(character => character.Name, StringComparer.Ordinal)
                .Take(10)
                .Select(character => new DashboardHeraldGuildMemberSummary(
                    character.Name.Trim(),
                    character.Realm,
                    RealmName(character.Realm),
                    Math.Max(0, character.Level),
                    Math.Max(0, character.Class),
                    ResolveClassName(character.Class, classNameResolver),
                    Math.Max(0, character.RealmPoints),
                    Math.Max(0, character.RealmLevel),
                    FormatRealmRank(character.RealmLevel),
                    ToUtcAssumeLocal(character.LastPlayed)))
                .ToList();

            return new DashboardHeraldGuildDetail(
                guild.GuildName.Trim(),
                guild.Realm,
                RealmName(guild.Realm),
                Math.Max(0, guild.RealmPoints),
                Math.Max(0, guild.BountyPoints),
                Math.Max(0, guild.GuildLevel),
                members.Count,
                members.Count(character => character.Level >= 50),
                topMembers);
        }

        private static IReadOnlyList<DashboardHeraldRealmSummary> BuildHeraldRealmSummaries(
            IReadOnlyList<DashboardRealmStats> realms,
            IReadOnlyList<DbCoreCharacter> characters,
            IReadOnlyList<DbGuild> guilds)
        {
            Dictionary<int, int> onlinePlayersByRealm = (realms ?? Array.Empty<DashboardRealmStats>())
                .Where(realm => realm != null && IsTrackedRealm(realm.RealmId))
                .GroupBy(realm => realm.RealmId)
                .ToDictionary(group => group.Key, group => group.Sum(realm => Math.Max(0, realm.Players)));

            return BuildRealmStats(0, 0, 0)
                .Select(realm =>
                {
                    int realmId = realm.RealmId;
                    List<DbCoreCharacter> realmCharacters = characters
                        .Where(character => character.Realm == realmId)
                        .ToList();

                    return new DashboardHeraldRealmSummary(
                        realmId,
                        realm.RealmName,
                        onlinePlayersByRealm.TryGetValue(realmId, out int onlinePlayers) ? onlinePlayers : 0,
                        realmCharacters.Count,
                        realmCharacters.Count(character => character.Level >= 50),
                        guilds.Count(guild => guild.Realm == realmId),
                        realmCharacters.Sum(character => Math.Max(0, character.RealmPoints)));
                })
                .ToList();
        }

        private static IReadOnlyList<DashboardHeraldActivityItem> BuildHeraldActivityItems(
            IEnumerable<DbDashboardRealmActivity> rows,
            DateTime now,
            TimeSpan range)
        {
            DateTime end = GetHourBucket(now);
            DateTime start = GetHourBucket(end - range);
            var groupedRows = (rows ?? Enumerable.Empty<DbDashboardRealmActivity>())
                .Where(row => row != null && IsTrackedRealm(row.Realm))
                .Select(row => new
                {
                    Row = row,
                    Bucket = GetHourBucket(row.BucketStart)
                })
                .Where(row => row.Bucket >= start && row.Bucket <= end)
                .GroupBy(row => row.Row.Realm);

            List<DashboardHeraldActivityItem> items = new();

            foreach (var group in groupedRows)
            {
                int realmId = group.Key;
                DateTime bucket = group.Max(row => row.Bucket);
                long realmPoints = group.Sum(row => Math.Max(0, row.Row.ServerIssuedRealmPoints));
                long gold = group.Sum(row => Math.Max(0, row.Row.ServerIssuedGold));

                if (realmPoints > 0)
                {
                    items.Add(new DashboardHeraldActivityItem(
                        bucket,
                        "이번 주 RP 증가량",
                        realmId,
                        RealmName(realmId),
                        realmPoints,
                        "realm-points"));
                }

                if (gold > 0)
                {
                    items.Add(new DashboardHeraldActivityItem(
                        bucket,
                        "이번 주 골드 증가량",
                        realmId,
                        RealmName(realmId),
                        gold,
                        "gold"));
                }
            }

            return items
                .OrderByDescending(item => item.Value)
                .ThenBy(item => item.RealmId)
                .Take(6)
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

        private static bool IsTrackedRealm(int realmId)
        {
            return realmId == (int)eRealm.Albion
                || realmId == (int)eRealm.Midgard
                || realmId == (int)eRealm.Hibernia;
        }

        private static int RealmIdFromName(string realmName)
        {
            if (string.IsNullOrWhiteSpace(realmName))
                return 0;

            return realmName.Trim().ToLowerInvariant() switch
            {
                "albion" => (int)eRealm.Albion,
                "midgard" => (int)eRealm.Midgard,
                "hibernia" => (int)eRealm.Hibernia,
                _ => 0
            };
        }

        private static bool IsPublicHeraldCharacter(DbCoreCharacter character)
        {
            return character != null
                && !character.IgnoreStatistics
                && IsTrackedRealm(character.Realm)
                && !string.IsNullOrWhiteSpace(character.Name);
        }

        private static bool IsPublicHeraldGuild(DbGuild guild)
        {
            return guild != null
                && IsTrackedRealm(guild.Realm)
                && !string.IsNullOrWhiteSpace(guild.GuildName);
        }

        private static string ResolveClassName(int classId, Func<int, string> classNameResolver)
        {
            if (classId <= 0)
                return "Unknown";

            try
            {
                string className = classNameResolver?.Invoke(classId);

                if (!string.IsNullOrWhiteSpace(className))
                    return className.Trim();
            }
            catch
            {
                // Class tables can be partially unavailable during tests or early API startup.
            }

            return $"Class {classId}";
        }

        private static string ResolveGuildName(string guildId, IReadOnlyDictionary<string, DbGuild> guildsById)
        {
            if (string.IsNullOrWhiteSpace(guildId) || guildsById == null)
                return string.Empty;

            return guildsById.TryGetValue(guildId, out DbGuild guild) && !string.IsNullOrWhiteSpace(guild.GuildName)
                ? guild.GuildName.Trim()
                : string.Empty;
        }

        private static string GetCharacterRankKey(DbCoreCharacter character)
        {
            if (!string.IsNullOrWhiteSpace(character?.ObjectId))
                return character.ObjectId.Trim();

            return character?.Name?.Trim() ?? string.Empty;
        }

        private static int GetTotalPlayerKills(DbCoreCharacter character)
        {
            if (character == null)
                return 0;

            return Math.Max(0, character.KillsAlbionPlayers)
                + Math.Max(0, character.KillsMidgardPlayers)
                + Math.Max(0, character.KillsHiberniaPlayers);
        }

        private static int GetTotalDeathBlows(DbCoreCharacter character)
        {
            if (character == null)
                return 0;

            return Math.Max(0, character.KillsAlbionDeathBlows)
                + Math.Max(0, character.KillsMidgardDeathBlows)
                + Math.Max(0, character.KillsHiberniaDeathBlows);
        }

        private static int GetTotalSoloKills(DbCoreCharacter character)
        {
            if (character == null)
                return 0;

            return Math.Max(0, character.KillsAlbionSolo)
                + Math.Max(0, character.KillsMidgardSolo)
                + Math.Max(0, character.KillsHiberniaSolo);
        }

        private static string FormatRealmRank(int realmLevel)
        {
            int value = Math.Max(0, realmLevel) + 10;
            string text = value.ToString().PadLeft(2, '0');

            if (value >= 100)
                return $"{text[..2]}L{text.Substring(2, 1)}";

            return $"{text[..1]}L{text.Substring(1, 1)}";
        }

        private static string RealmName(int realmId)
        {
            return ((eRealm)realmId) switch
            {
                eRealm.Albion => "Albion",
                eRealm.Midgard => "Midgard",
                eRealm.Hibernia => "Hibernia",
                _ => "Unknown"
            };
        }

        private static string TrimOrEmpty(string value)
        {
            return string.IsNullOrWhiteSpace(value) ? string.Empty : value.Trim();
        }

        private static string TrimOrUnknown(string value)
        {
            return string.IsNullOrWhiteSpace(value) ? "Unknown" : value.Trim();
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
