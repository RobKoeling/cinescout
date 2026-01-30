"""Scraper registry for mapping scraper types to scraper classes."""

from typing import Type

from cinescout.scrapers.base import BaseScraper
from cinescout.scrapers.bfi import BFIScraper

# Registry mapping scraper type names to scraper classes
SCRAPER_REGISTRY: dict[str, Type[BaseScraper]] = {
    "bfi": BFIScraper,
}


def get_scraper(scraper_type: str) -> BaseScraper | None:
    """
    Get a scraper instance by type.

    Args:
        scraper_type: The scraper type (e.g., "bfi", "curzon")

    Returns:
        Scraper instance or None if type not found
    """
    scraper_class = SCRAPER_REGISTRY.get(scraper_type)
    if scraper_class:
        return scraper_class()
    return None


__all__ = ["SCRAPER_REGISTRY", "get_scraper", "BaseScraper", "BFIScraper"]
