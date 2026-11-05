"""Full stats of a TFT season: champions, traits, items and augments.

Built from Community Dragon's game data (the same file that names the
patch notes): every champion's cost, traits, base stats and ability with its
numbers per star level; every trait's breakpoints; every item's stats and
recipe; every augment's text. Descriptions come with ``@Variable@``
placeholders, filled in here from the variables the game ships.

One file per season, ``data/tft_db/<set>.json``, published next to the page
and loaded when someone opens a stat sheet.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DB_VERSION = 8  # bump to rebuild every season's sheets on the next run
PLACEHOLDER = re.compile(r"@([A-Za-z0-9_{}.:]+?)(\*100)?@")
ICON_TEXT = {
    "scaleap": "SMPT",
    "scalead": "SMCK",
    "scalehealth": "Máu",
    "scalearmor": "Giáp",
    "scalemr": "Kháng phép",
    "scaleas": "Tốc đánh",
    "scalemana": "Năng lượng",
    "scalecrit": "Chí mạng",
    "scalecritmult": "Sát thương chí mạng",
    "scaledr": "Giảm sát thương",
    "scalesv": "Hút máu toàn phần",
    "scalerange": "Tầm đánh",
    "set": "",
    "tftbaseap": "SMPT",
    "tftbasead": "SMCK",
}
# Item stats worth listing on their own, with the unit the game stores them in.
ITEM_STATS = {
    "AD": ("SMCK", "%", 100),
    "AP": ("SMPT", "", 1),
    "AS": ("Tốc đánh", "%", 1),
    "Armor": ("Giáp", "", 1),
    "MagicResist": ("Kháng phép", "", 1),
    "Health": ("Máu", "", 1),
    "Mana": ("Năng lượng", "", 1),
    "CritChance": ("Chí mạng", "%", 1),
    "Omnivamp": ("Hút máu toàn phần", "%", 100),
    "StatOmnivamp": ("Hút máu toàn phần", "%", 100),
    "Durability": ("Chống chịu", "%", 100),
    "BonusDamage": ("Khuếch đại sát thương", "%", 100),
}


def fnv1a(name: str) -> str:
    """The "{xxxxxxxx}" key Community Dragon shows for a field it has no name for."""
    h = 0x811C9DC5
    for byte in name.lower().encode("utf-8"):
        h = ((h ^ byte) * 0x01000193) & 0xFFFFFFFF
    return "{%08x}" % h


def _num(value) -> str:
    if isinstance(value, bool) or value is None:
        return "?"
    if isinstance(value, (int, float)):
        rounded = round(float(value), 2)
        return str(int(rounded)) if rounded == int(rounded) else f"{rounded:g}".replace(".", ",")
    return str(value)


def _scaled(value, times100: bool):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value * 100 if times100 else value
    return value


def _per_star(values: list, times100: bool) -> str:
    """"200/300/450" from a variable's per-star-level values (index 1..3)."""
    if not isinstance(values, list) or not values:
        return "?"
    picked = values[1:4] if len(values) > 3 else values
    picked = [_scaled(v, times100) for v in picked]
    texts = [_num(v) for v in picked]
    return texts[0] if len(set(texts)) == 1 else "/".join(texts)


def _is_counter(line: str) -> bool:
    """A line that only shows a value during a game: "?", "Tổng thu nhập: ? Vàng",
    "Thưởng Hiện Tại: ?% SMCK ?% SMPT", "Lượt đổi: ? Máu: ?"."""
    if line == "?":
        return True
    if "?" not in line or ":" not in line or len(line) > 90 or re.search(r"[.!]", line):
        return False
    label, value = line.split(":", 1)
    if not label.strip() or "?" in label:
        return False
    words = re.sub(r"[?\d%/+,:\s-]+", " ", value).split()
    return len(words) <= 3


