using System;
using DOL.Database.Attributes;

namespace DOL.Database
{
    [DataTable(TableName = "dashboard_rvr_kill")]
    public class DbDashboardRvrKill : DataObject
    {
        private string m_killId = string.Empty;
        private DateTime m_killedAt;
        private string m_killerName = string.Empty;
        private int m_killerRealm;
        private int m_killerClassId;
        private string m_killerClassName = string.Empty;
        private string m_killerGuildName = string.Empty;
        private string m_victimName = string.Empty;
        private int m_victimRealm;
        private int m_victimClassId;
        private string m_victimClassName = string.Empty;
        private string m_victimGuildName = string.Empty;
        private string m_regionName = string.Empty;
        private int m_realmPoints;
        private bool m_soloKill;

        [PrimaryKey]
        public string KillId
        {
            get { return m_killId; }
            set
            {
                Dirty = true;
                m_killId = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public DateTime KilledAt
        {
            get { return m_killedAt; }
            set
            {
                Dirty = true;
                m_killedAt = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public string KillerName
        {
            get { return m_killerName; }
            set
            {
                Dirty = true;
                m_killerName = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public int KillerRealm
        {
            get { return m_killerRealm; }
            set
            {
                Dirty = true;
                m_killerRealm = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public int KillerClassId
        {
            get { return m_killerClassId; }
            set
            {
                Dirty = true;
                m_killerClassId = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public string KillerClassName
        {
            get { return m_killerClassName; }
            set
            {
                Dirty = true;
                m_killerClassName = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public string KillerGuildName
        {
            get { return m_killerGuildName; }
            set
            {
                Dirty = true;
                m_killerGuildName = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public string VictimName
        {
            get { return m_victimName; }
            set
            {
                Dirty = true;
                m_victimName = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public int VictimRealm
        {
            get { return m_victimRealm; }
            set
            {
                Dirty = true;
                m_victimRealm = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public int VictimClassId
        {
            get { return m_victimClassId; }
            set
            {
                Dirty = true;
                m_victimClassId = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public string VictimClassName
        {
            get { return m_victimClassName; }
            set
            {
                Dirty = true;
                m_victimClassName = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public string VictimGuildName
        {
            get { return m_victimGuildName; }
            set
            {
                Dirty = true;
                m_victimGuildName = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public string RegionName
        {
            get { return m_regionName; }
            set
            {
                Dirty = true;
                m_regionName = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public int RealmPoints
        {
            get { return m_realmPoints; }
            set
            {
                Dirty = true;
                m_realmPoints = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public bool SoloKill
        {
            get { return m_soloKill; }
            set
            {
                Dirty = true;
                m_soloKill = value;
            }
        }
    }
}
