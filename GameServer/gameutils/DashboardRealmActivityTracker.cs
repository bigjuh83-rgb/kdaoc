using System;
using System.Collections.Generic;
using System.Threading;
using DOL.Database;
using DOL.GS.API.Dashboard;
using DOL.Logging;

namespace DOL.GS
{
    public interface IDashboardRealmActivitySink
    {
        void Add(eRealm realm, long gold, long realmPoints, DateTime at);
    }

    public interface IDashboardRealmActivityRepository
    {
        DbDashboardRealmActivity Find(string key);
        bool Add(DbDashboardRealmActivity row);
        bool Save(DbDashboardRealmActivity row);
    }

    public static class DashboardRealmActivityTracker
    {
        private static readonly Logger log = LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);
        private static readonly IDashboardRealmActivitySink DefaultSink = new BufferedDashboardRealmActivitySink();
        private static readonly object ErrorLogLock = new();
        private static IDashboardRealmActivitySink m_sink = DefaultSink;
        private static DateTime m_nextErrorLogAt = DateTime.MinValue;

        public static IDashboardRealmActivitySink Sink
        {
            get { return m_sink; }
            set { m_sink = value ?? DefaultSink; }
        }

        public static void ResetSink()
        {
            m_sink = DefaultSink;
        }

        public static void RecordServerIssuedGold(eRealm realm, long copper, DateTime at)
        {
            Record(realm, copper, 0, at);
        }

        public static void RecordServerIssuedRealmPoints(eRealm realm, long realmPoints, DateTime at)
        {
            Record(realm, 0, realmPoints, at);
        }

        internal static void LogFailure(Exception exception)
        {
            DateTime now = DateTime.UtcNow;

            lock (ErrorLogLock)
            {
                if (now < m_nextErrorLogAt)
                    return;

                m_nextErrorLogAt = now.AddMinutes(1);
            }

            try
            {
                log.Error("Dashboard realm activity tracking failed.", exception);
            }
            catch
            {
            }
        }

        private static void Record(eRealm realm, long gold, long realmPoints, DateTime at)
        {
            if (!IsTrackedRealm(realm) || (gold <= 0 && realmPoints <= 0))
                return;

            try
            {
                m_sink.Add(realm, Math.Max(0, gold), Math.Max(0, realmPoints), at);
            }
            catch (Exception e)
            {
                LogFailure(e);
            }
        }

