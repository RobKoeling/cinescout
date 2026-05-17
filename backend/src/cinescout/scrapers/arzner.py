"""The Arzner cinema scraper (Savoy Systems)."""

from cinescout.scrapers.savoy import SavoySystemsScraper


class ArznerScraper(SavoySystemsScraper):
    """Scraper for The Arzner, London's LGBTQ+ cinema, Bermondsey."""

    BASE_URL = "https://thearzner.com"
    WHATS_ON_URL = f"{BASE_URL}/TheArzner.dll/WhatsOn"
    CINEMA_NAME = "The Arzner"
    PERF_FLAGS = {
        "AD": "Audio Described",
        "HOH": "Hard of Hearing",
        "RS": "Relaxed Screening",
        "QA": "Q&A",
    }
