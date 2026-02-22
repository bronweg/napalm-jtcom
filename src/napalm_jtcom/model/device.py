"""Typed model for device information."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeviceInfo:
    """General device information parsed from the switch system page.

    Attributes:
        hostname: Configured system hostname.
        vendor: Vendor name.
        model: Device model string.
        serial_number: Serial number, if available.
        os_version: Firmware / software version string.
        uptime_seconds: Device uptime in seconds, or -1 if unavailable.
    """

    hostname: str
    vendor: str = "JTCom"
    model: str = ""
    serial_number: str = ""
    os_version: str = ""
    uptime_seconds: int = -1
