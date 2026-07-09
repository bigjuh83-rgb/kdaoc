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

        [Test]
        public void BossPromotion_RespectsActiveBossLimitPerRegion()
        {
            FakeMobGrowthRepository growth = new();
            growth.Add(new DbMobGrowthState
            {
                MobId = "existing-region-boss",
                BaseName = "기존 지역 우두머리",
                CurrentName = "기존 지역 우두머리",
                RegionId = 1,
                Stage = MobGrowthStages.Boss,
                GrowthScore = 1000,
                IsActive = true
            });
            MobGrowthService service = CreateService(growth);
            MobGrowthObservation mob = CreateMob();
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.PlayerKillScore = 500;
            options.BossScore = 500;
            options.ChampionScore = 100;
            options.MaxActiveBosses = 5;
            options.MaxActiveBossesPerRegion = 1;

            DbMobGrowthState state = service.RecordPlayerKill(mob, DateTime.UtcNow, options);

            Assert.That(state.Stage, Is.EqualTo(MobGrowthStages.Champion));
        }

        [Test]
        public void LowLevelSafety_CapsGrowthStage()
        {
            FakeMobGrowthRepository growth = new();
            MobGrowthService service = CreateService(growth);
            MobGrowthObservation mob = CreateMob();
            mob.Level = 8;
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.PlayerKillScore = 1000;
            options.LowLevelMaxBaseLevel = 15;
            options.LowLevelMaxStage = MobGrowthStages.Elite;

            DbMobGrowthState state = service.RecordPlayerKill(mob, DateTime.UtcNow, options);

            Assert.Multiple(() =>
            {
                Assert.That(state.Stage, Is.EqualTo(MobGrowthStages.Elite));
                Assert.That(state.GrowthScore, Is.GreaterThanOrEqualTo(options.BossScore));
            });
        }

        [Test]
        public void SafetyRules_ExcludeProtectedLevelRegionAndName()
        {
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.MinimumEligibleLevel = 5;
            options.ProtectedRegions = "27;250";
            options.ProtectedNameTokens = "quest;trainer;훈련";

            Assert.Multiple(() =>
            {
                MobGrowthObservation low = CreateMob();
                low.Level = 4;
                Assert.That(MobGrowthService.IsProcessableForTest(low, options), Is.False);

                MobGrowthObservation protectedRegion = CreateMob();
                protectedRegion.RegionId = 27;
                Assert.That(MobGrowthService.IsProcessableForTest(protectedRegion, options), Is.False);

                MobGrowthObservation protectedName = CreateMob();
                protectedName.Name = "Quest Trainer";
                Assert.That(MobGrowthService.IsProcessableForTest(protectedName, options), Is.False);
            });
        }

        [Test]
        public void Summary_GroupsActiveMobsByStageAndRegion()
        {
            FakeMobGrowthRepository growth = new();
            growth.Add(new DbMobGrowthState
            {
                MobId = "elite-1",
                CurrentName = "정예 늑대",
                Region = "Salisbury Plains",
                RegionId = 1,
                Stage = MobGrowthStages.Elite,
                BaseLevel = 10,
                EffectiveLevel = 11,
                GrowthScore = 75,
                SurvivalTicks = 4,
                CombatCount = 2,
                IsActive = true
            });
            growth.Add(new DbMobGrowthState
            {
                MobId = "boss-1",
                CurrentName = "곰 우두머리",
                Region = "Camelot Hills",
                RegionId = 0,
                Stage = MobGrowthStages.Boss,
                BaseLevel = 12,
                EffectiveLevel = 17,
                GrowthScore = 500,
                PlayerKills = 1,
                IsActive = true
            });
            growth.Add(new DbMobGrowthState
            {
                MobId = "dead-1",
                CurrentName = "죽은 뱀",
                Region = "Salisbury Plains",
                RegionId = 1,
                Stage = MobGrowthStages.Champion,
                GrowthScore = 300,
                IsActive = false
            });
            MobGrowthService service = CreateService(growth);

            MobGrowthSummary summary = service.GetSummary(5);

            Assert.Multiple(() =>
            {
                Assert.That(summary.ActiveCount, Is.EqualTo(2));
                Assert.That(summary.ActiveBosses, Is.EqualTo(1));
                Assert.That(summary.Stages.Single(stage => stage.Stage == MobGrowthStages.Elite).Count, Is.EqualTo(1));
                Assert.That(summary.Stages.Single(stage => stage.Stage == MobGrowthStages.Boss).Count, Is.EqualTo(1));
                Assert.That(summary.Regions.Single(region => region.RegionId == 0).Bosses, Is.EqualTo(1));
                Assert.That(summary.Top.First().MobId, Is.EqualTo("boss-1"));
            });
        }

        [Test]
        public void Summary_WithRegionFilterReturnsTopMobsFromRequestedRegion()
        {
            FakeMobGrowthRepository growth = new();
            growth.Add(new DbMobGrowthState
            {
                MobId = "alb-high-1",
                CurrentName = "알비온 강한 늑대",
                Region = "Camelot Hills",
                RegionId = 1,
                Stage = MobGrowthStages.Champion,
                GrowthScore = 900,
                IsActive = true
            });
            growth.Add(new DbMobGrowthState
            {
                MobId = "mid-low-1",
                CurrentName = "미드가르드 약한 늑대",
                Region = "Mularn",
                RegionId = 100,
                Stage = MobGrowthStages.Elite,
                GrowthScore = 100,
                IsActive = true
            });
            MobGrowthService service = CreateService(growth);

            MobGrowthSummary summary = service.GetSummary(5, 100);

            Assert.Multiple(() =>
            {
                Assert.That(summary.ActiveCount, Is.EqualTo(2));
                Assert.That(summary.Regions.Select(region => region.RegionId), Does.Contain((ushort)100));
                Assert.That(summary.Top.Select(mob => mob.MobId), Is.EqualTo(new[] { "mid-low-1" }));
            });
        }

        [Test]
        public void FrequentDeathsWithinConfiguredWindow_QueuesMutantSpawn()
        {
            FakeMobGrowthRepository growth = new();
            MobGrowthService service = CreateService(growth, 10);
            MobGrowthObservation mob = CreateMob();
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.MutationEnabled = true;
            options.MutationDeathWindowMinutes = 10;
            options.MutationDeathThreshold = 5;
            options.MutationChanceStepPercent = 10;
            DateTime firstDeath = DateTime.UtcNow;

            DbMobGrowthState state = null;

            for (int i = 0; i < 5; i++)
                state = service.RecordDeath(mob, firstDeath.AddMinutes(i), options);

            Assert.Multiple(() =>
            {
                Assert.That(state, Is.Not.Null);
                Assert.That(state.IsActive, Is.False);
                Assert.That(state.RecentDeathCount, Is.EqualTo(5));
                Assert.That(state.MutationPending, Is.True);
                Assert.That(state.IsMutant, Is.False);
                Assert.That(state.LastMutationChancePercent, Is.EqualTo(10));
                Assert.That(state.MutationCount, Is.EqualTo(1));
            });
        }

        [Test]
        public void FrequentDeathMutationChance_IncreasesAfterThreshold()
        {
            FakeMobGrowthRepository growth = new();
            MobGrowthService service = CreateService(growth, 99, 15);
            MobGrowthObservation mob = CreateMob();
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.MutationEnabled = true;
            options.MutationDeathWindowMinutes = 10;
            options.MutationDeathThreshold = 5;
            options.MutationChanceStepPercent = 10;
            DateTime firstDeath = DateTime.UtcNow;

            for (int i = 0; i < 5; i++)
                service.RecordDeath(mob, firstDeath.AddMinutes(i), options);

            DbMobGrowthState state = service.RecordDeath(mob, firstDeath.AddMinutes(5), options);

            Assert.Multiple(() =>
            {
                Assert.That(state.RecentDeathCount, Is.EqualTo(6));
                Assert.That(state.MutationPending, Is.True);
                Assert.That(state.LastMutationChancePercent, Is.EqualTo(20));
                Assert.That(state.MutationCount, Is.EqualTo(1));
            });
        }

        [Test]
        public void PendingMutation_ActivatesOnNextAliveObservation()
        {
            FakeMobGrowthRepository growth = new();
            FakeWorldEventRepository events = new();
            MobGrowthService service = CreateService(growth, events, 1);
            MobGrowthObservation mob = CreateMob();
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.MutationEnabled = true;
            options.MutationDeathWindowMinutes = 10;
            options.MutationDeathThreshold = 5;
            options.MutationChanceStepPercent = 10;
            options.MutationSpellPool = "11890";
            options.MutationStylePool = "103|2";
            options.MutationAbilityPool = "Evade|1";
            DateTime firstDeath = DateTime.UtcNow;

            for (int i = 0; i < 5; i++)
                service.RecordDeath(mob, firstDeath.AddMinutes(i), options);

            DbMobGrowthState state = service.ObserveTick(mob, firstDeath.AddMinutes(6), options);

            Assert.Multiple(() =>
            {
                Assert.That(state.IsMutant, Is.True);
                Assert.That(state.MutationPending, Is.False);
                Assert.That(state.CurrentName, Is.EqualTo("돌연변이 검은 숲 늑대"));
                Assert.That(state.GrowthLevel, Is.GreaterThanOrEqualTo(1));
                Assert.That(state.EffectiveSize, Is.GreaterThan(state.BaseSize));
                Assert.That(state.BonusSpellIds, Is.EqualTo("11890"));
                Assert.That(state.BonusStyleIds, Is.EqualTo("103|2"));
                Assert.That(state.BonusAbilityKeys, Is.EqualTo("Evade|1"));
                Assert.That(events.Rows.Values.Count(row => row.EventType == WorldAiEventTypes.MobMutated), Is.EqualTo(1));
            });
        }

        [Test]
        public void DecayStaleActiveMobs_ReducesGrowthAndDemotes()
        {
            FakeMobGrowthRepository growth = new();
            growth.Add(new DbMobGrowthState
            {
                MobId = "stale-boss",
                BaseName = "검은 숲 늑대",
                CurrentName = "우두머리 검은 숲 늑대",
                Region = "북부 숲",
                RegionId = 1,
                BaseLevel = 10,
                EffectiveLevel = 15,
                BaseSize = 50,
                EffectiveSize = 72,
                Stage = MobGrowthStages.Boss,
                GrowthScore = 420,
                LastSeenAt = DateTime.UtcNow.AddHours(-3),
                IsActive = true
            });
            MobGrowthService service = CreateService(growth);
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.DecayEnabled = true;
            options.DecayAfterMinutes = 60;
            options.DecayScore = 300;

            MobGrowthDecayResult result = service.DecayStaleActive(DateTime.UtcNow, options, 100);
            DbMobGrowthState state = growth.Find("stale-boss");

            Assert.Multiple(() =>
            {
                Assert.That(result.Decayed, Is.EqualTo(1));
                Assert.That(state.Stage, Is.EqualTo(MobGrowthStages.Elite));
                Assert.That(state.GrowthScore, Is.EqualTo(120));
                Assert.That(state.CurrentName, Is.EqualTo("노련한 검은 숲 늑대"));
            });
        }

        [Test]
        public void DecayStaleActiveMobs_ClearsVeryOldInactiveRows()
        {
            FakeMobGrowthRepository growth = new();
            growth.Add(new DbMobGrowthState
            {
                MobId = "old-inactive",
                BaseName = "오래된 몹",
                CurrentName = "오래된 몹",
                Stage = MobGrowthStages.Champion,
                GrowthScore = 300,
                LastSeenAt = DateTime.UtcNow.AddDays(-10),
                IsActive = false
            });
            MobGrowthService service = CreateService(growth);
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.DecayEnabled = true;
            options.ResetInactiveAfterMinutes = 60 * 24;

            MobGrowthDecayResult result = service.DecayStaleActive(DateTime.UtcNow, options, 100);

            Assert.Multiple(() =>
            {
                Assert.That(result.ResetInactive, Is.EqualTo(1));
                Assert.That(growth.Find("old-inactive"), Is.Null);
            });
        }

        [Test]
        public void ValidateBonusPools_FlagsMalformedAndUnknownEntries()
        {
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.BossSpellPool = "0;abc;11840";
            options.BossStylePool = "bad;100|x;256|44";
            options.BossAbilityPool = "; ;";

            MobGrowthBonusPoolValidation validation = MobGrowthService.ValidateBonusPools(options);

            Assert.Multiple(() =>
            {
                Assert.That(validation.ValidEntries, Is.EqualTo(2));
                Assert.That(validation.Errors, Has.Count.GreaterThanOrEqualTo(4));
                Assert.That(validation.Errors.Any(error => error.Contains("BossSpellPool", StringComparison.OrdinalIgnoreCase)), Is.True);
                Assert.That(validation.Errors.Any(error => error.Contains("BossStylePool", StringComparison.OrdinalIgnoreCase)), Is.True);
                Assert.That(validation.Errors.Any(error => error.Contains("BossAbilityPool", StringComparison.OrdinalIgnoreCase)), Is.True);
            });
        }

        [Test]
        public void EliteAndHigherStages_GainIncreasingSizeLevelAndTraits()
        {
            FakeMobGrowthRepository growth = new();
            MobGrowthService service = CreateService(growth, 1, 1, 1, 1, 1, 1, 1, 1, 1);
            MobGrowthObservation mob = CreateMob();
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.PlayerKillScore = 100;
            options.EliteScore = 100;
            options.ChampionScore = 200;
            options.BossScore = 300;
            options.MaxLevelBonus = 6;
            options.MaxActiveBosses = 5;
            options.EliteSpellPool = "11874";
            options.ChampionSpellPool = "11893";
            options.BossSpellPool = "11955";
            options.EliteStylePool = "103|2";
            options.ChampionStylePool = "108|2";
            options.BossStylePool = "256|44";
            options.EliteAbilityPool = "Evade|1";
            options.ChampionAbilityPool = "Advanced Evade|1";
            options.BossAbilityPool = "CCImmunity|1";
            DateTime firstKill = DateTime.UtcNow;

            DbMobGrowthState elite = service.RecordPlayerKill(mob, firstKill, options);
            string eliteStage = elite.Stage;
            int eliteLevel = elite.GrowthLevel;
            int eliteSize = elite.EffectiveSize;
            string eliteAbilities = elite.BonusAbilityKeys;

            DbMobGrowthState champion = service.RecordPlayerKill(mob, firstKill.AddMinutes(1), options);
            string championStage = champion.Stage;
            int championLevel = champion.GrowthLevel;
            int championSize = champion.EffectiveSize;
            string championAbilities = champion.BonusAbilityKeys;

            DbMobGrowthState boss = service.RecordPlayerKill(mob, firstKill.AddMinutes(2), options);

            Assert.Multiple(() =>
            {
                Assert.That(eliteStage, Is.EqualTo(MobGrowthStages.Elite));
                Assert.That(championStage, Is.EqualTo(MobGrowthStages.Champion));
                Assert.That(boss.Stage, Is.EqualTo(MobGrowthStages.Boss));
                Assert.That(championLevel, Is.GreaterThan(eliteLevel));
                Assert.That(boss.GrowthLevel, Is.GreaterThan(championLevel));
                Assert.That(championSize, Is.GreaterThan(eliteSize));
                Assert.That(boss.EffectiveSize, Is.GreaterThan(championSize));
                Assert.That(eliteAbilities, Does.Contain("Evade|1"));
                Assert.That(championAbilities, Does.Contain("Advanced Evade|1"));
                Assert.That(boss.BonusAbilityKeys, Does.Contain("CCImmunity|1"));
                Assert.That(boss.BonusSpellIds, Does.Contain("11955"));
                Assert.That(boss.BonusStyleIds, Does.Contain("256|44"));
            });
        }

        [Test]
        public void MutantBoss_ComposesMutationAndBossIdentity()
        {
            FakeMobGrowthRepository growth = new();
            MobGrowthService service = CreateService(growth, 1, 1, 1, 1, 1, 1);
            MobGrowthObservation mob = CreateMob();
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.MutationEnabled = true;
            options.MutationDeathWindowMinutes = 10;
            options.MutationDeathThreshold = 5;
            options.MutationChanceStepPercent = 10;
            options.PlayerKillScore = 500;
            options.BossScore = 500;
            options.MutationSpellPool = "11890";
            options.BossSpellPool = "11955";
            options.MutationStylePool = "103|2";
            options.BossStylePool = "256|44";
            options.MutationAbilityPool = "Evade|1";
            options.BossAbilityPool = "CCImmunity|1";
            DateTime firstDeath = DateTime.UtcNow;

            for (int i = 0; i < 5; i++)
                service.RecordDeath(mob, firstDeath.AddMinutes(i), options);

            DbMobGrowthState state = service.RecordPlayerKill(mob, firstDeath.AddMinutes(6), options);

            Assert.Multiple(() =>
            {
                Assert.That(state.IsMutant, Is.True);
                Assert.That(state.Stage, Is.EqualTo(MobGrowthStages.Boss));
                Assert.That(state.CurrentName, Is.EqualTo("돌연변이 우두머리 검은 숲 늑대"));
                Assert.That(state.BonusSpellIds, Does.Contain("11890"));
                Assert.That(state.BonusSpellIds, Does.Contain("11955"));
                Assert.That(state.BonusAbilityKeys, Does.Contain("Evade|1"));
                Assert.That(state.BonusAbilityKeys, Does.Contain("CCImmunity|1"));
            });
        }

        [Test]
        public void ForceStage_RefreshesIdentityAndBonusLoadout()
        {
            FakeMobGrowthRepository growth = new();
            MobGrowthService service = CreateService(growth, 1, 1, 1);
            MobGrowthObservation mob = CreateMob();
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.BossSpellPool = "11955";
            options.BossStylePool = "256|44";
            options.BossAbilityPool = "CCImmunity|1";
            service.ObserveTick(mob, DateTime.UtcNow, options);

            DbMobGrowthState state = service.ForceStage(mob.MobId, MobGrowthStages.Boss, options);

            Assert.Multiple(() =>
            {
                Assert.That(state, Is.Not.Null);
                Assert.That(state.Stage, Is.EqualTo(MobGrowthStages.Boss));
                Assert.That(state.CurrentName, Is.EqualTo("우두머리 검은 숲 늑대"));
                Assert.That(state.GrowthLevel, Is.EqualTo(options.MaxLevelBonus));
                Assert.That(state.EffectiveSize, Is.GreaterThan(state.BaseSize));
                Assert.That(state.BonusSpellIds, Does.Contain("11955"));
                Assert.That(state.BonusStyleIds, Does.Contain("256|44"));
                Assert.That(state.BonusAbilityKeys, Does.Contain("CCImmunity|1"));
            });
        }

        [Test]
        public void ForceStage_ToNormalClearsGrowthScore()
        {
            FakeMobGrowthRepository growth = new();
            MobGrowthService service = CreateService(growth, 1);
            MobGrowthObservation mob = CreateMob();
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            service.ObserveTick(mob, DateTime.UtcNow, options);
            service.ForceStage(mob.MobId, MobGrowthStages.Boss, options);

            DbMobGrowthState state = service.ForceStage(mob.MobId, MobGrowthStages.Normal, options);

            Assert.Multiple(() =>
            {
                Assert.That(state.Stage, Is.EqualTo(MobGrowthStages.Normal));
                Assert.That(state.GrowthScore, Is.EqualTo(0));
                Assert.That(state.CurrentName, Is.EqualTo("검은 숲 늑대"));
                Assert.That(state.GrowthLevel, Is.EqualTo(0));
            });
        }

        [Test]
        public void ForceMutationAndRecentDeaths_UpdateOperationalState()
        {
            FakeMobGrowthRepository growth = new();
            MobGrowthService service = CreateService(growth, 1);
            MobGrowthObservation mob = CreateMob();
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            options.MutationSpellPool = "11890";
            options.MutationStylePool = "103|2";
            options.MutationAbilityPool = "Evade|1";
            service.ObserveTick(mob, DateTime.UtcNow, options);

            DbMobGrowthState deathState = service.SetRecentDeathCount(mob.MobId, 7, DateTime.UtcNow);
            DbMobGrowthState mutant = service.ForceMutation(mob.MobId, true, options);

            Assert.Multiple(() =>
            {
                Assert.That(deathState.RecentDeathCount, Is.EqualTo(7));
                Assert.That(mutant.IsMutant, Is.True);
                Assert.That(mutant.MutationPending, Is.False);
                Assert.That(mutant.CurrentName, Is.EqualTo("돌연변이 검은 숲 늑대"));
                Assert.That(mutant.BonusSpellIds, Is.EqualTo("11890"));
                Assert.That(mutant.BonusStyleIds, Is.EqualTo("103|2"));
                Assert.That(mutant.BonusAbilityKeys, Is.EqualTo("Evade|1"));
            });
        }

        [Test]
        public void QuestKillSignals_IgnoreNormalMonster()
        {
            MobGrowthObservation mob = CreateMob();
            DbMobGrowthState state = new()
            {
                MobId = mob.MobId,
                Stage = MobGrowthStages.Normal,
                IsMutant = false
            };

            IList<string> signals = MobGrowthService.BuildQuestKillSignalsForTest(state, mob);

            Assert.That(signals, Is.Empty);
        }

        [Test]
        public void QuestKillSignals_DescribeBossKillSpecificToGeneric()
        {
            MobGrowthObservation mob = CreateMob();
            DbMobGrowthState state = new()
            {
                MobId = mob.MobId,
                Stage = MobGrowthStages.Boss,
                IsMutant = false
            };

            IList<string> signals = MobGrowthService.BuildQuestKillSignalsForTest(state, mob);

            Assert.That(signals, Is.EqualTo(new[]
            {
                "mob-growth:killed:mob:mob-growth-test-1",
                "mob-growth:killed:boss",
                "mob-growth:killed:stage:boss",
                "mob-growth:killed:region:1",
                "mob-growth:killed"
            }));
        }

        [Test]
        public void QuestKillSignals_PreserveBossSignalsAfterDeathRecord()
        {
            FakeMobGrowthRepository growth = new();
            MobGrowthService service = CreateService(growth);
            MobGrowthObservation mob = CreateMob();
            mob.Name = "우두머리 검은 숲 늑대";
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            growth.Add(new DbMobGrowthState
            {
                MobId = mob.MobId,
                BaseName = "검은 숲 늑대",
                CurrentName = mob.Name,
                Region = mob.Region,
                RegionId = mob.RegionId,
                Stage = MobGrowthStages.Boss,
                GrowthScore = options.BossScore,
                IsActive = true
            });

            DbMobGrowthState killed = service.RecordDeath(mob, DateTime.UtcNow, options);
            IList<string> signals = MobGrowthService.BuildQuestKillSignalsForTest(killed, mob);

            Assert.Multiple(() =>
            {
                Assert.That(killed.IsActive, Is.False);
                Assert.That(signals, Does.Contain("mob-growth:killed:boss"));
                Assert.That(signals, Does.Contain("mob-growth:killed:stage:boss"));
                Assert.That(signals, Does.Contain("mob-growth:killed:region:1"));
                Assert.That(signals, Does.Contain("mob-growth:killed"));
            });
        }

        [Test]
        public void QuestKillSignals_PreserveMutantSignalFromKilledNpcName()
        {
            MobGrowthObservation mob = CreateMob();
            mob.Name = "돌연변이 검은 숲 늑대";
            DbMobGrowthState state = new()
            {
                MobId = mob.MobId,
                Stage = MobGrowthStages.Normal,
                IsMutant = false
            };

            IList<string> signals = MobGrowthService.BuildQuestKillSignalsForTest(state, mob);

            Assert.Multiple(() =>
            {
                Assert.That(signals, Does.Contain("mob-growth:killed:mutant"));
                Assert.That(signals, Does.Contain("mob-growth:killed"));
                Assert.That(signals, Does.Not.Contain("mob-growth:killed:boss"));
            });
        }

        [Test]
        public void QuestKillSignals_PreserveMutantSignalAfterDeathRecord()
        {
            FakeMobGrowthRepository growth = new();
            MobGrowthService service = CreateService(growth);
            MobGrowthObservation mob = CreateMob();
            mob.Name = "돌연변이 검은 숲 늑대";
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            growth.Add(new DbMobGrowthState
            {
                MobId = mob.MobId,
                BaseName = "검은 숲 늑대",
                CurrentName = mob.Name,
                Region = mob.Region,
                RegionId = mob.RegionId,
                Stage = MobGrowthStages.Normal,
                IsMutant = true,
                IsActive = true
            });

            DbMobGrowthState killed = service.RecordDeath(mob, DateTime.UtcNow, options);
            IList<string> signals = MobGrowthService.BuildQuestKillSignalsForTest(killed, mob);

            Assert.Multiple(() =>
            {
                Assert.That(killed.IsMutant, Is.False);
                Assert.That(signals, Does.Contain("mob-growth:killed:mutant"));
                Assert.That(signals, Does.Contain("mob-growth:killed:region:1"));
                Assert.That(signals, Does.Contain("mob-growth:killed"));
                Assert.That(signals, Does.Not.Contain("mob-growth:killed:boss"));
            });
        }

        private static MobGrowthService CreateService(FakeMobGrowthRepository growth)
        {
            return CreateService(growth, Array.Empty<int>());
        }

        private static MobGrowthService CreateService(FakeMobGrowthRepository growth, params int[] rolls)
        {
            return CreateService(growth, new FakeWorldEventRepository(), rolls);
        }

        private static MobGrowthService CreateService(FakeMobGrowthRepository growth, FakeWorldEventRepository events, params int[] rolls)
        {
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = new(events, jobs, results, new LlmResultValidationService(), new FakeLlmResultGenerator());
            WorldEventService worldEvents = new(events, queue);
            return new MobGrowthService(growth, worldEvents, new SequenceMobGrowthRandom(rolls));
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
                Level = 20,
                Size = 50,
                IsAlive = true,
                IsEligible = true
            };
        }
    }

    internal sealed class SequenceMobGrowthRandom : IMobGrowthRandom
    {
        private readonly Queue<int> m_values;

        public SequenceMobGrowthRandom(IEnumerable<int> values)
        {
            m_values = new Queue<int>(values ?? Array.Empty<int>());
        }

        public int NextInclusive(int minValue, int maxValue)
        {
            if (m_values.Count == 0)
                return minValue;

            return Math.Clamp(m_values.Dequeue(), minValue, maxValue);
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

        public IList<DbMobGrowthState> GetActive(int limit)
        {
            return Rows.Values
                .Where(row => row.IsActive)
                .OrderByDescending(row => row.GrowthScore)
                .Take(limit)
                .ToList();
        }

        public IList<DbMobGrowthState> GetAll(int limit)
        {
            return Rows.Values
                .OrderByDescending(row => row.UpdatedAt)
                .Take(limit)
                .ToList();
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

        public int CountActiveBossesInRegion(ushort regionId)
        {
            return Rows.Values.Count(row => row.IsActive && row.RegionId == regionId && row.Stage == MobGrowthStages.Boss);
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
