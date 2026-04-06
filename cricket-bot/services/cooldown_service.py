"""Cooldown management service."""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from config.constants import COOLDOWN_CLAIM, COOLDOWN_DAILY, COOLDOWN_GSPIN
from database.crud import get_user_stats, update_last_claim, update_last_daily, update_last_gspin
from database.models import User, UserStats

logger = logging.getLogger(__name__)

COOLDOWN_MAP = {
    "claim": COOLDOWN_CLAIM,
    "daily": COOLDOWN_DAILY,
    "gspin": COOLDOWN_GSPIN,
}


def check_cooldown(db: Session, user: User, command: str) -> dict:
    """
    Check if a command is on cooldown for a user.

    Returns:
        dict with keys: ready (bool), remaining_seconds (int)
    """
    stats = get_user_stats(db, user)
    if not stats:
        return {"ready": True, "remaining_seconds": 0}

    cooldown_seconds = COOLDOWN_MAP.get(command, 0)
    last_used = _get_last_used(stats, command)

    if last_used is None:
        return {"ready": True, "remaining_seconds": 0}

    now = datetime.now(timezone.utc)
    # Ensure last_used is timezone-aware
    if last_used.tzinfo is None:
        last_used = last_used.replace(tzinfo=timezone.utc)

    elapsed = (now - last_used).total_seconds()
    remaining = max(0, int(cooldown_seconds - elapsed))

    ready = remaining <= 0
    logger.info(
        "Cooldown check for user %s, command=%s: ready=%s, remaining=%ds",
        user.telegram_id,
        command,
        ready,
        remaining,
    )
    return {"ready": ready, "remaining_seconds": remaining}


def set_cooldown(db: Session, user: User, command: str) -> None:
    """Update the cooldown timestamp for a command."""
    stats = get_user_stats(db, user)
    if not stats:
        logger.error("No stats found for user %s", user.telegram_id)
        return

    if command == "claim":
        update_last_claim(db, stats)
    elif command == "daily":
        update_last_daily(db, stats)
    elif command == "gspin":
        update_last_gspin(db, stats)
    else:
        logger.warning("Unknown command for cooldown: %s", command)


def format_cooldown_time(seconds: int) -> str:
    """Format remaining cooldown seconds into a human-readable string."""
    if seconds <= 0:
        return "Ready!"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def _get_last_used(stats: UserStats, command: str) -> Optional[datetime]:
    """Get the last-used timestamp for a given command."""
    if command == "claim":
        return stats.last_claim
    elif command == "daily":
        return stats.last_daily
    elif command == "gspin":
        return stats.last_gspin
    return None
