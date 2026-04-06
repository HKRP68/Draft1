"""SQLAlchemy ORM models for the Cricket Bot."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from config.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    total_coins = Column(Integer, default=0)
    total_gems = Column(Integer, default=0)
    roster_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    roster = relationship("UserRoster", back_populates="user", cascade="all, delete-orphan")
    stats = relationship("UserStats", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username={self.username})>"


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    rating = Column(Integer, nullable=False, index=True)
    category = Column(String(50), nullable=False)  # Batsman/Bowler/All-rounder/Wicket Keeper
    country = Column(String(100), nullable=True)
    bat_hand = Column(String(10), nullable=True)  # Right/Left
    bowl_hand = Column(String(10), nullable=True)  # Right/Left
    bowl_style = Column(String(50), nullable=True)  # Fast/Off Spinner/Leg Spinner/Medium Pacer
    bat_rating = Column(Integer, nullable=True)
    bowl_rating = Column(Integer, nullable=True)
    bat_avg = Column(Float, nullable=True)
    strike_rate = Column(Float, nullable=True)
    runs = Column(Integer, nullable=True)
    centuries = Column(Integer, nullable=True)
    bowl_avg = Column(Float, nullable=True)
    economy = Column(Float, nullable=True)
    wickets = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    image_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    rosters = relationship("UserRoster", back_populates="player")

    def __repr__(self):
        return f"<Player(name={self.name}, rating={self.rating})>"


class UserRoster(Base):
    __tablename__ = "user_roster"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    acquired_date = Column(DateTime, default=utcnow)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="roster")
    player = relationship("Player", back_populates="rosters")

    def __repr__(self):
        return f"<UserRoster(user_id={self.user_id}, player_id={self.player_id})>"


class UserStats(Base):
    __tablename__ = "user_stats"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    last_claim = Column(DateTime, nullable=True)
    last_daily = Column(DateTime, nullable=True)
    last_gspin = Column(DateTime, nullable=True)
    streak_count = Column(Integer, default=0)
    total_streaks_completed = Column(Integer, default=0)
    last_streak_reset = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="stats")

    def __repr__(self):
        return f"<UserStats(user_id={self.user_id}, streak={self.streak_count})>"
