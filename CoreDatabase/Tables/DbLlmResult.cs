using System;
using DOL.Database.Attributes;

namespace DOL.Database
{
    [DataTable(TableName = "llm_result")]
    public class DbLlmResult : DataObject
    {
        private string m_resultId = string.Empty;
        private string m_jobId = string.Empty;
        private string m_status = string.Empty;
        private string m_resultJson = string.Empty;
        private string m_validationStatus = string.Empty;
        private string m_validationErrors = string.Empty;
        private DateTime m_createdAt = DateTime.UtcNow;
        private DateTime m_updatedAt = DateTime.UtcNow;

        [PrimaryKey]
        public string ResultId
        {
            get { return m_resultId; }
            set
            {
                Dirty = true;
                m_resultId = value;
            }
        }

        [DataElement(AllowDbNull = false, Varchar = 64, Index = true)]
        public string JobId
        {
            get { return m_jobId; }
            set
            {
                Dirty = true;
                m_jobId = value;
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

        [DataElement(AllowDbNull = false)]
        public string ResultJson
        {
            get { return m_resultJson; }
            set
            {
                Dirty = true;
                m_resultJson = value;
            }
        }

        [DataElement(AllowDbNull = false, Varchar = 32, Index = true)]
        public string ValidationStatus
        {
            get { return m_validationStatus; }
            set
            {
                Dirty = true;
                m_validationStatus = value;
            }
        }

        [DataElement(AllowDbNull = false)]
        public string ValidationErrors
        {
            get { return m_validationErrors; }
            set
            {
                Dirty = true;
                m_validationErrors = value;
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
