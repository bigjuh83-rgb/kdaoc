using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using DOL.AI.Brain;
using DOL.Database;
using DOL.GS.ServerProperties;
using DOL.GS.Spells;
using DOL.GS.Styles;

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
        IList<DbMobGrowthState> GetAll(int limit);
        IList<DbMobGrowthState> GetTopActive(int limit);
        int CountActiveBosses();
        int CountActiveBossesInRegion(ushort regionId);
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
        public int Size { get; set; }
        public bool IsAlive { get; set; }
        public bool IsEligible { get; set; }
    }

    public interface IMobGrowthRandom
    {
        int NextInclusive(int minValue, int maxValue);
    }

    internal sealed class MobGrowthRandom : IMobGrowthRandom
    {
        public int NextInclusive(int minValue, int maxValue)
        {
            return Util.Random(minValue, maxValue);
        }
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
        public int MaxActiveBossesPerRegion { get; set; } = 1;
        public string ExcludedRegions { get; set; } = string.Empty;
        public string ProtectedRegions { get; set; } = "27";
        public string ProtectedNameTokens { get; set; } = "quest;trainer;merchant;master;훈련;상인;퀘스트";
        public int MinimumEligibleLevel { get; set; } = 5;
        public int LowLevelMaxBaseLevel { get; set; } = 15;
        public string LowLevelMaxStage { get; set; } = MobGrowthStages.Elite;
        public bool DecayEnabled { get; set; } = true;
        public int DecayAfterMinutes { get; set; } = 720;
        public int DecayScore { get; set; } = 60;
        public int ResetInactiveAfterMinutes { get; set; } = 10080;
        public bool MutationEnabled { get; set; } = true;
        public int MutationDeathWindowMinutes { get; set; } = 10;
        public int MutationDeathThreshold { get; set; } = 5;
        public int MutationChanceStepPercent { get; set; } = 10;
        public int MutationMaxChancePercent { get; set; } = 100;
        public int MutationLevelBonus { get; set; } = 2;
        public int MutationSizeBonusPercent { get; set; } = 15;
        public int EliteSizeBonusPercent { get; set; } = 10;
        public int ChampionSizeBonusPercent { get; set; } = 25;
        public int BossSizeBonusPercent { get; set; } = 45;
        public string MutationSpellPool { get; set; } = string.Empty;
        public string EliteSpellPool { get; set; } = string.Empty;
        public string ChampionSpellPool { get; set; } = string.Empty;
        public string BossSpellPool { get; set; } = string.Empty;
        public string MutationStylePool { get; set; } = string.Empty;
        public string EliteStylePool { get; set; } = string.Empty;
        public string ChampionStylePool { get; set; } = string.Empty;
        public string BossStylePool { get; set; } = string.Empty;
        public string MutationAbilityPool { get; set; } = string.Empty;
        public string EliteAbilityPool { get; set; } = string.Empty;
        public string ChampionAbilityPool { get; set; } = string.Empty;
        public string BossAbilityPool { get; set; } = string.Empty;

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
                MaxActiveBossesPerRegion = Math.Max(0, Properties.WORLDAI_MOB_GROWTH_MAX_ACTIVE_BOSSES_PER_REGION),
                ExcludedRegions = Properties.WORLDAI_MOB_GROWTH_EXCLUDED_REGIONS ?? string.Empty,
                ProtectedRegions = Properties.WORLDAI_MOB_GROWTH_PROTECTED_REGIONS ?? string.Empty,
                ProtectedNameTokens = Properties.WORLDAI_MOB_GROWTH_PROTECTED_NAME_TOKENS ?? string.Empty,
                MinimumEligibleLevel = Math.Clamp(Properties.WORLDAI_MOB_GROWTH_MINIMUM_ELIGIBLE_LEVEL, 1, 74),
                LowLevelMaxBaseLevel = Math.Clamp(Properties.WORLDAI_MOB_GROWTH_LOW_LEVEL_MAX_BASE_LEVEL, 0, 74),
                LowLevelMaxStage = NormalizeOptionStage(Properties.WORLDAI_MOB_GROWTH_LOW_LEVEL_MAX_STAGE),
                DecayEnabled = Properties.WORLDAI_MOB_GROWTH_DECAY_ENABLED,
                DecayAfterMinutes = Math.Max(1, Properties.WORLDAI_MOB_GROWTH_DECAY_AFTER_MINUTES),
                DecayScore = Math.Max(0, Properties.WORLDAI_MOB_GROWTH_DECAY_SCORE),
                ResetInactiveAfterMinutes = Math.Max(1, Properties.WORLDAI_MOB_GROWTH_RESET_INACTIVE_AFTER_MINUTES),
                MutationEnabled = Properties.WORLDAI_MOB_GROWTH_MUTATION_ENABLED,
                MutationDeathWindowMinutes = Math.Max(1, Properties.WORLDAI_MOB_GROWTH_MUTATION_DEATH_WINDOW_MINUTES),
                MutationDeathThreshold = Math.Max(1, Properties.WORLDAI_MOB_GROWTH_MUTATION_DEATH_THRESHOLD),
                MutationChanceStepPercent = Math.Clamp(Properties.WORLDAI_MOB_GROWTH_MUTATION_CHANCE_STEP_PERCENT, 0, 100),
                MutationMaxChancePercent = Math.Clamp(Properties.WORLDAI_MOB_GROWTH_MUTATION_MAX_CHANCE_PERCENT, 0, 100),
                MutationLevelBonus = Math.Clamp(Properties.WORLDAI_MOB_GROWTH_MUTATION_LEVEL_BONUS, 0, 10),
                MutationSizeBonusPercent = Math.Clamp(Properties.WORLDAI_MOB_GROWTH_MUTATION_SIZE_BONUS_PERCENT, 0, 200),
                EliteSizeBonusPercent = Math.Clamp(Properties.WORLDAI_MOB_GROWTH_ELITE_SIZE_BONUS_PERCENT, 0, 200),
                ChampionSizeBonusPercent = Math.Clamp(Properties.WORLDAI_MOB_GROWTH_CHAMPION_SIZE_BONUS_PERCENT, 0, 200),
                BossSizeBonusPercent = Math.Clamp(Properties.WORLDAI_MOB_GROWTH_BOSS_SIZE_BONUS_PERCENT, 0, 200),
                MutationSpellPool = Properties.WORLDAI_MOB_GROWTH_MUTATION_SPELL_POOL ?? string.Empty,
                EliteSpellPool = Properties.WORLDAI_MOB_GROWTH_ELITE_SPELL_POOL ?? string.Empty,
                ChampionSpellPool = Properties.WORLDAI_MOB_GROWTH_CHAMPION_SPELL_POOL ?? string.Empty,
                BossSpellPool = Properties.WORLDAI_MOB_GROWTH_BOSS_SPELL_POOL ?? string.Empty,
                MutationStylePool = Properties.WORLDAI_MOB_GROWTH_MUTATION_STYLE_POOL ?? string.Empty,
                EliteStylePool = Properties.WORLDAI_MOB_GROWTH_ELITE_STYLE_POOL ?? string.Empty,
                ChampionStylePool = Properties.WORLDAI_MOB_GROWTH_CHAMPION_STYLE_POOL ?? string.Empty,
                BossStylePool = Properties.WORLDAI_MOB_GROWTH_BOSS_STYLE_POOL ?? string.Empty,
                MutationAbilityPool = Properties.WORLDAI_MOB_GROWTH_MUTATION_ABILITY_POOL ?? string.Empty,
                EliteAbilityPool = Properties.WORLDAI_MOB_GROWTH_ELITE_ABILITY_POOL ?? string.Empty,
                ChampionAbilityPool = Properties.WORLDAI_MOB_GROWTH_CHAMPION_ABILITY_POOL ?? string.Empty,
                BossAbilityPool = Properties.WORLDAI_MOB_GROWTH_BOSS_ABILITY_POOL ?? string.Empty
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
                MaxActiveBosses = 5,
                MaxActiveBossesPerRegion = 1,
                ProtectedRegions = "27",
                ProtectedNameTokens = "quest;trainer;merchant;master;훈련;상인;퀘스트",
                MinimumEligibleLevel = 5,
                LowLevelMaxBaseLevel = 15,
                LowLevelMaxStage = MobGrowthStages.Elite,
                DecayEnabled = true,
                DecayAfterMinutes = 720,
                DecayScore = 60,
                ResetInactiveAfterMinutes = 10080,
                MutationEnabled = true,
                MutationDeathWindowMinutes = 10,
                MutationDeathThreshold = 5,
                MutationChanceStepPercent = 10,
                MutationMaxChancePercent = 100,
                MutationLevelBonus = 2,
                MutationSizeBonusPercent = 15,
                EliteSizeBonusPercent = 10,
                ChampionSizeBonusPercent = 25,
                BossSizeBonusPercent = 45
            };
        }

        public bool IsRegionExcluded(ushort regionId)
        {
            return IsRegionInList(regionId, ExcludedRegions);
        }

        public bool IsRegionProtected(ushort regionId)
        {
            return IsRegionInList(regionId, ProtectedRegions);
        }

        public bool IsProtectedName(string name)
        {
            if (string.IsNullOrWhiteSpace(ProtectedNameTokens) || string.IsNullOrWhiteSpace(name))
                return false;

            string normalizedName = name.Trim();
            return ProtectedNameTokens
                .Split(new[] { ';', ',' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(part => part.Trim())
                .Any(part => part.Length > 0 && normalizedName.IndexOf(part, StringComparison.OrdinalIgnoreCase) >= 0);
        }

        private static bool IsRegionInList(ushort regionId, string regions)
        {
            if (string.IsNullOrWhiteSpace(regions))
                return false;

            return regions
                .Split(new[] { ';', ',' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(part => part.Trim())
                .Any(part => ushort.TryParse(part, out ushort value) && value == regionId);
        }

        private static string NormalizeOptionStage(string stage)
        {
            if (string.Equals(stage, MobGrowthStages.Elite, StringComparison.OrdinalIgnoreCase))
                return MobGrowthStages.Elite;
            if (string.Equals(stage, MobGrowthStages.Champion, StringComparison.OrdinalIgnoreCase))
                return MobGrowthStages.Champion;
            if (string.Equals(stage, MobGrowthStages.Boss, StringComparison.OrdinalIgnoreCase))
                return MobGrowthStages.Boss;

            return MobGrowthStages.Normal;
        }
    }

    public sealed class MobGrowthDecayResult
    {
        public int Scanned { get; set; }
        public int Decayed { get; set; }
        public int Demoted { get; set; }
        public int ResetInactive { get; set; }
    }

    public sealed class MobGrowthBonusPoolValidation
    {
        public int ValidEntries { get; set; }
        public IList<string> Errors { get; set; } = Array.Empty<string>();
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
        public int ObjectId { get; set; }
        public int X { get; set; }
        public int Y { get; set; }
        public int Z { get; set; }
        public ushort Heading { get; set; }
        public bool IsAlive { get; set; }
        public bool IsMutant { get; set; }
        public int BaseLevel { get; set; }
        public int EffectiveLevel { get; set; }
        public int BaseSize { get; set; }
        public int EffectiveSize { get; set; }
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
        private readonly IMobGrowthRandom m_random;

        public MobGrowthService(IMobGrowthRepository growth, WorldEventService worldEvents, IMobGrowthRandom random = null)
        {
            m_growth = growth ?? throw new ArgumentNullException(nameof(growth));
            m_worldEvents = worldEvents ?? throw new ArgumentNullException(nameof(worldEvents));
            m_random = random ?? new MobGrowthRandom();
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
            {
                if (!CanProcess(observation, options))
                    return null;

                state = GetOrCreate(observation, now);
            }

            RecordDeathWindow(state, now, options);
            state.IsActive = false;
            state.IsMutant = false;
            state.LastKilledAt = now;
            state.UpdatedAt = now;
            Save(state);
            return state;
        }

        public IList<DbMobGrowthState> GetTopActive(int limit)
        {
            return m_growth.GetTopActive(Math.Clamp(limit, 1, 100));
        }

        public IList<DbMobGrowthState> GetActive(int limit)
        {
            return m_growth.GetActive(Math.Clamp(limit, 1, 10000));
        }

        public IList<DbMobGrowthState> GetAll(int limit)
        {
            return m_growth.GetAll(Math.Clamp(limit, 1, 10000));
        }

        public MobGrowthSummary GetSummary(int topLimit)
        {
            return GetSummary(topLimit, 0);
        }

        public MobGrowthSummary GetSummary(int topLimit, ushort topRegionId)
        {
            MobGrowthOptions options = MobGrowthOptions.FromProperties();
            int limit = Math.Clamp(topLimit, 1, 100);
            IList<DbMobGrowthState> active = m_growth.GetActive(10000);
            IEnumerable<DbMobGrowthState> topRows = topRegionId > 0
                ? active
                    .Where(row => row.RegionId == topRegionId)
                    .OrderByDescending(row => row.GrowthScore)
                    .Take(limit)
                : m_growth.GetTopActive(limit);

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
                Top = topRows
                    .Select(ToTopMob)
                    .ToList()
            };
        }

        public bool Reset(string mobId)
        {
            DbMobGrowthState state = m_growth.Find(mobId);
            return state != null && m_growth.Delete(state);
        }

        public MobGrowthDecayResult DecayStaleActive(DateTime now, MobGrowthOptions options, int limit)
        {
            MobGrowthDecayResult result = new();

            if (options == null || !options.DecayEnabled)
                return result;

            foreach (DbMobGrowthState state in m_growth.GetAll(Math.Clamp(limit, 1, 10000)))
            {
                result.Scanned++;

                if (state.IsActive)
                {
                    if (now - state.LastSeenAt < TimeSpan.FromMinutes(options.DecayAfterMinutes))
                        continue;

                    string previousStage = state.Stage;
                    state.GrowthScore = Math.Max(0, state.GrowthScore - options.DecayScore);
                    state.Stage = ResolveStage(state, options);
                    state.IsMutant = false;
                    state.MutationPending = false;
                    RefreshForcedDerivedState(state, options);
                    Save(state);

                    result.Decayed++;
                    if (StageOrder(state.Stage) < StageOrder(previousStage))
                        result.Demoted++;

                    continue;
                }

                if (state.LastSeenAt != DateTime.MinValue &&
                    now - state.LastSeenAt >= TimeSpan.FromMinutes(options.ResetInactiveAfterMinutes) &&
                    m_growth.Delete(state))
                {
                    result.ResetInactive++;
                }
            }

            return result;
        }

        public static MobGrowthBonusPoolValidation ValidateBonusPools(MobGrowthOptions options)
        {
            List<string> errors = new();
            int validEntries = 0;

            ValidateSpellPool(nameof(options.MutationSpellPool), options.MutationSpellPool, errors, ref validEntries);
            ValidateSpellPool(nameof(options.EliteSpellPool), options.EliteSpellPool, errors, ref validEntries);
            ValidateSpellPool(nameof(options.ChampionSpellPool), options.ChampionSpellPool, errors, ref validEntries);
            ValidateSpellPool(nameof(options.BossSpellPool), options.BossSpellPool, errors, ref validEntries);
            ValidateStylePool(nameof(options.MutationStylePool), options.MutationStylePool, errors, ref validEntries);
            ValidateStylePool(nameof(options.EliteStylePool), options.EliteStylePool, errors, ref validEntries);
            ValidateStylePool(nameof(options.ChampionStylePool), options.ChampionStylePool, errors, ref validEntries);
            ValidateStylePool(nameof(options.BossStylePool), options.BossStylePool, errors, ref validEntries);
            ValidateAbilityPool(nameof(options.MutationAbilityPool), options.MutationAbilityPool, errors, ref validEntries);
            ValidateAbilityPool(nameof(options.EliteAbilityPool), options.EliteAbilityPool, errors, ref validEntries);
            ValidateAbilityPool(nameof(options.ChampionAbilityPool), options.ChampionAbilityPool, errors, ref validEntries);
            ValidateAbilityPool(nameof(options.BossAbilityPool), options.BossAbilityPool, errors, ref validEntries);

            return new MobGrowthBonusPoolValidation
            {
                ValidEntries = validEntries,
                Errors = errors
            };
        }

        public IList<string> BuildQuestKillSignals(GameNPC npc)
        {
            MobGrowthObservation observation = FromNpc(npc);
            if (observation == null || string.IsNullOrWhiteSpace(observation.MobId))
                return Array.Empty<string>();

            return BuildQuestKillSignals(m_growth.Find(observation.MobId), observation);
        }

        internal static IList<string> BuildQuestKillSignalsForTest(DbMobGrowthState state, MobGrowthObservation observation)
        {
            return BuildQuestKillSignals(state, observation);
        }

        internal static bool IsProcessableForTest(MobGrowthObservation observation, MobGrowthOptions options)
        {
            return CanProcess(observation, options);
        }

        public DbMobGrowthState ForceStage(string mobId, string stage, MobGrowthOptions options)
        {
            DbMobGrowthState state = m_growth.Find(mobId);

            if (state == null || options == null)
                return null;

            state.Stage = NormalizeStage(stage);
            state.GrowthScore = MinimumScoreForStage(state.Stage, options);
            RefreshForcedDerivedState(state, options);
            Save(state);
            return state;
        }

        public DbMobGrowthState ForceMutation(string mobId, bool enabled, MobGrowthOptions options)
        {
            DbMobGrowthState state = m_growth.Find(mobId);

            if (state == null || options == null)
                return null;

            if (enabled && !state.IsMutant)
                state.MutationCount++;

            state.IsMutant = enabled;
            state.MutationPending = false;
            state.LastMutationAt = enabled ? DateTime.UtcNow : state.LastMutationAt;
            RefreshForcedDerivedState(state, options);
            Save(state);
            return state;
        }

        public DbMobGrowthState SetRecentDeathCount(string mobId, int count, DateTime now)
        {
            DbMobGrowthState state = m_growth.Find(mobId);

            if (state == null)
                return null;

            state.RecentDeathCount = Math.Max(0, count);
            state.DeathWindowStartedAt = state.RecentDeathCount > 0 ? now : DateTime.MinValue;
            state.LastMutationChancePercent = 0;
            state.UpdatedAt = DateTime.UtcNow;
            Save(state);
            return state;
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
                Size = npc.Size,
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
            MobGrowthOptions options = MobGrowthOptions.FromProperties();

            if (state == null)
            {
                npc.WorldAiMaxHealthScalingFactor = 1.0;
                return;
            }

            if (state.MutationPending)
            {
                RefreshDerivedState(state, FromNpc(npc), options);
                Save(state);
            }

            if (state.Stage == MobGrowthStages.Normal && !state.IsMutant)
            {
                npc.WorldAiMaxHealthScalingFactor = 1.0;
                return;
            }

            npc.Name = state.CurrentName;
            npc.Level = (byte)Math.Clamp(state.EffectiveLevel, 1, byte.MaxValue);
            if (state.EffectiveSize > 0)
                npc.Size = (byte)Math.Clamp(state.EffectiveSize, 1, byte.MaxValue);
            npc.WorldAiMaxHealthScalingFactor = GetHealthMultiplier(state, options);
            ApplyBonusLoadout(npc, state);
            ApplyBrainModifiers(npc, state);
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
                BaseSize = ResolveBaseSize(observation),
                EffectiveSize = ResolveBaseSize(observation),
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
                observation.Level >= options.MinimumEligibleLevel &&
                !string.IsNullOrWhiteSpace(observation.MobId) &&
                !options.IsRegionExcluded(observation.RegionId) &&
                !options.IsRegionProtected(observation.RegionId) &&
                !options.IsProtectedName(observation.Name);
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
            state.BaseSize = state.BaseSize <= 0 ? ResolveBaseSize(observation) : state.BaseSize;
            bool mutationActivated = ActivatePendingMutation(state, options);
            state.Stage = ResolveStage(state, options);
            state.GrowthLevel = Math.Clamp(ResolveLevelBonus(state.Stage, state.IsMutant, options), 0, options.MaxLevelBonus);
            state.EffectiveLevel = Math.Clamp(state.BaseLevel + state.GrowthLevel, 1, byte.MaxValue);
            state.EffectiveSize = ResolveEffectiveSize(state.BaseSize, state.Stage, state.IsMutant, options);
            state.CurrentName = BuildCurrentName(state.BaseName, state.Stage, state.IsMutant);
            RefreshBonusLoadout(state, options);
            state.UpdatedAt = DateTime.UtcNow;

            if (mutationActivated)
                PublishMutationEvent(state, observation);
        }

        private string ResolveStage(DbMobGrowthState state, MobGrowthOptions options)
        {
            string resolvedStage;

            if (state.GrowthScore >= options.BossScore)
            {
                if (state.Stage == MobGrowthStages.Boss)
                    resolvedStage = MobGrowthStages.Boss;
                else
                    resolvedStage = CanPromoteToBoss(state, options)
                        ? MobGrowthStages.Boss
                        : MobGrowthStages.Champion;
            }
            else if (state.GrowthScore >= options.ChampionScore)
            {
                resolvedStage = MobGrowthStages.Champion;
            }
            else if (state.GrowthScore >= options.EliteScore)
            {
                resolvedStage = MobGrowthStages.Elite;
            }
            else
            {
                resolvedStage = MobGrowthStages.Normal;
            }

            return CapStageForLowLevel(state, options, resolvedStage);
        }

        private bool CanPromoteToBoss(DbMobGrowthState state, MobGrowthOptions options)
        {
            if (options.MaxActiveBosses > 0 && m_growth.CountActiveBosses() >= options.MaxActiveBosses)
                return false;

            if (options.MaxActiveBossesPerRegion > 0 &&
                m_growth.CountActiveBossesInRegion(state.RegionId) >= options.MaxActiveBossesPerRegion)
            {
                return false;
            }

            return true;
        }

        private static string CapStageForLowLevel(DbMobGrowthState state, MobGrowthOptions options, string stage)
        {
            if (state.BaseLevel <= 0 ||
                options.LowLevelMaxBaseLevel <= 0 ||
                state.BaseLevel > options.LowLevelMaxBaseLevel)
            {
                return stage;
            }

            string cap = NormalizeStage(options.LowLevelMaxStage);
            return StageOrder(stage) > StageOrder(cap) ? cap : stage;
        }

        private static string NormalizeStage(string stage)
        {
            if (string.Equals(stage, MobGrowthStages.Elite, StringComparison.OrdinalIgnoreCase))
                return MobGrowthStages.Elite;
            if (string.Equals(stage, MobGrowthStages.Champion, StringComparison.OrdinalIgnoreCase))
                return MobGrowthStages.Champion;
            if (string.Equals(stage, MobGrowthStages.Boss, StringComparison.OrdinalIgnoreCase))
                return MobGrowthStages.Boss;

            return MobGrowthStages.Normal;
        }

        private static IList<string> BuildQuestKillSignals(DbMobGrowthState state, MobGrowthObservation observation)
        {
            if (observation == null)
                return Array.Empty<string>();

            string stage = NormalizeStage(state?.Stage);
            if (stage == MobGrowthStages.Normal)
                stage = ResolveStageFromName(observation.Name);

            bool isMutant = state?.IsMutant == true || HasMobGrowthPrefix(observation.Name, "돌연변이 ");
            if (stage == MobGrowthStages.Normal && !isMutant)
                return Array.Empty<string>();

            List<string> signals = new();

            if (!string.IsNullOrWhiteSpace(observation.MobId))
                AddSignal(signals, $"mob-growth:killed:mob:{observation.MobId.Trim()}");

            if (stage != MobGrowthStages.Normal)
            {
                string stageValue = stage.ToLowerInvariant();
                AddSignal(signals, $"mob-growth:killed:{stageValue}");
                AddSignal(signals, $"mob-growth:killed:stage:{stageValue}");
            }

            if (isMutant)
                AddSignal(signals, "mob-growth:killed:mutant");

            if (observation.RegionId > 0)
                AddSignal(signals, $"mob-growth:killed:region:{observation.RegionId}");

            AddSignal(signals, "mob-growth:killed");
            return signals;
        }

        private static string ResolveStageFromName(string name)
        {
            if (HasMobGrowthPrefix(name, "우두머리 "))
                return MobGrowthStages.Boss;
            if (HasMobGrowthPrefix(name, "흉포한 ") || HasMobGrowthPrefix(name, "챔피언 "))
                return MobGrowthStages.Champion;
            if (HasMobGrowthPrefix(name, "노련한 ") || HasMobGrowthPrefix(name, "정예 "))
                return MobGrowthStages.Elite;

            return MobGrowthStages.Normal;
        }

        private static bool HasMobGrowthPrefix(string name, string prefix)
        {
            string normalized = (name ?? string.Empty).Trim();
            if (normalized.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                return true;

            if (normalized.StartsWith("돌연변이 ", StringComparison.OrdinalIgnoreCase))
                normalized = normalized.Substring("돌연변이 ".Length).TrimStart();

            return normalized.StartsWith(prefix, StringComparison.OrdinalIgnoreCase);
        }

        private static void AddSignal(List<string> signals, string signal)
        {
            if (string.IsNullOrWhiteSpace(signal) ||
                signals.Any(existing => string.Equals(existing, signal, StringComparison.OrdinalIgnoreCase)))
            {
                return;
            }

            signals.Add(signal);
        }

        private static int MinimumScoreForStage(string stage, MobGrowthOptions options)
        {
            if (stage == MobGrowthStages.Boss)
                return options.BossScore;
            if (stage == MobGrowthStages.Champion)
                return options.ChampionScore;
            if (stage == MobGrowthStages.Elite)
                return options.EliteScore;

            return 0;
        }

        private void RefreshForcedDerivedState(DbMobGrowthState state, MobGrowthOptions options)
        {
            state.BaseSize = state.BaseSize <= 0 ? 50 : state.BaseSize;
            state.BaseLevel = state.BaseLevel <= 0 ? 1 : state.BaseLevel;
            state.GrowthLevel = Math.Clamp(ResolveLevelBonus(state.Stage, state.IsMutant, options), 0, options.MaxLevelBonus + options.MutationLevelBonus);
            state.EffectiveLevel = Math.Clamp(state.BaseLevel + state.GrowthLevel, 1, byte.MaxValue);
            state.EffectiveSize = ResolveEffectiveSize(state.BaseSize, state.Stage, state.IsMutant, options);
            state.CurrentName = BuildCurrentName(state.BaseName, state.Stage, state.IsMutant);
            state.BonusLoadoutKey = string.Empty;
            RefreshBonusLoadout(state, options);
            state.UpdatedAt = DateTime.UtcNow;
        }

        private static int ResolveLevelBonus(string stage, bool isMutant, MobGrowthOptions options)
        {
            int levelBonus = 0;

            if (stage == MobGrowthStages.Boss)
                levelBonus = options.MaxLevelBonus;
            else if (stage == MobGrowthStages.Champion)
                levelBonus = Math.Max(2, options.MaxLevelBonus * 2 / 3);
            else if (stage == MobGrowthStages.Elite)
                levelBonus = 1;

            if (isMutant)
                levelBonus = Math.Max(levelBonus, 1) + Math.Max(0, options.MutationLevelBonus);

            return levelBonus;
        }

        private static string BuildCurrentName(string baseName, string stage, bool isMutant)
        {
            if (string.IsNullOrWhiteSpace(baseName))
                return string.Empty;

            string currentName = baseName;

            if (stage == MobGrowthStages.Elite)
                currentName = $"노련한 {baseName}";
            else if (stage == MobGrowthStages.Champion)
                currentName = $"흉포한 {baseName}";
            else if (stage == MobGrowthStages.Boss)
                currentName = $"우두머리 {baseName}";

            return isMutant ? $"돌연변이 {currentName}" : currentName;
        }

        private void RecordDeathWindow(DbMobGrowthState state, DateTime now, MobGrowthOptions options)
        {
            if (state == null || options == null || !options.Enabled)
                return;

            TimeSpan window = TimeSpan.FromMinutes(Math.Max(1, options.MutationDeathWindowMinutes));

            if (state.DeathWindowStartedAt == DateTime.MinValue || now - state.DeathWindowStartedAt > window)
            {
                state.DeathWindowStartedAt = now;
                state.RecentDeathCount = 0;
            }

            state.RecentDeathCount++;

            if (!options.MutationEnabled || state.MutationPending)
                return;

            int threshold = Math.Max(1, options.MutationDeathThreshold);

            if (state.RecentDeathCount < threshold)
                return;

            int overThreshold = state.RecentDeathCount - threshold + 1;
            int chance = Math.Clamp(overThreshold * Math.Max(0, options.MutationChanceStepPercent), 0, Math.Clamp(options.MutationMaxChancePercent, 0, 100));
            state.LastMutationChancePercent = chance;

            if (chance <= 0)
                return;

            if (m_random.NextInclusive(1, 100) <= chance)
            {
                state.MutationPending = true;
                state.MutationCount++;
            }
        }

        private static bool ActivatePendingMutation(DbMobGrowthState state, MobGrowthOptions options)
        {
            if (state == null || options == null || !options.MutationEnabled || !state.MutationPending)
                return false;

            state.IsMutant = true;
            state.MutationPending = false;
            state.LastMutationAt = DateTime.UtcNow;
            return true;
        }

        private static int ResolveBaseSize(MobGrowthObservation observation)
        {
            return Math.Clamp(observation?.Size ?? 50, 1, byte.MaxValue);
        }

        private static int ResolveEffectiveSize(int baseSize, string stage, bool isMutant, MobGrowthOptions options)
        {
            int bonusPercent = 0;

            if (stage == MobGrowthStages.Boss)
                bonusPercent += Math.Max(0, options.BossSizeBonusPercent);
            else if (stage == MobGrowthStages.Champion)
                bonusPercent += Math.Max(0, options.ChampionSizeBonusPercent);
            else if (stage == MobGrowthStages.Elite)
                bonusPercent += Math.Max(0, options.EliteSizeBonusPercent);

            if (isMutant)
                bonusPercent += Math.Max(0, options.MutationSizeBonusPercent);

            return Math.Clamp((int)Math.Round(Math.Max(1, baseSize) * (100 + bonusPercent) / 100.0), 1, byte.MaxValue);
        }

        private void RefreshBonusLoadout(DbMobGrowthState state, MobGrowthOptions options)
        {
            string loadoutKey = $"{state.Stage}:{state.IsMutant}";

            if (state.BonusLoadoutKey == loadoutKey)
                return;

            int pickCount = ResolveBonusPickCount(state.Stage, state.IsMutant);

            if (pickCount <= 0)
            {
                state.BonusLoadoutKey = loadoutKey;
                state.BonusSpellIds = string.Empty;
                state.BonusStyleIds = string.Empty;
                state.BonusAbilityKeys = string.Empty;
                return;
            }

            state.BonusLoadoutKey = loadoutKey;
            state.BonusSpellIds = string.Join(";", PickDistinct(BuildSpellPool(state.Stage, state.IsMutant, options), pickCount));
            state.BonusStyleIds = string.Join(";", PickDistinct(BuildStylePool(state.Stage, state.IsMutant, options), pickCount));
            state.BonusAbilityKeys = string.Join(";", PickDistinct(BuildAbilityPool(state.Stage, state.IsMutant, options), pickCount));
        }

        private static int ResolveBonusPickCount(string stage, bool isMutant)
        {
            int pickCount = StageOrder(stage);

            if (isMutant)
                pickCount++;

            return Math.Clamp(pickCount, 0, 4);
        }

        private static List<string> BuildSpellPool(string stage, bool isMutant, MobGrowthOptions options)
        {
            List<string> pool = new();
            int rank = StageOrder(stage);

            if (isMutant)
                pool.AddRange(SplitPool(options.MutationSpellPool));
            if (rank >= StageOrder(MobGrowthStages.Elite))
                pool.AddRange(SplitPool(options.EliteSpellPool));
            if (rank >= StageOrder(MobGrowthStages.Champion))
                pool.AddRange(SplitPool(options.ChampionSpellPool));
            if (rank >= StageOrder(MobGrowthStages.Boss))
                pool.AddRange(SplitPool(options.BossSpellPool));

            return pool;
        }

        private static List<string> BuildStylePool(string stage, bool isMutant, MobGrowthOptions options)
        {
            List<string> pool = new();
            int rank = StageOrder(stage);

            if (isMutant)
                pool.AddRange(SplitPool(options.MutationStylePool));
            if (rank >= StageOrder(MobGrowthStages.Elite))
                pool.AddRange(SplitPool(options.EliteStylePool));
            if (rank >= StageOrder(MobGrowthStages.Champion))
                pool.AddRange(SplitPool(options.ChampionStylePool));
            if (rank >= StageOrder(MobGrowthStages.Boss))
                pool.AddRange(SplitPool(options.BossStylePool));

            return pool;
        }

        private static List<string> BuildAbilityPool(string stage, bool isMutant, MobGrowthOptions options)
        {
            List<string> pool = new();
            int rank = StageOrder(stage);

            if (isMutant)
                pool.AddRange(SplitPool(options.MutationAbilityPool));
            if (rank >= StageOrder(MobGrowthStages.Elite))
                pool.AddRange(SplitPool(options.EliteAbilityPool));
            if (rank >= StageOrder(MobGrowthStages.Champion))
                pool.AddRange(SplitPool(options.ChampionAbilityPool));
            if (rank >= StageOrder(MobGrowthStages.Boss))
                pool.AddRange(SplitPool(options.BossAbilityPool));

            return pool;
        }

        private static IEnumerable<string> SplitPool(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return Array.Empty<string>();

            return value
                .Split(new[] { ';', ',' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(part => part.Trim())
                .Where(part => part.Length > 0)
                .Distinct(StringComparer.OrdinalIgnoreCase);
        }

        private List<string> PickDistinct(IEnumerable<string> pool, int pickCount)
        {
            List<string> candidates = pool
                .Where(value => !string.IsNullOrWhiteSpace(value))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();
            List<string> selected = new();

            while (selected.Count < pickCount && candidates.Count > 0)
            {
                int index = m_random.NextInclusive(0, candidates.Count - 1);
                selected.Add(candidates[index]);
                candidates.RemoveAt(index);
            }

            return selected;
        }

        private static void ApplyBonusLoadout(GameNPC npc, DbMobGrowthState state)
        {
            ApplyBonusSpells(npc, state.BonusSpellIds);
            ApplyBonusStyles(npc, state.BonusStyleIds);
            ApplyBonusAbilities(npc, state.BonusAbilityKeys);
        }

        private static void ApplyBrainModifiers(GameNPC npc, DbMobGrowthState state)
        {
            if (npc?.Brain is not StandardMobBrain brain || state == null)
                return;

            int minimumAggroLevel = 0;
            int minimumAggroRange = 0;

            if (state.Stage == MobGrowthStages.Boss)
            {
                minimumAggroLevel = 85;
                minimumAggroRange = 1200;
            }
            else if (state.Stage == MobGrowthStages.Champion)
            {
                minimumAggroLevel = 60;
                minimumAggroRange = 850;
            }
            else if (state.Stage == MobGrowthStages.Elite)
            {
                minimumAggroLevel = 35;
                minimumAggroRange = 600;
            }

            if (state.IsMutant)
            {
                minimumAggroLevel = Math.Max(minimumAggroLevel, 45);
                minimumAggroRange += 150;
            }

            if (minimumAggroLevel > 0)
                brain.AggroLevel = Math.Max(brain.AggroLevel, minimumAggroLevel);

            if (minimumAggroRange > 0)
                brain.AggroRange = Math.Min(StandardMobBrain.MAX_AGGRO_DISTANCE, Math.Max(brain.AggroRange, minimumAggroRange));
        }

        private static void ApplyBonusSpells(GameNPC npc, string spellIds)
        {
            List<int> ids = SplitPool(spellIds)
                .Select(part => int.TryParse(part, out int id) ? id : 0)
                .Where(id => id > 0)
                .ToList();

            if (ids.Count == 0)
                return;

            List<Spell> spells = npc.Spells?.ToList() ?? new List<Spell>();
            bool changed = false;

            foreach (int id in ids)
            {
                Spell spell = SkillBase.GetSpellByID(id);

                if (spell == null || spells.Any(existing => existing != null && existing.ID == spell.ID))
                    continue;

                spells.Add(spell);
                changed = true;
            }

            if (changed)
                npc.Spells = spells;
        }

        private static void ApplyBonusStyles(GameNPC npc, string styleIds)
        {
            List<Style> styles = npc.Styles?.ToList() ?? new List<Style>();
            bool changed = false;

            foreach (string entry in SplitPool(styleIds))
            {
                string[] parts = entry.Split('|');

                if (parts.Length != 2 ||
                    !int.TryParse(parts[0].Trim(), out int styleId) ||
                    !int.TryParse(parts[1].Trim(), out int classId))
                {
                    continue;
                }

                Style style = SkillBase.GetStyleByID(styleId, classId);

                if (style == null || styles.Any(existing => existing != null && existing.ID == style.ID && existing.ClassID == style.ClassID))
                    continue;

                styles.Add(style);
                changed = true;
            }

            if (changed)
                npc.Styles = styles;
        }

        private static void ApplyBonusAbilities(GameNPC npc, string abilityKeys)
        {
            foreach (string entry in SplitPool(abilityKeys))
            {
                string[] parts = entry.Split('|');
                string key = parts[0].Trim();
                int level = 1;

                if (parts.Length > 1 && int.TryParse(parts[1].Trim(), out int parsedLevel))
                    level = Math.Max(1, parsedLevel);

                if (SkillBase.TryGetAbility(key, level, out Ability ability))
                    npc.AddAbility(ability, false);
            }
        }

        private static void ValidateSpellPool(string poolName, string pool, IList<string> errors, ref int validEntries)
        {
            bool hasEntry = false;

            foreach (string entry in SplitPool(pool))
            {
                hasEntry = true;

                if (!int.TryParse(entry, out int spellId) || spellId <= 0)
                {
                    errors.Add($"{poolName}: invalid spell id '{entry}'");
                    continue;
                }

                validEntries++;
            }

            if (!hasEntry && poolName.Contains("Boss", StringComparison.OrdinalIgnoreCase))
                errors.Add($"{poolName}: empty pool");
        }

        private static void ValidateStylePool(string poolName, string pool, IList<string> errors, ref int validEntries)
        {
            foreach (string entry in SplitPool(pool))
            {
                string[] parts = entry.Split('|');

                if (parts.Length != 2 ||
                    !int.TryParse(parts[0].Trim(), out int styleId) ||
                    styleId <= 0 ||
                    !int.TryParse(parts[1].Trim(), out int classId) ||
                    classId <= 0)
                {
                    errors.Add($"{poolName}: invalid style entry '{entry}'");
                    continue;
                }

                validEntries++;
            }
        }

        private static void ValidateAbilityPool(string poolName, string pool, IList<string> errors, ref int validEntries)
        {
            bool hasEntry = false;

            foreach (string entry in SplitPool(pool))
            {
                hasEntry = true;
                string[] parts = entry.Split('|');

                if (string.IsNullOrWhiteSpace(parts[0]))
                {
                    errors.Add($"{poolName}: invalid ability entry '{entry}'");
                    continue;
                }

                if (parts.Length > 1 && (!int.TryParse(parts[1].Trim(), out int level) || level <= 0))
                {
                    errors.Add($"{poolName}: invalid ability level '{entry}'");
                    continue;
                }

                validEntries++;
            }

            if (!hasEntry && poolName.Contains("Boss", StringComparison.OrdinalIgnoreCase))
                errors.Add($"{poolName}: empty pool");
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

        private void PublishMutationEvent(DbMobGrowthState state, MobGrowthObservation observation)
        {
            string rawDataJson = JsonSerializer.Serialize(new
            {
                source = "mob_growth",
                stage = state.Stage,
                mutant = true,
                mutationCount = state.MutationCount,
                recentDeathCount = state.RecentDeathCount,
                chance = state.LastMutationChancePercent,
                location = new
                {
                    name = WorldAiEventTypes.MobMutated,
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
                EventType = WorldAiEventTypes.MobMutated,
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
                RequiresGmApproval = false
            });
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
            GameNPC npc = FindLiveGrowthNpc(row);
            return new MobGrowthTopMob
            {
                MobId = row.MobId,
                Name = npc?.Name ?? row.CurrentName,
                Stage = row.Stage,
                Region = row.Region,
                RegionId = row.RegionId,
                ObjectId = npc?.ObjectID ?? 0,
                X = npc?.X ?? 0,
                Y = npc?.Y ?? 0,
                Z = npc?.Z ?? 0,
                Heading = npc?.Heading ?? 0,
                IsAlive = npc?.IsAlive == true,
                IsMutant = row.IsMutant,
                BaseLevel = row.BaseLevel,
                EffectiveLevel = row.EffectiveLevel,
                BaseSize = row.BaseSize,
                EffectiveSize = row.EffectiveSize,
                GrowthScore = row.GrowthScore,
                SurvivalTicks = row.SurvivalTicks,
                CombatCount = row.CombatCount,
                PlayerKills = row.PlayerKills,
                LastSeenAt = row.LastSeenAt
            };
        }

        private static GameNPC FindLiveGrowthNpc(DbMobGrowthState row)
        {
            if (row == null || string.IsNullOrWhiteSpace(row.MobId) || row.RegionId <= 0)
                return null;

            string mobId = row.MobId.Trim();
            return WorldMgr.GetNPCsFromRegion(row.RegionId)
                .FirstOrDefault(npc => npc != null &&
                    npc.IsAlive &&
                    string.Equals(npc.InternalID ?? string.Empty, mobId, StringComparison.OrdinalIgnoreCase));
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
                .Take(Math.Clamp(limit, 1, 10000))
                .ToList();
        }

        public IList<DbMobGrowthState> GetAll(int limit)
        {
            return GameServer.Database.SelectAllObjects<DbMobGrowthState>()
                .OrderByDescending(row => row.UpdatedAt)
                .Take(Math.Clamp(limit, 1, 10000))
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

        public int CountActiveBossesInRegion(ushort regionId)
        {
            return GameServer.Database.SelectAllObjects<DbMobGrowthState>()
                .Count(row => row.IsActive && row.RegionId == regionId && row.Stage == MobGrowthStages.Boss);
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
