"""Error handling for the Telegram bot."""

import json
import logging
import traceback

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors raised during handler execution."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    # Format traceback
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    logger.error("Traceback:\n%s", tb_string)

    # Build error message for the user
    error_message = "⚠️ An unexpected error occurred. Please try again later."

    # Try to send a message to the user
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(error_message)
        except Exception as e:
            logger.error("Failed to send error message to user: %s", e)

    # Log detailed info
    if isinstance(update, Update):
        update_str = update.to_dict()
        logger.error(
            "Update %s caused error: %s\nUpdate data: %s",
            update.update_id if update else "N/A",
            context.error,
            json.dumps(update_str, indent=2, default=str),
        )
