"""The Lexi Cinema scraper (Savoy Systems)."""

from cinescout.scrapers.savoy import SavoySystemsScraper


class LexiScraper(SavoySystemsScraper):
    """Scraper for The Lexi Cinema, Kensal Rise."""

    BASE_URL = "https://thelexicinema.co.uk"
    WHATS_ON_URL = f"{BASE_URL}/TheLexiCinema.dll/WhatsOn"
    CINEMA_NAME = "The Lexi Cinema"
    PERF_FLAGS = {
        "BF": "Babes in Arms",
        "AD": "Audio Described",
        "HOH": "Hard of Hearing",
        "RS": "Relaxed Screening",
        "QA": "Q&A",
    }
