"""Fetching pages over plain HTTP or through a headless browser."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)


class FetchError(Exception):
    pass


@dataclass
class CapturedResponse:
    """An XHR/fetch response seen while a page was rendered in the browser."""

    url: str
    status: int
    content_type: str
    body: str
    method: str = "GET"
    request_body: str | None = None


@dataclass
class Page:
    url: str
    status: int
    content_type: str
    text: str
    responses: list[CapturedResponse] = field(default_factory=list)
    before_click: str | None = None  # DOM before ``render(click=...)`` clicked


class Fetcher:
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self.session = requests.Session()
        retry = Retry(
            total=3,
            connect=1,  # a host that drops connections will not answer a 3rd try either
            backoff_factor=2,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=None,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )

    def fetch(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict | None = None,
        params: dict | None = None,
        data: dict | str | None = None,
        json: dict | list | None = None,
        check: bool = True,
    ) -> Page:
        """GET/POST ``url``; ``check=False`` returns 4xx/5xx pages instead of raising."""
        try:
            resp = self.session.request(
                method,
                url,
                headers=headers,
                params=params,
                data=data,
                json=json,
                timeout=(min(10.0, self.timeout), self.timeout),  # (connect, read)
            )
        except requests.RequestException as exc:
            raise FetchError(f"Không kết nối được {url}: {exc}") from exc
        content_type = resp.headers.get("Content-Type", "")
        # requests falls back to ISO-8859-1 when no charset is declared, which
        # mangles Vietnamese text; nearly every site here serves UTF-8.
        if "charset" not in content_type.lower():
            resp.encoding = "utf-8"
        if check and resp.status_code >= 400:
            raise FetchError(f"{url} trả về HTTP {resp.status_code}")
        return Page(resp.url, resp.status_code, content_type, resp.text)

    def render(
        self,
        url: str,
        *,
        wait_for: str | None = None,
        wait_ms: int = 0,
        click: str | None = None,
    ) -> Page:
        """Load ``url`` in headless Chromium and return the rendered DOM.

        JSON/XHR responses made by the page are captured too, which is how
        single-page apps usually receive their giftcode lists. ``click`` is a
        Playwright selector (CSS or ``text=...``) to click once loaded, for
        codes hidden behind a reveal button.
        """
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import TimeoutError as PlaywrightTimeout
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise FetchError(
                "Nguồn này cần trình duyệt headless: pip install playwright"
            ) from exc

        timeout_ms = int(self.timeout * 1000)
        finished = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(**_launch_options())
                try:
                    page = browser.new_page(user_agent=USER_AGENT, locale="vi-VN")
                    # Only finished requests: reading the body of a streaming
                    # response would block. (Playwright tags handlers with
                    # attributes, so the handler cannot be a bound builtin.)
                    page.on("requestfinished", lambda request: finished.append(request))
                    nav = page.goto(url, wait_until="load", timeout=timeout_ms)
                    try:
                        page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 15000))
                    except PlaywrightTimeout:
                        pass  # pages with videos or live analytics never go idle
                    if wait_for:
                        page.wait_for_selector(wait_for, timeout=timeout_ms)
                    if wait_ms:
                        page.wait_for_timeout(wait_ms)
                    html = before = page.content()
                    if click:
                        _click(page, click)
                        page.wait_for_timeout(max(wait_ms, 3000))
                        html = page.content()
                    captured = [c for c in map(_capture, finished) if c is not None]
                    return Page(
                        page.url,
                        nav.status if nav else 0,
                        "text/html",
                        html,
                        captured,
                        before_click=before if click else None,
                    )
                finally:
                    browser.close()
        except PlaywrightError as exc:
            raise FetchError(f"Trình duyệt không tải được {url}: {exc}") from exc


def _click(page, selector: str) -> None:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    target = page.locator(selector).first
    page.keyboard.press("Escape")  # close promo pop-ups that cover the page
    try:
        target.click(timeout=5000)
    except PlaywrightTimeout:
        # Still covered by an overlay: fire the click on the element itself.
        target.dispatch_event("click")


def _launch_options() -> dict:
    options: dict = {"headless": True}
    # GitHub runners ship Google Chrome, so CI can skip downloading Chromium.
    if channel := os.environ.get("GCF_BROWSER_CHANNEL"):
        options["channel"] = channel
    if path := os.environ.get("GCF_BROWSER_PATH"):
        options["executable_path"] = path
    return options


def _capture(request) -> CapturedResponse | None:
    response = request.response()
    if response is None:
        return None
    content_type = response.headers.get("content-type", "")
    if request.resource_type not in ("xhr", "fetch") and "json" not in content_type:
        return None
    try:
        body = response.text()
    except Exception:  # body evicted or response was a redirect
        body = ""
    return CapturedResponse(
        response.url, response.status, content_type, body, request.method, request.post_data
    )
