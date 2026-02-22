#!/usr/bin/env python3
"""Smoke-test script: retrieve device facts from a JTCom switch.

Usage::

    export JTCOM_HOST="http://192.168.61.10"
    export JTCOM_USERNAME="admin"
    export JTCOM_PASSWORD="your-password"
    export JTCOM_VERIFY_TLS="false"   # optional, default false
    python examples/get_facts.py

Exit codes:
    0 — facts retrieved and printed successfully.
    1 — missing environment variable or driver error.
"""

from __future__ import annotations

import json
import os
import sys


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        print(f"ERROR: required environment variable {name!r} is not set.", file=sys.stderr)
        sys.exit(1)
    return value


def main() -> None:
    host = _env("JTCOM_HOST")
    username = _env("JTCOM_USERNAME")
    password = _env("JTCOM_PASSWORD")
    verify_tls_raw = os.environ.get("JTCOM_VERIFY_TLS", "false").lower()
    verify_tls = verify_tls_raw not in {"0", "false", "no", "off"}

    # Import here so import errors surface after env var check.
    from napalm_jtcom.driver import JTComDriver

    driver = JTComDriver(
        hostname=host,
        username=username,
        password=password,
        optional_args={"verify_tls": verify_tls},
    )

    try:
        driver.open()
        facts = driver.get_facts()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        driver.close()

    print(json.dumps(facts, indent=2))


if __name__ == "__main__":
    main()
