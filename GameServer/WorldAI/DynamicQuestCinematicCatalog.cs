using System;
using System.Collections.Generic;
using System.Linq;
using DOL.Database;

namespace DOL.GS.WorldAI
{
    internal sealed class DynamicQuestCinematicModelEntry
    {
        public ushort Model { get; init; }
        public string Label { get; init; } = string.Empty;
        public string Source { get; init; } = string.Empty;
        public string Category { get; init; } = string.Empty;
        public string[] Tags { get; init; } = Array.Empty<string>();
    }

    internal static class DynamicQuestCinematicCatalog
    {
        private static readonly object CatalogLock = new();
        private static readonly TimeSpan CatalogCacheTtl = TimeSpan.FromMinutes(5);
        private static DynamicQuestCinematicModelEntry[] s_propCatalogCache;
        private static DynamicQuestCinematicModelEntry[] s_npcCatalogCache;
        private static DateTime s_propCatalogCachedAtUtc = DateTime.MinValue;
        private static DateTime s_npcCatalogCachedAtUtc = DateTime.MinValue;

        internal static readonly DynamicQuestCinematicModelEntry[] PropModels =
        {
            new() { Model = 488, Label = "sealed pouch / path marker", Tags = new[] { "clue", "trace", "evidence", "path", "sign", "default", "선택", "흔적", "증거", "표식" } },
            new() { Model = 500, Label = "tome", Tags = new[] { "book", "record", "journal", "ritual", "magic", "rune", "룬", "기록", "책", "의식" } },
            new() { Model = 601, Label = "ball of flame", Tags = new[] { "fire", "flame", "ash", "campfire", "omen", "threat", "불", "불씨", "위협", "징후" } },
            new() { Model = 624, Label = "stone pendant", Tags = new[] { "stone", "pendant", "relic", "ring", "standing", "고리석", "돌", "성물", "펜던트" } },
            new() { Model = 101, Label = "quest pendant", Tags = new[] { "pendant", "small relic", "holy", "abbey", "성물", "수도원", "목걸이" } },
            new() { Model = 104, Label = "totem", Tags = new[] { "totem", "bone", "tribal", "midgard", "rune", "뼛조각", "토템", "룬" } },
            new() { Model = 1635, Label = "arrow bundle", Tags = new[] { "arrow", "weapon", "battle", "broken arrow", "combat", "화살", "전투", "무기" } },
            new() { Model = 485, Label = "glowing orb", Tags = new[] { "orb", "signal", "world signal", "magic", "choice", "신호", "마법", "선택" } }
        };

        internal static readonly DynamicQuestCinematicModelEntry[] NpcModels =
        {
            new() { Model = 39, Label = "Albion trainer / town defender", Category = "defender", Tags = new[] { "albion", "trainer", "guard", "defender", "church", "abbey", "human", "startnpc", "알비온", "수도원", "경비" } },
            new() { Model = 61, Label = "Albion soldier / logistics guard", Category = "fighter", Tags = new[] { "albion", "soldier", "guard", "logistics", "frontier", "battle", "human", "알비온", "전투", "병사" } },
            new() { Model = 153, Label = "Midgard trainer / rune defender", Category = "ritualist", Tags = new[] { "midgard", "trainer", "rune", "seer", "defender", "human", "미드가드", "룬", "수호" } },
            new() { Model = 230, Label = "Midgard village witness", Category = "witness", Tags = new[] { "midgard", "villager", "witness", "elder", "settlement", "human", "미드가드", "증인", "마을" } },
            new() { Model = 302, Label = "Hibernia trainer / grove defender", Category = "defender", Tags = new[] { "hibernia", "trainer", "grove", "nature", "defender", "human", "하이버니아", "숲", "수호" } },
            new() { Model = 342, Label = "Hibernia field guide", Category = "scout", Tags = new[] { "hibernia", "guide", "scout", "path", "field", "human", "하이버니아", "정찰", "길" } },
            new() { Model = 902, Label = "spectral threat witness", Category = "threat", Tags = new[] { "spectre", "death", "threat", "omen", "enemy", "shadow", "ghost", "위협", "망령", "그림자" } },
            new() { Model = 1198, Label = "armed companion", Category = "fighter", Tags = new[] { "companion", "ally", "escort", "defense", "guard", "battle", "human", "동료", "호위", "방어" } }
        };

