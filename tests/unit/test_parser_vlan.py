"""Unit tests for napalm_jtcom.parser.vlan."""

from __future__ import annotations

import pathlib

import pytest

from napalm_jtcom.parser.vlan import parse_static_vlans, parse_port_based_vlans

FIXTURES = pathlib.Path(__file__).parent.parent / "fixtures"


def test_parse_static_vlans_not_implemented() -> None:
    """parse_static_vlans raises NotImplementedError until implemented."""
    with pytest.raises(NotImplementedError):
        parse_static_vlans("<html></html>")


def test_parse_port_based_vlans_not_implemented() -> None:
    """parse_port_based_vlans raises NotImplementedError until implemented."""
    with pytest.raises(NotImplementedError):
        parse_port_based_vlans("<html></html>")
