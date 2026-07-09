using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.RegularExpressions;
using DOL.Database;
using DOL.GS.ServerProperties;

namespace DOL.GS.WorldAI
{
    public sealed class DynamicQuestStoryRequest
    {
        public string TemplateId { get; set; } = string.Empty;
        public string Realm { get; set; } = string.Empty;
        public string StartNpcName { get; set; } = string.Empty;
        public ushort RegionId { get; set; }
        public string TargetName { get; set; } = string.Empty;
        public int Count { get; set; } = 1;
        public int MinLevel { get; set; } = 1;
        public int MaxLevel { get; set; } = 50;
        public string StorySeed { get; set; } = string.Empty;
    }

    public sealed class DynamicQuestStoryText
    {
        public string Title { get; set; } = string.Empty;
        public string OfferText { get; set; } = string.Empty;
        public string ProgressText { get; set; } = string.Empty;
        public string FinishText { get; set; } = string.Empty;
        public int QualityScore { get; set; }
        public IList<DynamicQuestNarrativeScene> NarrativeScenes { get; set; } = Array.Empty<DynamicQuestNarrativeScene>();
        public IList<DynamicQuestPresentationBeat> PresentationBeats { get; set; } = Array.Empty<DynamicQuestPresentationBeat>();
        public DynamicQuestStoryQuality Quality { get; set; } = DynamicQuestStoryQuality.Empty;
        public bool StructureRepaired { get; set; }
    }

    public sealed class DynamicQuestNarrativeScene
    {
        public string NodeId { get; set; } = string.Empty;
        public string SceneType { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public string Body { get; set; } = string.Empty;
        public string JournalEntry { get; set; } = string.Empty;
        public string Mood { get; set; } = string.Empty;
        public string RevealPolicy { get; set; } = string.Empty;
    }

    public sealed class DynamicQuestPresentationBeat
    {
        public string NodeId { get; set; } = string.Empty;
        public string Trigger { get; set; } = string.Empty;
        public string Speaker { get; set; } = string.Empty;
        public string Text { get; set; } = string.Empty;
        public string Emotion { get; set; } = string.Empty;
        public string Emote { get; set; } = string.Empty;
        public string CinematicAction { get; set; } = string.Empty;
        public string SceneRole { get; set; } = string.Empty;
        public string Formation { get; set; } = string.Empty;
        public int ActorCount { get; set; }
        public int DelayMs { get; set; }
    }

    public sealed class DynamicQuestStoryQuality
    {
        public static DynamicQuestStoryQuality Empty { get; } = new();

        public int TotalScore { get; set; }
        public int StructureScore { get; set; }
        public int KoreanScore { get; set; }
        public int ObjectiveScore { get; set; }
        public int ImmersionScore { get; set; }
        public int NarrativeScore { get; set; }
        public int PresentationScore { get; set; }
        public int RebindabilityScore { get; set; }
        public int SafetyScore { get; set; }
        public int DiversityScore { get; set; }
        public IList<string> Reasons { get; set; } = Array.Empty<string>();
    }

    public sealed class DynamicQuestStoryGenerationResult
    {
        public bool Success { get; set; }
        public string ProviderName { get; set; } = string.Empty;
        public string ModelName { get; set; } = string.Empty;
        public string Error { get; set; } = string.Empty;
        public DynamicQuestStoryText Story { get; set; }

        public static DynamicQuestStoryGenerationResult Ok(DynamicQuestStoryText story, string providerName, string modelName = "")
        {
            return new DynamicQuestStoryGenerationResult
            {
                Success = true,
                Story = story,
                ProviderName = providerName ?? string.Empty,
                ModelName = modelName ?? string.Empty
            };
        }

        public static DynamicQuestStoryGenerationResult Fail(string error)
        {
            return new DynamicQuestStoryGenerationResult
            {
                Success = false,
                Error = error ?? string.Empty
            };
        }
    }

    public interface IDynamicQuestStoryProvider
    {
        string Name { get; }
        string ModelName { get; }
        DynamicQuestStoryGenerationResult TryGenerate(DynamicQuestStoryRequest request);
    }

    public sealed class DynamicQuestStoryService
    {
        private enum OpenAiStoryRequestMode
        {
            StrictSchema,
            PlainJson,
            CompactJson
        }

        private static readonly JsonSerializerOptions StoryJsonOptions = new()
        {
            Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            WriteIndented = false
        };

        private readonly IList<IDynamicQuestStoryProvider> m_providers;

        public DynamicQuestStoryService(IEnumerable<IDynamicQuestStoryProvider> providers)
        {
            m_providers = (providers ?? Array.Empty<IDynamicQuestStoryProvider>())
                .Where(provider => provider != null)
                .ToList();
        }

        public static DynamicQuestStoryService FromProperties()
        {
            Dictionary<string, IDynamicQuestStoryProvider> providers = new(StringComparer.OrdinalIgnoreCase)
            {
                ["openai"] = new OpenAiDynamicQuestStoryProvider(
                    "openai",
                    "https://api.openai.com",
                    Properties.KDAOC_DYNAMIC_QUEST_STORY_OPENAI_MODEL,
                    new DynamicQuestGeminiQuota(
                        Properties.KDAOC_DYNAMIC_QUEST_STORY_OPENAI_PER_MINUTE_LIMIT,
                        Properties.KDAOC_DYNAMIC_QUEST_STORY_OPENAI_DAILY_LIMIT,
                        () => DateTime.UtcNow,
                        "openai",
                        DynamicQuestServerPropertyDailyQuotaStore.Instance),
                    new DynamicQuestTokenBudget(
                        "openai",
                        Properties.KDAOC_DYNAMIC_QUEST_STORY_OPENAI_DAILY_TOKEN_LIMIT,
                        DynamicQuestServerPropertyDailyQuotaStore.Instance),
                    Properties.WORLDAI_LLM_TIMEOUT_SECONDS),
                ["main-local"] = new OpenAiCompatibleDynamicQuestStoryProvider(
                    "main-local",
                    Properties.WORLDAI_LLM_API_URL,
                    Properties.WORLDAI_LLM_MODEL,
                    Properties.WORLDAI_LLM_TIMEOUT_SECONDS),
                ["gemini"] = new GeminiDynamicQuestStoryProvider(
                    "gemini",
                    Properties.KDAOC_DYNAMIC_QUEST_STORY_GEMINI_MODEL,
                    new DynamicQuestGeminiQuota(
                        Properties.KDAOC_DYNAMIC_QUEST_STORY_GEMINI_PER_MINUTE_LIMIT,
                        Properties.KDAOC_DYNAMIC_QUEST_STORY_GEMINI_DAILY_LIMIT,
                        () => DateTime.UtcNow,
                        "gemini",
                        DynamicQuestServerPropertyDailyQuotaStore.Instance),
                    new DynamicQuestTokenBudget(
                        "gemini",
                        Properties.KDAOC_DYNAMIC_QUEST_STORY_GEMINI_DAILY_TOKEN_LIMIT,
                        DynamicQuestServerPropertyDailyQuotaStore.Instance)),
                ["secondary-local"] = new OpenAiCompatibleDynamicQuestStoryProvider(
                    "secondary-local",
                    Properties.KDAOC_DYNAMIC_QUEST_STORY_SECONDARY_LLM_API_URL,
                    Properties.KDAOC_DYNAMIC_QUEST_STORY_SECONDARY_LLM_MODEL,
                    Properties.WORLDAI_LLM_TIMEOUT_SECONDS)
            };

            List<IDynamicQuestStoryProvider> ordered = new();
            foreach (string name in SplitCsv(Properties.KDAOC_DYNAMIC_QUEST_STORY_PROVIDER_ORDER))
            {
                if (providers.TryGetValue(name, out IDynamicQuestStoryProvider provider))
                    ordered.Add(provider);
            }

            if (ordered.Count == 0)
            {
                ordered.Add(providers["openai"]);
                ordered.Add(providers["main-local"]);
                ordered.Add(providers["gemini"]);
                ordered.Add(providers["secondary-local"]);
            }

            return new DynamicQuestStoryService(ordered);
        }

        public DynamicQuestStoryGenerationResult TryGenerate(DynamicQuestStoryRequest request)
        {
            if (request == null)
                return DynamicQuestStoryGenerationResult.Fail("story request is missing");

            List<string> providerErrors = new();
            int minimumScore = StoryMinimumScore();
            bool compareProviders = Properties.KDAOC_DYNAMIC_QUEST_STORY_COMPARE_PROVIDERS_ENABLED;
            int compareMax = Math.Clamp(Properties.KDAOC_DYNAMIC_QUEST_STORY_COMPARE_MAX_PER_PREFILL, 1, 8);
            List<DynamicQuestStoryGenerationResult> candidates = compareProviders ? new List<DynamicQuestStoryGenerationResult>() : null;
            foreach (IDynamicQuestStoryProvider provider in m_providers)
            {
                DynamicQuestStoryGenerationResult result = provider.TryGenerate(request);
                if (!result.Success)
                {
                    providerErrors.Add($"{provider.Name}:{result.Error}");
                    continue;
                }

                result.ProviderName = string.IsNullOrWhiteSpace(result.ProviderName) ? provider.Name : result.ProviderName;
                result.ModelName = string.IsNullOrWhiteSpace(result.ModelName) ? provider.ModelName : result.ModelName;
                DynamicQuestStoryQuality rawQuality = EvaluateQualityDetails(request, result.Story);
                if (rawQuality.SafetyScore == 0)
                {
                    providerErrors.Add($"{provider.Name}:quality_below_minimum:{DescribeQualityGate(rawQuality, minimumScore)}");
                    continue;
                }

                result.Story = SanitizeStory(request, result.Story);
                DynamicQuestStoryQuality baseQuality = EvaluateQualityDetails(request, result.Story);
                result.Story = RepairWeakLocalizedStory(request, result.Story, baseQuality);
                baseQuality = EvaluateQualityDetails(request, result.Story);
                result.Story = RepairMissingStoryStructure(request, result.Story, baseQuality);
                result.Story.Quality = EvaluateQualityDetails(request, result.Story);
                if (result.Story.StructureRepaired)
                    AddQualityReason(result.Story.Quality, "story_structure_repaired");
                result.Story.QualityScore = result.Story.Quality.TotalScore;
                if (!MeetsStoryQualityGate(result.Story.Quality, minimumScore))
                {
                    providerErrors.Add($"{provider.Name}:quality_below_minimum:{DescribeQualityGate(result.Story.Quality, minimumScore)}");
                    continue;
                }
                if (compareProviders)
                {
                    candidates.Add(result);
                    if (candidates.Count < compareMax)
                        continue;

                    break;
                }

                return result;
            }

            if (compareProviders && candidates != null && candidates.Count > 0)
            {
                return candidates
                    .OrderByDescending(result => result.Story?.QualityScore ?? 0)
                    .ThenBy(result => result.ProviderName, StringComparer.OrdinalIgnoreCase)
                    .First();
            }

            string error = string.Join("|", providerErrors.Where(item => !string.IsNullOrWhiteSpace(item)));
            return DynamicQuestStoryGenerationResult.Fail(string.IsNullOrWhiteSpace(error)
                ? "no story provider configured"
                : error);
        }

        private static int StoryMinimumScore()
        {
            return Math.Clamp(Properties.KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE, 0, 100);
        }

        public static DynamicQuestTemplate ApplyStoryForTest(
            DynamicQuestTemplate template,
            DynamicQuestStoryText story,
            string providerName,
            string modelName = "")
        {
            return ApplyStory(template, story, providerName, modelName);
        }

        public static DynamicQuestTemplate ApplyStory(
            DynamicQuestTemplate template,
            DynamicQuestStoryText story,
            string providerName,
            string modelName = "")
        {
            template ??= new DynamicQuestTemplate();
            story ??= new DynamicQuestStoryText();
            DateTime now = DateTime.UtcNow;
            string target = template.TargetNameHint ?? string.Empty;
            DynamicQuestStoryRequest storyRequest = BuildStoryRequestFromTemplate(template);
            DynamicQuestStoryText sanitizedStory = SanitizeStory(storyRequest, story);
            DynamicQuestStoryQuality quality = EvaluateQualityDetails(storyRequest, sanitizedStory);
            List<string> tags = new(template.Tags ?? Array.Empty<string>());
            AddTag(tags, "llm-story");
            if (!string.IsNullOrWhiteSpace(providerName))
                AddTag(tags, $"llm-provider:{providerName.Trim()}");
            if (!string.IsNullOrWhiteSpace(modelName))
                AddTag(tags, $"llm-model:{modelName.Trim()}");
            if (sanitizedStory.StructureRepaired)
                AddTag(tags, "story-structure-repaired");

            return new DynamicQuestTemplate
            {
                TemplateId = template.TemplateId ?? string.Empty,
                Title = FirstNonEmpty(sanitizedStory.Title, template.Title),
                StorySeed = template.StorySeed ?? string.Empty,
                OfferText = PlaceholderizeTarget(FirstNonEmpty(sanitizedStory.OfferText, template.OfferText), target),
                ProgressText = PlaceholderizeTarget(FirstNonEmpty(sanitizedStory.ProgressText, template.ProgressText), target),
                FinishText = PlaceholderizeTarget(FirstNonEmpty(sanitizedStory.FinishText, template.FinishText), target),
                Realm = template.Realm ?? string.Empty,
                PreferredStartNpcName = template.PreferredStartNpcName ?? string.Empty,
                PreferredStartNpcInternalId = template.PreferredStartNpcInternalId ?? string.Empty,
                PreferredRegionId = template.PreferredRegionId,
                TargetNameHint = target,
                PreferredTargetNpcInternalId = template.PreferredTargetNpcInternalId ?? string.Empty,
                Count = Math.Max(1, template.Count),
                MinLevel = Math.Clamp(template.MinLevel, 1, 50),
                MaxLevel = Math.Clamp(Math.Max(template.MaxLevel, template.MinLevel), 1, 50),
                Source = "llm",
                Tags = tags,
                StoryProvider = providerName ?? string.Empty,
                StoryModel = modelName ?? string.Empty,
                StoryQualityScore = Math.Clamp(quality.TotalScore, 0, 100),
                StoryQualityJson = SerializeStoryMetadata(quality),
                StoryNarrativeJson = SerializeStoryMetadata(sanitizedStory.NarrativeScenes ?? Array.Empty<DynamicQuestNarrativeScene>()),
                StoryPresentationJson = SerializeStoryMetadata(sanitizedStory.PresentationBeats ?? Array.Empty<DynamicQuestPresentationBeat>()),
                StoryGeneratedAt = now,
                StoryLastUsedAt = now,
                StartMode = template.StartMode,
                Trigger = template.Trigger ?? string.Empty,
                WorldRevision = template.WorldRevision ?? string.Empty,
                CreatedAt = template.CreatedAt == default ? now : template.CreatedAt,
                UpdatedAt = now
            };
        }

        private static DynamicQuestStoryRequest BuildStoryRequestFromTemplate(DynamicQuestTemplate template)
        {
            return new DynamicQuestStoryRequest
            {
                TemplateId = template?.TemplateId ?? string.Empty,
                Realm = template?.Realm ?? string.Empty,
                StartNpcName = template?.PreferredStartNpcName ?? string.Empty,
                RegionId = template?.PreferredRegionId ?? 0,
                TargetName = template?.TargetNameHint ?? string.Empty,
                Count = Math.Max(1, template?.Count ?? 1),
                MinLevel = Math.Clamp(template?.MinLevel ?? 1, 1, 50),
                MaxLevel = Math.Clamp(Math.Max(template?.MaxLevel ?? 50, template?.MinLevel ?? 1), 1, 50),
                StorySeed = template?.StorySeed ?? string.Empty
            };
        }