def clean(text: str | None) -> str:
    """Game markup to plain text: <br> to newlines, icons to words, tags gone."""
    if not text:
        return ""
    text = text.replace("\\n", "\n")  # some strings carry a literal backslash-n
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</?(?:li|row|expandRow)[^>]*>", "\n", text, flags=re.I)
    # Stat icons to words; "(%i:scaleAD%%i:scaleAP%)" reads "(SMCK+SMPT)".
    text = re.sub(
        r"(?:%i:[A-Za-z]+%)+",
        lambda m: "+".join(filter(None, (ICON_TEXT.get(w.lower(), "") for w in re.findall(r"%i:([A-Za-z]+)%", m[0])))),
        text,
    )
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"(\d%?)\((?=[^()\d])", r"\1 (", text)  # "405(SMCK)" -> "405 (SMCK)"
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    # In-game progress counters ("Đòn Đánh: ?", "(Hiện tại: ?)") only have a
    # value during a game: drop them rather than show a "?".
    text = re.sub(r"\(\s*(?:hiện tại|current|đã nhận|tiến độ)[^()]*\?\s*\)", "", text, flags=re.I)
    text = re.sub(r"\((tối đa|max)\s*\?\s*/\s*(\d+)\)", r"(\1 \2)", text, flags=re.I)
    # "(Mũ: ?)", "(?/6)", "(Máu: ?, Tốc Độ Đánh: ?%)": short asides holding a count.
    text = re.sub(r"\s*\((?=[^()]*\?)[^().!]{1,60}\)", "", text)
    lines = [" ".join(line.split()) for line in text.split("\n")]
    lines = ["" if _is_counter(line) else line for line in lines]
    lines = [re.sub(r"(?<=[.!])\s*\?$", "", line) for line in lines]
    out = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()


def fill(desc: str | None, lookup) -> str:
    """Replace @Name@ placeholders using ``lookup(name, times100) -> str | None``."""
    if not desc:
        return ""

    def sub(match):
        found = lookup(match[1], bool(match[2]))
        return found if found is not None else "?"

    return PLACEHOLDER.sub(sub, desc)


def _variables(entries) -> dict:
    """Ability variables as {lower name: values}."""
    out = {}
    for entry in entries or []:
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            out[entry["name"].lower()] = entry.get("value")
    return out


def _ability_lookup(variables: dict):
    def lookup(name: str, times100: bool):
        key = name.lower()
        candidates = [key]
        # "ModifiedDamage" is computed by the game from "Damage" (and AP/AD).
        for prefix in ("modified", "total", "tooltip", "base", "calculated", "displayed"):
            if key.startswith(prefix):
                candidates.append(key[len(prefix):])
        candidates += [f"base{key}", f"{key}base"]
        for candidate in candidates:
            for variant in (candidate, fnv1a(candidate)):
                if variant in variables:
                    return _per_star(variables[variant], times100)
        return None

    return lookup


def _flat_lookup(effects: dict, extra: dict | None = None):
    lowered = {str(k).lower(): v for k, v in (effects or {}).items()}
    for k, v in (extra or {}).items():
        lowered.setdefault(k.lower(), v)

    def lookup(name: str, times100: bool):
        key = name.lower()
        for candidate in (key, key.replace("modified", ""), key.replace("total", "")):
            for variant in (candidate, fnv1a(candidate)):
                if variant in lowered:
                    return _num(_scaled(lowered[variant], times100))
        return None

    return lookup


def _asset(path, base: str) -> str | None:
    if not path or not isinstance(path, str):
        return None
    path = path.strip().lower()
    if path.startswith("http"):
        return path
    return base + re.sub(r"\.(tex|dds)$", ".png", path).lstrip("/")


def _champion(raw: dict, base: str) -> dict:
    stats = raw.get("stats") or {}
    ability = raw.get("ability") or {}
    variables = _variables(ability.get("variables"))
    # Newer sets ship abilities without their numbers: those read "?" here and
    # the page shows the values from the latest patch notes instead.
    desc = clean(fill(ability.get("desc"), _ability_lookup(variables)))
    return {
        "id": raw.get("apiName"),
        "name": raw.get("name"),
        "cost": raw.get("cost"),
        "traits": [t for t in raw.get("traits") or [] if isinstance(t, str)],
        "role": raw.get("role"),
        "icon": _asset(raw.get("squareIcon") or raw.get("tileIcon") or raw.get("icon"), base),
        "splash": _asset(raw.get("tileIcon") or raw.get("icon"), base),
        "stats": {
            "hp": stats.get("hp"),
            "mana": stats.get("mana"),
            "initialMana": stats.get("initialMana"),
            "damage": stats.get("damage"),
            "armor": stats.get("armor"),
            "magicResist": stats.get("magicResist"),
            "attackSpeed": stats.get("attackSpeed"),
            "range": stats.get("range"),
            "critChance": stats.get("critChance"),
            "critMultiplier": stats.get("critMultiplier"),
        },
        "ability": {
            "name": ability.get("name"),
            "icon": _asset(ability.get("icon"), base),
            "desc": desc,
            "variables": [
                {"name": entry["name"], "value": _per_star(entry.get("value"), False)}
                for entry in ability.get("variables") or []
                if isinstance(entry, dict) and isinstance(entry.get("name"), str) and not entry["name"].startswith("{")
            ],
        },
    }


