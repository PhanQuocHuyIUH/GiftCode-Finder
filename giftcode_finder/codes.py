"""Giftcode value objects and normalisation helpers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

# Codes are letters/digits, optionally joined by . _ - (e.g. "P.U.S").
DEFAULT_CODE_PATTERN = r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,48}[A-Za-z0-9])?"

_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)
_EDGE_JUNK = " \t\r\n\"'`“”‘’«»:;,()[]{}<>|"

VN_TZ = timezone(timedelta(hours=7))
# "2027-04-23 11:44:00" / "2026/09/21 08:59"
_YMD = re.compile(
    r"(?P<y>\d{4})[-/.](?P<m>\d{1,2})[-/.](?P<d>\d{1,2})"
    r"(?:(?:[ T]|,\s*)(?P<H>\d{1,2}):(?P<M>\d{2})(?::(?P<S>\d{2}))?)?"
)
# "23/04/2027" / "23-04-2027 23:59" / "23h59 31/12/2026"
_DMY = re.compile(
    r"(?:(?P<H0>\d{1,2})[:h](?P<M0>\d{2})\s+(?:ngày\s+)?)?"
    r"(?P<d>\d{1,2})[/.-](?P<m>\d{1,2})[/.-](?P<y>\d{4})"
    r"(?:\s+(?:lúc\s+)?(?P<H>\d{1,2})[:h](?P<M>\d{2})(?::(?P<S>\d{2}))?)?"
)
# "September 21, 2026" / "Sep 21" / "21 September 2026"
_MONTH = (
    r"(?P<mon>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
)
_MDY = re.compile(rf"\b{_MONTH}\s+(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(?P<y>\d{{4}})\b)?", re.I)
_DMY_NAMED = re.compile(rf"\b(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}\b(?:,?\s+(?P<y>\d{{4}})\b)?", re.I)
_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
# "8:59 AM" / "9pm" / "08:59", next to a date written with a month name.
_CLOCK = re.compile(
    r"\b(?P<H>\d{1,2})(?::(?P<M>\d{2}))?(?::(?P<S>\d{2}))?\s*(?P<ap>[ap])\.?m\b"
    r"|\b(?P<H24>\d{1,2}):(?P<M24>\d{2})(?::(?P<S24>\d{2}))?\b",
    re.I,
)
_AMPM = re.compile(r"\s*(?P<ap>[ap])\.?m\b", re.I)
# "UTC+8" / "GMT-07:00", or a zone named the way publishers write it: "(PT)".
_OFFSET = re.compile(r"\b(?:UTC|GMT)\s*(?P<sign>[+\-\u2212])\s*(?P<h>\d{1,2})(?::?(?P<m>\d{2}))?")
_ZONE = re.compile(r"\b(?P<zone>UTC|GMT|PDT|PST|PT|EDT|EST|ET|CEST|CET|BST|JST|KST)\b")
_ZONES = {"UTC": 0, "GMT": 0, "PDT": -7, "PST": -8, "EDT": -4, "EST": -5, "CEST": 2, "CET": 1, "BST": 1, "JST": 9, "KST": 9}
# PT is PDT or PST depending on the date.
_DST_ZONES = {"PT": "America/Los_Angeles", "ET": "America/New_York"}
# Discord's <t:1758470340:F> markup.
_DISCORD_TIME = re.compile(r"<t:(?P<ts>\d{1,11})(?::[tTdDfFR])?>")


@dataclass
class Code:
    # None when the source lists a giftcode but hides its value (for example
    # behind a login); such items are shown with ``link`` to claim them.
    code: str | None
    reward: str | None = None
    expires: str | None = None
    title: str | None = None  # event/post the code belongs to
    link: str | None = None  # page where the code is claimed
    expires_at: str | None = None  # UTC ISO time, for the countdown
    since: str | None = None  # UTC ISO time the source started offering it


def clean_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value)).translate(_INVISIBLE)
    return " ".join(text.split())


def clean_lines(value: object) -> str:
    """``clean_text`` line by line, keeping the line breaks."""
    return "\n".join(clean_text(line) for line in str(value).splitlines())


def clean_code(value: object) -> str:
    return clean_text(value).strip(_EDGE_JUNK)


def compile_pattern(pattern: str | None) -> re.Pattern:
    return re.compile(pattern or DEFAULT_CODE_PATTERN)


def is_code(value: str, pattern: re.Pattern, exclude: set[str] = frozenset()) -> bool:
    return (
        bool(pattern.fullmatch(value))
        and any(ch.isalpha() for ch in value)
        and value.upper() not in exclude
    )


def dedupe(codes: list[Code]) -> list[Code]:
    """Keep the first occurrence of each code, filling in missing details."""
    by_code: dict[str, Code] = {}
    for item in codes:
        existing = by_code.get(item.code)
        if existing is None:
            by_code[item.code] = item
            continue
        for name in DETAIL_FIELDS:
            setattr(existing, name, getattr(existing, name) or getattr(item, name))
    return list(by_code.values())


DETAIL_FIELDS = ("title", "reward", "expires", "expires_at", "since", "link")


def code_key(value: str) -> str:
    """Letters and digits only, upper-case: "P.U.S" -> "PUS"."""
    return re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKD", value).upper())


def parse_vn_time(text: object, now: datetime | None = None) -> str | None:
    """Read a date or date-time as a UTC ISO timestamp.

    Times without a zone ("UTC+8", "PT", ...) are Vietnam time; a bare date
    means the end of that day, and a date without a year the one nearest to
    ``now``.
    """
    value = clean_text(text or "")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if moment.tzinfo:
            return utc_iso(moment)
    except ValueError:
        pass
    if match := _DISCORD_TIME.search(value):
        return utc_iso(datetime.fromtimestamp(int(match["ts"]), timezone.utc))
    match = next(filter(None, (p.search(value) for p in (_YMD, _DMY, _MDY, _DMY_NAMED))), None)
    if match is None:
        return None
    g = match.groupdict()
    hour, minute, second = g.get("H") or g.get("H0"), g.get("M") or g.get("M0"), g.get("S")
    ampm = None
    if g.get("mon"):
        # "September 21, 2026 at 9 AM PT" / "9 AM PT on September 21"
        clock = _CLOCK.search(value, match.end()) or _CLOCK.search(value, 0, match.start())
        if clock:
            hour, minute = clock["H"] or clock["H24"], clock["M"] or clock["M24"]
            second, ampm = clock["S"] or clock["S24"], clock["ap"]
    elif hour and (suffix := _AMPM.match(value, match.end())):
        ampm = suffix["ap"]
    month = int(g["m"]) if g.get("m") else _MONTHS.index(g["mon"][:3].lower()) + 1
    if hour is None:
        clock_time = (23, 59, 59)  # a bare date lasts the whole day
    else:
        hours = int(hour) % 12 + (12 if ampm.lower() == "p" else 0) if ampm else int(hour)
        clock_time = (hours, int(minute or 0), int(second or 0))
    try:
        zone = _zone(value)
        if g.get("y"):
            moment = datetime(int(g["y"]), month, int(g["d"]), *clock_time, tzinfo=zone)
        else:
            moment = _nearest_year(month, int(g["d"]), clock_time, zone, now)
    except ValueError:
        return None
    return utc_iso(moment)


def _zone(value: str) -> tzinfo:
    if match := _OFFSET.search(value):
        sign = -1 if match["sign"] in "-−" else 1
        return timezone(sign * timedelta(hours=int(match["h"]), minutes=int(match["m"] or 0)))
    if match := _ZONE.search(value):
        name = match["zone"]
        return ZoneInfo(_DST_ZONES[name]) if name in _DST_ZONES else timezone(timedelta(hours=_ZONES[name]))
    return VN_TZ


def _nearest_year(month: int, day: int, clock_time: tuple, zone: tzinfo, now: datetime | None) -> datetime:
    now = now or datetime.now(timezone.utc)
    candidates = []
    for year in (now.year - 1, now.year, now.year + 1):
        try:
            candidates.append(datetime(year, month, day, *clock_time, tzinfo=zone))
        except ValueError:  # 29 February
            continue
    if not candidates:
        raise ValueError(f"no year has {day}/{month}")
    return min(candidates, key=lambda moment: abs(moment - now))


def utc_iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