        internal static ushort ResolvePropModel(DynamicQuestDefinition quest, DynamicQuestNode node, string trigger, string extraContext)
        {
            return ResolveModel(GetPropCatalog(), quest, node, trigger, extraContext, ScorePropNodeBonus);
        }

        internal static ushort ResolveNpcModel(DynamicQuestDefinition quest, DynamicQuestNode node, string trigger, string extraContext)
        {
            return ResolveModel(GetNpcCatalog(), quest, node, trigger, extraContext, ScoreNpcNodeBonus);
        }

        internal static string ResolveNpcCategoryForModel(ushort model)
        {
            if (model == 0)
                return string.Empty;

            DynamicQuestCinematicModelEntry entry = GetNpcCatalog()
                .FirstOrDefault(item => item != null && item.Model == model);
            return entry?.Category ?? string.Empty;
        }

        internal static string DescribeCatalogForPrompt()
        {
            string props = string.Join(", ", OrderCatalogForPrompt(GetPropCatalog(), "default_prop").Take(80).Select(entry => $"{entry.Model}:{entry.Label}:{entry.Category}"));
            string npcs = string.Join(", ", OrderCatalogForPrompt(GetNpcCatalog(), "default_npc").Take(80).Select(entry => $"{entry.Model}:{entry.Label}:{entry.Category}"));
            return $"Available cinematic prop model catalog is built from current world/DB objects plus defaults; examples use model:label:category format: {props}. Prop category intent: clue means tracks/evidence/path markers, record means tomes/journals/written warnings, relic means ritual stones/pendants/totems/realm symbols, flame means torches/campfires/omens/fresh danger, weapon means arrows/broken weapons/combat aftermath, structure means doors/gates/portals/keeps/relic pads. Available cinematic NPC model catalog is built from current world/DB NPCs plus defaults; examples use model:label:category format: {npcs}. NPC role category intent: defender means guards and shield lines, fighter means battle actors and armed companions, scout means guides/lookouts/retreating observers, witness means civilians and testimony, threat means spectral or hostile pressure, ritualist means rune/ritual/seer actors. Use presentation text that can be staged with guards, scouts, witnesses, spectral threats, movement, defense, props, clues, records, relics, flames, weapons, paths, structures, and standoffs instead of only static emotes.";
        }

        internal static DynamicQuestCinematicModelEntry[] BuildNpcCatalogForTest()
        {
            return GetNpcCatalog();
        }

        internal static DynamicQuestCinematicModelEntry[] BuildPropCatalogSnapshot()
        {
            return GetPropCatalog();
        }

        internal static DynamicQuestCinematicModelEntry[] BuildNpcCatalogSnapshot()
        {
            return GetNpcCatalog();
        }

        internal static DynamicQuestCinematicModelEntry[] BuildPropCatalogForTest()
        {
            return GetPropCatalog();
        }

        internal static void ClearCacheForTest()
        {
            lock (CatalogLock)
            {
                s_propCatalogCache = null;
                s_npcCatalogCache = null;
                s_propCatalogCachedAtUtc = DateTime.MinValue;
                s_npcCatalogCachedAtUtc = DateTime.MinValue;
            }
        }

        private static DynamicQuestCinematicModelEntry[] GetPropCatalog()
        {
            DateTime now = DateTime.UtcNow;
            lock (CatalogLock)
            {
                if (s_propCatalogCache != null && now - s_propCatalogCachedAtUtc < CatalogCacheTtl)
                    return s_propCatalogCache;

                s_propCatalogCache = BuildPropCatalog();
                s_propCatalogCachedAtUtc = now;
                return s_propCatalogCache;
            }
        }

