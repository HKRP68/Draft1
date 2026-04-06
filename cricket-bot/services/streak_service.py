"""Streak tracking service for /daily command."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from config.constants import STREAK_MILESTONE, STREAK_MISS_LIMIT
from database.crud import (
    get_user_stats,
    increment_streaks_completed,
    reset_streak as db_reset_streak,
    update_streak as db_update_streak,
)
from database.models import User

logger = logging.getLogger(__name__)


def check_streak(db: Session, user: User) -> dict:
    """
    Check the current streak status for a user.

    Returns:
        dict with keys:
            - streak_count (int)
            - should_reset (bool): True if user missed too many days
            - days_until_milestone (int)
            - milestone_reached (bool)
    """
    stats = get_user_stats(db, user)
    if not stats:
        return {
            "streak_count": 0,
            "should_reset": False,
            "days_until_milestone": STREAK_MILESTONE,
            "milestone_reached": False,
        }

    should_reset = _should_reset_streak(stats.last_daily)
    current_count = 0 if should_reset else stats.streak_count

    return {
        "streak_count": current_count,
        "should_reset": should_reset,
        "days_until_milestone": max(0, STREAK_MILESTONE - current_count),
        "milestone_reached": current_count >= STREAK_MILESTONE,
    }


def update_streak(db: Session, user: User) -> dict:
    """
    Update the streak after a /daily command.

    Returns:
        dict with keys:
            - streak_count (int): new streak count
            - milestone_reached (bool): True if streak hit 14
            - reset_occurred (bool): True if streak was reset
    """
    stats = get_user_stats(db, user)
    if not stats:
        return {"streak_count": 0, "milestone_reached": False, "reset_occurred": False}

    reset_occurred = _should_reset_streak(stats.last_daily)
    if reset_occurred:
        db_reset_streak(db, stats)
        logger.info("Streak reset for user %s (missed %d+ days)", user.telegram_id, STREAK_MISS_LIMIT)

    # Increment streak
    new_count = stats.streak_count + 1
    db_update_streak(db, stats, new_count)

    milestone_reached = new_count >= STREAK_MILESTONE
    if milestone_reached:
        increment_streaks_completed(db, stats)
        # Reset streak back to 0 after milestone
        db_update_streak(db, stats, 0)
        logger.info(
            "Streak milestone reached for user %s! Total completed: %d",
            user.telegram_id,
            stats.total_streaks_completed,
        )

    return {
        "streak_count": new_count,
        "milestone_reached": milestone_reached,
        "reset_occurred": reset_occurred,
    }


def reset_streak_for_user(db: Session, user: User) -> None:
    """Manually reset a user's streak."""
    stats = get_user_stats(db, user)
    if stats:
        db_reset_streak(db, stats)
        logger.info("Manually reset streak for user %s", user.telegram_id)


def _should_reset_streak(last_daily: Optional[datetime]) -> bool:
    """Check if the streak should be reset based on last daily claim."""
    if last_daily is None:
        return False  # First daily, no reset needed

    now = datetime.now(timezone.utc)
    if last_daily.tzinfo is None:
        last_daily = last_daily.replace(tzinfo=timezone.utc)

    days_since = (now - last_daily).days
    return days_since > STREAK_MISS_LIMIT