def _trait(raw: dict, base: str) -> dict:
    effects = [e for e in raw.get("effects") or [] if isinstance(e, dict)]
    desc = raw.get("desc") or ""
    # Breakpoint rows: <expandRow> is a template for every breakpoint,
    # <row> lines map to breakpoints in order.
    template = re.search(r"<expandRow>(.*?)</expandRow>", desc, re.S | re.I)
    rows = re.findall(r"<row>(.*?)</row>", desc, re.S | re.I)
    intro = re.split(r"<expandRow>|<row>", desc, maxsplit=1, flags=re.I)[0]
    first = effects[0].get("variables") if effects else {}
    breakpoints = []
    for i, effect in enumerate(effects):
        extra = {"MinUnits": effect.get("minUnits"), "MaxUnits": effect.get("maxUnits")}
        lookup = _flat_lookup(effect.get("variables") or {}, extra)
        source = template[1] if template else rows[i] if i < len(rows) else ""
        breakpoints.append(
            {
                "min": effect.get("minUnits"),
                "max": effect.get("maxUnits"),
                "style": effect.get("style"),
                "text": clean(fill(source, lookup)),
                "variables": {
                    str(k): _num(v) for k, v in (effect.get("variables") or {}).items() if not str(k).startswith("{")
                },
            }
        )
    return {
        "id": raw.get("apiName"),
        "name": raw.get("name"),
        "icon": _asset(raw.get("icon"), base),
        "desc": clean(fill(intro, _flat_lookup(first or {}))),
        "breakpoints": breakpoints,
    }


# Hidden tags of augments, named by what they hold in every season (15-18):
# augments only in a few variants lack TAG_IN_POOL; TAG_NOT_AT marks the stage
# an augment is never offered at ("Triệu Gọi Hỗn Mang": not 2-1, not 3-2 -> 4-2 only).
TAG_IN_POOL = "{b72bd3bf}"
TAG_NOT_AT = {"{d02ae323}": "2-1", "{d12ae4b6}": "3-2", "{d22ae649}": "4-2"}
TAG_TIER = {"{d11fd6d5}": 1, "{ce1fd21c}": 2, "{cf1fd3af}": 3}
STAGES = ("2-1", "3-2", "4-2")
COMPONENTS = {
    "tft_item_bfsword", "tft_item_recurvebow", "tft_item_needlesslylargerod", "tft_item_tearofthegoddess",
    "tft_item_chainvest", "tft_item_negatroncloak", "tft_item_giantsbelt", "tft_item_sparringgloves",
    "tft_item_spatula", "tft_item_fryingpan",
}


def item_kind(raw: dict) -> str:
    """completed, component, radiant, artifact, emblem, support, mechanic, consumable or other."""
    api = str(raw.get("apiName") or "").lower()
    tags = {str(t).lower() for t in raw.get("tags") or []}
    icon = str(raw.get("icon") or "").lower()
    name = str(raw.get("name") or "")
    if "radiant" in api:
        return "radiant"
    if "ornn" in api or "artifact" in api:
        return "artifact"
    if "emblem" in api or name.startswith("Ấn ") or fnv1a("traititem") in tags:
        return "emblem"
    if "support" in api or fnv1a("tft_support") in tags:
        return "support"
    if "consumable" in tags or "consumable" in api:
        return "consumable"
    if api in COMPONENTS or "component" in tags:
        return "component"
    if len(raw.get("composition") or []) == 2:
        return "completed"
    if "zaps/" in icon or api.startswith("da_") or re.match(r"tft\d+_(?!item)", api):
        return "mechanic"
    return "other"


def _item(raw: dict, base: str) -> dict:
    effects = raw.get("effects") or {}
    stats = []
    for key, value in effects.items():
        if key in ITEM_STATS and isinstance(value, (int, float)) and value:
            label, unit, times = ITEM_STATS[key]
            stats.append({"label": label, "value": f"{_num(value * times)}{unit}"})
    return {
        "id": raw.get("apiName"),
        "name": raw.get("name"),
        "icon": _asset(raw.get("icon"), base),
        "desc": clean(fill(raw.get("desc"), _flat_lookup(effects))),
        "stats": stats,
        "from": [c for c in raw.get("composition") or [] if isinstance(c, str)],
        "kind": item_kind(raw),
        "unique": bool(raw.get("unique")),
        "traits": [t for t in raw.get("associatedTraits") or [] if isinstance(t, str)],
    }


