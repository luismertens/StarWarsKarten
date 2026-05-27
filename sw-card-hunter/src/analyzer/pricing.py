"""Preisanalyse — Durchschnitt, Median und Liquidität aus Sold Listings berechnen."""

import logging
import statistics
from datetime import datetime

logger = logging.getLogger(__name__)


def _liquidity_label(sales_per_month: float) -> str:
    """Liquiditäts-Label aus Verkäufen pro Monat berechnen."""
    if sales_per_month >= 5:
        return "Hoch"
    elif sales_per_month >= 2:
        return "Mittel"
    return "Niedrig"


def _filter_outliers(prices: list[float]) -> list[float]:
    """Preise außerhalb ±2 Standardabweichungen entfernen."""
    if len(prices) < 4:
        return prices
    avg = statistics.mean(prices)
    stdev = statistics.stdev(prices)
    return [p for p in prices if abs(p - avg) <= 2 * stdev]


def calculate_market_price(sold_listings: list[dict], config: dict) -> dict:
    """Marktpreise aus Sold Listings berechnen.

    Jedes Listing muss mindestens 'price' (float) enthalten.
    Optional: 'date' (ISO-String) für Liquiditätsberechnung.

    Gibt leeres dict zurück wenn zu wenig Daten vorhanden.
    """
    min_sales = config.get("min_sales_for_avg", 3)

    if len(sold_listings) < min_sales:
        logger.debug(f"Zu wenig Verkäufe ({len(sold_listings)} < {min_sales}) für Marktpreis")
        return {}

    prices = [float(s["price"]) for s in sold_listings if s.get("price")]
    if not prices:
        return {}

    prices = _filter_outliers(prices)
    if len(prices) < min_sales:
        return {}

    # Zeitraum für Liquiditätsberechnung
    lookback_days = config.get("market_lookback_days", 90)
    sales_per_month = len(prices) / (lookback_days / 30)

    # Letzter Verkauf (neuestes Datum oder letzter in der Liste)
    sorted_by_date = sorted(
        [s for s in sold_listings if s.get("date")],
        key=lambda s: s["date"],
        reverse=True,
    )
    last_sold = float(sorted_by_date[0]["price"]) if sorted_by_date else prices[-1]

    return {
        "avg": round(statistics.mean(prices), 2),
        "median": round(statistics.median(prices), 2),
        "last_sold": round(last_sold, 2),
        "sales_count": len(prices),
        "liquidity": _liquidity_label(sales_per_month),
    }
