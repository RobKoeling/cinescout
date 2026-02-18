"""Genesis Cinema (Mile End) scraper.

Genesis uses Craft CMS with server-side rendered HTML and Admit One for ticketing.
All showings across all upcoming dates are embedded in a single page load:

  GET https://genesiscinema.co.uk/whats-on

The page contains date-keyed panels (id="panel_YYYYMMDD"), each holding one
block per film. Each block contains one or more booking buttons linking to
genesis.admit-one.co.uk with a unique perfCode.

Each showtime appears twice in the HTML (desktop + mobile layouts). Only
elements with style="display:inherit;" are visible; hidden duplicates carry
style="display:none;".

Booking URL:  https://genesis.admit-one.co.uk/seats/?perfCode={code}
"""

import logging
import re
from datetime import date, datetime, time

import httpx
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.models import RawShowing

logger = logging.getLogger(__name__)

LONDON_TZ = ZoneInfo("Europe/London")
WHATS_ON_URL = "https://genesiscinema.co.uk/whats-on"


class GenesisScraper(BaseScraper):
    """Scraper for Genesis Cinema, Mile End."""

    async def get_showings(self, date_from: date, date_to: date) -> list[RawShowing]:
        """Fetch showings from the Genesis Cinema whats-on page."""
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                verify=False,
                headers={"User-Agent": "Mozilla/5.0"},
                follow_redirects=True,
            ) as client:
                resp = await client.get(WHATS_ON_URL)
                resp.raise_for_status()
                showings = self._parse(resp.text, date_from, date_to)
        except Exception as e:
            logger.error(f"Genesis scraper error: {e}", exc_info=True)
            return []

        logger.info(f"Genesis: found {len(showings)} showings")
        return showings

    def _parse(self, html: str, date_from: date, date_to: date) -> list[RawShowing]:
        soup = BeautifulSoup(html, "html.parser")
        showings: list[RawShowing] = []
        seen_perf_codes: set[str] = set()

        for panel in soup.find_all("div", id=re.compile(r"^panel_\d{8}$")):
            panel_id: str = panel["id"]  # "panel_20260219"
            date_str = panel_id[len("panel_"):]
            try:
                panel_date = date(
                    int(date_str[:4]), int(date_str[4:6]), int(date_str[6:])
                )
            except ValueError:
                continue

            if not (date_from <= panel_date <= date_to):
                continue

            # Each film is wrapped in a div with "grid-container-border" class
            for film_div in panel.find_all(
                "div", class_=lambda c: c and "grid-container-border" in c
            ):
                h2 = film_div.find("h2")
                if not h2:
                    continue
                raw_title = h2.get_text(strip=True)
                title = self.normalise_title(raw_title)
                if not title or len(title) < 2:
                    continue

                for btn in film_div.find_all("a", class_=lambda c: c and "perfButton" in c):
                    # Skip hidden duplicates (mobile layout)
                    style = btn.get("style", "").replace(" ", "")
                    if "display:none" in style:
                        continue

                    href: str = btn.get("href", "")
                    perf_match = re.search(r"perfCode=(\d+)", href)
                    if not perf_match:
                        continue
                    perf_code = perf_match.group(1)

                    # Deduplicate across panels (some films span multiple date panels
                    # and the same perf code can appear more than once)
                    if perf_code in seen_perf_codes:
                        continue
                    seen_perf_codes.add(perf_code)

                    # The time is in the last span (buttons have 1-2 spans;
                    # when two are present the first is a category label, the
                    # second with class "rounded-xl" contains the HH:MM time)
                    spans = btn.find_all("span")
                    if not spans:
                        continue
                    time_text = spans[-1].get_text(strip=True)  # "18:00"
                    try:
                        h, m = int(time_text[:2]), int(time_text[3:5])
                        start_time = datetime.combine(
                            panel_date, time(h, m), tzinfo=LONDON_TZ
                        )
                    except (ValueError, IndexError):
                        continue

                    showings.append(
                        RawShowing(
                            title=title,
                            start_time=start_time,
                            booking_url=href,
                            screen_name=None,
                            format_tags=None,
                            price=None,
                        )
                    )

        return showings
