# Development Guide

## Prerequisites

- Python 3.11+
- Git

## Setup

```bash
git clone https://github.com/bronweg/napalm-jtcom.git
cd napalm-jtcom

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Upgrade packaging tools
pip install --upgrade pip setuptools wheel

# Install project + dev dependencies
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
```

Run with verbose output:

```bash
pytest -v
```

Run a specific test file:

```bash
pytest tests/unit/test_parser_vlan.py -v
```

## Code Quality

```bash
# Lint
ruff check src/ tests/ ansible/ galaxy/ examples/

# Auto-fix lint issues
ruff check --fix src/ tests/ ansible/ galaxy/ examples/

# Format
ruff format src/ tests/ ansible/ galaxy/ examples/

# Type check
mypy src/
```

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
  examples/            # Runnable usage examples
  docs/                # Developer documentation
```

## Adding a New Getter

1. Identify the CGI endpoint in `vendor/jtcom/endpoints.py`.
2. Capture an HTML fixture in `tests/fixtures/`.
3. Add a parser function in `parser/`.
4. Add a typed model in `model/` if needed.
5. Implement the getter in `driver.py` calling the session + parser.
6. Write tests in `tests/unit/`.

## Running the Ansible Module

The `ansible/` directory contains a native Ansible action plugin that wraps
`apply_device_config()` directly (no subprocess).

```bash
cd ansible

# Dry-run (--check) against the real switch:
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES \
VIRTUAL_ENV=/path/to/.venv \
ANSIBLE_CONFIG=ansible.cfg \
/path/to/.venv/bin/ansible-playbook \
  -i inventory.ini test_playbook.yml \
  -e jtcom_host=192.0.2.1 -e jtcom_user=admin -e jtcom_pass=admin \
  --check
```

The `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` flag is required on macOS to
prevent a fork-safety crash when Ansible forks a subprocess.

## Releasing



```bash
pip install build
python -m build
twine upload dist/*
```
