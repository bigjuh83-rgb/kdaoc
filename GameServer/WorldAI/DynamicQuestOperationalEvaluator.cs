using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;

namespace DOL.GS.WorldAI
{
    public sealed class DynamicQuestEvaluationContext
    {
        public bool RequireWorldBindings { get; set; }
        public DynamicQuestSeedNpc StartNpc { get; set; }
        public DynamicQuestSeedNpc TargetNpc { get; set; }
        public int TargetClusterCount { get; set; }
        public int RequestedTargetCount { get; set; }
        public int TargetDistance { get; set; }
        public bool HasRouteAccessibility { get; set; }
        public bool StartInKnownZone { get; set; }
        public bool TargetInKnownZone { get; set; }
        public bool SameZone { get; set; }
        public bool NavmeshAvailable { get; set; }
        public bool RouteChecked { get; set; }
        public bool RouteFound { get; set; }
        public string RouteStatus { get; set; } = string.Empty;
    }

    public sealed class DynamicQuestEvaluationResult
    {
        public bool Passed { get; set; }
        public int TotalScore { get; set; }
        public string Grade { get; set; } = string.Empty;
        public IList<string> FailReasons { get; set; } = new List<string>();
        public IList<string> Warnings { get; set; } = new List<string>();
        public IList<string> SuggestedFixes { get; set; } = new List<string>();
        public int FeasibilityScore { get; set; }
        public int DifficultyScore { get; set; }
        public int RewardBalanceScore { get; set; }
        public int RouteScore { get; set; }
        public int VarietyScore { get; set; }
        public int LoreScore { get; set; }
        public int CinematicScore { get; set; }
        public int ExploitPenalty { get; set; }
        public int EstimatedPlayableSteps { get; set; }
        public int EstimatedMinutes { get; set; }
        public int RewardDifficultyIndex { get; set; }
        public string RewardLengthTier { get; set; } = string.Empty;
        public string RewardDifficultyTier { get; set; } = string.Empty;
        public string SuggestedRewardTier { get; set; } = string.Empty;
        public double SuggestedRewardScale { get; set; }
    }

    public sealed class DynamicQuestOperationalEvaluator
    {
        private const int StarterSafeMaxTargetLevel = 2;
        private const int AutoAcceptStarterFallbackMaxTargetLevel = 5;
        private const int SoloGeneralMaxTargetDelta = 4;
        private const int LongRouteDistance = 12000;
        private const double MaxGeneralRewardMultiplier = 2.0;
        private const double MaxRepeatableRewardMultiplier = 1.4;
        private const double MaxStepBonusMultiplier = 0.75;
        private const double MaxPartyBonusMultiplier = 1.5;
        private const int MinimumCinematicIntentScore = 70;
        private const int PreferredCinematicActorBudget = 600;
        private const int HardCinematicActorBudget = 1200;

        public static DynamicQuestOperationalEvaluator Instance { get; } = new();

        public DynamicQuestEvaluationResult Evaluate(
            DynamicQuestDefinition quest,
            DynamicQuestEvaluationContext context = null)
        {
            context ??= new DynamicQuestEvaluationContext();
            DynamicQuestEvaluationResult result = new()
            {
                FeasibilityScore = 100,
                DifficultyScore = 100,
                RewardBalanceScore = 100,
                RouteScore = 100,
                VarietyScore = 100,
                LoreScore = 100,
                CinematicScore = 100
            };

            if (quest == null)
            {
                AddFailure(result, "quest definition is missing", "퀘스트 정의를 생성한 뒤 평가하기");
                return Finish(result);
            }

            EvaluateFeasibility(quest, context, result);
            EvaluateDifficulty(quest, context, result);
            EvaluateRewardBalance(quest, result);
            EvaluateRoute(quest, context, result);
            EvaluateVarietyAndLore(quest, result);
            EvaluateCinematicStructure(quest, result);
            EvaluateExploitRisk(quest, context, result);
            EstimateRewardPlanning(quest, context, result);

            if (result.FeasibilityScore < 70)
                AddFailure(result, "feasibility score is below 70", "목표 NPC, 수량, 완료 조건을 현재 월드에 맞게 다시 바인딩하기");
            if (result.RewardBalanceScore < 50)
                AddFailure(result, "reward balance score is below 50", "보상 multiplier를 낮추기");
            if (result.ExploitPenalty >= 25)
                AddFailure(result, "exploit penalty is too high", "반복 가능하거나 너무 짧은 퀘스트의 보상을 낮추거나 수량/동선을 늘리기");
            if (HasCinematicIntent(quest) && result.CinematicScore < MinimumCinematicIntentScore)
                AddFailure(result, "cinematic structure score is below 70", "scene-director, actor staging, varied set-piece presentation beats를 보강하기");

            return Finish(result);
        }

        private static void EvaluateFeasibility(
            DynamicQuestDefinition quest,
            DynamicQuestEvaluationContext context,
            DynamicQuestEvaluationResult result)
        {
            if (string.IsNullOrWhiteSpace(quest.TargetName))
                AddFailure(result, "target name is missing", "목표 몬스터 이름을 지정하기");

            if (RequiresStartNpc(quest) && string.IsNullOrWhiteSpace(quest.StartNpcInternalId))
                AddFailure(result, "start npc is missing", "NPC 시작 퀘스트는 시작 NPC를 지정하기");

            if (context.RequireWorldBindings)
            {
                if (RequiresStartNpc(quest) && context.StartNpc == null)
                    AddFailure(result, "start npc does not exist in current world", "현재 월드에 존재하는 시작 NPC로 다시 바인딩하기");
                if (context.TargetNpc == null)
                    AddFailure(result, "target npc does not exist in current world", "현재 월드에 존재하는 목표 몹으로 다시 바인딩하기");
                if (context.TargetClusterCount > 0 && quest.TargetCount > context.TargetClusterCount)
                {
                    AddFailure(
                        result,
                        "target count exceeds nearby spawn cluster",
                        $"kill count를 {quest.TargetCount}에서 {Math.Max(1, context.TargetClusterCount)}로 줄이기");
                }
            }

            if (quest.TargetCount < 1)
                AddFailure(result, "target count is invalid", "kill count를 1 이상으로 설정하기");

            if (quest.MinLevel < 1 || quest.MaxLevel < quest.MinLevel || quest.MaxLevel > 50)
                AddFailure(result, "quest level range is invalid", "레벨 범위를 1~50 안에서 다시 설정하기");

            if (!HasCheckableCompletion(quest))
                AddFailure(result, "completion condition is not checkable by server logic", "Kill, Talk, ReturnToNpc, Choice, Explore, WorldSignal 중 서버가 추적 가능한 node/edge로 구성하기");
        }

