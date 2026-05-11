using System;
using DOL.Database.Attributes;

namespace DOL.Database
{
    [DataTable(TableName = "dashboard_realm_activity")]
    public class DbDashboardRealmActivity : DataObject
    {
        private string m_bucketRealmKey = string.Empty;
        private DateTime m_bucketStart;
        private int m_realm;
        private long m_serverIssuedGold;
        private long m_serverIssuedRealmPoints;

        [PrimaryKey]
        public string BucketRealmKey
        {
            get { return m_bucketRealmKey; }
            set
            {
                Dirty = true;
                m_bucketRealmKey = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public DateTime BucketStart
        {
            get { return m_bucketStart; }
            set
            {
                Dirty = true;
                m_bucketStart = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public int Realm
        {
            get { return m_realm; }
            set
            {
                Dirty = true;
                m_realm = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public long ServerIssuedGold
        {
            get { return m_serverIssuedGold; }
            set
            {
                Dirty = true;
                m_serverIssuedGold = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public long ServerIssuedRealmPoints
        {
            get { return m_serverIssuedRealmPoints; }
            set
            {
                Dirty = true;
                m_serverIssuedRealmPoints = value;
            }
        }
    }
}
