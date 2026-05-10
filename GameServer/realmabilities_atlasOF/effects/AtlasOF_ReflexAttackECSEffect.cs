using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Effects
{
    public class ReflexAttackECSEffect : ECSGameAbilityEffect
    {
        public ReflexAttackECSEffect(in ECSGameEffectInitParams initParams)
            : base(initParams)
        {
            EffectType = eEffect.ReflexAttack;
        }

        public override ushort Icon { get { return 4277; } }
        public override string Name { get { return "Reflex Attack"; } }
        public override bool HasPositiveEffect { get { return true; } }

        public override void OnStartEffect()
        {
            if (OwnerPlayer == null)
                return;

            foreach (GamePlayer t_player in OwnerPlayer.GetPlayersInRadius(WorldMgr.INFO_DISTANCE))
            {
                if (t_player == OwnerPlayer)
                {
                    OwnerPlayer.Out.SendMessage(LanguageMgr.GetTranslation(OwnerPlayer.Client.Account.Language, "AtlasOF.ReflexAttack.Begins"), eChatType.CT_Spell, eChatLoc.CL_SystemWindow);
                }
                else
                {
                    t_player.Out.SendMessage(LanguageMgr.GetTranslation(t_player.Client.Account.Language, "AtlasOF.ReflexAttack.OtherBegins", OwnerPlayer.Name), eChatType.CT_Spell, eChatLoc.CL_SystemWindow);
                }
                t_player.Out.SendSpellEffectAnimation(OwnerPlayer, OwnerPlayer, 7012, 0, false, 1);
            }
        }

        public override void OnStopEffect()
        {
            if (OwnerPlayer == null)
                return;

            foreach (GamePlayer t_player in OwnerPlayer.GetPlayersInRadius(WorldMgr.INFO_DISTANCE))
            {
                if (t_player == OwnerPlayer)
                {
                    OwnerPlayer.Out.SendMessage(LanguageMgr.GetTranslation(OwnerPlayer.Client.Account.Language, "AtlasOF.ReflexAttack.Ends"), eChatType.CT_Spell, eChatLoc.CL_SystemWindow);
                }
                else
                {
                    t_player.Out.SendMessage(LanguageMgr.GetTranslation(t_player.Client.Account.Language, "AtlasOF.ReflexAttack.OtherEnds", OwnerPlayer.Name), eChatType.CT_Spell, eChatLoc.CL_SystemWindow);
                }
            }
        }
    }
}
