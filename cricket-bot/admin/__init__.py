"""Flask admin panel for managing cricket bot players."""

import logging

from flask import Flask

from config.database import SessionLocal
from config.settings import ADMIN_SECRET_KEY

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

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """Close the scoped database session at the end of each request."""
        SessionLocal.remove() if hasattr(SessionLocal, "remove") else None

    from admin.routes import admin_bp

    app.register_blueprint(admin_bp)
    return app
