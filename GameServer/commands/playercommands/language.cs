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
    [Cmd("&language", ePrivLevel.Player, "사용 언어를 변경합니다.",
        "'/language 현재'는 현재 사용 중인 언어를 표시합니다.",
        "'/language 설정 [언어]'는 사용할 언어를 설정합니다.",
        "'/language 보기'는 사용 가능한 모든 언어와 현재 언어를 표시합니다."
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

            string directLanguage = NormalizeLanguageCode(args[1]);
            if (LanguageMgr.Languages.Contains(directLanguage))
            {
                SetLanguage(client, directLanguage);
                return;
            }

            switch (NormalizeLanguageCommand(args[1]))
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

                        string language = NormalizeLanguageCode(args[2]);
                        if (!LanguageMgr.Languages.Contains(language))
                        {
                            DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Language.LanguageNotSupported", language));
                            return;
                        }

                        SetLanguage(client, language);
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

        private void SetLanguage(GameClient client, string language)
        {
            client.Account.Language = language;
            GameServer.Database.SaveObject(client.Account);
            DisplayMessage(client, LanguageMgr.GetTranslation(client.Account.Language, "Scripts.Players.Language.Set", language));
        }

        private static string NormalizeLanguageCommand(string command)
        {
            return command?.Trim().ToLowerInvariant() switch
            {
                "현재" => "current",
                "보기" => "show",
                "목록" => "show",
                "설정" => "set",
                "변경" => "set",
                _ => command?.Trim().ToLowerInvariant()
            };
        }

        private static string NormalizeLanguageCode(string language)
        {
            return language?.Trim().ToLowerInvariant() switch
            {
                "한국어" => "KR",
                "한글" => "KR",
                "영어" => "EN",
                "이탈리아어" => "IT",
                "프랑스어" => "FR",
                "독일어" => "DE",
                _ => language?.ToUpper()
            };
        }
    }
}
