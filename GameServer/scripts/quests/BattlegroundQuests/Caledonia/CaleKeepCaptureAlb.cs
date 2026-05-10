using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using DOL.Database;
using DOL.Events;
using DOL.GS;
using DOL.GS.API;
using DOL.GS.Keeps;
using DOL.GS.PacketHandler;
using DOL.GS.PlayerTitles;
using DOL.GS.Quests;

namespace DOL.GS.DailyQuest.Albion
{
	public class CaleKeepCaptureAlb : Quests.DailyQuest
	{
		/// <summary>
		/// Defines a logger for this class.
		/// </summary>
		private static readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);

		private const string questTitle = "[Daily] Caledonia Conquerer";
		private const int minimumLevel = 34;
		private const int maximumLevel = 39;

		// Capture Goal
		private const int MAX_CAPTURED = 1;

		private static GameNPC PazzAlb = null; // Start NPC

		private int _isCaptured = 0;

		// Constructors
		public CaleKeepCaptureAlb() : base()
		{
		}

		public CaleKeepCaptureAlb(GamePlayer questingPlayer) : base(questingPlayer, 1)
		{
		}

		public CaleKeepCaptureAlb(GamePlayer questingPlayer, int step) : base(questingPlayer, step)
		{
		}

		public CaleKeepCaptureAlb(GamePlayer questingPlayer, DbQuest dbQuest) : base(questingPlayer, dbQuest)
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
			GameNPC[] npcs = WorldMgr.GetNPCsByName("Pazz", eRealm.Albion);

			if (npcs.Length > 0)
				foreach (GameNPC npc in npcs)
				{
					if (npc.CurrentRegionID == 250 && npc.X == 37283 && npc.Y == 51881)
					{
						PazzAlb = npc;
						break;
					}
				}

			if (PazzAlb == null)
			{
				if (log.IsWarnEnabled)
					log.Warn("Could not find PazzAlb, creating it ...");
				PazzAlb = new GameNPC();
				PazzAlb.Model = 26;
				PazzAlb.Name = "Pazz";
				PazzAlb.GuildName = "Bone Collector";
				PazzAlb.Realm = eRealm.Albion;
				//Druim Ligen Location
				PazzAlb.CurrentRegionID = 250;
				PazzAlb.Size = 40;
				PazzAlb.Level = 59;
				PazzAlb.X = 37283;
				PazzAlb.Y = 51881;
				PazzAlb.Z = 3944;
				PazzAlb.Heading = 4090;
				PazzAlb.Flags |= GameNPC.eFlags.PEACE;
				PazzAlb.AddToWorld();
				if (SAVE_INTO_DATABASE)
				{
					PazzAlb.SaveIntoDatabase();
				}
			}

			#endregion

			#region defineItems
			#endregion

			#region defineObject
			#endregion

			GameEventMgr.AddHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
			GameEventMgr.AddHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

