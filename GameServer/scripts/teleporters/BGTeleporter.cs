using System;
using DOL.GS;
using DOL.Events;
using DOL.GS.PacketHandler;
using System.Reflection;
using DOL.Language;

namespace DOL.GS.Scripts
{
    public class BGTeleporter : GameNPC
	{
		private static new readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);

        public override bool AddToWorld()
        {
            Model = 2026;
            Name = "BG TELEPORTER";
            Level = 50;
            Size = 60;
            Flags |= GameNPC.eFlags.PEACE;
            return base.AddToWorld();
        }
		public override bool Interact(GamePlayer player)
		{
			if (!base.Interact(player)) return false;
			TurnTo(player.X, player.Y);
			player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "BGTeleporter.Interact.Menu", player.Name), eChatType.CT_Say,eChatLoc.CL_PopupWindow);
			return true;
		}

        private static void SendCannotPortInCombat(GamePlayer player)
        {
            player.Client.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "CustomTeleporter.CannotPortInCombat"), eChatType.CT_Say, eChatLoc.CL_PopupWindow);
        }
		public override bool WhisperReceive(GameLiving source, string str)
		{
			if(!base.WhisperReceive(source,str)) return false;
			if(!(source is GamePlayer)) return false;
			GamePlayer t = (GamePlayer) source;
			TurnTo(t.X,t.Y);
			switch(str)
			{
				//alb
                case "AbermenaiAlb":
                    if (!t.InCombat)
                    {
	                    t.MoveTo(253, 38113, 53507, 4160, 3268);
                    }
                    else { SendCannotPortInCombat(t); }
                    break;

                case "ThidrankiAlb":
	                if (!t.InCombat)
	                {
		                t.MoveTo(252, 38113, 53507, 4160, 3268);
	                }
	                else { SendCannotPortInCombat(t); }
	                break;

                case "MurdaigeanAlb":
	                if (!t.InCombat)
	                {
		                t.MoveTo(251, 38113, 53507, 4160, 3268);
	                }
	                else { SendCannotPortInCombat(t); }
	                break;

                case "CaledoniaAlb":
	                if (!t.InCombat)
	                {
		                t.MoveTo(250, 38113, 53507, 4160, 3268);
	                }
	                else { SendCannotPortInCombat(t); }
	                break;
                //mid
                case "AbermenaiMid":
	                if (!t.InCombat)
	                {
		                t.MoveTo(253, 53568, 23643, 4530, 3268);
	                }
	                else { SendCannotPortInCombat(t); }
	                break;

                case "ThidrankiMid":
	                if (!t.InCombat)
	                {
		                t.MoveTo(252, 53568, 23643, 4530, 3268);
	                }
	                else { SendCannotPortInCombat(t); }
	                break;

                case "MurdaigeanMid":
	                if (!t.InCombat)
	                {
		                t.MoveTo(251, 53568, 23643, 4530, 3268);
	                }
	                else { SendCannotPortInCombat(t); }
	                break;

                case "CaledoniaMid":
	                if (!t.InCombat)
	                {
		                t.MoveTo(250, 53568, 23643, 4530, 3268);
	                }
	                else { SendCannotPortInCombat(t); }
	                break;
                //hib
				case "AbermenaiHib":
					if (!t.InCombat)
					{
						t.MoveTo(253, 17367, 18248, 4320, 3268);
					}
					else { SendCannotPortInCombat(t); }
					break;

				case "ThidrankiHib":
					if (!t.InCombat)
					{
						t.MoveTo(252, 17367, 18248, 4320, 3268);
					}
					else { SendCannotPortInCombat(t); }
					break;

				case "MurdaigeanHib":
					if (!t.InCombat)
					{
						t.MoveTo(251, 17367, 18248, 4320, 3268);
					}
					else { SendCannotPortInCombat(t); }
					break;

				case "CaledoniaHib":
					if (!t.InCombat)
					{
						t.MoveTo(250, 17367, 18248, 4320, 3268);
					}
					else { SendCannotPortInCombat(t); }
					break;

                default: break;
			}
			return true;
		}
		private void SendReply(GamePlayer target, string msg)
			{
				target.Client.Out.SendMessage(
					msg,
					eChatType.CT_Say,eChatLoc.CL_PopupWindow);
			}
		[ScriptLoadedEvent]
        public static void OnScriptCompiled(DOLEvent e, object sender, EventArgs args)
        {
            log.Info("BG Teleporter initialized: true");
        }
    }
}
