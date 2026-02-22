"""Authenticated HTTP session for JTCom switches."""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests

from napalm_jtcom.client.errors import JTComAuthError, JTComHTTPError

logger = logging.getLogger(__name__)


class JTComSession:
    """Manages a persistent, authenticated requests.Session to a JTCom switch.

    Args:
        base_url: Base URL of the switch, e.g. ``http://192.168.1.1``.
        username: Login username.
        password: Login password.
        timeout: Default request timeout in seconds.
        verify_ssl: Whether to verify TLS certificates.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout: int = 30,
        verify_ssl: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._session: Optional[requests.Session] = None

    def open(self) -> None:
        """Create session and authenticate. Raises JTComAuthError on failure."""
        raise NotImplementedError("Session.open() not yet implemented")

    def close(self) -> None:
        """Logout and close the underlying requests.Session."""
        raise NotImplementedError("Session.close() not yet implemented")

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        """Perform an authenticated GET request.

        Args:
            path: URL path relative to base_url.
            **kwargs: Extra arguments forwarded to requests.Session.get().

        Returns:
            The HTTP response object.

        Raises:
            JTComHTTPError: If the response status code is not 2xx.
        """
        raise NotImplementedError("Session.get() not yet implemented")

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        """Perform an authenticated POST request.

        Args:
            path: URL path relative to base_url.
            **kwargs: Extra arguments forwarded to requests.Session.post().

        Returns:
            The HTTP response object.

        Raises:
            JTComHTTPError: If the response status code is not 2xx.
        """
        raise NotImplementedError("Session.post() not yet implemented")

    @property
    def is_open(self) -> bool:
        """True if the session is currently open and authenticated."""
        return self._session is not None
