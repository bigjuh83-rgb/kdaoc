using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using DOL.Database;
using DOL.GS;
using DOL.GS.PacketHandler;
using DOL.GS.Quests;
using DOL.GS.ServerProperties;
using DOL.GS.WorldAI;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_DynamicQuestRuntimeService
    {
        [SetUp]
        public void SetUp()
        {
            Properties.KDAOC_DYNAMIC_QUEST_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_MAX_ACTIVE_PER_PLAYER = 1;
            Properties.KDAOC_DYNAMIC_QUEST_MAX_ACTIVE_PER_NPC = 3;
            Properties.KDAOC_DYNAMIC_QUEST_MAX_KILL_COUNT = 20;
            Properties.KDAOC_DYNAMIC_QUEST_REWARD_XP_MULTIPLIER = 1.0;
            Properties.KDAOC_DYNAMIC_QUEST_REWARD_MONEY_MULTIPLIER = 1.0;
            Properties.KDAOC_DYNAMIC_QUEST_WORLD_REVISION = string.Empty;
            Properties.KDAOC_DYNAMIC_QUEST_CINEMATIC_MAX_ACTORS_PER_ACTION = 100;
            DynamicQuestCinematicCatalog.ClearCacheForTest();
            DynamicQuestRuntimeService.Instance.ClearAll();
        }

        [TearDown]
        public void TearDown()
        {
            DynamicQuestRuntimeService.Instance.ClearAll();
            Properties.KDAOC_DYNAMIC_QUEST_ENABLED = false;
            Properties.KDAOC_DYNAMIC_QUEST_WORLD_REVISION = string.Empty;
            Properties.KDAOC_DYNAMIC_QUEST_CINEMATIC_MAX_ACTORS_PER_ACTION = 0;
            DynamicQuestCinematicCatalog.ClearCacheForTest();
        }

        [Test]
        public void NormalizeQuestForTest_MaterializesLegacyKillQuestAsGraph()
        {
            DynamicQuestDefinition quest = LegacyQuest();

            DynamicQuestDefinition normalized = DynamicQuestRuntimeService.Instance.NormalizeQuestForTest(quest);

            Assert.Multiple(() =>
            {
                Assert.That(normalized.GraphVersion, Is.EqualTo(1));
                Assert.That(normalized.Nodes.Select(node => node.Type), Is.EqualTo(new[]
                {
                    DynamicQuestNodeType.Kill,
                    DynamicQuestNodeType.ReturnToNpc,
                    DynamicQuestNodeType.Complete
                }));
                Assert.That(normalized.StartNodeId, Is.EqualTo("kill"));
                Assert.That(normalized.Nodes.Single(node => node.Id == "kill").Objective.TargetName, Is.EqualTo("black wolf pup"));
                Assert.That(normalized.Nodes.Single(node => node.Id == "kill").Objective.TargetCount, Is.EqualTo(2));
            });
        }

        [Test]
        public void NormalizeQuestForTest_FillsRealmFromTagAndRegion()
        {
            DynamicQuestDefinition tagged = GraphQuest();
            tagged.Tags = new[] { "realm:Midgard" };
            DynamicQuestDefinition regional = GraphQuest();
            regional.Tags = Array.Empty<string>();

            DynamicQuestDefinition normalizedTagged = DynamicQuestRuntimeService.Instance.NormalizeQuestForTest(tagged);
            DynamicQuestDefinition normalizedRegional = DynamicQuestRuntimeService.Instance.NormalizeQuestForTest(regional);

            Assert.Multiple(() =>
            {
                Assert.That(normalizedTagged.Realm, Is.EqualTo("Midgard"));
                Assert.That(normalizedRegional.Realm, Is.EqualTo("Albion"));
            });
        }

        [Test]
        public void GetTimelineSnapshot_FallsBackToPlayerNameWhenRuntimeKeyChanged()
        {
            DynamicQuestRuntimeService service = new(new FakeDynamicQuestProgressRepository());
            MethodInfo recordTimeline = typeof(DynamicQuestRuntimeService).GetMethod(
                "RecordTimelineEventLocked",
                BindingFlags.Instance | BindingFlags.NonPublic);

            recordTimeline.Invoke(
                service,
                new object[]
                {
                    "online-runtime-key",
                    "Dummy Quest",
                    "quest-audit",
                    "quest_rewarded",
                    "complete",
                    string.Empty,
                    string.Empty,
                    "rewarded",
                    string.Empty,
                    0
                });

            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot(
                "offline-character-key",
                "Dummy Quest",
                false);

            Assert.Multiple(() =>
            {
                Assert.That(timeline.PlayerKey, Is.EqualTo("offline-character-key"));
                Assert.That(timeline.Events.Select(item => item.EventType), Does.Contain("quest_rewarded"));
                Assert.That(timeline.Events.Single(item => item.EventType == "quest_rewarded").PlayerKey, Is.EqualTo("online-runtime-key"));
            });
        }

        [Test]
        public void AddQuest_RejectsGraphWithMissingEdgeTarget()
        {
            DynamicQuestDefinition quest = LegacyQuest();
            quest.StartNodeId = "start";
            quest.Nodes = new[]
            {
                new DynamicQuestNode
                {
                    Id = "start",
                    Type = DynamicQuestNodeType.Talk,
                    Title = "시작",
                    Text = "시작합니다.",
                    Objective = new DynamicQuestObjective
                    {
                        NpcInternalId = "seed-npc-1",
                        NpcName = "Brother Penric",
                        RegionId = 1
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge { ToNodeId = "missing", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
                    }
                },
                new DynamicQuestNode { Id = "complete", Type = DynamicQuestNodeType.Complete, Title = "완료", Text = "완료" }
            };

            DynamicQuestResult result = DynamicQuestRuntimeService.Instance.AddQuest(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.False);
                Assert.That(result.Message, Does.Contain("edge target"));
            });
        }

        [Test]
        public void AddQuest_AcceptsValidTalkKillReturnChoiceCompleteGraph()
        {
            DynamicQuestDefinition quest = GraphQuest();

            DynamicQuestResult result = DynamicQuestRuntimeService.Instance.AddQuest(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True);
                Assert.That(DynamicQuestRuntimeService.Instance.GetQuests(), Has.Count.EqualTo(1));
            });
        }

        [Test]
        public void AddQuest_RejectsChoiceEdgeWithUnknownChoiceId()
        {
            DynamicQuestDefinition quest = GraphQuest();
            DynamicQuestNode choice = quest.Nodes.Single(node => node.Id == "choice");
            choice.Edges = new[]
            {
                new DynamicQuestEdge
                {
                    ToNodeId = "complete",
                    Condition = DynamicQuestEdgeCondition.ChoiceSelected,
                    ConditionValue = "missing"
                }
            };

            DynamicQuestResult result = DynamicQuestRuntimeService.Instance.AddQuest(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.False);
                Assert.That(result.Message, Does.Contain("choice edge value"));
            });
        }

        [Test]
        public void GetValidationSnapshot_WarnsAboutUnreachableGraphNode()
        {
            DynamicQuestDefinition quest = GraphQuest();
            quest.Id = "quest-unreachable";
            quest.Nodes = quest.Nodes.Concat(new[]
            {
                new DynamicQuestNode
                {
                    Id = "orphan",
                    Type = DynamicQuestNodeType.Talk,
                    Title = "고립 노드",
                    Text = "어디에서도 이어지지 않습니다.",
                    Objective = new DynamicQuestObjective
                    {
                        NpcInternalId = "seed-npc-1",
                        NpcName = "Brother Penric",
                        RegionId = 1
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
                    }
                }
            }).ToArray();

            DynamicQuestResult result = DynamicQuestRuntimeService.Instance.AddQuest(quest);
            DynamicQuestValidationSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetValidationSnapshot();
            DynamicQuestValidationItem item = snapshot.Items.Single(entry => entry.QuestId == "quest-unreachable");

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True);
                Assert.That(item.Valid, Is.True);
                Assert.That(item.Warnings.Any(warning => warning.Contains("unreachable")), Is.True);
            });
        }

        [Test]
        public void GetValidationSnapshot_ReportsLiveQuestValidationState()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(GraphQuest());

            DynamicQuestValidationSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetValidationSnapshot();

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.TotalQuests, Is.EqualTo(1));
                Assert.That(snapshot.ValidQuests, Is.EqualTo(1));
                Assert.That(snapshot.InvalidQuests, Is.EqualTo(0));
                Assert.That(snapshot.Items.Single().QuestId, Is.EqualTo("quest-graph"));
                Assert.That(snapshot.Items.Single().Valid, Is.True);
                Assert.That(snapshot.Items.Single().EstimatedPlayableSteps, Is.GreaterThanOrEqualTo(1));
                Assert.That(snapshot.Items.Single().EstimatedMinutes, Is.GreaterThanOrEqualTo(1));
                Assert.That(snapshot.Items.Single().RewardDifficultyIndex, Is.GreaterThanOrEqualTo(0));
                Assert.That(snapshot.Items.Single().SuggestedRewardScale, Is.GreaterThan(0));
                Assert.That(snapshot.Items.Single().SuggestedRewardTier, Is.Not.EqualTo(string.Empty));
            });
        }

        [Test]
        public void AddQuest_AcceptsValidTalkExploreKillReturnChoiceCompleteGraph()
        {
            DynamicQuestDefinition quest = ExploreGraphQuest();

            DynamicQuestResult result = DynamicQuestRuntimeService.Instance.AddQuest(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True);
                Assert.That(quest.Nodes.Select(node => node.Type), Is.EqualTo(new[]
                {
                    DynamicQuestNodeType.Talk,
                    DynamicQuestNodeType.Explore,
                    DynamicQuestNodeType.Kill,
                    DynamicQuestNodeType.ReturnToNpc,
                    DynamicQuestNodeType.Choice,
                    DynamicQuestNodeType.Complete
                }));
            });
        }

        [Test]
        public void AddQuest_AcceptsWorldOfferWithoutStartNpc()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();

            DynamicQuestResult result = DynamicQuestRuntimeService.Instance.AddQuest(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True);
                Assert.That(result.Quest.StartMode, Is.EqualTo(DynamicQuestStartMode.WorldOffer));
                Assert.That(result.Quest.StartNpcInternalId, Is.Empty);
                Assert.That(result.Quest.StartNodeId, Is.EqualTo("explore"));
            });
        }

        [Test]
        public void AcceptQuestForTest_AcceptsWorldOfferWithoutNpcAndStartsAtExplore()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(WorldOfferQuest());

            bool accepted = DynamicQuestRuntimeService.Instance.AcceptQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                "quest-world-offer",
                "world_region_entered");

            DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);
            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot("DummyQuest001", "DummyQuest001", true);
            DynamicQuestProgressItem item = snapshot.Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(item.QuestId, Is.EqualTo("quest-world-offer"));
                Assert.That(item.StartNpcName, Is.Empty);
                Assert.That(item.CurrentNodeId, Is.EqualTo("explore"));
                Assert.That(item.CurrentNodeType, Is.EqualTo(DynamicQuestNodeType.Explore));
                Assert.That(item.CurrentNodeElapsedSeconds, Is.GreaterThanOrEqualTo(0));
                Assert.That(item.PendingWorldSignals, Is.Empty);
                Assert.That(item.LastEventType, Is.EqualTo("quest_accepted"));
                Assert.That(item.LastEventNodeId, Is.EqualTo("explore"));
                Assert.That(item.LastEventDetail, Is.EqualTo("world_region_entered"));
                Assert.That(item.StalledReason, Is.EqualTo("waiting_for_location"));
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "quest_accepted" &&
                    evt.Detail == "world_region_entered"), Is.True);
            });
        }

        [Test]
        public void AcceptAvailableWorldQuestForTest_AcceptsWorldSignalTaggedQuestWithoutNpc()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.Id = "quest-world-signal-region";
            quest.StartMode = DynamicQuestStartMode.WorldOffer;
            quest.Tags = new[] { "world-signal:region-entered:1" };
            DynamicQuestRuntimeService.Instance.AddQuest(quest);

            bool ignored = DynamicQuestRuntimeService.Instance.AcceptAvailableWorldQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                "region-entered:2");
            bool accepted = DynamicQuestRuntimeService.Instance.AcceptAvailableWorldQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                "region-entered:1");

            DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(ignored, Is.False);
                Assert.That(accepted, Is.True);
                Assert.That(snapshot.Active.Single().QuestId, Is.EqualTo("quest-world-signal-region"));
            });
        }

        [Test]
        public void AcceptAvailableWorldQuestForTest_AcceptsTaggedAutoAcceptQuestWithoutNpc()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.Id = "quest-auto-rift";
            quest.StartMode = DynamicQuestStartMode.AutoAccept;
            quest.Tags = new[] { "trigger:rift-entered" };
            DynamicQuestRuntimeService.Instance.AddQuest(quest);

            bool ignored = DynamicQuestRuntimeService.Instance.AcceptAvailableWorldQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                "wrong-trigger");
            bool accepted = DynamicQuestRuntimeService.Instance.AcceptAvailableWorldQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                "rift-entered");

            DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(ignored, Is.False);
                Assert.That(accepted, Is.True);
                Assert.That(snapshot.Active.Single().QuestId, Is.EqualTo("quest-auto-rift"));
            });
        }

        [Test]
        public void AcceptAvailableWorldQuestForTest_LoadsCompletedProgressBeforeOffering()
        {
            FakeDynamicQuestProgressRepository repository = new();
            repository.Rows["dummyquest001:quest-auto-rift"] = new DbDynamicQuestProgress
            {
                ProgressId = "dummyquest001:quest-auto-rift",
                PlayerKey = "DummyQuest001",
                PlayerName = "DummyQuest001",
                QuestId = "quest-auto-rift",
                CurrentNodeId = "complete",
                IsComplete = true,
                Completed = true,
                IsActive = false,
                AcceptedAt = DateTime.UtcNow.AddMinutes(-10),
                CreatedAt = DateTime.UtcNow.AddMinutes(-10),
                UpdatedAt = DateTime.UtcNow.AddMinutes(-5)
            };

            DynamicQuestRuntimeService service = new(repository);
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.Id = "quest-auto-rift";
            quest.StartMode = DynamicQuestStartMode.AutoAccept;
            quest.Tags = new[] { "trigger:rift-entered" };
            service.AddQuest(quest);

            bool accepted = service.AcceptAvailableWorldQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                "rift-entered");
            DbDynamicQuestProgress row = repository.Rows["dummyquest001:quest-auto-rift"];
            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.False);
                Assert.That(snapshot.Active, Is.Empty);
                Assert.That(snapshot.CompletedQuestIds, Does.Contain("quest-auto-rift"));
                Assert.That(row.PlayerName, Is.EqualTo("DummyQuest001"));
                Assert.That(row.Completed, Is.True);
                Assert.That(row.IsComplete, Is.True);
                Assert.That(row.IsActive, Is.False);
            });
        }

        [Test]
        public void AcceptAvailableRegionalAutoQuestForTest_AcceptsOnlyAutoAcceptQuestForRegionTag()
        {
            DynamicQuestDefinition worldOffer = WorldOfferQuest();
            worldOffer.Id = "quest-world-region";
            worldOffer.StartMode = DynamicQuestStartMode.WorldOffer;
            worldOffer.Tags = new[] { "region:1" };
            DynamicQuestRuntimeService.Instance.AddQuest(worldOffer);

            DynamicQuestDefinition autoAccept = WorldOfferQuest();
            autoAccept.Id = "quest-auto-region";
            autoAccept.StartMode = DynamicQuestStartMode.AutoAccept;
            autoAccept.Tags = new[] { "region:1" };
            DynamicQuestRuntimeService.Instance.AddQuest(autoAccept);

            bool accepted = DynamicQuestRuntimeService.Instance.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1);

            DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);
            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(snapshot.Active.Single().QuestId, Is.EqualTo("quest-auto-region"));
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "quest_accepted" &&
                    evt.Detail == "region:1"), Is.True);
            });
        }

        [Test]
        public void AcceptAvailableRegionalAutoQuestForTest_DoesNotAcceptAutoAcceptOutsideStartScope()
        {
            DynamicQuestDefinition autoAccept = WorldOfferQuest();
            autoAccept.Id = "quest-auto-region";
            autoAccept.StartMode = DynamicQuestStartMode.AutoAccept;
            autoAccept.Tags = new[] { "region:1" };
            DynamicQuestRuntimeService.Instance.AddQuest(autoAccept);

            bool accepted = DynamicQuestRuntimeService.Instance.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1,
                520000,
                492000);

            DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.False);
                Assert.That(snapshot.Active, Is.Empty);
            });
        }

        [Test]
        public void AcceptAvailableRegionalAutoQuestForTest_AcceptsAutoAcceptInsideStartScope()
        {
            DynamicQuestDefinition autoAccept = WorldOfferQuest();
            autoAccept.Id = "quest-auto-region";
            autoAccept.StartMode = DynamicQuestStartMode.AutoAccept;
            autoAccept.Tags = new[] { "region:1" };
            DynamicQuestRuntimeService.Instance.AddQuest(autoAccept);

            bool accepted = DynamicQuestRuntimeService.Instance.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1,
                521100,
                492100);

            DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(snapshot.Active.Single().QuestId, Is.EqualTo("quest-auto-region"));
            });
        }

        [Test]
        public void AcceptAvailableRegionalAutoQuestForTest_SkipsOutOfScopeCandidateWithSameTrigger()
        {
            DynamicQuestRuntimeService service = new(new FakeDynamicQuestProgressRepository());

            DynamicQuestDefinition outside = WorldOfferQuest();
            outside.Id = "quest-auto-region-outside";
            outside.StartMode = DynamicQuestStartMode.AutoAccept;
            outside.Tags = new[] { "region:1" };
            outside.CreatedAt = DateTime.UtcNow.AddMinutes(-2);
            outside.Nodes.Single(node => node.Id == "explore").Objective.X = 530000;
            outside.Nodes.Single(node => node.Id == "explore").Objective.Y = 492000;
            service.AddQuest(outside);

            DynamicQuestDefinition inside = WorldOfferQuest();
            inside.Id = "quest-auto-region-inside";
            inside.StartMode = DynamicQuestStartMode.AutoAccept;
            inside.Tags = new[] { "region:1" };
            inside.CreatedAt = DateTime.UtcNow.AddMinutes(-1);
            service.AddQuest(inside);

            bool accepted = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1,
                521100,
                492100);
            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(snapshot.Active.Single().QuestId, Is.EqualTo("quest-auto-region-inside"));
                Assert.That(snapshot.Active.Select(item => item.QuestId), Does.Not.Contain("quest-auto-region-outside"));
            });
        }

        [Test]
        public void AcceptAvailableRegionalAutoQuestForTest_DoesNotUseRegionMetadataWhenExplicitAutoAcceptTriggerExists()
        {
            DynamicQuestDefinition itemTriggered = WorldOfferQuest();
            itemTriggered.Id = "quest-auto-item";
            itemTriggered.StartMode = DynamicQuestStartMode.AutoAccept;
            itemTriggered.Tags = new[] { "region:1", "trigger:item-acquired" };
            DynamicQuestRuntimeService.Instance.AddQuest(itemTriggered);

            bool regionAccepted = DynamicQuestRuntimeService.Instance.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1,
                521100,
                492100);
            DynamicQuestProgressSnapshot beforeItem = DynamicQuestRuntimeService.Instance.GetProgressSnapshot(
                "DummyQuest001",
                "DummyQuest001",
                true);

            bool itemAccepted = DynamicQuestRuntimeService.Instance.AcceptAvailableWorldQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                "item-acquired");
            DynamicQuestProgressSnapshot afterItem = DynamicQuestRuntimeService.Instance.GetProgressSnapshot(
                "DummyQuest001",
                "DummyQuest001",
                true);

            Assert.Multiple(() =>
            {
                Assert.That(regionAccepted, Is.False);
                Assert.That(beforeItem.Active, Is.Empty);
                Assert.That(itemAccepted, Is.True);
                Assert.That(afterItem.Active.Single().QuestId, Is.EqualTo("quest-auto-item"));
            });
        }

        [Test]
        public void AcceptAvailableRegionalAutoQuestForTest_AllowsMultipleSameRegionAutoQuestsAtActiveLimit()
        {
            DynamicQuestRuntimeService service = new(new FakeDynamicQuestProgressRepository());

            DynamicQuestDefinition first = WorldOfferQuest();
            first.Id = "quest-auto-region-first";
            first.StartMode = DynamicQuestStartMode.AutoAccept;
            first.Tags = new[] { "region:1" };
            first.CreatedAt = DateTime.UtcNow.AddMinutes(-2);
            service.AddQuest(first);

            DynamicQuestDefinition second = WorldOfferQuest();
            second.Id = "quest-auto-region-second";
            second.StartMode = DynamicQuestStartMode.AutoAccept;
            second.Tags = new[] { "region:1" };
            second.CreatedAt = DateTime.UtcNow.AddMinutes(-1);
            service.AddQuest(second);

            bool acceptedFirst = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1,
                521100,
                492100);
            bool acceptedSecond = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1,
                521100,
                492100);
            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(acceptedFirst, Is.True);
                Assert.That(acceptedSecond, Is.True);
                Assert.That(snapshot.Active.Select(item => item.QuestId), Is.EquivalentTo(new[]
                {
                    "quest-auto-region-first",
                    "quest-auto-region-second"
                }));
            });
        }

        [Test]
        public void AcceptQuestForTest_BlocksDifferentRegionWhenActiveLimitReached()
        {
            DynamicQuestRuntimeService service = new(new FakeDynamicQuestProgressRepository());

            DynamicQuestDefinition first = WorldOfferQuest();
            first.Id = "quest-region-one";
            first.StartRegionId = 1;
            service.AddQuest(first);

            DynamicQuestDefinition second = WorldOfferQuest();
            second.Id = "quest-region-two";
            second.StartRegionId = 2;
            service.AddQuest(second);

            bool acceptedFirst = service.AcceptQuestForTest("DummyQuest001", "DummyQuest001", first.Id);
            bool acceptedSecond = service.AcceptQuestForTest("DummyQuest001", "DummyQuest001", second.Id);
            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(acceptedFirst, Is.True);
                Assert.That(acceptedSecond, Is.False);
                Assert.That(snapshot.Active.Select(item => item.QuestId), Is.EqualTo(new[] { "quest-region-one" }));
            });
        }

        [Test]
        public void GetAvailableWorldQuestIdsForTest_ExcludesAutoAcceptCandidateWhenIncludeAutoAcceptFalse()
        {
            DynamicQuestRuntimeService service = new(new FakeDynamicQuestProgressRepository());

            DynamicQuestDefinition autoAccept = WorldOfferQuest();
            autoAccept.Id = "quest-auto-region-signal";
            autoAccept.StartMode = DynamicQuestStartMode.AutoAccept;
            autoAccept.Tags = new[] { "region:1" };
            service.AddQuest(autoAccept);

            IList<string> withAutoAccept = service.GetAvailableWorldQuestIdsForTest(
                "DummyQuest001",
                1,
                "region:1",
                includeAutoAccept: true);
            IList<string> withoutAutoAccept = service.GetAvailableWorldQuestIdsForTest(
                "DummyQuest001",
                1,
                "region:1",
                includeAutoAccept: false);

            Assert.Multiple(() =>
            {
                Assert.That(withAutoAccept, Does.Contain("quest-auto-region-signal"));
                Assert.That(withoutAutoAccept, Does.Not.Contain("quest-auto-region-signal"));
                Assert.That(withoutAutoAccept, Is.Empty);
            });
        }

        [Test]
        public void TryAcceptWorldQuest_MovementOriginActiveLimitFailureIsSilent()
        {
            DynamicQuestRuntimeService service = DynamicQuestRuntimeService.Instance;
            DynamicQuestDefinition first = WorldOfferQuest();
            first.Id = "quest-active-limit-first";
            first.StartRegionId = 1;
            service.AddQuest(first);

            DynamicQuestDefinition second = WorldOfferQuest();
            second.Id = "quest-active-limit-second";
            second.StartRegionId = 2;
            service.AddQuest(second);

            bool acceptedFirst = service.AcceptQuestForTest("DummyQuest001", "DummyQuest001", first.Id);
            GamePlayer player = CreateJournalTestPlayer("DummyQuest001", out RecordingPacketLib recorder);

            bool acceptedSecond = service.TryAcceptWorldQuest(
                player,
                second.Id,
                "region-entered:2",
                showFailureMessage: false);

            Assert.Multiple(() =>
            {
                Assert.That(acceptedFirst, Is.True);
                Assert.That(acceptedSecond, Is.False);
                Assert.That(recorder.Messages, Is.Empty);
            });
        }

        [Test]
        public void BuildActiveJournalProgressIdsForTest_RemovesCompletedProgressFromJournalProjection()
        {
            DynamicQuestRuntimeService service = new(new FakeDynamicQuestProgressRepository());
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.Id = "quest-journal-projection";
            service.AddQuest(quest);

            bool accepted = service.AcceptQuestForTest("DummyQuest001", "Dummy Quest", quest.Id);
            IList<string> activeJournalIds = service.BuildActiveJournalProgressIdsForTest("DummyQuest001", "Dummy Quest");
            service.RecordExploreProgressForTest("DummyQuest001", 1, 521000, 492000);
            service.RecordKillProgressForTest("DummyQuest001", "forest spiderling", 1, 1);
            IList<string> completedJournalIds = service.BuildActiveJournalProgressIdsForTest("DummyQuest001", "Dummy Quest");
            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "Dummy Quest", true);

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(activeJournalIds, Is.EqualTo(new[]
                {
                    DynamicQuestRuntimeService.BuildJournalProgressId("DummyQuest001", "quest-journal-projection")
                }));
                Assert.That(completedJournalIds, Is.Empty);
                Assert.That(snapshot.CompletedQuestIds, Does.Contain("quest-journal-projection"));
            });
        }

        [Test]
        public void SyncDynamicQuestJournal_AddsUpdatesAndRemovesGamePlayerQuestListAdapter()
        {
            DynamicQuestRuntimeService service = DynamicQuestRuntimeService.Instance;
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.Id = "quest-journal-sync";
            service.AddQuest(quest);

            bool accepted = service.AcceptQuestForTest("DummyQuest001", "DummyQuest001", quest.Id);
            GamePlayer player = CreateJournalTestPlayer("DummyQuest001", out RecordingPacketLib recorder);

            service.SyncDynamicQuestJournal(player);
            DynamicQuestJournalAdapter adapter = player.QuestList.Keys.OfType<DynamicQuestJournalAdapter>().Single();
            string initialDescription = adapter.Description;
            int updatesAfterAdd = recorder.QuestUpdates.Count;

            service.RecordExploreProgressForTest("DummyQuest001", 1, 521000, 492000);
            service.SyncDynamicQuestJournal(player);
            DynamicQuestJournalAdapter updatedAdapter = player.QuestList.Keys.OfType<DynamicQuestJournalAdapter>().Single();
            string killDescription = updatedAdapter.Description;

            service.RecordKillProgressForTest("DummyQuest001", "forest spiderling", 1, 1);
            service.SyncDynamicQuestJournal(player);

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(updatesAfterAdd, Is.EqualTo(1));
                Assert.That(updatedAdapter, Is.SameAs(adapter));
                Assert.That(updatedAdapter.Description, Is.Not.EqualTo(initialDescription));
                Assert.That(initialDescription, Does.Contain("목표: 숲의 균열 조사"));
                Assert.That(initialDescription, Does.Contain("힌트: 퀘스트 지역 안에서 해당 위치로 이동하세요."));
                Assert.That(killDescription, Does.Contain("목표: forest spiderling 처치"));
                Assert.That(killDescription, Does.Contain("진행: 0/1"));
                Assert.That(killDescription, Does.Contain("힌트: 이 동적 퀘스트가 시작된 지역 안에서 대상 몬스터를 찾으세요."));
                Assert.That(recorder.QuestUpdates.Count, Is.GreaterThan(updatesAfterAdd));
                Assert.That(player.QuestList.Keys.OfType<DynamicQuestJournalAdapter>(), Is.Empty);
                Assert.That(recorder.QuestRemoves, Is.EqualTo(new byte[] { 0 }));
                Assert.That(recorder.Messages, Is.Empty);
            });
        }

        [Test]
        public void DynamicQuestJournalAdapter_AbortCancelsRuntimeProgressAndRemovesQuestListEntry()
        {
            DynamicQuestRuntimeService service = DynamicQuestRuntimeService.Instance;
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.Id = "quest-journal-abort";
            service.AddQuest(quest);

            bool accepted = service.AcceptQuestForTest("DummyQuest001", "DummyQuest001", quest.Id);
            GamePlayer player = CreateJournalTestPlayer("DummyQuest001", out RecordingPacketLib recorder);
            service.SyncDynamicQuestJournal(player);

            DynamicQuestJournalAdapter adapter = player.QuestList.Keys.OfType<DynamicQuestJournalAdapter>().Single();
            adapter.AbortQuest();
            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(snapshot.Active, Is.Empty);
                Assert.That(player.QuestList.Keys.OfType<DynamicQuestJournalAdapter>(), Is.Empty);
                Assert.That(recorder.QuestRemoves, Is.EqualTo(new byte[] { 0 }));
            });
        }

        [Test]
        public void DynamicQuestJournalAdapterIdentity_MatchesOnlySameProgressId()
        {
            DynamicQuestJournalAdapter active = new(
                "DummyQuest001",
                "quest-journal-one",
                1,
                "Journal One",
                "First active dynamic quest",
                1,
                1);
            DynamicQuestJournalAdapter sameProgress = new(
                "DummyQuest001",
                "quest-journal-one",
                1,
                "Journal One Duplicate",
                "Duplicate dynamic quest adapter",
                1,
                1);
            DynamicQuestJournalAdapter differentProgress = new(
                "DummyQuest001",
                "quest-journal-two",
                1,
                "Journal Two",
                "Second active dynamic quest",
                1,
                1);

            Assert.Multiple(() =>
            {
                Assert.That(
                    GamePlayer.DynamicQuestJournalAdaptersRepresentSameProgressForTest(active, sameProgress),
                    Is.True);
                Assert.That(
                    GamePlayer.DynamicQuestJournalAdaptersRepresentSameProgressForTest(active, differentProgress),
                    Is.False);
            });
        }

        [Test]
        public void PlayerLevelMatchesQuestForTest_AllowsOverlevelMobGrowthBranchQuest()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.MinLevel = 1;
            quest.MaxLevel = 5;
            quest.Tags = new[] { "branch:mob-growth", "world-signal:mob-growth:killed:region:1" };

            bool underLevel = DynamicQuestRuntimeService.PlayerLevelMatchesQuestForTest(quest, 0);
            bool inBand = DynamicQuestRuntimeService.PlayerLevelMatchesQuestForTest(quest, 5);
            bool overLevel = DynamicQuestRuntimeService.PlayerLevelMatchesQuestForTest(quest, 15);

            Assert.Multiple(() =>
            {
                Assert.That(underLevel, Is.False);
                Assert.That(inBand, Is.True);
                Assert.That(overLevel, Is.True);
            });
        }

        [Test]
        public void PlayerLevelMatchesQuestForTest_RejectsOverlevelNonBranchQuest()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.MinLevel = 1;
            quest.MaxLevel = 5;
            quest.Tags = Array.Empty<string>();

            bool overLevel = DynamicQuestRuntimeService.PlayerLevelMatchesQuestForTest(quest, 15);

            Assert.That(overLevel, Is.False);
        }

        [Test]
        public void AcceptQuestForTest_ReplacesAutoAcceptProgressWhenManualOfferNeedsSlot()
        {
            DynamicQuestDefinition autoAccept = WorldOfferQuest();
            autoAccept.Id = "quest-auto-region";
            autoAccept.StartMode = DynamicQuestStartMode.AutoAccept;
            autoAccept.Tags = new[] { "region:1" };
            DynamicQuestRuntimeService.Instance.AddQuest(autoAccept);

            DynamicQuestDefinition manualOffer = WorldOfferQuest();
            manualOffer.Id = "quest-manual-region";
            manualOffer.StartMode = DynamicQuestStartMode.WorldOffer;
            manualOffer.StartRegionId = 2;
            DynamicQuestRuntimeService.Instance.AddQuest(manualOffer);

            bool autoAccepted = DynamicQuestRuntimeService.Instance.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1);
            bool manualAccepted = DynamicQuestRuntimeService.Instance.AcceptQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                "quest-manual-region",
                "manual_offer");

            DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);
            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(autoAccepted, Is.True);
                Assert.That(manualAccepted, Is.True);
                Assert.That(snapshot.Active.Select(item => item.QuestId), Is.EqualTo(new[] { "quest-manual-region" }));
                Assert.That(timeline.Events.Any(evt =>
                    evt.QuestId == "quest-auto-region" &&
                    evt.EventType == "quest_cancelled" &&
                    evt.Detail == "replaced_by_manual_dynamic_quest"), Is.True);
            });
        }

        [Test]
        public void ProgressSnapshot_HidesCompletedNpcLessQuestAfterTerminalNode()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.Id = "quest-auto-complete";
            quest.StartMode = DynamicQuestStartMode.AutoAccept;
            quest.Tags = new[] { "region:1" };
            service.AddQuest(quest);

            bool accepted = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1);
            bool explored = service.RecordExploreProgressForTest(
                "DummyQuest001",
                1,
                521000,
                492000);
            bool killed = service.RecordKillProgressForTest(
                "DummyQuest001",
                "forest spiderling",
                1,
                1);

            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);
            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot("DummyQuest001", "DummyQuest001", true);
            DbDynamicQuestProgress row = repository.Rows.Values.Single();
            bool acceptedAgain = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1);

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(explored, Is.True);
                Assert.That(killed, Is.True);
                Assert.That(snapshot.Active, Is.Empty);
                Assert.That(row.Completed, Is.True);
                Assert.That(row.IsComplete, Is.True);
                Assert.That(row.IsActive, Is.False);
                Assert.That(acceptedAgain, Is.False);
                Assert.That(timeline.Events.Select(evt => evt.EventType), Does.Contain("quest_completed"));
                Assert.That(timeline.Events.Select(evt => evt.EventType), Does.Contain("quest_rewarded"));
            });
        }

        [Test]
        public void AcceptAvailableRegionalAutoQuestForTest_AllowsNextQuestWithSameTriggerAfterAutoAcceptCompletion()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);

            DynamicQuestDefinition first = WorldOfferQuest();
            first.Id = "quest-auto-region-first";
            first.StartMode = DynamicQuestStartMode.AutoAccept;
            first.Tags = new[] { "region:1" };
            first.CreatedAt = DateTime.UtcNow.AddMinutes(-2);
            service.AddQuest(first);

            DynamicQuestDefinition second = WorldOfferQuest();
            second.Id = "quest-auto-region-second";
            second.StartMode = DynamicQuestStartMode.AutoAccept;
            second.Tags = new[] { "region:1" };
            second.CreatedAt = DateTime.UtcNow.AddMinutes(-1);
            service.AddQuest(second);

            bool acceptedFirst = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1);
            bool explored = service.RecordExploreProgressForTest(
                "DummyQuest001",
                1,
                521000,
                492000);
            bool killed = service.RecordKillProgressForTest(
                "DummyQuest001",
                "forest spiderling",
                1,
                1);
            bool acceptedSecond = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1);

            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(acceptedFirst, Is.True);
                Assert.That(explored, Is.True);
                Assert.That(killed, Is.True);
                Assert.That(acceptedSecond, Is.True);
                Assert.That(snapshot.Active.Single().QuestId, Is.EqualTo("quest-auto-region-second"));
                Assert.That(snapshot.CompletedQuestIds, Does.Contain("quest-auto-region-first"));
                Assert.That(snapshot.CompletedQuestIds, Does.Not.Contain("quest-auto-region-second"));
            });
        }

        [Test]
        public void AcceptAvailableRegionalAutoQuestForTest_BlocksCompletedStoryFamilyVariant()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);

            DynamicQuestDefinition lowLevelVariant = WorldOfferQuest();
            lowLevelVariant.Id = "quest-family-low";
            lowLevelVariant.StartMode = DynamicQuestStartMode.AutoAccept;
            lowLevelVariant.Tags = new[] { "region:1", "story-family:haunted-road" };
            lowLevelVariant.MinLevel = 1;
            lowLevelVariant.MaxLevel = 10;
            lowLevelVariant.CreatedAt = DateTime.UtcNow.AddMinutes(-3);
            service.AddQuest(lowLevelVariant);

            DynamicQuestDefinition highLevelVariant = WorldOfferQuest();
            highLevelVariant.Id = "quest-family-high";
            highLevelVariant.StartMode = DynamicQuestStartMode.AutoAccept;
            highLevelVariant.Tags = new[] { "region:1", "story-family:haunted-road" };
            highLevelVariant.MinLevel = 1;
            highLevelVariant.MaxLevel = 50;
            highLevelVariant.CreatedAt = DateTime.UtcNow.AddMinutes(-2);
            service.AddQuest(highLevelVariant);

            bool acceptedLow = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1);
            bool explored = service.RecordExploreProgressForTest(
                "DummyQuest001",
                1,
                521000,
                492000);
            bool killed = service.RecordKillProgressForTest(
                "DummyQuest001",
                "forest spiderling",
                1,
                1);
            bool acceptedSameFamily = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                30,
                1);

            DynamicQuestDefinition differentFamily = WorldOfferQuest();
            differentFamily.Id = "quest-family-different";
            differentFamily.StartMode = DynamicQuestStartMode.AutoAccept;
            differentFamily.Tags = new[] { "region:1", "story-family:market-shadow" };
            differentFamily.MinLevel = 1;
            differentFamily.MaxLevel = 50;
            differentFamily.CreatedAt = DateTime.UtcNow.AddMinutes(-1);
            service.AddQuest(differentFamily);

            bool acceptedDifferentFamily = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                30,
                1);

            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(acceptedLow, Is.True);
                Assert.That(explored, Is.True);
                Assert.That(killed, Is.True);
                Assert.That(acceptedSameFamily, Is.False);
                Assert.That(acceptedDifferentFamily, Is.True);
                Assert.That(snapshot.CompletedQuestIds, Does.Contain("quest-family-low"));
                Assert.That(snapshot.Active.Single().QuestId, Is.EqualTo("quest-family-different"));
            });
        }

        [Test]
        public void AcceptAvailableRegionalAutoQuestForTest_BlocksActiveStoryFamilyVariant()
        {
            Properties.KDAOC_DYNAMIC_QUEST_MAX_ACTIVE_PER_PLAYER = 2;
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);

            DynamicQuestDefinition first = WorldOfferQuest();
            first.Id = "quest-family-active-first";
            first.StartMode = DynamicQuestStartMode.AutoAccept;
            first.Tags = new[] { "region:1", "story-family:haunted-road" };
            first.CreatedAt = DateTime.UtcNow.AddMinutes(-3);
            service.AddQuest(first);

            DynamicQuestDefinition sameFamily = WorldOfferQuest();
            sameFamily.Id = "quest-family-active-second";
            sameFamily.StartMode = DynamicQuestStartMode.AutoAccept;
            sameFamily.Tags = new[] { "region:1", "story-family:haunted-road" };
            sameFamily.CreatedAt = DateTime.UtcNow.AddMinutes(-2);
            service.AddQuest(sameFamily);

            bool acceptedFirst = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1);
            bool acceptedSameFamily = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1);

            DynamicQuestDefinition differentFamily = WorldOfferQuest();
            differentFamily.Id = "quest-family-active-different";
            differentFamily.StartMode = DynamicQuestStartMode.AutoAccept;
            differentFamily.Tags = new[] { "region:1", "story-family:market-shadow" };
            differentFamily.CreatedAt = DateTime.UtcNow.AddMinutes(-1);
            service.AddQuest(differentFamily);

            bool acceptedDifferentFamily = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1);
            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(acceptedFirst, Is.True);
                Assert.That(acceptedSameFamily, Is.False);
                Assert.That(acceptedDifferentFamily, Is.True);
                Assert.That(snapshot.Active.Select(item => item.QuestId), Does.Contain("quest-family-active-first"));
                Assert.That(snapshot.Active.Select(item => item.QuestId), Does.Contain("quest-family-active-different"));
                Assert.That(snapshot.Active.Select(item => item.QuestId), Does.Not.Contain("quest-family-active-second"));
            });
        }

        [Test]
        public void AcceptAvailableRegionalAutoQuestForTest_LoadsCompletedStoryFamilyBeforeOfferingVariant()
        {
            DynamicQuestDefinition completedVariant = WorldOfferQuest();
            completedVariant.Id = "quest-family-low";
            completedVariant.StartMode = DynamicQuestStartMode.AutoAccept;
            completedVariant.Tags = new[] { "region:1", "story-family:haunted-road" };

            FakeDynamicQuestProgressRepository repository = new();
            repository.Rows["dummyquest001:quest-family-low"] = new DbDynamicQuestProgress
            {
                ProgressId = "dummyquest001:quest-family-low",
                PlayerKey = "DummyQuest001",
                PlayerName = "DummyQuest001",
                QuestId = "quest-family-low",
                Completed = true,
                IsComplete = true,
                IsActive = false,
                QuestSnapshotJson = JsonSerializer.Serialize(completedVariant),
                AcceptedAt = DateTime.UtcNow.AddMinutes(-5),
                UpdatedAt = DateTime.UtcNow.AddMinutes(-4),
                CreatedAt = DateTime.UtcNow.AddMinutes(-5)
            };

            DynamicQuestRuntimeService service = new(repository);
            DynamicQuestDefinition highLevelVariant = WorldOfferQuest();
            highLevelVariant.Id = "quest-family-high";
            highLevelVariant.StartMode = DynamicQuestStartMode.AutoAccept;
            highLevelVariant.Tags = new[] { "region:1", "story-family:haunted-road" };
            highLevelVariant.MinLevel = 1;
            highLevelVariant.MaxLevel = 50;
            service.AddQuest(highLevelVariant);

            bool accepted = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                30,
                1);
            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.False);
                Assert.That(snapshot.CompletedQuestIds, Does.Contain("quest-family-low"));
                Assert.That(snapshot.Active, Is.Empty);
            });
        }

        [Test]
        public void AcceptAvailableRegionalAutoQuestForTest_UnlocksStoryEpisodeAfterRequiredFamily()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);

            DynamicQuestDefinition intro = WorldOfferQuest();
            intro.Id = "quest-arc-intro";
            intro.StartMode = DynamicQuestStartMode.AutoAccept;
            intro.Tags = new[]
            {
                "region:1",
                "story-family:haunted-road-intro",
                "story-chain:haunted-road",
                "story-episode:1/3",
                "story-archetype:witness-conspiracy"
            };
            intro.CreatedAt = DateTime.UtcNow.AddMinutes(-3);
            service.AddQuest(intro);

            DynamicQuestDefinition sequel = WorldOfferQuest();
            sequel.Id = "quest-arc-sequel";
            sequel.StartMode = DynamicQuestStartMode.AutoAccept;
            sequel.Tags = new[]
            {
                "region:1",
                "story-family:haunted-road-sequel",
                "story-chain:haunted-road",
                "story-episode:2/3",
                "requires-story-family:haunted-road-intro",
                "requires-story-archetype:witness-conspiracy"
            };
            sequel.CreatedAt = DateTime.UtcNow.AddMinutes(-2);
            service.AddQuest(sequel);

            bool acceptedIntro = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1);
            bool explored = service.RecordExploreProgressForTest(
                "DummyQuest001",
                1,
                521000,
                492000);
            bool killed = service.RecordKillProgressForTest(
                "DummyQuest001",
                "forest spiderling",
                1,
                1);
            bool acceptedSequel = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1);
            DynamicQuestWorldMemorySnapshot memory = service.GetWorldMemorySnapshot("DummyQuest001", "DummyQuest001", true);
            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);
            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(acceptedIntro, Is.True);
                Assert.That(explored, Is.True);
                Assert.That(killed, Is.True);
                Assert.That(acceptedSequel, Is.True);
                Assert.That(snapshot.CompletedQuestIds, Does.Contain("quest-arc-intro"));
                Assert.That(snapshot.Active.Single().QuestId, Is.EqualTo("quest-arc-sequel"));
                Assert.That(memory.CompletedStoryFamilyIds, Does.Contain("haunted-road-intro"));
                Assert.That(memory.Signals, Does.Contain("story-family:haunted-road-intro:completed"));
                Assert.That(memory.Signals, Does.Contain("story-archetype:witness-conspiracy:completed"));
                Assert.That(memory.Signals, Does.Contain("story-chain:haunted-road:progress"));
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "world_memory_marked" &&
                    evt.QuestId == "quest-arc-intro"), Is.True);
            });
        }

        [Test]
        public void AcceptAvailableRegionalAutoQuestForTest_LoadsChoiceMemoryBeforeOfferingFollowup()
        {
            DynamicQuestDefinition completed = WorldOfferQuest();
            completed.Id = "quest-choice-memory-intro";
            completed.StartMode = DynamicQuestStartMode.AutoAccept;
            completed.Tags = new[]
            {
                "region:1",
                "story-family:choice-memory-intro",
                "story-chain:choice-memory"
            };

            FakeDynamicQuestProgressRepository repository = new();
            repository.Rows["dummyquest001:quest-choice-memory-intro"] = new DbDynamicQuestProgress
            {
                ProgressId = "dummyquest001:quest-choice-memory-intro",
                PlayerKey = "DummyQuest001",
                PlayerName = "DummyQuest001",
                QuestId = "quest-choice-memory-intro",
                Completed = true,
                IsComplete = true,
                IsActive = false,
                ChoiceHistoryJson = JsonSerializer.Serialize(new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                {
                    ["choice"] = "followup"
                }),
                QuestSnapshotJson = JsonSerializer.Serialize(completed),
                AcceptedAt = DateTime.UtcNow.AddMinutes(-5),
                UpdatedAt = DateTime.UtcNow.AddMinutes(-4),
                CreatedAt = DateTime.UtcNow.AddMinutes(-5)
            };

            DynamicQuestRuntimeService service = new(repository);
            DynamicQuestDefinition followup = WorldOfferQuest();
            followup.Id = "quest-choice-memory-followup";
            followup.StartMode = DynamicQuestStartMode.AutoAccept;
            followup.Tags = new[]
            {
                "region:1",
                "story-family:choice-memory-followup",
                "story-chain:choice-memory",
                "requires-memory:followup-observed",
                "requires-choice:followup"
            };
            service.AddQuest(followup);

            bool accepted = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1);
            DynamicQuestWorldMemorySnapshot memory = service.GetWorldMemorySnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(memory.Signals, Does.Contain("followup-observed"));
                Assert.That(memory.Signals, Does.Contain("choice:followup"));
                Assert.That(memory.Signals, Does.Contain("choice:choice:followup"));
            });
        }

        [Test]
        public void AcceptAvailableRegionalAutoQuestForTest_PrefersDummyEvaluationOfferOverOlderRegionalQuest()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);

            DynamicQuestDefinition olderRegional = WorldOfferQuest();
            olderRegional.Id = "quest-auto-region-older";
            olderRegional.StartMode = DynamicQuestStartMode.AutoAccept;
            olderRegional.Tags = new[] { "region:1" };
            olderRegional.CreatedAt = DateTime.UtcNow.AddMinutes(-2);
            service.AddQuest(olderRegional);

            DynamicQuestDefinition evaluationOffer = WorldOfferQuest();
            evaluationOffer.Id = "quest-auto-region-evaluation";
            evaluationOffer.StartMode = DynamicQuestStartMode.AutoAccept;
            evaluationOffer.Tags = new[] { "region:1", "dummy-evaluation-offer" };
            evaluationOffer.CreatedAt = DateTime.UtcNow.AddMinutes(-1);
            service.AddQuest(evaluationOffer);

            bool accepted = service.AcceptAvailableRegionalAutoQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                1,
                1);

            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(snapshot.Active.Single().QuestId, Is.EqualTo("quest-auto-region-evaluation"));
                Assert.That(snapshot.Active.Select(item => item.QuestId), Does.Not.Contain("quest-auto-region-older"));
            });
        }

        [TestCase("", 1, 521000, 492000, 450, "location")]
        [TestCase("흔적", 0, 521000, 492000, 450, "region")]
        [TestCase("흔적", 1, 0, 492000, 450, "coordinate")]
        [TestCase("흔적", 1, 521000, 0, 450, "coordinate")]
        [TestCase("흔적", 1, 521000, 492000, 63, "radius")]
        [TestCase("흔적", 1, 521000, 492000, 2001, "radius")]
        public void AddQuest_RejectsInvalidExploreObjective(string locationName, int regionId, int x, int y, int radius, string expected)
        {
            DynamicQuestDefinition quest = ExploreGraphQuest();
            DynamicQuestNode explore = quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Explore);
            explore.Objective.LocationName = locationName;
            explore.Objective.RegionId = (ushort)regionId;
            explore.Objective.X = x;
            explore.Objective.Y = y;
            explore.Objective.Radius = radius;

            DynamicQuestResult result = DynamicQuestRuntimeService.Instance.AddQuest(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.False);
                Assert.That(result.Message, Does.Contain(expected).IgnoreCase);
            });
        }

        [Test]
        public void ProgressSnapshot_IncludesGraphNodeState()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(GraphQuest());
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                playerKey: "DummyQuest001",
                questId: "quest-graph",
                currentNodeId: "kill",
                completedNodeIds: new[] { "talk" },
                nodeCounters: new System.Collections.Generic.Dictionary<string, int> { ["kill"] = 0 });

            DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);
            DynamicQuestProgressItem item = snapshot.Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(item.CurrentNodeId, Is.EqualTo("kill"));
                Assert.That(item.CurrentNodeType, Is.EqualTo(DynamicQuestNodeType.Kill));
                Assert.That(item.CurrentObjective.TargetName, Is.EqualTo("black wolf pup"));
                Assert.That(item.CompletedNodeIds, Is.EqualTo(new[] { "talk" }));
                Assert.That(item.Nodes.Select(node => node.Id), Does.Contain("choice"));
            });
        }

        [Test]
        public void TimelineSnapshot_RecordsProgressEventsWithoutMutatingActiveProgress()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(ExploreGraphQuest());
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-explore",
                "explore",
                new[] { "talk" },
                new System.Collections.Generic.Dictionary<string, int>());

            DynamicQuestRuntimeService.Instance.RecordExploreProgressForTest("DummyQuest001", 1, 521250, 492250);
            DynamicQuestRuntimeService.Instance.RecordKillProgressForTest("DummyQuest001", "black wolf pup", 1, 1);
            DynamicQuestRuntimeService.Instance.RecordNpcInteractionForTest("DummyQuest001", "seed-npc-1", 1);
            DynamicQuestRuntimeService.Instance.SelectChoiceForTest("DummyQuest001", "quest-explore", "safe");

            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot(
                "DummyQuest001",
                "DummyQuest001",
                true,
                200);
            DynamicQuestProgressSnapshot progress = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);
            string[] eventTypes = timeline.Events.Select(item => item.EventType).ToArray();
            string choiceOutcome = timeline.Events
                .FirstOrDefault(item => item.EventType == "choice_outcome_scene")
                ?.Detail ?? string.Empty;
            string choiceSceneOutcome = timeline.Events
                .FirstOrDefault(item =>
                    item.EventType == "scene_beat_outcome" &&
                    item.Detail.Contains("role:choice_containment", StringComparison.Ordinal))
                ?.Detail ?? string.Empty;
            string lastProgressEventType = timeline.Events
                .Where(item => item.EventType is not "presentation_beat" and not "presentation_spotlight" and not "narrative_scene" and not "narrative_scene_presented" and not "journal_entry" and not "cinematic_action" and not "scene_beat_outcome" and not "scene_choreography_phase" and not "scene_actor_exchange" and not "scene_exchange_outcome" and not "scene_consequence" and not "scene_world_signal" and not "cinematic_cleanup" and not "choice_outcome_scene")
                .Last()
                .EventType;

            Assert.Multiple(() =>
            {
                Assert.That(timeline.Player, Is.EqualTo("DummyQuest001"));
                Assert.That(timeline.Online, Is.True);
                Assert.That(progress.Active, Has.Count.EqualTo(1));
                Assert.That(progress.Active.Single().CurrentNodeId, Is.EqualTo("complete"));
                Assert.That(eventTypes, Does.Contain("explore_complete"));
                Assert.That(eventTypes, Does.Contain("kill_progress"));
                Assert.That(eventTypes, Does.Contain("npc_interaction"));
                Assert.That(eventTypes, Does.Contain("choice_selected"));
                Assert.That(eventTypes, Does.Contain("choice_outcome_scene"));
                Assert.That(choiceOutcome, Does.Contain("outcome:containment"));
                Assert.That(choiceOutcome, Does.Contain("tactic:screen"));
                Assert.That(choiceSceneOutcome, Does.Contain("action:defender_intercept"));
                Assert.That(timeline.Events.Any(item =>
                    item.EventType == "scene_world_signal" &&
                    item.NodeId == "choice" &&
                    item.Detail == "scene:choice_containment"), Is.True);
                Assert.That(eventTypes, Does.Contain("quest_completed"));
                Assert.That(eventTypes, Does.Contain("cinematic_action"));
                Assert.That(lastProgressEventType, Is.EqualTo("quest_completed"));
            });
        }

        [Test]
        public void TimelineSnapshot_RecordsNarrativeJournalAndPresentationWhenStoryNodesAreEntered()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.StoryNarrativeJson = "[" +
                "{\"nodeId\":\"explore\",\"sceneType\":\"Intro\",\"title\":\"숲의 숨죽임\",\"body\":\"울타리가 찢겼다.\",\"journalEntry\":\"숲 가장자리의 흔적을 조사한다.\",\"mood\":\"ominous\",\"revealPolicy\":\"FirstSeenOnly\"}," +
                "{\"nodeId\":\"kill\",\"sceneType\":\"Objective\",\"title\":\"발톱의 주인\",\"body\":\"흔적은 목표에게 이어진다.\",\"journalEntry\":\"목표를 처리해야 한다.\",\"mood\":\"urgent\",\"revealPolicy\":\"Always\"}" +
                "]";
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnNodeEnter\",\"speaker\":\"Narrator\",\"text\":\"숲이 숨을 죽인다.\",\"emotion\":\"fear\",\"emote\":\"Shiver\"}" +
                "]";
            DynamicQuestRuntimeService.Instance.AddQuest(quest);

            bool accepted = DynamicQuestRuntimeService.Instance.AcceptQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                "quest-world-offer",
                "world_region_entered");
            bool explored = DynamicQuestRuntimeService.Instance.RecordExploreProgressForTest(
                "DummyQuest001",
                1,
                521000,
                492000);

            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot(
                "DummyQuest001",
                "DummyQuest001",
                true,
                100);
            DynamicQuestProgressItem progress = DynamicQuestRuntimeService.Instance
                .GetProgressSnapshot("DummyQuest001", "DummyQuest001", true)
                .Active
                .Single();

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(explored, Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "narrative_scene" &&
                    evt.NodeId == "explore" &&
                    evt.Detail.Contains("숲의 숨죽임")), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "journal_entry" &&
                    evt.NodeId == "explore" &&
                    evt.Detail == "숲 가장자리의 흔적을 조사한다."), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "presentation_beat" &&
                    evt.NodeId == "explore" &&
                    evt.Detail.Contains("Shiver")), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "narrative_scene_presented"), Is.False);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "narrative_scene" &&
                    evt.NodeId == "kill" &&
                    evt.Detail.Contains("발톱의 주인")), Is.True);
                Assert.That(progress.JournalEntries.Select(entry => entry.JournalEntry), Does.Contain("숲 가장자리의 흔적을 조사한다."));
                Assert.That(progress.JournalEntries.Select(entry => entry.JournalEntry), Does.Contain("목표를 처리해야 한다."));
                Assert.That(progress.JournalEntries.Single(entry => entry.NodeId == "kill").Current, Is.True);
            });
        }

        [Test]
        public void TimelineSnapshot_RecordsPresentationTriggersForAcceptChoiceAndCompletion()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();
            DynamicQuestNode kill = quest.Nodes.Single(node => node.Id == "kill");
            DynamicQuestNode complete = quest.Nodes.Single(node => node.Id == "complete");
            kill.Edges = new[] { new DynamicQuestEdge { ToNodeId = "choice", Condition = DynamicQuestEdgeCondition.ObjectiveComplete } };
            quest.Nodes = quest.Nodes
                .Where(node => node.Id != "complete")
                .Concat(new[]
                {
                    new DynamicQuestNode
                    {
                        Id = "choice",
                        Type = DynamicQuestNodeType.Choice,
                        Title = "균열의 처리",
                        Text = "균열의 잔향을 어떻게 다룰까요?",
                        Objective = new DynamicQuestObjective
                        {
                            Choices = new[]
                            {
                                new DynamicQuestChoice
                                {
                                    Id = "safe",
                                    Label = "지금 봉합한다",
                                    Text = "균열을 즉시 봉합한다.",
                                    Consequence = "숲은 조용해졌지만, 멀리서 희미한 파문이 남았다."
                                },
                                new DynamicQuestChoice
                                {
                                    Id = "followup",
                                    Label = "잔향을 더 본다",
                                    Text = "잔향을 더 관찰한다.",
                                    Consequence = "균열 너머의 흐름을 조금 더 읽었다."
                                }
                            }
                        },
                        Edges = new[]
                        {
                            new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "safe", Priority = 0 },
                            new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "followup", Priority = 1 }
                        }
                    },
                    complete
                })
                .ToArray();
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnAccept\",\"speaker\":\"System\",\"text\":\"낡은 지도 위로 숲의 균열이 희미하게 떠오른다.\",\"emotion\":\"hope\",\"emote\":\"Cheer\"}," +
                "{\"nodeId\":\"choice\",\"trigger\":\"OnChoiceSelected\",\"speaker\":\"System\",\"text\":\"선택의 여파가 숲 안쪽으로 번진다.\",\"emotion\":\"warning\",\"emote\":\"Point\"}," +
                "{\"nodeId\":\"complete\",\"trigger\":\"OnComplete\",\"speaker\":\"System\",\"text\":\"균열의 마지막 빛이 흙 속으로 스며든다.\",\"emotion\":\"gratitude\",\"emote\":\"Bow\"}" +
                "]";
            DynamicQuestRuntimeService.Instance.AddQuest(quest);

            bool accepted = DynamicQuestRuntimeService.Instance.AcceptQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                "quest-world-offer",
                "world_region_entered");
            bool explored = DynamicQuestRuntimeService.Instance.RecordExploreProgressForTest("DummyQuest001", 1, 521000, 492000);
            bool killed = DynamicQuestRuntimeService.Instance.RecordKillProgressForTest("DummyQuest001", "forest spiderling", 1, 1);
            bool selected = DynamicQuestRuntimeService.Instance.SelectChoiceForTest("DummyQuest001", "quest-world-offer", "safe");

            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot(
                "DummyQuest001",
                "DummyQuest001",
                true,
                200);
            string[] beatDetails = timeline.Events
                .Where(evt => evt.EventType == "presentation_beat")
                .Select(evt => evt.Detail)
                .ToArray();
            string[] spotlightDetails = timeline.Events
                .Where(evt => evt.EventType == "presentation_spotlight")
                .Select(evt => evt.Detail)
                .ToArray();

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(explored, Is.True);
                Assert.That(killed, Is.True);
                Assert.That(selected, Is.True);
                Assert.That(beatDetails.Any(detail => detail.Contains("OnAccept") && detail.Contains("낡은 지도")), Is.True);
                Assert.That(beatDetails.Any(detail => detail.Contains("OnChoiceSelected") && detail.Contains("선택의 여파")), Is.True);
                Assert.That(beatDetails.Any(detail => detail.Contains("OnComplete") && detail.Contains("마지막 빛")), Is.True);
                Assert.That(spotlightDetails.Any(detail => detail.Contains("OnChoiceSelected") && detail.Contains("선택의 여파")), Is.True);
                Assert.That(spotlightDetails.Any(detail => detail.Contains("OnComplete") && detail.Contains("마지막 빛")), Is.True);
            });
        }

        [Test]
        public void TimelineSnapshot_ExposesPresentationBeatsAsReadOnlyObservation()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnAccept\",\"speaker\":\"System\",\"text\":\"낡은 지도 위로 숲의 균열이 희미하게 떠오른다.\",\"emotion\":\"hope\",\"emote\":\"Cheer\",\"cinematicAction\":\"guard_advance\",\"sceneRole\":\"escort_screen\",\"formation\":\"line\",\"actorCount\":6,\"delayMs\":900}" +
                "]";
            DynamicQuestRuntimeService.Instance.AddQuest(quest);

            bool accepted = DynamicQuestRuntimeService.Instance.AcceptQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                "quest-world-offer",
                "world_region_entered");
            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot(
                "DummyQuest001",
                "DummyQuest001",
                true,
                50);

            System.Reflection.PropertyInfo property = typeof(DynamicQuestTimelineSnapshot).GetProperty("PresentationBeats");
            Assert.That(property, Is.Not.Null);
            object value = property.GetValue(timeline);
            Assert.That(value, Is.InstanceOf<System.Collections.IEnumerable>());
            object beat = ((System.Collections.IEnumerable)value).Cast<object>().Single();

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(beat.GetType().GetProperty("QuestId")?.GetValue(beat), Is.EqualTo("quest-world-offer"));
                Assert.That(beat.GetType().GetProperty("NodeId")?.GetValue(beat), Is.EqualTo("explore"));
                Assert.That(beat.GetType().GetProperty("Trigger")?.GetValue(beat), Is.EqualTo("OnAccept"));
                Assert.That(beat.GetType().GetProperty("Speaker")?.GetValue(beat), Is.EqualTo("System"));
                Assert.That(beat.GetType().GetProperty("Emotion")?.GetValue(beat), Is.EqualTo("hope"));
                Assert.That(beat.GetType().GetProperty("Emote")?.GetValue(beat), Is.EqualTo("Cheer"));
                Assert.That(beat.GetType().GetProperty("Text")?.GetValue(beat)?.ToString(), Does.Contain("낡은 지도"));
                Assert.That(beat.GetType().GetProperty("CinematicAction")?.GetValue(beat), Is.EqualTo("guard_advance"));
                Assert.That(beat.GetType().GetProperty("SceneRole")?.GetValue(beat), Is.EqualTo("escort_screen"));
                Assert.That(beat.GetType().GetProperty("Formation")?.GetValue(beat), Is.EqualTo("line"));
                Assert.That(beat.GetType().GetProperty("ActorCount")?.GetValue(beat), Is.EqualTo(6));
                Assert.That(beat.GetType().GetProperty("DelayMs")?.GetValue(beat), Is.EqualTo(900));
            });
        }

        [Test]
        public void TimelineSnapshot_RecordsDefaultPresentationBeatsWhenStoryPresentationIsMissing()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.StoryPresentationJson = string.Empty;
            DynamicQuestNode exploreNode = quest.Nodes.Single(node => node.Id == "explore");
            DynamicQuestNode killNode = quest.Nodes.Single(node => node.Id == "kill");
            IList<string> explorePlan = DynamicQuestRuntimeService.BuildCinematicActionDetailsForTest(quest, exploreNode, "OnExplore");
            IList<string> killPlan = DynamicQuestRuntimeService.BuildCinematicActionDetailsForTest(quest, killNode, "OnKill");
            DynamicQuestRuntimeService.Instance.AddQuest(quest);

            bool accepted = DynamicQuestRuntimeService.Instance.AcceptQuestForTest(
                "DummyQuest001",
                "DummyQuest001",
                "quest-world-offer",
                "world_region_entered");
            bool explored = DynamicQuestRuntimeService.Instance.RecordExploreProgressForTest(
                "DummyQuest001",
                1,
                521000,
                492000);
            bool killed = DynamicQuestRuntimeService.Instance.RecordKillProgressForTest(
                "DummyQuest001",
                "forest spiderling",
                1,
                1);

            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot(
                "DummyQuest001",
                "DummyQuest001",
                true,
                50);
            string[] triggers = timeline.PresentationBeats.Select(beat => beat.Trigger).ToArray();
            string[] cinematicDetails = timeline.Events
                .Where(evt => evt.EventType == "cinematic_action")
                .Select(evt => evt.Detail)
                .ToArray();

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(explored, Is.True);
                Assert.That(killed, Is.True);
                Assert.That(triggers, Does.Contain("OnAccept"));
                Assert.That(triggers, Does.Contain("OnExplore"));
                Assert.That(triggers, Does.Contain("OnKill"));
                Assert.That(triggers, Does.Contain("OnComplete"));
                Assert.That(cinematicDetails.Any(detail =>
                    detail.Contains("scene_beat:OnExplore:explore", StringComparison.Ordinal) &&
                    detail.Contains("action:witness_point", StringComparison.Ordinal)), Is.True);
                Assert.That(explorePlan.Any(detail =>
                    detail.Contains("scene_beat:OnExplore:explore", StringComparison.Ordinal) &&
                    detail.Contains("action:witness_point", StringComparison.Ordinal) &&
                    detail.Contains("actors:1", StringComparison.Ordinal)), Is.True);
                Assert.That(killPlan.Any(detail =>
                    detail.Contains("scene_beat:OnKill:kill", StringComparison.Ordinal) &&
                    detail.Contains("action:ambush_reveal", StringComparison.Ordinal) &&
                    detail.Contains("actors:5", StringComparison.Ordinal)), Is.True);
            });
        }

        [Test]
        public void TimelineSnapshot_RecordsDefaultPresentationBeatWhenWorldSignalIsConsumed()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(WorldSignalGraphQuest());
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-signal",
                "wait_for_signal",
                Array.Empty<string>(),
                new System.Collections.Generic.Dictionary<string, int>());

            bool advanced = DynamicQuestRuntimeService.Instance.RecordWorldSignalForTest(
                "DummyQuest001",
                "DummyQuest001",
                "region-entered:1");

            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot(
                "DummyQuest001",
                "DummyQuest001",
                true,
                50);

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.True);
                Assert.That(timeline.PresentationBeats.Any(beat =>
                    beat.NodeId == "wait_for_signal" &&
                    beat.Trigger == "OnWorldSignal"), Is.True);
            });
        }

        [Test]
        public void BuildNarrativeSceneMessageForTest_FormatsSceneForInGamePresentation()
        {
            DynamicQuestNarrativeScene scene = new()
            {
                Title = "##수도원 길목의 경고",
                Body = "##Brother Penric은 찢긴 짐가방을 내려놓고, 길목의 침묵이 너무 오래 이어졌다고 말합니다.",
                JournalEntry = "##수도원 길목의 찢긴 짐가방을 조사한다.",
                Mood = "urgent"
            };

            string message = DynamicQuestRuntimeService.BuildNarrativeSceneMessageForTest(scene);
            string title = DynamicQuestRuntimeService.BuildNarrativeSceneTitleMessageForTest(scene);
            string journal = DynamicQuestRuntimeService.BuildNarrativeSceneJournalMessageForTest(scene);

            Assert.Multiple(() =>
            {
                Assert.That(message, Does.Contain("수도원 길목의 경고"));
                Assert.That(message, Does.Contain("찢긴 짐가방"));
                Assert.That(message, Does.Contain("분위기: urgent"));
                Assert.That(title, Is.EqualTo("[동적 퀘스트] 수도원 길목의 경고"));
                Assert.That(journal, Is.EqualTo("저널 갱신: 수도원 길목의 찢긴 짐가방을 조사한다."));
                Assert.That(message, Does.Not.Contain("##"));
            });
        }

        [Test]
        public void PresentationSpotlightForTest_HighlightsMajorStoryBeats()
        {
            DynamicQuestPresentationBeat choice = new()
            {
                Trigger = "OnChoiceSelected",
                Text = "##좋습니다. 선택한 이유까지 기록하겠습니다. 언젠가 누군가 이 밤을 다시 읽게 될 테니까요.",
                Emotion = "pride"
            };
            DynamicQuestPresentationBeat explore = new()
            {
                Trigger = "OnExplore",
                Text = "흔적이 선명해집니다.",
                Emotion = "suspicion"
            };

            Assert.Multiple(() =>
            {
                Assert.That(DynamicQuestRuntimeService.ShouldSpotlightPresentationBeatForTest(choice), Is.True);
                Assert.That(DynamicQuestRuntimeService.BuildPresentationSpotlightMessageForTest(choice), Does.Contain("선택한 이유까지"));
                Assert.That(DynamicQuestRuntimeService.BuildPresentationSpotlightMessageForTest(choice), Does.Not.Contain("##"));
                Assert.That(DynamicQuestRuntimeService.ShouldSpotlightPresentationBeatForTest(explore), Is.False);
            });
        }

        [Test]
        public void TryResolvePresentationEmoteForTest_UsesExplicitEmoteBeforeEmotionFallback()
        {
            bool explicitResolved = DynamicQuestRuntimeService.TryResolvePresentationEmoteForTest(
                new DynamicQuestPresentationBeat { Emotion = "fear", Emote = "Bow" },
                out eEmote explicitEmote);
            bool fallbackResolved = DynamicQuestRuntimeService.TryResolvePresentationEmoteForTest(
                new DynamicQuestPresentationBeat { Emotion = "fear", Emote = "" },
                out eEmote fallbackEmote);
            bool unknownResolved = DynamicQuestRuntimeService.TryResolvePresentationEmoteForTest(
                new DynamicQuestPresentationBeat { Emotion = "unmapped", Emote = "" },
                out _);

            Assert.Multiple(() =>
            {
                Assert.That(explicitResolved, Is.True);
                Assert.That(explicitEmote, Is.EqualTo(eEmote.Bow));
                Assert.That(fallbackResolved, Is.True);
                Assert.That(fallbackEmote, Is.EqualTo(eEmote.Shiver));
                Assert.That(unknownResolved, Is.False);
            });
        }

        [Test]
        public void CinematicActionPlanForTest_UsesMarkersNpcFocusAndCleanupForStoryNodes()
        {
            DynamicQuestDefinition quest = ExploreGraphQuest();
            DynamicQuestNode talk = quest.Nodes.Single(node => node.Id == "talk");
            DynamicQuestNode explore = quest.Nodes.Single(node => node.Id == "explore");
            DynamicQuestNode kill = quest.Nodes.Single(node => node.Id == "kill");
            DynamicQuestNode choice = quest.Nodes.Single(node => node.Id == "choice");
            DynamicQuestNode complete = quest.Nodes.Single(node => node.Id == "complete");

            IList<string> talkActions = DynamicQuestRuntimeService.BuildCinematicActionDetailsForTest(quest, talk);
            IList<string> exploreActions = DynamicQuestRuntimeService.BuildCinematicActionDetailsForTest(quest, explore, "OnExplore");
            IList<string> killActions = DynamicQuestRuntimeService.BuildCinematicActionDetailsForTest(quest, kill, "OnKill");
            IList<string> choiceActions = DynamicQuestRuntimeService.BuildCinematicActionDetailsForTest(quest, choice, "OnChoiceSelected");
            IList<string> completeActions = DynamicQuestRuntimeService.BuildCinematicActionDetailsForTest(quest, complete, "OnComplete");
            ushort exploreModel = DynamicQuestRuntimeService.ResolveCinematicMarkerModelForTest(quest, explore, "OnExplore", "explore trace evidence");
            ushort killModel = DynamicQuestRuntimeService.ResolveCinematicMarkerModelForTest(quest, kill, "OnKill", "threat battle sign");
            ushort killNpcModel = DynamicQuestRuntimeService.ResolveCinematicNpcModelForTest(quest, kill, "OnKill", "combat_stance OnKill kill");
            ushort talkNpcModel = DynamicQuestRuntimeService.ResolveCinematicNpcModelForTest(quest, talk, "OnNodeEnter", "challenge OnNodeEnter talk");
            ushort choiceNpcModel = DynamicQuestRuntimeService.ResolveCinematicNpcModelForTest(quest, choice, "OnChoiceSelected", "guard_advance OnChoiceSelected choice");
            string killNpcCategory = DynamicQuestCinematicCatalog.ResolveNpcCategoryForModel(killNpcModel);
            string talkNpcCategory = DynamicQuestCinematicCatalog.ResolveNpcCategoryForModel(talkNpcModel);
            string choiceNpcCategory = DynamicQuestCinematicCatalog.ResolveNpcCategoryForModel(choiceNpcModel);

            Assert.Multiple(() =>
            {
                Assert.That(talkActions, Does.Contain($"npc_action:OnNodeEnter:talk:challenge:LetsGo:model:{talkNpcModel}:catalogRole:{talkNpcCategory}:actors:1:motion:challenge:stagger:45:focal:player:actorRole:brace:choreo:2:interact:none:tactic:pressure"));
                Assert.That(exploreActions.Any(action =>
                    action.StartsWith("marker:OnExplore:explore:Quest trace:", StringComparison.Ordinal) &&
                    action.EndsWith($":model:{exploreModel}", StringComparison.Ordinal)), Is.True);
                Assert.That(killActions.Any(action =>
                    action.StartsWith("marker:OnKill:kill:Threat sign: black wolf pup", StringComparison.Ordinal) &&
                    action.EndsWith($":model:{killModel}", StringComparison.Ordinal)), Is.True);
                Assert.That(killActions, Does.Contain($"npc_action:OnKill:kill:combat_stance:PlayerPrepare:model:{killNpcModel}:catalogRole:{killNpcCategory}:actors:3:motion:brace:stagger:50:focal:player:actorRole:strike:choreo:3:interact:clash:tactic:flank"));
                Assert.That(choiceActions, Does.Contain($"npc_action:OnChoiceSelected:choice:guard_advance:Point:model:{choiceNpcModel}:catalogRole:{choiceNpcCategory}:actors:2:motion:advance:stagger:70:focal:player:actorRole:defend:choreo:3:interact:block:tactic:screen"));
                Assert.That(choiceActions.Any(action =>
                    action.StartsWith("marker:OnChoiceSelected:choice:Decision echo:", StringComparison.Ordinal)), Is.True);
                Assert.That(completeActions, Does.Contain("cleanup:OnComplete:complete"));
                Assert.That(completeActions, Does.Contain("npc_action:OnComplete:complete:focus:Bow"));
            });
        }

        [Test]
        public void ResolveCinematicNpcModelForTest_UsesSceneRoleIntentForCatalogVariety()
        {
            DynamicQuestDefinition quest = ExploreGraphQuest();
            quest.Title = "Witness route scout testimony";
            quest.OfferText = "A witness fled through a route watched by scouts.";
            quest.ProgressText = "Follow the witness route.";
            quest.FinishText = "The witness route is sealed.";
            DynamicQuestNode explore = quest.Nodes.Single(node => node.Id == "explore");
            DynamicQuestNode kill = quest.Nodes.Single(node => node.Id == "kill");
            DynamicQuestNode choice = quest.Nodes.Single(node => node.Id == "choice");

            string witnessCategory = DynamicQuestCinematicCatalog.ResolveNpcCategoryForModel(
                DynamicQuestRuntimeService.ResolveCinematicNpcModelForTest(quest, explore, "OnExplore", "broken_oath_witness witness_point escort"));
            string scoutCategory = DynamicQuestCinematicCatalog.ResolveNpcCategoryForModel(
                DynamicQuestRuntimeService.ResolveCinematicNpcModelForTest(quest, explore, "OnExplore", "oathbreaker_lookout scout_retreat patrol"));
            string fighterCategory = DynamicQuestCinematicCatalog.ResolveNpcCategoryForModel(
                DynamicQuestRuntimeService.ResolveCinematicNpcModelForTest(quest, kill, "OnKill", "traitor_signal_wave ambush_reveal ambush strike flank"));
            string defenderCategory = DynamicQuestCinematicCatalog.ResolveNpcCategoryForModel(
                DynamicQuestRuntimeService.ResolveCinematicNpcModelForTest(quest, choice, "OnChoiceSelected", "shield_oath_intercept defender_intercept shield line block"));

            Assert.Multiple(() =>
            {
                Assert.That(witnessCategory, Is.EqualTo("witness"));
                Assert.That(scoutCategory, Is.EqualTo("scout"));
                Assert.That(fighterCategory, Is.EqualTo("fighter"));
                Assert.That(defenderCategory, Is.EqualTo("defender"));
                Assert.That(new[] { witnessCategory, scoutCategory, fighterCategory, defenderCategory }.Distinct().Count(), Is.EqualTo(4));
            });
        }

        [Test]
        public void CinematicActorSpawnPointForTest_UsesObjectiveAnchorWhenProvided()
        {
            Point3D playerPosition = new(1000, 2000, 300);
            Point3D objectiveAnchor = new(5000, 7000, 450);

            Point3D spawnPoint = DynamicQuestRuntimeService.BuildCinematicActorSpawnPointForTest(
                objectiveAnchor,
                heading: 0,
                index: 0,
                actorCount: 3,
                formation: "line",
                npcAction: "defender_intercept");

            Assert.Multiple(() =>
            {
                Assert.That(spawnPoint.X, Is.EqualTo(4740));
                Assert.That(spawnPoint.Y, Is.EqualTo(6955));
                Assert.That(spawnPoint.Z, Is.EqualTo(450));
                Assert.That(Math.Abs(spawnPoint.X - playerPosition.X), Is.GreaterThan(3000));
                Assert.That(Math.Abs(spawnPoint.Y - playerPosition.Y), Is.GreaterThan(4000));
            });
        }

        [Test]
        public void CinematicActionTimelineDelayForTest_AppliesOnlyToSceneBeats()
        {
            Assert.Multiple(() =>
            {
                Assert.That(DynamicQuestRuntimeService.ResolveCinematicActionTimelineDelayMsForTest("scene_beat", 900), Is.EqualTo(900));
                Assert.That(DynamicQuestRuntimeService.ResolveCinematicActionTimelineDelayMsForTest("scene_beat", 9000), Is.EqualTo(6000));
                Assert.That(DynamicQuestRuntimeService.ResolveCinematicActionTimelineDelayMsForTest("scene_beat", 0), Is.EqualTo(0));
                Assert.That(DynamicQuestRuntimeService.ResolveCinematicActionTimelineDelayMsForTest("marker", 900), Is.EqualTo(0));
                Assert.That(DynamicQuestRuntimeService.ResolveCinematicActionTimelineDelayMsForTest("npc_action", 900), Is.EqualTo(0));
            });
        }

        [Test]
        public void CinematicActionPlanForTest_UsesStoryContextForPropsAndNpcActions()
        {
            DynamicQuestDefinition quest = ExploreGraphQuest();
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"speaker\":\"System\",\"text\":\"정찰병이 룬 토템 성물과 기록이 남은 흔적을 가리킵니다.\",\"emotion\":\"caution\",\"emote\":\"Point\"}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"speaker\":\"System\",\"text\":\"동료가 부러진 화살과 전투 흔적 앞에서 방어 자세를 잡습니다.\",\"emotion\":\"warning\",\"emote\":\"Point\"}," +
                "{\"nodeId\":\"return\",\"trigger\":\"OnNodeEnter\",\"speaker\":\"StartNpc\",\"text\":\"경비가 뒤로 물러나며 횃불 옆을 지킵니다.\",\"emotion\":\"relief\",\"emote\":\"Bow\"}" +
                "]";
            quest.StoryNarrativeJson = "[" +
                "{\"nodeId\":\"explore\",\"sceneType\":\"Discovery\",\"title\":\"룬 성물\",\"body\":\"룬 토템 성물 옆에 기록이 남아 있습니다.\",\"journalEntry\":\"룬 성물과 기록을 조사한다.\",\"mood\":\"ominous\",\"revealPolicy\":\"FirstSeenOnly\"}" +
                "]";

            DynamicQuestNode explore = quest.Nodes.Single(node => node.Id == "explore");
            DynamicQuestNode kill = quest.Nodes.Single(node => node.Id == "kill");
            DynamicQuestNode returnNode = quest.Nodes.Single(node => node.Id == "return");

            IList<string> exploreActions = DynamicQuestRuntimeService.BuildCinematicActionDetailsForTest(quest, explore, "OnExplore");
            IList<string> killActions = DynamicQuestRuntimeService.BuildCinematicActionDetailsForTest(quest, kill, "OnKill");
            IList<string> returnActions = DynamicQuestRuntimeService.BuildCinematicActionDetailsForTest(quest, returnNode, "OnNodeEnter");

            Assert.Multiple(() =>
            {
                Assert.That(exploreActions.Any(action =>
                    action.StartsWith("marker:OnExplore:explore:Written record:", StringComparison.Ordinal) ||
                    action.StartsWith("marker:OnExplore:explore:Relic sign:", StringComparison.Ordinal)), Is.True);
                Assert.That(exploreActions.Any(action => action.StartsWith("npc_action:OnExplore:explore:witness_point:Point:model:", StringComparison.Ordinal)), Is.True);
                Assert.That(killActions.Any(action => action.StartsWith("marker:OnKill:kill:Battle sign:", StringComparison.Ordinal)), Is.True);
                Assert.That(killActions.Any(action => action.StartsWith("npc_action:OnKill:kill:combat_stance:PlayerPrepare:model:", StringComparison.Ordinal)), Is.True);
                Assert.That(returnActions.Any(action => action.StartsWith("npc_action:OnNodeEnter:returntonpc:fallback_guard:BangOnShield:model:", StringComparison.Ordinal)), Is.True);
                Assert.That(returnActions.Any(action => action.StartsWith("marker:OnNodeEnter:returntonpc:Burning omen:", StringComparison.Ordinal)), Is.True);
            });
        }

        [Test]
        public void CinematicActionPlanForTest_PrefersScoutRetreatForLookoutEscapeRoute()
        {
            DynamicQuestDefinition quest = ExploreGraphQuest();
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"speaker\":\"System\",\"text\":\"목격자가 불씨를 가리키자 망보던 자가 탈출로로 후퇴합니다.\",\"emotion\":\"suspicion\",\"emote\":\"Point\"}" +
                "]";
            DynamicQuestNode explore = quest.Nodes.Single(node => node.Id == "explore");

            IList<string> exploreActions = DynamicQuestRuntimeService.BuildCinematicActionDetailsForTest(quest, explore, "OnExplore");

            Assert.That(exploreActions.Any(action =>
                action.StartsWith("npc_action:OnExplore:explore:scout_retreat:Point:model:", StringComparison.Ordinal) &&
                action.Contains(":actors:2:motion:retreat", StringComparison.Ordinal)), Is.True);
        }

        [Test]
        public void CinematicActionPlanForTest_BuildsStagedAssassinationWitnessAmbushEscapeBeats()
        {
            DynamicQuestDefinition quest = ExploreGraphQuest();
            quest.Tags = (quest.Tags ?? Array.Empty<string>())
                .Concat(new[]
                {
                    "realm:Albion",
                    "scene-director",
                    "dark-brotherhood",
                    "story-cinematic",
                    "story-archetype:witness-conspiracy",
                    "story-arc:motive",
                    "story-arc:conflict",
                    "story-arc:reversal",
                    "story-arc:consequence",
                    "cinematic-actors:scout_retreat:5",
                    "cinematic-actors:defender_intercept:6",
                    "cinematic-actors:ambush_reveal:8",
                    "cinematic-actors:ritual_interrupt:5"
                })
                .ToArray();
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"talk\",\"trigger\":\"OnNodeEnter\",\"speaker\":\"StartNpc\",\"text\":\"조용한 암살 계약입니다. 목표를 본 목격자는 반드시 움직일 겁니다.\",\"emotion\":\"caution\",\"emote\":\"No\"}," +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"speaker\":\"System\",\"text\":\"목격자가 골목 끝에서 단서를 가리키고, 망보던 자가 탈출로로 물러납니다.\",\"emotion\":\"suspicion\",\"emote\":\"Point\"}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"speaker\":\"System\",\"text\":\"암살 순간 매복 병력이 모습을 드러내고, 경비가 탈출 경로를 가로막습니다.\",\"emotion\":\"urgency\",\"emote\":\"LetsGo\"}," +
                "{\"nodeId\":\"choice\",\"trigger\":\"OnChoiceShown\",\"speaker\":\"StartNpc\",\"text\":\"목격자를 살려 보낼지, 진실을 덮을지 선택해야 합니다.\",\"emotion\":\"suspicion\",\"emote\":\"Ponder\"}" +
                "]";

            DynamicQuestCinematicPlanSnapshot snapshot = DynamicQuestRuntimeService.BuildCinematicPlanSnapshotForTest(quest);
            DynamicQuestCinematicPlanItem contract = snapshot.Actions.Single(item =>
                item.NodeId == "talk" &&
                item.Trigger == "OnNodeEnter" &&
                item.Kind == "scene_beat" &&
                item.SceneRole == "contract");
            DynamicQuestCinematicPlanItem witness = snapshot.Actions.Single(item =>
                item.NodeId == "explore" &&
                item.Trigger == "OnExplore" &&
                item.Kind == "scene_beat" &&
                item.SceneRole == "witness");
            DynamicQuestCinematicPlanItem lookout = snapshot.Actions.Single(item =>
                item.NodeId == "explore" &&
                item.Trigger == "OnExplore" &&
                item.Kind == "scene_beat" &&
                item.SceneRole == "lookout");
            DynamicQuestCinematicPlanItem ambush = snapshot.Actions.Single(item =>
                item.NodeId == "kill" &&
                item.Trigger == "OnKill" &&
                item.Kind == "scene_beat" &&
                item.SceneRole == "ambush");
            DynamicQuestCinematicPlanItem escape = snapshot.Actions.Single(item =>
                item.NodeId == "kill" &&
                item.Trigger == "OnKill" &&
                item.Kind == "scene_beat" &&
                item.SceneRole == "witness_escape");
            DynamicQuestCinematicPlanItem counterline = snapshot.Actions.Single(item =>
                item.NodeId == "kill" &&
                item.Trigger == "OnKill" &&
                item.Kind == "scene_beat" &&
                item.SceneRole == "counterline");
            DynamicQuestCinematicPlanItem shieldHold = snapshot.Actions.Single(item =>
                item.NodeId == "kill" &&
                item.Trigger == "OnKill" &&
                item.Kind == "scene_beat" &&
                item.SceneRole == "shield_hold");
            DynamicQuestCinematicPlanItem confrontation = snapshot.Actions.Single(item =>
                item.NodeId == "choice" &&
                item.Trigger == "OnChoiceShown" &&
                item.Kind == "scene_beat" &&
                item.SceneRole == "confrontation");
            DynamicQuestCinematicPlanItem choiceScreen = snapshot.Actions.Single(item =>
                item.NodeId == "choice" &&
                item.Trigger == "OnChoiceShown" &&
                item.Kind == "scene_beat" &&
                item.SceneRole == "choice_screen");
            DynamicQuestCinematicPlanItem choiceFallback = snapshot.Actions.Single(item =>
                item.NodeId == "choice" &&
                item.Trigger == "OnChoiceShown" &&
                item.Kind == "scene_beat" &&
                item.SceneRole == "choice_fallback");

            Assert.Multiple(() =>
            {
                Assert.That(contract.NpcAction, Is.EqualTo("witness_point"));
                Assert.That(contract.SceneBeatIndex, Is.EqualTo(1));
                Assert.That(contract.Formation, Is.EqualTo("escort"));
                Assert.That(witness.NpcAction, Is.EqualTo("witness_point"));
                Assert.That(witness.FocalPoint, Is.EqualTo("objective"));
                Assert.That(witness.ActorRole, Is.EqualTo("spot"));
                Assert.That(witness.ChoreographyPhases, Is.EqualTo(2));
                Assert.That(witness.InteractionStyle, Is.EqualTo("none"));
                Assert.That(witness.TacticalRole, Is.EqualTo("spot"));
                Assert.That(lookout.NpcAction, Is.EqualTo("scout_retreat"));
                Assert.That(lookout.ActorRole, Is.EqualTo("retreat"));
                Assert.That(lookout.InteractionStyle, Is.EqualTo("pursuit"));
                Assert.That(lookout.TacticalRole, Is.EqualTo("withdraw"));
                Assert.That(lookout.SceneDelayMs, Is.EqualTo(900));
                Assert.That(ambush.NpcAction, Is.EqualTo("ambush_reveal"));
                Assert.That(ambush.Formation, Is.EqualTo("ambush"));
                Assert.That(ambush.MotionPattern, Is.EqualTo("pincer"));
                Assert.That(ambush.ActorRole, Is.EqualTo("strike"));
                Assert.That(ambush.InteractionStyle, Is.EqualTo("clash"));
                Assert.That(ambush.TacticalRole, Is.EqualTo("flank"));
                Assert.That(ambush.MotionLateral, Is.GreaterThanOrEqualTo(120));
                Assert.That(ambush.MotionStaggerMs, Is.GreaterThanOrEqualTo(90));
                Assert.That(ambush.ActorCount, Is.GreaterThanOrEqualTo(5));
                Assert.That(escape.NpcAction, Is.EqualTo("scout_retreat"));
                Assert.That(escape.Formation, Is.EqualTo("escape"));
                Assert.That(escape.MotionPattern, Is.EqualTo("retreat"));
                Assert.That(escape.MotionDistance, Is.LessThanOrEqualTo(-150));
                Assert.That(escape.MotionStaggerMs, Is.GreaterThanOrEqualTo(100));
                Assert.That(escape.SceneDelayMs, Is.EqualTo(1700));
                Assert.That(counterline.NpcAction, Is.EqualTo("combat_stance"));
                Assert.That(counterline.SceneBeatIndex, Is.EqualTo(5));
                Assert.That(counterline.ActorCount, Is.GreaterThanOrEqualTo(6));
                Assert.That(counterline.InteractionStyle, Is.EqualTo("clash"));
                Assert.That(counterline.TacticalRole, Is.EqualTo("flank"));
                Assert.That(shieldHold.NpcAction, Is.EqualTo("hold_ground"));
                Assert.That(shieldHold.SceneBeatIndex, Is.EqualTo(6));
                Assert.That(shieldHold.ActorCount, Is.GreaterThanOrEqualTo(5));
                Assert.That(shieldHold.InteractionStyle, Is.EqualTo("block"));
                Assert.That(shieldHold.TacticalRole, Is.EqualTo("screen"));
                Assert.That(confrontation.NpcAction, Is.EqualTo("threat_standoff"));
                Assert.That(confrontation.MotionPattern, Is.EqualTo("standoff"));
                Assert.That(confrontation.InteractionStyle, Is.EqualTo("standoff"));
                Assert.That(confrontation.TacticalRole, Is.EqualTo("pressure"));
                Assert.That(confrontation.MotionStaggerMs, Is.GreaterThanOrEqualTo(80));
                Assert.That(choiceScreen.NpcAction, Is.EqualTo("defender_intercept"));
                Assert.That(choiceScreen.InteractionStyle, Is.EqualTo("block"));
                Assert.That(choiceFallback.NpcAction, Is.EqualTo("fallback_guard"));
                Assert.That(choiceFallback.MotionPattern, Is.EqualTo("fall-back"));
                Assert.That(snapshot.TotalActorCount, Is.GreaterThanOrEqualTo(40));
                Assert.That(snapshot.Actions.Any(item => item.Detail.Contains("scene_beat:OnKill:kill:beat:1", StringComparison.Ordinal)), Is.True);
            });
        }

        [Test]
        public void CinematicActionPlanForTest_AddsRitualInterruptSetPieceWhenStorySignalsRitual()
        {
            DynamicQuestDefinition quest = ExploreGraphQuest();
            quest.Tags = (quest.Tags ?? Array.Empty<string>())
                .Concat(new[] { "scene-director", "story-cinematic", "cinematic-actors:ritual_interrupt:5" })
                .ToArray();
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"speaker\":\"System\",\"text\":\"성물 옆 의식 표식이 흔들리자 경비들이 전열을 세우고 의식을 끊으려 다가갑니다.\",\"emotion\":\"urgency\",\"emote\":\"Point\"}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"speaker\":\"System\",\"text\":\"목표가 쓰러지자 남은 의식이 깨지고 경비가 성물 앞을 막아섭니다.\",\"emotion\":\"urgency\",\"emote\":\"Point\"}" +
                "]";

            DynamicQuestCinematicPlanSnapshot snapshot = DynamicQuestRuntimeService.BuildCinematicPlanSnapshotForTest(quest);
            DynamicQuestCinematicPlanItem exploreRitual = snapshot.Actions.Single(item =>
                item.NodeId == "explore" &&
                item.Trigger == "OnExplore" &&
                item.Kind == "scene_beat" &&
                item.SceneRole == "ritual");
            DynamicQuestCinematicPlanItem killRitual = snapshot.Actions.Single(item =>
                item.NodeId == "kill" &&
                item.Trigger == "OnKill" &&
                item.Kind == "scene_beat" &&
                item.SceneRole == "ritual_break");

            Assert.Multiple(() =>
            {
                Assert.That(exploreRitual.NpcAction, Is.EqualTo("ritual_interrupt"));
                Assert.That(exploreRitual.SceneBeatIndex, Is.EqualTo(3));
                Assert.That(exploreRitual.SceneDelayMs, Is.EqualTo(1500));
                Assert.That(exploreRitual.ActorCount, Is.GreaterThanOrEqualTo(5));
                Assert.That(killRitual.NpcAction, Is.EqualTo("ritual_interrupt"));
                Assert.That(killRitual.SceneBeatIndex, Is.EqualTo(4));
                Assert.That(killRitual.SceneDelayMs, Is.EqualTo(2400));
                Assert.That(killRitual.ActorCount, Is.GreaterThanOrEqualTo(5));
            });
        }

        [Test]
        public void CinematicActionPlanForTest_UsesExplicitPresentationSetPieceFields()
        {
            Properties.KDAOC_DYNAMIC_QUEST_CINEMATIC_MAX_ACTORS_PER_ACTION = 100;
            DynamicQuestDefinition quest = ExploreGraphQuest();
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"speaker\":\"System\",\"text\":\"지정된 매복대가 목표 주변에서 동시에 모습을 드러냅니다.\",\"emotion\":\"urgency\",\"emote\":\"LetsGo\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"ambush_wave\",\"formation\":\"ambush\",\"actorCount\":12,\"delayMs\":1200}" +
                "]";

            DynamicQuestCinematicPlanSnapshot snapshot = DynamicQuestRuntimeService.BuildCinematicPlanSnapshotForTest(quest);
            DynamicQuestCinematicPlanItem explicitAmbush = snapshot.Actions.Single(item =>
                item.NodeId == "kill" &&
                item.Trigger == "OnKill" &&
                item.Kind == "scene_beat" &&
                item.SceneRole == "ambush_wave");

            Assert.Multiple(() =>
            {
                Assert.That(explicitAmbush.NpcAction, Is.EqualTo("ambush_reveal"));
                Assert.That(explicitAmbush.Formation, Is.EqualTo("ambush"));
                Assert.That(explicitAmbush.ActorCount, Is.EqualTo(12));
                Assert.That(explicitAmbush.SceneDelayMs, Is.EqualTo(1200));
                Assert.That(explicitAmbush.Detail, Does.Contain("role:ambush_wave"));
                Assert.That(explicitAmbush.Detail, Does.Contain("actors:12"));
            });
        }

        [Test]
        public void CinematicActionPlanForTest_PreservesExplicitPresentationHundredActorCount()
        {
            Properties.KDAOC_DYNAMIC_QUEST_CINEMATIC_MAX_ACTORS_PER_ACTION = 100;
            DynamicQuestDefinition quest = ExploreGraphQuest();
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"speaker\":\"System\",\"text\":\"전열 전체가 목표 주변을 포위합니다.\",\"emotion\":\"urgency\",\"emote\":\"LetsGo\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"mass_ambush_wave\",\"formation\":\"ambush\",\"actorCount\":100,\"delayMs\":1200}" +
                "]";

            DynamicQuestCinematicPlanSnapshot snapshot = DynamicQuestRuntimeService.BuildCinematicPlanSnapshotForTest(quest);
            DynamicQuestCinematicPlanItem explicitAmbush = snapshot.Actions.Single(item =>
                item.NodeId == "kill" &&
                item.Trigger == "OnKill" &&
                item.Kind == "scene_beat" &&
                item.SceneRole == "mass_ambush_wave");

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.MaxActorsPerAction, Is.EqualTo(100));
                Assert.That(explicitAmbush.ActorCount, Is.EqualTo(100));
                Assert.That(explicitAmbush.Detail, Does.Contain("actors:100"));
                Assert.That(snapshot.TotalActorCount, Is.GreaterThanOrEqualTo(100));
            });
        }

        [Test]
        public void CinematicActionPlanForTest_DoesNotApplyHundredActorTagsToSupplementalNpcActions()
        {
            Properties.KDAOC_DYNAMIC_QUEST_CINEMATIC_MAX_ACTORS_PER_ACTION = 100;
            DynamicQuestDefinition quest = ExploreGraphQuest();
            quest.Tags = quest.Tags
                .Concat(new[] { "cinematic-actors:ambush_reveal:100", "mass-cinematic" })
                .ToArray();
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"speaker\":\"System\",\"text\":\"전열 전체가 목표 주변을 포위합니다.\",\"emotion\":\"urgency\",\"emote\":\"LetsGo\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"mass_ambush_wave\",\"formation\":\"ambush\",\"actorCount\":100,\"delayMs\":1200}" +
                "]";

            DynamicQuestCinematicPlanSnapshot snapshot = DynamicQuestRuntimeService.BuildCinematicPlanSnapshotForTest(quest);
            DynamicQuestCinematicPlanItem explicitAmbush = snapshot.Actions.Single(item =>
                item.NodeId == "kill" &&
                item.Trigger == "OnKill" &&
                item.Kind == "scene_beat" &&
                item.SceneRole == "mass_ambush_wave");
            DynamicQuestCinematicPlanItem supplementalAmbush = snapshot.Actions.First(item =>
                item.NodeId == "kill" &&
                item.Trigger == "OnKill" &&
                item.Kind == "npc_action" &&
                item.NpcAction == "ambush_reveal");

            Assert.Multiple(() =>
            {
                Assert.That(explicitAmbush.ActorCount, Is.EqualTo(100));
                Assert.That(supplementalAmbush.ActorCount, Is.LessThan(100));
                Assert.That(supplementalAmbush.Detail, Does.Not.Contain("actors:100"));
            });
        }

        [Test]
        public void CinematicActionPlanForTest_SceneDirectorDoesNotDuplicateExplicitSetPieceActions()
        {
            Properties.KDAOC_DYNAMIC_QUEST_CINEMATIC_MAX_ACTORS_PER_ACTION = 100;
            DynamicQuestDefinition quest = ExploreGraphQuest();
            quest.Tags = quest.Tags
                .Concat(new[] { "scene-director", "cinematic-actors:ambush_reveal:100", "mass-cinematic" })
                .ToArray();
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"speaker\":\"System\",\"text\":\"전열 전체가 목표 주변을 포위합니다.\",\"emotion\":\"urgency\",\"emote\":\"LetsGo\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"mass_ambush_wave\",\"formation\":\"ambush\",\"actorCount\":100,\"delayMs\":1200}" +
                "]";

            DynamicQuestCinematicPlanSnapshot snapshot = DynamicQuestRuntimeService.BuildCinematicPlanSnapshotForTest(quest);
            IList<DynamicQuestCinematicPlanItem> ambushes = snapshot.Actions
                .Where(item => item.NodeId == "kill" && item.Kind == "scene_beat" && item.NpcAction == "ambush_reveal")
                .ToArray();

            Assert.Multiple(() =>
            {
                Assert.That(ambushes, Has.Count.EqualTo(1));
                Assert.That(ambushes.Single().SceneRole, Is.EqualTo("mass_ambush_wave"));
                Assert.That(ambushes.Single().ActorCount, Is.EqualTo(100));
            });
        }

        [Test]
        public void CinematicActionPlanForTest_DefersNodeEnterSceneDirectorWhenExplicitEventSetPieceExists()
        {
            Properties.KDAOC_DYNAMIC_QUEST_CINEMATIC_MAX_ACTORS_PER_ACTION = 100;
            DynamicQuestDefinition quest = ExploreGraphQuest();
            quest.Tags = quest.Tags
                .Concat(new[] { "scene-director", "story-cinematic" })
                .ToArray();
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"speaker\":\"System\",\"text\":\"목표가 쓰러지는 순간 매복대가 모습을 드러냅니다.\",\"emotion\":\"urgency\",\"emote\":\"LetsGo\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"ambush_wave\",\"formation\":\"ambush\",\"actorCount\":12,\"delayMs\":1200}" +
                "]";

            DynamicQuestCinematicPlanSnapshot snapshot = DynamicQuestRuntimeService.BuildCinematicPlanSnapshotForTest(quest);
            IList<DynamicQuestCinematicPlanItem> nodeEnterSceneBeats = snapshot.Actions
                .Where(item => item.NodeId == "kill" && item.Trigger == "OnNodeEnter" && item.Kind == "scene_beat")
                .ToArray();
            IList<DynamicQuestCinematicPlanItem> killSceneBeats = snapshot.Actions
                .Where(item => item.NodeId == "kill" && item.Trigger == "OnKill" && item.Kind == "scene_beat")
                .ToArray();

            Assert.Multiple(() =>
            {
                Assert.That(nodeEnterSceneBeats, Is.Empty);
                Assert.That(killSceneBeats, Is.Not.Empty);
                Assert.That(killSceneBeats.Any(item => item.NpcAction == "ambush_reveal"), Is.True);
            });
        }

        [Test]
        public void CinematicFollowUpActionDelaysForTest_ExpandsChoreographyIntoBoundedPhases()
        {
            IList<int> noFollowUp = DynamicQuestRuntimeService.BuildCinematicFollowUpActionDelaysForTest(1, 0);
            IList<int> threePhaseActor = DynamicQuestRuntimeService.BuildCinematicFollowUpActionDelaysForTest(3, 2);
            IList<int> oversizedActor = DynamicQuestRuntimeService.BuildCinematicFollowUpActionDelaysForTest(100, 99);

            Assert.Multiple(() =>
            {
                Assert.That(noFollowUp, Is.Empty);
                Assert.That(threePhaseActor, Is.EqualTo(new[] { 886, 1586 }));
                Assert.That(oversizedActor, Is.EqualTo(new[] { 2632, 3200, 3200 }));
            });
        }

        [Test]
        public void CinematicMotionCommandCountForTest_TracksInitialAndFollowUpMovement()
        {
            int staticFocus = DynamicQuestRuntimeService.ResolveCinematicMotionCommandCountForTest(
                "",
                "",
                "",
                1);
            int ambushThreePhase = DynamicQuestRuntimeService.ResolveCinematicMotionCommandCountForTest(
                "ambush_reveal",
                "ambush",
                "mass_ambush_wave",
                3);
            int retreatFourPhase = DynamicQuestRuntimeService.ResolveCinematicMotionCommandCountForTest(
                "scout_retreat",
                "escape",
                "lookout_escape",
                4);

            Assert.Multiple(() =>
            {
                Assert.That(staticFocus, Is.EqualTo(0));
                Assert.That(ambushThreePhase, Is.EqualTo(3));
                Assert.That(retreatFourPhase, Is.EqualTo(4));
            });
        }

        [Test]
        public void CinematicEngagementPairCountForTest_TracksTacticalActorPairs()
        {
            int staticFocus = DynamicQuestRuntimeService.ResolveCinematicEngagementPairCountForTest(
                "",
                "",
                "",
                1);
            int ambushPairs = DynamicQuestRuntimeService.ResolveCinematicEngagementPairCountForTest(
                "ambush_reveal",
                "ambush",
                "mass_ambush_wave",
                100);
            int pursuitPairs = DynamicQuestRuntimeService.ResolveCinematicEngagementPairCountForTest(
                "scout_retreat",
                "escape",
                "lookout_escape",
                5);

            Assert.Multiple(() =>
            {
                Assert.That(staticFocus, Is.EqualTo(0));
                Assert.That(ambushPairs, Is.EqualTo(50));
                Assert.That(pursuitPairs, Is.EqualTo(2));
            });
        }

        [Test]
        public void TimelineSnapshot_RecordsSceneDirectorBeatOutcomes()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.Tags = (quest.Tags ?? Array.Empty<string>())
                .Concat(new[]
                {
                    "scene-director",
                    "dark-brotherhood",
                    "story-cinematic",
                    "story-archetype:witness-conspiracy",
                    "story-arc:motive",
                    "story-arc:conflict",
                    "story-arc:reversal",
                    "story-arc:consequence"
                })
                .ToArray();
            quest.StoryNarrativeJson = "[" +
                "{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"계약의 그림자\"}," +
                "{\"nodeId\":\"explore\",\"sceneType\":\"Discovery\",\"title\":\"목격자의 단서\"}," +
                "{\"nodeId\":\"explore\",\"sceneType\":\"Threat\",\"title\":\"탈출로의 망꾼\"}," +
                "{\"nodeId\":\"choice\",\"sceneType\":\"Choice\",\"title\":\"증언과 침묵\"}," +
                "{\"nodeId\":\"complete\",\"sceneType\":\"Completion\",\"title\":\"남은 흔적\"}" +
                "]";
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnAccept\",\"speaker\":\"System\",\"text\":\"계약의 그림자가 숲 가장자리에 모입니다.\",\"emotion\":\"suspicion\",\"emote\":\"Point\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"contract_witness\",\"formation\":\"ring\",\"actorCount\":8,\"delayMs\":100}," +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"speaker\":\"System\",\"text\":\"목격자가 단서를 가리킵니다.\",\"emotion\":\"suspicion\",\"emote\":\"Point\",\"cinematicAction\":\"witness_point\",\"sceneRole\":\"witness\",\"formation\":\"wedge\",\"actorCount\":4,\"delayMs\":150}," +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"speaker\":\"System\",\"text\":\"망보던 자가 탈출로로 물러납니다.\",\"emotion\":\"alarm\",\"emote\":\"Point\",\"cinematicAction\":\"scout_retreat\",\"sceneRole\":\"lookout\",\"formation\":\"patrol\",\"actorCount\":5,\"delayMs\":250}," +
                "{\"nodeId\":\"complete\",\"trigger\":\"OnComplete\",\"speaker\":\"System\",\"text\":\"남은 그림자들이 길목을 지키며 흔적을 정리합니다.\",\"emotion\":\"resolve\",\"emote\":\"Salute\",\"cinematicAction\":\"hold_ground\",\"sceneRole\":\"aftermath_guard\",\"formation\":\"line\",\"actorCount\":6,\"delayMs\":300}" +
                "]";
            DynamicQuestResult addResult = DynamicQuestRuntimeService.Instance.AddQuest(quest);
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-world-offer",
                "explore",
                Array.Empty<string>(),
                new Dictionary<string, int>());

            bool explored = DynamicQuestRuntimeService.Instance.RecordExploreProgressForTest(
                "DummyQuest001",
                1,
                521000,
                492000);

            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot(
                "DummyQuest001",
                "DummyQuest001",
                true,
                200);

            Assert.Multiple(() =>
            {
                Assert.That(addResult.Success, Is.True, addResult.Message);
                Assert.That(explored, Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "cinematic_action" &&
                    evt.NodeId == "explore" &&
                    evt.Detail.Contains("scene_beat:OnExplore:explore", StringComparison.Ordinal)), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "scene_beat_outcome" &&
                    evt.NodeId == "explore" &&
                    evt.Detail.Contains("role:witness", StringComparison.Ordinal) &&
                    evt.Detail.Contains("action:witness_point", StringComparison.Ordinal)), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "scene_beat_outcome" &&
                    evt.NodeId == "explore" &&
                    evt.Detail.Contains("role:lookout", StringComparison.Ordinal) &&
                    evt.Detail.Contains("formation:patrol", StringComparison.Ordinal) &&
                    evt.Detail.Contains("motion:retreat", StringComparison.Ordinal)), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "scene_choreography_phase" &&
                    evt.NodeId == "explore" &&
                    evt.Detail.Contains("role:lookout", StringComparison.Ordinal) &&
                    evt.Detail.Contains("phase:2", StringComparison.Ordinal) &&
                    evt.Detail.Contains("actors:5", StringComparison.Ordinal)), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "scene_actor_exchange" &&
                    evt.NodeId == "explore" &&
                    evt.Detail.Contains("role:lookout", StringComparison.Ordinal) &&
                    evt.Detail.Contains("exchange:pursuit_cutoff", StringComparison.Ordinal) &&
                    evt.Detail.Contains("interact:pursuit", StringComparison.Ordinal)), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "scene_exchange_outcome" &&
                    evt.NodeId == "explore" &&
                    evt.Detail.Contains("role:lookout", StringComparison.Ordinal) &&
                    evt.Detail.Contains("exchange:pursuit_cutoff", StringComparison.Ordinal) &&
                    evt.Detail.Contains("outcome:escape_cutoff", StringComparison.Ordinal)), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "scene_consequence" &&
                    evt.NodeId == "explore" &&
                    evt.Detail.Contains("outcome:escape_cutoff", StringComparison.Ordinal) &&
                    evt.Detail.Contains("consequence:escape_route_closed", StringComparison.Ordinal)), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "scene_world_signal" &&
                    evt.NodeId == "explore" &&
                    evt.Detail == "scene:witness"), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "scene_world_signal" &&
                    evt.NodeId == "explore" &&
                    evt.Detail == "scene:escape_cutoff"), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "world_signal_scene_shift" &&
                    evt.NodeId == "explore" &&
                    evt.Detail.Contains("signal:scene-witness", StringComparison.Ordinal) &&
                    evt.Detail.Contains("action:witness_point", StringComparison.Ordinal) &&
                    evt.Detail.Contains("role:witness", StringComparison.Ordinal) &&
                    evt.Detail.Contains("trigger:onexplore", StringComparison.Ordinal) &&
                    evt.Detail.Contains("phase:discovery", StringComparison.Ordinal) &&
                    evt.Detail.Contains("source:witness-witness_point", StringComparison.Ordinal) &&
                    evt.Detail.Contains("actors:4", StringComparison.Ordinal)), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "world_signal_scene_shift" &&
                    evt.NodeId == "explore" &&
                    evt.Detail.Contains("signal:scene-escape_cutoff", StringComparison.Ordinal) &&
                    evt.Detail.Contains("action:scout_retreat", StringComparison.Ordinal) &&
                    evt.Detail.Contains("role:lookout", StringComparison.Ordinal) &&
                    evt.Detail.Contains("phase:pursuit", StringComparison.Ordinal) &&
                    evt.Detail.Contains("source:lookout-scout_retreat", StringComparison.Ordinal) &&
                    evt.Detail.Contains("actors:5", StringComparison.Ordinal)), Is.True);
            });
        }

        [Test]
        public void TimelineSnapshot_ConsumesSceneExchangeOutcomeSignalOnFollowupNode()
        {
            DynamicQuestDefinition quest = ExploreGraphQuest();
            quest.Tags = (quest.Tags ?? Array.Empty<string>())
                .Concat(new[] { "scene-director", "dark-brotherhood", "story-cinematic" })
                .ToArray();
            DynamicQuestNode explore = quest.Nodes.Single(node => node.Id == "explore");
            explore.Edges = new[]
            {
                new DynamicQuestEdge { ToNodeId = "wait_outcome", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
            };
            DynamicQuestNode complete = quest.Nodes.Single(node => node.Id == "complete");
            quest.Nodes = quest.Nodes
                .Where(node => !string.Equals(node.Id, "complete", StringComparison.OrdinalIgnoreCase))
                .Concat(new[]
                {
                    new DynamicQuestNode
                    {
                        Id = "wait_outcome",
                        Type = DynamicQuestNodeType.Explore,
                        Title = "탈출로 차단 확인",
                        Text = "추격 차단 결과를 확인합니다.",
                        Objective = new DynamicQuestObjective
                        {
                            LocationName = "탈출로",
                            RegionId = 1,
                            X = 521000,
                            Y = 492000,
                            Z = 2954,
                            Radius = 450
                        },
                        Edges = new[]
                        {
                            new DynamicQuestEdge
                            {
                                ToNodeId = "complete",
                                Condition = DynamicQuestEdgeCondition.WorldSignal,
                                ConditionValue = "scene:escape_cutoff"
                            }
                        }
                    },
                    complete
                })
                .ToArray();
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"speaker\":\"System\",\"text\":\"망보던 자가 탈출로로 물러나자 추격대가 길목을 잘라냅니다.\",\"emotion\":\"alarm\",\"emote\":\"Point\",\"cinematicAction\":\"scout_retreat\",\"sceneRole\":\"lookout_escape\",\"formation\":\"escape\",\"actorCount\":5,\"delayMs\":250}," +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"speaker\":\"System\",\"text\":\"방패 든 전열이 좁은 길을 막아섭니다.\",\"emotion\":\"urgency\",\"emote\":\"Point\",\"cinematicAction\":\"defender_intercept\",\"sceneRole\":\"escape_intercept\",\"formation\":\"line\",\"actorCount\":6,\"delayMs\":700}," +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"speaker\":\"System\",\"text\":\"덤불 뒤의 매복 병력이 한꺼번에 모습을 드러냅니다.\",\"emotion\":\"alarm\",\"emote\":\"Point\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"ambush_wave\",\"formation\":\"ambush\",\"actorCount\":8,\"delayMs\":1100}," +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"speaker\":\"System\",\"text\":\"의식 표식이 끊기며 도주로의 빛이 사라집니다.\",\"emotion\":\"shock\",\"emote\":\"Point\",\"cinematicAction\":\"ritual_interrupt\",\"sceneRole\":\"ritual_break\",\"formation\":\"ring\",\"actorCount\":5,\"delayMs\":1500}," +
                "{\"nodeId\":\"wait_outcome\",\"trigger\":\"OnWorldSignal\",\"speaker\":\"System\",\"text\":\"탈출로 차단 신호가 닿자 방패선이 좁은 길을 밀고 들어갑니다.\",\"emotion\":\"urgency\",\"emote\":\"Point\",\"cinematicAction\":\"guard_advance\",\"sceneRole\":\"signal_counterline\",\"formation\":\"line\",\"actorCount\":7,\"delayMs\":600}" +
                "]";
            quest.StoryNarrativeJson = "[" +
                "{\"nodeId\":\"explore\",\"sceneType\":\"Discovery\",\"title\":\"탈출로의 그림자\",\"body\":\"망보던 자의 후퇴가 매복의 신호였음을 확인합니다.\",\"journalEntry\":\"탈출로 차단 결과를 확인한다.\",\"mood\":\"urgent\",\"revealPolicy\":\"Always\"}," +
                "{\"nodeId\":\"explore\",\"sceneType\":\"Threat\",\"title\":\"드러난 차단선\",\"body\":\"매복 병력이 길목을 좁히고 방패 전열이 퇴로를 압박합니다.\",\"journalEntry\":\"차단 병력의 움직임을 확인한다.\",\"mood\":\"alarm\",\"revealPolicy\":\"Always\"}," +
                "{\"nodeId\":\"wait_outcome\",\"sceneType\":\"Reversal\",\"title\":\"잘린 길목\",\"body\":\"추격대가 탈출로를 선점했고 남은 자들은 방향을 잃었습니다.\",\"journalEntry\":\"탈출 차단 신호가 남았다.\",\"mood\":\"ominous\",\"revealPolicy\":\"Always\"}," +
                "{\"nodeId\":\"complete\",\"sceneType\":\"Completion\",\"title\":\"닫힌 퇴로\",\"body\":\"도주로가 봉쇄되며 사건의 다음 실마리가 드러났습니다.\",\"journalEntry\":\"퇴로 봉쇄를 확인했다.\",\"mood\":\"relieved\",\"revealPolicy\":\"FirstSeenOnly\"}" +
                "]";

            DynamicQuestResult addResult = DynamicQuestRuntimeService.Instance.AddQuest(quest);
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-explore",
                "explore",
                Array.Empty<string>(),
                new Dictionary<string, int>());

            bool explored = DynamicQuestRuntimeService.Instance.RecordExploreProgressForTest(
                "DummyQuest001",
                1,
                521000,
                492000);

            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot(
                "DummyQuest001",
                "DummyQuest001",
                true,
                200);
            DynamicQuestProgressSnapshot progress = DynamicQuestRuntimeService.Instance
                .GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(addResult.Success, Is.True, addResult.Message);
                Assert.That(explored, Is.True);
                Assert.That(progress.CompletedQuestIds, Does.Contain("quest-explore"));
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "scene_exchange_outcome" &&
                    evt.NodeId == "explore" &&
                    evt.Detail.Contains("outcome:escape_cutoff", StringComparison.Ordinal)), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "scene_consequence" &&
                    evt.NodeId == "explore" &&
                    evt.Detail.Contains("consequence:escape_route_closed", StringComparison.Ordinal)), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "scene_world_signal" &&
                    evt.NodeId == "explore" &&
                    evt.Detail == "scene:escape_cutoff"), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "world_signal_pending" &&
                    evt.NodeId == "explore" &&
                    evt.Detail == "scene:escape_cutoff"), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "world_signal" &&
                    evt.NodeId == "wait_outcome" &&
                    evt.Detail == "scene:escape_cutoff"), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "world_signal_scene_shift" &&
                    evt.NodeId == "wait_outcome" &&
                    evt.Detail.Contains("signal:scene-escape_cutoff", StringComparison.Ordinal) &&
                    evt.Detail.Contains("action:guard_advance", StringComparison.Ordinal) &&
                    evt.Detail.Contains("trigger:onworldsignal", StringComparison.Ordinal) &&
                    evt.Detail.Contains("phase:blockade", StringComparison.Ordinal) &&
                    evt.Detail.Contains("source:scene-escape_cutoff", StringComparison.Ordinal) &&
                    evt.Detail.Contains("target:탈출로", StringComparison.Ordinal) &&
                    evt.Detail.Contains("region:1", StringComparison.Ordinal) &&
                    evt.Detail.Contains("actors:7", StringComparison.Ordinal)), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "node_advanced" &&
                    evt.FromNodeId == "wait_outcome" &&
                    evt.ToNodeId == "complete"), Is.True);
            });
        }

        [Test]
        public void TimelineSnapshot_RecordsHundredActorSceneBeatAndCleanup()
        {
            Properties.KDAOC_DYNAMIC_QUEST_CINEMATIC_MAX_ACTORS_PER_ACTION = 100;
            DynamicQuestDefinition quest = ExploreGraphQuest();
            quest.Tags = (quest.Tags ?? Array.Empty<string>())
                .Concat(new[]
                {
                    "story-cinematic",
                    "scene-director",
                    "story-archetype:witness-conspiracy",
                    "story-arc:motive",
                    "story-arc:conflict",
                    "story-arc:reversal",
                    "story-arc:consequence"
                })
                .ToArray();
            quest.StoryNarrativeJson = "[" +
                "{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"증언\",\"body\":\"의뢰인은 마을 길목에 남은 증언과 표식을 보여 준다.\",\"journalEntry\":\"의뢰인에게서 증언을 들었다.\",\"mood\":\"ominous\",\"revealPolicy\":\"FirstSeenOnly\"}," +
                "{\"nodeId\":\"explore\",\"sceneType\":\"Discovery\",\"title\":\"흔적\",\"body\":\"찢긴 울타리와 도망친 발자국이 매복의 동선을 드러낸다.\",\"journalEntry\":\"현장에서 매복 흔적을 찾았다.\",\"mood\":\"urgent\",\"revealPolicy\":\"FirstSeenOnly\"}," +
                "{\"nodeId\":\"kill\",\"sceneType\":\"Threat\",\"title\":\"포위\",\"body\":\"전열 전체가 드러나며 목표 주변을 포위한다.\",\"journalEntry\":\"포위 전열 속에서 위협을 제거해야 한다.\",\"mood\":\"grim\",\"revealPolicy\":\"FirstSeenOnly\"}," +
                "{\"nodeId\":\"return\",\"sceneType\":\"Return\",\"title\":\"보고\",\"body\":\"전투 뒤 남은 표식을 가지고 의뢰인에게 돌아간다.\",\"journalEntry\":\"전투 결과를 보고해야 한다.\",\"mood\":\"relieved\",\"revealPolicy\":\"FirstSeenOnly\"}," +
                "{\"nodeId\":\"choice\",\"sceneType\":\"Choice\",\"title\":\"결정\",\"body\":\"마을의 안전과 더 깊은 추적 사이에서 선택한다.\",\"journalEntry\":\"마무리 방식을 선택해야 한다.\",\"mood\":\"mysterious\",\"revealPolicy\":\"FirstSeenOnly\"}," +
                "{\"nodeId\":\"complete\",\"sceneType\":\"Completion\",\"title\":\"결말\",\"body\":\"마을은 즉각적인 안전을 얻고 사건의 기록이 남는다.\",\"journalEntry\":\"사건을 마무리했다.\",\"mood\":\"hopeful\",\"revealPolicy\":\"FirstSeenOnly\"}" +
                "]";
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"talk\",\"trigger\":\"OnAccept\",\"speaker\":\"StartNpc\",\"text\":\"증언자가 길목을 가리킵니다.\",\"emotion\":\"fear\",\"emote\":\"Shiver\",\"cinematicAction\":\"witness_point\",\"sceneRole\":\"contract_witness\",\"formation\":\"escort\",\"actorCount\":4}," +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"speaker\":\"System\",\"text\":\"망보던 자가 탈출로로 물러납니다.\",\"emotion\":\"suspicion\",\"emote\":\"Ponder\",\"cinematicAction\":\"scout_retreat\",\"sceneRole\":\"lookout_escape\",\"formation\":\"escape\",\"actorCount\":6,\"delayMs\":600}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"speaker\":\"System\",\"text\":\"전열 전체가 목표 주변을 포위합니다.\",\"emotion\":\"urgency\",\"emote\":\"LetsGo\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"mass_ambush_wave\",\"formation\":\"ambush\",\"actorCount\":100,\"delayMs\":1200}," +
                "{\"nodeId\":\"choice\",\"trigger\":\"OnChoiceShown\",\"speaker\":\"StartNpc\",\"text\":\"경비들이 길목을 막고 결정을 기다립니다.\",\"emotion\":\"caution\",\"emote\":\"Point\",\"cinematicAction\":\"threat_standoff\",\"sceneRole\":\"choice_confrontation\",\"formation\":\"line\",\"actorCount\":8,\"delayMs\":800}" +
                "]";
            DynamicQuestResult addResult = DynamicQuestRuntimeService.Instance.AddQuest(quest);
            Assert.That(addResult.Success, Is.True, addResult.Message);
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-explore",
                "explore",
                new[] { "talk" },
                new System.Collections.Generic.Dictionary<string, int>());

            bool explored = DynamicQuestRuntimeService.Instance.RecordExploreProgressForTest(
                "DummyQuest001",
                1,
                521000,
                492000);
            bool killed = DynamicQuestRuntimeService.Instance.RecordKillProgressForTest(
                "DummyQuest001",
                "black wolf pup",
                1,
                1);
            bool returned = DynamicQuestRuntimeService.Instance.RecordNpcInteractionForTest(
                "DummyQuest001",
                "seed-npc-1",
                1);
            bool selected = DynamicQuestRuntimeService.Instance.SelectChoiceForTest(
                "DummyQuest001",
                "quest-explore",
                "safe");

            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot(
                "DummyQuest001",
                "DummyQuest001",
                true,
                120);

            Assert.Multiple(() =>
            {
                Assert.That(explored, Is.True);
                Assert.That(killed, Is.True);
                Assert.That(returned, Is.True);
                Assert.That(selected, Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "world_signal_scene_shift" &&
                    evt.NodeId == "kill" &&
                    evt.Detail.Contains("role:mass_ambush_wave", StringComparison.Ordinal) &&
                    evt.Detail.Contains("actors:100", StringComparison.Ordinal)), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "cinematic_cleanup" &&
                    evt.Detail.StartsWith("cleanup:", StringComparison.Ordinal)), Is.True);
                Assert.That(timeline.Events.Any(evt => evt.EventType == "quest_completed"), Is.True);
            });
        }

        [Test]
        public void CinematicActionPlanForTest_PreservesExplicitHundredActorCountInSnapshot()
        {
            Properties.KDAOC_DYNAMIC_QUEST_CINEMATIC_MAX_ACTORS_PER_ACTION = 100;
            DynamicQuestDefinition quest = ExploreGraphQuest();
            quest.Tags = (quest.Tags ?? Array.Empty<string>())
                .Concat(new[] { "scene-director", "cinematic-actors:combat_stance:100" })
                .ToArray();

            DynamicQuestCinematicPlanSnapshot snapshot = DynamicQuestRuntimeService.BuildCinematicPlanSnapshotForTest(quest);
            DynamicQuestCinematicPlanItem killActor = snapshot.Actions.Single(item =>
                item.NodeId == "kill" &&
                item.Trigger == "OnKill" &&
                item.Kind == "scene_beat" &&
                item.SceneRole == "counterline" &&
                item.NpcAction == "combat_stance");

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.MaxActorsPerAction, Is.EqualTo(100));
                Assert.That(killActor.ActorCount, Is.EqualTo(100));
                Assert.That(killActor.MotionPattern, Is.EqualTo("brace"));
                Assert.That(killActor.MotionStaggerMs, Is.GreaterThanOrEqualTo(50));
                Assert.That(killActor.Detail, Does.Contain(":actors:100"));
                Assert.That(killActor.Detail, Does.Contain(":stagger:75"));
                Assert.That(snapshot.TotalActorCount, Is.GreaterThanOrEqualTo(100));
            });
        }

        [Test]
        public void CinematicActionPlanForTest_ClampsActorCountToOneHundred()
        {
            Properties.KDAOC_DYNAMIC_QUEST_CINEMATIC_MAX_ACTORS_PER_ACTION = 150;
            DynamicQuestDefinition quest = ExploreGraphQuest();
            quest.Tags = (quest.Tags ?? Array.Empty<string>())
                .Concat(new[] { "scene-director", "cinematic-actors:combat_stance:150" })
                .ToArray();

            DynamicQuestCinematicPlanSnapshot snapshot = DynamicQuestRuntimeService.BuildCinematicPlanSnapshotForTest(quest);
            DynamicQuestCinematicPlanItem killActor = snapshot.Actions.Single(item =>
                item.NodeId == "kill" &&
                item.Trigger == "OnKill" &&
                item.Kind == "scene_beat" &&
                item.SceneRole == "counterline" &&
                item.NpcAction == "combat_stance");

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.MaxActorsPerAction, Is.EqualTo(100));
                Assert.That(killActor.ActorCount, Is.EqualTo(100));
                Assert.That(killActor.MotionStaggerMs, Is.GreaterThanOrEqualTo(50));
                Assert.That(killActor.Detail, Does.Contain(":actors:100"));
            });
        }

        [Test]
        public void CinematicModelCatalogForTest_ResolvesPropAndNpcModelsFromQuestContext()
        {
            DynamicQuestDefinition quest = ExploreGraphQuest();
            quest.Realm = "Midgard";
            DynamicQuestNode explore = quest.Nodes.Single(node => node.Id == "explore");
            explore.Title = "룬 토템 조사";
            explore.Text = "룬이 새겨진 뼛조각 토템 주변의 흔적을 확인하세요.";
            explore.Objective.LocationName = "룬 뼛조각 토템";
            DynamicQuestNode kill = quest.Nodes.Single(node => node.Id == "kill");
            kill.Text = "부러진 화살과 전투 흔적이 남은 길목에서 black wolf pup을 제압하세요.";

            ushort totemModel = DynamicQuestRuntimeService.ResolveCinematicMarkerModelForTest(quest, explore, "OnExplore", "rune bone totem");
            ushort recordModel = DynamicQuestRuntimeService.ResolveCinematicMarkerModelForTest(quest, explore, "OnExplore", "record journal tome written 기록 책");
            ushort flameModel = DynamicQuestRuntimeService.ResolveCinematicMarkerModelForTest(quest, explore, "OnExplore", "flame fire torch campfire omen 횃불 불씨");
            ushort battleActorModel = DynamicQuestRuntimeService.ResolveCinematicNpcModelForTest(quest, kill, "OnKill", "battle guard defense");
            DynamicQuestCinematicModelEntry[] propCatalog = DynamicQuestCinematicCatalog.BuildPropCatalogForTest();
            DynamicQuestCinematicModelEntry[] npcCatalog = DynamicQuestCinematicCatalog.BuildNpcCatalogForTest();

            Assert.Multiple(() =>
            {
                Assert.That(totemModel, Is.EqualTo(104));
                Assert.That(recordModel, Is.EqualTo(500));
                Assert.That(flameModel, Is.EqualTo(601));
                Assert.That(battleActorModel, Is.Not.EqualTo(0));
                Assert.That(propCatalog.Length, Is.GreaterThanOrEqualTo(8));
                Assert.That(propCatalog.Select(entry => entry.Model), Does.Contain(totemModel));
                Assert.That(propCatalog.Single(entry => entry.Model == 104).Source, Is.EqualTo("default_prop"));
                Assert.That(propCatalog.Single(entry => entry.Model == 104).Category, Is.EqualTo("relic"));
                Assert.That(npcCatalog.Length, Is.GreaterThanOrEqualTo(8));
                Assert.That(npcCatalog.Select(entry => entry.Model), Does.Contain(battleActorModel));
                Assert.That(npcCatalog.Single(entry => entry.Model == 39).Category, Is.EqualTo("defender"));
                Assert.That(npcCatalog.Single(entry => entry.Model == 342).Category, Is.EqualTo("scout"));
                Assert.That(npcCatalog.Single(entry => entry.Model == 902).Category, Is.EqualTo("threat"));
            });
        }

        [Test]
        public void CinematicModelCatalogForTest_UsesSafeDefaultWhenPropContextIsWeak()
        {
            DynamicQuestDefinition quest = ExploreGraphQuest();
            DynamicQuestNode talk = quest.Nodes.Single(node => node.Id == "talk");

            ushort model = DynamicQuestRuntimeService.ResolveCinematicMarkerModelForTest(quest, talk, "OnNodeEnter", string.Empty);

            Assert.That(model, Is.EqualTo(488));
        }

        [Test]
        public void CinematicCatalogPromptDescription_ExplainsPropCategoriesForStoryGeneration()
        {
            string description = DynamicQuestCinematicCatalog.DescribeCatalogForPrompt();

            Assert.Multiple(() =>
            {
                Assert.That(description, Does.Contain("model:label:category"));
                Assert.That(description, Does.Contain("clue means tracks/evidence/path markers"));
                Assert.That(description, Does.Contain("record means tomes/journals/written warnings"));
                Assert.That(description, Does.Contain("relic means ritual stones/pendants/totems/realm symbols"));
                Assert.That(description, Does.Contain("flame means torches/campfires/omens/fresh danger"));
                Assert.That(description, Does.Contain("weapon means arrows/broken weapons/combat aftermath"));
                Assert.That(description, Does.Contain("structure means doors/gates/portals/keeps/relic pads"));
                Assert.That(description, Does.Contain("NPC role category intent"));
                Assert.That(description, Does.Contain("defender means guards and shield lines"));
            });
        }

        [Test]
        public void CinematicCatalogSnapshot_ExposesLimitedReadOnlyModelCatalog()
        {
            DynamicQuestCinematicCatalogSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetCinematicCatalogSnapshot(8);

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.Limit, Is.EqualTo(8));
                Assert.That(snapshot.PropCount, Is.GreaterThanOrEqualTo(8));
                Assert.That(snapshot.NpcCount, Is.GreaterThanOrEqualTo(8));
                Assert.That(snapshot.Props, Has.Count.EqualTo(8));
                Assert.That(snapshot.Npcs, Has.Count.EqualTo(8));
                Assert.That(snapshot.Props.Select(item => item.Model), Does.Contain(488));
                Assert.That(snapshot.Props.All(item => !string.IsNullOrWhiteSpace(item.Source)), Is.True);
                Assert.That(snapshot.Props.All(item => !string.IsNullOrWhiteSpace(item.Category)), Is.True);
                Assert.That(snapshot.Npcs.All(item => item.Model > 0), Is.True);
            });
        }

        [Test]
        public void CinematicPlanSnapshot_ExposesQuestActionModelsWithoutPlayingScene()
        {
            DynamicQuestDefinition quest = ExploreGraphQuest();
            DynamicQuestCinematicPlanSnapshot snapshot = DynamicQuestRuntimeService.BuildCinematicPlanSnapshotForTest(quest);

            DynamicQuestCinematicPlanItem exploreMarker = snapshot.Actions.First(item =>
                item.NodeId == "explore" &&
                item.Trigger == "OnExplore" &&
                item.Kind == "marker");
            DynamicQuestCinematicPlanItem talkActor = snapshot.Actions.Single(item =>
                item.NodeId == "talk" &&
                item.Trigger == "OnNodeEnter" &&
                item.NpcAction == "challenge");
            DynamicQuestCinematicPlanItem cleanup = snapshot.Actions.Single(item =>
                item.NodeId == "complete" &&
                item.Trigger == "OnComplete" &&
                item.CleanupMarkers);

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.Found, Is.True);
                Assert.That(snapshot.QuestId, Is.EqualTo("quest-explore"));
                Assert.That(snapshot.NodeCount, Is.EqualTo(6));
                Assert.That(snapshot.ActionCount, Is.EqualTo(snapshot.Actions.Count));
                Assert.That(snapshot.MaxActorsPerAction, Is.EqualTo(100));
                Assert.That(snapshot.TotalActorCount, Is.GreaterThan(0));
                Assert.That(exploreMarker.SpawnMarker, Is.True);
                Assert.That(exploreMarker.MarkerModel, Is.Not.EqualTo(0));
                Assert.That(talkActor.SpawnNpcActor, Is.True);
                Assert.That(talkActor.NpcModel, Is.Not.EqualTo(0));
                Assert.That(talkActor.NpcRoleCategory, Is.Not.Empty);
                Assert.That(talkActor.Detail, Does.Contain("catalogRole:"));
                Assert.That(talkActor.ActorCount, Is.EqualTo(1));
                Assert.That(talkActor.ActorName, Does.Contain("Quest Guard"));
                Assert.That(cleanup.Detail, Is.EqualTo("cleanup:OnComplete:complete"));
            });
        }

        [Test]
        public void ProgressSnapshot_RebuildsJournalEntriesAfterProgressReload()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.StoryNarrativeJson = "[" +
                "{\"nodeId\":\"explore\",\"sceneType\":\"Intro\",\"title\":\"숲의 숨죽임\",\"body\":\"울타리가 찢겼다.\",\"journalEntry\":\"숲 가장자리의 흔적을 조사한다.\",\"mood\":\"ominous\",\"revealPolicy\":\"FirstSeenOnly\"}," +
                "{\"nodeId\":\"kill\",\"sceneType\":\"Threat\",\"title\":\"발톱의 주인\",\"body\":\"흔적은 목표에게 이어진다.\",\"journalEntry\":\"목표를 처리해야 한다.\",\"mood\":\"urgent\",\"revealPolicy\":\"FirstSeenOnly\"}" +
                "]";
            service.AddQuest(quest);

            bool accepted = service.AcceptQuestForTest(
                "DummyQuest001",
                "Dummy Quest",
                "quest-world-offer",
                "world_region_entered");
            bool explored = service.RecordExploreProgressForTest(
                "DummyQuest001",
                1,
                521000,
                492000);

            DynamicQuestRuntimeService reloaded = new(repository);
            DynamicQuestProgressItem item = reloaded
                .GetProgressSnapshot("DummyQuest001", "Dummy Quest", false)
                .Active
                .Single();

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(explored, Is.True);
                Assert.That(item.CurrentNodeId, Is.EqualTo("kill"));
                Assert.That(item.JournalEntries.Select(entry => entry.NodeId), Is.EqualTo(new[] { "explore", "kill" }));
                Assert.That(item.JournalEntries.Select(entry => entry.JournalEntry), Does.Contain("숲 가장자리의 흔적을 조사한다."));
                Assert.That(item.JournalEntries.Select(entry => entry.JournalEntry), Does.Contain("목표를 처리해야 한다."));
                Assert.That(item.JournalEntries.Single(entry => entry.NodeId == "kill").Current, Is.True);
            });
        }

        [Test]
        public void RecordExploreProgressForTest_DoesNotAdvanceOutsideRadius()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(ExploreGraphQuest());
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-explore",
                "explore",
                new[] { "talk" },
                new System.Collections.Generic.Dictionary<string, int>());

            bool advanced = DynamicQuestRuntimeService.Instance.RecordExploreProgressForTest(
                "DummyQuest001",
                1,
                522000,
                493000);

            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.False);
                Assert.That(item.CurrentNodeId, Is.EqualTo("explore"));
                Assert.That(item.CompletedNodeIds, Does.Not.Contain("explore"));
            });
        }

        [Test]
        public void RecordExploreProgressForTest_AdvancesInsideRadiusToKillNode()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(ExploreGraphQuest());
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-explore",
                "explore",
                new[] { "talk" },
                new System.Collections.Generic.Dictionary<string, int>());

            bool advanced = DynamicQuestRuntimeService.Instance.RecordExploreProgressForTest(
                "DummyQuest001",
                1,
                521250,
                492250);

            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.True);
                Assert.That(item.CurrentNodeId, Is.EqualTo("kill"));
                Assert.That(item.CurrentNodeType, Is.EqualTo(DynamicQuestNodeType.Kill));
                Assert.That(item.CompletedNodeIds, Does.Contain("explore"));
            });
        }

        [Test]
        public void RecordKillProgressForTest_AdvancesKillNodeToReturnNode()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(GraphQuest());
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-graph",
                "kill",
                new[] { "talk" },
                new System.Collections.Generic.Dictionary<string, int>());

            bool advanced = DynamicQuestRuntimeService.Instance.RecordKillProgressForTest(
                "DummyQuest001",
                "black wolf pup",
                1,
                1);

            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.True);
                Assert.That(item.CurrentNodeId, Is.EqualTo("return"));
                Assert.That(item.CompletedNodeIds, Does.Contain("kill"));
            });
        }

        [TestCase("노련한 black wolf pup")]
        [TestCase("흉포한 black wolf pup")]
        [TestCase("우두머리 black wolf pup")]
        [TestCase("돌연변이 black wolf pup")]
        [TestCase("돌연변이 노련한 black wolf pup")]
        public void RecordKillProgressForTest_MatchesMobGrowthPrefixedTargetName(string enemyName)
        {
            DynamicQuestRuntimeService.Instance.AddQuest(GraphQuest());
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-graph",
                "kill",
                new[] { "talk" },
                new System.Collections.Generic.Dictionary<string, int>());

            bool advanced = DynamicQuestRuntimeService.Instance.RecordKillProgressForTest(
                "DummyQuest001",
                enemyName,
                2,
                1);

            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.True);
                Assert.That(item.CurrentNodeId, Is.EqualTo("return"));
                Assert.That(item.CompletedNodeIds, Does.Contain("kill"));
            });
        }

        [Test]
        public void RecordKillProgressForTest_GroupCreditDoesNotAdvanceWhenObjectiveDisallowsGroupCredit()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(GraphQuest());
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-graph",
                "kill",
                new[] { "talk" },
                new System.Collections.Generic.Dictionary<string, int>());

            bool advanced = DynamicQuestRuntimeService.Instance.RecordKillProgressForTest(
                "DummyQuest001",
                "black wolf pup",
                1,
                1,
                groupCredit: true);

            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.False);
                Assert.That(item.CurrentNodeId, Is.EqualTo("kill"));
                Assert.That(item.CompletedNodeIds, Does.Not.Contain("kill"));
            });
        }

        [Test]
        public void RecordKillProgressForTest_GroupCreditAdvancesWhenObjectiveAllowsGroupCredit()
        {
            DynamicQuestDefinition quest = GraphQuest();
            quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Kill).Objective.AllowGroupCredit = true;
            DynamicQuestRuntimeService.Instance.AddQuest(quest);
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-graph",
                "kill",
                new[] { "talk" },
                new System.Collections.Generic.Dictionary<string, int>());

            bool advanced = DynamicQuestRuntimeService.Instance.RecordKillProgressForTest(
                "DummyQuest001",
                "black wolf pup",
                1,
                1,
                groupCredit: true);

            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.True);
                Assert.That(item.CurrentNodeId, Is.EqualTo("return"));
                Assert.That(item.CompletedNodeIds, Does.Contain("kill"));
            });
        }

        [Test]
        public void RecordKillProgressForPlayersForTest_AdvancesNearbyPlayersWhenObjectiveAllowsGroupCredit()
        {
            DynamicQuestDefinition quest = GraphQuest();
            quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Kill).Objective.AllowGroupCredit = true;
            DynamicQuestRuntimeService.Instance.AddQuest(quest);
            foreach (string playerKey in new[] { "DummyQuest001", "DummyQuest002" })
            {
                DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                    playerKey,
                    "quest-graph",
                    "kill",
                    new[] { "talk" },
                    new System.Collections.Generic.Dictionary<string, int>());
            }

            int advanced = DynamicQuestRuntimeService.Instance.RecordKillProgressForPlayersForTest(
                new[] { "DummyQuest002", "DummyQuest001" },
                killerPlayerKey: "DummyQuest002",
                "black wolf pup",
                1,
                1);

            DynamicQuestProgressItem killer = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest002", "DummyQuest002", true).Active.Single();
            DynamicQuestProgressItem nearby = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.EqualTo(2));
                Assert.That(killer.CurrentNodeId, Is.EqualTo("return"));
                Assert.That(nearby.CurrentNodeId, Is.EqualTo("return"));
                Assert.That(nearby.CompletedNodeIds, Does.Contain("kill"));
            });
        }

        [Test]
        public void RecordNpcInteractionForTest_AdvancesReturnNodeToChoiceNode()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(GraphQuest());
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-graph",
                "return",
                new[] { "talk", "kill" },
                new System.Collections.Generic.Dictionary<string, int>());

            bool advanced = DynamicQuestRuntimeService.Instance.RecordNpcInteractionForTest(
                "DummyQuest001",
                "seed-npc-1",
                1);

            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.True);
                Assert.That(item.CurrentNodeId, Is.EqualTo("choice"));
                Assert.That(item.Choices.Select(choice => choice.Id), Is.EqualTo(new[] { "safe", "followup" }));
            });
        }

        [Test]
        public void RecordNpcInteractionForTest_AdvancesLegacyReturnNodeToComplete()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(LegacyQuest());
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-legacy",
                "return",
                new[] { "kill" },
                new System.Collections.Generic.Dictionary<string, int> { ["kill"] = 2 });

            bool advanced = DynamicQuestRuntimeService.Instance.RecordNpcInteractionForTest(
                "DummyQuest001",
                "seed-npc-1",
                1);

            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.True);
                Assert.That(item.CurrentNodeId, Is.EqualTo("complete"));
                Assert.That(item.IsComplete, Is.True);
            });
        }

        [Test]
        public void SelectChoiceForTest_AdvancesChoiceToComplete()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(GraphQuest());
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-graph",
                "choice",
                new[] { "talk", "kill", "return" },
                new System.Collections.Generic.Dictionary<string, int>());

            bool advanced = DynamicQuestRuntimeService.Instance.SelectChoiceForTest("DummyQuest001", "quest-graph", "safe");

            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();
            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.True);
                Assert.That(item.CurrentNodeId, Is.EqualTo("complete"));
                Assert.That(item.IsComplete, Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "choice_consequence" &&
                    evt.ChoiceId == "safe" &&
                    evt.Detail.Contains("마을은 즉각적인 안전을 얻었지만")), Is.True);
            });
        }

        [Test]
        public void SelectChoiceForTest_ConsumesPendingWorldSignalWhenFollowupNodeEntered()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(ChoiceWorldSignalQuest());
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-choice-signal",
                "return",
                new[] { "talk", "kill" },
                new Dictionary<string, int> { ["kill"] = 1 });

            bool pending = DynamicQuestRuntimeService.Instance.RecordWorldSignalForTest(
                "DummyQuest001",
                "Dummy Quest",
                "mob-growth:killed:region:1");
            bool returned = DynamicQuestRuntimeService.Instance.RecordNpcInteractionForTest(
                "DummyQuest001",
                "seed-npc-1",
                1);
            bool selected = DynamicQuestRuntimeService.Instance.SelectChoiceForTest(
                "DummyQuest001",
                "quest-choice-signal",
                "followup");

            DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "Dummy Quest", true);
            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true, 200);
            DynamicQuestProgressItem item = snapshot.Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(pending, Is.True);
                Assert.That(returned, Is.True);
                Assert.That(selected, Is.True);
                Assert.That(item.CurrentNodeId, Is.EqualTo("complete"));
                Assert.That(item.IsComplete, Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "world_signal_pending" &&
                    evt.NodeId == "return" &&
                    evt.Detail == "mob-growth:killed:region:1"), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "world_signal" &&
                    evt.NodeId == "observe_signal" &&
                    evt.Detail == "mob-growth:killed:region:1"), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "node_advanced" &&
                    evt.FromNodeId == "observe_signal" &&
                    evt.ToNodeId == "complete"), Is.True);
            });
        }

        [Test]
        public void RecordWorldSignalForTest_DeduplicatesRepeatedPendingWorldSignal()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(ChoiceWorldSignalQuest());
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-choice-signal",
                "return",
                new[] { "talk", "kill" },
                new Dictionary<string, int> { ["kill"] = 1 });

            bool first = DynamicQuestRuntimeService.Instance.RecordWorldSignalForTest(
                "DummyQuest001",
                "Dummy Quest",
                "mob-growth:killed:region:1");
            bool second = DynamicQuestRuntimeService.Instance.RecordWorldSignalForTest(
                "DummyQuest001",
                "Dummy Quest",
                "mob-growth:killed:region:1");
            bool third = DynamicQuestRuntimeService.Instance.RecordWorldSignalForTest(
                "DummyQuest001",
                "Dummy Quest",
                "mob-growth:killed:region:1");

            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot(
                "DummyQuest001",
                "Dummy Quest",
                true,
                200);

            Assert.Multiple(() =>
            {
                Assert.That(first, Is.True);
                Assert.That(second, Is.True);
                Assert.That(third, Is.True);
                Assert.That(timeline.Events.Count(evt =>
                    evt.EventType == "world_signal_pending" &&
                    evt.NodeId == "return" &&
                    evt.Detail == "mob-growth:killed:region:1"), Is.EqualTo(1));
            });
        }

        [Test]
        public void SelectChoiceForTest_ConsumesBaseTimeWindowSignalForSpecificWindowEdge()
        {
            DynamicQuestDefinition quest = ChoiceWorldSignalQuest();
            quest.Id = "quest-choice-time-window-signal";
            DynamicQuestNode observe = quest.Nodes.Single(node => node.Id == "observe_signal");
            observe.Edges.Single(edge => edge.Condition == DynamicQuestEdgeCondition.WorldSignal).ConditionValue = "time-window:night";
            DynamicQuestRuntimeService.Instance.AddQuest(quest);
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                quest.Id,
                "return",
                new[] { "talk", "kill" },
                new Dictionary<string, int> { ["kill"] = 1 });

            bool pending = DynamicQuestRuntimeService.Instance.RecordWorldSignalForTest(
                "DummyQuest001",
                "Dummy Quest",
                "time-window");
            bool returned = DynamicQuestRuntimeService.Instance.RecordNpcInteractionForTest(
                "DummyQuest001",
                "seed-npc-1",
                1);
            bool selected = DynamicQuestRuntimeService.Instance.SelectChoiceForTest(
                "DummyQuest001",
                quest.Id,
                "followup");

            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance
                .GetProgressSnapshot("DummyQuest001", "Dummy Quest", true)
                .Active
                .Single();
            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance
                .GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true);

            Assert.Multiple(() =>
            {
                Assert.That(pending, Is.True);
                Assert.That(returned, Is.True);
                Assert.That(selected, Is.True);
                Assert.That(item.CurrentNodeId, Is.EqualTo("complete"));
                Assert.That(item.IsComplete, Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "world_signal" &&
                    evt.NodeId == "observe_signal" &&
                    evt.Detail == "time-window"), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "node_advanced" &&
                    evt.FromNodeId == "observe_signal" &&
                    evt.ToNodeId == "complete"), Is.True);
            });
        }

        [Test]
        public void RecordKillProgressForTest_NpcLessChoiceWorldSignalQuestWaitsForExplicitChoice()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(NpcLessChoiceWorldSignalQuest());
            DynamicQuestRuntimeService.Instance.AcceptQuestForTest(
                "DummyQuest001",
                "Dummy Quest",
                "quest-npc-less-choice-signal");

            bool advanced = DynamicQuestRuntimeService.Instance.RecordKillProgressForTest(
                "DummyQuest001",
                "black wolf pup",
                1,
                1);

            DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot(
                "DummyQuest001",
                "Dummy Quest",
                true);
            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot(
                "DummyQuest001",
                "Dummy Quest",
                true);
            DynamicQuestProgressItem item = snapshot.Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.True);
                Assert.That(item.CurrentNodeId, Is.EqualTo("choice"));
                Assert.That(item.IsComplete, Is.False);
                Assert.That(item.Choices.Select(choice => choice.Id), Is.EqualTo(new[] { "safe", "followup" }));
                Assert.That(timeline.Events.Any(evt => evt.EventType == "choice_selected"), Is.False);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "node_advanced" &&
                    evt.FromNodeId == "choice" &&
                    evt.ToNodeId == "complete" &&
                    evt.Detail == "npc_less_default_choice"), Is.False);
            });
        }

        [Test]
        public void BuildItemAcquiredBranchClueDropForTest_CreatesGenericClueForMatchingActiveItemBranchTarget()
        {
            DynamicQuestRuntimeService service = new(new FakeDynamicQuestProgressRepository());
            DynamicQuestResult addResult = service.AddQuest(NpcLessItemAcquiredBranchQuest());
            Assert.That(addResult.Success, Is.True, addResult.Message);
            service.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-item-acquired-branch",
                "choice",
                new[] { "kill" },
                new Dictionary<string, int> { ["kill"] = 1 });

            DbItemTemplate clue = service.BuildItemAcquiredBranchClueDropForTest("DummyQuest001", "young lynx", 2, 100);
            DbItemTemplate wrongRegion = service.BuildItemAcquiredBranchClueDropForTest("DummyQuest001", "young lynx", 2, 1);

            Assert.Multiple(() =>
            {
                Assert.That(clue, Is.Not.Null);
                Assert.That(clue.Id_nb, Does.StartWith("dynamic_quest_clue_quest-item-acquired-branch_young-lynx"));
                Assert.That(clue.Name, Is.EqualTo("Quest Clue: young lynx"));
                Assert.That(clue.Object_Type, Is.EqualTo((int)eObjectType.GenericItem));
                Assert.That(clue.Item_Type, Is.EqualTo((int)eInventorySlot.Ground));
                Assert.That(clue.CanDropAsLoot, Is.True);
                Assert.That(clue.MaxCount, Is.EqualTo(1));
                Assert.That(wrongRegion, Is.Null);
            });
        }

        [Test]
        public void SelectChoiceForTest_ConsumesPendingItemAcquiredSignalWhenSafeItemBranchObservesClue()
        {
            DynamicQuestRuntimeService service = new(new FakeDynamicQuestProgressRepository());
            service.AddQuest(NpcLessItemAcquiredBranchQuest());
            service.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-item-acquired-branch",
                "choice",
                new[] { "kill" },
                new Dictionary<string, int> { ["kill"] = 1 });

            bool pending = service.RecordWorldSignalForTest(
                "DummyQuest001",
                "Dummy Quest",
                "item-acquired");
            bool selected = service.SelectChoiceForTest(
                "DummyQuest001",
                "quest-item-acquired-branch",
                "safe");

            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "Dummy Quest", true);
            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true, 200);

            Assert.Multiple(() =>
            {
                Assert.That(pending, Is.True);
                Assert.That(selected, Is.True);
                Assert.That(snapshot.Active, Is.Empty);
                Assert.That(snapshot.CompletedQuestIds, Does.Contain("quest-item-acquired-branch"));
                Assert.That(timeline.Events.Any(evt => evt.EventType == "choice_selected" && evt.ChoiceId == "safe"), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "world_signal" &&
                    evt.NodeId == "observe_signal" &&
                    evt.Detail == "item-acquired"), Is.True);
            });
        }

        [Test]
        public void SelectChoiceForTest_ClearsPendingWorldSignalWhenSafeBranchCompletes()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);
            service.AddQuest(ChoiceWorldSignalQuest());
            service.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-choice-signal",
                "return",
                new[] { "talk", "kill" },
                new Dictionary<string, int> { ["kill"] = 1 });

            bool pending = service.RecordWorldSignalForTest(
                "DummyQuest001",
                "Dummy Quest",
                "mob-growth:killed:region:1");
            bool returned = service.RecordNpcInteractionForTest(
                "DummyQuest001",
                "seed-npc-1",
                1);
            bool selected = service.SelectChoiceForTest(
                "DummyQuest001",
                "quest-choice-signal",
                "safe");

            DbDynamicQuestProgress row = repository.Rows.Values.Single();
            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true, 100);

            Assert.Multiple(() =>
            {
                Assert.That(pending, Is.True);
                Assert.That(returned, Is.True);
                Assert.That(selected, Is.True);
                Assert.That(row.CurrentNodeId, Is.EqualTo("complete"));
                Assert.That(row.Completed, Is.True);
                Assert.That(row.NodeCountersJson, Does.Not.Contain("__pending_world_signal__"));
                Assert.That(timeline.Events.Any(evt => evt.EventType == "choice_selected" && evt.ChoiceId == "safe"), Is.True);
                Assert.That(timeline.Events.Any(evt => evt.EventType == "world_signal" && evt.NodeId == "observe_signal"), Is.False);
            });
        }

        [Test]
        public void PendingWorldSignalSurvivesProgressReload()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);
            service.AddQuest(ChoiceWorldSignalQuest());
            service.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-choice-signal",
                "return",
                new[] { "talk", "kill" },
                new Dictionary<string, int> { ["kill"] = 1 });

            bool pending = service.RecordWorldSignalForTest(
                "DummyQuest001",
                "Dummy Quest",
                "mob-growth:killed:region:1");
            string pendingCountersJson = repository.Rows.Values.Single().NodeCountersJson;

            DynamicQuestRuntimeService reloaded = new(repository);
            reloaded.AddQuest(ChoiceWorldSignalQuest());
            reloaded.GetProgressSnapshot("DummyQuest001", "Dummy Quest", true);
            bool returned = reloaded.RecordNpcInteractionForTest("DummyQuest001", "seed-npc-1", 1);
            bool selected = reloaded.SelectChoiceForTest("DummyQuest001", "quest-choice-signal", "followup");

            DynamicQuestProgressSnapshot snapshot = reloaded.GetProgressSnapshot("DummyQuest001", "Dummy Quest", true);
            DynamicQuestTimelineSnapshot timeline = reloaded.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true);
            DynamicQuestProgressItem item = snapshot.Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(pending, Is.True);
                Assert.That(pendingCountersJson, Does.Contain("__pending_world_signal__:mob-growth:killed:region:1"));
                Assert.That(returned, Is.True);
                Assert.That(selected, Is.True);
                Assert.That(item.CurrentNodeId, Is.EqualTo("complete"));
                Assert.That(item.IsComplete, Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "world_signal" &&
                    evt.NodeId == "observe_signal"), Is.True);
            });
        }

        [Test]
        public void RecordExploreProgressForTest_DoesNotCompleteWorldSignalOnlyExploreNode()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);
            service.AddQuest(ChoiceWorldSignalQuest());
            service.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-choice-signal",
                "observe_signal",
                new[] { "talk", "kill", "return", "choice" },
                new Dictionary<string, int> { ["kill"] = 1 });

            bool advanced = service.RecordExploreProgressForTest("DummyQuest001", 1, 521000, 492000);
            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "Dummy Quest", true);
            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true, 100);
            DynamicQuestProgressItem active = snapshot.Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.False);
                Assert.That(active.CurrentNodeId, Is.EqualTo("observe_signal"));
                Assert.That(active.CompletedNodeIds, Does.Not.Contain("observe_signal"));
                Assert.That(timeline.Events.Any(evt => evt.EventType == "explore_complete" && evt.NodeId == "observe_signal"), Is.False);
            });
        }

        [Test]
        public void RecordKillProgressForTest_DefaultsSingleNpcLessChoiceToSafeCompletion()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.Id = "quest-world-choice";
            quest.Reward = new DynamicQuestRewardDefinition
            {
                XpMultiplier = 1.0,
                MoneyMultiplier = 1.0,
                PartyBonusMultiplier = 1.0,
                ChoiceBonusKey = "safe"
            };
            DynamicQuestNode kill = quest.Nodes.Single(node => node.Id == "kill");
            kill.Edges = new[] { new DynamicQuestEdge { ToNodeId = "choice", Condition = DynamicQuestEdgeCondition.ObjectiveComplete } };
            quest.Nodes = quest.Nodes.Concat(new[]
            {
                new DynamicQuestNode
                {
                    Id = "choice",
                    Type = DynamicQuestNodeType.Choice,
                    Title = "정화 방식 선택",
                    Text = "균열을 어떻게 정리할지 선택합니다.",
                    Objective = new DynamicQuestObjective
                    {
                        Choices = new[]
                        {
                            new DynamicQuestChoice { Id = "safe", Label = "지역 안전을 우선한다", Text = "지역 안전을 우선한다.", Consequence = "균열 주변의 즉각적인 위험을 낮추기로 했다." }
                        }
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "safe" }
                    }
                }
            }).ToArray();

            DynamicQuestRuntimeService.Instance.AddQuest(quest);
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-world-choice",
                "kill",
                new[] { "explore" },
                new Dictionary<string, int>());

            bool advanced = DynamicQuestRuntimeService.Instance.RecordKillProgressForTest(
                "DummyQuest001",
                "forest spiderling",
                1,
                1);
            DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);
            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.True);
                Assert.That(snapshot.Active, Is.Empty);
                Assert.That(snapshot.CompletedQuestIds, Does.Contain("quest-world-choice"));
                Assert.That(timeline.Events.Any(evt => evt.EventType == "choice_selected" && evt.ChoiceId == "safe"), Is.True);
                Assert.That(timeline.Events.Any(evt => evt.EventType == "choice_reward_bonus" && evt.Detail == "safe"), Is.True);
                Assert.That(timeline.Events.Select(evt => evt.EventType), Does.Contain("quest_rewarded"));
            });
        }

        [Test]
        public void RecordWorldSignalForTest_AdvancesMatchingWorldSignalEdge()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(WorldSignalGraphQuest());
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-signal",
                "wait_for_signal",
                new[] { "talk" },
                new System.Collections.Generic.Dictionary<string, int>());

            bool ignored = DynamicQuestRuntimeService.Instance.RecordWorldSignalForTest("DummyQuest001", "wrong-signal");
            bool advanced = DynamicQuestRuntimeService.Instance.RecordWorldSignalForTest("DummyQuest001", "region-entered:1");

            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();
            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(ignored, Is.False);
                Assert.That(advanced, Is.True);
                Assert.That(item.CurrentNodeId, Is.EqualTo("return"));
                Assert.That(item.CompletedNodeIds, Does.Contain("wait_for_signal"));
                Assert.That(timeline.Events.Select(evt => evt.EventType), Does.Contain("world_signal"));
            });
        }

        [Test]
        public void BuildTimeWindowSignalsForTest_UsesDeterministicUtcBuckets()
        {
            Assert.Multiple(() =>
            {
                Assert.That(
                    DynamicQuestRuntimeService.BuildTimeWindowSignalsForTest(new DateTime(2026, 6, 5, 5, 0, 0, DateTimeKind.Utc)),
                    Is.EqualTo(new[] { "time-window", "time-window:dawn" }));
                Assert.That(
                    DynamicQuestRuntimeService.BuildTimeWindowSignalsForTest(new DateTime(2026, 6, 5, 12, 0, 0, DateTimeKind.Utc)),
                    Is.EqualTo(new[] { "time-window", "time-window:day" }));
                Assert.That(
                    DynamicQuestRuntimeService.BuildTimeWindowSignalsForTest(new DateTime(2026, 6, 5, 18, 0, 0, DateTimeKind.Utc)),
                    Is.EqualTo(new[] { "time-window", "time-window:dusk" }));
                Assert.That(
                    DynamicQuestRuntimeService.BuildTimeWindowSignalsForTest(new DateTime(2026, 6, 5, 21, 0, 0, DateTimeKind.Utc)),
                    Is.EqualTo(new[] { "time-window", "time-window:night" }));
            });
        }

        [Test]
        public void BuildRegionEnteredSignalsForTest_UsesGenericAndSpecificRegionSignals()
        {
            IList<string> signals = DynamicQuestRuntimeService.BuildRegionEnteredSignalsForTest(181);

            Assert.That(signals, Is.EqualTo(new[]
            {
                "region-entered",
                "region-entered:181",
                "region:181"
            }));
        }

        [Test]
        public void RecordWorldSignalForTest_AdvancesItemAcquiredEdge()
        {
            DynamicQuestDefinition quest = WorldSignalGraphQuest();
            quest.Id = "quest-item-signal";
            quest.Nodes.Single(node => node.Id == "wait_for_signal").Edges = new[]
            {
                new DynamicQuestEdge
                {
                    ToNodeId = "return",
                    Condition = DynamicQuestEdgeCondition.WorldSignal,
                    ConditionValue = "item-acquired:id:ancient-relic-01"
                }
            };
            DynamicQuestRuntimeService.Instance.AddQuest(quest);
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-item-signal",
                "wait_for_signal",
                new[] { "talk" },
                new Dictionary<string, int>());

            IList<string> signals = DynamicQuestRuntimeService.BuildItemAcquiredSignalsForTest(new DbInventoryItem
            {
                Id_nb = "Ancient Relic 01",
                Name = "Ancient Relic"
            });
            bool ignored = DynamicQuestRuntimeService.Instance.RecordWorldSignalForTest("DummyQuest001", "item-acquired:id:other-relic");
            bool advanced = DynamicQuestRuntimeService.Instance.RecordWorldSignalForTest("DummyQuest001", signals.Single(signal => signal.StartsWith("item-acquired:id:", StringComparison.Ordinal)));
            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(signals, Does.Contain("item-acquired"));
                Assert.That(signals, Does.Contain("item-acquired:id:ancient-relic-01"));
                Assert.That(signals, Does.Contain("item-acquired:name:ancient-relic"));
                Assert.That(ignored, Is.False);
                Assert.That(advanced, Is.True);
                Assert.That(item.CurrentNodeId, Is.EqualTo("return"));
            });
        }

        [Test]
        public void CompletedNpcLessQuest_RecordsWorldImpactSummaryAndTimeline()
        {
            DynamicQuestRuntimeService service = new(new FakeDynamicQuestProgressRepository());
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"speaker\":\"System\",\"text\":\"망보던 자가 탈출로로 물러나자 추격대가 길목을 잘라냅니다.\",\"emotion\":\"alarm\",\"emote\":\"Point\",\"cinematicAction\":\"scout_retreat\",\"sceneRole\":\"lookout_escape\",\"formation\":\"escape\",\"actorCount\":5,\"delayMs\":250}" +
                "]";
            service.AddQuest(quest);
            service.AcceptQuestForTest("DummyQuest001", "Dummy Quest", quest.Id);

            service.RecordExploreProgressForTest("DummyQuest001", 1, 521000, 492000);
            service.RecordKillProgressForTest("DummyQuest001", "forest spiderling", 1, 1);

            DynamicQuestWorldImpactSummary impact = service.GetWorldImpactSummary();
            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", false, 20);

            Assert.Multiple(() =>
            {
                Assert.That(impact.TotalRecorded, Is.EqualTo(1));
                Assert.That(impact.Recent.Single().QuestId, Is.EqualTo(quest.Id));
                Assert.That(impact.Recent.Single().RegionId, Is.EqualTo(1));
                Assert.That(impact.Recent.Single().Signals, Does.Contain("region-stabilized:1"));
                Assert.That(impact.Recent.Single().Signals, Does.Contain("scene-consequence:escape_route_closed"));
                Assert.That(impact.Recent.Single().Summary, Does.Contain("현장 여파=탈출로가 닫힘"));
                Assert.That(impact.ByRegion.Single().CompletionCount, Is.EqualTo(1));
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "world_impact" &&
                    evt.Detail.Contains("impact:region_stabilized")), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "world_impact_summary" &&
                    evt.Detail.Contains("현장 여파=탈출로가 닫힘", StringComparison.Ordinal)), Is.True);
            });
        }

        [Test]
        public void CompletedFollowupQuest_RecordsChoiceAndSignalInWorldImpactSummary()
        {
            DynamicQuestRuntimeService service = new(new FakeDynamicQuestProgressRepository());
            DynamicQuestDefinition quest = NpcLessChoiceWorldSignalQuest();
            quest.Tags = new[] { "branch:mob-growth", "world-signal:mob-growth:killed:region:1" };
            service.AddQuest(quest);
            service.AcceptQuestForTest("DummyQuest001", "Dummy Quest", quest.Id);

            Assert.That(service.RecordKillProgressForTest("DummyQuest001", "black wolf pup", 1, 1), Is.True);
            Assert.That(service.SelectChoiceForTest("DummyQuest001", quest.Id, "followup"), Is.True);
            Assert.That(service.RecordWorldSignalForTest("DummyQuest001", "mob-growth:killed:region:1"), Is.True);

            DynamicQuestWorldImpactRecord impact = service.GetWorldImpactSummary().Recent.Single();
            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", false, 80);

            Assert.Multiple(() =>
            {
                Assert.That(impact.ImpactType, Is.EqualTo("thread_uncovered"));
                Assert.That(impact.ChoiceId, Is.EqualTo("followup"));
                Assert.That(impact.ChoiceConsequence, Does.Contain("다음 세계 신호"));
                Assert.That(impact.Summary, Does.Contain("선택=followup"));
                Assert.That(impact.Signals, Does.Contain("branch:mob-growth"));
                Assert.That(impact.Signals, Does.Contain("world-signal:mob-growth:killed:region:1"));
                Assert.That(impact.Signals, Does.Contain("followup-observed"));
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "world_impact" &&
                    evt.Detail.Contains("impact:thread_uncovered") &&
                    evt.Detail.Contains("choice:followup")), Is.True);
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "world_impact_summary" &&
                    evt.Detail.Contains("선택=followup")), Is.True);
            });
        }

        [Test]
        public void TimelineSnapshot_KeepsEarlyAcceptanceThroughPresentationHeavyQuest()
        {
            DynamicQuestRuntimeService service = new(new FakeDynamicQuestProgressRepository());
            MethodInfo recorder = typeof(DynamicQuestRuntimeService).GetMethod(
                "RecordTimelineEventLocked",
                BindingFlags.Instance | BindingFlags.NonPublic);

            Assert.That(recorder, Is.Not.Null);

            recorder.Invoke(service, new object[]
            {
                "DummyQuest001",
                "Dummy Quest",
                "quest-heavy",
                "quest_accepted",
                "talk",
                "",
                "",
                "test",
                "",
                0
            });

            for (int i = 0; i < 450; i++)
            {
                recorder.Invoke(service, new object[]
                {
                    "DummyQuest001",
                    "Dummy Quest",
                    "quest-heavy",
                    "world_signal_pending",
                    "return",
                    "",
                    "",
                    $"time-window:pending:{i}",
                    "",
                    0
                });
            }

            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", false, 1000);

            Assert.Multiple(() =>
            {
                Assert.That(timeline.Events.Count, Is.EqualTo(451));
                Assert.That(timeline.Events.First().EventType, Is.EqualTo("quest_accepted"));
                Assert.That(timeline.Events.Any(evt => evt.EventType == "world_signal_pending"), Is.True);
            });
        }

        [Test]
        public void AcceptAvailableWorldQuestForTest_AcceptsNpcLessItemTriggeredQuest()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.Id = "quest-item-world-offer";
            quest.StartMode = DynamicQuestStartMode.WorldOffer;
            quest.Tags = new[] { "signal:item-acquired:id:ancient-relic-01" };
            DynamicQuestRuntimeService.Instance.AddQuest(quest);

            bool accepted = DynamicQuestRuntimeService.Instance.AcceptAvailableWorldQuestForTest(
                "DummyQuest001",
                "Dummy Quest",
                1,
                "item-acquired:id:ancient-relic-01");
            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "Dummy Quest", true).Active.Single();
            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true);

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(item.QuestId, Is.EqualTo("quest-item-world-offer"));
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "quest_accepted" &&
                    evt.Detail == "item-acquired:id:ancient-relic-01"), Is.True);
            });
        }

        [Test]
        public void AcceptQuestForTest_AutoAdvancesAlwaysEdgeOnStartNode()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.Id = "quest-always-start";
            quest.Nodes.Single(node => node.Id == "explore").Edges = new[]
            {
                new DynamicQuestEdge { ToNodeId = "kill", Condition = DynamicQuestEdgeCondition.Always }
            };
            DynamicQuestRuntimeService.Instance.AddQuest(quest);

            bool accepted = DynamicQuestRuntimeService.Instance.AcceptQuestForTest(
                "DummyQuest001",
                "Dummy Quest",
                "quest-always-start");

            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance
                .GetProgressSnapshot("DummyQuest001", "Dummy Quest", true)
                .Active
                .Single();

            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.True);
                Assert.That(item.CurrentNodeId, Is.EqualTo("kill"));
                Assert.That(item.CompletedNodeIds, Does.Contain("explore"));
            });
        }

        [Test]
        public void RecordKillProgressForTest_AutoAdvancesAlwaysEdgeAfterNodeEntry()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.Id = "quest-always-after-kill";
            quest.Nodes.Single(node => node.Id == "kill").Edges = new[]
            {
                new DynamicQuestEdge { ToNodeId = "aftermath", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
            };
            quest.Nodes = quest.Nodes.Concat(new[]
            {
                new DynamicQuestNode
                {
                    Id = "aftermath",
                    Type = DynamicQuestNodeType.Explore,
                    Title = "잔향 확인",
                    Text = "균열의 잔향을 확인합니다.",
                    Objective = new DynamicQuestObjective
                    {
                        LocationName = "잔향",
                        RegionId = 1,
                        X = 521000,
                        Y = 492000,
                        Radius = 450
                    },
                    Edges = new[] { new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.Always } }
                }
            }).ToArray();
            DynamicQuestRuntimeService.Instance.AddQuest(quest);
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-always-after-kill",
                "kill",
                new[] { "explore" },
                new Dictionary<string, int>());

            bool advanced = DynamicQuestRuntimeService.Instance.RecordKillProgressForTest(
                "DummyQuest001",
                "forest spiderling",
                1,
                1);

            DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "Dummy Quest", true);
            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true);

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.True);
                Assert.That(snapshot.Active, Is.Empty);
                Assert.That(snapshot.CompletedQuestIds, Does.Contain("quest-always-after-kill"));
                Assert.That(timeline.Events.Any(evt => evt.EventType == "node_advanced" && evt.ToNodeId == "complete"), Is.True);
            });
        }

        [Test]
        public void RecordPlayerDiedForTest_AdvancesPlayerDiedEdge()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.Id = "quest-death-branch";
            quest.Nodes.Single(node => node.Id == "explore").Edges = new[]
            {
                new DynamicQuestEdge { ToNodeId = "failed", Condition = DynamicQuestEdgeCondition.PlayerDied }
            };
            quest.Nodes = quest.Nodes.Concat(new[]
            {
                new DynamicQuestNode
                {
                    Id = "failed",
                    Type = DynamicQuestNodeType.Fail,
                    Title = "실패",
                    Text = "흔적이 사라졌습니다."
                }
            }).ToArray();
            DynamicQuestRuntimeService.Instance.AddQuest(quest);
            DynamicQuestRuntimeService.Instance.AcceptQuestForTest("DummyQuest001", "Dummy Quest", "quest-death-branch");

            bool advanced = DynamicQuestRuntimeService.Instance.RecordPlayerDiedForTest("DummyQuest001", "Dummy Quest");
            DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "Dummy Quest", true);
            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true);

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.True);
                Assert.That(snapshot.Active, Is.Empty);
                Assert.That(timeline.Events.Any(evt => evt.EventType == "node_advanced" && evt.ToNodeId == "failed"), Is.True);
            });
        }

        [Test]
        public void RecordPartySizeChangedForTest_AdvancesPartySizeAtLeastWhenThresholdMet()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.Id = "quest-party-branch";
            quest.Nodes.Single(node => node.Id == "explore").Edges = new[]
            {
                new DynamicQuestEdge { ToNodeId = "kill", Condition = DynamicQuestEdgeCondition.PartySizeAtLeast, ConditionValue = "3" }
            };
            DynamicQuestRuntimeService.Instance.AddQuest(quest);
            DynamicQuestRuntimeService.Instance.AcceptQuestForTest("DummyQuest001", "Dummy Quest", "quest-party-branch");

            bool below = DynamicQuestRuntimeService.Instance.RecordPartySizeChangedForTest("DummyQuest001", 2, "Dummy Quest");
            bool met = DynamicQuestRuntimeService.Instance.RecordPartySizeChangedForTest("DummyQuest001", 3, "Dummy Quest");
            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance
                .GetProgressSnapshot("DummyQuest001", "Dummy Quest", true)
                .Active
                .Single();

            Assert.Multiple(() =>
            {
                Assert.That(below, Is.False);
                Assert.That(met, Is.True);
                Assert.That(item.CurrentNodeId, Is.EqualTo("kill"));
            });
        }

        [Test]
        public void RecordTimeoutTickForTest_AdvancesTimedOutEdgeAfterConditionSeconds()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.Id = "quest-timeout-branch";
            quest.Nodes.Single(node => node.Id == "explore").Edges = new[]
            {
                new DynamicQuestEdge { ToNodeId = "failed", Condition = DynamicQuestEdgeCondition.TimedOut, ConditionValue = "10" }
            };
            quest.Nodes = quest.Nodes.Concat(new[]
            {
                new DynamicQuestNode
                {
                    Id = "failed",
                    Type = DynamicQuestNodeType.Fail,
                    Title = "실패",
                    Text = "흔적이 식었습니다."
                }
            }).ToArray();
            DynamicQuestRuntimeService.Instance.AddQuest(quest);
            DynamicQuestRuntimeService.Instance.AcceptQuestForTest("DummyQuest001", "Dummy Quest", "quest-timeout-branch");
            DateTime acceptedAt = DateTime.UtcNow;

            bool early = DynamicQuestRuntimeService.Instance.RecordTimeoutTickForTest("DummyQuest001", acceptedAt.AddSeconds(5), "Dummy Quest");
            bool late = DynamicQuestRuntimeService.Instance.RecordTimeoutTickForTest("DummyQuest001", acceptedAt.AddSeconds(20), "Dummy Quest");

            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true);

            Assert.Multiple(() =>
            {
                Assert.That(early, Is.False);
                Assert.That(late, Is.True);
                Assert.That(timeline.Events.Any(evt => evt.EventType == "node_advanced" && evt.ToNodeId == "failed"), Is.True);
            });
        }

        [Test]
        public void RecordTimeoutTickForTest_AddsFallbackForWorldSignalOnlyFollowupNode()
        {
            DynamicQuestDefinition quest = ChoiceWorldSignalQuest();
            DynamicQuestRuntimeService.Instance.AddQuest(quest);
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                playerKey: "DummyQuest001",
                questId: "quest-choice-signal",
                currentNodeId: "observe_signal",
                completedNodeIds: new[] { "talk", "kill", "choice" },
                nodeCounters: new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase));

            bool advanced = DynamicQuestRuntimeService.Instance.RecordTimeoutTickForTest(
                "DummyQuest001",
                DateTime.UtcNow.AddSeconds(120),
                "Dummy Quest");
            DynamicQuestProgressSnapshot snapshot = DynamicQuestRuntimeService.Instance.GetProgressSnapshot(
                "DummyQuest001",
                "Dummy Quest",
                true);

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.True);
                Assert.That(snapshot.Active.Single().CurrentNodeId, Is.EqualTo("complete"));
                Assert.That(snapshot.Active.Single().IsComplete, Is.True);
            });
        }

        [Test]
        public void RecordWorldSignalForTest_PersistsPlayerNameAndSignalTimeline()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);
            service.AddQuest(WorldSignalGraphQuest());
            service.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-signal",
                "wait_for_signal",
                new[] { "talk" },
                new System.Collections.Generic.Dictionary<string, int>());

            bool advanced = service.RecordWorldSignalForTest("DummyQuest001", "Dummy Quest", "region-entered:1");
            DbDynamicQuestProgress row = repository.Rows.Values.Single();
            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true, 100);
            DynamicQuestTimelineEvent signalEvent = timeline.Events.Single(evt => evt.EventType == "world_signal");

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.True);
                Assert.That(row.PlayerName, Is.EqualTo("Dummy Quest"));
                Assert.That(row.CurrentNodeId, Is.EqualTo("return"));
                Assert.That(signalEvent.PlayerName, Is.EqualTo("Dummy Quest"));
                Assert.That(signalEvent.Detail, Is.EqualTo("region-entered:1"));
            });
        }

        [Test]
        public void RecordWorldSignalForTest_AdvancesGeneratedMobGrowthBossSignal()
        {
            DynamicQuestDefinition quest = WorldSignalGraphQuest();
            quest.Id = "quest-mob-growth-signal";
            quest.Nodes.Single(node => node.Id == "wait_for_signal")
                .Edges.Single()
                .ConditionValue = "mob-growth:killed:boss";
            DynamicQuestRuntimeService.Instance.AddQuest(quest);
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-mob-growth-signal",
                "wait_for_signal",
                new[] { "talk" },
                new System.Collections.Generic.Dictionary<string, int>());

            IList<string> signals = MobGrowthService.BuildQuestKillSignalsForTest(
                new DbMobGrowthState
                {
                    MobId = "mob-growth-test-1",
                    Stage = MobGrowthStages.Boss
                },
                new MobGrowthObservation
                {
                    MobId = "mob-growth-test-1",
                    Name = "우두머리 검은 숲 늑대",
                    RegionId = 1
                });
            bool advanced = false;
            foreach (string signal in signals)
            {
                if (!DynamicQuestRuntimeService.Instance.RecordWorldSignalForTest("DummyQuest001", "Dummy Quest", signal))
                    continue;

                advanced = true;
                break;
            }

            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "Dummy Quest", true).Active.Single();
            DynamicQuestTimelineEvent signalEvent = DynamicQuestRuntimeService.Instance
                .GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true)
                .Events.Single(evt => evt.EventType == "world_signal");

            Assert.Multiple(() =>
            {
                Assert.That(signals, Does.Contain("mob-growth:killed:boss"));
                Assert.That(advanced, Is.True);
                Assert.That(item.CurrentNodeId, Is.EqualTo("return"));
                Assert.That(signalEvent.Detail, Is.EqualTo("mob-growth:killed:boss"));
            });
        }

        [Test]
        public void RecordWorldSignalForTest_AdvancesMobGrowthBossSignalAfterDeathRecord()
        {
            DynamicQuestDefinition quest = WorldSignalGraphQuest();
            quest.Id = "quest-mob-growth-after-death";
            quest.Nodes.Single(node => node.Id == "wait_for_signal")
                .Edges.Single()
                .ConditionValue = "mob-growth:killed:region:1";
            DynamicQuestRuntimeService.Instance.AddQuest(quest);
            DynamicQuestRuntimeService.Instance.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-mob-growth-after-death",
                "wait_for_signal",
                new[] { "talk" },
                new System.Collections.Generic.Dictionary<string, int>());

            FakeMobGrowthRepository growth = new();
            MobGrowthOptions options = MobGrowthOptions.DefaultForTests();
            MobGrowthObservation mob = new()
            {
                MobId = "mob-growth-test-1",
                Name = "우두머리 검은 숲 늑대",
                Region = "북부 숲",
                RegionId = 1,
                Level = 10,
                Size = 50,
                IsAlive = true,
                IsEligible = true
            };
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
            WorldEventService worldEvents = new(
                new FakeWorldEventRepository(),
                new LlmJobQueueService(
                    new FakeWorldEventRepository(),
                    new FakeLlmJobRepository(),
                    new FakeLlmResultRepository(),
                    new LlmResultValidationService(),
                    new FakeLlmResultGenerator()));
            MobGrowthService mobGrowth = new(growth, worldEvents);

            DbMobGrowthState killed = mobGrowth.RecordDeath(mob, System.DateTime.UtcNow, options);
            IList<string> signals = MobGrowthService.BuildQuestKillSignalsForTest(killed, mob);
            foreach (string signal in signals)
            {
                if (DynamicQuestRuntimeService.Instance.RecordWorldSignalForTest("DummyQuest001", "Dummy Quest", signal))
                    break;
            }

            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance
                .GetProgressSnapshot("DummyQuest001", "Dummy Quest", true)
                .Active
                .Single();
            DynamicQuestTimelineEvent signalEvent = DynamicQuestRuntimeService.Instance
                .GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true)
                .Events.Single(evt => evt.EventType == "world_signal");

            Assert.Multiple(() =>
            {
                Assert.That(signals, Does.Contain("mob-growth:killed:region:1"));
                Assert.That(item.CurrentNodeId, Is.EqualTo("return"));
                Assert.That(signalEvent.Detail, Is.EqualTo("mob-growth:killed:region:1"));
            });
        }

        [Test]
        public void RecordWorldSignalForTest_CompletesFollowupBranchAndReloadsNpcTurnIn()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);
            DynamicQuestDefinition quest = ChoiceWorldSignalQuest();
            service.AddQuest(quest);
            service.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-choice-signal",
                "choice",
                new[] { "talk", "kill", "return" },
                new System.Collections.Generic.Dictionary<string, int> { ["kill"] = 1 });

            bool selected = service.SelectChoiceForTest("DummyQuest001", "quest-choice-signal", "followup");
            bool advanced = service.RecordWorldSignalForTest("DummyQuest001", "Dummy Quest", "mob-growth:killed:region:1");
            DbDynamicQuestProgress row = repository.Rows.Values.Single();

            DynamicQuestRuntimeService reloaded = new(repository);
            reloaded.AddQuest(ChoiceWorldSignalQuest());
            DynamicQuestProgressSnapshot snapshot = reloaded.GetProgressSnapshot("DummyQuest001", "Dummy Quest", true);
            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true, 1000);

            Assert.Multiple(() =>
            {
                Assert.That(selected, Is.True);
                Assert.That(advanced, Is.True);
                Assert.That(row.CurrentNodeId, Is.EqualTo("complete"));
                Assert.That(row.Completed, Is.True);
                Assert.That(row.IsActive, Is.True);
                Assert.That(snapshot.Active.Single().CurrentNodeId, Is.EqualTo("complete"));
                Assert.That(timeline.Events.Select(evt => evt.EventType), Does.Contain("choice_selected"));
                Assert.That(timeline.Events.Select(evt => evt.EventType), Does.Contain("world_signal"));
                Assert.That(timeline.Events.Select(evt => evt.EventType), Does.Contain("quest_completed"));
            });
        }

        [Test]
        public void LegacyProgressSnapshotStillReportsTargetFields()
        {
            DynamicQuestRuntimeService.Instance.AddQuest(LegacyQuest());
            DynamicQuestRuntimeService.Instance.RecordProgressForTest("DummyQuest001", "quest-legacy", 1, false);

            DynamicQuestProgressItem item = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(item.TargetName, Is.EqualTo("black wolf pup"));
                Assert.That(item.TargetCount, Is.EqualTo(2));
                Assert.That(item.CurrentNodeId, Is.EqualTo("kill"));
                Assert.That(item.CurrentNodeType, Is.EqualTo(DynamicQuestNodeType.Kill));
            });
        }

        [Test]
        public void ProgressRepository_ReloadsActiveGraphProgressIntoFreshRuntime()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);
            service.AddQuest(GraphQuest());
            service.RecordGraphProgressForTest(
                playerKey: "DummyQuest001",
                questId: "quest-graph",
                currentNodeId: "kill",
                completedNodeIds: new[] { "talk" },
                nodeCounters: new System.Collections.Generic.Dictionary<string, int> { ["kill"] = 1 });

            DynamicQuestRuntimeService reloaded = new(repository);
            reloaded.AddQuest(GraphQuest());

            DynamicQuestProgressItem item = reloaded.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(item.QuestId, Is.EqualTo("quest-graph"));
                Assert.That(item.CurrentNodeId, Is.EqualTo("kill"));
                Assert.That(item.Count, Is.EqualTo(1));
                Assert.That(item.CompletedNodeIds, Is.EqualTo(new[] { "talk" }));
            });
        }

        [Test]
        public void GetProgressSummary_ReportsActiveRowsAndStalledReasonCounts()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);
            service.AddQuest(GraphQuest());
            service.RecordGraphProgressForTest(
                playerKey: "DummyQuest001",
                questId: "quest-graph",
                currentNodeId: "kill",
                completedNodeIds: new[] { "talk" },
                nodeCounters: new System.Collections.Generic.Dictionary<string, int> { ["kill"] = 0 });

            DynamicQuestProgressSummary summary = service.GetProgressSummary();
            DynamicQuestProgressSummaryItem item = summary.Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(summary.ActiveProgressCount, Is.EqualTo(1));
                Assert.That(summary.ByStalledReason["waiting_for_kill_credit"], Is.EqualTo(1));
                Assert.That(summary.ByNodeType["Kill"], Is.EqualTo(1));
                Assert.That(item.PlayerKey, Is.EqualTo("DummyQuest001"));
                Assert.That(item.QuestId, Is.EqualTo("quest-graph"));
                Assert.That(item.CurrentNodeId, Is.EqualTo("kill"));
                Assert.That(item.StalledReason, Is.EqualTo("waiting_for_kill_credit"));
            });
        }

        [Test]
        public void GetProgressCleanupPlan_MarksOnlyStaleCompleteProgressAsCancelCandidate()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);
            DynamicQuestDefinition quest = GraphQuest();
            DateTime staleAt = DateTime.UtcNow.AddMinutes(-10);
            service.AddQuest(quest);
            repository.Rows["completeplayer:quest-graph"] = new DbDynamicQuestProgress
            {
                ProgressId = "completeplayer:quest-graph",
                PlayerKey = "CompletePlayer",
                PlayerName = "CompletePlayer",
                QuestId = "quest-graph",
                CurrentNodeId = "complete",
                IsComplete = true,
                Completed = true,
                IsActive = true,
                NodeCountersJson = JsonSerializer.Serialize(new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase)),
                CompletedNodeIdsJson = JsonSerializer.Serialize(new[] { "talk", "kill", "return", "choice" }),
                ChoiceHistoryJson = JsonSerializer.Serialize(new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)),
                QuestSnapshotJson = JsonSerializer.Serialize(quest),
                AcceptedAt = staleAt,
                CreatedAt = staleAt,
                UpdatedAt = staleAt
            };
            repository.Rows["killplayer:quest-graph"] = new DbDynamicQuestProgress
            {
                ProgressId = "killplayer:quest-graph",
                PlayerKey = "KillPlayer",
                PlayerName = "KillPlayer",
                QuestId = "quest-graph",
                CurrentNodeId = "kill",
                IsActive = true,
                NodeCountersJson = JsonSerializer.Serialize(new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase) { ["kill"] = 0 }),
                CompletedNodeIdsJson = JsonSerializer.Serialize(new[] { "talk" }),
                ChoiceHistoryJson = JsonSerializer.Serialize(new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)),
                QuestSnapshotJson = JsonSerializer.Serialize(quest),
                AcceptedAt = staleAt,
                CreatedAt = staleAt,
                UpdatedAt = staleAt
            };

            DynamicQuestProgressCleanupPlan plan = service.GetProgressCleanupPlan(staleThresholdSeconds: 60);
            DynamicQuestProgressCleanupPlanItem complete = plan.Candidates.Single(item => item.PlayerKey == "CompletePlayer");
            DynamicQuestProgressCleanupPlanItem kill = plan.Candidates.Single(item => item.PlayerKey == "KillPlayer");

            Assert.Multiple(() =>
            {
                Assert.That(plan.CancelCandidateCount, Is.EqualTo(1));
                Assert.That(complete.Stale, Is.True);
                Assert.That(complete.ShouldCancel, Is.True);
                Assert.That(complete.ActionHint, Is.EqualTo("cancel_completed_active_progress"));
                Assert.That(kill.Stale, Is.True);
                Assert.That(kill.ShouldCancel, Is.False);
                Assert.That(kill.ActionHint, Is.EqualTo("inspect_target_or_cancel"));
            });
        }

        [Test]
        public void CancelCompletedCleanupCandidates_CancelsOnlyStaleCompleteProgress()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);
            DynamicQuestDefinition quest = GraphQuest();
            DateTime staleAt = DateTime.UtcNow.AddMinutes(-10);
            service.AddQuest(quest);
            repository.Rows["completeplayer:quest-graph"] = new DbDynamicQuestProgress
            {
                ProgressId = "completeplayer:quest-graph",
                PlayerKey = "CompletePlayer",
                PlayerName = "CompletePlayer",
                QuestId = "quest-graph",
                CurrentNodeId = "complete",
                IsComplete = true,
                Completed = true,
                IsActive = true,
                NodeCountersJson = JsonSerializer.Serialize(new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase)),
                CompletedNodeIdsJson = JsonSerializer.Serialize(new[] { "talk", "kill", "return", "choice" }),
                ChoiceHistoryJson = JsonSerializer.Serialize(new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)),
                QuestSnapshotJson = JsonSerializer.Serialize(quest),
                AcceptedAt = staleAt,
                CreatedAt = staleAt,
                UpdatedAt = staleAt
            };
            repository.Rows["killplayer:quest-graph"] = new DbDynamicQuestProgress
            {
                ProgressId = "killplayer:quest-graph",
                PlayerKey = "KillPlayer",
                PlayerName = "KillPlayer",
                QuestId = "quest-graph",
                CurrentNodeId = "kill",
                IsActive = true,
                NodeCountersJson = JsonSerializer.Serialize(new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase) { ["kill"] = 0 }),
                CompletedNodeIdsJson = JsonSerializer.Serialize(new[] { "talk" }),
                ChoiceHistoryJson = JsonSerializer.Serialize(new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)),
                QuestSnapshotJson = JsonSerializer.Serialize(quest),
                AcceptedAt = staleAt,
                CreatedAt = staleAt,
                UpdatedAt = staleAt
            };

            DynamicQuestProgressCleanupCancelResult result = service.CancelCompletedCleanupCandidates(
                staleThresholdSeconds: 60,
                reason: "unit_cleanup_completed");
            DbDynamicQuestProgress complete = repository.Rows["completeplayer:quest-graph"];
            DbDynamicQuestProgress kill = repository.Rows["killplayer:quest-graph"];

            Assert.Multiple(() =>
            {
                Assert.That(result.CancelledCount, Is.EqualTo(1));
                Assert.That(result.Cancelled.Single().PlayerKey, Is.EqualTo("CompletePlayer"));
                Assert.That(complete.Failed, Is.True);
                Assert.That(complete.IsActive, Is.False);
                Assert.That(complete.CancelReason, Is.EqualTo("unit_cleanup_completed"));
                Assert.That(kill.Failed, Is.False);
                Assert.That(kill.IsActive, Is.True);
                Assert.That(kill.CancelReason, Is.Empty);
            });
        }

        [Test]
        public void AdvanceTimedOutCleanupCandidates_AdvancesWorldSignalFallbackTimeout()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);
            DynamicQuestDefinition quest = ChoiceWorldSignalQuest();
            DateTime staleAt = DateTime.UtcNow.AddMinutes(-10);
            service.AddQuest(quest);
            repository.Rows["dummyquest001:quest-choice-signal"] = new DbDynamicQuestProgress
            {
                ProgressId = "dummyquest001:quest-choice-signal",
                PlayerKey = "DummyQuest001",
                PlayerName = "Dummy Quest",
                QuestId = "quest-choice-signal",
                CurrentNodeId = "observe_signal",
                IsActive = true,
                NodeCountersJson = JsonSerializer.Serialize(new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase)),
                CompletedNodeIdsJson = JsonSerializer.Serialize(new[] { "talk", "kill", "choice" }),
                ChoiceHistoryJson = JsonSerializer.Serialize(new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase) { ["choice"] = "followup" }),
                QuestSnapshotJson = JsonSerializer.Serialize(quest),
                AcceptedAt = staleAt,
                CreatedAt = staleAt,
                UpdatedAt = staleAt
            };

            DynamicQuestProgressCleanupAdvanceResult result = service.AdvanceTimedOutCleanupCandidates(reason: "unit_cleanup_timeout");
            DbDynamicQuestProgress row = repository.Rows["dummyquest001:quest-choice-signal"];
            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "Dummy Quest", true);

            Assert.Multiple(() =>
            {
                Assert.That(result.AdvancedCount, Is.EqualTo(1));
                Assert.That(result.Advanced.Single().ActionHint, Is.EqualTo("advance_timed_out_progress"));
                Assert.That(row.CurrentNodeId, Is.EqualTo("complete"));
                Assert.That(row.IsComplete, Is.True);
                Assert.That(row.Completed, Is.True);
                Assert.That(snapshot.Active.Single().CurrentNodeId, Is.EqualTo("complete"));
            });
        }

        [Test]
        public void CancelActiveProgressForPlayer_MarksProgressCancelledWithoutDeletingRepositoryRow()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);
            service.AddQuest(GraphQuest());
            service.RecordGraphProgressForTest(
                playerKey: "DummyQuest001",
                questId: "quest-graph",
                currentNodeId: "kill",
                completedNodeIds: new[] { "talk" },
                nodeCounters: new System.Collections.Generic.Dictionary<string, int> { ["kill"] = 1 });

            int cancelled = service.CancelActiveProgressForPlayer(
                "DummyQuest001",
                "DummyQuest001",
                "dummy_test_cleanup");

            DbDynamicQuestProgress row = repository.Rows.Values.Single();
            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);
            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(cancelled, Is.EqualTo(1));
                Assert.That(repository.Rows, Has.Count.EqualTo(1));
                Assert.That(row.Failed, Is.True);
                Assert.That(row.IsActive, Is.False);
                Assert.That(row.CancelReason, Is.EqualTo("dummy_test_cleanup"));
                Assert.That(snapshot.Active, Is.Empty);
                Assert.That(timeline.Events.Select(evt => evt.EventType), Does.Contain("quest_cancelled"));
            });
        }

        [Test]
        public void ProgressRepository_ReloadsDynamicProgressWhenBindingAndWorldRevisionMatch()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestDefinition quest = GraphQuest();
            quest.Id = "template-wolf-trouble";
            quest.BindingKey = "binding-a";
            quest.WorldRevision = "world-1";

            DynamicQuestRuntimeService service = new(repository);
            service.AddQuest(quest);
            service.RecordGraphProgressForTest(
                playerKey: "DummyQuest001",
                questId: "template-wolf-trouble",
                currentNodeId: "kill",
                completedNodeIds: new[] { "talk" },
                nodeCounters: new System.Collections.Generic.Dictionary<string, int> { ["kill"] = 1 },
                bindingKey: "binding-a",
                worldRevision: "world-1");

            DynamicQuestRuntimeService reloaded = new(repository);
            reloaded.AddQuest(quest);

            DynamicQuestProgressItem item = reloaded.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true).Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(item.QuestId, Is.EqualTo("template-wolf-trouble"));
                Assert.That(item.BindingKey, Is.EqualTo("binding-a"));
                Assert.That(item.WorldRevision, Is.EqualTo("world-1"));
                Assert.That(item.CurrentNodeId, Is.EqualTo("kill"));
                Assert.That(item.Count, Is.EqualTo(1));
            });
        }

        [Test]
        public void ProgressRepository_ReloadsDynamicProgressFromSnapshotWhenLiveQuestRebound()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestDefinition quest = GraphQuest();
            quest.Id = "template-wolf-trouble";
            quest.BindingKey = "binding-a";
            quest.WorldRevision = "world-1";

            DynamicQuestRuntimeService service = new(repository);
            service.AddQuest(quest);
            service.RecordGraphProgressForTest(
                playerKey: "DummyQuest001",
                questId: "template-wolf-trouble",
                currentNodeId: "kill",
                completedNodeIds: new[] { "talk" },
                nodeCounters: new System.Collections.Generic.Dictionary<string, int> { ["kill"] = 1 },
                bindingKey: "binding-a",
                worldRevision: "world-1");

            DynamicQuestRuntimeService reloaded = new(repository);

            DynamicQuestProgressItem item = reloaded.GetProgressSnapshot("DummyQuest001", "DummyQuest001", false).Active.Single();

            Assert.Multiple(() =>
            {
                Assert.That(item.QuestId, Is.EqualTo("template-wolf-trouble"));
                Assert.That(item.BindingKey, Is.EqualTo("binding-a"));
                Assert.That(item.WorldRevision, Is.EqualTo("world-1"));
                Assert.That(item.CurrentNodeId, Is.EqualTo("kill"));
                Assert.That(item.Count, Is.EqualTo(1));
                Assert.That(item.TargetName, Is.EqualTo("black wolf pup"));
            });
        }

        [Test]
        public void ProgressRepository_CancelsSnapshotProgressWhenRuntimeOfferRemovedBySystemCleanup()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestDefinition quest = GraphQuest();
            quest.Id = "template-wolf-trouble";
            quest.BindingKey = "binding-a";
            quest.WorldRevision = "world-1";

            DynamicQuestRuntimeService service = new(repository);
            service.AddQuest(quest);
            service.RecordGraphProgressForTest(
                playerKey: "DummyQuest001",
                questId: "template-wolf-trouble",
                currentNodeId: "kill",
                completedNodeIds: new[] { "talk" },
                nodeCounters: new System.Collections.Generic.Dictionary<string, int> { ["kill"] = 1 },
                bindingKey: "binding-a",
                worldRevision: "world-1");

            DynamicQuestRuntimeService reloaded = new(repository);
            int cancelled = reloaded.CancelActiveProgressForMissingRuntimeQuests("runtime_offer_removed");

            DynamicQuestProgressSnapshot snapshot = reloaded.GetProgressSnapshot("DummyQuest001", "DummyQuest001", false);
            DbDynamicQuestProgress row = repository.Rows["dummyquest001:template-wolf-trouble"];
            DynamicQuestTimelineSnapshot timeline = reloaded.GetTimelineSnapshot("DummyQuest001", "DummyQuest001", false);

            Assert.Multiple(() =>
            {
                Assert.That(cancelled, Is.EqualTo(1));
                Assert.That(snapshot.Active, Is.Empty);
                Assert.That(row.IsActive, Is.False);
                Assert.That(row.Failed, Is.True);
                Assert.That(row.CancelReason, Is.EqualTo("runtime_offer_removed"));
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "quest_cancelled" &&
                    evt.Detail == "runtime_offer_removed"), Is.True);
            });
        }

        [Test]
        public void ProgressRepository_CancelsSnapshotProgressWhenServerWorldRevisionChangedBeforeSeed()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestDefinition quest = GraphQuest();
            quest.Id = "template-wolf-trouble";
            quest.BindingKey = "binding-a";
            quest.WorldRevision = "world-1";

            DynamicQuestRuntimeService service = new(repository);
            service.AddQuest(quest);
            service.RecordGraphProgressForTest(
                playerKey: "DummyQuest001",
                questId: "template-wolf-trouble",
                currentNodeId: "kill",
                completedNodeIds: new[] { "talk" },
                nodeCounters: new System.Collections.Generic.Dictionary<string, int> { ["kill"] = 1 },
                bindingKey: "binding-a",
                worldRevision: "world-1");

            Properties.KDAOC_DYNAMIC_QUEST_WORLD_REVISION = "world-2";
            DynamicQuestRuntimeService reloadedBeforeSeed = new(repository);

            DynamicQuestProgressSnapshot snapshot = reloadedBeforeSeed.GetProgressSnapshot("DummyQuest001", "DummyQuest001", false);
            DbDynamicQuestProgress row = repository.Rows["dummyquest001:template-wolf-trouble"];
            DynamicQuestTimelineSnapshot timeline = reloadedBeforeSeed.GetTimelineSnapshot("DummyQuest001", "DummyQuest001", false);

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.Active, Is.Empty);
                Assert.That(row.IsActive, Is.False);
                Assert.That(row.Failed, Is.True);
                Assert.That(row.CancelReason, Is.EqualTo("world_revision_changed"));
                Assert.That(timeline.Events.Any(evt =>
                    evt.EventType == "quest_cancelled" &&
                    evt.Detail == "world_revision_changed"), Is.True);
            });
        }

        [Test]
        public void ProgressRepository_KeepsBindingChangedProgressButCancelsWorldRevisionChangedProgress()
        {
            FakeDynamicQuestProgressRepository repository = new();
            repository.Rows["binding-stale:template-wolf-trouble"] = new DbDynamicQuestProgress
            {
                ProgressId = "binding-stale:template-wolf-trouble",
                PlayerKey = "binding-stale",
                PlayerName = "BindingStale",
                QuestId = "template-wolf-trouble",
                CurrentNodeId = "kill",
                BindingKey = "binding-old",
                WorldRevision = "world-2",
                IsActive = true,
                AcceptedAt = DateTime.UtcNow.AddMinutes(-10),
                CreatedAt = DateTime.UtcNow.AddMinutes(-10),
                UpdatedAt = DateTime.UtcNow.AddMinutes(-5)
            };
            repository.Rows["world-stale:template-wolf-trouble"] = new DbDynamicQuestProgress
            {
                ProgressId = "world-stale:template-wolf-trouble",
                PlayerKey = "world-stale",
                PlayerName = "WorldStale",
                QuestId = "template-wolf-trouble",
                CurrentNodeId = "kill",
                BindingKey = "binding-current",
                WorldRevision = "world-1",
                IsActive = true,
                AcceptedAt = DateTime.UtcNow.AddMinutes(-9),
                CreatedAt = DateTime.UtcNow.AddMinutes(-9),
                UpdatedAt = DateTime.UtcNow.AddMinutes(-4)
            };
            DynamicQuestDefinition quest = GraphQuest();
            quest.Id = "template-wolf-trouble";
            quest.BindingKey = "binding-current";
            quest.WorldRevision = "world-2";

            DynamicQuestRuntimeService service = new(repository);
            service.AddQuest(quest);

            DynamicQuestProgressSnapshot bindingSnapshot = service.GetProgressSnapshot("binding-stale", "BindingStale", false);
            DynamicQuestProgressSnapshot worldSnapshot = service.GetProgressSnapshot("world-stale", "WorldStale", false);
            DbDynamicQuestProgress bindingStale = repository.Rows["binding-stale:template-wolf-trouble"];
            DbDynamicQuestProgress worldStale = repository.Rows["world-stale:template-wolf-trouble"];

            Assert.Multiple(() =>
            {
                Assert.That(bindingSnapshot.Active, Has.Count.EqualTo(1));
                Assert.That(bindingSnapshot.Active.Single().BindingKey, Is.EqualTo("binding-old"));
                Assert.That(bindingSnapshot.Active.Single().WorldRevision, Is.EqualTo("world-2"));
                Assert.That(worldSnapshot.Active, Is.Empty);
                Assert.That(bindingStale.IsActive, Is.True);
                Assert.That(bindingStale.Failed, Is.False);
                Assert.That(bindingStale.CancelReason, Is.EqualTo(string.Empty));
                Assert.That(worldStale.IsActive, Is.False);
                Assert.That(worldStale.Failed, Is.True);
                Assert.That(worldStale.CancelReason, Is.EqualTo("world_revision_changed"));
            });
        }

        [Test]
        public void CancelActiveProgressForWorldRevision_MarksChangedWorldProgressInactive()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestDefinition quest = GraphQuest();
            quest.Id = "template-wolf-trouble";
            quest.BindingKey = "binding-a";
            quest.WorldRevision = "world-1";
            DynamicQuestRuntimeService service = new(repository);
            service.AddQuest(quest);
            service.RecordGraphProgressForTest(
                playerKey: "DummyQuest001",
                questId: "template-wolf-trouble",
                currentNodeId: "kill",
                completedNodeIds: new[] { "talk" },
                nodeCounters: new System.Collections.Generic.Dictionary<string, int> { ["kill"] = 1 },
                bindingKey: "binding-a",
                worldRevision: "world-1");

            int cancelled = service.CancelActiveProgressForWorldRevision("world-2", "world_changed");
            DbDynamicQuestProgress row = repository.Rows.Values.Single();
            DynamicQuestProgressSnapshot snapshot = service.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);
            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(cancelled, Is.EqualTo(1));
                Assert.That(row.IsActive, Is.False);
                Assert.That(row.Failed, Is.True);
                Assert.That(row.CancelReason, Is.EqualTo("world_changed"));
                Assert.That(snapshot.Active, Is.Empty);
                Assert.That(timeline.Events.Select(item => item.EventType), Does.Contain("quest_cancelled"));
            });
        }

        [Test]
        public void CancelActiveProgressForWorldRevision_MarksOfflineRepositoryRowsInactive()
        {
            FakeDynamicQuestProgressRepository repository = new();
            repository.Rows["offline-player:template-wolf-trouble"] = new DbDynamicQuestProgress
            {
                ProgressId = "offline-player:template-wolf-trouble",
                PlayerKey = "offline-player",
                PlayerName = "OfflinePlayer",
                QuestId = "template-wolf-trouble",
                CurrentNodeId = "kill",
                WorldRevision = "world-1",
                BindingKey = "binding-a",
                IsActive = true,
                AcceptedAt = DateTime.UtcNow.AddMinutes(-10),
                CreatedAt = DateTime.UtcNow.AddMinutes(-10),
                UpdatedAt = DateTime.UtcNow.AddMinutes(-5)
            };
            repository.Rows["same-world:template-wolf-trouble"] = new DbDynamicQuestProgress
            {
                ProgressId = "same-world:template-wolf-trouble",
                PlayerKey = "same-world",
                PlayerName = "SameWorld",
                QuestId = "template-wolf-trouble",
                CurrentNodeId = "kill",
                WorldRevision = "world-2",
                BindingKey = "binding-b",
                IsActive = true,
                AcceptedAt = DateTime.UtcNow.AddMinutes(-9),
                CreatedAt = DateTime.UtcNow.AddMinutes(-9),
                UpdatedAt = DateTime.UtcNow.AddMinutes(-4)
            };

            DynamicQuestRuntimeService service = new(repository);

            int cancelled = service.CancelActiveProgressForWorldRevision("world-2", "world_changed");
            DbDynamicQuestProgress stale = repository.Rows["offline-player:template-wolf-trouble"];
            DbDynamicQuestProgress current = repository.Rows["same-world:template-wolf-trouble"];
            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot("offline-player", "OfflinePlayer", false);

            Assert.Multiple(() =>
            {
                Assert.That(cancelled, Is.EqualTo(1));
                Assert.That(stale.IsActive, Is.False);
                Assert.That(stale.Failed, Is.True);
                Assert.That(stale.CancelReason, Is.EqualTo("world_changed"));
                Assert.That(timeline.Events.Select(item => item.EventType), Does.Contain("quest_cancelled"));
                Assert.That(current.IsActive, Is.True);
                Assert.That(current.Failed, Is.False);
            });
        }

        [Test]
        public void CancelActiveProgressForWorldRevision_CancelsCompletedNpcTurnInRows()
        {
            FakeDynamicQuestProgressRepository repository = new();
            repository.Rows["offline-player:template-wolf-trouble"] = new DbDynamicQuestProgress
            {
                ProgressId = "offline-player:template-wolf-trouble",
                PlayerKey = "offline-player",
                PlayerName = "OfflinePlayer",
                QuestId = "template-wolf-trouble",
                CurrentNodeId = "complete",
                WorldRevision = "world-1",
                BindingKey = "binding-a",
                IsActive = true,
                IsComplete = true,
                Completed = true,
                AcceptedAt = DateTime.UtcNow.AddMinutes(-10),
                CreatedAt = DateTime.UtcNow.AddMinutes(-10),
                UpdatedAt = DateTime.UtcNow.AddMinutes(-5)
            };

            DynamicQuestRuntimeService service = new(repository);

            int cancelled = service.CancelActiveProgressForWorldRevision("world-2", "world_changed");
            DbDynamicQuestProgress stale = repository.Rows["offline-player:template-wolf-trouble"];

            Assert.Multiple(() =>
            {
                Assert.That(cancelled, Is.EqualTo(1));
                Assert.That(stale.IsActive, Is.False);
                Assert.That(stale.Failed, Is.True);
                Assert.That(stale.CancelReason, Is.EqualTo("world_changed"));
            });
        }

        [Test]
        public void ProgressRepository_KeepsCompletedNpcChoiceProgressActiveUntilRewarded()
        {
            FakeDynamicQuestProgressRepository repository = new();
            DynamicQuestRuntimeService service = new(repository);
            service.AddQuest(GraphQuest());
            service.RecordGraphProgressForTest(
                "DummyQuest001",
                "quest-graph",
                "choice",
                new[] { "talk", "kill", "return" },
                new System.Collections.Generic.Dictionary<string, int> { ["kill"] = 1 });

            bool advanced = service.SelectChoiceForTest("DummyQuest001", "quest-graph", "safe");
            DbDynamicQuestProgress row = repository.Rows.Values.Single();
            using JsonDocument choiceHistory = JsonDocument.Parse(row.ChoiceHistoryJson);
            DynamicQuestDefinition savedQuest = JsonSerializer.Deserialize<DynamicQuestDefinition>(row.QuestSnapshotJson);

            DynamicQuestRuntimeService reloaded = new(repository);
            reloaded.AddQuest(GraphQuest());
            DynamicQuestProgressSnapshot snapshot = reloaded.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);

            Assert.Multiple(() =>
            {
                Assert.That(advanced, Is.True);
                Assert.That(row.Completed, Is.True);
                Assert.That(row.IsActive, Is.True);
                Assert.That(row.CurrentNodeId, Is.EqualTo("complete"));
                Assert.That(choiceHistory.RootElement.GetProperty("choice").GetString(), Is.EqualTo("safe"));
                Assert.That(savedQuest.Nodes.Single(node => node.Id == "choice").Objective.Choices.First().Consequence, Does.Contain("마을은 즉각적인 안전"));
                Assert.That(snapshot.Active.Single().CurrentNodeId, Is.EqualTo("complete"));
                Assert.That(snapshot.Active.Single().IsComplete, Is.True);
            });
        }

        [Test]
        public void CalculateRewardScaleForTest_UsesRewardMultipliersAndCompletedPlayableSteps()
        {
            DynamicQuestDefinition quest = GraphQuest();
            quest.Reward = new DynamicQuestRewardDefinition
            {
                XpMultiplier = 1.5,
                MoneyMultiplier = 2.0,
                StepBonusMultiplier = 0.25,
                PartyBonusMultiplier = 1.0
            };
            DynamicQuestProgress progress = new()
            {
                CompletedNodeIds = new System.Collections.Generic.HashSet<string> { "talk", "kill", "return", "choice" }
            };

            double xpScale = DynamicQuestRuntimeService.CalculateRewardScaleForTest(quest, progress, RewardScaleKind.Xp);
            double moneyScale = DynamicQuestRuntimeService.CalculateRewardScaleForTest(quest, progress, RewardScaleKind.Money);

            Assert.Multiple(() =>
            {
                Assert.That(xpScale, Is.EqualTo(2.625).Within(0.0001));
                Assert.That(moneyScale, Is.EqualTo(3.5).Within(0.0001));
            });
        }

        [Test]
        public void CalculateRewardScaleForTest_CountsCompletedExploreAsPlayableStep()
        {
            DynamicQuestDefinition quest = ExploreGraphQuest();
            quest.Reward = new DynamicQuestRewardDefinition
            {
                XpMultiplier = 1.0,
                MoneyMultiplier = 1.0,
                StepBonusMultiplier = 0.25,
                PartyBonusMultiplier = 1.0
            };
            DynamicQuestProgress progress = new()
            {
                CompletedNodeIds = new System.Collections.Generic.HashSet<string> { "talk", "explore", "kill", "return", "choice" }
            };

            double xpScale = DynamicQuestRuntimeService.CalculateRewardScaleForTest(quest, progress, RewardScaleKind.Xp);

            Assert.That(xpScale, Is.EqualTo(2.0).Within(0.0001));
        }

        [Test]
        public void CalculateRewardScaleForTest_AppliesChoiceBonusWhenSelectedChoiceMatchesRewardKey()
        {
            DynamicQuestDefinition quest = GraphQuest();
            quest.Reward = new DynamicQuestRewardDefinition
            {
                XpMultiplier = 1.0,
                MoneyMultiplier = 1.0,
                StepBonusMultiplier = 0,
                PartyBonusMultiplier = 1.0,
                ChoiceBonusKey = "followup"
            };
            DynamicQuestProgress rewardedProgress = new()
            {
                ChoiceHistory = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                {
                    ["choice"] = "followup"
                }
            };
            DynamicQuestProgress safeProgress = new()
            {
                ChoiceHistory = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                {
                    ["choice"] = "safe"
                }
            };

            double rewardedScale = DynamicQuestRuntimeService.CalculateRewardScaleForTest(quest, rewardedProgress, RewardScaleKind.Xp);
            double safeScale = DynamicQuestRuntimeService.CalculateRewardScaleForTest(quest, safeProgress, RewardScaleKind.Xp);

            Assert.Multiple(() =>
            {
                Assert.That(rewardedScale, Is.EqualTo(1.15).Within(0.0001));
                Assert.That(safeScale, Is.EqualTo(1.0).Within(0.0001));
            });
        }

        [Test]
        public void ParseLlmQuestForTest_AcceptsValidatedGraphTemplate()
        {
            const string json = @"{
                ""title"": ""늑대 흔적의 밤"",
                ""offer"": ""밤마다 울음소리가 가까워지고 있습니다."",
                ""progress"": ""검은 늑대 새끼의 흔적을 줄여야 합니다."",
                ""finish"": ""마을 사람들이 오늘은 잠들 수 있겠군요."",
                ""target"": ""black wolf pup"",
                ""count"": 1,
                ""min_level"": 1,
                ""max_level"": 5,
                ""graph"": {
                    ""start"": ""talk"",
                    ""nodes"": [
                        { ""id"": ""talk"", ""type"": ""Talk"", ""title"": ""소문 확인"", ""text"": ""먼저 이야기를 들어보세요."", ""edges"": [{ ""to"": ""kill"", ""condition"": ""ObjectiveComplete"" }] },
                        { ""id"": ""kill"", ""type"": ""Kill"", ""title"": ""위협 제거"", ""text"": ""검은 늑대 새끼를 처치하세요."", ""objective"": { ""target"": ""black wolf pup"", ""count"": 1, ""min_level"": 1, ""max_level"": 5 }, ""edges"": [{ ""to"": ""return"", ""condition"": ""ObjectiveComplete"" }] },
                        { ""id"": ""return"", ""type"": ""ReturnToNpc"", ""title"": ""보고"", ""text"": ""Brother Penric에게 돌아가세요."", ""edges"": [{ ""to"": ""choice"", ""condition"": ""ObjectiveComplete"" }] },
                        { ""id"": ""choice"", ""type"": ""Choice"", ""title"": ""결정"", ""text"": ""어떻게 마무리하시겠습니까?"", ""choices"": [{ ""id"": ""safe"", ""label"": ""마을 안전"", ""text"": ""마을 안전을 우선한다."", ""consequence"": ""마을 사람들은 오늘 밤 문을 덜 세게 잠근다."" }, { ""id"": ""followup"", ""label"": ""추적"", ""text"": ""더 큰 위협을 추적한다."" }], ""edges"": [{ ""to"": ""complete"", ""condition"": ""ChoiceSelected"", ""value"": ""safe"" }, { ""to"": ""complete"", ""condition"": ""ChoiceSelected"", ""value"": ""followup"" }] },
                        { ""id"": ""complete"", ""type"": ""Complete"", ""title"": ""완료"", ""text"": ""고맙습니다."" }
                    ]
                }
            }";

            DynamicQuestDefinition quest = DynamicQuestRuntimeService.ParseLlmQuestForTest("seed-npc-1", "Brother Penric", 1, json);
            DynamicQuestResult result = DynamicQuestRuntimeService.Instance.AddQuest(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True);
                Assert.That(quest.StartNodeId, Is.EqualTo("talk"));
                Assert.That(quest.Nodes.Select(node => node.Type), Is.EqualTo(new[]
                {
                    DynamicQuestNodeType.Talk,
                    DynamicQuestNodeType.Kill,
                    DynamicQuestNodeType.ReturnToNpc,
                    DynamicQuestNodeType.Choice,
                    DynamicQuestNodeType.Complete
                }));
                Assert.That(quest.Nodes.Single(node => node.Id == "kill").Objective.TargetName, Is.EqualTo("black wolf pup"));
                Assert.That(quest.Nodes.Single(node => node.Id == "return").Objective.NpcInternalId, Is.EqualTo("seed-npc-1"));
                Assert.That(quest.Nodes.Single(node => node.Id == "choice").Objective.Choices.Select(choice => choice.Id), Is.EqualTo(new[] { "safe", "followup" }));
                Assert.That(quest.Nodes.Single(node => node.Id == "choice").Objective.Choices.First().Consequence, Is.EqualTo("마을 사람들은 오늘 밤 문을 덜 세게 잠근다."));
            });
        }

        [Test]
        public void ParseLlmQuestForTest_AcceptsExploreTextOnlyAndUsesServerOwnedLocationFallback()
        {
            const string json = @"{
                ""title"": ""늑대 흔적의 밤"",
                ""offer"": ""밤마다 울음소리가 가까워지고 있습니다."",
                ""progress"": ""흔적을 확인해야 합니다."",
                ""finish"": ""마을 사람들이 오늘은 잠들 수 있겠군요."",
                ""target"": ""black wolf pup"",
                ""count"": 1,
                ""min_level"": 1,
                ""max_level"": 5,
                ""graph"": {
                    ""start"": ""talk"",
                    ""nodes"": [
                        { ""id"": ""talk"", ""type"": ""Talk"", ""title"": ""소문 확인"", ""text"": ""먼저 이야기를 들어보세요."", ""edges"": [{ ""to"": ""explore"", ""condition"": ""ObjectiveComplete"" }] },
                        { ""id"": ""explore"", ""type"": ""Explore"", ""title"": ""흔적 조사"", ""text"": ""찢긴 울타리 근처를 살펴보세요."", ""objective"": { ""locationName"": ""찢긴 울타리"" }, ""edges"": [{ ""to"": ""kill"", ""condition"": ""ObjectiveComplete"" }] },
                        { ""id"": ""kill"", ""type"": ""Kill"", ""title"": ""위협 제거"", ""text"": ""검은 늑대 새끼를 처치하세요."", ""objective"": { ""target"": ""black wolf pup"", ""count"": 1, ""min_level"": 1, ""max_level"": 5 }, ""edges"": [{ ""to"": ""return"", ""condition"": ""ObjectiveComplete"" }] },
                        { ""id"": ""return"", ""type"": ""ReturnToNpc"", ""title"": ""보고"", ""text"": ""Brother Penric에게 돌아가세요."", ""edges"": [{ ""to"": ""choice"", ""condition"": ""ObjectiveComplete"" }] },
                        { ""id"": ""choice"", ""type"": ""Choice"", ""title"": ""결정"", ""text"": ""어떻게 마무리하시겠습니까?"", ""choices"": [{ ""id"": ""safe"", ""label"": ""마을 안전"", ""text"": ""마을 안전을 우선한다."" }], ""edges"": [{ ""to"": ""complete"", ""condition"": ""ChoiceSelected"", ""value"": ""safe"" }] },
                        { ""id"": ""complete"", ""type"": ""Complete"", ""title"": ""완료"", ""text"": ""고맙습니다."" }
                    ]
                }
            }";

            DynamicQuestDefinition quest = DynamicQuestRuntimeService.ParseLlmQuestForTest("seed-npc-1", "Brother Penric", 1, json);
            DynamicQuestResult result = DynamicQuestRuntimeService.Instance.AddQuest(quest);
            DynamicQuestObjective explore = quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Explore).Objective;

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True);
                Assert.That(explore.LocationName, Is.EqualTo("찢긴 울타리"));
                Assert.That(explore.RegionId, Is.EqualTo(1));
                Assert.That(explore.X, Is.GreaterThan(0));
                Assert.That(explore.Y, Is.GreaterThan(0));
                Assert.That(explore.Radius, Is.EqualTo(450));
            });
        }

        [Test]
        public void ParseLlmQuestForTest_RejectsServerOwnedExploreCoordinates()
        {
            const string json = @"{
                ""title"": ""위험한 좌표"",
                ""offer"": ""도와주세요."",
                ""progress"": ""진행 중입니다."",
                ""finish"": ""끝났습니다."",
                ""target"": ""black wolf pup"",
                ""graph"": {
                    ""start"": ""explore"",
                    ""nodes"": [
                        { ""id"": ""explore"", ""type"": ""Explore"", ""title"": ""좌표"", ""text"": ""이동하세요."", ""objective"": { ""locationName"": ""임의 지점"", ""x"": 500000 }, ""edges"": [{ ""to"": ""complete"", ""condition"": ""ObjectiveComplete"" }] },
                        { ""id"": ""complete"", ""type"": ""Complete"", ""title"": ""완료"" }
                    ]
                }
            }";

            InvalidOperationException ex = Assert.Throws<InvalidOperationException>(() =>
                DynamicQuestRuntimeService.ParseLlmQuestForTest("seed-npc-1", "Brother Penric", 1, json));

            Assert.That(ex.Message, Does.Contain("server-owned"));
        }

        [Test]
        public void ParseLlmQuestForTest_RejectsForbiddenFieldInsideGraph()
        {
            const string json = @"{
                ""title"": ""위험한 초안"",
                ""offer"": ""도와주세요."",
                ""target"": ""black wolf pup"",
                ""graph"": {
                    ""start"": ""talk"",
                    ""nodes"": [
                        { ""id"": ""talk"", ""type"": ""Talk"", ""objective"": { ""sql"": ""drop table"" }, ""edges"": [{ ""to"": ""complete"", ""condition"": ""ObjectiveComplete"" }] },
                        { ""id"": ""complete"", ""type"": ""Complete"" }
                    ]
                }
            }";

            InvalidOperationException ex = Assert.Throws<InvalidOperationException>(() =>
                DynamicQuestRuntimeService.ParseLlmQuestForTest("seed-npc-1", "Brother Penric", 1, json));

            Assert.That(ex.Message, Does.Contain("forbidden field"));
        }

        [Test]
        public void ParseLlmQuestForTest_AcceptsAllowlistedWorldSignalEdge()
        {
            const string json = @"{
                ""title"": ""자라난 위협"",
                ""offer"": ""숲에 우두머리의 기척이 있습니다."",
                ""progress"": ""우두머리의 움직임을 기다려야 합니다."",
                ""finish"": ""위협이 사라졌군요."",
                ""target"": ""black wolf pup"",
                ""graph"": {
                    ""start"": ""talk"",
                    ""nodes"": [
                        { ""id"": ""talk"", ""type"": ""Talk"", ""title"": ""불길한 소문"", ""text"": ""주민들이 우두머리 이야기를 합니다."", ""edges"": [{ ""to"": ""wait"", ""condition"": ""ObjectiveComplete"" }] },
                        { ""id"": ""wait"", ""type"": ""Talk"", ""title"": ""정세 대기"", ""text"": ""성장한 몬스터가 쓰러지기를 기다립니다."", ""edges"": [{ ""to"": ""complete"", ""condition"": ""WorldSignal"", ""value"": ""mob-growth:killed:boss"" }] },
                        { ""id"": ""complete"", ""type"": ""Complete"", ""title"": ""완료"", ""text"": ""마을이 안정을 되찾았습니다."" }
                    ]
                }
            }";

            DynamicQuestDefinition quest = DynamicQuestRuntimeService.ParseLlmQuestForTest("seed-npc-1", "Brother Penric", 1, json);
            DynamicQuestResult result = DynamicQuestRuntimeService.Instance.AddQuest(quest);
            DynamicQuestNode wait = quest.Nodes.Single(node => node.Id == "wait");
            DynamicQuestEdge edge = wait.Edges.Single(edge => edge.Condition == DynamicQuestEdgeCondition.WorldSignal);
            DynamicQuestEdge timeout = wait.Edges.Single(edge => edge.Condition == DynamicQuestEdgeCondition.TimedOut);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True);
                Assert.That(edge.Condition, Is.EqualTo(DynamicQuestEdgeCondition.WorldSignal));
                Assert.That(edge.ConditionValue, Is.EqualTo("mob-growth:killed:boss"));
                Assert.That(timeout.ConditionValue, Is.EqualTo(DynamicQuestWorldSignalPolicy.FallbackTimeoutSeconds));
            });
        }

        [Test]
        public void ParseLlmQuestForTest_RejectsUnsafeWorldSignalEdge()
        {
            const string json = @"{
                ""title"": ""위험한 신호"",
                ""offer"": ""도와주세요."",
                ""progress"": ""진행 중입니다."",
                ""finish"": ""끝났습니다."",
                ""target"": ""black wolf pup"",
                ""graph"": {
                    ""start"": ""talk"",
                    ""nodes"": [
                        { ""id"": ""talk"", ""type"": ""Talk"", ""edges"": [{ ""to"": ""complete"", ""condition"": ""WorldSignal"", ""value"": ""spawn:dragon"" }] },
                        { ""id"": ""complete"", ""type"": ""Complete"" }
                    ]
                }
            }";

            InvalidOperationException ex = Assert.Throws<InvalidOperationException>(() =>
                DynamicQuestRuntimeService.ParseLlmQuestForTest("seed-npc-1", "Brother Penric", 1, json));

            Assert.That(ex.Message, Does.Contain("unsupported"));
        }

        [Test]
        public void ParseLlmQuestForTest_AcceptsRuntimeGraphEdgeConditions()
        {
            const string json = @"{
                ""title"": ""반응하는 사건"",
                ""offer"": ""도와주세요."",
                ""progress"": ""진행 중입니다."",
                ""finish"": ""끝났습니다."",
                ""target"": ""black wolf pup"",
                ""graph"": {
                    ""start"": ""talk"",
                    ""nodes"": [
                        { ""id"": ""talk"", ""type"": ""Talk"", ""edges"": [{ ""to"": ""wait"", ""condition"": ""Always"" }] },
                        { ""id"": ""wait"", ""type"": ""Talk"", ""edges"": [{ ""to"": ""party"", ""condition"": ""TimedOut"", ""value"": ""30"" }, { ""to"": ""failed"", ""condition"": ""PlayerDied"" }] },
                        { ""id"": ""party"", ""type"": ""Talk"", ""edges"": [{ ""to"": ""complete"", ""condition"": ""PartySizeAtLeast"", ""value"": ""3"" }] },
                        { ""id"": ""failed"", ""type"": ""Fail"" },
                        { ""id"": ""complete"", ""type"": ""Complete"" }
                    ]
                }
            }";

            DynamicQuestDefinition quest = DynamicQuestRuntimeService.ParseLlmQuestForTest("seed-npc-1", "Brother Penric", 1, json);

            Assert.That(quest.Nodes.SelectMany(node => node.Edges).Select(edge => edge.Condition), Does.Contain(DynamicQuestEdgeCondition.TimedOut));
            Assert.That(quest.Nodes.SelectMany(node => node.Edges).Select(edge => edge.Condition), Does.Contain(DynamicQuestEdgeCondition.PlayerDied));
            Assert.That(quest.Nodes.SelectMany(node => node.Edges).Select(edge => edge.Condition), Does.Contain(DynamicQuestEdgeCondition.PartySizeAtLeast));
        }

        private static GamePlayer CreateJournalTestPlayer(string name, out RecordingPacketLib recorder)
        {
            EnsureJournalTestGameServer();
            recorder = new RecordingPacketLib();
            GamePlayer player = GamePlayer.CreateTestableGamePlayer();
            player.Name = name;
            GameClient client = new(null)
            {
                Out = recorder.PacketLib
            };

            typeof(GamePlayer)
                .GetField("m_client", BindingFlags.Instance | BindingFlags.NonPublic)
                .SetValue(player, client);

            return player;
        }

        private static void EnsureJournalTestGameServer()
        {
            if (GameServer.Instance is JournalTestGameServer)
                return;

            GameServer.LoadTestDouble(new JournalTestGameServer(new EmptyObjectDatabase().Database));
        }

        private sealed class JournalTestGameServer : GameServer
        {
            public JournalTestGameServer(IObjectDatabase database)
                : base(new GameServerConfiguration())
            {
                m_database = database;
            }
        }

        private sealed class EmptyObjectDatabase
        {
            public EmptyObjectDatabase()
            {
                Database = DispatchProxy.Create<IObjectDatabase, EmptyObjectDatabaseProxy>();
            }

            public IObjectDatabase Database { get; }
        }

        private class EmptyObjectDatabaseProxy : DispatchProxy
        {
            protected override object Invoke(MethodInfo targetMethod, object[] args)
            {
                if (targetMethod.ReturnType == typeof(void))
                    return null;

                if (targetMethod.ReturnType == typeof(bool))
                    return true;

                if (targetMethod.ReturnType == typeof(int))
                    return 0;

                if (targetMethod.ReturnType == typeof(string))
                    return args != null && args.Length > 0 ? args[0] as string ?? string.Empty : string.Empty;

                if (targetMethod.ReturnType.IsGenericType &&
                    targetMethod.ReturnType.GetGenericTypeDefinition() == typeof(IList<>))
                {
                    Type listType = typeof(List<>).MakeGenericType(targetMethod.ReturnType.GetGenericArguments()[0]);
                    return Activator.CreateInstance(listType);
                }

                return targetMethod.ReturnType.IsValueType
                    ? Activator.CreateInstance(targetMethod.ReturnType)
                    : null;
            }
        }

        private sealed class RecordingPacketLib
        {
            public RecordingPacketLib()
            {
                PacketLib = DispatchProxy.Create<IPacketLib, RecordingPacketLibProxy>();
                ((RecordingPacketLibProxy)(object)PacketLib).Recorder = this;
            }

            public IPacketLib PacketLib { get; }
            public List<AbstractQuest> QuestUpdates { get; } = new();
            public List<byte> QuestRemoves { get; } = new();
            public List<string> Messages { get; } = new();
        }

        private class RecordingPacketLibProxy : DispatchProxy
        {
            public RecordingPacketLib Recorder { get; set; }

            protected override object Invoke(MethodInfo targetMethod, object[] args)
            {
                switch (targetMethod.Name)
                {
                    case nameof(IPacketLib.SendQuestUpdate):
                        Recorder.QuestUpdates.Add((AbstractQuest)args[0]);
                        break;
                    case nameof(IPacketLib.SendQuestRemove):
                        Recorder.QuestRemoves.Add((byte)args[0]);
                        break;
                    case nameof(IPacketLib.SendMessage):
                        Recorder.Messages.Add((string)args[0]);
                        break;
                }

                if (targetMethod.ReturnType == typeof(void))
                    return null;

                return targetMethod.ReturnType.IsValueType
                    ? Activator.CreateInstance(targetMethod.ReturnType)
                    : null;
            }
        }

        private static DynamicQuestDefinition LegacyQuest()
        {
            return new DynamicQuestDefinition
            {
                Id = "quest-legacy",
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
            };
        }

        private static DynamicQuestDefinition GraphQuest()
        {
            DynamicQuestDefinition quest = LegacyQuest();
            quest.Id = "quest-graph";
            quest.StartNodeId = "talk";
            quest.Nodes = new[]
            {
                new DynamicQuestNode
                {
                    Id = "talk",
                    Type = DynamicQuestNodeType.Talk,
                    Title = "부탁",
                    Text = "마을 주변의 흔적을 확인해 주세요.",
                    Objective = new DynamicQuestObjective
                    {
                        NpcInternalId = "seed-npc-1",
                        NpcName = "Brother Penric",
                        RegionId = 1
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge { ToNodeId = "kill", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
                    }
                },
                new DynamicQuestNode
                {
                    Id = "kill",
                    Type = DynamicQuestNodeType.Kill,
                    Title = "위협 제거",
                    Text = "검은 늑대 새끼를 처치하세요.",
                    Objective = new DynamicQuestObjective
                    {
                        TargetName = "black wolf pup",
                        TargetCount = 1,
                        MinLevel = 1,
                        MaxLevel = 5,
                        RegionId = 1
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge { ToNodeId = "return", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
                    }
                },
                new DynamicQuestNode
                {
                    Id = "return",
                    Type = DynamicQuestNodeType.ReturnToNpc,
                    Title = "보고",
                    Text = "Brother Penric에게 돌아가세요.",
                    Objective = new DynamicQuestObjective
                    {
                        NpcInternalId = "seed-npc-1",
                        NpcName = "Brother Penric",
                        RegionId = 1
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge { ToNodeId = "choice", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
                    }
                },
                new DynamicQuestNode
                {
                    Id = "choice",
                    Type = DynamicQuestNodeType.Choice,
                    Title = "결정",
                    Text = "어떻게 마무리하시겠습니까?",
                    Objective = new DynamicQuestObjective
                    {
                        Choices = new[]
                        {
                            new DynamicQuestChoice { Id = "safe", Label = "마을 안전을 우선한다", Text = "마을 안전을 우선한다.", Consequence = "마을은 즉각적인 안전을 얻었지만 더 먼 흔적은 남았다." },
                            new DynamicQuestChoice { Id = "followup", Label = "더 큰 위협을 추적한다", Text = "더 큰 위협을 추적한다.", Consequence = "다음 세계 신호를 기다리는 추적 기록이 열리고, 더 큰 위협의 꼬리를 잡았다." }
                        }
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "safe", Priority = 0 },
                        new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "followup", Priority = 1 }
                    }
                },
                new DynamicQuestNode
                {
                    Id = "complete",
                    Type = DynamicQuestNodeType.Complete,
                    Title = "완료",
                    Text = "고맙습니다."
                }
            };

            return quest;
        }

        private static DynamicQuestDefinition ExploreGraphQuest()
        {
            DynamicQuestDefinition quest = GraphQuest();
            quest.Id = "quest-explore";
            quest.Nodes = new[]
            {
                new DynamicQuestNode
                {
                    Id = "talk",
                    Type = DynamicQuestNodeType.Talk,
                    Title = "부탁",
                    Text = "마을 주변의 흔적을 확인해 주세요.",
                    Objective = new DynamicQuestObjective
                    {
                        NpcInternalId = "seed-npc-1",
                        NpcName = "Brother Penric",
                        RegionId = 1
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge { ToNodeId = "explore", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
                    }
                },
                new DynamicQuestNode
                {
                    Id = "explore",
                    Type = DynamicQuestNodeType.Explore,
                    Title = "흔적 조사",
                    Text = "찢긴 울타리 주변을 확인하세요.",
                    Objective = new DynamicQuestObjective
                    {
                        LocationName = "찢긴 울타리",
                        RegionId = 1,
                        X = 521000,
                        Y = 492000,
                        Z = 2954,
                        Radius = 450
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge { ToNodeId = "kill", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
                    }
                },
                quest.Nodes.Single(node => node.Id == "kill"),
                quest.Nodes.Single(node => node.Id == "return"),
                quest.Nodes.Single(node => node.Id == "choice"),
                quest.Nodes.Single(node => node.Id == "complete")
            };

            return quest;
        }

        private static DynamicQuestDefinition WorldSignalGraphQuest()
        {
            DynamicQuestDefinition quest = GraphQuest();
            quest.Id = "quest-signal";
            quest.StartNodeId = "wait_for_signal";
            quest.Nodes = new[]
            {
                new DynamicQuestNode
                {
                    Id = "wait_for_signal",
                    Type = DynamicQuestNodeType.Talk,
                    Title = "정세 대기",
                    Text = "늑대굴 정세가 바뀌기를 기다립니다.",
                    Objective = new DynamicQuestObjective
                    {
                        NpcInternalId = "seed-npc-1",
                        NpcName = "Brother Penric",
                        RegionId = 1
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge
                        {
                            ToNodeId = "return",
                            Condition = DynamicQuestEdgeCondition.WorldSignal,
                            ConditionValue = "region-entered:1"
                        }
                    }
                },
                quest.Nodes.Single(node => node.Id == "return"),
                quest.Nodes.Single(node => node.Id == "choice"),
                quest.Nodes.Single(node => node.Id == "complete")
            };

            return quest;
        }

        private static DynamicQuestDefinition ChoiceWorldSignalQuest()
        {
            DynamicQuestDefinition quest = GraphQuest();
            quest.Id = "quest-choice-signal";
            DynamicQuestNode choice = quest.Nodes.Single(node => node.Id == "choice");
            choice.Edges = new[]
            {
                new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "safe", Priority = 0 },
                new DynamicQuestEdge { ToNodeId = "observe_signal", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "followup", Priority = 1 }
            };

            DynamicQuestNode complete = quest.Nodes.Single(node => node.Id == "complete");
            quest.Nodes = quest.Nodes
                .Where(node => !string.Equals(node.Id, "complete", StringComparison.OrdinalIgnoreCase))
                .Concat(new[]
                {
                    new DynamicQuestNode
                    {
                        Id = "observe_signal",
                        Type = DynamicQuestNodeType.Explore,
                        Title = "성장 위협 관측",
                        Text = "성장한 위협이 쓰러지는지 지켜봅니다.",
                        Objective = new DynamicQuestObjective
                        {
                            LocationName = "성장 위협 흔적",
                            RegionId = 1,
                            X = 521000,
                            Y = 492000,
                            Z = 2954,
                            Radius = 450
                        },
                        Edges = new[]
                        {
                            new DynamicQuestEdge
                            {
                                ToNodeId = "complete",
                                Condition = DynamicQuestEdgeCondition.WorldSignal,
                                ConditionValue = "mob-growth:killed:region:1"
                            }
                        }
                    },
                    complete
                })
                .ToArray();

            return quest;
        }

        private static DynamicQuestDefinition NpcLessChoiceWorldSignalQuest()
        {
            DynamicQuestDefinition quest = ChoiceWorldSignalQuest();
            quest.Id = "quest-npc-less-choice-signal";
            quest.StartMode = DynamicQuestStartMode.AutoAccept;
            quest.StartNpcInternalId = string.Empty;
            quest.StartNpcName = string.Empty;
            quest.StartNodeId = "kill";

            DynamicQuestNode kill = quest.Nodes.Single(node => node.Id == "kill");
            kill.Edges = new[]
            {
                new DynamicQuestEdge { ToNodeId = "choice", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
            };
            quest.Nodes = new[]
            {
                kill,
                quest.Nodes.Single(node => node.Id == "choice"),
                quest.Nodes.Single(node => node.Id == "observe_signal"),
                quest.Nodes.Single(node => node.Id == "complete")
            };

            return quest;
        }

        private static DynamicQuestDefinition NpcLessItemAcquiredBranchQuest()
        {
            return new DynamicQuestDefinition
            {
                Id = "quest-item-acquired-branch",
                Title = "Dropped Clue",
                OfferText = "Something is hidden near the den.",
                ProgressText = "Search the creature for a clue.",
                FinishText = "The clue explains the disturbance.",
                StartMode = DynamicQuestStartMode.AutoAccept,
                StartRegionId = 100,
                TargetName = "young lynx",
                TargetCount = 1,
                MinLevel = 1,
                MaxLevel = 9,
                StartNodeId = "kill",
                Tags = new[] { "branch:item-acquired", "world-signal:item-acquired", "region:100" },
                Nodes = new[]
                {
                    new DynamicQuestNode
                    {
                        Id = "kill",
                        Type = DynamicQuestNodeType.Kill,
                        Title = "Find a clue",
                        Text = "Defeat a young lynx.",
                        Objective = new DynamicQuestObjective
                        {
                            TargetName = "young lynx",
                            TargetCount = 1,
                            MinLevel = 1,
                            MaxLevel = 2,
                            RegionId = 100
                        },
                        Edges = new[]
                        {
                            new DynamicQuestEdge { ToNodeId = "choice", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
                        }
                    },
                    new DynamicQuestNode
                    {
                        Id = "choice",
                        Type = DynamicQuestNodeType.Choice,
                        Title = "Read the clue",
                        Text = "Choose how to handle the clue.",
                        Objective = new DynamicQuestObjective
                        {
                            Choices = new[]
                            {
                                new DynamicQuestChoice { Id = "safe", Label = "Secure it", Text = "Keep the clue safe." },
                                new DynamicQuestChoice { Id = "followup", Label = "Study it", Text = "Study the clue." }
                            }
                        },
                        Edges = new[]
                        {
                            new DynamicQuestEdge { ToNodeId = "observe_signal", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "safe" },
                            new DynamicQuestEdge { ToNodeId = "observe_signal", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "followup" }
                        }
                    },
                    new DynamicQuestNode
                    {
                        Id = "observe_signal",
                        Type = DynamicQuestNodeType.Explore,
                        Title = "Confirm the clue",
                        Text = "Confirm that the clue was collected.",
                        Objective = new DynamicQuestObjective
                        {
                            LocationName = "young lynx trail",
                            RegionId = 100,
                            X = 1000,
                            Y = 1000,
                            Z = 0,
                            Radius = 450
                        },
                        Edges = new[]
                        {
                            new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.WorldSignal, ConditionValue = "item-acquired" }
                        }
                    },
                    new DynamicQuestNode
                    {
                        Id = "complete",
                        Type = DynamicQuestNodeType.Complete,
                        Title = "Complete",
                        Text = "The clue has been secured."
                    }
                }
            };
        }

        private static DynamicQuestDefinition WorldOfferQuest()
        {
            return new DynamicQuestDefinition
            {
                Id = "quest-world-offer",
                Title = "숲의 균열",
                OfferText = "숲 어딘가에서 이상한 기운이 밀려옵니다.",
                ProgressText = "기운의 흔적을 따라가세요.",
                FinishText = "균열의 기운이 잦아듭니다.",
                StartMode = DynamicQuestStartMode.WorldOffer,
                StartRegionId = 1,
                TargetName = "forest spiderling",
                TargetCount = 1,
                MinLevel = 1,
                MaxLevel = 5,
                StartNodeId = "explore",
                Nodes = new[]
                {
                    new DynamicQuestNode
                    {
                        Id = "explore",
                        Type = DynamicQuestNodeType.Explore,
                        Title = "기운 조사",
                        Text = "숲의 균열 흔적을 조사하세요.",
                        Objective = new DynamicQuestObjective
                        {
                            LocationName = "숲의 균열",
                            RegionId = 1,
                            X = 521000,
                            Y = 492000,
                            Z = 2954,
                            Radius = 450
                        },
                        Edges = new[] { new DynamicQuestEdge { ToNodeId = "kill", Condition = DynamicQuestEdgeCondition.ObjectiveComplete } }
                    },
                    new DynamicQuestNode
                    {
                        Id = "kill",
                        Type = DynamicQuestNodeType.Kill,
                        Title = "균열 정리",
                        Text = "균열 근처의 forest spiderling을 처치하세요.",
                        Objective = new DynamicQuestObjective
                        {
                            TargetName = "forest spiderling",
                            TargetCount = 1,
                            MinLevel = 1,
                            MaxLevel = 5,
                            RegionId = 1
                        },
                        Edges = new[] { new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ObjectiveComplete } }
                    },
                    new DynamicQuestNode
                    {
                        Id = "complete",
                        Type = DynamicQuestNodeType.Complete,
                        Title = "완료",
                        Text = "균열이 잠잠해졌습니다."
                    }
                }
            };
        }
    }
}
