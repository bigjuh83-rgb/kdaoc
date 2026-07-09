using DOL.GS.ServerProperties;
using DOL.GS.WorldAI;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_DynamicQuestReactiveRuntime
    {
        [SetUp]
        public void SetUp()
        {
            DynamicQuestRuntimeService.Instance.ClearAll();
            DynamicQuestReactiveRuntime.ResetForTest();
            Properties.KDAOC_DYNAMIC_QUEST_ENABLED = false;
        }

        [TearDown]
        public void TearDown()
        {
            DynamicQuestReactiveRuntime.ResetForTest();
            DynamicQuestRuntimeService.Instance.ClearAll();
            Properties.KDAOC_DYNAMIC_QUEST_ENABLED = false;
        }

        [Test]
        public void TickForTest_DoesNotAdvanceWhenDynamicQuestsAreDisabled()
        {
            DynamicQuestReactiveRuntime.TickForTest();

            Assert.That(DynamicQuestReactiveRuntime.LastTickAt, Is.EqualTo(default(System.DateTime)));
        }

        [Test]
        public void TickForTest_RecordsTickWhenDynamicQuestsAreEnabled()
        {
            Properties.KDAOC_DYNAMIC_QUEST_ENABLED = true;

            DynamicQuestReactiveRuntime.TickForTest();

            Assert.Multiple(() =>
            {
                Assert.That(DynamicQuestReactiveRuntime.LastTickAt, Is.Not.EqualTo(default(System.DateTime)));
                Assert.That(DynamicQuestReactiveRuntime.LastTimeoutAdvancedCount, Is.GreaterThanOrEqualTo(0));
            });
        }
    }
}
