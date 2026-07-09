using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection;
using DOL.Database;

namespace DOL.GS.ServerProperties
{
	/// <summary>
	/// The abstract ServerProperty class that also defines the
	/// static Init and Load methods for other properties that inherit
	/// </summary>
	public abstract class Properties
	{
		/// <summary>
		/// Defines a logger for this class.
		/// </summary>
		private static readonly Logging.Logger log = Logging.LoggerManager.Create(MethodBase.GetCurrentMethod().DeclaringType);

		/// <summary>
		/// Init the properties
		/// </summary>
		public static void InitProperties()
		{
			var propDict = AllDomainProperties;
			foreach (var prop in propDict)
			{
				Load(prop.Value.Item1, prop.Value.Item2, prop.Value.Item3);
			}
			
			// Refresh static dict values for display
			AllCurrentProperties = propDict.ToDictionary(k => k.Key, v => v.Value.Item2.GetValue(null));
		}

		// Properties: feel free to improve the SPs in the
		// categories below, or extend the category list.

		#region SYSTEM / DEBUG
		/// <summary>
		/// TempProperties to register
		/// </summary>
		[ServerProperty("system", "tempproperties_to_register", "Serialized list of tempprop string, separated by semi-colon for be registered when a player disconnect", "LastPotionItemUsedTick;SpellAvailableTime;ItemUseDelay;LastChargedItemUsedTick")]
		public static string TEMPPROPERTIES_TO_REGISTER;
		/// <summary>
		/// Do we activate TempProperties manager Checkup on log in
		/// </summary>
		[ServerProperty("system", "activate_temp_properties_manager_checkup", "Do we activate TempProperties manager Checkup on log in?", true)]
		public static bool ACTIVATE_TEMP_PROPERTIES_MANAGER_CHECKUP;
		/// <summary>
		/// Do we activate TempProperties manager Checkup debug
		/// </summary>
		[ServerProperty("log", "activate_temp_properties_manager_checkup_debug", "Do we activate TempProperties manager Checkup debug?", false)]
		public static bool ACTIVATE_TEMP_PROPERTIES_MANAGER_CHECKUP_DEBUG;
		/// <summary>
		/// Enable Debug mode - used to alter some features during server startup to make debugging easier
		/// Can be changed while server is running but may require restart to enable all debug features
		/// </summary>
		[ServerProperty("system", "enable_debug", "Enable Debug mode? Used to alter some features during server startup to make debugging easier", false)]
		public static bool ENABLE_DEBUG;

		/// <summary>
		/// Use raw RNG instead of Deck of Cards
		/// </summary>
		[ServerProperty("system", "override_deck_rng", "Should we use raw RNG instead of Deck-Of-Cards normalization?", false)]
		public static bool OVERRIDE_DECK_RNG;

		/// <summary>
		/// Maximum length for reward quest description text to prevent client crashes
		/// </summary>
		[ServerProperty("system", "max_rewardquest_description_length", "Maximum length for reward quest description text to prevent client crashes.", 1000)]
		public static int MAX_REWARDQUEST_DESCRIPTION_LENGTH;

		/// <summary>
		/// If the server should only accept connections from staff
		/// </summary>
		[ServerProperty("system", "staff_login", "Staff Login Only - Edit this to set weather you wish staff to be the only ones allowed to Log in values True,False", false)]
		public static bool STAFF_LOGIN;

		/// <summary>
		/// The minimum client version required to connect
		/// </summary>
		[ServerProperty("system", "client_version_min", "Minimum Client Version - Edit this to change which client version at the least have to be used: -1 = any, 1.80 = 180", -1)]
		public static int CLIENT_VERSION_MIN;

		/// <summary>
		/// What is the maximum client type allowed to connect
		/// </summary>
		[ServerProperty("system", "client_type_max", "What is the maximum client type allowed to connect", -1)]
		public static int CLIENT_TYPE_MAX;

		/// <summary>
		/// The maximum client version required to connect
		/// </summary>
		[ServerProperty("system", "client_version_max", "Maximum Client Version - Edit this to change which client version at the most have to be used: -1 = any, 1.80 = 180", -1)]
		public static int CLIENT_VERSION_MAX;

		/// <summary>
		/// Enable RC4 encryption for communication between the client and the server
		/// </summary>
		[ServerProperty("system", "client_enable_encryption_rc4", "Enable client RC4 encryption - Advanced user only, you need a special launcher to enable encryption", false)]
		public static bool CLIENT_ENABLE_ENCRYPTION_RC4;

		/// <summary>
		/// Should the server load quests
		/// </summary>
		[ServerProperty("system", "load_quests", "Should the server load quests, values True,False", true)]
		public static bool LOAD_QUESTS;

		/// <summary>
		/// Should the server load Buff Tokens
		/// </summary>
		[ServerProperty("system", "load_buff_tokens", "Should the server load buff tokens (npc and items), values True,False", true)]
		public static bool LOAD_BUFF_TOKENS;

		/// <summary>
		/// Should the server load Arrow Summoning items
		/// </summary>
		[ServerProperty("system", "load_arrow_summoning", "Should the server load Arrow Summoning items, values True,False", true)]
		public static bool LOAD_ARROW_SUMMONING;

		/// <summary>
		/// Should the server load Housing items
		/// </summary>
		[ServerProperty("system", "load_housing_items", "Should the server load Housing items, values True,False", true)]
		public static bool LOAD_HOUSING_ITEMS;

		/// <summary>
		/// Should the server load Housing NPC
		/// </summary>
		[ServerProperty("system", "load_housing_npc", "Should the server load Housing npc, values True,False", true)]
		public static bool LOAD_HOUSING_NPC;

		/// <summary>
		/// Disable Bug Reports
		/// </summary>
		[ServerProperty("system", "disable_bug_reports", "Set to true to disable bug reporting, and false to enable bug reporting", true)]
		public static bool DISABLE_BUG_REPORTS;
		/// <summary>
		/// Max bug repots in Queue
		/// </summary>
		[ServerProperty("system", "max_bugreport_queue", "Maximum number of bug reports allowed in queue.  0 to disabled max check", 100)]
		public static int MAX_BUGREPORT_QUEUE;

		/// <summary>
		/// The max number of players on the server
		/// </summary>
		[ServerProperty("system", "max_players", "Max Players - Edit this to set the maximum players allowed to connect at the same time", 4000)]
		public static int MAX_PLAYERS;

		/// <summary>
		/// What class should the server use for players
		/// </summary>
		[ServerProperty("system", "player_class", "What class should the server use for players", "DOL.GS.GamePlayer")]
		public static string PLAYER_CLASS;

		/// <summary>
		/// A serialised list of RegionIDs that will load objects
		/// </summary>
		[ServerProperty("system", "debug_load_regions", "Serialized list of region IDs that will load objects, separated by semi-colon (leave this blank to load all regions normally)", "")]
		public static string DEBUG_LOAD_REGIONS;

		/// <summary>
		/// A serialised list of disabled expansion IDs
		/// </summary>
		[ServerProperty("system", "disabled_expansions", "Serialized list of disabled expansions IDs, expansion IDs are client type seperated by ;", "")]
		public static string DISABLED_EXPANSIONS = string.Empty;

		/// <summary>
		/// Server Language
		/// </summary>
		[ServerProperty("system", "server_language", "Language of your server. It can be EN, FR or DE.", "EN")]
		public static string SERV_LANGUAGE;

		/// <summary>
		/// allow_change_language
		/// </summary>
		[ServerProperty("system", "allow_change_language", "Should we allow clients to change their language ?", false)]
		public static bool ALLOW_CHANGE_LANGUAGE;

		/// <summary>
		/// Allow player to change their character face after creation through customizing ?
		/// </summary>
		[ServerProperty("system", "allow_customize_face_after_creation", "Allow player to change their character face after creation through customizing ?", true)]
		public static bool ALLOW_CUSTOMIZE_FACE_AFTER_CREATION;

		/// <summary>
		/// Allow player to change their character starting stats after creation through customizing ?
		/// </summary>
		[ServerProperty("system", "allow_customize_stats_after_creation", "Allow player to change their character starting stats after creation through customizing ?", true)]
		public static bool ALLOW_CUSTOMIZE_STATS_AFTER_CREATION;

		/// <summary>
		/// StatSave Interval
		/// </summary>
		[ServerProperty("system", "statsave_interval", "Interval (in minutes) at which performance statistics are saved to the database. 0 or less to deactivate.", 0)]
		public static int STATSAVE_INTERVAL;

		/// <summary>
		/// Bug Report Email Addresses
		/// </summary>
		[ServerProperty("system", "bug_report_email_addresses", "set to the email addresses you want bug reports sent to (bug reports will only send if the user has set an email address for his account, multiple addresses seperate with ;", "")]
		public static string BUG_REPORT_EMAIL_ADDRESSES;

		/// <summary>
		/// Ban Hackers
		/// </summary>
		[ServerProperty("system", "ban_hackers", "Should we ban hackers, if set to true, bans will be done, if set to false, kicks will be done", false)]
		public static bool BAN_HACKERS;

		/// <summary>
		/// Is the database translated
		/// </summary>
		[ServerProperty("system", "db_language", "What language is the DB", "EN")]
		public static string DB_LANGUAGE;

		[ServerProperty("system", "statprint_frequency", "Interval (in milliseconds) at which performance statistics are gathered and print to the server console. 0 or less to deactivate.", 30000)]
		public static int STATPRINT_FREQUENCY;

		/// <summary>
		/// Should users be able to create characters in all realms using the same account
		/// </summary>
		[ServerProperty("system", "allow_all_realms", "should we allow characters to be created on all realms using a single account", false)]
		public static bool ALLOW_ALL_REALMS;

		/// <summary>
		/// This will Allow/Disallow dual loggins
		/// </summary>
		[ServerProperty("system", "allow_dual_logins", "Disable to disallow players to connect with more than 1 account at a time.", true)]
		public static bool ALLOW_DUAL_LOGINS;

		/// <summary>
		/// The emote delay
		/// </summary>
		[ServerProperty("system", "emote_delay", "The emote delay, default 3000ms before another emote.", 3000)]
		public static int EMOTE_DELAY;

		/// <summary>
		/// Command spam protection delay
		/// </summary>
		[ServerProperty("system", "command_spam_delay", "The spam delay, default 1500ms before the same command can be issued again.", 1500)]
		public static int COMMAND_SPAM_DELAY;

		/// <summary>
		/// This specifies the max number of inventory items to send in an update packet
		/// </summary>
		[ServerProperty("system", "max_items_per_packet", "Max number of inventory items sent per packet.", 30)]
		public static int MAX_ITEMS_PER_PACKET;

		/// <summary>
		/// Display centered screen messages if a player enters an area.
		/// </summary>
		[ServerProperty("system", "display_area_enter_screen_desc", "Display centered screen messages if a player enters an area.", false)]
		public static bool DISPLAY_AREA_ENTER_SCREEN_DESC;

		/// <summary>
		/// Whether or not to enable the audit log
		/// </summary>
		[ServerProperty("system", "enable_audit_log", "Whether or not to enable the audit log", false)]
		public static bool ENABLE_AUDIT_LOG;
		
		/// <summary>
		/// Enable a periodic server shutdown. If you run your server into a batch loop, this performs a restart.
		/// </summary>
		[ServerProperty("system", "hours_uptime_between_shutdown", "Hours between a scheduled server shutdown (-1 = no scheduled restart)", -1)]
		public static int HOURS_UPTIME_BETWEEN_SHUTDOWN;

		/// <summary>
		/// Use the NPC Guild Scripts
		/// </summary>
		[ServerProperty("system", "use_npcguildscripts", "Use the NPC Guild Scripts", true)]
		public static bool USE_NPCGUILDSCRIPTS;

		[ServerProperty("system", "game_loop_tick_rate", "How many ticks per second the game loop tries to run at. If it can't keep up, the logic will effectively run slower than intended.", 30)]
		public static int GAME_LOOP_TICK_RATE;

		#endregion

		#region LOGGING

		/// <summary>
		/// Log All GM commands
		/// </summary>
		[ServerProperty("system", "log_all_gm_commands", "Log all GM commands on the server", false)]
		public static bool LOG_ALL_GM_COMMANDS;

		/// <summary>
		/// Should the server Log trades
		/// </summary>
		[ServerProperty("system", "log_trades", "Should the server Log all trades a player makes, values True,False", false)]
		public static bool LOG_TRADES;

		/// <summary>
		/// Log Email Addresses
		/// </summary>
		[ServerProperty("system", "log_email_addresses", "set to the email addresses you want logs automatically emailed to, multiple addresses seperate with ;", "")]
		public static string LOG_EMAIL_ADDRESSES;

		/// <summary>
		/// Enable inventory logging (trade, loot, buy, sell, quests,...)
		/// </summary>
		[ServerProperty("log", "log_inventory", "Enable inventory logging (trade, loot, buy, sell, quests,...)", false)]
		public static bool LOG_INVENTORY;

		/// <summary>
		/// Enable trade logging in inventory log (log_inventory must be enabled)
		/// </summary>
		[ServerProperty("log", "log_inventory_trade", "Enable trade logging in inventory log (log_inventory must be enabled)", true)]
		public static bool LOG_INVENTORY_TRADE;

		/// <summary>
		/// Enable craft logging in inventory log (log_inventory must be enabled)
		/// </summary>
		[ServerProperty("log", "log_inventory_craft", "Enable craft logging in inventory log (log_inventory must be enabled)", true)]
		public static bool LOG_INVENTORY_CRAFT;

		/// <summary>
		/// Enable loot logging in inventory log (log_inventory must be enabled)
		/// </summary>
		[ServerProperty("log", "log_inventory_loot", "Enable loot logging in inventory log (log_inventory must be enabled)", true)]
		public static bool LOG_INVENTORY_LOOT;

		/// <summary>
		/// Enable quest logging in inventory log (log_inventory must be enabled)
		/// </summary>
		[ServerProperty("log", "log_inventory_quest", "Enable quest logging in inventory log (log_inventory must be enabled)", true)]
		public static bool LOG_INVENTORY_QUEST;

		/// <summary>
		/// Enable merchant logging in inventory log (log_inventory must be enabled)
		/// </summary>
		[ServerProperty("log", "log_inventory_merchant", "Enable merchant logging in inventory log (log_inventory must be enabled)", true)]
		public static bool LOG_INVENTORY_MERCHANT;

		/// <summary>
		/// Enable other logging in inventory log (log_inventory must be enabled)
		/// </summary>
		[ServerProperty("log", "log_inventory_other", "Enable other logging in inventory log (log_inventory must be enabled)", true)]
		public static bool LOG_INVENTORY_OTHER;
		#endregion

		#region SERVER

		/// <summary>
		/// Enable/Disable Autokick Timer
		/// </summary>
		[ServerProperty("server", "player idle kick", "Enable auto kick for inactive players", false)]
		public static bool KICK_IDLE_PLAYER_STATUS;

		/// <summary>
		/// How long before kicking inactive player
		/// </summary>
		[ServerProperty("server", "minutes to kick", "How many minutes before kicking inactive player to char screen <Default 1hr> ", 60)]
		public static int KICK_IDLE_PLAYER_TIME;

		/// <summary>
		/// Disable quit timers for players?
		/// </summary>
		[ServerProperty("server", "disable_quit_timer", "Allow players to log out without waiting?", false)]
		public static bool DISABLE_QUIT_TIMER;

		/// <summary>
		/// Queue Service Host
		/// </summary>
		[ServerProperty("server", "queue_api_url", "Provide the URL for the queue service endpoint - blank to disable", "")]
		public static string QUEUE_API_URI;

		/// <summary>
		/// OpenAI-compatible local LLM endpoint used by WorldAI.
		/// </summary>
		[ServerProperty("worldai", "worldai_llm_api_url", "OpenAI-compatible local LLM API base URL for WorldAI.", "http://192.168.0.42:1234")]
		public static string WORLDAI_LLM_API_URL;

		/// <summary>
		/// Model id used by the OpenAI-compatible local LLM endpoint.
		/// </summary>
		[ServerProperty("worldai", "worldai_llm_model", "Model id used by WorldAI local LLM calls.", "gemma-4-e4b-it")]
		public static string WORLDAI_LLM_MODEL;

		/// <summary>
		/// Timeout for one WorldAI local LLM request.
		/// </summary>
		[ServerProperty("worldai", "worldai_llm_timeout_seconds", "Timeout in seconds for one WorldAI local LLM request.", 45)]
		public static int WORLDAI_LLM_TIMEOUT_SECONDS;

		[ServerProperty("kdaoc", "worldai_mob_growth_enabled", "KDAOC: Enable living-world monster survival growth. Keep false until ready to open this content.", false)]
		public static bool WORLDAI_MOB_GROWTH_ENABLED;

		[ServerProperty("kdaoc", "worldai_mob_growth_tick_minutes", "KDAOC: Minutes between automatic monster growth scans.", 30)]
		public static int WORLDAI_MOB_GROWTH_TICK_MINUTES;

		[ServerProperty("kdaoc", "worldai_mob_growth_survival_score", "KDAOC: Growth score added when an eligible monster survives one scan tick.", 2)]
		public static int WORLDAI_MOB_GROWTH_SURVIVAL_SCORE;

		[ServerProperty("kdaoc", "worldai_mob_growth_unhunted_score", "KDAOC: Extra growth score added when a monster has not been killed for the configured idle window.", 8)]
		public static int WORLDAI_MOB_GROWTH_UNHUNTED_SCORE;

		[ServerProperty("kdaoc", "worldai_mob_growth_combat_score", "KDAOC: Growth score added when an eligible monster survives combat contact.", 12)]
		public static int WORLDAI_MOB_GROWTH_COMBAT_SCORE;

		[ServerProperty("kdaoc", "worldai_mob_growth_combat_cooldown_seconds", "KDAOC: Minimum seconds between combat growth grants for the same monster.", 30)]
		public static int WORLDAI_MOB_GROWTH_COMBAT_COOLDOWN_SECONDS;

		[ServerProperty("kdaoc", "worldai_mob_growth_player_kill_score", "KDAOC: Growth score added when an eligible monster kills a player.", 50)]
		public static int WORLDAI_MOB_GROWTH_PLAYER_KILL_SCORE;

		[ServerProperty("kdaoc", "worldai_mob_growth_unhunted_after_minutes", "KDAOC: Minutes after which an un-killed monster also gains idle/unhunted growth.", 360)]
		public static int WORLDAI_MOB_GROWTH_UNHUNTED_AFTER_MINUTES;

		[ServerProperty("kdaoc", "worldai_mob_growth_elite_score", "KDAOC: Growth score required for Elite stage.", 60)]
		public static int WORLDAI_MOB_GROWTH_ELITE_SCORE;

		[ServerProperty("kdaoc", "worldai_mob_growth_champion_score", "KDAOC: Growth score required for Champion stage.", 180)]
		public static int WORLDAI_MOB_GROWTH_CHAMPION_SCORE;

		[ServerProperty("kdaoc", "worldai_mob_growth_boss_score", "KDAOC: Growth score required for Boss stage.", 420)]
		public static int WORLDAI_MOB_GROWTH_BOSS_SCORE;

		[ServerProperty("kdaoc", "worldai_mob_growth_max_level_bonus", "KDAOC: Maximum level bonus a grown monster can receive.", 5)]
		public static int WORLDAI_MOB_GROWTH_MAX_LEVEL_BONUS;

		[ServerProperty("kdaoc", "worldai_mob_growth_max_health_multiplier", "KDAOC: Maximum health multiplier a grown monster can receive.", 1.5)]
		public static double WORLDAI_MOB_GROWTH_MAX_HEALTH_MULTIPLIER;

		[ServerProperty("kdaoc", "worldai_mob_growth_max_active_bosses", "KDAOC: Maximum active grown bosses operators should allow before pruning or resetting.", 5)]
		public static int WORLDAI_MOB_GROWTH_MAX_ACTIVE_BOSSES;

