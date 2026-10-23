"""Extractor registry.

Each source in the config names an extractor via ``type``. An extractor is a
function ``(source, fetcher) -> list[Code]``; the options it accepts are read
from the source's remaining keys. Generic extractors (``html``, ``regex``,
``json``) cover most sites through config alone; site-specific ones live in
their own module and are registered with :func:`register`.
"""

from __future__ import annotations

from typing import Callable

from ..codes import Code, clean_code, compile_pattern, dedupe, is_code
from ..config import Source
from ..fetch import Fetcher, Page

Extractor = Callable[[Source, Fetcher], list[Code]]
EXTRACTORS: dict[str, Extractor] = {}


class ExtractError(Exception):
    pass


def register(name: str) -> Callable[[Extractor], Extractor]:
    def wrap(fn: Extractor) -> Extractor:
        EXTRACTORS[name] = fn
        return fn

    return wrap


def load_page(source: Source, fetcher: Fetcher, url: str | None = None) -> Page:
    url = url or source.url
    if source.get("render"):
        return fetcher.render(url, wait_for=source.get("wait_for"), wait_ms=int(source.get("wait_ms", 0)))
    return fetcher.fetch(
        url,
        method=str(source.get("method", "GET")).upper(),
        headers=source.get("headers"),
        params=source.get("params"),
        data=source.get("data"),
        json=source.get("json"),
    )


def finalize(source: Source, codes: list[Code]) -> list[Code]:
    """Clean, validate and de-duplicate extracted codes."""
    pattern = compile_pattern(source.get("code_pattern"))
    exclude = {str(word).upper() for word in source.get("exclude", [])}
    valid = []
    for item in codes:
        item.code = clean_code(item.code)
        if is_code(item.code, pattern, exclude):
            valid.append(item)
    return dedupe(valid)


def extract(source: Source, fetcher: Fetcher) -> list[Code]:
    codes = finalize(source, EXTRACTORS[source.type](source, fetcher))
    if not codes and not source.get("allow_empty"):
        raise ExtractError(
            "Không tìm thấy code nào - có thể trang đã đổi cấu trúc "
            "(đặt allow_empty: true nếu trang thật sự không còn code)"
        )
    return codes


# Register the bundled extractors.
from . import generic, zoneplay  # noqa: E402,F401
