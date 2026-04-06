"""Telegram Mini App REST API for admin player management.

Provides JWT-based email/password authentication and CRUD endpoints
for players and admin users.  Served under ``/miniapp/api/``.
"""

import logging
import math
from datetime import datetime, timezone, timedelta
from functools import wraps

import bcrypt
import jwt
from flask import Blueprint, jsonify, request

from config.database import SessionLocal
from config.settings import MINIAPP_JWT_SECRET
from database.models import AdminUser, Player
from sqlalchemy import func

logger = logging.getLogger(__name__)

miniapp_api = Blueprint("miniapp_api", __name__, url_prefix="/miniapp/api")

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


# ── Helpers ────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _create_token(admin_user: AdminUser) -> str:
    payload = {
        "sub": admin_user.id,
        "email": admin_user.email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, MINIAPP_JWT_SECRET, algorithm=JWT_ALGORITHM)


def _get_db():
    return SessionLocal()


def auth_required(fn):
    """Decorator that validates the JWT Bearer token."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header[7:]
        try:
            payload = jwt.decode(token, MINIAPP_JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        db = _get_db()
        try:
            user = db.query(AdminUser).filter(AdminUser.id == payload["sub"]).first()
            if not user or not user.is_active:
                return jsonify({"error": "User not found or deactivated"}), 401
        finally:
            db.close()

        request.admin_user_id = payload["sub"]
        request.admin_email = payload["email"]
        return fn(*args, **kwargs)

    return wrapper


def _to_int(val, default=None):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _to_float(val, default=None):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ── Auth endpoints ─────────────────────────────────────────────

@miniapp_api.route("/auth/login", methods=["POST"])
def login():
    """Authenticate with email + password and return a JWT."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    db = _get_db()
    try:
        admin = db.query(AdminUser).filter(
            func.lower(AdminUser.email) == email
        ).first()
        if not admin or not admin.is_active:
            return jsonify({"error": "Invalid credentials"}), 401
        if not _check_password(password, admin.password_hash):
            return jsonify({"error": "Invalid credentials"}), 401

        token = _create_token(admin)
        return jsonify({
            "token": token,
            "user": {
                "id": admin.id,
                "email": admin.email,
                "display_name": admin.display_name,
            },
        })
    finally:
        db.close()


@miniapp_api.route("/auth/me", methods=["GET"])
@auth_required
def auth_me():
    """Return the current admin user info."""
    db = _get_db()
    try:
        admin = db.query(AdminUser).filter(AdminUser.id == request.admin_user_id).first()
        return jsonify({
            "id": admin.id,
            "email": admin.email,
            "display_name": admin.display_name,
        })
    finally:
        db.close()


# ── Admin user management ──────────────────────────────────────

