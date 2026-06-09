using System;
using System.Reflection;
using DOL.Database;
using DOL.Events;
using DOL.GS.PacketHandler;
using DOL.GS.Quests;

namespace DOL.GS.DailyQuest
{
	public class HardcoreKillNPCInFrontiersAlb : Quests.DailyQuest
	{
		/// <summary>
		/// Defines a logger for this class.
		/// </summary>
		private static readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);

		private const string questTitle = "[Hardcore] A Bit of Bravery";
		private const int minimumLevel = 1;
		private const int maximumLevel = 50;

		private static GameNPC SucciAlb = null; // Start NPC

		private int FrontierMobsKilled = 0;
		private int MAX_KillGoal = 25;

		// Constructors
		public HardcoreKillNPCInFrontiersAlb() : base()
		{
		}

		public HardcoreKillNPCInFrontiersAlb(GamePlayer questingPlayer) : base(questingPlayer)
		{
		}

		public HardcoreKillNPCInFrontiersAlb(GamePlayer questingPlayer, int step) : base(questingPlayer, step)
		{
		}

		public HardcoreKillNPCInFrontiersAlb(GamePlayer questingPlayer, DbQuest dbQuest) : base(questingPlayer, dbQuest)
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

			GameNPC[] npcs = WorldMgr.GetNPCsByName("Succi", eRealm.Albion);

			if (npcs.Length > 0)
				foreach (GameNPC npc in npcs)
				{
					if (npc.CurrentRegionID == 1 && npc.X == 584652 && npc.Y == 477773)
					{
						SucciAlb = npc;
						break;
					}
				}

			if (SucciAlb == null)
			{
				if (log.IsWarnEnabled)
					log.Warn("Could not find SucciAlb , creating it ...");
				SucciAlb = new GameNPC();
				SucciAlb.Model = 902;
				SucciAlb.Name = "Succi";
				SucciAlb.GuildName = "Spectre of Death";
				SucciAlb.Realm = eRealm.Albion;
				//Sauvage Location
				SucciAlb.CurrentRegionID = 1;
				SucciAlb.Size = 60;
				SucciAlb.Level = 59;
				SucciAlb.X = 584652;
				SucciAlb.Y = 477773;
				SucciAlb.Z = 2600;
				SucciAlb.Heading = 2257;
				SucciAlb.Flags |= GameNPC.eFlags.PEACE;
				SucciAlb.AddToWorld();
				if (SAVE_INTO_DATABASE)
				{
					SucciAlb.SaveIntoDatabase();
				}
			}

			#endregion

			#region defineItems
			#endregion

			#region defineObject
			#endregion

			GameEventMgr.AddHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
			GameEventMgr.AddHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

