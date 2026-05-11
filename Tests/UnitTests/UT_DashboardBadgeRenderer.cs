using System;
using DOL.GS.API.Dashboard;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_DashboardBadgeRenderer
    {
        [Test]
        public void Render_ReturnsPngImage()
        {
            DashboardLiveResponse live = new(
                12,
                DashboardAggregation.BuildRealmStats(3, 4, 5),
                Array.Empty<DashboardClassStats>(),
                new DashboardPerformanceStats(0, 0),
                "00:10:00",
                new DateTime(2026, 5, 11, 12, 0, 0, DateTimeKind.Utc),
                new DateTime(2026, 5, 11, 12, 10, 0, DateTimeKind.Utc));

            byte[] png = DashboardBadgeRenderer.Render(live);

            Assert.Multiple(() =>
            {
                Assert.That(png, Has.Length.GreaterThan(100));
                Assert.That(png[..8], Is.EqualTo(new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 }));
            });
        }
    }
}
