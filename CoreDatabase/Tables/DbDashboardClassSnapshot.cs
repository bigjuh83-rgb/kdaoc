using System;
using DOL.Database.Attributes;

namespace DOL.Database
{
    [DataTable(TableName = "dashboard_class_snapshot")]
    public class DbDashboardClassSnapshot : DataObject
    {
        private string m_snapshotClassKey = string.Empty;
        private DateTime m_bucketStart;
        private int m_realm;
        private string m_realmName = string.Empty;
        private int m_classId;
        private string m_className = string.Empty;
        private int m_players;

        [PrimaryKey]
        public string SnapshotClassKey
        {
            get { return m_snapshotClassKey; }
            set
            {
                Dirty = true;
                m_snapshotClassKey = value;
            }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public DateTime BucketStart
        {
            get { return m_bucketStart; }
            set
            {
                Dirty = true;
                m_bucketStart = value;
            }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public int Realm
        {
            get { return m_realm; }
            set
            {
                Dirty = true;
                m_realm = value;
            }
        }

        [DataElement(AllowDbNull = false, Varchar = 32)]
        public string RealmName
        {
            get { return m_realmName; }
            set
            {
                Dirty = true;
                m_realmName = value;
            }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public int ClassId
        {
            get { return m_classId; }
            set
            {
                Dirty = true;
                m_classId = value;
            }
        }

        [DataElement(AllowDbNull = false, Varchar = 64)]
        public string ClassName
        {
            get { return m_className; }
            set
            {
                Dirty = true;
                m_className = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public int Players
        {
            get { return m_players; }
            set
            {
                Dirty = true;
                m_players = value;
            }
        }
    }
}