        private static void EvaluateDifficulty(
            DynamicQuestDefinition quest,
            DynamicQuestEvaluationContext context,
            DynamicQuestEvaluationResult result)
        {
            int playerLevel = Math.Clamp(quest.MinLevel <= 0 ? 1 : quest.MinLevel, 1, 50);
            int targetLevel = ResolveTargetLevel(quest, context);
            bool targetLevelKnown = context?.TargetNpc?.Level > 0;
            int delta = targetLevel - playerLevel;

            if (IsStarterQuest(quest) &&
                targetLevelKnown &&
                targetLevel > StarterSafeMaxTargetLevel &&
                quest.StartMode != DynamicQuestStartMode.AutoAccept)
            {
                AddFailure(
                    result,
                    "starter quest target is above safe solo level",
                    $"starter target level을 {targetLevel}에서 {StarterSafeMaxTargetLevel} 이하로 낮추거나 starter 태그를 제거하기");
            }
            else if (IsStarterQuest(quest) &&
                     quest.StartMode == DynamicQuestStartMode.AutoAccept &&
                     targetLevelKnown &&
                     targetLevel > StarterSafeMaxTargetLevel)
            {
                result.DifficultyScore -= targetLevel > AutoAcceptStarterFallbackMaxTargetLevel ? 25 : 15;
                result.Warnings.Add("auto-accept starter quest uses fallback target level");
            }
            else if (delta > SoloGeneralMaxTargetDelta && !IsGroupRecommended(quest))
            {
                AddFailure(
                    result,
                    "target level is too high for solo dynamic quest",
                    "group recommended 태그를 붙이거나 목표 레벨을 플레이어 레벨 +4 이하로 낮추기");
            }
            else if (delta > 2 && !IsGroupRecommended(quest))
            {
                result.DifficultyScore -= 25;
                result.Warnings.Add("target level is challenging for a solo quest");
                result.SuggestedFixes.Add("일반 솔로 퀘스트라면 목표 레벨을 플레이어 레벨 -1~+2로 조정하기");
            }

            if (quest.TargetCount > 12 && !IsGroupRecommended(quest))
            {
                result.DifficultyScore -= 20;
                result.Warnings.Add("solo quest target count is high");
                result.SuggestedFixes.Add($"kill count를 {quest.TargetCount}에서 8~10 이하로 줄이기");
            }
        }

        private static void EvaluateRewardBalance(DynamicQuestDefinition quest, DynamicQuestEvaluationResult result)
        {
            DynamicQuestRewardDefinition reward = quest.Reward ?? new DynamicQuestRewardDefinition();
            if (!IsFiniteNonNegative(reward.XpMultiplier) ||
                !IsFiniteNonNegative(reward.MoneyMultiplier) ||
                !IsFiniteNonNegative(reward.StepBonusMultiplier) ||
                !IsFiniteNonNegative(reward.PartyBonusMultiplier))
            {
                AddFailure(result, "reward multiplier is invalid", "보상 multiplier를 0 이상의 정상 숫자로 설정하기");
                return;
            }

            double maxBaseMultiplier = IsRepeatableRiskQuest(quest)
                ? MaxRepeatableRewardMultiplier
                : MaxGeneralRewardMultiplier;
            if (reward.XpMultiplier > maxBaseMultiplier || reward.MoneyMultiplier > maxBaseMultiplier)
            {
                AddFailure(
                    result,
                    "reward multiplier exceeds policy cap",
                    $"XP/Money multiplier를 {maxBaseMultiplier:0.0} 이하로 낮추기");
            }

            if (reward.StepBonusMultiplier > MaxStepBonusMultiplier)
            {
                result.RewardBalanceScore -= 35;
                result.Warnings.Add("step bonus multiplier is high");
                result.SuggestedFixes.Add($"step bonus multiplier를 {MaxStepBonusMultiplier:0.00} 이하로 낮추기");
            }

            if (reward.PartyBonusMultiplier > MaxPartyBonusMultiplier)
            {
                result.RewardBalanceScore -= 35;
                result.Warnings.Add("party bonus multiplier is high");
                result.SuggestedFixes.Add($"party bonus multiplier를 {MaxPartyBonusMultiplier:0.00} 이하로 낮추기");
            }
        }

        private static void EvaluateRoute(
            DynamicQuestDefinition quest,
            DynamicQuestEvaluationContext context,
            DynamicQuestEvaluationResult result)
        {
            if (context.TargetDistance > LongRouteDistance && !IsGroupRecommended(quest))
            {
                result.RouteScore -= 30;
                result.Warnings.Add("start-to-target route is long for a solo dynamic quest");
                result.SuggestedFixes.Add("target area를 시작 NPC와 가까운 spawn cluster로 변경하기");
            }

            if (context.HasRouteAccessibility)
            {
                if (!context.StartInKnownZone)
                {
                    AddFailure(result, "start location is outside a known zone", "시작 NPC를 알려진 zone 내부 좌표로 다시 바인딩하기");
                }

                if (!context.TargetInKnownZone)
                {
                    AddFailure(result, "target location is outside a known zone", "target area를 알려진 zone 내부 spawn cluster로 변경하기");
                }

                if (context.StartInKnownZone && context.TargetInKnownZone && !context.SameZone)
                {
                    result.RouteScore -= 15;
                    result.Warnings.Add("start and target are in different zones; exact pathing was not checked");
                    result.SuggestedFixes.Add("가능하면 같은 zone 안의 가까운 target cluster로 바인딩하기");
                }

                if (context.StartInKnownZone &&
                    context.TargetInKnownZone &&
                    context.SameZone &&
                    !context.NavmeshAvailable)
                {
                    result.Warnings.Add("navmesh is unavailable for the quest zone; route accessibility was not proven");
                }

                if (context.RouteChecked && !context.RouteFound)
                {
                    AddFailure(
                        result,
                        "pathfinding did not find a traversable route",
                        "target area를 navmesh에서 접근 가능한 spawn cluster로 변경하기");
                }
            }

            bool hasExplore = (quest.Nodes ?? Array.Empty<DynamicQuestNode>())
                .Any(node => node?.Type == DynamicQuestNodeType.Explore);
            if (hasExplore && quest.StartRegionId == 0)
            {
                result.RouteScore -= 20;
                result.Warnings.Add("explore quest has no start region");
                result.SuggestedFixes.Add("explore objective와 시작 region을 명확히 지정하기");
            }
        }

