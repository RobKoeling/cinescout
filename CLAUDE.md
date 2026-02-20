# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CineScout aggregates film showings from independent and arthouse cinemas in London and Brighton. Users search by date and time window to find what's playing across multiple venues. The backend scrapes cinema websites, matches film titles to TMDb metadata, and serves this via a FastAPI REST API. The frontend is a React + TypeScript SPA with distance calculations and TfL (Transport for London) public transport travel times for London cinemas.

## Architecture

### Monorepo Structure
- `backend/` - Python FastAPI backend
- `frontend/` - React + Vite frontend
- `docs/` - Comprehensive technical documentation

### Key Data Flow
1. **Scrapers** fetch showings from cinema websites (Playwright for JS-heavy sites, httpx for APIs/HTML)
2. **Film Matcher** normalizes titles and matches against existing films or TMDb API
3. **Database** stores cinemas, films, showings with PostgreSQL
4. **API** serves aggregated showings grouped by film, then by cinema
5. **Frontend** displays searchable, expandable film cards

### Database Schema Highlights
- **Cinemas**: Store scraper type/config, coordinates, capabilities (online booking, availability checks)
- **Films**: TMDb metadata (directors, countries, year), stored in PostgreSQL arrays
- **Film Aliases**: Maps cinema-specific titles to canonical films for matching
- **Showings**: Links cinema + film + time, stores raw title for debugging

## Development Commands

### Initial Setup
```bash
# Start infrastructure
docker-compose up -d

# Backend setup
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium
cp ../.env.example .env
# Edit .env with your TMDb API key from https://www.themoviedb.org/settings/api
alembic upgrade head

# Frontend setup
cd frontend
npm install
```

### Running Development Servers
```bash
# Terminal 1: Backend API
cd backend && uvicorn cinescout.main:app --reload

# Terminal 2: Admin panel
cd backend && uvicorn cinescout.admin.app:admin_app --port 8001 --reload

# Terminal 3: Frontend
cd frontend && npm run dev
```

Frontend at http://localhost:5173, backend API at http://localhost:8000, admin panel at http://localhost:8001/admin (login: admin / changeme by default)

### Testing

**Backend:**
```bash
cd backend

# All tests (excluding live scraper tests)
pytest -m "not live"

# With coverage report
pytest --cov=cinescout --cov-report=html -m "not live"

# Run live scraper tests (makes real HTTP requests)
pytest -m live

# Run specific test file
pytest tests/unit/test_film_matcher.py

# Run single test
pytest tests/unit/test_film_matcher.py::TestFilmMatcherNormalisation::test_removes_year_suffix
```

**Frontend:**
```bash
cd frontend

# Run all tests
npm test

# Watch mode for development
npm test -- --watch

# Coverage report
npm test -- --coverage

# Run specific test file
npm test -- SearchForm
```

**Linting:**
```bash
# Backend
cd backend
ruff check .
mypy src/cinescout

# Frontend
cd frontend
npm run lint
```

