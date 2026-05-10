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

        private static IList ReadLanguageDirectory(string path, string language)
        {
            MethodInfo method = typeof(LanguageMgr).GetMethod("ReadLanguageDirectory", BindingFlags.Static | BindingFlags.NonPublic)!;
            return (IList) method.Invoke(null, new object[] { path, language })!;
        }
    }
}
