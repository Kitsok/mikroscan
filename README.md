# Mikrotik Network Mapper

A tool for mapping network connections between Mikrotik devices and hosts. This tool scans networks for Mikrotik devices, collects configuration data via SSH, and builds a connection map showing how devices and hosts are interconnected.

## Features

- **Network Scanning**: Automatically discovers Mikrotik devices on a network
- **Data Collection**: Gathers interface, bridge, ARP, and DHCP information via SSH
- **Connection Mapping**: Builds a map of device-to-device and device-to-host connections
- **Encrypted Credentials**: Securely stores SSH credentials with master password protection
- **JSON Output**: Exports connection data in structured JSON format
- **Human-Readable Output**: Generates easy-to-understand connection descriptions

## Requirements

- Python 3.6+
- Paramiko library
- Cryptography library

Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Network Mapping

Scan a network range and map connections:
```bash
python3 main.py 192.168.1.0/24 -u admin -p password
```

All output files will be stored in the `data/` directory:
- `data/scan_results.json`: Discovered Mikrotik devices
- `data/collected_data.json`: Raw device data
- `data/final_map.json`: Structured JSON connection map
- `data/connections.txt`: Human-readable connection descriptions
- `data/credentials.encrypted`: Encrypted SSH credentials

### Network Mapping with Custom SSH Port

Scan and map connections using a custom SSH port:
```bash
python3 main.py --ssh-port 10021 192.168.1.0/24 -u admin -p password
```

### Network Mapping with Verbose Output

Scan with detailed output showing the scanning process:
```bash
python3 main.py -v 192.168.1.0/24 -u admin -p password
```

### Storing Default Credentials

Store default credentials for all routers (will prompt for username/password):
```bash
python3 main.py --store-default-credentials
```

Or provide credentials directly:
```bash
python3 main.py --store-default-credentials -u admin -p password
```

### Storing Host-Specific Credentials

Store credentials for a specific host (will prompt for username/password):
```bash
python3 main.py --store-credentials --hostname 192.168.1.1
```

Or provide credentials directly:
```bash
python3 main.py --store-credentials --hostname 192.168.1.1 -u admin -p password
```

### Using Stored Credentials

Run mapping without specifying credentials (will use default or host-specific credentials):
```bash
python3 main.py 192.168.1.0/24
```

The tool will:
1. Use host-specific credentials if stored for a particular router
2. Fall back to default credentials if no host-specific credentials are found
3. Prompt for credentials if neither default nor host-specific credentials are available

### Using Stored Credentials

Store credentials for later use:
```bash
python3 main.py --store-credentials --hostname 192.168.1.1 -u admin -p password
```

Then run mapping without specifying credentials (will prompt for master password):
```bash
python3 main.py 192.168.1.0/24
```

### Generate Network Topology Diagram

Create a network topology diagram from collected data:
```bash
python3 main.py --generate-topology --data-file data/collected_data.json
```

This will generate a topology diagram showing:
- Categorized devices (routers, switches, access points)
- Network connectivity analysis
- Intelligent recommendations for network optimization
- Output saved to `data/topology.txt`

## Running Tests

The tool includes a comprehensive test suite that can be run with user-provided credentials:

```bash
python3 tests/test_runner.py
```

The test runner will prompt for:
- Test device hostname/IP
- SSH username and password
- Master password for credential storage

If credentials are provided, integration tests will be run against actual Mikrotik devices.
If no credentials are provided, unit tests will still run.

Individual test modules can also be run directly:
```bash
python3 tests/test_scanner.py
python3 tests/test_ssh.py
python3 tests/test_data_collector.py
python3 tests/test_mapping.py
python3 tests/test_credential_manager.py
python3 tests/test_main.py
```

## Output Files

All files are stored in the `data/` directory:
- `data/final_map.json`: Structured JSON connection map
- `data/connections.txt`: Human-readable connection descriptions
- `data/scan_results.json`: Discovered Mikrotik devices (when scanning)
- `data/collected_data.json`: Raw device data (when collecting)
- `data/credentials.encrypted`: Encrypted SSH credentials (when storing)

## Security

- SSH credentials are encrypted using AES with a master password
- Each credential entry is encrypted separately
- Master password is never stored on disk
- All sensitive data is stored in encrypted format

## Modules

- `lib/`: All core library modules (network scanning, data collection, mapping, credential management, SSH)
- `data/`: All generated data files

## License

MIT License