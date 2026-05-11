using System;
using System.Linq;
using DOL.Database;
using DOL.GS.API.Dashboard;
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
                new(1, "Armsman"),
                new(1, "Armsman"),
                new(2, "Cabalist"),
                new(0, ""),
                new(-1, "Broken")
            };

            var stats = DashboardAggregation.BuildClassStats(samples);

            Assert.That(stats, Has.Count.EqualTo(2));
            Assert.Multiple(() =>
            {
                Assert.That(stats[0].ClassId, Is.EqualTo(1));
                Assert.That(stats[0].ClassName, Is.EqualTo("Armsman"));
                Assert.That(stats[0].Players, Is.EqualTo(2));
                Assert.That(stats[1].ClassId, Is.EqualTo(2));
                Assert.That(stats[1].ClassName, Is.EqualTo("Cabalist"));
                Assert.That(stats[1].Players, Is.EqualTo(1));
            });
        }

        [Test]
        public void BuildRealmStats_ClampsNegativeCounts()
        {
            var stats = DashboardAggregation.BuildRealmStats(-1, 2, -3);

            Assert.That(stats.Select(stat => stat.Players), Is.EqualTo(new[] { 0, 2, 0 }));
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
    }
}
