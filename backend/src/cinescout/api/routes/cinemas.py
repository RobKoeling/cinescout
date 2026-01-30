"""Cinema API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cinescout.database import get_db
from cinescout.models.cinema import Cinema
from cinescout.schemas.cinema import CinemaResponse

router = APIRouter()


@router.get("/cinemas", response_model=list[CinemaResponse])
async def get_cinemas(
    city: str = Query(default="london", description="City to filter cinemas"),
    db: AsyncSession = Depends(get_db),
) -> list[Cinema]:
    """
    Get list of cinemas.

    Args:
        city: City to filter cinemas (default: london)
        db: Database session

    Returns:
        List of cinema objects
    """
    query = select(Cinema).where(Cinema.city == city).order_by(Cinema.name)
    result = await db.execute(query)
    cinemas = result.scalars().all()
    return list(cinemas)