        private static DynamicQuestCinematicModelEntry[] GetNpcCatalog()
        {
            DateTime now = DateTime.UtcNow;
            lock (CatalogLock)
            {
                if (s_npcCatalogCache != null && now - s_npcCatalogCachedAtUtc < CatalogCacheTtl)
                    return s_npcCatalogCache;

                s_npcCatalogCache = BuildNpcCatalog();
                s_npcCatalogCachedAtUtc = now;
                return s_npcCatalogCache;
            }
        }

        private static DynamicQuestCinematicModelEntry[] BuildPropCatalog()
        {
            Dictionary<ushort, List<string>> tagsByModel = new();
            foreach (DynamicQuestCinematicModelEntry entry in PropModels)
                AddCatalogEntry(tagsByModel, entry.Model, entry.Label, entry.Tags, "default_prop", GuessPropCategory(entry.Label, entry.Tags));

            try
            {
                foreach (Region region in WorldMgr.GetAllRegions())
                {
                    if (region == null)
                        continue;

                    foreach (GameStaticItem item in region.Objects.OfType<GameStaticItem>())
                    {
                        if (item == null || item.Model == 0)
                            continue;

                        AddCatalogEntry(
                            tagsByModel,
                            item.Model,
                            item.Name,
                            new[]
                            {
                                item.Name,
                                item.GetType().Name,
                                item.Realm.ToString(),
                                item.CurrentRegionID.ToString()
                            },
                            "world_object",
                            GuessPropCategory(item.Name, new[] { item.GetType().Name }));
                    }
                }
            }
            catch
            {
            }

            try
            {
                foreach (DbWorldObject item in GameServer.Database.SelectAllObjects<DbWorldObject>() ?? Array.Empty<DbWorldObject>())
                {
                    if (item == null || item.Model == 0)
                        continue;

                    AddCatalogEntry(
                        tagsByModel,
                        item.Model,
                        item.Name,
                        new[]
                        {
                            item.Name,
                            item.ClassType,
                            item.TranslationId,
                            RealmName(item.Realm),
                            item.Region.ToString()
                        },
                        "db_world_object",
                        GuessPropCategory(item.Name, new[] { item.ClassType, item.TranslationId }));
                }
            }
            catch
            {
            }

            return ToCatalogEntries(tagsByModel, "object model");
        }

        private static DynamicQuestCinematicModelEntry[] BuildNpcCatalog()
        {
            Dictionary<ushort, List<string>> tagsByModel = new();
            foreach (DynamicQuestCinematicModelEntry entry in NpcModels)
                AddCatalogEntry(
                    tagsByModel,
                    entry.Model,
                    entry.Label,
                    entry.Tags,
                    "default_npc",
                    string.IsNullOrWhiteSpace(entry.Category)
                        ? GuessNpcCategory(entry.Label, entry.Tags)
                        : entry.Category);

            try
            {
                foreach (Region region in WorldMgr.GetAllRegions())
                {
                    if (region == null)
                        continue;

                    foreach (GameNPC npc in region.Objects.OfType<GameNPC>())
                    {
                        if (npc == null || npc.Model == 0)
                            continue;

                        AddCatalogEntry(
                            tagsByModel,
                            npc.Model,
                            $"{npc.Name} / {npc.GuildName}".Trim(' ', '/'),
                            new[]
                            {
                                npc.Name,
                                npc.GuildName,
                                npc.Realm.ToString(),
                                npc.CurrentRegionID.ToString()
                            },
                            "world_npc",
                            GuessNpcCategory(npc.Name, new[] { npc.GuildName }));
                    }
                }
            }
            catch
            {
            }

            try
            {
                foreach (DbMob mob in GameServer.Database.SelectAllObjects<DbMob>() ?? Array.Empty<DbMob>())
                {
                    if (mob == null || mob.Model == 0)
                        continue;

                        AddCatalogEntry(
                            tagsByModel,
                            mob.Model,
                            $"{mob.Name} / {mob.Guild}".Trim(' ', '/'),
                        new[]
                        {
                            mob.Name,
                            mob.Guild,
                            RealmName(mob.Realm),
                            mob.Region.ToString()
                        },
                        "db_mob",
                        GuessNpcCategory(mob.Name, new[] { mob.Guild, RealmName(mob.Realm) }));
                }
            }
            catch
            {
            }

            return ToCatalogEntries(tagsByModel, "npc model");
        }

