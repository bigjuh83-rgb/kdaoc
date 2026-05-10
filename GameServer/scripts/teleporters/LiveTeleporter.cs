using System;
using System.Collections.Generic;
using DOL.Database;
using DOL.GS.Housing;
using DOL.GS.PacketHandler;
using DOL.GS.Spells;
using DOL.Language;

/* Need to fix
 * EquipTemplate for Hib and Mid
 * Oceanus for all realms.
 * Kobold Undercity for Mid
 * personal guild and hearth teleports
 */
namespace DOL.GS.Scripts
{
    public class LiveTeleporter : GameNPC
    {
        /// <summary>
        /// The type of teleporter; this is used in order to be able to handle
        /// identical TeleportIDs differently, depending on the actual teleporter.
        /// </summary>
        protected virtual String Type
        {
            get { return string.Empty; }
        }

        /// <summary>
        /// The destination realm.
        /// </summary>
        protected virtual eRealm DestinationRealm
        {
            get { return Realm; }
        }

        public override bool AddToWorld()
        {
            switch (Realm)
            {
                case eRealm.Albion:
                    Name = "Master Visur";
                    GuildName = "Teleporter";
                    Model = 61;

                    GameNpcInventoryTemplate templateAlb = new GameNpcInventoryTemplate();
                    templateAlb.AddNPCEquipment(eInventorySlot.Cloak, 57, 66);
                    templateAlb.AddNPCEquipment(eInventorySlot.TorsoArmor, 1005, 86);
                    templateAlb.AddNPCEquipment(eInventorySlot.LegsArmor, 140, 6);
                    templateAlb.AddNPCEquipment(eInventorySlot.ArmsArmor, 141, 6);
                    templateAlb.AddNPCEquipment(eInventorySlot.HandsArmor, 142, 6);
                    templateAlb.AddNPCEquipment(eInventorySlot.FeetArmor, 143, 6);
                    templateAlb.AddNPCEquipment(eInventorySlot.TwoHandWeapon, 1166);
                    Inventory = templateAlb.CloseTemplate();
                    break;
                case eRealm.Midgard:
                    Name = "Stor Gothi Annark";
                    GuildName = "Teleporter";
                    Model = 215;

                    GameNpcInventoryTemplate templateMid = new GameNpcInventoryTemplate();
                    templateMid.AddNPCEquipment(eInventorySlot.Cloak, 57, 26);
                    templateMid.AddNPCEquipment(eInventorySlot.TorsoArmor, 245, 26);
                    templateMid.AddNPCEquipment(eInventorySlot.LegsArmor, 246, 26);
                    templateMid.AddNPCEquipment(eInventorySlot.HandsArmor, 248, 26);
                    templateMid.AddNPCEquipment(eInventorySlot.FeetArmor, 249, 26);
                    Inventory = templateMid.CloseTemplate();
                    break;
                case eRealm.Hibernia:
                    Name = "Channeler Glasny";
                    GuildName = "Teleporter";
                    Model = 342;

                    GameNpcInventoryTemplate templateHib = new GameNpcInventoryTemplate();
                    templateHib.AddNPCEquipment(eInventorySlot.TorsoArmor, 1008);
                    templateHib.AddNPCEquipment(eInventorySlot.HandsArmor, 396);
                    templateHib.AddNPCEquipment(eInventorySlot.FeetArmor, 402);
                    templateHib.AddNPCEquipment(eInventorySlot.TwoHandWeapon, 468);
                    Inventory = templateHib.CloseTemplate();
                    break;
            }

            Level = 60;
            Size = 50;
            Flags |= GameNPC.eFlags.PEACE;

            return base.AddToWorld();
        }

        /// <summary>
        /// Display the teleport indicator around this teleporters feet
        /// </summary>
        public override bool ShowTeleporterIndicator
        {
            get { return true; }
        }


        public override bool Interact(GamePlayer player) // What to do when a player clicks on me
        {
            if (!base.Interact(player) || GameRelic.IsPlayerCarryingRelic(player)) return false;

            if (player.Realm != this.Realm && player.Client.Account.PrivLevel == 1) return false;

            TurnTo(player, 10000);

            var message = string.Empty;

            switch (Realm)
            {
                case eRealm.Albion:
                    message = LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTeleporter.Interact.Menu", player.Name);
                    break;

                case eRealm.Midgard:
                    message = LanguageMgr.GetTranslation(player.Client.Account.Language, "MidgardTeleporter.Interact.Menu", player.Name);
                    break;

                case eRealm.Hibernia:
                    message = LanguageMgr.GetTranslation(player.Client.Account.Language, "HiberniaTeleporter.Interact.Menu", player.Name);
                    break;

                default:
                    SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "LiveTeleporter.NoRealm"));
                    break;
            }

