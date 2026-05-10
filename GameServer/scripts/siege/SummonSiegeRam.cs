using System.Collections.Generic;
using DOL.GS.Keeps;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS.Spells
{
    [SpellHandler(eSpellType.SummonSiegeRam)]
    public class SummonSiegeRam : SpellHandler
    {
        public SummonSiegeRam(GameLiving caster, Spell spell, SpellLine line) : base(caster, spell, line) { }

        public override bool StartSpell(GameLiving target)
        {
            if (!Caster.CurrentZone.IsOF || Caster.CurrentRegion.IsDungeon)
            {
                MessageToCaster(T("Siege.Summon.CannotUseHere"), eChatType.CT_SpellResisted);
                return false;
            }

            if (Caster is not GamePlayer player)
                return false;

            if (!player.CurrentZone.IsOF || player.CurrentRegion.IsDungeon)
            {
                MessageToCaster(T("Siege.Summon.CannotUseHere"), eChatType.CT_SpellResisted);
                return false;
            }

            // Overwrite the target, since this is used like a potion.
            target = Caster.TargetObject as GameLiving;

            if (target is not (GameKeepDoor or GameRelicDoor))
            {
                MessageToCaster(T("Siege.Summon.NeedDoorTarget"), eChatType.CT_SpellResisted);
                return false;
            }

            if (!target.IsAttackable)
            {
                MessageToCaster(T("Siege.Summon.TargetNotAttackable"), eChatType.CT_SpellResisted);
                return false;
            }

            if (!Caster.IsWithinRadius(target, 500))
            {
                player.Out.SendMessage(T("Siege.Summon.TooFar", Caster.TargetObject.Name), eChatType.CT_SpellResisted, eChatLoc.CL_SystemWindow);
                return false;
            }

            if (Caster.GetDistanceTo(target) < 200)
            {
                player.Out.SendMessage(T("Siege.Summon.TooClose", Caster.TargetObject.Name), eChatType.CT_SpellResisted, eChatLoc.CL_SystemWindow);
                return false;
            }

            // Limit 2 Rams in a certain radius.
            int ramSummonRadius = 200;
            int ramsInRadius = 0;

            foreach (GameNPC npc in Caster.GetNPCsInRadius((ushort) ramSummonRadius))
            {
                if (npc is GameSiegeRam ram && ram.Realm == Caster.Realm)
                    ramsInRadius++;
            }

            if (ramsInRadius >= 2)
            {
                MessageToCaster(T("Siege.Summon.TooManyRams"), eChatType.CT_SpellResisted);
                return false;
            }

            return base.StartSpell(target);
        }

        public override void ApplyEffectOnTarget(GameLiving target)
        {
            base.ApplyEffectOnTarget(target);

            if (Caster is not GamePlayer player)
                return;

            GameSiegeRam ram = new()
            {
                X = Caster.X,
                Y = Caster.Y,
                Z = Caster.Z,
                Heading = Caster.Heading,
                CurrentRegion = Caster.CurrentRegion,
                Realm = Caster.Realm
            };

            //determine the ram level based on Spell Damage
            switch (Spell.Damage)
            {
                case 0:
                {
                    ram.Level = 0;
                    ram.Name = "mini siege ram";
                    ram.Model = 2605;
                    break;
                }
                case 1:
                {
                    ram.Level = 1;
                    ram.Name = "light siege ram";
                    ram.Model = 2600;
                    break;
                }
                case 2:
                {
                    ram.Level = 2;
                    ram.Name = "medium siege ram";
                    ram.Model = 2601;
                    break;
                }
                case 3:
                {
                    ram.Level = 3;
                    ram.Name = "heavy siege ram";
                    ram.Model = 2602;
                    break;
                }
            }

            ram.AddToWorld();
            player.MountSteed(ram,true);
            ram.TakeControl(player);
        }

        public override bool CheckBeginCast(GameLiving selectedTarget)
        {
            if (selectedTarget is not (GameKeepDoor or GameRelicDoor))
            {
                MessageToCaster(T("Siege.Summon.NeedDoorTarget"), eChatType.CT_SpellResisted);
                return false;
            }

            return base.CheckBeginCast(selectedTarget);
        }

        private string T(string key, params object[] args)
        {
            return LanguageMgr.GetTranslation((Caster as GamePlayer)?.Client, key, args);
        }

        public override IList<string> DelveInfo
        {
            get
            {
                return new List<string>
                {
                    ShortDescription
                };
            }
        }
    }
}
