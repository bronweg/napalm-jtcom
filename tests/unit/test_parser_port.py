"""Unit tests for napalm_jtcom.parser.port."""

from __future__ import annotations

import pytest

from napalm_jtcom.parser.port import parse_port_settings


def test_parse_port_settings_not_implemented() -> None:
    """parse_port_settings raises NotImplementedError until implemented."""
    with pytest.raises(NotImplementedError):
        parse_port_settings("<html></html>")
