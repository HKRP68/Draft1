"""Telegram command handlers for /debut, /claim, /myroster, /playerinfo, /daily, /gspin,
/release, /releasemultiple, /trade, /mytradesettings."""

import logging
import os
import random
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config.constants import (
    CLAIM_REWARD_COINS,
    DAILY_REWARD_COINS,
    DAILY_REWARD_PLAYERS,
    DEBUT_INITIAL_COINS,
    DEBUT_INITIAL_GEMS,
    DEBUT_PLAYER_DISTRIBUTION,
    GSPIN_OUTCOMES,
    MAX_ROSTER_SIZE,
    ROSTER_PAGE_SIZE,
    STREAK_MILESTONE,
    TRADE_ALLOWED_MIN_RATING,
    TRADE_EXPIRES_SECONDS,
    TRADE_FEE_PERCENT,
    BUY_SELL_VALUES,
)
from config.database import SessionLocal
from database.crud import (
    add_player_to_roster,
    create_user,
    get_player_by_name,
    get_user_by_telegram_id,
    get_user_by_username,
    get_user_roster,
    search_players_by_name,
    update_user_coins,
    update_user_gems,
)
from services.card_generator import format_card_text, generate_card
from services.cooldown_service import check_cooldown, format_cooldown_time, set_cooldown
from services.player_service import (
    get_player_stats,
    get_player_value,
    get_random_player_by_rarity,
    get_random_player_by_rating,
)
from services.rating_matcher_service import (
    get_matching_tradeable_ratings,
    get_tradeable_ratings,
)
from services.roster_service import (
    get_duplicate_players,
    get_players_by_rating,
    get_roster_stats,
    get_user_roster_sorted,
)
from services.streak_service import update_streak
from utils.formatters import (
    format_coins,
    format_cooldown_message,
    format_player_info,
    format_roster_entry,
)
from utils.helpers import cleanup_temp_file

logger = logging.getLogger(__name__)


