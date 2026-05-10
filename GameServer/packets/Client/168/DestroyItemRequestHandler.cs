using DOL.Database;
using DOL.Language;

namespace DOL.GS.PacketHandler.Client.v168
{
	[PacketHandlerAttribute(PacketHandlerType.TCP, eClientPackets.DestroyItemRequest, "Handles destroy item requests from client", eClientStatus.PlayerInGame)]
	public class DestroyItemRequestHandler : PacketHandler
	{
		protected override void HandlePacketInternal(GameClient client, GSPacketIn packet)
		{
			packet.Skip(4);
			int slot = packet.ReadShort();
			DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
			if (item != null)
			{
				if (item.IsIndestructible)
				{
					client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Inventory.Destroy.CantDestroy", item.GetName(0, false)), eChatType.CT_System, eChatLoc.CL_SystemWindow);
					return;
				}

				if (item.Id_nb == "ARelic")
				{
					client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Inventory.Destroy.Relic"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
					return;
				}

				if (client.Player.Inventory.EquippedItems.Contains(item))
				{
					client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Inventory.Destroy.Equipped"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
					return;
				}

				if (client.Player.Inventory.RemoveItem(item))
				{
					client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Inventory.Destroy.Success", item.Name), eChatType.CT_System, eChatLoc.CL_SystemWindow);
					InventoryLogging.LogInventoryAction(client.Player, "(destroy)", eInventoryActionType.Other, item.Template, item.Count);
				}
			}
		}
	}
}
