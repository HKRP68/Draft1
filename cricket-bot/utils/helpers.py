"""Utility helper functions."""

import logging
import os

logger = logging.getLogger(__name__)


def cleanup_temp_file(filepath: str) -> None:
    """Safely remove a temporary file."""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
    except OSError as e:
        logger.warning("Failed to clean up temp file %s: %s", filepath, e)


def truncate_text(text: str, max_length: int = 4096) -> str:
    """Truncate text to fit Telegram message limits."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def safe_int(value, default: int = 0) -> int:
    """Safely convert a value to int."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
