using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using DOL.Database;
using DOL.Events;
using DOL.GS;
using DOL.GS.API;
using DOL.GS.PacketHandler;
using DOL.GS.PlayerTitles;
using DOL.GS.Quests;

namespace DOL.GS.WeeklyQuest.Albion
{
	public class EpicRvRMobsWeeklyQuestAlb : Quests.WeeklyQuest
	{
		/// <summary>
		/// Defines a logger for this class.
		/// </summary>
		private static readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);

		private const string questTitle = "[Weekly] Frontier Cleanup";
		private const int minimumLevel = 50;
		private const int maximumLevel = 50;

		// Kill Goal
		private const int MAX_KILLED = 1;
		// Quest Counter
		private int _evernKilled = 0;
		private int _glacierGiantKilled = 0;
		private int _greenKnightKilled = 0;

		private static GameNPC Haszan = null; // Start NPC

		private const string EVERN_NAME = "Evern";
		private const string GREENKNIGHT_NAME = "Green Knight";
		private const string GLACIERGIANT_NAME = "Glacier Giant";

		// Constructors
		public EpicRvRMobsWeeklyQuestAlb() : base()
		{
		}

		public EpicRvRMobsWeeklyQuestAlb(GamePlayer questingPlayer) : base(questingPlayer)
		{
		}

		public EpicRvRMobsWeeklyQuestAlb(GamePlayer questingPlayer, int step) : base(questingPlayer, step)
		{
		}

		public EpicRvRMobsWeeklyQuestAlb(GamePlayer questingPlayer, DbQuest dbQuest) : base(questingPlayer, dbQuest)
		{
		}

		public override int Level
		{
			get
			{
				// Quest Level
				return minimumLevel;
			}
		}

		[ScriptLoadedEvent]
		public static void ScriptLoaded(DOLEvent e, object sender, EventArgs args)
		{
			if (!ServerProperties.Properties.LOAD_QUESTS)
				return;


			#region defineNPCs

			GameNPC[] npcs = WorldMgr.GetNPCsByName("Haszan", eRealm.Albion);

			if (npcs.Length > 0)
				foreach (GameNPC npc in npcs)
					if (npc.CurrentRegionID == 1 && npc.X == 583866 && npc.Y == 477497)
					{
						Haszan = npc;
						break;
					}

			if (Haszan == null)
			{
				if (log.IsWarnEnabled)
					log.Warn("Could not find Haszan , creating it ...");
				Haszan = new GameNPC();
				Haszan.Model = 51;
				Haszan.Name = "Haszan";
				Haszan.GuildName = "Realm Logistics";
				Haszan.Realm = eRealm.Albion;
				//Castle Sauvage Location
				Haszan.CurrentRegionID = 1;
				Haszan.Size = 50;
				Haszan.Level = 59;
				Haszan.X = 583866;
				Haszan.Y = 477497;
				Haszan.Z = 2600;
				Haszan.Heading = 3111;
				Haszan.AddToWorld();
				if (SAVE_INTO_DATABASE)
				{
					Haszan.SaveIntoDatabase();
				}
			}

			#endregion

			#region defineItems
			#endregion

			#region defineObject
			#endregion

			GameEventMgr.AddHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
			GameEventMgr.AddHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

			GameEventMgr.AddHandler(Haszan, GameObjectEvent.Interact, new DOLEventHandler(TalkToHaszan));
			GameEventMgr.AddHandler(Haszan, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToHaszan));

			/* Now we bring to Haszan the possibility to give this quest to players */
			Haszan.AddQuestToGive(typeof (EpicRvRMobsWeeklyQuestAlb));