async def debut_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /debut command – create user account and give starting players."""
    telegram_user = update.effective_user
    logger.info("User %s (%s) used /debut", telegram_user.id, telegram_user.username)

    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = get_user_by_telegram_id(db, telegram_user.id)
        if existing_user:
            await update.message.reply_text(
                "❌ You've already made your debut! Use /myroster to see your players."
            )
            return

        # Create new user
        user = create_user(
            db,
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            coins=DEBUT_INITIAL_COINS,
            gems=DEBUT_INITIAL_GEMS,
        )

        # Generate starting players based on distribution
        players_added = []
        for tier in DEBUT_PLAYER_DISTRIBUTION:
            for _ in range(tier["count"]):
                player = get_random_player_by_rating(
                    db, tier["min_rating"], tier["max_rating"]
                )
                if player:
                    add_player_to_roster(db, user, player)
                    players_added.append(player)

        # Send welcome message
        player_list = "\n".join(
            f"  • {p.name} - {p.rating} OVR | {p.category}" for p in players_added
        )
        roster_count = len(players_added)

        welcome_msg = (
            f"🎉 Welcome to Cricket Bot!\n"
            f"✅ Your debut is complete!\n"
            f"✅ You received {roster_count} starting players\n\n"
            f"📋 **Your Players:**\n{player_list}\n\n"
            f"📊 Your Roster: {roster_count}/{MAX_ROSTER_SIZE} players\n"
            f"💰 Coins: {format_coins(DEBUT_INITIAL_COINS)}\n"
            f"💎 Gems: {DEBUT_INITIAL_GEMS}\n\n"
            f"**Commands:**\n"
            f"/claim - Get 1 player + {CLAIM_REWARD_COINS} coins (hourly)\n"
            f"/myroster - View your players\n"
            f"/playerinfo [name] - Player details\n"
            f"/daily - Daily reward (tomorrow)\n"
            f"/gspin - Spin wheel (tomorrow)"
        )

        await update.message.reply_text(welcome_msg, parse_mode="Markdown")
        logger.info("Debut complete for user %s: %d players", telegram_user.id, roster_count)

    except Exception as e:
        logger.error("Error in /debut for user %s: %s", telegram_user.id, e, exc_info=True)
        await update.message.reply_text("⚠️ An error occurred. Please try again later.")
    finally:
        db.close()


async def claim_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /claim command – get a random player based on rarity distribution."""
    telegram_user = update.effective_user
    logger.info("User %s (%s) used /claim", telegram_user.id, telegram_user.username)

    db = SessionLocal()
    try:
        # Check if user exists
        user = get_user_by_telegram_id(db, telegram_user.id)
        if not user:
            await update.message.reply_text("❌ Do /debut first!")
            return

        # Check cooldown
        cooldown = check_cooldown(db, user, "claim")
        if not cooldown["ready"]:
            msg = format_cooldown_message("claim", cooldown["remaining_seconds"])
            await update.message.reply_text(msg, parse_mode="Markdown")
            return

        # Generate random player by rarity
        player = get_random_player_by_rarity(db)
        if not player:
            await update.message.reply_text("⚠️ No players available. Please try again later.")
            return

        # Get player stats
        stats = get_player_stats(player)

        # Award coins
        update_user_coins(db, user, CLAIM_REWARD_COINS)

        # Set cooldown
        set_cooldown(db, user, "claim")

        # Generate card image
        card_path = generate_card(stats)

        # Build message
        buy_str = format_coins(stats["buy_value"])
        sell_str = format_coins(stats["sell_value"])

        text = (
            f"🎉 **New Player, Retain or Release!**\n\n"
            f"📛 {stats['name']}\n"
            f"⭐ **Rating:** {stats['rating']} OVR\n"
            f"🎯 **Category:** {stats['category']}\n"
            f"🏏 **Bat Hand:** {stats['bat_hand']}\n"
            f"🎳 **Bowl Hand:** {stats['bowl_hand']}\n"
            f"🌀 **Bowl Style:** {stats['bowl_style']}\n"
            f"💰 **Card Value:** {buy_str} 🪙\n"
            f"💸 **Sell Value:** {sell_str}\n\n"
            f"💰 +{format_coins(CLAIM_REWARD_COINS)} coins added!"
        )

        # Retain/Release buttons
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Retain", callback_data=f"retain_{player.id}_{user.id}"),
                InlineKeyboardButton("❌ Release", callback_data=f"release_{player.id}_{user.id}"),
            ]
        ])

        # Send card image or text
        if card_path and os.path.exists(card_path):
            try:
                with open(card_path, "rb") as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption=text,
                        parse_mode="Markdown",
                        reply_markup=keyboard,
                    )
            finally:
                cleanup_temp_file(card_path)
        else:
            await update.message.reply_text(
                text, parse_mode="Markdown", reply_markup=keyboard
            )

        logger.info(
            "Claim sent for user %s: %s (%d OVR)",
            telegram_user.id,
            player.name,
            player.rating,
        )

    except Exception as e:
        logger.error("Error in /claim for user %s: %s", telegram_user.id, e, exc_info=True)
        await update.message.reply_text("⚠️ An error occurred. Please try again later.")
    finally:
        db.close()


