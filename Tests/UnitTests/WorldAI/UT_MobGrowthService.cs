using System;
using System.Collections.Generic;
using System.Linq;
using DOL.Database;
using DOL.GS.WorldAI;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_MobGrowthService
    {
        [Test]
        public void TickGrowth_PromotesUnhuntedMonsterEvenWithoutPlayerKills()
        {
            FakeMobGrowthRepository growth = new();
            MobGrowthService service = CreateService(growth);
            MobGrowthObservation mob = CreateMob();
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.UnhuntedAfterMinutes = 1;
            options.EliteScore = 10;

            DateTime firstSeen = DateTime.UtcNow;
            service.ObserveTick(mob, firstSeen, options);

            DbMobGrowthState state = service.ObserveTick(mob, firstSeen.AddMinutes(10), options);

            Assert.Multiple(() =>
            {
                Assert.That(state.Stage, Is.EqualTo(MobGrowthStages.Elite));
                Assert.That(state.UnhuntedTicks, Is.EqualTo(1));
                Assert.That(state.GrowthScore, Is.GreaterThanOrEqualTo(options.EliteScore));
                Assert.That(state.GrowthLevel, Is.EqualTo(1));
            });
        }

        [Test]
        public void PlayerKills_AddGrowthButRespectLevelCap()
        {
            FakeMobGrowthRepository growth = new();
            MobGrowthService service = CreateService(growth);
            MobGrowthObservation mob = CreateMob();
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.PlayerKillScore = 100;
            options.ChampionScore = 150;
            options.MaxLevelBonus = 2;

            service.RecordPlayerKill(mob, DateTime.UtcNow, options);
            DbMobGrowthState state = service.RecordPlayerKill(mob, DateTime.UtcNow.AddMinutes(1), options);

            Assert.Multiple(() =>
            {
                Assert.That(state.Stage, Is.EqualTo(MobGrowthStages.Champion));
                Assert.That(state.PlayerKills, Is.EqualTo(2));
                Assert.That(state.GrowthLevel, Is.EqualTo(2));
                Assert.That(state.EffectiveLevel, Is.EqualTo(mob.Level + options.MaxLevelBonus));
            });
        }

        [Test]
        public void CombatGrowth_IsThrottledPerMonster()
        {
            FakeMobGrowthRepository growth = new();
            MobGrowthService service = CreateService(growth);
            MobGrowthObservation mob = CreateMob();
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.CombatScore = 12;
            options.CombatGrowthCooldownSeconds = 30;
            DateTime firstHit = DateTime.UtcNow;

            service.RecordCombat(mob, firstHit, options);
            service.RecordCombat(mob, firstHit.AddSeconds(10), options);
            DbMobGrowthState state = service.RecordCombat(mob, firstHit.AddSeconds(31), options);

            Assert.Multiple(() =>
            {
                Assert.That(state.CombatCount, Is.EqualTo(2));
                Assert.That(state.GrowthScore, Is.EqualTo(options.CombatScore * 2));
                Assert.That(state.LastCombatGrowthAt, Is.EqualTo(firstHit.AddSeconds(31)));
                Assert.That(growth.SaveCalls, Is.EqualTo(2));
            });
        }

        [Test]
        public void BossPromotion_RecordsWorldEventOnlyOnce()
        {
            FakeMobGrowthRepository growth = new();
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = new(events, jobs, results, new LlmResultValidationService(), new FakeLlmResultGenerator());
            WorldEventService worldEvents = new(events, queue);
            MobGrowthService service = new(growth, worldEvents);
            MobGrowthObservation mob = CreateMob();
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.PlayerKillScore = 500;
            options.BossScore = 500;

            service.RecordPlayerKill(mob, DateTime.UtcNow, options);
            service.RecordPlayerKill(mob, DateTime.UtcNow.AddMinutes(1), options);

            Assert.Multiple(() =>
            {
                Assert.That(growth.Rows.Values.Single().Stage, Is.EqualTo(MobGrowthStages.Boss));
                Assert.That(events.Rows.Values.Count(row => row.EventType == WorldAiEventTypes.MobAscended), Is.EqualTo(1));
                Assert.That(jobs.Rows.Values, Has.Count.EqualTo(2));
            });
        }

        [Test]
        public void BossPromotion_RespectsActiveBossLimit()
        {
            FakeMobGrowthRepository growth = new();
            growth.Add(new DbMobGrowthState
            {
                MobId = "existing-boss",
                BaseName = "기존 우두머리",
                CurrentName = "기존 우두머리",
                Stage = MobGrowthStages.Boss,
                GrowthScore = 1000,
                IsActive = true
            });
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = new(events, jobs, results, new LlmResultValidationService(), new FakeLlmResultGenerator());
            WorldEventService worldEvents = new(events, queue);
            MobGrowthService service = new(growth, worldEvents);
            MobGrowthObservation mob = CreateMob();
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.PlayerKillScore = 500;
            options.BossScore = 500;
            options.ChampionScore = 100;
            options.MaxActiveBosses = 1;

            DbMobGrowthState state = service.RecordPlayerKill(mob, DateTime.UtcNow, options);

            Assert.Multiple(() =>
            {
                Assert.That(state.Stage, Is.EqualTo(MobGrowthStages.Champion));
                Assert.That(state.GrowthScore, Is.GreaterThanOrEqualTo(options.BossScore));
                Assert.That(events.Rows.Values.Count(row => row.EventType == WorldAiEventTypes.MobAscended), Is.Zero);
                Assert.That(jobs.Rows.Values, Is.Empty);
            });
        }

        private static MobGrowthService CreateService(FakeMobGrowthRepository growth)
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = new(events, jobs, results, new LlmResultValidationService(), new FakeLlmResultGenerator());
            WorldEventService worldEvents = new(events, queue);
            return new MobGrowthService(growth, worldEvents);
        }

        private static MobGrowthObservation CreateMob()
        {
            return new MobGrowthObservation
            {
                MobId = "mob-growth-test-1",
                Name = "검은 숲 늑대",
                Region = "북부 숲",
                RegionId = 1,
                X = 1000,
                Y = 2000,
                Z = 3000,
                Heading = 100,
                Level = 10,
                IsAlive = true,
                IsEligible = true
            };
        }
    }

    internal sealed class FakeMobGrowthRepository : IMobGrowthRepository
    {
        public readonly Dictionary<string, DbMobGrowthState> Rows = new();
        public int SaveCalls { get; private set; }

        public bool Add(DbMobGrowthState row)
        {
            Rows[row.MobId] = row;
            return true;
        }

        public DbMobGrowthState Find(string mobId)
        {
            Rows.TryGetValue(mobId, out DbMobGrowthState row);
            return row;
        }

        public IList<DbMobGrowthState> GetTopActive(int limit)
        {
            return Rows.Values
                .Where(row => row.IsActive)
                .OrderByDescending(row => row.GrowthScore)
                .Take(limit)
                .ToList();
        }

        public int CountActiveBosses()
        {
            return Rows.Values.Count(row => row.IsActive && row.Stage == MobGrowthStages.Boss);
        }

        public bool Save(DbMobGrowthState row)
        {
            SaveCalls++;
            Rows[row.MobId] = row;
            return true;
        }

        public bool Delete(DbMobGrowthState row)
        {
            return Rows.Remove(row.MobId);
        }
    }
}
