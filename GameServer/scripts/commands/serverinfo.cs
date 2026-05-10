using System;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands
{
    [CmdAttribute("&serverinfo", //command to handle
        ePrivLevel.Player, //minimum privelege level
        "Shows information about the server", //command description
        "/serverinfo")] //usage
    public class ServerInfoCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            client.Out.SendMessage(LanguageMgr.GetTranslation(client, "Commands.ServerInfo.Title"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
            client.Out.SendMessage(LanguageMgr.GetTranslation(client, "Commands.ServerInfo.Online", ClientService.Instance.ClientCount), eChatType.CT_System, eChatLoc.CL_SystemWindow);
            TimeSpan uptime = DateTime.Now.Subtract(GameServer.Instance.StartupTime);
            double sec = uptime.TotalSeconds;
            long min = Convert.ToInt64(sec) / 60;
            long hours = min / 60;
            long days = hours / 24;
            DisplayMessage(client, LanguageMgr.GetTranslation(client, "Commands.ServerInfo.Uptime", days, hours % 24, min % 60, sec % 60));
        }
    }
}
