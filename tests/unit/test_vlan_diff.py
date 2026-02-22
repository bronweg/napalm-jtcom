"""Unit tests for napalm_jtcom.utils.vlan_diff.plan_vlan_changes."""

from __future__ import annotations

import warnings

from napalm_jtcom.model.vlan import VlanChangeSet, VlanConfig, VlanEntry
from napalm_jtcom.utils.vlan_diff import plan_vlan_changes

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_entry(vid: int, name: str = "", **kwargs: object) -> VlanEntry:
    return VlanEntry(vlan_id=vid, name=name, **kwargs)  # type: ignore[arg-type]


def make_cfg(vid: int, name: str | None = None, **kwargs: object) -> VlanConfig:
    return VlanConfig(vlan_id=vid, name=name, **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class TestCreate:
    def test_new_vlan_appears_in_create(self) -> None:
        current = {1: make_entry(1), 10: make_entry(10, "Management")}
        desired = {1: make_cfg(1), 10: make_cfg(10), 20: make_cfg(20, "Dev")}
        cs = plan_vlan_changes(current, desired)
        assert [c.vlan_id for c in cs.create] == [20]

    def test_multiple_new_vlans_sorted_ascending(self) -> None:
        current = {1: make_entry(1)}
        desired = {1: make_cfg(1), 30: make_cfg(30), 20: make_cfg(20)}
        cs = plan_vlan_changes(current, desired)
        assert [c.vlan_id for c in cs.create] == [20, 30]

    def test_no_creates_when_already_present(self) -> None:
        current = {1: make_entry(1), 10: make_entry(10)}
        desired = {1: make_cfg(1), 10: make_cfg(10)}
        cs = plan_vlan_changes(current, desired)
        assert cs.create == []


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestDelete:
    def test_no_delete_when_allow_delete_false(self) -> None:
        current = {1: make_entry(1), 10: make_entry(10), 20: make_entry(20)}
        desired = {1: make_cfg(1), 10: make_cfg(10)}
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            cs = plan_vlan_changes(current, desired, allow_delete=False)
        assert cs.delete == []

    def test_delete_when_allowed(self) -> None:
        current = {1: make_entry(1), 10: make_entry(10), 20: make_entry(20)}
        desired = {1: make_cfg(1), 10: make_cfg(10)}
        cs = plan_vlan_changes(current, desired, allow_delete=True)
        assert cs.delete == [20]

    def test_vlan1_never_deleted(self) -> None:
        current = {1: make_entry(1), 10: make_entry(10)}
        desired = {10: make_cfg(10)}
        cs = plan_vlan_changes(current, desired, allow_delete=True)
        assert 1 not in cs.delete

    def test_multiple_deletes_sorted_ascending(self) -> None:
        current = {1: make_entry(1), 10: make_entry(10), 20: make_entry(20), 30: make_entry(30)}
        desired = {1: make_cfg(1)}
        cs = plan_vlan_changes(current, desired, allow_delete=True)
        assert cs.delete == [10, 20, 30]

    def test_warning_emitted_when_extra_vlans_and_no_allow_delete(self) -> None:
        current = {1: make_entry(1), 99: make_entry(99)}
        desired = {1: make_cfg(1)}
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            plan_vlan_changes(current, desired, allow_delete=False)
        assert len(w) == 1
        assert "allow_delete=True" in str(w[0].message)

    def test_no_warning_when_all_desired_match_current(self) -> None:
        current = {1: make_entry(1), 10: make_entry(10)}
        desired = {1: make_cfg(1), 10: make_cfg(10)}
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            plan_vlan_changes(current, desired, allow_delete=False)
        assert len(w) == 0


# ---------------------------------------------------------------------------
# Update — name changes
# ---------------------------------------------------------------------------

class TestUpdateName:
    def test_rename_detected_when_allow_rename_true(self) -> None:
        current = {10: make_entry(10, "OldName")}
        desired = {10: make_cfg(10, "NewName")}
        cs = plan_vlan_changes(current, desired, allow_rename=True)
        assert [u.vlan_id for u in cs.update] == [10]

    def test_rename_skipped_when_allow_rename_false(self) -> None:
        current = {10: make_entry(10, "OldName")}
        desired = {10: make_cfg(10, "NewName")}
        cs = plan_vlan_changes(current, desired, allow_rename=False)
        assert cs.update == []

    def test_none_name_does_not_trigger_rename(self) -> None:
        current = {10: make_entry(10, "Existing")}
        desired = {10: make_cfg(10, None)}  # name=None means "do not change"
        cs = plan_vlan_changes(current, desired, allow_rename=True)
        assert cs.update == []

    def test_empty_string_name_triggers_rename(self) -> None:
        current = {10: make_entry(10, "Existing")}
        desired = {10: make_cfg(10, "")}
        cs = plan_vlan_changes(current, desired, allow_rename=True)
        assert [u.vlan_id for u in cs.update] == [10]


# ---------------------------------------------------------------------------
# Update — membership changes
# ---------------------------------------------------------------------------

class TestUpdateMembership:
    def test_membership_change_detected_when_allowed(self) -> None:
        current = {10: make_entry(10, untagged_ports=["Port 1"])}
        # desired: port 0 untagged (Port 1 = index 0) — no change → port 1 (Port 2) added
        desired = {10: make_cfg(10, untagged_ports=[0, 1])}
        cs = plan_vlan_changes(current, desired, allow_membership=True)
        assert [u.vlan_id for u in cs.update] == [10]

    def test_membership_same_not_flagged(self) -> None:
        current = {10: make_entry(10, untagged_ports=["Port 1"])}
        desired = {10: make_cfg(10, untagged_ports=[0])}  # Port 1 = index 0
        cs = plan_vlan_changes(current, desired, allow_membership=True)
        assert cs.update == []

    def test_membership_ignored_when_not_allowed(self) -> None:
        current = {10: make_entry(10, untagged_ports=["Port 1"])}
        desired = {10: make_cfg(10, untagged_ports=[0, 1, 2])}
        cs = plan_vlan_changes(current, desired, allow_membership=False)
        assert cs.update == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_current_empty_desired(self) -> None:
        cs = plan_vlan_changes({}, {})
        assert cs == VlanChangeSet()

    def test_empty_desired_only_deletes_non_vlan1_when_allowed(self) -> None:
        current = {1: make_entry(1), 10: make_entry(10)}
        cs = plan_vlan_changes(current, {}, allow_delete=True)
        assert cs.create == []
        assert cs.update == []
        assert cs.delete == [10]

    def test_result_is_deterministic(self) -> None:
        import random
        vids = list(range(2, 20))
        random.shuffle(vids)
        current = {v: make_entry(v) for v in vids}
        current[1] = make_entry(1)
        desired = {1: make_cfg(1)}
        cs1 = plan_vlan_changes(current, desired, allow_delete=True)
        cs2 = plan_vlan_changes(current, desired, allow_delete=True)
        assert cs1.delete == cs2.delete == sorted(vids)
