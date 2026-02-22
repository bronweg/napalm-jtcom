"""JTCom CGI endpoint URL paths.

Each constant is a URL path segment relative to the switch base URL.
Extend this module as new pages are reverse-engineered.
"""

from __future__ import annotations

# Device / system
DEVICE_INFO: str = "/cgi-bin/system_info.cgi"

# Port management
PORT_SETTINGS: str = "/cgi-bin/port_settings.cgi"

# VLAN management
VLAN_STATIC: str = "/cgi-bin/vlan_static.cgi"
VLAN_PORT_BASED: str = "/cgi-bin/vlan_portbased.cgi"

# Trunk / LAG
TRUNK_GROUP: str = "/cgi-bin/trunk_group.cgi"
TRUNK_LACP: str = "/cgi-bin/trunk_lacp.cgi"

# Authentication
LOGIN: str = "/cgi-bin/login.cgi"
LOGOUT: str = "/cgi-bin/logout.cgi"