			if (log.IsInfoEnabled)
				log.Info("Quest \"" + questTitle + "\" initialized");
		}

		[ScriptUnloadedEvent]
		public static void ScriptUnloaded(DOLEvent e, object sender, EventArgs args)
		{
			//if not loaded, don't worry
			if (Haszan == null)
				return;
			// remove handlers
			GameEventMgr.RemoveHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
			GameEventMgr.RemoveHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

			GameEventMgr.RemoveHandler(Haszan, GameObjectEvent.Interact, new DOLEventHandler(TalkToHaszan));
			GameEventMgr.RemoveHandler(Haszan, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToHaszan));

			/* Now we remove to Haszan the possibility to give this quest to players */
			Haszan.RemoveQuestToGive(typeof (EpicRvRMobsWeeklyQuestAlb));
		}

		private static void TalkToHaszan(DOLEvent e, object sender, EventArgs args)
		{
			//We get the player from the event arguments and check if he qualifies
			GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
			if (player == null)
				return;

			if(Haszan.CanGiveQuest(typeof (EpicRvRMobsWeeklyQuestAlb), player)  <= 0)
				return;

			//We also check if the player is already doing the quest
			EpicRvRMobsWeeklyQuestAlb quest = player.IsDoingQuest(typeof (EpicRvRMobsWeeklyQuestAlb)) as EpicRvRMobsWeeklyQuestAlb;

			if (e == GameObjectEvent.Interact)
			{
				if (quest != null)
				{
					switch (quest.Step)
					{
						case 1:
							Haszan.SayTo(player, player.Name + ", please find allys and kill the epic creatures in frontiers for Albion!");
							break;
						case 2:
							Haszan.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.DidYouToken", player.Name, "[slay the creatures] and return for your reward"));
							break;
					}
				}
				else
				{
					Haszan.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.EpicFrontierIntroFriends", player.Name, "Haszan", "Albion"));
				}
			}
				// The player whispered to the NPC
			else if (e == GameLivingEvent.WhisperReceive)
			{
				WhisperReceiveEventArgs wArgs = (WhisperReceiveEventArgs) args;
				if (quest == null)
				{
					switch (wArgs.Text)
					{
						case "kill the epic creatures":
						case "에픽 생명체 처치":
							player.Out.SendQuestSubscribeCommand(Haszan, QuestMgr.GetIDForQuestType(typeof(EpicRvRMobsWeeklyQuestAlb)), DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.HelpNpcQuest", "Haszan", questTitle));
							break;
					}
				}
				else
				{
					switch (wArgs.Text)
					{
						case "slay the creatures":
							if (quest.Step == 2)
							{
								player.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.ThankContribution"), eChatType.CT_Chat, eChatLoc.CL_PopupWindow);
								quest.FinishQuest();
							}
							break;
						case "abort":
							player.Out.SendCustomDialog(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.AbortConfirm"), new CustomDialogResponse(CheckPlayerAbortQuest));
							break;
					}
				}
			}
		}

		public override string QuestPropertyKey
		{
			get => "EpicRvRMobsWeeklyQuestAlb";
			set { ; }
		}

		public override bool CheckQuestQualification(GamePlayer player)
		{
			// if the player is already doing the quest his level is no longer of relevance
			if (player.IsDoingQuest(typeof (EpicRvRMobsWeeklyQuestAlb)) != null)
				return true;

			// This checks below are only performed is player isn't doing quest already

			//if (player.HasFinishedQuest(typeof(Academy_47)) == 0) return false;

			//if (!CheckPartAccessible(player,typeof(CityOfCamelot)))
			//	return false;

			if (player.Level < minimumLevel || player.Level > maximumLevel)
				return false;

			return true;
		}

		public override void LoadQuestParameters()
		{
			_evernKilled = GetCustomProperty(EVERN_NAME) != null ? int.Parse(GetCustomProperty(EVERN_NAME)) : 0;
			_glacierGiantKilled = GetCustomProperty(GLACIERGIANT_NAME) != null ? int.Parse(GetCustomProperty(GLACIERGIANT_NAME)) : 0;
			_greenKnightKilled = GetCustomProperty(GREENKNIGHT_NAME) != null ? int.Parse(GetCustomProperty(GREENKNIGHT_NAME)) : 0;
		}

		public override void SaveQuestParameters()
		{
			SetCustomProperty(EVERN_NAME, _evernKilled.ToString());
			SetCustomProperty(GLACIERGIANT_NAME, _glacierGiantKilled.ToString());
			SetCustomProperty(GREENKNIGHT_NAME, _greenKnightKilled.ToString());
		}

		private static void CheckPlayerAbortQuest(GamePlayer player, byte response)
		{
			EpicRvRMobsWeeklyQuestAlb quest = player.IsDoingQuest(typeof (EpicRvRMobsWeeklyQuestAlb)) as EpicRvRMobsWeeklyQuestAlb;

			if (quest == null)
				return;

			if (response == 0x00)
			{
				SendSystemMessage(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.ContinueSlayCreatures"));
			}
			else
			{
				SendSystemMessage(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.AbortingQuestRestart", questTitle));
				quest.AbortQuest();
			}
		}

		private static void SubscribeQuest(DOLEvent e, object sender, EventArgs args)
		{
			QuestEventArgs qargs = args as QuestEventArgs;
			if (qargs == null)
				return;

			if (qargs.QuestID != QuestMgr.GetIDForQuestType(typeof(EpicRvRMobsWeeklyQuestAlb)))
				return;

			if (e == GamePlayerEvent.AcceptQuest)
				CheckPlayerAcceptQuest(qargs.Player, 0x01);
			else if (e == GamePlayerEvent.DeclineQuest)
				CheckPlayerAcceptQuest(qargs.Player, 0x00);
		}

		private static void CheckPlayerAcceptQuest(GamePlayer player, byte response)
		{
			if(Haszan.CanGiveQuest(typeof (EpicRvRMobsWeeklyQuestAlb), player)  <= 0)
				return;

			if (player.IsDoingQuest(typeof (EpicRvRMobsWeeklyQuestAlb)) != null)
				return;

			if (response == 0x00)
			{
				player.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.ThanksForHelpingRealm", "Albion"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
			}
			else
			{
				//Check if we can add the quest!
				if (!Haszan.GiveQuest(typeof (EpicRvRMobsWeeklyQuestAlb), player, 1))
					return;

				Haszan.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.EpicFrontierReminder"));

			}
		}

		//Set quest name
		public override string Name
		{
			get { return DOL.Language.LanguageMgr.GetTranslatedQuestTitle(m_questPlayer?.Client?.Account?.Language, questTitle); }
		}

		// Define Steps
		public override string Description
		{
			get
			{
				switch (Step)
				{
					case 1:
						return DOL.Language.LanguageMgr.GetTranslation(m_questPlayer.Client.Account.Language, "Quest.Common.EpicFrontierDescription", EVERN_NAME, _evernKilled, MAX_KILLED, GREENKNIGHT_NAME, _greenKnightKilled, MAX_KILLED, GLACIERGIANT_NAME, _glacierGiantKilled, MAX_KILLED);
					case 2:
						return DOL.Language.LanguageMgr.GetTranslation(m_questPlayer.Client.Account.Language, "Quest.Common.ReturnToNpc", "Haszan");
				}
				return base.Description;
			}
		}

		public override void Notify(DOLEvent e, object sender, EventArgs args)
		{
			GamePlayer player = sender as GamePlayer;

			if (player?.IsDoingQuest(typeof(EpicRvRMobsWeeklyQuestAlb)) == null)
				return;

			if (sender != m_questPlayer)
				return;

			if (Step != 1 || e != GameLivingEvent.EnemyKilled) return;
			EnemyKilledEventArgs gArgs = (EnemyKilledEventArgs) args;

			if (gArgs.Target.Name.ToLower() == EVERN_NAME.ToLower() && gArgs.Target is GameNPC && _evernKilled < MAX_KILLED)
			{
				_evernKilled = 1;
				player.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.WeeklyNamedKilled", EVERN_NAME, _evernKilled, MAX_KILLED), eChatType.CT_ScreenCenter, eChatLoc.CL_SystemWindow);
				player.Out.SendQuestUpdate(this);
			}
			else if (gArgs.Target.Name.ToLower() == GREENKNIGHT_NAME.ToLower() && gArgs.Target is GameNPC && _greenKnightKilled < MAX_KILLED)
			{
				_greenKnightKilled = 1;
				player.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.WeeklyNamedKilled", GREENKNIGHT_NAME, _greenKnightKilled, MAX_KILLED), eChatType.CT_ScreenCenter, eChatLoc.CL_SystemWindow);
				player.Out.SendQuestUpdate(this);
			}
			else if (gArgs.Target.Name.ToLower() == GLACIERGIANT_NAME.ToLower() && gArgs.Target is GameNPC && _glacierGiantKilled < MAX_KILLED)
			{
				_glacierGiantKilled = 1;
				player.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.WeeklyNamedKilled", GLACIERGIANT_NAME, _glacierGiantKilled, MAX_KILLED), eChatType.CT_ScreenCenter, eChatLoc.CL_SystemWindow);
				player.Out.SendQuestUpdate(this);
			}

			if (_evernKilled >= MAX_KILLED && _greenKnightKilled >= MAX_KILLED && _glacierGiantKilled>= MAX_KILLED)
			{
				// FinishQuest or go back to Haszan
				Step = 2;
			}
		}

		public override void FinishQuest()
		{
			//m_questPlayer.GainExperience(eXPSource.Quest, (m_questPlayer.ExperienceForNextLevel - m_questPlayer.ExperienceForCurrentLevel)/10, true);
			m_questPlayer.AddServerIssuedMoney(Money.GetMoney(0,0,m_questPlayer.Level * 5,32,Util.Random(50)), "You receive {0} as a reward.");
			AtlasROGManager.GenerateReward(m_questPlayer, 1500);
			AtlasROGManager.GenerateJewel(m_questPlayer, (byte)(m_questPlayer.Level + 1), m_questPlayer.Level + Util.Random(10, 11));
			_evernKilled = 0;
			_glacierGiantKilled = 0;
			_greenKnightKilled = 0;
			base.FinishQuest(); //Defined in Quest, changes the state, stores in DB etc ...
		}
	}
}
