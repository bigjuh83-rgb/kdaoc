using System;
using System.Threading;
using DOL.Events;
using DOL.GS.ServerProperties;
using DOL.Logging;

namespace DOL.GS.WorldAI
{
    public static class MobGrowthRuntime
    {
        private static readonly Logger Log = LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);
        private static readonly Lock RuntimeLock = new();
        private static Timer ScanTimer;

        [GameServerStartedEvent]
        public static void OnServerStarted(DOLEvent e, object sender, EventArgs args)
        {
            RestartTimer();
        }

        [GameServerStoppedEvent]
        [ScriptUnloadedEvent]
        public static void OnServerStopped(DOLEvent e, object sender, EventArgs args)
        {
            StopTimer();
        }

        public static void RestartTimer()
        {
            lock (RuntimeLock)
            {
                StopTimerLocked();

                if (!Properties.WORLDAI_MOB_GROWTH_ENABLED)
                    return;

                int minutes = Math.Max(1, Properties.WORLDAI_MOB_GROWTH_TICK_MINUTES);
                ScanTimer = new Timer(Scan, null, TimeSpan.FromMinutes(minutes), Timeout.InfiniteTimeSpan);
            }
        }

        public static void StopTimer()
        {
            lock (RuntimeLock)
                StopTimerLocked();
        }

        private static void StopTimerLocked()
        {
            ScanTimer?.Change(Timeout.InfiniteTimeSpan, Timeout.InfiniteTimeSpan);
            ScanTimer?.Dispose();
            ScanTimer = null;
        }

        private static void Scan(object state)
        {
            try
            {
                int scanned = MobGrowthService.Instance.ScanActiveWorld(500);

                if (Log.IsInfoEnabled && scanned > 0)
                    Log.Info($"WorldAI mob growth scan observed {scanned} NPCs.");
            }
            catch (Exception ex)
            {
                Log.Error("WorldAI mob growth scan failed.", ex);
            }
            finally
            {
                lock (RuntimeLock)
                {
                    if (ScanTimer != null && Properties.WORLDAI_MOB_GROWTH_ENABLED)
                        ScanTimer.Change(TimeSpan.FromMinutes(Math.Max(1, Properties.WORLDAI_MOB_GROWTH_TICK_MINUTES)), Timeout.InfiniteTimeSpan);
                }
            }
        }
    }
}
