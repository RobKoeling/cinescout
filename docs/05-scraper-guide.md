# CineScout: Scraper Development Guide

This guide explains how to create new scrapers for cinema websites.

## Overview

Each cinema needs its own scraper that implements the `BaseScraper` interface. Scrapers are responsible for:

1. Fetching listings from the cinema's website
2. Parsing the response into `RawShowing` objects
3. Handling errors gracefully

## Scraper Interface

All scrapers must extend `BaseScraper`:

```python
from abc import ABC, abstractmethod
from datetime import date
from cinescout.scrapers.base import BaseScraper, RawShowing

class MyCinemaScraper(BaseScraper):
    cinema_id = "my-cinema"  # Unique identifier
    base_url = "https://mycinema.com"
    
    async def get_showings(
        self, 
        date_from: date, 
        date_to: date
    ) -> list[RawShowing]:
        """Fetch showings for the date range."""
        # Implementation here
        pass
    
    async def get_availability(
        self, 
        booking_url: str
    ) -> dict | None:
        """Optional: Check real-time availability."""
        return None  # Return None if not supported
```

## RawShowing Data Class

```python
@dataclass
class RawShowing:
    # Required fields
    film_title: str           # Title as shown on cinema site
    start_time: datetime      # Showing start time
    cinema_id: str            # Must match scraper's cinema_id
    
    # Optional fields
    end_time: datetime | None = None
    screen: str | None = None        # "Screen 1", "NFT1", etc.
    format: str | None = None        # "35mm", "IMAX", "2D"
    booking_url: str | None = None   # Direct link to book tickets
    price_amount: float | None = None
    price_currency: str = "GBP"
    
    # Debug info
    raw_data: dict = field(default_factory=dict)  # Store original response
```

## Scraping Approaches

### 1. API-based (Preferred)

Some cinemas expose internal APIs. These are the most reliable.

```python
async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{self.base_url}/api/showtimes",
            params={"from": date_from.isoformat()},
            headers={"Accept": "application/json"},
            timeout=30.0
        )
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        return self._parse_api_response(data)
```

**How to find APIs:**
1. Open cinema website in browser
2. Open Developer Tools (F12) → Network tab
3. Navigate to listings page
4. Look for XHR/Fetch requests returning JSON
5. Note the URL pattern and parameters

### 2. HTML Scraping with HTTPX

For simple HTML pages that don't require JavaScript:

```python
async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
    from bs4 import BeautifulSoup
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{self.base_url}/whats-on",
            timeout=30.0
        )
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        showings = []
        for card in soup.select(".film-card"):
            title = card.select_one(".title").text.strip()
            # ... parse other fields
            showings.append(RawShowing(...))
        
        return showings
```

### 3. Browser Automation with Playwright

For JavaScript-heavy sites that require rendering:

```python
async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
    page = await self.get_page()  # Provided by BaseScraper
    
    try:
        await page.goto(f"{self.base_url}/whats-on", wait_until="networkidle")
        await page.wait_for_selector(".film-card", timeout=10000)
        
        cards = await page.query_selector_all(".film-card")
        
        showings = []
        for card in cards:
            title_el = await card.query_selector(".title")
            title = await title_el.inner_text()
            # ... parse other fields
            showings.append(RawShowing(...))
        
        return showings
        
    finally:
        await page.close()
```

## Step-by-Step: Creating a New Scraper

### 1. Research the Website

Before writing code:

1. **Understand the site structure**: How are listings organised?
2. **Check for APIs**: Look in Network tab for JSON endpoints
3. **Identify selectors**: What CSS classes/IDs identify film cards, times, etc.?
4. **Note edge cases**: Multiple venues? Special events? Different date formats?

### 2. Create the Scraper File

```bash
touch backend/src/cinescout/scrapers/mycinema.py
```

### 3. Implement the Scraper

