"""Scraper registry for mapping scraper types to scraper classes."""

from typing import Type

from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.bfi import BFIScraper
from cinescout.scrapers.garden import GardenScraper
from cinescout.scrapers.picturehouse import PicturehouseScraper
from cinescout.scrapers.prince_charles import PrinceCharlesScraper

# Registry mapping scraper type names to scraper classes
SCRAPER_REGISTRY: dict[str, Type[BaseScraper]] = {
    "bfi": BFIScraper,
    "garden": GardenScraper,
    "picturehouse": PicturehouseScraper,
    "prince-charles": PrinceCharlesScraper,
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
        # Pass config to scrapers that need it (like Picturehouse)
        if scraper_config and scraper_type == "picturehouse":
            cinema_slug = scraper_config.get("cinema_slug", "picturehouse-central")
            return scraper_class(cinema_slug=cinema_slug)
        return scraper_class()
    return None


__all__ = [
    "SCRAPER_REGISTRY",
    "get_scraper",
    "BaseScraper",
    "BFIScraper",
    "GardenScraper",
    "PicturehouseScraper",
    "PrinceCharlesScraper",
]
