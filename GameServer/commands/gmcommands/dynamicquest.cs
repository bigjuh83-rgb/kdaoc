using System;
using System.Linq;
using DOL.GS.ServerProperties;
using DOL.GS.WorldAI;

namespace DOL.GS.Commands
{
    [CmdAttribute(
        "&dynamicquest",
        ePrivLevel.GM,
        "KDAOC dynamic quest runtime controls. GM-created offers are runtime-only; auto-seeded story templates and player progress use the DB-backed runtime.",
        "/dynamicquest fakekill <target mob name> [count]",
        "/dynamicquest llm [seed text]",
        "/dynamicquest list",
        "/dynamicquest clear",
        "/dynamicquest status")]
    public class DynamicQuestCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (client?.Player == null)
                return;

            if (args.Length < 2)
            {
                DisplayUsage(client);
                return;
            }

            switch (args[1].ToLowerInvariant())
            {
                case "fakekill":
                    CreateFakeKillQuest(client, args);
                    return;
                case "llm":
                    CreateLlmQuest(client, args);
                    return;
                case "list":
                    ListQuests(client);
                    return;
                case "clear":
                    ClearQuests(client);
                    return;
                case "status":
                    DisplayStatus(client);
                    return;
                default:
                    DisplayUsage(client);
                    return;
            }
        }

        private void CreateFakeKillQuest(GameClient client, string[] args)
        {
            if (client.Player.TargetObject is not GameNPC npc)
            {
                DisplayMessage(client, "시작 NPC를 타겟한 뒤 실행하세요.");
                return;
            }

            if (args.Length < 3)
            {
                DisplayMessage(client, "사용법: /dynamicquest fakekill <target mob name> [count]");
                return;
            }

            int count = 3;
            string targetName;

            if (args.Length >= 4 && int.TryParse(args[^1], out int parsedCount))
            {
                count = parsedCount;
                targetName = string.Join(" ", args.Skip(2).Take(args.Length - 3));
            }
            else
            {
                targetName = string.Join(" ", args.Skip(2));
            }

            DynamicQuestResult result = DynamicQuestRuntimeService.Instance.CreateKillQuest(npc, targetName, count);
            DisplayMessage(client, result.Message);
        }

        private void CreateLlmQuest(GameClient client, string[] args)
        {
            if (client.Player.TargetObject is not GameNPC npc)
            {
                DisplayMessage(client, "시작 NPC를 타겟한 뒤 실행하세요.");
                return;
            }

            string seed = args.Length >= 3 ? string.Join(" ", args.Skip(2)) : "이 지역에 어울리는 짧은 처치 의뢰";
            DynamicQuestResult result = DynamicQuestRuntimeService.Instance.CreateKillQuestFromLlm(npc, seed);
            DisplayMessage(client, result.Message);
        }

        private void ListQuests(GameClient client)
        {
            var quests = DynamicQuestRuntimeService.Instance.GetQuests();
            if (quests.Count == 0)
            {
                DisplayMessage(client, "현재 활성화된 런타임 동적 퀘스트 오퍼가 없습니다.");
                return;
            }

            client.Out.SendCustomTextWindow("Dynamic Quests", quests.Select(quest =>
                $"{quest.Title} | NPC={quest.StartNpcName} | Target={quest.TargetName} {quest.TargetCount} | Region={quest.StartRegionId}").ToList());
        }

        private void ClearQuests(GameClient client)
        {
            int count = DynamicQuestRuntimeService.Instance.ClearAll();
            DisplayMessage(client, $"런타임 동적 퀘스트 오퍼 {count}개를 삭제했습니다.");
        }

        private void DisplayStatus(GameClient client)
        {
            DisplayMessage(client,
                $"enabled={Properties.KDAOC_DYNAMIC_QUEST_ENABLED}, " +
                $"maxPerPlayer={Properties.KDAOC_DYNAMIC_QUEST_MAX_ACTIVE_PER_PLAYER}, " +
                $"maxPerNpc={Properties.KDAOC_DYNAMIC_QUEST_MAX_ACTIVE_PER_NPC}, " +
                $"maxKillCount={Properties.KDAOC_DYNAMIC_QUEST_MAX_KILL_COUNT}");
        }

        private static void DisplayUsage(GameClient client)
        {
            client.Out.SendCustomTextWindow("Dynamic Quest Commands", new[]
            {
                "/dynamicquest status",
                "/dynamicquest fakekill <target mob name> [count]",
                "/dynamicquest llm [seed text]",
                "/dynamicquest list",
                "/dynamicquest clear",
                "주의: 이 GM 명령으로 만든 임시 오퍼는 런타임 상태입니다. 자동 시드 스토리 템플릿과 플레이어 진행은 DB-backed 런타임 경로를 사용합니다."
            });
        }
    }
}
