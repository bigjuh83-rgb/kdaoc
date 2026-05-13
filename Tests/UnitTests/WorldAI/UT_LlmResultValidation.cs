using System.Linq;
using DOL.GS.WorldAI;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_LlmResultValidation
    {
        private readonly LlmResultValidationService m_validator = new();

        [Test]
        public void Validate_RejectsBrokenJson()
        {
            LlmValidationResult result = m_validator.Validate(WorldAiJobTypes.WorldNews, "{broken");

            Assert.Multiple(() =>
            {
                Assert.That(result.IsValid, Is.False);
                Assert.That(result.Errors.Any(error => error.Contains("JSON")), Is.True);
            });
        }

        [Test]
        public void Validate_RejectsMissingRequiredFields()
        {
            LlmValidationResult result = m_validator.Validate(WorldAiJobTypes.WorldNews, "{\"title\":\"소식\"}");

            Assert.Multiple(() =>
            {
                Assert.That(result.IsValid, Is.False);
                Assert.That(result.Errors.Any(error => error.Contains("body")), Is.True);
                Assert.That(result.Errors.Any(error => error.Contains("importance")), Is.True);
            });
        }

        [Test]
        public void Validate_RejectsForbiddenNumericAndRewardFields()
        {
            string json = "{\"title\":\"소식\",\"body\":\"보상이 들어간 소식\",\"importance\":\"Normal\",\"reward\":{\"gold\":100}}";

            LlmValidationResult result = m_validator.Validate(WorldAiJobTypes.WorldNews, json);

            Assert.Multiple(() =>
            {
                Assert.That(result.IsValid, Is.False);
                Assert.That(result.Errors.Any(error => error.Contains("reward")), Is.True);
                Assert.That(result.Errors.Any(error => error.Contains("gold")), Is.True);
            });
        }

        [Test]
        public void Validate_AcceptsValidWorldNews()
        {
            string json = "{\"title\":\"붉은 송곳니 그락 출현\",\"body\":\"북부 숲에서 새로운 위협이 보고되었습니다.\",\"importance\":\"Major\"}";

            LlmValidationResult result = m_validator.Validate(WorldAiJobTypes.WorldNews, json);

            Assert.That(result.IsValid, Is.True);
            Assert.That(result.Errors, Is.Empty);
        }

        [Test]
        public void Validate_AcceptsValidChronicleEntry()
        {
            string json = "{\"summary\":\"붉은 송곳니 그락 출현\",\"chronicle\":\"북부 숲에서 오래 살아남은 고블린이 부족을 모으기 시작했다.\"}";

            LlmValidationResult result = m_validator.Validate(WorldAiJobTypes.ChronicleEntry, json);

            Assert.That(result.IsValid, Is.True);
            Assert.That(result.Errors, Is.Empty);
        }
    }
}
