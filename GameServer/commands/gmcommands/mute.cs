using System;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands
{
	[Cmd(
		"&mute",
		ePrivLevel.GM,
		"Command to mute annoying players.  Player mutes are temporary, allchars are set on an account and must be removed.",
		"/mute <playername or #ClientID> - example /mute #24  to mute player on client id 24",
		"/mute <playername or #ClientID> allchars - this applies an account mute to this player",
		"/mute <playername or #ClientID> remove - remove all mutes from this players account")]
	public class MuteCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		private static readonly Logging.Logger log = Logging.LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);

		public void OnCommand(GameClient client, string[] args)
		{
			if (args.Length < 2)
			{
				DisplaySyntax(client);
				return;
			}

			GameClient playerClient = null;

			if (args[1].StartsWith("#"))
			{
				try
				{
					int sessionID = Convert.ToInt32(args[1][1..]);
					playerClient = ClientService.Instance.GetClientBySessionId(sessionID);
				}
				catch
				{
					DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Mute.InvalidClientID"));
				}
			}
			else
			{
				playerClient = ClientService.Instance.GetPlayerByExactName(args[1])?.Client;
			}

			if (playerClient == null)
			{
				DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Mute.NoPlayerFound", args[1]));
				return;
			}

			if (client.Account.PrivLevel < playerClient.Account.PrivLevel)
			{
				DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Mute.PrivLevelTooLow"));
				return;
			}

			bool mutedAccount = false;

			if (args.Length > 2 && (args[2].ToLower() == "account" || args[2].ToLower() == "allchars"))
			{
				if (playerClient != null)
				{
					playerClient.Account.IsMuted = true;
					playerClient.Player.IsMuted = true;
					GameServer.Database.SaveObject(playerClient.Account);
					mutedAccount = true;
				}
			}
			else if (args.Length > 2 && args[2].ToLower() == "remove")
			{
				if (playerClient != null)
				{
					playerClient.Account.IsMuted = false;
					playerClient.Player.IsMuted = false;
					GameServer.Database.SaveObject(playerClient.Account);
					mutedAccount = true;
				}
			}
			else
			{
				if (playerClient != null)
				{
					if (playerClient.Account.IsMuted)
					{
						DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Mute.AllCharsMuteMustBeRemoved"));
						return;
					}

					playerClient.Player.IsMuted = !playerClient.Player.IsMuted;
				}
			}

			if (playerClient.Player.IsMuted)
			{
				playerClient.Player.Out.SendMessage(LanguageMgr.GetTranslation(playerClient.Account.Language, "GMCommands.Mute.YouHaveBeenMuted", client.Player.Name), eChatType.CT_Staff, eChatLoc.CL_SystemWindow);
				client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Mute.YouMutedPlayer", playerClient.Player.Name), eChatType.CT_Staff, eChatLoc.CL_SystemWindow);
				if (mutedAccount)
				{
					playerClient.Player.Out.SendMessage(LanguageMgr.GetTranslation(playerClient.Account.Language, "GMCommands.Mute.AccountMutePlaced"), eChatType.CT_Staff, eChatLoc.CL_SystemWindow);
					client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Mute.ActionDoneToAccount"), eChatType.CT_Staff, eChatLoc.CL_SystemWindow);
				}

				log.Warn(client.Player.Name + " muted " + playerClient.Player.Name);
			}
			else
			{
				playerClient.Player.Out.SendMessage(LanguageMgr.GetTranslation(playerClient.Account.Language, "GMCommands.Mute.YouHaveBeenUnmuted", client.Player.Name), eChatType.CT_Staff, eChatLoc.CL_SystemWindow);
				client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Mute.YouUnmutedPlayer", playerClient.Player.Name), eChatType.CT_Staff, eChatLoc.CL_SystemWindow);
				if (mutedAccount)
				{
					client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "GMCommands.Mute.ActionDoneToAccount"), eChatType.CT_Staff, eChatLoc.CL_SystemWindow);
				}

				log.Warn(client.Player.Name + " un-muted " + playerClient.Player.Name);
			}
			return;
		}
	}
}
