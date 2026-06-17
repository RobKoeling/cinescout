# Backend

FastAPI + SQLAlchemy (asyncpg) + Alembic. Python 3.13, strict mypy, ruff linter.

## Dev setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
cp ../.env.example .env   # add TMDB_API_KEY
alembic upgrade head
```

## Running locally

```bash
# API (port 8000)
uvicorn cinescout.main:app --reload

# Admin panel (port 8001) — login: admin / changeme by default
uvicorn cinescout.admin.app:admin_app --port 8001 --reload
```

## Testing

```bash
pytest -m "not live"                          # fast unit + integration tests
pytest -m live                                # real HTTP — run manually only
pytest --cov=cinescout --cov-report=html -m "not live"
ruff check .
mypy src/cinescout
```

Mark any test that makes real HTTP requests `@pytest.mark.live`.

## Database migrations

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

## File layout

```
src/cinescout/
  admin/      SQLAdmin panel (served on :8001)
  api/        FastAPI route handlers
  models/     SQLAlchemy ORM models
  schemas/    Pydantic request/response schemas
  scrapers/   Cinema-specific scrapers
  services/   FilmMatcher, TMDb client, TfL client, …
  tasks/      Background scrape jobs
  scripts/    One-off scripts (backfill, seed data, …)
  utils/      Haversine distance, etc.
```

## Scrapers

**Interface** — extend `BaseScraper` and implement:
- `get_showings(date_from, date_to) -> list[RawShowing]` (required)
- `get_availability(booking_url) -> dict | None` (optional)

**Adding a new scraper:**
1. Check DevTools Network tab — prefer REST API > HTML scraping > Playwright
2. Create `scrapers/cinema_name.py`
3. Call `self.normalise_title()` on every title before returning
4. Register in `scrapers/__init__.py` SCRAPER_REGISTRY
5. Add the cinema row to the database (`scraper_type` must match)
6. Write a fixture-based unit test in `tests/scrapers/fixtures/cinema_name/`

**Title normalisation** (done by `normalise_title()`):
- Strips year suffixes `(2024)`, prefixes `Preview:`, format tags `[35mm]`
- Downstream `FilmMatcher`: alias lookup → fuzzy match (85% threshold) → TMDb

**Year extraction** — scrapers should populate `RawShowing.year` where the data
source exposes it (e.g. Curzon `relatedData.films`, BFI `searchResults[17]`
keywords field). Year hints improve film disambiguation.

**Known site-blocking issues:**
- Curzon `www.curzon.com` blocks cloud/datacenter IPs (Cloudflare).
  On Fly.io the scraper uses `CURZON_AUTH_TOKEN` env secret instead of fetching live.
  Refresh the token every ~10 h from a local machine:
  `python -m cinescout.scripts.refresh_curzon_token`
- BFI uses Playwright + stealth to bypass Cloudflare; can be slow/flaky on Fly.io.

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | yes | asyncpg URL; docker-compose provides default |
| `TMDB_API_KEY` | yes | https://www.themoviedb.org/settings/api |
| `REDIS_URL` | no | falls back to in-process cache |
| `TFL_APP_KEY` | no | 50 req/min without; 500 with |
| `CURZON_AUTH_TOKEN` | prod | JWT, 12 h TTL — set via `fly secrets set` |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | yes (prod) | default: admin / changeme |
| `ADMIN_SECRET_KEY` | yes (prod) | signs session cookie |

## Caching TTLs

| Data | TTL | Backend |
|---|---|---|
| Showings list | 15 min | Redis |
| Cinema list | 24 h | Redis |
| TfL journey times | 24 h | Redis |
| Film metadata | 7 days | DB |
