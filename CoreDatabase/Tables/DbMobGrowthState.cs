using System;
using DOL.Database.Attributes;

namespace DOL.Database
{
    [DataTable(TableName = "mob_growth_state")]
    public class DbMobGrowthState : DataObject
    {
        private string m_mobId = string.Empty;
        private string m_baseName = string.Empty;
        private string m_currentName = string.Empty;
        private string m_region = string.Empty;
        private ushort m_regionId;
        private int m_baseLevel;
        private int m_growthLevel;
        private int m_effectiveLevel;
        private int m_growthScore;
        private int m_survivalTicks;
        private int m_unhuntedTicks;
        private int m_combatCount;
        private int m_playerKills;
        private string m_stage = string.Empty;
        private bool m_isActive;
        private DateTime m_createdAt = DateTime.UtcNow;
        private DateTime m_firstSeenAt = DateTime.UtcNow;
        private DateTime m_lastSeenAt = DateTime.UtcNow;
        private DateTime m_lastKilledAt = DateTime.MinValue;
        private DateTime m_lastCombatGrowthAt = DateTime.MinValue;
        private DateTime m_lastStageEventAt = DateTime.MinValue;
        private DateTime m_updatedAt = DateTime.UtcNow;

        [PrimaryKey]
        public string MobId
        {
            get { return m_mobId; }
            set { Dirty = true; m_mobId = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 128, Index = true)]
        public string BaseName
        {
            get { return m_baseName; }
            set { Dirty = true; m_baseName = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 160)]
        public string CurrentName
        {
            get { return m_currentName; }
            set { Dirty = true; m_currentName = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 128)]
        public string Region
        {
            get { return m_region; }
            set { Dirty = true; m_region = value; }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public ushort RegionId
        {
            get { return m_regionId; }
            set { Dirty = true; m_regionId = value; }
        }

        [DataElement(AllowDbNull = false)]
        public int BaseLevel
        {
            get { return m_baseLevel; }
            set { Dirty = true; m_baseLevel = value; }
        }

        [DataElement(AllowDbNull = false)]
        public int GrowthLevel
        {
            get { return m_growthLevel; }
            set { Dirty = true; m_growthLevel = value; }
        }

        [DataElement(AllowDbNull = false)]
        public int EffectiveLevel
        {
            get { return m_effectiveLevel; }
            set { Dirty = true; m_effectiveLevel = value; }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public int GrowthScore
        {
            get { return m_growthScore; }
            set { Dirty = true; m_growthScore = value; }
        }

        [DataElement(AllowDbNull = false)]
        public int SurvivalTicks
        {
            get { return m_survivalTicks; }
            set { Dirty = true; m_survivalTicks = value; }
        }

        [DataElement(AllowDbNull = false)]
        public int UnhuntedTicks
        {
            get { return m_unhuntedTicks; }
            set { Dirty = true; m_unhuntedTicks = value; }
        }

        [DataElement(AllowDbNull = false)]
        public int CombatCount
        {
            get { return m_combatCount; }
            set { Dirty = true; m_combatCount = value; }
        }

        [DataElement(AllowDbNull = false)]
        public int PlayerKills
        {
            get { return m_playerKills; }
            set { Dirty = true; m_playerKills = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 32, Index = true)]
        public string Stage
        {
            get { return m_stage; }
            set { Dirty = true; m_stage = value; }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public bool IsActive
        {
            get { return m_isActive; }
            set { Dirty = true; m_isActive = value; }
        }

        [DataElement(AllowDbNull = false)]
        public DateTime CreatedAt
        {
            get { return m_createdAt; }
            set { Dirty = true; m_createdAt = value; }
        }

        [DataElement(AllowDbNull = false)]
        public DateTime FirstSeenAt
        {
            get { return m_firstSeenAt; }
            set { Dirty = true; m_firstSeenAt = value; }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public DateTime LastSeenAt
        {
            get { return m_lastSeenAt; }
            set { Dirty = true; m_lastSeenAt = value; }
        }

        [DataElement(AllowDbNull = false)]
        public DateTime LastKilledAt
        {
            get { return m_lastKilledAt; }
            set { Dirty = true; m_lastKilledAt = value; }
        }

        [DataElement(AllowDbNull = false)]
        public DateTime LastCombatGrowthAt
        {
            get { return m_lastCombatGrowthAt; }
            set { Dirty = true; m_lastCombatGrowthAt = value; }
        }

        [DataElement(AllowDbNull = false)]
        public DateTime LastStageEventAt
        {
            get { return m_lastStageEventAt; }
            set { Dirty = true; m_lastStageEventAt = value; }
        }

        [DataElement(AllowDbNull = false)]
        public DateTime UpdatedAt
        {
            get { return m_updatedAt; }
            set { Dirty = true; m_updatedAt = value; }
        }
    }
}