        private static string SerializeStoryMetadata<T>(T value)
        {
            return JsonSerializer.Serialize(value, StoryJsonOptions);
        }

        internal static string BuildGeminiRequestJsonForTest(DynamicQuestStoryRequest request)
        {
            return BuildGeminiRequestJson(request);
        }

        internal static string BuildOpenAiRequestJsonForTest(string model, DynamicQuestStoryRequest request)
        {
            return JsonSerializer.Serialize(BuildOpenAiRequest(model, request), StoryJsonOptions);
        }

        internal static string BuildOpenAiResponsesRequestJsonForTest(string model, DynamicQuestStoryRequest request)
        {
            return JsonSerializer.Serialize(BuildOpenAiResponsesRequest(model, request), StoryJsonOptions);
        }

        internal static DynamicQuestStoryText ParseStoryJsonForTest(string json, DynamicQuestStoryRequest request)
        {
            return ParseStoryJson(json, request);
        }

        internal static int EvaluateQualityForTest(DynamicQuestStoryRequest request, DynamicQuestStoryText story)
        {
            return EvaluateQuality(request, story);
        }

        internal static DynamicQuestStoryQuality EvaluateQualityDetailsForTest(DynamicQuestStoryRequest request, DynamicQuestStoryText story)
        {
            return EvaluateQualityDetails(request, story);
        }

        internal static DynamicQuestStoryQuality EvaluateQualityDetailsForCache(DynamicQuestStoryRequest request, DynamicQuestStoryText story)
        {
            return EvaluateQualityDetails(request, story);
        }

        internal static bool IsStoryQualityAcceptableForCache(DynamicQuestStoryRequest request, DynamicQuestStoryText story)
        {
            DynamicQuestStoryQuality quality = EvaluateQualityDetails(request, story);
            return MeetsStoryQualityGate(quality, Math.Max(75, StoryMinimumScore())) &&
                   HasCacheReadyNarrativeText(story) &&
                   !(quality.Reasons ?? Array.Empty<string>()).Contains("generic_scaffold", StringComparer.OrdinalIgnoreCase) &&
                   !(quality.Reasons ?? Array.Empty<string>()).Contains("missing_specific_local_anchor", StringComparer.OrdinalIgnoreCase);
        }

        private static bool HasCacheReadyNarrativeText(DynamicQuestStoryText story)
        {
            if (story == null)
                return false;

            List<DynamicQuestNarrativeScene> scenes = (story.NarrativeScenes ?? Array.Empty<DynamicQuestNarrativeScene>())
                .Where(IsValidNarrativeScene)
                .ToList();
            List<DynamicQuestPresentationBeat> beats = (story.PresentationBeats ?? Array.Empty<DynamicQuestPresentationBeat>())
                .Where(IsValidPresentationBeat)
                .ToList();

            int journalReadyScenes = scenes.Count(scene =>
                !string.IsNullOrWhiteSpace(scene.JournalEntry) &&
                scene.JournalEntry.Trim().Length >= 12);
            if (scenes.Count >= 3 && journalReadyScenes < 3)
                return false;

            return true;
        }

        internal static DynamicQuestStoryText SanitizeStoryForTest(DynamicQuestStoryRequest request, DynamicQuestStoryText story)
        {
            return SanitizeStory(request, story);
        }

        internal static string PlaceholderizeTargetForTest(string text, string targetName)
        {
            return PlaceholderizeTarget(text, targetName);
        }

        private static DynamicQuestStoryText ParseStoryJson(string json, DynamicQuestStoryRequest request)
        {
            string normalized = NormalizeJsonContent(json);
            using JsonDocument document = JsonDocument.Parse(normalized);
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object)
                throw new InvalidOperationException("story response must be a JSON object");

            string returnedTarget = GetString(root, "target", 100);
            if (!string.IsNullOrWhiteSpace(returnedTarget) &&
                !string.Equals(returnedTarget, request.TargetName, StringComparison.Ordinal))
                throw new InvalidOperationException("story response target changed");

            int returnedCount = GetInt(root, "count", request.Count);
            if (returnedCount != request.Count)
                throw new InvalidOperationException("story response count changed");

            DynamicQuestStoryText parsed = new()
            {
                Title = GetString(root, "title", 120),
                OfferText = GetStringAny(root, 700, "offer", "offerText"),
                ProgressText = GetStringAny(root, 400, "progress", "progressText"),
                FinishText = GetStringAny(root, 400, "finish", "finishText"),
                NarrativeScenes = ParseNarrativeScenes(root),
                PresentationBeats = ParsePresentationBeats(root)
            };
            return SanitizeStory(request, parsed);
        }

        private static int EvaluateQuality(DynamicQuestStoryRequest request, DynamicQuestStoryText story)
        {
            return EvaluateQualityDetails(request, story).TotalScore;
        }

        private static DynamicQuestStoryQuality EvaluateQualityDetails(DynamicQuestStoryRequest request, DynamicQuestStoryText story)
        {
            if (story == null)
                return DynamicQuestStoryQuality.Empty;

            List<string> reasons = new();
            string combined = StoryCombinedText(story);
            int structureScore = 0;
            if (!string.IsNullOrWhiteSpace(story.Title))
                structureScore += 3;
            if (!string.IsNullOrWhiteSpace(story.OfferText))
                structureScore += 4;
            if (!string.IsNullOrWhiteSpace(story.ProgressText))
                structureScore += 4;
            if (!string.IsNullOrWhiteSpace(story.FinishText))
                structureScore += 4;
            if (structureScore < 15)
                reasons.Add("missing_story_field");

            int koreanScore = ContainsHangul(combined) ? 12 : 0;
            if (ContainsOperationalEnglish(combined))
                koreanScore = Math.Max(0, koreanScore - 4);
            bool hasAwkwardKoreanParticle = ContainsAwkwardKoreanParticle(combined);
            if (hasAwkwardKoreanParticle)
            {
                koreanScore = Math.Max(0, koreanScore - 6);
                reasons.Add("awkward_korean_particle");
            }

            int objectiveScore = 0;
            if (ContainsKillIntent(story.OfferText))
                objectiveScore += 5;
            if (ContainsKillIntent(story.ProgressText))
                objectiveScore += 5;
            if (ContainsKillIntent(story.FinishText))
                objectiveScore += 5;
            if (ContainsTargetOrPlaceholder(combined, request?.TargetName))
                objectiveScore += 5;
            if (objectiveScore < 15)
                reasons.Add("weak_objective_alignment");

            int immersionScore = 0;
            if (ContainsHangul(combined))
                immersionScore += 4;
            bool hasSpecificLocalAnchor = HasSpecificLocalAnchor(combined, request);
            bool hasGenericScaffold = HasGenericScaffoldText(combined);
            if (hasSpecificLocalAnchor)
                immersionScore += 6;
            if (HasConsequenceText(combined))
                immersionScore += 5;
            if (hasGenericScaffold)
                immersionScore = Math.Max(0, immersionScore - 6);
            if (immersionScore < 10)
                reasons.Add("weak_immersion");
            if (!hasSpecificLocalAnchor)
                reasons.Add("missing_specific_local_anchor");

            int narrativeScore = ScoreNarrative(story, reasons);
            int presentationScore = ScorePresentation(story, reasons);
            bool hasMechanicalObjectiveCopy = ContainsMechanicalObjectiveCopy(combined);
            bool hasSystemSpeakerOveruse = HasSystemSpeakerOveruse(story);
            bool hasSystemExpressionLeak = ContainsSystemExpressionLeak(combined);
            if (hasMechanicalObjectiveCopy)
                reasons.Add("mechanical_objective_copy");
            if (hasSystemExpressionLeak)
                reasons.Add("system_expression_leak");
            if (hasSystemSpeakerOveruse)
            {
                presentationScore = Math.Min(presentationScore, 4);
                reasons.Add("system_speaker_overuse");
            }
            if (narrativeScore == 0)
                reasons.Add("missing_narrative_scene");
            if (presentationScore == 0)
                reasons.Add("missing_presentation_beat");
            int rebindabilityScore = ScoreDynamicRebindability(combined, request, reasons);
            if (rebindabilityScore < 15)
                reasons.Add("weak_dynamic_rebindability");

            int safetyScore = hasMechanicalObjectiveCopy ||
                              hasSystemExpressionLeak ||
                              ContainsForbiddenOperationalText(combined) ||
                              ContainsUnsafePresentation(story) ||
                              ContainsUnsafeNarrative(story)
                ? 0
                : 15;
            if (safetyScore == 0)
                reasons.Add("unsafe_story_text");

            bool hasRepetitiveStorySkeleton = HasRepetitiveStorySkeleton(combined);
            bool hasRepeatedGenericPhrases = HasRepeatedGenericPhrases(combined);
            bool hasRepeatedSentenceOpenings = HasRepeatedSentenceOpenings(story);
            int diversityScore = hasRepeatedGenericPhrases ? 5 : 10;
            if (hasRepetitiveStorySkeleton)
            {
                diversityScore = Math.Min(diversityScore, 1);
                reasons.Add("repetitive_story_skeleton");
            }
            if (hasRepeatedSentenceOpenings)
            {
                diversityScore = Math.Min(diversityScore, 2);
                reasons.Add("repetitive_sentence_opening");
            }
            if (hasGenericScaffold)
            {
                diversityScore = Math.Min(diversityScore, 2);
                reasons.Add("generic_scaffold");
            }
            if (diversityScore < 10)
                reasons.Add("generic_repetition");

            int total = structureScore +
                        koreanScore +
                        objectiveScore +
                        immersionScore +
                        narrativeScore +
                        presentationScore +
                        rebindabilityScore +
                        safetyScore +
                        diversityScore;
            if (hasGenericScaffold || !hasSpecificLocalAnchor)
                total = Math.Min(total, 74);
            if (narrativeScore == 0)
                total = Math.Min(total, 74);
            if (presentationScore == 0)
                total = Math.Min(total, 74);
            if (hasMechanicalObjectiveCopy)
                total = Math.Min(total, 64);
            if (hasSystemSpeakerOveruse)
                total = Math.Min(total, 84);
            if (rebindabilityScore < 15)
                total = Math.Min(total, 74);
            if (hasRepeatedGenericPhrases)
                total = Math.Min(total, 94);
            if (hasRepetitiveStorySkeleton)
                total = Math.Min(total, 74);
            if (hasRepeatedSentenceOpenings)
                total = Math.Min(total, 74);
            if (hasAwkwardKoreanParticle)
                total = Math.Min(total, 74);
            if (hasSystemExpressionLeak)
                total = 0;

            return new DynamicQuestStoryQuality
            {
                TotalScore = Math.Clamp(total, 0, 100),
                StructureScore = Math.Clamp(structureScore, 0, 15),
                KoreanScore = Math.Clamp(koreanScore, 0, 15),
                ObjectiveScore = Math.Clamp(objectiveScore, 0, 20),
                ImmersionScore = Math.Clamp(immersionScore, 0, 15),
                NarrativeScore = Math.Clamp(narrativeScore, 0, 12),
                PresentationScore = Math.Clamp(presentationScore, 0, 8),
                RebindabilityScore = Math.Clamp(rebindabilityScore, 0, 15),
                SafetyScore = Math.Clamp(safetyScore, 0, 15),
                DiversityScore = Math.Clamp(diversityScore, 0, 10),
                Reasons = reasons.Distinct(StringComparer.OrdinalIgnoreCase).ToList()
            };
        }

        private static bool MeetsStoryQualityGate(DynamicQuestStoryQuality quality, int minimumScore)
        {
            if (quality == null)
                return false;

            return quality.TotalScore >= minimumScore &&
                   quality.NarrativeScore > 0 &&
                   quality.PresentationScore > 0 &&
                   quality.SafetyScore > 0 &&
                   !HasBlockingQualityReason(quality);
        }

        private static bool HasBlockingQualityReason(DynamicQuestStoryQuality quality)
        {
            IList<string> reasons = quality?.Reasons ?? Array.Empty<string>();
            return reasons.Contains("generic_scaffold", StringComparer.OrdinalIgnoreCase) ||
                   reasons.Contains("missing_specific_local_anchor", StringComparer.OrdinalIgnoreCase) ||
                   reasons.Contains("weak_dynamic_rebindability", StringComparer.OrdinalIgnoreCase) ||
                   reasons.Contains("awkward_korean_particle", StringComparer.OrdinalIgnoreCase) ||
                   reasons.Contains("system_expression_leak", StringComparer.OrdinalIgnoreCase) ||
                   reasons.Contains("repetitive_sentence_opening", StringComparer.OrdinalIgnoreCase) ||
                   reasons.Contains("repetitive_story_skeleton", StringComparer.OrdinalIgnoreCase);
        }

        private static void AddQualityReason(DynamicQuestStoryQuality quality, string reason)
        {
            if (quality == null || string.IsNullOrWhiteSpace(reason))
                return;

            List<string> reasons = new(quality.Reasons ?? Array.Empty<string>());
            if (!reasons.Contains(reason, StringComparer.OrdinalIgnoreCase))
                reasons.Add(reason);
            quality.Reasons = reasons;
        }

        private static string DescribeQualityGate(DynamicQuestStoryQuality quality, int minimumScore)
        {
            if (quality == null)
                return $"0/{minimumScore}:missing_quality";

            string reasons = quality.Reasons == null || quality.Reasons.Count == 0
                ? "none"
                : string.Join(",", quality.Reasons);
            return $"{quality.TotalScore}/{minimumScore}:narrative={quality.NarrativeScore}:presentation={quality.PresentationScore}:safety={quality.SafetyScore}:reasons={reasons}";
        }

        private static string StoryCombinedText(DynamicQuestStoryText story)
        {
            List<string> parts = new()
            {
                story?.Title ?? string.Empty,
                story?.OfferText ?? string.Empty,
                story?.ProgressText ?? string.Empty,
                story?.FinishText ?? string.Empty
            };

            foreach (DynamicQuestNarrativeScene scene in story?.NarrativeScenes ?? Array.Empty<DynamicQuestNarrativeScene>())
            {
                parts.Add(scene.Title ?? string.Empty);
                parts.Add(scene.Body ?? string.Empty);
                parts.Add(scene.JournalEntry ?? string.Empty);
            }

            foreach (DynamicQuestPresentationBeat beat in story?.PresentationBeats ?? Array.Empty<DynamicQuestPresentationBeat>())
                parts.Add(beat.Text ?? string.Empty);

            return string.Join(" ", parts);
        }

        private static int ScoreNarrative(DynamicQuestStoryText story, List<string> reasons)
        {
            int score = 0;
            int validScenes = 0;
            foreach (DynamicQuestNarrativeScene scene in story?.NarrativeScenes ?? Array.Empty<DynamicQuestNarrativeScene>())
            {
                if (!IsValidNarrativeScene(scene))
                    continue;

                validScenes++;
                score += 4;
                if (ContainsHangul(scene.Body) && scene.Body.Length >= 40)
                    score += 3;
                if (!string.IsNullOrWhiteSpace(scene.JournalEntry))
                    score += 3;
                if (!string.IsNullOrWhiteSpace(scene.Mood))
                    score += 2;
            }

            if (score > 0)
                reasons.Add("narrative_scene");
            if (validScenes == 1)
                score = Math.Min(score, 8);
            else if (validScenes == 2)
                score = Math.Min(score, 10);
            return Math.Clamp(score, 0, 12);
        }

