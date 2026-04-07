"""VLAN membership apply engine.

This module keeps the runtime VLAN membership logic independent from the CGI
write path.  It works with 0-based port IDs because that is the convention used
by JTCom VLAN payloads and :class:`napalm_jtcom.model.vlan.VlanConfig`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from napalm_jtcom.model.vlan import VlanConfig, VlanEntry

PortMode = Literal["access", "trunk", "none"]
PortMembershipState = dict[str, int | set[int] | None]
PortMembershipMap = dict[int, PortMembershipState]


class PortVlanIntent(TypedDict):
    """Full device-level VLAN intent for one 0-based port."""

    mode: PortMode
    native_vlan: int | None
    permit_vlans: list[int]

_MODE_CHANGE_HINT = "Set allow_port_mode_change=true to allow this access/trunk transition."


class VlanMembershipModeChangeError(ValueError):
    """Raised when a dangerous access/trunk mode change is blocked."""

    def __init__(self, warnings: list[dict[str, Any]]) -> None:
        self.warnings = warnings
        details = "; ".join(
            (
                f"port_id={w['port_id']} current_mode={w['current_mode']} "
                f"desired_mode={w['desired_mode']}"
            )
            for w in warnings
        )
        super().__init__(f"VLAN port mode change blocked: {details}. {_MODE_CHANGE_HINT}")


@dataclass
class VlanMembershipPlan:
    """Computed VLAN membership plan."""

    current_per_port: PortMembershipMap
    desired_per_port: PortMembershipMap
    desired_port_vlan: dict[int, PortVlanIntent]
    changed_ports: list[int]
    changed_vlans: list[int]
    warnings: list[dict[str, Any]]


def make_port_state(
    untagged_vlan: int | None = None,
    tagged_vlans: Iterable[int] | None = None,
) -> PortMembershipState:
    """Return one canonical per-port membership state."""
    return {
        "untagged_vlan": untagged_vlan,
        "tagged_vlans": set(tagged_vlans or ()),
    }


def build_current_per_port_from_vlans(
    vlans: dict[int, VlanEntry],
    known_ports: Iterable[int],
) -> PortMembershipMap:
    """Build canonical current membership from VLAN-centric parsed state.

    Args:
        vlans: Current VLAN entries, including tagged/untagged port names.
        known_ports: Known 0-based port IDs.  Every listed port is initialized
            even if it has no membership in *vlans*.

    Raises:
        ValueError: If a port name is unparseable or a port is untagged in more
            than one VLAN.
    """
    current: PortMembershipMap = {port_id: make_port_state() for port_id in known_ports}

    for vlan_id, entry in sorted(vlans.items()):
        for port_name in entry.untagged_ports:
            port_id = _port_name_to_index(port_name)
            if port_id is None:
                raise ValueError(
                    f"Cannot parse untagged port name {port_name!r} in VLAN {vlan_id}"
                )
            current.setdefault(port_id, make_port_state())
            state = current[port_id]
            existing = _untagged_vlan(state)
            if existing is not None and existing != vlan_id:
                raise ValueError(
                    f"Impossible VLAN state: port_id={port_id} is untagged in "
                    f"both VLAN {existing} and VLAN {vlan_id}"
                )
            state["untagged_vlan"] = vlan_id

        for port_name in entry.tagged_ports:
            port_id = _port_name_to_index(port_name)
            if port_id is None:
                raise ValueError(f"Cannot parse tagged port name {port_name!r} in VLAN {vlan_id}")
            current.setdefault(port_id, make_port_state())
            _tagged_vlans(current[port_id]).add(vlan_id)

    return current


def plan_vlan_membership_changes(
    current_per_port: PortMembershipMap,
    vlan_configs: Iterable[VlanConfig],
    *,
    allow_port_mode_change: bool = False,
    check_mode: bool = False,
) -> VlanMembershipPlan:
    """Apply VLAN membership operations in memory and produce a device intent.

    The engine starts from *current_per_port*, applies every present
    :class:`VlanConfig` operation via ``normalized_membership()``, and never
    talks to the device during planning.
    """
    current = copy_membership_map(current_per_port)
    desired = copy_membership_map(current_per_port)

    for cfg in sorted(vlan_configs, key=lambda item: item.vlan_id):
        if cfg.state != "present":
            continue
        _apply_vlan_config(desired, cfg)

    normalize_tagged_untagged_consistency(desired)
    warnings = detect_mode_change_warnings(current, desired)
    if warnings and not allow_port_mode_change and not check_mode:
        raise VlanMembershipModeChangeError(warnings)

    return VlanMembershipPlan(
        current_per_port=current,
        desired_per_port=desired,
        desired_port_vlan=build_desired_port_vlan(desired),
        changed_ports=changed_ports(current, desired),
        changed_vlans=changed_vlans(current, desired),
        warnings=warnings,
    )


def copy_membership_map(source: PortMembershipMap) -> PortMembershipMap:
    """Deep-copy a canonical membership map."""
    return {
        port_id: make_port_state(_untagged_vlan(state), _tagged_vlans(state))
        for port_id, state in sorted(source.items())
    }


def normalize_tagged_untagged_consistency(per_port: PortMembershipMap) -> None:
    """Ensure a port never carries the same VLAN tagged and untagged."""
    for state in per_port.values():
        untagged = _untagged_vlan(state)
        if untagged is not None:
            _tagged_vlans(state).discard(untagged)


def classify_port_mode(port_state: PortMembershipState) -> PortMode:
    """Classify a canonical per-port membership state."""
    if _tagged_vlans(port_state):
        return "trunk"
    if _untagged_vlan(port_state) is not None:
        return "access"
    return "none"


def detect_mode_change_warnings(
    current_per_port: PortMembershipMap,
    desired_per_port: PortMembershipMap,
) -> list[dict[str, Any]]:
    """Return dangerous access↔trunk transitions."""
    warnings: list[dict[str, Any]] = []
    for port_id in sorted(set(current_per_port) | set(desired_per_port)):
        current_state = current_per_port.get(port_id, make_port_state())
        desired_state = desired_per_port.get(port_id, make_port_state())
        current_mode = classify_port_mode(current_state)
        desired_mode = classify_port_mode(desired_state)
        if (current_mode, desired_mode) in {("access", "trunk"), ("trunk", "access")}:
            warnings.append(
                {
                    "port_id": port_id,
                    "current_mode": current_mode,
                    "desired_mode": desired_mode,
                    "hint": _MODE_CHANGE_HINT,
                }
            )
    return warnings


def build_desired_port_vlan(per_port: PortMembershipMap) -> dict[int, PortVlanIntent]:
    """Build full device-level per-port VLAN intent."""
    intent: dict[int, PortVlanIntent] = {}
    for port_id, state in sorted(per_port.items()):
        mode = classify_port_mode(state)
        native_vlan = _untagged_vlan(state)
        tagged = _tagged_vlans(state)
        if mode == "trunk":
            permit = set(tagged)
            if native_vlan is not None:
                permit.add(native_vlan)
            permit_vlans = sorted(permit)
        elif mode == "access":
            permit_vlans = [native_vlan] if native_vlan is not None else []
        else:
            permit_vlans = []

        intent[port_id] = {
            "mode": mode,
            "native_vlan": native_vlan,
            "permit_vlans": permit_vlans,
        }
    return intent


def changed_ports(
    current_per_port: PortMembershipMap,
    desired_per_port: PortMembershipMap,
) -> list[int]:
    """Return 0-based ports whose membership changed."""
    ports: list[int] = []
    for port_id in sorted(set(current_per_port) | set(desired_per_port)):
        if not _same_state(
            current_per_port.get(port_id, make_port_state()),
            desired_per_port.get(port_id, make_port_state()),
        ):
            ports.append(port_id)
    return ports


def changed_vlans(
    current_per_port: PortMembershipMap,
    desired_per_port: PortMembershipMap,
) -> list[int]:
    """Return VLAN IDs touched by a membership diff."""
    vlans: set[int] = set()
    for port_id in sorted(set(current_per_port) | set(desired_per_port)):
        current_state = current_per_port.get(port_id, make_port_state())
        desired_state = desired_per_port.get(port_id, make_port_state())
        vlans.update(_tagged_vlans(current_state) ^ _tagged_vlans(desired_state))
        cur_untagged = _untagged_vlan(current_state)
        des_untagged = _untagged_vlan(desired_state)
        if cur_untagged != des_untagged:
            if cur_untagged is not None:
                vlans.add(cur_untagged)
            if des_untagged is not None:
                vlans.add(des_untagged)
    return sorted(vlans)


def serialize_membership_map(per_port: PortMembershipMap) -> dict[int, dict[str, Any]]:
    """Return a JSON-friendly representation of a membership map."""
    return {
        port_id: {
            "untagged_vlan": _untagged_vlan(state),
            "tagged_vlans": sorted(_tagged_vlans(state)),
        }
        for port_id, state in sorted(per_port.items())
    }


def diff_membership_maps(
    current_per_port: PortMembershipMap,
    desired_per_port: PortMembershipMap,
) -> dict[str, Any]:
    """Return a JSON-friendly per-port membership diff."""
    diffs: dict[str, Any] = {}
    for port_id in changed_ports(current_per_port, desired_per_port):
        current_state = current_per_port.get(port_id, make_port_state())
        desired_state = desired_per_port.get(port_id, make_port_state())
        diffs[str(port_id)] = {
            "from": {
                "untagged_vlan": _untagged_vlan(current_state),
                "tagged_vlans": sorted(_tagged_vlans(current_state)),
            },
            "to": {
                "untagged_vlan": _untagged_vlan(desired_state),
                "tagged_vlans": sorted(_tagged_vlans(desired_state)),
            },
        }
    return diffs


def _apply_vlan_config(desired_per_port: PortMembershipMap, cfg: VlanConfig) -> None:
    membership = cfg.normalized_membership()
    tagged = membership["tagged"]
    untagged = membership["untagged"]

    tagged_set = tagged["set"]
    if tagged_set is not None:
        for state in desired_per_port.values():
            _tagged_vlans(state).discard(cfg.vlan_id)
        for port_id in tagged_set:
            _require_known_port(desired_per_port, port_id)
            _tagged_vlans(desired_per_port[port_id]).add(cfg.vlan_id)
    else:
        for port_id in tagged["add"] or set():
            _require_known_port(desired_per_port, port_id)
            _tagged_vlans(desired_per_port[port_id]).add(cfg.vlan_id)
        for port_id in tagged["remove"] or set():
            _require_known_port(desired_per_port, port_id)
            _tagged_vlans(desired_per_port[port_id]).discard(cfg.vlan_id)

    untagged_set = untagged["set"]
    if untagged_set is not None:
        for state in desired_per_port.values():
            if _untagged_vlan(state) == cfg.vlan_id:
                state["untagged_vlan"] = None
        for port_id in untagged_set:
            _require_known_port(desired_per_port, port_id)
            desired_per_port[port_id]["untagged_vlan"] = cfg.vlan_id
    else:
        for port_id in untagged["add"] or set():
            _require_known_port(desired_per_port, port_id)
            desired_per_port[port_id]["untagged_vlan"] = cfg.vlan_id
        for port_id in untagged["remove"] or set():
            _require_known_port(desired_per_port, port_id)
            if _untagged_vlan(desired_per_port[port_id]) == cfg.vlan_id:
                desired_per_port[port_id]["untagged_vlan"] = None


def _same_state(left: PortMembershipState, right: PortMembershipState) -> bool:
    return _untagged_vlan(left) == _untagged_vlan(right) and _tagged_vlans(
        left
    ) == _tagged_vlans(right)


def _require_known_port(per_port: PortMembershipMap, port_id: int) -> None:
    if port_id not in per_port:
        raise ValueError(f"Unknown VLAN membership port_id={port_id}")


def _untagged_vlan(state: PortMembershipState) -> int | None:
    value = state["untagged_vlan"]
    if value is not None and not isinstance(value, int):
        raise TypeError(f"untagged_vlan must be int or None, got {type(value)!r}")
    return value


def _tagged_vlans(state: PortMembershipState) -> set[int]:
    value = state["tagged_vlans"]
    if not isinstance(value, set):
        raise TypeError(f"tagged_vlans must be set[int], got {type(value)!r}")
    return value


def _port_name_to_index(name: str) -> int | None:
    parts = name.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return int(parts[1]) - 1
    return None
