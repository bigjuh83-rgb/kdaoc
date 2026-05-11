using System;
using System.Collections.Generic;
using DOL.GS;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_DashboardRealmActivityTracker
    {
        [Test]
        public void RecordServerIssuedGold_IgnoresInvalidRealmAndNonPositiveAmount()
        {
            FakeDashboardRealmActivitySink sink = new();
            DashboardRealmActivityTracker.Sink = sink;

            DashboardRealmActivityTracker.RecordServerIssuedGold(eRealm.None, 100, DateTime.UtcNow);
            DashboardRealmActivityTracker.RecordServerIssuedGold(eRealm.Albion, 0, DateTime.UtcNow);
            DashboardRealmActivityTracker.RecordServerIssuedGold(eRealm.Albion, -5, DateTime.UtcNow);

            Assert.That(sink.Entries, Is.Empty);
        }

        [Test]
        public void RecordServerIssuedRealmPoints_ForwardsValidAmountToSink()
        {
            FakeDashboardRealmActivitySink sink = new();
            DashboardRealmActivityTracker.Sink = sink;
            DateTime at = new(2026, 5, 11, 12, 42, 0, DateTimeKind.Utc);

            DashboardRealmActivityTracker.RecordServerIssuedRealmPoints(eRealm.Midgard, 75, at);

            Assert.That(sink.Entries, Has.Count.EqualTo(1));
            Assert.Multiple(() =>
            {
                Assert.That(sink.Entries[0].Realm, Is.EqualTo(eRealm.Midgard));
                Assert.That(sink.Entries[0].RealmPoints, Is.EqualTo(75));
                Assert.That(sink.Entries[0].Gold, Is.EqualTo(0));
                Assert.That(sink.Entries[0].At, Is.EqualTo(at));
            });
        }

        [Test]
        public void RecordServerIssuedGold_ForwardsValidAmountToSink()
        {
            FakeDashboardRealmActivitySink sink = new();
            DashboardRealmActivityTracker.Sink = sink;
            DateTime at = new(2026, 5, 11, 12, 42, 0, DateTimeKind.Utc);

            DashboardRealmActivityTracker.RecordServerIssuedGold(eRealm.Albion, 125, at);

            Assert.That(sink.Entries, Has.Count.EqualTo(1));
            Assert.Multiple(() =>
            {
                Assert.That(sink.Entries[0].Realm, Is.EqualTo(eRealm.Albion));
                Assert.That(sink.Entries[0].Gold, Is.EqualTo(125));
                Assert.That(sink.Entries[0].RealmPoints, Is.EqualTo(0));
                Assert.That(sink.Entries[0].At, Is.EqualTo(at));
            });
        }

        [Test]
        public void RecordServerIssuedGold_DoesNotThrowWhenSinkFails()
        {
            DashboardRealmActivityTracker.Sink = new ThrowingDashboardRealmActivitySink();

            Assert.DoesNotThrow(() => DashboardRealmActivityTracker.RecordServerIssuedGold(eRealm.Hibernia, 100, DateTime.UtcNow));
        }

        [Test]
        public void BufferedSink_AddDoesNotTouchRepositoryUntilFlush()
        {
            FakeDashboardRealmActivityRepository repository = new();
            BufferedDashboardRealmActivitySink sink = new(repository, false);

            sink.Add(eRealm.Albion, 100, 0, DateTime.UtcNow);

            Assert.Multiple(() =>
            {
                Assert.That(repository.FindCalls, Is.EqualTo(0));
                Assert.That(repository.AddCalls, Is.EqualTo(0));
                Assert.That(repository.SaveCalls, Is.EqualTo(0));
            });

            sink.Flush();

            Assert.Multiple(() =>
            {
                Assert.That(repository.FindCalls, Is.EqualTo(1));
                Assert.That(repository.AddCalls, Is.EqualTo(1));
                Assert.That(repository.SaveCalls, Is.EqualTo(0));
            });
        }

        [Test]
        public void BufferedSink_AutoFlushUsesDelayedBatch()
        {
            FakeDashboardRealmActivityRepository repository = new();
            using BufferedDashboardRealmActivitySink sink = new(repository, true, TimeSpan.FromHours(1));

            sink.Add(eRealm.Albion, 100, 0, DateTime.UtcNow);

            Assert.Multiple(() =>
            {
                Assert.That(repository.FindCalls, Is.EqualTo(0));
                Assert.That(repository.AddCalls, Is.EqualTo(0));
                Assert.That(repository.SaveCalls, Is.EqualTo(0));
            });

            sink.Flush();

            Assert.That(repository.AddCalls, Is.EqualTo(1));
        }

        [Test]
        public void BufferedSink_FlushRequeuesWhenExistingRowSaveFails()
        {
            FakeDashboardRealmActivityRepository repository = new();
            BufferedDashboardRealmActivitySink sink = new(repository, false);
            DateTime at = new(2026, 5, 11, 12, 42, 0, DateTimeKind.Utc);
            string key = DOL.GS.API.Dashboard.DashboardAggregation.BuildActivityKey(at, eRealm.Albion);
            repository.Rows[key] = new DOL.Database.DbDashboardRealmActivity
            {
                BucketRealmKey = key,
                BucketStart = DOL.GS.API.Dashboard.DashboardAggregation.GetHourBucket(at),
                Realm = (int)eRealm.Albion,
                ServerIssuedGold = 20,
                ServerIssuedRealmPoints = 5
            };
            repository.SaveResults.Enqueue(false);
            repository.SaveResults.Enqueue(true);

            sink.Add(eRealm.Albion, 100, 7, at);
            sink.Flush();
            sink.Flush();

            Assert.Multiple(() =>
            {
                Assert.That(repository.SaveCalls, Is.EqualTo(2));
                Assert.That(repository.Rows[key].ServerIssuedGold, Is.EqualTo(120));
                Assert.That(repository.Rows[key].ServerIssuedRealmPoints, Is.EqualTo(12));
            });
        }

        [Test]
        public void BufferedSink_FlushAggregatesSameHourAndSeparatesRealms()
        {
            FakeDashboardRealmActivityRepository repository = new();
            BufferedDashboardRealmActivitySink sink = new(repository, false);
            DateTime at = new(2026, 5, 11, 12, 42, 0, DateTimeKind.Utc);

            sink.Add(eRealm.Albion, 100, 0, at);
            sink.Add(eRealm.Albion, 50, 7, at.AddMinutes(5));
            sink.Add(eRealm.Midgard, 25, 3, at);
            sink.Flush();

            Assert.That(repository.Rows, Has.Count.EqualTo(2));
            string albionKey = DOL.GS.API.Dashboard.DashboardAggregation.BuildActivityKey(at, eRealm.Albion);
            string midgardKey = DOL.GS.API.Dashboard.DashboardAggregation.BuildActivityKey(at, eRealm.Midgard);

            Assert.Multiple(() =>
            {
                Assert.That(repository.Rows[albionKey].ServerIssuedGold, Is.EqualTo(150));
                Assert.That(repository.Rows[albionKey].ServerIssuedRealmPoints, Is.EqualTo(7));
                Assert.That(repository.Rows[midgardKey].ServerIssuedGold, Is.EqualTo(25));
                Assert.That(repository.Rows[midgardKey].ServerIssuedRealmPoints, Is.EqualTo(3));
            });
        }

        [Test]
        public void BufferedSink_FlushClampsOverflow()
        {
            FakeDashboardRealmActivityRepository repository = new();
            BufferedDashboardRealmActivitySink sink = new(repository, false);
            DateTime at = new(2026, 5, 11, 12, 42, 0, DateTimeKind.Utc);
            string key = DOL.GS.API.Dashboard.DashboardAggregation.BuildActivityKey(at, eRealm.Hibernia);
            repository.Rows[key] = new DOL.Database.DbDashboardRealmActivity
            {
                BucketRealmKey = key,
                BucketStart = DOL.GS.API.Dashboard.DashboardAggregation.GetHourBucket(at),
                Realm = (int)eRealm.Hibernia,
                ServerIssuedGold = long.MaxValue - 2,
                ServerIssuedRealmPoints = long.MaxValue - 3
            };

            sink.Add(eRealm.Hibernia, 10, 10, at);
            sink.Flush();

            Assert.Multiple(() =>
            {
                Assert.That(repository.Rows[key].ServerIssuedGold, Is.EqualTo(long.MaxValue));
                Assert.That(repository.Rows[key].ServerIssuedRealmPoints, Is.EqualTo(long.MaxValue));
            });
        }

        [TearDown]
        public void TearDown()
        {
            DashboardRealmActivityTracker.ResetSink();
        }

        private sealed class FakeDashboardRealmActivitySink : IDashboardRealmActivitySink
        {
            public List<Entry> Entries { get; } = new();

            public void Add(eRealm realm, long gold, long realmPoints, DateTime at)
            {
                Entries.Add(new Entry(realm, gold, realmPoints, at));
            }
        }

        private sealed class ThrowingDashboardRealmActivitySink : IDashboardRealmActivitySink
        {
            public void Add(eRealm realm, long gold, long realmPoints, DateTime at)
            {
                throw new InvalidOperationException();
            }
        }

        private sealed class FakeDashboardRealmActivityRepository : IDashboardRealmActivityRepository
        {
            public Dictionary<string, DOL.Database.DbDashboardRealmActivity> Rows { get; } = new();
            public Queue<bool> AddResults { get; } = new();
            public Queue<bool> SaveResults { get; } = new();
            public int FindCalls { get; private set; }
            public int AddCalls { get; private set; }
            public int SaveCalls { get; private set; }

            public DOL.Database.DbDashboardRealmActivity Find(string key)
            {
                FindCalls++;
                return Rows.TryGetValue(key, out DOL.Database.DbDashboardRealmActivity row)
                    ? Clone(row)
                    : null;
            }

            public bool Add(DOL.Database.DbDashboardRealmActivity row)
            {
                AddCalls++;
                bool result = AddResults.Count == 0 || AddResults.Dequeue();

                if (result)
                    Rows[row.BucketRealmKey] = Clone(row);

                return result;
            }

            public bool Save(DOL.Database.DbDashboardRealmActivity row)
            {
                SaveCalls++;
                bool result = SaveResults.Count == 0 || SaveResults.Dequeue();

                if (result)
                    Rows[row.BucketRealmKey] = Clone(row);

                return result;
            }

            private static DOL.Database.DbDashboardRealmActivity Clone(DOL.Database.DbDashboardRealmActivity row)
            {
                return new DOL.Database.DbDashboardRealmActivity
                {
                    BucketRealmKey = row.BucketRealmKey,
                    BucketStart = row.BucketStart,
                    Realm = row.Realm,
                    ServerIssuedGold = row.ServerIssuedGold,
                    ServerIssuedRealmPoints = row.ServerIssuedRealmPoints
                };
            }
        }

        private sealed record Entry(eRealm Realm, long Gold, long RealmPoints, DateTime At);
    }
}
