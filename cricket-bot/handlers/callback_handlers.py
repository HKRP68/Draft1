"""Callback handlers for inline keyboard buttons (Retain/Release)."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from config.constants import MAX_ROSTER_SIZE
from config.database import SessionLocal
from database.crud import (
    add_player_to_roster,
    get_player_by_id,
    get_user_by_telegram_id,
    update_user_coins,
)
from services.player_service import get_player_value
from utils.formatters import format_coins

logger = logging.getLogger(__name__)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Retain/Release button callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    telegram_user = update.effective_user
    logger.info("Button callback from user %s: %s", telegram_user.id, data)

    db = SessionLocal()
    try:
        parts = data.split("_")
        if len(parts) != 3:
            await query.edit_message_reply_markup(reply_markup=None)
            return

        action = parts[0]
        player_id = int(parts[1])
        user_id = int(parts[2])

        # Verify the button is for this user
        user = get_user_by_telegram_id(db, telegram_user.id)
        if not user or user.id != user_id:
            await query.answer("❌ This button is not for you!", show_alert=True)
            return

        player = get_player_by_id(db, player_id)
        if not player:
            await query.edit_message_text("❌ Player not found.")
            return

        if action == "retain":
            await _handle_retain(query, db, user, player, telegram_user)
        elif action == "release":
            await _handle_release(query, db, user, player, telegram_user)
        else:
            await query.edit_message_reply_markup(reply_markup=None)

    except Exception as e:
        logger.error("Error in button callback for user %s: %s", telegram_user.id, e, exc_info=True)
        try:
            await query.edit_message_text("⚠️ An error occurred. Please try again later.")
        except Exception:
            pass
    finally:
        db.close()


async def _handle_retain(query, db, user, player, telegram_user):
    """Handle Retain button – add player to roster."""
    # Check roster space
    if user.roster_count >= MAX_ROSTER_SIZE:
        await query.answer(
            f"❌ Your roster is full! ({MAX_ROSTER_SIZE}/{MAX_ROSTER_SIZE})\n"
            "Release players to claim more.",
            show_alert=True,
        )
        return

    # Add to roster
    add_player_to_roster(db, user, player)

    username = telegram_user.username or telegram_user.first_name or "Player"
    text = f"✅ {player.name} Added to @{username}"

    # Keep the original message text but remove buttons and append result
    try:
        original_text = query.message.text or query.message.caption or ""
        new_text = f"{original_text}\n\n{text}"
        if query.message.photo:
            await query.edit_message_caption(caption=new_text, parse_mode="Markdown")
        else:
            await query.edit_message_text(new_text, parse_mode="Markdown")
    except Exception:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(text)

    logger.info(
        "Player %s retained by user %s (roster: %d/%d)",
        player.name,
        telegram_user.id,
        user.roster_count,
        MAX_ROSTER_SIZE,
    )


async def _handle_release(query, db, user, player, telegram_user):
    """Handle Release button – add sell value to coins."""
    _, sell_value = get_player_value(player.rating)
    update_user_coins(db, user, sell_value)

    username = telegram_user.username or telegram_user.first_name or "Player"
    text = (
        f"❌ {player.name} Released by @{username}\n"
        f"💰 +{format_coins(sell_value)} coins added to purse"
    )

    # Update message
    try:
        original_text = query.message.text or query.message.caption or ""
        new_text = f"{original_text}\n\n{text}"
        if query.message.photo:
            await query.edit_message_caption(caption=new_text, parse_mode="Markdown")
        else:
            await query.edit_message_text(new_text, parse_mode="Markdown")
    except Exception:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(text)

    logger.info(
        "Player %s released by user %s for %d coins",
        player.name,
        telegram_user.id,
        sell_value,
    )
