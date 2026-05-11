using System.IO;
using System.Linq;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.FileProviders;

namespace DOL.GS.API.Dashboard
{
    internal static class DashboardRoutes
    {
        public static void MapDashboardRoutes(this WebApplication api, string contentRoot)
        {
            string dashboardRoot = Path.Combine(contentRoot, "wwwroot", "dashboard");
            string indexPath = Path.Combine(dashboardRoot, "index.html");
            DashboardStatsProvider provider = new();

            if (Directory.Exists(dashboardRoot))
            {
                api.UseStaticFiles(new StaticFileOptions
                {
                    FileProvider = new PhysicalFileProvider(dashboardRoot),
                    RequestPath = new PathString("/dashboard")
                });
            }

            api.MapGet("/dashboard", () =>
            {
                if (File.Exists(indexPath))
                    return Results.File(indexPath, "text/html");

                return Results.Text(
                    "Dashboard assets are not built yet.",
                    "text/plain",
                    statusCode: StatusCodes.Status503ServiceUnavailable);
            });

            api.MapGet("/api/dashboard/live", () => Results.Ok(provider.GetLive()));
            api.MapGet("/api/dashboard/history", (HttpContext context) =>
                Results.Ok(provider.GetHistory(context.Request.Query["range"].FirstOrDefault())));
            api.MapGet("/api/dashboard/realm-activity", (HttpContext context) =>
                Results.Ok(provider.GetRealmActivity(context.Request.Query["range"].FirstOrDefault())));
            api.MapGet("/status/badge.png", (HttpContext context) =>
            {
                context.Response.Headers.CacheControl = "public, max-age=30";
                return Results.File(DashboardBadgeRenderer.Render(provider.GetLive()), "image/png");
            });
        }
    }
}
