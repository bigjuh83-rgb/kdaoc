using DOL.GS.PacketHandler;
using DOL.GS.Keeps;
using DOL.Language;

namespace DOL.GS.Commands
{
    [CmdAttribute(
        "&transfercorpse",
        new string[] {"&tc"},
        ePrivLevel.Player, // Set to player.
        "/transfercorpse <Keep name> ie: /transfercorpse dun crauchon")]
    public class transfercorpseCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (!ServerProperties.Properties.ENABLE_CORPSESUMONNER)
            {
                client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client, "Scripts.Players.TransferCorpse.Disabled"), eChatType.CT_System,
                    eChatLoc.CL_ChatWindow);
                return;
            }

            if (IsSpammingCommand(client.Player, "transfercorpse"))
                return;
            if (args.Length < 3)
            {
                DisplaySyntax(client);
                return;
            }

            string keepname = string.Empty;
            if (args.Length == 3)
            {
                keepname = args[1] + " " + args[2];
            }
            else if (args.Length == 4)
            {
                keepname = args[1] + " " + args[2] + " " + args[3];
            }
            else
            {
                DisplaySyntax(client);
                return;
            }

            if (client.Player.IsAlive)
            {
                client.Player.Out.SendMessage(
                    LanguageMgr.GetTranslation(client, "Scripts.Players.TransferCorpse.MustBeDeadSameRegion"),
                    eChatType.CT_System, eChatLoc.CL_ChatWindow);
                return;
            }

            if (!client.Player.CurrentZone.IsOF)
            {
                client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client, "Scripts.Players.TransferCorpse.MustBeInFrontiers"), eChatType.CT_System,
                    eChatLoc.CL_ChatWindow);
                return;
            }

            if (!client.Player.LastDeathPvP)
            {
                client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client, "Scripts.Players.TransferCorpse.MustBeRealmDeath"),
                    eChatType.CT_System, eChatLoc.CL_ChatWindow);
                return;
            }

            if (client.Player.WasMovedByCorpseSummoner)
            {
                client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client, "Scripts.Players.TransferCorpse.OncePerDeath"),
                    eChatType.CT_System, eChatLoc.CL_ChatWindow);
                return;
            }

            AbstractGameKeep keep = GameServer.KeepManager.GetKeepByShortName(keepname);

            if (keep == null)
            {
                client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client, "Scripts.Players.TransferCorpse.ValidKeepName"), eChatType.CT_System,
                    eChatLoc.CL_ChatWindow);
                return;
            }

            if (keep.Realm != client.Player.Realm)
            {
                client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client, "Scripts.Players.TransferCorpse.RealmMustOwnKeep"),
                    eChatType.CT_System, eChatLoc.CL_ChatWindow);
                return;
            }

            foreach (GameKeepGuard guard in keep.Guards.Values)
            {
                if (guard is GuardCorpseSummoner)
                {
                    if (guard.CurrentZone != null && guard.CurrentZone.ID == client.Player.CurrentZone.ID)
                    {
                        if (!guard.IsAlive || guard.ObjectState != GameObject.eObjectState.Active || guard.IsRespawning)
                        {
                            client.Player.Out.SendMessage(
                                LanguageMgr.GetTranslation(client, "Scripts.Players.TransferCorpse.SummonerInactive"), eChatType.CT_System,
                                eChatLoc.CL_ChatWindow);
                            break;
                        }
                        else
                        {
                            Point3D targetPoint;
                            targetPoint = new Point3D(guard.GetPointFromHeading((ushort) Util.Random(4096), 50),
                                guard.Z);
                            client.Player.WasMovedByCorpseSummoner = true;
                            client.Player.MoveTo(guard.CurrentRegionID, targetPoint.X, targetPoint.Y, targetPoint.Z,
                                client.Player.Heading);
                            break;
                        }
                    }
                    else
                    {
                        client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client, "Scripts.Players.TransferCorpse.SameZoneRequired"),
                            eChatType.CT_System, eChatLoc.CL_ChatWindow);
                        break;
                    }
                }
            }
        }
    }
}
