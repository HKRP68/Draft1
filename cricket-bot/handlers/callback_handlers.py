"""Callback handlers for inline keyboard buttons (Retain/Release and trading flows)."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config.constants import MAX_ROSTER_SIZE, BUY_SELL_VALUES, ROSTER_PAGE_SIZE
from config.database import SessionLocal
from database.crud import (
    add_player_to_roster,
    get_player_by_id,
    get_user_by_telegram_id,
    update_user_coins,
)
from services.player_service import get_player_value
from services.roster_service import get_user_roster_sorted, get_roster_stats
from utils.formatters import format_coins, format_roster_entry
from handlers.inline_handlers import (
    release_confirm_callback,
    release_cancel_callback,
    release_multi_one_callback,
    trade_rating_select_callback,
    trade_my_pick_callback,
    trade_their_pick_callback,
    trade_send_callback,
    trade_accept_callback,
    trade_reject_callback,
    trade_cancel_callback,
    trade_back_callback,
)
from handlers.admin_handlers import admin_listplayers_page_callback

logger = logging.getLogger(__name__)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route all inline keyboard callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    telegram_user = update.effective_user
    logger.info("Button callback from user %s: %s", telegram_user.id, data)

    # ── Retain / Release (claim flow) ───────────────────────────────
    if data.startswith("retain_"):
        await _handle_claim_retain(query, update, context)
        return

    # ── Admin list-players pagination ────────────────────────────────
    if data.startswith("adm_lp_"):
        await admin_listplayers_page_callback(update, context)
        return

    if data.startswith("release_confirm_"):
        await release_confirm_callback(update, context)
        return
    if data.startswith("release_cancel_"):
        await release_cancel_callback(update, context)
        return
    if data.startswith("release_multi_one_"):
        await release_multi_one_callback(update, context)
        return

    # Legacy release_ prefix (claim card release)
    if data.startswith("release_"):
        parts = data.split("_")
        if len(parts) == 3:
            await _handle_claim_release(query, update, context)
            return

    # ── Roster pagination ────────────────────────────────────────────
    if data.startswith("roster_page_"):
        await _handle_roster_page(query, update, context)
        return

    # ── Trade flow ───────────────────────────────────────────────────
    if data.startswith("trade_rating_"):
        await trade_rating_select_callback(update, context)
        return
    if data.startswith("trade_mypick_"):
        await trade_my_pick_callback(update, context)
        return
    if data.startswith("trade_theirpick_"):
        await trade_their_pick_callback(update, context)
        return
    if data.startswith("trade_send_"):
        await trade_send_callback(update, context)
        return
    if data.startswith("trade_accept_"):
        await trade_accept_callback(update, context)
        return
    if data.startswith("trade_reject_"):
        await trade_reject_callback(update, context)
        return
    if data.startswith("trade_cancel"):
        await trade_cancel_callback(update, context)
        return
    if data.startswith("trade_back_"):
        await trade_back_callback(update, context)
        return

    # Unknown
    logger.warning("Unhandled callback data: %s", data)
    await query.edit_message_reply_markup(reply_markup=None)


# ─────────────────────────────────────────────────────────────────────
# Claim-card retain / release helpers
# ─────────────────────────────────────────────────────────────────────

async def _handle_claim_retain(query, update, context) -> None:
    """Handle Retain button from /claim card."""
    data = query.data
    parts = data.split("_")
    if len(parts) != 3:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    player_id = int(parts[1])
    user_id = int(parts[2])

    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, update.effective_user.id)
        if not user or user.id != user_id:
            await query.answer("❌ This button is not for you!", show_alert=True)
            return

        player = get_player_by_id(db, player_id)
        if not player:
            await query.edit_message_text("❌ Player not found.")
            return

        if user.roster_count >= MAX_ROSTER_SIZE:
            await query.answer(
                f"❌ Your roster is full! ({MAX_ROSTER_SIZE}/{MAX_ROSTER_SIZE})\n"
                "Release players to claim more.",
                show_alert=True,
            )
            return

        add_player_to_roster(db, user, player)

        username = update.effective_user.username or update.effective_user.first_name or "Player"
        text = f"✅ {player.name} Added to @{username}"

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
            player.name, update.effective_user.id, user.roster_count, MAX_ROSTER_SIZE,
        )
    except Exception as e:
        logger.error("Error in retain callback: %s", e, exc_info=True)
        try:
            await query.edit_message_text("⚠️ An error occurred.")
        except Exception:
            pass
    finally:
        db.close()


async def _handle_claim_release(query, update, context) -> None:
    """Handle Release button from /claim card (gives sell value without roster add)."""
    data = query.data
    parts = data.split("_")
    if len(parts) != 3:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    player_id = int(parts[1])
    user_id = int(parts[2])

    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, update.effective_user.id)
        if not user or user.id != user_id:
            await query.answer("❌ This button is not for you!", show_alert=True)
            return

        player = get_player_by_id(db, player_id)
        if not player:
            await query.edit_message_text("❌ Player not found.")
            return

        _, sell_value = get_player_value(player.rating)
        update_user_coins(db, user, sell_value)

        username = update.effective_user.username or update.effective_user.first_name or "Player"
        text = (
            f"❌ {player.name} Released by @{username}\n"
            f"💰 +{format_coins(sell_value)} coins added to purse"
        )

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
            "Player %s released (claim) by user %s for %d coins",
            player.name, update.effective_user.id, sell_value,
        )
    except Exception as e:
        logger.error("Error in claim release callback: %s", e, exc_info=True)
        try:
            await query.edit_message_text("⚠️ An error occurred.")
        except Exception:
            pass
    finally:
        db.close()


async def _handle_roster_page(query, update, context) -> None:
    """Handle roster_page_<page>_<user_id> pagination callback."""
    parts = query.data.split("_")
    # roster_page_<page>_<user_id>
    if len(parts) != 4:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    page = int(parts[2])
    owner_user_id = int(parts[3])

    if update.effective_user.id != owner_user_id:
        # Compare telegram_id with stored user.id – need db lookup
        db = SessionLocal()
        try:
            u = get_user_by_telegram_id(db, update.effective_user.id)
            if not u or u.id != owner_user_id:
                await query.answer("❌ Not your roster!", show_alert=True)
                return
        finally:
            db.close()

    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, update.effective_user.id)
        if not user:
            await query.edit_message_text("❌ Do /debut first!")
            return

        entries = get_user_roster_sorted(db, user)
        stats = get_roster_stats(db, user)
        total_pages = max(1, (len(entries) + ROSTER_PAGE_SIZE - 1) // ROSTER_PAGE_SIZE)
        page = min(max(1, page), total_pages)
        start = (page - 1) * ROSTER_PAGE_SIZE
        page_entries = entries[start: start + ROSTER_PAGE_SIZE]

        lines = []
        release_buttons = []
        for i, entry in enumerate(page_entries, start=start):
            player = entry.player
            sell_val = BUY_SELL_VALUES.get(player.rating, (200, 120))[1]
            lines.append(
                f"{format_roster_entry(i, player.name, player.rating, player.category)}\n"
                f"   🪙 Sell: {format_coins(sell_val)}"
            )
            release_buttons.append(
                InlineKeyboardButton(
                    f"Release {player.name[:12]}",
                    callback_data=f"release_confirm_{entry.id}_{user.id}",
                )
            )

        kb_rows = []
        for i in range(0, len(release_buttons), 2):
            kb_rows.append(release_buttons[i: i + 2])

        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton("◀️ Previous", callback_data=f"roster_page_{page-1}_{user.id}"))
        if page < total_pages:
            nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"roster_page_{page+1}_{user.id}"))
        if nav_row:
            kb_rows.append(nav_row)

        roster_text = "\n\n".join(lines)
        text = (
            f"📊 **YOUR ROSTER** ({len(entries)}/{MAX_ROSTER_SIZE})\n\n"
            f"📈 **Roster Stats:**\n"
            f"• Avg Rating: {stats['avg_rating']}\n"
            f"• Total Value: {format_coins(stats['total_value'])} 🪙\n"
            f"• Duplicates: {stats['duplicate_count']}\n\n"
            f"👥 **Players (Page {page}/{total_pages}):**\n\n"
            f"{roster_text}"
        )

        await query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb_rows) if kb_rows else None,
        )
    except Exception as e:
        logger.error("Error in roster pagination: %s", e, exc_info=True)
        try:
            await query.edit_message_text("⚠️ An error occurred.")
        except Exception:
            pass
    finally:
        db.close()
