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

## Key Features

| Capability | Method / Command |
|---|---|
| Read device facts | `get_facts()` |
| Read interfaces | `get_interfaces()` |
| Read VLANs | `get_vlans()` |
| Incremental VLAN changes | `set_vlans(desired, dry_run=False)` |
| Full device config apply | `apply_device_config(desired, check_mode=False)` |
| Ansible integration | `ansible/action_plugins/jtcom_config` |

### Incremental Change Model

`set_vlans()` and `apply_device_config()` use an **incremental model**: only
the VLANs and ports you list are affected. Unlisted items are always a no-op.

Each entry carries a `state` field:

```python
from napalm_jtcom.driver import JTComDriver
from napalm_jtcom.model.config import DeviceConfig
from napalm_jtcom.model.vlan import VlanConfig

driver = JTComDriver("192.168.1.1", "admin", "admin")
driver.open()

result = driver.apply_device_config(
    DeviceConfig(
        vlans={
            100: VlanConfig(vlan_id=100, name="servers", state="present"),
            # 200: VlanConfig(vlan_id=200, state="absent"),  # delete VLAN 200
        },
        ports={},  # no port changes
    ),
    check_mode=True,  # dry-run — pass False to apply
)
driver.close()
```

### Ansible Module

The `ansible/` directory contains a native action plugin that calls
`apply_device_config()` without any subprocess.

```yaml
- name: Configure switch VLANs
  jtcom_config:
    host: "{{ jtcom_host }}"
    username: "{{ jtcom_user }}"
    password: "{{ jtcom_pass }}"
    vlans:
      - vlan_id: 100
        name: servers
        state: present
      - vlan_id: 200
        state: absent
```

---

## Development

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for setup, testing, and contribution guidelines.

```bash
# Run tests
pytest

# Lint + type-check
ruff check src/ tests/ ansible/
mypy src/
```

---

## License

MIT — see [LICENSE](LICENSE).
