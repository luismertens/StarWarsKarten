"""SW Card Hunter — Hauptprogramm und Scheduler."""

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from db import init_db, get_meta, set_meta
from scraper.pricecharting import scrape_star_wars_cards
from notifier.alerts import send_test_message

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


def run_cycle(config: dict, available_keys: dict) -> None:
    """Ein vollständiger Bot-Durchlauf (wird alle 30 Min ausgeführt)."""
    logger = logging.getLogger("main")
    logger.info("=== Bot-Zyklus gestartet ===")

    # PriceCharting: nur alle 24h neu scrapen
    if _should_scrape():
        scrape_star_wars_cards(config)
        set_meta("last_pricecharting_scrape", datetime.now(timezone.utc).isoformat())
    else:
        logger.info("PriceCharting: kein Scrape nötig (< 24h)")

    # eBay Integration (Phase 3 — folgt wenn Key verfügbar)
    if available_keys.get("ebay"):
        pass  # TODO: Phase 3

    # Deal-Erkennung + Telegram (Phase 4 — folgt)

    # Notion Sync (läuft separat einmalig beim Start)

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

    # Scheduler einrichten
    interval = config.get("scheduler_interval_minutes", 30)
    scheduler = BlockingScheduler(timezone="Europe/Berlin")
    scheduler.add_job(
        run_cycle, "interval",
        minutes=interval,
        args=[config, available_keys],
        id="main_cycle",
    )

    logger.info(f"Scheduler läuft — Intervall: alle {interval} Minuten")

    run_cycle(config, available_keys)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot gestoppt")


if __name__ == "__main__":
    main()