async def gspin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /gspin command – spin the wheel for rewards."""
    telegram_user = update.effective_user
    logger.info("User %s (%s) used /gspin", telegram_user.id, telegram_user.username)

    db = SessionLocal()
    try:
        # Check if user exists
        user = get_user_by_telegram_id(db, telegram_user.id)
        if not user:
            await update.message.reply_text("❌ Do /debut first!")
            return

        # Check cooldown
        cooldown = check_cooldown(db, user, "gspin")
        if not cooldown["ready"]:
            msg = format_cooldown_message("gspin", cooldown["remaining_seconds"])
            await update.message.reply_text(msg, parse_mode="Markdown")
            return

        # Spin the wheel
        weights = [o["weight"] for o in GSPIN_OUTCOMES]
        outcome = random.choices(GSPIN_OUTCOMES, weights=weights, k=1)[0]

        # Set cooldown
        set_cooldown(db, user, "gspin")

        # Process outcome
        reward_details = ""
        if outcome["type"] == "coins":
            amount = random.randint(outcome["min_amount"], outcome["max_amount"])
            update_user_coins(db, user, amount)
            reward_details = f"💰 +{format_coins(amount)} coins added"

        elif outcome["type"] == "gems":
            amount = random.randint(outcome["min_amount"], outcome["max_amount"])
            update_user_gems(db, user, amount)
            reward_details = f"💎 +{amount} gems added"

        elif outcome["type"] == "player":
            player = get_random_player_by_rating(
                db, outcome["min_rating"], outcome["max_rating"]
            )
            if player:
                # Auto-add player to roster if there's space
                if user.roster_count < MAX_ROSTER_SIZE:
                    add_player_to_roster(db, user, player)
                    reward_details = f"🎉 {player.name} - {player.rating} OVR added to roster!"
                else:
                    # If roster is full, give sell value as coins
                    _, sell_value = get_player_value(player.rating)
                    update_user_coins(db, user, sell_value)
                    reward_details = (
                        f"🎉 {player.name} - {player.rating} OVR\n"
                        f"(Roster full! +{format_coins(sell_value)} coins instead)"
                    )
            else:
                # Fallback: give coins
                amount = 5000
                update_user_coins(db, user, amount)
                reward_details = f"💰 +{format_coins(amount)} coins (no player available)"

        text = (
            f"🎡 **GSPIN Wheel Result!**\n\n"
            f"{outcome['emoji']} {outcome['name']}\n\n"
            f"CONGRATULATIONS YOU GET {outcome['type'].upper()}!\n\n"
            f"{reward_details}\n\n"
            f"✅ Reward added to your account!"
        )

        await update.message.reply_text(text, parse_mode="Markdown")
        logger.info("Gspin result for user %s: %s", telegram_user.id, outcome["name"])

    except Exception as e:
        logger.error("Error in /gspin for user %s: %s", telegram_user.id, e, exc_info=True)
        await update.message.reply_text("⚠️ An error occurred. Please try again later.")
    finally:
        db.close()


async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /daily command – daily reward with streak tracking."""
    telegram_user = update.effective_user
    logger.info("User %s (%s) used /daily", telegram_user.id, telegram_user.username)

    db = SessionLocal()
    try:
        # Check if user exists
        user = get_user_by_telegram_id(db, telegram_user.id)
        if not user:
            await update.message.reply_text("❌ Do /debut first!")
            return

        # Check cooldown
        cooldown = check_cooldown(db, user, "daily")
        if not cooldown["ready"]:
            msg = format_cooldown_message("daily", cooldown["remaining_seconds"])
            await update.message.reply_text(msg, parse_mode="Markdown")
            return

        # Award coins
        update_user_coins(db, user, DAILY_REWARD_COINS)

        # Generate random players
        players_added = []
        for _ in range(DAILY_REWARD_PLAYERS):
            player = get_random_player_by_rarity(db)
            if player and user.roster_count < MAX_ROSTER_SIZE:
                add_player_to_roster(db, user, player)
                players_added.append(player)

        # Update streak
        streak_result = update_streak(db, user)

        # Set cooldown
        set_cooldown(db, user, "daily")

        # Build message
        player_lines = "\n".join(
            f"✅ {p.name} - {p.rating} OVR" for p in players_added
        )

        text = (
            f"📅 **Daily Reward Claimed!**\n\n"
            f"✅ +{format_coins(DAILY_REWARD_COINS)} coins\n"
            f"{player_lines}\n\n"
            f"📊 **Streak:** {streak_result['streak_count']}/{STREAK_MILESTONE}\n"
        )

        if streak_result["milestone_reached"]:
            # Give milestone bonus player
            bonus_player = get_random_player_by_rating(db, 81, 85)
            if bonus_player and user.roster_count < MAX_ROSTER_SIZE:
                add_player_to_roster(db, user, bonus_player)
                text += (
                    f"\n🎉 **MILESTONE REACHED!**\n"
                    f"🏆 {bonus_player.name} - {bonus_player.rating} OVR (Streak Bonus)\n"
                    f"📊 Streak resets to 1"
                )
            else:
                text += "\n🎉 **MILESTONE REACHED!** (Roster full, bonus skipped)"
        else:
            remaining = max(0, STREAK_MILESTONE - streak_result["streak_count"])
            text += f"⏳ {remaining} days until 81-85 OVR bonus card"

        if streak_result["reset_occurred"]:
            text += "\n\n⚠️ Streak was reset (missed 2+ days)"

        await update.message.reply_text(text, parse_mode="Markdown")
        logger.info(
            "Daily claimed by user %s: streak=%d",
            telegram_user.id,
            streak_result["streak_count"],
        )

    except Exception as e:
        logger.error("Error in /daily for user %s: %s", telegram_user.id, e, exc_info=True)
        await update.message.reply_text("⚠️ An error occurred. Please try again later.")
    finally:
        db.close()