        private static bool IsTrackedRealm(eRealm realm)
        {
            return realm == eRealm.Albion || realm == eRealm.Midgard || realm == eRealm.Hibernia;
        }
    }

    public sealed class BufferedDashboardRealmActivitySink : IDashboardRealmActivitySink, IDisposable
    {
        private static readonly TimeSpan DefaultFlushDelay = TimeSpan.FromSeconds(30);
        private readonly object m_lock = new();
        private readonly Dictionary<string, PendingActivity> m_pending = new();
        private readonly IDashboardRealmActivityRepository m_repository;
        private readonly bool m_autoFlush;
        private readonly TimeSpan m_flushDelay;
        private Timer m_flushTimer;
        private bool m_flushQueued;
        private bool m_disposed;

        public BufferedDashboardRealmActivitySink()
            : this(new DatabaseDashboardRealmActivityRepository(), true, DefaultFlushDelay)
        {
        }

        public BufferedDashboardRealmActivitySink(IDashboardRealmActivityRepository repository, bool autoFlush)
            : this(repository, autoFlush, DefaultFlushDelay)
        {
        }

        public BufferedDashboardRealmActivitySink(IDashboardRealmActivityRepository repository, bool autoFlush, TimeSpan flushDelay)
        {
            m_repository = repository ?? throw new ArgumentNullException(nameof(repository));
            m_autoFlush = autoFlush;
            m_flushDelay = flushDelay < TimeSpan.Zero ? TimeSpan.Zero : flushDelay;
        }

        public void Add(eRealm realm, long gold, long realmPoints, DateTime at)
        {
            if (gold <= 0 && realmPoints <= 0)
                return;

            DateTime bucket = DashboardAggregation.GetHourBucket(at);
            string key = DashboardAggregation.BuildActivityKey(bucket, realm);

            lock (m_lock)
            {
                if (!m_pending.TryGetValue(key, out PendingActivity pending))
                {
                    pending = new PendingActivity(key, bucket, realm);
                    m_pending[key] = pending;
                }

                pending.Gold = AddClamped(pending.Gold, gold);
                pending.RealmPoints = AddClamped(pending.RealmPoints, realmPoints);

                if (m_autoFlush)
                    QueueFlushLocked();
            }
        }

        public void Dispose()
        {
            Timer timer;

            lock (m_lock)
            {
                m_disposed = true;
                m_flushQueued = false;
                timer = m_flushTimer;
                m_flushTimer = null;
            }

            timer?.Dispose();
        }

        public void Flush()
        {
            List<PendingActivity> snapshot;

            lock (m_lock)
            {
                if (m_pending.Count == 0)
                    return;

                snapshot = new List<PendingActivity>(m_pending.Values);
                m_pending.Clear();
            }

            foreach (PendingActivity activity in snapshot)
            {
                bool persisted = false;

                try
                {
                    persisted = Flush(activity);
                }
                catch (Exception e)
                {
                    DashboardRealmActivityTracker.LogFailure(e);
                }

                if (!persisted)
                {
                    Requeue(activity);
                    DashboardRealmActivityTracker.LogFailure(new InvalidOperationException("Dashboard realm activity persistence failed."));
                }
            }
        }

        private static long AddClamped(long current, long amount)
        {
            if (amount <= 0)
                return current;

            if (current > long.MaxValue - amount)
                return long.MaxValue;

            return current + amount;
        }

        private bool Flush(PendingActivity activity)
        {
            DbDashboardRealmActivity row = m_repository.Find(activity.Key);

            if (row == null)
            {
                row = new DbDashboardRealmActivity
                {
                    BucketRealmKey = activity.Key,
                    BucketStart = activity.BucketStart,
                    Realm = (int)activity.Realm,
                    ServerIssuedGold = activity.Gold,
                    ServerIssuedRealmPoints = activity.RealmPoints
                };

                if (m_repository.Add(row))
                    return true;

                row = m_repository.Find(activity.Key);

                if (row == null)
                    return false;
            }

            row.ServerIssuedGold = AddClamped(row.ServerIssuedGold, activity.Gold);
            row.ServerIssuedRealmPoints = AddClamped(row.ServerIssuedRealmPoints, activity.RealmPoints);
            return m_repository.Save(row);
        }

        private void Requeue(PendingActivity activity)
        {
            lock (m_lock)
            {
                if (m_disposed)
                    return;

                if (!m_pending.TryGetValue(activity.Key, out PendingActivity pending))
                {
                    pending = new PendingActivity(activity.Key, activity.BucketStart, activity.Realm);
                    m_pending[activity.Key] = pending;
                }

                pending.Gold = AddClamped(pending.Gold, activity.Gold);
                pending.RealmPoints = AddClamped(pending.RealmPoints, activity.RealmPoints);

                if (m_autoFlush)
                    QueueFlushLocked();
            }
        }

        private void QueueFlushLocked()
        {
            if (m_disposed || m_flushQueued)
                return;

            try
            {
                if (m_flushTimer == null)
                    m_flushTimer = new Timer(_ => FlushQueued(), null, Timeout.InfiniteTimeSpan, Timeout.InfiniteTimeSpan);

                m_flushTimer.Change(m_flushDelay, Timeout.InfiniteTimeSpan);
                m_flushQueued = true;
            }
            catch (Exception e)
            {
                DashboardRealmActivityTracker.LogFailure(e);
                m_flushQueued = false;
            }
        }

        private void FlushQueued()
        {
            Flush();

            lock (m_lock)
            {
                if (m_disposed)
                    return;

                m_flushQueued = false;

                if (m_autoFlush && m_pending.Count > 0)
                    QueueFlushLocked();
            }
        }

        private sealed class PendingActivity
        {
            public PendingActivity(string key, DateTime bucketStart, eRealm realm)
            {
                Key = key;
                BucketStart = bucketStart;
                Realm = realm;
            }

            public string Key { get; }
            public DateTime BucketStart { get; }
            public eRealm Realm { get; }
            public long Gold { get; set; }
            public long RealmPoints { get; set; }
        }
    }

    public sealed class DatabaseDashboardRealmActivityRepository : IDashboardRealmActivityRepository
    {
        public DbDashboardRealmActivity Find(string key)
        {
            return GameServer.Database.FindObjectByKey<DbDashboardRealmActivity>(key);
        }

        public bool Add(DbDashboardRealmActivity row)
        {
            return GameServer.Database.AddObject(row);
        }

        public bool Save(DbDashboardRealmActivity row)
        {
            return GameServer.Database.SaveObject(row);
        }
    }
}
