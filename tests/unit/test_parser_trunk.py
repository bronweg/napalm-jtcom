"""Unit tests for napalm_jtcom.parser.trunk."""

from __future__ import annotations

import pytest

from napalm_jtcom.parser.trunk import parse_trunk_groups, parse_lacp_status


def test_parse_trunk_groups_not_implemented() -> None:
    """parse_trunk_groups raises NotImplementedError until implemented."""
    with pytest.raises(NotImplementedError):
        parse_trunk_groups("<html></html>")


def test_parse_lacp_status_not_implemented() -> None:
    """parse_lacp_status raises NotImplementedError until implemented."""
    with pytest.raises(NotImplementedError):
        parse_lacp_status("<html></html>")
