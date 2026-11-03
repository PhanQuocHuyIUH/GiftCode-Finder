"""Teamfight Tactics patch notes: every buff, nerf and change, patch by patch.

Riot posts each patch's notes as an article. This module lists those articles,
reads each one and turns its bullet points into structured changes::

    {"subject": "Ahri", "stat": "Mana", "before": "0/60", "after": "0/50",
     "dir": "buff", "kind": "champions", ...}

``dir`` is worked out from the numbers (lower mana or cooldown is a buff,
higher damage is a buff) unless the heading already says "Buffs"/"Nerfs".
Names of champions, traits, items and augments (and their icons) come from
Community Dragon, so a line like "Ahri Mana: 0/60 ⇒ 0/50" knows that "Ahri"
is the champion and "Mana" the stat.

The history lives in ``data/tft.json``: articles are read once, so earlier
patches stay on the site after Riot's listing drops them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml
from bs4 import BeautifulSoup, NavigableString, Tag

from .config import ConfigError
from .fetch import Fetcher

# Bump when parsing changes: every patch still listed by Riot is then read again.
PARSER_VERSION = 3
KINDS = ("champions", "traits", "items", "augments", "mechanics", "modes", "fixes", "other")
DIRS = ("buff", "nerf", "adjust", "new", "removed", "fix")

ARROW = re.compile(r"\s*(?:⇒|=>|→|->|➔|➜|⟶|⮕|»)\s*")
NUMBER = re.compile(r"-?\d+(?:[.,]\d+)*")
VERSION_IN_TITLE = re.compile(r"(?<![\d.])(\d{1,2})\.(\d{1,2})([a-z])?(?![\d.])", re.I)
VERSION_IN_URL = re.compile(r"(?:patch|cap-nhat|phien-ban|ban)-(\d{1,2})-(\d{1,2})([a-z])?(?=-|/|$)", re.I)
NOT_NOTES = re.compile(r"preview|xem trước|xem-truoc|rundown|tóm tắt trước|teaser", re.I)
TIER = re.compile(
    r"^(?:tier|bậc|cấp|tướng|champions?|units?)\s*\d\b|^\d\s*[-–]?\s*(?:cost|vàng|gold|tiền)\b|^\d\s*★|^[1-5]\s*$",
    re.I,
)
# A ", " that starts another "Stat: old ⇒ new" in the same bullet.
MULTI_SPLIT = re.compile(r"[,;]\s+(?=[^,;⇒>]{2,60}:\s*[^⇒]{1,60}?(?:⇒|=>|→|->))")
DATE_HEAD = re.compile(r"^(?:ngày|day|date)?\s*\d{1,2}\s*/\s*\d{1,2}(?:\s*/\s*\d{2,4})?$|^(?:ngày|day)\s+\d", re.I)
HIGHLIGHTS = re.compile(r"highlight|tiêu điểm|điểm nhấn", re.I)
BUFF_HEAD = re.compile(r"\bbuffs?\b|tăng sức mạnh|được tăng|tăng cường", re.I)
NERF_HEAD = re.compile(r"\bnerfs?\b|giảm sức mạnh|bị giảm|suy yếu", re.I)
NEW_LINE = re.compile(r"^(?:new|mới|thêm mới|bổ sung)\b[:\s!]|^(?:new|mới)\s*[-–:]", re.I)
REMOVED_LINE = re.compile(r"\b(?:removed|disabled|no longer|loại bỏ|gỡ bỏ|xóa bỏ|xoá bỏ|bị loại|vô hiệu|không còn)\b", re.I)
# For these stats a smaller number is better for whoever owns them.
LOWER_IS_BETTER = re.compile(
    r"\bmana\b|năng lượng|cooldown|hồi chiêu|cast time|thời gian (?:niệm|tung|vận)|\bdelay\b|độ trễ|"
    r"lockout|\bcosts?\b|\bprice\b|\bgiá\b|chi phí|reroll|\bxp\b|kinh nghiệm cần|"
    r"wind-?up|channel(?:ing)? time",
    re.I,
)
# ...unless it is something given back: "Mana Refund", "Starting Mana", "Hồi năng lượng".
MORE_IS_BETTER = re.compile(
    r"refund|regen|restor|gain|grant|start(?:ing)?|reduction|giảm|hồi(?! chiêu)|hoàn|nhận|khởi đầu|ban đầu|gold|vàng",
    re.I,
)

# Which section a heading opens. Checked in this order; English and Vietnamese.
SECTION_KINDS = [
    ("fixes", r"\bbugs?\b|sửa lỗi|lỗi\b"),
    ("mechanics", r"hệ thống|\bsystems?\b"),
    ("augments", r"augment|lõi|nâng cấp|anomal|dị biến"),
    ("traits", r"trait|tộc|(?<!\w)hệ(?!\w)|origin|\bclass"),
    ("items", r"\bitems?\b|trang bị|emblem|(?<!\w)ấn(?!\w)|artifact|tạo tác|radiant|ánh sáng|component|mảnh ghép"),
    ("champions", r"champion|\bunits?\b|tướng|đơn vị|tier \d|\d-cost"),
    ("modes", r"double up|hyper roll|tranh tài|siêu tốc|chế độ|\bmodes?\b|ranked|xếp hạng|revival|tái hiện|tocker"),
    (
        "mechanics",
        r"mechanic|gameplay|cơ chế|lối chơi|econom|kinh tế|portal|cổng|encounter|"
        r"big change|large change|small change|thay đổi lớn|thay đổi nhỏ|player damage|sát thương người chơi|loot|"
        r"chiến lợi phẩm|carousel|vòng quay|odds|tỉ lệ|tỷ lệ|shop|cửa hàng|pve|creep|quái",
    ),
]
SECTION_KINDS = [(kind, re.compile(pattern, re.I)) for kind, pattern in SECTION_KINDS]
# Sections about skins, videos and such: no balance changes to show.
SKIP_SECTIONS = re.compile(
    r"vật phẩm trang trí|trang phục|cosmetic|skins?\b|phim ngắn|cinematic|teaser|video|lịch trình phát triển|roadmap|"
    r"cấu hình|\bspecs?\b|bài viết liên quan|related articles|riot client|đăng nhập qr|gói đặt mua|pre-?order|"
    r"\bpass\b|chapter|thông báo đtcl|bản đồ sao|star map|tàng thư|linh thú|little legend|chưởng lực|ghi chú hiệu năng|"
    r"performance note",
    re.I,
)
# "VẬT PHẨM TRANG TRÍ ĐẠI NGÀN KỲ BÍ" in a set's first patch names the set.
SET_NAME_HEAD = re.compile(
    r"^(?:phim ngắn|vật phẩm trang trí|lịch trình phát triển|teaser (?:&|và) video lịch trình phát triển)\s+(?P<vi>.+)$"
    r"|^(?P<en>.+?)\s+(?:cinematic|cosmetics)$",
    re.I,
)
NOT_SET_NAME = re.compile(r"chuyển đổi|khả dụng|được|sẽ|transferred|available|vault", re.I)


@dataclass
class TftConfig:
    listings: list[str]
    max_patches: int = 40
    refresh_hours: int = 6
    names_url: str | None = None
    asset_base: str = "https://raw.communitydragon.org/latest/game/"
    sets: dict = field(default_factory=dict)
    min_version: str | None = None


def load_tft_config(path: str | Path) -> TftConfig | None:
    path = Path(path)
    if not path.exists():
        return None
    try:
        raw = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("tft") or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Không đọc được {path}: {exc}") from exc
    listings = raw.get("listings") or []
    if not listings or not all(isinstance(u, str) and u.startswith("http") for u in listings):
        raise ConfigError(f"{path}: 'tft.listings' phải là danh sách link trang patch notes")
    return TftConfig(
        listings=listings,
        max_patches=int(raw.get("max_patches", 40)),
        refresh_hours=int(raw.get("refresh_hours", 6)),
        names_url=raw.get("names_url"),
        asset_base=raw.get("asset_base") or TftConfig.asset_base,
        sets={str(k): str(v) for k, v in (raw.get("sets") or {}).items()},
        min_version=str(raw["min_version"]) if raw.get("min_version") else None,
    )


# --- Listing ----------------------------------------------------------------


@dataclass
class Article:
    url: str
    title: str
    version: str
    published_at: str | None = None
    image: str | None = None
    locale: str | None = None


def version_of(title: str, url: str) -> str | None:
    match = VERSION_IN_TITLE.search(title or "")
    if not match:
        match = VERSION_IN_URL.search(urlparse(url).path)
    if not match:
        return None
    major, minor, letter = match.groups()
    return f"{int(major)}.{int(minor)}{(letter or '').lower()}"


def version_key(version: str) -> tuple:
    match = re.match(r"(\d+)\.(\d+)([a-z]?)", version)
    return (int(match[1]), int(match[2]), match[3]) if match else (0, 0, version)


def _walk_json(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _next_data(soup: BeautifulSoup):
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except ValueError:
        return None


def _json_url(node: dict) -> str | None:
    action = node.get("action")
    if isinstance(action, dict):
        payload = action.get("payload")
        if isinstance(payload, dict) and isinstance(payload.get("url"), str):
            return payload["url"]
    for key in ("url", "href", "link"):
        value = node.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict) and isinstance(value.get("url"), str):
            return value["url"]
    return None


def _json_image(node: dict) -> str | None:
    for key in ("media", "image", "banner", "thumbnail"):
        value = node.get(key)
        if isinstance(value, dict) and isinstance(value.get("url"), str):
            return value["url"]
        if isinstance(value, str) and value.startswith("http"):
            return value
    return None


def _is_notes(title: str, url: str) -> bool:
    text = f"{title} {url}"
    if NOT_NOTES.search(text):
        return False
    return bool(re.search(r"patch|cập nhật|cap-nhat|phiên bản|phien-ban|notes|ghi chú", text, re.I))


def _locale(url: str) -> str | None:
    match = re.match(r"/([a-z]{2}-[a-z]{2})/", urlparse(url).path)
    return match[1] if match else None


def parse_listing(html: str, base_url: str) -> list[Article]:
    """Patch note articles linked from a Riot news page, newest first."""
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, Article] = {}

    def add(url, title, date=None, image=None):
        if not url or not title:
            return
        url = urljoin(base_url, url)
        title = " ".join(str(title).split())
        version = version_of(title, url)
        if not version or not _is_notes(title, url):
            return
        old = found.get(version)
        if old is None:
            found[version] = Article(url, title, version, date, image, _locale(url))
        elif old.url != url and date and old.published_at and date[:10] > old.published_at[:10]:
            # Riot reused a number ("13.6" in 2023 and in 2025): keep the newer article.
            found[version] = Article(url, title, version, date, image or old.image, _locale(url))
        elif old.url == url:
            old.published_at = old.published_at or date
            old.image = old.image or image

    data = _next_data(soup)
    if data is not None:
        for node in _walk_json(data):
            title = node.get("title")
            if isinstance(title, str):
                add(_json_url(node), title, node.get("publishedAt") or node.get("date"), _json_image(node))
    for link in soup.find_all("a", href=True):
        heading = link.find(["h2", "h3", "h4"]) or link.find(attrs={"data-testid": re.compile("title")})
        title = heading.get_text(" ", strip=True) if heading else link.get("aria-label") or link.get_text(" ", strip=True)
        stamp = link.find("time")
        image = link.find("img")
        add(
            link["href"],
            title,
            stamp.get("datetime") if stamp else None,
            (image.get("src") or image.get("data-src")) if image else None,
        )
    return sorted(found.values(), key=lambda a: version_key(a.version), reverse=True)


# --- Names and icons (Community Dragon) --------------------------------------


@dataclass
class Names:
    """Known names, longest first, so "Kai'Sa" wins over "Kai"."""

    entries: list[tuple[str, str, str | None]] = field(default_factory=list)  # (lower name, kind, icon)
    display: dict[str, str] = field(default_factory=dict)

    def match(self, text: str):
        """The known name ``text`` starts with: (name, kind, icon, rest)."""
        low = text.lower()
        for name, kind, icon in self.entries:
            if low.startswith(name) and (len(low) == len(name) or not low[len(name)].isalnum()):
                return self.display[name], kind, icon, text[len(name):].strip(" :,–-")
        return None

    def find(self, text: str):
        low = text.lower().strip(" :")
        bare = re.sub(r"\s*\([^)]*\)$", "", low)
        for name, kind, icon in self.entries:
            if low == name or bare == name:
                return (self.display[name] if low == name else text.strip(" :")), kind, icon
        return None


def _asset(path: str | None, base: str) -> str | None:
    if not path or not isinstance(path, str):
        return None
    path = path.strip().lower()
    if path.startswith("http"):
        return path
    path = re.sub(r"\.(tex|dds)$", ".png", path)
    return base + path.lstrip("/")


def build_names(data: dict, set_number: int | None, base: str) -> Names:
    names = Names()
    seen: dict[str, tuple[str, str | None]] = {}

    def add(name, kind, icon):
        if not isinstance(name, str):
            return
        clean = " ".join(re.sub(r"<[^>]+>", "", name).split())
        low = clean.lower()
        if len(low) < 2 or low in seen:
            return
        seen[low] = (kind, _asset(icon, base))
        names.display[low] = clean

    sets = data.get("setData") or []
    if isinstance(data.get("sets"), dict):
        sets = sets + list(data["sets"].values())
    numbers = [s.get("number") for s in sets if isinstance(s, dict) and isinstance(s.get("number"), int)]
    wanted = set_number if set_number in numbers else (max(numbers) if numbers else None)
    for entry in sets:
        if not isinstance(entry, dict) or entry.get("number") != wanted:
            continue
        for champ in entry.get("champions") or []:
            if isinstance(champ, dict) and champ.get("traits"):
                add(champ.get("name"), "champions", champ.get("squareIcon") or champ.get("tileIcon") or champ.get("icon"))
        for trait in entry.get("traits") or []:
            if isinstance(trait, dict):
                add(trait.get("name"), "traits", trait.get("icon"))
    for item in data.get("items") or []:
        if not isinstance(item, dict):
            continue
        api = str(item.get("apiName") or "")
        kind = "augments" if "augment" in api.lower() or "/augments/" in str(item.get("icon", "")).lower() else "items"
        add(item.get("name"), kind, item.get("icon"))
    names.entries = sorted(((low, kind, icon) for low, (kind, icon) in seen.items()), key=lambda e: -len(e[0]))
    return names


# --- Article ----------------------------------------------------------------


@dataclass
class _Section:
    title: str
    kind: str
    notes: list[str] = field(default_factory=list)
    changes: list[dict] = field(default_factory=list)


def _text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if isinstance(node, Tag) else " ".join(str(node).split())


def _own_text(li: Tag) -> str:
    """Text of ``li`` without its nested lists."""
    parts = []
    for child in li.children:
        if isinstance(child, Tag) and child.name in ("ul", "ol"):
            continue
        parts.append(child.get_text(" ", strip=True) if isinstance(child, Tag) else str(child))
    return " ".join(" ".join(parts).split())


def _numbers(text: str) -> list[float]:
    values = []
    for raw in NUMBER.findall(text):
        # "1.000" (Vietnamese) and "1,000" (English) are thousands; "0,5" and "0.5" are halves.
        if re.fullmatch(r"-?\d{1,3}(?:[.,]\d{3})+", raw):
            raw = re.sub(r"[.,]", "", raw)
        values.append(float(raw.replace(",", ".")))
    return values


def direction(stat: str, before: str, after: str) -> str:
    """"buff", "nerf" or "adjust" from the numbers on each side of the arrow."""
    old, new = _numbers(before), _numbers(after)
    if not old or not new:
        return "adjust"
    if len(old) == len(new):
        ups = sum(n > o for o, n in zip(old, new))
        downs = sum(n < o for o, n in zip(old, new))
        if ups and downs:
            return "adjust"
        trend = 1 if ups else -1 if downs else 0
    else:
        trend = (sum(new) / len(new) > sum(old) / len(old)) - (sum(new) / len(new) < sum(old) / len(old))
    if trend == 0:
        return "adjust"
    if LOWER_IS_BETTER.search(stat or "") and not MORE_IS_BETTER.search(stat or ""):
        trend = -trend
    return "buff" if trend > 0 else "nerf"


def kind_of(title: str) -> str | None:
    for name, pattern in SECTION_KINDS:
        if pattern.search(title):
            return name
    return None


class _Parser:
    def __init__(self, names: Names | None):
        self.names = names or Names()
        self.sections: list[_Section] = []
        self.section: _Section | None = None
        self.sub: str | None = None  # the h3/h4 above the current list
        self.highlights: str | None = None
        self.highlights_sure = False
        self.icons: dict[str, str] = {}
        self.titles: list[str] = []
        self.subkind: str | None = None  # set by a "Champions"/"Tướng" heading inside a section
        self.date: str | None = None  # "NGÀY 22/10": when a mid-patch change went live

    # Sections and headings
    def open_section(self, title: str) -> None:
        self.titles.append(title)
        self.section = _Section(title, kind_of(title) or "other")
        self.sub = None
        self.subkind = None
        self.date = None
        if not SKIP_SECTIONS.search(title):
            self.sections.append(self.section)

    def current(self) -> _Section:
        if self.section is None:
            self.open_section("Tổng quan")
        return self.section

    # Changes
    def add(self, text: str, subject: str | None = None, group: str | None = None) -> None:
        text = " ".join(text.split())
        if len(text) < 3:
            return
        # "Damage: 700 ⇒ 1.000, Stun: 1,5 giây ⇒ 3 giây": one change per stat.
        if len(ARROW.findall(text)) > 1:
            parts = MULTI_SPLIT.split(text)
            if len(parts) > 1:
                for part in parts:
                    self.add(part, subject, group)
                return
        section = self.current()
        heading = " ".join(filter(None, (section.title, self.sub, group)))
        parts = ARROW.split(text, maxsplit=1)
        stat, before, after = "", "", ""
        if len(parts) == 2:
            left, after = parts
            if ":" in left:
                stat, before = left.rsplit(":", 1)
            else:
                before = left
            stat, before = stat.strip(), before.strip()
        base = self.subkind or section.kind
        kind = base
        icon = None
        generic = base in ("other", "mechanics", "modes")
        # "Ahri Mana" -> subject Ahri, stat Mana.
        if not subject and stat:
            match = self.names.match(stat)
            if match:
                subject, name_kind, icon, stat = match
                kind = name_kind if generic else kind
        if not subject and not stat and len(parts) == 1:
            match = self.names.match(text)
            if match and match[3]:
                subject, name_kind, icon = match[0], match[1], match[2]
                kind = name_kind if generic else kind
        if subject and icon is None:
            known = self.names.find(subject)
            if known:
                subject, name_kind, icon = known
                if generic:
                    kind = name_kind
        if subject and icon:
            self.icons[subject] = icon

        if base == "fixes":
            dir_ = "fix"
        elif NEW_LINE.search(text):
            dir_ = "new"
        elif len(parts) == 1 and REMOVED_LINE.search(text):
            dir_ = "removed"
        elif BUFF_HEAD.search(heading) and not NERF_HEAD.search(heading):
            dir_ = "buff"
        elif NERF_HEAD.search(heading) and not BUFF_HEAD.search(heading):
            dir_ = "nerf"
        elif len(parts) == 2:
            if kind == "champions" and re.fullmatch(r"(?i)cost|giá|giá tiền|bậc", stat):
                dir_ = "adjust"
            else:
                dir_ = direction(stat, before, after)
        else:
            dir_ = "adjust"
        change = {"subject": subject, "stat": stat or None, "before": before or None, "after": after or None,
                  "dir": dir_, "kind": kind}
        if not (before and after):
            change["text"] = text  # otherwise "stat: before ⇒ after" says it all
        if group:
            change["group"] = group
        if self.date:
            change["date"] = self.date.capitalize() if self.date.isupper() else self.date
        section.changes.append(change)

    def li(self, li: Tag, subject: str | None, group: str | None) -> None:
        own = _own_text(li)
        nested = [n for n in li.find_all(["ul", "ol"], recursive=False)]
        if nested:
            label = own.strip(" :")
            inner_subject, inner_group = subject, group
            if ARROW.search(own):
                self.add(own, subject, group)
            elif TIER.search(label):
                inner_group = label
            elif label:
                # "Caitlyn" over its changes: the label is what they are about.
                inner_subject = label
                if subject and subject != label:
                    inner_group = " · ".join(filter(None, (group, subject)))
            for lst in nested:
                self.items(lst.find_all("li", recursive=False), inner_subject, inner_group)
            return
        # "<strong>Ahri</strong>: Mana 0/60 ⇒ 0/50"
        strong = li.find(["strong", "b"], recursive=False)
        if not subject and strong and own.startswith(_text(strong)) and len(_text(strong)) < 40:
            head = _text(strong).strip(" :")
            rest = own[len(_text(strong)):].strip(" :")
            if rest and not ARROW.search(head) and self.names.find(head):
                subject = head
                own = rest if ARROW.search(rest) or ":" not in rest else rest
        self.add(own, subject, group)

    def list(self, node: Tag) -> None:
        subject, group = self._sub_context()
        self.items(node.find_all("li", recursive=False), subject, group)

    def items(self, items: list[Tag], subject: str | None, group: str | None) -> None:
        current, current_group = subject, group
        for i, li in enumerate(items):
            own = _own_text(li)
            nxt = items[i + 1] if i + 1 < len(items) else None
            # A flat list where a bare name ("Đổ Xúc Xắc") heads the lines after it.
            if (
                not li.find(["ul", "ol"], recursive=False)
                and not ARROW.search(own)
                and 0 < len(own) <= 40
                and not re.search(r"[.!?:]$|[.!?] ", own)
                and nxt is not None
                and ARROW.search(_own_text(nxt))
                and not nxt.find(["ul", "ol"], recursive=False)
            ):
                current = own
                current_group = " · ".join(filter(None, (group, subject))) or None
                continue
            self.li(li, current, current_group)

    def heading(self, text: str) -> None:
        text = (text or "").strip(" :")
        # "TƯỚNG", "TỘC/HỆ", "TRANG BỊ"...: a category inside the section, not a subject.
        if DATE_HEAD.search(text):  # "NGÀY 22/10" inside the mid-patch updates
            self.date = text
            self.sub = None
            self.subkind = None
            return
        kind = kind_of(text) if text and len(text) <= 40 else None
        if kind and not TIER.search(text):
            self.subkind = kind
            # "TƯỚNG: BẬC 2" -> champions, grouped as "Bậc 2".
            tail = text.split(":", 1)[1].strip() if ":" in text else ""
            self.sub = (tail.capitalize() if tail.isupper() else tail) or None
            return
        self.subkind = None
        self.sub = text or None

    def walk(self, node: Tag) -> None:
        for child in node.children:
            if isinstance(child, NavigableString):
                continue
            if not isinstance(child, Tag):
                continue
            name = child.name
            if name in ("script", "style", "noscript", "button", "svg"):
                continue
            if name in ("h1", "h2"):
                self.open_section(_text(child))
            elif name in ("h3", "h4", "h5", "h6"):
                self.heading(_text(child))
            elif name in ("ul", "ol"):
                self.list(child)
            elif name == "blockquote":
                note = _text(child)
                if note:
                    self.current().notes.append(note)
            elif name == "table":
                self.table(child)
            elif name == "img":
                self.image(child)
            elif name == "p":
                self.paragraph(child)
            else:
                self.walk(child)

    def _sub_context(self):
        if not self.sub:
            return None, None
        if TIER.search(self.sub) or BUFF_HEAD.search(self.sub) or NERF_HEAD.search(self.sub):
            return None, self.sub
        known = self.names.find(self.sub)
        if known:
            return known[0], None
        # Headings that name a single item/champion are rare; most are groups ("Tinh Linh").
        if self.subkind is None and len(self.sub) <= 30 and not self.sub.isupper() and len(self.sub.split()) <= 3:
            return self.sub, None
        return None, self.sub

    def paragraph(self, p: Tag) -> None:
        for img in p.find_all("img"):
            self.image(img)
        text = _text(p)
        if not text:
            return
        strong = p.find(["strong", "b"])
        if strong and _text(strong) == text and len(text) <= 60 and not ARROW.search(text):
            self.heading(text)
        elif ARROW.search(text):
            self.add(text, *self._sub_context())
        elif self.section is not None and len(text) > 30:
            self.current().notes.append(text)

    def table(self, table: Tag) -> None:
        for row in table.find_all("tr"):
            cells = [_text(c) for c in row.find_all(["td", "th"])]
            cells = [c for c in cells if c]
            if row.find("th") and not row.find("td"):
                continue
            if len(cells) >= 3 and not ARROW.search(" ".join(cells)):
                self.add(f"{cells[0]}: {cells[-2]} ⇒ {cells[-1]}")
            elif cells:
                self.add(": ".join(cells))

    def image(self, img: Tag) -> None:
        src = img.get("src") or img.get("data-src")
        if not src or not src.startswith("http"):
            return
        in_highlights = self.section is not None and HIGHLIGHTS.search(self.section.title)
        if in_highlights and not self.highlights_sure:
            self.highlights, self.highlights_sure = src, True
        elif not self.highlights:
            self.highlights = src


def _container(soup: BeautifulSoup) -> Tag | None:
    for selector in ("#patch-notes-container", "[data-testid='rich-text-html']", "article", "main"):
        node = soup.select_one(selector)
        if node and node.find("li"):
            return node
    data = _next_data(soup)
    if data is not None:
        best = ""
        for node in _walk_json(data):
            for value in node.values():
                if isinstance(value, str) and value.count("<li") > best.count("<li"):
                    best = value
        if best.count("<li") >= 5:
            return BeautifulSoup(best, "html.parser")
    return soup.body


def _meta(soup: BeautifulSoup, *names: str) -> str | None:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"]
    return None


def parse_article(html: str, article: Article, names: Names | None = None, sets: dict | None = None) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    container = _container(soup)
    if container is None:
        raise ValueError("không thấy nội dung bài viết")
    parser = _Parser(names)
    parser.walk(container)
    sections = [s for s in parser.sections if s.changes or s.notes]
    changes = [c for s in sections for c in s.changes]
    if len(changes) < 3:
        raise ValueError(f"chỉ đọc được {len(changes)} thay đổi, có thể trang đã đổi giao diện")
    published = article.published_at
    if not published:
        stamp = soup.find("time", attrs={"datetime": True})
        published = _meta(soup, "article:published_time") or (stamp["datetime"] if stamp else None)
        if not published and (data := _next_data(soup)) is not None:
            for node in _walk_json(data):
                if isinstance(node.get("publishedAt"), str):
                    published = node["publishedAt"]
                    break
    title = article.title or _meta(soup, "og:title") or article.version
    major = int(article.version.split(".")[0])
    guess = None
    for heading in parser.titles:
        match = SET_NAME_HEAD.match(heading.strip())
        if match and not NOT_SET_NAME.search(heading):
            name = (match["vi"] or match["en"]).strip()
            guess = name.title() if name.isupper() else name
            break
    counts = {d: sum(1 for c in changes if c["dir"] == d) for d in DIRS}
    return {
        "version": article.version,
        "set": major,
        "set_name": (sets or {}).get(str(major)) or guess,
        "title": " ".join(title.split()),
        "url": article.url,
        "locale": article.locale,
        "published_at": _iso(published),
        "image": article.image or _meta(soup, "og:image"),
        "highlights": parser.highlights,
        "description": _meta(soup, "og:description", "description"),
        "counts": counts,
        "icons": parser.icons,
        "sections": [
            {"title": s.title, "kind": s.kind, "notes": s.notes[:6], "changes": s.changes} for s in sections
        ],
    }


def _iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# --- History ----------------------------------------------------------------


def load_history(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return {"updated_at": None, "patches": []}
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class TftResult:
    history: dict
    new_versions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    checked_at: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _stamp(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def update_history(config: TftConfig, history: dict, fetcher: Fetcher, log=print) -> TftResult:
    """Read new patch notes into ``history``; errors are collected, not raised."""
    now = _now()
    result = TftResult(history=history, checked_at=_stamp(now))
    articles: dict[str, Article] = {}
    for url in config.listings:
        try:
            page = fetcher.fetch(url)
            found = parse_listing(page.text, page.url)
            log(f"  {url}: {len(found)} bài patch notes ({', '.join(a.version for a in found[:12])})")
        except Exception as exc:  # try the next listing
            result.errors.append(f"{url}: {exc}")
            log(f"  {url}: lỗi {exc}")
            continue
        for article in found:
            if config.min_version and version_key(article.version) < version_key(config.min_version):
                continue
            articles.setdefault(article.version, article)
    if not articles:
        result.errors.append("không tìm thấy bài patch notes nào")
        return result

    known = {p["version"]: p for p in history.get("patches", [])}
    newest = max(articles, key=version_key)
    reparse = history.get("parser") != PARSER_VERSION
    todo = []
    for version, article in sorted(articles.items(), key=lambda kv: version_key(kv[0]), reverse=True)[: config.max_patches]:
        stored = known.get(version)
        if stored is None or reparse:
            todo.append(article)
        elif version == newest and _stale(stored, now, config.refresh_hours):
            todo.append(article)  # B-patches are added to the newest article

    names_cache: dict = {}
    changed = False
    for article in todo:
        try:
            html = fetcher.fetch(article.url).text
            names = _names(config, article, names_cache, fetcher, log, result)
            patch = parse_article(html, article, names, config.sets)
        except Exception as exc:
            result.errors.append(f"{article.version}: {exc}")
            log(f"  {article.version}: lỗi {exc}")
            continue
        patch["fetched_at"] = _stamp(now)
        stored = known.get(article.version)
        if stored and _same(stored, patch):
            stored["fetched_at"] = patch["fetched_at"]
            log(f"  {article.version}: không đổi")
            continue
        if stored is None:
            result.new_versions.append(article.version)
        known[article.version] = patch
        changed = True
        log(f"  {article.version}: {sum(len(s['changes']) for s in patch['sections'])} thay đổi {patch['counts']} — {article.url}")
        for section in patch["sections"]:
            log(f"      [{section['kind']}] {section['title']}: {len(section['changes'])}")

    patches = sorted(known.values(), key=lambda p: version_key(p["version"]), reverse=True)
    if config.min_version:
        patches = [p for p in patches if version_key(p["version"]) >= version_key(config.min_version)]
    patches = patches[: config.max_patches]
    if [p["version"] for p in patches] != [p["version"] for p in history.get("patches", [])]:
        changed = True
    for patch in patches:  # names from the config win over guessed ones
        if config.sets.get(str(patch.get("set"))):
            patch["set_name"] = config.sets[str(patch["set"])]
    history["patches"] = patches
    if reparse:  # an article that failed keeps its earlier reading
        history["parser"] = PARSER_VERSION
        changed = True
    if changed:
        history["updated_at"] = _stamp(now)
    return result


def _stale(patch: dict, now: datetime, hours: int) -> bool:
    fetched = patch.get("fetched_at")
    if not fetched:
        return True
    published = patch.get("published_at")
    if published and now - datetime.fromisoformat(published.replace("Z", "+00:00")) > timedelta(days=21):
        return False
    return now - datetime.fromisoformat(fetched.replace("Z", "+00:00")) >= timedelta(hours=hours)


def _same(a: dict, b: dict) -> bool:
    skip = {"fetched_at"}
    return {k: v for k, v in a.items() if k not in skip} == {k: v for k, v in b.items() if k not in skip}


def _names(config: TftConfig, article: Article, cache: dict, fetcher: Fetcher, log, result: TftResult) -> Names | None:
    """Names for the article's set, in the article's language."""
    if not config.names_url:
        return None
    lang = (article.locale or "en-us").replace("-", "_")
    url = config.names_url.replace("{locale}", lang)
    if url not in cache:
        try:
            cache[url] = json.loads(fetcher.fetch(url).text)
        except Exception as exc:  # parse without names rather than not at all
            cache[url] = None
            result.errors.append(f"tên tướng/trang bị ({lang}): {exc}")
            log(f"  {url}: lỗi {exc}")
    if cache[url] is None:
        return None
    set_number = int(article.version.split(".")[0])
    key = (url, set_number)
    if key not in cache:
        cache[key] = build_names(cache[url], set_number, config.asset_base)
        counts: dict[str, int] = {}
        for _, kind, _ in cache[key].entries:
            counts[kind] = counts.get(kind, 0) + 1
        log(f"  tên mùa {set_number} ({lang}): {counts}")
    return cache[key]


def save_history(path: str | Path, history: dict) -> bool:
    path = Path(path)
    text = json.dumps(history, ensure_ascii=False, indent=1) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True
