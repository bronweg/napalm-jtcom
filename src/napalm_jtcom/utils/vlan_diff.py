"""VLAN change-set planner.

Compares a *current* VLAN state (as returned by :meth:`JTComDriver.get_vlans`
after parsing) against a *desired* declarative state and produces a
:class:`VlanChangeSet` describing what needs to be created, updated or deleted.
"""

from __future__ import annotations

import warnings

from napalm_jtcom.model.vlan import VlanChangeSet, VlanConfig, VlanEntry


def plan_vlan_changes(
    current: dict[int, VlanEntry],
    desired: dict[int, VlanConfig],
    *,
    allow_delete: bool = False,
    allow_membership: bool = False,
    allow_rename: bool = True,
    _warn_stacklevel: int = 2,
) -> VlanChangeSet:
    """Compute the minimal set of changes needed to reach *desired* from *current*.

    Args:
        current: Mapping of VLAN ID → :class:`VlanEntry` (current switch state).
        desired: Mapping of VLAN ID → :class:`VlanConfig` (target state).
        allow_delete: If ``True``, VLANs present in *current* but absent from
            *desired* are added to :attr:`VlanChangeSet.delete`.  VLAN 1 is
            **never** included regardless.
        allow_membership: If ``True``, port membership differences are included
            in update detection.
        allow_rename: If ``True``, VLAN name differences are included in update
            detection.

    Returns:
        A :class:`VlanChangeSet` with sorted (ascending VID) lists.
    """
    creates: list[VlanConfig] = []
    updates: list[VlanConfig] = []
    deletes: list[int] = []

    # --- Create: in desired but not in current ---
    for vid in sorted(desired):
        if vid not in current:
            creates.append(desired[vid])

    # --- Update: in both, with relevant differences ---
    for vid in sorted(desired):
        if vid not in current:
            continue
        cfg = desired[vid]
        entry = current[vid]
        name_changed = (
            allow_rename
            and cfg.name is not None
            and cfg.name != entry.name
        )
        membership_changed = False
        if allow_membership:
            current_untagged_names = set(entry.untagged_ports)
            current_tagged_names = set(entry.tagged_ports)
            # desired stores 0-based int IDs; current stores "Port N" strings
            # We compare port-index sets if membership is enabled
            desired_untagged = set(cfg.untagged_ports)
            desired_tagged = set(cfg.tagged_ports)
            # Convert current name sets to 0-based indices for comparison
            current_untagged_idx = _port_names_to_indices(current_untagged_names)
            current_tagged_idx = _port_names_to_indices(current_tagged_names)
            membership_changed = (
                desired_untagged != current_untagged_idx
                or desired_tagged != current_tagged_idx
            )
        if name_changed or membership_changed:
            updates.append(cfg)

    # --- Delete: in current but not in desired ---
    if allow_delete:
        for vid in sorted(current):
            if vid == 1:
                continue  # VLAN 1 is never deleted
            if vid not in desired:
                deletes.append(vid)
    else:
        extra_vids = sorted(v for v in current if v not in desired and v != 1)
        if extra_vids:
            warnings.warn(
                f"VLANs {extra_vids} exist on switch but are not in desired state; "
                "pass allow_delete=True to remove them.",
                stacklevel=_warn_stacklevel,
            )

    return VlanChangeSet(create=creates, update=updates, delete=deletes)


def _port_names_to_indices(names: set[str]) -> set[int]:
    """Convert a set of ``"Port N"`` strings to 0-based integer indices."""
    indices: set[int] = set()
    for name in names:
        parts = name.rsplit(" ", 1)
        if len(parts) == 2 and parts[1].isdigit():
            indices.add(int(parts[1]) - 1)
    return indices
