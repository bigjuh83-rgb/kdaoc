using System;
using DOL.Database.Attributes;

namespace DOL.Database
{
    [DataTable(TableName = "dynamic_quest_progress")]
    public class DbDynamicQuestProgress : DataObject
    {
        private string m_progressId = string.Empty;
        private string m_playerKey = string.Empty;
        private string m_playerName = string.Empty;
        private string m_questId = string.Empty;
        private int m_count;
        private bool m_isComplete;
        private string m_currentNodeId = string.Empty;
        private string m_nodeCountersJson = string.Empty;
        private string m_completedNodeIdsJson = string.Empty;
        private string m_choiceHistoryJson = string.Empty;
        private string m_questSnapshotJson = string.Empty;
        private string m_bindingKey = string.Empty;
        private string m_worldRevision = string.Empty;
        private string m_cancelReason = string.Empty;
        private bool m_failed;
        private bool m_completed;
        private bool m_isActive;
        private DateTime m_acceptedAt = DateTime.UtcNow;
        private DateTime m_createdAt = DateTime.UtcNow;
        private DateTime m_updatedAt = DateTime.UtcNow;

        [PrimaryKey]
        public string ProgressId
        {
            get { return m_progressId; }
            set { Dirty = true; m_progressId = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 128, Index = true)]
        public string PlayerKey
        {
            get { return m_playerKey; }
            set { Dirty = true; m_playerKey = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 64)]
        public string PlayerName
        {
            get { return m_playerName; }
            set { Dirty = true; m_playerName = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 96, Index = true)]
        public string QuestId
        {
            get { return m_questId; }
            set { Dirty = true; m_questId = value; }
        }

        [DataElement(AllowDbNull = false)]
        public int Count
        {
            get { return m_count; }
            set { Dirty = true; m_count = value; }
        }

        [DataElement(AllowDbNull = false)]
        public bool IsComplete
        {
            get { return m_isComplete; }
            set { Dirty = true; m_isComplete = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 64, Index = true)]
        public string CurrentNodeId
        {
            get { return m_currentNodeId; }
            set { Dirty = true; m_currentNodeId = value; }
        }

        [DataElement(AllowDbNull = false)]
        public string NodeCountersJson
        {
            get { return m_nodeCountersJson; }
            set { Dirty = true; m_nodeCountersJson = value; }
        }

        [DataElement(AllowDbNull = false)]
        public string CompletedNodeIdsJson
        {
            get { return m_completedNodeIdsJson; }
            set { Dirty = true; m_completedNodeIdsJson = value; }
        }

        [DataElement(AllowDbNull = false)]
        public string ChoiceHistoryJson
        {
            get { return m_choiceHistoryJson; }
            set { Dirty = true; m_choiceHistoryJson = value; }
        }

        [DataElement(AllowDbNull = false)]
        public string QuestSnapshotJson
        {
            get { return m_questSnapshotJson; }
            set { Dirty = true; m_questSnapshotJson = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 128, Index = true)]
        public string BindingKey
        {
            get { return m_bindingKey; }
            set { Dirty = true; m_bindingKey = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 128, Index = true)]
        public string WorldRevision
        {
            get { return m_worldRevision; }
            set { Dirty = true; m_worldRevision = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 128)]
        public string CancelReason
        {
            get { return m_cancelReason; }
            set { Dirty = true; m_cancelReason = value; }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public bool Failed
        {
            get { return m_failed; }
            set { Dirty = true; m_failed = value; }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public bool Completed
        {
            get { return m_completed; }
            set { Dirty = true; m_completed = value; }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public bool IsActive
        {
            get { return m_isActive; }
            set { Dirty = true; m_isActive = value; }
        }

        [DataElement(AllowDbNull = false)]
        public DateTime AcceptedAt
        {
            get { return m_acceptedAt; }
            set { Dirty = true; m_acceptedAt = value; }
        }

        [DataElement(AllowDbNull = false)]
        public DateTime CreatedAt
        {
            get { return m_createdAt; }
            set { Dirty = true; m_createdAt = value; }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public DateTime UpdatedAt
        {
            get { return m_updatedAt; }
            set { Dirty = true; m_updatedAt = value; }
        }
    }
}
