#!/usr/bin/env python3
"""Example: apply a declarative VLAN configuration to a JTCom switch.

Environment variables:
    JTCOM_HOST       Switch base URL, e.g. http://192.168.51.21
    JTCOM_USERNAME   Login username (default: admin)
    JTCOM_PASSWORD   Login password (default: admin)
    JTCOM_VERIFY_TLS Verify TLS certificates, "true" / "false" (default: false)
    APPLY            Set to "1" to actually apply changes; omit for dry-run only

Usage (dry run first, then apply):

    JTCOM_HOST=http://192.168.51.21 python examples/apply_vlan.py
    APPLY=1 JTCOM_HOST=http://192.168.51.21 python examples/apply_vlan.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from napalm_jtcom.driver import JTComDriver
from napalm_jtcom.model.vlan import VlanConfig

# ---------------------------------------------------------------------------
# Desired VLAN state -- edit this to suit your test
# ---------------------------------------------------------------------------
DESIRED_VLANS: dict[int, VlanConfig] = {
    1: VlanConfig(vlan_id=1),            # keep VLAN 1 unchanged
    222: VlanConfig(vlan_id=222, name="test222"),  # create / ensure this VLAN
}

# ---------------------------------------------------------------------------
# Read configuration from environment
# ---------------------------------------------------------------------------
host = os.environ.get("JTCOM_HOST", "http://192.168.51.21")
username = os.environ.get("JTCOM_USERNAME", "admin")
password = os.environ.get("JTCOM_PASSWORD", "admin")
verify_tls = os.environ.get("JTCOM_VERIFY_TLS", "false").lower() == "true"
apply_changes = os.environ.get("APPLY", "") == "1"

# ---------------------------------------------------------------------------
# Driver setup
# ---------------------------------------------------------------------------
print(f"Target switch : {host}")
print(f"Apply changes : {apply_changes}")
print()

driver = JTComDriver(
    hostname=host,
    username=username,
    password=password,
    optional_args={
        "verify_tls": verify_tls,
        "backup_before_change": apply_changes,  # only backup when really applying
        "backup_dir": "./backups",
    },
)

try:
    driver.open()
    print("=== DRY RUN ===")
    plan = driver.set_vlans(DESIRED_VLANS, dry_run=True, allow_delete=False)
    print(f"  Create : {plan['create']}")
    print(f"  Update : {plan['update']}")
    print(f"  Delete : {plan['delete']}")
    print()

    if not apply_changes:
        print("Dry-run only -- set APPLY=1 to apply changes.")
        sys.exit(0)

    print("=== APPLYING ===")
    result = driver.set_vlans(DESIRED_VLANS, dry_run=False, allow_delete=False)
    print(f"  Backup : {result['backup_file'] or '(none)'}")
    print(f"  Created: {result['create']}")
    print(f"  Updated: {result['update']}")
    print(f"  Deleted: {result['delete']}")
    print()
    print("Done.")

except Exception as exc:  # noqa: BLE001
    print(f"ERROR: {exc}", file=sys.stderr)
    sys.exit(1)
finally:
    driver.close()
