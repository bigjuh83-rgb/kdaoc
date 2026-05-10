using DOL.GS.Spells;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_AblativeArmorSpellHandler
    {
        [Test]
        public void MeleeAblative_WithMeleeHit_ShouldMatch()
        {
            AttackData attackData = CreateAttackData(AttackData.eAttackType.MeleeOneHand, eAttackResult.HitUnstyled);

            Assert.That(Matches(new AblativeArmorSpellHandler(null, null, null), attackData), Is.True);
        }

        [Test]
        public void MeleeAblative_WithSpellDamage_ShouldNotMatch()
        {
            AttackData attackData = CreateAttackData(AttackData.eAttackType.Spell, eAttackResult.Any);

            Assert.That(Matches(new AblativeArmorSpellHandler(null, null, null), attackData), Is.False);
        }

        [Test]
        public void MagicAblative_WithMeleeHit_ShouldNotMatch()
        {
            AttackData attackData = CreateAttackData(AttackData.eAttackType.MeleeOneHand, eAttackResult.HitStyle);

            Assert.That(Matches(new MagicAblativeArmorSpellHandler(null, null, null), attackData), Is.False);
        }

        [Test]
        public void MagicAblative_WithSpellDamage_ShouldMatch()
        {
            AttackData attackData = CreateAttackData(AttackData.eAttackType.Spell, eAttackResult.Any);

            Assert.That(Matches(new MagicAblativeArmorSpellHandler(null, null, null), attackData), Is.True);
        }

        [Test]
        public void BothAblative_WithMeleeHitAndSpellDamage_ShouldMatchBoth()
        {
            AttackData meleeAttackData = CreateAttackData(AttackData.eAttackType.MeleeOneHand, eAttackResult.HitUnstyled);
            AttackData spellAttackData = CreateAttackData(AttackData.eAttackType.Spell, eAttackResult.Any);
            BothAblativeArmorSpellHandler handler = new(null, null, null);

            Assert.That(Matches(handler, meleeAttackData), Is.True);
            Assert.That(Matches(handler, spellAttackData), Is.True);
        }

        private static AttackData CreateAttackData(AttackData.eAttackType attackType, eAttackResult attackResult)
        {
            return new AttackData
            {
                AttackType = attackType,
                AttackResult = attackResult,
                Damage = 100
            };
        }

        private static bool Matches(AblativeArmorSpellHandler handler, AttackData attackData)
        {
            return handler.MatchingDamageType(ref attackData);
        }
    }
}
