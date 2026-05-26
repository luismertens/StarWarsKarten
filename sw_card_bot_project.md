# SW Card Hunter — Projektstruktur

## Ziel
Automatisiertes Tool das Star Wars Sammelkarten auf eBay überwacht, Preise analysiert und gute Deals per Telegram meldet. Alle Daten landen in Notion.

---

## Fokus-Kartentypen
1. **Autogramm-Karten** (On-Card, offizielles Topps Certified Auto, PSA-bewertet)
2. **Vintage Karten 1977–1983** (PSA-bewertet, gute Deals für jeweilige Note)
3. **Nummerierte Parallels** (PSA-bewertet, Deals unter Marktdurchschnitt)

> Regel: **Nur PSA-gegraded Karten** werden getrackt und gekauft.

---

## Tech-Stack

| Tool | Zweck | Kosten |
|---|---|---|
| Python 3.11+ | Hauptsprache | Kostenlos |
| eBay Finding API | Listings + Sold Prices abrufen | Kostenlos |
| PriceCharting Scraper | Karten-Datenbank aufbauen | Kostenlos |
| Notion API | Daten speichern + visualisieren | Kostenlos |
| Telegram Bot API | Deal-Alerts senden | Kostenlos |
| SQLite | Lokale Zwischenspeicherung | Kostenlos |

---

## Projektstruktur

```
sw-card-hunter/
│
├── README.md
├── requirements.txt
├── .env                          # API Keys (nie in Git!)
├── config.yaml                   # Suchparameter, Schwellenwerte
│
├── data/
│   └── cards.db                  # SQLite Datenbank
│
├── src/
│   ├── scraper/
│   │   └── pricecharting.py      # Karten-Datenbank von PriceCharting aufbauen
│   │
│   ├── ebay/
│   │   ├── search.py             # Aktuelle Listings abrufen
│   │   └── sold.py               # Sold Listings / Marktpreise
│   │
│   ├── analyzer/
│   │   ├── pricing.py            # Durchschnittspreis, Median, PSA-Prämie berechnen
│   │   └── deals.py              # Deal-Score berechnen (wie gut ist ein Angebot)
│   │
│   ├── notion/
│   │   └── sync.py               # Daten in Notion Datenbank schreiben
│   │
│   ├── telegram/
│   │   └── alerts.py             # Telegram Benachrichtigungen senden
│   │
│   └── main.py                   # Hauptprogramm, Scheduler
│
└── notebooks/
    └── market_analysis.ipynb     # Manuelle Analysen, Experimente
```

---

## Konfiguration (config.yaml)

```yaml
# Welche Charaktere werden überwacht
characters:
  - "Anakin Skywalker"
  - "Darth Vader"
  - "Luke Skywalker"
  - "Han Solo"
  - "Boba Fett"
  - "Jango Fett"
  - "Padme Amidala"
  - "Obi-Wan Kenobi"

# Nur PSA-gegraded Karten
grading:
  provider: "PSA"
  min_grade: 8          # Nur PSA 8, 9, 10

# Kartentypen die überwacht werden
card_types:
  autographs: true       # Autogramm-Karten
  vintage: true          # 1977-1983 Vintage
  numbered: true         # Nummerierte Parallels
  base: false            # Normale Basis-Karten nicht

# Numbered Cards: nur bis welche Auflage?
numbered_max: 99         # Nur /99 oder seltener

# Deal-Alert: wenn Preis X% unter Durchschnitt liegt
deal_threshold_percent: 15   # 15% unter Marktdurchschnitt = Alert

# Wie oft läuft der Bot?
scheduler_interval_minutes: 30

# Preislimits pro Kategorie (in USD)
price_limits:
  autographs:
    min: 50
    max: 2000
  vintage:
    min: 20
    max: 500
  numbered:
    min: 20
    max: 300
```

---

## Notion Datenbank Struktur

### Tabelle 1: `Cards` (alle bekannten Karten)
| Property | Typ | Beschreibung |
|---|---|---|
| Name | Title | Kartenname z.B. "Anakin Skywalker Auto /25" |
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

### Tabelle 2: `Deals` (gemeldete Deals)
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

## Ablauf — wie der Bot funktioniert

```
1. [Einmalig] PriceCharting scrapen
   → Alle Star Wars Karten in SQLite speichern
   → Nach Charakter + Typ filtern

2. [Alle 30 Min] eBay API abfragen
   → Aktuelle PSA Listings für Ziel-Charaktere
   → Sold Listings der letzten 90 Tage

3. [Analyse]
   → Durchschnittspreis berechnen
   → Aktuelles Angebot mit Durchschnitt vergleichen
   → Deal-Score berechnen

4. [Alert]
   → Wenn Deal-Score > Schwellenwert:
     → Telegram Nachricht senden
     → Eintrag in Notion Deals Tabelle

5. [Notion Sync]
   → Alle Marktpreise in Cards Tabelle aktualisieren
```

---

## Schritt-für-Schritt Umsetzung

### Phase 1 — Setup (Tag 1)
- [ ] Python Umgebung einrichten
- [ ] eBay Developer Account erstellen → API Key holen
- [ ] Notion Integration erstellen → Token holen
- [ ] Telegram Bot erstellen via BotFather → Token holen
- [ ] .env Datei mit allen Keys anlegen
- [ ] requirements.txt installieren

### Phase 2 — Datenbasis (Tag 2)
- [ ] PriceCharting Scraper schreiben
- [ ] Karten nach Charakter + Typ filtern
- [ ] SQLite Datenbank befüllen

### Phase 3 — eBay Integration (Tag 3)
- [ ] eBay Finding API einrichten
- [ ] Sold Listings für Test-Charakter abrufen
- [ ] Preisanalyse berechnen

### Phase 4 — Alerts (Tag 4)
- [ ] Telegram Bot einrichten
- [ ] Deal-Erkennung implementieren
- [ ] Test-Alert senden

### Phase 5 — Notion Sync (Tag 5)
- [ ] Notion API Tabellen anlegen
- [ ] Sync-Script schreiben
- [ ] Alles zusammenbauen in main.py

### Phase 6 — Automatisierung
- [ ] Scheduler einrichten (läuft alle 30 Min)
- [ ] Auf eigenem Rechner oder kostenlosem Server deployen

---

## API Keys die du brauchst

```
# .env Datei (nie teilen!)
EBAY_APP_ID=
EBAY_CERT_ID=
EBAY_DEV_ID=
NOTION_TOKEN=
NOTION_CARDS_DB_ID=
NOTION_DEALS_DB_ID=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

---

## Kosten

| Service | Kosten |
|---|---|
| eBay API | Kostenlos |
| Notion API | Kostenlos |
| Telegram Bot | Kostenlos |
| Python / SQLite | Kostenlos |
| Server (optional) | Kostenlos via GitHub Actions oder Railway Free Tier |
| **Gesamt** | **€0/Monat** |