		[ServerProperty("kdaoc", "worldai_mob_growth_max_active_bosses_per_region", "KDAOC: Maximum active grown bosses per region. 0 disables the regional cap.", 1)]
		public static int WORLDAI_MOB_GROWTH_MAX_ACTIVE_BOSSES_PER_REGION;

		[ServerProperty("kdaoc", "worldai_mob_growth_excluded_regions", "KDAOC: CSV/semicolon region IDs excluded from monster growth.", "")]
		public static string WORLDAI_MOB_GROWTH_EXCLUDED_REGIONS;

		[ServerProperty("kdaoc", "worldai_mob_growth_protected_regions", "KDAOC: CSV/semicolon region IDs protected from monster growth by default, such as tutorial or newbie regions.", "27")]
		public static string WORLDAI_MOB_GROWTH_PROTECTED_REGIONS;

		[ServerProperty("kdaoc", "worldai_mob_growth_protected_name_tokens", "KDAOC: CSV/semicolon name tokens excluded from monster growth, for quest-critical or utility NPCs.", "quest;trainer;merchant;master;훈련;상인;퀘스트")]
		public static string WORLDAI_MOB_GROWTH_PROTECTED_NAME_TOKENS;

		[ServerProperty("kdaoc", "worldai_mob_growth_minimum_eligible_level", "KDAOC: Minimum base level eligible for monster growth.", 5)]
		public static int WORLDAI_MOB_GROWTH_MINIMUM_ELIGIBLE_LEVEL;

		[ServerProperty("kdaoc", "worldai_mob_growth_low_level_max_base_level", "KDAOC: Base level at or below which monsters are capped by worldai_mob_growth_low_level_max_stage. 0 disables this cap.", 15)]
		public static int WORLDAI_MOB_GROWTH_LOW_LEVEL_MAX_BASE_LEVEL;

		[ServerProperty("kdaoc", "worldai_mob_growth_low_level_max_stage", "KDAOC: Maximum growth stage for low-level monsters. normal, elite, champion, or boss.", "Elite")]
		public static string WORLDAI_MOB_GROWTH_LOW_LEVEL_MAX_STAGE;

		[ServerProperty("kdaoc", "worldai_mob_growth_decay_enabled", "KDAOC: Enable GM-triggered stale monster growth decay cleanup.", true)]
		public static bool WORLDAI_MOB_GROWTH_DECAY_ENABLED;

		[ServerProperty("kdaoc", "worldai_mob_growth_decay_after_minutes", "KDAOC: Active grown monsters unseen for this many minutes lose growth when /mobgrowth decay runs.", 720)]
		public static int WORLDAI_MOB_GROWTH_DECAY_AFTER_MINUTES;

		[ServerProperty("kdaoc", "worldai_mob_growth_decay_score", "KDAOC: Growth score removed from stale active monsters per /mobgrowth decay run.", 60)]
		public static int WORLDAI_MOB_GROWTH_DECAY_SCORE;

		[ServerProperty("kdaoc", "worldai_mob_growth_reset_inactive_after_minutes", "KDAOC: Inactive growth rows unseen for this many minutes are deleted by /mobgrowth decay.", 10080)]
		public static int WORLDAI_MOB_GROWTH_RESET_INACTIVE_AFTER_MINUTES;

		[ServerProperty("kdaoc", "worldai_mob_growth_mutation_enabled", "KDAOC: Enable mutant monster spawns when the same monster is killed too often.", true)]
		public static bool WORLDAI_MOB_GROWTH_MUTATION_ENABLED;

		[ServerProperty("kdaoc", "worldai_mob_growth_mutation_death_window_minutes", "KDAOC: Minutes in the rolling death window used for mutant spawn checks.", 10)]
		public static int WORLDAI_MOB_GROWTH_MUTATION_DEATH_WINDOW_MINUTES;

		[ServerProperty("kdaoc", "worldai_mob_growth_mutation_death_threshold", "KDAOC: Deaths required inside the mutation window before mutation rolls start.", 5)]
		public static int WORLDAI_MOB_GROWTH_MUTATION_DEATH_THRESHOLD;

		[ServerProperty("kdaoc", "worldai_mob_growth_mutation_chance_step_percent", "KDAOC: Mutation chance added for each death at or above the threshold.", 10)]
		public static int WORLDAI_MOB_GROWTH_MUTATION_CHANCE_STEP_PERCENT;

		[ServerProperty("kdaoc", "worldai_mob_growth_mutation_max_chance_percent", "KDAOC: Maximum mutant spawn chance after repeated deaths.", 100)]
		public static int WORLDAI_MOB_GROWTH_MUTATION_MAX_CHANCE_PERCENT;

		[ServerProperty("kdaoc", "worldai_mob_growth_mutation_level_bonus", "KDAOC: Extra level bonus applied while a monster is mutant.", 2)]
		public static int WORLDAI_MOB_GROWTH_MUTATION_LEVEL_BONUS;

		[ServerProperty("kdaoc", "worldai_mob_growth_mutation_size_bonus_percent", "KDAOC: Extra size percent applied while a monster is mutant.", 15)]
		public static int WORLDAI_MOB_GROWTH_MUTATION_SIZE_BONUS_PERCENT;

		[ServerProperty("kdaoc", "worldai_mob_growth_elite_size_bonus_percent", "KDAOC: Size percent bonus for Elite grown monsters.", 10)]
		public static int WORLDAI_MOB_GROWTH_ELITE_SIZE_BONUS_PERCENT;

		[ServerProperty("kdaoc", "worldai_mob_growth_champion_size_bonus_percent", "KDAOC: Size percent bonus for Champion grown monsters.", 25)]
		public static int WORLDAI_MOB_GROWTH_CHAMPION_SIZE_BONUS_PERCENT;

		[ServerProperty("kdaoc", "worldai_mob_growth_boss_size_bonus_percent", "KDAOC: Size percent bonus for Boss grown monsters.", 45)]
		public static int WORLDAI_MOB_GROWTH_BOSS_SIZE_BONUS_PERCENT;

		[ServerProperty("kdaoc", "worldai_mob_growth_mutation_spell_pool", "KDAOC: Semicolon-separated spell IDs randomly granted to mutant monsters.", "11890;11891;11933;11934;12006;12008")]
		public static string WORLDAI_MOB_GROWTH_MUTATION_SPELL_POOL;

		[ServerProperty("kdaoc", "worldai_mob_growth_elite_spell_pool", "KDAOC: Semicolon-separated spell IDs randomly granted to Elite or higher monsters.", "11874;11892;11899;12001")]
		public static string WORLDAI_MOB_GROWTH_ELITE_SPELL_POOL;

		[ServerProperty("kdaoc", "worldai_mob_growth_champion_spell_pool", "KDAOC: Semicolon-separated spell IDs randomly granted to Champion or higher monsters.", "11893;11902;11979;12003")]
		public static string WORLDAI_MOB_GROWTH_CHAMPION_SPELL_POOL;

		[ServerProperty("kdaoc", "worldai_mob_growth_boss_spell_pool", "KDAOC: Semicolon-separated boss-style spell IDs randomly granted to Boss monsters.", "11840;11841;11842;11955;11956;11957;11958;12013")]
		public static string WORLDAI_MOB_GROWTH_BOSS_SPELL_POOL;

		[ServerProperty("kdaoc", "worldai_mob_growth_mutation_style_pool", "KDAOC: Semicolon-separated styleId|classId entries randomly granted to mutant monsters.", "103|2;247|44;240|10")]
		public static string WORLDAI_MOB_GROWTH_MUTATION_STYLE_POOL;

		[ServerProperty("kdaoc", "worldai_mob_growth_elite_style_pool", "KDAOC: Semicolon-separated styleId|classId entries randomly granted to Elite or higher monsters.", "103|2;247|44")]
		public static string WORLDAI_MOB_GROWTH_ELITE_STYLE_POOL;

		[ServerProperty("kdaoc", "worldai_mob_growth_champion_style_pool", "KDAOC: Semicolon-separated styleId|classId entries randomly granted to Champion or higher monsters.", "108|2;112|2;246|44;247|44")]
		public static string WORLDAI_MOB_GROWTH_CHAMPION_STYLE_POOL;

		[ServerProperty("kdaoc", "worldai_mob_growth_boss_style_pool", "KDAOC: Semicolon-separated boss-style styleId|classId entries randomly granted to Boss monsters.", "256|44;259|44;292|44;302|44;157|22;178|22;167|22")]
		public static string WORLDAI_MOB_GROWTH_BOSS_STYLE_POOL;

		[ServerProperty("kdaoc", "worldai_mob_growth_mutation_ability_pool", "KDAOC: Semicolon-separated abilityKey|level entries randomly granted to mutant monsters.", "Enhanced Evade|1;Tireless|1;CCImmunity|1")]
		public static string WORLDAI_MOB_GROWTH_MUTATION_ABILITY_POOL;

		[ServerProperty("kdaoc", "worldai_mob_growth_elite_ability_pool", "KDAOC: Semicolon-separated abilityKey|level entries randomly granted to Elite or higher monsters.", "Evade|1;Tireless|1")]
		public static string WORLDAI_MOB_GROWTH_ELITE_ABILITY_POOL;

		[ServerProperty("kdaoc", "worldai_mob_growth_champion_ability_pool", "KDAOC: Semicolon-separated abilityKey|level entries randomly granted to Champion or higher monsters.", "Advanced Evade|1;Stoicism|1;CCImmunity|1")]
		public static string WORLDAI_MOB_GROWTH_CHAMPION_ABILITY_POOL;

		[ServerProperty("kdaoc", "worldai_mob_growth_boss_ability_pool", "KDAOC: Semicolon-separated boss-style abilityKey|level entries randomly granted to Boss monsters.", "CCImmunity|1;Stoicism|1;Advanced Evade|1;Enhanced Evade|1")]
		public static string WORLDAI_MOB_GROWTH_BOSS_ABILITY_POOL;

		[ServerProperty("kdaoc", "kdaoc_random_item_enabled", "KDAOC: Enable global random generated item drops.", false)]
		public static bool KDAOC_RANDOM_ITEM_ENABLED;

		[ServerProperty("kdaoc", "kdaoc_random_item_suppress_existing_loot", "KDAOC: When enabled, random item loot replaces existing normal item loot generators.", false)]
		public static bool KDAOC_RANDOM_ITEM_SUPPRESS_EXISTING_LOOT;

		[ServerProperty("kdaoc", "kdaoc_random_item_exclusive_priority", "KDAOC: Exclusive loot priority used when suppressing existing loot.", 1000)]
		public static int KDAOC_RANDOM_ITEM_EXCLUSIVE_PRIORITY;

		[ServerProperty("kdaoc", "kdaoc_random_item_min_mob_level", "KDAOC: Minimum monster level eligible for random item drops.", 1)]
		public static int KDAOC_RANDOM_ITEM_MIN_MOB_LEVEL;

		[ServerProperty("kdaoc", "kdaoc_random_item_max_item_level", "KDAOC: Maximum generated random item level.", 51)]
		public static int KDAOC_RANDOM_ITEM_MAX_ITEM_LEVEL;

		[ServerProperty("kdaoc", "kdaoc_random_item_drop_grey_mobs", "KDAOC: Allow random item drops from grey-con monsters.", false)]
		public static bool KDAOC_RANDOM_ITEM_DROP_GREY_MOBS;

		[ServerProperty("kdaoc", "kdaoc_random_item_base_drop_chance", "KDAOC: Base random item drop chance for normal monsters, in percent.", 12)]
		public static int KDAOC_RANDOM_ITEM_BASE_DROP_CHANCE;

		[ServerProperty("kdaoc", "kdaoc_random_item_named_drop_bonus", "KDAOC: Extra random item drop chance for named/epic NPCs, in percent.", 20)]
		public static int KDAOC_RANDOM_ITEM_NAMED_DROP_BONUS;

		[ServerProperty("kdaoc", "kdaoc_random_item_boss_drop_bonus", "KDAOC: Extra random item drop chance for boss NPCs, in percent.", 55)]
		public static int KDAOC_RANDOM_ITEM_BOSS_DROP_BONUS;

		[ServerProperty("kdaoc", "kdaoc_random_item_normal_drop_rolls", "KDAOC: Independent random item drop rolls for normal monsters.", 1)]
		public static int KDAOC_RANDOM_ITEM_NORMAL_DROP_ROLLS;

		[ServerProperty("kdaoc", "kdaoc_random_item_named_drop_rolls", "KDAOC: Independent random item drop rolls for named/epic NPCs.", 2)]
		public static int KDAOC_RANDOM_ITEM_NAMED_DROP_ROLLS;

		[ServerProperty("kdaoc", "kdaoc_random_item_boss_drop_rolls", "KDAOC: Independent random item drop rolls for boss NPCs. Each roll uses the normal tier chance table.", 6)]
		public static int KDAOC_RANDOM_ITEM_BOSS_DROP_ROLLS;

		[ServerProperty("kdaoc", "kdaoc_random_item_boss_min_total_drops", "KDAOC: Minimum total random items from one boss kill. Missing items are filled with lower-tier drops.", 5)]
		public static int KDAOC_RANDOM_ITEM_BOSS_MIN_TOTAL_DROPS;

		[ServerProperty("kdaoc", "kdaoc_random_item_max_drop_rolls", "KDAOC: Safety cap for random item drop rolls per monster.", 12)]
		public static int KDAOC_RANDOM_ITEM_MAX_DROP_ROLLS;

		[ServerProperty("kdaoc", "kdaoc_random_item_boss_max_premium_drops", "KDAOC: Maximum Heroic-or-better random items from one boss kill. Extra premium rolls are downgraded to Rare.", 2)]
		public static int KDAOC_RANDOM_ITEM_BOSS_MAX_PREMIUM_DROPS;

		[ServerProperty("kdaoc", "kdaoc_random_item_boss_title_min_level", "KDAOC: Minimum NPC level for title-based random-item boss detection.", 55)]
		public static int KDAOC_RANDOM_ITEM_BOSS_TITLE_MIN_LEVEL;

		[ServerProperty("kdaoc", "kdaoc_random_item_boss_title_tokens", "KDAOC: Semicolon-separated title words that make high-level DB NPCs count as random-item bosses.", "lord;lady;king;queen;prince;princess;dragon;giant;chief;chieftain;commander;baron;duke;duchess;emperor;empress;archon;overlord")]
		public static string KDAOC_RANDOM_ITEM_BOSS_TITLE_TOKENS;

		[ServerProperty("kdaoc", "kdaoc_random_item_min_level_offset", "KDAOC: Minimum level offset applied to generated random items.", -2)]
		public static int KDAOC_RANDOM_ITEM_MIN_LEVEL_OFFSET;

		[ServerProperty("kdaoc", "kdaoc_random_item_max_level_offset", "KDAOC: Maximum level offset applied to generated random items.", 1)]
		public static int KDAOC_RANDOM_ITEM_MAX_LEVEL_OFFSET;

		[ServerProperty("kdaoc", "kdaoc_random_item_named_level_bonus", "KDAOC: Additional generated item level bonus for named/epic NPCs.", 2)]
		public static int KDAOC_RANDOM_ITEM_NAMED_LEVEL_BONUS;

		[ServerProperty("kdaoc", "kdaoc_random_item_boss_level_bonus", "KDAOC: Additional generated item level bonus for boss NPCs.", 4)]
		public static int KDAOC_RANDOM_ITEM_BOSS_LEVEL_BONUS;

		[ServerProperty("kdaoc", "kdaoc_random_item_max_generation_attempts", "KDAOC: Maximum attempts to generate a safe random item before dropping nothing.", 5)]
		public static int KDAOC_RANDOM_ITEM_MAX_GENERATION_ATTEMPTS;

		[ServerProperty("kdaoc", "kdaoc_dragon_ball_enabled", "KDAOC: Enable rare Dragon Ball collection drops from monster kills.", true)]
		public static bool KDAOC_DRAGON_BALL_ENABLED;

		[ServerProperty("kdaoc", "kdaoc_dragon_ball_drop_chance_per_million", "KDAOC: Dragon Ball drop chance per eligible monster kill, in one-millionths. 250 means 0.025%.", 250)]
		public static int KDAOC_DRAGON_BALL_DROP_CHANCE_PER_MILLION;

		[ServerProperty("kdaoc", "kdaoc_dragon_ball_min_mob_level", "KDAOC: Minimum monster level eligible for Dragon Ball drops.", 5)]
		public static int KDAOC_DRAGON_BALL_MIN_MOB_LEVEL;

		[ServerProperty("kdaoc", "kdaoc_dragon_ball_summon_dragon_model", "KDAOC: NPC model used for the temporary Dragon Ball summon dragon.", 2383)]
		public static int KDAOC_DRAGON_BALL_SUMMON_DRAGON_MODEL;

		[ServerProperty("kdaoc", "kdaoc_dragon_ball_summon_dragon_size", "KDAOC: NPC size used for the temporary Dragon Ball summon dragon.", 180)]
		public static int KDAOC_DRAGON_BALL_SUMMON_DRAGON_SIZE;

		[ServerProperty("kdaoc", "kdaoc_dragon_ball_summon_duration_seconds", "KDAOC: Seconds the temporary Dragon Ball summon dragon remains visible for wish presentation.", 300)]
		public static int KDAOC_DRAGON_BALL_SUMMON_DURATION_SECONDS;

		[ServerProperty("kdaoc", "kdaoc_dragon_ball_summon_weather_enabled", "KDAOC: Start temporary foggy weather during Dragon Ball summon when the region has no active weather.", true)]
		public static bool KDAOC_DRAGON_BALL_SUMMON_WEATHER_ENABLED;

