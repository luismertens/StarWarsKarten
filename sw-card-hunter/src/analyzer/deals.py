"""Deal-Erkennung — prüfen ob ein Angebot einen guten Deal darstellt.

Phase 4 Implementierung.
"""

import logging

logger = logging.getLogger(__name__)


def is_deal(listing_price: float, market_price: dict, config: dict) -> tuple[bool, float]:
    """Prüfen ob ein Listing ein Deal ist.

    Gibt (is_deal: bool, savings_percent: float) zurück.
    Wird in Phase 4 implementiert.
    """
    logger.info("Deal Analyzer — noch nicht implementiert (Phase 4)")
    return False, 0.0
