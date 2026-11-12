import re
import json
import time
from datetime import datetime, timedelta, timezone
import requests


BROWSER_HEADERS = {
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


class SolidGPS:
    BASE_URL = "https://www.solidgps.com"
    LOGIN_URL = f"{BASE_URL}/login/"
    DASHBOARD_URL = f"{BASE_URL}/dashboard/"
    HISTORY_URL = f"{BASE_URL}/custom-monorepo/dashboard-page/api/dashboard-api.php?endpoint=history"
    REFRESH_API_URL = f"{BASE_URL}/custom-monorepo/dashboard-page/api/dashboard-api.php?endpoint=refresh"

    def __init__(self, username: str, password: str, account_id: str | None = None, imei: str | None = None):
        self.username = username
        self.password = password
        self.account_id = account_id
        self.imei = imei          # default device; set to first device after login if None
        self.auth_code: str | None = None
        self.devices: dict = {}   # keyed by IMEI, values are device metadata from dashboard
        self._cursor: dict[str, str] = {}   # per-IMEI update_time cursor for get_refresh_data
        self.live_fix: dict[str, dict] = {}  # per-IMEI latest fix from the refresh endpoint
        self._session = requests.Session()
        self._session.headers.update({
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            **BROWSER_HEADERS,
        })

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def login(self) -> bool:
        """Log in to SolidGPS and extract account info into memory."""
        self._session.cookies.clear()
        nonce = self._fetch_nonce()
        if not self._post_login(nonce):
            return False
        self.refresh()
        return True

    def refresh(self):
        """Re-fetch the dashboard to update device info (battery, status, etc.)."""
        self._extract_dashboard_info()

    def _fetch_nonce(self) -> str:
        print("Fetching login page for nonce...")
        resp = self._session.get(self.LOGIN_URL, headers={
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "upgrade-insecure-requests": "1",
        })
        print(f"  Status: {resp.status_code}")

        match = re.search(
            r'name=["\']user-registration-login-nonce["\'][^>]*value=["\']([^"\']+)["\']'
            r'|value=["\']([^"\']+)["\'][^>]*name=["\']user-registration-login-nonce["\']',
            resp.text,
        )
        if not match:
            match = re.search(r'"user_registration_login_nonce"\s*:\s*"([^"]+)"', resp.text)

        if match:
            nonce = next(g for g in match.groups() if g)
            print(f"  Nonce: {nonce}")
            return nonce

        raise RuntimeError("Could not find login nonce on login page")

    def _post_login(self, nonce: str) -> bool:
        print("Submitting login...")
        resp = self._session.post(
            self.LOGIN_URL,
            data={
                "username": self.username,
                "password": self.password,
                "user-registration-login-nonce": nonce,
                "_wp_http_referer": "/login/",
                "rememberme": "forever",
                "login": "Login",
                "redirect": "",
            },
            headers={
                "content-type": "application/x-www-form-urlencoded",
                "origin": self.BASE_URL,
                "referer": self.LOGIN_URL,
                "cache-control": "max-age=0",
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "same-origin",
                "sec-fetch-user": "?1",
                "upgrade-insecure-requests": "1",
                "priority": "u=0, i",
            },
            allow_redirects=True,
        )
        print(f"  Status: {resp.status_code} | Final URL: {resp.url}")
        success = "/login/" not in resp.url
        print(f"  {'SUCCESS' if success else 'FAILED'}")
        return success

    def _extract_dashboard_info(self):
        print("Fetching dashboard to extract account info...")
        resp = self._session.get(self.DASHBOARD_URL, headers={
            "referer": self.BASE_URL + "/",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "upgrade-insecure-requests": "1",
        })
        print(f"  Status: {resp.status_code}")
        html = resp.text

        # Parse window.DASHBOARD_DATA = {...} — valid JSON blob introduced in 2026 redesign
        dashboard_match = re.search(r'window\.DASHBOARD_DATA\s*=\s*(\{)', html)
        if dashboard_match:
            try:
                dashboard_data, _ = json.JSONDecoder().raw_decode(html, dashboard_match.start(1))
                user = dashboard_data.get("user", {})
                if self.account_id is None:
                    self.account_id = str(user.get("AccountID", ""))
                print(f"  account_id: {self.account_id}")
                devices_list = dashboard_data.get("devices", [])
                self.devices = {d["imei"]: d for d in devices_list if "imei" in d}
                if self.imei is None and self.devices:
                    self.imei = next(iter(self.devices))
                print(f"  devices:    {list(self.devices.keys())}")
                print(f"  default:    {self.imei}")
            except (json.JSONDecodeError, KeyError) as exc:
                print(f"  WARNING: Failed to parse DASHBOARD_DATA: {exc}")
        else:
            print("  WARNING: DASHBOARD_DATA not found in dashboard HTML")

        # Extract csrf_token from window.PHP_CONFIG (JS object literal, not valid JSON)
        csrf_match = re.search(r'csrf_token\s*:\s*["\']([^"\']+)["\']', html)
        if csrf_match:
            self.auth_code = csrf_match.group(1)
            print(f"  auth_code:  {self.auth_code}")
        else:
            print("  WARNING: csrf_token not found in dashboard HTML")

    # ------------------------------------------------------------------
    # Data requests
    # ------------------------------------------------------------------

    def get_tracking_data(self, imei: str | None = None, start_epoch: int | None = None, end_epoch: int | None = None) -> dict | str:
        """Fetch GPS tracking data for a device.

        Args:
            imei: IMEI of the device to query. Defaults to the first device found at login.
        """
        if not self.account_id:
            raise RuntimeError("Not logged in — call login() first")
        target_imei = imei or self.imei
        if not target_imei:
            raise RuntimeError("No IMEI specified and no default device available")
        now = int(time.time())
        response = self._session.post(
            self.HISTORY_URL,
            data={
                "IMEI": target_imei,
                "start_epoch": start_epoch if start_epoch is not None else now - 604800,
                "end_epoch": end_epoch if end_epoch is not None else now,
            },
            headers={
                "accept": "*/*",
                "content-type": "application/x-www-form-urlencoded",
                "origin": self.BASE_URL,
                "priority": "u=1, i",
                "referer": self.DASHBOARD_URL,
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                **BROWSER_HEADERS,
            },
        )
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return response.text

    def get_battery_status(self, imei: str | None = None) -> int | None:
        """Return battery percentage (0-100) for a device, sourced from dashboard device_info."""
        if not self.devices:
            raise RuntimeError("No device info — call login() first")
        target_imei = imei or self.imei
        if not target_imei or target_imei not in self.devices:
            raise RuntimeError(f"IMEI {target_imei!r} not found in devices")
        device = self.devices[target_imei]
        return device.get("batteryStatus")

    def get_refresh_data(self, imei: str | None = None, update_time: str | None = None) -> dict | str:
        """Poll the lightweight refresh endpoint for GPS fixes reported since update_time.

        This is the same endpoint the live dashboard polls every few seconds; it only
        returns a device entry when a new fix has been reported since update_time, so
        callers should keep using the last response's data.update_time as the next
        cursor to avoid re-fetching data that hasn't changed.
        """
        if not self.account_id:
            raise RuntimeError("Not logged in — call login() first")
        target_imei = imei or self.imei
        if not target_imei:
            raise RuntimeError("No IMEI specified and no default device available")
        response = self._session.post(
            self.REFRESH_API_URL,
            data={
                "IMEI": target_imei,
                "update_time": update_time or self._default_update_time(),
            },
            headers={
                "accept": "*/*",
                "content-type": "application/x-www-form-urlencoded",
                "origin": self.BASE_URL,
                "priority": "u=1, i",
                "referer": self.DASHBOARD_URL,
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                **BROWSER_HEADERS,
            },
        )
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return response.text

    # How far back the first refresh poll looks. A device that has been quiet for
    # more than a day (sleeping tracker) would otherwise return nothing at all.
    INITIAL_LOOKBACK_DAYS = 30

    @classmethod
    def _default_update_time(cls) -> str:
        """Cursor fallback when no prior refresh response exists (e.g. first poll)."""
        return (datetime.now(timezone.utc) - timedelta(days=cls.INITIAL_LOOKBACK_DAYS)).strftime("%Y-%m-%d %H:%M:%S")

    def get_latest_location(self, imei: str | None = None) -> dict | None:
        """Return the newest known location across every source, by timestamp.

        Candidates: live refresh fix, history gps_data, history cell_data.
        Returns the point plus a "source" key, or None if nothing is known.
        """
        target_imei = imei or self.imei
        candidates: list[tuple[str, dict]] = []

        # Only poll when we have no fix yet; later calls reuse the stored one.
        if target_imei not in self.live_fix:
            self.poll_live_fix(target_imei)
        if target_imei in self.live_fix:
            candidates.append(("refresh", self.live_fix[target_imei]))

        history = self.get_tracking_data(target_imei)
        if isinstance(history, dict) and history.get("success"):
            dev = history.get("data", {}).get("devices", {}).get(target_imei, {})
            candidates += [("history_gps", p) for p in dev.get("gps_data") or []]
            candidates += [("history_cell", p) for p in dev.get("cell_data") or []]

        if not candidates:
            return None
        source, point = max(candidates, key=lambda c: c[1].get("utc", 0))
        return {**point, "source": source}

    def poll_live_fix(self, imei: str | None = None) -> dict | None:
        """Poll the refresh endpoint and update self.live_fix[imei], tracking the cursor internally.

        Returns the freshest fix for the device if a new one was reported, else None.
        """
        target_imei = imei or self.imei
        if not target_imei:
            raise RuntimeError("No IMEI specified and no default device available")
        resp = self.get_refresh_data(target_imei, self._cursor.get(target_imei))
        if not isinstance(resp, dict) or not resp.get("success"):
            return None
        data = resp.get("data", {})
        if data.get("update_time"):
            self._cursor[target_imei] = data["update_time"]
        devices = data.get("devices", {})
        device = devices.get(target_imei) if isinstance(devices, dict) else None
        if device and device.get("gps_data"):
            self.live_fix[target_imei] = max(device["gps_data"], key=lambda p: p.get("utc", 0))
            return self.live_fix[target_imei]
        return None
