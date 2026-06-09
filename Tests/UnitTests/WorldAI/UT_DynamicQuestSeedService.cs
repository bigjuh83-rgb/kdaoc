using System;
using System.Collections.Generic;
using System.Linq;
using DOL.Database;
using DOL.GS.ServerProperties;
using DOL.GS.WorldAI;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_DynamicQuestSeedService
    {
        [SetUp]
        public void SetUp()
        {
            Properties.KDAOC_DYNAMIC_QUEST_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_MAX_ACTIVE_PER_PLAYER = 1;
            Properties.KDAOC_DYNAMIC_QUEST_MAX_ACTIVE_PER_NPC = 1;
            Properties.KDAOC_DYNAMIC_QUEST_MAX_KILL_COUNT = 20;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_ENABLED = false;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_USE_LLM = false;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_MAX_QUESTS = 3;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_DEFINITIONS = DynamicQuestSeedOptions.DefaultDeterministicDefinitions;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_MAX_TEMPLATES = 500;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PRUNE_COUNT = 50;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE = 5;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = false;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_MAX_CANDIDATES = 60;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_OFFER_ENABLED = false;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_OFFER_MIN_SLOTS = 3;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_GEMINI_RESET_DELAY_MINUTES = 10;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_GEMINI_RESET_WINDOW_MINUTES = 360;
            DynamicQuestSeedService.ResetStoryCacheCleanupForTest();
            DynamicQuestSeedService.SetClockForTest(() => new DateTime(2026, 6, 3, 7, 20, 0, DateTimeKind.Utc));
            DynamicQuestRuntimeService.Instance.ClearAll();
        }

        [TearDown]
        public void TearDown()
        {
            DynamicQuestRuntimeService.Instance.ClearAll();
            DynamicQuestSeedService.SetClockForTest(null);
            Properties.KDAOC_DYNAMIC_QUEST_ENABLED = false;
        }

        [Test]
        public void Seed_DeterministicDefinitionCreatesOneRuntimeQuest()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedNpc target = CreateNpc("black wolf pup", "target-npc-1", 1, x: 502100, y: 500800, z: 2954);
            DynamicQuestSeedNpc target2 = CreateNpc("black wolf pup", "target-npc-2", 1, x: 502300, y: 500900, z: 2954);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|2|1|5");

            DynamicQuestSeedSummary summary = service.Seed(new[] { npc, target, target2 }, options);

            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();
            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Brother Penric"));
                Assert.That(quest.StartRegionId, Is.EqualTo(1));
                Assert.That(quest.TargetName, Is.EqualTo("black wolf pup"));
                Assert.That(quest.TargetCount, Is.EqualTo(2));
                Assert.That(quest.MinLevel, Is.EqualTo(1));
                Assert.That(quest.MaxLevel, Is.EqualTo(5));
                Assert.That(quest.Nodes.Select(node => node.Type), Is.EqualTo(new[]
                {
                    DynamicQuestNodeType.Talk,
                    DynamicQuestNodeType.Explore,
                    DynamicQuestNodeType.Kill,
                    DynamicQuestNodeType.ReturnToNpc,
                    DynamicQuestNodeType.Choice,
                    DynamicQuestNodeType.Complete
                }));
                Assert.That(quest.StartNodeId, Is.EqualTo("talk"));
                DynamicQuestObjective explore = quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Explore).Objective;
                Assert.That(explore.LocationName, Is.EqualTo("black wolf pup 흔적"));
                Assert.That(explore.RegionId, Is.EqualTo(1));
                Assert.That(explore.X, Is.EqualTo(502100));
                Assert.That(explore.Y, Is.EqualTo(500800));
                Assert.That(explore.Z, Is.EqualTo(2954));
                Assert.That(explore.Radius, Is.EqualTo(450));
                DynamicQuestObjective kill = quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Kill).Objective;
                Assert.That(kill.AllowGroupCredit, Is.True);
                Assert.That(quest.Tags, Does.Contain("realm:Albion"));
                Assert.That(quest.Tags, Does.Contain("starter"));
                Assert.That(quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Choice).Objective.Choices.Select(choice => choice.Id),
                    Is.EqualTo(new[] { "safe", "followup" }));
            });
        }

        [Test]
        public void Seed_IsIdempotentForSameNpcAndDefinition()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedNpc target = CreateNpc("black wolf pup", "target-npc-1", 1);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");

            DynamicQuestSeedSummary first = service.Seed(new[] { npc, target }, options);
            DynamicQuestSeedSummary second = service.Seed(new[] { npc, target }, options);

            Assert.Multiple(() =>
            {
                Assert.That(first.Created, Is.EqualTo(1));
                Assert.That(second.Created, Is.EqualTo(0));
                Assert.That(second.Skipped, Is.EqualTo(1));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests(), Has.Count.EqualTo(1));
            });
        }

        [Test]
        public void Seed_RebindsOffersAndCancelsActiveProgressWhenWorldRevisionChanges()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedNpc wolf = CreateNpc("black wolf pup", "target-wolf-1", 1);
            DynamicQuestSeedOptions firstOptions = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            firstOptions.WorldRevision = "world-1";

            DynamicQuestSeedSummary first = service.Seed(new[] { npc, wolf }, firstOptions);
            DynamicQuestDefinition firstQuest = DynamicQuestRuntimeService.Instance.GetQuests().Single();
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                firstQuest.Id,
                firstQuest.StartNodeId,
                new[] { firstQuest.StartNodeId },
                null,
                firstQuest.BindingKey,
                firstQuest.WorldRevision);

            DynamicQuestSeedNpc spider = CreateNpc("forest spiderling", "target-spider-1", 1, x: 502000, y: 500800, z: 2954);
            DynamicQuestSeedOptions secondOptions = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            secondOptions.WorldRevision = "world-2";

            DynamicQuestSeedSummary second = service.Seed(new[] { npc, spider }, secondOptions);
            DynamicQuestDefinition rebound = DynamicQuestRuntimeService.Instance.GetQuests().Single();
            DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(first.Created, Is.EqualTo(1));
                Assert.That(firstQuest.WorldRevision, Is.EqualTo("world-1"));
                Assert.That(firstQuest.TargetName, Is.EqualTo("black wolf pup"));
                Assert.That(second.Created, Is.EqualTo(1));
                Assert.That(rebound.Id, Is.EqualTo(firstQuest.Id));
                Assert.That(rebound.WorldRevision, Is.EqualTo("world-2"));
                Assert.That(rebound.TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(rebound.BindingKey, Is.Not.EqualTo(firstQuest.BindingKey));
                Assert.That(snapshot.Active, Is.Empty);
            });
        }

        [Test]
        public void Seed_UsesStableQuestIdForSameNpcAndDefinitionAfterRuntimeRestart()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedNpc target = CreateNpc("black wolf pup", "target-npc-1", 1);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");

            service.Seed(new[] { npc, target }, options);
            string firstQuestId = DynamicQuestRuntimeService.Instance.GetQuests().Single().Id;
            DynamicQuestRuntimeService.Instance.ClearAll();

            service.Seed(new[] { npc, target }, options);
            string secondQuestId = DynamicQuestRuntimeService.Instance.GetQuests().Single().Id;

            Assert.Multiple(() =>
            {
                Assert.That(firstQuestId, Is.Not.Empty);
                Assert.That(secondQuestId, Is.EqualTo(firstQuestId));
            });
        }

        [Test]
        public void Seed_DefaultDefinitionsCoverAllStarterRealms()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc[] npcs =
            {
                CreateNpc("Brother Penric", "alb-seed-npc", 1, level: 30),
                CreateNpc("black wolf pup", "alb-target-npc", 1, x: 502000, y: 500000),
                CreateNpc("Aud", "mid-seed-npc", 100, level: 30),
                CreateNpc("young sveawolf", "mid-target-npc", 100, x: 502000, y: 500000),
                CreateNpc("Ionhar", "hib-seed-npc", 200, level: 30),
                CreateNpc("water beetle larva", "hib-target-npc", 200, x: 502000, y: 500000)
            };
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                DynamicQuestSeedOptions.DefaultDeterministicDefinitions);

            DynamicQuestSeedSummary summary = service.Seed(npcs, options);
            DynamicQuestDefinition[] quests = DynamicQuestRuntimeService.Instance.GetQuests().ToArray();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(3));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(summary.CreatedByRealm["Albion"], Is.EqualTo(1));
                Assert.That(summary.CreatedByRealm["Midgard"], Is.EqualTo(1));
                Assert.That(summary.CreatedByRealm["Hibernia"], Is.EqualTo(1));
                Assert.That(quests.Select(quest => quest.StartRegionId), Is.EquivalentTo(new ushort[] { 1, 100, 200 }));
                Assert.That(quests.Select(quest => quest.StartNpcName), Is.EquivalentTo(new[] { "Brother Penric", "Aud", "Ionhar" }));
                Assert.That(quests.SelectMany(quest => quest.Tags), Does.Contain("selector:start:town-npc"));
                Assert.That(quests.SelectMany(quest => quest.Tags), Does.Contain("selector:target:hostile-near-start"));
                foreach (DynamicQuestDefinition quest in quests)
                {
                    string expectedSignal = quest.StartRegionId switch
                    {
                        100 => "time-window:night",
                        200 => "item-acquired",
                        _ => $"mob-growth:killed:region:{quest.StartRegionId}"
                    };
                    DynamicQuestNode choice = quest.Nodes.Single(node => node.Id == "choice");
                    DynamicQuestNode observe = quest.Nodes.Single(node => node.Id == "observe_signal");
                    DynamicQuestEdge followup = choice.Edges.Single(edge => edge.ConditionValue == "followup");
                    DynamicQuestEdge signal = observe.Edges.Single(edge => edge.Condition == DynamicQuestEdgeCondition.WorldSignal);
                    DynamicQuestEdge timeout = observe.Edges.Single(edge => edge.Condition == DynamicQuestEdgeCondition.TimedOut);

                    Assert.That(quest.Tags, Does.Contain($"world-signal:{expectedSignal}"));
                    Assert.That(followup.ToNodeId, Is.EqualTo("observe_signal"));
                    Assert.That(signal.Condition, Is.EqualTo(DynamicQuestEdgeCondition.WorldSignal));
                    Assert.That(signal.ConditionValue, Is.EqualTo(expectedSignal));
                    Assert.That(timeout.ConditionValue, Is.EqualTo(DynamicQuestWorldSignalPolicy.FallbackTimeoutSeconds));
                }
            });
        }

        [Test]
        public void Seed_FixedTargetNamePinsSaferSameNameTargetAwayFromQuestGiver()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30, x: 500000, y: 500000);
            DynamicQuestSeedNpc tooCloseTarget = CreateNpc("black wolf pup", "target-too-close", 1, level: 1, x: 500300, y: 500100);
            DynamicQuestSeedNpc saferTarget = CreateNpc("black wolf pup", "target-safe", 1, level: 1, x: 502300, y: 500000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");

            DynamicQuestSeedSummary summary = service.Seed(new[] { npc, tooCloseTarget, saferTarget }, options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();
            DynamicQuestObjective explore = quest.Nodes.Single(node => node.Id == "explore").Objective;

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(explore.X, Is.EqualTo(502300));
                Assert.That(explore.Y, Is.EqualTo(500000));
            });
        }

        [Test]
        public void Seed_FixedTargetNameAvoidsSameNameTargetClusterWithHigherLevelThreat()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30, x: 500000, y: 500000);
            DynamicQuestSeedNpc unsafeTarget = CreateNpc("black wolf pup", "target-unsafe", 1, level: 1, x: 502000, y: 500000);
            DynamicQuestSeedNpc nearbyThreat = CreateNpc("forest spiderling", "threat-near-target", 1, level: 4, x: 502200, y: 500100);
            DynamicQuestSeedNpc safeTarget = CreateNpc("black wolf pup", "target-safe", 1, level: 1, x: 503200, y: 500000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");

            DynamicQuestSeedSummary summary = service.Seed(new[] { npc, unsafeTarget, nearbyThreat, safeTarget }, options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();
            DynamicQuestObjective explore = quest.Nodes.Single(node => node.Id == "explore").Objective;

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(explore.X, Is.EqualTo(503200));
                Assert.That(explore.Y, Is.EqualTo(500000));
            });
        }

        [Test]
        public void FromProperties_ExpandsLegacySingleRealmDefaultToBalancedStarterRealms()
        {
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_USE_LLM = false;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_MAX_QUESTS = 1;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_DEFINITIONS = DynamicQuestSeedOptions.LegacySingleRealmDefinitions;

            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.FromProperties();

            Assert.Multiple(() =>
            {
                Assert.That(options.Definitions, Has.Count.EqualTo(3));
                Assert.That(options.MaxQuests, Is.EqualTo(3));
                Assert.That(options.Definitions.Select(definition => definition.RegionId), Is.EquivalentTo(new ushort[] { 1, 100, 200 }));
                Assert.That(options.Definitions.Select(definition => definition.BranchWorldSignal), Is.EquivalentTo(new[]
                {
                    "mob-growth:killed:region:1",
                    "time-window:night",
                    "item-acquired"
                }));
            });
        }

        [Test]
        public void FromProperties_UsesBalancedDefaultMaxWhenDefaultDefinitionsAreStored()
        {
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_USE_LLM = false;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_MAX_QUESTS = 1;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_DEFINITIONS = DynamicQuestSeedOptions.DefaultDeterministicDefinitions;

            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.FromProperties();

            Assert.Multiple(() =>
            {
                Assert.That(options.Definitions, Has.Count.EqualTo(3));
                Assert.That(options.MaxQuests, Is.EqualTo(3));
                Assert.That(options.Definitions.Select(definition => definition.RegionId), Is.EquivalentTo(new ushort[] { 1, 100, 200 }));
            });
        }

        [Test]
        public void FromProperties_UpgradesLegacyBalancedDefinitionsToDiverseBranches()
        {
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_USE_LLM = false;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_MAX_QUESTS = 1;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_DEFINITIONS = DynamicQuestSeedOptions.LegacyBalancedDefinitions;

            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.FromProperties();

            Assert.Multiple(() =>
            {
                Assert.That(options.Definitions, Has.Count.EqualTo(3));
                Assert.That(options.MaxQuests, Is.EqualTo(3));
                Assert.That(options.Definitions.Select(definition => definition.BranchWorldSignal), Is.EquivalentTo(new[]
                {
                    "mob-growth:killed:region:1",
                    "time-window:night",
                    "item-acquired"
                }));
            });
        }

        [Test]
        public void FromProperties_ReservesStoryCacheOfferSlotsWhenLlmCacheOffersAreEnabled()
        {
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_USE_LLM = true;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_MAX_QUESTS = 3;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_DEFINITIONS = DynamicQuestSeedOptions.DefaultDeterministicDefinitions;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_OFFER_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_OFFER_MIN_SLOTS = 3;

            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.FromProperties();

            Assert.Multiple(() =>
            {
                Assert.That(options.Definitions, Has.Count.EqualTo(3));
                Assert.That(options.MaxQuests, Is.EqualTo(6));
            });
        }

        [Test]
        public void Seed_SkipsDefinitionWhenTargetNpcDoesNotExistInRegion()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|missing wolf|1|1|5");

            DynamicQuestSeedSummary summary = service.Seed(new[] { npc }, options);

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(0));
                Assert.That(summary.Skipped, Is.EqualTo(1));
                Assert.That(summary.SkippedByRealm["Albion"], Is.EqualTo(1));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests(), Is.Empty);
            });
        }

        [Test]
        public void Seed_RebindsTemplateToAvailableWorldTargetWhenHintTargetIsMissing()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedNpc fallbackTarget = CreateNpc("forest spiderling", "spider-1", 1, x: 502000, y: 500800, z: 2954);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|missing wolf|1|1|5");

            DynamicQuestSeedSummary summary = service.Seed(new[] { npc, fallbackTarget }, options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Skipped, Is.EqualTo(0));
                Assert.That(quest.Id, Does.StartWith("seed-1-"));
                Assert.That(quest.TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(quest.Tags, Does.Contain("dynamic-rebind"));
                Assert.That(quest.Tags, Does.Contain("target:forest spiderling"));
                Assert.That(quest.Tags.Any(tag => tag.StartsWith("binding:", System.StringComparison.OrdinalIgnoreCase)), Is.True);
            });
        }

        [Test]
        public void Seed_AutoAcceptDefinitionCreatesNpcLessTriggeredQuest()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc target = CreateNpc("forest spiderling", "spider-1", 1, x: 522000, y: 492000, z: 2954);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "|1|forest spiderling|1|1|5|AutoAccept|rift-entered");

            DynamicQuestSeedSummary summary = service.Seed(new[] { target }, options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();
            bool accepted = DynamicQuestRuntimeService.Instance.AcceptAvailableWorldQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                "rift-entered");

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Skipped, Is.EqualTo(0));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(summary.CreatedByRealm["Albion"], Is.EqualTo(1));
                Assert.That(quest.StartMode, Is.EqualTo(DynamicQuestStartMode.AutoAccept));
                Assert.That(quest.StartNpcInternalId, Is.EqualTo(string.Empty));
                Assert.That(quest.StartNpcName, Is.EqualTo(string.Empty));
                Assert.That(quest.StartRegionId, Is.EqualTo(1));
                Assert.That(quest.TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(quest.StartNodeId, Is.EqualTo("explore"));
                Assert.That(quest.Tags, Does.Contain("trigger:rift-entered"));
                Assert.That(quest.Tags, Does.Contain("start-mode:AutoAccept"));
                Assert.That(accepted, Is.True);
                Assert.That(DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single().CurrentNodeId,
                    Is.EqualTo("explore"));
            });
        }

        [Test]
        public void Seed_SelectorNpcOfferBindsCurrentQuestGiverAndNearbyHostileTarget()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Brother Penric", "seed-npc-1", 1, level: 50, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc nearTarget = CreateNpc("black wolf pup", "target-near", 1, level: 2, x: 500200, y: 500100, z: 3000);
            DynamicQuestSeedNpc farTarget = CreateNpc("forest spiderling", "target-far", 1, level: 2, x: 540000, y: 540000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(new[] { startNpc, nearTarget, farTarget }, options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(summary.Skipped, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Brother Penric"));
                Assert.That(quest.TargetName, Is.EqualTo("black wolf pup"));
                Assert.That(quest.Nodes.Single(node => node.Id == "explore").Objective.X, Is.EqualTo(500200));
                Assert.That(quest.Tags, Does.Contain("selector:start:town-npc"));
                Assert.That(quest.Tags, Does.Contain("selector:target:hostile-near-start"));
                Assert.That(quest.Tags, Does.Contain("target:black wolf pup"));
                Assert.That(quest.Tags, Does.Contain("branch:mob-growth"));
                Assert.That(quest.Tags, Does.Contain("world-signal:mob-growth:killed:region:1"));
                Assert.That(quest.Nodes.Select(node => node.Id), Does.Contain("observe_signal"));
                Assert.That(quest.Nodes.Single(node => node.Id == "choice").Edges.Single(edge => edge.ConditionValue == "followup").ToNodeId,
                    Is.EqualTo("observe_signal"));
            });
        }

        [Test]
        public void Seed_SelectorNearStartChoosesClosestQuestGiverTargetPairOverHighestLevelNpc()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc distantHighLevelStart = CreateNpc("Bowman Commander", "seed-npc-far", 1, level: 50, x: 100000, y: 100000, z: 3000);
            DynamicQuestSeedNpc distantTarget = CreateNpc("dragon ant worker", "target-far", 1, level: 2, x: 119000, y: 100000, z: 3000);
            DynamicQuestSeedNpc closerStart = CreateNpc("Brother Penric", "seed-npc-near", 1, level: 40, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc closerTarget = CreateNpc("black wolf pup", "target-near", 1, level: 2, x: 502000, y: 500000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { distantHighLevelStart, distantTarget, closerStart, closerTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Brother Penric"));
                Assert.That(quest.TargetName, Is.EqualTo("black wolf pup"));
                Assert.That(quest.Nodes.Single(node => node.Id == "explore").Objective.X, Is.EqualTo(502000));
            });
        }

        [Test]
        public void Seed_SelectorNearStartScansPastManyHighLevelQuestGiversBeforeRankingPairs()
        {
            DynamicQuestSeedService service = new();
            List<DynamicQuestSeedNpc> npcs = new();
            for (int index = 0; index < 48; index++)
            {
                int x = 100000 + index * 10000;
                npcs.Add(CreateNpc($"High Steward {index}", $"seed-high-{index}", 1, level: 75, x: x, y: 100000, z: 3000));
                npcs.Add(CreateNpc($"distant mite {index}", $"target-high-{index}", 1, level: 1, x: x + 4500, y: 100000, z: 3000));
            }

            npcs.Add(CreateNpc("Brother Penric", "seed-near", 1, level: 30, x: 500000, y: 500000, z: 3000));
            npcs.Add(CreateNpc("black wolf pup", "target-near", 1, level: 1, x: 501800, y: 500000, z: 3000));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(npcs, options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Brother Penric"));
                Assert.That(quest.TargetName, Is.EqualTo("black wolf pup"));
                Assert.That(quest.Nodes.Single(node => node.Id == "explore").Objective.X, Is.EqualTo(501800));
            });
        }

        [Test]
        public void Seed_SelectorNearStartDoesNotFallbackToDistantStarterTarget()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Gothi of Odin", "seed-npc-mid", 100, level: 50, x: 800000, y: 727000, z: 3000);
            DynamicQuestSeedNpc distantTarget = CreateNpc("meandering spirit", "target-distant", 100, level: 1, x: 800000, y: 697000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|100|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(new[] { startNpc, distantTarget }, options);

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(0));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests(), Is.Empty);
            });
        }

        [Test]
        public void Seed_SelectorNearStartScansPastHighLevelStartsWithoutNearbyTargets()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc[] unsafeHighLevelStarts = Enumerable.Range(0, 8)
                .Select(index => CreateNpc("Gothi of Odin", $"seed-high-{index}", 100, level: 50, x: 700000 + index * 10000, y: 700000, z: 3000))
                .ToArray();
            DynamicQuestSeedNpc[] distantTargets = unsafeHighLevelStarts
                .Select((start, index) => CreateNpc("meandering spirit", $"target-far-{index}", 100, level: 1, x: 650000 + index * 1000, y: 760000, z: 3000))
                .ToArray();
            DynamicQuestSeedNpc safeStart = CreateNpc("Aud", "seed-safe", 100, level: 40, x: 800000, y: 727000, z: 3000);
            DynamicQuestSeedNpc safeTarget = CreateNpc("young sveawolf", "target-safe", 100, level: 1, x: 802000, y: 727000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|100|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                unsafeHighLevelStarts
                    .Concat(distantTargets)
                    .Concat(new[] { safeStart, safeTarget }),
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(quest.StartNpcName, Is.EqualTo("Aud"));
                Assert.That(quest.TargetName, Is.EqualTo("young sveawolf"));
            });
        }

        [Test]
        public void Seed_SelectorNearStartDoesNotUseLevelZeroCreatureAsQuestGiver()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc levelZeroCreature = CreateNpc("water snake", "creature-start", 1, level: 0, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc nearbyCreatureTarget = CreateNpc("eel", "creature-target", 1, level: 1, x: 500200, y: 500100, z: 3000);
            DynamicQuestSeedNpc realQuestGiver = CreateNpc("Brother Penric", "seed-npc-real", 1, level: 40, x: 520000, y: 520000, z: 3000);
            DynamicQuestSeedNpc realTarget = CreateNpc("black wolf pup", "target-real", 1, level: 2, x: 521000, y: 520500, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { levelZeroCreature, nearbyCreatureTarget, realQuestGiver, realTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Brother Penric"));
                Assert.That(quest.TargetName, Is.EqualTo("black wolf pup"));
            });
        }

        [Test]
        public void Seed_SelectorNearStartPrefersMinimumLevelTargetOverCloserHigherLevelTarget()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Anga Weaver", "seed-npc-1", 1, level: 20, x: 473197, y: 626639, z: 1724);
            DynamicQuestSeedNpc closerHigherTarget = CreateNpc("spiny eel", "target-close", 1, level: 3, x: 473088, y: 625902, z: 1546);
            DynamicQuestSeedNpc fartherMinimumTarget = CreateNpc("puny skeleton", "target-min", 1, level: 1, x: 476525, y: 625903, z: 1601);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, closerHigherTarget, fartherMinimumTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Anga Weaver"));
                Assert.That(quest.TargetName, Is.EqualTo("puny skeleton"));
            });
        }

        [Test]
        public void Seed_SelectorNearStartPrefersStarterPreyOverLargeAnt()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Sir Lukas", "seed-npc-1", 1, level: 30, x: 530000, y: 501000, z: 3000);
            DynamicQuestSeedNpc riskyTarget = CreateNpc("large ant", "target-risky", 1, level: 1, x: 531600, y: 501000, z: 3000);
            DynamicQuestSeedNpc starterPrey = CreateNpc("boar piglet", "target-safe", 1, level: 1, x: 532400, y: 501000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, riskyTarget, starterPrey },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Sir Lukas"));
                Assert.That(quest.TargetName, Is.EqualTo("boar piglet"));
                Assert.That(quest.Nodes.Single(node => node.Id == "explore").Objective.X, Is.EqualTo(532400));
            });
        }

        [Test]
        public void Seed_SelectorNearStartSkipsAggressiveStarterTargetWhenNoSafeTargetExists()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Devyn Godric", "seed-npc-1", 1, level: 30, x: 474770, y: 628824, z: 1724);
            DynamicQuestSeedNpc aggressiveSkeleton = CreateNpc(
                "puny skeleton",
                "target-aggressive-skeleton",
                1,
                level: 1,
                x: 478729,
                y: 628561,
                z: 1626,
                hasSourceNpcMetadata: true,
                sourceAggroLevel: 30,
                sourceAggroRange: 850);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(new[] { startNpc, aggressiveSkeleton }, options);

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(0));
                Assert.That(summary.Skipped, Is.EqualTo(1));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests(), Is.Empty);
            });
        }

        [Test]
        public void Seed_SelectorNearStartPrefersPassiveStarterTargetOverCloserAggressiveTarget()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Devyn Godric", "seed-npc-1", 1, level: 30, x: 474770, y: 628824, z: 1724);
            DynamicQuestSeedNpc aggressiveSkeleton = CreateNpc(
                "puny skeleton",
                "target-aggressive-skeleton",
                1,
                level: 1,
                x: 478729,
                y: 628561,
                z: 1626,
                hasSourceNpcMetadata: true,
                sourceAggroLevel: 30,
                sourceAggroRange: 850);
            DynamicQuestSeedNpc passiveSnake = CreateNpc("muck snake", "target-safe-snake", 1, level: 1, x: 481600, y: 628900, z: 1626);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(new[] { startNpc, aggressiveSkeleton, passiveSnake }, options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.TargetName, Is.EqualTo("muck snake"));
                Assert.That(quest.Nodes.Single(node => node.Id == "explore").Objective.X, Is.EqualTo(481600));
            });
        }

        [Test]
        public void Seed_SelectorRebindsCachedConcreteStoryTitleToCurrentTarget()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate cached = CreateStoryRow(
                "seed-1-8a1b79a8c557103e",
                "Albion",
                1,
                "large ant",
                DynamicQuestStartMode.NpcOffer,
                100,
                DateTime.UtcNow.AddHours(-1));
            cached.Title = "large ant 처치 요청";
            cached.OfferText = "large ant 때문에 이 근처가 어수선합니다.";
            cached.ProgressText = "아직 large ant 위협이 남아 있습니다.";
            cached.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"불안한 부탁\",\"body\":\"large ant의 흔적이 커지고 있습니다.\",\"journalEntry\":\"large ant 조사\",\"mood\":\"urgent\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            repository.Add(cached);
            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[]
            {
                new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Fail("no generation expected"))
            });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");
            options.UseLlm = true;
            options.GenerateMissingStoriesInline = false;

            DynamicQuestSeedSummary summary = service.Seed(new[]
            {
                CreateNpc("Sir Lukas", "seed-npc-1", 1, level: 30, x: 530000, y: 501000, z: 3000),
                CreateNpc("large ant", "target-risky", 1, level: 1, x: 531600, y: 501000, z: 3000),
                CreateNpc("boar piglet", "target-safe", 1, level: 1, x: 532400, y: 501000, z: 3000)
            }, options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.TargetName, Is.EqualTo("boar piglet"));
                Assert.That(quest.Title, Is.EqualTo("boar piglet 처치 요청"));
                Assert.That(quest.OfferText, Does.Contain("boar piglet"));
                Assert.That(quest.StoryNarrativeJson, Does.Contain("boar piglet"));
                Assert.That(quest.StoryNarrativeJson, Does.Contain("수도원 길목"));
                Assert.That(quest.Title, Does.Not.Contain("large ant"));
            });
        }

        [Test]
        public void Seed_SelectorNearStartAvoidsStarterRouteWithDangerousThreat()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Sir Lukas", "seed-npc-1", 1, level: 30, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc routeThreat = CreateNpc("흉포한 large ant", "route-threat", 1, level: 4, x: 502000, y: 500100, z: 3000, hasSourceNpcMetadata: true);
            DynamicQuestSeedNpc riskyRouteTarget = CreateNpc("boar piglet", "target-route-risk", 1, level: 1, x: 504000, y: 500000, z: 3000);
            DynamicQuestSeedNpc saferRouteTarget = CreateNpc("black wolf pup", "target-route-safe", 1, level: 1, x: 500000, y: 504000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, routeThreat, riskyRouteTarget, saferRouteTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.TargetName, Is.EqualTo("black wolf pup"));
                Assert.That(quest.Nodes.Single(node => node.Id == "explore").Objective.X, Is.EqualTo(500000));
                Assert.That(quest.Nodes.Single(node => node.Id == "explore").Objective.Y, Is.EqualTo(504000));
            });
        }

        [Test]
        public void Seed_SelectorNearStartSkipsStarterWhenOnlyTargetRouteIsDangerous()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Sir Lukas", "seed-npc-1", 1, level: 30, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc routeThreat = CreateNpc("흉포한 large ant", "route-threat", 1, level: 4, x: 502000, y: 500100, z: 3000, hasSourceNpcMetadata: true);
            DynamicQuestSeedNpc riskyRouteTarget = CreateNpc("boar piglet", "target-route-risk", 1, level: 1, x: 504000, y: 500000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, routeThreat, riskyRouteTarget },
                options);

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(0));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests(), Is.Empty);
                Assert.That(summary.Messages.Any(message => message.Contains("selector near-start pair not found", StringComparison.OrdinalIgnoreCase)), Is.True);
            });
        }

        [Test]
        public void Seed_SelectorNearStartAvoidsGrownStarterTarget()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Sir Lukas", "seed-npc-1", 1, level: 30, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc grownPiglet = CreateNpc("boar piglet", "target-grown", 1, level: 1, x: 502000, y: 500000, z: 3000);
            grownPiglet.HasGrowthState = true;
            grownPiglet.GrowthStage = MobGrowthStages.Elite;
            grownPiglet.GrowthScore = 90;
            grownPiglet.GrowthLevel = 4;
            grownPiglet.GrowthEffectiveLevel = 5;
            grownPiglet.GrowthPlayerKills = 1;
            DynamicQuestSeedNpc safePiglet = CreateNpc("boar piglet", "target-safe", 1, level: 1, x: 503000, y: 500000, z: 3000);
            DynamicQuestSeedNpc safeSpiderling = CreateNpc("forest spiderling", "target-safe-spiderling", 1, level: 1, x: 503500, y: 500000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, grownPiglet, safePiglet, safeSpiderling },
                options);
            Assert.That(summary.Created, Is.EqualTo(1), string.Join(" | ", summary.Messages));
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(quest.Nodes.Single(node => node.Id == "explore").Objective.X, Is.EqualTo(503500));
            });
        }

        [Test]
        public void Seed_SelectorNearStartAvoidsStarterTargetNameWithGrownSameNameThreats()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Sir Lukas", "seed-npc-1", 1, level: 30, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc normalPiglet = CreateNpc("boar piglet", "target-normal-piglet", 1, level: 1, x: 501800, y: 500000, z: 3000);
            normalPiglet.NameGrowthThreatCount = 4;
            normalPiglet.NameGrowthMaxScore = 5000;
            normalPiglet.NameGrowthMaxEffectiveLevel = 4;
            normalPiglet.NameGrowthPlayerKills = 11;
            DynamicQuestSeedNpc safeSpiderling = CreateNpc("forest spiderling", "target-safe-spiderling", 1, level: 1, x: 502600, y: 500000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, normalPiglet, safeSpiderling },
                options);
            Assert.That(summary.Created, Is.EqualTo(1), string.Join(" | ", summary.Messages));
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(quest.Nodes.Single(node => node.Id == "explore").Objective.X, Is.EqualTo(502600));
            });
        }

        [Test]
        public void Seed_SelectorNearStartExpandsRadiusWhenNearbyStarterTargetsAreGrowthRiskNames()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Sir Lukas", "seed-npc-1", 1, level: 30, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc riskyWolf = CreateNpc("black wolf pup", "target-risk-wolf", 1, level: 1, x: 501800, y: 500000, z: 3000);
            riskyWolf.NameGrowthThreatCount = 5;
            riskyWolf.NameGrowthMaxScore = 5200;
            riskyWolf.NameGrowthMaxEffectiveLevel = 4;
            riskyWolf.NameGrowthPlayerKills = 11;
            DynamicQuestSeedNpc riskyPiglet = CreateNpc("boar piglet", "target-risk-piglet", 1, level: 1, x: 502300, y: 500000, z: 3000);
            riskyPiglet.NameGrowthThreatCount = 4;
            riskyPiglet.NameGrowthMaxScore = 4900;
            riskyPiglet.NameGrowthMaxEffectiveLevel = 4;
            DynamicQuestSeedNpc unsafeAnt = CreateNpc("large ant", "target-unsafe-ant", 1, level: 1, x: 503000, y: 500000, z: 3000);
            DynamicQuestSeedNpc expandedSafeTarget = CreateNpc("ant drone", "target-expanded-safe", 1, level: 2, x: 508200, y: 500000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, riskyWolf, riskyPiglet, unsafeAnt, expandedSafeTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.TargetName, Is.EqualTo("ant drone"));
                Assert.That(quest.Nodes.Single(node => node.Id == "explore").Objective.X, Is.EqualTo(508200));
            });
        }

        [Test]
        public void Seed_SelectorNearStartTreatsGrowthPrefixedSameNameAsStarterNameRisk()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Sir Lukas", "seed-npc-1", 1, level: 30, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc normalWolf = CreateNpc("black wolf pup", "target-normal-wolf", 1, level: 1, x: 501800, y: 500000, z: 3000);
            DynamicQuestSeedNpc fierceWolf = CreateNpc("흉포한 black wolf pup", "target-fierce-wolf", 1, level: 4, x: 502200, y: 500000, z: 3000);
            DynamicQuestSeedNpc safeTarget = CreateNpc("ant drone", "target-expanded-safe", 1, level: 2, x: 508200, y: 500000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, normalWolf, fierceWolf, safeTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.TargetName, Is.EqualTo("ant drone"));
            });
        }

        [Test]
        public void Seed_SelectorNearStartTreatsRawGrowthPrefixedNameAsStarterNameRisk()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Sir Lukas", "seed-npc-1", 1, level: 30, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc normalWolf = CreateNpc("black wolf pup", "target-normal-wolf", 1, level: 1, x: 501800, y: 500000, z: 3000);
            DynamicQuestSeedNpc fierceWolf = CreateNpc("black wolf pup", "target-fierce-wolf", 1, level: 4, x: 502200, y: 500000, z: 3000);
            fierceWolf.RawName = "흉포한 black wolf pup";
            DynamicQuestSeedNpc safeTarget = CreateNpc("ant drone", "target-expanded-safe", 1, level: 2, x: 508200, y: 500000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, normalWolf, fierceWolf, safeTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.TargetName, Is.EqualTo("ant drone"));
            });
        }

        [Test]
        public void Seed_SelectorNearStartSkipsStartNpcWhenOnlySafeTargetIsTooFar()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc unsafeStart = CreateNpc("Sir Lukas", "seed-unsafe", 1, level: 30, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc riskyWolf = CreateNpc("black wolf pup", "target-risk-wolf", 1, level: 1, x: 501800, y: 500000, z: 3000);
            riskyWolf.NameGrowthThreatCount = 5;
            riskyWolf.NameGrowthMaxScore = 5200;
            riskyWolf.NameGrowthMaxEffectiveLevel = 4;
            DynamicQuestSeedNpc farSafe = CreateNpc("muck snake", "target-too-far-safe", 1, level: 1, x: 464833, y: 628288, z: 1682);
            DynamicQuestSeedNpc safeStart = CreateNpc("Captain Prahlion", "seed-safe", 1, level: 50, x: 466548, y: 634346, z: 1954);
            DynamicQuestSeedNpc nearbySafe = CreateNpc("muck snake", "target-near-safe", 1, level: 1, x: 467950, y: 632881, z: 1784);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { unsafeStart, riskyWolf, farSafe, safeStart, nearbySafe },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Captain Prahlion"));
                Assert.That(quest.TargetName, Is.EqualTo("muck snake"));
                Assert.That(quest.Nodes.Single(node => node.Id == "explore").Objective.X, Is.EqualTo(467950));
            });
        }

        [Test]
        public void Seed_SelectorNearStartFallsBackWhenSafeStartCandidatesHaveNoSafeTargets()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc safeStartWithoutTarget = CreateNpc("Brother Penric", "seed-safe-empty", 1, level: 30, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc unsafeNearSafeStart = CreateNpc("black wolf pup", "target-risk-safe-start", 1, level: 1, x: 501800, y: 500000, z: 3000);
            unsafeNearSafeStart.NameGrowthThreatCount = 4;
            unsafeNearSafeStart.NameGrowthMaxEffectiveLevel = 4;
            DynamicQuestSeedNpc unsafeStartWithSafeTarget = CreateNpc("Sir Lukas", "seed-unsafe-with-target", 1, level: 25, x: 510000, y: 510000, z: 3000);
            DynamicQuestSeedNpc closeThreat = CreateNpc("young hill cat", "target-close-threat", 1, level: 3, x: 510500, y: 510000, z: 3000);
            DynamicQuestSeedNpc safeTarget = CreateNpc("forest spiderling", "target-safe-fallback", 1, level: 1, x: 512200, y: 510000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { safeStartWithoutTarget, unsafeNearSafeStart, unsafeStartWithSafeTarget, closeThreat, safeTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Sir Lukas"));
                Assert.That(quest.TargetName, Is.EqualTo("forest spiderling"));
            });
        }

        [Test]
        public void Seed_SelectorNearStartPrefersSaferDistanceOverSameLevelTargetOnQuestGiver()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Pig Herder Stanley", "seed-npc-1", 1, level: 20, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc tooCloseTarget = CreateNpc("boar piglet", "target-too-close", 1, level: 1, x: 500300, y: 500200, z: 3000);
            DynamicQuestSeedNpc saferTarget = CreateNpc("forest spiderling", "target-safe", 1, level: 1, x: 502200, y: 500100, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, tooCloseTarget, saferTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(quest.Nodes.Single(node => node.Id == "explore").Objective.X, Is.EqualTo(502200));
            });
        }

        [Test]
        public void Seed_SelectorNearStartAvoidsTargetClusterWithHigherLevelThreat()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Captain Prahlion", "seed-npc-1", 1, level: 50, x: 466548, y: 634346, z: 1954);
            DynamicQuestSeedNpc unsafeTarget = CreateNpc("muck snake", "target-unsafe", 1, level: 1, x: 467950, y: 632881, z: 1784);
            DynamicQuestSeedNpc nearbyThreat = CreateNpc("slime lizard", "threat-near-target", 1, level: 4, x: 467619, y: 632848, z: 1797);
            DynamicQuestSeedNpc safeTarget = CreateNpc("black wolf pup", "target-safe", 1, level: 1, x: 469200, y: 634000, z: 1900);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, unsafeTarget, nearbyThreat, safeTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Captain Prahlion"));
                Assert.That(quest.TargetName, Is.EqualTo("black wolf pup"));
                Assert.That(quest.Nodes.Single(node => node.Id == "explore").Objective.X, Is.EqualTo(469200));
            });
        }

        [Test]
        public void Seed_SelectorNearStartAvoidsRealmCodedTargetClusterThreat()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc(
                "Tersa Weaver",
                "seed-npc-1",
                1,
                level: 22,
                x: 472188,
                y: 626884,
                z: 1724,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.Albion,
                sourceFlags: GameNPC.eFlags.PEACE);
            DynamicQuestSeedNpc unsafeTarget = CreateNpc(
                "muck snake",
                "target-unsafe",
                1,
                level: 1,
                x: 467950,
                y: 632881,
                z: 1784,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.None);
            DynamicQuestSeedNpc nearbyThreat = CreateNpc(
                "slime lizard",
                "threat-near-target",
                1,
                level: 4,
                x: 467619,
                y: 632848,
                z: 1797,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.Albion);
            DynamicQuestSeedNpc safeTarget = CreateNpc(
                "muck snake",
                "target-safe",
                1,
                level: 1,
                x: 469200,
                y: 634000,
                z: 1900,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.None);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, unsafeTarget, nearbyThreat, safeTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Tersa Weaver"));
                Assert.That(quest.TargetName, Is.EqualTo("muck snake"));
                Assert.That(quest.Nodes.Single(node => node.Id == "explore").Objective.X, Is.EqualTo(469200));
            });
        }

        [Test]
        public void Seed_SelectorNearStartAllowsMildStarterGrowthAddNearTarget()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Sir Lukas", "seed-npc-1", 1, level: 30, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc target = CreateNpc("boar piglet", "target-safe", 1, level: 1, x: 502000, y: 500000, z: 3000);
            DynamicQuestSeedNpc mildGrowthAdd = CreateNpc("노련한 black wolf pup", "target-mild-growth", 1, level: 2, x: 502350, y: 500100, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, target, mildGrowthAdd },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1), string.Join(" | ", summary.Messages));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Sir Lukas"));
                Assert.That(quest.TargetName, Is.EqualTo("boar piglet"));
            });
        }

        [Test]
        public void Seed_SelectorNearStartDoesNotLetMildGrowthNameElsewherePoisonSafeBaseName()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Sir Lukas", "seed-npc-1", 1, level: 30, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc target = CreateNpc("black wolf pup", "target-safe", 1, level: 1, x: 502000, y: 500000, z: 3000);
            DynamicQuestSeedNpc mildGrowthElsewhere = CreateNpc("노련한 black wolf pup", "target-mild-growth-far", 1, level: 2, x: 540000, y: 540000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, target, mildGrowthElsewhere },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1), string.Join(" | ", summary.Messages));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Sir Lukas"));
                Assert.That(quest.TargetName, Is.EqualTo("black wolf pup"));
            });
        }

        [Test]
        public void Seed_SelectorNearStartDoesNotLetFarSevereGrowthNamePoisonSafeBaseName()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Sir Lukas", "seed-npc-1", 1, level: 30, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc target = CreateNpc("black wolf pup", "target-safe", 1, level: 1, x: 502000, y: 500000, z: 3000);
            DynamicQuestSeedNpc farSevereGrowth = CreateNpc("흉포한 black wolf pup", "target-severe-growth-far", 1, level: 4, x: 540000, y: 540000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, target, farSevereGrowth },
                options);
            Assert.That(summary.Created, Is.EqualTo(1), string.Join(" | ", summary.Messages));
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Sir Lukas"));
                Assert.That(quest.TargetName, Is.EqualTo("black wolf pup"));
            });
        }

        [Test]
        public void Seed_SelectorNearStartAvoidsNearbySevereGrowthSameBaseName()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Sir Lukas", "seed-npc-1", 1, level: 30, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc poisonedTarget = CreateNpc("black wolf pup", "target-poisoned", 1, level: 1, x: 502000, y: 500000, z: 3000);
            DynamicQuestSeedNpc nearbySevereGrowth = CreateNpc("흉포한 black wolf pup", "target-severe-growth-near", 1, level: 4, x: 502500, y: 500000, z: 3000);
            DynamicQuestSeedNpc safeAlternative = CreateNpc("forest spiderling", "target-safe-alternative", 1, level: 1, x: 504500, y: 500000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, poisonedTarget, nearbySevereGrowth, safeAlternative },
                options);
            Assert.That(summary.Created, Is.EqualTo(1), string.Join(" | ", summary.Messages));
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Sir Lukas"));
                Assert.That(quest.TargetName, Is.EqualTo("forest spiderling"));
            });
        }

        [Test]
        public void Seed_SelectorNearStartAvoidsNearbyHighLevelSameBaseNameWithoutGrowthPrefix()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Sir Lukas", "seed-npc-1", 1, level: 30, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc poisonedTarget = CreateNpc("black wolf pup", "target-poisoned", 1, level: 1, x: 502000, y: 500000, z: 3000);
            DynamicQuestSeedNpc nearbyHighLevelSameName = CreateNpc("black wolf pup", "target-high-same-name", 1, level: 4, x: 502500, y: 500000, z: 3000);
            DynamicQuestSeedNpc safeAlternative = CreateNpc("forest spiderling", "target-safe-alternative", 1, level: 1, x: 504500, y: 500000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, poisonedTarget, nearbyHighLevelSameName, safeAlternative },
                options);
            Assert.That(summary.Created, Is.EqualTo(1), string.Join(" | ", summary.Messages));
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Sir Lukas"));
                Assert.That(quest.TargetName, Is.EqualTo("forest spiderling"));
            });
        }

        [Test]
        public void Seed_SelectorNearStartSkipsMildGrowthPrefixedTargetAndUsesBaseNameTarget()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Sir Lukas", "seed-npc-1", 1, level: 30, x: 500000, y: 500000, z: 3000);
            DynamicQuestSeedNpc mildGrowthTarget = CreateNpc("노련한 muck snake", "target-mild-growth", 1, level: 2, x: 501800, y: 500000, z: 3000);
            DynamicQuestSeedNpc baseTarget = CreateNpc("muck snake", "target-base", 1, level: 1, x: 502300, y: 500000, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, mildGrowthTarget, baseTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1), string.Join(" | ", summary.Messages));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.TargetName, Is.EqualTo("muck snake"));
            });
        }

        [Test]
        public void Seed_StarterSelectorPrefersPassiveSameLevelTargetOverAggressiveTarget()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc startNpc = CreateNpc("Captain Prahlion", "seed-npc-1", 1, level: 50, x: 466548, y: 634346, z: 1954);
            DynamicQuestSeedNpc aggressiveTarget = CreateNpc(
                "slime lizard",
                "target-aggressive",
                1,
                level: 1,
                x: 467238,
                y: 632158,
                z: 1784,
                hasSourceNpcMetadata: true,
                sourceAggroLevel: 45,
                sourceAggroRange: 500);
            DynamicQuestSeedNpc passiveTarget = CreateNpc(
                "muck snake",
                "target-passive",
                1,
                level: 1,
                x: 467950,
                y: 632881,
                z: 1784,
                hasSourceNpcMetadata: true);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { startNpc, aggressiveTarget, passiveTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.TargetName, Is.EqualTo("muck snake"));
                Assert.That(quest.Nodes.Single(node => node.Id == "explore").Objective.X, Is.EqualTo(467950));
            });
        }

        [Test]
        public void Seed_SelectorTownNpcDoesNotFallbackToCreatureStartWhenQuestGiverIsMissing()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc creatureStart = CreateNpc("skeletal oarsman", "creature-start", 100, level: 17, x: 100000, y: 100000, z: 3000);
            DynamicQuestSeedNpc creatureTarget = CreateNpc("skeletal seafarer", "creature-target", 100, level: 17, x: 100300, y: 100100, z: 3000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|100|selector:hostile-near-start|1|1|20|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { creatureStart, creatureTarget },
                options);

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(0));
                Assert.That(summary.Skipped, Is.EqualTo(1));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests(), Is.Empty);
            });
        }

        [Test]
        public void Seed_SelectorTownNpcDoesNotUseAmbientRealmNpcAsQuestGiver()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc ambientStart = CreateNpc("ambient pixie", "ambient-start", 200, level: 30, x: 338584, y: 444469, z: 5068);
            DynamicQuestSeedNpc realQuestGiver = CreateNpc("Maeve, the Crone", "seed-npc-real", 200, level: 30, x: 345000, y: 445000, z: 5068);
            DynamicQuestSeedNpc realTarget = CreateNpc("water beetle larva", "target-real", 200, level: 1, x: 345300, y: 445200, z: 5068);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|200|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { ambientStart, realQuestGiver, realTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Maeve, the Crone"));
                Assert.That(quest.TargetName, Is.EqualTo("water beetle larva"));
            });
        }

        [Test]
        public void Seed_SelectorTownNpcAvoidsStartNpcWithNearbyThreatsWhenSafeCandidateExists()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc unsafeStart = CreateNpc("Woodsman", "unsafe-start", 1, level: 50, x: 500000, y: 500000);
            DynamicQuestSeedNpc unsafeNearbyThreat = CreateNpc("wild sow", "unsafe-threat", 1, level: 5, x: 500300, y: 500100);
            DynamicQuestSeedNpc unsafePreferredTarget = CreateNpc("boar piglet", "unsafe-target", 1, level: 2, x: 501600, y: 500000);
            DynamicQuestSeedNpc safeStart = CreateNpc("Brother Penric", "safe-start", 1, level: 50, x: 510000, y: 510000);
            DynamicQuestSeedNpc safeTarget = CreateNpc("black wolf pup", "safe-target", 1, level: 2, x: 513000, y: 510000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { unsafeStart, unsafeNearbyThreat, unsafePreferredTarget, safeStart, safeTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Brother Penric"));
                Assert.That(quest.TargetName, Is.EqualTo("black wolf pup"));
            });
        }

        [Test]
        public void Seed_SelectorTownNpcAvoidsNonPeaceRealmNpcWhenPeaceCandidateExists()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc combatStart = CreateNpc(
                "Woodsman",
                "combat-start",
                1,
                level: 50,
                x: 500000,
                y: 500000,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.Albion);
            DynamicQuestSeedNpc combatTarget = CreateNpc("boar piglet", "combat-target", 1, level: 2, x: 501600, y: 500000);
            DynamicQuestSeedNpc peaceStart = CreateNpc(
                "Brother Penric",
                "peace-start",
                1,
                level: 40,
                x: 510000,
                y: 510000,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.Albion,
                sourceFlags: GameNPC.eFlags.PEACE);
            DynamicQuestSeedNpc peaceTarget = CreateNpc("black wolf pup", "peace-target", 1, level: 2, x: 513000, y: 510000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { combatStart, combatTarget, peaceStart, peaceTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(quest.StartNpcName, Is.EqualTo("Brother Penric"));
                Assert.That(quest.TargetName, Is.EqualTo("black wolf pup"));
            });
        }

        [Test]
        public void Seed_SelectorTownNpcAvoidsGameGuardAndServiceNpcWhenPeaceCandidateExists()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc guardStart = CreateNpc(
                "Woodsman",
                "guard-start",
                1,
                level: 50,
                x: 500000,
                y: 500000,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.Albion,
                sourceFlags: GameNPC.eFlags.PEACE,
                sourceTypeName: "DOL.GS.GameGuard");
            DynamicQuestSeedNpc guardNearbyTarget = CreateNpc("boar piglet", "guard-target", 1, level: 2, x: 501600, y: 500000);
            DynamicQuestSeedNpc serviceStart = CreateNpc(
                "Brother Penric",
                "service-start",
                1,
                level: 40,
                x: 510000,
                y: 510000,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.Albion,
                sourceFlags: GameNPC.eFlags.PEACE,
                sourceTypeName: "DOL.GS.GameHealer");
            DynamicQuestSeedNpc serviceTarget = CreateNpc("black wolf pup", "service-target", 1, level: 2, x: 513000, y: 510000);
            DynamicQuestSeedNpc peaceStart = CreateNpc(
                "Brother Penric",
                "peace-start",
                1,
                level: 30,
                x: 520000,
                y: 520000,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.Albion,
                sourceFlags: GameNPC.eFlags.PEACE);
            DynamicQuestSeedNpc peaceTarget = CreateNpc("forest spiderling", "peace-target", 1, level: 2, x: 522000, y: 520000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { guardStart, guardNearbyTarget, serviceStart, serviceTarget, peaceStart, peaceTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(quest.StartNpcName, Is.EqualTo("Brother Penric"));
                Assert.That(quest.TargetName, Is.EqualTo("forest spiderling"));
            });
        }

        [Test]
        public void Seed_SelectorTownNpcAvoidsHastenerNpcWhenPeaceCandidateExists()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc hastenerStart = CreateNpc(
                "Minstrel of Albion",
                "hastener-start",
                1,
                level: 50,
                x: 500000,
                y: 500000,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.Albion,
                sourceFlags: GameNPC.eFlags.PEACE,
                sourceTypeName: "GameHastener");
            DynamicQuestSeedNpc hastenerTarget = CreateNpc("boar piglet", "hastener-target", 1, level: 2, x: 501600, y: 500000);
            DynamicQuestSeedNpc peaceStart = CreateNpc(
                "Brother Penric",
                "peace-start",
                1,
                level: 30,
                x: 520000,
                y: 520000,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.Albion,
                sourceFlags: GameNPC.eFlags.PEACE);
            DynamicQuestSeedNpc peaceTarget = CreateNpc("forest spiderling", "peace-target", 1, level: 2, x: 522000, y: 520000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { hastenerStart, hastenerTarget, peaceStart, peaceTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(quest.StartNpcName, Is.EqualTo("Brother Penric"));
                Assert.That(quest.TargetName, Is.EqualTo("forest spiderling"));
            });
        }

        [Test]
        public void Seed_SelectorTownNpcAvoidsTrainerNpcWhenPeaceCandidateExists()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc trainerStart = CreateNpc(
                "Captain Prahlion",
                "trainer-start",
                1,
                level: 50,
                x: 466548,
                y: 634346,
                z: 1954,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.Albion,
                sourceFlags: GameNPC.eFlags.PEACE,
                sourceTypeName: "DOL.GS.Trainer.ArmsmanTrainer");
            DynamicQuestSeedNpc trainerTarget = CreateNpc("slime lizard", "trainer-target", 1, level: 1, x: 467238, y: 632158, z: 1784);
            DynamicQuestSeedNpc peaceStart = CreateNpc(
                "Anga Weaver",
                "peace-start",
                1,
                level: 20,
                x: 473197,
                y: 626639,
                z: 1724,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.Albion,
                sourceFlags: GameNPC.eFlags.PEACE);
            DynamicQuestSeedNpc peaceTarget = CreateNpc("puny skeleton", "peace-target", 1, level: 1, x: 476525, y: 625903, z: 1601);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { trainerStart, trainerTarget, peaceStart, peaceTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(quest.StartNpcName, Is.EqualTo("Anga Weaver"));
                Assert.That(quest.TargetName, Is.EqualTo("puny skeleton"));
            });
        }

        [Test]
        public void Seed_SelectorTownNpcFallsBackToServiceNpcWhenPeaceCandidatesHaveNoTargets()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc peaceStart = CreateNpc(
                "Brother Penric",
                "peace-start",
                1,
                level: 30,
                x: 500000,
                y: 500000,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.Albion,
                sourceFlags: GameNPC.eFlags.PEACE);
            DynamicQuestSeedNpc trainerStart = CreateNpc(
                "Captain Prahlion",
                "trainer-start",
                1,
                level: 50,
                x: 520000,
                y: 520000,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.Albion,
                sourceFlags: GameNPC.eFlags.PEACE,
                sourceTypeName: "DOL.GS.Trainer.ArmsmanTrainer");
            DynamicQuestSeedNpc trainerTarget = CreateNpc("forest spiderling", "trainer-target", 1, level: 1, x: 522000, y: 520000);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { peaceStart, trainerStart, trainerTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartNpcName, Is.EqualTo("Captain Prahlion"));
                Assert.That(quest.TargetName, Is.EqualTo("forest spiderling"));
            });
        }

        [Test]
        public void Seed_SelectorTownNpcAvoidsGenericHorseNameWhenPeaceCandidateExists()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc horseStart = CreateNpc(
                "horse",
                "horse-start",
                200,
                level: 51,
                x: 344481,
                y: 706177,
                z: 6351,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.Hibernia,
                sourceFlags: GameNPC.eFlags.PEACE);
            DynamicQuestSeedNpc horseTarget = CreateNpc("large frog", "horse-target", 200, level: 1, x: 303569, y: 638862, z: 4848);
            DynamicQuestSeedNpc peaceStart = CreateNpc(
                "Daibheid",
                "peace-start",
                200,
                level: 41,
                x: 341171,
                y: 592655,
                z: 5458,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.Hibernia,
                sourceFlags: GameNPC.eFlags.PEACE);
            DynamicQuestSeedNpc peaceTarget = CreateNpc("badger cub", "peace-target", 200, level: 1, x: 339994, y: 593640, z: 5449);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|200|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { horseStart, horseTarget, peaceStart, peaceTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(quest.StartNpcName, Is.EqualTo("Daibheid"));
                Assert.That(quest.TargetName, Is.EqualTo("badger cub"));
            });
        }

        [Test]
        public void Seed_SelectorTownNpcAvoidsTeleporterNpcWhenPeaceCandidateExists()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc teleporterStart = CreateNpc(
                "Channeler Glasny",
                "teleporter-start",
                200,
                level: 60,
                x: 334718,
                y: 719978,
                z: 4296,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.Hibernia,
                sourceFlags: GameNPC.eFlags.PEACE,
                sourceTypeName: "DOL.GS.Scripts.LiveTeleporter");
            DynamicQuestSeedNpc teleporterTarget = CreateNpc("large frog", "teleporter-target", 200, level: 1, x: 303569, y: 638862, z: 4848);
            DynamicQuestSeedNpc peaceStart = CreateNpc(
                "Daibheid",
                "peace-start",
                200,
                level: 41,
                x: 341171,
                y: 592655,
                z: 5458,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.Hibernia,
                sourceFlags: GameNPC.eFlags.PEACE);
            DynamicQuestSeedNpc peaceTarget = CreateNpc("badger cub", "peace-target", 200, level: 1, x: 339994, y: 593640, z: 5449);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|200|selector:hostile-near-start|1|1|5|NpcOffer|");

            DynamicQuestSeedSummary summary = service.Seed(
                new[] { teleporterStart, teleporterTarget, peaceStart, peaceTarget },
                options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(quest.StartNpcName, Is.EqualTo("Daibheid"));
                Assert.That(quest.TargetName, Is.EqualTo("badger cub"));
            });
        }

        [Test]
        public void Seed_SelectorAutoAcceptBindsNpcLessWorldTarget()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc target = CreateNpc("forest spiderling", "target-1", 1, level: 3, x: 522000, y: 492000, z: 2954);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:world|1|selector:hostile|1|1|5|AutoAccept|region:1");

            DynamicQuestSeedSummary summary = service.Seed(new[] { target }, options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quest.StartMode, Is.EqualTo(DynamicQuestStartMode.AutoAccept));
                Assert.That(quest.StartNpcName, Is.EqualTo(string.Empty));
                Assert.That(quest.TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(quest.StartNodeId, Is.EqualTo("explore"));
                Assert.That(quest.Tags, Does.Contain("selector:start:world"));
                Assert.That(quest.Tags, Does.Contain("selector:target:hostile"));
                Assert.That(quest.Tags, Does.Contain("trigger:region:1"));
            });
        }

        [Test]
        public void Seed_SelectorQuestIdRemainsLogicalAcrossDifferentCurrentBindings()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");

            service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1, level: 50, x: 500000, y: 500000),
                CreateNpc("black wolf pup", "target-1", 1, level: 2, x: 500100, y: 500100)
            }, options);
            string firstQuestId = DynamicQuestRuntimeService.Instance.GetQuests().Single().Id;

            DynamicQuestRuntimeService.Instance.ClearAll();
            service.Seed(new[]
            {
                CreateNpc("Sister Alana", "seed-npc-2", 1, level: 50, x: 510000, y: 510000),
                CreateNpc("forest spiderling", "target-2", 1, level: 2, x: 510100, y: 510100)
            }, options);
            DynamicQuestDefinition rebound = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(rebound.Id, Is.EqualTo(firstQuestId));
                Assert.That(rebound.StartNpcName, Is.EqualTo("Sister Alana"));
                Assert.That(rebound.TargetName, Is.EqualTo("forest spiderling"));
            });
        }

        [Test]
        public void Seed_SelectorRebindsExistingOfferInSameWorldRevision()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");
            options.WorldRevision = "same-world";

            DynamicQuestSeedSummary first = service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1, level: 50, x: 500000, y: 500000),
                CreateNpc("black wolf pup", "target-1", 1, level: 2, x: 502000, y: 500000)
            }, options);
            string firstQuestId = DynamicQuestRuntimeService.Instance.GetQuests().Single().Id;

            DynamicQuestSeedSummary second = service.Seed(new[]
            {
                CreateNpc("Sister Alana", "seed-npc-2", 1, level: 50, x: 510000, y: 510000),
                CreateNpc("forest spiderling", "target-2", 1, level: 2, x: 512000, y: 510000)
            }, options);
            DynamicQuestDefinition rebound = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(first.Created, Is.EqualTo(1));
                Assert.That(second.Created, Is.EqualTo(1));
                Assert.That(rebound.Id, Is.EqualTo(firstQuestId));
                Assert.That(rebound.WorldRevision, Is.EqualTo("same-world"));
                Assert.That(rebound.StartNpcName, Is.EqualTo("Sister Alana"));
                Assert.That(rebound.TargetName, Is.EqualTo("forest spiderling"));
            });
        }

        [Test]
        public void Seed_SelectorRebindInSameWorldKeepsAcceptedProgressSnapshot()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer|");
            options.WorldRevision = "same-world";

            service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1, level: 50, x: 500000, y: 500000),
                CreateNpc("black wolf pup", "target-1", 1, level: 2, x: 502000, y: 500000)
            }, options);
            DynamicQuestDefinition acceptedQuest = DynamicQuestRuntimeService.Instance.GetQuests().Single();
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                acceptedQuest.Id,
                acceptedQuest.StartNodeId,
                new[] { acceptedQuest.StartNodeId },
                null,
                acceptedQuest.BindingKey,
                acceptedQuest.WorldRevision);

            service.Seed(new[]
            {
                CreateNpc("Sister Alana", "seed-npc-2", 1, level: 50, x: 510000, y: 510000),
                CreateNpc("forest spiderling", "target-2", 1, level: 2, x: 512000, y: 510000)
            }, options);
            DynamicQuestDefinition rebound = DynamicQuestRuntimeService.Instance.GetQuests().Single();
            DynamicQuestProgressItem progress = DynamicQuestRuntimeService.Instance
                .GetProgressSnapshot("DummyQuest001", "DummyQuest001", true)
                .Active
                .Single();

            Assert.Multiple(() =>
            {
                Assert.That(rebound.Id, Is.EqualTo(acceptedQuest.Id));
                Assert.That(rebound.TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(progress.QuestId, Is.EqualTo(acceptedQuest.Id));
                Assert.That(progress.TargetName, Is.EqualTo("black wolf pup"));
                Assert.That(progress.BindingKey, Is.EqualTo(acceptedQuest.BindingKey));
                Assert.That(progress.WorldRevision, Is.EqualTo("same-world"));
                Assert.That(progress.Failed, Is.False);
            });
        }

        [Test]
        public void FromProperties_DisablesInlineStoryGenerationForRuntimeSeeding()
        {
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_USE_LLM = true;
            Properties.KDAOC_DYNAMIC_QUEST_AUTO_SEED_DEFINITIONS = DynamicQuestSeedOptions.DefaultDeterministicDefinitions;

            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.FromProperties();

            Assert.Multiple(() =>
            {
                Assert.That(options.UseLlm, Is.True);
                Assert.That(options.GenerateMissingStoriesInline, Is.False);
                Assert.That(options.PrefillStoryCacheInline, Is.False);
            });
        }

        [Test]
        public void Seed_UseLlmNonInlineBindsStructuredRuntimeFallbackWithoutCallingProvider()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            FakeStoryProvider provider = new("main-local", DynamicQuestStoryGenerationResult.Ok(new DynamicQuestStoryText
            {
                Title = "늦게 도착할 이야기",
                OfferText = "{{target}} 이야기는 나중에 채워집니다.",
                ProgressText = "{{target}} 흔적을 따라가세요.",
                FinishText = "{{target}} 위협이 끝났습니다."
            }, "main-local"), "gemma-test");
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(new IDynamicQuestStoryProvider[] { provider }));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            options.GenerateMissingStoriesInline = false;
            options.PrefillStoryCacheInline = false;

            DynamicQuestSeedSummary summary = service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-npc-1", 1)
            }, options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.StoryCachePrefilled, Is.EqualTo(0));
                Assert.That(provider.Calls, Is.EqualTo(0));
                Assert.That(repository.GetActive(), Is.Empty);
                Assert.That(quest.TargetName, Is.EqualTo("black wolf pup"));
                Assert.That(quest.Tags, Does.Contain("llm-story"));
                Assert.That(quest.Tags, Does.Contain("llm-provider:deterministic-fallback"));
                Assert.That(quest.Tags, Does.Contain("story-fallback"));
                Assert.That(quest.Tags, Does.Not.Contain("llm-ready"));
                Assert.That(quest.Tags.Any(tag => tag.StartsWith("llm-score:", StringComparison.OrdinalIgnoreCase)), Is.False);
                Assert.That(quest.StoryNarrativeJson, Is.Not.Empty);
                Assert.That(quest.StoryPresentationJson, Is.Not.Empty);
            });
        }

        [Test]
        public void Seed_UseLlmStoresScoredStoryTemplateAndBindsCurrentTarget()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[]
            {
                new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Ok(new DynamicQuestStoryText
                {
                    Title = "숲속의 작은 위협",
                    OfferText = "Brother Penric이 black wolf pup 처치를 부탁합니다.",
                    ProgressText = "black wolf pup를 찾아 쓰러뜨려야 합니다.",
                    FinishText = "black wolf pup 위협을 제압했습니다."
                }, "main-local"), "gemma-test")
            });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedNpc reboundTarget = CreateNpc("forest spiderling", "spider-1", 1, x: 502000, y: 500800, z: 2954);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;

            DynamicQuestSeedSummary summary = service.Seed(new[] { npc, reboundTarget }, options);
            DbDynamicQuestTemplate row = repository.GetActive().Single();
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(row.StoryProvider, Is.EqualTo("main-local"));
                Assert.That(row.StoryModel, Is.EqualTo("gemma-test"));
                Assert.That(row.StoryQualityScore, Is.GreaterThan(0));
                Assert.That(row.OfferText, Does.Contain("{{target}}"));
                Assert.That(row.OfferText, Does.Not.Contain("black wolf pup"));
                Assert.That(quest.TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(quest.OfferText, Does.Contain("forest spiderling"));
                Assert.That(quest.Tags, Does.Contain("llm-story"));
                Assert.That(quest.Tags, Does.Contain("llm-provider:main-local"));
                Assert.That(quest.Tags, Does.Contain("llm-model:gemma-test"));
            });
        }

        [Test]
        public void Seed_UseLlmCachedStoryDoesNotLeakStaleRuntimeTargetTags()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[]
            {
                new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Ok(new DynamicQuestStoryText
                {
                    Title = "오래된 소문",
                    OfferText = "{{target}} 처치를 부탁합니다.",
                    ProgressText = "{{target}} 흔적을 따라가십시오.",
                    FinishText = "{{target}} 위협이 끝났습니다."
                }, "main-local"), "gemma-test")
            });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedNpc reboundTarget = CreateNpc("forest spiderling", "spider-1", 1, x: 502000, y: 500800, z: 2954);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;

            service.Seed(new[] { npc, reboundTarget }, options);
            DbDynamicQuestTemplate cached = repository.GetActive().Single();
            cached.TagsJson = "[\"llm-story\",\"target:dragon ant worker\",\"region:1\",\"start-mode:NpcOffer\",\"template:old\",\"binding:old\"]";
            repository.Save(cached);

            DynamicQuestRuntimeService.Instance.ClearAll();
            DynamicQuestSeedSummary summary = service.Seed(new[] { npc, reboundTarget }, options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(quest.TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(quest.Tags, Does.Contain("target:forest spiderling"));
                Assert.That(quest.Tags, Does.Not.Contain("target:dragon ant worker"));
                Assert.That(quest.Tags, Does.Not.Contain("binding:old"));
                Assert.That(quest.Tags, Does.Not.Contain("template:old"));
                Assert.That(quest.Tags.Count(tag => tag.StartsWith("target:", StringComparison.OrdinalIgnoreCase)), Is.EqualTo(1));
            });
        }

        [Test]
        public void Seed_UseLlmRegeneratesLegacyCachedStoryWithoutPresentationMetadata()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            FakeStoryProvider provider = new("main-local", DynamicQuestStoryGenerationResult.Ok(new DynamicQuestStoryText
            {
                Title = "새로 쓴 숲의 의뢰",
                OfferText = "Brother Penric이 {{target}} 처치를 부탁합니다.",
                ProgressText = "{{target}}의 흔적을 따라가야 합니다.",
                FinishText = "{{target}} 위협이 사라졌습니다."
            }, "main-local"), "gemma-test");
            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[] { provider });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedNpc target = CreateNpc("black wolf pup", "target-npc-1", 1);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;

            service.Seed(new[] { npc, target }, options);
            DbDynamicQuestTemplate cached = repository.GetActive().Single();
            cached.StoryQualityJson = "{\"totalScore\":100,\"safetyScore\":15,\"structureScore\":15}";
            cached.StoryNarrativeJson = string.Empty;
            cached.StoryPresentationJson = string.Empty;
            repository.Save(cached);

            DynamicQuestRuntimeService.Instance.ClearAll();
            DynamicQuestSeedSummary second = service.Seed(new[] { npc, target }, options);
            DbDynamicQuestTemplate refreshed = repository.GetActive().Single();
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(second.Created, Is.EqualTo(1));
                Assert.That(provider.Calls, Is.EqualTo(2));
                Assert.That(refreshed.StoryNarrativeJson, Is.Not.Empty);
                Assert.That(refreshed.StoryPresentationJson, Is.Not.Empty);
                Assert.That(quest.StoryNarrativeJson, Is.Not.Empty);
                Assert.That(quest.StoryPresentationJson, Is.Not.Empty);
            });
        }

        [Test]
        public void Seed_UseLlmCreatesStructuredFallbackWhenProvidersFail()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[]
            {
                new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Fail("offline"))
            });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedNpc target = CreateNpc("black wolf pup", "target-npc-1", 1);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;

            DynamicQuestSeedSummary summary = service.Seed(new[] { npc, target }, options);
            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(repository.GetActive(), Is.Empty);
                Assert.That(quest.StoryNarrativeJson, Is.Not.Empty);
                Assert.That(quest.StoryPresentationJson, Is.Not.Empty);
                Assert.That(quest.Tags, Does.Contain("llm-provider:deterministic-fallback"));
                Assert.That(quest.Tags, Does.Contain("story-fallback"));
                Assert.That(quest.Tags, Does.Not.Contain("llm-ready"));
                Assert.That(quest.Tags.Any(tag => tag.StartsWith("llm-score:", StringComparison.OrdinalIgnoreCase)), Is.False);
            });
        }

        [Test]
        public void Seed_StoryCachePrunesLowestScoreOnlyOncePerDayWhenFull()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow("story-low-1", 8, DateTime.UtcNow.AddDays(-3)));
            repository.Add(CreateStoryRow("story-high", 92, DateTime.UtcNow.AddDays(-2)));

            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[]
            {
                new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Ok(new DynamicQuestStoryText
                {
                    Title = "다시 쓰인 국경의 전조",
                    OfferText = "Brother Penric이 {{target}} 처치를 부탁합니다.",
                    ProgressText = "{{target}}의 흔적을 따라가야 합니다.",
                    FinishText = "{{target}} 위협이 사라졌습니다."
                }, "main-local"))
            });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedNpc target = CreateNpc("black wolf pup", "target-npc-1", 1);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_MAX_TEMPLATES = 2;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PRUNE_COUNT = 1;

            DynamicQuestSeedSummary first = service.Seed(new[] { npc, target }, options);
            repository.Add(CreateStoryRow("story-low-2", 3, DateTime.UtcNow.AddDays(-4)));
            DynamicQuestRuntimeService.Instance.ClearAll();
            DynamicQuestSeedSummary second = service.Seed(new[] { npc, target }, options);

            Assert.Multiple(() =>
            {
                Assert.That(first.Created, Is.EqualTo(1));
                Assert.That(second.Created, Is.EqualTo(1));
                Assert.That(repository.Rows["story-low-1"].IsActive, Is.False);
                Assert.That(repository.Rows["story-high"].IsActive, Is.True);
                Assert.That(repository.Rows["story-low-2"].IsActive, Is.True);
            });
        }

        [Test]
        public void Seed_StoryCachePrunesUnsafeQualityBeforeOlderEqualScoreRows()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate olderSafe = CreateStoryRow("story-safe-old", 50, DateTime.UtcNow.AddDays(-5));
            olderSafe.StoryQualityJson = "{\"totalScore\":50,\"safetyScore\":20,\"structureScore\":18}";
            DbDynamicQuestTemplate newerUnsafe = CreateStoryRow("story-unsafe-new", 50, DateTime.UtcNow.AddDays(-1));
            newerUnsafe.StoryQualityJson = "{\"totalScore\":50,\"safetyScore\":2,\"structureScore\":5}";
            repository.Add(olderSafe);
            repository.Add(newerUnsafe);

            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[]
            {
                new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Ok(new DynamicQuestStoryText
                {
                    Title = "정리 이후의 의뢰",
                    OfferText = "Brother Penric이 {{target}} 처치를 부탁합니다.",
                    ProgressText = "{{target}}의 흔적을 따라가야 합니다.",
                    FinishText = "{{target}} 위협이 사라졌습니다."
                }, "main-local"))
            });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedNpc target = CreateNpc("black wolf pup", "target-npc-1", 1);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_MAX_TEMPLATES = 2;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PRUNE_COUNT = 1;

            service.Seed(new[] { npc, target }, options);

            Assert.Multiple(() =>
            {
                Assert.That(repository.Rows["story-safe-old"].IsActive, Is.True);
                Assert.That(repository.Rows["story-unsafe-new"].IsActive, Is.False);
            });
        }

        [Test]
        public void Seed_StoryCachePrunesLowestCurrentQualityBeforeLegacyStoredScore()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate immersive = CreateStoryRow("story-current-high-stored-lower", 90, DateTime.UtcNow.AddDays(-2));
            immersive.Title = "{{start_npc}}의 수도원 울타리 경고";
            immersive.OfferText = "{{start_npc}}은 {{realm}} 수도원 울타리 아래 젖은 흙을 보여 주며 {{target}}이 밤사이 성벽 그림자 쪽으로 지나갔다고 말합니다.";
            immersive.ProgressText = "부러진 창대와 꺼진 횃불 흔적을 따라 {{realm}} 수도원 울타리 근처의 {{target}}을 추적해야 합니다.";
            immersive.FinishText = "{{start_npc}}은 수도원 종소리가 다시 들리자 {{target}} 위협이 사라졌다고 안도합니다.";
            immersive.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"젖은 흙의 경고\",\"body\":\"{{start_npc}}은 {{realm}} 수도원 울타리 아래 젖은 흙을 살피며 {{target}}이 성벽 그림자 쪽으로 지나갔다고 말합니다.\",\"journalEntry\":\"{{start_npc}}에게서 {{realm}} 수도원 울타리의 {{target}} 위협을 들었다.\",\"mood\":\"ominous\",\"revealPolicy\":\"FirstSeenOnly\"},{\"nodeId\":\"return\",\"sceneType\":\"Return\",\"title\":\"다시 울린 종\",\"body\":\"{{target}} 위협이 사라지자 수도원 종소리와 횃불이 다시 길목을 채웁니다.\",\"journalEntry\":\"{{target}}을 제압했고 {{start_npc}}에게 돌아가야 한다.\",\"mood\":\"relieved\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            immersive.StoryPresentationJson = "[{\"nodeId\":\"talk\",\"trigger\":\"OnNpcInteract\",\"speaker\":\"StartNpc\",\"text\":\"저 울타리 아래 자국을 보십시오. 놈이 성벽 그림자로 숨어들기 전에 막아야 합니다.\",\"emotion\":\"fear\",\"emote\":\"Point\"},{\"nodeId\":\"return\",\"trigger\":\"OnComplete\",\"speaker\":\"StartNpc\",\"text\":\"이제야 종소리가 제대로 들리는군요. 고맙습니다.\",\"emotion\":\"gratitude\",\"emote\":\"Bow\"}]";

            DbDynamicQuestTemplate systemOnly = CreateStoryRow("story-current-lower-stored-higher", 100, DateTime.UtcNow.AddDays(-1));
            systemOnly.Title = "수도원 울타리의 희미한 흔적";
            systemOnly.OfferText = "Albion 수도원 울타리 아래 젖은 흙에 {{target}}의 흔적이 남아 있습니다.";
            systemOnly.ProgressText = "부러진 창대와 꺼진 횃불 근처에서 {{target}}의 발자국을 따라가야 합니다.";
            systemOnly.FinishText = "{{target}}이 사라지자 Albion 수도원 울타리의 횃불이 다시 안정됩니다.";
            systemOnly.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"울타리의 낮은 경고\",\"body\":\"Albion 수도원 울타리 아래 젖은 흙과 성벽 그림자 사이에 {{target}}의 흔적이 남아 있습니다.\",\"journalEntry\":\"Albion 수도원 울타리에서 {{target}} 흔적을 찾았다.\",\"mood\":\"ominous\",\"revealPolicy\":\"FirstSeenOnly\"},{\"nodeId\":\"return\",\"sceneType\":\"Return\",\"title\":\"다시 켜진 횃불\",\"body\":\"{{target}} 위협이 사라지자 수도원 울타리의 횃불이 다시 곧게 섭니다.\",\"journalEntry\":\"{{target}}을 제압했고 Albion 길목은 잠시 안정됐다.\",\"mood\":\"relieved\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            systemOnly.StoryPresentationJson = "[{\"nodeId\":\"talk\",\"trigger\":\"OnNodeEnter\",\"speaker\":\"System\",\"text\":\"수도원 울타리 근처에 {{target}}가 지나간 자국과 급히 꺼진 횃불이 남아 있습니다.\",\"emotion\":\"caution\",\"emote\":\"Point\"},{\"nodeId\":\"return\",\"trigger\":\"OnComplete\",\"speaker\":\"System\",\"text\":\"수도원 울타리의 경계 소리가 잦아들고, 길목의 불빛이 다시 안정됩니다.\",\"emotion\":\"relief\",\"emote\":\"Smile\"}]";

            repository.Add(immersive);
            repository.Add(systemOnly);

            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedNpc target = CreateNpc("black wolf pup", "target-npc-1", 1);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_MAX_TEMPLATES = 2;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PRUNE_COUNT = 1;

            service.Seed(new[] { npc, target }, options);

            Assert.Multiple(() =>
            {
                Assert.That(repository.Rows["story-current-high-stored-lower"].IsActive, Is.True);
                Assert.That(repository.Rows["story-current-lower-stored-higher"].IsActive, Is.False);
            });
        }

        [Test]
        public void Seed_StoryCachePrunesLowestCurrentQualityAmongNotReadyLegacyRows()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate generic = CreateStoryRow("story-generic-stored-lower", 70, DateTime.UtcNow.AddDays(-2));
            generic.Title = "지역 분위기의 불길한 전조";
            generic.OfferText = "지역 분위기가 심상치 않습니다. {{target}}의 기운이 느껴지는 곳을 조사하여 {{target}}를 처단해 주십시오.";
            generic.ProgressText = "{{target}}의 흔적을 따라 위협의 중심에 가까워지고 있습니다.";
            generic.FinishText = "{{target}} 위협을 제압했고 지역은 잠시 안정을 되찾았습니다.";
            generic.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"불안한 부탁\",\"body\":\"지역 주민은 {{target}}의 흔적이 Albion 곳곳으로 번지고 있다고 말합니다. 아직 작은 소문처럼 들리지만, 방치하면 마을의 밤이 더 길어질 것입니다.\",\"journalEntry\":\"지역 주민에게서 {{target}} 위협이 커지고 있다는 이야기를 들었다.\",\"mood\":\"urgent\",\"revealPolicy\":\"FirstSeenOnly\"},{\"nodeId\":\"explore\",\"sceneType\":\"Discovery\",\"title\":\"흔적의 방향\",\"body\":\"흙과 풀잎 사이에 남은 {{target}}의 흔적이 한 방향으로 이어집니다.\",\"journalEntry\":\"{{target}}의 흔적을 따라 위협의 중심에 가까워지고 있다.\",\"mood\":\"ominous\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            generic.StoryPresentationJson = "[{\"nodeId\":\"talk\",\"trigger\":\"OnNpcInteract\",\"speaker\":\"StartNpc\",\"text\":\"{{target}} 소식 때문에 모두가 조용히 문을 걸어 잠그고 있습니다.\",\"emotion\":\"fear\",\"emote\":\"Shiver\"},{\"nodeId\":\"complete\",\"trigger\":\"OnComplete\",\"speaker\":\"StartNpc\",\"text\":\"이제야 숨을 쉴 수 있겠군요. 고맙습니다.\",\"emotion\":\"gratitude\",\"emote\":\"Bow\"}]";

            DbDynamicQuestTemplate mechanical = CreateStoryRow("story-mechanical-stored-higher", 100, DateTime.UtcNow.AddDays(-1));
            mechanical.Title = "마을 길목의 위협: black wolf pup 처치";
            mechanical.OfferText = "{{target}} {{count}}마리 처치 시, 마을 길목에서 퀘스트 보상을 받으세요.";
            mechanical.ProgressText = "현재 {{target}} {{count}}마리 중 0마리 처치";
            mechanical.FinishText = "마을 길목에서 {{target}} {{count}}마리 처치 완료! 보상을 받으세요.";
            mechanical.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"마을 길목의 위협\",\"body\":\"마을 길목에서 {{target}} {{count}}마리 처치 시 보상을 받을 수 있습니다.\",\"journalEntry\":\"{{target}} {{count}}마리를 처치해야 한다.\",\"mood\":\"urgent\",\"revealPolicy\":\"FirstSeenOnly\"},{\"nodeId\":\"complete\",\"sceneType\":\"Completion\",\"title\":\"처치 완료\",\"body\":\"{{target}} {{count}}마리 처치 완료. 보상을 받으세요.\",\"journalEntry\":\"{{target}} 처치를 완료했다.\",\"mood\":\"relieved\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            mechanical.StoryPresentationJson = "[{\"nodeId\":\"talk\",\"trigger\":\"OnNodeEnter\",\"speaker\":\"System\",\"text\":\"{{target}} {{count}}마리 처치 퀘스트가 시작되었습니다.\",\"emotion\":\"neutral\",\"emote\":\"None\"},{\"nodeId\":\"complete\",\"trigger\":\"OnComplete\",\"speaker\":\"System\",\"text\":\"{{target}} {{count}}마리 처치 완료. 보상을 받으세요.\",\"emotion\":\"neutral\",\"emote\":\"None\"}]";

            repository.Add(generic);
            repository.Add(mechanical);

            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedNpc target = CreateNpc("black wolf pup", "target-npc-1", 1);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_MAX_TEMPLATES = 2;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PRUNE_COUNT = 1;

            service.Seed(new[] { npc, target }, options);

            Assert.Multiple(() =>
            {
                Assert.That(repository.Rows["story-generic-stored-lower"].IsActive, Is.True);
                Assert.That(repository.Rows["story-mechanical-stored-higher"].IsActive, Is.False);
            });
        }

        [Test]
        public void Seed_UseLlmPrefillsStoryCacheBeyondCurrentQuestLimit()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            FakeStoryProvider provider = new("main-local", DynamicQuestStoryGenerationResult.Ok(new DynamicQuestStoryText
            {
                Title = "미리 준비된 의뢰",
                OfferText = "{{target}} 문제가 커지기 전에 도와주세요.",
                ProgressText = "{{target}} 흔적을 추적하세요.",
                FinishText = "{{target}} 위협이 사라졌습니다."
            }, "main-local"), "gemma-test");
            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[] { provider });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                DynamicQuestSeedOptions.DefaultDeterministicDefinitions);
            options.UseLlm = true;
            options.MaxQuests = 1;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE = 10;

            DynamicQuestSeedSummary summary = service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30),
                CreateNpc("black wolf pup", "target-alb", 1, x: 502000, y: 500000),
                CreateNpc("Aud", "seed-npc-100", 100, level: 30),
                CreateNpc("young sveawolf", "target-mid", 100, x: 502000, y: 500000),
                CreateNpc("Ionhar", "seed-npc-200", 200, level: 30),
                CreateNpc("water beetle larva", "target-hib", 200, x: 502000, y: 500000)
            }, options);

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.Skipped, Is.EqualTo(2));
                Assert.That(summary.StoryCachePrefilled, Is.EqualTo(3));
                Assert.That(provider.Calls, Is.EqualTo(3));
                Assert.That(repository.GetActive()
                    .Count(row => string.Equals(row.StoryProvider, "main-local", StringComparison.OrdinalIgnoreCase)), Is.EqualTo(3));
                Assert.That(repository.GetActive().All(row => row.StoryModel == "gemma-test"), Is.True);
            });
        }

        [Test]
        public void Seed_UseLlmPrefillsCurrentWorldCandidatesWithoutOfferingThem()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            FakeStoryProvider provider = new("main-local", DynamicQuestStoryGenerationResult.Ok(new DynamicQuestStoryText
            {
                Title = "{{realm}} 지역의 흔적",
                OfferText = "{{target}} 위협이 번지기 전에 조사해 주세요.",
                ProgressText = "{{target}} 흔적을 따라가세요.",
                FinishText = "{{target}} 위협이 사라졌습니다."
            }, "main-local"), "gemma-test");
            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[] { provider });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE = 4;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_MAX_CANDIDATES = 3;

            DynamicQuestSeedSummary summary = service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-configured", 1, x: 502000, y: 500800),
                CreateNpc("forest spiderling", "target-alb-extra", 1, level: 3, x: 508000, y: 505000),
                CreateNpc("young tomte", "target-mid-extra", 100, level: 6, x: 510000, y: 510000),
                CreateNpc("water beetle", "target-hib-extra", 200, level: 8, x: 512000, y: 512000),
                CreateNpc("training master", "trainer-extra", 1, level: 75, x: 514000, y: 514000)
            }, options);

            DbDynamicQuestTemplate[] rows = repository.GetActive().ToArray();
            DbDynamicQuestTemplate albionWorld = rows.Single(row => row.TargetNameHint == "forest spiderling");
            DbDynamicQuestTemplate midgardWorld = rows.Single(row => row.TargetNameHint == "young tomte");
            DbDynamicQuestTemplate hiberniaWorld = rows.Single(row => row.TargetNameHint == "water beetle");

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.StoryCachePrefillCandidates, Is.EqualTo(4));
                Assert.That(summary.StoryCachePrefilled, Is.EqualTo(4));
                Assert.That(provider.Calls, Is.EqualTo(4));
                Assert.That(rows, Has.Length.EqualTo(4));
                Assert.That(rows.Count(row => row.StartMode == DynamicQuestStartMode.AutoAccept.ToString()), Is.EqualTo(3));
                Assert.That(rows.Select(row => row.TargetNameHint), Does.Contain("forest spiderling"));
                Assert.That(rows.Select(row => row.TargetNameHint), Does.Contain("young tomte"));
                Assert.That(rows.Select(row => row.TargetNameHint), Does.Contain("water beetle"));
                Assert.That(rows.Select(row => row.TargetNameHint), Does.Not.Contain("training master"));
                Assert.That(albionWorld.TagsJson, Does.Contain("world-signal:mob-growth:killed:region:1"));
                Assert.That(albionWorld.Trigger, Is.Empty);
                Assert.That(midgardWorld.TagsJson, Does.Contain("world-signal:time-window:night"));
                Assert.That(midgardWorld.Trigger, Is.EqualTo("time-window:night"));
                Assert.That(hiberniaWorld.TagsJson, Does.Contain("world-signal:item-acquired"));
                Assert.That(hiberniaWorld.Trigger, Is.EqualTo("time-window:dawn"));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests(), Has.Count.EqualTo(1));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests().Single().TargetName, Is.EqualTo("black wolf pup"));
            });
        }

        [Test]
        public void StoryCachePrefillPlan_ReportsWorldCandidatesWithoutMutation()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_MAX_CANDIDATES = 3;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE = 2;

            DynamicQuestStoryCachePrefillPlanSnapshot plan = service.GetStoryCachePrefillPlanSnapshot(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-configured", 1, x: 502000, y: 500800),
                CreateNpc("forest spiderling", "target-alb-extra", 1, level: 3, x: 508000, y: 505000),
                CreateNpc("young tomte", "target-mid-extra", 100, level: 6, x: 510000, y: 510000),
                CreateNpc("water beetle", "target-hib-extra", 200, level: 8, x: 512000, y: 512000),
                CreateNpc("training master", "trainer-extra", 1, level: 75, x: 514000, y: 514000)
            }, options, sampleLimit: 10);

            Assert.Multiple(() =>
            {
                Assert.That(plan.ScannedNpcs, Is.EqualTo(6));
                Assert.That(plan.ExistingDefinitions, Is.EqualTo(1));
                Assert.That(plan.WorldCandidates, Is.EqualTo(3));
                Assert.That(plan.TotalCandidates, Is.EqualTo(4));
                Assert.That(plan.BatchSize, Is.EqualTo(2));
                Assert.That(plan.CanGenerateNewStory, Is.True);
                Assert.That(plan.Reasons, Is.Empty);
                Assert.That(plan.Samples.Select(sample => sample.TargetName), Does.Contain("forest spiderling"));
                Assert.That(plan.Samples.Single(sample => sample.TargetName == "forest spiderling").BranchWorldSignal, Is.EqualTo("mob-growth:killed:region:1"));
                Assert.That(plan.Samples.Single(sample => sample.TargetName == "young tomte").BranchWorldSignal, Is.EqualTo("time-window:night"));
                Assert.That(plan.Samples.Single(sample => sample.TargetName == "water beetle").BranchWorldSignal, Is.EqualTo("item-acquired"));
                Assert.That(plan.Samples.Select(sample => sample.TargetName), Does.Not.Contain("training master"));
                Assert.That(repository.GetActive(), Is.Empty);
            });
        }

        [Test]
        public void StoryCachePrefillPlan_PrefersNpcOfferGrowthBranchCandidateOverNpcLessWorldCandidate()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_MAX_CANDIDATES = 5;

            DynamicQuestSeedNpc grownMauler = CreateNpc(
                "black mauler",
                "growth-mid-mauler",
                100,
                level: 9,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.None);
            grownMauler.HasGrowthState = true;
            grownMauler.GrowthStage = MobGrowthStages.Elite;
            grownMauler.GrowthEffectiveLevel = 13;
            grownMauler.GrowthScore = 80;

            DynamicQuestStoryCachePrefillPlanSnapshot plan = service.GetStoryCachePrefillPlanSnapshot(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-configured", 1, x: 502000, y: 500800),
                CreateNpc(
                    "Field Warden",
                    "growth-quest-giver-mid",
                    100,
                    level: 30,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.Midgard,
                    sourceFlags: GameNPC.eFlags.PEACE,
                    sourceTypeName: "GameNPC"),
                grownMauler
            }, options, sampleLimit: 10);

            DynamicQuestStoryCachePrefillCandidate growth = plan.Samples.Single(sample =>
                string.Equals(sample.TargetName, "black mauler", StringComparison.OrdinalIgnoreCase));

            Assert.Multiple(() =>
            {
                Assert.That(growth.StartMode, Is.EqualTo(DynamicQuestStartMode.NpcOffer.ToString()));
                Assert.That(growth.StartNpcName, Is.EqualTo("selector:quest-giver"));
                Assert.That(growth.MinLevel, Is.EqualTo(12));
                Assert.That(growth.MaxLevel, Is.EqualTo(14));
                Assert.That(growth.Count, Is.EqualTo(1));
                Assert.That(growth.BranchWorldSignal, Is.EqualTo("mob-growth:killed:region:100"));
                Assert.That(plan.ByStartMode[DynamicQuestStartMode.NpcOffer.ToString()], Is.EqualTo(2));
                Assert.That(plan.ByStartMode.ContainsKey(DynamicQuestStartMode.AutoAccept.ToString()), Is.False);
            });
        }

        [Test]
        public void Seed_StoryCachePrefillsNpcOfferGrowthBranchUsingEffectiveLevel()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            FakeStoryProvider provider = new("main-local", DynamicQuestStoryGenerationResult.Ok(new DynamicQuestStoryText
            {
                Title = "{{realm}} 성장한 위협의 흔적",
                OfferText = "{{target}} 위협이 더 커지기 전에 추적해 주세요.",
                ProgressText = "{{target}} 흔적을 따라가세요.",
                FinishText = "{{target}} 위협의 고리가 끊어졌습니다."
            }, "main-local"), "gemma-test");
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(new IDynamicQuestStoryProvider[] { provider }));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE = 2;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_MAX_CANDIDATES = 1;

            DynamicQuestSeedNpc grownMauler = CreateNpc(
                "black mauler",
                "growth-mid-mauler",
                100,
                level: 9,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.None);
            grownMauler.HasGrowthState = true;
            grownMauler.GrowthStage = MobGrowthStages.Elite;
            grownMauler.GrowthEffectiveLevel = 13;
            grownMauler.GrowthScore = 80;

            DynamicQuestSeedSummary summary = service.PrefillStoryCache(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-configured", 1, x: 502000, y: 500800),
                CreateNpc(
                    "Field Warden",
                    "growth-quest-giver-mid",
                    100,
                    level: 30,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.Midgard,
                    sourceFlags: GameNPC.eFlags.PEACE,
                    sourceTypeName: "GameNPC"),
                grownMauler
            }, options);

            DbDynamicQuestTemplate growth = repository.GetActive()
                .Single(row => string.Equals(row.TargetNameHint, "black mauler", StringComparison.OrdinalIgnoreCase));

            Assert.Multiple(() =>
            {
                Assert.That(summary.StoryCachePrefillCandidates, Is.EqualTo(2));
                Assert.That(summary.StoryCachePrefilled, Is.EqualTo(2));
                Assert.That(summary.StoryCachePrefillResolveSkipped, Is.EqualTo(0));
                Assert.That(provider.Calls, Is.EqualTo(2));
                Assert.That(growth.StartMode, Is.EqualTo(DynamicQuestStartMode.NpcOffer.ToString()));
                Assert.That(growth.PreferredStartNpcName, Is.EqualTo("Field Warden"));
                Assert.That(growth.MinLevel, Is.EqualTo(12));
                Assert.That(growth.MaxLevel, Is.EqualTo(14));
                Assert.That(growth.TagsJson, Does.Contain("world-signal:mob-growth:killed:region:100"));
            });
        }

        [Test]
        public void StoryCachePrefillPlan_ReservesWorldPrefillSlotsForNpcLessCandidatesWhenGrowthCandidatesArePlentiful()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_MAX_CANDIDATES = 4;

            DynamicQuestSeedNpc[] growthTargets =
            {
                CreateGrowthNpc("growth-wolf", "growth-wolf", 1, level: 6, effectiveLevel: 9),
                CreateGrowthNpc("growth-spider", "growth-spider", 1, level: 7, effectiveLevel: 10),
                CreateGrowthNpc("growth-ant", "growth-ant", 1, level: 8, effectiveLevel: 11),
                CreateGrowthNpc("growth-bandit", "growth-bandit", 1, level: 9, effectiveLevel: 12)
            };

            DynamicQuestStoryCachePrefillPlanSnapshot plan = service.GetStoryCachePrefillPlanSnapshot(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-configured", 1, x: 502000, y: 500800),
                CreateNpc(
                    "Field Warden",
                    "growth-quest-giver-alb",
                    1,
                    level: 30,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.Albion,
                    sourceFlags: GameNPC.eFlags.PEACE,
                    sourceTypeName: "GameNPC"),
                growthTargets[0],
                growthTargets[1],
                growthTargets[2],
                growthTargets[3],
                CreateNpc("plain wolf", "plain-wolf", 1, level: 4, hasSourceNpcMetadata: true, sourceRealm: eRealm.None),
                CreateNpc("plain spider", "plain-spider", 1, level: 5, hasSourceNpcMetadata: true, sourceRealm: eRealm.None)
            }, options, sampleLimit: 10);

            Assert.Multiple(() =>
            {
                Assert.That(plan.WorldCandidates, Is.EqualTo(4));
                Assert.That(plan.ByStartMode[DynamicQuestStartMode.NpcOffer.ToString()], Is.EqualTo(3));
                Assert.That(plan.ByStartMode[DynamicQuestStartMode.AutoAccept.ToString()], Is.EqualTo(2));
                Assert.That(plan.Samples.Count(sample => sample.StartMode == DynamicQuestStartMode.NpcOffer.ToString() &&
                                                        sample.StartNpcName == "selector:quest-giver"), Is.EqualTo(2));
                Assert.That(plan.Samples.Count(sample => sample.StartMode == DynamicQuestStartMode.AutoAccept.ToString()), Is.EqualTo(2));
            });
        }

        [Test]
        public void Seed_StoryCachePrefillDoesNotStoreStoriesBelowCacheQualityGate()
        {
            int previousMinimum = Properties.KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE;
            try
            {
                Properties.KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE = 50;
                FakeDynamicQuestTemplateRepository repository = new();
                DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[]
                {
                    new RawStoryProvider("main-local", DynamicQuestStoryGenerationResult.Ok(new DynamicQuestStoryText
                    {
                        Title = "Brother Penric report",
                        OfferText = "Brother Penric saw trouble near Albion road.",
                        ProgressText = "Check the road.",
                        FinishText = "Road is quiet.",
                        NarrativeScenes = new[]
                        {
                            new DynamicQuestNarrativeScene
                            {
                                NodeId = "talk",
                                SceneType = "Intro",
                                Title = "Road note",
                                Body = "Brother Penric Albion road.",
                                JournalEntry = "",
                                Mood = "urgent",
                                RevealPolicy = "FirstSeenOnly"
                            }
                        },
                        PresentationBeats = new[]
                        {
                            new DynamicQuestPresentationBeat
                            {
                                NodeId = "talk",
                                Trigger = "OnNpcInteract",
                                Speaker = "StartNpc",
                                Text = "Stay alert.",
                                Emotion = "",
                                Emote = ""
                            }
                        }
                    }, "main-local"), "weak-cache-story")
                });
                DynamicQuestSeedService service = new(repository, storyService);
                DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                    "Brother Penric|1|black wolf pup|1|1|5");
                options.UseLlm = true;

                DynamicQuestSeedSummary summary = service.PrefillStoryCache(new[]
                {
                    CreateNpc("Brother Penric", "seed-npc-1", 1),
                    CreateNpc("black wolf pup", "target-npc-1", 1)
                }, options);

                Assert.Multiple(() =>
                {
                    Assert.That(summary.StoryCachePrefillCandidates, Is.EqualTo(1));
                    Assert.That(summary.StoryCachePrefillAttempted, Is.EqualTo(1));
                    Assert.That(summary.StoryCachePrefillQualityRejected, Is.EqualTo(1));
                    Assert.That(summary.StoryCachePrefilled, Is.EqualTo(0));
                    Assert.That(summary.Messages, Does.Contain("story cache prefill rejected by quality gate: 1"));
                    Assert.That(repository.GetActive(), Is.Empty);
                });
            }
            finally
            {
                Properties.KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE = previousMinimum;
            }
        }

        [Test]
        public void Seed_StoryCachePrefillBatchLimitsProviderAttemptsWhenGenerationFails()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            FakeStoryProvider provider = new("main-local", DynamicQuestStoryGenerationResult.Fail("offline"));
            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[] { provider });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE = 2;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_MAX_CANDIDATES = 3;

            DynamicQuestSeedSummary summary = service.PrefillStoryCache(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-configured", 1, x: 502000, y: 500800),
                CreateNpc("forest spiderling", "target-alb-extra", 1, level: 3, x: 508000, y: 505000),
                CreateNpc("young tomte", "target-mid-extra", 100, level: 6, x: 510000, y: 510000),
                CreateNpc("water beetle", "target-hib-extra", 200, level: 8, x: 512000, y: 512000)
            }, options);

            Assert.Multiple(() =>
            {
                Assert.That(summary.StoryCachePrefillCandidates, Is.EqualTo(4));
                Assert.That(summary.StoryCachePrefillAttempted, Is.EqualTo(2));
                Assert.That(summary.StoryCachePrefillGenerationFailed, Is.EqualTo(2));
                Assert.That(summary.StoryCachePrefilled, Is.EqualTo(0));
                Assert.That(summary.StoryCachePrefillGenerationErrors["main-local:offline"], Is.EqualTo(2));
                Assert.That(summary.Messages, Does.Contain("story cache prefill error main-local:offline: 2"));
                Assert.That(provider.Calls, Is.EqualTo(2));
            });
        }

        [Test]
        public void Seed_StoryCacheWorldPrefillBindsMobGrowthSignalBranchWhenOffered()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            FakeStoryProvider provider = new("main-local", DynamicQuestStoryGenerationResult.Ok(new DynamicQuestStoryText
            {
                Title = "{{realm}} 지역의 성장 징후",
                OfferText = "{{target}} 위협이 번지기 전에 조사해 주세요.",
                ProgressText = "{{target}} 흔적을 따라가세요.",
                FinishText = "{{target}} 위협이 잠잠해졌습니다."
            }, "main-local"), "gemma-test");
            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[] { provider });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            options.MaxQuests = 1;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE = 4;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_MAX_CANDIDATES = 1;

            service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-configured", 1),
                CreateNpc("forest spiderling", "target-alb-extra", 1, level: 1, x: 522000, y: 492000, z: 2954)
            }, options);

            DbDynamicQuestTemplate cachedWorld = repository.GetActive()
                .Single(row => row.TargetNameHint == "forest spiderling");

            DynamicQuestRuntimeService.Instance.ClearAll();
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = false;
            options.UseStoryCacheOffers = true;
            options.MaxQuests = 2;

            DynamicQuestSeedSummary second = service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-configured", 1),
                CreateNpc("forest spiderling", "target-alb-extra", 1, level: 1, x: 522000, y: 492000, z: 2954)
            }, options);

            DynamicQuestDefinition branchQuest = DynamicQuestRuntimeService.Instance.GetQuests()
                .Single(quest => quest.TargetName == "forest spiderling");

            Assert.That(cachedWorld.TagsJson, Does.Contain("world-signal:mob-growth:killed:region:1"));
            Assert.That(branchQuest.Nodes.Select(node => node.Id), Does.Contain("observe_signal"));

            DynamicQuestNode observe = branchQuest.Nodes.Single(node => node.Id == "observe_signal");
            DynamicQuestEdge signal = observe.Edges.Single(edge => edge.Condition == DynamicQuestEdgeCondition.WorldSignal);
            DynamicQuestEdge timeout = observe.Edges.Single(edge => edge.Condition == DynamicQuestEdgeCondition.TimedOut);

            Assert.Multiple(() =>
            {
                Assert.That(second.StoryCacheOffered, Is.EqualTo(1));
                Assert.That(branchQuest.StartMode, Is.EqualTo(DynamicQuestStartMode.AutoAccept));
                Assert.That(branchQuest.Tags, Does.Contain("world-signal:mob-growth:killed:region:1"));
                Assert.That(signal.Condition, Is.EqualTo(DynamicQuestEdgeCondition.WorldSignal));
                Assert.That(signal.ConditionValue, Is.EqualTo("mob-growth:killed:region:1"));
                Assert.That(timeout.ConditionValue, Is.EqualTo(DynamicQuestWorldSignalPolicy.FallbackTimeoutSeconds));
            });
        }

        [Test]
        public void Seed_DeterministicNpcOfferMobGrowthBranchFollowupWaitsForWorldSignal()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5|NpcOffer||mob-growth:killed:region:1");

            service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-configured", 1, level: 1, x: 502000, y: 500000, z: 2954)
            }, options);

            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests()
                .Single(quest => quest.TargetName == "black wolf pup");
            DynamicQuestNode choice = quest.Nodes.Single(node => node.Id == "choice");
            DynamicQuestEdge followup = choice.Edges.Single(edge => edge.ConditionValue == "followup");
            DynamicQuestNode observe = quest.Nodes.Single(node => node.Id == "observe_signal");
            DynamicQuestEdge signal = observe.Edges.Single(edge => edge.Condition == DynamicQuestEdgeCondition.WorldSignal);
            DynamicQuestEdge timeout = observe.Edges.Single(edge => edge.Condition == DynamicQuestEdgeCondition.TimedOut);

            Assert.Multiple(() =>
            {
                Assert.That(quest.Nodes.Select(node => node.Id), Does.Contain("observe_signal"));
                Assert.That(followup.ToNodeId, Is.EqualTo("observe_signal"));
                Assert.That(signal.ConditionValue, Is.EqualTo("mob-growth:killed:region:1"));
                Assert.That(timeout.ConditionValue, Is.EqualTo(DynamicQuestWorldSignalPolicy.FallbackTimeoutSeconds));
            });
        }

        [Test]
        public void Seed_DeterministicNpcOfferTimeWindowBranchFollowupWaitsForWorldSignal()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5|NpcOffer||time-window:night");

            service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-configured", 1, level: 1, x: 502000, y: 500000, z: 2954)
            }, options);

            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests()
                .Single(quest => quest.TargetName == "black wolf pup");
            DynamicQuestNode observe = quest.Nodes.Single(node => node.Id == "observe_signal");
            DynamicQuestEdge signal = observe.Edges.Single(edge => edge.Condition == DynamicQuestEdgeCondition.WorldSignal);
            DynamicQuestEdge timeout = observe.Edges.Single(edge => edge.Condition == DynamicQuestEdgeCondition.TimedOut);

            Assert.Multiple(() =>
            {
                Assert.That(quest.Tags, Does.Contain("branch:time-window"));
                Assert.That(quest.Tags, Does.Contain("world-signal:time-window:night"));
                Assert.That(signal.Condition, Is.EqualTo(DynamicQuestEdgeCondition.WorldSignal));
                Assert.That(signal.ConditionValue, Is.EqualTo("time-window:night"));
                Assert.That(timeout.ConditionValue, Is.EqualTo(DynamicQuestWorldSignalPolicy.FallbackTimeoutSeconds));
            });
        }

        [Test]
        public void Seed_DeterministicNpcOfferItemAcquiredBranchFollowupWaitsForWorldSignal()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5|NpcOffer||item-acquired:id:ancient-relic-01");

            service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-configured", 1, level: 1, x: 502000, y: 500000, z: 2954)
            }, options);

            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests()
                .Single(quest => quest.TargetName == "black wolf pup");
            DynamicQuestNode observe = quest.Nodes.Single(node => node.Id == "observe_signal");
            DynamicQuestEdge signal = observe.Edges.Single(edge => edge.Condition == DynamicQuestEdgeCondition.WorldSignal);
            DynamicQuestEdge timeout = observe.Edges.Single(edge => edge.Condition == DynamicQuestEdgeCondition.TimedOut);

            Assert.Multiple(() =>
            {
                Assert.That(quest.Tags, Does.Contain("branch:item-acquired"));
                Assert.That(quest.Tags, Does.Contain("world-signal:item-acquired:id:ancient-relic-01"));
                Assert.That(signal.Condition, Is.EqualTo(DynamicQuestEdgeCondition.WorldSignal));
                Assert.That(signal.ConditionValue, Is.EqualTo("item-acquired:id:ancient-relic-01"));
                Assert.That(timeout.ConditionValue, Is.EqualTo(DynamicQuestWorldSignalPolicy.FallbackTimeoutSeconds));
            });
        }

        [Test]
        public void Seed_UseLlmFillsRemainingActiveOffersFromStoryCache()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-albion-forest-spiderling",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                91,
                DateTime.UtcNow.AddHours(-3)));
            repository.Add(CreateStoryRow(
                "story-cache-midgard-young-tomte",
                "Midgard",
                100,
                "young tomte",
                DynamicQuestStartMode.AutoAccept,
                87,
                DateTime.UtcNow.AddHours(-4)));
            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[]
            {
                new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Fail("no generation expected"))
            });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            options.UseStoryCacheOffers = true;
            options.MaxQuests = 3;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_MAX_TEMPLATES = 500;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = false;

            DynamicQuestSeedSummary summary = service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-configured", 1),
                CreateNpc("forest spiderling", "target-alb-cache", 1),
                CreateNpc("young tomte", "target-mid-cache", 100)
            }, options);

            DynamicQuestDefinition[] quests = DynamicQuestRuntimeService.Instance.GetQuests()
                .OrderBy(quest => quest.Id, StringComparer.OrdinalIgnoreCase)
                .ToArray();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(3));
                Assert.That(summary.StoryCacheOffered, Is.EqualTo(2));
                Assert.That(summary.Failed, Is.EqualTo(0));
                Assert.That(quests.Select(quest => quest.TargetName), Is.EquivalentTo(new[]
                {
                    "black wolf pup",
                    "forest spiderling",
                    "young tomte"
                }));
                Assert.That(quests.Count(quest => quest.StartMode == DynamicQuestStartMode.AutoAccept), Is.EqualTo(2));
                Assert.That(repository.Rows["story-cache-albion-forest-spiderling"].LastBindingKey, Is.Not.Empty);
                Assert.That(repository.Rows["story-cache-midgard-young-tomte"].LastBindingKey, Is.Not.Empty);
            });
        }

        [Test]
        public void Seed_StoryCacheOffersInterleaveNpcOfferGrowthRowsWithNpcLessRows()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate growth = CreateStoryRow(
                "story-cache-midgard-growth-black-mauler",
                "Midgard",
                100,
                "black mauler",
                DynamicQuestStartMode.NpcOffer,
                96,
                DateTime.UtcNow.AddHours(-5));
            growth.PreferredStartNpcName = "Field Warden";
            growth.MinLevel = 12;
            growth.MaxLevel = 14;
            growth.TagsJson = "[\"llm-story\",\"branch:mob-growth\",\"world-signal:mob-growth:killed:region:100\"]";
            growth.OfferText = "{{start_npc}}은 {{realm}} 보급로를 끊는 {{target}} 무리를 조용히 처치해 달라고 부탁한다.";
            growth.ProgressText = "{{realm}} 경계의 {{target}} 흔적을 따라가며 {{start_npc}}의 보고가 맞는지 확인한다.";
            growth.FinishText = "{{start_npc}}에게 {{target}} 위협을 정리했다는 소식을 전한다.";
            growth.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"눈밭 경계의 찢긴 깃발\",\"body\":\"{{start_npc}}은 눈밭에 박힌 {{realm}} 보급 깃발을 보여 주며 {{target}} 무리가 다음 순찰대를 덮치기 전에 막아 달라고 말합니다.\",\"journalEntry\":\"{{start_npc}}에게서 {{realm}} 경계의 {{target}} 위협을 조사해 달라는 부탁을 받았다.\",\"mood\":\"urgent\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            growth.StoryPresentationJson = "[{\"nodeId\":\"talk\",\"trigger\":\"OnNpcInteract\",\"speaker\":\"StartNpc\",\"text\":\"보급로가 조용히 끊기고 있습니다. {{target}}를 막아 주십시오.\",\"emotion\":\"fear\",\"emote\":\"Shiver\"}]";
            repository.Add(growth);
            repository.Add(CreateStoryRow(
                "story-cache-albion-auto-forest-spiderling",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                95,
                DateTime.UtcNow.AddHours(-4)));
            repository.Add(CreateStoryRow(
                "story-cache-albion-auto-boar-piglet",
                "Albion",
                1,
                "boar piglet",
                DynamicQuestStartMode.AutoAccept,
                94,
                DateTime.UtcNow.AddHours(-3)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(new[]
            {
                new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Fail("no generation expected"))
            }));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            options.UseStoryCacheOffers = true;
            options.MaxQuests = 3;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = false;

            DynamicQuestSeedSummary summary = service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-configured", 1),
                CreateNpc(
                    "Field Warden",
                    "growth-quest-giver-mid",
                    100,
                    level: 30,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.Midgard,
                    sourceFlags: GameNPC.eFlags.PEACE,
                    sourceTypeName: "GameNPC"),
                CreateNpc("black mauler", "growth-mid-mauler", 100, level: 13, hasSourceNpcMetadata: true, sourceRealm: eRealm.None),
                CreateNpc("forest spiderling", "auto-alb-forest-spiderling", 1, level: 1, x: 522000, y: 492000, z: 2954),
                CreateNpc("boar piglet", "auto-alb-boar-piglet", 1, level: 1, x: 532400, y: 501000, z: 3000)
            }, options);

            DynamicQuestDefinition[] offered = DynamicQuestRuntimeService.Instance.GetQuests()
                .Where(quest => !string.Equals(quest.TargetName, "black wolf pup", StringComparison.OrdinalIgnoreCase))
                .OrderBy(quest => quest.CreatedAt)
                .ToArray();

            Assert.Multiple(() =>
            {
                string messages = string.Join(" | ", summary.Messages);
                Assert.That(summary.StoryCacheOffered, Is.EqualTo(2), messages);
                Assert.That(offered, Has.Length.EqualTo(2), messages);
                Assert.That(offered.Count(quest => quest.StartMode == DynamicQuestStartMode.NpcOffer), Is.EqualTo(1), messages);
                Assert.That(offered.Count(quest => quest.StartMode == DynamicQuestStartMode.AutoAccept), Is.EqualTo(1), messages);
                Assert.That(offered.Any(quest => quest.TargetName == "black mauler"), Is.True, messages);
            });
        }

        [Test]
        public void Seed_StoryCacheOffersSkipGenericScaffoldRowsEvenWithLegacyHighScore()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate generic = CreateStoryRow(
                "story-cache-generic-scaffold-high-score",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-5));
            generic.Title = "지역 분위기의 불길한 조짐";
            generic.OfferText = "지역 분위기가 심상치 않습니다. {{target}}의 기운이 느껴지는 곳을 조사하여 {{target}}를 처단해 주십시오.";
            generic.ProgressText = "{{target}}가 나타나 마을을 위협하고 있습니다. {{target}}를 1마리 더 물리쳐야 합니다.";
            generic.FinishText = "모든 {{target}}를 소탕했습니다. 이제 지역은 다시 평온을 되찾았습니다.";
            generic.StoryQualityJson = "{\"totalScore\":100,\"structureScore\":15,\"koreanScore\":12,\"objectiveScore\":20,\"immersionScore\":15,\"narrativeScore\":12,\"presentationScore\":8,\"rebindabilityScore\":15,\"safetyScore\":15,\"diversityScore\":10,\"reasons\":[\"legacy_high_score\"]}";
            generic.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"불안한 부탁\",\"body\":\"지역 주민은 {{target}}의 흔적이 Albion 곳곳으로 번지고 있다고 말합니다. 아직 작은 소문처럼 들리지만, 방치하면 마을의 밤이 더 길어질 것입니다.\",\"journalEntry\":\"지역 주민에게서 {{target}} 위협이 커지고 있다는 이야기를 들었다.\",\"mood\":\"urgent\",\"revealPolicy\":\"FirstSeenOnly\"},{\"nodeId\":\"explore\",\"sceneType\":\"Discovery\",\"title\":\"흔적의 방향\",\"body\":\"흙과 풀잎 사이에 남은 {{target}}의 흔적이 한 방향으로 이어집니다. 주변은 조용하지만, 그 조용함이 오히려 다음 싸움을 예고합니다.\",\"journalEntry\":\"{{target}}의 흔적을 따라 위협의 중심에 가까워지고 있다.\",\"mood\":\"ominous\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            generic.StoryPresentationJson = "[{\"nodeId\":\"talk\",\"trigger\":\"OnNpcInteract\",\"speaker\":\"System\",\"text\":\"{{target}} 소식 때문에 모두가 조용히 문을 걸어 잠그고 있습니다.\",\"emotion\":\"fear\",\"emote\":\"Shiver\"}]";
            repository.Add(generic);
            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[]
            {
                new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Fail("no generation expected"))
            });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            options.UseStoryCacheOffers = true;
            options.MaxQuests = 2;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = false;

            DynamicQuestSeedSummary summary = service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-configured", 1),
                CreateNpc("forest spiderling", "target-cache", 1)
            }, options);

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.StoryCacheOffered, Is.EqualTo(0));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests().Select(quest => quest.TargetName), Does.Not.Contain("forest spiderling"));
                Assert.That(repository.Rows["story-cache-generic-scaffold-high-score"].LastBindingKey, Is.EqualTo(string.Empty));
            });
        }

        [Test]
        public void Seed_StoryCacheOffersUpgradeLegacyRowsWithoutPresentationMetadata()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate legacy = CreateStoryRow(
                "story-cache-legacy-empty-presentation",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-5));
            legacy.StoryQualityJson = "{\"totalScore\":100,\"safetyScore\":15,\"structureScore\":15}";
            legacy.StoryNarrativeJson = string.Empty;
            legacy.StoryPresentationJson = string.Empty;
            repository.Add(legacy);
            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[]
            {
                new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Fail("no generation expected"))
            });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            options.UseStoryCacheOffers = true;
            options.MaxQuests = 2;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = false;

            DynamicQuestSeedSummary summary = service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-configured", 1),
                CreateNpc("forest spiderling", "target-alb-cache", 1)
            }, options);

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(2));
                Assert.That(summary.StoryCacheOffered, Is.EqualTo(1));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests().Select(quest => quest.TargetName), Does.Contain("black wolf pup"));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests().Select(quest => quest.TargetName), Does.Contain("forest spiderling"));
                Assert.That(repository.Rows["story-cache-legacy-empty-presentation"].LastBindingKey, Is.Not.EqualTo(string.Empty));
                Assert.That(repository.Rows["story-cache-legacy-empty-presentation"].StoryNarrativeJson, Is.Not.EqualTo(string.Empty));
                Assert.That(repository.Rows["story-cache-legacy-empty-presentation"].StoryPresentationJson, Is.Not.EqualTo(string.Empty));
                Assert.That(repository.Rows["story-cache-legacy-empty-presentation"].TagsJson, Does.Contain("story-scaffold-upgraded"));
            });
        }

        [Test]
        public void Seed_StoryCacheOffersInterleaveNpcOfferAndNpcLessRowsAcrossStarterRealms()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-albion-npc-high",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                99,
                DateTime.UtcNow.AddHours(-1)));
            repository.Add(CreateStoryRow(
                "story-cache-midgard-npc-high",
                "Midgard",
                100,
                "young tomte",
                DynamicQuestStartMode.NpcOffer,
                98,
                DateTime.UtcNow.AddHours(-1)));
            repository.Add(CreateStoryRow(
                "story-cache-hibernia-npc-high",
                "Hibernia",
                200,
                "water beetle",
                DynamicQuestStartMode.NpcOffer,
                97,
                DateTime.UtcNow.AddHours(-1)));
            repository.Add(CreateStoryRow(
                "story-cache-albion-auto-lower",
                "Albion",
                1,
                "blackthorn sapling",
                DynamicQuestStartMode.AutoAccept,
                80,
                DateTime.UtcNow.AddHours(-2)));
            repository.Add(CreateStoryRow(
                "story-cache-midgard-auto-lower",
                "Midgard",
                100,
                "frostling scout",
                DynamicQuestStartMode.AutoAccept,
                79,
                DateTime.UtcNow.AddHours(-2)));
            repository.Add(CreateStoryRow(
                "story-cache-hibernia-auto-lower",
                "Hibernia",
                200,
                "bogling scout",
                DynamicQuestStartMode.AutoAccept,
                78,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[]
            {
                new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Fail("no generation expected"))
            });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                DynamicQuestSeedOptions.DefaultDeterministicDefinitions);
            options.UseLlm = true;
            options.UseStoryCacheOffers = true;
            options.MaxQuests = 6;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = false;

            DynamicQuestSeedSummary summary = service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30),
                CreateNpc("black wolf pup", "target-configured-alb", 1, x: 502000, y: 500000),
                CreateNpc("Aud", "seed-npc-100", 100, level: 30),
                CreateNpc("young sveawolf", "target-configured-mid", 100, x: 502000, y: 500000),
                CreateNpc("Ionhar", "seed-npc-200", 200, level: 30),
                CreateNpc("water beetle larva", "target-configured-hib", 200, x: 502000, y: 500000),
                CreateNpc("forest spiderling", "target-npc-cache-alb", 1),
                CreateNpc("young tomte", "target-npc-cache-mid", 100),
                CreateNpc("water beetle", "target-npc-cache-hib", 200),
                CreateNpc("blackthorn sapling", "target-auto-cache-alb", 1),
                CreateNpc("frostling scout", "target-auto-cache-mid", 100),
                CreateNpc("bogling scout", "target-auto-cache-hib", 200)
            }, options);

            DynamicQuestDefinition[] autoOffers = DynamicQuestRuntimeService.Instance.GetQuests()
                .Where(quest => quest.StartMode == DynamicQuestStartMode.AutoAccept)
                .OrderBy(quest => quest.StartRegionId)
                .ToArray();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(6));
                Assert.That(summary.StoryCacheOffered, Is.EqualTo(3));
                Assert.That(autoOffers.Select(quest => quest.StartRegionId), Does.Contain((ushort)1));
                Assert.That(autoOffers.Select(quest => quest.StartRegionId), Does.Contain((ushort)100));
                Assert.That(autoOffers.Select(quest => quest.StartRegionId), Does.Contain((ushort)200));
                Assert.That(autoOffers.Select(quest => quest.TargetName), Is.EquivalentTo(new[]
                {
                    "blackthorn sapling",
                    "frostling scout",
                    "bogling scout"
                }));
                Assert.That(repository.Rows["story-cache-albion-auto-lower"].LastBindingKey, Is.Not.Empty);
                Assert.That(repository.Rows["story-cache-midgard-auto-lower"].LastBindingKey, Is.Not.Empty);
                Assert.That(repository.Rows["story-cache-hibernia-auto-lower"].LastBindingKey, Is.Not.Empty);
                Assert.That(repository.Rows["story-cache-albion-npc-high"].LastBindingKey, Is.Empty);
                Assert.That(repository.Rows["story-cache-midgard-npc-high"].LastBindingKey, Is.Empty);
                Assert.That(repository.Rows["story-cache-hibernia-npc-high"].LastBindingKey, Is.Empty);
            });
        }

        [Test]
        public void Seed_StoryCacheOffersMissingNpcOfferRealmBeforeNpcLessFallback()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-albion-npc-backfill",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                90,
                DateTime.UtcNow.AddHours(-1)));
            repository.Add(CreateStoryRow(
                "story-cache-albion-auto-backfill",
                "Albion",
                1,
                "blackthorn sapling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|100|selector:hostile-near-start|1|1|5|NpcOffer||mob-growth:killed:region:100;" +
                "selector:town-npc|200|selector:hostile-near-start|1|1|5|NpcOffer||mob-growth:killed:region:200");
            options.UseLlm = true;
            options.UseStoryCacheOffers = true;
            options.MaxQuests = 3;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = false;

            DynamicQuestSeedSummary summary = service.Seed(new[]
            {
                CreateNpc("Aud", "seed-npc-100", 100, level: 30),
                CreateNpc("young sveawolf", "target-configured-mid", 100, x: 502000, y: 500000),
                CreateNpc("Ionhar", "seed-npc-200", 200, level: 30),
                CreateNpc("water beetle larva", "target-configured-hib", 200, x: 502000, y: 500000),
                CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30),
                CreateNpc("forest spiderling", "target-npc-cache-alb", 1),
                CreateNpc("blackthorn sapling", "target-auto-cache-alb", 1)
            }, options);

            DynamicQuestDefinition[] quests = DynamicQuestRuntimeService.Instance.GetQuests().ToArray();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(3));
                Assert.That(summary.StoryCacheOffered, Is.EqualTo(1));
                Assert.That(quests.Any(quest =>
                    quest.StartRegionId == 1 &&
                    quest.StartMode == DynamicQuestStartMode.NpcOffer &&
                    string.Equals(quest.TargetName, "forest spiderling", StringComparison.OrdinalIgnoreCase)), Is.True);
                Assert.That(quests.Any(quest =>
                    quest.StartRegionId == 1 &&
                    quest.StartMode == DynamicQuestStartMode.AutoAccept), Is.False);
                Assert.That(repository.Rows["story-cache-albion-npc-backfill"].LastBindingKey, Is.Not.Empty);
                Assert.That(repository.Rows["story-cache-albion-auto-backfill"].LastBindingKey, Is.Empty);
            });
        }

        [Test]
        public void Seed_StoryCacheMissingHintAutoAcceptFallsBackWithinSameStarterRealm()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-hibernia-auto-missing-target",
                "Hibernia",
                200,
                "missing bogling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-3)));
            repository.Add(CreateStoryRow(
                "story-cache-hibernia-auto-valid",
                "Hibernia",
                200,
                "bogling scout",
                DynamicQuestStartMode.AutoAccept,
                90,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[]
            {
                new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Fail("no generation expected"))
            });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5|NpcOffer|");
            options.UseLlm = true;
            options.UseStoryCacheOffers = true;
            options.MaxQuests = 2;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = false;

            DynamicQuestSeedSummary summary = service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30),
                CreateNpc("black wolf pup", "target-configured-alb", 1, x: 502000, y: 500000),
                CreateNpc("bogling scout", "target-auto-cache-hib", 200)
            }, options);

            DynamicQuestDefinition autoOffer = DynamicQuestRuntimeService.Instance.GetQuests()
                .Single(quest => quest.StartMode == DynamicQuestStartMode.AutoAccept);

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(2));
                Assert.That(summary.StoryCacheOffered, Is.EqualTo(1));
                Assert.That(summary.Skipped, Is.EqualTo(0));
                Assert.That(autoOffer.StartRegionId, Is.EqualTo((ushort)200));
                Assert.That(autoOffer.StartNpcName, Is.EqualTo(string.Empty));
                Assert.That(autoOffer.Tags, Does.Contain("realm:Hibernia"));
                Assert.That(autoOffer.Tags, Does.Contain("start-mode:AutoAccept"));
                Assert.That(autoOffer.TargetName, Is.EqualTo("bogling scout"));
                Assert.That(autoOffer.Nodes.Single(node => node.Type == DynamicQuestNodeType.Kill).Objective.RegionId, Is.EqualTo((ushort)200));
                Assert.That(repository.Rows["story-cache-hibernia-auto-missing-target"].LastBindingKey, Is.Not.Empty);
                Assert.That(repository.Rows["story-cache-hibernia-auto-valid"].LastBindingKey, Is.Empty);
            });
        }

        [Test]
        public void Seed_StoryCacheOffersPreferStarterLevelAutoAcceptRows()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate albionHigh = CreateStoryRow(
                "story-cache-albion-auto-high-level",
                "Albion",
                1,
                "albion waylayer",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1));
            DbDynamicQuestTemplate midgardHigh = CreateStoryRow(
                "story-cache-midgard-auto-high-level",
                "Midgard",
                100,
                "arcsinimpede drone",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1));
            DbDynamicQuestTemplate hiberniaHigh = CreateStoryRow(
                "story-cache-hibernia-auto-high-level",
                "Hibernia",
                200,
                "azure avenger",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1));
            foreach (DbDynamicQuestTemplate row in new[] { albionHigh, midgardHigh, hiberniaHigh })
            {
                row.MinLevel = 48;
                row.MaxLevel = 50;
                row.Count = 3;
                repository.Add(row);
            }

            repository.Add(CreateStoryRow(
                "story-cache-albion-auto-starter",
                "Albion",
                1,
                "ant drone",
                DynamicQuestStartMode.AutoAccept,
                80,
                DateTime.UtcNow.AddHours(-2)));
            repository.Add(CreateStoryRow(
                "story-cache-midgard-auto-starter",
                "Midgard",
                100,
                "arachite hatchling",
                DynamicQuestStartMode.AutoAccept,
                79,
                DateTime.UtcNow.AddHours(-2)));
            DbDynamicQuestTemplate hiberniaStarter = CreateStoryRow(
                "story-cache-hibernia-auto-starter",
                "Hibernia",
                200,
                "anger sprite",
                DynamicQuestStartMode.AutoAccept,
                78,
                DateTime.UtcNow.AddHours(-2));
            hiberniaStarter.MinLevel = 9;
            hiberniaStarter.MaxLevel = 13;
            hiberniaStarter.Count = 2;
            repository.Add(hiberniaStarter);
            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[]
            {
                new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Fail("no generation expected"))
            });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                DynamicQuestSeedOptions.DefaultDeterministicDefinitions);
            options.UseLlm = true;
            options.UseStoryCacheOffers = true;
            options.MaxQuests = 6;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = false;

            DynamicQuestSeedSummary summary = service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30),
                CreateNpc("black wolf pup", "target-configured-alb", 1, x: 502000, y: 500000),
                CreateNpc("Aud", "seed-npc-100", 100, level: 30),
                CreateNpc("young sveawolf", "target-configured-mid", 100, x: 502000, y: 500000),
                CreateNpc("Ionhar", "seed-npc-200", 200, level: 30),
                CreateNpc("water beetle larva", "target-configured-hib", 200, x: 502000, y: 500000),
                CreateNpc("albion waylayer", "target-high-alb", 1, level: 50),
                CreateNpc("arcsinimpede drone", "target-high-mid", 100, level: 50),
                CreateNpc("azure avenger", "target-high-hib", 200, level: 50),
                CreateNpc("ant drone", "target-starter-alb", 1, level: 2),
                CreateNpc("arachite hatchling", "target-starter-mid", 100, level: 2),
                CreateNpc("anger sprite", "target-starter-hib", 200, level: 11)
            }, options);

            DynamicQuestDefinition[] autoOffers = DynamicQuestRuntimeService.Instance.GetQuests()
                .Where(quest => quest.StartMode == DynamicQuestStartMode.AutoAccept)
                .OrderBy(quest => quest.StartRegionId)
                .ToArray();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(6));
                Assert.That(summary.StoryCacheOffered, Is.EqualTo(3));
                Assert.That(autoOffers.Select(quest => quest.TargetName), Is.EquivalentTo(new[]
                {
                    "ant drone",
                    "arachite hatchling",
                    "water beetle larva"
                }));
                Assert.That(autoOffers.All(quest =>
                    quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Kill).Objective.MaxLevel <= 2), Is.True);
                Assert.That(repository.Rows["story-cache-albion-auto-starter"].LastBindingKey, Is.Not.Empty);
                Assert.That(repository.Rows["story-cache-midgard-auto-starter"].LastBindingKey, Is.Not.Empty);
                Assert.That(repository.Rows["story-cache-hibernia-auto-starter"].LastBindingKey, Is.Not.Empty);
                Assert.That(repository.Rows["story-cache-albion-auto-high-level"].LastBindingKey, Is.Empty);
                Assert.That(repository.Rows["story-cache-midgard-auto-high-level"].LastBindingKey, Is.Empty);
                Assert.That(repository.Rows["story-cache-hibernia-auto-high-level"].LastBindingKey, Is.Empty);
            });
        }

        [Test]
        public void Seed_StoryCacheWaitsUntilGeminiDailyQuotaResetBeforePruningAndGenerating()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            FakeStoryProvider provider = new("main-local", DynamicQuestStoryGenerationResult.Ok(new DynamicQuestStoryText
            {
                Title = "새벽 이후의 의뢰",
                OfferText = "Brother Penric이 {{target}} 처치를 부탁합니다.",
                ProgressText = "{{target}}의 흔적을 따라가야 합니다.",
                FinishText = "{{target}} 위협이 사라졌습니다."
            }, "main-local"));
            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[] { provider });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedNpc target = CreateNpc("black wolf pup", "target-npc-1", 1);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_MAX_TEMPLATES = 2;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PRUNE_COUNT = 1;
            repository.Add(CreateStoryRow("story-low", 5, DateTime.UtcNow.AddDays(-3)));
            repository.Add(CreateStoryRow("story-high", 95, DateTime.UtcNow.AddDays(-2)));

            DynamicQuestSeedService.SetClockForTest(() => new DateTime(2026, 6, 3, 6, 59, 0, DateTimeKind.Utc));
            DynamicQuestSeedSummary beforeReset = service.Seed(new[] { npc, target }, options);
            DynamicQuestRuntimeService.Instance.ClearAll();
            DynamicQuestSeedService.SetClockForTest(() => new DateTime(2026, 6, 3, 7, 10, 0, DateTimeKind.Utc));
            DynamicQuestSeedSummary afterReset = service.Seed(new[] { npc, target }, options);

            Assert.Multiple(() =>
            {
                Assert.That(beforeReset.Created, Is.EqualTo(1));
                Assert.That(afterReset.Created, Is.EqualTo(1));
                Assert.That(repository.Rows["story-low"].IsActive, Is.False);
                Assert.That(repository.Rows["story-high"].IsActive, Is.True);
                Assert.That(provider.Calls, Is.EqualTo(1));
            });
        }

        [Test]
        public void Seed_StoryCacheCleanupRunsLaterSameDayWhenCacheBecomesFullAfterEarlierBelowLimit()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            FakeStoryProvider provider = new("main-local", DynamicQuestStoryGenerationResult.Ok(new DynamicQuestStoryText
            {
                Title = "리셋 이후의 의뢰",
                OfferText = "Brother Penric이 {{target}} 처치를 부탁합니다.",
                ProgressText = "{{target}}의 흔적을 따라가야 합니다.",
                FinishText = "{{target}} 위협이 사라졌습니다."
            }, "main-local"));
            DynamicQuestStoryService storyService = new(new IDynamicQuestStoryProvider[] { provider });
            DynamicQuestSeedService service = new(repository, storyService);
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedNpc target = CreateNpc("black wolf pup", "target-npc-1", 1);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_MAX_TEMPLATES = 3;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PRUNE_COUNT = 1;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE = 1;
            repository.Add(CreateStoryRow("story-high", 95, DateTime.UtcNow.AddDays(-2)));

            DynamicQuestSeedService.SetClockForTest(() => new DateTime(2026, 6, 3, 7, 20, 0, DateTimeKind.Utc));
            service.Seed(new[] { npc, target }, options);
            DbDynamicQuestTemplate low = CreateStoryRow("story-low", 5, DateTime.UtcNow.AddDays(-3));
            low.StoryNarrativeJson = string.Empty;
            low.StoryPresentationJson = string.Empty;
            repository.Add(low);
            DynamicQuestRuntimeService.Instance.ClearAll();
            service.Seed(new[] { npc, target }, options);

            Assert.Multiple(() =>
            {
                Assert.That(repository.Rows["story-low"].IsActive, Is.False);
                Assert.That(repository.Rows["story-high"].IsActive, Is.True);
            });
        }

        [Test]
        public void StoryCacheSnapshot_ReadsScoredTemplatesAndBranchTagsWithoutMutation()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-high-branch",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                94,
                DateTime.UtcNow.AddHours(-3)));
            repository.Add(CreateStoryRow("story-low", 12, DateTime.UtcNow.AddDays(-2)));
            repository.Rows["story-high-branch"].TagsJson = "[\"llm-story\",\"branch:mob-growth\",\"world-signal:mob-growth:killed:region:1\"]";
            repository.Rows["story-high-branch"].OfferText = "{{target}} 위협이 커지고 있습니다.";
            repository.Rows["story-high-branch"].StoryQualityJson = "{\"totalScore\":94,\"safetyScore\":20,\"structureScore\":19,\"narrativeScore\":10,\"presentationScore\":10}";
            repository.Rows["story-high-branch"].StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"숲의 숨죽임\",\"body\":\"숨겨야 할 긴 본문\",\"journalEntry\":\"숨겨야 할 저널\",\"mood\":\"ominous\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            repository.Rows["story-high-branch"].StoryPresentationJson = "[{\"nodeId\":\"talk\",\"trigger\":\"OnNpcInteract\",\"speaker\":\"StartNpc\",\"text\":\"숨겨야 할 대사\",\"emotion\":\"fear\",\"emote\":\"Shiver\"}]";
            repository.Rows["story-low"].StoryProvider = "gemini";
            repository.Rows["story-low"].StoryModel = "gemini-3.5-flash";
            repository.Add(new DbDynamicQuestTemplate
            {
                TemplateId = "non-story-active-row",
                Title = "일반 템플릿",
                TagsJson = "[\"starter\"]",
                IsActive = true,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow
            });
            int addCalls = repository.AddCalls;
            int saveCalls = repository.SaveCalls;
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem branch = snapshot.Items.Single(item => item.TemplateId == "story-high-branch");
            DynamicQuestStoryCacheItem low = snapshot.Items.Single(item => item.TemplateId == "story-low");

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.TotalActive, Is.EqualTo(2));
                Assert.That(snapshot.Returned, Is.EqualTo(2));
                Assert.That(snapshot.Items.Select(item => item.TemplateId), Is.EqualTo(new[] { "story-high-branch", "story-low" }));
                Assert.That(snapshot.ByProvider["main-local"], Is.EqualTo(1));
                Assert.That(snapshot.ByProvider["gemini"], Is.EqualTo(1));
                Assert.That(snapshot.ByRealm["Albion"], Is.EqualTo(2));
                Assert.That(branch.BranchWorldSignal, Is.EqualTo("mob-growth:killed:region:1"));
                Assert.That(branch.Tags, Does.Contain("branch:mob-growth"));
                Assert.That(branch.StartMode, Is.EqualTo(DynamicQuestStartMode.AutoAccept.ToString()));
                Assert.That(branch.OfferText, Is.EqualTo(string.Empty));
                Assert.That(branch.Quality.TotalScore, Is.EqualTo(94));
                Assert.That(branch.Quality.SafetyScore, Is.EqualTo(20));
                Assert.That(branch.NarrativeScenes.Single().Title, Is.EqualTo("숲의 숨죽임"));
                Assert.That(branch.NarrativeScenes.Single().Body, Is.EqualTo(string.Empty));
                Assert.That(branch.NarrativeScenes.Single().JournalEntry, Is.EqualTo(string.Empty));
                Assert.That(branch.PresentationBeats.Single().Emotion, Is.EqualTo("fear"));
                Assert.That(branch.PresentationBeats.Single().Emote, Is.EqualTo("Shiver"));
                Assert.That(branch.PresentationBeats.Single().Text, Is.EqualTo(string.Empty));
                Assert.That(branch.CurrentQuality.TotalScore, Is.LessThanOrEqualTo(low.CurrentQuality.TotalScore));
                Assert.That(low.StoryModel, Is.EqualTo("gemini-3.5-flash"));
                Assert.That(snapshot.Items.Select(item => item.TemplateId), Does.Not.Contain("non-story-active-row"));
                Assert.That(repository.AddCalls, Is.EqualTo(addCalls));
                Assert.That(repository.SaveCalls, Is.EqualTo(saveCalls));
                Assert.That(repository.Rows["story-high-branch"].LastBindingKey, Is.EqualTo(string.Empty));
            });
        }

        [Test]
        public void StoryCacheSnapshot_ReevaluatesLegacyQualityAgainstCurrentGate()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate legacy = CreateStoryRow(
                "story-cache-legacy-generic",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                100,
                DateTime.UtcNow.AddDays(-1));
            legacy.Title = "지역 분위기의 불길한 전조";
            legacy.StoryQualityScore = 100;
            legacy.StoryQualityJson = "{\"totalScore\":100,\"structureScore\":15,\"koreanScore\":12,\"objectiveScore\":20,\"immersionScore\":15,\"narrativeScore\":12,\"presentationScore\":8,\"rebindabilityScore\":15,\"safetyScore\":15,\"diversityScore\":10,\"reasons\":[\"narrative_scene\",\"presentation_beat\"]}";
            legacy.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"불안한 부탁\",\"body\":\"지역 주민은 {{target}}의 흔적이 Albion 곳곳으로 번지고 있다고 말합니다. 아직 작은 소문처럼 들리지만, 방치하면 마을의 밤이 더 길어질 것입니다.\",\"journalEntry\":\"지역 주민에게서 {{target}} 위협이 커지고 있다는 이야기를 들었다.\",\"mood\":\"urgent\",\"revealPolicy\":\"FirstSeenOnly\"},{\"nodeId\":\"explore\",\"sceneType\":\"Discovery\",\"title\":\"흔적의 방향\",\"body\":\"흙과 풀잎 사이에 남은 {{target}}의 흔적이 한 방향으로 이어집니다.\",\"journalEntry\":\"{{target}}의 흔적을 따라 위협의 중심에 가까워지고 있다.\",\"mood\":\"ominous\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            legacy.StoryPresentationJson = "[{\"nodeId\":\"talk\",\"trigger\":\"OnNpcInteract\",\"speaker\":\"StartNpc\",\"text\":\"{{target}} 소식 때문에 모두가 조용히 문을 걸어 잠그고 있습니다.\",\"emotion\":\"fear\",\"emote\":\"Shiver\"},{\"nodeId\":\"complete\",\"trigger\":\"OnComplete\",\"speaker\":\"StartNpc\",\"text\":\"이제야 숨을 쉴 수 있겠군요. 고맙습니다.\",\"emotion\":\"gratitude\",\"emote\":\"Bow\"}]";
            repository.Add(legacy);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single();

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.ReadyActive, Is.EqualTo(0));
                Assert.That(snapshot.NotReadyByReason["generic_scaffold"], Is.EqualTo(1));
                Assert.That(snapshot.NotReadyByReason["missing_specific_local_anchor"], Is.EqualTo(1));
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Not.Contain("narrative_scene"));
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Not.Contain("presentation_beat"));
                Assert.That(item.StoryQualityScore, Is.EqualTo(100));
                Assert.That(item.Quality.TotalScore, Is.EqualTo(100));
                Assert.That(item.ReadyForUse, Is.False);
                Assert.That(item.CurrentQuality.TotalScore, Is.LessThan(75));
                Assert.That(item.CurrentQuality.Reasons, Does.Contain("generic_scaffold"));
            });
        }

        [Test]
        public void TemplateBind_StarterTagWithHigherLevelRangeAvoidsGrowthTarget()
        {
            DynamicQuestTemplateService service = new();
            DynamicQuestTemplate template = new()
            {
                TemplateId = "starter-story-higher-range",
                Title = "{{target}} 흔적",
                OfferText = "{{start_npc}}이 {{target}} 조사를 부탁합니다.",
                ProgressText = "{{target}} 위협을 제압하십시오.",
                FinishText = "{{target}} 위협이 사라졌습니다.",
                PreferredStartNpcName = "Brother Penric",
                PreferredRegionId = 1,
                TargetNameHint = "bogman grappler",
                Count = 1,
                MinLevel = 6,
                MaxLevel = 8,
                StartMode = DynamicQuestStartMode.NpcOffer,
                Tags = new[] { "starter", "llm-story" }
            };
            DynamicQuestSeedNpc startNpc = CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30, x: 500000, y: 500000);
            DynamicQuestSeedNpc unsafeGrowthTarget = CreateNpc(
                "노련한 bogman grappler",
                "target-growth",
                1,
                level: 6,
                x: 508000,
                y: 506000,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.None);
            DynamicQuestSeedNpc safeTarget = CreateNpc(
                "muck snake",
                "target-safe",
                1,
                level: 1,
                x: 502500,
                y: 500200,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.None);

            DynamicQuestTemplateBindingResult result = service.BindTemplate(
                template,
                new[] { startNpc, unsafeGrowthTarget, safeTarget });

            Assert.That(result.Success, Is.True, result.Message);
            Assert.That(result.Quest.TargetName, Is.EqualTo("muck snake"));
            Assert.That(result.Quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Kill).Objective.MaxLevel, Is.EqualTo(1));
        }

        [Test]
        public void ProgressSnapshot_ReadsActiveProgressWithoutMutation()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(new DynamicQuestDefinition
            {
                Id = "quest-1",
                Title = "검은 늑대 새끼 처치",
                OfferText = "도와주겠습니까?",
                ProgressText = "검은 늑대 새끼를 처치하세요.",
                FinishText = "고맙습니다.",
                StartNpcInternalId = "seed-npc-1",
                StartNpcName = "Brother Penric",
                StartRegionId = 1,
                TargetName = "black wolf pup",
                TargetCount = 2,
                MinLevel = 1,
                MaxLevel = 5
            });
            DynamicQuestRuntimeService.Instance.RecordProgressForTest("DummyQuest001", "quest-1", 1, false);

            DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.Player, Is.EqualTo("DummyQuest001"));
                Assert.That(snapshot.Online, Is.True);
                Assert.That(snapshot.Active, Has.Count.EqualTo(1));
                Assert.That(snapshot.Active.Single().QuestId, Is.EqualTo("quest-1"));
                Assert.That(snapshot.Active.Single().Count, Is.EqualTo(1));
                Assert.That(snapshot.Active.Single().IsComplete, Is.False);
                Assert.That(DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active, Has.Count.EqualTo(1));
            });
        }

        private static DynamicQuestSeedNpc CreateNpc(
            string name,
            string internalId,
            ushort regionId,
            int level = 1,
            int x = 500000,
            int y = 500000,
            int z = 3000,
            bool hasSourceNpcMetadata = false,
            eRealm sourceRealm = eRealm.None,
            GameNPC.eFlags sourceFlags = 0,
            bool sourceIsAlive = true,
            string sourceTypeName = "",
            int sourceAggroLevel = 0,
            int sourceAggroRange = 0)
        {
            return new DynamicQuestSeedNpc
            {
                Name = name,
                InternalID = internalId,
                RegionId = regionId,
                Level = level,
                X = x,
                Y = y,
                Z = z,
                HasSourceNpcMetadata = hasSourceNpcMetadata,
                SourceRealm = sourceRealm,
                SourceFlags = sourceFlags,
                SourceIsAlive = sourceIsAlive,
                SourceTypeName = sourceTypeName,
                SourceAggroLevel = sourceAggroLevel,
                SourceAggroRange = sourceAggroRange
            };
        }

        private static DynamicQuestSeedNpc CreateGrowthNpc(
            string name,
            string internalId,
            ushort regionId,
            int level,
            int effectiveLevel)
        {
            DynamicQuestSeedNpc npc = CreateNpc(
                name,
                internalId,
                regionId,
                level,
                hasSourceNpcMetadata: true,
                sourceRealm: eRealm.None);
            npc.HasGrowthState = true;
            npc.GrowthStage = MobGrowthStages.Elite;
            npc.GrowthScore = 80;
            npc.GrowthLevel = Math.Max(1, effectiveLevel - level);
            npc.GrowthEffectiveLevel = effectiveLevel;
            return npc;
        }

        private static DbDynamicQuestTemplate CreateStoryRow(string templateId, int score, DateTime lastUsedAt)
        {
            return CreateStoryRow(
                templateId,
                "Albion",
                1,
                "black wolf pup",
                DynamicQuestStartMode.NpcOffer,
                score,
                lastUsedAt);
        }

        private static DbDynamicQuestTemplate CreateStoryRow(
            string templateId,
            string realm,
            ushort regionId,
            string targetName,
            DynamicQuestStartMode startMode,
            int score,
            DateTime lastUsedAt)
        {
            return new DbDynamicQuestTemplate
            {
                TemplateId = templateId,
                Title = templateId,
                OfferText = "{{target}} 처치 요청",
                ProgressText = "{{target}} 추적 중",
                FinishText = "{{target}} 처치 완료",
                Realm = realm,
                PreferredStartNpcName = "Brother Penric",
                PreferredRegionId = regionId,
                TargetNameHint = targetName,
                Count = 1,
                MinLevel = 1,
                MaxLevel = 5,
                Source = "llm",
                TagsJson = "[\"llm-story\"]",
                StoryProvider = "main-local",
                StoryModel = "gemma-test",
                StoryQualityScore = score,
                StoryQualityJson = "{\"totalScore\":90,\"structureScore\":15,\"koreanScore\":12,\"objectiveScore\":20,\"immersionScore\":15,\"narrativeScore\":12,\"presentationScore\":8,\"rebindabilityScore\":15,\"safetyScore\":15,\"diversityScore\":10,\"reasons\":[\"narrative_scene\",\"presentation_beat\"]}",
                StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"수도원 길목의 경고\",\"body\":\"{{start_npc}}은 {{realm}} 수도원 길목에서 발견된 찢긴 짐가방을 보여 주며 {{target}} 위협이 통행로를 막기 시작했다고 말합니다.\",\"journalEntry\":\"{{start_npc}}에게서 {{realm}} 수도원 길목의 {{target}} 위협을 조사해 달라는 부탁을 받았다.\",\"mood\":\"urgent\",\"revealPolicy\":\"FirstSeenOnly\"}]",
                StoryPresentationJson = "[{\"nodeId\":\"talk\",\"trigger\":\"OnNpcInteract\",\"speaker\":\"StartNpc\",\"text\":\"수도원 길목에서 돌아오지 못한 이들이 있습니다. {{target}}를 막아 주십시오.\",\"emotion\":\"fear\",\"emote\":\"Shiver\"}]",
                StoryGeneratedAt = lastUsedAt.AddMinutes(-10),
                StoryLastUsedAt = lastUsedAt,
                StartMode = startMode.ToString(),
                IsActive = true,
                CreatedAt = lastUsedAt,
                UpdatedAt = lastUsedAt
            };
        }

        private sealed class FakeStoryProvider : IDynamicQuestStoryProvider
        {
            private readonly DynamicQuestStoryGenerationResult m_result;

            public FakeStoryProvider(string name, DynamicQuestStoryGenerationResult result, string modelName = "")
            {
                Name = name;
                ModelName = modelName;
                m_result = result;
            }

            public string Name { get; }
            public string ModelName { get; }
            public int Calls { get; private set; }

            public DynamicQuestStoryGenerationResult TryGenerate(DynamicQuestStoryRequest request)
            {
                Calls++;
                if (!m_result.Success || m_result.Story == null)
                    return m_result;

                return DynamicQuestStoryGenerationResult.Ok(WithRequiredPresentation(m_result.Story, request), m_result.ProviderName, m_result.ModelName);
            }
        }

        private sealed class RawStoryProvider : IDynamicQuestStoryProvider
        {
            private readonly DynamicQuestStoryGenerationResult m_result;

            public RawStoryProvider(string name, DynamicQuestStoryGenerationResult result, string modelName = "")
            {
                Name = name;
                ModelName = modelName;
                m_result = result;
            }

            public string Name { get; }
            public string ModelName { get; }

            public DynamicQuestStoryGenerationResult TryGenerate(DynamicQuestStoryRequest request)
            {
                return m_result;
            }
        }

        private static DynamicQuestStoryText WithRequiredPresentation(DynamicQuestStoryText story, DynamicQuestStoryRequest request)
        {
            string realm = string.IsNullOrWhiteSpace(request?.Realm) ? "Unknown" : request.Realm;
            string startName = string.IsNullOrWhiteSpace(request?.StartNpcName)
                ? "현장 정찰병"
                : "{{start_npc}}";
            string realmName = string.Equals(realm, "Unknown", StringComparison.OrdinalIgnoreCase)
                ? "마을 외곽"
                : "{{realm}}";
            string texture = RealmTextureForFakeStory(realm);
            IList<DynamicQuestNarrativeScene> scenes = story.NarrativeScenes == null || story.NarrativeScenes.Count == 0
                ? new[]
                {
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "talk",
                        SceneType = "Intro",
                        Title = $"{texture}의 첫 흔적",
                        Body = $"{startName}은 {realmName} {texture}에서 발견된 찢긴 짐가방을 보여 주며 {{target}}의 흔적이 통행로까지 번지고 있다고 말합니다. 공포가 커지기 전에 위협을 꺾어야 합니다.",
                        JournalEntry = $"{startName}에게서 {texture}의 {{target}} 위협을 조사해 달라는 이야기를 들었다.",
                        Mood = "urgent",
                        RevealPolicy = "FirstSeenOnly"
                    }
                }
                : story.NarrativeScenes
                    .Select(scene => new DynamicQuestNarrativeScene
                    {
                        NodeId = scene.NodeId,
                        SceneType = scene.SceneType,
                        Title = LocalizeFakeStoryField(scene.Title, request, texture),
                        Body = LocalizeFakeStoryField(scene.Body, request, texture),
                        JournalEntry = LocalizeFakeStoryField(scene.JournalEntry, request, texture),
                        Mood = scene.Mood,
                        RevealPolicy = scene.RevealPolicy
                    })
                    .ToList();
            IList<DynamicQuestPresentationBeat> beats = story.PresentationBeats == null || story.PresentationBeats.Count == 0
                ? new[]
                {
                    new DynamicQuestPresentationBeat
                    {
                        NodeId = "talk",
                        Trigger = "OnNpcInteract",
                        Speaker = "StartNpc",
                        Text = $"{texture}에서 {{target}} 소식 때문에 사람들이 밤마다 잠을 설치고 있습니다.",
                        Emotion = "fear",
                        Emote = "Shiver"
                    }
                }
                : story.PresentationBeats
                    .Select(beat => new DynamicQuestPresentationBeat
                    {
                        NodeId = beat.NodeId,
                        Trigger = beat.Trigger,
                        Speaker = beat.Speaker,
                        Text = LocalizeFakeStoryField(beat.Text, request, texture),
                        Emotion = beat.Emotion,
                        Emote = beat.Emote
                    })
                    .ToList();

            return new DynamicQuestStoryText
            {
                Title = LocalizeFakeStoryField(story.Title, request, texture),
                OfferText = LocalizeFakeStoryField(story.OfferText, request, texture),
                ProgressText = LocalizeFakeStoryField(story.ProgressText, request, texture),
                FinishText = LocalizeFakeStoryField(story.FinishText, request, texture),
                QualityScore = story.QualityScore,
                Quality = story.Quality,
                NarrativeScenes = scenes,
                PresentationBeats = beats
            };
        }

        private static string LocalizeFakeStoryField(string value, DynamicQuestStoryRequest request, string texture)
        {
            string text = value ?? string.Empty;
            if (!string.IsNullOrWhiteSpace(request?.StartNpcName))
                text = text.Replace(request.StartNpcName, "{{start_npc}}", StringComparison.OrdinalIgnoreCase);
            if (!string.IsNullOrWhiteSpace(request?.Realm))
                text = text.Replace(request.Realm, "{{realm}}", StringComparison.OrdinalIgnoreCase);
            if (!string.IsNullOrWhiteSpace(request?.TargetName))
                text = text.Replace(request.TargetName, "{{target}}", StringComparison.OrdinalIgnoreCase);
            if (!string.IsNullOrWhiteSpace(texture) && !text.Contains(texture, StringComparison.OrdinalIgnoreCase))
                text = $"{texture}: {text}";
            return text;
        }

        private static string RealmTextureForFakeStory(string realm)
        {
            if (string.Equals(realm, "Albion", StringComparison.OrdinalIgnoreCase))
                return "수도원 길목";
            if (string.Equals(realm, "Midgard", StringComparison.OrdinalIgnoreCase))
                return "롱하우스 바깥 눈길";
            if (string.Equals(realm, "Hibernia", StringComparison.OrdinalIgnoreCase))
                return "고리석 숲길";
            return "마을 외곽 길목";
        }
    }
}
