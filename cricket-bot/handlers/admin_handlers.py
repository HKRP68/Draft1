"""Telegram admin commands for managing players directly from a private chat / channel.

Only users whose Telegram ID is listed in the ``ADMIN_TELEGRAM_IDS``
environment variable may use these commands.

Commands
--------
/addplayer   – create a new player
/editplayer  – edit an existing player's fields
/delplayer   – deactivate a player (soft-delete)
/listplayers – search / list players with pagination
/playerstats – show database statistics
"""

import logging
import math

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config.database import SessionLocal
from config.settings import ADMIN_TELEGRAM_IDS
from database.models import Player

logger = logging.getLogger(__name__)

ADMIN_PAGE_SIZE = 15

# ── Helpers ─────────────────────────────────────────────────────

def _is_admin(telegram_id: int) -> bool:
    """Return True when *telegram_id* is in the allow-list."""
    return telegram_id in ADMIN_TELEGRAM_IDS


def _not_admin_msg() -> str:
    return "🚫 You don't have permission to use this command."


def _to_int(value: str):
    try:
        return int(value.strip())
    except (ValueError, TypeError):
        return None


def _to_float(value: str):
    try:
        return float(value.strip())
    except (ValueError, TypeError):
        return None


# Fields that can be edited via /editplayer and their types.
_EDITABLE_FIELDS: dict[str, str] = {
    "name": "str",
    "version": "str",
    "rating": "int",
    "category": "str",
    "country": "str",
    "bat_hand": "str",
    "bowl_hand": "str",
    "bowl_style": "str",
    "bat_rating": "int",
    "bowl_rating": "int",
    "bat_avg": "float",
    "strike_rate": "float",
    "runs": "int",
    "centuries": "int",
    "bowl_avg": "float",
    "economy": "float",
    "wickets": "int",
    "is_active": "bool",
    "image_url": "str",
}

VALID_CATEGORIES = {"Batsman", "Bowler", "All-rounder", "Wicket Keeper"}


# ═══════════════════════════════════════════════════════════════
# /addplayer
# ═══════════════════════════════════════════════════════════════

