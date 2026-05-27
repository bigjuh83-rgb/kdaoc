using System;
using System.Collections.Generic;
using System.Linq;
using DOL.AI.Brain;
using DOL.GS.LiveCompanion;
using DOL.GS.Styles;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace DOL.GS.API.DummyCombat
{
    internal static class DummyCombatRoutes
    {
        private const string TestClonePrefix = "KDAOC_TEST_";

        public static void MapDummyCombatRoutes(this WebApplication api)
        {
            api.MapGet("/api/dummy/combat/usable", (HttpContext context) =>
            {
                string name = context.Request.Query["name"].FirstOrDefault() ?? string.Empty;
                string account = context.Request.Query["account"].FirstOrDefault() ?? string.Empty;
                GamePlayer player = FindPlayer(name, account);

                if (player == null)
                    return Results.NotFound(new { error = "PlayerNotFound", name, account });

                return Results.Ok(BuildUsableSnapshot(player));
            });

            api.MapGet("/api/dummy/combat/npcs", (HttpContext context) =>
            {
                string name = context.Request.Query["name"].FirstOrDefault() ?? string.Empty;
                ushort region = 0;
                int limit = 20;
                int objectId = 0;
                int x = 0;
                int y = 0;
                int radius = 0;
                int minLevel = 0;
                int maxLevel = 0;

                ushort.TryParse(context.Request.Query["region"].FirstOrDefault(), out region);
                int.TryParse(context.Request.Query["limit"].FirstOrDefault(), out limit);
                int.TryParse(context.Request.Query["objectId"].FirstOrDefault(), out objectId);
                int.TryParse(context.Request.Query["x"].FirstOrDefault(), out x);
                int.TryParse(context.Request.Query["y"].FirstOrDefault(), out y);
                int.TryParse(context.Request.Query["radius"].FirstOrDefault(), out radius);
                int.TryParse(context.Request.Query["minLevel"].FirstOrDefault(), out minLevel);
                int.TryParse(context.Request.Query["maxLevel"].FirstOrDefault(), out maxLevel);
                limit = Math.Clamp(limit, 1, 200);
                radius = Math.Clamp(radius, 0, 50000);

                GameNPC[] npcs = region > 0
                    ? WorldMgr.GetNPCsFromRegion(region)
                    : WorldMgr.GetAllRegions()
                        .SelectMany(entry => entry.Objects.OfType<GameNPC>())
                        .ToArray();

                bool hasOrigin = x != 0 || y != 0;
                long radiusSquared = (long)radius * radius;

                var matches = npcs
                    .Where(npc => npc != null)
                    .Where(npc => npc.ObjectState is GameObject.eObjectState.Active)
                    .Where(npc => npc.IsAlive)
                    .Where(npc => objectId <= 0 || npc.ObjectID == objectId)
                    .Where(npc => minLevel <= 0 || npc.Level >= minLevel)
                    .Where(npc => maxLevel <= 0 || npc.Level <= maxLevel)
                    .Where(npc =>
                    {
                        if (!hasOrigin || radius <= 0)
                            return true;

                        return DistanceSquared(npc.X, npc.Y, x, y) <= radiusSquared;
                    })
                    .Where(npc => string.IsNullOrWhiteSpace(name) ||
                                  npc.Name.IndexOf(name, StringComparison.OrdinalIgnoreCase) >= 0)
                    .OrderBy(npc => hasOrigin ? DistanceSquared(npc.X, npc.Y, x, y) : 0)
                    .ThenBy(npc => npc.Name)
                    .ThenBy(npc => npc.ObjectID)
                    .Take(limit)
                    .Select(npc => ToNpcCombatDto(npc, queryX: hasOrigin ? x : null, queryY: hasOrigin ? y : null))
                    .ToArray();

                return matches.Length == 0
                    ? Results.NotFound(new { error = "NpcNotFound", name, region })
                    : Results.Ok(matches);
            });

            api.MapGet("/api/dummy/combat/encounter-snapshot", (HttpContext context) =>
            {
                string name = context.Request.Query["name"].FirstOrDefault() ?? string.Empty;
                ushort region = 0;
                int radius = 5000;
                int limit = 80;

                ushort.TryParse(context.Request.Query["region"].FirstOrDefault(), out region);
                int.TryParse(context.Request.Query["radius"].FirstOrDefault(), out radius);
                int.TryParse(context.Request.Query["limit"].FirstOrDefault(), out limit);
                radius = Math.Clamp(radius, 250, 20000);
                limit = Math.Clamp(limit, 1, 500);

                if (string.IsNullOrWhiteSpace(name))
                    return Results.BadRequest(new { error = "MissingName" });

                GameNPC target = FindNpc(name, region);

                if (target == null)
                    return Results.NotFound(new { error = "NpcNotFound", name, region });

                region = target.CurrentRegionID;
                long radiusSquared = (long)radius * radius;

                var players = ClientService.Instance.GetClients()
                    .Select(client => client.Player)
                    .Where(IsUsablePlayer)
                    .Where(player => player.CurrentRegionID == region)
                    .Where(player => DistanceSquared(player.X, player.Y, target.X, target.Y) <= radiusSquared)
                    .OrderBy(player => DistanceSquared(player.X, player.Y, target.X, target.Y))
                    .ThenBy(player => player.Name)
                    .Take(limit)
                    .Select(player => ToPlayerEncounterDto(player, target))
                    .ToArray();

                var npcs = WorldMgr.GetNPCsFromRegion(region)
                    .Where(npc => npc != null)
                    .Where(npc => npc.ObjectState is GameObject.eObjectState.Active)
                    .Where(npc => npc.ObjectID != target.ObjectID)
                    .Where(npc => DistanceSquared(npc.X, npc.Y, target.X, target.Y) <= radiusSquared)
                    .OrderBy(npc => DistanceSquared(npc.X, npc.Y, target.X, target.Y))
                    .ThenBy(npc => npc.Name)
                    .Take(limit)
                    .Select(npc => ToNpcEncounterDto(npc, target))
                    .ToArray();

                return Results.Ok(new
                {
                    eventType = "server_encounter_snapshot",
                    queryName = name,
                    region,
                    radius,
                    target = ToNpcCombatDto(target, radius, npcs.Length),
                    players,
                    npcs
                });
            });

            api.MapPost("/api/dummy/combat/clone-npc", (HttpContext context) =>
            {
                string sourceName = context.Request.Query["source"].FirstOrDefault() ?? string.Empty;
                string requestedName = context.Request.Query["name"].FirstOrDefault() ?? string.Empty;

                if (string.IsNullOrWhiteSpace(sourceName))
                    return Results.BadRequest(new { error = "MissingSource" });

                string cloneName = string.IsNullOrWhiteSpace(requestedName)
                    ? $"{TestClonePrefix}{Guid.NewGuid():N}"
                    : requestedName.Trim();

                if (!cloneName.StartsWith(TestClonePrefix, StringComparison.OrdinalIgnoreCase))
                    cloneName = $"{TestClonePrefix}{cloneName}";

                ushort region = 0;
                int x = 0;
                int y = 0;
                int z = 0;
                int nearbyRadius = 2600;
                ushort heading = 0;
                byte level = 0;

                ushort.TryParse(context.Request.Query["region"].FirstOrDefault(), out region);
                int.TryParse(context.Request.Query["x"].FirstOrDefault(), out x);
                int.TryParse(context.Request.Query["y"].FirstOrDefault(), out y);
                int.TryParse(context.Request.Query["z"].FirstOrDefault(), out z);
                int.TryParse(context.Request.Query["nearbyRadius"].FirstOrDefault(), out nearbyRadius);
                ushort.TryParse(context.Request.Query["heading"].FirstOrDefault(), out heading);
                byte.TryParse(context.Request.Query["level"].FirstOrDefault(), out level);

                GameNPC source = FindNpc(sourceName, region);

                if (source == null)
                    return Results.NotFound(new { error = "SourceNpcNotFound", source = sourceName, region });

                RemoveTestClones(cloneName);

                region = region > 0 ? region : source.CurrentRegionID;
                x = x != 0 ? x : source.X;
                y = y != 0 ? y : source.Y;
                z = z != 0 ? z : source.Z;
                heading = heading != 0 ? heading : source.Heading;
                nearbyRadius = Math.Clamp(nearbyRadius, 0, 10000);
                int nearbyNpcCount = CountNearbyNpcs(region, x, y, nearbyRadius, source.ObjectID, cloneName);

                GameNPC clone = CreateNpcClone(source);
                clone.Name = cloneName;
                clone.SaveInDB = false;
                clone.RespawnInterval = 0;
                clone.Level = level > 0 ? level : source.Level;

                bool created = clone.Create(region, x, y, z, heading);

                if (!created)
                    return Results.BadRequest(new { error = "CloneCreateFailed", name = cloneName, region, x, y, z });

                clone.Health = clone.MaxHealth;

                return Results.Ok(ToNpcCombatDto(clone, nearbyRadius, nearbyNpcCount));
            });

            api.MapDelete("/api/dummy/combat/test-clones", (HttpContext context) =>
            {
                string prefix = context.Request.Query["prefix"].FirstOrDefault() ?? TestClonePrefix;

                if (string.IsNullOrWhiteSpace(prefix))
                    prefix = TestClonePrefix;

                int removed = RemoveTestClones(prefix);
                return Results.Ok(new { removed, prefix });
            });
        }

        private static GameNPC FindNpc(string name, ushort region)
        {
            IEnumerable<GameNPC> npcs = region > 0
                ? WorldMgr.GetNPCsFromRegion(region)
                : WorldMgr.GetAllRegions().SelectMany(entry => entry.Objects.OfType<GameNPC>());

            return npcs
                .Where(npc => npc != null)
                .Where(npc => npc.ObjectState is GameObject.eObjectState.Active)
                .FirstOrDefault(npc => string.Equals(npc.Name, name, StringComparison.OrdinalIgnoreCase)) ??
                   npcs
                       .Where(npc => npc != null)
                       .Where(npc => npc.ObjectState is GameObject.eObjectState.Active)
                       .FirstOrDefault(npc => npc.Name.IndexOf(name, StringComparison.OrdinalIgnoreCase) >= 0);
        }

        private static GameNPC CreateNpcClone(GameNPC source)
        {
            // Use a plain NPC for test clones. Scripted epic bosses often override AddToWorld()
            // to reload templates, reset static encounter state, or save themselves to the DB.
            GameNPC clone = new GameNPC();

            clone.BodyType = source.BodyType;
            clone.DamageFactor = source.DamageFactor;
            clone.Faction = source.Faction;
            clone.Flags = source.Flags;
            clone.GuildName = source.GuildName;
            clone.Heading = source.Heading;
            clone.Level = source.Level;
            clone.MaxSpeedBase = source.MaxSpeedBase;
            clone.MeleeDamageType = source.MeleeDamageType;
            clone.Model = source.Model;
            clone.ParryChance = source.ParryChance;
            clone.Realm = source.Realm;
            clone.RoamingRange = 0;
            clone.Size = source.Size;
            clone.TetherRange = source.TetherRange;

            if (clone.Brain is StandardMobBrain cloneBrain && source.Brain is StandardMobBrain sourceBrain)
            {
                cloneBrain.AggroLevel = sourceBrain.AggroLevel;
                cloneBrain.AggroRange = sourceBrain.AggroRange;
            }

            if (source.Spells != null && source.Spells.Count > 0)
                clone.Spells = new List<Spell>(source.Spells);

            if (source.Styles != null && source.Styles.Count > 0)
                clone.Styles = new List<Style>(source.Styles);

            return clone;
        }

        private static int RemoveTestClones(string prefix)
        {
            GameNPC[] clones = WorldMgr.GetAllRegions()
                .SelectMany(entry => entry.Objects.OfType<GameNPC>())
                .Where(npc => npc != null)
                .Where(npc => npc.Name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                .ToArray();

            int removed = 0;

            foreach (GameNPC clone in clones)
            {
                clone.Delete();
                removed++;
            }

            return removed;
        }

        private static int CountNearbyNpcs(ushort region, int x, int y, int radius, int sourceObjectId, string cloneName)
        {
            if (region <= 0 || radius <= 0)
                return 0;

            long radiusSquared = (long)radius * radius;

            return WorldMgr.GetNPCsFromRegion(region)
                .Where(npc => npc != null)
                .Where(npc => npc.ObjectState is GameObject.eObjectState.Active)
                .Where(npc => npc.ObjectID != sourceObjectId)
                .Where(npc => !string.Equals(npc.Name, cloneName, StringComparison.OrdinalIgnoreCase))
                .Where(npc => !npc.Name.StartsWith(TestClonePrefix, StringComparison.OrdinalIgnoreCase))
                .Count(npc =>
                {
                    long dx = (long)npc.X - x;
                    long dy = (long)npc.Y - y;
                    return dx * dx + dy * dy <= radiusSquared;
                });
        }

        private static long DistanceSquared(int ax, int ay, int bx, int by)
        {
            long dx = (long)ax - bx;
            long dy = (long)ay - by;
            return dx * dx + dy * dy;
        }

        private static double HorizontalDistance(GameObject actor, GameObject target)
        {
            return Math.Round(Math.Sqrt(DistanceSquared(actor.X, actor.Y, target.X, target.Y)), 2);
        }

        private static GamePlayer FindPlayer(string name, string account)
        {
            if (!string.IsNullOrWhiteSpace(name))
            {
                GamePlayer player = ClientService.Instance.GetPlayerByExactName(name);

                if (IsUsablePlayer(player))
                    return player;
            }

            return ClientService.Instance.GetClients()
                .Select(client => client.Player)
                .FirstOrDefault(player =>
                    IsUsablePlayer(player) &&
                    ((!string.IsNullOrWhiteSpace(name) && string.Equals(player.Name, name, StringComparison.OrdinalIgnoreCase)) ||
                     (!string.IsNullOrWhiteSpace(account) && string.Equals(player.Client?.Account?.Name, account, StringComparison.OrdinalIgnoreCase))));
        }

        private static bool IsUsablePlayer(GamePlayer player)
        {
            return player != null &&
                   player.ObjectState is GameObject.eObjectState.Active &&
                   player.Client?.ClientState is GameClient.eClientState.Playing;
        }

        private static object BuildUsableSnapshot(GamePlayer player)
        {
            var skills = player.GetAllUsableSkills(true);
            int nonSpecBegin = Math.Max(0, skills.FindIndex(item => item.Item1 is not Specialization));
            var spellLines = player.GetAllUsableListSpells(true);
            object[] groupMembers = player.Group == null
                ? Array.Empty<object>()
                : player.Group.GetPlayersInTheGroup()
                    .Where(IsUsablePlayer)
                    .OrderBy(member => ReferenceEquals(member, player) ? 0 : 1)
                    .ThenBy(member => member.Name)
                    .Select(ToPlayerCombatDto)
                    .ToArray();

            return new
            {
                player = ToPlayerCombatDto(player),
                groupMembers,
                skills = skills.Select((entry, index) => ToSkillDto(entry.Item1, entry.Item2, index, nonSpecBegin)).ToArray(),
                spellLines = spellLines.Select((entry, lineIndex) => new
                {
                    lineIndex,
                    line = new
                    {
                        entry.Item1.Name,
                        entry.Item1.KeyName,
                        entry.Item1.Spec,
                        entry.Item1.IsBaseLine
                    },
                    entries = entry.Item2.Select(skill => ToSpellLineEntryDto(skill, lineIndex)).ToArray()
                }).ToArray()
            };
        }

        private static object ToPlayerCombatDto(GamePlayer player)
        {
            int maxHealth = Math.Max(1, player.MaxHealth);
            string companionRole = CompanionRequestService.ActiveCompanionRoleFor(player.Name);

            return new
            {
                name = player.Name,
                account = player.Client?.Account?.Name ?? string.Empty,
                sessionId = player.Client?.SessionID ?? 0,
                objectId = player.ObjectID,
                level = player.Level,
                @class = player.CharacterClass?.Name ?? string.Empty,
                classId = player.CharacterClass?.ID ?? 0,
                realm = player.Realm.ToString(),
                region = player.CurrentRegionID,
                x = player.X,
                y = player.Y,
                z = player.Z,
                health = player.Health,
                maxHealth,
                healthPercent = Math.Round(player.Health * 100.0 / maxHealth, 2),
                isAlive = player.IsAlive,
                isDead = !player.IsAlive,
                inCombat = player.InCombat,
                isStunned = player.IsStunned,
                isMezzed = player.IsMezzed,
                isCrowdControlled = player.IsCrowdControlled,
                isDiseased = player.IsDiseased,
                isPoisoned = player.IsPoisoned,
                isSilenced = player.IsSilenced,
                isNearsighted = player.effectListComponent.ContainsEffectForEffectType(DOL.GS.eEffect.Nearsight),
                isCompanion = !string.IsNullOrWhiteSpace(companionRole),
                companionRole,
                targetObjectId = player.TargetObject?.ObjectID ?? 0,
                targetName = player.TargetObject?.Name ?? string.Empty,
                targetType = player.TargetObject?.GetType().FullName ?? string.Empty,
                targetCanAttack = TargetCanAttack(player, player.TargetObject),
                targetRelation = TargetRelationFor(player, player.TargetObject)
            };
        }

        private static bool TargetCanAttack(GamePlayer player, GameObject target)
        {
            if (target is not GameLiving livingTarget)
                return false;

            return GameServer.ServerRules.IsAllowedToAttack(player, livingTarget, true);
        }

        private static string TargetRelationFor(GamePlayer player, GameObject target)
        {
            if (target == null)
                return "none";
            if (ReferenceEquals(player, target))
                return "self";

            if (target is GamePlayer targetPlayer)
            {
                if (player.Group != null && player.Group.IsInTheGroup(targetPlayer))
                    return "party";
                if (targetPlayer.Realm == player.Realm)
                    return "same_realm";

                return TargetCanAttack(player, target) ? "enemy" : "blocked";
            }

            return TargetCanAttack(player, target) ? "hostile" : "neutral";
        }

        private static object ToNpcCombatDto(GameNPC npc, int nearbyNpcRadius = 0, int nearbyNpcCount = -1, int? queryX = null, int? queryY = null)
        {
            int maxHealth = Math.Max(1, npc.MaxHealth);
            double healthPercent = Math.Round(npc.Health * 100.0 / maxHealth, 2);
            StandardMobBrain brain = npc.Brain as StandardMobBrain;
            double distance = queryX.HasValue && queryY.HasValue
                ? Math.Round(Math.Sqrt(DistanceSquared(npc.X, npc.Y, queryX.Value, queryY.Value)), 2)
                : 0;

            return new
            {
                name = npc.Name,
                guildName = npc.GuildName ?? string.Empty,
                objectId = npc.ObjectID,
                internalId = npc.InternalID,
                classType = npc.GetType().FullName,
                level = npc.Level,
                region = npc.CurrentRegionID,
                x = npc.X,
                y = npc.Y,
                z = npc.Z,
                health = npc.Health,
                maxHealth,
                healthPercent,
                isAlive = npc.IsAlive,
                inCombat = npc.InCombat,
                hasAggro = brain?.HasAggro ?? false,
                target = npc.TargetObject?.Name ?? string.Empty,
                distance,
                nearbyNpcRadius,
                nearbyNpcCount
            };
        }

        private static object ToPlayerEncounterDto(GamePlayer player, GameNPC target)
        {
            int maxHealth = Math.Max(1, player.MaxHealth);

            return new
            {
                type = "player",
                name = player.Name,
                account = player.Client?.Account?.Name ?? string.Empty,
                objectId = player.ObjectID,
                level = player.Level,
                realm = player.Realm.ToString(),
                region = player.CurrentRegionID,
                x = player.X,
                y = player.Y,
                z = player.Z,
                distance = HorizontalDistance(player, target),
                health = player.Health,
                maxHealth,
                healthPercent = Math.Round(player.Health * 100.0 / maxHealth, 2),
                isAlive = player.IsAlive,
                isDead = !player.IsAlive,
                inCombat = player.InCombat,
                isStunned = player.IsStunned,
                isMezzed = player.IsMezzed,
                isCrowdControlled = player.IsCrowdControlled,
                isDiseased = player.IsDiseased,
                isPoisoned = player.IsPoisoned,
                isSilenced = player.IsSilenced,
                isNearsighted = player.effectListComponent.ContainsEffectForEffectType(DOL.GS.eEffect.Nearsight),
                targetObjectId = player.TargetObject?.ObjectID ?? 0,
                targetName = player.TargetObject?.Name ?? string.Empty,
                targetType = player.TargetObject?.GetType().FullName ?? string.Empty,
                targetCanAttack = TargetCanAttack(player, player.TargetObject),
                targetRelation = TargetRelationFor(player, player.TargetObject)
            };
        }

        private static object ToNpcEncounterDto(GameNPC npc, GameNPC target)
        {
            StandardMobBrain brain = npc.Brain as StandardMobBrain;
            int maxHealth = Math.Max(1, npc.MaxHealth);

            return new
            {
                type = "npc",
                name = npc.Name,
                guildName = npc.GuildName ?? string.Empty,
                objectId = npc.ObjectID,
                internalId = npc.InternalID,
                classType = npc.GetType().FullName,
                level = npc.Level,
                region = npc.CurrentRegionID,
                x = npc.X,
                y = npc.Y,
                z = npc.Z,
                distance = HorizontalDistance(npc, target),
                health = npc.Health,
                maxHealth,
                healthPercent = Math.Round(npc.Health * 100.0 / maxHealth, 2),
                isAlive = npc.IsAlive,
                inCombat = npc.InCombat,
                hasAggro = brain?.HasAggro ?? false,
                targetObjectId = npc.TargetObject?.ObjectID ?? 0,
                targetName = npc.TargetObject?.Name ?? string.Empty,
                targetType = npc.TargetObject?.GetType().FullName ?? string.Empty
            };
        }

        private static object ToSkillDto(Skill skill, Skill sibling, int rawIndex, int nonSpecBegin)
        {
            int useSkillType = rawIndex >= nonSpecBegin ? 1 : 0;
            int useSkillIndex = useSkillType > 0 ? rawIndex - nonSpecBegin : rawIndex;

            return new
            {
                rawIndex,
                useSkillIndex,
                useSkillType,
                kind = SkillKind(skill),
                name = skill.Name,
                id = skill.ID,
                internalId = skill.InternalID,
                level = skill.Level,
                icon = skill.Icon,
                skillType = skill.SkillType.ToString(),
                siblingKind = sibling == null ? string.Empty : SkillKind(sibling),
                style = skill is Style style ? StyleInfo(style) : null,
                ability = skill is Ability ability ? AbilityInfo(ability) : null,
                spell = skill is Spell spell ? SpellInfo(spell) : null
            };
        }

        private static object ToSpellLineEntryDto(Skill skill, int lineIndex)
        {
            int spellLevel = skill switch
            {
                Spell spellEntry => spellEntry.Level,
                Style styleEntry => styleEntry.SpecLevelRequirement,
                Ability abilityEntry => abilityEntry.SpecLevelRequirement,
                _ => skill.Level
            };

            return new
            {
                lineIndex,
                spellLevel,
                kind = SkillKind(skill),
                name = skill.Name,
                id = skill.ID,
                internalId = skill.InternalID,
                level = skill.Level,
                icon = skill.Icon,
                skillType = skill.SkillType.ToString(),
                style = skill is Style style ? StyleInfo(style) : null,
                ability = skill is Ability ability ? AbilityInfo(ability) : null,
                spell = skill is Spell spell ? SpellInfo(spell) : null
            };
        }

        private static string SkillKind(Skill skill)
        {
            return skill switch
            {
                Spell => "Spell",
                Style => "Style",
                Ability => "Ability",
                Specialization => "Specialization",
                SpellLine => "SpellLine",
                _ => skill.GetType().Name
            };
        }

        private static object StyleInfo(Style style)
        {
            return new
            {
                specLevelRequirement = style.SpecLevelRequirement,
                openingRequirementType = style.OpeningRequirementType.ToString(),
                openingRequirementValue = style.OpeningRequirementValue,
                attackResultRequirement = style.AttackResultRequirement.ToString()
            };
        }

        private static object AbilityInfo(Ability ability)
        {
            return new
            {
                specLevelRequirement = ability.SpecLevelRequirement,
                spec = ability.Spec
            };
        }

        private static object SpellInfo(Spell spell)
        {
            return new
            {
                spellType = spell.SpellType.ToString(),
                target = spell.Target.ToString(),
                range = spell.Range,
                radius = spell.Radius,
                castTime = spell.CastTime,
                recastDelay = spell.RecastDelay,
                duration = spell.Duration,
                concentration = spell.Concentration,
                damage = spell.Damage,
                damageType = spell.DamageType.ToString(),
                frequency = spell.Frequency,
                pulse = spell.Pulse,
                instrumentRequirement = spell.InstrumentRequirement,
                uninterruptible = spell.Uninterruptible,
                value = spell.Value,
                power = spell.Power,
                isHarmful = spell.IsHarmful,
                isHelpful = spell.IsHelpful,
                isHealing = spell.IsHealing,
                isBuff = spell.IsBuff,
                isDebuff = spell.IsDebuff,
                capabilityTags = SpellCapabilityTags(spell)
            };
        }

        private static string[] SpellCapabilityTags(Spell spell)
        {
            HashSet<string> tags = new HashSet<string>(StringComparer.Ordinal);
            string spellType = spell.SpellType.ToString();
            string spellTypeKey = spellType.ToLowerInvariant();

            if (spell.IsHealing)
                tags.Add("heal");
            if (spell.IsBuff)
                tags.Add("buff");
            if (spell.IsDebuff)
                tags.Add("debuff");
            if (spell.IsHarmful && spell.Damage > 0)
                tags.Add("damage");
            if (spell.Radius > 0 || string.Equals(spell.Target.ToString(), "Area", StringComparison.OrdinalIgnoreCase))
                tags.Add("aoe");

            switch (spell.SpellType)
            {
                case eSpellType.Resurrect:
                    tags.Add("resurrection");
                    break;
                case eSpellType.CureAll:
                    tags.Add("cure");
                    tags.Add("cureAll");
                    tags.Add("cureDisease");
                    tags.Add("cureMezz");
                    tags.Add("cureNearsight");
                    tags.Add("curePoison");
                    break;
                case eSpellType.CureDisease:
                    tags.Add("cure");
                    tags.Add("cureDisease");
                    break;
                case eSpellType.CureMezz:
                    tags.Add("cure");
                    tags.Add("cureMezz");
                    break;
                case eSpellType.CureNearsightCustom:
                    tags.Add("cure");
                    tags.Add("cureNearsight");
                    break;
                case eSpellType.CurePoison:
                    tags.Add("cure");
                    tags.Add("curePoison");
                    break;
                case eSpellType.Mesmerize:
                case eSpellType.CeremonialBracerMezz:
                    tags.Add("mez");
                    break;
                case eSpellType.Stun:
                case eSpellType.StyleStun:
                case eSpellType.CeremonialBracerStun:
                    tags.Add("stun");
                    break;
                case eSpellType.Taunt:
                case eSpellType.StyleTaunt:
                    tags.Add("taunt");
                    break;
                case eSpellType.Charm:
                    tags.Add("charm");
                    tags.Add("crowdControl");
                    break;
                case eSpellType.Bladeturn:
                    tags.Add("bladeturn");
                    tags.Add("buff");
                    break;
                case eSpellType.Lifedrain:
                case eSpellType.LifedrainNoVariance:
                case eSpellType.PetLifedrain:
                case eSpellType.OmniLifedrain:
                    tags.Add("lifedrain");
                    tags.Add("damage");
                    break;
                case eSpellType.Disease:
                    tags.Add("disease");
                    tags.Add("debuff");
                    break;
                case eSpellType.SpeedEnhancement:
                case eSpellType.SpeedOfTheRealm:
                case eSpellType.SpeedWrap:
                    tags.Add("speed");
                    if (spell.InstrumentRequirement > 0 || spell.Pulse > 0 || spell.Frequency > 0)
                        tags.Add("speedSong");
                    break;
                case eSpellType.StealthSkillBuff:
                case eSpellType.BlanketOfCamouflage:
                case eSpellType.Climbing:
                    tags.Add("stealth");
                    break;
                case eSpellType.VampiirStealthDetection:
                    tags.Add("stealthDetection");
                    break;
            }

            if (spellTypeKey.Contains("debuff") || spellTypeKey.Contains("disease") || spellTypeKey.Contains("nearsight"))
                tags.Add("debuff");
            if (spellTypeKey.Contains("disease"))
                tags.Add("disease");
            if (spellTypeKey.Contains("damageovertime") || spellTypeKey.Contains("dot") || spellTypeKey.Contains("bleeding"))
                tags.Add("dot");
            if (spellTypeKey.Contains("root") || spellTypeKey.Contains("snare"))
                tags.Add("root");
            if (spellTypeKey.Contains("amnesia") || spellTypeKey.Contains("interrupt"))
                tags.Add("interrupt");
            if (spellTypeKey.Contains("summon") || spellTypeKey.Contains("pet"))
            {
                tags.Add("pet");
                tags.Add("summon");
            }
            if (spellTypeKey.Contains("charm"))
                tags.Add("charm");
            if (spellTypeKey.Contains("bladeturn"))
                tags.Add("bladeturn");
            if (spellTypeKey.Contains("lifedrain"))
                tags.Add("lifedrain");

            return tags.OrderBy(tag => tag, StringComparer.Ordinal).ToArray();
        }
    }
}
