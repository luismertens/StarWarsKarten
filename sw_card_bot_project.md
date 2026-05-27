# SW Card Hunter — Projektdokumentation

## Ziel
Automatisierter Bot der Star Wars Sammelkarten auf eBay überwacht, Preise analysiert und gute Deals per Telegram meldet. Alle Daten landen in Notion.

---

## Fokus-Kartentypen
1. **Autogramm-Karten** — mit Charakter-Filter (Whitelist in config.yaml)
2. **Vintage Karten 1977–1983** — KEIN Charakter-Filter, jede PSA-Karte zu gutem Preis
3. **Nummerierte Parallels /99 oder seltener** — mit Charakter-Filter

> Regel: **Nur PSA-gegraded Karten** (PSA 8, 9, 10) werden getrackt.

---

## Aktueller Stand

### ✅ Phase 1 — Setup (abgeschlossen)
- Projektstruktur unter `sw-card-hunter/` angelegt
- `requirements.txt`, `.env.example`, `config.yaml` erstellt
- SQLite-Datenbank-Schema (Tabellen: `cards`, `deals`, `price_history`)
- `src/main.py` mit Scheduler-Grundgerüst
- Alle API Keys in `.env` eingetragen (außer eBay — wird noch reviewed)

### ✅ Phase 2 — PriceCharting Scraper (abgeschlossen)
- `src/scraper/pricecharting.py` vollständig implementiert
- **4.014 Karten** in lokaler SQLite-Datenbank gespeichert:
  - Nummerierte Parallels: 2.173 Karten
  - Vintage (1977–1983): 1.209 Karten
  - Autogramm-Karten: 632 Karten
- Charakter-Whitelist-Filter mit Wortgrenzen (verhindert Fehl-Matches)
- Rate-Limiting: 1,5 Sekunden zwischen Requests

### ✅ Phase 3.5 — Notion Sync + Telegram + Analyzer (abgeschlossen)
- **Notion Sync** vollständig: 3.463 Karten in Notion-Dashboard synchronisiert
  - Inkrementeller Sync: nur neue/geänderte Karten werden hochgeladen (fast instant)
  - `notion_page_id` wird in SQLite gespeichert für spätere Updates
  - Retry-Logik bei Notion-Fehlern (429/502/503) mit 60s/120s Backoff
- **Telegram Alerts** fertig: `src/notifier/alerts.py`
  - `send_deal_alert()` mit formatierter HTML-Nachricht
  - Test-Nachricht beim Start
- **Analyzer** fertig: `src/analyzer/pricing.py` + `deals.py`
  - Marktpreis-Berechnung (Avg, Median, Liquidität) mit Outlier-Filterung
  - Deal-Erkennung: ≥15% unter Marktdurchschnitt
- **Bereinigung**: Sticker-Karten, TCG/CCG-Sets, Kakawow aus DB entfernt (→ 3.463 saubere Karten)
- **SQLite-Migration**: `meta`-Tabelle für Sync-Timestamps, `notion_page_id` in `cards`

### ⏳ Phase 3 — eBay Integration (wartet auf eBay API Key)
- eBay Developer Account submitted, Key noch ausstehend
- Nächste Session: eBay Finding API einbinden

### 🔲 Phase 4 — Deal-Erkennung + Telegram Alerts (Framework fertig, braucht eBay-Daten)
### 🔲 Phase 5 — Automatisierung / Deployment

---

## Was ist SQLite vs. Notion?

**SQLite** (`data/cards.db`) = lokale Datenbank auf dem Mac. Nur eine Datei auf der Festplatte, kein Online-Service. Der Bot liest und schreibt hier alle Daten intern — als schneller Zwischenspeicher.

**Notion** = kommt in Phase 5. Dann werden alle Karten und Deals aus SQLite nach Notion synchronisiert, so dass du dort ein übersichtliches Dashboard hast.

---

## Tech-Stack

| Tool | Zweck | Status |
|---|---|---|
| Python / SQLite | Hauptsprache + lokale DB | ✅ läuft |
| PriceCharting Scraper | Karten-Datenbank aufbauen | ✅ 3.463 Karten |
| eBay Finding API | Listings + Sold Prices | ⏳ Key ausstehend |
| Telegram Bot API | Deal-Alerts senden | ✅ implementiert |
| Notion API | Dashboard + Sync | ✅ 3.463 Karten live |

---

## Projektstruktur

