"""Google Sheets integration for managing player data.

Allows exporting the Players table to a Google Sheet and importing
changes back into the database.  Uses a Google Cloud service-account
credential file for authentication.
"""

import logging
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy import func as sa_func

from config.settings import (
    GOOGLE_SHEETS_CREDENTIALS_FILE,
    GOOGLE_SHEETS_SPREADSHEET_ID,
    GOOGLE_SHEETS_WORKSHEET_NAME,
)
from database.models import Player

logger = logging.getLogger(__name__)

# Columns written to / expected in the Google Sheet.
SHEET_COLUMNS = [
    "id",
    "name",
    "version",
    "rating",
    "category",
    "country",
    "bat_hand",
    "bowl_hand",
    "bowl_style",
    "bat_rating",
    "bowl_rating",
    "bat_avg",
    "strike_rate",
    "runs",
    "centuries",
    "bowl_avg",
    "economy",
    "wickets",
    "is_active",
    "image_url",
]

DEFAULT_VERSION = "Base"
DEFAULT_CATEGORY = "Batsman"

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_client() -> gspread.Client:
    """Return an authorised gspread client using service-account credentials."""
    if not GOOGLE_SHEETS_CREDENTIALS_FILE:
        raise RuntimeError(
            "GOOGLE_SHEETS_CREDENTIALS_FILE is not set. "
            "Please provide the path to your service-account JSON key."
        )
    creds = Credentials.from_service_account_file(
        GOOGLE_SHEETS_CREDENTIALS_FILE, scopes=_SCOPES,
    )
    return gspread.authorize(creds)


def _get_worksheet() -> gspread.Worksheet:
    """Open the configured spreadsheet and return the target worksheet."""
    client = _get_client()
    spreadsheet_id = GOOGLE_SHEETS_SPREADSHEET_ID
    if not spreadsheet_id:
        raise RuntimeError(
            "GOOGLE_SHEETS_SPREADSHEET_ID is not set. "
            "Provide the spreadsheet ID or full URL."
        )
    # Accept either a full URL or plain spreadsheet ID.
    if "/" in spreadsheet_id:
        spreadsheet = client.open_by_url(spreadsheet_id)
    else:
        spreadsheet = client.open_by_key(spreadsheet_id)

    worksheet_name = GOOGLE_SHEETS_WORKSHEET_NAME or "Players"
    try:
        return spreadsheet.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        logger.info(
            "Worksheet '%s' not found – creating it.", worksheet_name,
        )
        return spreadsheet.add_worksheet(
            title=worksheet_name, rows=5000, cols=len(SHEET_COLUMNS),
        )


def is_configured() -> bool:
    """Return True when all required Google Sheets env vars are set."""
    return bool(GOOGLE_SHEETS_CREDENTIALS_FILE and GOOGLE_SHEETS_SPREADSHEET_ID)


# ── Export (DB → Sheet) ────────────────────────────────────────

def export_players_to_sheet(db_session) -> int:
    """Push every player from the database into the Google Sheet.

    The sheet is cleared first and then re-populated with a header row
    followed by one row per player.  Returns the number of rows written.
    """
    players = (
        db_session.query(Player)
        .order_by(Player.rating.desc(), Player.name)
        .all()
    )

    rows: list[list] = [SHEET_COLUMNS]  # header
    for p in players:
        rows.append([
            p.id,
            p.name or "",
            p.version or "",
            p.rating,
            p.category or "",
            p.country or "",
            p.bat_hand or "",
            p.bowl_hand or "",
            p.bowl_style or "",
            _val(p.bat_rating),
            _val(p.bowl_rating),
            _val(p.bat_avg),
            _val(p.strike_rate),
            _val(p.runs),
            _val(p.centuries),
            _val(p.bowl_avg),
            _val(p.economy),
            _val(p.wickets),
            "TRUE" if p.is_active else "FALSE",
            p.image_url or "",
        ])

    ws = _get_worksheet()
    ws.clear()
    ws.update(rows, "A1")
    logger.info("Exported %d players to Google Sheets.", len(players))
    return len(players)


# ── Import (Sheet → DB) ───────────────────────────────────────

class SheetImportResult:
    """Container for the outcome of an import operation."""

    def __init__(self):
        self.created: int = 0
        self.updated: int = 0
        self.skipped: int = 0
        self.errors: list[str] = []


