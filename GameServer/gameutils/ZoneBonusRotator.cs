using System;
using System.Collections.Generic;
using DOL.Database;
using DOL.Events;
using DOL.GS.PacketHandler;
using DOL.GS.Scheduler;
using DOL.Language;
using DOL.GS.ServerProperties;

namespace DOL.GS.Scripts
{
    static class ZoneBonusRotator
    {
        // Region ID's
        public const int ALBION_CLASSIC_ID = 1;
        public const int ALBION_SI_ID = 51;
        public const int MIDGARD_CLASSIC_ID = 100;
        public const int MIDGARD_SI_ID = 151;
        public const int HIBERNIA_CLASSIC_ID = 200;
        public const int HIBERNIA_SI_ID = 181;

        // RvR Zone ID's
        private static List<int> albionRvRZones = new List<int>() { 11, 12, 14, 15};
        private static List<int> midgardRvRZones = new List<int>() { 111, 112, 113, 115 };
        private static List<int> hiberniaRvRZones = new List<int>() { 210, 211, 212, 214 };

        // low level zone ids
        private static List<int> albionLowbieZones = new List<int>() { 0, 1, 52, 8, 6};
        private static List<int> midgardLowbieZones = new List<int>() {102, 104, 106, 155};
        private static List<int> hiberniaLowbieZones = new List<int>() { 201, 202, 203, 206, 182};

        // high level zone ids
        private static List<int> albionHighZones = new List<int>() {4, 7, 10, 53, 55, 56, 57};
        private static List<int> midgardHighZones = new List<int>() {107, 108, 116, 152, 153, 154, 156, 158};
        private static List<int> hiberniaHighZones = new List<int>() {204, 205, 216, 183, 184, 185, 186, 187};

        // PvE Zone ID's
        private static List<int> albionClassicZones = new List<int>();
        private static List<int> albionSIZones = new List<int>();
        private static List<int> midgardClassicZones = new List<int>();
        private static List<int> midgardSIZones = new List<int>();
        private static List<int> hiberniaClassicZones = new List<int>();
        private static List<int> hiberniaSIZones = new List<int>();

        // Current OF Realm with Bonuses
        private static int currentRvRRealm = 0;

        // Current PvE Zones with Bonuses
        private static int currentAlbionZone;
        private static int currentAlbionZoneSI;
        private static int currentMidgardZone;
        private static int currentMidgardZoneSI;
        private static int currentHiberniaZone;
        private static int currentHiberniaZoneSI;

        private static DbZone albDBZone;
        private static DbZone albDBZoneSI;
        private static DbZone midDBZone;
        private static DbZone midDBZoneSI;
        private static DbZone hibDBZone;
        private static DbZone hibDBZoneSI;

        private static SimpleScheduler scheduler = new SimpleScheduler();

        public static int PvETimer { get; set; }
        public static int RvRTimer { get; set; }
        public static int PvEExperienceBonusAmount { get; set; }
        public static int RvRExperienceBonusAmount { get; set; }
        public static int RPBonusAmount { get; set; }
        public static int BPBonusAmount { get; set; }

        public static long _lastRvRChangeTick { get; set; }
        public static long _lastPvEChangeTick { get; set; }

        private static int RvRTickTime = 2700;
        private static int PvETickTime = 7200;

        [GameServerStartedEvent]
        public static void OnServerStart(DOLEvent e, object sender, EventArgs arguments)
        {
            Initialize();
            GameEventMgr.AddHandler(GamePlayerEvent.GameEntered, new DOLEventHandler(PlayerEntered));

        }

        [GameServerStoppedEvent]
        public static void OnServerStopped(DOLEvent e, object sender, EventArgs arguments)
        {
            // Should be changed to keep data saved in DB for restart
            ClearPvEZones();
            ClearRvRZones();

            GameEventMgr.RemoveHandler(GamePlayerEvent.GameEntered, new DOLEventHandler(PlayerEntered));
        }

