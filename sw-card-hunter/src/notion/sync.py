"""Notion Sync — Karten und Deals in Notion Datenbanken schreiben."""

import logging
import os
import time
from datetime import datetime, timezone

from notion_client import Client
from notion_client.errors import APIResponseError, HTTPResponseError

from db import get_connection, get_meta, set_meta

logger = logging.getLogger(__name__)

# Rate Limiting: sicher unter 3 req/s bleiben
_REQUEST_DELAY = 0.4

TYPE_MAP = {
    "autograph": "Autogramm",
    "vintage": "Vintage",
    "numbered": "Nummeriert",
    "base": "Basis",
}


def _client() -> Client:
    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise ValueError("NOTION_TOKEN nicht gesetzt")
    return Client(auth=token)


def _clean_db_id(raw: str) -> str:
    """Notion DB-ID bereinigen — entfernt Dashes, Query-Params und URL-Pfade."""
    # Falls volle URL eingefügt wurde: nur den ID-Teil extrahieren
    raw = raw.split("?")[0].split("/")[-1].replace("-", "")
    return raw


def _cards_db_id() -> str:
    db_id = os.getenv("NOTION_CARDS_DB_ID")
    if not db_id:
        raise ValueError("NOTION_CARDS_DB_ID nicht gesetzt")
    return _clean_db_id(db_id)


def _deals_db_id() -> str:
    db_id = os.getenv("NOTION_DEALS_DB_ID")
    if not db_id:
        raise ValueError("NOTION_DEALS_DB_ID nicht gesetzt")
    return _clean_db_id(db_id)


def setup_notion_databases() -> None:
    """Fehlende Properties in den Notion-Datenbanken anlegen."""
    notion = _client()

    logger.info("Prüfe Notion Cards-Datenbank Properties...")
    _ensure_cards_properties(notion, _cards_db_id())

    logger.info("Prüfe Notion Deals-Datenbank Properties...")
    _ensure_deals_properties(notion, _deals_db_id())

    logger.info("Notion Datenbanken Setup abgeschlossen")


def _ensure_cards_properties(notion: Client, db_id: str) -> None:
    """Alle benötigten Properties in der Cards-DB anlegen."""
    db = notion.databases.retrieve(database_id=db_id)
    existing = set(db["properties"].keys())

    new_props = {}

    if "Charakter" not in existing:
        new_props["Charakter"] = {"select": {}}
    if "Set" not in existing:
        new_props["Set"] = {"rich_text": {}}
    if "Typ" not in existing:
        new_props["Typ"] = {"select": {}}
    if "Auflage" not in existing:
        new_props["Auflage"] = {"number": {"format": "number"}}
    if "Avg Price USD" not in existing:
        new_props["Avg Price USD"] = {"number": {"format": "dollar"}}
    if "Last Sold USD" not in existing:
        new_props["Last Sold USD"] = {"number": {"format": "dollar"}}
    if "Liquidität" not in existing:
        new_props["Liquidität"] = {"select": {}}
    if "PriceCharting Link" not in existing:
        new_props["PriceCharting Link"] = {"url": {}}
    if "Zuletzt gecheckt" not in existing:
        new_props["Zuletzt gecheckt"] = {"date": {}}

    if new_props:
        notion.databases.update(database_id=db_id, properties=new_props)
        logger.info(f"Cards DB: {len(new_props)} Properties angelegt: {list(new_props.keys())}")
    else:
        logger.info("Cards DB: alle Properties bereits vorhanden")


def _ensure_deals_properties(notion: Client, db_id: str) -> None:
    """Alle benötigten Properties in der Deals-DB anlegen."""
    db = notion.databases.retrieve(database_id=db_id)
    existing = set(db["properties"].keys())

    new_props = {}

    if "Angebotspreis" not in existing:
        new_props["Angebotspreis"] = {"number": {"format": "dollar"}}
    if "Marktpreis" not in existing:
        new_props["Marktpreis"] = {"number": {"format": "dollar"}}
    if "Ersparnis %" not in existing:
        new_props["Ersparnis %"] = {"number": {"format": "percent"}}
    if "eBay Listing URL" not in existing:
        new_props["eBay Listing URL"] = {"url": {}}
    if "Status" not in existing:
        new_props["Status"] = {"select": {}}
    if "Gefunden am" not in existing:
        new_props["Gefunden am"] = {"date": {}}

    if new_props:
        notion.databases.update(database_id=db_id, properties=new_props)
        logger.info(f"Deals DB: {len(new_props)} Properties angelegt: {list(new_props.keys())}")
    else:
        logger.info("Deals DB: alle Properties bereits vorhanden")


def _build_card_properties(card: dict) -> dict:
    """Notion-Properties-Objekt für eine Karte bauen."""
    props = {
        "Name": {"title": [{"text": {"content": card["name"][:2000]}}]},
    }

    if card.get("character"):
        props["Charakter"] = {"select": {"name": card["character"][:100]}}

    if card.get("card_set"):
        props["Set"] = {"rich_text": [{"text": {"content": card["card_set"][:2000]}}]}

    if card.get("card_type"):
        props["Typ"] = {"select": {"name": TYPE_MAP.get(card["card_type"], card["card_type"])}}

    if card.get("numbered_to") is not None:
        props["Auflage"] = {"number": card["numbered_to"]}

    if card.get("avg_price_usd") is not None:
        props["Avg Price USD"] = {"number": card["avg_price_usd"]}

    if card.get("last_sold_usd") is not None:
        props["Last Sold USD"] = {"number": card["last_sold_usd"]}

    if card.get("liquidity"):
        props["Liquidität"] = {"select": {"name": card["liquidity"]}}

    if card.get("pricecharting_link"):
        props["PriceCharting Link"] = {"url": card["pricecharting_link"]}

    props["Zuletzt gecheckt"] = {"date": {"start": datetime.now(timezone.utc).strftime("%Y-%m-%d")}}

    return props


