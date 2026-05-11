using System;
using System.Globalization;
using System.Linq;
using DOL.Database;
using SkiaSharp;

namespace DOL.GS.API.Dashboard
{
    public static class DashboardBadgeRenderer
    {
        private const int Width = 900;
        private const int Height = 240;

        public static byte[] Render(DashboardLiveResponse live)
        {
            using SKBitmap bitmap = new(Width, Height);
            using SKCanvas canvas = new(bitmap);
            canvas.Clear(new SKColor(16, 20, 24));

            using SKPaint borderPaint = new()
            {
                Color = new SKColor(63, 72, 86),
                IsStroke = true,
                StrokeWidth = 2,
                IsAntialias = true
            };
            canvas.DrawRoundRect(new SKRect(8, 8, Width - 8, Height - 8), 20, 20, borderPaint);

            using SKPaint titlePaint = CreateTextPaint(SKColors.White, 42, true);
            using SKPaint labelPaint = CreateTextPaint(new SKColor(154, 168, 181), 24, false);
            using SKPaint countPaint = CreateTextPaint(new SKColor(219, 176, 84), 64, true);
            using SKPaint realmPaint = CreateTextPaint(SKColors.White, 28, true);
            using SKPaint updatedPaint = CreateTextPaint(new SKColor(154, 168, 181), 20, false);

            canvas.DrawText("KDAOC LIVE", 38, 64, titlePaint);
            canvas.DrawText("Online players", 42, 120, labelPaint);
            canvas.DrawText(GetTotalPlayers(live).ToString(CultureInfo.InvariantCulture), 42, 196, countPaint);

            DrawRealm(canvas, realmPaint, live, eRealm.Albion, "Albion", 296, 134, new SKColor(214, 74, 74));
            DrawRealm(canvas, realmPaint, live, eRealm.Midgard, "Midgard", 500, 134, new SKColor(95, 142, 232));
            DrawRealm(canvas, realmPaint, live, eRealm.Hibernia, "Hibernia", 704, 134, new SKColor(80, 173, 111));

            canvas.DrawText(GetUpdatedText(live), 592, 210, updatedPaint);

            using SKImage image = SKImage.FromBitmap(bitmap);
            using SKData data = image.Encode(SKEncodedImageFormat.Png, 92);
            return data.ToArray();
        }

        private static SKPaint CreateTextPaint(SKColor color, float textSize, bool bold)
        {
            return new SKPaint
            {
                Color = color,
                TextSize = textSize,
                IsAntialias = true,
                Typeface = SKTypeface.FromFamilyName("Arial", bold ? SKFontStyle.Bold : SKFontStyle.Normal)
            };
        }

        private static int GetTotalPlayers(DashboardLiveResponse live)
        {
            return Math.Max(0, live?.TotalPlayers ?? 0);
        }

        private static string GetUpdatedText(DashboardLiveResponse live)
        {
            DateTime updatedAt = live?.UpdatedAt ?? DateTime.UtcNow;
            return "Updated " + updatedAt.ToLocalTime().ToString("HH:mm:ss", CultureInfo.InvariantCulture);
        }

        private static void DrawRealm(
            SKCanvas canvas,
            SKPaint textPaint,
            DashboardLiveResponse live,
            eRealm realm,
            string label,
            float x,
            float y,
            SKColor color)
        {
            using SKPaint dotPaint = new()
            {
                Color = color,
                IsAntialias = true
            };

            canvas.DrawCircle(x, y - 10, 10, dotPaint);
            canvas.DrawText(label + " " + GetRealmPlayers(live, realm, label).ToString(CultureInfo.InvariantCulture), x + 22, y, textPaint);
        }

        private static int GetRealmPlayers(DashboardLiveResponse live, eRealm realm, string realmName)
        {
            DashboardRealmStats stats = live?.Realms?.FirstOrDefault(item => item.RealmId == (int)realm)
                ?? live?.Realms?.FirstOrDefault(item => string.Equals(item.RealmName, realmName, StringComparison.OrdinalIgnoreCase));

            return Math.Max(0, stats?.Players ?? 0);
        }
    }
}
