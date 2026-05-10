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

        [Test]
        public void ShouldMoveToBindOnInstanceLogin_ShouldMoveWhenRegisteredRegionIsMissing()
        {
            Assert.That(PlayerInitRequestHandler.ShouldMoveToBindOnInstanceLogin(null, CreateRegion(1)), Is.True);
        }

        [Test]
        public void ShouldMoveToBindOnInstanceLogin_ShouldNotMoveForRegisteredNormalRegion()
        {
            Region region = CreateRegion(1);

            Assert.That(PlayerInitRequestHandler.ShouldMoveToBindOnInstanceLogin(region, region), Is.False);
        }

        private static Region CreateRegion(ushort id)
        {
            return new Region(new RegionData
            {
                Id = id,
                Name = $"Region {id}",
                Description = $"Region {id}",
                Mobs = []
            });
        }
    }
}
