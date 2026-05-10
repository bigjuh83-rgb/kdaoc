using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using DOL.Database;
using DOL.Database.UniqueID;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS
{
    [NPCGuildScript("Effect Master")]
    public class EffectNPC : GameNPC
    {
        private string EFFECTNPC_ITEM_WEAK = "DOL.GS.Scripts.EffectNPC_Item_Manipulation";//used to store the item in the player
        private ushort spell = 7215;//The spell which is casted
        private ushort duration = 3000;//3s, the duration the spell is cast
        private Queue m_timer = new Queue();//Gametimer for casting some spell at the end of the process
        private Queue castplayer = new Queue();//Used to hold the player who the spell gets cast on
        public string TempProperty = "ItemEffect";
        public string DisplayedItem = "EffectDisplay";
        public string TempEffectId = "TempEffectID";
        public string TempColorId = "TempColorID";

        private static string T(GamePlayer player, string key, params object[] args)
            => LanguageMgr.GetTranslation(player.Client.Account.Language, key, args);

        private sealed class MenuOption
        {
            public MenuOption(string key, string command, int id)
            {
                Key = key;
                Command = command;
                Id = id;
            }

            public string Key { get; }
            public string Command { get; }
            public int Id { get; }
            public string TranslationKey => "CustomNPC.EffectNPC.Option." + Key;
        }

        private sealed class MenuCategory
        {
            public MenuCategory(string key, string command, MenuOption[] options)
            {
                Key = key;
                Command = command;
                Options = options;
            }

            public string Key { get; }
            public string Command { get; }
            public MenuOption[] Options { get; }
            public string TranslationKey => "CustomNPC.EffectNPC.Category." + Key;
        }

        private static MenuOption Effect(string key, string command, int id) => new MenuOption("Effect." + key, command, id);
        private static MenuOption Dye(string key, string command, int id) => new MenuOption("Dye." + key, command, id);

        private static readonly MenuOption[] LongswordEffects =
        {
            Effect("LongswordPropaneStyleFlame", "longsword - propane-style flame", 1),
            Effect("LongswordRegularFlame", "longsword - regular flame", 2),
            Effect("LongswordOrangeFlame", "longsword - orange flame", 3),
            Effect("LongswordRisingFlame", "longsword - rising flame", 4),
            Effect("LongswordFlameWithSmoke", "longsword - flame with smoke", 5),
            Effect("LongswordFlameWithSparks", "longsword - flame with sparks", 6),
            Effect("LongswordHotGlow", "longsword - hot glow", 7),
            Effect("LongswordHotAura", "longsword - hot aura", 8),
            Effect("LongswordBlueAura", "longsword - blue aura", 9),
            Effect("LongswordHotGoldGlow", "longsword - hot gold glow", 10),
            Effect("LongswordHotBlueGlow", "longsword - hot blue glow", 11),
            Effect("LongswordHotRedGlow", "longsword - hot red glow", 12),
            Effect("LongswordRedAura", "longsword - red aura", 13),
            Effect("LongswordColdAuraWithSparkles", "longsword - cold aura with sparkles", 14),
            Effect("LongswordColdAuraWithVapor", "longsword - cold aura with vapor", 15),
            Effect("LongswordHiltWaveringBlueBeam", "longsword - hilt wavering blue beam", 16),
            Effect("LongswordHiltWaveringGreenBeam", "longsword - hilt wavering green beam", 17),
            Effect("LongswordHiltWaveringRedBeam", "longsword - hilt wavering red beam", 18),
            Effect("LongswordHiltRedBlueBeam", "longsword - hilt red/blue beam", 19),
            Effect("LongswordHiltPurpleBeam", "longsword - hilt purple beam", 20),
        };

        private static readonly MenuOption[] GreatSwordEffects =
        {
            Effect("GreatSwordYellowFlames", "gr sword - yellow flames", 21),
            Effect("GreatSwordOrangeFlames", "gr sword - orange flames", 22),
            Effect("GreatSwordFireWithSmoke", "gr sword - fire with smoke", 23),
            Effect("GreatSwordFireWithSparks", "gr sword - fire with sparks", 24),
        };

        private static readonly MenuOption[] GreatWeaponEffects =
        {
            Effect("GreatWeaponBlueGlowWithSparkles", "gr - blue glow with sparkles", 25),
            Effect("GreatWeaponBlueAuraWithColdVapor", "gr - blue aura with cold vapor", 26),
            Effect("GreatWeaponIcyBlueGlow", "gr - icy blue glow", 27),
            Effect("GreatWeaponRedAura", "gr - red aura", 28),
            Effect("GreatWeaponStrongCrimsonGlow", "gr - strong crimson glow", 29),
            Effect("GreatWeaponWhiteCoreRedGlow", "gr - white core red glow", 30),
            Effect("GreatWeaponSilveryWhiteGlow", "gr - silvery/white glow", 31),
            Effect("GreatWeaponGoldYellowGlow", "gr - gold/yellow glow", 31),
            Effect("GreatWeaponHotGreenGlow", "gr - hot green glow", 33),
        };

        private static readonly MenuOption[] HammerEffects =
        {
            Effect("HammerRedAura", "hammer - red aura", 34),
            Effect("HammerFieryGlow", "hammer - fiery glow", 35),
            Effect("HammerMoreIntenseFieryGlow", "hammer - more intense fiery glow", 36),
            Effect("HammerFlaming", "hammer - flaming", 37),
            Effect("HammerTorchlikeFlaming", "hammer - torchlike flaming", 38),
            Effect("HammerSilveryGlow", "hammer - silvery glow", 39),
            Effect("HammerPurpleGlow", "hammer - purple glow", 40),
            Effect("HammerBlueAura", "hammer - blue aura", 41),
            Effect("HammerBlueGlow", "hammer - blue glow", 42),
            Effect("HammerArcsFromHeadToHandle", "hammer - arcs from head to handle", 43),
        };

        private static readonly MenuOption[] CrushEffects =
        {
            Effect("CrushArcingHalo", "crush - arcing halo", 44),
            Effect("CrushCenterArcing", "crush - center arcing", 45),
            Effect("CrushSmallerArcingHalo", "crush - smaller arcing halo", 46),
            Effect("CrushHotOrangeCoreGlow", "crush - hot orange core glow", 47),
            Effect("CrushOrangeAura", "crush - orange aura", 48),
            Effect("CrushSubtleAuraWithSparks", "crush - subtle aura with sparks", 49),
            Effect("CrushYellowFlame", "crush - yellow flame", 50),
            Effect("CrushManaFlame", "crush - mana flame", 51),
            Effect("CrushHotGreenGlow", "crush - hot green glow", 52),
            Effect("CrushHotRedGlow", "crush - hot red glow", 53),
            Effect("CrushHotPurpleGlow", "crush - hot purple glow", 54),
            Effect("CrushColdVapor", "crush - cold vapor", 55),
        };

        private static readonly MenuOption[] AxeEffects =
        {
            Effect("AxeBasicFlame", "axe - basic flame", 56),
            Effect("AxeOrangeFlame", "axe - orange flame", 57),
            Effect("AxeSlowOrangeFlameWithSparks", "axe - slow orange flame with sparks", 58),
            Effect("AxeFieryTrailingFlame", "axe - fiery/trailing flame", 59),
            Effect("AxeColdVapor", "axe - cold vapor", 60),
            Effect("AxeBlueAuraWithTwinkles", "axe - blue aura with twinkles", 61),
            Effect("AxeHotGreenGlow", "axe - hot green glow", 62),
            Effect("AxeHotBlueGlow", "axe - hot blue glow", 63),
            Effect("AxeHotCyanGlow", "axe - hot cyan glow", 64),
            Effect("AxeHotPurpleGlow", "axe - hot purple glow", 65),
            Effect("AxeBluePurpleOrangeGlow", "axe - blue->purple->orange glow", 66),
        };

        private static readonly MenuOption[] ShortswordEffects =
        {
            Effect("ShortswordPropaneFlame", "shortsword - propane flame", 67),
            Effect("ShortswordOrangeFlameWithSparks", "shortsword - orange flame with sparks", 68),
            Effect("ShortswordBlueAuraWithTwinkles", "shortsword - blue aura with twinkles", 69),
            Effect("ShortswordGreenCloudWithBubbles", "shortsword - green cloud with bubbles", 70),
            Effect("ShortswordRedAuraWithBloodBubbles", "shortsword - red aura with blood bubbles", 71),
            Effect("ShortswordEvilGreenGlow", "shortsword - evil green glow", 72),
            Effect("ShortswordBlackGlow", "shortsword - black glow", 73),
        };

        private static readonly MenuOption[] BattlespearEffects =
        {
            Effect("BattlespearColdWithTwinkles", "battlespear - cold with twinkles", 74),
            Effect("BattlespearEvilGreenAura", "battlespear - evil green aura", 75),
            Effect("BattlespearEvilRedAura", "battlespear - evil red aura", 76),
            Effect("BattlespearFlaming", "battlespear - flaming", 77),
            Effect("BattlespearHotGoldGlow", "battlespear - hot gold glow", 78),
            Effect("BattlespearHotFireGlow", "battlespear - hot fire glow", 79),
            Effect("BattlespearRedAura", "battlespear - red aura", 80),
        };

        private static readonly MenuOption[] LuggedSpearEffects =
        {
            Effect("LuggedSpearBlueGlow", "lugged spear - blue glow", 81),
            Effect("LuggedSpearHotBlueGlow", "lugged spear - hot blue glow", 82),
            Effect("LuggedSpearColdWithTwinkles", "lugged spear - cold with twinkles", 83),
            Effect("LuggedSpearFlaming", "lugged spear - flaming", 84),
            Effect("LuggedSpearElectricArcing", "lugged spear - electric arcing", 85),
            Effect("LuggedSpearHotYellowFlame", "lugged spear - hot yellow flame", 86),
            Effect("LuggedSpearOrangeFlameWithSparks", "lugged spear - orange flame with sparks", 87),
            Effect("LuggedSpearOrangeToPurpleFlame", "lugged spear - orange to purple flame", 88),
            Effect("LuggedSpearHotPurpleFlame", "lugged spear - hot purple flame", 89),
            Effect("LuggedSpearSilveryGlow", "lugged spear - silvery glow", 90),
        };

        private static readonly MenuOption[] StaffEffects =
        {
            Effect("StaffBlueGlow", "staff - blue glow", 90),
            Effect("StaffBlueGlowWithTwinkles", "staff - blue glow with twinkles", 91),
            Effect("StaffGoldGlow", "staff - gold glow", 92),
            Effect("StaffGoldGlowWithTwinkles", "staff - gold glow with twinkles", 93),
            Effect("StaffFaintRedGlow", "staff - faint red glow", 94),
        };

        private static readonly MenuOption[][] EffectGroups =
        {
            LongswordEffects,
            GreatSwordEffects,
            GreatWeaponEffects,
            HammerEffects,
            CrushEffects,
            AxeEffects,
            ShortswordEffects,
            BattlespearEffects,
            LuggedSpearEffects,
            StaffEffects,
        };

        private static readonly MenuOption[] DyeOptions =
        {
            Dye("White", "White", 0),
            Dye("OldRed", "Old Red", 1),
            Dye("OldGreen", "Old Green", 2),
            Dye("OldBlue", "Old Blue", 3),
            Dye("OldYellow", "Old Yellow", 4),
            Dye("OldPurple", "Old Purple", 5),
            Dye("Gray", "Gray", 6),
            Dye("OldTurquoise", "Old Turquoise", 7),
            Dye("LeatherYellow", "Leather Yellow", 8),
            Dye("LeatherRed", "Leather Red", 9),
            Dye("LeatherGreen", "Leather Green", 10),
            Dye("LeatherOrange", "Leather Orange", 11),
            Dye("LeatherViolet", "Leather Violet", 12),
            Dye("LeatherForestGreen", "Leather Forest Green", 13),
            Dye("LeatherBlue", "Leather Blue", 14),
            Dye("LeatherPurple", "Leather Purple", 15),
            Dye("Bronze", "Bronze", 16),
            Dye("Iron", "Iron", 17),
            Dye("Steel", "Steel", 18),
            Dye("Alloy", "Alloy", 19),
            Dye("FineAlloy", "Fine Alloy", 20),
            Dye("Mithril", "Mithril", 21),
            Dye("Asterite", "Asterite", 22),
            Dye("Eog", "Eog", 23),
            Dye("Xenium", "Xenium", 24),
            Dye("Vaanum", "Vaanum", 25),
            Dye("Adamantium", "Adamantium", 26),
            Dye("RedCloth", "Red Cloth", 27),
            Dye("OrangeCloth", "Orange Cloth", 28),
            Dye("YellowOrangeCloth", "Yellow-Orange Cloth", 29),
            Dye("YellowCloth", "Yellow Cloth", 30),
            Dye("YellowGreenCloth", "Yellow-Green Cloth", 31),
            Dye("GreenCloth", "Green Cloth", 32),
            Dye("BlueGreenCloth", "Blue-Green Cloth", 33),
            Dye("TurquoiseCloth", "Turquoise Cloth", 34),
            Dye("LightBlueCloth", "Light Blue Cloth", 35),
            Dye("BlueCloth", "Blue Cloth", 36),
            Dye("BlueVioletCloth", "Blue-Violet Cloth", 37),
            Dye("VioletCloth", "Violet Cloth", 38),
            Dye("BrightVioletCloth", "Bright Violet Cloth", 39),
            Dye("PurpleCloth", "Purple Cloth", 40),
            Dye("BrightPurpleCloth", "Bright Purple Cloth", 41),
            Dye("PurpleRedCloth", "Purple-Red Cloth", 42),
            Dye("BlackCloth", "Black Cloth", 43),
            Dye("BrownCloth", "Brown Cloth", 44),
            Dye("BlueMetal", "Blue Metal", 45),
            Dye("GreenMetal", "Green Metal", 46),
            Dye("YellowMetal", "Yellow Metal", 47),
            Dye("GoldMetal", "Gold Metal", 48),
            Dye("RedMetal", "Red Metal", 49),
            Dye("PurpleMetal", "Purple Metal", 50),
            Dye("Blue1", "Blue 1", 51),
            Dye("Blue2", "Blue 2", 52),
            Dye("Blue3", "Blue 3", 53),
            Dye("Blue4", "Blue 4", 54),
            Dye("Turquoise1", "Turquoise 1", 55),
            Dye("Turquoise2", "Turquoise 2", 56),
            Dye("Turquoise3", "Turquoise 3", 57),
            Dye("Teal1", "Teal 1", 58),
            Dye("Teal2", "Teal 2", 59),
            Dye("Teal3", "Teal 3", 60),
            Dye("Brown1", "Brown 1", 61),
            Dye("Brown2", "Brown 2", 62),
            Dye("Brown3", "Brown 3", 63),
            Dye("Red1", "Red 1", 64),
            Dye("Red2", "Red 2", 65),
            Dye("Red3", "Red 3", 66),
            Dye("Red4", "Red 4", 67),
            Dye("Green1", "Green 1", 68),
            Dye("Green2", "Green 2", 69),
            Dye("Green3", "Green 3", 70),
            Dye("Green4", "Green 4", 71),
            Dye("Gray1", "Gray 1", 72),
            Dye("Gray2", "Gray 2", 73),
            Dye("Gray3", "Gray 3", 74),
            Dye("Orange1", "Orange 1", 75),
            Dye("Orange2", "Orange 2", 76),
            Dye("Orange3", "Orange 3", 77),
            Dye("Purple1", "Purple 1", 78),
            Dye("Purple2", "Purple 2", 79),
            Dye("Purple3", "Purple 3", 80),
            Dye("Yellow1", "Yellow 1", 81),
            Dye("Yellow2", "Yellow 2", 82),
            Dye("Yellow3", "Yellow 3", 83),
            Dye("Violet", "violet", 84),
            Dye("Mauve", "Mauve", 85),
            Dye("Blue5", "Blue 5", 86),
            Dye("Purple4", "Purple 4", 87),
            Dye("ShipRed", "Ship Red", 100),
            Dye("ShipRed2", "Ship Red 2", 101),
            Dye("ShipOrange", "Ship Orange", 102),
            Dye("ShipOrange2", "Ship Orange 2", 103),
            Dye("Orange4", "Orange 4", 104),
            Dye("ShipYellow", "Ship Yellow", 105),
            Dye("ShipLimeGreen", "Ship Lime Green", 106),
            Dye("ShipGreen", "Ship Green", 107),
            Dye("ShipGreen2", "Ship Green 2", 108),
            Dye("ShipTurquoise", "Ship Turquoise", 109),
            Dye("ShipTurquoise2", "Ship Turquoise 2", 110),
            Dye("ShipBlue", "Ship Blue", 111),
            Dye("ShipBlue2", "Ship Blue 2", 112),
            Dye("ShipBlue3", "Ship Blue 3", 113),
            Dye("ShipPurple", "Ship Purple", 114),
            Dye("ShipPurple2", "Ship Purple 2", 115),
            Dye("ShipPurple3", "Ship Purple 3", 116),
            Dye("ShipPink", "Ship Pink", 117),
            Dye("ShipCharcoal", "Ship Charcoal", 118),
            Dye("ShipCharcoal2", "Ship Charcoal 2", 119),
            Dye("RedCrafterOnly", "Red - crafter only", 120),
            Dye("PlumCrafterOnly", "Plum - crafter only", 121),
            Dye("PurpleCrafterOnly", "Purple - crafter only", 122),
            Dye("DarkPurpleCrafterOnly", "Dark Purple - crafter only", 123),
            Dye("DuskyPurpleCrafterOnly", "Dusky Purple - crafter only", 124),
            Dye("LightGoldCrafterOnly", "Light Gold - crafter only", 125),
            Dye("DarkGoldCrafterOnly", "Dark Gold - crafter only", 126),
            Dye("DirtyOrangeCrafterOnly", "Dirty Orange - crafter only", 127),
            Dye("DarkTanCrafterOnly", "Dark Tan - crafter only", 128),
            Dye("BrownCrafterOnly", "Brown - crafter only", 129),
            Dye("LightGreenCrafterOnly", "Light Green - crafter only", 130),
            Dye("OliveGreenCrafterOnly", "Olive Green - crafter only", 131),
            Dye("CornflowerBlueCrafterOnly", "Cornflower Blue - crafter only", 132),
            Dye("LightGrayCrafterOnly", "Light Gray - crafter only", 133),
            Dye("HotPinkCrafterOnly", "Hot Pink - crafter only", 134),
            Dye("DuskyRoseCrafterOnly", "Dusky Rose - crafter only", 135),
            Dye("SageGreenCrafterOnly", "Sage Green - crafter only", 136),
            Dye("LimeGreenCrafterOnly", "Lime Green - crafter only", 137),
            Dye("GrayTealCrafterOnly", "Gray Teal - crafter only", 138),
            Dye("GrayBlueCrafterOnly", "Gray Blue - crafter only", 139),
            Dye("OliveGrayCrafterOnly", "Olive Gray - crafter only", 140),
            Dye("NavyBlueCrafterOnly", "Navy Blue - crafter only", 141),
            Dye("ForestGreenCrafterOnly", "Forest Green - crafter only", 142),
            Dye("BurgundyCrafterOnly", "Burgundy - crafter only", 143),
        };

        private static readonly MenuCategory[] DyeCategories =
        {
            new MenuCategory("Blues", "Blues", PickDyes("OldTurquoise", "LeatherBlue", "BlueGreenCloth", "TurquoiseCloth", "LightBlueCloth", "BlueCloth", "BlueVioletCloth", "BlueMetal", "Blue1", "Blue2", "Blue3", "Blue4", "Turquoise1", "Turquoise2", "Turquoise3", "Teal1", "Teal2", "Teal3")),
            new MenuCategory("Greens", "Greens", PickDyes("OldGreen", "LeatherGreen", "LeatherForestGreen", "GreenCloth", "BlueGreenCloth", "YellowGreenCloth", "GreenMetal", "Green1", "Green2", "Green3", "Green4", "ShipLimeGreen", "ShipGreen", "ShipGreen2", "LightGreenCrafterOnly", "OliveGreenCrafterOnly", "SageGreenCrafterOnly", "LimeGreenCrafterOnly", "ForestGreenCrafterOnly")),
            new MenuCategory("Reds", "Reds", PickDyes("OldRed", "LeatherRed", "RedCloth", "PurpleRedCloth", "RedMetal", "Red1", "Red2", "Red3", "Red4", "ShipRed", "ShipRed2", "RedCrafterOnly")),
            new MenuCategory("Yellows", "Yellows", PickDyes("OldYellow", "LeatherYellow", "YellowOrangeCloth", "YellowCloth", "YellowMetal", "Yellow1", "Yellow2", "Yellow3", "LightGoldCrafterOnly", "DarkGoldCrafterOnly", "GoldMetal", "ShipYellow")),
            new MenuCategory("Purples", "Purples", PickDyes("OldPurple", "LeatherPurple", "PurpleCloth", "BrightPurpleCloth", "PurpleMetal", "Purple1", "Purple2", "Purple3", "Purple4", "ShipPurple", "ShipPurple2", "ShipPurple3", "PurpleCrafterOnly", "DarkPurpleCrafterOnly", "DuskyPurpleCrafterOnly")),
            new MenuCategory("Violets", "Violets", PickDyes("LeatherViolet", "VioletCloth", "BrightVioletCloth", "HotPinkCrafterOnly", "DuskyRoseCrafterOnly", "ShipPink", "Violet")),
            new MenuCategory("Oranges", "Oranges", PickDyes("LeatherOrange", "OrangeCloth", "Orange1", "Orange2", "Orange3", "ShipOrange", "ShipOrange2", "DirtyOrangeCrafterOnly")),
            new MenuCategory("Blacks", "Blacks", PickDyes("BlackCloth", "BrownCloth", "Brown1", "Brown2", "Brown3", "BrownCrafterOnly", "Gray", "Gray2", "Gray3", "LightGrayCrafterOnly", "OliveGrayCrafterOnly")),
            new MenuCategory("Other", "Other", PickDyes("Bronze", "Iron", "Steel", "Alloy", "FineAlloy", "Mithril", "Asterite", "Eog", "Xenium", "Vaanum", "Adamantium", "Mauve", "ShipCharcoal", "ShipCharcoal2", "PlumCrafterOnly", "DarkTanCrafterOnly", "White")),
        };

        private static MenuOption[] PickDyes(params string[] keys)
        {
            var result = new MenuOption[keys.Length];

            for (int i = 0; i < keys.Length; i++)
            {
                string translationKey = "Dye." + keys[i];

                foreach (MenuOption option in DyeOptions)
                {
                    if (option.Key == translationKey)
                    {
                        result[i] = option;
                        break;
                    }
                }

                if (result[i] == null)
                    throw new InvalidOperationException("Unknown dye option: " + keys[i]);
            }

            return result;
        }

        public override bool AddToWorld()
        {
            GuildName = "Effect Master";
            Level = 50;
            base.AddToWorld();
            return true;
        }

        public override bool Interact(GamePlayer player)
        {
            if (base.Interact(player))
            {
                TurnTo(player, 500);
                DbInventoryItem item = player.TempProperties.GetProperty<DbInventoryItem>(TempProperty);
                DbInventoryItem displayItem = player.TempProperties.GetProperty<DbInventoryItem>(DisplayedItem);

                if (item == null)
                {
                    SendReply(player, T(player, "CustomNPC.EffectNPC.Greeting"));
                }
                else
                {
                    ReceiveItem(player, item);
                }

                if (displayItem != null)
                    DisplayReskinPreviewTo(player, (DbInventoryItem)displayItem.Clone());

                return true;
            }

            return false;
        }

        public override bool ReceiveItem(GameLiving source, DbInventoryItem item)
        {
            if (source == null || item == null)
                return false;

            if (source is GamePlayer p)
            {
                SendReply(p, T(p, "CustomNPC.EffectNPC.ServicePrompt"));
                p.TempProperties.SetProperty(EFFECTNPC_ITEM_WEAK, item);

                SendReply(p, T(p, "CustomNPC.EffectNPC.ConfirmEffectPrompt"));
                var tmp = (DbInventoryItem) item.Clone();
                p.TempProperties.SetProperty(TempProperty, item);
                p.TempProperties.SetProperty(DisplayedItem, tmp);
            }

            return false;
        }

        public override bool WhisperReceive(GameLiving source, string str)
        {
            if (!base.WhisperReceive(source, str)) return false;

            if (!(source is GamePlayer)) return false;

            GamePlayer player = source as GamePlayer;
            DbInventoryItem item = player.TempProperties.GetProperty<DbInventoryItem>(EFFECTNPC_ITEM_WEAK);

            int cachedEffectID = player.TempProperties.GetProperty<int>(TempEffectId);
            int cachedColorID = player.TempProperties.GetProperty<int>(TempColorId);

            if (item == null) return false;

            string command = str?.Trim();

            if (MatchesCommand(command, "effect") || MatchesCommand(command, "효과"))
            {
                IEnumerable<MenuOption> options = GetEffectOptionsForItem(item.Object_Type);

                if (options == null)
                    SendReply(player, T(player, "CustomNPC.EffectNPC.CannotWorkWithItem"));
                else
                    SendReply(player, BuildOptionList(player, options, "CustomNPC.EffectNPC.ChooseWeaponEffect"));

                return true;
            }

            if (MatchesCommand(command, "dye") || MatchesCommand(command, "염색"))
            {
                SendReply(player, T(player, "CustomNPC.EffectNPC.ColorTypePrompt", BuildCategoryLinks(player)));
                return true;
            }

            if (TrySendDyeCategory(player, command)) return true;

            if (TryPreviewEffect(player, command)) return true;

            if (TryPreviewColor(player, command)) return true;

            if (MatchesCommand(command, "remove all effects") || MatchesCommand(command, "모든 효과 제거"))
            {
                PreviewEffect(player, 0);
                return true;
            }

            if (MatchesCommand(command, "remove dye") || MatchesCommand(command, "염색 제거"))
            {
                SetColor(player, 0);
                return true;
            }

            if (MatchesCommand(command, "confirm effect") || MatchesCommand(command, "효과 확정"))
            {
                SetEffect(player, cachedEffectID);
                return true;
            }

            if (MatchesCommand(command, "confirm color") || MatchesCommand(command, "색상 확정"))
            {
                SetColor(player, cachedColorID);
                return true;
            }

            return true;
        }

        private static IEnumerable<MenuOption> GetEffectOptionsForItem(int objectType)
        {
            switch (objectType)
            {
                case (int)eObjectType.TwoHandedWeapon:
                case (int)eObjectType.LargeWeapons:
                    return Combine(GreatSwordEffects, GreatWeaponEffects);
                case (int)eObjectType.Blunt:
                case (int)eObjectType.CrushingWeapon:
                case (int)eObjectType.Hammer:
                    return Combine(HammerEffects, CrushEffects);
                case (int)eObjectType.SlashingWeapon:
                case (int)eObjectType.Sword:
                case (int)eObjectType.Blades:
                case (int)eObjectType.Piercing:
                case (int)eObjectType.ThrustWeapon:
                case (int)eObjectType.LeftAxe:
                    return Combine(LongswordEffects, ShortswordEffects);
                case (int)eObjectType.Axe:
                    return AxeEffects;
                case (int)eObjectType.Shield:
                    return CrushEffects;
                case (int)eObjectType.Spear:
                case (int)eObjectType.CelticSpear:
                case (int)eObjectType.PolearmWeapon:
                    return Combine(BattlespearEffects, LuggedSpearEffects);
                case (int)eObjectType.Staff:
                    return Combine(StaffEffects, CrushEffects);
                default:
                    return null;
            }
        }

        private static IEnumerable<MenuOption> Combine(params MenuOption[][] groups)
        {
            foreach (MenuOption[] group in groups)
            {
                foreach (MenuOption option in group)
                    yield return option;
            }
        }

        private static string BuildOptionList(GamePlayer player, IEnumerable<MenuOption> options, string headerKey = null)
        {
            var builder = new StringBuilder();

            if (!string.IsNullOrEmpty(headerKey))
                builder.Append(T(player, headerKey));

            foreach (MenuOption option in options)
                builder.Append('[').Append(T(player, option.TranslationKey)).Append("]\n");

            return builder.ToString();
        }

        private static string BuildCategoryLinks(GamePlayer player)
        {
            var builder = new StringBuilder();

            for (int i = 0; i < DyeCategories.Length; i++)
            {
                if (i > 0)
                    builder.Append(i == DyeCategories.Length - 1 ? ", " : ", ");

                builder.Append('[').Append(T(player, DyeCategories[i].TranslationKey)).Append(']');
            }

            return builder.ToString();
        }

        private bool TrySendDyeCategory(GamePlayer player, string command)
        {
            foreach (MenuCategory category in DyeCategories)
            {
                if (!MatchesOption(player, command, category.Command, category.TranslationKey))
                    continue;

                SendReply(player, BuildOptionList(player, category.Options));
                return true;
            }

            return false;
        }

        private bool TryPreviewEffect(GamePlayer player, string command)
        {
            foreach (MenuOption[] group in EffectGroups)
            {
                foreach (MenuOption option in group)
                {
                    if (!MatchesOption(player, command, option))
                        continue;

                    PreviewEffect(player, option.Id);
                    return true;
                }
            }

            return false;
        }

        private bool TryPreviewColor(GamePlayer player, string command)
        {
            foreach (MenuOption option in DyeOptions)
            {
                if (!MatchesOption(player, command, option))
                    continue;

                PreviewColor(player, option.Id);
                return true;
            }

            return false;
        }

        private static bool MatchesOption(GamePlayer player, string command, MenuOption option)
            => MatchesOption(player, command, option.Command, option.TranslationKey);

        private static bool MatchesOption(GamePlayer player, string command, string englishCommand, string translationKey)
            => MatchesCommand(command, englishCommand) || MatchesCommand(command, T(player, translationKey));

        private static bool MatchesCommand(string command, string expected)
            => string.Equals(command, expected, StringComparison.OrdinalIgnoreCase);

        public void SendReply(GamePlayer player, string msg)
        {
            player.Out.SendMessage(msg, eChatType.CT_System, eChatLoc.CL_PopupWindow);
        }
        #region setcolor
        public void SetColor(GamePlayer player, int color)
        {
            DbInventoryItem item = player.TempProperties.GetProperty<DbInventoryItem>(EFFECTNPC_ITEM_WEAK);

            player.TempProperties.RemoveProperty(EFFECTNPC_ITEM_WEAK);

            if (item == null || item.SlotPosition == (int)eInventorySlot.Ground
                || item.OwnerID == null || item.OwnerID != player.InternalID)
            {
                player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "CustomNPC.InvalidItem"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                return;
            }

            if (item.Object_Type == 41 || item.Object_Type == 43 || item.Object_Type == 44 ||
               item.Object_Type == 46)
            {
                SendReply(player, T(player, "CustomNPC.EffectNPC.CannotDye"));
                return;
            }

            m_timer.Enqueue(new ECSGameTimer(this, new ECSGameTimer.ECSTimerCallback(Effect), duration));
            castplayer.Enqueue(player);

            player.Inventory.RemoveItem(item);
            DbItemUnique unique = new DbItemUnique(item.Template);
            unique.Color = color;
            unique.ObjectId = "Unique" + System.Guid.NewGuid().ToString();
            unique.Id_nb = "Unique" + System.Guid.NewGuid().ToString();
            if (GameServer.Database.ExecuteNonQuery("SELECT ItemUnique_ID FROM itemunique WHERE ItemUnique_ID = 'unique.ObjectId'"))
            {
                unique.ObjectId = "Unique" + System.Guid.NewGuid().ToString();
            }
            if (GameServer.Database.ExecuteNonQuery("SELECT Id_nb FROM itemunique WHERE Id_nb = 'unique.Id_nb'"))
            {
                unique.Id_nb = IdGenerator.GenerateID();
            }

            DbInventoryItem newInventoryItem = GameInventoryItem.Create<DbItemUnique>(unique);
            if(item.IsCrafted)
                newInventoryItem.IsCrafted = true;
            if(item.Creator != string.Empty)
                newInventoryItem.Creator = item.Creator;
            newInventoryItem.Count = 1;
            player.Inventory.AddItem(eInventorySlot.FirstEmptyBackpack, newInventoryItem);
            player.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { newInventoryItem });
            //player.RealmPoints -= price;
            //player.RespecRealm();
            //SetRealmLevel(player, (int)player.RealmPoints);

            player.TempProperties.RemoveProperty(TempProperty);
            player.TempProperties.RemoveProperty(DisplayedItem);
            player.TempProperties.RemoveProperty(TempEffectId);
            player.TempProperties.RemoveProperty(TempColorId);

            SendReply(player, T(player, "CustomNPC.EffectNPC.ColorComplete"));

            foreach (GamePlayer visplayer in this.GetPlayersInRadius(WorldMgr.VISIBILITY_DISTANCE))
            {
                visplayer.Out.SendSpellCastAnimation(this, spell, 30);
            }
        }
        #endregion setcolor


        private void PreviewEffect(GamePlayer player, int effect)
        {
            DbInventoryItem item = (DbInventoryItem)player.TempProperties.GetProperty<DbInventoryItem>(TempProperty).Clone();
            DbInventoryItem displayItem = player.TempProperties.GetProperty<DbInventoryItem>(DisplayedItem);
            item.Effect = effect;
            player.TempProperties.SetProperty(TempEffectId, effect);
            DisplayReskinPreviewTo(player, item);
            SendReply(player, T(player, "CustomNPC.EffectNPC.ConfirmEffectPrompt"));
        }

        private void PreviewColor(GamePlayer player, int color)
        {
            DbInventoryItem item = (DbInventoryItem)player.TempProperties.GetProperty<DbInventoryItem>(TempProperty).Clone();
            DbInventoryItem displayItem = player.TempProperties.GetProperty<DbInventoryItem>(DisplayedItem);
            item.Color = color;
            player.TempProperties.SetProperty(TempColorId, color);
            DisplayReskinPreviewTo(player, item);
            SendReply(player, T(player, "CustomNPC.EffectNPC.ConfirmColorPrompt"));
        }

        #region seteffect
        public void SetEffect(GamePlayer player, int effect)
        {
            if (player == null)
                return;

            DbInventoryItem item = player.TempProperties.GetProperty<DbInventoryItem>(EFFECTNPC_ITEM_WEAK);
            player.TempProperties.RemoveProperty(EFFECTNPC_ITEM_WEAK);

            if (item == null)
                return;

            if ((item.Object_Type < 1 || item.Object_Type > 26) || item.Object_Type == 42)
            {
                SendReply(player, T(player, "CustomNPC.EffectNPC.WeaponsAndShieldsOnly"));
                return;
            }

            if (item == null || item.SlotPosition == (int)eInventorySlot.Ground
                || item.OwnerID == null || item.OwnerID != player.InternalID)
            {
                player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "CustomNPC.InvalidItem"), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
                return;
            }

            m_timer.Enqueue(new ECSGameTimer(this, new ECSGameTimer.ECSTimerCallback(Effect), duration));
            castplayer.Enqueue(player);


            player.Inventory.RemoveItem(item);
            DbItemUnique unique = new DbItemUnique(item.Template);
            unique.Effect = effect;
            unique.Id_nb = IdGenerator.GenerateID();
            unique.ObjectId = "Unique" + System.Guid.NewGuid().ToString();
            if (GameServer.Database.ExecuteNonQuery("SELECT ItemUnique_ID FROM itemunique WHERE ItemUnique_ID = 'unique.ObjectId'"))
            {
                unique.ObjectId = "Unique" + System.Guid.NewGuid().ToString();
            }
            if (GameServer.Database.ExecuteNonQuery("SELECT Id_nb FROM itemunique WHERE Id_nb = 'unique.Id_nb'"))
            {
                unique.Id_nb = IdGenerator.GenerateID();
            }

            DbInventoryItem newInventoryItem = GameInventoryItem.Create<DbItemUnique>(unique);
            if(item.IsCrafted)
                newInventoryItem.IsCrafted = true;
            if(item.Creator != string.Empty)
                newInventoryItem.Creator = item.Creator;
            newInventoryItem.Count = 1;
            player.Inventory.AddItem(eInventorySlot.FirstEmptyBackpack, newInventoryItem);
            player.Out.SendInventoryItemsUpdate(new DbInventoryItem[] { newInventoryItem });
            //player.RealmPoints -= price;
            //player.RespecRealm();
            //SetRealmLevel(player, (int)player.RealmPoints);

            player.TempProperties.RemoveProperty(TempProperty);
            player.TempProperties.RemoveProperty(DisplayedItem);
            player.TempProperties.RemoveProperty(TempEffectId);
            player.TempProperties.RemoveProperty(TempColorId);

            SendReply(player, T(player, "CustomNPC.EffectNPC.EffectComplete", item.Name));
            foreach (GamePlayer visplayer in this.GetPlayersInRadius(WorldMgr.VISIBILITY_DISTANCE))
            {
                visplayer.Out.SendSpellCastAnimation(this, spell, 30);
            }
        }
        #endregion seteffect

        public int Effect(ECSGameTimer timer)
        {
            m_timer.Dequeue();
            GamePlayer player = (GamePlayer)castplayer.Dequeue();
            foreach (GamePlayer visplayer in this.GetPlayersInRadius(WorldMgr.VISIBILITY_DISTANCE))
            {
                visplayer.Out.SendSpellEffectAnimation(this, player, spell, 0, false, 1);
            }
            return 0;
        }

        private void DisplayReskinPreviewTo(GamePlayer player, DbInventoryItem item)
        {
            GameNPC display = CreateDisplayNPC(player, item);
            display.AddToWorld();

            var tempAd = new AttackData();
            tempAd.Attacker = display;
            tempAd.Target = display;
            if (item.Hand == 1)
            {
                tempAd.AttackType = AttackData.eAttackType.MeleeTwoHand;
                display.SwitchWeapon(eActiveWeaponSlot.TwoHanded);
            }
            else
            {
                tempAd.AttackType = AttackData.eAttackType.MeleeOneHand;
                display.SwitchWeapon(eActiveWeaponSlot.Standard);
            }

            tempAd.AttackResult = eAttackResult.HitUnstyled;
            display.TargetObject = display;
            display.ObjectState = eObjectState.Active;
            display.attackComponent.AttackState = true;
            display.BroadcastLivingEquipmentUpdate();
            ClientService.UpdateNpcForPlayer(player, display);

            //Uncomment this if you want animations
            // var animationThread = new Thread(() => LoopAnimation(player,item, display,tempAd));
            // animationThread.IsBackground = true;
            // animationThread.Start();
        }

        private GameNPC CreateDisplayNPC(GamePlayer player, DbInventoryItem item)
        {
            var mob = new DisplayModel(player, item);

            //player model contains 5 bits of extra data that causes issues if used
            //for an NPC model. we do this to drop the first 5 bits and fill w/ 0s
            ushort tmpModel = (ushort)(player.Model << 5);
            tmpModel = (ushort)(tmpModel >> 5);

            //Fill the object variables
            mob.X = this.X + 50;
            mob.Y = this.Y;
            mob.Z = this.Z;
            mob.CurrentRegion = this.CurrentRegion;

            return mob;

            /*
            mob.Inventory = new GameNPCInventory(GameNpcInventoryTemplate.EmptyTemplate);
            //mob.Inventory.AddItem((eInventorySlot) item.Item_Type, item);
            player.Out.SendNPCCreate(mob);
            //mob.AddToWorld();*/
        }
    }
}
