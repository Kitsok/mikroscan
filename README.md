# Mikrotik Network Mapper

A tool for discovering MikroTik devices, collecting live RouterOS data,
and generating a connection map plus a rooted topology tree.

## Features

- Discover MikroTik devices on a subnet
- Collect live data via RouterOS API by default
- Fall back to SSH collection when needed
- Store encrypted device credentials behind a master password
- Build `final_map.json` and `connections.txt`
- Generate `topology.txt` as a rooted port tree
- Append unresolved known-but-unplaced hosts after the topology tree

## Requirements

- Python 3.8+
- Dependencies from `requirements.txt`

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## Default Behavior

Live collection now defaults to:

- backend: RouterOS API
- API port: `8728`
- API SSL: disabled

So this is the default refresh flow:

```bash
python3 main.py --scan-file
```

That command will:

1. read `data/scan_results.json`
2. recollect live data from those devices
3. rebuild `data/final_map.json`
4. rebuild `data/connections.txt`
5. regenerate `data/topology.txt`

## Common Workflows

### Store default credentials

```bash
python3 main.py --store-default-credentials -u admin -p 'password'
```

If `-u/-p` are omitted, the CLI will prompt.

### Scan a subnet and build the map

```bash
python3 main.py 192.168.1.0/24
```

This scans for MikroTik devices, collects data, and builds:

- `data/scan_results.json`
- `data/collected_data.json`
- `data/final_map.json`
- `data/connections.txt`

### Refresh known devices without rescanning the subnet

```bash
python3 main.py --scan-file
```

You can also point at a different scan file:

```bash
python3 main.py --scan-file other_scan_results.json
```

### Generate topology from existing collected data

```bash
python3 main.py --generate-topology
```

`--generate-topology` defaults to:

- input: `data/collected_data.json`
- output: `data/topology.txt`

### Build only the map from existing collected data

```bash
python3 main.py --data-file data/collected_data.json
```

## Backend Selection

### RouterOS API, default

```bash
python3 main.py --scan-file --backend api --api-port 8728
```

Enable API TLS explicitly:

```bash
python3 main.py --scan-file --backend api --api-port 8729 --api-ssl
```

### Explicit SSH backend

```bash
python3 main.py --scan-file --backend ssh --ssh-port 22
```

## Topology Output

`data/topology.txt` is generated as a rooted tree:

- root device first, usually the edge router
- ports rendered under each managed device
- downstream MikroTiks nested under the port they hang off
- WAN interface chains rendered under the physical WAN port
- shared segments shown explicitly when point-to-point inference is weak
- unresolved known hosts listed after the tree

PoE labels are shown on Ethernet ports when live PoE monitor data is
available, for example:

```text
ether5-shadow [04:F4:1C:0F:DC:1C] [PoE: 3.1W]
```

## Output Files

All generated output lives under `data/`:

- `scan_results.json`: discovered MikroTik devices
- `collected_data.json`: raw collected device data
- `final_map.json`: structured JSON connection map
- `connections.txt`: readable connection summary
- `topology.txt`: rooted topology tree
- `credentials.encrypted`: encrypted stored credentials

## Security

- Device credentials are encrypted locally
- Access to stored credentials requires the master password
- The master password is not stored on disk

## Tests

Run focused tests directly:

```bash
python3 tests/test_api.py
python3 tests/test_data_collector.py
python3 tests/test_main.py
python3 tests/test_mapping.py
python3 tests/test_topology_builder.py
python3 tests/test_ssh.py
```

## Modules

- `lib/`: scanner, collectors, backends, mapping, topology, credentials
- `tests/`: unit and integration-style tests
- `data/`: generated local output, not committed by default
