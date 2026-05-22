using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using DOL.Database;
using DOL.GS.ServerProperties;

namespace DOL.GS.WorldAI
{
    public static class MobGrowthStages
    {
        public const string Normal = "Normal";
        public const string Elite = "Elite";
        public const string Champion = "Champion";
        public const string Boss = "Boss";
    }

    public interface IMobGrowthRepository
    {
        bool Add(DbMobGrowthState row);
        DbMobGrowthState Find(string mobId);
        IList<DbMobGrowthState> GetActive(int limit);
        IList<DbMobGrowthState> GetTopActive(int limit);
        int CountActiveBosses();
        bool Save(DbMobGrowthState row);
        bool Delete(DbMobGrowthState row);
    }

    public sealed class MobGrowthObservation
    {
        public string MobId { get; set; }
        public string Name { get; set; }
        public string Region { get; set; }
        public ushort RegionId { get; set; }
        public int X { get; set; }
        public int Y { get; set; }
        public int Z { get; set; }
        public ushort Heading { get; set; }
        public int Level { get; set; }
        public bool IsAlive { get; set; }
        public bool IsEligible { get; set; }
    }

    public sealed class MobGrowthOptions
    {
        public bool Enabled { get; set; }
        public int SurvivalScorePerTick { get; set; } = 2;
        public int UnhuntedScorePerTick { get; set; } = 8;
        public int CombatScore { get; set; } = 12;
        public int CombatGrowthCooldownSeconds { get; set; } = 30;
        public int PlayerKillScore { get; set; } = 50;
        public int UnhuntedAfterMinutes { get; set; } = 360;
        public int EliteScore { get; set; } = 60;
        public int ChampionScore { get; set; } = 180;
        public int BossScore { get; set; } = 420;
        public int MaxLevelBonus { get; set; } = 5;
        public double MaxHealthMultiplier { get; set; } = 1.5;
        public int MaxActiveBosses { get; set; } = 5;
        public string ExcludedRegions { get; set; } = string.Empty;

        public static MobGrowthOptions FromProperties()
        {
            return new MobGrowthOptions
            {
                Enabled = Properties.WORLDAI_MOB_GROWTH_ENABLED,
                SurvivalScorePerTick = Math.Max(0, Properties.WORLDAI_MOB_GROWTH_SURVIVAL_SCORE),
                UnhuntedScorePerTick = Math.Max(0, Properties.WORLDAI_MOB_GROWTH_UNHUNTED_SCORE),
                CombatScore = Math.Max(0, Properties.WORLDAI_MOB_GROWTH_COMBAT_SCORE),
                CombatGrowthCooldownSeconds = Math.Max(0, Properties.WORLDAI_MOB_GROWTH_COMBAT_COOLDOWN_SECONDS),
                PlayerKillScore = Math.Max(0, Properties.WORLDAI_MOB_GROWTH_PLAYER_KILL_SCORE),
                UnhuntedAfterMinutes = Math.Max(1, Properties.WORLDAI_MOB_GROWTH_UNHUNTED_AFTER_MINUTES),
                EliteScore = Math.Max(1, Properties.WORLDAI_MOB_GROWTH_ELITE_SCORE),
                ChampionScore = Math.Max(1, Properties.WORLDAI_MOB_GROWTH_CHAMPION_SCORE),
                BossScore = Math.Max(1, Properties.WORLDAI_MOB_GROWTH_BOSS_SCORE),
                MaxLevelBonus = Math.Clamp(Properties.WORLDAI_MOB_GROWTH_MAX_LEVEL_BONUS, 0, 10),
                MaxHealthMultiplier = Math.Clamp(Properties.WORLDAI_MOB_GROWTH_MAX_HEALTH_MULTIPLIER, 1.0, 3.0),
                MaxActiveBosses = Math.Max(0, Properties.WORLDAI_MOB_GROWTH_MAX_ACTIVE_BOSSES),
                ExcludedRegions = Properties.WORLDAI_MOB_GROWTH_EXCLUDED_REGIONS ?? string.Empty
            };
        }

        public static MobGrowthOptions DefaultForTests()
        {
            return new MobGrowthOptions
            {
                Enabled = true,
                SurvivalScorePerTick = 2,
                UnhuntedScorePerTick = 10,
                CombatScore = 12,
                CombatGrowthCooldownSeconds = 30,
                PlayerKillScore = 50,
                UnhuntedAfterMinutes = 360,
                EliteScore = 60,
                ChampionScore = 180,
                BossScore = 420,
                MaxLevelBonus = 5,
                MaxHealthMultiplier = 1.5,
                MaxActiveBosses = 5
            };
        }

