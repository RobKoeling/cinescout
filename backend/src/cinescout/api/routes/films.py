"""Films API endpoints."""

import logging
import re

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from cinescout.database import get_db
from cinescout.models import Cinema, Film, Showing

logger = logging.getLogger(__name__)
router = APIRouter()

# In-process caches (persist for the lifetime of the process)
_rt_head_cache: dict[str, bool] = {}  # slug → HTTP 200?
_rt_year_cache: dict[str, int | None] = {}  # slug → year extracted from page


def _to_rt_slug(title: str) -> str:
    return re.sub(r"^_|_$", "", re.sub(r"[^a-z0-9]+", "_", re.sub(r"[''']", "", title.lower())))


async def _rt_head_valid(slug: str) -> bool:
    if slug in _rt_head_cache:
        return _rt_head_cache[slug]
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=8, verify=False) as client:
            r = await client.head(
                f"https://www.rottentomatoes.com/m/{slug}",
                headers={"User-Agent": "Mozilla/5.0"},
            )
        valid = r.status_code == 200
    except Exception as exc:
        logger.debug(f"RT HEAD failed for {slug!r}: {exc}")
        valid = True  # fail open — don't hide the link on network errors
    _rt_head_cache[slug] = valid
    return valid


async def _rt_page_year(slug: str) -> int | None:
    """Fetch the RT page for *slug* and extract its release year."""
    if slug in _rt_year_cache:
        return _rt_year_cache[slug]
    year: int | None = None
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10, verify=False) as client:
            r = await client.get(
                f"https://www.rottentomatoes.com/m/{slug}",
                headers={"User-Agent": "Mozilla/5.0"},
            )
        if r.status_code == 200:
            text = r.text
            # Pattern 1: metadataProps JSON array — year may be first or second (after a rating like "R")
            m = re.search(r'"metadataProps":\[[^\]]*"((?:19|20)\d{2})"', text)
            if not m:
                # Pattern 2: cag[release] used on older pages
                m = re.search(r'"cag\[release\]":"[^"]*?((?:19|20)\d{2})', text)
            if not m:
                # Pattern 3: JSON-LD releaseYear
                m = re.search(r'releaseYear["\s]*:["\s]*(\d{4})', text)
            if m:
                year = int(m.group(1))
    except Exception as exc:
        logger.debug(f"RT page year fetch failed for {slug!r}: {exc}")
    _rt_year_cache[slug] = year
    return year


class FilmSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    year: int | None = None


@router.get("/films/search", response_model=list[FilmSearchResult])
async def search_films(
    q: str = Query(..., min_length=1, description="Title search string"),
    city: str = Query("london", description="City to search in"),
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[FilmSearchResult]:
    """
    Search films by title that have showings in the given city.

    Returns up to `limit` matching films ordered alphabetically.
    """
    stmt = (
        select(Film.id, Film.title, Film.year)
        .join(Showing, Showing.film_id == Film.id)
        .join(Cinema, Cinema.id == Showing.cinema_id)
        .where(
            and_(
                Cinema.city == city,
                Film.title.ilike(f"%{q}%"),
            )
        )
        .distinct()
        .order_by(Film.title)
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()
    return [FilmSearchResult(id=row.id, title=row.title, year=row.year) for row in rows]


class RTCheckResponse(BaseModel):
    valid: bool
    url: str


@router.get("/films/rt-check", response_model=RTCheckResponse)
async def check_rt_url(
    title: str = Query(..., description="Film title"),
    year: int | None = Query(None, description="Release year"),
) -> RTCheckResponse:
    """Check whether a Rotten Tomatoes page exists for a film title."""
    base_slug = _to_rt_slug(title)

    # 1. Year-qualified slug (e.g. mandy_2018) — unambiguous when it exists.
    if year and await _rt_head_valid(f"{base_slug}_{year}"):
        slug = f"{base_slug}_{year}"
        return RTCheckResponse(valid=True, url=f"https://www.rottentomatoes.com/m/{slug}")

    # 2. Bare slug — exists on RT?
    if not await _rt_head_valid(base_slug):
        return RTCheckResponse(valid=False, url=f"https://www.rottentomatoes.com/m/{base_slug}")

    # 3. Year known: verify the bare-slug page is actually the right film.
    if year:
        page_year = await _rt_page_year(base_slug)
        if page_year is None or abs(page_year - year) > 2:
            logger.debug(f"RT year check for {base_slug!r}: page={page_year}, film={year} — suppressing link")
            return RTCheckResponse(valid=False, url=f"https://www.rottentomatoes.com/m/{base_slug}")

    return RTCheckResponse(valid=True, url=f"https://www.rottentomatoes.com/m/{base_slug}")
