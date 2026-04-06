"""Pydantic validation schemas for the Cricket Bot."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
# User Schemas
# ═══════════════════════════════════════════════════════════════

class UserCreate(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    total_coins: int
    total_gems: int
    roster_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════
# Player Schemas
# ═══════════════════════════════════════════════════════════════

class PlayerCreate(BaseModel):
    name: str
    rating: int = Field(ge=50, le=100)
    category: str
    country: Optional[str] = None
    bat_hand: Optional[str] = None
    bowl_hand: Optional[str] = None
    bowl_style: Optional[str] = None
    bat_rating: Optional[int] = None
    bowl_rating: Optional[int] = None
    bat_avg: Optional[float] = None
    strike_rate: Optional[float] = None
    runs: Optional[int] = None
    centuries: Optional[int] = None
    bowl_avg: Optional[float] = None
    economy: Optional[float] = None
    wickets: Optional[int] = None
    is_active: bool = True
    image_url: Optional[str] = None


class PlayerResponse(BaseModel):
    id: int
    name: str
    rating: int
    category: str
    country: Optional[str]
    bat_hand: Optional[str]
    bowl_hand: Optional[str]
    bowl_style: Optional[str]
    bat_rating: Optional[int]
    bowl_rating: Optional[int]
    bat_avg: Optional[float]
    strike_rate: Optional[float]
    runs: Optional[int]
    centuries: Optional[int]
    bowl_avg: Optional[float]
    economy: Optional[float]
    wickets: Optional[int]
    image_url: Optional[str]

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════
# UserRoster Schemas
# ═══════════════════════════════════════════════════════════════

class RosterEntryResponse(BaseModel):
    id: int
    player_id: int
    player_name: str
    player_rating: int
    player_category: str
    acquired_date: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════
# UserStats Schemas
# ═══════════════════════════════════════════════════════════════

class UserStatsResponse(BaseModel):
    user_id: int
    last_claim: Optional[datetime]
    last_daily: Optional[datetime]
    last_gspin: Optional[datetime]
    streak_count: int
    total_streaks_completed: int

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════
# Cooldown Schema
# ═══════════════════════════════════════════════════════════════

class CooldownStatus(BaseModel):
    ready: bool
    remaining_seconds: int = 0
