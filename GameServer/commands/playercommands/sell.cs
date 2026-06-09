using System.Linq;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&sell",
		ePrivLevel.Player,
		"대상 상인에게 아이템을 판매합니다. 가방 하나, 범위 또는 all을 지정할 수 있습니다.",
		"사용법: /sell 4 - 4번 가방의 모든 아이템을 판매합니다.",
		"/sell 2-3 - 2번과 3번 가방의 모든 아이템을 판매합니다.",
		"/sell all - 모든 아이템을 판매합니다.")]
	public class SellCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
			int firstItem = 0, lastItem = 0, firstBag = 0, lastBag = 0;

			if (args.Length >= 2)
			{
				if (args[1].Contains("all"))
				{
					firstItem = 1;
					lastItem = 40;
				}
				else if (args[1].Contains('-'))
				{
					string [] bags = args[1].Split("-".ToCharArray(), 2);
					firstBag = int.TryParse(bags[0], out firstBag) ? firstBag : 0;
					lastBag = int.TryParse(bags[1], out lastBag) ? lastBag : 0;

					// if (firstBag > lastBag)
					// {
					// 	(firstBag, lastBag) = (lastBag, firstBag);
					// }

					switch(firstBag)
					{
						case 1:
							firstItem = 1;
							break;
						case 2:
							firstItem = 9;
							break;
						case 3:
							firstItem = 17;
							break;
						case 4:
							firstItem = 25;
							break;
						case 5:
							firstItem = 33;
							break;
					}

					switch (lastBag)
					{
						case 1:
							lastItem = 8;
							break;
						case 2:
							lastItem = 16;
							break;
						case 3:
							lastItem = 24;
							break;
						case 4:
							lastItem = 32;
							break;
						case 5:
							lastItem = 40;
							break;
					}

				}
				else if (int.TryParse(args[1], out int bag))
				{
					switch (bag)
					{
						case 1:
							firstItem = 1;
							lastItem = 8;
							break;
						case 2:
							firstItem = 9;
							lastItem = 16;
							break;
						case 3:
							firstItem = 17;
							lastItem = 24;
							break;
						case 4:
							firstItem = 25;
							lastItem = 32;
							break;
						case 5:
							firstItem = 33;
							lastItem = 40;
							break;
					}
				}
			}

			if (client.Player is GamePlayer player && player.Inventory != null && args.Length >= 2)
            {
	            if (player.TargetObject is GameMerchant merchant)
                {
					firstItem += (int)eInventorySlot.FirstBackpack - 1;
					lastItem += (int)eInventorySlot.FirstBackpack - 1;

					var skipPotions = args.Contains("nopot");

					for (int i = firstItem; i <= lastItem; i++)
                    {
						var item = player.Inventory.GetItem((eInventorySlot)i);

						if (item != null)
						{
							if (item is {PackageID: "AtlasXPItem"} or {PackageID: "atlas_orbs_item"} or {PackageID: "atlas_potion"}) continue;
							if (skipPotions && item.Object_Type == 41) continue;
						}
						merchant.OnPlayerSell(player, item);
                    }
				}
	            else if (player.TargetObject is GameGuardMerchant guardMerchant)
	            {
		            firstItem += (int)eInventorySlot.FirstBackpack - 1;
		            lastItem += (int)eInventorySlot.FirstBackpack - 1;

		            var skipPotions = args.Contains("nopot");

		            for (int i = firstItem; i <= lastItem; i++)
		            {
			            var item = player.Inventory.GetItem((eInventorySlot)i);

			            if (item != null)
			            {
				            if (item is {PackageID: "AtlasXPItem"} or {PackageID: "atlas_orbs_item"} or {PackageID: "atlas_potion"}) continue;
				            if (skipPotions && item.Object_Type == 41) continue;
			            }
			            guardMerchant.OnPlayerSell(player, item);
		            }
	            }
				else
					client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Sell.TargetMerchantRequired"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
			}
			else
			{
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Sell.Usage"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
			}
		}
	}
}
