"""Low-level VLAN write operations for JTCom CGI switches.

Each function translates a strongly-typed request into the exact form-field
payload captured from the real switch and delegates to
:class:`~napalm_jtcom.client.session.JTComSession` for dispatch.

Confirmed payloads (real switch 192.168.51.21):

    CREATE: POST /staticvlan.cgi
        vlanid=<id>&vlanname=<name>&cmd=add&page=inside
        → {"code":0,"data":""}

    DELETE: POST /staticvlan.cgi
        del=<id>[&del=<id2>…]&cmd=del&page=inside
        → {"code":0,"data":""}

    PORT ACCESS: POST /vlanport.cgi
        PortId=<0_1_…>&VlanType=0&AccessVlan=<id>&NativeVlan=1&PermitVlan=&page=inside
        → {"code":0,"data":""}

    PORT TRUNK: POST /vlanport.cgi
        PortId=<0_1_…>&VlanType=1&AccessVlan=1&NativeVlan=<id>&PermitVlan=<id1_id2_…>&page=inside
        → {"code":0,"data":""}
"""

from __future__ import annotations

import logging

import requests

from napalm_jtcom.client.errors import JTComSwitchError
from napalm_jtcom.client.session import JTComSession
from napalm_jtcom.vendor.jtcom.endpoints import VLAN_CREATE_DELETE, VLAN_PORT_SET

logger = logging.getLogger(__name__)

# VlanType values understood by the switch firmware.
_VLAN_TYPE_ACCESS: str = "0"
_VLAN_TYPE_TRUNK: str = "1"


def vlan_create(
    session: JTComSession,
    vlan_id: int,
    name: str | None = None,
) -> None:
    """Create a static VLAN on the switch.

    Args:
        session: Active authenticated session.
        vlan_id: 802.1Q VLAN identifier (2–4094; 1 is reserved).
        name: Optional human-readable VLAN name.  Defaults to an empty
            string if not provided (switch displays blank).

    Raises:
        JTComSwitchError: If the switch returns a non-zero response code.
    """
    logger.debug("Creating VLAN %d (name=%r)", vlan_id, name)
    session.post(
        VLAN_CREATE_DELETE,
        data={
            "vlanid": str(vlan_id),
            "vlanname": name or "",
            "cmd": "add",
        },
    )


def vlan_delete(
    session: JTComSession,
    vlan_ids: list[int],
) -> None:
    """Delete one or more static VLANs from the switch.

    The switch accepts multiple ``del`` keys in a single POST body.
    VLAN 1 is silently skipped even if included in *vlan_ids*.

    Args:
        session: Active authenticated session.
        vlan_ids: List of VLAN IDs to delete.  Must not be empty.

    Raises:
        ValueError: If *vlan_ids* is empty after filtering out VLAN 1.
        JTComSwitchError: If the switch returns a non-zero response code.
    """
    safe_ids = [v for v in vlan_ids if v != 1]
    if not safe_ids:
        raise ValueError("vlan_ids must contain at least one deletable VLAN (not 1)")

    logger.debug("Deleting VLANs %s", safe_ids)

    # requests.Session.post() with data= only sends one value per key when
    # data is a dict.  We need to repeat the key, so we pass a list of tuples.
    form_fields: list[tuple[str, str]] = [("del", str(v)) for v in sorted(safe_ids)]
    form_fields.append(("cmd", "del"))
    form_fields.append(("page", "inside"))

    resp = session._http.post_form(VLAN_CREATE_DELETE, data=form_fields)
    _check_response(resp, VLAN_CREATE_DELETE, form_fields)


def vlan_set_port(
    session: JTComSession,
    port_ids: list[int],
    vlan_type: str,
    access_vlan: int | None,
    native_vlan: int | None,
    permit_vlans: list[int],
) -> None:
    """Set VLAN membership for one or more ports.

    The switch accepts multiple ports in a single POST by joining 0-based
    port indices with underscores (``PortId=0_1_2``).

    Args:
        session: Active authenticated session.
        port_ids: 0-based port indices (Port 1 = 0, Port 2 = 1, …).
        vlan_type: ``"access"`` or ``"trunk"`` (case-insensitive).
        access_vlan: VLAN ID for Access mode (ignored in Trunk mode).
        native_vlan: Native VLAN ID for Trunk mode (ignored in Access mode).
        permit_vlans: Tagged VLAN IDs for Trunk mode (non-native only).

    Raises:
        ValueError: If *port_ids* is empty or *vlan_type* is invalid.
        JTComSwitchError: If the switch returns a non-zero response code.
    """
    if not port_ids:
        raise ValueError("port_ids must not be empty")
    vt_lower = vlan_type.lower()
    if vt_lower not in {"access", "trunk"}:
        raise ValueError(f"vlan_type must be 'access' or 'trunk', got {vlan_type!r}")

    port_id_str = "_".join(str(p) for p in sorted(port_ids))

    if vt_lower == "access":
        vlan_type_val = _VLAN_TYPE_ACCESS
        av = str(access_vlan) if access_vlan is not None else "1"
        nv = "1"
        pv = ""
    else:
        vlan_type_val = _VLAN_TYPE_TRUNK
        av = "1"
        nv = str(native_vlan) if native_vlan is not None else "1"
        pv = "_".join(str(v) for v in sorted(permit_vlans))

    logger.debug(
        "Setting port(s) %s → %s (AccessVlan=%s NativeVlan=%s PermitVlan=%s)",
        port_id_str, vlan_type, av, nv, pv,
    )
    session.post(
        VLAN_PORT_SET,
        data={
            "PortId": port_id_str,
            "VlanType": vlan_type_val,
            "AccessVlan": av,
            "NativeVlan": nv,
            "PermitVlan": pv,
        },
    )


def _check_response(
    resp: requests.Response,
    endpoint: str,
    payload: list[tuple[str, str]],
) -> None:
    """Parse JSON and raise :exc:`JTComSwitchError` on non-zero code."""
    import json

    try:
        result: dict[str, object] = json.loads(resp.text)
    except (json.JSONDecodeError, ValueError) as exc:
        from napalm_jtcom.client.errors import JTComParseError

        raise JTComParseError(
            f"Non-JSON response from {endpoint!r}: {resp.text[:200]!r}"
        ) from exc

    code = result.get("code", -1)
    if code != 0:
        raise JTComSwitchError(
            code=int(str(code)),
            message=str(result.get("data", "")),
            endpoint=endpoint,
            payload=dict(payload),
        )
