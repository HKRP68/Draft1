"""Inline / multi-step callback handlers for trade and release-multiple flows."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config.constants import BUY_SELL_VALUES, TRADE_ALLOWED_MIN_RATING, TRADE_EXPIRES_SECONDS, TRADE_FEE_PERCENT
from config.database import SessionLocal
from database.crud import get_roster_entry_by_id, get_user_by_telegram_id, get_user_by_username
from database.models import User
from services.rating_matcher_service import (
    find_same_rating_players_in_roster,
    get_matching_tradeable_ratings,
    get_tradeable_ratings,
)
from services.roster_service import (
    get_duplicate_players,
    get_players_by_rating,
    get_roster_entry_for_trade,
    release_multiple_by_entry_ids,
    release_player_by_entry_id,
)
from services.trading_service import (
    accept_trade,
    get_pending_trades,
    get_trade_details,
    initiate_trade,
    reject_trade,
)
from utils.formatters import format_coins

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _trade_fee_for_rating(rating: int) -> int:
    bv = BUY_SELL_VALUES.get(rating, (200, 120))[0]
    return max(1, int(bv * TRADE_FEE_PERCENT / 100))


def _build_cancel_keyboard(callback_prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Cancel", callback_data=f"{callback_prefix}_cancel"),
    ]])


# ─────────────────────────────────────────────────────────────────────
# /release confirm flow
# ─────────────────────────────────────────────────────────────────────

async def release_confirm_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle release_confirm_<entry_id>_<user_id> callback."""
    query = update.callback_query
    await query.answer()
    data = query.data  # release_confirm_<entry_id>_<user_id>
    parts = data.split("_")
    # parts: ['release', 'confirm', entry_id, user_id]
    if len(parts) != 4:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    entry_id = int(parts[2])
    owner_user_id = int(parts[3])

    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, update.effective_user.id)
        if not user or user.id != owner_user_id:
            await query.answer("❌ This button is not for you!", show_alert=True)
            return

        result = release_player_by_entry_id(db, user, entry_id)
        if not result["success"]:
            await query.edit_message_text(f"❌ {result['error']}")
            return

        text = (
            f"✅ **PLAYER RELEASED!**\n\n"
            f"{result['player_name']} - {result['rating']} OVR\n\n"
            f"💸 Received: {format_coins(result['sell_value'])} 🪙\n"
            f"💰 New Balance: {format_coins(result['new_balance'])}\n"
            f"📊 Roster: {user.roster_count}/25"
        )
        await query.edit_message_text(text, parse_mode="Markdown")

    except Exception as e:
        logger.error("Error in release_confirm callback: %s", e, exc_info=True)
        await query.edit_message_text("⚠️ An error occurred. Please try again later.")
    finally:
        db.close()


async def release_cancel_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle release_cancel_<entry_id>_<user_id> callback."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Release cancelled.")


# ─────────────────────────────────────────────────────────────────────
# /releasemultiple flow
# ─────────────────────────────────────────────────────────────────────

async def release_multi_one_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle release_multi_one_<entry_id>_<user_id>."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    # release_multi_one_<entry_id>_<user_id>
    if len(parts) != 5:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    entry_id = int(parts[3])
    owner_user_id = int(parts[4])

    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, update.effective_user.id)
        if not user or user.id != owner_user_id:
            await query.answer("❌ This button is not for you!", show_alert=True)
            return

        result = release_player_by_entry_id(db, user, entry_id)
        if not result["success"]:
            await query.edit_message_text(f"❌ {result['error']}")
            return

        text = (
            f"✅ Released {result['player_name']} - {result['rating']} OVR\n"
            f"💸 +{format_coins(result['sell_value'])} 🪙 | Balance: {format_coins(result['new_balance'])}"
        )
        await query.edit_message_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error("Error in release_multi_one callback: %s", e, exc_info=True)
        await query.edit_message_text("⚠️ An error occurred.")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────
# /trade multi-step flow
# ─────────────────────────────────────────────────────────────────────

