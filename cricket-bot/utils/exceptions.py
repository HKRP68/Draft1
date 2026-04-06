"""Custom exceptions for the Cricket Bot."""


class CricketBotError(Exception):
    """Base exception for Cricket Bot."""
    pass


class UserNotFoundError(CricketBotError):
    """Raised when a user is not found in the database."""
    pass


class CooldownActiveError(CricketBotError):
    """Raised when a command is on cooldown."""

    def __init__(self, remaining_seconds: int):
        self.remaining_seconds = remaining_seconds
        super().__init__(f"Cooldown active: {remaining_seconds}s remaining")


class RosterFullError(CricketBotError):
    """Raised when a user's roster is full."""
    pass


class PlayerNotFoundError(CricketBotError):
    """Raised when a player is not found in the database."""
    pass


class PlayerNotInRosterError(CricketBotError):
    """Raised when a player is not in the user's roster."""
    pass


class DatabaseError(CricketBotError):
    """Raised when a database operation fails."""
    pass


class ImageGenerationError(CricketBotError):
    """Raised when card image generation fails."""
    pass
