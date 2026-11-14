"""Einmalig: Beispielkopie der DWDL-Jobbörse speichern, um den Leseteil anzupassen."""
from pathlib import Path
import requests
r = requests.get("https://www.dwdl.de/jobboerse/", timeout=30,
                 headers={"User-Agent": "Mozilla/5.0 (compatible; jobsammler/1.0; privater Jobsammler, 1 Abruf pro Tag)"})
Path(__file__).with_name("dwdl_beispiel.html").write_text(f"<!-- {r.status_code} {r.url} -->\n" + r.text, encoding="utf-8")
print(r.status_code, len(r.text))
