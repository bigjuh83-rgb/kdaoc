using System;
using DOL.Database;
using DOL.Logging;

namespace DOL.GS
{
    public interface IDashboardRvrKillSink
    {
        void Add(DbDashboardRvrKill row);
    }

    public static class DashboardRvrKillTracker
    {
        private static readonly Logger log = LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);
        private static readonly IDashboardRvrKillSink DefaultSink = new DatabaseDashboardRvrKillSink();
        private static readonly object ErrorLogLock = new();
        private static IDashboardRvrKillSink m_sink = DefaultSink;
        private static DateTime m_nextErrorLogAt = DateTime.MinValue;

        public static IDashboardRvrKillSink Sink
        {
            get { return m_sink; }
            set { m_sink = value ?? DefaultSink; }
        }

        public static void ResetSink()
        {
            m_sink = DefaultSink;
        }

        public static void RecordPlayerKill(GamePlayer killer, GamePlayer victim, string regionName, DateTime at)
        {
            if (!IsValidPlayerKill(killer, victim))
                return;

            try
            {
                m_sink.Add(new DbDashboardRvrKill
                {
                    KillId = $"{ToUtcAssumeUtc(at):yyyyMMddHHmmssfff}-{Guid.NewGuid():N}",
                    KilledAt = ToUtcAssumeUtc(at),
                    KillerName = SafeName(killer.Name),
                    KillerRealm = (int)killer.Realm,
                    KillerClassId = killer.CharacterClass?.ID ?? 0,
                    KillerClassName = SafeName(killer.CharacterClass?.Name),
                    KillerGuildName = SafeName(killer.GuildName),
                    VictimName = SafeName(victim.Name),
                    VictimRealm = (int)victim.Realm,
                    VictimClassId = victim.CharacterClass?.ID ?? 0,
                    VictimClassName = SafeName(victim.CharacterClass?.Name),
                    VictimGuildName = SafeName(victim.GuildName),
                    RegionName = SafeName(regionName),
                    RealmPoints = 0,
                    SoloKill = false
                });
            }
            catch (Exception e)
            {
                LogFailure(e);
            }
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
                log.Error("Dashboard RvR kill tracking failed.", exception);
            }
            catch
            {
            }
        }

        private static bool IsValidPlayerKill(GamePlayer killer, GamePlayer victim)
        {
            return killer != null
                && victim != null
                && killer != victim
                && IsTrackedRealm(killer.Realm)
                && IsTrackedRealm(victim.Realm)
                && killer.Realm != victim.Realm
                && !string.IsNullOrWhiteSpace(killer.Name)
                && !string.IsNullOrWhiteSpace(victim.Name);
        }

        private static bool IsTrackedRealm(eRealm realm)
        {
            return realm == eRealm.Albion || realm == eRealm.Midgard || realm == eRealm.Hibernia;
        }

        private static string SafeName(string value)
        {
            return string.IsNullOrWhiteSpace(value) ? string.Empty : value.Trim();
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
    }

    public sealed class DatabaseDashboardRvrKillSink : IDashboardRvrKillSink
    {
        public void Add(DbDashboardRvrKill row)
        {
            GameServer.Database.AddObject(row);
        }
    }
}
