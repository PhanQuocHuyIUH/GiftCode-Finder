"""Temporary: where can cover art come from, and do sized image URLs work?"""
import json

import requests

from .fetch import USER_AGENT

S = requests.Session()
S.headers["User-Agent"] = USER_AGENT


def head(url):
    try:
        r = S.get(url, timeout=30, stream=True)
        size = r.headers.get("content-length")
        print(f"   {r.status_code} {r.headers.get('content-type')} len={size} {url[:150]}")
        r.close()
    except Exception as exc:
        print("   ERR", exc, url[:120])


for term in ("Wuthering Waves", "Strinova"):
    try:
        raw = S.get("https://store.steampowered.com/api/storesearch/", params={"term": term, "cc": "us", "l": "english"}, timeout=30).json()
        print("SEARCH", term, [(i.get("id"), i.get("name"), i.get("tiny_image")) for i in (raw.get("items") or [])[:4]])
    except Exception as exc:
        print("SEARCH ERR", term, exc)

for appid in (3513350, 1282270):
    try:
        raw = S.get("https://store.steampowered.com/api/appdetails", params={"appids": appid, "l": "english", "cc": "us"}, timeout=30).json()
        entry = raw[str(appid)]
        if not entry.get("success"):
            print("APP", appid, "no success", json.dumps(entry)[:300])
        else:
            d = entry["data"]
            print("APP", appid, {k: d.get(k) for k in ("name", "type", "header_image", "capsule_image", "capsule_imagev5", "background", "background_raw")})
            print("   keys:", sorted(d.keys()))
            for key in ("header_image", "capsule_imagev5", "background_raw"):
                if d.get(key):
                    head(d[key])
            for shot in (d.get("screenshots") or [])[:2]:
                print("   shot", shot)
    except Exception as exc:
        print("APP ERR", appid, exc)
    for name in ("header.jpg", "library_hero.jpg", "library_600x900.jpg", "capsule_616x353.jpg", "logo.png"):
        head(f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/{name}")

base = "https://cmsassets.rgpub.io/sanity/images/dsfx7636/news_live/7aaebca3079aebd84cd6c257a16beeb8a8ff31fb-1920x1080.jpg?accountingTag=TFT"
print("RIOT")
for extra in ("", "&w=480", "&w=480&auto=format&q=75", "&w=960&fit=max&auto=format&q=75", "&w=160&h=160&fit=crop&auto=format"):
    head(base + extra)
for url in (
    "https://raw.communitydragon.org/latest/game/assets/ux/traiticons/trait_icon_18_blossom.png",
    "https://raw.communitydragon.org/latest/game/assets/ux/tft/championsplashes/",
    "https://raw.communitydragon.org/latest/game/assets/characters/tft18_akali/skins/base/images/",
):
    head(url)
db = json.load(open("data/tft_db/18.json"))
print("DB champ sample:", [(c["name"], c.get("icon")) for c in db["champions"][:3]])
for c in db["champions"][:2]:
    head(c["icon"])