def import_players_from_sheet(db_session) -> SheetImportResult:
    """Read rows from the Google Sheet and upsert them into the database.

    * Rows whose ``id`` column matches an existing player are **updated**.
    * Rows with an empty ``id`` (or ``id`` = 0) are treated as new and
      **created** (duplicate names are skipped with a warning).
    * The ``name`` and ``rating`` columns are required; rows missing
      either are skipped.
    """
    ws = _get_worksheet()
    all_rows = ws.get_all_records(expected_headers=SHEET_COLUMNS)

    result = SheetImportResult()

    for idx, row in enumerate(all_rows, start=2):  # row 1 = header
        try:
            name = str(row.get("name", "")).strip()
            rating_raw = row.get("rating", "")
            if not name:
                result.skipped += 1
                continue
            if rating_raw == "" or rating_raw is None:
                result.errors.append(f"Row {idx}: missing rating for '{name}'.")
                result.skipped += 1
                continue

            data = _row_to_dict(row)
            player_id = _to_int(row.get("id"))

            if player_id:
                # Update existing player
                player = db_session.query(Player).filter(Player.id == player_id).first()
                if not player:
                    result.errors.append(
                        f"Row {idx}: no player with id={player_id} ('{name}')."
                    )
                    result.skipped += 1
                    continue
                for key, value in data.items():
                    setattr(player, key, value)
                result.updated += 1
            else:
                # Create new player (skip if name already exists)
                existing = (
                    db_session.query(Player)
                    .filter(sa_func.lower(Player.name) == name.lower())
                    .first()
                )
                if existing:
                    result.errors.append(
                        f"Row {idx}: player '{name}' already exists (id={existing.id}). Skipped."
                    )
                    result.skipped += 1
                    continue
                player = Player(**data)
                db_session.add(player)
                result.created += 1

        except Exception as exc:
            result.errors.append(f"Row {idx}: {exc}")
            result.skipped += 1

    db_session.commit()
    logger.info(
        "Sheet import done – created=%d, updated=%d, skipped=%d, errors=%d",
        result.created, result.updated, result.skipped, len(result.errors),
    )
    return result


# ── Helpers ────────────────────────────────────────────────────

def _val(v):
    """Return the value or empty string (Google Sheets prefers '' over None)."""
    return v if v is not None else ""


def _to_int(v) -> Optional[int]:
    """Safely convert to int or return None."""
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _to_float(v) -> Optional[float]:
    """Safely convert to float or return None."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _row_to_dict(row: dict) -> dict:
    """Convert a Google Sheets row dict into a Player-compatible dict.

    The ``id`` field is intentionally excluded so SQLAlchemy can
    auto-generate it for new records.
    """
    is_active_raw = str(row.get("is_active", "TRUE")).strip().upper()
    is_active = is_active_raw not in ("FALSE", "0", "NO", "")

    raw_rating = int(row.get("rating", 50))
    if raw_rating < 50 or raw_rating > 100:
        logger.warning(
            "Rating %d for '%s' is outside 50-100; clamping.",
            raw_rating, row.get("name", ""),
        )

    return {
        "name": str(row.get("name", "")).strip(),
        "version": str(row.get("version", DEFAULT_VERSION)).strip() or DEFAULT_VERSION,
        "rating": max(50, min(100, raw_rating)),
        "category": str(row.get("category", DEFAULT_CATEGORY)).strip() or DEFAULT_CATEGORY,
        "country": str(row.get("country", "")).strip() or None,
        "bat_hand": str(row.get("bat_hand", "")).strip() or None,
        "bowl_hand": str(row.get("bowl_hand", "")).strip() or None,
        "bowl_style": str(row.get("bowl_style", "")).strip() or None,
        "bat_rating": _to_int(row.get("bat_rating")),
        "bowl_rating": _to_int(row.get("bowl_rating")),
        "bat_avg": _to_float(row.get("bat_avg")),
        "strike_rate": _to_float(row.get("strike_rate")),
        "runs": _to_int(row.get("runs")),
        "centuries": _to_int(row.get("centuries")),
        "bowl_avg": _to_float(row.get("bowl_avg")),
        "economy": _to_float(row.get("economy")),
        "wickets": _to_int(row.get("wickets")),
        "is_active": is_active,
        "image_url": str(row.get("image_url", "")).strip() or None,
    }
