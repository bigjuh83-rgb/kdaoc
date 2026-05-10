using System.Reflection;
using DOL.GS.Commands;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_PlvlCommand
    {
        [TestCase("1")]
        [TestCase("2")]
        public void RequiresSelfPlvlPermission_WithSelfDemotionToPlayerOrGm_ShouldReturnTrue(string privilegeLevel)
        {
            Assert.That(RequiresSelfPlvlPermission(privilegeLevel, true), Is.True);
        }

        [TestCase("1")]
        [TestCase("2")]
        public void RequiresSelfPlvlPermission_WithOtherTarget_ShouldReturnFalse(string privilegeLevel)
        {
            Assert.That(RequiresSelfPlvlPermission(privilegeLevel, false), Is.False);
        }

        [TestCase("3")]
        [TestCase("0")]
        [TestCase("")]
        public void RequiresSelfPlvlPermission_WithUnsupportedPrivilegeLevel_ShouldReturnFalse(string privilegeLevel)
        {
            Assert.That(RequiresSelfPlvlPermission(privilegeLevel, true), Is.False);
        }

        private static bool RequiresSelfPlvlPermission(string privilegeLevel, bool targetIsCommandIssuer)
        {
            MethodInfo method = typeof(PlvlCommand).GetMethod("RequiresSelfPlvlPermission", BindingFlags.Static | BindingFlags.NonPublic);
            Assert.That(method, Is.Not.Null);

            return (bool)method.Invoke(null, new object[] { privilegeLevel, targetIsCommandIssuer });
        }
    }
}
