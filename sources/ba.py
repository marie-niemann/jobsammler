"""Jobsuche der Bundesagentur für Arbeit.

Die Arbeitsagentur bietet keine offizielle Schnittstelle an. Diese hier nutzt ihre eigene Jobbörse;
sie ist öffentlich dokumentiert von bundesAPI: https://github.com/bundesAPI/jobsuche-api
Wir übernehmen nur Titel, Firma, Ort, Datum, Link und einen kurzen Auszug – keine ganzen Seiten.

Stand der Prüfung (2026-11-14):
- Suche über /pc/v6/jobs, Details über /pc/v4/jobdetails/<base64(refnr)>.
- angebotsart 1 = Arbeit, 2 = Selbständigkeit/freie Mitarbeit. Beides wird abgefragt.
- zeitarbeit=false und pav=false schließen Zeitarbeit und private Vermittlung aus.
- Die Suche ("was") ist ungenau. Deshalb wird mit "suche_ba" aus roles.yaml gesucht und danach streng gefiltert.
"""

import base64

from .common import PoliteSession, to_text

API = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc"
HEADERS = {"X-API-Key": "jobboerse-jobsuche"}
PUBLIC_URL = "https://www.arbeitsagentur.de/jobsuche/jobdetail/{}"
PAGE_SIZE = 100
MAX_PAGES = 3


def _orte(j):
    return [
        (l.get("adresse") or {}).get("ort", "")
        for l in j.get("stellenlokationen") or []
        if (l.get("adresse") or {}).get("ort")
    ]


def _salary(j):
    lo, hi = j.get("gehaltsspanneVon"), j.get("gehaltsspanneBis")
    if not lo and not hi:
        return ""
    fmt = lambda x: f"{x:,.0f}".replace(",", ".")  # noqa: E731
    return f"{fmt(lo)}–{fmt(hi)} €" if lo and hi and lo != hi else f"{fmt(lo or hi)} €"


def fetch_details(sess, refnr):
    enc = base64.b64encode(refnr.encode()).decode()
    r = sess.get(f"{API}/v4/jobdetails/{enc}", headers=HEADERS)
    if r.status_code in (404, 410):
        return None
    r.raise_for_status()
    return r.json()


def fetch(roles, flt, known=None, max_details=150, sess=None, log=print):
    """Rückgabe: (jobs, info). jobs sind fertig bewertete Einträge (mit Rolle und Ort)."""
    sess = sess or PoliteSession(pause=0.5)
    known = known or {}
    raw, errors, dropped, calls_before = {}, [], {}, sess.calls

    def drop(why):
        dropped[why] = dropped.get(why, 0) + 1

    terms = sorted({t for spec in roles.values() for t in spec.get("suche_ba") or []})
    for term in terms:
        for art in (1, 2):
            for page in range(1, MAX_PAGES + 1):
                params = {"was": term, "angebotsart": art, "zeitarbeit": "false", "pav": "false",
                          "size": PAGE_SIZE, "page": page}
                try:
                    r = sess.get(f"{API}/v6/jobs", params=params, headers=HEADERS)
                    r.raise_for_status()
                    d = r.json()
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"Arbeitsagentur: Suche '{term}' (Art {art}, Seite {page}) fehlgeschlagen: {exc}")
                    break
                items = d.get("ergebnisliste") or []
                for j in items:
                    if j.get("referenznummer"):
                        j["_art"] = "freie Mitarbeit / selbständig" if art == 2 else ""
                        raw.setdefault(j["referenznummer"], j)
                if page * PAGE_SIZE >= (d.get("maxErgebnisse") or 0) or not items:
                    break

    jobs, loaded = [], 0
    for ref, j in raw.items():
        title = (j.get("stellenangebotsTitel") or "").strip()
        beruf = j.get("hauptberuf", "")
        x = flt.ex.ba_job(beruf)
        if x:
            drop(f"ausgeschlossen (Beruf: {x})")
            continue
        if not flt.role_of(title):
            drop("titel passt zu keiner rolle oder ausgeschlossen")
            continue
        if j.get("istGeringfuegigeBeschaeftigung"):
            drop("minijob")
            continue
        jid = f"ba:{ref}"
        desc = (known.get(jid) or {}).get("description", "")
        remote = j.get("homeofficeprozent") == 100
        # Beschreibung laden (für neue Stellen), um kurze Einsätze in anderen Orten zu erkennen
        if not desc and loaded < max_details:
            try:
                det = fetch_details(sess, ref)
                loaded += 1
                if det:
                    desc = to_text(det.get("stellenangebotsBeschreibung", ""))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Arbeitsagentur: Details für {ref} fehlgeschlagen: {exc}")
        ev, why = flt.evaluate(title, j.get("firma", ""), _orte(j), desc, remote)
        if why:
            drop(why)
            continue
        jobs.append({
            "id": jid,
            "source": "Arbeitsagentur",
            "company": (j.get("firma") or "").strip(),
            "title": title,
            "url": PUBLIC_URL.format(ref),
            "published": j.get("datumErsteVeroeffentlichung", "") or "",
            "description": desc,
            "salary": _salary(j),
            "art": j.get("_art", ""),
            **ev,
        })

    log(f"Arbeitsagentur: {len(jobs)} passend von {len(raw)} gefundenen, {sess.calls - calls_before} Aufrufe")
    return jobs, {"calls": sess.calls - calls_before, "errors": errors, "dropped": dropped, "gefunden": len(raw)}
