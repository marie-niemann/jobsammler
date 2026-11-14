"""Einmalige Prüfung: radioszene.de und dwdl.de (Jobs, Feeds, robots.txt, Nutzungsbedingungen)."""
import json, re, time
from pathlib import Path
from urllib.parse import urljoin
import requests

HERE = Path(__file__).resolve().parent
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (compatible; jobsammler/1.0; einmaliger Regel-Check)"
SITES = {"radioszene": "https://www.radioszene.de", "dwdl": "https://www.dwdl.de"}
HIT = re.compile(r"[^.\n]{0,250}(?:automatisiert|crawl|scrap|spider|robot|\bbots?\b|data.?mining|rss|feed|auslese|systematisch|vervielfältig)[^.\n]{0,250}", re.I)

def g(u):
    time.sleep(1)
    try:
        r = S.get(u, timeout=25); return r
    except Exception as e:
        return e

def txt(h):
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", h); return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))

out = {}
for k, base in SITES.items():
    res = {}
    r = g(base + "/robots.txt"); res["robots"] = r.text[:4000] if not isinstance(r, Exception) else str(r)
    r = g(base)
    if isinstance(r, Exception):
        res["fehler"] = str(r); out[k] = res; continue
    h = r.text
    res["feeds"] = sorted(set(urljoin(r.url, m) for m in re.findall(r"""<link[^>]+type=["']application/(?:rss|atom)\+xml["'][^>]*href=["']([^"']+)""", h, re.I)))
    links = [(urljoin(r.url, a), txt(b).strip()) for a, b in re.findall(r"""(?is)<a\b[^>]*href=["']([^"'#]+)["'][^>]*>(.*?)</a>""", h)]
    res["job_links"] = list(dict.fromkeys(a for a, b in links if re.search(r"job|stellen|karriere|markt", a + " " + b, re.I)))[:15]
    res["rechts_links"] = list(dict.fromkeys(a for a, b in links if re.search(r"agb|nutzungsbeding|impressum|terms|rechtlich", a + " " + b, re.I)))[:5]
    res["jobseiten"] = {}
    for u in res["job_links"][:4]:
        r2 = g(u)
        if isinstance(r2, Exception): res["jobseiten"][u] = str(r2); continue
        h2 = r2.text
        f2 = sorted(set(urljoin(r2.url, m) for m in re.findall(r"""(?:href|src)=["']([^"']*(?:rss|feed|\.xml)[^"']*)""", h2, re.I)))
        titles = [txt(b).strip()[:100] for a, b in re.findall(r"""(?is)<a\b[^>]*href=["']([^"'#]+)["'][^>]*>(.*?)</a>""", h2) if re.search(r"/job|stellen|anzeige", a, re.I)]
        res["jobseiten"][u] = {"status": r2.status_code, "final": r2.url, "feeds": f2[:10], "beispiele": [t for t in dict.fromkeys(titles) if t][:25],
                               "hosts": sorted(set(re.findall(r"https?://([\w.-]+)", h2)))[:40]}
    for f in res["feeds"][:4] + [x for v in res["jobseiten"].values() if isinstance(v, dict) for x in v["feeds"] if "job" in x.lower()][:4]:
        r3 = g(f)
        if not isinstance(r3, Exception):
            res.setdefault("feed_inhalt", {})[f] = {"status": r3.status_code, "titel": re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", r3.text)[:12]}
    res["regeln"] = {}
    for u in res["rechts_links"][:3]:
        r4 = g(u)
        if not isinstance(r4, Exception): res["regeln"][u] = [m.group(0).strip() for m in HIT.finditer(txt(r4.text))][:10]
    out[k] = res
(HERE / "check_boersen.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("fertig")
