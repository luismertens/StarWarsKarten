"""PriceCharting Scraper — Star Wars Karten-Datenbank aufbauen."""

import logging
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from db import get_connection

logger = logging.getLogger(__name__)

BASE_URL = "https://www.pricecharting.com"
CATEGORY_URL = f"{BASE_URL}/de/category/star-wars-cards"

# Verzögerung zwischen Requests um PriceCharting nicht zu überlasten
REQUEST_DELAY_SECONDS = 1.5

# Vintage-Zeitraum laut Konfiguration
VINTAGE_YEARS = {1977, 1978, 1979, 1980, 1981, 1982, 1983}


def _make_session() -> requests.Session:
    """HTTP-Session mit browser-ähnlichem User-Agent erstellen."""
    session = requests.Session()
    try:
        ua = UserAgent()
        user_agent = ua.chrome
    except Exception:
        user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    session.headers.update({
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    })
    return session


def _fetch_page(session: requests.Session, url: str) -> BeautifulSoup | None:
    """URL abrufen und als BeautifulSoup zurückgeben. None bei Fehler."""
    try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")
    except requests.RequestException as e:
        logger.warning(f"Fehler beim Abrufen von {url}: {e}")
        return None


def _parse_price(price_str: str) -> float | None:
    """Preisstring wie '$1,234.56' in float umwandeln."""
    if not price_str:
        return None
    cleaned = price_str.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _detect_set_type(url_slug: str, set_name: str) -> str:
    """Kartentyp eines Sets anhand URL und Name bestimmen.

    Gibt 'skip' zurück für Sets die komplett ignoriert werden sollen.
    """
    slug_lower = url_slug.lower()
    name_lower = set_name.lower()

    # Unerwünschte Sets komplett überspringen
    skip_patterns = ["sticker", " tcg", "-tcg", " ccg", "-ccg", "unlimited", "young-jedi", "young jedi", "kakawow"]
    if any(p in slug_lower or p in name_lower for p in skip_patterns):
        return "skip"

    if "autograph" in slug_lower or "autograph" in name_lower:
        return "autograph"

    # Vintage-Erkennung: Jahr 1977-1983 im URL-Slug
    for year in VINTAGE_YEARS:
        if str(year) in slug_lower:
            return "vintage"

    # Bekannte Vintage-Bezeichnungen
    vintage_patterns = ["empire-strikes-back", "return-of-the-jedi", "wonder-bread"]
    if any(p in slug_lower for p in vintage_patterns):
        return "vintage"

    return "base"


def _detect_year(url_slug: str, set_name: str) -> int | None:
    """Erscheinungsjahr aus URL oder Set-Name extrahieren."""
    for text in [url_slug, set_name]:
        match = re.search(r"(19|20)\d{2}", text)
        if match:
            return int(match.group())
    return None


def _find_character(card_name: str, whitelist: list[str]) -> str | None:
    """Ersten passenden Charakter aus der Whitelist im Kartennamen finden.

    Nutzt Wortgrenzen damit 'Rey' nicht in 'Carey' matcht.
    """
    for character in whitelist:
        # Wortgrenze-Suche: \b damit 'Rey' nicht in 'Carey Jones' matcht
        pattern = r"\b" + re.escape(character) + r"\b"
        if re.search(pattern, card_name, re.IGNORECASE):
            return character
    return None


def _get_all_set_urls(session: requests.Session) -> list[dict]:
    """Alle Star Wars Karten-Sets von der Kategorie-Seite abrufen."""
    logger.info(f"Lade Kategorie-Seite: {CATEGORY_URL}")
    soup = _fetch_page(session, CATEGORY_URL)
    if not soup:
        logger.error("Kategorie-Seite konnte nicht geladen werden")
        return []

    sets = []
    seen_urls = set()
    links = soup.find_all("a", href=True)

    for link in links:
        href = link.get("href", "")
        if "/console/" not in href or "star-wars" not in href.lower():
            continue

        full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
        slug = href.split("/console/")[-1].rstrip("/")

        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        set_name = link.get_text(strip=True)
        set_type = _detect_set_type(slug, set_name)
        year = _detect_year(slug, set_name)

        sets.append({
            "url": full_url,
            "slug": slug,
            "name": set_name,
            "type": set_type,
            "year": year,
        })

    logger.info(f"{len(sets)} Sets gefunden")
    return sets


