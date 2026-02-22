"""VLAN change-set planner.

Compares a *current* VLAN state (as returned by :meth:`JTComDriver.get_vlans`
after parsing) against a *desired* incremental-change state and produces a
:class:`VlanChangeSet` describing what needs to be created, updated or deleted.

Each entry in *desired* carries a ``state`` field:

- ``"present"`` — create or update the VLAN to match the given attributes.
- ``"absent"`` — delete the VLAN if it exists (VLAN 1 is never deleted).

VLANs not mentioned in *desired* are left untouched.
"""

from __future__ import annotations

from napalm_jtcom.model.vlan import VlanChangeSet, VlanConfig, VlanEntry


def plan_vlan_changes(
    current: dict[int, VlanEntry],
    desired: dict[int, VlanConfig],
) -> VlanChangeSet:
    """Compute the minimal set of changes needed from the explicit *desired* entries.

    Only VLANs listed in *desired* are considered; unlisted VLANs are never
    touched.  The ``state`` field on each :class:`VlanConfig` controls intent:

    - ``state="present"`` + not in *current* → create.
    - ``state="present"`` + in *current* + name or membership differs → update.
    - ``state="absent"`` + in *current* + ``vlan_id != 1`` → delete.
    - ``state="absent"`` + not in *current* → no-op.

    Args:
        current: Mapping of VLAN ID → :class:`VlanEntry` (current switch state).
        desired: Mapping of VLAN ID → :class:`VlanConfig` (incremental changes).

    Returns:
        A :class:`VlanChangeSet` with ``create`` and ``update`` sorted ascending
        by VID and ``delete`` sorted ascending by VID.
    """
    creates: list[VlanConfig] = []
    updates: list[VlanConfig] = []
    deletes: list[int] = []

    for vid in sorted(desired):
        cfg = desired[vid]

        if cfg.state == "absent":
            if vid in current and vid != 1:
                deletes.append(vid)
            continue

        # state == "present"
        if vid not in current:
            creates.append(cfg)
        else:
            entry = current[vid]
            name_changed = cfg.name is not None and cfg.name != entry.name

            current_untagged_idx = _port_names_to_indices(set(entry.untagged_ports))
            current_tagged_idx = _port_names_to_indices(set(entry.tagged_ports))
            membership_changed = (
                set(cfg.untagged_ports) != current_untagged_idx
                or set(cfg.tagged_ports) != current_tagged_idx
            )

            if name_changed or membership_changed:
                updates.append(cfg)

    return VlanChangeSet(create=creates, update=updates, delete=deletes)


def _port_names_to_indices(names: set[str]) -> set[int]:
    """Convert a set of ``"Port N"`` strings to 0-based integer indices."""
    indices: set[int] = set()
    for name in names:
        parts = name.rsplit(" ", 1)
        if len(parts) == 2 and parts[1].isdigit():
            indices.add(int(parts[1]) - 1)
    return indices
