using DOL.Database;
using DOL.Events;
using DOL.Language;
using System;

namespace DOL.GS.Scripts
{
    public class BrotherDon : GameNPC
    {
        private static DbItemTemplate _wolfPeltCloak = null;
        protected const string wolfPeltCloak = "wolf_pelt_cloak";
        public BrotherDon()
        {
            _wolfPeltCloak = GameServer.Database.FindObjectByKey<DbItemTemplate>(wolfPeltCloak);
        }

        public override void Notify(DOLEvent e, object sender, EventArgs args)
        {
            if (e == GamePlayerEvent.ReceiveItem)
            {
                ReceiveItemEventArgs gArgs = (ReceiveItemEventArgs)args;
                GamePlayer player = gArgs.Source as GamePlayer;
                if(player == null)
                {
                    return;
                }

                if (gArgs.Target.Name == this.Name && gArgs.Item.Id_nb == _wolfPeltCloak.Id_nb)
                {
                    DbInventoryItem item = player.Inventory.GetFirstItemByID(wolfPeltCloak, eInventorySlot.FirstBackpack, eInventorySlot.LastBackpack);
                    if(item != null)
                    {
                        SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "Scripts.NamedMobs.BrotherDon.ThankYou"));
                        player.Inventory.RemoveItem(item);
                        SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "Scripts.NamedMobs.BrotherDon.WellDone"));
                        player.GainExperience(eXPSource.Quest, 200, true);
                        return;
                    }
                }
            }
            base.Notify(e, sender, args);
        }

        public override bool WhisperReceive(GameLiving source, string text)
        {
            if (source == null)
            {
                return false;
            }
            GamePlayer player = source as GamePlayer;
            if (player == null)
            {
                return false;
            }
            switch (text)
            {
                case "orphanage":
							case "고아원":
                    SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "Scripts.NamedMobs.BrotherDon.Orphanage"));
                    break;
                case "donation":
							case "기부":
                    SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "Scripts.NamedMobs.BrotherDon.Donation"));
                    break;
            }
            return base.WhisperReceive(source, text);
        }

        public override bool Interact(GamePlayer player)
        {
            if (player == null)
            {
                return false;
            }
            if (player.Inventory.GetFirstItemByID(wolfPeltCloak, eInventorySlot.FirstBackpack, eInventorySlot.LastBackpack) != null)
            {
                SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "Scripts.NamedMobs.BrotherDon.Interact"));
            }
            return base.Interact(player);
        }
    }
}