			GameEventMgr.AddHandler(PazzAlb, GameObjectEvent.Interact, new DOLEventHandler(TalkToHaszan));
			GameEventMgr.AddHandler(PazzAlb, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToHaszan));

			/* Now we bring to Haszan the possibility to give this quest to players */
			PazzAlb.AddQuestToGive(typeof (CaleKeepCaptureAlb));

			if (log.IsInfoEnabled)
				log.Info("Quest \"" + questTitle + "\" initialized");
		}

		[ScriptUnloadedEvent]
		public static void ScriptUnloaded(DOLEvent e, object sender, EventArgs args)
		{
			//if not loaded, don't worry
			if (PazzAlb == null)
				return;
			// remove handlers
			GameEventMgr.RemoveHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
			GameEventMgr.RemoveHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

			GameEventMgr.RemoveHandler(PazzAlb, GameObjectEvent.Interact, new DOLEventHandler(TalkToHaszan));
			GameEventMgr.RemoveHandler(PazzAlb, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToHaszan));

			/* Now we remove to Haszan the possibility to give this quest to players */
			PazzAlb.RemoveQuestToGive(typeof (CaleKeepCaptureAlb));
		}

		private static void TalkToHaszan(DOLEvent e, object sender, EventArgs args)
		{
			//We get the player from the event arguments and check if he qualifies
			GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
			if (player == null)
				return;

			if(PazzAlb.CanGiveQuest(typeof (CaleKeepCaptureAlb), player)  <= 0)
				return;

			//We also check if the player is already doing the quest
			CaleKeepCaptureAlb quest = player.IsDoingQuest(typeof (CaleKeepCaptureAlb)) as CaleKeepCaptureAlb;

			if (e == GameObjectEvent.Interact)
			{
				if (quest != null)
				{
					switch (quest.Step)
					{
						case 1:
							PazzAlb.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.CaptureKeepObjective"));
							break;
						case 2:
							PazzAlb.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.CaptureKeepPrompt", player.Name));
							break;
					}
				}
				else
				{
					PazzAlb.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.BGKeepIntro", player.Name));
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
						case "help a skeleton":
							player.Out.SendQuestSubscribeCommand(PazzAlb, QuestMgr.GetIDForQuestType(typeof(CaleKeepCaptureAlb)), DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.HelpNpcWithQuest", "Pazz", questTitle));
							break;
					}
				}
				else
				{
					switch (wArgs.Text)
					{
						case "capture":
						case "점령":
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
			if (player.IsDoingQuest(typeof (CaleKeepCaptureAlb)) != null)
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
			CaleKeepCaptureAlb quest = player.IsDoingQuest(typeof (CaleKeepCaptureAlb)) as CaleKeepCaptureAlb;

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

		protected static void SubscribeQuest(DOLEvent e, object sender, EventArgs args)
		{
			QuestEventArgs qargs = args as QuestEventArgs;
			if (qargs == null)
				return;

			if (qargs.QuestID != QuestMgr.GetIDForQuestType(typeof(CaleKeepCaptureAlb)))
				return;

			if (e == GamePlayerEvent.AcceptQuest)
				CheckPlayerAcceptQuest(qargs.Player, 0x01);
			else if (e == GamePlayerEvent.DeclineQuest)
				CheckPlayerAcceptQuest(qargs.Player, 0x00);
		}

		private static void CheckPlayerAcceptQuest(GamePlayer player, byte response)
		{
			if(PazzAlb.CanGiveQuest(typeof (CaleKeepCaptureAlb), player)  <= 0)
				return;

			if (player.IsDoingQuest(typeof (CaleKeepCaptureAlb)) != null)
				return;

			if (response == 0x00)
			{
				player.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.ThanksForHelp"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
			}
			else
			{
				//Check if we can add the quest!
				if (!PazzAlb.GiveQuest(typeof (CaleKeepCaptureAlb), player, 1))
					return;

				PazzAlb.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.EnrichmentRealm", player.Name));

			}
		}

		//Set quest name
		public override string Name
		{
			get { return questTitle; }
		}

		// Define Steps
		public override string Description
		{
			get
			{
				switch (Step)
				{
					case 1:
						return DOL.Language.LanguageMgr.GetTranslation(m_questPlayer.Client.Account.Language, "Quest.Common.KeepCaptureDescription", _isCaptured, 1);
					case 2:
						return DOL.Language.LanguageMgr.GetTranslation(m_questPlayer.Client.Account.Language, "Quest.Common.ReturnToPazz", "Caledonia Portal Keep");
				}
				return base.Description;
			}
		}

		public override void Notify(DOLEvent e, object sender, EventArgs args)
		{
			GamePlayer player = sender as GamePlayer;

			if (player?.IsDoingQuest(typeof(CaleKeepCaptureAlb)) == null)
				return;

			if (sender != m_questPlayer)
				return;

			if (Step != 1 || e != GamePlayerEvent.CapturedKeepsChanged) return;
			_isCaptured = 1;
			player.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.DailyCapturedKeep", _isCaptured, MAX_CAPTURED), eChatType.CT_ScreenCenter, eChatLoc.CL_SystemWindow);
			player.Out.SendQuestUpdate(this);

			if (_isCaptured >= MAX_CAPTURED)
			{
				// FinishQuest or go back to Dean
				Step = 2;
			}

		}

		public override string QuestPropertyKey
		{
			get => "CaleKeepCaptureAlb";
			set { ; }
		}

		public override void LoadQuestParameters()
		{

		}

		public override void SaveQuestParameters()
		{

		}

		public override void AbortQuest()
		{
			base.AbortQuest(); //Defined in Quest, changes the state, stores in DB etc ...
		}

		public override void FinishQuest()
		{
			if (m_questPlayer.Inventory.IsSlotsFree(1, eInventorySlot.FirstBackpack, eInventorySlot.LastBackpack))
			{
				m_questPlayer.ForceGainExperience((m_questPlayer.ExperienceForNextLevel - m_questPlayer.ExperienceForCurrentLevel) / 2);
				m_questPlayer.AddMoney(Money.GetMoney(0, 0, m_questPlayer.Level * 2, 0, Util.Random(50)),
					"You receive {0} as a reward.");
				AtlasROGManager.GenerateBattlegroundToken(m_questPlayer, 1);
				_isCaptured = 0;
				base.FinishQuest(); //Defined in Quest, changes the state, stores in DB etc ...
			}
			else
			{
				m_questPlayer.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(m_questPlayer.Client.Account.Language, "Quest.Common.ClearInventorySlots", 1), eChatType.CT_System, eChatLoc.CL_SystemWindow);
			}
		}
	}
}
