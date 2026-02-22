"""Unit tests for napalm_jtcom.parser.device."""

from __future__ import annotations

import pytest

from napalm_jtcom.parser.device import parse_device_info


def test_parse_device_info_not_implemented() -> None:
    """parse_device_info raises NotImplementedError until implemented."""
    with pytest.raises(NotImplementedError):
        parse_device_info("<html></html>")
