namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&show",
		ePrivLevel.Player,
		"내 모든 카드를 다른 플레이어에게 공개합니다. 모든 카드가 앞면이 됩니다.",
		"/show")]
	public class ShowCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
			CardMgr.Show(client);
		}
	}
}