#!/usr/bin/python3
# Copyright: (c) 2024, napalm-jtcom contributors
# SPDX-License-Identifier: Apache-2.0
"""Ansible module: jtcom_config — idempotent configuration for JTCom CGI switches."""

from __future__ import annotations

import os
import sys


# ---------------------------------------------------------------------------
# Bootstrap: re-exec under the venv Python if napalm_jtcom is not importable.
# Ansible 2.20 hardcodes /usr/bin/python3 for localhost module execution
# regardless of ansible_python_interpreter.  When VIRTUAL_ENV is set (either
# by activating the venv or passing it explicitly), we transparently re-exec
# the AnsiballZ wrapper under the correct interpreter so all dependencies are
# available.
#
# NOTE: sys.argv[0] inside AnsiballZ is a synthetic zip path such as
#   ".../ansible_jtcom_config_payload.zip/ansible/legacy/jtcom_config.py"
# which is NOT a real filesystem path.  We therefore recover the actual
# AnsiballZ wrapper path by querying the OS process table via ``ps``.
# ---------------------------------------------------------------------------
def _bootstrap_venv() -> None:
    import subprocess

    try:
        import napalm_jtcom  # noqa: F401  # type: ignore[import-untyped]

        return  # Already running under the right Python.
    except ImportError:
        pass

    venv = os.environ.get("VIRTUAL_ENV", "")
    if not venv:
        return  # No hint; fall through and let AnsibleModule surface the error.

    candidate = os.path.join(venv, "bin", "python3")
    if candidate == sys.executable:
        return  # Already this Python; nothing to do.
    if not (os.path.isfile(candidate) and os.access(candidate, os.X_OK)):
        return

    # Recover the real AnsiballZ wrapper path from the OS process table.
    # Expected cmdline: '/usr/bin/python3 /path/.ansible/tmp/.../AnsiballZ_jtcom_config.py'
    script: str | None = None
    try:
        result = subprocess.run(
            ["ps", "-p", str(os.getpid()), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for part in reversed(result.stdout.strip().split()):
            if os.path.isfile(part) and "AnsiballZ" in part:
                script = part
                break
    except Exception:  # noqa: BLE001
        pass

    if script:
        # Replace the current process with the venv Python running AnsiballZ.
        os.execv(candidate, [candidate, script])
    # Fall through — AnsibleModule will surface the ImportError.


_bootstrap_venv()


DOCUMENTATION = r"""
---
module: jtcom_config
short_description: Configure JTCom CGI Ethernet switches
description:
  - Idempotent configuration of VLANs and ports on JTCom-compatible L2 switches.
  - Wraps napalm-jtcom C(apply_device_config()) for deterministic, diff-aware apply.
  - Supports Ansible check mode (dry-run) natively.
options:
  host:
    description: IP address or hostname of the switch.
    required: true
    type: str
  username:
    description: Login username.
    required: true
    type: str
  password:
    description: Login password.
    required: true
    type: str
    no_log: true
  port:
    description: HTTP(S) port override. Defaults to 80 (or 443 when verify_tls=true).
    type: int
  verify_tls:
    description: Verify TLS certificates when connecting over HTTPS.
    type: bool
    default: false
  backup_before_change:
    description: Download and save a config backup before applying any change.
    type: bool
    default: true
  safety_port_id:
    description: >
      1-based port ID that must never be administratively disabled (management uplink).
      Defaults to 6.
    type: int
    default: 6
  allow_vlan_delete:
    description: >
      Allow deletion of VLANs present on the device but absent from I(vlans).
      VLAN 1 is never deleted regardless of this flag.
    type: bool
    default: false
  allow_vlan_membership:
    description: Include port-membership differences in the VLAN change plan.
    type: bool
    default: true
  allow_vlan_rename:
    description: Include VLAN name differences in the change plan.
    type: bool
    default: true
  vlans:
    description: >
      Desired VLAN configuration, keyed by VLAN ID (string or int).
      Each entry may contain C(name), C(tagged_ports), and C(untagged_ports).
      Ports are 0-based indices as used by the switch CGI.
    type: dict
  ports:
    description: >
      Desired port configuration, keyed by 1-based port ID (string or int).
      Each entry may contain C(admin_up) (bool), C(speed_duplex) (str),
      and C(flow_control) (bool).  Omit a field to leave it unchanged.
    type: dict
notes:
  - Run this module on the Ansible controller (C(connection: local)).
  - napalm-jtcom must be installed in the Python environment used by Ansible.
  - Use C(--check) for a safe dry-run that shows planned changes without applying them.
requirements:
  - napalm-jtcom >= 0.8.0
author:
  - napalm-jtcom contributors
"""

EXAMPLES = r"""
- name: Configure VLANs on JTCom switch (check mode)
  jtcom_config:
    host: 192.168.51.21
    username: admin
    password: admin
    vlans:
      10:
        name: Management
      100:
        name: Servers
        untagged_ports: [2, 3]
  check_mode: true

- name: Apply VLAN and port config
  jtcom_config:
    host: 192.168.51.21
    username: admin
    password: admin
    allow_vlan_delete: false
    vlans:
      10:
        name: Management
        untagged_ports: [0]
      20:
        name: Data
        untagged_ports: [1, 2, 3]
    ports:
      1:
        admin_up: true
        speed_duplex: Auto
        flow_control: false
"""

RETURN = r"""
changed:
  description: Whether any configuration change was made (or would be in check mode).
  type: bool
  returned: always
diff:
  description: >
    Structured diff dict from the napalm-jtcom plan engine, containing
    C(summary), C(total_changes), and C(changes) list.
  type: dict
  returned: always
backup_file:
  description: Path to the config backup file saved before changes, or empty string.
  type: str
  returned: always
applied:
  description: List of change keys that were applied (empty in check mode).
  type: list
  elements: str
  returned: always
"""

from ansible.module_utils.basic import AnsibleModule  # noqa: E402


def _build_desired_config(vlans_param: dict | None, ports_param: dict | None) -> object:  # type: ignore[type-arg]
    """Convert module params into a DeviceConfig instance."""
    # Import here so import errors surface as fail_json, not as a module crash
    from napalm_jtcom.model.config import DeviceConfig
    from napalm_jtcom.model.port import PortConfig
    from napalm_jtcom.model.vlan import VlanConfig

    vlans = {}
    for key, entry in (vlans_param or {}).items():
        vid = int(key)
        entry = entry or {}
        vlans[vid] = VlanConfig(
            vlan_id=vid,
            name=entry.get("name", ""),
            tagged_ports=[int(p) for p in entry.get("tagged_ports", [])],
            untagged_ports=[int(p) for p in entry.get("untagged_ports", [])],
        )

    ports = {}
    for key, entry in (ports_param or {}).items():
        pid = int(key)
        entry = entry or {}
        ports[pid] = PortConfig(
            port_id=pid,
            admin_up=entry.get("admin_up"),
            speed_duplex=entry.get("speed_duplex"),
            flow_control=entry.get("flow_control"),
        )

    return DeviceConfig(vlans=vlans, ports=ports)


def run_module() -> None:
    argument_spec = dict(
        host=dict(type="str", required=True),
        username=dict(type="str", required=True),
        password=dict(type="str", required=True, no_log=True),
        port=dict(type="int"),
        verify_tls=dict(type="bool", default=False),
        backup_before_change=dict(type="bool", default=True),
        safety_port_id=dict(type="int", default=6),
        allow_vlan_delete=dict(type="bool", default=False),
        allow_vlan_membership=dict(type="bool", default=True),
        allow_vlan_rename=dict(type="bool", default=True),
        vlans=dict(type="dict"),
        ports=dict(type="dict"),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    p = module.params

    # Build optional_args for the driver
    optional_args: dict = {
        "verify_tls": p["verify_tls"],
        "backup_before_change": p["backup_before_change"],
        "safety_port_id": p["safety_port_id"],
    }
    if p["port"] is not None:
        optional_args["port"] = p["port"]

    try:
        from napalm_jtcom.driver import JTComDriver

        desired = _build_desired_config(p["vlans"], p["ports"])

        driver = JTComDriver(
            hostname=p["host"],
            username=p["username"],
            password=p["password"],
            optional_args=optional_args,
        )
        driver.open()
        try:
            result = driver.apply_device_config(
                desired,
                check_mode=module.check_mode,
                allow_vlan_delete=p["allow_vlan_delete"],
                allow_vlan_membership=p["allow_vlan_membership"],
                allow_vlan_rename=p["allow_vlan_rename"],
            )
        finally:
            driver.close()

    except Exception as exc:
        module.fail_json(msg=str(exc))
        return

    module.exit_json(
        changed=result["changed"],
        diff=result["diff"],
        backup_file=result.get("backup_file", ""),
        applied=result.get("applied", []),
    )


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()
