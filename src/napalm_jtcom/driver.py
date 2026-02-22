"""JTCom NAPALM driver — top-level NetworkDriver implementation."""

from __future__ import annotations

import datetime
import logging
import pathlib
from typing import Any

from napalm.base.base import NetworkDriver

from napalm_jtcom.client.errors import JTComError, JTComVerificationError
from napalm_jtcom.client.port_ops import apply_port_changes
from napalm_jtcom.client.session import JTComCredentials, JTComSession
from napalm_jtcom.client.vlan_ops import vlan_create, vlan_delete, vlan_set_port
from napalm_jtcom.model.config import DeviceConfig
from napalm_jtcom.model.port import PortChangeSet, PortConfig, PortSettings
from napalm_jtcom.model.vlan import VlanConfig, VlanEntry
from napalm_jtcom.parser.device import parse_device_info, parse_uptime_seconds
from napalm_jtcom.parser.port import parse_port_page
from napalm_jtcom.parser.vlan import parse_port_vlan_settings, parse_static_vlans
from napalm_jtcom.utils.device_diff import build_device_plan
from napalm_jtcom.utils.normalize import normalize_device_config
from napalm_jtcom.utils.port_diff import plan_port_changes
from napalm_jtcom.utils.render import render_diff
from napalm_jtcom.utils.vlan_diff import plan_vlan_changes
from napalm_jtcom.vendor.jtcom.endpoints import (
    DEVICE_INFO,
    PORT_SETTINGS,
    VLAN_PORT_BASED,
    VLAN_STATIC,
)

logger = logging.getLogger(__name__)

_VENDOR: str = "JTCom"