_TIER = re.compile(r"(?:^|[_\s-])(III|II|I)$|(\d)$")


def _augment(raw: dict, base: str) -> dict:
    entry = _item(raw, base)
    entry.pop("kind", None)
    tags = set(raw.get("tags") or [])
    entry["pool"] = TAG_IN_POOL in tags
    if TAG_IN_POOL not in tags and not tags & TAG_NOT_AT.keys() and str(raw.get("apiName") or "").startswith("DA_"):
        # Newer "DA_" records carry no tags at all: offered or not, and when, is unknown.
        entry["pool"] = None
    banned = {TAG_NOT_AT[t] for t in tags if t in TAG_NOT_AT}
    entry["stages"] = [stage for stage in STAGES if stage not in banned] if entry["pool"] is not None else None
    icon = str(raw.get("icon") or "").lower()
    tier = next((TAG_TIER[t] for t in tags if t in TAG_TIER), None)
    for word, value in (("prismatic", 3), ("-iii", 3), ("_iii", 3), ("3.", 3), ("gold", 2), ("-ii", 2), ("_ii", 2), ("2.", 2), ("silver", 1), ("-i.", 1), ("_i.", 1), ("1.", 1)):
        if tier is not None:
            break
        if word in icon:
            tier = value
            break
    entry["tier"] = tier
    return entry


def _is_augment(raw: dict) -> bool:
    api = str(raw.get("apiName") or "").lower()
    return "augment" in api or "/augments/" in str(raw.get("icon") or "").lower()


def build_db(data: dict, set_number: int, base: str) -> dict | None:
    """The stat sheets of one season, or None when the game data lacks it."""
    sets = list(data.get("setData") or [])
    if isinstance(data.get("sets"), dict):
        sets += [dict(v, number=v.get("number", int(k)) if str(k).isdigit() else v.get("number")) for k, v in data["sets"].items()]
    # Several entries can share a number (game modes); the one with most champions is the set.
    candidates = [s for s in sets if isinstance(s, dict) and s.get("number") == set_number]
    if not candidates:
        return None
    entry = max(candidates, key=lambda s: len(s.get("champions") or []))
    champions = [
        _champion(c, base)
        for c in entry.get("champions") or []
        if isinstance(c, dict) and c.get("traits") and isinstance(c.get("cost"), int) and c.get("cost", 0) <= 7
    ]
    traits = [_trait(t, base) for t in entry.get("traits") or [] if isinstance(t, dict) and t.get("name")]

    all_items = [i for i in data.get("items") or [] if isinstance(i, dict) and i.get("name") and i.get("apiName")]
    by_id = {i["apiName"]: i for i in all_items}
    prefix = f"tft{set_number}_"
    listed_items = entry.get("items")
    listed_augments = entry.get("augments")
    if isinstance(listed_augments, list) and listed_augments:
        augments_raw = [by_id[a] for a in listed_augments if isinstance(a, str) and a in by_id]
    else:
        augments_raw = [i for i in all_items if _is_augment(i) and str(i["apiName"]).lower().startswith((prefix, "tft_augment"))]
    if isinstance(listed_items, list) and listed_items:
        items_raw = [by_id[a] for a in listed_items if isinstance(a, str) and a in by_id and not _is_augment(by_id[a])]
    else:
        items_raw = [
            i
            for i in all_items
            if not _is_augment(i)
            and str(i["apiName"]).lower().startswith((prefix, "tft_item_"))
            and i.get("desc")
            and "debug" not in str(i["apiName"]).lower()
        ]
    # Test items of the practice tool and the anniversary event's items are not
    # part of a season.
    items_raw = [i for i in items_raw if not re.match(r"tft_item_debug|tftevent", str(i["apiName"]).lower())]
    items = [_item(i, base) for i in items_raw]
    augments = [_augment(a, base) for a in augments_raw if a.get("desc")]
    if not any(a["pool"] for a in augments):  # data without the tag: treat all as offered
        for augment in augments:
            augment["pool"] = True
            augment["stages"] = augment["stages"] or list(STAGES)
    # Variants share a name with the offered augment: keep the offered one.
    offered = {(a["name"], a["tier"]) for a in augments if a["pool"]}
    offered_names = {a["name"] for a in augments if a["pool"]}
    for augment in augments:
        # "Hộp Pandora I" beside the offered "Hộp Pandora": a variant, not offered.
        if augment["pool"] is None and re.sub(r"\s*(?:I{1,3}|\+{1,2})$", "", augment["name"]) in offered_names:
            augment["pool"] = False
    kept, seen_aug = [], set()
    for augment in augments:
        key = (augment["name"], augment["tier"])
        if (augment["pool"] is not True and key in offered) or (key, augment["pool"]) in seen_aug:
            continue
        seen_aug.add((key, augment["pool"]))
        kept.append(augment)
    augments = kept
    names = {i["id"]: i["name"] for i in items}
    for item in items:  # recipe ids to names
        item["from"] = [names.get(c) or by_id.get(c, {}).get("name") or c for c in item["from"]]
    unique_items = merge_items(items)
    return {
        "version": DB_VERSION,
        "set": set_number,
        "name": entry.get("name"),
        "champions": sorted(champions, key=lambda c: (c["cost"] or 0, c["name"] or "")),
        "traits": sorted(traits, key=lambda t: t["name"] or ""),
        "items": unique_items,
        "augments": sorted(augments, key=lambda a: ({True: 0, None: 1, False: 2}[a["pool"]], a.get("tier") or 0, a["name"] or "")),
    }


