"""CRUD operations for the Cricket Bot database."""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database.models import Player, Trade, User, UserRoster, UserStats

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# User CRUD
# ═══════════════════════════════════════════════════════════════

def get_user_by_telegram_id(db: Session, telegram_id: int) -> Optional[User]:
    """Get a user by their Telegram ID."""
    return db.query(User).filter(User.telegram_id == telegram_id).first()


def create_user(
    db: Session,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    coins: int = 0,
    gems: int = 0,
) -> User:
    """Create a new user."""
    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        total_coins=coins,
        total_gems=gems,
        roster_count=0,
    )
    db.add(user)
    db.flush()
    logger.info("Created user: telegram_id=%s, username=%s", telegram_id, username)

    # Create user stats
    stats = UserStats(user_id=user.id)
    db.add(stats)
    db.commit()
    db.refresh(user)
    return user


def update_user_coins(db: Session, user: User, amount: int) -> User:
    """Add (or subtract) coins from a user."""
    user.total_coins += amount
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    logger.info("Updated coins for user %s: %+d (total: %d)", user.telegram_id, amount, user.total_coins)
    return user


def update_user_gems(db: Session, user: User, amount: int) -> User:
    """Add (or subtract) gems from a user."""
    user.total_gems += amount
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    logger.info("Updated gems for user %s: %+d (total: %d)", user.telegram_id, amount, user.total_gems)
    return user


# ═══════════════════════════════════════════════════════════════
# Player CRUD
# ═══════════════════════════════════════════════════════════════

def get_player_by_id(db: Session, player_id: int) -> Optional[Player]:
    """Get a player by their ID."""
    return db.query(Player).filter(Player.id == player_id).first()


def get_player_by_name(db: Session, name: str) -> Optional[Player]:
    """Get a player by their name (case-insensitive)."""
    return db.query(Player).filter(func.lower(Player.name) == func.lower(name)).first()


def search_players_by_name(db: Session, name: str, limit: int = 10) -> list[Player]:
    """Search players by partial name match (case-insensitive)."""
    return (
        db.query(Player)
        .filter(func.lower(Player.name).contains(func.lower(name)))
        .limit(limit)
        .all()
    )


def get_random_player_in_range(db: Session, min_rating: int, max_rating: int) -> Optional[Player]:
    """Get a random active player within a rating range."""
    return (
        db.query(Player)
        .filter(
            Player.rating >= min_rating,
            Player.rating <= max_rating,
            Player.is_active == True,  # noqa: E712
        )
        .order_by(func.random())
        .first()
    )


def get_player_count(db: Session) -> int:
    """Get total number of players in the database."""
    return db.query(func.count(Player.id)).scalar()


def bulk_create_players(db: Session, players_data: list[dict]) -> int:
    """Bulk insert players into the database. Returns count of inserted players."""
    count = 0
    for data in players_data:
        existing = db.query(Player).filter(Player.name == data["name"]).first()
        if existing:
            continue
        player = Player(**data)
        db.add(player)
        count += 1
    db.commit()
    logger.info("Bulk created %d players", count)
    return count


# ═══════════════════════════════════════════════════════════════
# UserRoster CRUD
# ═══════════════════════════════════════════════════════════════

def add_player_to_roster(db: Session, user: User, player: Player) -> UserRoster:
    """Add a player to the user's roster."""
    entry = UserRoster(user_id=user.id, player_id=player.id)
    db.add(entry)
    user.roster_count += 1
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entry)
    logger.info(
        "Added player %s (id=%d) to roster of user %s",
        player.name,
        player.id,
        user.telegram_id,
    )
    return entry


def get_user_roster(db: Session, user: User) -> list[UserRoster]:
    """Get all roster entries for a user, most recent first."""
    return (
        db.query(UserRoster)
        .filter(UserRoster.user_id == user.id)
        .order_by(UserRoster.acquired_date.desc())
        .all()
    )


def is_player_in_roster(db: Session, user: User, player: Player) -> bool:
    """Check if a specific player is in the user's roster."""
    return (
        db.query(UserRoster)
        .filter(UserRoster.user_id == user.id, UserRoster.player_id == player.id)
        .first()
        is not None
    )


# ═══════════════════════════════════════════════════════════════
# UserStats CRUD
# ═══════════════════════════════════════════════════════════════

def get_user_stats(db: Session, user: User) -> Optional[UserStats]:
    """Get user stats."""
    return db.query(UserStats).filter(UserStats.user_id == user.id).first()


def update_last_claim(db: Session, stats: UserStats) -> None:
    """Update the last claim timestamp."""
    stats.last_claim = datetime.now(timezone.utc)
    db.commit()
    logger.info("Updated last_claim for user_id=%d", stats.user_id)


