import json
from time import sleep
from solidgps import SolidGPS

# --- Configuration ---
USERNAME = "your@email.com"  # replace with your Solid GPS account email
PASSWORD = "yourpassword"   # replace with your Solid GPS account password

# ---------------------

gps = SolidGPS(username=USERNAME, password=PASSWORD)

if not gps.login():
    raise SystemExit("Login failed — check credentials")
print()

# Fetch tracking data
print("Fetching tracking data...")
data = gps.get_tracking_data()
print(json.dumps(data, indent=2) if isinstance(data, (dict, list)) else data)

print(f"Battery: {gps.get_battery_status()}%")

# Example: refresh device info (battery, status, etc.) periodically
sleep(10)
gps.refresh()
print(f"Battery (refreshed): {gps.get_battery_status()}%")