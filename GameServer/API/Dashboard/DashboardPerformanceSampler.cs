using System;
using DOL.GS.PerformanceStatistics;

namespace DOL.GS.API.Dashboard
{
    internal sealed class DashboardPerformanceSampler
    {
        private readonly IPerformanceStatistic m_cpu;

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

            return new DashboardPerformanceStats(
                (float)cpu,
                GC.GetTotalMemory(false) / 1024);
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
    }
}
