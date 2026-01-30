# CineScout: Testing Strategy

## Overview

This document outlines the testing approach for CineScout, covering unit tests, integration tests, end-to-end tests, and scraper-specific testing strategies.

## Testing Pyramid

```
        ┌───────────┐
        │    E2E    │  ← Few, slow, high confidence
        │  (Cypress)│
        ├───────────┤
        │Integration│  ← Some, medium speed
        │  (pytest) │
        ├───────────┤
        │   Unit    │  ← Many, fast, focused
        │  (pytest) │
        └───────────┘
```

| Level | Tools | Focus | Count |
|-------|-------|-------|-------|
| Unit | pytest, pytest-asyncio | Individual functions, classes | Many (70%) |
| Integration | pytest, httpx, testcontainers | API endpoints, database | Some (20%) |
| E2E | Cypress or Playwright | User workflows | Few (10%) |

## Test Directory Structure

```
backend/
└── tests/
    ├── conftest.py              # Shared fixtures
    ├── unit/
    │   ├── test_film_matcher.py
    │   ├── test_text_utils.py
    │   └── test_schemas.py
    ├── integration/
    │   ├── test_api_showings.py
    │   ├── test_api_cinemas.py
    │   └── test_database.py
    ├── scrapers/
    │   ├── conftest.py          # Scraper-specific fixtures
    │   ├── test_base_scraper.py
    │   ├── test_bfi_scraper.py
    │   ├── test_curzon_scraper.py
    │   └── fixtures/            # Saved HTML/JSON responses
    │       ├── bfi/
    │       ├── curzon/
    │       └── garden/
    └── e2e/
        └── test_search_flow.py

frontend/
└── src/
    └── __tests__/
        ├── components/
        │   ├── SearchForm.test.tsx
        │   ├── FilmCard.test.tsx
        │   └── FilmList.test.tsx
        └── hooks/
            └── useShowings.test.ts
```

## Backend Testing

### Configuration (pyproject.toml)

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
filterwarnings = [
    "ignore::DeprecationWarning",
]
addopts = "-v --tb=short"

