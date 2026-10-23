"""``inspect`` command: show how a page exposes its giftcodes.

Prints a structural summary that makes configuring a new source easy without
reading raw HTML: candidate codes grouped by CSS selector, framework hints,
scripts, API-looking URLs and (with ``--render``) the JSON responses the page
loads.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Comment, Tag

from .codes import clean_code, clean_text
from .fetch import Fetcher, Page

# A text node that is nothing but an upper-case token, e.g. "STRINGIFY", "P.U.S".
_UPPER_TOKEN = re.compile(r"(?=.*[A-Z])[A-Z0-9](?:[A-Z0-9._-]{0,48}[A-Z0-9])?")
_ANY_TOKEN = re.compile(r"(?=.*[A-Za-z])[A-Za-z0-9](?:[A-Za-z0-9._-]{0,48}[A-Za-z0-9])?")
_QUOTED = re.compile(r"""["']([^"']{3,50})["']""")
_URL = re.compile(r"""(?:https?:)?//[^\s"'`<>\\)]+|["'`](/[^"'`\s<>]*api[^"'`\s<>]*)["'`]""")
_ENDPOINT_HINT = re.compile(r"gift|code|reward|qua|api", re.I)
# Quoted path fragments in JS bundles, e.g. "/event/list-event-of-game/".
_JS_PATH = re.compile(r"""["'`](/?[a-z][a-z0-9_-]*(?:/[a-z0-9_-]+)+/?)["'`]""", re.I)
_JS_PATH_HINT = re.compile(r"gift|code|event|receive|reward|care|nhan", re.I)
_SKIP_TAGS = ["script", "style", "noscript", "svg", "template", "head"]


def css_path(el: Tag, depth: int = 5) -> str:
    parts = []
    while isinstance(el, Tag) and el.name not in ("[document]", "html", "body") and depth:
        part = el.name
        if el.get("id"):
            part += f"#{el['id']}"
        classes = [c for c in el.get("class", []) if c][:2]
        if classes:
            part += "." + ".".join(classes)
        parts.append(part)
        el = el.parent
        depth -= 1
    return " > ".join(reversed(parts))


def find_candidates(soup: BeautifulSoup) -> dict[str, list[str]]:
    """Group code-looking values by the selector of the element holding them."""
    groups: dict[str, list[str]] = defaultdict(list)

    for node in soup.find_all(string=True):
        if isinstance(node, Comment) or node.parent is None or node.parent.name in _SKIP_TAGS:
            continue
        value = clean_code(node)
        if _UPPER_TOKEN.fullmatch(value) and len(value) >= 3:
            groups[f"text  {css_path(node.parent)}"].append(value)

    for el in soup.find_all(True):
        if el.name in _SKIP_TAGS:
            continue
        for attr, raw in el.attrs.items():
            raw = " ".join(raw) if isinstance(raw, list) else str(raw)
            name = attr.lower()
            if name.startswith(("on", "@", "v-on", "x-on")) or "click" in name:
                values = _QUOTED.findall(raw)
            elif any(k in name for k in ("clipboard", "code", "copy")) or (
                name == "value" and el.name in ("input", "textarea")
            ):
                values = [raw]
            else:
                continue
            for value in map(clean_code, values):
                if _ANY_TOKEN.fullmatch(value):
                    groups[f"@{attr:<5} {css_path(el)}"].append(value)
    return groups


def framework_hints(page: Page, soup: BeautifulSoup) -> list[str]:
    html = page.text
    hints = []
    checks = [
        ("Next.js", "__NEXT_DATA__" in html or "/_next/" in html),
        ("Nuxt", "__NUXT__" in html or "/_nuxt/" in html),
        ("Angular", soup.find(attrs={"ng-version": True}) is not None),
        ("React root (#root)", soup.find(id="root") is not None),
        ("Vue root (#app)", soup.find(id="app") is not None),
        ("Laravel (csrf-token)", soup.find("meta", attrs={"name": "csrf-token"}) is not None),
        ("WordPress", "wp-content" in html),
    ]
    hints = [name for name, hit in checks if hit]
    body = soup.body
    visible = len(clean_text(body.get_text(" "))) if body else 0
    hints.append(f"{visible} ký tự chữ hiển thị trong <body>")
    return hints


def _api_urls(text: str, base: str) -> list[str]:
    found = []
    for match in _URL.finditer(text):
        url = match.group(1) or match.group(0)
        url = url.rstrip(".,;")
        if _ENDPOINT_HINT.search(url) and not url.endswith((".png", ".jpg", ".svg", ".webp", ".css", ".woff2")):
            found.append(urljoin(base, url))
    return sorted(set(found))


def _js_paths(js: str) -> list[str]:
    paths = {m.group(1) for m in _JS_PATH.finditer(js)}
    return sorted(p for p in paths if _JS_PATH_HINT.search(p))


def _grep(js: str, needle: str, limit: int = 8, width: int = 300) -> list[str]:
    hits = []
    for match in re.finditer(re.escape(needle), js, re.I):
        start = max(match.start() - width, 0)
        hits.append(clean_text(js[start : match.end() + width]))
        if len(hits) >= limit:
            break
    return hits


