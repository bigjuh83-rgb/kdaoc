using System.Linq;
using DOL.Database;
using DOL.GS.WorldAI;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_WorldEventService
    {
        [Test]
        public void SeedBossBorn_CreatesWorldEventAndLlmJobs()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = new(
                events,
                jobs,
                results,
                new LlmResultValidationService(),
                new FakeLlmResultGenerator());
            WorldEventService service = new(events, queue);

            WorldEventSeedResult result = service.SeedBossBornSample();

            Assert.Multiple(() =>
            {
                Assert.That(result.Event.EventType, Is.EqualTo(WorldAiEventTypes.BossBorn));
                Assert.That(result.Event.ActorName, Is.EqualTo("붉은 송곳니 그락"));
                Assert.That(events.Rows, Has.Count.EqualTo(1));
                Assert.That(jobs.Rows.Values.Count(job => job.JobType == WorldAiJobTypes.WorldNews), Is.EqualTo(1));
                Assert.That(jobs.Rows.Values.Count(job => job.JobType == WorldAiJobTypes.ChronicleEntry), Is.EqualTo(1));
                Assert.That(jobs.Rows.Values.All(job => job.Status == WorldAiJobStatuses.Pending), Is.True);
            });
        }

        [Test]
        public void SeedBossBorn_StoresLocationForGmSeeCommand()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = new(
                events,
                jobs,
                results,
                new LlmResultValidationService(),
                new FakeLlmResultGenerator());
            WorldEventService service = new(events, queue);
            service.SeedBossBornSample();

            bool found = service.TryGetLatestEventLocation(WorldAiEventTypes.BossBorn, out WorldEventLocation location);

            Assert.Multiple(() =>
            {
                Assert.That(found, Is.True);
                Assert.That(location.RegionId, Is.EqualTo(1));
                Assert.That(location.X, Is.GreaterThan(0));
                Assert.That(location.Y, Is.GreaterThan(0));
                Assert.That(location.Name, Is.EqualTo("bossborn"));
                Assert.That(location.ActorName, Is.EqualTo("붉은 송곳니 그락"));
            });
        }

        [Test]
        public void SeedBossBorn_ReusesExistingSampleAndDoesNotCreateDuplicateJobs()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = new(
                events,
                jobs,
                results,
                new LlmResultValidationService(),
                new FakeLlmResultGenerator());
            WorldEventService service = new(events, queue);

            WorldEventSeedResult first = service.SeedBossBornSample();
            WorldEventSeedResult second = service.SeedBossBornSample();

            Assert.Multiple(() =>
            {
                Assert.That(second.Event.EventId, Is.EqualTo(first.Event.EventId));
                Assert.That(events.Rows, Has.Count.EqualTo(1));
                Assert.That(jobs.Rows.Values.Count(job => job.JobType == WorldAiJobTypes.WorldNews), Is.EqualTo(1));
                Assert.That(jobs.Rows.Values.Count(job => job.JobType == WorldAiJobTypes.ChronicleEntry), Is.EqualTo(1));
            });
        }

        [Test]
        public void RejectDuplicateBossBornSampleJobs_KeepsOneActiveJobPerType()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = new(
                events,
                jobs,
                results,
                new LlmResultValidationService(),
                new FakeLlmResultGenerator());
            WorldEventService service = new(events, queue);
            WorldEventSeedResult first = service.SeedBossBornSample();
            events.Rows.Remove(first.Event.EventId);
            WorldEventSeedResult second = service.SeedBossBornSample();
            events.Rows[first.Event.EventId] = first.Event;

            int rejected = service.RejectDuplicateBossBornSampleJobs();

            Assert.Multiple(() =>
            {
                Assert.That(rejected, Is.EqualTo(2));
                Assert.That(jobs.Rows.Values.Count(job => job.JobType == WorldAiJobTypes.WorldNews && job.Status == WorldAiJobStatuses.Pending), Is.EqualTo(1));
                Assert.That(jobs.Rows.Values.Count(job => job.JobType == WorldAiJobTypes.ChronicleEntry && job.Status == WorldAiJobStatuses.Pending), Is.EqualTo(1));
                Assert.That(jobs.Rows.Values.Count(job => job.Status == WorldAiJobStatuses.Rejected), Is.EqualTo(2));
                Assert.That(second.Event, Is.Not.Null);
            });
        }

        [Test]
        public void CalculateImportance_UsesSurvivalAndKillThresholds()
        {
            WorldEventService service = new(new FakeWorldEventRepository(), CreateQueue());

            Assert.Multiple(() =>
            {
                Assert.That(service.CalculateImportance(0, 0), Is.EqualTo(WorldAiImportance.Minor));
                Assert.That(service.CalculateImportance(1, 0), Is.EqualTo(WorldAiImportance.Normal));
                Assert.That(service.CalculateImportance(7, 0), Is.EqualTo(WorldAiImportance.Major));
                Assert.That(service.CalculateImportance(30, 0), Is.EqualTo(WorldAiImportance.Legendary));
                Assert.That(service.CalculateImportance(0, 200), Is.EqualTo(WorldAiImportance.Legendary));
            });
        }

        [Test]
        public void RecordEvent_CreatesEventAndJobsWithApprovalFlag()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = new(
                events,
                jobs,
                results,
                new LlmResultValidationService(),
                new FakeLlmResultGenerator());
            WorldEventService service = new(events, queue);

            WorldEventSeedResult result = service.RecordEvent(new WorldEventRecordRequest
            {
                EventType = "elite_promoted",
                Region = "카멜롯 힐스",
                ActorName = "검은 가지 늑대",
                AliveDays = 3,
                Kills = 14,
                RequiresGmApproval = true,
                RawDataJson = "{\"source\":\"unit-test\"}"
            });

            Assert.Multiple(() =>
            {
                Assert.That(result.Event.EventType, Is.EqualTo("elite_promoted"));
                Assert.That(result.Event.Importance, Is.EqualTo(WorldAiImportance.Normal));
                Assert.That(result.Event.RequiresGmApproval, Is.True);
                Assert.That(result.Event.IsPublic, Is.False);
                Assert.That(jobs.Rows.Values.Count(job => job.EventId == result.Event.EventId), Is.EqualTo(2));
            });
        }

        [Test]
        public void ApproveEvent_PublishesValidatedEventAndClearsApprovalFlag()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = new(
                events,
                jobs,
                results,
                new LlmResultValidationService(),
                new FakeLlmResultGenerator());
            WorldEventService service = new(events, queue);
            WorldEventSeedResult seed = service.RecordEvent(new WorldEventRecordRequest
            {
                EventType = "elite_promoted",
                Region = "카멜롯 힐스",
                ActorName = "검은 가지 늑대",
                AliveDays = 3,
                Kills = 14,
                RequiresGmApproval = true
            });
            queue.ProcessFake(10);

            bool approved = service.ApprovePublicEvent(seed.Event.EventId);

            Assert.Multiple(() =>
            {
                Assert.That(approved, Is.True);
                Assert.That(seed.Event.IsPublic, Is.True);
                Assert.That(seed.Event.RequiresGmApproval, Is.False);
            });
        }

        [Test]
        public void GetPendingApprovalEvents_ReturnsOnlyValidatedPrivateEvents()
        {
            FakeWorldEventRepository events = new();
            WorldEventService service = new(events, CreateQueue());
            DbWorldEventLog waiting = WorldAiTestData.CreateEvent(isPublic: false);
            waiting.RequiresGmApproval = true;
            waiting.PublicText = "검증된 공개문";
            DbWorldEventLog privateDraft = WorldAiTestData.CreateEvent(isPublic: false);
            privateDraft.RequiresGmApproval = true;
            privateDraft.PublicText = string.Empty;
            events.Add(waiting);
            events.Add(privateDraft);

            DbWorldEventLog[] approvals = service.GetPendingApprovalEvents(10).ToArray();

            Assert.That(approvals, Has.Length.EqualTo(1));
            Assert.That(approvals[0].EventId, Is.EqualTo(waiting.EventId));
        }

        private static LlmJobQueueService CreateQueue()
        {
            return new LlmJobQueueService(
                new FakeWorldEventRepository(),
                new FakeLlmJobRepository(),
                new FakeLlmResultRepository(),
                new LlmResultValidationService(),
                new FakeLlmResultGenerator());
        }
    }
}