        private static void EvaluateVarietyAndLore(DynamicQuestDefinition quest, DynamicQuestEvaluationResult result)
        {
            IList<DynamicQuestNode> nodes = quest.Nodes ?? Array.Empty<DynamicQuestNode>();
            int objectiveTypes = nodes
                .Where(node => node != null)
                .Select(node => node.Type)
                .Where(type => type is DynamicQuestNodeType.Kill or DynamicQuestNodeType.Talk or DynamicQuestNodeType.ReturnToNpc or DynamicQuestNodeType.Choice or DynamicQuestNodeType.Explore)
                .Distinct()
                .Count();
            if (objectiveTypes <= 1)
            {
                result.VarietyScore -= 35;
                result.Warnings.Add("quest has low objective variety");
            }

            if (string.IsNullOrWhiteSpace(quest.Realm) &&
                !(quest.Tags ?? Array.Empty<string>()).Any(tag => (tag ?? string.Empty).StartsWith("realm:", StringComparison.OrdinalIgnoreCase)))
            {
                result.LoreScore -= 20;
                result.Warnings.Add("quest has no realm signal");
                result.SuggestedFixes.Add("realm 태그나 Realm 필드를 지정하기");
            }
        }

        private static void EvaluateCinematicStructure(DynamicQuestDefinition quest, DynamicQuestEvaluationResult result)
        {
            if (!HasCinematicIntent(quest))
                return;

            IList<string> tags = quest.Tags ?? Array.Empty<string>();
            string combined = string.Join(" ", new[]
            {
                quest.Title,
                quest.OfferText,
                quest.ProgressText,
                quest.FinishText,
                quest.StoryNarrativeJson,
                quest.StoryPresentationJson,
                string.Join(" ", tags)
            }.Where(value => !string.IsNullOrWhiteSpace(value)));

            bool hasSceneDirector = tags.Any(tag => string.Equals((tag ?? string.Empty).Trim(), "scene-director", StringComparison.OrdinalIgnoreCase));
            bool hasStoryCinematic = tags.Any(tag => string.Equals((tag ?? string.Empty).Trim(), "story-cinematic", StringComparison.OrdinalIgnoreCase));
            if (!hasSceneDirector)
            {
                result.CinematicScore -= 30;
                result.Warnings.Add("cinematic quest has no scene director tag");
                result.SuggestedFixes.Add("story-cinematic 퀘스트에는 scene-director 태그를 추가하기");
            }

            CinematicPresentationSignals presentationSignals = ReadCinematicPresentationSignals(quest.StoryPresentationJson);
            CinematicStoryArcSignals storyArcSignals = ReadCinematicStoryArcSignals(quest.StoryNarrativeJson, tags);
            int stagedActionCount = Math.Max(
                CountCinematicSetPieceSignals(combined),
                presentationSignals.ExplicitActionCount);
            if (presentationSignals.StagedBeatCount < 4)
            {
                result.CinematicScore -= 15;
                result.Warnings.Add("cinematic quest has too few executable staged beats");
                result.SuggestedFixes.Add("presentation_beats에 actorCount, sceneRole, formation, cinematicAction을 가진 세트피스를 4개 이상 넣기");
            }

            if (stagedActionCount < 3)
            {
                result.CinematicScore -= 25;
                result.Warnings.Add("cinematic quest has too few staged set-piece signals");
                result.SuggestedFixes.Add("매복, 차단, 후퇴, 대치, 의식 중단 같은 staged set-piece 연출을 3종 이상 포함하기");
            }

            if (presentationSignals.ExplicitActionCount < 3)
            {
                result.CinematicScore -= 15;
                result.Warnings.Add("cinematic quest has too few explicit presentation set-piece actions");
                result.SuggestedFixes.Add("presentation_beats에 cinematicAction, actorCount, formation을 가진 실행 가능한 세트피스를 3개 이상 넣기");
            }

            int actorTagCount = 0;
            int maxRequestedActors = 0;
            foreach (string tag in tags)
            {
                string value = (tag ?? string.Empty).Trim();
                if (!value.StartsWith("cinematic-actors:", StringComparison.OrdinalIgnoreCase))
                    continue;

                actorTagCount++;
                int lastColon = value.LastIndexOf(':');
                if (lastColon >= 0 && lastColon < value.Length - 1 &&
                    int.TryParse(value.Substring(lastColon + 1), out int requestedActors))
                {
                    maxRequestedActors = Math.Max(maxRequestedActors, requestedActors);
                }
            }

            maxRequestedActors = Math.Max(maxRequestedActors, presentationSignals.MaxActorCount);
            bool hasActorStaging = actorTagCount > 0 || presentationSignals.MaxActorCount > 0;

            if (!hasActorStaging)
            {
                result.CinematicScore -= 20;
                result.Warnings.Add("cinematic quest has no actor-count staging tags");
                result.SuggestedFixes.Add("cinematic-actors:<action>:<count> 태그나 presentation beat actorCount로 핵심 액션의 actor 규모를 지정하기");
            }
            else if (maxRequestedActors < 4)
            {
                result.CinematicScore -= 10;
                result.Warnings.Add("cinematic quest actor scale is small");
                result.SuggestedFixes.Add("주요 세트피스는 최소 4명 이상의 actor로 staging하기");
            }

            if (maxRequestedActors > 100)
            {
                result.CinematicScore -= 15;
                result.Warnings.Add("cinematic actor request exceeds runtime safety cap");
                result.SuggestedFixes.Add("cinematic actor 요청 수를 action당 100 이하로 낮추기");
            }

            if (presentationSignals.TotalActorCount > PreferredCinematicActorBudget)
            {
                result.CinematicScore -= 10;
                result.Warnings.Add("cinematic total actor budget is high");
                result.SuggestedFixes.Add($"presentation beat actor 합계를 {PreferredCinematicActorBudget}명 이하로 낮추고 100명 세트피스는 핵심 장면 1개에만 쓰기");
            }

            if (presentationSignals.HundredActorBeatCount > 1)
            {
                result.CinematicScore -= 10;
                result.Warnings.Add("cinematic quest has multiple hundred-actor set pieces");
                result.SuggestedFixes.Add("100명 actor 세트피스는 climax 장면 1개로 제한하고 나머지는 12~48명 규모로 낮추기");
            }

            if (presentationSignals.TotalActorCount > HardCinematicActorBudget)
            {
                result.CinematicScore -= 20;
                AddFailure(
                    result,
                    "cinematic total actor budget exceeds safety budget",
                    $"presentation beat actor 합계를 {HardCinematicActorBudget}명 이하로 낮추기");
            }

            if (presentationSignals.FormationCount < 2)
            {
                result.CinematicScore -= 10;
                result.Warnings.Add("cinematic quest has low formation variety");
                result.SuggestedFixes.Add("ambush, line, escort, ring, escape 같은 formation을 장면마다 다르게 배치하기");
            }

            if (presentationSignals.SceneRoleCount < 3)
            {
                result.CinematicScore -= 10;
                result.Warnings.Add("cinematic quest has low scene role variety");
                result.SuggestedFixes.Add("contract_witness, ambush_wave, escape_intercept, choice_fallout 같은 sceneRole을 장면별로 다르게 지정하기");
            }

            if (presentationSignals.DelayedBeatCount == 0)
            {
                result.CinematicScore -= 5;
                result.Warnings.Add("cinematic quest has no delayed set-piece beat");
                result.SuggestedFixes.Add("중요한 장면 하나 이상에 delayMs를 넣어 장면 전환 리듬을 만들기");
            }

            if (!presentationSignals.HasActionScene)
            {
                result.CinematicScore -= 15;
                result.Warnings.Add("cinematic quest has no combat or movement action scene");
                result.SuggestedFixes.Add("ambush_reveal, defender_intercept, scout_retreat, ritual_interrupt, hold_ground 같은 실제 액션 set-piece를 포함하기");
            }

            if (presentationSignals.ActorExchangeActionCount == 0)
            {
                result.CinematicScore -= 10;
                result.Warnings.Add("cinematic quest has no actor exchange action");
                result.SuggestedFixes.Add("clash, block, interrupt, pursuit, standoff로 해석되는 다중 actor 액션 교환을 1개 이상 포함하기");
            }

            if (presentationSignals.ActionPhaseCount < 3)
            {
                result.CinematicScore -= 10;
                result.Warnings.Add("cinematic quest has low action phase variety");
                result.SuggestedFixes.Add("전투, 이동/후퇴, 방어/차단, 의식/증거 같은 서로 다른 액션 phase를 3종 이상 섞기");
            }

            if (!storyArcSignals.HasArchetypeTag)
            {
                result.CinematicScore -= 10;
                result.Warnings.Add("cinematic quest has no story archetype tag");
                result.SuggestedFixes.Add("story-archetype:<type> 태그로 증언 음모, 깨진 맹세, 성물 메아리 같은 핵심 서사 아키타입을 지정하기");
            }

            if (storyArcSignals.StageCount < 4)
            {
                result.CinematicScore -= 15;
                result.Warnings.Add("cinematic quest has weak narrative arc coverage");
                result.SuggestedFixes.Add("서사 장면이나 story-arc 태그에 motive, conflict, reversal, consequence 단계가 드러나게 하기");
            }

            if (storyArcSignals.HasNarrativeSequence && storyArcSignals.OrderedChainLength < 3)
            {
                result.CinematicScore -= 15;
                result.Warnings.Add("cinematic quest narrative arc order is broken");
                result.SuggestedFixes.Add("StoryNarrativeJson 장면을 discovery -> conflict/battle -> aftermath/completion 순서로 배치하기");
                if (hasStoryCinematic && hasSceneDirector)
                {
                    AddFailure(
                        result,
                        "cinematic narrative arc order is broken",
                        "StoryNarrativeJson 장면 순서를 discovery -> conflict/battle -> aftermath/completion으로 재배치하기");
                }
            }

            if (!storyArcSignals.HasConsequence)
            {
                result.CinematicScore -= 10;
                result.Warnings.Add("cinematic quest has no visible consequence beat");
                result.SuggestedFixes.Add("Choice, Return, Aftermath, Completion 장면 중 하나로 플레이어 선택/전투 결과가 세계에 남는 후폭풍을 기록하기");
            }

            if (HasFollowupEpisodeIntent(tags) && !HasStoryPrerequisiteTag(tags))
            {
                result.CinematicScore -= 20;
                result.Warnings.Add("follow-up story episode has no memory prerequisite");
                result.SuggestedFixes.Add("2편 이상 story episode에는 requires-story-family, requires-story-archetype, requires-choice, requires-memory 중 하나를 추가하기");
                if (hasStoryCinematic && hasSceneDirector)
                {
                    AddFailure(
                        result,
                        "follow-up story episode has no memory prerequisite",
                        "후속편이 모든 유저에게 바로 노출되지 않도록 story prerequisite 태그를 추가하기");
                }
            }
        }

