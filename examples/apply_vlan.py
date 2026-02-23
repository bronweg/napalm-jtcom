#!/usr/bin/env python3
"""Example: apply an incremental VLAN change to a JTCom switch.

Only the VLANs listed in ``DESIRED_VLANS`` are affected; all other VLANs on
the switch are left completely untouched.  Each entry must carry a ``state``
field:

    state="present"  — create the VLAN if it doesn't exist, or update its
                       name/membership if it does.
    state="absent"   — delete the VLAN if it exists (VLAN 1 is never deleted).

Usage (dry run, default):

    JTCOM_HOST=192.0.2.1 python examples/apply_vlan.py

Usage (live apply):

    APPLY=1 JTCOM_HOST=192.0.2.1 python examples/apply_vlan.py

Environment variables:
    JTCOM_HOST        Switch IP or hostname (required).
    JTCOM_USERNAME    Login username (default: admin).
    JTCOM_PASSWORD    Login password (default: admin).
    JTCOM_VERIFY_TLS  Set to "true" to verify TLS certificates (default: false).
    APPLY             Set to "1" to actually apply changes (default: dry-run).
"""

from __future__ import annotations

import os
import sys

from napalm_jtcom.driver import JTComDriver
from napalm_jtcom.model.vlan import VlanConfig

# ---------------------------------------------------------------------------
# Incremental VLAN change set — only these VLANs will be touched.
# ---------------------------------------------------------------------------
DESIRED_VLANS: dict[int, VlanConfig] = {
    222: VlanConfig(vlan_id=222, name="test222", state="present"),  # create / update
    # 10: VlanConfig(vlan_id=10, state="absent"),  # uncomment to delete VLAN 10
}

# ---------------------------------------------------------------------------
# Read configuration from environment
# ---------------------------------------------------------------------------
host = os.environ.get("JTCOM_HOST", "")
if not host:
    print("ERROR: JTCOM_HOST environment variable is required.", file=sys.stderr)
    sys.exit(1)

username = os.environ.get("JTCOM_USERNAME", "admin")
password = os.environ.get("JTCOM_PASSWORD", "admin")
verify_tls = os.environ.get("JTCOM_VERIFY_TLS", "false").lower() == "true"
apply_changes = os.environ.get("APPLY", "0") == "1"

# ---------------------------------------------------------------------------
# Driver setup and apply
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
    plan = driver.set_vlans(DESIRED_VLANS, dry_run=True)
    print(f"  Create : {plan['create']}")
    print(f"  Update : {plan['update']}")
    print(f"  Delete : {plan['delete']}")
    print()

    if not apply_changes:
        print("Dry-run only -- set APPLY=1 to apply changes.")
        sys.exit(0)

    print("=== APPLYING ===")
    result = driver.set_vlans(DESIRED_VLANS, dry_run=False)
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
