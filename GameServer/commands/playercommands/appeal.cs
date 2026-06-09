using DOL.Database;
using DOL.GS.Appeal;
using DOL.Language;

namespace DOL.GS.Commands
{
    //The appeal command is really just a tool to redirect the players concerns to the proper command.
    //most of it's functionality is built into the client.
    [CmdAttribute(
        "&appeal",
        ePrivLevel.Player,
        "사용법: '/appeal <신고 유형> <신고 내용>",
        "<신고 유형>은 다음 중 하나입니다:",
        "  harassment(괴롭힘), naming(이름), conduct(행동), stuck(고립), emergency(긴급), other(기타)",
        "<신고 내용>에는 문제를 자세히 적어 주세요.",
        "이미 신고를 접수했다면",
        "'/checkappeal'로 상태를 확인할 수 있습니다.")]
    public class AppealCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
			if (IsSpammingCommand(client.Player, "appeal"))
				return;

			if (ServerProperties.Properties.DISABLE_APPEALSYSTEM)
            {
                AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.SystemDisabled"));
                return;
            }

			if (client.Player.IsMuted)
			{
				return;
			}

            //Help display
            if (args.Length == 1)
            {
                DisplaySyntax(client);
                if (client.Account.PrivLevel > (uint)ePrivLevel.Player)
                {
                    AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.UseGMappeal"));
                }
            }

            //Support for EU Clients

            if (args.Length == 2 && args[1].ToLower() == "cancel")
            {
                CheckAppealCommandHandler cch = new CheckAppealCommandHandler();
                cch.OnCommand(client, args);
                return;
            }

