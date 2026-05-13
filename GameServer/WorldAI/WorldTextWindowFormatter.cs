using System;
using System.Collections.Generic;

namespace DOL.GS.WorldAI
{
    public static class WorldTextWindowFormatter
    {
        private const int DefaultMaxLineLength = 22;

        public static void AddWrapped(List<string> lines, string text, int maxLineLength = DefaultMaxLineLength)
        {
            if (lines == null)
                throw new ArgumentNullException(nameof(lines));

            if (string.IsNullOrWhiteSpace(text))
                return;

            int limit = maxLineLength <= 0 ? DefaultMaxLineLength : maxLineLength;

            foreach (string paragraph in text.Replace("\r", string.Empty).Split('\n'))
                AddParagraph(lines, paragraph.Trim(), limit);
        }

        private static void AddParagraph(List<string> lines, string paragraph, int limit)
        {
            if (string.IsNullOrWhiteSpace(paragraph))
            {
                lines.Add(string.Empty);
                return;
            }

            string remaining = paragraph;

            while (remaining.Length > limit)
            {
                int split = FindSplitIndex(remaining, limit);
                lines.Add(remaining.Substring(0, split).TrimEnd());
                remaining = remaining.Substring(split).TrimStart();
            }

            if (remaining.Length > 0)
                lines.Add(remaining);
        }

        private static int FindSplitIndex(string text, int limit)
        {
            int searchStart = Math.Min(limit, text.Length - 1);

            for (int i = searchStart; i >= Math.Max(1, limit - 8); i--)
            {
                if (char.IsWhiteSpace(text[i]))
                    return i;
            }

            return limit;
        }
    }
}
