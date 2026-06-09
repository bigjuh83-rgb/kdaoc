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

namespace DOL.GS.WeeklyQuest.Hibernia
{
	public class DFWeeklyKillQuestHib : Quests.WeeklyQuest
	{
		/// <summary>
		/// Defines a logger for this class.
		/// </summary>
		private static readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);

		private const string questTitle = "[Weekly] Femurs From Darkness Falls";
		private const int minimumLevel = 15;
		private const int maximumLevel = 50;

		// prevent grey killing
		private const int MIN_PLAYER_CON = -3;
		// Kill Goal
		private const int MAX_KILLED = 50;

		private static GameNPC Stefano = null; // Start NPC

		private int EnemiesKilled = 0;

		// Constructors
		public DFWeeklyKillQuestHib() : base()
		{
		}

		public DFWeeklyKillQuestHib(GamePlayer questingPlayer) : base(questingPlayer)
		{
		}

		public DFWeeklyKillQuestHib(GamePlayer questingPlayer, int step) : base(questingPlayer, step)
		{
		}

		public DFWeeklyKillQuestHib(GamePlayer questingPlayer, DbQuest dbQuest) : base(questingPlayer, dbQuest)
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

			GameNPC[] npcs = WorldMgr.GetNPCsByName("Stefano", eRealm.Hibernia);

			if (npcs.Length > 0)
				foreach (GameNPC npc in npcs)
					if (npc.CurrentRegionID == 249 && npc.X == 46083 && npc.Y == 39681)
					{
						Stefano = npc;
						break;
					}

			if (Stefano == null)
			{
				if (log.IsWarnEnabled)
					log.Warn("Could not find Stefano , creating it ...");
				Stefano = new GameNPC();
				Stefano.Model = 306;
				Stefano.Name = "Stefano";
				Stefano.GuildName = "Realm Logistics";
				Stefano.Realm = eRealm.Hibernia;
				//Darkness Falls Hib Entrance Location
				Stefano.CurrentRegionID = 249;
				Stefano.Size = 50;
				Stefano.Level = 59;
				Stefano.X = 46083;
				Stefano.Y = 39681;
				Stefano.Z = 21357;
				Stefano.Heading = 3066;
				Stefano.Flags |= GameNPC.eFlags.PEACE;
				GameNpcInventoryTemplate templateHib = new GameNpcInventoryTemplate();
				templateHib.AddNPCEquipment(eInventorySlot.TorsoArmor, 734,0,0,3);
				templateHib.AddNPCEquipment(eInventorySlot.LegsArmor, 735);
				templateHib.AddNPCEquipment(eInventorySlot.ArmsArmor, 736);
				templateHib.AddNPCEquipment(eInventorySlot.HandsArmor, 737, 0,0,3);
				templateHib.AddNPCEquipment(eInventorySlot.FeetArmor, 738, 0, 0, 3);
				templateHib.AddNPCEquipment(eInventorySlot.Cloak, 678);
				Stefano.Inventory = templateHib.CloseTemplate();
				Stefano.AddToWorld();
				if (SAVE_INTO_DATABASE)
				{
					Stefano.SaveIntoDatabase();
				}
			}

			#endregion

			#region defineItems
			#endregion

			#region defineObject
			#endregion

			GameEventMgr.AddHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
			GameEventMgr.AddHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

