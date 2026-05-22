using System;
using System.Collections.Generic;
using DOL.Database;

namespace DOL.GS
{
	public enum KdaocRandomItemTier
	{
		Common,
		Magic,
		Rare,
		Heroic,
		Legendary,
		Mythic,
	}

	public enum KdaocRandomMobRank
	{
		Normal,
		Named,
		Boss,
	}

	public static class KdaocRandomItemService
	{
		public static bool ValidateGeneratedItem(DbItemTemplate item, out string reason)
		{
			reason = string.Empty;

			if (item == null)
			{
				reason = "item is null";
				return false;
			}

			if (string.IsNullOrWhiteSpace(item.Name))
			{
				reason = "item name is empty";
				return false;
			}

			if (item.Model <= 0)
			{
				reason = "item model is empty";
				return false;
			}

			if (IsWeaponSlot(item.Item_Type))
				return ValidateWeapon(item, out reason);

			if (IsArmorSlot(item.Item_Type))
				return ValidateArmor(item, out reason);

			if (IsJewelrySlot(item.Item_Type))
				return ValidateJewelry(item, out reason);

			reason = $"unsupported item slot {item.Item_Type}";
			return false;
		}

		public static void SanitizeWeaponEffect(DbItemTemplate item)
		{
			if (item == null || item.Effect == 0)
				return;

			if (item.Object_Type == (int)eObjectType.FistWraps && (item.Effect == 48 || item.Effect == 49 || item.Effect == 102))
				return;

			item.Effect = 0;
		}

		public static void NormalizeGeneratedItem(DbItemTemplate item)
		{
			if (item == null)
				return;

			SanitizeWeaponEffect(item);
			SanitizeProcSpells(item);

			if (!IsJewelrySlot(item.Item_Type))
				return;

			item.DPS_AF = 0;
			item.SPD_ABS = 0;
			item.Type_Damage = 0;
			item.ProcSpellID = 0;
			item.ProcSpellID1 = 0;
			item.ProcChance = 0;
		}

		public static void SanitizeProcSpells(DbItemTemplate item)
		{
			if (item == null)
				return;

			item.ProcSpellID = 0;
			item.ProcSpellID1 = 0;
			item.ProcChance = 0;
		}

		public static KdaocRandomItemTier RollTier(KdaocRandomMobRank rank)
		{
			int roll = Util.Random(1, 1000);
			int rankBonus = rank switch
			{
				KdaocRandomMobRank.Boss => 180,
				KdaocRandomMobRank.Named => 70,
				_ => 0,
			};

			roll += rankBonus;

			if (roll >= 995)
				return KdaocRandomItemTier.Mythic;
			if (roll >= 970)
				return KdaocRandomItemTier.Legendary;
			if (roll >= 900)
				return KdaocRandomItemTier.Heroic;
			if (roll >= 760)
				return KdaocRandomItemTier.Rare;
			if (roll >= 450)
				return KdaocRandomItemTier.Magic;

			return KdaocRandomItemTier.Common;
		}

		public static KdaocRandomItemTier[] ApplyBossPremiumDropCap(IEnumerable<KdaocRandomItemTier> rolledTiers, int maxPremiumDrops)
		{
			if (rolledTiers == null)
				return Array.Empty<KdaocRandomItemTier>();

			int premiumDrops = 0;
			int premiumLimit = Math.Max(0, maxPremiumDrops);
			List<KdaocRandomItemTier> cappedTiers = new();

			foreach (KdaocRandomItemTier tier in rolledTiers)
			{
				if (!IsPremiumTier(tier))
				{
					cappedTiers.Add(tier);
					continue;
				}

				premiumDrops++;
				cappedTiers.Add(premiumDrops <= premiumLimit ? tier : KdaocRandomItemTier.Rare);
			}

			return cappedTiers.ToArray();
		}

		public static KdaocRandomItemTier[] EnsureBossMinimumLowTierDrops(IEnumerable<KdaocRandomItemTier> rolledTiers, int minimumTotalDrops, int maxDropRolls)
		{
			if (rolledTiers == null)
				return Array.Empty<KdaocRandomItemTier>();

			int maxDrops = Math.Max(0, maxDropRolls);
			int minimumDrops = Math.Clamp(Math.Max(0, minimumTotalDrops), 0, maxDrops);
			List<KdaocRandomItemTier> tiers = new(rolledTiers);

			if (maxDrops > 0 && tiers.Count > maxDrops)
				tiers.RemoveRange(maxDrops, tiers.Count - maxDrops);

			while (tiers.Count < minimumDrops)
				tiers.Add(KdaocRandomItemTier.Magic);

			return tiers.ToArray();
		}

		public static bool IsPremiumTier(KdaocRandomItemTier tier)
		{
			return tier >= KdaocRandomItemTier.Heroic;
		}