            message += LanguageMgr.GetTranslation(player.Client.Account.Language, "LiveTeleporter.EpicDungeonPrompt");

            SayTo(player, message);

            return true;
        }

        public override bool WhisperReceive(GameLiving source, string str) // What to do when a player whispers me
        {
            if (!base.WhisperReceive(source, str)) return false;

            GamePlayer player = source as GamePlayer;
            if (player == null)
                return false;

            if (GameRelic.IsPlayerCarryingRelic(player))
                return false;

            return GetTeleportLocation(player, str);

        }

        protected virtual bool GetTeleportLocation(GamePlayer player, string text)
        {
	            text = text switch
	            {
	                "주택" => "housing",
	                "슈라우디드 아일스" => "shrouded isles",
	                "마을" => "towns",
	                "입구" => "Entrance",
	                "개인 주택" => "personal",
	                "길드 주택" => "guild",
	                "귀환 위치" => "hearth",
	                "소바쥬 성" => "Castle Sauvage",
	                "스노도니아 요새" => "Snowdonia Fortress",
	                "아발론 습지" => "Avalon Marsh",
	                "고스웨이트 항구" => "Gothwaite Harbor",
	                "카멜롯" => "Camelot",
	                "고스웨이트" => "Gothwaite",
	                "위어리얼 마을" => "Wearyall Village",
	                "귄텔 요새" => "Gwyntell",
	                "케어 디오겔" => "Caer Diogel",
	                "코츠월드 마을" => "Cotswold Village",
	                "프리드웬 성채" => "Prydwen Keep",
	                "케어 울프위치" => "Caer Ulfwych",
	                "캄파코렌틴 기지" => "Campacorentin Station",
	                "아드리바드 은거지" => "Adribard's Retreat",
	                "야를리 농장" => "Yarley's Farm",
	                "스바수드 파스테" => "Svasud Faste",
	                "빈드사울 파스테" => "Vindsaul Faste",
	                "고타르" => "Gotar",
	                "에기르함" => "Aegirhamn",
	                "요르드하임" => "Jordheim",
	                "비야르켄" => "Bjarken",
	                "하갈" => "Hagall",
	                "크나르" => "Knarr",
	                "물란" => "Mularn",
	                "벨돈 요새" => "Fort Veldon",
	                "아우들리텐" => "Audliten",
	                "후긴펠" => "Huginfell",
	                "아틀라 요새" => "Fort Atla",
	                "웨스트 스코나" => "West Skona",
	                "드루임 리겐" => "Druim Ligen",
	                "드루임 케인" => "Druim Cain",
	                "섀넌 하구" => "Shannon Estuary",
	                "돔난" => "Domnann",
	                "티르 나 노그" => "Tir na Nog",
	                "드로하이드" => "Droighaid",
	                "알리드 페이" => "Aalid Feie",
	                "네흐트" => "Necht",
	                "마그 멜" => "Mag Mell",
	                "티르 나 므베오" => "Tir na mBeo",
	                "아르다" => "Ardagh",
	                "호스" => "Howth",
	                "콘라" => "Connla",
	                "이니스 카르사이그" => "Innis Carthaig",
	                _ => text
	            };

            switch (Realm) // Only offer locations based on what realm i am set at.
            {
                case eRealm.Albion:

                    if (text.ToLower() == "shrouded isles")
                    {
                        SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTeleporter.SubSelection.ShroudedIslesPrompt"));
                        return false;
                    }

                    if (text.ToLower() == "housing")
                    {
                        SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "RealmTeleporter.SubSelection.HousingPrompt"));
                        return false;
                    }

                    if (text.ToLower() == "towns")
                    {
                        SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTeleporter.SubSelection.TownsPrompt"));
                        return false;
                    }

                    /*
                    if (text.ToLower() == "darkness falls")
                    {
                        IGameLocation location = new GameLocation("df", 249, 249, 23122, 19634, 22897, 3074);

                        Teleport teleport = new Teleport();
                        teleport.TeleportID = "Darkness Falls";
                        teleport.Realm = (int) DestinationRealm;
                        teleport.RegionID = location.RegionID;
                        teleport.X = location.X;
                        teleport.Y = location.Y;
                        teleport.Z = location.Z;
                        teleport.Heading = location.Heading;
                        OnDestinationPicked(player, teleport);
                        return true;
                    }*/

                    break;

                case eRealm.Midgard:

                    if (text.ToLower() == "shrouded isles")
                    {
                        SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "MidgardTeleporter.SubSelection.ShroudedIslesPrompt"));

                        return false;
                    }

                    if (text.ToLower() == "housing")
                    {
                        SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "RealmTeleporter.SubSelection.HousingPrompt"));
                        return false;
                    }

                    if (text.ToLower() == "towns")
                    {
                        SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "MidgardTeleporter.SubSelection.TownsPrompt"));
                        return false;
                    }

                    break;

                case eRealm.Hibernia:

                    if (text.ToLower() == "shrouded isles")
                    {
                        SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "HiberniaTeleporter.SubSelection.ShroudedIslesPrompt"));
                        return false;
                    }

                    if (text.ToLower() == "housing")
                    {
                        SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "RealmTeleporter.SubSelection.HousingPrompt"));
                        return false;
                    }

                    if (text.ToLower() == "towns")
                    {
                        SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "HiberniaTeleporter.SubSelection.TownsPrompt"));
                        return false;
                    }

                    break;
            }

            // Another special case is personal house, as there is no location
            // that will work for every player.
            if (text == "Entrance") text = text.ToLower();

            if (text.ToLower() == "personal")
            {
                House house = HouseMgr.GetHouseByPlayer(player);

                if (house == null)
                {
                    text = "entrance"; // Fall through, port to housing entrance.
                }
                else
                {
                    IGameLocation location = house.OutdoorJumpPoint;
                    DbTeleport teleport = new DbTeleport();
                    teleport.TeleportID = "your house";
                    teleport.Realm = (int) DestinationRealm;
                    teleport.RegionID = location.RegionID;
                    teleport.X = location.X;
                    teleport.Y = location.Y;
                    teleport.Z = location.Z;
                    teleport.Heading = location.Heading;
                    OnDestinationPicked(player, teleport);
                    return true;
                }
            }

            // Yet another special case the port to the 'hearth' what means
            // that the player will be ported to the defined house bindstone
            if (text.ToLower() == "hearth")
            {
                // Check if player has set a house bind
                if (!(player.BindHouseRegion > 0))
                {
                    SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Hearth.NoBindPoint"));
                    return false;
                }

                // Check if the house at the player's house bind location still exists
                var houses = HouseMgr.GetHousesCloseToSpot((ushort) player.BindHouseRegion,
                    player.BindHouseXpos, player.BindHouseYpos, 700);
                if (houses.Count == 0)
                {
                    SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Hearth.HouseRemoved"));
                    return false;
                }

                // Check if the house at the player's house bind location contains a bind stone
                House targetHouse = houses[0];
                var hookpointItems = targetHouse.HousePointItems;
                Boolean hasBindstone = false;

                foreach (KeyValuePair<uint, DbHouseHookPointItem> targetHouseItem in hookpointItems)
                {
                    if (((GameObject) targetHouseItem.Value.GameObject).GetName(0, false).ToLower()
                        .EndsWith("bindstone"))
                    {
                        hasBindstone = true;
                        break;
                    }
                }

                if (!hasBindstone)
                {
                    SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Hearth.BindstoneRemoved"));
                    return false;
                }

                // Check if the player has the permission to bind at the house bind stone
                if (!targetHouse.CanBindInHouse(player))
                {
                    SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AllRealmsTeleporter.Hearth.NoBindPermission"));
                    return false;
                }

                DbTeleport teleport = new DbTeleport();
                teleport.TeleportID = "hearth";
                teleport.Realm = (int) DestinationRealm;
                teleport.RegionID = player.BindHouseRegion;
                teleport.X = player.BindHouseXpos;
                teleport.Y = player.BindHouseYpos;
                teleport.Z = player.BindHouseZpos;
                teleport.Heading = player.BindHouseHeading;
                OnDestinationPicked(player, teleport);
                return true;
            }

            if (text.ToLower() == "guild")
            {
                House house = HouseMgr.GetGuildHouseByPlayer(player);

                if (house == null)
                {
                    SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "LiveTeleporter.GuildHouseMissing", player.Guild?.Name ?? string.Empty));
                    return false;
                    return false; // no teleport when guild house not found
                }
                else
                {
                    IGameLocation location = house.OutdoorJumpPoint;
                    DbTeleport teleport = new DbTeleport();
                    teleport.TeleportID = "guild house";
                    teleport.Realm = (int) DestinationRealm;
                    teleport.RegionID = location.RegionID;
                    teleport.X = location.X;
                    teleport.Y = location.Y;
                    teleport.Z = location.Z;
                    teleport.Heading = location.Heading;
                    OnDestinationPicked(player, teleport);
                    return true;
                }
            }

            if (text.ToLower() == "epic dungeon" || text == "에픽 던전")
            {
                switch (player.Realm)
                {
                    case eRealm.Albion:
                        GetTeleportLocation(player, "Caer Sidi");
                        return true;
                    case eRealm.Midgard:
                        GetTeleportLocation(player, "Tuscaran Glacier");
                        return true;
                    case eRealm.Hibernia:
                        GetTeleportLocation(player, "Galladoria");
                        return false;
                }
            }

            // Find the teleport location in the database.
            DbTeleport port = WorldMgr.GetTeleportLocation(DestinationRealm, String.Format("{0}:{1}", Type, text));
            if (port != null)
            {
                if (port.RegionID == 0 && port.X == 0 && port.Y == 0 && port.Z == 0)
                {
                    OnSubSelectionPicked(player, port);
                }
                else
                {
                    OnDestinationPicked(player, port);
                }

                return false;
            }

            return true; // Needs further processing.
        }

        /// <summary>
        /// Player has picked a destination.
        /// Override if you need the teleporter to say something to the player
        /// before porting him.
        /// </summary>
        /// <param name="player"></param>
        /// <param name="destination"></param>
        protected virtual void OnDestinationPicked(GamePlayer player, DbTeleport destination)
        {
            Region region = WorldMgr.GetRegion((ushort) destination.RegionID);

            if (region == null || region.IsDisabled)
            {
                player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "RealmTeleporter.Destination.NotAvailable"), eChatType.CT_System,
                    eChatLoc.CL_SystemWindow);
                return;
            }

            var message = $"{Name} says, \"{LanguageMgr.GetTranslation(player.Client.Account.Language, "RealmTeleporter.Destination.Teleporting", destination.TeleportID)}\"";

            player.Out.SendMessage(message, eChatType.CT_Say, eChatLoc.CL_ChatWindow);

            OnTeleportSpell(player, destination);
        }

        /// <summary>
        /// Player has picked a subselection.
        /// Override to pass teleport options on to the player.
        /// </summary>
        /// <param name="player"></param>
        /// <param name="subSelection"></param>
        protected virtual void OnSubSelectionPicked(GamePlayer player, DbTeleport subSelection)
        {
        }

        /// <summary>
        /// Teleport the player to the designated coordinates using the
        /// portal spell.
        /// </summary>
        /// <param name="player"></param>
        /// <param name="destination"></param>
        protected virtual void OnTeleportSpell(GamePlayer player, DbTeleport destination)
        {
            SpellLine spellLine = SkillBase.GetSpellLine(GlobalSpellsLines.Mob_Spells);
            List<Spell> spellList = SkillBase.GetSpellList(GlobalSpellsLines.Mob_Spells);
            Spell spell = SkillBase.GetSpellByID(5999); // UniPortal spell.

            if (spell != null)
            {
                UniPortal portalHandler = new UniPortal(this, spell, spellLine, destination);
                portalHandler.StartSpell(player);
                return;
            }

            // Spell not found in the database, fall back on default procedure.

            if (player.Client.Account.PrivLevel > 1)
                player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "LiveTeleporter.UniPortalSpellNotFound"),
                    eChatType.CT_Items, eChatLoc.CL_SystemWindow);


            this.OnTeleport(player, destination);
        }

        /// <summary>
        /// Teleport the player to the designated coordinates.
        /// </summary>
        /// <param name="player"></param>
        /// <param name="destination"></param>
        protected virtual void OnTeleport(GamePlayer player, DbTeleport destination)
        {
            if (player.InCombat == false && GameRelic.IsPlayerCarryingRelic(player) == false)
            {
                player.LeaveHouse();
                GameLocation currentLocation =
                    new GameLocation("TeleportStart", player.CurrentRegionID, player.X, player.Y, player.Z);
                player.MoveTo((ushort) destination.RegionID, destination.X, destination.Y, destination.Z,
                    (ushort) destination.Heading);
                GameServer.ServerRules.OnPlayerTeleport(player, currentLocation, destination);
            }
        }
    }
}
