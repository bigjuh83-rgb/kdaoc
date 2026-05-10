using DOL.GS.PacketHandler.Client.v168;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_PlayerInitRequestHandler
    {
        [TestCase("KR", true)]
        [TestCase("kr", true)]
        [TestCase("EN", false)]
        [TestCase(null, false)]
        public void ShouldUseCustomTextWindowForStarterHelp_ShouldOnlyRouteKoreanClients(string language, bool expected)
        {
            Assert.That(PlayerInitRequestHandler.ShouldUseCustomTextWindowForStarterHelp(language), Is.EqualTo(expected));
        }
    }
}
