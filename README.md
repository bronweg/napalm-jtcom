# napalm-jtcom

NAPALM community driver for **JTCom CGI-based Ethernet switches**.

Extends [NAPALM](https://napalm.readthedocs.io/) to support L2 managed switches
that expose a CGI-based web interface (no SSH/NETCONF/SNMP API).

---

## Overview

`napalm-jtcom` speaks HTTP to the switch's built-in web UI, parses HTML responses
with BeautifulSoup, and exposes a standard NAPALM driver interface. This makes it
possible to manage JTCom (and compatible) switches from Ansible, Python scripts, and
any tool built on top of NAPALM.

---

## Supported Devices

| Vendor | Series | Tested |
|--------|--------|--------|
| JTCom  | L2 CGI | ✅     |

---

## Installation

```bash
# From PyPI (once published)
pip install napalm-jtcom

# From source (development)
git clone https://github.com/bronweg/napalm-jtcom.git
cd napalm-jtcom
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Quick Example

```python
import napalm

driver = napalm.get_network_driver("jtcom")
with driver("192.168.1.1", "admin", "admin") as device:
    facts = device.get_facts()
    print(facts)
```

---

## Development

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for setup, testing, and contribution guidelines.

```bash
# Run tests
pytest

# Lint + type-check
ruff check src/
mypy src/
```

---

## License

MIT — see [LICENSE](LICENSE).