        public static void Initialize()
        {
            PvETimer = PvETickTime * 1000;
            RvRTimer = RvRTickTime * 1000;
            PvEExperienceBonusAmount = 50;
            RvRExperienceBonusAmount = 100;
            RPBonusAmount = 20;
            BPBonusAmount = 25;

            GetZones();
            UpdatePvEZones();
            UpdateRvRZones();
        }

        /// <summary>
        /// Gets all ZoneID's for PvE Zones
        /// </summary>
        public static void GetZones()
        {
            albionClassicZones.Clear();
            albionSIZones.Clear();
            midgardClassicZones.Clear();
            midgardSIZones.Clear();
            hiberniaClassicZones.Clear();
            hiberniaSIZones.Clear();

            // Get Albion ZoneID's
            foreach (DbZone zone in DOLDB<DbZone>.SelectObjects(DB.Column("RegionID").IsEqualTo(ALBION_CLASSIC_ID)))
            {
                if (!albionRvRZones.Contains(zone.ZoneID))
                {
                    albionClassicZones.Add(zone.ZoneID);
                }
            }
            foreach (DbZone zone in DOLDB<DbZone>.SelectObjects(DB.Column("RegionID").IsEqualTo(ALBION_SI_ID)))
            {
                albionSIZones.Add(zone.ZoneID);
            }

            // Get Midgard ZoneID's
            foreach (DbZone zone in DOLDB<DbZone>.SelectObjects(DB.Column("RegionID").IsEqualTo(MIDGARD_CLASSIC_ID)))
            {
                if (!midgardRvRZones.Contains(zone.ZoneID))
                {
                    midgardClassicZones.Add(zone.ZoneID);
                }
            }
            foreach (DbZone zone in DOLDB<DbZone>.SelectObjects(DB.Column("RegionID").IsEqualTo(MIDGARD_SI_ID)))
            {
                midgardSIZones.Add(zone.ZoneID);
            }

            // Get Hibernia ZoneID's
            foreach (DbZone zone in DOLDB<DbZone>.SelectObjects(DB.Column("RegionID").IsEqualTo(HIBERNIA_CLASSIC_ID)))
            {
                if (!hiberniaRvRZones.Contains(zone.ZoneID))
                {
                    hiberniaClassicZones.Add(zone.ZoneID);
                }
            }
            foreach (DbZone zone in DOLDB<DbZone>.SelectObjects(DB.Column("RegionID").IsEqualTo(HIBERNIA_SI_ID)))
            {
                hiberniaSIZones.Add(zone.ZoneID);
            }
        }

        public static void PlayerEntered(DOLEvent e, object sender, EventArgs arguments)
        {
            TellPlayer(sender as GamePlayer);
        }

        internal static int UpdatePvEZones()
        {
            _lastPvEChangeTick = GameLoop.GameLoopTime;

            ClearPvEZones();

            GetNextPvEZones();

            albDBZone = DOLDB<DbZone>.SelectObject(DB.Column("ZoneID").IsEqualTo(currentAlbionZone));
            albDBZoneSI = DOLDB<DbZone>.SelectObject(DB.Column("ZoneID").IsEqualTo(currentAlbionZoneSI));
            midDBZone = DOLDB<DbZone>.SelectObject(DB.Column("ZoneID").IsEqualTo(currentMidgardZone));
            midDBZoneSI = DOLDB<DbZone>.SelectObject(DB.Column("ZoneID").IsEqualTo(currentMidgardZoneSI));
            hibDBZone = DOLDB<DbZone>.SelectObject(DB.Column("ZoneID").IsEqualTo(currentHiberniaZone));
            hibDBZoneSI = DOLDB<DbZone>.SelectObject(DB.Column("ZoneID").IsEqualTo(currentHiberniaZoneSI));

            SetDbZoneExperience(albDBZone, PvEExperienceBonusAmount);
            SetDbZoneExperience(albDBZoneSI, PvEExperienceBonusAmount);
            SetDbZoneExperience(midDBZone, PvEExperienceBonusAmount);
            SetDbZoneExperience(midDBZoneSI, PvEExperienceBonusAmount);
            SetDbZoneExperience(hibDBZone, PvEExperienceBonusAmount);
            SetDbZoneExperience(hibDBZoneSI, PvEExperienceBonusAmount);

            // Update Bonuses In-Game
            SetWorldZoneExperience(currentAlbionZone, PvEExperienceBonusAmount);
            SetWorldZoneExperience(currentAlbionZoneSI, PvEExperienceBonusAmount);
            SetWorldZoneExperience(currentMidgardZone, PvEExperienceBonusAmount);
            SetWorldZoneExperience(currentMidgardZoneSI, PvEExperienceBonusAmount);
            SetWorldZoneExperience(currentHiberniaZone, PvEExperienceBonusAmount);
            SetWorldZoneExperience(currentHiberniaZoneSI, PvEExperienceBonusAmount);

            foreach (GamePlayer player in ClientService.Instance.GetPlayers())
                TellPlayer(player);

            scheduler.Start(UpdatePvEZones, PvETimer);
            return 0;
        }

