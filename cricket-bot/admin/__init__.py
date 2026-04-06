"""Flask admin panel for managing cricket bot players."""

from flask import Flask

from config.settings import ADMIN_SECRET_KEY


def create_app() -> Flask:
    """Create and configure the Flask admin application."""
    app = Flask(__name__, template_folder="templates")
    app.secret_key = ADMIN_SECRET_KEY

    from admin.routes import admin_bp

    app.register_blueprint(admin_bp)
    return app
