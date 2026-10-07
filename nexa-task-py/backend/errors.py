"""Exceptions shared by all layers."""


class ApiError(Exception):
    """An error that should be reported to the client with a specific HTTP status."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class DataAccessError(Exception):
    """Wraps low-level database failures so upper layers never deal with driver-specific errors."""