        private static DynamicQuestCinematicModelEntry[] ToCatalogEntries(Dictionary<ushort, List<string>> tagsByModel, string fallbackLabelPrefix)
        {
            return tagsByModel
                .Select(pair => new DynamicQuestCinematicModelEntry
                {
                    Model = pair.Key,
                    Label = pair.Value.FirstOrDefault() ?? $"{fallbackLabelPrefix} {pair.Key}",
                    Source = ResolveCatalogSource(pair.Value),
                    Category = ResolveCatalogCategory(pair.Value),
                    Tags = pair.Value
                        .Where(value => !string.IsNullOrWhiteSpace(value))
                        .Distinct(StringComparer.OrdinalIgnoreCase)
                        .Take(48)
                        .ToArray()
                })
                .OrderBy(entry => entry.Model)
                .ToArray();
        }

        private static IEnumerable<DynamicQuestCinematicModelEntry> OrderCatalogForPrompt(
            IEnumerable<DynamicQuestCinematicModelEntry> entries,
            string defaultSource)
        {
            return (entries ?? Array.Empty<DynamicQuestCinematicModelEntry>())
                .OrderByDescending(entry => string.Equals(entry?.Source, defaultSource, StringComparison.OrdinalIgnoreCase))
                .ThenBy(entry => entry?.Category ?? string.Empty, StringComparer.OrdinalIgnoreCase)
                .ThenBy(entry => entry?.Model ?? 0);
        }

        private static void AddCatalogEntry(
            Dictionary<ushort, List<string>> tagsByModel,
            ushort model,
            string label,
            IEnumerable<string> tags,
            string source = "",
            string category = "")
        {
            if (model == 0)
                return;

            if (!tagsByModel.TryGetValue(model, out List<string> values))
            {
                values = new List<string>();
                tagsByModel[model] = values;
            }

            AddTag(values, label);
            AddTag(values, string.IsNullOrWhiteSpace(source) ? string.Empty : $"source:{source}");
            AddTag(values, string.IsNullOrWhiteSpace(category) ? string.Empty : $"category:{category}");
            foreach (string tag in tags ?? Array.Empty<string>())
                AddTag(values, tag);
        }

        private static string ResolveCatalogSource(IEnumerable<string> values)
        {
            return ResolvePrefixedTag(values, "source:") ?? string.Empty;
        }

        private static string ResolveCatalogCategory(IEnumerable<string> values)
        {
            return ResolvePrefixedTag(values, "category:") ?? string.Empty;
        }

