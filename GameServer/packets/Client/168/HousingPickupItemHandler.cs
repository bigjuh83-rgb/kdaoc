using DOL.Database;
using DOL.GS.Housing;
using DOL.Language;

namespace DOL.GS.PacketHandler.Client.v168
{
	/// <summary>
	/// Handle housing pickup item requests from the client.
	/// </summary>
	[PacketHandlerAttribute(PacketHandlerType.TCP, eClientPackets.PlayerPickupHouseItem, "Handle Housing Pick Up Request.", eClientStatus.PlayerInGame)]
	public class HousingPickupItemHandler : PacketHandler
	{
		/// <summary>
		/// Handle the packet
		/// </summary>
		/// <param name="client"></param>
		/// <param name="packet"></param>
		/// <returns></returns>
		protected override void HandlePacketInternal(GameClient client, GSPacketIn packet)
		{
			int unknown = packet.ReadByte();
			int position = packet.ReadByte();
			int housenumber = packet.ReadShort();
			int method = packet.ReadByte();

			House house = HouseMgr.GetHouse(client.Player.CurrentRegionID, housenumber);

			if (house == null) return;
			if (client.Player == null) return;

			//log.DebugFormat("House PickupItem - Method: {0}, Position: {0}", method, position);

			switch (method)
			{
				case 1: //garden item
					// no permission to remove items from the garden, return
					if (!house.CanChangeGarden(client.Player, DecorationPermissions.Remove))
						return;

					foreach (var entry in house.OutdoorItems)
					{
						// continue if this is not the item in question
						OutdoorItem oitem = entry.Value;
						if (oitem.Position != position)
							continue;

						int i = entry.Key;
						GameServer.Database.DeleteObject(oitem.DatabaseItem); //delete the database instance

						// return indoor item into inventory item, add to player inventory
						var invitem = GameInventoryItem.Create((house.OutdoorItems[i]).BaseItem);
						if (client.Player.Inventory.AddItem(eInventorySlot.FirstEmptyBackpack, invitem))
							InventoryLogging.LogInventoryAction("(HOUSE;" + house.HouseNumber + ")", client.Player, eInventoryActionType.Other, invitem.Template, invitem.Count);
						house.RemoveOutdoorItem(i);

						// update garden
						client.Out.SendGarden(house);

						ChatUtil.SendSystemMessage(client, "Scripts.Player.Housing.GardenObjectRemoved", null);
						ChatUtil.SendSystemMessage(client, "Scripts.Player.Housing.ItemReturnedToBackpack", invitem.Name);
						return;
					}

					//no object @ position
					ChatUtil.SendSystemMessage(client, "Scripts.Player.Housing.NoGardenTileAtSlot", position);
					break;

				case 2:
				case 3: //wall/floor mode
					// no permission to remove items from the interior, return
					if (!house.CanChangeInterior(client.Player, DecorationPermissions.Remove))
						return;

					if (house.IndoorItems.ContainsKey(position) == false)
						return;

					IndoorItem iitem = house.IndoorItems[position];
					if (iitem == null)
					{
						client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Player.Housing.HookPointIdNull"), eChatType.CT_Help, eChatLoc.CL_SystemWindow);
						return;
					}

					if (iitem.BaseItem != null)
					{
						var item = GameInventoryItem.Create((house.IndoorItems[(position)]).BaseItem);
						if (GetItemBack(item))
						{
							if (client.Player.Inventory.AddItem(eInventorySlot.FirstEmptyBackpack, item))
							{
								ChatUtil.SendSystemMessage(client, "Scripts.Player.Housing.ItemClearedFromSurface", item.Name,
								                           LanguageMgr.GetTranslation(client.Account.Language, method == 2 ? "Scripts.Player.Housing.SurfaceWall" : "Scripts.Player.Housing.SurfaceFloor"));
								InventoryLogging.LogInventoryAction("(HOUSE;" + house.HouseNumber + ")", client.Player, eInventoryActionType.Other, item.Template, item.Count);
							}
							else
							{
								ChatUtil.SendSystemMessage(client, "Scripts.Player.Housing.NeedInventorySpace", null);
								return;
							}
						}
						else
						{
							ChatUtil.SendSystemMessage(client, "Scripts.Player.Housing.ItemClearedFromSurface", item.Name, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Player.Housing.SurfaceWall"));
						}
					}
					else if (iitem.DatabaseItem.BaseItemID.Contains("GuildBanner"))
					{
						var it = new DbItemTemplate
							{
								Id_nb = iitem.DatabaseItem.BaseItemID,
								CanDropAsLoot = false,
								IsDropable = true,
								IsPickable = true,
								IsTradable = true,
								Item_Type = 41,
								Level = 1,
								MaxCharges = 1,
								MaxCount = 1,
								Model = iitem.DatabaseItem.Model,
								Emblem = iitem.DatabaseItem.Emblem,
								Object_Type = (int) eObjectType.HouseWallObject,
								Realm = 0,
								Quality = 100
							};

						string[] idnb = iitem.DatabaseItem.BaseItemID.Split('_');
						it.Name = idnb[1] + "'s Banner";

						// TODO: Once again with guild banners, templates are memory only and will not load correctly once player logs out - tolakram
						var inv = GameInventoryItem.Create(it);
						if (client.Player.Inventory.AddItem(eInventorySlot.FirstEmptyBackpack, inv))
						{
							ChatUtil.SendSystemMessage(client, "Scripts.Player.Housing.ItemClearedFromSurface", inv.Name,
							                           LanguageMgr.GetTranslation(client.Account.Language, method == 2 ? "Scripts.Player.Housing.SurfaceWall" : "Scripts.Player.Housing.SurfaceFloor"));
							InventoryLogging.LogInventoryAction("(HOUSE;" + house.HouseNumber + ")", client.Player, eInventoryActionType.Other, inv.Template, inv.Count);
						}
						else
						{
							ChatUtil.SendSystemMessage(client, "Scripts.Player.Housing.NeedInventorySpace", null);
							return;
						}
					}
					else if (method == 2)
					{
						ChatUtil.SendSystemMessage(client, "Scripts.Player.Housing.DecorationClearedFromSurface", LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Player.Housing.SurfaceWall"));
					}
					else
					{
						ChatUtil.SendSystemMessage(client, "Scripts.Player.Housing.DecorationClearedFromSurface", LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Player.Housing.SurfaceFloor"));
					}

					GameServer.Database.DeleteObject((house.IndoorItems[(position)]).DatabaseItem);
					house.RemoveIndoorItem(position);

					using (var pak = PooledObjectFactory.GetForTick<GSTCPPacketOut>().Init(AbstractPacketLib.GetPacketCode(eServerPackets.HousingItem)))
					{
						if (client.Version >= GameClient.eClientVersion.Version1125)
						{
							pak.WriteShortLowEndian((ushort) housenumber);
							pak.WriteByte(0x01);
							pak.WriteByte(0x00);
							pak.WriteByte((byte) position);
							pak.Fill(0x00, 11);
						}
						else
						{
							pak.WriteShort((ushort) housenumber);
							pak.WriteByte(0x01);
							pak.WriteByte(0x00);
							pak.WriteByte((byte) position);
							pak.WriteByte(0x00);
						}

						foreach (GamePlayer plr in house.GetAllPlayersInHouse())
						{
							plr.Out.SendTCP(pak);
						}
					}

					break;
			}
		}

		private static bool GetItemBack(DbInventoryItem item)
		{
			switch (item.Object_Type)
			{
				case (int) eObjectType.Axe:
				case (int) eObjectType.Blades:
				case (int) eObjectType.Blunt:
				case (int) eObjectType.CelticSpear:
				case (int) eObjectType.CompositeBow:
				case (int) eObjectType.Crossbow:
				case (int) eObjectType.Flexible:
				case (int) eObjectType.Hammer:
				case (int) eObjectType.HandToHand:
				case (int) eObjectType.LargeWeapons:
				case (int) eObjectType.LeftAxe:
				case (int) eObjectType.Longbow:
				case (int) eObjectType.MaulerStaff:
				case (int) eObjectType.Piercing:
				case (int) eObjectType.PolearmWeapon:
				case (int) eObjectType.RecurvedBow:
				case (int) eObjectType.Scythe:
				case (int) eObjectType.Shield:
				case (int) eObjectType.SlashingWeapon:
				case (int) eObjectType.Spear:
				case (int) eObjectType.Staff:
				case (int) eObjectType.Sword:
				case (int) eObjectType.Thrown:
				case (int) eObjectType.ThrustWeapon:
				case (int) eObjectType.TwoHandedWeapon:
					return false;
				default:
					return true;
			}
		}
	}
}
