"""Jobsammler: sammelt passende Stellen aus allen Quellen und schreibt

  data/jobs.json               alle Stellen (offen und kürzlich geschlossen)
  data/neu.md                  gut lesbare Liste der neuen Stellen des Tages
  data/alle.md                 gut lesbare Liste aller offenen Stellen
  data/run.json                Protokoll des letzten Laufs
  data/protokolle/DATUM.json   Protokoll jedes einzelnen Laufs

Regel: Eine Stelle ist offen, wenn sie heute in der Quelle steht. Fehlt sie, ist sie geschlossen.
Geschlossene Stellen bleiben 60 Tage in der Datei (ab dem letzten Tag, an dem sie gesehen wurden).
War eine Quelle heute nicht erreichbar, bleibt der Status ihrer Stellen unverändert.

Aufruf:  python collect.py      (läuft täglich als GitHub Action)
"""

import json
import re
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sources import ba, firmen
from sources.common import ROOT, Filter, PoliteSession, load_yaml, normalize_title

DATA = ROOT / "data"
JOBS_FILE = DATA / "jobs.json"
RUN_FILE = DATA / "run.json"
NEW_FILE = DATA / "neu.md"
ALL_FILE = DATA / "alle.md"
LOG_DIR = DATA / "protokolle"
KEEP_CLOSED_DAYS = 60
BOARDS = ["newsroom.de", "RADIOSZENE", "DWDL.de"]  # Quellen, die keinen Firmennamen liefern
FIELDS = ["id", "source", "company", "title", "url", "location", "remote", "published", "firstSeen", "lastSeen",
          "open", "roleGuess", "rolle", "prio", "ortRang", "hinweis", "art", "salary", "description"]


def now_berlin():
    return datetime.now(ZoneInfo("Europe/Berlin"))


def company_key(name):
    n = (name or "").lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"\b(gmbh|ag|se|kg|ug|mbh|co|inc|ltd|llc|group|holding|deutschland|germany)\b\.?", " ", n)
    return re.sub(r"[^a-z0-9äöü]", "", n)


def load_old():
    if not JOBS_FILE.exists():
        return {}
    try:
        return {j["id"]: j for j in json.loads(JOBS_FILE.read_text(encoding="utf-8"))}
    except Exception:  # noqa: BLE001
        return {}


def merge_duplicates(jobs):
    """Dieselbe Stelle aus mehreren Quellen zusammenführen (Firma + Titel). Die Firmenquelle gewinnt."""
    groups = {}
    for j in jobs:
        groups.setdefault((company_key(j["company"]), normalize_title(j["title"])), []).append(j)
    # Jobbörsen-Feeds ohne Firmennamen (z. B. newsroom.de): gleiche Stelle bei einer Firma per Titel erkennen
    boards = {company_key(n) for n in BOARDS}
    by_title = {}
    for (ck, nt), g in groups.items():
        if ck not in boards:
            by_title.setdefault(nt, (ck, nt))
    for key in [k for k in groups if k[0] in boards]:
        target = by_title.get(key[1]) or next(
            (v for nt, v in by_title.items() if len(key[1]) >= 15 and (nt.startswith(key[1]) or key[1].startswith(nt))), None)
        if target and target in groups:
            groups[target] += groups.pop(key)
    merged = []
    for group in groups.values():
        group.sort(key=lambda j: (company_key(j["company"]) in boards, j["source"] == "Arbeitsagentur", j["ortRang"], j["id"]))
        win = dict(group[0])
        for other in group[1:]:
            for f in ("salary", "description", "published", "art"):
                if not win.get(f) and other.get(f):
                    win[f] = other[f]
        win["_ids"] = [j["id"] for j in group]
        merged.append(win)
    return merged


def sort_key(j):
    return (j.get("prio", 9), j.get("ortRang", 99), j.get("company", "").lower(), j.get("title", "").lower())


