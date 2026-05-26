# SW Card Hunter

Automatisierter Bot der Star Wars Sammelkarten auf eBay überwacht, Deals erkennt und per Telegram meldet.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# .env mit echten API Keys befüllen
```

## Starten

```bash
cd src
python main.py
```

## Konfiguration

Alle Einstellungen in `config.yaml`:
- `characters_whitelist` — Charaktere für Autogramm + Nummerierte Karten
- `price_limits` — Budget pro Kategorie
- `deal_threshold_percent` — Schwellenwert für Deal-Alerts (Standard: 15%)
- `card_types` — Kartentypen an/aus schalten

## Projektstruktur

```
src/
├── main.py          # Einstiegspunkt + Scheduler
├── db.py            # SQLite Datenbank
├── scraper/         # PriceCharting Scraper
├── ebay/            # eBay Finding API
├── analyzer/        # Preisanalyse + Deal-Erkennung
├── notion/          # Notion Sync
└── telegram/        # Deal-Alerts
```
