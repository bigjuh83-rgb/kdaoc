/*
 * DAWN OF LIGHT - The first free open source DAoC server emulator
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 *
 */

using System;
using DOL.GS.PacketHandler;
using DOL.GS.RealmAbilities;
using DOL.Language;

namespace DOL.GS.Commands
{
	[CmdAttribute(
		"&resetability",
		ePrivLevel.GM,
		"/resetability - <self|target|group|cg|bg>")]

	public class ResetAbilityCommandHandler : AbstractCommandHandler, ICommandHandler
	{
		private static string T(GameClient client, string key, params object[] args)
			=> LanguageMgr.GetTranslation(client.Account.Language, key, args);

		private static string T(GamePlayer player, string key, params object[] args)
			=> LanguageMgr.GetTranslation(player.Client.Account.Language, key, args);

		public void OnCommand(GameClient client, string[] args)
		{
			GamePlayer target = client.Player.TargetObject as GamePlayer;
			BattleGroup bg = client.Player.TempProperties.GetProperty<BattleGroup>(BattleGroup.BATTLEGROUP_PROPERTY);
			ChatGroup cg = client.Player.TempProperties.GetProperty<ChatGroup>(ChatGroup.CHATGROUP_PROPERTY);


			if (args.Length < 2)
			{
				DisplaySyntax(client);
				return;
			}

			switch (args[1].ToLower())
			{
					#region group
				case "group":
					{
						if (target != null)
						{
							if (target.Group != null)
							{
								foreach (GamePlayer groupedplayers in client.Player.Group.GetMembersInTheGroup())
								{

									groupedplayers.ResetDisabledSkills();
									groupedplayers.Out.SendMessage(T(groupedplayers, "GMCommands.ResetAbility.TargetReset", client.Player.Name), eChatType.CT_Spell, eChatLoc.CL_ChatWindow);
								}
							}
						}
						else
							client.Player.ResetDisabledSkills();
						client.Player.Out.SendMessage(T(client, "GMCommands.ResetAbility.TargetNoGroupResetSelf"), eChatType.CT_Spell, eChatLoc.CL_ChatWindow);
						break;
					}
					#endregion

					#region chatgrp
				case "cg":
					{
						if (cg != null)
						{
							foreach (GamePlayer cgplayers in cg.Members.Keys)
							{
								cgplayers.ResetDisabledSkills();
								cgplayers.Out.SendMessage(T(cgplayers, "GMCommands.ResetAbility.TargetReset", client.Player.Name), eChatType.CT_Spell, eChatLoc.CL_ChatWindow);
							}
						}
						else
							client.Player.ResetDisabledSkills();
						client.Player.Out.SendMessage(T(client, "GMCommands.ResetAbility.TargetNoChatGroupResetSelf"), eChatType.CT_Spell, eChatLoc.CL_ChatWindow);
						break;
					}
					#endregion

					#region target
				case "target":
					{
						if (target == null)
							target = (GamePlayer)client.Player;
						target.ResetDisabledSkills();
						target.Out.SendMessage(T(target, "GMCommands.ResetAbility.SelfReset"), eChatType.CT_Spell, eChatLoc.CL_ChatWindow);
					}
					break;
					#endregion

					#region self
				case "self":
					{
						client.Player.ResetDisabledSkills();
						client.Player.Out.SendMessage(T(client, "GMCommands.ResetAbility.SelfReset"), eChatType.CT_Spell, eChatLoc.CL_ChatWindow);
					}
					break;
					#endregion

					#region battlegroup
				case "bg":
					{
						if (target != null)
						{
							if (bg != null)
							{
								foreach (GamePlayer bgplayers in bg.Members.Keys)
								{
									bgplayers.ResetDisabledSkills();
									bgplayers.Out.SendMessage(T(bgplayers, "GMCommands.ResetAbility.TargetReset", client.Player.Name), eChatType.CT_Spell, eChatLoc.CL_ChatWindow);
								}
							}
						}
						else
							client.Player.ResetDisabledSkills();
						client.Player.Out.SendMessage(T(client, "GMCommands.ResetAbility.TargetNoBattleGroupResetSelf"), eChatType.CT_Spell, eChatLoc.CL_ChatWindow);
						break;
					}
					#endregion
				default:
					{
						client.Out.SendMessage(T(client, "GMCommands.ResetAbility.InvalidArgument", args[1]), eChatType.CT_Important, eChatLoc.CL_SystemWindow);
					}
					break;
			}
		}
	}
}
