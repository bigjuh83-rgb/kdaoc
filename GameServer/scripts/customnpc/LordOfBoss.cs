using System;
using DOL.Events;
using DOL.GS.PacketHandler;
using System.Collections.Generic;
using System.Reflection;
using DOL.AI.Brain;
using DOL.GS.API;
using DOL.Language;

namespace DOL.GS {
    public class LordOfBoss : GameTrainingDummy {

	    public override bool AddToWorld()
        {
            Name = "Mordbro";
            GuildName = "Lord Of Bosses";
            Realm = 0;
            Model = 1903;
            Size = 60;
            Level = 75;
            Inventory = new GameNPCInventory(GameNpcInventoryTemplate.EmptyTemplate);
            SetOwnBrain(new LordOfBossBrain());

            return base.AddToWorld(); // Finish up and add him to the world.
        }

        public override bool Interact(GamePlayer player)
        {
	        bool inFight = false;

	        if (!base.Interact(player)) return false;
	        if (player.InCombatInLast(10000)) return false;
	        TurnTo(player.X, player.Y);

	        foreach (GameNPC npc in WorldMgr.GetNPCsFromRegion(player.CurrentRegionID))
	        {
		        if (npc.Brain is LordOfBossBrain || npc.Name.Contains("Council") || npc.Name.Contains("isolationist") || npc.Name.Contains("muryan"))
			        continue;
		        inFight = true;
	        }

	        if (player.Group == null && player.Client.Account.PrivLevel == 1)
	        {
		        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "LordOfBoss.NeedGroup", player.CharacterClass.Name), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
		        return false;
	        }

	        if (player.Group != null && player.Group.Leader != player)
	        {
		        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "LordOfBoss.NotGroupLeader", player.CharacterClass.Name), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
		        return false;
	        }

