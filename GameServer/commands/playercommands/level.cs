using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Commands
{
    [CmdAttribute("&level",
    ePrivLevel.Player,
    "Allows you to level 20 instantly if you have a level 50", "/level")]
    public class LevelCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (ServerProperties.Properties.SLASH_LEVEL_TARGET <= 1)
            {
                DisplayMessage(client, T(client, "Scripts.Players.Level.Disabled"));
                return;
            }

            if (client.Player.TargetObject is not GameTrainer)
            {
                client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Level.TrainerRequired"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            if (!ServerProperties.Properties.ALLOW_CATA_SLASH_LEVEL)
            {
                switch ((eCharacterClass) client.Player.CharacterClass.ID)
                {
                    case eCharacterClass.Heretic:
                    case eCharacterClass.Valkyrie:
                    case eCharacterClass.Warlock:
                    case eCharacterClass.Vampiir:
                    case eCharacterClass.Bainshee:
                    case eCharacterClass.MaulerAlb:
                    case eCharacterClass.MaulerHib:
                    case eCharacterClass.MaulerMid:
                    {
                        client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Level.ClassCannotUse"), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                        return;
                    }
                }
            }
            if (!client.Player.CanUseSlashLevel)
            {
                client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Level.RequirementMissing", ServerProperties.Properties.SLASH_LEVEL_REQUIREMENT), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            if (client.Player.Experience >= client.Player.GetExperienceNeededForLevel(ServerProperties.Properties.SLASH_LEVEL_TARGET - 1))
            {
                client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Level.TargetOnly", ServerProperties.Properties.SLASH_LEVEL_TARGET), eChatType.CT_System, eChatLoc.CL_SystemWindow);
                return;
            }

            int targetLevel = ServerProperties.Properties.SLASH_LEVEL_TARGET;

            if (targetLevel is < 1 or > 50)
                targetLevel = 20;

            long newXP = client.Player.GetExperienceNeededForLevel(targetLevel - 1) - client.Player.Experience;

            if (newXP < 0)
                newXP = 0;

            client.Player.GainExperience(eXPSource.Other, newXP);
            client.Player.UsedLevelCommand = true;
            client.Player.Out.SendMessage(LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Level.Rewarded", ServerProperties.Properties.SLASH_LEVEL_TARGET), eChatType.CT_System, eChatLoc.CL_SystemWindow);
            client.Player.SaveIntoDatabase();
        }
    }
}
