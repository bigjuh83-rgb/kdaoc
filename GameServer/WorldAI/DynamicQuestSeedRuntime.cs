using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;
using DOL.Events;
using DOL.GS.ServerProperties;
using DOL.Logging;

namespace DOL.GS.WorldAI
{
    public static class DynamicQuestSeedRuntime
    {
        private static readonly Logger Log = LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);
        private static readonly Lock RuntimeLock = new();
        private static Timer SeedTimer;
        private static Func<DynamicQuestSeedSummary> SeedFromWorldCallback = () => DynamicQuestSeedService.Instance.SeedFromWorld();
        private static Func<DynamicQuestSeedSummary> PrefillStoryCacheFromWorldCallback = () => DynamicQuestSeedService.Instance.PrefillStoryCacheFromWorld();
        private static Func<DynamicQuestStoryCachePrefillPlanSnapshot> PrefillStoryCachePlanFromWorldCallback =
            () => DynamicQuestSeedService.Instance.GetStoryCachePrefillPlanSnapshotFromWorld(1);
        private static TimeSpan InitialSeedDelay = TimeSpan.FromSeconds(10);
        private static int SeedInProgress;
        private static TimeSpan DeferredStoryCachePrefillDelay = TimeSpan.FromSeconds(30);
        private static int DeferredStoryCachePrefillInProgress;

        public static DynamicQuestSeedSummary LastSummary { get; private set; }

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
            bool shouldSeed;

            lock (RuntimeLock)
            {
                StopTimerLocked();
            }

