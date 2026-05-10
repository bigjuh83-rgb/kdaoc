using System;
using DOL.Database;
using DOL.GS.Housing;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS
{
    public class MasterVaultBanker : VaultBanker
    {
        public override void LoadFromDatabase(DataObject obj)
        {
            base.LoadFromDatabase(obj);
            GuildName = "Master Vault Banker";
        }

        public override bool Interact(GamePlayer player)
        {
            if (!base.Interact(player))
                return false;

            string language = player.Client.Account.Language;
            string msg = LanguageMgr.GetTranslation(language, "Banker.Vault.MasterGreeting", player.Name);

            foreach (VaultType vaultType in Enum.GetValues<VaultType>())
            {
                msg += "\n";

                for (int i = 1; i <= House.MAX_VAULT_COUNT; i++)
                {
                    string key = vaultType is VaultType.Personal ? "Banker.Vault.PersonalLink" : "Banker.Vault.GuildLink";
                    msg += $"[{LanguageMgr.GetTranslation(language, key, i)}]\n";
                }
            }

            player.Out.SendMessage(msg, eChatType.CT_Say, eChatLoc.CL_PopupWindow);
            return true;
        }

        public override bool WhisperReceive(GameLiving source, string text)
        {
            if (!base.WhisperReceive(source, text))
                return false;

            if (source is not GamePlayer player)
                return false;

            if (TryParseVaultSelection(text, "personal vault ", "개인 금고 ", out int personalVaultIndex))
            {
                OpenVault(player, VaultType.Personal, personalVaultIndex - 1);

                return true;
            }

            if (TryParseVaultSelection(text, "guild vault ", "길드 금고 ", out int guildVaultIndex))
            {
                OpenVault(player, VaultType.Guild, guildVaultIndex - 1);

                return true;
            }

            return false;
        }

        private static bool TryParseVaultSelection(string text, string englishPrefix, string koreanPrefix, out int vaultIndex)
        {
            vaultIndex = 0;

            if (text.StartsWith(englishPrefix, StringComparison.OrdinalIgnoreCase))
                return int.TryParse(text.AsSpan(englishPrefix.Length), out vaultIndex) && vaultIndex >= 1 && vaultIndex <= House.MAX_VAULT_COUNT;

            if (text.StartsWith(koreanPrefix, StringComparison.OrdinalIgnoreCase))
                return int.TryParse(text.AsSpan(koreanPrefix.Length), out vaultIndex) && vaultIndex >= 1 && vaultIndex <= House.MAX_VAULT_COUNT;

            return false;
        }

        private static void OpenVault(GamePlayer player, VaultType type, int index)
        {
            if (!TryGetHouseVault(player, type, index, out GameHouseVault houseVault))
            {
                player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "Banker.Vault.CannotAccess"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
                return;
            }

            houseVault.Interact(player);
        }
    }
}
