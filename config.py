from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GROK_MODEL = "x-ai/grok-4.3"
GROK_MAX_TOKENS = 50  # JSON response is tiny: {"intellectual":7,"retarded":false}

# Conversation buffering
CONVERSATION_WINDOW = 10     # max messages kept per channel
MIN_MESSAGES_FOR_SCORING = 3  # need at least this many messages before scoring
MIN_USERS_FOR_SCORING = 2    # need at least this many distinct authors

# A score at or below this threshold is considered a "bad" interaction
BAD_INTERACTION_THRESHOLD = 4.0

# Minimum seconds between automatic scores for the same channel (avoids spam)
SCORE_COOLDOWN_SECONDS = 60

# Periodic background check interval (minutes)
BACKGROUND_CHECK_INTERVAL_MINUTES = 5

DB_PATH = "interactions.db"
