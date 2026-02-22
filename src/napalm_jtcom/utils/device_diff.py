"""Device-level diff / plan engine for napalm-jtcom.

Compares a *current* :class:`~napalm_jtcom.model.config.DeviceConfig` against
a *desired* one and produces an ordered :class:`DevicePlan` with the minimal
set of changes needed to reach *desired*.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Literal

from napalm_jtcom.model.config import DeviceConfig

ChangeKind = Literal["vlan_create", "vlan_update", "vlan_delete", "port_update"]


@dataclass
class Change:
    """A single configuration change.

    Attributes:
        kind: Category of change.
        key: Unique string key (e.g. ``"vlan:10"``, ``"port:3"``).
        details: Freeform metadata describing what changed.
    """

    kind: ChangeKind
    key: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DevicePlan:
    """Ordered list of changes to apply to reach the desired config.

    Apply ordering:

    1. ``vlan_create`` — ascending VLAN ID
    2. ``vlan_update`` — ascending VLAN ID
    3. ``port_update`` — ascending port_id
    4. ``vlan_delete`` — descending VLAN ID

    Attributes:
        changes: Ordered :class:`Change` list.
        summary: Count per change kind.
    """

    changes: list[Change] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)


def build_device_plan(
    current: DeviceConfig,
    desired: DeviceConfig,
    *,
    allow_vlan_delete: bool = False,
    allow_vlan_membership: bool = True,
    allow_vlan_rename: bool = True,
    safety_port_id: int | None = None,
) -> DevicePlan:
    """Compute the minimal ordered plan to move *current* to *desired*.

    Args:
        current: Current device config (as read from the switch).
        desired: Desired device config.
        allow_vlan_delete: Include ``vlan_delete`` changes for VLANs present in
            *current* but absent from *desired*.  VLAN 1 is never deleted.
        allow_vlan_membership: Include port membership differences in VLAN
            update detection.
        allow_vlan_rename: Include VLAN name differences in update detection.
        safety_port_id: 1-based port ID that must never be disabled.  A desired
            change that sets ``admin_up=False`` for this port is silently skipped.

    Returns:
        A :class:`DevicePlan` with changes in apply order.
    """
    creates: list[Change] = []
    updates: list[Change] = []
    port_changes: list[Change] = []
    deletes: list[Change] = []

    # ------------------------------------------------------------------ VLANs
    for vid in sorted(desired.vlans):
        cfg = desired.vlans[vid]
        if vid not in current.vlans:
            creates.append(
                Change(
                    kind="vlan_create",
                    key=f"vlan:{vid}",
                    details={
                        "vlan_id": vid,
                        "name": cfg.name,
                        "tagged_ports": list(cfg.tagged_ports),
                        "untagged_ports": list(cfg.untagged_ports),
                    },
                )
            )
            continue

        entry = current.vlans[vid]
        diffs: dict[str, Any] = {}

        if allow_vlan_rename and cfg.name is not None and cfg.name != entry.name:
            diffs["name"] = {"from": entry.name, "to": cfg.name}

        if allow_vlan_membership:
            if sorted(cfg.tagged_ports) != sorted(entry.tagged_ports):
                diffs["tagged_ports"] = {
                    "from": sorted(entry.tagged_ports),
                    "to": sorted(cfg.tagged_ports),
                }
            if sorted(cfg.untagged_ports) != sorted(entry.untagged_ports):
                diffs["untagged_ports"] = {
                    "from": sorted(entry.untagged_ports),
                    "to": sorted(cfg.untagged_ports),
                }

        if diffs:
            updates.append(
                Change(
                    kind="vlan_update",
                    key=f"vlan:{vid}",
                    details={"vlan_id": vid, **diffs},
                )
            )

    # ------------------------------------------------------------------ Ports
    for pid in sorted(desired.ports):
        cfg_p = desired.ports[pid]
        cur_p = current.ports.get(pid)
        if cur_p is None:
            continue

        field_diffs: dict[str, Any] = {}

        if cfg_p.admin_up is not None and cfg_p.admin_up != cur_p.admin_up:
            if not cfg_p.admin_up and safety_port_id is not None and pid == safety_port_id:
                warnings.warn(
                    f"Refusing to disable safety port {pid}; skipping admin_up change.",
                    stacklevel=2,
                )
            else:
                field_diffs["admin_up"] = {"from": cur_p.admin_up, "to": cfg_p.admin_up}

        if cfg_p.speed_duplex is not None and cfg_p.speed_duplex != cur_p.speed_duplex:
            field_diffs["speed_duplex"] = {
                "from": cur_p.speed_duplex,
                "to": cfg_p.speed_duplex,
            }

        if cfg_p.flow_control is not None and cfg_p.flow_control != cur_p.flow_control:
            field_diffs["flow_control"] = {
                "from": cur_p.flow_control,
                "to": cfg_p.flow_control,
            }

        if field_diffs:
            port_changes.append(
                Change(
                    kind="port_update",
                    key=f"port:{pid}",
                    details={"port_id": pid, **field_diffs},
                )
            )

    # ---------------------------------------------------------------- Deletes
    if allow_vlan_delete:
        for vid in sorted(current.vlans, reverse=True):
            if vid == 1:
                continue
            if vid not in desired.vlans:
                deletes.append(
                    Change(
                        kind="vlan_delete",
                        key=f"vlan:{vid}",
                        details={"vlan_id": vid},
                    )
                )
    else:
        extra = sorted(v for v in current.vlans if v not in desired.vlans and v != 1)
        if extra:
            warnings.warn(
                f"VLANs {extra} exist on the device but are absent from the desired config; "
                "pass allow_vlan_delete=True to remove them.",
                stacklevel=2,
            )

    all_changes = creates + updates + port_changes + deletes
    summary: dict[str, int] = {
        "vlan_create": len(creates),
        "vlan_update": len(updates),
        "port_update": len(port_changes),
        "vlan_delete": len(deletes),
    }
    return DevicePlan(changes=all_changes, summary=summary)
