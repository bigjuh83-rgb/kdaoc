using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using DOL.Database;
using DOL.Language;

namespace DOL.GS.WorldAI
{
    public sealed class DynamicQuestTemplate
    {
        public string TemplateId { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public string StorySeed { get; set; } = string.Empty;
        public string OfferText { get; set; } = string.Empty;
        public string ProgressText { get; set; } = string.Empty;
        public string FinishText { get; set; } = string.Empty;
        public string Realm { get; set; } = string.Empty;
        public string PreferredStartNpcName { get; set; } = string.Empty;
        public string PreferredStartNpcInternalId { get; set; } = string.Empty;
        public ushort PreferredRegionId { get; set; }
        public string TargetNameHint { get; set; } = string.Empty;
        public string PreferredTargetNpcInternalId { get; set; } = string.Empty;
        public int Count { get; set; } = 1;
        public int MinLevel { get; set; } = 1;
        public int MaxLevel { get; set; } = 50;
        public string Source { get; set; } = string.Empty;
        public IList<string> Tags { get; set; } = Array.Empty<string>();
        public string StoryProvider { get; set; } = string.Empty;
        public string StoryModel { get; set; } = string.Empty;
        public int StoryQualityScore { get; set; }
        public string StoryQualityJson { get; set; } = string.Empty;
        public string StoryNarrativeJson { get; set; } = string.Empty;
        public string StoryPresentationJson { get; set; } = string.Empty;
        public DateTime StoryGeneratedAt { get; set; } = DateTime.MinValue;
        public DateTime StoryLastUsedAt { get; set; } = DateTime.MinValue;
        public DynamicQuestStartMode StartMode { get; set; } = DynamicQuestStartMode.NpcOffer;
        public string Trigger { get; set; } = string.Empty;
        public string WorldRevision { get; set; } = string.Empty;
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
    }

    public sealed class DynamicQuestTemplateBindingResult
    {
        public bool Success { get; set; }
        public string Message { get; set; } = string.Empty;
        public string BindingKey { get; set; } = string.Empty;
        public DynamicQuestDefinition Quest { get; set; }

        public static DynamicQuestTemplateBindingResult Fail(string message)
        {
            return new DynamicQuestTemplateBindingResult { Success = false, Message = message };
        }
    }

    public interface IDynamicQuestTemplateRepository
    {
        bool Add(DbDynamicQuestTemplate row);
        DbDynamicQuestTemplate Find(string templateId);
        IList<DbDynamicQuestTemplate> GetActive();
        bool Save(DbDynamicQuestTemplate row);
    }

    public sealed class DynamicQuestTemplateService
    {
        private const int TargetClusterRadius = 6500;
        private const int TargetClusterLevelTolerance = 5;
        private const int NearStartMinimumSafeTargetDistance = 1500;
        private const int NearStartPreferredRadius = 5000;
        private const int NearStartExpandedSafeRadius = 12000;
        private const int StarterMaxSoloSafeTargetLevel = 2;
        private const int AutoAcceptFallbackMaxTargetLevel = 5;
        private const int TargetAreaThreatRadius = 900;
        private const int TargetRouteThreatRadius = 1200;

        private static readonly JsonSerializerOptions JsonOptions = new()
        {
            PropertyNameCaseInsensitive = true
        };

        public DynamicQuestTemplateBindingResult BindTemplate(
            DynamicQuestTemplate template,
            IEnumerable<DynamicQuestSeedNpc> npcs)
        {
            if (template == null || string.IsNullOrWhiteSpace(template.TemplateId))
                return DynamicQuestTemplateBindingResult.Fail("dynamic quest template is missing");

            List<DynamicQuestSeedNpc> npcList = (npcs ?? Array.Empty<DynamicQuestSeedNpc>())
                .Where(IsUsableNpc)
                .ToList();

            bool requiresStartNpc = RequiresStartNpc(template);
            DynamicQuestSeedNpc startNpc = null;
            DynamicQuestSeedNpc targetNpc = null;
            if (requiresStartNpc && IsStarterLocationConstrained(template))
            {
                (startNpc, targetNpc) = SelectStarterLocationConstrainedPair(template, npcList);
            }
            else
            {
                startNpc = requiresStartNpc ? SelectStartNpc(template, npcList) : null;
            }

            if (requiresStartNpc && startNpc == null)
                return DynamicQuestTemplateBindingResult.Fail($"start npc not found for template: {template.TemplateId}");

            targetNpc ??= requiresStartNpc
                ? SelectTargetNpc(template, startNpc, npcList)
                : SelectWorldTargetNpc(template, npcList);
            if (targetNpc == null)
                return DynamicQuestTemplateBindingResult.Fail($"target npc not found for template: {template.TemplateId}");

            DynamicQuestTargetPlan targetPlan = BuildTargetPlan(template, targetNpc, npcList);
            string bindingKey = BuildBindingKey(template, startNpc, targetNpc, targetPlan);
            DynamicQuestDefinition quest = BuildQuest(template, startNpc, targetNpc, targetPlan, bindingKey);
            return new DynamicQuestTemplateBindingResult
            {
                Success = true,
                Message = $"dynamic quest template bound: {template.TemplateId}",
                BindingKey = bindingKey,
                Quest = quest
            };
        }

        internal static DbDynamicQuestTemplate ToRowForTest(DynamicQuestTemplate template)
        {
            return ToRow(template, string.Empty);
        }

        internal static DbDynamicQuestTemplate ToRowForCache(DynamicQuestTemplate template, string lastBindingKey)
        {
            return ToRow(template, lastBindingKey);
        }

        internal static DynamicQuestTemplate FromRowForTest(DbDynamicQuestTemplate row)
        {
            return FromRow(row);
        }

        internal static DynamicQuestTemplate FromRowForCache(DbDynamicQuestTemplate row)
        {
            return FromRow(row);
        }

        private static DbDynamicQuestTemplate ToRow(DynamicQuestTemplate template, string lastBindingKey)
        {
            DateTime now = DateTime.UtcNow;
            return new DbDynamicQuestTemplate
            {
                TemplateId = template.TemplateId ?? string.Empty,
                Title = template.Title ?? string.Empty,
                StorySeed = template.StorySeed ?? string.Empty,
                OfferText = template.OfferText ?? string.Empty,
                ProgressText = template.ProgressText ?? string.Empty,
                FinishText = template.FinishText ?? string.Empty,
                Realm = template.Realm ?? string.Empty,
                PreferredStartNpcName = template.PreferredStartNpcName ?? string.Empty,
                PreferredRegionId = template.PreferredRegionId,
                TargetNameHint = template.TargetNameHint ?? string.Empty,
                Count = Math.Max(1, template.Count),
                MinLevel = Math.Clamp(template.MinLevel, 1, 50),
                MaxLevel = Math.Clamp(Math.Max(template.MaxLevel, template.MinLevel), 1, 50),
                Source = template.Source ?? string.Empty,
                TagsJson = JsonSerializer.Serialize(template.Tags ?? Array.Empty<string>(), JsonOptions),
                StoryProvider = template.StoryProvider ?? string.Empty,
                StoryModel = template.StoryModel ?? string.Empty,
                StoryQualityScore = Math.Clamp(template.StoryQualityScore, 0, 100),
                StoryQualityJson = template.StoryQualityJson ?? string.Empty,
                StoryNarrativeJson = template.StoryNarrativeJson ?? string.Empty,
                StoryPresentationJson = template.StoryPresentationJson ?? string.Empty,
                StoryGeneratedAt = template.StoryGeneratedAt == default ? DateTime.MinValue : template.StoryGeneratedAt,
                StoryLastUsedAt = template.StoryLastUsedAt == default ? DateTime.MinValue : template.StoryLastUsedAt,
                StartMode = template.StartMode.ToString(),
                Trigger = template.Trigger ?? string.Empty,
                StartNpcInternalId = string.Empty,
                LastBindingKey = lastBindingKey ?? string.Empty,
                IsActive = true,
                CreatedAt = template.CreatedAt == default ? now : template.CreatedAt,
                UpdatedAt = now
            };
        }

