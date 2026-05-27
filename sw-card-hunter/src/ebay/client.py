"""eBay Browse API — Low-level HTTP-Client mit Token-Cache und Rate-Limit-Tracking."""

import base64
import logging
import os
import time
from datetime import date

import requests

from db import get_meta, set_meta

logger = logging.getLogger(__name__)

_REQUEST_DELAY = 0.3


class EbayBrowseClient:
    TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    SCOPE = "https://api.ebay.com/oauth/api_scope"
    DAILY_LIMIT = 4800

    def __init__(self) -> None:
        app_id = os.getenv("EBAY_APP_ID")
        cert_id = os.getenv("EBAY_CERT_ID")
        if not app_id or not cert_id:
            raise ValueError("EBAY_APP_ID / EBAY_CERT_ID nicht gesetzt")
        self._credentials = base64.b64encode(f"{app_id}:{cert_id}".encode()).decode()
        self._token: str | None = None
        self._token_expiry: float = 0
        self._session = requests.Session()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def find_active(self, keywords: str, max_results: int = 100) -> list[dict]:
        """Aktuelle eBay-Listings suchen."""
        if self.calls_today() >= self.DAILY_LIMIT:
            logger.warning(f"eBay Daily-Limit ({self.DAILY_LIMIT}) erreicht — überspringe Call")
            return []

        token = self._get_token()
        params = {
            "q": keywords,
            "limit": min(max_results, 200),
            "filter": "buyingOptions:{FIXED_PRICE|AUCTION}",
        }

        time.sleep(_REQUEST_DELAY)
        try:
            resp = self._session.get(
                self.SEARCH_URL,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.warning(f"eBay Browse API Fehler: {e}")
            return []

        self._increment_counter()
        return self._parse_items(data)

    def calls_today(self) -> int:
        today = date.today().isoformat()
        if get_meta("ebay_calls_date") != today:
            return 0
        return int(get_meta("ebay_daily_calls") or 0)

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        try:
            resp = self._session.post(
                self.TOKEN_URL,
                headers={
                    "Authorization": f"Basic {self._credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data=f"grant_type=client_credentials&scope={self.SCOPE}",
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            self._token_expiry = time.time() + data.get("expires_in", 7200)
            return self._token
        except Exception as e:
            raise RuntimeError(f"eBay OAuth Token fehlgeschlagen: {e}") from e

    def _increment_counter(self) -> None:
        today = date.today().isoformat()
        current = int(get_meta("ebay_daily_calls") or 0)
        if get_meta("ebay_calls_date") != today:
            current = 0
            set_meta("ebay_calls_date", today)
        set_meta("ebay_daily_calls", str(current + 1))

    def _parse_items(self, data: dict) -> list[dict]:
        results = []
        for item in data.get("itemSummaries", []):
            try:
                price_obj = item.get("price", {})
                if price_obj.get("currency") != "USD":
                    continue
                price = float(price_obj["value"])
                if price <= 0:
                    continue

                title = item.get("title", "")
                if "PSA" not in title.upper():
                    continue

                results.append({
                    "title": title,
                    "price": price,
                    "url": item.get("itemWebUrl", ""),
                    "item_id": item.get("itemId", ""),
                })
            except (KeyError, ValueError):
                continue
        return results


# Alias für bestehende Importe
EbayFindingClient = EbayBrowseClient
