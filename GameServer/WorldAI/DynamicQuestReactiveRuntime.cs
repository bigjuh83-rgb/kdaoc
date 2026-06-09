using System;
using System.Threading;
using DOL.Events;
using DOL.GS.ServerProperties;
using DOL.Logging;

namespace DOL.GS.WorldAI
{
    public static class DynamicQuestReactiveRuntime
    {
        private static readonly Logger Log = LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);
        private static readonly Lock RuntimeLock = new();
        private static Timer TimeoutTimer;
        private static int TickInProgress;

        public static int LastTimeoutAdvancedCount { get; private set; }
        public static DateTime LastTickAt { get; private set; }

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
                if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED)
                    return;

                TimeoutTimer = new Timer(Tick, null, TimeSpan.FromSeconds(30), TimeSpan.FromSeconds(30));
            }
        }

        public static void StopTimer()
        {
            lock (RuntimeLock)
                StopTimerLocked();
        }

        private static void StopTimerLocked()
        {
            TimeoutTimer?.Change(Timeout.InfiniteTimeSpan, Timeout.InfiniteTimeSpan);
            TimeoutTimer?.Dispose();
            TimeoutTimer = null;
        }

        private static void Tick(object state)
        {
            if (Interlocked.Exchange(ref TickInProgress, 1) == 1)
                return;

            try
            {
                if (!Properties.KDAOC_DYNAMIC_QUEST_ENABLED)
                    return;

                LastTickAt = DateTime.UtcNow;
                LastTimeoutAdvancedCount = DynamicQuestRuntimeService.Instance.TickTimeouts(LastTickAt);
            }
            catch (Exception e)
            {
                Log.Warn("Dynamic quest reactive runtime tick failed.", e);
            }
            finally
            {
                Interlocked.Exchange(ref TickInProgress, 0);
            }
        }
    }
}
