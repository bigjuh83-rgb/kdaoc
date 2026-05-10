using System.Collections.Generic;
using DOL.GS.PacketHandler.Client.v168;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_DetailDisplayHandler
    {
        [Test]
        public void TryGetIndexedSkill_ShouldReturnFalseForObjectIdBeforeSkillBase()
        {
            List<(Skill, Skill)> skills =
            [
                (new Specialization("slash", "Slash", 1), null),
                (new Ability("quickcast", "Quickcast", "", 1, 1, 1, 100), null)
            ];

            bool found = DetailDisplayHandler.TryGetIndexedSkill<Ability>(skills, 99, out Ability ability);

            Assert.That(found, Is.False);
            Assert.That(ability, Is.Null);
        }

        [Test]
        public void TryGetIndexedSkill_ShouldReturnFalseForOutOfRangeIndex()
        {
            List<(Skill, Skill)> skills =
            [
                (new Specialization("slash", "Slash", 1), null),
                (new Ability("quickcast", "Quickcast", "", 1, 1, 1, 100), null)
            ];

            bool found = DetailDisplayHandler.TryGetIndexedSkill<Ability>(skills, 101, out Ability ability);

            Assert.That(found, Is.False);
            Assert.That(ability, Is.Null);
        }

        [Test]
        public void TryGetIndexedSkill_ShouldReturnFalseForWrongSkillType()
        {
            List<(Skill, Skill)> skills =
            [
                (new Specialization("slash", "Slash", 1), null)
            ];

            bool found = DetailDisplayHandler.TryGetIndexedSkill<Ability>(skills, 100, out Ability ability);

            Assert.That(found, Is.False);
            Assert.That(ability, Is.Null);
        }

        [Test]
        public void TryGetIndexedSkill_ShouldReturnMatchingSkillAfterSpecializations()
        {
            Ability expected = new("quickcast", "Quickcast", "", 1, 1, 1, 100);
            List<(Skill, Skill)> skills =
            [
                (new Specialization("slash", "Slash", 1), null),
                (expected, null)
            ];

            bool found = DetailDisplayHandler.TryGetIndexedSkill<Ability>(skills, 100, out Ability ability);

            Assert.That(found, Is.True);
            Assert.That(ability, Is.SameAs(expected));
        }
    }
}
