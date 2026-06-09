using System;
using DOL.GS.GameEvents;
using DOL.GS.PacketHandler;

namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&keepsupplyconvoy",
		ePrivLevel.GM,
		"킵 보급대 출발 위치를 관리합니다.",
		"/keepsupplyconvoy start <keepID>",
		"/keepsupplyconvoy setstart <albion|midgard|hibernia>",
		"/keepsupplyconvoy clearstart <albion|midgard|hibernia>",
		"/keepsupplyconvoy list")]
	public class KeepSupplyConvoyCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		public void OnCommand(GameClient client, string[] args)
		{
			if (client?.Player == null || args.Length < 2)
			{
				DisplaySyntax(client);
				return;
			}

			switch (args[1].ToLowerInvariant())
			{
				case "start":
					StartConvoy(client, args);
					break;
				case "setstart":
					SetStart(client, args);
					break;
				case "clearstart":
					ClearStart(client, args);
					break;
				case "list":
					ListStarts(client);
					break;
				default:
					DisplaySyntax(client);
					break;
			}
		}

		private void StartConvoy(GameClient client, string[] args)
		{
			if (args.Length < 3 || !int.TryParse(args[2], out int keepId))
			{
				DisplayMessage(client, "사용법: /keepsupplyconvoy start <keepID>");
				return;
			}

			bool started = KeepSupplyConvoyEvent.ForceStartConvoy(keepId, out string message);
			DisplayMessage(client, started ? message : $"보급대 강제 출발 실패: {message}");
		}

		private void SetStart(GameClient client, string[] args)
		{
			if (args.Length < 3 || !TryParseRealm(args[2], out eRealm realm))
			{
				DisplayMessage(client, "사용법: /keepsupplyconvoy setstart <albion|midgard|hibernia>");
				return;
			}

			if (client.Player.CurrentRegion == null)
			{
				DisplayMessage(client, "현재 지역 정보를 찾을 수 없습니다.");
				return;
			}

			bool saved = KeepSupplyConvoyEvent.SetStartPosition(
				realm,
				client.Player.CurrentRegion.ID,
				client.Player.X,
				client.Player.Y,
				client.Player.Z,
				client.Player.Heading,
				out string message);

			DisplayMessage(client, saved ? message : $"보급대 출발 위치 저장 실패: {message}");
		}

		private void ClearStart(GameClient client, string[] args)
		{
			if (args.Length < 3 || !TryParseRealm(args[2], out eRealm realm))
			{
				DisplayMessage(client, "사용법: /keepsupplyconvoy clearstart <albion|midgard|hibernia>");
				return;
			}

			bool cleared = KeepSupplyConvoyEvent.ClearStartPosition(realm, out string message);
			DisplayMessage(client, cleared ? message : $"보급대 출발 위치 삭제 실패: {message}");
		}

		private void ListStarts(GameClient client)
		{
			KeepSupplyConvoyEvent.ConvoyStartPosition[] starts = KeepSupplyConvoyEvent.GetStartPositions();
			if (starts.Length == 0)
			{
				DisplayMessage(client, "설정된 보급대 출발 위치가 없습니다.");
				return;
			}

			foreach (KeepSupplyConvoyEvent.ConvoyStartPosition start in starts)
			{
				DisplayMessage(
					client,
					$"{GlobalConstants.RealmToName(start.Realm)}: region={start.RegionID}, x={start.Point.X}, y={start.Point.Y}, z={start.Point.Z}, heading={start.Heading}");
			}
		}

		private static bool TryParseRealm(string value, out eRealm realm)
		{
			realm = eRealm.None;
			if (string.IsNullOrWhiteSpace(value))
				return false;

			switch (value.Trim().ToLowerInvariant())
			{
				case "1":
				case "alb":
				case "albion":
				case "알비온":
					realm = eRealm.Albion;
					return true;
				case "2":
				case "mid":
				case "midgard":
				case "미드":
				case "미드가드":
					realm = eRealm.Midgard;
					return true;
				case "3":
				case "hib":
				case "hibernia":
				case "히브":
				case "히베":
				case "하이버니아":
					realm = eRealm.Hibernia;
					return true;
				default:
					return Enum.TryParse(value, true, out realm)
						&& realm is eRealm.Albion or eRealm.Midgard or eRealm.Hibernia;
			}
		}
	}
}
