using System;
using DOL.Database.Attributes;

namespace DOL.Database
{
    [DataTable(TableName = "world_event_log")]
    public class DbWorldEventLog : DataObject
    {
        private string m_eventId = string.Empty;
        private string m_eventType = string.Empty;
        private string m_importance = string.Empty;
        private string m_region = string.Empty;
        private string m_actorName = string.Empty;
        private string m_language = string.Empty;
        private string m_rawDataJson = string.Empty;
        private string m_publicTitle = string.Empty;
        private string m_publicText = string.Empty;
        private string m_chronicleText = string.Empty;
        private string m_gmNote = string.Empty;
        private bool m_isPublic;
        private bool m_requiresGmApproval;
        private DateTime m_createdAt = DateTime.UtcNow;
        private DateTime m_updatedAt = DateTime.UtcNow;

        [PrimaryKey]
        public string EventId
        {
            get { return m_eventId; }
            set
            {
                Dirty = true;
                m_eventId = value;
            }
        }

        [DataElement(AllowDbNull = false, Varchar = 64, Index = true)]
        public string EventType
        {
            get { return m_eventType; }
            set
            {
                Dirty = true;
                m_eventType = value;
            }
        }

        [DataElement(AllowDbNull = false, Varchar = 32, Index = true)]
        public string Importance
        {
            get { return m_importance; }
            set
            {
                Dirty = true;
                m_importance = value;
            }
        }

        [DataElement(AllowDbNull = false, Varchar = 128)]
        public string Region
        {
            get { return m_region; }
            set
            {
                Dirty = true;
                m_region = value;
            }
        }

        [DataElement(AllowDbNull = false, Varchar = 128)]
        public string ActorName
        {
            get { return m_actorName; }
            set
            {
                Dirty = true;
                m_actorName = value;
            }
        }

        [DataElement(AllowDbNull = false, Varchar = 16, Index = true)]
        public string Language
        {
            get { return m_language; }
            set
            {
                Dirty = true;
                m_language = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public string RawDataJson
        {
            get { return m_rawDataJson; }
            set
            {
                Dirty = true;
                m_rawDataJson = value;
            }
        }

        [DataElement(AllowDbNull = false, Varchar = 160)]
        public string PublicTitle
        {
            get { return m_publicTitle; }
            set
            {
                Dirty = true;
                m_publicTitle = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public string PublicText
        {
            get { return m_publicText; }
            set
            {
                Dirty = true;
                m_publicText = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public string ChronicleText
        {
            get { return m_chronicleText; }
            set
            {
                Dirty = true;
                m_chronicleText = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public string GmNote
        {
            get { return m_gmNote; }
            set
            {
                Dirty = true;
                m_gmNote = value;
            }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public bool IsPublic
        {
            get { return m_isPublic; }
            set
            {
                Dirty = true;
                m_isPublic = value;
            }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public bool RequiresGmApproval
        {
            get { return m_requiresGmApproval; }
            set
            {
                Dirty = true;
                m_requiresGmApproval = value;
            }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public DateTime CreatedAt
        {
            get { return m_createdAt; }
            set
            {
                Dirty = true;
                m_createdAt = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public DateTime UpdatedAt
        {
            get { return m_updatedAt; }
            set
            {
                Dirty = true;
                m_updatedAt = value;
            }
        }
    }
}
