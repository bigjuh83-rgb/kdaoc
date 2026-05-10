using System;
using System.Collections;
using System.Collections.Generic;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Effects
{
	/// <summary>
	/// Trueshot grants 50% more range for next archery attack
	/// </summary>
	public class TrueshotEffect : StaticEffect, IGameEffect
	{
		public TrueshotEffect()
			: base()
		{
		}

		public override void Start(GameLiving target)
		{
			base.Start(target);
			GamePlayer player = target as GamePlayer;
			if (player != null)
			{
				player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "RealmAbility.TrueshotEffect.Prepare"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
			}
		}

		public override string Name { get { return "Trueshot"; } }

		public override ushort Icon { get { return 3004; } }

		public override IList<string> DelveInfo
		{
			get
			{
				var list = new List<string>();
				list.Add("Grants 50% bonus to the next arrow fired. The arrow will penetrate and pop bladeturn.");
				return list;
			}
		}

	}
}