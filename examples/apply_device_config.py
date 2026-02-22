#!/usr/bin/env python3
"""Demonstrate apply_device_config() with check_mode and live apply.

Usage (dry-run, default):
    python examples/apply_device_config.py

Usage (live apply):
    APPLY=1 python examples/apply_device_config.py

The script builds a minimal desired DeviceConfig that:
  - Keeps VLAN 1 (management) as-is.
  - Adds VLAN 100 named "example" (creates it if absent, updates name if present).
  - Leaves all ports at their current settings (no port changes).

Set APPLY=1 only when you are ready to push changes to the switch.
"""

from __future__ import annotations

import os
import pprint

from napalm_jtcom.driver import JTComNetworkDriver
from napalm_jtcom.model.config import DeviceConfig
from napalm_jtcom.model.vlan import VlanConfig

HOST = os.getenv("SWITCH_HOST", "192.168.51.21")
USERNAME = os.getenv("SWITCH_USER", "admin")
PASSWORD = os.getenv("SWITCH_PASS", "admin")
APPLY = os.getenv("APPLY", "0") == "1"

# ---------------------------------------------------------------------------
# Build the desired configuration
# ---------------------------------------------------------------------------
desired = DeviceConfig(
    vlans={
        1: VlanConfig(vlan_id=1, name="Default"),
        100: VlanConfig(vlan_id=100, name="example"),
    },
    # Leave ports empty → no port changes will be planned.
    ports={},
)

# ---------------------------------------------------------------------------
# Connect and apply (or dry-run)
# ---------------------------------------------------------------------------
driver = JTComNetworkDriver(
    hostname=HOST,
    username=USERNAME,
    password=PASSWORD,
    timeout=10,
    optional_args={"safety_port_id": 6, "backup_before_change": True},
)

driver.open()
try:
    result = driver.apply_device_config(
        desired,
        check_mode=not APPLY,
        allow_vlan_delete=False,
        allow_vlan_membership=True,
        allow_vlan_rename=True,
    )
finally:
    driver.close()

mode = "LIVE APPLY" if APPLY else "DRY-RUN (check_mode=True)"
print(f"\n=== apply_device_config — {mode} ===\n")
pprint.pprint(result)

if not APPLY:
    print(
        "\n[INFO] No changes were applied. "
        "Set APPLY=1 to push the plan above to the switch."
    )
