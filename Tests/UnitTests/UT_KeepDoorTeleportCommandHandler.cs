using System.Reflection;
using DOL.GS.Commands;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_KeepDoorTeleportCommandHandler
    {
        [TestCase("enter")]
        [TestCase("exit")]
        public void IsValidTeleportText_WithSupportedText_ShouldReturnTrue(string text)
        {
            Assert.That(InvokeValidation("IsValidTeleportText", text), Is.True);
        }

        [TestCase("gate")]
        [TestCase("")]
        public void IsValidTeleportText_WithUnsupportedText_ShouldReturnFalse(string text)
        {
            Assert.That(InvokeValidation("IsValidTeleportText", text), Is.False);
        }

        [TestCase("in")]
        [TestCase("out")]
        public void IsValidTeleportDirection_WithSupportedDirection_ShouldReturnTrue(string direction)
        {
            Assert.That(InvokeValidation("IsValidTeleportDirection", direction), Is.True);
        }

        [TestCase("inside")]
        [TestCase("")]
        public void IsValidTeleportDirection_WithUnsupportedDirection_ShouldReturnFalse(string direction)
        {
            Assert.That(InvokeValidation("IsValidTeleportDirection", direction), Is.False);
        }

        private static bool InvokeValidation(string methodName, string value)
        {
            MethodInfo method = typeof(KeepDoorTeleportCommandHandler).GetMethod(methodName, BindingFlags.Static | BindingFlags.NonPublic);
            Assert.That(method, Is.Not.Null);

            return (bool)method.Invoke(null, new object[] { value });
        }
    }
}