        private static int ScorePresentation(DynamicQuestStoryText story, List<string> reasons)
        {
            int score = 0;
            int validBeats = 0;
            foreach (DynamicQuestPresentationBeat beat in story?.PresentationBeats ?? Array.Empty<DynamicQuestPresentationBeat>())
            {
                if (!IsValidPresentationBeat(beat))
                    continue;

                validBeats++;
                score += 4;
                if (!string.IsNullOrWhiteSpace(beat.Emotion))
                    score += 2;
                if (!string.IsNullOrWhiteSpace(beat.Emote))
                    score += 2;
            }

            if (score > 0)
                reasons.Add("presentation_beat");
            if (validBeats == 1)
                score = Math.Min(score, 6);
            return Math.Clamp(score, 0, 8);
        }

        private static DynamicQuestStoryText SanitizeStory(DynamicQuestStoryRequest request, DynamicQuestStoryText story)
        {
            if (story == null)
                return new DynamicQuestStoryText();

            return new DynamicQuestStoryText
            {
                Title = story.Title ?? string.Empty,
                OfferText = story.OfferText ?? string.Empty,
                ProgressText = story.ProgressText ?? string.Empty,
                FinishText = story.FinishText ?? string.Empty,
                QualityScore = story.QualityScore,
                StructureRepaired = story.StructureRepaired,
                NarrativeScenes = (story.NarrativeScenes ?? Array.Empty<DynamicQuestNarrativeScene>())
                    .Where(IsValidNarrativeScene)
                    .Select(scene => new DynamicQuestNarrativeScene
                    {
                        NodeId = NormalizeAllowlisted(scene.NodeId, AllowedNodeIds),
                        SceneType = NormalizeAllowlisted(scene.SceneType, AllowedSceneTypes),
                        Title = TrimTo(scene.Title, 120),
                        Body = PlaceholderizeTarget(TrimTo(scene.Body, 1200), request?.TargetName),
                        JournalEntry = PlaceholderizeTarget(TrimTo(scene.JournalEntry, 400), request?.TargetName),
                        Mood = NormalizeAllowlisted(scene.Mood, AllowedMoods),
                        RevealPolicy = NormalizeAllowlisted(scene.RevealPolicy, AllowedRevealPolicies)
                    })
                    .ToList(),
                PresentationBeats = (story.PresentationBeats ?? Array.Empty<DynamicQuestPresentationBeat>())
                    .Where(IsValidPresentationBeat)
                    .Select(beat => new DynamicQuestPresentationBeat
                    {
                        NodeId = NormalizeAllowlisted(beat.NodeId, AllowedNodeIds),
                        Trigger = NormalizeAllowlisted(beat.Trigger, AllowedPresentationTriggers),
                        Speaker = NormalizeAllowlisted(beat.Speaker, AllowedSpeakers),
                        Text = PlaceholderizeTarget(TrimTo(beat.Text, 240), request?.TargetName),
                        Emotion = NormalizeAllowlisted(beat.Emotion, AllowedEmotions),
                        Emote = NormalizeAllowlisted(beat.Emote, AllowedEmotes),
                        CinematicAction = NormalizeAllowlisted(beat.CinematicAction, AllowedCinematicActions),
                        SceneRole = NormalizeSceneToken(beat.SceneRole),
                        Formation = NormalizeAllowlisted(beat.Formation, AllowedCinematicFormations),
                        ActorCount = Math.Clamp(beat.ActorCount, 0, 100),
                        DelayMs = Math.Clamp(beat.DelayMs, 0, 6000)
                    })
                    .ToList()
            };
        }

        private static DynamicQuestStoryText RepairMissingStoryStructure(
            DynamicQuestStoryRequest request,
            DynamicQuestStoryText story,
            DynamicQuestStoryQuality baseQuality)
        {
            if (!CanRepairMissingStoryStructure(baseQuality))
                return story;

            bool missingNarrative = !(story?.NarrativeScenes ?? Array.Empty<DynamicQuestNarrativeScene>()).Any(IsValidNarrativeScene);
            bool missingPresentation = !(story?.PresentationBeats ?? Array.Empty<DynamicQuestPresentationBeat>()).Any(IsValidPresentationBeat);
            if (!missingNarrative && !missingPresentation)
                return story;

            DynamicQuestStoryText repaired = new()
            {
                Title = story?.Title ?? string.Empty,
                OfferText = story?.OfferText ?? string.Empty,
                ProgressText = story?.ProgressText ?? string.Empty,
                FinishText = story?.FinishText ?? string.Empty,
                QualityScore = story?.QualityScore ?? 0,
                StructureRepaired = true,
                NarrativeScenes = missingNarrative
                    ? BuildRepairedNarrativeScenes(request)
                    : story?.NarrativeScenes ?? Array.Empty<DynamicQuestNarrativeScene>(),
                PresentationBeats = missingPresentation
                    ? BuildRepairedPresentationBeats(request)
                    : story?.PresentationBeats ?? Array.Empty<DynamicQuestPresentationBeat>()
            };

            return SanitizeStory(request, repaired);
        }

        private static DynamicQuestStoryText RepairWeakLocalizedStory(
            DynamicQuestStoryRequest request,
            DynamicQuestStoryText story,
            DynamicQuestStoryQuality baseQuality)
        {
            if (!CanRepairWeakLocalizedStory(baseQuality))
                return story;

            IList<string> reasons = baseQuality.Reasons ?? Array.Empty<string>();
            bool needsRepair =
                reasons.Contains("generic_scaffold", StringComparer.OrdinalIgnoreCase) ||
                reasons.Contains("missing_specific_local_anchor", StringComparer.OrdinalIgnoreCase) ||
                reasons.Contains("weak_immersion", StringComparer.OrdinalIgnoreCase);
            if (!needsRepair)
                return story;

            string npc = string.IsNullOrWhiteSpace(request?.StartNpcName) ? "현장의 목격자" : "{{start_npc}}";
            string realm = string.IsNullOrWhiteSpace(request?.Realm) || string.Equals(request.Realm, "Unknown", StringComparison.OrdinalIgnoreCase)
                ? "이 지역"
                : "{{realm}}";
            string landmark = RealmLandmark(request?.Realm);
            string texture = RealmTexture(request?.Realm);

            DynamicQuestStoryText repaired = new()
            {
                Title = $"{landmark}에 남은 찢긴 흔적",
                OfferText = $"{npc}은 {realm} {landmark} 근처에서 발견된 {texture} 자국을 짚으며 {{{{target}}}} 처치를 부탁했다.",
                ProgressText = $"{realm} {landmark} 주변의 증거를 따라가 {{{{target}}}} 위협을 끊어내야 한다.",
                FinishText = $"{landmark}의 경계가 풀리고 {{{{target}}}} 위협이 사라졌다는 소식이 {realm} 사람들에게 전해졌다.",
                QualityScore = story?.QualityScore ?? 0,
                StructureRepaired = true,
                NarrativeScenes = BuildRepairedNarrativeScenes(request),
                PresentationBeats = BuildRepairedPresentationBeats(request)
            };

            return SanitizeStory(request, repaired);
        }

        private static bool CanRepairWeakLocalizedStory(DynamicQuestStoryQuality quality)
        {
            if (quality == null)
                return false;

            return quality.SafetyScore > 0 &&
                   quality.StructureScore >= 15 &&
                   quality.KoreanScore > 0 &&
                   quality.ObjectiveScore >= 15 &&
                   !(quality.Reasons ?? Array.Empty<string>()).Contains("unsafe_story_text", StringComparer.OrdinalIgnoreCase);
        }

        private static bool CanRepairMissingStoryStructure(DynamicQuestStoryQuality quality)
        {
            if (quality == null)
                return false;

            return quality.SafetyScore > 0 &&
                   quality.StructureScore >= 15 &&
                   quality.KoreanScore > 0 &&
                   quality.ObjectiveScore >= 15 &&
                   quality.ImmersionScore >= 10 &&
                   !HasBlockingQualityReason(quality) &&
                   !(quality.Reasons ?? Array.Empty<string>()).Contains("unsafe_story_text", StringComparer.OrdinalIgnoreCase);
        }

        private static IList<DynamicQuestNarrativeScene> BuildRepairedNarrativeScenes(DynamicQuestStoryRequest request)
        {
            string npc = string.IsNullOrWhiteSpace(request?.StartNpcName) ? "현장의 목격자" : "{{start_npc}}";
            string realm = string.IsNullOrWhiteSpace(request?.Realm) || string.Equals(request.Realm, "Unknown", StringComparison.OrdinalIgnoreCase)
                ? "이 지역"
                : "{{realm}}";
            string landmark = RealmLandmark(request?.Realm);
            string texture = RealmTexture(request?.Realm);

            return new[]
            {
                new DynamicQuestNarrativeScene
                {
                    NodeId = "talk",
                    SceneType = "Intro",
                    Title = $"{landmark}의 낮은 경고",
                    Body = $"{npc}은 {realm} {landmark} 근처의 젖은 흙을 살피며 {{{{target}}}}가 밤사이 울타리를 찢고 지나갔다고 말했다. {texture} 사이에는 부러진 창대와 급히 끌린 발자국이 남아 있었다.",
                    JournalEntry = $"{npc}에게서 {realm} {landmark} 근처로 번지는 {{{{target}}}} 위협을 막아 달라는 부탁을 받았다.",
                    Mood = "ominous",
                    RevealPolicy = "FirstSeenOnly"
                },
                new DynamicQuestNarrativeScene
                {
                    NodeId = "explore",
                    SceneType = "Discovery",
                    Title = "부러진 창대의 길",
                    Body = $"길가의 피 묻은 천 조각과 {texture} 냄새가 같은 곳을 가리킨다. {{{{target}}}}를 지금 제압하지 못하면 {realm}의 밤길은 더 오래 비게 될 것이다.",
                    JournalEntry = $"{realm}의 현장 증거가 {{{{target}}}} 은신처로 이어진다는 사실을 확인했다.",
                    Mood = "urgent",
                    RevealPolicy = "EveryInteraction"
                },
                new DynamicQuestNarrativeScene
                {
                    NodeId = "return",
                    SceneType = "Return",
                    Title = "다시 켜진 길목의 불",
                    Body = $"{{{{target}}}} 위협을 꺾자 {landmark} 근처의 횃불이 다시 곧게 섰다. {npc}에게 돌아가면 {realm} 사람들도 오늘 밤 문을 덜 두드리게 될 것이다.",
                    JournalEntry = $"{{{{target}}}}를 제압했다. {npc}에게 {realm} 길목이 다시 안전해졌다고 알려야 한다.",
                    Mood = "relieved",
                    RevealPolicy = "FirstSeenOnly"
                }
            };
        }

        private static IList<DynamicQuestPresentationBeat> BuildRepairedPresentationBeats(DynamicQuestStoryRequest request)
        {
            bool hasNpc = !string.IsNullOrWhiteSpace(request?.StartNpcName);
            string landmark = RealmLandmark(request?.Realm);
            string speaker = hasNpc ? "StartNpc" : "System";

            return new[]
            {
                new DynamicQuestPresentationBeat
                {
                    NodeId = "talk",
                    Trigger = hasNpc ? "OnNpcInteract" : "OnNodeEnter",
                    Speaker = speaker,
                    Text = hasNpc
                        ? $"{landmark} 쪽에서 방금 비명이 멎었습니다. {{{{target}}}}를 오래 두면 안 됩니다."
                        : $"{landmark} 근처에 {{{{target}}}}가 지나간 자국과 급히 꺼진 횃불이 남아 있습니다.",
                    Emotion = hasNpc ? "fear" : "caution",
                    Emote = hasNpc ? "Shiver" : "Point",
                    CinematicAction = "witness_point",
                    SceneRole = "contract_witness",
                    Formation = "escort",
                    ActorCount = 3
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "explore",
                    Trigger = "OnExplore",
                    Speaker = "System",
                    Text = $"{landmark} 바깥의 표식이 끊기자, 망보던 자가 뒤로 빠지고 남은 경비가 길을 가리킵니다.",
                    Emotion = "suspicion",
                    Emote = "Point",
                    CinematicAction = "scout_retreat",
                    SceneRole = "lookout_escape",
                    Formation = "escape",
                    ActorCount = 4,
                    DelayMs = 700
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "kill",
                    Trigger = "OnKill",
                    Speaker = "System",
                    Text = $"{{{{target}}}} 위협이 쓰러지자 숨어 있던 매복 병력이 모습을 드러내고, 방패 든 경비가 탈출로를 막습니다.",
                    Emotion = "urgency",
                    Emote = "Point",
                    CinematicAction = "ambush_reveal",
                    SceneRole = "ambush_wave",
                    Formation = "ambush",
                    ActorCount = 8
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "kill",
                    Trigger = "OnKill",
                    Speaker = "Companion",
                    Text = "아직 끝난 게 아닙니다. 도망치는 목격자를 놓치면 이 표식은 다음 밤에 다시 돌아옵니다.",
                    Emotion = "warning",
                    Emote = "Salute",
                    CinematicAction = "defender_intercept",
                    SceneRole = "escape_intercept",
                    Formation = "line",
                    ActorCount = 6,
                    DelayMs = 900
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "return",
                    Trigger = "OnNodeEnter",
                    Speaker = "System",
                    Text = $"{landmark}로 돌아오는 길에 남은 경비가 한 걸음 물러서며 보고할 길을 열어 줍니다.",
                    Emotion = "relief",
                    Emote = "Bow",
                    CinematicAction = "fallback_guard",
                    SceneRole = "debrief_guard",
                    Formation = "escort",
                    ActorCount = 3,
                    DelayMs = 500
                },
                new DynamicQuestPresentationBeat
                {
                    NodeId = "return",
                    Trigger = "OnComplete",
                    Speaker = speaker,
                    Text = hasNpc
                        ? "오늘 밤은 문을 걸어 잠그기 전에 서로의 이름을 부를 수 있겠군요."
                        : $"{landmark}의 경계 소리가 잦아들고, 길목의 불빛이 다시 안정됩니다.",
                    Emotion = hasNpc ? "gratitude" : "relief",
                    Emote = hasNpc ? "Bow" : "Smile",
                    CinematicAction = "hold_ground",
                    SceneRole = "watch_restored",
                    Formation = "line",
                    ActorCount = 4,
                    DelayMs = 1000
                }
            };
        }

        private static string RealmLandmark(string realm)
        {
            if (string.Equals(realm, "Midgard", StringComparison.OrdinalIgnoreCase))
                return "롱하우스 길목";
            if (string.Equals(realm, "Hibernia", StringComparison.OrdinalIgnoreCase))
                return "고리석 숲길";
            if (string.Equals(realm, "Albion", StringComparison.OrdinalIgnoreCase))
                return "수도원 울타리";

            return "마을 길목";
        }

        private static string RealmTexture(string realm)
        {
            if (string.Equals(realm, "Midgard", StringComparison.OrdinalIgnoreCase))
                return "눈밭과 룬 새긴 말뚝";
            if (string.Equals(realm, "Hibernia", StringComparison.OrdinalIgnoreCase))
                return "수풀과 드루이드 표식";
            if (string.Equals(realm, "Albion", StringComparison.OrdinalIgnoreCase))
                return "브리튼 성벽 그림자와 수도원 종소리";

            return "부러진 수레바퀴와 젖은 흙";
        }

