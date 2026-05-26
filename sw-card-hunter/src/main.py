"""SW Card Hunter — Hauptprogramm und Scheduler."""

import logging
import os
import sys
from pathlib import Path

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from db import init_db
from scraper.pricecharting import scrape_star_wars_cards

# .env laden (muss vor allen anderen Imports sein)
load_dotenv(Path(__file__).parent.parent / ".env")


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


def check_env_keys() -> bool:
    """Prüfen ob alle benötigten API Keys vorhanden sind."""
    required = [
        "EBAY_APP_ID",
        "EBAY_CERT_ID",
        "NOTION_TOKEN",
        "NOTION_CARDS_DB_ID",
        "NOTION_DEALS_DB_ID",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
    ]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        logging.warning(f"Fehlende API Keys: {', '.join(missing)}")
        return False
    return True


def run_cycle(config: dict) -> None:
    """Ein vollständiger Bot-Durchlauf (wird alle 30 Min ausgeführt)."""
    logger = logging.getLogger("main")
    logger.info("=== Bot-Zyklus gestartet ===")

    # Phase 2: PriceCharting scrapen (einmalig + als Auffrischung)
    scrape_star_wars_cards(config)

    # Phase 3: eBay API abfragen (folgt)
    # Phase 4: Deal-Erkennung + Telegram Alert (folgt)
    # Phase 5: Notion Sync (folgt)

    logger.info("=== Bot-Zyklus abgeschlossen ===")


def main() -> None:
    config = load_config()
    setup_logging(config)
    logger = logging.getLogger("main")

    logger.info("SW Card Hunter gestartet")
    logger.info(f"Überwachte Charaktere: {len(config.get('characters_whitelist', []))}")

    # Datenbank initialisieren
    init_db()

    # API Keys prüfen (warnt, bricht aber nicht ab)
    keys_ok = check_env_keys()
    if keys_ok:
        logger.info("Alle API Keys gefunden")
    else:
        logger.warning("Bot läuft ohne vollständige API Keys — einige Funktionen deaktiviert")

    # Scheduler einrichten
    interval = config.get("scheduler_interval_minutes", 30)
    scheduler = BlockingScheduler(timezone="Europe/Berlin")
    scheduler.add_job(run_cycle, "interval", minutes=interval, args=[config], id="main_cycle")

    logger.info(f"Scheduler läuft — Intervall: alle {interval} Minuten")
    logger.info("Erster Durchlauf startet jetzt...")

    # Sofortiger erster Durchlauf
    run_cycle(config)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot gestoppt")


if __name__ == "__main__":
    main()
