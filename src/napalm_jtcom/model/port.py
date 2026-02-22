"""Typed model for port/interface data."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PortEntry:
    """Represents a single physical port configuration entry.

    Attributes:
        port_id: Switch port identifier, e.g. ``1``, ``gi1``.
        description: Port description / alias.
        admin_enabled: Whether the port is administratively enabled.
        speed: Negotiated speed in Mbps, or None if down/unknown.
        duplex: Duplex mode: ``"full"``, ``"half"``, or ``"auto"``.
        link_up: Current link state.
    """

    port_id: str
    description: str = ""
    admin_enabled: bool = True
    speed: int | None = None
    duplex: str = "auto"
    link_up: bool = False