		[ServerProperty("kdaoc", "kdaoc_dragon_ball_summon_effect", "KDAOC: Client spell effect id played during Dragon Ball summon.", 4074)]
		public static int KDAOC_DRAGON_BALL_SUMMON_EFFECT;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_enabled", "KDAOC: Enable dynamic quest offers, graph progress, and runtime world bindings.", false)]
		public static bool KDAOC_DYNAMIC_QUEST_ENABLED;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_max_active_per_player", "KDAOC: Maximum active in-memory dynamic quests per player.", 1)]
		public static int KDAOC_DYNAMIC_QUEST_MAX_ACTIVE_PER_PLAYER;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_max_active_per_npc", "KDAOC: Maximum active in-memory dynamic quest offers per NPC.", 1)]
		public static int KDAOC_DYNAMIC_QUEST_MAX_ACTIVE_PER_NPC;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_max_kill_count", "KDAOC: Maximum kill target count allowed for one dynamic quest.", 20)]
		public static int KDAOC_DYNAMIC_QUEST_MAX_KILL_COUNT;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_reward_xp_multiplier", "KDAOC: XP multiplier for volatile dynamic quest completion.", 1.0)]
		public static double KDAOC_DYNAMIC_QUEST_REWARD_XP_MULTIPLIER;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_reward_money_multiplier", "KDAOC: Money multiplier for volatile dynamic quest completion.", 1.0)]
		public static double KDAOC_DYNAMIC_QUEST_REWARD_MONEY_MULTIPLIER;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_auto_seed_enabled", "KDAOC: Automatically seed dynamic quest offers from configured story templates and current world NPCs.", false)]
		public static bool KDAOC_DYNAMIC_QUEST_AUTO_SEED_ENABLED;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_auto_seed_tick_minutes", "KDAOC: Minutes between automatic dynamic quest seed checks.", 30)]
		public static int KDAOC_DYNAMIC_QUEST_AUTO_SEED_TICK_MINUTES;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_auto_seed_max_quests", "KDAOC: Maximum dynamic quest offers created by one automatic seed pass.", 3)]
		public static int KDAOC_DYNAMIC_QUEST_AUTO_SEED_MAX_QUESTS;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_auto_seed_definitions", "KDAOC: Semicolon-separated deterministic dynamic quest story hints: StartNpcNameOrSelector|RegionId|TargetNameOrSelector|Count|MinLevel|MaxLevel|StartMode|Trigger|BranchWorldSignal.", "selector:town-npc|1|selector:hostile-near-start|1|1|5|NpcOffer||mob-growth:killed:region:1;selector:town-npc|100|selector:hostile-near-start|1|1|5|NpcOffer||time-window:night;selector:town-npc|200|selector:hostile-near-start|1|1|5|NpcOffer||item-acquired")]
		public static string KDAOC_DYNAMIC_QUEST_AUTO_SEED_DEFINITIONS;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_world_revision", "KDAOC: Dynamic quest world/lore revision. Change this value to cancel stale dynamic quest progress and rebind volatile quest offers.", "default")]
		public static string KDAOC_DYNAMIC_QUEST_WORLD_REVISION;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_auto_seed_use_llm", "KDAOC: Use LLM quest generation for automatic dynamic quest seeds instead of deterministic text.", false)]
		public static bool KDAOC_DYNAMIC_QUEST_AUTO_SEED_USE_LLM;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_auto_seed_llm_seed", "KDAOC: LLM prompt seed suffix used when automatic dynamic quest LLM generation is enabled.", "지역 분위기에 맞는 짧은 처치 의뢰")]
		public static string KDAOC_DYNAMIC_QUEST_AUTO_SEED_LLM_SEED;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_provider_order", "KDAOC: Dynamic quest story provider fallback order. Supported aliases: openai, main-local, gemini, secondary-local.", "openai,main-local,secondary-local")]
		public static string KDAOC_DYNAMIC_QUEST_STORY_PROVIDER_ORDER;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_minimum_score", "KDAOC: Minimum evaluated quality score accepted for generated dynamic quest stories before trying the next provider.", 50)]
		public static int KDAOC_DYNAMIC_QUEST_STORY_MINIMUM_SCORE;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_compare_providers_enabled", "KDAOC: Generate comparison candidates from multiple story providers before choosing a dynamic quest story. Disabled by default to protect API quota.", false)]
		public static bool KDAOC_DYNAMIC_QUEST_STORY_COMPARE_PROVIDERS_ENABLED;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_compare_max_per_prefill", "KDAOC: Maximum story provider comparison candidates generated per prefill item when provider comparison is enabled.", 2)]
		public static int KDAOC_DYNAMIC_QUEST_STORY_COMPARE_MAX_PER_PREFILL;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_cache_max_templates", "KDAOC: Maximum active generated dynamic quest story templates kept in DB before daily low-score pruning.", 500)]
		public static int KDAOC_DYNAMIC_QUEST_STORY_CACHE_MAX_TEMPLATES;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_cache_prune_count", "KDAOC: Number of low-score generated story templates pruned once per day when the story cache is full.", 50)]
		public static int KDAOC_DYNAMIC_QUEST_STORY_CACHE_PRUNE_COUNT;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_cache_prefill_batch_size", "KDAOC: Maximum generated dynamic quest story templates to prefill per seed pass.", 5)]
		public static int KDAOC_DYNAMIC_QUEST_STORY_CACHE_PREFILL_BATCH_SIZE;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_cache_world_prefill_enabled", "KDAOC: Derive extra generated dynamic quest story cache candidates from current world NPC and monster data.", true)]
		public static bool KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_ENABLED;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_cache_world_prefill_max_candidates", "KDAOC: Maximum extra current-world dynamic quest story candidates considered per seed pass.", 60)]
		public static int KDAOC_DYNAMIC_QUEST_STORY_CACHE_WORLD_PREFILL_MAX_CANDIDATES;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_cache_offer_enabled", "KDAOC: Promote cached generated dynamic quest stories into live offers when automatic seed slots remain.", true)]
		public static bool KDAOC_DYNAMIC_QUEST_STORY_CACHE_OFFER_ENABLED;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_cache_offer_min_slots", "KDAOC: Minimum automatic seed slots reserved for cached story offers when LLM quest generation and cache offers are enabled.", 3)]
		public static int KDAOC_DYNAMIC_QUEST_STORY_CACHE_OFFER_MIN_SLOTS;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_cache_require_dummy_evaluation_for_offers", "KDAOC: Only promote story cache rows with a passing dummy-client evaluation into live dynamic quest offers. Enabled by default for production safety; disable only while intentionally building evaluation coverage.", true)]
		public static bool KDAOC_DYNAMIC_QUEST_STORY_CACHE_REQUIRE_DUMMY_EVALUATION_FOR_OFFERS;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_dummy_evaluation_enabled", "KDAOC: Accept dummy-client dynamic quest evaluation scores and prune failed story cache rows.", true)]
		public static bool KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_ENABLED;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_dummy_evaluation_min_score", "KDAOC: Minimum dummy-client evaluation score required to keep a dynamic quest story cache row active.", 70)]
		public static int KDAOC_DYNAMIC_QUEST_DUMMY_EVALUATION_MIN_SCORE;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_cinematic_max_actors_per_action", "KDAOC: Maximum temporary NPC actors one dynamic quest cinematic action may spawn. Missing, non-positive, or legacy default 8 values fall back to 100; values above 100 are clamped.", 100)]
		public static int KDAOC_DYNAMIC_QUEST_CINEMATIC_MAX_ACTORS_PER_ACTION;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_secondary_llm_api_url", "KDAOC: Secondary OpenAI-compatible local LLM API base URL for dynamic quest story fallback.", "http://192.168.0.28:8001")]
		public static string KDAOC_DYNAMIC_QUEST_STORY_SECONDARY_LLM_API_URL;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_secondary_llm_model", "KDAOC: Secondary OpenAI-compatible local LLM model id for dynamic quest story fallback.", "local-gemma-4-e4b-it")]
		public static string KDAOC_DYNAMIC_QUEST_STORY_SECONDARY_LLM_MODEL;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_openai_model", "KDAOC: OpenAI model id used for premium dynamic quest story generation.", "gpt-5.4")]
		public static string KDAOC_DYNAMIC_QUEST_STORY_OPENAI_MODEL;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_openai_per_minute_limit", "KDAOC: Maximum OpenAI dynamic quest story calls per server minute.", 2)]
		public static int KDAOC_DYNAMIC_QUEST_STORY_OPENAI_PER_MINUTE_LIMIT;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_openai_daily_limit", "KDAOC: Maximum OpenAI dynamic quest story calls per server day.", 5)]
		public static int KDAOC_DYNAMIC_QUEST_STORY_OPENAI_DAILY_LIMIT;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_openai_daily_token_limit", "KDAOC: Maximum OpenAI dynamic quest story tokens reserved per server day.", 500000)]
		public static int KDAOC_DYNAMIC_QUEST_STORY_OPENAI_DAILY_TOKEN_LIMIT;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_gemini_model", "KDAOC: Gemini model id used as cloud fallback for dynamic quest story generation.", "gemini-3.5-flash")]
		public static string KDAOC_DYNAMIC_QUEST_STORY_GEMINI_MODEL;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_gemini_per_minute_limit", "KDAOC: Maximum Gemini dynamic quest story calls per server minute. Keep below provider quota. Set 0 to disable Gemini calls.", 0)]
		public static int KDAOC_DYNAMIC_QUEST_STORY_GEMINI_PER_MINUTE_LIMIT;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_gemini_daily_limit", "KDAOC: Maximum Gemini dynamic quest story calls per server day. Keep below provider quota. Set 0 to disable Gemini calls.", 0)]
		public static int KDAOC_DYNAMIC_QUEST_STORY_GEMINI_DAILY_LIMIT;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_gemini_daily_token_limit", "KDAOC: Maximum Gemini dynamic quest story tokens reserved per server day. Set 0 to disable Gemini token spend.", 0)]
		public static int KDAOC_DYNAMIC_QUEST_STORY_GEMINI_DAILY_TOKEN_LIMIT;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_gemini_reset_delay_minutes", "KDAOC: Minutes after Gemini RPD reset at midnight Pacific Time before pruning and refilling generated quest stories.", 10)]
		public static int KDAOC_DYNAMIC_QUEST_STORY_GEMINI_RESET_DELAY_MINUTES;

		[ServerProperty("kdaoc", "kdaoc_dynamic_quest_story_gemini_reset_window_minutes", "KDAOC: Minutes after the reset delay during which generated quest story pruning/refill may use fresh Gemini daily quota.", 360)]
		public static int KDAOC_DYNAMIC_QUEST_STORY_GEMINI_RESET_WINDOW_MINUTES;

		[ServerProperty("companion", "dummy_companion_dialogue_enabled", "Enable AI-driven dialogue for live companion service.", false)]
		public static bool DUMMY_COMPANION_DIALOGUE_ENABLED;

		/// <summary>
		/// Enable Discord Webhook?
		/// </summary>
		[ServerProperty("server", "Discord_Webhook_Active", "Enable Discord webhook?", false)]
		public static bool DISCORD_ACTIVE;

		/// <summary>
		/// Webhook ID
		/// </summary>
		[ServerProperty("server", "Discord_Webhook_ID", "The id of the webhook", "")]
		public static string DISCORD_WEBHOOK_ID;
		
		/// <summary>
		/// RvRWebhook ID
		/// </summary>
		[ServerProperty("atlas", "Discord_RVR_Webhook_ID", "The id of the webhook for RvR updates", "")]
		public static string DISCORD_RVR_WEBHOOK_ID;

		/// <summary>
		/// RvRWebhook ID
		/// </summary>
		[ServerProperty("atlas", "Discord_AlbChat_Webhook_ID", "The id of the webhook for all Albion chat", "")]
		public static string DISCORD_ALBCHAT_WEBHOOK_ID;

		/// <summary>
		/// RvRWebhook ID
		/// </summary>
		[ServerProperty("atlas", "Discord_HibChat_Webhook_ID", "The id of the webhook for Hibernia chat", "")]
		public static string DISCORD_HIBCHAT_WEBHOOK_ID;

		/// <summary>
		/// RvRWebhook ID
		/// </summary>
		[ServerProperty("atlas", "Discord_MidChat_Webhook_ID", "The id of the webhook for Midgard chat", "")]
		public static string DISCORD_MIDCHAT_WEBHOOK_ID;

		/// <summary>
		/// Tester Role
		/// </summary>
		[ServerProperty("atlas", "tester_login", "Allow only testers and staff to login", false)]
		public static bool TESTER_LOGIN;

		/// <summary>
		/// The slowmode duration for /advice in seconds
		/// </summary>
		[ServerProperty("atlas", "advice_slowmode_length", "The slowmode duration for /advice in seconds", 60)]
		public static int ADVICE_SLOWMODE_LENGTH;

		/// <summary>
		/// The slowmode duration for /trade in seconds
		/// </summary>
		[ServerProperty("atlas", "trade_slowmode_length", "The slowmode duration for /trade in seconds", 60)]
		public static int TRADE_SLOWMODE_LENGTH;

		/// <summary>
		/// The slowmode duration for /lfg in seconds
		/// </summary>
		[ServerProperty("atlas", "lfg_slowmode_length", "The slowmode duration for /lfg in seconds", 60)]
		public static int LFG_SLOWMODE_LENGTH;

		/// <summary>
		/// The first factor in the PVE mob damage equation. Lower hits harder.
		/// </summary>
		[ServerProperty("atlas", "pve_mob_damage_f1", "The first factor in the PVE mob damage equation. Lower hits harder.", 3.2)]
		public static double PVE_MOB_DAMAGE_F1;

		/// <summary>
		/// The second factor in the PVE mob damage equation. Lower hits harder.
		/// </summary>
		[ServerProperty("atlas", "pve_mob_damage_f2", "The second factor in the PVE mob damage equation. Lower hits harder.", 150.0)]
		public static double PVE_MOB_DAMAGE_F2;

		/// <summary>
		/// Enable integrated serverlistupdate script?
		/// </summary>
		[ServerProperty("server", "serverlistupdate_enabled", "Enable in-built serverlistupdate script?", false)]
		public static bool SERVERLISTUPDATE_ENABLED;

		/// <summary>
		/// The username for server list update.
		/// </summary>
		[ServerProperty("server", "serverlistupdate_user", "Username for serverlistupdate.", "")]
		public static string SERVER_LIST_UPDATE_USER;

		/// <summary>
		/// The password for server list update.
		/// </summary>
		[ServerProperty("server", "serverlistupdate_password", "Password for serverlistupdate.", "")]
		public static string SERVER_LIST_UPDATE_PASS;

		/// <summary>
		/// Post 1.108 Passive RA 9-Tiers
		/// </summary>
		[ServerProperty("server", "use_new_passives_ras_scaling", "Use new passives realmabilities scaling (1.108+) ?", false)]
		public static bool USE_NEW_PASSIVES_RAS_SCALING;

		/// <summary>
		/// Post 1.108 Active RA 5-Tiers
		/// </summary>
		[ServerProperty("server", "use_new_actives_ras_scaling", "Use new actives realmabilities (5-Tiers) scaling (1.108+) ?", false)]
		public static bool USE_NEW_ACTIVES_RAS_SCALING;

		/// <summary>
		/// Use pre 1.105 train or livelike
		/// </summary>
		[ServerProperty("server", "custom_train", "Train is custom pre-1.105 one ? (false set it to livelike 1.105+)", true)]
		public static bool CUSTOM_TRAIN;

		/// <summary>
		/// Record news in database
		/// </summary>
		[ServerProperty("server", "record_news", "Record News in database?", true)]
		public static bool RECORD_NEWS;

		/// <summary>
		/// The Server Message of the Day
		/// </summary>
		[ServerProperty("server", "motd", "The Server Message of the Day - Edit this to set what is displayed when a level 2+ character enters the game for the first time, set to \"\" for nothing", "Welcome to a Dawn of Light server, please edit this MOTD")]
		public static string MOTD;

		/// <summary>
		/// The message players get when they enter the game past level 1
		/// </summary>
		[ServerProperty("server", "starting_msg", "The Starting Mesage - Edit this to set what is displayed when a level 1 character enters the game for the first time, set to \"\" for nothing", "Welcome for your first time to a Dawn of Light server, please edit this Starter Message")]
		public static string STARTING_MSG;

		/// <summary>
		/// The broadcast type
		/// </summary>
		[ServerProperty("server", "broadcast_type", "Broadcast Type - Edit this to change what /b does, values 0 = disabled, 1 = area, 2 = visibility distance, 3 = zone, 4 = region, 5 = realm, 6 = server", 1)]
		public static int BROADCAST_TYPE;

		/// <summary>
		/// Anon Modifier
		/// </summary>
		[ServerProperty("server", "anon_modifier", "Various modifying options for anon, 0 = default, 1 = /who shows player but as ANON, -1 = disabled", 0)]
		public static int ANON_MODIFIER;

		/// <summary>
		/// Death Messages All Realms
		/// </summary>
		[ServerProperty("server", "death_messages_all_realms", "Set to true if you want all realms to see other realms death and kill messages", false)]
		public static bool DEATH_MESSAGES_ALL_REALMS;

		/// <summary>
		/// Disable Instances
		/// </summary>
		[ServerProperty("server", "disable_instances", "Enable or disable instances on the server", false)]
		public static bool DISABLE_INSTANCES;

		/// <summary>
		/// Save QuestItems into Database
		/// </summary>
		[ServerProperty("server", "save_quest_mobs_into_database", "set false if you don't want this", true)]
		public static bool SAVE_QUEST_MOBS_INTO_DATABASE;

		/// <summary>
		/// This specifies the max amount of people in one battlegroup.
		/// </summary>
		[ServerProperty("server", "battlegroup_max_member", "Max number of members allowed in a battlegroup.", 64)]
		public static int BATTLEGROUP_MAX_MEMBER;

		/// <summary>
		///  This specifies the max amount of people in one group.
		/// </summary>
		[ServerProperty("server", "group_max_member", "Max number of members allowed in a group.", 8)]
		public static int GROUP_MAX_MEMBER;

		/// <summary>
		/// Sets the disabled commands for the server split by ;
		/// </summary>
		[ServerProperty("server", "disabled_commands", "Serialized list of disabled commands separated by semi-colon, example /realm;/toon;/quit", "")]
		public static string DISABLED_COMMANDS;

		/// <summary>
		/// Disable Appeal System
		/// </summary>
		[ServerProperty("server", "disable_appeal_system", "Disable the /Appeal System", false)]
		public static bool DISABLE_APPEALSYSTEM;

		/// <summary>
		/// Use Database Language datas instead of files (if empty = build the table from files)
		/// </summary>
		[ServerProperty("server", "use_dblanguage", "Use Database Language datas instead of files (if empty = build the table from files)", false)]
		public static bool USE_DBLANGUAGE;

		/// <summary>
		/// Update existing rows within the LanguageSystem table from language files.
		/// </summary>
		[ServerProperty("server", "update_existing_db_system_sentences_from_files", "Update existing rows within the LanguageSystem table from language files.", false)]
		public static bool UPDATE_EXISTING_DB_SYSTEM_SENTENCES_FROM_FILES;

		/// <summary>
		/// Set the maximum number of objects allowed in a region.  Smaller numbers offer better performance.  This is used to allocate arrays for both Regions and GamePlayers
		/// </summary>
		[ServerProperty("server", "region_max_objects", "Set the maximum number of objects allowed in a region.  Smaller numbers offer better performance.  This can't be changed while the server is running. (256 - 65535)", (ushort)30000)]
		public static ushort REGION_MAX_OBJECTS;

		/// <summary>
		/// Show logins
		/// </summary>
		[ServerProperty("server", "show_logins", "Show login messages when players log in and out of game?", true)]
		public static bool SHOW_LOGINS;

		/// <summary>
		/// Show logins channel
		/// </summary>
		[ServerProperty("server", "show_logins_channel", "What channel should be used for login messages? See eChatType, default is System.", (byte)0)]
		public static byte SHOW_LOGINS_CHANNEL;

		/// <summary>
		/// Enable PvE Speed
		/// </summary>
		[ServerProperty("server", "enable_pve_speed", "Set to true if you wish to enable the extra 25% increase to speed when not in combat or an RvR zone", false)]
		public static bool ENABLE_PVE_SPEED;

		/// <summary>
		/// Enable Encumberance Speed loss
		/// </summary>
		[ServerProperty("server", "enable_encumberance_speed_loss", "Set to true if you wish to enable the encumberance speed loss", true)]
		public static bool ENABLE_ENCUMBERANCE_SPEED_LOSS;

		/// <summary>
		/// Property to enable "forced" Tooltip send when Update are made to player skills, or player effects.
		/// </summary>
		[ServerProperty("server", "use_new_tooltip_forcedupdate", "Set to true if you wish to enable the new 1.110+ Tooltip Forced update each time the server send a skill to a new client.", true)]
		public static bool USE_NEW_TOOLTIP_FORCEDUPDATE;

		/// <summary>
		/// Property to enable crush/slash/thrust determining damage variance for polearms and 2H weapons
		/// </summary>
		[ServerProperty("server", "enable_albion_advanced_weapon_spec", "Set to true to determine damage variance for polearms and 2H weapons on 1H crush/slash/thrust spec.", true)]
		public static bool ENABLE_ALBION_ADVANCED_WEAPON_SPEC;
		
		/// <summary>
		/// Property to enable free respecs
		/// </summary>
		[ServerProperty("server", "free_respec", "Set to true to always allow respecs", false)]
		public static bool FREE_RESPEC;
		#endregion

		#region WORLD
		/// <summary>
		/// Epic encounters strength: 100 is 100% base strength
		/// </summary>
		[ServerProperty("world", "set_difficulty_on_epic_encounters", "Tune encounters taggued <Epic Encounter>. 0 means auto adaptative, others values are % of the initial difficulty (100%=initial difficulty)", 100)]
		public static int SET_DIFFICULTY_ON_EPIC_ENCOUNTERS;

		/// <summary>
		/// A serialised list of disabled RegionIDs
		/// </summary>
		[ServerProperty("world", "disabled_regions", "Serialized list of disabled region IDs, separated by semi-colon or a range with a dash (ie 1-5;7;9)", "")]
		public static string DISABLED_REGIONS = string.Empty;