        private static void EvaluateExploitRisk(
            DynamicQuestDefinition quest,
            DynamicQuestEvaluationContext context,
            DynamicQuestEvaluationResult result)
        {
            DynamicQuestRewardDefinition reward = quest.Reward ?? new DynamicQuestRewardDefinition();
            if (IsRepeatableRiskQuest(quest) && quest.TargetCount <= 1)
                result.ExploitPenalty += 8;
            if (IsRepeatableRiskQuest(quest) && (reward.XpMultiplier > 1.2 || reward.MoneyMultiplier > 1.2))
                result.ExploitPenalty += 12;
            if (quest.StartMode == DynamicQuestStartMode.AutoAccept && context.TargetDistance > 0 && context.TargetDistance < 1200)
                result.ExploitPenalty += 8;
            if ((quest.Nodes ?? Array.Empty<DynamicQuestNode>()).Any(HasBroadWorldSignalEdge))
                result.ExploitPenalty += 8;

            if (result.ExploitPenalty > 0)
            {
                result.Warnings.Add($"exploit risk penalty: {result.ExploitPenalty}");
                result.SuggestedFixes.Add("반복 가능성이 높은 퀘스트는 보상 multiplier를 낮추고 world signal 조건을 구체화하기");
            }
        }

        private static void EstimateRewardPlanning(
            DynamicQuestDefinition quest,
            DynamicQuestEvaluationContext context,
            DynamicQuestEvaluationResult result)
        {
            if (quest == null)
                return;

            int playableSteps = CountPlayableSteps(quest);
            int targetCount = Math.Max(1, quest.TargetCount);
            int playerLevel = Math.Clamp(quest.MinLevel <= 0 ? 1 : quest.MinLevel, 1, 50);
            int targetLevel = ResolveTargetLevel(quest, context);
            int levelDelta = Math.Max(0, targetLevel - playerLevel);
            int distance = Math.Max(0, context?.TargetDistance ?? 0);

            double minutes = 2.0 +
                             targetCount * 1.25 +
                             Math.Max(0, playableSteps - 1) * 0.75 +
                             Math.Min(8.0, distance / 4000.0);
            if (HasWorldSignalStep(quest))
                minutes += 1.5;
            if (IsGroupRecommended(quest))
                minutes += 2.0;

            int difficultyIndex = Math.Clamp(
                20 +
                levelDelta * 12 +
                Math.Max(0, targetCount - 1) * 4 +
                (IsGroupRecommended(quest) ? 15 : 0) +
                (distance > LongRouteDistance ? 10 : 0),
                0,
                100);

            double uncappedScale = 0.85 +
                                   Math.Max(0, minutes - 4.0) * 0.045 +
                                   difficultyIndex * 0.006 +
                                   Math.Max(0, playableSteps - 2) * 0.06;
            double cap = IsRepeatableRiskQuest(quest)
                ? MaxRepeatableRewardMultiplier
                : MaxGeneralRewardMultiplier;

            result.EstimatedPlayableSteps = playableSteps;
            result.EstimatedMinutes = Math.Clamp((int)Math.Ceiling(minutes), 1, 60);
            result.RewardDifficultyIndex = difficultyIndex;
            result.RewardLengthTier = result.EstimatedMinutes switch
            {
                <= 4 => "short",
                <= 8 => "standard",
                <= 14 => "long",
                _ => "epic"
            };
            result.RewardDifficultyTier = difficultyIndex switch
            {
                < 30 => "easy",
                < 55 => "normal",
                < 80 => "hard",
                _ => "elite"
            };
            result.SuggestedRewardScale = Math.Round(Math.Clamp(uncappedScale, 0.75, cap), 2);
            result.SuggestedRewardTier = result.SuggestedRewardScale switch
            {
                < 1.0 => "low",
                < 1.2 => "standard",
                < 1.45 => "enhanced",
                _ => "premium"
            };
        }

