"""Deal-Erkennung — prüfen ob ein Angebot einen guten Deal darstellt."""

import logging

logger = logging.getLogger(__name__)


def is_deal(
    listing_price: float,
    market_price: dict,
    config: dict,
    card_type: str = "autograph",
) -> tuple[bool, float]:
    """Prüfen ob ein Listing ein Deal ist.

    Gibt (is_deal: bool, savings_percent: float) zurück.
    savings_percent ist positiv wenn unter Markt, negativ wenn über Markt.
    """
    if not market_price or not market_price.get("avg"):
        return False, 0.0

    avg = market_price["avg"]
    if avg <= 0:
        return False, 0.0

    # Preislimits prüfen
    limits = config.get("price_limits", {}).get(card_type, {})
    min_price = limits.get("min", 0)
    max_price = limits.get("max", float("inf"))

    if not (min_price <= listing_price <= max_price):
        logger.debug(f"Preis ${listing_price} außerhalb Limit [{min_price}–{max_price}] für {card_type}")
        return False, 0.0

    savings_pct = round((avg - listing_price) / avg * 100, 1)
    threshold = config.get("deal_threshold_percent", 15)

    return savings_pct >= threshold, savings_pct
