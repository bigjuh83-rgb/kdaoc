
using DOL.Database;
using DOL.GS.PacketHandler;
using DOL.Language;

namespace DOL.GS
{
	/// <summary>
	/// Represents an in-game StatsCustomiser NPC
	/// </summary>
	public class StatsCustomiser : GameNPC
	{

		private const string StatsResetKey = "StatsReset";

		/// <summary>
		/// Constructor
		/// </summary>
		public StatsCustomiser () : base()
		{
		}

		/// <summary>
		/// Called when a player right clicks on the npc
		/// </summary>
		/// <param name="player">Player that interacting</param>
		/// <returns>True if succeeded</returns>
		public override bool Interact(GamePlayer player)
		{
			if (!base.Interact(player))
				return false;

			TurnTo(player, 5000);

			var alreadyReset = DOLDB<DbCoreCharacterXCustomParam>.SelectObject(DB.Column("DOLCharactersObjectId")
				.IsEqualTo(player.ObjectId).And(DB.Column("KeyName").IsEqualTo(StatsResetKey)));

			if(alreadyReset == null)
			{
				SayTo(player, eChatLoc.CL_PopupWindow, LanguageMgr.GetTranslation(player.Client.Account.Language, "StatsCustomiser.Interact.Offer", player.CharacterClass.Name));
			}
			else
			{
				SayTo(player, eChatLoc.CL_PopupWindow, LanguageMgr.GetTranslation(player.Client.Account.Language, "StatsCustomiser.Interact.AlreadyGranted"));
			}

			return true;
		}

		/// <summary>
		/// This function is called when the Living receives a whispered text
		/// </summary>
		/// <param name="source">GameLiving that was whispering</param>
		/// <param name="text">string that was whispered</param>
		/// <returns>true if the string correctly processed</returns>
		public override bool WhisperReceive(GameLiving source, string text)
		{
			if (!base.WhisperReceive(source, text))
				return false;

			GamePlayer player = source as GamePlayer;
			if (player == null)
				return false;

			var alreadyReset = DOLDB<DbCoreCharacterXCustomParam>.SelectObject(DB.Column("DOLCharactersObjectId")
				.IsEqualTo(player.ObjectId).And(DB.Column("KeyName").IsEqualTo(StatsResetKey)));

			string normalizedText = text.ToLowerInvariant();

			if (alreadyReset == null && (normalizedText == "stats respec" || text == "능력치 초기화"))
			{
				SayTo(player, eChatLoc.CL_PopupWindow, LanguageMgr.GetTranslation(player.Client.Account.Language, "StatsCustomiser.Whisper.DoneLogoutRequired"));
				player.CustomisationStep = 3;

				DbCoreCharacterXCustomParam statsReset = new DbCoreCharacterXCustomParam();
				statsReset.DOLCharactersObjectId = player.ObjectId;
				statsReset.KeyName = StatsResetKey;
				statsReset.Value = "1";
				GameServer.Database.AddObject(statsReset);

			}
			return true;
		}
	}
}
