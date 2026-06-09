using System;
using DOL.Database.Attributes;

namespace DOL.Database
{
    [DataTable(TableName = "dynamic_quest_template")]
    public class DbDynamicQuestTemplate : DataObject
    {
        private string m_templateId = string.Empty;
        private string m_title = string.Empty;
        private string m_storySeed = string.Empty;
        private string m_offerText = string.Empty;
        private string m_progressText = string.Empty;
        private string m_finishText = string.Empty;
        private string m_realm = string.Empty;
        private string m_preferredStartNpcName = string.Empty;
        private ushort m_preferredRegionId;
        private string m_targetNameHint = string.Empty;
        private int m_count = 1;
        private int m_minLevel = 1;
        private int m_maxLevel = 50;
        private string m_source = string.Empty;
        private string m_tagsJson = string.Empty;
        private string m_storyProvider = string.Empty;
        private string m_storyModel = string.Empty;
        private int m_storyQualityScore;
        private string m_storyQualityJson = string.Empty;
        private string m_storyNarrativeJson = string.Empty;
        private string m_storyPresentationJson = string.Empty;
        private DateTime m_storyGeneratedAt = DateTime.MinValue;
        private DateTime m_storyLastUsedAt = DateTime.MinValue;
        private string m_startMode = "NpcOffer";
        private string m_trigger = string.Empty;
        private string m_startNpcInternalId = string.Empty;
        private string m_lastBindingKey = string.Empty;
        private bool m_isActive = true;
        private DateTime m_createdAt = DateTime.UtcNow;
        private DateTime m_updatedAt = DateTime.UtcNow;

        [PrimaryKey]
        public string TemplateId
        {
            get { return m_templateId; }
            set { Dirty = true; m_templateId = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 120)]
        public string Title
        {
            get { return m_title; }
            set { Dirty = true; m_title = value; }
        }

        [DataElement(AllowDbNull = false)]
        public string StorySeed
        {
            get { return m_storySeed; }
            set { Dirty = true; m_storySeed = value; }
        }

        [DataElement(AllowDbNull = false)]
        public string OfferText
        {
            get { return m_offerText; }
            set { Dirty = true; m_offerText = value; }
        }

        [DataElement(AllowDbNull = false)]
        public string ProgressText
        {
            get { return m_progressText; }
            set { Dirty = true; m_progressText = value; }
        }

        [DataElement(AllowDbNull = false)]
        public string FinishText
        {
            get { return m_finishText; }
            set { Dirty = true; m_finishText = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 32, Index = true)]
        public string Realm
        {
            get { return m_realm; }
            set { Dirty = true; m_realm = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 100, Index = true)]
        public string PreferredStartNpcName
        {
            get { return m_preferredStartNpcName; }
            set { Dirty = true; m_preferredStartNpcName = value; }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public ushort PreferredRegionId
        {
            get { return m_preferredRegionId; }
            set { Dirty = true; m_preferredRegionId = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 100, Index = true)]
        public string TargetNameHint
        {
            get { return m_targetNameHint; }
            set { Dirty = true; m_targetNameHint = value; }
        }

        [DataElement(AllowDbNull = false)]
        public int Count
        {
            get { return m_count; }
            set { Dirty = true; m_count = value; }
        }

        [DataElement(AllowDbNull = false)]
        public int MinLevel
        {
            get { return m_minLevel; }
            set { Dirty = true; m_minLevel = value; }
        }

        [DataElement(AllowDbNull = false)]
        public int MaxLevel
        {
            get { return m_maxLevel; }
            set { Dirty = true; m_maxLevel = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 32, Index = true)]
        public string Source
        {
            get { return m_source; }
            set { Dirty = true; m_source = value; }
        }

        [DataElement(AllowDbNull = false)]
        public string TagsJson
        {
            get { return m_tagsJson; }
            set { Dirty = true; m_tagsJson = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 64, Index = true)]
        public string StoryProvider
        {
            get { return m_storyProvider; }
            set { Dirty = true; m_storyProvider = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 128, Index = true)]
        public string StoryModel
        {
            get { return m_storyModel; }
            set { Dirty = true; m_storyModel = value; }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public int StoryQualityScore
        {
            get { return m_storyQualityScore; }
            set { Dirty = true; m_storyQualityScore = value; }
        }

        [DataElement(AllowDbNull = false)]
        public string StoryQualityJson
        {
            get { return m_storyQualityJson; }
            set { Dirty = true; m_storyQualityJson = value; }
        }

        [DataElement(AllowDbNull = false)]
        public string StoryNarrativeJson
        {
            get { return m_storyNarrativeJson; }
            set { Dirty = true; m_storyNarrativeJson = value; }
        }

        [DataElement(AllowDbNull = false)]
        public string StoryPresentationJson
        {
            get { return m_storyPresentationJson; }
            set { Dirty = true; m_storyPresentationJson = value; }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public DateTime StoryGeneratedAt
        {
            get { return m_storyGeneratedAt; }
            set { Dirty = true; m_storyGeneratedAt = value; }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public DateTime StoryLastUsedAt
        {
            get { return m_storyLastUsedAt; }
            set { Dirty = true; m_storyLastUsedAt = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 32, Index = true)]
        public string StartMode
        {
            get { return m_startMode; }
            set { Dirty = true; m_startMode = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 128, Index = true)]
        public string Trigger
        {
            get { return m_trigger; }
            set { Dirty = true; m_trigger = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 128)]
        public string StartNpcInternalId
        {
            get { return m_startNpcInternalId; }
            set { Dirty = true; m_startNpcInternalId = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 128)]
        public string LastBindingKey
        {
            get { return m_lastBindingKey; }
            set { Dirty = true; m_lastBindingKey = value; }
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

        [DataElement(AllowDbNull = false, Index = true)]
        public DateTime UpdatedAt
        {
            get { return m_updatedAt; }
            set { Dirty = true; m_updatedAt = value; }
        }
    }
}
