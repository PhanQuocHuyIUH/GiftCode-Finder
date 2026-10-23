"""Config-driven extractors that work for most sites.

``html``  - pick codes with CSS selectors.
``regex`` - match a regular expression against the page text or HTML.
``json``  - read codes from a JSON API, or JSON embedded in a <script> tag.
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup, Tag

from ..codes import Code, clean_text
from ..config import Source
from ..fetch import Fetcher
from . import ExtractError, load_page, register


@register("html")
def extract_html(source: Source, fetcher: Fetcher) -> list[Code]:
    soup = BeautifulSoup(load_page(source, fetcher).text, "html.parser")
    return codes_from_soup(soup, source.options)


def codes_from_soup(soup: BeautifulSoup, options: dict) -> list[Code]:
    item_sel, code_sel = options.get("item"), options.get("code")
    if not item_sel and not code_sel:
        raise ExtractError("Nguồn 'html' cần 'item' hoặc 'code' (CSS selector)")
    attr = options.get("attr")
    codes = []
    for item in soup.select(item_sel) if item_sel else [soup]:
        targets = item.select(code_sel) if code_sel else [item]
        if item_sel:
            targets = targets[:1]  # one code per item block
        for el in targets:
            value = el.get(attr) if attr else el.get_text(" ", strip=True)
            if value:
                codes.append(
                    Code(
                        code=str(value),
                        reward=_text(item, options.get("reward")) if item_sel else None,
                        expires=_text(item, options.get("expires")) if item_sel else None,
                    )
                )
    return codes


def _text(scope: Tag, selector: str | None) -> str | None:
    if not selector:
        return None
    el = scope.select_one(selector)
    return clean_text(el.get_text(" ", strip=True)) or None if el else None


@register("regex")
def extract_regex(source: Source, fetcher: Fetcher) -> list[Code]:
    pattern = source.get("pattern")
    if not pattern:
        raise ExtractError("Nguồn 'regex' cần 'pattern'")
    flags = re.IGNORECASE if "i" in str(source.get("flags", "")) else 0
    regex = re.compile(pattern, flags | re.MULTILINE)
    page = load_page(source, fetcher)
    if source.get("on", "text") == "html":
        haystack = page.text
    else:
        haystack = BeautifulSoup(page.text, "html.parser").get_text("\n")
    codes = []
    for match in regex.finditer(haystack):
        groups = match.groupdict()
        code = groups.get("code") or (match.group(1) if regex.groups else match.group(0))
        reward, expires = groups.get("reward"), groups.get("expires")
        codes.append(
            Code(
                code=code,
                reward=clean_text(reward) if reward else None,
                expires=clean_text(expires) if expires else None,
            )
        )
    return codes


@register("json")
def extract_json(source: Source, fetcher: Fetcher) -> list[Code]:
    page = load_page(source, fetcher)
    if script := source.get("script"):
        el = BeautifulSoup(page.text, "html.parser").select_one(script)
        if el is None:
            raise ExtractError(f"Không thấy thẻ script khớp '{script}'")
        text = el.get_text()
    else:
        text = page.text
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ExtractError(f"Dữ liệu không phải JSON hợp lệ: {exc}") from exc
    return codes_from_json(data, source.options)


def codes_from_json(data, options: dict) -> list[Code]:
    code_key = options.get("code", "code")
    if items_path := options.get("items"):
        items = [x for v in resolve(data, items_path) for x in (v if isinstance(v, list) else [v])]
    else:
        items = find_items(data, code_key)
    codes = []
    for item in items:
        value = _first(resolve(item, code_key))
        if value in (None, ""):
            continue
        reward = _first(resolve(item, options["reward"])) if options.get("reward") else None
        expires = _first(resolve(item, options["expires"])) if options.get("expires") else None
        codes.append(
            Code(
                code=str(value),
                reward=clean_text(reward) if reward else None,
                expires=clean_text(expires) if expires else None,
            )
        )
    return codes


def resolve(data, path: str) -> list:
    """Follow a dotted path; ``*`` fans out over list items or object values."""
    values = [data]
    for part in str(path).split("."):
        step = []
        for value in values:
            if part == "*":
                if isinstance(value, list):
                    step.extend(value)
                elif isinstance(value, dict):
                    step.extend(value.values())
            elif isinstance(value, dict) and part in value:
                step.append(value[part])
            elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
                step.append(value[int(part)])
        values = step
    return values


def find_items(data, code_key: str) -> list[dict]:
    """Find the objects that carry ``code_key`` anywhere in the document."""
    first = code_key.split(".")[0]
    found = []
    stack = [data]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            if first in value and resolve(value, code_key):
                found.append(value)
            else:
                stack.extend(reversed(list(value.values())))
        elif isinstance(value, list):
            stack.extend(reversed(value))
    return found


def _first(values: list):
    return values[0] if values else None