        private static readonly HashSet<string> AllowedNodeIds = NewSet("talk", "explore", "kill", "return", "choice", "observe_signal", "complete");
        private static readonly HashSet<string> AllowedSceneTypes = NewSet("Intro", "Discovery", "Threat", "Return", "Choice", "Completion", "Aftermath");
        private static readonly HashSet<string> AllowedMoods = NewSet("ominous", "urgent", "tragic", "hopeful", "grim", "mysterious", "relieved", "neutral");
        private static readonly HashSet<string> AllowedRevealPolicies = NewSet("FirstSeenOnly", "EveryInteraction", "ManualReviewOnly");
        private static readonly HashSet<string> AllowedPresentationTriggers = NewSet(
            "OnAccept",
            "OnNodeEnter",
            "OnNpcInteract",
            "OnExplore",
            "OnKill",
            "OnChoiceShown",
            "OnChoiceSelected",
            "OnWorldSignal",
            "OnComplete");
        private static readonly HashSet<string> AllowedSpeakers = NewSet("StartNpc", "TargetNpc", "System", "Companion");
        private static readonly HashSet<string> AllowedEmotions = NewSet(
            "fear",
            "urgency",
            "urgent",
            "warning",
            "ominous",
            "anxious",
            "hope",
            "hopeful",
            "confusion",
            "relief",
            "anger",
            "sorrow",
            "suspicion",
            "pride",
            "caution",
            "gratitude",
            "neutral",
            "celebration");
        private static readonly HashSet<string> AllowedEmotes = NewSet("Shiver", "Point", "Smile", "Angry", "Cry", "Ponder", "Salute", "No", "Bow", "Cheer", "Cower");
        private static readonly HashSet<string> AllowedCinematicActions = NewSet(
            "witness_point",
            "scout_retreat",
            "ambush_reveal",
            "defender_intercept",
            "ritual_interrupt",
            "threat_standoff",
            "combat_stance",
            "hold_ground",
            "guard_advance",
            "fallback_guard");
        private static readonly HashSet<string> AllowedCinematicFormations = NewSet("escort", "patrol", "ambush", "line", "escape", "ring", "wedge");

        private static HashSet<string> NewSet(params string[] values)
        {
            return new HashSet<string>(values ?? Array.Empty<string>(), StringComparer.OrdinalIgnoreCase);
        }

        private static bool IsValidNarrativeScene(DynamicQuestNarrativeScene scene)
        {
            return scene != null &&
                   IsAllowed(scene.NodeId, AllowedNodeIds) &&
                   IsAllowed(scene.SceneType, AllowedSceneTypes) &&
                   IsAllowed(scene.Mood, AllowedMoods, allowEmpty: true) &&
                   IsAllowed(scene.RevealPolicy, AllowedRevealPolicies) &&
                   !ContainsForbiddenOperationalText($"{scene.Title} {scene.Body} {scene.JournalEntry}") &&
                   !string.IsNullOrWhiteSpace(scene.Body) &&
                   scene.Body.Length <= 1600 &&
                   scene.JournalEntry.Length <= 500;
        }

        private static bool IsValidPresentationBeat(DynamicQuestPresentationBeat beat)
        {
            return beat != null &&
                   IsAllowed(beat.NodeId, AllowedNodeIds) &&
                   IsAllowed(beat.Trigger, AllowedPresentationTriggers) &&
                   IsAllowed(beat.Speaker, AllowedSpeakers) &&
                   IsAllowed(beat.Emotion, AllowedEmotions, allowEmpty: true) &&
                   IsAllowed(beat.Emote, AllowedEmotes, allowEmpty: true) &&
                   IsAllowed(beat.CinematicAction, AllowedCinematicActions, allowEmpty: true) &&
                   IsAllowed(beat.Formation, AllowedCinematicFormations, allowEmpty: true) &&
                   beat.ActorCount >= 0 &&
                   beat.ActorCount <= 100 &&
                   beat.DelayMs >= 0 &&
                   beat.DelayMs <= 6000 &&
                   !ContainsForbiddenOperationalText(beat.Text) &&
                   !ContainsForbiddenOperationalText(beat.SceneRole) &&
                   !LooksLikeRawNumber(beat.Emote) &&
                   !string.IsNullOrWhiteSpace(beat.Text);
        }

        private static bool IsAllowed(string value, HashSet<string> allowed, bool allowEmpty = false)
        {
            string normalized = (value ?? string.Empty).Trim();
            return (allowEmpty && normalized.Length == 0) || allowed.Contains(normalized);
        }

        private static string NormalizeAllowlisted(string value, HashSet<string> allowed)
        {
            string normalized = (value ?? string.Empty).Trim();
            return allowed.FirstOrDefault(item => string.Equals(item, normalized, StringComparison.OrdinalIgnoreCase)) ?? string.Empty;
        }

        private static string NormalizeSceneToken(string value)
        {
            string normalized = Regex.Replace((value ?? string.Empty).Trim().ToLowerInvariant(), "[^a-z0-9_-]+", "_").Trim('_');
            if (normalized.Length > 40)
                normalized = normalized.Substring(0, 40);
            return normalized;
        }

        private static string TrimTo(string value, int maxLength)
        {
            string text = (value ?? string.Empty).Trim();
            return text.Length <= maxLength ? text : text.Substring(0, maxLength);
        }

        private static bool LooksLikeRawNumber(string value)
        {
            return int.TryParse((value ?? string.Empty).Trim(), out _);
        }

        private static bool ContainsUnsafePresentation(DynamicQuestStoryText story)
        {
            return (story?.PresentationBeats ?? Array.Empty<DynamicQuestPresentationBeat>())
                .Any(beat => !IsValidPresentationBeat(beat));
        }

        private static bool ContainsUnsafeNarrative(DynamicQuestStoryText story)
        {
            return (story?.NarrativeScenes ?? Array.Empty<DynamicQuestNarrativeScene>())
                .Any(scene => !IsValidNarrativeScene(scene));
        }

        private static bool HasSpecificLocalAnchor(string text, DynamicQuestStoryRequest request)
        {
            string value = text ?? string.Empty;
            int anchors = 0;
            bool hasStartNpc = !string.IsNullOrWhiteSpace(request?.StartNpcName);
            bool mentionsStartNpc = hasStartNpc &&
                                    (value.Contains("{{start_npc}}", StringComparison.OrdinalIgnoreCase) ||
                                     ContainsStartNpcAnchor(value, request.StartNpcName));
            if (hasStartNpc && !mentionsStartNpc)
                return false;
            if (mentionsStartNpc)
                anchors++;
            if (!string.IsNullOrWhiteSpace(request?.Realm) &&
                !string.Equals(request.Realm, "Unknown", StringComparison.OrdinalIgnoreCase) &&
                (value.Contains("{{realm}}", StringComparison.OrdinalIgnoreCase) ||
                 ContainsRealmAnchor(value, request.Realm)))
                anchors++;
            if (!hasStartNpc && ContainsTargetOrPlaceholder(value, request?.TargetName))
                anchors++;
            if (ContainsConcreteLocalTexture(value))
                anchors++;
            if (ContainsRealmTexture(value, request?.Realm))
                anchors++;

            return anchors >= 2;
        }

        private static int ScoreDynamicRebindability(string text, DynamicQuestStoryRequest request, List<string> reasons)
        {
            string value = text ?? string.Empty;
            int score = 0;

            if (value.Contains("{{target}}", StringComparison.OrdinalIgnoreCase))
                score += 5;
            else if (ContainsTargetOrPlaceholder(value, request?.TargetName))
            {
                score += 2;
                reasons.Add("target_not_placeholderized");
            }
            else
            {
                reasons.Add("target_not_placeholderized");
            }

            if (string.IsNullOrWhiteSpace(request?.Realm) ||
                string.Equals(request.Realm, "Unknown", StringComparison.OrdinalIgnoreCase))
            {
                score += 5;
            }
            else if (value.Contains("{{realm}}", StringComparison.OrdinalIgnoreCase))
            {
                score += 5;
            }
            else if (ContainsRealmAnchor(value, request.Realm))
            {
                score += 2;
                reasons.Add("realm_not_placeholderized");
            }
            else
            {
                reasons.Add("realm_not_placeholderized");
            }

            if (string.IsNullOrWhiteSpace(request?.StartNpcName))
            {
                score += 5;
            }
            else if (value.Contains("{{start_npc}}", StringComparison.OrdinalIgnoreCase))
            {
                score += 5;
            }
            else if (ContainsStartNpcAnchor(value, request.StartNpcName))
            {
                score += 1;
                reasons.Add("start_npc_not_placeholderized");
            }
            else
            {
                reasons.Add("start_npc_not_placeholderized");
            }

            return score;
        }

        private static bool ContainsRealmAnchor(string text, string realm)
        {
            string value = text ?? string.Empty;
            string realmValue = realm ?? string.Empty;
            if (string.IsNullOrWhiteSpace(realmValue))
                return false;
            if (value.Contains(realmValue, StringComparison.OrdinalIgnoreCase))
                return true;

            string localized = realmValue.ToLowerInvariant() switch
            {
                "albion" => "알비온",
                "midgard" => "미드가르드",
                "hibernia" => "하이버니아",
                _ => string.Empty
            };
            return !string.IsNullOrWhiteSpace(localized) &&
                   value.Contains(localized, StringComparison.OrdinalIgnoreCase);
        }

        private static bool ContainsStartNpcAnchor(string text, string startNpcName)
        {
            string value = text ?? string.Empty;
            string npc = (startNpcName ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(npc))
                return false;
            if (value.Contains(npc, StringComparison.OrdinalIgnoreCase))
                return true;

            foreach (string candidate in LocalizedStartNpcAnchorCandidates(npc))
            {
                if (!string.IsNullOrWhiteSpace(candidate) &&
                    value.Contains(candidate, StringComparison.OrdinalIgnoreCase))
                    return true;
            }

            return false;
        }

        private static IEnumerable<string> LocalizedStartNpcAnchorCandidates(string startNpcName)
        {
            string[] tokens = (startNpcName ?? string.Empty)
                .Split(new[] { ' ', '\t', '-', '_' }, StringSplitOptions.RemoveEmptyEntries);
            if (tokens.Length == 0)
                yield break;

            string[] localizedTokens = tokens
                .SelectMany(LocalizedNameTokenCandidates)
                .Where(candidate => !string.IsNullOrWhiteSpace(candidate))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToArray();
            foreach (string token in localizedTokens)
                yield return token;

            if (localizedTokens.Length >= 2)
                yield return string.Join(" ", localizedTokens.Take(2));
        }

        private static IEnumerable<string> LocalizedNameTokenCandidates(string token)
        {
            string value = (token ?? string.Empty).Trim();
            if (value.Length == 0)
                yield break;

            foreach (string title in LocalizedTitleTokenCandidates(value))
                yield return title;

            string transliterated = TransliterateAsciiTokenToHangul(value);
            if (!string.IsNullOrWhiteSpace(transliterated))
                yield return transliterated;
        }

        private static IEnumerable<string> LocalizedTitleTokenCandidates(string token)
        {
            switch ((token ?? string.Empty).Trim().ToLowerInvariant())
            {
                case "brother":
                    yield return "브라더";
                    yield return "형제";
                    break;
                case "sister":
                    yield return "시스터";
                    yield return "자매";
                    break;
                case "sir":
                    yield return "경";
                    break;
                case "lady":
                    yield return "레이디";
                    break;
                case "master":
                    yield return "마스터";
                    yield return "스승";
                    break;
                case "captain":
                    yield return "캡틴";
                    yield return "대장";
                    break;
                case "guard":
                    yield return "가드";
                    yield return "경비병";
                    break;
            }
        }

        private static string TransliterateAsciiTokenToHangul(string token)
        {
            string value = new((token ?? string.Empty)
                .Where(ch => ch >= 'A' && ch <= 'Z' || ch >= 'a' && ch <= 'z')
                .Select(char.ToLowerInvariant)
                .ToArray());
            if (value.Length == 0)
                return string.Empty;

            StringBuilder output = new();
            int index = 0;
            while (index < value.Length)
            {
                char initialChar = value[index];
                int initial = HangulInitialIndex(initialChar);
                if (initial < 0)
                    initial = 11;

                index++;
                if (index >= value.Length || HangulVowelIndex(value, index, out string vowelText) < 0)
                {
                    output.Append(ComposeHangul(initial, 18, 0));
                    continue;
                }

                int vowel = HangulVowelIndex(value, index, out vowelText);
                index += vowelText.Length;
                int final = 0;
                if (index < value.Length)
                {
                    int candidateFinal = HangulFinalIndex(value[index]);
                    bool nextStartsSyllable = index + 1 < value.Length &&
                                             HangulVowelIndex(value, index + 1, out _) >= 0;
                    if (candidateFinal > 0 && !nextStartsSyllable)
                    {
                        final = candidateFinal;
                        index++;
                    }
                }

                output.Append(ComposeHangul(initial, vowel, final));
            }

            return output.ToString();
        }

        private static char ComposeHangul(int initial, int vowel, int final)
        {
            return (char)('\uac00' + (initial * 21 + vowel) * 28 + final);
        }

        private static int HangulInitialIndex(char ch)
        {
            return ch switch
            {
                'g' => 0,
                'k' => 15,
                'n' => 2,
                'd' => 3,
                't' => 16,
                'r' => 5,
                'l' => 5,
                'm' => 6,
                'b' => 7,
                'v' => 7,
                'p' => 17,
                's' => 9,
                'z' => 9,
                'j' => 12,
                'c' => 14,
                'q' => 15,
                'h' => 18,
                'f' => 17,
                'w' => 11,
                'y' => 11,
                _ => -1
            };
        }

        private static int HangulVowelIndex(string text, int index, out string matched)
        {
            foreach ((string roman, int vowel) in new[]
            {
                ("ae", 1),
                ("eo", 4),
                ("eu", 18),
                ("oo", 13),
                ("ou", 13),
                ("a", 0),
                ("e", 5),
                ("i", 20),
                ("y", 20),
                ("o", 8),
                ("u", 13)
            })
            {
                if (index + roman.Length <= text.Length &&
                    string.Equals(text.Substring(index, roman.Length), roman, StringComparison.OrdinalIgnoreCase))
                {
                    matched = roman;
                    return vowel;
                }
            }

            matched = string.Empty;
            return -1;
        }

        private static int HangulFinalIndex(char ch)
        {
            return ch switch
            {
                'g' => 1,
                'k' => 1,
                'c' => 1,
                'q' => 1,
                'n' => 4,
                'd' => 7,
                't' => 7,
                'l' => 8,
                'r' => 8,
                'm' => 16,
                'b' => 17,
                'p' => 17,
                's' => 19,
                _ => 0
            };
        }

        private static bool HasConsequenceText(string text)
        {
            string value = text ?? string.Empty;
            string[] terms = { "위협", "안전", "변화", "번지", "사라", "두려", "걱정", "잠잠" };
            return terms.Any(term => value.Contains(term, StringComparison.OrdinalIgnoreCase));
        }

        private static bool HasRepeatedGenericPhrases(string text)
        {
            string value = text ?? string.Empty;
            return value.Split(new[] { "처치" }, StringSplitOptions.None).Length > 5 ||
                   value.Split(new[] { "{{target}}" }, StringSplitOptions.None).Length > 7;
        }