		/// <summary>
		/// Should the server disable the tutorial zone
		/// </summary>
		[ServerProperty("world", "disable_tutorial", "should the server disable the tutorial zone", false)]
		public static bool DISABLE_TUTORIAL;

		[ServerProperty("world", "world_item_decay_time", "How long (milliseconds) will an item dropped on the ground stay in the world.", (uint) 180000)]
		public static uint WORLD_ITEM_DECAY_TIME;

		[ServerProperty("world", "world_pickup_distance", "How far before you can no longer pick up an object (loot for example).", 256)]
		public static int WORLD_PICKUP_DISTANCE;

		[ServerProperty("world", "world_day_increment", "Larger increments make shorter days. Because night time is 25% faster, it should ideally be a multiple of 4.", (uint) 24)]
		public static uint WORLD_DAY_INCREMENT;

		[ServerProperty("world", "world_npc_update_interval", "How often (milliseconds) will npc's broadcast updates to the clients.", (uint) 5000)]
		public static uint WORLD_NPC_UPDATE_INTERVAL;

		[ServerProperty("world", "world_object_update_interval", "How often (milliseconds) will objects (static, housing, doors) broadcast updates to the clients.", (uint) 30000)]
		public static uint WORLD_OBJECT_UPDATE_INTERVAL;

		[ServerProperty("world", "world_player_update_interval", "How often (milliseconds) will players be checked for updates.", (uint) 1000)]
		public static uint WORLD_PLAYER_UPDATE_INTERVAL;

		[ServerProperty("world", "weather_check_interval", "How often (milliseconds) will weather be checked for a chance to start a storm.", 5 * 60 * 1000)]
		public static int WEATHER_CHECK_INTERVAL;

		[ServerProperty("world", "weather_chance", "What is the chance of starting a storm.", 5)]
		public static int WEATHER_CHANCE;

		[ServerProperty("world", "weather_log_events", "Should weather events be shown in the Log (and on the console).", true)]
		public static bool WEATHER_LOG_EVENTS;

		[ServerProperty("world", "check_los_before_aggro", "Should we perform LoS checks before allowing standard NPCs to aggro from proximity.", true)]
		public static bool CHECK_LOS_BEFORE_AGGRO;

		[ServerProperty("world", "check_los_before_aggro_fnf", "Should we perform LoS checks before allowing FnF turrets to aggro from proximity. If false, they will attempt to cast behind walls.", true)]
		public static bool CHECK_LOS_BEFORE_AGGRO_FNF;

		[ServerProperty("world", "check_los_before_npc_ranged_attack", "Should we perform LoS checks before allowing archer NPCs to attack.", true)]
		public static bool CHECK_LOS_BEFORE_NPC_RANGED_ATTACK;

		[ServerProperty("world", "check_los_during_ranged_attack_minimum_interval", "The minimum interval (milliseconds) between two LoS checks performed during a ranged attack.", 200)]
		public static int CHECK_LOS_DURING_RANGED_ATTACK_MINIMUM_INTERVAL;

		[ServerProperty("world", "check_los_during_cast", "Should we perform LoS checks during spell casts.", true)]
		public static bool CHECK_LOS_DURING_CAST;

		[ServerProperty("world", "check_los_during_cast_minimum_interval", "The minimum interval (milliseconds) between two LoS checks performed during a spell cast.", 200)]
		public static int CHECK_LOS_DURING_CAST_MINIMUM_INTERVAL;

		[ServerProperty("world", "los_check_timeout", "After how long (milliseconds) should a los check timeout. If less than 0, the default ECS timer interval will be used.", 1500)]
		public static int LOS_CHECK_TIMEOUT;

		/// <summary>
		/// HPs gained per champion's level
		/// </summary>
		[ServerProperty("world", "hps_per_championlevel", "The amount of extra HPs gained each time you reach a new Champion's Level", 40)]
		public static int HPS_PER_CHAMPIONLEVEL;

		/// <summary>
		/// Time player must wait after failed task
		/// </summary>
		[ServerProperty("world", "task_pause_ticks", "Time player must wait after failed task check to get new chance for a task, in milliseconds", 5 * 60 * 1000)]
		public static int TASK_PAUSE_TICKS;

		/// <summary>
		/// Should we handle tasks with items
		/// </summary>
		[ServerProperty("world", "task_give_random_item", "Task is also rewarded with ROG ?", false)]
		public static bool TASK_GIVE_RANDOM_ITEM;

		/// <summary>
		/// Should we enable Zone Bonuses?
		/// </summary>
		[ServerProperty("world", "enable_zone_bonuses", "Are Zone Bonuses Enabled?", false)]
		public static bool ENABLE_ZONE_BONUSES;

		/// <summary>
		/// List of ZoneId where personnal mount is allowed
		/// </summary>
		[ServerProperty("world", "allow_personnal_mount_in_regions", "CSV Regions where player mount is allowed", "")]
		public static string ALLOW_PERSONNAL_MOUNT_IN_REGIONS;

		/// <summary>
		/// Display the zonepoint with a choosen model
		/// </summary>
		[ServerProperty("world", "zonepoint_npctemplate", "Display the zonepoint with the following npctemplate. 0 for no display", 0)]
		public static int ZONEPOINT_NPCTEMPLATE;
		#endregion

		#region RATES
		/// <summary>
		/// Xp Cap for a player.  Given in percent of level.  Default is 125%
		/// </summary>
		[ServerProperty("rates", "XP_Cap_Percent", "Maximum XP a player can earn given in percent of their level. Default is 125%", 125)]
		public static int XP_CAP_PERCENT;

		/// <summary>
		/// Xp Cap for a player vs player kill.  Given in percent of level.  Default is 125%
		/// </summary>
		[ServerProperty("rates", "XP_PVP_Cap_Percent", "Maximum XP a player can earn killing another player, given in percent of their level. Default is 125%", 125)]
		public static int XP_PVP_CAP_PERCENT;

		/// <summary>
		/// The Experience Rate
		/// </summary>
		[ServerProperty("rates", "xp_rate", "The Experience Points Rate Modifier - Edit this to change the rate at which you gain experience points e.g 1.5 is 50% more 2.0 is twice the amount (100%) 0.5 is half the amount (50%)", 1.0)]
		public static double XP_RATE;

		/// <summary>
		/// The CL Experience Rate
		/// </summary>
		[ServerProperty("rates", "cl_xp_rate", "The Champion Level Experience Points Rate Modifier - Edit this to change the rate at which you gain CL experience points e.g 1.5 is 50% more 2.0 is twice the amount (100%) 0.5 is half the amount (50%)", 1.0)]
		public static double CL_XP_RATE;

		/// <summary>
		/// RvR Zones XP Rate
		/// </summary>
		[ServerProperty("rates", "rvr_zones_xp_rate", "The RvR zones Experience Points Rate Modifier", 1.0)]
		public static double RvR_XP_RATE;

		/// <summary>
		/// The Realm Points Rate
		/// </summary>
		[ServerProperty("rates", "rp_rate", "The Realm Points Rate Modifier - Edit this to change the rate at which you gain realm points e.g 1.5 is 50% more 2.0 is twice the amount (100%) 0.5 is half the amount (50%)", 1.0)]
		public static double RP_RATE;

		/// <summary>
		/// The Bounty Points Rate
		/// </summary>
		[ServerProperty("rates", "bp_rate", "The Bounty Points Rate Modifier - Edit this to change the rate at which you gain bounty points e.g 1.5 is 50% more 2.0 is twice the amount (100%) 0.5 is half the amount (50%)", 1.0)]
		public static double BP_RATE;

		/// <summary>
		/// The damage players do against monsters with melee
		/// </summary>
		[ServerProperty("rates", "pve_melee_damage", "The PvE Melee Damage Modifier - Edit this to change the amount of melee damage done when fighting mobs e.g 1.5 is 50% more damage 2.0 is twice the damage (100%) 0.5 is half the damage (50%)", 1.0)]
		public static double PVE_MELEE_DAMAGE;

		/// <summary>
		/// The damage players do against monsters with spells
		/// </summary>
		[ServerProperty("rates", "pve_spell_damage", "The PvE Spell Damage Modifier - Edit this to change the amount of spell damage done when fighting mobs e.g 1.5 is 50% more damage 2.0 is twice the damage (100%) 0.5 is half the damage (50%)", 1.0)]
		public static double PVE_SPELL_DAMAGE = 1.0;

		/// <summary>
		/// The damage players do against players with melee
		/// </summary>
		[ServerProperty("rates", "pvp_melee_damage", "The PvP Melee Damage Modifier - Edit this to change the amount of melee damage done when fighting players e.g 1.5 is 50% more damage 2.0 is twice the damage (100%) 0.5 is half the damage (50%)", 1.0)]
		public static double PVP_MELEE_DAMAGE;

		/// <summary>
		/// The damage players do against players with spells
		/// </summary>
		[ServerProperty("rates", "pvp_spell_damage", "The PvP Spell Damage Modifier - Edit this to change the amount of spell damage done when fighting players e.g 1.5 is 50% more damage 2.0 is twice the damage (100%) 0.5 is half the damage (50%)", 1.0)]
		public static double PVP_SPELL_DAMAGE;

		/// <summary>
		/// The % value of gainrps when heal a players recently damaged in rvr.
		/// </summary>
		[ServerProperty("rates", "heal_pvp_damage_value_rp", "How many % of heal final value is obtained in rps?", 8)]
		public static int HEAL_PVP_DAMAGE_VALUE_RP;

		/// <summary>
		/// The highest possible Block Rate against an Enemy (Hard Cap)
		/// </summary>
		[ServerProperty("rates", "block_cap", "Block Rate Cap Modifier - Edit this to change the highest possible block rate against an enemy (Hard Cap) in game e.g .60 = 60%", 1.00)]
		public static double BLOCK_CAP;

		///<summary>
		/// The highest possible Evade Rate against an Enemy (Hard Cap)
		/// </summary>
		[ServerProperty("rates", "evade_cap", "Evade Rate Cap Modifier - Edit this to change the highest possible evade rate against an enemy (Hard Cap) in game e.g .50 = 50%", 0.50)]
		public static double EVADE_CAP;

		///<summary>
		///The highest possible Parry Rate against an Enemy (Hard Cap)
		/// </summary>
		[ServerProperty("rates", "parry_cap", "Parry Rate Cap Modifier - Edit this to change the highest possible parry rate against an enemy (Hard Cap) in game e.g .50 = 50%", 0.50)]
		public static double PARRY_CAP;

		/// <summary>
		/// The money drop modifier
		/// </summary>
		[ServerProperty("rates", "money_drop", "Money Drop Modifier - Edit this to change the amount of money which is dropped e.g 1.5 is 50% more 2.0 is twice the amount (100%) 0.5 is half the amount (50%)", 1.0)]
		public static double MONEY_DROP;
		
		/// <summary>
		/// The small chest drop chance
		/// </summary>
		[ServerProperty("rates", "base_smallchest_chance", "Percentage chance that a mob will drop a small chest of money", 10)]
		public static int BASE_SMALLCHEST_CHANCE;
		
		/// <summary>
		/// The math multiplier for small chest value
		/// </summary>
		[ServerProperty("rates", "smallchest_multiplier", "The math multiplier for small chest value. Increase for more gold", 10)]
		public static int SMALLCHEST_MULTIPLIER;
		
		/// <summary>
		/// The large chest drop chance
		/// </summary>
		[ServerProperty("rates", "base_largechest_chance", "Percentage chance that a mob will drop a large chest of money", 5)]
		public static int BASE_LARGECHEST_CHANCE;
		
		/// <summary>
		/// The math multiplier for small chest value
		/// </summary>
		[ServerProperty("rates", "largechest_multiplier", "The math multiplier for large chest value. Increase for more gold", 17)]
		public static int LARGECHEST_MULTIPLIER;
		
		/// <summary>
		/// The time until a player is worth rps again after death
		/// </summary>
		[ServerProperty("rates", "rp_worth_seconds", "Realm Points Worth Seconds - Edit this to change how many seconds until a player is worth RPs again after being killed ", 300)]
		public static int RP_WORTH_SECONDS;

		/// <summary>
		/// Health Regen Rate
		/// </summary>
		[ServerProperty("rates", "health_regen_amount_modifier", "Health regen amount modifier", 1.0)]
		public static double HEALTH_REGEN_AMOUNT_MODIFIER;

		/// <summary>
		/// Health Regen Rate
		/// </summary>
		[ServerProperty("rates", "endurance_regen_amount_modifier", "Endurance regen amount modifier", 1.0)]
		public static double ENDURANCE_REGEN_AMOUNT_MODIFIER;

		/// <summary>
		/// Health Regen Rate
		/// </summary>
		[ServerProperty("rates", "mana_regen_amount_modifier", "Mana regen amount modifier", 1.0)]
		public static double MANA_REGEN_AMOUNT_MODIFIER;

		[ServerProperty("rates", "mana_regen_amount_halved_below_50_percent", "Should the mana regen amount be halved below 50%? Affects list casters only.", true)]
		public static bool MANA_REGEN_AMOUNT_HALVED_BELOW_50_PERCENT;

		/// <summary>
		/// Items sell ratio
		/// </summary>
		[ServerProperty("rates", "item_sell_ratio", "Merchants are buying items at the % of initial value", 50)]
		public static int ITEM_SELL_RATIO;

		/// <summary>
		/// Chance for condition loss on weapons and armor
		/// </summary>
		[ServerProperty("rates", "item_condition_loss_chance", "What chance does armor or weapon have to lose condition?", 5)]
		public static int ITEM_CONDITION_LOSS_CHANCE;

		/// <summary>
		/// Under level 35 mount speed, live like = 135
		/// </summary>
		[ServerProperty("rates", "mount_under_level_35_speed", "What is the speed of player controlled mounts under level 35?", (short)135)]
		public static short MOUNT_UNDER_LEVEL_35_SPEED;

		/// <summary>
		/// Over level 35 mount speed, live like = 145
		/// </summary>
		[ServerProperty("rates", "mount_over_level_35_speed", "What is the speed of player controlled mounts over level 35?", (short)145)]
		public static short MOUNT_OVER_LEVEL_35_SPEED;

		/// <summary>
		/// Relic Bonus Modifier
		/// </summary>
		[ServerProperty("rates", "relic_owning_bonus", "Relic Owning Bonus in percent per relic (default 10%) in effect when owning enemy relic", (short)10)]
		public static short RELIC_OWNING_BONUS;

		#endregion

		#region NPCs
		/// <summary>
		/// Doppelganger realm point value
		/// </summary>
		[ServerProperty("npc", "doppelganger_realm_points", "Realm point value of doppelgangers.", 400)]
		public static int DOPPELGANGER_REALM_POINTS;

		/// <summary>
		/// Doppelganger bounty point value
		/// </summary>
		[ServerProperty("npc", "doppelganger_bounty_points", "Bounty point value of doppelgangers.", 250)]
		public static int DOPPELGANGER_BOUNTY_POINTS;

		[ServerProperty("npc", "force_mob_autoset_stats", "Should standard NPCs have their stat automatically set using server properties (discarding database values).", true)]
		public static bool FORCE_MOB_AUTOSET_STATS;

		/// <summary>
		/// Base Value to use when auto-setting STR stat.
		/// </summary>
		[ServerProperty("npc", "mob_autoset_str_base", "Base Value to use when auto-setting STR stat.", (short)30)]
		public static short MOB_AUTOSET_STR_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting STR stat.
		/// </summary>
		[ServerProperty("npc", "mob_autoset_str_multiplier", "Multiplier to use when auto-setting STR stat. Multiplied by 10 when applied.", 1.0)]
		public static double MOB_AUTOSET_STR_MULTIPLIER;

		/// <summary>
		/// Base Value to use when auto-setting CON stat.
		/// </summary>
		[ServerProperty("npc", "mob_autoset_con_base", "Base Value to use when auto-setting CON stat.", (short)30)]
		public static short MOB_AUTOSET_CON_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting CON stat.
		/// </summary>
		[ServerProperty("npc", "mob_autoset_con_multiplier", "Multiplier to use when auto-setting CON stat.", 1.0)]
		public static double MOB_AUTOSET_CON_MULTIPLIER;

		/// <summary>
		/// Base Value to use when auto-setting DEX stat.
		/// </summary>
		[ServerProperty("npc", "mob_autoset_dex_base", "Base Value to use when auto-setting DEX stat.", (short)30)]
		public static short MOB_AUTOSET_DEX_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting DEX stat.
		/// </summary>
		[ServerProperty("npc", "mob_autoset_dex_multiplier", "Multiplier to use when auto-setting DEX stat.", 1.0)]
		public static double MOB_AUTOSET_DEX_MULTIPLIER;

		/// <summary>
		/// Base Value to use when auto-setting QUI stat.
		/// </summary>
		[ServerProperty("npc", "mob_autoset_qui_base", "Base Value to use when auto-setting qui stat.", (short)30)]
		public static short MOB_AUTOSET_QUI_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting QUI stat.
		/// </summary>
		[ServerProperty("npc", "mob_autoset_qui_multiplier", "Multiplier to use when auto-setting QUI stat.", 1.0)]
		public static double MOB_AUTOSET_QUI_MULTIPLIER;

		/// <summary>
		/// Base Value to use when auto-setting INT stat.
		/// </summary>
		[ServerProperty("npc", "mob_autoset_int_base", "Base Value to use when auto-setting INT stat.", (short)30)]
		public static short MOB_AUTOSET_INT_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting INT stat.
		/// </summary>
		[ServerProperty("npc", "mob_autoset_int_multiplier", "Multiplier to use when auto-setting INT stat.", 1.0)]
		public static double MOB_AUTOSET_INT_MULTIPLIER;

		/// <summary>
		/// Base Value to use when auto-setting pet STR stat.
		/// </summary>
		[ServerProperty("npc", "pet_autoset_str_base", "Base Value to use when auto-setting Pet STR stat.", (short)30)]
		public static short PET_AUTOSET_STR_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting pet STR stat.
		/// </summary> 
		[ServerProperty("npc", "pet_autoset_str_multiplier", "Multiplier to use when auto-setting Pet STR stat. Multiplied by 10 when applied.", 1.0)]
		public static double PET_AUTOSET_STR_MULTIPLIER;
		
		/// Base Value to use when auto-setting pet CON stat.
		/// </summary>
		[ServerProperty("npc", "pet_autoset_con_base", "Base Value to use when auto-setting Pet CON stat.", (short)30)]
		public static short PET_AUTOSET_CON_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting pet CON stat.
		/// </summary>
		[ServerProperty("npc", "pet_autoset_con_multiplier", "Multiplier to use when auto-setting Pet CON stat.", 1.0)]
		public static double PET_AUTOSET_CON_MULTIPLIER;

		/// Base Value to use when auto-setting Pet DEX stat.
		/// </summary>
		[ServerProperty("npc", "pet_autoset_dex_base", "Base Value to use when auto-setting Pet DEX stat.", (short)30)]
		public static short PET_AUTOSET_DEX_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting pet DEX stat.
		/// </summary>
		[ServerProperty("npc", "pet_autoset_dex_multiplier", "Multiplier to use when auto-setting Pet DEX stat.", 1.0)]
		public static double PET_AUTOSET_DEX_MULTIPLIER;

		/// Base Value to use when auto-setting Pet QUI stat.
		/// </summary>
		[ServerProperty("npc", "pet_autoset_qui_base", "Base Value to use when auto-setting Pet QUI stat.", (short)30)]
		public static short PET_AUTOSET_QUI_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting pet QUI stat.
		/// </summary>
		[ServerProperty("npc", "pet_autoset_qui_multiplier", "Multiplier to use when auto-setting Pet QUI stat. ", 1.0)]
		public static double PET_AUTOSET_QUI_MULTIPLIER;

