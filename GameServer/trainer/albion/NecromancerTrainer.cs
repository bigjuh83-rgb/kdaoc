using System;
using DOL.Language;

namespace DOL.GS.Trainer
{
	/// <summary>
	/// Necromancer trainer.
	/// </summary>
	/// <author>Aredhel</author>
	[NPCGuildScript("Necromancer Trainer", eRealm.Albion)]
	public class NecromancerTrainer : GameTrainer
	{
		public override eCharacterClass TrainedClass
		{
			get { return eCharacterClass.Necromancer; }
		}

		public const string WEAPON_ID = "necromancer_item";

		public NecromancerTrainer()
			: base() { }

		/// <summary>
		/// Interact with trainer.
		/// </summary>
		/// <param name="player"></param>
		/// <returns></returns>
		public override bool Interact(GamePlayer player)
		{
			if (!base.Interact(player)) return false;

			// If the player is a necromancer, offer training, if it is a disciple,
			// offer a promotion. Otherwise send them somewhere else.
			if (player.CharacterClass.ID == (int)TrainedClass)
			{
				OfferTraining(player);
			}
			else
			{
				if (CanPromotePlayer(player))
				{
						SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.NecromancerPrompt"));
					if (!player.IsLevelRespecUsed)
					{
						OfferRespecialize(player);
					}
				}
				else
					CheckChampionTraining(player);
			}
			return true;
		}

		/// <summary>
		/// Talk to the trainer.
		/// </summary>
		/// <param name="source"></param>
		/// <param name="text"></param>
		/// <returns></returns>
		public override bool WhisperReceive(GameLiving source, string text)
		{
			if (!base.WhisperReceive(source, text)) return false;
			GamePlayer player = source as GamePlayer;

			switch (text.ToLower())
			{
					case "necromancers":
					case "네크로맨서":
						SayTo(player, LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.NecromancerInfo"));
						break;

					case "join the temple of arawn":
					case "아라운 사원 입문":
						if (CanPromotePlayer(player))
						{
							PromotePlayer(player, (int)eCharacterClass.Necromancer,
							              LanguageMgr.GetTranslation(player.Client.Account.Language, "AlbionTrainer.NecromancerWelcome"), null);
							player.ReceiveItem(this, WEAPON_ID);
						}
					break;
			}
			return true;
		}
	}
}
