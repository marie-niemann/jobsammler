# Quellen: was abgerufen wird und warum

Stand der Prüfung: 14.11.2026. Geprüft wurden robots.txt, Nutzungsbedingungen/AGB/Impressum und
ob es einen RSS-Feed oder eine Schnittstelle gibt. Der Jobsammler prüft die robots.txt außerdem **bei jedem Lauf**
neu: Verbietet eine Seite den Abruf irgendwann, wird sie übersprungen und das steht in `data/run.json`.

Abgerufen wird höchstens einmal am Tag, mit Pausen zwischen den Anfragen. Gespeichert werden nur Titel, Firma, Ort,
Datum, Link und ein kurzer Auszug, nie ganze Seiten.

## Automatisch abgerufen

| Quelle | Art | Prüfergebnis |
|---|---|---|
| Jobsuche der Arbeitsagentur | Schnittstelle der BA-Jobbörse | Die BA bietet **keine offizielle** Schnittstelle an. Diese ist öffentlich dokumentiert ([bundesAPI](https://github.com/bundesAPI/jobsuche-api)) und wird viel genutzt. Laut Impressum ist nur das Veröffentlichen kompletter Seiten genehmigungspflichtig; das tun wir nicht. |
| newsroom.de | offizieller Job-RSS-Feed | robots.txt erlaubt alles |
| RADIOSZENE | offizieller RSS-Feed der Kategorie „Stellenangebote“ | robots.txt erlaubt Abrufen (sperrt nur bestimmte Bots, nicht diesen); Impressum ohne Verbot. Nur Anzeigen der letzten 60 Tage. |
| DWDL.de (DWDL.jobs) | öffentliche Anzeigenliste | robots.txt erlaubt alles außer `/features/vitamind/`; Impressum ohne Verbot. Laut DWDL ist keine Anzeige älter als vier Wochen. |
| Karriere-Feeds von NDR, ZDF, SWR (mit funk), MDR, BR, ARD-Programmdirektion | offizielle RSS-Feeds | robots.txt erlaubt sie. Enthalten oft nur Rubriken, selten einzelne Stellen. |
| ZDF Digital | offizielle Personio-Schnittstelle (XML) | robots.txt erlaubt alles |
| btf (bildundtonfabrik), ITV Studios Germany | Personio-Stellenseite (die XML-Schnittstelle ist dort abgeschaltet) | robots.txt erlaubt alles |
| rbb, NDR, BR | öffentliche Stellenliste (umantis) | robots.txt erlaubt die Stellenliste |
| ZDF, ProSiebenSat.1 (Joyn, Seven.One, Studio71, Redseven), RTL Deutschland | öffentliche Stellensuche (SAP SuccessFactors) | robots.txt erlaubt die Suche. **Gesperrt** ist der RSS-Bereich `/services/`, der deshalb nicht genutzt wird. RTL schließt „kommerzielles Text und Data Mining“ aus; dieser Jobsammler ist privat und nicht kommerziell. |
| Banijay Germany (Brainpool, Good Times), EndemolShine, Seapoint, Deutschlandradio, Radio Bremen, SR | öffentliche Stellenliste (softgarden) | robots.txt erlaubt die Liste, sperrt nur `/api/` und `/widgets/` (werden nicht genutzt). Die **Website** endemolshine.de verbietet Crawler in ihren AGB und wird deshalb nicht abgerufen, nur die softgarden-Liste. |
| UFA (mit UFA Show & Factual) | öffentliche Stellenliste auf ufa.de | robots.txt erlaubt die Seite |
| Hessischer Rundfunk | öffentliche Stellenliste auf hr.de | robots.txt erlaubt die Seite |

Hinweis: Stellenlisten, die keine offizielle Schnittstelle oder kein Feed sind, wurden auf deinen Wunsch dazugenommen,
wo robots.txt und Nutzungsbedingungen es erlauben. Ändert eine Firma ihre Seite, kann das Lesen dort ausfallen;
dann steht im Protokoll „keine einzige Stelle gelesen“.

## Nicht automatisch: bitte E-Mail-Jobalert einrichten

| Wo | Warum nicht automatisch | So geht der Alert |
|---|---|---|
| Raab Entertainment | robots.txt sperrt Programme ausdrücklich | jobs.raab-entertainment.de regelmäßig ansehen |
| florida entertainment | Website antwortet Programmen nicht | Karriereseite / LinkedIn folgen |
| Constantin Entertainment | keine lesbare Stellenliste | constantin-entertainment.de/karriere und constantin-casting.de |
| Bavaria Film / Bavaria Entertainment | Liste wird per JavaScript nachgeladen | bavaria-film.de/jobportal |
| WDR | Liste wird per JavaScript nachgeladen | karriere.wdr.de, Job-Alert im Bewerbungsportal |
| Rocket Beans TV, Hyperbole, Mediakraft | keine lesbare Stellenliste | Website / Social Media folgen |
| Netflix | robots.txt verbietet Abrufen | jobs.netflix.com |
| Amazon (Prime Video), Disney, Warner Bros. Discovery | keine offene Schnittstelle, Seiten per JavaScript | Job-Alert auf amazon.jobs, join.disneycareers.com, careers.wbd.com |
| Sky Deutschland, DAZN | blocken automatische Zugriffe | Job-Alert auf der Karriereseite |
| e-TALENTA (früher Castforward), filmmakers, Schauspielervideos | Castings nur mit Profil; Nutzungsbedingungen bzw. robots.txt verbieten Auslesen | Profil anlegen, Casting-Benachrichtigungen einschalten |
| Crew United | Jobinserate nur mit Login | Profil, Benachrichtigungen |
| kress / MEEDIA | großteils über newsroom.de abgedeckt | Job-Newsletter |

**Tipp:** Bei rbb, NDR, BR (Stellen-Abonnement), den softgarden-Firmen („Stellenangebote abonnieren“) und den
SuccessFactors-Seiten (Job-Alert) kannst du zusätzlich E-Mail-Alerts einrichten. Doppelt hält besser.

## Was die Prüfung sonst gezeigt hat

- Bei der Arbeitsagentur gibt es deutschlandweit nur wenige echte Moderationsstellen (rund 15 Treffer für
  „Moderator“, davon viele Content-Moderation). Deshalb filtert der Jobsammler streng.
- „Host“ bedeutet bei der Arbeitsagentur meist Empfang/Hostess; das wird aussortiert.
