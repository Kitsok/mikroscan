# Changelog

This file records the main user-visible changes to Mikroscan.

## Unreleased

### Added
- Home Assistant add-on packaging for installation through
  `Settings -> Apps`
- Home Assistant custom integration under the `mikroscan` domain
- Home Assistant dashboard card for embedding the topology map
- Local browser UI for the topology map with dragging, collapse, and
  details
- Layout persistence via `data/topology_layout.json`
- Structured topology export in `data/topology_graph.json`
- Local API server for topology/status/scan actions
- WireGuard and ZeroTier interface rendering in topology output
- PoE monitor collection and PoE labels in topology output
- Unresolved host listing appended to `data/topology.txt`

### Changed
- Live collection now defaults to the RouterOS API backend
- `python3 main.py --scan-file` now refreshes data, rebuilds map files,
  and regenerates topology
- `python3 main.py --generate-topology` now defaults to
  `data/collected_data.json`
- Topology output is now rendered as a rooted physical tree with WAN
  chains and shared segments
- Project and Home Assistant naming now use `Mikroscan`

### Fixed
- Data collection gaps around bridge hosts, DHCP lease retrieval, and
  RouterOS command error handling
- Shared-segment topology reduction and remote-port labeling
- Duplicate-device rendering caused by repeated identities or shared
  graph paths
- API-backed PoE runtime collection
- CLI failure propagation for scan, map, and topology workflows
- Credential-store handling for missing, unusable, and existing stores

## Earlier Milestones

### Initial mapper
- Added subnet scanning, sequential device collection, connection map
  generation, and encrypted credential storage

### Topology builder
- Added rooted topology generation based on collected RouterOS data

### API-first collection
- Added native RouterOS API collection support and made it the default
  backend

### Browser map
- Added a local web UI and topology JSON model as the foundation for
  interactive visualization