### Database Migrations
```bash
cd backend

# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

## Scraper Development

### Scraper Interface
All scrapers extend `BaseScraper` and implement:
- `get_showings(date_from, date_to) -> list[RawShowing]` - Required
- `get_availability(booking_url) -> dict | None` - Optional for real-time seat checks

### Creating a New Scraper
1. Research cinema website in browser DevTools Network tab for APIs
2. Create `backend/src/cinescout/scrapers/cinema_name.py`
3. Implement scraper (prefer API > HTML scraping > Playwright)
4. Use `self.normalise_title()` to clean film titles before returning
5. Register in `scrapers/__init__.py` SCRAPER_REGISTRY
6. Add cinema to database with matching `scraper_type`
7. Create test with saved fixture in `tests/scrapers/fixtures/cinema_name/`

### Title Normalization
Scrapers should normalize titles to improve matching:
- Remove year suffixes: "Film (2024)" → "Film"
- Remove prefixes: "Preview: Film" → "Film"
- Remove format indicators: "Film [35mm]" → "Film"
- Clean whitespace

The `FilmMatcher` service then:
1. Checks `film_aliases` table for exact match
2. Fuzzy matches against existing films (rapidfuzz, 85% threshold)
3. Searches TMDb API if no local match
4. Creates new film from TMDb data or placeholder
5. Stores alias for future lookups

### Scraper Testing Strategy
- **Unit tests**: Use saved fixtures from `tests/scrapers/fixtures/` (fast, deterministic)
- **Live tests**: Mark with `@pytest.mark.live`, skip in CI, run manually to verify scrapers still work
- Save new fixtures with browser DevTools or httpx responses to JSON files

## API Structure

Main endpoint: `GET /api/showings?date=YYYY-MM-DD&time_from=HH:MM&time_to=HH:MM`

Optional distance/travel time parameters:
- `user_lat` - User's latitude for distance calculation
- `user_lng` - User's longitude for distance calculation
- `use_tfl=true` - Enable TfL API for public transport travel times (London only)
- `transport_mode=public` - Transport mode (currently only "public" supported)

Response groups showings by film, then by cinema:
```json
{
  "films": [
    {
      "film": { "id": "...", "title": "...", "directors": [...], "year": 2024 },
      "cinemas": [
        {
          "cinema": {
            "id": "...",
            "name": "...",
            "address": "...",
            "distance_km": 2.5,
            "distance_miles": 1.55,
            "travel_time_minutes": 15,
            "travel_mode": "public"
          },
          "times": [
            { "start_time": "2024-01-25T18:30:00", "booking_url": "...", ... }
          ]
        }
      ]
    }
  ]
}
```

See `docs/04-api-reference.md` for full API documentation.

## Caching Strategy
| Data | TTL | Storage |
|------|-----|---------|
| Cinema list | 24 hours | Redis |
| Film metadata | 7 days | Database |
| Showings list | 15 minutes | Redis |
| Availability | 5 minutes | Redis |
| TfL journey times | 24 hours | Redis |

## Important Patterns

### Async/Await
The entire backend is async-native (FastAPI, SQLAlchemy with asyncpg, Playwright, httpx). Always use `async def` and `await`.

### Error Handling in Scrapers
Scrapers should never crash the system. Return empty list `[]` on errors, log warnings. Individual parsing failures should skip that showing, not abort the entire scrape.

### Database Sessions
Use dependency injection for `AsyncSession`:
```python
async def endpoint(db: AsyncSession = Depends(get_db)):
    # Use db here
