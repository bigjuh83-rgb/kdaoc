/*
 *  Script by clait
 *
 *  This NPC will level the player to 10, 20, 30, 40 or 50
 *
 */

using System;
using DOL;
using DOL.GS;
using DOL.Events;
using DOL.GS.PacketHandler;
using System.Reflection;
using System.Collections;
using System.Collections.Generic;
using DOL.Database;
using DOL.Language;


namespace DOL.GS.Scripts
{

    public class InstantLevelNPC : GameNPC
    {
        private static new readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);

		public override bool AddToWorld()
		{
			Name = "Free Levels";
            Model = 1198;
            Size = 70;
			Flags |= eFlags.PEACE;
			Level = 75;

			return base.AddToWorld();
		}

        [ScriptLoadedEvent]
        public static void ScriptLoaded(DOLEvent e, object sender, EventArgs args)
        {
            if (log.IsInfoEnabled)
                log.Info("InstantLevelNPC is loading...");
		}
        public void SendReply(GamePlayer player, string msg)
        {
            player.Out.SendMessage(msg, eChatType.CT_System, eChatLoc.CL_PopupWindow);
        }
        public override bool Interact(GamePlayer player)
        {
            if (!base.Interact(player))
                return false;

            player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "InstantLevelNPC.Interact.Menu", player.Name), eChatType.CT_Say, eChatLoc.CL_PopupWindow);

            return true;
        }

        public override bool WhisperReceive(GameLiving source, string str)
        {
            if (!base.WhisperReceive(source, str))
                return false;

            GamePlayer player = source as GamePlayer;

            if (player == null)
                return false;

            switch(str)
            {
                case "10":
                    if (player.Level >= 10) {
                       player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "InstantLevelNPC.LevelAlreadyHigher"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
                       return false;
                    }
                    else {
                        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "InstantLevelNPC.LevelGranted", 10), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
                        player.Level = 10;
                        return true;
                    }
                case "20":
                    if (player.Level >= 20) {
                       player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "InstantLevelNPC.LevelAlreadyHigher"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
                       return false;
                    }
                    else {
                        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "InstantLevelNPC.LevelGranted", 20), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
                        player.Level = 20;
                        return true;
                    }
                case "30":
                    if (player.Level >= 30) {
                       player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "InstantLevelNPC.LevelAlreadyHigher"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
                       return false;
                    }
                    else {
                        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "InstantLevelNPC.LevelGranted", 30), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
                        player.Level = 30;
                        return true;
                    }
                case "40":
                    if (player.Level >= 40) {
                       player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "InstantLevelNPC.LevelAlreadyHigher"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
                       return false;
                    }
                    else {
                        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "InstantLevelNPC.LevelGranted", 40), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
                        player.Level = 40;
                        return true;
                    }
                case "50":
                    if (player.Level >= 50) {
                       player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "InstantLevelNPC.LevelAlreadyHigher"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
                       return false;
                    }
                    else {
                        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "InstantLevelNPC.LevelGranted", 50), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
                        player.Level = 50;
                        return true;
                    }
	                case "reset":
	                case "초기화":
                    player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "InstantLevelNPC.LevelReset"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
                    player.Level = 1;
                    return true;

                default:
                    return false;

                return true;
            }
        }

    }
}
