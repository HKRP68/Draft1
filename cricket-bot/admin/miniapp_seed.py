"""Bootstrap logic for the Mini App admin system.

Creates the initial admin user (from env vars) if the admin_users table
is empty so the owner can log in for the first time.
"""

import logging

import bcrypt
from sqlalchemy.orm import Session

from config.settings import MINIAPP_INIT_EMAIL, MINIAPP_INIT_PASSWORD
from database.models import AdminUser

logger = logging.getLogger(__name__)


def seed_initial_admin(db: Session) -> None:
    """Create the first admin user when the table is empty.

    Uses ``MINIAPP_INIT_EMAIL`` and ``MINIAPP_INIT_PASSWORD`` env vars.
    Does nothing if an admin already exists or the env vars are not set.
    """
    if not MINIAPP_INIT_EMAIL or not MINIAPP_INIT_PASSWORD:
        logger.debug(
            "MINIAPP_INIT_EMAIL / MINIAPP_INIT_PASSWORD not set – "
            "skipping initial admin seed."
        )
        return

    existing = db.query(AdminUser).first()
    if existing:
        return

    hashed = bcrypt.hashpw(
        MINIAPP_INIT_PASSWORD.encode(), bcrypt.gensalt()
    ).decode()
    admin = AdminUser(
        email=MINIAPP_INIT_EMAIL.strip().lower(),
        password_hash=hashed,
        display_name="Owner",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    logger.info("Initial admin user created: %s", admin.email)
