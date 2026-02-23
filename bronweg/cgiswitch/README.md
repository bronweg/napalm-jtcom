# bronweg.cgiswitch

Ansible Collection for managing JTCom CGI-based L2 Ethernet switches via
[napalm-jtcom](https://github.com/bronweg/napalm-jtcom).

## Requirements

- Ansible >= 2.14
- Python >= 3.10
- `napalm-jtcom >= 0.8.0` installed in the Ansible controller's Python environment

## Installation

```bash
ansible-galaxy collection install bronweg-cgiswitch-0.1.0.tar.gz
pip install napalm-jtcom
```

## Modules

### `bronweg.cgiswitch.jtcom_config`

Idempotent, diff-aware PATCH-style configuration of VLANs and ports.

- **VLANs** support `state: present | absent` (incremental — unlisted VLANs untouched)
- **Ports** are patch-only: supply only the fields you want to change
- Supports Ansible `--check` (dry-run) mode
- Port 6 (management uplink) cannot be administratively disabled
- VLAN 1 cannot be deleted

```yaml
- name: Configure switch
  bronweg.cgiswitch.jtcom_config:
    host: 192.0.2.1
    username: "{{ jtcom_user }}"
    password: "{{ jtcom_pass }}"
    verify_tls: false
    vlans:
      10:
        name: Management
        untagged_ports: [0]
      99:
        state: absent
    ports:
      1:
        admin_up: true
        speed: Auto
        flow_control: false
```

See `examples/` for ready-to-run playbooks.

## License

MIT
