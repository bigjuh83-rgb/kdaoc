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

namespace DOL.GS.MonthlyQuest.Hibernia
{
	public class CaptureRelicQuestHib : Quests.MonthlyQuest
	{
		/// <summary>
		/// Defines a logger for this class.
		/// </summary>
		private static readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);

		private const string questTitle = "[Monthly] Aspiring Relic Guardian";
		private const int minimumLevel = 50;
		private const int maximumLevel = 50;

		// Capture Goal
		private const int MAX_CAPTURED = 1;

		private static GameNPC Kelteen = null; // Start NPC

		private int _isCaptured = 0;

		// Constructors
		public CaptureRelicQuestHib() : base()
		{
		}

		public CaptureRelicQuestHib(GamePlayer questingPlayer) : base(questingPlayer, 1)
		{
		}

		public CaptureRelicQuestHib(GamePlayer questingPlayer, int step) : base(questingPlayer, step)
		{
		}

		public CaptureRelicQuestHib(GamePlayer questingPlayer, DbQuest dbQuest) : base(questingPlayer, dbQuest)
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

			GameNPC[] npcs = WorldMgr.GetNPCsByName("Kelteen", eRealm.Hibernia);

			if (npcs.Length > 0)
				foreach (GameNPC npc in npcs)
				{
					if (npc.CurrentRegionID == 200 && npc.X == 334215 && npc.Y == 421276)
					{
						Kelteen = npc;
						break;
					}
				}

			if (Kelteen == null)
			{
				if (log.IsWarnEnabled)
					log.Warn("Could not find KelteenHib, creating it ...");
				Kelteen = new GameNPC();
				Kelteen.Model = 315;
				Kelteen.Name = "Kelteen";
				Kelteen.GuildName = "Atlas Logistics";
				Kelteen.Realm = eRealm.Hibernia;
				//Druim Ligen Location
				Kelteen.CurrentRegionID = 200;
				Kelteen.Size = 60;
				Kelteen.Level = 59;
				Kelteen.X = 334215;
				Kelteen.Y = 421276;
				Kelteen.Z = 5180;
				Kelteen.Heading = 1566;
				Kelteen.Flags |= GameNPC.eFlags.PEACE;
				GameNpcInventoryTemplate templateHib = new GameNpcInventoryTemplate();
				templateHib.AddNPCEquipment(eInventorySlot.Cloak, 1722);
				templateHib.AddNPCEquipment(eInventorySlot.HeadArmor, 1288);
				templateHib.AddNPCEquipment(eInventorySlot.TorsoArmor, 2517);
				templateHib.AddNPCEquipment(eInventorySlot.HandsArmor, 1645);
				templateHib.AddNPCEquipment(eInventorySlot.FeetArmor, 1643);
				templateHib.AddNPCEquipment(eInventorySlot.DistanceWeapon, 3239);
				Kelteen.Inventory = templateHib.CloseTemplate();
				Kelteen.VisibleActiveWeaponSlots = (byte) eInventorySlot.DistanceWeapon;
				Kelteen.AddToWorld();
				if (SAVE_INTO_DATABASE)
				{
					Kelteen.SaveIntoDatabase();
				}
			}

			#endregion

			#region defineItems
			#endregion

			#region defineObject
			#endregion

			GameEventMgr.AddHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
			GameEventMgr.AddHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

