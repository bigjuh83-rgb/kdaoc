using System.Reflection;
using DOL.Database;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_ItemModel
    {
        [TestCase(Slot.RIGHTHAND)]
        [TestCase(Slot.TWOHAND)]
        public void IsValidHealerChampionHammer_WithHammerInSupportedSlot_ShouldReturnTrue(int slot)
        {
            DbInventoryItem item = new DbInventoryItem
            {
                Item_Type = slot,
                Object_Type = (int)eObjectType.Hammer
            };

            Assert.That(IsValidHealerChampionHammer(item), Is.True);
        }

        [Test]
        public void IsValidHealerChampionHammer_WithHammerInUnsupportedSlot_ShouldReturnFalse()
        {
            DbInventoryItem item = new DbInventoryItem
            {
                Item_Type = Slot.LEFTHAND,
                Object_Type = (int)eObjectType.Hammer
            };

            Assert.That(IsValidHealerChampionHammer(item), Is.False);
        }

        [Test]
        public void IsValidHealerChampionHammer_WithNonHammer_ShouldReturnFalse()
        {
            DbInventoryItem item = new DbInventoryItem
            {
                Item_Type = Slot.RIGHTHAND,
                Object_Type = (int)eObjectType.Sword
            };

            Assert.That(IsValidHealerChampionHammer(item), Is.False);
        }

        private static bool IsValidHealerChampionHammer(DbInventoryItem item)
        {
            MethodInfo method = typeof(ItemModel).GetMethod("IsValidHealerChampionHammer", BindingFlags.Static | BindingFlags.NonPublic);
            Assert.That(method, Is.Not.Null);

            return (bool)method.Invoke(null, new object[] { item });
        }
    }
}
