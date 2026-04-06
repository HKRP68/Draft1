"""Player generation, stats, and rarity services."""

import logging
import random
from typing import Optional

from sqlalchemy.orm import Session

from config.constants import (
    BUY_SELL_VALUES,
    CLAIM_RARITY_DISTRIBUTION,
    RATING_TIERS,
)
from database.crud import get_random_player_in_range
from database.models import Player

logger = logging.getLogger(__name__)


def get_tier_info(rating: int) -> tuple[str, str, str]:
    """Return (tier_name, color, emoji) for a given rating."""
    for (low, high), info in RATING_TIERS.items():
        if low <= rating <= high:
            return info["name"], info["color"], info["emoji"]
    return "Common", "#A9A9A9", "📦"


def get_player_value(rating: int) -> tuple[int, int]:
    """Return (buy_value, sell_value) for a given rating."""
    if rating in BUY_SELL_VALUES:
        return BUY_SELL_VALUES[rating]
    # Fallback for ratings below 51
    return 200, 120


def get_random_player_by_rating(
    db: Session, min_rating: int, max_rating: int
) -> Optional[Player]:
    """Get a random active player within a rating range."""
    player = get_random_player_in_range(db, min_rating, max_rating)
    if player:
        logger.info(
            "Random player fetched: %s (rating=%d) in range [%d, %d]",
            player.name,
            player.rating,
            min_rating,
            max_rating,
        )
    else:
        logger.warning(
            "No player found in range [%d, %d]", min_rating, max_rating
        )
    return player


def get_random_player_by_rarity(db: Session) -> Optional[Player]:
    """Get a random player based on /claim rarity distribution."""
    weights = [tier["weight"] for tier in CLAIM_RARITY_DISTRIBUTION]
    chosen = random.choices(CLAIM_RARITY_DISTRIBUTION, weights=weights, k=1)[0]

    logger.info(
        "Rarity roll: %d-%d OVR (weight=%.1f%%)",
        chosen["min_rating"],
        chosen["max_rating"],
        chosen["weight"],
    )

    return get_random_player_by_rating(
        db, chosen["min_rating"], chosen["max_rating"]
    )


def get_player_stats(player: Player) -> dict:
    """Return a complete stats dictionary for a player."""
    tier_name, tier_color, tier_emoji = get_tier_info(player.rating)
    buy_value, sell_value = get_player_value(player.rating)

    return {
        "id": player.id,
        "name": player.name,
        "rating": player.rating,
        "category": player.category,
        "country": player.country or "Unknown",
        "bat_hand": player.bat_hand or "Right",
        "bowl_hand": player.bowl_hand or "Right",
        "bowl_style": player.bowl_style or "Medium Pacer",
        "bat_rating": player.bat_rating or player.rating,
        "bowl_rating": player.bowl_rating or player.rating,
        "bat_avg": player.bat_avg or 0.0,
        "strike_rate": player.strike_rate or 0.0,
        "runs": player.runs or 0,
        "centuries": player.centuries or 0,
        "bowl_avg": player.bowl_avg or 0.0,
        "economy": player.economy or 0.0,
        "wickets": player.wickets or 0,
        "image_url": player.image_url,
        "tier_name": tier_name,
        "tier_color": tier_color,
        "tier_emoji": tier_emoji,
        "buy_value": buy_value,
        "sell_value": sell_value,
    }
