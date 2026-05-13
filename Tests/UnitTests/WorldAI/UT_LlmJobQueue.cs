using System.Collections.Generic;
using System;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using DOL.Database;
using DOL.GS.WorldAI;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_LlmJobQueue
    {
        [Test]
        public void Enqueue_CreatesPendingJob()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = CreateQueue(events, jobs, results);
            DbWorldEventLog worldEvent = WorldAiTestData.CreateEvent();
            events.Add(worldEvent);

            DbLlmJob job = queue.Enqueue(WorldAiJobTypes.WorldNews, worldEvent.EventId, "kr", "{\"kind\":\"test\"}");

            Assert.Multiple(() =>
            {
                Assert.That(job.Status, Is.EqualTo(WorldAiJobStatuses.Pending));
                Assert.That(job.EventId, Is.EqualTo(worldEvent.EventId));
                Assert.That(jobs.Rows, Has.Count.EqualTo(1));
            });
        }

        [Test]
        public void ProcessFake_CompletesPendingJobAndAppliesPublicText()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = CreateQueue(events, jobs, results);
            DbWorldEventLog worldEvent = WorldAiTestData.CreateEvent();
            events.Add(worldEvent);
            queue.Enqueue(WorldAiJobTypes.WorldNews, worldEvent.EventId, "kr", "{}");

            LlmJobProcessingSummary summary = queue.ProcessFake(10);

            Assert.Multiple(() =>
            {
                Assert.That(summary.Completed, Is.EqualTo(1));
                Assert.That(summary.Rejected, Is.EqualTo(0));
                Assert.That(jobs.Rows.Values.Single().Status, Is.EqualTo(WorldAiJobStatuses.Completed));
                Assert.That(results.Rows.Values.Single().ValidationStatus, Is.EqualTo(WorldAiValidationStatuses.Valid));
                Assert.That(worldEvent.IsPublic, Is.True);
                Assert.That(worldEvent.PublicText, Is.Not.Empty);
            });
        }

        [Test]
        public void ProcessFake_RejectsJobWhenValidationFails()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = CreateQueue(events, jobs, results, new InvalidLlmResultGenerator());
            DbWorldEventLog worldEvent = WorldAiTestData.CreateEvent();
            events.Add(worldEvent);
            queue.Enqueue(WorldAiJobTypes.WorldNews, worldEvent.EventId, "kr", "{}");

            LlmJobProcessingSummary summary = queue.ProcessFake(10);

            Assert.Multiple(() =>
            {
                Assert.That(summary.Completed, Is.EqualTo(0));
                Assert.That(summary.Rejected, Is.EqualTo(1));
                Assert.That(jobs.Rows.Values.Single().Status, Is.EqualTo(WorldAiJobStatuses.Rejected));
                Assert.That(results.Rows.Values.Single().ValidationStatus, Is.EqualTo(WorldAiValidationStatuses.Rejected));
                Assert.That(worldEvent.IsPublic, Is.False);
            });
        }

        [Test]
        public void ProcessFake_DoesNotPublishApprovalRequiredEvent()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = CreateQueue(events, jobs, results);
            DbWorldEventLog worldEvent = WorldAiTestData.CreateEvent();
            worldEvent.RequiresGmApproval = true;
            events.Add(worldEvent);
            queue.Enqueue(WorldAiJobTypes.WorldNews, worldEvent.EventId, "kr", "{}");

            LlmJobProcessingSummary summary = queue.ProcessFake(10);

            Assert.Multiple(() =>
            {
                Assert.That(summary.Completed, Is.EqualTo(1));
                Assert.That(worldEvent.PublicText, Is.Not.Empty);
                Assert.That(worldEvent.IsPublic, Is.False);
                Assert.That(worldEvent.RequiresGmApproval, Is.True);
            });
        }

        [Test]
        public void GetPendingWorkItems_ReturnsWorkerSafeContract()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = CreateQueue(events, jobs, results);
            DbWorldEventLog worldEvent = WorldAiTestData.CreateEvent();
            events.Add(worldEvent);
            DbLlmJob job = queue.Enqueue(WorldAiJobTypes.WorldNews, worldEvent.EventId, "kr", "{\"kind\":\"test\"}");

            LlmWorkItem workItem = queue.GetPendingWorkItems(10).Single();

            Assert.Multiple(() =>
            {
                Assert.That(workItem.JobId, Is.EqualTo(job.JobId));
                Assert.That(workItem.JobType, Is.EqualTo(WorldAiJobTypes.WorldNews));
                Assert.That(workItem.EventId, Is.EqualTo(worldEvent.EventId));
                Assert.That(workItem.PayloadJson, Does.Contain("kind"));
                Assert.That(workItem.SchemaJson, Does.Contain("title"));
                Assert.That(workItem.Instructions, Does.Contain("JSON"));
                Assert.That(workItem.Instructions, Does.Not.Contain(worldEvent.GmNote));
            });
        }

        [Test]
        public void ClaimPendingWorkItems_MarksJobsClaimedAndDoesNotReturnThemTwice()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = CreateQueue(events, jobs, results);
            DbWorldEventLog worldEvent = WorldAiTestData.CreateEvent();
            events.Add(worldEvent);
            DbLlmJob first = queue.Enqueue(WorldAiJobTypes.WorldNews, worldEvent.EventId, "kr", "{\"kind\":\"first\"}");
            DbLlmJob second = queue.Enqueue(WorldAiJobTypes.ChronicleEntry, worldEvent.EventId, "kr", "{\"kind\":\"second\"}");

            IList<LlmWorkItem> claimed = queue.ClaimPendingWorkItems(1);
            IList<LlmWorkItem> nextClaimed = queue.ClaimPendingWorkItems(10);

            Assert.Multiple(() =>
            {
                Assert.That(claimed, Has.Count.EqualTo(1));
                Assert.That(claimed.Single().JobId, Is.EqualTo(first.JobId));
                Assert.That(first.Status, Is.EqualTo(WorldAiJobStatuses.Claimed));
                Assert.That(second.Status, Is.EqualTo(WorldAiJobStatuses.Claimed));
                Assert.That(nextClaimed.Single().JobId, Is.EqualTo(second.JobId));
                Assert.That(queue.ClaimPendingWorkItems(10), Is.Empty);
            });
        }

        [Test]
        public void GetQueueHealth_ReportsActiveJobsAndAges()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = CreateQueue(events, jobs, results);
            DbWorldEventLog worldEvent = WorldAiTestData.CreateEvent();
            events.Add(worldEvent);
            DbLlmJob pending = queue.Enqueue(WorldAiJobTypes.WorldNews, worldEvent.EventId, "kr", "{}");
            pending.CreatedAt = DateTime.UtcNow.AddMinutes(-5);
            pending.UpdatedAt = pending.CreatedAt;
            jobs.Save(pending);
            queue.ClaimPendingWorkItems(1);

            LlmQueueHealth health = queue.GetQueueHealth();

            Assert.Multiple(() =>
            {
                Assert.That(health.ActiveJobs, Is.EqualTo(1));
                Assert.That(health.Counts[WorldAiJobStatuses.Claimed], Is.EqualTo(1));
                Assert.That(health.OldestClaimedAgeSeconds, Is.GreaterThanOrEqualTo(0));
            });
        }

        [Test]
        public void ReclaimStaleClaimedJobs_ReturnsOldClaimedJobsToPending()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = CreateQueue(events, jobs, results);
            DbWorldEventLog worldEvent = WorldAiTestData.CreateEvent();
            events.Add(worldEvent);
            DbLlmJob stale = queue.Enqueue(WorldAiJobTypes.WorldNews, worldEvent.EventId, "kr", "{}");
            DbLlmJob fresh = queue.Enqueue(WorldAiJobTypes.ChronicleEntry, worldEvent.EventId, "kr", "{}");
            stale.Status = WorldAiJobStatuses.Claimed;
            stale.UpdatedAt = DateTime.UtcNow.AddMinutes(-30);
            fresh.Status = WorldAiJobStatuses.Claimed;
            fresh.UpdatedAt = DateTime.UtcNow;
            jobs.Save(stale);
            jobs.Save(fresh);

            int reclaimed = queue.ReclaimStaleClaimedJobs(15);

            Assert.Multiple(() =>
            {
                Assert.That(reclaimed, Is.EqualTo(1));
                Assert.That(stale.Status, Is.EqualTo(WorldAiJobStatuses.Pending));
                Assert.That(stale.LastError, Does.Contain("Reclaimed"));
                Assert.That(fresh.Status, Is.EqualTo(WorldAiJobStatuses.Claimed));
            });
        }

        [Test]
        public void SubmitExternalResult_AcceptsClaimedJob()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = CreateQueue(events, jobs, results);
            DbWorldEventLog worldEvent = WorldAiTestData.CreateEvent();
            events.Add(worldEvent);
            DbLlmJob job = queue.Enqueue(WorldAiJobTypes.WorldNews, worldEvent.EventId, "kr", "{}");
            queue.ClaimPendingWorkItems(1);

            LlmJobSubmissionResult submission = queue.SubmitExternalResult(
                job.JobId,
                "{\"title\":\"숲의 위협\",\"body\":\"새로운 보스가 모습을 드러냈습니다.\",\"importance\":\"Major\"}");

            Assert.Multiple(() =>
            {
                Assert.That(submission.Accepted, Is.True);
                Assert.That(job.Status, Is.EqualTo(WorldAiJobStatuses.Completed));
                Assert.That(worldEvent.PublicTitle, Is.EqualTo("숲의 위협"));
            });
        }

        [Test]
        public void RetryJob_ReturnsRejectedJobToPending()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = CreateQueue(events, jobs, results);
            DbWorldEventLog worldEvent = WorldAiTestData.CreateEvent();
            events.Add(worldEvent);
            DbLlmJob job = queue.Enqueue(WorldAiJobTypes.WorldNews, worldEvent.EventId, "kr", "{}");
            queue.SubmitExternalResult(
                job.JobId,
                "{\"title\":\"숲의 위협\",\"body\":\"금화 보상이 포함된 결과입니다.\",\"importance\":\"Major\",\"gold\":100}");

            LlmJobSubmissionResult retry = queue.RetryJob(job.JobId);

            Assert.Multiple(() =>
            {
                Assert.That(retry.Accepted, Is.True);
                Assert.That(job.Status, Is.EqualTo(WorldAiJobStatuses.Pending));
                Assert.That(job.LastError, Is.Empty);
            });
        }

        [Test]
        public void RejectJob_MarksClaimedJobRejectedWithReason()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = CreateQueue(events, jobs, results);
            DbWorldEventLog worldEvent = WorldAiTestData.CreateEvent();
            events.Add(worldEvent);
            DbLlmJob job = queue.Enqueue(WorldAiJobTypes.WorldNews, worldEvent.EventId, "kr", "{}");
            queue.ClaimPendingWorkItems(1);

            LlmJobSubmissionResult rejection = queue.RejectJob(job.JobId, "운영자 수동 거부");

            Assert.Multiple(() =>
            {
                Assert.That(rejection.Accepted, Is.True);
                Assert.That(job.Status, Is.EqualTo(WorldAiJobStatuses.Rejected));
                Assert.That(job.LastError, Is.EqualTo("운영자 수동 거부"));
            });
        }

        [Test]
        public void GetJobDetails_ReturnsMostRecentlyUpdatedJobsFirst()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = CreateQueue(events, jobs, results);
            DbWorldEventLog worldEvent = WorldAiTestData.CreateEvent();
            events.Add(worldEvent);
            DbLlmJob older = queue.Enqueue(WorldAiJobTypes.WorldNews, worldEvent.EventId, "kr", "{}");
            older.UpdatedAt = older.UpdatedAt.AddMinutes(-10);
            DbLlmJob newer = queue.Enqueue(WorldAiJobTypes.ChronicleEntry, worldEvent.EventId, "kr", "{}");

            IList<LlmJobDetail> details = queue.GetJobDetails(10);

            Assert.Multiple(() =>
            {
                Assert.That(details, Has.Count.EqualTo(2));
                Assert.That(details[0].JobId, Is.EqualTo(newer.JobId));
                Assert.That(details[1].JobId, Is.EqualTo(older.JobId));
                Assert.That(details[0].ActorName, Is.EqualTo(worldEvent.ActorName));
            });
        }

        [Test]
        public void SubmitExternalResult_CompletesAndAppliesValidatedJson()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = CreateQueue(events, jobs, results);
            DbWorldEventLog worldEvent = WorldAiTestData.CreateEvent();
            events.Add(worldEvent);
            DbLlmJob job = queue.Enqueue(WorldAiJobTypes.WorldNews, worldEvent.EventId, "kr", "{}");

            LlmJobSubmissionResult submission = queue.SubmitExternalResult(
                job.JobId,
                "{\"title\":\"숲의 위협\",\"body\":\"새로운 보스가 모습을 드러냈습니다.\",\"importance\":\"Major\"}");

            Assert.Multiple(() =>
            {
                Assert.That(submission.Accepted, Is.True);
                Assert.That(submission.Status, Is.EqualTo(WorldAiJobStatuses.Completed));
                Assert.That(job.Status, Is.EqualTo(WorldAiJobStatuses.Completed));
                Assert.That(worldEvent.IsPublic, Is.True);
                Assert.That(worldEvent.PublicTitle, Is.EqualTo("숲의 위협"));
                Assert.That(results.Rows.Values.Single().ValidationStatus, Is.EqualTo(WorldAiValidationStatuses.Valid));
            });
        }

        [Test]
        public void SubmitExternalResult_RejectsForbiddenField()
        {
            FakeWorldEventRepository events = new();
            FakeLlmJobRepository jobs = new();
            FakeLlmResultRepository results = new();
            LlmJobQueueService queue = CreateQueue(events, jobs, results);
            DbWorldEventLog worldEvent = WorldAiTestData.CreateEvent();
            events.Add(worldEvent);
            DbLlmJob job = queue.Enqueue(WorldAiJobTypes.WorldNews, worldEvent.EventId, "kr", "{}");

            LlmJobSubmissionResult submission = queue.SubmitExternalResult(
                job.JobId,
                "{\"title\":\"숲의 위협\",\"body\":\"금화 보상이 포함된 결과입니다.\",\"importance\":\"Major\",\"gold\":100}");

            Assert.Multiple(() =>
            {
                Assert.That(submission.Accepted, Is.False);
                Assert.That(submission.Status, Is.EqualTo(WorldAiJobStatuses.Rejected));
                Assert.That(submission.Errors.Single(), Does.Contain("gold"));
                Assert.That(job.Status, Is.EqualTo(WorldAiJobStatuses.Rejected));
                Assert.That(worldEvent.IsPublic, Is.False);
                Assert.That(results.Rows.Values.Single().ValidationStatus, Is.EqualTo(WorldAiValidationStatuses.Rejected));
            });
        }

        [Test]
        public void OpenAiCompatibleGenerator_ExtractsAssistantJson()
        {
            DbWorldEventLog worldEvent = WorldAiTestData.CreateEvent();
            DbLlmJob job = new()
            {
                JobType = WorldAiJobTypes.WorldNews,
                Language = "kr",
                PayloadJson = "{}"
            };
            HttpClient httpClient = new(new StaticHttpMessageHandler(
                "{\"choices\":[{\"message\":{\"content\":\"{\\\"title\\\":\\\"테스트\\\",\\\"body\\\":\\\"작동 확인\\\",\\\"importance\\\":\\\"Minor\\\"}\"}}]}"))
            {
                BaseAddress = new System.Uri("http://localhost:1234/")
            };
            OpenAiCompatibleLlmResultGenerator generator = new(httpClient, "unit-test-model");

            string json = generator.Generate(job, worldEvent);

            Assert.That(json, Is.EqualTo("{\"title\":\"테스트\",\"body\":\"작동 확인\",\"importance\":\"Minor\"}"));
        }

        [Test]
        public void OpenAiCompatibleGenerator_StripsMarkdownFence()
        {
            DbWorldEventLog worldEvent = WorldAiTestData.CreateEvent();
            DbLlmJob job = new()
            {
                JobType = WorldAiJobTypes.WorldNews,
                Language = "kr",
                PayloadJson = "{}"
            };
            HttpClient httpClient = new(new StaticHttpMessageHandler(
                "{\"choices\":[{\"message\":{\"content\":\"```json\\n{\\\"title\\\":\\\"테스트\\\",\\\"body\\\":\\\"작동 확인\\\",\\\"importance\\\":\\\"Minor\\\"}\\n```\"}}]}"))
            {
                BaseAddress = new System.Uri("http://localhost:1234/")
            };
            OpenAiCompatibleLlmResultGenerator generator = new(httpClient, "unit-test-model");

            string json = generator.Generate(job, worldEvent);

            Assert.That(json, Is.EqualTo("{\"title\":\"테스트\",\"body\":\"작동 확인\",\"importance\":\"Minor\"}"));
        }

        [Test]
        public void OpenAiCompatibleGenerator_CheckConnectionReadsModelList()
        {
            HttpClient httpClient = new(new StaticHttpMessageHandler(
                "{\"data\":[{\"id\":\"gemma-4-e4b-it\"},{\"id\":\"other-model\"}],\"object\":\"list\"}"))
            {
                BaseAddress = new System.Uri("http://192.168.0.42:1234/")
            };
            OpenAiCompatibleLlmResultGenerator generator = new(httpClient, "gemma-4-e4b-it");

            LlmConnectionCheckResult result = generator.CheckConnection("http://192.168.0.42:1234");

            Assert.Multiple(() =>
            {
                Assert.That(result.IsAvailable, Is.True);
                Assert.That(result.ApiUrl, Is.EqualTo("http://192.168.0.42:1234"));
                Assert.That(result.Model, Is.EqualTo("gemma-4-e4b-it"));
                Assert.That(result.AvailableModels, Does.Contain("gemma-4-e4b-it"));
                Assert.That(result.Error, Is.Empty);
            });
        }

        private static LlmJobQueueService CreateQueue(
            FakeWorldEventRepository events,
            FakeLlmJobRepository jobs,
            FakeLlmResultRepository results,
            ILlmResultGenerator generator = null)
        {
            return new LlmJobQueueService(
                events,
                jobs,
                results,
                new LlmResultValidationService(),
                generator ?? new FakeLlmResultGenerator());
        }

        private sealed class StaticHttpMessageHandler : HttpMessageHandler
        {
            private readonly string m_responseJson;

            public StaticHttpMessageHandler(string responseJson)
            {
                m_responseJson = responseJson;
            }

            protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
            {
                HttpResponseMessage response = new(HttpStatusCode.OK)
                {
                    Content = new StringContent(m_responseJson)
                };

                return Task.FromResult(response);
            }
        }
    }
}
