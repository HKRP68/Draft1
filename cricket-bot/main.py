"""Cricket Simulator Telegram Bot – Application Entry Point."""

import logging
import sys

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
)

from config.database import init_db
from config.logging_config import setup_logging
from config.settings import BOT_TOKEN
from database.seed import seed_database
from handlers.callback_handlers import button_callback
from handlers.command_handlers import (
    claim_command,
    daily_command,
    debut_command,
    gspin_command,
    myroster_command,
    playerinfo_command,
)
from handlers.error_handlers import error_handler

logger = logging.getLogger(__name__)


def main():
    """Initialize and start the Telegram bot."""
    # Setup logging
    setup_logging()
    logger.info("Starting Cricket Simulator Bot...")

    # Validate bot token
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set! Please set it in .env file.")
        sys.exit(1)

    # Initialize database
    logger.info("Initializing database...")
    init_db()

    # Seed player data
    logger.info("Seeding player data...")
    seed_database()

    # Build the Telegram application
    logger.info("Building Telegram application...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register command handlers
    app.add_handler(CommandHandler("debut", debut_command))
    app.add_handler(CommandHandler("claim", claim_command))
    app.add_handler(CommandHandler("gspin", gspin_command))
    app.add_handler(CommandHandler("daily", daily_command))
    app.add_handler(CommandHandler("myroster", myroster_command))
    app.add_handler(CommandHandler("playerinfo", playerinfo_command))

    # Register callback handler for Retain/Release buttons
    app.add_handler(CallbackQueryHandler(button_callback))

    # Register error handler
    app.add_error_handler(error_handler)

    # Start the bot
    logger.info("Bot is starting polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
