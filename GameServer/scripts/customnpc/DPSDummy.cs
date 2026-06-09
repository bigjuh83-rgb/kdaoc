using System;
using System.Collections.Generic;
using DOL.Database;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS
{
    public class DPSDummy : GameTrainingDummy
    {
        private int _damage;
        private DateTime _startTime;
        private TimeSpan _timePassed;
        private bool _startCheck = true;

        private static string T(GamePlayer player, string key, params object[] args)
            => LanguageMgr.GetTranslation(player.Client.Account.Language, key, args);

        public override bool Interact(GamePlayer player)
        {
            if (!base.Interact(player))
                return false;

            _damage = 0;
            _startCheck = true;
            Name = "Total: 0 DPS: 0";

            SetDefaultResists();
            SetDefaultArmor();

            SendReply(player, T(player, "CustomNPC.DPSDummy.Greeting"));
            return true;
        }

        public override bool WhisperReceive(GameLiving source, string text)
        {
            if (!base.WhisperReceive(source, text))
                return false;

            if (source is not GamePlayer player)
                return false;

            string[] splitText = text.Split(' ');

            if (splitText.Length > 1)
            {
                if (!int.TryParse(splitText[1], out int value))
                {
                    SendReply(player, T(player, "CustomNPC.DPSDummy.InvalidNumber"));
                    return false;
                }
                else if (value is < 0 or > 100)
                {
                    SendReply(player, T(player, "CustomNPC.DPSDummy.NumberRange"));
                    return false;
                }

                switch (splitText[0].ToLower())
                {
                    case "slash":
                    case "슬래쉬":
                    {
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Slash, value);
                        break;
                    }
                    case "thrust":
                    case "쓰러스트":
                    {
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Thrust, value);
                        break;
                    }
                    case "crush":
                    case "크러쉬":
                    {
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Crush, value);
                        break;
                    }
                    case "body":
                    case "바디":
                    {
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Body, value);
                        break;
                    }
                    case "cold":
                    case "콜드":
                    {
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Cold, value);
                        break;
                    }
                    case "energy":
                    case "에너지":
                    {
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Energy, value);
                        break;
                    }
                    case "heat":
                    case "히트":
                    {
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Heat, value);
                        break;
                    }
                    case "matter":
                    case "매터":
                    {
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Matter, value);
                        break;
                    }
                    case "spirit":
                    case "스피릿":
                    {
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Spirit, value);
                        break;
                    }
                    case "block":
                    case "블록":
                    case "방패막기":
                    {
                        BlockChance = (byte) value;
                        break;
                    }
                    case "parry":
                    case "패리":
                    {
                        ParryChance = (byte) value;
                        break;
                    }
                    case "evade":
                    case "이베이드":
                    {
                        EvadeChance = (byte) value;
                        break;
                    }
                    case "allresist":
                    case "모든저항":
                    case "전체저항":
                    {
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Slash, value);
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Thrust, value);
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Crush, value);
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Body, value);
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Cold, value);
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Energy, value);
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Heat, value);
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Matter, value);
                        ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) eResist.Spirit, value);
                        break;
                    }
                    case "alldefense":
                    case "모든방어":
                    case "전체방어":
                    {
                        BlockChance = (byte) value;
                        EvadeChance = (byte) value;
                        ParryChance = (byte) value;
                        break;
                    }
                }
            }
            else
            {
                switch (splitText[0].ToLower())
                {
                    case "armor":
                    case "방어구":
                    {
                        SendReply(player, T(player, "CustomNPC.DPSDummy.ArmorPrompt"));
                        break;
                    }
                    case "cloth":
                    case "천":
                    {
                        CreateArmorSetOfType(eObjectType.Cloth);
                        break;
                    }
                    case "leather":
                    case "가죽":
                    {
                        CreateArmorSetOfType(eObjectType.Leather);
                        break;
                    }
                    case "studded":
                    case "스터디드":
                    {
                        CreateArmorSetOfType(eObjectType.Studded);
                        break;
                    }
                    case "chain":
                    case "체인":
                    {
                        CreateArmorSetOfType(eObjectType.Chain);
                        break;
                    }
                    case "plate":
                    case "플레이트":
                    {
                        CreateArmorSetOfType(eObjectType.Plate);
                        break;
                    }
                    case "reinforced":
                    case "강화가죽":
                    {
                        CreateArmorSetOfType(eObjectType.Reinforced);
                        break;
                    }
                    case "scale":
                    case "스케일":
                    {
                        CreateArmorSetOfType(eObjectType.Scale);
                        break;
                    }

                    case "resistances":
                    case "저항":
                    {
                        SendReply(player, T(player, "CustomNPC.DPSDummy.ResistancePrompt"));
                        break;
                    }
                    default:
                        break;
                }
            }

            return true;
        }

        private void CreateArmorSetOfType(eObjectType armorType)
        {
            Inventory.ClearInventory();
            ClearAFAndABSBuffs();

            List<int> invSlots =
            [
                Slot.ARMS,
                Slot.FEET,
                Slot.HANDS,
                Slot.HELM,
                Slot.LEGS,
                Slot.TORSO,
            ];

            foreach (int slot in invSlots)
            {
                DbInventoryItem invItem = new()
                {
                    Item_Type = slot,
                    Object_Type = (int) armorType
                };

                invItem = GenerateItemNameModel(invItem);
                invItem = GenerateArmorStats(invItem);
                Inventory.AddItem((eInventorySlot) slot, invItem);
            }

            BroadcastLivingEquipmentUpdate();
            ClientService.UpdateNpcForPlayers(this);
        }

        private DbInventoryItem GenerateArmorStats(DbInventoryItem item)
        {
            eObjectType type = (eObjectType)item.Object_Type;

            if (type is >= eObjectType._FirstArmor and <= eObjectType._LastArmor)
            {
                if (type is eObjectType.GenericArmor)
                    item.DPS_AF = 0;
                else if (type is eObjectType.Cloth)
                    item.DPS_AF = Level;
                else
                    item.DPS_AF = Level * 2;

                item.SPD_ABS = type switch
                {
                    eObjectType.Cloth => 0,
                    eObjectType.Leather => 10,
                    eObjectType.Studded => 19,
                    eObjectType.Reinforced => 19,
                    eObjectType.Chain => 27,
                    eObjectType.Scale => 27,
                    eObjectType.Plate => 34,
                    _ => 0,
                };
            }

            item.Quality = 100;
            item.Condition = 100;
            return item;
        }

        private void ClearAFAndABSBuffs()
        {
            effectListComponent.CancelAll();
        }

        public int GetArmorFactorCap(eObjectType type, out int itemArmorFactorCap)
        {
            // Copy paste of `GamePlayer.GetArmorFactorCap`, without RR5 check.
            if (!GlobalConstants.IsArmor((int) type))
                throw new ArgumentException($"{nameof(type)} must be an armor type");

            int modifiedCharacterLevel = Level;

            // Returns two caps:
            // * One for player AF, which is twice the modified character level and is meant to be applied after base AF buffs.
            // * One for the item AF, which depends on the armor type and is meant to be applied first.
            int playerArmorFactorCap = modifiedCharacterLevel * 2;
            itemArmorFactorCap = type is eObjectType.Cloth ? modifiedCharacterLevel : playerArmorFactorCap;
            return playerArmorFactorCap;
        }

        public override double GetArmorAF(eArmorSlot slot)
        {
            // Mostly a copy paste of `GamePlayer.GetArmorAF`, but we force the slot to torso.
            DbInventoryItem item = Inventory.GetItem(eInventorySlot.TorsoArmor);

            if (item == null)
                return 0;

            int armorFactorCap = GetArmorFactorCap((eObjectType) item.Object_Type, out int itemArmorFactorCap);
            double armorFactor = Math.Min(item.DPS_AF, itemArmorFactorCap); // Cap item AF first.
            armorFactor += BaseBuffBonusCategory[eProperty.ArmorFactor] / 5.0; // Base AF buffs need to be applied manually for players.
            armorFactor *= item.Quality * 0.01 * item.ConditionPercent * 0.01; // Apply condition and quality before the second cap. Maybe incorrect, but it makes base AF buffs a little more useful.
            armorFactor = Math.Min(armorFactor, armorFactorCap);
            armorFactor += GetModified(eProperty.ArmorFactor) / 5.0; // Don't call base here.
            return Math.Max(0, armorFactor);
        }

        public override double GetArmorAbsorb(eArmorSlot slot)
        {
            // Mostly a copy paste of `GamePlayer.GetArmorAF`, but we force the slot to torso.
            DbInventoryItem item = Inventory.GetItem(eInventorySlot.TorsoArmor);

            if (item == null)
                return 0;

            double absorb = item.SPD_ABS * 0.01 * (1 + GetModified(eProperty.ArmorAbsorption) * 0.01);
            return Math.Clamp(absorb, 0, 1); // Debuffs can't lower absorb below 0%: https://darkageofcamelot.com/article/friday-grab-bag-08302019
        }

        private void SetDefaultResists()
        {
            foreach (eResist resist in Enum.GetValues<eResist>())
                ApplyBonus(eBuffBonusCategory.BaseBuff, (eProperty) resist, 26);
        }

        private void SetDefaultArmor()
        {
            // Skip generic armor.
            int armorIndex = Util.Random((int) eObjectType.Cloth, (int) eObjectType._LastArmor);
            CreateArmorSetOfType((eObjectType) armorIndex);
        }

        public override void OnAttackedByEnemy(AttackData ad)
        {
            base.OnAttackedByEnemy(ad);

            if (_startCheck)
            {
                _startTime = DateTime.Now;
                _startCheck = false;
            }

            _damage += ad.Damage + ad.CriticalDamage;
            _timePassed = DateTime.Now - _startTime;
            Name = "Total: " + _damage.ToString() + " DPS: " + (_damage / (_timePassed.TotalSeconds + 1)).ToString("0");
        }

        public override bool AddToWorld()
        {
            if (!base.AddToWorld())
                return false;

            Name = "Total: 0 DPS: 0";
            GuildName = "Dummy Union";
            Model = 34;
            Inventory = new GameNPCInventory(GameNpcInventoryTemplate.EmptyTemplate);
            SetDefaultResists();
            SetDefaultArmor();
            return true;
        }

        private static void SendReply(GamePlayer player, string msg)
        {
            player.Out.SendMessage(msg, eChatType.CT_Merchant, eChatLoc.CL_PopupWindow);
        }

        private static DbInventoryItem GenerateItemNameModel(DbInventoryItem item)
        {
            eInventorySlot slot = (eInventorySlot) item.Item_Type;

            int model = 0;

            switch ((eObjectType) item.Object_Type)
            {
                case eObjectType.Cloth:
                {
                    switch (slot)
                    {
                        case eInventorySlot.ArmsArmor:
                        {
                            model = 141;
                            break;
                        }
                        case eInventorySlot.LegsArmor:
                        {
                            model = 140;
                            break;
                        }
                        case eInventorySlot.FeetArmor:
                        {
                            model = 143;
                            break;
                        }
                        case eInventorySlot.HeadArmor:
                        {
                            model = 822;
                            break;
                        }
                        case eInventorySlot.HandsArmor:
                        {
                            model = 142;
                            break;
                        }
                        case eInventorySlot.TorsoArmor:
                        {
                            if (Util.Chance(60))
                                model = 139;
                            else
                            {
                                switch (Util.Random(2))
                                {
                                    case 0: model = 58; break;
                                    case 1: model = 65; break;
                                    case 2: model = 66; break;
                                }
                            }

                            break;
                        }
                    }

                    break;
                }
                case eObjectType.Leather:
                {
                    switch (slot)
                    {
                        case eInventorySlot.ArmsArmor:
                        {
                            model = 38;
                            break;
                        }
                        case eInventorySlot.LegsArmor:
                        {
                            model = 37;
                            break;
                        }
                        case eInventorySlot.FeetArmor:
                        {
                            model = 40;
                            break;
                        }
                        case eInventorySlot.HeadArmor:
                        {
                            model = 62;
                            break;
                        }
                        case eInventorySlot.TorsoArmor:
                        {
                            model = 36;
                            break;
                        }
                        case eInventorySlot.HandsArmor:
                        {
                            model = 39;
                            break;
                        }
                    }

                    break;
                }
                case eObjectType.Studded:
                {
                    switch (slot)
                    {
                        case eInventorySlot.ArmsArmor:
                        {
                            model = 83;
                            break;
                        }
                        case eInventorySlot.LegsArmor:
                        {
                            model = 82;
                            break;
                        }
                        case eInventorySlot.FeetArmor:
                        {
                            model = 84;
                            break;
                        }
                        case eInventorySlot.HeadArmor:
                        {
                            model = 824;
                            break;
                        }
                        case eInventorySlot.TorsoArmor:
                        {
                            model = 81;
                            break;
                        }
                        case eInventorySlot.HandsArmor:
                        {
                            model = 85;
                            break;
                        }
                    }

                break;
                }
                case eObjectType.Plate:
                {
                    switch (slot)
                    {
                        case eInventorySlot.ArmsArmor:
                        {
                            model = 48;
                            break;
                        }
                        case eInventorySlot.LegsArmor:
                        {
                            model = 47;
                            break;
                        }
                        case eInventorySlot.FeetArmor:
                        {
                            model = 50;
                            break;
                        }
                        case eInventorySlot.HandsArmor:
                        {
                            model = 49;
                            break;
                        }
                        case eInventorySlot.HeadArmor:
                        {
                            if (Util.Chance(25))
                                model = 93;
                            else
                                model = 64;

                            break;
                        }
                        case eInventorySlot.TorsoArmor:
                        {
                            model = 46;
                            break;
                        }
                    }

                    break;
                }
                case eObjectType.Chain:
                {
                    switch (slot)
                    {
                        case eInventorySlot.ArmsArmor:
                        {
                            model = 43;
                            break;
                        }
                        case eInventorySlot.LegsArmor:
                        {
                            model = 42;
                            break;
                        }
                        case eInventorySlot.FeetArmor:
                        {
                            model = 45;
                            break;
                        }
                        case eInventorySlot.HeadArmor:
                        {
                            model = 63;
                            break;
                        }
                        case eInventorySlot.TorsoArmor:
                        {
                            model = 41;
                            break;
                        }
                        case eInventorySlot.HandsArmor:
                        {
                            model = 44;
                            break;
                        }
                    }

                    break;
                }
                case eObjectType.Reinforced:
                {
                    switch (slot)
                    {
                        case eInventorySlot.ArmsArmor:
                        {
                            model = 385;
                            break;
                        }
                        case eInventorySlot.LegsArmor:
                        {
                            model = 384;
                            break;
                        }
                        case eInventorySlot.FeetArmor:
                        {
                            model = 387;
                            break;
                        }
                        case eInventorySlot.HeadArmor:
                        {
                            model = 835;
                            break;
                        }
                        case eInventorySlot.TorsoArmor:
                        {
                            model = 383;
                            break;
                        }
                        case eInventorySlot.HandsArmor:
                        {
                            model = 386;
                            break;
                        }
                    }

                    break;
                }
                case eObjectType.Scale:
                {
                    switch (slot)
                    {
                        case eInventorySlot.ArmsArmor:
                        {
                            model = 390;
                            break;
                        }
                        case eInventorySlot.LegsArmor:
                        {
                            model = 389;
                            break;
                        }
                        case eInventorySlot.FeetArmor:
                        {
                            model = 392;
                            break;
                        }
                        case eInventorySlot.HeadArmor:
                        {
                            model = 838;
                            break;
                        }
                        case eInventorySlot.TorsoArmor:
                        {
                            model = 388;
                            break;
                        }
                        case eInventorySlot.HandsArmor:
                        {
                            model = 391;
                            break;
                        }
                    }

                    break;
                }
                default:
                    break;
            }

            item.Model = model;
            return item;
        }
    }
}
