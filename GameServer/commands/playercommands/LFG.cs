using DOL.GS.PacketHandler;
using DOL.GS.Scripts.discord;
using DOL.GS.ServerProperties;
using DOL.Language;

namespace DOL.GS.Commands
{
    [CmdAttribute(
         "&lfg",
         ePrivLevel.Player,
         "같은 지역의 다른 플레이어에게 파티 찾기 메시지를 방송합니다.",
         "/lfg <메시지>")]
    public class LFGCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        private const string LFG_TIMEOUT_KEY = "lastLFGTick";

        public void OnCommand(GameClient client, string[] args)
        {
            if (args.Length < 2)
            {
                DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Broadcast.NoText"));
                return;
            }

            if (client.Player.IsMuted)
            {
                client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Broadcast.Muted"), eChatType.CT_Staff, eChatLoc.CL_SystemWindow);
                return;
            }

            string message = string.Join(" ", args, 1, args.Length - 1);
            long lastLfgTick = client.Player.TempProperties.GetProperty<long>(LFG_TIMEOUT_KEY);
            int slowModeLength = Properties.LFG_SLOWMODE_LENGTH * 1000;

            if ((GameLoop.GameLoopTime - lastLfgTick) < slowModeLength && client.Account.PrivLevel == 1) // 60 secs
            {
                // Message: You must wait {0} seconds before using this command again.
                ChatUtil.SendSystemMessage(client, "PLCommands.LFG.List.Wait", Properties.LFG_SLOWMODE_LENGTH - (GameLoop.GameLoopTime - lastLfgTick) / 1000);
                return;
            }

            Broadcast(client.Player, message);
        }

        private static void Broadcast(GamePlayer player, string message)
        {
            foreach (GamePlayer otherPlayer in ClientService.Instance.GetPlayersForRealmWideChatMessage(player))
                otherPlayer.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "Scripts.Players.LFG.Message", $"{player.Name} ({player.Level}, {player.CharacterClass.Name})", message), eChatType.CT_LookingForGroup, eChatLoc.CL_ChatWindow);

            if (Properties.DISCORD_ACTIVE)
                WebhookMessage.LogChatMessage(player, eChatType.CT_LookingForGroup, message);

            if (player.Client.Account.PrivLevel == 1)
                player.Client.Player.TempProperties.SetProperty(LFG_TIMEOUT_KEY, GameLoop.GameLoopTime);
        }
    }
}
