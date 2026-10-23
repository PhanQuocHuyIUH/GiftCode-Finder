"""The bundled Strinova sources, run against snapshots of the live pages."""

import json
from pathlib import Path

import pytest

from giftcode_finder.config import load_config
from giftcode_finder.extractors import ExtractError, extract
from giftcode_finder.fetch import Page

FIXTURES = Path(__file__).parent / "fixtures"
EVENTS = json.loads((FIXTURES / "zoneplay_events_367.json").read_text(encoding="utf-8"))
ARTICLE = (FIXTURES / "strinova_huong_dan_giftcode.html").read_text(encoding="utf-8")
STRINOVA_CODES = ["STRINOVA", "P.U.S", "THESCISSORS", "URBINO", "SUPERSTRING", "STRINGIFY"]
# What Gzone hands out for each event (event names are not the codes).
CODE_OF_EVENT = {945: "STRINGIFY", 944: "SUPERSTRING", 943: "URBINO", 942: "THESCISSORS", 941: "P.U.S", 940: "STRINOVA"}
API = "https://api-v3.zoneplay.vn/api/care"


def source(source_id):
    game = next(g for g in load_config("config/sources.yaml") if g.id == "strinova")
    return next(s for s in game.sources if s.id == source_id)


class RouteFetcher:
    """Answers each (method, url) from a table of handlers."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def fetch(self, url, *, method="GET", json=None, check=True, **kwargs):
        self.calls.append((method, url, json))
        status, body = self.routes[(method, url)](json)
        return Page(url, status, "application/json", body if isinstance(body, str) else _dumps(body))


def _dumps(value):
    return json.dumps(value, ensure_ascii=False)


def events_route(events=None):
    payload = EVENTS if events is None else {"data": events}
    return {("GET", f"{API}/event/list-event-of-game/367"): lambda _: (200, payload)}


def test_guide_article_lists_the_six_launch_codes():
    article = source("huong-dan")
    fetcher = RouteFetcher({("GET", article.url): lambda _: (200, ARTICLE)})
    assert [c.code for c in extract(article, fetcher)] == STRINOVA_CODES


def test_care_page_without_token_lists_events_to_claim(monkeypatch):
    monkeypatch.delenv("ZONEPLAY_ACCESS_TOKEN", raising=False)
    items = extract(source("gzone"), RouteFetcher(events_route()))
    assert [(i.code, i.title) for i in items] == [
        (None, "STRINGIFY"),
        (None, "SUPERSTRING"),
        (None, "STRINOVA URBINO"),
        (None, "THESCISSORS"),
        (None, "Strinova PUS"),
        (None, "Strinova VN"),
    ]
    first = items[0]
    assert first.link == "https://zoneplay.vn/care/event/945/367"
    assert first.expires == "23/04/2027"
    # Gzone times are Vietnam time (UTC+7).
    assert first.expires_at == "2027-04-23T04:45:00Z"
    assert first.since == "2026-10-21T04:45:00Z"
    assert first.reward == "Mừng Game Ra Mắt Thành Công"


def test_care_page_with_token_claims_public_codes(monkeypatch):
    monkeypatch.setenv("ZONEPLAY_ACCESS_TOKEN", "tok")
    routes = events_route()
    routes[("POST", f"{API}/event/get-code-load")] = lambda body: (200, {"data": None})
    routes[("POST", f"{API}/event/get-code-of-event")] = lambda body: (
        200,
        {"error_code": 0, "code": CODE_OF_EVENT[body["event_id"]], "message": "Nhận code thành công"},
    )
    fetcher = RouteFetcher(routes)
    items = extract(source("gzone"), fetcher)
    assert sorted(i.code for i in items) == sorted(STRINOVA_CODES)
    assert next(i for i in items if i.code == "P.U.S").title == "Strinova PUS"
    # Same request bodies as the site sends.
    load = next(c for c in fetcher.calls if c[1].endswith("get-code-load"))
    claim = next(c for c in fetcher.calls if c[1].endswith("get-code-of-event"))
    assert load[2] == {"event_id": 945, "access_token": "tok", "app_key": "df053f7601394f2817b7e1a0a4e8e1ef"}
    assert claim[2] == {"event_id": 945, "access_token": "tok", "app_key": "367"}


def test_already_claimed_code_is_read_without_claiming_again(monkeypatch):
    monkeypatch.setenv("ZONEPLAY_ACCESS_TOKEN", "tok")
    routes = events_route()
    routes[("POST", f"{API}/event/get-code-load")] = lambda body: (200, {"data": CODE_OF_EVENT[body["event_id"]]})
    fetcher = RouteFetcher(routes)
    assert sorted(i.code for i in extract(source("gzone"), fetcher)) == sorted(STRINOVA_CODES)
    assert not any(url.endswith("get-code-of-event") for _, url, _ in fetcher.calls)


def test_rejected_token_fails_the_source(monkeypatch):
    monkeypatch.setenv("ZONEPLAY_ACCESS_TOKEN", "expired")
    routes = events_route()
    routes[("POST", f"{API}/event/get-code-load")] = lambda body: (401, {"message": "Unauthenticated."})
    with pytest.raises(ExtractError, match="ZONEPLAY_ACCESS_TOKEN"):
        extract(source("gzone"), RouteFetcher(routes))


def test_private_and_ended_events(monkeypatch):
    monkeypatch.setenv("ZONEPLAY_ACCESS_TOKEN", "tok")
    private = dict(EVENTS["data"][0], id=1, name="Giftcode riêng", type=1)
    ended = dict(EVENTS["data"][1], id=2, to_date="2020-01-01 00:00:00")
    fetcher = RouteFetcher(events_route([private, ended]))
    items = extract(source("gzone"), fetcher)
    # Private codes belong to one account: listed, never claimed or published.
    assert [(i.code, i.title) for i in items] == [(None, "Giftcode riêng")]
    assert all(method == "GET" for method, _, _ in fetcher.calls)


def test_no_events_is_not_an_error(monkeypatch):
    monkeypatch.delenv("ZONEPLAY_ACCESS_TOKEN", raising=False)
    assert extract(source("gzone"), RouteFetcher(events_route([]))) == []