        private static DynamicQuestTemplate FromRow(DbDynamicQuestTemplate row)
        {
            if (row == null)
                return null;

            return new DynamicQuestTemplate
            {
                TemplateId = row.TemplateId ?? string.Empty,
                Title = row.Title ?? string.Empty,
                StorySeed = row.StorySeed ?? string.Empty,
                OfferText = row.OfferText ?? string.Empty,
                ProgressText = row.ProgressText ?? string.Empty,
                FinishText = row.FinishText ?? string.Empty,
                Realm = row.Realm ?? string.Empty,
                PreferredStartNpcName = row.PreferredStartNpcName ?? string.Empty,
                PreferredRegionId = row.PreferredRegionId,
                TargetNameHint = row.TargetNameHint ?? string.Empty,
                Count = Math.Max(1, row.Count),
                MinLevel = Math.Clamp(row.MinLevel, 1, 50),
                MaxLevel = Math.Clamp(Math.Max(row.MaxLevel, row.MinLevel), 1, 50),
                Source = row.Source ?? string.Empty,
                Tags = DeserializeTags(row.TagsJson),
                StoryProvider = row.StoryProvider ?? string.Empty,
                StoryModel = row.StoryModel ?? string.Empty,
                StoryQualityScore = Math.Clamp(row.StoryQualityScore, 0, 100),
                StoryQualityJson = row.StoryQualityJson ?? string.Empty,
                StoryNarrativeJson = row.StoryNarrativeJson ?? string.Empty,
                StoryPresentationJson = row.StoryPresentationJson ?? string.Empty,
                StoryGeneratedAt = row.StoryGeneratedAt,
                StoryLastUsedAt = row.StoryLastUsedAt,
                StartMode = ParseStartMode(row.StartMode),
                Trigger = row.Trigger ?? string.Empty,
                CreatedAt = row.CreatedAt,
                UpdatedAt = row.UpdatedAt
            };
        }

        private static IList<string> DeserializeTags(string json)
        {
            try
            {
                if (string.IsNullOrWhiteSpace(json))
                    return Array.Empty<string>();

                return JsonSerializer.Deserialize<List<string>>(json, JsonOptions) ?? new List<string>();
            }
            catch
            {
                return Array.Empty<string>();
            }
        }

        private static bool IsUsableNpc(DynamicQuestSeedNpc npc)
        {
            return npc != null &&
                   !string.IsNullOrWhiteSpace(npc.Name) &&
                   !string.IsNullOrWhiteSpace(npc.InternalID);
        }

        private static DynamicQuestSeedNpc SelectStartNpc(DynamicQuestTemplate template, IList<DynamicQuestSeedNpc> npcs)
        {
            if (!string.IsNullOrWhiteSpace(template.PreferredStartNpcInternalId))
            {
                DynamicQuestSeedNpc pinnedStart = npcs.FirstOrDefault(npc =>
                    IsPinnedTemplateStartNpcCandidate(npc) &&
                    string.Equals(npc.InternalID, template.PreferredStartNpcInternalId, StringComparison.OrdinalIgnoreCase) &&
                    (template.PreferredRegionId == 0 || npc.RegionId == template.PreferredRegionId));
                if (pinnedStart != null)
                    return pinnedStart;
            }

            return SelectStartNpcCandidates(template, npcs)
                .FirstOrDefault();
        }

        private static IEnumerable<DynamicQuestSeedNpc> SelectStartNpcCandidates(
            DynamicQuestTemplate template,
            IList<DynamicQuestSeedNpc> npcs)
        {
            return npcs
                .Where(npc => template.PreferredRegionId == 0 || npc.RegionId == template.PreferredRegionId)
                .Where(IsTemplateStartNpcCandidate)
                .OrderByDescending(npc => string.Equals(npc.Name, template.PreferredStartNpcName, StringComparison.OrdinalIgnoreCase))
                .ThenBy(npc => Math.Abs((npc.Level <= 0 ? 1 : npc.Level) - template.MinLevel))
                .ThenBy(npc => npc.Name, StringComparer.OrdinalIgnoreCase);
        }

        private static (DynamicQuestSeedNpc StartNpc, DynamicQuestSeedNpc TargetNpc) SelectStarterLocationConstrainedPair(
            DynamicQuestTemplate template,
            IList<DynamicQuestSeedNpc> npcs)
        {
            DynamicQuestSeedNpc pinnedStart = null;
            if (!string.IsNullOrWhiteSpace(template.PreferredStartNpcInternalId))
            {
                pinnedStart = npcs.FirstOrDefault(npc =>
                    IsPinnedTemplateStartNpcCandidate(npc) &&
                    string.Equals(npc.InternalID, template.PreferredStartNpcInternalId, StringComparison.OrdinalIgnoreCase) &&
                    (template.PreferredRegionId == 0 || npc.RegionId == template.PreferredRegionId));
            }

            IEnumerable<DynamicQuestSeedNpc> starts = pinnedStart != null
                ? new[] { pinnedStart }
                : SelectStartNpcCandidates(template, npcs);

            foreach (DynamicQuestSeedNpc candidateStart in starts)
            {
                DynamicQuestSeedNpc candidateTarget = SelectTargetNpc(template, candidateStart, npcs);
                if (candidateTarget != null)
                    return (candidateStart, candidateTarget);
            }

            return pinnedStart != null
                ? (pinnedStart, null)
                : (SelectStartNpc(template, npcs), null);
        }

        private static DynamicQuestSeedNpc SelectTargetNpc(
            DynamicQuestTemplate template,
            DynamicQuestSeedNpc startNpc,
            IList<DynamicQuestSeedNpc> npcs)
        {
            DynamicQuestSeedNpc pinnedTarget = SelectPinnedTargetNpc(template, startNpc, npcs);
            if (pinnedTarget != null)
                return pinnedTarget;

            List<DynamicQuestSeedNpc> candidates = npcs
                .Where(npc => npc.RegionId == startNpc.RegionId)
                .Where(npc => !string.Equals(npc.InternalID, startNpc.InternalID, StringComparison.OrdinalIgnoreCase))
                .Where(IsTemplateTargetNpcCandidate)
                .Where(npc => IsTargetLevelCandidate(npc, template))
                .ToList();

            candidates = PreferStarterSafeTargets(candidates, template, npcs, startNpc);
            if (candidates.Count == 0)
                return null;

            return candidates
                .OrderBy(npc => TargetStarterUnsafeNameRank(npc, template))
                .ThenBy(npc => TargetGrowthRiskRank(npc, template))
                .ThenBy(npc => TargetNameHintRank(npc, template))
                .ThenBy(npc => TargetSafetyRankLevel(npc, template))
                .ThenBy(npc => TargetAggressionRank(npc, template))
                .ThenBy(npc => TargetAreaThreatRank(npcs, npc, template, startNpc))
                .ThenBy(npc => TargetRouteThreatRank(npcs, startNpc, npc, template))
                .ThenBy(npc => TargetStartDistanceRank(startNpc, npc))
                .ThenBy(npc => TargetStarterPreyNameRank(npc, template))
                .ThenBy(npc => DistanceSquared(startNpc, npc))
                .ThenBy(npc => npc.Name, StringComparer.OrdinalIgnoreCase)
                .FirstOrDefault();
        }

        private static DynamicQuestSeedNpc SelectWorldTargetNpc(
            DynamicQuestTemplate template,
            IList<DynamicQuestSeedNpc> npcs)
        {
            DynamicQuestSeedNpc pinnedTarget = SelectPinnedTargetNpc(template, null, npcs);
            if (pinnedTarget != null)
                return pinnedTarget;

            List<DynamicQuestSeedNpc> candidates = npcs
                .Where(npc => template.PreferredRegionId == 0 || npc.RegionId == template.PreferredRegionId)
                .Where(IsTemplateTargetNpcCandidate)
                .Where(npc => IsTargetLevelCandidate(npc, template))
                .ToList();

            candidates = PreferStarterSafeTargets(candidates, template, npcs);

            IEnumerable<DynamicQuestSeedNpc> ordered = template.StartMode == DynamicQuestStartMode.AutoAccept
                ? candidates
                    .OrderBy(npc => TargetAutoAcceptSoloRiskRank(npc, template))
                    .ThenBy(npc => TargetGrowthRiskRank(npc, template))
                    .ThenBy(npc => TargetAreaThreatRank(npcs, npc, template))
                    .ThenBy(npc => TargetNameHintRank(npc, template))
                    .ThenBy(npc => Math.Abs((npc.Level <= 0 ? template.MinLevel : npc.Level) - template.MinLevel))
                    .ThenBy(npc => TargetStarterPreyNameRank(npc, template))
                    .ThenBy(npc => npc.Name, StringComparer.OrdinalIgnoreCase)
                : candidates
                    .OrderBy(npc => TargetStarterUnsafeNameRank(npc, template))
                    .ThenBy(npc => TargetGrowthRiskRank(npc, template))
                    .ThenBy(npc => TargetNameHintRank(npc, template))
                    .ThenBy(npc => Math.Abs((npc.Level <= 0 ? template.MinLevel : npc.Level) - template.MinLevel))
                    .ThenBy(npc => TargetStarterPreyNameRank(npc, template))
                    .ThenBy(npc => npc.Name, StringComparer.OrdinalIgnoreCase);

            return ordered.FirstOrDefault();
        }

