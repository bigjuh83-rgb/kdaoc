namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&held",
		ePrivLevel.Player,
		"내 손패를 표시합니다. 'held g'를 사용하면 그룹원이 공개한 카드를 표시합니다.",
		"/held <g>")]
	public class HeldCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
            if (args.Length == 2 && client.Player.Group != null)
                foreach (GamePlayer Groupee in client.Player.Group.GetPlayersInTheGroup())
                    if(Groupee != client.Player) CardMgr.Held(client, Groupee.Client);
            else
                CardMgr.Held(client, client);
		}
	}
}