"""Telegram command handlers for /debut, /claim, /myroster, /playerinfo, /daily, /gspin."""

import logging
import os
import random

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
    STREAK_MILESTONE,
)
from config.database import SessionLocal
from database.crud import (
    add_player_to_roster,
    create_user,
    get_player_by_name,
    get_user_by_telegram_id,
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
    """Handle /myroster command – display user's roster."""
    telegram_user = update.effective_user
    logger.info("User %s (%s) used /myroster", telegram_user.id, telegram_user.username)

    db = SessionLocal()
    try:
        # Check if user exists
        user = get_user_by_telegram_id(db, telegram_user.id)
        if not user:
            await update.message.reply_text("❌ Do /debut first!")
            return

        # Get roster
        roster_entries = get_user_roster(db, user)

        if not roster_entries:
            await update.message.reply_text(
                f"📊 **Your Roster** (0/{MAX_ROSTER_SIZE})\n\n"
                f"No players yet! Use /claim to get players.\n\n"
                f"💰 Total Coins: {format_coins(user.total_coins)}\n"
                f"💎 Total Gems: {user.total_gems}",
                parse_mode="Markdown",
            )
            return

        # Format roster
        lines = []
        total_rating = 0
        for i, entry in enumerate(roster_entries):
            player = entry.player
            lines.append(
                format_roster_entry(i, player.name, player.rating, player.category)
            )
            total_rating += player.rating

        avg_rating = round(total_rating / len(roster_entries), 1) if roster_entries else 0
        roster_text = "\n".join(lines)

        text = (
            f"📊 **Your Roster** ({len(roster_entries)}/{MAX_ROSTER_SIZE})\n\n"
            f"{roster_text}\n\n"
            f"💰 Total Coins: {format_coins(user.total_coins)}\n"
            f"💎 Total Gems: {user.total_gems}\n"
            f"📊 Average Team Rating: {avg_rating}"
        )

        await update.message.reply_text(text, parse_mode="Markdown")
        logger.info("Roster displayed for user %s: %d players", telegram_user.id, len(roster_entries))

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
