"""Normalization helpers for device configuration models.

Normalization produces a stable, canonical form suitable for reliable diff
comparisons: sorted port lists, no duplicates, canonical speed/duplex tokens.
"""

from __future__ import annotations

from dataclasses import replace

from napalm_jtcom.model.config import DeviceConfig
from napalm_jtcom.model.port import PortConfig
from napalm_jtcom.model.vlan import VlanConfig
from napalm_jtcom.vendor.jtcom.mappings import SPEED_DUPLEX_ALIASES, SPEED_DUPLEX_CANONICAL


def normalize_vlan_config(cfg: VlanConfig) -> VlanConfig:
    """Return a normalized copy of *cfg*.

    Normalization rules:

    - Deduplicate and sort ``tagged_ports`` and ``untagged_ports``.
    - Remove any port that appears in both lists (prefer untagged over tagged).
    """
    tagged = sorted(set(cfg.tagged_ports))
    untagged = sorted(set(cfg.untagged_ports))
    untagged_set = set(untagged)
    tagged = [p for p in tagged if p not in untagged_set]
    return replace(cfg, tagged_ports=tagged, untagged_ports=untagged)


def normalize_port_config(cfg: PortConfig) -> PortConfig:
    """Return a normalized copy of *cfg*.

    Normalization rules:

    - Canonicalize ``speed_duplex`` via
      :data:`~napalm_jtcom.vendor.jtcom.mappings.SPEED_DUPLEX_ALIASES`.
    - Unknown tokens are left unchanged.
    - ``None`` speed_duplex is left unchanged.
    """
    if cfg.speed_duplex is None:
        return cfg
    if cfg.speed_duplex in SPEED_DUPLEX_CANONICAL:
        return cfg
    canonical = SPEED_DUPLEX_ALIASES.get(cfg.speed_duplex.lower())
    if canonical is not None:
        return replace(cfg, speed_duplex=canonical)
    return cfg


def normalize_device_config(cfg: DeviceConfig) -> DeviceConfig:
    """Return a fully normalized copy of *cfg*.

    Applies :func:`normalize_vlan_config` to each VLAN and
    :func:`normalize_port_config` to each port.  Both dicts are rebuilt
    with keys sorted ascending.
    """
    vlans = {vid: normalize_vlan_config(v) for vid, v in sorted(cfg.vlans.items())}
    ports = {pid: normalize_port_config(p) for pid, p in sorted(cfg.ports.items())}
    return DeviceConfig(vlans=vlans, ports=ports, metadata=dict(cfg.metadata))
