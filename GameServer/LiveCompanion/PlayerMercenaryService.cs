using System;
using System.Collections.Generic;
using System.Linq;
using DOL.Database;

namespace DOL.GS.LiveCompanion
{
    public static class PlayerMercenaryService
    {
        private static readonly MercenaryClassTemplate[] ClassTemplates =
        {
            new(1, 2, "Armsman", CompanionRequestRoles.Tank, "defensive_tank"),
            new(1, 11, "Mercenary", CompanionRequestRoles.Dps, "dedicated_dps"),
            new(1, 6, "Cleric", CompanionRequestRoles.Healer, "heal|buff|resurrection"),
            new(1, 1, "Paladin", CompanionRequestRoles.Tank, "defensive_tank|self_sustain"),
            new(1, 7, "Wizard", CompanionRequestRoles.Dps, "caster_dps"),
            new(1, 5, "Theurgist", CompanionRequestRoles.Support, "pet|bladeturn|caster_dps"),
            new(1, 4, "Minstrel", CompanionRequestRoles.Support, "speed_song|stealth"),
            new(2, 22, "Warrior", CompanionRequestRoles.Tank, "defensive_tank"),
            new(2, 26, "Healer", CompanionRequestRoles.Healer, "heal|buff|resurrection|mez"),
            new(2, 28, "Shaman", CompanionRequestRoles.Healer, "heal|buff|disease"),
            new(2, 29, "Runemaster", CompanionRequestRoles.Dps, "caster_dps"),
            new(2, 24, "Skald", CompanionRequestRoles.Support, "speed_song|dps"),
            new(3, 44, "Hero", CompanionRequestRoles.Tank, "defensive_tank"),
            new(3, 47, "Druid", CompanionRequestRoles.Healer, "heal|buff|resurrection"),
            new(3, 48, "Bard", CompanionRequestRoles.Healer, "heal|speed_song|mez"),
            new(3, 40, "Eldritch", CompanionRequestRoles.Dps, "caster_dps|disease"),
            new(3, 41, "Enchanter", CompanionRequestRoles.Dps, "caster_dps|pet")
        };

        private static readonly string[] Personalities =
        {
            "calm_support",
            "reckless_berserker",
            "wary_survivor",
            "eager_rookie",
            "proud_veteran",
            "shifty_traitor",
            "cunning_opportunist"
        };

        private static readonly Dictionary<int, string[]> NamesByRealm = new()
        {
            [1] = new[] { "알릭", "브란", "세드릭", "엘윈", "로완", "마리엘" },
            [2] = new[] { "하콘", "시그룬", "울프", "라그니", "에이라", "토르벤" },
            [3] = new[] { "케일", "니아브", "핀", "에린", "로난", "실리아" }
        };

        private static readonly string[] TraitPool =
        {
            "전투 후 주변을 먼저 확인함",
            "위험하면 한 박자 늦게 진입함",
            "체력이 낮은 아군을 집요하게 챙김",
            "강한 적을 보면 먼저 거리를 벌림",
            "기회가 보이면 과감히 추격함",
            "낯선 지역에서 길 안내를 자주 확인함"
        };

        private static readonly string[] ItemProfiles =
        {
            "낡았지만 손에 익은 장비",
            "가벼운 기동 장비",
            "방어를 중시한 현장 장비",
            "마법 저항을 보강한 장비",
            "사냥터 장기 체류용 보급품"
        };

        private static readonly string[] AdventureMemories =
        {
            "초보 파티를 호위하며 사냥터 길목과 안전한 후퇴로를 익혔다.",
            "파티가 무너질 때 마지막까지 남아 부상자를 빼낸 적이 있다.",
            "낯선 지역에서 몬스터 습성을 적어 두며 길 안내 경험을 쌓았다.",
            "보급이 끊긴 장기 사냥에서 쉬는 타이밍을 판단하는 법을 배웠다."
        };

