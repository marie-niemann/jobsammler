"""Stellen von Sendern, Produktionsfirmen und Jobbörsen (config/companies.yaml, Teil "quellen").

Arten:
  rss             RSS-Feed (z. B. newsroom.de, Karriere-Feeds der Sender)
  personio        offizielle Personio-XML-Schnittstelle; falls abgeschaltet, die öffentliche Personio-Stellenseite
  softgarden      öffentliche softgarden-Stellenliste (/de/vacancies; /api/ und /widgets/ sind per robots.txt gesperrt)
  umantis         öffentliche umantis-Stellenliste (/Jobs/All, 10 Stellen pro Seite)
  successfactors  öffentliche Stellensuche (/search/; der RSS-Bereich /services/ ist per robots.txt gesperrt)
  ufa             Stellenliste auf ufa.de
  hr              Stellenliste auf hr.de

Vor jedem Abruf wird die robots.txt geprüft. Verbietet sie den Abruf, wird die Quelle übersprungen.
"""

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urljoin, urlparse

from .common import PoliteSession, clean, record, to_text

MAX_PAGES = 20


class NotAllowed(Exception):
    pass


def _get(sess, url):
    if not sess.allowed(url):
        raise NotAllowed(url)
    r = sess.get(url)
    r.raise_for_status()
    return r


def _day(value):
    if not value:
        return ""
    v = str(value).strip()
    try:
        if v.isdigit():
            return datetime.fromtimestamp(int(v), tz=timezone.utc).strftime("%Y-%m-%d")
        if re.match(r"\d{4}-\d{2}-\d{2}", v):
            return v[:10]
        m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", v)
        if m:
            y = int(m.group(3))
            return f"{y + 2000 if y < 100 else y:04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
        return parsedate_to_datetime(v).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return ""


# ---------- je Art: liefert Liste von (Eintrag, [Orte], remote_flag) ----------

def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _child(el, *names):
    """Text des ersten Kind-Elements mit einem dieser Namen (egal welcher Namensraum)."""
    for c in el:
        if _local(c.tag) in names:
            if _local(c.tag) == "link" and not (c.text or "").strip():
                return c.get("href", "")
            return c.text or ""
    return ""


def _split_sucht(title, q):
    """Jobbörsen schreiben oft "Firma sucht Stelle". Dann Firma und Titel trennen."""
    title = clean(title)
    if q.get("firma_aus_titel") and " sucht " in title:
        firma, rest = title.split(" sucht ", 1)
        return rest.strip(), firma.strip()
    return title, q.get("firma") or q["name"]