async def addplayer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a new player to the database.

    Usage::

        /addplayer Virat Kohli | 95 | Batsman | India
        /addplayer MS Dhoni | 90 | Wicket Keeper | India | Right | Right | Medium Pacer
    """
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text(_not_admin_msg())
        return

    if not context.args:
        await update.message.reply_text(
            "📝 **Usage:**\n"
            "`/addplayer Name | Rating | Category | Country`\n\n"
            "**Optional extended format:**\n"
            "`/addplayer Name | Rating | Category | Country | BatHand | BowlHand | BowlStyle`\n\n"
            "**Example:**\n"
            "`/addplayer Virat Kohli | 95 | Batsman | India`",
            parse_mode="Markdown",
        )
        return

    raw = " ".join(context.args)
    parts = [p.strip() for p in raw.split("|")]

    if len(parts) < 4:
        await update.message.reply_text(
            "❌ Need at least: `Name | Rating | Category | Country`",
            parse_mode="Markdown",
        )
        return

    name = parts[0]
    rating = _to_int(parts[1])
    category = parts[2]
    country = parts[3]

    if not name:
        await update.message.reply_text("❌ Player name cannot be empty.")
        return
    if rating is None or not (50 <= rating <= 100):
        await update.message.reply_text("❌ Rating must be an integer between 50 and 100.")
        return
    if category not in VALID_CATEGORIES:
        await update.message.reply_text(
            f"❌ Category must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
        )
        return

    bat_hand = parts[4].strip() if len(parts) > 4 and parts[4].strip() else None
    bowl_hand = parts[5].strip() if len(parts) > 5 and parts[5].strip() else None
    bowl_style = parts[6].strip() if len(parts) > 6 and parts[6].strip() else None

    db = SessionLocal()
    try:
        from sqlalchemy import func
        existing = db.query(Player).filter(func.lower(Player.name) == name.lower()).first()
        if existing:
            await update.message.reply_text(f"⚠️ A player named **{existing.name}** already exists (ID {existing.id}).", parse_mode="Markdown")
            return

        player = Player(
            name=name,
            rating=rating,
            category=category,
            country=country,
            bat_hand=bat_hand,
            bowl_hand=bowl_hand,
            bowl_style=bowl_style,
            is_active=True,
        )
        db.add(player)
        db.commit()
        db.refresh(player)

        await update.message.reply_text(
            f"✅ **Player Created!**\n\n"
            f"🆔 ID: {player.id}\n"
            f"📛 Name: {player.name}\n"
            f"⭐ Rating: {player.rating}\n"
            f"🎯 Category: {player.category}\n"
            f"🌍 Country: {player.country}\n"
            f"🏏 Bat: {player.bat_hand or '—'}  |  🎳 Bowl: {player.bowl_hand or '—'}\n"
            f"🌀 Style: {player.bowl_style or '—'}",
            parse_mode="Markdown",
        )
        logger.info("Admin %s created player '%s' (id=%d)", update.effective_user.id, player.name, player.id)
    except Exception as exc:
        logger.exception("addplayer failed")
        await update.message.reply_text(f"❌ Error: {exc}")
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# /editplayer
# ═══════════════════════════════════════════════════════════════

async def editplayer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Edit one or more fields on an existing player.

    Usage::

        /editplayer Virat Kohli | rating=97, country=India
        /editplayer MS Dhoni | is_active=false
    """
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text(_not_admin_msg())
        return

    if not context.args:
        fields_list = ", ".join(sorted(_EDITABLE_FIELDS.keys()))
        await update.message.reply_text(
            "📝 **Usage:**\n"
            "`/editplayer Player Name | field=value, field=value`\n\n"
            f"**Editable fields:** `{fields_list}`\n\n"
            "**Example:**\n"
            "`/editplayer Virat Kohli | rating=97, country=India`",
            parse_mode="Markdown",
        )
        return

    raw = " ".join(context.args)
    if "|" not in raw:
        await update.message.reply_text("❌ Use `|` to separate name from fields.\n`/editplayer Name | field=value`", parse_mode="Markdown")
        return

    name_part, fields_part = raw.split("|", 1)
    name = name_part.strip()

    db = SessionLocal()
    try:
        from sqlalchemy import func
        player = db.query(Player).filter(func.lower(Player.name) == name.lower()).first()
        if not player:
            await update.message.reply_text(f"❌ No player found with name **{name}**.", parse_mode="Markdown")
            return

        changes: dict[str, object] = {}
        for pair in fields_part.split(","):
            pair = pair.strip()
            if "=" not in pair:
                continue
            key, val = pair.split("=", 1)
            key = key.strip().lower()
            val = val.strip()
            if key not in _EDITABLE_FIELDS:
                await update.message.reply_text(f"❌ Unknown field: `{key}`", parse_mode="Markdown")
                return
            ftype = _EDITABLE_FIELDS[key]
            if ftype == "int":
                parsed = _to_int(val)
                if parsed is None:
                    await update.message.reply_text(f"❌ `{key}` must be an integer.", parse_mode="Markdown")
                    return
                if key == "rating" and not (50 <= parsed <= 100):
                    await update.message.reply_text("❌ Rating must be 50–100.")
                    return
                changes[key] = parsed
            elif ftype == "float":
                parsed = _to_float(val)
                if parsed is None:
                    await update.message.reply_text(f"❌ `{key}` must be a number.", parse_mode="Markdown")
                    return
                changes[key] = parsed
            elif ftype == "bool":
                changes[key] = val.lower() in ("true", "1", "yes", "on")
            else:
                if key == "category" and val not in VALID_CATEGORIES:
                    await update.message.reply_text(
                        f"❌ Category must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
                    )
                    return
                changes[key] = val

        if not changes:
            await update.message.reply_text("❌ No valid field=value pairs found.")
            return

        for k, v in changes.items():
            setattr(player, k, v)
        db.commit()
        db.refresh(player)

        lines = [f"• **{k}** → `{v}`" for k, v in changes.items()]
        await update.message.reply_text(
            f"✅ **Player Updated:** {player.name} (ID {player.id})\n\n" + "\n".join(lines),
            parse_mode="Markdown",
        )
        logger.info("Admin %s edited player '%s': %s", update.effective_user.id, player.name, changes)
    except Exception as exc:
        logger.exception("editplayer failed")
        await update.message.reply_text(f"❌ Error: {exc}")
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# /delplayer
# ═══════════════════════════════════════════════════════════════

async def delplayer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deactivate (soft-delete) a player.

    Usage::

        /delplayer Virat Kohli
    """
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text(_not_admin_msg())
        return

    if not context.args:
        await update.message.reply_text(
            "📝 **Usage:** `/delplayer Player Name`\n\n"
            "This sets `is_active=False` so the player won't appear in claims.",
            parse_mode="Markdown",
        )
        return

    name = " ".join(context.args).strip()

    db = SessionLocal()
    try:
        from sqlalchemy import func
        player = db.query(Player).filter(func.lower(Player.name) == name.lower()).first()
        if not player:
            await update.message.reply_text(f"❌ No player found with name **{name}**.", parse_mode="Markdown")
            return

        if not player.is_active:
            await update.message.reply_text(f"ℹ️ **{player.name}** is already deactivated.", parse_mode="Markdown")
            return

        player.is_active = False
        db.commit()

        await update.message.reply_text(
            f"🗑️ **{player.name}** (ID {player.id}, {player.rating} OVR) has been **deactivated**.\n"
            f"To reactivate: `/editplayer {player.name} | is_active=true`",
            parse_mode="Markdown",
        )
        logger.info("Admin %s deactivated player '%s' (id=%d)", update.effective_user.id, player.name, player.id)
    except Exception as exc:
        logger.exception("delplayer failed")
        await update.message.reply_text(f"❌ Error: {exc}")
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# /listplayers
# ═══════════════════════════════════════════════════════════════

async def listplayers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search/list players with inline-button pagination.

    Usage::

        /listplayers          – first page of all players
        /listplayers kohli    – search by name
    """
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text(_not_admin_msg())
        return

    search = " ".join(context.args).strip() if context.args else ""
    await _send_player_list(update, search=search, page=1)


