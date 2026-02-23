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

## Key Features

| Capability | Detail |
|---|---|
| Read device facts | `get_facts()` |
| Read interfaces | `get_interfaces()` |
| Read VLANs | `get_vlans()` |
| Incremental VLAN changes | `set_vlans(desired, dry_run=False)` |
| Incremental port patching | `apply_device_config()` with `ports=` |
| Full device config apply | `apply_device_config(desired, check_mode=False)` |
| Ansible standalone plugin | `ansible/` — zero subprocess, direct import |
| Ansible Galaxy collection | `bronweg.cgiswitch.jtcom_config` |

### Incremental Change Model

All write operations use an **incremental / patch model**: only the VLANs and ports you
list are affected. Unlisted items are always left untouched.

- VLANs carry a `state` field: `present` (default) or `absent`.
- Port entries are patch-only — supply only the fields you want to change.
- VLAN 1 is protected and can never be deleted.
- Port 6 (management uplink) can never be administratively disabled.

---

## Python API

```python
from napalm_jtcom.driver import JTComDriver
from napalm_jtcom.model.config import DeviceConfig
from napalm_jtcom.model.vlan import VlanConfig
from napalm_jtcom.model.port import PortConfig

driver = JTComDriver("192.0.2.1", "admin", "secret", optional_args={"verify_tls": False})
driver.open()

result = driver.apply_device_config(
    DeviceConfig(
        vlans={
            10: VlanConfig(vlan_id=10, name="Management", untagged_ports=[0], state="present"),
            99: VlanConfig(vlan_id=99, state="absent"),   # delete VLAN 99 if it exists
        },
        ports={
            1: PortConfig(port_id=1, admin_up=True, speed_duplex="Auto", flow_control=False),
        },
    ),
    check_mode=True,   # dry-run — pass False to apply
)

print(result)   # {"changed": True, "diff": {...}}
driver.close()
```

See the `examples/` directory for additional runnable scripts (`get_facts.py`,
`get_interfaces.py`, `get_vlans.py`, `apply_vlan.py`, `apply_device_config.py`,
`toggle_port_admin.py`).

---

## Ansible

Two integration paths are provided: a **standalone plugin** (no extra install step) and
a **Galaxy collection** (shareable, versioned artifact).

### Standalone plugin (`ansible/`)

The `ansible/` directory contains a native action plugin that imports `napalm_jtcom`
directly — no subprocess overhead, works out of the box once `napalm-jtcom` is installed
in the same Python environment as Ansible.

Add the plugin paths to your `ansible.cfg`:

```ini
[defaults]
library        = /path/to/napalm-jtcom/ansible/library
action_plugins = /path/to/napalm-jtcom/ansible/action_plugins
```

Example task:

```yaml
- name: Configure switch VLANs and ports
  jtcom_config:
    host: "{{ jtcom_host }}"
    username: "{{ jtcom_user }}"
    password: "{{ jtcom_pass }}"
    vlans:
      10:
        name: Management
        state: present
      99:
        state: absent
    ports:
      1:
        admin_up: true
        speed_duplex: Auto
        flow_control: false
```

### Galaxy Collection (`bronweg.cgiswitch`)

A fully packaged Ansible Galaxy collection lives at `galaxy/bronweg/cgiswitch/`.
FQCN: **`bronweg.cgiswitch.jtcom_config`**

**Install:**

```bash
ansible-galaxy collection install galaxy/bronweg/cgiswitch/bronweg-cgiswitch-0.1.0.tar.gz
pip install napalm-jtcom
```

**Example task:**

```yaml
- name: Configure JTCom switch
  bronweg.cgiswitch.jtcom_config:
    host: "{{ jtcom_host }}"
    username: "{{ jtcom_user }}"
    password: "{{ jtcom_pass }}"
    verify_tls: false
    vlans:
      10:
        name: Management
        untagged_ports: [0]
      20:
        name: Data
        tagged_ports: [7]
        untagged_ports: [1, 2, 3]
      99:
        state: absent
    ports:
      1:
        admin_up: true
        speed: Auto
        flow_control: false
```

Both the standalone plugin and the collection support Ansible `--check` (dry-run) mode.

**Key differences between the two:**

| Setting | Standalone (`ansible/`) | Collection (`bronweg.cgiswitch`) |
|---|---|---|
| `verify_tls` default | `false` | `true` (production-safe) |
| `safety_port_id` | configurable, default 6 | hardcoded 6, not exposed |
| Port speed key | `speed_duplex` | `speed` |

Inspect the collection module documentation:

```bash
ansible-doc bronweg.cgiswitch.jtcom_config
```

See `galaxy/bronweg/cgiswitch/examples/` for ready-to-run collection playbooks.

---

## Project Structure

```
napalm-jtcom/
  src/napalm_jtcom/
    driver.py          # NAPALM NetworkDriver subclass
    client/            # HTTP session, request helpers, VLAN/port write ops
    parser/            # HTML → Python object parsers
    model/             # Typed dataclass models (VlanConfig, PortConfig, DeviceConfig …)
    utils/             # Diff/plan engines (vlan_diff, device_diff, port_diff, render)
    vendor/jtcom/      # JTCom-specific endpoint paths and field mappings
  ansible/
    action_plugins/    # jtcom_config action plugin (imports napalm_jtcom directly)
    library/           # jtcom_config module stub (docs / argument_spec for ansible-doc)
    inventory.ini      # Example inventory
    ansible.cfg        # Ansible configuration
    test_playbook.yml  # Example playbook
  galaxy/
    bronweg/cgiswitch/ # Ansible Galaxy collection (bronweg.cgiswitch, v0.1.0)
      galaxy.yml       # Collection manifest
      plugins/action/  # Action plugin
      plugins/modules/ # Module stub (ansible-doc / Galaxy)
      examples/        # Ready-to-run playbooks
  tests/
    unit/              # Unit tests for parsers, diff engines, and payloads
    fixtures/          # HTML snapshots from real devices
  examples/            # Runnable Python usage examples
  docs/                # Developer documentation
```

---

## Development

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for setup, testing, and contribution guidelines.

```bash
# Run tests
pytest

# Lint + type-check
ruff check src/ tests/ ansible/ galaxy/ examples/
mypy src/ ansible/

# Build the Galaxy collection
cd galaxy/bronweg/cgiswitch
ansible-galaxy collection build --force
```

---

## License

MIT — see [LICENSE](LICENSE).
