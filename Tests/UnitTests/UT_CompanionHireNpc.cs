using System;
using System.Linq;
using DOL.GS.LiveCompanion;
using DOL.GS.Scripts;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_CompanionHireNpc
    {
        [Test]
        public void BuildHireReplyForResult_UsesSpecificFailureMessage()
        {
            CompanionRequestResult result = new()
            {
                Success = false,
                Message = "파티가 가득 차 용병을 부를 수 없습니다."
            };

            string reply = CompanionHireNpc.BuildHireReplyForResult(result, "용병에게 연락을 넣었습니다.");

            Assert.That(reply, Is.EqualTo("파티가 가득 차 용병을 부를 수 없습니다."));
        }

        [Test]
        public void BuildHireReplyForResult_FallsBackWhenFailureMessageIsEmpty()
        {
            CompanionRequestResult result = new()
            {
                Success = false,
                Message = ""
            };

            string reply = CompanionHireNpc.BuildHireReplyForResult(result, "용병에게 연락을 넣었습니다.");

            Assert.That(reply, Is.EqualTo("지금 가능한 용병이 없습니다."));
        }

        [Test]
        public void BuildHireReplyForResult_KeepsSuccessMessage()
        {
            CompanionRequestResult result = new()
            {
                Success = true,
                Message = "용병 요청이 접수되었습니다."
            };

            string reply = CompanionHireNpc.BuildHireReplyForResult(result, "알브가드에게 연락을 넣었습니다.");

            Assert.That(reply, Is.EqualTo("알브가드에게 연락을 넣었습니다."));
        }

        [Test]
        public void BuildMainMenuText_OffersSupportHireAndManualDismissal()
        {
            string text = CompanionHireNpc.BuildMainMenuText();

            Assert.That(text, Does.Contain("[처음 안내]"));
            Assert.That(text, Does.Contain("[운용 팁]"));
            Assert.That(text, Does.Contain("[추천 고용]"));
            Assert.That(text, Does.Contain("[지원형 고용]"));
            Assert.That(text, Does.Contain("[용병 일지]"));
            Assert.That(text, Does.Contain("[용병 해산]"));
            Assert.That(text, Does.Contain("[상태 확인]"));
        }

        [Test]
        public void BuildBeginnerGuideText_ExplainsSafeFirstHireAndNaturalCommands()
        {
            string text = CompanionHireNpc.BuildBeginnerGuideText();

            Assert.That(text, Does.Contain("치유형"));
            Assert.That(text, Does.Contain("상태"));
            Assert.That(text, Does.Contain("ㄱㄱ"));
            Assert.That(text, Does.Contain("사냥터"));
            Assert.That(text, Does.Contain("용병 해산"));
        }

        [Test]
        public void BuildVeteranGuideText_ExplainsSupportRoleAndProgressionManagement()
        {
            string text = CompanionHireNpc.BuildVeteranGuideText();

            Assert.That(text, Does.Contain("지원형"));
            Assert.That(text, Does.Contain("메즈"));
            Assert.That(text, Does.Contain("스피드송"));
            Assert.That(text, Does.Contain("친밀도"));
            Assert.That(text, Does.Contain("피로"));
            Assert.That(text, Does.Contain("친밀도 불이익 없이"));
        }

        [Test]
        public void BuildNoRequestStatusText_PointsNewPlayerToGuideOrSafeHire()
        {
            string text = CompanionHireNpc.BuildNoRequestStatusText();

            Assert.That(text, Does.Contain("아직 접수된 용병 요청이 없습니다"));
            Assert.That(text, Does.Contain("[처음 안내]"));
            Assert.That(text, Does.Contain("[추천 고용]"));
            Assert.That(text, Does.Contain("[치유형 고용]"));
        }

        [Test]
        public void RecommendRoleForPlayer_PrefersSafeHealerForLowLevelOrSoloDamageDealer()
        {
            Assert.That(
                CompanionHireNpc.RecommendRoleForPlayer(5, "Armsman", 1),
                Is.EqualTo(CompanionRequestRoles.Healer));
            Assert.That(
                CompanionHireNpc.RecommendRoleForPlayer(24, "Wizard", 1),
                Is.EqualTo(CompanionRequestRoles.Healer));
        }

        [Test]
        public void RecommendRoleForPlayer_PrefersTankForHealerAndSupportForSmallParty()
        {
            Assert.That(
                CompanionHireNpc.RecommendRoleForPlayer(24, "Cleric", 1),
                Is.EqualTo(CompanionRequestRoles.Tank));
            Assert.That(
                CompanionHireNpc.RecommendRoleForPlayer(24, "Wizard", 3),
                Is.EqualTo(CompanionRequestRoles.Support));
        }

        [Test]
        public void BuildRecommendedHireLine_ExplainsRecommendedRole()
        {
            string solo = CompanionHireNpc.BuildRecommendedHireLine(8, "Scout", 1);
            string group = CompanionHireNpc.BuildRecommendedHireLine(30, "Wizard", 4);

            Assert.That(solo, Does.Contain("추천: 치유형 용병"));
            Assert.That(solo, Does.Contain("가장 안전"));
            Assert.That(group, Does.Contain("추천: 지원형 용병"));
            Assert.That(group, Does.Contain("메즈"));
            Assert.That(group, Does.Contain("스피드송"));
        }

        [Test]
        public void BuildDisplaySummary_ActiveRequestShowsContractMercenaryAndRecovery()
        {
            DateTime now = new(2026, 6, 21, 10, 0, 0, DateTimeKind.Utc);
            CompanionRequest request = new()
            {
                Status = CompanionRequestStatus.Active,
                RequestedRole = CompanionRequestRoles.Healer,
                ContractTier = CompanionContractTiers.Skilled,
                ContractDurationSeconds = 45 * 60,
                OfflineGraceSeconds = 5 * 60,
                ContractStartedUtc = now.AddMinutes(-10),
                AssignedCompanionName = "Albtest001",
                MercenaryId = "merc1",
                MercenaryName = "마리엘",
                MercenaryClassName = "Cleric",
                MercenaryPersonality = "wary_survivor",
                MercenaryTacticPreset = "heal_priority",
                MercenaryTrust = 76,
                MercenaryFatigue = 12,
                MercenaryTotalContracts = 6,
                MercenaryTotalContractMinutes = 143,
                MercenaryKillsTogether = 22,
                MercenaryRescues = 4,
                MercenaryQuestsCompleted = 2,
                MercenaryEarnedTitles = "위기 구원자|의뢰 해결사",
                MercenaryPersonalQuestState = "completed:first_bond",
                GroupSize = 2,
                VacantSlots = 6,
                Message = "live companion heartbeat"
            };

            CompanionRequestDisplaySummary summary = CompanionRequestService.BuildDisplaySummary(request, now);

            Assert.That(summary.Lines, Does.Contain("상태: 계약 진행 중"));
            Assert.That(summary.Lines.Any(line => line.Contains("역할: 치유 / 등급: 숙련")), Is.True);
            Assert.That(summary.Lines.Any(line => line.Contains("마리엘 Cleric")), Is.True);
            Assert.That(summary.Lines.Any(line => line.Contains("위기 구원자")), Is.True);
            Assert.That(summary.Lines.Any(line => line.Contains("계약 6회/143분")), Is.True);
            Assert.That(summary.Lines.Any(line => line.Contains("처치 기여 22회")), Is.True);
            Assert.That(summary.Lines.Any(line => line.Contains("개인 의뢰 신뢰의 첫 증표 완료")), Is.True);
            Assert.That(summary.Lines.Any(line => line.Contains("남은 시간 약 35분")), Is.True);
            Assert.That(summary.Lines.Any(line => line.Contains("상태 갱신이 끊기면 자동 정리")), Is.True);
        }

        [Test]
        public void BuildDisplaySummary_CompletedRequestShowsResultAndContribution()
        {
            DateTime now = new(2026, 6, 21, 10, 0, 0, DateTimeKind.Utc);
            CompanionRequest request = new()
            {
                Status = CompanionRequestStatus.Completed,
                RequestedRole = CompanionRequestRoles.Dps,
                ContractTier = CompanionContractTiers.Common,
                ContractDurationSeconds = 30 * 60,
                ContractStartedUtc = now.AddMinutes(-12),
                AssignedCompanionName = "Albtest002",
                CloseReason = "boss_defeated",
                SuppressedKillCredits = 2,
                SuppressedRealmPoints = 150,
                Message = "behavior client exited with 0"
            };

            CompanionRequestDisplaySummary summary = CompanionRequestService.BuildDisplaySummary(request, now);

            Assert.That(summary.Lines, Does.Contain("상태: 계약 종료"));
            Assert.That(summary.Lines.Any(line => line.Contains("결과: 강적 처치 완료")), Is.True);
            Assert.That(summary.Lines.Any(line => line.Contains("처치 기여 2")), Is.True);
            Assert.That(summary.Lines.Any(line => line.Contains("RVR 보상 제한 150")), Is.True);
        }

        [Test]
        public void BuildDisplaySummary_SystemFailureShowsSafeRetryRecovery()
        {
            CompanionRequest request = new()
            {
                Status = CompanionRequestStatus.Failed,
                RequestedRole = CompanionRequestRoles.Support,
                ContractTier = CompanionContractTiers.Common,
                CloseReason = "system_attach_failed",
                Message = "group attach failed"
            };

            CompanionRequestDisplaySummary summary = CompanionRequestService.BuildDisplaySummary(request);

            Assert.That(summary.Lines, Does.Contain("상태: 실패"));
            Assert.That(summary.Lines.Any(line => line.Contains("결과: 실패 - 파티 합류 실패")), Is.True);
            Assert.That(summary.Lines.Any(line => line.Contains("친밀도 불이익 없이 다시 고용")), Is.True);
        }
    }
}