        private static bool HasRepetitiveStorySkeleton(string text)
        {
            string value = text ?? string.Empty;
            string[] phrases =
            {
                "말 없는 부탁",
                "열린 경고",
                "누군가 급히 남긴",
                "끊어진 발자국",
                "길목을 비우기 전에",
                "단서를 짚으며",
                "낮게 말했다",
                "흔적 사이의 간격은 점점 좁아지고",
                "다시 돌아오기 전에 먼저 찾아내야 한다는 압박",
                "위협이 가까워졌다는 증거다",
                "위협이 사라진 뒤",
                "공기가 가벼워졌다",
                "아직 완전히 안전하지 않지만",
                "오늘 밤의 공포는 한 번 꺾였다",
                "오래 참았던 숨을 내쉬었다",
                "쪽 공기가 달라졌습니다",
                "이제 사람들도 길을 다시 볼 겁니다"
            };

            int hits = phrases.Count(phrase => value.Contains(phrase, StringComparison.OrdinalIgnoreCase));
            if (hits >= 3)
                return true;

            return value.Contains("단서가 발견됐다", StringComparison.OrdinalIgnoreCase) &&
                   value.Contains("낮은 길을 따라 이어진다", StringComparison.OrdinalIgnoreCase) &&
                   value.Contains("먼저 찾아내야 한다", StringComparison.OrdinalIgnoreCase);
        }

        private static bool HasRepeatedSentenceOpenings(string text)
        {
            string value = Regex.Replace(text ?? string.Empty, @"\s+", " ").Trim();
            if (value.Length == 0)
                return false;

            return Regex.Split(value, @"[.!?。？！]+")
                .Select(NormalizeSentenceOpening)
                .Where(opening => opening.Length >= 8)
                .GroupBy(opening => opening, StringComparer.OrdinalIgnoreCase)
                .Any(group => group.Count() >= 2);
        }

        private static bool HasRepeatedSentenceOpenings(DynamicQuestStoryText story)
        {
            if (HasRepeatedSentenceOpenings(story?.OfferText) ||
                HasRepeatedSentenceOpenings(story?.ProgressText) ||
                HasRepeatedSentenceOpenings(story?.FinishText))
                return true;

            foreach (DynamicQuestNarrativeScene scene in story?.NarrativeScenes ?? Array.Empty<DynamicQuestNarrativeScene>())
            {
                if (HasRepeatedSentenceOpenings(scene.Body) ||
                    HasRepeatedSentenceOpenings(scene.JournalEntry))
                    return true;
            }

            foreach (DynamicQuestPresentationBeat beat in story?.PresentationBeats ?? Array.Empty<DynamicQuestPresentationBeat>())
            {
                if (HasRepeatedSentenceOpenings(beat.Text))
                    return true;
            }

            return false;
        }

        private static string NormalizeSentenceOpening(string sentence)
        {
            string value = Regex.Replace(sentence ?? string.Empty, @"[{}\[\]""'`“”‘’(),，,:;]+", " ");
            value = Regex.Replace(value, @"\s+", " ").Trim();
            if (value.Length < 12)
                return string.Empty;

            string[] tokens = value.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            if (tokens.Length >= 3)
                return string.Join(" ", tokens.Take(3));

            return value.Length <= 12 ? value : value.Substring(0, 12);
        }

        private static bool HasGenericScaffoldText(string text)
        {
            string value = text ?? string.Empty;
            string[] phrases =
            {
                "지역 분위기",
                "불안한 부탁",
                "흔적의 방향",
                "잠잠해진 길목",
                "심상치 않습니다",
                "작은 소문처럼 들리지만",
                "흙과 풀잎 사이",
                "문을 걸어 잠그고 있습니다",
                "이제야 숨을 쉴 수 있겠군요",
                "지역은 다시 평온"
            };

            int hits = phrases.Count(phrase => value.Contains(phrase, StringComparison.OrdinalIgnoreCase));
            return hits >= 2;
        }

        private static bool ContainsMechanicalObjectiveCopy(string text)
        {
            string value = text ?? string.Empty;
            string[] phrases =
            {
                "퀘스트 보상",
                "보상을 받으세요",
                "처치 완료",
                "처치 시",
                "마리 중",
                "마리 처치",
                "현재 {{target}}",
                "현재 {target}",
                "0마리 처치",
                "/3)",
                "/1)"
            };

            int hits = phrases.Count(phrase => value.Contains(phrase, StringComparison.OrdinalIgnoreCase));
            if (hits >= 2)
                return true;

            return value.Contains("현재", StringComparison.OrdinalIgnoreCase) &&
                   value.Contains("처치", StringComparison.OrdinalIgnoreCase) &&
                   value.Contains("마리", StringComparison.OrdinalIgnoreCase);
        }

        private static bool HasSystemSpeakerOveruse(DynamicQuestStoryText story)
        {
            IList<DynamicQuestPresentationBeat> beats = story?.PresentationBeats ?? Array.Empty<DynamicQuestPresentationBeat>();
            int validBeats = beats.Count(IsValidPresentationBeat);
            if (validBeats < 2)
                return false;

            int systemBeats = beats.Count(beat =>
                IsValidPresentationBeat(beat) &&
                string.Equals(beat.Speaker, "System", StringComparison.OrdinalIgnoreCase));
            return systemBeats == validBeats;
        }

        private static bool ContainsRealmTexture(string text, string realm)
        {
            string value = text ?? string.Empty;
            string realmValue = realm ?? string.Empty;
            string[] albionTerms = { "Camelot", "카멜롯", "수도원", "브리튼", "성벽", "교구", "기사" };
            string[] midgardTerms = { "Jordheim", "요르드헤임", "롱하우스", "룬", "스칼드", "눈밭", "협만" };
            string[] hiberniaTerms = { "Tir na Nog", "티르 나 노그", "드루이드", "성소", "고리석", "숲길", "수풀" };
            string[] genericLocalTerms = { "마을 길목", "부러진 수레바퀴", "젖은 흙", "버려진 수레", "횃불" };

            if (string.Equals(realmValue, "Albion", StringComparison.OrdinalIgnoreCase))
                return albionTerms.Any(term => value.Contains(term, StringComparison.OrdinalIgnoreCase));
            if (string.Equals(realmValue, "Midgard", StringComparison.OrdinalIgnoreCase))
                return midgardTerms.Any(term => value.Contains(term, StringComparison.OrdinalIgnoreCase));
            if (string.Equals(realmValue, "Hibernia", StringComparison.OrdinalIgnoreCase))
                return hiberniaTerms.Any(term => value.Contains(term, StringComparison.OrdinalIgnoreCase));
            if (string.IsNullOrWhiteSpace(realmValue) ||
                string.Equals(realmValue, "Unknown", StringComparison.OrdinalIgnoreCase))
                return genericLocalTerms.Any(term => value.Contains(term, StringComparison.OrdinalIgnoreCase));

            return false;
        }

        private static bool ContainsConcreteLocalTexture(string text)
        {
            string value = text ?? string.Empty;
            string[] terms =
            {
                "숲 가장자리",
                "울타리",
                "수도원",
                "성벽",
                "교구",
                "롱하우스",
                "눈밭",
                "협만",
                "고리석",
                "숲길",
                "수풀",
                "마을 길목",
                "부러진 수레바퀴",
                "젖은 흙",
                "버려진 수레",
                "횃불"
            };

            return terms.Any(term => value.Contains(term, StringComparison.OrdinalIgnoreCase));
        }

        private static bool ContainsOperationalEnglish(string text)
        {
            string value = text ?? string.Empty;
            string[] terms = { "objective", "quest", "target", "reward", "script", "database" };
            return terms.Any(term => value.Contains(term, StringComparison.OrdinalIgnoreCase));
        }

        private static bool ContainsTargetOrPlaceholder(string text, string targetName)
        {
            return text.Contains("{{target}}", StringComparison.OrdinalIgnoreCase) ||
                   (!string.IsNullOrWhiteSpace(targetName) && text.Contains(targetName, StringComparison.OrdinalIgnoreCase));
        }

        private static bool ContainsHangul(string text)
        {
            return (text ?? string.Empty).Any(ch => ch >= '\uac00' && ch <= '\ud7a3');
        }

        private static bool ContainsAwkwardKoreanParticle(string text)
        {
            string value = text ?? string.Empty;
            for (int i = 1; i < value.Length; i++)
            {
                char previous = value[i - 1];
                char current = value[i];
                if (IsAsciiLetter(previous) && (current == '와' || current == '과'))
                    return true;
                if (IsClosingQuote(previous) && i >= 2)
                {
                    if (IsAsciiLetter(value[i - 2]) && IsKoreanParticle(current))
                        return true;
                    previous = value[i - 2];
                }

                if (!IsHangulSyllable(previous))
                    continue;

                bool hasFinalConsonant = HasHangulFinalConsonant(previous);
                if ((current == '와' || current == '를') && hasFinalConsonant)
                    return true;
            }

            return false;
        }

        private static bool IsKoreanParticle(char ch)
        {
            return ch == '와' || ch == '과' ||
                   ch == '이' || ch == '가' ||
                   ch == '은' || ch == '는' ||
                   ch == '을' || ch == '를';
        }

        private static bool IsAsciiLetter(char ch)
        {
            return (ch >= 'A' && ch <= 'Z') ||
                   (ch >= 'a' && ch <= 'z');
        }

        private static bool IsClosingQuote(char ch)
        {
            return ch == '\'' || ch == '"' || ch == '’' || ch == '”';
        }

        private static bool IsHangulSyllable(char ch)
        {
            return ch >= '\uac00' && ch <= '\ud7a3';
        }

        private static bool HasHangulFinalConsonant(char ch)
        {
            return IsHangulSyllable(ch) && (ch - '\uac00') % 28 != 0;
        }

        private static bool ContainsKillIntent(string text)
        {
            string value = text ?? string.Empty;
            string[] terms = { "처치", "쓰러", "제압", "소탕", "퇴치", "사냥", "물리", "위협" };
            return terms.Any(term => value.Contains(term, StringComparison.OrdinalIgnoreCase));
        }

        private static bool ContainsForbiddenOperationalText(string text)
        {
            string value = text ?? string.Empty;
            string[] terms = { "reward", "gold", "realm_points", "command", "spawn", "delete", "database", "sql", "script", "api key" };
            return terms.Any(term => value.Contains(term, StringComparison.OrdinalIgnoreCase)) ||
                   ContainsSystemExpressionLeak(value);
        }

        private static bool ContainsSystemExpressionLeak(string text)
        {
            string value = StripAllowedDynamicPlaceholders(text ?? string.Empty);
            if (string.IsNullOrWhiteSpace(value))
                return false;

            string[] terms =
            {
                "nearby settlement",
                "local area",
                "region_id",
                "region id",
                "template_id",
                "template id",
                "start_npc",
                "start npc",
                "target_name",
                "target name",
                "min_level",
                "max_level",
                "quest id",
                "npc id",
                "mob id"
            };

            return terms.Any(term => value.Contains(term, StringComparison.OrdinalIgnoreCase)) ||
                   Regex.IsMatch(value, @"\b(?:region|zone)\s*#?\s*\d+\b", RegexOptions.IgnoreCase);
        }

        private static string StripAllowedDynamicPlaceholders(string text)
        {
            string value = text ?? string.Empty;
            string[] placeholders = { "{{target}}", "{{start_npc}}", "{{realm}}", "{{count}}" };
            foreach (string placeholder in placeholders)
                value = value.Replace(placeholder, string.Empty, StringComparison.OrdinalIgnoreCase);
            return value;
        }

        private static string PlaceholderizeTarget(string text, string targetName)
        {
            string value = (text ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(value) || string.IsNullOrWhiteSpace(targetName))
                return value;

            return value.Replace(targetName, "{{target}}", StringComparison.OrdinalIgnoreCase);
        }

