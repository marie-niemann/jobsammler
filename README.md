# Jobsammler für Moderation, Host & Entertainment

Sammelt jeden Morgen automatisch passende Stellen: Moderation und Host vor der Kamera, digitales Entertainment,
Radio, Castings, Musik, Formatentwicklung und Leitung. Läuft als GitHub Action, also auch, wenn dein Rechner aus ist.

## Wo finde ich die Ergebnisse?

| Datei | Was steht drin |
|---|---|
| [`data/neu.md`](data/neu.md) | **Die neuen Stellen des Tages**, nach Rolle sortiert, mit Links. Hier schaust du jeden Morgen rein. |
| [`data/jobs.json`](data/jobs.json) | Alle Stellen: Titel, Firma, Ort, Link, Datum, offen/geschlossen |
| [`data/run.json`](data/run.json) | Protokoll des letzten Laufs: wie viele Stellen pro Quelle, Fehler und Hinweise |
| [`data/protokolle/`](data/protokolle/) | Ein Protokoll pro Lauf (Dateiname = Datum) |
| [`QUELLEN.md`](QUELLEN.md) | Welche Quellen abgerufen werden, was erlaubt ist und wo du E-Mail-Alerts einrichten solltest |

**Regel:** Eine Stelle ist offen, solange sie in der Quelle steht. Fehlt sie, wird sie als geschlossen markiert
und bleibt noch 60 Tage in `jobs.json`.

Sortierung: zuerst nach Wichtigkeit der Rolle (Host/Digital oben), dann nach Ort (Berlin, München, Hamburg,
dann remote, dann „Ort prüfen“, dann andere Orte mit kurzem Einsatz).

## Einen Lauf von Hand starten

1. Öffne dein Repository auf github.com.
2. Klicke oben auf **Actions**.
3. Klicke links auf **Stellen sammeln**.
4. Klicke rechts auf **Run workflow** und dann auf den grünen Knopf **Run workflow**.
5. Nach etwa 5–10 Minuten ist der Lauf fertig (grüner Haken). Dann liegt die neue `data/neu.md` im Repository.

Automatisch läuft er jeden Morgen um ca. 5:17 Uhr (im Sommer 6:17 Uhr). GitHub startet geplante Läufe manchmal
etwas später, das ist normal.

## Suchbegriffe und Firmen selbst ändern

Alle Einstellungen stehen im Ordner [`config/`](config/). Ändern geht direkt auf github.com:

1. Datei öffnen (z. B. `config/roles.yaml`).
2. Rechts oben auf den **Stift** ✏️ klicken.
3. Ändern.
4. Rechts oben auf **Commit changes…** klicken und noch einmal **Commit changes** bestätigen.

Ab dem nächsten Lauf gilt die Änderung. Willst du sie sofort sehen, starte einen Lauf von Hand (siehe oben).

**Wichtig bei diesen Dateien:** Die Einrückung (Leerzeichen am Zeilenanfang) muss stimmen, und jeder
Listeneintrag beginnt mit `- `. Am einfachsten kopierst du eine bestehende Zeile und änderst nur den Text.
Keine Tabs verwenden.

### `config/roles.yaml` – Rollen und Suchbegriffe

Jede Rolle hat eine Liste `terms`. Ein Suchbegriff passt, wenn **alle seine Wörter** im Stellentitel vorkommen.
Groß-/Kleinschreibung und Endungen wie -in, /in, (m/w/d) sind egal.

Beispiel: einen neuen Suchbegriff „Showmasterin“ zur Rolle Host hinzufügen:

```yaml
host:
  name: Moderation & Host vor der Kamera
  prio: 1
  terms:
    - Moderator
    - Showmasterin        # <- neue Zeile
```

- `prio`: 1 = wichtig (steht oben), 3 = weniger wichtig.
- `ohne`: Wörter, bei denen ein Treffer für diese Rolle doch nicht zählt (z. B. „hostess“ bei Host).
- `suche_ba`: Begriffe, mit denen bei der Arbeitsagentur gesucht wird. Wenn du dort mehr finden willst,
  ergänze hier ein Wort **und** passende `terms`.

### `config/exclude.yaml` – was nie auftauchen soll

- `titel`: Stellentitel, die eines dieser Wörter enthalten, fliegen raus (z. B. „praktikum“, „content moderat“).
- `firmen`: Firmen, die nie auftauchen sollen (z. B. Zeitarbeitsfirmen).
- `ba_berufe`: Berufsbezeichnungen der Arbeitsagentur, die nie passen.

Ein Eintrag trifft auch Wortteile: `podcast producer` trifft auch „Senior Podcast Producer“.
Willst du doch Volontariate sehen? Einfach die Zeile `- volontariat` löschen.

### `config/orte.yaml` – wo die Stelle sein darf

- `wunschorte`: Berlin, München, Hamburg, in dieser Reihenfolge. Einen Ort hinzufügen:
  ```yaml
    - name: Köln
      muster: köln|koeln|cologne|hürth
  ```
- `kurzzeit_woerter`: Stellen in anderen Orten kommen nur in die Liste, wenn sie remote sind oder eines dieser
  Wörter enthalten (z. B. „casting“, „drehtag“, „event“).

### `config/companies.yaml` – Firmen und Sender

- Teil `quellen`: wird automatisch abgerufen. Eine Quelle vorübergehend abschalten: Zeile `aus: true` darunter setzen.
- Teil `alerts`: Firmen, die nicht automatisch abgerufen werden dürfen oder können. Hier lohnt sich ein E-Mail-Alert.

**Neue Firma aufnehmen:** Am einfachsten in Claude Code sagen: „Nimm Firma X in den Jobsammler auf.“
Dann wird geprüft, welches Bewerbungssystem die Firma nutzt und ob das Abrufen erlaubt ist.
Selbst geht es, wenn die Firma eines dieser Systeme nutzt (zu erkennen an der Adresse der Stellenliste):

| Adresse der Stellenliste sieht so aus | `art` |
|---|---|
| `https://FIRMA.softgarden.io/...` | `softgarden` mit `url: https://FIRMA.softgarden.io/de/vacancies` |
| `https://FIRMA.jobs.personio.de/...` | `personio` mit `url: https://FIRMA.jobs.personio.de/xml` |
| `.../Jobs/All` oder `umantis` in der Adresse | `umantis` |
| `.../search/?q=` (SAP SuccessFactors) | `successfactors` |
| ein RSS-Feed | `rss` |

Beispiel:

```yaml
  - name: Neue Produktionsfirma
    art: softgarden
    url: https://neuefirma.softgarden.io/de/vacancies
    ort: Berlin
```

## Hilfe, etwas stimmt nicht

- **In `neu.md` steht nichts:** Das ist bei Moderationsjobs häufig, es gibt einfach wenige öffentliche Ausschreibungen.
  Schau in `data/run.json` unter `fehler`, ob eine Quelle Probleme hatte.
- **Der Lauf ist rot (fehlgeschlagen):** Unter **Actions** auf den roten Lauf klicken, dann siehst du die Fehlermeldung.
  Oft liegt es an einem Tippfehler in einer `config`-Datei (z. B. falsche Einrückung).
- **Eine Quelle meldet „keine einzige Stelle gelesen“:** Die Firma hat vermutlich ihre Seite umgebaut.
  Die Quelle mit `aus: true` abschalten und Claude Code bitten, den Leseteil anzupassen.

## Lokal ausführen (optional, für Technikinteressierte)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python collect.py
```

Aufbau angelehnt an [fabiuschko/jobsammler](https://github.com/fabiuschko/jobsammler).
