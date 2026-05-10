namespace DOL.GS.Commands
{
    [CmdAttribute(
         "&safety",
         ePrivLevel.Player,
         "Turns off PvP safety flag.",
         "/safety off")]
    public class SafetyCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if(args.Length >= 2 && args[1].ToLower() == "off")
            {
                client.Player.SafetyFlag = false;
                DisplayMessage(client, T(client, "PlayerCommands.Safety.Off"));
            }
            else if(client.Player.SafetyFlag)
            {
                DisplayMessage(client, T(client, "PlayerCommands.Safety.Info1"));
                DisplayMessage(client, T(client, "PlayerCommands.Safety.Info2"));
                DisplayMessage(client, T(client, "PlayerCommands.Safety.Info3"));
            }
            else
            {
                DisplayMessage(client, T(client, "PlayerCommands.Safety.AlreadyOff"));
            }
        }
    }
}
