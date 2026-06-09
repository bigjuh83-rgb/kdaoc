using System.Collections.Generic;
using DOL.GS.WorldAI;

namespace DOL.GS.Commands
{
    [CmdAttribute(
        "&history",
        ePrivLevel.Player,
        "최근 공개 월드 기록을 표시합니다.",
        "/history")]
    public class HistoryCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (client.Player == null)
                return;

            if (IsSpammingCommand(client.Player, "history"))
                return;

            IList<WorldEventItem> history = WorldNewsService.Instance.GetHistory(20);
            List<string> lines = new();

            if (history.Count == 0)
            {
                lines.Add("아직 공개된 역사 기록이 없습니다.");
            }
            else
            {
                foreach (WorldEventItem item in history)
                {
                    lines.Add($"[{item.Importance}] {item.Title}");
                    WorldTextWindowFormatter.AddWrapped(lines, item.Chronicle);
                    lines.Add(string.Empty);
                }
            }

            client.Out.SendCustomTextWindow("서버 역사", lines);
        }
    }
}
