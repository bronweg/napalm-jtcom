"""JTCom field name mappings from HTML labels to model attributes.

Maps raw HTML text labels (as they appear in the switch web UI) to
the typed model attribute names used in this driver.
"""

from __future__ import annotations

# Maps port speed strings displayed in the UI to integer Mbps values.
SPEED_MAP: dict[str, int] = {
    "10M": 10,
    "100M": 100,
    "1000M": 1000,
    "1G": 1000,
    "10G": 10000,
}

# Maps duplex strings from the UI to normalised values.
DUPLEX_MAP: dict[str, str] = {
    "Full": "full",
    "Half": "half",
    "Auto": "auto",
}
