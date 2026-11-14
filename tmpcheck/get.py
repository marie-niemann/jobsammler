from pathlib import Path
import requests
r = requests.get("https://www.dwdl.de/jobboerse/alle-anzeigen.html?typ=alle", timeout=30,
                 headers={"User-Agent": "Mozilla/5.0 (compatible; jobsammler/1.0; privater Jobsammler, 1 Abruf pro Tag)"})
Path("tmpcheck/dwdl_alle.html").write_text(f"<!-- {r.status_code} {r.url} -->\n" + r.text, encoding="utf-8")
