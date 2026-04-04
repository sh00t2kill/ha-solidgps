import re
import json
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
    REQUEST_URL = f"{BASE_URL}/custom-monorepo/dashboard/request.php"

    def __init__(self, username: str, password: str, account_id: str | None = None, imei: str | None = None):
        self.username = username
        self.password = password
        self.account_id = account_id
        self.imei = imei          # default device; set to first device after login if None
        self.auth_code: str | None = None
        self.devices: dict = {}   # keyed by IMEI, values are device metadata from dashboard
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

        # Parse var account_info = {...}
        account_match = re.search(r'var account_info\s*=\s*(\{[^;]+\})', resp.text)
        if account_match:
            account_info = json.loads(account_match.group(1))
            self.auth_code = account_info.get("AuthCode")
            if self.account_id is None:
                self.account_id = str(account_info.get("AccountID", ""))
            print(f"  account_id: {self.account_id}")
            print(f"  auth_code:  {self.auth_code}")
        else:
            print("  WARNING: account_info not found in dashboard HTML")

        # Parse var device_info = {...} — keys are IMEIs
        device_match = re.search(r'var device_info\s*=\s*(\{.+?\});', resp.text)
        if device_match:
            self.devices = json.loads(device_match.group(1))
            if self.imei is None:
                self.imei = next(iter(self.devices))
            print(f"  devices:    {list(self.devices.keys())}")
            print(f"  default:    {self.imei}")
        else:
            print("  WARNING: device_info not found in dashboard HTML")

    # ------------------------------------------------------------------
    # Data requests
    # ------------------------------------------------------------------

    def get_tracking_data(self, imei: str | None = None, start_epoch: str = "", end_epoch: str = "", tracking_code: str = "") -> dict | str:
        """Fetch GPS tracking data for a device.

        Args:
            imei: IMEI of the device to query. Defaults to the first device found at login.
        """
        if not self.auth_code or not self.account_id:
            raise RuntimeError("Not logged in — call login() first")
        target_imei = imei or self.imei
        if not target_imei:
            raise RuntimeError("No IMEI specified and no default device available")

        response = self._session.get(
            self.REQUEST_URL,
            params={
                "IMEI": target_imei,
                "account_id": self.account_id,
                "auth_code": self.auth_code,
                "startEpoch": start_epoch,
                "endEpoch": end_epoch,
                "tracking_code": tracking_code,
            },
            headers={
                "accept": "*/*",
                "priority": "u=1, i",
                "referer": self.DASHBOARD_URL,
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "x-requested-with": "XMLHttpRequest",
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
        return self.devices[target_imei].get("BatteryStatus")
