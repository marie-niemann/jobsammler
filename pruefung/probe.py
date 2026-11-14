"""Einmaliger Prüf-Lauf: Welche Quellen gibt es, und was erlauben sie?

Besucht jede Seite aus ziele.yaml einmal, sucht die Karriereseite, erkennt das Bewerbungssystem,
liest robots.txt und sucht in Nutzungsbedingungen/AGB/Impressum nach Regeln zu automatischem Abruf.
Testet außerdem die Jobsuche der Arbeitsagentur und Arbeitnow mit ein paar Suchbegriffen.
Ergebnis: pruefung/ergebnis/bericht.json
"""

import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
import yaml

HERE = Path(__file__).resolve().parent
OUT = HERE / "ergebnis"
UA = "Mozilla/5.0 (compatible; jobsammler-pruefung/0.1; einmaliger Regel-Check)"
S = requests.Session()
S.headers["User-Agent"] = UA
S.headers["Accept-Language"] = "de-DE,de;q=0.9,en;q=0.5"

ATS = {
    "greenhouse": r"greenhouse\.io/[\w/?=.-]*",
    "lever": r"jobs\.(?:eu\.)?lever\.co/[\w.-]+",
    "ashby": r"ashbyhq\.com/[\w.%-]+",
    "personio": r"[\w-]+\.jobs\.personio\.(?:de|com)",
    "workable": r"apply\.workable\.com/[\w-]+",
    "smartrecruiters": r"(?:jobs|careers)\.smartrecruiters\.com/[\w-]+",
    "softgarden": r"[\w.-]+\.softgarden\.(?:io|de)",
    "dvinci": r"[\w.-]+\.dvinci(?:-hr)?\.(?:com|de)",
    "rexx": r"[\w.-]*rexx-(?:systems|recruitment)\.com[\w/.-]*",
    "successfactors": r"[\w.-]*(?:successfactors\.(?:com|eu)|sapsf\.(?:com|eu))[\w/?=.-]*",
    "workday": r"[\w.-]+\.myworkdayjobs\.com[\w/.-]*",
    "recruitee": r"[\w-]+\.recruitee\.com",
    "teamtailor": r"[\w-]+\.teamtailor\.com",
    "join": r"join\.com/companies/[\w-]+",
    "onlyfy": r"[\w.-]*(?:onlyfy\.jobs|prescreen\.io)[\w/.-]*",
    "umantis": r"[\w.-]*umantis\.com[\w/?=.-]*",
    "interamt": r"interamt\.de[\w/?=.-]*",
    "bite": r"[\w.-]*b-ite\.(?:de|com|net)[\w/.-]*",
    "concludis": r"[\w.-]*concludis\.de[\w/.-]*",
    "mhm": r"[\w.-]*mhm-portal\.de[\w/.-]*",
    "pitchyou": r"pitchyou\.de[\w/.-]*",
    "hrworks": r"[\w.-]*hrworks\.de[\w/.-]*",
    "jobbase": r"[\w.-]*jobbase\.io[\w/.-]*",
    "taleo": r"[\w.-]*taleo\.net[\w/.-]*",
    "icims": r"[\w.-]*icims\.com[\w/.-]*",
    "phenom": r"[\w.-]*phenompeople\.com[\w/.-]*",
    "eightfold": r"[\w.-]*eightfold\.ai[\w/.-]*",
}
CAREER_LINK = re.compile(r"karriere|career|jobs?\b|jobs/|stellen|stellenangebot|arbeiten-bei|work-with-us|join-us|mitarbeit", re.I)
TERMS_LINK = re.compile(r"nutzungsbedingung|\bagb\b|terms|impressum|imprint|rechtliche|legal|disclaimer", re.I)
TERMS_HIT = re.compile(
    r"[^.\n]{0,250}(?:automatisiert|automatische[nrs]? (?:abruf|auslese|zugriff|erfass)|crawl|scrap|spider|robot\b|bots?\b|"
    r"data.?mining|text.?und.?data|tdm|maschinell|systematisch\w* (?:abruf|auslese|erfass|kopie)|auslesen|harvest)[^.\n]{0,250}",
    re.I,
)
FEED = re.compile(r"""<link[^>]+type=["']application/(?:rss|atom)\+xml["'][^>]*>""", re.I)
HREF = re.compile(r"""(?:href|src|action)\s*=\s*["']([^"'#]+)["']""", re.I)
ANCHOR = re.compile(r"""<a\b[^>]*href\s*=\s*["']([^"'#]+)["'][^>]*>(.*?)</a>""", re.I | re.S)

robots_cache = {}


def get(url, **kw):
    time.sleep(0.8)
    try:
        r = S.get(url, timeout=25, allow_redirects=True, **kw)
        return r
    except Exception as exc:  # noqa: BLE001
        return exc


