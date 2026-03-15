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

### Network Mapping with Custom SSH Port

Scan and map connections using a custom SSH port:
```bash
python3 main.py --ssh-port 10021 192.168.1.0/24 -u admin -p password
```

### Using Stored Credentials

Store credentials for later use:
```bash
python3 main.py --store-credentials --hostname 192.168.1.1 -u admin -p password
```

Then run mapping without specifying credentials (will prompt for master password):
```bash
python3 main.py 192.168.1.0/24
```

### Using Existing Data

Use previously collected scan results:
```bash
python3 main.py --scan-file scan_results.json -u admin -p password
```

Use previously collected device data:
```bash
python3 main.py --data-file collected_data.json
```

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

- `final_map.json`: Structured JSON connection map
- `connections.txt`: Human-readable connection descriptions
- `scan_results.json`: Discovered Mikrotik devices (when scanning)
- `collected_data.json`: Raw device data (when collecting)
- `credentials.encrypted`: Encrypted SSH credentials (when storing)

## Security

- SSH credentials are encrypted using AES with a master password
- Each credential entry is encrypted separately
- Master password is never stored on disk
- All sensitive data is stored in encrypted format

## Modules

- `scanner/`: Network scanning functionality
- `ssh/`: SSH connection and data collection
- `data/`: Data coordination and storage
- `mapping/`: Connection mapping logic
- `credential_manager.py`: Encrypted credential storage

## License

MIT License