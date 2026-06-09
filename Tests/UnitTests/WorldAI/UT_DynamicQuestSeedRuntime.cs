using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;
using DOL.GS.ServerProperties;
using DOL.GS.WorldAI;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_DynamicQuestSeedRuntime
    {
        [SetUp]
        public void SetUp()
        {
            DynamicQuestSeedRuntime.ResetForTest();
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_USE_LLM = false;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_TICK_MINUTES = 30;
        }

        [TearDown]
        public void TearDown()
        {
            DynamicQuestSeedRuntime.ResetForTest();
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_ENABLED = false;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_USE_LLM = false;
        }

        [Test]
        public void RestartTimer_ReturnsBeforeInitialSeedCompletes()
        {
            using ManualResetEventSlim started = new(false);
            using ManualResetEventSlim release = new(false);
            using ManualResetEventSlim completed = new(false);
            DynamicQuestSeedRuntime.SetInitialSeedDelayForTest(TimeSpan.Zero);
            DynamicQuestSeedRuntime.SetSeedFromWorldForTest(() =>
            {
                started.Set();
                release.Wait(TimeSpan.FromSeconds(2));
                completed.Set();
                return new DynamicQuestSeedSummary { Enabled = true };
            });

            Stopwatch stopwatch = Stopwatch.StartNew();
            DynamicQuestSeedRuntime.RestartTimer();
            stopwatch.Stop();

            try
            {
                Assert.Multiple(() =>
                {
                    Assert.That(stopwatch.ElapsedMilliseconds, Is.LessThan(500));
                    Assert.That(started.Wait(TimeSpan.FromSeconds(1)), Is.True);
                });
            }
            finally
            {
                release.Set();
            }

            Assert.That(completed.Wait(TimeSpan.FromSeconds(1)), Is.True);
        }

        [Test]
        public void Seed_StatusShowsStoryCachePrefillRunningBeforeSlowGenerationCompletes()
        {
            using ManualResetEventSlim prefillStarted = new(false);
            using ManualResetEventSlim releasePrefill = new(false);
            DynamicQuestSeedRuntime.SetInitialSeedDelayForTest(TimeSpan.Zero);
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_USE_LLM = true;
            DynamicQuestSeedRuntime.SetSeedFromWorldForTest(() => new DynamicQuestSeedSummary
            {
                Enabled = true,
                DynamicQuestEnabled = true,
                Created = 3
            });
            DynamicQuestSeedRuntime.SetPrefillStoryCachePlanFromWorldForTest(() => new DynamicQuestStoryCachePrefillPlanSnapshot
            {
                TotalCandidates = 63
            });
            DynamicQuestSeedRuntime.SetPrefillStoryCacheFromWorldForTest(() =>
            {
                prefillStarted.Set();
                releasePrefill.Wait(TimeSpan.FromSeconds(2));
                return new DynamicQuestSeedSummary
                {
                    StoryCachePrefillCandidates = 63,
                    StoryCachePrefilled = 5,
                    StoryCachePrefillAttempted = 7,
                    StoryCachePrefillGenerationFailed = 1,
                    StoryCachePrefillQualityRejected = 1,
                    StoryCachePrefillGenerationErrors = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase)
                    {
                        ["gemini:http_429"] = 1
                    }
                };
            });

            DynamicQuestSeedRuntime.RestartTimer();

            try
            {
                Assert.That(prefillStarted.Wait(TimeSpan.FromSeconds(1)), Is.True);
                DynamicQuestSeedSummary running = DynamicQuestSeedRuntime.LastSummary;
                Assert.Multiple(() =>
                {
                    Assert.That(running.StoryCachePrefillCandidates, Is.EqualTo(63));
                    Assert.That(running.Messages, Does.Contain("story cache prefill running: candidates=63"));
                });
            }
            finally
            {
                releasePrefill.Set();
            }

            Thread.Sleep(100);
            DynamicQuestSeedSummary finished = DynamicQuestSeedRuntime.LastSummary;
            Assert.Multiple(() =>
            {
                Assert.That(finished.StoryCachePrefilled, Is.EqualTo(5));
                Assert.That(finished.StoryCachePrefillAttempted, Is.EqualTo(7));
                Assert.That(finished.StoryCachePrefillGenerationFailed, Is.EqualTo(1));
                Assert.That(finished.StoryCachePrefillQualityRejected, Is.EqualTo(1));
                Assert.That(finished.StoryCachePrefillGenerationErrors["gemini:http_429"], Is.EqualTo(1));
            });
        }
    }
}
