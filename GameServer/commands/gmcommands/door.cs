using System;
using System.Collections.Generic;
using DOL.Database;
using DOL.GS.PacketHandler;
using DOL.GS.PacketHandler.Client.v168;
using DOL.Language;

namespace DOL.GS.Commands
{
	[Cmd(
		"&door",
		ePrivLevel.GM,
		"GMCommands.Door.Description",
		"'/door show' toggle enable/disable add dialog when targeting doors",
		"GMCommands.Door.Add",
		"GMCommands.Door.Update",
		"GMCommands.Door.Delete",
		"GMCommands.Door.Name",
		"GMCommands.Door.Level",
		"GMCommands.Door.Realm",
		"GMCommands.Door.Guild",
		"'/door sound <soundid>'",
		"GMCommands.Door.Info",
		"GMCommands.Door.Heal",
		"GMCommands.Door.Locked",
		"GMCommands.Door.Unlocked")]
	public class NewDoorCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		private int DoorID;
		private int doorType;
		private string Realmname;
		private string statut;

		#region ICommandHandler Members

		public void OnCommand(GameClient client, string[] args)
		{
			GameDoor targetDoor = null;

			if (args.Length > 1 && args[1] == "show" && client.Player != null)
			{
				if (client.Player.TempProperties.GetProperty<bool>(DoorMgr.WANT_TO_ADD_DOORS))
				{
					client.Player.TempProperties.RemoveProperty(DoorMgr.WANT_TO_ADD_DOORS);
					client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.AddDialogDisabled"), eChatType.CT_System,
					                       eChatLoc.CL_SystemWindow);
				}
				else
				{
					client.Player.TempProperties.SetProperty(DoorMgr.WANT_TO_ADD_DOORS, true);
					client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.AddDialogEnabled"),
					                       eChatType.CT_System, eChatLoc.CL_SystemWindow);
				}