			GameEventMgr.AddHandler(Stefano, GameObjectEvent.Interact, new DOLEventHandler(TalkToStefano));
			GameEventMgr.AddHandler(Stefano, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToStefano));

			Stefano.AddQuestToGive(typeof (DFWeeklyKillQuestHib));

			if (log.IsInfoEnabled)
				log.Info("Quest \"" + questTitle + "\" initialized");
		}

		[ScriptUnloadedEvent]
		public static void ScriptUnloaded(DOLEvent e, object sender, EventArgs args)
		{
			//if not loaded, don't worry
			if (Stefano == null)
				return;
			// remove handlers
			GameEventMgr.RemoveHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
			GameEventMgr.RemoveHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

			GameEventMgr.RemoveHandler(Stefano, GameObjectEvent.Interact, new DOLEventHandler(TalkToStefano));
			GameEventMgr.RemoveHandler(Stefano, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToStefano));

			Stefano.RemoveQuestToGive(typeof (DFWeeklyKillQuestHib));
		}

		private static void TalkToStefano(DOLEvent e, object sender, EventArgs args)
		{
			//We get the player from the event arguments and check if he qualifies
			GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
			if (player == null)
				return;

			if(Stefano.CanGiveQuest(typeof (DFWeeklyKillQuestHib), player)  <= 0)
				return;

			//We also check if the player is already doing the quest
			DFWeeklyKillQuestHib quest = player.IsDoingQuest(typeof (DFWeeklyKillQuestHib)) as DFWeeklyKillQuestHib;

			if (e == GameObjectEvent.Interact)
			{
				if (quest != null)
				{
					switch (quest.Step)
					{
						case 1:
							Stefano.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.DFEnemyPrompt", "Hibernia"));
							break;
						case 2:
							Stefano.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.DidYouToken", player.Name, "[find the bones] we needed"));
							break;
					}
				}
				else
				{
					Stefano.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.DFEnemyIntro", player.Name));
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
						case "demonic aura":
						case "악마의 기운":
							player.Out.SendQuestSubscribeCommand(Stefano, QuestMgr.GetIDForQuestType(typeof(DFWeeklyKillQuestHib)), DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.HelpNpcWithQuest", "Stefano", questTitle));
							break;
					}
				}
				else
				{
					switch (wArgs.Text)
					{
						case "find the bones":
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

		public override bool CheckQuestQualification(GamePlayer player)
		{
			// if the player is already doing the quest his level is no longer of relevance
			if (player.IsDoingQuest(typeof (DFWeeklyKillQuestHib)) != null)
				return true;

			// This checks below are only performed is player isn't doing quest already

			//if (player.HasFinishedQuest(typeof(Academy_47)) == 0) return false;

			//if (!CheckPartAccessible(player,typeof(CityOfCamelot)))
			//	return false;

			if (player.Level < minimumLevel || player.Level > maximumLevel)
				return false;

			return true;
		}

		private static void CheckPlayerAbortQuest(GamePlayer player, byte response)
		{
			DFWeeklyKillQuestHib quest = player.IsDoingQuest(typeof (DFWeeklyKillQuestHib)) as DFWeeklyKillQuestHib;

			if (quest == null)
				return;

			if (response == 0x00)
			{
				SendSystemMessage(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.ContinueQuestWork"));
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

			if (qargs.QuestID != QuestMgr.GetIDForQuestType(typeof(DFWeeklyKillQuestHib)))
				return;

			if (e == GamePlayerEvent.AcceptQuest)
				CheckPlayerAcceptQuest(qargs.Player, 0x01);
			else if (e == GamePlayerEvent.DeclineQuest)
				CheckPlayerAcceptQuest(qargs.Player, 0x00);
		}

		private static void CheckPlayerAcceptQuest(GamePlayer player, byte response)
		{
			if(Stefano.CanGiveQuest(typeof (DFWeeklyKillQuestHib), player)  <= 0)
				return;

			if (player.IsDoingQuest(typeof (DFWeeklyKillQuestHib)) != null)
				return;

			if (response == 0x00)
			{
				player.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.ThanksForHelp"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
			}
			else
			{
				//Check if we can add the quest!
				if (!Stefano.GiveQuest(typeof (DFWeeklyKillQuestHib), player, 1))
					return;

				Stefano.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.DFEnemyReminder"));

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
						return DOL.Language.LanguageMgr.GetTranslation(m_questPlayer.Client.Account.Language, "Quest.Common.DFEnemyDescription", "Hibernia", EnemiesKilled, MAX_KILLED);
					case 2:
						return DOL.Language.LanguageMgr.GetTranslation(m_questPlayer.Client.Account.Language, "Quest.Common.ReturnToNpcLocation", "Stefano", "Darkness Falls");
				}
				return base.Description;
			}
		}

		public override void Notify(DOLEvent e, object sender, EventArgs args)
		{
			GamePlayer player = sender as GamePlayer;

			if (player == null || player.IsDoingQuest(typeof(DFWeeklyKillQuestHib)) == null)
				return;

			if (sender != m_questPlayer)
				return;

			if (Step != 1 || e != GameLivingEvent.EnemyKilled) return;
			EnemyKilledEventArgs gArgs = (EnemyKilledEventArgs) args;

			//prevent grey killing
			if (gArgs.Target.Realm == 0 || gArgs.Target.Realm == player.Realm || gArgs.Target is not GamePlayer ||
			    !(player.GetConLevel(gArgs.Target) > MIN_PLAYER_CON) || gArgs.Target.CurrentRegionID != 249) return;
			EnemiesKilled++;
			player.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.WeeklyEnemyKilled", EnemiesKilled, MAX_KILLED), eChatType.CT_ScreenCenter, eChatLoc.CL_SystemWindow);
			player.Out.SendQuestUpdate(this);

			if (EnemiesKilled >= MAX_KILLED)
			{
				Step = 2;
			}

		}

		public override string QuestPropertyKey
		{
			get => "DFWeeklyKillQuestHib";
			set { ; }
		}

		public override void LoadQuestParameters()
		{
			EnemiesKilled = GetCustomProperty(QuestPropertyKey) != null ? int.Parse(GetCustomProperty(QuestPropertyKey)) : 0;
		}

		public override void SaveQuestParameters()
		{
			SetCustomProperty(QuestPropertyKey, EnemiesKilled.ToString());
		}

		public override void FinishQuest()
		{
			int reward = ServerProperties.Properties.WEEKLY_RVR_REWARD;

			m_questPlayer.ForceGainExperience((m_questPlayer.ExperienceForNextLevel - m_questPlayer.ExperienceForCurrentLevel));
			m_questPlayer.AddServerIssuedMoney(Money.GetMoney(0,0,m_questPlayer.Level * 5,32,Util.Random(50)), "You receive {0} as a reward.");
			AtlasROGManager.GenerateReward(m_questPlayer, 1500);
			EnemiesKilled = 0;

			if (reward > 0)
			{
				m_questPlayer.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(m_questPlayer.Client.Account.Language, "Quest.Common.RealmPointReward", reward, "Weekly"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
				m_questPlayer.GainRealmPoints(reward, false);
				m_questPlayer.Out.SendUpdatePlayer();
			}
			base.FinishQuest(); //Defined in Quest, changes the state, stores in DB etc ...

		}
	}
}