async def trade_rating_select_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle trade_rating_<rating>_<receiver_telegram_id>_<initiator_telegram_id>.
    Step 2: user chose a rating; now show initiator's players at that rating.
    """
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    # trade_rating_<rating>_<receiver_tid>_<initiator_tid>
    if len(parts) != 5:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    rating = int(parts[2])
    receiver_tid = int(parts[3])
    initiator_tid = int(parts[4])

    if update.effective_user.id != initiator_tid:
        await query.answer("❌ Not for you!", show_alert=True)
        return

    db = SessionLocal()
    try:
        initiator = get_user_by_telegram_id(db, initiator_tid)
        if not initiator:
            await query.edit_message_text("❌ User not found.")
            return

        my_entries = get_players_by_rating(db, initiator, rating)
        if not my_entries:
            await query.edit_message_text(f"❌ You have no {rating} OVR players.")
            return

        buttons = []
        seen_names: dict[str, int] = {}
        for e in my_entries:
            pname = e.player.name
            seen_names[pname] = seen_names.get(pname, 0) + 1
            label = pname if seen_names[pname] == 1 else f"{pname} (copy {seen_names[pname]})"
            buttons.append([InlineKeyboardButton(
                f"Select {label}",
                callback_data=f"trade_mypick_{e.id}_{receiver_tid}_{initiator_tid}",
            )])
        buttons.append([InlineKeyboardButton(
            "⬅️ Back", callback_data=f"trade_back_{receiver_tid}_{initiator_tid}"
        )])

        text = f"🏏 **SELECT YOUR PLAYER TO TRADE** ({rating} OVR)\n\nAvailable:"
        for idx, e in enumerate(my_entries, 1):
            text += f"\n{idx}. {e.player.name} - {e.player.rating} OVR | {e.player.category}"

        await query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    except Exception as e:
        logger.error("Error in trade_rating_select: %s", e, exc_info=True)
        await query.edit_message_text("⚠️ An error occurred.")
    finally:
        db.close()


async def trade_my_pick_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle trade_mypick_<my_entry_id>_<receiver_tid>_<initiator_tid>.
    Step 3: initiator chose their player; show receiver's players at same rating.
    """
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    # trade_mypick_<my_entry_id>_<receiver_tid>_<initiator_tid>
    if len(parts) != 5:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    my_entry_id = int(parts[2])
    receiver_tid = int(parts[3])
    initiator_tid = int(parts[4])

    if update.effective_user.id != initiator_tid:
        await query.answer("❌ Not for you!", show_alert=True)
        return

    db = SessionLocal()
    try:
        initiator = get_user_by_telegram_id(db, initiator_tid)
        receiver = get_user_by_telegram_id(db, receiver_tid)
        if not initiator or not receiver:
            await query.edit_message_text("❌ User not found.")
            return

        my_entry = get_roster_entry_by_id(db, my_entry_id)
        if not my_entry or my_entry.user_id != initiator.id:
            await query.edit_message_text("❌ Player not found in your roster.")
            return

        rating = my_entry.player.rating
        their_entries = get_players_by_rating(db, receiver, rating)
        if not their_entries:
            await query.edit_message_text(
                f"❌ @{receiver.username or receiver_tid} has no {rating} OVR players."
            )
            return

        buttons = []
        seen_names: dict[str, int] = {}
        for e in their_entries:
            pname = e.player.name
            seen_names[pname] = seen_names.get(pname, 0) + 1
            label = pname if seen_names[pname] == 1 else f"{pname} (copy {seen_names[pname]})"
            buttons.append([InlineKeyboardButton(
                f"Select {label}",
                callback_data=f"trade_theirpick_{my_entry_id}_{e.id}_{receiver_tid}_{initiator_tid}",
            )])
        buttons.append([InlineKeyboardButton(
            "⬅️ Back",
            callback_data=f"trade_rating_{rating}_{receiver_tid}_{initiator_tid}",
        )])

        recv_uname = receiver.username or str(receiver_tid)
        text = f"🏏 **SELECT @{recv_uname}'s PLAYER TO RECEIVE** ({rating} OVR)\n\nAvailable:"
        for idx, e in enumerate(their_entries, 1):
            text += f"\n{idx}. {e.player.name} - {e.player.rating} OVR | {e.player.category}"

        await query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    except Exception as e:
        logger.error("Error in trade_my_pick: %s", e, exc_info=True)
        await query.edit_message_text("⚠️ An error occurred.")
    finally:
        db.close()


