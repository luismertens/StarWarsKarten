"""eBay Listing → DB-Card Matching — Titel-Parsing und Zuordnung."""

import re
import logging

logger = logging.getLogger(__name__)

VINTAGE_YEARS = [1977, 1978, 1979, 1980, 1981, 1982, 1983]

# Schauspieler → zugehörige Charaktere (für DB-Lookup)
ACTOR_TO_CHARACTERS: dict[str, list[str]] = {
    "Mark Hamill":        ["Luke Skywalker", "Mark Hamill"],
    "Harrison Ford":      ["Han Solo", "Harrison Ford"],
    "Hayden Christensen": ["Anakin Skywalker", "Darth Vader", "Hayden Christensen"],
    "Ewan McGregor":      ["Obi-Wan Kenobi", "Ewan McGregor"],
    "Pedro Pascal":       ["The Mandalorian", "Din Djarin", "Pedro Pascal"],
    "Carrie Fisher":      ["Leia Organa", "Carrie Fisher"],
    "Billy Dee Williams": ["Lando Calrissian", "Billy Dee Williams"],
    "Anthony Daniels":    ["Anthony Daniels"],
}


def extract_psa_grade(title: str) -> int | None:
    """PSA-Grade aus Listing-Titel extrahieren. Nur 8, 9, 10 werden zurückgegeben."""
    match = re.search(r"\bPSA\s*(10|[89])\b", title, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def extract_numbered_to(title: str) -> int | None:
    """Print-Run aus Titel extrahieren, z.B. '/25' → 25."""
    match = re.search(r"/(\d{1,4})\b", title)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None


def build_keywords(character: str | None, card_type: str, year: int | None = None) -> str:
    """Such-Keywords für eBay Browse API bauen."""
    if card_type == "vintage" and year:
        return f"star wars topps {year} PSA"
    if card_type == "autograph" and character:
        # "auto" statt "autograph" — verhindert Match auf PSA/DNA-Echtheits-Zertifikate
        return f'star wars "{character}" PSA auto topps'
    if card_type == "numbered" and character:
        return f'star wars "{character}" PSA numbered topps'
    return f'"{character}" PSA star wars topps' if character else "star wars PSA topps"


def get_market_price(card: dict, psa_grade: int | None) -> float | None:
    """Marktpreis für einen bestimmten PSA-Grade aus der Karte lesen.

    Fallback-Kette: grade-spezifisch → nächster verfügbarer → None
    """
    if psa_grade == 10:
        return card.get("price_psa10") or card.get("price_grade9") or card.get("last_sold_usd")
    elif psa_grade == 9:
        return card.get("price_grade9") or card.get("price_psa10") or card.get("last_sold_usd")
    else:  # PSA 8 oder unbekannt
        return card.get("last_sold_usd") or card.get("price_grade9")


def find_matching_card(
    listing: dict,
    cards: list[dict],
    character: str | None,
    card_type: str,
) -> dict | None:
    """Passendes Karten-Dict aus der DB-Liste für ein eBay-Listing finden.

    Matching: card_type + character (außer vintage) + irgendein Marktpreis vorhanden.
    Bei mehreren Treffern: Karte mit Marktpreis am nächsten am Listing-Preis.
    """
    grade = extract_psa_grade(listing["title"])
    numbered_to = extract_numbered_to(listing["title"])

    # Alle Charakternamen für diesen Suchbegriff (Schauspieler → Charaktere)
    char_names = ACTOR_TO_CHARACTERS.get(character, [character]) if character else []

    candidates = [
        c for c in cards
        if c.get("card_type") == card_type
        and get_market_price(c, grade) is not None
        and (card_type == "vintage" or c.get("character") in char_names)
    ]

    if not candidates:
        return None

    # Für numbered: bevorzuge Karten mit passendem numbered_to
    if card_type == "numbered" and numbered_to is not None:
        exact = [c for c in candidates if c.get("numbered_to") == numbered_to]
        if exact:
            candidates = exact

    # Nimm die Karte deren Marktpreis am nächsten am Listing-Preis liegt
    listing_price = listing["price"]
    return min(candidates, key=lambda c: abs((get_market_price(c, grade) or 0) - listing_price))
