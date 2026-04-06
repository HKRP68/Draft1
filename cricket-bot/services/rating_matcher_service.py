"""Rating-based matching logic for player trades."""

import logging
from collections import Counter

from sqlalchemy.orm import Session

from config.constants import BUY_SELL_VALUES, TRADE_ALLOWED_MIN_RATING, TRADE_FEE_PERCENT
from database.crud import count_active_trades_for_user, get_user_roster
from database.models import User, UserRoster

logger = logging.getLogger(__name__)


def _get_trade_fee(rating: int) -> int:
    """Calculate the 5 % trade fee based on buy value."""
    if rating in BUY_SELL_VALUES:
        buy_value = BUY_SELL_VALUES[rating][0]
    else:
        buy_value = 200
    return max(1, int(buy_value * TRADE_FEE_PERCENT / 100))


def find_same_rating_players_in_roster(
    db: Session, user: User, rating: int
) -> list[UserRoster]:
    """Return all roster entries for a user with the exact given rating."""
    entries = get_user_roster(db, user)
    return [e for e in entries if e.player.rating == rating]


def find_same_rating_players_for_user(
    db: Session, user: User, rating: int
) -> list[UserRoster]:
    """Alias – same as above, used to query a target user's matching players."""
    return find_same_rating_players_in_roster(db, user, rating)


def get_tradeable_ratings(db: Session, user: User) -> list[int]:
    """Return sorted list of unique ratings >= TRADE_ALLOWED_MIN_RATING in user's roster."""
    entries = get_user_roster(db, user)
    ratings = sorted(
        {e.player.rating for e in entries if e.player.rating >= TRADE_ALLOWED_MIN_RATING},
        reverse=True,
    )
    return ratings


def get_matching_tradeable_ratings(
    db: Session, initiator: User, receiver: User
) -> list[int]:
    """
    Return ratings that BOTH users own players at AND which are >= min trade rating.
    """
    i_ratings = set(get_tradeable_ratings(db, initiator))
    r_ratings = set(get_tradeable_ratings(db, receiver))
    return sorted(i_ratings & r_ratings, reverse=True)


def can_trade_with_user(
    db: Session,
    initiator: User,
    receiver: User,
    rating: int,
) -> dict:
    """
    Validate whether a trade of a specific rating between two users is permissible.
    Returns {can_trade: bool, reason: str}.
    """
    if initiator.id == receiver.id:
        return {"can_trade": False, "reason": "You cannot trade with yourself"}

    if rating < TRADE_ALLOWED_MIN_RATING:
        return {
            "can_trade": False,
            "reason": f"Only players rated {TRADE_ALLOWED_MIN_RATING}+ OVR can be traded",
        }

    i_entries = find_same_rating_players_in_roster(db, initiator, rating)
    if not i_entries:
        return {
            "can_trade": False,
            "reason": f"You have no {rating} OVR players to trade",
        }

    r_entries = find_same_rating_players_in_roster(db, receiver, rating)
    if not r_entries:
        return {
            "can_trade": False,
            "reason": f"@{receiver.username or receiver.telegram_id} has no {rating} OVR players",
        }

    if count_active_trades_for_user(db, initiator) >= 1:
        return {
            "can_trade": False,
            "reason": "You already have a pending trade. Wait or cancel it first",
        }

    if count_active_trades_for_user(db, receiver) >= 1:
        return {
            "can_trade": False,
            "reason": f"@{receiver.username or receiver.telegram_id} already has a pending trade",
        }

    fee = _get_trade_fee(rating)
    if initiator.total_coins < fee:
        return {
            "can_trade": False,
            "reason": f"You need {fee:,} 🪙 for the trade fee but only have {initiator.total_coins:,} 🪙",
        }
    if receiver.total_coins < fee:
        return {
            "can_trade": False,
            "reason": f"@{receiver.username or receiver.telegram_id} cannot afford the {fee:,} 🪙 trade fee",
        }

    return {"can_trade": True, "reason": ""}
