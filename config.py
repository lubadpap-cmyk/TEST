import os

# Telegram Bot Token. Set BOT_TOKEN in the hosting panel or environment.
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# SQLite database file path
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_database.db")

# Default daily limit of free username checks per user
DAILY_FREE_LIMIT = 5

# Cooldown delay in seconds between username checks to prevent rate limits/banning
CHECK_COOLDOWN = 1.5

# Premium subscription cost placeholder / details
PREMIUM_PRICE_STARS = 100
PREMIUM_DURATION_DAYS = 30

# Maximum number of username generation attempts per search loop
MAX_USERNAME_SEARCH_TRIES = 400

# Admin User ID for restricted commands
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
