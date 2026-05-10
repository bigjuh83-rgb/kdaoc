using System;
using System.Collections.Generic;
using System.Reflection;
using DOL.GS.PacketHandler;

namespace DOL.GS.Commands
{
	[CmdAttribute("&object", //command to handle
	              ePrivLevel.GM, //minimum privelege level
	              "Various Object commands!", //command description
	              //usage
	              "'/object info' to get information about the object",
	              "'/object movehere' to move object to your location",
	              "'/object create [ObjectClassName]' to create a default object",
	              "'/object fastcreate [name] [modelID]' to create the specified object",
	              "'/object model <newModel>' to set the model to newModel",
	              "'/object modelinc' Increment the object model by 1",
	              "'/object modeldec' Decrement the object model by 1",
	              "'/object emblem <newEmblem>' to set the emblem to newEmblem",
	              "'/object realm <0/1/2/3>' to set the targeted object realm",
	              "'/object name <newName>' to set the targeted object name to newName",
	              "'/object noname' to remove the targeted object name",
	              "'/object respawn <seconds>' to set a respawn time if this object is removed from the world",
	               "'/object remove' to remove the targeted object",
	              "'/object copy' to copy the targeted object",
	              "'/object save' to save the object",
	              "'/object target' to automatically target the nearest object",
	              "'/object quests' to load any dataquests associated with the target object")]
	public class ObjectCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
			if (args.Length == 1)
			{
				DisplaySyntax(client);
				return;
			}
			string param = string.Empty;
			if (args.Length > 2)
				param = String.Join(" ", args, 2, args.Length - 2);

			GameStaticItem targetObject = client.Player.TargetObject as GameStaticItem;

