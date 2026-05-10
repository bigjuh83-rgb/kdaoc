using System;
using System.Collections.Generic;
using DOL.Database;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands
{
	[Cmd("&item",
	     ePrivLevel.GM,
	     "GMCommands.Item.Description",
	     "GMCommands.Item.Information",
	     "GMCommands.Item.Usage.Blank",
	     "GMCommands.Item.Usage.Info",
	     "GMCommands.Item.Usage.Create",
	     "GMCommands.Item.Usage.Count",
	     "GMCommands.Item.Usage.MaxCount",
	     "GMCommands.Item.Usage.PackSize",
	     "GMCommands.Item.Usage.Model",
	     "GMCommands.Item.Usage.Extension",
	     "GMCommands.Item.Usage.Color",
	     "GMCommands.Item.Usage.Effect",
	     "GMCommands.Item.Usage.Name",
	     "GMCommands.Item.Usage.Description",
	     "GMCommands.Item.Usage.CrafterName",
	     "GMCommands.Item.Usage.Type",
	     "GMCommands.Item.Usage.Object",
	     "GMCommands.Item.Usage.Hand",
	     "GMCommands.Item.Usage.DamageType",
	     "GMCommands.Item.Usage.Emblem",
	     "GMCommands.Item.Usage.Price",
	     "GMCommands.Item.Usage.Condition",
	     "GMCommands.Item.Usage.Quality",
	     "GMCommands.Item.Usage.Durability",
	     "GMCommands.Item.Usage.isPickable",
	     "GMCommands.Item.Usage.IsNotLosingDUR",
	     "GMCommands.Item.Usage.IsIndestructible",
	     "GMCommands.Item.Usage.isDropable",
	     "GMCommands.Item.Usage.IsTradable",
	     "GMCommands.Item.Usage.IsStackable",
	     "GMCommands.Item.Usage.CanDropAsLoot",
	     "GMCommands.Item.Usage.Bonus",
	     "GMCommands.Item.Usage.mBonus",
	     "GMCommands.Item.Usage.Weight",
	     "GMCommands.Item.Usage.DPS_AF",
	     "GMCommands.Item.Usage.SPD_ABS",
	     "GMCommands.Item.Usage.Material",
	     "GMCommands.Item.Usage.Spell",
	     "GMCommands.Item.Usage.Spell1",
	     "GMCommands.Item.Usage.Proc",
	     "GMCommands.Item.Usage.Proc1",
	     "GMCommands.Item.Usage.ProcChance",
	     "GMCommands.Item.Usage.Poison",
	     "GMCommands.Item.Usage.Realm",
	     "GMCommands.Item.Usage.ClassType",
	     "GMCommands.Item.Usage.PackageID",
	     "GMCommands.Item.Usage.LevelRequired",
	     "GMCommands.Item.Usage.BonusLevel",
	     "GMCommands.Item.Usage.Flags",
	     "GMCommands.Item.Usage.Classes",
	     "GMCommands.Item.Usage.SalvageID",
	     "GMCommands.Item.Usage.SalvageInfo",
	     "GMCommands.Item.Usage.Update",
	     "GMCommands.Item.Usage.Save",
	     "GMCommands.Item.Usage.AddUnique",
	     "GMCommands.Item.Usage.SaveUnique",
	     "GMCommands.Item.Usage.FindID",
	     "GMCommands.Item.Usage.FindName",
	     "GMCommands.Item.Usage.Load",
	     "GMCommands.Item.Usage.LoadPackage",
	     "GMCommands.Item.Usage.LoadSpells")]
	public class ItemCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		private static readonly Logging.Logger Log = Logging.LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);

		private static string T(GameClient client, string key, params object[] args)
			=> LanguageMgr.GetTranslation(client.Account.Language, key, args);

		public void OnCommand(GameClient client, string[] args)
		{
			if (args.Length < 2)
			{
				DisplaySyntax(client);
				return;
			}

			try
			{
				switch (args[1].ToLower())
				{
						#region Blank
					case "blank":
						{
                            DbItemTemplate newTemplate = new DbItemTemplate
                            {
                                Name = T(client, "GMCommands.Item.Blank.Name"),
                                Id_nb = DbInventoryItem.BLANK_ITEM
                            };
                            GameInventoryItem item = new GameInventoryItem(newTemplate);
							if (client.Player.Inventory.AddItem(eInventorySlot.FirstEmptyBackpack, item))
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Blank.ItemCreated"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								InventoryLogging.LogInventoryAction(client.Player, client.Player, eInventoryActionType.Other, item.Template, item.Count);
							}
							else
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Blank.CreationError"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
							}
							break;
						}
						#endregion Blank
						#region Classes
					case "classes":
						{
							int slot = (int)eInventorySlot.LastBackpack;

							if (args.Length >= 4)
							{
								slot = Convert.ToInt32(args[3]);
							}

							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);

							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}

							item.AllowedClasses = args[2].Trim();
							break;
						}
						#endregion
						#region Create
					case "create":
						{
							DbItemTemplate template = GameServer.Database.FindObjectByKey<DbItemTemplate>(args[2]);
							if (template == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Create.NotFound", args[2]), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							else
							{
								int count = 1;
								if (args.Length >= 4)
								{
									try
									{
										count = Convert.ToInt32(args[3]);
										if (count < 1)
											count = 1;
									}
									catch (Exception)
									{
									}
								}

								DbInventoryItem item = GameInventoryItem.Create(template);
								if (item.IsStackable)
								{
									item.Count = count;
								}
								if (client.Player.Inventory.AddItem(eInventorySlot.FirstEmptyBackpack, item))
								{
									client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Create.Created", item.Level, item.GetName(0, false), count), eChatType.CT_System, eChatLoc.CL_SystemWindow);
									InventoryLogging.LogInventoryAction(client.Player, client.Player, eInventoryActionType.Other, item.Template, item.Count);
								}
							}
							break;
						}
						#endregion Create
						#region Count
					case "count":
						{
							int slot = (int)eInventorySlot.LastBackpack;

							if (args.Length >= 4)
							{
								slot = Convert.ToInt32(args[3]);
							}

							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);

							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							if (!item.IsStackable)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NotStackable", item.GetName(0, true)), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							if (Convert.ToInt32(args[2]) < 1)
							{
								item.Count = 1;
							}
							else
							{
								item.Count = Convert.ToInt32(args[2]);
							}

							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							client.Player.UpdateEncumbrance();
							break;
						}
						#endregion Count
						#region MaxCount
					case "maxcount":
						{
							int slot = (int)eInventorySlot.LastBackpack;

							if (args.Length >= 4)
							{
								slot = Convert.ToInt32(args[3]);
							}

							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);

							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.MaxCount = Convert.ToInt32(args[2]);
							if (item.MaxCount < 1)
								item.MaxCount = 1;
							break;
						}
						#endregion MaxCount
						#region PackSize
					case "packsize":
						{
							int slot = (int)eInventorySlot.LastBackpack;

							if (args.Length >= 4)
							{
								slot = Convert.ToInt32(args[3]);
							}

							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);

							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.PackSize = Convert.ToInt32(args[2]);
							if (item.PackSize < 1)
								item.PackSize = 1;
							break;
						}
						#endregion PackSize
						#region Info
					case "info":
						{
							DbItemTemplate obj = GameServer.Database.FindObjectByKey<DbItemTemplate>(args[2]);
							if (obj == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Info.ItemTemplateUnknown", args[2]), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							GameInventoryItem invItem = GameInventoryItem.Create(obj);
							var objectInfo = new List<string>();
                            invItem.WriteTechnicalInfo(objectInfo, client);
							client.Out.SendCustomTextWindow(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Info.Informations", obj.Id_nb), objectInfo);
							break;
						}
						#endregion Info
						#region Model
					case "model":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.Model = Convert.ToUInt16(args[2]);
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							if (item.SlotPosition < (int)eInventorySlot.FirstBackpack)
								client.Player.UpdateEquipmentAppearance();
							break;
						}
						#endregion Model
						#region Extension
					case "extension":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.Extension = Convert.ToByte(args[2]);

							if (item.Template is DbItemUnique || (item.Template is DbItemTemplate && (item.Template as DbItemTemplate).AllowUpdate))
							{
								item.Template.Extension = item.Extension;
							}

							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							if (item.SlotPosition < (int)eInventorySlot.FirstBackpack)
								client.Player.UpdateEquipmentAppearance();
							break;
						}
						#endregion Extension
						#region Color
					case "color":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.Color = Convert.ToUInt16(args[2]);

							if (item.Template is DbItemUnique || (item.Template is DbItemTemplate && (item.Template as DbItemTemplate).AllowUpdate))
							{
								item.Template.Color = item.Color;
							}

							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							if (item.SlotPosition < (int)eInventorySlot.FirstBackpack)
								client.Player.UpdateEquipmentAppearance();
							break;
						}
						#endregion Color
						#region Effect
					case "effect":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.Effect = Convert.ToUInt16(args[2]);
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							if (item.SlotPosition < (int)eInventorySlot.FirstBackpack)
								client.Player.UpdateEquipmentAppearance();
							break;
						}
						#endregion Effect
						#region Type
					case "type":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.Item_Type = Convert.ToInt32(args[2]);
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Type
						#region Object
					case "object":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.Object_Type = Convert.ToInt32(args[2]);
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Object
						#region Hand
					case "hand":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.Hand = Convert.ToInt32(args[2]);
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Hand
						#region DamageType
					case "damagetype":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.Type_Damage = Convert.ToInt32(args[2]);
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion DamageType
						#region Name
					case "name":
						{
							string name = args[2];
							int slot = (int)eInventorySlot.LastBackpack;

							if (int.TryParse(args[args.Length - 1], out slot))
							{
								name = string.Join(" ", args, 2, args.Length - 3);
							}
							else
							{
								name = string.Join(" ", args, 2, args.Length - 2);
								slot = (int)eInventorySlot.LastBackpack;
							}

							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}

							item.Name = name;
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Name
						#region Description
					case "description":
						{
							string desc = args[2];
							int slot = (int)eInventorySlot.LastBackpack;

							if (int.TryParse(args[args.Length - 1], out slot))
							{
								desc = string.Join(" ", args, 2, args.Length - 3);
							}
							else
							{
								desc = string.Join(" ", args, 2, args.Length - 2);
								slot = (int)eInventorySlot.LastBackpack;
							}

							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}

							item.Description = desc;
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Name
						#region CrafterName
					case "craftername":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.IsCrafted = true;
							item.Creator = args[2];
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion CrafterName
						#region Emblem
					case "emblem":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.Emblem = Convert.ToInt32(args[2]);

							if (item.Template is DbItemUnique || (item.Template is DbItemTemplate && (item.Template as DbItemTemplate).AllowUpdate))
							{
								item.Template.Emblem = item.Emblem;
							}

							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							if (item.SlotPosition < (int)eInventorySlot.FirstBackpack)
								client.Player.UpdateEquipmentAppearance();
							break;
						}
						#endregion Emblem
						#region Level
					case "level":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.Level = Convert.ToUInt16(args[2]);
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Level
						#region Price
					case "price":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 7)
							{
								try
								{
									slot = Convert.ToInt32(args[6]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.Price = Money.GetMoney(0, (int)(Convert.ToInt16(args[2]) % 1000), (int)(Convert.ToInt16(args[3]) % 1000), (int)(Convert.ToByte(args[4]) % 100), (int)(Convert.ToByte(args[5]) % 100));
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Price
						#region Condition
					case "condition":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 5)
							{
								try
								{
									slot = Convert.ToInt32(args[4]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}

							UpdateAllowed(item, client);
							int con = Convert.ToInt32(args[2]);
							int maxcon = Convert.ToInt32(args[3]);
							item.Condition = con;
							item.MaxCondition = maxcon;
							if (item.Template is DbItemUnique || (item.Template is DbItemTemplate && (item.Template as DbItemTemplate).AllowUpdate))
							{
								item.Template.Condition = item.Condition;
							}
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Condition
						#region Durability
					case "durability":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 5)
							{
								try
								{
									slot = Convert.ToInt32(args[4]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}

							UpdateAllowed(item, client);
							int Dur = Convert.ToInt32(args[2]);
							int MaxDur = Convert.ToInt32(args[3]);
							item.Durability = Dur;
							if (item.Template is DbItemUnique || (item.Template is DbItemTemplate && (item.Template as DbItemTemplate).AllowUpdate))
							{
								item.Template.Durability = item.Durability;
							}
							item.MaxDurability = MaxDur;
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Durability
						#region Quality
					case "quality":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							int Qua = Convert.ToInt32(args[2]);
							item.Quality = Qua;
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Quality
						#region Bonus
					case "bonus":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							int Bonus = Convert.ToInt32(args[2]);
							item.Bonus = Bonus;
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Bonus
						#region mBonus
					case "mbonus":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							int num = 0;
							int bonusType = 0;
							int bonusValue = 0;
							if (args.Length >= 6)
							{
								try
								{
									slot = Convert.ToInt32(args[5]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							try
							{
								num = Convert.ToInt32(args[2]);
							}
							catch
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.mBonus.NonSetBonusNumber"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
							}
							try
							{
								bonusType = Convert.ToInt32(args[3]);
								if (bonusType < 0 || bonusType >= (int)eProperty.MaxProperty)
								{
									client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.mBonus.TypeShouldBeInRange", (int)(eProperty.MaxProperty - 1)), eChatType.CT_System, eChatLoc.CL_SystemWindow);
									break;
								}
							}
							catch
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.mBonus.NonSetBonusType"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
							}
							try
							{
								bonusValue = Convert.ToInt32(args[4]);
								switch (num)
								{
									case 0:
										{
											item.ExtraBonus = bonusValue;
											item.ExtraBonusType = bonusType;
											break;
										}
									case 1:
										{
											item.Bonus1 = bonusValue;
											item.Bonus1Type = bonusType;
											break;
										}
									case 2:
										{
											item.Bonus2 = bonusValue;
											item.Bonus2Type = bonusType;
											break;
										}
									case 3:
										{
											item.Bonus3 = bonusValue;
											item.Bonus3Type = bonusType;
											break;
										}
									case 4:
										{
											item.Bonus4 = bonusValue;
											item.Bonus4Type = bonusType;
											break;
										}
									case 5:
										{
											item.Bonus5 = bonusValue;
											item.Bonus5Type = bonusType;
											break;
										}
									case 6:
										{
											item.Bonus6 = bonusValue;
											item.Bonus6Type = bonusType;
											break;
										}
									case 7:
										{
											item.Bonus7 = bonusValue;
											item.Bonus7Type = bonusType;
											break;
										}
									case 8:
										{
											item.Bonus8 = bonusValue;
											item.Bonus8Type = bonusType;
											break;
										}
									case 9:
										{
											item.Bonus9 = bonusValue;
											item.Bonus9Type = bonusType;
											break;
										}
									case 10:
										{
											item.Bonus10 = bonusValue;
											item.Bonus10Type = bonusType;
											break;
										}
									default:
										client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.mBonus.UnknownBonusNumber", num), eChatType.CT_System, eChatLoc.CL_SystemWindow);
										return;
								}
								if (item.SlotPosition < (int)eInventorySlot.FirstBackpack)
								{
									client.Out.SendCharStatsUpdate();
									client.Out.SendCharResistsUpdate();
								}
							}
							catch
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.mBonus.NotSetBonusValue"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
							}
							break;
						}
						#endregion mBonus
						#region Weight
					case "weight":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.Weight = Convert.ToInt32(args[2]);
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Weight
						#region DPS_AF - DPS - AF
					case "dps_af":
					case "dps":
					case "af":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.DPS_AF = Convert.ToByte(args[2]);
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion DPS_AF - DPS - AF
						#region SPD_ABS - SPD - ABS
					case "spd_abs":
					case "spd":
					case "abs":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.SPD_ABS = Convert.ToByte(args[2]);
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion SPD_ABS - SPD - ABS
						#region IsDropable
					case "isdropable":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.IsDropable = Convert.ToBoolean(args[2]);
							break;
						}
						#endregion IsDropable
						#region IsPickable
					case "ispickable":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.IsPickable = Convert.ToBoolean(args[2]);
							break;
						}
						#endregion IsPickable
						#region IsNotLosingDur
					case "isnotlosingdur":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.IsNotLosingDur = Convert.ToBoolean(args[2]);
							break;
						}
						#endregion IsNotLosingDur
						#region IsIndestructible
					case "isindestructible":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.IsIndestructible = Convert.ToBoolean(args[2]);
							break;
						}
						#endregion IsIndestructible
						#region IsTradable
					case "istradable":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.IsTradable = Convert.ToBoolean(args[2]);
							break;
						}
						#endregion IsTradable
						#region CanDropAsLoot
					case "candropasloot":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.CanDropAsLoot = Convert.ToBoolean(args[2]);
							break;
						}
						#endregion CanDropAsLoot
						#region Spell
					case "spell":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 6)
							{
								try
								{
									slot = Convert.ToInt32(args[5]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							int Charges = Convert.ToInt32(args[2]);
							int MaxCharges = Convert.ToInt32(args[3]);
							int SpellID = Convert.ToInt32(args[4]);
							item.Charges = Charges;
							item.MaxCharges = MaxCharges;
							if (item.Template is DbItemUnique || (item.Template is DbItemTemplate && (item.Template as DbItemTemplate).AllowUpdate))
							{
								item.Template.Charges = item.Charges;
								item.Template.MaxCharges = item.MaxCharges;
							}
							item.SpellID = SpellID;
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Spell
						#region Spell1
					case "spell1":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 6)
							{
								try
								{
									slot = Convert.ToInt32(args[5]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							int Charges = Convert.ToInt32(args[2]);
							int MaxCharges = Convert.ToInt32(args[3]);
							int SpellID1 = Convert.ToInt32(args[4]);
							item.Charges1 = Charges;
							item.MaxCharges1 = MaxCharges;
							if (item.Template is DbItemUnique || (item.Template is DbItemTemplate && (item.Template as DbItemTemplate).AllowUpdate))
							{
								item.Template.Charges1 = item.Charges1;
								item.Template.MaxCharges1 = item.MaxCharges1;
							}
							item.SpellID1 = SpellID1;
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Spell1
						#region Proc
					case "proc":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.ProcSpellID = Convert.ToInt32(args[2]);
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Proc
						#region Proc1
					case "proc1":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.ProcSpellID1 = Convert.ToInt32(args[2]);
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Proc1
						#region ProcChance
					case "procchance":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.ProcChance = Convert.ToByte(args[2]);
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion ProcChance
						#region Poison
					case "poison":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 6)
							{
								try
								{
									slot = Convert.ToInt32(args[5]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							int Charges = Convert.ToInt32(args[2]);
							int MaxCharges = Convert.ToInt32(args[3]);
							int SpellID = Convert.ToInt32(args[4]);
							item.PoisonCharges = Charges;
							item.PoisonMaxCharges = MaxCharges;
							if (item.Template is DbItemUnique || (item.Template is DbItemTemplate && (item.Template as DbItemTemplate).AllowUpdate))
							{
								item.Template.PoisonCharges = item.PoisonCharges;
								item.Template.PoisonMaxCharges = item.PoisonMaxCharges;
							}
							item.PoisonSpellID = SpellID;
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Poison
						#region Realm
					case "realm":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							item.Realm = int.Parse(args[2]);
							break;
						}
						#endregion Realm
						#region Level Required
					case "levelrequired":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							int setting = Convert.ToInt32(args[2]);
							item.LevelRequirement = setting;
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Level Required
						#region Bonus Level
					case "bonuslevel":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}
							int setting = Convert.ToInt32(args[2]);
							item.BonusLevel = setting;
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Bonus Level
						#region ClassType
					case "classtype":
						{
							string classType = args[2];
							int slot = (int)eInventorySlot.LastBackpack;

							if (int.TryParse(args[args.Length - 1], out slot) == false)
							{
								slot = (int)eInventorySlot.LastBackpack;
							}

							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}

							item.ClassType = classType;
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion ClassType
						#region PackageID
					case "packageid":
						{
							string packageID = args[2];
							int slot = (int)eInventorySlot.LastBackpack;

							if (int.TryParse(args[args.Length - 1], out slot) == false)
							{
								slot = (int)eInventorySlot.LastBackpack;
							}

							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}

							item.PackageID = packageID;
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion PackageID
						#region Flags
					case "flags":
						{
							int flags = Convert.ToInt32(args[2]);
							int slot = (int)eInventorySlot.LastBackpack;

							if (args.Length == 4)
							{
								slot = Convert.ToInt32(args[3]);
							}

							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}

							item.Flags = flags;
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
						#endregion Flags
						#region Salvage
					case "salvageid":
						{
							int salvageID = Convert.ToInt32(args[2]);
							int slot = (int)eInventorySlot.LastBackpack;

							if (args.Length == 4)
							{
								slot = Convert.ToInt32(args[3]);
							}

							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}

							item.SalvageYieldID = salvageID;
							client.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { item });
							break;
						}
					case "salvageinfo":
						{
							int slot = (int)eInventorySlot.LastBackpack;

							if (args.Length == 3)
							{
								slot = Convert.ToInt32(args[2]);
							}

							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}

							List<string> list = new List<string>();

							DbSalvageYield salvageYield = null;
							bool calculated = true;
							var whereClause = WhereClause.Empty;

							int salvageLevel = CraftingMgr.GetItemCraftLevel(item) / 100;
							if (salvageLevel > 9) salvageLevel = 9; // max 9

							if (item.SalvageYieldID == 0)
							{
								whereClause = DB.Column("ObjectType").IsEqualTo(item.Object_Type).And(DB.Column("SalvageLevel").IsEqualTo(salvageLevel));
							}
							else
							{
								whereClause = DB.Column("ID").IsEqualTo(item.SalvageYieldID);
								calculated = false;
							}

							if (ServerProperties.Properties.USE_SALVAGE_PER_REALM)
							{
								whereClause = whereClause.And(DB.Column("Realm").IsEqualTo((int)eRealm.None).Or(DB.Column("Realm").IsEqualTo(item.Realm)));
							}

							salvageYield = DOLDB<DbSalvageYield>.SelectObject(whereClause);

							DbSalvageYield yield = null;

							if (salvageYield != null)
							{
								yield = salvageYield.Clone() as DbSalvageYield;
							}

							if (yield == null || yield.PackageID == DbSalvageYield.LEGACY_SALVAGE_ID)
							{
								if (calculated == false)
								{
									list.Add(T(client, "GMCommands.Item.SalvageInfo.SpecifiedNotFound", item.SalvageYieldID));
								}
								else if (ServerProperties.Properties.USE_NEW_SALVAGE)
								{
									list.Add(T(client, "GMCommands.Item.SalvageInfo.CalculatedValuesNew"));
								}
								else
								{
									list.Add(T(client, "GMCommands.Item.SalvageInfo.CalculatedValuesLegacy"));
								}
							}
							else
							{
								list.Add(T(client, "GMCommands.Item.SalvageInfo.UsingID", yield.ID));
							}

							list.Add(" ");

							DbItemTemplate material = GameServer.Database.FindObjectByKey<DbItemTemplate>(yield.MaterialId_nb);
							string materialName = yield.MaterialId_nb;

							if (material != null)
							{
								materialName = material.Name + " (" + materialName + ")";
							}
							else
							{
								materialName = T(client, "GMCommands.Item.SalvageInfo.MaterialNotFound", materialName);
							}

							if (calculated == false)
							{
								if (yield != null)
								{
									list.Add(T(client, "GMCommands.Item.SalvageInfo.ID", yield.ID));
									list.Add(T(client, "GMCommands.Item.SalvageInfo.Material", materialName));
									list.Add(T(client, "GMCommands.Item.SalvageInfo.Count", yield.Count));
									list.Add(T(client, "GMCommands.Item.SalvageInfo.Realm", yield.Realm == 0 ? T(client, "GMCommands.Item.SalvageInfo.Realm.Any") : GlobalConstants.RealmToName((eRealm)yield.Realm)));
									list.Add(T(client, "GMCommands.Item.SalvageInfo.PackageID", yield.PackageID));
								}
							}
							else
							{
								list.Add(T(client, "GMCommands.Item.SalvageInfo.ID", yield.ID));
								list.Add(T(client, "GMCommands.Item.SalvageInfo.ObjectType", yield.ObjectType));
								list.Add(T(client, "GMCommands.Item.SalvageInfo.SalvageLevel", yield.SalvageLevel));
								list.Add(T(client, "GMCommands.Item.SalvageInfo.Material", materialName));
								list.Add(T(client, "GMCommands.Item.SalvageInfo.Count", Salvage.GetMaterialYield(client.Player, item, yield, material)));
								list.Add(T(client, "GMCommands.Item.SalvageInfo.Realm", yield.Realm == 0 ? T(client, "GMCommands.Item.SalvageInfo.Realm.Any") : GlobalConstants.RealmToName((eRealm)yield.Realm)));
								list.Add(T(client, "GMCommands.Item.SalvageInfo.PackageID", yield.PackageID));
							}

							client.Out.SendCustomTextWindow(T(client, "GMCommands.Item.SalvageInfo.WindowTitle", item.Name), list);
							break;
						}
						#endregion Flags
						#region Update
					case "update":
					case "updatetemplate":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length == 3)
							{
								slot = Convert.ToInt32(args[2]);
							}

							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}

							UpdateAllowed(item, client);
							break;
						}
						#endregion Update
						#region SaveUnique
					case "saveunique":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							string idnb = string.Empty;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
								if (slot > (int)eInventorySlot.LastBackpack)
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
								if (slot < 0)
								{
									slot = 0;
								}

								idnb = args[2];
							}
							else if (args.Length >= 3)
							{
								idnb = args[2];
							}
							else if (args.Length < 2)
							{
								DisplaySyntax(client);
								return;
							}

							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}

							if (item.Template is DbItemUnique)
							{
								DbItemUnique itemUnique = item.Template as DbItemUnique;
								Log.Debug("update ItemUnique " + item.Template.Id_nb);
								GameServer.Database.SaveObject(itemUnique);
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.SaveUnique.Updated", itemUnique.Id_nb), eChatType.CT_System, eChatLoc.CL_SystemWindow);
							}
							else
							{
								DisplayMessage(client, T(client, "GMCommands.Item.SaveUnique.NotItemUnique"));
								return;
							}
						}
						break;
						#endregion SaveUnique
						#region Save / AddUnique
					case "save":
					case "addunique":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							string idnb = string.Empty;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
								if (slot > (int)eInventorySlot.LastBackpack)
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
								if (slot < 0)
								{
									slot = 0;
								}

								idnb = args[2];
							}
							else if (args.Length >= 3)
							{
								idnb = args[2];
							}
							else if (args.Length < 2)
							{
								DisplaySyntax(client);
								return;
							}

							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}

							// if a blank item was created then AllowAdd will be false here
							if (idnb == string.Empty && (item.AllowAdd == false || item.Id_nb == DbInventoryItem.BLANK_ITEM || args[1].ToLower() == "addunique"))
							{
								DisplayMessage(client, T(client, "GMCommands.Item.Save.NeedNewID"));
								return;
							}
							else if (idnb == string.Empty)
							{
								if (args[1].ToLower() == "save" && item.Template is DbItemUnique)
								{
									DisplayMessage(client, T(client, "GMCommands.Item.Save.NeedNewIDForUniqueTemplate"));
									return;
								}

								idnb = item.Id_nb;
							}

							DbItemTemplate temp = null;
							if (args[1].ToLower() == "save")
							{
								// if the item is allready in the database
								temp = GameServer.Database.FindObjectByKey<DbItemTemplate>(idnb);
							}

							// save the new item
							if (temp == null)
							{
								if (args[1].ToLower() == "save")
								{
									try
									{
										client.Player.Inventory.RemoveItem(item);
                                        DbItemTemplate itemTemplate = new DbItemTemplate(item.Template)
                                        {
                                            Id_nb = idnb
                                        };
                                        GameServer.Database.AddObject(itemTemplate);
										Log.Debug("Added New Item Template: " + itemTemplate.Id_nb);
										DisplayMessage(client, T(client, "GMCommands.Item.Save.AddedTemplate", itemTemplate.Id_nb));
										GameInventoryItem newItem = GameInventoryItem.Create(itemTemplate);
										if (client.Player.Inventory.AddItem((eInventorySlot)slot, newItem))
											InventoryLogging.LogInventoryAction(client.Player, client.Player, eInventoryActionType.Other, newItem.Template, newItem.Count);
									}
									catch (Exception ex)
									{
										DisplayMessage(client, T(client, "GMCommands.Item.Save.AddTemplateError", ex.Message));
										return;
									}
								}
								else //addunique
								{
									try
									{
										client.Player.Inventory.RemoveItem(item);
                                        DbItemUnique unique = new DbItemUnique(item.Template)
                                        {
                                            Id_nb = idnb
                                        };
										Log.Debug("Added New ItemUnique: " + unique.Id_nb + " (" + unique.ObjectId + ")");
										DisplayMessage(client, T(client, "GMCommands.Item.Save.AddedUnique", unique.Id_nb, unique.ObjectId));
										GameInventoryItem newItem = GameInventoryItem.Create(unique);
										if (client.Player.Inventory.AddItem((eInventorySlot)slot, newItem))
											InventoryLogging.LogInventoryAction(client.Player, client.Player, eInventoryActionType.Other, newItem.Template, newItem.Count);
									}
									catch (Exception ex)
									{
										DisplayMessage(client, T(client, "GMCommands.Item.Save.AddUniqueError", ex.Message));
										return;
									}
								}
							}
							else // update the item
							{
								item.Template.Dirty = true;
								GameServer.Database.SaveObject(item.Template);
								GameServer.Database.UpdateInCache<DbItemTemplate>(item.Template.Id_nb);
								DisplayMessage(client, T(client, "GMCommands.Item.Save.UpdatedInventoryItem", item.Id_nb));

								if (item.Template is DbItemTemplate && (item.Template as DbItemTemplate).AllowUpdate)
								{
									Log.Debug("Updated ItemTemplate: " + item.Template.Id_nb);
									DisplayMessage(client, T(client, "GMCommands.Item.Save.SourceTemplateUpdated"));
								}
							}

						}
						break;
						#endregion Save / AddUnique
						#region FindID
					case "findid":
						{
							string name = string.Join(" ", args, 2, args.Length - 2);
							if (name != string.Empty)
							{
								var items = DOLDB<DbItemTemplate>.SelectObjects(DB.Column("id_nb").IsLike($"%{name}%"));
								DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.FindID.MatchingIDsForX", name, items.Count), new object[] { });
								foreach (DbItemTemplate item in items)
								{
									DisplayMessage(client, item.Id_nb + " (" + item.Name + ")", new object[] { });
								}
							}
							break;
						}
						#endregion FindID
						#region FindName
					case "findname":
						{
							string name = string.Join(" ", args, 2, args.Length - 2);
							if (name != string.Empty)
							{
								var items = DOLDB<DbItemTemplate>.SelectObjects(DB.Column("name").IsLike($"%{name}%"));
								DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.FindName.MatchingNamesForX", name, items.Count), new object[] { });
								foreach (DbItemTemplate item in items)
								{
									DisplayMessage(client, item.Name + "  (" + item.Id_nb + ")", new object[] { });
								}
							}
							break;
						}
						#endregion FindName
						#region Load
					case "load":
						{
							if (GameServer.Database.UpdateInCache<DbItemTemplate>(args[2]))
							{
								Log.DebugFormat("Item {0} updated or added to ItemTemplate cache.", args[2]);
								DisplayMessage(client, T(client, "GMCommands.Item.Load.UpdatedOrAdded", args[2]), new object[] { });
							}
							else
							{
								Log.DebugFormat("Item {0} not found.", args[2]);
								DisplayMessage(client, T(client, "GMCommands.Item.Load.NotFound", args[2]), new object[] { });
							}
							break;
						}
					case "reloadall":
						{
							var allItems = DOLDB<DbItemTemplate>.SelectAllObjects();

							if (allItems != null)
							{
								int count = 0;

								foreach (DbItemTemplate item in allItems)
								{
									if (GameServer.Database.UpdateInCache<DbItemTemplate>(item.Id_nb))
									{
										count++;
									}
								}
								Log.DebugFormat("{0} items updated or added to the ItemTemplate cache.", count);
								DisplayMessage(client, T(client, "GMCommands.Item.Load.CountUpdatedOrAdded", count), new object[] { });
							}
							break;
						}
						#endregion Load
						#region LoadPackage
					case "loadpackage":
						{
							if (args[2] != string.Empty)
							{
								if (args[2] == "**all**") args[2] = String.Empty;

								var packageItems = DOLDB<DbItemTemplate>.SelectObjects(DB.Column("PackageID").IsEqualTo(args[2]));

								if (packageItems != null)
								{
									int count = 0;

									foreach (DbItemTemplate item in packageItems)
									{
										if (GameServer.Database.UpdateInCache<DbItemTemplate>(item.Id_nb))
										{
											count++;
										}
									}

									Log.DebugFormat("{0} items updated or added to the ItemTemplate cache.", count);
									DisplayMessage(client, T(client, "GMCommands.Item.Load.CountUpdatedOrAdded", count), new object[] { });
								}
								else
								{
									DisplayMessage(client, T(client, "GMCommands.Item.LoadPackage.NoItemsFound", args[2]), new object[] { });
								}
							}
							break;
						}
						#endregion LoadPackage
						#region LoadSpells
					case "loadspells":
						{
							int slot = (int)eInventorySlot.LastBackpack;
							if (args.Length >= 4)
							{
								try
								{
									slot = Convert.ToInt32(args[3]);
								}
								catch
								{
									slot = (int)eInventorySlot.LastBackpack;
								}
							}
							DbInventoryItem item = client.Player.Inventory.GetItem((eInventorySlot)slot);
							if (item == null)
							{
								client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.Count.NoItemInSlot", slot), eChatType.CT_System, eChatLoc.CL_SystemWindow);
								return;
							}

							LoadSpell(client, item.SpellID);
							LoadSpell(client, item.SpellID1);
							LoadSpell(client, item.ProcSpellID);
							LoadSpell(client, item.ProcSpellID1);
							break;
						}
						#endregion LoadSpells
				}
			}
			catch
			{
				DisplaySyntax(client);
			}
		}

		private void UpdateAllowed(DbInventoryItem item, GameClient client)
		{
			if (item.Template is DbItemUnique)
			{
				DisplayMessage(client, T(client, "GMCommands.Item.UpdateAllowed.ItemTemplateOnly"));
				return;
			}
			else
			{
				(item.Template as DbItemTemplate).AllowUpdate = true;
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.UpdateAllowed.SourceTemplateWarning", item.Template.Id_nb), eChatType.CT_Staff, eChatLoc.CL_SystemWindow);
				DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Item.UpdateAllowed.SourceTemplateWarning", item.Template.Id_nb));
			}
		}

		private void LoadSpell(GameClient client, int spellID)
		{
			if (spellID != 0)
			{
				if (SkillBase.UpdateSpell(spellID))
				{
					Log.DebugFormat("Spell ID {0} added / updated in the global spell list", spellID);
					DisplayMessage(client, T(client, "GMCommands.Item.LoadSpells.UpdatedOrAdded", spellID), new object[] { });
				}
			}
		}
	}
}
