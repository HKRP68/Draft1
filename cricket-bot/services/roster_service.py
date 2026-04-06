"""Roster management service – release players, compute stats."""

import logging
from collections import Counter
from typing import Optional

from sqlalchemy.orm import Session

from config.constants import BUY_SELL_VALUES
from database.crud import (
    get_roster_entry_by_id,
    get_user_roster,
    remove_roster_entry,
    update_user_coins,
)
from database.models import Player, User, UserRoster

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────

def _sell_value(rating: int) -> int:
    """Return the sell value for a given rating (0 if unknown)."""
    if rating in BUY_SELL_VALUES:
        return BUY_SELL_VALUES[rating][1]
    return 120  # fallback


def _buy_value(rating: int) -> int:
    """Return the buy value for a given rating."""
    if rating in BUY_SELL_VALUES:
        return BUY_SELL_VALUES[rating][0]
    return 200  # fallback


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

def get_user_roster_sorted(db: Session, user: User) -> list[UserRoster]:
    """Return all roster entries sorted by rating desc, then name."""
    entries = get_user_roster(db, user)
    entries.sort(key=lambda e: (-e.player.rating, e.player.name))
    return entries


def get_roster_stats(db: Session, user: User) -> dict:
    """Compute roster statistics for display."""
    entries = get_user_roster(db, user)
    if not entries:
        return {
            "total_players": 0,
            "total_value": 0,
            "avg_rating": 0.0,
            "duplicate_count": 0,
            "rating_breakdown": {},
        }

    player_ids = [e.player_id for e in entries]
    id_counts = Counter(player_ids)
    duplicate_count = sum(c - 1 for c in id_counts.values() if c > 1)

    total_value = sum(_sell_value(e.player.rating) for e in entries)
    avg_rating = round(sum(e.player.rating for e in entries) / len(entries), 1)

    rating_breakdown: dict[int, int] = {}
    for e in entries:
        rating_breakdown[e.player.rating] = rating_breakdown.get(e.player.rating, 0) + 1

    return {
        "total_players": len(entries),
        "total_value": total_value,
        "avg_rating": avg_rating,
        "duplicate_count": duplicate_count,
        "rating_breakdown": dict(sorted(rating_breakdown.items(), reverse=True)),
    }


def release_player_by_entry_id(
    db: Session, user: User, entry_id: int
) -> dict:
    """
    Release a specific UserRoster entry (identified by entry_id).
    Returns {success, player_name, sell_value, new_balance} or {success:False, error}.
    """
    entry = get_roster_entry_by_id(db, entry_id)
    if not entry or entry.user_id != user.id:
        return {"success": False, "error": "Player not found in your roster"}

    player: Player = entry.player
    sv = _sell_value(player.rating)

    remove_roster_entry(db, user, entry)
    update_user_coins(db, user, sv)

    logger.info(
        "roster_service: user=%s released %s (%d OVR) for %d coins",
        user.telegram_id,
        player.name,
        player.rating,
        sv,
    )
    return {
        "success": True,
        "player_name": player.name,
        "rating": player.rating,
        "sell_value": sv,
        "new_balance": user.total_coins,
    }


def release_multiple_by_entry_ids(
    db: Session, user: User, entry_ids: list[int]
) -> dict:
    """
    Release multiple players by their entry IDs.
    Returns {success, released_count, total_value, new_balance, released}.
    """
    released = []
    total_value = 0

    for eid in entry_ids:
        result = release_player_by_entry_id(db, user, eid)
        if result["success"]:
            released.append(result)
            total_value += result["sell_value"]

    logger.info(
        "roster_service: user=%s released %d players for %d total coins",
        user.telegram_id,
        len(released),
        total_value,
    )
    return {
        "success": True,
        "released_count": len(released),
        "total_value": total_value,
        "new_balance": user.total_coins,
        "released": released,
    }


def get_players_by_rating(db: Session, user: User, rating: int) -> list[UserRoster]:
    """Return all roster entries for the user with exact rating."""
    entries = get_user_roster(db, user)
    return [e for e in entries if e.player.rating == rating]


def player_exists_in_roster(db: Session, user: User, player_id: int) -> bool:
    """Check if the user owns at least one copy of a player."""
    entries = get_user_roster(db, user)
    return any(e.player_id == player_id for e in entries)


def get_duplicate_players(db: Session, user: User) -> list[dict]:
    """
    Return players that appear more than once in the user's roster.
    Each element: {player, entries, count, sell_value}.
    """
    entries = get_user_roster(db, user)
    by_player: dict[int, list[UserRoster]] = {}
    for e in entries:
        by_player.setdefault(e.player_id, []).append(e)

    result = []
    for pid, group in by_player.items():
        if len(group) > 1:
            player = group[0].player
            result.append({
                "player": player,
                "entries": group,
                "count": len(group),
                "sell_value": _sell_value(player.rating),
            })
    result.sort(key=lambda x: (-x["player"].rating, x["player"].name))
    return result


def can_afford_player(db: Session, user: User, player_rating: int) -> dict:
    """Check whether the user can afford the buy price of a player."""
    bv = _buy_value(player_rating)
    can_afford = user.total_coins >= bv
    return {
        "can_afford": can_afford,
        "buy_value": bv,
        "shortage": max(0, bv - user.total_coins),
    }


def get_roster_entry_for_trade(
    db: Session, user: User, player_id: int
) -> Optional[UserRoster]:
    """Return the first roster entry for a given player owned by the user."""
    entries = get_user_roster(db, user)
    for e in entries:
        if e.player_id == player_id:
            return e
    return None