class JTComDriver(NetworkDriver):  # type: ignore[misc]
    """NAPALM driver for JTCom CGI-based Ethernet switches.

    Communicates with the switch via its HTTP CGI web interface.
    HTML responses are parsed with BeautifulSoup to extract structured data.

    Args:
        hostname: IP address or hostname of the switch, optionally including
            the URL scheme (e.g. ``http://192.168.1.1``).
        username: Login username.
        password: Login password.
        timeout: Default request timeout in seconds.
        optional_args: Optional driver configuration overrides.
            Supported keys:

            - ``port`` (int): HTTP port (default 80; 443 when verify_tls=True).
            - ``verify_tls`` (bool): Verify TLS certificates (default ``False``).
    """

    def __init__(
        self,
        hostname: str,
        username: str,
        password: str,
        timeout: int = 60,
        optional_args: dict[str, Any] | None = None,
    ) -> None:
        self.hostname = hostname
        self.username = username
        self.password = password
        self.timeout = timeout
        self.optional_args: dict[str, Any] = optional_args or {}

        self._verify_tls: bool = bool(self.optional_args.get("verify_tls", False))
        self._port: int = int(
            self.optional_args.get(
                "port",
                443 if self._verify_tls else 80,
            )
        )
        self._session: JTComSession | None = None

        logger.debug(
            "JTComDriver initialised: host=%s port=%d user=%s",
            self.hostname,
            self._port,
            self.username,
        )

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Open an HTTP session and authenticate with the switch.

        Raises:
            JTComAuthError: If login is rejected by the switch.
        """
        base_url = self._build_base_url()
        logger.info("Opening connection to %s", base_url)
        creds = JTComCredentials(username=self.username, password=self.password)
        self._session = JTComSession(
            base_url=base_url,
            credentials=creds,
            timeout_s=float(self.timeout),
            verify_tls=self._verify_tls,
        )
        self._session.login()

    def close(self) -> None:
        """Logout and close the HTTP session (best-effort; never raises)."""
        if self._session is not None:
            logger.info("Closing connection to %s", self.hostname)
            try:
                self._session.close()
            except Exception:  # noqa: BLE001
                logger.debug("Session close failed (ignored)", exc_info=True)
            finally:
                self._session = None

    # ------------------------------------------------------------------
    # NAPALM getters
    # ------------------------------------------------------------------

    def get_facts(self) -> dict[str, Any]:
        """Return general device facts conforming to the NAPALM schema.

        Returns:
            A dict with keys: ``hostname``, ``fqdn``, ``vendor``, ``model``,
            ``serial_number``, ``os_version``, ``uptime``, ``interface_list``.

        Raises:
            JTComError: If the session is not open.
            JTComParseError: If the device info page cannot be parsed.
        """
        session = self._require_session()
        html = session.get(DEVICE_INFO)
        device_info = parse_device_info(html)

        # Prefer the IP from the page; fall back to the configured hostname.
        hostname = device_info.ip_address or self.hostname

        return {
            "hostname": hostname,
            "fqdn": hostname,
            "vendor": _VENDOR,
            "model": device_info.model or "unknown",
            "serial_number": device_info.serial_number or "",
            "os_version": device_info.firmware_version or "",
            "uptime": parse_uptime_seconds(device_info.uptime),
            "interface_list": [],
        }

    def get_interfaces(self) -> dict[str, Any]:
        """Return interface information conforming to the NAPALM schema.

        Fetches port settings and status from ``port.cgi`` and returns
        a mapping from interface name (e.g. ``"Port 1"``) to a dict with
        keys: ``is_up``, ``is_enabled``, ``description``, ``last_flapped``,
        ``speed``, ``mtu``, ``mac_address``.

        Returns:
            Dict keyed by interface name.

        Raises:
            JTComError: If the session is not open.
            JTComParseError: If the port page cannot be parsed.
        """
        session = self._require_session()
        html = session.get(PORT_SETTINGS)
        settings_list, oper_list = parse_port_page(html)
        oper_by_id = {op.port_id: op for op in oper_list}

        result: dict[str, Any] = {}
        for settings in settings_list:
            oper = oper_by_id.get(settings.port_id)
            link_up: bool = bool(oper.link_up) if oper is not None else False
            speed: float = (
                float(oper.negotiated_speed_mbps)
                if oper is not None and oper.negotiated_speed_mbps is not None
                else 0.0
            )
            result[settings.name] = {
                "is_up": link_up,
                "is_enabled": settings.admin_up,
                "description": "",
                "last_flapped": -1.0,
                "speed": speed,
                "mtu": 0,
                "mac_address": "",
            }

        return result

    def get_vlans(self) -> dict[str, Any]:
        """Return VLAN information conforming to the NAPALM schema.

        Fetches the static VLAN list from ``vlan.cgi?page=static`` and the
        per-port VLAN settings from ``vlan.cgi?page=port_based``.  The two
        results are combined to produce the NAPALM ``get_vlans()`` mapping.

        Returns:
            Dict keyed by integer VLAN ID, each value being::

                {"name": str, "interfaces": [str, ...]}

            ``interfaces`` is the sorted union of all ports that carry the
            VLAN (tagged or untagged).

        Raises:
            JTComError: If the session is not open.
            JTComParseError: If either VLAN page cannot be parsed.
        """
        session = self._require_session()
        static_html = session.get(VLAN_STATIC, params={"page": "static"})
        port_html = session.get(VLAN_PORT_BASED, params={"page": "port_based"})

        vlans = parse_static_vlans(static_html)
        port_configs = parse_port_vlan_settings(port_html)

        vlan_map = {v.vlan_id: v for v in vlans}

        for pc in port_configs:
            if pc.vlan_type.lower() == "access" and pc.access_vlan is not None:
                entry = vlan_map.get(pc.access_vlan)
                if entry is not None:
                    entry.untagged_ports.append(pc.port_name)
            elif pc.vlan_type.lower() == "trunk":
                if pc.native_vlan is not None:
                    entry = vlan_map.get(pc.native_vlan)
                    if entry is not None:
                        entry.untagged_ports.append(pc.port_name)
                for vid in pc.permit_vlans:
                    entry = vlan_map.get(vid)
                    if entry is not None:
                        entry.tagged_ports.append(pc.port_name)

        result: dict[str, Any] = {}
        for vid, ve in sorted(vlan_map.items()):
            all_ports = sorted(set(ve.tagged_ports + ve.untagged_ports))
            result[str(vid)] = {"name": ve.name, "interfaces": all_ports}
        return result

    def set_vlans(
        self,
        desired_vlans: dict[int, VlanConfig],
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Apply an incremental VLAN change plan to the switch.

        Computes the difference between the current VLAN state and *desired_vlans*,
        optionally saves a binary configuration backup, then creates / updates /
        deletes VLANs as needed.

        Each entry in *desired_vlans* must carry a ``state`` field:
        ``"present"`` to create or update, ``"absent"`` to delete.
        VLANs not listed in *desired_vlans* are left untouched.

        Args:
            desired_vlans: Mapping of VLAN ID → :class:`~napalm_jtcom.model.vlan.VlanConfig`
                representing the incremental change.
            dry_run: If ``True``, compute and return the change plan without
                applying anything to the switch.

        Returns:
            A dict with keys:

            - ``"backup_file"`` – path to the saved backup, or ``""`` if skipped.
            - ``"create"`` – list of VLAN IDs that were (or would be) created.
            - ``"update"`` – list of VLAN IDs that were (or would be) updated.
            - ``"delete"`` – list of VLAN IDs that were (or would be) deleted.

        Raises:
            JTComError: If the session is not open.
            JTComSwitchError: If any switch operation returns a non-zero code.
        """
        session = self._require_session()

        # --- Fetch current state ---
        static_html = session.get(VLAN_STATIC, params={"page": "static"})
        port_html = session.get(VLAN_PORT_BASED, params={"page": "port_based"})
        vlans = parse_static_vlans(static_html)
        port_configs = parse_port_vlan_settings(port_html)

        vlan_map: dict[int, VlanEntry] = {v.vlan_id: v for v in vlans}
        for pc in port_configs:
            if pc.vlan_type.lower() == "access" and pc.access_vlan is not None:
                entry = vlan_map.get(pc.access_vlan)
                if entry is not None:
                    entry.untagged_ports.append(pc.port_name)
            elif pc.vlan_type.lower() == "trunk":
                if pc.native_vlan is not None:
                    entry = vlan_map.get(pc.native_vlan)
                    if entry is not None:
                        entry.untagged_ports.append(pc.port_name)
                for vid in pc.permit_vlans:
                    entry = vlan_map.get(vid)
                    if entry is not None:
                        entry.tagged_ports.append(pc.port_name)

        # --- Plan changes ---
        change_set = plan_vlan_changes(vlan_map, desired_vlans)

        result: dict[str, Any] = {
            "backup_file": "",
            "create": [c.vlan_id for c in change_set.create],
            "update": [u.vlan_id for u in change_set.update],
            "delete": change_set.delete,
        }

        if dry_run:
            return result

        # --- Backup before change ---
        if self.optional_args.get("backup_before_change", True):
            backup_dir = pathlib.Path(
                str(self.optional_args.get("backup_dir", "./backups"))
            )
            backup_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            safe_host = self.hostname.replace("://", "_").replace("/", "_").replace(":", "_")
            filename = f"jtcom_{safe_host}_{ts}_switch_cfg.bin"
            backup_path = backup_dir / filename
            raw = session.download_config_backup()
            backup_path.write_bytes(raw)
            result["backup_file"] = str(backup_path)
            logger.info("Config backup saved to %s (%d bytes)", backup_path, len(raw))

        # --- Apply creates (ascending VID) ---
        for cfg in change_set.create:
            vlan_create(session, cfg.vlan_id, cfg.name)
            logger.info("Created VLAN %d (%s)", cfg.vlan_id, cfg.name)

        # --- Apply updates (ascending VID) ---
        for cfg in change_set.update:
            vlan_create(session, cfg.vlan_id, cfg.name)
            logger.info("Updated VLAN %d (%s)", cfg.vlan_id, cfg.name)

        # --- Apply membership changes ---
        for cfg in change_set.create + change_set.update:
            if cfg.untagged_ports:
                vlan_set_port(
                    session,
                    port_ids=cfg.untagged_ports,
                    vlan_type="access",
                    access_vlan=cfg.vlan_id,
                    native_vlan=None,
                    permit_vlans=[],
                )
            if cfg.tagged_ports:
                vlan_set_port(
                    session,
                    port_ids=cfg.tagged_ports,
                    vlan_type="trunk",
                    access_vlan=None,
                    native_vlan=1,
                    permit_vlans=[cfg.vlan_id],
                )

        # --- Apply deletes (descending VID) ---
        if change_set.delete:
            vlan_delete(session, sorted(change_set.delete, reverse=True))
            logger.info("Deleted VLANs %s", sorted(change_set.delete, reverse=True))

        return result


    def set_interfaces(
        self,
        desired_ports: list[PortConfig],
        *,
        dry_run: bool = False,
        backup_before_change: bool | None = None,
    ) -> dict[str, Any]:
        """Apply declarative port configuration to the switch.

        Computes the difference between the current port state and
        *desired_ports*, optionally saves a binary configuration backup,
        then applies the necessary changes to each port.

        Only the non-``None`` fields in each :class:`~.PortConfig` are
        changed; ``None`` fields preserve the current switch value.

        Args:
            desired_ports: List of :class:`~.PortConfig` representing the
                desired state for each port to be configured.
            dry_run: If ``True``, compute and return the change plan without
                applying anything to the switch.
            backup_before_change: Override the ``backup_before_change``
                optional_arg for this call.  ``None`` means use the
                optional_args value (default ``True``).

        Returns:
            A dict with keys:

            - ``"backup_file"`` – path to the saved backup, or ``""`` if
              skipped.
            - ``"updated_ports"`` – list of port IDs (1-based) that were
              (or would be) reconfigured.

        Raises:
            JTComError: If the session is not open.
            JTComSwitchError: If any switch operation returns a non-zero code.
        """
        session = self._require_session()

        # --- Fetch current state ---
        html = session.get(PORT_SETTINGS)
        settings_list, _ = parse_port_page(html)

        # --- Plan changes ---
        change_set: PortChangeSet = plan_port_changes(settings_list, desired_ports)

        result: dict[str, Any] = {
            "backup_file": "",
            "updated_ports": [cfg.port_id for cfg in change_set.update],
        }

        if dry_run:
            return result

        if not change_set.update:
            return result

        # --- Backup before change ---
        do_backup = (
            backup_before_change
            if backup_before_change is not None
            else bool(self.optional_args.get("backup_before_change", True))
        )
        if do_backup:
            backup_dir = pathlib.Path(
                str(self.optional_args.get("backup_dir", "./backups"))
            )
            backup_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            safe_host = self.hostname.replace("://", "_").replace("/", "_").replace(":", "_")
            filename = f"jtcom_{safe_host}_{ts}_switch_cfg.bin"
            backup_path = backup_dir / filename
            raw = session.download_config_backup()
            backup_path.write_bytes(raw)
            result["backup_file"] = str(backup_path)
            logger.info("Config backup saved to %s (%d bytes)", backup_path, len(raw))

        # --- Apply changes in ascending port_id order ---
        apply_port_changes(session, settings_list, change_set)
        logger.info("Port changes applied: %s", result["updated_ports"])

        return result


    def apply_device_config(
        self,
        desired: DeviceConfig,
        *,
        check_mode: bool = False,
        backup_before_change: bool | None = None,
    ) -> dict[str, Any]:
        """Apply an incremental device configuration to the switch idempotently.

        Reads the current switch state, normalizes both current and desired
        configs, computes a deterministic change plan, and applies only what
        has changed.  A post-apply read-back verifies the result.

        Each VLAN/port entry in *desired* carries a ``state`` field:
        ``"present"`` to create or update, ``"absent"`` to delete/disable.
        Items not listed in *desired* are left untouched.

        Args:
            desired: Incremental :class:`~napalm_jtcom.model.config.DeviceConfig`.
            check_mode: If ``True``, return the plan without applying anything.
            backup_before_change: Override the ``backup_before_change`` optional
                arg.  ``None`` means use the optional_args value (default ``True``).

        Returns:
            A dict with keys:

            - ``"changed"`` — ``True`` if any changes were (or would be) applied.
            - ``"diff"`` — rendered plan dict from :func:`~napalm_jtcom.utils.render.render_diff`.
            - ``"backup_file"`` — path to the backup, or ``""`` if skipped.
            - ``"applied"`` — list of change keys that were applied.

        Raises:
            JTComError: If the session is not open.
            JTComVerificationError: If post-apply verification detects residual
                differences between the switch state and *desired*.
        """
        session = self._require_session()
        safety_port_id: int = int(self.optional_args.get("safety_port_id", 6))

        # --- Read and normalize current state ---
        current_vlans, current_ports = self._read_current_state(session)
        current_cfg = DeviceConfig.from_current(current_vlans, current_ports)
        current_n = normalize_device_config(current_cfg)
        desired_n = normalize_device_config(desired)

        # --- Build plan ---
        plan = build_device_plan(
            current_n,
            desired_n,
            safety_port_id=safety_port_id,
        )
        diff = render_diff(plan)

        if not plan.changes:
            return {"changed": False, "diff": diff, "backup_file": "", "applied": []}

        if check_mode:
            return {"changed": True, "diff": diff, "backup_file": "", "applied": []}

        # --- Backup before change ---
        do_backup = (
            backup_before_change
            if backup_before_change is not None
            else bool(self.optional_args.get("backup_before_change", True))
        )
        backup_file = self._save_backup(session) if do_backup else ""

        # --- Apply changes in plan order ---
        applied: list[str] = []
        for change in plan.changes:
            if change.kind in ("vlan_create", "vlan_update"):
                vid = change.details["vlan_id"]
                vc = desired_n.vlans[vid]
                vlan_create(session, vc.vlan_id, vc.name)
                logger.info("%s VLAN %d (%s)", change.kind, vid, vc.name)
                if vc.untagged_ports:
                    vlan_set_port(
                        session,
                        port_ids=vc.untagged_ports,
                        vlan_type="access",
                        access_vlan=vc.vlan_id,
                        native_vlan=None,
                        permit_vlans=[],
                    )
                if vc.tagged_ports:
                    vlan_set_port(
                        session,
                        port_ids=vc.tagged_ports,
                        vlan_type="trunk",
                        access_vlan=None,
                        native_vlan=1,
                        permit_vlans=[vc.vlan_id],
                    )
            elif change.kind == "vlan_delete":
                vid = change.details["vlan_id"]
                vlan_delete(session, [vid])
                logger.info("Deleted VLAN %d", vid)
            elif change.kind == "port_update":
                pid = change.details["port_id"]
                desired_port = desired_n.ports[pid]
                port_cs = PortChangeSet(update=[desired_port])
                apply_port_changes(session, current_ports, port_cs)
                logger.info("Updated port %d", pid)
            applied.append(change.key)

        # --- Post-apply verification ---
        post_vlans, post_ports = self._read_current_state(session)
        post_cfg = DeviceConfig.from_current(post_vlans, post_ports)
        post_n = normalize_device_config(post_cfg)
        residual_plan = build_device_plan(
            post_n,
            desired_n,
            safety_port_id=safety_port_id,
        )
        if residual_plan.changes:
            raise JTComVerificationError(remaining_diff=render_diff(residual_plan))

        return {
            "changed": True,
            "diff": diff,
            "backup_file": backup_file,
            "applied": applied,
        }

    def _read_current_state(
        self, session: JTComSession
    ) -> tuple[dict[int, VlanEntry], list[PortSettings]]:
        """Read VLANs and ports from the switch and return both.

        Args:
            session: Active authenticated session.

        Returns:
            A tuple of ``(vlan_map, settings_list)`` where ``vlan_map`` is a
            ``dict[int, VlanEntry]`` (with port memberships populated) and
            ``settings_list`` is a ``list[PortSettings]``.
        """
        static_html = session.get(VLAN_STATIC, params={"page": "static"})
        port_html = session.get(VLAN_PORT_BASED, params={"page": "port_based"})
        vlans = parse_static_vlans(static_html)
        port_vlan_configs = parse_port_vlan_settings(port_html)

        vlan_map: dict[int, VlanEntry] = {v.vlan_id: v for v in vlans}
        for pc in port_vlan_configs:
            if pc.vlan_type.lower() == "access" and pc.access_vlan is not None:
                entry = vlan_map.get(pc.access_vlan)
                if entry is not None:
                    entry.untagged_ports.append(pc.port_name)
            elif pc.vlan_type.lower() == "trunk":
                if pc.native_vlan is not None:
                    entry = vlan_map.get(pc.native_vlan)
                    if entry is not None:
                        entry.untagged_ports.append(pc.port_name)
                for vid in pc.permit_vlans:
                    entry = vlan_map.get(vid)
                    if entry is not None:
                        entry.tagged_ports.append(pc.port_name)

        port_html2 = session.get(PORT_SETTINGS)
        settings_list, _ = parse_port_page(port_html2)
        return vlan_map, settings_list

    def _save_backup(self, session: JTComSession) -> str:
        """Download a config backup and save it to disk.

        Args:
            session: Active authenticated session.

        Returns:
            The local file path of the saved backup.
        """
        backup_dir = pathlib.Path(str(self.optional_args.get("backup_dir", "./backups")))
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_host = self.hostname.replace("://", "_").replace("/", "_").replace(":", "_")
        filename = f"jtcom_{safe_host}_{ts}_switch_cfg.bin"
        backup_path = backup_dir / filename
        raw = session.download_config_backup()
        backup_path.write_bytes(raw)
        logger.info("Config backup saved to %s (%d bytes)", backup_path, len(raw))
        return str(backup_path)

    def is_alive(self) -> dict[str, bool]:
        """Return liveness status of the HTTP session."""
        return {"is_alive": self._session is not None and self._session.logged_in}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_base_url(self) -> str:
        """Construct the switch base URL from hostname / port / TLS settings."""
        if "://" in self.hostname:
            return self.hostname.rstrip("/")
        scheme = "https" if self._verify_tls else "http"
        host = self.hostname
        port = self._port
        default_port = 443 if self._verify_tls else 80
        if port == default_port:
            return f"{scheme}://{host}"
        return f"{scheme}://{host}:{port}"

    def _require_session(self) -> JTComSession:
        """Return the active session or raise :exc:`.JTComError`."""
        if self._session is None:
            raise JTComError("Session not open — call open() first.")
        return self._session