def job_lines(j, today_s=""):
    bits = [j.get("location") or "Ort unbekannt"]
    if j.get("remote"):
        bits.append("remote möglich")
    if j.get("art"):
        bits.append(j["art"])
    if j.get("salary"):
        bits.append(j["salary"])
    new = " 🆕" if today_s and j.get("firstSeen") == today_s else ""
    extra = [f"Quelle: {j['source']}"]
    if j.get("published"):
        extra.append(f"veröffentlicht {j['published']}")
    extra.append(f"gefunden am {j.get('firstSeen', '')}")
    if j.get("hinweis"):
        extra.append(f"⚠️ {j['hinweis']}")
    return [f"- **[{j['title']}]({j['url']})**{new}  ",
            f"  {j['company']} · {' · '.join(bits)}",
            f"  <sub>{' · '.join(extra)}</sub>"]


def write_all_md(today_s, open_jobs):
    """Alle offenen Stellen, nach Rolle gruppiert, darin nach Ort (Wunschorte zuerst)."""
    lines = [f"# Alle offenen Stellen ({len(open_jobs)})", "",
             f"Stand: {datetime.fromisoformat(today_s).strftime('%d.%m.%Y')} · 🆕 = heute neu · "
             "Nur die neuen des Tages: [neu.md](neu.md)", ""]
    by_role = {}
    for j in sorted(open_jobs, key=sort_key):
        by_role.setdefault((j.get("prio", 9), j.get("rolle", "")), []).append(j)
    lines += ["**Rollen:** " + " · ".join(
        f"[{rolle} ({len(items)})](#{re.sub(r'[^a-z0-9äöüß -]', '', rolle.lower()).replace(' ', '-')}-{len(items)})"
        for (_, rolle), items in sorted(by_role.items())), ""]
    for (_, rolle), items in sorted(by_role.items()):
        lines += [f"## {rolle} ({len(items)})", ""]
        for j in items:
            lines += job_lines(j, today_s)
        lines.append("")
    ALL_FILE.write_text("\n".join(lines), encoding="utf-8")


def write_new_md(today_s, new_jobs, open_jobs, run, alerts):
    lines = [f"# Neue Stellen vom {datetime.fromisoformat(today_s).strftime('%d.%m.%Y')}", ""]
    if not new_jobs:
        lines += ["Heute sind keine neuen passenden Stellen dazugekommen.", ""]
    else:
        lines += [f"**{len(new_jobs)} neue Stelle{'n' if len(new_jobs) != 1 else ''}** "
                  f"(insgesamt {len(open_jobs)} offene Stellen in [alle.md](alle.md)).", ""]
        by_role = {}
        for j in sorted(new_jobs, key=sort_key):
            by_role.setdefault((j.get("prio", 9), j.get("rolle", "")), []).append(j)
        for (_, rolle), items in sorted(by_role.items()):
            lines += [f"## {rolle} ({len(items)})", ""]
            for j in items:
                lines += job_lines(j)
            lines.append("")
    if run["fehler"]:
        lines += ["---", "", f"ℹ️ Beim Abruf gab es {len(run['fehler'])} Hinweis(e), Details in [run.json](run.json).", ""]
    if alerts:
        lines += ["---", "",
                  "Nicht automatisch abrufbar (bitte per E-Mail-Jobalert oder von Hand prüfen): "
                  + ", ".join(a["name"] for a in alerts) + ". Mehr dazu in [QUELLEN.md](../QUELLEN.md).", ""]
    NEW_FILE.write_text("\n".join(lines), encoding="utf-8")