        private static DynamicQuestSeedNpc SelectPinnedTargetNpc(
            DynamicQuestTemplate template,
            DynamicQuestSeedNpc startNpc,
            IList<DynamicQuestSeedNpc> npcs)
        {
            if (template == null || string.IsNullOrWhiteSpace(template.PreferredTargetNpcInternalId))
                return null;

            DynamicQuestSeedNpc pinned = npcs.FirstOrDefault(npc =>
                string.Equals(npc.InternalID, template.PreferredTargetNpcInternalId, StringComparison.OrdinalIgnoreCase) &&
                IsPinnedTemplateTargetNpcCandidate(npc) &&
                (template.PreferredRegionId == 0 || npc.RegionId == template.PreferredRegionId) &&
                (startNpc == null || npc.RegionId == startNpc.RegionId) &&
                (startNpc == null || !string.Equals(npc.InternalID, startNpc.InternalID, StringComparison.OrdinalIgnoreCase)) &&
                (npc.Level <= 0 || (npc.Level >= template.MinLevel && npc.Level <= template.MaxLevel)));

            if (pinned == null)
                return null;

            if (template.StartMode == DynamicQuestStartMode.AutoAccept &&
                TargetAutoAcceptSoloRiskRank(pinned, template) > 0)
                return null;

            if ((IsStarterBand(template) || IsStarterLocationConstrained(template)) &&
                startNpc != null &&
                DistanceSquared(startNpc, pinned) > (long)NearStartExpandedSafeRadius * NearStartExpandedSafeRadius)
                return null;

            if (IsStarterTargetSafeForSolo(pinned, template, npcs, startNpc))
                return pinned;

            return null;
        }

        private static bool IsTemplateStartNpcCandidate(DynamicQuestSeedNpc npc)
        {
            return npc != null &&
                   (!npc.HasSourceNpcMetadata || DynamicQuestSeedService.IsLikelyDynamicQuestStartNpc(npc));
        }

        private static bool IsPinnedTemplateStartNpcCandidate(DynamicQuestSeedNpc npc)
        {
            return npc != null &&
                   (!npc.HasSourceNpcMetadata || !DynamicQuestSeedService.IsLikelyWorldQuestTarget(npc));
        }

        private static bool IsTemplateTargetNpcCandidate(DynamicQuestSeedNpc npc)
        {
            return npc != null &&
                   (!npc.HasSourceNpcMetadata || DynamicQuestSeedService.IsLikelyWorldQuestTarget(npc));
        }

        private static bool IsPinnedTemplateTargetNpcCandidate(DynamicQuestSeedNpc npc)
        {
            if (npc == null)
                return false;

            if (!npc.HasSourceNpcMetadata)
                return true;

            return npc.SourceIsAlive &&
                   !npc.SourceFlags.HasFlag(GameNPC.eFlags.PEACE) &&
                   !npc.SourceFlags.HasFlag(GameNPC.eFlags.CANTTARGET);
        }

        private static long DistanceSquared(DynamicQuestSeedNpc a, DynamicQuestSeedNpc b)
        {
            long dx = (long)a.X - b.X;
            long dy = (long)a.Y - b.Y;
            return dx * dx + dy * dy;
        }

        private static double DistanceSquaredToSegment(
            DynamicQuestSeedNpc point,
            DynamicQuestSeedNpc segmentStart,
            DynamicQuestSeedNpc segmentEnd)
        {
            double x = point.X;
            double y = point.Y;
            double x1 = segmentStart.X;
            double y1 = segmentStart.Y;
            double x2 = segmentEnd.X;
            double y2 = segmentEnd.Y;
            double dx = x2 - x1;
            double dy = y2 - y1;
            double lengthSquared = dx * dx + dy * dy;
            if (lengthSquared <= double.Epsilon)
                return DistanceSquared(point, segmentStart);

            double t = ((x - x1) * dx + (y - y1) * dy) / lengthSquared;
            t = Math.Clamp(t, 0.0, 1.0);
            double projectionX = x1 + t * dx;
            double projectionY = y1 + t * dy;
            double pdx = x - projectionX;
            double pdy = y - projectionY;
            return pdx * pdx + pdy * pdy;
        }

        private static int TargetSafetyRankLevel(DynamicQuestSeedNpc npc, DynamicQuestTemplate template)
        {
            int minLevel = Math.Clamp(template?.MinLevel ?? 1, 1, 50);
            return Math.Abs(((npc?.Level ?? 0) <= 0 ? minLevel : npc.Level) - minLevel);
        }

        private static int TargetAggressionRank(DynamicQuestSeedNpc targetNpc, DynamicQuestTemplate template)
        {
            if (targetNpc == null || template == null)
                return 0;

            if (!IsStarterSafetyConstrained(template))
                return 0;

            int rank = 0;
            if (targetNpc.SourceAggroLevel > 0)
                rank += 10 + Math.Clamp(targetNpc.SourceAggroLevel, 0, 100);
            if (targetNpc.SourceAggroRange > 0)
                rank += Math.Min(10, targetNpc.SourceAggroRange / 100);
            return rank;
        }

        private static int TargetAutoAcceptSoloRiskRank(DynamicQuestSeedNpc targetNpc, DynamicQuestTemplate template)
        {
            if (targetNpc == null || template == null || template.StartMode != DynamicQuestStartMode.AutoAccept)
                return 0;

            string name = NormalizeNameForSafetyRank(targetNpc.Name);
            int rank = 0;
            if (IsLikelyInvalidTargetDisplayName(targetNpc.Name))
                rank += 250;
            if (IsLikelyProperNamedTarget(targetNpc.Name))
                rank += 120;
            if (ContainsAny(name, "lord", "lady", "captain", "commander", "chief", "prince", "princess", "king", "queen", "master",
                    "bandit", "raider", "brawler", "giant", "massive", "elder", "ancient"))
                rank += 100;
            if (ContainsAny(name, " guard", " sentry", " sentinel", " watchman", " watcher", " protector", " defender",
                    " eater", " ghoul", " wraith", " spectre", " specter", " changeling"))
                rank += 140;
            if (targetNpc.SourceAggroLevel > 0)
                rank += 10 + Math.Clamp(targetNpc.SourceAggroLevel, 0, 100);
            if (targetNpc.SourceAggroRange > 0)
                rank += Math.Min(20, targetNpc.SourceAggroRange / 75);
            int effectiveLevel = targetNpc.Level > 0 ? targetNpc.Level : Math.Max(1, template.MinLevel);
            if (targetNpc.Level <= 0 && template.MinLevel > AutoAcceptFallbackMaxTargetLevel)
                rank += 120;
            if (effectiveLevel > StarterMaxSoloSafeTargetLevel)
                rank += Math.Min(160, 30 + (effectiveLevel - StarterMaxSoloSafeTargetLevel) * 12);
            if (effectiveLevel > 10)
                rank += Math.Min(80, (effectiveLevel - 10) * 4);

            return rank;
        }

        private static bool IsTargetLevelCandidate(DynamicQuestSeedNpc npc, DynamicQuestTemplate template)
        {
            if (npc == null || template == null)
                return true;

            if (npc.Level <= 0)
                return template.StartMode != DynamicQuestStartMode.AutoAccept ||
                       template.MinLevel <= AutoAcceptFallbackMaxTargetLevel;

            if (npc.Level >= template.MinLevel && npc.Level <= template.MaxLevel)
                return true;

            if (IsStarterSafetyConstrained(template) &&
                npc.Level >= 1 &&
                npc.Level <= StarterMaxSoloSafeTargetLevel)
                return true;

            return template.StartMode == DynamicQuestStartMode.AutoAccept &&
                   npc.Level >= 1 &&
                   npc.Level <= AutoAcceptFallbackMaxTargetLevel;
        }

        private static bool IsLikelyInvalidTargetDisplayName(string name)
        {
            string value = (name ?? string.Empty).Trim();
            if (value.Length == 0)
                return false;

            string normalized = NormalizeNameForSafetyRank(value);
            return value.Contains(':') ||
                   ContainsAny(normalized, " dps", " total", " af", " abs") ||
                   value.Any(char.IsDigit);
        }

        private static bool IsLikelyProperNamedTarget(string name)
        {
            string value = (name ?? string.Empty).Trim();
            if (value.Length == 0)
                return false;

            string[] ignored = { "the", "of", "a", "an", "de", "la" };
            List<string> words = value
                .Split(' ', StringSplitOptions.RemoveEmptyEntries)
                .Select(word => word.Trim('\'', '"', ',', '.', ':', ';', '!', '?', '(', ')', '[', ']'))
                .Where(word => word.Any(char.IsLetter))
                .Where(word => !ignored.Contains(word, StringComparer.OrdinalIgnoreCase))
                .ToList();

            return words.Count > 0 && words.All(IsProperNameWord);
        }

        private static bool IsProperNameWord(string word)
        {
            return !string.IsNullOrWhiteSpace(word) &&
                   char.IsUpper(word[0]) &&
                   word.Skip(1).Any(char.IsLower);
        }

        private static int TargetStarterUnsafeNameRank(DynamicQuestSeedNpc targetNpc, DynamicQuestTemplate template)
        {
            if (targetNpc == null || template == null || !IsStarterSafetyConstrained(template))
                return 0;

            string name = NormalizeNameForSafetyRank(targetNpc.Name);
            if (string.IsNullOrWhiteSpace(name))
                return 0;

            if (ContainsAny(name, "large ant", "dragon ant", "giant", "massive", "elder", "ancient", "raider", "brawler", "bandit", "nuisance"))
                return 30;

            return 0;
        }

