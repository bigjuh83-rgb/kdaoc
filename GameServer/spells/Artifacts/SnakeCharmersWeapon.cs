using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Spells
{
    /// <summary>
    /// Heal Over Time spell handler
    /// </summary>
    [SpellHandler(eSpellType.SnakeCharmer)]
    public class SnakeCharmer : LifedrainSpellHandler
    {
		public override double CalculateSpellResistChance(GameLiving target)
		{
			return 0;
		}

        /// <summary>
        /// Uses percent of damage to heal the caster
        /// </summary>
        public override void StealLife(AttackData ad)
        {
            if (ad == null) return;
            if (!m_caster.IsAlive) return;

            int heal = (ad.Damage + ad.CriticalDamage) * 50 / 100;
            int mana = (ad.Damage + ad.CriticalDamage) * 30 / 100;
            int endu = (ad.Damage + ad.CriticalDamage) * 20 / 100;

            if (m_caster.IsDiseased)
            {
                MessageToCaster(LanguageMgr.GetTranslation((Caster as GamePlayer)?.Client.Account.Language, "DrainSpell.YouAreDiseased"), eChatType.CT_SpellResisted);
                heal >>= 1;
            }
            if (heal <= 0) return;
            heal = m_caster.ChangeHealth(m_caster, eHealthChangeType.Spell, heal);
            if (heal > 0)
            {
                MessageToCaster(LanguageMgr.GetTranslation((Caster as GamePlayer)?.Client.Account.Language, "DrainSpell.StealLife", heal), eChatType.CT_Spell);
            }
            else
            {
                MessageToCaster(LanguageMgr.GetTranslation((Caster as GamePlayer)?.Client.Account.Language, "DrainSpell.CannotAbsorbLife"), eChatType.CT_SpellResisted);
            }

            if (mana <=0) return;
            mana = m_caster.ChangeMana(m_caster,eManaChangeType.Spell,mana);
            if (mana > 0)
            {
                MessageToCaster(LanguageMgr.GetTranslation((Caster as GamePlayer)?.Client.Account.Language, "DrainSpell.StealPower", mana), eChatType.CT_Spell);
            }
            else
            {
                MessageToCaster(LanguageMgr.GetTranslation((Caster as GamePlayer)?.Client.Account.Language, "DrainSpell.CannotAbsorbPower"), eChatType.CT_SpellResisted);
            }

            if (endu <=0) return;
            endu = m_caster.ChangeEndurance(m_caster,eEnduranceChangeType.Spell,endu);
            if (endu > 0)
            {
                MessageToCaster(LanguageMgr.GetTranslation((Caster as GamePlayer)?.Client.Account.Language, "DrainSpell.StealEndurance", endu), eChatType.CT_Spell);
            }
            else
            {
                MessageToCaster(LanguageMgr.GetTranslation((Caster as GamePlayer)?.Client.Account.Language, "DrainSpell.CannotAbsorbEndurance"), eChatType.CT_SpellResisted);
            }
        }

        public SnakeCharmer(GameLiving caster, Spell spell, SpellLine line) : base(caster, spell, line) { }
    }
}
