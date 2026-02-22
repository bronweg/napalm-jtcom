"""Custom exceptions for the napalm-jtcom HTTP client."""

from __future__ import annotations

from dataclasses import dataclass

# Switch JSON response codes
CODE_OK: int = 0
CODE_PARAM_ERR: int = 1
CODE_AUTH_EXPIRED: int = 11


class JTComError(Exception):
    """Base exception for all napalm-jtcom errors."""


class JTComAuthError(JTComError):
    """Raised when authentication with the switch fails."""


class JTComRequestError(JTComError):
    """Raised when a network-level error occurs (connection refused, timeout, etc.)."""

    def __init__(self, url: str, cause: Exception) -> None:
        self.url = url
        self.cause = cause
        super().__init__(f"Request to {url!r} failed: {cause}")


class JTComResponseError(JTComError):
    """Raised when the switch returns a non-2xx HTTP status code."""

    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f"HTTP {status_code} for {url!r}")


class JTComParseError(JTComError):
    """Raised when HTML/JSON parsing fails or expected elements are not found."""


@dataclass
class JTComSwitchError(JTComError):
    """Raised when the switch returns a JSON payload with a non-zero error code."""

    code: int
    message: str
    endpoint: str
    payload: dict[str, object] | None = None

    def __post_init__(self) -> None:
        super().__init__(
            f"Switch error code={self.code} at {self.endpoint!r}: {self.message}"
        )