        private static bool IsStarterUnsafeName(string name)
        {
            string normalized = NormalizeNameForSafetyRank(name);
            return ContainsAny(normalized, "large ant", "dragon ant", "giant", "massive", "elder", "ancient", "raider", "brawler", "bandit", "nuisance");
        }

        private static List<DynamicQuestSeedNpc> PreferStarterSafeTargets(
            List<DynamicQuestSeedNpc> candidates,
            DynamicQuestTemplate template,
            IEnumerable<DynamicQuestSeedNpc> allNpcs,
            DynamicQuestSeedNpc startNpc = null)
        {
            if (candidates == null)
                return new List<DynamicQuestSeedNpc>();

            if (!IsStarterBand(template) &&
                template?.StartMode != DynamicQuestStartMode.AutoAccept &&
                !(startNpc != null && IsStarterLocationConstrained(template)))
                return candidates;

            if (startNpc != null)
            {
                List<DynamicQuestSeedNpc> nearby = RequireTargetsNearStart(candidates, startNpc, NearStartPreferredRadius);
                List<DynamicQuestSeedNpc> nearbySafe = nearby
                    .Where(npc => IsStarterTargetSafeForSolo(npc, template, allNpcs, startNpc))
                    .ToList();

                List<DynamicQuestSeedNpc> expandedSafe = RequireTargetsNearStart(candidates, startNpc, NearStartExpandedSafeRadius)
                    .Where(npc => IsStarterTargetSafeForSolo(npc, template, allNpcs, startNpc))
                    .ToList();
                List<DynamicQuestSeedNpc> nearbyOrExpandedSafe = nearbySafe
                    .Concat(expandedSafe)
                    .GroupBy(npc => npc.InternalID ?? string.Empty, StringComparer.OrdinalIgnoreCase)
                    .Select(group => group.First())
                    .ToList();
                if (nearbyOrExpandedSafe.Count > 0)
                    return nearbyOrExpandedSafe;

                return new List<DynamicQuestSeedNpc>();
            }

            List<DynamicQuestSeedNpc> safe = candidates
                .Where(npc => IsStarterAutoAcceptAreaSafe(npc, template, allNpcs, startNpc))
                .ToList();
            if (safe.Count > 0)
                return safe;

            if (template.StartMode == DynamicQuestStartMode.AutoAccept)
                return new List<DynamicQuestSeedNpc>();

            List<DynamicQuestSeedNpc> nonSevere = candidates
                .Where(npc => !IsStarterSevereTargetRisk(npc, template))
                .ToList();
            return nonSevere.Count > 0 ? nonSevere : candidates;
        }

        private static bool IsStarterAutoAcceptAreaSafe(
            DynamicQuestSeedNpc targetNpc,
            DynamicQuestTemplate template,
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedNpc startNpc)
        {
            if (targetNpc == null)
                return true;

            bool starterBand = IsStarterSafetyConstrained(template);
            bool lowAutoAcceptTarget = template?.StartMode == DynamicQuestStartMode.AutoAccept &&
                                       (targetNpc.Level <= 0 || targetNpc.Level <= AutoAcceptFallbackMaxTargetLevel);
            if (!starterBand && !lowAutoAcceptTarget)
                return true;

            return !IsStarterActiveGrowthThreat(targetNpc) &&
                   TargetStarterUnsafeNameRank(targetNpc, template) < 30 &&
                   TargetAggressionRank(targetNpc, template) == 0 &&
                   TargetAreaThreatRank(npcs, targetNpc, template, startNpc) == 0 &&
                   TargetRouteThreatRank(npcs, startNpc, targetNpc, template) == 0;
        }

        private static List<DynamicQuestSeedNpc> RequireTargetsNearStart(
            IEnumerable<DynamicQuestSeedNpc> candidates,
            DynamicQuestSeedNpc startNpc,
            int radius)
        {
            if (startNpc == null)
                return (candidates ?? Array.Empty<DynamicQuestSeedNpc>()).ToList();

            long radiusSquared = (long)Math.Max(1, radius) * Math.Max(1, radius);
            return (candidates ?? Array.Empty<DynamicQuestSeedNpc>())
                .Where(npc => DistanceSquared(startNpc, npc) <= radiusSquared)
                .ToList();
        }

        private static bool IsStarterBand(DynamicQuestTemplate template)
        {
            return template != null && template.MinLevel <= 1 && template.MaxLevel <= 5;
        }

        private static bool IsStarterSafetyConstrained(DynamicQuestTemplate template)
        {
            return IsStarterBand(template) || HasTag(template, "starter");
        }

        private static bool IsStarterLocationConstrained(DynamicQuestTemplate template)
        {
            return template != null &&
                   template.StartMode == DynamicQuestStartMode.NpcOffer &&
                   HasTag(template, "starter");
        }

        private static bool HasTag(DynamicQuestTemplate template, string tag)
        {
            return template?.Tags != null &&
                   template.Tags.Any(value => string.Equals(value, tag, StringComparison.OrdinalIgnoreCase));
        }

        private static bool IsStarterSevereTargetRisk(DynamicQuestSeedNpc targetNpc, DynamicQuestTemplate template)
        {
            return IsStarterSafetyConstrained(template) &&
                   targetNpc != null &&
                   (targetNpc.Level > StarterMaxSoloSafeTargetLevel ||
                    TargetStarterUnsafeNameRank(targetNpc, template) >= 30 ||
                    TargetAggressionRank(targetNpc, template) > 0 ||
                    IsStarterActiveGrowthThreat(targetNpc));
        }

