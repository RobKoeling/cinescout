# CineScout

Find films showing in London cinemas within your time window.

## Overview

CineScout aggregates film showings from independent and arthouse cinemas in London, allowing you to search by date and time window. When you find a film you're interested in, expand it to see all venues and showtimes, check availability, and book tickets.

## Features

- Search for films by date and time window
- View aggregated listings from multiple cinemas
- Expand films to see all showings grouped by cinema with director, year, country, and cast
- Direct links to booking pages
- Film metadata from TMDb (director, year, country, cast, overview, runtime)
- SQLAdmin data management panel (CRUD + scrape/backfill triggers) on port 8001

## Implemented Cinemas

1. BFI Southbank
2. Curzon (Soho, Mayfair, Bloomsbury, Victoria)
3. Prince Charles Cinema
4. Picturehouse (Hackney, Central, etc.)
5. The Garden Cinema
6. Regent Street Cinema
7. Rio Cinema

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React + TypeScript + Vite + TailwindCSS |
| Backend | Python + FastAPI |
| Database | PostgreSQL |
| Scraping | Playwright (Python) |
| Cache | Redis |
| Film Data | TMDb API |

## Project Structure

```
cinescout/
├── backend/                 # Python FastAPI backend
│   ├── src/cinescout/      # Main package
│   │   ├── admin/          # SQLAdmin panel (port 8001)
│   │   ├── api/            # API routes
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── scrapers/       # Cinema scrapers
│   │   ├── services/       # Business logic
│   │   ├── tasks/          # Background jobs
│   │   └── scripts/        # One-off scripts (TMDb backfill, etc.)
│   ├── tests/              # Test suite
│   └── alembic/            # Database migrations
├── frontend/               # React + Vite frontend
│   └── src/
│       ├── components/     # React components
│       └── types/          # TypeScript types
└── docs/                   # Documentation
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (for local Postgres/Redis)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/cinescout.git
   cd cinescout
   ```

2. Start infrastructure:
   ```bash
   docker-compose up -d
   ```

3. Set up backend:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
   pip install -e ".[dev]"
   playwright install chromium
   cp ../.env.example .env
   # Edit .env with your TMDb API key
   alembic upgrade head
   ```

4. Set up frontend:
   ```bash
   cd frontend
   npm install
   ```

5. Run the development servers:
   ```bash
   # Terminal 1: Backend API
   cd backend && uvicorn cinescout.main:app --reload

   # Terminal 2: Admin panel
   cd backend && uvicorn cinescout.admin.app:admin_app --port 8001 --reload

   # Terminal 3: Frontend
   cd frontend && npm run dev
   ```

6. Open http://localhost:5173 (viewer) or http://localhost:8001/admin (admin panel)

## Documentation

- [Planning & Architecture](docs/01-planning.md)
- [Technical Specification](docs/02-technical-spec.md)
- [Testing Strategy](docs/03-testing-strategy.md)
- [API Reference](docs/04-api-reference.md)
- [Scraper Development Guide](docs/05-scraper-guide.md)

## Future Features

- [ ] User accounts and preferences
- [ ] Travel time integration (TfL API)
- [ ] Ticket purchasing passthrough
- [ ] Custom data sources (RSS, newsletters)
- [ ] Watch history tracking
- [ ] Multi-city support

## License

MIT
