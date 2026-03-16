# Mikroscan

Mikroscan provides an interactive MikroTik topology map inside Home
Assistant and can refresh the topology directly from your network
devices.

## What this app does

- serves the Mikroscan browser UI through Home Assistant ingress
- keeps topology data and command logs in persistent app storage
- can trigger live refreshes using the configured device credentials

## Configuration

- `backend`: `api` or `ssh`
- `api_port`: RouterOS API port, usually `8728`
- `ssh_port`: SSH port, usually `22`
- `api_ssl`: enable RouterOS API TLS when required
- `verbose`: enable verbose server logging
- `device_username`: optional MikroTik username for live actions
- `device_password`: optional MikroTik password for live actions

If `device_username` and `device_password` are left empty, the app
still starts and the current topology can be viewed, but live scan
actions will fail unless credentials are already available inside the
app's persistent storage.

## Stored data

Mikroscan stores its persistent files under the app's `/data`
directory:

- topology JSON and text outputs
- collected device data
- encrypted credential store
- command logs

## Notes

- The app UI is exposed through Home Assistant ingress.
- The internal Mikroscan server listens on port `8099` inside the
  container.
- Live refreshes require network connectivity from Home Assistant to
  your MikroTik devices.
