using System;
using DOL.Database;
using DOL.GS.PacketHandler;
using DOL.GS.Keeps;
using DOL.Language;

namespace DOL.GS.Commands
{
    /// <summary>
    /// A command to manage teleport destinations.
    /// </summary>
    /// <author>Shursan</author>
    [CmdAttribute(
        "&keepdoorteleport",
        ePrivLevel.Admin,
        "Manage keepdoor teleport destinations",
        "'/keepdoorteleport add <enter|exit> <in|out> add a teleport destination"/*,
        "'/keepdoorteleport reload' reload all teleport locations from the db"*/)]
    public class KeepDoorTeleportCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        private static readonly Logging.Logger log = Logging.LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);

        /// <summary>
        /// Handle command.
        /// </summary>
        /// <param name="client"></param>
        /// <param name="args"></param>
        public void OnCommand(GameClient client, string[] args)
        {
            if (args.Length < 4)
            {
                DisplaySyntax(client);
                return;
            }

            switch (args[1].ToLower())
            {
                case "add":
                {
                        var npcString = args[2].ToLowerInvariant();
                        if (npcString == string.Empty)
                        {
                            client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "AdminCommands.KeepDoorTeleport.MustSpecifyString"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        if (!IsValidTeleportText(npcString))
                        {
                            client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "AdminCommands.KeepDoorTeleport.ValidStrings"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        var teleportDirection = args[3].ToLowerInvariant();
                        if (teleportDirection == string.Empty)
                        {
                            client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "AdminCommands.KeepDoorTeleport.MustSpecifyType"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        if (!IsValidTeleportDirection(teleportDirection))
                        {
                            client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "AdminCommands.KeepDoorTeleport.ValidTypes"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        var teleportType = string.Empty;
                        if (teleportDirection == "in")
                        {
                            teleportType = "GateKeeperIn";
                        }
                        else
                        {
                            teleportType = "GateKeeperOut";
                        }

                        var keep = GameServer.KeepManager.GetClosestKeepToSpot(client.Player.CurrentRegionID, client.Player, WorldMgr.VISIBILITY_DISTANCE);
                        if (keep == null)
                        {
                            client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "AdminCommands.KeepDoorTeleport.NeedKeepArea"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                            return;
                        }

                        AddTeleport(client, npcString, keep, teleportType);
                    }
                    break;

                case "reload":

                    var results = WorldMgr.LoadTeleports();
                    log.Info(results);
                    client.Out.SendMessage(results, eChatType.CT_System, eChatLoc.CL_SystemWindow);

                    break;

                default:
                    DisplaySyntax(client);
                    break;
            }
        }

        private static bool IsValidTeleportText(string text)
        {
            return text == "enter" || text == "exit";
        }

        private static bool IsValidTeleportDirection(string direction)
        {
            return direction == "in" || direction == "out";
        }

        /// <summary>
        /// Add a new teleport destination in memory and save to database, if
        /// successful.
        /// </summary>
        /// <param name="client"></param>
        /// <param name="teleportID"></param>
        /// <param name="type"></param>
        private void AddTeleport(GameClient client, String Text, AbstractGameKeep keep, string teleportType)
        {
            GamePlayer player = client.Player;

            var verification = GameServer.Database.SelectObject<DbKeepDoorTeleport>(DB.Column("KeepID").IsEqualTo(keep.KeepID).And(DB.Column("Text").IsEqualTo(Text).And(DB.Column("Type").IsEqualTo(teleportType))));
            if (verification != null)
            {
                client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "AdminCommands.KeepDoorTeleport.AlreadyExists"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }
            DbKeepDoorTeleport teleport = new DbKeepDoorTeleport();
            teleport.Text = Text;
            teleport.Region = player.CurrentRegion.ID;
            teleport.X = player.X;
            teleport.Y = player.Y;
            teleport.Z = player.Z;
            teleport.Heading = player.Heading;
            teleport.KeepID = keep.KeepID;
            teleport.CreateInfo = keep.Name;
            teleport.TeleportType = teleportType;

            GameServer.Database.AddObject(teleport);
            client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "AdminCommands.KeepDoorTeleport.Added", Text),
                eChatType.CT_System, eChatLoc.CL_SystemWindow);
        }
    }
}
