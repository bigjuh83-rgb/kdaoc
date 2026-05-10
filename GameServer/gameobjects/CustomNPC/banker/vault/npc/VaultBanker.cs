using DOL.GS.Housing;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS
{
    public abstract class VaultBanker : GameNPC
    {
        protected virtual int Index => -1; // Legacy single-vault bankers override these. Unified banker defaults to -1.
        protected virtual VaultType Type => VaultType.Personal;

        public override bool Interact(GamePlayer player)
        {
            if (!base.Interact(player))
                return false;

            // Execute default behavior only for legacy single-index bankers.
            if (Index >= 0)
            {
                player.Out.SendMessage(BuildInteractionMessage(player, Type, Index), eChatType.CT_Say, eChatLoc.CL_PopupWindow);

                if (TryGetHouseVault(player, Type, Index, out GameHouseVault houseVault))
                    houseVault.Interact(player);
            }

            return true;
        }

        protected static string BuildInteractionMessage(GamePlayer player, VaultType type, int index)
        {
            if (type is VaultType.Personal)
                return LanguageMgr.GetTranslation(player.Client.Account.Language, "Banker.Vault.LegacyPersonalGreeting", player.Name, index + 1);

            else if (type is VaultType.Guild)
                return LanguageMgr.GetTranslation(player.Client.Account.Language, "Banker.Vault.LegacyGuildGreeting", player.Name, index + 1);

            return LanguageMgr.GetTranslation(player.Client.Account.Language, "Banker.Vault.GenericGreeting", player.Name);
        }

        protected static bool TryGetHouseVault(GamePlayer player, VaultType vaultType, int index, out GameHouseVault vault)
        {
            vault = null;

            if (TryGetRealHouseVault(player, vaultType, index, out _))
                return false;

            if (vaultType is VaultType.Personal)
            {
                if (player.ActiveInventoryObject is PersonalRecoveredHouseVault cachedVault && cachedVault.Index == index)
                {
                    vault = cachedVault;
                    return true;
                }

                vault = new PersonalRecoveredHouseVault(player, AccountVaultKeeper.GetDummyVaultItem(player), index)
                {
                    CurrentHouse = new NullHouse(player.ObjectId, false)
                };

                return true;
            }

            if (vaultType is VaultType.Guild)
            {
                if (player.ActiveInventoryObject is GuildRecoveredHouseVault cachedVault && cachedVault.Index == index)
                {
                    vault = cachedVault;
                    return true;
                }

                Guild guild = player.Guild;

                if (guild == null)
                    return false;

                vault = new GuildRecoveredHouseVault(player, AccountVaultKeeper.GetDummyVaultItem(player), index)
                {
                    CurrentHouse = new NullHouse(guild.GuildID, true)
                };

                return true;
            }

            return false;
        }

        private static bool TryGetRealHouseVault(GamePlayer player, VaultType type, int index, out GameHouseVault vault)
        {
            vault = null;
            House house = null;

            if (type is VaultType.Personal)
                house = HouseMgr.GetHouseByCharacterIds([player.ObjectId]);
            else if (type is VaultType.Guild)
                house = HouseMgr.GetGuildHouseByPlayer(player);

            return house != null && house.HouseVaults.TryGetValue(index, out vault);
        }

    }
}
