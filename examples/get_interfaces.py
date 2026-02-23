#!/usr/bin/env python3
"""Smoke-test script: connect to a JTCom switch and print get_interfaces().

Environment variables
---------------------
JTCOM_HOST        Switch base URL or IP (e.g. http://192.0.2.1)
JTCOM_USERNAME    Login username          (required)
JTCOM_PASSWORD    Login password          (required)
JTCOM_VERIFY_TLS  Set to "true" to verify TLS (default: false)
"""

from __future__ import annotations

import json
import os
import sys

from napalm_jtcom.driver import JTComDriver


def _require(name: str) -> str:
    print(f"ERROR: required environment variable {name!r} is not set.", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    host = os.environ.get("JTCOM_HOST", "")
    if not host:
        print("ERROR: JTCOM_HOST is not set.", file=sys.stderr)
        sys.exit(1)

    username = os.environ.get("JTCOM_USERNAME") or _require("JTCOM_USERNAME")
    password = os.environ.get("JTCOM_PASSWORD") or _require("JTCOM_PASSWORD")
    verify_tls = os.environ.get("JTCOM_VERIFY_TLS", "false").lower() == "true"

    driver = JTComDriver(
        hostname=host,
        username=username,
        password=password,
        optional_args={"verify_tls": verify_tls},
    )
    try:
        driver.open()
        interfaces = driver.get_interfaces()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        driver.close()

    print(json.dumps(interfaces, indent=2))


if __name__ == "__main__":
    main()
