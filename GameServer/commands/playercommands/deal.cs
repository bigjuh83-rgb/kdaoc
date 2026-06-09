// using DOL.GS;
//
// namespace DOL.GS.Commands
// {
// 	[CmdAttribute(
// 		"&deal",
// 		ePrivLevel.Player,
// 		"그룹원에게 카드 한 장을 나눠 줍니다. 먼저 /shuffle로 카드를 준비해야 합니다.",
// 		"/deal <이름> <u/d>")]
// 	public class DealCommandHandler : AbstractCommandHandler, ICommandHandler
// 	{
// 		public void OnCommand(GameClient client, string[] args)
// 		{
// 			if (args.Length < 3)
// 				return;
//
//             bool up = false;
//
// 			if (args[2][0] == 'u')
// 				up = true;
// 			else if
// 				(args[2][0] == 'd') up = false;
// 			else
// 				return;
//
// 			GameClient friendClient = WorldMgr.GetClientByPlayerName(args[1], true, true);
//             CardMgr.Deal(client, friendClient, up);
// 		}
// 	}
// }