[tool.coverage.run]
source = ["src/cinescout"]
omit = ["*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
```

### Shared Fixtures (conftest.py)

```python
"""
Shared test fixtures for CineScout backend tests.
"""

import asyncio
from datetime import date, datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from cinescout.main import app
from cinescout.database import Base, get_db
from cinescout.models.cinema import Cinema
from cinescout.models.film import Film
from cinescout.models.showing import Showing


# Use SQLite for fast tests (PostgreSQL for integration)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(
        db_engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with database override."""
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


# ============== Test Data Fixtures ==============

@pytest.fixture
def sample_cinema() -> Cinema:
    """Create a sample cinema for testing."""
    return Cinema(
        id="test-cinema",
        name="Test Cinema",
        slug="test-cinema",
        address="123 Test Street, London",
        city="london",
        website="https://testcinema.com",
        booking_url="https://testcinema.com/book",
        scraper_type="test",
        is_active=True,
        supports_online_booking=True,
        supports_availability_check=False,
        latitude=51.5074,
        longitude=-0.1278,
    )


@pytest.fixture
def sample_film() -> Film:
    """Create a sample film for testing."""
    return Film(
        id="test-film-001",
        title="The Test Movie",
        original_title="Le Film Test",
        year=2024,
        directors=["Test Director"],
        countries=["GB", "FR"],
        runtime_minutes=120,
        tmdb_id=12345,
    )


@pytest.fixture
def sample_showing(sample_cinema: Cinema, sample_film: Film) -> Showing:
    """Create a sample showing for testing."""
    return Showing(
        id="test-showing-001",
        cinema_id=sample_cinema.id,
        film_id=sample_film.id,
        start_time=datetime(2024, 1, 25, 18, 30),
        end_time=datetime(2024, 1, 25, 20, 30),
        screen="Screen 1",
        format="2D",
        booking_url="https://testcinema.com/book/001",
        price_amount=12.50,
        price_currency="GBP",
        raw_title="The Test Movie",
    )


@pytest.fixture
async def seeded_db(
    db_session: AsyncSession,
    sample_cinema: Cinema,
    sample_film: Film,
    sample_showing: Showing,
):
    """Seed database with test data."""
    db_session.add(sample_cinema)
    db_session.add(sample_film)
    db_session.add(sample_showing)
    await db_session.commit()
    
    return {
        "cinema": sample_cinema,
        "film": sample_film,
        "showing": sample_showing,
    }


# ============== Mock Fixtures ==============

@pytest.fixture
def mock_tmdb_client():
    """Mock TMDb API client."""
    mock = AsyncMock()
    mock.search_movie.return_value = {
        "results": [
            {
                "id": 12345,
                "title": "The Test Movie",
                "original_title": "Le Film Test",
                "release_date": "2024-01-15",
                "poster_path": "/test.jpg",
            }
        ]
    }
    mock.get_movie_details.return_value = {
        "id": 12345,
        "runtime": 120,
        "production_countries": [{"iso_3166_1": "GB"}, {"iso_3166_1": "FR"}],
        "credits": {
            "crew": [{"name": "Test Director", "job": "Director"}]
        },
    }
    return mock


@pytest.fixture
def mock_playwright_page():
    """Mock Playwright page for scraper tests."""
    mock = AsyncMock()
    mock.goto = AsyncMock()
    mock.wait_for_selector = AsyncMock()
    mock.query_selector_all = AsyncMock(return_value=[])
    mock.close = AsyncMock()
    return mock
```

### Unit Tests

#### Test Film Matcher

```python
"""
Unit tests for the film matching service.
"""

import pytest
from unittest.mock import AsyncMock, patch

from cinescout.services.film_matcher import FilmMatcher


class TestFilmMatcherNormalisation:
    """Test title normalisation logic."""
    
    def test_removes_year_suffix(self):
        matcher = FilmMatcher(db_session=AsyncMock())
        assert matcher._normalise_title("The Godfather (1972)") == "The Godfather"
    
    def test_removes_preview_prefix(self):
        matcher = FilmMatcher(db_session=AsyncMock())
        assert matcher._normalise_title("Preview: Dune Part Two") == "Dune Part Two"
    
    def test_removes_premiere_prefix(self):
        matcher = FilmMatcher(db_session=AsyncMock())
        assert matcher._normalise_title("Premiere: New Film") == "New Film"
    
    def test_removes_remastered_suffix(self):
        matcher = FilmMatcher(db_session=AsyncMock())
        result = matcher._normalise_title("Blade Runner - Remastered")
        assert result == "Blade Runner"
    
    def test_removes_directors_cut_suffix(self):
        matcher = FilmMatcher(db_session=AsyncMock())
        result = matcher._normalise_title("Apocalypse Now - Director's Cut")
        assert result == "Apocalypse Now"
    
    def test_cleans_extra_whitespace(self):
        matcher = FilmMatcher(db_session=AsyncMock())
        assert matcher._normalise_title("  Too   Many  Spaces  ") == "Too Many Spaces"
    
    def test_removes_square_brackets(self):
        matcher = FilmMatcher(db_session=AsyncMock())
        assert matcher._normalise_title("Film Name [35mm]") == "Film Name"


class TestFilmMatcherMatching:
    """Test the matching logic."""
    
    @pytest.mark.asyncio
    async def test_exact_alias_match(self, db_session):
        """Should return film when exact alias exists."""
        # Setup: create film with alias
        # ...
        
        matcher = FilmMatcher(db_session)
        result = await matcher.match("Godfather, The")
        
        assert result is not None
        assert result.title == "The Godfather"
    
    @pytest.mark.asyncio
    async def test_fuzzy_match_above_threshold(self, db_session, sample_film):
        """Should match when similarity is above threshold."""
        db_session.add(sample_film)
        await db_session.commit()
        
        matcher = FilmMatcher(db_session)
        # Slightly different title
        result = await matcher.match("Test Movie, The")
        
        assert result is not None
        assert result.id == sample_film.id
    
    @pytest.mark.asyncio
    async def test_no_match_below_threshold(self, db_session, sample_film):
        """Should not match when similarity is below threshold."""
        db_session.add(sample_film)
        await db_session.commit()
        
        matcher = FilmMatcher(db_session)
        result = await matcher.match("Completely Different Film")
        
        # Should create placeholder, not match existing
        assert result.title == "Completely Different Film"
        assert result.id != sample_film.id
    
    @pytest.mark.asyncio
    async def test_tmdb_search_fallback(self, db_session, mock_tmdb_client):
        """Should search TMDb when no local match."""
        with patch.object(FilmMatcher, '_search_tmdb', mock_tmdb_client.search_movie):
            matcher = FilmMatcher(db_session)
            result = await matcher.match("New Film Not In Database")
            
            mock_tmdb_client.search_movie.assert_called_once()


class TestFilmMatcherYearHint:
    """Test year hint functionality."""
    
    @pytest.mark.asyncio
    async def test_year_hint_narrows_search(self, db_session):
        """Year hint should limit candidate films."""
        # Create films with different years
        film_2020 = Film(id="f1", title="Test Film", year=2020, directors=[], countries=[])
        film_2024 = Film(id="f2", title="Test Film", year=2024, directors=[], countries=[])
        
        db_session.add_all([film_2020, film_2024])
        await db_session.commit()
        
        matcher = FilmMatcher(db_session)
        result = await matcher.match("Test Film", year_hint=2024)
        
        assert result.year == 2024
```

#### Test Text Utilities

```python
"""
Unit tests for text utility functions.
"""

import pytest
from cinescout.utils.text import (
    clean_title,
    extract_year_from_title,
    normalise_cinema_name,
)


class TestCleanTitle:
    
    def test_basic_cleaning(self):
        assert clean_title("  Hello World  ") == "Hello World"
    
    def test_removes_multiple_spaces(self):
        assert clean_title("Hello    World") == "Hello World"
    
    def test_handles_none(self):
        assert clean_title(None) == ""
    
    def test_handles_empty_string(self):
        assert clean_title("") == ""


class TestExtractYearFromTitle:
    
    def test_extracts_year_suffix(self):
        title, year = extract_year_from_title("The Godfather (1972)")
        assert title == "The Godfather"
        assert year == 1972
    
    def test_no_year_present(self):
        title, year = extract_year_from_title("The Godfather")
        assert title == "The Godfather"
        assert year is None
    
    def test_year_in_middle_ignored(self):
        title, year = extract_year_from_title("2001: A Space Odyssey")
        assert title == "2001: A Space Odyssey"
        assert year is None
    
    def test_handles_brackets_without_year(self):
        title, year = extract_year_from_title("Film (Director's Cut)")
        assert title == "Film (Director's Cut)"
        assert year is None


class TestNormaliseCinemaName:
    
    def test_lowercase(self):
        assert normalise_cinema_name("BFI Southbank") == "bfi-southbank"
    
    def test_removes_special_chars(self):
        assert normalise_cinema_name("Cinema's Place!") == "cinemas-place"
    
    def test_replaces_spaces(self):
        assert normalise_cinema_name("Prince Charles Cinema") == "prince-charles-cinema"
```

### Integration Tests

#### Test API Showings Endpoint

```python
"""
Integration tests for the showings API endpoint.
"""

import pytest
from datetime import date, datetime


class TestShowingsEndpoint:
    
    @pytest.mark.asyncio
    async def test_search_returns_results(self, client, seeded_db):
        """Should return showings matching query."""
        response = await client.get(
            "/api/showings",
            params={
                "date": "2024-01-25",
                "time_from": "18:00",
                "time_to": "22:00",
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_films"] == 1
        assert data["total_showings"] == 1
        assert data["films"][0]["film"]["title"] == "The Test Movie"
    
    @pytest.mark.asyncio
    async def test_search_filters_by_time(self, client, seeded_db):
        """Should exclude showings outside time window."""
        response = await client.get(
            "/api/showings",
            params={
                "date": "2024-01-25",
                "time_from": "20:00",  # After showing starts
                "time_to": "22:00",
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_showings"] == 0
    
    @pytest.mark.asyncio
    async def test_search_filters_by_date(self, client, seeded_db):
        """Should exclude showings on different dates."""
        response = await client.get(
            "/api/showings",
            params={
                "date": "2024-01-26",  # Different date
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_showings"] == 0
    
    @pytest.mark.asyncio
    async def test_search_groups_by_film(self, client, db_session, sample_cinema, sample_film):
        """Should group multiple showings of same film."""
        # Create second showing
        showing1 = Showing(
            id="s1", cinema_id=sample_cinema.id, film_id=sample_film.id,
            start_time=datetime(2024, 1, 25, 14, 00), raw_title="Test"
        )
        showing2 = Showing(
            id="s2", cinema_id=sample_cinema.id, film_id=sample_film.id,
            start_time=datetime(2024, 1, 25, 18, 00), raw_title="Test"
        )
        
        db_session.add(sample_cinema)
        db_session.add(sample_film)
        db_session.add_all([showing1, showing2])
        await db_session.commit()
        
        response = await client.get(
            "/api/showings",
            params={"date": "2024-01-25"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_films"] == 1
        assert data["total_showings"] == 2
        assert len(data["films"][0]["cinemas"][0]["times"]) == 2
    
    @pytest.mark.asyncio
    async def test_search_invalid_date(self, client):
        """Should return 422 for invalid date format."""
        response = await client.get(
            "/api/showings",
            params={"date": "not-a-date"}
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_search_missing_date(self, client):
        """Should return 422 when date is missing."""
        response = await client.get("/api/showings")
        
        assert response.status_code == 422


class TestAvailabilityEndpoint:
    
    @pytest.mark.asyncio
    async def test_returns_unknown_when_not_supported(self, client, seeded_db):
        """Should return 'unknown' when cinema doesn't support checks."""
        response = await client.get(
            "/api/showings/test-showing-001/availability"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["availability"] == "unknown"
    
    @pytest.mark.asyncio
    async def test_not_found_for_invalid_id(self, client):
        """Should return 404 for non-existent showing."""
        response = await client.get(
            "/api/showings/nonexistent-id/availability"
        )
        
        assert response.status_code == 404
```

### Scraper Tests

#### Scraper Test Strategy

Scraper tests are challenging because:
1. External websites change frequently
2. Real HTTP requests are slow and unreliable in CI
3. We need to test parsing logic in isolation

**Solution**: Use saved fixtures (HTML/JSON snapshots) for unit tests, with optional live tests for development.

```python
"""
Tests for the BFI scraper.
"""

import pytest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

from cinescout.scrapers.bfi import BFIScraper
from cinescout.scrapers.base import RawShowing


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "bfi"


class TestBFIScraperParsing:
    """Test BFI response parsing with saved fixtures."""
    
    @pytest.fixture
    def sample_api_response(self) -> dict:
        """Load saved API response."""
        import json
        with open(FIXTURES_DIR / "api_response.json") as f:
            return json.load(f)
    
    def test_parse_event_basic(self, sample_api_response):
        """Should parse basic event data."""
        scraper = BFIScraper()
        event = sample_api_response["events"][0]
        
        showings = scraper._parse_event(event)
        
        assert len(showings) >= 1
        assert all(isinstance(s, RawShowing) for s in showings)
    
    def test_parse_event_extracts_title(self, sample_api_response):
        """Should extract and normalise film title."""
        scraper = BFIScraper()
        event = sample_api_response["events"][0]
        
        showings = scraper._parse_event(event)
        
        assert showings[0].film_title != ""
        assert "Preview:" not in showings[0].film_title
    
    def test_parse_event_extracts_time(self, sample_api_response):
        """Should extract start time as datetime."""
        scraper = BFIScraper()
        event = sample_api_response["events"][0]
        
        showings = scraper._parse_event(event)
        
        assert isinstance(showings[0].start_time, datetime)
    
    def test_parse_event_extracts_format(self, sample_api_response):
        """Should extract screening format when present."""
        scraper = BFIScraper()
        # Use event with format tag
        event = {
            "title": "Test Film",
            "tags": ["35mm", "Archive"],
            "performances": [
                {"startTime": "2024-01-25T18:30:00Z"}
            ]
        }
        
        showings = scraper._parse_event(event)
        
        assert showings[0].format == "35mm"
    
    def test_parse_event_handles_missing_performances(self):
        """Should handle events with no performances."""
        scraper = BFIScraper()
        event = {"title": "Test Film", "performances": []}
        
        showings = scraper._parse_event(event)
        
        assert showings == []
    
    def test_extract_price_parses_pounds(self):
        """Should parse price from £X.XX format."""
        scraper = BFIScraper()
        
        assert scraper._extract_price({"price": "£12.50"}) == 12.50
        assert scraper._extract_price({"price": "12.50"}) == 12.50
        assert scraper._extract_price({"price": "£8"}) == 8.0
    
    def test_extract_price_handles_missing(self):
        """Should return None when price not present."""
        scraper = BFIScraper()
        
        assert scraper._extract_price({}) is None
        assert scraper._extract_price({"price": ""}) is None


class TestBFIScraperIntegration:
    """Integration tests that make real HTTP requests.
    
    These are marked slow and skipped in CI.
    Run manually with: pytest -m live
    """
    
    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_live_fetch(self):
        """Fetch real data from BFI website."""
        async with BFIScraper() as scraper:
            showings = await scraper.get_showings(
                date_from=date.today(),
                date_to=date.today()
            )
        
        # Just check we got something back
        assert isinstance(showings, list)
        # Note: might be empty if no showings today
        if showings:
            assert all(isinstance(s, RawShowing) for s in showings)


class TestBFIScraperMocked:
    """Tests with mocked HTTP responses."""
    
    @pytest.mark.asyncio
    async def test_get_showings_calls_api(self):
        """Should call BFI API endpoint."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"events": []}
        
        with patch("httpx.AsyncClient.get", return_value=mock_response):
            async with BFIScraper() as scraper:
                await scraper.get_showings(
                    date_from=date(2024, 1, 25),
                    date_to=date(2024, 1, 25)
                )
        
        # Verify API was called with correct params
        # ...
    
    @pytest.mark.asyncio
    async def test_falls_back_to_html_on_api_failure(self):
        """Should scrape HTML if API returns error."""
        mock_response = AsyncMock()
        mock_response.status_code = 500
        
        with patch("httpx.AsyncClient.get", return_value=mock_response):
            with patch.object(BFIScraper, "_scrape_html", return_value=[]) as mock_html:
                async with BFIScraper() as scraper:
                    await scraper.get_showings(
                        date_from=date(2024, 1, 25),
                        date_to=date(2024, 1, 25)
                    )
                
                mock_html.assert_called_once()
```

#### Creating Scraper Fixtures

```python
"""
Utility script to capture scraper fixtures for testing.

Run manually to update fixtures when scraper logic changes:
    python -m tests.scrapers.capture_fixtures
"""

import asyncio
import json
from datetime import date
from pathlib import Path

import httpx

FIXTURES_DIR = Path(__file__).parent / "fixtures"


async def capture_bfi_fixture():
    """Capture BFI API response."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.bfi.org.uk/api/whats-on",
            params={
                "from": date.today().isoformat(),
                "to": date.today().isoformat(),
                "venue": "southbank",
            }
        )
        
        (FIXTURES_DIR / "bfi").mkdir(parents=True, exist_ok=True)
        with open(FIXTURES_DIR / "bfi" / "api_response.json", "w") as f:
            json.dump(response.json(), f, indent=2)
        
        print("Captured BFI fixture")


async def main():
    await capture_bfi_fixture()
    # Add more cinemas as needed


if __name__ == "__main__":
    asyncio.run(main())
```

### Frontend Tests

#### Component Tests (Vitest + React Testing Library)

```typescript
// frontend/src/__tests__/components/SearchForm.test.tsx

import { render, screen, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import { SearchForm } from '../../components/SearchForm';

describe('SearchForm', () => {
  it('renders date and time inputs', () => {
    render(<SearchForm onSearch={vi.fn()} isLoading={false} />);
    
    expect(screen.getByLabelText(/date/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/from/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/until/i)).toBeInTheDocument();
  });
  
  it('calls onSearch with form values', () => {
    const onSearch = vi.fn();
    render(<SearchForm onSearch={onSearch} isLoading={false} />);
    
    fireEvent.change(screen.getByLabelText(/date/i), {
      target: { value: '2024-01-25' }
    });
    fireEvent.change(screen.getByLabelText(/from/i), {
      target: { value: '18:00' }
    });
    fireEvent.click(screen.getByRole('button', { name: /find/i }));
    
    expect(onSearch).toHaveBeenCalledWith({
      city: 'london',
      date: '2024-01-25',
      timeFrom: '18:00',
      timeTo: expect.any(String),
    });
  });
  
  it('disables button when loading', () => {
    render(<SearchForm onSearch={vi.fn()} isLoading={true} />);
    
    expect(screen.getByRole('button')).toBeDisabled();
  });
  
  it('shows loading text when loading', () => {
    render(<SearchForm onSearch={vi.fn()} isLoading={true} />);
    
    expect(screen.getByRole('button')).toHaveTextContent(/searching/i);
  });
});
```

```typescript
// frontend/src/__tests__/components/FilmCard.test.tsx

import { render, screen, fireEvent } from '@testing-library/react';
import { FilmCard } from '../../components/FilmCard';

const mockFilmData = {
  film: {
    id: 'test-1',
    title: 'The Test Movie',
    year: 2024,
    directors: ['Test Director'],
    countries: ['GB'],
    showingCount: 3,
  },
  cinemas: [
    {
      cinema: {
        id: 'cinema-1',
        name: 'Test Cinema',
        slug: 'test-cinema',
        address: '123 Test St',
        city: 'london',
        website: 'https://test.com',
        supportsOnlineBooking: true,
      },
      times: [
        {
          id: 'showing-1',
          startTime: '2024-01-25T18:30:00',
          bookingUrl: 'https://test.com/book',
          availability: 'unknown' as const,
        },
      ],
    },
  ],
};

describe('FilmCard', () => {
  it('renders film title', () => {
    render(<FilmCard data={mockFilmData} />);
    
    expect(screen.getByText('The Test Movie')).toBeInTheDocument();
  });
  
  it('renders metadata line', () => {
    render(<FilmCard data={mockFilmData} />);
    
    expect(screen.getByText(/Test Director/)).toBeInTheDocument();
    expect(screen.getByText(/2024/)).toBeInTheDocument();
    expect(screen.getByText(/GB/)).toBeInTheDocument();
  });
  
  it('shows showing count', () => {
    render(<FilmCard data={mockFilmData} />);
    
    expect(screen.getByText(/3 showings/)).toBeInTheDocument();
  });
  
  it('expands on click', () => {
    render(<FilmCard data={mockFilmData} />);
    
    // Details not visible initially
    expect(screen.queryByText('Test Cinema')).not.toBeInTheDocument();
    
    // Click to expand
    fireEvent.click(screen.getByRole('button'));
    
    // Details now visible
    expect(screen.getByText('Test Cinema')).toBeInTheDocument();
  });
  
  it('collapses on second click', () => {
    render(<FilmCard data={mockFilmData} />);
    
    const button = screen.getByRole('button');
    fireEvent.click(button);  // Expand
    fireEvent.click(button);  // Collapse
    
    expect(screen.queryByText('Test Cinema')).not.toBeInTheDocument();
  });
});
```

#### Hook Tests

```typescript
// frontend/src/__tests__/hooks/useShowings.test.ts

import { renderHook, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { useShowings } from '../../hooks/useShowings';
import * as api from '../../api/client';

vi.mock('../../api/client');

describe('useShowings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  
  it('fetches showings on search', async () => {
    const mockData = {
      films: [],
      totalFilms: 0,
      totalShowings: 0,
      query: { city: 'london', date: '2024-01-25' },
    };
    
    vi.mocked(api.fetchShowings).mockResolvedValue(mockData);
    
    const { result } = renderHook(() => useShowings());
    
    result.current.search({
      city: 'london',
      date: '2024-01-25',
      timeFrom: '18:00',
      timeTo: '22:00',
    });
    
    await waitFor(() => {
      expect(result.current.data).toEqual(mockData);
    });
  });
  
  it('sets loading state during fetch', async () => {
    vi.mocked(api.fetchShowings).mockImplementation(
      () => new Promise(resolve => setTimeout(resolve, 100))
    );
    
    const { result } = renderHook(() => useShowings());
    
    result.current.search({ city: 'london', date: '2024-01-25' });
    
    expect(result.current.isLoading).toBe(true);
  });
  
  it('handles errors', async () => {
    vi.mocked(api.fetchShowings).mockRejectedValue(new Error('API Error'));
    
    const { result } = renderHook(() => useShowings());
    
    result.current.search({ city: 'london', date: '2024-01-25' });
    
    await waitFor(() => {
      expect(result.current.error).toBe('API Error');
    });
  });
});
```

## End-to-End Tests (Playwright)

```typescript
// e2e/search.spec.ts

import { test, expect } from '@playwright/test';

test.describe('Film Search', () => {
  test('searches and displays results', async ({ page }) => {
    await page.goto('/');
    
    // Fill search form
    await page.fill('input[type="date"]', '2024-01-25');
    await page.fill('input[aria-label="From"]', '18:00');
    await page.fill('input[aria-label="Until"]', '22:00');
    
    // Submit
    await page.click('button:has-text("Find Films")');
    
    // Wait for results
    await expect(page.locator('[data-testid="film-list"]')).toBeVisible();
    
    // Should show some results (assuming test data)
    const filmCards = page.locator('[data-testid="film-card"]');
    await expect(filmCards).toHaveCount.greaterThan(0);
  });
  
  test('expands film to show showings', async ({ page }) => {
    await page.goto('/');
    
    // Search
    await page.fill('input[type="date"]', '2024-01-25');
    await page.click('button:has-text("Find Films")');
    
    // Click first film card
    await page.locator('[data-testid="film-card"]').first().click();
    
    // Should show cinema and showings
    await expect(page.locator('[data-testid="cinema-name"]')).toBeVisible();
    await expect(page.locator('[data-testid="showing-time"]')).toBeVisible();
  });
  
  test('shows loading state', async ({ page }) => {
    await page.goto('/');
    
    // Slow down API response
    await page.route('**/api/showings*', async route => {
      await new Promise(r => setTimeout(r, 1000));
      await route.continue();
    });
    
    await page.fill('input[type="date"]', '2024-01-25');
    await page.click('button:has-text("Find Films")');
    
    // Should show loading indicator
    await expect(page.locator('[data-testid="loading"]')).toBeVisible();
  });
  
  test('shows error on API failure', async ({ page }) => {
    await page.goto('/');
    
    // Mock API failure
    await page.route('**/api/showings*', route => {
      route.fulfill({ status: 500 });
    });
    
    await page.fill('input[type="date"]', '2024-01-25');
    await page.click('button:has-text("Find Films")');
    
    // Should show error message
    await expect(page.locator('[data-testid="error"]')).toBeVisible();
  });
});
```

## CI/CD Configuration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml

name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: cinescout_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        working-directory: backend
        run: |
          pip install -e ".[dev]"
          playwright install chromium
      
      - name: Run tests
        working-directory: backend
        run: |
          pytest --cov=cinescout --cov-report=xml -m "not live"
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/cinescout_test
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: backend/coverage.xml

  frontend-tests:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '18'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
      
      - name: Install dependencies
        working-directory: frontend
        run: npm ci
      
      - name: Run tests
        working-directory: frontend
        run: npm test -- --coverage
      
      - name: Build
        working-directory: frontend
        run: npm run build

  e2e-tests:
    runs-on: ubuntu-latest
    needs: [backend-tests, frontend-tests]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '18'
      
      - name: Install Playwright
        run: npx playwright install --with-deps
      
      - name: Run E2E tests
        run: npx playwright test
```

## Test Coverage Goals

| Module | Target Coverage |
|--------|-----------------|
| Film Matcher | 90% |
| API Endpoints | 85% |
| Scrapers (parsing logic) | 80% |
| Scrapers (HTTP) | 50% (difficult to test) |
| Frontend Components | 80% |
| Frontend Hooks | 85% |

## Running Tests

### Backend

```bash
cd backend

# All tests (excluding live scraper tests)
pytest -m "not live"

# With coverage
pytest --cov=cinescout --cov-report=html -m "not live"

# Specific module
pytest tests/unit/test_film_matcher.py

# Live scraper tests (requires network)
pytest -m live

# Verbose output
pytest -v
```

### Frontend

```bash
cd frontend

# All tests
npm test

# Watch mode
npm test -- --watch

# With coverage
npm test -- --coverage

# Specific file
npm test -- SearchForm
```

### E2E

```bash
# Run all E2E tests
npx playwright test

# With UI
npx playwright test --ui

# Specific test
npx playwright test search.spec.ts
```
