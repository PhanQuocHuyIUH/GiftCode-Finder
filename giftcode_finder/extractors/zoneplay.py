"""Gzone portal (zoneplay.vn) - giftcodes listed on /care/game/<id>."""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..codes import Code
from ..config import Source
from ..fetch import Fetcher
from . import load_page, register

_COPY_ATTRS = ("data-clipboard-text", "data-code", "data-copy")


@register("zoneplay")
def extract_zoneplay(source: Source, fetcher: Fetcher) -> list[Code]:
    soup = BeautifulSoup(load_page(source, fetcher).text, "html.parser")
    codes = []
    for el in soup.select(", ".join(f"[{a}]" for a in _COPY_ATTRS)):
        codes += [Code(el[a]) for a in _COPY_ATTRS if el.get(a)]
    return codes
