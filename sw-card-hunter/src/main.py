"""SW Card Hunter — Hauptprogramm und Scheduler."""

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from db import init_db, get_connection, get_meta, set_meta
from scraper.pricecharting import scrape_star_wars_cards
from notifier.alerts import send_test_message, send_deal_alert

# .env laden (muss vor allen anderen Imports sein)
load_dotenv(Path(__file__).parent.parent / ".env")

# Wie viele Stunden zwischen PriceCharting-Scrapes
SCRAPER_INTERVAL_HOURS = 24


def setup_logging(config: dict) -> None:
    """Logging konfigurieren — Ausgabe in Datei und Konsole."""
    log_cfg = config.get("logging", {})
    level = getattr(logging, log_cfg.get("level", "INFO"))
    log_file = Path(__file__).parent.parent / log_cfg.get("file", "logs/bot.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_config() -> dict:
    """config.yaml laden und zurückgeben."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_env_keys() -> dict[str, bool]:
    """Prüfen welche API Keys vorhanden sind."""
    keys = {
        "ebay": all(os.getenv(k) for k in ["EBAY_APP_ID", "EBAY_CERT_ID"]),
        "notion": all(os.getenv(k) for k in ["NOTION_TOKEN", "NOTION_CARDS_DB_ID", "NOTION_DEALS_DB_ID"]),
        "telegram": all(os.getenv(k) for k in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]),
    }
    for service, ok in keys.items():
        status = "✅" if ok else "❌"
        logging.getLogger("main").info(f"  {status} {service.capitalize()} API")
    return keys


def _should_scrape() -> bool:
    """Prüfen ob PriceCharting neu gescraped werden soll (alle 24h)."""
    from db import get_connection
    card_count = get_connection().execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    if card_count == 0:
        return True
    last = get_meta("last_pricecharting_scrape")
    if not last:
        return True
    last_dt = datetime.fromisoformat(last)
    hours_since = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
    return hours_since >= SCRAPER_INTERVAL_HOURS


def _handle_deal(listing: dict, card: dict, savings_pct: float, config: dict) -> None:
    """Deal speichern, Telegram-Alert senden und nach Notion schreiben."""
    logger = logging.getLogger("main")

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM deals WHERE ebay_item_id = ?", (listing["item_id"],)
        ).fetchone()
        if existing:
            return  # Bereits bekannt

        from ebay.matcher import extract_psa_grade, get_market_price
        market_price = get_market_price(card, extract_psa_grade(listing["title"]))

        conn.execute(
            """INSERT INTO deals
               (card_id, listing_price, market_price, savings_percent,
                ebay_listing_url, ebay_item_id, status)
               VALUES (?, ?, ?, ?, ?, ?, 'Neu')""",
            (
                card["id"],
                listing["price"],
                market_price,
                savings_pct,
                listing["url"],
                listing["item_id"],
            ),
        )

    from ebay.matcher import extract_psa_grade, get_market_price
    market_price = get_market_price(card, extract_psa_grade(listing["title"]))

    deal_dict = {
        "card_name": card["name"],
        "character": card.get("character"),
        "card_type": card["card_type"],
        "card_set": card.get("card_set", ""),
        "listing_price": listing["price"],
        "market_price": market_price,
        "savings_percent": savings_pct,
        "ebay_url": listing["url"],
        "pricecharting_url": card.get("pricecharting_link"),
        "numbered_to": card.get("numbered_to"),
    }

    send_deal_alert(deal_dict)

    try:
        from notion.sync import sync_deal
        sync_deal(deal_dict)
    except Exception as e:
        logger.warning(f"Notion Deal-Sync fehlgeschlagen: {e}")

    logger.info(
        f"DEAL: {card['name']} — ${listing['price']:.2f} "
        f"({savings_pct:.1f}% unter Markt ${market_price:.2f})"
    )


def run_ebay_cycle(config: dict, client, cycle_num: int) -> None:
    """eBay-Scan: aktive Listings prüfen und Deals erkennen."""
    logger = logging.getLogger("main")
    from ebay.search import search_active_listings
    from ebay.matcher import build_keywords, find_matching_card, get_market_price, extract_psa_grade, VINTAGE_YEARS
    from analyzer.deals import is_deal

    min_grade = config.get("grading", {}).get("min_grade", 8)
    characters = config.get("characters_whitelist", [])

    # Alle Karten einmal laden (kein Query pro Listing)
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM cards").fetchall()
    all_cards = [dict(r) for r in rows]

    deals_found = 0

    # --- Charakter-Karten (Autogramm + Nummeriert) ---
    for character in characters:
        for card_type in ("autograph", "numbered"):
            if not config.get("card_types", {}).get(
                "autographs" if card_type == "autograph" else "numbered", True
            ):
                continue

            keywords = build_keywords(character, card_type)
            listings = search_active_listings(keywords, client, min_grade=min_grade)

            for listing in listings:
                card = find_matching_card(listing, all_cards, character, card_type)
                if not card:
                    continue

                grade = extract_psa_grade(listing["title"])
                market_price = get_market_price(card, grade)
                if not market_price:
                    continue

                deal_found, savings_pct = is_deal(listing["price"], {"avg": market_price}, config, card_type)
                if deal_found:
                    _handle_deal(listing, card, savings_pct, config)
                    deals_found += 1

    # --- Vintage (kein Charakter-Filter) ---
    if config.get("card_types", {}).get("vintage", True):
        vintage_cards = [c for c in all_cards if c["card_type"] == "vintage"]
        for year in VINTAGE_YEARS:
            keywords = build_keywords(None, "vintage", year=year)
            listings = search_active_listings(keywords, client, min_grade=min_grade)

            for listing in listings:
                card = find_matching_card(listing, vintage_cards, None, "vintage")
                if not card:
                    continue

                grade = extract_psa_grade(listing["title"])
                market_price = get_market_price(card, grade)
                if not market_price:
                    continue

                deal_found, savings_pct = is_deal(listing["price"], {"avg": market_price}, config, "vintage")
                if deal_found:
                    _handle_deal(listing, card, savings_pct, config)
                    deals_found += 1

    logger.info(
        f"eBay-Scan abgeschlossen: {client.calls_today()} Calls heute, {deals_found} Deals gefunden"
    )


def run_cycle(config: dict, available_keys: dict, cycle_num: int = 0) -> None:
    """Ein vollständiger Bot-Durchlauf (wird alle 30 Min ausgeführt)."""
    logger = logging.getLogger("main")
    logger.info("=== Bot-Zyklus gestartet ===")

    # PriceCharting: nur alle 24h neu scrapen
    if _should_scrape():
        scrape_star_wars_cards(config)
        set_meta("last_pricecharting_scrape", datetime.now(timezone.utc).isoformat())
    else:
        logger.info("PriceCharting: kein Scrape nötig (< 24h)")

    # eBay Scan
    if available_keys.get("ebay"):
        try:
            from ebay.client import EbayFindingClient
            client = EbayFindingClient()
            run_ebay_cycle(config, client, cycle_num)
        except Exception as e:
            logger.error(f"eBay-Zyklus Fehler: {e}", exc_info=True)

    logger.info("=== Bot-Zyklus abgeschlossen ===")


def main() -> None:
    config = load_config()
    setup_logging(config)
    logger = logging.getLogger("main")

    logger.info("SW Card Hunter gestartet")
    logger.info(f"Überwachte Charaktere: {len(config.get('characters_whitelist', []))}")

    init_db()

    logger.info("API Keys Status:")
    available_keys = check_env_keys()

    # Telegram Test beim ersten Start
    if available_keys.get("telegram"):
        send_test_message()

    cycle_counter = {"n": 0}

    def _cycle():
        run_cycle(config, available_keys, cycle_counter["n"])
        cycle_counter["n"] += 1

    # Scheduler einrichten
    interval = config.get("scheduler_interval_minutes", 30)
    scheduler = BlockingScheduler(timezone="Europe/Berlin")
    scheduler.add_job(_cycle, "interval", minutes=interval, id="main_cycle")

    logger.info(f"Scheduler läuft — Intervall: alle {interval} Minuten")

    _cycle()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot gestoppt")


if __name__ == "__main__":
    main()
