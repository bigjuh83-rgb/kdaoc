using System;
using DOL.Database.Attributes;

namespace DOL.Database
{
    [DataTable(TableName = "llm_job")]
    public class DbLlmJob : DataObject
    {
        private string m_jobId = string.Empty;
        private string m_jobType = string.Empty;
        private string m_status = string.Empty;
        private string m_eventId = string.Empty;
        private string m_language = string.Empty;
        private string m_payloadJson = string.Empty;
        private int m_attemptCount;
        private string m_lastError = string.Empty;
        private DateTime m_createdAt = DateTime.UtcNow;
        private DateTime m_updatedAt = DateTime.UtcNow;

        [PrimaryKey]
        public string JobId
        {
            get { return m_jobId; }
            set
            {
                Dirty = true;
                m_jobId = value;
            }
        }

        [DataElement(AllowDbNull = false, Varchar = 64, Index = true)]
        public string JobType
        {
            get { return m_jobType; }
            set
            {
                Dirty = true;
                m_jobType = value;
            }
        }

        [DataElement(AllowDbNull = false, Varchar = 32, Index = true)]
        public string Status
        {
            get { return m_status; }
            set
            {
                Dirty = true;
                m_status = value;
            }
        }

        [DataElement(AllowDbNull = false, Varchar = 64, Index = true)]
        public string EventId
        {
            get { return m_eventId; }
            set
            {
                Dirty = true;
                m_eventId = value;
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
        public string PayloadJson
        {
            get { return m_payloadJson; }
            set
            {
                Dirty = true;
                m_payloadJson = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public int AttemptCount
        {
            get { return m_attemptCount; }
            set
            {
                Dirty = true;
                m_attemptCount = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public string LastError
        {
            get { return m_lastError; }
            set
            {
                Dirty = true;
                m_lastError = value;
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
