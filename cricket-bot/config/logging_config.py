"""Logging configuration for the Cricket Bot."""

import logging
import os
from config.settings import LOG_LEVEL

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def setup_logging():
    """Configure logging with file and console handlers."""
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler – bot.log (all messages)
    bot_handler = logging.FileHandler(os.path.join(LOG_DIR, "bot.log"))
    bot_handler.setLevel(level)
    bot_handler.setFormatter(formatter)
    root_logger.addHandler(bot_handler)

    # File handler – errors.log (ERROR and above)
    error_handler = logging.FileHandler(os.path.join(LOG_DIR, "errors.log"))
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    return root_logger
