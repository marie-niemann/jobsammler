"""Gemeinsame Hilfsfunktionen für alle Quellen: Abruf, robots.txt, Rollen, Filter, Orte."""

import html
import re
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
USER_AGENT = "Mozilla/5.0 (compatible; jobsammler/1.0; privater Jobsammler, 1 Abruf pro Tag)"
ROBOTS_NAME = "jobsammler"


def load_yaml(rel_path):
    with open(ROOT / rel_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class PoliteSession:
    """HTTP-Zugriff mit Pause zwischen Anfragen, Wiederholung bei Fehlern, robots.txt-Prüfung und Aufrufzähler."""

    def __init__(self, pause=1.0, timeout=30, retries=2):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT
        self.s.headers["Accept-Language"] = "de-DE,de;q=0.9,en;q=0.5"
        self.pause = pause
        self.timeout = timeout
        self.retries = retries
        self.calls = 0
        self._last = 0.0
        self._robots = {}

    def get(self, url, **kw):
        kw.setdefault("timeout", self.timeout)
        last_exc = None
        for attempt in range(self.retries + 1):
            wait = self.pause - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            self.calls += 1
            try:
                r = self.s.get(url, **kw)
                if r.status_code in (429, 500, 502, 503, 504) and attempt < self.retries:
                    time.sleep(3 * (attempt + 1))
                    continue
                return r
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(3 * (attempt + 1))
        raise last_exc

    def allowed(self, url):
        """Erlaubt die robots.txt der Seite den Abruf? Ist robots.txt gesperrt (401/403), gilt: nicht erlaubt."""
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = RobotFileParser()
            try:
                r = self.get(base + "/robots.txt")
                if r.status_code in (401, 403):
                    rp.disallow_all = True
                elif r.status_code >= 400:
                    rp.allow_all = True
                else:
                    rp.parse(r.text.splitlines())
            except Exception:  # noqa: BLE001
                rp.allow_all = True  # robots.txt nicht erreichbar: wie "keine Regeln"
            self._robots[base] = rp
        return self._robots[base].can_fetch(ROBOTS_NAME, url)


def to_text(raw, limit=1500):
    """HTML oder Markdown grob in Klartext umwandeln und kürzen."""
    if not raw:
        return ""
    t = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>", "\n", raw)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(html.unescape(t))
    t = re.sub(r"[#*_`]{1,}", "", t)
    t = re.sub(r"[ \t\xa0]+", " ", t)
    t = re.sub(r"\s*\n\s*", "\n", t).strip()
    return t[:limit]


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(html.unescape(s or ""))).strip()


# ---------- Rollen-Erkennung ----------

_GENDER = re.compile(
    r"\((?:[mwfdxa]\s*[/|,]\s*)+[mwfdxa]\)|\b[mwfdx]/[mwfdx]/[mwfdx]\b|\(all genders?\)|\(gn\)|\(mensch\)|\*in\b|:in\b|/in\b|\*innen\b|:innen\b",
    re.I,
)


