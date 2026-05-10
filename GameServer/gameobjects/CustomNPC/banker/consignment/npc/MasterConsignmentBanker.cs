using System;
using DOL.Database;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS
{
    public class MasterConsignmentBanker : ConsignmentBanker
    {
        public override void LoadFromDatabase(DataObject obj)
        {
            base.LoadFromDatabase(obj);
            GuildName = "Master Consignment Banker";
        }

        public override bool Interact(GamePlayer player)
        {
            if (!base.Interact(player))
                return false;

            string language = player.Client.Account.Language;
            string msg =
                LanguageMgr.GetTranslation(language, "Banker.Consignment.MasterGreeting", player.Name) +
                $"\n\n[{LanguageMgr.GetTranslation(language, "Banker.Consignment.PersonalLink")}]\n" +
                $"[{LanguageMgr.GetTranslation(language, "Banker.Consignment.GuildLink")}]\n";

            player.Out.SendMessage(msg, eChatType.CT_Say, eChatLoc.CL_PopupWindow);
            return true;
        }

        public override bool WhisperReceive(GameLiving source, string text)
        {
            if (!base.WhisperReceive(source, text))
                return false;

            if (source is not GamePlayer player)
                return false;

            if (text.Equals("personal consignment", StringComparison.OrdinalIgnoreCase) ||
                text.Equals("개인 위탁상인", StringComparison.OrdinalIgnoreCase))
            {
                OpenConsignment(player, VaultType.Personal);
                return true;
            }

            if (text.Equals("guild consignment", StringComparison.OrdinalIgnoreCase) ||
                text.Equals("길드 위탁상인", StringComparison.OrdinalIgnoreCase))
            {
                OpenConsignment(player, VaultType.Guild);
                return true;
            }

            return false;
        }

        private void OpenConsignment(GamePlayer player, VaultType type)
        {
            if (!TryGetConsignmentMerchant(player, type, out GameConsignmentMerchant consignmentMerchant))
            {
                player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "Banker.Consignment.CannotAccess"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
                return;
            }

            consignmentMerchant.Interact(player);
        }
    }
}