        private static bool HasCheckableCompletion(DynamicQuestDefinition quest)
        {
            IList<DynamicQuestNode> nodes = quest.Nodes ?? Array.Empty<DynamicQuestNode>();
            if (nodes.Count == 0)
                return false;

            bool hasTerminal = nodes.Any(node => node?.Type == DynamicQuestNodeType.Complete);
            bool hasObjective = nodes.Any(node =>
                node?.Type is DynamicQuestNodeType.Kill or DynamicQuestNodeType.Talk or DynamicQuestNodeType.ReturnToNpc or DynamicQuestNodeType.Choice or DynamicQuestNodeType.Explore);
            bool invalidWorldSignal = nodes.Any(node =>
                (node?.Edges ?? Array.Empty<DynamicQuestEdge>()).Any(edge =>
                    edge?.Condition == DynamicQuestEdgeCondition.WorldSignal &&
                    !string.IsNullOrWhiteSpace(edge.ConditionValue) &&
                    !DynamicQuestWorldSignalPolicy.IsAllowed(edge.ConditionValue)));
            return hasTerminal && hasObjective && !invalidWorldSignal;
        }

        private static bool HasBroadWorldSignalEdge(DynamicQuestNode node)
        {
            return (node?.Edges ?? Array.Empty<DynamicQuestEdge>()).Any(edge =>
                edge?.Condition == DynamicQuestEdgeCondition.WorldSignal &&
                string.IsNullOrWhiteSpace(edge.ConditionValue));
        }

        private static bool HasWorldSignalStep(DynamicQuestDefinition quest)
        {
            return (quest?.Nodes ?? Array.Empty<DynamicQuestNode>()).Any(node =>
                (node?.Edges ?? Array.Empty<DynamicQuestEdge>()).Any(edge =>
                    edge?.Condition == DynamicQuestEdgeCondition.WorldSignal));
        }

        private static int CountPlayableSteps(DynamicQuestDefinition quest)
        {
            int count = (quest?.Nodes ?? Array.Empty<DynamicQuestNode>())
                .Count(node => node != null &&
                               node.Type is not DynamicQuestNodeType.Complete and not DynamicQuestNodeType.Fail);
            return Math.Max(1, count);
        }

        private static int ResolveTargetLevel(DynamicQuestDefinition quest, DynamicQuestEvaluationContext context)
        {
            int level = context?.TargetNpc?.Level ?? 0;
            if (level <= 0)
                level = quest.MinLevel;
            return Math.Clamp(level <= 0 ? 1 : level, 1, 50);
        }

        private static bool RequiresStartNpc(DynamicQuestDefinition quest)
        {
            return quest?.StartMode != DynamicQuestStartMode.WorldOffer &&
                   quest?.StartMode != DynamicQuestStartMode.AutoAccept;
        }

