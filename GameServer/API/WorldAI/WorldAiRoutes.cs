using System.Linq;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;
using DOL.GS.ServerProperties;
using DOL.GS.WorldAI;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace DOL.GS.API.WorldAI
{
    internal static class WorldAiRoutes
    {
        public static void MapWorldAiRoutes(this WebApplication api)
        {
            WorldNewsService provider = WorldNewsService.Instance;

            api.MapGet("/api/world/events", (HttpContext context) =>
                Results.Ok(provider.GetEvents(ReadLimit(context, 20))));

            api.MapGet("/api/world/news", (HttpContext context) =>
                Results.Ok(provider.GetNews(ReadLimit(context, 10))));

            api.MapGet("/api/world/llm/jobs", (HttpContext context) =>
                Results.Ok(LlmJobQueueService.Instance.GetPendingWorkItems(ReadLimit(context, 10))));

            api.MapGet("/api/world/llm/jobs/detail", (HttpContext context) =>
                Results.Ok(LlmJobQueueService.Instance.GetJobDetails(ReadLimit(context, 20))));

            api.MapGet("/api/world/llm/health", () =>
                Results.Ok(LlmJobQueueService.Instance.GetQueueHealth()));

            api.MapGet("/api/world/mob-growth/summary", (HttpContext context) =>
                Results.Ok(MobGrowthService.Instance.GetSummary(ReadLimit(context, 20))));

            api.MapGet("/api/world/llm/config", () =>
                Results.Ok(new
                {
                    apiUrl = Properties.WORLDAI_LLM_API_URL,
                    model = Properties.WORLDAI_LLM_MODEL,
                    timeoutSeconds = Properties.WORLDAI_LLM_TIMEOUT_SECONDS
                }));

            api.MapGet("/api/world/llm/check", () =>
            {
                OpenAiCompatibleLlmResultGenerator generator = new(
                    Properties.WORLDAI_LLM_API_URL,
                    Properties.WORLDAI_LLM_MODEL,
                    Properties.WORLDAI_LLM_TIMEOUT_SECONDS);
                return Results.Ok(generator.CheckConnection(Properties.WORLDAI_LLM_API_URL));
            });

            api.MapPost("/api/world/llm/jobs/claim", (HttpContext context) =>
                Results.Ok(LlmJobQueueService.Instance.ClaimPendingWorkItems(ReadLimit(context, 10))));

            api.MapPost("/api/world/llm/jobs/reclaim", (HttpContext context) =>
                Results.Ok(new
                {
                    reclaimed = LlmJobQueueService.Instance.ReclaimStaleClaimedJobs(ReadMinutes(context, 15))
                }));

            api.MapPost("/api/world/llm/jobs/{jobId}/result", SubmitLlmJobResult);

            api.MapPost("/api/world/llm/jobs/{jobId}/retry", (string jobId) =>
            {
                LlmJobSubmissionResult result = LlmJobQueueService.Instance.RetryJob(jobId);
                return result.Accepted ? Results.Ok(result) : Results.BadRequest(result);
            });

            api.MapPost("/api/world/llm/jobs/{jobId}/reject", RejectLlmJob);
        }

        private static int ReadLimit(HttpContext context, int defaultLimit)
        {
            string raw = context.Request.Query["limit"].FirstOrDefault();

            if (!int.TryParse(raw, out int limit))
                return defaultLimit;

            return limit;
        }

        private static int ReadMinutes(HttpContext context, int defaultMinutes)
        {
            string raw = context.Request.Query["minutes"].FirstOrDefault();

            if (!int.TryParse(raw, out int minutes))
                return defaultMinutes;

            return minutes;
        }

        private static async Task<IResult> SubmitLlmJobResult(HttpContext context, string jobId)
        {
            using JsonDocument document = await JsonDocument.ParseAsync(context.Request.Body);
            string resultJson = ExtractResultJson(document.RootElement);
            LlmJobSubmissionResult result = LlmJobQueueService.Instance.SubmitExternalResult(jobId, resultJson);

            return result.Accepted ? Results.Ok(result) : Results.BadRequest(result);
        }

        private static async Task<IResult> RejectLlmJob(HttpContext context, string jobId)
        {
            using StreamReader reader = new(context.Request.Body);
            string reason = ExtractReason(await reader.ReadToEndAsync());
            LlmJobSubmissionResult result = LlmJobQueueService.Instance.RejectJob(jobId, reason);

            return result.Accepted ? Results.Ok(result) : Results.BadRequest(result);
        }

        private static string ExtractResultJson(JsonElement root)
        {
            if (root.ValueKind == JsonValueKind.Object &&
                root.TryGetProperty("resultJson", out JsonElement resultJson) &&
                resultJson.ValueKind == JsonValueKind.String)
                return resultJson.GetString() ?? string.Empty;

            return root.GetRawText();
        }

        private static string ExtractReason(string body)
        {
            if (string.IsNullOrWhiteSpace(body))
                return "Rejected by API.";

            try
            {
                using JsonDocument document = JsonDocument.Parse(body);

                if (document.RootElement.ValueKind == JsonValueKind.Object &&
                    document.RootElement.TryGetProperty("reason", out JsonElement reason) &&
                    reason.ValueKind == JsonValueKind.String)
                    return reason.GetString() ?? "Rejected by API.";
            }
            catch (JsonException)
            {
                // Plain text bodies are accepted for quick local operator scripts.
            }

            return body.Trim();
        }
    }
}
