"""Typed models for port/interface data."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PortSettings:
    """Administrative configuration for a single switch port.

    Attributes:
        port_id: 1-based port number as reported by the switch.
        name: Human-readable port name (e.g. ``"Port 1"``).
        admin_up: ``True`` if the port is administratively enabled.
        speed_duplex: Configured speed/duplex string (e.g. ``"Auto"``,
            ``"1000M/Full"``), or ``None`` if unknown.
        flow_control: ``True`` if flow control is enabled, ``None`` if unknown.
    """

    port_id: int
    name: str
    admin_up: bool
    speed_duplex: str | None = None
    flow_control: bool | None = None


@dataclass
class PortOperStatus:
    """Operational status for a single switch port.

    Attributes:
        port_id: 1-based port number matching :attr:`PortSettings.port_id`.
        link_up: ``True`` if the link is up, ``False`` if down, ``None`` if
            the state could not be determined.
        negotiated_speed_mbps: Negotiated link speed in Mbps
            (e.g. 10, 100, 1000, 10000), or ``None`` if link is down.
        duplex: Negotiated duplex: ``"full"``, ``"half"``, or ``None``.
    """

    port_id: int
    link_up: bool | None = None
    negotiated_speed_mbps: int | None = None
    duplex: str | None = None
