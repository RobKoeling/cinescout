"""Fetch a fresh Curzon auth token and push it to Fly.io as a secret.

Run from a machine with residential/home IP (not a cloud server):

    python -m cinescout.scripts.refresh_curzon_token

The token expires after 12 hours. Set up a cron job or launchd job to run
this every ~10 hours to keep Curzon scraping working on Fly.io.
"""

import re
import subprocess
import sys

import httpx

CURZON_URL = "https://www.curzon.com/venues/soho/"
FLY_APP = "cinescout-api"
SECRET_NAME = "CURZON_AUTH_TOKEN"


def main() -> None:
    print(f"Fetching Curzon auth token from {CURZON_URL}...")
    r = httpx.get(
        CURZON_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html",
        },
        follow_redirects=True,
        timeout=15,
        verify=False,
    )
    r.raise_for_status()

    m = re.search(r'"authToken"\s*:\s*"([^"]+)"', r.text)
    if not m:
        print("ERROR: authToken not found in page HTML", file=sys.stderr)
        sys.exit(1)

    token = m.group(1)
    print(f"Token extracted (first 40 chars): {token[:40]}...")

    print(f"Setting Fly.io secret {SECRET_NAME} on app {FLY_APP}...")
    result = subprocess.run(
        ["fly", "secrets", "set", f"{SECRET_NAME}={token}", "-a", FLY_APP],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: fly secrets set failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    print("Done. Token pushed to Fly.io.")
    print("Note: machines will restart automatically to pick up the new secret.")


if __name__ == "__main__":
    main()
