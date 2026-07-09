using System;
using System.Reflection;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using DOL.GS.ServerProperties;
using DOL.GS.WorldAI;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_DynamicQuestStoryService
    {
        [Test]
        public void TryGenerate_UsesFirstSuccessfulProviderAfterMainFailure()
        {
            DynamicQuestStoryService service = new(new IDynamicQuestStoryProvider[]
            {
                new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Fail("offline")),
                new FakeStoryProvider("secondary-local", DynamicQuestStoryGenerationResult.Ok(Story(), "secondary-local"), "local-gemma-test")
            });

            DynamicQuestStoryGenerationResult result = service.TryGenerate(Request());

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True);
                Assert.That(result.ProviderName, Is.EqualTo("secondary-local"));
                Assert.That(result.ModelName, Is.EqualTo("local-gemma-test"));
                Assert.That(result.Story.Title, Is.EqualTo("숲속의 작은 위협"));
            });
        }

        [Test]
        public void TryGenerate_SkipsSuccessfulProviderWhenQualityBelowConfiguredMinimum()
        {
            int previousMinimum = Properties.KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE;
            try
            {
                Properties.KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE = 75;
                DynamicQuestStoryService service = new(new IDynamicQuestStoryProvider[]
                {
                    new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Ok(new DynamicQuestStoryText
                    {
                        Title = "깨진 의뢰",
                        OfferText = "늑대.",
                        ProgressText = "가라.",
                        FinishText = "끝."
                    }, "main-local"), "weak-local"),
                    new FakeStoryProvider("gemini", DynamicQuestStoryGenerationResult.Ok(Story(), "gemini"), "gemini-3.5-flash")
                });

                DynamicQuestStoryGenerationResult result = service.TryGenerate(Request());

                Assert.Multiple(() =>
                {
                    Assert.That(result.Success, Is.True);
                    Assert.That(result.ProviderName, Is.EqualTo("gemini"));
                    Assert.That(result.ModelName, Is.EqualTo("gemini-3.5-flash"));
                    Assert.That(result.Story.QualityScore, Is.GreaterThanOrEqualTo(75));
                });
            }
            finally
            {
                Properties.KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE = previousMinimum;
            }
        }

        [Test]
        public void TryGenerate_RepairsAnchoredStoryWithoutNarrativeAndPresentation()
        {
            int previousMinimum = Properties.KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE;
            try
            {
                Properties.KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE = 50;
                DynamicQuestStoryService service = new(new IDynamicQuestStoryProvider[]
                {
                    new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Ok(BasicStoryWithoutPresentation(), "main-local"), "weak-local"),
                    new FakeStoryProvider("gemini", DynamicQuestStoryGenerationResult.Ok(Story(), "gemini"), "gemini-3.5-flash")
                });

                DynamicQuestStoryGenerationResult result = service.TryGenerate(Request());

                Assert.Multiple(() =>
                {
                    Assert.That(result.Success, Is.True);
                    Assert.That(result.ProviderName, Is.EqualTo("main-local"));
                    Assert.That(result.Story.StructureRepaired, Is.True);
                    Assert.That(result.Story.NarrativeScenes, Has.Count.GreaterThanOrEqualTo(3));
                    Assert.That(result.Story.PresentationBeats, Has.Count.GreaterThanOrEqualTo(4));
                    Assert.That(result.Story.PresentationBeats.Select(beat => beat.CinematicAction).Where(action => !string.IsNullOrWhiteSpace(action)).Distinct(StringComparer.OrdinalIgnoreCase).Count(), Is.GreaterThanOrEqualTo(3));
                    Assert.That(result.Story.PresentationBeats.Select(beat => beat.SceneRole).Where(role => !string.IsNullOrWhiteSpace(role)).Distinct(StringComparer.OrdinalIgnoreCase).Count(), Is.GreaterThanOrEqualTo(3));
                    Assert.That(result.Story.PresentationBeats.Select(beat => beat.Formation).Where(formation => !string.IsNullOrWhiteSpace(formation)).Distinct(StringComparer.OrdinalIgnoreCase).Count(), Is.GreaterThanOrEqualTo(2));
                    Assert.That(result.Story.PresentationBeats.Any(beat => beat.ActorCount >= 4), Is.True);
                    Assert.That(result.Story.PresentationBeats.Any(beat => beat.DelayMs > 0), Is.True);
                    Assert.That(result.Story.Quality.Reasons, Does.Contain("story_structure_repaired"));
                    Assert.That(result.Story.QualityScore, Is.GreaterThanOrEqualTo(75));
                });
            }
            finally
            {
                Properties.KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE = previousMinimum;
            }
        }

        [Test]
        public void TryGenerate_RepairsSafeGenericScaffoldWithLocalAnchors()
        {
            int previousMinimum = Properties.KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE;
            try
            {
                Properties.KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE = 50;
                DynamicQuestStoryService service = new(new IDynamicQuestStoryProvider[]
                {
                    new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Ok(GenericScaffoldStory(), "main-local"), "weak-local"),
                    new FakeStoryProvider("gemini", DynamicQuestStoryGenerationResult.Ok(Story(), "gemini"), "gemini-3.5-flash")
                });

                DynamicQuestStoryGenerationResult result = service.TryGenerate(Request());

                Assert.Multiple(() =>
                {
                    Assert.That(result.Success, Is.True);
                    Assert.That(result.ProviderName, Is.EqualTo("main-local"));
                    Assert.That(result.Story.Quality.Reasons, Does.Not.Contain("generic_scaffold"));
                    Assert.That(result.Story.Quality.Reasons, Does.Not.Contain("missing_specific_local_anchor"));
                    Assert.That(result.Story.Quality.Reasons, Does.Contain("story_structure_repaired"));
                    Assert.That(result.Story.OfferText, Does.Contain("{{start_npc}}"));
                    Assert.That(result.Story.OfferText, Does.Contain("{{realm}}"));
                    Assert.That(result.Story.OfferText, Does.Contain("수도원"));
                    Assert.That(result.Story.QualityScore, Is.GreaterThanOrEqualTo(50));
                });
            }
            finally
            {
                Properties.KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE = previousMinimum;
            }
        }

        [Test]
        public void TryGenerate_RepairsUnknownRealmScaffoldWithGenericLocalAnchors()
        {
            int previousMinimum = Properties.KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE;
            try
            {
                Properties.KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE = 50;
                DynamicQuestStoryService service = new(new IDynamicQuestStoryProvider[]
                {
                    new FakeStoryProvider("main-local", DynamicQuestStoryGenerationResult.Ok(GenericScaffoldStory(), "main-local"), "weak-local")
                });

                DynamicQuestStoryGenerationResult result = service.TryGenerate(UnknownRealmRequest());

                Assert.Multiple(() =>
                {
                    Assert.That(result.Success, Is.True, result.Error);
                    Assert.That(result.ProviderName, Is.EqualTo("main-local"));
                    Assert.That(result.Story.Quality.Reasons, Does.Not.Contain("missing_specific_local_anchor"));
                    Assert.That(result.Story.OfferText, Does.Contain("마을 길목"));
                    Assert.That(result.Story.OfferText, Does.Contain("부러진 수레바퀴"));
                    Assert.That(result.Story.QualityScore, Is.GreaterThanOrEqualTo(50));
                });
            }
            finally
            {
                Properties.KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE = previousMinimum;
            }
        }

        [Test]
        public void ApplyStory_PlaceholderizesServerBoundTargetBeforeTemplateStorage()
        {
            DynamicQuestTemplate template = Template();
            DynamicQuestStoryText story = Story();

            DynamicQuestTemplate applied = DynamicQuestStoryService.ApplyStoryForTest(template, story, "main-local", "gemma-test");

            Assert.Multiple(() =>
            {
                Assert.That(applied.OfferText, Does.Contain("{{target}}"));
                Assert.That(applied.ProgressText, Does.Contain("{{target}}"));
                Assert.That(applied.FinishText, Does.Contain("{{target}}"));
                Assert.That(applied.OfferText, Does.Not.Contain("black wolf pup"));
                Assert.That(applied.Tags, Does.Contain("llm-story"));
                Assert.That(applied.Tags, Does.Contain("llm-provider:main-local"));
                Assert.That(applied.Tags, Does.Contain("llm-model:gemma-test"));
                Assert.That(applied.StoryModel, Is.EqualTo("gemma-test"));
                Assert.That(applied.PreferredStartNpcInternalId, Is.EqualTo("start-npc-1"));
                Assert.That(applied.PreferredTargetNpcInternalId, Is.EqualTo("target-npc-1"));
            });
        }

        [Test]
        public void ApplyStory_StoresQualityNarrativeAndPresentationJson()
        {
            DynamicQuestTemplate template = Template();
            DynamicQuestStoryText story = Story();
            story.NarrativeScenes = new[]
            {
                new DynamicQuestNarrativeScene
                {
                    NodeId = "talk",
                    SceneType = "Intro",
                    Title = "숲의 숨죽임",
                    Body = "숲 가장자리의 울타리가 찢겼습니다.\n\n마을 사람들은 {{target}} 울음소리를 들었습니다.",
                    JournalEntry = "숲 가장자리에서 마을로 번지는 위협의 흔적을 들었다.",
                    Mood = "ominous",
                    RevealPolicy = "FirstSeenOnly"
                }
            };
            story.PresentationBeats = new[]
            {
                new DynamicQuestPresentationBeat
                {
                    NodeId = "talk",
                    Trigger = "OnNpcInteract",
                    Speaker = "StartNpc",
                    Text = "숲이 오늘은 숨을 죽인 것 같습니다.",
                    Emotion = "fear",
                    Emote = "Shiver"
                }
            };

            DynamicQuestTemplate applied = DynamicQuestStoryService.ApplyStoryForTest(template, story, "main-local", "gemma-test");

            Assert.Multiple(() =>
            {
                Assert.That(applied.StoryQualityJson, Does.Contain("totalScore"));
                Assert.That(applied.StoryNarrativeJson, Does.Contain("숲의 숨죽임"));
                Assert.That(applied.StoryPresentationJson, Does.Contain("Shiver"));
                Assert.That(applied.StoryQualityScore, Is.GreaterThan(0));
            });
        }

        [Test]
        public void ApplyStory_StoresStructureRepairedTag()
        {
            DynamicQuestTemplate template = Template();
            DynamicQuestStoryText story = Story();
            story.StructureRepaired = true;

            DynamicQuestTemplate applied = DynamicQuestStoryService.ApplyStoryForTest(template, story, "main-local", "gemma-test");

            Assert.That(applied.Tags, Does.Contain("story-structure-repaired"));
        }

        [Test]
        public void EvaluateQuality_ReturnsBreakdownForImmersiveStory()
        {
            DynamicQuestStoryText story = Story();
            story.NarrativeScenes = new[]
            {
                new DynamicQuestNarrativeScene
                {
                    NodeId = "talk",
                    SceneType = "Intro",
                    Title = "숲의 숨죽임",
                    Body = "해가 지자 숲 가장자리의 울타리가 한 번 더 찢겼습니다.\n\n마을 사람들은 {{target}}의 울음이 전보다 가까워졌다고 말합니다.",
                    JournalEntry = "Brother Penric은 숲 가장자리의 변화가 마을로 번질까 두려워했다.",
                    Mood = "ominous",
                    RevealPolicy = "FirstSeenOnly"
                }
            };
            story.PresentationBeats = new[]
            {
                new DynamicQuestPresentationBeat
                {
                    NodeId = "talk",
                    Trigger = "OnNpcInteract",
                    Speaker = "StartNpc",
                    Text = "저 숲이 오늘은 숨을 죽인 것 같군요.",
                    Emotion = "fear",
                    Emote = "Shiver"
                }
            };

            DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForTest(Request(), story);

            Assert.Multiple(() =>
            {
                Assert.That(quality.TotalScore, Is.GreaterThanOrEqualTo(80));
                Assert.That(quality.NarrativeScore, Is.GreaterThan(0));
                Assert.That(quality.PresentationScore, Is.GreaterThan(0));
                Assert.That(quality.Reasons, Does.Contain("narrative_scene"));
                Assert.That(quality.Reasons, Does.Contain("presentation_beat"));
            });
        }

        [Test]
        public void EvaluateQuality_DoesNotAwardFullNarrativeForSingleScene()
        {
            DynamicQuestStoryText story = Story();

            DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForTest(Request(), story);

            Assert.That(quality.NarrativeScore, Is.LessThan(12));
        }

        [Test]
        public void EvaluateQuality_DoesNotAwardFullPresentationForSingleBeat()
        {
            DynamicQuestStoryText story = Story();

            DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForTest(Request(), story);

            Assert.That(quality.PresentationScore, Is.LessThan(8));
        }

        [Test]
        public void EvaluateQuality_PenalizesGenericScaffoldStoryEvenWhenStructurallyComplete()
        {
            DynamicQuestStoryText story = new()
            {
                Title = "지역 분위기의 불길한 조짐",
                OfferText = "지역 분위기가 심상치 않습니다. {{target}}의 기운이 느껴지는 곳을 조사하여 {{target}}를 처단해 주십시오.",
                ProgressText = "{{target}}가 나타나 마을을 위협하고 있습니다. {{target}}를 1마리 더 물리쳐야 합니다.",
                FinishText = "모든 {{target}}를 소탕했습니다. 이제 지역은 다시 평온을 되찾았습니다.",
                NarrativeScenes = new[]
                {
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "talk",
                        SceneType = "Intro",
                        Title = "불안한 부탁",
                        Body = "지역 주민은 {{target}}의 흔적이 Albion 곳곳으로 번지고 있다고 말합니다. 아직 작은 소문처럼 들리지만, 방치하면 마을의 밤이 더 길어질 것입니다.",
                        JournalEntry = "지역 주민에게서 {{target}} 위협이 커지고 있다는 이야기를 들었다.",
                        Mood = "urgent",
                        RevealPolicy = "FirstSeenOnly"
                    },
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "explore",
                        SceneType = "Discovery",
                        Title = "흔적의 방향",
                        Body = "흙과 풀잎 사이에 남은 {{target}}의 흔적이 한 방향으로 이어집니다. 주변은 조용하지만, 그 조용함이 오히려 다음 싸움을 예고합니다.",
                        JournalEntry = "{{target}}의 흔적을 따라 위협의 중심에 가까워지고 있다.",
                        Mood = "ominous",
                        RevealPolicy = "FirstSeenOnly"
                    },
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "complete",
                        SceneType = "Completion",
                        Title = "잠잠해진 길목",
                        Body = "{{target}} 위협을 꺾자 긴장으로 굳어 있던 길목이 조금씩 풀립니다. 이 변화가 오래가려면, 다음 징후도 놓치지 않아야 합니다.",
                        JournalEntry = "{{target}} 위협을 제압했고 지역은 잠시 안정을 되찾았다.",
                        Mood = "relieved",
                        RevealPolicy = "FirstSeenOnly"
                    }
                },
                PresentationBeats = new[]
                {
                    new DynamicQuestPresentationBeat
                    {
                        NodeId = "talk",
                        Trigger = "OnNpcInteract",
                        Speaker = "System",
                        Text = "{{target}} 소식 때문에 모두가 조용히 문을 걸어 잠그고 있습니다.",
                        Emotion = "fear",
                        Emote = "Shiver"
                    },
                    new DynamicQuestPresentationBeat
                    {
                        NodeId = "complete",
                        Trigger = "OnComplete",
                        Speaker = "System",
                        Text = "이제야 숨을 쉴 수 있겠군요. 고맙습니다.",
                        Emotion = "gratitude",
                        Emote = "Bow"
                    }
                }
            };

            DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForTest(Request(), story);

            Assert.Multiple(() =>
            {
                Assert.That(quality.TotalScore, Is.LessThan(75));
                Assert.That(quality.DiversityScore, Is.LessThanOrEqualTo(2));
                Assert.That(quality.ImmersionScore, Is.LessThan(10));
                Assert.That(quality.Reasons, Does.Contain("generic_scaffold"));
                Assert.That(quality.Reasons, Does.Contain("missing_specific_local_anchor"));
            });
        }

        [Test]
        public void EvaluateQuality_CapsScoreForRepeatedTargetPhrasingWithoutBlockingCache()
        {
            DynamicQuestStoryText story = new()
            {
                Title = "숲길에 남은 같은 발자국",
                OfferText = "{{start_npc}}은 {{realm}} 수도원 울타리의 찢긴 끈을 보여 주며 {{target}} 위협을 막아 달라고 말했다.",
                ProgressText = "{{realm}} 수도원 울타리 주변에서 {{target}} 흔적과 {{target}} 울음이 같은 길로 이어진다.",
                FinishText = "{{target}} 위협이 꺾이자 {{start_npc}}은 {{realm}} 길목의 횃불을 다시 세웠다.",
                NarrativeScenes = new[]
                {
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "talk",
                        SceneType = "Intro",
                        Title = "찢긴 끈의 증언",
                        Body = "{{start_npc}}은 {{realm}} 수도원 울타리 앞의 젖은 흙을 짚었다. {{target}} 발자국은 끊기지 않았고, {{target}} 냄새는 밤새 같은 문턱에 머물렀다.",
                        JournalEntry = "{{start_npc}}에게서 {{realm}} 수도원 울타리 주변의 {{target}} 위협을 확인해 달라는 부탁을 받았다.",
                        Mood = "ominous",
                        RevealPolicy = "FirstSeenOnly"
                    },
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "explore",
                        SceneType = "Discovery",
                        Title = "돌아온 흔적",
                        Body = "성벽 그림자와 수도원 종소리 사이로 {{target}} 흔적이 되돌아온다. 길목의 사람들은 {{target}} 이름을 낮게 부르며 문을 닫는다.",
                        JournalEntry = "{{realm}} 길목에서 {{target}}가 같은 길을 반복해 지나간 흔적을 찾았다.",
                        Mood = "urgent",
                        RevealPolicy = "FirstSeenOnly"
                    },
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "complete",
                        SceneType = "Completion",
                        Title = "다시 선 횃불",
                        Body = "{{target}} 위협이 물러나자 울타리 옆 횃불이 다시 곧게 섰다. {{realm}}의 밤길은 아직 조심스럽지만, 오늘의 공포는 한 번 꺾였다.",
                        JournalEntry = "{{target}} 위협을 제압했고 {{realm}} 수도원 울타리 주변의 길이 다시 열렸다.",
                        Mood = "relieved",
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
                        Text = "저 울타리를 보십시오. {{target}}가 같은 자리로 돌아왔습니다.",
                        Emotion = "fear",
                        Emote = "Shiver"
                    },
                    new DynamicQuestPresentationBeat
                    {
                        NodeId = "explore",
                        Trigger = "OnExplore",
                        Speaker = "Companion",
                        Text = "{{target}} 흔적이 수도원 종소리 쪽으로 이어집니다.",
                        Emotion = "suspicion",
                        Emote = "Point"
                    },
                    new DynamicQuestPresentationBeat
                    {
                        NodeId = "complete",
                        Trigger = "OnComplete",
                        Speaker = "StartNpc",
                        Text = "오늘 밤은 사람들이 서로의 이름을 부르며 돌아올 수 있겠군요.",
                        Emotion = "gratitude",
                        Emote = "Bow"
                    }
                }
            };

            DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForTest(Request(), story);

            Assert.Multiple(() =>
            {
                Assert.That(quality.TotalScore, Is.EqualTo(94));
                Assert.That(quality.DiversityScore, Is.EqualTo(5));
                Assert.That(quality.Reasons, Does.Contain("generic_repetition"));
                Assert.That(DynamicQuestStoryService.IsStoryQualityAcceptableForCache(Request(), story), Is.True);
            });
        }

        [Test]
        public void IsStoryQualityAcceptableForCache_RejectsHighScoreStoryWithoutJournalReadyScenes()
        {
            DynamicQuestStoryText story = CacheReadyStory();
            story.NarrativeScenes = story.NarrativeScenes
                .Select(scene => new DynamicQuestNarrativeScene
                {
                    NodeId = scene.NodeId,
                    SceneType = scene.SceneType,
                    Title = scene.Title,
                    Body = scene.Body,
                    JournalEntry = string.Empty,
                    Mood = scene.Mood,
                    RevealPolicy = scene.RevealPolicy
                })
                .ToArray();

            bool acceptable = DynamicQuestStoryService.IsStoryQualityAcceptableForCache(Request(), story);

            Assert.That(acceptable, Is.False);
        }

        [Test]
        public void IsStoryQualityAcceptableForCache_AcceptsJournalReadyCinematicStory()
        {
            DynamicQuestStoryText story = CacheReadyStory();

            bool acceptable = DynamicQuestStoryService.IsStoryQualityAcceptableForCache(Request(), story);

            Assert.That(acceptable, Is.True);
        }

        [Test]
        public void EvaluateQuality_PenalizesMechanicalObjectiveAndRewardCopy()
        {
            DynamicQuestStoryText story = new()
            {
                Title = "마을 길목의 위협: thidranki raider 처치",
                OfferText = "{{target}} 3마리 처치 시, 마을 길목에서 퀘스트 보상을 받으세요.",
                ProgressText = "현재 {{target}} 3마리 중 0마리 처치",
                FinishText = "마을 길목에서 {{target}} 3마리 처치 완료! 보상을 받으세요.",
                NarrativeScenes = new[]
                {
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "talk",
                        SceneType = "Intro",
                        Title = "마을 길목의 낮은 경고",
                        Body = "현장의 목격자는 마을 길목 근처의 젖은 흙을 살피며 {{target}}가 밤사이 울타리를 찢고 지나갔다고 말했다. 부러진 수레바퀴와 젖은 흙 사이에는 부러진 창대와 급히 끌린 발자국이 남아 있었다.",
                        JournalEntry = "마을 길목에서 {{target}} 위협을 확인했다.",
                        Mood = "urgent",
                        RevealPolicy = "FirstSeenOnly"
                    },
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "complete",
                        SceneType = "Completion",
                        Title = "길목의 침묵",
                        Body = "{{target}}가 쓰러지자 마을 길목의 횃불이 다시 켜졌다. 사람들은 문틈으로 밖을 살피며 조용히 안도의 숨을 내쉬었다.",
                        JournalEntry = "{{target}} 위협을 제압했고 길목의 불안이 가라앉았다.",
                        Mood = "relieved",
                        RevealPolicy = "FirstSeenOnly"
                    }
                },
                PresentationBeats = new[]
                {
                    new DynamicQuestPresentationBeat
                    {
                        NodeId = "talk",
                        Trigger = "OnNodeEnter",
                        Speaker = "System",
                        Text = "마을 길목 근처에 {{target}}가 지나간 자국과 급히 꺼진 횃불이 남아 있습니다.",
                        Emotion = "caution",
                        Emote = "Point"
                    },
                    new DynamicQuestPresentationBeat
                    {
                        NodeId = "complete",
                        Trigger = "OnComplete",
                        Speaker = "System",
                        Text = "{{target}} 처치 완료. 보상을 받으세요.",
                        Emotion = "gratitude",
                        Emote = "Bow"
                    }
                }
            };

            DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForTest(Request(), story);

            Assert.Multiple(() =>
            {
                Assert.That(quality.TotalScore, Is.LessThan(75));
                Assert.That(quality.SafetyScore, Is.EqualTo(0));
                Assert.That(quality.Reasons, Does.Contain("mechanical_objective_copy"));
                Assert.That(quality.Reasons, Does.Contain("system_speaker_overuse"));
            });
        }

        [Test]
        public void EvaluateQuality_RejectsSystemLocationExpressionsImmediately()
        {
            DynamicQuestStoryText story = Story();
            story.OfferText = "Midgard의 차가운 새벽비가 region 100 길목을 적실 때, Barkeep Nognar는 {{target}}이 nearby settlement 쪽으로 스며든다고 말했다.";
            story.ProgressText = "region 100의 돌우물 근처를 살피며 {{target}}을 제압해야 한다.";
            story.FinishText = "{{target}} 위협이 사라지자 nearby settlement로 번지던 불안이 멎었다.";
            story.NarrativeScenes = new[]
            {
                new DynamicQuestNarrativeScene
                {
                    NodeId = "talk",
                    SceneType = "Intro",
                    Title = "비 젖은 뒤뜰",
                    Body = "Barkeep Nognar는 region 100 여관 뒤편 장작더미 아래를 가리키며 {{target}}이 nearby settlement로 향했다고 말했다.",
                    JournalEntry = "region 100에서 {{target}} 흔적을 확인했다.",
                    Mood = "urgent",
                    RevealPolicy = "FirstSeenOnly"
                },
                new DynamicQuestNarrativeScene
                {
                    NodeId = "complete",
                    SceneType = "Completion",
                    Title = "멎은 소란",
                    Body = "{{target}}이 쓰러지자 장작더미 곁의 소란이 잦아들었다.",
                    JournalEntry = "{{target}} 위협을 막았다.",
                    Mood = "relieved",
                    RevealPolicy = "FirstSeenOnly"
                }
            };
            story.PresentationBeats = new[]
            {
                new DynamicQuestPresentationBeat
                {
                    NodeId = "talk",
                    Trigger = "OnNpcInteract",
                    Speaker = "StartNpc",
                    Text = "region 100 뒤뜰에서 자루 끄는 소리가 났소.",
                    Emotion = "urgency",
                    Emote = "Point"
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "complete",
                    Trigger = "OnComplete",
                    Speaker = "StartNpc",
                    Text = "nearby settlement 쪽 불안은 이제 잦아들었소.",
                    Emotion = "relief",
                    Emote = "Bow"
                }
            };

            DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForTest(Request(), story);

            Assert.Multiple(() =>
            {
                Assert.That(quality.TotalScore, Is.EqualTo(0));
                Assert.That(quality.SafetyScore, Is.EqualTo(0));
                Assert.That(quality.Reasons, Does.Contain("system_expression_leak"));
                Assert.That(quality.Reasons, Does.Contain("unsafe_story_text"));
            });
        }

        [Test]
        public void EvaluateQuality_RewardsSpecificNpcPlaceAndEmotionalDialogue()
        {
            DynamicQuestStoryText story = new()
            {
                Title = "{{start_npc}}의 젖은 담장 부탁",
                OfferText = "{{start_npc}}은 {{realm}} 수도원 담장 아래 젖은 흙과 찢긴 자루를 보여 주며 {{target}}가 아이들이 다니는 길목까지 내려왔다고 말했다.",
                ProgressText = "{{realm}} 수도원 종소리가 멎기 전, 성벽 그림자와 울타리 아래의 작은 발자국을 따라 {{target}}를 찾아 제압해야 한다.",
                FinishText = "{{target}} 위협이 사라지자 {{start_npc}}은 꺼진 횃불을 다시 세우며 {{realm}} 길목이 오늘 밤은 버틸 수 있겠다고 말했다.",
                NarrativeScenes = new[]
                {
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "talk",
                        SceneType = "Intro",
                        Title = "수도원 담장의 발자국",
                        Body = "{{start_npc}}은 {{realm}} 수도원 담장 아래 젖은 흙을 가리켰다. 작은 발자국과 찢긴 자루가 {{target}} 위협이 마을 길목까지 번지고 있음을 보여 주었다.",
                        JournalEntry = "{{start_npc}}에게서 {{realm}} 수도원 근처의 {{target}} 위협을 막아 달라는 부탁을 받았다.",
                        Mood = "urgent",
                        RevealPolicy = "FirstSeenOnly"
                    },
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "explore",
                        SceneType = "Discovery",
                        Title = "성벽 그림자의 흔적",
                        Body = "성벽 그림자 아래에는 꺼진 횃불과 부러진 울타리 조각이 남아 있었다. {{target}}의 흔적은 수도원 뒤 숲 가장자리로 이어졌다.",
                        JournalEntry = "성벽 그림자와 숲 가장자리 사이에서 {{target}} 흔적을 찾았다.",
                        Mood = "ominous",
                        RevealPolicy = "FirstSeenOnly"
                    },
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "complete",
                        SceneType = "Completion",
                        Title = "다시 켜진 횃불",
                        Body = "{{start_npc}}은 다시 켜진 횃불 앞에서 떨리는 손을 감추지 못했다. 그는 {{realm}} 아이들이 아침 종소리를 들으며 길을 건널 수 있게 되었다고 낮게 말했다.",
                        JournalEntry = "{{realm}} 수도원 길목의 {{target}} 위협을 제압했다.",
                        Mood = "relieved",
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
                        Text = "담장 아래 자국을 보십시오. 놈이 아이들 길목까지 내려왔습니다.",
                        Emotion = "fear",
                        Emote = "Point"
                    },
                    new DynamicQuestPresentationBeat
                    {
                        NodeId = "complete",
                        Trigger = "OnComplete",
                        Speaker = "StartNpc",
                        Text = "오늘 밤 종이 울릴 때, 사람들은 문을 잠그지 않아도 되겠군요.",
                        Emotion = "gratitude",
                        Emote = "Bow"
                    }
                }
            };

            DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForTest(Request(), story);

            Assert.Multiple(() =>
            {
                Assert.That(quality.TotalScore, Is.GreaterThanOrEqualTo(90));
                Assert.That(quality.SafetyScore, Is.EqualTo(15));
                Assert.That(quality.ImmersionScore, Is.GreaterThanOrEqualTo(12));
                Assert.That(quality.Reasons, Does.Not.Contain("mechanical_objective_copy"));
                Assert.That(quality.Reasons, Does.Not.Contain("system_speaker_overuse"));
            });
        }

        [Test]
        public void EvaluateQuality_RequiresConcreteLocalAnchorBeyondStartNpcName()
        {
            DynamicQuestStoryText story = Story();
            story.OfferText = "Brother Penric이 {{target}} 위협을 막아 달라고 부탁합니다.";
            story.ProgressText = "{{target}} 흔적을 따라가야 합니다.";
            story.FinishText = "{{target}} 위협을 제압했습니다.";
            story.NarrativeScenes = new[]
            {
                new DynamicQuestNarrativeScene
                {
                    NodeId = "talk",
                    SceneType = "Intro",
                    Title = "낮은 경고",
                    Body = "Brother Penric은 밤마다 들리는 울음이 전보다 가까워졌다고 말합니다. {{target}}를 방치하면 더 많은 사람이 길을 피하게 될 것입니다.",
                    JournalEntry = "Brother Penric에게서 {{target}} 위협을 막아 달라는 부탁을 받았다.",
                    Mood = "urgent",
                    RevealPolicy = "FirstSeenOnly"
                }
            };
            story.PresentationBeats = new[]
            {
                new DynamicQuestPresentationBeat
                {
                    NodeId = "talk",
                    Trigger = "OnNpcInteract",
                    Speaker = "StartNpc",
                    Text = "{{target}} 소식 때문에 사람들이 두려워하고 있습니다.",
                    Emotion = "fear",
                    Emote = "Shiver"
                }
            };

            DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForTest(Request(), story);

            Assert.Multiple(() =>
            {
                Assert.That(quality.TotalScore, Is.LessThan(75));
                Assert.That(quality.Reasons, Does.Contain("missing_specific_local_anchor"));
            });
        }

        [Test]
        public void OpenAiPrompt_BansScaffoldPhrasesAndRequiresSpecificLocalAnchors()
        {
            string payload = DynamicQuestStoryService.BuildOpenAiRequestJsonForTest("model-test", Request());

            Assert.Multiple(() =>
            {
                Assert.That(payload, Does.Contain("Do not use generic scaffold titles"));
                Assert.That(payload, Does.Contain("불안한 부탁"));
                Assert.That(payload, Does.Contain("흔적의 방향"));
                Assert.That(payload, Does.Contain("Use at least two concrete local anchors"));
                Assert.That(payload, Does.Contain("Write reusable dynamic templates"));
                Assert.That(payload, Does.Contain("{{start_npc}}"));
                Assert.That(payload, Does.Contain("{{realm}}"));
                Assert.That(payload, Does.Contain("never expose raw fields"));
                Assert.That(payload, Does.Not.Contain("from the provided realm, start_npc, region_id"));
                Assert.That(payload, Does.Contain("Brother Penric"));
                Assert.That(payload, Does.Contain("Albion"));
                Assert.That(payload, Does.Not.Contain("must appear exactly at least once"));
            });
        }

        [Test]
        public void EvaluateQuality_RejectsFixedNaturalizedStartNpcAndRealmAnchors()
        {
            DynamicQuestStoryText story = Story();
            story.OfferText = "브라더 펜릭이 알비온 수도원 울타리의 찢긴 자루를 보이며 {{target}} 처치를 부탁했다.";
            story.ProgressText = "알비온 수도원 울타리 아래의 젖은 흙과 성벽 그림자를 따라 {{target}}를 제압해야 한다.";
            story.FinishText = "{{target}} 위협이 사라지자 브라더 펜릭은 수도원 길목의 횃불을 다시 세웠다.";
            story.NarrativeScenes = new[]
            {
                new DynamicQuestNarrativeScene
                {
                    NodeId = "talk",
                    SceneType = "Intro",
                    Title = "수도원 담장의 발자국",
                    Body = "브라더 펜릭은 알비온 수도원 담장 아래 젖은 흙을 가리켰다. 작은 발자국과 찢긴 자루가 {{target}} 위협이 마을 길목까지 번지고 있음을 보여 주었다.",
                    JournalEntry = "브라더 펜릭에게서 알비온 수도원 근처의 {{target}} 위협을 막아 달라는 부탁을 받았다.",
                    Mood = "urgent",
                    RevealPolicy = "FirstSeenOnly"
                },
                new DynamicQuestNarrativeScene
                {
                    NodeId = "explore",
                    SceneType = "Discovery",
                    Title = "성벽 그림자",
                    Body = "성벽 그림자 아래로 이어진 피 묻은 털과 발자국이 같은 방향을 가리킨다. {{target}}를 제압하지 못하면 알비온 수도원 길목은 더 위험해질 것이다.",
                    JournalEntry = "알비온 수도원 울타리의 흔적이 {{target}} 은신처로 이어진다는 사실을 확인했다.",
                    Mood = "ominous",
                    RevealPolicy = "EveryInteraction"
                },
                new DynamicQuestNarrativeScene
                {
                    NodeId = "return",
                    SceneType = "Return",
                    Title = "다시 선 횃불",
                    Body = "{{target}} 위협을 꺾자 수도원 울타리의 횃불이 다시 곧게 섰다. 브라더 펜릭에게 돌아가면 길목이 다시 안전해졌다고 전할 수 있다.",
                    JournalEntry = "{{target}}를 제압했다. 브라더 펜릭에게 알비온 수도원 길목이 안정됐다고 알려야 한다.",
                    Mood = "relieved",
                    RevealPolicy = "FirstSeenOnly"
                }
            };
            story.PresentationBeats = new[]
            {
                new DynamicQuestPresentationBeat
                {
                    NodeId = "talk",
                    Trigger = "OnNpcInteract",
                    Speaker = "StartNpc",
                    Text = "저 발자국은 방금 생긴 겁니다. 오래 두면 안 됩니다.",
                    Emotion = "caution",
                    Emote = "Point"
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "complete",
                    Trigger = "OnComplete",
                    Speaker = "StartNpc",
                    Text = "오늘 밤은 아이들이 수도원 길을 덜 무서워하겠군요.",
                    Emotion = "gratitude",
                    Emote = "Bow"
                }
            };

            DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForTest(Request(), story);

            Assert.Multiple(() =>
            {
                Assert.That(quality.TotalScore, Is.LessThan(75));
                Assert.That(quality.Reasons, Does.Not.Contain("missing_specific_local_anchor"));
                Assert.That(quality.Reasons, Does.Contain("weak_dynamic_rebindability"));
                Assert.That(quality.Reasons, Does.Contain("start_npc_not_placeholderized"));
                Assert.That(quality.Reasons, Does.Contain("realm_not_placeholderized"));
            });
        }

        [Test]
        public void EvaluateQuality_RejectsRepetitiveStorySkeleton()
        {
            DynamicQuestStoryText story = new()
            {
                Title = "{{start_npc}}의 고리석 숲길의 열린 경고",
                OfferText = "{{start_npc}}은 {{realm}} 고리석 숲길에 남은 찢긴 잎사귀 단서를 짚으며 {{target}}이 길목을 비우기 전에 위협을 막아 달라고 낮게 말했다.",
                ProgressText = "{{realm}} 고리석 숲길의 발자국과 긁힌 목책을 따라가 {{target}} 위협을 꺾어야 한다.",
                FinishText = "{{target}} 위협이 사라지자 {{start_npc}}은 성소의 물소리가 돌아왔다며 오래 참았던 숨을 내쉬었다.",
                NarrativeScenes = new[]
                {
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "talk",
                        SceneType = "Intro",
                        Title = "고리석 숲길의 말 없는 부탁",
                        Body = "{{realm}} 고리석 숲길에는 누군가 급히 남긴 찢긴 잎사귀 단서와 끊어진 발자국이 있다. 말하는 사람은 없지만 아이들이 길을 돌아가고 있다. {{target}} 위협이 가까워졌다는 증거다.",
                        JournalEntry = "{{realm}} 고리석 숲길에서 {{target}} 위협을 알리는 현장 단서를 발견했다.",
                        Mood = "mysterious",
                        RevealPolicy = "FirstSeenOnly"
                    },
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "explore",
                        SceneType = "Discovery",
                        Title = "이어지는 발자국과 긁힌 목책",
                        Body = "발자국과 긁힌 목책이 낮은 길을 따라 이어진다. 흔적 사이의 간격은 점점 좁아지고, {{target}}이 다시 돌아오기 전에 먼저 찾아내야 한다는 압박이 커진다.",
                        JournalEntry = "고리석 숲길의 단서가 {{target}}이 머문 곳으로 이어졌다.",
                        Mood = "urgent",
                        RevealPolicy = "EveryInteraction"
                    },
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "complete",
                        SceneType = "Completion",
                        Title = "잠잠해진 고리석 숲길",
                        Body = "{{target}} 위협이 사라진 뒤 고리석 숲길의 공기가 가벼워졌다. {{realm}}의 길목은 아직 완전히 안전하지 않지만, 오늘 밤의 공포는 한 번 꺾였다.",
                        JournalEntry = "{{target}} 위협을 제압했고 {{realm}} 고리석 숲길의 단서가 가리키던 불안을 잠재웠다.",
                        Mood = "relieved",
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
                        Text = "목소리를 낮추십시오. 찢긴 잎사귀 단서는 방금 생긴 흔적입니다.",
                        Emotion = "fear",
                        Emote = "Point"
                    },
                    new DynamicQuestPresentationBeat
                    {
                        NodeId = "complete",
                        Trigger = "OnComplete",
                        Speaker = "StartNpc",
                        Text = "고리석 숲길 쪽 공기가 달라졌습니다. 이제 사람들도 길을 다시 볼 겁니다.",
                        Emotion = "relief",
                        Emote = "Bow"
                    }
                }
            };

            DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForTest(Request(), story);

            Assert.Multiple(() =>
            {
                Assert.That(quality.TotalScore, Is.LessThan(75));
                Assert.That(quality.DiversityScore, Is.LessThanOrEqualTo(1));
                Assert.That(quality.Reasons, Does.Contain("repetitive_story_skeleton"));
                Assert.That(DynamicQuestStoryService.IsStoryQualityAcceptableForCache(Request(), story), Is.False);
            });
        }

        [Test]
        public void EvaluateQuality_RejectsRepeatedSentenceOpenings()
        {
            DynamicQuestStoryText story = Story();
            story.NarrativeScenes = story.NarrativeScenes.Concat(new[]
            {
                new DynamicQuestNarrativeScene
                {
                    NodeId = "choice",
                    SceneType = "Choice",
                    Title = "유품의 선택",
                    Body = "유품을 조용히 돌려주면 한 사람은 구원받지만, 진짜 주인의 이름은 묻힌다. 유품을 조용히 돌려주면 피난길은 안전해지지만, 장부를 연 손은 다시 숨는다.",
                    JournalEntry = "{{realm}} 숲 가장자리에서 {{target}} 위협을 제압한 뒤 유품을 어떻게 처리할지 결정해야 한다.",
                    Mood = "mysterious",
                    RevealPolicy = "FirstSeenOnly"
                }
            }).ToArray();

            DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForTest(Request(), story);

            Assert.Multiple(() =>
            {
                Assert.That(quality.TotalScore, Is.LessThan(75));
                Assert.That(quality.DiversityScore, Is.LessThanOrEqualTo(2));
                Assert.That(quality.Reasons, Does.Contain("repetitive_sentence_opening"));
                Assert.That(DynamicQuestStoryService.IsStoryQualityAcceptableForCache(Request(), story), Is.False);
            });
        }

        [Test]
        public void OpenAiPrompt_DoesNotSendDefaultScaffoldSeedAsPositiveInstruction()
        {
            string payload = DynamicQuestStoryService.BuildOpenAiRequestJsonForTest("model-test", Request());

            Assert.Multiple(() =>
            {
                Assert.That(payload, Does.Not.Contain("지역 분위기에 맞는 짧은 처치 의뢰"));
                Assert.That(payload, Does.Contain("story_seed"));
                Assert.That(payload, Does.Contain("현재 세계 바인딩"));
            });
        }

        [Test]
        public void EvaluateQuality_RejectsAwkwardKoreanParticleJoins()
        {
            DynamicQuestStoryText story = Story();
            story.OfferText = "마을 외곽 길목에 남은 안쪽에서 긁힌 경계석 조각와 단서 '안쪽에서 긁힌 경계석 조각'와 Talan와 되돌아온 발자국은 {{target}} 위협 뒤의 사건을 보여 줍니다.";
            story.ProgressText = "목격자 'Nessa'이 단서를 들어 올리고, 경비는 Harrow Vale과 대치합니다.";
            story.NarrativeScenes = story.NarrativeScenes.Concat(new[]
            {
                new DynamicQuestNarrativeScene
                {
                    NodeId = "complete",
                    SceneType = "Completion",
                    Title = "증언의 끝",
                    Body = "경계석 조각와 목격자의 이름이 같은 기록에 남으며, {{target}} 위협이 끝난 뒤에도 길목의 불안은 오래 감시됩니다.",
                    JournalEntry = "마을 외곽 길목에서 {{target}} 위협을 제압했고 경계석 조각와 증언을 남겼다.",
                    Mood = "hopeful",
                    RevealPolicy = "FirstSeenOnly"
                }
            }).ToArray();

            DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForTest(Request(), story);

            Assert.Multiple(() =>
            {
                Assert.That(quality.Reasons, Does.Contain("awkward_korean_particle"));
                Assert.That(quality.TotalScore, Is.LessThan(75));
                Assert.That(DynamicQuestStoryService.IsStoryQualityAcceptableForCache(Request(), story), Is.False);
            });
        }

        [Test]
        public void ValidatePresentation_StripsRawEmoteIdsAndUnsafeTriggers()
        {
            DynamicQuestStoryText story = Story();
            story.PresentationBeats = new[]
            {
                new DynamicQuestPresentationBeat
                {
                    NodeId = "talk",
                    Trigger = "RunCommand",
                    Speaker = "StartNpc",
                    Text = "spawn now",
                    Emotion = "fear",
                    Emote = "999"
                }
            };

            DynamicQuestStoryQuality quality = DynamicQuestStoryService.EvaluateQualityDetailsForTest(Request(), story);
            DynamicQuestStoryText sanitized = DynamicQuestStoryService.SanitizeStoryForTest(Request(), story);

            Assert.Multiple(() =>
            {
                Assert.That(sanitized.PresentationBeats, Is.Empty);
                Assert.That(quality.SafetyScore, Is.LessThan(15));
            });
        }

        [Test]
        public void ParseStoryJson_ReadsNarrativeAndPresentationArrays()
        {
            string json = """
            {
              "title": "숲속의 작은 위협",
              "offer": "Brother Penric이 {{target}} 처치를 부탁합니다.",
              "progress": "{{target}} 흔적을 따라가야 합니다.",
              "finish": "{{target}} 위협이 사라졌습니다.",
              "target": "black wolf pup",
              "count": 1,
              "min_level": 1,
              "max_level": 5,
              "narrative_scenes": [
                {
                  "node_id": "talk",
                  "scene_type": "Intro",
                  "title": "숲의 숨죽임",
                  "body": "숲 가장자리의 울타리가 찢겼습니다.\n\n마을 사람들은 밤마다 울음소리를 듣습니다.",
                  "journal_entry": "Brother Penric은 숲의 변화가 마을로 번질까 걱정했다.",
                  "mood": "ominous",
                  "reveal_policy": "FirstSeenOnly"
                }
              ],
              "presentation_beats": [
                {
                  "node_id": "talk",
                  "trigger": "OnNpcInteract",
                  "speaker": "StartNpc",
                  "text": "저 소리를 들으셨습니까?",
                  "emotion": "fear",
                  "emote": "Shiver",
                  "cinematic_action": "ambush_reveal",
                  "scene_role": "ambush_wave",
                  "formation": "ambush",
                  "actor_count": 12,
                  "delay_ms": 900
                }
              ]
            }
            """;

            DynamicQuestStoryText parsed = DynamicQuestStoryService.ParseStoryJsonForTest(json, Request());

            Assert.Multiple(() =>
            {
                Assert.That(parsed.NarrativeScenes, Has.Count.EqualTo(1));
                Assert.That(parsed.PresentationBeats, Has.Count.EqualTo(1));
                Assert.That(parsed.NarrativeScenes[0].Body, Does.Contain("울타리"));
                Assert.That(parsed.PresentationBeats[0].Emote, Is.EqualTo("Shiver"));
                Assert.That(parsed.PresentationBeats[0].CinematicAction, Is.EqualTo("ambush_reveal"));
                Assert.That(parsed.PresentationBeats[0].SceneRole, Is.EqualTo("ambush_wave"));
                Assert.That(parsed.PresentationBeats[0].Formation, Is.EqualTo("ambush"));
                Assert.That(parsed.PresentationBeats[0].ActorCount, Is.EqualTo(12));
                Assert.That(parsed.PresentationBeats[0].DelayMs, Is.EqualTo(900));
            });
        }

        [Test]
        public void OpenAiSchema_IncludesNarrativeAndPresentationFields()
        {
            string payload = DynamicQuestStoryService.BuildOpenAiRequestJsonForTest("model-test", Request());

            Assert.Multiple(() =>
            {
                Assert.That(payload, Does.Contain("narrative_scenes"));
                Assert.That(payload, Does.Contain("presentation_beats"));
                Assert.That(payload, Does.Contain("cinematic_action"));
                Assert.That(payload, Does.Contain("actor_count"));
                Assert.That(payload, Does.Contain("delay_ms"));
                Assert.That(payload, Does.Contain("warning"));
                Assert.That(payload, Does.Contain("anxious"));
                Assert.That(payload, Does.Contain("\"minItems\":3"));
                Assert.That(payload, Does.Contain("\"minItems\":4"));
                Assert.That(payload, Does.Contain("\"max_tokens\":2048"));
                Assert.That(payload, Does.Contain("Example JSON shape"));
                Assert.That(payload, Does.Contain("\\\"narrative_scenes\\\":[{\\\"node_id\\\":\\\"talk\\\""));
                Assert.That(payload, Does.Contain("\\\"presentation_beats\\\":[{\\\"node_id\\\":\\\"talk\\\""));
                Assert.That(payload, Does.Contain("\\\"trigger\\\":\\\"OnComplete\\\""));
                Assert.That(payload, Does.Not.Contain("OnQuestComplete"));
                Assert.That(payload, Does.Not.Contain("\\\"mood\\\":\\\"uneasy\\\""));
                Assert.That(payload, Does.Not.Contain("\\\"emote\\\":\\\"Thank\\\""));
                Assert.That(payload, Does.Contain("Do not output raw emote ids"));
                Assert.That(payload, Does.Contain("Do not invent model numbers"));
                Assert.That(payload, Does.Contain("model:label:category"));
                Assert.That(payload, Does.Contain("clue means tracks/evidence/path markers"));
                Assert.That(payload, Does.Contain("record means tomes/journals/written warnings"));
                Assert.That(payload, Does.Contain("relic means ritual stones/pendants/totems/realm symbols"));
                Assert.That(payload, Does.Contain("flame means torches/campfires/omens/fresh danger"));
                Assert.That(payload, Does.Contain("weapon means arrows/broken weapons/combat aftermath"));
                Assert.That(payload, Does.Contain("structure means doors/gates/portals/keeps/relic pads"));
                Assert.That(payload, Does.Contain("\"enum\":[\"choice\",\"complete\",\"explore\",\"kill\",\"observe_signal\",\"return\",\"talk\"]"));
                Assert.That(payload, Does.Contain("\"enum\":[\"OnAccept\",\"OnChoiceSelected\",\"OnChoiceShown\",\"OnComplete\",\"OnExplore\",\"OnKill\",\"OnNodeEnter\",\"OnNpcInteract\",\"OnWorldSignal\"]"));
                Assert.That(payload, Does.Contain("\"enum\":[\"Angry\",\"Bow\",\"Cheer\",\"Cower\",\"Cry\",\"No\",\"Point\",\"Ponder\",\"Salute\",\"Shiver\",\"Smile\"]"));
            });
        }

        [Test]
        public void OpenAiResponsesRequest_UsesJsonSchemaAndOutputTokenLimit()
        {
            string payload = DynamicQuestStoryService.BuildOpenAiResponsesRequestJsonForTest("gpt-5.4", Request());

            Assert.Multiple(() =>
            {
                Assert.That(payload, Does.Contain("\"model\":\"gpt-5.4\""));
                Assert.That(payload, Does.Contain("\"max_output_tokens\":2048"));
                Assert.That(payload, Does.Contain("\"format\""));
                Assert.That(payload, Does.Contain("\"json_schema\""));
                Assert.That(payload, Does.Contain("\"enum\":[\"choice\",\"complete\",\"explore\",\"kill\",\"observe_signal\",\"return\",\"talk\"]"));
            });
        }

        [Test]
        public void GeminiQuota_AllowsConfiguredMinuteAndDailyLimitsOnly()
        {
            DateTime now = new(2026, 6, 3, 10, 0, 0, DateTimeKind.Utc);
            DynamicQuestGeminiQuota quota = new(1, 1, () => now);

            bool first = quota.TryReserve();
            bool secondSameMinute = quota.TryReserve();
            now = now.AddMinutes(2);
            bool thirdSameDay = quota.TryReserve();
            now = now.AddDays(1);
            bool firstNextDay = quota.TryReserve();

            Assert.Multiple(() =>
            {
                Assert.That(first, Is.True);
                Assert.That(secondSameMinute, Is.False);
                Assert.That(thirdSameDay, Is.False);
                Assert.That(firstNextDay, Is.True);
            });
        }

        [Test]
        public void GeminiQuota_ResetsDailyAtPacificMidnight()
        {
            DateTime now = new(2026, 6, 3, 6, 59, 0, DateTimeKind.Utc);
            DynamicQuestGeminiQuota quota = new(10, 1, () => now);

            bool beforePacificMidnight = quota.TryReserve();
            now = new DateTime(2026, 6, 3, 7, 0, 0, DateTimeKind.Utc);
            bool atPacificMidnight = quota.TryReserve();

            Assert.Multiple(() =>
            {
                Assert.That(beforePacificMidnight, Is.True);
                Assert.That(atPacificMidnight, Is.True);
            });
        }

        [Test]
        public void GeminiQuota_PersistsDailyLimitAcrossQuotaInstances()
        {
            DateTime now = new(2026, 6, 3, 10, 0, 0, DateTimeKind.Utc);
            MemoryDailyQuotaStore store = new();
            DynamicQuestGeminiQuota firstQuota = new(10, 1, () => now, "openai", store);
            DynamicQuestGeminiQuota restartedQuota = new(10, 1, () => now, "openai", store);

            bool first = firstQuota.TryReserve();
            bool secondAfterRestart = restartedQuota.TryReserve();
            now = new DateTime(2026, 6, 4, 7, 0, 0, DateTimeKind.Utc);
            DynamicQuestGeminiQuota nextPacificDayQuota = new(10, 1, () => now, "openai", store);
            bool firstNextDay = nextPacificDayQuota.TryReserve();

            Assert.Multiple(() =>
            {
                Assert.That(first, Is.True);
                Assert.That(secondAfterRestart, Is.False);
                Assert.That(firstNextDay, Is.True);
            });
        }

        [Test]
        public void DynamicQuestTokenBudget_BlocksBeforeProviderCallWhenEstimatedTokensExceedCap()
        {
            DateTime now = new(2026, 6, 3, 10, 0, 0, DateTimeKind.Utc);
            MemoryTokenBudgetStore tokenStore = new();
            DynamicQuestTokenBudget tokenBudget = new("openai", 1, tokenStore, () => now);

            bool reserved = tokenBudget.TryReserve(estimatedTokens: 2048, out DynamicQuestTokenReservation reservation, out string error);

            Assert.Multiple(() =>
            {
                Assert.That(reserved, Is.False);
                Assert.That(error, Is.EqualTo("openai_token_quota_exhausted"));
                Assert.That(reservation, Is.Null);
                Assert.That(tokenStore.Spent("openai", DynamicQuestGeminiQuotaClock.PacificDate(now)), Is.EqualTo(0));
            });
        }

        [Test]
        public void DynamicQuestTokenBudget_FinalizesReservedTokensToActualUsage()
        {
            DateTime now = new(2026, 6, 3, 10, 0, 0, DateTimeKind.Utc);
            MemoryTokenBudgetStore tokenStore = new();
            DynamicQuestTokenBudget tokenBudget = new("openai", 10000, tokenStore, () => now);

            bool reserved = tokenBudget.TryReserve(estimatedTokens: 7000, out DynamicQuestTokenReservation reservation, out string error);
            tokenBudget.Finalize(reservation, actualTokens: 2413);

            Assert.Multiple(() =>
            {
                Assert.That(reserved, Is.True, error);
                Assert.That(tokenStore.Spent("openai", DynamicQuestGeminiQuotaClock.PacificDate(now)), Is.EqualTo(2413));
            });
        }

        [Test]
        public void OpenAiProvider_UsesTokenBudgetBeforeHttpCall()
        {
            Type providerType = typeof(DynamicQuestStoryService)
                .GetNestedType("OpenAiDynamicQuestStoryProvider", BindingFlags.NonPublic);
            Assert.That(providerType, Is.Not.Null);

            DateTime now = new(2026, 6, 3, 10, 0, 0, DateTimeKind.Utc);
            DynamicQuestTokenBudget tokenBudget = new("openai", 1, new MemoryTokenBudgetStore(), () => now);
            IDynamicQuestStoryProvider provider = (IDynamicQuestStoryProvider)Activator.CreateInstance(
                providerType,
                "openai",
                "http://127.0.0.1:1",
                "gpt-5.4",
                new DynamicQuestGeminiQuota(10, 10),
                tokenBudget,
                5);

            using (new ScopedEnvironment("OPENAI_API_KEY", "test-openai-key"))
            {
                DynamicQuestStoryGenerationResult result = provider.TryGenerate(Request());

                Assert.Multiple(() =>
                {
                    Assert.That(result.Success, Is.False);
                    Assert.That(result.Error, Is.EqualTo("openai_token_quota_exhausted"));
                });
            }
        }

        [Test]
        public void GeminiQuota_BacksOffAfterRemoteThrottle()
        {
            DateTime now = new(2026, 6, 3, 10, 0, 0, DateTimeKind.Utc);
            DynamicQuestGeminiQuota quota = new(5, 100, () => now);

            bool beforeThrottle = quota.TryReserve();
            quota.MarkThrottled(TimeSpan.FromMinutes(1));
            bool duringThrottle = quota.TryReserve();
            now = now.AddSeconds(61);
            bool afterThrottle = quota.TryReserve();

            Assert.Multiple(() =>
            {
                Assert.That(beforeThrottle, Is.True);
                Assert.That(duringThrottle, Is.False);
                Assert.That(afterThrottle, Is.True);
            });
        }

        [Test]
        public async Task OpenAiProvider_UsesResponsesApiAndRespectsQuota()
        {
            using TcpListener listener = new(IPAddress.Loopback, 0);
            listener.Start();
            int port = ((IPEndPoint)listener.LocalEndpoint).Port;
            Task<IList<string>> serverTask = ServeOpenAiResponsesApiStoryResponse(listener, expectedRequests: 1);

            Type providerType = typeof(DynamicQuestStoryService)
                .GetNestedType("OpenAiDynamicQuestStoryProvider", BindingFlags.NonPublic);
            Assert.That(providerType, Is.Not.Null);

            DynamicQuestGeminiQuota quota = new(1, 1);
            IDynamicQuestStoryProvider provider = (IDynamicQuestStoryProvider)Activator.CreateInstance(
                providerType,
                "openai",
                $"http://127.0.0.1:{port}",
                "gpt-5.4",
                quota,
                5);

            using (new ScopedEnvironment("OPENAI_API_KEY", "test-openai-key"))
            {
                DynamicQuestStoryGenerationResult first = provider.TryGenerate(Request());
                DynamicQuestStoryGenerationResult second = provider.TryGenerate(Request());
                IList<string> requests = await serverTask;

                Assert.Multiple(() =>
                {
                    Assert.That(first.Success, Is.True, first.Error);
                    Assert.That(first.ProviderName, Is.EqualTo("openai"));
                    Assert.That(first.ModelName, Is.EqualTo("gpt-5.4"));
                    Assert.That(second.Success, Is.False);
                    Assert.That(second.Error, Is.EqualTo("openai_quota_exhausted"));
                    Assert.That(requests, Has.Count.EqualTo(1));
                    Assert.That(requests[0], Does.Contain("POST /v1/responses"));
                    Assert.That(requests[0], Does.Contain("\"max_output_tokens\":2048"));
                });
            }
        }

        [Test]
        public void GeminiPayload_UsesEnoughOutputTokensForThinkingModels()
        {
            string payloadJson = DynamicQuestStoryService.BuildGeminiRequestJsonForTest(Request());

            Assert.Multiple(() =>
            {
                Assert.That(payloadJson, Does.Contain("\"maxOutputTokens\":2048"));
                Assert.That(payloadJson, Does.Contain("\"responseMimeType\":\"application/json\""));
            });
        }

        [Test]
        public void GeminiProvider_DefaultsToGemini35FlashWhenModelPropertyIsBlank()
        {
            Type providerType = typeof(DynamicQuestStoryService)
                .GetNestedType("GeminiDynamicQuestStoryProvider", BindingFlags.NonPublic);
            Assert.That(providerType, Is.Not.Null);

            IDynamicQuestStoryProvider provider = (IDynamicQuestStoryProvider)Activator.CreateInstance(
                providerType,
                "gemini",
                "",
                new DynamicQuestGeminiQuota(1, 1));

            Assert.That(provider.ModelName, Is.EqualTo("gemini-3.5-flash"));
        }

        [Test]
        public async Task OpenAiProvider_RetriesWithoutJsonSchemaWhenStrictSchemaRejected()
        {
            using TcpListener listener = new(IPAddress.Loopback, 0);
            listener.Start();
            int port = ((IPEndPoint)listener.LocalEndpoint).Port;
            Task<IList<string>> serverTask = ServeSchemaFallbackOpenAiResponses(listener);

            Type providerType = typeof(DynamicQuestStoryService)
                .GetNestedType("OpenAiCompatibleDynamicQuestStoryProvider", BindingFlags.NonPublic);
            Assert.That(providerType, Is.Not.Null);

            IDynamicQuestStoryProvider provider = (IDynamicQuestStoryProvider)Activator.CreateInstance(
                providerType,
                "secondary-local",
                $"http://127.0.0.1:{port}",
                "local-gemma-test",
                5);

            DynamicQuestStoryGenerationResult result = provider.TryGenerate(Request());
            IList<string> requests = await serverTask;

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Error);
                Assert.That(result.ProviderName, Is.EqualTo("secondary-local"));
                Assert.That(result.Story.Title, Is.EqualTo("수도원 울타리의 밤소리"));
                Assert.That(requests, Has.Count.EqualTo(2));
                Assert.That(requests[0], Does.Contain("\"json_schema\""));
                Assert.That(requests[1], Does.Not.Contain("\"response_format\""));
            });
        }

        [Test]
        public async Task OpenAiProvider_RetriesWithCompactPromptWhenPlainRequestStillRejected()
        {
            using TcpListener listener = new(IPAddress.Loopback, 0);
            listener.Start();
            int port = ((IPEndPoint)listener.LocalEndpoint).Port;
            Task<IList<string>> serverTask = ServeCompactFallbackOpenAiResponses(listener);

            Type providerType = typeof(DynamicQuestStoryService)
                .GetNestedType("OpenAiCompatibleDynamicQuestStoryProvider", BindingFlags.NonPublic);
            Assert.That(providerType, Is.Not.Null);

            IDynamicQuestStoryProvider provider = (IDynamicQuestStoryProvider)Activator.CreateInstance(
                providerType,
                "secondary-local",
                $"http://127.0.0.1:{port}",
                "local-gemma-test",
                5);

            DynamicQuestStoryGenerationResult result = provider.TryGenerate(Request());
            IList<string> requests = await serverTask;

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Error);
                Assert.That(result.ProviderName, Is.EqualTo("secondary-local"));
                Assert.That(requests, Has.Count.EqualTo(3));
                Assert.That(requests[0], Does.Contain("\"json_schema\""));
                Assert.That(requests[1], Does.Contain("Example JSON shape"));
                Assert.That(requests[1], Does.Not.Contain("\"response_format\""));
                Assert.That(requests[2], Does.Not.Contain("Example JSON shape"));
                Assert.That(requests[2], Does.Contain("\"max_tokens\":256"));
            });
        }

        private static DynamicQuestStoryRequest Request()
        {
            return new DynamicQuestStoryRequest
            {
                TemplateId = "seed-1-test",
                Realm = "Albion",
                StartNpcName = "Brother Penric",
                RegionId = 1,
                TargetName = "black wolf pup",
                Count = 1,
                MinLevel = 1,
                MaxLevel = 5,
                StorySeed = "지역 분위기에 맞는 짧은 처치 의뢰"
            };
        }

        private static DynamicQuestStoryRequest UnknownRealmRequest()
        {
            return new DynamicQuestStoryRequest
            {
                TemplateId = "seed-334-test",
                Realm = "Unknown",
                StartNpcName = "",
                RegionId = 334,
                TargetName = "thidranki raider",
                Count = 3,
                MinLevel = 42,
                MaxLevel = 46,
                StorySeed = "지역 분위기에 맞는 짧은 처치 의뢰"
            };
        }

        private static DynamicQuestTemplate Template()
        {
            return new DynamicQuestTemplate
            {
                TemplateId = "seed-1-test",
                Realm = "Albion",
                PreferredStartNpcName = "Brother Penric",
                PreferredStartNpcInternalId = "start-npc-1",
                PreferredRegionId = 1,
                TargetNameHint = "black wolf pup",
                PreferredTargetNpcInternalId = "target-npc-1",
                Count = 1,
                MinLevel = 1,
                MaxLevel = 5,
                StorySeed = "지역 분위기에 맞는 짧은 처치 의뢰"
            };
        }

        private static DynamicQuestStoryText Story()
        {
            return new DynamicQuestStoryText
            {
                Title = "숲속의 작은 위협",
                OfferText = "{{start_npc}}이 {{realm}} 숲 가장자리의 찢긴 울타리를 보여 주며 {{target}} 처치를 부탁합니다.",
                ProgressText = "{{realm}} 숲 가장자리의 발자국을 따라가 {{target}}를 찾아 쓰러뜨려야 합니다.",
                FinishText = "{{target}} 위협을 제압하자 {{start_npc}}은 {{realm}} 길목의 횃불을 다시 세웠습니다.",
                NarrativeScenes = new[]
                {
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "talk",
                        SceneType = "Intro",
                        Title = "숲의 숨죽임",
                        Body = "{{start_npc}}은 {{realm}} 숲 가장자리의 울타리가 한 번 더 찢겼다고 말했다. 마을 사람들은 {{target}}의 울음이 전보다 가까워졌다고 말합니다.",
                        JournalEntry = "{{start_npc}}에게서 {{realm}} 숲 가장자리의 {{target}} 위협을 막아 달라는 부탁을 받았다.",
                        Mood = "ominous",
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
                        Text = "저 숲이 오늘은 숨을 죽인 것 같군요.",
                        Emotion = "fear",
                        Emote = "Shiver"
                    }
                }
            };
        }

        private static DynamicQuestStoryText GenericScaffoldStory()
        {
            return new DynamicQuestStoryText
            {
                Title = "지역 분위기의 불길한 조짐",
                OfferText = "지역 분위기가 심상치 않습니다. {{target}}의 기운이 느껴지는 곳을 조사하여 {{target}}를 처단해 주십시오.",
                ProgressText = "{{target}}가 나타나 마을을 위협하고 있습니다. {{target}}를 1마리 더 물리쳐야 합니다.",
                FinishText = "모든 {{target}}를 소탕했습니다. 이제 지역은 다시 평온을 되찾았습니다.",
                NarrativeScenes = new[]
                {
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "talk",
                        SceneType = "Intro",
                        Title = "불안한 부탁",
                        Body = "지역 주민은 {{target}}의 흔적이 Albion 곳곳으로 번지고 있다고 말합니다. 아직 작은 소문처럼 들리지만, 방치하면 마을의 밤이 더 길어질 것입니다.",
                        JournalEntry = "지역 주민에게서 {{target}} 위협이 커지고 있다는 이야기를 들었다.",
                        Mood = "urgent",
                        RevealPolicy = "FirstSeenOnly"
                    },
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "explore",
                        SceneType = "Discovery",
                        Title = "흔적의 방향",
                        Body = "흙과 풀잎 사이에 남은 {{target}}의 흔적이 한 방향으로 이어집니다. 주변은 조용하지만, 그 조용함이 오히려 다음 싸움을 예고합니다.",
                        JournalEntry = "{{target}}의 흔적을 따라 위협의 중심에 가까워지고 있다.",
                        Mood = "ominous",
                        RevealPolicy = "FirstSeenOnly"
                    }
                },
                PresentationBeats = new[]
                {
                    new DynamicQuestPresentationBeat
                    {
                        NodeId = "talk",
                        Trigger = "OnNpcInteract",
                        Speaker = "System",
                        Text = "{{target}} 소식 때문에 모두가 조용히 문을 걸어 잠그고 있습니다.",
                        Emotion = "fear",
                        Emote = "Shiver"
                    }
                }
            };
        }

        private static DynamicQuestStoryText CacheReadyStory()
        {
            return new DynamicQuestStoryText
            {
                Title = "수도원 길목의 찢긴 보호끈",
                OfferText = "{{start_npc}}은 {{realm}} 수도원 길목에서 발견된 찢긴 보호끈을 보여 주며 {{target}} 위협이 마을 가까이 왔다고 말합니다.",
                ProgressText = "{{realm}} 수도원 길목의 젖은 흙과 부러진 표식을 따라가 {{target}} 위협을 끊어야 합니다.",
                FinishText = "{{target}} 위협이 사라지자 {{start_npc}}은 {{realm}} 길목의 횃불을 다시 세웠습니다.",
                NarrativeScenes = new[]
                {
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "talk",
                        SceneType = "Intro",
                        Title = "찢긴 보호끈",
                        Body = "{{start_npc}}은 {{realm}} 수도원 길목의 젖은 흙을 짚으며 {{target}}의 발자국이 마을 울타리까지 번지고 있다고 말합니다.",
                        JournalEntry = "{{start_npc}}에게서 {{realm}} 수도원 길목의 {{target}} 위협을 조사해 달라는 부탁을 받았다.",
                        Mood = "ominous",
                        RevealPolicy = "FirstSeenOnly"
                    },
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "explore",
                        SceneType = "Discovery",
                        Title = "되돌아온 발자국",
                        Body = "부러진 표식과 젖은 흙 사이로 {{target}} 흔적이 같은 방향으로 되돌아옵니다. 길목의 침묵은 다음 싸움이 가까웠다는 증거처럼 남습니다.",
                        JournalEntry = "{{realm}} 수도원 길목에서 {{target}}가 같은 길을 반복해 지나간 흔적을 찾았다.",
                        Mood = "urgent",
                        RevealPolicy = "FirstSeenOnly"
                    },
                    new DynamicQuestNarrativeScene
                    {
                        NodeId = "complete",
                        SceneType = "Completion",
                        Title = "다시 선 횃불",
                        Body = "{{target}} 위협을 꺾자 수도원 길목의 횃불이 다시 곧게 섭니다. 사람들은 아직 조심스럽지만 오늘 밤 문을 조금 늦게 닫아도 됩니다.",
                        JournalEntry = "{{target}} 위협을 제압했고 {{realm}} 수도원 길목 주변의 길이 다시 열렸다.",
                        Mood = "hopeful",
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
                        Text = "저 발자국은 방금 생긴 겁니다. 길목이 더 조용해지기 전에 막아야 합니다.",
                        Emotion = "fear",
                        Emote = "Shiver"
                    },
                    new DynamicQuestPresentationBeat
                    {
                        NodeId = "explore",
                        Trigger = "OnExplore",
                        Speaker = "System",
                        Text = "젖은 흙 위의 표식이 흔들리고, 정찰자가 뒤쪽 길로 물러납니다.",
                        Emotion = "suspicion",
                        Emote = "Ponder",
                        CinematicAction = "scout_retreat",
                        SceneRole = "oathbreaker_lookout",
                        Formation = "patrol",
                        ActorCount = 12
                    },
                    new DynamicQuestPresentationBeat
                    {
                        NodeId = "kill",
                        Trigger = "OnKill",
                        Speaker = "System",
                        Text = "매복 병력이 모습을 드러내자 경비들이 방패선을 세우고 탈출 경로를 막습니다.",
                        Emotion = "urgency",
                        Emote = "Point",
                        CinematicAction = "defender_intercept",
                        SceneRole = "shield_oath_intercept",
                        Formation = "line",
                        ActorCount = 12,
                        DelayMs = 700
                    }
                }
            };
        }

        private static DynamicQuestStoryText BasicStoryWithoutPresentation()
        {
            return new DynamicQuestStoryText
            {
                Title = "숲속의 작은 위협",
                OfferText = "Brother Penric이 black wolf pup 처치를 부탁합니다.",
                ProgressText = "black wolf pup를 찾아 쓰러뜨려야 합니다.",
                FinishText = "black wolf pup 위협을 제압했습니다."
            };
        }

        private static async Task<IList<string>> ServeSchemaFallbackOpenAiResponses(TcpListener listener)
        {
            List<string> requests = new();
            for (int index = 0; index < 2; index++)
            {
                using CancellationTokenSource acceptTimeout = new(TimeSpan.FromSeconds(2));
                TcpClient client;
                try
                {
                    client = await listener.AcceptTcpClientAsync(acceptTimeout.Token);
                }
                catch (OperationCanceledException)
                {
                    break;
                }

                using (client)
                {
                using NetworkStream stream = client.GetStream();
                string requestBody = await ReadHttpRequestBody(stream);
                requests.Add(requestBody);

                if (index == 0)
                {
                    await WriteHttpResponse(stream, 400, "{}");
                    continue;
                }

                await WriteHttpResponse(stream, 200, BuildOpenAiStoryResponse());
                }
            }

            return requests;
        }

        private static async Task<IList<string>> ServeCompactFallbackOpenAiResponses(TcpListener listener)
        {
            List<string> requests = new();
            for (int index = 0; index < 3; index++)
            {
                using CancellationTokenSource acceptTimeout = new(TimeSpan.FromSeconds(2));
                TcpClient client;
                try
                {
                    client = await listener.AcceptTcpClientAsync(acceptTimeout.Token);
                }
                catch (OperationCanceledException)
                {
                    break;
                }

                using (client)
                {
                    using NetworkStream stream = client.GetStream();
                    string requestBody = await ReadHttpRequestBody(stream);
                    requests.Add(requestBody);

                    if (index < 2)
                    {
                        await WriteHttpResponse(stream, 400, "{}");
                        continue;
                    }

                    await WriteHttpResponse(stream, 200, BuildOpenAiStoryResponse());
                }
            }

            return requests;
        }

        private static async Task<IList<string>> ServeOpenAiResponsesApiStoryResponse(TcpListener listener, int expectedRequests)
        {
            List<string> requests = new();
            for (int index = 0; index < expectedRequests; index++)
            {
                using CancellationTokenSource acceptTimeout = new(TimeSpan.FromSeconds(2));
                TcpClient client;
                try
                {
                    client = await listener.AcceptTcpClientAsync(acceptTimeout.Token);
                }
                catch (OperationCanceledException)
                {
                    break;
                }

                using (client)
                {
                    using NetworkStream stream = client.GetStream();
                    string request = await ReadHttpRequest(stream);
                    requests.Add(request);
                    await WriteHttpResponse(stream, 200, BuildOpenAiResponsesStoryResponse());
                }
            }

            return requests;
        }

        private static async Task<string> ReadHttpRequest(NetworkStream stream)
        {
            List<byte> bytes = new();
            byte[] buffer = new byte[1024];
            int headerEnd = -1;
            while (headerEnd < 0)
            {
                int read = await stream.ReadAsync(buffer.AsMemory(0, buffer.Length));
                if (read <= 0)
                    break;
                bytes.AddRange(buffer.Take(read));
                headerEnd = IndexOfHeaderEnd(bytes);
            }

            string header = Encoding.ASCII.GetString(bytes.Take(headerEnd + 4).ToArray());
            int contentLength = 0;
            foreach (string line in header.Split(new[] { "\r\n" }, StringSplitOptions.RemoveEmptyEntries))
            {
                if (line.StartsWith("Content-Length:", StringComparison.OrdinalIgnoreCase))
                    int.TryParse(line.Substring("Content-Length:".Length).Trim(), out contentLength);
            }

            int bodyStart = headerEnd + 4;
            while (bytes.Count - bodyStart < contentLength)
            {
                int read = await stream.ReadAsync(buffer.AsMemory(0, buffer.Length));
                if (read <= 0)
                    break;
                bytes.AddRange(buffer.Take(read));
            }

            string body = Encoding.UTF8.GetString(bytes.Skip(bodyStart).Take(contentLength).ToArray());
            string requestLine = header.Split(new[] { "\r\n" }, StringSplitOptions.RemoveEmptyEntries).FirstOrDefault() ?? string.Empty;
            return requestLine + "\n" + body;
        }

        private static async Task<string> ReadHttpRequestBody(NetworkStream stream)
        {
            List<byte> bytes = new();
            byte[] buffer = new byte[1024];
            int headerEnd = -1;
            while (headerEnd < 0)
            {
                int read = await stream.ReadAsync(buffer.AsMemory(0, buffer.Length));
                if (read <= 0)
                    break;
                bytes.AddRange(buffer.Take(read));
                headerEnd = IndexOfHeaderEnd(bytes);
            }

            string header = Encoding.ASCII.GetString(bytes.Take(headerEnd + 4).ToArray());
            int contentLength = 0;
            foreach (string line in header.Split(new[] { "\r\n" }, StringSplitOptions.RemoveEmptyEntries))
            {
                if (line.StartsWith("Content-Length:", StringComparison.OrdinalIgnoreCase))
                    int.TryParse(line.Substring("Content-Length:".Length).Trim(), out contentLength);
            }

            int bodyStart = headerEnd + 4;
            while (bytes.Count - bodyStart < contentLength)
            {
                int read = await stream.ReadAsync(buffer.AsMemory(0, buffer.Length));
                if (read <= 0)
                    break;
                bytes.AddRange(buffer.Take(read));
            }

            return Encoding.UTF8.GetString(bytes.Skip(bodyStart).Take(contentLength).ToArray());
        }

        private static int IndexOfHeaderEnd(IList<byte> bytes)
        {
            for (int index = 3; index < bytes.Count; index++)
            {
                if (bytes[index - 3] == '\r' &&
                    bytes[index - 2] == '\n' &&
                    bytes[index - 1] == '\r' &&
                    bytes[index] == '\n')
                    return index - 3;
            }

            return -1;
        }

        private static Task WriteHttpResponse(NetworkStream stream, int statusCode, string body)
        {
            string statusText = statusCode == 200 ? "OK" : "Bad Request";
            byte[] bodyBytes = Encoding.UTF8.GetBytes(body ?? string.Empty);
            string header = $"HTTP/1.1 {statusCode} {statusText}\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {bodyBytes.Length}\r\nConnection: close\r\n\r\n";
            byte[] headerBytes = Encoding.ASCII.GetBytes(header);
            return stream.WriteAsync(headerBytes.Concat(bodyBytes).ToArray()).AsTask();
        }

        private static string BuildOpenAiStoryResponse()
        {
            string storyJson = JsonSerializer.Serialize(new
            {
                title = "수도원 울타리의 밤소리",
                offer = "Brother Penric은 Albion 수도원 울타리에 남은 발자국을 짚으며 {{target}} 처치를 부탁했다.",
                progress = "Albion 수도원 울타리 너머로 이어지는 {{target}} 흔적을 따라가 제압해야 한다.",
                finish = "{{target}} 위협이 사라지자 Brother Penric은 수도원 울타리의 횃불을 다시 세웠다.",
                target = "black wolf pup",
                count = 1,
                min_level = 1,
                max_level = 5,
                narrative_scenes = new[]
                {
                    new
                    {
                        node_id = "talk",
                        scene_type = "Intro",
                        title = "젖은 울타리",
                        body = "Brother Penric은 Albion 수도원 울타리의 젖은 흙 위에 남은 {{target}} 발자국을 낮게 가리켰다. 밤마다 종소리가 끊기고 아이들이 길을 피해 돌아간다고 말했다.",
                        journal_entry = "Brother Penric에게서 Albion 수도원 울타리 근처의 {{target}} 위협을 막아 달라는 부탁을 받았다.",
                        mood = "ominous",
                        reveal_policy = "FirstSeenOnly"
                    },
                    new
                    {
                        node_id = "explore",
                        scene_type = "Discovery",
                        title = "성벽 그림자",
                        body = "브리튼 성벽 그림자 아래의 찢긴 천과 발자국이 같은 곳을 가리킨다. {{target}}를 지금 제압하지 못하면 수도원 길목은 더 오래 비게 될 것이다.",
                        journal_entry = "Albion 수도원 울타리의 증거가 {{target}} 은신처로 이어진다는 사실을 확인했다.",
                        mood = "urgent",
                        reveal_policy = "EveryInteraction"
                    },
                    new
                    {
                        node_id = "return",
                        scene_type = "Return",
                        title = "다시 선 횃불",
                        body = "{{target}} 위협을 꺾자 수도원 울타리 근처의 횃불이 다시 곧게 섰다. Brother Penric에게 돌아가면 Albion 길목이 다시 안전해졌다고 전할 수 있다.",
                        journal_entry = "{{target}}를 제압했다. Brother Penric에게 Albion 수도원 길목이 안정됐다고 알려야 한다.",
                        mood = "relieved",
                        reveal_policy = "FirstSeenOnly"
                    }
                },
                presentation_beats = new[]
                {
                    new
                    {
                        node_id = "talk",
                        trigger = "OnNpcInteract",
                        speaker = "StartNpc",
                        text = "목소리를 낮추세요. 저 발자국은 방금 생긴 겁니다.",
                        emotion = "fear",
                        emote = "Shiver"
                    },
                    new
                    {
                        node_id = "return",
                        trigger = "OnComplete",
                        speaker = "StartNpc",
                        text = "오늘 밤은 수도원 울타리의 불을 꺼도 되겠군요.",
                        emotion = "gratitude",
                        emote = "Bow"
                    }
                }
            });

            return JsonSerializer.Serialize(new
            {
                choices = new[]
                {
                    new
                    {
                        message = new
                        {
                            content = storyJson
                        }
                    }
                }
            });
        }

        private static string BuildOpenAiResponsesStoryResponse()
        {
            string storyJson = JsonSerializer.Serialize(new
            {
                title = "수도원 울타리의 밤소리",
                offer = "Brother Penric은 Albion 수도원 울타리에 남은 발자국을 짚으며 {{target}} 처치를 부탁했다.",
                progress = "Albion 수도원 울타리 너머로 이어지는 {{target}} 흔적을 따라가 제압해야 한다.",
                finish = "{{target}} 위협이 사라지자 Brother Penric은 수도원 울타리의 횃불을 다시 세웠다.",
                target = "black wolf pup",
                count = 1,
                min_level = 1,
                max_level = 5,
                narrative_scenes = new[]
                {
                    new
                    {
                        node_id = "talk",
                        scene_type = "Intro",
                        title = "젖은 울타리",
                        body = "Brother Penric은 Albion 수도원 울타리의 젖은 흙 위에 남은 {{target}} 발자국을 낮게 가리켰다. 밤마다 종소리가 끊기고 아이들이 길을 피해 돌아간다고 말했다.",
                        journal_entry = "Brother Penric에게서 Albion 수도원 울타리 근처의 {{target}} 위협을 막아 달라는 부탁을 받았다.",
                        mood = "ominous",
                        reveal_policy = "FirstSeenOnly"
                    },
                    new
                    {
                        node_id = "explore",
                        scene_type = "Discovery",
                        title = "성벽 그림자",
                        body = "브리튼 성벽 그림자 아래의 찢긴 천과 발자국이 같은 곳을 가리킨다. {{target}}를 지금 제압하지 못하면 수도원 길목은 더 오래 비게 될 것이다.",
                        journal_entry = "Albion 수도원 울타리의 증거가 {{target}} 은신처로 이어진다는 사실을 확인했다.",
                        mood = "urgent",
                        reveal_policy = "EveryInteraction"
                    },
                    new
                    {
                        node_id = "return",
                        scene_type = "Return",
                        title = "다시 선 횃불",
                        body = "{{target}} 위협을 꺾자 수도원 울타리 근처의 횃불이 다시 곧게 섰다. Brother Penric에게 돌아가면 Albion 길목이 다시 안전해졌다고 전할 수 있다.",
                        journal_entry = "{{target}}를 제압했다. Brother Penric에게 Albion 수도원 길목이 안정됐다고 알려야 한다.",
                        mood = "relieved",
                        reveal_policy = "FirstSeenOnly"
                    }
                },
                presentation_beats = new[]
                {
                    new
                    {
                        node_id = "talk",
                        trigger = "OnNpcInteract",
                        speaker = "StartNpc",
                        text = "목소리를 낮추세요. 저 발자국은 방금 생긴 겁니다.",
                        emotion = "fear",
                        emote = "Shiver"
                    },
                    new
                    {
                        node_id = "return",
                        trigger = "OnComplete",
                        speaker = "StartNpc",
                        text = "오늘 밤은 수도원 울타리의 불을 꺼도 되겠군요.",
                        emotion = "gratitude",
                        emote = "Bow"
                    }
                }
            });

            return JsonSerializer.Serialize(new
            {
                output = new[]
                {
                    new
                    {
                        content = new[]
                        {
                            new
                            {
                                type = "output_text",
                                text = storyJson
                            }
                        }
                    }
                }
            });
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

            public DynamicQuestStoryGenerationResult TryGenerate(DynamicQuestStoryRequest request)
            {
                return m_result;
            }
        }

        private sealed class ScopedEnvironment : IDisposable
        {
            private readonly string m_name;
            private readonly string m_previous;

            public ScopedEnvironment(string name, string value)
            {
                m_name = name;
                m_previous = Environment.GetEnvironmentVariable(name);
                Environment.SetEnvironmentVariable(name, value);
            }

            public void Dispose()
            {
                Environment.SetEnvironmentVariable(m_name, m_previous);
            }
        }

        private sealed class MemoryDailyQuotaStore : IDynamicQuestDailyQuotaStore
        {
            private readonly Dictionary<string, int> m_counts = new(StringComparer.OrdinalIgnoreCase);

            public bool TryReserveDaily(string providerName, DateTime pacificDay, int dailyLimit)
            {
                string key = $"{providerName}:{pacificDay:yyyy-MM-dd}";
                m_counts.TryGetValue(key, out int count);
                if (count >= dailyLimit)
                    return false;

                m_counts[key] = count + 1;
                return true;
            }
        }

        private sealed class MemoryTokenBudgetStore : IDynamicQuestTokenBudgetStore
        {
            private readonly Dictionary<string, int> m_tokens = new(StringComparer.OrdinalIgnoreCase);

            public DynamicQuestTokenReservation TryReserveTokens(
                string providerName,
                DateTime pacificDay,
                int dailyTokenLimit,
                int estimatedTokens,
                out string error)
            {
                error = string.Empty;
                string key = Key(providerName, pacificDay);
                m_tokens.TryGetValue(key, out int tokens);
                if (tokens + estimatedTokens > dailyTokenLimit)
                {
                    error = $"{providerName}_token_quota_exhausted";
                    return null;
                }

                m_tokens[key] = tokens + estimatedTokens;
                return new DynamicQuestTokenReservation(providerName, pacificDay, estimatedTokens);
            }

            public void FinalizeTokens(DynamicQuestTokenReservation reservation, int actualTokens)
            {
                string key = Key(reservation.ProviderName, reservation.PacificDay);
                m_tokens.TryGetValue(key, out int tokens);
                m_tokens[key] = Math.Max(0, tokens + actualTokens - reservation.EstimatedTokens);
            }

            public void CancelTokens(DynamicQuestTokenReservation reservation)
            {
                string key = Key(reservation.ProviderName, reservation.PacificDay);
                m_tokens.TryGetValue(key, out int tokens);
                m_tokens[key] = Math.Max(0, tokens - reservation.EstimatedTokens);
            }

            public int Spent(string providerName, DateTime pacificDay)
            {
                m_tokens.TryGetValue(Key(providerName, pacificDay), out int tokens);
                return tokens;
            }

            private static string Key(string providerName, DateTime pacificDay)
            {
                return $"{providerName}:{pacificDay:yyyy-MM-dd}";
            }
        }
    }
}