        private static string ResolvePrefixedTag(IEnumerable<string> values, string prefix)
        {
            foreach (string value in values ?? Array.Empty<string>())
            {
                string tag = (value ?? string.Empty).Trim();
                if (tag.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                    return tag.Substring(prefix.Length).Trim();
            }

            return null;
        }

        private static string GuessPropCategory(string label, IEnumerable<string> tags)
        {
            string text = string.Join(" ", new[] { label }.Concat(tags ?? Array.Empty<string>())).ToLowerInvariant();
            if (ContainsAny(text, "book", "tome", "record", "journal", "scroll", "책", "기록"))
                return "record";
            if (ContainsAny(text, "flame", "fire", "campfire", "torch", "불", "불씨", "횃불"))
                return "flame";
            if (ContainsAny(text, "grave", "stone", "relic", "pendant", "totem", "orb", "rune", "성물", "묘", "돌", "룬", "토템"))
                return "relic";
            if (ContainsAny(text, "arrow", "sword", "dirk", "axe", "bow", "staff", "shield", "weapon", "무기", "화살", "검", "도끼"))
                return "weapon";
            if (ContainsAny(text, "pouch", "marker", "sign", "path", "trace", "clue", "evidence", "흔적", "증거", "표식"))
                return "clue";
            if (ContainsAny(text, "door", "gate", "portal", "teleport", "keep", "relic pad"))
                return "structure";

            return "object";
        }

        private static string GuessNpcCategory(string label, IEnumerable<string> tags)
        {
            string text = string.Join(" ", new[] { label }.Concat(tags ?? Array.Empty<string>())).ToLowerInvariant();
            if (ContainsAny(text, "scout", "lookout", "guide", "path", "field", "retreat", "정찰", "길", "후퇴"))
                return "scout";
            if (ContainsAny(text, "witness", "villager", "elder", "civilian", "testimony", "증인", "목격", "마을"))
                return "witness";
            if (ContainsAny(text, "spectre", "spectral", "death", "threat", "enemy", "shadow", "ghost", "omen", "위협", "망령", "그림자"))
                return "threat";
            if (ContainsAny(text, "rune", "seer", "ritual", "totem", "magic", "relic", "룬", "의식", "토템", "성물"))
                return "ritualist";
            if (ContainsAny(text, "soldier", "fighter", "armed", "battle", "combat", "ambush", "strike", "병사", "전투", "무장"))
                return "fighter";
            if (ContainsAny(text, "guard", "defender", "trainer", "companion", "escort", "defense", "shield", "경비", "수호", "호위", "방어"))
                return "defender";

            return "npc";
        }

        private static bool ContainsAny(string text, params string[] terms)
        {
            if (string.IsNullOrWhiteSpace(text))
                return false;

            return terms.Any(term => !string.IsNullOrWhiteSpace(term) && text.Contains(term, StringComparison.OrdinalIgnoreCase));
        }

        private static void AddTag(List<string> values, string tag)
        {
            string value = (tag ?? string.Empty).Trim();
            if (value.Length == 0)
                return;

            values.Add(value);
            foreach (string part in value.Split(new[] { ' ', '/', '-', '_', '.', ',', ':', ';', '[', ']', '(', ')' }, StringSplitOptions.RemoveEmptyEntries))
            {
                if (part.Length > 1)
                    values.Add(part);
            }
        }

        private static string RealmName(byte realm)
        {
            return realm switch
            {
                1 => "Albion",
                2 => "Midgard",
                3 => "Hibernia",
                _ => string.Empty
            };
        }

        private static ushort ResolveModel(
            DynamicQuestCinematicModelEntry[] catalog,
            DynamicQuestDefinition quest,
            DynamicQuestNode node,
            string trigger,
            string extraContext,
            Func<DynamicQuestCinematicModelEntry, DynamicQuestNode, int> nodeBonus)
        {
            if (catalog == null || catalog.Length == 0)
                return 0;

            string context = BuildContext(quest, node, trigger, extraContext);
            DynamicQuestCinematicModelEntry best = catalog[0];
            int bestScore = int.MinValue;
            string roleIntentContext = BuildRoleIntentContext(node, trigger, extraContext);
            string roleIntentCategory = ResolveNpcRoleIntentCategory(roleIntentContext);
            IEnumerable<DynamicQuestCinematicModelEntry> candidates = catalog;
            if (!string.IsNullOrWhiteSpace(roleIntentCategory) &&
                catalog.Any(entry => string.Equals(entry?.Category, roleIntentCategory, StringComparison.OrdinalIgnoreCase)))
            {
                candidates = catalog.Where(entry => string.Equals(entry?.Category, roleIntentCategory, StringComparison.OrdinalIgnoreCase));
            }

            foreach (DynamicQuestCinematicModelEntry entry in candidates)
            {
                int score = nodeBonus?.Invoke(entry, node) ?? 0;
                score += ScoreContextCategoryBonus(entry, context);
                foreach (string tag in entry.Tags ?? Array.Empty<string>())
                {
                    string normalizedTag = (tag ?? string.Empty).Trim().ToLowerInvariant();
                    if (normalizedTag.Length == 0)
                        continue;

                    if (context.Contains(normalizedTag, StringComparison.OrdinalIgnoreCase))
                        score += normalizedTag.Length <= 3 ? 2 : 3;
                }

                if (score > bestScore)
                {
                    best = entry;
                    bestScore = score;
                }
            }

            return best.Model;
        }

        private static int ScoreContextCategoryBonus(DynamicQuestCinematicModelEntry entry, string context)
        {
            string category = (entry?.Category ?? string.Empty).Trim().ToLowerInvariant();
            if (string.IsNullOrWhiteSpace(category) || string.IsNullOrWhiteSpace(context))
                return 0;

            int score = 0;
            string roleIntentCategory = ResolveNpcRoleIntentCategory(context);
            if (!string.IsNullOrWhiteSpace(roleIntentCategory) && IsNpcCategory(category))
                score += string.Equals(category, roleIntentCategory, StringComparison.OrdinalIgnoreCase) ? 128 : -64;

            score += category switch
            {
                "record" when ContainsAny(context, "record", "journal", "tome", "book", "written", "기록", "책", "문서") => 16,
                "relic" when ContainsAny(context, "relic", "rune", "totem", "pendant", "ritual", "성물", "룬", "토템", "의식") => 16,
                "flame" when ContainsAny(context, "flame", "fire", "torch", "campfire", "omen", "불", "불씨", "횃불") => 16,
                "weapon" when ContainsAny(context, "weapon", "arrow", "battle", "combat", "무기", "화살", "전투") => 16,
                "structure" when ContainsAny(context, "structure", "gate", "portal", "keep", "door", "관문", "문", "성채") => 16,
                "clue" when ContainsAny(context, "clue", "trace", "evidence", "marker", "path", "흔적", "증거", "표식") => 4,
                "defender" when ContainsAny(context, "defender", "defense", "guard", "intercept", "shield", "hold", "line", "수호", "경비", "방어") => 16,
                "fighter" when ContainsAny(context, "fighter", "soldier", "battle", "combat", "ambush", "strike", "armed", "전투", "병사") => 16,
                "scout" when ContainsAny(context, "scout", "lookout", "guide", "retreat", "runner", "정찰", "후퇴") => 16,
                "witness" when ContainsAny(context, "witness", "villager", "civilian", "testimony", "contract", "증인", "목격", "마을") => 16,
                "threat" when ContainsAny(context, "threat", "spectral", "spectre", "shadow", "ghost", "enemy", "omen", "위협", "망령", "그림자") => 16,
                "ritualist" when ContainsAny(context, "ritual", "rune", "seer", "totem", "relic", "magic", "의식", "룬", "토템", "성물") => 16,
                _ => 0
            };

            return score;
        }

        private static string ResolveNpcRoleIntentCategory(string context)
        {
            if (string.IsNullOrWhiteSpace(context))
                return string.Empty;

            if (ContainsAny(context, "witness_point"))
                return "witness";
            if (ContainsAny(context, "scout_retreat", "lookout", "scout", "retreat", "runner", "정찰", "후퇴"))
                return "scout";
            if (ContainsAny(context, "ritual_interrupt", "ritual", "rune", "oath_knot", "totem", "seer", "의식", "룬"))
                return "ritualist";
            if (ContainsAny(context, "ambush_reveal", "combat_stance", "ambush", "combat", "battle", "strike", "flank", "soldier", "fighter", "전투", "매복"))
                return "fighter";
            if (ContainsAny(context, "defender_intercept", "guard_advance", "hold_ground", "shield", "intercept", "block", "screen", "escort", "defend", "방패", "방어"))
                return "defender";
            if (ContainsAny(context, "threat_standoff", "threat", "spectral", "shadow", "ghost", "enemy", "omen", "위협", "그림자"))
                return "threat";
            if (ContainsAny(context, "witness", "testimony", "civilian", "villager", "목격", "증인"))
                return "witness";

            return string.Empty;
        }

        private static bool IsNpcCategory(string category)
        {
            return category switch
            {
                "defender" or "fighter" or "scout" or "witness" or "threat" or "ritualist" or "npc" => true,
                _ => false
            };
        }

        private static int ScorePropNodeBonus(DynamicQuestCinematicModelEntry entry, DynamicQuestNode node)
        {
            int score = HasTag(entry, "default") ? 4 : 0;
            if (string.Equals(entry?.Source, "default_prop", StringComparison.OrdinalIgnoreCase))
                score += 2;

            score += node?.Type switch
            {
                DynamicQuestNodeType.Kill when entry.Model is 1635 or 601 => 4,
                DynamicQuestNodeType.Explore when entry.Model is 488 or 624 or 500 => 3,
                DynamicQuestNodeType.Choice when entry.Model is 485 or 488 => 4,
                DynamicQuestNodeType.Complete when entry.Model is 485 or 101 => 2,
                _ => 0
            };

            if (node?.Type == DynamicQuestNodeType.Kill &&
                string.Equals(entry?.Category, "weapon", StringComparison.OrdinalIgnoreCase))
                score += 1;

            return score;
        }

        private static bool HasTag(DynamicQuestCinematicModelEntry entry, string tag)
        {
            return (entry?.Tags ?? Array.Empty<string>())
                .Any(value => string.Equals(value, tag, StringComparison.OrdinalIgnoreCase));
        }

        private static int ScoreNpcNodeBonus(DynamicQuestCinematicModelEntry entry, DynamicQuestNode node)
        {
            return node?.Type switch
            {
                DynamicQuestNodeType.Kill when entry.Model is 61 or 1198 or 902 => 4,
                DynamicQuestNodeType.Explore when entry.Model is 342 or 230 => 3,
                DynamicQuestNodeType.Choice when entry.Model is 1198 or 39 or 153 or 302 => 3,
                DynamicQuestNodeType.ReturnToNpc when entry.Model is 39 or 153 or 302 => 2,
                _ => 0
            };
        }

        private static string BuildContext(DynamicQuestDefinition quest, DynamicQuestNode node, string trigger, string extraContext)
        {
            DynamicQuestObjective objective = node?.Objective;
            return string.Join(" ", new[]
            {
                trigger,
                extraContext,
                node?.Type.ToString(),
                node?.Id,
                node?.Title,
                node?.Text,
                objective?.TargetName,
                objective?.LocationName,
                objective?.NpcName,
                quest?.Title,
                quest?.OfferText,
                quest?.ProgressText,
                quest?.FinishText,
                quest?.TargetName,
                quest?.Realm,
                string.Join(" ", quest?.Tags ?? Array.Empty<string>())
            }.Where(value => !string.IsNullOrWhiteSpace(value))).ToLowerInvariant();
        }

        private static string BuildRoleIntentContext(DynamicQuestNode node, string trigger, string extraContext)
        {
            return string.Join(" ", new[]
            {
                trigger,
                extraContext,
                node?.Type.ToString(),
                node?.Id,
                node?.Title
            }.Where(value => !string.IsNullOrWhiteSpace(value))).ToLowerInvariant();
        }
    }
}
