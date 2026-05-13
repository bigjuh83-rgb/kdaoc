using System;
using System.Linq;
using DOL.GS.WorldAI;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_WorldNews
    {
        [Test]
        public void GetNews_ExcludesPrivateEvents()
        {
            FakeWorldEventRepository events = new();
            events.Add(WorldAiTestData.CreateEvent(isPublic: true));
            events.Add(WorldAiTestData.CreateEvent(isPublic: false));
            WorldNewsService service = new(events);

            WorldNewsItem[] news = service.GetNews(10).ToArray();

            Assert.That(news, Has.Length.EqualTo(1));
            Assert.That(news[0].Title, Is.Not.Empty);
        }

        [Test]
        public void GetEvents_ClampsLimitToOneHundred()
        {
            FakeWorldEventRepository events = new();
            DateTime now = DateTime.UtcNow;

            for (int i = 0; i < 150; i++)
                events.Add(WorldAiTestData.CreateEvent(now.AddSeconds(i), true));

            WorldNewsService service = new(events);

            Assert.That(service.GetEvents(500), Has.Count.EqualTo(100));
        }

        [Test]
        public void GetEvents_ReturnsNewestFirst()
        {
            FakeWorldEventRepository events = new();
            events.Add(WorldAiTestData.CreateEvent(new DateTime(2026, 5, 1, 0, 0, 0, DateTimeKind.Utc), true));
            events.Add(WorldAiTestData.CreateEvent(new DateTime(2026, 5, 2, 0, 0, 0, DateTimeKind.Utc), true));
            WorldNewsService service = new(events);

            WorldEventItem[] rows = service.GetEvents(10).ToArray();

            Assert.That(rows[0].CreatedAt, Is.GreaterThan(rows[1].CreatedAt));
        }

        [Test]
        public void PublicDtos_DoNotExposePrivateFields()
        {
            string[] newsProperties = typeof(WorldNewsItem).GetProperties().Select(property => property.Name).ToArray();
            string[] eventProperties = typeof(WorldEventItem).GetProperties().Select(property => property.Name).ToArray();

            Assert.Multiple(() =>
            {
                Assert.That(newsProperties, Does.Not.Contain("RawDataJson"));
                Assert.That(newsProperties, Does.Not.Contain("GmNote"));
                Assert.That(newsProperties, Does.Not.Contain("AccountName"));
                Assert.That(newsProperties, Does.Not.Contain("IpAddress"));
                Assert.That(eventProperties, Does.Not.Contain("RawDataJson"));
                Assert.That(eventProperties, Does.Not.Contain("GmNote"));
                Assert.That(eventProperties, Does.Not.Contain("CharacterLocation"));
            });
        }
    }
}