	        if (inFight)
	        {
		        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "LordOfBoss.BattleInProgress", player.CharacterClass.Name), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
		        return false;
	        }

	        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "LordOfBoss.Greeting", player.CharacterClass.Name), eChatType.CT_Say, eChatLoc.CL_PopupWindow);

	        switch (player.Realm)
	        {
		        case eRealm._FirstPlayerRealm:
			        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "LordOfBoss.Minions.CaerSidi"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
			        break;
		        case eRealm.Midgard:
			        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "LordOfBoss.Minions.TuscarenGlacier"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
			        break;
		        case eRealm.Hibernia:
			        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "LordOfBoss.Minions.Galladoria"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
			        break;
	        }

	        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "LordOfBoss.Minions.DarknessFalls"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
	        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "LordOfBoss.BackPrompt"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);


            return true;


		}
		public override bool WhisperReceive(GameLiving source, string str)
		{
			if (!base.WhisperReceive(source, str)) return false;
			if (!(source is GamePlayer)) return false;
            if (source.InCombatInLast(10000) || source.Group != null && source.Group.Leader != source) return false;
			GamePlayer t = (GamePlayer)source;
			TurnTo(t.X, t.Y);
			switch (str.ToLower())
			{
					case "back":
					case "돌아가기":
					switch (t.Realm)
					{
						case eRealm.Albion:
							t.MoveTo(1, 560365, 511888, 2280, 66);
							break;
						case eRealm.Midgard:
							t.MoveTo(100, 804750, 723986, 4680, 671);
							break;
						case eRealm.Hibernia:
							t.MoveTo(200, 345684, 490996, 1071, 900);
							break;
					}

					break;

				#region Caer Sidi

				case "caer sidi":
				case "케어 시디":
					if (t.Realm != eRealm.Albion) return false;
					t.Out.SendMessage(LanguageMgr.GetTranslation(t.Client.Account.Language, "LordOfBoss.Menu.CaerSidi"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
					break;

				case "skeletal sacristan":
				case "스켈레탈 새크리스턴":
					if (t.Realm != eRealm.Albion) return false;
					SummonBoss(t,"DOL.GS.Scripts.SkeletalSacristan");
					break;

				case "spectral provisioner":
				case "스펙트럴 프로비저너":
					if (t.Realm != eRealm.Albion) return false;
					SummonBoss(t,"DOL.GS.Scripts.SpectralProvisioner");
					break;

				case "lich lord ilron":
				case "리치 로드 일론":
					if (t.Realm != eRealm.Albion) return false;
					SummonBoss(t,"DOL.GS.Scripts.LichLordIlron");
					break;

				case "warlord dorinakka":
				case "워로드 도리나카":
					if (t.Realm != eRealm.Albion) return false;
					SummonBoss(t,"DOL.GS.Scripts.WarlordDorinakka");
					break;

				case "soul reckoner":
				case "소울 레커너":
					if (t.Realm != eRealm.Albion) return false;
					SummonBoss(t,"DOL.GS.SoulReckoner");
					break;

				case "crypt lord":
				case "크립트 로드":
					if (t.Realm != eRealm.Albion) return false;
					SummonBoss(t,"DOL.GS.CryptLord");
					break;

				case "silencer":
				case "사일런서":
					if (t.Realm != eRealm.Albion) return false;
					SummonBoss(t,"DOL.GS.Silencer");
					break;

				case "lord sanguis":
				case "로드 생귀스":
					if (t.Realm != eRealm.Albion) return false;
					SummonBoss(t,"DOL.GS.LordSanguis");
					break;

				case "bane of hope":
				case "베인 오브 호프":
					if (t.Realm != eRealm.Albion) return false;
					SummonBoss(t,"DOL.GS.Scripts.BaneOfHope");
					break;
				#endregion

				#region Galladoria
				case "galladoria":
				case "갈라도리아":
					if (t.Realm != eRealm.Hibernia) return false;
					t.Out.SendMessage(LanguageMgr.GetTranslation(t.Client.Account.Language, "LordOfBoss.Menu.Galladoria"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
					break;

				case "easmarach":
				case "이스마라크":
					if (t.Realm != eRealm.Hibernia) return false;
					SummonBoss(t,"DOL.GS.Easmarach");
					break;

				case "organic energy mechanism":
				case "유기 에너지 장치":
					if (t.Realm != eRealm.Hibernia) return false;
					SummonBoss(t,"DOL.GS.OrganicEnergyMechanism");
					break;

				case "giant sporite cluster":
				case "거대 스포라이트 군집":
					if (t.Realm != eRealm.Hibernia) return false;
					SummonBoss(t,"DOL.GS.GiantSporiteCluster");
					break;

				case "conservator":
				case "컨서베이터":
					if (t.Realm != eRealm.Hibernia) return false;
					SummonBoss(t,"DOL.GS.Conservator");
					break;

				case "xaga":
				case "자가":
					if (t.Realm != eRealm.Hibernia) return false;
					SummonBoss(t,"DOL.GS.Xaga");
					SummonBoss(t,"DOL.GS.Beatha");
					SummonBoss(t,"DOL.GS.Tine");
					break;

				case "spindler broodmother":
				case "스핀들러 브루드마더":
					if (t.Realm != eRealm.Hibernia) return false;
					SummonBoss(t,"DOL.GS.SpindlerBroodmother");
					break;

				case "olcasar geomancer":
				case "올카사르 지오맨서":
					if (t.Realm != eRealm.Hibernia) return false;
					SummonBoss(t,"DOL.GS.OlcasarGeomancer");
					break;

				case "aroon the urlamhai":
				case "아룬 더 우를람하이":
					if (t.Realm != eRealm.Hibernia) return false;
					SummonBoss(t,"DOL.GS.Aroon");
					break;

				case "hurionthex":
				case "휴리온텍스":
					if (t.Realm != eRealm.Hibernia) return false;
					SummonBoss(t,"DOL.GS.Hurionthex");
					break;

				#endregion

				#region Darkness Falls
					case "darkness falls":
					case "다크니스 폴스":
					t.Out.SendMessage(LanguageMgr.GetTranslation(t.Client.Account.Language, "LordOfBoss.DarknessFallsUnavailable"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
					break;

				#endregion

					case "reset":
					case "초기화":
					if (source.InCombatInLast(10000)) return false;
					foreach (GameNPC mob in WorldMgr.GetNPCsFromRegion(t.CurrentRegionID))
					{
						if (mob.Brain is LordOfBossBrain || mob.Name.Contains("Council") || mob.Name.Contains("isolationist") || mob.Name.Contains("muryan"))
							continue;
						mob.Delete();
					}
					break;
				default: break;
			}
			return true;
		}
		private void SendReply(GamePlayer target, string msg)
		{
			target.Client.Out.SendMessage(
				msg,
				eChatType.CT_Say, eChatLoc.CL_PopupWindow);
		}

		private void SummonBoss(GamePlayer player, string BossClass)
		{
			foreach (GameNPC npc in WorldMgr.GetNPCsFromRegion(player.CurrentRegionID))
			{
				if (npc.Brain is LordOfBossBrain || npc.Name.Contains("Council") || npc.Name.Contains("isolationist") || npc.Name.Contains("muryan"))
					continue;
				player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "LordOfBoss.AlreadySummoned"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
				return;
			}

			//Create a new mob
			GameNPC mob = new GameNPC();
			mob = (GameNPC) Assembly.GetAssembly(typeof(GameServer)).CreateInstance(BossClass, false);

			//Fill the object variables
			mob.X = 34885;
			mob.Y = 35347;
			mob.Z = 19153;
			mob.CurrentRegion = player.CurrentRegion;
			mob.Heading = 2050;

			//Fill the living variables
			mob.Flags ^= eFlags.PEACE;
			mob.AddToWorld();
		}
	}

    public class LordOfBossBrain : StandardMobBrain {

        public int timeBeforeRez = 3000; //3 seconds

        Dictionary<GamePlayer, long> playersToRez;
        List<GamePlayer> playersToKill;

        public override void Think()
        {

        }
    }
}
