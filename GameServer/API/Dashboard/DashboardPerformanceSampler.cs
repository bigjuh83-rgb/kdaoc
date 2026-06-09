using System;
using System.Linq;
using System.Net.NetworkInformation;
using DOL.GS.PerformanceStatistics;

namespace DOL.GS.API.Dashboard
{
    internal sealed class DashboardPerformanceSampler
    {
        private readonly IPerformanceStatistic m_cpu;
        private readonly object m_networkLock = new();
        private NetworkSample m_lastNetworkSample;

        public DashboardPerformanceSampler()
            : this(() => new CurrentProcessCpuUsagePercentStatistic())
        {
        }

        internal DashboardPerformanceSampler(Func<IPerformanceStatistic> createCpuStatistic)
        {
            m_cpu = TryCreateStatistic(createCpuStatistic);
        }

        public DashboardPerformanceStats GetSnapshot()
        {
            double cpu = GetCpuPercent();
            (double receivedKbps, double sentKbps) = GetNetworkThroughputKbps();

            return new DashboardPerformanceStats(
                (float)cpu,
                GC.GetTotalMemory(false) / 1024,
                receivedKbps,
                sentKbps);
        }

        private double GetCpuPercent()
        {
            try
            {
                double cpu = m_cpu?.GetNextValue() ?? 0;

                if (double.IsNaN(cpu) || double.IsInfinity(cpu) || cpu < 0)
                    return 0;

                return cpu;
            }
            catch
            {
                return 0;
            }
        }

        private static IPerformanceStatistic TryCreateStatistic(Func<IPerformanceStatistic> createStatistic)
        {
            try
            {
                return createStatistic?.Invoke() ?? DummyPerformanceStatistic.Instance;
            }
            catch
            {
                return DummyPerformanceStatistic.Instance;
            }
        }

        private (double ReceivedKbps, double SentKbps) GetNetworkThroughputKbps()
        {
            try
            {
                NetworkSample current = ReadNetworkSample();

                lock (m_networkLock)
                {
                    if (m_lastNetworkSample == null)
                    {
                        m_lastNetworkSample = current;
                        return (0, 0);
                    }

                    double seconds = Math.Max(0.001, (current.SampledAt - m_lastNetworkSample.SampledAt).TotalSeconds);
                    long receivedBytes = Math.Max(0, current.ReceivedBytes - m_lastNetworkSample.ReceivedBytes);
                    long sentBytes = Math.Max(0, current.SentBytes - m_lastNetworkSample.SentBytes);

                    m_lastNetworkSample = current;
                    return (receivedBytes / 1024d / seconds, sentBytes / 1024d / seconds);
                }
            }
            catch
            {
                return (0, 0);
            }
        }

        private static NetworkSample ReadNetworkSample()
        {
            long receivedBytes = 0;
            long sentBytes = 0;

            foreach (NetworkInterface networkInterface in NetworkInterface.GetAllNetworkInterfaces()
                .Where(IsUsableNetworkInterface))
            {
                IPv4InterfaceStatistics statistics = networkInterface.GetIPv4Statistics();
                receivedBytes += Math.Max(0, statistics.BytesReceived);
                sentBytes += Math.Max(0, statistics.BytesSent);
            }

            return new NetworkSample(DateTime.UtcNow, receivedBytes, sentBytes);
        }

        private static bool IsUsableNetworkInterface(NetworkInterface networkInterface)
        {
            return networkInterface != null
                && networkInterface.OperationalStatus == OperationalStatus.Up
                && networkInterface.NetworkInterfaceType != NetworkInterfaceType.Loopback
                && networkInterface.NetworkInterfaceType != NetworkInterfaceType.Tunnel;
        }

        private sealed class NetworkSample
        {
            public NetworkSample(DateTime sampledAt, long receivedBytes, long sentBytes)
            {
                SampledAt = sampledAt;
                ReceivedBytes = receivedBytes;
                SentBytes = sentBytes;
            }

            public DateTime SampledAt { get; }
            public long ReceivedBytes { get; }
            public long SentBytes { get; }
        }
    }
}