async def myroster_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /myroster [page] command – display paginated roster with release buttons."""
    telegram_user = update.effective_user
    logger.info("User %s (%s) used /myroster", telegram_user.id, telegram_user.username)

    # Parse optional page number from args
    page = 1
    if context.args:
        try:
            page = max(1, int(context.args[0]))
        except ValueError:
            pass

    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, telegram_user.id)
        if not user:
            await update.message.reply_text("❌ Do /debut first!")
            return

        entries = get_user_roster_sorted(db, user)

        if not entries:
            await update.message.reply_text(
                f"📊 **Your Roster** (0/{MAX_ROSTER_SIZE})\n\n"
                f"No players yet! Use /claim to get players.\n\n"
                f"💰 Total Coins: {format_coins(user.total_coins)}\n"
                f"💎 Total Gems: {user.total_gems}",
                parse_mode="Markdown",
            )
            return

        stats = get_roster_stats(db, user)
        total_pages = max(1, (len(entries) + ROSTER_PAGE_SIZE - 1) // ROSTER_PAGE_SIZE)
        page = min(page, total_pages)
        start = (page - 1) * ROSTER_PAGE_SIZE
        page_entries = entries[start: start + ROSTER_PAGE_SIZE]

        # Build player lines with release buttons
        lines = []
        buttons_row = []
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

        # Group release buttons two per row
        kb_rows = []
        for i in range(0, len(release_buttons), 2):
            kb_rows.append(release_buttons[i: i + 2])

        # Pagination navigation row
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

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb_rows) if kb_rows else None,
        )
        logger.info(
            "Roster page %d/%d displayed for user %s: %d players",
            page, total_pages, telegram_user.id, len(entries),
        )

    except Exception as e:
        logger.error("Error in /myroster for user %s: %s", telegram_user.id, e, exc_info=True)
        await update.message.reply_text("⚠️ An error occurred. Please try again later.")
    finally:
        db.close()


async def playerinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /playerinfo [name] command – show detailed player info."""
    telegram_user = update.effective_user
    logger.info("User %s (%s) used /playerinfo", telegram_user.id, telegram_user.username)

    db = SessionLocal()
    try:
        # Check if user exists
        user = get_user_by_telegram_id(db, telegram_user.id)
        if not user:
            await update.message.reply_text("❌ Do /debut first!")
            return

        # Get player name from arguments
        if not context.args:
            await update.message.reply_text(
                "❌ Usage: `/playerinfo Player Name`\n"
                "Example: `/playerinfo Virat Kohli`",
                parse_mode="Markdown",
            )
            return

        player_name = " ".join(context.args)

        # Search for player
        player = get_player_by_name(db, player_name)
        if not player:
            # Try partial search
            matches = search_players_by_name(db, player_name, limit=5)
            if matches:
                suggestions = "\n".join(f"  • {p.name}" for p in matches)
                await update.message.reply_text(
                    f"❌ Player not found. Did you mean:\n{suggestions}\n\n"
                    f"Use: `/playerinfo Exact Name`",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text("❌ Player not found")
            return

        # Get stats and format
        stats = get_player_stats(player)

        # Check if user owns this player
        roster_entries = get_user_roster(db, user)
        owned = any(e.player_id == player.id for e in roster_entries)
        acquired_date = None
        if owned:
            for entry in roster_entries:
                if entry.player_id == player.id:
                    acquired_date = entry.acquired_date.strftime("%d %b %Y")
                    break

        text = format_player_info(stats, acquired_date)
        if owned:
            text += "\n\n✅ You own this player"

        # Try to generate card image
        card_path = generate_card(stats)
        if card_path and os.path.exists(card_path):
            try:
                with open(card_path, "rb") as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption=text,
                        parse_mode="Markdown",
                    )
            finally:
                cleanup_temp_file(card_path)
        else:
            await update.message.reply_text(text, parse_mode="Markdown")

        logger.info("Player info displayed: %s for user %s", player.name, telegram_user.id)

    except Exception as e:
        logger.error("Error in /playerinfo for user %s: %s", telegram_user.id, e, exc_info=True)
        await update.message.reply_text("⚠️ An error occurred. Please try again later.")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────
