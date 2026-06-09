using System;
using System.Collections;
using System.IO;
using System.Reflection;
using System.Text;
using DOL.Language;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_LanguageMgr
    {
        [Test]
        public void ReadLanguageDirectory_WithEscapedNewlines_ShouldNormalizeText()
        {
            string tempPath = Path.Combine(Path.GetTempPath(), $"opendaoc-lang-{Guid.NewGuid():N}");
            Directory.CreateDirectory(tempPath);

            try
            {
                File.WriteAllText(
                    Path.Combine(tempPath, "OtherSentences.txt"),
                    "Test.Key: 첫 줄\\n둘째 줄\\n[선택]\n",
                    Encoding.UTF8);

                IList entries = ReadLanguageDirectory(tempPath, "KR");
                object entry = entries[0];
                string text = (string) entry.GetType().GetProperty("Text")!.GetValue(entry)!;

                Assert.That(text, Is.EqualTo("첫 줄\n둘째 줄\n[선택]"));
            }
            finally
            {
                Directory.Delete(tempPath, true);
            }
        }

        [TestCase("훈련검을(를) 장비했습니다.", "훈련검을 장비했습니다.")]
        [TestCase("개인 귀환석을(를) 장비했습니다.", "개인 귀환석을 장비했습니다.")]
        [TestCase("후후이(가) 그룹에 참가했습니다.", "후후가 그룹에 참가했습니다.")]
        [TestCase("성검(으)로 변경했습니다.", "성검으로 변경했습니다.")]
        [TestCase("망치(으)로 변경했습니다.", "망치로 변경했습니다.")]
        [TestCase("[녹색 뱀]을(를) 대상으로 삼았습니다.", "[녹색 뱀]을 대상으로 삼았습니다.")]
        [TestCase("Sprint을(를) 사용했습니다.", "Sprint를 사용했습니다.")]
        [TestCase("Albtest007이(가) 그룹에 참가했습니다.", "Albtest007이 그룹에 참가했습니다.")]
        [TestCase("NPC3은(는) 너무 멀리 있습니다.", "NPC3은 너무 멀리 있습니다.")]
        [TestCase("Caer Ulfwych(으)로 이동합니다.", "Caer Ulfwych로 이동합니다.")]
        public void ApplyKoreanParticles_ShouldSelectNaturalParticle(string source, string expected)
        {
            Assert.That(ApplyKoreanParticles(source), Is.EqualTo(expected));
        }

        private static IList ReadLanguageDirectory(string path, string language)
        {
            MethodInfo method = typeof(LanguageMgr).GetMethod("ReadLanguageDirectory", BindingFlags.Static | BindingFlags.NonPublic)!;
            return (IList) method.Invoke(null, new object[] { path, language })!;
        }

        private static string ApplyKoreanParticles(string text)
        {
            return LanguageMgr.ApplyKoreanParticles(text);
        }
    }
}