async def _send_player_list(update_or_query, *, search: str, page: int, edit: bool = False) -> None:
    """Build and send/edit the paginated player list message."""
    db = SessionLocal()
    try:
        from sqlalchemy import func
        query = db.query(Player)
        if search:
            query = query.filter(func.lower(Player.name).contains(search.lower()))

        total = query.count()
        total_pages = max(1, math.ceil(total / ADMIN_PAGE_SIZE))
        page = max(1, min(page, total_pages))

        players = (
            query.order_by(Player.rating.desc(), Player.name)
            .offset((page - 1) * ADMIN_PAGE_SIZE)
            .limit(ADMIN_PAGE_SIZE)
            .all()
        )

        if not players and not search:
            text = "📭 No players in the database."
        elif not players:
            text = f"🔍 No players matching **{search}**."
        else:
            lines = []
            for p in players:
                status = "✅" if p.is_active else "❌"
                lines.append(f"{status} `{p.id:>4}` | **{p.name}** | {p.rating} OVR | {p.category}")
            header = f"📋 **Players** (page {page}/{total_pages}, total {total})"
            if search:
                header += f"\n🔍 Search: _{search}_"
            text = header + "\n\n" + "\n".join(lines)

        # Build navigation buttons
        kb_rows: list[list[InlineKeyboardButton]] = []
        nav = []
        if page > 1:
            cb = f"adm_lp_{page - 1}_{search}" if search else f"adm_lp_{page - 1}_"
            nav.append(InlineKeyboardButton("◀️ Prev", callback_data=cb[:64]))
        if page < total_pages:
            cb = f"adm_lp_{page + 1}_{search}" if search else f"adm_lp_{page + 1}_"
            nav.append(InlineKeyboardButton("Next ▶️", callback_data=cb[:64]))
        if nav:
            kb_rows.append(nav)

        markup = InlineKeyboardMarkup(kb_rows) if kb_rows else None

        if edit:
            # Called from a callback query
            await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
        else:
            await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
    finally:
        db.close()


async def admin_listplayers_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pagination callback for /listplayers (adm_lp_<page>_<search>)."""
    query = update.callback_query
    await query.answer()

    if not _is_admin(update.effective_user.id):
        await query.answer("🚫 Not authorized.", show_alert=True)
        return

    data = query.data  # adm_lp_<page>_<search>
    parts = data.split("_", 3)  # ['adm', 'lp', page, search]
    if len(parts) < 3:
        return
    page = _to_int(parts[2]) or 1
    search = parts[3] if len(parts) > 3 else ""

    await _send_player_list(query, search=search, page=page, edit=True)


# ═══════════════════════════════════════════════════════════════
# /playerstats
# ═══════════════════════════════════════════════════════════════

async def playerstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show high-level database statistics.

    Usage::

        /playerstats
    """
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text(_not_admin_msg())
        return

    db = SessionLocal()
    try:
        from sqlalchemy import func
        total = db.query(func.count(Player.id)).scalar() or 0
        active = db.query(func.count(Player.id)).filter(Player.is_active == True).scalar() or 0  # noqa: E712
        inactive = total - active

        # Per-category counts
        category_rows = (
            db.query(Player.category, func.count(Player.id))
            .filter(Player.is_active == True)  # noqa: E712
            .group_by(Player.category)
            .all()
        )
        cat_lines = [f"  • {cat}: {cnt}" for cat, cnt in sorted(category_rows)]

        # Rating distribution
        rating_rows = (
            db.query(
                func.min(Player.rating),
                func.max(Player.rating),
                func.round(func.avg(Player.rating), 1),
            )
            .filter(Player.is_active == True)  # noqa: E712
            .first()
        )
        min_r, max_r, avg_r = rating_rows if rating_rows[0] else (0, 0, 0)

        from database.models import User, UserRoster
        user_count = db.query(func.count(User.id)).scalar() or 0
        roster_count = db.query(func.count(UserRoster.id)).scalar() or 0

        text = (
            f"📊 **Database Statistics**\n\n"
            f"👥 **Users:** {user_count}\n"
            f"📦 **Roster entries:** {roster_count}\n\n"
            f"🏏 **Players:** {total} total\n"
            f"  ✅ Active: {active}\n"
            f"  ❌ Inactive: {inactive}\n\n"
            f"🎯 **By Category:**\n" + "\n".join(cat_lines) + "\n\n"
            f"⭐ **Ratings:** {min_r} – {max_r} (avg {avg_r})"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as exc:
        logger.exception("playerstats failed")
        await update.message.reply_text(f"❌ Error: {exc}")
    finally:
        db.close()