async def trade_their_pick_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle trade_theirpick_<my_entry_id>_<their_entry_id>_<receiver_tid>_<initiator_tid>.
    Step 4: show confirmation with fees.
    """
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    # trade_theirpick_<my_entry_id>_<their_entry_id>_<receiver_tid>_<initiator_tid>
    if len(parts) != 6:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    my_entry_id = int(parts[2])
    their_entry_id = int(parts[3])
    receiver_tid = int(parts[4])
    initiator_tid = int(parts[5])

    if update.effective_user.id != initiator_tid:
        await query.answer("❌ Not for you!", show_alert=True)
        return

    db = SessionLocal()
    try:
        my_entry = get_roster_entry_by_id(db, my_entry_id)
        their_entry = get_roster_entry_by_id(db, their_entry_id)
        if not my_entry or not their_entry:
            await query.edit_message_text("❌ Player(s) no longer found.")
            return

        rating = my_entry.player.rating
        fee = _trade_fee_for_rating(rating)
        buy_val = BUY_SELL_VALUES.get(rating, (200, 120))[0]
        recv_uname = (
            get_user_by_telegram_id(db, receiver_tid).username or str(receiver_tid)
        )

        text = (
            f"📬 **TRADE OFFER CONFIRMATION**\n\n"
            f"➡️  You offer: {my_entry.player.name} - {rating} OVR\n"
            f"💰 Buy Value: {format_coins(buy_val)} 🪙\n"
            f"💳 Trade Fee (5%): {format_coins(fee)} 🪙\n\n"
            f"⬅️  You receive: {their_entry.player.name} - {rating} OVR\n"
            f"💰 Buy Value: {format_coins(buy_val)} 🪙\n"
            f"💳 Trade Fee (5%): {format_coins(fee)} 🪙\n\n"
            f"🔄 Fair Trade: ✅ Yes (Same rating)\n\n"
            f"💸 Your Cost: {format_coins(fee)} 🪙 (your fee)\n"
            f"⏳ Offer expires in: {TRADE_EXPIRES_SECONDS} seconds"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Send Offer",
                    callback_data=f"trade_send_{my_entry_id}_{their_entry_id}_{receiver_tid}_{initiator_tid}",
                ),
                InlineKeyboardButton("❌ Cancel", callback_data="trade_cancel_offer"),
            ]
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)

    except Exception as e:
        logger.error("Error in trade_their_pick: %s", e, exc_info=True)
        await query.edit_message_text("⚠️ An error occurred.")
    finally:
        db.close()


async def trade_send_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle trade_send_<my_entry_id>_<their_entry_id>_<receiver_tid>_<initiator_tid>.
    Create the trade and notify the receiver.
    """
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    # trade_send_<my_entry_id>_<their_entry_id>_<receiver_tid>_<initiator_tid>
    if len(parts) != 6:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    my_entry_id = int(parts[2])
    their_entry_id = int(parts[3])
    receiver_tid = int(parts[4])
    initiator_tid = int(parts[5])

    if update.effective_user.id != initiator_tid:
        await query.answer("❌ Not for you!", show_alert=True)
        return

    db = SessionLocal()
    try:
        initiator = get_user_by_telegram_id(db, initiator_tid)
        receiver = get_user_by_telegram_id(db, receiver_tid)
        if not initiator or not receiver:
            await query.edit_message_text("❌ User not found.")
            return

        my_entry = get_roster_entry_by_id(db, my_entry_id)
        their_entry = get_roster_entry_by_id(db, their_entry_id)
        if not my_entry or not their_entry:
            await query.edit_message_text("❌ Player(s) no longer found.")
            return

        result = initiate_trade(
            db,
            initiator=initiator,
            receiver=receiver,
            initiator_player_id=my_entry.player_id,
            receiver_player_id=their_entry.player_id,
        )
        if not result["success"]:
            await query.edit_message_text(f"❌ {result['error']}")
            return

        trade = result["trade"]
        rating = my_entry.player.rating
        fee = trade.trade_fee
        buy_val = BUY_SELL_VALUES.get(rating, (200, 120))[0]
        recv_uname = receiver.username or str(receiver_tid)
        init_uname = initiator.username or str(initiator_tid)

        # Confirm message for initiator
        sent_text = (
            f"📤 **TRADE OFFER SENT!**\n\n"
            f"To: @{recv_uname}\n\n"
            f"➡️  You offer: {my_entry.player.name} - {rating} OVR\n"
            f"⬅️  You receive: {their_entry.player.name} - {rating} OVR\n\n"
            f"⏳ Waiting for response... (expires in {TRADE_EXPIRES_SECONDS} seconds)\n"
        )
        cancel_keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "❌ Cancel Offer",
                callback_data=f"trade_cancel_{trade.id}_{initiator_tid}",
            )
        ]])
        await query.edit_message_text(
            sent_text, parse_mode="Markdown", reply_markup=cancel_keyboard
        )

        # Notify receiver
        notify_text = (
            f"📬 **INCOMING TRADE OFFER FROM @{init_uname}!**\n\n"
            f"➡️  They offer: {my_entry.player.name} - {rating} OVR\n"
            f"💰 Buy Value: {format_coins(buy_val)} 🪙\n"
            f"💳 Trade Fee (5%): {format_coins(fee)} 🪙\n\n"
            f"⬅️  They want: {their_entry.player.name} - {rating} OVR\n"
            f"💰 Buy Value: {format_coins(buy_val)} 🪙\n"
            f"💳 Trade Fee (5%): {format_coins(fee)} 🪙\n\n"
            f"🔄 Fair Trade: ✅ Yes (Same rating)\n\n"
            f"💸 Your Cost: {format_coins(fee)} 🪙 (your fee)\n"
            f"⏳ Expires in: {TRADE_EXPIRES_SECONDS} seconds"
        )
        trade_keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "✅ Accept",
                callback_data=f"trade_accept_{trade.id}_{receiver_tid}",
            ),
            InlineKeyboardButton(
                "❌ Reject",
                callback_data=f"trade_reject_{trade.id}_{receiver_tid}",
            ),
        ]])
        try:
            await context.bot.send_message(
                chat_id=receiver_tid,
                text=notify_text,
                parse_mode="Markdown",
                reply_markup=trade_keyboard,
            )
        except Exception as notify_err:
            logger.warning("Could not notify receiver %s: %s", receiver_tid, notify_err)

    except Exception as e:
        logger.error("Error in trade_send callback: %s", e, exc_info=True)
        await query.edit_message_text("⚠️ An error occurred.")
    finally:
        db.close()


