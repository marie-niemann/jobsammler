"""Dritte Prüfrunde: Beispielkopien der Stellenlisten speichern, um die Leseteile passgenau zu bauen."""

import base64
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
OUT = HERE / "ergebnis" / "html"
UA = "Mozilla/5.0 (compatible; jobsammler/1.0; privates Projekt, 1 Abruf pro Tag)"
S = requests.Session()
S.headers["User-Agent"] = UA
S.headers["Accept-Language"] = "de-DE,de;q=0.9"

PAGES = {
    "sf_p7s1": "https://jobs.prosiebensat1.com/search/?q=&locale=de_DE",
    "sf_p7s1_p2": "https://jobs.prosiebensat1.com/search/?q=&locale=de_DE&startrow=25",
    "sf_rtl": "https://jobsearch.createyourowncareer.com/RTL/search/?q=&locale=de_DE",
    "sf_zdf": "https://jobs.zdf.de/search/?q=&locale=de_DE",
    "sg_banijay": "https://banijay.softgarden.io/de/vacancies",
    "sg_seapoint": "https://seapoint.softgarden.io/de/vacancies",
    "um_rbb": "https://recruitingapp-5154.de.umantis.com/Jobs/All",
    "um_ndr": "https://jobs.ndr.de/Jobs/All",
    "ufa": "https://www.ufa.de/karriere/jobs",
    "hr": "https://www.hr.de/karriere/alle-angebote/index.html",
    "wdr": "https://bewerbung.wdr.de/index.php?ac=search_result",
    "personio_btf": "https://btf-gmbh.jobs.personio.de/",
    "personio_itv": "https://itv-studios-germany.jobs.personio.de/",
    "newsroom_rss": "https://www.newsroom.de/rss/jobs-feed/",
    "ndr_rss": "https://www.ndr.de/der_ndr/karriere/index~rss2.xml",
    "robots_hr": "https://www.hr.de/robots.txt",
    "robots_personio_btf": "https://btf-gmbh.jobs.personio.de/robots.txt",
    "robots_seapoint_sg": "https://seapoint.softgarden.io/robots.txt",
}
BA = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, url in PAGES.items():
        time.sleep(1)
        try:
            r = S.get(url, timeout=30)
            body = r.text
            if name == "newsroom_rss":
                body = body[:120_000]
            (OUT / f"{name}.txt").write_text(f"<!-- {r.status_code} {r.url} -->\n" + body[:900_000], encoding="utf-8")
            print(name, r.status_code, len(body), flush=True)
        except Exception as exc:  # noqa: BLE001
            (OUT / f"{name}.txt").write_text(f"FEHLER {exc}", encoding="utf-8")
    # BA: eine Suche und ein Detail
    h = {"X-API-Key": "jobboerse-jobsuche"}
    r = S.get(f"{BA}/v6/jobs", params={"was": "Moderator", "size": 5, "angebotsart": 1}, headers=h, timeout=30)
    (OUT / "ba_search.txt").write_text(r.text, encoding="utf-8")
    try:
        ref = r.json()["ergebnisliste"][0]["referenznummer"]
        time.sleep(1)
        d = S.get(f"{BA}/v4/jobdetails/{base64.b64encode(ref.encode()).decode()}", headers=h, timeout=30)
        (OUT / "ba_detail.txt").write_text(f"<!-- {d.status_code} -->\n" + d.text, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        (OUT / "ba_detail.txt").write_text(f"FEHLER {exc}", encoding="utf-8")
    print("fertig")


if __name__ == "__main__":
    main()
