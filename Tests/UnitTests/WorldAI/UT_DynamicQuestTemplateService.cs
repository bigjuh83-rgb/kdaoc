using System;
using System.Linq;
using DOL.Database;
using DOL.GS.WorldAI;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_DynamicQuestTemplateService
    {
        [Test]
        public void BindTemplate_StoresStoryIntentButBindsCurrentWorldTarget()
        {
            DynamicQuestTemplate template = StoryTemplate();
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult first = service.BindTemplate(template, new[]
            {
                SeedNpc("Brother Penric", "penric-1", 1, 10, 518850, 494050, 3352),
                SeedNpc("black wolf pup", "wolf-1", 1, 1, 522000, 492000, 2954)
            });
            DynamicQuestTemplateBindingResult rebound = service.BindTemplate(template, new[]
            {
                SeedNpc("Brother Penric", "penric-1", 1, 10, 518850, 494050, 3352),
                SeedNpc("forest spiderling", "spider-1", 1, 1, 522000, 492000, 2954)
            });

            Assert.Multiple(() =>
            {
                Assert.That(first.Success, Is.True);
                Assert.That(rebound.Success, Is.True);
                Assert.That(first.Quest.Id, Is.EqualTo("template-wolf-trouble"));
                Assert.That(rebound.Quest.Id, Is.EqualTo("template-wolf-trouble"));
                Assert.That(first.BindingKey, Is.Not.EqualTo(rebound.BindingKey));
                Assert.That(first.Quest.TargetName, Is.EqualTo("black wolf pup"));
                Assert.That(rebound.Quest.TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(rebound.Quest.OfferText, Does.Contain("밤마다 숲의 소리가 달라졌습니다"));
                Assert.That(rebound.Quest.Tags, Does.Contain("template:template-wolf-trouble"));
                Assert.That(rebound.Quest.Tags.Any(tag => tag.StartsWith("binding:", StringComparison.OrdinalIgnoreCase)), Is.True);
            });
        }

        [Test]
        public void BindTemplate_RendersStoryPlaceholdersInTopLevelTexts()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.Title = "{{realm}}의 {{target}} 징조";
            template.OfferText = "{{start_npc}}가 {{target}} 조사를 부탁합니다.";
            template.ProgressText = "{{target}}의 흔적은 아직 사라지지 않았습니다.";
            template.FinishText = "{{target}} 위협이 사라졌습니다.";
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Brother Penric", "penric-1", 1, 10, 518850, 494050, 3352),
                SeedNpc("forest spiderling", "spider-1", 1, 1, 522000, 492000, 2954)
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.Title, Is.EqualTo("Albion의 forest spiderling 징조"));
                Assert.That(result.Quest.OfferText, Is.EqualTo("Brother Penric가 forest spiderling 조사를 부탁합니다."));
                Assert.That(result.Quest.ProgressText, Is.EqualTo("forest spiderling의 흔적은 아직 사라지지 않았습니다."));
                Assert.That(result.Quest.FinishText, Is.EqualTo("forest spiderling 위협이 사라졌습니다."));
                Assert.That(result.Quest.ProgressText, Does.Not.Contain("{{target}}"));
                Assert.That(result.Quest.FinishText, Does.Not.Contain("{{target}}"));
            });
        }

        [Test]
        public void BindTemplate_RendersStoryPlaceholdersInNarrativeAndPresentationMetadata()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"title\":\"{{realm}}의 불안\",\"body\":\"{{start_npc}}가 {{target}} 흔적을 말한다.\",\"journalEntry\":\"{{target}} 조사 시작\"}]";
            template.StoryPresentationJson = "[{\"nodeId\":\"talk\",\"speaker\":\"StartNpc\",\"emotion\":\"fear\",\"emote\":\"Shiver\",\"text\":\"{{target}} 때문에 모두가 떨고 있습니다.\"}]";
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Brother Penric", "penric-1", 1, 10, 518850, 494050, 3352),
                SeedNpc("forest spiderling", "spider-1", 1, 1, 522000, 492000, 2954)
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.StoryNarrativeJson, Does.Contain("Albion의 불안"));
                Assert.That(result.Quest.StoryNarrativeJson, Does.Contain("Brother Penric가 forest spiderling 흔적을 말한다."));
                Assert.That(result.Quest.StoryNarrativeJson, Does.Not.Contain("{{target}}"));
                Assert.That(result.Quest.StoryPresentationJson, Does.Contain("forest spiderling 때문에 모두가 떨고 있습니다."));
                Assert.That(result.Quest.StoryPresentationJson, Does.Not.Contain("{{target}}"));
            });
        }

        [Test]
        public void BindTemplate_AppliesKoreanParticlesAfterStoryPlaceholderRendering()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.PreferredStartNpcName = "Gothi of Odin";
            template.PreferredRegionId = 100;
            template.OfferText = "{{start_npc}}이(가) {{target}}을(를) 막아 달라고 부탁합니다.";
            template.ProgressText = "{{target}}이(가) 아직 남아 있습니다.";
            template.FinishText = "{{target}}을(를) 제압했습니다.";
            template.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"body\":\"{{start_npc}}은(는) {{target}}이(가) 지나간 흔적을 가리켰다.\"}]";
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Gothi of Odin", "gothi-1", 100, 10, 802000, 720000, 4900),
                SeedNpc("young sveawolf", "sveawolf-1", 100, 1, 803000, 720500, 4900)
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.OfferText, Is.EqualTo("Gothi of Odin이 young sveawolf를 막아 달라고 부탁합니다."));
                Assert.That(result.Quest.ProgressText, Is.EqualTo("young sveawolf가 아직 남아 있습니다."));
                Assert.That(result.Quest.FinishText, Is.EqualTo("young sveawolf를 제압했습니다."));
                Assert.That(result.Quest.StoryNarrativeJson, Does.Contain("Gothi of Odin은 young sveawolf가 지나간 흔적을 가리켰다."));
                Assert.That(result.Quest.OfferText, Does.Not.Contain("이(가)"));
                Assert.That(result.Quest.OfferText, Does.Not.Contain("을(를)"));
                Assert.That(result.Quest.ProgressText, Does.Not.Contain("이(가)"));
            });
        }

        [Test]
        public void BindTemplate_PrefersTransientSeedTargetOverFarStoryNameHint()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.TargetNameHint = "soft-shelled crab";
            template.PreferredTargetNpcInternalId = "near-selected-target";
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Brother Penric", "penric-1", 1, 10, 518850, 494050, 3352),
                SeedNpc("young sveawolf", "near-selected-target", 1, 1, 520000, 494000, 3352),
                SeedNpc("soft-shelled crab", "far-story-name-target", 1, 1, 580000, 494000, 3352)
            });

            DynamicQuestNode explore = result.Quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Explore);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.TargetName, Is.EqualTo("young sveawolf"));
                Assert.That(explore.Objective.X, Is.EqualTo(520000));
                Assert.That(explore.Objective.Y, Is.EqualTo(494000));
            });
        }

        [Test]
        public void BindTemplate_StarterBindingPrefersSafePreyOverUnsafeStoryNameHint()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.PreferredStartNpcName = "Sir Lukas";
            template.TargetNameHint = "large ant";
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Sir Lukas", "lukas-1", 1, 30, 530000, 501000, 3000),
                SeedNpc("large ant", "ant-1", 1, 1, 531600, 501000, 3000),
                SeedNpc("boar piglet", "piglet-1", 1, 1, 532400, 501000, 3000)
            });

            DynamicQuestNode explore = result.Quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Explore);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.StartNpcName, Is.EqualTo("Sir Lukas"));
                Assert.That(result.Quest.TargetName, Is.EqualTo("boar piglet"));
                Assert.That(explore.Objective.X, Is.EqualTo(532400));
            });
        }

        [Test]
        public void BindTemplate_StarterBindingSkipsPinnedGrowthRiskWhenSafeAlternativeExists()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.PreferredStartNpcName = "Sir Lukas";
            template.TargetNameHint = "black wolf pup";
            template.PreferredTargetNpcInternalId = "target-risk-wolf";
            DynamicQuestTemplateService service = new();

            DynamicQuestSeedNpc riskyWolf = SeedNpc("black wolf pup", "target-risk-wolf", 1, 1, 501800, 500000, 3000);
            riskyWolf.NameGrowthThreatCount = 5;
            riskyWolf.NameGrowthMaxScore = 5200;
            riskyWolf.NameGrowthMaxEffectiveLevel = 4;
            riskyWolf.NameGrowthPlayerKills = 11;
            DynamicQuestSeedNpc rawPrefixedWolf = SeedNpc("black wolf pup", "target-raw-risk-wolf", 1, 4, 502200, 500000, 3000);
            rawPrefixedWolf.RawName = "흉포한 black wolf pup";

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Sir Lukas", "lukas-1", 1, 30, 500000, 500000, 3000),
                riskyWolf,
                rawPrefixedWolf,
                SeedNpc("ant drone", "target-safe-ant", 1, 2, 508200, 500000, 3000)
            });

            DynamicQuestNode explore = result.Quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Explore);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.TargetName, Is.EqualTo("ant drone"));
                Assert.That(explore.Objective.X, Is.EqualTo(508200));
            });
        }

        [Test]
        public void BindTemplate_StarterBindingSkipsFarPinnedTargetAndUsesNearbySafeTarget()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.PreferredStartNpcName = "Sir Lukas";
            template.PreferredTargetNpcInternalId = "far-wolf";
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Sir Lukas", "lukas-1", 1, 30, 500000, 500000, 3000),
                SeedNpc("black wolf pup", "far-wolf", 1, 1, 540000, 500000, 3000),
                SeedNpc("forest spiderling", "near-spider", 1, 1, 504000, 500000, 3000)
            });

            DynamicQuestNode explore = result.Quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Explore);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(explore.Objective.X, Is.EqualTo(504000));
            });
        }

        [Test]
        public void BindTemplate_StarterTaggedNpcOfferHighBandSkipsDistantStoryHint()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.PreferredStartNpcName = "Gothi of Odin";
            template.TargetNameHint = "wood ogre lord";
            template.MinLevel = 15;
            template.MaxLevel = 16;
            template.Tags = new[] { "llm-story", "starter", "branch:mob-growth" };
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Gothi of Odin", "gothi-1", 1, 30, 642000, 322000, 3000),
                SeedNpc("wood ogre lord", "far-ogre", 1, 16, 507002, 624174, 2815),
                SeedNpc("forest spiderling", "near-spider", 1, 1, 645500, 323000, 3000)
            });

            DynamicQuestNode explore = result.Quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Explore);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(explore.Objective.X, Is.EqualTo(645500));
            });
        }

        [Test]
        public void BindTemplate_StarterTaggedNpcOfferHighBandRebindsStartWhenPreferredHasNoNearbyTarget()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.PreferredStartNpcName = "Gothi of Odin";
            template.TargetNameHint = "wood ogre lord";
            template.MinLevel = 15;
            template.MaxLevel = 16;
            template.Tags = new[] { "llm-story", "starter", "branch:mob-growth" };
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Gothi of Odin", "gothi-1", 1, 30, 642000, 322000, 3000),
                SeedNpc("wood ogre lord", "far-ogre", 1, 16, 507002, 624174, 2815),
                SeedNpc("Brother Penric", "penric-1", 1, 30, 518850, 494050, 3352),
                SeedNpc("forest spiderling", "near-spider", 1, 1, 522000, 494000, 3352)
            });

            DynamicQuestNode explore = result.Quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Explore);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.StartNpcName, Is.EqualTo("Brother Penric"));
                Assert.That(result.Quest.TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(explore.Objective.X, Is.EqualTo(522000));
            });
        }

        [Test]
        public void BindTemplate_StarterBindingFailsWhenOnlyTargetRouteIsDangerous()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.PreferredStartNpcName = "Sir Lukas";
            template.TargetNameHint = "boar piglet";
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Sir Lukas", "lukas-1", 1, 30, 500000, 500000, 3000),
                SeedNpc("흉포한 large ant", "route-threat", 1, 4, 502000, 500100, 3000, hasSourceNpcMetadata: true),
                SeedNpc("boar piglet", "target-route-risk", 1, 1, 504000, 500000, 3000)
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.False);
                Assert.That(result.Message, Does.Contain("target npc not found"));
            });
        }

        [Test]
        public void BindTemplate_StarterBindingIgnoresPinnedTargetInDifferentRegion()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.PreferredStartNpcName = "Sir Lukas";
            template.PreferredRegionId = 0;
            template.PreferredTargetNpcInternalId = "mid-wolf";
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Sir Lukas", "lukas-1", 1, 30, 500000, 500000, 3000),
                SeedNpc("black wolf pup", "mid-wolf", 100, 1, 501000, 500000, 3000),
                SeedNpc("forest spiderling", "alb-spider", 1, 1, 504000, 500000, 3000)
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(result.Quest.StartRegionId, Is.EqualTo(1));
            });
        }

        [Test]
        public void BindTemplate_StarterBindingFailsWhenNoSafeTargetIsNearStart()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.PreferredStartNpcName = "Sir Lukas";
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Sir Lukas", "lukas-1", 1, 30, 500000, 500000, 3000),
                SeedNpc("forest spiderling", "far-spider", 1, 1, 540000, 500000, 3000)
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.False);
                Assert.That(result.Message, Does.Contain("target npc not found"));
            });
        }

        [Test]
        public void TemplateRepository_RoundTripsStoryWithoutConcreteBinding()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.StartMode = DynamicQuestStartMode.AutoAccept;
            template.Trigger = "rift-entered";
            FakeDynamicQuestTemplateRepository repository = new();

            repository.Add(DynamicQuestTemplateService.ToRowForTest(template));

            DynamicQuestTemplate loaded = DynamicQuestTemplateService.FromRowForTest(repository.GetActive().Single());

            Assert.Multiple(() =>
            {
                Assert.That(loaded.TemplateId, Is.EqualTo(template.TemplateId));
                Assert.That(loaded.StorySeed, Is.EqualTo(template.StorySeed));
                Assert.That(loaded.PreferredStartNpcName, Is.EqualTo("Brother Penric"));
                Assert.That(loaded.TargetNameHint, Is.EqualTo("black wolf pup"));
                Assert.That(loaded.StartMode, Is.EqualTo(DynamicQuestStartMode.AutoAccept));
                Assert.That(loaded.Trigger, Is.EqualTo("rift-entered"));
                Assert.That(loaded.StoryModel, Is.EqualTo("gemma-test"));
                Assert.That(loaded.Tags, Does.Contain("llm-story"));
                Assert.That(repository.GetActive().Single().StoryModel, Is.EqualTo("gemma-test"));
                Assert.That(repository.GetActive().Single().StartNpcInternalId, Is.EqualTo(string.Empty));
                Assert.That(repository.GetActive().Single().LastBindingKey, Is.EqualTo(string.Empty));
            });
        }

        [Test]
        public void TemplateRepository_RoundTripsQualityNarrativeAndPresentationJson()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.StoryQualityJson = "{\"totalScore\":91}";
            template.StoryNarrativeJson = "[{\"nodeId\":\"talk\",\"title\":\"숲의 숨죽임\"}]";
            template.StoryPresentationJson = "[{\"nodeId\":\"talk\",\"emotion\":\"fear\",\"emote\":\"Shiver\"}]";
            FakeDynamicQuestTemplateRepository repository = new();

            repository.Add(DynamicQuestTemplateService.ToRowForTest(template));
            DynamicQuestTemplate loaded = DynamicQuestTemplateService.FromRowForTest(repository.GetActive().Single());
            DynamicQuestTemplateBindingResult bound = new DynamicQuestTemplateService().BindTemplate(loaded, new[]
            {
                SeedNpc("Brother Penric", "penric-1", 1, 10, 518850, 494050, 3352),
                SeedNpc("black wolf pup", "wolf-1", 1, 1, 522000, 492000, 2954)
            });

            Assert.Multiple(() =>
            {
                Assert.That(loaded.StoryQualityJson, Does.Contain("totalScore"));
                Assert.That(loaded.StoryNarrativeJson, Does.Contain("숲의 숨죽임"));
                Assert.That(loaded.StoryPresentationJson, Does.Contain("Shiver"));
                Assert.That(repository.GetActive().Single().StoryQualityJson, Does.Contain("totalScore"));
                Assert.That(bound.Success, Is.True, bound.Message);
                Assert.That(bound.Quest.StoryNarrativeJson, Does.Contain("숲의 숨죽임"));
                Assert.That(bound.Quest.StoryPresentationJson, Does.Contain("Shiver"));
            });
        }

        [Test]
        public void BindTemplate_WorldOfferBuildsNpcLessQuestFromCurrentWorldTarget()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.TemplateId = "template-rift";
            template.PreferredStartNpcName = string.Empty;
            template.TargetNameHint = "forest spiderling";
            template.StartMode = DynamicQuestStartMode.AutoAccept;
            template.Trigger = "rift-entered";
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("forest spiderling", "spider-1", 1, 1, 522000, 492000, 2954)
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.Id, Is.EqualTo("template-rift"));
                Assert.That(result.Quest.StartMode, Is.EqualTo(DynamicQuestStartMode.AutoAccept));
                Assert.That(result.Quest.StartNpcInternalId, Is.EqualTo(string.Empty));
                Assert.That(result.Quest.StartNpcName, Is.EqualTo(string.Empty));
                Assert.That(result.Quest.StartRegionId, Is.EqualTo(1));
                Assert.That(result.Quest.TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(result.Quest.StartNodeId, Is.EqualTo("explore"));
                Assert.That(result.Quest.Nodes.Select(node => node.Type), Is.EqualTo(new[]
                {
                    DynamicQuestNodeType.Explore,
                    DynamicQuestNodeType.Kill,
                    DynamicQuestNodeType.Complete
                }));
                Assert.That(result.Quest.Tags, Does.Contain("trigger:rift-entered"));
                Assert.That(result.Quest.Tags, Does.Contain("start-mode:AutoAccept"));
                Assert.That(result.Quest.Tags.Any(tag => tag.StartsWith("binding:", StringComparison.OrdinalIgnoreCase)), Is.True);
            });
        }

        [Test]
        public void BindTemplate_AutoAcceptItemAcquiredBranchDoesNotUseItemAcquiredAsStartTrigger()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.TemplateId = "template-item-branch";
            template.PreferredStartNpcName = string.Empty;
            template.TargetNameHint = "forest spiderling";
            template.StartMode = DynamicQuestStartMode.AutoAccept;
            template.Trigger = "item-acquired";
            template.Tags = new[] { "llm-story", "starter", "branch:item-acquired", "world-signal:item-acquired" };
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("forest spiderling", "spider-1", 1, 1, 522000, 492000, 2954)
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.StartMode, Is.EqualTo(DynamicQuestStartMode.AutoAccept));
                Assert.That(result.Quest.Tags, Does.Contain("branch:item-acquired"));
                Assert.That(result.Quest.Tags, Does.Contain("world-signal:item-acquired"));
                Assert.That(result.Quest.Tags, Does.Contain("region:1"));
                Assert.That(result.Quest.Tags, Does.Not.Contain("trigger:item-acquired"));
            });
        }

        [Test]
        public void BindTemplate_ClampsKillObjectiveToNearbyTargetCluster()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.TemplateId = "template-sparse-boggart";
            template.PreferredStartNpcName = "Boggart Watcher";
            template.TargetNameHint = "boggart";
            template.Count = 3;
            template.MinLevel = 48;
            template.MaxLevel = 50;
            template.Tags = new[] { "llm-story" };
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Boggart Watcher", "watcher-1", 1, 50, 617000, 388000, 5681),
                SeedNpc("boggart", "boggart-48", 1, 48, 618469, 388858, 5681),
                SeedNpc("boggart", "boggart-45", 1, 45, 618498, 389564, 5279),
                SeedNpc("boggart", "boggart-38", 1, 38, 618700, 389000, 5279),
                SeedNpc("boggart", "boggart-49-far", 1, 49, 640000, 410000, 5279)
            });

            DynamicQuestNode kill = result.Quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Kill);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.TargetName, Is.EqualTo("boggart"));
                Assert.That(result.Quest.TargetCount, Is.EqualTo(2));
                Assert.That(result.Quest.MinLevel, Is.EqualTo(48));
                Assert.That(result.Quest.MaxLevel, Is.EqualTo(50));
                Assert.That(kill.Objective.TargetCount, Is.EqualTo(2));
                Assert.That(kill.Objective.MinLevel, Is.EqualTo(45));
                Assert.That(kill.Objective.MaxLevel, Is.EqualTo(48));
            });
        }

        [Test]
        public void BindTemplate_AutoAcceptUsesSingleSoloTargetCount()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.TemplateId = "template-auto-boggart";
            template.PreferredStartNpcName = string.Empty;
            template.TargetNameHint = "boggart";
            template.StartMode = DynamicQuestStartMode.AutoAccept;
            template.Count = 3;
            template.MinLevel = 48;
            template.MaxLevel = 50;
            template.ProgressText = "{{target}} {{count}}마리를 처치하세요.";
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("boggart", "boggart-48", 1, 48, 618469, 388858, 5681),
                SeedNpc("boggart", "boggart-45", 1, 45, 618498, 389564, 5279),
                SeedNpc("boggart", "boggart-49", 1, 49, 618700, 389000, 5279)
            });

            DynamicQuestNode kill = result.Quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Kill);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.StartMode, Is.EqualTo(DynamicQuestStartMode.AutoAccept));
                Assert.That(result.Quest.TargetCount, Is.EqualTo(1));
                Assert.That(kill.Objective.TargetCount, Is.EqualTo(1));
                Assert.That(result.Quest.ProgressText, Does.Contain("1마리"));
                Assert.That(kill.Text, Does.Contain("1마리"));
            });
        }

        [Test]
        public void BindTemplate_AutoAcceptRebindsPinnedNamedTargetToSaferSoloTarget()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.TemplateId = "template-auto-named";
            template.PreferredStartNpcName = string.Empty;
            template.TargetNameHint = "Agisthil";
            template.PreferredTargetNpcInternalId = "named-agisthil";
            template.StartMode = DynamicQuestStartMode.AutoAccept;
            template.Count = 2;
            template.MinLevel = 12;
            template.MaxLevel = 12;
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Agisthil", "named-agisthil", 1, 12, 537342, 451714, 2972),
                SeedNpc("hill cat", "safe-cat", 1, 12, 537900, 451900, 2972),
                SeedNpc("forest bandit", "unsafe-bandit", 1, 12, 538200, 451900, 2972)
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.StartMode, Is.EqualTo(DynamicQuestStartMode.AutoAccept));
                Assert.That(result.Quest.TargetName, Is.EqualTo("hill cat"));
                Assert.That(result.Quest.TargetCount, Is.EqualTo(1));
                Assert.That(result.Quest.Tags.Any(tag => tag.StartsWith("binding:", StringComparison.OrdinalIgnoreCase)), Is.True);
            });
        }

        [Test]
        public void BindTemplate_AutoAcceptDoesNotTreatQuestGiverAsTargetAreaThreat()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.TemplateId = "template-auto-hinted-near-giver";
            template.PreferredStartNpcName = string.Empty;
            template.TargetNameHint = "blackthorn sapling";
            template.StartMode = DynamicQuestStartMode.AutoAccept;
            template.Count = 1;
            template.MinLevel = 1;
            template.MaxLevel = 5;
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Brother Penric", "seed-npc-1", 1, 30, 500000, 500000, 3000),
                SeedNpc("black wolf pup", "configured-target", 1, 1, 502000, 500000, 3000),
                SeedNpc("blackthorn sapling", "story-target", 1, 1, 500000, 500000, 3000)
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.StartMode, Is.EqualTo(DynamicQuestStartMode.AutoAccept));
                Assert.That(result.Quest.TargetName, Is.EqualTo("blackthorn sapling"));
            });
        }

        [Test]
        public void BindTemplate_AutoAcceptRebindsMultiWordProperNamedTargetToSaferSoloTarget()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.TemplateId = "template-auto-proper-name";
            template.PreferredStartNpcName = string.Empty;
            template.TargetNameHint = "Aldous Wynedd";
            template.StartMode = DynamicQuestStartMode.AutoAccept;
            template.Count = 1;
            template.MinLevel = 10;
            template.MaxLevel = 10;
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Aldous Wynedd", "proper-named-target", 1, 10, 533126, 466691, 6327),
                SeedNpc("hill cat", "safe-cat", 1, 10, 533300, 466700, 6327)
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.TargetName, Is.EqualTo("hill cat"));
                Assert.That(result.Quest.TargetCount, Is.EqualTo(1));
            });
        }

        [Test]
        public void BindTemplate_AutoAcceptRebindsInvalidDisplayTargetNameToSaferSoloTarget()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.TemplateId = "template-auto-invalid-display-name";
            template.PreferredStartNpcName = string.Empty;
            template.TargetNameHint = "Total: 0 DPS: 0";
            template.PreferredRegionId = 200;
            template.StartMode = DynamicQuestStartMode.AutoAccept;
            template.Count = 1;
            template.MinLevel = 10;
            template.MaxLevel = 10;
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Total: 0 DPS: 0", "invalid-display-target", 200, 10, 334064, 419472, 5184),
                SeedNpc("anger sprite", "safe-sprite", 200, 10, 334300, 419500, 5184)
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                if (result.Success)
                {
                    Assert.That(result.Quest.TargetName, Is.EqualTo("anger sprite"));
                    Assert.That(result.Quest.TargetCount, Is.EqualTo(1));
                }
            });
        }

        [Test]
        public void BindTemplate_AutoAcceptPrefersStarterSafeFallbackOverDangerousStoryLevelTarget()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.TemplateId = "template-auto-dangerous-story-target";
            template.PreferredStartNpcName = string.Empty;
            template.TargetNameHint = "convert guard";
            template.StartMode = DynamicQuestStartMode.AutoAccept;
            template.Count = 3;
            template.MinLevel = 8;
            template.MaxLevel = 12;
            DynamicQuestTemplateService service = new();

            DynamicQuestSeedNpc growthCorpseEater = SeedNpc("corpse eater", "growth-corpse-eater", 1, 12, 577700, 491700, 2649);
            growthCorpseEater.RawName = "흉포한 corpse eater";
            growthCorpseEater.NameGrowthThreatCount = 2;
            growthCorpseEater.NameGrowthMaxEffectiveLevel = 14;
            growthCorpseEater.NameGrowthPlayerKills = 1;

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("convert guard", "dangerous-guard", 1, 9, 577400, 491609, 2649),
                growthCorpseEater,
                SeedNpc("forest spiderling", "starter-safe-spider", 1, 1, 579000, 492500, 2649)
            });

            DynamicQuestNode kill = result.Quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Kill);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.StartMode, Is.EqualTo(DynamicQuestStartMode.AutoAccept));
                Assert.That(result.Quest.TargetName, Is.EqualTo("forest spiderling"));
                Assert.That(result.Quest.TargetCount, Is.EqualTo(1));
                Assert.That(kill.Objective.MinLevel, Is.EqualTo(1));
                Assert.That(kill.Objective.MaxLevel, Is.EqualTo(1));
            });
        }

        [Test]
        public void BindTemplate_AutoAcceptAllowsLevelFiveFallbackWhenNoLowerStarterTargetExists()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.TemplateId = "template-auto-hibernia-fallback";
            template.PreferredStartNpcName = string.Empty;
            template.PreferredRegionId = 200;
            template.TargetNameHint = "lough wolf cadger";
            template.StartMode = DynamicQuestStartMode.AutoAccept;
            template.MinLevel = 14;
            template.MaxLevel = 18;
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("lough wolf cadger", "dangerous-wolf-cadger", 200, 14, 292411, 458413, 6630),
                SeedNpc("large frog", "starter-frog", 200, 4, 294000, 460000, 6630)
            });

            DynamicQuestNode kill = result.Quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Kill);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.TargetName, Is.EqualTo("large frog"));
                Assert.That(kill.Objective.MinLevel, Is.EqualTo(4));
                Assert.That(kill.Objective.MaxLevel, Is.EqualTo(4));
            });
        }

        [Test]
        public void BindTemplate_AutoAcceptDoesNotTrustUnknownLevelHighBandStoryTarget()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.TemplateId = "template-auto-unknown-level";
            template.PreferredStartNpcName = string.Empty;
            template.PreferredRegionId = 100;
            template.TargetNameHint = "little water goblin";
            template.StartMode = DynamicQuestStartMode.AutoAccept;
            template.MinLevel = 13;
            template.MaxLevel = 17;
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("little water goblin", "unknown-story-target", 100, 0, 815190, 917322, 4744),
                SeedNpc("soft-shelled crab", "starter-crab", 100, 3, 815500, 917600, 4744)
            });

            DynamicQuestNode kill = result.Quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Kill);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.TargetName, Is.EqualTo("soft-shelled crab"));
                Assert.That(kill.Objective.MinLevel, Is.EqualTo(3));
                Assert.That(kill.Objective.MaxLevel, Is.EqualTo(3));
            });
        }

        [Test]
        public void BindTemplate_AutoAcceptRebindsStarterTargetAwayFromNearbyGrowthThreat()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.TemplateId = "template-auto-growth-near-target";
            template.PreferredStartNpcName = string.Empty;
            template.TargetNameHint = "muck snake";
            template.StartMode = DynamicQuestStartMode.AutoAccept;
            template.MinLevel = 1;
            template.MaxLevel = 4;
            DynamicQuestTemplateService service = new();

            DynamicQuestSeedNpc growthBogman = SeedNpc("흉포한 scrawny bogman", "growth-bogman", 1, 5, 465536, 622464, 1688, hasSourceNpcMetadata: true);
            growthBogman.RawName = "흉포한 scrawny bogman";
            growthBogman.GrowthEffectiveLevel = 5;

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("muck snake", "unsafe-muck-snake", 1, 1, 465331, 622549, 1645),
                growthBogman,
                SeedNpc("slime lizard", "safe-lizard", 1, 1, 470000, 622549, 1645)
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.StartMode, Is.EqualTo(DynamicQuestStartMode.AutoAccept));
                Assert.That(result.Quest.TargetName, Is.EqualTo("slime lizard"));
                Assert.That(result.Quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Explore).Objective.X, Is.EqualTo(470000));
            });
        }

        [Test]
        public void BindTemplate_AutoAcceptSkipsStarterQuestWhenOnlyUnsafeAreaTargetsExist()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.TemplateId = "template-auto-only-unsafe-growth-area";
            template.PreferredStartNpcName = string.Empty;
            template.TargetNameHint = "muck snake";
            template.StartMode = DynamicQuestStartMode.AutoAccept;
            template.MinLevel = 1;
            template.MaxLevel = 4;
            DynamicQuestTemplateService service = new();

            DynamicQuestSeedNpc growthBogman = SeedNpc("흉포한 scrawny bogman", "growth-bogman", 1, 5, 465536, 622464, 1688, hasSourceNpcMetadata: true);
            growthBogman.RawName = "흉포한 scrawny bogman";
            growthBogman.GrowthEffectiveLevel = 5;

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("muck snake", "unsafe-muck-snake", 1, 1, 465331, 622549, 1645),
                growthBogman
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.False);
                Assert.That(result.Message, Does.Contain("target npc not found"));
            });
        }

        [Test]
        public void BindTemplate_AutoAcceptHighBandSkipsUnsafeLowLevelFallbackTargetArea()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.TemplateId = "template-auto-high-band-unsafe-low-fallback";
            template.PreferredStartNpcName = string.Empty;
            template.TargetNameHint = "muck snake";
            template.StartMode = DynamicQuestStartMode.AutoAccept;
            template.MinLevel = 15;
            template.MaxLevel = 19;
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("muck snake", "unsafe-low-fallback", 1, 1, 476739, 631156, 1575),
                SeedNpc("bogman gatherer", "nearby-high-threat", 1, 8, 477500, 630740, 1604, hasSourceNpcMetadata: true)
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.False);
                Assert.That(result.Message, Does.Contain("target npc not found"));
            });
        }

        [Test]
        public void BindTemplate_WithMobGrowthWorldSignalTagBuildsOptionalSignalBranch()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.Tags = new[] { "llm-story", "branch:mob-growth", "world-signal:mob-growth:killed:boss" };
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc("Brother Penric", "penric-1", 1, 10, 518850, 494050, 3352),
                SeedNpc("forest spiderling", "spider-1", 1, 1, 522000, 492000, 2954)
            });

            DynamicQuestNode choice = result.Quest.Nodes.Single(node => node.Id == "choice");
            DynamicQuestNode observe = result.Quest.Nodes.Single(node => node.Id == "observe_signal");
            DynamicQuestEdge followup = choice.Edges.Single(edge => edge.ConditionValue == "followup");
            DynamicQuestEdge signal = observe.Edges.Single(edge => edge.Condition == DynamicQuestEdgeCondition.WorldSignal);
            DynamicQuestEdge timeout = observe.Edges.Single(edge => edge.Condition == DynamicQuestEdgeCondition.TimedOut);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(followup.ToNodeId, Is.EqualTo("observe_signal"));
                Assert.That(observe.Type, Is.EqualTo(DynamicQuestNodeType.Explore));
                Assert.That(observe.Objective.RegionId, Is.EqualTo(1));
                Assert.That(observe.Objective.X, Is.EqualTo(522000));
                Assert.That(observe.Objective.Y, Is.EqualTo(492000));
                Assert.That(signal.Condition, Is.EqualTo(DynamicQuestEdgeCondition.WorldSignal));
                Assert.That(signal.ConditionValue, Is.EqualTo("mob-growth:killed:boss"));
                Assert.That(signal.ToNodeId, Is.EqualTo("complete"));
                Assert.That(timeout.ToNodeId, Is.EqualTo("complete"));
                Assert.That(timeout.ConditionValue, Is.EqualTo(DynamicQuestWorldSignalPolicy.FallbackTimeoutSeconds));
                Assert.That(result.Quest.Tags, Does.Contain("world-signal:mob-growth:killed:boss"));
                Assert.That(result.Quest.Tags.Any(tag => tag.Contains("mob:", StringComparison.OrdinalIgnoreCase)), Is.False);
            });
        }

        [Test]
        public void BindTemplate_AvoidsHastenerStartNpcWhenPeaceCandidateExists()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.PreferredStartNpcName = "Minstrel of Albion";
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc(
                    "Minstrel of Albion",
                    "hastener-1",
                    1,
                    50,
                    518000,
                    494000,
                    3352,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.Albion,
                    sourceFlags: GameNPC.eFlags.PEACE,
                    sourceTypeName: "GameHastener"),
                SeedNpc(
                    "Brother Penric",
                    "penric-1",
                    1,
                    30,
                    520000,
                    494000,
                    3352,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.Albion,
                    sourceFlags: GameNPC.eFlags.PEACE),
                SeedNpc(
                    "black wolf pup",
                    "wolf-1",
                    1,
                    2,
                    522000,
                    492000,
                    2954,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.None)
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.StartNpcName, Is.EqualTo("Brother Penric"));
                Assert.That(result.Quest.StartNpcInternalId, Is.EqualTo("penric-1"));
                Assert.That(result.Quest.TargetName, Is.EqualTo("black wolf pup"));
            });
        }

        [Test]
        public void BindTemplate_UsesPinnedServiceStartNpc()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.PreferredStartNpcName = "Captain Prahlion";
            template.PreferredStartNpcInternalId = "trainer-1";
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc(
                    "Captain Prahlion",
                    "trainer-1",
                    1,
                    50,
                    520000,
                    520000,
                    3000,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.Albion,
                    sourceFlags: GameNPC.eFlags.PEACE,
                    sourceTypeName: "DOL.GS.Trainer.ArmsmanTrainer"),
                SeedNpc("forest spiderling", "spider-1", 1, 1, 522000, 520000, 3000)
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.StartNpcName, Is.EqualTo("Captain Prahlion"));
                Assert.That(result.Quest.StartNpcInternalId, Is.EqualTo("trainer-1"));
                Assert.That(result.Quest.TargetName, Is.EqualTo("forest spiderling"));
            });
        }

        [Test]
        public void BindTemplate_UsesPinnedRealmCodedHostileTarget()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.PreferredStartNpcName = "Tersa Weaver";
            template.PreferredStartNpcInternalId = "start-1";
            template.PreferredTargetNpcInternalId = "realm-coded-snake";
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc(
                    "Tersa Weaver",
                    "start-1",
                    1,
                    22,
                    472188,
                    626884,
                    1724,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.Albion,
                    sourceFlags: GameNPC.eFlags.PEACE),
                SeedNpc(
                    "muck snake",
                    "realm-coded-snake",
                    1,
                    1,
                    464833,
                    628288,
                    1682,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.Albion)
            });

            DynamicQuestNode explore = result.Quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Explore);

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.StartNpcInternalId, Is.EqualTo("start-1"));
                Assert.That(result.Quest.TargetName, Is.EqualTo("muck snake"));
                Assert.That(explore.Objective.X, Is.EqualTo(464833));
                Assert.That(explore.Objective.Y, Is.EqualTo(628288));
            });
        }

        [Test]
        public void BindTemplate_StarterBindingSkipsPinnedTargetWithNearbyRealmCodedThreat()
        {
            DynamicQuestTemplate template = StoryTemplate();
            template.PreferredStartNpcName = "Tersa Weaver";
            template.PreferredStartNpcInternalId = "start-1";
            template.PreferredTargetNpcInternalId = "unsafe-snake";
            DynamicQuestTemplateService service = new();

            DynamicQuestTemplateBindingResult result = service.BindTemplate(template, new[]
            {
                SeedNpc(
                    "Tersa Weaver",
                    "start-1",
                    1,
                    22,
                    472188,
                    626884,
                    1724,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.Albion,
                    sourceFlags: GameNPC.eFlags.PEACE),
                SeedNpc(
                    "muck snake",
                    "unsafe-snake",
                    1,
                    1,
                    467950,
                    632881,
                    1784,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.Albion),
                SeedNpc(
                    "slime lizard",
                    "nearby-threat",
                    1,
                    4,
                    467619,
                    632848,
                    1797,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.Albion),
                SeedNpc(
                    "black wolf pup",
                    "safe-wolf",
                    1,
                    1,
                    469200,
                    634000,
                    1900,
                    hasSourceNpcMetadata: true,
                    sourceRealm: eRealm.None)
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Success, Is.True, result.Message);
                Assert.That(result.Quest.TargetName, Is.EqualTo("black wolf pup"));
                Assert.That(result.Quest.Nodes.Single(node => node.Type == DynamicQuestNodeType.Explore).Objective.X, Is.EqualTo(469200));
            });
        }

        private static DynamicQuestTemplate StoryTemplate()
        {
            return new DynamicQuestTemplate
            {
                TemplateId = "template-wolf-trouble",
                Title = "숲의 불안한 밤",
                StorySeed = "밤마다 숲의 소리가 달라졌습니다. 마을 사람들은 무엇이든 지금 가장 가까운 위협을 확인해 달라고 부탁합니다.",
                OfferText = "밤마다 숲의 소리가 달라졌습니다. 지금 이 지역의 위협을 확인해 주시겠습니까?",
                ProgressText = "위협의 흔적은 아직 사라지지 않았습니다.",
                FinishText = "오늘 밤은 조금 조용해질 겁니다.",
                Realm = "Albion",
                PreferredStartNpcName = "Brother Penric",
                PreferredRegionId = 1,
                TargetNameHint = "black wolf pup",
                Count = 1,
                MinLevel = 1,
                MaxLevel = 5,
                Source = "llm",
                Tags = new[] { "llm-story", "starter" },
                StoryProvider = "main-local",
                StoryModel = "gemma-test"
            };
        }

        private static DynamicQuestSeedNpc SeedNpc(
            string name,
            string internalId,
            ushort regionId,
            int level,
            int x,
            int y,
            int z,
            bool hasSourceNpcMetadata = false,
            eRealm sourceRealm = eRealm.None,
            GameNPC.eFlags sourceFlags = 0,
            string sourceTypeName = "")
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
                SourceTypeName = sourceTypeName,
                SourceIsAlive = true
            };
        }
    }

    internal sealed class FakeDynamicQuestTemplateRepository : IDynamicQuestTemplateRepository
    {
        public readonly System.Collections.Generic.Dictionary<string, DbDynamicQuestTemplate> Rows = new();
        public int AddCalls { get; private set; }
        public int SaveCalls { get; private set; }

        public bool Add(DbDynamicQuestTemplate row)
        {
            AddCalls++;
            Rows[row.TemplateId] = row;
            return true;
        }

        public DbDynamicQuestTemplate Find(string templateId)
        {
            Rows.TryGetValue(templateId, out DbDynamicQuestTemplate row);
            return row;
        }

        public System.Collections.Generic.IList<DbDynamicQuestTemplate> GetActive()
        {
            return Rows.Values.Where(row => row.IsActive).OrderBy(row => row.CreatedAt).ToList();
        }

        public bool Save(DbDynamicQuestTemplate row)
        {
            SaveCalls++;
            Rows[row.TemplateId] = row;
            return true;
        }
    }
}
