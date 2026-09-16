"""Pacote scraper."""

from src.scraper.client import (
    EbayScraper,
    EbayScraperError,
    EbayScraperHTTPError,
    EbayScraperTimeoutError,
)
from src.scraper.parser import parse_ebay_item

__all__ = [
    "EbayScraper",
    "EbayScraperError",
    "EbayScraperHTTPError",
    "EbayScraperTimeoutError",
    "parse_ebay_item",
]
