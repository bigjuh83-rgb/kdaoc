using System;
using DOL.Database.Attributes;

namespace DOL.Database
{
    [DataTable(TableName = "player_mercenary")]
    public class DbPlayerMercenary : DataObject
    {
        private string m_mercenaryId = string.Empty;
        private string m_ownerCharacterId = string.Empty;
        private string m_ownerAccountName = string.Empty;
        private string m_ownerCharacterName = string.Empty;
        private string m_displayName = string.Empty;
        private string m_background = string.Empty;
        private string m_personality = string.Empty;
        private int m_classId;
        private string m_className = string.Empty;
        private int m_realm;
        private string m_role = string.Empty;
        private string m_capabilities = string.Empty;
        private string m_contractTier = string.Empty;
        private string m_traits = string.Empty;
        private string m_itemProfile = string.Empty;
        private string m_tacticPreset = "balanced";
        private int m_trust = 50;
        private int m_fatigue;
        private string m_adventureMemory = string.Empty;
        private string m_rumorHint = string.Empty;
        private int m_totalContracts;
        private DateTime m_lastHiredAt = DateTime.UtcNow;
        private string m_sourceId = string.Empty;
        private DateTime m_createdAt = DateTime.UtcNow;
        private DateTime m_updatedAt = DateTime.UtcNow;

        [PrimaryKey]
        public string MercenaryId
        {
            get { return m_mercenaryId; }
            set { Dirty = true; m_mercenaryId = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 64, Index = true)]
        public string OwnerCharacterId
        {
            get { return m_ownerCharacterId; }
            set { Dirty = true; m_ownerCharacterId = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 64, Index = true)]
        public string OwnerAccountName
        {
            get { return m_ownerAccountName; }
            set { Dirty = true; m_ownerAccountName = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 64)]
        public string OwnerCharacterName
        {
            get { return m_ownerCharacterName; }
            set { Dirty = true; m_ownerCharacterName = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 64, Index = true)]
        public string DisplayName
        {
            get { return m_displayName; }
            set { Dirty = true; m_displayName = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 255)]
        public string Background
        {
            get { return m_background; }
            set { Dirty = true; m_background = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 64)]
        public string Personality
        {
            get { return m_personality; }
            set { Dirty = true; m_personality = value; }
        }

        [DataElement(AllowDbNull = false)]
        public int ClassId
        {
            get { return m_classId; }
            set { Dirty = true; m_classId = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 64, Index = true)]
        public string ClassName
        {
            get { return m_className; }
            set { Dirty = true; m_className = value; }
        }

        [DataElement(AllowDbNull = false, Index = true)]
        public int Realm
        {
            get { return m_realm; }
            set { Dirty = true; m_realm = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 32, Index = true)]
        public string Role
        {
            get { return m_role; }
            set { Dirty = true; m_role = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 255)]
        public string Capabilities
        {
            get { return m_capabilities; }
            set { Dirty = true; m_capabilities = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 32, Index = true)]
        public string ContractTier
        {
            get { return m_contractTier; }
            set { Dirty = true; m_contractTier = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 255)]
        public string Traits
        {
            get { return m_traits; }
            set { Dirty = true; m_traits = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 255)]
        public string ItemProfile
        {
            get { return m_itemProfile; }
            set { Dirty = true; m_itemProfile = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 32, Index = true)]
        public string TacticPreset
        {
            get { return m_tacticPreset; }
            set { Dirty = true; m_tacticPreset = value; }
        }

        [DataElement(AllowDbNull = false)]
        public int Trust
        {
            get { return m_trust; }
            set { Dirty = true; m_trust = value; }
        }

        [DataElement(AllowDbNull = false)]
        public int Fatigue
        {
            get { return m_fatigue; }
            set { Dirty = true; m_fatigue = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 255)]
        public string AdventureMemory
        {
            get { return m_adventureMemory; }
            set { Dirty = true; m_adventureMemory = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 255)]
        public string RumorHint
        {
            get { return m_rumorHint; }
            set { Dirty = true; m_rumorHint = value; }
        }

        [DataElement(AllowDbNull = false)]
        public int TotalContracts
        {
            get { return m_totalContracts; }
            set { Dirty = true; m_totalContracts = value; }
        }

        [DataElement(AllowDbNull = false)]
        public DateTime LastHiredAt
        {
            get { return m_lastHiredAt; }
            set { Dirty = true; m_lastHiredAt = value; }
        }

        [DataElement(AllowDbNull = false, Varchar = 96, Index = true)]
        public string SourceId
        {
            get { return m_sourceId; }
            set { Dirty = true; m_sourceId = value; }
        }

        [DataElement(AllowDbNull = false)]
        public DateTime CreatedAt
        {
            get { return m_createdAt; }
            set { Dirty = true; m_createdAt = value; }
        }

        [DataElement(AllowDbNull = false)]
        public DateTime UpdatedAt
        {
            get { return m_updatedAt; }
            set { Dirty = true; m_updatedAt = value; }
        }
    }
}
