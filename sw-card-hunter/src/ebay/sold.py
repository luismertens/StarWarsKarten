"""eBay Finding API — Sold Listings abrufen und in price_history speichern."""

import logging
from datetime import datetime, timezone

from ebay.client import EbayFindingClient
from ebay.matcher import extract_psa_grade

logger = logging.getLogger(__name__)


def fetch_and_store_sold(
    keywords: str,
    card_id: int,
    client: EbayFindingClient,
    conn,
    min_grade: int = 8,
) -> list[dict]:
    """Verkaufte eBay-Listings abrufen und in price_history speichern.

    Gibt [{price, date}]-Liste zurück, die calculate_market_price() als Input dient.
    """
    raw = client.find_sold(keywords)
    now = datetime.now(timezone.utc).isoformat()
    results = []

    for item in raw:
        grade = extract_psa_grade(item["title"])
        if grade is None or grade < min_grade:
            continue

        sale_date = item.get("end_time", now)[:10] if item.get("end_time") else now[:10]

        try:
            conn.execute(
                """INSERT OR IGNORE INTO price_history
                   (card_id, price_usd, sale_date, source, recorded_at)
                   VALUES (?, ?, ?, 'ebay', ?)""",
                (card_id, item["price"], sale_date, now),
            )
        except Exception as e:
            logger.debug(f"price_history Insert übersprungen: {e}")

        results.append({"price": item["price"], "date": sale_date})

    logger.debug(f"  Sold '{keywords}': {len(raw)} Treffer, {len(results)} PSA {min_grade}+ gespeichert")
    return results
