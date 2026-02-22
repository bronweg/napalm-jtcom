"""Parser for JTCom port/interface settings pages."""

from __future__ import annotations

from napalm_jtcom.model.port import PortEntry


def parse_port_settings(html: str) -> list[PortEntry]:
    """Parse the port settings page and return port entries.

    Args:
        html: Raw HTML from the port settings page.

    Returns:
        List of parsed PortEntry objects.
    """
    raise NotImplementedError("parse_port_settings() not yet implemented")
