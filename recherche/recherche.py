"""Einmalige Recherche für Initiativbewerbungen.

Liest pro Kandidat die offiziellen Seiten (Start, Impressum, Kontakt, Karriere, Casting, Produktionen/Formate),
nur wenn robots.txt es erlaubt. Sammelt: Titel/Beschreibung, E-Mail-Adressen (mit Fundstelle),
Textstellen rund um "Casting", "Ansprechpartner", "Bewerbung", "Initiativ", "Moderator", "Talent",
und Überschriften/Linktexte der Produktionen-Seiten (Formatnamen).
Ergebnis: recherche/ergebnis.json
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
UA = "Mozilla/5.0 (compatible; jobsammler/1.0; private Recherche)"
S = requests.Session()
S.headers["User-Agent"] = UA
S.headers["Accept-Language"] = "de-DE,de;q=0.9"
ROBOTS = {}

LINK_KIND = [
    ("impressum", r"impressum|imprint"),
    ("kontakt", r"kontakt|contact"),
    ("karriere", r"karriere|career|jobs|stellen|join|team-werden|mitarbeit"),
    ("casting", r"casting|bewirb|mitmachen|kandidat|talent"),
    ("produktionen", r"produktion|production|formate|formats|shows|portfolio|programm|sendungen|brands|work|projekte"),
    ("team", r"team|ueber-uns|uber-uns|about|wir"),
]
KEYS = re.compile(r"casting|ansprechpartner|ansprechpartnerin|bewerbung|initiativ|moderator|moderation|talent|"
                  r"showreel|redaktion|unterhaltung|entertainment|kontaktperson|head of|leitung", re.I)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+\s?(?:@|\[at\]|\(at\)| at )\s?[A-Za-z0-9.-]+\s?(?:\.|\[dot\]|\(dot\))\s?[A-Za-z]{2,}")


def allowed(url):
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in ROBOTS:
        rp = RobotFileParser()
        try:
            r = S.get(base + "/robots.txt", timeout=20)
            if r.status_code in (401, 403):
                rp.disallow_all = True
            elif r.status_code >= 400:
                rp.allow_all = True
            else:
                rp.parse(r.text.splitlines())
        except Exception:  # noqa: BLE001
            rp.allow_all = True
        ROBOTS[base] = rp
    return ROBOTS[base].can_fetch("jobsammler", url)


def get(url):
    time.sleep(1.0)
    if not allowed(url):
        return None, "robots.txt verbietet"
    try:
        r = S.get(url, timeout=25)
        return r, ""
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)[:150]


def text_of(html):
    t = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    t = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>|</div>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    import html as h
    t = h.unescape(t)
    t = re.sub(r"[ \t\xa0]+", " ", t)
    return re.sub(r"\s*\n\s*", "\n", t)


def emails(html, text):
    found = set(re.findall(r"mailto:([^\"'?>\s]+)", html, re.I))
    for m in EMAIL.finditer(text):
        e = re.sub(r"\s?(\[at\]|\(at\)| at )\s?", "@", m.group(0))
        e = re.sub(r"\s?(\[dot\]|\(dot\))\s?", ".", e).replace(" ", "")
        found.add(e)
    return sorted(e.strip(".,;") for e in found if "@" in e and not e.endswith((".png", ".jpg", ".svg", ".webp")))


def snippets(text):
    out = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for i, l in enumerate(lines):
        if KEYS.search(l) and len(l) < 400:
            ctx = " / ".join(lines[max(0, i - 1):i + 3])
            if ctx not in out:
                out.append(ctx[:400])
    return out[:25]


def headings(html):
    hs = [re.sub(r"<[^>]+>", " ", x) for x in re.findall(r"(?is)<h[1-4][^>]*>(.*?)</h[1-4]>", html)]
    import html as h
    hs = [re.sub(r"\s+", " ", h.unescape(x)).strip() for x in hs]
    return [x for x in dict.fromkeys(hs) if 2 < len(x) < 90][:60]


def research(name, url):
    res = {"name": name, "start": url, "seiten": {}}
    r, err = get(url)
    if r is None:
        res["fehler"] = err
        return res
    res["status"] = r.status_code
    res["final"] = r.url
    html = r.text[:3_000_000]
    t = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    d = re.search(r'(?is)<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', html)
    res["titel"] = re.sub(r"\s+", " ", t.group(1)).strip()[:150] if t else ""
    res["beschreibung"] = d.group(1).strip()[:300] if d else ""
    text = text_of(html)
    res["seiten"]["start"] = {"url": r.url, "emails": emails(html, text), "stellen": snippets(text)[:10],
                              "ueberschriften": headings(html)[:30]}
    links = []
    for href, label in re.findall(r"""(?is)<a\b[^>]*href=["']([^"'#]+)["'][^>]*>(.*?)</a>""", html):
        full = urljoin(r.url, href.strip())
        if not full.startswith("http") or urlparse(full).netloc.split(".")[-2:] != urlparse(r.url).netloc.split(".")[-2:]:
            continue
        links.append((full, re.sub(r"<[^>]+>", " ", label).strip().lower()))
    used = {r.url}
    for kind, rx in LINK_KIND:
        cand = [f for f, lab in links if re.search(rx, urlparse(f).path.lower() + " " + lab)]
        cand = [c for c in dict.fromkeys(cand) if c not in used][:2 if kind in ("produktionen", "casting") else 1]
        for c in cand:
            used.add(c)
            r2, err2 = get(c)
            if r2 is None or r2.status_code != 200:
                res["seiten"][f"{kind}:{c}"] = {"fehler": err2 or f"HTTP {r2.status_code if r2 else ''}"}
                continue
            h2 = r2.text[:3_000_000]
            t2 = text_of(h2)
            res["seiten"][f"{kind}:{c}"] = {"url": r2.url, "emails": emails(h2, t2), "stellen": snippets(t2),
                                            "ueberschriften": headings(h2) if kind in ("produktionen", "casting", "team") else []}
    return res


def main():
    cands = yaml.safe_load((HERE / "kandidaten.yaml").read_text(encoding="utf-8"))
    out = {"zeit": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "kandidaten": {}}
    for gruppe, items in cands.items():
        for name, url in items:
            print("recherche", name, flush=True)
            try:
                out["kandidaten"][name] = {"gruppe": gruppe, **research(name, url)}
            except Exception as exc:  # noqa: BLE001
                out["kandidaten"][name] = {"gruppe": gruppe, "fehler": f"Absturz: {exc}"[:200]}
    (HERE / "ergebnis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("fertig")


if __name__ == "__main__":
    main()
