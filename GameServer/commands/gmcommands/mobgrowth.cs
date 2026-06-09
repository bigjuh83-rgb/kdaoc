using System;
using System.Collections.Generic;
using System.Linq;
using DOL.Database;
using DOL.GS.PacketHandler;
using DOL.GS.ServerProperties;
using DOL.GS.WorldAI;

namespace DOL.GS.Commands
{
    [CmdAttribute(
        "&mobgrowth",
        ePrivLevel.GM,
        "WorldAI monster survival growth controls.",
        "/mobgrowth status",
        "/mobgrowth enable",
        "/mobgrowth disable",
        "/mobgrowth scan [limit]",
        "/mobgrowth top [limit|boss|mutant|region <regionId>]",
        "/mobgrowth region [regionId]",
        "/mobgrowth inspect",
        "/mobgrowth promote <normal|elite|champion|boss> [mobId|target]",
        "/mobgrowth mutate <on|off> [mobId|target]",
        "/mobgrowth deaths <count> [mobId|target]",
        "/mobgrowth decay [limit]",
        "/mobgrowth validatepools",
        "/mobgrowth reset <mobId|target>")]
    public class MobGrowthCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (client.Player == null)
                return;

            if (args.Length < 2)
            {
                DisplayUsage(client);
                return;
            }