		/// <summary>
		/// Multiplier to use when auto-setting pet INT stat.
		/// INT is the stat used for spell damage for mobs/pets
		/// </summary>
		[ServerProperty("npc", "pet_autoset_int_base", "Multiplier to use when auto-setting Pet INT stat.", (short)30)]
		public static short PET_AUTOSET_INT_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting pet INT stat.
		/// INT is the stat used for spell damage for mobs/pets
		/// </summary>
		[ServerProperty("npc", "pet_autoset_int_multiplier", "Multiplier to use when auto-setting Pet INT stat.", 1.0)]
		public static double PET_AUTOSET_INT_MULTIPLIER;

		// Necro pet stat properties

		/// <summary>
		/// Base value to use when setting strength for most necromancer pets.
		/// </summary>
		[ServerProperty("npc", "necro_pet_str_base", "Base value to use when setting strength for most necromancer pets.", (short)60)]
		public static short NECRO_PET_STR_BASE;

		/// <summary>
		/// Multiplier to use when setting strength for most necromancer pets.
		/// </summary>
		[ServerProperty("npc", "necro_pet_str_multiplier", "Multiplier to use when setting strength for most necromancer pets.", 1.0)]
		public static double NECRO_PET_STR_MULTIPLIER;

		/// <summary>
		/// Base value to use when setting constitution for most necromancer pets.
		/// </summary>
		[ServerProperty("npc", "necro_pet_con_base", "Base value to use when setting constitution for most necromancer pets.", (short)60)]
		public static short NECRO_PET_CON_BASE;

		/// <summary>
		/// Multiplier to use when setting constitution for most necromancer pets.
		/// </summary>
		[ServerProperty("npc", "necro_pet_con_multiplier", "Multiplier to use when setting constitution for most necromancer pets.", 0.5)]
		public static double NECRO_PET_CON_MULTIPLIER;

		/// <summary>
		/// Base value to use when setting dexterity for most necromancer pets.
		/// </summary>
		[ServerProperty("npc", "necro_pet_dex_base", "Base value to use when setting dexterity for most necromancer pets.", (short)60)]
		public static short NECRO_PET_DEX_BASE;

		/// <summary>
		/// Multiplier to use when setting dexterity for most necromancer pets.
		/// </summary>
		[ServerProperty("npc", "necro_pet_dex_multiplier", "Multiplier to use when setting dexterity for most necromancer pets.", 0.0)]
		public static double NECRO_PET_DEX_MULTIPLIER;

		/// <summary>
		/// Base value to use when setting quickness for most necromancer pets.
		/// </summary>
		[ServerProperty("npc", "necro_pet_qui_base", "Base value to use when setting quickness for most necromancer pets.", (short)60)]
		public static short NECRO_PET_QUI_BASE;

		/// <summary>
		/// Multiplier to use when setting quickness for most necromancer pets.
		/// </summary>
		[ServerProperty("npc", "necro_pet_qui_multiplier", "Multiplier to use when setting quickness for most necromancer pets.", 0.3333)]
		public static double NECRO_PET_QUI_MULTIPLIER;

		/// <summary>
		/// Base value to use when setting intelligence for most necromancer pets.
		/// </summary>
		[ServerProperty("npc", "necro_pet_int_base", "Base value to use when setting intelligence for most necromancer pets.", (short)60)]
		public static short NECRO_PET_INT_BASE;

		/// <summary>
		/// Multiplier to use when setting intelligence for most necromancer pets.
		/// </summary>
		[ServerProperty("npc", "necro_pet_int_multiplier", "Multiplier to use when setting intelligence for most necromancer pets.", 0.3333)]
		public static double NECRO_PET_INT_MULTIPLIER;

		/// <summary>
		/// Base value to use when setting strength for greater necroservant pets.
		/// </summary>
		[ServerProperty("npc", "necro_greater_pet_str_base", "Base value to use when setting strength for greater necroservant pets.", (short)60)]
		public static short NECRO_GREATER_PET_STR_BASE;

		/// <summary>
		/// Multiplier to use when setting strength for greater necroservant pets.
		/// </summary>
		[ServerProperty("npc", "necro_greater_pet_str_multiplier", "Multiplier to use when setting strength for greater necroservant pets.", 0.0)]
		public static double NECRO_GREATER_PET_STR_MULTIPLIER;

		/// <summary>
		/// Base value to use when setting constitution forgreater necroservant pets.
		/// </summary>
		[ServerProperty("npc", "necro_greater_pet_con_base", "Base value to use when setting constitution for greater necroservant pets.", (short)60)]
		public static short NECRO_GREATER_PET_CON_BASE;

		/// <summary>
		/// Multiplier to use when setting constitution for greater necroservant pets.
		/// </summary>
		[ServerProperty("npc", "necro_greater_pet_con_multiplier", "Multiplier to use when setting constitution for greater necroservant pets.", 0.3333)]
		public static double NECRO_GREATER_PET_CON_MULTIPLIER;

		/// <summary>
		/// Base value to use when setting dexterity for greater necroservant pets.
		/// </summary>
		[ServerProperty("npc", "necro_greater_pet_dex_base", "Base value to use when setting dexterity for greater necroservant pets.", (short)60)]
		public static short NECRO_GREATER_PET_DEX_BASE;

		/// <summary>
		/// Multiplier to use when setting dexterity for greater necroservant pets.
		/// </summary>
		[ServerProperty("npc", "necro_greater_pet_dex_multiplier", "Multiplier to use when setting dexterity for greater necroservant pets.", 0.5)]
		public static double NECRO_GREATER_PET_DEX_MULTIPLIER;

		/// <summary>
		/// Base value to use when setting quickness for greater necroservant pets.
		/// </summary>
		[ServerProperty("npc", "necro_greater_pet_qui_base", "Base value to use when setting quickness for greater necroservant pets.", (short)60)]
		public static short NECRO_GREATER_PET_QUI_BASE;

		/// <summary>
		/// Multiplier to use when setting quickness for greater necroservant pets.
		/// </summary>
		[ServerProperty("npc", "necro_greater_pet_qui_multiplier", "Multiplier to use when setting quickness for greater necroservant pets.", 1.0)]
		public static double NECRO_GREATER_PET_QUI_MULTIPLIER;

		/// <summary>
		/// Base value to use when setting intelligence for greater necroservant pets.
		/// </summary>
		[ServerProperty("npc", "necro_greater_pet_int_base", "Base value to use when setting intelligence for greater necroservant pets.", (short)60)]
		public static short NECRO_GREATER_PET_INT_BASE;

		/// <summary>
		/// Multiplier to use when setting intelligence for greater necroservant pets.
		/// </summary>
		[ServerProperty("npc", "necro_greater_pet_int_multiplier", "Multiplier to use when setting intelligence for greater necroservant pets.", 0.3333)]
		public static double NECRO_GREATER_PET_INT_MULTIPLIER;

		/// <summary>
		/// How often should pets think?
		/// </summary>
		[ServerProperty("npc", "pet_think_interval", "How often should pets think?", 600)]
		public static int PET_THINK_INTERVAL;

		/// <summary>
		/// Scale pet spell values according to their level?
		/// </summary>
		[ServerProperty("npc", "pet_bd_commander_taunt_multiplier", "Percentage of damage that BD commanders get as extra aggro when taunting, e.g. a taunting BD commander gets 150% normal aggro at 50, 200% at 100, 250% at 150 etc. ", 150)]
		public static int PET_BD_COMMANDER_TAUNT_VALUE;

		/// <summary>
		/// Minimum respawn time for npc's without a set respawninterval
		/// </summary>
		[ServerProperty("npc", "npc_min_respawn_interval", "Minimum respawn time, in minutes, for npc's without a set respawninterval", 5)]
		public static int NPC_MIN_RESPAWN_INTERVAL;

		/// <summary>
		/// Respawn Interval for Shrouded Isles Epic Encounter
		/// </summary>
		[ServerProperty("world", "set_si_epic_encounter_respawninterval", "Respawn Time, in minutes, for Epic Encounters in Shrouded Isles", 60)]
		public static int SET_SI_EPIC_ENCOUNTER_RESPAWNINTERVAL;

		/// <summary>
		/// Respawn Interval for Normal Epic Game Boss Encounter
		/// </summary>
		[ServerProperty("world", "set_epic_game_encounter_respawninterval", "Respawn Time, in minutes, for Normal Epic Game Encounters", 60)]
		public static int SET_EPIC_GAME_ENCOUNTER_RESPAWNINTERVAL;

		/// <summary>
		/// Respawn Interval for Epic Quest Mobs
		/// </summary>
		[ServerProperty("world", "set_epic_quest_encounter_respawninterval", "Respawn Time, in minutes, for Epic Quest Encounters", 30)]
		public static int SET_EPIC_QUEST_ENCOUNTER_RESPAWNINTERVAL;

		/// <summary>
		/// Weapon damage cap for epic encounters that use melee weapons
		/// </summary>
		[ServerProperty("npc", "set_epic_encounter_weapon_damage_cap", "Maximum damage cap multipler for epic encounters that use melee weapons", 1.5)]
		public static double SET_EPIC_ENCOUNTER_WEAPON_DAMAGE_CAP;

		/// <summary>
		/// Allow Roam
		/// </summary>
		[ServerProperty("npc", "allow_roam", "Allow mobs to roam on the server", true)]
		public static bool ALLOW_ROAM;

		/// <summary>
		/// Chance for NPC to roam.
		/// </summary>
		[ServerProperty("npc", "gamenpc_roam_cooldown_min", "Minimum duration in seconds between two roams.", 5)]
		public static int GAMENPC_ROAM_COOLDOWN_MIN;

		/// <summary>
		/// Chance for NPC to roam.
		/// </summary>
		[ServerProperty("npc", "gamenpc_roam_cooldown_max", "Maximum duration in seconds between two roams.", 40)]
		public static int GAMENPC_ROAM_COOLDOWN_MAX;

		/// <summary>
		/// How often, in milliseconds, to check follow distance.  Lower numbers make NPC follow closer but increase load on server.
		/// </summary>
		[ServerProperty("npc", "gamenpc_followcheck_time", "How often, in milliseconds, to check follow distance. Lower numbers make NPC follow closer but increase load on server.", 100)]
		public static int GAMENPC_FOLLOWCHECK_TIME;

		/// <summary>
		/// Override the classtype of any npc with a classtype of DOL.GS.GameNPC
		/// </summary>
		[ServerProperty("npc", "gamenpc_default_classtype", "Change the classtype of any npc of classtype DOL.GS.GameNPC to this.", "DOL.GS.GameNPC")]
		public static string GAMENPC_DEFAULT_CLASSTYPE;

		/// <summary>
		/// Chances for npc (including pet) to style (chance is calculated randomly according to this value + the number of style the NPC own)
		/// </summary>
		[ServerProperty("npc", "gamenpc_chances_to_style", "Change the chance to fire a style for a mob or a pet", 20)]
		public static int GAMENPC_CHANCES_TO_STYLE;

		/// <summary>
		/// NPCs heal when a target is below what percentage of their health?
		/// </summary>
		[ServerProperty("npc", "npc_heal_threshold", "NPCs heal targets whose health falls below this percentage.", 75)]
		public static int NPC_HEAL_THRESHOLD;

		/// <summary>
		/// Pets heal when a target is below what percentage of their health?
		/// </summary>
		[ServerProperty("npc", "pet_heal_threshold", "Pets (including charmed NPCs, excluding Bonedancer pets) heal targets whose health falls below this percentage.", 50)]
		public static int PET_HEAL_THRESHOLD;

		/// <summary>
		/// Bonedancer healer pets heal when a target is below what percentage of their health?
		/// </summary>
		[ServerProperty("npc", "bonedancer_healer_pets_heal_threshold", "Bonedancer healer pets heal targets whose health falls below this percentage.", 90)]
		public static int BONEDANCER_HEALER_PET_HEAL_THRESHOLD;

		/// <summary>
		/// Expand the Wild Minion RA to also improve crit chance for ranged and spell attacks?
		/// </summary>
		[ServerProperty("npc", "expand_wild_minion", "Expand the Wild Minion RA to also improve crit chance for ranged and spell attacks?", false)]
		public static bool EXPAND_WILD_MINION;

		#endregion

		#region PVP / RVR

		/// <summary>
		/// PvP Immunity Timer - Killed by Mobs
		/// </summary>
		[ServerProperty("pvp", "Timer_Killed_By_Mob", "Immunity Timer When player killed in PvP, in seconds", 10)]
		public static int TIMER_KILLED_BY_MOB;

		/// <summary>
		/// PvP Immunity Timer - Killed by Player
		/// </summary>
		[ServerProperty("pvp", "Timer_Killed_By_Player", "Immunity Timer When player killed in PvP, in seconds", 10)]
		public static int TIMER_KILLED_BY_PLAYER;

		/// <summary>
		/// PvP Immunity Timer - Region Changed
		/// </summary>
		[ServerProperty("pvp", "Timer_Region_Changed", "Immunity Timer when player changes regions, in seconds", 10)]
		public static int TIMER_REGION_CHANGED;

		/// <summary>
		/// PvP Immunity Timer - Game Entered
		/// </summary>
		[ServerProperty("pvp", "Timer_Game_Entered", "Immunity Timer when player enters the game, in seconds", 10)]
		public static int TIMER_GAME_ENTERED;

		/// <summary>
		/// PvP Immunity Timer - Teleport
		/// </summary>
		[ServerProperty("pvp", "Timer_PvP_Teleport", "Immunity Timer when player teleports within the same region, in seconds", 10)]
		public static int TIMER_PVP_TELEPORT;

		/// <summary>
		/// Time after a relic lost in nature is returning to his ReturnRelicPad pad
		/// </summary>
		[ServerProperty("pvp", "Relic_Return_Time", "A lost relic will automatically returns to its defined point, in seconds", 20 * 60)]
		public static int RELIC_RETURN_TIME;

		/// <summary>
		/// Allow all realms access to DF
		/// </summary>
		[ServerProperty("pvp", "allow_all_realms_df", "Should we allow all realms access to DF", false)]
		public static bool ALLOW_ALL_REALMS_DF;

		/// <summary>
		/// Allow Bounty Points to be gained in Battlegrounds
		/// </summary>
		[ServerProperty("pvp", "allow_bps_in_bgs", "Allow bounty points to be gained in battlegrounds", false)]
		public static bool ALLOW_BPS_IN_BGS;

		/// <summary>
		/// This if the server battleground zones are open to players
		/// </summary>
		[ServerProperty("pvp", "bg_zones_open", "Can the players teleport to battleground", true)]
		public static bool BG_ZONES_OPENED;

		/// <summary>
		/// Message to display to player if BG zones are closed
		/// </summary>
		[ServerProperty("pvp", "bg_zones_closed_message", "Message to display to player if BG zones are closed", "The battlegrounds are not open on this server.")]
		public static string BG_ZONES_CLOSED_MESSAGE;

		/// <summary>
		/// How many players are required on the relic pad to trigger the pillar?
		/// </summary>
		[ServerProperty("pvp", "relic_players_required_on_pad", "How many players are required on the relic pad to trigger the pillar?", 16)]
		public static int RELIC_PLAYERS_REQUIRED_ON_PAD;

		/// <summary>
		/// Ignore too long outcoming packet or not
		/// </summary>
		[ServerProperty("pvp", "enable_minotaur_relics", "Shall we enable Minotaur Relics ?", false)]
		public static bool ENABLE_MINOTAUR_RELICS;

		/// <summary>
		/// Enable WarMap manager
		/// </summary>
		[ServerProperty("pvp", "enable_warmapmgr", "Shall we enable the WarMap manager ?", false)]
		public static bool ENABLE_WARMAPMGR;
		
		/// <summary>
		/// Toggle con loss on PvP server type
		/// </summary>
		[ServerProperty("pvp", "pvp_death_con_loss", "Loose con on pvp death on PvP servertype", true)]
		public static bool PVP_DEATH_CON_LOSS;

		/// <summary>
		/// Whether releasing in a battleground should teleport the player to the portal keep
		/// </summary>
		[ServerProperty("pvp", "bg_release_to_portal_keep", "Whether releasing in a battleground should teleport the player to the portal keep", false)]
		public static bool BG_RELEASE_TO_PORTAL_KEEP;

		#endregion

		#region Daily / Weekly / Monthly / Beetle Quest
		/// <summary>
		/// The value of Daily Quest realmpoints reward
		/// </summary>
		[ServerProperty("quest", "daily_rvr_reward", "Daily Quest realmpoints reward", 0)]
		public static int DAILY_RVR_REWARD;
		
		/// <summary>
		/// The value of Weekly Quest realmpoints reward
		/// </summary>
		[ServerProperty("quest", "weekly_rvr_reward", "Weekly Quest realmpoints reward", 0)]
		public static int WEEKLY_RVR_REWARD;
		
		/// <summary>
		/// The value of Monthly Quest realmpoints reward
		/// </summary>
		[ServerProperty("quest", "monthly_rvr_reward", "Monthly Quest realmpoints reward", 0)]
		public static int MONTHLY_RVR_REWARD;
		
		/// <summary>
		/// The value of Hardcore RvR Quest realmpoints reward
		/// </summary>
		[ServerProperty("quest", "hardcore_rvr_reward", "Hardcore Quest realmpoints reward", 0)]
		public static int HARDCORE_RVR_REWARD;
		
		/// <summary>
		/// The value of Beetle RvR Quest realmpoints reward
		/// </summary>
		[ServerProperty("quest", "beetle_rvr_reward", "Beetle Quest realmpoints reward", 0)]
		public static int BEETLE_RVR_REWARD;
		#endregion

		#region KEEPS
		/// <summary>
		/// The number of players needed for claiming
		/// </summary>
		[ServerProperty("keeps", "claim_num", "Players Needed For Claim - Edit this to change the amount of players required to claim a keep, towers are half this amount", 8)]
		public static int CLAIM_NUM;

		/// <summary>
		/// Use Keep Balancing
		/// </summary>
		[ServerProperty("keeps", "use_keep_balancing", "Set to true if you want keeps to be higher level in NF the less you have, and lower level the more you have", false)]
		public static bool USE_KEEP_BALANCING;

		/// <summary>
		/// Use Live Keep Bonuses
		/// </summary>
		[ServerProperty("keeps", "use_live_keep_bonuses", "Set to true if you want to use the live keeps bonuses, for example 3% extra xp", false)]
		public static bool USE_LIVE_KEEP_BONUSES;

		/// <summary>
		/// Use Supply Chain
		/// </summary>
		[ServerProperty("keeps", "use_supply_chain", "Set to true if you want to use the live supply chain for keep teleporting, set to false to allow teleporting to any keep that your realm controls (and towers)", false)]
		public static bool USE_SUPPLY_CHAIN;

		/// <summary>
		/// Load Hookpoints
		/// </summary>
		[ServerProperty("keeps", "load_hookpoints", "Load keep hookpoints", true)]
		public static bool LOAD_HOOKPOINTS;

		/// <summary>
		/// Load Keeps
		/// </summary>
		[ServerProperty("keeps", "load_keeps", "Load keeps", true)]
		public static bool LOAD_KEEPS = true;

		/// <summary>
		/// The level keeps start at when not claimed - please note only levels 4 and 5 are supported correctly at this time
		/// </summary>
		[ServerProperty("keeps", "starting_keep_level", "The level an unclaimed keep starts at.", 4)]
		public static int STARTING_KEEP_LEVEL;

		/// <summary>
		/// The level keeps start at when claimed - please note only levels 4 and 5 are supported correctly at this time
		/// </summary>
		[ServerProperty("keeps", "starting_keep_claim_level", "The level a claimed keep starts at.", 5)]
		public static int STARTING_KEEP_CLAIM_LEVEL;

		/// <summary>
		/// The maximum keep level - please note only levels 4 and 5 are supported correctly at this time
		/// </summary>
		[ServerProperty("keeps", "max_keep_level", "The maximum keep level.", 5)]
		public static int MAX_KEEP_LEVEL;

		/// <summary>
		/// Enable the keep upgrade timer to slowly raise keep levels
		/// </summary>
		[ServerProperty("keeps", "enable_keep_upgrade_timer", "Enable the keep upgrade timer to slowly raise keep levels?", false)]
		public static bool ENABLE_KEEP_UPGRADE_TIMER;

