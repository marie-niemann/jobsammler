"""Zweite Prüfrunde: gefundene Feeds und Bewerbungssysteme genauer ansehen.

Für jede Adresse: Status, Inhaltstyp, Anzahl Einträge und die ersten Titel.
Dazu vollständige robots.txt der wichtigsten Hosts und Regel-Treffer in AGB/Nutzungsbedingungen.
Ergebnis: pruefung/ergebnis/bericht2.json
"""

import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

HERE = Path(__file__).resolve().parent
UA = "Mozilla/5.0 (compatible; jobsammler-pruefung/0.1; einmaliger Regel-Check)"
S = requests.Session()
S.headers["User-Agent"] = UA
S.headers["Accept-Language"] = "de-DE,de;q=0.9"

CHECK = {
    # RSS-Feeds der Sender
    "ARD Programmdirektion RSS": "https://www.ard.de/die-ard/ard-programmdirektion/uebersicht-ard-programmdirektion-jobs-100~rss2.xml",
    "NDR Karriere RSS": "https://www.ndr.de/der_ndr/karriere/index~rss2.xml",
    "MDR Karriere RSS": "https://www.mdr.de/karriere/index~rss2.xml",
    "SWR Stellen RSS": "https://www.swr.de/~rss/unternehmen/karriere/stellenangebote-110.xml",
    "HR Karriere RSS": "https://www.hr.de/karriere/index.rss",
    "BR Karriere RSS": "https://www.br.de/extra/karriere/karriere-ausbildung-werkstudenten-duales-studium-jobs-stellenmarkt-stellenangebote-100~rss.xml",
    "Deutschlandradio RSS": "https://www.deutschlandradio.de/ausbildung-und-karriere-100.rss",
    "rbb Karriere RSS": "https://www.rbb-online.de/unternehmen/karriere/rss.html",
    "ZDF Karriere RSS": "https://www.zdf.de/rss/zdf/unternehmen/karriere",
    "newsroom Jobs RSS": "https://www.newsroom.de/rss/jobs-feed/",
    # SuccessFactors-Karriereseiten (RSS-Schnittstelle der Plattform)
    "ProSiebenSat.1 SF RSS": "https://jobs.prosiebensat1.com/services/rss/job/?locale=de_DE&keywords=moderator",
    "ProSiebenSat.1 SF RSS alle": "https://jobs.prosiebensat1.com/services/rss/job/?locale=de_DE",
    "RTL SF RSS": "https://jobsearch.createyourowncareer.com/RTL/services/rss/job/?locale=de_DE",
    "ZDF SF RSS": "https://jobs.zdf.de/services/rss/job/?locale=de_DE",
    # Personio (offizielle XML-Schnittstelle)
    "ZDF Digital Personio": "https://zdf-digital.jobs.personio.de/xml",
    "ITV Studios Germany Personio": "https://itv-studios-germany.jobs.personio.de/xml",
    "btf Personio": "https://btf-gmbh.jobs.personio.de/xml",
    # softgarden
    "Banijay softgarden": "https://banijay.softgarden.io/de/vacancies",
    "EndemolShine softgarden": "https://endemolshine.softgarden.io/de/vacancies",
    "Radio Bremen softgarden": "https://radiobremen.softgarden.io/de/vacancies",
    "SR softgarden": "https://srjobs.softgarden.io/de/vacancies",
    "Deutschlandradio softgarden": "https://deutschlandradio.softgarden.io/de/vacancies",
    # umantis (Abacus)
    "rbb umantis": "https://recruitingapp-5154.de.umantis.com/Jobs/All",
    "NDR umantis": "https://jobs.ndr.de/Jobs/All",
    "BR umantis": "https://jobs.br.de/Jobs/All",
    "MDR umantis": "https://recruitingapp-5280.de.umantis.com/Jobs/1?CompanyID=1",
    "ARD umantis": "https://recruitingapp-5685.de.umantis.com/Jobs/1",
    "WDR Bewerbung": "https://bewerbung.wdr.de/index.php?ac=search_result",
    # rexx
    "Raab rexx": "https://jobs.raab-entertainment.de/stellenangebote.html",
    "Raab rexx RSS": "https://jobs.raab-entertainment.de/stellenangebote.rss",
    # eigene Seiten
    "UFA Jobs": "https://www.ufa.de/karriere/jobs",
    "Brainpool Karriere": "https://brainpool.de/karriere/",
    "Constantin Karriere": "https://constantin-entertainment.de/karriere/",
    "Redseven Career": "https://www.redseven.de/career",
    "Bavaria Jobportal": "https://www.bavaria-film.de/jobportal",
    "Hyperbole Jobs": "https://www.hyperbole.de/jobs/",
    "Seapoint Jobs": "https://seapoint.de/jobs/",
    "Rocket Beans Jobs": "https://rocketbeans.tv/jobs",
    "funk Jobs": "https://www.funk.net/jobs",
    "EndemolShine Jobs": "https://endemolshine.de/jobs_category/alle/",
    "kress Stellenmarkt": "https://kress.de/jobs/stellenmarkt",
    "Crew United Jobs": "https://www.crew-united.com/de/jobs/",
    "Amazon Jobs JSON": "https://www.amazon.jobs/en/search.json?base_query=presenter&loc_query=Germany&result_limit=10",
    # andere Adressen für nicht erreichte Firmen
    "florida 1": "https://florida-tv.de",
    "florida 2": "https://www.florida.tv",
    "florida 3": "https://floridatv.de",
    "florida 4": "https://www.florida-entertainment.de",
    "i&u 1": "https://iundu.de",
    "i&u 2": "https://www.iundu-tv.de",
    "Mediakraft 2": "https://mediakraft.tv",
    "Mediakraft 3": "https://www.mediakraft.de",
}

