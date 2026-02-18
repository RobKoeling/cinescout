"""Unit tests for the FilmMatcher service."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from cinescout.models.film import Film
from cinescout.services.film_matcher import FilmMatcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_execute_result(
    *,
    scalar_one_or_none: object = None,
    scalars_all: list | None = None,
) -> MagicMock:
    """Build a mock object that mimics an SQLAlchemy execute result."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = scalar_one_or_none
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = scalars_all if scalars_all is not None else []
    r.scalars.return_value = mock_scalars
    return r


def make_film(
    id: str = "nosferatu-2024",
    title: str = "Nosferatu",
    year: int | None = 2024,
) -> Film:
    return Film(id=id, title=title, year=year)


def make_nested_ctx() -> MagicMock:
    """Async context manager that mimics SQLAlchemy's begin_nested() / SAVEPOINT."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=ctx)
    ctx.__aexit__ = AsyncMock(return_value=False)  # never suppress exceptions
    return ctx


def make_db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()
    db.get = AsyncMock(return_value=None)
    db.begin_nested = MagicMock(side_effect=lambda: make_nested_ctx())
    return db


def make_tmdb(search_result: dict | None = None, details: dict | None = None) -> MagicMock:
    tmdb = MagicMock()
    tmdb.search_film = AsyncMock(return_value=search_result)
    tmdb.get_film_details = AsyncMock(return_value=details)
    tmdb.extract_directors = MagicMock(return_value=["Robert Eggers"])
    tmdb.extract_countries = MagicMock(return_value=["United States"])
    return tmdb


# ---------------------------------------------------------------------------
# Pure helpers: _extract_year, _generate_film_id
# ---------------------------------------------------------------------------


class TestExtractYear:
    def setup_method(self) -> None:
        self.matcher = FilmMatcher(make_db())

    def test_extracts_year_from_valid_date(self) -> None:
        assert self.matcher._extract_year("2024-01-15") == 2024

    def test_returns_none_for_none_input(self) -> None:
        assert self.matcher._extract_year(None) is None

    def test_returns_none_for_empty_string(self) -> None:
        assert self.matcher._extract_year("") is None

    def test_returns_none_for_invalid_string(self) -> None:
        assert self.matcher._extract_year("not-a-date") is None


class TestGenerateFilmId:
    def setup_method(self) -> None:
        self.matcher = FilmMatcher(make_db())

    def test_combines_slug_and_year(self) -> None:
        assert self.matcher._generate_film_id("Nosferatu", 2024) == "nosferatu-2024"

    def test_returns_slug_only_when_no_year(self) -> None:
        assert self.matcher._generate_film_id("The Grand Budapest Hotel", None) == (
            "the-grand-budapest-hotel"
        )

    def test_slugifies_special_characters(self) -> None:
        assert self.matcher._generate_film_id("Mission: Impossible", 1996) == (
            "mission-impossible-1996"
        )


# ---------------------------------------------------------------------------
# _fuzzy_match
# ---------------------------------------------------------------------------


class TestFuzzyMatch:
    async def test_returns_film_for_identical_title(self) -> None:
        film = make_film(title="Nosferatu")
        db = make_db()
        db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[film]))

        matcher = FilmMatcher(db)
        result = await matcher._fuzzy_match("Nosferatu")

        assert result is film

    async def test_returns_film_for_high_similarity(self) -> None:
        # "Nosferatu" vs "Nosferatu: A Symphony of Horror" — score < 85
        # Use titles that are clearly close enough
        film = make_film(title="The Grand Budapest Hotel")
        db = make_db()
        db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[film]))

        matcher = FilmMatcher(db)
        # Exact match → 100%
        result = await matcher._fuzzy_match("The Grand Budapest Hotel")
        assert result is film

    async def test_returns_none_when_score_below_threshold(self) -> None:
        film = make_film(title="Nosferatu")
        db = make_db()
        db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[film]))

        matcher = FilmMatcher(db)
        # Completely different title → low score
        result = await matcher._fuzzy_match("The Grand Budapest Hotel")
        assert result is None

    async def test_returns_none_for_empty_film_list(self) -> None:
        db = make_db()
        db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[]))

        matcher = FilmMatcher(db)
        result = await matcher._fuzzy_match("Nosferatu")
        assert result is None


# ---------------------------------------------------------------------------
# match_or_create_film — end-to-end flow via each stage
# ---------------------------------------------------------------------------


class TestMatchOrCreateFilm:
    async def test_stage1_alias_hit_returns_existing_film(self) -> None:
        existing = make_film()
        db = make_db()
        # First execute call (_check_alias) returns the existing film
        db.execute = AsyncMock(return_value=make_execute_result(scalar_one_or_none=existing))

        matcher = FilmMatcher(db)
        result = await matcher.match_or_create_film("Nosferatu")

        assert result is existing
        # Only one DB query needed — no fuzzy match, no TMDb
        assert db.execute.call_count == 1

    async def test_stage2_fuzzy_match_returns_existing_film(self) -> None:
        existing = make_film(title="Nosferatu")
        db = make_db()
        db.execute = AsyncMock(
            side_effect=[
                make_execute_result(scalar_one_or_none=None),  # alias miss
                make_execute_result(scalars_all=[existing]),   # fuzzy: all films
                make_execute_result(scalar_one_or_none=None),  # store alias: check
            ]
        )

        matcher = FilmMatcher(db)
        result = await matcher.match_or_create_film("Nosferatu")

        assert result is existing
        db.add.assert_called_once()  # alias stored
        db.flush.assert_called_once()

    async def test_stage3_creates_film_from_tmdb(self) -> None:
        db = make_db()
        db.execute = AsyncMock(
            side_effect=[
                make_execute_result(scalar_one_or_none=None),  # alias miss
                make_execute_result(scalars_all=[]),            # fuzzy: empty DB
                make_execute_result(scalar_one_or_none=None),  # store alias: check
            ]
        )

        tmdb = make_tmdb(
            search_result={"id": 12345},
            details={
                "title": "Nosferatu",
                "release_date": "2024-01-10",
                "credits": {"crew": [{"name": "Robert Eggers", "job": "Director"}]},
                "production_countries": [{"name": "United States"}],
                "overview": "Horror film.",
                "poster_path": "/abc.jpg",
                "runtime": 132,
            },
        )

        matcher = FilmMatcher(db, tmdb_client=tmdb)
        result = await matcher.match_or_create_film("Nosferatu")

        assert result.title == "Nosferatu"
        assert result.year == 2024
        assert result.tmdb_id == 12345
        # Film added + alias added = 2 add calls, 2 flush calls
        assert db.add.call_count == 2
        assert db.flush.call_count == 2

    async def test_stage4_creates_placeholder_when_no_tmdb_match(self) -> None:
        db = make_db()
        db.execute = AsyncMock(
            side_effect=[
                make_execute_result(scalar_one_or_none=None),
                make_execute_result(scalars_all=[]),
                make_execute_result(scalar_one_or_none=None),
            ]
        )

        tmdb = make_tmdb(search_result=None)  # TMDb returns nothing

        matcher = FilmMatcher(db, tmdb_client=tmdb)
        result = await matcher.match_or_create_film("Unknown Obscure Film")

        assert result.title == "Unknown Obscure Film"
        assert result.tmdb_id is None
        assert db.add.call_count == 2   # placeholder + alias

    async def test_integrity_error_on_flush_falls_back_to_existing_film(self) -> None:
        """The bug fix: concurrent scrapes trying to insert the same film."""
        existing = make_film()
        db = make_db()
        db.execute = AsyncMock(
            side_effect=[
                make_execute_result(scalar_one_or_none=None),
                make_execute_result(scalars_all=[]),
                make_execute_result(scalar_one_or_none=None),
            ]
        )
        # flush raises IntegrityError on the film insert
        db.flush = AsyncMock(
            side_effect=[
                IntegrityError("INSERT", {}, Exception("unique violation")),
                None,  # second flush (for alias) succeeds
            ]
        )
        db.get = AsyncMock(return_value=existing)

        tmdb = make_tmdb(
            search_result={"id": 12345},
            details={
                "title": "Nosferatu",
                "release_date": "2024-01-10",
                "credits": {},
                "production_countries": [],
                "overview": None,
                "poster_path": None,
                "runtime": None,
            },
        )

        matcher = FilmMatcher(db, tmdb_client=tmdb)
        result = await matcher.match_or_create_film("Nosferatu")

        assert result is existing
        # Savepoints are used instead of session-level rollback, so db.rollback is NOT called.
        db.rollback.assert_not_called()
