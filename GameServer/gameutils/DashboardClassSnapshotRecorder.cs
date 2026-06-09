using System;
using System.Collections.Generic;
using System.Linq;
using DOL.Database;
using DOL.GS.API.Dashboard;
using DOL.Logging;

namespace DOL.GS
{
    public interface IDashboardClassSnapshotRepository
    {
        DbDashboardClassSnapshot Find(string key);
        bool Add(DbDashboardClassSnapshot row);
        bool Save(DbDashboardClassSnapshot row);
    }

    public static class DashboardClassSnapshotRecorder
    {
        private static readonly Logger log = LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);
        private static readonly eRealm[] TrackedRealms =
        {
            eRealm.Albion,
            eRealm.Midgard,
            eRealm.Hibernia
        };

        public static void SaveCurrentSnapshot(DateTime at)
        {
            try
            {
                SaveSnapshot(CreateCurrentSamples(), at, new DatabaseDashboardClassSnapshotRepository());
            }
            catch (Exception e)
            {
                try
                {
                    log.Error("Dashboard class snapshot persistence failed.", e);
                }
                catch
                {
                }
            }
        }

        internal static void SaveSnapshot(
            IEnumerable<DashboardClassSample> samples,
            DateTime at,
            IDashboardClassSnapshotRepository repository)
        {
            if (repository == null)
                throw new ArgumentNullException(nameof(repository));

            DateTime bucket = DashboardAggregation.GetMinuteBucket(at);
            Dictionary<ClassSnapshotKey, int> counts = (samples ?? Enumerable.Empty<DashboardClassSample>())
                .Where(sample =>
                    sample != null
                    && IsTrackedRealm(sample.RealmId)
                    && sample.ClassId > 0
                    && !string.IsNullOrWhiteSpace(sample.ClassName))
                .GroupBy(sample => new ClassSnapshotKey(
                    sample.RealmId,
                    string.IsNullOrWhiteSpace(sample.RealmName) ? GlobalConstants.RealmToName((eRealm)sample.RealmId) : sample.RealmName,
                    sample.ClassId,
                    sample.ClassName))
                .ToDictionary(group => group.Key, group => group.Count());

            foreach (eRealm realm in TrackedRealms)
            {
                string realmName = GlobalConstants.RealmToName(realm);
                Upsert(repository, bucket, (int)realm, realmName, 0, "__snapshot__", 0);
            }

            foreach (KeyValuePair<ClassSnapshotKey, int> item in counts)
            {
                Upsert(
                    repository,
                    bucket,
                    item.Key.RealmId,
                    item.Key.RealmName,
                    item.Key.ClassId,
                    item.Key.ClassName,
                    Math.Max(0, item.Value));
            }
        }

        private static IEnumerable<DashboardClassSample> CreateCurrentSamples()
        {
            foreach (eRealm realm in TrackedRealms)
            {
                foreach (GamePlayer player in ClientService.Instance.GetPlayersOfRealm(realm).Where(player => player != null))
                {
                    ICharacterClass characterClass = player.CharacterClass;

                    if (characterClass == null)
                        continue;

                    yield return new DashboardClassSample(
                        (int)realm,
                        GlobalConstants.RealmToName(realm),
                        characterClass.ID,
                        characterClass.Name ?? $"Class {characterClass.ID}");
                }
            }
        }

        private static void Upsert(
            IDashboardClassSnapshotRepository repository,
            DateTime bucket,
            int realmId,
            string realmName,
            int classId,
            string className,
            int players)
        {
            string key = DashboardAggregation.BuildClassSnapshotKey(bucket, realmId, classId);
            DbDashboardClassSnapshot row = repository.Find(key);

            if (row == null)
            {
                row = new DbDashboardClassSnapshot
                {
                    SnapshotClassKey = key,
                    BucketStart = bucket,
                    Realm = realmId,
                    RealmName = realmName,
                    ClassId = classId,
                    ClassName = className,
                    Players = players
                };

                if (repository.Add(row))
                    return;

                row = repository.Find(key);

                if (row == null)
                    throw new InvalidOperationException("Dashboard class snapshot insert failed.");
            }

            row.BucketStart = bucket;
            row.Realm = realmId;
            row.RealmName = realmName;
            row.ClassId = classId;
            row.ClassName = className;
            row.Players = players;

            if (!repository.Save(row))
                throw new InvalidOperationException("Dashboard class snapshot update failed.");
        }

        private static bool IsTrackedRealm(int realmId)
        {
            return realmId == (int)eRealm.Albion
                || realmId == (int)eRealm.Midgard
                || realmId == (int)eRealm.Hibernia;
        }

        private sealed record ClassSnapshotKey(int RealmId, string RealmName, int ClassId, string ClassName);
    }

    public sealed class DatabaseDashboardClassSnapshotRepository : IDashboardClassSnapshotRepository
    {
        public DbDashboardClassSnapshot Find(string key)
        {
            return GameServer.Database.FindObjectByKey<DbDashboardClassSnapshot>(key);
        }

        public bool Add(DbDashboardClassSnapshot row)
        {
            return GameServer.Database.AddObject(row);
        }

        public bool Save(DbDashboardClassSnapshot row)
        {
            return GameServer.Database.SaveObject(row);
        }
    }
}
