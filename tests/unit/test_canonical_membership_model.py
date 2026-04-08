"""Unit tests for canonical VLAN membership semantics and JTCom conversions."""

from __future__ import annotations

import pytest

from napalm_jtcom.utils.vlan_membership import (
    canonical_membership_for_vlan,
    canonical_to_jtcom_port_vlan_state,
    jtcom_to_canonical_port_vlan_state,
    make_port_state,
    validate_canonical_port_state,
)


def test_canonical_to_jtcom_access() -> None:
    backend = canonical_to_jtcom_port_vlan_state(make_port_state(untagged_vlan=10))
    assert backend == {
        "mode": "access",
        "access_vlan": 10,
        "native_vlan": None,
        "permit_vlans": [],
    }


def test_canonical_to_jtcom_trunk() -> None:
    backend = canonical_to_jtcom_port_vlan_state(
        make_port_state(untagged_vlan=1, tagged_vlans={61})
    )
    assert backend == {
        "mode": "trunk",
        "access_vlan": None,
        "native_vlan": 1,
        "permit_vlans": [1, 61],
    }


def test_jtcom_to_canonical_access() -> None:
    canonical = jtcom_to_canonical_port_vlan_state(
        {
            "mode": "access",
            "access_vlan": 10,
            "native_vlan": None,
            "permit_vlans": [],
        }
    )
    assert canonical == make_port_state(untagged_vlan=10)


def test_jtcom_to_canonical_trunk() -> None:
    canonical = jtcom_to_canonical_port_vlan_state(
        {
            "mode": "trunk",
            "access_vlan": None,
            "native_vlan": 1,
            "permit_vlans": [1, 61],
        }
    )
    assert canonical == make_port_state(untagged_vlan=1, tagged_vlans={61})


def test_round_trip_trunk_preserves_canonical_semantics() -> None:
    canonical = make_port_state(untagged_vlan=10, tagged_vlans={20, 30})
    round_trip = jtcom_to_canonical_port_vlan_state(
        canonical_to_jtcom_port_vlan_state(canonical)
    )
    assert round_trip == canonical


def test_invalid_jtcom_trunk_requires_native_vlan_in_permit_list() -> None:
    with pytest.raises(ValueError, match="native_vlan=10"):
        jtcom_to_canonical_port_vlan_state(
            {
                "mode": "trunk",
                "access_vlan": None,
                "native_vlan": 10,
                "permit_vlans": [20, 30],
            }
        )


def test_tagged_only_canonical_state_is_not_supported_for_jtcom_conversion() -> None:
    with pytest.raises(ValueError, match="tagged-only canonical VLAN state"):
        canonical_to_jtcom_port_vlan_state(make_port_state(tagged_vlans={20}))


def test_empty_canonical_state_is_not_supported_for_jtcom_conversion() -> None:
    with pytest.raises(ValueError, match="requires at least one canonical VLAN membership"):
        canonical_to_jtcom_port_vlan_state(make_port_state())


def test_canonical_invariant_rejects_same_vlan_as_tagged_and_untagged() -> None:
    with pytest.raises(ValueError, match="cannot be both untagged and tagged"):
        make_port_state(untagged_vlan=10, tagged_vlans={10, 20})


def test_canonical_membership_for_vlan_reports_absent_untagged_and_tagged() -> None:
    state = make_port_state(untagged_vlan=10, tagged_vlans={20, 30})
    assert canonical_membership_for_vlan(state, 10) == "untagged"
    assert canonical_membership_for_vlan(state, 20) == "tagged"
    assert canonical_membership_for_vlan(state, 99) == "absent"


def test_validate_canonical_port_state_accepts_valid_state() -> None:
    validate_canonical_port_state(make_port_state(untagged_vlan=10, tagged_vlans={20}))