		/// <summary>
		/// Define toughness for keep and tower walls: 100 is 100% player's damages inflicted.
		/// </summary>
		[ServerProperty("keeps", "set_structures_toughness", "This value is % of total damages inflicted to walls. (100=full damages)", 100)]
		public static int SET_STRUCTURES_TOUGHNESS;

		/// <summary>
		/// Define toughness for keep doors: 100 is 100% player's damages inflicted.
		/// </summary>
		[ServerProperty("keeps", "set_keep_door_toughness", "This value is % of total damages inflicted to level 1 door. (100=full damages)", 100)]
		public static int SET_KEEP_DOOR_TOUGHNESS;

		/// <summary>
		/// Define toughness for tower doors: 100 is 100% player's damages inflicted.
		/// </summary>
		[ServerProperty("keeps", "set_tower_door_toughness", "This value is % of total damages inflicted to level 1 door. (100=full damages)", 100)]
		public static int SET_TOWER_DOOR_TOUGHNESS;

		/// <summary>
		/// Allow player pets to attack keep walls
		/// </summary>
		[ServerProperty("keeps", "structures_allowpetattack", "Allow player pets to attack keep and tower walls?", true)]
		public static bool STRUCTURES_ALLOWPETATTACK;

		/// <summary>
		/// Allow player pets to attack keep and tower doors
		/// </summary>
		[ServerProperty("keeps", "doors_allowpetattack", "Allow player pets to attack keep and tower doors?", true)]
		public static bool DOORS_ALLOWPETATTACK;

		/// <summary>
		/// Multiplier used in determining RP reward for claiming towers.
		/// </summary>
		[ServerProperty("keeps", "tower_rp_claim_multiplier", "Integer multiplier used in determining RP reward for claiming towers.", 100)]
		public static int TOWER_RP_CLAIM_MULTIPLIER;

		/// <summary>
		/// Multiplier used in determining RP reward for keeps.
		/// </summary>
		[ServerProperty("keeps", "keep_rp_claim_multiplier", "Integer multiplier used in determining RP reward for claiming keeps.", 1000)]
		public static int KEEP_RP_CLAIM_MULTIPLIER;

		/// <summary>
		/// Turn on logging of keep captures
		/// </summary>
		[ServerProperty("keeps", "log_keep_captures", "Turn on logging of keep captures?", false)]
		public static bool LOG_KEEP_CAPTURES;

		/// <summary>
		/// Base RP value of a keep
		/// </summary>
		[ServerProperty("keeps", "keep_rp_base", "Base RP value of a keep", 0)] // Previously 4500.
		public static int KEEP_RP_BASE;

		/// <summary>
		/// Base RP value of a tower
		/// </summary>
		[ServerProperty("keeps", "tower_rp_base", "Base RP value of a tower", 0)] // Previously 500.
		public static int TOWER_RP_BASE;

		/// <summary>
		/// The number of seconds from last kill the this lord is worth no RP
		/// </summary>
		[ServerProperty("keeps", "lord_rp_worth_seconds", "The number of seconds from last kill the this lord is worth no RP.", 300)]
		public static int LORD_RP_WORTH_SECONDS;

		/// <summary>
		/// Multiplier used to add or subtract RP worth based on keep level difference from 50.
		/// </summary>
		[ServerProperty("keeps", "keep_rp_multiplier", "Integer multiplier used to increase/decrease RP worth based on keep level difference from 50.", 0)] // Previously 50.
		public static int KEEP_RP_MULTIPLIER;

		/// <summary>
		/// Multiplier used to add or subtract RP worth based on tower level difference from 50.
		/// </summary>
		[ServerProperty("keeps", "tower_rp_multiplier", "Integer multiplier used to increase/decrease RP worth based on tower level difference from 50.", 0)] // Previously 50.
		public static int TOWER_RP_MULTIPLIER;

		/// <summary>
		/// Multiplier used to add or subtract RP worth based on upgrade level > 1
		/// </summary>
		[ServerProperty("keeps", "upgrade_multiplier", "Integer multiplier used to increase/decrease RP worth based on upgrade level (0..10)", 100)]
		public static int UPGRADE_MULTIPLIER;

		/// <summary>
		/// Multiplier used to determine keep level changes when balancing.  For each keep above or below normal multiply by this.
		/// </summary>
		[ServerProperty("keeps", "keep_balance_multiplier", "Multiplier used to determine keep level changes when balancing.  For each keep above or below normal multiply by this.", 1.0)]
		public static double KEEP_BALANCE_MULTIPLIER;

		/// <summary>
		/// Multiplier used to determine keep level changes when balancing.  For each keep above or below normal multiply by this.
		/// </summary>
		[ServerProperty("keeps", "tower_balance_multiplier", "Multiplier used to determine tower level changes when balancing.  For each keep above or below normal multiply by this.", 0.15)]
		public static double TOWER_BALANCE_MULTIPLIER;

		/// <summary>
		/// Balance Towers and Keeps separately
		/// </summary>
		[ServerProperty("keeps", "balance_towers_separate", "Balance Towers and Keeps separately?", true)]
		public static bool BALANCE_TOWERS_SEPARATE;

		/// <summary>
		/// Multiplier used to determine keep guard levels.  This is applied to the bonus level (usually 4) and added after balance adjustments.
		/// </summary>
		[ServerProperty("keeps", "keep_guard_level_multiplier", "Multiplier used to determine keep guard levels.  This is applied to the bonus level (usually 4) and added after balance adjustments.", 1.6)]
		public static double KEEP_GUARD_LEVEL_MULTIPLIER;

		/// <summary>
		/// Modifier used to adjust damage for pets on keep components
		/// </summary>
		[ServerProperty("keeps", "pet_damage_multiplier", "Modifier used to adjust damage for pets classes.", 1.0)]
		public static double PET_DAMAGE_MULTIPLIER;

		/// <summary>
		/// Modifier used to adjust damage for pet spam classes (currently animist and theurgist) on keep components
		/// </summary>
		[ServerProperty("keeps", "pet_spam_damage_multiplier", "Modifier used to adjust damage for pet spam classes (currently animist and theurgist).", 1.0)]
		public static double PET_SPAM_DAMAGE_MULTIPLIER;

		/// <summary>
		/// Multiplier used to determine keep guard levels.  This is applied to the bonus level (usually 4) and added after balance adjustments.
		/// </summary>
		[ServerProperty("keeps", "tower_guard_level_multiplier", "Multiplier used to determine tower guard levels.  This is applied to the bonus level (usually 4) and added after balance adjustments.", 1.0)]
		public static double TOWER_GUARD_LEVEL_MULTIPLIER;

		/// <summary>
		/// Keeps to load. 0 for Old Keeps, 1 for new keeps, 2 for both.
		/// </summary>
		[ServerProperty("keeps", "use_new_keeps", "Appearance Keeps Components to load. 0 for Old Appearance Keeps Components, 1 for New Appearance Keeps Components. 2 is no longer used but load 0 for compatibility.", 0)]
		public static int USE_NEW_KEEPS;

		/// <summary>
		/// Should guards loaded from db be equipped by Keepsystem? (false=load equipment from db)
		/// </summary>
		[ServerProperty("keeps", "autoequip_guards_loaded_from_db", "Should guards loaded from db be equipped by Keepsystem? (false=load equipment from db)", true)]
		public static bool AUTOEQUIP_GUARDS_LOADED_FROM_DB;

		/// <summary>
		/// Should guards loaded from db be modeled by Keepsystem? (false=load from db)
		/// </summary>
		[ServerProperty("keeps", "automodel_guards_loaded_from_db", "Should guards loaded from db be modeled by Keepsystem? (false=load from db)", true)]
		public static bool AUTOMODEL_GUARDS_LOADED_FROM_DB;

		/// <summary>
		/// Are unclaimed keeps considered the enemy in PvP mode?
		/// </summary>
		[ServerProperty("keeps", "pvp_unclaimed_keeps_enemy", "Are unclaimed keeps considered the enemy in PvP mode?", false)]
		public static bool PVP_UNCLAIMED_KEEPS_ENEMY;

		/// <summary>
		/// Grace period in minutes to allow relog near enemy structure after link death
		/// </summary>
		[ServerProperty("keeps", "NearKeepRelogGracePeriod", "The grace period in minutes, to allow to relog near an enemy structure.", 3)]
		public static int NEAR_KEEP_RELOG_GRACE_PERIOD;

		/// <summary>
		/// Should players that exceed BG level cap be moved out of BG when logging in?
		/// </summary>
		[ServerProperty("keeps", "teleport_login_bg_level_exceeded", "Should players that exceed BG level cap be moved out of BG when logging in?", true)]
		public static bool TELEPORT_LOGIN_BG_LEVEL_EXCEEDED;

		/// <summary>
		/// Do you allowed player to climb towers?
		/// </summary>
		[ServerProperty("keeps", "allow_tower_climb", "Do you allowed player to climb towers? Set True for yes, False for not.", false)]
		public static bool ALLOW_TOWER_CLIMB;

		/// <summary>
		/// Keep guard heal when a target is below what percentage of their health?
		/// </summary>
		[ServerProperty("keeps", "keep_heal_threshold", "Keep guards heal targets whose health falls below this value.", 60)]
		public static int KEEP_HEAL_THRESHOLD;
		
		/// <summary>
		/// Base Value to use when auto-setting STR stat.
		/// </summary>
		[ServerProperty("keeps", "guard_autoset_str_base", "Base Value to use when auto-setting STR stat. ", (short)20)]
		public static short GUARD_AUTOSET_STR_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting STR stat.
		/// </summary>
		[ServerProperty("keeps", "guard_autoset_str_multiplier", "Multiplier to use when auto-setting STR stat.  Multiplied by 10 when used.", 0.7)]
		public static double GUARD_AUTOSET_STR_MULTIPLIER;

		/// <summary>
		/// Base Value to use when auto-setting CON stat.
		/// </summary>
		[ServerProperty("keeps", "guard_autoset_con_base", "Base Value to use when auto-setting CON stat. ", (short)30)]
		public static short GUARD_AUTOSET_CON_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting CON stat.
		/// </summary>
		[ServerProperty("keeps", "guard_autoset_con_multiplier", "Multiplier to use when auto-setting CON stat. ", 0.0)]
		public static double GUARD_AUTOSET_CON_MULTIPLIER;

		/// <summary>
		/// Base Value to use when auto-setting QUI stat.
		/// </summary>
		[ServerProperty("keeps", "guard_autoset_qui_base", "Base Value to use when auto-setting qui stat. ", (short)40)]
		public static short GUARD_AUTOSET_QUI_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting QUI stat.
		/// </summary>
		[ServerProperty("keeps", "guard_autoset_qui_multiplier", "Multiplier to use when auto-setting QUI stat. ", 0.0)]
		public static double GUARD_AUTOSET_QUI_MULTIPLIER;

		/// <summary>
		/// Base Value to use when auto-setting DEX stat.
		/// </summary>
		[ServerProperty("keeps", "guard_autoset_dex_base", "Base Value to use when auto-setting DEX stat. ", (short)1)]
		public static short GUARD_AUTOSET_DEX_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting DEX stat.
		/// </summary>
		[ServerProperty("keeps", "guard_autoset_dex_multiplier", "Multiplier to use when auto-setting DEX stat. ", 1.0)]
		public static double GUARD_AUTOSET_DEX_MULTIPLIER;

		/// <summary>
		/// Base Value to use when auto-setting INT stat.
		/// </summary>
		[ServerProperty("keeps", "guard_autoset_int_base", "Base Value to use when auto-setting INT stat. ", (short)30)]
		public static short GUARD_AUTOSET_INT_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting INT stat.
		/// </summary>
		[ServerProperty("keeps", "guard_autoset_int_multiplier", "Multiplier to use when auto-setting INT stat. ", 1.0)]
		public static double GUARD_AUTOSET_INT_MULTIPLIER;

		/// <summary>
		/// Base Value to use when auto-setting STR stat.
		/// </summary>
		[ServerProperty("keeps", "lord_autoset_str_base", "Base Value to use when auto-setting STR stat. ", (short)20)]
		public static short LORD_AUTOSET_STR_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting STR stat.
		/// </summary>
		[ServerProperty("keeps", "lord_autoset_str_multiplier", "Multiplier to use when auto-setting STR stat.  Multiplied by 10 when used.", 0.8)]
		public static double LORD_AUTOSET_STR_MULTIPLIER;

		/// <summary>
		/// Base Value to use when auto-setting CON stat.
		/// </summary>
		[ServerProperty("keeps", "lord_autoset_con_base", "Base Value to use when auto-setting CON stat. ", (short)30)]
		public static short LORD_AUTOSET_CON_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting CON stat.
		/// </summary>
		[ServerProperty("keeps", "lord_autoset_con_multiplier", "Multiplier to use when auto-setting CON stat. ", 0)]
		public static double LORD_AUTOSET_CON_MULTIPLIER;

		/// <summary>
		/// Base Value to use when auto-setting QUI stat.
		/// </summary>
		[ServerProperty("keeps", "lord_autoset_qui_base", "Base Value to use when auto-setting qui stat. ", (short)60)]
		public static short LORD_AUTOSET_QUI_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting QUI stat.
		/// </summary>
		[ServerProperty("keeps", "lord_autoset_qui_multiplier", "Multiplier to use when auto-setting QUI stat. ", 0)]
		public static double LORD_AUTOSET_QUI_MULTIPLIER;

		/// <summary>
		/// Base Value to use when auto-setting DEX stat.
		/// </summary>
		[ServerProperty("keeps", "lord_autoset_dex_base", "Base Value to use when auto-setting DEX stat. ", (short)2)]
		public static short LORD_AUTOSET_DEX_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting DEX stat.
		/// </summary>
		[ServerProperty("keeps", "lord_autoset_dex_multiplier", "Multiplier to use when auto-setting DEX stat. ", 2.0)]
		public static double LORD_AUTOSET_DEX_MULTIPLIER;

		/// <summary>
		/// Base Value to use when auto-setting INT stat.
		/// </summary>
		[ServerProperty("keeps", "lord_autoset_int_base", "Base Value to use when auto-setting INT stat. ", (short)30)]
		public static short LORD_AUTOSET_INT_BASE;

		/// <summary>
		/// Multiplier to use when auto-setting INT stat.
		/// </summary>
		[ServerProperty("keeps", "lord_autoset_int_multiplier", "Multiplier to use when auto-setting INT stat. ", 1.0)]
		public static double LORD_AUTOSET_INT_MULTIPLIER;

		/// <summary>
		/// Respawn time for keep guards in minutes.
		/// </summary>
		[ServerProperty("keeps", "guard_respawn", "Respawn time for keep guards in minutes.", 15)]
		public static int GUARD_RESPAWN;

		/// <summary>
		/// Respawn variance for keep guards in minutes.
		/// </summary>
		[ServerProperty("keeps", "guard_respawn_variance", "Respawn variance for keep guards in minutes.", 10)]
		public static int GUARD_RESPAWN_VARIANCE;
		
		/// <summary>
		/// Doors base health value.
		/// </summary>
		[ServerProperty("keeps", "keep_doors_base_health", "Keep doors base health. Will be multiplied by the keep's base level.", 200)]
		public static int KEEP_DOORS_BASE_HEALTH;

		/// <summary>
		/// Doors health upgrade modifier.
		/// </summary>
		[ServerProperty("keeps", "keep_doors_health_upgrade_modifier", "The modifier used to calculate the extra amount of door health per upgrade.", 1.0)]
		public static double KEEP_DOORS_HEALTH_UPGRADE_MODIFIER;

		/// <summary>
		/// Components base health value.
		/// </summary>
		[ServerProperty("keeps", "keep_components_base_health", "Keep components base health. Will be multiplied by the keep's base level.", 200)]
		public static int KEEP_COMPONENTS_BASE_HEALTH;

		/// <summary>
		/// Components health upgrade modifier.
		/// </summary>
		[ServerProperty("keeps", "keep_components_health_upgrade_modifier", "The modifier used to calculate the extra amount of component health per upgrade.", 1.0)]
		public static double KEEP_COMPONENTS_HEALTH_UPGRADE_MODIFIER;

		/// <summary>
		/// Relic gates health value.
		/// </summary>
		[ServerProperty("keeps", "relic_doors_health", "Relic gates health value", 180000)]
		public static int RELIC_DOORS_HEALTH;

		#endregion

		#region PVE / TOA
		/// <summary>
		/// Allow currency exchange?
		/// </summary>
		[ServerProperty("pve", "currency_exchange_allow", "Allow players to exchange aurulite/blood seals/glass/scales by giving them to a merchant who takes the desired currency, i.e. you can give glass to dragon merchants to get scales?", true)]
		public static bool CURRENCY_EXCHANGE_ALLOW;

		/// <summary>
		/// Currency exchange values, i.e. you need 10 aurulite to get 1 dragon scale.
		/// </summary>
		[ServerProperty("pve", "currency_exchange_values", "Value of special currencies for currency conversion.", "atlanteanglass|1;aurulite|4;dragonscales|40;BloodSeal|1000")]
		public static string CURRENCY_EXCHANGE_VALUES;

		/// <summary>
		/// Allow currencies to be exchanged for BPs?
		/// </summary>
		[ServerProperty("pve", "bp_exchange_allow", "Allow players to exchange special currencies for BPs by giving them to BP merchants?", true)]
		public static bool BP_EXCHANGE_ALLOW;

		/// <summary>
		/// BP exchange values.  Each item grants x BPs.
		/// </summary>
		[ServerProperty("pve", "bp_exchange_values", "Value of special currencies in BPs.", "atlanteanglass|1;aurulite|4;dragonscales|40;BloodSeal|1000")]
		public static string BP_EXCHANGE_VALUES;

		/// <summary>
		/// Initial percent chance of a mob BAFing for a single attacker
		/// </summary>
		[ServerProperty("pve", "baf_initial_chance", "Percent chance for a mob to bring a friend when attacked by a single attacker.  Each multiples of 100 guarantee an add, so a cumulative chance of 250% guarantees two adds with a 50% chance of a third.", 0)]
		public static int BAF_INITIAL_CHANCE;

		/// <summary>
		/// Added percent chance of a mob BAFing for each attacker past the first
		/// </summary>
		[ServerProperty("pve", "baf_additional_chance", "Percent chance for a mob to bring a friend for each additional attacker.  Each multiples of 100 guarantee an add, so a cumulative chance of 250% guarantees two adds with a 50% chance of a third.", 50)]
		public static int BAF_ADDITIONAL_CHANCE;

		/// <summary>
		/// Do BAF mobs attack the player who pulled?
		/// </summary>
		[ServerProperty("pve", "baf_mobs_attack_puller", "Do mobs brought by friends only attack the character who pulled them?  If false, mobs attack random players near the puller.", false)]
		public static bool BAF_MOBS_ATTACK_PULLER;

		/// <summary>
		/// Do BAF mobs attack characters in the same BG as the pulling character?
		/// </summary>
		[ServerProperty("pve", "baf_mobs_attack_bg_members", "Do mobs brought by friends attack random nearby players in the puller's battlegroup?  If false, mobs only attack characters in the pulling player's group.", false)]
		public static bool BAF_MOBS_ATTACK_BG_MEMBERS;

		/// <summary>
		/// Is the number of mobs added by BAF based on the number of nearby players in the puller's BG?
		/// </summary>
		[ServerProperty("pve", "baf_mobs_count_bg_members", "Is the number of mobs brought by a friend based on the number of nearby players in the pulling player's battlegroup?  If false, the number of mobs brought is determined by the number of players in the pulling player's group.", false)]
		public static bool BAF_MOBS_COUNT_BG_MEMBERS;			

		/// <summary>
		/// Adjustment to missrate per number of attackers
		/// </summary>
		[ServerProperty("pve", "missrate_reduction_per_attackers", "Adjustment to missrate per number of attackers", 0)]
		public static int MISSRATE_REDUCTION_PER_ATTACKERS;

