using System.Collections.Generic;
using DOL.Database;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_KdaocRandomItemService
    {
        [Test]
        public void ValidateGeneratedItem_RejectsGenericItemInWeaponSlot()
        {
            DbItemTemplate item = new()
            {
                Name = "broken weapon",
                Item_Type = Slot.RIGHTHAND,
                Object_Type = (int)eObjectType.GenericItem,
                DPS_AF = 120,
                SPD_ABS = 35,
                Type_Damage = (int)eDamageType.Slash,
                Model = 10
            };

            Assert.That(KdaocRandomItemService.ValidateGeneratedItem(item, out string reason), Is.False);
            Assert.That(reason, Does.Contain("weapon object type"));
        }

        [Test]
        public void ValidateGeneratedItem_RejectsWeaponWithoutDamageType()
        {
            DbItemTemplate item = new()
            {
                Name = "broken weapon",
                Item_Type = Slot.RIGHTHAND,
                Object_Type = (int)eObjectType.SlashingWeapon,
                DPS_AF = 120,
                SPD_ABS = 35,
                Type_Damage = 0,
                Model = 10
            };

            Assert.That(KdaocRandomItemService.ValidateGeneratedItem(item, out string reason), Is.False);
            Assert.That(reason, Does.Contain("damage type"));
        }

        [Test]
        public void ValidateGeneratedItem_AllowsInstrumentInRangedSlot()
        {
            DbItemTemplate item = new()
            {
                Name = "training lute",
                Item_Type = Slot.RANGED,
                Object_Type = (int)eObjectType.Instrument,
                DPS_AF = 0,
                SPD_ABS = 0,
                Type_Damage = 0,
                Model = 665
            };

            Assert.That(KdaocRandomItemService.ValidateGeneratedItem(item, out string reason), Is.True, reason);
        }

        [Test]
        public void ValidateGeneratedItem_RejectsJewelryWithWeaponStats()
        {
            DbItemTemplate item = new()
            {
                Name = "broken jewel",
                Item_Type = Slot.CLOAK,
                Object_Type = (int)eObjectType.Magical,
                DPS_AF = 90,
                SPD_ABS = 20,
                Type_Damage = 0,
                Model = 100
            };

            Assert.That(KdaocRandomItemService.ValidateGeneratedItem(item, out string reason), Is.False);
            Assert.That(reason, Does.Contain("jewelry"));
        }

        [Test]
        public void ApplyTierBonuses_NamesAndBoostsBossLegendaryItem()
        {
            DbItemTemplate item = new()
            {
                Name = "asterite sword",
                Level = 45,
                Quality = 95,
                Bonus = 20,
                Item_Type = Slot.RIGHTHAND,
                Object_Type = (int)eObjectType.SlashingWeapon,
                DPS_AF = 150,
                SPD_ABS = 35,
                Type_Damage = (int)eDamageType.Slash,
                Model = 10
            };

            KdaocRandomItemService.ApplyTierBonuses(item, KdaocRandomItemTier.Legendary, KdaocRandomMobRank.Boss);

            Assert.Multiple(() =>
            {
                Assert.That(item.Name, Does.StartWith("Legendary:"));
                Assert.That(item.Quality, Is.GreaterThanOrEqualTo(99));
                Assert.That(item.Bonus, Is.GreaterThanOrEqualTo(30));
                Assert.That(item.Level, Is.EqualTo(50));
            });
        }

        [Test]
        public void ApplyTierBonuses_DoesNotDowngradeLevelFiftyOneWhenMaxAllowsIt()
        {
            DbItemTemplate item = new()
            {
                Name = "asterite sword",
                Level = 51,
                Quality = 95,
                Bonus = 20,
                Item_Type = Slot.RIGHTHAND,
                Object_Type = (int)eObjectType.SlashingWeapon,
                DPS_AF = 165,
                SPD_ABS = 35,
                Type_Damage = (int)eDamageType.Slash,
                Model = 10
            };

            KdaocRandomItemService.ApplyTierBonuses(item, KdaocRandomItemTier.Magic, KdaocRandomMobRank.Named, 51);

            Assert.That(item.Level, Is.EqualTo(51));
        }

        [Test]
        public void SanitizeWeaponEffect_RemovesUnknownModelEffectCombination()
        {
            DbItemTemplate item = new()
            {
                Name = "glowing sword",
                Item_Type = Slot.RIGHTHAND,
                Object_Type = (int)eObjectType.SlashingWeapon,
                DPS_AF = 120,
                SPD_ABS = 35,
                Type_Damage = (int)eDamageType.Slash,
                Model = 9999,
                Effect = 48
            };

            KdaocRandomItemService.SanitizeWeaponEffect(item);

            Assert.That(item.Effect, Is.EqualTo(0));
        }

        [Test]
        public void NormalizeGeneratedItem_RemovesProcSpells()
        {
            DbItemTemplate item = new()
            {
                Name = "proc sword",
                Item_Type = Slot.RIGHTHAND,
                Object_Type = (int)eObjectType.SlashingWeapon,
                DPS_AF = 120,
                SPD_ABS = 35,
                Type_Damage = (int)eDamageType.Slash,
                Model = 10,
                ProcSpellID = 32186,
                ProcSpellID1 = 32177,
                ProcChance = 10
            };

            KdaocRandomItemService.NormalizeGeneratedItem(item);

            Assert.Multiple(() =>
            {
                Assert.That(item.ProcSpellID, Is.EqualTo(0));
                Assert.That(item.ProcSpellID1, Is.EqualTo(0));
                Assert.That(item.ProcChance, Is.EqualTo(0));
            });
        }

        [Test]
        public void ApplyBossPremiumDropCap_KeepsOnlyConfiguredNumberOfHighTiers()
        {
            KdaocRandomItemTier[] tiers =
            [
                KdaocRandomItemTier.Mythic,
                KdaocRandomItemTier.Legendary,
                KdaocRandomItemTier.Heroic,
                KdaocRandomItemTier.Magic,
                KdaocRandomItemTier.Rare
            ];

            KdaocRandomItemTier[] capped = KdaocRandomItemService.ApplyBossPremiumDropCap(tiers, 2);

            Assert.That(capped, Is.EqualTo(new[]
            {
                KdaocRandomItemTier.Mythic,
                KdaocRandomItemTier.Legendary,
                KdaocRandomItemTier.Rare,
                KdaocRandomItemTier.Magic,
                KdaocRandomItemTier.Rare
            }));
        }

        [Test]
        public void ApplyBossPremiumDropCap_DoesNotDowngradeWhenLimitAllowsAllPremiumTiers()
        {
            KdaocRandomItemTier[] tiers =
            [
                KdaocRandomItemTier.Mythic,
                KdaocRandomItemTier.Legendary
            ];

            KdaocRandomItemTier[] capped = KdaocRandomItemService.ApplyBossPremiumDropCap(tiers, 2);

            Assert.That(capped, Is.EqualTo(tiers));
        }

        [Test]
        public void EnsureBossMinimumLowTierDrops_AddsMagicItemsWithoutIncreasingPremiumCount()
        {
            KdaocRandomItemTier[] tiers =
            [
                KdaocRandomItemTier.Mythic,
                KdaocRandomItemTier.Legendary
            ];

            KdaocRandomItemTier[] expanded = KdaocRandomItemService.EnsureBossMinimumLowTierDrops(tiers, 5, 8);

            Assert.That(expanded, Is.EqualTo(new[]
            {
                KdaocRandomItemTier.Mythic,
                KdaocRandomItemTier.Legendary,
                KdaocRandomItemTier.Magic,
                KdaocRandomItemTier.Magic,
                KdaocRandomItemTier.Magic
            }));
        }

        [Test]
        public void EnsureBossMinimumLowTierDrops_RespectsMaxDropCap()
        {
            KdaocRandomItemTier[] expanded = KdaocRandomItemService.EnsureBossMinimumLowTierDrops(
                [KdaocRandomItemTier.Heroic],
                5,
                3);

            Assert.That(expanded, Is.EqualTo(new[]
            {
                KdaocRandomItemTier.Heroic,
                KdaocRandomItemTier.Magic,
                KdaocRandomItemTier.Magic
            }));
        }

        [Test]
        public void LooksLikeBossTitle_MatchesHighLevelTitledDatabaseBosses()
        {
            Assert.That(KdaocRandomItemService.LooksLikeBossTitle("Lord Elidyn", 59, "lord;king;queen", 55), Is.True);
            Assert.That(KdaocRandomItemService.LooksLikeBossTitle("forest guardian", 59, "lord;king;queen", 55), Is.False);
            Assert.That(KdaocRandomItemService.LooksLikeBossTitle("Lord Recruit", 30, "lord;king;queen", 55), Is.False);
        }

        [Test]
        public void SelectHighestDamageLootPlayer_PicksHighestPositiveDamagePlayer()
        {
            string resolved = KdaocRandomItemLootGenerator.SelectHighestDamageLootPlayer(new[]
            {
                new KeyValuePair<string, double>("zero-damage-group-member", 0),
                new KeyValuePair<string, double>("lower-damage-player", 25),
                new KeyValuePair<string, double>("top-damage-player", 100)
            });

            Assert.That(resolved, Is.EqualTo("top-damage-player"));
        }

        [Test]
        public void SelectHighestDamageLootPlayer_DoesNotUseZeroDamageFallback()
        {
            string resolved = KdaocRandomItemLootGenerator.SelectHighestDamageLootPlayer(new[]
            {
                new KeyValuePair<string, double>("zero-damage-group-member", 0)
            });

            Assert.That(resolved, Is.Null);
        }

        [Test]
        public void ShouldSkipLegacyRandomItemGeneratorForTest_SkipsROG()
        {
            Assert.That(LootMgr.ShouldSkipLegacyRandomItemGeneratorForTest("DOL.GS.ROGMobGenerator"), Is.True);
        }

        [Test]
        public void ShouldSkipLegacyRandomItemGeneratorForTest_SkipsShortROGClassName()
        {
            Assert.That(LootMgr.ShouldSkipLegacyRandomItemGeneratorForTest("ROGMobGenerator"), Is.True);
        }

        [Test]
        public void ShouldSkipLegacyRandomItemGeneratorForTest_DoesNotSkipTemplateGenerator()
        {
            Assert.That(LootMgr.ShouldSkipLegacyRandomItemGeneratorForTest("DOL.GS.LootGeneratorTemplate"), Is.False);
        }
    }
}
