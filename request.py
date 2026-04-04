import requests
import json
import os

# Load session data from login.py output
SESSION_FILE = os.path.join(os.path.dirname(__file__), "session_cookies.json")
if not os.path.exists(SESSION_FILE):
    raise FileNotFoundError("session_cookies.json not found — run login.py first")

with open(SESSION_FILE) as f:
    session_data = json.load(f)

auth_code = session_data["auth_code"]
cookie_header = "; ".join(
    f"{c['name']}={c['value']}" for c in session_data["cookies"]
)

print(f"Using auth_code: {auth_code}")

url = "https://www.solidgps.com/custom-monorepo/dashboard/request.php"

params = {
    "IMEI": "your_imei_here",
    "account_id": "your_account_id_here",
    "auth_code": auth_code,
    "startEpoch": "",
    "endEpoch": "",
    "tracking_code": "",
}

headers = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "cookie": cookie_header,
    "priority": "u=1, i",
    "referer": "https://www.solidgps.com/dashboard/",
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "x-requested-with": "XMLHttpRequest",
}

response = requests.get(url, params=params, headers=headers)

print(f"Status: {response.status_code}")
print(f"URL: {response.url}")
print()

try:
    data = response.json()
    print(json.dumps(data, indent=2))
except ValueError:
    print(response.text)
