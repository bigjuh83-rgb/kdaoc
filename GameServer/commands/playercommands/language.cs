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
using System.Linq;

using DOL.Database;
using DOL.Language;

namespace DOL.GS.Commands
{
    [Cmd("&language", ePrivLevel.Player, "Change your language.",
        "Use '/language current' to see your current used language.",
        "Use '/language set [language]' to set your language.",
        "Use '/language show' to show all available languages and to see your current used language."
    )]
    public class LanguageCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (IsSpammingCommand(client.Player, "language"))
                return;

            if (client.Account.PrivLevel == (uint)ePrivLevel.Player && !DOL.GS.ServerProperties.Properties.ALLOW_CHANGE_LANGUAGE)
            {
                DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Language.Disabled"));
                return;
            }

            if (args.Length < 2)
            {
                DisplayLanguageSyntax(client);
                return;
            }

            switch (args[1].ToLower())
            {
                #region current
                case "current":
                    {
                        DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Language.Current"), client.Account.Language);
                        return;
                    }
                #endregion current

                #region set
                case "set":
                    {
                        if (args.Length < 3)
                        {
                            DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Language.SyntaxSet"));
                            return;
                        }

                        string language = args[2].ToUpper();
                        if (!LanguageMgr.Languages.Contains(language))
                        {
                            DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Language.LanguageNotSupported", language));
                            return;
                        }

                        client.Account.Language = language;
                        GameServer.Database.SaveObject(client.Account);
                        DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Language.Set", language));
                        return;
                    }
                #endregion set

                #region show
                case "show":
                    {
                        string languages = string.Empty;
                        foreach (string language in LanguageMgr.Languages)
                        {
                            if (client.Account.Language == language)
                                languages += ("*" + language + ","); // The * marks a language as the players current used language
                            else
                                languages += (language + ",");
                        }

                        if (languages.EndsWith(","))
                            languages = languages.Substring(0, languages.Length - 1);

                        DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Language.AvailableLanguages", languages));
                        return;
                    }
                #endregion show

                default:
                    {
                        DisplayLanguageSyntax(client);
                        return;
                    }
            }
        }

        private void DisplayLanguageSyntax(GameClient client)
        {
            DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Language.SyntaxCurrent"));
            DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Language.SyntaxSet"));
            DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Language.SyntaxShow"));
        }
    }
}
