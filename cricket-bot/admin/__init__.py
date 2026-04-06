"""Flask admin panel for managing cricket bot players."""

import logging

from flask import Flask, render_template

from config.database import SessionLocal
from config.settings import ADMIN_PASSWORD, ADMIN_SECRET_KEY

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask admin application."""
    app = Flask(__name__, template_folder="templates")
    app.secret_key = ADMIN_SECRET_KEY

    if ADMIN_SECRET_KEY == "change-me-in-production":
        logger.warning(
            "ADMIN_SECRET_KEY is using the default value. "
            "Set a strong random value via the ADMIN_SECRET_KEY env var."
        )

    if not ADMIN_PASSWORD:
        logger.warning(
            "ADMIN_PASSWORD is not set – admin panel has no authentication. "
            "Set ADMIN_PASSWORD env var to enable HTTP Basic Auth."
        )

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """Close the scoped database session at the end of each request."""
        if hasattr(SessionLocal, "remove"):
            SessionLocal.remove()

    # ── Blueprints ──────────────────────────────────────────────
    from admin.routes import admin_bp
    from admin.miniapp_api import miniapp_api

    app.register_blueprint(admin_bp)
    app.register_blueprint(miniapp_api)

    # ── Mini App HTML endpoint ──────────────────────────────────
    @app.route("/miniapp")
    def miniapp_page():
        """Serve the Telegram Mini App single-page admin panel."""
        return render_template("miniapp.html")

    return app