        internal static int UpdateRvRZones()
        {

            _lastRvRChangeTick = GameLoop.GameLoopTime;

            ClearRvRZones();

            // Get new RvR Realm and set Bonuses for each Zone
            GetNextRvRZone();

            switch (currentRvRRealm)
            {
                case 1:
                    SetRvRZoneBonuses(albionRvRZones, RvRExperienceBonusAmount, RPBonusAmount, BPBonusAmount);
                    break;
                case 2:
                    SetRvRZoneBonuses(midgardRvRZones, RvRExperienceBonusAmount, RPBonusAmount, BPBonusAmount);
                    break;
                case 3:
                    SetRvRZoneBonuses(hiberniaRvRZones, RvRExperienceBonusAmount, RPBonusAmount, BPBonusAmount);
                    break;
            }

            foreach (GamePlayer player in ClientService.Instance.GetPlayers())
                TellPlayer(player);

            scheduler.Start(UpdateRvRZones, RvRTimer);
            return 0;
        }

        /// <summary>
        /// Rotate through the realms for Bonuses
        /// 1) Albion
        /// 2) Midgard
        /// 3) Hibernia
        /// </summary>
        private static void GetNextRvRZone()
        {
            /*
            if (currentRvRRealm < 3)
                currentRvRRealm += 1; // currentRvRRealm++;// currentRealm + 1;
            else
                currentRvRRealm = 1;
            */
            //get random int from 1-3 to decide realm
            //if realm is undefined or current realm, reroll to new result
            //set new realm
            int rand = Util.Random(2) + 1;
            while(rand == currentRvRRealm)
            {
                rand = Util.Random(2) + 1;
            }
            currentRvRRealm = rand;
        }