def merge_items(items: list[dict]) -> list[dict]:
    """One entry per item name: newer sets list an item twice (a "DA_" record
    without text and the classic one with its stats), so the two are merged."""
    merged: dict[str, dict] = {}
    for item in items:
        name = item.get("name")
        current = merged.get(name)
        if current is None:
            merged[name] = dict(item)
            continue
        for key in ("desc", "stats", "from", "icon"):
            if not current.get(key) and item.get(key):
                current[key] = item[key]
        if current.get("kind") in ("other", "mechanic") and item.get("kind") not in ("other", "mechanic", None):
            current["kind"] = item["kind"]
    for item in merged.values():
        if not item.get("desc") and item.get("kind") == "emblem" and str(item.get("name", "")).startswith("Ấn "):
            item["desc"] = f"Người mang trang bị này được tính thêm tộc/hệ {item['name'][3:]}."
    return list(merged.values())


def save_db(directory: str | Path, db: dict) -> bool:
    directory = Path(directory)
    path = directory / f"{db['set']}.json"
    text = json.dumps(db, ensure_ascii=False, separators=(",", ":")) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    directory.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def describe(data: dict, set_number: int) -> str:
    """A short look at the raw game data, for the CI log."""
    lines = [f"top-level keys: {sorted(data)[:20]}"]
    for entry in data.get("setData") or []:
        if isinstance(entry, dict) and entry.get("number") == set_number:
            lines.append(f"setData {entry.get('number')} {entry.get('name')} {entry.get('mutator')}: keys {sorted(entry)}")
            champs = entry.get("champions") or []
            if champs:
                lines.append(f"  champion sample: {json.dumps(champs[0], ensure_ascii=False)[:1500]}")
            traits = entry.get("traits") or []
            if traits:
                lines.append(f"  trait sample: {json.dumps(traits[0], ensure_ascii=False)[:1200]}")
            for key in ("items", "augments"):
                if isinstance(entry.get(key), list):
                    lines.append(f"  {key}: {len(entry[key])} e.g. {entry[key][:3]}")
    def summary(where, entry):
        champs = [c for c in entry.get("champions") or [] if isinstance(c, dict)]
        with_vars = [c for c in champs if (c.get("ability") or {}).get("variables")]
        lines.append(f"{where}: number={entry.get('number')} name={entry.get('name')} mutator={entry.get('mutator')} champions={len(champs)} with variables={len(with_vars)} e.g. {[c.get('apiName') for c in champs[:4]]}")
        if with_vars:
            lines.append(f"    with-vars sample: {json.dumps(with_vars[-1], ensure_ascii=False)[:900]}")
    for entry in data.get("setData") or []:
        if isinstance(entry, dict) and entry.get("number") in (set_number, set_number - 1):
            summary("setData", entry)
    for key, entry in (data.get("sets") or {}).items():
        if isinstance(entry, dict):
            summary(f"sets[{key}]", entry)
    items = data.get("items") or []
    sample_item = next((i for i in items if "TFT_Item_" in str(i.get("apiName"))), None)
    sample_aug = next((i for i in items if "Augment" in str(i.get("apiName")) and f"TFT{set_number}" in str(i.get("apiName"))), None)
    lines.append(f"item sample: {json.dumps(sample_item, ensure_ascii=False)[:1200]}")
    lines.append(f"augment sample: {json.dumps(sample_aug, ensure_ascii=False)[:1200]}")
    return "\n".join(lines)
