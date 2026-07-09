using System;
using System.Linq;
using DOL.GS.ServerProperties;
using DOL.GS.WorldAI;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_DynamicQuestOperationalEvaluator
    {
        [SetUp]
        public void SetUp()
        {
            Properties.KDAOC_DYNAMIC_QUEST_ENABLED = true;
            Properties.KDAOC_DYNAMIC_QUEST_MAX_KILL_COUNT = 20;
            Properties.KDAOC_DYNAMIC_QUEST_MAX_ACTIVE_PER_NPC = 3;
            DynamicQuestRuntimeService.Instance.ClearAll();
        }

        [TearDown]
        public void TearDown()
        {
            DynamicQuestRuntimeService.Instance.ClearAll();
            Properties.KDAOC_DYNAMIC_QUEST_ENABLED = false;
        }

        [Test]
        public void Evaluate_FailsWhenTargetCountExceedsNearbyCluster()
        {
            DynamicQuestDefinition quest = KillQuest();
            quest.TargetCount = 5;
            quest.Nodes.Single(node => node.Id == "kill").Objective.TargetCount = 5;

            DynamicQuestEvaluationResult result = DynamicQuestOperationalEvaluator.Instance.Evaluate(
                quest,
                new DynamicQuestEvaluationContext
                {
                    RequireWorldBindings = true,
                    TargetNpc = SeedNpc("black wolf pup", "wolf-1", 1),
                    TargetClusterCount = 2
                });

            Assert.Multiple(() =>
            {
                Assert.That(result.Passed, Is.False);
                Assert.That(result.FailReasons, Does.Contain("target count exceeds nearby spawn cluster"));
                Assert.That(result.SuggestedFixes.Any(fix => fix.Contains("5에서 2", StringComparison.Ordinal)), Is.True);
            });
        }

        [Test]
        public void Evaluate_FailsStarterQuestWithUnsafeTargetLevel()
        {
            DynamicQuestDefinition quest = KillQuest();
            quest.MinLevel = 6;
            quest.MaxLevel = 8;
            quest.Tags = new[] { "starter" };

            DynamicQuestEvaluationResult result = DynamicQuestOperationalEvaluator.Instance.Evaluate(
                quest,
                new DynamicQuestEvaluationContext
                {
                    RequireWorldBindings = true,
                    TargetNpc = SeedNpc("veteran bogman grappler", "bogman-1", 6),
                    TargetClusterCount = 1
                });

            Assert.Multiple(() =>
            {
                Assert.That(result.Passed, Is.False);
                Assert.That(result.FailReasons, Does.Contain("starter quest target is above safe solo level"));
            });
        }

        [Test]
        public void AddQuest_RejectsRewardMultiplierAboveOperationalCap()
        {
            DynamicQuestDefinition quest = KillQuest();
            quest.Reward = new DynamicQuestRewardDefinition
            {
                XpMultiplier = 3.0,
                MoneyMultiplier = 1.0,
                StepBonusMultiplier = 0.25,
                PartyBonusMultiplier = 1.0
            };

            DynamicQuestResult result = DynamicQuestRuntimeService.Instance.AddQuest(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.False);
                Assert.That(result.Message, Does.Contain("운영 평가 실패"));
                Assert.That(result.Message, Does.Contain("reward multiplier exceeds policy cap"));
            });
        }

        [Test]
        public void AddQuest_AcceptsOperationallySafeQuest()
        {
            DynamicQuestResult result = DynamicQuestRuntimeService.Instance.AddQuest(KillQuest());

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest, Is.Not.Null);
            });
        }

        [Test]
        public void Evaluate_FailsWhenTargetLocationIsOutsideKnownZone()
        {
            DynamicQuestEvaluationResult result = DynamicQuestOperationalEvaluator.Instance.Evaluate(
                KillQuest(),
                new DynamicQuestEvaluationContext
                {
                    HasRouteAccessibility = true,
                    StartInKnownZone = true,
                    TargetInKnownZone = false,
                    SameZone = false
                });

            Assert.Multiple(() =>
            {
                Assert.That(result.Passed, Is.False);
                Assert.That(result.FailReasons, Does.Contain("target location is outside a known zone"));
                Assert.That(result.SuggestedFixes.Any(fix => fix.Contains("알려진 zone", StringComparison.Ordinal)), Is.True);
            });
        }

        [Test]
        public void Evaluate_FailsWhenCheckedNavmeshRouteIsNotFound()
        {
            DynamicQuestEvaluationResult result = DynamicQuestOperationalEvaluator.Instance.Evaluate(
                KillQuest(),
                new DynamicQuestEvaluationContext
                {
                    HasRouteAccessibility = true,
                    StartInKnownZone = true,
                    TargetInKnownZone = true,
                    SameZone = true,
                    NavmeshAvailable = true,
                    RouteChecked = true,
                    RouteFound = false,
                    RouteStatus = "PathNotFound"
                });

            Assert.Multiple(() =>
            {
                Assert.That(result.Passed, Is.False);
                Assert.That(result.FailReasons, Does.Contain("pathfinding did not find a traversable route"));
            });
        }

        [Test]
        public void Evaluate_WarnsButDoesNotFailWhenStartAndTargetAreInDifferentKnownZones()
        {
            DynamicQuestEvaluationResult result = DynamicQuestOperationalEvaluator.Instance.Evaluate(
                KillQuest(),
                new DynamicQuestEvaluationContext
                {
                    HasRouteAccessibility = true,
                    StartInKnownZone = true,
                    TargetInKnownZone = true,
                    SameZone = false
                });

            Assert.Multiple(() =>
            {
                Assert.That(result.Passed, Is.True);
                Assert.That(result.RouteScore, Is.EqualTo(85));
                Assert.That(result.Warnings, Does.Contain("start and target are in different zones; exact pathing was not checked"));
                Assert.That(result.SuggestedFixes.Any(fix => fix.Contains("같은 zone", StringComparison.Ordinal)), Is.True);
            });
        }

        [Test]
        public void Evaluate_EstimatesHigherRewardTierForLongerHarderQuest()
        {
            DynamicQuestDefinition simple = KillQuest();
            DynamicQuestEvaluationResult simpleResult = DynamicQuestOperationalEvaluator.Instance.Evaluate(
                simple,
                new DynamicQuestEvaluationContext
                {
                    TargetNpc = SeedNpc("black wolf pup", "wolf-1", 1),
                    TargetClusterCount = 1,
                    TargetDistance = 800
                });

            DynamicQuestDefinition harder = KillQuest();
            harder.TargetCount = 6;
            harder.MinLevel = 10;
            harder.MaxLevel = 14;
            harder.Tags = new[] { "realm:Albion", "group-recommended" };
            harder.Nodes = harder.Nodes.Concat(new[]
            {
                new DynamicQuestNode
                {
                    Id = "choice",
                    Type = DynamicQuestNodeType.Choice,
                    Title = "분기 선택",
                    Text = "다음 대응을 고르십시오.",
                    Objective = new DynamicQuestObjective
                    {
                        Choices = new[] { new DynamicQuestChoice { Id = "safe", Label = "안전", Text = "안전하게 마무리합니다." } }
                    },
                    Edges = new[] { new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "safe" } }
                }
            }).ToArray();
            harder.Nodes.Single(node => node.Id == "kill").Objective.TargetCount = 6;
            harder.Nodes.Single(node => node.Id == "kill").Edges = new[]
            {
                new DynamicQuestEdge { ToNodeId = "choice", Condition = DynamicQuestEdgeCondition.ObjectiveComplete }
            };

            DynamicQuestEvaluationResult hardResult = DynamicQuestOperationalEvaluator.Instance.Evaluate(
                harder,
                new DynamicQuestEvaluationContext
                {
                    TargetNpc = SeedNpc("black wolf pup", "wolf-2", 14),
                    TargetClusterCount = 6,
                    TargetDistance = 16000
                });

            Assert.Multiple(() =>
            {
                Assert.That(simpleResult.EstimatedPlayableSteps, Is.EqualTo(1));
                Assert.That(hardResult.EstimatedPlayableSteps, Is.GreaterThan(simpleResult.EstimatedPlayableSteps));
                Assert.That(hardResult.EstimatedMinutes, Is.GreaterThan(simpleResult.EstimatedMinutes));
                Assert.That(hardResult.RewardDifficultyIndex, Is.GreaterThan(simpleResult.RewardDifficultyIndex));
                Assert.That(hardResult.SuggestedRewardScale, Is.GreaterThan(simpleResult.SuggestedRewardScale));
                Assert.That(hardResult.RewardLengthTier, Is.Not.EqualTo(string.Empty));
                Assert.That(hardResult.SuggestedRewardTier, Is.Not.EqualTo(string.Empty));
            });
        }

        [Test]
        public void Evaluate_CinematicQuestRewardsStructuredSetPieceSignals()
        {
            DynamicQuestDefinition quest = KillQuest();
            quest.Tags = new[]
            {
                "realm:Albion",
                "story-cinematic",
                "scene-director",
                "story-archetype:witness-conspiracy",
                "story-arc:motive",
                "story-arc:conflict",
                "story-arc:reversal",
                "story-arc:consequence",
                "cinematic-actors:ambush_reveal:8",
                "cinematic-actors:defender_intercept:6",
                "cinematic-actors:scout_retreat:4",
                "cinematic-actors:ritual_interrupt:5"
            };
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"매복 병력이 모습을 드러내고 경비가 탈출 경로를 가로막습니다.\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"ambush_wave\",\"formation\":\"ambush\",\"actorCount\":8}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"경비가 탈출 경로를 가로막습니다.\",\"cinematicAction\":\"defender_intercept\",\"sceneRole\":\"escape_intercept\",\"formation\":\"line\",\"actorCount\":6,\"delayMs\":700}," +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"text\":\"망보던 자가 뒤로 물러납니다.\",\"cinematicAction\":\"scout_retreat\",\"sceneRole\":\"lookout_escape\",\"formation\":\"escape\",\"actorCount\":4,\"delayMs\":1200}," +
                "{\"nodeId\":\"choice\",\"trigger\":\"OnChoiceShown\",\"text\":\"목격자와 대치하고 성물 의식을 끊어야 합니다.\",\"cinematicAction\":\"ritual_interrupt\",\"sceneRole\":\"ritual_break\",\"formation\":\"ring\",\"actorCount\":5,\"delayMs\":1600}" +
                "]";
            quest.StoryNarrativeJson = "[" +
                "{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"숨긴 증언\"}," +
                "{\"nodeId\":\"explore\",\"sceneType\":\"Discovery\",\"title\":\"꺼진 불씨\"}," +
                "{\"nodeId\":\"kill\",\"sceneType\":\"Threat\",\"title\":\"매복\"}," +
                "{\"nodeId\":\"choice\",\"sceneType\":\"Choice\",\"title\":\"대치\"}," +
                "{\"nodeId\":\"complete\",\"sceneType\":\"Completion\",\"title\":\"남은 변화\"}" +
                "]";

            DynamicQuestEvaluationResult result = DynamicQuestOperationalEvaluator.Instance.Evaluate(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Passed, Is.True, string.Join(", ", result.FailReasons));
                Assert.That(result.CinematicScore, Is.EqualTo(100));
                Assert.That(result.Warnings.Any(warning => warning.Contains("cinematic quest", StringComparison.OrdinalIgnoreCase)), Is.False);
            });
        }

        [Test]
        public void Evaluate_CinematicIntentFailsWhenNarrativeArcOrderIsBroken()
        {
            DynamicQuestDefinition quest = KillQuest();
            quest.Tags = new[]
            {
                "realm:Albion",
                "story-cinematic",
                "scene-director",
                "story-archetype:witness-conspiracy",
                "story-arc:motive",
                "story-arc:conflict",
                "story-arc:reversal",
                "story-arc:consequence",
                "cinematic-actors:ambush_reveal:8",
                "cinematic-actors:defender_intercept:6",
                "cinematic-actors:scout_retreat:4",
                "cinematic-actors:ritual_interrupt:5"
            };
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"매복 병력이 모습을 드러내고 경비가 탈출 경로를 가로막습니다.\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"ambush_wave\",\"formation\":\"ambush\",\"actorCount\":8}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"경비가 탈출 경로를 가로막습니다.\",\"cinematicAction\":\"defender_intercept\",\"sceneRole\":\"escape_intercept\",\"formation\":\"line\",\"actorCount\":6,\"delayMs\":700}," +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"text\":\"망보던 자가 뒤로 물러납니다.\",\"cinematicAction\":\"scout_retreat\",\"sceneRole\":\"lookout_escape\",\"formation\":\"escape\",\"actorCount\":4,\"delayMs\":1200}," +
                "{\"nodeId\":\"choice\",\"trigger\":\"OnChoiceShown\",\"text\":\"목격자와 대치하고 성물 의식을 끊어야 합니다.\",\"cinematicAction\":\"ritual_interrupt\",\"sceneRole\":\"ritual_break\",\"formation\":\"ring\",\"actorCount\":5,\"delayMs\":1600}" +
                "]";
            quest.StoryNarrativeJson = "[" +
                "{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"숨긴 증언\"}," +
                "{\"nodeId\":\"kill\",\"sceneType\":\"Threat\",\"title\":\"너무 이른 매복\"}," +
                "{\"nodeId\":\"explore\",\"sceneType\":\"Discovery\",\"title\":\"뒤늦은 발견\"}," +
                "{\"nodeId\":\"choice\",\"sceneType\":\"Choice\",\"title\":\"대치\"}," +
                "{\"nodeId\":\"complete\",\"sceneType\":\"Completion\",\"title\":\"남은 변화\"}" +
                "]";

            DynamicQuestEvaluationResult result = DynamicQuestOperationalEvaluator.Instance.Evaluate(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Passed, Is.False);
                Assert.That(result.FailReasons, Does.Contain("cinematic narrative arc order is broken"));
                Assert.That(result.CinematicScore, Is.LessThan(100));
                Assert.That(result.Warnings, Does.Contain("cinematic quest narrative arc order is broken"));
                Assert.That(result.SuggestedFixes.Any(fix => fix.Contains("discovery -> conflict", StringComparison.Ordinal)), Is.True);
            });
        }

        [Test]
        public void Evaluate_FailsFollowupStoryEpisodeWithoutMemoryPrerequisite()
        {
            DynamicQuestDefinition quest = CinematicQuest();
            quest.Tags = quest.Tags
                .Concat(new[] { "story-chain:haunted-road", "story-episode:2/3" })
                .ToArray();

            DynamicQuestEvaluationResult result = DynamicQuestOperationalEvaluator.Instance.Evaluate(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Passed, Is.False);
                Assert.That(result.FailReasons, Does.Contain("follow-up story episode has no memory prerequisite"));
                Assert.That(result.Warnings, Does.Contain("follow-up story episode has no memory prerequisite"));
                Assert.That(result.SuggestedFixes.Any(fix => fix.Contains("requires-story-family", StringComparison.Ordinal)), Is.True);
            });
        }

        [Test]
        public void Evaluate_AllowsFollowupStoryEpisodeWithMemoryPrerequisite()
        {
            DynamicQuestDefinition quest = CinematicQuest();
            quest.Tags = quest.Tags
                .Concat(new[] { "story-chain:haunted-road", "story-episode:2/3", "requires-story-family:haunted-road-intro" })
                .ToArray();

            DynamicQuestEvaluationResult result = DynamicQuestOperationalEvaluator.Instance.Evaluate(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Passed, Is.True, string.Join(", ", result.FailReasons));
                Assert.That(result.FailReasons, Does.Not.Contain("follow-up story episode has no memory prerequisite"));
                Assert.That(result.Warnings, Does.Not.Contain("follow-up story episode has no memory prerequisite"));
            });
        }

        [Test]
        public void Evaluate_PresentationSetPiecesWithoutTagsStillUseCinematicGate()
        {
            DynamicQuestDefinition quest = KillQuest();
            quest.Tags = new[] { "realm:Albion", "story-archetype:witness-conspiracy" };
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"매복 병력이 모습을 드러냅니다.\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"ambush_wave\",\"formation\":\"ambush\",\"actorCount\":8}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"경비가 탈출로를 막습니다.\",\"cinematicAction\":\"defender_intercept\",\"sceneRole\":\"escape_intercept\",\"formation\":\"line\",\"actorCount\":6}," +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"text\":\"정찰병이 물러납니다.\",\"cinematicAction\":\"scout_retreat\",\"sceneRole\":\"lookout_escape\",\"formation\":\"escape\",\"actorCount\":4}" +
                "]";

            DynamicQuestEvaluationResult result = DynamicQuestOperationalEvaluator.Instance.Evaluate(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Passed, Is.False);
                Assert.That(result.FailReasons, Does.Contain("cinematic structure score is below 70"));
                Assert.That(result.Warnings, Does.Contain("cinematic quest has no scene director tag"));
            });
        }

        [Test]
        public void Evaluate_CinematicIntentWarnsWhenSetPieceStructureIsMissing()
        {
            DynamicQuestDefinition quest = KillQuest();
            quest.Tags = new[] { "realm:Albion", "story-cinematic" };
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"근처 위협을 처리합니다.\"}" +
                "]";

            DynamicQuestEvaluationResult result = DynamicQuestOperationalEvaluator.Instance.Evaluate(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Passed, Is.False);
                Assert.That(result.CinematicScore, Is.LessThan(60));
                Assert.That(result.FailReasons, Does.Contain("cinematic structure score is below 70"));
                Assert.That(result.Warnings, Does.Contain("cinematic quest has no scene director tag"));
                Assert.That(result.Warnings, Does.Contain("cinematic quest has too few staged set-piece signals"));
                Assert.That(result.Warnings, Does.Contain("cinematic quest has no actor-count staging tags"));
                Assert.That(result.SuggestedFixes.Any(fix => fix.Contains("scene-director", StringComparison.Ordinal)), Is.True);
            });
        }

        [Test]
        public void Evaluate_CinematicIntentWarnsWhenSceneRolesAreNotVaried()
        {
            DynamicQuestDefinition quest = KillQuest();
            quest.Tags = new[] { "realm:Albion", "story-cinematic", "scene-director", "story-archetype:witness-conspiracy", "story-arc:motive", "story-arc:conflict", "story-arc:reversal", "story-arc:consequence" };
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"매복 병력이 드러납니다.\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"repeated\",\"formation\":\"ambush\",\"actorCount\":8}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"경비가 길을 막습니다.\",\"cinematicAction\":\"defender_intercept\",\"sceneRole\":\"repeated\",\"formation\":\"line\",\"actorCount\":6,\"delayMs\":700}," +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"text\":\"망보던 자가 후퇴합니다.\",\"cinematicAction\":\"scout_retreat\",\"sceneRole\":\"repeated\",\"formation\":\"escape\",\"actorCount\":4,\"delayMs\":1200}" +
                "]";
            quest.StoryNarrativeJson = "[" +
                "{\"nodeId\":\"talk\",\"sceneType\":\"Intro\"}," +
                "{\"nodeId\":\"explore\",\"sceneType\":\"Discovery\"}," +
                "{\"nodeId\":\"kill\",\"sceneType\":\"Threat\"}," +
                "{\"nodeId\":\"choice\",\"sceneType\":\"Choice\"}," +
                "{\"nodeId\":\"complete\",\"sceneType\":\"Completion\"}" +
                "]";

            DynamicQuestEvaluationResult result = DynamicQuestOperationalEvaluator.Instance.Evaluate(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Passed, Is.True, string.Join(", ", result.FailReasons));
                Assert.That(result.CinematicScore, Is.LessThan(100));
                Assert.That(result.Warnings, Does.Contain("cinematic quest has too few executable staged beats"));
                Assert.That(result.Warnings, Does.Contain("cinematic quest has low scene role variety"));
            });
        }

        [Test]
        public void Evaluate_CinematicIntentWarnsWhenNarrativeArcIsMissing()
        {
            DynamicQuestDefinition quest = KillQuest();
            quest.Tags = new[]
            {
                "realm:Albion",
                "story-cinematic",
                "scene-director",
                "cinematic-actors:ambush_reveal:8",
                "cinematic-actors:defender_intercept:6",
                "cinematic-actors:scout_retreat:4",
                "cinematic-actors:ritual_interrupt:5"
            };
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"매복 병력이 모습을 드러냅니다.\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"ambush_wave\",\"formation\":\"ambush\",\"actorCount\":8}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"경비가 길을 막습니다.\",\"cinematicAction\":\"defender_intercept\",\"sceneRole\":\"escape_intercept\",\"formation\":\"line\",\"actorCount\":6,\"delayMs\":700}," +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"text\":\"망보던 자가 후퇴합니다.\",\"cinematicAction\":\"scout_retreat\",\"sceneRole\":\"lookout_escape\",\"formation\":\"escape\",\"actorCount\":4,\"delayMs\":1200}," +
                "{\"nodeId\":\"choice\",\"trigger\":\"OnChoiceShown\",\"text\":\"의식이 흔들립니다.\",\"cinematicAction\":\"ritual_interrupt\",\"sceneRole\":\"ritual_break\",\"formation\":\"ring\",\"actorCount\":5,\"delayMs\":1600}" +
                "]";

            DynamicQuestEvaluationResult result = DynamicQuestOperationalEvaluator.Instance.Evaluate(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Passed, Is.False);
                Assert.That(result.CinematicScore, Is.LessThan(70));
                Assert.That(result.FailReasons, Does.Contain("cinematic structure score is below 70"));
                Assert.That(result.Warnings, Does.Contain("cinematic quest has no story archetype tag"));
                Assert.That(result.Warnings, Does.Contain("cinematic quest has weak narrative arc coverage"));
                Assert.That(result.Warnings, Does.Contain("cinematic quest has no visible consequence beat"));
            });
        }

        [Test]
        public void Evaluate_CinematicIntentWarnsWhenActionPhasesAreNotVaried()
        {
            DynamicQuestDefinition quest = KillQuest();
            quest.Tags = new[]
            {
                "realm:Albion",
                "story-cinematic",
                "scene-director",
                "story-archetype:witness-conspiracy",
                "story-arc:motive",
                "story-arc:conflict",
                "story-arc:reversal",
                "story-arc:consequence",
                "cinematic-actors:ambush_reveal:8",
                "cinematic-actors:combat_stance:6",
                "cinematic-actors:threat_standoff:6"
            };
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"매복 병력이 모습을 드러냅니다.\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"ambush_wave\",\"formation\":\"ambush\",\"actorCount\":8}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"전투원들이 반원으로 자세를 낮춥니다.\",\"cinematicAction\":\"combat_stance\",\"sceneRole\":\"counterline\",\"formation\":\"ambush\",\"actorCount\":6,\"delayMs\":700}," +
                "{\"nodeId\":\"choice\",\"trigger\":\"OnChoiceShown\",\"text\":\"위협과 대치합니다.\",\"cinematicAction\":\"threat_standoff\",\"sceneRole\":\"choice_confrontation\",\"formation\":\"ambush\",\"actorCount\":6,\"delayMs\":1200}," +
                "{\"nodeId\":\"complete\",\"trigger\":\"OnComplete\",\"text\":\"마지막 전투 흔적을 확인합니다.\",\"cinematicAction\":\"combat_stance\",\"sceneRole\":\"aftermath_watch\",\"formation\":\"ambush\",\"actorCount\":4,\"delayMs\":1600}" +
                "]";
            quest.StoryNarrativeJson = "[" +
                "{\"nodeId\":\"talk\",\"sceneType\":\"Intro\"}," +
                "{\"nodeId\":\"explore\",\"sceneType\":\"Discovery\"}," +
                "{\"nodeId\":\"kill\",\"sceneType\":\"Threat\"}," +
                "{\"nodeId\":\"choice\",\"sceneType\":\"Choice\"}," +
                "{\"nodeId\":\"complete\",\"sceneType\":\"Completion\"}" +
                "]";

            DynamicQuestEvaluationResult result = DynamicQuestOperationalEvaluator.Instance.Evaluate(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Passed, Is.True, string.Join(", ", result.FailReasons));
                Assert.That(result.CinematicScore, Is.LessThan(100));
                Assert.That(result.Warnings, Does.Contain("cinematic quest has low action phase variety"));
            });
        }

        [Test]
        public void Evaluate_CinematicIntentFailsWhenTotalActorBudgetIsTooLarge()
        {
            DynamicQuestDefinition quest = KillQuest();
            quest.Tags = new[]
            {
                "realm:Albion",
                "story-cinematic",
                "scene-director",
                "story-archetype:witness-conspiracy",
                "story-arc:motive",
                "story-arc:conflict",
                "story-arc:reversal",
                "story-arc:consequence",
                "cinematic-actors:ambush_reveal:100",
                "cinematic-actors:defender_intercept:100",
                "cinematic-actors:scout_retreat:100",
                "cinematic-actors:ritual_interrupt:100"
            };
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"talk\",\"trigger\":\"OnAccept\",\"text\":\"증인이 길을 가리킵니다.\",\"cinematicAction\":\"witness_point\",\"sceneRole\":\"witness\",\"formation\":\"escort\",\"actorCount\":100}," +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"text\":\"정찰대가 빠집니다.\",\"cinematicAction\":\"scout_retreat\",\"sceneRole\":\"scout_escape\",\"formation\":\"escape\",\"actorCount\":100,\"delayMs\":600}," +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"text\":\"차단선이 들어옵니다.\",\"cinematicAction\":\"defender_intercept\",\"sceneRole\":\"route_block\",\"formation\":\"line\",\"actorCount\":100,\"delayMs\":900}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"매복대가 드러납니다.\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"ambush_wave\",\"formation\":\"ambush\",\"actorCount\":100,\"delayMs\":1200}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"반격 전열이 섭니다.\",\"cinematicAction\":\"combat_stance\",\"sceneRole\":\"counterline\",\"formation\":\"line\",\"actorCount\":100,\"delayMs\":1500}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"의식 표식이 끊깁니다.\",\"cinematicAction\":\"ritual_interrupt\",\"sceneRole\":\"ritual_break\",\"formation\":\"ring\",\"actorCount\":100,\"delayMs\":1800}," +
                "{\"nodeId\":\"choice\",\"trigger\":\"OnChoiceShown\",\"text\":\"대치선이 길을 막습니다.\",\"cinematicAction\":\"threat_standoff\",\"sceneRole\":\"choice_standoff\",\"formation\":\"line\",\"actorCount\":100,\"delayMs\":2100}," +
                "{\"nodeId\":\"choice\",\"trigger\":\"OnChoiceSelected\",\"text\":\"호위대가 전진합니다.\",\"cinematicAction\":\"guard_advance\",\"sceneRole\":\"choice_fallout\",\"formation\":\"escort\",\"actorCount\":100,\"delayMs\":2400}," +
                "{\"nodeId\":\"choice\",\"trigger\":\"OnChoiceSelected\",\"text\":\"방패선이 버팁니다.\",\"cinematicAction\":\"hold_ground\",\"sceneRole\":\"choice_hold\",\"formation\":\"line\",\"actorCount\":100,\"delayMs\":2700}," +
                "{\"nodeId\":\"return\",\"trigger\":\"OnNodeEnter\",\"text\":\"보고대가 물러납니다.\",\"cinematicAction\":\"fallback_guard\",\"sceneRole\":\"debrief\",\"formation\":\"escort\",\"actorCount\":100,\"delayMs\":3000}," +
                "{\"nodeId\":\"complete\",\"trigger\":\"OnComplete\",\"text\":\"증언대가 남습니다.\",\"cinematicAction\":\"witness_point\",\"sceneRole\":\"aftermath_witness\",\"formation\":\"escort\",\"actorCount\":100,\"delayMs\":3300}," +
                "{\"nodeId\":\"complete\",\"trigger\":\"OnComplete\",\"text\":\"마지막 전열이 정리됩니다.\",\"cinematicAction\":\"hold_ground\",\"sceneRole\":\"aftermath_hold\",\"formation\":\"line\",\"actorCount\":100,\"delayMs\":3600}," +
                "{\"nodeId\":\"complete\",\"trigger\":\"OnComplete\",\"text\":\"잔류 정찰대가 퇴각합니다.\",\"cinematicAction\":\"scout_retreat\",\"sceneRole\":\"aftermath_scout\",\"formation\":\"escape\",\"actorCount\":100,\"delayMs\":3900}" +
                "]";
            quest.StoryNarrativeJson = "[" +
                "{\"nodeId\":\"talk\",\"sceneType\":\"Intro\"}," +
                "{\"nodeId\":\"explore\",\"sceneType\":\"Discovery\"}," +
                "{\"nodeId\":\"kill\",\"sceneType\":\"Threat\"}," +
                "{\"nodeId\":\"choice\",\"sceneType\":\"Choice\"}," +
                "{\"nodeId\":\"complete\",\"sceneType\":\"Completion\"}" +
                "]";

            DynamicQuestEvaluationResult result = DynamicQuestOperationalEvaluator.Instance.Evaluate(quest);

            Assert.Multiple(() =>
            {
                Assert.That(result.Passed, Is.False);
                Assert.That(result.FailReasons, Does.Contain("cinematic total actor budget exceeds safety budget"));
                Assert.That(result.Warnings, Does.Contain("cinematic total actor budget is high"));
                Assert.That(result.Warnings, Does.Contain("cinematic quest has multiple hundred-actor set pieces"));
            });
        }

        private static DynamicQuestDefinition KillQuest()
        {
            return new DynamicQuestDefinition
            {
                Id = Guid.NewGuid().ToString("N"),
                Title = "숲의 위협",
                OfferText = "근처의 위협을 처리해 주시겠습니까?",
                ProgressText = "아직 위협이 남아 있습니다.",
                FinishText = "덕분에 길이 안전해졌습니다.",
                StartMode = DynamicQuestStartMode.WorldOffer,
                StartRegionId = 1,
                Realm = "Albion",
                TargetName = "black wolf pup",
                TargetCount = 1,
                MinLevel = 1,
                MaxLevel = 2,
                StartNodeId = "kill",
                Nodes = new[]
                {
                    new DynamicQuestNode
                    {
                        Id = "kill",
                        Type = DynamicQuestNodeType.Kill,
                        Title = "위협 제거",
                        Text = "black wolf pup을 처치하십시오.",
                        Objective = new DynamicQuestObjective
                        {
                            TargetName = "black wolf pup",
                            TargetCount = 1,
                            MinLevel = 1,
                            MaxLevel = 2
                        },
                        Edges = new[]
                        {
                            new DynamicQuestEdge
                            {
                                ToNodeId = "complete",
                                Condition = DynamicQuestEdgeCondition.ObjectiveComplete
                            }
                        }
                    },
                    new DynamicQuestNode
                    {
                        Id = "complete",
                        Type = DynamicQuestNodeType.Complete,
                        Title = "완료",
                        Text = "위협이 사라졌습니다."
                    }
                },
                Reward = new DynamicQuestRewardDefinition
                {
                    XpMultiplier = 1.0,
                    MoneyMultiplier = 1.0,
                    StepBonusMultiplier = 0.25,
                    PartyBonusMultiplier = 1.0
                },
                Tags = new[] { "realm:Albion" }
            };
        }

        private static DynamicQuestDefinition CinematicQuest()
        {
            DynamicQuestDefinition quest = KillQuest();
            quest.Tags = new[]
            {
                "realm:Albion",
                "story-cinematic",
                "scene-director",
                "story-archetype:witness-conspiracy",
                "story-arc:motive",
                "story-arc:conflict",
                "story-arc:reversal",
                "story-arc:consequence",
                "cinematic-actors:ambush_reveal:8",
                "cinematic-actors:defender_intercept:6",
                "cinematic-actors:scout_retreat:4",
                "cinematic-actors:ritual_interrupt:5"
            };
            quest.StoryPresentationJson = "[" +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"매복 병력이 모습을 드러내고 경비가 탈출 경로를 가로막습니다.\",\"cinematicAction\":\"ambush_reveal\",\"sceneRole\":\"ambush_wave\",\"formation\":\"ambush\",\"actorCount\":8}," +
                "{\"nodeId\":\"kill\",\"trigger\":\"OnKill\",\"text\":\"경비가 탈출 경로를 가로막습니다.\",\"cinematicAction\":\"defender_intercept\",\"sceneRole\":\"escape_intercept\",\"formation\":\"line\",\"actorCount\":6,\"delayMs\":700}," +
                "{\"nodeId\":\"explore\",\"trigger\":\"OnExplore\",\"text\":\"망보던 자가 뒤로 물러납니다.\",\"cinematicAction\":\"scout_retreat\",\"sceneRole\":\"lookout_escape\",\"formation\":\"escape\",\"actorCount\":4,\"delayMs\":1200}," +
                "{\"nodeId\":\"choice\",\"trigger\":\"OnChoiceShown\",\"text\":\"목격자와 대치하고 성물 의식을 끊어야 합니다.\",\"cinematicAction\":\"ritual_interrupt\",\"sceneRole\":\"ritual_break\",\"formation\":\"ring\",\"actorCount\":5,\"delayMs\":1600}" +
                "]";
            quest.StoryNarrativeJson = "[" +
                "{\"nodeId\":\"talk\",\"sceneType\":\"Intro\",\"title\":\"숨긴 증언\"}," +
                "{\"nodeId\":\"explore\",\"sceneType\":\"Discovery\",\"title\":\"꺼진 불씨\"}," +
                "{\"nodeId\":\"kill\",\"sceneType\":\"Threat\",\"title\":\"매복\"}," +
                "{\"nodeId\":\"choice\",\"sceneType\":\"Choice\",\"title\":\"대치\"}," +
                "{\"nodeId\":\"complete\",\"sceneType\":\"Completion\",\"title\":\"남은 변화\"}" +
                "]";
            return quest;
        }

        private static DynamicQuestSeedNpc SeedNpc(string name, string internalId, int level)
        {
            return new DynamicQuestSeedNpc
            {
                Name = name,
                InternalID = internalId,
                RegionId = 1,
                Level = level,
                X = 1000,
                Y = 1000,
                Z = 1000
            };
        }
    }
}
