"""Fill the numbers the game data leaves out, from LoLCHESS.GG.

Community Dragon's game data writes "?" where a number is computed by the
game (most ability numbers of the newest set, some augments and items).
LoLCHESS.GG's champion, augment and item pages embed the same entries with
those numbers filled in (in Vietnamese with ``?hl=vi``), keyed by the game's
own id (``ingameKey``), so they can be matched one to one.
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from .tft_db import ICON_TEXT, STAGES, clean

BASE = "https://lolchess.gg"
STAGE = re.compile(r"^[2-5]-[1-7]$")


def _next_data(html: str):
    tag = BeautifulSoup(html, "html.parser").find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except ValueError:
        return None


def _find_list(value, key: str):
    """The first list under ``key`` whose entries carry an ``ingameKey``."""
    if isinstance(value, dict):
        found = value.get(key)
        if isinstance(found, list) and found and isinstance(found[0], dict) and "ingameKey" in found[0]:
            return found
        for child in value.values():
            hit = _find_list(child, key)
            if hit:
                return hit
    elif isinstance(value, list):
        for child in value:
            hit = _find_list(child, key)
            if hit:
                return hit
    return None


def fetch_lists(set_number: int, fetch, champion_hint: str | None = None, log=print) -> dict:
    """{"champions": [...], "augments": [...], "items": [...]} for a season."""
    out = {}
    pages = {
        "champions": [f"{BASE}/champions/set{set_number}?hl=vi"]
        + ([f"{BASE}/champions/set{set_number}/{champion_hint}?hl=vi"] if champion_hint else []),
        "augments": [f"{BASE}/augments/set{set_number}?hl=vi"],
        "items": [f"{BASE}/items/set{set_number}?hl=vi"],
    }
    for kind, urls in pages.items():
        for url in urls:
            try:
                data = _next_data(fetch(url))
            except Exception as exc:
                log(f"    lolchess {kind}: {exc}")
                continue
            found = _find_list(data, kind) if data else None
            if found:
                out[kind] = found
                break
    return out


def _stats_rows(stats) -> list[dict]:
    """"Sát Thương: 455(%i:scaleAP%) [455 / 685 / 3500]" -> {"name", "value"}."""
    rows = []
    for line in stats or []:
        if not isinstance(line, str):
            continue
        text = clean(line)
        match = re.match(r"^(.*?):\s*(.*?)\s*\[([^\]]+)\]\s*$", text)
        if match:
            rows.append({"name": match[1].strip(), "value": re.sub(r"\s*/\s*", "/", match[3].strip())})
        elif ":" in text:
            name, value = text.split(":", 1)
            rows.append({"name": name.strip(), "value": value.strip()})
    return rows


def _stages(entry: dict) -> list[str] | None:
    """Stages an augment is offered at, wherever the site keeps them."""
    found = set()

    def walk(value, key=""):
        if isinstance(value, str):
            if STAGE.match(value.strip()) and key not in ("desc", "name"):
                found.add(value.strip())
        elif isinstance(value, list):
            for child in value:
                walk(child, key)
        elif isinstance(value, dict):
            for k, child in value.items():
                if k not in ("desc", "name", "imageUrl"):
                    walk(child, k)

    walk(entry)
    # The augment list flags the rounds as booleans: "isRound21": true.
    for key, value in entry.items():
        match = re.fullmatch(r"isRound([2-5])([1-7])", key)
        if match and value is True:
            found.add(f"{match[1]}-{match[2]}")
    stages = [s for s in STAGES if s in found]
    return stages or None


def _item_stats(from_desc: str | None) -> list[dict]:
    rows = []
    for line in re.split(r"<br\s*/?>", from_desc or ""):
        match = re.match(r"\s*%i:([A-Za-z]+)%\s*(.+)$", line)
        if match:
            label = ICON_TEXT.get(match[1].lower()) or {"tftmanaregen": "Hồi năng lượng"}.get(match[1].lower(), match[1])
            rows.append({"label": label, "value": clean(match[2])})
    return rows


def _norm(text: str) -> str:
    return re.sub(r"\W+", "", text.lower())


def enrich(db: dict, lists: dict) -> dict:
    """Fill "?" and missing stages of ``db`` in place; returns counts of what changed."""
    counts = {"champions": 0, "augments": 0, "stages": 0, "items": 0}
    by_key = {kind: {str(e.get("ingameKey")).lower(): e for e in lists.get(kind) or [] if e.get("ingameKey")} for kind in lists}
    # The site sometimes keys an entry by another season's id: fall back to the
    # name, using only an entry whose description has every number.
    by_name: dict[str, dict] = {}
    for kind in ("augments", "items"):
        names = by_name.setdefault(kind, {})
        for e in lists.get(kind) or []:
            if e.get("name") and e.get("desc") and "?" not in clean(e["desc"]):
                names.setdefault(_norm(e["name"]), e)

    def match(kind: str, entry: dict):
        other = by_key.get(kind, {}).get(str(entry.get("id")).lower())
        if other and "?" not in clean(other.get("desc")):
            return other
        return by_name.get(kind, {}).get(_norm(entry.get("name") or "")) or other
    for champ in db.get("champions") or []:
        other = by_key.get("champions", {}).get(str(champ.get("id")).lower())
        if not other:
            continue
        skill = other.get("skill") or {}
        ability = champ.setdefault("ability", {})
        desc = clean(skill.get("desc"))
        if desc and ("?" in (ability.get("desc") or "?") or not ability.get("desc")) and "?" not in desc:
            ability["desc"] = desc
            ability["name"] = ability.get("name") or skill.get("name")
            counts["champions"] += 1
        if not ability.get("variables"):
            ability["variables"] = _stats_rows(skill.get("stats"))
        stats = champ.setdefault("stats", {})
        if stats.get("initialMana") in (None, 0) and isinstance(skill.get("startingMana"), (int, float)):
            stats["initialMana"] = skill["startingMana"]
        if not stats.get("mana") and isinstance(skill.get("skillMana"), (int, float)):
            stats["mana"] = skill["skillMana"]
    for augment in db.get("augments") or []:
        other = match("augments", augment)
        if not other:
            continue
        desc = clean(other.get("desc"))
        if desc and "?" in (augment.get("desc") or "") and "?" not in desc:
            augment["desc"] = desc
            counts["augments"] += 1
        keyed = by_key.get("augments", {}).get(str(augment.get("id")).lower())
        stages = _stages(keyed) if keyed else None  # a namesake of another season may differ
        if stages and augment.get("pool") is None:
            augment["pool"] = True
            augment["stages"] = stages
            counts["stages"] += 1
    for item in db.get("items") or []:
        other = match("items", item)
        if not other:
            continue
        desc = clean(other.get("desc"))
        if desc and ("?" in (item.get("desc") or "") or not item.get("desc")) and "?" not in desc:
            item["desc"] = desc
            counts["items"] += 1
        if not item.get("stats"):
            item["stats"] = _item_stats(other.get("fromDesc"))
    db["filled_from"] = "LoLCHESS.GG"
    return counts
