#!/usr/bin/env python3
"""Example: retrieve VLAN configuration from a JTCom switch using napalm-jtcom."""

from __future__ import annotations

import json

import napalm

# Replace with real switch credentials
HOST = "192.168.1.1"
USER = "admin"
PASS = "admin"

driver_cls = napalm.get_network_driver("jtcom")

with driver_cls(HOST, USER, PASS) as device:
    vlans = device.get_vlans()

print(json.dumps(vlans, indent=2))
