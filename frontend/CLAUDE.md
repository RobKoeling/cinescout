# Frontend

React 18 + TypeScript + Vite + Tailwind CSS. No global state library — React hooks only.

## Dev setup

```bash
cd frontend
npm install
```

## Running locally

```bash
npm run dev      # http://localhost:5173
npm test         # vitest unit tests
npm run lint     # ESLint
```

Set `VITE_API_URL` in `.env` if the backend is not on `http://localhost:8000`.

## File layout

```
src/
  api/          fetch wrappers for the backend API
  components/   React components (one file per component)
  hooks/        custom hooks (useShowings, …)
  types/        TypeScript type definitions
```

## Key components

| Component | Role |
|---|---|
| `App.tsx` | root — search state, city toggle, modal orchestration |
| `SearchForm.tsx` | date/time/mode inputs, geolocation, format filter |
| `FilmList.tsx` | renders a list of `FilmCard`s |
| `FilmCard.tsx` | collapsible card — title, year, RT link, cinemas, showtimes |
| `RTLink.tsx` | fetches `/api/films/rt-check` and renders 🍅 if valid |
| `CinemaModal.tsx` | day schedule for a single cinema |
| `DirectorModal.tsx` | other films by a director currently showing |

## RT link pattern

`RTLink` is driven by the backend `/api/films/rt-check?title=…&year=…` endpoint.
Pass `film.title` (canonical TMDb title, not `displayTitle`) and `film.year`.
The backend tries year-qualified slugs first, then validates the bare slug against
the RT page year to suppress links to wrong films.

## Code style

- Functional components with hooks only
- ESLint + React hooks plugin — run `npm run lint` before committing
- Keep components focused; extract hooks for any non-trivial async logic