```python
"""
Scraper for My Cinema.

Website: https://mycinema.com
Notes: Uses internal API at /api/programme
"""

import re
from datetime import date, datetime
from typing import Any

import httpx

from cinescout.scrapers.base import BaseScraper, RawShowing


class MyCinemaScraper(BaseScraper):
    cinema_id = "my-cinema"
    base_url = "https://mycinema.com"
    
    async def get_showings(
        self, 
        date_from: date, 
        date_to: date
    ) -> list[RawShowing]:
        """Fetch showings from My Cinema."""
        
        showings: list[RawShowing] = []
        
        async with httpx.AsyncClient() as client:
            # Fetch each day separately (some APIs require this)
            current = date_from
            while current <= date_to:
                day_showings = await self._fetch_day(client, current)
                showings.extend(day_showings)
                current = date(current.year, current.month, current.day + 1)
        
        return showings
    
    async def _fetch_day(
        self, 
        client: httpx.AsyncClient, 
        day: date
    ) -> list[RawShowing]:
        """Fetch showings for a single day."""
        
        try:
            response = await client.get(
                f"{self.base_url}/api/programme",
                params={"date": day.isoformat()},
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (compatible)",
                },
                timeout=30.0
            )
            
            if response.status_code != 200:
                # Log error, return empty
                return []
            
            data = response.json()
            return self._parse_response(data, day)
            
        except httpx.HTTPError as e:
            # Log error, return empty
            return []
    
    def _parse_response(
        self, 
        data: dict[str, Any], 
        day: date
    ) -> list[RawShowing]:
        """Parse API response into RawShowing objects."""
        
        showings = []
        
        for film in data.get("films", []):
            film_title = self.normalise_title(film.get("title", ""))
            
            for session in film.get("sessions", []):
                try:
                    # Parse time (format: "14:30")
                    time_str = session.get("time", "")
                    hour, minute = map(int, time_str.split(":"))
                    start_time = datetime(day.year, day.month, day.day, hour, minute)
                    
                    showing = RawShowing(
                        film_title=film_title,
                        start_time=start_time,
                        cinema_id=self.cinema_id,
                        screen=session.get("screen"),
                        format=session.get("format"),
                        booking_url=session.get("booking_link"),
                        price_amount=self._parse_price(session.get("price")),
                        raw_data={"film": film, "session": session},
                    )
                    showings.append(showing)
                    
                except (ValueError, KeyError, TypeError):
                    # Skip malformed entries
                    continue
        
        return showings
    
    def _parse_price(self, price_str: str | None) -> float | None:
        """Extract numeric price from string."""
        if not price_str:
            return None
        
        match = re.search(r'[\d.]+', str(price_str))
        return float(match.group()) if match else None
```

### 4. Register the Scraper

Add to `backend/src/cinescout/scrapers/__init__.py`:

```python
from cinescout.scrapers.mycinema import MyCinemaScraper

SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {
    # ... existing scrapers
    "mycinema": MyCinemaScraper,
}
```

### 5. Add Cinema to Database

Create a migration or seed script:

```python
cinema = Cinema(
    id="my-cinema",
    name="My Cinema",
    slug="my-cinema",
    address="123 Film Street, London",
    city="london",
    website="https://mycinema.com",
    booking_url="https://mycinema.com/book",
    scraper_type="mycinema",
    is_active=True,
    supports_online_booking=True,
)
```

### 6. Write Tests

```python
# tests/scrapers/test_mycinema_scraper.py

import pytest
from datetime import date
from cinescout.scrapers.mycinema import MyCinemaScraper


class TestMyCinemaScraperParsing:
    
    def test_parse_response_basic(self):
        scraper = MyCinemaScraper()
        data = {
            "films": [
                {
                    "title": "Test Film",
                    "sessions": [
                        {"time": "14:30", "screen": "Screen 1"}
                    ]
                }
            ]
        }
        
        showings = scraper._parse_response(data, date(2024, 1, 25))
        
        assert len(showings) == 1
        assert showings[0].film_title == "Test Film"
    
    def test_parse_price(self):
        scraper = MyCinemaScraper()
        
        assert scraper._parse_price("£12.50") == 12.50
        assert scraper._parse_price("12") == 12.0
        assert scraper._parse_price(None) is None
```

## Best Practices

### Error Handling

Always handle errors gracefully. A failing scraper shouldn't crash the entire system.

```python
try:
    response = await client.get(url, timeout=30.0)
    response.raise_for_status()
except httpx.TimeoutException:
    logger.warning(f"Timeout fetching {url}")
    return []
except httpx.HTTPStatusError as e:
    logger.warning(f"HTTP {e.response.status_code} from {url}")
    return []
```

### Respect Rate Limits

Add delays between requests if scraping multiple pages:

