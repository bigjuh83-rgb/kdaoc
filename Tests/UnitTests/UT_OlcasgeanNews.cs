using System;
using System.Reflection;
using DOL.GS;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_OlcasgeanNews
    {
        [Test]
        public void ShouldReportNews_WithNullKiller_ShouldReturnFalse()
        {
            Assert.That(ShouldReportNews(null), Is.False);
        }

        [Test]
        public void ShouldReportNews_WithOlcasgeanKillers_ShouldReturnFalse()
        {
            Assert.That(ShouldReportNewsType(typeof(Olcasgean)), Is.False);
            Assert.That(ShouldReportNewsType(typeof(Olcasgean2)), Is.False);
        }

        [Test]
        public void ShouldReportNews_WithRegularNpcKiller_ShouldReturnTrue()
        {
            Assert.That(ShouldReportNewsType(typeof(GameNPC)), Is.True);
        }

        private static bool ShouldReportNews(GameObject killer)
        {
            Type type = typeof(Olcasgean).Assembly.GetType("DOL.GS.OlcasgeanNews");
            Assert.That(type, Is.Not.Null);

            MethodInfo method = type.GetMethod("ShouldReportNews", BindingFlags.Static | BindingFlags.NonPublic);
            Assert.That(method, Is.Not.Null);

            return (bool)method.Invoke(null, new object[] { killer });
        }

        private static bool ShouldReportNewsType(Type killerType)
        {
            Type type = typeof(Olcasgean).Assembly.GetType("DOL.GS.OlcasgeanNews");
            Assert.That(type, Is.Not.Null);

            MethodInfo method = type.GetMethod("ShouldReportNewsType", BindingFlags.Static | BindingFlags.NonPublic);
            Assert.That(method, Is.Not.Null);

            return (bool)method.Invoke(null, new object[] { killerType });
        }
    }
}
