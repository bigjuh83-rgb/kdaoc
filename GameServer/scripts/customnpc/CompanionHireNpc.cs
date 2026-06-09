using System;
using System.Linq;
using DOL.Database;
using DOL.Events;
using DOL.GS.LiveCompanion;
using DOL.GS.PacketHandler;

namespace DOL.GS.Scripts
{
    public class CompanionHireNpc : GameNPC
    {
        private const string CompanionHireNpcPackageId = "live_companion_hire_npc";
        private const string CompanionHireNpcName = "용병 고용관";
        private const int TeleporterSideOffset = 420;
        private const int LegacyPlacementClaimRadius = 1600;

        [ScriptLoadedEvent]
        public static void OnScriptLoaded(DOLEvent e, object sender, EventArgs args)
        {
            SpawnNearLiveTeleporters();
        }

        [GameServerStartedEvent]
        public static void OnGameServerStarted(DOLEvent e, object sender, EventArgs args)
        {
            SpawnNearLiveTeleporters();
        }

        public override bool AddToWorld()
        {
            if (string.IsNullOrWhiteSpace(Name) || Name.Equals(GetType().Name, StringComparison.OrdinalIgnoreCase))
                Name = CompanionHireNpcName;

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
                $"{CompanionHireNpcName}입니다. 어떤 용병을 고용하시겠습니까?\n" +
                "보유: [내 용병]\n" +
                "고용: [치유형 고용] [방어형 고용] [공격형 고용]\n" +
                "관리: [용병 상세] [휴식] [상태 확인] [소문] [요청 취소] [용병 해산]");
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
                case "내 용병":
                case "보유 용병":
                case "용병 목록":
                case "mercenaries":
                    ShowOwnedMercenaries(player);
                    return true;
                case "용병 상세":
                case "상세":
                case "detail":
                case "details":
                    ShowMercenaryDetails(player, string.Empty);
                    return true;
                case "휴식":
                case "용병 휴식":
                case "rest":
                    RestMercenaries(player, string.Empty);
                    return true;
                case "소문":
                case "용병 소문":
                case "도감":
                case "용병 도감":
                case "rumor":
                case "rumors":
                    ShowMercenaryRumors(player);
                    return true;
                case "치유 용병":
                case "치유형 고용":
                case "치유":
                case "healer":
                    QueueCompanion(player, CompanionRequestRoles.Healer);
                    return true;
                case "방어 용병":
                case "방어형 고용":
                case "방어":
                case "tank":
                    QueueCompanion(player, CompanionRequestRoles.Tank);
                    return true;
                case "공격 용병":
                case "공격형 고용":
                case "공격":
                case "dps":
                    QueueCompanion(player, CompanionRequestRoles.Dps);
                    return true;
                case "용병 상태":
                case "상태 확인":
                case "상태":
                case "status":
                    ShowStatus(player);
                    return true;
                case "용병 요청 취소":
                case "요청 취소":
                case "취소":
                case "cancel":
                    CancelPending(player);
                    return true;
                case "용병 해산":
                case "해산":
                case "leave":
                    QueueLeave(player);
                    return true;
                default:
                    if (TryShowMercenaryDetails(player, str))
                        return true;
                    if (TryRestMercenary(player, str))
                        return true;
                    if (QueueOwnedMercenary(player, str))
                        return true;
                    Interact(player);
                    return true;
            }
        }

        private void QueueCompanion(GamePlayer player, string role)
        {
            PlayerMercenaryService.EnsureStarterMercenary(player);
            CompanionRequestResult result = CompanionRequestService.CreateRequest(
                player,
                role,
                "hire_npc",
                "pve",
                Name);

            SendReply(player, result.Success ? "용병에게 연락을 넣었습니다." : "지금 가능한 용병이 없습니다.");
        }

        private bool QueueOwnedMercenary(GamePlayer player, string mercenaryName)
        {
            DbPlayerMercenary mercenary = PlayerMercenaryService.GetOwned(player, mercenaryName);
            if (mercenary == null)
                return false;

            CompanionRequestResult result = CompanionRequestService.CreateOwnedMercenaryRequest(
                player,
                mercenary.MercenaryId,
                "hire_npc",
                "pve",
                Name);

            SendReply(
                player,
                result.Success
                    ? $"{mercenary.DisplayName}에게 연락을 넣었습니다."
                    : result.Message);
            return true;
        }

        private void ShowOwnedMercenaries(GamePlayer player)
        {
            PlayerMercenaryService.EnsureStarterMercenary(player);
            var mercenaries = PlayerMercenaryService.OwnedBy(player);
            if (mercenaries.Count == 0)
            {
                SendReply(player, "아직 보유한 용병이 없습니다.");
                return;
            }

            string lines = string.Join(
                "\n",
                mercenaries.Take(8).Select(row =>
                    $"[{row.DisplayName}] {TierLabel(row.ContractTier)} {row.ClassName} / {PersonalityLabel(row.Personality)} / {TacticLabel(row.TacticPreset)}\n" +
                    $"신뢰 {row.Trust}, 피로 {row.Fatigue}, 계약 {row.TotalContracts}회\n" +
                    $"{row.Background}\n" +
                    $"관리: [{row.DisplayName} 상세] [{row.DisplayName} 휴식]"));
            SendReply(player, "보유 용병 목록입니다. 이름만 누르면 고용합니다.\n" + lines);
        }

        private bool TryShowMercenaryDetails(GamePlayer player, string command)
        {
            string name = ExtractMercenaryCommandSubject(command, "상세", "detail", "details");
            if (string.IsNullOrWhiteSpace(name))
                return false;

            return ShowMercenaryDetails(player, name);
        }

        private bool ShowMercenaryDetails(GamePlayer player, string mercenaryName)
        {
            PlayerMercenaryService.EnsureStarterMercenary(player);
            var mercenaries = string.IsNullOrWhiteSpace(mercenaryName)
                ? PlayerMercenaryService.OwnedBy(player)
                : PlayerMercenaryService.OwnedBy(player)
                    .Where(row =>
                        row.MercenaryId.Equals(mercenaryName.Trim(), StringComparison.OrdinalIgnoreCase) ||
                        row.DisplayName.Equals(mercenaryName.Trim(), StringComparison.OrdinalIgnoreCase))
                    .ToList();

            if (mercenaries.Count == 0)
            {
                SendReply(player, "상세를 볼 보유 용병을 찾지 못했습니다.");
                return true;
            }

            string lines = string.Join(
                "\n\n",
                mercenaries.Take(4).Select(row =>
                    $"[{row.DisplayName}] {TierLabel(row.ContractTier)} {row.ClassName}\n" +
                    $"성격 {PersonalityLabel(row.Personality)}, 전술 {TacticLabel(row.TacticPreset)}\n" +
                    $"신뢰 {row.Trust}, 피로 {row.Fatigue}, 계약 {row.TotalContracts}회\n" +
                    $"특성: {FormatPipeList(row.Traits)}\n" +
                    $"장비: {FirstNonEmpty(row.ItemProfile, "기본 장비")}\n" +
                    $"기억: {FirstNonEmpty(row.AdventureMemory, row.Background)}"));
            SendReply(player, "보유 용병 상세입니다.\n" + lines);
            return true;
        }

        private bool TryRestMercenary(GamePlayer player, string command)
        {
            string name = ExtractMercenaryCommandSubject(command, "휴식", "rest");
            if (string.IsNullOrWhiteSpace(name))
                return false;

            RestMercenaries(player, name);
            return true;
        }

        private void RestMercenaries(GamePlayer player, string mercenaryName)
        {
            PlayerMercenaryService.EnsureStarterMercenary(player);
            if (string.IsNullOrWhiteSpace(mercenaryName))
            {
                int recovered = PlayerMercenaryService.RestAll(player);
                SendReply(
                    player,
                    recovered > 0
                        ? $"보유 용병들을 쉬게 했습니다. 피로가 총 {recovered} 회복되었습니다."
                        : "보유 용병들이 이미 충분히 쉬었습니다.");
                return;
            }

            DbPlayerMercenary mercenary = PlayerMercenaryService.GetOwned(player, mercenaryName);
            if (mercenary == null)
            {
                SendReply(player, "휴식시킬 보유 용병을 찾지 못했습니다.");
                return;
            }

            int recoveredAmount = PlayerMercenaryService.RestMercenary(mercenary);
            SendReply(
                player,
                recoveredAmount > 0
                    ? $"{mercenary.DisplayName}이(가) 휴식했습니다. 피로가 {recoveredAmount} 회복되었습니다."
                    : $"{mercenary.DisplayName}은(는) 이미 충분히 쉬었습니다.");
        }

        private void ShowMercenaryRumors(GamePlayer player)
        {
            PlayerMercenaryService.EnsureStarterMercenary(player);
            var mercenaries = PlayerMercenaryService.OwnedBy(player);
            if (mercenaries.Count == 0)
            {
                SendReply(player, "아직 들려줄 용병 소문이 없습니다.");
                return;
            }

            string lines = string.Join(
                "\n",
                mercenaries.Take(8).Select(row =>
                    $"[{row.DisplayName}] {FirstNonEmpty(row.RumorHint, row.AdventureMemory, row.Background)}"));
            SendReply(player, "고용관이 들려주는 보유 용병 소문입니다.\n" + lines);
        }

        private void QueueLeave(GamePlayer player)
        {
            CompanionRequestResult result = CompanionRequestService.RequestLeave(
                player,
                "hire_npc",
                Name);

            SendReply(player, result.Success ? "용병에게 귀환을 전했습니다." : "돌려보낼 용병 요청을 만들 수 없습니다.");
        }

        private void CancelPending(GamePlayer player)
        {
            CompanionRequestResult result = CompanionRequestService.CancelPendingRequests(
                player,
                "hire_npc",
                Name);

            SendReply(player, result.Message);
        }

        private void ShowStatus(GamePlayer player)
        {
            CompanionRequest request = CompanionRequestService.LatestForPlayer(player.Name);
            if (request == null)
            {
                SendReply(player, "아직 접수된 용병 요청이 없습니다.");
                return;
            }

            string companion = string.IsNullOrWhiteSpace(request.AssignedCompanionName)
                ? "배정 대기"
                : request.AssignedCompanionName;
            SendReply(
                player,
                $"최근 용병 요청: 상태={request.Status}, 역할={request.RequestedRole}, 용병={companion}\n{request.Message}");
        }

        private static string TierLabel(string tier)
        {
            return CompanionContractTiers.Normalize(tier) switch
            {
                CompanionContractTiers.Skilled => "숙련",
                CompanionContractTiers.Elite => "정예",
                CompanionContractTiers.Legendary => "전설",
                _ => "일반"
            };
        }

        private static string PersonalityLabel(string personality)
        {
            return (personality ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "reckless_berserker" => "돌격형",
                "wary_survivor" => "생존형",
                "eager_rookie" => "신참형",
                "proud_veteran" => "고참형",
                "shifty_traitor" => "배신자형",
                "cunning_opportunist" => "얍삽한형",
                _ => "침착형"
            };
        }

        private static string TacticLabel(string tactic)
        {
            return (tactic ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "safe" => "안전 우선",
                "aggressive" => "공격 우선",
                "heal_priority" => "힐 우선",
                "mez_priority" => "메즈 우선",
                "leader_protect" => "리더 보호",
                _ => "균형"
            };
        }

        private static string FirstNonEmpty(params string[] values)
        {
            foreach (string value in values)
            {
                if (!string.IsNullOrWhiteSpace(value))
                    return value.Trim();
            }

            return "아직 특별한 이야기는 알려지지 않았습니다.";
        }

        private static string FormatPipeList(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return "없음";

            return string.Join(", ", value.Split('|').Select(part => part.Trim()).Where(part => !string.IsNullOrWhiteSpace(part)));
        }

        private static string ExtractMercenaryCommandSubject(string command, params string[] keywords)
        {
            string text = (command ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(text))
                return string.Empty;

            foreach (string keyword in keywords)
            {
                if (text.Equals(keyword, StringComparison.OrdinalIgnoreCase))
                    return string.Empty;

                if (text.StartsWith(keyword + " ", StringComparison.OrdinalIgnoreCase))
                    return text.Substring(keyword.Length + 1).Trim();

                if (text.EndsWith(" " + keyword, StringComparison.OrdinalIgnoreCase))
                    return text.Substring(0, text.Length - keyword.Length - 1).Trim();
            }

            return string.Empty;
        }

        private static void SendReply(GamePlayer player, string message)
        {
            player.Out.SendMessage(message, eChatType.CT_Merchant, eChatLoc.CL_PopupWindow);
        }

        private static void SpawnNearLiveTeleporters()
        {
            foreach (Region region in WorldMgr.GetAllRegions())
            {
                foreach (LiveTeleporter teleporter in WorldMgr.GetNPCsFromRegion(region.ID).OfType<LiveTeleporter>())
                {
                    if (teleporter.Realm is not (eRealm.Albion or eRealm.Midgard or eRealm.Hibernia))
                        continue;

                    SpawnNearTeleporter(teleporter, region);
                }
            }
        }

        private static void SpawnNearTeleporter(LiveTeleporter teleporter, Region region)
        {
            HubPlacement placement = ComputeHireNpcPlacement(teleporter);
            string packageId = PackageIdForTeleporter(teleporter);

            CompanionHireNpc existing = WorldMgr.GetNPCsFromRegion(region.ID)
                .OfType<CompanionHireNpc>()
                .Where(npc => npc.PackageID == packageId || IsLegacyPlacementForTeleporter(npc, teleporter))
                .OrderBy(npc => DistanceSquared(npc.X, npc.Y, placement.X, placement.Y))
                .FirstOrDefault();
            if (existing != null)
            {
                existing.Name = CompanionHireNpcName;
                ApplyPlacement(existing, placement, region, packageId);
                return;
            }

            CompanionHireNpc npc = new CompanionHireNpc
            {
                Name = CompanionHireNpcName,
                Model = 1198,
                Size = 55,
                Level = 50,
                Realm = placement.Realm,
                X = placement.X,
                Y = placement.Y,
                Z = placement.Z,
                Heading = placement.Heading,
                CurrentRegion = region,
                PackageID = packageId,
            };
            npc.AddToWorld();
        }

        private static HubPlacement ComputeHireNpcPlacement(LiveTeleporter teleporter)
        {
            double angle = (teleporter.Heading & 0x0FFF) * (Math.PI * 2.0 / 4096.0);
            int offsetX = (int)Math.Round(Math.Cos(angle + Math.PI / 2.0) * TeleporterSideOffset);
            int offsetY = (int)Math.Round(Math.Sin(angle + Math.PI / 2.0) * TeleporterSideOffset);

            return new HubPlacement(
                teleporter.CurrentRegionID,
                teleporter.Realm,
                teleporter.X + offsetX,
                teleporter.Y + offsetY,
                teleporter.Z,
                teleporter.Heading);
        }

        private static string PackageIdForTeleporter(LiveTeleporter teleporter)
        {
            return $"{CompanionHireNpcPackageId}:{teleporter.CurrentRegionID}:{teleporter.X}:{teleporter.Y}";
        }

        private static bool IsLegacyPlacementForTeleporter(CompanionHireNpc npc, LiveTeleporter teleporter)
        {
            if (npc.PackageID != CompanionHireNpcPackageId)
                return false;

            return DistanceSquared(npc.X, npc.Y, teleporter.X, teleporter.Y)
                <= LegacyPlacementClaimRadius * LegacyPlacementClaimRadius;
        }

        private static long DistanceSquared(int ax, int ay, int bx, int by)
        {
            long dx = ax - bx;
            long dy = ay - by;
            return dx * dx + dy * dy;
        }

        private static void ApplyPlacement(CompanionHireNpc npc, HubPlacement placement, Region region, string packageId)
        {
            npc.Realm = placement.Realm;
            npc.CurrentRegion = region;
            npc.X = placement.X;
            npc.Y = placement.Y;
            npc.Z = placement.Z;
            npc.Heading = placement.Heading;
            npc.PackageID = packageId;
            npc.MoveTo(placement.Region, placement.X, placement.Y, placement.Z, placement.Heading);
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
