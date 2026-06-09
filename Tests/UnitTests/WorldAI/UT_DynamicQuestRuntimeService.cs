using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using DOL.Database;
using DOL.GS.PacketHandler;
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
            DynamicQuestRuntimeService.Instance.ClearAll();
        }

        [TearDown]
        public void TearDown()
        {
            DynamicQuestRuntimeService.Instance.ClearAll();
            Properties.KDAOC_DYNAMIC_QUEST_ENABLED = false;
            Properties.KDAOC_DYNAMIC_QUEST_WORLD_REVISION = string.Empty;
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
                20);
            DynamicQuestProgressSnapshot progress = DynamicQuestRuntimeService.Instance.GetProgressSnapshot("DummyQuest001", "DummyQuest001", true);
            string[] eventTypes = timeline.Events.Select(item => item.EventType).ToArray();

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
                Assert.That(eventTypes, Does.Contain("quest_completed"));
                Assert.That(timeline.Events.Last().EventType, Is.EqualTo("quest_completed"));
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
                20);
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
                50);
            string[] beatDetails = timeline.Events
                .Where(evt => evt.EventType == "presentation_beat")
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
            });
        }

        [Test]
        public void TimelineSnapshot_ExposesPresentationBeatsAsReadOnlyObservation()
        {
            DynamicQuestDefinition quest = WorldOfferQuest();
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnAccept\",\"speaker\":\"System\",\"text\":\"낡은 지도 위로 숲의 균열이 희미하게 떠오른다.\",\"emotion\":\"hope\",\"emote\":\"Cheer\"}" +
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
            });
        }

        [Test]
        public void BuildNarrativeSceneMessageForTest_FormatsSceneForInGamePresentation()
        {
            DynamicQuestNarrativeScene scene = new()
            {
                Title = "수도원 길목의 경고",
                Body = "Brother Penric은 찢긴 짐가방을 내려놓고, 길목의 침묵이 너무 오래 이어졌다고 말합니다.",
                Mood = "urgent"
            };

            string message = DynamicQuestRuntimeService.BuildNarrativeSceneMessageForTest(scene);

            Assert.Multiple(() =>
            {
                Assert.That(message, Does.Contain("수도원 길목의 경고"));
                Assert.That(message, Does.Contain("찢긴 짐가방"));
                Assert.That(message, Does.Contain("분위기: urgent"));
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
            DynamicQuestTimelineSnapshot timeline = DynamicQuestRuntimeService.Instance.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true);
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
            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true);

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
            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true);
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
            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true);
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
            DynamicQuestTimelineSnapshot timeline = service.GetTimelineSnapshot("DummyQuest001", "Dummy Quest", true);

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
                            new DynamicQuestChoice { Id = "followup", Label = "더 큰 위협을 추적한다", Text = "더 큰 위협을 추적한다.", Consequence = "마을은 불안해하지만 더 큰 위협의 꼬리를 잡았다." }
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
                            new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "safe" },
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
