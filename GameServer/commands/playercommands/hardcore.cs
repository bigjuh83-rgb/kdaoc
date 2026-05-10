using System;
using System.Reflection;
using DOL.Events;
using DOL.GS.PacketHandler;
using DOL.GS.PacketHandler.Client.v168;
using DOL.GS.PlayerTitles;
using DOL.Language;
using DOL.Logging;

namespace DOL.GS
{
    public class HardCoreLogin
    {
        private static readonly Logger Log = LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);

        [GameServerStartedEvent]
        public static void OnServerStart(DOLEvent e, object sender, EventArgs arguments)
        {
            GameEventMgr.AddHandler(GamePlayerEvent.GameEntered, new DOLEventHandler(HCPlayerEntered));
        }

        [GameServerStoppedEvent]
        public static void OnServerStop(DOLEvent e, object sender, EventArgs arguments)
        {
            GameEventMgr.RemoveHandler(GamePlayerEvent.GameEntered, new DOLEventHandler(HCPlayerEntered));
        }

        public static void HandleDeath(GamePlayer player)
        {
            GameServiceUtils.KickPlayerToCharScreen(player);
            CharacterCreateRequestHandler.DeleteCharacter(player.Client, player.DBCharacter);
        }

        private static void HCPlayerEntered(DOLEvent e, object sender, EventArgs arguments)
        {
            if (sender is not GamePlayer player || !player.HCFlag || player.DeathCount == 0)
                return;

            if (Log.IsWarnEnabled)
                Log.Warn($"[HARDCORE] player {player.Name} has {player.DeathCount} deaths and has been removed from the database.");

            HandleDeath(player);
        }
    }
}

namespace DOL.GS.Commands
{
    [Cmd(
        "&hardcore",
        ePrivLevel.Player,
        "Flags a player as Hardcore. Dying after activating Hardcore will result in the character deletion.",
        "/hardcore on")]
    public class HardcoreCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (IsSpammingCommand(client.Player, "hardcore"))
                return;

            if (client.Player.RealmPoints > 0)
                return;

            if (client.Player.HCFlag)
            {
                client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Hardcore.AlreadyOn"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                return;
            }

            if (args.Length < 2)
            {
                DisplaySyntax(client);
                return;
            }

            if (!args[1].ToLower().Equals("on"))
                return;

            if (client.Player.Level != 1)
            {
                client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Hardcore.RequireLevelOne"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                return;
            }

            client.Out.SendCustomDialog(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Hardcore.Confirm"), new CustomDialogResponse(HardcoreResponseHandler));
        }

        protected virtual void HardcoreResponseHandler(GamePlayer player, byte response)
        {
            if (response == 1)
            {
                if (player.Level > 1)
                {
                    player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "Scripts.Players.Hardcore.RequireLevelOne"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                    return;
                }

                player.Emote(eEmote.StagFrenzy);
                player.HCFlag = true;
                player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "Scripts.Players.Hardcore.Enabled"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                player.CurrentTitle = new HardCoreTitle();
            }
            else
                player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "Scripts.Players.Hardcore.Cancelled"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
        }
    }
}

namespace DOL.GS.PlayerTitles
{
    public class HardCoreTitle : SimplePlayerTitle
    {
        public override string GetDescription(GamePlayer player)
        {
            return "Hardcore";
        }

        public override string GetValue(GamePlayer source, GamePlayer player)
        {
            return "Hardcore";
        }

        public override void OnTitleGained(GamePlayer player)
        {
            player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "Scripts.Players.Hardcore.TitleGained"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
        }

        public override bool IsSuitable(GamePlayer player)
        {
            return player.HCFlag || player.HCCompleted;
        }
    }
}
