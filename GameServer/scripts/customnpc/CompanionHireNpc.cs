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
                BuildMainMenuText());
            return true;
        }

        public static string BuildMainMenuText()
        {
            return $"{CompanionHireNpcName}입니다. 어떤 용병을 고용하시겠습니까?\n" +
                "안내: [처음 안내] [운용 팁]\n" +
                "보유: [내 용병]\n" +
                "고용: [추천 고용] [치유형 고용] [방어형 고용] [공격형 고용] [지원형 고용]\n" +
                "관리: [용병 상세] [용병 일지] [휴식] [상태 확인] [소문] [요청 취소] [용병 해산]";
        }

        public static string BuildBeginnerGuideText()
        {
            return "처음이라면 치유형부터 고용해 보세요. 체력 회복과 해제가 안정적입니다.\n" +
                "용병에게 파티말로 `상태`, `기록`, `대기`, `따라와`, `ㄱㄱ`처럼 말하면 바로 반응합니다.\n" +
                "사냥터나 스킬이 궁금하면 `5렙 사냥 어디서 해?`, `내 직업이면 스킬 뭐 찍어?`처럼 물어보세요.\n" +
                "실제 플레이어 자리가 필요하면 파티장이 먼저 [용병 해산]으로 빈자리를 만들면 됩니다.";
        }

        public static string BuildVeteranGuideText()
        {
            return "역할은 치유형, 방어형, 공격형, 지원형으로 나뉩니다. 지원형은 메즈, 스피드송, 보조 유틸을 기대할 때 고릅니다.\n" +
                "보유 용병은 성격, 전술, 친밀도, 피로도가 달라 같은 역할이라도 움직임이 달라집니다.\n" +
                "[용병 상세]로 전술과 특성을 보고, 피로가 높으면 [휴식]을 먼저 쓰는 편이 안정적입니다.\n" +
                "서버/서비스 문제로 실패한 계약은 친밀도 불이익 없이 다시 고용하면 됩니다.";
        }

        public static string BuildNoRequestStatusText()
        {
            return "아직 접수된 용병 요청이 없습니다.\n" +
                "처음이면 [처음 안내]를 보고, 바로 시작하려면 [추천 고용]이나 [치유형 고용]을 눌러 보세요.";
        }

        public static string RecommendRoleForPlayer(int level, string className, int groupSize = 1)
        {
            int safeLevel = Math.Max(1, level);
            int safeGroupSize = Math.Max(1, groupSize);
            string normalizedClass = (className ?? string.Empty).Trim().ToLowerInvariant();

            if (safeGroupSize >= 3 && safeLevel >= 10)
                return CompanionRequestRoles.Support;

            if (ClassNameLooksLikeHealer(normalizedClass))
                return CompanionRequestRoles.Tank;

            if (ClassNameLooksLikeTank(normalizedClass))
                return CompanionRequestRoles.Healer;

            if (safeLevel <= 12)
                return CompanionRequestRoles.Healer;

            return CompanionRequestRoles.Healer;
        }

        public static string BuildRecommendedHireLine(int level, string className, int groupSize = 1)
        {
            string role = RecommendRoleForPlayer(level, className, groupSize);
            string roleLabel = RoleLabel(role);
            string reason = role switch
            {
                CompanionRequestRoles.Support => "파티 인원이 있으면 메즈, 스피드송, 보조 유틸이 체감됩니다.",
                CompanionRequestRoles.Tank => "회복 직업은 앞에서 붙잡아 줄 방어형이 있으면 안정적입니다.",
                CompanionRequestRoles.Dps => "이미 생존과 방어가 충분하면 공격형으로 처치 속도를 올릴 수 있습니다.",
                _ => "혼자 시작하거나 익숙하지 않다면 치유형이 가장 안전합니다."
            };
            return $"추천: {roleLabel} 용병. {reason}";
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
                case "처음 안내":
                case "초보 안내":
                case "가이드":
                case "guide":
                case "beginner":
                    SendReply(player, BuildBeginnerGuideText());
                    return true;
                case "운용 팁":
                case "숙련 안내":
                case "고급 안내":
                case "advanced":
                case "tips":
                    SendReply(player, BuildVeteranGuideText());
                    return true;
                case "추천 고용":
                case "추천":
                case "추천 용병":
                case "recommend":
                    QueueRecommendedCompanion(player);
                    return true;
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
                case "용병 일지":
                case "일지":
                case "추억":
                case "journal":
                    ShowMercenaryJournal(player, string.Empty);
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
                case "지원 용병":
                case "지원형 고용":
                case "지원":
                case "support":
                    QueueCompanion(player, CompanionRequestRoles.Support);
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
                    if (TryShowMercenaryJournal(player, str))
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

            SendReply(player, BuildHireReplyForResult(result, "용병에게 연락을 넣었습니다."));
        }

        private void QueueRecommendedCompanion(GamePlayer player)
        {
            int groupSize = CompanionRequestService.CurrentGroupSize(player);
            string className = player?.CharacterClass?.Name ?? string.Empty;
            string role = RecommendRoleForPlayer(player?.Level ?? 1, className, groupSize);

            PlayerMercenaryService.EnsureStarterMercenary(player);
            CompanionRequestResult result = CompanionRequestService.CreateRequest(
                player,
                role,
                "hire_npc_recommended",
                "pve",
                Name);

            SendReply(
                player,
                BuildHireReplyForResult(
                    result,
                    $"{BuildRecommendedHireLine(player?.Level ?? 1, className, groupSize)} 연락을 넣었습니다."));
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
                BuildHireReplyForResult(result, $"{mercenary.DisplayName}에게 연락을 넣었습니다."));
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
                    $"칭호 {PlayerMercenaryService.PrimaryTitle(row)}, 친밀도 {row.Trust}({PlayerMercenaryService.TrustStageLabel(row.Trust)}), 피로 {row.Fatigue}, 계약 {row.TotalContracts}회\n" +
                    $"{PlayerMercenaryService.RecordSummary(row)}\n" +
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
                    $"칭호 {PlayerMercenaryService.PrimaryTitle(row)}, 친밀도 {row.Trust}({PlayerMercenaryService.TrustStageLabel(row.Trust)}), 피로 {row.Fatigue}, 계약 {row.TotalContracts}회\n" +
                    $"{PlayerMercenaryService.RecordSummary(row)}\n" +
                    $"{PlayerMercenaryService.PersonalQuestLine(row)}\n" +
                    $"특성: {FormatPipeList(row.Traits)}\n" +
                    $"장비: {FirstNonEmpty(row.ItemProfile, "기본 장비")}\n" +
                    $"기억: {FirstNonEmpty(row.AdventureMemory, row.Background)}"));
            SendReply(player, "보유 용병 상세입니다.\n" + lines);
            return true;
        }

        private bool TryShowMercenaryJournal(GamePlayer player, string command)
        {
            string name = ExtractMercenaryCommandSubject(command, "일지", "추억", "journal");
            if (string.IsNullOrWhiteSpace(name))
                return false;

            return ShowMercenaryJournal(player, name);
        }

        private bool ShowMercenaryJournal(GamePlayer player, string mercenaryName)
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
                SendReply(player, "일지를 볼 보유 용병을 찾지 못했습니다.");
                return true;
            }

            string lines = string.Join(
                "\n\n",
                mercenaries.Take(4).Select(row =>
                    $"[{row.DisplayName}] {PlayerMercenaryService.PrimaryTitle(row)}\n" +
                    $"추억: {FirstNonEmpty(row.AdventureMemory, row.Background)}\n" +
                    $"{PlayerMercenaryService.RecordSummary(row)}\n" +
                    $"{PlayerMercenaryService.PersonalQuestLine(row)}\n" +
                    $"{RelationshipEventLine(row.RelationshipEventState)}"));
            SendReply(player, "보유 용병 일지입니다.\n" + lines);
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
                SendReply(player, BuildNoRequestStatusText());
                return;
            }

            SendReply(
                player,
                "최근 용병 요청입니다.\n" +
                string.Join("\n", CompanionRequestService.BuildDisplaySummary(request).Lines));
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

        private static string RoleLabel(string role)
        {
            return CompanionRequestRoles.Normalize(role) switch
            {
                CompanionRequestRoles.Healer => "치유형",
                CompanionRequestRoles.Tank => "방어형",
                CompanionRequestRoles.Dps => "공격형",
                CompanionRequestRoles.Support => "지원형",
                _ => "빈자리 보충"
            };
        }

        private static bool ClassNameLooksLikeHealer(string normalizedClass)
        {
            return normalizedClass.Contains("cleric") ||
                normalizedClass.Contains("druid") ||
                normalizedClass.Contains("healer") ||
                normalizedClass.Contains("shaman") ||
                normalizedClass.Contains("friar");
        }

        private static bool ClassNameLooksLikeTank(string normalizedClass)
        {
            return normalizedClass.Contains("armsman") ||
                normalizedClass.Contains("hero") ||
                normalizedClass.Contains("warrior") ||
                normalizedClass.Contains("paladin") ||
                normalizedClass.Contains("thane");
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

        public static string BuildHireReplyForResult(CompanionRequestResult result, string successMessage)
        {
            if (result != null && result.Success)
                return string.IsNullOrWhiteSpace(successMessage) ? "용병에게 연락을 넣었습니다." : successMessage;

            string message = result?.Message;
            return string.IsNullOrWhiteSpace(message) ? "지금 가능한 용병이 없습니다." : message.Trim();
        }

        private static string FormatPipeList(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return "없음";

            return string.Join(", ", value.Split('|').Select(part => part.Trim()).Where(part => !string.IsNullOrWhiteSpace(part)));
        }

        private static string RelationshipEventLine(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return "관계 기록: 아직 특별한 사건 없음";

            var labels = value.Split('|', ';', ',')
                .Select(part => part.Trim().ToLowerInvariant())
                .Where(part => !string.IsNullOrWhiteSpace(part))
                .Select(part => part switch
                {
                    "bond_acknowledged" => "처음으로 리더를 믿겠다고 인정",
                    "field_oath" => "전장에서 끝까지 함께하겠다고 맹세",
                    _ => part
                })
                .ToList();

            return labels.Count == 0
                ? "관계 기록: 아직 특별한 사건 없음"
                : $"관계 기록: {string.Join(", ", labels)}";
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
