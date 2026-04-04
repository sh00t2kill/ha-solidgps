# Solid GPS — Home Assistant Integration

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration for [Solid GPS](https://www.solidgps.com) GPS trackers.

## Features

- **Device Tracker** — shows your device on the HA map with real-time GPS coordinates
- **Battery sensor** — current battery level (%)
- **Status sensor** — device status (e.g. Sleeping till Movement, Active)
- **Last Update sensor** — timestamp of the last GPS ping
- **Next Update sensor** — when the next ping is expected
- **Lifetime Distance sensor** — total distance travelled

All data is polled automatically every 30 seconds via the Solid GPS dashboard API.

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** → **Custom repositories**
3. Add `https://github.com/sh00t2kill/ha-solidgps` with category **Integration**
4. Install **Solid GPS**
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/solidgps` folder into your HA `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Integrations → Add Integration**
2. Search for **Solid GPS**
3. Enter your Solid GPS account email and password

The integration will automatically discover all devices linked to your account.

## Entities

For each GPS device linked to your account, the following entities are created:

| Entity | Entity ID | Description |
|---|---|---|
| Device Tracker | `device_tracker.<IMEI>` | GPS location on the HA map |
| Battery | `sensor.<nickname>_battery` | Battery % |
| Status | `sensor.<nickname>_status` | Device status |
| Last Update | `sensor.<nickname>_last_update` | Last GPS ping timestamp |
| Next Update | `sensor.<nickname>_next_update` | Next expected ping timestamp |
| Lifetime Distance | `sensor.<nickname>_lifetime_distance` | Total distance in metres |
