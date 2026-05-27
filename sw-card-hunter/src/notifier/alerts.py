"""Telegram Alerts — Deal-Benachrichtigungen senden."""

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

TYPE_LABELS = {
    "autograph": "Autogramm",
    "vintage": "Vintage",
    "numbered": "Nummeriert",
}


def _get_bot():
    """Telegram Bot-Instanz erstellen."""
    from telegram import Bot
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN nicht gesetzt")
    return Bot(token=token)


def _get_chat_id() -> str:
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID nicht gesetzt")
    return chat_id


async def _send_async(text: str) -> bool:
    """Nachricht asynchron senden."""
    bot = _get_bot()
    chat_id = _get_chat_id()
    await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    return True


def _send(text: str) -> bool:
    """Synchroner Wrapper für async Telegram-Send."""
    try:
        asyncio.run(_send_async(text))
        return True
    except Exception as e:
        logger.error(f"Telegram Fehler: {e}")
        return False


def send_test_message() -> bool:
    """Test-Nachricht senden um Verbindung zu prüfen."""
    logger.info("Sende Telegram Test-Nachricht...")
    success = _send("✅ <b>SW Card Hunter läuft!</b>\n\nBot ist aktiv und überwacht Star Wars Karten auf eBay.")
    if success:
        logger.info("Test-Nachricht erfolgreich gesendet")
    return success


def send_deal_alert(deal: dict) -> bool:
    """Deal-Alert per Telegram senden.

    deal muss enthalten: card_name, character, card_type, card_set,
    listing_price, market_price, savings_percent, ebay_url.
    Optional: pricecharting_url, numbered_to, psa_grade
    """
    card_type_label = TYPE_LABELS.get(deal.get("card_type", ""), deal.get("card_type", ""))
    auflage = f" /{deal['numbered_to']}" if deal.get("numbered_to") else ""
    psa = f" | PSA {deal['psa_grade']}" if deal.get("psa_grade") else ""
    charakter = deal.get("character") or "Unbekannt"

    ebay_link = deal.get("ebay_url", "")
    pc_link = deal.get("pricecharting_url", "")
    links_text = f'\n🔗 <a href="{ebay_link}">eBay Angebot</a>' if ebay_link else ""
    if pc_link:
        links_text += f'\n📋 <a href="{pc_link}">PriceCharting</a>'

    text = (
        f"🎯 <b>DEAL GEFUNDEN{auflage}</b>\n\n"
        f"<b>{deal['card_name']}</b>\n"
        f"{charakter}  |  {card_type_label}{psa}\n"
        f"📦 {deal.get('card_set', '')}\n\n"
        f"💰 Angebot:    <b>${deal['listing_price']:.2f}</b>\n"
        f"📊 Marktpreis: ${deal['market_price']:.2f}\n"
        f"🔥 Ersparnis:  <b>{deal['savings_percent']:.1f}% unter Markt</b>"
        f"{links_text}"
    )

    logger.info(f"Sende Deal-Alert: {deal['card_name']} ({deal['savings_percent']:.1f}% unter Markt)")
    success = _send(text)
    if success:
        logger.info("Deal-Alert gesendet")
    return success
