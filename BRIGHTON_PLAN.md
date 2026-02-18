# Plan: Brighton as Second City

## Overview

Six pieces of work, roughly in dependency order.

---

## 1. Frontend: City Selector

Add a city tab bar to the app header (London | Brighton). The selected city is passed to all API calls and the DirectorModal.

**Files:** `frontend/src/App.tsx`, `frontend/src/components/SearchForm.tsx`

- `App.tsx`: add `city` state (`'london' | 'brighton'`), render tab pills in the header, thread `city` into `handleSearch`, `handleLiveFormatChange`, `DirectorModal`, and `CinemaModal`.
- `SearchForm.tsx`: remove the hardcoded `city` and receive it as a prop (or pass it via `onSearch`).
- All API URLs: replace hardcoded `"london"` references with the active city.

---

## 2. Picturehouse Brighton Venues

Two Brighton Picturehouse venues can use the **existing scraper** once we know their internal API IDs.

**Cinemas to add:**
| ID (seed) | Name | cinema_slug | API ID (TBD) |
|---|---|---|---|
| `duke-of-yorks-picturehouse` | Duke of York's Picturehouse | `duke-of-yorks-picturehouse` | ? |
| `dukes-at-komedia` | Duke's at Komedia | `dukes-at-komedia` | ? |

**Steps:**
1. Discover the Picturehouse API IDs by hitting the API and filtering by city or checking the website's JS bundle. The existing `CINEMA_ID_MAP` shows the pattern (e.g. `"010"`, `"011"`).
2. Add both slugs → IDs to `CINEMA_ID_MAP` in `backend/src/cinescout/scrapers/picturehouse.py`.
3. Add both cinemas to `backend/src/cinescout/scripts/seed_cinemas.py` with `city: "brighton"`, correct address/postcode/coords, and `scraper_type: "picturehouse"` + `scraper_config: {"cinema_slug": "<slug>"}`.
4. Run `seed_cinemas.py`.

---

## 3. Depot Lewes Scraper

The Depot uses a **WordPress + Jacro cinema management plugin** with dynamic AJAX loading.

**Investigation needed first:** try hitting `https://lewesdepot.org/wp-admin/admin-ajax.php` directly with httpx to see if the film listing data can be retrieved without a browser. If the AJAX action name/nonce can be found in the page source, a pure httpx approach is possible. Otherwise, use Playwright.

**Likely approach (Playwright):**
```python
# scrapers/depot_lewes.py
class DepotLewesScraper(BaseScraper):
    # Navigate to https://lewesdepot.org/whats-on/
    # Wait for .film-title / .film_showtime elements to render
    # Parse date headers + film rows + show times
```

**Key parsing targets (from Jacro CSS classes):**
- `.film-title` / `.poster_name h3` — film title
- `.film_showtime` — time
- `.show_date` — date

**File:** `backend/src/cinescout/scrapers/depot_lewes.py`
**Register in:** `backend/src/cinescout/scrapers/__init__.py`
**Seed entry:** `city: "brighton"` (Lewes grouped under Brighton for simplicity)

---

## 4. Screen-Shot Brighton Scraper

screen-shot.co.uk uses **The Events Calendar REST API** — identical format to the Cinema Museum scraper. It is an aggregator covering alternative/pop-up film events across Brighton and Sussex.

**API endpoint:** `https://screen-shot.co.uk/wp-json/tribe/events/v1/events`

**Key differences from Cinema Museum:**
- Multiple venues per scrape — each event has a `venue` object with `venue.venue` (name) and `venue.address`.
- Store the venue name in `screen_name` so users can see where each event is.
- Skip events whose venue name matches a cinema we already scrape individually (e.g., "Lewes Depot" / "The Depot") to avoid duplicates.
- May need broader category filtering — check `categories` to exclude non-film events (workshops, talks, etc. that aren't screenings).

**Cinema seed entry:**
```python
{
    "id": "screen-shot-brighton",
    "name": "Screen-Shot Brighton",
    "city": "brighton",
    "address": "Various venues, Brighton & Sussex",
    "scraper_type": "screen-shot",
    "has_online_booking": True,
}
```

**Scraper sketch:**
```python
# scrapers/screen_shot.py
class ScreenShotScraper(BaseScraper):
    API_URL = "https://screen-shot.co.uk/wp-json/tribe/events/v1/events"
    SKIP_VENUES = {"lewes depot", "the depot"}  # venues scraped separately

    def _parse_event(self, event, ...) -> list[RawShowing]:
        venue_name = (event.get("venue") or {}).get("venue", "")
        if venue_name.lower() in self.SKIP_VENUES:
            return []
        return [RawShowing(
            title=...,
            start_time=...,
            booking_url=event.get("url"),
            screen_name=venue_name or None,
        )]
```

**File:** `backend/src/cinescout/scrapers/screen_shot.py`
**Register in:** `backend/src/cinescout/scrapers/__init__.py`

---

## 5. Scrape Scheduling

Screen-shot.co.uk is updated monthly. Include it in the **existing weekly scrape** (`run_scrape_all`) — scraping weekly is harmless even if upstream only updates monthly; it means new events are picked up within a week of publication.

No scheduler changes needed.

---

## 6. Suggested Implementation Order

1. **Frontend city selector** — unblocks manual testing of Brighton results.
2. **Picturehouse API IDs** — quick win, reuses existing scraper.
3. **Seed Brighton cinemas** — puts all four cinemas into the DB.
4. **Screen-Shot scraper** — straightforward port of Cinema Museum scraper.
5. **Depot Lewes scraper** — most uncertain (AJAX investigation needed); do this last.
6. **Run scrapes + verify** — trigger scrape for each Brighton cinema, check results.

---

## Open Questions

- **Depot Lewes AJAX**: Can we hit `admin-ajax.php` directly, or is Playwright required? Need to inspect the network tab on the What's On page.
- **Picturehouse API IDs**: Need to find the numeric IDs for the two Brighton venues.
- **Screen-Shot venue deduplication**: Is "Lewes Depot" the exact venue name used in the API, or a variant? Confirm from a live API call.
- **Lewes as part of Brighton city**: The DB groups all these venues under `city = "brighton"`. Lewes is a separate town ~8 miles away — acceptable for MVP, could refine later.
