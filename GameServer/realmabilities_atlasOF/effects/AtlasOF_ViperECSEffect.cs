using DOL.GS.PacketHandler;
using DOL.GS.Spells;
using DOL.Language;

namespace DOL.GS.Effects
{
    public class AtlasOF_ViperECSEffect : ECSGameAbilityEffect
    {
        public new SpellHandler SpellHandler;
        public AtlasOF_ViperECSEffect(in ECSGameEffectInitParams initParams)
            : base(initParams)
        {
            EffectType = eEffect.Viper;
        }

        public override ushort Icon { get { return 4283; } }
        public override string Name { get { return "Viper"; } }
        public override bool HasPositiveEffect { get { return true; } }

        public override void OnStartEffect()
        {
            base.OnStartEffect();
            if(OwnerPlayer != null) OwnerPlayer.Out.SendMessage(LanguageMgr.GetTranslation(OwnerPlayer.Client.Account.Language, "AtlasOF.Viper.Begins"), eChatType.CT_Spell, eChatLoc.CL_SystemWindow);
        }

        public override void OnStopEffect()
        {
            if(OwnerPlayer != null) OwnerPlayer.Out.SendMessage(LanguageMgr.GetTranslation(OwnerPlayer.Client.Account.Language, "AtlasOF.Viper.Ends"), eChatType.CT_Spell, eChatLoc.CL_SystemWindow);
            base.OnStopEffect();
        }
    }
}
