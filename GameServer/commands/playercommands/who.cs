using System;
using System.Collections;
using System.Text;
using DOL.Language;

namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&who",
		ePrivLevel.Player,
		"접속 중인 플레이어를 표시합니다.",
		//help:
		//"/who  [플레이어이름], [클래스], [#] 레벨, [지역], [##] [##] 레벨 범위로 필터링할 수 있습니다.",
		"/WHO 전체 - 접속 중인 모든 플레이어를 표시합니다.",
		//"/WHO NF - New Frontiers에 접속 중인 모든 플레이어를 표시합니다.",
		// "/WHO CSR - 접속 중인 고객지원 담당자를 표시합니다.",
		// "/WHO DEV - 접속 중인 개발팀원을 표시합니다.",
		// "/WHO QTA - 접속 중인 퀘스트 팀 어시스턴트를 표시합니다.",
		"/WHO <이름> - 해당 이름으로 시작하는 플레이어를 표시합니다.",
		"/WHO <길드 이름> - 해당 길드 이름으로 시작하는 플레이어를 표시합니다.",
		"/WHO <클래스> - 해당 클래스의 플레이어를 표시합니다.",
		"/WHO <지역> - 해당 지역의 플레이어를 표시합니다.",
		"/WHO <레벨> - 해당 레벨의 플레이어를 표시합니다.",
		"/WHO <레벨> <레벨> - 지정한 레벨 범위의 플레이어를 표시합니다.",
		"/WHO BG - 공개 배틀그룹을 이끄는 모든 플레이어를 표시합니다.",
		"/WHO 그룹없음 - 그룹이 없는 모든 플레이어를 표시합니다.",
		"/WHO 하드코어 - 모든 하드코어 플레이어를 표시합니다."
	)]
	public class WhoCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		private static readonly Logging.Logger log = Logging.LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);

		public const int MAX_LIST_SIZE = 49;

		public void OnCommand(GameClient client, string[] args)
		{
			if (IsSpammingCommand(client.Player, "who") && client.Account.PrivLevel == 1)
				return;
			
			int listStart = 1;
			ArrayList filters = null;
			ArrayList clientsList = new ArrayList();
			ArrayList resultMessages = new ArrayList();

			foreach (GamePlayer otherPlayer in ClientService.Instance.GetPlayers())
			{
				if (otherPlayer.Client.Account.PrivLevel > (uint) ePrivLevel.Player && otherPlayer.IsAnonymous == false)
				{
					clientsList.Add(otherPlayer.Client);
					continue;
				}

				if (otherPlayer.Client != client
					&& client.Account.PrivLevel == (uint) ePrivLevel.Player
					&& (otherPlayer.IsAnonymous || !GameServer.ServerRules.IsSameRealm(otherPlayer, client.Player, true)))
				{
					continue;
				}

				clientsList.Add(otherPlayer.Client);
			}

			// no params
			if (args.Length == 1)
			{
				int playing = clientsList.Count;

				// including anon?
				DisplayMessage(client, L(client, "PLCommands.Who.PlayersOnline", playing));
				DisplayMessage(client, L(client, "PLCommands.Who.NoArgs"));
				return;
			}
			
			// any params passed?
			switch (args[1].ToLower())
			{
				case "all": // display all players, no filter
				case "전체":
				case "모두":
				{
					filters = null;
					break;
				}
				case "help": // list syntax for the who command
				case "도움말":
				{
					DisplaySyntax(client);
					return;
				}
				case "staff":
				case "스태프":
				case "gm":
				case "admin":
				{
					filters = new ArrayList(1);
					filters.Add(new GMFilter());
					break;
				}
				case "en":
				case "cz":
				case "de":
				case "es":
				case "fr":
				case "it":
				{
					filters = new ArrayList(1);
					filters.Add(new LanguageFilter(args[1].ToLower()));
					break;
				}
				case "cg":
				case "채팅그룹":
				{
					filters = new ArrayList(1);
					filters.Add(new ChatGroupFilter());
					break;
				}
				case "bg":
				case "배틀그룹":
				{
					filters = new ArrayList(1);
					filters.Add(new BGFilter());
					break;
				}
				case "nogroup":
				case "그룹없음":
				case "솔로":
				{
					filters = new ArrayList();
					filters.Add(new SoloFilter());
					break;
				}
				case "rp":
				case "렐름포인트":
				{
					filters = new ArrayList(1);
					filters.Add(new RPFilter());
					break;
				}
				case "hc":
				case "hardcore":
				case "하드코어":
				{
					filters = new ArrayList(1);
					filters.Add(new HCFilter());
					break;
				}
				case "frontiers":
				case "프론티어":
				{
					filters = new ArrayList();
					filters.Add(new OldFrontiersFilter());
					break;
				}
				case "adv": // Filter for '/advisor' system
				case "조언자":
				{
					filters = new ArrayList();
					filters.Add(new AdvisorFilter());
					break;
				}
				default:
				{
					filters = new ArrayList();
					AddFilters(filters, args, 1);
					break;
				}
			}

			int resultCount = 0;
			foreach (GameClient clients in clientsList)
			{
				if (ApplyFilter(filters, clients.Player))
				{
					resultCount++;
					if (resultMessages.Count < MAX_LIST_SIZE && resultCount >= listStart)
					{
						resultMessages.Add(resultCount + ") " + FormatLine(clients.Player, client.Account.PrivLevel, client));
					}
				}
			}

			foreach (string str in resultMessages)
			{
				DisplayMessage(client, str);
			}

			if (resultCount == 0)
			{
				DisplayMessage(client, L(client, "PLCommands.Who.NoMatches"));
			}
			else if (resultCount > MAX_LIST_SIZE)
			{
				DisplayMessage(client, L(client, "PLCommands.Who.ListTruncated", resultCount));
			}

			filters = null;
		}


		// make /who line using GamePlayer
		private string FormatLine(GamePlayer player, uint PrivLevel, GameClient source)
		{

			// /setwho class | trade
			// Sets how the player wishes to be displayed on a /who inquery.
			// Class displays the character's class and level.
			// Trade displays the tradeskill type and level of the character.
			// and it is saved after char logs out


			if (player == null)
			{
				if (log.IsErrorEnabled)
					log.Error("null player in who command");
				return "???";
			}

			StringBuilder result = new StringBuilder(player.Name, 100);
			if (player.GuildName != string.Empty)
			{
				result.Append(" <");
				result.Append(player.GuildName);
				result.Append(">");
			}

			result.Append(" ");
			result.Append(L(source, "PLCommands.Who.LevelPrefix"));
			result.Append(" ");
			result.Append(player.Level);
			if (player.ClassNameFlag)
			{
				result.Append(" ");
				result.Append(player.CharacterClass.Name);
			}
			else if (player.CharacterClass != null)
			{
				result.Append(" ");
				AbstractCraftingSkill skill = CraftingMgr.getSkillbyEnum(player.CraftingPrimarySkill);
				result.Append(player.CraftTitle.GetValue(source.Player, player));
			}
			else
			{
				if (log.IsErrorEnabled)
					log.Error("no character class spec in who commandhandler for player " + player.Name);
			}

			if (player.CurrentZone != null && GameServer.Instance.Configuration.ServerType != EGameServerType.GST_PvP)
			{
				// If '/who' source is a Player and target is plvl 3, do not return zone description (only return for Admins if Admin is source)
				if (source.Account.PrivLevel == (uint)ePrivLevel.Player && player.Client.Account.PrivLevel == (uint)ePrivLevel.Player || source.Account.PrivLevel == (uint)ePrivLevel.Admin)
				{
					result.Append(" ");
					result.Append(L(source, "PLCommands.Who.LocationPrefix"));
					result.Append(" ");
					// Counter-espionage behavior: Change zone description to "Frontiers" if source is a Player and target(s) located in OF (RVR-enabled zone in classic Alb/Hib/Mid region)
					if (source.Account.PrivLevel == (uint)ePrivLevel.Player && player.CurrentZone.IsRvR && player.CurrentRegion.ID is 1 or 100 or 200)
					{
						result.Append(L(source, "PLCommands.Who.Frontiers"));
					}
					// If target player(s) are not in RvR-enabled zones in classic region, return zone name/description
					else
					{
						result.Append(player.CurrentZone.Description);	
					}
				}
			}
			else
			{
				if (log.IsErrorEnabled && player.Client.Account.PrivLevel != (uint)ePrivLevel.Admin)
					log.Error("no currentzone in who commandhandler for player " + player.Name);
			}
			ChatGroup mychatgroup = player.TempProperties.GetProperty<ChatGroup>(ChatGroup.CHATGROUP_PROPERTY);
			if (mychatgroup != null && (mychatgroup.Members.Contains(player) || mychatgroup.IsPublic && (bool)mychatgroup.Members[player] == true))
			{
				result.Append(" [CG]");
			}
			BattleGroup mybattlegroup = player.TempProperties.GetProperty<BattleGroup>(BattleGroup.BATTLEGROUP_PROPERTY);
			if (mybattlegroup != null && (mybattlegroup.Members.Contains(player) || mybattlegroup.IsPublic && (bool)mybattlegroup.Members[player] == true))
			{
				result.Append(" [BG]");
			}
			if (player.IsAnonymous)
			{
				result.Append(" <ANON>");
			}
			if (player.TempProperties.GetProperty<string>(GamePlayer.AFK_MESSAGE) != null)
			{
				result.Append(" <AFK>");
			}
			if (player.Advisor)
			{
				result.Append(" <ADV>");
			}
			if (player.HCFlag)
			{
				result.Append(" <HC>");
			}
			if(player.Client.Account.PrivLevel == (uint)ePrivLevel.GM)
			{
				result.Append(" <GM>");
			}
			if(player.Client.Account.PrivLevel == (uint)ePrivLevel.Admin)
			{
				result.Append(" <Admin>");
			}
			if (ServerProperties.Properties.ALLOW_CHANGE_LANGUAGE)
			{
				result.Append(" <" + player.Client.Account.Language + ">");
			}

			return result.ToString();
		}

		private void AddFilters(ArrayList filters, string[] args, int skip)
		{
			for (int i = skip; i < args.Length; i++)
			{
				if (GameServer.Instance.Configuration.ServerType == EGameServerType.GST_PvP)
					filters.Add(new StringFilter(args[i]));
				else
				{
					try
					{
						int currentNum = (int) System.Convert.ToUInt32(args[i]);
						int nextNum = -1;
						try
						{
							nextNum = (int) System.Convert.ToUInt32(args[i + 1]);
						}
						catch
						{
						}

						if (nextNum != -1)
						{
							filters.Add(new LevelRangeFilter(currentNum, nextNum));
							i++;
						}
						else
						{
							filters.Add(new LevelFilter(currentNum));
						}
					}
					catch
					{
						filters.Add(new StringFilter(args[i]));
					}
				}
			}
		}


		private bool ApplyFilter(ArrayList filters, GamePlayer player)
		{
			if (filters == null)
				return true;
			foreach (IWhoFilter filter in filters)
			{
				if (!filter.ApplyFilter(player))
					return false;
			}
			return true;
		}


		//Filters

		private class StringFilter : IWhoFilter
		{
			private string m_filterString;

			public StringFilter(string str)
			{
				m_filterString = str.ToLower().Trim();
			}

			public bool ApplyFilter(GamePlayer player)
			{
				if (player.Name.ToLower().StartsWith(m_filterString))
					return true;
				if (player.GuildName.ToLower().StartsWith(m_filterString))
					return true;
				if (GameServer.Instance.Configuration.ServerType == EGameServerType.GST_PvP)
					return false;
				if (player.CharacterClass.Name.ToLower().StartsWith(m_filterString))
					return true;
				if (player.CurrentZone != null && player.CurrentZone.Description.ToLower().Contains(m_filterString) && !player.CurrentZone.IsOF)
					return true;
				return false;
			}
		}

		private class LevelRangeFilter : IWhoFilter
		{
			private int m_minLevel;
			private int m_maxLevel;

			public LevelRangeFilter(int minLevel, int maxLevel)
			{
				m_minLevel = Math.Min(minLevel, maxLevel);
				m_maxLevel = Math.Max(minLevel, maxLevel);
			}

			public bool ApplyFilter(GamePlayer player)
			{
				if (player.Level >= m_minLevel && player.Level <= m_maxLevel)
					return true;
				return false;
			}
		}

		private class LevelFilter : IWhoFilter
		{
			private int m_level;

			public LevelFilter(int level)
			{
				m_level = level;
			}

			public bool ApplyFilter(GamePlayer player)
			{
				return player.Level == m_level;
			}
		}

		private class GMFilter : IWhoFilter
		{
			public bool ApplyFilter(GamePlayer player)
			{
				if(!player.IsAnonymous && player.Client.Account.PrivLevel > (uint)ePrivLevel.Player)
					return true;
				return false;
			}
		}

		private class LanguageFilter : IWhoFilter
		{
			private string m_str;
			public bool ApplyFilter(GamePlayer player)
			{
				if (!player.IsAnonymous && player.Client.Account.Language.ToLower() == m_str)
					return true;
				return false;
			}
			
			public LanguageFilter(string language)
			{
				m_str = language;
			}
		}

		private class ChatGroupFilter : IWhoFilter
		{
			public bool ApplyFilter(GamePlayer player)
			{
				ChatGroup cg = player.TempProperties.GetProperty<ChatGroup>(ChatGroup.CHATGROUP_PROPERTY);
				//no chatgroup found
				if (cg == null)
					return false;

				//always show your own cg
				//TODO

				//player is a cg leader, and the cg is public
				if ((bool)cg.Members[player] == true && cg.IsPublic)
					return true;

				return false;
			}
		}

		private class OldFrontiersFilter : IWhoFilter
		{
			public bool ApplyFilter(GamePlayer player)
			{
				if (player.Client.Account.PrivLevel == (uint)ePrivLevel.Admin && player.CurrentZone.IsRvR)
					return false;
				if (player.Client.Account.PrivLevel < (uint)ePrivLevel.Admin && player.CurrentZone.IsRvR && player.CurrentRegion.ID is 1 or 100 or 200)
					return true;
				return false;
			}
		}

		private class RPFilter : IWhoFilter
		{
			public bool ApplyFilter(GamePlayer player)
			{
				return player.RPFlag;
			}
		}

		private class AdvisorFilter : IWhoFilter
		{
			public bool ApplyFilter(GamePlayer player)
			{
				return player.Advisor;
			}
		}

		private class HCFilter : IWhoFilter
		{
			public bool ApplyFilter(GamePlayer player)
			{
				return player.HCFlag;
			}
		}

		private class SoloFilter : IWhoFilter
		{
			public bool ApplyFilter(GamePlayer player)
			{
				if (player.Group == null)
				{
					return true;
				}
				return false;
			}
		}

		private class BGFilter : IWhoFilter
		{
			public bool ApplyFilter(GamePlayer player)
			{
				BattleGroup bg = player.TempProperties.GetProperty<BattleGroup>(BattleGroup.BATTLEGROUP_PROPERTY);
				//no battlegroup found
				if (bg == null)
					return false;

				//always show your own bg
				//TODO

				//player is a bg leader, and the bg is public
				if (bg.Leader == player && bg.IsPublic)
					return true;
				
				return false;
			}
		}

		private interface IWhoFilter
		{
			bool ApplyFilter(GamePlayer player);
		}

		private static string L(GameClient client, string key, params object[] args)
		{
			return LanguageMgr.GetTranslation(client, key, args);
		}
	}
}
