import re
import json
import requests

LOGIN_URL = "https://www.solidgps.com/login/"
USERNAME = "your@email.com"  # replace with your Solid GPS account email
PASSWORD = "yourpassword"   # replace with your Solid GPS account password

session = requests.Session()

session.headers.update({
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
})

# Step 1: GET the login page to extract a fresh nonce
print("Fetching login page...")
get_resp = session.get(LOGIN_URL, headers={
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "upgrade-insecure-requests": "1",
})
print(f"  Status: {get_resp.status_code}")

nonce_match = re.search(r'name=["\']user-registration-login-nonce["\'][^>]*value=["\']([^"\']+)["\']|value=["\']([^"\']+)["\'][^>]*name=["\']user-registration-login-nonce["\']', get_resp.text)
if not nonce_match:
    # Try alternate pattern (script block)
    nonce_match = re.search(r'"user_registration_login_nonce"\s*:\s*"([^"]+)"', get_resp.text)

if nonce_match:
    nonce = next(g for g in nonce_match.groups() if g)
    print(f"  Nonce found: {nonce}")
else:
    print("  WARNING: Could not find nonce — using hardcoded fallback (may be expired)")
    nonce = "3689d6f536"

# Step 2: POST login credentials
print("\nSubmitting login...")
post_headers = {
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.solidgps.com",
    "referer": LOGIN_URL,
    "cache-control": "max-age=0",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "priority": "u=0, i",
}

payload = {
    "username": USERNAME,
    "password": PASSWORD,
    "user-registration-login-nonce": nonce,
    "_wp_http_referer": "/login/",
    "rememberme": "forever",
    "login": "Login",
    "redirect": "",
}

post_resp = session.post(
    LOGIN_URL,
    data=payload,
    headers=post_headers,
    allow_redirects=True,
)

print(f"  Status: {post_resp.status_code}")
print(f"  Final URL: {post_resp.url}")

# Check for successful login (WordPress typically redirects away from /login/ on success)
if "/login/" not in post_resp.url:
    print("\nLogin appears SUCCESSFUL (redirected away from login page)")
else:
    print("\nLogin may have FAILED (still on login page)")
    if "incorrect" in post_resp.text.lower() or "error" in post_resp.text.lower():
        error_match = re.search(r'<[^>]*class="[^"]*(?:error|message)[^"]*"[^>]*>(.*?)</[^>]+>', post_resp.text, re.DOTALL)
        if error_match:
            print(f"  Error message: {re.sub(r'<[^>]+>', '', error_match.group(1)).strip()}")

# Print session cookies (useful for copying into request.py or other scripts)
print("\nSession cookies:")
for name, value in session.cookies.items():
    print(f"  {name} = {value}")

# Step 3: Fetch the dashboard page and look for auth_code
print("\nFetching dashboard to locate auth_code...")
dashboard_resp = session.get(
    "https://www.solidgps.com/dashboard/",
    headers={
        "referer": "https://www.solidgps.com/",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "upgrade-insecure-requests": "1",
    },
)
print(f"  Status: {dashboard_resp.status_code}")

# Search for auth_code in the page (JS variable, data attribute, or inline JSON)
auth_code = None
auth_code_match = re.search(
    r'auth_code["\']?\s*[:=]\s*["\']([a-f0-9]{40,})["\']',
    dashboard_resp.text,
    re.IGNORECASE,
)
if auth_code_match:
    auth_code = auth_code_match.group(1)
    print(f"  auth_code found (labelled): {auth_code}")
else:
    # Broader search for first 64-char hex string in the page
    auth_code_match = re.search(r'["\']([a-f0-9]{64})["\']', dashboard_resp.text)
    if auth_code_match:
        auth_code = auth_code_match.group(1)
        print(f"  auth_code found (hex-64): {auth_code}")
    else:
        print("  auth_code NOT found in dashboard HTML")

# Save cookies and auth_code to a file for reuse
cookies_list = [
    {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
    for c in session.cookies
]
session_data = {
    "auth_code": auth_code,
    "cookies": cookies_list,
}
with open("session_cookies.json", "w") as f:
    json.dump(session_data, f, indent=2)
print("\nCookies and auth_code saved to session_cookies.json")
