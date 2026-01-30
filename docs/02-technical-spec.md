# CineScout: Technical Specification

## Tech Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Frontend | React + TypeScript + Vite | Interactive UI, good DX |
| Styling | TailwindCSS | Clean, minimal, fast iteration |
| Backend | Python + FastAPI | Modern, async-native, great type hints, auto-generates OpenAPI docs |
| Scraping | Playwright (Python) | Handles JS-rendered sites, async support |
| Database | PostgreSQL + SQLAlchemy | Robust ORM, async support via `asyncpg` |
| Cache | Redis (via `redis-py`) | Async support, good for availability caching |
| Task Queue | Celery or `arq` | Scheduled scraping jobs |
| Film Data | TMDb API | Free tier sufficient, good metadata |
| Hosting | Railway or Render | Easy Python/Postgres/Redis deployment |

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                │
│  React + TypeScript + TailwindCSS                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Search Form │  │ Film List   │  │ Film Detail │             │
│  │ (city/time) │  │ (collapsed) │  │ (expanded)  │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         API LAYER                               │
│  Python FastAPI                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ /showings   │  │ /films/:id  │  │ /cinemas    │             │
│  │             │  │ /availability│  │             │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA SERVICES                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │ Scraper Service │  │ Film Metadata   │  │ Cache Layer    │  │
│  │ (per-cinema     │  │ Service (TMDb)  │  │ (Redis)        │  │
│  │  adapters)      │  │                 │  │                │  │
│  └─────────────────┘  └─────────────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       PERSISTENCE                               │
│  PostgreSQL                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ cinemas  │ │ films    │ │ showings │ │ users    │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

## Database Schema

### Cinema Table

```sql
CREATE TABLE cinemas (
    id VARCHAR(50) PRIMARY KEY,           -- e.g., "bfi-southbank"
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    
    -- Location
    address VARCHAR(500) NOT NULL,
    city VARCHAR(100) NOT NULL,
    latitude FLOAT,
    longitude FLOAT,
    
    -- Links
    website VARCHAR(500) NOT NULL,
    booking_url VARCHAR(500),
    
    -- Scraper config
    scraper_type VARCHAR(50) NOT NULL,    -- "bfi", "curzon", etc.
    scraper_config JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Contact (fallback)
    phone VARCHAR(50),
    email VARCHAR(200),
    
    -- Capabilities
    supports_online_booking BOOLEAN DEFAULT TRUE,
    supports_availability_check BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_cinemas_city ON cinemas(city);
CREATE INDEX idx_cinemas_slug ON cinemas(slug);
```

### Film Table

```sql
CREATE TABLE films (
    id VARCHAR(50) PRIMARY KEY,
    
    -- Core metadata
    title VARCHAR(500) NOT NULL,
    original_title VARCHAR(500),
    year INTEGER,
    
    -- Credits (PostgreSQL arrays)
    directors TEXT[] DEFAULT '{}',
    countries TEXT[] DEFAULT '{}',
    
    -- Additional metadata
    runtime_minutes INTEGER,
    poster_url VARCHAR(500),
    synopsis TEXT,
    
    -- External IDs
    tmdb_id INTEGER UNIQUE,
    imdb_id VARCHAR(20) UNIQUE,
    
    -- Tracking
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_films_title ON films(title);
CREATE INDEX idx_films_year ON films(year);
CREATE INDEX idx_films_tmdb_id ON films(tmdb_id);
```

### Film Aliases Table

```sql
CREATE TABLE film_aliases (
    id SERIAL PRIMARY KEY,
    film_id VARCHAR(50) REFERENCES films(id),
    alias VARCHAR(500) NOT NULL,
    source VARCHAR(100),                   -- Which cinema uses this
    
    UNIQUE(film_id, alias)
);

CREATE INDEX idx_film_aliases_alias ON film_aliases(alias);
CREATE INDEX idx_film_aliases_film_id ON film_aliases(film_id);
```

### Showing Table

```sql
CREATE TABLE showings (
    id VARCHAR(100) PRIMARY KEY,
    
    -- Foreign keys
    cinema_id VARCHAR(50) REFERENCES cinemas(id),
    film_id VARCHAR(50) REFERENCES films(id),
    
    -- Timing
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    
    -- Screening details
    screen VARCHAR(100),
    format VARCHAR(50),                    -- "2D", "35mm", "IMAX"
    
    -- Booking
    booking_url VARCHAR(1000),
    price_amount FLOAT,
    price_currency VARCHAR(3) DEFAULT 'GBP',
    
    -- Tracking
    scraped_at TIMESTAMP DEFAULT NOW(),
    raw_title VARCHAR(500) NOT NULL,       -- Original title from cinema
    
    UNIQUE(cinema_id, film_id, start_time)
);

CREATE INDEX idx_showings_cinema_id ON showings(cinema_id);
CREATE INDEX idx_showings_film_id ON showings(film_id);
CREATE INDEX idx_showings_start_time ON showings(start_time);
```

## API Endpoints

