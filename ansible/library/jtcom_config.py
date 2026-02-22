#!/usr/bin/python3
# Copyright: (c) 2024, napalm-jtcom contributors
# SPDX-License-Identifier: Apache-2.0
"""Ansible module stub: jtcom_config.

All execution logic lives in action_plugins/jtcom_config.py which runs in the
Ansible controller Python process and imports napalm_jtcom directly.
This file exists only for argument documentation (ansible-doc, Galaxy, IDEs).
"""

from __future__ import annotations

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

from ansible.module_utils.basic import AnsibleModule  # noqa: E402  # type: ignore[import-untyped]


def main() -> None:
    module = AnsibleModule(
        argument_spec=dict(
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
        ),
        supports_check_mode=True,
    )
    # Execution is handled entirely by action_plugins/jtcom_config.py.
    # This stub is reached only when the action plugin is absent.
    module.fail_json(msg="jtcom_config action plugin not found. Check action_plugins path.")


if __name__ == "__main__":
    main()
