#!/usr/bin/python3
# Copyright: (c) 2024, napalm-jtcom contributors
# SPDX-License-Identifier: Apache-2.0
"""Ansible action plugin: jtcom_config.

Runs entirely in the Ansible controller Python process — napalm_jtcom is
imported directly with no subprocess or bootstrap tricks required.
"""
from __future__ import annotations

from typing import Any

from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):  # type: ignore[misc]
    """Idempotent configuration of JTCom CGI switches via napalm_jtcom."""

    TRANSFERS_FILES = False

    def run(
        self,
        tmp: str | None = None,
        task_vars: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = super().run(tmp, task_vars)
        p: dict[str, Any] = self._task.args

        for key in ("host", "username", "password"):
            if not p.get(key):
                return dict(failed=True, msg=f"Parameter '{key}' is required.")

        try:
            from napalm_jtcom.driver import JTComDriver
            from napalm_jtcom.model.config import DeviceConfig
            from napalm_jtcom.model.port import PortConfig
            from napalm_jtcom.model.vlan import VlanConfig
        except ImportError as exc:
            return dict(failed=True, msg=f"napalm_jtcom is not installed: {exc}")

        vlans: dict[int, Any] = {}
        for key, entry in (p.get("vlans") or {}).items():
            vid = int(key)
            entry = entry or {}
            vlans[vid] = VlanConfig(
                vlan_id=vid,
                name=entry.get("name", ""),
                tagged_ports=[int(x) for x in entry.get("tagged_ports", [])],
                untagged_ports=[int(x) for x in entry.get("untagged_ports", [])],
                state=entry.get("state", "present"),
            )

        ports: dict[int, Any] = {}
        for key, entry in (p.get("ports") or {}).items():
            pid = int(key)
            entry = entry or {}
            ports[pid] = PortConfig(
                port_id=pid,
                admin_up=entry.get("admin_up"),
                speed_duplex=entry.get("speed_duplex"),
                flow_control=entry.get("flow_control"),
            )

        desired = DeviceConfig(vlans=vlans, ports=ports)

        optional_args: dict[str, Any] = {
            "verify_tls": p.get("verify_tls", False),
            "backup_before_change": p.get("backup_before_change", True),
            "safety_port_id": p.get("safety_port_id", 6),
        }
        if p.get("port") is not None:
            optional_args["port"] = p["port"]

        try:
            driver = JTComDriver(
                hostname=p["host"],
                username=p["username"],
                password=p["password"],
                optional_args=optional_args,
            )
            driver.open()
            try:
                cfg_result = driver.apply_device_config(
                    desired,
                    check_mode=self._play_context.check_mode,
                )
            finally:
                driver.close()
        except Exception as exc:  # noqa: BLE001
            return dict(failed=True, msg=str(exc))

        result.update(
            changed=cfg_result["changed"],
            diff=cfg_result["diff"],
            backup_file=cfg_result.get("backup_file", ""),
            applied=cfg_result.get("applied", []),
        )
        return result
