using System.Collections.Generic;
using System.IO;
using System.Text;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_LanguageFormatStrings
    {
        [Test]
        public void LiteralBraceHelpEntries_ShouldParseAsCompositeFormat()
        {
            string root = FindRepoRoot();
            string[] entries =
            {
                "GMCommands.Mob.TriggerHelpKeywords",
                "GMCommands.Mob.TriggerHelpExample3",
                "GMCommands.Mob.TriggerHelpExample4",
                "GMCommands.Mob.TriggerHelpExample5",
                "GMCommands.Mob.TriggerHelpUsageAdd",
                "GMCommands.Keep.Usage.Move"
            };

            foreach (string language in new[] { "EN", "KR" })
            foreach (string entry in entries)
            {
                string text = FindLanguageEntry(root, language, entry);

                Assert.That(
                    () => CompositeFormat.Parse(text),
                    Throws.Nothing,
                    $"{language}:{entry}");
            }
        }

        private static string FindRepoRoot()
        {
            DirectoryInfo dir = new(TestContext.CurrentContext.TestDirectory);

            while (dir != null)
            {
                if (Directory.Exists(Path.Combine(dir.FullName, "GameServer", "language")))
                    return dir.FullName;

                dir = dir.Parent;
            }

            Assert.Fail("Could not locate repository root from test directory.");
            return string.Empty;
        }

        private static string FindLanguageEntry(string root, string language, string key)
        {
            string languageRoot = Path.Combine(root, "GameServer", "language", language);
            foreach (string file in Directory.EnumerateFiles(languageRoot, "*.txt", SearchOption.AllDirectories))
            {
                foreach (string line in File.ReadLines(file))
                {
                    if (!line.StartsWith(key + ":"))
                        continue;

                    return line[(key.Length + 1)..].Trim();
                }
            }

            Assert.Fail($"Missing language entry {language}:{key}");
            return string.Empty;
        }
    }
}
