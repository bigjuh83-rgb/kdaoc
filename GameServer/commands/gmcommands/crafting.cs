/*
 * DAWN OF LIGHT - The first free open source DAoC server emulator
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 *
 */
using System;
using System.Collections.Generic;
using DOL.GS.PacketHandler;
using DOL.Database;

namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&crafting",
		ePrivLevel.GM,
		"GMCommands.Crafting.Description",
		"GMCommands.Crafting.Usage.Add",
		"GMCommands.Crafting.Usage.Change",
		"GMCommands.Crafting.Usage.SalvageAdd",
		"GMCommands.Crafting.Usage.SalvageUpdate",
		"GMCommands.Crafting.Usage.SalvageInfo",
		"GMCommands.Crafting.Usage.List")]
	public class CraftCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
			if (args.Length < 2)
			{
				DisplaySyntax(client);
				return;
			}

			try
			{
				#region List
				if (args[1].ToLower() == "list")
				{
					List<string> list = new List<string>();
					int count = 0;
					foreach (int value in Enum.GetValues(typeof(eCraftingSkill)))
					{
						if (++count < 16) // get rid of duplicate due to _Last
							list.Add(value + " = " + Enum.GetName(typeof(eCraftingSkill), value));
					}

					client.Out.SendCustomTextWindow(T(client, "GMCommands.Crafting.SkillDescription"), list);
					return;
				}
				#endregion List

				#region Salvage

				if (args[1].ToLower() == "salvageinfo")
				{
					List<string> list = new List<string>();
					int salvageID = Convert.ToInt32(args[2]);
					DbSalvageYield salvage = GameServer.Database.FindObjectByKey<DbSalvageYield>(salvageID);

					if (salvage == null)
					{
						DisplayMessage(client, T(client, "GMCommands.Crafting.SalvageYieldNotFound"));
						return;
					}

					DbItemTemplate template = GameServer.Database.FindObjectByKey<DbItemTemplate>(salvage.MaterialId_nb);
					string materialName = T(client, "GMCommands.Crafting.NotFound");

					if (template != null)
					{
						materialName = template.Name;
					}

					list.Add(T(client, "GMCommands.Crafting.SalvageInfo.ID", salvageID));
					list.Add(T(client, "GMCommands.Crafting.SalvageInfo.ObjectType", salvage.ObjectType == 0 ? T(client, "GMCommands.Crafting.Unused") : salvage.ObjectType.ToString()));
					list.Add(T(client, "GMCommands.Crafting.SalvageInfo.SalvageLevel", salvage.SalvageLevel == 0 ? T(client, "GMCommands.Crafting.Unused") : salvage.SalvageLevel.ToString()));
					list.Add(T(client, "GMCommands.Crafting.SalvageInfo.Material", materialName, salvage.MaterialId_nb));
					list.Add(T(client, "GMCommands.Crafting.SalvageInfo.Count", salvage.Count == 0 ? T(client, "GMCommands.Crafting.Calculated") : salvage.Count.ToString()));
					list.Add(T(client, "GMCommands.Crafting.SalvageInfo.Realm", salvage.Realm == 0 ? T(client, "GMCommands.Crafting.Realm.Any") : GlobalConstants.RealmToName((eRealm)salvage.Realm)));
					list.Add(T(client, "GMCommands.Crafting.SalvageInfo.PackageID", salvage.PackageID));

					client.Out.SendCustomTextWindow(T(client, "GMCommands.Crafting.SalvageInfo.WindowTitle", salvageID), list);
					return;
				}

				if (args[1].ToLower() == "adjustprices")
				{
					var recipeIDs = new List<ushort>();
					var DBrecipes = GameServer.Database.SelectAllObjects<DbCraftedItem>();
					foreach (var dbrecipe in DBrecipes)
					{
						recipeIDs.Add(Convert.ToUInt16(dbrecipe.CraftedItemID));
					}

					foreach (var r in recipeIDs)
					{
						RecipeDB.FindBy(r);
					}

					return;
				}

				if (args[1].ToLower() == "salvageadd" || args[1].ToLower() == "salvageupdate")
				{
					try
					{
						int salvageID = Convert.ToInt32(args[2]);
						string material = args[3];
						int count = Convert.ToInt32(args[4]);
						byte realm = 0;
						string package = string.Empty;

						if (args.Length > 5)
							realm = Convert.ToByte(args[5]);

						if (args.Length > 6)
							package = args[6];

						DbItemTemplate template = GameServer.Database.FindObjectByKey<DbItemTemplate>(material);

						if (template == null)
						{
							DisplayMessage(client, T(client, "GMCommands.Crafting.MaterialNotFound", material));
							return;
						}

						DbSalvageYield salvage = GameServer.Database.FindObjectByKey<DbSalvageYield>(salvageID);

						if (args[1].ToLower() == "salvageadd")
						{
							if (salvage != null)
							{
								DisplayMessage(client, T(client, "GMCommands.Crafting.SalvageYieldAlreadyExists"));
								return;
							}

							salvage = new DbSalvageYield();
							if (salvageID > 0)
								salvage.ID = salvageID;

							salvage.MaterialId_nb = material;
							salvage.Count = Math.Max(1, count);
							salvage.Realm = realm;

							if (package == string.Empty)
							{
								package = client.Player.Name;
							}

							salvage.PackageID = package;

							GameServer.Database.AddObject(salvage);

							DisplayMessage(client, T(client, "GMCommands.Crafting.SalvageYieldCreated", salvage.ID, salvage.MaterialId_nb, salvage.Count, salvage.Realm, salvage.PackageID));
						}
						else
						{
							if (salvage == null)
							{
								DisplayMessage(client, T(client, "GMCommands.Crafting.SalvageIdNotFound"));
								return;
							}

							if (salvage.PackageID == DbSalvageYield.LEGACY_SALVAGE_ID)
							{
								DisplayMessage(client, T(client, "GMCommands.Crafting.SalvageYieldLegacyCannotUpdate"));
								return;
							}

							salvage.MaterialId_nb = material;
							salvage.Count = Math.Max(1, count);
							salvage.Realm = realm;

							if (string.IsNullOrEmpty(salvage.PackageID) && package == string.Empty)
							{
								package = client.Player.Name;
							}

							if (package != string.Empty)
							{
								salvage.PackageID = package;
							}

							GameServer.Database.SaveObject(salvage);

							DisplayMessage(client, T(client, "GMCommands.Crafting.SalvageYieldUpdated", salvage.ID, salvage.MaterialId_nb, salvage.Count, salvage.Realm, salvage.PackageID));
						}

					}
					catch
					{
						DisplaySyntax(client);
					}

					return;
				}

				#endregion Salvage

				GamePlayer target = null;
				if ((client.Player.TargetObject != null) && (client.Player.TargetObject is GamePlayer))
					target = client.Player.TargetObject as GamePlayer;
				else
				{
					DisplayMessage(client, T(client, "GMCommands.Crafting.NoPlayerTarget"));
					return;
				}

				switch (args[1].ToLower())
				{
					#region Add
					case "add":
						{
							eCraftingSkill craftingSkillID = eCraftingSkill.NoCrafting;
							int startLevel = 1;
							try
							{
								craftingSkillID = (eCraftingSkill)Convert.ToUInt16(args[2]);
								if (args.Length > 3)
									startLevel = Convert.ToUInt16(args[3]);

								AbstractCraftingSkill skill = CraftingMgr.getSkillbyEnum(craftingSkillID);
								if (skill == null)
								{
									DisplayMessage(client, T(client, "GMCommands.Crafting.InvalidSkill"));
								}
								else
								{
									if (target.AddCraftingSkill(craftingSkillID, startLevel))
									{
										target.Out.SendUpdateCraftingSkills();
										target.SaveIntoDatabase();
										DisplayMessage(client, T(client, "GMCommands.Crafting.SkillAdded", skill.Name));
									}
									else
									{
										DisplayMessage(client, T(client, "GMCommands.Crafting.AlreadyHaveSkill", target.Name, skill.Name));
									}
								}
							}
							catch (Exception)
							{
								DisplaySyntax(client);
							}
							break;
						}
					#endregion Add
					#region Change
					case "change":
						{
							eCraftingSkill craftingSkillID = eCraftingSkill.NoCrafting;
							int amount = 1;
							try
							{
								craftingSkillID = (eCraftingSkill)Convert.ToUInt16(args[2]);

								if (args.Length > 3)
								{
									amount = Convert.ToInt32(args[3]);
								}

								AbstractCraftingSkill skill = CraftingMgr.getSkillbyEnum(craftingSkillID);
								if (skill == null)
								{
									DisplayMessage(client, T(client, "GMCommands.Crafting.InvalidSkill"));
								}
								else
								{
									if (target.GetCraftingSkillValue(craftingSkillID) < 0)
									{
										DisplayMessage(client, T(client, "GMCommands.Crafting.NotHaveSkillAddIt", target.Name, skill.Name));
										return;
									}

									if (amount > 0)
									{
										target.GainCraftingSkill(craftingSkillID, amount);
									}
									else
									{
										target.CraftingSkills[craftingSkillID] += amount;
									}
									target.Out.SendUpdateCraftingSkills();
									target.SaveIntoDatabase();
									DisplayMessage(client, T(client, "GMCommands.Crafting.SkillChanged", skill.Name));
									DisplayMessage(client, T(client, "GMCommands.Crafting.NowHasSkillPoints", target.Name, target.GetCraftingSkillValue(craftingSkillID), (eCraftingSkill)craftingSkillID));
								}
							}
							catch (Exception)
							{
								DisplaySyntax(client);
								return;
							}
							break;
						}
					#endregion Change
					#region Default
					default:
						{
							DisplaySyntax(client);
							break;
						}
					#endregion Default
				}
			}
			catch
			{
				DisplaySyntax(client);
			}
		}
	}
}
