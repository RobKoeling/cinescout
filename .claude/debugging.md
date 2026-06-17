# Debugging

## General approach

1. **Reproduce first** — identify the exact failing case before touching code
2. **Fix the root cause** — not the symptom. If a first fix doesn't fully hold, dig deeper
3. **Validate against all known cases** — don't declare done until every problem case passes
4. **Write a regression test** — so the same bug can't silently return

## Scraper failures

Common causes, in rough order of likelihood:

| Symptom | Likely cause |
|---|---|
| `0 new showings` after scrape | Showings already in DB (normal on re-run); check date range |
| `403 Forbidden` | IP blocking (Curzon/Cloudflare) — see deployment.md |
| `unexpected connection_lost()` | Stale asyncpg connection — `pool_pre_ping` should catch this |
| Wrong film matched | Bad alias in DB, or year hint missing; check `film_aliases` table |
| Film matched to wrong RT link | Year mismatch — check `film.year` and RT page year via `/api/films/rt-check` |
| Playwright hangs | Cloudflare challenge not clearing (BFI) — check `CLOUDFLARE_INDICATORS` |

## Film matching issues

The matching pipeline: alias lookup → fuzzy match (≥85%) → TMDb search

- Wrong match? Check the `film_aliases` table — a stale alias may be routing to the wrong film
- Delete the bad alias row and re-scrape; the matcher will create a fresh one
- If a title is genuinely ambiguous, the scraper needs to extract and pass `RawShowing.year`
- Fuzzy threshold is 85% — don't lower it or unrelated films will merge

## DB connection issues

If you see `unexpected connection_lost()` or similar asyncpg errors during a scrape:
- The connection pool had stale connections
- Fix is already in place: `pool_pre_ping=True` + `pool_recycle=300` in `database.py`
- If it reappears, check whether the Postgres machine restarted recently

## Checking the hosted DB

Direct DB access via `fly postgres connect` requires wireguard. Easier alternatives:

```bash
# Query via the API
curl "https://cinescout-api.fly.dev/api/showings?date=YYYY-MM-DD&time_from=00:00&time_to=23:59"

# Check scraper logs
fly logs -a cinescout-api --no-tail | grep -E "Scraped|ERROR|new showings"
```

## Common pitfalls

- **Timezone**: cinema websites use local time without TZ info. Always attach `Europe/London`
- **Unique constraint** on `(cinema_id, film_id, start_time)` — re-runs update existing rows, not insert
- **Playwright**: always close browser in a `finally` block to avoid memory leaks
- **SSL on macOS**: `verify=False` in httpx is intentional — macOS certificate chain issue
- **Ollama**: used locally for title extraction; not available on Fly.io (fails silently/harmlessly)
