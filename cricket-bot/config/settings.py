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

# Admin panel port (separate from health-check / bot)
ADMIN_PORT = int(os.getenv("ADMIN_PORT", "5000"))

# Secret key for Flask session / CSRF (generate a strong random key for production)
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "change-me-in-production")
