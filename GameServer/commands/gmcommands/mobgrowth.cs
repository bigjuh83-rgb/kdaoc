using System;
using System.Collections.Generic;
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
        "/mobgrowth top [limit]",
        "/mobgrowth inspect",
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
                case "inspect":
                    InspectTarget(client);
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

            if (args.Length >= 3)
                int.TryParse(args[2], out limit);

            IList<DbMobGrowthState> top = MobGrowthService.Instance.GetTopActive(limit);
            List<string> lines = new();

            if (top.Count == 0)
                lines.Add("추적 중인 성장 몬스터가 없습니다.");

            foreach (DbMobGrowthState state in top)
            {
                lines.Add($"{ShortId(state.MobId)} [{state.Stage}] {state.CurrentName}");
                lines.Add($"  Lv {state.BaseLevel}->{state.EffectiveLevel}, score={state.GrowthScore}, kills={state.PlayerKills}, combat={state.CombatCount}, idle={state.UnhuntedTicks}, region={state.Region}");
            }

            client.Out.SendCustomTextWindow("Mob Growth Top", lines);
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
                $"Level: {state.BaseLevel} -> {state.EffectiveLevel}",
                $"Score: {state.GrowthScore}",
                $"Survival ticks: {state.SurvivalTicks}",
                $"Unhunted ticks: {state.UnhuntedTicks}",
                $"Combat count: {state.CombatCount}",
                $"Player kills: {state.PlayerKills}",
                $"Region: {state.Region} ({state.RegionId})",
                $"Last seen UTC: {state.LastSeenAt:yyyy-MM-dd HH:mm:ss}"
            });
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
                "/mobgrowth top [limit]",
                "/mobgrowth inspect",
                "/mobgrowth reset <mobId|target>"
            });
        }

        private static string ShortId(string id)
        {
            if (string.IsNullOrWhiteSpace(id))
                return "(none)";

            return id.Length > 8 ? id.Substring(0, 8) : id;
        }
    }
}