			GameEventMgr.AddHandler(Kelteen, GameObjectEvent.Interact, new DOLEventHandler(TalkToKelteen));
			GameEventMgr.AddHandler(Kelteen, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToKelteen));

			/* Now we bring to Kelteen the possibility to give this quest to players */
			Kelteen.AddQuestToGive(typeof (CaptureRelicQuestHib));

			if (log.IsInfoEnabled)
				log.Info("Quest \"" + questTitle + "\" initialized");
		}

		[ScriptUnloadedEvent]
		public static void ScriptUnloaded(DOLEvent e, object sender, EventArgs args)
		{
			//if not loaded, don't worry
			if (Kelteen == null)
				return;
			// remove handlers
			GameEventMgr.RemoveHandler(GamePlayerEvent.AcceptQuest, new DOLEventHandler(SubscribeQuest));
			GameEventMgr.RemoveHandler(GamePlayerEvent.DeclineQuest, new DOLEventHandler(SubscribeQuest));

			GameEventMgr.RemoveHandler(Kelteen, GameObjectEvent.Interact, new DOLEventHandler(TalkToKelteen));
			GameEventMgr.RemoveHandler(Kelteen, GameLivingEvent.WhisperReceive, new DOLEventHandler(TalkToKelteen));

			/* Now we remove to Kelteen the possibility to give this quest to players */
			Kelteen.RemoveQuestToGive(typeof (CaptureRelicQuestHib));
		}

		private static void TalkToKelteen(DOLEvent e, object sender, EventArgs args)
		{
			//We get the player from the event arguments and check if he qualifies
			GamePlayer player = ((SourceEventArgs) args).Source as GamePlayer;
			if (player == null)
				return;

			if(Kelteen.CanGiveQuest(typeof (CaptureRelicQuestHib), player)  <= 0)
				return;

			//We also check if the player is already doing the quest
			CaptureRelicQuestHib quest = player.IsDoingQuest(typeof (CaptureRelicQuestHib)) as CaptureRelicQuestHib;

			if (e == GameObjectEvent.Interact)
			{
				if (quest != null)
				{
					switch (quest.Step)
					{
						case 1:
							Kelteen.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.CaptureRelicObjective", "Albion", "Midgard"));
							break;
						case 2:
							Kelteen.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.DidYouToken", player.Name, "[capture] a relic"));
							break;
					}
				}
				else
				{
					Kelteen.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.CaptureRelicIntro", player.Name, "Albion", "Midgard"));
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
						case "securing a foothold":
							player.Out.SendQuestSubscribeCommand(Kelteen, QuestMgr.GetIDForQuestType(typeof(CaptureRelicQuestHib)), DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.HelpNpcQuest", "Kelteen", questTitle));
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
			if (player.IsDoingQuest(typeof (CaptureRelicQuestHib)) != null)
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
			CaptureRelicQuestHib quest = player.IsDoingQuest(typeof (CaptureRelicQuestHib)) as CaptureRelicQuestHib;

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

			if (qargs.QuestID != QuestMgr.GetIDForQuestType(typeof(CaptureRelicQuestHib)))
				return;

			if (e == GamePlayerEvent.AcceptQuest)
				CheckPlayerAcceptQuest(qargs.Player, 0x01);
			else if (e == GamePlayerEvent.DeclineQuest)
				CheckPlayerAcceptQuest(qargs.Player, 0x00);
		}

		private static void CheckPlayerAcceptQuest(GamePlayer player, byte response)
		{
			if(Kelteen.CanGiveQuest(typeof (CaptureRelicQuestHib), player)  <= 0)
				return;

			if (player.IsDoingQuest(typeof (CaptureRelicQuestHib)) != null)
				return;

			if (response == 0x00)
			{
				player.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.ThanksForHelpingRealm", "Hibernia"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
			}
			else
			{
				//Check if we can add the quest!
				if (!Kelteen.GiveQuest(typeof (CaptureRelicQuestHib), player, 1))
					return;

				Kelteen.SayTo(player, DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.TrueGuardianRealm", player.Name, "Hibernia"));

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
						return DOL.Language.LanguageMgr.GetTranslation(m_questPlayer.Client.Account.Language, "Quest.Common.CaptureRelicDescription", "Albion", "Midgard", _isCaptured, MAX_CAPTURED);
					case 2:
						return DOL.Language.LanguageMgr.GetTranslation(m_questPlayer.Client.Account.Language, "Quest.Common.ReturnToNpc", "Kelteen");
				}
				return base.Description;
			}
		}

		public override void Notify(DOLEvent e, object sender, EventArgs args)
		{
			GamePlayer player = sender as GamePlayer;

			if (player?.IsDoingQuest(typeof(CaptureRelicQuestHib)) == null)
				return;

			if (sender != m_questPlayer)
				return;

			if (Step != 1 || e != GamePlayerEvent.CapturedRelicsChanged) return;
			_isCaptured = 1;
			player.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(player.Client.Account.Language, "Quest.Common.MonthlyCapturedRelic", _isCaptured, MAX_CAPTURED), eChatType.CT_ScreenCenter, eChatLoc.CL_SystemWindow);
			player.Out.SendQuestUpdate(this);

			if (_isCaptured >= MAX_CAPTURED)
			{
				// FinishQuest or go back to Dean
				Step = 2;
			}

		}

		public override string QuestPropertyKey
		{
			get => "CaptureRelicQuestHib";
			set { ; }
		}

		public override void LoadQuestParameters()
		{
			_isCaptured = GetCustomProperty(QuestPropertyKey) != null ? int.Parse(GetCustomProperty(QuestPropertyKey)) : 0;
		}

		public override void SaveQuestParameters()
		{
			SetCustomProperty(QuestPropertyKey, _isCaptured.ToString());
		}

		public override void FinishQuest()
		{
			int reward = ServerProperties.Properties.MONTHLY_RVR_REWARD;

			if (m_questPlayer.Inventory.IsSlotsFree(3, eInventorySlot.FirstBackpack, eInventorySlot.LastBackpack))
			{
				m_questPlayer.ForceGainExperience((m_questPlayer.ExperienceForNextLevel - m_questPlayer.ExperienceForCurrentLevel));
				m_questPlayer.AddServerIssuedMoney(Money.GetMoney(0,0,m_questPlayer.Level*8,0,Util.Random(50)), "You receive {0} as a reward.");
				AtlasROGManager.GenerateReward(m_questPlayer, 5000);
				AtlasROGManager.GenerateJewel(m_questPlayer, 51);
				_isCaptured = 0;

				if (reward > 0)
				{
					m_questPlayer.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(m_questPlayer.Client.Account.Language, "Quest.Common.RealmPointReward", reward, "Monthly"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
					m_questPlayer.GainRealmPoints(reward, false);
					m_questPlayer.Out.SendUpdatePlayer();
				}
				base.FinishQuest(); //Defined in Quest, changes the state, stores in DB etc ...
			}
			else
			{
				m_questPlayer.Out.SendMessage(DOL.Language.LanguageMgr.GetTranslation(m_questPlayer.Client.Account.Language, "Quest.Common.ClearInventorySlots", 3), eChatType.CT_System, eChatLoc.CL_SystemWindow);
			}
		}
	}
}
