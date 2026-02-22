"""Typed models for port/interface data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


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


@dataclass
class PortConfig:
    """Desired configuration for a single switch port.

    Used as input to :func:`~napalm_jtcom.utils.port_diff.plan_port_changes`.
    Any field set to ``None`` means "do not change this attribute".

    Attributes:
        port_id: 1-based port number, matching :attr:`PortSettings.port_id`.
        admin_up: ``True`` to enable the port, ``False`` to disable it,
            ``None`` to leave unchanged.
        speed_duplex: Configured speed/duplex token as shown in the switch UI
            (e.g. ``"Auto"``, ``"1000M/Full"``), or ``None`` to leave unchanged.
        flow_control: ``True`` to enable flow control, ``False`` to disable,
            ``None`` to leave unchanged.
        state: ``"present"`` to apply config to this port; ``"absent"`` to disable it
            (set ``admin_up=False``).
    """

    port_id: int
    admin_up: bool | None = None
    speed_duplex: str | None = None
    flow_control: bool | None = None
    state: Literal["present", "absent"] = "present"


@dataclass
class PortChangeSet:
    """A set of planned port configuration changes.

    Attributes:
        update: Ports whose configuration differs from the desired state.
            Sorted ascending by :attr:`PortConfig.port_id`.
    """

    update: list[PortConfig] = field(default_factory=list)