			if (targetObject == null && args[1] != "create" && args[1] != "fastcreate" && args[1] != "target" && args[1] != "quests")
			{
				client.Out.SendMessage(T(client, "GMCommands.Object.CommandOverview"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
				return;
			}

			switch (args[1])
			{
				case "info":
					{
						List<string> info = new List<string>();

						string name = T(client, "GMCommands.Object.Info.BlankName");
						if (!string.IsNullOrEmpty(targetObject.Name))
							name = targetObject.Name;

						info.Add(T(client, "GMCommands.Object.Info.OID", targetObject.ObjectID));
						info.Add(T(client, "GMCommands.Object.Info.Type", targetObject.GetType()));
						info.Add(" ");
						info.Add(T(client, "GMCommands.Object.Info.Name", name));
						info.Add(T(client, "GMCommands.Object.Info.Model", targetObject.Model));
						info.Add(T(client, "GMCommands.Object.Info.Emblem", targetObject.Emblem));
						info.Add(T(client, "GMCommands.Object.Info.Realm", targetObject.Realm));

						if (targetObject is GameStaticItemTimed staticItem && staticItem.Owners.Count > 0)
						{
							info.Add(" ");

							foreach (IGameStaticItemOwner owner in staticItem.Owners)
								info.Add(T(client, "GMCommands.Object.Info.Owner", owner.Name));
						}

						if (string.IsNullOrEmpty(targetObject.OwnerID) == false)
						{
							info.Add(" ");
							info.Add(T(client, "GMCommands.Object.Info.OwnerID", targetObject.OwnerID));
						}
						if (targetObject.RespawnInterval > 0)
						{
							info.Add(T(client, "GMCommands.Object.Info.RespawnInterval", targetObject.RespawnInterval));
						}

						info.Add(" ");

						WorldInventoryItem invItem = targetObject as WorldInventoryItem;
						if( invItem != null )
						{
							info.Add(T(client, "GMCommands.Object.Info.Count", invItem.Item.Count));
						}

						info.Add(" ");
						info.Add(T(client, "GMCommands.Object.Info.Location", targetObject.X, targetObject.Y, targetObject.Z));

						client.Out.SendCustomTextWindow( "[ " + name + " ]", info );
						break;
					}
				case "movehere":
					{
						targetObject.X = client.Player.X;
						targetObject.Y = client.Player.Y;
						targetObject.Z = client.Player.Z;
						targetObject.Heading = client.Player.Heading;
						targetObject.SaveIntoDatabase();
						break;
					}
				case "create":
					{
						string theType = "DOL.GS.GameStaticItem";
						if (args.Length > 2)
							theType = args[2];

						GameStaticItem obj = CreateItem( client, theType );

						if( obj != null )
							DisplayMessage(client, T(client, "GMCommands.Object.Created", obj.ObjectID));

						break;
					}
				case "fastcreate":
					{
						string objName = "new object";
						ushort modelID = 100;

						if ( args.Length > 2 )
							objName = args[2];

						if ( args.Length > 3 )
							ushort.TryParse( args[3], out modelID );

						GameStaticItem obj = CreateItem( client, null );

						if ( obj != null )
						{
							obj.Name = objName;
							obj.Model = modelID;
							DisplayMessage(client, T(client, "GMCommands.Object.CreatedWithSpaces", obj.ObjectID));
						}

						break;
					}
				case "model":
					{
						ushort model;
						try
						{
							model = Convert.ToUInt16(args[2]);
							targetObject.Model = model;
							targetObject.SaveIntoDatabase();
							DisplayMessage(client, T(client, "GMCommands.Object.ModelChanged", targetObject.Model));
						}
						catch (Exception)
						{
							DisplayMessage(client, T(client, "GMCommands.Object.CommandOverview"));
							return;
						}
						break;
					}
				case "modelinc":
					{
						ushort model = targetObject.Model;
						try
						{
							if (model < 4249)
							{
							model++;
							targetObject.Model = model;
							targetObject.SaveIntoDatabase();
							DisplayMessage(client, T(client, "GMCommands.Object.ModelChanged", targetObject.Model));
							}
							else
							{
								DisplayMessage(client, T(client, "GMCommands.Object.HighestModelReached"));
							}
						}
						catch (Exception)
						{
							DisplayMessage(client, T(client, "GMCommands.Object.CommandOverview"));
							return;
						}
						break;
					}
				case "modeldec":
					{
						ushort model = targetObject.Model;
						try
						{
							if (model != 1)
							{
								model--;
								targetObject.Model = model;
								targetObject.SaveIntoDatabase();
								DisplayMessage(client, T(client, "GMCommands.Object.ModelChanged", targetObject.Model));
							}
							else
							{
								DisplayMessage(client, T(client, "GMCommands.Object.ModelCannotBeZero"));
							}
						}
						catch (Exception)
						{
							DisplayMessage(client, T(client, "GMCommands.Object.CommandOverview"));
							return;
						}
						break;
					}
				case "emblem":
					{
						int emblem;
						try
						{
							emblem = Convert.ToInt32(args[2]);
							targetObject.Emblem = emblem;
							targetObject.SaveIntoDatabase();
							DisplayMessage(client, T(client, "GMCommands.Object.EmblemChanged", targetObject.Emblem));
						}
						catch (Exception)
						{
							DisplayMessage(client, T(client, "GMCommands.Object.CommandOverview"));
							return;
						}
						break;
					}
				case "realm":
					{
						eRealm realm = eRealm.None;
						if (args[2] == "0") realm = eRealm.None;
						if (args[2] == "1") realm = eRealm.Albion;
						if (args[2] == "2") realm = eRealm.Midgard;
						if (args[2] == "3") realm = eRealm.Hibernia;
						targetObject.Realm = realm;
						targetObject.SaveIntoDatabase();
						DisplayMessage(client, T(client, "GMCommands.Object.RealmChanged", targetObject.Realm));

						break;
					}
				case "name":
					{
						if (param != string.Empty)
						{
							targetObject.Name = param;
							targetObject.SaveIntoDatabase();
							DisplayMessage(client, T(client, "GMCommands.Object.NameChanged", targetObject.Name));
						}
						break;
					}
				case "noname":
					{
						targetObject.Name = string.Empty;
						targetObject.SaveIntoDatabase();
						DisplayMessage(client, T(client, "GMCommands.Object.NameRemoved"));
						break;
					}
				case "copy":
					{
						GameStaticItem item = CreateItemInstance(client, targetObject.GetType().FullName);
						if (item == null)
						{
							ChatUtil.SendSystemMessage(client, T(client, "GMCommands.Object.CreateInstanceError", targetObject.GetType().FullName));
							return;
						}
						item.X = client.Player.X;
						item.Y = client.Player.Y;
						item.Z = client.Player.Z;
						item.CurrentRegion = client.Player.CurrentRegion;
						item.Heading = client.Player.Heading;
						item.Level = targetObject.Level;
						item.Name = targetObject.Name;
						item.Model = targetObject.Model;
						item.Realm = targetObject.Realm;
						item.Emblem = targetObject.Emblem;
						item.LoadedFromScript = targetObject.LoadedFromScript;
						item.AddToWorld();
						item.SaveIntoDatabase();
						DisplayMessage(client, T(client, "GMCommands.Object.Created", item.ObjectID));
						break;
					}
				case "save":
					{
						targetObject.LoadedFromScript = false;
						targetObject.SaveIntoDatabase();
						DisplayMessage(client, T(client, "GMCommands.Object.SavedToDatabase"));
						break;
					}
				case "remove":
					{
						targetObject.DeleteFromDatabase();
						targetObject.Delete();
						DisplayMessage(client, T(client, "GMCommands.Object.RemovedFromClientsAndDatabase"));
						break;
					}
				case "target":
					{
						foreach ( GameStaticItem item in client.Player.GetItemsInRadius( 1000 ) )
						{
							client.Player.TargetObject = item;
							DisplayMessage(client, T(client, "GMCommands.Object.TargetSetToNearest"));
							return;
						}

						DisplayMessage(client, T(client, "GMCommands.Object.NoObjectsInRange", 1000));
						break;
					}
				case "respawn":
					{
						int respawn = 0;
						if (int.TryParse(args[2], out respawn))
						{
							targetObject.RespawnInterval = respawn;
							targetObject.SaveIntoDatabase();
							DisplayMessage(client, T(client, "GMCommands.Object.RespawnIntervalSet", targetObject.RespawnInterval));
						}

						break;
					}
				case "quests":
					{
						try
						{
							GameObject.FillDataQuestCache();
							client.Player.TargetObject.LoadDataQuests();

							if (client.Player.TargetObject is GameNPC)
							{
								foreach (GamePlayer player in client.Player.TargetObject.GetPlayersInRadius(WorldMgr.VISIBILITY_DISTANCE))
								{
									player.Out.SendNPCsQuestEffect(client.Player.TargetObject as GameNPC, (client.Player.TargetObject as GameNPC).GetQuestIndicator(player));
								}
							}

							client.Out.SendMessage(T(client, "GMCommands.Object.DataQuestsLoaded", targetObject.DataQuestList.Count), eChatType.CT_System, eChatLoc.CL_SystemWindow);
						}
						catch (Exception)
						{
							DisplayMessage(client, T(client, "GMCommands.Object.RefreshQuestsError"));
						}

						break;
					}
			}
		}

		GameStaticItem CreateItemInstance(GameClient client, string itemClassName)
		{
			GameStaticItem obj = null;

			foreach (Assembly script in ScriptMgr.GameServerScripts)
			{
				try
				{
					client.Out.SendDebugMessage(script.FullName);
					obj = (GameStaticItem)script.CreateInstance(itemClassName, false);

					if (obj != null)
						break;
				}
				catch (Exception e)
				{
					DisplayMessage(client, e.ToString());
				}
			}
			return obj;
		}

		GameStaticItem CreateItem(GameClient client, string itemClassName)
		{
			GameStaticItem obj;

			if (!string.IsNullOrEmpty(itemClassName))
				obj = CreateItemInstance(client, itemClassName);
			else
				obj = new GameStaticItem();


			if (obj == null)
			{
				client.Out.SendMessage(T(client, "GMCommands.Object.CreateInstanceError", itemClassName), eChatType.CT_System, eChatLoc.CL_SystemWindow);
				return null;
			}

			//Fill the object variables
			obj.LoadedFromScript = false;
			obj.X = client.Player.X;
			obj.Y = client.Player.Y;
			obj.Z = client.Player.Z;
			obj.CurrentRegion = client.Player.CurrentRegion;
			obj.Heading = client.Player.Heading;
			obj.Name = "New Object";
			obj.Model = 100;
			obj.Emblem = 0;
			obj.Realm = 0;
			obj.AddToWorld();
			obj.SaveIntoDatabase();

			return obj;
		}
	}
}
