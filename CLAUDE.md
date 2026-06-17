# CineScout

CineScout aggregates film showings from independent and arthouse cinemas in London and Brighton.
Users search by date/time window; the backend scrapes venues, matches titles via TMDb, and serves
a FastAPI REST API. The frontend is a React + TypeScript SPA.

## Repo layout

```
backend/   Python FastAPI — scrapers, film matcher, API, admin panel
frontend/  React + Vite SPA
docs/      Technical documentation
```

Sub-docs (loaded automatically when working in each area):

- `backend/CLAUDE.md` — backend dev commands, scrapers, API patterns, DB migrations
- `frontend/CLAUDE.md` — frontend dev commands, component structure
- `.claude/deployment.md` — Fly.io deploy workflow and known pitfalls
- `.claude/debugging.md` — debugging approach and common pitfalls

## Key data flow

1. **Scrapers** fetch showings (Playwright for JS-heavy sites, httpx for APIs/HTML)
2. **FilmMatcher** normalises titles → alias lookup → fuzzy match → TMDb API
3. **PostgreSQL** stores cinemas, films, showings; Redis caches API responses
4. **API** serves showings grouped by film → cinema
5. **Frontend** renders expandable film cards with booking links and RT buttons

## Working conventions

- The entire backend is async-native. Always use `async def` / `await`.
- Scrapers must never crash the caller — return `[]` on any error and log a warning.
- Confirm the correct worktree/directory before running `fly deploy`. See `.claude/deployment.md`.
- Ask before adding any new feature or page not explicitly requested.