        private static void GetNextPvEZones()
        {
            /*
            if (currentAlbionZone < albionClassicZones.Count - 1)
                currentAlbionZone += 1;
            else
                currentAlbionZone = 0;

            if (currentAlbionZoneSI < albionSIZones.Count - 1)
                currentAlbionZoneSI += 1;
            else
                currentAlbionZoneSI = 0;

            if (currentMidgardZone < midgardClassicZones.Count - 1)
                currentMidgardZone += 1;
            else
                currentMidgardZone = 0;

            if (currentMidgardZoneSI < midgardSIZones.Count - 1)
                currentMidgardZoneSI += 1;
            else
                currentMidgardZoneSI = 0;

            if (currentHiberniaZone < hiberniaClassicZones.Count - 1)
                currentHiberniaZone += 1;
            else
                currentHiberniaZone = 0;

            if (currentHiberniaZoneSI < hiberniaSIZones.Count - 1)
                currentHiberniaZoneSI += 1;
            else
                currentHiberniaZoneSI = 0;
            */
            bool UseClassicAlbHighZones = Util.Chance(50);
            if (UseClassicAlbHighZones)
            {
                List<int> ClassicHighZones = new List<int>();
                foreach (var highZone in albionHighZones)
                {
                    if(albionClassicZones.Contains(highZone))
                        ClassicHighZones.Add(highZone);
                }

                List<int> SILowZones = new List<int>();
                foreach (var lowZone in albionLowbieZones)
                {
                    if (albionSIZones.Contains(lowZone))
                        SILowZones.Add(lowZone);
                }

                currentAlbionZone = PickRandomZone(ClassicHighZones, albionClassicZones);
                currentAlbionZoneSI = PickRandomZone(SILowZones, albionSIZones);
            }
            else
            {
                List<int> ClassicLowZones = new List<int>();
                foreach (var lowZone in albionLowbieZones)
                {
                    if(albionClassicZones.Contains(lowZone))
                        ClassicLowZones.Add(lowZone);
                }

                List<int> SIHighZones = new List<int>();
                foreach (var highZone in albionHighZones)
                {
                    if (albionSIZones.Contains(highZone))
                        SIHighZones.Add(highZone);
                }

                currentAlbionZone = PickRandomZone(ClassicLowZones, albionClassicZones);
                currentAlbionZoneSI = PickRandomZone(SIHighZones, albionSIZones);
            }
            //currentAlbionZone = Util.Random(albionClassicZones.Count - 1);
            //currentAlbionZoneSI = Util.Random(albionSIZones.Count - 1);

            bool UseClassicMidHighZones = Util.Chance(50);
            if (UseClassicMidHighZones)
            {
                List<int> ClassicHighZones = new List<int>();
                foreach (var highZone in midgardHighZones)
                {
                    if(midgardClassicZones.Contains(highZone))
                        ClassicHighZones.Add(highZone);
                }

                List<int> SILowZones = new List<int>();
                foreach (var lowZone in midgardLowbieZones)
                {
                    if (midgardSIZones.Contains(lowZone))
                        SILowZones.Add(lowZone);
                }

                currentMidgardZone = PickRandomZone(ClassicHighZones, midgardClassicZones);
                currentMidgardZoneSI = PickRandomZone(SILowZones, midgardSIZones);
            }
            else
            {
                List<int> ClassicLowZones = new List<int>();
                foreach (var lowZone in midgardLowbieZones)
                {
                    if(midgardClassicZones.Contains(lowZone))
                        ClassicLowZones.Add(lowZone);
                }

                List<int> SIHighZones = new List<int>();
                foreach (var highZone in midgardHighZones)
                {
                    if (midgardSIZones.Contains(highZone))
                        SIHighZones.Add(highZone);
                }

                currentMidgardZone = PickRandomZone(ClassicLowZones, midgardClassicZones);
                currentMidgardZoneSI = PickRandomZone(SIHighZones, midgardSIZones);
            }

            //currentMidgardZone = Util.Random(midgardClassicZones.Count - 1);
            //currentMidgardZoneSI = Util.Random(midgardSIZones.Count - 1);

            bool UseClassicHibHighZones = Util.Chance(50);
            if (UseClassicHibHighZones)
            {
                List<int> ClassicHighZones = new List<int>();
                foreach (var highZone in hiberniaHighZones)
                {
                    if(hiberniaClassicZones.Contains(highZone))
                        ClassicHighZones.Add(highZone);
                }

                List<int> SILowZones = new List<int>();
                foreach (var lowZone in hiberniaLowbieZones)
                {
                    if (hiberniaSIZones.Contains(lowZone))
                        SILowZones.Add(lowZone);
                }

                currentHiberniaZone = PickRandomZone(ClassicHighZones, hiberniaClassicZones);
                currentHiberniaZoneSI = PickRandomZone(SILowZones, hiberniaSIZones);
            }
            else
            {
                List<int> ClassicLowZones = new List<int>();
                foreach (var lowZone in hiberniaLowbieZones)
                {
                    if(hiberniaClassicZones.Contains(lowZone))
                        ClassicLowZones.Add(lowZone);
                }

                List<int> SIHighZones = new List<int>();
                foreach (var highZone in hiberniaHighZones)
                {
                    if (hiberniaSIZones.Contains(highZone))
                        SIHighZones.Add(highZone);
                }

                currentHiberniaZone = PickRandomZone(ClassicLowZones, hiberniaClassicZones);
                currentHiberniaZoneSI = PickRandomZone(SIHighZones, hiberniaSIZones);
            }
            //currentHiberniaZone = Util.Random(hiberniaClassicZones.Count - 1);
            //currentHiberniaZoneSI = Util.Random(hiberniaSIZones.Count - 1);

        }

