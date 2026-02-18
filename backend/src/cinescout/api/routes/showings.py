"""Showings API endpoints."""

import logging
from collections import defaultdict
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cinescout.database import get_db
from cinescout.models import Cinema, Film, Showing
from cinescout.schemas import (
    CinemaResponse,
    CinemaWithShowings,
    FilmWithCinemas,
    FilmWithShowingCount,
    ShowingsQuery,
    ShowingsResponse,
    ShowingTimeResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

LONDON_TZ = ZoneInfo("Europe/London")


@router.get("/showings", response_model=ShowingsResponse)
async def get_showings(
    date_param: date = Query(..., alias="date", description="Date to search (YYYY-MM-DD)"),
    city: str = Query("london", description="City to search in"),
    time_from: time = Query(time(0, 0), description="Earliest start time (HH:MM)"),
    time_to: time = Query(time(23, 59), description="Latest start time (HH:MM)"),
    db: AsyncSession = Depends(get_db),
) -> ShowingsResponse:
    """
    Search for film showings within a date and time window.

    Groups results by film, then by cinema, sorted by film popularity
    (number of showings).
    """
    # Combine date and time boundaries with timezone awareness
    datetime_from = datetime.combine(date_param, time_from, tzinfo=LONDON_TZ)
    datetime_to = datetime.combine(date_param, time_to, tzinfo=LONDON_TZ)

    # Query showings with joined cinema and film data
    stmt = (
        select(Showing)
        .options(
            selectinload(Showing.cinema),
            selectinload(Showing.film),
        )
        .join(Cinema)
        .where(
            and_(
                Cinema.city == city,
                Showing.start_time >= datetime_from,
                Showing.start_time < datetime_to,
            )
        )
        .order_by(Showing.start_time)
    )

    result = await db.execute(stmt)
    showings = result.scalars().all()

    # Group showings by film, then by cinema
    film_groups: dict[str, dict[str, list[Showing]]] = defaultdict(lambda: defaultdict(list))
    film_objects: dict[str, Film] = {}
    cinema_objects: dict[str, Cinema] = {}

    for showing in showings:
        film_id = showing.film_id
        cinema_id = showing.cinema_id

        film_groups[film_id][cinema_id].append(showing)
        film_objects[film_id] = showing.film
        cinema_objects[cinema_id] = showing.cinema

    # Build response structure
    films_with_cinemas: list[FilmWithCinemas] = []

    for film_id, cinema_groups in film_groups.items():
        film = film_objects[film_id]
        total_showings = sum(len(showings) for showings in cinema_groups.values())

        # Build cinema list with showing times
        cinemas_with_showings: list[CinemaWithShowings] = []
        for cinema_id, cinema_showings in cinema_groups.items():
            cinema = cinema_objects[cinema_id]

            # Convert showings to showing time responses
            times = [
                ShowingTimeResponse(
                    id=showing.id,
                    start_time=showing.start_time,
                    screen_name=showing.screen_name,
                    format_tags=showing.format_tags,
                    booking_url=showing.booking_url,
                    price=showing.price,
                    raw_title=showing.raw_title,
                )
                for showing in cinema_showings
            ]

            cinemas_with_showings.append(
                CinemaWithShowings(
                    cinema=CinemaResponse.model_validate(cinema),
                    times=times,
                )
            )

        # Create film with showing count
        film_response = FilmWithShowingCount(
            id=film.id,
            title=film.title,
            year=film.year,
            directors=film.directors,
            countries=film.countries,
            runtime=film.runtime,
            overview=film.overview,
            poster_path=film.poster_path,
            tmdb_id=film.tmdb_id,
            showing_count=total_showings,
        )

        films_with_cinemas.append(
            FilmWithCinemas(
                film=film_response,
                cinemas=cinemas_with_showings,
            )
        )

    # Sort films by showing count (descending)
    films_with_cinemas.sort(key=lambda f: f.film.showing_count, reverse=True)

    # Calculate totals
    total_films = len(films_with_cinemas)
    total_showings = len(showings)

    return ShowingsResponse(
        films=films_with_cinemas,
        total_films=total_films,
        total_showings=total_showings,
        query=ShowingsQuery(
            date=date_param,
            city=city,
            time_from=time_from,
            time_to=time_to,
        ),
    )


@router.get("/director-showings", response_model=list[FilmWithCinemas])
async def get_director_showings(
    director: str = Query(..., description="Director name"),
    city: str = Query("london", description="City to search in"),
    date_from: date = Query(..., description="Start date (YYYY-MM-DD)"),
    date_to: date = Query(..., description="End date (YYYY-MM-DD)"),
    exclude_film_id: str | None = Query(None, description="Film ID to exclude"),
    db: AsyncSession = Depends(get_db),
) -> list[FilmWithCinemas]:
    """
    Fetch all showings by a director within a date range.

    Returns results grouped by film, then by cinema.
    """
    datetime_from = datetime.combine(date_from, time(0, 0), tzinfo=LONDON_TZ)
    datetime_to = datetime.combine(date_to, time(23, 59), tzinfo=LONDON_TZ)

    stmt = (
        select(Showing)
        .options(
            selectinload(Showing.cinema),
            selectinload(Showing.film),
        )
        .join(Cinema)
        .join(Film)
        .where(
            and_(
                Cinema.city == city,
                Showing.start_time >= datetime_from,
                Showing.start_time <= datetime_to,
                Film.directors.contains([director]),
            )
        )
        .order_by(Showing.start_time)
    )

    result = await db.execute(stmt)
    showings = result.scalars().all()

    # Group by film → cinema
    film_groups: dict[str, dict[str, list[Showing]]] = defaultdict(lambda: defaultdict(list))
    film_objects: dict[str, Film] = {}
    cinema_objects: dict[str, Cinema] = {}

    for showing in showings:
        if exclude_film_id and showing.film_id == exclude_film_id:
            continue
        film_groups[showing.film_id][showing.cinema_id].append(showing)
        film_objects[showing.film_id] = showing.film
        cinema_objects[showing.cinema_id] = showing.cinema

    films_with_cinemas: list[FilmWithCinemas] = []
    for film_id, cinema_groups in film_groups.items():
        film = film_objects[film_id]
        total_showings = sum(len(s) for s in cinema_groups.values())

        cinemas_with_showings: list[CinemaWithShowings] = []
        for cinema_id, cinema_showings in cinema_groups.items():
            cinema = cinema_objects[cinema_id]
            times = [
                ShowingTimeResponse(
                    id=s.id,
                    start_time=s.start_time,
                    screen_name=s.screen_name,
                    format_tags=s.format_tags,
                    booking_url=s.booking_url,
                    price=s.price,
                )
                for s in cinema_showings
            ]
            cinemas_with_showings.append(
                CinemaWithShowings(
                    cinema=CinemaResponse.model_validate(cinema),
                    times=times,
                )
            )

        films_with_cinemas.append(
            FilmWithCinemas(
                film=FilmWithShowingCount(
                    id=film.id,
                    title=film.title,
                    year=film.year,
                    directors=film.directors,
                    countries=film.countries,
                    runtime=film.runtime,
                    overview=film.overview,
                    poster_path=film.poster_path,
                    tmdb_id=film.tmdb_id,
                    showing_count=total_showings,
                ),
                cinemas=cinemas_with_showings,
            )
        )

    films_with_cinemas.sort(key=lambda f: f.film.title)
    return films_with_cinemas
