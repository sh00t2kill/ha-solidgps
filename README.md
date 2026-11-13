# Solid GPS — Home Assistant Integration

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration for [Solid GPS](https://www.solidgps.com) GPS trackers.

## Features

- **Device Tracker** — shows your device on the HA map with real-time GPS coordinates
- **Predicted Location tracker** — a best-guess location that falls back to Solid GPS's predicted zones when only a cell-tower fix is available (see [How locations are chosen](#how-locations-are-chosen))
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
| Predicted Location | `device_tracker.<IMEI>_predicted` | Real fix when newest, otherwise the predicted zone location |
| Battery | `sensor.<nickname>_battery` | Battery % |
| Status | `sensor.<nickname>_status` | Device status |
| Last Update | `sensor.<nickname>_last_update` | Last GPS ping timestamp |
| Next Update | `sensor.<nickname>_next_update` | Next expected ping timestamp |
| Lifetime Distance | `sensor.<nickname>_lifetime_distance` | Total distance in metres |

## How locations are chosen

Solid GPS reports location from several sources: the live refresh fix, GPS history, and cell-tower fixes. A cell-tower fix is only accurate to roughly 1–2 km, so it is a rough estimate rather than a real GPS position. The newest point, by timestamp, across all sources is always the one used, so an old cell fix never overrides a newer GPS fix.

### Device Tracker (`device_tracker.<IMEI>`)

Shows the newest point as reported, including a raw cell-tower fix when that is the most recent report. Useful attributes:

| Attribute | Meaning |
|---|---|
| `location_source` | `refresh`, `history_gps` or `history_cell` |
| `using_live_fix` / `using_cell_location` | Which kind of fix is being shown |

### Predicted Location tracker (`device_tracker.<IMEI>_predicted`)

- **Newest report is a GPS fix:** it shows that fix, same as the Device Tracker.
- **Newest report is a cell-tower fix:** Solid GPS attaches a list of predicted zones (places the device has been seen near that tower, each with a 50 m radius). The tracker works out one location from them:
  1. Each zone is treated as a seed, and its cluster is every zone within 250 m of it.
  2. The largest cluster wins, and zones outside it are ignored as outliers. For example, two zones a few metres apart and a third 1 km away give the centroid of the pair.
  3. The location is the centroid (average position) of the zones in that cluster.
  4. `location_accuracy` is set so the circle on the map covers every zone used, including its 50 m radius.
  5. If two separate clusters are the same size there is no basis to choose, so all zones are used and `zones_ambiguous` is set. The accuracy circle will be large.
- **No usable zones:** it falls back to the cell-tower point itself, with that fix's accuracy.

Attributes: `predicted` (true when a zone-based location is shown), `zones_used`, `zones_excluded`, `zones_ambiguous`, plus `location_source` (`predicted_zone` when zones were used) and the same attributes as the Device Tracker.

A predicted location is a guess. Check `predicted` and `location_accuracy` before using it in automations such as home/away.
