"""JTCom NAPALM driver — top-level NetworkDriver implementation."""

from __future__ import annotations

import logging
from typing import Any

from napalm.base.base import NetworkDriver

from napalm_jtcom.client.errors import JTComError
from napalm_jtcom.client.session import JTComCredentials, JTComSession
from napalm_jtcom.parser.device import parse_device_info, parse_uptime_seconds
from napalm_jtcom.parser.port import parse_port_page
from napalm_jtcom.vendor.jtcom.endpoints import DEVICE_INFO, PORT_SETTINGS

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
        """Return VLAN configuration."""
        raise NotImplementedError("get_vlans() not yet implemented")

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
