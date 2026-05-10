using System.Collections;
using System.Collections.Generic;
using DOL.GS.PacketHandler;
using DOL.GS.RealmAbilities;
using DOL.Language;

namespace DOL.GS.Spells
{
	[SpellHandler(eSpellType.RealmLore)]
	public class RealmLore : SpellHandler
	{
		public override bool CheckBeginCast(GameLiving selectedTarget)
        {
			if(!base.CheckBeginCast(selectedTarget))
				return false;

			if(selectedTarget==null)
				return false;

			if (selectedTarget is GameNPC)
			{
				MessageToCaster(LanguageMgr.GetTranslation((Caster as GamePlayer)?.Client, "Artifacts.RealmLore.PlayersOnly"), eChatType.CT_SpellResisted); return false;
			}

			if(selectedTarget as GamePlayer==null)
				return false;

			if(!m_caster.IsWithinRadius(selectedTarget, Spell.Range))
			{
				MessageToCaster(LanguageMgr.GetTranslation((Caster as GamePlayer)?.Client, "Artifacts.RealmLore.TargetTooFar"), eChatType.CT_SpellResisted); return false;
			}

            return true;
        }
		public override void OnDirectEffect(GameLiving target)
		{
			GamePlayer player = target as GamePlayer;
			if(player == null)
				return;

			var text = new List<string>();
			string language = (m_caster as GamePlayer)?.Client.Account.Language;
			text.Add(LanguageMgr.GetTranslation(language, "Artifacts.RealmLore.Class", player.CharacterClass.Name));
			text.Add(LanguageMgr.GetTranslation(language, "Artifacts.RealmLore.RealmPoints", player.RealmPoints, string.Format("{0:#L#} {1}",player.RealmLevel+10,player.RealmRankTitle(player.Client.Account.Language))));
			text.Add("----------------------------------------------------");
			text.Add(LanguageMgr.GetTranslation(language, "Artifacts.RealmLore.StatsLine1", player.Strength, player.Dexterity, player.Constitution));
			text.Add(LanguageMgr.GetTranslation(language, "Artifacts.RealmLore.StatsLine2", player.Quickness, player.Empathy, player.Charisma));
			text.Add(LanguageMgr.GetTranslation(language, "Artifacts.RealmLore.StatsLine3", player.Piety, player.Intelligence, player.MaxHealth));
			text.Add("----------------------------------------------------");
			IList<Specialization> specs = player.GetSpecList();
			foreach (object obj in specs)
				if (obj is Specialization)
					text.Add(((Specialization)obj).Name + ": " + ((Specialization)obj).Level.ToString());
			text.Add("----------------------------------------------------");
			IList abilities = player.GetAllAbilities();
			foreach(Ability ab in abilities)
				if(ab is RealmAbility && ab is RR5RealmAbility == false)
					text.Add(((RealmAbility)ab).Name);

			string title = LanguageMgr.GetTranslation(language, "Artifacts.RealmLore.Title", player.Name);
			(m_caster as GamePlayer).Out.SendCustomTextWindow(title,text);
			(m_caster as GamePlayer).Out.SendMessage(title + "\n" + string.Join("\n", text),eChatType.CT_System,eChatLoc.CL_SystemWindow);
		}
		public RealmLore(GameLiving caster, Spell spell, SpellLine line) : base(caster, spell, line) {}
    }
}
