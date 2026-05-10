using DOL.Database;
using DOL.GS.Quests;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_RewardQuestRewards
    {
        [TestCase(-1)]
        [TestCase(1)]
        public void Choose_WithOutOfRangeRewardIndex_ReturnsFalse(int rewardIndex)
        {
            RewardQuest.QuestRewards rewards = new(new RewardQuest());
            rewards.AddOptionalItem(new DbItemTemplate());

            bool chosen = rewards.Choose(rewardIndex);

            Assert.That(chosen, Is.False);
            Assert.That(rewards.ChosenItems, Is.Empty);
        }
    }
}