        public static IList<DbPlayerMercenary> OwnedBy(GamePlayer player)
        {
            string ownerId = OwnerCharacterId(player);
            if (string.IsNullOrWhiteSpace(ownerId))
                return new List<DbPlayerMercenary>();

            return GameServer.Database
                .SelectObjects<DbPlayerMercenary>(DB.Column("OwnerCharacterId").IsEqualTo(ownerId))
                .OrderBy(row => row.CreatedAt)
                .ThenBy(row => row.DisplayName)
                .ToList();
        }

        public static DbPlayerMercenary GetOwned(GamePlayer player, string mercenaryIdOrName)
        {
            string key = (mercenaryIdOrName ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(key))
                return null;

            return OwnedBy(player).FirstOrDefault(row =>
                row.MercenaryId.Equals(key, StringComparison.OrdinalIgnoreCase) ||
                row.DisplayName.Equals(key, StringComparison.OrdinalIgnoreCase));
        }

        public static DbPlayerMercenary EnsureStarterMercenary(GamePlayer player)
        {
            DbPlayerMercenary existing = OwnedBy(player).FirstOrDefault(row =>
                row.SourceId.Equals("starter", StringComparison.OrdinalIgnoreCase));
            return existing ?? GrantRandom(player, "starter", CompanionContractTiers.Common, starter: true);
        }

        public static DbPlayerMercenary GrantRandom(
            GamePlayer player,
            string sourceId,
            string contractTier = CompanionContractTiers.Common,
            bool starter = false)
        {
            if (player == null)
                return null;

            int realm = (int) player.Realm;
            Random random = new Random(Guid.NewGuid().GetHashCode());
            MercenaryClassTemplate template = ChooseClassTemplate(realm, starter, random);
            string normalizedTier = CompanionContractTiers.Normalize(contractTier);
            string displayName = UniqueDisplayName(player, RandomName(realm, random));
            string personality = Personalities[random.Next(Personalities.Length)];
            string tactic = ChooseTacticPreset(template.Role, personality, starter, random);
            string adventureMemory = AdventureMemories[random.Next(AdventureMemories.Length)];
            DateTime now = DateTime.UtcNow;
            DbPlayerMercenary mercenary = new DbPlayerMercenary
            {
                MercenaryId = Guid.NewGuid().ToString("N"),
                OwnerCharacterId = OwnerCharacterId(player),
                OwnerAccountName = player.Client?.Account?.Name ?? string.Empty,
                OwnerCharacterName = player.Name ?? string.Empty,
                DisplayName = displayName,
                Background = BuildBackground(displayName, template, sourceId, starter, random),
                Personality = personality,
                ClassId = template.ClassId,
                ClassName = template.ClassName,
                Realm = realm,
                Role = template.Role,
                Capabilities = template.Capabilities,
                ContractTier = normalizedTier,
                Traits = PickTwo(TraitPool, random),
                ItemProfile = ItemProfiles[random.Next(ItemProfiles.Length)],
                TacticPreset = tactic,
                Trust = starter ? 65 : random.Next(42, 71),
                Fatigue = 0,
                AdventureMemory = adventureMemory,
                RumorHint = BuildRumorHint(displayName, template, tactic, normalizedTier),
                TotalContracts = 0,
                TotalContractMinutes = 0,
                KillsTogether = 0,
                DeathsTogether = 0,
                RevivesReceived = 0,
                Rescues = 0,
                QuestsCompleted = 0,
                EarnedTitles = string.Empty,
                PersonalQuestState = string.Empty,
                RelationshipEventState = string.Empty,
                LastHiredAt = now,
                SourceId = string.IsNullOrWhiteSpace(sourceId) ? "event" : sourceId.Trim(),
                CreatedAt = now,
                UpdatedAt = now
            };

            GameServer.Database.AddObject(mercenary);
            return mercenary;
        }

        public static void RecordContractStarted(DbPlayerMercenary mercenary)
        {
            if (mercenary == null)
                return;

            mercenary.TotalContracts = Math.Max(0, mercenary.TotalContracts) + 1;
            mercenary.Fatigue = Math.Min(100, Math.Max(0, mercenary.Fatigue) + FatigueGainForTier(mercenary.ContractTier));
            mercenary.Trust = Math.Min(100, Math.Max(0, mercenary.Trust) + 1);
            mercenary.LastHiredAt = DateTime.UtcNow;
            mercenary.UpdatedAt = DateTime.UtcNow;
            GameServer.Database.SaveObject(mercenary);
        }

