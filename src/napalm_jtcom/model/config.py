"""Canonical device configuration model for napalm-jtcom."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from napalm_jtcom.model.port import PortConfig, PortSettings
from napalm_jtcom.model.vlan import VlanConfig, VlanEntry

logger = logging.getLogger(__name__)


@dataclass
class DeviceConfig:
    """Full device configuration snapshot: VLANs + ports.

    Attributes:
        vlans: Mapping of VLAN ID to :class:`~napalm_jtcom.model.vlan.VlanConfig`.
        ports: Mapping of 1-based port ID to :class:`~napalm_jtcom.model.port.PortConfig`.
        metadata: Arbitrary string key-value metadata (e.g. capture timestamp).
    """

    vlans: dict[int, VlanConfig] = field(default_factory=dict)
    ports: dict[int, PortConfig] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_current(
        cls,
        current_vlans: dict[int, VlanEntry],
        current_ports: list[PortSettings],
    ) -> DeviceConfig:
        """Build a :class:`DeviceConfig` from the switch current state.

        Converts :class:`~napalm_jtcom.model.vlan.VlanEntry` port name strings
        (``"Port N"``) to 0-based integer indices used by
        :class:`~napalm_jtcom.model.vlan.VlanConfig`.

        Args:
            current_vlans: VLAN ID to :class:`VlanEntry` mapping from the parser.
            current_ports: List of :class:`PortSettings` from the port parser.

        Returns:
            A fully-populated :class:`DeviceConfig`.
        """
        vlans: dict[int, VlanConfig] = {}
        for vid, entry in current_vlans.items():
            tagged: list[int] = []
            for name in entry.tagged_ports:
                idx = _port_name_to_index(name)
                if idx is not None:
                    tagged.append(idx)
                else:
                    logger.warning("Skipping unparseable tagged port name %r in VLAN %d", name, vid)
            untagged: list[int] = []
            for name in entry.untagged_ports:
                idx = _port_name_to_index(name)
                if idx is not None:
                    untagged.append(idx)
                else:
                    logger.warning(
                        "Skipping unparseable untagged port name %r in VLAN %d", name, vid
                    )
            vlans[vid] = VlanConfig(
                vlan_id=vid,
                name=entry.name,
                tagged_ports=sorted(tagged),
                untagged_ports=sorted(untagged),
            )

        ports: dict[int, PortConfig] = {}
        for s in current_ports:
            ports[s.port_id] = PortConfig(
                port_id=s.port_id,
                admin_up=s.admin_up,
                speed_duplex=s.speed_duplex,
                flow_control=s.flow_control,
            )

        return cls(vlans=vlans, ports=ports)


def _port_name_to_index(name: str) -> int | None:
    """Convert ``"Port N"`` to a 0-based integer index, or ``None`` if unparseable."""
    parts = name.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return int(parts[1]) - 1
    return None