            if (args.Length > 1)
            {
                DbAppeal appeal = AppealMgr.GetAppeal(client.Player);
                if (appeal != null)
                {
                    AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.AlreadyActiveAppeal", client.Player.Name));
                    return;
                }
                if (args.Length < 5)
                {
                    AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.NeedMoreDetail"));
                    return;
                }
                int severity = 0;
                switch (args[1].ToLower())
                {
                    case "harassment":
                        {
                            severity = (int)AppealMgr.Severity.High;
                            args[1] = string.Empty;
                            break;
                        }
                    case "naming":
                        {
                            severity = (int)AppealMgr.Severity.Low;
                            args[1] = string.Empty;
                            break;
                        }
                    case "other":
                    case "conduct":
                        {
                            severity = (int)AppealMgr.Severity.Medium;
                            args[1] = string.Empty;
                            break;
                        }
                    case "stuck":
                    case "emergency":
                        {
                            severity = (int)AppealMgr.Severity.Critical;
                            args[1] = string.Empty;
                            break;
                        }
                    default:
                        {
                            severity = (int)AppealMgr.Severity.Medium;
                            break;
                        }

                }
                string message = string.Join(" ", args, 1, args.Length - 1);
                GamePlayer p = client.Player as GamePlayer;
                AppealMgr.CreateAppeal(p, severity, "Open", message);
                return;
            }
            return;
        }
    }

    #region reportbug
    //handles /reportbug command that is issued from the client /appeal function.
    [CmdAttribute(
    "&reportbug",
    ePrivLevel.Player, "신고를 접수하려면 /appeal을 사용하세요.")]
    public class ReportBugCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (ServerProperties.Properties.DISABLE_APPEALSYSTEM)
            {
                AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.SystemDisabled"));
                return;
            }

            if (args.Length < 5)
            {
                AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.NeedMoreDetail"));
                return;
            }

            //send over the info to the /report command
            args[1] = string.Empty;
            //strip these words if they are the first word in the bugreport text
            switch (args[2].ToLower())
            {
                case "harassment":
                case "naming":
                case "other":
                case "conduct":
                case "stuck":
                case "emergency":
                    {
                        args[2] = string.Empty;
                        break;
                    }
            }
            ReportCommandHandler report = new ReportCommandHandler();
            report.OnCommand(client, args);
            AppealMgr.MessageToAllStaff(client.Player.Name + " submitted a bug report.");
            return;
        }
    }
    #endregion reportbug
    #region reportharass
    //handles /reportharass command that is issued from the client /appeal function.
    [CmdAttribute(
    "&reportharass",
    ePrivLevel.Player, "신고를 접수하려면 /appeal을 사용하세요.")]
    public class ReportHarassCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (ServerProperties.Properties.DISABLE_APPEALSYSTEM)
            {
                AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.SystemDisabled"));
                return;
            }
            DbAppeal appeal = AppealMgr.GetAppeal(client.Player);
            if (appeal != null)
            {
                AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.AlreadyActiveAppeal", client.Player.Name));
                return;
            }
            if (args.Length < 7)
            {
                AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.NeedMoreDetail"));
                return;
            }
            //strip these words if they are the first word in the appeal text
            switch (args[1].ToLower())
            {
                case "harassment":
                case "naming":
                case "other":
                case "conduct":
                case "stuck":
                case "emergency":
                    {
                        args[1] = string.Empty;
                        break;
                    }
            }
            string message = string.Join(" ", args, 1, args.Length - 1);
            GamePlayer p = client.Player as GamePlayer;
            AppealMgr.CreateAppeal(p, (int)AppealMgr.Severity.High, "Open", message);
            return;
        }
    }
    #endregion reportharass
    #region reporttos
    //handles /reporttos command that is issued from the client /appeal function.
    [CmdAttribute(
    "&reporttos",
    ePrivLevel.Player, "신고를 접수하려면 /appeal을 사용하세요.")]
    public class ReportTosCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (ServerProperties.Properties.DISABLE_APPEALSYSTEM)
            {
                AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.SystemDisabled"));
                return;
            }
            DbAppeal appeal = AppealMgr.GetAppeal(client.Player);
            if (appeal != null)
            {
                AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.AlreadyActiveAppeal", client.Player.Name));
                return;
            }
            if (args.Length < 7)
            {
                AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.NeedMoreDetail"));
                return;
            }
            switch (args[1])
            {
                case "NAME":
                    {
                        //strip these words if they are the first word in the appeal text
                        switch (args[2].ToLower())
                        {
                            case "harassment":
                            case "naming":
                            case "other":
                            case "conduct":
                            case "stuck":
                            case "emergency":
                                {
                                    args[2] = string.Empty;
                                    break;
                                }
                        }
                        string message = string.Join(" ", args, 2, args.Length - 2);
                        GamePlayer p = client.Player as GamePlayer;
                        AppealMgr.CreateAppeal(p, (int)AppealMgr.Severity.Low, "Open", message);
                        break;
                    }
                case "TOS":
                    {
                        //strip these words if they are the first word in the appeal text
                        switch (args[2].ToLower())
                        {
                            case "harassment":
                            case "naming":
                            case "other":
                            case "conduct":
                            case "stuck":
                            case "emergency":
                                {
                                    args[2] = string.Empty;
                                    break;
                                }
                        }
                        string message = string.Join(" ", args, 2, args.Length - 2);
                        GamePlayer p = client.Player as GamePlayer;
                        AppealMgr.CreateAppeal(p, (int)AppealMgr.Severity.Medium, "Open", message);
                        break;
                    }
            }
            return;
        }
    }
    #endregion reporttos
    #region reportstuck
    //handles /reportharass command that is issued from the client /appeal function.
    [CmdAttribute(
    "&reportstuck",
    ePrivLevel.Player, "신고를 접수하려면 /appeal을 사용하세요.")]
    public class ReportStuckCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (ServerProperties.Properties.DISABLE_APPEALSYSTEM)
            {
                AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.SystemDisabled"));
                return;
            }
            DbAppeal appeal = AppealMgr.GetAppeal(client.Player);
            if (appeal != null)
            {
                AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.AlreadyActiveAppeal", client.Player.Name));
                return;
            }
            if (args.Length < 5)
            {
                AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.NeedMoreDetail"));
                return;
            }
            //strip these words if they are the first word in the appeal text
            switch (args[1].ToLower())
            {
                case "harassment":
                case "naming":
                case "other":
                case "conduct":
                case "stuck":
                case "emergency":
                    {
                        args[1] = string.Empty;
                        break;
                    }
            }
            string message = string.Join(" ", args, 1, args.Length - 1);
            GamePlayer p = client.Player as GamePlayer;
            AppealMgr.CreateAppeal(p, (int)AppealMgr.Severity.Critical, "Open", message);
            return;
        }
    }
    #endregion reportstuck
    #region emergency
    //handles /appea command that is issued from the client /appeal function (emergency appeal).
    [CmdAttribute(
    "&appea",
    ePrivLevel.Player, "신고를 접수하려면 /appeal을 사용하세요.")]
    public class EmergencyAppealCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (ServerProperties.Properties.DISABLE_APPEALSYSTEM)
            {
                AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.SystemDisabled"));
                return;
            }
            DbAppeal appeal = AppealMgr.GetAppeal(client.Player);
            if (appeal != null)
            {
                AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.AlreadyActiveAppeal", client.Player.Name));
                return;
            }
            if (args.Length < 5)
            {
                AppealMgr.MessageToClient(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Appeal.NeedMoreDetail"));
                return;
            }
            //strip these words if they are the first word in the appeal text
            switch (args[1].ToLower())
            {
                case "harassment":
                case "naming":
                case "other":
                case "conduct":
                case "stuck":
                case "emergency":
                    {
                        args[1] = string.Empty;
                        break;
                    }
            }
            string message = string.Join(" ", args, 1, args.Length - 1);
            GamePlayer p = client.Player as GamePlayer;
            AppealMgr.CreateAppeal(p, (int)AppealMgr.Severity.Critical, "Open", message);
            return;
        }
    }
    #endregion emergency
}