def update_last_daily(db: Session, stats: UserStats) -> None:
    """Update the last daily timestamp."""
    stats.last_daily = datetime.now(timezone.utc)
    db.commit()
    logger.info("Updated last_daily for user_id=%d", stats.user_id)


def update_last_gspin(db: Session, stats: UserStats) -> None:
    """Update the last gspin timestamp."""
    stats.last_gspin = datetime.now(timezone.utc)
    db.commit()
    logger.info("Updated last_gspin for user_id=%d", stats.user_id)


def update_streak(db: Session, stats: UserStats, new_count: int) -> None:
    """Update the streak count."""
    stats.streak_count = new_count
    db.commit()
    logger.info("Updated streak for user_id=%d to %d", stats.user_id, new_count)


def reset_streak(db: Session, stats: UserStats) -> None:
    """Reset the streak count to 0."""
    stats.streak_count = 0
    stats.last_streak_reset = datetime.now(timezone.utc)
    db.commit()
    logger.info("Reset streak for user_id=%d", stats.user_id)


def increment_streaks_completed(db: Session, stats: UserStats) -> None:
    """Increment total streaks completed."""
    stats.total_streaks_completed += 1
    db.commit()


# ═══════════════════════════════════════════════════════════════
# UserRoster extended queries
# ═══════════════════════════════════════════════════════════════

def get_roster_entries_by_rating(db: Session, user: User, rating: int) -> list[UserRoster]:
    """Get all roster entries for a user matching a specific rating."""
    from database.models import Player  # avoid circular at module level
    return (
        db.query(UserRoster)
        .join(Player, UserRoster.player_id == Player.id)
        .filter(UserRoster.user_id == user.id, Player.rating == rating)
        .all()
    )


def get_roster_entry_by_id(db: Session, entry_id: int) -> Optional[UserRoster]:
    """Get a single UserRoster entry by its primary key."""
    return db.query(UserRoster).filter(UserRoster.id == entry_id).first()


def remove_roster_entry(db: Session, user: User, entry: UserRoster) -> None:
    """Remove a specific roster entry and decrement the user's roster count."""
    db.delete(entry)
    user.roster_count = max(0, user.roster_count - 1)
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(
        "Removed roster entry id=%d (player_id=%d) from user %s",
        entry.id,
        entry.player_id,
        user.telegram_id,
    )


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Get a user by Telegram username (case-insensitive, without @)."""
    clean = username.lstrip("@").lower()
    return (
        db.query(User)
        .filter(func.lower(User.username) == clean)
        .first()
    )


# ═══════════════════════════════════════════════════════════════
# Trade CRUD
# ═══════════════════════════════════════════════════════════════

def create_trade(
    db: Session,
    initiator: User,
    receiver: User,
    initiator_player_id: int,
    receiver_player_id: int,
    trade_fee: int,
    expires_at: datetime,
) -> Trade:
    """Create a new pending trade."""
    trade = Trade(
        initiator_id=initiator.id,
        receiver_id=receiver.id,
        initiator_player_id=initiator_player_id,
        receiver_player_id=receiver_player_id,
        status="pending",
        trade_fee=trade_fee,
        expires_at=expires_at,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    logger.info(
        "Trade created id=%d initiator=%s receiver=%s",
        trade.id,
        initiator.telegram_id,
        receiver.telegram_id,
    )
    return trade


def get_trade_by_id(db: Session, trade_id: int) -> Optional[Trade]:
    """Get a trade by its ID."""
    return db.query(Trade).filter(Trade.id == trade_id).first()


def get_pending_trades_for_user(db: Session, user: User) -> list[Trade]:
    """Get all pending trades involving a user."""
    return (
        db.query(Trade)
        .filter(
            or_(Trade.initiator_id == user.id, Trade.receiver_id == user.id),
            Trade.status == "pending",
        )
        .all()
    )


def count_active_trades_for_user(db: Session, user: User) -> int:
    """Count pending trades where user is initiator or receiver."""
    return (
        db.query(func.count(Trade.id))
        .filter(
            or_(Trade.initiator_id == user.id, Trade.receiver_id == user.id),
            Trade.status == "pending",
        )
        .scalar()
        or 0
    )


def update_trade_status(
    db: Session,
    trade: Trade,
    status: str,
    completed_at: Optional[datetime] = None,
) -> Trade:
    """Update trade status."""
    trade.status = status
    trade.updated_at = datetime.now(timezone.utc)
    if completed_at is not None:
        trade.completed_at = completed_at
    db.commit()
    db.refresh(trade)
    logger.info("Trade id=%d status updated to %s", trade.id, status)
    return trade
