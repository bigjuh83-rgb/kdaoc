using System.Linq;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_GameLoopTickPacerStats
    {
        [Test]
        public void GetAverageTicks_WithNoRecordedTicks_ShouldReturnZeroForEachInterval()
        {
            GameLoopTickPacerStats stats = new(new() { 10000, 30000, 60000 }, 30);

            var averages = stats.GetAverageTicks();

            Assert.That(averages, Has.Count.EqualTo(3));
            Assert.That(averages.All(x => x.Item2 == 0), Is.True);
        }
    }
}