ROBOTS = [
    "https://jobs.prosiebensat1.com", "https://jobsearch.createyourowncareer.com", "https://jobs.zdf.de",
    "https://banijay.softgarden.io", "https://recruitingapp-5154.de.umantis.com", "https://jobs.ndr.de",
    "https://jobs.br.de", "https://bewerbung.wdr.de", "https://jobs.raab-entertainment.de", "https://www.ufa.de",
    "https://www.crew-united.com", "https://www.etalenta.eu", "https://www.filmmakers.eu", "https://kress.de",
    "https://www.newsroom.de", "https://www.amazon.jobs", "https://careers.wbd.com", "https://join.disneycareers.com",
    "https://zdf-digital.jobs.personio.de", "https://www.ard.de", "https://www.swr.de", "https://www.ndr.de",
    "https://www.mdr.de", "https://www.hr.de", "https://www.br.de", "https://www.deutschlandradio.de",
    "https://www.rbb-online.de", "https://www.zdf.de", "https://endemolshine.de", "https://brainpool.de",
    "https://constantin-entertainment.de", "https://www.redseven.de",
]

TERMS = {
    "Crew United AGB": "https://www.crew-united.com/de/home/agb.asp",
    "newsroom Nutzungsbedingungen": "https://www.newsroom.de/nutzungsbedingungen/",
    "newsroom AGB": "https://www.newsroom.de/agb/",
    "e-TALENTA AGB": "https://www.etalenta.eu/de/agb/",
    "filmmakers AGB": "https://www.filmmakers.eu/de/terms_of_service",
    "kress AGB": "https://kress.de/rechtliches-hilfe/agb",
    "softgarden Nutzungsbedingungen": "https://softgarden.com/de/nutzungsbedingungen/",
    "Arbeitnow Terms": "https://www.arbeitnow.com/terms",
    "Amazon Jobs Terms": "https://www.amazon.jobs/en/terms",
    "UFA Impressum": "https://www.ufa.de/impressum",
    "EndemolShine AGB": "https://endemolshine.de/agb/",
    "ProSiebenSat.1 Impressum": "https://www.prosiebensat1.com/impressum",
    "RTL Impressum company": "https://company.rtl.com/de/impressum/",
}
HIT = re.compile(
    r"[^.\n]{0,300}(?:automatisiert|automatische|crawl|scrap|spider|robot|\bbots?\b|data.?mining|maschinell|"
    r"auslese|systematisch|harvest|rss|feed|herunterlad|vervielfältig|datenbank)[^.\n]{0,300}",
    re.I,
)


def text_of(html):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t)


def titles(body, ctype):
    if "<rss" in body[:500] or "<feed" in body[:500] or "xml" in ctype:
        items = re.findall(r"<item\b.*?</item>|<entry\b.*?</entry>|<position\b.*?</position>", body, re.S)
        out = []
        for it in items:
            m = re.search(r"<title[^>]*>(.*?)</title>|<name>(.*?)</name>", it, re.S)
            if m:
                out.append(re.sub(r"<!\[CDATA\[|\]\]>", "", (m.group(1) or m.group(2) or "")).strip()[:120])
        return len(items), out
    if "json" in ctype:
        try:
            d = json.loads(body)
            jobs = d.get("jobs") or []
            return d.get("hits", len(jobs)), [f"{j.get('title')} | {j.get('location')}" for j in jobs[:15]]
        except Exception:  # noqa: BLE001
            return None, []
    # HTML: Links, die nach einzelnen Stellen aussehen
    links = re.findall(r"""<a\b[^>]*href=["']([^"']+)["'][^>]*>(.*?)</a>""", body, re.S | re.I)
    jobs = []
    for href, lab in links:
        if re.search(r"/job/|/jobs/\d|vacanc|stellenangebot|Description|jobposting|/stellen/|career/\w|jobdetail|job-details|/position", href, re.I):
            t = text_of(lab).strip()
            if t and len(t) > 4:
                jobs.append(f"{t[:90]} -> {href[:120]}")
    return len(jobs), list(dict.fromkeys(jobs))


