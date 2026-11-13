import contextlib
import io
import json
import os
from datetime import datetime, timezone
from time import sleep
from solidgps import SolidGPS

# --- Configuration ---
# Credentials come from SOLIDGPS_USERNAME / SOLIDGPS_PASSWORD if set (used by CI),
# otherwise from the gitignored credentials.py (see credentials.example.py).
USERNAME = os.environ.get("SOLIDGPS_USERNAME")
PASSWORD = os.environ.get("SOLIDGPS_PASSWORD")
if not (USERNAME and PASSWORD):
    from credentials import USERNAME, PASSWORD

# ---------------------

# In CI (GitHub sets CI=true) the logs may be public, so nothing identifying
# (IMEI, account id, tokens, coordinates) is printed — only pass/fail summaries.
CI = os.environ.get("CI", "").lower() == "true"


def quiet():
    """Swallow the library's verbose prints in CI; no-op locally."""
    return contextlib.redirect_stdout(io.StringIO()) if CI else contextlib.nullcontext()


def check(ok: bool, message: str) -> None:
    if CI:
        print(f"{'PASS' if ok else 'FAIL'}: {message}")
    if not ok:
        raise SystemExit(f"Integration check failed: {message}")


gps = SolidGPS(username=USERNAME, password=PASSWORD)

with quiet():
    logged_in = gps.login()
if not logged_in:
    raise SystemExit("Login failed — check credentials")
check(bool(gps.devices), "login succeeded and at least one device was found")
print()

# Fetch tracking data (history endpoint — gps_data here is normally empty;
# real-time fixes come from the refresh endpoint below)
print("Fetching tracking data...")
data = gps.get_tracking_data()
if not CI:
    print(json.dumps(data, indent=2) if isinstance(data, (dict, list)) else data)
check(isinstance(data, dict) and bool(data.get("success")), "tracking (history) endpoint returned success")

battery = gps.get_battery_status()
if not CI:
    print(f"Battery: {battery}%")
check(battery is not None, "battery status retrieved")

# Poll the live refresh endpoint for the freshest GPS fix
print("\nPolling live refresh endpoint...")
fix = gps.poll_live_fix()
if not CI:
    print(f"Live fix: {json.dumps(fix, indent=2) if fix else 'no new fix reported yet'}")

loc = gps.get_latest_location()
check(loc is not None, "a latest location is known (live, GPS history or cell)")
when = datetime.fromtimestamp(loc["utc"] / 1000, timezone.utc)
if CI:
    print(f"Latest location source: {loc['source']}, age: {datetime.now(timezone.utc) - when}")
else:
    print(f"\nLatest location: {loc['latitude']}, {loc['longitude']} "
          f"@ {when:%Y-%m-%d %H:%M:%S} UTC (source: {loc['source']})")

if CI:
    raise SystemExit(0)

# Example: refresh device info (battery, status, etc.) periodically
sleep(10)
gps.refresh()
print(f"Battery (refreshed): {gps.get_battery_status()}%")

fix = gps.poll_live_fix()
print(f"Live fix (polled again): {json.dumps(fix, indent=2) if fix else 'no new fix reported yet'}")
