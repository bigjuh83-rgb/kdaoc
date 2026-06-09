using DOL.GS;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_SkillBase
    {
        [Test]
        public void CreateIntrinsicAbility_ProvidesAbilityForInternalKey()
        {
            Ability ability = IntrinsicAbilityFactory.Create(Abilities.ConfusionImmunity);

            Assert.Multiple(() =>
            {
                Assert.That(ability, Is.Not.Null);
                Assert.That(ability.KeyName, Is.EqualTo(Abilities.ConfusionImmunity));
                Assert.That(ability.Name, Is.EqualTo(Abilities.ConfusionImmunity));
                Assert.That(ability.Level, Is.EqualTo(0));
            });
        }
    }
}
