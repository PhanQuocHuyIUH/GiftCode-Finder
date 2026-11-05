"""Temporary: what LoLCHESS.GG lists look like."""
import json

from .fetch import Fetcher
from .tft_lolchess import fetch_lists

f = Fetcher(timeout=60)
for url in ("https://lolchess.gg/augments/set18?hl=vi", "https://lolchess.gg/champions/set18?hl=vi"):
    try:
        page = f.fetch(url)
        print(url, "->", page.url, page.status_code if hasattr(page, "status_code") else "", len(page.text))
    except Exception as exc:
        print(url, "ERR", exc)
lists = fetch_lists(18, lambda u: f.fetch(u).text, "akali")
for kind, entries in lists.items():
    print("#####", kind, len(entries), "keys", sorted(entries[0].keys()))
    for e in entries[:40]:
        if kind == "augments" and ("?" in json.dumps(e, ensure_ascii=False) or e is entries[0]):
            print("  ", json.dumps(e, ensure_ascii=False)[:700])
    print("  sample:", json.dumps(entries[1], ensure_ascii=False)[:900])
    print("  with ?:", sum(1 for e in entries if "?" in str(e.get("desc") or (e.get("skill") or {}).get("desc") or "")))
