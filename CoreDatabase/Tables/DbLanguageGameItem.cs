using DOL.Database.Attributes;

namespace DOL.Database
{
    [DataTable(TableName = "LanguageItem")]
    public class DbLanguageGameItem : LanguageDataObject
    {
        #region Variables
        private string m_name = string.Empty;
        private string m_description = string.Empty;
        private string m_examineArticle = string.Empty;
        private string m_messageArticle = string.Empty;
        #endregion Variables

        public DbLanguageGameItem()
            : base() { }

        #region Properties
        public override eTranslationIdentifier TranslationIdentifier
        {
            get { return eTranslationIdentifier.eItem; }
        }

        /// <summary>
        /// Gets or sets the translated item name.
        /// </summary>
        [DataElement(AllowDbNull = true)]
        public string Name
        {
            get { return m_name; }
            set
            {
                Dirty = true;
                m_name = value;
            }
        }

        /// <summary>
        /// Gets or sets the translated item description.
        /// </summary>
        [DataElement(AllowDbNull = true)]
        public string Description
        {
            get { return m_description; }
            set
            {
                Dirty = true;
                m_description = value;
            }
        }

        /// <summary>
        /// Gets or sets the translated examine article.
        /// </summary>
        [DataElement(AllowDbNull = true)]
        public string ExamineArticle
        {
            get { return m_examineArticle; }
            set
            {
                Dirty = true;
                m_examineArticle = value;
            }
        }

        /// <summary>
        /// Gets or sets the translated message article.
        /// </summary>
        [DataElement(AllowDbNull = true)]
        public string MessageArticle
        {
            get { return m_messageArticle; }
            set
            {
                Dirty = true;
                m_messageArticle = value;
            }
        }
        #endregion Properties
    }
}
