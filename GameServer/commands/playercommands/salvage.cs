using System;
using System.Collections.Generic;
using DOL.Database;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&salvage",
		ePrivLevel.Player,
		"You can salvage one or multiple item(s) when you are a crafter",
		"/salvage", "/salvage all", "/salvage <bag>", "/salvage <bag-bag>", "Add 'Qxx' to specify the minimum quality of the items to salvage (Q98)")]
	public class SalvageCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
			if (IsSpammingCommand(client.Player, "salvage"))
				return;

			uint firstItem = 0, lastItem = 0, qualityInt = 0;

			if (args.Length >= 2)
			{
				if (args[1].Equals("all", StringComparison.OrdinalIgnoreCase))
				{
					firstItem = 1;
					lastItem = 40;
				}
				else if (args[1].Contains('-'))
				{
					string[] bags = args[1].Split("-".ToCharArray(), 2);

					if (!uint.TryParse(bags[0], out uint firstBag) || !uint.TryParse(bags[1], out uint lastBag))
						return;

					if (firstBag > lastBag)
					{
						client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Salvage.InvalidBagRange"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
						return;
					}

					switch (firstBag)
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
						default:
							client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Salvage.InvalidFirstBag"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
							return;
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
						default:
							client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Salvage.InvalidLastBag"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
							return;
					}
				}
				else if (uint.TryParse(args[1], out uint bag))
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
						default:
							client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Salvage.InvalidBag"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
							return;
					}
				}

				IList<DbInventoryItem> items = new List<DbInventoryItem>();
				firstItem += (uint)eInventorySlot.FirstBackpack - 1;
				lastItem += (uint)eInventorySlot.FirstBackpack - 1;

				foreach (string arg in args)
				{
					if (!arg.StartsWith("Q", StringComparison.OrdinalIgnoreCase))
						continue;

					string quality = arg.Replace("Q", "", StringComparison.OrdinalIgnoreCase);

					if (!uint.TryParse(quality, out qualityInt))
					{
						client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Salvage.InvalidQualityFilter"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
						return;
					}

					if (qualityInt > 100)
					{
						client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Salvage.QualityTooHigh"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
						return;
					}
				}

				for (uint i = firstItem; i <= lastItem; i++)
				{
					DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)i);

					if (item == null)
						continue;

					if (!Salvage.IsAllowedToBeginWork(client.Player, item, true))
						continue;

					if (qualityInt > 0)
					{
						if (item.Quality <= qualityInt)
							items.Add(item);
					}
					else
						items.Add(item);
				}

				if (items.Count > 0)
					client.Player.SalvageItemList(items);
			}
			else
			{
				if (client.Player.TargetObject is not WorldInventoryItem item)
					return;

				client.Player.SalvageItem(item.Item);
			}
		}
	}
}