def normalize_title(title):
    t = _GENDER.sub(" ", title or "")
    t = t.lower().replace("’", "'")
    t = re.sub(r"[^a-z0-9äöüß&' ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _words(s):
    return normalize_title(s).split()


def _word_hit(t, w):
    """Titelwort t passt zu Suchwort w: gleich, weibliche Form/Mehrzahl, oder (bei langen Wörtern) Wortanfang/-ende."""
    forms = (w, w + "in", w + "innen", w + "s", w + "en", w + "n")
    return (t in forms
            or (len(w) >= 9 and t.startswith(w))                      # Wortanfang: "Formatentwicklungs..."
            or (len(w) >= 8 and any(t.endswith(f) for f in forms)))   # Wortende: "Morgenmoderator", "Eventmoderatorin"


class RoleMatcher:
    """Ordnet einen Stellentitel einer Rolle aus roles.yaml zu.

    Ein Suchbegriff passt, wenn alle seine Wörter im Titel vorkommen (lange Wörter auch als Wortanfang),
    oder wenn der zusammengeschriebene Begriff im Titel steckt ("TV-Moderator" -> "tvmoderator").
    Steht ein Wort aus "ohne" der Rolle im Titel, zählt die Rolle nicht.
    Bei mehreren Treffern gewinnt die wichtigste Rolle (prio), dann der längste Suchbegriff.
    """

    def __init__(self, roles):
        self.roles = roles
        self.terms = []
        for key, spec in roles.items():
            for term in spec.get("terms", []):
                self.terms.append((key, _words(term)))
        self.terms.sort(key=lambda x: (roles[x[0]].get("prio", 9), -len(" ".join(x[1]))))

    def guess(self, title):
        low = (title or "").lower()
        tw = _words(title)
        compact = "".join(tw)
        for key, words in self.terms:
            if not words:
                continue
            if any(o.lower() in low for o in self.roles[key].get("ohne") or []):
                continue
            if all(any(_word_hit(t, w) for t in tw) for w in words):
                return key
            if len(words) > 1 and "".join(words) in compact:
                return key
        return ""


# ---------- Ausschlüsse ----------

class Excluder:
    def __init__(self, cfg):
        self.titles = [str(t).lower() for t in cfg.get("titel") or [] if str(t).strip()]
        self.firms = [str(t).lower() for t in cfg.get("firmen") or [] if str(t).strip()]
        self.ba_jobs = [str(t).lower() for t in cfg.get("ba_berufe") or [] if str(t).strip()]

    def title(self, title):
        t = (title or "").lower()
        return next((x for x in self.titles if x in t), "")

    def firm(self, company):
        c = (company or "").lower()
        return next((x for x in self.firms if x in c), "")

    def ba_job(self, beruf):
        b = (beruf or "").lower()
        return next((x for x in self.ba_jobs if x in b), "")


# ---------- Orte ----------

class Places:
    """Wunschorte (mit Rang), remote, kurze Einsätze."""

    def __init__(self, cfg):
        self.wish = [(w["name"], re.compile(w["muster"], re.I),
                      re.compile(w["nur_firmen"], re.I) if w.get("nur_firmen") else None)
                     for w in cfg.get("wunschorte") or []]
        self.short = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in cfg.get("kurzzeit_woerter") or ["casting"]) + r")\b", re.I)
        self.remote = re.compile("|".join(re.escape(w) for w in cfg.get("remote_woerter") or ["remote"]), re.I)

    def judge(self, locations, title="", text="", remote_flag=False, company=""):
        """Rückgabe dict: ok, rang (0 = erster Wunschort), ortText, remote, hinweis.

        Rang-Reihenfolge: Wunschorte (0, 1, 2 ...), remote (50), Ort unbekannt (60), kurzer Einsatz woanders (70).
        """
        locs = [clean(l).strip(" ,;|") for l in locations if l and clean(l).strip(" ,;|")]
        text_loc = " | ".join(dict.fromkeys(locs))
        remote = bool(remote_flag or self.remote.search(text_loc) or self.remote.search(title or ""))
        wish = [(i, name, rx) for i, (name, rx, only) in enumerate(self.wish)
                if not only or only.search(f"{company} {title}")]  # "nur_firmen": Ort gilt nur für diese Firmen
        for i, name, rx in wish:
            if any(rx.search(l) for l in locs):
                return {"ok": True, "rang": i, "ort": name if len(locs) == 1 else text_loc, "remote": remote, "hinweis": ""}
        if remote:
            return {"ok": True, "rang": 50, "ort": text_loc or "remote", "remote": True, "hinweis": "remote"}
        if not locs:
            # Kein Ort angegeben: im Titel/Text nach einem Wunschort suchen
            for i, name, rx in wish:
                if rx.search(f"{title} {text}"):
                    return {"ok": True, "rang": i, "ort": name, "remote": remote, "hinweis": "Ort aus dem Anzeigentext"}
            return {"ok": True, "rang": 60, "ort": "", "remote": False, "hinweis": "Ort prüfen"}
        hit = self.short.search(f"{title} {text}")
        if hit:
            return {"ok": True, "rang": 70, "ort": text_loc, "remote": False,
                    "hinweis": f"anderer Ort, evtl. kurzer Einsatz ({hit.group(0).lower()})"}
        return {"ok": False, "rang": 99, "ort": text_loc, "remote": False, "hinweis": ""}


class Filter:
    """Alle Regeln zusammen. evaluate() gibt (Eintrag-Ergänzung, Grund fürs Aussortieren) zurück."""

    def __init__(self, roles, exclude, orte):
        self.roles = roles
        self.matcher = RoleMatcher(roles)
        self.ex = Excluder(exclude)
        self.places = Places(orte)

    def role_of(self, title):
        if self.ex.title(title):
            return ""
        return self.matcher.guess(title)

    def evaluate(self, title, company, locations, text="", remote_flag=False):
        x = self.ex.title(title)
        if x:
            return None, f"ausgeschlossen (Titel: {x})"
        x = self.ex.firm(company)
        if x:
            return None, f"ausgeschlossen (Firma: {x})"
        role = self.matcher.guess(title)
        if not role:
            return None, "titel passt zu keiner rolle"
        pl = self.places.judge(locations, title, text, remote_flag, company)
        if not pl["ok"]:
            return None, "ort passt nicht"
        spec = self.roles[role]
        return {
            "roleGuess": role,
            "rolle": spec.get("name", role),
            "prio": spec.get("prio", 9),
            "location": pl["ort"],
            "ortRang": pl["rang"],
            "remote": pl["remote"],
            "hinweis": pl["hinweis"],
        }, ""


def record(quelle, jid, company, title, url, published="", description="", salary="", art=""):
    return {
        "id": f"{quelle}:{jid}",
        "source": quelle,
        "company": clean(company),
        "title": clean(title),
        "url": url or "",
        "published": published or "",
        "description": description or "",
        "salary": salary or "",
        "art": art or "",
    }
