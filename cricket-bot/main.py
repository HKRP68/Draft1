"""Cricket Simulator Telegram Bot – Application Entry Point."""

import logging
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
)

from admin import create_app
from config.database import init_db
from config.logging_config import setup_logging
from config.settings import ADMIN_PORT, ADMIN_TELEGRAM_IDS, BOT_TOKEN, PORT
from database.seed import seed_database
from handlers.admin_handlers import (
    addplayer_command,
    delplayer_command,
    editplayer_command,
    listplayers_command,
    playerstats_command,
)
from handlers.callback_handlers import button_callback
from handlers.command_handlers import (
    claim_command,
    daily_command,
    debut_command,
    gspin_command,
    myroster_command,
    mytradesettings_command,
    playerinfo_command,
    release_command,
    releasemultiple_command,
    trade_command,
)
from handlers.error_handlers import error_handler

logger = logging.getLogger(__name__)


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Simple handler that responds to health-check requests."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        """Suppress default request logging to keep output clean."""
        return


def start_health_server(port: int) -> None:
    """Start a lightweight HTTP server for platform health checks."""
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    except OSError:
        logger.exception("Failed to bind health-check server on port %d", port)
        return
    logger.info("Health-check server listening on port %d", port)
    server.serve_forever()


def main():
    """Initialize and start the Telegram bot."""
    # Setup logging
    setup_logging()
    logger.info("Starting Cricket Simulator Bot...")

    # Validate bot token
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set! Please set it in .env file.")
        sys.exit(1)

    # Start health-check HTTP server in a daemon thread so that PaaS
    # platforms (e.g. Render) detect an open port and don't time out.
    health_thread = threading.Thread(
        target=start_health_server, args=(PORT,), daemon=True
    )
    health_thread.start()

    # Start the Flask admin panel in a daemon thread
    admin_app = create_app()
    admin_thread = threading.Thread(
        target=lambda: admin_app.run(
            host="0.0.0.0", port=ADMIN_PORT, debug=False, use_reloader=False
        ),
        daemon=True,
    )
    admin_thread.start()
    logger.info("Admin panel running on http://0.0.0.0:%d/admin", ADMIN_PORT)

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
    app.add_handler(CommandHandler("release", release_command))
    app.add_handler(CommandHandler("releasemultiple", releasemultiple_command))
    app.add_handler(CommandHandler("trade", trade_command))
    app.add_handler(CommandHandler("mytradesettings", mytradesettings_command))

    # Register admin command handlers (restricted to ADMIN_TELEGRAM_IDS)
    app.add_handler(CommandHandler("addplayer", addplayer_command))
    app.add_handler(CommandHandler("editplayer", editplayer_command))
    app.add_handler(CommandHandler("delplayer", delplayer_command))
    app.add_handler(CommandHandler("listplayers", listplayers_command))
    app.add_handler(CommandHandler("playerstats", playerstats_command))

    if ADMIN_TELEGRAM_IDS:
        logger.info("Telegram admin commands enabled for user IDs: %s", ADMIN_TELEGRAM_IDS)
    else:
        logger.warning(
            "ADMIN_TELEGRAM_IDS is not set – Telegram admin commands are disabled. "
            "Set it in .env to enable /addplayer, /editplayer, etc."
        )

    # Register callback handler for all inline buttons
    app.add_handler(CallbackQueryHandler(button_callback))

    # Register error handler
    app.add_error_handler(error_handler)

    # Start the bot
    logger.info("Bot is starting polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
