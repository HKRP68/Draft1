"""Trading service – create, accept, reject, expire trades."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from config.constants import BUY_SELL_VALUES, TRADE_EXPIRES_SECONDS, TRADE_FEE_PERCENT
from database.crud import (
    add_player_to_roster,
    count_active_trades_for_user,
    create_trade,
    get_pending_trades_for_user,
    get_roster_entry_by_id,
    get_trade_by_id,
    get_user_roster,
    remove_roster_entry,
    update_trade_status,
    update_user_coins,
)
from database.models import Trade, User, UserRoster
from services.rating_matcher_service import can_trade_with_user

logger = logging.getLogger(__name__)


def _trade_fee(rating: int) -> int:
    """5 % of buy value for the given rating."""
    bv = BUY_SELL_VALUES.get(rating, (200, 120))[0]
    return max(1, int(bv * TRADE_FEE_PERCENT / 100))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_first_roster_entry(db: Session, user: User, player_id: int) -> Optional[UserRoster]:
    """Return the first roster entry for a player owned by the user."""
    entries = get_user_roster(db, user)
    for e in entries:
        if e.player_id == player_id:
            return e
    return None


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

def initiate_trade(
    db: Session,
    initiator: User,
    receiver: User,
    initiator_player_id: int,
    receiver_player_id: int,
) -> dict:
    """
    Create a pending trade between initiator and receiver.
    Returns {success, trade_id, message} or {success:False, error}.
    """
    # Load players and ratings
    initiator_entry = _get_first_roster_entry(db, initiator, initiator_player_id)
    if not initiator_entry:
        return {"success": False, "error": "You don't own this player"}

    receiver_entry = _get_first_roster_entry(db, receiver, receiver_player_id)
    if not receiver_entry:
        return {"success": False, "error": "Target user doesn't own that player"}

    initiator_player = initiator_entry.player
    receiver_player = receiver_entry.player

    if initiator_player.rating != receiver_player.rating:
        return {"success": False, "error": "Players must be the same rating to trade"}

    rating = initiator_player.rating

    # Validate rules
    check = can_trade_with_user(db, initiator, receiver, rating)
    if not check["can_trade"]:
        return {"success": False, "error": check["reason"]}

    fee = _trade_fee(rating)
    expires_at = _now() + timedelta(seconds=TRADE_EXPIRES_SECONDS)

    trade = create_trade(
        db,
        initiator=initiator,
        receiver=receiver,
        initiator_player_id=initiator_player.id,
        receiver_player_id=receiver_player.id,
        trade_fee=fee,
        expires_at=expires_at,
    )

    logger.info(
        "trading_service: trade initiated id=%d %s <-> %s",
        trade.id,
        initiator.telegram_id,
        receiver.telegram_id,
    )
    return {"success": True, "trade_id": trade.id, "trade": trade}


def expire_trade(db: Session, trade: Trade) -> dict:
    """Expire a trade if it is past its expiry time. Returns {expired: bool}."""
    if trade.status != "pending":
        return {"expired": False}
    if _now() >= trade.expires_at.replace(tzinfo=timezone.utc):
        update_trade_status(db, trade, "expired")
        logger.info("trading_service: trade id=%d expired", trade.id)
        return {"expired": True}
    return {"expired": False}


def _ensure_not_expired(db: Session, trade: Trade) -> bool:
    """Auto-expire if past expiry; return True if still valid."""
    if trade.status != "pending":
        return False
    result = expire_trade(db, trade)
    if result["expired"]:
        return False
    return True


def accept_trade(db: Session, trade_id: int, user: User) -> dict:
    """
    Accept a pending trade as the receiver.
    Swaps players in rosters and deducts fees from both parties.
    Returns {success, message} or {success:False, error}.
    """
    trade = get_trade_by_id(db, trade_id)
    if not trade:
        return {"success": False, "error": "Trade not found"}

    if trade.receiver_id != user.id:
        return {"success": False, "error": "This trade is not for you"}

    if not _ensure_not_expired(db, trade):
        if trade.status == "expired":
            return {"success": False, "error": "⏰ Trade offer has expired"}
        return {"success": False, "error": f"Trade is no longer pending (status: {trade.status})"}

    # Re-load users
    from database.crud import get_user_by_telegram_id
    from sqlalchemy.orm import Session as _S

    # Use ORM to reload
    from database.models import User as UserModel
    initiator = db.query(UserModel).filter(UserModel.id == trade.initiator_id).first()
    receiver = db.query(UserModel).filter(UserModel.id == trade.receiver_id).first()

    # Verify both still own the player
    initiator_entry = _get_first_roster_entry(db, initiator, trade.initiator_player_id)
    if not initiator_entry:
        update_trade_status(db, trade, "expired")
        return {"success": False, "error": "Trade failed: initiator no longer owns the offered player"}

    receiver_entry = _get_first_roster_entry(db, receiver, trade.receiver_player_id)
    if not receiver_entry:
        update_trade_status(db, trade, "expired")
        return {"success": False, "error": "Trade failed: you no longer own your player"}

    fee = trade.trade_fee

    # Verify both can afford fee
    if initiator.total_coins < fee:
        update_trade_status(db, trade, "expired")
        return {"success": False, "error": "Trade failed: initiator can no longer afford the trade fee"}
    if receiver.total_coins < fee:
        return {"success": False, "error": f"You need {fee:,} 🪙 for the trade fee but only have {receiver.total_coins:,} 🪙"}

    initiator_player = initiator_entry.player
    receiver_player = receiver_entry.player

    # Swap: remove each player from owner, add to other
    remove_roster_entry(db, initiator, initiator_entry)
    remove_roster_entry(db, receiver, receiver_entry)
    add_player_to_roster(db, initiator, receiver_player)
    add_player_to_roster(db, receiver, initiator_player)

    # Deduct fees
    update_user_coins(db, initiator, -fee)
    update_user_coins(db, receiver, -fee)

    # Mark complete
    update_trade_status(db, trade, "completed", completed_at=_now())

    logger.info(
        "trading_service: trade id=%d COMPLETED %s gave %s, received %s; fee=%d each",
        trade.id,
        initiator.telegram_id,
        initiator_player.name,
        receiver_player.name,
        fee,
    )

    return {
        "success": True,
        "initiator_gave": initiator_player,
        "receiver_gave": receiver_player,
        "fee": fee,
        "initiator_new_balance": initiator.total_coins,
        "receiver_new_balance": receiver.total_coins,
        "initiator": initiator,
        "receiver": receiver,
    }


def reject_trade(db: Session, trade_id: int, user: User) -> dict:
    """
    Reject a pending trade as receiver OR cancel it as initiator.
    Returns {success, cancelled_by}.
    """
    trade = get_trade_by_id(db, trade_id)
    if not trade:
        return {"success": False, "error": "Trade not found"}

    if trade.initiator_id != user.id and trade.receiver_id != user.id:
        return {"success": False, "error": "This trade is not related to you"}

    if trade.status != "pending":
        return {"success": False, "error": f"Trade is not pending (status: {trade.status})"}

    cancelled_by = "initiator" if trade.initiator_id == user.id else "receiver"
    new_status = "cancelled" if cancelled_by == "initiator" else "rejected"
    update_trade_status(db, trade, new_status)

    logger.info(
        "trading_service: trade id=%d %s by user=%s",
        trade.id,
        new_status,
        user.telegram_id,
    )
    return {"success": True, "cancelled_by": cancelled_by, "trade": trade}


def get_pending_trades(db: Session, user: User) -> list[Trade]:
    """Return non-expired pending trades for a user (auto-expire stale ones)."""
    trades = get_pending_trades_for_user(db, user)
    active = []
    for t in trades:
        if not _ensure_not_expired(db, t):
            continue
        active.append(t)
    return active


def get_trade_details(db: Session, trade_id: int) -> Optional[dict]:
    """Return enriched trade dict with time remaining and fees."""
    trade = get_trade_by_id(db, trade_id)
    if not trade:
        return None

    now = _now()
    expires = trade.expires_at.replace(tzinfo=timezone.utc)
    remaining = max(0, int((expires - now).total_seconds()))

    return {
        "trade": trade,
        "initiator": trade.initiator,
        "receiver": trade.receiver,
        "initiator_player": trade.initiator_player,
        "receiver_player": trade.receiver_player,
        "fee": trade.trade_fee,
        "remaining_seconds": remaining,
        "is_expired": remaining == 0 and trade.status == "pending",
    }


def validate_trade_rules(
    db: Session, initiator: User, receiver: User, rating: int
) -> dict:
    """
    Validate all trading rules at once.
    Returns {valid: bool, errors: list[str]}.
    """
    check = can_trade_with_user(db, initiator, receiver, rating)
    if not check["can_trade"]:
        return {"valid": False, "errors": [check["reason"]]}
    return {"valid": True, "errors": []}