        private static int PickRandomZone(List<int> preferredZones, List<int> fallbackZones)
        {
            List<int> zones = preferredZones.Count > 0 ? preferredZones : fallbackZones;
            return zones.Count > 0 ? zones[Util.Random(zones.Count - 1)] : 0;
        }

        private static void TellPlayer(GamePlayer player)
        {
            if (player?.Client?.Account == null)
                return;

            player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "ZoneBonusRotator.Updated"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
        }

        private static string GetLevelRange(int zoneID)
        {
            switch (zoneID)
            {
                case 0:
                case 8:
                case 100:
                case 103:
                case 181:
                    return "[1-20]";
                case 1:
                case 201:
                case 202:
                case 102:
                    return "[10-30]";
                case 52:
                case 206:
                    return "[15-35]";
                case 6:
                case 203:
                case 182:
                case 204:
                case 104:
                case 106:
                case 155:
                    return "[20-35]";
                case 186:
                case 152:
                case 116:
                    return "[25-45]";
                case 4:
                case 10:
                case 53:
                case 57:
                case 216:
                case 183:
                case 187:
                    return "[35-50]";
                case 205:
                case 107:
                case 153:
                case 158:
                    return "[30-50]";
                case 7:
                    return "[25-50]";
                case 184:
                case 185:
                case 108:
                case 154:
                case 156:
                case 54:
                case 55:
                case 56:
                    return "[40-50+]";
            }

            return string.Empty;
        }

        public static string GetText()
        {
            string realm = string.Empty;
            switch (currentRvRRealm)
            {
                case 1:
                    realm = GlobalConstants.RealmToName(eRealm.Albion, Properties.SERV_LANGUAGE);
                    break;
                case 2:
                    realm = GlobalConstants.RealmToName(eRealm.Midgard, Properties.SERV_LANGUAGE);
                    break;
                case 3:
                    realm = GlobalConstants.RealmToName(eRealm.Hibernia, Properties.SERV_LANGUAGE);
                    break;
            }
            return "\n" + LanguageMgr.GetTranslation(Properties.SERV_LANGUAGE, "ZoneBonusRotator.OFBonusRegion", realm) + "\n\n" +
                LanguageMgr.GetTranslation(Properties.SERV_LANGUAGE, "ZoneBonusRotator.RealmClassic", GlobalConstants.RealmToName(eRealm.Albion, Properties.SERV_LANGUAGE), GetZoneName(albDBZone), GetZoneExperience(albDBZone)) + "\n" +
                LanguageMgr.GetTranslation(Properties.SERV_LANGUAGE, "ZoneBonusRotator.RealmSI", GlobalConstants.RealmToName(eRealm.Albion, Properties.SERV_LANGUAGE), GetZoneName(albDBZoneSI), GetZoneExperience(albDBZoneSI)) + "\n\n" +
                LanguageMgr.GetTranslation(Properties.SERV_LANGUAGE, "ZoneBonusRotator.RealmClassic", GlobalConstants.RealmToName(eRealm.Midgard, Properties.SERV_LANGUAGE), GetZoneName(midDBZone), GetZoneExperience(midDBZone)) + "\n" +
                LanguageMgr.GetTranslation(Properties.SERV_LANGUAGE, "ZoneBonusRotator.RealmSI", GlobalConstants.RealmToName(eRealm.Midgard, Properties.SERV_LANGUAGE), GetZoneName(midDBZoneSI), GetZoneExperience(midDBZoneSI)) + "\n\n" +
                LanguageMgr.GetTranslation(Properties.SERV_LANGUAGE, "ZoneBonusRotator.RealmClassic", GlobalConstants.RealmToName(eRealm.Hibernia, Properties.SERV_LANGUAGE), GetZoneName(hibDBZone), GetZoneExperience(hibDBZone)) + "\n" +
                LanguageMgr.GetTranslation(Properties.SERV_LANGUAGE, "ZoneBonusRotator.RealmSI", GlobalConstants.RealmToName(eRealm.Hibernia, Properties.SERV_LANGUAGE), GetZoneName(hibDBZoneSI), GetZoneExperience(hibDBZoneSI)) + "\n\n";
        }