            lock (RuntimeLock)
            {
                shouldSeed = Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_ENABLED;
                if (!shouldSeed)
                    return;

                SeedTimer = new Timer(Seed, null, Timeout.InfiniteTimeSpan, Timeout.InfiniteTimeSpan);
                LastSummary = new DynamicQuestSeedSummary
                {
                    Enabled = true,
                    DynamicQuestEnabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                    GeneratedAt = DateTime.UtcNow,
                    WorldRevision = Properties.KDAOC_DYNAMIC_QUEST_WORLD_REVISION ?? string.Empty,
                    Messages = { "initial seed scheduled" }
                };

                ThreadPool.QueueUserWorkItem(RunInitialSeedAfterDelay);
            }
        }

        public static void StopTimer()
        {
            lock (RuntimeLock)
                StopTimerLocked();
        }

        private static void StopTimerLocked()
        {
            SeedTimer?.Change(Timeout.InfiniteTimeSpan, Timeout.InfiniteTimeSpan);
            SeedTimer?.Dispose();
                SeedTimer = null;
        }

        private static void RunInitialSeedAfterDelay(object state)
        {
            TimeSpan delay;
            lock (RuntimeLock)
                delay = InitialSeedDelay;

            if (delay > TimeSpan.Zero)
                Thread.Sleep(delay);

            Seed(null);
        }

        internal static void SetSeedFromWorldForTest(Func<DynamicQuestSeedSummary> seedFromWorld)
        {
            lock (RuntimeLock)
                SeedFromWorldCallback = seedFromWorld ?? (() => DynamicQuestSeedService.Instance.SeedFromWorld());
        }

        internal static void SetPrefillStoryCacheFromWorldForTest(Func<DynamicQuestSeedSummary> prefillStoryCacheFromWorld)
        {
            lock (RuntimeLock)
                PrefillStoryCacheFromWorldCallback = prefillStoryCacheFromWorld ?? (() => DynamicQuestSeedService.Instance.PrefillStoryCacheFromWorld());
        }

        internal static void SetPrefillStoryCachePlanFromWorldForTest(Func<DynamicQuestStoryCachePrefillPlanSnapshot> prefillStoryCachePlanFromWorld)
        {
            lock (RuntimeLock)
                PrefillStoryCachePlanFromWorldCallback = prefillStoryCachePlanFromWorld ?? (() => DynamicQuestSeedService.Instance.GetStoryCachePrefillPlanSnapshotFromWorld(1));
        }

        internal static void SetInitialSeedDelayForTest(TimeSpan delay)
        {
            lock (RuntimeLock)
                InitialSeedDelay = delay < TimeSpan.Zero ? TimeSpan.Zero : delay;
        }

        internal static void ResetForTest()
        {
            lock (RuntimeLock)
            {
                StopTimerLocked();
                SeedFromWorldCallback = () => DynamicQuestSeedService.Instance.SeedFromWorld();
                PrefillStoryCacheFromWorldCallback = () => DynamicQuestSeedService.Instance.PrefillStoryCacheFromWorld();
                PrefillStoryCachePlanFromWorldCallback = () => DynamicQuestSeedService.Instance.GetStoryCachePrefillPlanSnapshotFromWorld(1);
                InitialSeedDelay = TimeSpan.FromSeconds(10);
                DeferredStoryCachePrefillDelay = TimeSpan.FromSeconds(30);
                LastSummary = null;
            }

            Interlocked.Exchange(ref SeedInProgress, 0);
            Interlocked.Exchange(ref DeferredStoryCachePrefillInProgress, 0);
        }

        private static void Seed(object state)
        {
            if (Interlocked.Exchange(ref SeedInProgress, 1) == 1)
                return;

            try
            {
                Func<DynamicQuestSeedSummary> seedFromWorld;
                lock (RuntimeLock)
                {
                    if (SeedTimer == null || !Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_ENABLED)
                        return;

                    seedFromWorld = SeedFromWorldCallback;
                }

                if (Log.IsInfoEnabled)
                    Log.Info("Dynamic quest auto seed executing.");

                Stopwatch stopwatch = Stopwatch.StartNew();
                LastSummary = new DynamicQuestSeedSummary
                {
                    Enabled = true,
                    DynamicQuestEnabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                    GeneratedAt = DateTime.UtcNow,
                    WorldRevision = Properties.KDAOC_DYNAMIC_QUEST_WORLD_REVISION ?? string.Empty,
                    Messages = { "seed running: seedFromWorld" }
                };

                DynamicQuestSeedSummary summary = seedFromWorld();
                if (Log.IsInfoEnabled)
                    Log.Info($"Dynamic quest auto seed world pass completed in {stopwatch.ElapsedMilliseconds}ms.");

                LastSummary = summary;
                PrefillStoryCacheAfterSeed(summary);
                QueueDeferredStoryCachePrefillIfNeeded();
            }
            catch (Exception ex)
            {
                Log.Error("Dynamic quest auto seed failed.", ex);
            }
            finally
            {
                Interlocked.Exchange(ref SeedInProgress, 0);

                lock (RuntimeLock)
                {
                    if (SeedTimer != null && Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_ENABLED)
                        SeedTimer.Change(TimeSpan.FromMinutes(Math.Max(1, Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_TICK_MINUTES)), Timeout.InfiniteTimeSpan);
                }
            }
        }

        private static void PrefillStoryCacheAfterSeed(DynamicQuestSeedSummary seedSummary)
        {
            if (seedSummary == null || !Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_USE_LLM)
            {
                if (Log.IsInfoEnabled && seedSummary != null)
                    Log.Info("Dynamic quest story cache prefill skipped after seed because LLM auto seed is disabled.");
                return;
            }

            Func<DynamicQuestSeedSummary> prefillStoryCacheFromWorld;
            Func<DynamicQuestStoryCachePrefillPlanSnapshot> prefillStoryCachePlanFromWorld;
            lock (RuntimeLock)
            {
                prefillStoryCacheFromWorld = PrefillStoryCacheFromWorldCallback;
                prefillStoryCachePlanFromWorld = PrefillStoryCachePlanFromWorldCallback;
            }

            try
            {
                DynamicQuestStoryCachePrefillPlanSnapshot plan = prefillStoryCachePlanFromWorld();
                if (plan != null)
                {
                    seedSummary.StoryCachePrefillCandidates = plan.TotalCandidates;
                    string runningMessage = $"story cache prefill running: candidates={plan.TotalCandidates}";
                    if (!seedSummary.Messages.Contains(runningMessage))
                        seedSummary.Messages.Add(runningMessage);
                    LastSummary = seedSummary;
                }

                DynamicQuestSeedSummary prefillSummary = prefillStoryCacheFromWorld();
                if (prefillSummary == null)
                    return;

                MergePrefillSummary(seedSummary, prefillSummary);
                LastSummary = seedSummary;
            }
            catch (Exception ex)
            {
                string message = $"story cache prefill failed: {ex.Message}";
                if (!seedSummary.Messages.Contains(message))
                    seedSummary.Messages.Add(message);
                LastSummary = seedSummary;
                if (Log.IsWarnEnabled)
                    Log.Warn($"Dynamic quest story cache prefill failed: {ex.Message}");
            }
        }

        private static void QueueDeferredStoryCachePrefillIfNeeded()
        {
            if (!Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_USE_LLM)
                return;

            DynamicQuestSeedSummary summary = LastSummary;
            if (summary != null && summary.StoryCachePrefillCandidates > 0)
                return;

            if (Interlocked.Exchange(ref DeferredStoryCachePrefillInProgress, 1) == 1)
                return;

            ThreadPool.QueueUserWorkItem(RunDeferredStoryCachePrefill);
        }

        private static void RunDeferredStoryCachePrefill(object state)
        {
            try
            {
                TimeSpan delay;
                lock (RuntimeLock)
                    delay = DeferredStoryCachePrefillDelay;

                if (delay > TimeSpan.Zero)
                    Thread.Sleep(delay);

                if (!Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_USE_LLM)
                    return;

                Func<DynamicQuestSeedSummary> prefillStoryCacheFromWorld;
                Func<DynamicQuestStoryCachePrefillPlanSnapshot> prefillStoryCachePlanFromWorld;
                lock (RuntimeLock)
                {
                    prefillStoryCacheFromWorld = PrefillStoryCacheFromWorldCallback;
                    prefillStoryCachePlanFromWorld = PrefillStoryCachePlanFromWorldCallback;
                }

                DynamicQuestStoryCachePrefillPlanSnapshot plan = prefillStoryCachePlanFromWorld();
                if (plan == null || plan.TotalCandidates <= 0)
                    return;

                DynamicQuestSeedSummary seedSummary = LastSummary ?? new DynamicQuestSeedSummary
                {
                    Enabled = true,
                    DynamicQuestEnabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                    GeneratedAt = DateTime.UtcNow,
                    WorldRevision = Properties.KDAOC_DYNAMIC_QUEST_WORLD_REVISION ?? string.Empty
                };
                seedSummary.StoryCachePrefillCandidates = plan.TotalCandidates;
                string runningMessage = $"story cache deferred prefill running: candidates={plan.TotalCandidates}";
                if (!seedSummary.Messages.Contains(runningMessage))
                    seedSummary.Messages.Add(runningMessage);
                LastSummary = seedSummary;

                DynamicQuestSeedSummary prefillSummary = prefillStoryCacheFromWorld();
                if (prefillSummary == null)
                    return;

                MergePrefillSummary(seedSummary, prefillSummary);
                LastSummary = seedSummary;

                if (Log.IsInfoEnabled)
                    Log.Info($"Dynamic quest deferred story cache prefill completed. prefilled={seedSummary.StoryCachePrefilled} attempted={seedSummary.StoryCachePrefillAttempted} failed={seedSummary.StoryCachePrefillGenerationFailed}");
            }
            catch (Exception ex)
            {
                DynamicQuestSeedSummary seedSummary = LastSummary ?? new DynamicQuestSeedSummary
                {
                    Enabled = true,
                    DynamicQuestEnabled = Properties.KDAOC_DYNAMIC_QUEST_ENABLED,
                    GeneratedAt = DateTime.UtcNow,
                    WorldRevision = Properties.KDAOC_DYNAMIC_QUEST_WORLD_REVISION ?? string.Empty
                };
                string message = $"story cache deferred prefill failed: {ex.Message}";
                if (!seedSummary.Messages.Contains(message))
                    seedSummary.Messages.Add(message);
                LastSummary = seedSummary;
                if (Log.IsWarnEnabled)
                    Log.Warn(message, ex);
            }
            finally
            {
                Interlocked.Exchange(ref DeferredStoryCachePrefillInProgress, 0);
            }
        }

        private static void MergePrefillSummary(DynamicQuestSeedSummary seedSummary, DynamicQuestSeedSummary prefillSummary)
        {
            if (seedSummary == null || prefillSummary == null)
                return;

            seedSummary.StoryCachePrefillCandidates = prefillSummary.StoryCachePrefillCandidates;
            seedSummary.StoryCachePrefilled = prefillSummary.StoryCachePrefilled;
            seedSummary.StoryCachePrefillAttempted = prefillSummary.StoryCachePrefillAttempted;
            seedSummary.StoryCachePrefillAlreadyReady = prefillSummary.StoryCachePrefillAlreadyReady;
            seedSummary.StoryCachePrefillResolveSkipped = prefillSummary.StoryCachePrefillResolveSkipped;
            seedSummary.StoryCachePrefillGenerationFailed = prefillSummary.StoryCachePrefillGenerationFailed;
            seedSummary.StoryCachePrefillQualityRejected = prefillSummary.StoryCachePrefillQualityRejected;
            seedSummary.StoryCachePrefillGenerationErrors = new Dictionary<string, int>(
                prefillSummary.StoryCachePrefillGenerationErrors ?? new Dictionary<string, int>(),
                StringComparer.OrdinalIgnoreCase);

            foreach (string message in prefillSummary.Messages ?? Array.Empty<string>())
            {
                if (!string.IsNullOrWhiteSpace(message) && !seedSummary.Messages.Contains(message))
                    seedSummary.Messages.Add(message);
            }
        }
    }
}
