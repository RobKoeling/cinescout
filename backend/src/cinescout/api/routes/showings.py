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


async def enrich_cinemas_with_distance(
    cinemas: list[Cinema],
    user_lat: float,
    user_lng: float,
    use_tfl: bool,
    transport_mode: str,
) -> None:
    """
    Add distance/travel time to cinema objects in-place.

    Args:
        cinemas: List of Cinema objects to enrich
        user_lat: User's latitude
        user_lng: User's longitude
        use_tfl: Whether to use TfL API for London cinemas
        transport_mode: Transport mode for TfL ("public", "walking", "cycling")
    """
    from cinescout.utils.geo import calculate_haversine_distance
    from cinescout.services.tfl_client import TfLClient
    from cinescout.config import settings

    # Initialize TfL client if needed
    tfl_client = None
    if use_tfl:
        tfl_client = TfLClient(app_key=settings.tfl_app_key)

    # Always calculate straight-line distance for all cinemas
    for cinema in cinemas:
        if cinema.latitude is None or cinema.longitude is None:
            logger.warning(f"Cinema {cinema.id} ({cinema.name}) missing coordinates, skipping distance calculation")
            continue

        # Calculate Haversine distance
        distance_km = calculate_haversine_distance(
            user_lat, user_lng, cinema.latitude, cinema.longitude
        )
        cinema.distance_km = round(distance_km, 2)
        cinema.distance_miles = round(distance_km * 0.621371, 2)

    # Optionally get TfL journey times for London cinemas
    if tfl_client:
        # Collect London cinemas with valid coordinates
        london_cinemas = [
            c for c in cinemas
            if c.city == "london" and c.latitude is not None and c.longitude is not None
        ]

        # Parallelize TfL API calls
        import asyncio

        async def fetch_journey_time(cinema: Cinema) -> None:
            """Fetch and attach journey time for a single cinema."""
            try:
                result = await tfl_client.get_journey_time(
                    user_lat, user_lng,
                    cinema.latitude, cinema.longitude,
                    mode=transport_mode
                )
                if result and result.get("status") == "ok":
                    cinema.travel_time_minutes = result["duration_minutes"]
                    cinema.travel_mode = transport_mode
            except Exception as e:
                logger.error(f"Failed to get TfL journey time for cinema {cinema.id}: {e}")

        # Execute all TfL API calls in parallel
        if london_cinemas:
            await asyncio.gather(*[fetch_journey_time(c) for c in london_cinemas])


@router.get("/showings", response_model=ShowingsResponse)
async def get_showings(
    date_param: date = Query(..., alias="date", description="Date to search (YYYY-MM-DD)"),
    city: str = Query("london", description="City to search in"),
    time_from: time = Query(time(0, 0), description="Earliest start time (HH:MM)"),
    time_to: time = Query(time(23, 59), description="Latest start time (HH:MM)"),
    user_lat: float | None = Query(None, description="User latitude for distance calculation"),
    user_lng: float | None = Query(None, description="User longitude for distance calculation"),
    use_tfl: bool = Query(False, description="Use TfL API for travel time (London only)"),
    transport_mode: str = Query("public", description="Transport mode: public, walking, cycling"),
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

    # Enrich cinemas with distance/travel time if user location provided
    if user_lat is not None and user_lng is not None:
        await enrich_cinemas_with_distance(
            list(cinema_objects.values()),
            user_lat,
            user_lng,
            use_tfl,
            transport_mode,
        )

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
                    estimated_price=cinema.get_estimated_price(showing.start_time),
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

    # Sort cinemas by distance if user location provided
    if user_lat is not None and user_lng is not None:
        for film_with_cinemas in films_with_cinemas:
            film_with_cinemas.cinemas.sort(
                key=lambda c: c.cinema.distance_km if c.cinema.distance_km is not None else float('inf')
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
                    estimated_price=cinema.get_estimated_price(s.start_time),
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
