"""Giftcode value objects and normalisation helpers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Codes are letters/digits, optionally joined by . _ - (e.g. "P.U.S").
DEFAULT_CODE_PATTERN = r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,48}[A-Za-z0-9])?"

_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)
_EDGE_JUNK = " \t\r\n\"'`“”‘’«»:;,()[]{}<>|"

VN_TZ = timezone(timedelta(hours=7))
# "2027-04-23 11:44:00" / "23/04/2027" / "23-04-2027 23:59" / "23h59 31/12/2026"
_YMD = re.compile(r"(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})(?:[ T](?P<H>\d{1,2}):(?P<M>\d{2})(?::(?P<S>\d{2}))?)?")
_DMY = re.compile(
    r"(?:(?P<H0>\d{1,2})[:h](?P<M0>\d{2})\s+(?:ngày\s+)?)?"
    r"(?P<d>\d{1,2})[/.-](?P<m>\d{1,2})[/.-](?P<y>\d{4})"
    r"(?:\s+(?:lúc\s+)?(?P<H>\d{1,2})[:h](?P<M>\d{2})(?::(?P<S>\d{2}))?)?"
)


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


def parse_vn_time(text: object) -> str | None:
    """Read a date or date-time as a UTC ISO timestamp.

    Times without an offset are Vietnam time; a bare date means the end of
    that day.
    """
    value = clean_text(text or "")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if moment.tzinfo:
            return _iso(moment)
    except ValueError:
        pass
    for pattern in (_YMD, _DMY):
        if match := pattern.search(value):
            g = match.groupdict()
            hour, minute, second = g.get("H") or g.get("H0"), g.get("M") or g.get("M0"), g.get("S")
            try:
                moment = datetime(
                    int(g["y"]),
                    int(g["m"]),
                    int(g["d"]),
                    int(hour) if hour else 23,
                    int(minute) if minute else 59,
                    int(second) if second else (0 if hour else 59),
                    tzinfo=VN_TZ,
                )
            except ValueError:
                return None
            return _iso(moment)
    return None


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