        public bool IsRegionExcluded(ushort regionId)
        {
            if (string.IsNullOrWhiteSpace(ExcludedRegions))
                return false;

            return ExcludedRegions
                .Split(new[] { ';', ',' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(part => part.Trim())
                .Any(part => ushort.TryParse(part, out ushort value) && value == regionId);
        }
    }

    public sealed class MobGrowthSummary
    {
        public bool Enabled { get; set; }
        public int ActiveCount { get; set; }
        public int ActiveBosses { get; set; }
        public int MaxActiveBosses { get; set; }
        public DateTime GeneratedAt { get; set; }
        public IList<MobGrowthStageSummary> Stages { get; set; } = Array.Empty<MobGrowthStageSummary>();
        public IList<MobGrowthRegionSummary> Regions { get; set; } = Array.Empty<MobGrowthRegionSummary>();
        public IList<MobGrowthTopMob> Top { get; set; } = Array.Empty<MobGrowthTopMob>();
    }

    public sealed class MobGrowthStageSummary
    {
        public string Stage { get; set; }
        public int Count { get; set; }
        public int MaxScore { get; set; }
    }

    public sealed class MobGrowthRegionSummary
    {
        public ushort RegionId { get; set; }
        public string Region { get; set; }
        public int Count { get; set; }
        public int Bosses { get; set; }
        public int MaxScore { get; set; }
    }

    public sealed class MobGrowthTopMob
    {
        public string MobId { get; set; }
        public string Name { get; set; }
        public string Stage { get; set; }
        public string Region { get; set; }
        public ushort RegionId { get; set; }
        public int BaseLevel { get; set; }
        public int EffectiveLevel { get; set; }
        public int GrowthScore { get; set; }
        public int SurvivalTicks { get; set; }
        public int CombatCount { get; set; }
        public int PlayerKills { get; set; }
        public DateTime LastSeenAt { get; set; }
    }

    public sealed class MobGrowthService
    {
        public static MobGrowthService Instance { get; } = new(new DatabaseMobGrowthRepository(), WorldEventService.Instance);

        private readonly IMobGrowthRepository m_growth;
        private readonly WorldEventService m_worldEvents;

        public MobGrowthService(IMobGrowthRepository growth, WorldEventService worldEvents)
        {
            m_growth = growth ?? throw new ArgumentNullException(nameof(growth));
            m_worldEvents = worldEvents ?? throw new ArgumentNullException(nameof(worldEvents));
        }

        public DbMobGrowthState ObserveTick(MobGrowthObservation observation, DateTime now, MobGrowthOptions options)
        {
            if (!CanProcess(observation, options))
                return null;

            DbMobGrowthState state = GetOrCreate(observation, now);
            string previousStage = state.Stage;

            state.IsActive = true;
            state.LastSeenAt = now;
            state.SurvivalTicks++;
            state.GrowthScore += options.SurvivalScorePerTick;

            if (IsUnhunted(state, now, options))
            {
                state.UnhuntedTicks++;
                state.GrowthScore += options.UnhuntedScorePerTick;
            }

            RefreshDerivedState(state, observation, options);
            Save(state);
            PublishPromotionIfNeeded(previousStage, state, observation);
            return state;
        }

        public DbMobGrowthState RecordCombat(MobGrowthObservation observation, DateTime now, MobGrowthOptions options)
        {
            if (!CanProcess(observation, options))
                return null;

            DbMobGrowthState state = GetOrCreate(observation, now);
            string previousStage = state.Stage;

            if (!CanRecordCombatGrowth(state, now, options))
                return state;

            state.CombatCount++;
            state.GrowthScore += options.CombatScore;
            state.LastCombatGrowthAt = now;
            state.LastSeenAt = now;

            RefreshDerivedState(state, observation, options);
            Save(state);
            PublishPromotionIfNeeded(previousStage, state, observation);
            return state;
        }

        public DbMobGrowthState RecordPlayerKill(MobGrowthObservation observation, DateTime now, MobGrowthOptions options)
        {
            if (!CanProcess(observation, options))
                return null;

            DbMobGrowthState state = GetOrCreate(observation, now);
            string previousStage = state.Stage;

            state.PlayerKills++;
            state.CombatCount++;
            state.GrowthScore += options.PlayerKillScore;
            state.LastSeenAt = now;

            RefreshDerivedState(state, observation, options);
            Save(state);
            PublishPromotionIfNeeded(previousStage, state, observation);
            return state;
        }

        public DbMobGrowthState RecordDeath(MobGrowthObservation observation, DateTime now, MobGrowthOptions options)
        {
            if (observation == null || string.IsNullOrWhiteSpace(observation.MobId))
                return null;

            DbMobGrowthState state = m_growth.Find(observation.MobId);

            if (state == null)
                return null;

            state.IsActive = false;
            state.LastKilledAt = now;
            state.UpdatedAt = now;
            Save(state);
            return state;
        }

        public IList<DbMobGrowthState> GetTopActive(int limit)
        {
            return m_growth.GetTopActive(Math.Clamp(limit, 1, 100));
        }

        public MobGrowthSummary GetSummary(int topLimit)
        {
            MobGrowthOptions options = MobGrowthOptions.FromProperties();
            int limit = Math.Clamp(topLimit, 1, 100);
            IList<DbMobGrowthState> active = m_growth.GetActive(1000);

            return new MobGrowthSummary
            {
                Enabled = options.Enabled,
                ActiveCount = active.Count,
                ActiveBosses = active.Count(row => row.Stage == MobGrowthStages.Boss),
                MaxActiveBosses = options.MaxActiveBosses,
                GeneratedAt = DateTime.UtcNow,
                Stages = active
                    .GroupBy(row => string.IsNullOrWhiteSpace(row.Stage) ? MobGrowthStages.Normal : row.Stage)
                    .OrderBy(group => StageOrder(group.Key))
                    .Select(group => new MobGrowthStageSummary
                    {
                        Stage = group.Key,
                        Count = group.Count(),
                        MaxScore = group.Max(row => row.GrowthScore)
                    })
                    .ToList(),
                Regions = active
                    .GroupBy(row => new { row.RegionId, row.Region })
                    .OrderByDescending(group => group.Max(row => row.GrowthScore))
                    .ThenBy(group => group.Key.RegionId)
                    .Take(10)
                    .Select(group => new MobGrowthRegionSummary
                    {
                        RegionId = group.Key.RegionId,
                        Region = group.Key.Region,
                        Count = group.Count(),
                        Bosses = group.Count(row => row.Stage == MobGrowthStages.Boss),
                        MaxScore = group.Max(row => row.GrowthScore)
                    })
                    .ToList(),
                Top = m_growth.GetTopActive(limit)
                    .Select(ToTopMob)
                    .ToList()
            };
        }

        public bool Reset(string mobId)
        {
            DbMobGrowthState state = m_growth.Find(mobId);
            return state != null && m_growth.Delete(state);
        }

        public int ScanActiveWorld(int maxNpcs)
        {
            MobGrowthOptions options = MobGrowthOptions.FromProperties();

            if (!options.Enabled)
                return 0;

            int scanned = 0;
            DateTime now = DateTime.UtcNow;

            foreach (var regionEntry in WorldMgr.GetRegionList())
            {
                foreach (GameNPC npc in WorldMgr.GetNPCsFromRegion(regionEntry.id))
                {
                    if (scanned >= maxNpcs)
                        return scanned;

                    if (ObserveTick(FromNpc(npc), now, options) != null)
                    {
                        ApplyToNpc(npc);
                        scanned++;
                    }
                }
            }

            return scanned;
        }

        public static MobGrowthObservation FromNpc(GameNPC npc)
        {
            if (npc == null)
                return null;

            return new MobGrowthObservation
            {
                MobId = npc.InternalID,
                Name = npc.Name,
                Region = npc.CurrentRegion?.Name ?? npc.CurrentZone?.Description ?? $"Region {npc.CurrentRegionID}",
                RegionId = npc.CurrentRegionID,
                X = npc.X,
                Y = npc.Y,
                Z = npc.Z,
                Heading = npc.Heading,
                Level = npc.Level,
                IsAlive = npc.IsAlive,
                IsEligible = IsEligibleNpc(npc)
            };
        }

        public static double GetHealthMultiplier(DbMobGrowthState state, MobGrowthOptions options)
        {
            if (state == null || options == null)
                return 1.0;

            double maxBonus = Math.Max(0, options.MaxHealthMultiplier - 1.0);
            double ratio = options.MaxLevelBonus <= 0 ? 0 : state.GrowthLevel / (double)options.MaxLevelBonus;
            return Math.Clamp(1.0 + maxBonus * ratio, 1.0, options.MaxHealthMultiplier);
        }

        public void ApplyToNpc(GameNPC npc)
        {
            if (npc == null || !Properties.WORLDAI_MOB_GROWTH_ENABLED || string.IsNullOrWhiteSpace(npc.InternalID))
                return;

            DbMobGrowthState state = m_growth.Find(npc.InternalID);

            if (state == null || state.Stage == MobGrowthStages.Normal)
            {
                npc.WorldAiMaxHealthScalingFactor = 1.0;
                return;
            }

            npc.Name = state.CurrentName;
            npc.Level = (byte)Math.Clamp(state.EffectiveLevel, 1, byte.MaxValue);
            npc.WorldAiMaxHealthScalingFactor = GetHealthMultiplier(state, MobGrowthOptions.FromProperties());
        }

        private DbMobGrowthState GetOrCreate(MobGrowthObservation observation, DateTime now)
        {
            DbMobGrowthState state = m_growth.Find(observation.MobId);

            if (state != null)
                return state;

            state = new DbMobGrowthState
            {
                MobId = observation.MobId,
                BaseName = observation.Name,
                CurrentName = observation.Name,
                Region = observation.Region,
                RegionId = observation.RegionId,
                BaseLevel = observation.Level,
                EffectiveLevel = observation.Level,
                Stage = MobGrowthStages.Normal,
                IsActive = true,
                CreatedAt = now,
                FirstSeenAt = now,
                LastSeenAt = now,
                UpdatedAt = now
            };

            m_growth.Add(state);
            return state;
        }

        private static bool CanProcess(MobGrowthObservation observation, MobGrowthOptions options)
        {
            return options != null &&
                options.Enabled &&
                observation != null &&
                observation.IsAlive &&
                observation.IsEligible &&
                !string.IsNullOrWhiteSpace(observation.MobId) &&
                !options.IsRegionExcluded(observation.RegionId);
        }

        private static bool IsEligibleNpc(GameNPC npc)
        {
            if (npc == null || !npc.IsAlive || string.IsNullOrWhiteSpace(npc.InternalID))
                return false;

            if (npc.Realm != eRealm.None || npc is GamePlayer)
                return false;

            if (npc.Flags.HasFlag(GameNPC.eFlags.PEACE) || npc.Flags.HasFlag(GameNPC.eFlags.CANTTARGET))
                return false;

            return npc.Level > 0 && npc.Level < 75;
        }

        private static bool IsUnhunted(DbMobGrowthState state, DateTime now, MobGrowthOptions options)
        {
            DateTime reference = state.LastKilledAt == DateTime.MinValue ? state.FirstSeenAt : state.LastKilledAt;
            return now - reference >= TimeSpan.FromMinutes(options.UnhuntedAfterMinutes);
        }

        private static bool CanRecordCombatGrowth(DbMobGrowthState state, DateTime now, MobGrowthOptions options)
        {
            return state.LastCombatGrowthAt == DateTime.MinValue ||
                now - state.LastCombatGrowthAt >= TimeSpan.FromSeconds(options.CombatGrowthCooldownSeconds);
        }

        private void RefreshDerivedState(DbMobGrowthState state, MobGrowthObservation observation, MobGrowthOptions options)
        {
            state.Region = observation.Region;
            state.RegionId = observation.RegionId;
            state.BaseLevel = state.BaseLevel <= 0 ? observation.Level : state.BaseLevel;
            state.Stage = ResolveStage(state, options);
            state.GrowthLevel = Math.Clamp(ResolveLevelBonus(state.Stage, state.GrowthScore, options), 0, options.MaxLevelBonus);
            state.EffectiveLevel = Math.Clamp(state.BaseLevel + state.GrowthLevel, 1, byte.MaxValue);
            state.CurrentName = BuildCurrentName(state.BaseName, state.Stage);
            state.UpdatedAt = DateTime.UtcNow;
        }

        private string ResolveStage(DbMobGrowthState state, MobGrowthOptions options)
        {
            if (state.GrowthScore >= options.BossScore)
            {
                if (state.Stage == MobGrowthStages.Boss)
                    return MobGrowthStages.Boss;

                return m_growth.CountActiveBosses() < options.MaxActiveBosses
                    ? MobGrowthStages.Boss
                    : MobGrowthStages.Champion;
            }

            if (state.GrowthScore >= options.ChampionScore)
                return MobGrowthStages.Champion;

            if (state.GrowthScore >= options.EliteScore)
                return MobGrowthStages.Elite;

            return MobGrowthStages.Normal;
        }

        private static int ResolveLevelBonus(string stage, int score, MobGrowthOptions options)
        {
            if (stage == MobGrowthStages.Boss)
                return options.MaxLevelBonus;

            if (stage == MobGrowthStages.Champion)
                return Math.Max(2, options.MaxLevelBonus * 2 / 3);

            if (stage == MobGrowthStages.Elite)
                return 1;

            return 0;
        }

        private static string BuildCurrentName(string baseName, string stage)
        {
            if (string.IsNullOrWhiteSpace(baseName) || stage == MobGrowthStages.Normal)
                return baseName ?? string.Empty;

            if (stage == MobGrowthStages.Elite)
                return $"정예 {baseName}";

            if (stage == MobGrowthStages.Champion)
                return $"챔피언 {baseName}";

            return $"{baseName} 우두머리";
        }

        private void PublishPromotionIfNeeded(string previousStage, DbMobGrowthState state, MobGrowthObservation observation)
        {
            if (state.Stage != MobGrowthStages.Boss || previousStage == MobGrowthStages.Boss || state.LastStageEventAt != DateTime.MinValue)
                return;

            string rawDataJson = JsonSerializer.Serialize(new
            {
                source = "mob_growth",
                stage = state.Stage,
                score = state.GrowthScore,
                playerKills = state.PlayerKills,
                combatCount = state.CombatCount,
                survivalTicks = state.SurvivalTicks,
                unhuntedTicks = state.UnhuntedTicks,
                location = new
                {
                    name = WorldAiEventTypes.MobAscended,
                    actorName = state.CurrentName,
                    regionId = observation.RegionId,
                    x = observation.X,
                    y = observation.Y,
                    z = observation.Z,
                    heading = observation.Heading
                }
            });

            m_worldEvents.RecordEvent(new WorldEventRecordRequest
            {
                EventType = WorldAiEventTypes.MobAscended,
                Region = observation.Region,
                ActorName = state.CurrentName,
                Language = "kr",
                RawDataJson = rawDataJson,
                AliveDays = Math.Max(1, state.SurvivalTicks),
                Kills = state.PlayerKills,
                RegionId = observation.RegionId,
                X = observation.X,
                Y = observation.Y,
                Z = observation.Z,
                Heading = observation.Heading,
                RequiresGmApproval = true
            });

            state.LastStageEventAt = DateTime.UtcNow;
            Save(state);
        }

        private void Save(DbMobGrowthState state)
        {
            state.UpdatedAt = DateTime.UtcNow;
            m_growth.Save(state);
        }

        private static int StageOrder(string stage)
        {
            return stage switch
            {
                MobGrowthStages.Boss => 3,
                MobGrowthStages.Champion => 2,
                MobGrowthStages.Elite => 1,
                _ => 0
            };
        }

        private static MobGrowthTopMob ToTopMob(DbMobGrowthState row)
        {
            return new MobGrowthTopMob
            {
                MobId = row.MobId,
                Name = row.CurrentName,
                Stage = row.Stage,
                Region = row.Region,
                RegionId = row.RegionId,
                BaseLevel = row.BaseLevel,
                EffectiveLevel = row.EffectiveLevel,
                GrowthScore = row.GrowthScore,
                SurvivalTicks = row.SurvivalTicks,
                CombatCount = row.CombatCount,
                PlayerKills = row.PlayerKills,
                LastSeenAt = row.LastSeenAt
            };
        }
    }

    public sealed class DatabaseMobGrowthRepository : IMobGrowthRepository
    {
        public bool Add(DbMobGrowthState row)
        {
            return GameServer.Database.AddObject(row);
        }

        public DbMobGrowthState Find(string mobId)
        {
            if (string.IsNullOrWhiteSpace(mobId))
                return null;

            return GameServer.Database.FindObjectByKey<DbMobGrowthState>(mobId);
        }

        public IList<DbMobGrowthState> GetActive(int limit)
        {
            return GameServer.Database.SelectAllObjects<DbMobGrowthState>()
                .Where(row => row.IsActive)
                .OrderByDescending(row => row.GrowthScore)
                .Take(Math.Clamp(limit, 1, 1000))
                .ToList();
        }

        public IList<DbMobGrowthState> GetTopActive(int limit)
        {
            return GameServer.Database.SelectAllObjects<DbMobGrowthState>()
                .Where(row => row.IsActive)
                .OrderByDescending(row => row.GrowthScore)
                .Take(Math.Clamp(limit, 1, 100))
                .ToList();
        }

        public int CountActiveBosses()
        {
            return GameServer.Database.SelectAllObjects<DbMobGrowthState>()
                .Count(row => row.IsActive && row.Stage == MobGrowthStages.Boss);
        }

        public bool Save(DbMobGrowthState row)
        {
            return GameServer.Database.SaveObject(row);
        }

        public bool Delete(DbMobGrowthState row)
        {
            return GameServer.Database.DeleteObject(row);
        }
    }
}
