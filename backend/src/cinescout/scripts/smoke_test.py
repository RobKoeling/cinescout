"""Smoke test: check that each cinema has at least a minimum number of showings on a given date."""

import argparse
import asyncio
import sys
from datetime import date, datetime, time
from typing import TypedDict
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from cinescout.database import AsyncSessionLocal
from cinescout.models.cinema import Cinema
from cinescout.models.showing import Showing

LONDON_TZ = ZoneInfo("Europe/London")
DEFAULT_MIN_SHOWINGS = 1


class CinemaResult(TypedDict):
    name: str
    count: int
    ok: bool


class SmokeTestReport(TypedDict):
    check_date: date
    min_showings: int
    results: list[CinemaResult]
    all_ok: bool


async def run_smoke_test(check_date: date, min_showings: int = DEFAULT_MIN_SHOWINGS) -> SmokeTestReport:
    """Query showings per cinema for a given date and return a structured report."""
    day_start = datetime.combine(check_date, time.min, tzinfo=LONDON_TZ)
    day_end = datetime.combine(check_date, time.max, tzinfo=LONDON_TZ)

    results: list[CinemaResult] = []

    async with AsyncSessionLocal() as db:
        cinemas_result = await db.execute(select(Cinema).order_by(Cinema.name))
        cinemas = cinemas_result.scalars().all()

        for cinema in cinemas:
            count_result = await db.execute(
                select(func.count())
                .select_from(Showing)
                .where(
                    Showing.cinema_id == cinema.id,
                    Showing.start_time >= day_start,
                    Showing.start_time <= day_end,
                )
            )
            count = count_result.scalar_one()
            results.append({"name": cinema.name, "count": count, "ok": count >= min_showings})

    all_ok = all(r["ok"] for r in results)
    return {"check_date": check_date, "min_showings": min_showings, "results": results, "all_ok": all_ok}


async def smoke_test(check_date: date, min_showings: int) -> bool:
    """Print a smoke test report and return True if all cinemas pass."""
    report = await run_smoke_test(check_date, min_showings)

    print(f"Smoke test for {check_date}  (min showings per cinema: {min_showings})\n")
    for r in report["results"]:
        status = "✓" if r["ok"] else "✗"
        print(f"  {status}  {r['name']:<45} {r['count']} showing{'s' if r['count'] != 1 else ''}")

    print()
    warnings = [r["name"] for r in report["results"] if not r["ok"]]
    if warnings:
        print(f"WARNING: {len(warnings)} cinema(s) below threshold ({min_showings} showing(s)):")
        for name in warnings:
            print(f"  - {name}")
        return False

    print("All cinemas OK.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check that each cinema has sufficient showings on a given date."
    )
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=date.today(),
        metavar="YYYY-MM-DD",
        help="Date to check (default: today)",
    )
    parser.add_argument(
        "--min-showings",
        type=int,
        default=DEFAULT_MIN_SHOWINGS,
        metavar="N",
        help=f"Minimum showings per cinema (default: {DEFAULT_MIN_SHOWINGS})",
    )
    args = parser.parse_args()

    ok = asyncio.run(smoke_test(args.date, args.min_showings))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