```
sw-card-hunter/
├── README.md
├── requirements.txt
├── .env                          # API Keys (nie in Git!)
├── .env.example                  # Vorlage mit allen Key-Namen
├── config.yaml                   # Suchparameter, Whitelist, Schwellenwerte
│
├── data/
│   └── cards.db                  # SQLite — 3.463 Karten gespeichert
│
├── logs/
│   └── bot.log                   # Wird beim Start angelegt
│
├── src/
│   ├── main.py                   # Einstiegspunkt + APScheduler (alle 30 Min)
│   ├── db.py                     # SQLite Schema + Hilfsfunktionen
│   │
│   ├── scraper/
│   │   └── pricecharting.py      # ✅ Fertig — scrapt alle Star Wars Sets
│   │
│   ├── ebay/
│   │   ├── search.py             # 🔲 Aktuelle PSA-Listings abrufen
│   │   └── sold.py               # 🔲 Sold Listings / Marktpreise
│   │
│   ├── analyzer/
│   │   ├── pricing.py            # ✅ Durchschnitt, Median, Liquidität
│   │   └── deals.py              # ✅ Deal-Score (15% unter Markt = Alert)
│   │
│   ├── notion/
│   │   └── sync.py               # ✅ 3.463 Karten live in Notion
│   │
│   └── notifier/
│       └── alerts.py             # ✅ Telegram Deal-Alerts
│
└── notebooks/
    └── market_analysis.ipynb     # Manuelle Analysen
```

---

## Konfiguration (config.yaml)

Alle Einstellungen direkt in `config.yaml` bearbeiten:

```yaml
# Charakter-Whitelist — gilt NUR für Autogramm + Nummerierte Karten
# Vintage Karten werden OHNE Charakter-Filter gesucht
characters_whitelist:
  - "Anakin Skywalker"
  - "Darth Vader"
  - "Luke Skywalker"
  - "Han Solo"
  - "Obi-Wan Kenobi"
  - "Padme Amidala"
  - "Leia Organa"
  - "Boba Fett"
  - "Jango Fett"
  - "The Mandalorian"
  - "Yoda"
  - "Ahsoka Tano"
  - "Rey" / "Kylo Ren"
  - "Mark Hamill" / "Harrison Ford" / "Hayden Christensen"
  # ... (28 Einträge gesamt, in config.yaml vollständig)

deal_threshold_percent: 15   # 15% unter Marktdurchschnitt = Alert
numbered_max: 99             # Nur /99 oder seltener
scheduler_interval_minutes: 30

price_limits:
  autographs: {min: 50, max: 2000}
  vintage:    {min: 20, max: 500}
  numbered:   {min: 20, max: 300}
```

---

## Notion Datenbank Struktur (für Phase 5 anlegen)

### Tabelle 1: `Cards`
| Property | Typ | Beschreibung |
|---|---|---|
| Name | Title | z.B. "Anakin Skywalker Auto /25" |
| Charakter | Select | Anakin, Luke, Vader etc. |
| Set | Text | z.B. "2025 Topps Masterwork" |
| Typ | Select | Auto / Vintage / Numbered |
| Auflage | Number | z.B. 25 für /25 |
| PSA Grade | Select | PSA 8 / PSA 9 / PSA 10 |
| Avg Price USD | Number | Durchschnitt letzte 90 Tage |
| Last Sold USD | Number | Letzter Verkaufspreis |
| Sales Count | Number | Verkäufe letzte 90 Tage |
| Liquidität | Select | Hoch / Mittel / Niedrig |
| Zuletzt gecheckt | Date | |
| eBay Link | URL | Sold Listings Link |
| PriceCharting Link | URL | |

### Tabelle 2: `Deals`
| Property | Typ | Beschreibung |
|---|---|---|
| Karte | Relation | Verweis auf Cards Tabelle |
| Angebotspreis | Number | Aktueller Listing-Preis |
| Marktpreis | Number | Berechneter Durchschnitt |
| Ersparnis % | Number | Wie weit unter Markt |
| eBay Listing URL | URL | Direktlink zum Angebot |
| Status | Select | Neu / Geprüft / Gekauft / Abgelaufen |
| Gefunden am | Date | |

---

## Bot starten

```bash
cd sw-card-hunter/src
python main.py
```

Der Bot startet, baut die DB auf (falls nicht vorhanden) und läuft dann alle 30 Minuten.

---

## Nächste Session — Phase 3 (eBay Integration)

**Voraussetzung:** eBay App ID, Cert ID, Dev ID in `.env` eintragen.

Was dann gebaut wird:
1. `src/ebay/sold.py` — Sold Listings der letzten 90 Tage per eBay Finding API
2. `src/ebay/search.py` — Aktuelle PSA-Listings abrufen
3. Deal-Erkennung verbinden (Analyzer ist fertig, braucht nur eBay-Daten)
4. Telegram-Alert auslösen bei Deal (Alert-Framework fertig)
5. Deal in Notion Deals-DB schreiben (sync_deal() fertig)

---

## API Keys

```
# .env Datei (niemals in Git!)
EBAY_APP_ID=        ← ⏳ ausstehend
EBAY_CERT_ID=       ← ⏳ ausstehend
EBAY_DEV_ID=        ← ⏳ ausstehend
NOTION_TOKEN=       ← ✅ vorhanden
NOTION_CARDS_DB_ID= ← ✅ vorhanden
NOTION_DEALS_DB_ID= ← ✅ vorhanden
TELEGRAM_BOT_TOKEN= ← ✅ vorhanden
TELEGRAM_CHAT_ID=   ← ✅ vorhanden
```

---

## Kosten: €0/Monat

Alle genutzten Services sind kostenlos.