async def trade_accept_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle trade_accept_<trade_id>_<receiver_tid>."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    # trade_accept_<trade_id>_<receiver_tid>
    if len(parts) != 4:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    trade_id = int(parts[2])
    receiver_tid = int(parts[3])

    if update.effective_user.id != receiver_tid:
        await query.answer("❌ Not for you!", show_alert=True)
        return

    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, receiver_tid)
        if not user:
            await query.edit_message_text("❌ User not found.")
            return

        result = accept_trade(db, trade_id, user)
        if not result["success"]:
            await query.edit_message_text(f"❌ {result['error']}")
            return

        init_gave = result["initiator_gave"]
        recv_gave = result["receiver_gave"]
        fee = result["fee"]
        initiator = result["initiator"]
        receiver = result["receiver"]

        # Receiver success message
        recv_text = (
            f"✅ **TRADE COMPLETED!**\n\n"
            f"From: @{initiator.username or initiator.telegram_id}\n\n"
            f"✅ You gave: {recv_gave.name} - {recv_gave.rating} OVR\n"
            f"✅ You received: {init_gave.name} - {init_gave.rating} OVR\n\n"
            f"💸 Trade Fee Paid: {format_coins(fee)} 🪙\n"
            f"💰 New Balance: {format_coins(receiver.total_coins)}\n"
            f"📊 Roster: {receiver.roster_count}/25"
        )
        await query.edit_message_text(recv_text, parse_mode="Markdown")

        # Notify initiator
        init_text = (
            f"✅ **TRADE COMPLETED!**\n\n"
            f"From: @{receiver.username or receiver.telegram_id}\n\n"
            f"✅ You gave: {init_gave.name} - {init_gave.rating} OVR\n"
            f"✅ You received: {recv_gave.name} - {recv_gave.rating} OVR\n\n"
            f"💸 Trade Fee Paid: {format_coins(fee)} 🪙\n"
            f"💰 New Balance: {format_coins(initiator.total_coins)}\n"
            f"📊 Roster: {initiator.roster_count}/25"
        )
        try:
            await context.bot.send_message(
                chat_id=initiator.telegram_id,
                text=init_text,
                parse_mode="Markdown",
            )
        except Exception as ne:
            logger.warning("Could not notify initiator %s: %s", initiator.telegram_id, ne)

    except Exception as e:
        logger.error("Error in trade_accept callback: %s", e, exc_info=True)
        await query.edit_message_text("⚠️ An error occurred.")
    finally:
        db.close()


async def trade_reject_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle trade_reject_<trade_id>_<receiver_tid>."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    if len(parts) != 4:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    trade_id = int(parts[2])
    receiver_tid = int(parts[3])

    if update.effective_user.id != receiver_tid:
        await query.answer("❌ Not for you!", show_alert=True)
        return

    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, receiver_tid)
        if not user:
            await query.edit_message_text("❌ User not found.")
            return

        result = reject_trade(db, trade_id, user)
        if not result["success"]:
            await query.edit_message_text(f"❌ {result['error']}")
            return

        trade = result["trade"]
        initiator = trade.initiator

        await query.edit_message_text("❌ Trade rejected.")

        try:
            await context.bot.send_message(
                chat_id=initiator.telegram_id,
                text=(
                    f"❌ **TRADE REJECTED**\n\n"
                    f"@{user.username or receiver_tid} rejected your trade offer."
                ),
                parse_mode="Markdown",
            )
        except Exception as ne:
            logger.warning("Could not notify initiator %s: %s", initiator.telegram_id, ne)

    except Exception as e:
        logger.error("Error in trade_reject callback: %s", e, exc_info=True)
        await query.edit_message_text("⚠️ An error occurred.")
    finally:
        db.close()