				return;
			}

			if (client.Player.CurrentRegion.IsInstance)
			{
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.CantAddInInstance"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
				return;
			}

			if (client.Player.TargetObject == null)
			{
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.MustTargetDoor"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
				return;
			}

			if (client.Player.TargetObject != null &&
			    (client.Player.TargetObject is GameNPC || client.Player.TargetObject is GamePlayer))
			{
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.MustTargetDoor"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
				return;
			}

			if (client.Player.TargetObject != null && client.Player.TargetObject is GameDoor)
			{
				targetDoor = (GameDoor) client.Player.TargetObject;
				DoorID = targetDoor.DoorId;
				doorType = targetDoor.DoorId/100000000;
			}

			if (args.Length < 2)
			{
				DisplaySyntax(client);
				return;
			}

			switch (args[1])
			{
				case "name":
					name(client, targetDoor, args);
					break;
				case "guild":
					guild(client, targetDoor, args);
					break;
				case "level":
					level(client, targetDoor, args);
					break;
				case "realm":
					realm(client, targetDoor, args);
					break;
				case "info":
					info(client, targetDoor);
					break;
				case "heal":
					heal(client, targetDoor);
					break;
				case "locked":
					locked(client, targetDoor);
					break;
				case "unlocked":
					unlocked(client, targetDoor);
					break;
				case "kill":
					kill(client, targetDoor, args);
					break;
				case "delete":
					delete(client, targetDoor);
					break;
				case "add":
					add(client, targetDoor);
					break;
				case "update":
					update(client, targetDoor);
					break;
				case "sound":
					sound(client, targetDoor, args);
					break;

				default:
					DisplaySyntax(client);
					return;
			}
		}

		#endregion

		private void add(GameClient client, GameDoor targetDoor)
		{
			var DOOR = DOLDB<DbDoor>.SelectObject(DB.Column("InternalID").IsEqualTo(DoorID));

			if (DOOR != null)
			{
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.AlreadyInDatabase"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
				return;
			}
			if (DOOR == null)
			{
				if (doorType != 7 && doorType != 9)
				{
					var door = new DbDoor();
					door.ObjectId = null;
					door.InternalID = DoorID;
					door.Name = "door";
					door.Type = DoorID/100000000;
					door.Level = 20;
					door.Realm = 6;
					door.X = targetDoor.X;
					door.Y = targetDoor.Y;
					door.Z = targetDoor.Z;
					door.Heading = targetDoor.Heading;
					door.Health = 2545;
					GameServer.Database.AddObject(door);
					targetDoor.LoadFromDatabase(door);
					DoorMgr.RegisterDoor(targetDoor);
					client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.AddedDoorId", DoorID), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
					return;
				}
			}
		}

		private void update(GameClient client, GameDoor targetDoor)
		{
			delete(client, targetDoor);

			if (targetDoor != null)
			{
				if (doorType != 7 && doorType != 9)
				{
					var door = new DbDoor();
					door.ObjectId = null;
					door.InternalID = DoorID;
					door.Name = "door";
					door.Type = DoorID/100000000;
					door.Level = targetDoor.Level;
					door.Realm = (byte) targetDoor.Realm;
					door.Health = targetDoor.Health;
					door.Locked = Convert.ToInt32(targetDoor.Locked);
					door.X = client.Player.X;
					door.Y = client.Player.Y;
					door.Z = client.Player.Z;
					door.Heading = client.Player.Heading;
					GameServer.Database.AddObject(door);
					targetDoor.LoadFromDatabase(door);
					DoorMgr.RegisterDoor(targetDoor);
					client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.AddedDoor", DoorID), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
					return;
				}
			}
		}

		private void delete(GameClient client, GameDoor targetDoor)
		{
			var dbDoor = DOLDB<DbDoor>.SelectObject(DB.Column("InternalID").IsEqualTo(DoorID));

			if (dbDoor != null)
			{
				GameServer.Database.DeleteObject(dbDoor);
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.Removed"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
			}
			else
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.NotInDatabase"), eChatType.CT_System, eChatLoc.CL_SystemWindow);

			DoorMgr.UnregisterDoor(DoorID);
			targetDoor.RemoveFromWorld();
		}

		private void name(GameClient client, GameDoor targetDoor, string[] args)
		{
			string doorName = string.Empty;

			if (args.Length > 2)
				doorName = String.Join(" ", args, 2, args.Length - 2);

			if (doorName != string.Empty)
			{
				targetDoor.Name = CheckName(doorName, client);
				targetDoor.SaveIntoDatabase();
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.NameChanged", targetDoor.Name), eChatType.CT_System,
				                       eChatLoc.CL_SystemWindow);
			}
			else
			{
				DisplaySyntax(client, args[1]);
			}
		}

		private void sound(GameClient client, GameDoor targetDoor, string[] args)
		{
			uint doorSound;

			try
			{
				if (args.Length > 2)
				{
					doorSound = Convert.ToUInt16(args[2]);
					targetDoor.Flag = doorSound;
					targetDoor.SaveIntoDatabase();
					client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.SoundSet", doorSound), eChatType.CT_System, eChatLoc.CL_SystemWindow);
				}
				else
				{
					DisplaySyntax(client, args[1]);
				}
			}
			catch
			{
				DisplaySyntax(client, args[1]);
			}
		}

		private void guild(GameClient client, GameDoor targetDoor, string[] args)
		{
			string guildName = string.Empty;

			if (args.Length > 2)
				guildName = String.Join(" ", args, 2, args.Length - 2);

			if (guildName != string.Empty)
			{
				targetDoor.GuildName = CheckGuildName(guildName, client);
				targetDoor.SaveIntoDatabase();
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.GuildChanged", targetDoor.GuildName), eChatType.CT_System,
				                       eChatLoc.CL_SystemWindow);
			}
			else
			{
				if (targetDoor.GuildName != string.Empty)
				{
					targetDoor.GuildName = string.Empty;
					targetDoor.SaveIntoDatabase();
					client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.GuildRemoved"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
				}
				else
					DisplaySyntax(client, args[1]);
			}
		}

		private void level(GameClient client, GameDoor targetDoor, string[] args)
		{
			byte level;

			try
			{
				level = Convert.ToByte(args[2]);
				targetDoor.Level = level;
				targetDoor.Health = targetDoor.MaxHealth;
				targetDoor.SaveIntoDatabase();
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.LevelChanged", targetDoor.Level), eChatType.CT_System,
				                       eChatLoc.CL_SystemWindow);
			}
			catch (Exception)
			{
				DisplaySyntax(client, args[1]);
			}
		}

		private void realm(GameClient client, GameDoor targetDoor, string[] args)
		{
			byte realm;

			try
			{
				realm = Convert.ToByte(args[2]);
				targetDoor.Realm = (eRealm) realm;
				targetDoor.SaveIntoDatabase();
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.RealmChanged", targetDoor.Realm), eChatType.CT_System,
				                       eChatLoc.CL_SystemWindow);
			}
			catch (Exception)
			{
				DisplaySyntax(client, args[1]);
			}
		}

		private void info(GameClient client, GameDoor targetDoor)
		{
			if (targetDoor.Realm == eRealm.None)
				Realmname = "None";
			else if (targetDoor.Realm == eRealm.Albion)
				Realmname = "Albion";
			else if (targetDoor.Realm == eRealm.Midgard)
				Realmname = "Midgard";
			else if (targetDoor.Realm == eRealm.Hibernia)
				Realmname = "Hibernia";
			else if (targetDoor.Realm == eRealm.Door)
				Realmname = "All";

			if (targetDoor.Locked)
				statut = " Locked";
			else
				statut = " Unlocked";

			int doorType = DoorRequestHandler.HandlerDoorId / 100000000;

			var info = new List<string>();

			info.Add(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.Info.DoorInfo", targetDoor.Name));
			info.Add("  ");
			info.Add(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.Info.Name", targetDoor.Name));
			info.Add(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.Info.ID", DoorID));
			info.Add(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.Info.Realm", (int) targetDoor.Realm, Realmname));
			info.Add(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.Info.Level", targetDoor.Level));
			info.Add(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.Info.Guild", targetDoor.GuildName));
			info.Add(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.Info.Health", targetDoor.Health, targetDoor.MaxHealth));
			info.Add(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.Info.Status", statut));
			info.Add(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.Info.Type", doorType));
			info.Add(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.Info.X", targetDoor.X));
			info.Add(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.Info.Y", targetDoor.Y));
			info.Add(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.Info.Z", targetDoor.Z));
			info.Add(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.Info.Heading", targetDoor.Heading));

			client.Out.SendCustomTextWindow(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.Info.WindowTitle"), info);
		}

		private void heal(GameClient client, GameDoor targetDoor)
		{
			targetDoor.Health = targetDoor.MaxHealth;
			targetDoor.SaveIntoDatabase();
			client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.HealthChanged", targetDoor.Health), eChatType.CT_System,
			                       eChatLoc.CL_SystemWindow);
		}

		private void locked(GameClient client, GameDoor targetDoor)
		{
			targetDoor.Locked = true;
			targetDoor.SaveIntoDatabase();
			client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.IsLocked", targetDoor.Name), eChatType.CT_System, eChatLoc.CL_SystemWindow);
		}

		private void unlocked(GameClient client, GameDoor targetDoor)
		{
			targetDoor.Locked = false;
			targetDoor.SaveIntoDatabase();
			client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.IsUnlocked", targetDoor.Name), eChatType.CT_System, eChatLoc.CL_SystemWindow);
		}

		private void kill(GameClient client, GameDoor targetDoor, string[] args)
		{
			try
			{
				lock (targetDoor.XpGainersLock)
				{
					targetDoor.AddXPGainer(client.Player, targetDoor.Health);
					targetDoor.Die(client.Player);
					client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.HealthReachedZero", targetDoor.Name), eChatType.CT_System,
										   eChatLoc.CL_SystemWindow);
				}
			}
			catch (Exception e)
			{
				client.Out.SendMessage(e.ToString(), eChatType.CT_System, eChatLoc.CL_SystemWindow);
			}
		}

		private string CheckName(string name, GameClient client)
		{
			if (name.Length > 47)
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.NameTooLong"), eChatType.CT_System,
				                       eChatLoc.CL_SystemWindow);
			return name;
		}

		private string CheckGuildName(string name, GameClient client)
		{
			if (name.Length > 47)
				client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Door.GuildNameTooLong", name.Length),
				                       eChatType.CT_System, eChatLoc.CL_SystemWindow);
			return name;
		}
	}
}