```

### Frontend State Management
The frontend uses React hooks for state. No global state library planned for MVP.

## Environment Variables

Copy `.env.example` to `.env` and configure:
- `DATABASE_URL` - PostgreSQL connection (docker-compose provides default)
- `REDIS_URL` - Redis connection (optional for MVP)
- `TMDB_API_KEY` - Required for film metadata (get from https://www.themoviedb.org/settings/api)
- `TFL_APP_KEY` - Optional TfL API key for higher rate limits (get from https://api-portal.tfl.gov.uk/). API works without key (50 req/min), with key increases to 500 req/min
- `SCRAPE_TIMEOUT` - Timeout in seconds for scraper HTTP requests
- `SCRAPE_MAX_RETRIES` - Number of retry attempts for failed scrapes
- `ADMIN_USERNAME` / `ADMIN_PASSWORD` - Credentials for the SQLAdmin panel (default: admin / changeme)
- `ADMIN_SECRET_KEY` - Secret used to sign the admin session cookie (change in production)

## Code Style

**Python:**
- Line length: 100 characters
- Linter: ruff (selects E, F, I, N, W)
- Type checker: mypy (strict mode)
- Use type hints everywhere
- Follow FastAPI/Pydantic patterns for API schemas

**TypeScript:**
- ESLint with React hooks plugin
- Prefer functional components with hooks
- Keep components focused and composable

## Testing Philosophy

Follow the testing pyramid:
- **70% Unit tests**: Fast, focused on individual functions/classes
- **20% Integration tests**: API endpoints with database
- **10% E2E tests**: Critical user flows with Playwright

Target coverage:
- Film Matcher: 90%
- API Endpoints: 85%
- Scrapers (parsing): 80%
- Frontend Components: 80%

Mark tests that make real HTTP requests with `@pytest.mark.live` to exclude from CI.

## File Organization

**Backend:**
- `src/cinescout/admin/` - SQLAdmin panel (auth, model views, scrape tools) — served on port 8001
- `src/cinescout/api/` - FastAPI route handlers
- `src/cinescout/models/` - SQLAlchemy ORM models
- `src/cinescout/schemas/` - Pydantic request/response schemas
- `src/cinescout/scrapers/` - Cinema-specific scrapers
- `src/cinescout/services/` - Business logic (FilmMatcher, TMDb client, TfL client, etc.)
- `src/cinescout/utils/` - Utility functions (Haversine distance calculation, etc.)
- `src/cinescout/tasks/` - Background jobs (scheduled scraping)
- `src/cinescout/scripts/` - One-off scripts (TMDb backfill, seed data, etc.)

**Frontend:**
- `src/api/` - API client (fetch wrappers)
- `src/components/` - React components
- `src/hooks/` - Custom hooks (useShowings, etc.)
- `src/types/` - TypeScript type definitions

## Distance & Travel Time Feature

The distance feature helps users find nearby cinemas and plan their journey:

**Backend Implementation:**
- `utils/geo.py` - Haversine formula for straight-line distance calculation
- `services/tfl_client.py` - TfL Journey Planner API client with Redis caching
- Distance enrichment happens in `api/routes/showings.py` via `enrich_cinemas_with_distance()`
- All cinemas have latitude/longitude in the database

**How it works:**
1. User provides location (browser geolocation or manual address via Nominatim geocoding)
2. Frontend sends `user_lat`, `user_lng` to API
3. Backend calculates straight-line distance (Haversine) for all cinemas
4. If `use_tfl=true` for London cinemas: call TfL API for public transport travel time
5. Response includes `distance_km`, `distance_miles`, `travel_time_minutes` for each cinema
6. Frontend displays: "2.5 mi • 🚇 15 min" or just "2.5 mi" if no TfL data

**TfL API limitations:**
- Only works reliably for public transport mode (tube/bus)
- Walking/cycling modes have limited coverage (often return 404/400 errors)
- Falls back gracefully to showing only straight-line distance when TfL fails

**Caching:**
- TfL API responses cached in Redis for 24 hours
- Cache key: `tfl:{dest_lat}:{dest_lng}:{origin_lat}:{origin_lng}:{mode}`
- Coordinates rounded to 4 decimals (~11m precision) for better cache hit rates

## Common Pitfalls

1. **Scraper timezones**: Cinema websites often use local time without timezone info. Assume London timezone (UTC/BST).
2. **Film matching false positives**: Don't fuzzy match below 85% threshold or you'll merge unrelated films.
3. **Unique constraints**: `showings` table has unique constraint on `(cinema_id, film_id, start_time)`. Handle conflicts on scraper re-runs.
4. **Playwright cleanup**: Always close pages in `finally` blocks to avoid browser memory leaks.
5. **SQLAlchemy sessions**: Always `await session.commit()` to persist changes.
6. **TfL API SSL**: The TfL client has SSL verification disabled for development (`verify=False` in httpx). This is a workaround for macOS certificate issues.

## Future Enhancements

See README.md for roadmap, including:
- User accounts and watch history
- Expanded multi-city support (beyond London & Brighton)
- Custom data sources (RSS feeds)
- Walking/cycling travel time estimates