		public static bool LooksLikeBossTitle(string name, int level, string titleTokens, int minimumLevel)
		{
			if (level < Math.Max(1, minimumLevel) || string.IsNullOrWhiteSpace(name) || string.IsNullOrWhiteSpace(titleTokens))
				return false;

			string normalizedName = $" {name.ToLowerInvariant().Replace('_', ' ').Replace('-', ' ')} ";
			char[] separators = [';', ',', '|'];
			foreach (string rawToken in titleTokens.Split(separators, StringSplitOptions.RemoveEmptyEntries))
			{
				string token = rawToken.Trim().ToLowerInvariant();
				if (token.Length == 0)
					continue;

				if (normalizedName.Contains($" {token} ", StringComparison.Ordinal))
					return true;
			}

			return false;
		}

		public static void ApplyTierBonuses(DbItemTemplate item, KdaocRandomItemTier tier, KdaocRandomMobRank rank)
		{
			if (item == null)
				return;

			int minimumQuality = tier switch
			{
				KdaocRandomItemTier.Mythic => 100,
				KdaocRandomItemTier.Legendary => 99,
				KdaocRandomItemTier.Heroic => 97,
				KdaocRandomItemTier.Rare => 95,
				KdaocRandomItemTier.Magic => 92,
				_ => 89,
			};

			int minimumBonus = tier switch
			{
				KdaocRandomItemTier.Mythic => 35,
				KdaocRandomItemTier.Legendary => 30,
				KdaocRandomItemTier.Heroic => 22,
				KdaocRandomItemTier.Rare => 15,
				KdaocRandomItemTier.Magic => 8,
				_ => 0,
			};

			item.Quality = Math.Max(item.Quality, minimumQuality);
			item.Bonus = Math.Max(item.Bonus, minimumBonus);

			if (rank == KdaocRandomMobRank.Boss)
				item.Level = Math.Min(50, Math.Max(item.Level, item.Level + 5));
			else if (rank == KdaocRandomMobRank.Named)
				item.Level = Math.Min(50, Math.Max(item.Level, item.Level + 2));

			string prefix = tier switch
			{
				KdaocRandomItemTier.Mythic => "신화:",
				KdaocRandomItemTier.Legendary => "전설:",
				KdaocRandomItemTier.Heroic => "영웅:",
				KdaocRandomItemTier.Rare => "희귀:",
				KdaocRandomItemTier.Magic => "마력:",
				_ => string.Empty,
			};

			if (!string.IsNullOrEmpty(prefix) && !item.Name.StartsWith(prefix, StringComparison.Ordinal))
				item.Name = $"{prefix} {item.Name}";
		}

		public static bool IsWeaponSlot(int itemType)
		{
			return itemType == Slot.RIGHTHAND || itemType == Slot.LEFTHAND || itemType == Slot.TWOHAND || itemType == Slot.RANGED;
		}

		public static bool IsArmorSlot(int itemType)
		{
			return itemType == Slot.HELM || itemType == Slot.HANDS || itemType == Slot.FEET || itemType == Slot.TORSO
				|| itemType == Slot.LEGS || itemType == Slot.ARMS;
		}

		public static bool IsJewelrySlot(int itemType)
		{
			return itemType == Slot.JEWELRY || itemType == Slot.CLOAK || itemType == Slot.NECK || itemType == Slot.WAIST
				|| itemType == Slot.LEFTWRIST || itemType == Slot.RIGHTWRIST || itemType == Slot.LEFTRING
				|| itemType == Slot.RIGHTRING || itemType == Slot.MYTHICAL;
		}

		private static bool ValidateWeapon(DbItemTemplate item, out string reason)
		{
			bool isRealWeapon = item.Object_Type >= (int)eObjectType._FirstWeapon && item.Object_Type <= (int)eObjectType._LastWeapon;
			bool isShield = item.Item_Type == Slot.LEFTHAND && item.Object_Type == (int)eObjectType.Shield;

			if (!isRealWeapon && !isShield)
			{
				reason = $"invalid weapon object type {item.Object_Type}";
				return false;
			}

			if (item.DPS_AF <= 0)
			{
				reason = "weapon dps is empty";
				return false;
			}

			if (item.SPD_ABS <= 0)
			{
				reason = "weapon speed is empty";
				return false;
			}

			if (!isShield && item.Type_Damage <= 0)
			{
				reason = "weapon damage type is empty";
				return false;
			}

			reason = string.Empty;
			return true;
		}

		private static bool ValidateArmor(DbItemTemplate item, out string reason)
		{
			if (item.Object_Type < (int)eObjectType._FirstArmor || item.Object_Type > (int)eObjectType._LastArmor)
			{
				reason = $"invalid armor object type {item.Object_Type}";
				return false;
			}

			if (item.DPS_AF <= 0)
			{
				reason = "armor af is empty";
				return false;
			}

			reason = string.Empty;
			return true;
		}

		private static bool ValidateJewelry(DbItemTemplate item, out string reason)
		{
			if (item.Object_Type != (int)eObjectType.Magical)
			{
				reason = $"invalid jewelry object type {item.Object_Type}";
				return false;
			}

			if (item.DPS_AF != 0 || item.SPD_ABS != 0 || item.Type_Damage != 0)
			{
				reason = "jewelry must not carry weapon stats";
				return false;
			}

			reason = string.Empty;
			return true;
		}
	}
}
