using System.Reflection;
using DOL.GS;
using DOL.GS.Quests;
using DOL.Language;

namespace DOL.GS
{
	public class TaskMaster : GameNPC
	{
		private static new readonly Logging.Logger log = Logging.LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);

		public override bool Interact(GamePlayer player)
		{
			if (!base.Interact(player))
				return false;

			//we need to disable them for players for now
			if (player.Client.Account.PrivLevel == 1)
			{
				SayTo(player, LanguageMgr.GetTranslation(player.Client, "TaskMaster.Disabled"));
				return true;
			}

			if (player.Mission == null)
				SayTo(player, LanguageMgr.GetTranslation(player.Client, "TaskMaster.Intro"));
			else SayTo(player, LanguageMgr.GetTranslation(player.Client, "TaskMaster.AlreadyHaveTask"));

			return true;
		}

		public override bool WhisperReceive(GameLiving source, string str)
		{
			if (!base.WhisperReceive(source, str))
				return false;

			GamePlayer player = source as GamePlayer;
			if (player == null)
				return false;

			if (player.Mission != null)
				return false;

            switch (str.ToLower())
            {
                case "assignment":
                case "임무":
                    {
                        SayTo(player, LanguageMgr.GetTranslation(player.Client, "TaskMaster.Assignment"));
                        break;
                    }
                case "program":
                case "과업 제도":
                    {
                        SayTo(player, LanguageMgr.GetTranslation(player.Client, "TaskMaster.Program"));
                        break;
                    }
                case "long corridors":
                case "긴 복도":
                case "labyrinthine dungeons":
                case "미로형 던전":
                    {
                        if (player.Mission != null)
                            break;
                        //Can't if we already have one!

                        //Can't if group has one!
                        if (player.Group != null && player.Group.Mission != null)
                            break;

                        log.Info("INFO: TaskMaster Dungeons activated");
                        TaskDungeonMission mission;
                        if (player.Group != null)
	mission = new TaskDungeonMission(player.Group, TaskDungeonMission.eDungeonType.Ranged);
                        else
                        {
                            mission = new TaskDungeonMission(player, TaskDungeonMission.eDungeonType.Melee);
                            player.Mission = mission;
                        }
                        /*
                         * Very well Gwirenn, it's good to see adventurers willing to help out the realm in such times.  Dralkden the Thirster has taken over the caves to the south and needs to be disposed of.  Good luck!
                         * Very well Gwirenn, it's good to see adventurers willing to help out the realm in such times. Clear the caves to the south of creatures. Good luck!
                         */
                        string msg = LanguageMgr.GetTranslation(player.Client, "TaskMaster.MissionAccepted", player.Name);
                        switch (mission.TDMissionType)
                        {
                            case TaskDungeonMission.eTDMissionType.Clear:
                                msg += " " + LanguageMgr.GetTranslation(player.Client, "TaskMaster.MissionClear", mission.TaskRegion.Description);
                                break;
                            case TaskDungeonMission.eTDMissionType.Boss:
                                msg += " " + LanguageMgr.GetTranslation(player.Client, "TaskMaster.MissionBoss", mission.BossName, mission.TaskRegion.Description);
                                break;
                            case TaskDungeonMission.eTDMissionType.Specific:
                                msg += " " + LanguageMgr.GetTranslation(player.Client, "TaskMaster.MissionSpecific", mission.Total, mission.TargetName, mission.TaskRegion.Description);
                                break;
                        }
                        SayTo(player, msg);
                        break;
                    }
            }
			return true;
		}
	}
}
