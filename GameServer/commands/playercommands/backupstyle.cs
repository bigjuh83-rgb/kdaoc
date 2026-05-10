using DOL.GS.PacketHandler;
using DOL.GS.ServerProperties;
using DOL.Language;

namespace DOL.GS.Commands
{
    [CmdAttribute("&backupstyle", ePrivLevel.Player, "Modify automatic backup style.", "/backupstyle <set | clear>")]
    public class BackupStyleCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (IsSpammingCommand(client.Player, "backupstyle"))
                return;

            if (!Properties.ALLOW_AUTO_BACKUP_STYLES)
            {
                client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.BackupStyle.Disabled"), eChatType.CT_SpellResisted, eChatLoc.CL_SystemWindow);
                return;
            }

            if (args.Length < 2)
            {
                DisplaySyntax(client);
                return;
            }

            switch (args[1])
            {
                case "set":
                {
                    client.Player.styleComponent.AwaitingBackupInput = true;
                    client.Player.styleComponent.AutomaticBackupStyle = null;

                    if (Properties.ALLOW_NON_ANYTIME_BACKUP_STYLES)
                        client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.BackupStyle.NextStyle"), eChatType.CT_SpellResisted, eChatLoc.CL_SystemWindow);
                    else
                        client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.BackupStyle.NextAnytimeStyle"), eChatType.CT_SpellResisted, eChatLoc.CL_SystemWindow);

                    break;
                }
                case "clear":
                {
                    client.Player.styleComponent.AutomaticBackupStyle = null;
                    client.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.BackupStyle.Cleared"), eChatType.CT_SpellResisted, eChatLoc.CL_SystemWindow);
                    break;
                }
                default:
                {
                    DisplaySyntax(client);
                    return;
                }
            }
        }
    }
}