        private static string BuildSystemPrompt()
        {
            return "You generate MMORPG quest story text for a Korean game server. " +
                   "Return exactly one JSON object with keys title, offer, progress, finish, target, count, min_level, max_level, narrative_scenes, presentation_beats. " +
                   "title, offer, progress, and finish must be natural Korean Hangul text. " +
                   "narrative_scenes is required and must include at least three concise immersive Korean scenes across intro, discovery, return, or completion. " +
                   "Each narrative scene uses node_id, scene_type, title, body, journal_entry, mood, reveal_policy. " +
                   "presentation_beats is required and must include at least four staged moments using node_id, trigger, speaker, text, emotion, emote, cinematic_action, scene_role, formation, actor_count, and delay_ms. Use delay_ms 0 when there is no delay. " +
                   "Include at least three distinct cinematic_action values, at least three distinct scene_role values, at least two formations, one delayed beat, one actor_count of 4 or more, and one combat or movement action scene. " +
                   "Allowed cinematic_action values are witness_point, scout_retreat, ambush_reveal, defender_intercept, ritual_interrupt, threat_standoff, combat_stance, hold_ground, guard_advance, fallback_guard. " +
                   "Allowed formation values are escort, patrol, ambush, line, escape, ring. Keep actor_count between 1 and 100 and delay_ms between 0 and 6000. " +
                   "Do not use generic scaffold titles or phrases such as '지역 분위기', '불안한 부탁', '흔적의 방향', '잠잠해진 길목', or '이제야 숨을 쉴 수 있겠군요'. " +
                   "Do not reuse repetitive skeleton phrases such as '말 없는 부탁', '열린 경고', '누군가 급히 남긴', '끊어진 발자국', '흔적 사이의 간격은 점점 좁아지고', '오늘 밤의 공포는 한 번 꺾였다', or '이제 사람들도 길을 다시 볼 겁니다'. " +
                   "Write reusable dynamic templates: use {{start_npc}} for the bound quest giver and {{realm}} for the bound realm instead of hard-coding NPC names or realm names in story text. " +
                   "Use at least two concrete local anchors from the NPC role, monster ecology, landmark, weather, injury, witness, or consequence; never expose raw fields such as region_id, numeric region names, or nearby settlement. " +
                   DynamicQuestCinematicCatalog.DescribeCatalogForPrompt() + " " +
                   "Every narrative scene and presentation beat should imply a fitting prop category when possible: use clue for investigation or tracks, record for written lore, relic for ritual or realm symbols, flame for danger or omens, weapon for combat aftermath, and structure for gates, portals, keeps, or relic pads. " +
                   "Do not invent model numbers; describe the scene so the runtime can select a matching catalog category. " +
                   "Write presentation beats as scene directions that the runtime can stage with temporary NPC actors walking, guarding, falling back, pointing, intercepting, interrupting rituals, revealing ambushes, or holding ground; do not rely on emotes alone. " +
                   "For thriller or assassination style quests, stage the existing nodes as a sequence of contract, witness clue, ambush reveal, escape-route interception, fleeing witness, confrontation, and debrief beats; keep them server-checkable and never require a custom client camera. " +
                   "For large battle-tableau scenes, describe the scale in words instead of raw actor counts; the runtime clamps temporary cinematic actors to the configured safe limit and never above 100 per action. " +
                   "Use {{target}} as the monster placeholder inside offer, progress, and finish; do not translate the DB target name inside the target field. " +
                   "target, count, min_level, and max_level must exactly match the provided values. " +
                   "Do not output raw emote ids, packet names, opcodes, arbitrary animation numbers, graph, rewards, commands, markdown, comments, or extra keys. " +
                   "The objective is kill/combat, so every narrative field must clearly describe defeating or subduing {{target}}. " +
                   "Example JSON shape: {\"title\":\"{{start_npc}}의 젖은 길목 경고\",\"offer\":\"{{start_npc}}은 {{realm}} 길목의 젖은 흙 위에 남은 {{target}} 흔적을 가리키며 마을로 번지기 전에 제압해 달라고 낮게 말했다.\",\"progress\":\"{{realm}} 길목의 발자국을 따라가 {{target}} 위협을 끊어내야 한다.\",\"finish\":\"{{target}} 위협이 사라지자 {{start_npc}}은 찢긴 울타리를 다시 묶고 {{realm}} 길목의 횃불을 세웠다.\",\"target\":\"black wolf pup\",\"count\":1,\"min_level\":1,\"max_level\":5,\"narrative_scenes\":[{\"node_id\":\"talk\",\"scene_type\":\"Intro\",\"title\":\"찢긴 울타리\",\"body\":\"{{start_npc}}은 {{realm}} 길목의 젖은 흙 위에 남은 {{target}} 발자국을 가리켰다. 부러진 울타리와 꺼진 횃불은 위협이 밤새 가까워졌음을 보여 주었다.\",\"journal_entry\":\"{{start_npc}}에게서 {{realm}} 길목의 {{target}} 흔적을 조사해 달라는 부탁을 받았다.\",\"mood\":\"ominous\",\"reveal_policy\":\"FirstSeenOnly\"},{\"node_id\":\"explore\",\"scene_type\":\"Discovery\",\"title\":\"젖은 발자국\",\"body\":\"발자국은 낮은 덤불과 버려진 수레바퀴 사이로 이어졌다. {{target}}을 지금 막지 못하면 {{realm}}의 밤길은 더 오래 비게 될 것이다.\",\"journal_entry\":\"{{target}} 흔적은 마을 가까이 이어졌다.\",\"mood\":\"urgent\",\"reveal_policy\":\"EveryInteraction\"},{\"node_id\":\"return\",\"scene_type\":\"Return\",\"title\":\"숨 돌린 길목\",\"body\":\"{{target}} 위협이 사라지자 길목의 횃불이 다시 곧게 섰다. {{start_npc}}에게 돌아가면 {{realm}} 사람들이 문을 덜 두드리게 될 것이다.\",\"journal_entry\":\"{{start_npc}}에게 {{target}} 처치 소식을 전해야 한다.\",\"mood\":\"relieved\",\"reveal_policy\":\"FirstSeenOnly\"}],\"presentation_beats\":[{\"node_id\":\"talk\",\"trigger\":\"OnNpcInteract\",\"speaker\":\"StartNpc\",\"text\":\"목소리를 낮추세요. 저 발자국은 방금 생긴 겁니다.\",\"emotion\":\"fear\",\"emote\":\"Shiver\",\"cinematic_action\":\"witness_point\",\"scene_role\":\"contract_witness\",\"formation\":\"escort\",\"actor_count\":3,\"delay_ms\":0},{\"node_id\":\"explore\",\"trigger\":\"OnExplore\",\"speaker\":\"System\",\"text\":\"망보던 자가 뒤로 물러나고 길가의 표식이 드러납니다.\",\"emotion\":\"suspicion\",\"emote\":\"Point\",\"cinematic_action\":\"scout_retreat\",\"scene_role\":\"lookout_escape\",\"formation\":\"escape\",\"actor_count\":4,\"delay_ms\":700},{\"node_id\":\"kill\",\"trigger\":\"OnKill\",\"speaker\":\"System\",\"text\":\"{{target}}이 쓰러지자 매복 병력이 모습을 드러내고 탈출로를 막습니다.\",\"emotion\":\"urgency\",\"emote\":\"Point\",\"cinematic_action\":\"ambush_reveal\",\"scene_role\":\"ambush_wave\",\"formation\":\"ambush\",\"actor_count\":8,\"delay_ms\":0},{\"node_id\":\"return\",\"trigger\":\"OnComplete\",\"speaker\":\"StartNpc\",\"text\":\"이제 길목의 아이들이 다시 불빛을 따라 걸을 수 있겠군요.\",\"emotion\":\"gratitude\",\"emote\":\"Bow\",\"cinematic_action\":\"fallback_guard\",\"scene_role\":\"watch_restored\",\"formation\":\"line\",\"actor_count\":4,\"delay_ms\":1000}]}";
        }

        private static string BuildUserPrompt(DynamicQuestStoryRequest request)
        {
            object payload = new
            {
                template_id = request.TemplateId,
                realm = request.Realm,
                start_npc = request.StartNpcName,
                region_id = request.RegionId,
                target = request.TargetName,
                count = request.Count,
                min_level = request.MinLevel,
                max_level = request.MaxLevel,
                story_seed = SanitizeStorySeed(request.StorySeed),
                cinematic_catalog = DynamicQuestCinematicCatalog.DescribeCatalogForPrompt(),
                local_anchor_requirement = "Use at least two concrete local anchors; if start_npc is present, mention that NPC by name in narrative or journal text. If start_npc contains English letters, include that exact original value at least once."
            };
            return "Create one deterministic story-only dynamic quest template. " +
                   JsonSerializer.Serialize(payload, StoryJsonOptions);
        }

        private static string SanitizeStorySeed(string seed)
        {
            string value = (seed ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(value) || LooksLikeDefaultScaffoldSeed(value))
                return "현재 세계 바인딩된 NPC, 렐름, 지역, 목표 생태를 기준으로 새 사건을 구성하십시오.";

            return value;
        }

        private static bool LooksLikeDefaultScaffoldSeed(string seed)
        {
            string value = seed ?? string.Empty;
            string[] phrases =
            {
                "지역 분위기",
                "짧은 처치 의뢰",
                "불안한 부탁",
                "흔적의 방향",
                "잠잠해진 길목"
            };

            return phrases.Any(phrase => value.Contains(phrase, StringComparison.OrdinalIgnoreCase));
        }

        private static object BuildOpenAiRequest(string model, DynamicQuestStoryRequest request)
        {
            return BuildOpenAiRequest(model, request, OpenAiStoryRequestMode.StrictSchema);
        }

        private static object BuildOpenAiRequest(string model, DynamicQuestStoryRequest request, bool includeJsonSchema)
        {
            return BuildOpenAiRequest(
                model,
                request,
                includeJsonSchema ? OpenAiStoryRequestMode.StrictSchema : OpenAiStoryRequestMode.PlainJson);
        }

        private static object BuildOpenAiRequest(string model, DynamicQuestStoryRequest request, OpenAiStoryRequestMode mode)
        {
            object[] messages = mode == OpenAiStoryRequestMode.CompactJson
                ? new object[]
                {
                    new { role = "system", content = BuildCompactSystemPrompt() },
                    new { role = "user", content = BuildCompactUserPrompt(request) }
                }
                : new object[]
            {
                new { role = "system", content = BuildSystemPrompt() },
                new { role = "user", content = BuildUserPrompt(request) }
            };

            if (mode == OpenAiStoryRequestMode.CompactJson)
            {
                return new
                {
                    model,
                    messages,
                    temperature = 0.2,
                    max_tokens = 256
                };
            }

            if (mode == OpenAiStoryRequestMode.PlainJson)
            {
                return new
                {
                    model,
                    messages,
                    temperature = 0.2,
                    max_tokens = 2048
                };
            }

            return new
            {
                model,
                messages,
                temperature = 0.2,
                max_tokens = 2048,
                response_format = new
                {
                    type = "json_schema",
                    json_schema = new
                    {
                        name = "dynamic_quest_story",
                        strict = true,
                        schema = StorySchema()
                    }
                }
            };
        }

        private static object BuildOpenAiResponsesRequest(string model, DynamicQuestStoryRequest request)
        {
            return new
            {
                model,
                input = new object[]
                {
                    new { role = "system", content = BuildSystemPrompt() },
                    new { role = "user", content = BuildUserPrompt(request) }
                },
                max_output_tokens = 2048,
                text = new
                {
                    format = new
                    {
                        type = "json_schema",
                        name = "dynamic_quest_story",
                        strict = true,
                        schema = StorySchema()
                    }
                }
            };
        }

        private static string BuildCompactSystemPrompt()
        {
            return "Return only one JSON object for a Korean MMORPG kill quest. " +
                   "Keys: title, offer, progress, finish, target, count, min_level, max_level. " +
                   "Korean text must mention the realm or local anchor and use {{target}} in offer/progress/finish. " +
                   "Avoid repeated scaffold phrases like '불안한 부탁', '열린 경고', '끊어진 발자국', or '이제 사람들도 길을 다시 볼 겁니다'. " +
                   "target/count/min_level/max_level must exactly match input. No markdown, no extra keys.";
        }

        private static string BuildCompactUserPrompt(DynamicQuestStoryRequest request)
        {
            object payload = new
            {
                realm = request?.Realm ?? string.Empty,
                start_npc = request?.StartNpcName ?? string.Empty,
                local_anchor = RealmLandmark(request?.Realm),
                region_id = request?.RegionId ?? 0,
                target = request?.TargetName ?? string.Empty,
                count = Math.Max(1, request?.Count ?? 1),
                min_level = Math.Clamp(request?.MinLevel ?? 1, 1, 50),
                max_level = Math.Clamp(Math.Max(request?.MaxLevel ?? 50, request?.MinLevel ?? 1), 1, 50)
            };
            return JsonSerializer.Serialize(payload, StoryJsonOptions);
        }

        private static string BuildGeminiRequestJson(DynamicQuestStoryRequest request)
        {
            return JsonSerializer.Serialize(BuildGeminiRequest(request));
        }

        private static object BuildGeminiRequest(DynamicQuestStoryRequest request)
        {
            string text = BuildSystemPrompt() + "\n\n" + BuildUserPrompt(request);
            return new
            {
                contents = new[]
                {
                    new
                    {
                        role = "user",
                        parts = new[] { new { text } }
                    }
                },
                generationConfig = new
                {
                    temperature = 0.2,
                    maxOutputTokens = 2048,
                    responseMimeType = "application/json"
                }
            };
        }

        private static object StorySchema()
        {
            return new
            {
                type = "object",
                additionalProperties = false,
                properties = new Dictionary<string, object>
                {
                    ["title"] = new { type = "string" },
                    ["offer"] = new { type = "string" },
                    ["progress"] = new { type = "string" },
                    ["finish"] = new { type = "string" },
                    ["target"] = new { type = "string" },
                    ["count"] = new { type = "integer" },
                    ["min_level"] = new { type = "integer" },
                    ["max_level"] = new { type = "integer" },
                    ["narrative_scenes"] = new
                    {
                        type = "array",
                        minItems = 3,
                        items = new
                        {
                            type = "object",
                            additionalProperties = false,
                            properties = new Dictionary<string, object>
                            {
                                ["node_id"] = new { type = "string", @enum = AllowedNodeIds.OrderBy(item => item, StringComparer.Ordinal).ToArray() },
                                ["scene_type"] = new { type = "string", @enum = AllowedSceneTypes.OrderBy(item => item, StringComparer.Ordinal).ToArray() },
                                ["title"] = new { type = "string" },
                                ["body"] = new { type = "string" },
                                ["journal_entry"] = new { type = "string" },
                                ["mood"] = new { type = "string", @enum = AllowedMoods.OrderBy(item => item, StringComparer.Ordinal).ToArray() },
                                ["reveal_policy"] = new { type = "string", @enum = AllowedRevealPolicies.OrderBy(item => item, StringComparer.Ordinal).ToArray() }
                            },
                            required = new[] { "node_id", "scene_type", "title", "body", "journal_entry", "mood", "reveal_policy" }
                        }
                    },
                    ["presentation_beats"] = new
                    {
                        type = "array",
                        minItems = 4,
                        items = new
                        {
                            type = "object",
                            additionalProperties = false,
                            properties = new Dictionary<string, object>
                            {
                                ["node_id"] = new { type = "string", @enum = AllowedNodeIds.OrderBy(item => item, StringComparer.Ordinal).ToArray() },
                                ["trigger"] = new { type = "string", @enum = AllowedPresentationTriggers.OrderBy(item => item, StringComparer.Ordinal).ToArray() },
                                ["speaker"] = new { type = "string", @enum = AllowedSpeakers.OrderBy(item => item, StringComparer.Ordinal).ToArray() },
                                ["text"] = new { type = "string" },
                                ["emotion"] = new { type = "string", @enum = AllowedEmotions.OrderBy(item => item, StringComparer.Ordinal).ToArray() },
                                ["emote"] = new { type = "string", @enum = AllowedEmotes.OrderBy(item => item, StringComparer.Ordinal).ToArray() },
                                ["cinematic_action"] = new { type = "string", @enum = AllowedCinematicActions.OrderBy(item => item, StringComparer.Ordinal).ToArray() },
                                ["scene_role"] = new { type = "string" },
                                ["formation"] = new { type = "string", @enum = AllowedCinematicFormations.OrderBy(item => item, StringComparer.Ordinal).ToArray() },
                                ["actor_count"] = new { type = "integer", minimum = 1, maximum = 100 },
                                ["delay_ms"] = new { type = "integer", minimum = 0, maximum = 6000 }
                            },
                            required = new[] { "node_id", "trigger", "speaker", "text", "emotion", "emote", "cinematic_action", "scene_role", "formation", "actor_count", "delay_ms" }
                        }
                    }
                },
                required = new[] { "title", "offer", "progress", "finish", "target", "count", "min_level", "max_level", "narrative_scenes", "presentation_beats" }
            };
        }

        private static string NormalizeJsonContent(string raw)
        {
            string value = (raw ?? string.Empty).Trim();
            if (value.StartsWith("```", StringComparison.Ordinal))
            {
                value = value.Trim('`').Trim();
                if (value.StartsWith("json", StringComparison.OrdinalIgnoreCase))
                    value = value.Substring(4).Trim();
            }

            int first = value.IndexOf('{');
            int last = value.LastIndexOf('}');
            return first >= 0 && last >= first ? value.Substring(first, last - first + 1) : value;
        }

        private static string ExtractOpenAiContent(string body)
        {
            using JsonDocument document = JsonDocument.Parse(body);
            return document.RootElement.GetProperty("choices")[0]
                .GetProperty("message")
                .GetProperty("content")
                .GetString() ?? string.Empty;
        }

        private static string ExtractOpenAiResponsesContent(string body)
        {
            using JsonDocument document = JsonDocument.Parse(body);
            JsonElement root = document.RootElement;
            if (root.TryGetProperty("output_text", out JsonElement outputText) &&
                outputText.ValueKind == JsonValueKind.String)
                return outputText.GetString() ?? string.Empty;

            if (!root.TryGetProperty("output", out JsonElement output) ||
                output.ValueKind != JsonValueKind.Array)
                return string.Empty;

            StringBuilder builder = new();
            foreach (JsonElement item in output.EnumerateArray())
            {
                if (!item.TryGetProperty("content", out JsonElement content) ||
                    content.ValueKind != JsonValueKind.Array)
                    continue;

                foreach (JsonElement part in content.EnumerateArray())
                {
                    if (part.TryGetProperty("text", out JsonElement text) &&
                        text.ValueKind == JsonValueKind.String)
                        builder.Append(text.GetString());
                }
            }

            return builder.ToString();
        }

        private static int EstimateTokenSpend(string requestJson, int maxOutputTokens)
        {
            int inputEstimate = Math.Max(1, ((requestJson ?? string.Empty).Length + 3) / 4);
            return Math.Max(1, inputEstimate + Math.Max(0, maxOutputTokens));
        }