```python
import asyncio

for day in date_range:
    showings = await self._fetch_day(client, day)
    await asyncio.sleep(0.5)  # 500ms delay
```

### Preserve Raw Data

Always store the original response for debugging:

```python
RawShowing(
    # ... parsed fields
    raw_data={"original": response_data}
)
```

### Title Normalisation

Use the built-in normalisation for consistent matching:

```python
film_title = self.normalise_title(raw_title)
```

This removes common prefixes/suffixes like "Preview:", "(1972)", "35mm", etc.

### Handle Multiple Venues

For cinema chains with multiple locations:

```python
VENUES = {
    "my-cinema-soho": "soho",
    "my-cinema-hackney": "hackney",
}

async def get_showings(self, date_from, date_to):
    all_showings = []
    
    for cinema_id, venue_code in self.VENUES.items():
        venue_showings = await self._fetch_venue(venue_code, date_from, date_to)
        
        # Override cinema_id for each venue
        for showing in venue_showings:
            showing.cinema_id = cinema_id
        
        all_showings.extend(venue_showings)
    
    return all_showings
```

## Common Patterns

### Date Iteration

```python
from datetime import date, timedelta

current = date_from
while current <= date_to:
    # Process current date
    current += timedelta(days=1)
```

### Time Parsing

```python
# "14:30" format
time_str = "14:30"
hour, minute = map(int, time_str.split(":"))
start_time = datetime(day.year, day.month, day.day, hour, minute)

# ISO format
start_time = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))

# Human readable
from dateutil import parser
start_time = parser.parse("Fri 25 Jan 2024, 6:30pm")
```

### Price Extraction

```python
import re

def extract_price(text: str) -> float | None:
    if not text:
        return None
    
    # Handle various formats: "£12.50", "12.50", "£12", "GBP 12.50"
    match = re.search(r'(\d+(?:\.\d{2})?)', text)
    return float(match.group(1)) if match else None
```

### Format Detection

```python
def extract_format(tags: list[str]) -> str | None:
    formats = {"35mm", "70mm", "IMAX", "4K", "3D", "Dolby Atmos"}
    
    for tag in tags:
        if tag.upper() in {f.upper() for f in formats}:
            return tag
    
    return None
```

## Debugging Tips

### 1. Test in Isolation

```python
# Quick test script
import asyncio
from datetime import date
from cinescout.scrapers.mycinema import MyCinemaScraper

async def main():
    async with MyCinemaScraper() as scraper:
        showings = await scraper.get_showings(
            date_from=date.today(),
            date_to=date.today()
        )
        
        for s in showings[:5]:
            print(f"{s.film_title} - {s.start_time}")

asyncio.run(main())
```

### 2. Save Raw Responses

During development, save responses for fixture creation:

```python
import json

response = await client.get(url)
with open(f"fixtures/{self.cinema_id}_response.json", "w") as f:
    json.dump(response.json(), f, indent=2)
```

### 3. Use Browser DevTools

For Playwright scrapers, run with headed mode:

```python
self._browser = await playwright.chromium.launch(headless=False)
```

### 4. Check for Anti-Bot Measures

If requests fail, the site may have protection. Try:
- Adding realistic User-Agent headers
- Adding delays between requests
- Using Playwright instead of direct HTTP requests

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Empty results | Check selectors in browser DevTools |
| Timeout errors | Increase timeout, add `wait_until="networkidle"` |
| 403 Forbidden | Add User-Agent header, check for rate limiting |
| Date parsing fails | Log raw date strings, check locale settings |
| Duplicate showings | Check unique constraint in database |

## Cinema-Specific Notes

### BFI Southbank
- Has internal API at `/api/whats-on`
- Complex programme with seasons and retrospectives
- Multiple screens (NFT1, NFT2, NFT3, Studio)

### Curzon
- Multiple venues share same website
- Modern React frontend with API
- Venue IDs in URL parameters

### Prince Charles Cinema
- Quirky site, may need Playwright
- Repertory programming (older films)
- Special events (singalongs, marathons)

### Picturehouse
- Chain with consistent format across venues
- API available for listings

### Barbican
- Part of larger arts complex
- Cinema listings mixed with other events
- Filter by event type

### The Garden Cinema
- Smaller independent
- Curated programme
- May need Playwright for JS rendering
