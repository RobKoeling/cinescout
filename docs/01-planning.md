# CineScout: Planning Document

## Problem Statement

Every Thursday, the user travels to London for office work and wants to catch a film afterwards. Current cinema listing services don't provide a convenient way to:

1. See all films showing across multiple cinemas in a single view
2. Filter by a specific time window (e.g., 18:00-21:00)
3. Quickly compare options and book tickets

The result is spending considerable time checking individual cinema websites to build a shortlist manually.

## Solution

A web service that, given a city and time window, returns all films showing within that window, organised by film rather than by cinema. Clicking a film expands to show all venues and showtimes with booking links.

## Core Requirements (MVP)

1. **Search**: Specify city (London for MVP), date, and time window
2. **Film List**: Display all unique films with basic metadata (title, director, year, country)
3. **Expandable Detail**: Click to see all cinemas showing that film with times
4. **Booking Info**: Show booking links, prices (where available), and availability status
5. **Fallback Contact**: If online booking unavailable, show cinema contact details

## Future Features (Post-MVP)

| Feature | Description | Priority |
|---------|-------------|----------|
| Route Planning | Order cinemas by travel time from current/set location | High |
| Ticket Purchase | Passthrough booking via cinema box office APIs | Medium |
| Custom Sources | Add URLs, newsletters, or RSS feeds as extra data sources | Medium |
| User Accounts | Save preferences, track watch history | Low |
| Multi-City | Expand beyond London | Low |

## Critical Analysis

### The Hard Problems

**1. Data Acquisition**

This is the core challenge. London cinemas don't publish unified APIs. Options:

| Approach | Pros | Cons |
|----------|------|------|
| Web Scraping | Works with any site | Maintenance burden, ToS concerns, fragile |
| Aggregator APIs | Clean data | Expensive, limited UK coverage |
| Manual Curation | Reliable | Doesn't scale |

**Decision**: Web scraping is the pragmatic choice for MVP. Start with 6 cinemas that matter to the user. Accept the maintenance cost.

**2. Real-time Availability**

Checking availability for every showing on every request would be:
- Slow (multiple requests per cinema)
- Rate-limited (aggressive scraping may be blocked)
- Stale (availability changes constantly)

**Decision**: Lazy loading. Show availability as "unknown" initially. Check on-demand when user expands a film. Cache aggressively (5-10 min TTL).

**3. Film Matching**

Different cinemas list films with different titles:
- "The Godfather" vs "The Godfather (1972)" vs "GODFATHER, THE"
- Foreign language titles vs English titles
- Special screenings with prefixes ("Preview: ...")

**Decision**: Use TMDb API for canonical film data. Build a fuzzy matching system with an aliases table to learn from corrections.

### What's Good About This Idea

- **Clear personal use case**: The user knows exactly what they want
- **Genuine gap**: Existing tools are poor for this workflow
- **Natural expansion path**: Future features are logical progressions
- **Modest initial scope**: One city, 6 cinemas, one use case

## Target Cinemas

| Cinema | Type | Notes |
|--------|------|-------|
| BFI Southbank | Arthouse | Complex programme, retrospectives, good data structure |
| Curzon | Chain/Arthouse | Multiple venues, modern site |
| Prince Charles Cinema | Repertory | Cult classics, quirky programming |
| Picturehouse | Chain | Multiple London venues, consistent format |
| Barbican | Arts Centre | Mixed programme, part of larger arts complex |
| The Garden Cinema | Independent | Curated programme, newer venue |

## Mobile App Considerations

For eventual mobile support:

1. **API-first design**: Keep all business logic in backend. Frontend is a thin client.
2. **PWA as intermediate step**: Progressive Web App can work offline, be installed, send notifications.
3. **React Native later**: Same API supports native mobile apps when needed.

**Recommendation**: Build as responsive web app first. Prove concept. Decide on native mobile based on actual usage.

## Development Phases

### Phase 1: Foundation (Days 1-3)
- Project structure (monorepo with frontend + backend)
- Docker setup for local Postgres/Redis
- Database models and migrations
- Seed cinema data
- Basic FastAPI app with health check
- Basic React app with search form

### Phase 2: First Scraper (Days 4-6)
- Scraper framework (BaseScraper)
- BFI scraper (has API-like endpoint)
- Film matcher with TMDb integration
- Store scraped data in database
- Manual scrape trigger endpoint

### Phase 3: API & Frontend Integration (Days 7-9)
- `/showings` endpoint with grouping logic
- Connect frontend to API
- Film list with expand/collapse
- Basic styling with Tailwind

### Phase 4: More Scrapers (Days 10-14)
- Curzon scraper
- Garden Cinema scraper
- Prince Charles scraper
- Graceful error handling

### Phase 5: Polish (Days 15-17)
- Scheduled scraping (daily job)
- Caching layer
- Loading states and error handling
- Responsive design
- Basic filtering/sorting

### Phase 6: Deployment (Days 18-20)
- Set up Railway/Render
- Configure production database
- Environment variables
- Deploy and test