async def trade_cancel_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle trade_cancel_<trade_id>_<initiator_tid> (cancel own trade offer)."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")

    # trade_cancel_offer (no trade yet) or trade_cancel_<trade_id>_<initiator_tid>
    if len(parts) == 3 and parts[2] == "offer":
        await query.edit_message_text("❌ Trade offer cancelled.")
        return

    if len(parts) != 4:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    trade_id = int(parts[2])
    initiator_tid = int(parts[3])

    if update.effective_user.id != initiator_tid:
        await query.answer("❌ Not for you!", show_alert=True)
        return

    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, initiator_tid)
        if not user:
            await query.edit_message_text("❌ User not found.")
            return

        result = reject_trade(db, trade_id, user)
        if not result["success"]:
            await query.edit_message_text(f"❌ {result['error']}")
            return

        trade = result["trade"]
        receiver = trade.receiver
        await query.edit_message_text("✅ Trade offer cancelled.")

        try:
            await context.bot.send_message(
                chat_id=receiver.telegram_id,
                text=(
                    f"⚠️ Trade offer from @{user.username or initiator_tid} was cancelled."
                ),
            )
        except Exception as ne:
            logger.warning("Could not notify receiver %s: %s", receiver.telegram_id, ne)

    except Exception as e:
        logger.error("Error in trade_cancel callback: %s", e, exc_info=True)
        await query.edit_message_text("⚠️ An error occurred.")
    finally:
        db.close()


async def trade_back_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle trade_back_<receiver_tid>_<initiator_tid> – go back to rating selection."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    if len(parts) != 4:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    receiver_tid = int(parts[2])
    initiator_tid = int(parts[3])

    if update.effective_user.id != initiator_tid:
        await query.answer("❌ Not for you!", show_alert=True)
        return

    db = SessionLocal()
    try:
        initiator = get_user_by_telegram_id(db, initiator_tid)
        receiver = get_user_by_telegram_id(db, receiver_tid)
        if not initiator or not receiver:
            await query.edit_message_text("❌ User not found.")
            return

        await _show_rating_selection(query, db, initiator, receiver)
    except Exception as e:
        logger.error("Error in trade_back callback: %s", e, exc_info=True)
        await query.edit_message_text("⚠️ An error occurred.")
    finally:
        db.close()


async def _show_rating_selection(query, db, initiator: User, receiver: User) -> None:
    """Shared helper: show matching rating buttons for a trade."""
    from services.roster_service import get_user_roster_sorted
    matching = get_matching_tradeable_ratings(db, initiator, receiver)
    recv_uname = receiver.username or str(receiver.telegram_id)

    if not matching:
        await query.edit_message_text(
            f"❌ No matching tradeable ratings found with @{recv_uname}."
        )
        return

    # Build rating overview
    my_entries_all = get_user_roster_sorted(db, initiator)
    their_entries_all = get_user_roster_sorted(db, receiver)

    from config.constants import TRADE_ALLOWED_MIN_RATING
    my_tradeable = get_tradeable_ratings(db, initiator)
    their_tradeable = get_tradeable_ratings(db, receiver)

    def _player_list(entries, ratings_filter):
        lines = []
        shown_ratings: set = set()
        for e in entries:
            if e.player.rating in ratings_filter and e.player.rating not in shown_ratings:
                shown_ratings.add(e.player.rating)
                lines.append(f"• {e.player.rating} OVR: {e.player.name}")
        return "\n".join(lines) if lines else "None"

    my_lines = _player_list(my_entries_all, my_tradeable)
    their_lines = _player_list(their_entries_all, their_tradeable)

    text = (
        f"🔍 **TRADE WITH @{recv_uname}**\n\n"
        f"Your tradeable players (rating ≥ {TRADE_ALLOWED_MIN_RATING}):\n{my_lines}\n\n"
        f"Their tradeable players (rating ≥ {TRADE_ALLOWED_MIN_RATING}):\n{their_lines}\n\n"
        f"✅ Matching Ratings: {', '.join(str(r) + ' OVR' for r in matching)}"
    )

    buttons = [
        [InlineKeyboardButton(
            f"Select {r} OVR",
            callback_data=f"trade_rating_{r}_{receiver.telegram_id}_{initiator.telegram_id}",
        )]
        for r in matching
    ]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="trade_cancel_offer")])

    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
