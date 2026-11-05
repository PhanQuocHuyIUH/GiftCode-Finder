"""Temporary: which "?" remain after filling from LoLCHESS.GG."""
import json
import re

from .fetch import Fetcher
from .tft_db import build_db
from .tft_lolchess import enrich, fetch_lists

f = Fetcher(timeout=60)
raw = json.loads(f.fetch("https://raw.communitydragon.org/latest/cdragon/tft/vi_vn.json").text)
for number in (18, 17):
    db = build_db(raw, number, "https://raw.communitydragon.org/latest/game/")
    lists = fetch_lists(number, lambda u: f.fetch(u).text, "akali")
    flags = sorted({k for e in lists.get("augments", []) for k in e if k.startswith("is")})
    print("#####", number, "augment flags", flags)
    print("  counts", enrich(db, lists), "unknown pools", sum(1 for a in db["augments"] if a.get("pool") is None))
    lc = {str(e.get("ingameKey")).lower(): e for e in lists.get("items", [])}
    for kind in ("augments", "items", "champions"):
        for e in db[kind]:
            d = (e.get("ability") or {}).get("desc") if kind == "champions" else e.get("desc")
            if d and "?" in d:
                spots = [d[max(0, m.start() - 50): m.end() + 15].replace("\n", " ") for m in re.finditer(r"\?", d)][:2]
                other = lc.get(str(e.get("id")).lower()) if kind == "items" else None
                print(f"  {kind} {e.get('id')} [{e.get('kind') or ''}] {e.get('name')}: {spots} lc={'yes' if other else 'no'}")
