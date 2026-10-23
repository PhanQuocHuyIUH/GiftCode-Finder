"""Giftcode value objects and normalisation helpers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Codes are letters/digits, optionally joined by . _ - (e.g. "P.U.S").
DEFAULT_CODE_PATTERN = r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,48}[A-Za-z0-9])?"

_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)
_EDGE_JUNK = " \t\r\n\"'`“”‘’«»:;,()[]{}<>|"


@dataclass
class Code:
    # None when the source lists a giftcode but hides its value (for example
    # behind a login); such items are shown with ``link`` to claim them.
    code: str | None
    reward: str | None = None
    expires: str | None = None
    title: str | None = None  # event/post the code belongs to
    link: str | None = None  # page where the code is claimed


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
        for name in ("reward", "expires", "title", "link"):
            setattr(existing, name, getattr(existing, name) or getattr(item, name))
    return list(by_code.values())
