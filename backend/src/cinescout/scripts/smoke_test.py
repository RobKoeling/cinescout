"""Smoke test: check that each cinema has at least a minimum number of showings on a given date."""

import argparse
import asyncio
import sys
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from cinescout.database import AsyncSessionLocal
from cinescout.models.cinema import Cinema
from cinescout.models.showing import Showing

LONDON_TZ = ZoneInfo("Europe/London")
DEFAULT_MIN_SHOWINGS = 1


async def smoke_test(check_date: date, min_showings: int) -> bool:
    """Check showings per cinema for a given date.

    Returns True if all cinemas meet the threshold, False otherwise.
    """
    day_start = datetime.combine(check_date, time.min, tzinfo=LONDON_TZ)
    day_end = datetime.combine(check_date, time.max, tzinfo=LONDON_TZ)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Cinema).order_by(Cinema.name))
        cinemas = result.scalars().all()

        if not cinemas:
            print("No cinemas found in database.")
            return False

        print(f"Smoke test for {check_date}  (min showings per cinema: {min_showings})\n")

        warnings: list[str] = []

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
            ok = count >= min_showings
            status = "✓" if ok else "✗"
            label = f"{cinema.name:<45}"
            print(f"  {status}  {label} {count} showing{'s' if count != 1 else ''}")
            if not ok:
                warnings.append(cinema.name)

        print()
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
