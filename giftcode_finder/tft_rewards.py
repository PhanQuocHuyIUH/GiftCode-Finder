"""Loot tables of TFT augments and traits, from LoLCHESS.GG's reward tables.

Riot's game data has no loot tables, but the community tools publish them:
LoLCHESS.GG lists, per season, what Expedition, Warpath, Call to Chaos, The
Golden Egg, Coven... can give and how likely each outcome is. Each table is
read into::

    {"slug": "coven", "title": "Coven", "icon": ..., "updated": ..., "desc": ...,
     "groups": [{"title": "130 Essence", "note": ..., "rows": [
         {"chance": "25%", "items": [{"name": "Vàng", "qty": 6, "icon": ...}]}]}],
     "links": ["Tiên Hắc Ám"]}

``links`` are the names of this season's augments and traits the table is
about, so the page can show it next to them. Item names that the site leaves
as game ids ("DA_18_Elise") are turned into the champion's or item's name.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

BASE = "https://lolchess.gg"
REWARDS_VERSION = 1
SKIP = {"augment-exclusive"}  # not a loot table
GAME_ID = re.compile(r"^(?:DA|TFT\d*)_[A-Za-z0-9_]+$")


def index_url(set_number: int) -> str:
    return f"{BASE}/rewards/set{set_number}?hl=vi"


def table_url(set_number: int, slug: str) -> str:
    return f"{BASE}/rewards/set{set_number}/{slug}?hl=vi"


def list_tables(html: str, set_number: int) -> list[str]:
    """Slugs of the reward tables of a season, from any reward page's menu."""
    soup = BeautifulSoup(html, "html.parser")
    slugs = []
    for link in soup.find_all("a", href=True):
        match = re.fullmatch(rf"/rewards/set{set_number}/([a-z0-9-]+)", link["href"].split("?")[0])
        if match and match[1] not in slugs and match[1] not in SKIP:
            slugs.append(match[1])
    return slugs


def _text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if isinstance(node, Tag) else ""


def _item(node: Tag, page_url: str) -> dict:
    img = node.find("img")
    qty = None
    label_parts = []
    for child in node.find_all(string=True):
        text = " ".join(str(child).split())
        if not text or child.parent.name == "style":
            continue
        match = re.fullmatch(r"x\s*(\d+)", text, re.I)
        if match and qty is None:
            qty = int(match[1])
        else:
            label_parts.append(text)
    return {
        "key": node.get("data-reward-key"),
        "name": " ".join(label_parts).strip() or node.get("data-reward-key") or "?",
        "qty": qty,
        "icon": urljoin(page_url, img["src"]) if img and img.get("src") else None,
    }


def parse_table(html: str, slug: str, page_url: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    for style in soup.find_all("style"):
        style.decompose()
    box = soup.select_one(".RewardContainer")
    if box is None:
        return None
    head_img = box.find("img")
    title = box.select_one("h2.title")
    updated = box.select_one(".update-time")
    desc = " ".join(_text(p) for p in box.select(".description p"))
    groups: list[dict] = []
    loose: list[dict] = []
    for section in box.find_all("section"):
        table = section.find("table")
        if table is not None:
            header = section.find("header")
            note = header.find(attrs={"aria-label": True}) if header else None
            rows = []
            for tr in table.select("tbody tr"):
                chance = tr.select_one("td.probability")
                items = [_item(n, page_url) for n in tr.select(".RewardItem")]
                if items:
                    rows.append({"chance": _text(chance) or None, "items": items})
            if rows:
                strong = header.find("strong") if header else None
                groups.append({"title": _text(strong) or _text(header), "note": note["aria-label"] if note else None, "rows": rows})
        elif section.find_parent("section") is None and section.select(".RewardItem"):
            # A plain list of outcomes (Expedition): one row per section.
            chance = section.find(string=re.compile(r"^\s*\d+(?:[.,]\d+)?\s*%\s*$"))
            items = [_item(n, page_url) for n in section.select(".RewardItem")]
            loose.append({"chance": " ".join(chance.split()) if chance else None, "items": items})
    if loose:
        groups.insert(0, {"title": "", "note": None, "rows": loose})
    if not groups:
        return None
    return {
        "slug": slug,
        "title": _text(title) or slug,
        "icon": urljoin(page_url, head_img["src"]) if head_img and head_img.get("src") else None,
        "updated": _text(updated).replace("Updated:", "").replace("Cập nhật:", "").strip() or None,
        "desc": desc or None,
        "url": page_url,
        "groups": groups,
    }


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def link_to_db(table: dict, db: dict | None) -> None:
    """Name the champions/items given as game ids, and find what the table is about."""
    if not db:
        table["links"] = []
        return
    by_id = {}
    for kind in ("champions", "items", "traits", "augments"):
        for entry in db.get(kind) or []:
            if entry.get("id"):
                by_id.setdefault(entry["id"].lower(), (kind, entry))
    for group in table["groups"]:
        for row in group["rows"]:
            for item in row["items"]:
                key = item["name"] if GAME_ID.match(item["name"]) else item.get("key") or ""
                hit = by_id.get(key.lower()) if GAME_ID.match(key) else None
                if hit:
                    kind, entry = hit
                    item["name"] = entry["name"]
                    item["kind"] = kind
                    if kind == "champions":
                        item["cost"] = entry.get("cost")
    slug = _norm(table["slug"])
    links = []
    for kind in ("augments", "traits"):
        for entry in db.get(kind) or []:
            ident = _norm(re.sub(r"^(?:da|tft\d*)_(?:\d+_)?(?:augment_)?", "", str(entry.get("id") or "").lower())).rstrip("0123456789")
            if ident and (ident == slug or ident.startswith(slug) or slug.startswith(ident) and len(ident) > 4):
                if entry["name"] not in links:
                    links.append(entry["name"])
    table["links"] = links


def build_rewards(set_number: int, fetch, db: dict | None, log=print) -> dict | None:
    """All loot tables of a season (``fetch(url) -> html``)."""
    slugs = []
    # The season index redirects to the newest season once a season is over;
    # any of the season's own tables carries the same menu.
    for url in (index_url(set_number), table_url(set_number, "expedition"), table_url(set_number, "callto-chaos")):
        try:
            slugs = list_tables(fetch(url), set_number)
        except Exception:
            continue
        if slugs:
            break
    tables = []
    for slug in slugs:
        url = table_url(set_number, slug)
        try:
            table = parse_table(fetch(url), slug, url)
        except Exception as exc:  # one broken table must not lose the others
            log(f"    {slug}: lỗi {exc}")
            continue
        if table is None:
            continue
        link_to_db(table, db)
        tables.append(table)
    if not tables:
        return None
    return {"version": REWARDS_VERSION, "set": set_number, "source": "LoLCHESS.GG", "url": index_url(set_number), "tables": tables}


def save_rewards(directory: str | Path, rewards: dict) -> bool:
    directory = Path(directory)
    path = directory / f"{rewards['set']}.json"
    text = json.dumps(rewards, ensure_ascii=False, separators=(",", ":")) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    directory.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True