### GET /api/showings

Search for showings within a time window.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| city | string | No | City to search (default: "london") |
| date | date | Yes | Date to search (YYYY-MM-DD) |
| time_from | time | No | Earliest start time (HH:MM) |
| time_to | time | No | Latest start time (HH:MM) |

**Response:**

```json
{
  "films": [
    {
      "film": {
        "id": "abc123",
        "title": "The Godfather",
        "year": 1972,
        "directors": ["Francis Ford Coppola"],
        "countries": ["US"],
        "showing_count": 3
      },
      "cinemas": [
        {
          "cinema": {
            "id": "prince-charles",
            "name": "Prince Charles Cinema",
            "slug": "prince-charles",
            "address": "7 Leicester Place, London WC2H 7BY",
            "city": "london",
            "website": "https://princecharlescinema.com",
            "supports_online_booking": true,
            "coordinates": { "lat": 51.5112, "lng": -0.1305 },
            "contact": { "phone": "020 7494 3654" }
          },
          "times": [
            {
              "id": "showing-001",
              "start_time": "2024-01-25T18:30:00",
              "screen": "Screen 1",
              "format": "35mm",
              "booking_url": "https://...",
              "price": { "amount": 12.50, "currency": "GBP" },
              "availability": "unknown"
            }
          ]
        }
      ]
    }
  ],
  "total_films": 15,
  "total_showings": 42,
  "query": {
    "city": "london",
    "date": "2024-01-25",
    "time_from": "18:00",
    "time_to": "21:00"
  }
}
```

### GET /api/showings/{showing_id}/availability

Check real-time availability for a specific showing.

**Response:**

```json
{
  "showing_id": "showing-001",
  "availability": "available",
  "price": { "amount": 12.50, "currency": "GBP" }
}
```

Availability values: `available`, `limited`, `sold_out`, `unknown`

### GET /api/cinemas

List all active cinemas.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| city | string | No | Filter by city |

### POST /api/admin/scrape

Trigger a manual scrape (admin only, for development).

**Request Body:**

```json
{
  "cinema_ids": ["bfi-southbank"],
  "date_from": "2024-01-25",
  "date_to": "2024-01-26"
}
```

## Scraper Interface

All scrapers implement this interface:

```python
class BaseScraper(ABC):
    cinema_id: str
    base_url: str
    
    @abstractmethod
    async def get_showings(
        self, 
        date_from: date, 
        date_to: date
    ) -> list[RawShowing]:
        """Fetch all showings for the given date range."""
        pass
    
    async def get_availability(
        self, 
        booking_url: str
    ) -> dict | None:
        """Check real-time availability. Override if supported."""
        return None
```

### RawShowing Data Class

```python
@dataclass
class RawShowing:
    film_title: str
    start_time: datetime
    cinema_id: str
    
    end_time: datetime | None = None
    screen: str | None = None
    format: str | None = None
    booking_url: str | None = None
    price_amount: float | None = None
    price_currency: str = "GBP"
    raw_data: dict = field(default_factory=dict)
```

## Film Matching Strategy

1. **Normalise** the raw title (remove year suffixes, prefixes, clean whitespace)
2. **Check aliases** table for exact match
3. **Fuzzy match** against existing films (using rapidfuzz, threshold 85%)
4. **Search TMDb** if no local match
5. **Create film** from TMDb data if confident match
6. **Create placeholder** if no match found
7. **Store alias** for future lookups

## Frontend Components

| Component | Purpose |
|-----------|---------|
| `SearchForm` | Date/time inputs, search button |
| `FilmList` | Scrollable list of films with count |
| `FilmCard` | Collapsed view (title, director, year, country) |
| `FilmDetail` | Expanded view with cinema/showings |
| `ShowingRow` | Individual showing with time, price, book button |
| `CinemaInfo` | Cinema details (address, contact) |
| `LoadingSpinner` | Loading state indicator |

## Error Handling

### Scraper Errors

- **Network errors**: Retry with exponential backoff (max 3 attempts)
- **Parse errors**: Log and skip individual showings, continue with others
- **Rate limiting**: Respect `Retry-After` headers, implement delays

### API Errors

- **400 Bad Request**: Invalid query parameters
- **404 Not Found**: Showing/cinema not found
- **500 Internal Server Error**: Unexpected errors (log, return generic message)

### Frontend Errors

- Display user-friendly error messages
- Maintain partial results where possible
- Offer retry option for transient errors

## Caching Strategy

| Data | TTL | Storage |
|------|-----|---------|
| Cinema list | 24 hours | Redis |
| Film metadata | 7 days | Database |
| Showings list | 15 minutes | Redis |
| Availability | 5 minutes | Redis |

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/cinescout

# Redis
REDIS_URL=redis://localhost:6379

# TMDb API
TMDB_API_KEY=your_api_key

# Scraping
SCRAPE_TIMEOUT=30
SCRAPE_MAX_RETRIES=3

# API
API_HOST=0.0.0.0
API_PORT=8000
```
