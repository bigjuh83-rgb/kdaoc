using System;
using System.Collections.Generic;

namespace DOL.GS.WorldAI
{
    public enum DynamicQuestNodeType
    {
        Talk,
        Kill,
        ReturnToNpc,
        Choice,
        Complete,
        Fail,
        Explore
    }

    public enum DynamicQuestEdgeCondition
    {
        Always,
        ObjectiveComplete,
        ChoiceSelected,
        PlayerDied,
        TimedOut,
        PartySizeAtLeast,
        WorldSignal
    }

    internal static class DynamicQuestWorldSignalPolicy
    {
        public const string FallbackTimeoutSeconds = "60";

        public static bool IsAllowed(string value)
        {
            value = (value ?? string.Empty).Trim().ToLowerInvariant();
            if (string.IsNullOrWhiteSpace(value))
                return false;

            foreach (char ch in value)
            {
                if (char.IsWhiteSpace(ch))
                    return false;
            }

            if (value == "mob-growth:killed" ||
                value == "mob-growth:killed:mutant" ||
                value == "mob-growth:killed:elite" ||
                value == "mob-growth:killed:champion" ||
                value == "mob-growth:killed:boss" ||
                value == "mob-growth:killed:stage:elite" ||
                value == "mob-growth:killed:stage:champion" ||
                value == "mob-growth:killed:stage:boss")
            {
                return true;
            }

            if (TryParseUInt16Suffix(value, "mob-growth:killed:region:"))
                return true;

            if (value == "time-window" ||
                value == "time-window:dawn" ||
                value == "time-window:day" ||
                value == "time-window:dusk" ||
                value == "time-window:night")
            {
                return true;
            }

            if (value == "item-acquired" ||
                TryParseSafeTokenSuffix(value, "item-acquired:id:") ||
                TryParseSafeTokenSuffix(value, "item-acquired:name:"))
            {
                return true;
            }

            if (TryParseSafeTokenSuffix(value, "scene:"))
                return true;

            return value == "region-entered" ||
                   TryParseUInt16Suffix(value, "region-entered:") ||
                   TryParseUInt16Suffix(value, "region:");
        }

        private static bool TryParseUInt16Suffix(string value, string prefix)
        {
            if (!value.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                return false;

            return ushort.TryParse(value.Substring(prefix.Length), out _);
        }

        private static bool TryParseSafeTokenSuffix(string value, string prefix)
        {
            if (!value.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                return false;

            string token = value.Substring(prefix.Length);
            if (token.Length == 0 || token.Length > 80)
                return false;

            foreach (char ch in token)
            {
                if (!(char.IsLetterOrDigit(ch) || ch == '-' || ch == '_' || ch == '.'))
                    return false;
            }

            return true;
        }
    }

    internal enum RewardScaleKind
    {
        Xp,
        Money
    }

    public sealed class DynamicQuestChoice
    {
        public string Id { get; set; } = string.Empty;
        public string Label { get; set; } = string.Empty;
        public string Text { get; set; } = string.Empty;
        public string Consequence { get; set; } = string.Empty;
    }

    public sealed class DynamicQuestObjective
    {
        public string TargetName { get; set; } = string.Empty;
        public int TargetCount { get; set; } = 1;
        public int MinLevel { get; set; } = 1;
        public int MaxLevel { get; set; } = 50;
        public ushort RegionId { get; set; }
        public bool AllowGroupCredit { get; set; }
        public string NpcInternalId { get; set; } = string.Empty;
        public string NpcName { get; set; } = string.Empty;
        public string LocationName { get; set; } = string.Empty;
        public int X { get; set; }
        public int Y { get; set; }
        public int Z { get; set; }
        public int Radius { get; set; }
        public IList<DynamicQuestChoice> Choices { get; set; } = Array.Empty<DynamicQuestChoice>();
    }

    public sealed class DynamicQuestEdge
    {
        public string ToNodeId { get; set; } = string.Empty;
        public DynamicQuestEdgeCondition Condition { get; set; } = DynamicQuestEdgeCondition.Always;
        public string ConditionValue { get; set; } = string.Empty;
        public int Priority { get; set; }
    }

    public sealed class DynamicQuestNode
    {
        public string Id { get; set; } = string.Empty;
        public DynamicQuestNodeType Type { get; set; }
        public string Title { get; set; } = string.Empty;
        public string Text { get; set; } = string.Empty;
        public DynamicQuestObjective Objective { get; set; } = new();
        public IList<DynamicQuestEdge> Edges { get; set; } = Array.Empty<DynamicQuestEdge>();
    }

    public sealed class DynamicQuestRewardDefinition
    {
        public double XpMultiplier { get; set; } = 1.0;
        public double MoneyMultiplier { get; set; } = 1.0;
        public double StepBonusMultiplier { get; set; }
        public double PartyBonusMultiplier { get; set; } = 1.0;
        public string ChoiceBonusKey { get; set; } = string.Empty;
    }
}
