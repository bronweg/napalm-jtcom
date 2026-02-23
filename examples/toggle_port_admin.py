#!/usr/bin/env python3
"""Example: toggle a port's admin state and revert it (safe, dry-run by default).

Usage::

    # Dry-run (no changes) — shows the planned toggle:
    export JTCOM_HOST=192.0.2.1
    export TEST_PORT_ID=1        # required: 1-based port number to test
    python examples/toggle_port_admin.py

    # Apply (disables port, waits 2 s, re-enables it):
    export APPLY=1
    python examples/toggle_port_admin.py

Environment variables:
    JTCOM_HOST        Switch IP or hostname (required).
    JTCOM_USERNAME    Login username (default: admin).
    JTCOM_PASSWORD    Login password (default: admin).
    JTCOM_VERIFY_TLS  Set to "1" to verify TLS certificates (default: off).
    TEST_PORT_ID      1-based port number to toggle (required).
    APPLY             Set to "1" to actually apply changes (default: dry-run).

WARNING: Do NOT set TEST_PORT_ID to the management uplink port.
"""

from __future__ import annotations

import os
import sys
import time

from napalm_jtcom.client.port_ops import apply_port_changes
from napalm_jtcom.client.session import JTComCredentials, JTComSession
from napalm_jtcom.model.port import PortConfig
from napalm_jtcom.parser.port import parse_port_page
from napalm_jtcom.utils.port_diff import plan_port_changes
from napalm_jtcom.vendor.jtcom.endpoints import PORT_SETTINGS


def main() -> None:
    host = os.environ.get("JTCOM_HOST", "")
    if not host:
        print("ERROR: JTCOM_HOST environment variable is required.", file=sys.stderr)
        sys.exit(1)

    port_id_str = os.environ.get("TEST_PORT_ID", "")
    if not port_id_str:
        print("ERROR: TEST_PORT_ID environment variable is required.", file=sys.stderr)
        print("  Set it to the 1-based port number you want to toggle.", file=sys.stderr)
        sys.exit(1)

    try:
        port_id = int(port_id_str)
    except ValueError:
        print(f"ERROR: TEST_PORT_ID must be an integer, got {port_id_str!r}", file=sys.stderr)
        sys.exit(1)

    username = os.environ.get("JTCOM_USERNAME", "admin")
    password = os.environ.get("JTCOM_PASSWORD", "admin")
    verify_tls = os.environ.get("JTCOM_VERIFY_TLS", "0") == "1"
    apply_changes = os.environ.get("APPLY", "0") == "1"

    base_url = host if "://" in host else f"http://{host}"
    creds = JTComCredentials(username=username, password=password)
    session = JTComSession(base_url=base_url, credentials=creds, verify_tls=verify_tls)
    session.login()

    try:
        html = session.get(PORT_SETTINGS)
        settings_list, _ = parse_port_page(html)

        current_map = {s.port_id: s for s in settings_list}
        current = current_map.get(port_id)
        if current is None:
            print(f"ERROR: Port {port_id} not found on switch.", file=sys.stderr)
            sys.exit(1)

        print(f"Current state of Port {port_id}:")
        print(f"  admin_up     = {current.admin_up}")
        print(f"  speed_duplex = {current.speed_duplex}")
        print(f"  flow_control = {current.flow_control}")
        print()

        # Plan: toggle admin state
        toggled = not current.admin_up
        desired_disable = [PortConfig(port_id=port_id, admin_up=toggled)]
        desired_restore = [PortConfig(port_id=port_id, admin_up=current.admin_up)]

        cs_disable = plan_port_changes(settings_list, desired_disable)
        print(f"Dry-run plan — toggle to {'Enable' if toggled else 'Disable'}:")
        for cfg in cs_disable.update:
            print(f"  Port {cfg.port_id}: admin_up → {cfg.admin_up}")
        if not cs_disable.update:
            print("  (no changes needed)")
        print()

        if not apply_changes:
            print("Dry-run mode — set APPLY=1 to apply changes.")
            return

        action = 'Enable' if toggled else 'Disable'
        print(f"[APPLY] Toggling Port {port_id} admin state to {action}...")
        apply_port_changes(session, settings_list, cs_disable)
        print("  Done.  Waiting 2 seconds...")
        time.sleep(2)

        # Re-read current state after toggle
        html2 = session.get(PORT_SETTINGS)
        settings2, _ = parse_port_page(html2)
        cs_restore = plan_port_changes(settings2, desired_restore)

        orig = 'Enable' if current.admin_up else 'Disable'
        print(f"[APPLY] Restoring Port {port_id} admin state to {orig}...")
        apply_port_changes(session, settings2, cs_restore)
        print("  Done.  Port restored to original state.")

    finally:
        session.close()


if __name__ == "__main__":
    main()
