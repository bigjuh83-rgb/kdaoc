using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Spells
{
    [SpellHandler(eSpellType.Tartaros)]
    public class Tartaros : LifedrainSpellHandler
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
            if (!Caster.IsAlive) return;

            int heal = (ad.Damage + ad.CriticalDamage) * 35 / 100;
            int mana = (ad.Damage + ad.CriticalDamage) * 21 / 100;
            int endu = (ad.Damage + ad.CriticalDamage) * 14 / 100;

            if (Caster.IsDiseased)
            {
                MessageToCaster(LanguageMgr.GetTranslation((Caster as GamePlayer)?.Client.Account.Language, "DrainSpell.YouAreDiseased"), eChatType.CT_SpellResisted);
                heal >>= 1;
            }
            if (heal <= 0) return;
            heal = Caster.ChangeHealth(Caster, eHealthChangeType.Spell, heal);
            if (heal > 0)
            {
                MessageToCaster(LanguageMgr.GetTranslation((Caster as GamePlayer)?.Client.Account.Language, "DrainSpell.DrainLife", heal), eChatType.CT_Spell);
            }
            else
            {
                MessageToCaster(LanguageMgr.GetTranslation((Caster as GamePlayer)?.Client.Account.Language, "DrainSpell.CannotAbsorbLife"), eChatType.CT_SpellResisted);
            }

            if (mana <=0) return;
            mana = Caster.ChangeMana(Caster,eManaChangeType.Spell,mana);
            if (mana > 0)
            {
                MessageToCaster(LanguageMgr.GetTranslation((Caster as GamePlayer)?.Client.Account.Language, "DrainSpell.DrainPower", mana), eChatType.CT_Spell);
            }
            else
            {
                MessageToCaster(LanguageMgr.GetTranslation((Caster as GamePlayer)?.Client.Account.Language, "DrainSpell.CannotAbsorbPower"), eChatType.CT_SpellResisted);
            }

            if (endu <=0) return;
            endu = Caster.ChangeEndurance(Caster,eEnduranceChangeType.Spell,endu);
            if (endu > 0)
            {
                MessageToCaster(LanguageMgr.GetTranslation((Caster as GamePlayer)?.Client.Account.Language, "DrainSpell.DrainEndurance", endu), eChatType.CT_Spell);
            }
            else
            {
                MessageToCaster(LanguageMgr.GetTranslation((Caster as GamePlayer)?.Client.Account.Language, "DrainSpell.CannotAbsorbEndurance"), eChatType.CT_SpellResisted);
            }
        }

        public Tartaros(GameLiving caster, Spell spell, SpellLine line) : base(caster, spell, line) { }
    }
}
