using System;
using System.Collections.Concurrent;
using System.Globalization;
using System.IO;
using System.Text;

namespace DOL.GS
{
    public static class MovementAudit
    {
        private sealed class AuditState
        {
            public bool Full { get; set; }
        }

        private static readonly ConcurrentDictionary<string, AuditState> _enabled = new(StringComparer.OrdinalIgnoreCase);

        public static bool Enable(GamePlayer player, bool full)
        {
            if (player == null || string.IsNullOrWhiteSpace(player.Name))
                return false;

            _enabled[player.Name] = new AuditState { Full = full };
            return true;
        }

        public static bool Disable(GamePlayer player)
        {
            if (player == null || string.IsNullOrWhiteSpace(player.Name))
                return false;

            return _enabled.TryRemove(player.Name, out _);
        }

        public static bool IsEnabled(GamePlayer player)
        {
            return player != null && _enabled.ContainsKey(player.Name);
        }

        public static void RecordPositionUpdate(GamePlayer player, int x, int y, int z, ushort heading, float speed, float zSpeed, ushort zoneId, string packetVersion)
        {
            if (player == null || !_enabled.TryGetValue(player.Name, out AuditState state))
                return;

            int previousX = player.X;
            int previousY = player.Y;
            int previousZ = player.Z;
            double horizontalDelta = Math.Sqrt(Math.Pow(x - previousX, 2) + Math.Pow(y - previousY, 2));
            int deltaZ = z - previousZ;
            string path = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "logs", $"movement-audit-{SafeFileName(player.Name)}.jsonl");

            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                File.AppendAllText(path, BuildJsonLine(player, x, y, z, previousX, previousY, previousZ, heading, speed, zSpeed, zoneId, packetVersion, horizontalDelta, deltaZ, state.Full), Encoding.UTF8);
            }
            catch
            {
                // Audit must never affect movement processing.
            }
        }

        private static string BuildJsonLine(GamePlayer player, int x, int y, int z, int previousX, int previousY, int previousZ, ushort heading, float speed, float zSpeed, ushort zoneId, string packetVersion, double horizontalDelta, int deltaZ, bool full)
        {
            return "{"
                + "\"event\":\"c2s_position\","
                + $"\"time\":\"{DateTime.UtcNow:O}\","
                + $"\"player\":\"{Escape(player.Name)}\","
                + $"\"account\":\"{Escape(player.Client?.Account?.Name)}\","
                + $"\"region\":{player.CurrentRegionID},"
                + $"\"zoneId\":{zoneId},"
                + $"\"x\":{x},\"y\":{y},\"z\":{z},"
                + $"\"previousX\":{previousX},\"previousY\":{previousY},\"previousZ\":{previousZ},"
                + $"\"horizontalDelta\":{horizontalDelta.ToString("0.###", CultureInfo.InvariantCulture)},"
                + $"\"deltaZ\":{deltaZ},"
                + $"\"heading\":{heading},"
                + $"\"speed\":{speed.ToString("0.###", CultureInfo.InvariantCulture)},"
                + $"\"zSpeed\":{zSpeed.ToString("0.###", CultureInfo.InvariantCulture)},"
                + $"\"packetVersion\":\"{Escape(packetVersion)}\","
                + $"\"full\":{(full ? "true" : "false")}"
                + "}\n";
        }

        private static string Escape(string value)
        {
            if (string.IsNullOrEmpty(value))
                return string.Empty;

            return value.Replace("\\", "\\\\").Replace("\"", "\\\"");
        }

        private static string SafeFileName(string value)
        {
            StringBuilder builder = new(value.Length);
            foreach (char c in value)
                builder.Append(Array.IndexOf(Path.GetInvalidFileNameChars(), c) >= 0 ? '_' : c);
            return builder.ToString();
        }
    }
}