        private static bool IsStarterQuest(DynamicQuestDefinition quest)
        {
            return (quest?.Tags ?? Array.Empty<string>())
                .Any(tag => string.Equals((tag ?? string.Empty).Trim(), "starter", StringComparison.OrdinalIgnoreCase));
        }

        private static bool IsGroupRecommended(DynamicQuestDefinition quest)
        {
            return (quest?.Tags ?? Array.Empty<string>())
                .Any(tag =>
                    string.Equals((tag ?? string.Empty).Trim(), "group", StringComparison.OrdinalIgnoreCase) ||
                    string.Equals((tag ?? string.Empty).Trim(), "group-recommended", StringComparison.OrdinalIgnoreCase));
        }

        private static bool IsRepeatableRiskQuest(DynamicQuestDefinition quest)
        {
            if (quest == null)
                return false;

            if (quest.StartMode == DynamicQuestStartMode.AutoAccept)
                return true;

            return (quest.Tags ?? Array.Empty<string>()).Any(tag =>
                string.Equals((tag ?? string.Empty).Trim(), "repeatable", StringComparison.OrdinalIgnoreCase) ||
                string.Equals((tag ?? string.Empty).Trim(), "dynamic-rebind", StringComparison.OrdinalIgnoreCase));
        }

        private static bool HasCinematicIntent(DynamicQuestDefinition quest)
        {
            if (quest == null)
                return false;

            if ((quest.Tags ?? Array.Empty<string>()).Any(tag =>
            {
                string value = (tag ?? string.Empty).Trim();
                return string.Equals(value, "scene-director", StringComparison.OrdinalIgnoreCase) ||
                       string.Equals(value, "story-cinematic", StringComparison.OrdinalIgnoreCase) ||
                       string.Equals(value, "dark-brotherhood", StringComparison.OrdinalIgnoreCase) ||
                       value.StartsWith("cinematic-actors:", StringComparison.OrdinalIgnoreCase);
            }))
            {
                return true;
            }

            CinematicPresentationSignals presentationSignals = ReadCinematicPresentationSignals(quest.StoryPresentationJson);
            return presentationSignals.StagedBeatCount >= 3 ||
                   presentationSignals.ExplicitActionCount >= 3 ||
                   presentationSignals.MaxActorCount >= 20;
        }

        private static bool HasFollowupEpisodeIntent(IEnumerable<string> tags)
        {
            foreach (string tag in tags ?? Array.Empty<string>())
            {
                string value = (tag ?? string.Empty).Trim();
                if (value.StartsWith("story-episode:", StringComparison.OrdinalIgnoreCase) &&
                    TryParseEpisodeIndex(value.Substring("story-episode:".Length), out int episode) &&
                    episode > 1)
                {
                    return true;
                }

                if (value.StartsWith("arc-step:", StringComparison.OrdinalIgnoreCase) &&
                    TryParseEpisodeIndex(value.Substring("arc-step:".Length), out int arcStep) &&
                    arcStep > 1)
                {
                    return true;
                }
            }

            return false;
        }

        private static bool HasStoryPrerequisiteTag(IEnumerable<string> tags)
        {
            return (tags ?? Array.Empty<string>()).Any(tag =>
            {
                string value = (tag ?? string.Empty).Trim();
                return value.StartsWith("requires-story-family:", StringComparison.OrdinalIgnoreCase) ||
                       value.StartsWith("requires-story-archetype:", StringComparison.OrdinalIgnoreCase) ||
                       value.StartsWith("requires-choice:", StringComparison.OrdinalIgnoreCase) ||
                       value.StartsWith("requires-memory:", StringComparison.OrdinalIgnoreCase) ||
                       value.StartsWith("arc-prev:", StringComparison.OrdinalIgnoreCase);
            });
        }

        private static bool TryParseEpisodeIndex(string value, out int episode)
        {
            episode = 0;
            value = (value ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(value))
                return false;

            int slash = value.IndexOf('/');
            if (slash >= 0)
                value = value.Substring(0, slash);

            return int.TryParse(value, out episode);
        }

        private static int CountCinematicSetPieceSignals(string text)
        {
            string value = (text ?? string.Empty).ToLowerInvariant();
            int count = 0;
            if (ContainsAny(value, "매복", "기습", "ambush", "ambush_reveal"))
                count++;
            if (ContainsAny(value, "차단", "가로막", "intercept", "defender_intercept"))
                count++;
            if (ContainsAny(value, "후퇴", "탈출로", "망보", "retreat", "scout_retreat", "escape route"))
                count++;
            if (ContainsAny(value, "대치", "standoff", "threat_standoff", "confront"))
                count++;
            if (ContainsAny(value, "의식", "성물", "ritual", "relic", "ritual_interrupt"))
                count++;
            if (ContainsAny(value, "증인", "목격", "witness", "witness_point"))
                count++;

            return count;
        }

        private sealed class CinematicPresentationSignals
        {
            public int ExplicitActionCount { get; set; }
            public int StagedBeatCount { get; set; }
            public int MaxActorCount { get; set; }
            public int TotalActorCount { get; set; }
            public int HundredActorBeatCount { get; set; }
            public int DelayedBeatCount { get; set; }
            public int FormationCount { get; set; }
            public int SceneRoleCount { get; set; }
            public int ActionPhaseCount { get; set; }
            public int ActorExchangeActionCount { get; set; }
            public bool HasActionScene { get; set; }
        }

        private sealed class CinematicStoryArcSignals
        {
            public int StageCount { get; set; }
            public int OrderedChainLength { get; set; }
            public bool HasArchetypeTag { get; set; }
            public bool HasConsequence { get; set; }
            public bool HasNarrativeSequence { get; set; }
        }