def _rss(sess, q):
    """RSS 2.0, RSS 1.0 (RDF) und Atom."""
    r = _get(sess, q["url"])
    root = ET.fromstring(r.content)
    out = []
    for it in root.iter():
        if _local(it.tag) not in ("item", "entry"):
            continue
        link = (_child(it, "link") or it.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about", "")).strip()
        jid = it.get("id") or _child(it, "guid", "id") or link
        title, firma = _split_sucht(_child(it, "title"), q)
        rec = record(q["name"], jid, firma, title, link,
                     published=_day(_child(it, "pubDate", "date", "updated", "published")),
                     description=to_text(_child(it, "description", "summary")))
        city = _child(it, "city")
        out.append((rec, [city] if city else ([q["ort"]] if q.get("ort") else []), False))
    return out


def _personio(sess, q):
    url = q["url"]
    r = sess.get(url) if sess.allowed(url) else None
    if r is not None and r.status_code == 200 and b"<workzag-jobs" in r.content[:500]:
        out = []
        host = urlparse(url).netloc
        for p in ET.fromstring(r.content).findall("position"):
            pid = p.findtext("id")
            locs = [p.findtext("office") or ""] + [o.text or "" for o in p.findall("additionalOffices/office")]
            desc = "\n".join(f"{d.findtext('name') or ''}\n{d.findtext('value') or ''}"
                             for d in p.findall("jobDescriptions/jobDescription"))
            rec = record(q["name"], pid, q["name"], p.findtext("name"), f"https://{host}/job/{pid}",
                         published=_day(p.findtext("createdAt")), description=to_text(desc),
                         art=" ".join(filter(None, [p.findtext("employmentType"), p.findtext("schedule")])))
            out.append((rec, [l for l in locs if l] or ([q["ort"]] if q.get("ort") else []), False))
        return out
    # XML abgeschaltet: öffentliche Stellenseite lesen
    page = url.rsplit("/xml", 1)[0] + "/"
    body = _get(sess, page).text
    out = []
    for m in re.finditer(r'<a[^>]*href="(/job/(\d+))"[^>]*>(.*?)</a>', body, re.S):
        inner = m.group(3)
        title = re.search(r'jb-title">([^<]*)<', inner)
        metas = [clean(x) for x in re.findall(r'jobMetaText[^"]*">([^<]*)<', inner)]
        if not title:
            continue
        rec = record(q["name"], m.group(2), q["name"], title.group(1), urljoin(page, m.group(1)),
                     art=" ".join(metas[1:2]))
        out.append((rec, metas[:1] or ([q["ort"]] if q.get("ort") else []), False))
    return out


def _softgarden(sess, q):
    body = _get(sess, q["url"]).text
    out = []
    for block in re.split(r'<div class="matchElement" id="job_id_', body)[1:]:
        jid = re.match(r"(\d+)", block).group(1)
        a = re.search(r'<a href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not a:
            continue
        date = re.search(r'matchValue date">([^<]*)<', block)
        locs = [clean(x) for x in re.findall(r'location-view-item">([^<]*)<', block)]
        aud = re.search(r'matchValue audience">([^<]*)<', block)
        rec = record(q["name"], jid, q["name"], a.group(2), urljoin(q["url"], html.unescape(a.group(1)).split("?")[0]),
                     published=_day(date.group(1) if date else ""), art=clean(aud.group(1)) if aud else "")
        out.append((rec, locs or ([q["ort"]] if q.get("ort") else []), False))
    return out


def _umantis(sess, q):
    url, out, seen = q["url"], [], set()
    for _ in range(MAX_PAGES):
        body = _get(sess, url).text
        new = 0
        for m in re.finditer(r'href="(/Vacancies/(\d+)/Description/\d+)"[^>]*>([^<]*)</a>', body):
            jid = m.group(2)
            if jid in seen:
                continue
            seen.add(jid)
            new += 1
            seg = body[m.end():m.end() + 6000].split("/Description/")[0]
            pairs = re.findall(r'id="column_label_\d+">([^<]*)</span>.*?column-value"[^>]*>([^<]*)<', seg, re.S)
            if pairs:  # neue Darstellung (z. B. rbb): Wertepaare, Ort ohne Beschriftung
                art = " · ".join(dict.fromkeys(clean(v) for l, v in pairs if l.strip() in ("Art", "Befristung") or "Mitarbeit" in v))
                ort = next((clean(v) for l, v in reversed(pairs) if not l.strip() and "Mitarbeit" not in v), "")
            else:  # ältere Darstellung (z. B. NDR, BR): Werte mit | getrennt
                info = clean(re.sub(r"<[^>]+>", " ", body[m.end():m.end() + 2500]))
                parts = [p.strip() for p in info.split("|")]
                art = " · ".join(dict.fromkeys(p for p in parts if p.startswith(("Art:", "Befristung:"))))
                ort = next((p for p in parts if p and not re.search(r":|Stellennummer|^VG|^nein|^ja|^Frau|^Mann", p)), "")
                ort = re.split(r"-->", ort)[0].strip()
            rec = record(q["name"], jid, q["name"], m.group(3), urljoin(url, m.group(1)), art=art)
            out.append((rec, [ort] if ort else ([q["ort"]] if q.get("ort") else []), False))
        nxt = re.search(r"NextLink&quot;:\{[^}]*?EnhancedUrl&quot;:&quot;([^&]*?(?:&amp;amp;[^&]*?)*)&quot;", body)
        if not new or not nxt:
            break
        href = html.unescape(html.unescape(nxt.group(1))).split("#")[0]
        if not href:
            break
        url = urljoin(q["url"], href)
    return out


def _successfactors(sess, q):
    base, out, start = q["url"], [], 0
    for _ in range(MAX_PAGES):
        url = base + (f"&startrow={start}" if start else "")
        body = _get(sess, url).text
        rows = re.findall(r'<tr class="data-row">(.*?)</tr>', body, re.S)
        for row in rows:
            a = re.search(r'<a[^>]*href="(/[^"]*job/[^"]+)"[^>]*class="jobTitle-link"[^>]*>([^<]*)</a>', row) or \
                re.search(r'<a[^>]*class="jobTitle-link"[^>]*href="(/[^"]*job/[^"]+)"[^>]*>([^<]*)</a>', row)
            if not a:
                continue
            href = html.unescape(a.group(1))
            jid = re.search(r"/(\d+)/?$", href)
            loc = re.search(r'<span class="jobLocation">\s*([^<]*?)\s*</span>', row) or \
                re.search(r'<span class="jobFacility">\s*([^<]*?)\s*</span>', row)
            date = re.search(r'<span class="jobDate">\s*([^<]*?)\s*</span>', row)
            rec = record(q["name"], jid.group(1) if jid else href, q["name"], a.group(2), urljoin(base, href),
                         published=_day(date.group(1) if date else ""))
            locs = [clean(loc.group(1))] if loc else []
            out.append((rec, locs, False))
        total = re.search(r"von <b>(\d+)</b>", body)
        start += len(rows)
        if not rows or not total or start >= int(total.group(1)):
            break
    return out


def _ufa(sess, q):
    body = _get(sess, q["url"]).text
    out = []
    for m in re.finditer(r'<a class="job-teaser" href="([^"]+)"(.*?)</a>', body, re.S):
        attrs, inner = m.group(2), m.group(2)
        title = re.search(r'job-teaser__headline">([^<]*)<', inner)
        if not title:
            continue
        cities = re.search(r'data-job-cities="([^"]*)"', attrs)
        dept = re.search(r'data-job-department="([^"]*)"', attrs)
        etype = re.search(r'data-job-entry-type="([^"]*)"', attrs)
        jid = m.group(1).rstrip("/").rsplit("/", 1)[-1]
        rec = record(q["name"], jid, clean(dept.group(1)) if dept and dept.group(1) else "UFA", title.group(1), m.group(1),
                     art=clean(etype.group(1)) if etype else "")
        locs = [c.strip() for c in (cities.group(1) if cities else "").split(",") if c.strip()]
        out.append((rec, locs or ([q["ort"]] if q.get("ort") else []), False))
    return out


def _hr(sess, q):
    body = _get(sess, q["url"]).text
    out, seen = [], set()
    for m in re.finditer(r'href="(https://www\.hr\.de/karriere/alle-angebote/[^"/]+/[^"]+\.html)"[^>]*>\s*<h3>\s*<span[^>]*>([^<]*)</span>',
                         body, re.S):
        link = m.group(1)
        if link in seen:
            continue
        seen.add(link)
        rec = record(q["name"], link.rsplit("/", 1)[-1], q["name"], m.group(2), link)
        out.append((rec, [q["ort"]] if q.get("ort") else [], False))
    return out


def _dwdl(sess, q):
    """DWDL.de-Jobbörse: Links /jobboerse/<nr>_<firma>.html mit Text "Firma sucht Stelle Ort"."""
    body = _get(sess, q["url"]).text
    out, seen = [], set()
    for m in re.finditer(r"""<a\b[^>]*href=["']([^"']*jobboerse/(\d+)_[^"']*)["'][^>]*>(.*?)</a>""", body, re.S | re.I):
        jid = m.group(2)
        if jid in seen:
            continue
        parts = [clean(x) for x in re.split(r"<[^>]+>", m.group(3)) if clean(x)]
        line = next((p for p in parts if " sucht " in p), "")
        if not line:
            continue
        seen.add(jid)
        firma, title = line.split(" sucht ", 1)
        rest = [p for p in parts if p != line and " sucht " not in p]
        locs = rest[-1:] if rest else []
        link = re.sub(r"(jobboerse/)+", "jobboerse/", urljoin(q["url"], html.unescape(m.group(1))))
        rec = record(q["name"], jid, firma.strip(), title.strip(), link)
        out.append((rec, locs, False))
    return out


FETCHERS = {
    "rss": _rss,
    "personio": _personio,
    "softgarden": _softgarden,
    "umantis": _umantis,
    "successfactors": _successfactors,
    "ufa": _ufa,
    "hr": _hr,
    "dwdl": _dwdl,
}


def fetch(quellen, flt, sess=None, log=print):
    """Rückgabe: (jobs, info). info["ok"] = Namen der Quellen, die heute vollständig gelesen wurden."""
    sess = sess or PoliteSession(pause=1.0)
    jobs, errors, ok, per_source, dropped = [], [], [], {}, {}

    def drop(why):
        dropped[why] = dropped.get(why, 0) + 1

    for q in quellen:
        if q.get("aus") or q.get("art") not in FETCHERS:
            continue
        try:
            postings = FETCHERS[q["art"]](sess, q)
        except NotAllowed as exc:
            errors.append(f"{q['name']}: robots.txt erlaubt den Abruf nicht ({exc}) – übersprungen")
            per_source[q["name"]] = {"status": "robots.txt verbietet"}
            continue
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{q['name']}: Abruf fehlgeschlagen: {exc}"[:400])
            per_source[q["name"]] = {"status": "Fehler"}
            continue
        kept = 0
        max_age = q.get("max_alter_tage")
        cutoff = (datetime.now(timezone.utc) - timedelta(days=int(max_age))).strftime("%Y-%m-%d") if max_age else ""
        for rec, locs, remote_flag in postings:
            if cutoff and rec.get("published") and rec["published"] < cutoff:
                drop(f"älter als {max_age} Tage")
                continue
            ev, why = flt.evaluate(rec["title"], rec["company"], locs, rec.get("description", ""), remote_flag)
            if why:
                drop(why)
                continue
            jobs.append({**rec, **ev})
            kept += 1
        ok.append(q["name"])
        per_source[q["name"]] = {"gesamt": len(postings), "passend": kept,
                                 "beispiele": [f"{r['title']} | {r['company']} | {', '.join(l)}" for r, l, _ in postings[:3]]}
        if not postings:
            errors.append(f"{q['name']}: keine einzige Stelle gelesen – Seite geändert? Bitte prüfen.")

    log(f"Firmen/Feeds: {len(jobs)} passend aus {len(ok)} Quellen, {sess.calls} Aufrufe")
    return jobs, {"calls": sess.calls, "errors": errors, "ok": ok, "per_source": per_source, "dropped": dropped}