		/// <summary>
		/// Spell damage reduction multiplier based on hitchance below 55%.
		/// Default is 4.3, which will produce the minimum 1 damage at a 33% chance to hit
		/// Lower numbers reduce damage reduction
		/// </summary>
		[ServerProperty("pve", "spell_hitchance_damage_reduction_multiplier", "Spell damage reduction multiplier based on hitchance if < 55%. Lower numbers reduce damage reduction.", 4.3)]
		public static double SPELL_HITCHANCE_DAMAGE_REDUCTION_MULTIPLIER;

		/// <summary>
		/// TOA Artifact XP rate
		/// </summary>
		[ServerProperty("pve", "artifact_xp_rate", "Adjust the rate at which all artifacts gain xp.  Higher numbers mean slower XP gain. XP / this = result", 350)]
		public static int ARTIFACT_XP_RATE;

		/// <summary>
		/// TOA Scroll drop rate
		/// </summary>
		[ServerProperty("pve", "scroll_drop_rate", "Adjust the drop rate (percent chance) for scrolls.", 25)]
		public static int SCROLL_DROP_RATE;

		/// <summary>
		/// Max camp bonus
		/// </summary>
		[ServerProperty("pve", "max_camp_bonus", "Max camp bonus, 0.55 = 55%", 0.55)]
		public static double MAX_CAMP_BONUS;

		/// <summary>
		/// Max camp bonus
		/// </summary>
		[ServerProperty("pve", "max_dungeon_camp_bonus", "Max camp bonus, 0.55 = 55%", 0.66)]
		public static double MAX_DUNGEON_CAMP_BONUS;

		/// <summary>
		/// Minimum privilege level to be able to enter Atlantis through teleporters.
		/// </summary>
		[ServerProperty("pve", "atlantis_teleport_plvl", "Set the minimum privilege level required to enter Atlantis zones.", 2)]
		public static int ATLANTIS_TELEPORT_PLVL;
		
		/// <summary>
		/// Time Before Adventure Wings Instances Destroy when Empty
		/// </summary>
		[ServerProperty("pve", "adventurewing_time_to_destroy", "Set the time before Instanced Adventure Wings (Catacombs) are destroy when empty (in minutes).", 5)]
		public static int ADVENTUREWING_TIME_TO_DESTROY;

		/// <summary>
		/// Aurulite Loot Generator Drop Base Chance
		/// </summary>
		[ServerProperty("pve", "lootgenerator_aurulite_base_chance", "Base chance for dropping Aurulite using Loot Generator.", 10)]
		public static int LOOTGENERATOR_AURULITE_BASE_CHANCE;

		/// <summary>
		/// Aurulite Loot Generator Amount Ratio
		/// </summary>
		[ServerProperty("pve", "lootgenerator_aurulite_amount_ratio", "Modify the final count of Aurulite Loot Generator drop. (TotalCount * lootgenerator_aurulite_amount_ratio)", 0.5)]
		public static double LOOTGENERATOR_AURULITE_AMOUNT_RATIO;
		
		/// <summary>
		/// Aurulite Loot Generator Named Boost Count
		/// </summary>
		[ServerProperty("pve", "lootgenerator_aurulite_named_count", "Increase count of Aurulite Loot Generator drop for Named mobs. (count * lootgenerator_aurulite_named_count)", 1.5)]
		public static double LOOTGENERATOR_AURULITE_NAMED_COUNT;
				
		/// <summary>
		/// Atlantean Glass Loot Generator Drop Base Chance
		/// </summary>
		[ServerProperty("pve", "lootgenerator_atlanteanglass_base_chance", "Base chance for dropping Atlantean Glass using Loot Generator.", 20)]
		public static int LOOTGENERATOR_ATLANTEANGLASS_BASE_CHANCE;
		
		/// <summary>
		/// Atlantean Glass Loot Generator Named Boost Count
		/// </summary>
		[ServerProperty("pve", "lootgenerator_atlanteanglass_named_count", "Increase count of Atlantean Glass Loot Generator drop for Named mobs. (count * lootgenerator_atlanteanglass_named_count)", 1.5)]
		public static double LOOTGENERATOR_ATLANTEANGLASS_NAMED_COUNT;
		
		/// <summary>
		/// Dragon Scales Loot Generator Drop Base Chance
		/// </summary>
		[ServerProperty("pve", "lootgenerator_dragonscales_base_chance", "Base chance for dropping Dragon Scales using Loot Generator.", 15)]
		public static int LOOTGENERATOR_DRAGONSCALES_BASE_CHANCE;
		
		/// <summary>
		/// Dragon Scales Loot Generator Named Boost Count
		/// </summary>
		[ServerProperty("pve", "lootgenerator_dragonscales_named_count", "Multiplier for number of scales dropped from named mobs, including named dragons.  Must be an integer.", 2)]
		public static int LOOTGENERATOR_DRAGONSCALES_NAMED_COUNT;	
		
		/// <summary>
		/// Dreaded Seals Loot Generator Starting Level
		/// </summary>
		[ServerProperty("pve", "lootgenerator_dreadedseals_starting_level", "Mob level to start dropping Dreaded Glowing Seals", 25)]
		public static int LOOTGENERATOR_DREADEDSEALS_STARTING_LEVEL;

		/// <summary>
		/// Dreaded Seals Loot Generator Drop Chance Per Level
		/// </summary>
		[ServerProperty("pve", "lootgenerator_dreadedseals_drop_chance_per_level", "Increase in Dreaded Glowing Seal drop chance per level, in hundredths of a percent.", 25)]
		public static int LOOTGENERATOR_DREADEDSEALS_DROP_CHANCE_PER_LEVEL;

		/// <summary>
		/// Dreaded Seals Loot Generator Base Chance
		/// </summary>
		[ServerProperty("pve", "lootgenerator_dreadedseals_base_chance", "Base chance to drop a Dreaded Seal, in hundredths of a percent", 25)]
		public static int LOOTGENERATOR_DREADEDSEALS_BASE_CHANCE;

		/// <summary>
		/// Dreaded Seals Loot Generator Named Boost Chance
		/// </summary>
		[ServerProperty("pve", "lootgenerator_dreadedseals_named_chance", "Increase chance of Dreaded Seals Loot Generator drop for Named mobs. (count * lootgenerator_dreadedseals_named_chance)", 1.5)]
		public static double LOOTGENERATOR_DREADEDSEALS_NAMED_CHANCE;

		/// <summary>
		/// Dreaded Seal multipliers by level
		/// </summary>
		[ServerProperty("pve", "dreadedseals_level_multiplier", "Level based multipliers for RPs and BPs awarded when turning in dreaded seals.", "21|2;26|3;31|5;36|30;41|70;46|150;50|300")]
		public static string DREADEDSEALS_LEVEL_MULTIPLIER;

		/// <summary>
		/// Dreaded Seal RP values before level multiplier and BP rate
		/// </summary>
		[ServerProperty("pve", "dreadedseals_bp_values", "BP values of dreaded seal types before level multiplier and BP rate is applied.", "glowing_dreaded_seal|3.334;sanguine_dreaded_seal|3.334;lambent_dreaded_seal|33.334;lambent_dreaded_seal2|33.334;fulgent_dreaded_seal|166.667;effulgent_dreaded_seal|833.334")]
		public static string DREADEDSEALS_BP_VALUES;

		/// <summary>
		/// Dreaded Seal BP values before level multiplier and RP rate
		/// </summary>
		[ServerProperty("pve", "dreadedseals_rp_values", "RP values of dreaded seal types before level multiplier and RP rate is applied.", "glowing_dreaded_seal|10;sanguine_dreaded_seal|10;lambent_dreaded_seal|100;lambent_dreaded_seal2|100;fulgent_dreaded_seal|500;effulgent_dreaded_seal|2500")]
		public static string DREADEDSEALS_RP_VALUES;

		/// <summary>
		/// PvE Experience Loss Start Level
		/// </summary>
		[ServerProperty("pve", "pve_exp_loss_level", "Which level should players killed in PvE start losing experience?", (byte)6)]
		public static byte PVE_EXP_LOSS_LEVEL;

		/// <summary>
		/// PvE Conn Loss Start Level
		/// </summary>
		[ServerProperty("pve", "pve_con_loss_level", "Which level should players killed in PvE start losing constitution?", (byte)6)]
		public static byte PVE_CON_LOSS_LEVEL;

		#endregion

		#region HOUSING
		/// <summary>
		/// Maximum number of houses supported on this server.  Limits the size of the housing array used for updates
		/// </summary>
		[ServerProperty("housing", "max_num_houses", "Max number of houses supported on this server.", 5000)]
		public static int MAX_NUM_HOUSES;

		/// <summary>
		/// The starting NPCTemplate ID to use for housing NPC's
		/// </summary>
		[ServerProperty("housing", "housing_starting_npctemplate_id", "The starting NPCTemplate ID to use for housing NPC's", 500)]
		public static int HOUSING_STARTING_NPCTEMPLATE_ID;

		/// <summary>
		/// Sets the max allowed items inside a house.
		/// </summary>
		[ServerProperty("housing", "max_indoor_house_items", "Max number of items allowed inside a players house.", 40)]
		public static int MAX_INDOOR_HOUSE_ITEMS;

		/// <summary>
		/// Max outdoor items.  If Outdoor is increased past 30 they vanish. It seems to be hardcoded in client
		/// </summary>
		[ServerProperty("housing", "max_outdoor_house_items", "Max number of items allowed in a players garden.", 30)]
		public static int MAX_OUTDOOR_HOUSE_ITEMS;

		[ServerProperty("housing", "indoor_items_depend_on_size", "If true the max number of allowed House indoor items are set like live (40, 60, 80, 100)", true)]
		public static bool INDOOR_ITEMS_DEPEND_ON_SIZE;

		[ServerProperty("housing", "housing_rent_cottage", "Rent price for a cottage.", 20L * 100L * 100L)] // 20g
		public static long HOUSING_RENT_COTTAGE;

		[ServerProperty("housing", "housing_rent_house", "Rent price for a house.", 35L * 100L * 100L)] // 35g
		public static long HOUSING_RENT_HOUSE;

		[ServerProperty("housing", "housing_rent_villa", "Rent price for a villa.", 60L * 100L * 100L)] // 60g
		public static long HOUSING_RENT_VILLA;

		[ServerProperty("housing", "housing_rent_mansion", "Rent price for a mansion.", 100L * 100L * 100L)] // 100g
		public static long HOUSING_RENT_MANSION;

		[ServerProperty("housing", "housing_lot_price_start", "Starting lot price before per hour reductions", 95L * 1000L * 100L * 100L)] // 95p
		public static long HOUSING_LOT_PRICE_START;

		[ServerProperty("housing", "housing_lot_price_per_hour", "Lot price reduction per hour.", (long)(1.2 * 1000 * 100 * 100))] // 1.2p
		public static long HOUSING_LOT_PRICE_PER_HOUR;

		[ServerProperty("housing", "housing_lot_price_minimum", "Minimum lot price.", 300L * 100L * 100L)] // 300g
		public static long HOUSING_LOT_PRICE_MINIMUM;

		/// <summary>
		/// How often, in days, is rent due?  0 for never, negative for testing repossession
		/// </summary>
		[ServerProperty("housing", "rent_due_days", "How often, in days, is rent due?  0 for never, negative for testing repossession.", 7)]
		public static int RENT_DUE_DAYS;

		/// <summary>
		/// How many rent payments can be stored in the lockbox?
		/// </summary>
		[ServerProperty("housing", "rent_lockbox_payments", "How many rent payments can be stored in the lockbox?", 4)]
		public static int RENT_LOCKBOX_PAYMENTS;

		/// <summary>
		/// The worth of 1 (one) bounty point in gold (e.g. 1 bp = 1g -> 10000, 1bp = 10g -> 100000)
		/// </summary>
		[ServerProperty("housing", "rent_bounty_point_to_gold", "The worth of 1 (one) bounty point in gold (e.g. 1 bp = 1g -> 10000, 1bp = 10g -> 100000)", 10000)]
		public static long RENT_BOUNTY_POINT_TO_GOLD;

		/// <summary>
		/// Do housing consignment merchants use BP instead of money?
		/// </summary>
		[ServerProperty("housing", "consignment_use_bp", "If true the housing consignment merchants use BP instead of money.", false)]
		public static bool CONSIGNMENT_USE_BP;

		/// <summary>
		/// Enable consignment merchants and market cache
		/// </summary>
		[ServerProperty("housing", "market_enabled", "If true the market explorers are enabled and the cache is initialized on server start.", true)]
		public static bool MARKET_ENABLED;

		/// <summary>
		/// Enable consignment merchants and market cache
		/// </summary>
		[ServerProperty("housing", "market_enable", "If true the market explorers are enabled and the cache is initialized on server start.", true)]
		public static bool MARKET_ENABLE;

		/// <summary>
		/// Enable logging of all market activity
		/// </summary>
		[ServerProperty("housing", "market_enable_log", "Enable debug logging of all market activity", false)]
		public static bool MARKET_ENABLE_LOG;

		/// <summary>
		/// What is the additional fee (%) charged to players using the market explorer?
		/// </summary>
		[ServerProperty("housing", "market_fee_percent", "What is the additional fee (%) charged to players using the market explorer?", 20)]
		public static int MARKET_FEE_PERCENT;

		/// <summary>
		/// How many items can the market search return?
		/// </summary>
		[ServerProperty("housing", "market_search_limit", "How many items can the market search return?", 300)]
		public static int MARKET_SEARCH_LIMIT;

		#endregion

		#region CLASSES
		/// <summary>
		/// Allow players to /train without having a trainer present
		/// </summary>
		[ServerProperty("classes", "allow_train_anywhere", "Allow players to use the /train command to open a trainer window anywhere in the world?", true)]
		public static bool ALLOW_TRAIN_ANYWHERE;

		/// <summary>
		/// Allow players to /train without having a trainer present
		/// </summary>
		[ServerProperty("classes", "allow_vault_command", "Allow players to use the /vault command to open the player's vault anywhere in the world?", false)]
		public static bool ALLOW_VAULT_COMMAND;

		/// <summary>
		/// Disable some classes from being created
		/// </summary>
		[ServerProperty("classes", "disabled_classes", "Serialized list of disabled classes, separated by semi-colon or a range with a dash (ie 1-5;7;9)", "")]
		public static string DISABLED_CLASSES;

		/// <summary>
		/// Disable some races from being created
		/// </summary>
		[ServerProperty("classes", "disabled_races", "Serialized list of disabled races, separated by semi-colon or a range with a dash (ie 1-5;7;9)", "")]
		public static string DISABLED_RACES;

		/// <summary>
		/// Days before your eligible for a free level in Albion
		/// </summary>
		[ServerProperty("classes", "freelevel_days_albion", "days before your eligible for a free level in Albion, use -1 to deactivate", 7)]
		public static int FREELEVEL_DAYS_ALBION;
		
		/// <summary>
		/// Days before your eligible for a free level in Midgard
		/// </summary>
		[ServerProperty("classes", "freelevel_days_midgard", "days before your eligible for a free level in Midgard, use -1 to deactivate", 7)]
		public static int FREELEVEL_DAYS_MIDGARD;

		/// <summary>
		/// Days before your eligible for a free level in Hibernia
		/// </summary>
		[ServerProperty("classes", "freelevel_days_hibernia", "days before your eligible for a free level in Hibernia, use -1 to deactivate", 7)]
		public static int FREELEVEL_DAYS_HIBERNIA;

		[ServerProperty("classes", "concentration_buff_range", "The range at which concentration buffs get disabled. 0 for unlimited.", 5000)]
		public static int CONCENTRATION_BUFF_RANGE;

		[ServerProperty("classes", "endurance_concentration_buff_range", "The range at which endurance concentration buffs get disabled. 0 for unlimited.", 1500)]
		public static int ENDURANCE_CONCENTRATION_BUFF_RANGE;

		/// <summary>
		/// Allow Cata Slash Level
		/// </summary>
		[ServerProperty("classes", "allow_cata_slash_level", "Allow catacombs classes to use /level command", false)]
		public static bool ALLOW_CATA_SLASH_LEVEL;

		/// <summary>
		/// Sets the Cap for Player Turrets
		/// </summary>
		[ServerProperty("classes", "turret_player_cap_count", "Sets the cap of turrets for a Player", 12)]
		public static int TURRET_PLAYER_CAP_COUNT;

		/// <summary>
		/// Sets the Area Cap for Turrets
		/// </summary>
		[ServerProperty("classes", "turret_area_cap_count", "Sets the cap of the Area for turrets", 10)]
		public static int TURRET_AREA_CAP_COUNT;

		/// <summary>
		/// Sets the Circle of the Area to check for Turrets
		/// </summary>
		[ServerProperty("classes", "turret_area_cap_radius", "Sets the Radius which is checked for the turret area cap", 1000)]
		public static int TURRET_AREA_CAP_RADIUS;

		[ServerProperty("classes", "theurgist_pet_cap", "Sets the maximum number of pets a Theurgist can summon", 16)]
		public static int THEURGIST_PET_CAP;

		/// <summary>
		/// Do we want to allow items to be equipped regardless of realm?
		/// </summary>
		[ServerProperty("classes", "allow_cross_realm_items", "Do we want to allow items to be equipped regardless of realm?", false)]
		public static bool ALLOW_CROSS_REALM_ITEMS;

		/// <summary>
		/// What level should /level bring you to? 0 to disable
		/// </summary>
		[ServerProperty("classes", "slash_level_target", "What level should /level bring you to? 0 is disabled.", 0)]
		public static int SLASH_LEVEL_TARGET;

		/// <summary>
		/// What level should you have on your account to be able to use /level?
		/// </summary>
		[ServerProperty("classes", "slash_level_requirement", "What level should you have on your account be able to use /level?", 50)]
		public static int SLASH_LEVEL_REQUIREMENT;

		/// <summary>
		/// Should we allow archers to be able to use arrows from their quiver?
		/// </summary>
		[ServerProperty("classes", "allow_old_archery", "Should we allow archers to be able to use arrows from their quiver?", true)]
		public static bool ALLOW_OLD_ARCHERY;

		/// <summary>
		/// Level at which res sickness starts to apply
		/// </summary>
		[ServerProperty("classes", "ress_sickness_level", "What level should ress sickness start to apply?", (byte)6)]
		public static byte RESS_SICKNESS_LEVEL;

		[ServerProperty("classes", "volley_roof_check", "Enables roof obstruction checks for Volley", false)]
		public static bool VOLLEY_ROOF_CHECK;

		[ServerProperty("classes", "ground_target_snap_max_distance", "Max snap distance for ground-targets onto a walkable surface. Failed checks invalidate the ground target. (0 = disabled)", 16f)]
		public static float GROUND_TARGET_SNAP_MAX_DISTANCE;

		#endregion

		#region SPELLS

		/// <summary>
		/// Spells-related properties
		/// </summary>
		[ServerProperty("spells", "spell_interrupt_duration", "", 3000)]
		public static int SPELL_INTERRUPT_DURATION;

		[ServerProperty("spells", "spell_charm_named_check", "Prevents charm spell to work on Named Mobs, 0 = disable, 1 = enable", 1)]
		public static int SPELL_CHARM_NAMED_CHECK;

		#endregion

		#region GUILDS / ALLIANCES
		/// <summary>
		/// The max number of guilds in an alliance
		/// </summary>
		[ServerProperty("guild", "alliance_max", "Max Guilds In Alliance - Edit this to change the maximum number of guilds in an alliance -1 = unlimited, 0=disable alliances", -1)]
		public static int ALLIANCE_MAX;

		/// <summary>
		/// The number of players needed to form a guild
		/// </summary>
		[ServerProperty("guild", "guild_num", "Players Needed For Guild Form - Edit this to change the amount of players required to form a guild", 8)]
		public static int GUILD_NUM;