        public static void RecordContractCompleted(
            DbPlayerMercenary mercenary,
            TimeSpan activeDuration,
            string closeReason = "",
            long killCredits = 0)
        {
            if (mercenary == null)
                return;

            string reason = (closeReason ?? string.Empty).Trim();
            mercenary.TotalContractMinutes = Math.Max(
                0,
                mercenary.TotalContractMinutes + Math.Max(0, (int)Math.Round(activeDuration.TotalMinutes)));
            long nextKillsTogether = Math.Max(0, mercenary.KillsTogether) + Math.Max(0, killCredits);
            mercenary.KillsTogether = (int)Math.Min(int.MaxValue, nextKillsTogether);
            if (IsQuestCompletionReason(reason))
                mercenary.QuestsCompleted = Math.Max(0, mercenary.QuestsCompleted) + 1;
            if (IsRescueReason(reason))
                mercenary.Rescues = Math.Max(0, mercenary.Rescues) + 1;

            int trustGain = TrustGainForCompletedContract(activeDuration) +
                TrustGainForCompletedReason(reason);

            if (trustGain > 0)
                mercenary.Trust = Math.Min(100, Math.Max(0, mercenary.Trust) + trustGain);
            RefreshTitlesAndPersonalQuest(mercenary);
            mercenary.UpdatedAt = DateTime.UtcNow;
            GameServer.Database.SaveObject(mercenary);
        }

        public static void RecordContractFailed(DbPlayerMercenary mercenary, bool wasActive)
        {
            if (mercenary == null || !wasActive)
                return;

            mercenary.Trust = Math.Max(0, Math.Min(100, mercenary.Trust) - 2);
            mercenary.Fatigue = Math.Min(100, Math.Max(0, mercenary.Fatigue) + 3);
            mercenary.DeathsTogether = Math.Max(0, mercenary.DeathsTogether) + 1;
            RefreshTitlesAndPersonalQuest(mercenary);
            mercenary.UpdatedAt = DateTime.UtcNow;
            GameServer.Database.SaveObject(mercenary);
        }

        public static int RestMercenary(DbPlayerMercenary mercenary, int fatigueRecovery = 25)
        {
            if (mercenary == null)
                return 0;

            int before = Math.Max(0, mercenary.Fatigue);
            int recovered = Math.Min(before, Math.Max(1, fatigueRecovery));
            mercenary.Fatigue = Math.Max(0, before - recovered);
            mercenary.UpdatedAt = DateTime.UtcNow;
            GameServer.Database.SaveObject(mercenary);
            return recovered;
        }

        public static string TrustStageLabel(int trust)
        {
            int normalizedTrust = Math.Max(0, Math.Min(100, trust));
            if (normalizedTrust >= 90)
                return "충성";
            if (normalizedTrust >= 75)
                return "두터운 신뢰";
            if (normalizedTrust >= 55)
                return "익숙함";
            if (normalizedTrust >= 35)
                return "조심스러움";
            return "낯섦";
        }

        public static string PrimaryTitle(DbPlayerMercenary mercenary)
        {
            return TitleList(mercenary?.EarnedTitles).FirstOrDefault() ?? "칭호 없음";
        }

        public static string RecordSummary(DbPlayerMercenary mercenary)
        {
            if (mercenary == null)
                return "기록 없음";

            return
                $"누적 {Math.Max(0, mercenary.TotalContractMinutes)}분, 처치 기여 {Math.Max(0, mercenary.KillsTogether)}회, " +
                $"구출 {Math.Max(0, mercenary.Rescues)}회, 개인 의뢰 {Math.Max(0, mercenary.QuestsCompleted)}회, 전투불능 {Math.Max(0, mercenary.DeathsTogether)}회";
        }

