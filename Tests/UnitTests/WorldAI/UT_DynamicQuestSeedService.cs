using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text.Json;
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
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = false;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_GEMINI_RESET_DELAY_MINUTES = 10;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_GEMINI_RESET_WINDOW_MINUTES = 360;
            Properties.WORLDAI_MOB_GROWTH_ENABLED = false;
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
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = false;
            Properties.WORLDAI_MOB_GROWTH_ENABLED = false;
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
                Assert.That(explore.LocationName, Is.EqualTo("'black wolf pup'의 흔적"));
                Assert.That(explore.RegionId, Is.EqualTo(1));
                Assert.That(explore.X, Is.EqualTo(502100));
                Assert.That(explore.Y, Is.EqualTo(500800));
                Assert.That(explore.Z, Is.EqualTo(2954));
                Assert.That(explore.Radius, Is.EqualTo(450));
                DynamicQuestObjective kill = quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Kill).Objective;
                Assert.That(kill.AllowGroupCredit, Is.True);
                Assert.That(kill.X, Is.EqualTo(502100));
                Assert.That(kill.Y, Is.EqualTo(500800));
                Assert.That(kill.Z, Is.EqualTo(2954));
                Assert.That(kill.Radius, Is.EqualTo(6500));
                Assert.That(quest.Tags, Does.Contain("realm:Albion"));
                Assert.That(quest.Tags, Does.Contain("starter"));
                Assert.That(quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Choice).Objective.Choices.Select(choice => choice.Id),
                    Is.EqualTo(new[] { "safe", "followup" }));
            });
        }

        [Test]
        public void Seed_HigherLevelAutoDefinitionDoesNotTagQuestAsStarter()
        {
            DynamicQuestSeedService service = new();
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30);
            DynamicQuestSeedNpc target = CreateNpc("albion waylayer", "target-high", 1, level: 42, x: 503000, y: 501000, z: 2954);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|albion waylayer|2|40|44");

            DynamicQuestSeedSummary summary = service.Seed(new[] { npc, target }, options);

            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();
            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(quest.MinLevel, Is.EqualTo(40));
                Assert.That(quest.MaxLevel, Is.EqualTo(44));
                Assert.That(quest.TargetName, Is.EqualTo("albion waylayer"));
                Assert.That(quest.Tags, Does.Not.Contain("starter"));
                Assert.That(quest.Tags, Does.Contain("realm:Albion"));
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
            Properties.WORLDAI_MOB_GROWTH_ENABLED = true;
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
            Properties.WORLDAI_MOB_GROWTH_ENABLED = true;
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
        public void Seed_SelectorRebindsCachedScaffoldStoryTitleToCuratedTitle()
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
                Assert.That(quest.Title, Does.Contain("수도원 길목"));
                Assert.That(quest.Title, Does.Not.Contain("처치 요청"));
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
                Assert.That(quest.Tags, Does.Contain("story-cinematic"));
                Assert.That(quest.Tags, Does.Contain("scene-director"));
                Assert.That(quest.Tags, Does.Contain("cinematic-actors:ambush_reveal:8"));
                Assert.That(quest.Tags, Does.Not.Contain("llm-ready"));
                Assert.That(quest.Tags.Any(tag => tag.StartsWith("llm-score:", StringComparison.OrdinalIgnoreCase)), Is.False);
                Assert.That(quest.StoryNarrativeJson, Is.Not.Empty);
                Assert.That(quest.StoryPresentationJson, Is.Not.Empty);
            });
        }

        [Test]
        public void Seed_CodexCuratedStoriesBindAndStoreStoryCacheWhenLlmDisabled()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            FakeStoryProvider provider = new("main-local", DynamicQuestStoryGenerationResult.Fail("should-not-call"));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(new IDynamicQuestStoryProvider[] { provider }));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Ionhar|200|water beetle larva|1|1|5|NpcOffer||item-acquired");
            options.UseLlm = false;
            options.UseCodexCuratedStories = true;

            DynamicQuestSeedSummary summary = service.Seed(new[]
            {
                CreateNpc("Ionhar", "seed-npc-1", 200),
                CreateNpc("water beetle larva", "target-npc-1", 200, x: 502100, y: 500800, z: 2954)
            }, options);

            DynamicQuestDefinition quest = DynamicQuestRuntimeService.Instance.GetQuests().Single();
            DbDynamicQuestTemplate row = repository.GetActive().Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(provider.Calls, Is.EqualTo(0));
                Assert.That(row.StoryProvider, Is.EqualTo("codex-curated"));
                Assert.That(row.StoryModel, Is.EqualTo("hand-authored-cinematic-v15"));
                Assert.That(row.StoryQualityScore, Is.GreaterThanOrEqualTo(95));
                Assert.That(row.StoryQualityJson, Does.Not.Contain("generic_repetition"));
                Assert.That(row.Title, Does.Not.Contain("처치 요청"));
                Assert.That(row.Title, Does.Not.Contain("{{target}}"));
                Assert.That(row.OfferText, Does.Contain("단순한 사냥 의뢰가 아니다"));
                Assert.That(row.StoryNarrativeJson, Does.Contain("observe_signal"));
                Assert.That(row.StoryNarrativeJson, Does.Contain("의식 표식"));
                Assert.That(row.StoryNarrativeJson, Does.Contain("매복"));
                Assert.That(row.StoryNarrativeJson, Does.Contain("다시 반응"));
                Assert.That(row.StoryNarrativeJson, Does.Contain("목격자"));
                Assert.That(row.StoryPresentationJson, Does.Contain("OnWorldSignal"));
                Assert.That(row.StoryPresentationJson, Does.Contain("선택한 이유까지 기록"));
                Assert.That(row.StoryPresentationJson, Does.Contain("마을 안전"));
                Assert.That(row.StoryPresentationJson, Does.Contain("더 큰 위협"));
                Assert.That(row.StoryPresentationJson.Contains("우연한 단서가 아닙니다", StringComparison.OrdinalIgnoreCase) ||
                            row.StoryPresentationJson.Contains("결박끈의 매듭", StringComparison.OrdinalIgnoreCase) ||
                            row.StoryPresentationJson.Contains("다음 방향을 가리킵니다", StringComparison.OrdinalIgnoreCase), Is.True);
                Assert.That(row.StoryPresentationJson.Contains("탈출 경로를 가로막", StringComparison.OrdinalIgnoreCase) ||
                            row.StoryPresentationJson.Contains("방패선", StringComparison.OrdinalIgnoreCase) ||
                            row.StoryPresentationJson.Contains("구출 통로", StringComparison.OrdinalIgnoreCase), Is.True);
                Assert.That(row.StoryPresentationJson, Does.Contain("cinematicAction"));
                Assert.That(row.StoryPresentationJson, Does.Contain("ambush_reveal"));
                Assert.That(row.StoryPresentationJson, Does.Contain("combat_stance"));
                Assert.That(row.StoryPresentationJson, Does.Contain("hold_ground"));
                Assert.That(row.StoryPresentationJson, Does.Contain("actorCount"));
                Assert.That(row.StoryPresentationJson, Does.Contain("\"actorCount\":100"));
                Assert.That(row.StoryPresentationJson, Does.Contain("delayMs"));
                Assert.That(row.StoryPresentationJson, Does.Not.Contain("현장의 목격자은"));
                Assert.That(row.StoryNarrativeJson, Does.Not.Match("'[A-Za-z][^']*'[이가은는을를와과]"));
                Assert.That(row.StoryNarrativeJson, Does.Not.Match("'[A-Za-z][^']*'(로|으로)"));
                Assert.That(row.StoryNarrativeJson, Does.Not.Match("[A-Za-z][A-Za-z ]{2,}의"));
                Assert.That(row.StoryPresentationJson, Does.Not.Match("'[A-Za-z][^']*'[이가은는을를와과]"));
                Assert.That(row.StoryPresentationJson, Does.Not.Match("'[A-Za-z][^']*'(로|으로)"));
                Assert.That(row.StoryPresentationJson, Does.Not.Match("[A-Za-z][A-Za-z ]{2,}의"));
                Assert.That(quest.Tags, Does.Contain("codex-curated"));
                Assert.That(quest.Tags.Any(tag => tag.StartsWith("story-archetype:", StringComparison.OrdinalIgnoreCase)), Is.True);
                Assert.That(quest.Tags, Does.Contain("story-cinematic"));
                Assert.That(quest.Tags, Does.Contain("scene-director"));
                Assert.That(quest.Tags, Does.Contain("story-title-variant:v3"));
                Assert.That(quest.Tags, Does.Contain("story-arc:motive"));
                Assert.That(quest.Tags, Does.Contain("story-arc:conflict"));
                Assert.That(quest.Tags, Does.Contain("story-arc:reversal"));
                Assert.That(quest.Tags, Does.Contain("story-arc:consequence"));
                Assert.That(quest.Tags, Does.Contain("mass-cinematic"));
                Assert.That(quest.Tags, Does.Contain("cinematic-actors:ambush_reveal:8"));
                Assert.That(quest.Tags, Does.Contain("cinematic-actors:ambush_reveal:100"));
                Assert.That(quest.Tags, Does.Contain("cinematic-actors:defender_intercept:6"));
                Assert.That(quest.Tags, Does.Contain("cinematic-actors:defender_intercept:32"));
                Assert.That(quest.Tags, Does.Contain("cinematic-actors:ritual_interrupt:5"));
                Assert.That(quest.Tags, Does.Contain("cinematic-actors:ritual_interrupt:40"));
                Assert.That(quest.Tags, Does.Contain("cinematic-actors:scout_retreat:3"));
                Assert.That(quest.Tags, Does.Contain("cinematic-actors:guard_advance:4"));
                Assert.That(quest.Tags, Does.Contain("cinematic-actors:combat_stance:5"));
                Assert.That(quest.Tags, Does.Contain("cinematic-actors:hold_ground:4"));
                Assert.That(quest.StoryNarrativeJson, Does.Contain("고리석 숲길"));
                Assert.That(quest.StoryPresentationJson, Does.Contain("OnChoiceSelected"));
            });

            using JsonDocument presentation = JsonDocument.Parse(row.StoryPresentationJson);
            JsonElement ambushBeat = presentation.RootElement.EnumerateArray()
                .Single(element => element.GetProperty("cinematicAction").GetString() == "ambush_reveal");
            Assert.Multiple(() =>
            {
                Assert.That(ambushBeat.GetProperty("emotion").GetString(), Is.EqualTo("urgency"));
                Assert.That(ambushBeat.GetProperty("emote").GetString(), Is.EqualTo("Point"));
            });
        }

        [Test]
        public void PrefillStoryCache_CodexCuratedStoriesWorkWhenLlmDisabled()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            FakeStoryProvider provider = new("main-local", DynamicQuestStoryGenerationResult.Fail("should-not-call"));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(new IDynamicQuestStoryProvider[] { provider }));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = false;
            options.UseCodexCuratedStories = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE = 1;

            DynamicQuestSeedSummary summary = service.PrefillStoryCache(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-npc-1", 1, x: 502100, y: 500800, z: 2954)
            }, options);

            DbDynamicQuestTemplate row = repository.GetActive().Single();
            Assert.Multiple(() =>
            {
                Assert.That(summary.StoryCachePrefilled, Is.EqualTo(1));
                Assert.That(summary.StoryCachePrefillAttempted, Is.EqualTo(1));
                Assert.That(provider.Calls, Is.EqualTo(0));
                Assert.That(row.StoryProvider, Is.EqualTo("codex-curated"));
                Assert.That(row.StoryPresentationJson, Does.Contain("OnAccept"));
                Assert.That(row.StoryNarrativeJson, Does.Contain("수도원 길목"));
            });
        }

        [Test]
        public void PrefillStoryCache_SkipsAutoAcceptTargetWithDummyDifficultyHistory()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate failed = CreateStoryRow(
                "story-cache-albion-auto-forest-spiderling-failed",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-2));
            failed.DummyEvaluationCount = 1;
            failed.DummyEvaluationScore = 100;
            failed.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":false,\"completed\":false,\"players\":1,\"okPlayers\":0,\"playerDeaths\":1,\"failureCategory\":\"dummy_difficulty\"}";
            repository.Add(failed);

            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "|1|forest spiderling|1|1|5|AutoAccept|region:1");
            options.UseLlm = false;
            options.UseCodexCuratedStories = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE = 1;

            DynamicQuestSeedSummary summary = service.PrefillStoryCache(new[]
            {
                CreateNpc("forest spiderling", "target-npc-1", 1, level: 3, x: 522000, y: 492000, z: 2954)
            }, options);

            Assert.Multiple(() =>
            {
                Assert.That(summary.StoryCachePrefilled, Is.EqualTo(0));
                Assert.That(summary.StoryCachePrefillAttempted, Is.EqualTo(0));
                Assert.That(summary.StoryCachePrefillResolveSkipped, Is.EqualTo(1));
                Assert.That(repository.Rows, Has.Count.EqualTo(1));
                Assert.That(repository.Rows["story-cache-albion-auto-forest-spiderling-failed"].DummyEvaluationJson, Does.Contain("dummy_difficulty"));
            });
        }

        [Test]
        public void PrefillStoryCache_SkipsRelatedAutoAcceptTargetFamilyWithDummyDifficultyHistory()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate failed = CreateStoryRow(
                "story-cache-albion-auto-arachite-failed",
                "Albion",
                1,
                "arachite warrior",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-2));
            failed.DummyEvaluationCount = 1;
            failed.DummyEvaluationScore = 100;
            failed.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":false,\"completed\":false,\"players\":1,\"okPlayers\":0,\"playerDeaths\":1,\"failureCategory\":\"dummy_difficulty\"}";
            repository.Add(failed);

            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "|1|arachite krigare|1|35|39|AutoAccept|region:1");
            options.UseLlm = false;
            options.UseCodexCuratedStories = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE = 1;

            DynamicQuestSeedSummary summary = service.PrefillStoryCache(new[]
            {
                CreateNpc("arachite krigare", "target-npc-1", 1, level: 37, x: 522000, y: 492000, z: 2954)
            }, options);

            Assert.Multiple(() =>
            {
                Assert.That(summary.StoryCachePrefilled, Is.EqualTo(0));
                Assert.That(summary.StoryCachePrefillAttempted, Is.EqualTo(0));
                Assert.That(summary.StoryCachePrefillResolveSkipped, Is.EqualTo(1));
                Assert.That(repository.Rows, Has.Count.EqualTo(1));
                Assert.That(repository.Rows["story-cache-albion-auto-arachite-failed"].DummyEvaluationJson, Does.Contain("dummy_difficulty"));
            });
        }

        [Test]
        public void PrefillStoryCache_SkipsNpcOfferTargetWithDummyDifficultyHistory()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate failed = CreateStoryRow(
                "story-cache-midgard-npc-wyvern-failed",
                "Midgard",
                100,
                "savage wyvern",
                DynamicQuestStartMode.NpcOffer,
                100,
                DateTime.UtcNow.AddHours(-2));
            failed.DummyEvaluationCount = 1;
            failed.DummyEvaluationScore = 100;
            failed.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":false,\"completed\":false,\"players\":3,\"okPlayers\":0,\"targetName\":\"savage wyvern\",\"failureCategory\":\"dummy_difficulty\"}";
            repository.Add(failed);

            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|100|savage wyvern|1|46|50|NpcOffer|time-window");
            options.UseLlm = false;
            options.UseCodexCuratedStories = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE = 1;

            DynamicQuestSeedSummary summary = service.PrefillStoryCache(new[]
            {
                CreateNpc(
                    "Gothi of Odin",
                    "seed-npc-1",
                    100,
                    level: 50,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.Midgard,
                    sourceFlags: GameNPC.eFlags.PEACE),
                CreateNpc(
                    "savage wyvern",
                    "target-npc-1",
                    100,
                    level: 48,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.None,
                    sourceAggroLevel: 50,
                    sourceAggroRange: 1200)
            }, options);

            Assert.Multiple(() =>
            {
                Assert.That(summary.StoryCachePrefilled, Is.EqualTo(0));
                Assert.That(summary.StoryCachePrefillAttempted, Is.EqualTo(0));
                Assert.That(summary.StoryCachePrefillResolveSkipped, Is.EqualTo(1));
                Assert.That(repository.Rows, Has.Count.EqualTo(1));
                Assert.That(repository.Rows["story-cache-midgard-npc-wyvern-failed"].DummyEvaluationJson, Does.Contain("dummy_difficulty"));
            });
        }

        [Test]
        public void PrefillStoryCache_WorldPrefillSkipsPassiveProperNameAutoAcceptTarget()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(string.Empty);
            options.UseLlm = false;
            options.UseCodexCuratedStories = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE = 5;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_MAX_CANDIDATES = 5;

            DynamicQuestSeedSummary summary = service.PrefillStoryCache(new[]
            {
                CreateNpc(
                    "Aonghas Prirerd",
                    "passive-proper-target",
                    1,
                    level: 22,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.None),
                CreateNpc(
                    "adder",
                    "safe-creature-target",
                    1,
                    level: 7,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.None)
            }, options);

            DbDynamicQuestTemplate row = repository.GetActive().Single();
            Assert.Multiple(() =>
            {
                Assert.That(summary.StoryCachePrefilled, Is.EqualTo(1));
                Assert.That(row.TargetNameHint, Is.EqualTo("adder"));
                Assert.That(row.StartMode, Is.EqualTo(DynamicQuestStartMode.AutoAccept.ToString()));
            });
        }

        [Test]
        public void PrefillStoryCache_WorldPrefillAllowsAggressiveProperNameAutoAcceptTarget()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(string.Empty);
            options.UseLlm = false;
            options.UseCodexCuratedStories = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE = 5;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_MAX_CANDIDATES = 5;

            DynamicQuestSeedSummary summary = service.PrefillStoryCache(new[]
            {
                CreateNpc(
                    "Arachneida",
                    "aggressive-proper-target",
                    1,
                    level: 22,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.None,
                    sourceAggroLevel: 50,
                    sourceAggroRange: 1200)
            }, options);

            DbDynamicQuestTemplate row = repository.GetActive().Single();
            Assert.Multiple(() =>
            {
                Assert.That(summary.StoryCachePrefilled, Is.EqualTo(1));
                Assert.That(row.TargetNameHint, Is.EqualTo("Arachneida"));
                Assert.That(row.StartMode, Is.EqualTo(DynamicQuestStartMode.AutoAccept.ToString()));
            });
        }

        [Test]
        public void PrefillStoryCache_WorldPrefillSkipsHighLevelTargetsUntilRouteValidated()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(string.Empty);
            options.UseLlm = false;
            options.UseCodexCuratedStories = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE = 5;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_MAX_CANDIDATES = 5;

            DynamicQuestSeedSummary summary = service.PrefillStoryCache(new[]
            {
                CreateNpc(
                    "Brother Penric",
                    "quest-giver",
                    1,
                    level: 30,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.Albion,
                    sourceFlags: GameNPC.eFlags.PEACE),
                CreateNpc(
                    "archer",
                    "high-level-world-target",
                    1,
                    level: 45,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.None,
                    sourceAggroLevel: 50,
                    sourceAggroRange: 1200)
            }, options);

            Assert.Multiple(() =>
            {
                Assert.That(summary.StoryCachePrefilled, Is.EqualTo(0));
                Assert.That(summary.StoryCachePrefillAttempted, Is.EqualTo(0));
                Assert.That(repository.GetActive(), Is.Empty);
            });
        }

        [Test]
        public void Seed_CodexCuratedStoriesPrefillMultipleStoryArchetypesWhenLlmDisabled()
        {
            Properties.WORLDAI_MOB_GROWTH_ENABLED = true;
            FakeDynamicQuestTemplateRepository repository = new();
            FakeStoryProvider provider = new("main-local", DynamicQuestStoryGenerationResult.Fail("should-not-call"));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(new IDynamicQuestStoryProvider[] { provider }));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = false;
            options.UseCodexCuratedStories = true;
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
            string[] archetypes = rows
                .SelectMany(row => (row.TagsJson ?? string.Empty).Split(new[] { '"', ',', '[', ']' }, StringSplitOptions.RemoveEmptyEntries))
                .Where(tag => tag.StartsWith("story-archetype:", StringComparison.OrdinalIgnoreCase))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToArray();
            string[] knownArchetypes =
            {
                "story-archetype:black-contract",
                "story-archetype:witness-conspiracy",
                "story-archetype:oath-breach",
                "story-archetype:relic-echo",
                "story-archetype:blood-price",
                "story-archetype:border-omen",
                "story-archetype:lost-heirloom",
                "story-archetype:hostage-rescue",
                "story-archetype:siege-break",
                "story-archetype:turncoat-parley"
            };

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(summary.StoryCachePrefilled, Is.EqualTo(4));
                Assert.That(provider.Calls, Is.EqualTo(0));
                Assert.That(rows, Has.Length.EqualTo(4));
                Assert.That(archetypes, Has.Length.GreaterThanOrEqualTo(2));
                Assert.That(archetypes.All(archetype => knownArchetypes.Contains(archetype, StringComparer.OrdinalIgnoreCase)), Is.True);
                Assert.That(archetypes.Any(archetype => string.Equals(archetype, "story-archetype:blood-price", StringComparison.OrdinalIgnoreCase)
                    || string.Equals(archetype, "story-archetype:border-omen", StringComparison.OrdinalIgnoreCase)
                    || string.Equals(archetype, "story-archetype:lost-heirloom", StringComparison.OrdinalIgnoreCase)
                    || string.Equals(archetype, "story-archetype:hostage-rescue", StringComparison.OrdinalIgnoreCase)
                    || string.Equals(archetype, "story-archetype:siege-break", StringComparison.OrdinalIgnoreCase)
                    || string.Equals(archetype, "story-archetype:turncoat-parley", StringComparison.OrdinalIgnoreCase)), Is.True);
                Assert.That(rows.All(row => row.TagsJson.Contains("story-arc:motive", StringComparison.OrdinalIgnoreCase)), Is.True);
                Assert.That(rows.All(row => row.TagsJson.Contains("story-arc:conflict", StringComparison.OrdinalIgnoreCase)), Is.True);
                Assert.That(rows.All(row => row.TagsJson.Contains("story-arc:reversal", StringComparison.OrdinalIgnoreCase)), Is.True);
                Assert.That(rows.All(row => row.TagsJson.Contains("story-arc:consequence", StringComparison.OrdinalIgnoreCase)), Is.True);
                Assert.That(rows.All(row => row.TagsJson.Contains("story-chain:", StringComparison.OrdinalIgnoreCase)), Is.True);
                Assert.That(rows.All(row => row.TagsJson.Contains("story-episode:1/3", StringComparison.OrdinalIgnoreCase)), Is.True);
                Assert.That(rows.All(row => row.TagsJson.Contains("arc-step:1/3", StringComparison.OrdinalIgnoreCase)), Is.True);
                Assert.That(rows.All(row => row.TagsJson.Contains("cinematic-actors:combat_stance:5", StringComparison.OrdinalIgnoreCase)), Is.True);
                Assert.That(rows.All(row => row.TagsJson.Contains("cinematic-actors:guard_advance:4", StringComparison.OrdinalIgnoreCase)), Is.True);
            });
        }

        [Test]
        public void CodexCuratedStories_UseDistinctCinematicProfilesPerArchetype()
        {
            MethodInfo profileBuilder = typeof(DynamicQuestSeedService).GetMethod(
                "CodexStoryCinematicProfileFor",
                BindingFlags.NonPublic | BindingFlags.Static);

            Assert.That(profileBuilder, Is.Not.Null);

            string[] archetypes =
            {
                "black-contract",
                "witness-conspiracy",
                "oath-breach",
                "relic-echo",
                "blood-price",
                "border-omen",
                "lost-heirloom",
                "hostage-rescue",
                "siege-break",
                "turncoat-parley"
            };

            string[] signatures = archetypes
                .Select(archetype =>
                {
                    object profile = profileBuilder.Invoke(null, new object[] { archetype, "수도원 길목", "{{target}}" });
                    return string.Join("|", new[]
                    {
                        GetProfileString(profile, "AcceptSceneRole"),
                        GetProfileString(profile, "ScoutSceneRole"),
                        GetProfileString(profile, "ScoutFormation"),
                        GetProfileString(profile, "RitualSceneRole"),
                        GetProfileString(profile, "AmbushSceneRole"),
                        GetProfileString(profile, "InterceptSceneRole"),
                        GetProfileString(profile, "ChoiceConfrontationRole"),
                        GetProfileString(profile, "ChoiceFalloutRole"),
                        GetProfileString(profile, "HoldRole"),
                        GetProfileString(profile, "BranchCompanionRole")
                    });
                })
                .ToArray();
            string[] witnesses = archetypes
                .Select(archetype =>
                {
                    object profile = profileBuilder.Invoke(null, new object[] { archetype, "수도원 길목", "{{target}}" });
                    return GetProfileString(profile, "WitnessName");
                })
                .ToArray();
            string[] evidenceNames = archetypes
                .Select(archetype =>
                {
                    object profile = profileBuilder.Invoke(null, new object[] { archetype, "수도원 길목", "{{target}}" });
                    return GetProfileString(profile, "EvidenceName");
                })
                .ToArray();

            Assert.Multiple(() =>
            {
                Assert.That(signatures.Distinct(StringComparer.OrdinalIgnoreCase).Count(), Is.EqualTo(archetypes.Length));
                Assert.That(witnesses.Distinct(StringComparer.OrdinalIgnoreCase).Count(), Is.EqualTo(archetypes.Length));
                Assert.That(evidenceNames.Distinct(StringComparer.OrdinalIgnoreCase).Count(), Is.EqualTo(archetypes.Length));
                Assert.That(witnesses, Does.Contain("Sable Mara"));
                Assert.That(witnesses, Does.Contain("Caelric"));
                Assert.That(witnesses, Does.Contain("Aline"));
                Assert.That(witnesses, Does.Contain("Rowan"));
                Assert.That(witnesses, Does.Contain("Iseult"));
                Assert.That(evidenceNames, Does.Contain("검은 밀랍이 묻은 계약서"));
                Assert.That(evidenceNames, Does.Contain("찢긴 서약장"));
                Assert.That(evidenceNames, Does.Contain("피 묻은 결박끈"));
                Assert.That(evidenceNames, Does.Contain("불탄 보급 표식"));
                Assert.That(evidenceNames, Does.Contain("반쪽으로 접힌 전령 표식"));
                Assert.That(signatures.Single(signature => signature.Contains("contract_witness", StringComparison.OrdinalIgnoreCase)), Does.Contain("witness_screen"));
                Assert.That(signatures.Single(signature => signature.Contains("hidden_witness_ring", StringComparison.OrdinalIgnoreCase)), Does.Contain("truth_fallout"));
                Assert.That(signatures.Single(signature => signature.Contains("broken_oath_witness", StringComparison.OrdinalIgnoreCase)), Does.Contain("renewed_shield_hold"));
                Assert.That(signatures.Single(signature => signature.Contains("relic_witness_circle", StringComparison.OrdinalIgnoreCase)), Does.Contain("echo_fallout"));
                Assert.That(signatures.Single(signature => signature.Contains("ledger_witness", StringComparison.OrdinalIgnoreCase)), Does.Contain("debt_fallout"));
                Assert.That(signatures.Single(signature => signature.Contains("border_watch", StringComparison.OrdinalIgnoreCase)), Does.Contain("gate_hold"));
                Assert.That(signatures.Single(signature => signature.Contains("heirloom_witness", StringComparison.OrdinalIgnoreCase)), Does.Contain("heirloom_guard_hold"));
                Assert.That(signatures.Single(signature => signature.Contains("bound_witness_guard", StringComparison.OrdinalIgnoreCase)), Does.Contain("safe_corridor_hold"));
                Assert.That(signatures.Single(signature => signature.Contains("siege_watch", StringComparison.OrdinalIgnoreCase)), Does.Contain("breach_hold"));
                Assert.That(signatures.Single(signature => signature.Contains("turncoat_witness", StringComparison.OrdinalIgnoreCase)), Does.Contain("two_banner_hold"));
            });
        }

        [Test]
        public void CodexCuratedStories_UseDistinctResolutionAndChoiceForLostHeirloom()
        {
            MethodInfo resolutionBuilder = typeof(DynamicQuestSeedService).GetMethod(
                "CodexStoryArchetypeResolution",
                BindingFlags.NonPublic | BindingFlags.Static);
            MethodInfo choiceBuilder = typeof(DynamicQuestSeedService).GetMethod(
                "CodexStoryDramaticChoice",
                BindingFlags.NonPublic | BindingFlags.Static);

            Assert.That(resolutionBuilder, Is.Not.Null);
            Assert.That(choiceBuilder, Is.Not.Null);

            string resolution = (string)resolutionBuilder.Invoke(null, new object[] { "lost-heirloom", "고리석 숲길", "{{target}}" });
            string choice = (string)choiceBuilder.Invoke(null, new object[] { "lost-heirloom", "고리석 숲길", "{{target}}" });

            Assert.Multiple(() =>
            {
                Assert.That(choice, Does.Not.StartWith("유품을 조용히 돌려주면"));
                Assert.That($"{resolution} {choice}", Does.Not.Match("유품을 조용히 돌려주면[^.]+유품을 조용히 돌려주면"));
                Assert.That(choice, Does.Contain("목격자"));
                Assert.That(choice, Does.Contain("장부"));
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
        public void Seed_UseLlmUpgradesLegacyCachedStoryWithoutPresentationMetadata()
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
                Assert.That(provider.Calls, Is.EqualTo(1));
                Assert.That(refreshed.StoryNarrativeJson, Is.Not.Empty);
                Assert.That(refreshed.StoryPresentationJson, Is.Not.Empty);
                Assert.That(refreshed.TagsJson, Does.Contain("story-scaffold-upgraded"));
                Assert.That(refreshed.TagsJson, Does.Contain("story-title-variant:v3"));
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
                Assert.That(quest.Tags, Does.Contain("story-cinematic"));
                Assert.That(quest.Tags, Does.Contain("scene-director"));
                Assert.That(quest.Tags, Does.Contain("cinematic-actors:threat_standoff:6"));
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
        public void Seed_StoryCacheCleanupDeactivatesUnknownRealmRowsBeforePruneWindow()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-unknown-realm",
                "Unknown",
                352,
                "crazed prisoner",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddDays(-1)));
            repository.Add(CreateStoryRow("story-albion-ready", 95, DateTime.UtcNow.AddDays(-2)));

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
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_MAX_TEMPLATES = 100;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PRUNE_COUNT = 1;
            DynamicQuestSeedService.SetClockForTest(() => new DateTime(2026, 6, 3, 6, 30, 0, DateTimeKind.Utc));

            service.Seed(new[] { npc, target }, options);

            Assert.Multiple(() =>
            {
                Assert.That(repository.Rows["story-unknown-realm"].IsActive, Is.False);
                Assert.That(repository.Rows["story-albion-ready"].IsActive, Is.True);
            });
        }

        [Test]
        public void Seed_StoryCacheCleanupDeactivatesTargetMissingRowsButKeepsDifficultyMemory()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate targetMissing = CreateStoryRow(
                "story-target-missing",
                "Albion",
                1,
                "vanished herald",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddDays(-1));
            targetMissing.DummyEvaluationCount = 1;
            targetMissing.DummyEvaluationScore = 0;
            targetMissing.DummyEvaluationJson = "{\"score\":0,\"minimumScore\":70,\"passed\":false,\"completed\":false,\"players\":0,\"okPlayers\":0,\"failureCategory\":\"target_missing\"}";
            repository.Add(targetMissing);

            DbDynamicQuestTemplate difficulty = CreateStoryRow(
                "story-difficulty-memory",
                "Albion",
                1,
                "ant drone",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddDays(-2));
            difficulty.DummyEvaluationCount = 1;
            difficulty.DummyEvaluationScore = 0;
            difficulty.DummyEvaluationJson = "{\"score\":0,\"minimumScore\":70,\"passed\":false,\"completed\":false,\"players\":3,\"okPlayers\":0,\"failureCategory\":\"dummy_difficulty\",\"source\":\"run-dummy-dynamic-quest-matrix\"}";
            repository.Add(difficulty);

            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedNpc target = CreateNpc("black wolf pup", "target-npc-1", 1);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_MAX_TEMPLATES = 100;
            DynamicQuestSeedService.SetClockForTest(() => new DateTime(2026, 6, 3, 6, 30, 0, DateTimeKind.Utc));

            service.Seed(new[] { npc, target }, options);

            Assert.Multiple(() =>
            {
                Assert.That(repository.Rows["story-target-missing"].IsActive, Is.False);
                Assert.That(repository.Rows["story-difficulty-memory"].IsActive, Is.True);
            });
        }

        [Test]
        public void Seed_StoryCacheCleanupDeactivatesUnevaluatedHighLevelWorldPrefillRows()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate unsafeHighLevel = CreateStoryRow(
                "story-high-world-prefill",
                "Albion",
                1,
                "cait sidhe",
                DynamicQuestStartMode.NpcOffer,
                100,
                DateTime.UtcNow.AddDays(-1));
            unsafeHighLevel.MinLevel = 48;
            unsafeHighLevel.MaxLevel = 50;
            unsafeHighLevel.StoryProvider = "codex-curated";
            unsafeHighLevel.StoryModel = "hand-authored-cinematic-v15";
            unsafeHighLevel.TagsJson = "[\"story-cache\",\"codex-curated\",\"selector:start:quest-giver\"]";
            repository.Add(unsafeHighLevel);

            DbDynamicQuestTemplate evaluatedHighLevel = CreateStoryRow(
                "story-high-evaluated-memory",
                "Albion",
                1,
                "savage wyvern",
                DynamicQuestStartMode.NpcOffer,
                100,
                DateTime.UtcNow.AddDays(-2));
            evaluatedHighLevel.MinLevel = 48;
            evaluatedHighLevel.MaxLevel = 50;
            evaluatedHighLevel.StoryProvider = "codex-curated";
            evaluatedHighLevel.StoryModel = "hand-authored-cinematic-v15";
            evaluatedHighLevel.TagsJson = "[\"story-cache\",\"codex-curated\",\"selector:start:quest-giver\"]";
            evaluatedHighLevel.DummyEvaluationCount = 1;
            evaluatedHighLevel.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":false,\"completed\":false,\"failureCategory\":\"dummy_difficulty\"}";
            repository.Add(evaluatedHighLevel);

            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedNpc npc = CreateNpc("Brother Penric", "seed-npc-1", 1);
            DynamicQuestSeedNpc target = CreateNpc("black wolf pup", "target-npc-1", 1);
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "Brother Penric|1|black wolf pup|1|1|5");
            options.UseLlm = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_MAX_TEMPLATES = 100;

            service.Seed(new[] { npc, target }, options);

            Assert.Multiple(() =>
            {
                Assert.That(repository.Rows["story-high-world-prefill"].IsActive, Is.False);
                Assert.That(repository.Rows["story-high-evaluated-memory"].IsActive, Is.True);
            });
        }

        [Test]
        public void Seed_StoryCacheCleanupMarksRelatedUnevaluatedDifficultyHistoryRows()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate failed = CreateStoryRow(
                "story-arachite-failed",
                "Midgard",
                100,
                "arachite warrior",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddDays(-2));
            failed.DummyEvaluationCount = 1;
            failed.DummyEvaluationScore = 100;
            failed.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":false,\"completed\":false,\"players\":1,\"okPlayers\":0,\"playerDeaths\":1,\"failureCategory\":\"dummy_difficulty\"}";
            repository.Add(failed);
            repository.Add(CreateStoryRow(
                "story-arachite-sibling",
                "Midgard",
                100,
                "arachite prelate",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddDays(-1)));

            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(string.Empty);
            options.UseLlm = false;
            options.UseCodexCuratedStories = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE = 0;

            service.PrefillStoryCache(Array.Empty<DynamicQuestSeedNpc>(), options);

            DbDynamicQuestTemplate sibling = repository.Rows["story-arachite-sibling"];
            Assert.Multiple(() =>
            {
                Assert.That(sibling.IsActive, Is.True);
                Assert.That(sibling.DummyEvaluationCount, Is.EqualTo(1));
                Assert.That(sibling.DummyEvaluationScore, Is.EqualTo(0));
                Assert.That(sibling.DummyEvaluationJson, Does.Contain("dummy_difficulty"));
                Assert.That(sibling.DummyEvaluationJson, Does.Contain("blocked by related autoaccept target difficulty history"));
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
            Properties.WORLDAI_MOB_GROWTH_ENABLED = true;
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
            Properties.WORLDAI_MOB_GROWTH_ENABLED = true;
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
                Assert.That(midgardWorld.TagsJson, Does.Contain("world-signal:time-window"));
                Assert.That(midgardWorld.Trigger, Is.EqualTo("time-window"));
                Assert.That(hiberniaWorld.TagsJson, Does.Contain("world-signal:item-acquired"));
                Assert.That(hiberniaWorld.Trigger, Is.Empty);
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests(), Has.Count.EqualTo(1));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests().Single().TargetName, Is.EqualTo("black wolf pup"));
            });
        }

        [Test]
        public void StoryCachePrefillPlan_ReportsWorldCandidatesWithoutMutation()
        {
            Properties.WORLDAI_MOB_GROWTH_ENABLED = true;
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
                CreateNpc("crazed prisoner", "target-unknown-extra", 352, level: 30, x: 26000, y: 32000),
                CreateNpc("training master", "trainer-extra", 1, level: 75, x: 514000, y: 514000)
            }, options, sampleLimit: 10);

            Assert.Multiple(() =>
            {
                Assert.That(plan.ScannedNpcs, Is.EqualTo(7));
                Assert.That(plan.ExistingDefinitions, Is.EqualTo(1));
                Assert.That(plan.WorldCandidates, Is.EqualTo(3));
                Assert.That(plan.TotalCandidates, Is.EqualTo(4));
                Assert.That(plan.BatchSize, Is.EqualTo(2));
                Assert.That(plan.CanGenerateNewStory, Is.True);
                Assert.That(plan.Reasons, Is.Empty);
                Assert.That(plan.Samples.Select(sample => sample.TargetName), Does.Contain("forest spiderling"));
                Assert.That(plan.Samples.Single(sample => sample.TargetName == "forest spiderling").BranchWorldSignal, Is.EqualTo("mob-growth:killed:region:1"));
                Assert.That(plan.Samples.Single(sample => sample.TargetName == "young tomte").BranchWorldSignal, Is.EqualTo("time-window"));
                Assert.That(plan.Samples.Single(sample => sample.TargetName == "water beetle").BranchWorldSignal, Is.EqualTo("item-acquired"));
                Assert.That(plan.Samples.Select(sample => sample.TargetName), Does.Not.Contain("training master"));
                Assert.That(plan.Samples.Select(sample => sample.TargetName), Does.Not.Contain("crazed prisoner"));
                Assert.That(repository.GetActive(), Is.Empty);
            });
        }

        [Test]
        public void StoryCachePrefillPlan_SkipsAutoAcceptTargetWithDummyDifficultyHistory()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate failed = CreateStoryRow(
                "story-cache-albion-auto-forest-spiderling-plan-failed",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-2));
            failed.DummyEvaluationCount = 1;
            failed.DummyEvaluationScore = 100;
            failed.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":false,\"completed\":false,\"players\":1,\"okPlayers\":0,\"playerDeaths\":1,\"failureCategory\":\"dummy_difficulty\"}";
            repository.Add(failed);

            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "|1|forest spiderling|1|1|5|AutoAccept|region:1");
            options.UseLlm = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = false;

            DynamicQuestStoryCachePrefillPlanSnapshot plan = service.GetStoryCachePrefillPlanSnapshot(new[]
            {
                CreateNpc("forest spiderling", "target-npc-1", 1, level: 3, x: 522000, y: 492000, z: 2954)
            }, options, sampleLimit: 10);

            Assert.Multiple(() =>
            {
                Assert.That(plan.ExistingDefinitions, Is.EqualTo(0));
                Assert.That(plan.WorldCandidates, Is.EqualTo(0));
                Assert.That(plan.TotalCandidates, Is.EqualTo(0));
                Assert.That(plan.Samples, Is.Empty);
                Assert.That(repository.GetActive(), Has.Count.EqualTo(1));
            });
        }

        [Test]
        public void StoryCachePrefillPlan_PrefersNpcOfferGrowthBranchCandidateOverNpcLessWorldCandidate()
        {
            Properties.WORLDAI_MOB_GROWTH_ENABLED = true;
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
            Properties.WORLDAI_MOB_GROWTH_ENABLED = true;
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
            Properties.WORLDAI_MOB_GROWTH_ENABLED = true;
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
            Properties.WORLDAI_MOB_GROWTH_ENABLED = true;
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
        public void Seed_DeterministicNpcOfferSkipsMobGrowthBranchWhenSystemDisabled()
        {
            Properties.WORLDAI_MOB_GROWTH_ENABLED = false;
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

            Assert.Multiple(() =>
            {
                Assert.That(quest.Tags, Does.Not.Contain("branch:mob-growth"));
                Assert.That(quest.Tags.Any(tag => tag.StartsWith("world-signal:mob-growth", StringComparison.OrdinalIgnoreCase)), Is.False);
                Assert.That(quest.Nodes.Select(node => node.Id), Does.Not.Contain("observe_signal"));
                Assert.That(quest.Nodes.Single(node => node.Id == "choice").Edges.Select(edge => edge.ToNodeId), Does.Not.Contain("observe_signal"));
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
            DynamicQuestNode choice = quest.Nodes.Single(node => node.Id == "choice");
            DynamicQuestNode observe = quest.Nodes.Single(node => node.Id == "observe_signal");
            DynamicQuestEdge safe = choice.Edges.Single(edge => edge.ConditionValue == "safe");
            DynamicQuestEdge followup = choice.Edges.Single(edge => edge.ConditionValue == "followup");
            DynamicQuestEdge signal = observe.Edges.Single(edge => edge.Condition == DynamicQuestEdgeCondition.WorldSignal);
            DynamicQuestEdge timeout = observe.Edges.Single(edge => edge.Condition == DynamicQuestEdgeCondition.TimedOut);

            Assert.Multiple(() =>
            {
                Assert.That(quest.Tags, Does.Contain("branch:time-window"));
                Assert.That(quest.Tags, Does.Contain("world-signal:time-window:night"));
                Assert.That(safe.ToNodeId, Is.EqualTo("observe_signal"));
                Assert.That(followup.ToNodeId, Is.EqualTo("observe_signal"));
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
        public void Seed_StoryCacheOffersRemoveIneligibleRuntimeOfferBeforeRealmCoverage()
        {
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = true;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate stale = CreateStoryRow(
                "story-cache-albion-stale-difficulty",
                "Albion",
                1,
                "black wolf pup",
                DynamicQuestStartMode.NpcOffer,
                96,
                DateTime.UtcNow.AddHours(-3));
            stale.DummyEvaluationCount = 1;
            stale.DummyEvaluationScore = 100;
            stale.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":false,\"completed\":false,\"players\":1,\"okPlayers\":0,\"failureCategory\":\"dummy_difficulty\"}";
            stale.DummyEvaluatedAt = DateTime.UtcNow.AddHours(-2);
            repository.Add(stale);
            DbDynamicQuestTemplate eligible = CreateStoryRow(
                "story-cache-albion-eligible-spiderling",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                95,
                DateTime.UtcNow.AddHours(-4));
            eligible.DummyEvaluationCount = 1;
            eligible.DummyEvaluationScore = 95;
            eligible.DummyEvaluationJson = "{\"score\":95,\"minimumScore\":70,\"passed\":true,\"completed\":true,\"players\":1,\"okPlayers\":1,\"failureCategory\":\"passed\",\"operationalEvaluation\":{\"totalScore\":85,\"grade\":\"usable\",\"passed\":true}}";
            eligible.DummyEvaluatedAt = DateTime.UtcNow.AddHours(-2);
            repository.Add(eligible);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestRuntimeService.Instance.AddQuest(new DynamicQuestDefinition
            {
                Id = "runtime-stale-story-cache-offer",
                Title = "stale",
                OfferText = "stale",
                ProgressText = "stale",
                FinishText = "stale",
                StartNpcInternalId = "seed-npc-1",
                StartNpcName = "Brother Penric",
                StartRegionId = 1,
                TargetName = "black wolf pup",
                TargetCount = 1,
                MinLevel = 1,
                MaxLevel = 5,
                StartMode = DynamicQuestStartMode.NpcOffer,
                WorldRevision = "test",
                Tags = new[] { "template:story-cache-albion-stale-difficulty" }
            });
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(string.Empty);
            options.UseLlm = true;
            options.UseStoryCacheOffers = true;
            options.MaxQuests = 1;

            DynamicQuestSeedSummary summary = service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-stale", 1),
                CreateNpc("forest spiderling", "target-eligible", 1)
            }, options);

            DynamicQuestDefinition[] quests = DynamicQuestRuntimeService.Instance.GetQuests()
                .OrderBy(quest => quest.Id, StringComparer.OrdinalIgnoreCase)
                .ToArray();

            Assert.Multiple(() =>
            {
                Assert.That(summary.RemovedStaleOffers, Is.EqualTo(1));
                Assert.That(summary.StoryCacheOffered, Is.EqualTo(1));
                Assert.That(summary.Created, Is.EqualTo(1));
                Assert.That(quests.Select(quest => quest.Id), Does.Not.Contain("runtime-stale-story-cache-offer"));
                Assert.That(quests.Single().TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(quests.Single().Tags, Does.Contain("template:story-cache-albion-eligible-spiderling"));
            });
        }

        [Test]
        public void Seed_StoryCacheOffersInterleaveNpcOfferGrowthRowsWithNpcLessRows()
        {
            Properties.WORLDAI_MOB_GROWTH_ENABLED = true;
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
        public void Seed_StoryCacheOffersUpgradeCodexRowsWithGenericRepetition()
        {
            Properties.WORLDAI_MOB_GROWTH_ENABLED = true;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate generic = CreateStoryRow(
                "story-cache-codex-generic-repetition",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-5));
            generic.Title = "{{target}} 처치 요청";
            generic.OfferText = "{{target}} 위협이 {{realm}} 길목에 번지고 있습니다.";
            generic.ProgressText = "{{target}}를 추적하고 {{target}} 위협을 끊어야 합니다.";
            generic.FinishText = "{{target}} 위협이 사라지고 {{target}} 흔적이 잦아들었습니다.";
            generic.StoryProvider = "codex-curated";
            generic.StoryModel = "hand-authored-cinematic-v6";
            generic.TagsJson = "[\"llm-story\",\"story-cache\",\"codex-curated\",\"branch:mob-growth\",\"world-signal:mob-growth:killed:region:1\"]";
            generic.StoryQualityJson = "{\"totalScore\":94,\"structureScore\":15,\"koreanScore\":8,\"objectiveScore\":20,\"immersionScore\":15,\"narrativeScore\":12,\"presentationScore\":8,\"rebindabilityScore\":15,\"safetyScore\":15,\"diversityScore\":5,\"reasons\":[\"narrative_scene\",\"presentation_beat\",\"generic_repetition\"]}";
            generic.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"수도원 길목의 경고\",\"body\":\"{{start_npc}}은 {{realm}} 수도원 길목에서 {{target}} 위협이 커지고, {{target}} 흔적이 다시 {{target}} 쪽으로 이어진다고 말합니다.\",\"journalEntry\":\"{{target}} 흔적을 조사한다.\",\"mood\":\"urgent\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            generic.StoryPresentationJson = "[{\"nodeId\":\"talk\",\"trigger\":\"OnNpcInteract\",\"speaker\":\"StartNpc\",\"text\":\"{{target}} 소식 때문에 모두가 조용히 문을 걸어 잠그고 있습니다.\",\"emotion\":\"fear\",\"emote\":\"Shiver\"}]";
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
            DbDynamicQuestTemplate upgraded = repository.Rows["story-cache-codex-generic-repetition"];

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(2));
                Assert.That(summary.StoryCacheOffered, Is.EqualTo(1));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests().Select(quest => quest.TargetName), Does.Contain("forest spiderling"));
                Assert.That(upgraded.LastBindingKey, Is.Not.EqualTo(string.Empty));
                Assert.That(upgraded.Title, Does.Not.Contain("처치 요청"));
                Assert.That(upgraded.Title, Does.Not.Contain("{{target}}"));
                Assert.That(upgraded.StoryQualityScore, Is.GreaterThanOrEqualTo(95));
                Assert.That(upgraded.StoryQualityJson, Does.Not.Contain("generic_repetition"));
                Assert.That(upgraded.TagsJson, Does.Contain("story-scaffold-upgraded"));
                Assert.That(upgraded.TagsJson, Does.Contain("story-title-variant:v3"));
                Assert.That(upgraded.TagsJson, Does.Contain("mass-cinematic"));
                Assert.That(upgraded.TagsJson, Does.Contain("llm-model:hand-authored-cinematic-v15"));
                Assert.That(upgraded.TagsJson, Does.Not.Contain("llm-model:hand-authored-cinematic-v6"));
                Assert.That(upgraded.StoryPresentationJson, Does.Contain("\"actorCount\":100"));
            });
        }

        [Test]
        public void Seed_StoryCacheOffersUpgradeCodexRowsWithAwkwardKoreanParticle()
        {
            Properties.WORLDAI_MOB_GROWTH_ENABLED = true;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate awkward = CreateStoryRow(
                "story-cache-codex-awkward-particle",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-5));
            awkward.OfferText = "목격자 'Nessa'를 기록한 증인이 {{target}} 위협을 전했습니다.";
            awkward.StoryProvider = "codex-curated";
            awkward.StoryModel = "hand-authored-cinematic-v14";
            awkward.TagsJson = "[\"llm-story\",\"story-cache\",\"codex-curated\",\"branch:mob-growth\",\"world-signal:mob-growth:killed:region:1\",\"story-title-variant:v3\"]";
            repository.Add(awkward);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
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
            DbDynamicQuestTemplate upgraded = repository.Rows["story-cache-codex-awkward-particle"];

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(2));
                Assert.That(summary.StoryCacheOffered, Is.EqualTo(1));
                Assert.That(upgraded.LastBindingKey, Is.Not.EqualTo(string.Empty));
                Assert.That(upgraded.StoryQualityScore, Is.GreaterThanOrEqualTo(95));
                Assert.That(upgraded.StoryQualityJson, Does.Not.Contain("awkward_korean_particle"));
                Assert.That(upgraded.StoryNarrativeJson, Does.Not.Match("'[A-Za-z][^']*'[이가은는을를와과]"));
                Assert.That(upgraded.StoryNarrativeJson, Does.Not.Match("'[A-Za-z][^']*'(로|으로)"));
                Assert.That(upgraded.StoryNarrativeJson, Does.Not.Match("[A-Za-z][A-Za-z ]{2,}의"));
                Assert.That(upgraded.TagsJson, Does.Contain("story-scaffold-upgraded"));
                Assert.That(upgraded.StoryPresentationJson, Does.Contain("\"actorCount\":100"));
            });
        }

        [Test]
        public void PrefillStoryCache_UpgradesCodexRowsWithGenericRepetitionBeforeGeneratingNewRows()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate generic = CreateStoryRow(
                "story-cache-codex-prefill-generic-repetition",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-5));
            generic.Title = "{{target}} 처치 요청";
            generic.StoryProvider = "codex-curated";
            generic.StoryModel = "hand-authored-cinematic-v6";
            generic.TagsJson = "[\"llm-story\",\"story-cache\",\"codex-curated\",\"branch:time-window\",\"world-signal:time-window\"]";
            generic.StoryQualityJson = "{\"totalScore\":94,\"structureScore\":15,\"koreanScore\":8,\"objectiveScore\":20,\"immersionScore\":15,\"narrativeScore\":12,\"presentationScore\":8,\"rebindabilityScore\":15,\"safetyScore\":15,\"diversityScore\":5,\"reasons\":[\"generic_repetition\"]}";
            generic.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"수도원 길목의 경고\",\"body\":\"{{target}} 위협과 {{target}} 흔적이 {{target}} 쪽으로 이어집니다.\",\"journalEntry\":\"{{target}} 흔적을 조사한다.\",\"mood\":\"urgent\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            generic.StoryPresentationJson = "[{\"nodeId\":\"talk\",\"trigger\":\"OnNpcInteract\",\"speaker\":\"StartNpc\",\"text\":\"{{target}} 때문에 모두가 조용히 문을 잠급니다.\",\"emotion\":\"fear\",\"emote\":\"Shiver\"}]";
            repository.Add(generic);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(string.Empty);
            options.UseLlm = false;
            options.UseCodexCuratedStories = true;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE = 0;

            DynamicQuestSeedSummary summary = service.PrefillStoryCache(Array.Empty<DynamicQuestSeedNpc>(), options);
            DbDynamicQuestTemplate upgraded = repository.Rows["story-cache-codex-prefill-generic-repetition"];

            Assert.Multiple(() =>
            {
                Assert.That(summary.StoryCachePrefilled, Is.EqualTo(0));
                Assert.That(upgraded.Title, Does.Not.Contain("처치 요청"));
                Assert.That(upgraded.Title, Does.Not.Contain("{{target}}"));
                Assert.That(upgraded.StoryQualityScore, Is.GreaterThanOrEqualTo(95));
                Assert.That(upgraded.StoryQualityJson, Does.Not.Contain("generic_repetition"));
                Assert.That(upgraded.TagsJson, Does.Contain("story-scaffold-upgraded"));
                Assert.That(upgraded.TagsJson, Does.Contain("story-title-variant:v3"));
                Assert.That(upgraded.TagsJson, Does.Contain("mass-cinematic"));
                Assert.That(upgraded.TagsJson, Does.Contain("llm-model:hand-authored-cinematic-v15"));
                Assert.That(upgraded.TagsJson, Does.Not.Contain("llm-model:hand-authored-cinematic-v6"));
                Assert.That(upgraded.StoryPresentationJson, Does.Contain("\"actorCount\":100"));
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
        public void Seed_StoryCacheOffersPreferPassingDummyEvaluatedRowsWithinSameLevelBucket()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate unevaluated = CreateStoryRow(
                "story-cache-albion-npc-unevaluated-high-quality",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                100,
                DateTime.UtcNow.AddHours(-3));
            DbDynamicQuestTemplate evaluated = CreateStoryRow(
                "story-cache-albion-npc-dummy-validated",
                "Albion",
                1,
                "river spraggon",
                DynamicQuestStartMode.NpcOffer,
                85,
                DateTime.UtcNow.AddHours(-2));
            evaluated.DummyEvaluationScore = 95;
            evaluated.DummyEvaluationCount = 1;
            evaluated.DummyEvaluationJson = "{\"score\":95,\"minimumScore\":70,\"belowThreshold\":false,\"skyrimGradeScore\":95,\"cinematicDensityScore\":92}";
            repository.Add(unevaluated);
            repository.Add(evaluated);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|100|selector:hostile-near-start|1|1|5|NpcOffer||mob-growth:killed:region:100");
            options.UseLlm = true;
            options.UseStoryCacheOffers = true;
            options.MaxQuests = 2;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = false;

            DynamicQuestSeedSummary summary = service.Seed(new[]
            {
                CreateNpc("Aud", "seed-npc-100", 100, level: 30),
                CreateNpc("young sveawolf", "target-configured-mid", 100, x: 502000, y: 500000),
                CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30),
                CreateNpc("forest spiderling", "target-cache-unevaluated", 1),
                CreateNpc("river spraggon", "target-cache-evaluated", 1)
            }, options);

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(2));
                Assert.That(summary.StoryCacheOffered, Is.EqualTo(1));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests().Select(quest => quest.TargetName), Does.Contain("river spraggon"));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests().Select(quest => quest.TargetName), Does.Not.Contain("forest spiderling"));
                Assert.That(repository.Rows["story-cache-albion-npc-dummy-validated"].LastBindingKey, Is.Not.Empty);
                Assert.That(repository.Rows["story-cache-albion-npc-unevaluated-high-quality"].LastBindingKey, Is.Empty);
            });
        }

        [Test]
        public void Seed_StoryCacheOffersCanRequirePassingDummyEvaluation()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate unevaluated = CreateStoryRow(
                "story-cache-albion-auto-unevaluated",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-3));
            DbDynamicQuestTemplate evaluated = CreateStoryRow(
                "story-cache-albion-auto-evaluated",
                "Albion",
                1,
                "river spraggon",
                DynamicQuestStartMode.AutoAccept,
                85,
                DateTime.UtcNow.AddHours(-2));
            evaluated.DummyEvaluationScore = 95;
            evaluated.DummyEvaluationCount = 1;
            evaluated.DummyEvaluationJson = "{\"score\":95,\"minimumScore\":70,\"belowThreshold\":false,\"skyrimGradeScore\":95,\"cinematicDensityScore\":92,\"passed\":true,\"completed\":true,\"players\":1,\"okPlayers\":1}";
            unevaluated.TagsJson = "[\"llm-story\",\"story-cache\",\"story-archetype:border-omen\"]";
            evaluated.TagsJson = "[\"llm-story\",\"story-cache\",\"story-archetype:relic-echo\"]";
            repository.Add(unevaluated);
            repository.Add(evaluated);

            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestSeedOptions options = DynamicQuestSeedOptions.DefaultForTests(
                "selector:town-npc|100|selector:hostile-near-start|1|1|5|NpcOffer||time-window:night");
            options.UseLlm = true;
            options.UseStoryCacheOffers = true;
            options.MaxQuests = 2;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED = false;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = true;

            DynamicQuestSeedSummary summary = service.Seed(new[]
            {
                CreateNpc("Aud", "seed-npc-100", 100, level: 30),
                CreateNpc("young sveawolf", "target-configured-mid", 100, x: 502000, y: 500000),
                CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30),
                CreateNpc("forest spiderling", "target-cache-unevaluated", 1),
                CreateNpc("river spraggon", "target-cache-evaluated", 1)
            }, options);
            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem unevaluatedItem = snapshot.Items.Single(item => item.TemplateId == "story-cache-albion-auto-unevaluated");
            DynamicQuestStoryCacheItem evaluatedItem = snapshot.Items.Single(item => item.TemplateId == "story-cache-albion-auto-evaluated");

            Assert.Multiple(() =>
            {
                Assert.That(summary.StoryCacheOffered, Is.EqualTo(1));
                Assert.That(snapshot.ReadyActive, Is.EqualTo(2));
                Assert.That(snapshot.OfferEligibleActive, Is.EqualTo(1));
                Assert.That(snapshot.DummyUnevaluatedOfferBlocked, Is.EqualTo(1));
                Assert.That(snapshot.ByArchetype["border-omen"], Is.EqualTo(1));
                Assert.That(snapshot.ByArchetype["relic-echo"], Is.EqualTo(1));
                Assert.That(snapshot.ReadyByArchetype["border-omen"], Is.EqualTo(1));
                Assert.That(snapshot.ReadyByArchetype["relic-echo"], Is.EqualTo(1));
                Assert.That(snapshot.OfferEligibleByArchetype.ContainsKey("border-omen"), Is.False);
                Assert.That(snapshot.OfferEligibleByArchetype["relic-echo"], Is.EqualTo(1));
                Assert.That(snapshot.DummyUnevaluatedOfferBlockedByArchetype["border-omen"], Is.EqualTo(1));
                Assert.That(snapshot.DummyUnevaluatedOfferBlockedByArchetype.ContainsKey("relic-echo"), Is.False);
                Assert.That(unevaluatedItem.ReadyForUse, Is.True);
                Assert.That(unevaluatedItem.OfferEligible, Is.False);
                Assert.That(unevaluatedItem.OfferBlockReasons, Does.Contain("dummy_evaluation_required"));
                Assert.That(evaluatedItem.ReadyForUse, Is.True);
                Assert.That(evaluatedItem.OfferEligible, Is.True);
                Assert.That(evaluatedItem.OfferBlockReasons, Is.Empty);
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests().Select(quest => quest.TargetName), Does.Contain("river spraggon"));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests().Select(quest => quest.TargetName), Does.Not.Contain("forest spiderling"));
                Assert.That(repository.Rows["story-cache-albion-auto-evaluated"].LastBindingKey, Is.Not.Empty);
                Assert.That(repository.Rows["story-cache-albion-auto-unevaluated"].LastBindingKey, Is.Empty);
            });
        }

        [Test]
        public void StoryCacheEvaluationOffer_CreatesRuntimeQuestForDummyRequiredReadyRow()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-albion-evaluation-offer",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1));
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = true;

            DynamicQuestStoryCacheEvaluationOfferResult result = service.OfferStoryCacheTemplateForEvaluation(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30),
                CreateNpc("forest spiderling", "target-cache", 1, level: 2, x: 502000, y: 500000)
            }, "story-cache-albion-evaluation-offer", "test");

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True);
                Assert.That(result.Existing, Is.False);
                Assert.That(result.QuestId, Is.Not.Empty);
                Assert.That(result.OfferBlockReasons, Does.Contain("dummy_evaluation_required"));
                Assert.That(result.Quest.Tags.First(), Is.EqualTo("template:story-cache-albion-evaluation-offer"));
                Assert.That(result.Quest.Tags, Does.Contain("dummy-evaluation-offer"));
                Assert.That(result.Quest.Tags, Does.Contain("template:story-cache-albion-evaluation-offer"));
                Assert.That(result.Quest.Tags, Does.Contain("region:1"));
                Assert.That(result.Quest.Tags, Does.Contain("trigger:region:1"));
                Assert.That(DynamicQuestRuntimeService.Instance.GetTemplateIdForQuest(result.QuestId), Is.EqualTo("story-cache-albion-evaluation-offer"));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests(), Has.Count.EqualTo(1));
                Assert.That(repository.Rows["story-cache-albion-evaluation-offer"].LastBindingKey, Is.Not.Empty);
            });

            bool accepted = DynamicQuestRuntimeService.Instance.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1,
                502000,
                500000);
            DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(snapshot.Active.Single().QuestId, Is.EqualTo(result.QuestId));
            });
        }

        [Test]
        public void StoryCacheEvaluationOffer_ReusesExistingRuntimeQuestForTemplate()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-albion-evaluation-existing",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = true;
            DynamicQuestSeedNpc[] npcs =
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30),
                CreateNpc("forest spiderling", "target-cache", 1, level: 2, x: 502000, y: 500000)
            };

            DynamicQuestStoryCacheEvaluationOfferResult first = service.OfferStoryCacheTemplateForEvaluation(
                npcs,
                "story-cache-albion-evaluation-existing",
                "test");
            first.Quest.Tags = new[] { "template:story-cache-albion-evaluation-existing" };
            DynamicQuestStoryCacheEvaluationOfferResult second = service.OfferStoryCacheTemplateForEvaluation(
                npcs,
                "story-cache-albion-evaluation-existing",
                "test");

            Assert.Multiple(() =>
            {
                Assert.That(first.Success, Is.True);
                Assert.That(second.Success, Is.True);
                Assert.That(second.Existing, Is.True);
                Assert.That(second.QuestId, Is.EqualTo(first.QuestId));
                Assert.That(second.Quest.Tags, Does.Contain("dummy-evaluation-offer"));
                Assert.That(second.Quest.Tags, Does.Contain("region:1"));
                Assert.That(second.Quest.Tags, Does.Contain("trigger:region:1"));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests(), Has.Count.EqualTo(1));
            });
        }

        [Test]
        public void StoryCacheEvaluationOffer_TargetMissingMarksTemplateInactive()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-albion-missing-target",
                "Albion",
                1,
                "missing forest threat",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1));
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = true;

            DynamicQuestStoryCacheEvaluationOfferResult result = service.OfferStoryCacheTemplateForEvaluation(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30)
            }, "story-cache-albion-missing-target", "test");

            DbDynamicQuestTemplate saved = repository.Rows["story-cache-albion-missing-target"];

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.False);
                Assert.That(result.Message, Does.StartWith("target npc not found for template:"));
                Assert.That(result.OfferBlockReasons, Does.Contain("dummy_evaluation_target_missing"));
                Assert.That(saved.IsActive, Is.False);
                Assert.That(saved.DummyEvaluationCount, Is.EqualTo(1));
                Assert.That(saved.DummyEvaluationScore, Is.EqualTo(0));
                Assert.That(saved.DummyEvaluationJson, Does.Contain("\"failureCategory\":\"target_missing\""));
            });
        }

        [Test]
        public void StoryCacheSnapshot_UnknownRealmRegionBlocksReadyAndOfferEligibility()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-unknown-realm-region",
                "Unknown",
                352,
                "dungeon sentinel",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1));
            row.DummyEvaluationCount = 1;
            row.DummyEvaluationScore = 100;
            row.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":true,\"completed\":true,\"players\":3,\"okPlayers\":3,\"failureCategory\":\"passed\",\"skyrimGradeScore\":100,\"cinematicDensityScore\":100,\"actionSceneCohesionScore\":100,\"cinematicCatalogRoleVariety\":6,\"cinematicModelRoleFitScore\":100}";
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single(entry => entry.TemplateId == "story-cache-unknown-realm-region");

            Assert.Multiple(() =>
            {
                Assert.That(item.ReadyForUse, Is.False);
                Assert.That(item.OfferEligible, Is.False);
                Assert.That(item.Warnings, Does.Contain("story_cache_unknown_realm"));
                Assert.That(item.OfferBlockReasons, Does.Contain("story_cache_unknown_realm"));
            });
        }

        [Test]
        public void StoryCacheEvaluationOffer_RepairsDisabledMobGrowthBranchToTimeWindowOffer()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-albion-evaluation-mob-growth-disabled",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1));
            row.TagsJson = "[\"llm-story\",\"story-cache\",\"branch:mob-growth\",\"world-signal:mob-growth:killed:region:1\"]";
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = true;
            Properties.WORLDAI_MOB_GROWTH_ENABLED = false;

            DynamicQuestStoryCacheEvaluationOfferResult result = service.OfferStoryCacheTemplateForEvaluation(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30),
                CreateNpc("forest spiderling", "target-cache", 1, level: 2, x: 502000, y: 500000)
            }, "story-cache-albion-evaluation-mob-growth-disabled", "test");

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True);
                Assert.That(result.OfferBlockReasons, Does.Not.Contain("mob_growth_disabled"));
                Assert.That(result.OfferBlockReasons, Does.Contain("dummy_evaluation_required"));
                Assert.That(result.Quest.Tags, Does.Contain("branch:time-window"));
                Assert.That(result.Quest.Tags, Does.Contain("world-signal:time-window"));
                Assert.That(result.Quest.Tags, Does.Not.Contain("branch:mob-growth"));
                Assert.That(result.Quest.Tags, Does.Contain("trigger:region:1"));
                Assert.That(result.Quest.Tags, Does.Not.Contain("trigger:time-window"));
                Assert.That(repository.Rows["story-cache-albion-evaluation-mob-growth-disabled"].Trigger, Is.EqualTo("time-window"));
                Assert.That(repository.Rows["story-cache-albion-evaluation-mob-growth-disabled"].DummyEvaluationCount, Is.EqualTo(0));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests(), Has.Count.EqualTo(1));
            });

            bool accepted = DynamicQuestRuntimeService.Instance.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1,
                502000,
                500000);
            Assert.That(accepted, Is.True);
        }

        [Test]
        public void StoryCacheEvaluationOffer_AllowsExplicitReevaluationOfPreviousDummyFailure()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = true;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-albion-evaluation-difficulty-reeval",
                "Albion",
                1,
                "black wolf pup",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-albion-evaluation-difficulty-reeval",
                Score = 100,
                MinimumScore = 70,
                Passed = false,
                Completed = false,
                Players = 1,
                OkPlayers = 0,
                PlayerDeaths = 1,
                PresentationBeat = 4,
                NarrativeScene = 2,
                CinematicAction = 12,
                FailureCategory = "dummy_difficulty",
                Source = "unit-test"
            });

            DynamicQuestStoryCacheEvaluationOfferResult blocked = service.OfferStoryCacheTemplateForEvaluation(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30),
                CreateNpc("black wolf pup", "target-cache", 1, level: 2, x: 502000, y: 500000)
            }, "story-cache-albion-evaluation-difficulty-reeval", "test");
            DynamicQuestStoryCacheEvaluationOfferResult allowed = service.OfferStoryCacheTemplateForEvaluation(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30),
                CreateNpc("black wolf pup", "target-cache", 1, level: 2, x: 502000, y: 500000)
            }, "story-cache-albion-evaluation-difficulty-reeval", "test", allowFailedDummyEvaluation: true);

            Assert.Multiple(() =>
            {
                Assert.That(blocked.Success, Is.False);
                Assert.That(blocked.OfferBlockReasons, Does.Contain("dummy_evaluation_difficulty_failed"));
                Assert.That(allowed.Success, Is.True);
                Assert.That(allowed.Quest.Tags, Does.Contain("dummy-evaluation-offer"));
                Assert.That(allowed.Quest.Tags, Does.Contain("template:story-cache-albion-evaluation-difficulty-reeval"));
            });
        }

        [Test]
        public void StoryCacheEvaluationOffer_BlocksRelatedAutoAcceptTargetWithDummyDifficultyHistory()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = false;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate failed = CreateStoryRow(
                "story-cache-albion-evaluation-target-difficulty-failed",
                "Albion",
                1,
                "arachite prelate",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1));
            failed.DummyEvaluationCount = 1;
            failed.DummyEvaluationScore = 100;
            failed.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":false,\"completed\":false,\"players\":1,\"okPlayers\":0,\"playerDeaths\":1,\"failureCategory\":\"dummy_difficulty\"}";
            repository.Add(failed);
            repository.Add(CreateStoryRow(
                "story-cache-albion-evaluation-target-difficulty-sibling",
                "Albion",
                1,
                "arachite krigare",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheEvaluationOfferResult result = service.OfferStoryCacheTemplateForEvaluation(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1, level: 30),
                CreateNpc("arachite krigare", "target-cache", 1, level: 38, x: 502000, y: 500000)
            }, "story-cache-albion-evaluation-target-difficulty-sibling", "test");
            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem sibling = snapshot.Items.Single(item =>
                item.TemplateId == "story-cache-albion-evaluation-target-difficulty-sibling");

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.False);
                Assert.That(result.OfferBlockReasons, Does.Contain("dummy_evaluation_target_difficulty_history"));
                Assert.That(result.Message, Does.Contain("dummy_evaluation_target_difficulty_history"));
                Assert.That(sibling.ReadyForUse, Is.False);
                Assert.That(sibling.OfferEligible, Is.False);
                Assert.That(sibling.OfferBlockReasons, Does.Contain("dummy_evaluation_difficulty_failed"));
            });
        }

        [Test]
        public void StoryCacheEvaluationOffer_BlocksRelatedAutoAcceptRuntimeTargetWithDummyDifficultyHistory()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = false;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate failed = CreateStoryRow(
                "story-cache-midgard-evaluation-runtime-target-failed",
                "Midgard",
                100,
                "Arcsinimpede's Drone",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1));
            failed.DummyEvaluationCount = 1;
            failed.DummyEvaluationScore = 100;
            failed.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":false,\"completed\":false,\"players\":3,\"okPlayers\":0,\"playerDeaths\":2,\"targetName\":\"frost bound bear\",\"failureCategory\":\"dummy_difficulty\"}";
            repository.Add(failed);
            repository.Add(CreateStoryRow(
                "story-cache-midgard-evaluation-runtime-target-sibling",
                "Midgard",
                100,
                "Arcsinimpede",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1)));
            DynamicQuestRuntimeService.Instance.AddQuest(new DynamicQuestDefinition
            {
                Id = "runtime-midgard-runtime-target-sibling",
                Title = "얼음 숲의 미끼",
                OfferText = "도와주겠습니까?",
                ProgressText = "frost bound bear를 처치하세요.",
                FinishText = "고맙습니다.",
                StartRegionId = 100,
                TargetName = "frost bound bear",
                TargetCount = 1,
                MinLevel = 48,
                MaxLevel = 50,
                StartMode = DynamicQuestStartMode.AutoAccept,
                Tags = new[] { "template:story-cache-midgard-evaluation-runtime-target-sibling" }
            });
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheEvaluationOfferResult result = service.OfferStoryCacheTemplateForEvaluation(new[]
            {
                CreateNpc("Aud", "seed-npc-100", 100, level: 50),
                CreateNpc("frost bound bear", "target-cache", 100, level: 49, x: 502000, y: 500000)
            }, "story-cache-midgard-evaluation-runtime-target-sibling", "test");
            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem sibling = snapshot.Items.Single(item =>
                item.TemplateId == "story-cache-midgard-evaluation-runtime-target-sibling");

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.False);
                Assert.That(result.OfferBlockReasons, Does.Contain("dummy_evaluation_target_difficulty_history"));
                Assert.That(sibling.ReadyForUse, Is.False);
                Assert.That(sibling.OfferEligible, Is.False);
                Assert.That(sibling.OfferBlockReasons, Does.Contain("dummy_evaluation_difficulty_failed"));
            });
        }

        [Test]
        public void StoryCacheEvaluationOffer_PersistsDifficultyHistoryWhenRuntimeTargetIsRelated()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = true;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate failed = CreateStoryRow(
                "story-cache-midgard-bound-target-failed",
                "Midgard",
                100,
                "frost bound bear",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1));
            failed.DummyEvaluationCount = 1;
            failed.DummyEvaluationScore = 100;
            failed.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":false,\"completed\":false,\"players\":3,\"okPlayers\":0,\"playerDeaths\":2,\"failureCategory\":\"dummy_difficulty\"}";
            repository.Add(failed);
            repository.Add(CreateStoryRow(
                "story-cache-midgard-bound-target-sibling",
                "Midgard",
                100,
                "Arcsinimpede",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1)));
            DynamicQuestRuntimeService.Instance.AddQuest(new DynamicQuestDefinition
            {
                Id = "runtime-midgard-bound-target-sibling",
                Title = "얼음 숲의 미끼",
                OfferText = "도와주겠습니까?",
                ProgressText = "frost bound bear를 처치하세요.",
                FinishText = "고맙습니다.",
                StartRegionId = 100,
                TargetName = "frost bound bear",
                TargetCount = 1,
                MinLevel = 48,
                MaxLevel = 50,
                StartMode = DynamicQuestStartMode.AutoAccept,
                Tags = new[] { "template:story-cache-midgard-bound-target-sibling" }
            });
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheEvaluationOfferResult result = service.OfferStoryCacheTemplateForEvaluation(new[]
            {
                CreateNpc("Aud", "seed-npc-100", 100, level: 50),
                CreateNpc("frost bound bear", "target-cache", 100, level: 49, x: 502000, y: 500000)
            }, "story-cache-midgard-bound-target-sibling", "test");

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.False);
                Assert.That(result.OfferBlockReasons, Does.Contain("dummy_evaluation_target_difficulty_history"));
                Assert.That(repository.Rows["story-cache-midgard-bound-target-sibling"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-midgard-bound-target-sibling"].DummyEvaluationCount, Is.EqualTo(1));
                Assert.That(repository.Rows["story-cache-midgard-bound-target-sibling"].DummyEvaluationJson, Does.Contain("\"failureCategory\":\"dummy_difficulty\""));
                Assert.That(repository.Rows["story-cache-midgard-bound-target-sibling"].DummyEvaluationJson, Does.Contain("frost bound bear"));
            });
        }

        [Test]
        public void StoryCacheOfferEligibility_AllowsPassingTemplateDespiteRelatedDifficultyHistory()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = true;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate failed = CreateStoryRow(
                "story-cache-midgard-family-difficulty-failed",
                "Midgard",
                100,
                "arachite impaler",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-2));
            failed.DummyEvaluationCount = 1;
            failed.DummyEvaluationScore = 100;
            failed.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":false,\"completed\":false,\"players\":3,\"okPlayers\":0,\"failureCategory\":\"dummy_difficulty\"}";
            repository.Add(failed);
            DbDynamicQuestTemplate passed = CreateStoryRow(
                "story-cache-midgard-family-passed",
                "Midgard",
                100,
                "arachite prelate",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1));
            passed.DummyEvaluationCount = 1;
            passed.DummyEvaluationScore = 100;
            passed.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":true,\"completed\":true,\"players\":3,\"okPlayers\":3,\"failureCategory\":\"passed\",\"skyrimGradeScore\":100,\"cinematicDensityScore\":100,\"actionSceneCohesionScore\":100,\"cinematicCatalogRoleVariety\":5,\"cinematicModelRoleFitScore\":100}";
            repository.Add(passed);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single(row =>
                row.TemplateId == "story-cache-midgard-family-passed");

            Assert.Multiple(() =>
            {
                Assert.That(item.ReadyForUse, Is.True);
                Assert.That(item.OfferEligible, Is.True);
                Assert.That(item.OfferBlockReasons, Does.Not.Contain("dummy_evaluation_target_difficulty_history"));
            });
        }

        [Test]
        public void StoryCacheOfferEligibility_DoesNotTreatGenericAdjectiveAsTargetFamily()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = true;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate failed = CreateStoryRow(
                "story-cache-albion-ancient-basilisk-failed",
                "Albion",
                1,
                "ancient basilisk",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-2));
            failed.DummyEvaluationCount = 1;
            failed.DummyEvaluationScore = 100;
            failed.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":false,\"completed\":false,\"players\":3,\"okPlayers\":0,\"failureCategory\":\"dummy_difficulty\"}";
            repository.Add(failed);
            DbDynamicQuestTemplate passed = CreateStoryRow(
                "story-cache-albion-ancient-brownie-passed",
                "Albion",
                1,
                "ancient brownie",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1));
            passed.DummyEvaluationCount = 1;
            passed.DummyEvaluationScore = 100;
            passed.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":true,\"completed\":true,\"players\":3,\"okPlayers\":3,\"failureCategory\":\"passed\",\"skyrimGradeScore\":100,\"cinematicDensityScore\":100,\"actionSceneCohesionScore\":100,\"cinematicCatalogRoleVariety\":6,\"cinematicModelRoleFitScore\":100}";
            repository.Add(passed);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem passedItem = snapshot.Items.Single(item =>
                item.TemplateId == "story-cache-albion-ancient-brownie-passed");

            Assert.Multiple(() =>
            {
                Assert.That(passedItem.ReadyForUse, Is.True);
                Assert.That(passedItem.OfferEligible, Is.True);
                Assert.That(passedItem.OfferBlockReasons, Does.Not.Contain("dummy_evaluation_target_difficulty_history"));
            });
        }

        [Test]
        public void StoryCacheSnapshot_ExposesRuntimeAndDummyEvaluationTargetNames()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-albion-rebound-target",
                "Albion",
                1,
                "ancient brownie",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1));
            row.DummyEvaluationCount = 1;
            row.DummyEvaluationScore = 100;
            row.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":true,\"completed\":true,\"players\":3,\"okPlayers\":3,\"targetName\":\"dryad twig\",\"failureCategory\":\"passed\",\"skyrimGradeScore\":100,\"cinematicDensityScore\":100,\"actionSceneCohesionScore\":100,\"cinematicCatalogRoleVariety\":6,\"cinematicModelRoleFitScore\":100}";
            repository.Add(row);
            DynamicQuestRuntimeService.Instance.AddQuest(new DynamicQuestDefinition
            {
                Id = "runtime-rebound-target",
                Title = "다시 묶인 표적",
                OfferText = "도와주겠습니까?",
                ProgressText = "dappled lynx를 처치하세요.",
                FinishText = "고맙습니다.",
                StartRegionId = 1,
                TargetName = "dappled lynx",
                TargetCount = 1,
                MinLevel = 1,
                MaxLevel = 8,
                StartMode = DynamicQuestStartMode.AutoAccept,
                Tags = new[] { "template:story-cache-albion-rebound-target" }
            });
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheItem item = service.GetStoryCacheSnapshot(10, includeText: false).Items.Single();

            Assert.Multiple(() =>
            {
                Assert.That(item.TargetNameHint, Is.EqualTo("ancient brownie"));
                Assert.That(item.RuntimeTargetName, Is.EqualTo("dappled lynx"));
                Assert.That(item.DummyEvaluationTargetName, Is.EqualTo("dryad twig"));
                Assert.That(item.EffectiveTargetName, Is.EqualTo("dappled lynx"));
            });
        }

        [Test]
        public void StoryCacheOfferEligibility_BlocksPassedLegacyEvaluationWithoutModernCinematicMetrics()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = true;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-legacy-passed-without-cinematic-metrics",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-1));
            row.DummyEvaluationCount = 1;
            row.DummyEvaluationScore = 100;
            row.DummyEvaluationJson = "{\"source\":\"run-dummy-dynamic-quest-matrix\",\"score\":100,\"minimumScore\":70,\"passed\":true,\"completed\":true,\"players\":3,\"okPlayers\":3,\"failureCategory\":\"passed\",\"skyrimGradeScore\":100,\"cinematicDensityScore\":100}";
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single();

            Assert.Multiple(() =>
            {
                Assert.That(item.ReadyForUse, Is.False);
                Assert.That(item.OfferEligible, Is.False);
                Assert.That(item.OfferBlockReasons, Does.Contain("dummy_evaluation_cinematic_metrics_missing"));
                Assert.That(snapshot.NotReadyByReason["dummy_evaluation_cinematic_metrics_missing"], Is.EqualTo(1));
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
        public void Seed_StoryCacheOffersRepairLegacyItemAcquiredTriggerBeforeReadyGate()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate legacy = CreateStoryRow(
                "story-cache-hibernia-auto-legacy-item-trigger",
                "Hibernia",
                200,
                "bogling scout",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-3));
            legacy.Trigger = "time-window:dawn";
            legacy.TagsJson = "[\"llm-story\",\"branch:item-acquired\",\"world-signal:item-acquired\"]";
            repository.Add(legacy);
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
            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem repairedItem = snapshot.Items.Single(item => item.TemplateId == "story-cache-hibernia-auto-legacy-item-trigger");
            DynamicQuestDefinition autoOffer = DynamicQuestRuntimeService.Instance.GetQuests()
                .Single(quest => quest.StartMode == DynamicQuestStartMode.AutoAccept);

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(2));
                Assert.That(summary.StoryCacheOffered, Is.EqualTo(1));
                Assert.That(autoOffer.TargetName, Is.EqualTo("bogling scout"));
                Assert.That(autoOffer.Tags, Does.Contain("branch:item-acquired"));
                Assert.That(autoOffer.Tags, Does.Contain("world-signal:item-acquired"));
                Assert.That(repository.Rows["story-cache-hibernia-auto-legacy-item-trigger"].Trigger, Is.EqualTo(string.Empty));
                Assert.That(repository.Rows["story-cache-hibernia-auto-legacy-item-trigger"].LastBindingKey, Is.Not.Empty);
                Assert.That(repairedItem.ReadyForUse, Is.True);
                Assert.That(repairedItem.Warnings, Is.Empty);
                Assert.That(snapshot.WarningsByReason.Keys, Does.Not.Contain("autoaccept_item_acquired_legacy_trigger"));
            });
        }

        [Test]
        public void Seed_StoryCacheOffersRepairLegacyAutoAcceptTimeWindowBeforeOffer()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate legacy = CreateStoryRow(
                "story-cache-midgard-auto-legacy-night-window",
                "Midgard",
                100,
                "young tomte",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-3));
            legacy.Trigger = "time-window:night";
            legacy.TagsJson = "[\"llm-story\",\"story-cache\",\"codex-curated\",\"branch:time-window\",\"world-signal:time-window:night\",\"story-archetype:witness-conspiracy\"]";
            repository.Add(legacy);
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
                CreateNpc("young tomte", "target-auto-cache-mid", 100, level: 3)
            }, options);
            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestDefinition autoOffer = DynamicQuestRuntimeService.Instance.GetQuests()
                .Single(quest => quest.StartMode == DynamicQuestStartMode.AutoAccept);

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(2));
                Assert.That(summary.StoryCacheOffered, Is.EqualTo(1));
                Assert.That(autoOffer.TargetName, Is.EqualTo("young tomte"));
                Assert.That(autoOffer.Tags, Does.Contain("branch:time-window"));
                Assert.That(autoOffer.Tags, Does.Contain("world-signal:time-window"));
                Assert.That(repository.Rows["story-cache-midgard-auto-legacy-night-window"].Trigger, Is.EqualTo("time-window"));
                Assert.That(repository.Rows["story-cache-midgard-auto-legacy-night-window"].TagsJson, Does.Contain("world-signal:time-window"));
                Assert.That(repository.Rows["story-cache-midgard-auto-legacy-night-window"].TagsJson, Does.Not.Contain("world-signal:time-window:night"));
                Assert.That(snapshot.Items.Single().ReadyForUse, Is.True);
            });
        }

        [Test]
        public void Seed_StoryCacheOffersRepairCodexCuratedTagsBeforeOffer()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate legacy = CreateStoryRow(
                "story-cache-hibernia-auto-codex-missing-archetype",
                "Hibernia",
                200,
                "bogling scout",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-3));
            legacy.Source = "codex-curated";
            legacy.StoryProvider = "codex-curated";
            legacy.StoryModel = "hand-authored-cinematic-v7";
            legacy.TagsJson = "[\"llm-story\",\"story-cache\",\"codex-curated\",\"branch:item-acquired\",\"world-signal:item-acquired\",\"llm-provider:codex-curated\",\"llm-model:hand-authored-cinematic-v6\",\"llm-model:hand-authored-cinematic-v7\",\"story-title-variant:v2\",\"story-title-variant:v3\",\"story-archetype:witness-conspiracy\",\"story-archetype:relic-echo\"]";
            repository.Add(legacy);
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
                Assert.That(repository.Rows["story-cache-hibernia-auto-codex-missing-archetype"].TagsJson, Does.Contain("story-archetype:relic-echo"));
                Assert.That(repository.Rows["story-cache-hibernia-auto-codex-missing-archetype"].TagsJson, Does.Contain("llm-model:hand-authored-cinematic-v15"));
                Assert.That(repository.Rows["story-cache-hibernia-auto-codex-missing-archetype"].TagsJson, Does.Not.Contain("llm-model:hand-authored-cinematic-v6"));
                Assert.That(repository.Rows["story-cache-hibernia-auto-codex-missing-archetype"].TagsJson, Does.Not.Contain("story-title-variant:v2"));
                Assert.That(repository.Rows["story-cache-hibernia-auto-codex-missing-archetype"].TagsJson, Does.Not.Contain("story-archetype:witness-conspiracy"));
                Assert.That(repository.Rows["story-cache-hibernia-auto-codex-missing-archetype"].TagsJson, Does.Contain("story-family:story-cache-hibernia-auto-codex-missing-archetype"));
                Assert.That(repository.Rows["story-cache-hibernia-auto-codex-missing-archetype"].TagsJson, Does.Contain("story-arc:motive"));
                Assert.That(repository.Rows["story-cache-hibernia-auto-codex-missing-archetype"].TagsJson, Does.Contain("story-arc:conflict"));
                Assert.That(repository.Rows["story-cache-hibernia-auto-codex-missing-archetype"].TagsJson, Does.Contain("story-arc:reversal"));
                Assert.That(repository.Rows["story-cache-hibernia-auto-codex-missing-archetype"].TagsJson, Does.Contain("story-arc:consequence"));
                Assert.That(repository.Rows["story-cache-hibernia-auto-codex-missing-archetype"].TagsJson, Does.Contain("story-chain:"));
                Assert.That(repository.Rows["story-cache-hibernia-auto-codex-missing-archetype"].TagsJson, Does.Contain("story-episode:1/3"));
                Assert.That(repository.Rows["story-cache-hibernia-auto-codex-missing-archetype"].TagsJson, Does.Contain("arc-step:1/3"));
                Assert.That(autoOffer.Tags, Does.Contain("story-archetype:relic-echo"));
                Assert.That(autoOffer.Tags, Does.Contain("story-family:story-cache-hibernia-auto-codex-missing-archetype"));
                Assert.That(autoOffer.Tags, Does.Contain("story-arc:consequence"));
                Assert.That(autoOffer.Tags.Any(tag => tag.StartsWith("story-chain:", StringComparison.OrdinalIgnoreCase)), Is.True);
                Assert.That(autoOffer.Tags, Does.Contain("story-episode:1/3"));
                Assert.That(autoOffer.Tags, Does.Contain("arc-step:1/3"));
                Assert.That(autoOffer.Tags, Does.Contain("codex-curated"));
            });
        }

        [Test]
        public void Seed_StoryCacheOffersRepairCodexCuratedHighLevelStarterTagBeforeOffer()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate legacy = CreateStoryRow(
                "story-cache-albion-auto-codex-high-starter",
                "Albion",
                1,
                "albion waylayer",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-3));
            legacy.Source = "codex-curated";
            legacy.StoryProvider = "codex-curated";
            legacy.StoryModel = "hand-authored-cinematic-v7";
            legacy.MinLevel = 42;
            legacy.MaxLevel = 46;
            legacy.TagsJson = "[\"starter\",\"llm-story\",\"story-cache\",\"codex-curated\",\"branch:time-window\",\"world-signal:time-window\",\"llm-provider:codex-curated\",\"llm-model:hand-authored-cinematic-v7\",\"story-title-variant:v2\",\"story-archetype:border-omen\"]";
            repository.Add(legacy);
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
                CreateNpc("albion waylayer", "target-auto-cache-alb", 1, level: 44)
            }, options);
            DynamicQuestDefinition autoOffer = DynamicQuestRuntimeService.Instance.GetQuests()
                .Single(quest => quest.Tags.Contains("template:story-cache-albion-auto-codex-high-starter"));

            Assert.Multiple(() =>
            {
                Assert.That(summary.Created, Is.EqualTo(2));
                Assert.That(summary.StoryCacheOffered, Is.EqualTo(1));
                Assert.That(repository.Rows["story-cache-albion-auto-codex-high-starter"].TagsJson, Does.Not.Contain("\"starter\""));
                Assert.That(repository.Rows["story-cache-albion-auto-codex-high-starter"].TagsJson, Does.Contain("llm-model:hand-authored-cinematic-v15"));
                Assert.That(autoOffer.Tags, Does.Not.Contain("starter"));
                Assert.That(autoOffer.Tags, Does.Contain("codex-curated"));
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
                    "black wolf pup",
                    "young sveawolf",
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
            repository.Rows["story-high-branch"].StoryPresentationJson = "[{\"nodeId\":\"talk\",\"trigger\":\"OnNpcInteract\",\"speaker\":\"StartNpc\",\"text\":\"숨겨야 할 대사\",\"emotion\":\"fear\",\"emote\":\"Shiver\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"ambush_wave\",\"formation\":\"ambush\",\"actorCount\":12,\"delayMs\":900}]";
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
                Assert.That(branch.PresentationBeats.Single().CinematicAction, Is.EqualTo("ambush_reveal"));
                Assert.That(branch.PresentationBeats.Single().SceneRole, Is.EqualTo("ambush_wave"));
                Assert.That(branch.PresentationBeats.Single().Formation, Is.EqualTo("ambush"));
                Assert.That(branch.PresentationBeats.Single().ActorCount, Is.EqualTo(12));
                Assert.That(branch.PresentationBeats.Single().DelayMs, Is.EqualTo(900));
                Assert.That(branch.CurrentQuality.TotalScore, Is.LessThanOrEqualTo(low.CurrentQuality.TotalScore));
                Assert.That(low.StoryModel, Is.EqualTo("gemini-3.5-flash"));
                Assert.That(snapshot.Items.Select(item => item.TemplateId), Does.Not.Contain("non-story-active-row"));
                Assert.That(repository.AddCalls, Is.EqualTo(addCalls));
                Assert.That(repository.SaveCalls, Is.EqualTo(saveCalls));
                Assert.That(repository.Rows["story-high-branch"].LastBindingKey, Is.EqualTo(string.Empty));
            });
        }

        [Test]
        public void StoryCacheSnapshot_BlocksBranchRowsWithoutChoiceSelectedSetPiece()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-branch-missing-choice-setpiece",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-2));
            row.TagsJson = "[\"llm-story\",\"story-cache\",\"branch:time-window\",\"world-signal:time-window\"]";
            row.StoryQualityJson = "{\"totalScore\":100,\"structureScore\":15,\"koreanScore\":12,\"objectiveScore\":20,\"immersionScore\":15,\"narrativeScore\":12,\"presentationScore\":8,\"rebindabilityScore\":15,\"safetyScore\":15,\"diversityScore\":10,\"reasons\":[\"narrative_scene\",\"presentation_beat\"]}";
            row.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"수도원 길목의 경고\",\"body\":\"{{target}} 위협 뒤에 이상한 시간의 흔적이 남아 있습니다.\",\"journalEntry\":\"{{target}} 위협을 조사한다.\",\"mood\":\"urgent\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            row.StoryPresentationJson = "[{\"nodeId\":\"talk\",\"trigger\":\"OnNpcInteract\",\"speaker\":\"StartNpc\",\"text\":\"밤마다 같은 발자국이 되돌아옵니다.\",\"emotion\":\"fear\",\"emote\":\"Shiver\",\"cinematicAction\":\"witness_point\",\"sceneRole\":\"contract_witness\",\"formation\":\"escort\",\"actorCount\":4}]";
            repository.Add(row);
            int saveCalls = repository.SaveCalls;
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single();

            Assert.Multiple(() =>
            {
                Assert.That(item.ReadyForUse, Is.False);
                Assert.That(snapshot.ReadyActive, Is.EqualTo(0));
                Assert.That(snapshot.NotReadyByReason["choice_presentation_setpiece_missing"], Is.EqualTo(1));
                Assert.That(repository.SaveCalls, Is.EqualTo(saveCalls));
            });
        }

        [Test]
        public void StoryCacheSnapshot_BlocksBranchRowsWithoutWorldSignalSetPiece()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-branch-missing-world-signal-setpiece",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-2));
            row.TagsJson = "[\"llm-story\",\"story-cache\",\"branch:time-window\",\"world-signal:time-window\"]";
            row.StoryQualityJson = "{\"totalScore\":100,\"structureScore\":15,\"koreanScore\":12,\"objectiveScore\":20,\"immersionScore\":15,\"narrativeScore\":12,\"presentationScore\":8,\"rebindabilityScore\":15,\"safetyScore\":15,\"diversityScore\":10,\"reasons\":[\"narrative_scene\",\"presentation_beat\"]}";
            row.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"수도원 길목의 경고\",\"body\":\"{{target}} 위협 뒤에 이상한 시간의 흔적이 남아 있습니다.\",\"journalEntry\":\"{{target}} 위협을 조사한다.\",\"mood\":\"urgent\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            row.StoryPresentationJson = "[{\"nodeId\":\"choice\",\"trigger\":\"OnChoiceSelected\",\"speaker\":\"System\",\"text\":\"선택의 여파가 남습니다.\",\"emotion\":\"urgency\",\"emote\":\"Point\",\"cinematicAction\":\"defender_intercept\",\"sceneRole\":\"choice_fallout\",\"formation\":\"escort\",\"actorCount\":6}]";
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single();

            Assert.Multiple(() =>
            {
                Assert.That(item.ReadyForUse, Is.False);
                Assert.That(snapshot.ReadyActive, Is.EqualTo(0));
                Assert.That(snapshot.NotReadyByReason["world_signal_presentation_setpiece_missing"], Is.EqualTo(1));
            });
        }

        [Test]
        public void WorldSignalSetPiece_UsesBranchSpecificCinematicActions()
        {
            MethodInfo builder = typeof(DynamicQuestSeedService).GetMethod(
                "BuildWorldSignalSetPieceBeat",
                BindingFlags.NonPublic | BindingFlags.Static);

            Assert.That(builder, Is.Not.Null);

            DynamicQuestPresentationBeat growth = (DynamicQuestPresentationBeat)builder.Invoke(
                null,
                new object[] { "mob-growth:killed:region:1" });
            DynamicQuestPresentationBeat item = (DynamicQuestPresentationBeat)builder.Invoke(
                null,
                new object[] { "item-acquired:id:ancient-relic-01" });
            DynamicQuestPresentationBeat time = (DynamicQuestPresentationBeat)builder.Invoke(
                null,
                new object[] { "time-window:night" });

            Assert.Multiple(() =>
            {
                Assert.That(growth.Trigger, Is.EqualTo("OnWorldSignal"));
                Assert.That(growth.CinematicAction, Is.EqualTo("guard_advance"));
                Assert.That(growth.SceneRole, Is.EqualTo("growth_counterline"));
                Assert.That(growth.Formation, Is.EqualTo("line"));
                Assert.That(growth.ActorCount, Is.GreaterThanOrEqualTo(7));

                Assert.That(item.CinematicAction, Is.EqualTo("witness_point"));
                Assert.That(item.SceneRole, Is.EqualTo("clue_witness"));
                Assert.That(item.Formation, Is.EqualTo("escort"));
                Assert.That(item.Speaker, Is.EqualTo("Companion"));

                Assert.That(time.CinematicAction, Is.EqualTo("ritual_interrupt"));
                Assert.That(time.SceneRole, Is.EqualTo("signal_reveal"));
                Assert.That(time.Formation, Is.EqualTo("ring"));
            });
        }

        [Test]
        public void StoryCacheSnapshot_BlocksBranchRowsWithoutChoiceNarrativeScene()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-branch-missing-choice-narrative",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-2));
            row.TagsJson = "[\"llm-story\",\"story-cache\",\"branch:time-window\",\"world-signal:time-window\"]";
            row.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"수도원 길목의 경고\",\"body\":\"{{target}} 위협 뒤에 이상한 시간의 흔적이 남아 있습니다.\",\"journalEntry\":\"{{target}} 위협을 조사한다.\",\"mood\":\"urgent\",\"revealPolicy\":\"FirstSeenOnly\"},{\"nodeId\":\"observe_signal\",\"sceneType\":\"Aftermath\",\"title\":\"두 번째 신호\",\"body\":\"신호가 길을 드러냅니다.\",\"journalEntry\":\"신호를 확인한다.\",\"mood\":\"mysterious\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            row.StoryPresentationJson = "[{\"nodeId\":\"choice\",\"trigger\":\"OnChoiceSelected\",\"speaker\":\"System\",\"text\":\"선택의 여파가 남습니다.\",\"emotion\":\"urgency\",\"emote\":\"Point\",\"cinematicAction\":\"defender_intercept\",\"sceneRole\":\"choice_fallout\",\"formation\":\"escort\",\"actorCount\":6},{\"nodeId\":\"observe_signal\",\"trigger\":\"OnWorldSignal\",\"speaker\":\"System\",\"text\":\"신호가 현장을 흔듭니다.\",\"emotion\":\"urgency\",\"emote\":\"Point\",\"cinematicAction\":\"ritual_interrupt\",\"sceneRole\":\"signal_reveal\",\"formation\":\"ring\",\"actorCount\":5}]";
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.Items.Single().ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason["choice_narrative_scene_missing"], Is.EqualTo(1));
            });
        }

        [Test]
        public void StoryCacheSnapshot_BlocksBranchRowsWithoutWorldSignalNarrativeScene()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-branch-missing-world-signal-narrative",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-2));
            row.TagsJson = "[\"llm-story\",\"story-cache\",\"branch:time-window\",\"world-signal:time-window\"]";
            row.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"수도원 길목의 경고\",\"body\":\"{{target}} 위협 뒤에 이상한 시간의 흔적이 남아 있습니다.\",\"journalEntry\":\"{{target}} 위협을 조사한다.\",\"mood\":\"urgent\",\"revealPolicy\":\"FirstSeenOnly\"},{\"nodeId\":\"choice\",\"sceneType\":\"Choice\",\"title\":\"선택\",\"body\":\"남은 표식을 어떻게 다룰지 선택한다.\",\"journalEntry\":\"선택해야 한다.\",\"mood\":\"mysterious\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            row.StoryPresentationJson = "[{\"nodeId\":\"choice\",\"trigger\":\"OnChoiceSelected\",\"speaker\":\"System\",\"text\":\"선택의 여파가 남습니다.\",\"emotion\":\"urgency\",\"emote\":\"Point\",\"cinematicAction\":\"defender_intercept\",\"sceneRole\":\"choice_fallout\",\"formation\":\"escort\",\"actorCount\":6},{\"nodeId\":\"observe_signal\",\"trigger\":\"OnWorldSignal\",\"speaker\":\"System\",\"text\":\"신호가 현장을 흔듭니다.\",\"emotion\":\"urgency\",\"emote\":\"Point\",\"cinematicAction\":\"ritual_interrupt\",\"sceneRole\":\"signal_reveal\",\"formation\":\"ring\",\"actorCount\":5}]";
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.Items.Single().ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason["world_signal_narrative_scene_missing"], Is.EqualTo(1));
            });
        }

        [Test]
        public void StoryCacheSnapshot_BlocksCinematicRowsWithoutActionVariety()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-cinematic-low-action-variety",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                100,
                DateTime.UtcNow.AddHours(-2));
            row.TagsJson = "[\"llm-story\",\"story-cache\",\"story-cinematic\",\"scene-director\",\"cinematic-actors:ambush_reveal:8\"]";
            row.StoryQualityJson = "{\"totalScore\":100,\"structureScore\":15,\"koreanScore\":12,\"objectiveScore\":20,\"immersionScore\":15,\"narrativeScore\":12,\"presentationScore\":8,\"rebindabilityScore\":15,\"safetyScore\":15,\"diversityScore\":10,\"reasons\":[\"narrative_scene\",\"presentation_beat\"]}";
            row.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"숲의 숨죽임\",\"body\":\"{{start_npc}}은 숲 가장자리의 부러진 표식과 젖은 발자국을 가리키며 {{target}} 위협이 마을 가까이 왔다고 말합니다.\",\"journalEntry\":\"숲 가장자리의 {{target}} 위협을 조사한다.\",\"mood\":\"ominous\",\"revealPolicy\":\"FirstSeenOnly\"},{\"nodeId\":\"return\",\"sceneType\":\"Return\",\"title\":\"다시 켜진 길목\",\"body\":\"위협이 사라지자 경비들이 쓰러진 표식을 다시 세우고 길목의 횃불을 밝힙니다.\",\"journalEntry\":\"{{start_npc}}에게 돌아가 결과를 전한다.\",\"mood\":\"relieved\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            row.StoryPresentationJson = "[" +
                "{\"nodeId\":\"talk\",\"trigger\":\"OnNpcInteract\",\"speaker\":\"StartNpc\",\"text\":\"저 발자국은 방금 생긴 겁니다.\",\"emotion\":\"fear\",\"emote\":\"Shiver\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"contract_witness\",\"formation\":\"ambush\",\"actorCount\":8}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"speaker\":\"System\",\"text\":\"경비들이 길목을 막아섭니다.\",\"emotion\":\"urgency\",\"emote\":\"Point\",\"cinematicAction\":\"defender_intercept\",\"sceneRole\":\"escape_intercept\",\"formation\":\"line\",\"actorCount\":6,\"delayMs\":700}," +
                "{\"nodeId\":\"return\",\"trigger\":\"OnComplete\",\"speaker\":\"StartNpc\",\"text\":\"길목의 횃불이 다시 섰습니다.\",\"emotion\":\"gratitude\",\"emote\":\"Bow\",\"cinematicAction\":\"defender_intercept\",\"sceneRole\":\"debrief_guard\",\"formation\":\"escort\",\"actorCount\":4,\"delayMs\":1200}" +
                "]";
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.Items.Single().ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason["cinematic_action_variety_missing"], Is.EqualTo(1));
            });
        }

        [Test]
        public void StoryCacheSnapshot_BlocksCinematicRowsWithOnlyThreeExecutableSetPieces()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-cinematic-three-set-pieces",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                100,
                DateTime.UtcNow.AddHours(-2));
            row.TagsJson = "[\"llm-story\",\"story-cache\",\"story-cinematic\",\"scene-director\",\"cinematic-actors:ambush_reveal:8\",\"cinematic-actors:defender_intercept:6\",\"cinematic-actors:scout_retreat:4\"]";
            row.StoryQualityJson = "{\"totalScore\":100,\"structureScore\":15,\"koreanScore\":12,\"objectiveScore\":20,\"immersionScore\":15,\"narrativeScore\":12,\"presentationScore\":8,\"rebindabilityScore\":15,\"safetyScore\":15,\"diversityScore\":10,\"reasons\":[\"narrative_scene\",\"presentation_beat\"]}";
            row.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"숲의 숨죽임\",\"body\":\"{{start_npc}}은 숲 가장자리의 부러진 표식과 젖은 발자국을 가리키며 {{target}} 위협이 마을 가까이 왔다고 말합니다.\",\"journalEntry\":\"숲 가장자리의 {{target}} 위협을 조사한다.\",\"mood\":\"ominous\",\"revealPolicy\":\"FirstSeenOnly\"},{\"nodeId\":\"return\",\"sceneType\":\"Return\",\"title\":\"다시 켜진 길목\",\"body\":\"위협이 사라지자 경비들이 쓰러진 표식을 다시 세우고 길목의 횃불을 밝힙니다.\",\"journalEntry\":\"{{start_npc}}에게 돌아가 결과를 전한다.\",\"mood\":\"relieved\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            row.StoryPresentationJson = "[" +
                "{\"nodeId\":\"talk\",\"trigger\":\"OnNpcInteract\",\"speaker\":\"StartNpc\",\"text\":\"저 발자국은 방금 생긴 겁니다.\",\"emotion\":\"fear\",\"emote\":\"Shiver\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"contract_witness\",\"formation\":\"ambush\",\"actorCount\":8}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"speaker\":\"System\",\"text\":\"경비들이 길목을 막아섭니다.\",\"emotion\":\"urgency\",\"emote\":\"Point\",\"cinematicAction\":\"defender_intercept\",\"sceneRole\":\"escape_intercept\",\"formation\":\"line\",\"actorCount\":6,\"delayMs\":700}," +
                "{\"nodeId\":\"return\",\"trigger\":\"OnComplete\",\"speaker\":\"StartNpc\",\"text\":\"망보던 자가 뒤로 물러납니다.\",\"emotion\":\"gratitude\",\"emote\":\"Bow\",\"cinematicAction\":\"scout_retreat\",\"sceneRole\":\"lookout_escape\",\"formation\":\"escape\",\"actorCount\":4,\"delayMs\":1200}" +
                "]";
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.Items.Single().ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason["cinematic_set_piece_count_missing"], Is.EqualTo(1));
                Assert.That(snapshot.NotReadyByReason.ContainsKey("cinematic_action_variety_missing"), Is.False);
            });
        }

        [Test]
        public void StoryCacheSnapshot_BlocksCinematicRowsWithoutTriggerVariety()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-cinematic-low-trigger-variety",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                100,
                DateTime.UtcNow.AddHours(-2));
            row.TagsJson = "[\"llm-story\",\"story-cache\",\"story-cinematic\",\"scene-director\",\"cinematic-actors:ambush_reveal:8\",\"cinematic-actors:defender_intercept:6\",\"cinematic-actors:scout_retreat:4\",\"cinematic-actors:ritual_interrupt:5\"]";
            row.StoryQualityJson = "{\"totalScore\":100,\"structureScore\":15,\"koreanScore\":12,\"objectiveScore\":20,\"immersionScore\":15,\"narrativeScore\":12,\"presentationScore\":8,\"rebindabilityScore\":15,\"safetyScore\":15,\"diversityScore\":10,\"reasons\":[\"narrative_scene\",\"presentation_beat\"]}";
            row.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"숲의 숨죽임\",\"body\":\"{{start_npc}}은 숲 가장자리의 부러진 표식과 젖은 발자국을 가리키며 {{target}} 위협이 마을 가까이 왔다고 말합니다.\",\"journalEntry\":\"숲 가장자리의 {{target}} 위협을 조사한다.\",\"mood\":\"ominous\",\"revealPolicy\":\"FirstSeenOnly\"},{\"nodeId\":\"return\",\"sceneType\":\"Return\",\"title\":\"다시 켜진 길목\",\"body\":\"위협이 사라지자 경비들이 쓰러진 표식을 다시 세우고 길목의 횃불을 밝힙니다.\",\"journalEntry\":\"{{start_npc}}에게 돌아가 결과를 전한다.\",\"mood\":\"relieved\",\"revealPolicy\":\"FirstSeenOnly\"}]";
            row.StoryPresentationJson = "[" +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"speaker\":\"System\",\"text\":\"매복 병력이 모습을 드러냅니다.\",\"emotion\":\"urgency\",\"emote\":\"Point\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"ambush_wave\",\"formation\":\"ambush\",\"actorCount\":8}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"speaker\":\"System\",\"text\":\"경비가 탈출 경로를 막습니다.\",\"emotion\":\"urgency\",\"emote\":\"Point\",\"cinematicAction\":\"defender_intercept\",\"sceneRole\":\"escape_intercept\",\"formation\":\"line\",\"actorCount\":6,\"delayMs\":700}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"speaker\":\"System\",\"text\":\"망보던 자가 후퇴합니다.\",\"emotion\":\"urgency\",\"emote\":\"Point\",\"cinematicAction\":\"scout_retreat\",\"sceneRole\":\"lookout_escape\",\"formation\":\"escape\",\"actorCount\":4,\"delayMs\":1200}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"speaker\":\"System\",\"text\":\"의식 표식이 끊깁니다.\",\"emotion\":\"urgency\",\"emote\":\"Point\",\"cinematicAction\":\"ritual_interrupt\",\"sceneRole\":\"ritual_break\",\"formation\":\"ring\",\"actorCount\":5,\"delayMs\":1600}" +
                "]";
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.Items.Single().ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason["cinematic_trigger_variety_missing"], Is.EqualTo(1));
                Assert.That(snapshot.NotReadyByReason.ContainsKey("cinematic_set_piece_count_missing"), Is.False);
                Assert.That(snapshot.NotReadyByReason.ContainsKey("cinematic_action_variety_missing"), Is.False);
            });
        }

        [Test]
        public void StoryCacheSnapshot_ReportsLegacyTriggerAndBranchSignalWarningsWithoutMutation()
        {
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate legacyTrigger = CreateStoryRow(
                "story-legacy-item-trigger",
                "Hibernia",
                200,
                "lough wolf cadger",
                DynamicQuestStartMode.AutoAccept,
                94,
                DateTime.UtcNow.AddHours(-3));
            legacyTrigger.Trigger = "time-window:dawn";
            legacyTrigger.TagsJson = "[\"llm-story\",\"branch:item-acquired\",\"world-signal:item-acquired\"]";
            repository.Add(legacyTrigger);

            DbDynamicQuestTemplate mismatch = CreateStoryRow(
                "story-branch-mismatch",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                94,
                DateTime.UtcNow.AddHours(-2));
            mismatch.TagsJson = "[\"llm-story\",\"branch:time-window\",\"world-signal:mob-growth:killed:region:1\"]";
            repository.Add(mismatch);

            int addCalls = repository.AddCalls;
            int saveCalls = repository.SaveCalls;
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem legacyItem = snapshot.Items.Single(item => item.TemplateId == "story-legacy-item-trigger");
            DynamicQuestStoryCacheItem mismatchItem = snapshot.Items.Single(item => item.TemplateId == "story-branch-mismatch");

            Assert.Multiple(() =>
            {
                Assert.That(legacyItem.Warnings, Does.Contain("autoaccept_item_acquired_legacy_trigger"));
                Assert.That(mismatchItem.Warnings, Does.Contain("branch_world_signal_mismatch"));
                Assert.That(legacyItem.ReadyForUse, Is.False);
                Assert.That(mismatchItem.ReadyForUse, Is.False);
                Assert.That(snapshot.ReadyActive, Is.EqualTo(0));
                Assert.That(snapshot.WarningsByReason["autoaccept_item_acquired_legacy_trigger"], Is.EqualTo(1));
                Assert.That(snapshot.WarningsByReason["branch_world_signal_mismatch"], Is.EqualTo(1));
                Assert.That(repository.Rows["story-legacy-item-trigger"].Trigger, Is.EqualTo("time-window:dawn"));
                Assert.That(repository.AddCalls, Is.EqualTo(addCalls));
                Assert.That(repository.SaveCalls, Is.EqualTo(saveCalls));
            });
        }

        [Test]
        public void StoryCacheSnapshot_BlocksMobGrowthBranchWhenMobGrowthSystemDisabled()
        {
            Properties.WORLDAI_MOB_GROWTH_ENABLED = false;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-mob-growth-disabled",
                "Albion",
                1,
                "ant drone",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-2));
            row.TagsJson = "[\"llm-story\",\"story-cache\",\"branch:mob-growth\",\"world-signal:mob-growth:killed:region:1\"]";
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single();

            Assert.Multiple(() =>
            {
                Assert.That(item.ReadyForUse, Is.False);
                Assert.That(item.BranchWorldSignal, Is.EqualTo("mob-growth:killed:region:1"));
                Assert.That(item.Tags, Does.Contain("branch:mob-growth"));
                Assert.That(item.Warnings, Does.Contain("mob_growth_disabled"));
                Assert.That(snapshot.ReadyActive, Is.EqualTo(0));
                Assert.That(snapshot.NotReadyByReason["mob_growth_disabled"], Is.EqualTo(1));
                Assert.That(repository.Rows["story-cache-mob-growth-disabled"].DummyEvaluationCount, Is.EqualTo(0));
            });
        }

        [Test]
        public void StoryCacheSnapshot_DoesNotDoubleCountLegacyRuntimeFailureWhenMobGrowthDisabled()
        {
            Properties.WORLDAI_MOB_GROWTH_ENABLED = false;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-mob-growth-legacy-runtime",
                "Albion",
                1,
                "ant drone",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-2));
            row.TagsJson = "[\"llm-story\",\"story-cache\",\"branch:mob-growth\",\"world-signal:mob-growth:killed:region:1\"]";
            row.DummyEvaluationCount = 1;
            row.DummyEvaluationScore = 95;
            row.DummyEvaluationJson = "{\"score\":95,\"minimumScore\":75,\"passed\":false,\"completed\":true,\"players\":2,\"okPlayers\":0,\"playerDeaths\":0,\"presentationBeat\":18,\"narrativeScene\":8,\"cinematicAction\":108,\"sceneDirectorBeat\":54,\"cinematicDensityScore\":100,\"skyrimGradeScore\":95,\"failureCategory\":\"quest_runtime\"}";
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single();

            Assert.Multiple(() =>
            {
                Assert.That(item.ReadyForUse, Is.False);
                Assert.That(item.BranchWorldSignal, Is.EqualTo("mob-growth:killed:region:1"));
                Assert.That(item.OfferBlockReasons, Does.Contain("mob_growth_disabled"));
                Assert.That(item.OfferBlockReasons, Does.Not.Contain("dummy_evaluation_runtime_failed"));
                Assert.That(snapshot.NotReadyByReason["mob_growth_disabled"], Is.EqualTo(1));
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Not.Contain("dummy_evaluation_runtime_failed"));
                Assert.That(snapshot.DummyFailedActive, Is.EqualTo(0));
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
        public void DummyEvaluation_BelowSkyrimGradeThresholdDeactivatesStoryCacheRow()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-low-grade",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-low-grade",
                Score = 69,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                ChoiceSelected = 1,
                ChoiceOutcomeScene = 1,
                WorldSignal = 1,
                PresentationBeat = 0,
                WorldImpact = 0,
                WorldImpactSummary = 0,
                SkyrimGradeScore = 60,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.True);
                Assert.That(result.Deactivated, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-low-grade"].IsActive, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-low-grade"].DummyEvaluationScore, Is.EqualTo(69));
                Assert.That(repository.Rows["story-cache-dummy-low-grade"].DummyEvaluationCount, Is.EqualTo(1));
                Assert.That(repository.Rows["story-cache-dummy-low-grade"].DummyEvaluationJson, Does.Contain("skyrimGradeScore"));
                Assert.That(snapshot.Items.Select(item => item.TemplateId), Does.Not.Contain("story-cache-dummy-low-grade"));
            });
        }

        [Test]
        public void DummyEvaluation_BelowCinematicDensityThresholdDeactivatesStoryCacheRow()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-low-density",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-low-density",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                ChoiceSelected = 1,
                ChoiceOutcomeScene = 1,
                WorldSignal = 1,
                PresentationBeat = 1,
                WorldImpact = 1,
                WorldImpactSummary = 1,
                NarrativeScene = 1,
                CinematicAction = 1,
                SceneDirectorBeat = 3,
                CinematicInteractionScene = 3,
                CinematicTacticVariety = 3,
                CinematicDensityScore = 55,
                SkyrimGradeScore = 95,
                Source = "unit-test"
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.True);
                Assert.That(result.Deactivated, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-low-density"].IsActive, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-low-density"].DummyEvaluationJson, Does.Contain("cinematicDensityScore"));
                Assert.That(repository.Rows["story-cache-dummy-low-density"].DummyEvaluationJson, Does.Contain("sceneDirectorBeat"));
            });
        }

        [Test]
        public void DummyEvaluation_LowPartySceneCoverageKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-low-party-coverage",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-low-party-coverage",
                Score = 100,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 3,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignal = 3,
                PresentationBeat = 42,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                NarrativeScene = 15,
                CinematicAction = 246,
                MinNarrativeScenePerPlayer = 0,
                MinPresentationBeatPerPlayer = 14,
                MinCinematicActionPerPlayer = 82,
                SceneDirectorBeat = 135,
                SceneBeatOutcome = 93,
                SceneChoreographyPhase = 186,
                SceneActorExchange = 78,
                SceneExchangeOutcome = 78,
                SceneOutcomeSignal = 78,
                SceneConsequence = 51,
                SceneWorldSignal = 171,
                WorldSignalSceneShift = 156,
                CinematicCleanup = 9,
                CinematicVariety = 30,
                CinematicMotionVariety = 30,
                CinematicStaggeredScene = 135,
                CinematicObjectiveFocalScene = 69,
                CinematicActorRoleVariety = 18,
                CinematicChoreographedScene = 135,
                CinematicInteractionScene = 135,
                CinematicTacticVariety = 18,
                CinematicActorInstances = 7284,
                CinematicActorPeak = 100,
                CinematicActorBudgetScore = 100,
                CinematicDensityScore = 100,
                StoryContinuityScore = 100,
                StoryArchetypeScore = 100,
                SkyrimGradeScore = 100,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-low-party-coverage"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-low-party-coverage"].DummyEvaluationJson, Does.Contain("minNarrativeScenePerPlayer"));
                Assert.That(snapshot.Items.Single().ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_party_narrative_coverage_low"));
            });
        }

        [Test]
        public void DummyEvaluation_LowPresentationSpeakerVarietyKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-low-speaker-variety",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-low-speaker-variety",
                Score = 100,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 3,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignal = 3,
                PresentationBeat = 42,
                PresentationSpeakerVariety = 1,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                NarrativeScene = 15,
                CinematicAction = 246,
                MinNarrativeScenePerPlayer = 5,
                MinPresentationBeatPerPlayer = 14,
                MinCinematicActionPerPlayer = 82,
                SceneDirectorBeat = 135,
                SceneBeatOutcome = 93,
                SceneChoreographyPhase = 186,
                SceneActorExchange = 78,
                SceneExchangeOutcome = 78,
                SceneOutcomeSignal = 78,
                SceneConsequence = 51,
                SceneWorldSignal = 171,
                WorldSignalSceneShift = 156,
                CinematicCleanup = 9,
                CinematicVariety = 30,
                CinematicMotionVariety = 30,
                CinematicStaggeredScene = 135,
                CinematicObjectiveFocalScene = 69,
                CinematicActorRoleVariety = 18,
                CinematicChoreographedScene = 135,
                CinematicInteractionScene = 135,
                CinematicTacticVariety = 18,
                CinematicActorInstances = 7284,
                CinematicActorPeak = 100,
                CinematicActorBudgetScore = 100,
                CinematicDensityScore = 100,
                StoryContinuityScore = 100,
                StoryArchetypeScore = 100,
                SkyrimGradeScore = 100,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-low-speaker-variety"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-low-speaker-variety"].DummyEvaluationJson, Does.Contain("presentationSpeakerVariety"));
                Assert.That(snapshot.Items.Single().ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_presentation_speaker_variety_low"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingPresentationStagingKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-presentation-staging",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-presentation-staging",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                ChoiceSelected = 1,
                ChoiceOutcomeScene = 1,
                WorldSignal = 1,
                PresentationBeat = 6,
                PresentationSpeakerVariety = 3,
                PresentationStagedBeat = 0,
                PresentationStagedActionVariety = 0,
                PresentationStagedRoleVariety = 0,
                WorldImpact = 1,
                WorldImpactSummary = 1,
                NarrativeScene = 4,
                CinematicAction = 12,
                SceneDirectorBeat = 4,
                SceneBeatOutcome = 4,
                SceneChoreographyPhase = 4,
                SceneActorExchange = 4,
                SceneExchangeOutcome = 4,
                SceneOutcomeSignal = 4,
                SceneConsequence = 4,
                CinematicCleanup = 1,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 4,
                CinematicObjectiveFocalScene = 4,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 4,
                CinematicInteractionScene = 4,
                CinematicTacticVariety = 4,
                CinematicActorInstances = 80,
                CinematicActorPeak = 12,
                CinematicActorBudgetScore = 100,
                CinematicDensityScore = 95,
                StoryContinuityScore = 95,
                StoryArchetypeScore = 95,
                SkyrimGradeScore = 95,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-presentation-staging"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-presentation-staging"].DummyEvaluationJson, Does.Contain("presentationStagedBeat"));
                Assert.That(snapshot.Items.Single().ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_presentation_staging_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingSceneBeatOutcomeKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-scene-outcome",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-scene-outcome",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                ChoiceSelected = 1,
                ChoiceOutcomeScene = 1,
                PresentationBeat = 8,
                NarrativeScene = 4,
                CinematicAction = 24,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 0,
                CinematicDensityScore = 90,
                SkyrimGradeScore = 95,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-scene-outcome"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-scene-outcome"].DummyEvaluationJson, Does.Contain("sceneBeatOutcome"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-missing-scene-outcome").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_scene_beat_outcome_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_LegacyJsonWithoutSceneBeatOutcomeMetricDoesNotBlock()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-dummy-legacy-no-scene-outcome",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2));
            row.DummyEvaluationCount = 1;
            row.DummyEvaluationScore = 100;
            row.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":true,\"completed\":true,\"players\":1,\"okPlayers\":1,\"playerDeaths\":0,\"choiceSelected\":1,\"choiceOutcomeScene\":1,\"presentationBeat\":8,\"narrativeScene\":4,\"cinematicAction\":24,\"sceneDirectorBeat\":12,\"cinematicDensityScore\":100,\"skyrimGradeScore\":100,\"failureCategory\":\"passed\"}";
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-legacy-no-scene-outcome").ReadyForUse, Is.True);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Not.Contain("dummy_evaluation_scene_beat_outcome_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingSceneChainMetricKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-scene-chain",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-scene-chain",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                PresentationBeat = 8,
                WorldImpact = 1,
                WorldImpactSummary = 1,
                NarrativeScene = 4,
                CinematicAction = 24,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 2,
                CinematicObjectiveFocalScene = 2,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 2,
                SceneChoreographyPhase = 2,
                CinematicInteractionScene = 2,
                CinematicTacticVariety = 4,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                SceneActorExchange = 6,
                SceneExchangeOutcome = 6,
                SceneOutcomeSignal = 0,
                SceneConsequence = 6,
                CinematicDensityScore = 95,
                SkyrimGradeScore = 95,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-scene-chain"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-scene-chain"].DummyEvaluationJson, Does.Contain("sceneOutcomeSignal"));
                Assert.That(repository.Rows["story-cache-dummy-missing-scene-chain"].DummyEvaluationJson, Does.Contain("sceneConsequence"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-missing-scene-chain").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_scene_outcome_signal_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingSceneConsequenceKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-scene-consequence",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-scene-consequence",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                PresentationBeat = 8,
                WorldImpact = 1,
                WorldImpactSummary = 1,
                NarrativeScene = 4,
                CinematicAction = 24,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 2,
                CinematicObjectiveFocalScene = 2,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 2,
                SceneChoreographyPhase = 2,
                CinematicInteractionScene = 2,
                CinematicTacticVariety = 4,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                SceneActorExchange = 6,
                SceneExchangeOutcome = 6,
                SceneOutcomeSignal = 6,
                SceneConsequence = 0,
                CinematicDensityScore = 95,
                SkyrimGradeScore = 95,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-scene-consequence"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-scene-consequence"].DummyEvaluationJson, Does.Contain("sceneConsequence"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-missing-scene-consequence").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_scene_consequence_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingWorldSignalSceneShiftKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-world-signal-scene-shift",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-world-signal-scene-shift",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                ChoiceSelected = 1,
                ChoiceOutcomeScene = 1,
                WorldSignal = 1,
                WorldSignalSceneShift = 0,
                PresentationBeat = 8,
                WorldImpact = 1,
                WorldImpactSummary = 1,
                NarrativeScene = 4,
                CinematicAction = 24,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 2,
                CinematicObjectiveFocalScene = 2,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 2,
                SceneChoreographyPhase = 2,
                CinematicInteractionScene = 2,
                CinematicTacticVariety = 4,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                SceneActorExchange = 6,
                SceneExchangeOutcome = 6,
                SceneOutcomeSignal = 6,
                SceneConsequence = 6,
                CinematicDensityScore = 95,
                SkyrimGradeScore = 95,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-world-signal-scene-shift"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-world-signal-scene-shift"].DummyEvaluationJson, Does.Contain("worldSignalSceneShift"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-missing-world-signal-scene-shift").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_world_signal_scene_shift_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingWorldSignalSceneShiftDetailKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-world-signal-scene-shift-detail",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-world-signal-scene-shift-detail",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                ChoiceSelected = 1,
                ChoiceOutcomeScene = 1,
                WorldSignal = 1,
                WorldSignalSceneShift = 1,
                WorldSignalSceneShiftDetail = 0,
                WorldSignalSceneShiftPhaseVariety = 1,
                WorldSignalSceneShiftSourceVariety = 1,
                WorldSignalSceneShiftTargetVariety = 1,
                PresentationBeat = 8,
                WorldImpact = 1,
                WorldImpactSummary = 1,
                NarrativeScene = 4,
                CinematicAction = 24,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 2,
                CinematicObjectiveFocalScene = 2,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 2,
                SceneChoreographyPhase = 2,
                CinematicInteractionScene = 2,
                CinematicTacticVariety = 4,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                SceneActorExchange = 6,
                SceneExchangeOutcome = 6,
                SceneOutcomeSignal = 6,
                SceneConsequence = 6,
                CinematicDensityScore = 95,
                SkyrimGradeScore = 95,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-world-signal-scene-shift-detail"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-world-signal-scene-shift-detail"].DummyEvaluationJson, Does.Contain("worldSignalSceneShiftDetail"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-missing-world-signal-scene-shift-detail").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_world_signal_scene_shift_detail_low"));
            });
        }

        [Test]
        public void DummyEvaluation_AllowsHighWorldSignalSceneShiftDetailCoverage()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-high-world-signal-scene-shift-detail",
                "Midgard",
                100,
                "little water goblin",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-high-world-signal-scene-shift-detail",
                Score = 100,
                MinimumScore = 75,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 2,
                InitialTimelineObservationGapAccepted = true,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignalExpected = true,
                WorldSignal = 3,
                WorldSignalSceneShift = 68,
                WorldSignalSceneShiftDetail = 67,
                WorldSignalSceneShiftPhaseVariety = 11,
                WorldSignalSceneShiftSourceVariety = 37,
                WorldSignalSceneShiftTargetVariety = 12,
                PresentationBeat = 40,
                PresentationSpeakerVariety = 2,
                PresentationStagedBeat = 32,
                PresentationStagedActionVariety = 9,
                PresentationStagedRoleVariety = 11,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                NarrativeScene = 14,
                CinematicAction = 187,
                CinematicVariety = 30,
                CinematicMotionVariety = 30,
                CinematicStaggeredScene = 82,
                CinematicObjectiveFocalScene = 31,
                CinematicActorRoleVariety = 18,
                CinematicChoreographedScene = 82,
                SceneChoreographyPhase = 142,
                CinematicInteractionScene = 82,
                CinematicTacticVariety = 18,
                CinematicActorInstances = 2892,
                CinematicActorPeak = 100,
                CinematicActorBudgetScore = 100,
                ActionSceneCohesionScore = 100,
                CinematicCatalogRoleVariety = 6,
                CinematicModelRoleFitScore = 100,
                CinematicMarkerScene = 63,
                CinematicMarkerVariety = 14,
                CinematicPhaseCoverage = 9,
                CinematicSetpiecePhaseCoverage = 9,
                CinematicMarkerPhaseCoverage = 8,
                CinematicStoryChain = 9,
                SceneDirectorBeat = 82,
                SceneBeatOutcome = 71,
                SceneActorExchange = 63,
                SceneExchangeOutcome = 63,
                SceneOutcomeSignal = 63,
                SceneConsequence = 45,
                CinematicCleanup = 9,
                CinematicDensityScore = 100,
                StoryContinuityScore = 100,
                StoryArchetypeScore = 100,
                SkyrimGradeScore = 100,
                OperationalEvaluation = new DynamicQuestDummyOperationalEvaluation
                {
                    TotalScore = 86,
                    Grade = "usable",
                    Passed = true
                },
                FailureCategory = "passed",
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-high-world-signal-scene-shift-detail");

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(item.ReadyForUse, Is.True);
                Assert.That(item.OfferEligible, Is.True);
                Assert.That(item.OfferBlockReasons, Does.Not.Contain("dummy_evaluation_world_signal_scene_shift_detail_low"));
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Not.Contain("dummy_evaluation_world_signal_scene_shift_detail_low"));
            });
        }

        [Test]
        public void DummyEvaluation_LowStoryContinuityKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-low-story-continuity",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-low-story-continuity",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                ChoiceSelected = 1,
                ChoiceOutcomeScene = 1,
                WorldSignal = 1,
                WorldSignalSceneShift = 1,
                PresentationBeat = 8,
                WorldImpact = 1,
                WorldImpactSummary = 1,
                NarrativeScene = 4,
                CinematicAction = 24,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 2,
                CinematicObjectiveFocalScene = 2,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 2,
                SceneChoreographyPhase = 2,
                CinematicInteractionScene = 2,
                CinematicTacticVariety = 4,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                SceneActorExchange = 6,
                SceneExchangeOutcome = 6,
                SceneOutcomeSignal = 6,
                SceneConsequence = 6,
                CinematicDensityScore = 95,
                StoryContinuityScore = 40,
                SkyrimGradeScore = 95,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-low-story-continuity"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-low-story-continuity"].DummyEvaluationJson, Does.Contain("storyContinuityScore"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-low-story-continuity").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_story_continuity_low"));
            });
        }

        [Test]
        public void DummyEvaluation_LowStoryArchetypeKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-low-story-archetype",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-low-story-archetype",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                ChoiceSelected = 1,
                ChoiceOutcomeScene = 1,
                WorldSignal = 1,
                WorldSignalSceneShift = 1,
                PresentationBeat = 8,
                WorldImpact = 1,
                WorldImpactSummary = 1,
                NarrativeScene = 4,
                CinematicAction = 24,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 2,
                CinematicObjectiveFocalScene = 2,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 2,
                SceneChoreographyPhase = 2,
                CinematicInteractionScene = 2,
                CinematicTacticVariety = 4,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                SceneActorExchange = 6,
                SceneExchangeOutcome = 6,
                SceneOutcomeSignal = 6,
                SceneConsequence = 6,
                CinematicDensityScore = 95,
                StoryContinuityScore = 95,
                StoryArchetypeScore = 40,
                SkyrimGradeScore = 95,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-low-story-archetype"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-low-story-archetype"].DummyEvaluationJson, Does.Contain("storyArchetypeScore"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-low-story-archetype").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_story_archetype_low"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingSceneChoreographyPhaseKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-scene-choreography-phase",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-scene-choreography-phase",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                ChoiceSelected = 1,
                ChoiceOutcomeScene = 1,
                WorldSignal = 1,
                WorldSignalSceneShift = 1,
                PresentationBeat = 8,
                WorldImpact = 1,
                WorldImpactSummary = 1,
                NarrativeScene = 4,
                CinematicAction = 24,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 2,
                CinematicObjectiveFocalScene = 2,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 2,
                SceneChoreographyPhase = 0,
                CinematicInteractionScene = 2,
                CinematicTacticVariety = 4,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                SceneActorExchange = 6,
                SceneExchangeOutcome = 6,
                SceneOutcomeSignal = 6,
                SceneConsequence = 6,
                CinematicDensityScore = 95,
                StoryContinuityScore = 95,
                StoryArchetypeScore = 95,
                SkyrimGradeScore = 95,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-scene-choreography-phase"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-scene-choreography-phase"].DummyEvaluationJson, Does.Contain("sceneChoreographyPhase"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-missing-scene-choreography-phase").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_scene_choreography_phase_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingChoiceOutcomeSceneKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-choice-outcome",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-choice-outcome",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                ChoiceSelected = 1,
                ChoiceOutcomeScene = 0,
                WorldSignal = 1,
                WorldImpact = 1,
                WorldImpactSummary = 1,
                PresentationBeat = 8,
                NarrativeScene = 4,
                CinematicAction = 24,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 4,
                CinematicObjectiveFocalScene = 4,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 4,
                SceneChoreographyPhase = 4,
                CinematicInteractionScene = 4,
                CinematicTacticVariety = 4,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                CinematicDensityScore = 95,
                SkyrimGradeScore = 95,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-choice-outcome"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-choice-outcome"].DummyEvaluationJson, Does.Contain("choiceOutcomeScene"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-missing-choice-outcome").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_choice_outcome_scene_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingChoiceConsequenceKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-choice-consequence",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-choice-consequence",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                ChoiceSelected = 1,
                ChoiceOutcomeScene = 1,
                ChoiceConsequence = 0,
                WorldSignal = 1,
                WorldImpact = 1,
                WorldImpactSummary = 1,
                WorldMemoryMarked = 1,
                PresentationBeat = 8,
                NarrativeScene = 4,
                CinematicAction = 24,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 4,
                CinematicObjectiveFocalScene = 4,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 4,
                SceneChoreographyPhase = 4,
                CinematicInteractionScene = 4,
                CinematicTacticVariety = 4,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                ActionSceneCohesionScore = 100,
                CinematicCatalogRoleVariety = 6,
                CinematicModelRoleFitScore = 100,
                CinematicDensityScore = 95,
                SkyrimGradeScore = 95,
                Source = "run-dummy-dynamic-quest-matrix"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-choice-consequence"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-choice-consequence"].DummyEvaluationJson, Does.Contain("choiceConsequence"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-missing-choice-consequence").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_choice_consequence_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingExpectedBranchChoiceKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-branch-choice",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-branch-choice",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                BranchChoiceExpected = true,
                ChoiceSelected = 0,
                ChoiceOutcomeScene = 0,
                WorldSignal = 1,
                WorldImpact = 1,
                WorldImpactSummary = 1,
                PresentationBeat = 8,
                NarrativeScene = 4,
                CinematicAction = 24,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 4,
                CinematicObjectiveFocalScene = 4,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 4,
                SceneChoreographyPhase = 4,
                CinematicInteractionScene = 4,
                CinematicTacticVariety = 4,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                CinematicDensityScore = 95,
                SkyrimGradeScore = 95,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-branch-choice"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-branch-choice"].DummyEvaluationJson, Does.Contain("branchChoiceExpected"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-missing-branch-choice").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_branch_choice_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingExpectedWorldSignalKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-expected-world-signal",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-expected-world-signal",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                BranchChoiceExpected = true,
                ChoiceSelected = 1,
                ChoiceOutcomeScene = 1,
                WorldSignalExpected = true,
                WorldSignal = 0,
                WorldImpact = 1,
                WorldImpactSummary = 1,
                PresentationBeat = 8,
                NarrativeScene = 4,
                CinematicAction = 24,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 4,
                CinematicObjectiveFocalScene = 4,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 4,
                SceneChoreographyPhase = 4,
                CinematicInteractionScene = 4,
                CinematicTacticVariety = 4,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                CinematicDensityScore = 95,
                SkyrimGradeScore = 95,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-expected-world-signal"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-expected-world-signal"].DummyEvaluationJson, Does.Contain("worldSignalExpected"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-missing-expected-world-signal").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_expected_world_signal_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_LargeCinematicActorBudgetWithoutCleanupKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-large-actor-no-cleanup",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-large-actor-no-cleanup",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 2,
                OkPlayers = 2,
                ChoiceSelected = 2,
                ChoiceOutcomeScene = 2,
                WorldSignal = 2,
                WorldSignalSceneShift = 2,
                PresentationBeat = 16,
                WorldImpact = 2,
                WorldImpactSummary = 2,
                NarrativeScene = 8,
                CinematicAction = 32,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 8,
                CinematicObjectiveFocalScene = 8,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 8,
                SceneChoreographyPhase = 8,
                CinematicInteractionScene = 8,
                CinematicTacticVariety = 4,
                CinematicActorInstances = 200,
                CinematicActorPeak = 100,
                CinematicActorBudgetScore = 70,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                SceneActorExchange = 6,
                SceneExchangeOutcome = 6,
                SceneOutcomeSignal = 6,
                SceneConsequence = 6,
                CinematicCleanup = 0,
                CinematicDensityScore = 95,
                StoryContinuityScore = 95,
                SkyrimGradeScore = 95,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-large-actor-no-cleanup"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-large-actor-no-cleanup"].DummyEvaluationJson, Does.Contain("cinematicActorPeak"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-large-actor-no-cleanup").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_cinematic_cleanup_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingWorldImpactSummaryKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-world-impact-summary",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-world-impact-summary",
                Score = 100,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                ChoiceSelected = 1,
                ChoiceOutcomeScene = 1,
                WorldSignal = 1,
                WorldImpact = 1,
                WorldImpactSummary = 0,
                PresentationBeat = 8,
                NarrativeScene = 4,
                CinematicAction = 24,
                CinematicVariety = 4,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 100,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-world-impact-summary"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-world-impact-summary"].DummyEvaluationJson, Does.Contain("worldImpactSummary"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-missing-world-impact-summary").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_world_impact_summary_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingWorldMemoryKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-world-memory",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-world-memory",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                ChoiceSelected = 1,
                ChoiceOutcomeScene = 1,
                ChoiceConsequence = 1,
                WorldSignal = 1,
                WorldImpact = 1,
                WorldImpactSummary = 1,
                WorldMemoryMarked = 0,
                PresentationBeat = 8,
                NarrativeScene = 4,
                CinematicAction = 24,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 4,
                CinematicObjectiveFocalScene = 4,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 4,
                SceneChoreographyPhase = 4,
                CinematicInteractionScene = 4,
                CinematicTacticVariety = 4,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                ActionSceneCohesionScore = 100,
                CinematicCatalogRoleVariety = 6,
                CinematicModelRoleFitScore = 100,
                CinematicDensityScore = 95,
                SkyrimGradeScore = 95,
                Source = "run-dummy-dynamic-quest-matrix"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-world-memory"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-world-memory"].DummyEvaluationJson, Does.Contain("worldMemoryMarked"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-missing-world-memory").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_world_memory_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_LowCinematicVarietyKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-low-cinematic-variety",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-low-cinematic-variety",
                Score = 100,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 3,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignal = 3,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                PresentationBeat = 18,
                NarrativeScene = 9,
                CinematicAction = 36,
                CinematicVariety = 1,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 100,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-low-cinematic-variety"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-low-cinematic-variety"].DummyEvaluationJson, Does.Contain("cinematicVariety"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-low-cinematic-variety").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_cinematic_variety_low"));
            });
        }

        [Test]
        public void DummyEvaluation_LowCinematicMotionVarietyKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-low-cinematic-motion-variety",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-low-cinematic-motion-variety",
                Score = 100,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 3,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignal = 3,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                PresentationBeat = 18,
                NarrativeScene = 9,
                CinematicAction = 36,
                CinematicVariety = 4,
                CinematicMotionVariety = 1,
                CinematicStaggeredScene = 9,
                CinematicObjectiveFocalScene = 9,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 9,
                SceneChoreographyPhase = 9,
                CinematicInteractionScene = 9,
                CinematicTacticVariety = 3,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 100,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-low-cinematic-motion-variety"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-low-cinematic-motion-variety"].DummyEvaluationJson, Does.Contain("cinematicMotionVariety"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-low-cinematic-motion-variety").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_cinematic_motion_variety_low"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingCinematicStaggerKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-cinematic-stagger",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-cinematic-stagger",
                Score = 100,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 3,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignal = 3,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                PresentationBeat = 18,
                NarrativeScene = 9,
                CinematicAction = 36,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 0,
                CinematicObjectiveFocalScene = 9,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 9,
                SceneChoreographyPhase = 9,
                CinematicInteractionScene = 9,
                CinematicTacticVariety = 3,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 100,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-cinematic-stagger"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-cinematic-stagger"].DummyEvaluationJson, Does.Contain("cinematicStaggeredScene"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-missing-cinematic-stagger").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_cinematic_stagger_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_LowActionSceneCohesionKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-low-action-scene-cohesion",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-low-action-scene-cohesion",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 3,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignal = 3,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                PresentationBeat = 18,
                NarrativeScene = 9,
                CinematicAction = 36,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 9,
                CinematicObjectiveFocalScene = 9,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 9,
                SceneChoreographyPhase = 9,
                CinematicInteractionScene = 9,
                CinematicTacticVariety = 3,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                ActionSceneCohesionScore = 55,
                CinematicCatalogRoleVariety = 3,
                CinematicModelRoleFitScore = 88,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 95,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-low-action-scene-cohesion");

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-low-action-scene-cohesion"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-low-action-scene-cohesion"].DummyEvaluationJson, Does.Contain("actionSceneCohesionScore"));
                Assert.That(repository.Rows["story-cache-dummy-low-action-scene-cohesion"].DummyEvaluationJson, Does.Contain("cinematicModelRoleFitScore"));
                Assert.That(item.ReadyForUse, Is.False);
                Assert.That(item.DummyActionSceneCohesionScore, Is.EqualTo(55));
                Assert.That(item.DummyCinematicCatalogRoleVariety, Is.EqualTo(3));
                Assert.That(item.DummyCinematicModelRoleFitScore, Is.EqualTo(88));
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_action_scene_cohesion_low"));
            });
        }

        [Test]
        public void DummyEvaluation_ZeroActionSceneCohesionKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-zero-action-scene-cohesion",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-zero-action-scene-cohesion",
                Score = 95,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 3,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignal = 3,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                PresentationBeat = 18,
                NarrativeScene = 9,
                CinematicAction = 36,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 9,
                CinematicObjectiveFocalScene = 9,
                CinematicMarkerScene = 9,
                CinematicMarkerVariety = 3,
                CinematicPhaseCoverage = 3,
                CinematicSetpiecePhaseCoverage = 2,
                CinematicMarkerPhaseCoverage = 2,
                CinematicStoryChain = 3,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 9,
                SceneChoreographyPhase = 9,
                CinematicInteractionScene = 9,
                CinematicTacticVariety = 3,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                ActionSceneCohesionScore = 0,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 95,
                FailureCategory = "quest_quality",
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-zero-action-scene-cohesion");

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-zero-action-scene-cohesion"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-zero-action-scene-cohesion"].DummyEvaluationJson, Does.Contain("actionSceneCohesionScore"));
                Assert.That(item.ReadyForUse, Is.False);
                Assert.That(item.DummyActionSceneCohesionScore, Is.EqualTo(0));
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_action_scene_cohesion_low"));
            });
        }

        [Test]
        public void DummyEvaluation_LowCatalogRoleVarietyKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-low-catalog-role-variety",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-low-catalog-role-variety",
                Score = 100,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 3,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignal = 3,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                PresentationBeat = 18,
                NarrativeScene = 9,
                CinematicAction = 36,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 9,
                CinematicObjectiveFocalScene = 9,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 9,
                SceneChoreographyPhase = 9,
                CinematicInteractionScene = 9,
                CinematicTacticVariety = 3,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                ActionSceneCohesionScore = 100,
                CinematicCatalogRoleVariety = 1,
                CinematicModelRoleFitScore = 100,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 100,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-low-catalog-role-variety");

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-low-catalog-role-variety"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-low-catalog-role-variety"].DummyEvaluationJson, Does.Contain("cinematicCatalogRoleVariety"));
                Assert.That(item.ReadyForUse, Is.False);
                Assert.That(item.DummyCinematicCatalogRoleVariety, Is.EqualTo(1));
                Assert.That(item.DummyCinematicModelRoleFitScore, Is.EqualTo(100));
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_cinematic_catalog_role_variety_low"));
            });
        }

        [Test]
        public void DummyEvaluation_LowModelRoleFitKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-low-model-role-fit",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-low-model-role-fit",
                Score = 100,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 3,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignal = 3,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                PresentationBeat = 18,
                NarrativeScene = 9,
                CinematicAction = 36,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 9,
                CinematicObjectiveFocalScene = 9,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 9,
                SceneChoreographyPhase = 9,
                CinematicInteractionScene = 9,
                CinematicTacticVariety = 3,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                ActionSceneCohesionScore = 100,
                CinematicCatalogRoleVariety = 3,
                CinematicModelRoleFitScore = 55,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 100,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-low-model-role-fit");

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-low-model-role-fit"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-low-model-role-fit"].DummyEvaluationJson, Does.Contain("cinematicModelRoleFitScore"));
                Assert.That(item.ReadyForUse, Is.False);
                Assert.That(item.DummyCinematicCatalogRoleVariety, Is.EqualTo(3));
                Assert.That(item.DummyCinematicModelRoleFitScore, Is.EqualTo(55));
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_cinematic_model_role_fit_low"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingObjectiveFocalSceneKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-objective-focal",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-objective-focal",
                Score = 100,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 3,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignal = 3,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                PresentationBeat = 18,
                NarrativeScene = 9,
                CinematicAction = 36,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 9,
                CinematicObjectiveFocalScene = 0,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 9,
                SceneChoreographyPhase = 9,
                CinematicInteractionScene = 9,
                CinematicTacticVariety = 3,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 100,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-objective-focal"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-objective-focal"].DummyEvaluationJson, Does.Contain("cinematicObjectiveFocalScene"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-missing-objective-focal").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_cinematic_objective_focal_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingCinematicMarkerKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-cinematic-marker",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-cinematic-marker",
                Score = 100,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 3,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignal = 3,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                PresentationBeat = 18,
                NarrativeScene = 9,
                CinematicAction = 36,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 9,
                CinematicObjectiveFocalScene = 9,
                CinematicMarkerScene = 0,
                CinematicMarkerVariety = 0,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 9,
                SceneChoreographyPhase = 9,
                CinematicInteractionScene = 9,
                CinematicTacticVariety = 3,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 100,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-cinematic-marker"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-cinematic-marker"].DummyEvaluationJson, Does.Contain("cinematicMarkerScene"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-missing-cinematic-marker").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_cinematic_marker_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_LowCinematicPhaseCoverageKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-low-cinematic-phase-coverage",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-low-cinematic-phase-coverage",
                Score = 100,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 3,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignal = 3,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                PresentationBeat = 18,
                NarrativeScene = 9,
                CinematicAction = 36,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 9,
                CinematicObjectiveFocalScene = 9,
                CinematicMarkerScene = 9,
                CinematicMarkerVariety = 4,
                CinematicPhaseCoverage = 2,
                CinematicSetpiecePhaseCoverage = 2,
                CinematicMarkerPhaseCoverage = 2,
                CinematicStoryChain = 3,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 9,
                SceneChoreographyPhase = 9,
                CinematicInteractionScene = 9,
                CinematicTacticVariety = 3,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 100,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-low-cinematic-phase-coverage"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-low-cinematic-phase-coverage"].DummyEvaluationJson, Does.Contain("cinematicPhaseCoverage"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-low-cinematic-phase-coverage").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_cinematic_phase_coverage_low"));
            });
        }

        [Test]
        public void DummyEvaluation_LowCinematicStoryChainKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-low-cinematic-story-chain",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-low-cinematic-story-chain",
                Score = 100,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 3,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignal = 3,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                PresentationBeat = 18,
                NarrativeScene = 9,
                CinematicAction = 36,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 9,
                CinematicObjectiveFocalScene = 9,
                CinematicMarkerScene = 9,
                CinematicMarkerVariety = 4,
                CinematicPhaseCoverage = 3,
                CinematicSetpiecePhaseCoverage = 2,
                CinematicMarkerPhaseCoverage = 2,
                CinematicStoryChain = 2,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 9,
                SceneChoreographyPhase = 9,
                CinematicInteractionScene = 9,
                CinematicTacticVariety = 3,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 100,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-low-cinematic-story-chain"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-low-cinematic-story-chain"].DummyEvaluationJson, Does.Contain("cinematicStoryChain"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-low-cinematic-story-chain").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_cinematic_story_chain_low"));
            });
        }

        [Test]
        public void DummyEvaluation_LowActorRoleVarietyKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-low-actor-role-variety",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-low-actor-role-variety",
                Score = 100,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 3,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignal = 3,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                PresentationBeat = 18,
                NarrativeScene = 9,
                CinematicAction = 36,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 9,
                CinematicObjectiveFocalScene = 9,
                CinematicActorRoleVariety = 1,
                CinematicChoreographedScene = 9,
                SceneChoreographyPhase = 9,
                CinematicInteractionScene = 9,
                CinematicTacticVariety = 3,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 100,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-low-actor-role-variety"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-low-actor-role-variety"].DummyEvaluationJson, Does.Contain("cinematicActorRoleVariety"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-low-actor-role-variety").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_cinematic_actor_role_variety_low"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingChoreographyKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-choreography",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-choreography",
                Score = 100,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 3,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignal = 3,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                PresentationBeat = 18,
                NarrativeScene = 9,
                CinematicAction = 36,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 9,
                CinematicObjectiveFocalScene = 9,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 0,
                CinematicInteractionScene = 9,
                CinematicTacticVariety = 3,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 100,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-choreography"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-choreography"].DummyEvaluationJson, Does.Contain("cinematicChoreographedScene"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-missing-choreography").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_cinematic_choreography_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_MissingInteractionKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-missing-interaction",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-missing-interaction",
                Score = 100,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 3,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignal = 3,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                PresentationBeat = 18,
                NarrativeScene = 9,
                CinematicAction = 36,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 9,
                CinematicObjectiveFocalScene = 9,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 9,
                SceneChoreographyPhase = 9,
                CinematicInteractionScene = 0,
                CinematicTacticVariety = 3,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 100,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-missing-interaction"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-missing-interaction"].DummyEvaluationJson, Does.Contain("cinematicInteractionScene"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-missing-interaction").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_cinematic_interaction_missing"));
            });
        }

        [Test]
        public void DummyEvaluation_LowTacticVarietyKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-low-tactic-variety",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestRuntimeService.Instance.AddQuest(new DynamicQuestDefinition
            {
                Id = "runtime-dummy-low-tactic-variety",
                Title = "수도원 길목의 흩어진 전술",
                OfferText = "도와주겠습니까?",
                ProgressText = "forest spiderling을 처치하세요.",
                FinishText = "고맙습니다.",
                StartRegionId = 1,
                TargetName = "forest spiderling",
                TargetCount = 1,
                MinLevel = 1,
                MaxLevel = 8,
                StartMode = DynamicQuestStartMode.AutoAccept,
                Tags = new[] { "template:story-cache-dummy-low-tactic-variety" }
            });

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-low-tactic-variety",
                Score = 100,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 3,
                OkPlayers = 3,
                ChoiceSelected = 3,
                ChoiceOutcomeScene = 3,
                WorldSignal = 3,
                WorldImpact = 3,
                WorldImpactSummary = 3,
                PresentationBeat = 18,
                NarrativeScene = 9,
                CinematicAction = 36,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 9,
                CinematicObjectiveFocalScene = 9,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 9,
                SceneChoreographyPhase = 9,
                CinematicInteractionScene = 9,
                CinematicTacticVariety = 1,
                SceneDirectorBeat = 12,
                SceneBeatOutcome = 12,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 100,
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(result.RemovedRuntimeQuests, Is.EqualTo(1));
                Assert.That(repository.Rows["story-cache-dummy-low-tactic-variety"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-low-tactic-variety"].DummyEvaluationJson, Does.Contain("cinematicTacticVariety"));
                Assert.That(snapshot.Items.Single(item => item.TemplateId == "story-cache-dummy-low-tactic-variety").ReadyForUse, Is.False);
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Contain("dummy_evaluation_cinematic_tactic_variety_low"));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests().Select(quest => quest.Id), Does.Not.Contain("runtime-dummy-low-tactic-variety"));
            });
        }

        [Test]
        public void DummyEvaluation_HighScoreRuntimeFailureKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-runtime-fail",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-runtime-fail",
                Score = 95,
                MinimumScore = 70,
                Passed = false,
                Completed = false,
                Players = 3,
                OkPlayers = 2,
                PlayerDeaths = 1,
                ChoiceSelected = 0,
                PresentationBeat = 9,
                NarrativeScene = 4,
                CinematicAction = 66,
                SceneDirectorBeat = 36,
                CinematicDensityScore = 75,
                SkyrimGradeScore = 85,
                OperationalEvaluation = new DynamicQuestDummyOperationalEvaluation
                {
                    TotalScore = 39,
                    Grade = "discard",
                    Passed = false,
                    FeasibilityScore = 65,
                    DifficultyScore = 65,
                    RewardBalanceScore = 100,
                    RouteScore = 100,
                    VarietyScore = 100,
                    LoreScore = 100,
                    ExploitPenalty = 0,
                    FailReasons = new[] { "quest completion was not observed for every player" },
                    Warnings = new[] { "dummy did not observe completion for every player" },
                    SuggestedFixes = new[] { "완료 조건이 서버 timeline/progress로 확인 가능한지 점검하기" }
                },
                FailureCategory = "dummy_runtime",
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single();

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-runtime-fail"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-runtime-fail"].DummyEvaluationJson, Does.Contain("failureCategory"));
                Assert.That(repository.Rows["story-cache-dummy-runtime-fail"].DummyEvaluationJson, Does.Contain("operationalEvaluation"));
                Assert.That(snapshot.ReadyActive, Is.EqualTo(0));
                Assert.That(snapshot.DummyFailedActive, Is.EqualTo(1));
                Assert.That(snapshot.NotReadyByReason["dummy_evaluation_runtime_failed"], Is.EqualTo(1));
                Assert.That(item.ReadyForUse, Is.False);
                Assert.That(item.DummyEvaluationScore, Is.EqualTo(95));
                Assert.That(item.DummyOperationalScore, Is.EqualTo(39));
                Assert.That(item.DummyOperationalGrade, Is.EqualTo("discard"));
                Assert.That(item.DummyOperationalPassed, Is.False);
                Assert.That(item.DummyFailureCategory, Is.EqualTo("dummy_runtime"));
            });
        }

        [Test]
        public void StoryCacheSnapshot_TreatsLegacyQuestQualityWithOkPlayerMismatchAsRuntimeFailure()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-legacy-quality-runtime-mismatch",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                100,
                DateTime.UtcNow.AddHours(-2));
            row.DummyEvaluationCount = 1;
            row.DummyEvaluationScore = 100;
            row.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":false,\"completed\":true,\"players\":2,\"okPlayers\":0,\"playerDeaths\":0,\"presentationBeat\":18,\"narrativeScene\":8,\"cinematicAction\":108,\"sceneDirectorBeat\":54,\"cinematicDensityScore\":100,\"skyrimGradeScore\":100,\"failureCategory\":\"quest_quality\",\"operationalEvaluation\":{\"totalScore\":96,\"grade\":\"good\",\"passed\":true}}";
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single();

            Assert.Multiple(() =>
            {
                Assert.That(item.ReadyForUse, Is.False);
                Assert.That(item.DummyFailureCategory, Is.EqualTo("quest_quality"));
                Assert.That(item.OfferBlockReasons, Does.Contain("dummy_evaluation_runtime_failed"));
                Assert.That(item.OfferBlockReasons, Does.Not.Contain("dummy_evaluation_quality_failed"));
                Assert.That(snapshot.NotReadyByReason["dummy_evaluation_runtime_failed"], Is.EqualTo(1));
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Not.Contain("dummy_evaluation_quality_failed"));
            });
        }

        [Test]
        public void StoryCacheSnapshot_TreatsPassedOkPlayerMismatchWithoutObservationGapAsRuntimeFailure()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-passed-ok-mismatch-without-gap",
                "Midgard",
                100,
                "little water goblin",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-2));
            row.DummyEvaluationCount = 1;
            row.DummyEvaluationScore = 100;
            row.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":true,\"completed\":true,\"players\":2,\"okPlayers\":1,\"playerDeaths\":0,\"presentationBeat\":18,\"narrativeScene\":8,\"cinematicAction\":108,\"sceneDirectorBeat\":54,\"cinematicDensityScore\":100,\"skyrimGradeScore\":100,\"failureCategory\":\"passed\",\"operationalEvaluation\":{\"totalScore\":96,\"grade\":\"good\",\"passed\":true}}";
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single();

            Assert.Multiple(() =>
            {
                Assert.That(item.ReadyForUse, Is.False);
                Assert.That(item.DummyFailureCategory, Is.EqualTo("passed"));
                Assert.That(item.OfferBlockReasons, Does.Contain("dummy_evaluation_runtime_failed"));
                Assert.That(snapshot.NotReadyByReason["dummy_evaluation_runtime_failed"], Is.EqualTo(1));
            });
        }

        [Test]
        public void StoryCacheSnapshot_AllowsPassedOkPlayerMismatchWithInitialObservationGap()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-passed-ok-mismatch-initial-gap",
                "Midgard",
                100,
                "little water goblin",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-2));
            row.DummyEvaluationCount = 1;
            row.DummyEvaluationScore = 100;
            row.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":true,\"completed\":true,\"players\":2,\"okPlayers\":1,\"initialTimelineObservationGapAccepted\":true,\"playerDeaths\":0,\"presentationBeat\":18,\"narrativeScene\":8,\"cinematicAction\":108,\"sceneDirectorBeat\":54,\"cinematicDensityScore\":100,\"skyrimGradeScore\":100,\"failureCategory\":\"passed\",\"operationalEvaluation\":{\"totalScore\":96,\"grade\":\"good\",\"passed\":true}}";
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single();

            Assert.Multiple(() =>
            {
                Assert.That(item.ReadyForUse, Is.True);
                Assert.That(item.OfferEligible, Is.True);
                Assert.That(item.DummyFailureCategory, Is.EqualTo("passed"));
                Assert.That(item.OfferBlockReasons, Does.Not.Contain("dummy_evaluation_runtime_failed"));
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Not.Contain("dummy_evaluation_runtime_failed"));
            });
        }

        [Test]
        public void StoryCacheSnapshot_KeepsLegacyQuestQualityWithoutRuntimeMismatchAsQualityFailure()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-legacy-quality-real-quality",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                100,
                DateTime.UtcNow.AddHours(-2));
            row.DummyEvaluationCount = 1;
            row.DummyEvaluationScore = 100;
            row.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":70,\"passed\":false,\"completed\":true,\"players\":2,\"okPlayers\":2,\"playerDeaths\":0,\"presentationBeat\":18,\"narrativeScene\":8,\"cinematicAction\":108,\"sceneDirectorBeat\":54,\"cinematicDensityScore\":100,\"skyrimGradeScore\":100,\"failureCategory\":\"quest_quality\",\"operationalEvaluation\":{\"totalScore\":96,\"grade\":\"good\",\"passed\":true}}";
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single();

            Assert.Multiple(() =>
            {
                Assert.That(item.ReadyForUse, Is.False);
                Assert.That(item.DummyFailureCategory, Is.EqualTo("quest_quality"));
                Assert.That(item.OfferBlockReasons, Does.Contain("dummy_evaluation_quality_failed"));
                Assert.That(item.OfferBlockReasons, Does.Not.Contain("dummy_evaluation_runtime_failed"));
                Assert.That(snapshot.NotReadyByReason["dummy_evaluation_quality_failed"], Is.EqualTo(1));
            });
        }

        [Test]
        public void DummyEvaluation_HighScoreDifficultyFailureKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-difficulty-fail",
                "Midgard",
                100,
                "young lynx",
                DynamicQuestStartMode.AutoAccept,
                94,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-difficulty-fail",
                Score = 100,
                MinimumScore = 70,
                Passed = false,
                Completed = false,
                Players = 2,
                OkPlayers = 0,
                PlayerDeaths = 2,
                ChoiceSelected = 1,
                ChoiceOutcomeScene = 1,
                PresentationBeat = 8,
                NarrativeScene = 4,
                CinematicAction = 66,
                SceneDirectorBeat = 34,
                SceneBeatOutcome = 12,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 100,
                FailureCategory = "dummy_difficulty",
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-difficulty-fail"].IsActive, Is.True);
                Assert.That(snapshot.ReadyActive, Is.EqualTo(0));
                Assert.That(snapshot.DummyFailedActive, Is.EqualTo(1));
                Assert.That(snapshot.NotReadyByReason["dummy_evaluation_difficulty_failed"], Is.EqualTo(1));
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Not.Contain("dummy_evaluation_runtime_failed"));
                Assert.That(snapshot.Items.Single().ReadyForUse, Is.False);
                Assert.That(snapshot.Items.Single().OfferBlockReasons, Does.Contain("dummy_evaluation_difficulty_failed"));
            });
        }

        [Test]
        public void DummyEvaluation_HighScoreDifficultyFailureRemovesLiveRuntimeOffer()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-live-offer-fail",
                "Albion",
                1,
                "Arcsinimpede's Drone",
                DynamicQuestStartMode.AutoAccept,
                96,
                DateTime.UtcNow.AddHours(-2)));
            repository.Add(CreateStoryRow(
                "story-cache-dummy-live-offer-related",
                "Albion",
                1,
                "Arcsinimpede",
                DynamicQuestStartMode.AutoAccept,
                96,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));
            DynamicQuestRuntimeService.Instance.AddQuest(new DynamicQuestDefinition
            {
                Id = "runtime-dummy-live-offer-fail",
                Title = "수도원 길목의 닫힌 입술의 밤",
                OfferText = "도와주겠습니까?",
                ProgressText = "frost bound bear를 처치하세요.",
                FinishText = "고맙습니다.",
                StartRegionId = 1,
                TargetName = "frost bound bear",
                TargetCount = 1,
                MinLevel = 1,
                MaxLevel = 8,
                StartMode = DynamicQuestStartMode.AutoAccept,
                Tags = new[] { "template:story-cache-dummy-live-offer-fail" }
            });
            DynamicQuestRuntimeService.Instance.AddQuest(new DynamicQuestDefinition
            {
                Id = "runtime-dummy-live-offer-related",
                Title = "수도원 길목의 다른 그림자",
                OfferText = "도와주겠습니까?",
                ProgressText = "frost bound bear를 처치하세요.",
                FinishText = "고맙습니다.",
                StartRegionId = 1,
                TargetName = "frost bound bear",
                TargetCount = 1,
                MinLevel = 1,
                MaxLevel = 8,
                StartMode = DynamicQuestStartMode.AutoAccept,
                Tags = new[] { "template:story-cache-dummy-live-offer-related" }
            });

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-live-offer-fail",
                TargetName = "frost bound bear",
                Score = 100,
                MinimumScore = 70,
                Passed = false,
                Completed = false,
                Players = 1,
                OkPlayers = 0,
                PlayerDeaths = 1,
                PresentationBeat = 4,
                NarrativeScene = 2,
                CinematicAction = 33,
                SceneDirectorBeat = 17,
                SceneBeatOutcome = 13,
                CinematicDensityScore = 100,
                SkyrimGradeScore = 100,
                FailureCategory = "dummy_difficulty",
                Source = "unit-test"
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(result.RemovedRuntimeQuests, Is.EqualTo(2));
                Assert.That(repository.Rows["story-cache-dummy-live-offer-fail"].IsActive, Is.True);
                Assert.That(service.GetStoryCacheSnapshot(10, includeText: false).NotReadyByReason["dummy_evaluation_difficulty_failed"], Is.EqualTo(1));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests().Select(quest => quest.Id), Does.Not.Contain("runtime-dummy-live-offer-fail"));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests().Select(quest => quest.Id), Does.Not.Contain("runtime-dummy-live-offer-related"));
            });
        }

        [Test]
        public void DummyEvaluation_OperationalFailureKeepsRowActiveButNotReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-operational-fail",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                94,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-operational-fail",
                Score = 96,
                MinimumScore = 70,
                Passed = true,
                Completed = true,
                Players = 1,
                OkPlayers = 1,
                PlayerDeaths = 0,
                ChoiceSelected = 1,
                ChoiceOutcomeScene = 1,
                WorldImpactSummary = 1,
                PresentationBeat = 9,
                NarrativeScene = 4,
                CinematicAction = 66,
                CinematicVariety = 4,
                CinematicMotionVariety = 4,
                CinematicStaggeredScene = 3,
                CinematicObjectiveFocalScene = 3,
                CinematicActorRoleVariety = 4,
                CinematicChoreographedScene = 8,
                CinematicInteractionScene = 6,
                CinematicTacticVariety = 4,
                CinematicActorInstances = 80,
                CinematicActorPeak = 20,
                CinematicActorBudgetScore = 96,
                SceneDirectorBeat = 36,
                SceneBeatOutcome = 18,
                SceneChoreographyPhase = 8,
                CinematicDensityScore = 95,
                StoryContinuityScore = 95,
                StoryArchetypeScore = 95,
                SkyrimGradeScore = 95,
                OperationalEvaluation = new DynamicQuestDummyOperationalEvaluation
                {
                    TotalScore = 64,
                    Grade = "discard",
                    Passed = false,
                    FeasibilityScore = 90,
                    DifficultyScore = 45,
                    RewardBalanceScore = 100,
                    RouteScore = 90,
                    VarietyScore = 80,
                    LoreScore = 85,
                    ExploitPenalty = 0,
                    FailReasons = new[] { "target level is above the solo dummy safety band" },
                    Warnings = new[] { "난이도 조정 필요" },
                    SuggestedFixes = new[] { "target area를 낮은 레벨 spawn cluster로 변경" }
                },
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single();

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-operational-fail"].IsActive, Is.True);
                Assert.That(snapshot.ReadyActive, Is.EqualTo(0));
                Assert.That(snapshot.DummyFailedActive, Is.EqualTo(1));
                Assert.That(snapshot.NotReadyByReason["dummy_evaluation_operational_failed"], Is.EqualTo(1));
                Assert.That(item.ReadyForUse, Is.False);
                Assert.That(item.DummyOperationalScore, Is.EqualTo(64));
                Assert.That(item.DummyOperationalGrade, Is.EqualTo("discard"));
                Assert.That(item.DummyOperationalPassed, Is.False);
            });
        }

        [Test]
        public void StoryCacheSnapshot_UsableOperationalEvaluationBelowStoryThresholdStaysReady()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 90;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = true;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate row = CreateStoryRow(
                "story-cache-dummy-operational-usable",
                "Midgard",
                100,
                "little water goblin",
                DynamicQuestStartMode.AutoAccept,
                100,
                DateTime.UtcNow.AddHours(-2));
            row.DummyEvaluationCount = 1;
            row.DummyEvaluationScore = 100;
            row.DummyEvaluationJson = "{\"score\":100,\"minimumScore\":90,\"passed\":true,\"completed\":true,\"players\":1,\"okPlayers\":1,\"playerDeaths\":0,\"presentationBeat\":14,\"narrativeScene\":5,\"cinematicAction\":62,\"cinematicDensityScore\":100,\"skyrimGradeScore\":100,\"failureCategory\":\"passed\",\"operationalEvaluation\":{\"totalScore\":85,\"grade\":\"usable\",\"passed\":true}}";
            repository.Add(row);
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestStoryCacheItem item = snapshot.Items.Single();

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.ReadyActive, Is.EqualTo(1));
                Assert.That(snapshot.DummyFailedActive, Is.EqualTo(0));
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Not.Contain("dummy_evaluation_operational_failed"));
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Not.Contain("dummy_evaluation_not_passing"));
                Assert.That(item.ReadyForUse, Is.True);
                Assert.That(item.OfferEligible, Is.True);
                Assert.That(item.OfferBlockReasons, Does.Not.Contain("dummy_evaluation_operational_failed"));
                Assert.That(item.OfferBlockReasons, Does.Not.Contain("dummy_evaluation_not_passing"));
                Assert.That(item.DummyOperationalScore, Is.EqualTo(85));
                Assert.That(item.DummyOperationalGrade, Is.EqualTo("usable"));
                Assert.That(item.DummyOperationalPassed, Is.True);
            });
        }

        [Test]
        public void DummyEvaluation_HighScoreInfrastructureFailureDoesNotBlockStoryCacheRow()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = true;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-infra-fail",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-infra-fail",
                Score = 95,
                MinimumScore = 70,
                Passed = false,
                Completed = false,
                Players = 3,
                OkPlayers = 0,
                PlayerDeaths = 1,
                PresentationBeat = 9,
                NarrativeScene = 4,
                CinematicAction = 66,
                SceneDirectorBeat = 36,
                CinematicDensityScore = 75,
                SkyrimGradeScore = 85,
                FailureCategory = "infrastructure",
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.False);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(snapshot.ReadyActive, Is.EqualTo(1));
                Assert.That(snapshot.DummyFailedActive, Is.EqualTo(0));
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Not.Contain("dummy_evaluation_below_threshold"));
                Assert.That(snapshot.Items.Single().ReadyForUse, Is.True);
                Assert.That(snapshot.Items.Single().OfferEligible, Is.False);
                Assert.That(snapshot.Items.Single().OfferBlockReasons, Does.Contain("dummy_evaluation_inconclusive"));
            });
        }

        [Test]
        public void DummyEvaluation_LowScoreInfrastructureFailureDoesNotDeactivateOrBlockStoryCacheRow()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            Properties.KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS = true;
            FakeDynamicQuestTemplateRepository repository = new();
            repository.Add(CreateStoryRow(
                "story-cache-dummy-low-infra-fail",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2)));
            DynamicQuestSeedService service = new(repository, new DynamicQuestStoryService(Array.Empty<IDynamicQuestStoryProvider>()));

            DynamicQuestDummyEvaluationResult result = service.SubmitDummyEvaluation(new DynamicQuestDummyEvaluationRequest
            {
                QuestId = "story-cache-dummy-low-infra-fail",
                Score = 15,
                MinimumScore = 70,
                Passed = false,
                Completed = true,
                Players = 3,
                OkPlayers = 0,
                PlayerDeaths = 0,
                CinematicDensityScore = 5,
                SkyrimGradeScore = 15,
                FailureCategory = "no_fresh_quest_attempt",
                Source = "unit-test"
            });

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: true);

            Assert.Multiple(() =>
            {
                Assert.That(result.Accepted, Is.True);
                Assert.That(result.BelowThreshold, Is.True);
                Assert.That(result.Deactivated, Is.False);
                Assert.That(repository.Rows["story-cache-dummy-low-infra-fail"].IsActive, Is.True);
                Assert.That(repository.Rows["story-cache-dummy-low-infra-fail"].DummyEvaluationJson, Does.Contain("no_fresh_quest_attempt"));
                Assert.That(snapshot.ReadyActive, Is.EqualTo(1));
                Assert.That(snapshot.DummyFailedActive, Is.EqualTo(0));
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Not.Contain("dummy_evaluation_below_threshold"));
                Assert.That(snapshot.NotReadyByReason.Keys, Does.Not.Contain("dummy_evaluation_runtime_failed"));
                Assert.That(snapshot.Items.Single().ReadyForUse, Is.True);
                Assert.That(snapshot.Items.Single().OfferEligible, Is.False);
                Assert.That(snapshot.Items.Single().OfferBlockReasons, Does.Contain("dummy_evaluation_inconclusive"));
            });
        }

        [Test]
        public void Seed_StoryCacheOffersSkipActiveRowsWithFailedHistoricalDummyEvaluation()
        {
            Properties.KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE = 70;
            FakeDynamicQuestTemplateRepository repository = new();
            DbDynamicQuestTemplate failed = CreateStoryRow(
                "story-cache-dummy-historical-fail",
                "Albion",
                1,
                "forest spiderling",
                DynamicQuestStartMode.NpcOffer,
                92,
                DateTime.UtcNow.AddHours(-2));
            failed.DummyEvaluationScore = 95;
            failed.DummyEvaluationCount = 1;
            failed.DummyEvaluationJson = "{\"score\":95,\"minimumScore\":70,\"belowThreshold\":true,\"skyrimGradeScore\":60,\"cinematicDensityScore\":95}";
            failed.IsActive = true;
            repository.Add(failed);
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

            DynamicQuestStoryCacheSnapshot snapshot = service.GetStoryCacheSnapshot(10, includeText: false);
            DynamicQuestSeedSummary summary = service.Seed(new[]
            {
                CreateNpc("Brother Penric", "seed-npc-1", 1),
                CreateNpc("black wolf pup", "target-configured", 1),
                CreateNpc("forest spiderling", "target-cache", 1)
            }, options);

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.ReadyActive, Is.EqualTo(0));
                Assert.That(snapshot.DummyEvaluatedActive, Is.EqualTo(1));
                Assert.That(snapshot.DummyEvaluatedReady, Is.EqualTo(0));
                Assert.That(snapshot.DummyUnevaluatedReady, Is.EqualTo(0));
                Assert.That(snapshot.DummyFailedActive, Is.EqualTo(1));
                Assert.That(snapshot.NotReadyByReason["dummy_evaluation_below_threshold"], Is.EqualTo(1));
                Assert.That(snapshot.Items.Single().ReadyForUse, Is.False);
                Assert.That(summary.StoryCacheOffered, Is.EqualTo(0));
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests().Select(quest => quest.TargetName), Does.Not.Contain("forest spiderling"));
                Assert.That(repository.Rows["story-cache-dummy-historical-fail"].IsActive, Is.True);
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
            Assert.That(result.Quest.MinLevel, Is.EqualTo(1));
            Assert.That(result.Quest.MaxLevel, Is.EqualTo(1));
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

        private static string GetProfileString(object profile, string propertyName)
        {
            return profile?.GetType().GetProperty(propertyName)?.GetValue(profile)?.ToString() ?? string.Empty;
        }
    }
}
