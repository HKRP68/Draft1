"""Environment variables and API key configuration."""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Database URL (SQLite default for development, PostgreSQL for production)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cricket_bot.db")

# Logging level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Port for the health-check HTTP server (required by PaaS platforms like Render)
PORT = int(os.getenv("PORT", "8080"))
