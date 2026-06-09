using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using DOL.Database;
using DOL.GS.API.Dashboard;
using DOL.GS.PerformanceStatistics;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_DashboardAggregation
    {
        [Test]
        public void BuildClassStats_GroupsValidClassesAndSkipsInvalidSamples()
        {
            DashboardClassSample[] samples =
            {
                null,
                new((int)eRealm.Albion, "Albion", 1, "Armsman"),
                new((int)eRealm.Albion, "Albion", 1, "Armsman"),
                new((int)eRealm.Albion, "Albion", 2, "Cabalist"),
                new((int)eRealm.Midgard, "Midgard", 1, "Armsman"),
                new(0, "", 1, "Invalid Realm"),
                new((int)eRealm.Hibernia, "Hibernia", 0, ""),
                new((int)eRealm.Hibernia, "Hibernia", -1, "Broken")
            };

            var stats = DashboardAggregation.BuildClassStats(samples);

            Assert.That(stats, Has.Count.EqualTo(3));
            Assert.Multiple(() =>
            {
                Assert.That(stats[0].RealmId, Is.EqualTo((int)eRealm.Albion));
                Assert.That(stats[0].RealmName, Is.EqualTo("Albion"));
                Assert.That(stats[0].ClassId, Is.EqualTo(1));
                Assert.That(stats[0].ClassName, Is.EqualTo("Armsman"));
                Assert.That(stats[0].Players, Is.EqualTo(2));

                Assert.That(stats[1].RealmId, Is.EqualTo((int)eRealm.Albion));
                Assert.That(stats[1].ClassId, Is.EqualTo(2));
                Assert.That(stats[1].ClassName, Is.EqualTo("Cabalist"));
                Assert.That(stats[1].Players, Is.EqualTo(1));

                Assert.That(stats[2].RealmId, Is.EqualTo((int)eRealm.Midgard));
                Assert.That(stats[2].RealmName, Is.EqualTo("Midgard"));
                Assert.That(stats[2].ClassId, Is.EqualTo(1));
                Assert.That(stats[2].ClassName, Is.EqualTo("Armsman"));
                Assert.That(stats[2].Players, Is.EqualTo(1));
            });
        }

        [Test]
        public void BuildRealmStats_ClampsNegativeCounts()
        {
            var stats = DashboardAggregation.BuildRealmStats(-1, 2, -3);

            Assert.That(stats.Select(stat => stat.Players), Is.EqualTo(new[] { 0, 2, 0 }));
        }

        [Test]
        public void LiveResponse_PublicContractDoesNotContainPrivateFieldNames()
        {
            string[] propertyNames = typeof(DashboardLiveResponse)
                .GetProperties()
                .Select(property => property.Name)
                .ToArray();

            Assert.That(propertyNames, Does.Not.Contain("AccountName"));
            Assert.That(propertyNames, Does.Not.Contain("CharacterName"));
            Assert.That(propertyNames, Does.Not.Contain("IPAddress"));
            Assert.That(propertyNames, Does.Not.Contain("Zone"));
            Assert.That(propertyNames, Does.Not.Contain("GuildName"));
        }

        [Test]
        public void PerformanceSampler_FallsBackWhenCpuStatisticCannotBeCreated()
        {
            object sampler = CreatePerformanceSampler(() => throw new PlatformNotSupportedException());
            DashboardPerformanceStats snapshot = InvokePerformanceSnapshot(sampler);

            Assert.That(snapshot.CpuPercent, Is.EqualTo(0));
        }

        [Test]
        public void PerformanceSampler_FallsBackWhenCpuStatisticReadFails()
        {
            object sampler = CreatePerformanceSampler(() => new ThrowingPerformanceStatistic());
            DashboardPerformanceStats snapshot = InvokePerformanceSnapshot(sampler);

            Assert.That(snapshot.CpuPercent, Is.EqualTo(0));
        }

        [Test]
        public void NormalizeHistory_ReturnsChronologicalRowsInsideRange()
        {
            DateTime now = new(2026, 5, 11, 12, 0, 0, DateTimeKind.Utc);
            DbServerStat[] rows =
            {
                CreateServerStat(now.AddHours(-1), clients: 10),
                CreateServerStat(now.AddHours(-25), clients: 25),
                null,
                CreateServerStat(now.AddHours(-2), clients: 20)
            };

            var points = DashboardAggregation.NormalizeHistory(rows, now, TimeSpan.FromHours(24));

            Assert.That(points.Select(point => point.Bucket), Is.EqualTo(new[] { now.AddHours(-2), now.AddHours(-1) }));
            Assert.That(points.Select(point => point.TotalPlayers), Is.EqualTo(new[] { 20, 10 }));
            Assert.That(points.Select(point => point.CpuPercent), Is.EqualTo(new[] { 20.5f, 10.5f }));
            Assert.That(points.Select(point => point.MemoryKb), Is.EqualTo(new[] { 1020, 1010 }));
        }

        [Test]
        public void NormalizeHistory_TreatsUnspecifiedDbDatesAsLocalTime()
        {
            DateTime localNow = new(2026, 5, 11, 12, 0, 0, DateTimeKind.Local);
            DateTime unspecifiedStatDate = DateTime.SpecifyKind(localNow.AddHours(-1), DateTimeKind.Unspecified);
            DateTime expectedBucket = DateTime.SpecifyKind(unspecifiedStatDate, DateTimeKind.Local).ToUniversalTime();

            var points = DashboardAggregation.NormalizeHistory(
                new[] { CreateServerStat(unspecifiedStatDate, clients: 10) },
                localNow,
                TimeSpan.FromHours(24));

            Assert.That(points, Has.Count.EqualTo(1));
            Assert.That(points[0].Bucket, Is.EqualTo(expectedBucket));
        }

        [Test]
        public void BuildRealmActivitySeries_FillsMissingHourlyBucketsWithZeroes()
        {
            DateTime now = new(2026, 5, 11, 12, 35, 0, DateTimeKind.Utc);
            DateTime albionBucket = new(2026, 5, 11, 11, 0, 0, DateTimeKind.Utc);
            DbDashboardRealmActivity[] rows =
            {
                null,
                new()
                {
                    BucketRealmKey = DashboardAggregation.BuildActivityKey(albionBucket, eRealm.Albion),
                    BucketStart = albionBucket,
                    Realm = (int)eRealm.Albion,
                    ServerIssuedGold = 500,
                    ServerIssuedRealmPoints = 42
                },
                new()
                {
                    BucketRealmKey = DashboardAggregation.BuildActivityKey(albionBucket, eRealm.Midgard),
                    BucketStart = albionBucket,
                    Realm = (int)eRealm.Midgard,
                    ServerIssuedGold = -100,
                    ServerIssuedRealmPoints = -50
                },
                new()
                {
                    BucketRealmKey = DashboardAggregation.BuildActivityKey(albionBucket, eRealm.None),
                    BucketStart = albionBucket,
                    Realm = (int)eRealm.None,
                    ServerIssuedGold = 1000,
                    ServerIssuedRealmPoints = 1000
                },
                new()
                {
                    BucketRealmKey = "invalid",
                    BucketStart = albionBucket,
                    Realm = 257,
                    ServerIssuedGold = 2000,
                    ServerIssuedRealmPoints = 2000
                }
            };

            var points = DashboardAggregation.BuildRealmActivitySeries(rows, now, TimeSpan.FromHours(3));

            Assert.That(points, Has.Count.EqualTo(4));
            Assert.That(points[^1].Bucket, Is.EqualTo(DashboardAggregation.GetHourBucket(now)));

            var activityBucket = points.Single(point => point.Bucket == albionBucket);
            Assert.Multiple(() =>
            {
                Assert.That(activityBucket.AlbionGold, Is.EqualTo(500));
                Assert.That(activityBucket.AlbionRealmPoints, Is.EqualTo(42));
                Assert.That(activityBucket.MidgardGold, Is.EqualTo(0));
                Assert.That(activityBucket.MidgardRealmPoints, Is.EqualTo(0));
                Assert.That(activityBucket.HiberniaGold, Is.EqualTo(0));
                Assert.That(activityBucket.HiberniaRealmPoints, Is.EqualTo(0));
            });
        }

        [Test]
        public void BuildRealmActivitySeries_TreatsUnspecifiedActivityBucketsAsUtc()
        {
            DateTime now = new(2026, 5, 11, 12, 35, 0, DateTimeKind.Utc);
            DateTime dbBucket = new(2026, 5, 11, 11, 0, 0, DateTimeKind.Unspecified);
            DbDashboardRealmActivity[] rows =
            {
                new()
                {
                    BucketRealmKey = DashboardAggregation.BuildActivityKey(dbBucket, eRealm.Albion),
                    BucketStart = dbBucket,
                    Realm = (int)eRealm.Albion,
                    ServerIssuedGold = 123,
                    ServerIssuedRealmPoints = 456
                }
            };

            var points = DashboardAggregation.BuildRealmActivitySeries(rows, now, TimeSpan.FromHours(3));
            var activityBucket = points.Single(point => point.Bucket == new DateTime(2026, 5, 11, 11, 0, 0, DateTimeKind.Utc));

            Assert.That(activityBucket.AlbionGold, Is.EqualTo(123));
            Assert.That(activityBucket.AlbionRealmPoints, Is.EqualTo(456));
        }

        [Test]
        public void BuildClassHistoryStats_AveragesClassCountsAgainstRealmSnapshotMarkers()
        {
            DateTime now = new(2026, 5, 11, 12, 3, 0, DateTimeKind.Utc);
            DateTime first = new(2026, 5, 11, 12, 0, 0, DateTimeKind.Utc);
            DateTime second = first.AddMinutes(1);
            DateTime third = first.AddMinutes(2);
            DbDashboardClassSnapshot[] rows =
            {
                CreateClassSnapshot(first, eRealm.Albion, 0, "__snapshot__", 0),
                CreateClassSnapshot(second, eRealm.Albion, 0, "__snapshot__", 0),
                CreateClassSnapshot(third, eRealm.Albion, 0, "__snapshot__", 0),
                CreateClassSnapshot(first, eRealm.Albion, 1, "Armsman", 2),
                CreateClassSnapshot(third, eRealm.Albion, 1, "Armsman", 1),
                CreateClassSnapshot(first, eRealm.Albion, 2, "Cabalist", 1),
                CreateClassSnapshot(now.AddDays(-2), eRealm.Albion, 3, "Old", 9),
                CreateClassSnapshot(first, eRealm.Midgard, 0, "__snapshot__", 0),
                CreateClassSnapshot(first, eRealm.Midgard, 4, "Healer", 2)
            };

            var stats = DashboardAggregation.BuildClassHistoryStats(rows, now, TimeSpan.FromHours(24));

            DashboardClassHistoryStats armsman = stats.Single(stat => stat.RealmId == (int)eRealm.Albion && stat.ClassName == "Armsman");
            DashboardClassHistoryStats cabalist = stats.Single(stat => stat.RealmId == (int)eRealm.Albion && stat.ClassName == "Cabalist");
            DashboardClassHistoryStats healer = stats.Single(stat => stat.RealmId == (int)eRealm.Midgard && stat.ClassName == "Healer");

            Assert.Multiple(() =>
            {
                Assert.That(armsman.AveragePlayers, Is.EqualTo(1.0));
                Assert.That(armsman.PeakPlayers, Is.EqualTo(2));
                Assert.That(cabalist.AveragePlayers, Is.EqualTo(0.33));
                Assert.That(cabalist.PeakPlayers, Is.EqualTo(1));
                Assert.That(healer.AveragePlayers, Is.EqualTo(2.0));
                Assert.That(healer.PeakPlayers, Is.EqualTo(2));
                Assert.That(stats.Any(stat => stat.ClassName == "Old"), Is.False);
            });
        }

        [Test]
        public void BuildHeraldStats_RanksPublicCharactersAndGuildsWithoutPrivateFields()
        {
            DateTime now = new(2026, 5, 11, 12, 0, 0, DateTimeKind.Utc);
            DbGuild[] guilds =
            {
                CreateGuild("alb-guild", "Knights", eRealm.Albion, realmPoints: 7000),
                CreateGuild("mid-guild", "Hammers", eRealm.Midgard, realmPoints: 3000),
                CreateGuild("starter", "Starter", eRealm.Albion, realmPoints: 99999, isStartingGuild: true)
            };
            DbCoreCharacter[] characters =
            {
                CreateCharacter("Alice", eRealm.Albion, level: 50, classId: 1, realmPoints: 5000, realmLevel: 31, guildId: "alb-guild"),
                CreateCharacter("Bjorn", eRealm.Midgard, level: 49, classId: 2, realmPoints: 6000, realmLevel: 32, guildId: "mid-guild"),
                CreateCharacter("Ignored", eRealm.Albion, level: 50, classId: 1, realmPoints: 9000, realmLevel: 40, guildId: "alb-guild", ignoreStatistics: true),
                CreateCharacter("", eRealm.Albion, level: 50, classId: 1, realmPoints: 8000, realmLevel: 40, guildId: "alb-guild"),
                CreateCharacter("NoRealm", eRealm.None, level: 50, classId: 1, realmPoints: 7000, realmLevel: 40, guildId: "alb-guild")
            };

            DashboardHeraldResponse herald = DashboardAggregation.BuildHeraldStats(
                characters,
                guilds,
                DashboardAggregation.BuildRealmStats(albion: 2, midgard: 1, hibernia: 0),
                null,
                Array.Empty<DbDashboardRealmActivity>(),
                now,
                classId => classId == 1 ? "Armsman" : "Healer");

            Assert.Multiple(() =>
            {
                Assert.That(herald.RealmSummaries.Single(summary => summary.RealmId == (int)eRealm.Albion).OnlinePlayers, Is.EqualTo(2));
                Assert.That(herald.RealmSummaries.Single(summary => summary.RealmId == (int)eRealm.Albion).Level50Characters, Is.EqualTo(1));
                Assert.That(herald.TopCharacters.Select(rank => rank.Name), Is.EqualTo(new[] { "Bjorn", "Alice" }));
                Assert.That(herald.TopCharacters[0].ClassName, Is.EqualTo("Healer"));
                Assert.That(herald.TopCharacters[0].GuildName, Is.EqualTo("Hammers"));
                Assert.That(herald.TopGuilds.Select(rank => rank.GuildName), Is.EqualTo(new[] { "Starter", "Knights", "Hammers" }));
            });
        }

        [Test]
        public void HeraldResponse_PublicContractDoesNotContainPrivateFieldNames()
        {
            string[] propertyNames = typeof(DashboardHeraldResponse).Assembly
                .GetTypes()
                .Where(type => type.Namespace == "DOL.GS.API.Dashboard" && type.Name.StartsWith("DashboardHerald", StringComparison.Ordinal))
                .SelectMany(type => type.GetProperties())
                .Select(property => property.Name)
                .ToArray();

            Assert.That(propertyNames, Does.Not.Contain("AccountName"));
            Assert.That(propertyNames, Does.Not.Contain("GuildID"));
            Assert.That(propertyNames, Does.Not.Contain("IPAddress"));
            Assert.That(propertyNames, Does.Not.Contain("Email"));
            Assert.That(propertyNames, Does.Not.Contain("Webpage"));
            Assert.That(propertyNames, Does.Not.Contain("Motd"));
            Assert.That(propertyNames, Does.Not.Contain("Region"));
        }

        [Test]
        public void BuildHeraldCharacterDetail_ReturnsPublicCharacterStats()
        {
            DbGuild[] guilds =
            {
                CreateGuild("alb-guild", "Knights", eRealm.Albion, realmPoints: 7000)
            };
            DbCoreCharacter[] characters =
            {
                CreateCharacter("Alice", eRealm.Albion, level: 50, classId: 1, realmPoints: 5000, realmLevel: 31, guildId: "alb-guild"),
                CreateCharacter("Bob", eRealm.Albion, level: 42, classId: 1, realmPoints: 1200, realmLevel: 12, guildId: "alb-guild")
            };
            characters[0].BountyPoints = 450;
            characters[0].KillsAlbionPlayers = 1;
            characters[0].KillsMidgardPlayers = 2;
            characters[0].KillsHiberniaPlayers = 3;
            characters[0].KillsAlbionDeathBlows = 4;
            characters[0].KillsMidgardDeathBlows = 5;
            characters[0].KillsHiberniaDeathBlows = 6;
            characters[0].KillsAlbionSolo = 7;
            characters[0].KillsMidgardSolo = 8;
            characters[0].KillsHiberniaSolo = 9;
            characters[0].DeathsPvP = 10;

            DashboardHeraldCharacterDetail detail = DashboardAggregation.BuildHeraldCharacterDetail(
                "alice",
                characters,
                guilds,
                classId => classId == 1 ? "Armsman" : "Unknown");

            Assert.Multiple(() =>
            {
                Assert.That(detail.Name, Is.EqualTo("Alice"));
                Assert.That(detail.RealmName, Is.EqualTo("Albion"));
                Assert.That(detail.ClassName, Is.EqualTo("Armsman"));
                Assert.That(detail.GuildName, Is.EqualTo("Knights"));
                Assert.That(detail.RealmRank, Is.EqualTo("4L1"));
                Assert.That(detail.TotalPlayerKills, Is.EqualTo(6));
                Assert.That(detail.TotalDeathBlows, Is.EqualTo(15));
                Assert.That(detail.TotalSoloKills, Is.EqualTo(24));
                Assert.That(detail.PvpDeaths, Is.EqualTo(10));
            });
        }

        [Test]
        public void BuildHeraldGuildDetail_ReturnsPublicGuildStatsAndTopMembers()
        {
            DbGuild[] guilds =
            {
                CreateGuild("alb-guild", "Knights", eRealm.Albion, realmPoints: 7000)
            };
            DbCoreCharacter[] characters =
            {
                CreateCharacter("Alice", eRealm.Albion, level: 50, classId: 1, realmPoints: 5000, realmLevel: 31, guildId: "alb-guild"),
                CreateCharacter("Bob", eRealm.Albion, level: 42, classId: 1, realmPoints: 1200, realmLevel: 12, guildId: "alb-guild"),
                CreateCharacter("Other", eRealm.Midgard, level: 50, classId: 2, realmPoints: 9000, realmLevel: 40, guildId: "mid-guild")
            };

            DashboardHeraldGuildDetail detail = DashboardAggregation.BuildHeraldGuildDetail(
                "knights",
                guilds,
                characters,
                classId => classId == 1 ? "Armsman" : "Healer");

            Assert.Multiple(() =>
            {
                Assert.That(detail.GuildName, Is.EqualTo("Knights"));
                Assert.That(detail.RealmName, Is.EqualTo("Albion"));
                Assert.That(detail.MemberCount, Is.EqualTo(2));
                Assert.That(detail.Level50Members, Is.EqualTo(1));
                Assert.That(detail.TopMembers.Select(member => member.Name), Is.EqualTo(new[] { "Alice", "Bob" }));
                Assert.That(detail.TopMembers[0].ClassName, Is.EqualTo("Armsman"));
            });
        }

        [Test]
        public void BuildHeraldWarState_SummarizesKeepsTowersRelicsAndDarknessFalls()
        {
            DashboardHeraldKeepSample[] keeps =
            {
                new((int)eRealm.Albion, IsTower: false, IsUnderSiege: true),
                new((int)eRealm.Albion, IsTower: true, IsUnderSiege: false),
                new((int)eRealm.Midgard, IsTower: false, IsUnderSiege: false),
                new((int)eRealm.Hibernia, IsTower: true, IsUnderSiege: true),
                new(0, IsTower: false, IsUnderSiege: true)
            };
            DashboardHeraldRelicStatus[] relics =
            {
                new("Excalibur", "Melee", (int)eRealm.Albion, "Albion", (int)eRealm.Midgard, "Midgard", true),
                new("Mjollnir", "Magic", (int)eRealm.Midgard, "Midgard", (int)eRealm.Midgard, "Midgard", false),
                new("Lamfhota", "Magic", (int)eRealm.Hibernia, "Hibernia", (int)eRealm.Albion, "Albion", true)
            };

            DashboardHeraldWarState state = DashboardAggregation.BuildHeraldWarState("Midgard", keeps, relics);

            DashboardHeraldWarRealmSummary albion = state.RealmSummaries.Single(summary => summary.RealmId == (int)eRealm.Albion);
            DashboardHeraldWarRealmSummary midgard = state.RealmSummaries.Single(summary => summary.RealmId == (int)eRealm.Midgard);
            DashboardHeraldWarRealmSummary hibernia = state.RealmSummaries.Single(summary => summary.RealmId == (int)eRealm.Hibernia);

            Assert.Multiple(() =>
            {
                Assert.That(state.DarknessFallsOwnerRealmId, Is.EqualTo((int)eRealm.Midgard));
                Assert.That(albion.Keeps, Is.EqualTo(1));
                Assert.That(albion.Towers, Is.EqualTo(1));
                Assert.That(albion.KeepsUnderSiege, Is.EqualTo(1));
                Assert.That(albion.Relics, Is.EqualTo(1));
                Assert.That(midgard.Keeps, Is.EqualTo(1));
                Assert.That(midgard.Relics, Is.EqualTo(2));
                Assert.That(hibernia.Towers, Is.EqualTo(1));
                Assert.That(hibernia.KeepsUnderSiege, Is.EqualTo(1));
                Assert.That(state.Relics.Count(relic => relic.IsCaptured), Is.EqualTo(2));
            });
        }

        [Test]
        public void BuildHeraldRvrActivity_ReturnsRecentCrossRealmKillsOnly()
        {
            DateTime now = new(2026, 5, 12, 12, 0, 0, DateTimeKind.Utc);
            DbDashboardRvrKill[] rows =
            {
                CreateRvrKill("old", "Oldkiller", eRealm.Albion, "Oldvictim", eRealm.Midgard, now.AddDays(-3)),
                CreateRvrKill("same", "Dueler", eRealm.Albion, "Friend", eRealm.Albion, now.AddMinutes(-1)),
                CreateRvrKill("blank", "", eRealm.Albion, "Target", eRealm.Midgard, now.AddMinutes(-2)),
                CreateRvrKill("newer", "Alice", eRealm.Albion, "Bjorn", eRealm.Midgard, now.AddMinutes(-5), killerClassId: 1, killerClassName: "Armsman", victimClassId: 2, victimClassName: "Healer", regionName: "Emain Macha", realmPoints: 120, soloKill: true),
                CreateRvrKill("older", "Cian", eRealm.Hibernia, "Alice", eRealm.Albion, now.AddHours(-2), killerClassId: 3, killerClassName: "Hero", victimClassId: 1, victimClassName: "Armsman", regionName: "Hadrian's Wall", realmPoints: 80)
            };

            IReadOnlyList<DashboardHeraldRvrActivityItem> activity = DashboardAggregation.BuildHeraldRvrActivity(
                rows,
                now,
                TimeSpan.FromDays(2));

            Assert.Multiple(() =>
            {
                Assert.That(activity.Select(item => item.KillerName), Is.EqualTo(new[] { "Alice", "Cian" }));
                Assert.That(activity[0].VictimName, Is.EqualTo("Bjorn"));
                Assert.That(activity[0].KillerRealmName, Is.EqualTo("Albion"));
                Assert.That(activity[0].VictimRealmName, Is.EqualTo("Midgard"));
                Assert.That(activity[0].KillerClassName, Is.EqualTo("Armsman"));
                Assert.That(activity[0].VictimClassName, Is.EqualTo("Healer"));
                Assert.That(activity[0].RegionName, Is.EqualTo("Emain Macha"));
                Assert.That(activity[0].RealmPoints, Is.EqualTo(120));
                Assert.That(activity[0].SoloKill, Is.True);
            });
        }

        private static DashboardPerformanceStats InvokePerformanceSnapshot(object sampler)
        {
            MethodInfo getSnapshot = sampler.GetType().GetMethod(
                "GetSnapshot",
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);

            Assert.That(getSnapshot, Is.Not.Null);
            return (DashboardPerformanceStats)getSnapshot.Invoke(sampler, Array.Empty<object>());
        }

        private static object CreatePerformanceSampler(Func<IPerformanceStatistic> createStatistic)
        {
            Type samplerType = typeof(DashboardLiveResponse).Assembly.GetType("DOL.GS.API.Dashboard.DashboardPerformanceSampler");
            Assert.That(samplerType, Is.Not.Null);

            ConstructorInfo constructor = samplerType.GetConstructor(
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic,
                null,
                new[] { typeof(Func<IPerformanceStatistic>) },
                null);

            Assert.That(constructor, Is.Not.Null);
            return constructor.Invoke(new object[] { createStatistic });
        }

        private sealed class ThrowingPerformanceStatistic : IPerformanceStatistic
        {
            public double GetNextValue()
            {
                throw new PlatformNotSupportedException();
            }
        }

        private static DbServerStat CreateServerStat(DateTime statDate, int clients)
        {
            return new DbServerStat
            {
                StatDate = statDate,
                Clients = clients,
                AlbionPlayers = clients + 1,
                MidgardPlayers = clients + 2,
                HiberniaPlayers = clients + 3,
                CPU = clients + 0.5f,
                Memory = clients + 1000
            };
        }

        private static DbDashboardClassSnapshot CreateClassSnapshot(DateTime bucket, eRealm realm, int classId, string className, int players)
        {
            return new DbDashboardClassSnapshot
            {
                SnapshotClassKey = DashboardAggregation.BuildClassSnapshotKey(bucket, (int)realm, classId),
                BucketStart = bucket,
                Realm = (int)realm,
                RealmName = realm.ToString(),
                ClassId = classId,
                ClassName = className,
                Players = players
            };
        }

        private static DbCoreCharacter CreateCharacter(
            string name,
            eRealm realm,
            int level,
            int classId,
            long realmPoints,
            int realmLevel,
            string guildId,
            bool ignoreStatistics = false)
        {
            return new DbCoreCharacter
            {
                AccountName = "private-account",
                Name = name,
                Realm = (int)realm,
                Level = level,
                Class = classId,
                RealmPoints = realmPoints,
                RealmLevel = realmLevel,
                GuildID = guildId,
                LastPlayed = new DateTime(2026, 5, 10, 8, 0, 0, DateTimeKind.Utc),
                IgnoreStatistics = ignoreStatistics
            };
        }

        private static DbGuild CreateGuild(string guildId, string name, eRealm realm, long realmPoints, bool isStartingGuild = false)
        {
            return new DbGuild
            {
                GuildID = guildId,
                GuildName = name,
                Realm = (byte)realm,
                RealmPoints = realmPoints,
                BountyPoints = realmPoints / 10,
                GuildLevel = realmPoints / 1000,
                IsStartingGuild = isStartingGuild,
                Email = "private@example.invalid",
                Webpage = "https://private.invalid",
                Motd = "private motd"
            };
        }

        private static DbDashboardRvrKill CreateRvrKill(
            string id,
            string killerName,
            eRealm killerRealm,
            string victimName,
            eRealm victimRealm,
            DateTime killedAt,
            int killerClassId = 0,
            string killerClassName = "",
            int victimClassId = 0,
            string victimClassName = "",
            string regionName = "",
            int realmPoints = 0,
            bool soloKill = false)
        {
            return new DbDashboardRvrKill
            {
                KillId = id,
                KilledAt = killedAt,
                KillerName = killerName,
                KillerRealm = (int)killerRealm,
                KillerClassId = killerClassId,
                KillerClassName = killerClassName,
                VictimName = victimName,
                VictimRealm = (int)victimRealm,
                VictimClassId = victimClassId,
                VictimClassName = victimClassName,
                RegionName = regionName,
                RealmPoints = realmPoints,
                SoloKill = soloKill
            };
        }
    }
}