        private static CinematicPresentationSignals ReadCinematicPresentationSignals(string presentationJson)
        {
            CinematicPresentationSignals signals = new();
            if (string.IsNullOrWhiteSpace(presentationJson))
                return signals;

            try
            {
                using JsonDocument document = JsonDocument.Parse(presentationJson);
                if (document.RootElement.ValueKind != JsonValueKind.Array)
                    return signals;

                HashSet<string> actions = new(StringComparer.OrdinalIgnoreCase);
                HashSet<string> formations = new(StringComparer.OrdinalIgnoreCase);
                HashSet<string> sceneRoles = new(StringComparer.OrdinalIgnoreCase);
                HashSet<string> actionPhases = new(StringComparer.OrdinalIgnoreCase);
                HashSet<string> actorExchangeActions = new(StringComparer.OrdinalIgnoreCase);
                foreach (JsonElement element in document.RootElement.EnumerateArray())
                {
                    if (element.ValueKind != JsonValueKind.Object)
                        continue;

                    string action = GetStringProperty(element, "cinematicAction", "CinematicAction", "cinematic_action");
                    if (!string.IsNullOrWhiteSpace(action))
                        actions.Add(action.Trim());

                    string formation = GetStringProperty(element, "formation", "Formation");
                    if (!string.IsNullOrWhiteSpace(formation))
                        formations.Add(formation.Trim());

                    string sceneRole = GetStringProperty(element, "sceneRole", "SceneRole", "scene_role");
                    if (!string.IsNullOrWhiteSpace(sceneRole))
                        sceneRoles.Add(sceneRole.Trim());

                    int actorCount = GetIntProperty(element, "actorCount", "ActorCount", "actor_count");
                    if (actorCount > 0)
                    {
                        signals.MaxActorCount = Math.Max(signals.MaxActorCount, actorCount);
                        signals.TotalActorCount += actorCount;
                        if (actorCount >= 100)
                            signals.HundredActorBeatCount++;
                    }
                    if (actorCount > 1 && IsActorExchangeCinematicAction(action))
                        actorExchangeActions.Add(action.Trim());

                    string actionPhase = ResolveCinematicActionPhase(
                        action,
                        sceneRole,
                        formation,
                        GetStringProperty(element, "text", "Text"));
                    if (!string.IsNullOrWhiteSpace(actionPhase))
                        actionPhases.Add(actionPhase);

                    if (!string.IsNullOrWhiteSpace(action) &&
                        !string.IsNullOrWhiteSpace(sceneRole) &&
                        !string.IsNullOrWhiteSpace(formation) &&
                        actorCount > 0)
                    {
                        signals.StagedBeatCount++;
                    }

                    int delayMs = GetIntProperty(element, "delayMs", "DelayMs", "delay_ms");
                    if (delayMs > 0)
                        signals.DelayedBeatCount++;
                }

                signals.ExplicitActionCount = actions.Count;
                signals.FormationCount = formations.Count;
                signals.SceneRoleCount = sceneRoles.Count;
                signals.ActionPhaseCount = actionPhases.Count;
                signals.ActorExchangeActionCount = actorExchangeActions.Count;
                signals.HasActionScene = actions.Any(IsActionSceneCinematicAction);
            }
            catch (JsonException)
            {
            }

            return signals;
        }