def robots(host_url):
    p = urlparse(host_url)
    base = f"{p.scheme}://{p.netloc}"
    if base in robots_cache:
        return robots_cache[base]
    r = get(base + "/robots.txt")
    if isinstance(r, Exception):
        info = {"status": f"Fehler: {r}"[:200]}
    else:
        txt = r.text if r.status_code == 200 else ""
        info = {"status": r.status_code, "text": txt[:6000]}
    robots_cache[base] = info
    return info


def allowed(url):
    p = urlparse(url)
    info = robots(url)
    txt = info.get("text")
    if not txt:
        return None
    rp = RobotFileParser()
    rp.parse(txt.splitlines())
    return {"*": rp.can_fetch("*", url), "jobsammler": rp.can_fetch("jobsammler", url)}


def ats_hits(html):
    hits = {}
    for name, rx in ATS.items():
        for m in re.finditer(rx, html, re.I):
            hits.setdefault(name, set()).add(m.group(0)[:150])
    return {k: sorted(v)[:8] for k, v in hits.items()}


def text_of(html):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t)


def probe(name, url):
    res = {"name": name, "start": url, "seiten": [], "ats": {}, "feeds": [], "regeln": [], "robots": {}}
    r = get(url)
    if isinstance(r, Exception):
        res["fehler"] = str(r)[:300]
        return res
    res["status"] = r.status_code
    res["final"] = r.url
    html = r.text[:2_000_000]
    pages = [(r.url, html)]
    links = []
    for href, label in ANCHOR.findall(html):
        full = urljoin(r.url, href.strip())
        lab = text_of(label)[:80]
        if full.startswith("http"):
            links.append((full, lab))
    career = []
    for full, lab in links:
        if CAREER_LINK.search(full) or CAREER_LINK.search(lab):
            if full not in [c[0] for c in career]:
                career.append((full, lab))
    res["karriere_links"] = career[:15]
    for full, _ in career[:3]:
        if full == r.url:
            continue
        r2 = get(full)
        if isinstance(r2, Exception):
            res["seiten"].append({"url": full, "fehler": str(r2)[:200]})
            continue
        res["seiten"].append({"url": full, "final": r2.url, "status": r2.status_code, "titel": (re.search(r"<title[^>]*>(.*?)</title>", r2.text, re.I | re.S) or [None, ""])[1].strip()[:120]})
        pages.append((r2.url, r2.text[:2_000_000]))
        # eine Ebene tiefer: Link zu "alle Stellen"/"Stellenangebote"
        for href, label in ANCHOR.findall(r2.text):
            f3 = urljoin(r2.url, href.strip())
            if re.search(r"stellenangebot|offene stellen|alle (?:jobs|stellen)|jobbörse|job ?search|jobsuche|open positions|vacancies", text_of(label) + " " + f3, re.I):
                if f3.startswith("http") and f3 not in [p[0] for p in pages] and len(pages) < 7:
                    r3 = get(f3)
                    if not isinstance(r3, Exception):
                        res["seiten"].append({"url": f3, "final": r3.url, "status": r3.status_code})
                        pages.append((r3.url, r3.text[:2_000_000]))
                    break
    hosts = set()
    for purl, phtml in pages:
        for k, v in ats_hits(phtml).items():
            res["ats"].setdefault(k, [])
            res["ats"][k] = sorted(set(res["ats"][k]) | set(v))[:8]
        for f in FEED.findall(phtml):
            m = re.search(r"""href=["']([^"']+)""", f)
            if m:
                res["feeds"].append(urljoin(purl, m.group(1)))
        for h in HREF.findall(phtml):
            if re.search(r"rss|feed|\.xml|atom", h, re.I) and re.search(r"job|stell|karriere|career", h, re.I):
                res["feeds"].append(urljoin(purl, h))
        hosts.add(urlparse(purl).netloc)
        for h in HREF.findall(phtml):
            full = urljoin(purl, h)
            if full.startswith("http") and CAREER_LINK.search(full):
                hosts.add(urlparse(full).netloc)
    res["feeds"] = sorted(set(res["feeds"]))[:10]
    res["job_hosts"] = sorted(hosts)[:25]
    for purl, _ in pages:
        res["robots"][purl] = allowed(purl)
    for base in {f"{urlparse(p).scheme}://{urlparse(p).netloc}" for p, _ in pages}:
        info = robots(base)
        res.setdefault("robots_txt", {})[base] = info
    # Nutzungsbedingungen / Impressum
    terms = []
    for full, lab in links:
        if TERMS_LINK.search(full) or TERMS_LINK.search(lab):
            if full not in terms:
                terms.append(full)
    for t in terms[:3]:
        r4 = get(t)
        if isinstance(r4, Exception) or r4.status_code != 200:
            continue
        txt = text_of(r4.text)
        hits = [m.group(0).strip() for m in TERMS_HIT.finditer(txt)][:6]
        res["regeln"].append({"url": t, "treffer": hits})
    return res


