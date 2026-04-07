"""Unit tests for the pure VLAN membership apply engine."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
from unittest.mock import MagicMock

import pytest

from napalm_jtcom.driver import JTComDriver
from napalm_jtcom.model.port import PortSettings
from napalm_jtcom.model.vlan import VlanConfig, VlanEntry
from napalm_jtcom.utils.vlan_membership import (
    VlanMembershipModeChangeError,
    VlanMembershipPlan,
    VlanMembershipUnsupportedModeError,
    build_current_per_port_from_vlans,
    build_desired_port_vlan,
    make_port_state,
    plan_vlan_membership_changes,
)


def test_tagged_add_merges() -> None:
    current = {5: make_port_state(tagged_vlans={10, 30})}
    plan = plan_vlan_membership_changes(current, [VlanConfig(vlan_id=20, tagged_add=[5])])
    assert plan.desired_per_port[5]["tagged_vlans"] == {10, 20, 30}


def test_tagged_remove_subtracts() -> None:
    current = {5: make_port_state(tagged_vlans={10, 20, 30})}
    plan = plan_vlan_membership_changes(current, [VlanConfig(vlan_id=20, tagged_remove=[5])])
    assert plan.desired_per_port[5]["tagged_vlans"] == {10, 30}


def test_tagged_set_replaces_vlan_dimension_only() -> None:
    current = {
        5: make_port_state(tagged_vlans={10, 20, 30}),
        6: make_port_state(tagged_vlans={40}),
    }
    plan = plan_vlan_membership_changes(
        current,
        [VlanConfig(vlan_id=40, tagged_set=[5])],
        check_mode=True,
    )
    assert plan.desired_per_port[5]["tagged_vlans"] == {10, 20, 30, 40}
    assert plan.desired_per_port[6]["tagged_vlans"] == set()


def test_untagged_add_assigns_native_vlan() -> None:
    current = {3: make_port_state(untagged_vlan=10)}
    plan = plan_vlan_membership_changes(current, [VlanConfig(vlan_id=20, untagged_add=[3])])
    assert plan.desired_per_port[3]["untagged_vlan"] == 20


def test_untagged_remove_clears_native_if_matching() -> None:
    current = {3: make_port_state(untagged_vlan=20)}
    plan = plan_vlan_membership_changes(
        current,
        [VlanConfig(vlan_id=20, untagged_remove=[3])],
        check_mode=True,
    )
    assert plan.desired_per_port[3]["untagged_vlan"] is None


def test_tagged_untagged_same_vlan_is_auto_normalized() -> None:
    current = {3: make_port_state(tagged_vlans={20})}
    plan = plan_vlan_membership_changes(
        current,
        [VlanConfig(vlan_id=20, untagged_add=[3])],
        allow_port_mode_change=True,
    )
    assert plan.desired_per_port[3]["untagged_vlan"] == 20
    assert plan.desired_per_port[3]["tagged_vlans"] == set()


def test_access_to_trunk_fails_by_default() -> None:
    current = {3: make_port_state(untagged_vlan=20)}
    with pytest.raises(VlanMembershipModeChangeError) as exc_info:
        plan_vlan_membership_changes(current, [VlanConfig(vlan_id=30, tagged_add=[3])])
    assert exc_info.value.warnings[0]["port_id"] == 3
    assert exc_info.value.warnings[0]["current_mode"] == "access"
    assert exc_info.value.warnings[0]["desired_mode"] == "trunk"
    assert "allow_port_mode_change=true" in str(exc_info.value)


def test_trunk_to_access_fails_by_default() -> None:
    current = {5: make_port_state(untagged_vlan=10, tagged_vlans={20, 30})}
    desired = [
        VlanConfig(vlan_id=20, tagged_remove=[5]),
        VlanConfig(vlan_id=30, tagged_remove=[5]),
    ]
    with pytest.raises(VlanMembershipModeChangeError) as exc_info:
        plan_vlan_membership_changes(current, desired)
    assert exc_info.value.warnings[0]["port_id"] == 5
    assert exc_info.value.warnings[0]["current_mode"] == "trunk"
    assert exc_info.value.warnings[0]["desired_mode"] == "access"


def test_access_to_trunk_allowed_with_flag() -> None:
    current = {3: make_port_state(untagged_vlan=20)}
    plan = plan_vlan_membership_changes(
        current,
        [VlanConfig(vlan_id=30, tagged_add=[3])],
        allow_port_mode_change=True,
    )
    assert plan.desired_per_port[3]["untagged_vlan"] == 20
    assert plan.desired_per_port[3]["tagged_vlans"] == {30}
    assert plan.warnings[0]["desired_mode"] == "trunk"


def test_check_mode_warns_instead_of_failing_on_mode_change() -> None:
    current = {3: make_port_state(untagged_vlan=20)}
    plan = plan_vlan_membership_changes(
        current,
        [VlanConfig(vlan_id=30, tagged_add=[3])],
        check_mode=True,
    )
    assert plan.warnings[0]["port_id"] == 3
    assert "allow_port_mode_change=true" in plan.warnings[0]["hint"]


def test_omitted_legacy_fields_are_noop_not_empty_replacement() -> None:
    current = {5: make_port_state(untagged_vlan=10, tagged_vlans={20, 30})}
    plan = plan_vlan_membership_changes(current, [VlanConfig(vlan_id=20)])
    assert plan.changed_ports == []
    assert plan.desired_per_port[5]["untagged_vlan"] == 10
    assert plan.desired_per_port[5]["tagged_vlans"] == {20, 30}


def test_trunk_intent_uses_full_final_permit_list_not_delta() -> None:
    per_port = {5: make_port_state(untagged_vlan=10, tagged_vlans={20, 30})}
    intent = build_desired_port_vlan(per_port)
    assert intent[5]["mode"] == "trunk"
    assert intent[5]["native_vlan"] == 10
    assert intent[5]["permit_vlans"] == [10, 20, 30]


def test_driver_apply_sends_full_permit_list_for_changed_port_only() -> None:
    driver = JTComDriver("192.0.2.1", "admin", "admin")
    session = MagicMock()
    plan = VlanMembershipPlan(
        current_per_port={4: make_port_state(), 5: make_port_state(tagged_vlans={20})},
        desired_per_port={
            4: make_port_state(),
            5: make_port_state(untagged_vlan=10, tagged_vlans={20, 30}),
        },
        desired_port_vlan={
            4: {"mode": "none", "native_vlan": None, "permit_vlans": []},
            5: {"mode": "trunk", "native_vlan": 10, "permit_vlans": [10, 20, 30]},
        },
        changed_ports=[5],
        changed_vlans=[10, 30],
        warnings=[],
    )

    driver._apply_vlan_membership_plan(session, plan)

    session.post.assert_called_once()
    endpoint = session.post.call_args.args[0]
    payload = session.post.call_args.kwargs["data"]
    assert endpoint == "/vlanport.cgi"
    assert payload["PortId"] == "5"
    assert payload["VlanType"] == "1"
    assert payload["NativeVlan"] == "10"
    assert payload["PermitVlan"] == "10_20_30"


def test_build_current_rejects_port_untagged_in_multiple_vlans() -> None:
    current_vlans = {
        10: VlanEntry(vlan_id=10, name="v10", untagged_ports=["Port 1"]),
        20: VlanEntry(vlan_id=20, name="v20", untagged_ports=["Port 1"]),
    }
    with pytest.raises(ValueError, match="Impossible VLAN state"):
        build_current_per_port_from_vlans(current_vlans, known_ports=[0])


def test_check_mode_warns_instead_of_failing_on_desired_mode_none() -> None:
    current = {3: make_port_state(untagged_vlan=20)}
    plan = plan_vlan_membership_changes(
        current,
        [VlanConfig(vlan_id=20, untagged_remove=[3])],
        check_mode=True,
    )
    assert plan.desired_port_vlan[3]["mode"] == "none"
    assert plan.warnings[0]["type"] == "unsupported_vlan_port_mode"
    assert plan.warnings[0]["port_id"] == 3
    assert "access/trunk" in plan.warnings[0]["hint"]


def test_apply_mode_fails_on_desired_mode_none() -> None:
    current = {3: make_port_state(untagged_vlan=20)}
    with pytest.raises(VlanMembershipUnsupportedModeError) as exc_info:
        plan_vlan_membership_changes(current, [VlanConfig(vlan_id=20, untagged_remove=[3])])
    assert exc_info.value.warnings[0]["port_id"] == 3
    assert "cannot be applied safely" in str(exc_info.value)


def test_set_vlans_mode_none_failure_happens_before_device_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = JTComDriver("192.0.2.1", "admin", "admin")
    session = MagicMock()
    driver._session = session
    current_vlans = {
        20: VlanEntry(vlan_id=20, name="v20", untagged_ports=["Port 4"]),
    }
    current_ports = [
        PortSettings(port_id=4, name="Port 4", admin_up=True),
    ]
    monkeypatch.setattr(
        driver,
        "_read_current_state",
        lambda _session: (current_vlans, current_ports),
    )

    with pytest.raises(VlanMembershipUnsupportedModeError):
        driver.set_vlans({20: VlanConfig(vlan_id=20, untagged_remove=[3])})

    session.post.assert_not_called()
    session.download_config_backup.assert_not_called()


@pytest.mark.parametrize(
    "path",
    [
        pathlib.Path("ansible/action_plugins/jtcom_config.py"),
        pathlib.Path("galaxy/bronweg/cgiswitch/plugins/action/jtcom_config.py"),
    ],
)
def test_action_plugin_int_list_helper_preserves_missing_none_and_empty_list(
    path: pathlib.Path,
) -> None:
    module = _load_action_plugin_module(path)

    assert module._int_list_or_none({}, "tagged_ports") is None
    assert module._int_list_or_none({"tagged_ports": None}, "tagged_ports") is None
    assert module._int_list_or_none({"tagged_ports": []}, "tagged_ports") == []
    assert module._int_list_or_none({"tagged_ports": ["1"]}, "tagged_ports") == [1]
    assert module._int_or_none({}, "access_vlan") is None
    assert module._int_or_none({"access_vlan": None}, "access_vlan") is None
    assert module._int_or_none({"access_vlan": "10"}, "access_vlan") == 10


def _load_action_plugin_module(path: pathlib.Path) -> types.ModuleType:
    class ActionBase:
        pass

    class Display:
        def display(self, _data: str) -> None:
            pass

    ansible_mod = types.ModuleType("ansible")
    plugins_mod = types.ModuleType("ansible.plugins")
    action_mod = types.ModuleType("ansible.plugins.action")
    action_mod.ActionBase = ActionBase
    utils_mod = types.ModuleType("ansible.utils")
    display_mod = types.ModuleType("ansible.utils.display")
    display_mod.Display = Display

    old_modules = {
        name: sys.modules.get(name)
        for name in (
            "ansible",
            "ansible.plugins",
            "ansible.plugins.action",
            "ansible.utils",
            "ansible.utils.display",
        )
    }
    sys.modules.update(
        {
            "ansible": ansible_mod,
            "ansible.plugins": plugins_mod,
            "ansible.plugins.action": action_mod,
            "ansible.utils": utils_mod,
            "ansible.utils.display": display_mod,
        }
    )
    try:
        spec = importlib.util.spec_from_file_location("jtcom_action_under_test", path)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, old_module in old_modules.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module
