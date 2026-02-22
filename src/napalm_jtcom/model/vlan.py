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
