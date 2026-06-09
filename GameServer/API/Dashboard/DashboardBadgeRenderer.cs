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

        public static byte[] Render(DashboardLiveResponse live, bool serverOnline = true)
        {
            bool online = serverOnline && live != null;
            int totalPlayers = GetTotalPlayers(live);

            using SKBitmap bitmap = new(Width, Height);
            using SKCanvas canvas = new(bitmap);
            canvas.Clear(new SKColor(7, 9, 13));

            using SKPaint backgroundPaint = new()
            {
                Shader = SKShader.CreateLinearGradient(
                    new SKPoint(0, 0),
                    new SKPoint(Width, Height),
                    new[]
                    {
                        new SKColor(17, 20, 25),
                        new SKColor(29, 31, 36),
                        new SKColor(8, 10, 14)
                    },
                    new[] { 0f, 0.62f, 1f },
                    SKShaderTileMode.Clamp),
                IsAntialias = true
            };
            SKRect outer = new(8, 8, Width - 8, Height - 8);
            canvas.DrawRoundRect(outer, 18, 18, backgroundPaint);

            using SKPaint leftPanelPaint = new()
            {
                Shader = SKShader.CreateLinearGradient(
                    new SKPoint(8, 8),
                    new SKPoint(312, Height - 8),
                    new[] { new SKColor(72, 35, 34, 118), new SKColor(24, 24, 29, 28) },
                    null,
                    SKShaderTileMode.Clamp),
                IsAntialias = true
            };
            canvas.DrawRoundRect(new SKRect(8, 8, 316, Height - 8), 18, 18, leftPanelPaint);

            using SKPaint patternPaint = new()
            {
                Color = new SKColor(255, 255, 255, 14),
                IsStroke = true,
                StrokeWidth = 1,
                IsAntialias = true
            };
            for (int x = -120; x < Width; x += 72)
                canvas.DrawLine(x, Height - 16, x + 210, 14, patternPaint);

            using SKPaint borderPaint = new()
            {
                Shader = SKShader.CreateLinearGradient(
                    new SKPoint(8, 8),
                    new SKPoint(Width - 8, Height - 8),
                    new[] { new SKColor(181, 54, 57), new SKColor(214, 173, 88), new SKColor(76, 151, 224), new SKColor(80, 180, 116) },
                    new[] { 0f, 0.34f, 0.68f, 1f },
                    SKShaderTileMode.Clamp),
                IsStroke = true,
                StrokeWidth = 2,
                IsAntialias = true
            };
            canvas.DrawRoundRect(outer, 18, 18, borderPaint);

            using SKPaint dividerPaint = new()
            {
                Color = new SKColor(255, 255, 255, 46),
                IsStroke = true,
                StrokeWidth = 1,
                IsAntialias = true
            };
            canvas.DrawLine(316, 28, 316, Height - 28, dividerPaint);

            using SKPaint titlePaint = CreateTextPaint(new SKColor(250, 247, 236), 40, true);
            using SKPaint labelPaint = CreateTextPaint(new SKColor(192, 201, 214), 18, true);
            using SKPaint countPaint = CreateTextPaint(new SKColor(255, 220, 132), 82, true);
            using SKPaint countGlowPaint = CreateTextPaint(new SKColor(235, 160, 59, 82), 82, true);
            countGlowPaint.MaskFilter = SKMaskFilter.CreateBlur(SKBlurStyle.Normal, 8);
            using SKPaint updatedPaint = CreateTextPaint(new SKColor(133, 146, 164), 15, false);
            using SKPaint statusPaint = CreateTextPaint(online ? new SKColor(115, 239, 163) : new SKColor(255, 128, 128), 14, true);

            DrawSmallPill(canvas, online ? "LIVE" : "OFFLINE", 38, 31, online ? new SKColor(48, 221, 134) : new SKColor(236, 85, 85), statusPaint);
            canvas.DrawText("K-DAOC", 38, 94, titlePaint);

            canvas.DrawText("ONLINE PLAYERS", 40, 150, labelPaint);
            string totalText = totalPlayers.ToString(CultureInfo.InvariantCulture);
            canvas.DrawText(totalText, 107, 220, countGlowPaint);
            canvas.DrawText(totalText, 107, 220, countPaint);

            DrawRealmRow(canvas, live, eRealm.Albion, "Albion", 352, 44, 516, new SKColor(221, 70, 76));
            DrawRealmRow(canvas, live, eRealm.Midgard, "Midgard", 352, 100, 516, new SKColor(86, 145, 239));
            DrawRealmRow(canvas, live, eRealm.Hibernia, "Hibernia", 352, 156, 516, new SKColor(83, 203, 123));
            DrawRightAlignedText(canvas, online ? GetUpdatedText(live) : "Updated --:--:--", 868, 224, updatedPaint);

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
                Typeface = SKTypeface.FromFamilyName("Malgun Gothic", bold ? SKFontStyle.Bold : SKFontStyle.Normal)
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

        private static void DrawSmallPill(SKCanvas canvas, string text, float x, float y, SKColor color, SKPaint textPaint)
        {
            using SKPaint fillPaint = new()
            {
                Color = new SKColor(color.Red, color.Green, color.Blue, 34),
                IsAntialias = true
            };
            using SKPaint strokePaint = new()
            {
                Color = new SKColor(color.Red, color.Green, color.Blue, 135),
                IsStroke = true,
                StrokeWidth = 1.3f,
                IsAntialias = true
            };
            SKRect rect = new(x, y, x + 64, y + 24);
            canvas.DrawRoundRect(rect, 12, 12, fillPaint);
            canvas.DrawRoundRect(rect, 12, 12, strokePaint);
            canvas.DrawText(text, x + 13, y + 17, textPaint);
        }

        private static void DrawRealmRow(
            SKCanvas canvas,
            DashboardLiveResponse live,
            eRealm realm,
            string label,
            float x,
            float y,
            float width,
            SKColor color)
        {
            int players = GetRealmPlayers(live, realm, label);
            SKRect rect = new(x, y, x + width, y + 42);
            using SKPaint rowPaint = new()
            {
                Color = new SKColor(255, 255, 255, 16),
                IsAntialias = true
            };
            using SKPaint strokePaint = new()
            {
                Color = new SKColor(color.Red, color.Green, color.Blue, 105),
                IsStroke = true,
                StrokeWidth = 1.2f,
                IsAntialias = true
            };
            using SKPaint accentPaint = new()
            {
                Color = color,
                IsAntialias = true
            };
            using SKPaint labelPaint = CreateTextPaint(new SKColor(230, 235, 244), 25, true);
            using SKPaint numberPaint = CreateTextPaint(SKColors.White, 34, true);

            canvas.DrawRoundRect(rect, 12, 12, rowPaint);
            canvas.DrawRoundRect(rect, 12, 12, strokePaint);
            canvas.DrawRoundRect(new SKRect(x, y, x + 7, y + 42), 4, 4, accentPaint);
            canvas.DrawCircle(x + 30, y + 21, 8, accentPaint);
            canvas.DrawText(label, x + 48, y + 29, labelPaint);

            string playerText = players.ToString(CultureInfo.InvariantCulture);
            DrawRightAlignedText(canvas, playerText, x + width - 24, y + 31, numberPaint);
        }

        private static void DrawRightAlignedText(SKCanvas canvas, string text, float right, float y, SKPaint paint)
        {
            canvas.DrawText(text, right - paint.MeasureText(text), y, paint);
        }

        private static int GetRealmPlayers(DashboardLiveResponse live, eRealm realm, string realmName)
        {
            DashboardRealmStats stats = live?.Realms?.FirstOrDefault(item => item.RealmId == (int)realm)
                ?? live?.Realms?.FirstOrDefault(item => string.Equals(item.RealmName, realmName, StringComparison.OrdinalIgnoreCase));

            return Math.Max(0, stats?.Players ?? 0);
        }
    }
}