def _site_of(url: str) -> str:
    return ".".join((urlparse(url).hostname or "").split(".")[-2:])


def _visible_lines(soup: BeautifulSoup) -> list[str]:
    for el in soup.find_all(_SKIP_TAGS):
        el.decompose()
    lines = [clean_text(line) for line in soup.get_text("\n").splitlines()]
    return [line for line in lines if line]


def _section(title: str) -> None:
    print(f"\n=== {title} ===")


def inspect_url(
    url: str,
    *,
    render: bool = False,
    scan_js: bool = False,
    grep: list[str] = (),
    grep_width: int = 300,
    grep_limit: int = 8,
    click: str | None = None,
    dump_text: int = 0,
    dump_html: int = 0,
    fetcher: Fetcher | None = None,
) -> None:
    fetcher = fetcher or Fetcher()
    render = render or bool(click)
    page = fetcher.render(url, click=click) if render else fetcher.fetch(url)
    soup = BeautifulSoup(page.text, "html.parser")

    _section(f"Trang {'(render)' if render else '(HTTP)'}")
    print(f"URL      : {page.url}")
    print(f"HTTP     : {page.status}  {page.content_type}  {len(page.text)} ký tự")
    title = soup.title.get_text(strip=True) if soup.title else ""
    print(f"Tiêu đề  : {title}")
    for hint in framework_hints(page, soup):
        print(f"Gợi ý    : {hint}")

    _section("Ứng viên giftcode (selector -> giá trị)")
    groups = find_candidates(soup)
    if not groups:
        print("(không thấy giá trị nào giống giftcode trong HTML)")
    for selector, values in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print(f"[{len(values):>3}] {selector}")
        print(f"      {', '.join(values[:12])}{' ...' if len(values) > 12 else ''}")

    _section("Script")
    inline = [s for s in soup.find_all("script") if not s.get("src")]
    srcs = [urljoin(page.url, s["src"]) for s in soup.find_all("script", src=True)]
    print(f"{len(srcs)} script ngoài, {len(inline)} script inline")
    for src in srcs:
        print(f"  src: {src}")
    for script in inline:
        body = script.get_text()
        if len(body) > 200 or "__" in body:
            print(f"  inline {len(body)} ký tự: {clean_text(body)[:300]}")

    _section("URL có dạng API trong HTML")
    for api in _api_urls(page.text, page.url) or ["(không có)"]:
        print(f"  {api}")

    site = _site_of(page.url)
    if scan_js or grep:
        _section("URL có dạng API trong file JS")
        for src in srcs:
            if _site_of(src) != site:
                continue
            try:
                js = fetcher.fetch(src).text
            except Exception as exc:  # keep inspecting the other bundles
                print(f"  {src}: lỗi {exc}")
                continue
            apis = _api_urls(js, page.url)
            print(f"  {src} ({len(js)} ký tự): {len(apis)} URL")
            for api in apis[:80]:
                print(f"     {api}")
            paths = _js_paths(js)
            print(f"  Đường dẫn API tương đối ({len(paths)}):")
            for path in paths[:150]:
                print(f"     {path}")
            for needle in grep:
                hits = _grep(js, needle, limit=grep_limit, width=grep_width)
                print(f"  Tìm '{needle}': {len(hits)} chỗ")
                for hit in hits:
                    print(f"     … {hit} …")

    if page.responses:
        _section("Response XHR/fetch khi render")
        for res in page.responses:
            print(f"  {res.status} {res.method:<5} {res.content_type[:30]:<30} {len(res.body):>7}  {res.url}")
        for res in page.responses:
            if _site_of(res.url) != site and not re.search(r"code|gift", res.body, re.I):
                continue
            if not res.body and not res.request_body:
                continue
            print(f"\n--- {res.method} {res.url}")
            if res.request_body:
                print(f"    gửi: {res.request_body[:1000]}")
            try:
                body = json.dumps(json.loads(res.body), ensure_ascii=False)
            except ValueError:
                body = res.body
            print(body[:6000])

    if page.before_click is not None:
        _section(f"Chữ mới xuất hiện sau khi bấm {click!r}")
        before = set(_visible_lines(BeautifulSoup(page.before_click, "html.parser")))
        added = [line for line in _visible_lines(BeautifulSoup(page.text, "html.parser")) if line not in before]
        for line in added[:200] or ["(không có gì thay đổi)"]:
            print(f"  {line}")

    if dump_text:
        _section(f"Chữ hiển thị (tối đa {dump_text} dòng)")
        for line in _visible_lines(BeautifulSoup(page.text, "html.parser"))[:dump_text]:
            print(f"  {line}")

    if dump_html:
        _section(f"HTML <body> đã lược script/style (tối đa {dump_html} dòng)")
        body_soup = BeautifulSoup(page.text, "html.parser")
        for el in body_soup.find_all(_SKIP_TAGS):
            el.decompose()
        root = body_soup.body or body_soup
        for line in root.prettify().splitlines()[:dump_html]:
            print(line.rstrip()[:240])