        public static List<string> GetTextList(string language)
        {
            List<string> temp = new List<string>();
            string realm = string.Empty;
            switch (currentRvRRealm)
            {
                case 1:
                    realm = GlobalConstants.RealmToName(eRealm.Albion, language);
                    break;
                case 2:
                    realm = GlobalConstants.RealmToName(eRealm.Midgard, language);
                    break;
                case 3:
                    realm = GlobalConstants.RealmToName(eRealm.Hibernia, language);
                    break;
            }
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.CurrentOFBonusRegion", realm));
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.BonusRP", RPBonusAmount));
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.BonusBP", BPBonusAmount));
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.BonusXP", RvRExperienceBonusAmount));
            temp.Add("");
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.CurrentRealmZones", GlobalConstants.RealmToName(eRealm.Albion, language)));
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.ClassicZone", GetZoneName(albDBZone), GetLevelRange(albDBZone), GetZoneExperience(albDBZone)));
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.SIZone", GetZoneName(albDBZoneSI), GetLevelRange(albDBZoneSI), GetZoneExperience(albDBZoneSI)));
            temp.Add("");
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.CurrentRealmZones", GlobalConstants.RealmToName(eRealm.Midgard, language)));
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.ClassicZone", GetZoneName(midDBZone), GetLevelRange(midDBZone), GetZoneExperience(midDBZone)));
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.SIZone", GetZoneName(midDBZoneSI), GetLevelRange(midDBZoneSI), GetZoneExperience(midDBZoneSI)));
            temp.Add("");
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.CurrentRealmZones", GlobalConstants.RealmToName(eRealm.Hibernia, language)));
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.ClassicZone", GetZoneName(hibDBZone), GetLevelRange(hibDBZone), GetZoneExperience(hibDBZone)));
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.SIZone", GetZoneName(hibDBZoneSI), GetLevelRange(hibDBZoneSI), GetZoneExperience(hibDBZoneSI)));

            temp.Add("");
            var rvr = _lastRvRChangeTick + RvRTimer - GameLoop.GameLoopTime;
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.RvRTimeRemaining", TimeSpan.FromMilliseconds(rvr).Hours, TimeSpan.FromMilliseconds(rvr).Minutes, TimeSpan.FromMilliseconds(rvr).Seconds));

            var pve = _lastPvEChangeTick + PvETimer - GameLoop.GameLoopTime;
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.PvETimeRemaining", TimeSpan.FromMilliseconds(pve).Hours, TimeSpan.FromMilliseconds(pve).Minutes, TimeSpan.FromMilliseconds(pve).Seconds));

            temp.Add("");
            temp.Add("");

            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.PermanentBonuses"));
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.AllDungeons", 25));
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.RvRDungeons", 50));
            temp.Add(LanguageMgr.GetTranslation(language, "ZoneBonusRotator.DarknessFalls", 75));

            temp.Add("");
            temp.Add("");

            return temp;
        }

        public static eRealm GetCurrentBonusRealm()
        {
            return (eRealm) currentRvRRealm;
        }

        private static void ClearRvRZones()
        {
            // Clear RvR Zone
            switch (currentRvRRealm)
            {
                case 1:
                    SetRvRZoneBonuses(albionRvRZones, 0, 0, 0);
                    break;
                case 2:
                    SetRvRZoneBonuses(midgardRvRZones, 0, 0, 0);
                    break;
                case 3:
                    SetRvRZoneBonuses(hiberniaRvRZones, 0, 0, 0);
                    break;
            }
        }