		/// <summary>
		/// This enables or disables new guild dues.
		/// </summary>
		[ServerProperty("guild", "new_guild_dues", "Guild dues can be set from 1-100% if enabled, or standard 2% if not", true)]
		public static bool NEW_GUILD_DUES;

		/// <summary>
		/// This sets the guild dues max value to 0~100%.
		/// </summary>
		[ServerProperty("guild", "guild_dues_max_value", "Guild dues can be set from 1-100%", 25)]
		public static int GUILD_DUES_MAX_VALUE;

		/// <summary>
		/// Do we allow guild members from other realms
		/// </summary>
		[ServerProperty("guild", "allow_cross_realm_guilds", "Do we allow guild members from other realms?", false)]
		public static bool ALLOW_CROSS_REALM_GUILDS;

		/// <summary>
		/// How many things do we allow guilds to claim?
		/// </summary>
		[ServerProperty("guild", "guilds_claim_limit", "How many things do we allow guilds to claim?", 1)]
		public static int GUILDS_CLAIM_LIMIT;

		/// <summary>
		/// Guild Crafting Buff bonus amount
		/// </summary>
		[ServerProperty("guild", "guild_buff_crafting", "Percent speed gain for the guild crafting buff?", (ushort)5)]
		public static ushort GUILD_BUFF_CRAFTING;

		/// <summary>
		/// Guild XP Buff bonus amount
		/// </summary>
		[ServerProperty("guild", "guild_buff_xp", "Extra XP gain percent for the guild PvE XP buff?", (ushort)5)]
		public static ushort GUILD_BUFF_XP;

		/// <summary>
		/// Guild RP Buff bonus amount
		/// </summary>
		[ServerProperty("guild", "guild_buff_rp", "Extra RP gain percent for the guild RP buff?", (ushort)2)]
		public static ushort GUILD_BUFF_RP;

		/// <summary>
		/// Guild BP Buff bonus amount -  this is not available on live, disabled by default
		/// </summary>
		[ServerProperty("guild", "guild_buff_bp", "Extra BP gain percent for the guild BP buff?", (ushort)0)]
		public static ushort GUILD_BUFF_BP;

		/// <summary>
		/// Guild artifact XP Buff bonus amount
		/// </summary>
		[ServerProperty("guild", "guild_buff_artifact_xp", "Extra artifact XP gain percent for the guild artifact XP buff?", (ushort)5)]
		public static ushort GUILD_BUFF_ARTIFACT_XP;

		/// <summary>
		/// Guild masterlevel XP Buff bonus amount
		/// </summary>
		[ServerProperty("guild", "guild_buff_masterlevel_xp", "Extra masterlevel XP gain percent for the guild masterlevel XP buff?", (ushort)20)]
		public static ushort GUILD_BUFF_MASTERLEVEL_XP;

		/// <summary>
		/// How much merit to reward guild when dragon is killed, if any.
		/// </summary>
		[ServerProperty("guild", "guild_merit_on_dragon_kill", "How much merit to reward guild when dragon is killed, if any.", (ushort)0)]
		public static ushort GUILD_MERIT_ON_DRAGON_KILL;
		
		/// <summary>
		/// How much merit to reward guild when legion is killed, if any.
		/// </summary>
		[ServerProperty("guild", "guild_merit_on_legion_kill", "How much merit to reward guild when legion is killed, if any.", (ushort)0)]
		public static ushort GUILD_MERIT_ON_LEGION_KILL;

		/// <summary>
		/// When a banner is lost to the enemy how long is the wait before purchase is allowed?  In Minutes.
		/// </summary>
		[ServerProperty("guild", "guild_banner_lost_time", "When a banner is lost to the enemy how many minutes is the wait before purchase is allowed?", (ushort)1440)]
		public static ushort GUILD_BANNER_LOST_TIME;



		#endregion

		#region CRAFT / SALVAGE

		/// <summary>
		/// The crafting sellback price control at each craft (calculate a percent of raw materials used)
		/// </summary>
		[ServerProperty("craft", "crafting_adjust_product_price", "Change price to recommended value in database for product itemtemplate", false)]
		public static bool CRAFTING_ADJUST_PRODUCT_PRICE;
		/// <summary>
		/// The crafting price control for secondary craft (trinketing) modifier
		/// </summary>
		[ServerProperty("craft", "crafting_secondary_sellback_percent", "How many percent of raw materials cost is SellBack values", 98.572)]
		public static double CRAFTING_SECONDARYCRAFT_SELLBACK_PERCENT;
		/// <summary>
		/// The crafting price control for craft modifier
		/// </summary>
		[ServerProperty("craft", "crafting_sellback_percent", "How many percent of raw materials cost is SellBack values", 95)]
		public static int CRAFTING_SELLBACK_PERCENT;
		/// <summary>
		/// The crafting speed modifier
		/// </summary>
		[ServerProperty("craft", "crafting_speed", "Crafting Speed Modifier - Edit this to change the speed at which you craft e.g 1.5 is 50% faster 2.0 is twice as fast (100%) 0.5 is half the speed (50%)", 1.0)]
		public static double CRAFTING_SPEED;

		/// <summary>
		/// Crafting skill gain bonus in capital cities
		/// </summary>
		[ServerProperty("craft", "capital_city_crafting_skill_gain_bonus", "Crafting skill gain bonus % in capital cities; 5 = 5%", 5)]
		public static int CAPITAL_CITY_CRAFTING_SKILL_GAIN_BONUS;

		/// <summary>
		/// Crafting speed bonus in capital cities
		/// </summary>
		[ServerProperty("craft", "capital_city_crafting_speed_bonus", "Crafting speed bonus in capital cities; 2 = 2x, 3 = 3x, ..., 1 = standard", 1.0)]
		public static double CAPITAL_CITY_CRAFTING_SPEED_BONUS;
		
		/// <summary>
		/// Crafting speed bonus in capital cities
		/// </summary>
		[ServerProperty("craft", "keep_crafting_speed_bonus", "Crafting speed bonus in the keeps; 2 = 2x, 3 = 3x, ..., 1 = standard", 1.0)]
		public static double KEEP_CRAFTING_SPEED_BONUS;

		/// <summary>
		/// Allow any realm to craft items with a realm of 0 (no realm)
		/// </summary>
		[ServerProperty("craft", "allow_craft_norealm_items", "Allow any realm to craft items with 0 (no) realm.", false)]
		public static bool ALLOW_CRAFT_NOREALM_ITEMS;

		/// <summary>
		/// Max character crafting skill?
		/// </summary>
		[ServerProperty("craft", "crafting_max_skills", "Set character crafting skills to max level.", false)]
		public static bool CRAFTING_MAX_SKILLS;
		
		/// <summary>
		/// Max character crafting skill?
		/// </summary>
		[ServerProperty("craft", "crafting_max_skills_amount", "The amount to which set the crafting skills when using crafting_max_skills", 1)]
		public static int CRAFTING_MAX_SKILLS_AMOUNT;

		/// <summary>
		/// Use salvage per realm and get back material to use in chars realm
		/// </summary>
		[ServerProperty("salvage", "use_salvage_per_realm", "Enable to get back material to use in chars realm. Disable to get back the same material in all realms.", false)]
		public static bool USE_SALVAGE_PER_REALM;

		/// <summary>
		/// Use salvage per realm and get back material to use in chars realm
		/// </summary>
		[ServerProperty("salvage", "use_new_salvage", "Enable to use a new system calcul of salvage count based on object_type.", false)]
		public static bool USE_NEW_SALVAGE;

		#endregion

		#region ACCOUNT
		/// <summary>
		/// Allow auto-account creation  This is also set in serverconfig.xml and must be enabled for this property to work.
		/// </summary>
		[ServerProperty("account", "allow_auto_account_creation", "Allow auto-account creation  This is also set in serverconfig.xml and must be enabled for this property to work.", true)]
		public static bool ALLOW_AUTO_ACCOUNT_CREATION;

		/// <summary>
		/// Account bombing prevention
		/// </summary>
		[ServerProperty("account", "time_between_account_creation", "The time in minutes between 2 accounts creation. This avoid account bombing with dynamic ip. 0 to disable", 0)]
		public static int TIME_BETWEEN_ACCOUNT_CREATION;

		/// <summary>
		/// Account IP bombing prevention
		/// </summary>
		[ServerProperty("account", "time_between_account_creation_sameip", "The time in minutes between accounts creation from the same ip.", 15)]
		public static int TIME_BETWEEN_ACCOUNT_CREATION_SAMEIP;

		/// <summary>
		/// Total number of account allowed for the same IP
		/// </summary>
		[ServerProperty("account", "total_accounts_allowed_sameip", "Total number of account allowed for the same IP", 20)]
		public static int TOTAL_ACCOUNTS_ALLOWED_SAMEIP;

		#endregion

		#region ATLAS
		/// <summary>
		/// Allow claiming of BG keeps
		/// </summary>
		[ServerProperty("atlas", "allow_bg_claim", "Allow claiming of BG keeps", false)]
		public static bool ALLOW_BG_CLAIM;

		/// <summary>
		/// Enables the API endpoints on the configured API port.
		/// </summary>
		[ServerProperty("atlas", "atlas_api", "Enables the API endpoints on the configured API port", false)]
		public static bool ATLAS_API;
		
		/// <summary>
		/// Maximum number of charges allowed
		/// </summary>
		[ServerProperty("atlas", "max_charge_items", "Maximum number of charges allowed", 2)]
		public static int MAX_CHARGE_ITEMS;
		
		/// <summary>
		/// Maximum numbers of entities allowed
		/// </summary>
		[ServerProperty("server", "max_entities", "Maximum numbers of entities allowed", 150000)]
		public static int MAX_ENTITIES;

		/// <summary>
		/// Enforces the check on the link between game account and Discord
		/// </summary>
		[ServerProperty("atlas", "force_discord_link", "Enforces the check on the link between game account and Discord", false)]
		public static bool FORCE_DISCORD_LINK;

		/// <summary>
		/// Set the password to access certain API commands as shutdown
		/// </summary>
		[ServerProperty("atlas", "api_password", "Set the password to access certain API commands as shutdown", "")]
		public static string API_PASSWORD;

		[ServerProperty("atlas", "enable_corpsesummoner", "Whether or not to enable the corpse summoner command", true)]
		public static bool ENABLE_CORPSESUMONNER;

		[ServerProperty("atlas", "salvage_yield_multiplier", "The salvage yield multiplier", 0.5)]
		public static double SALVAGE_YIELD_MULTIPLIER;

		[ServerProperty("atlas", "max_craft_time", "The maximum craft time allowed in seconds. All timers above this value will be normalised to the input value", 0)]
		public static int MAX_CRAFT_TIME;
		
		[ServerProperty("atlas", "of_teleport_interval", "The seconds between OF porting ceremonies", 120)]
		public static int OF_REPORT_INTERVAL;

		[ServerProperty("atlas", "patch_notes_url", "The URL of the remote patch notes .txt to display with /sn", "")]
		public static string PATCH_NOTES_URL;

		[ServerProperty("atlas", "immunity_timer_use_adaptive", "toggle adaptive vs. flat immunity timers", false)]
		public static bool IMMUNITY_TIMER_USE_ADAPTIVE;

		[ServerProperty("atlas", "immunity_timer_flat_length", "if non-adapative timers, the duration (in seconds) for immunity", 60)]
		public static int IMMUNITY_TIMER_FLAT_LENGTH;

		[ServerProperty("atlas", "immunity_timer_adaptive_length", "if adapative timers, the modifer to apply to length (i.e. stun length * 6)", 6)]
		public static int IMMUNITY_TIMER_ADAPTIVE_LENGTH;

		#endregion

		#region RANDOM OBJECT GENERATION

		[ServerProperty("atlas_rog", "rog_toa_item_chance", "chance of generating an object with TOA stats (in %)", 0)]
		public static int ROG_TOA_ITEM_CHANCE;
		
		[ServerProperty("atlas_rog", "rog_armor_weight", "chance of armor being included in the roll (in %)", 50)]
		public static int ROG_ARMOR_WEIGHT;

		[ServerProperty("atlas_rog", "rog_magical_weight", "chance of jewelry/magical being included in the roll (in %)", 40)]
		public static int ROG_MAGICAL_WEIGHT;

		[ServerProperty("atlas_rog", "rog_weapon_weight", "chance of weapons being included in the roll (in %)", 40)]
		public static int ROG_WEAPON_WEIGHT;

		[ServerProperty("atlas_rog", "rog_starting_qual", "base item quality (in %)", 95)]
		public static int ROG_STARTING_QUAL;

		[ServerProperty("atlas_rog", "rog_cap_qual", "max item quality (in %)", 99)]
		public static int ROG_CAP_QUAL;

		//don't put this above 35-45 or you will get way too many
		[ServerProperty("atlas_rog", "rog_toa_stat_weight", "toa specific stat weight (in %)", 0)]
		public static int ROG_TOA_STAT_WEIGHT;

		[ServerProperty("atlas_rog", "rog_item_stat_weight", "stat bonus (str, con, dex, etc) weight (in %)", 45)]
		public static int ROG_ITEM_STAT_WEIGHT;

		[ServerProperty("atlas_rog", "rog_item_resist_weight", "resist bonus (body, matter, etc) weight (in %)", 48)]
		public static int ROG_ITEM_RESIST_WEIGHT;

		[ServerProperty("atlas_rog", "rog_item_skill_weight", "skill bonus (Celtic Spear, Dual Wield, etc) weight (in %)", 25)]
		public static int ROG_ITEM_SKILL_WEIGHT;

		[ServerProperty("atlas_rog", "rog_item_allskill_weight", "all skills bonus weight (in %)", 0)]
		public static int ROG_STAT_ALLSKILL_WEIGHT;

		[ServerProperty("atlas_rog", "rog_magical_item_offset", "base chance to get a magical RoG item (in %) [Level*2 is added to get final value]", 60)]
		public static int ROG_MAGICAL_ITEM_OFFSET;

		[ServerProperty("atlas_rog", "rog_use_weighted_generation", "toggle weighted rolls vs. simple generation", false)]
		public static bool ROG_USE_WEIGHTED_GENERATION;

		#endregion

		#region CONTROLS_AUTOMATION

		[ServerProperty("controls_automation", "auto_select_opening_style", "Automatically perform the opening style of the currently selected style if conditions are not met (recursive).", false)]
		public static bool AUTO_SELECT_OPENING_STYLE;

		[ServerProperty("controls_automation", "allow_auto_backup_styles", "Allow players to set a style to be used automatically with /backupstyle.", false)]
		public static bool ALLOW_AUTO_BACKUP_STYLES;

		[ServerProperty("controls_automation", "allow_non_anytime_backup_styles", "If /backupstyle is enabled, can players set a non-anytime style as their backup?", false)] 
		public static bool ALLOW_NON_ANYTIME_BACKUP_STYLES;

		#endregion

		public static IDictionary<string, object> AllCurrentProperties { get; private set; }

		/// <summary>
		/// Get a Dictionary that tracks all Properties by Key String
		/// Returns the ServerPropertyAttribute, the Static Field with current Value, and the according DataObject
		/// Create a default dataObject if value wasn't found in Database
		/// </summary>
		public static IDictionary<string, Tuple<ServerPropertyAttribute, FieldInfo, DbServerProperty>> AllDomainProperties
		{
			get
			{
				var result = new Dictionary<string, Tuple<ServerPropertyAttribute, FieldInfo, DbServerProperty>>();
				var allProperties = GameServer.Database.SelectAllObjects<DbServerProperty>();
				
				foreach (Assembly asm in AppDomain.CurrentDomain.GetAssemblies())
				{
					foreach (Type type in asm.GetTypes())
					{
						foreach (FieldInfo fld in type.GetFields())
						{
							// Properties are Static
							if (!fld.IsStatic)
								continue;
							
							// Properties shoud contain a property attribute
							object[] attribs = fld.GetCustomAttributes(typeof(ServerPropertyAttribute), false);
							if (attribs.Length == 0)
								continue;
							
							ServerPropertyAttribute att = (ServerPropertyAttribute)attribs[0];
							
							DbServerProperty serverProp = allProperties.Where(p => p.Key.Equals(att.Key, StringComparison.OrdinalIgnoreCase)).FirstOrDefault();
							
							if (serverProp == null)
							{
								// Init DB Object
								serverProp = new DbServerProperty();
								serverProp.Category = att.Category;
								serverProp.Key = att.Key;
								serverProp.Description = att.Description;
								if (att.DefaultValue is double)
								{
									CultureInfo myCIintl = new CultureInfo("en-US", false);
									IFormatProvider provider = myCIintl.NumberFormat;
									serverProp.DefaultValue = ((double)att.DefaultValue).ToString(provider);
								}
								else
								{
									serverProp.DefaultValue = att.DefaultValue.ToString();
								}
								serverProp.Value = serverProp.DefaultValue;
							}
							
							result[att.Key] = new Tuple<ServerPropertyAttribute, FieldInfo, DbServerProperty>(att, fld, serverProp);
						}
					}
				}

				return result;
			}
		}
		
		/// <summary>
		/// This method loads the property from the database and returns
		/// the value of the property as strongly typed object based on the
		/// type of the default value
		/// </summary>
		/// <param name="attrib">The attribute</param>
		/// <returns>The real property value</returns>
		public static void Load(ServerPropertyAttribute attrib, FieldInfo field, DbServerProperty prop)
		{
			string key = attrib.Key;
			
			// Not Added to database...
			if (!prop.IsPersisted)
			{
				GameServer.Database.AddObject(prop);

				if (log.IsDebugEnabled)
					log.DebugFormat("Cannot find server property {0} creating it", key);
			}
			
			if (log.IsDebugEnabled)
				log.DebugFormat("Loading {0} Value is {1}", key, prop.Value);
			
			try
			{
				if (field.IsInitOnly && log.IsWarnEnabled)
					log.WarnFormat("Property {0} is ReadOnly, Value won't be changed - {1} !", key, field.GetValue(null));
				
				//we do this because we need "1.0" to be considered double sometimes its "1,0" in other countries
				CultureInfo myCIintl = new CultureInfo("en-US", false);
				IFormatProvider provider = myCIintl.NumberFormat;
				field.SetValue(null, Convert.ChangeType(prop.Value, attrib.DefaultValue.GetType(), provider));
			}
			catch (Exception e)
			{
				if (log.IsErrorEnabled)
				{
					log.ErrorFormat("Exception in ServerProperties Load: {0}", e);
					log.ErrorFormat("Trying to load {0} value is {1}", key, prop.Value);
				}
			}
		}

		/// <summary>
		/// Refreshes the server properties from the DB
		/// </summary>
		public static void Refresh()
		{
			if (log.IsInfoEnabled)
				log.Info("Refreshing server properties...");

			InitProperties();
		}

		/// <summary>
		/// Irreversibly removes rogue properties from the Database.
		/// </summary>
		public static void CleanUpDatabase()
		{
			IList<DbServerProperty> dbProperties = GameServer.Database.SelectAllObjects<DbServerProperty>();
			List<string> properties = [];

			foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
			{
				foreach (Type type in assembly.GetTypes())
				{
					foreach (FieldInfo field in type.GetFields())
					{
						// Properties are static.
						if (!field.IsStatic)
							continue;

						// Properties should contain a property attribute.
						object[] attributes = field.GetCustomAttributes(typeof(ServerPropertyAttribute), false);

						if (attributes.Length == 0)
							continue;

						properties.Add(((ServerPropertyAttribute) attributes[0]).Key);
					}
				}
			}

			foreach (DbServerProperty dbProperty in dbProperties)
			{
				if (properties.Contains(dbProperty.Key))
					continue;

				try
				{
					GameServer.Database.DeleteObject(dbProperty);

					if (log.IsInfoEnabled)
						log.Info($"Removed rogue property: {dbProperty.Key} ({dbProperty.Value}).");
				}
				catch
				{
					if (log.IsErrorEnabled)
						log.Error($"Couldn't remove rogue property: {dbProperty.Key} ({dbProperty.Value}).");
				}
			}
		}
	}
}
