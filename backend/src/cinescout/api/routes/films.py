"""Films API endpoints."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from cinescout.database import get_db
from cinescout.models import Cinema, Film, Showing

router = APIRouter()


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
