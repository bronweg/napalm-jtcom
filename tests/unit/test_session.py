"""Unit tests for napalm_jtcom.client.session."""

from __future__ import annotations

import pytest

from napalm_jtcom.client.session import JTComSession


def test_session_init() -> None:
    """JTComSession stores constructor arguments correctly."""
    session = JTComSession(
        base_url="http://192.168.1.1",
        username="admin",
        password="secret",
        timeout=15,
        verify_ssl=False,
    )
    assert session.base_url == "http://192.168.1.1"
    assert session.username == "admin"
    assert session.timeout == 15
    assert session.verify_ssl is False


def test_session_base_url_trailing_slash_stripped() -> None:
    """Trailing slash is stripped from base_url."""
    session = JTComSession(
        base_url="http://192.168.1.1/",
        username="admin",
        password="pw",
    )
    assert session.base_url == "http://192.168.1.1"


def test_session_not_open_by_default() -> None:
    """A newly created session reports is_open == False."""
    session = JTComSession("http://192.168.1.1", "admin", "pw")
    assert session.is_open is False
