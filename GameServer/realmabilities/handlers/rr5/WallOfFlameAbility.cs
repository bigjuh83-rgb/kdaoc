using System;
using System.Collections;
using System.Reflection;
using DOL.GS;
using DOL.GS.PacketHandler;
using DOL.GS.Effects;
using DOL.Events;
using DOL.Database;
using DOL.Language;

namespace DOL.GS.RealmAbilities
{
	public class WallOfFlameAbility : RR5RealmAbility
	{
		public WallOfFlameAbility(DbAbility dba, int level) : base(dba, level) { }

		private int dmgValue = 400; // 400 Dmg
		private int duration = 15; // 15 Sec duration

		public override void Execute(GameLiving living)
		{
			if (CheckPreconditions(living, DEAD | SITTING | MEZZED | STUNNED)) return;

			base.Execute(living);

			GamePlayer caster = living as GamePlayer;
			if (caster == null)
				return;

			if (caster.IsMoving)
			{
				caster.Out.SendMessage(LanguageMgr.GetTranslation(caster.Client.Account.Language, "RealmAbility.Message.MustStandStill"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
				return;
			}

			foreach (GamePlayer i_player in caster.GetPlayersInRadius(WorldMgr.INFO_DISTANCE))
			{
				if (i_player == caster)
				{
					i_player.MessageToSelf(LanguageMgr.GetTranslation(i_player.Client.Account.Language, "RealmAbility.Generic.CastSelf", Name), eChatType.CT_Spell);
				}
				else
				{
					i_player.MessageFromArea(caster, LanguageMgr.GetTranslation(i_player.Client.Account.Language, "RealmAbility.Message.CasterCastsSpell", caster.Name), eChatType.CT_Spell, eChatLoc.CL_SystemWindow);
				}

				i_player.Out.SendSpellCastAnimation(caster, 7028, 20);
			}

			Statics.WallOfFlameBase wof = new Statics.WallOfFlameBase(dmgValue);
			Point3D targetSpot = new Point3D(caster.X, caster.Y, caster.Z);
			wof.CreateStatic(caster, targetSpot, duration, 3, 150);

			DisableSkill(living);
			caster.StopCurrentSpellcast();

		}


		public override int GetReUseDelay(int level)
		{
			return 600;
		}
	}
}