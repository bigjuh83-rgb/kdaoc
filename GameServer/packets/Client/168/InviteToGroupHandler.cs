using DOL.Language;

namespace DOL.GS.PacketHandler.Client.v168
{
    [PacketHandlerAttribute(PacketHandlerType.TCP, eClientPackets.InviteToGroup, "Handle Invite to Group Request.", eClientStatus.PlayerInGame)]
    public class InviteToGroupHandler : PacketHandler
    {
        protected override void HandlePacketInternal(GameClient client, GSPacketIn packet)
        {
            GamePlayer player = client.Player;

            if (player.TargetObject == null || player.TargetObject == player)
            {
                ChatUtil.SendSystemMessage(player, "Group.Invite.NoValidTarget", null);
                return;
            }

            if (player.TargetObject is not GamePlayer target)
            {
                ChatUtil.SendSystemMessage(player, "Group.Invite.NoValidTarget", null);
                return;
            }

            if (player.Group != null && player.Group.Leader != player)
            {
                ChatUtil.SendSystemMessage(player, "Group.Invite.NotLeader", null);
                return;
            }

            if (player.Group != null && player.Group.MemberCount >= ServerProperties.Properties.GROUP_MAX_MEMBER)
            {
                ChatUtil.SendSystemMessage(player, "Dialog.Group.Full", null);
                return;
            }

            if (!GameServer.ServerRules.IsAllowedToGroup(player, target, false))
                return;

            if (target.Group != null)
            {
                ChatUtil.SendSystemMessage(player, "Group.Invite.TargetInGroup", null);
                return;
            }

            ChatUtil.SendSystemMessage(player, "Group.Invite.Sent", target.Name);
            target.Out.SendGroupInviteCommand(player, LanguageMgr.GetTranslation(target.Client.Account.Language, "Group.Invite.Popup", player.Name, player.GetPronoun(1, false)));
            ChatUtil.SendSystemMessage(target, "Group.Invite.Received", player.Name, player.GetPronoun(1, false));
        }
    }
}
