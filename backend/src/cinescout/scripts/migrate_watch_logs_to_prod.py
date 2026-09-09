"""One-off: copy a user's local watch-log diary to the production API.

Reads watch_logs for a local user directly from the local database, then
POSTs each entry to the production /api/watch-logs endpoint over HTTPS
using a bearer token for the equivalent production account. No direct
production DB access is used or required.

Notes:
- showing_id is never carried over (local showing IDs are meaningless in
  the production DB) — every entry is recreated as a manual log
  (film_id + watched_date). Rating/comment/date survive; the "watched at
  <cinema>" link does not.
- film_id is a deterministic slug ("title-year"), so it matches
  automatically if that film has already been scraped/matched in
  production. If not, and the local film has a tmdb_id, the script backfills
  it in production via POST /api/films/ensure (same TMDb lookup the
  Letterboxd import uses) before retrying. Films with no tmdb_id (rare
  placeholder rows) are skipped and reported.
- Safe to re-run: existing production entries are fetched first and
  matched on (film_id, watched_date) to avoid creating duplicates.

Usage:
    cd backend
    source .venv/bin/activate
    CINESCOUT_PROD_TOKEN=<jwt> python -m cinescout.scripts.migrate_watch_logs_to_prod \\
        --username RobKoeling
"""

import argparse
import asyncio
import logging
import os
import ssl
import sys
from pathlib import Path

import httpx
from sqlalchemy import select

from cinescout.database import AsyncSessionLocal
from cinescout.models.film import Film
from cinescout.models.user import User
from cinescout.models.watch_log import WatchLog

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_API_URL = "https://cinescout-api.fly.dev/api"

# On this corporate network, a Zscaler TLS-inspecting proxy MITMs outbound
# HTTPS, so the default trust store rejects it. Trust the Zscaler CA on top
# of (not instead of) the system defaults, matching the Dockerfile's approach.
_ZSCALER_BUNDLE = Path(__file__).resolve().parents[3] / "certs" / "zscaler-bundle.crt"


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if _ZSCALER_BUNDLE.exists():
        ctx.load_verify_locations(cafile=str(_ZSCALER_BUNDLE))
    return ctx


async def _load_local_watch_logs(username: str) -> list[dict]:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if user is None:
            logger.error(f"No local user named {username!r} found")
            return []

        result = await db.execute(
            select(WatchLog, Film.tmdb_id)
            .join(Film, Film.id == WatchLog.film_id)
            .where(WatchLog.user_id == user.id)
            .order_by(WatchLog.id)
        )
        rows = result.all()
        return [
            {
                "film_id": log.film_id,
                "tmdb_id": tmdb_id,
                "watched_date": log.watched_date.isoformat(),
                "rating": float(log.rating) if log.rating is not None else None,
                "comment": log.comment,
            }
            for log, tmdb_id in rows
        ]


async def _migrate(api_url: str, token: str, username: str) -> None:
    local_logs = await _load_local_watch_logs(username)
    if not local_logs:
        logger.warning("Nothing to migrate")
        return
    logger.info(f"Loaded {len(local_logs)} local watch-log entries for {username!r}")

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(
        base_url=api_url, headers=headers, timeout=30.0, verify=_ssl_context()
    ) as client:
        existing_resp = await client.get("/watch-logs", params={"limit": 500})
        existing_resp.raise_for_status()
        existing = {(e["film_id"], e["watched_date"]) for e in existing_resp.json()}
        logger.info(f"Production already has {len(existing)} entries for this account")

        created = 0
        backfilled_films = 0
        skipped_duplicate = 0
        skipped_missing_film: list[str] = []
        errors: list[str] = []

        for entry in local_logs:
            key = (entry["film_id"], entry["watched_date"])
            if key in existing:
                skipped_duplicate += 1
                continue

            payload = {
                "film_id": entry["film_id"],
                "watched_date": entry["watched_date"],
                "rating": entry["rating"],
                "comment": entry["comment"],
            }
            resp = await client.post("/watch-logs", json=payload)

            if resp.status_code == 404 and entry["tmdb_id"]:
                ensure_resp = await client.post("/films/ensure", params={"tmdb_id": entry["tmdb_id"]})
                if ensure_resp.status_code == 200:
                    backfilled_films += 1
                    # The film may get a different id in production than
                    # locally (e.g. the local match happened before the
                    # release year was known, so the local slug lacks a
                    # year suffix that a fresh TMDb lookup now includes).
                    payload["film_id"] = ensure_resp.json()["id"]
                    resp = await client.post("/watch-logs", json=payload)

            if resp.status_code == 201:
                created += 1
            elif resp.status_code == 404:
                skipped_missing_film.append(entry["film_id"])
            else:
                errors.append(f"{entry['film_id']} ({entry['watched_date']}): {resp.status_code} {resp.text}")

    logger.info("Migration complete:")
    logger.info(f"  Created:            {created}")
    logger.info(f"  Films backfilled:   {backfilled_films}")
    logger.info(f"  Already present:    {skipped_duplicate}")
    logger.info(f"  Missing film:       {len(skipped_missing_film)}")
    if skipped_missing_film:
        for film_id in skipped_missing_film:
            logger.info(f"    - {film_id}")
    if errors:
        logger.error(f"  Errors:             {len(errors)}")
        for err in errors:
            logger.error(f"    - {err}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--username", required=True, help="Local username whose watch logs to migrate")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help=f"Production API base URL (default: {DEFAULT_API_URL})")
    args = parser.parse_args()

    token = os.environ.get("CINESCOUT_PROD_TOKEN")
    if not token:
        logger.error("Set CINESCOUT_PROD_TOKEN to a valid production JWT (see login instructions)")
        sys.exit(1)

    asyncio.run(_migrate(args.api_url, token, args.username))