        private static bool IsStarterGrowthThreat(DynamicQuestSeedNpc npc)
        {
            if (npc == null)
                return false;

            if (npc.NameGrowthThreatCount > 0)
                return true;

            string liveName = string.IsNullOrWhiteSpace(npc.RawName) ? npc.Name : npc.RawName;
            if (HasGrowthNamePrefix(liveName))
                return true;

            if (!npc.HasGrowthState)
                return false;

            if (npc.GrowthIsMutant || npc.GrowthMutationPending || npc.GrowthPlayerKills > 0 || npc.GrowthLevel > 0)
                return true;

            if (!string.IsNullOrWhiteSpace(npc.GrowthStage) &&
                !string.Equals(npc.GrowthStage, MobGrowthStages.Normal, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            return npc.GrowthEffectiveLevel > 5 || npc.GrowthScore >= 20;
        }

        private static bool IsStarterTargetSafeForSolo(
            DynamicQuestSeedNpc targetNpc,
            DynamicQuestTemplate template,
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedNpc startNpc)
        {
            if (!IsStarterSafetyConstrained(template))
                return true;

            return !IsStarterSevereTargetRisk(targetNpc, template) &&
                   TargetAreaThreatRank(npcs, targetNpc, template, startNpc) == 0 &&
                   TargetRouteThreatRank(npcs, startNpc, targetNpc, template) == 0;
        }

        private static int TargetGrowthRiskRank(DynamicQuestSeedNpc targetNpc, DynamicQuestTemplate template)
        {
            if (targetNpc == null || template == null)
                return 0;

            bool starterBand = IsStarterSafetyConstrained(template);
            int rank = 0;
            int effectiveLevel = targetNpc.GrowthEffectiveLevel > 0
                ? targetNpc.GrowthEffectiveLevel
                : targetNpc.Level;

            if (targetNpc.HasGrowthState)
            {
                if (!string.IsNullOrWhiteSpace(targetNpc.GrowthStage) &&
                    !string.Equals(targetNpc.GrowthStage, MobGrowthStages.Normal, StringComparison.OrdinalIgnoreCase))
                {
                    rank += starterBand ? 180 : 40;
                }

                if (targetNpc.GrowthIsMutant || targetNpc.GrowthMutationPending)
                    rank += starterBand ? 220 : 60;
                if (effectiveLevel > template.MaxLevel)
                    rank += (starterBand ? 140 : 30) + Math.Min(100, (effectiveLevel - template.MaxLevel) * 20);
                if (targetNpc.GrowthLevel > 0)
                    rank += (starterBand ? 60 : 10) + Math.Min(80, targetNpc.GrowthLevel * 12);
                if (targetNpc.GrowthPlayerKills > 0)
                    rank += (starterBand ? 160 : 40) + Math.Min(120, targetNpc.GrowthPlayerKills * 20);
                if (starterBand && targetNpc.GrowthScore >= 20)
                    rank += Math.Min(80, targetNpc.GrowthScore / 2);
            }

            if (targetNpc.NameGrowthThreatCount > 0)
            {
                rank += starterBand ? 260 : 50;
                rank += Math.Min(starterBand ? 180 : 60, targetNpc.NameGrowthThreatCount * (starterBand ? 25 : 8));
                if (targetNpc.NameGrowthMaxEffectiveLevel > template.MaxLevel)
                    rank += (starterBand ? 120 : 25) + Math.Min(80, (targetNpc.NameGrowthMaxEffectiveLevel - template.MaxLevel) * 15);
                if (targetNpc.NameGrowthPlayerKills > 0)
                    rank += (starterBand ? 120 : 30) + Math.Min(100, targetNpc.NameGrowthPlayerKills * 12);
                if (starterBand && targetNpc.NameGrowthMaxScore >= 20)
                    rank += Math.Min(120, targetNpc.NameGrowthMaxScore / 12);
            }

            if (HasGrowthNamePrefix(string.IsNullOrWhiteSpace(targetNpc.RawName) ? targetNpc.Name : targetNpc.RawName))
                rank += starterBand ? 220 : 40;

            return rank;
        }

        private static int TargetStarterPreyNameRank(DynamicQuestSeedNpc targetNpc, DynamicQuestTemplate template)
        {
            if (targetNpc == null || template == null || !IsStarterSafetyConstrained(template))
                return 0;

            string name = NormalizeNameForSafetyRank(targetNpc.Name);
            if (string.IsNullOrWhiteSpace(name))
                return 10;

            if (ContainsAny(name, "pup", "piglet", "larva", "young ", "soft-shelled", "beetle larva"))
                return 0;

            return 10;
        }

        private static int TargetNameHintRank(DynamicQuestSeedNpc targetNpc, DynamicQuestTemplate template)
        {
            if (targetNpc == null || template == null || string.IsNullOrWhiteSpace(template.TargetNameHint))
                return 1;

            return string.Equals(targetNpc.Name, template.TargetNameHint, StringComparison.OrdinalIgnoreCase) ? 0 : 1;
        }

        private static string NormalizeNameForSafetyRank(string name)
        {
            return $" {(name ?? string.Empty).Trim().ToLowerInvariant()} ";
        }

        private static bool ContainsAny(string value, params string[] needles)
        {
            return needles.Any(needle => value.Contains(needle, StringComparison.OrdinalIgnoreCase));
        }

        private static bool HasGrowthNamePrefix(string name)
        {
            string normalized = (name ?? string.Empty).Trim();
            return normalized.StartsWith("돌연변이 ", StringComparison.OrdinalIgnoreCase) ||
                   normalized.StartsWith("흉포한 ", StringComparison.OrdinalIgnoreCase) ||
                   normalized.StartsWith("챔피언 ", StringComparison.OrdinalIgnoreCase) ||
                   normalized.StartsWith("노련한 ", StringComparison.OrdinalIgnoreCase) ||
                   normalized.StartsWith("정예 ", StringComparison.OrdinalIgnoreCase) ||
                   normalized.StartsWith("우두머리 ", StringComparison.OrdinalIgnoreCase) ||
                   normalized.EndsWith(" 우두머리", StringComparison.OrdinalIgnoreCase);
        }

        private static int TargetAreaThreatRank(
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedNpc targetNpc,
            DynamicQuestTemplate template,
            DynamicQuestSeedNpc excludedNpc = null)
        {
            if (targetNpc == null)
                return 0;

            int targetLevel = targetNpc.Level > 0 ? targetNpc.Level : Math.Max(1, template?.MinLevel ?? 1);
            long radiusSquared = (long)TargetAreaThreatRadius * TargetAreaThreatRadius;
            return (npcs ?? Array.Empty<DynamicQuestSeedNpc>()).Count(npc =>
                !IsSameNpc(npc, excludedNpc) &&
                IsLikelyTargetAreaThreat(npc, targetNpc, targetLevel, template) &&
                DistanceSquared(targetNpc, npc) <= radiusSquared);
        }

        private static int TargetRouteThreatRank(
            IEnumerable<DynamicQuestSeedNpc> npcs,
            DynamicQuestSeedNpc startNpc,
            DynamicQuestSeedNpc targetNpc,
            DynamicQuestTemplate template)
        {
            if (startNpc == null || targetNpc == null || template == null || !IsStarterSafetyConstrained(template))
                return 0;

            int targetLevel = targetNpc.Level > 0 ? targetNpc.Level : Math.Max(1, template.MinLevel);
            double radiusSquared = TargetRouteThreatRadius * TargetRouteThreatRadius;
            return (npcs ?? Array.Empty<DynamicQuestSeedNpc>()).Count(npc =>
                IsLikelyTargetRouteThreat(npc, startNpc, targetNpc, targetLevel) &&
                DistanceSquaredToSegment(npc, startNpc, targetNpc) <= radiusSquared);
        }

        private static bool IsLikelyTargetRouteThreat(
            DynamicQuestSeedNpc npc,
            DynamicQuestSeedNpc startNpc,
            DynamicQuestSeedNpc targetNpc,
            int targetLevel)
        {
            return npc != null &&
                   startNpc != null &&
                   targetNpc != null &&
                   npc.RegionId == targetNpc.RegionId &&
                   !string.Equals(npc.InternalID, startNpc.InternalID, StringComparison.OrdinalIgnoreCase) &&
                   !string.Equals(npc.InternalID, targetNpc.InternalID, StringComparison.OrdinalIgnoreCase) &&
                   (!string.Equals(npc.Name, targetNpc.Name, StringComparison.OrdinalIgnoreCase) || IsStarterActiveGrowthThreat(npc)) &&
                   npc.HasSourceNpcMetadata &&
                   IsLikelyTemplateTargetAreaThreat(npc, targetNpc) &&
                   IsStarterDangerousActiveGrowthThreat(npc, Math.Max(targetLevel, StarterMaxSoloSafeTargetLevel));
        }

        private static bool IsSameNpc(DynamicQuestSeedNpc left, DynamicQuestSeedNpc right)
        {
            return left != null &&
                   right != null &&
                   !string.IsNullOrWhiteSpace(left.InternalID) &&
                   string.Equals(left.InternalID, right.InternalID, StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsLikelyTargetAreaThreat(
            DynamicQuestSeedNpc npc,
            DynamicQuestSeedNpc targetNpc,
            int targetLevel,
            DynamicQuestTemplate template)
        {
            bool starterBand = IsStarterSafetyConstrained(template);
            int threatLevelFloor = starterBand
                ? Math.Max(targetLevel, StarterMaxSoloSafeTargetLevel)
                : targetLevel;

            return npc != null &&
                   targetNpc != null &&
                   npc.RegionId == targetNpc.RegionId &&
                   !string.Equals(npc.InternalID, targetNpc.InternalID, StringComparison.OrdinalIgnoreCase) &&
                   IsLikelyTemplateTargetAreaThreat(npc, targetNpc) &&
                   (npc.Level > threatLevelFloor ||
                    (starterBand && IsStarterDangerousActiveGrowthThreat(npc, threatLevelFloor)) ||
                    (!starterBand && IsStarterGrowthThreat(npc)));
        }

        private static bool IsLikelyTemplateTargetAreaThreat(DynamicQuestSeedNpc npc, DynamicQuestSeedNpc targetNpc)
        {
            if (npc == null || targetNpc == null)
                return false;

            if (DynamicQuestSeedService.IsLikelyDynamicQuestStartNpc(npc))
                return false;

            if (!npc.HasSourceNpcMetadata)
                return true;

            return npc.SourceIsAlive &&
                   !npc.SourceFlags.HasFlag(GameNPC.eFlags.PEACE) &&
                   !npc.SourceFlags.HasFlag(GameNPC.eFlags.CANTTARGET);
        }

        private static bool IsStarterDangerousActiveGrowthThreat(DynamicQuestSeedNpc npc, int threatLevelFloor)
        {
            if (!IsStarterActiveGrowthThreat(npc))
                return false;

            int effectiveLevel = npc.GrowthEffectiveLevel > 0 ? npc.GrowthEffectiveLevel : npc.Level;
            return npc.GrowthIsMutant ||
                   npc.GrowthMutationPending ||
                   npc.GrowthPlayerKills > 0 ||
                   effectiveLevel > threatLevelFloor;
        }

        private static bool IsStarterActiveGrowthThreat(DynamicQuestSeedNpc npc)
        {
            if (npc == null)
                return false;

            string liveName = string.IsNullOrWhiteSpace(npc.RawName) ? npc.Name : npc.RawName;
            if (HasGrowthNamePrefix(liveName))
                return true;

            if (!npc.HasGrowthState)
                return false;

            if (npc.GrowthIsMutant || npc.GrowthMutationPending || npc.GrowthPlayerKills > 0 || npc.GrowthLevel > 0)
                return true;

            if (!string.IsNullOrWhiteSpace(npc.GrowthStage) &&
                !string.Equals(npc.GrowthStage, MobGrowthStages.Normal, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            return npc.GrowthEffectiveLevel > 5 || npc.GrowthScore >= 20;
        }

        private static bool IsLikelyWorldQuestTarget(DynamicQuestSeedNpc npc)
        {
            if (npc == null || string.IsNullOrWhiteSpace(npc.Name) || string.IsNullOrWhiteSpace(npc.InternalID))
                return false;

            if (npc.Level <= 0 || npc.Level >= 75)
                return false;

            if (!npc.HasSourceNpcMetadata)
                return true;

            return npc.SourceIsAlive &&
                   npc.SourceRealm == eRealm.None &&
                   !npc.SourceFlags.HasFlag(GameNPC.eFlags.PEACE) &&
                   !npc.SourceFlags.HasFlag(GameNPC.eFlags.CANTTARGET);
        }

        private static int TargetStartDistanceRank(DynamicQuestSeedNpc startNpc, DynamicQuestSeedNpc targetNpc)
        {
            if (startNpc == null || targetNpc == null)
                return 0;

            long distanceSquared = DistanceSquared(startNpc, targetNpc);
            long minimumSafeSquared = (long)NearStartMinimumSafeTargetDistance * NearStartMinimumSafeTargetDistance;
            return distanceSquared < minimumSafeSquared ? 1 : 0;
        }

        private sealed class DynamicQuestTargetPlan
        {
            public int Count { get; set; } = 1;
            public int ObjectiveMinLevel { get; set; } = 1;
            public int ObjectiveMaxLevel { get; set; } = 50;
        }

        private static DynamicQuestTargetPlan BuildTargetPlan(
            DynamicQuestTemplate template,
            DynamicQuestSeedNpc targetNpc,
            IList<DynamicQuestSeedNpc> npcs)
        {
            int requestedCount = EffectiveRequestedTargetCount(template);
            int requestedMinLevel = Math.Clamp(template.MinLevel, 1, 50);
            int requestedMaxLevel = Math.Clamp(Math.Max(template.MaxLevel, template.MinLevel), 1, 50);
            List<DynamicQuestSeedNpc> cluster = FindNearbyTargetCluster(template, targetNpc, npcs).ToList();
            if (cluster.Count == 0)
                cluster.Add(targetNpc);

            List<int> knownLevels = cluster
                .Where(npc => npc.Level > 0)
                .Select(npc => Math.Clamp(npc.Level, 1, 50))
                .ToList();

            int objectiveMinLevel = knownLevels.Count == 0 ? requestedMinLevel : knownLevels.Min();
            int objectiveMaxLevel = knownLevels.Count == 0 ? requestedMaxLevel : knownLevels.Max();

            return new DynamicQuestTargetPlan
            {
                Count = Math.Clamp(Math.Min(requestedCount, cluster.Count), 1, requestedCount),
                ObjectiveMinLevel = Math.Clamp(objectiveMinLevel, 1, 50),
                ObjectiveMaxLevel = Math.Clamp(Math.Max(objectiveMaxLevel, objectiveMinLevel), 1, 50)
            };
        }

        private static int EffectiveRequestedTargetCount(DynamicQuestTemplate template)
        {
            int requestedCount = Math.Max(1, template?.Count ?? 1);
            return template?.StartMode == DynamicQuestStartMode.AutoAccept
                ? 1
                : requestedCount;
        }

        private static IEnumerable<DynamicQuestSeedNpc> FindNearbyTargetCluster(
            DynamicQuestTemplate template,
            DynamicQuestSeedNpc targetNpc,
            IEnumerable<DynamicQuestSeedNpc> npcs)
        {
            if (targetNpc == null)
                return Array.Empty<DynamicQuestSeedNpc>();

            long radiusSquared = (long)TargetClusterRadius * TargetClusterRadius;
            int targetLevel = targetNpc.Level;
            int requestedMinLevel = Math.Clamp(template.MinLevel, 1, 50);
            int requestedMaxLevel = Math.Clamp(Math.Max(template.MaxLevel, template.MinLevel), 1, 50);

            return (npcs ?? Array.Empty<DynamicQuestSeedNpc>())
                .Where(IsUsableNpc)
                .Where(npc => npc.RegionId == targetNpc.RegionId)
                .Where(npc => string.Equals(npc.Name, targetNpc.Name, StringComparison.OrdinalIgnoreCase))
                .Where(npc => DistanceSquared(targetNpc, npc) <= radiusSquared)
                .Where(npc =>
                    npc.Level <= 0 ||
                    targetLevel <= 0 ||
                    (npc.Level >= requestedMinLevel && npc.Level <= requestedMaxLevel) ||
                    Math.Abs(npc.Level - targetLevel) <= TargetClusterLevelTolerance)
                .OrderBy(npc => DistanceSquared(targetNpc, npc))
                .ThenBy(npc => npc.InternalID, StringComparer.OrdinalIgnoreCase);
        }

        private static string BuildBindingKey(
            DynamicQuestTemplate template,
            DynamicQuestSeedNpc startNpc,
            DynamicQuestSeedNpc targetNpc,
            DynamicQuestTargetPlan targetPlan)
        {
            string raw = string.Join("|", new[]
            {
                template.TemplateId ?? string.Empty,
                ResolveWorldSignal(template),
                RequiresStartNpc(template) ? startNpc?.InternalID ?? string.Empty : "world",
                (startNpc?.RegionId ?? template.PreferredRegionId).ToString(),
                template.StartMode.ToString(),
                template.Trigger ?? string.Empty,
                targetNpc.InternalID ?? string.Empty,
                targetNpc.Name ?? string.Empty,
                targetNpc.RegionId.ToString(),
                targetNpc.X.ToString(),
                targetNpc.Y.ToString(),
                targetNpc.Z.ToString(),
                (targetPlan?.Count ?? Math.Max(1, template.Count)).ToString(),
                (targetPlan?.ObjectiveMinLevel ?? Math.Clamp(template.MinLevel, 1, 50)).ToString(),
                (targetPlan?.ObjectiveMaxLevel ?? Math.Clamp(Math.Max(template.MaxLevel, template.MinLevel), 1, 50)).ToString()
            }).ToLowerInvariant();
            byte[] hash = SHA256.HashData(Encoding.UTF8.GetBytes(raw));
            return Convert.ToHexString(hash).Substring(0, 16).ToLowerInvariant();
        }

        private static DynamicQuestDefinition BuildQuest(
            DynamicQuestTemplate template,
            DynamicQuestSeedNpc startNpc,
            DynamicQuestSeedNpc targetNpc,
            DynamicQuestTargetPlan targetPlan,
            string bindingKey)
        {
            string renderedTitle = RenderStoryText(template.Title, template, startNpc, targetNpc, targetPlan.Count);
            string renderedOffer = RenderStoryText(template.OfferText, template, startNpc, targetNpc, targetPlan.Count);
            string renderedProgress = RenderStoryText(template.ProgressText, template, startNpc, targetNpc, targetPlan.Count);
            string renderedFinish = RenderStoryText(template.FinishText, template, startNpc, targetNpc, targetPlan.Count);
            string renderedNarrativeJson = RenderStoryText(template.StoryNarrativeJson, template, startNpc, targetNpc, targetPlan.Count);
            string renderedPresentationJson = RenderStoryText(template.StoryPresentationJson, template, startNpc, targetNpc, targetPlan.Count);
            string title = string.IsNullOrWhiteSpace(template.Title)
                ? $"{targetNpc.Name} 위협"
                : renderedTitle.Trim();
            string offer = string.IsNullOrWhiteSpace(renderedOffer)
                ? template.StorySeed
                : renderedOffer;
            if (string.IsNullOrWhiteSpace(offer))
                offer = $"{targetNpc.Name} 위협을 확인해 주시겠습니까?";

            bool requiresStartNpc = RequiresStartNpc(template);
            ushort startRegionId = requiresStartNpc
                ? startNpc.RegionId
                : (template.PreferredRegionId > 0 ? template.PreferredRegionId : targetNpc.RegionId);

            return new DynamicQuestDefinition
            {
                Id = template.TemplateId,
                Title = title,
                OfferText = offer,
                ProgressText = string.IsNullOrWhiteSpace(renderedProgress)
                    ? $"{targetNpc.Name} 위협이 아직 남아 있습니다."
                    : renderedProgress,
                FinishText = string.IsNullOrWhiteSpace(renderedFinish)
                    ? "덕분에 이 지역이 조금 안전해졌습니다."
                    : renderedFinish,
                StoryNarrativeJson = renderedNarrativeJson,
                StoryPresentationJson = renderedPresentationJson,
                StartNpcInternalId = requiresStartNpc ? startNpc.InternalID ?? string.Empty : string.Empty,
                StartNpcName = requiresStartNpc ? startNpc.Name ?? string.Empty : string.Empty,
                StartRegionId = startRegionId,
                StartMode = template.StartMode,
                TargetName = targetNpc.Name ?? string.Empty,
                TargetCount = targetPlan.Count,
                MinLevel = Math.Clamp(template.MinLevel, 1, 50),
                MaxLevel = Math.Clamp(Math.Max(template.MaxLevel, template.MinLevel), 1, 50),
                StartNodeId = requiresStartNpc ? "talk" : "explore",
                Nodes = BuildGraph(template, startNpc, targetNpc, targetPlan, renderedOffer, renderedProgress, renderedFinish),
                Reward = new DynamicQuestRewardDefinition
                {
                    XpMultiplier = 1.0,
                    MoneyMultiplier = 1.0,
                    StepBonusMultiplier = 0.25,
                    PartyBonusMultiplier = 1.0
                },
                Tags = BuildTags(template, startNpc, targetNpc, bindingKey),
                BindingKey = bindingKey,
                WorldRevision = template.WorldRevision ?? string.Empty
            };
        }

        private static IList<string> BuildTags(
            DynamicQuestTemplate template,
            DynamicQuestSeedNpc startNpc,
            DynamicQuestSeedNpc targetNpc,
            string bindingKey)
        {
            ushort regionId = RequiresStartNpc(template)
                ? startNpc.RegionId
                : (template.PreferredRegionId > 0 ? template.PreferredRegionId : targetNpc.RegionId);

            List<string> tags = (template.Tags ?? Array.Empty<string>())
                .Where(tag => !IsRuntimeBindingTag(tag))
                .Where(tag => !IsWorldSignalTag(tag, out _))
                .ToList();
            string worldSignal = ResolveWorldSignal(template);

            tags.AddRange(new[]
            {
                $"template:{template.TemplateId}",
                $"binding:{bindingKey}",
                "dynamic-rebind",
                $"region:{regionId}",
                $"target:{targetNpc.Name}",
                $"start-mode:{template.StartMode}"
            });

            if (!string.IsNullOrWhiteSpace(template.Realm))
                tags.Add($"realm:{template.Realm}");

            if (ShouldIncludeTemplateTrigger(template, worldSignal))
                tags.Add($"trigger:{template.Trigger.Trim()}");

            if (!string.IsNullOrWhiteSpace(worldSignal))
                tags.Add($"world-signal:{worldSignal}");

            if (!string.IsNullOrWhiteSpace(template.StoryProvider))
                tags.Add($"llm-provider:{template.StoryProvider.Trim()}");

            if (!string.IsNullOrWhiteSpace(template.StoryModel))
                tags.Add($"llm-model:{template.StoryModel.Trim()}");

            if (template.StoryQualityScore > 0)
                tags.Add($"llm-score:{Math.Clamp(template.StoryQualityScore, 0, 100)}");

            return tags.Distinct(StringComparer.OrdinalIgnoreCase).ToList();
        }

        private static bool ShouldIncludeTemplateTrigger(DynamicQuestTemplate template, string worldSignal)
        {
            string trigger = (template?.Trigger ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(trigger))
                return false;

            bool itemAcquiredBranch = template.StartMode == DynamicQuestStartMode.AutoAccept &&
                                      trigger.StartsWith("item-acquired", StringComparison.OrdinalIgnoreCase) &&
                                      (worldSignal ?? string.Empty).Trim().StartsWith("item-acquired", StringComparison.OrdinalIgnoreCase);

            return !itemAcquiredBranch;
        }

        private static bool IsRuntimeBindingTag(string tag)
        {
            if (string.IsNullOrWhiteSpace(tag))
                return true;

            string[] runtimePrefixes =
            {
                "template:",
                "binding:",
                "region:",
                "target:",
                "start-mode:",
                "realm:",
                "trigger:",
                "llm-provider:",
                "llm-model:",
                "llm-score:"
            };

            return string.Equals(tag, "dynamic-rebind", StringComparison.OrdinalIgnoreCase) ||
                   runtimePrefixes.Any(prefix => tag.StartsWith(prefix, StringComparison.OrdinalIgnoreCase));
        }

        private static IList<DynamicQuestNode> BuildGraph(
            DynamicQuestTemplate template,
            DynamicQuestSeedNpc startNpc,
            DynamicQuestSeedNpc targetNpc,
            DynamicQuestTargetPlan targetPlan,
            string renderedOffer,
            string renderedProgress,
            string renderedFinish)
        {
            if (!RequiresStartNpc(template))
                return BuildWorldGraph(template, targetNpc, targetPlan, renderedProgress, renderedFinish);

            string worldSignal = ResolveWorldSignal(template);
            List<DynamicQuestNode> nodes = new()
            {
                new DynamicQuestNode
                {
                    Id = "talk",
                    Type = DynamicQuestNodeType.Talk,
                    Title = "부탁",
                    Text = renderedOffer,
                    Objective = new DynamicQuestObjective
                    {
                        NpcInternalId = startNpc.InternalID,
                        NpcName = startNpc.Name,
                        RegionId = startNpc.RegionId
                    },
                    Edges = new[] { new DynamicQuestEdge { ToNodeId = "explore", Condition = DynamicQuestEdgeCondition.ObjectiveComplete } }
                },
                new DynamicQuestNode
                {
                    Id = "explore",
                    Type = DynamicQuestNodeType.Explore,
                    Title = "흔적 조사",
                    Text = $"{targetNpc.Name} 흔적을 조사하세요.",
                    Objective = new DynamicQuestObjective
                    {
                        LocationName = $"{targetNpc.Name} 흔적",
                        RegionId = targetNpc.RegionId,
                        X = Math.Max(1, targetNpc.X),
                        Y = Math.Max(1, targetNpc.Y),
                        Z = Math.Max(0, targetNpc.Z),
                        Radius = 450
                    },
                    Edges = new[] { new DynamicQuestEdge { ToNodeId = "kill", Condition = DynamicQuestEdgeCondition.ObjectiveComplete } }
                },
                new DynamicQuestNode
                {
                    Id = "kill",
                    Type = DynamicQuestNodeType.Kill,
                    Title = "위협 제거",
                    Text = string.IsNullOrWhiteSpace(renderedProgress)
                        ? $"{targetNpc.Name} {targetPlan.Count}마리를 처치하세요."
                        : renderedProgress,
                    Objective = new DynamicQuestObjective
                    {
                        TargetName = targetNpc.Name,
                        TargetCount = targetPlan.Count,
                        MinLevel = targetPlan.ObjectiveMinLevel,
                        MaxLevel = targetPlan.ObjectiveMaxLevel,
                        RegionId = targetNpc.RegionId,
                        AllowGroupCredit = true
                    },
                    Edges = new[] { new DynamicQuestEdge { ToNodeId = "return", Condition = DynamicQuestEdgeCondition.ObjectiveComplete } }
                },
                new DynamicQuestNode
                {
                    Id = "return",
                    Type = DynamicQuestNodeType.ReturnToNpc,
                    Title = "보고",
                    Text = $"{startNpc.Name}에게 돌아가세요.",
                    Objective = new DynamicQuestObjective
                    {
                        NpcInternalId = startNpc.InternalID,
                        NpcName = startNpc.Name,
                        RegionId = startNpc.RegionId
                    },
                    Edges = new[] { new DynamicQuestEdge { ToNodeId = "choice", Condition = DynamicQuestEdgeCondition.ObjectiveComplete } }
                },
                new DynamicQuestNode
                {
                    Id = "choice",
                    Type = DynamicQuestNodeType.Choice,
                    Title = "결정",
                    Text = "이 일을 어떻게 마무리하시겠습니까?",
                    Objective = new DynamicQuestObjective
                    {
                        Choices = new[]
                        {
                            new DynamicQuestChoice { Id = "safe", Label = "지역 안전을 우선한다", Text = "지역 안전을 우선한다.", Consequence = "지역은 당장의 위협에서 벗어나지만, 남은 흔적은 다음 보고에 기록된다." },
                            new DynamicQuestChoice { Id = "followup", Label = "변화를 더 지켜본다", Text = "변화를 더 지켜본다.", Consequence = "불안한 징후를 방치하지 않고 다음 세계 신호를 기다리기로 했다." }
                        }
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "safe", Priority = 0 },
                        new DynamicQuestEdge
                        {
                            ToNodeId = string.IsNullOrWhiteSpace(worldSignal) ? "complete" : "observe_signal",
                            Condition = DynamicQuestEdgeCondition.ChoiceSelected,
                            ConditionValue = "followup",
                            Priority = 1
                        }
                    }
                }
            };

            if (!string.IsNullOrWhiteSpace(worldSignal))
                nodes.Add(BuildSignalObservationNode(targetNpc, worldSignal));

            nodes.Add(new DynamicQuestNode
            {
                Id = "complete",
                Type = DynamicQuestNodeType.Complete,
                Title = "완료",
                Text = renderedFinish
            });

            return nodes;
        }

        private static IList<DynamicQuestNode> BuildWorldGraph(
            DynamicQuestTemplate template,
            DynamicQuestSeedNpc targetNpc,
            DynamicQuestTargetPlan targetPlan,
            string renderedProgress,
            string renderedFinish)
        {
            string worldSignal = ResolveWorldSignal(template);
            List<DynamicQuestNode> nodes = new()
            {
                new DynamicQuestNode
                {
                    Id = "explore",
                    Type = DynamicQuestNodeType.Explore,
                    Title = "흔적 조사",
                    Text = $"{targetNpc.Name} 흔적을 조사하세요.",
                    Objective = new DynamicQuestObjective
                    {
                        LocationName = $"{targetNpc.Name} 흔적",
                        RegionId = targetNpc.RegionId,
                        X = Math.Max(1, targetNpc.X),
                        Y = Math.Max(1, targetNpc.Y),
                        Z = Math.Max(0, targetNpc.Z),
                        Radius = 450
                    },
                    Edges = new[] { new DynamicQuestEdge { ToNodeId = "kill", Condition = DynamicQuestEdgeCondition.ObjectiveComplete } }
                },
                new DynamicQuestNode
                {
                    Id = "kill",
                    Type = DynamicQuestNodeType.Kill,
                    Title = "위협 제거",
                    Text = string.IsNullOrWhiteSpace(renderedProgress)
                        ? $"{targetNpc.Name} {targetPlan.Count}마리를 처치하세요."
                        : renderedProgress,
                    Objective = new DynamicQuestObjective
                    {
                        TargetName = targetNpc.Name,
                        TargetCount = targetPlan.Count,
                        MinLevel = targetPlan.ObjectiveMinLevel,
                        MaxLevel = targetPlan.ObjectiveMaxLevel,
                        RegionId = targetNpc.RegionId,
                        AllowGroupCredit = true
                    },
                    Edges = new[]
                    {
                        new DynamicQuestEdge
                        {
                            ToNodeId = string.IsNullOrWhiteSpace(worldSignal) ? "complete" : "choice",
                            Condition = DynamicQuestEdgeCondition.ObjectiveComplete
                        }
                    }
                }
            };

            if (!string.IsNullOrWhiteSpace(worldSignal))
            {
                nodes.Add(BuildSignalChoiceNode(worldSignal));
                nodes.Add(BuildSignalObservationNode(targetNpc, worldSignal));
            }

            nodes.Add(new DynamicQuestNode
            {
                Id = "complete",
                Type = DynamicQuestNodeType.Complete,
                Title = "완료",
                Text = string.IsNullOrWhiteSpace(renderedFinish)
                    ? "덕분에 이 지역이 조금 안전해졌습니다."
                    : renderedFinish
            });

            return nodes;
        }

        private static DynamicQuestNode BuildSignalChoiceNode(string worldSignal)
        {
            return new DynamicQuestNode
            {
                Id = "choice",
                Type = DynamicQuestNodeType.Choice,
                Title = "결정",
                Text = "이 일을 어떻게 마무리하시겠습니까?",
                Objective = new DynamicQuestObjective
                {
                    Choices = new[]
                    {
                        new DynamicQuestChoice { Id = "safe", Label = "지역 안전을 우선한다", Text = "지역 안전을 우선한다.", Consequence = "성장한 위협을 지금 끊어내며 지역의 즉각적인 피해를 줄인다." },
                        new DynamicQuestChoice { Id = "followup", Label = "성장한 위협을 더 추적한다", Text = "성장한 위협을 더 추적한다.", Consequence = "성장한 위협의 근원을 추적하기로 하며 다음 성장 신호를 기다린다." }
                    }
                },
                Edges = new[]
                {
                    new DynamicQuestEdge { ToNodeId = "complete", Condition = DynamicQuestEdgeCondition.ChoiceSelected, ConditionValue = "safe", Priority = 0 },
                    new DynamicQuestEdge
                    {
                        ToNodeId = string.IsNullOrWhiteSpace(worldSignal) ? "complete" : "observe_signal",
                        Condition = DynamicQuestEdgeCondition.ChoiceSelected,
                        ConditionValue = "followup",
                        Priority = 1
                    }
                }
            };
        }

        private static DynamicQuestNode BuildSignalObservationNode(DynamicQuestSeedNpc targetNpc, string worldSignal)
        {
            return new DynamicQuestNode
            {
                Id = "observe_signal",
                Type = DynamicQuestNodeType.Explore,
                Title = "변화 관측",
                Text = $"{targetNpc.Name} 주변에서 성장한 위협의 움직임을 지켜보세요.",
                Objective = new DynamicQuestObjective
                {
                    LocationName = $"{targetNpc.Name} 성장 징후",
                    RegionId = targetNpc.RegionId,
                    X = Math.Max(1, targetNpc.X),
                    Y = Math.Max(1, targetNpc.Y),
                    Z = Math.Max(0, targetNpc.Z),
                    Radius = 650
                },
                Edges = new[]
                {
                    new DynamicQuestEdge
                    {
                        ToNodeId = "complete",
                        Condition = DynamicQuestEdgeCondition.WorldSignal,
                        ConditionValue = worldSignal,
                        Priority = 0
                    },
                    new DynamicQuestEdge
                    {
                        ToNodeId = "complete",
                        Condition = DynamicQuestEdgeCondition.TimedOut,
                        ConditionValue = DynamicQuestWorldSignalPolicy.FallbackTimeoutSeconds,
                        Priority = 1
                    }
                }
            };
        }

        private static string ResolveWorldSignal(DynamicQuestTemplate template)
        {
            foreach (string tag in template?.Tags ?? Array.Empty<string>())
            {
                if (!IsWorldSignalTag(tag, out string signal))
                    continue;

                if (DynamicQuestWorldSignalPolicy.IsAllowed(signal))
                    return signal.Trim().ToLowerInvariant();
            }

            return string.Empty;
        }

        private static bool IsWorldSignalTag(string tag, out string signal)
        {
            signal = string.Empty;
            string value = (tag ?? string.Empty).Trim();
            const string prefix = "world-signal:";
            if (!value.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                return false;

            signal = value.Substring(prefix.Length).Trim();
            return true;
        }

        private static string RenderStoryText(
            string text,
            DynamicQuestTemplate template,
            DynamicQuestSeedNpc startNpc,
            DynamicQuestSeedNpc targetNpc,
            int count)
        {
            string value = text ?? string.Empty;
            if (value.Length == 0)
                return string.Empty;

            value = value.Replace("{{target}}", targetNpc?.Name ?? string.Empty, StringComparison.OrdinalIgnoreCase);
            value = value.Replace("{{start_npc}}", startNpc?.Name ?? template?.PreferredStartNpcName ?? string.Empty, StringComparison.OrdinalIgnoreCase);
            value = value.Replace("{{realm}}", template?.Realm ?? string.Empty, StringComparison.OrdinalIgnoreCase);
            value = value.Replace("{{count}}", Math.Max(1, count).ToString(), StringComparison.OrdinalIgnoreCase);
            return LanguageMgr.ApplyKoreanParticles(value).Trim();
        }

        private static bool RequiresStartNpc(DynamicQuestTemplate template)
        {
            return template == null || template.StartMode == DynamicQuestStartMode.NpcOffer;
        }

        private static DynamicQuestStartMode ParseStartMode(string value)
        {
            return Enum.TryParse(value, true, out DynamicQuestStartMode parsed)
                ? parsed
                : DynamicQuestStartMode.NpcOffer;
        }
    }

    public sealed class DatabaseDynamicQuestTemplateRepository : IDynamicQuestTemplateRepository
    {
        private static readonly Logging.Logger Log = Logging.LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);

        public bool Add(DbDynamicQuestTemplate row)
        {
            if (row == null || string.IsNullOrWhiteSpace(row.TemplateId))
                return false;

            try
            {
                return GameServer.Database?.AddObject(row) ?? false;
            }
            catch (Exception e)
            {
                if (Log.IsWarnEnabled)
                    Log.Warn($"Dynamic quest template add failed: {row.TemplateId}", e);
                return false;
            }
        }

        public DbDynamicQuestTemplate Find(string templateId)
        {
            if (string.IsNullOrWhiteSpace(templateId))
                return null;

            try
            {
                return GameServer.Database?.FindObjectByKey<DbDynamicQuestTemplate>(templateId);
            }
            catch (Exception e)
            {
                if (Log.IsWarnEnabled)
                    Log.Warn($"Dynamic quest template find failed: {templateId}", e);
                return null;
            }
        }

        public IList<DbDynamicQuestTemplate> GetActive()
        {
            try
            {
                return GameServer.Database?.SelectAllObjects<DbDynamicQuestTemplate>()
                    .Where(row => row.IsActive)
                    .OrderBy(row => row.CreatedAt)
                    .ToList() ?? new List<DbDynamicQuestTemplate>();
            }
            catch (Exception e)
            {
                if (Log.IsWarnEnabled)
                    Log.Warn("Dynamic quest template load failed.", e);
                return Array.Empty<DbDynamicQuestTemplate>();
            }
        }

        public bool Save(DbDynamicQuestTemplate row)
        {
            if (row == null || string.IsNullOrWhiteSpace(row.TemplateId))
                return false;

            try
            {
                return GameServer.Database?.SaveObject(row) ?? false;
            }
            catch (Exception e)
            {
                if (Log.IsWarnEnabled)
                    Log.Warn($"Dynamic quest template save failed: {row.TemplateId}", e);
                return false;
            }
        }
    }
}