def _parse_set_cards(
    session: requests.Session,
    card_set: dict,
    config: dict,
) -> list[dict]:
    """Alle Karten eines Sets abrufen und filtern."""
    whitelist = config.get("characters_whitelist", [])
    numbered_max = config.get("numbered_max", 99)
    card_types_cfg = config.get("card_types", {})
    set_type = card_set["type"]

    # Deaktivierte Typen überspringen
    if set_type == "autograph" and not card_types_cfg.get("autographs", True):
        return []
    if set_type == "vintage" and not card_types_cfg.get("vintage", True):
        return []
    if set_type == "base" and not card_types_cfg.get("numbered", True):
        return []

    soup = _fetch_page(session, card_set["url"])
    if not soup:
        return []

    rows = soup.select("tr[data-product]")
    logger.debug(f"  {len(rows)} Karten in '{card_set['name']}'")

    cards = []
    for row in rows:
        title_td = row.find("td", class_="title")
        if not title_td:
            continue

        title_link = title_td.find("a")
        if not title_link:
            continue

        card_name = title_link.get_text(strip=True)
        card_url = title_link.get("href", "")
        if card_url and not card_url.startswith("http"):
            card_url = f"{BASE_URL}{card_url}"

        # Print-Run (Auflage)
        print_run_span = title_td.find("span", class_="list-print-run")
        numbered_to = None
        if print_run_span:
            run_text = print_run_span.get_text(strip=True).replace("/", "")
            try:
                numbered_to = int(run_text)
            except ValueError:
                pass

        # Kartentyp bestimmen
        if set_type == "autograph":
            card_type = "autograph"
        elif set_type == "vintage":
            card_type = "vintage"
        elif numbered_to is not None and numbered_to <= numbered_max:
            card_type = "numbered"
        else:
            card_type = "base"

        # Basis-Karten überspringen
        if card_type == "base":
            continue

        # Charakter-Filter für Autogramm und Nummerierte Karten
        character = None
        if card_type in ("autograph", "numbered"):
            character = _find_character(card_name, whitelist)
            if character is None:
                continue  # Kein bekannter Charakter → überspringen

        # Preise extrahieren
        ungraded = _parse_price(
            row.select_one("td.used_price .js-price").get_text(strip=True)
            if row.select_one("td.used_price .js-price") else ""
        )
        grade9 = _parse_price(
            row.select_one("td.cib_price .js-price").get_text(strip=True)
            if row.select_one("td.cib_price .js-price") else ""
        )
        psa10 = _parse_price(
            row.select_one("td.new_price .js-price").get_text(strip=True)
            if row.select_one("td.new_price .js-price") else ""
        )

        cards.append({
            "name": card_name,
            "character": character,
            "card_set": card_set["name"],
            "card_type": card_type,
            "series_year": card_set.get("year"),
            "numbered_to": numbered_to,
            "price_ungraded": ungraded,
            "price_grade9": grade9,
            "price_psa10": psa10,
            "pricecharting_link": card_url,
        })

    return cards


def _upsert_cards(cards: list[dict]) -> int:
    """Karten in SQLite einfügen oder aktualisieren. Gibt Anzahl gespeicherter Karten zurück."""
    if not cards:
        return 0

    now = datetime.utcnow().isoformat()
    saved = 0

    with get_connection() as conn:
        for card in cards:
            # Vorhandene Karte per PriceCharting-Link prüfen
            existing = conn.execute(
                "SELECT id FROM cards WHERE pricecharting_link = ?",
                (card["pricecharting_link"],),
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE cards SET
                        name = ?, character = ?, card_set = ?, card_type = ?,
                        series_year = ?, numbered_to = ?,
                        last_sold_usd = ?, price_grade9 = ?, price_psa10 = ?,
                        updated_at = ?
                       WHERE id = ?""",
                    (
                        card["name"], card["character"], card["card_set"],
                        card["card_type"], card["series_year"], card["numbered_to"],
                        card["price_ungraded"], card["price_grade9"], card["price_psa10"],
                        now, existing["id"],
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO cards
                        (name, character, card_set, card_type, series_year,
                         numbered_to, last_sold_usd, price_grade9, price_psa10,
                         pricecharting_link, last_checked, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        card["name"], card["character"], card["card_set"],
                        card["card_type"], card["series_year"], card["numbered_to"],
                        card["price_ungraded"], card["price_grade9"], card["price_psa10"],
                        card["pricecharting_link"], now, now, now,
                    ),
                )
            saved += 1

    return saved


def scrape_star_wars_cards(config: dict) -> int:
    """Hauptfunktion: PriceCharting scrapen und Karten in DB speichern.

    Gibt Gesamtanzahl gespeicherter Karten zurück.
    """
    logger.info("=== PriceCharting Scraper gestartet ===")
    session = _make_session()

    all_sets = _get_all_set_urls(session)
    if not all_sets:
        return 0

    card_types_cfg = config.get("card_types", {})

    # Nur relevante Sets verarbeiten
    relevant_sets = [
        s for s in all_sets
        if s["type"] != "skip" and (
            (s["type"] == "autograph" and card_types_cfg.get("autographs", True))
            or (s["type"] == "vintage" and card_types_cfg.get("vintage", True))
            or (s["type"] == "base" and card_types_cfg.get("numbered", True))
        )
    ]

    logger.info(f"{len(relevant_sets)} relevante Sets werden verarbeitet")

    total_saved = 0
    for i, card_set in enumerate(relevant_sets, 1):
        logger.info(f"[{i}/{len(relevant_sets)}] {card_set['name']} ({card_set['type']})")
        time.sleep(REQUEST_DELAY_SECONDS)

        try:
            cards = _parse_set_cards(session, card_set, config)
            saved = _upsert_cards(cards)
            total_saved += saved
            if saved:
                logger.info(f"  → {saved} Karten gespeichert")
        except Exception as e:
            logger.error(f"  Fehler bei '{card_set['name']}': {e}")
            continue

    logger.info(f"=== Scraper abgeschlossen — {total_saved} Karten total ===")
    return total_saved
