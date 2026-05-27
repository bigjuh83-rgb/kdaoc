using System;
using System.Linq;
using DOL.Events;
using DOL.GS.LiveCompanion;
using DOL.GS.PacketHandler;

namespace DOL.GS.Scripts
{
    public class CompanionHireNpc : GameNPC
    {
        private const string CompanionHireNpcPackageId = "live_companion_hire_npc";
        private static readonly HubPlacement[] HubPlacements =
        {
            new HubPlacement(1, eRealm.Albion, 531504, 479073, 2200, 2048),
            new HubPlacement(100, eRealm.Midgard, 774601, 755307, 4600, 2048),
            new HubPlacement(200, eRealm.Hibernia, 345677, 490738, 5200, 2048),
        };

        [ScriptLoadedEvent]
        public static void OnScriptLoaded(DOLEvent e, object sender, EventArgs args)
        {
            foreach (HubPlacement placement in HubPlacements)
                SpawnHubNpcIfMissing(placement);
        }

        public override bool AddToWorld()
        {
            if (string.IsNullOrWhiteSpace(Name) || Name.Equals(GetType().Name, StringComparison.OrdinalIgnoreCase))
                Name = "동료 고용관";

            if (Model == 0)
                Model = 1198;

            if (Size == 0)
                Size = 55;

            if (Level == 0)
                Level = 50;

            if (string.IsNullOrWhiteSpace(PackageID))
                PackageID = CompanionHireNpcPackageId;

            Flags |= eFlags.PEACE;

            return base.AddToWorld();
        }

        public override bool Interact(GamePlayer player)
        {
            if (!base.Interact(player))
                return false;

            SendReply(
                player,
                "동료 고용관입니다. 필요한 도움을 고르세요.\n" +
                "[파티 동료] [치유 동료] [방어 동료] [공격 동료] [동료 상태] [동료 해산]");
            return true;
        }

        public override bool WhisperReceive(GameLiving source, string str)
        {
            if (!base.WhisperReceive(source, str))
                return false;

            if (source is not GamePlayer player)
                return false;

            string command = (str ?? string.Empty).Trim().ToLowerInvariant();
            switch (command)
            {
                case "파티 동료":
                case "파티":
                case "fill":
                    QueueCompanion(player, CompanionRequestRoles.Fill);
                    return true;
                case "치유 동료":
                case "치유":
                case "healer":
                    QueueCompanion(player, CompanionRequestRoles.Healer);
                    return true;
                case "방어 동료":
                case "방어":
                case "tank":
                    QueueCompanion(player, CompanionRequestRoles.Tank);
                    return true;
                case "공격 동료":
                case "공격":
                case "dps":
                    QueueCompanion(player, CompanionRequestRoles.Dps);
                    return true;
                case "동료 상태":
                case "상태":
                case "status":
                    ShowStatus(player);
                    return true;
                case "동료 해산":
                case "해산":
                case "leave":
                    QueueLeave(player);
                    return true;
                default:
                    Interact(player);
                    return true;
            }
        }

        private void QueueCompanion(GamePlayer player, string role)
        {
            CompanionRequestResult result = CompanionRequestService.CreateRequest(
                player,
                role,
                "hire_npc",
                "pve",
                Name);

            SendReply(player, result.Success ? "동료에게 연락을 넣었습니다." : "지금 가능한 동료가 없습니다.");
        }

        private void QueueLeave(GamePlayer player)
        {
            CompanionRequestResult result = CompanionRequestService.RequestLeave(
                player,
                "hire_npc",
                Name);

            SendReply(player, result.Success ? "동료에게 귀환을 전했습니다." : "돌려보낼 동료 요청을 만들 수 없습니다.");
        }

        private void ShowStatus(GamePlayer player)
        {
            CompanionRequest request = CompanionRequestService.LatestForPlayer(player.Name);
            if (request == null)
            {
                SendReply(player, "아직 접수된 동료 요청이 없습니다.");
                return;
            }

            string companion = string.IsNullOrWhiteSpace(request.AssignedCompanionName)
                ? "배정 대기"
                : request.AssignedCompanionName;
            SendReply(
                player,
                $"최근 동료 요청: 상태={request.Status}, 역할={request.RequestedRole}, 동료={companion}\n{request.Message}");
        }

        private static void SendReply(GamePlayer player, string message)
        {
            player.Out.SendMessage(message, eChatType.CT_Merchant, eChatLoc.CL_PopupWindow);
        }

        private static void SpawnHubNpcIfMissing(HubPlacement placement)
        {
            Region region = WorldMgr.GetRegion(placement.Region);
            if (region == null)
                return;

            bool exists = WorldMgr.GetNPCsFromRegion(placement.Region)
                .OfType<CompanionHireNpc>()
                .Any(npc => npc.PackageID == CompanionHireNpcPackageId);
            if (exists)
                return;

            CompanionHireNpc npc = new CompanionHireNpc
            {
                Name = "동료 고용관",
                Model = 1198,
                Size = 55,
                Level = 50,
                Realm = placement.Realm,
                X = placement.X,
                Y = placement.Y,
                Z = placement.Z,
                Heading = placement.Heading,
                CurrentRegion = region,
                PackageID = CompanionHireNpcPackageId,
            };
            npc.AddToWorld();
        }

        private sealed class HubPlacement
        {
            public HubPlacement(ushort region, eRealm realm, int x, int y, int z, ushort heading)
            {
                Region = region;
                Realm = realm;
                X = x;
                Y = y;
                Z = z;
                Heading = heading;
            }

            public ushort Region { get; }
            public eRealm Realm { get; }
            public int X { get; }
            public int Y { get; }
            public int Z { get; }
            public ushort Heading { get; }
        }
    }
}
