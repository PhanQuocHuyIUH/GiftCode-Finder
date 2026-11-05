"""Temporary: where can the missing numbers come from?"""
import json
import re

from bs4 import BeautifulSoup

from .fetch import Fetcher

f = Fetcher(timeout=60)
try:
    raw = json.loads(f.fetch("https://raw.communitydragon.org/pbe/cdragon/tft/vi_vn.json").text)
    for entry in raw.get("setData") or []:
        if entry.get("number") == 18:
            champs = [c for c in entry.get("champions") or [] if c.get("traits")]
            withv = [c for c in champs if (c.get("ability") or {}).get("variables")]
            print("PBE set18", entry.get("mutator"), len(champs), "with vars", len(withv), withv[0]["ability"]["variables"][:3] if withv else None)
except Exception as exc:
    print("PBE ERR", exc)

for url in ("https://lolchess.gg/champions/set18/akali?hl=vi", "https://lolchess.gg/guide/augments/set18?hl=vi", "https://lolchess.gg/items/set18?hl=vi"):
    try:
        page = f.fetch(url)
    except Exception as exc:
        print(url, "ERR", exc)
        continue
    soup = BeautifulSoup(page.text, "html.parser")
    nd = soup.find("script", id="__NEXT_DATA__")
    pp = json.loads(nd.string)["props"]["pageProps"] if nd and nd.string else {}
    blob = json.dumps(pp, ensure_ascii=False)
    print("#####", url, "->", page.url, "len", len(page.text), "pageProps", list(pp)[:12], len(blob))
    print("  pp sample:", blob[:1500])
    text = soup.get_text(" ", strip=True)
    for word in ("Phi Đao", "Kích Cỡ", "Máu tối đa", "Hừng Đông"):
        i = text.find(word)
        if i >= 0:
            print("  text@", word, ":", text[max(0, i - 200): i + 500])
            break
