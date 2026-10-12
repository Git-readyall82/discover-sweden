import json
import time
import urllib.parse
import urllib.request

bad = []
for e in json.load(open("data/entries.json", encoding="utf-8")):
    url = ("https://en.wikipedia.org/api/rest_v1/page/summary/"
           + urllib.parse.quote(e["wiki"].replace(" ", "_"), safe=""))
    time.sleep(1)
    req = urllib.request.Request(url, headers={"User-Agent": "DiscoverSweden/1.0 (school project)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.load(r)
        img = "picture" if d.get("thumbnail") else "NO PICTURE"
        print(f'ok   {e["id"]:<15} -> {d.get("title", "?")} ({img})')
        if not d.get("thumbnail"):
            bad.append(e["id"])
    except Exception as exc:
        print(f'FAIL {e["id"]:<15} {e["wiki"]!r}: {exc}')
        bad.append(e["id"])
print("\nProblems:", bad if bad else "none")
