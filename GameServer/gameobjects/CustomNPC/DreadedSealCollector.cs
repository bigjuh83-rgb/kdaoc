using System;
using System.Collections.Generic;
using DOL.Database;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS
{
    /// <summary>
    /// LootGeneratorDreadedSeal
    /// Adds Glowing Dreaded Seal to loot
    /// </summary>
    public class DreadedSealCollector : GameNPC
    {
        private static new readonly Logging.Logger log = Logging.LoggerManager.Create(System.Reflection.MethodBase.GetCurrentMethod().DeclaringType);

        protected static List<Tuple<int, int>> m_levelMultipliers = ParseMultipliers();
        protected static Dictionary<string, float> m_BPMultipliers = ParseValues(ServerProperties.Properties.DREADEDSEALS_BP_VALUES);
        protected static Dictionary<string, float> m_RPMultipliers = ParseValues(ServerProperties.Properties.DREADEDSEALS_RP_VALUES);

        /// <summary>
        /// Parse a server property string level multiplier values
        /// </summary>
        /// <param name="serverProperty"></param>
        /// <returns></returns>
        protected static List<Tuple<int, int>> ParseMultipliers()
        {
            List<Tuple<int, int>> list = new List<Tuple<int, int>>();

            foreach (string entry in ServerProperties.Properties.DREADEDSEALS_LEVEL_MULTIPLIER.Split(';'))
            {
                string[] asVal = entry.Split('|');

                if (asVal.Length > 1 && int.TryParse(asVal[0], out int level) && int.TryParse(asVal[1], out int multiplier))
                    list.Add(Tuple.Create(level, multiplier));
            } // foreach

            if (list.Count > 0)
                list.Sort();
            else
                log.Error("ParseMultipliers: Could not parse any level multipliers; DreadedSealCollector disabled.");

            return list;
        }

        /// <summary>
        /// Parse a server property string BP or RP values
        /// </summary>
        /// <param name="serverProperty"></param>
        /// <returns></returns>
        protected static Dictionary<string, float> ParseValues(string serverProperty)
        {
            Dictionary<string, float> dict = new Dictionary<string, float>();

            foreach (string entry in serverProperty.Split(';'))
            {
                string[] asVal = entry.Split('|');

                if (asVal.Length > 1 && float.TryParse(asVal[1], out float value))
                    dict[asVal[0]] = value;
            } // foreach

            return dict;
        }

        private void SendReply(GamePlayer target, string msg)
        {
            target.Out.SendMessage(msg, eChatType.CT_System, eChatLoc.CL_ChatWindow);
        }

        public override bool Interact(GamePlayer player)
        {
            if (!base.Interact(player))
                return false;

            string response;

            if (m_levelMultipliers.Count <= 0)
                response = "Sorry, no level multipliers are defined so I cannot accept seals at this time.";
            else if (m_BPMultipliers.Count > 0 && m_RPMultipliers.Count > 0)
                response = LanguageMgr.GetTranslation(player.Client.Account.Language, "DreadedSealCollector.HandSealsForBpAndRp");
            else if (m_BPMultipliers.Count > 0)
                response = LanguageMgr.GetTranslation(player.Client.Account.Language, "DreadedSealCollector.HandSealsForBp");
            else if (m_RPMultipliers.Count > 0)
                response = LanguageMgr.GetTranslation(player.Client.Account.Language, "DreadedSealCollector.HandSealsForRp");
            else
                response = LanguageMgr.GetTranslation(player.Client.Account.Language, "DreadedSealCollector.NoSealTypesDefined");
            player.Out.SendMessage(response, eChatType.CT_Say, eChatLoc.CL_ChatWindow);

            return true;
        }

        public override bool ReceiveItem(GameLiving source, DbInventoryItem item)
        {
            if (source is GamePlayer player && item != null)
            {
                if (GetDistanceTo(player) > WorldMgr.INTERACT_DISTANCE)
                {
                    player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "DreadedSealCollector.TooFarAway", player.Name), eChatType.CT_Say, eChatLoc.CL_ChatWindow);
                    return false;
                }

                if (m_levelMultipliers.Count < 1)
                {
                    player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "DreadedSealCollector.NoLevelMultipliers"),
                        eChatType.CT_Say, eChatLoc.CL_ChatWindow);
                    return false;
                }

                m_BPMultipliers.TryGetValue(item.Id_nb, out float bpMultiplier);
                m_RPMultipliers.TryGetValue(item.Id_nb, out float rpMultiplier);

                if (bpMultiplier < 1 && rpMultiplier < 1)
                {
                    player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "DreadedSealCollector.CannotAcceptItemType"),
                        eChatType.CT_Say, eChatLoc.CL_ChatWindow);
                    return false;
                }
                else
                {
                    int levelMultiplier = 0;
                    int nextLevel = 0;

                    foreach (Tuple<int, int> tup in m_levelMultipliers)
                    {
                        if (player.Level >= tup.Item1)
                            levelMultiplier = tup.Item2;
                        else
                        {
                            nextLevel = tup.Item1;
                            break;
                        }
                    }

                    if (levelMultiplier <= 0)
                    {
                        player.Out.SendMessage(LanguageMgr.GetTranslation(player.Client.Account.Language, "DreadedSealCollector.TooYoung", player.Name, nextLevel - player.Level), eChatType.CT_Say, eChatLoc.CL_ChatWindow);

                        return false;
                    }

                    if (bpMultiplier > 0)
                        player.GainBountyPoints((int)(item.Count * levelMultiplier * bpMultiplier));

                    if (rpMultiplier > 0)
                        player.GainRealmPoints((int)(item.Count * levelMultiplier * rpMultiplier));

                    player.Inventory.RemoveItem(item);
                    player.Out.SendUpdatePoints();

                    return true;
                }
            }

            return base.ReceiveItem(source, item);
        }
    }
}
