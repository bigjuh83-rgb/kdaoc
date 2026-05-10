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

using DOL.Database;
using DOL.Language;

namespace DOL.GS.Commands
{
    [Cmd("&translate", ePrivLevel.GM,
         "GMCommands.Translate.Description",
         "GMCommands.Translate.Help.Debug",
         "GMCommands.Translate.Help.MemAdd",
         "GMCommands.Translate.Help.MemClear",
         "GMCommands.Translate.Help.MemSave",
         "GMCommands.Translate.Help.MemShow",
         "GMCommands.Translate.Help.Refresh",
         "GMCommands.Translate.Help.Select",
         "GMCommands.Translate.Help.SelectClear",
         "GMCommands.Translate.Help.SelectSave",
         "GMCommands.Translate.Help.SelectShow",
         "GMCommands.Translate.Help.Show")]
    //"Use '/translate showlist [showall or Language]' to show a sorted list of all registered translations or to show a list of all translations of a language.")]
    public class TranslateCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        private const string LANGUAGEMGR_MEM_LNG_OBJ = "LANGUAGEMGR_MEM_LNG_OBJ";
        private const string LANGUAGEMGR_SEL_LNG_OBJ = "LANGUAGEMGR_SEL_LNG_OBJ";

        public void OnCommand(GameClient client, string[] args)
        {
            if (IsSpammingCommand(client.Player, "translate"))
                return;

            if (args.Length < 2)
            {
                DisplaySyntax(client);
                return;
            }

            switch (args[1].ToLower())
            {
                #region add
                case "add":
                    {
                        if (client.Account.PrivLevel != (uint)ePrivLevel.Player)
                        {
                            if (args.Length < 5)
                            {
                                DisplayMessage(client, T(client, "GMCommands.Translate.Usage.Add"));
                                return;
                            }

                            LanguageDataObject translation = LanguageMgr.GetLanguageDataObject(args[2].ToUpper(), args[3], LanguageDataObject.eTranslationIdentifier.eSystem);
                            if (translation != null)
                            {
                                DisplayMessage(client, T(client, "GMCommands.Translate.Add.IdAlreadyInUse", args[2].ToUpper(), args[3]));
                                return;
                            }

                            translation = new DbLanguageSystem();
                            ((DbLanguageSystem)translation).TranslationId = args[3];
                            ((DbLanguageSystem)translation).Text = args[4];
                            ((DbLanguageSystem)translation).Language = args[2];

                            GameServer.Database.AddObject(translation);
                            LanguageMgr.RegisterLanguageDataObject(translation);
                            DisplayMessage(client, T(client, "GMCommands.Translate.Add.Success", args[2].ToUpper(), args[3]));
                            return;
                        }

                        return;
                    }
                #endregion add

                #region debug
                case "debug":
                    {
                        bool debug = client.Player.TempProperties.GetProperty<bool>("LANGUAGEMGR-DEBUG");
                        debug = !debug;
                        client.Player.TempProperties.SetProperty("LANGUAGEMGR-DEBUG", debug);
                        DisplayMessage(client, T(client, "GMCommands.Translate.Debug.Mode", T(client, debug ? "GMCommands.Translate.Debug.On" : "GMCommands.Translate.Debug.Off")));
                        return;
                    }
                #endregion debug

                #region memadd
                case "memadd":
                    {
                        // This sub command adds a new language object to your temp properties which will "pre save" the given translation id
                        // and language. Use this sub command if the translation id or text of your new translation requires more room
                        // as the DAoC chat allows you to use in one line. Use the memsave sub command to add a text to this language object
                        // and to save it into the database - or use "memclear" to remove the language object from your temp properties.

                        if (args.Length < 4)
                            DisplayMessage(client, T(client, "GMCommands.Translate.Usage.MemAdd"));
                        else
                        {
                            LanguageDataObject lngObj = client.Player.TempProperties.GetProperty<LanguageDataObject>(LANGUAGEMGR_MEM_LNG_OBJ);

                            if (lngObj != null)
                                DisplayMessage(client, T(client, "GMCommands.Translate.MemAdd.AlreadyExists"));
                            else
                            {
                                lngObj = LanguageMgr.GetLanguageDataObject(args[2].ToUpper(), args[3], LanguageDataObject.eTranslationIdentifier.eSystem);

                                if (lngObj != null)
                                    DisplayMessage(client, T(client, "GMCommands.Translate.MemAdd.CombinationInUse", args[3], args[2].ToUpper()));
                                else
                                {
                                    lngObj = new DbLanguageSystem();
                                    ((DbLanguageSystem)lngObj).TranslationId = args[3];
                                    ((DbLanguageSystem)lngObj).Language = args[2];

                                    client.Player.TempProperties.SetProperty(LANGUAGEMGR_MEM_LNG_OBJ, lngObj);
                                    DisplayMessage(client, T(client, "GMCommands.Translate.MemAdd.Success", args[2].ToUpper(), args[3]));
                                }
                            }
                        }

                        return;
                    }
                #endregion memadd

                #region memclear
                case "memclear":
                    {
                        // Removes the language object from your temp properties you've previously added with the "memadd" sub command.
                        LanguageDataObject lngObj = client.Player.TempProperties.GetProperty<LanguageDataObject>(LANGUAGEMGR_MEM_LNG_OBJ);

                        if (lngObj == null)
                            DisplayMessage(client, T(client, "GMCommands.Translate.NoLanguageObject"));
                        else
                        {
                            client.Player.TempProperties.RemoveProperty(LANGUAGEMGR_MEM_LNG_OBJ);
                            DisplayMessage(client, T(client, "GMCommands.Translate.MemClear.Success"));
                        }

                        return;
                    }
                #endregion memclear

                #region memsave
                case "memsave":
                    {
                        // See "memadd" sub command for a description.
                        if (args.Length < 3)
                            DisplayMessage(client, T(client, "GMCommands.Translate.Usage.MemSave"));
                        else
                        {
                            LanguageDataObject lngObj = client.Player.TempProperties.GetProperty<LanguageDataObject>(LANGUAGEMGR_MEM_LNG_OBJ);

                            if (lngObj == null)
                                DisplayMessage(client, T(client, "GMCommands.Translate.NoLanguageObject"));
                            else
                            {
                                if (args.Length > 3)
                                    ((DbLanguageSystem)lngObj).Text = string.Join(" ", args, 2, args.Length - 2);
                                else
                                    ((DbLanguageSystem)lngObj).Text = args[2];

                                if (!LanguageMgr.RegisterLanguageDataObject(lngObj))
                                    DisplayMessage(client, T(client, "GMCommands.Translate.MemSave.RegisterFailed"));
                                else
                                {
                                    GameServer.Database.AddObject(lngObj);
                                    client.Player.TempProperties.RemoveProperty(LANGUAGEMGR_MEM_LNG_OBJ);
                                    DisplayMessage(client, T(client, "GMCommands.Translate.MemSave.Success"));
                                }
                            }
                        }

                        return;
                    }
                #endregion memsave

                #region memshow
                case "memshow":
                    {
                        LanguageDataObject lngObj = client.Player.TempProperties.GetProperty<LanguageDataObject>(LANGUAGEMGR_MEM_LNG_OBJ);

                        if (lngObj == null)
                            DisplayMessage(client, T(client, "GMCommands.Translate.NoLanguageObject"));
                        else
                            DisplayMessage(client, T(client, "GMCommands.Translate.MemShow.Info", lngObj.Language, lngObj.TranslationId));

                        return;
                    }
                #endregion memshow

                #region refresh
                case "refresh":
                    {
                        if (args.Length < 5)
                            DisplayMessage(client, T(client, "GMCommands.Translate.Usage.Refresh"));
                        else
                        {
                            LanguageDataObject lngObj = LanguageMgr.GetLanguageDataObject(args[2].ToUpper(), args[3], LanguageDataObject.eTranslationIdentifier.eSystem);

                            if (lngObj == null)
                                DisplayMessage(client, T(client, "GMCommands.Translate.Refresh.NotFound", args[3], args[2].ToUpper()));
                            else
                            {
                                ((DbLanguageSystem)lngObj).Text = args[3];
                                GameServer.Database.SaveObject(lngObj);
                                DisplayMessage(client, T(client, "GMCommands.Translate.Refresh.Success", args[3], args[2].ToUpper()));
                            }
                        }

                        return;
                    }
                #endregion refresh

                #region select
                case "select":
                    {
                        if (args.Length < 4)
                            DisplayMessage(client, T(client, "GMCommands.Translate.Usage.Select"));
                        else
                        {
                            LanguageDataObject lngObj = client.Player.TempProperties.GetProperty<LanguageDataObject>(LANGUAGEMGR_SEL_LNG_OBJ);

                            if (lngObj != null)
                            {
                                DisplayMessage(client, T(client, "GMCommands.Translate.Select.AlreadySelected", ((DbLanguageSystem)lngObj).Language, ((DbLanguageSystem)lngObj).TranslationId));
                            }
                            else
                            {
                                lngObj = LanguageMgr.GetLanguageDataObject(args[2].ToUpper(), args[3], LanguageDataObject.eTranslationIdentifier.eSystem);

                                if (lngObj == null)
                                {
                                    DisplayMessage(client, T(client, "GMCommands.Translate.LanguageObjectNotFound", args[2].ToUpper(), args[3]));
                                }
                                else
                                {
                                    client.Player.TempProperties.SetProperty(LANGUAGEMGR_SEL_LNG_OBJ, lngObj);
                                    DisplayMessage(client, T(client, "GMCommands.Translate.Select.Success", args[2].ToUpper(), args[3]));
                                }
                            }
                        }

                        return;
                    }
                #endregion select

                #region selectclear
                case "selectclear":
                    {
                        // Removes the language object from your temp properties you've previously selected with the "select" sub command.
                        LanguageDataObject lngObj = client.Player.TempProperties.GetProperty<LanguageDataObject>(LANGUAGEMGR_SEL_LNG_OBJ);

                        if (lngObj == null)
                            DisplayMessage(client, T(client, "GMCommands.Translate.NoLanguageObjectSelected"));
                        else
                        {
                            client.Player.TempProperties.RemoveProperty(LANGUAGEMGR_SEL_LNG_OBJ);
                            DisplayMessage(client, T(client, "GMCommands.Translate.SelectClear.Success", ((DbLanguageSystem)lngObj).Language, ((DbLanguageSystem)lngObj).TranslationId));
                        }

                        return;
                    }
                #endregion selectclear

                #region selectsave
                case "selectsave":
                    {
                        if (args.Length < 3)
                            DisplayMessage(client, T(client, "GMCommands.Translate.Usage.SelectSave"));
                        else
                        {
                            LanguageDataObject lngObj = client.Player.TempProperties.GetProperty<LanguageDataObject>(LANGUAGEMGR_SEL_LNG_OBJ);

                            if (lngObj == null)
                                DisplayMessage(client, T(client, "GMCommands.Translate.NoLanguageObjectSelected"));
                            else
                            {
                                if (args.Length > 3)
                                    ((DbLanguageSystem)lngObj).Text = string.Join(" ", args, 2, args.Length - 2);
                                else
                                    ((DbLanguageSystem)lngObj).Text = args[2];

                                GameServer.Database.SaveObject(lngObj);
                                client.Player.TempProperties.RemoveProperty(LANGUAGEMGR_SEL_LNG_OBJ);
                                DisplayMessage(client, T(client, "GMCommands.Translate.SelectSave.Success", ((DbLanguageSystem)lngObj).Language, ((DbLanguageSystem)lngObj).TranslationId, ((DbLanguageSystem)lngObj).Text));
                            }
                        }

                        return;
                    }
                #endregion selectsave

                #region selectshow
                case "selectshow":
                    {
                        LanguageDataObject lngObj = client.Player.TempProperties.GetProperty<LanguageDataObject>(LANGUAGEMGR_SEL_LNG_OBJ);

                        if (lngObj == null)
                            DisplayMessage(client, T(client, "GMCommands.Translate.NoLanguageObjectSelected"));
                        else
                            DisplayMessage(client, T(client, "GMCommands.Translate.SelectShow.Info", lngObj.Language, lngObj.TranslationId, ((DbLanguageSystem)lngObj).Text));
                        return;
                    }
                #endregion selectshow

                #region show
                case "show":
                    {
                        if (args.Length < 4)
                            DisplayMessage(client, T(client, "GMCommands.Translate.Usage.Show"));
                        else
                        {
                            LanguageDataObject lngObj = LanguageMgr.GetLanguageDataObject(args[2].ToUpper(), args[3], LanguageDataObject.eTranslationIdentifier.eSystem);

                            if (lngObj == null)
                                DisplayMessage(client, T(client, "GMCommands.Translate.LanguageObjectNotFound", args[2].ToUpper(), args[3]));
                            else
                                DisplayMessage(client, T(client, "GMCommands.Translate.Show.Text", ((DbLanguageSystem)lngObj).Text));
                        }

                        return;
                    }
                #endregion show

                #region showlist
                /*
                 * The code works fine, but DAoC does not support a such huge list.
                 *
                 * case "showlist":
                    {
                        if (args.Length < 3)
                            DisplayMessage(client, "aaa");
                        else
                        {
                            #region showall
                            if (args[2].ToLower() == "showall")
                            {
                                IDictionary<string, IList<string>> idLangs = new Dictionary<string, IList<string>>();
                                List<string> languages = new List<string>();
                                languages.AddRange(LanguageMgr.Languages);
                                IList<string> data = new List<string>();

                                foreach (string language in LanguageMgr.Translations.Keys)
                                {
                                    if (!LanguageMgr.Translations[language].ContainsKey(LanguageDataObject.eTranslationIdentifier.eSystem))
                                        continue;

                                    data.Add("======== Language <" + language + "> ========\n\n");

                                    foreach (LanguageDataObject lngObj in LanguageMgr.Translations[language][LanguageDataObject.eTranslationIdentifier.eSystem])
                                    {
                                        data.Add("TranslationId: " + lngObj.TranslationId + "\nText: " + ((DBLanguageSystem)lngObj).Text + "\n\n");

                                        if (!idLangs.ContainsKey(lngObj.TranslationId))
                                        {
                                            IList<string> langs = new List<string>();
                                            langs.Add(lngObj.Language);
                                            idLangs.Add(lngObj.TranslationId, langs);
                                            continue;
                                        }

                                        if (!idLangs[lngObj.TranslationId].Contains(lngObj.Language))
                                            idLangs[lngObj.TranslationId].Add(lngObj.Language);

                                        continue;
                                    }
                                }

                                IDictionary<string, IList<string>> missingLanguageTranslations = new Dictionary<string, IList<string>>();

                                foreach (string translationId in idLangs.Keys)
                                {
                                    foreach (string language in languages)
                                    {
                                        if (idLangs[translationId].Contains(language))
                                            continue;

                                        if (!missingLanguageTranslations.ContainsKey(translationId))
                                        {
                                            IList<string> langs = new List<string>();
                                            langs.Add(language);
                                            missingLanguageTranslations.Add(translationId, langs);
                                            continue;
                                        }

                                        if (!missingLanguageTranslations[translationId].Contains(language))
                                            missingLanguageTranslations[translationId].Add(language);

                                        continue;
                                    }
                                }

                                if (missingLanguageTranslations.Count > 0)
                                {
                                    data.Add("======== Missing language translations ========\n\n");

                                    foreach (string translationId in missingLanguageTranslations.Keys)
                                    {
                                        string str = ("TranslationId: " + translationId + "\nLanguages: ");

                                        foreach (string language in missingLanguageTranslations[translationId])
                                            str += (language + ",");

                                        if (str[(str.Length - 1)] == ',')
                                            str = str.Remove(str.Length - 1);

                                        data.Add(str);
                                    }
                                }

                                client.Out.SendCustomTextWindow("[Language-Manager] Translations", data); // I wish you a merry christmas and a happy new year (2112)! :-)
                            }
                            #endregion  showall

                            #region language
                            else
                            {
                                if (!LanguageMgr.Languages.Contains(args[2].ToUpper()))
                                    DisplayMessage(client, "aaa");
                                else
                                {
                                    if (!LanguageMgr.Translations[args[2].ToUpper()].ContainsKey(LanguageDataObject.eTranslationIdentifier.eSystem))
                                        DisplayMessage(client, "aaa");
                                    else
                                    {
                                        IList<string> data = new List<string>();

                                        foreach (LanguageDataObject lngObj in LanguageMgr.Translations[args[2].ToUpper()][LanguageDataObject.eTranslationIdentifier.eSystem])
                                            data.Add("TranslationId: " + lngObj.TranslationId + "\nText: " + ((DBLanguageSystem)lngObj).Text + "\n\n");

                                        client.Out.SendCustomTextWindow("[Language-Manager] Language translations <" + args[2].ToUpper() + ">", data);
                                    }
                                }
                            }
                            #endregion language
                        }

                        return;
                    }*/
                #endregion showlist

                default:
                    {
                        DisplaySyntax(client);
                        return;
                    }
            }
        }
    }
}