def main():
    t0 = time.time()
    started = now_berlin()
    today = started.date()
    today_s = today.isoformat()
    roles = load_yaml("config/roles.yaml")
    comp = load_yaml("config/companies.yaml")
    flt = Filter(roles, load_yaml("config/exclude.yaml"), load_yaml("config/orte.yaml"))
    old = load_old()

    found, errors, stats, ok_sources = [], [], {}, set()

    # 1) Sender, Firmen, Feeds
    try:
        jobs, info = firmen.fetch(comp.get("quellen") or [], flt, sess=PoliteSession(pause=1.0))
        found += jobs
        errors += info["errors"]
        ok_sources.update(info["ok"])
        stats["firmen_und_feeds"] = {"stellen": len(jobs), "aufrufe": info["calls"], "pro_quelle": info["per_source"],
                                     "aussortiert": info["dropped"]}
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Firmen/Feeds komplett fehlgeschlagen: {exc}")

    # 2) Arbeitsagentur
    try:
        jobs, info = ba.fetch(roles, flt, known=old, sess=PoliteSession(pause=0.5))
        found += jobs
        errors += info["errors"]
        if not any("Suche" in e for e in info["errors"]):
            ok_sources.add("Arbeitsagentur")
        stats["arbeitsagentur"] = {"stellen": len(jobs), "gefunden": info["gefunden"], "aufrufe": info["calls"],
                                   "aussortiert": info["dropped"]}
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Arbeitsagentur fehlgeschlagen: {exc}")

    found = [j for j in found if j.get("url")]
    merged = merge_duplicates(found)

    # offen / geschlossen
    result, seen_ids, new_jobs = {}, set(), []
    for j in merged:
        ids = j.pop("_ids")
        seen_ids.update(ids)
        prev = [old[i] for i in ids if i in old]
        j["firstSeen"] = min([p["firstSeen"] for p in prev if p.get("firstSeen")] or [today_s])
        j["lastSeen"] = today_s
        j["open"] = True
        rec = {f: j.get(f, "") for f in FIELDS}
        result[j["id"]] = rec
        if not prev:
            new_jobs.append(rec)

    closed_today = 0
    cutoff = (today - timedelta(days=KEEP_CLOSED_DAYS)).isoformat()
    for jid, j in old.items():
        if jid in result or jid in seen_ids:
            continue
        if j.get("open") and j.get("source") not in ok_sources:
            result[jid] = j  # Quelle heute nicht erreichbar: Status unverändert lassen
            continue
        if j.get("open"):
            j = {**j, "open": False}
            closed_today += 1
        if j.get("lastSeen", today_s) >= cutoff:
            result[jid] = j

    jobs_out = sorted(result.values(), key=sort_key)
    jobs_out.sort(key=lambda j: j["firstSeen"], reverse=True)
    jobs_out.sort(key=lambda j: not j["open"])
    open_jobs = [j for j in jobs_out if j["open"]]

    per_source, per_role = {}, {}
    for j in open_jobs:
        per_source[j["source"]] = per_source.get(j["source"], 0) + 1
        per_role[j["roleGuess"]] = per_role.get(j["roleGuess"], 0) + 1
    run = {
        "datum": today_s,
        "gestartet": started.isoformat(timespec="seconds"),
        "dauerSekunden": round(time.time() - t0),
        "offen": len(open_jobs),
        "neuHeute": len(new_jobs),
        "geschlossenHeute": closed_today,
        "geschlossenInDatei": len(jobs_out) - len(open_jobs),
        "offenProQuelle": dict(sorted(per_source.items(), key=lambda x: -x[1])),
        "offenProRolle": dict(sorted(per_role.items(), key=lambda x: -x[1])),
        "zusammengefuehrt": len(found) - len(merged),
        "quellenOk": sorted(ok_sources),
        "quellen": stats,
        "fehler": errors,
    }

    DATA.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    JOBS_FILE.write_text(json.dumps(jobs_out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    RUN_FILE.write_text(json.dumps(run, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (LOG_DIR / f"{today_s}.json").write_text(json.dumps(run, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    write_new_md(today_s, new_jobs, open_jobs, run, comp.get("alerts") or [])
    write_all_md(today_s, open_jobs)

    print(f"{today_s}: {len(open_jobs)} offen ({len(new_jobs)} neu, {closed_today} heute geschlossen), "
          f"{len(errors)} Hinweise, {run['dauerSekunden']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
