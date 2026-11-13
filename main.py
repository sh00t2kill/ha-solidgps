import json
from datetime import datetime, timezone
from time import sleep
from solidgps import SolidGPS

# --- Configuration ---
from credentials import USERNAME, PASSWORD

# ---------------------

gps = SolidGPS(username=USERNAME, password=PASSWORD)

if not gps.login():
    raise SystemExit("Login failed — check credentials")
print()

# Fetch tracking data (history endpoint — gps_data here is normally empty;
# real-time fixes come from the refresh endpoint below)
print("Fetching tracking data...")
data = gps.get_tracking_data()
print(json.dumps(data, indent=2) if isinstance(data, (dict, list)) else data)

print(f"Battery: {gps.get_battery_status()}%")

# Poll the live refresh endpoint for the freshest GPS fix
print("\nPolling live refresh endpoint...")
fix = gps.poll_live_fix()
print(f"Live fix: {json.dumps(fix, indent=2) if fix else 'no new fix reported yet'}")

loc = gps.get_latest_location()
if loc:
    when = datetime.fromtimestamp(loc["utc"] / 1000, timezone.utc)
    print(f"\nLatest location: {loc['latitude']}, {loc['longitude']} "
          f"@ {when:%Y-%m-%d %H:%M:%S} UTC (source: {loc['source']})")
else:
    print("\nLatest location: none known")

# Example: refresh device info (battery, status, etc.) periodically
sleep(10)
gps.refresh()
print(f"Battery (refreshed): {gps.get_battery_status()}%")

fix = gps.poll_live_fix()
print(f"Live fix (polled again): {json.dumps(fix, indent=2) if fix else 'no new fix reported yet'}")