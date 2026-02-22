"""Parser for JTCom VLAN configuration pages."""

from __future__ import annotations

from napalm_jtcom.model.vlan import VlanEntry


def parse_static_vlans(html: str) -> list[VlanEntry]:
    """Parse the static VLAN list page and return VLAN entries.

    Args:
        html: Raw HTML from the VLAN static configuration page.

    Returns:
        List of parsed VlanEntry objects.
    """
    raise NotImplementedError("parse_static_vlans() not yet implemented")


def parse_port_based_vlans(html: str) -> list[VlanEntry]:
    """Parse the port-based VLAN page.

    Args:
        html: Raw HTML from the port-based VLAN configuration page.

    Returns:
        List of parsed VlanEntry objects.
    """
    raise NotImplementedError("parse_port_based_vlans() not yet implemented")