        private static int ExtractOpenAiResponsesUsageTokens(string body)
        {
            try
            {
                using JsonDocument document = JsonDocument.Parse(body);
                JsonElement root = document.RootElement;
                if (!root.TryGetProperty("usage", out JsonElement usage) ||
                    usage.ValueKind != JsonValueKind.Object)
                    return 0;

                int total = ReadInt(usage, "total_tokens");
                if (total > 0)
                    return total;

                return ReadInt(usage, "input_tokens") + ReadInt(usage, "output_tokens");
            }
            catch
            {
                return 0;
            }
        }

        private static int ExtractGeminiUsageTokens(string body)
        {
            try
            {
                using JsonDocument document = JsonDocument.Parse(body);
                JsonElement root = document.RootElement;
                if (!root.TryGetProperty("usageMetadata", out JsonElement usage) ||
                    usage.ValueKind != JsonValueKind.Object)
                    return 0;

                int total = ReadInt(usage, "totalTokenCount");
                if (total > 0)
                    return total;

                return ReadInt(usage, "promptTokenCount") + ReadInt(usage, "candidatesTokenCount");
            }
            catch
            {
                return 0;
            }
        }

        private static int ReadInt(JsonElement element, string propertyName)
        {
            if (!element.TryGetProperty(propertyName, out JsonElement value))
                return 0;

            if (value.ValueKind == JsonValueKind.Number && value.TryGetInt32(out int number))
                return Math.Max(0, number);

            if (value.ValueKind == JsonValueKind.String &&
                int.TryParse(value.GetString(), out number))
                return Math.Max(0, number);

            return 0;
        }

        private static string ExtractGeminiContent(string body)
        {
            using JsonDocument document = JsonDocument.Parse(body);
            JsonElement parts = document.RootElement
                .GetProperty("candidates")[0]
                .GetProperty("content")
                .GetProperty("parts");
            return parts[0].GetProperty("text").GetString() ?? string.Empty;
        }

        private static string GetString(JsonElement root, string field, int maxLength)
        {
            if (root.ValueKind != JsonValueKind.Object ||
                !root.TryGetProperty(field, out JsonElement value) ||
                value.ValueKind != JsonValueKind.String)
                return string.Empty;

            string text = value.GetString()?.Trim() ?? string.Empty;
            return text.Length <= maxLength ? text : text.Substring(0, maxLength);
        }

        private static string GetStringAny(JsonElement root, int maxLength, params string[] fields)
        {
            foreach (string field in fields)
            {
                string value = GetString(root, field, maxLength);
                if (!string.IsNullOrWhiteSpace(value))
                    return value;
            }

            return string.Empty;
        }

        private static int GetInt(JsonElement root, string field, int fallback)
        {
            if (root.ValueKind != JsonValueKind.Object ||
                !root.TryGetProperty(field, out JsonElement value))
                return fallback;

            if (value.ValueKind == JsonValueKind.Number && value.TryGetInt32(out int parsed))
                return parsed;
            if (value.ValueKind == JsonValueKind.String && int.TryParse(value.GetString(), out parsed))
                return parsed;
            return fallback;
        }

        private static IList<DynamicQuestNarrativeScene> ParseNarrativeScenes(JsonElement root)
        {
            JsonElement array = GetArrayAny(root, "narrative_scenes", "narrativeScenes");
            if (array.ValueKind != JsonValueKind.Array)
                return Array.Empty<DynamicQuestNarrativeScene>();

            List<DynamicQuestNarrativeScene> scenes = new();
            foreach (JsonElement item in array.EnumerateArray())
            {
                if (item.ValueKind != JsonValueKind.Object)
                    continue;

                scenes.Add(new DynamicQuestNarrativeScene
                {
                    NodeId = GetStringAny(item, 40, "node_id", "nodeId"),
                    SceneType = GetStringAny(item, 40, "scene_type", "sceneType"),
                    Title = GetString(item, "title", 120),
                    Body = GetString(item, "body", 1200),
                    JournalEntry = GetStringAny(item, 400, "journal_entry", "journalEntry"),
                    Mood = GetString(item, "mood", 40),
                    RevealPolicy = GetStringAny(item, 40, "reveal_policy", "revealPolicy")
                });
            }

            return scenes;
        }

        private static IList<DynamicQuestPresentationBeat> ParsePresentationBeats(JsonElement root)
        {
            JsonElement array = GetArrayAny(root, "presentation_beats", "presentationBeats");
            if (array.ValueKind != JsonValueKind.Array)
                return Array.Empty<DynamicQuestPresentationBeat>();

            List<DynamicQuestPresentationBeat> beats = new();
            foreach (JsonElement item in array.EnumerateArray())
            {
                if (item.ValueKind != JsonValueKind.Object)
                    continue;

                beats.Add(new DynamicQuestPresentationBeat
                {
                    NodeId = GetStringAny(item, 40, "node_id", "nodeId"),
                    Trigger = GetString(item, "trigger", 40),
                    Speaker = GetString(item, "speaker", 40),
                    Text = GetString(item, "text", 240),
                    Emotion = GetString(item, "emotion", 40),
                    Emote = GetString(item, "emote", 40),
                    CinematicAction = GetStringAny(item, 40, "cinematic_action", "cinematicAction"),
                    SceneRole = GetStringAny(item, 40, "scene_role", "sceneRole"),
                    Formation = GetString(item, "formation", 40),
                    ActorCount = GetIntAny(item, 0, "actor_count", "actorCount"),
                    DelayMs = GetIntAny(item, 0, "delay_ms", "delayMs")
                });
            }

            return beats;
        }

        private static int GetIntAny(JsonElement root, int fallback, params string[] fields)
        {
            foreach (string field in fields)
            {
                int value = GetInt(root, field, int.MinValue);
                if (value != int.MinValue)
                    return value;
            }

            return fallback;
        }

        private static JsonElement GetArrayAny(JsonElement root, params string[] fields)
        {
            if (root.ValueKind != JsonValueKind.Object)
                return default;

            foreach (string field in fields)
            {
                if (root.TryGetProperty(field, out JsonElement value) &&
                    value.ValueKind == JsonValueKind.Array)
                    return value;
            }

            return default;
        }

        private static string FirstNonEmpty(string first, string second)
        {
            return !string.IsNullOrWhiteSpace(first) ? first.Trim() : (second ?? string.Empty).Trim();
        }

        private static void AddTag(List<string> tags, string tag)
        {
            if (!tags.Contains(tag, StringComparer.OrdinalIgnoreCase))
                tags.Add(tag);
        }

