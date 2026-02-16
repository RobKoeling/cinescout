"""Scraper registry for mapping scraper types to scraper classes."""

from typing import Type

from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.bfi import BFIScraper
from cinescout.scrapers.curzon import CurzonScraper
from cinescout.scrapers.garden import GardenScraper
from cinescout.scrapers.picturehouse import PicturehouseScraper
from cinescout.scrapers.prince_charles import PrinceCharlesScraper
from cinescout.scrapers.regent_street import RegentStreetScraper
from cinescout.scrapers.rio import RioScraper

# Registry mapping scraper type names to scraper classes
SCRAPER_REGISTRY: dict[str, Type[BaseScraper]] = {
    "bfi": BFIScraper,
    "curzon": CurzonScraper,
    "garden": GardenScraper,
    "picturehouse": PicturehouseScraper,
    "prince-charles": PrinceCharlesScraper,
    "regent-street": RegentStreetScraper,
    "rio": RioScraper,
}


def get_scraper(scraper_type: str, scraper_config: dict | None = None) -> BaseScraper | None:
    """
    Get a scraper instance by type.

    Args:
        scraper_type: The scraper type (e.g., "bfi", "curzon")
        scraper_config: Optional configuration dict for the scraper

    Returns:
        Scraper instance or None if type not found
    """
    scraper_class = SCRAPER_REGISTRY.get(scraper_type)
    if scraper_class:
        if scraper_config and scraper_type == "picturehouse":
            cinema_slug = scraper_config.get("cinema_slug", "picturehouse-central")
            return scraper_class(cinema_slug=cinema_slug)
        if scraper_config and scraper_type == "curzon":
            venue_id = scraper_config.get("venue_id", "SOH1")
            return scraper_class(venue_id=venue_id)
        return scraper_class()
    return None


__all__ = [
    "SCRAPER_REGISTRY",
    "get_scraper",
    "BaseScraper",
    "BFIScraper",
    "CurzonScraper",
    "GardenScraper",
    "PicturehouseScraper",
    "PrinceCharlesScraper",
    "RegentStreetScraper",
    "RioScraper",
]