@miniapp_api.route("/admins", methods=["GET"])
@auth_required
def list_admins():
    """List all admin users."""
    db = _get_db()
    try:
        admins = db.query(AdminUser).order_by(AdminUser.id).all()
        return jsonify([
            {
                "id": a.id,
                "email": a.email,
                "display_name": a.display_name,
                "is_active": a.is_active,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in admins
        ])
    finally:
        db.close()


@miniapp_api.route("/admins", methods=["POST"])
@auth_required
def create_admin():
    """Create a new admin user."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    display_name = (data.get("display_name") or "").strip() or None

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    db = _get_db()
    try:
        existing = db.query(AdminUser).filter(
            func.lower(AdminUser.email) == email
        ).first()
        if existing:
            return jsonify({"error": "An admin with this email already exists"}), 409

        admin = AdminUser(
            email=email,
            password_hash=_hash_password(password),
            display_name=display_name,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        return jsonify({
            "id": admin.id,
            "email": admin.email,
            "display_name": admin.display_name,
            "is_active": admin.is_active,
        }), 201
    finally:
        db.close()


@miniapp_api.route("/admins/<int:admin_id>", methods=["DELETE"])
@auth_required
def delete_admin(admin_id):
    """Delete (deactivate) an admin user.  Cannot delete yourself."""
    if admin_id == request.admin_user_id:
        return jsonify({"error": "Cannot delete yourself"}), 400

    db = _get_db()
    try:
        admin = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
        if not admin:
            return jsonify({"error": "Admin not found"}), 404
        db.delete(admin)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


# ── Player CRUD ────────────────────────────────────────────────

VALID_CATEGORIES = {"Batsman", "Bowler", "All-rounder", "Wicket Keeper"}


def _player_to_dict(p: Player) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "version": p.version,
        "rating": p.rating,
        "category": p.category,
        "country": p.country,
        "bat_hand": p.bat_hand,
        "bowl_hand": p.bowl_hand,
        "bowl_style": p.bowl_style,
        "bat_rating": p.bat_rating,
        "bowl_rating": p.bowl_rating,
        "bat_avg": p.bat_avg,
        "strike_rate": p.strike_rate,
        "runs": p.runs,
        "centuries": p.centuries,
        "bowl_avg": p.bowl_avg,
        "economy": p.economy,
        "wickets": p.wickets,
        "is_active": p.is_active,
        "image_url": p.image_url,
    }


@miniapp_api.route("/players", methods=["GET"])
@auth_required
def list_players():
    """List players with search, filter, and pagination."""
    page = max(1, _to_int(request.args.get("page"), 1))
    per_page = max(1, min(100, _to_int(request.args.get("per_page"), 25)))
    search = (request.args.get("search") or "").strip()
    category = (request.args.get("category") or "").strip()
    country = (request.args.get("country") or "").strip()

    db = _get_db()
    try:
        query = db.query(Player)
        if search:
            query = query.filter(func.lower(Player.name).contains(search.lower()))
        if category:
            query = query.filter(Player.category == category)
        if country:
            query = query.filter(func.lower(Player.country).contains(country.lower()))

        total = query.count()
        total_pages = max(1, math.ceil(total / per_page))
        page = min(page, total_pages)

        players = (
            query.order_by(Player.rating.desc(), Player.name)
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return jsonify({
            "players": [_player_to_dict(p) for p in players],
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        })
    finally:
        db.close()


@miniapp_api.route("/players/<int:player_id>", methods=["GET"])
@auth_required
def get_player(player_id):
    """Get a single player."""
    db = _get_db()
    try:
        p = db.query(Player).filter(Player.id == player_id).first()
        if not p:
            return jsonify({"error": "Player not found"}), 404
        return jsonify(_player_to_dict(p))
    finally:
        db.close()


@miniapp_api.route("/players", methods=["POST"])
@auth_required
def create_player():
    """Create a new player."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    rating = _to_int(data.get("rating"))
    category = (data.get("category") or "").strip()

    if not name:
        return jsonify({"error": "Name is required"}), 400
    if rating is None or not (50 <= rating <= 100):
        return jsonify({"error": "Rating must be 50–100"}), 400
    if category not in VALID_CATEGORIES:
        return jsonify({"error": f"Category must be one of: {', '.join(sorted(VALID_CATEGORIES))}"}), 400

    db = _get_db()
    try:
        dup = db.query(Player).filter(func.lower(Player.name) == name.lower()).first()
        if dup:
            return jsonify({"error": f"Player '{dup.name}' already exists"}), 409

        player = Player(
            name=name,
            version=(data.get("version") or "Base").strip() or "Base",
            rating=rating,
            category=category,
            country=(data.get("country") or "").strip() or None,
            bat_hand=(data.get("bat_hand") or "").strip() or None,
            bowl_hand=(data.get("bowl_hand") or "").strip() or None,
            bowl_style=(data.get("bowl_style") or "").strip() or None,
            bat_rating=_to_int(data.get("bat_rating")),
            bowl_rating=_to_int(data.get("bowl_rating")),
            bat_avg=_to_float(data.get("bat_avg")),
            strike_rate=_to_float(data.get("strike_rate")),
            runs=_to_int(data.get("runs")),
            centuries=_to_int(data.get("centuries")),
            bowl_avg=_to_float(data.get("bowl_avg")),
            economy=_to_float(data.get("economy")),
            wickets=_to_int(data.get("wickets")),
            is_active=data.get("is_active", True),
            image_url=(data.get("image_url") or "").strip() or None,
        )
        db.add(player)
        db.commit()
        db.refresh(player)
        return jsonify(_player_to_dict(player)), 201
    finally:
        db.close()


@miniapp_api.route("/players/<int:player_id>", methods=["PUT"])
@auth_required
def update_player(player_id):
    """Update an existing player."""
    data = request.get_json(silent=True) or {}

    db = _get_db()
    try:
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            return jsonify({"error": "Player not found"}), 404

        name = (data.get("name") or "").strip()
        if name:
            dup = db.query(Player).filter(
                func.lower(Player.name) == name.lower(),
                Player.id != player_id,
            ).first()
            if dup:
                return jsonify({"error": f"Another player named '{dup.name}' exists"}), 409
            player.name = name

        if "version" in data:
            player.version = (data["version"] or "Base").strip() or "Base"
        if "rating" in data:
            r = _to_int(data["rating"])
            if r is not None and 50 <= r <= 100:
                player.rating = r
        if "category" in data and data["category"] in VALID_CATEGORIES:
            player.category = data["category"]
        if "country" in data:
            player.country = (data["country"] or "").strip() or None
        if "bat_hand" in data:
            player.bat_hand = (data["bat_hand"] or "").strip() or None
        if "bowl_hand" in data:
            player.bowl_hand = (data["bowl_hand"] or "").strip() or None
        if "bowl_style" in data:
            player.bowl_style = (data["bowl_style"] or "").strip() or None
        if "bat_rating" in data:
            player.bat_rating = _to_int(data["bat_rating"])
        if "bowl_rating" in data:
            player.bowl_rating = _to_int(data["bowl_rating"])
        if "bat_avg" in data:
            player.bat_avg = _to_float(data["bat_avg"])
        if "strike_rate" in data:
            player.strike_rate = _to_float(data["strike_rate"])
        if "runs" in data:
            player.runs = _to_int(data["runs"])
        if "centuries" in data:
            player.centuries = _to_int(data["centuries"])
        if "bowl_avg" in data:
            player.bowl_avg = _to_float(data["bowl_avg"])
        if "economy" in data:
            player.economy = _to_float(data["economy"])
        if "wickets" in data:
            player.wickets = _to_int(data["wickets"])
        if "is_active" in data:
            player.is_active = bool(data["is_active"])
        if "image_url" in data:
            player.image_url = (data["image_url"] or "").strip() or None

        db.commit()
        db.refresh(player)
        return jsonify(_player_to_dict(player))
    finally:
        db.close()


@miniapp_api.route("/players/<int:player_id>", methods=["DELETE"])
@auth_required
def delete_player(player_id):
    """Delete a player."""
    db = _get_db()
    try:
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            return jsonify({"error": "Player not found"}), 404
        db.delete(player)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


@miniapp_api.route("/stats", methods=["GET"])
@auth_required
def stats():
    """Dashboard statistics."""
    from database.models import User, UserRoster

    db = _get_db()
    try:
        total_players = db.query(func.count(Player.id)).scalar() or 0
        active_players = db.query(func.count(Player.id)).filter(Player.is_active.is_(True)).scalar() or 0
        total_users = db.query(func.count(User.id)).scalar() or 0
        total_roster = db.query(func.count(UserRoster.id)).scalar() or 0

        categories = (
            db.query(Player.category, func.count(Player.id))
            .filter(Player.is_active.is_(True))
            .group_by(Player.category)
            .all()
        )

        return jsonify({
            "total_players": total_players,
            "active_players": active_players,
            "inactive_players": total_players - active_players,
            "total_users": total_users,
            "total_roster_entries": total_roster,
            "categories": {cat: cnt for cat, cnt in categories},
        })
    finally:
        db.close()