        public static string PersonalQuestLine(DbPlayerMercenary mercenary)
        {
            string state = (mercenary?.PersonalQuestState ?? string.Empty).Trim().ToLowerInvariant();
            if (string.IsNullOrWhiteSpace(state))
                return "개인 의뢰: 아직 없음";
            if (state == "available:first_bond")
                return "개인 의뢰: 신뢰의 첫 증표 - 함께 10회 처치하거나 의뢰 하나를 끝내면 보상이 열립니다.";
            if (state == "completed:first_bond")
                return "개인 의뢰: 신뢰의 첫 증표 완료";
            if (state == "available:field_oath")
                return "개인 의뢰: 전장의 맹세 - 긴 계약과 구출 기록으로 더 강한 특성을 노립니다.";
            if (state == "completed:field_oath")
                return "개인 의뢰: 전장의 맹세 완료";
            return $"개인 의뢰: {state}";
        }

        public static int RestAll(GamePlayer player, int fatigueRecovery = 25)
        {
            int recovered = 0;
            foreach (DbPlayerMercenary mercenary in OwnedBy(player))
                recovered += RestMercenary(mercenary, fatigueRecovery);
            return recovered;
        }

        private static void RefreshTitlesAndPersonalQuest(DbPlayerMercenary mercenary)
        {
            if (mercenary == null)
                return;

            mercenary.EarnedTitles = string.Join("|", BuildTitles(mercenary));
            string state = (mercenary.PersonalQuestState ?? string.Empty).Trim().ToLowerInvariant();
            if (string.IsNullOrWhiteSpace(state) &&
                (mercenary.TotalContracts >= 3 || mercenary.TotalContractMinutes >= 60 || mercenary.KillsTogether >= 10))
            {
                mercenary.PersonalQuestState = "available:first_bond";
            }
            else if (state == "available:first_bond" &&
                     (mercenary.QuestsCompleted >= 1 || mercenary.KillsTogether >= 20 || mercenary.Trust >= 75))
            {
                mercenary.PersonalQuestState = "completed:first_bond";
                mercenary.RelationshipEventState = AppendToken(mercenary.RelationshipEventState, "bond_acknowledged");
            }
            else if (state == "completed:first_bond" &&
                     (mercenary.TotalContractMinutes >= 180 || mercenary.Rescues >= 3 || mercenary.Trust >= 90))
            {
                mercenary.PersonalQuestState = "available:field_oath";
            }
            else if (state == "available:field_oath" &&
                     mercenary.Trust >= 90 &&
                     (mercenary.Rescues >= 5 || mercenary.KillsTogether >= 50 || mercenary.QuestsCompleted >= 3))
            {
                mercenary.PersonalQuestState = "completed:field_oath";
                mercenary.RelationshipEventState = AppendToken(mercenary.RelationshipEventState, "field_oath");
            }
        }

        private static IList<string> BuildTitles(DbPlayerMercenary mercenary)
        {
            List<string> titles = new();
            if (mercenary.TotalContracts >= 5)
                titles.Add("오랜 계약자");
            if (mercenary.TotalContractMinutes >= 120)
                titles.Add("긴 여정의 동행");
            if (mercenary.KillsTogether >= 10)
                titles.Add("사냥길 용병");
            if (mercenary.KillsTogether >= 50)
                titles.Add("전장의 해결사");
            if (mercenary.Rescues >= 3)
                titles.Add("위기 구원자");
            if (mercenary.QuestsCompleted >= 1)
                titles.Add("의뢰 해결사");
            if (mercenary.Trust >= 90)
                titles.Add("맹세한 방패");
            if (mercenary.DeathsTogether >= 3)
                titles.Add("다시 일어선 자");
            return titles;
        }

