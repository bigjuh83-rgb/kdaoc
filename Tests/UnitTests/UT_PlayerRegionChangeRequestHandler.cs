using DOL.Database;
using DOL.GS.PacketHandler.Client.v168;
using NUnit.Framework;

namespace DOL.GS.Tests
{
    [TestFixture]
    public class UT_PlayerRegionChangeRequestHandler
    {
        [Test]
        public void CreateWorkingZonePoint_ShouldPreserveCustomHandlerDataForTargetRegionZero()
        {
            DbZonePoint zonePoint = new()
            {
                Id = 7,
                TargetRegion = 0,
                TargetX = 10,
                TargetY = 20,
                TargetZ = 30,
                TargetHeading = 40,
                SourceRegion = 1,
                SourceX = 50,
                SourceY = 60,
                SourceZ = 70,
                Realm = 1,
                ClassType = "DOL.GS.ServerRules.TaskDungeonJumpPoint"
            };

            DbZonePoint workingZonePoint = PlayerRegionChangeRequestHandler.CreateWorkingZonePoint(zonePoint, out bool canPersistSourceInfo);

            Assert.That(workingZonePoint, Is.Not.SameAs(zonePoint));
            Assert.That(canPersistSourceInfo, Is.False);
            Assert.That(workingZonePoint.Id, Is.EqualTo(zonePoint.Id));
            Assert.That(workingZonePoint.ClassType, Is.EqualTo(zonePoint.ClassType));
            Assert.That(workingZonePoint.TargetRegion, Is.Zero);
            Assert.That(workingZonePoint.TargetX, Is.EqualTo(zonePoint.TargetX));
            Assert.That(workingZonePoint.SourceRegion, Is.EqualTo(zonePoint.SourceRegion));
        }

        [Test]
        public void CreateWorkingZonePoint_ShouldKeepNormalZonePointPersistable()
        {
            DbZonePoint zonePoint = new()
            {
                Id = 8,
                TargetRegion = 1
            };

            DbZonePoint workingZonePoint = PlayerRegionChangeRequestHandler.CreateWorkingZonePoint(zonePoint, out bool canPersistSourceInfo);

            Assert.That(workingZonePoint, Is.SameAs(zonePoint));
            Assert.That(canPersistSourceInfo, Is.True);
        }

        [TestCase(19, 1, true)]
        [TestCase(36, 1, true)]
        [TestCase(25, 5, true)]
        [TestCase(25, 4, false)]
        public void IsDeniedByBattlegroundCap_ShouldDenyLevelsOrRealmRanksOutsideCap(int level, int realmLevel, bool expected)
        {
            DbBattleground battleground = new()
            {
                MinLevel = 20,
                MaxLevel = 35,
                MaxRealmLevel = 5
            };

            Assert.That(PlayerRegionChangeRequestHandler.IsDeniedByBattlegroundCap(battleground, level, realmLevel), Is.EqualTo(expected));
        }

        [Test]
        public void IsDeniedByBattlegroundCap_ShouldTreatZeroRealmCapAsUnlimited()
        {
            DbBattleground battleground = new()
            {
                MinLevel = 20,
                MaxLevel = 35,
                MaxRealmLevel = 0
            };

            Assert.That(PlayerRegionChangeRequestHandler.IsDeniedByBattlegroundCap(battleground, 25, 99), Is.False);
        }
    }
}
