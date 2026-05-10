using System.Reflection;
using DOL.Database;
using DOL.GS.PacketHandler;
using DOL.GS.Spells;
using DOL.Language;

namespace DOL.GS
{
	public class GameMythirian : GameInventoryItem
	{
		private static readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);

		private GameMythirian() { }

		public GameMythirian(DbItemTemplate template)
			: base(template)
		{
		}

		public GameMythirian(DbItemUnique template)
			: base(template)
		{
		}

		public override bool CanEquip(GamePlayer player)
		{
			if (base.CanEquip(player))
			{
				if (Type_Damage <= player.ChampionLevel)
				{
					return true;
				}
				player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "Inventory.Mythirian.NeedChampionLevel"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
			}
			return false;
		}

		#region Overrides

		public override void OnEquipped(GamePlayer player)
		{
			if (this.Name.ToLower().Contains("ektaktos"))
			{
				player.CanBreathUnderWater = true;
				player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "Inventory.Mythirian.WaterBreathing"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
			}
			base.OnEquipped(player);
		}

		public override void OnUnEquipped(GamePlayer player)
		{
			/*if (this.Name.ToLower().Contains("ektaktos") && SpellHelper.FindEffectOnTarget(player, typeof(WaterBreathingSpellHandler)) == null)
			{
				player.CanBreathUnderWater = false;
				player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "Inventory.Mythirian.WaterBreathingExpired"), eChatType.CT_SpellExpires, eChatLoc.CL_SystemWindow);
			}*/
			base.OnUnEquipped(player);
		}
		#endregion

	}
}
