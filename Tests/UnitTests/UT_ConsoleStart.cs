using System.Reflection;
using DOL.DOLServer.Actions;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_ConsoleStart
    {
        [Test]
        public void ShouldThrottleMissingConsoleInput_WithNullLine_ShouldReturnTrue()
        {
            MethodInfo method = typeof(ConsoleStart).GetMethod(
                "ShouldThrottleMissingConsoleInput",
                BindingFlags.Static | BindingFlags.NonPublic);

            Assert.That(method, Is.Not.Null);
            Assert.That(method.Invoke(null, new object[] { null }), Is.True);
        }

        [Test]
        public void ShouldThrottleMissingConsoleInput_WithEmptyLine_ShouldReturnFalse()
        {
            MethodInfo method = typeof(ConsoleStart).GetMethod(
                "ShouldThrottleMissingConsoleInput",
                BindingFlags.Static | BindingFlags.NonPublic);

            Assert.That(method, Is.Not.Null);
            Assert.That(method.Invoke(null, new object[] { string.Empty }), Is.False);
        }
    }
}
