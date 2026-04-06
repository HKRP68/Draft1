"""Admin panel routes for Player CRUD operations."""

import logging
import math

from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import func

from config.database import SessionLocal
from config.settings import ADMIN_PASSWORD, ADMIN_USERNAME
from database.models import Player
from services.sheets_service import (
    export_players_to_sheet,
    import_players_from_sheet,
    is_configured as sheets_configured,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ITEMS_PER_PAGE = 25

CATEGORIES = ["Batsman", "Bowler", "All-rounder", "Wicket Keeper"]
HAND_CHOICES = ["Right", "Left"]
BOWL_STYLES = ["Fast", "Off Spinner", "Leg Spinner", "Medium Pacer"]


# ── Authentication ─────────────────────────────────────────────

def _check_auth(username: str, password: str) -> bool:
    """Verify admin credentials."""
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


def _authenticate():
    """Send a 401 response that triggers the browser login dialog."""
    return Response(
        "Login required to access the admin panel.",
        401,
        {"WWW-Authenticate": 'Basic realm="Cricket Bot Admin"'},
    )


@admin_bp.before_request
def _before_request():
    """Apply authentication to every admin request."""
    if ADMIN_PASSWORD:
        auth = request.authorization
        if not auth or not _check_auth(auth.username, auth.password):
            return _authenticate()


def _get_db():
    """Return a new database session."""
    return SessionLocal()


@admin_bp.route("/")
def index():
    """Dashboard – redirect to player list."""
    return redirect(url_for("admin.player_list"))


@admin_bp.route("/players")
def player_list():
    """List players with search, filter, and pagination."""
    db = _get_db()
    try:
        page = request.args.get("page", 1, type=int)
        search = request.args.get("search", "", type=str).strip()
        category = request.args.get("category", "", type=str).strip()
        country = request.args.get("country", "", type=str).strip()

        query = db.query(Player)

        if search:
            query = query.filter(func.lower(Player.name).contains(search.lower()))
        if category:
            query = query.filter(Player.category == category)
        if country:
            query = query.filter(func.lower(Player.country).contains(country.lower()))

        total = query.count()
        total_pages = max(1, math.ceil(total / ITEMS_PER_PAGE))
        page = max(1, min(page, total_pages))

        players = (
            query.order_by(Player.rating.desc(), Player.name)
            .offset((page - 1) * ITEMS_PER_PAGE)
            .limit(ITEMS_PER_PAGE)
            .all()
        )

        countries = [
            r[0]
            for r in db.query(Player.country).distinct().order_by(Player.country).all()
            if r[0]
        ]

        return render_template(
            "player_list.html",
            players=players,
            page=page,
            total_pages=total_pages,
            total=total,
            search=search,
            category=category,
            country=country,
            categories=CATEGORIES,
            countries=countries,
        )
    finally:
        db.close()


@admin_bp.route("/players/create", methods=["GET", "POST"])
def player_create():
    """Create a new player."""
    if request.method == "POST":
        db = _get_db()
        try:
            data = _parse_player_form(request.form)

            existing = (
                db.query(Player)
                .filter(func.lower(Player.name) == data["name"].lower())
                .first()
            )
            if existing:
                flash(f"A player named '{data['name']}' already exists.", "danger")
                return render_template(
                    "player_form.html",
                    action="Create",
                    player=data,
                    categories=CATEGORIES,
                    hand_choices=HAND_CHOICES,
                    bowl_styles=BOWL_STYLES,
                )

            player = Player(**data)
            db.add(player)
            db.commit()
            flash(f"Player '{player.name}' created successfully!", "success")
            return redirect(url_for("admin.player_view", player_id=player.id))
        finally:
            db.close()

    return render_template(
        "player_form.html",
        action="Create",
        player={},
        categories=CATEGORIES,
        hand_choices=HAND_CHOICES,
        bowl_styles=BOWL_STYLES,
    )


@admin_bp.route("/players/<int:player_id>")
def player_view(player_id):
    """View a single player."""
    db = _get_db()
    try:
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            abort(404)
        return render_template("player_view.html", player=player)
    finally:
        db.close()


@admin_bp.route("/players/<int:player_id>/edit", methods=["GET", "POST"])
def player_edit(player_id):
    """Edit an existing player."""
    db = _get_db()
    try:
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            abort(404)

        if request.method == "POST":
            data = _parse_player_form(request.form)

            # Check uniqueness (excluding self)
            duplicate = (
                db.query(Player)
                .filter(
                    func.lower(Player.name) == data["name"].lower(),
                    Player.id != player_id,
                )
                .first()
            )
            if duplicate:
                flash(f"Another player named '{data['name']}' already exists.", "danger")
                return render_template(
                    "player_form.html",
                    action="Edit",
                    player=data,
                    player_id=player_id,
                    categories=CATEGORIES,
                    hand_choices=HAND_CHOICES,
                    bowl_styles=BOWL_STYLES,
                )

            for key, value in data.items():
                setattr(player, key, value)
            db.commit()
            flash(f"Player '{player.name}' updated successfully!", "success")
            return redirect(url_for("admin.player_view", player_id=player.id))

        # GET – populate form with current values
        player_data = {
            "name": player.name,
            "version": player.version,
            "rating": player.rating,
            "category": player.category,
            "country": player.country,
            "bat_hand": player.bat_hand,
            "bowl_hand": player.bowl_hand,
            "bowl_style": player.bowl_style,
            "bat_rating": player.bat_rating,
            "bowl_rating": player.bowl_rating,
            "bat_avg": player.bat_avg,
            "strike_rate": player.strike_rate,
            "runs": player.runs,
            "centuries": player.centuries,
            "bowl_avg": player.bowl_avg,
            "economy": player.economy,
            "wickets": player.wickets,
            "is_active": player.is_active,
            "image_url": player.image_url,
        }
        return render_template(
            "player_form.html",
            action="Edit",
            player=player_data,
            player_id=player_id,
            categories=CATEGORIES,
            hand_choices=HAND_CHOICES,
            bowl_styles=BOWL_STYLES,
        )
    finally:
        db.close()


@admin_bp.route("/players/<int:player_id>/delete", methods=["POST"])
def player_delete(player_id):
    """Delete a player."""
    db = _get_db()
    try:
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            abort(404)
        name = player.name
        db.delete(player)
        db.commit()
        flash(f"Player '{name}' deleted successfully!", "success")
        return redirect(url_for("admin.player_list"))
    finally:
        db.close()


def _parse_player_form(form) -> dict:
    """Extract and validate player fields from a form submission."""
    data = {
        "name": form.get("name", "").strip(),
        "version": form.get("version", "Base").strip() or "Base",
        "rating": int(form.get("rating", 50)),
        "category": form.get("category", "Batsman"),
        "country": form.get("country", "").strip() or None,
        "bat_hand": form.get("bat_hand", "").strip() or None,
        "bowl_hand": form.get("bowl_hand", "").strip() or None,
        "bowl_style": form.get("bowl_style", "").strip() or None,
        "bat_rating": _to_int_or_none(form.get("bat_rating")),
        "bowl_rating": _to_int_or_none(form.get("bowl_rating")),
        "bat_avg": _to_float_or_none(form.get("bat_avg")),
        "strike_rate": _to_float_or_none(form.get("strike_rate")),
        "runs": _to_int_or_none(form.get("runs")),
        "centuries": _to_int_or_none(form.get("centuries")),
        "bowl_avg": _to_float_or_none(form.get("bowl_avg")),
        "economy": _to_float_or_none(form.get("economy")),
        "wickets": _to_int_or_none(form.get("wickets")),
        "is_active": form.get("is_active") == "on",
        "image_url": form.get("image_url", "").strip() or None,
    }
    # Clamp rating
    data["rating"] = max(50, min(100, data["rating"]))
    return data


def _to_int_or_none(value):
    """Convert a string to int, or return None if empty/invalid."""
    if not value or not value.strip():
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _to_float_or_none(value):
    """Convert a string to float, or return None if empty/invalid."""
    if not value or not value.strip():
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# ── Google Sheets sync ─────────────────────────────────────────

@admin_bp.route("/sheets")
def sheets_sync():
    """Google Sheets sync page."""
    configured = sheets_configured()
    return render_template("sheets_sync.html", configured=configured)


@admin_bp.route("/sheets/export", methods=["POST"])
def sheets_export():
    """Export all players from DB → Google Sheet."""
    if not sheets_configured():
        flash("Google Sheets is not configured. Set the required env vars.", "danger")
        return redirect(url_for("admin.sheets_sync"))

    db = _get_db()
    try:
        count = export_players_to_sheet(db)
        flash(f"Successfully exported {count} players to Google Sheets!", "success")
    except Exception as exc:
        logger.exception("Google Sheets export failed")
        flash(f"Export failed: {exc}", "danger")
    finally:
        db.close()
    return redirect(url_for("admin.sheets_sync"))


@admin_bp.route("/sheets/import", methods=["POST"])
def sheets_import():
    """Import / sync players from Google Sheet → DB."""
    if not sheets_configured():
        flash("Google Sheets is not configured. Set the required env vars.", "danger")
        return redirect(url_for("admin.sheets_sync"))

    db = _get_db()
    try:
        result = import_players_from_sheet(db)
        parts = []
        if result.created:
            parts.append(f"{result.created} created")
        if result.updated:
            parts.append(f"{result.updated} updated")
        if result.skipped:
            parts.append(f"{result.skipped} skipped")
        summary = ", ".join(parts) if parts else "No changes"
        flash(f"Import complete — {summary}.", "success")
        for err in result.errors[:20]:  # show first 20 warnings
            flash(err, "warning")
    except Exception as exc:
        logger.exception("Google Sheets import failed")
        flash(f"Import failed: {exc}", "danger")
    finally:
        db.close()
    return redirect(url_for("admin.sheets_sync"))