            switch (args[1].ToLowerInvariant())
            {
                case "status":
                    DisplayStatus(client);
                    return;
                case "enable":
                    SetEnabled(client, true);
                    return;
                case "disable":
                    SetEnabled(client, false);
                    return;
                case "scan":
                    Scan(client, args);
                    return;
                case "top":
                    DisplayTop(client, args);
                    return;
                case "region":
                    DisplayRegions(client, args);
                    return;
                case "inspect":
                    InspectTarget(client);
                    return;
                case "promote":
                    Promote(client, args);
                    return;
                case "mutate":
                    Mutate(client, args);
                    return;
                case "deaths":
                    SetDeaths(client, args);
                    return;
                case "decay":
                    Decay(client, args);
                    return;
                case "validatepools":
                    ValidatePools(client);
                    return;
                case "reset":
                    Reset(client, args);
                    return;
                default:
                    DisplayUsage(client);
                    return;
            }
        }

        private static void DisplayStatus(GameClient client)
        {
            MobGrowthOptions options = MobGrowthOptions.FromProperties();
            IList<DbMobGrowthState> top = MobGrowthService.Instance.GetTopActive(10);
            int activeBosses = 0;

            foreach (DbMobGrowthState state in top)
            {
                if (state.Stage == MobGrowthStages.Boss)
                    activeBosses++;
            }

            client.Out.SendCustomTextWindow("Mob Growth Status", new List<string>
            {
                $"Enabled: {options.Enabled}",
                $"Tick minutes: {Properties.WORLDAI_MOB_GROWTH_TICK_MINUTES}",
                $"Scores: survival {options.SurvivalScorePerTick}, unhunted {options.UnhuntedScorePerTick}, combat {options.CombatScore}, player kill {options.PlayerKillScore}",
                $"Thresholds: Elite {options.EliteScore}, Champion {options.ChampionScore}, Boss {options.BossScore}",
                $"Caps: +{options.MaxLevelBonus} levels, x{options.MaxHealthMultiplier:0.00} health, active bosses advisory {options.MaxActiveBosses}",
                $"Mutation: enabled={options.MutationEnabled}, window={options.MutationDeathWindowMinutes}m, deaths={options.MutationDeathThreshold}+, +{options.MutationChanceStepPercent}% each, max={options.MutationMaxChancePercent}%",
                $"Size bonuses: mutant +{options.MutationSizeBonusPercent}%, elite +{options.EliteSizeBonusPercent}%, champion +{options.ChampionSizeBonusPercent}%, boss +{options.BossSizeBonusPercent}%",
                $"Safety: minLevel={options.MinimumEligibleLevel}, protectedRegions={Blank(options.ProtectedRegions)}, lowLevelCap<=L{options.LowLevelMaxBaseLevel}:{options.LowLevelMaxStage}, bossesPerRegion={options.MaxActiveBossesPerRegion}",
                $"Decay: enabled={options.DecayEnabled}, after={options.DecayAfterMinutes}m, score=-{options.DecayScore}, inactiveReset={options.ResetInactiveAfterMinutes}m",
                $"Top active tracked mobs loaded: {top.Count}",
                $"Bosses in top list: {activeBosses}"
            });
        }

        private static void SetEnabled(GameClient client, bool enabled)
        {
            Properties.WORLDAI_MOB_GROWTH_ENABLED = enabled;
            MobGrowthRuntime.RestartTimer();
            client.Out.SendMessage(enabled ? "몬스터 생존성장 시스템을 켰습니다." : "몬스터 생존성장 시스템을 껐습니다.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
        }

        private static void Scan(GameClient client, string[] args)
        {
            if (!Properties.WORLDAI_MOB_GROWTH_ENABLED)
            {
                client.Out.SendMessage("몬스터 생존성장 시스템이 꺼져 있습니다. /mobgrowth enable 후 사용하세요.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            int limit = 250;

            if (args.Length >= 3 && int.TryParse(args[2], out int requestedLimit))
                limit = Math.Clamp(requestedLimit, 1, 500);

            int scanned = MobGrowthService.Instance.ScanActiveWorld(limit);
            client.Out.SendMessage($"몬스터 생존성장 스캔 완료: {scanned}개 NPC 관측.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
        }

        private static void DisplayTop(GameClient client, string[] args)
        {
            int limit = 20;
            string filter = args.Length >= 3 ? args[2].ToLowerInvariant() : string.Empty;
            ushort regionId = 0;

            if (args.Length >= 3 && int.TryParse(args[2], out int requestedLimit))
            {
                limit = Math.Clamp(requestedLimit, 1, 100);
                filter = string.Empty;
            }
            else if (filter == "region" && args.Length >= 4 && ushort.TryParse(args[3], out ushort requestedRegionId))
            {
                regionId = requestedRegionId;
            }

            IEnumerable<DbMobGrowthState> top = regionId > 0
                ? MobGrowthService.Instance.GetActive(10000).Where(state => state.RegionId == regionId).OrderByDescending(state => state.GrowthScore).Take(limit)
                : MobGrowthService.Instance.GetTopActive(limit);

            if (filter == "boss")
                top = top.Where(state => state.Stage == MobGrowthStages.Boss);
            else if (filter == "mutant")
                top = top.Where(state => state.IsMutant || state.MutationPending);
            else if (!string.IsNullOrWhiteSpace(filter) && filter != "region")
                client.Out.SendMessage("필터는 boss, mutant, region <regionId> 중 하나입니다.", eChatType.CT_System, eChatLoc.CL_SystemWindow);

            List<string> lines = new();
            List<DbMobGrowthState> rows = top.ToList();

            if (rows.Count == 0)
                lines.Add("추적 중인 성장 몬스터가 없습니다.");

            foreach (DbMobGrowthState state in rows)
            {
                string mutation = state.IsMutant ? " mutant" : state.MutationPending ? " mutation-pending" : string.Empty;
                lines.Add($"{ShortId(state.MobId)} [{state.Stage}{mutation}] {state.CurrentName}");
                lines.Add($"  Lv {state.BaseLevel}->{state.EffectiveLevel}, size {state.BaseSize}->{state.EffectiveSize}, score={state.GrowthScore}, playerKills={state.PlayerKills}, combat={state.CombatCount}, deaths={state.RecentDeathCount}, chance={state.LastMutationChancePercent}%, region={state.Region}");
                lines.Add($"  Bonus: spells={Blank(state.BonusSpellIds)}, styles={Blank(state.BonusStyleIds)}, traits={Blank(state.BonusAbilityKeys)}");
            }

            client.Out.SendCustomTextWindow("Mob Growth Top", lines);
        }

        private static void DisplayRegions(GameClient client, string[] args)
        {
            ushort regionId = 0;

            if (args.Length >= 3)
                ushort.TryParse(args[2], out regionId);

            MobGrowthSummary summary = MobGrowthService.Instance.GetSummary(20, regionId);
            List<string> lines = new()
            {
                $"Active: {summary.ActiveCount}, bosses: {summary.ActiveBosses}/{summary.MaxActiveBosses}"
            };

            foreach (MobGrowthRegionSummary region in summary.Regions)
                lines.Add($"{region.RegionId} {Blank(region.Region)}: count={region.Count}, bosses={region.Bosses}, maxScore={region.MaxScore}");

            if (regionId > 0)
            {
                lines.Add("");
                lines.Add($"Top in region {regionId}:");
                foreach (MobGrowthTopMob mob in summary.Top)
                    lines.Add($"{ShortId(mob.MobId)} [{mob.Stage}{(mob.IsMutant ? " mutant" : string.Empty)}] {mob.Name} score={mob.GrowthScore} loc={mob.X},{mob.Y},{mob.Z}");
            }

            client.Out.SendCustomTextWindow("Mob Growth Regions", lines);
        }

        private static void InspectTarget(GameClient client)
        {
            if (client.Player.TargetObject is not GameNPC npc)
            {
                client.Out.SendMessage("대상 몬스터를 선택하고 다시 사용하세요.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            MobGrowthOptions options = MobGrowthOptions.FromProperties();
            DbMobGrowthState state = MobGrowthService.Instance.ObserveTick(MobGrowthService.FromNpc(npc), DateTime.UtcNow, options);

            if (state == null)
            {
                client.Out.SendMessage("이 대상은 성장 시스템 대상이 아닙니다.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            client.Out.SendCustomTextWindow("Mob Growth Inspect", new List<string>
            {
                $"MobId: {state.MobId}",
                $"Name: {state.CurrentName}",
                $"Stage: {state.Stage}",
                $"Mutant: active={state.IsMutant}, pending={state.MutationPending}, mutations={state.MutationCount}, last chance={state.LastMutationChancePercent}%",
                $"Level: {state.BaseLevel} -> {state.EffectiveLevel}",
                $"Size: {state.BaseSize} -> {state.EffectiveSize}",
                $"Score: {state.GrowthScore}",
                $"Survival ticks: {state.SurvivalTicks}",
                $"Unhunted ticks: {state.UnhuntedTicks}",
                $"Combat count: {state.CombatCount}",
                $"Player kills: {state.PlayerKills}",
                $"Recent deaths: {state.RecentDeathCount} since {state.DeathWindowStartedAt:yyyy-MM-dd HH:mm:ss}",
                $"Bonus spells: {state.BonusSpellIds}",
                $"Bonus styles: {state.BonusStyleIds}",
                $"Bonus traits: {state.BonusAbilityKeys}",
                $"Region: {state.Region} ({state.RegionId})",
                $"Last seen UTC: {state.LastSeenAt:yyyy-MM-dd HH:mm:ss}"
            });
        }

        private static void Promote(GameClient client, string[] args)
        {
            if (args.Length < 3)
            {
                client.Out.SendMessage("사용법: /mobgrowth promote <normal|elite|champion|boss> [mobId|target]", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            string stage = ParseStage(args[2]);

            if (stage == null)
            {
                client.Out.SendMessage("단계는 normal, elite, champion, boss 중 하나여야 합니다.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            string mobId = ResolveMobId(client, args, 3);

            if (string.IsNullOrWhiteSpace(mobId))
            {
                client.Out.SendMessage("대상 몬스터를 선택하거나 mobId를 입력하세요.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            DbMobGrowthState state = MobGrowthService.Instance.ForceStage(mobId, stage, MobGrowthOptions.FromProperties());

            if (state == null)
            {
                client.Out.SendMessage("해당 몬스터 성장 기록을 찾지 못했습니다. 먼저 /mobgrowth inspect 또는 /mobgrowth scan을 실행하세요.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            ApplyTargetIfSame(client, state);
            client.Out.SendMessage($"성장 단계 강제 변경: {state.CurrentName} [{state.Stage}]", eChatType.CT_System, eChatLoc.CL_SystemWindow);
        }

        private static void Mutate(GameClient client, string[] args)
        {
            if (args.Length < 3 || !TryParseToggle(args[2], out bool enabled))
            {
                client.Out.SendMessage("사용법: /mobgrowth mutate <on|off> [mobId|target]", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            string mobId = ResolveMobId(client, args, 3);

            if (string.IsNullOrWhiteSpace(mobId))
            {
                client.Out.SendMessage("대상 몬스터를 선택하거나 mobId를 입력하세요.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            DbMobGrowthState state = MobGrowthService.Instance.ForceMutation(mobId, enabled, MobGrowthOptions.FromProperties());

            if (state == null)
            {
                client.Out.SendMessage("해당 몬스터 성장 기록을 찾지 못했습니다. 먼저 /mobgrowth inspect 또는 /mobgrowth scan을 실행하세요.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            ApplyTargetIfSame(client, state);
            client.Out.SendMessage(enabled ? $"돌연변이 강제 적용: {state.CurrentName}" : $"돌연변이 해제: {state.CurrentName}", eChatType.CT_System, eChatLoc.CL_SystemWindow);
        }

        private static void SetDeaths(GameClient client, string[] args)
        {
            if (args.Length < 3 || !int.TryParse(args[2], out int count))
            {
                client.Out.SendMessage("사용법: /mobgrowth deaths <count> [mobId|target]", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            string mobId = ResolveMobId(client, args, 3);

            if (string.IsNullOrWhiteSpace(mobId))
            {
                client.Out.SendMessage("대상 몬스터를 선택하거나 mobId를 입력하세요.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            DbMobGrowthState state = MobGrowthService.Instance.SetRecentDeathCount(mobId, count, DateTime.UtcNow);

            if (state == null)
            {
                client.Out.SendMessage("해당 몬스터 성장 기록을 찾지 못했습니다. 먼저 /mobgrowth inspect 또는 /mobgrowth scan을 실행하세요.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            client.Out.SendMessage($"최근 사망 카운트 설정: {state.CurrentName} deaths={state.RecentDeathCount}", eChatType.CT_System, eChatLoc.CL_SystemWindow);
        }

        private static void Decay(GameClient client, string[] args)
        {
            int limit = 1000;

            if (args.Length >= 3 && int.TryParse(args[2], out int requestedLimit))
                limit = Math.Clamp(requestedLimit, 1, 10000);

            MobGrowthDecayResult result = MobGrowthService.Instance.DecayStaleActive(DateTime.UtcNow, MobGrowthOptions.FromProperties(), limit);
            client.Out.SendMessage($"성장 몬스터 쇠퇴 정리: scanned={result.Scanned}, decayed={result.Decayed}, demoted={result.Demoted}, resetInactive={result.ResetInactive}", eChatType.CT_System, eChatLoc.CL_SystemWindow);
        }

        private static void ValidatePools(GameClient client)
        {
            MobGrowthBonusPoolValidation validation = MobGrowthService.ValidateBonusPools(MobGrowthOptions.FromProperties());
            List<string> lines = new()
            {
                $"Valid entries: {validation.ValidEntries}",
                $"Errors: {validation.Errors.Count}"
            };

            foreach (string error in validation.Errors.Take(100))
                lines.Add(error);

            if (validation.Errors.Count == 0)
                lines.Add("보너스 풀 형식 오류가 없습니다.");

            client.Out.SendCustomTextWindow("Mob Growth Bonus Pools", lines);
        }

        private static void Reset(GameClient client, string[] args)
        {
            string mobId = args.Length >= 3 ? args[2] : string.Empty;

            if ((string.IsNullOrWhiteSpace(mobId) || mobId.Equals("target", StringComparison.OrdinalIgnoreCase)) &&
                client.Player.TargetObject is GameNPC npc)
                mobId = npc.InternalID;

            if (string.IsNullOrWhiteSpace(mobId))
            {
                client.Out.SendMessage("사용법: /mobgrowth reset <mobId|target>", eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            bool deleted = MobGrowthService.Instance.Reset(mobId);
            client.Out.SendMessage(deleted ? "몬스터 성장 기록을 삭제했습니다." : "해당 몬스터 성장 기록을 찾지 못했습니다.", eChatType.CT_System, eChatLoc.CL_SystemWindow);
        }

        private void DisplayUsage(GameClient client)
        {
            client.Out.SendCustomTextWindow("Mob Growth Commands", new List<string>
            {
                "/mobgrowth status",
                "/mobgrowth enable",
                "/mobgrowth disable",
                "/mobgrowth scan [limit]",
                "/mobgrowth top [limit|boss|mutant|region <regionId>]",
                "/mobgrowth region [regionId]",
                "/mobgrowth inspect",
                "/mobgrowth promote <normal|elite|champion|boss> [mobId|target]",
                "/mobgrowth mutate <on|off> [mobId|target]",
                "/mobgrowth deaths <count> [mobId|target]",
                "/mobgrowth decay [limit]",
                "/mobgrowth validatepools",
                "/mobgrowth reset <mobId|target>"
            });
        }

        private static string ResolveMobId(GameClient client, string[] args, int index)
        {
            string mobId = args.Length > index ? args[index] : string.Empty;

            if ((string.IsNullOrWhiteSpace(mobId) || mobId.Equals("target", StringComparison.OrdinalIgnoreCase)) &&
                client.Player.TargetObject is GameNPC npc)
                return npc.InternalID;

            return mobId;
        }

        private static string ParseStage(string value)
        {
            if (value.Equals("normal", StringComparison.OrdinalIgnoreCase))
                return MobGrowthStages.Normal;
            if (value.Equals("elite", StringComparison.OrdinalIgnoreCase))
                return MobGrowthStages.Elite;
            if (value.Equals("champion", StringComparison.OrdinalIgnoreCase))
                return MobGrowthStages.Champion;
            if (value.Equals("boss", StringComparison.OrdinalIgnoreCase))
                return MobGrowthStages.Boss;

            return null;
        }

        private static bool TryParseToggle(string value, out bool enabled)
        {
            if (value.Equals("on", StringComparison.OrdinalIgnoreCase) ||
                value.Equals("true", StringComparison.OrdinalIgnoreCase) ||
                value.Equals("1", StringComparison.OrdinalIgnoreCase))
            {
                enabled = true;
                return true;
            }

            if (value.Equals("off", StringComparison.OrdinalIgnoreCase) ||
                value.Equals("false", StringComparison.OrdinalIgnoreCase) ||
                value.Equals("0", StringComparison.OrdinalIgnoreCase))
            {
                enabled = false;
                return true;
            }

            enabled = false;
            return false;
        }

        private static void ApplyTargetIfSame(GameClient client, DbMobGrowthState state)
        {
            if (client.Player.TargetObject is GameNPC npc && npc.InternalID == state.MobId)
                MobGrowthService.Instance.ApplyToNpc(npc);
        }

        private static string Blank(string value)
        {
            return string.IsNullOrWhiteSpace(value) ? "-" : value;
        }

        private static string ShortId(string id)
        {
            if (string.IsNullOrWhiteSpace(id))
                return "(none)";

            return id.Length > 8 ? id.Substring(0, 8) : id;
        }
    }
}
