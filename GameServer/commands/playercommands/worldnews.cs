using System.Collections.Generic;
using DOL.GS.WorldAI;

namespace DOL.GS.Commands
{
    [CmdAttribute(
        "&worldnews",
        ePrivLevel.Player,
        "최근 공개 월드 뉴스를 표시합니다.",
        "/worldnews")]
    public class WorldNewsCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (client.Player == null)
                return;

            if (IsSpammingCommand(client.Player, "worldnews"))
                return;

            IList<WorldNewsItem> news = WorldNewsService.Instance.GetNews(10);
            List<string> lines = new();

            if (news.Count == 0)
            {
                lines.Add("아직 공개된 서버 뉴스가 없습니다.");
            }
            else
            {
                foreach (WorldNewsItem item in news)
                {
                    lines.Add($"[{item.Importance}] {item.Title}");
                    WorldTextWindowFormatter.AddWrapped(lines, item.Body);
                    lines.Add(string.Empty);
                }
            }

            client.Out.SendCustomTextWindow("서버 뉴스", lines);
        }
    }
}
