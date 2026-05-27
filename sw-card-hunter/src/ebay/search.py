"""eBay Finding API — aktuelle PSA-Listings abrufen."""

import logging

from ebay.client import EbayFindingClient
from ebay.matcher import extract_psa_grade

logger = logging.getLogger(__name__)


def search_active_listings(keywords: str, client: EbayFindingClient, min_grade: int = 8) -> list[dict]:
    """Aktuelle eBay-Listings für Keywords abrufen.

    Gibt nur Listings zurück die PSA min_grade oder höher enthalten.
    """
    listings = client.find_active(keywords)
    filtered = [
        item for item in listings
        if (grade := extract_psa_grade(item["title"])) is not None and grade >= min_grade
    ]
    logger.debug(f"  '{keywords}': {len(listings)} Treffer, {len(filtered)} mit PSA {min_grade}+")
    return filtered
