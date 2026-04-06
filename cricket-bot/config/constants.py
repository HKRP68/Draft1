"""Game constants for the Cricket Simulator Bot."""

# ═══════════════════════════════════════════════════════════════
# Rating Tiers
# ═══════════════════════════════════════════════════════════════

RATING_TIERS = {
    (95, 100): {"name": "Legendary", "color": "#FFD700", "emoji": "🏆"},
    (90, 94):  {"name": "Elite", "color": "#FF4500", "emoji": "🔥"},
    (85, 89):  {"name": "Diamond", "color": "#00BFFF", "emoji": "💎"},
    (80, 84):  {"name": "Gold", "color": "#DAA520", "emoji": "🥇"},
    (75, 79):  {"name": "Silver", "color": "#C0C0C0", "emoji": "🥈"},
    (68, 74):  {"name": "Bronze", "color": "#CD7F32", "emoji": "🥉"},
    (59, 67):  {"name": "Iron", "color": "#808080", "emoji": "⚙️"},
    (50, 58):  {"name": "Common", "color": "#A9A9A9", "emoji": "📦"},
}

# ═══════════════════════════════════════════════════════════════
# Player Categories
# ═══════════════════════════════════════════════════════════════

PLAYER_CATEGORIES = ["Batsman", "Bowler", "All-rounder", "Wicket Keeper"]

BATTING_HANDS = ["Right", "Left"]

BOWLING_HANDS = ["Right", "Left"]

BOWL_STYLES = ["Fast", "Off Spinner", "Leg Spinner", "Medium Pacer"]

# ═══════════════════════════════════════════════════════════════
# Cooldown Settings (in seconds)
# ═══════════════════════════════════════════════════════════════

COOLDOWN_CLAIM = 3600       # 1 hour
COOLDOWN_DAILY = 86400      # 24 hours
COOLDOWN_GSPIN = 28800      # 8 hours

# ═══════════════════════════════════════════════════════════════
# Reward Settings
# ═══════════════════════════════════════════════════════════════

DEBUT_INITIAL_COINS = 5000
DEBUT_INITIAL_GEMS = 100
DEBUT_PLAYERS_TOTAL = 8

CLAIM_REWARD_COINS = 500
DAILY_REWARD_COINS = 5000
DAILY_REWARD_PLAYERS = 2

MAX_ROSTER_SIZE = 25

# ═══════════════════════════════════════════════════════════════
# Debut Player Distribution
# ═══════════════════════════════════════════════════════════════

DEBUT_PLAYER_DISTRIBUTION = [
    {"count": 1, "min_rating": 83, "max_rating": 85},
    {"count": 3, "min_rating": 75, "max_rating": 80},
    {"count": 4, "min_rating": 50, "max_rating": 74},
]

# ═══════════════════════════════════════════════════════════════
# /claim Rarity Distribution (cumulative weights)
# ═══════════════════════════════════════════════════════════════

CLAIM_RARITY_DISTRIBUTION = [
    {"min_rating": 50, "max_rating": 58, "weight": 31.0},
    {"min_rating": 59, "max_rating": 67, "weight": 20.0},
    {"min_rating": 68, "max_rating": 76, "weight": 26.0},
    {"min_rating": 77, "max_rating": 80, "weight": 10.0},
    {"min_rating": 81, "max_rating": 85, "weight": 8.0},
    {"min_rating": 86, "max_rating": 94, "weight": 4.5},
    {"min_rating": 95, "max_rating": 100, "weight": 0.5},
]

# ═══════════════════════════════════════════════════════════════
# /gspin Wheel Outcomes
# ═══════════════════════════════════════════════════════════════

GSPIN_OUTCOMES = [
    {
        "name": "Red",
        "emoji": "🟥",
        "weight": 55.0,
        "type": "coins",
        "min_amount": 5000,
        "max_amount": 10000,
    },
    {
        "name": "Yellow",
        "emoji": "🟨",
        "weight": 30.0,
        "type": "player",
        "min_rating": 79,
        "max_rating": 85,
    },
    {
        "name": "Blue",
        "emoji": "🟦",
        "weight": 12.0,
        "type": "gems",
        "min_amount": 10,
        "max_amount": 50,
    },
    {
        "name": "Green",
        "emoji": "🟩",
        "weight": 2.5,
        "type": "player",
        "min_rating": 85,
        "max_rating": 90,
    },
    {
        "name": "Purple",
        "emoji": "⭐",
        "weight": 0.5,
        "type": "player",
        "min_rating": 90,
        "max_rating": 95,
    },
]

# ═══════════════════════════════════════════════════════════════
# Streak Settings
# ═══════════════════════════════════════════════════════════════

STREAK_MILESTONE = 14           # Days for milestone reward
STREAK_MISS_LIMIT = 2           # Days missed before reset
STREAK_REWARD_MIN_RATING = 81
STREAK_REWARD_MAX_RATING = 85

# ═══════════════════════════════════════════════════════════════
# Buy / Sell Values by Rating
# ═══════════════════════════════════════════════════════════════

BUY_SELL_VALUES = {
    100: (5_100_000, 3_570_000),
    99:  (4_600_000, 3_220_000),
    98:  (4_100_000, 2_870_000),
    97:  (3_600_000, 2_520_000),
    96:  (3_100_000, 2_170_000),
    95:  (2_600_000, 1_716_000),
    94:  (2_255_000, 1_488_300),
    93:  (1_910_000, 1_260_600),
    92:  (1_565_000, 1_032_900),
    91:  (1_220_000, 805_200),
    90:  (1_420_000, 880_400),
    89:  (1_220_000, 756_000),
    88:  (1_020_000, 632_400),
    87:  (820_000, 508_400),
    86:  (745_000, 461_900),
    85:  (677_000, 392_660),
    84:  (356_000, 206_480),
    83:  (187_000, 108_460),
    82:  (98_000, 56_840),
    81:  (51_000, 29_580),
    80:  (27_000, 14_580),
    79:  (15_400, 8_316),
    78:  (8_800, 4_752),
    77:  (5_030, 2_716),
    76:  (2_875, 1_553),
    75:  (1_643, 822),
    74:  (1_807, 904),
    73:  (1_642, 821),
    72:  (1_493, 747),
    71:  (1_357, 679),
    70:  (1_233, 678),
    69:  (1_195, 657),
    68:  (1_138, 626),
    67:  (1_084, 596),
    66:  (1_033, 568),
    65:  (983, 590),
    64:  (950, 570),
    63:  (900, 540),
    62:  (825, 495),
    61:  (775, 465),
    60:  (700, 420),
    59:  (625, 375),
    58:  (550, 330),
    57:  (475, 285),
    56:  (400, 240),
    55:  (325, 195),
    54:  (275, 165),
    53:  (250, 150),
    52:  (225, 135),
    51:  (200, 120),
    50:  (175, 105),
}

# ═══════════════════════════════════════════════════════════════
# Roster / Release Settings
# ═══════════════════════════════════════════════════════════════

DUPLICATE_ALLOWED = True        # Players can be owned multiple times
ROSTER_PAGE_SIZE = 10           # Players shown per /myroster page

# ═══════════════════════════════════════════════════════════════
# Trading Settings
# ═══════════════════════════════════════════════════════════════

TRADE_EXPIRES_SECONDS = 20      # Trade offer expires after 20 seconds
MAX_ACTIVE_TRADES = 1           # Max 1 pending trade per user
TRADE_ALLOWED_MIN_RATING = 75   # Only rating >= 75 can trade
TRADE_FEE_PERCENT = 5           # 5 % fee on buy value (deducted from both)
