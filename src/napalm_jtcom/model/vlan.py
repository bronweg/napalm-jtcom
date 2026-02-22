"""Typed model for VLAN data."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VlanEntry:
    """Represents a single VLAN configuration entry.

    Attributes:
        vlan_id: 802.1Q VLAN identifier (1-4094).
        name: Human-readable VLAN name.
        tagged_ports: Ports that carry this VLAN tagged (trunk ports).
        untagged_ports: Ports that carry this VLAN untagged (access ports).
        active: Whether the VLAN is administratively active.
    """

    vlan_id: int
    name: str
    tagged_ports: list[str] = field(default_factory=list)
    untagged_ports: list[str] = field(default_factory=list)
    active: bool = True


@dataclass
class VlanPortConfig:
    """Per-port VLAN configuration parsed from the port-based VLAN page.

    Attributes:
        port_name: Human-readable port name (e.g. "Port 1").
        vlan_type: VLAN mode — "Access" or "Trunk".
        access_vlan: Access VLAN ID (Access mode only; None if not set).
        native_vlan: Native/untagged VLAN ID (Trunk mode only; None if not set).
        permit_vlans: List of tagged VLAN IDs allowed on this trunk port.
    """

    port_name: str
    vlan_type: str
    access_vlan: int | None = None
    native_vlan: int | None = None
    permit_vlans: list[int] = field(default_factory=list)


@dataclass
class VlanConfig:
    """Desired VLAN state used as input to :func:`plan_vlan_changes`.

    Attributes:
        vlan_id: 802.1Q VLAN identifier (1-4094).
        name: Human-readable VLAN name; ``None`` means "do not change".
        tagged_ports: 0-based port indices that carry this VLAN tagged (trunk).
        untagged_ports: 0-based port indices that carry this VLAN untagged (access).
    """

    vlan_id: int
    name: str | None = None
    tagged_ports: list[int] = field(default_factory=list)
    untagged_ports: list[int] = field(default_factory=list)


@dataclass
class VlanChangeSet:
    """A set of planned VLAN changes produced by :func:`plan_vlan_changes`.

    Attributes:
        create: VLANs that exist in *desired* but not in *current*.
        update: VLANs present in both where name or membership differs.
        delete: VLAN IDs present in *current* but not in *desired*
                (only populated when ``allow_delete=True``; VLAN 1 is never included).
    """

    create: list[VlanConfig] = field(default_factory=list)
    update: list[VlanConfig] = field(default_factory=list)
    delete: list[int] = field(default_factory=list)

