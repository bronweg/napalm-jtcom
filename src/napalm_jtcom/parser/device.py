"""Parser for JTCom device information pages."""

from __future__ import annotations

from napalm_jtcom.model.device import DeviceInfo


def parse_device_info(html: str) -> DeviceInfo:
    """Parse the device information page.

    Args:
        html: Raw HTML from the device information / system page.

    Returns:
        Parsed DeviceInfo object.
    """
    raise NotImplementedError("parse_device_info() not yet implemented")