        private static IEnumerable<string> TitleList(string titles)
        {
            return (titles ?? string.Empty)
                .Split(new[] { '|', ';', ',' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(title => title.Trim())
                .Where(title => !string.IsNullOrWhiteSpace(title));
        }

        private static string AppendToken(string current, string token)
        {
            if (string.IsNullOrWhiteSpace(token))
                return current ?? string.Empty;

            HashSet<string> tokens = new(
                (current ?? string.Empty)
                    .Split(new[] { '|', ';', ',' }, StringSplitOptions.RemoveEmptyEntries)
                    .Select(row => row.Trim())
                    .Where(row => !string.IsNullOrWhiteSpace(row)),
                StringComparer.OrdinalIgnoreCase);
            tokens.Add(token.Trim());
            return string.Join("|", tokens);
        }

        private static string OwnerCharacterId(GamePlayer player)
        {
            return player?.ObjectId ?? string.Empty;
        }

        private static MercenaryClassTemplate ChooseClassTemplate(int realm, bool starter, Random random)
        {
            MercenaryClassTemplate[] realmClasses = ClassTemplates
                .Where(row => row.Realm == realm)
                .ToArray();
            if (realmClasses.Length == 0)
                realmClasses = ClassTemplates.Where(row => row.Realm == 1).ToArray();

            if (starter)
            {
                MercenaryClassTemplate starterTemplate = realmClasses.FirstOrDefault(row =>
                    row.Role.Equals(CompanionRequestRoles.Healer, StringComparison.OrdinalIgnoreCase));
                if (starterTemplate.ClassName != null)
                    return starterTemplate;
            }

            return realmClasses[random.Next(realmClasses.Length)];
        }

        private static string RandomName(int realm, Random random)
        {
            if (!NamesByRealm.TryGetValue(realm, out string[] names) || names.Length == 0)
                names = NamesByRealm[1];
            return names[random.Next(names.Length)];
        }

        private static string UniqueDisplayName(GamePlayer player, string baseName)
        {
            HashSet<string> existing = OwnedBy(player)
                .Select(row => row.DisplayName)
                .ToHashSet(StringComparer.OrdinalIgnoreCase);
            if (!existing.Contains(baseName))
                return baseName;

            for (int i = 2; i < 100; i++)
            {
                string candidate = $"{baseName}{i}";
                if (!existing.Contains(candidate))
                    return candidate;
            }

            return $"{baseName}{DateTime.UtcNow.Ticks % 10000}";
        }

        private static string BuildBackground(
            string displayName,
            MercenaryClassTemplate template,
            string sourceId,
            bool starter,
            Random random)
        {
            string origin = starter
                ? "초기 계약으로 합류한 기본 용병"
                : $"{(string.IsNullOrWhiteSpace(sourceId) ? "이벤트" : sourceId)} 보상으로 합류한 용병";
            string memory = random.Next(3) switch
            {
                0 => "국경 지대 소규모 전투에서 살아남은 뒤 실전 감각을 익혔다.",
                1 => "여러 사냥터를 떠돌며 길과 몬스터 습성을 기록해 왔다.",
                _ => "한 파티가 무너진 뒤에도 끝까지 의뢰인을 호위했다."
            };
            return $"{displayName}은 {origin}이며, {template.ClassName} 전술을 익혔다. {memory}";
        }

        private static string ChooseTacticPreset(string role, string personality, bool starter, Random random)
        {
            if (starter)
                return "safe";

            string normalizedRole = CompanionRequestRoles.Normalize(role);
            string normalizedPersonality = (personality ?? string.Empty).Trim().ToLowerInvariant();
            if (normalizedPersonality is "reckless_berserker" or "cunning_opportunist")
                return "aggressive";
            if (normalizedPersonality is "wary_survivor" or "shifty_traitor")
                return "safe";
            if (normalizedRole == CompanionRequestRoles.Healer)
                return random.Next(2) == 0 ? "heal_priority" : "safe";
            if (normalizedRole == CompanionRequestRoles.Tank)
                return random.Next(2) == 0 ? "leader_protect" : "balanced";
            if (normalizedRole == CompanionRequestRoles.Support)
                return random.Next(2) == 0 ? "mez_priority" : "balanced";
            return random.Next(3) == 0 ? "aggressive" : "balanced";
        }

        private static int FatigueGainForTier(string tier)
        {
            return CompanionContractTiers.Normalize(tier) switch
            {
                CompanionContractTiers.Legendary => 12,
                CompanionContractTiers.Elite => 9,
                CompanionContractTiers.Skilled => 7,
                _ => 5
            };
        }

        private static int TrustGainForCompletedContract(TimeSpan activeDuration)
        {
            if (activeDuration >= TimeSpan.FromMinutes(20))
                return 3;
            if (activeDuration >= TimeSpan.FromMinutes(5))
                return 2;
            if (activeDuration >= TimeSpan.FromMinutes(1))
                return 1;
            return 0;
        }

        private static int TrustGainForCompletedReason(string closeReason)
        {
            string reason = (closeReason ?? string.Empty).Trim().ToLowerInvariant();
            if (string.IsNullOrWhiteSpace(reason))
                return 0;

            if (reason.Contains("objective_completed", StringComparison.OrdinalIgnoreCase) ||
                reason.Contains("quest_completed", StringComparison.OrdinalIgnoreCase) ||
                reason.Contains("boss_defeated", StringComparison.OrdinalIgnoreCase))
                return 3;

            if (reason.Contains("party_saved", StringComparison.OrdinalIgnoreCase) ||
                reason.Contains("protected_leader", StringComparison.OrdinalIgnoreCase) ||
                reason.Contains("resurrection_save", StringComparison.OrdinalIgnoreCase))
                return 2;

            if (reason.Contains("real_player_joined", StringComparison.OrdinalIgnoreCase) ||
                reason.Contains("honorable_release", StringComparison.OrdinalIgnoreCase))
                return 1;

            return 0;
        }

        private static bool IsQuestCompletionReason(string closeReason)
        {
            string reason = (closeReason ?? string.Empty).Trim().ToLowerInvariant();
            return reason.Contains("quest_completed", StringComparison.OrdinalIgnoreCase) ||
                   reason.Contains("objective_completed", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsRescueReason(string closeReason)
        {
            string reason = (closeReason ?? string.Empty).Trim().ToLowerInvariant();
            return reason.Contains("party_saved", StringComparison.OrdinalIgnoreCase) ||
                   reason.Contains("protected_leader", StringComparison.OrdinalIgnoreCase) ||
                   reason.Contains("resurrection_save", StringComparison.OrdinalIgnoreCase);
        }

        private static string BuildRumorHint(
            string displayName,
            MercenaryClassTemplate template,
            string tactic,
            string tier)
        {
            string tacticLabel = tactic switch
            {
                "safe" => "안전한 길을 먼저 보는",
                "aggressive" => "기회를 보면 바로 파고드는",
                "heal_priority" => "부상자를 먼저 챙기는",
                "mez_priority" => "적을 묶고 흐름을 끊는",
                "leader_protect" => "고용주 보호를 우선하는",
                _ => "상황에 맞춰 움직이는"
            };
            string tierLabel = CompanionContractTiers.Normalize(tier) switch
            {
                CompanionContractTiers.Legendary => "전설급",
                CompanionContractTiers.Elite => "정예",
                CompanionContractTiers.Skilled => "숙련",
                _ => "일반"
            };
            return $"{displayName}이라는 {tierLabel} {template.ClassName} 용병은 {tacticLabel} 전술로 알려져 있다.";
        }

        private static string PickTwo(string[] values, Random random)
        {
            if (values.Length <= 2)
                return string.Join("|", values);

            int first = random.Next(values.Length);
            int second;
            do
            {
                second = random.Next(values.Length);
            } while (second == first);

            return $"{values[first]}|{values[second]}";
        }

        private readonly struct MercenaryClassTemplate
        {
            public MercenaryClassTemplate(int realm, int classId, string className, string role, string capabilities)
            {
                Realm = realm;
                ClassId = classId;
                ClassName = className;
                Role = role;
                Capabilities = capabilities;
            }

            public int Realm { get; }
            public int ClassId { get; }
            public string ClassName { get; }
            public string Role { get; }
            public string Capabilities { get; }
        }
    }
}