# /release [player_name]
# ─────────────────────────────────────────────────────────────────────

async def release_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /release [player_name] – show confirmation dialog before releasing."""
    telegram_user = update.effective_user
    logger.info("User %s (%s) used /release", telegram_user.id, telegram_user.username)

    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, telegram_user.id)
        if not user:
            await update.message.reply_text("❌ Do /debut first!")
            return

        if not context.args:
            await update.message.reply_text(
                "❌ Usage: `/release Player Name`\n"
                "Example: `/release Virat Kohli`",
                parse_mode="Markdown",
            )
            return

        player_name = " ".join(context.args)
        entries = get_user_roster_sorted(db, user)

        # Find roster entry by player name (case-insensitive)
        matched_entry = None
        for e in entries:
            if e.player.name.lower() == player_name.lower():
                matched_entry = e
                break

        if not matched_entry:
            # Try partial match suggestions
            suggestions = [
                e.player.name for e in entries
                if player_name.lower() in e.player.name.lower()
            ][:5]
            if suggestions:
                sugg_text = "\n".join(f"  • {n}" for n in suggestions)
                await update.message.reply_text(
                    f"❌ No player named '{player_name}' in your roster. Did you mean:\n{sugg_text}",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text(
                    f"❌ No player named '{player_name}' in your roster."
                )
            return

        player = matched_entry.player
        sell_val = BUY_SELL_VALUES.get(player.rating, (200, 120))[1]

        text = (
            f"🔴 **RELEASE PLAYER?**\n\n"
            f"Player: {player.name}\n"
            f"Rating: {player.rating} OVR\n"
            f"Category: {player.category}\n\n"
            f"💸 You will receive: {format_coins(sell_val)} 🪙\n"
        )

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "✅ Confirm Release",
                callback_data=f"release_confirm_{matched_entry.id}_{user.id}",
            ),
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data=f"release_cancel_{matched_entry.id}_{user.id}",
            ),
        ]])

        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

    except Exception as e:
        logger.error("Error in /release for user %s: %s", telegram_user.id, e, exc_info=True)
        await update.message.reply_text("⚠️ An error occurred. Please try again later.")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────
# /releasemultiple
# ─────────────────────────────────────────────────────────────────────

async def releasemultiple_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /releasemultiple – show duplicate players with release buttons."""
    telegram_user = update.effective_user
    logger.info("User %s (%s) used /releasemultiple", telegram_user.id, telegram_user.username)

    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, telegram_user.id)
        if not user:
            await update.message.reply_text("❌ Do /debut first!")
            return

        duplicates = get_duplicate_players(db, user)

        if not duplicates:
            await update.message.reply_text(
                "📋 You have no duplicate players.\n"
                "Use /myroster to see your full roster."
            )
            return

        lines = []
        kb_rows = []
        for dup in duplicates:
            player = dup["player"]
            count = dup["count"]
            sv = dup["sell_value"]
            lines.append(
                f"• {player.name} - {player.rating} OVR (Qty: {count})\n"
                f"  💸 {format_coins(sv)} each"
            )
            # One release button per copy (up to 5 shown)
            row = []
            for idx, entry in enumerate(dup["entries"][:5], 1):
                row.append(InlineKeyboardButton(
                    f"Release copy {idx}" if count > 1 else "Release",
                    callback_data=f"release_multi_one_{entry.id}_{user.id}",
                ))
            kb_rows.append(row)

        text = (
            f"📋 **YOUR DUPLICATE PLAYERS**\n\n"
            f"Found {len(duplicates)} players owned multiple times:\n\n"
            + "\n\n".join(lines)
        )

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb_rows) if kb_rows else None,
        )

    except Exception as e:
        logger.error(
            "Error in /releasemultiple for user %s: %s", telegram_user.id, e, exc_info=True
        )
        await update.message.reply_text("⚠️ An error occurred. Please try again later.")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────