BA = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
BA_TERMS = ["Moderator", "Moderatorin", "Moderation", "Radiomoderator", "Sprecher", "Sprecherin", "Host",
            "Presenter", "Entertainer", "Casting", "Redakteur Moderation", "Showredaktion", "Formatentwicklung",
            "Video Host", "Model", "Komparse", "Werbespot"]


def ba_tests():
    out = {}
    for term in BA_TERMS:
        for mode, extra in (("berlin", {"wo": "Berlin", "umkreis": 25}), ("de", {})):
            time.sleep(0.6)
            try:
                r = S.get(BA, params={"was": term, "size": 25, **extra}, headers={"X-API-Key": "jobboerse-jobsuche"}, timeout=25)
                d = r.json() if r.status_code == 200 else {}
                items = d.get("ergebnisliste") or []
                out[f"{term} | {mode}"] = {
                    "status": r.status_code,
                    "treffer": d.get("maxErgebnisse"),
                    "beispiele": [
                        f"{j.get('stellenangebotsTitel')} | {j.get('firma')} | "
                        f"{', '.join((l.get('adresse') or {}).get('ort', '') for l in j.get('stellenlokationen') or [])} | "
                        f"{j.get('hauptberuf', '')} | Art {j.get('angebotsart', '')}"
                        for j in items[:25]
                    ],
                }
            except Exception as exc:  # noqa: BLE001
                out[f"{term} | {mode}"] = {"fehler": str(exc)[:200]}
    # auch freie Mitarbeit / Selbständigkeit (angebotsart 2?) testen
    for art in (1, 2, 4, 34):
        time.sleep(0.6)
        try:
            r = S.get(BA, params={"was": "Moderator", "size": 10, "angebotsart": art}, headers={"X-API-Key": "jobboerse-jobsuche"}, timeout=25)
            d = r.json() if r.status_code == 200 else {}
            out[f"angebotsart {art}"] = {"status": r.status_code, "treffer": d.get("maxErgebnisse"),
                                         "beispiele": [j.get("stellenangebotsTitel") for j in (d.get("ergebnisliste") or [])[:10]]}
        except Exception as exc:  # noqa: BLE001
            out[f"angebotsart {art}"] = {"fehler": str(exc)[:200]}
    return out


def arbeitnow_test():
    r = get("https://www.arbeitnow.com/api/job-board-api")
    if isinstance(r, Exception):
        return {"fehler": str(r)[:200]}
    try:
        d = r.json()
    except Exception:  # noqa: BLE001
        return {"status": r.status_code, "text": r.text[:500]}
    titles = [j.get("title") for j in d.get("data") or []]
    media = [t for t in titles if re.search(r"modera|host|present|redak|editor|video|media|content|creator", t or "", re.I)]
    return {"status": r.status_code, "meta_keys": [k for k in d if k != "data"], "meta": {k: d[k] for k in d if k not in ("data",)},
            "anzahl_seite1": len(titles), "medien_titel": media}


def raw_texts():
    """Einige Dokumente, deren Text wir direkt brauchen."""
    urls = [
        "https://raw.githubusercontent.com/bundesAPI/jobsuche-api/main/README.md",
        "https://raw.githubusercontent.com/bundesAPI/jobsuche-api/main/openapi.yaml",
        "https://jobsuche.api.bund.dev/",
        "https://www.arbeitnow.com/api",
    ]
    out = {}
    for u in urls:
        r = get(u)
        if isinstance(r, Exception):
            out[u] = {"fehler": str(r)[:200]}
            continue
        t = r.text
        if "openapi" in u:
            t = "\n".join(l for l in t.splitlines() if re.search(r"(?i)terms|nutzung|licen|bedingung|description", l))
        elif "<html" in t[:500].lower():
            t = text_of(t)
        out[u] = {"status": r.status_code, "text": t[:5000]}
    return out


def main():
    OUT.mkdir(exist_ok=True)
    ziele = yaml.safe_load((HERE / "ziele.yaml").read_text(encoding="utf-8"))
    bericht = {"zeit": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "quellen": {}}
    for gruppe, items in ziele.items():
        for name, url in items:
            print("prüfe", name, url, flush=True)
            try:
                bericht["quellen"][name] = {"gruppe": gruppe, **probe(name, url)}
            except Exception as exc:  # noqa: BLE001
                bericht["quellen"][name] = {"gruppe": gruppe, "fehler": f"Absturz: {exc}"[:300]}
    print("BA-Tests", flush=True)
    bericht["ba"] = ba_tests()
    bericht["ba_robots"] = {u: robots(u) for u in ("https://rest.arbeitsagentur.de", "https://www.arbeitsagentur.de")}
    print("Arbeitnow", flush=True)
    bericht["arbeitnow"] = arbeitnow_test()
    bericht["texte"] = raw_texts()
    (OUT / "bericht.json").write_text(json.dumps(bericht, ensure_ascii=False, indent=1), encoding="utf-8")
    print("fertig")


if __name__ == "__main__":
    main()
