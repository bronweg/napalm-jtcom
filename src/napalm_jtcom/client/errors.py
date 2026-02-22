"""Custom exceptions for the napalm-jtcom HTTP client."""

from __future__ import annotations


class JTComError(Exception):
    """Base exception for all napalm-jtcom errors."""


class JTComAuthError(JTComError):
    """Raised when authentication with the switch fails."""


class JTComHTTPError(JTComError):
    """Raised when an unexpected HTTP response is received."""

    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f"HTTP {status_code} for {url}")


class JTComParseError(JTComError):
    """Raised when HTML parsing fails or expected elements are not found."""