        private static IList<string> SplitCsv(string value)
        {
            return (value ?? string.Empty)
                .Split(new[] { ',', ';', '|' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(item => item.Trim())
                .Where(item => item.Length > 0)
                .ToList();
        }

        private sealed class OpenAiCompatibleDynamicQuestStoryProvider : IDynamicQuestStoryProvider
        {
            private readonly string m_baseUrl;
            private readonly string m_model;
            private readonly int m_timeoutSeconds;

            public OpenAiCompatibleDynamicQuestStoryProvider(string name, string baseUrl, string model, int timeoutSeconds)
            {
                Name = name ?? string.Empty;
                m_baseUrl = baseUrl ?? string.Empty;
                m_model = model ?? string.Empty;
                m_timeoutSeconds = timeoutSeconds <= 0 ? 30 : timeoutSeconds;
            }

            public string Name { get; }
            public string ModelName => m_model ?? string.Empty;

            public DynamicQuestStoryGenerationResult TryGenerate(DynamicQuestStoryRequest request)
            {
                if (string.IsNullOrWhiteSpace(m_baseUrl) || string.IsNullOrWhiteSpace(m_model))
                    return DynamicQuestStoryGenerationResult.Fail("provider_not_configured");

                try
                {
                    using HttpClient client = new()
                    {
                        BaseAddress = new Uri(m_baseUrl.TrimEnd('/') + "/"),
                        Timeout = TimeSpan.FromSeconds(m_timeoutSeconds)
                    };
                    DynamicQuestStoryGenerationResult strictResult = TryGenerate(client, request, includeJsonSchema: true);
                    if (strictResult.Success || !string.Equals(strictResult.Error, "http_400", StringComparison.OrdinalIgnoreCase))
                        return strictResult;

                    DynamicQuestStoryGenerationResult plainResult = TryGenerate(client, request, OpenAiStoryRequestMode.PlainJson);
                    if (plainResult.Success || !string.Equals(plainResult.Error, "http_400", StringComparison.OrdinalIgnoreCase))
                        return plainResult;

                    return TryGenerate(client, request, OpenAiStoryRequestMode.CompactJson);
                }
                catch (Exception e)
                {
                    return DynamicQuestStoryGenerationResult.Fail(e.GetType().Name);
                }
            }

            private DynamicQuestStoryGenerationResult TryGenerate(
                HttpClient client,
                DynamicQuestStoryRequest request,
                bool includeJsonSchema)
            {
                return TryGenerate(
                    client,
                    request,
                    includeJsonSchema ? OpenAiStoryRequestMode.StrictSchema : OpenAiStoryRequestMode.PlainJson);
            }

            private DynamicQuestStoryGenerationResult TryGenerate(
                HttpClient client,
                DynamicQuestStoryRequest request,
                OpenAiStoryRequestMode mode)
            {
                string requestJson = JsonSerializer.Serialize(BuildOpenAiRequest(m_model, request, mode), StoryJsonOptions);
                using StringContent content = new(requestJson, Encoding.UTF8, "application/json");
                using HttpResponseMessage response = client.PostAsync("v1/chat/completions", content).GetAwaiter().GetResult();
                string body = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                if (!response.IsSuccessStatusCode)
                    return DynamicQuestStoryGenerationResult.Fail($"http_{(int)response.StatusCode}");

                DynamicQuestStoryText story = ParseStoryJson(ExtractOpenAiContent(body), request);
                return DynamicQuestStoryGenerationResult.Ok(story, Name);
            }
        }

        private sealed class OpenAiDynamicQuestStoryProvider : IDynamicQuestStoryProvider
        {
            private readonly string m_baseUrl;
            private readonly string m_model;
            private readonly DynamicQuestGeminiQuota m_quota;
            private readonly DynamicQuestTokenBudget m_tokenBudget;
            private readonly int m_timeoutSeconds;

            public OpenAiDynamicQuestStoryProvider(
                string name,
                string baseUrl,
                string model,
                DynamicQuestGeminiQuota quota,
                int timeoutSeconds)
                : this(name, baseUrl, model, quota, null, timeoutSeconds)
            {
            }

            public OpenAiDynamicQuestStoryProvider(
                string name,
                string baseUrl,
                string model,
                DynamicQuestGeminiQuota quota,
                DynamicQuestTokenBudget tokenBudget,
                int timeoutSeconds)
            {
                Name = name ?? string.Empty;
                m_baseUrl = string.IsNullOrWhiteSpace(baseUrl) ? "https://api.openai.com" : baseUrl.Trim();
                m_model = string.IsNullOrWhiteSpace(model) ? "gpt-5.4" : model.Trim();
                m_quota = quota ?? new DynamicQuestGeminiQuota(0, 0);
                m_tokenBudget = tokenBudget;
                m_timeoutSeconds = timeoutSeconds <= 0 ? 60 : Math.Max(timeoutSeconds, 60);
            }

            public string Name { get; }
            public string ModelName => m_model ?? string.Empty;

            public DynamicQuestStoryGenerationResult TryGenerate(DynamicQuestStoryRequest request)
            {
                string apiKey = Environment.GetEnvironmentVariable("OPENAI_API_KEY") ?? string.Empty;
                if (string.IsNullOrWhiteSpace(apiKey))
                    return DynamicQuestStoryGenerationResult.Fail("openai_api_key_missing");

                string requestJson = JsonSerializer.Serialize(BuildOpenAiResponsesRequest(m_model, request), StoryJsonOptions);
                DynamicQuestTokenReservation tokenReservation = null;
                if (m_tokenBudget != null &&
                    !m_tokenBudget.TryReserve(EstimateTokenSpend(requestJson, 2048), out tokenReservation, out string tokenError))
                    return DynamicQuestStoryGenerationResult.Fail(tokenError);

                if (!m_quota.TryReserve())
                {
                    m_tokenBudget?.Cancel(tokenReservation);
                    return DynamicQuestStoryGenerationResult.Fail("openai_quota_exhausted");
                }

                try
                {
                    using HttpClient client = new()
                    {
                        BaseAddress = new Uri(m_baseUrl.TrimEnd('/') + "/"),
                        Timeout = TimeSpan.FromSeconds(m_timeoutSeconds)
                    };
                    client.DefaultRequestHeaders.Authorization =
                        new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", apiKey.Trim());

                    using StringContent content = new(requestJson, Encoding.UTF8, "application/json");
                    using HttpResponseMessage response = client.PostAsync("v1/responses", content).GetAwaiter().GetResult();
                    string body = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                    if (!response.IsSuccessStatusCode)
                    {
                        if ((int)response.StatusCode == 429)
                            m_quota.MarkThrottled(TimeSpan.FromMinutes(1));
                        m_tokenBudget?.Cancel(tokenReservation);
                        return DynamicQuestStoryGenerationResult.Fail($"http_{(int)response.StatusCode}");
                    }

                    DynamicQuestStoryText story = ParseStoryJson(ExtractOpenAiResponsesContent(body), request);
                    m_tokenBudget?.Finalize(tokenReservation, ExtractOpenAiResponsesUsageTokens(body));
                    return DynamicQuestStoryGenerationResult.Ok(story, Name, m_model);
                }
                catch (Exception e)
                {
                    m_tokenBudget?.Cancel(tokenReservation);
                    return DynamicQuestStoryGenerationResult.Fail(e.GetType().Name);
                }
            }
        }

        private sealed class GeminiDynamicQuestStoryProvider : IDynamicQuestStoryProvider
        {
            private readonly string m_model;
            private readonly DynamicQuestGeminiQuota m_quota;
            private readonly DynamicQuestTokenBudget m_tokenBudget;

            public GeminiDynamicQuestStoryProvider(string name, string model, DynamicQuestGeminiQuota quota)
                : this(name, model, quota, null)
            {
            }

            public GeminiDynamicQuestStoryProvider(
                string name,
                string model,
                DynamicQuestGeminiQuota quota,
                DynamicQuestTokenBudget tokenBudget)
            {
                Name = name ?? string.Empty;
                m_model = string.IsNullOrWhiteSpace(model) ? "gemini-3.5-flash" : model.Trim();
                m_quota = quota ?? new DynamicQuestGeminiQuota(0, 0);
                m_tokenBudget = tokenBudget;
            }

            public string Name { get; }
            public string ModelName => m_model ?? string.Empty;

            public DynamicQuestStoryGenerationResult TryGenerate(DynamicQuestStoryRequest request)
            {
                string apiKey = Environment.GetEnvironmentVariable("GEMINI_API_KEY") ?? string.Empty;
                if (string.IsNullOrWhiteSpace(apiKey))
                    return DynamicQuestStoryGenerationResult.Fail("gemini_api_key_missing");

                string requestJson = BuildGeminiRequestJson(request);
                DynamicQuestTokenReservation tokenReservation = null;
                if (m_tokenBudget != null &&
                    !m_tokenBudget.TryReserve(EstimateTokenSpend(requestJson, 2048), out tokenReservation, out string tokenError))
                    return DynamicQuestStoryGenerationResult.Fail(tokenError);

                if (!m_quota.TryReserve())
                {
                    m_tokenBudget?.Cancel(tokenReservation);
                    return DynamicQuestStoryGenerationResult.Fail("gemini_quota_exhausted");
                }

                try
                {
                    string url = $"https://generativelanguage.googleapis.com/v1beta/models/{Uri.EscapeDataString(m_model)}:generateContent?key={Uri.EscapeDataString(apiKey)}";
                    using HttpClient client = new() { Timeout = TimeSpan.FromSeconds(45) };
                    using StringContent content = new(requestJson, Encoding.UTF8, "application/json");
                    using HttpResponseMessage response = client.PostAsync(url, content).GetAwaiter().GetResult();
                    string body = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                    if (!response.IsSuccessStatusCode)
                    {
                        if ((int)response.StatusCode == 429)
                            m_quota.MarkThrottled(TimeSpan.FromMinutes(1));
                        m_tokenBudget?.Cancel(tokenReservation);
                        return DynamicQuestStoryGenerationResult.Fail($"http_{(int)response.StatusCode}");
                    }

                    DynamicQuestStoryText story = ParseStoryJson(ExtractGeminiContent(body), request);
                    m_tokenBudget?.Finalize(tokenReservation, ExtractGeminiUsageTokens(body));
                    return DynamicQuestStoryGenerationResult.Ok(story, Name);
                }
                catch (Exception e)
                {
                    m_tokenBudget?.Cancel(tokenReservation);
                    return DynamicQuestStoryGenerationResult.Fail(e.GetType().Name);
                }
            }
        }
    }

    internal static class DynamicQuestGeminiQuotaClock
    {
        private static readonly Lazy<TimeZoneInfo> PacificTimeZone = new(FindPacificTimeZone);

        public static DateTime PacificDate(DateTime utcNow)
        {
            return PacificNow(utcNow).Date;
        }

        public static TimeSpan PacificTimeOfDay(DateTime utcNow)
        {
            return PacificNow(utcNow).TimeOfDay;
        }

        private static DateTime PacificNow(DateTime utcNow)
        {
            DateTime utc = utcNow.Kind == DateTimeKind.Utc
                ? utcNow
                : utcNow.ToUniversalTime();
            return TimeZoneInfo.ConvertTimeFromUtc(utc, PacificTimeZone.Value);
        }

        private static TimeZoneInfo FindPacificTimeZone()
        {
            foreach (string id in new[] { "Pacific Standard Time", "America/Los_Angeles" })
            {
                try
                {
                    return TimeZoneInfo.FindSystemTimeZoneById(id);
                }
                catch (TimeZoneNotFoundException)
                {
                }
                catch (InvalidTimeZoneException)
                {
                }
            }

            return TimeZoneInfo.CreateCustomTimeZone(
                "PacificFallback",
                TimeSpan.FromHours(-8),
                "Pacific Time",
                "Pacific Standard Time");
        }
    }

    public interface IDynamicQuestDailyQuotaStore
    {
        bool TryReserveDaily(string providerName, DateTime pacificDay, int dailyLimit);
    }

    public interface IDynamicQuestTokenBudgetStore
    {
        DynamicQuestTokenReservation TryReserveTokens(
            string providerName,
            DateTime pacificDay,
            int dailyTokenLimit,
            int estimatedTokens,
            out string error);

        void FinalizeTokens(DynamicQuestTokenReservation reservation, int actualTokens);
        void CancelTokens(DynamicQuestTokenReservation reservation);
    }

    public sealed class DynamicQuestTokenReservation
    {
        public DynamicQuestTokenReservation(string providerName, DateTime pacificDay, int estimatedTokens)
        {
            ProviderName = providerName ?? string.Empty;
            PacificDay = pacificDay.Date;
            EstimatedTokens = Math.Max(0, estimatedTokens);
        }

        public string ProviderName { get; }
        public DateTime PacificDay { get; }
        public int EstimatedTokens { get; }
    }

    public sealed class DynamicQuestTokenBudget
    {
        private readonly string m_providerName;
        private readonly int m_dailyTokenLimit;
        private readonly IDynamicQuestTokenBudgetStore m_store;
        private readonly Func<DateTime> m_now;

        public DynamicQuestTokenBudget(string providerName, int dailyTokenLimit, IDynamicQuestTokenBudgetStore store)
            : this(providerName, dailyTokenLimit, store, () => DateTime.UtcNow)
        {
        }

        public DynamicQuestTokenBudget(
            string providerName,
            int dailyTokenLimit,
            IDynamicQuestTokenBudgetStore store,
            Func<DateTime> now)
        {
            m_providerName = providerName ?? string.Empty;
            m_dailyTokenLimit = Math.Max(0, dailyTokenLimit);
            m_store = store;
            m_now = now ?? (() => DateTime.UtcNow);
        }

        public bool TryReserve(int estimatedTokens, out DynamicQuestTokenReservation reservation, out string error)
        {
            reservation = null;
            string providerName = (m_providerName ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(providerName))
            {
                error = "token_quota_provider_missing";
                return false;
            }

            if (m_dailyTokenLimit <= 0 || m_store == null)
            {
                error = $"{providerName}_token_quota_exhausted";
                return false;
            }

            int tokens = Math.Max(1, estimatedTokens);
            DateTime day = DynamicQuestGeminiQuotaClock.PacificDate(m_now().ToUniversalTime());
            reservation = m_store.TryReserveTokens(providerName, day, m_dailyTokenLimit, tokens, out error);
            return reservation != null;
        }

        public void Finalize(DynamicQuestTokenReservation reservation, int actualTokens)
        {
            if (reservation == null || m_store == null)
                return;

            m_store.FinalizeTokens(reservation, actualTokens > 0 ? actualTokens : reservation.EstimatedTokens);
        }

        public void Cancel(DynamicQuestTokenReservation reservation)
        {
            if (reservation == null || m_store == null)
                return;

            m_store.CancelTokens(reservation);
        }
    }

    public sealed class DynamicQuestGeminiQuota
    {
        private readonly int m_perMinuteLimit;
        private readonly int m_dailyLimit;
        private readonly Func<DateTime> m_now;
        private readonly string m_providerName;
        private readonly IDynamicQuestDailyQuotaStore m_dailyStore;
        private readonly object m_lock = new();
        private DateTime m_minuteBucket = DateTime.MinValue;
        private DateTime m_dayBucket = DateTime.MinValue;
        private DateTime m_backoffUntilUtc = DateTime.MinValue;
        private int m_minuteCount;
        private int m_dayCount;

        public DynamicQuestGeminiQuota(int perMinuteLimit, int dailyLimit)
            : this(perMinuteLimit, dailyLimit, () => DateTime.UtcNow)
        {
        }

        public DynamicQuestGeminiQuota(int perMinuteLimit, int dailyLimit, Func<DateTime> now)
            : this(perMinuteLimit, dailyLimit, now, string.Empty, null)
        {
        }

        public DynamicQuestGeminiQuota(
            int perMinuteLimit,
            int dailyLimit,
            Func<DateTime> now,
            string providerName,
            IDynamicQuestDailyQuotaStore dailyStore)
        {
            m_perMinuteLimit = Math.Max(0, perMinuteLimit);
            m_dailyLimit = Math.Max(0, dailyLimit);
            m_now = now ?? (() => DateTime.UtcNow);
            m_providerName = providerName ?? string.Empty;
            m_dailyStore = dailyStore;
        }

        public bool TryReserve()
        {
            if (m_perMinuteLimit <= 0 || m_dailyLimit <= 0)
                return false;

            lock (m_lock)
            {
                DateTime now = m_now().ToUniversalTime();
                if (now < m_backoffUntilUtc)
                    return false;

                DateTime minute = new(now.Year, now.Month, now.Day, now.Hour, now.Minute, 0, DateTimeKind.Utc);
                DateTime day = DynamicQuestGeminiQuotaClock.PacificDate(now);

                if (minute != m_minuteBucket)
                {
                    m_minuteBucket = minute;
                    m_minuteCount = 0;
                }

                if (day != m_dayBucket)
                {
                    m_dayBucket = day;
                    m_dayCount = 0;
                }

                if (m_minuteCount >= m_perMinuteLimit || m_dayCount >= m_dailyLimit)
                    return false;

                if (m_dailyStore != null && !string.IsNullOrWhiteSpace(m_providerName))
                {
                    if (!m_dailyStore.TryReserveDaily(m_providerName, day, m_dailyLimit))
                        return false;

                    m_minuteCount++;
                    return true;
                }

                m_minuteCount++;
                m_dayCount++;
                return true;
            }
        }

        public void MarkThrottled(TimeSpan duration)
        {
            if (duration <= TimeSpan.Zero)
                return;

            lock (m_lock)
            {
                DateTime until = m_now().ToUniversalTime().Add(duration);
                if (until > m_backoffUntilUtc)
                    m_backoffUntilUtc = until;
            }
        }
    }

    public sealed class DynamicQuestServerPropertyDailyQuotaStore : IDynamicQuestDailyQuotaStore, IDynamicQuestTokenBudgetStore
    {
        public static DynamicQuestServerPropertyDailyQuotaStore Instance { get; } = new();

        private readonly object m_lock = new();

        private DynamicQuestServerPropertyDailyQuotaStore()
        {
        }

        public bool TryReserveDaily(string providerName, DateTime pacificDay, int dailyLimit)
        {
            if (dailyLimit <= 0 || string.IsNullOrWhiteSpace(providerName))
                return false;

            if (GameServer.Database == null)
                return false;

            string safeProvider = SanitizeProviderName(providerName);
            if (string.IsNullOrWhiteSpace(safeProvider))
                return false;

            string key = $"kdaoc_dynamic_quest_story_quota_{safeProvider}_daily_usage";
            string dayText = pacificDay.ToString("yyyy-MM-dd", System.Globalization.CultureInfo.InvariantCulture);

            lock (m_lock)
            {
                try
                {
                    DbServerProperty row = GameServer.Database.SelectObject<DbServerProperty>(DB.Column("`Key`").IsEqualTo(key));
                    bool isNew = row == null;
                    if (row == null)
                    {
                        row = new DbServerProperty
                        {
                            Category = "kdaoc",
                            Key = key,
                            Description = $"KDAOC: Persistent dynamic quest story daily quota usage for {safeProvider}.",
                            DefaultValue = string.Empty,
                            Value = string.Empty
                        };
                    }

                    int used = 0;
                    string storedDay = string.Empty;
                    string[] parts = (row.Value ?? string.Empty).Split('|');
                    if (parts.Length == 2)
                    {
                        storedDay = parts[0].Trim();
                        int.TryParse(parts[1], out used);
                    }

                    if (!string.Equals(storedDay, dayText, StringComparison.Ordinal))
                        used = 0;

                    if (used >= dailyLimit)
                        return false;

                    row.Value = $"{dayText}|{used + 1}";
                    if (isNew || !row.IsPersisted)
                        return GameServer.Database.AddObject(row);

                    return GameServer.Database.SaveObject(row);
                }
                catch
                {
                    return false;
                }
            }
        }

        public DynamicQuestTokenReservation TryReserveTokens(
            string providerName,
            DateTime pacificDay,
            int dailyTokenLimit,
            int estimatedTokens,
            out string error)
        {
            error = string.Empty;
            if (dailyTokenLimit <= 0 || estimatedTokens <= 0 || string.IsNullOrWhiteSpace(providerName))
            {
                error = $"{providerName}_token_quota_exhausted";
                return null;
            }

            if (GameServer.Database == null)
            {
                error = $"{providerName}_token_quota_unavailable";
                return null;
            }

            string safeProvider = SanitizeProviderName(providerName);
            if (string.IsNullOrWhiteSpace(safeProvider))
            {
                error = "token_quota_provider_missing";
                return null;
            }

            string key = TokenBudgetKey(safeProvider);
            string dayText = pacificDay.ToString("yyyy-MM-dd", System.Globalization.CultureInfo.InvariantCulture);

            lock (m_lock)
            {
                try
                {
                    DbServerProperty row = ReadOrCreateTokenRow(key, safeProvider);
                    int used = ReadTokenUsage(row, dayText);
                    if (used + estimatedTokens > dailyTokenLimit)
                    {
                        error = $"{safeProvider}_token_quota_exhausted";
                        return null;
                    }

                    row.Value = $"{dayText}|{used + estimatedTokens}";
                    if (!SaveTokenRow(row))
                    {
                        error = $"{safeProvider}_token_quota_unavailable";
                        return null;
                    }

                    return new DynamicQuestTokenReservation(safeProvider, pacificDay, estimatedTokens);
                }
                catch
                {
                    error = $"{safeProvider}_token_quota_unavailable";
                    return null;
                }
            }
        }

        public void FinalizeTokens(DynamicQuestTokenReservation reservation, int actualTokens)
        {
            AdjustTokens(reservation, Math.Max(0, actualTokens) - (reservation?.EstimatedTokens ?? 0));
        }

        public void CancelTokens(DynamicQuestTokenReservation reservation)
        {
            AdjustTokens(reservation, -(reservation?.EstimatedTokens ?? 0));
        }

        private void AdjustTokens(DynamicQuestTokenReservation reservation, int delta)
        {
            if (reservation == null || delta == 0 || GameServer.Database == null)
                return;

            string safeProvider = SanitizeProviderName(reservation.ProviderName);
            if (string.IsNullOrWhiteSpace(safeProvider))
                return;

            string key = TokenBudgetKey(safeProvider);
            string dayText = reservation.PacificDay.ToString("yyyy-MM-dd", System.Globalization.CultureInfo.InvariantCulture);

            lock (m_lock)
            {
                try
                {
                    DbServerProperty row = ReadOrCreateTokenRow(key, safeProvider);
                    int used = ReadTokenUsage(row, dayText);
                    row.Value = $"{dayText}|{Math.Max(0, used + delta)}";
                    SaveTokenRow(row);
                }
                catch
                {
                }
            }
        }

        private static string TokenBudgetKey(string safeProvider)
        {
            return $"kdaoc_dynamic_quest_story_quota_{safeProvider}_daily_tokens";
        }

        private static DbServerProperty ReadOrCreateTokenRow(string key, string safeProvider)
        {
            DbServerProperty row = GameServer.Database.SelectObject<DbServerProperty>(DB.Column("`Key`").IsEqualTo(key));
            if (row != null)
                return row;

            return new DbServerProperty
            {
                Category = "kdaoc",
                Key = key,
                Description = $"KDAOC: Persistent dynamic quest story daily token usage for {safeProvider}.",
                DefaultValue = string.Empty,
                Value = string.Empty
            };
        }

        private static int ReadTokenUsage(DbServerProperty row, string dayText)
        {
            int used = 0;
            string storedDay = string.Empty;
            string[] parts = (row?.Value ?? string.Empty).Split('|');
            if (parts.Length == 2)
            {
                storedDay = parts[0].Trim();
                int.TryParse(parts[1], out used);
            }

            return string.Equals(storedDay, dayText, StringComparison.Ordinal) ? Math.Max(0, used) : 0;
        }

        private static bool SaveTokenRow(DbServerProperty row)
        {
            if (row == null)
                return false;

            if (!row.IsPersisted)
                return GameServer.Database.AddObject(row);

            return GameServer.Database.SaveObject(row);
        }

        private static string SanitizeProviderName(string providerName)
        {
            StringBuilder builder = new();
            foreach (char c in providerName.Trim().ToLowerInvariant())
            {
                if ((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9'))
                    builder.Append(c);
                else if (c == '-' || c == '_')
                    builder.Append('_');
            }

            return builder.ToString().Trim('_');
        }
    }
}
