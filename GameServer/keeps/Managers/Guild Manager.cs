using System;

using DOL.Database;
using DOL.GS;
using DOL.GS.PacketHandler;

namespace DOL.GS.Keeps
{
	/// <summary>
	/// Class to manage all the dealings with Guilds
	/// </summary>
	public class KeepGuildMgr
	{
		/// <summary>
		/// Sends a message to the guild informing them that a door has been destroyed
		/// </summary>
		/// <param name="door">The door object</param>
		public static void SendDoorDestroyedMessage(GameKeepDoor door)
		{
			door.Component.Keep.Guild?.SendTranslatedMessageToGuildMembers("Keep.GuildManager.DoorDestroyed", eChatType.CT_Guild, eChatLoc.CL_ChatWindow, door.Name, door.Component.Keep.Name);
		}

		/// <summary>
		/// Send message to a guild
		/// </summary>
		/// <param name="message">The message</param>
		/// <param name="guild">The guild</param>
		public static void SendMessageToGuild(string message, Guild guild)
		{
			if (guild == null)
				return;

			message = "[Guild] [" + message +"]";
			guild.SendMessageToGuildMembers(message, eChatType.CT_Guild, eChatLoc.CL_ChatWindow);
		}

		public static void SendLevelChangeMessage(AbstractGameKeep keep)
		{
			if (keep.Level != ServerProperties.Properties.MAX_KEEP_LEVEL)
				keep.Guild?.SendTranslatedMessageToGuildMembers("Keep.GuildManager.KeepLevelNowProgress", eChatType.CT_Guild, eChatLoc.CL_ChatWindow, keep.Name, keep.Level, ServerProperties.Properties.MAX_KEEP_LEVEL);
			else
				keep.Guild?.SendTranslatedMessageToGuildMembers("Keep.GuildManager.KeepLevelNow", eChatType.CT_Guild, eChatLoc.CL_ChatWindow, keep.Name, keep.Level);
		}

		public static void SendChangeLevelTimeMessage(AbstractGameKeep keep)
		{
            string message;
            string changeleveltext = string.Empty;
            int nextlevel = 0;

            byte maxlevel = (byte)ServerProperties.Properties.MAX_KEEP_LEVEL;

            if (keep.Level < maxlevel)
            {
                changeleveltext = "upgrade";
                nextlevel = keep.Level + 1;
            }
            else if (keep.Level > maxlevel)
            {
                changeleveltext = "downgrade";
                nextlevel = keep.Level - 1;
            }
            else
            {
                return;
            }
				message = string.Empty;
				TimeSpan time = keep.ChangeLevelTimeRemaining;
				if (time.Hours > 0)
					message += time.Hours + " hour(s) ";
				if (time.Minutes > 0)
					message += time.Minutes + " minute(s)";
				else message += time.Seconds + " second(s)";
				string translationId = changeleveltext == "upgrade" ? "Keep.GuildManager.LevelChangeStartedUpgrade" : "Keep.GuildManager.LevelChangeStartedDowngrade";
				keep.Guild?.SendTranslatedMessageToGuildMembers(translationId, eChatType.CT_Guild, eChatLoc.CL_ChatWindow, keep.Name, maxlevel, message);
			}
		}
}