# /trade @username
# ─────────────────────────────────────────────────────────────────────

async def trade_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /trade @username – start the trade flow."""
    telegram_user = update.effective_user
    logger.info("User %s (%s) used /trade", telegram_user.id, telegram_user.username)

    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, telegram_user.id)
        if not user:
            await update.message.reply_text("❌ Do /debut first!")
            return

        if not context.args:
            await update.message.reply_text(
                "❌ Usage: `/trade @username`\nExample: `/trade @PlayerTwo`",
                parse_mode="Markdown",
            )
            return

        raw_target = context.args[0]
        if not raw_target.startswith("@"):
            await update.message.reply_text(
                "❌ Invalid username format. Use `/trade @username`",
                parse_mode="Markdown",
            )
            return

        target_username = raw_target.lstrip("@")

        # Validate username characters
        if not re.match(r"^[a-zA-Z0-9_]{3,32}$", target_username):
            await update.message.reply_text(
                "❌ Invalid username format. Use `/trade @username`",
                parse_mode="Markdown",
            )
            return

        receiver = get_user_by_username(db, target_username)
        if not receiver:
            await update.message.reply_text(
                f"❌ User @{target_username} not found. They must use /debut first."
            )
            return

        if receiver.id == user.id:
            await update.message.reply_text("❌ You cannot trade with yourself")
            return

        # Check if initiator has any tradeable players
        my_ratings = get_tradeable_ratings(db, user)
        if not my_ratings:
            await update.message.reply_text(
                f"❌ You have no players rated {TRADE_ALLOWED_MIN_RATING}+ OVR to trade"
            )
            return

        matching = get_matching_tradeable_ratings(db, user, receiver)
        if not matching:
            recv_uname = receiver.username or str(receiver.telegram_id)
            await update.message.reply_text(
                f"❌ @{recv_uname} has no players with your tradeable ratings"
            )
            return

        # Build rating overview
        entries_sorted = get_user_roster_sorted(db, user)
        their_entries_sorted = get_user_roster_sorted(db, receiver)

        def _player_list_for_ratings(entries, ratings):
            shown: set = set()
            lines = []
            for e in entries:
                r = e.player.rating
                if r in ratings and r not in shown:
                    shown.add(r)
                    lines.append(f"• {r} OVR: {e.player.name}")
            return "\n".join(lines) if lines else "None"

        my_lines = _player_list_for_ratings(entries_sorted, set(my_ratings))
        their_lines = _player_list_for_ratings(their_entries_sorted, set(get_tradeable_ratings(db, receiver)))
        recv_uname = receiver.username or str(receiver.telegram_id)

        text = (
            f"🔍 **SEARCHING FOR TRADE MATCHES WITH @{recv_uname}**\n\n"
            f"Your tradeable players (rating ≥ {TRADE_ALLOWED_MIN_RATING}):\n{my_lines}\n\n"
            f"Their tradeable players (rating ≥ {TRADE_ALLOWED_MIN_RATING}):\n{their_lines}\n\n"
            f"✅ Matching Ratings: {', '.join(str(r) + ' OVR' for r in matching)}"
        )

        buttons = [
            [InlineKeyboardButton(
                f"Select {r} OVR",
                callback_data=f"trade_rating_{r}_{receiver.telegram_id}_{user.telegram_id}",
            )]
            for r in matching
        ]
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="trade_cancel_offer")])

        await update.message.reply_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    except Exception as e:
        logger.error("Error in /trade for user %s: %s", telegram_user.id, e, exc_info=True)
        await update.message.reply_text("⚠️ An error occurred. Please try again later.")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────
# /mytradesettings
# ─────────────────────────────────────────────────────────────────────

async def mytradesettings_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /mytradesettings – show current trade settings."""
    text = (
        f"⚙️ **TRADE SETTINGS**\n\n"
        f"Current Rules:\n"
        f"• Minimum Rating: {TRADE_ALLOWED_MIN_RATING} OVR\n"
        f"• Trade Fee: {TRADE_FEE_PERCENT}% from both parties\n"
        f"• Offer Expires: {TRADE_EXPIRES_SECONDS} seconds\n"
        f"• Max Active Trades: 1\n"
        f"• Allowed Ratings: Only same rating"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