def sync_card(card: dict) -> str | None:
    """Einzelne Karte in Notion anlegen oder aktualisieren.

    Gibt die Notion Page ID zurück, oder None bei Fehler.
    """
    notion = _client()
    props = _build_card_properties(card)

    try:
        if card.get("notion_page_id"):
            # Seite aktualisieren
            notion.pages.update(page_id=card["notion_page_id"], properties=props)
            return card["notion_page_id"]
        else:
            # Neue Seite erstellen
            page = notion.pages.create(
                parent={"database_id": _cards_db_id()},
                properties=props,
            )
            return page["id"]
    except APIResponseError as e:
        logger.error(f"Notion API Fehler für '{card['name']}': {e}")
        return None


def _upsert_card_page(
    notion: Client,
    cards_db: str,
    card_dict: dict,
    props: dict,
    now: str,
    max_retries: int = 3,
) -> str | None:
    """Karte in Notion anlegen oder updaten — mit Retry bei 429/502/503."""
    for attempt in range(max_retries):
        try:
            if card_dict.get("notion_page_id"):
                notion.pages.update(page_id=card_dict["notion_page_id"], properties=props)
                return card_dict["notion_page_id"]
            else:
                page = notion.pages.create(
                    parent={"database_id": cards_db},
                    properties=props,
                )
                page_id = page["id"]
                with get_connection() as conn:
                    conn.execute(
                        "UPDATE cards SET notion_page_id = ?, updated_at = ? WHERE id = ?",
                        (page_id, now, card_dict["id"]),
                    )
                return page_id

        except (APIResponseError, HTTPResponseError) as e:
            err_str = str(e).lower()
            is_transient = "rate" in err_str or "502" in err_str or "503" in err_str
            if is_transient and attempt < max_retries - 1:
                wait = 60 * (attempt + 1)  # 60s, 120s, ...
                logger.warning(f"Transient Fehler (Versuch {attempt+1}), warte {wait}s: {e}")
                time.sleep(wait)
                continue
            raise

    return None


def sync_all_cards(limit: int | None = None, force: bool = False) -> int:
    """Karten aus SQLite nach Notion synchronisieren.

    Standardmäßig werden nur neue Karten (kein notion_page_id) und
    geänderte Karten (updated_at nach letztem Sync) synchronisiert.
    Mit force=True werden alle Karten aktualisiert.

    Gibt Anzahl erfolgreich synchronisierter Karten zurück.
    """
    notion = _client()
    cards_db = _cards_db_id()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    last_sync = get_meta("last_notion_sync")

    with get_connection() as conn:
        if force:
            query = "SELECT * FROM cards ORDER BY id"
        elif limit:
            # Für Tests: nur neue Karten, auf Limit begrenzt
            query = f"SELECT * FROM cards WHERE notion_page_id IS NULL ORDER BY id LIMIT {limit}"
        elif last_sync:
            # Nur neue oder geänderte Karten seit letztem Sync
            query = f"SELECT * FROM cards WHERE notion_page_id IS NULL OR updated_at > '{last_sync}' ORDER BY id"
        else:
            # Kein vorheriger Sync: nur Karten die noch nicht in Notion sind
            query = "SELECT * FROM cards WHERE notion_page_id IS NULL ORDER BY id"

        cards = conn.execute(query).fetchall()

    total = len(cards)
    logger.info(f"Starte Notion Sync: {total} Karten")

    synced = 0
    errors = 0

    for i, card in enumerate(cards, 1):
        card_dict = dict(card)
        props = _build_card_properties(card_dict)

        try:
            page_id = _upsert_card_page(notion, cards_db, card_dict, props, now)
            if page_id:
                synced += 1
            else:
                errors += 1

        except (APIResponseError, HTTPResponseError) as e:
            logger.warning(f"Notion Fehler bei '{card_dict['name']}': {e}")
            errors += 1

        if i % 100 == 0:
            logger.info(f"  Fortschritt: {i}/{total} ({synced} OK, {errors} Fehler)")

        time.sleep(_REQUEST_DELAY)

    logger.info(f"Notion Sync abgeschlossen: {synced}/{total} Karten synchronisiert, {errors} Fehler")
    if not force:
        set_meta("last_notion_sync", datetime.now(timezone.utc).isoformat())
    return synced


def sync_deal(deal: dict) -> str | None:
    """Deal in die Notion Deals-Datenbank schreiben.

    Gibt die Notion Page ID zurück, oder None bei Fehler.
    """
    notion = _client()

    props = {
        "Name": {"title": [{"text": {"content": deal.get("card_name", "Unbekannte Karte")[:2000]}}]},
        "Angebotspreis": {"number": deal.get("listing_price")},
        "Marktpreis": {"number": deal.get("market_price")},
        "Status": {"select": {"name": "Neu"}},
        "Gefunden am": {"date": {"start": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")}},
    }

    if deal.get("savings_percent") is not None:
        props["Ersparnis %"] = {"number": deal["savings_percent"] / 100}

    if deal.get("ebay_url"):
        props["eBay Listing URL"] = {"url": deal["ebay_url"]}

    try:
        if deal.get("notion_page_id"):
            notion.pages.update(page_id=deal["notion_page_id"], properties=props)
            return deal["notion_page_id"]
        else:
            page = notion.pages.create(
                parent={"database_id": _deals_db_id()},
                properties=props,
            )
            return page["id"]
    except APIResponseError as e:
        logger.error(f"Notion Fehler beim Deal-Sync: {e}")
        return None