			GameEventMgr.AddHandler(SucciAlb, GameObjectEvent.Interact, new DOLEventHandler(TalkToSucci));
			GameEventMgr.AddHandler(SucciAlb, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToSucci));

			/* Now we bring to Dean the possibility to give this quest to players */
			SucciAlb.AddQuestToGive(typeof (HardcoreKillNPCInFrontiersAlb));

			if (log.IsInfoEnabled)
				log.Info("Quest \"" + questTitle + "\" initialized");
		}

		[ScriptUnloadedEvent]
		public static void ScriptUnloaded(DOLEvent e, object sender, EventArgs args)
		{
			//if not loaded, don't worry
			if (SucciAlb == null)
				return;
			// remove handlers
			GameEventMgr.RemoveHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
			GameEventMgr.RemoveHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

			GameEventMgr.RemoveHandler(SucciAlb, GameObjectEvent.Interact, new DOLEventHandler(TalkToSucci));
			GameEventMgr.RemoveHandler(SucciAlb, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToSucci));

			/* Now we remove to Dean the possibility to give this quest to players */
			SucciAlb.RemoveQuestToGive(typeof (HardcoreKillNPCInFrontiersAlb));
		}

		private static void TalkToSucci(DOLEvent e, object sender, EventArgs args)
		{
			//We get the player from the event arguments and check if he qualifies
			GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
			if (player == null)
				return;

			if (SucciAlb.CanGiveQuest(typeof(HardcoreKillNPCInFrontiersAlb), player) <= 0)
				return;

			//We also check if the player is already doing the quest
			HardcoreKillNPCInFrontiersAlb oranges = player.IsDoingQuest(typeof (HardcoreKillNPCInFrontiersAlb)) as HardcoreKillNPCInFrontiersAlb;

			if (e == GameObjectEvent.Interact)
			{
				if (oranges != null)
				{
					switch (oranges.Step)
					{
						case 1:
							SucciAlb.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Hardcore.ExemplifyBravery"));
							break;
						case 2:
							SucciAlb.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Hardcore.EarnedAnotherSunrise", player.Name));
							break;
					}
				}
				else
				{
					SucciAlb.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Hardcore.BraveWhenAfraid"));
					SucciAlb.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Hardcore.Warning"));
				}
			}
				// The player whispered to the NPC
			else if (e == GameLivingEvent.WhisperReceive)
			{
				WhisperReceiveEventArgs wArgs = (WhisperReceiveEventArgs) args;
				if (oranges == null)
				{
					switch (wArgs.Text.ToLower())
					{
						case "one can be brave":
						case "용기를 낼 수 있습니다":
							player.Out.SendQuestSubscribeCommand(SucciAlb, QuestMgr.GetIDForQuestType(typeof(HardcoreKillNPCInFrontiersAlb)), DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.SubscribePrompt", questTitle));
							break;
					}
				}
				else
				{
					switch (wArgs.Text)
					{
						case "another sunrise":
						case "또 하나의 일출":
							if (oranges.Step == 2)
							{
								player.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Hardcore.EnjoyMeal"), eChatType.CT_Chat, eChatLoc.CL_PopupWindow);
								oranges.FinishQuest();
							}
							break;
						case "abort":
							player.Out.SendCustomDialog(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Hardcore.DeathRejected"), new CustomDialogResponse(CheckPlayerAbortQuest));
							break;
					}
				}
			}
		}

		public override bool CheckQuestQualification(GamePlayer player)
		{
			// if the player is already doing the quest his level is no longer of relevance
			if (player.IsDoingQuest(typeof (HardcoreKillNPCInFrontiersAlb)) != null)
				return true;

			// This checks below are only performed is player isn't doing quest already

			if (player.Level < minimumLevel || player.Level > maximumLevel)
				return false;

			return true;
		}

		private static void CheckPlayerAbortQuest(GamePlayer player, byte response)
		{
			HardcoreKillNPCInFrontiersAlb oranges = player.IsDoingQuest(typeof (HardcoreKillNPCInFrontiersAlb)) as HardcoreKillNPCInFrontiersAlb;

			if (oranges == null)
				return;

			if (response == 0x00)
			{
				SendSystemMessage(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Hardcore.DeathRejected"));
			}
			else
			{
				SendSystemMessage(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.AbortingQuest", questTitle));
				oranges.AbortQuest();
			}
		}

		private static void SubscribeQuest(DOLEvent e, object sender, EventArgs args)
		{
			QuestEventArgs qargs = args as QuestEventArgs;
			if (qargs == null)
				return;

			if (qargs.QuestID != QuestMgr.GetIDForQuestType(typeof(HardcoreKillNPCInFrontiersAlb)))
				return;

			if (e == GamePlayerEvent.AcceptQuest)
				CheckPlayerAcceptQuest(qargs.Player, 0x01);
			else if (e == GamePlayerEvent.DeclineQuest)
				CheckPlayerAcceptQuest(qargs.Player, 0x00);
		}

		private static void CheckPlayerAcceptQuest(GamePlayer player, byte response)
		{
			if(SucciAlb.CanGiveQuest(typeof (HardcoreKillNPCInFrontiersAlb), player)  <= 0)
				return;

			if (player.IsDoingQuest(typeof (HardcoreKillNPCInFrontiersAlb)) != null)
				return;

			if (player.Group != null)
				return;

			if (response == 0x00)
			{
				player.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Hardcore.WatchYourBack"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
			}
			else
			{
				//Check if we can add the quest!
				if (!SucciAlb.GiveQuest(typeof (HardcoreKillNPCInFrontiersAlb), player, 1))
					return;

				SucciAlb.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Hardcore.BraveWarning"));

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
					case -1:
						return DOL.Language.LanguageMgr.GetTranslation(m_questPlayer.Client.Account.Language, "Quest.Hardcore.DoneToday");
					case 1:
						return DOL.Language.LanguageMgr.GetTranslation(m_questPlayer.Client.Account.Language, "Quest.Hardcore.KillNpcDescription", FrontierMobsKilled, MAX_KillGoal);
					case 2:
						return DOL.Language.LanguageMgr.GetTranslation(m_questPlayer.Client.Account.Language, "Quest.Hardcore.ReturnToSucciAlb");
				}
				return base.Description;
			}
		}

		public override void Notify(DOLEvent e, object sender, EventArgs args)
		{
			GamePlayer player = sender as GamePlayer;

			if (player?.IsDoingQuest(typeof(HardcoreKillNPCInFrontiersAlb)) == null)
				return;

			if(player.Group != null && Step == 1)
				FailQuest();

			if (sender != m_questPlayer)
				return;

			if (e == GameLivingEvent.Dying && Step == 1)
			{
				FailQuest();
			}

			if (e != GameLivingEvent.EnemyKilled || Step != 1) return;

			EnemyKilledEventArgs gArgs = (EnemyKilledEventArgs) args;

			if (gArgs.Target is GameSummonedPet)
				return;

			if (!(player.GetConLevel(gArgs.Target) > -1) || !gArgs.Target.CurrentZone.IsRvR ||
			    !player.CurrentZone.IsRvR) return;
			if (gArgs.Target.XPGainers.Count > 1)
			{
				Array gainers = new GameObject[gArgs.Target.XPGainers.Count];
				lock (gArgs.Target.XpGainersLock)
				{

					foreach (GameLiving living in gArgs.Target.XPGainers.Keys)
					{
						if (living == player ||
						    (player.ControlledBrain is {Body: { }} && player.ControlledBrain.Body == living) ||
						    (living is BdPet bdpet &&
						     (bdpet.Owner == player || bdpet.Owner == player.ControlledBrain?.Body)))
							continue;

						return;
					}
				}
			}
			FrontierMobsKilled++;
			player.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.HardcoreMonsterKilled", FrontierMobsKilled, MAX_KillGoal), eChatType.CT_ScreenCenter, eChatLoc.CL_SystemWindow);
			player.Out.SendQuestUpdate(this);

			if (FrontierMobsKilled >= MAX_KillGoal)
			{
				// FinishQuest or go back to npc
				Step = 2;
			}

		}

		public override string QuestPropertyKey
		{
			get => "HardcoreKillNPCInFrontiersAlb";
			set { ; }
		}

		public override void LoadQuestParameters()
		{
			FrontierMobsKilled = GetCustomProperty(QuestPropertyKey) != null ? int.Parse(GetCustomProperty(QuestPropertyKey)) : 0;
		}

		public override void SaveQuestParameters()
		{
			SetCustomProperty(QuestPropertyKey, FrontierMobsKilled.ToString());
		}


		public override void FinishQuest()
		{
			m_questPlayer.ForceGainExperience((m_questPlayer.ExperienceForNextLevel - m_questPlayer.ExperienceForCurrentLevel)/2);
			m_questPlayer.AddServerIssuedMoney(Money.GetMoney(0,0,m_questPlayer.Level*2,32,Util.Random(50)), "You receive {0} as a reward.");
			AtlasROGManager.GenerateReward(m_questPlayer, 150);
			FrontierMobsKilled = 0;
			base.FinishQuest(); //Defined in Quest, changes the state, stores in DB etc ...

		}

		private void FailQuest()
		{
			m_questPlayer.Out.SendMessage(questTitle + " failed.", eChatType.CT_ScreenCenter_And_CT_System, eChatLoc.CL_SystemWindow);
			FrontierMobsKilled = 0;
			Step = -1;

			if (m_questPlayer.QuestList.TryRemove(this, out byte value))
				m_questPlayer.AvailableQuestIndexes.Enqueue(value);

			m_questPlayer.AddFinishedQuest(this);
			m_questPlayer.Out.SendQuestListUpdate();
		}
	}
}
