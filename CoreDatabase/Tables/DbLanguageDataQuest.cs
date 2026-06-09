using DOL.Database.Attributes;

namespace DOL.Database
{
    [DataTable(TableName = "LanguageDataQuest")]
    public class DbLanguageDataQuest : LanguageDataObject
    {
        private string m_name = string.Empty;
        private string m_description = string.Empty;
        private string m_sourceText = string.Empty;
        private string m_stepText = string.Empty;
        private string m_targetText = string.Empty;
        private string m_finishText = string.Empty;

        public override eTranslationIdentifier TranslationIdentifier
        {
            get { return eTranslationIdentifier.eDataQuest; }
        }

        [DataElement(AllowDbNull = true)]
        public string Name
        {
            get { return m_name; }
            set { Dirty = true; m_name = value; }
        }

        [DataElement(AllowDbNull = true)]
        public string Description
        {
            get { return m_description; }
            set { Dirty = true; m_description = value; }
        }

        [DataElement(AllowDbNull = true)]
        public string SourceText
        {
            get { return m_sourceText; }
            set { Dirty = true; m_sourceText = value; }
        }

        [DataElement(AllowDbNull = true)]
        public string StepText
        {
            get { return m_stepText; }
            set { Dirty = true; m_stepText = value; }
        }

        [DataElement(AllowDbNull = true)]
        public string TargetText
        {
            get { return m_targetText; }
            set { Dirty = true; m_targetText = value; }
        }

        [DataElement(AllowDbNull = true)]
        public string FinishText
        {
            get { return m_finishText; }
            set { Dirty = true; m_finishText = value; }
        }
    }
}