        private static bool IsActionSceneCinematicAction(string action)
        {
            string value = (action ?? string.Empty).Trim();
            return string.Equals(value, "ambush_reveal", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "defender_intercept", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "scout_retreat", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "ritual_interrupt", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "threat_standoff", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "combat_stance", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "hold_ground", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "guard_advance", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "fallback_guard", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsActorExchangeCinematicAction(string action)
        {
            string value = (action ?? string.Empty).Trim();
            return string.Equals(value, "ambush_reveal", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "defender_intercept", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "scout_retreat", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "ritual_interrupt", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "threat_standoff", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "combat_stance", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "hold_ground", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(value, "guard_advance", StringComparison.OrdinalIgnoreCase);
        }

        private static string ResolveCinematicActionPhase(string action, string sceneRole, string formation, string text)
        {
            string actionValue = (action ?? string.Empty).Trim();
            if (string.Equals(actionValue, "scout_retreat", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(actionValue, "fallback_guard", StringComparison.OrdinalIgnoreCase))
                return "movement";
            if (string.Equals(actionValue, "defender_intercept", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(actionValue, "hold_ground", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(actionValue, "guard_advance", StringComparison.OrdinalIgnoreCase))
                return "defense";
            if (string.Equals(actionValue, "ritual_interrupt", StringComparison.OrdinalIgnoreCase))
                return "ritual";
            if (string.Equals(actionValue, "witness_point", StringComparison.OrdinalIgnoreCase))
                return "witness";
            if (string.Equals(actionValue, "ambush_reveal", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(actionValue, "combat_stance", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(actionValue, "threat_standoff", StringComparison.OrdinalIgnoreCase))
                return "combat";

            string value = string.Join(" ", new[] { action, sceneRole, formation, text }
                .Where(item => !string.IsNullOrWhiteSpace(item)))
                .ToLowerInvariant();

            if (ContainsAny(value, "scout_retreat", "fallback", "escape", "retreat", "후퇴", "탈출", "이동"))
                return "movement";
            if (ContainsAny(value, "defender_intercept", "hold_ground", "guard_advance", "line", "shield", "intercept", "차단", "가로막", "방어", "경비"))
                return "defense";
            if (ContainsAny(value, "ritual_interrupt", "relic", "clue", "evidence", "ritual", "성물", "의식", "증거", "표식"))
                return "ritual";
            if (ContainsAny(value, "witness_point", "contract_witness", "witness", "목격", "증인"))
                return "witness";
            if (ContainsAny(value, "ambush_reveal", "combat_stance", "threat_standoff", "ambush", "combat", "attack", "매복", "전투", "대치"))
                return "combat";

            return string.Empty;
        }

        private static CinematicStoryArcSignals ReadCinematicStoryArcSignals(string narrativeJson, IEnumerable<string> tags)
        {
            CinematicStoryArcSignals signals = new();
            HashSet<string> stages = new(StringComparer.OrdinalIgnoreCase);

            foreach (string tag in tags ?? Array.Empty<string>())
            {
                string value = (tag ?? string.Empty).Trim();
                if (value.StartsWith("story-archetype:", StringComparison.OrdinalIgnoreCase))
                    signals.HasArchetypeTag = true;
                if (value.StartsWith("story-arc:", StringComparison.OrdinalIgnoreCase))
                {
                    string stage = value.Substring("story-arc:".Length).Trim();
                    if (!string.IsNullOrWhiteSpace(stage))
                        stages.Add(NormalizeStoryArcStage(stage));
                }
            }

            if (!string.IsNullOrWhiteSpace(narrativeJson))
            {
                try
                {
                    using JsonDocument document = JsonDocument.Parse(narrativeJson);
                    if (document.RootElement.ValueKind == JsonValueKind.Array)
                    {
                        int orderedChainLength = 0;
                        foreach (JsonElement element in document.RootElement.EnumerateArray())
                        {
                            if (element.ValueKind != JsonValueKind.Object)
                                continue;

                            string sceneType = GetStringProperty(element, "sceneType", "SceneType", "scene_type");
                            string nodeId = GetStringProperty(element, "nodeId", "NodeId", "node_id");
                            string stage = NormalizeStoryArcStage(string.IsNullOrWhiteSpace(sceneType) ? nodeId : sceneType);
                            if (!string.IsNullOrWhiteSpace(stage))
                            {
                                stages.Add(stage);
                                signals.HasNarrativeSequence = true;
                                orderedChainLength = AdvanceOrderedStoryChain(orderedChainLength, stage);
                            }
                        }

                        signals.OrderedChainLength = orderedChainLength;
                    }
                }
                catch (JsonException)
                {
                }
            }

            signals.StageCount = stages.Count;
            signals.HasConsequence =
                stages.Contains("choice") ||
                stages.Contains("return") ||
                stages.Contains("aftermath") ||
                stages.Contains("completion") ||
                stages.Contains("consequence");
            return signals;
        }

        private static int AdvanceOrderedStoryChain(int current, string stage)
        {
            string value = (stage ?? string.Empty).Trim().ToLowerInvariant();
            if (value == "discovery")
                return Math.Max(current, 1);
            if (value == "conflict" && current >= 1)
                return Math.Max(current, 2);
            if ((value == "choice" || value == "return" || value == "aftermath" || value == "completion") && current >= 2)
                return Math.Max(current, 3);
            return current;
        }

        private static string NormalizeStoryArcStage(string value)
        {
            string stage = (value ?? string.Empty).Trim().ToLowerInvariant();
            return stage switch
            {
                "intro" or "talk" or "motive" => "motive",
                "discovery" or "explore" => "discovery",
                "threat" or "kill" or "conflict" => "conflict",
                "choice" or "reversal" => "choice",
                "return" => "return",
                "aftermath" or "observe_signal" => "aftermath",
                "completion" or "complete" or "consequence" => "completion",
                _ => string.Empty
            };
        }

        private static string GetStringProperty(JsonElement element, params string[] names)
        {
            foreach (string name in names)
            {
                if (element.TryGetProperty(name, out JsonElement property) &&
                    property.ValueKind == JsonValueKind.String)
                {
                    return property.GetString() ?? string.Empty;
                }
            }

            return string.Empty;
        }

        private static int GetIntProperty(JsonElement element, params string[] names)
        {
            foreach (string name in names)
            {
                if (!element.TryGetProperty(name, out JsonElement property))
                    continue;

                if (property.ValueKind == JsonValueKind.Number &&
                    property.TryGetInt32(out int number))
                {
                    return number;
                }

                if (property.ValueKind == JsonValueKind.String &&
                    int.TryParse(property.GetString(), out number))
                {
                    return number;
                }
            }

            return 0;
        }

        private static bool ContainsAny(string value, params string[] needles)
        {
            if (string.IsNullOrWhiteSpace(value))
                return false;

            return needles.Any(needle =>
                !string.IsNullOrWhiteSpace(needle) &&
                value.Contains(needle, StringComparison.OrdinalIgnoreCase));
        }

        private static bool IsFiniteNonNegative(double value)
        {
            return !double.IsNaN(value) && !double.IsInfinity(value) && value >= 0.0;
        }

        private static void AddFailure(DynamicQuestEvaluationResult result, string reason, string suggestedFix)
        {
            if (!result.FailReasons.Contains(reason, StringComparer.OrdinalIgnoreCase))
                result.FailReasons.Add(reason);
            if (!string.IsNullOrWhiteSpace(suggestedFix) &&
                !result.SuggestedFixes.Contains(suggestedFix, StringComparer.OrdinalIgnoreCase))
            {
                result.SuggestedFixes.Add(suggestedFix);
            }
        }

        private static DynamicQuestEvaluationResult Finish(DynamicQuestEvaluationResult result)
        {
            result.FeasibilityScore = Math.Clamp(result.FeasibilityScore - result.FailReasons.Count * 20, 0, 100);
            result.DifficultyScore = Math.Clamp(result.DifficultyScore, 0, 100);
            result.RewardBalanceScore = Math.Clamp(result.RewardBalanceScore - result.FailReasons.Count(reason => reason.Contains("reward", StringComparison.OrdinalIgnoreCase)) * 25, 0, 100);
            result.RouteScore = Math.Clamp(result.RouteScore, 0, 100);
            result.VarietyScore = Math.Clamp(result.VarietyScore, 0, 100);
            result.LoreScore = Math.Clamp(result.LoreScore, 0, 100);
            result.CinematicScore = Math.Clamp(result.CinematicScore, 0, 100);
            int weighted =
                (int)Math.Round(
                    result.FeasibilityScore * 0.35 +
                    result.DifficultyScore * 0.30 +
                    result.RewardBalanceScore * 0.20 +
                    result.RouteScore * 0.10 +
                    ((result.VarietyScore + result.LoreScore + result.CinematicScore) / 3.0) * 0.05);
            result.TotalScore = Math.Clamp(weighted - result.ExploitPenalty, 0, 100);
            result.Passed = result.FailReasons.Count == 0 &&
                            result.FeasibilityScore >= 70 &&
                            result.RewardBalanceScore >= 50 &&
                            result.ExploitPenalty < 25;
            result.Grade = result.TotalScore switch
            {
                >= 90 => "excellent",
                >= 75 => "usable",
                >= 60 => "conditional",
                >= 40 => "needs-work",
                _ => "discard"
            };
            return result;
        }
    }
}