        private static void ClearPvEZones()
        {
            // Clear PvE Zones
            albDBZone = DOLDB<DbZone>.SelectObject(DB.Column("ZoneID").IsEqualTo(currentAlbionZone));
            albDBZoneSI = DOLDB<DbZone>.SelectObject(DB.Column("ZoneID").IsEqualTo(currentAlbionZoneSI));
            midDBZone = DOLDB<DbZone>.SelectObject(DB.Column("ZoneID").IsEqualTo(currentMidgardZone));
            midDBZoneSI = DOLDB<DbZone>.SelectObject(DB.Column("ZoneID").IsEqualTo(currentMidgardZoneSI));
            hibDBZone = DOLDB<DbZone>.SelectObject(DB.Column("ZoneID").IsEqualTo(currentHiberniaZone));
            hibDBZoneSI = DOLDB<DbZone>.SelectObject(DB.Column("ZoneID").IsEqualTo(currentHiberniaZoneSI));

            SetDbZoneExperience(albDBZone, 0);
            SetDbZoneExperience(albDBZoneSI, 0);
            SetDbZoneExperience(midDBZone, 0);
            SetDbZoneExperience(midDBZoneSI, 0);
            SetDbZoneExperience(hibDBZone, 0);
            SetDbZoneExperience(hibDBZoneSI, 0);


            foreach (var zone in albionClassicZones)
                SetWorldZoneExperience(zone, 0);

            foreach (var zone in albionSIZones)
                SetWorldZoneExperience(zone, 0);

            foreach (var zone in midgardClassicZones)
                SetWorldZoneExperience(zone, 0);

            foreach (var zone in midgardSIZones)
                SetWorldZoneExperience(zone, 0);

            foreach (var zone in hiberniaClassicZones)
                SetWorldZoneExperience(zone, 0);

            foreach (var zone in hiberniaSIZones)
                SetWorldZoneExperience(zone, 0);

            /*
            WorldMgr.Zones[(ushort)albionClassicZones[currentAlbionZone]].BonusExperience = 0;
            WorldMgr.Zones[(ushort)albionSIZones[currentAlbionZoneSI]].BonusExperience = 0;
            WorldMgr.Zones[(ushort)midgardClassicZones[currentMidgardZone]].BonusExperience = 0;
            WorldMgr.Zones[(ushort)midgardSIZones[currentMidgardZoneSI]].BonusExperience = 0;
            WorldMgr.Zones[(ushort)hiberniaClassicZones[currentHiberniaZone]].BonusExperience = 0;
            WorldMgr.Zones[(ushort)hiberniaSIZones[currentHiberniaZoneSI]].BonusExperience = 0;
            */
        }

        private static void SetDbZoneExperience(DbZone zone, int experience)
        {
            if (zone == null)
                return;

            zone.Experience = experience;
            GameServer.Database.SaveObject(zone);
        }

        private static void SetRvRZoneBonuses(IEnumerable<int> zoneIds, int experience, int realmPoints, int bountyPoints)
        {
            foreach (int zoneId in zoneIds)
            {
                DbZone zone = DOLDB<DbZone>.SelectObject(DB.Column("ZoneID").IsEqualTo(zoneId));
                SetDbZoneBonuses(zone, experience, realmPoints, bountyPoints);
                SetWorldZoneBonuses(zoneId, experience, realmPoints, bountyPoints);
            }
        }

        private static void SetDbZoneBonuses(DbZone zone, int experience, int realmPoints, int bountyPoints)
        {
            if (zone == null)
                return;

            zone.Experience = experience;
            zone.Realmpoints = realmPoints;
            zone.Bountypoints = bountyPoints;
            GameServer.Database.SaveObject(zone);
        }

        private static void SetWorldZoneExperience(int zoneId, int experience)
        {
            if (WorldMgr.Zones.TryGetValue((ushort)zoneId, out var zone))
                zone.BonusExperience = experience;
        }

        private static void SetWorldZoneBonuses(int zoneId, int experience, int realmPoints, int bountyPoints)
        {
            if (!WorldMgr.Zones.TryGetValue((ushort)zoneId, out var zone))
                return;

            zone.BonusExperience = experience;
            zone.BonusRealmpoints = realmPoints;
            zone.BonusBountypoints = bountyPoints;
        }

        private static string GetZoneName(DbZone zone)
        {
            return zone?.Name ?? "Unknown";
        }

        private static int GetZoneExperience(DbZone zone)
        {
            return zone?.Experience ?? 0;
        }

        private static string GetLevelRange(DbZone zone)
        {
            return zone == null ? string.Empty : GetLevelRange(zone.ZoneID);
        }
    }
}