BA = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
BA_TERMS = ["Moderator/in", "TV-Moderator", "Fernsehmoderator", "Radiomoderation", "Hörfunk Moderation",
            "Eventmoderator", "Showmoderator", "Moderator Hörfunk Fernsehen", "Sprecher/in (Fernsehen/Film/Rundfunk)",
            "Entertainer/in", "Darsteller", "Model", "Fotomodell", "Host TV", "Live Host", "Game Master",
            "Redaktionsleitung", "Chef vom Dienst", "Showrunner", "Producer Entertainment", "Formatentwickler",
            "Hörfunkjournalist", "Fernsehjournalist", "Reporter TV", "Volontariat Moderation", "Unterhaltung"]


def ba_tests():
    res = {}
    for term in BA_TERMS:
        for mode, extra in (("de", {}), ("berufsfeld", {"berufsfeld": term})):
            time.sleep(0.6)
            params = {"size": 50, "angebotsart": 1, **({"was": term} if mode == "de" else extra)}
            try:
                r = S.get(BA, params=params, headers={"X-API-Key": "jobboerse-jobsuche"}, timeout=25)
                d = r.json() if r.status_code == 200 else {}
                res[f"{term} | {mode}"] = {"status": r.status_code, "treffer": d.get("maxErgebnisse"), "beispiele": [
                    f"{j.get('stellenangebotsTitel')} | {j.get('firma')} | "
                    f"{', '.join((l.get('adresse') or {}).get('ort', '') for l in j.get('stellenlokationen') or [])} | {j.get('hauptberuf', '')}"
                    for j in (d.get('ergebnisliste') or [])[:20]]}
            except Exception as exc:  # noqa: BLE001
                res[f"{term} | {mode}"] = {"fehler": str(exc)[:200]}
    # freie Mitarbeit / selbständig
    for term in ["Moderator", "Moderation", "Sprecher", "Host", "Model"]:
        time.sleep(0.6)
        try:
            r = S.get(BA, params={"was": term, "size": 30, "angebotsart": 2}, headers={"X-API-Key": "jobboerse-jobsuche"}, timeout=25)
            d = r.json() if r.status_code == 200 else {}
            res[f"{term} | selbstaendig"] = {"status": r.status_code, "treffer": d.get("maxErgebnisse"),
                                            "beispiele": [f"{j.get('stellenangebotsTitel')} | {j.get('firma')}" for j in (d.get('ergebnisliste') or [])[:15]]}
        except Exception as exc:  # noqa: BLE001
            res[f"{term} | selbstaendig"] = {"fehler": str(exc)[:200]}
    return res


def main():
    out = {"zeit": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "check": {}, "robots": {}, "terms": {}}
    for name, url in CHECK.items():
        time.sleep(0.8)
        print("prüfe", name, flush=True)
        try:
            r = S.get(url, timeout=25)
            body = r.text[:3_000_000]
            ctype = r.headers.get("content-type", "")
            n, ts = titles(body, ctype)
            hosts = sorted(set(re.findall(r"https?://([\w.-]+)", body)))
            feeds = sorted(set(re.findall(r"""["']([^"']*(?:rss|feed|\.xml|atom)[^"']*)["']""", body, re.I)))[:15]
            out["check"][name] = {"url": url, "final": r.url, "status": r.status_code, "ctype": ctype, "laenge": len(body),
                                  "anzahl": n, "titel": ts[:25], "hosts": hosts[:60], "feeds": feeds,
                                  "anfang": text_of(body)[:400] if not ts else ""}
        except Exception as exc:  # noqa: BLE001
            out["check"][name] = {"url": url, "fehler": str(exc)[:200]}
    for base in ROBOTS:
        time.sleep(0.5)
        try:
            r = S.get(base + "/robots.txt", timeout=20)
            out["robots"][base] = {"status": r.status_code, "text": r.text[:4000] if r.status_code == 200 else ""}
        except Exception as exc:  # noqa: BLE001
            out["robots"][base] = {"fehler": str(exc)[:200]}
    for name, url in TERMS.items():
        time.sleep(0.8)
        try:
            r = S.get(url, timeout=25)
            txt = text_of(r.text)
            out["terms"][name] = {"url": url, "final": r.url, "status": r.status_code,
                                  "treffer": [m.group(0).strip() for m in HIT.finditer(txt)][:12]}
        except Exception as exc:  # noqa: BLE001
            out["terms"][name] = {"url": url, "fehler": str(exc)[:200]}
    out["ba"] = ba_tests()
    (HERE / "ergebnis").mkdir(exist_ok=True)
    (HERE / "ergebnis" / "bericht2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("fertig")


if __name__ == "__main__":
    main()
