"""Gzone portal (zoneplay.vn): giftcode events on /care/game/<id>.

The page is a React app on top of the care API:

  GET  {api}/event/list-event-of-game/<game_id>  events: name, type, dates
  POST {api}/event/get-code-load                 code this account already claimed
  POST {api}/event/get-code-of-event             claim the code of an event

Event names are titles ("Strinova PUS"), not codes ("P.U.S"), and both code
endpoints need a logged-in Gzone session. With a token in the environment
variable named by ``token_env`` (``localStorage.access_token`` on zoneplay.vn)
the codes of public events are fetched; without it every event is still
listed, with a link to claim its code on the site.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from ..codes import Code, clean_text, parse_vn_time
from ..config import Source
from ..fetch import Fetcher, Page
from . import ExtractError, register

API = "https://api-v3.zoneplay.vn/api/care"
EVENT_URL = "https://zoneplay.vn/care/event/{event}/{game}"
PUBLIC = 2  # "Giftcode chung": one code shared by everyone
VN_TZ = timezone(timedelta(hours=7))
_GAME_ID = re.compile(r"/care/game/(\d+)")
_AUTH_HINT = re.compile(r"token|đăng nhập|login|unauth", re.I)


@register("zoneplay", empty_ok=True)
def extract_zoneplay(source: Source, fetcher: Fetcher) -> list[Code]:
    match = _GAME_ID.search(source.url)
    if not match:
        raise ExtractError("url Gzone phải có dạng https://zoneplay.vn/care/game/<id>")
    game_id = match.group(1)
    api = str(source.get("api", API)).rstrip("/")
    token = os.environ.get(str(source.get("token_env", "ZONEPLAY_ACCESS_TOKEN")), "").strip()
    reveal = set(source.get("reveal_types", [PUBLIC]))

    events = _json(fetcher.fetch(f"{api}/event/list-event-of-game/{game_id}")).get("data")
    if not isinstance(events, list):
        raise ExtractError("API Gzone không trả danh sách sự kiện (có thể đã đổi cấu trúc)")
    codes = []
    for event in events:
        if _ended(event):
            continue
        item = Code(
            code=None,
            title=clean_text(event.get("name") or ""),
            reward=_plain(event.get("description")),
            expires=_vn_date(event.get("to_date")),
            expires_at=parse_vn_time(event.get("to_date")),
            since=parse_vn_time(event.get("from_date")),
            link=EVENT_URL.format(event=event["id"], game=game_id),
        )
        if token and event.get("type") in reveal:
            item.code = _reveal(fetcher, api, token, event)
        codes.append(item)
    return codes


def _reveal(fetcher: Fetcher, api: str, token: str, event: dict) -> str | None:
    """Read the account's code for ``event``, claiming it the first time."""
    app_key = (event.get("game") or {}).get("app_key")
    # Same bodies as the site: get-code-load sends the game's app_key,
    # get-code-of-event sends the game id in that field.
    for endpoint, key in (("get-code-load", app_key), ("get-code-of-event", str(event.get("game_id")))):
        page = fetcher.fetch(
            f"{api}/event/{endpoint}",
            method="POST",
            json={"event_id": event["id"], "access_token": token, "app_key": key},
            check=False,
        )
        body = _json(page, strict=False)
        if code := _code_in(body):
            return code
        message = clean_text(body.get("message") or "")
        if page.status in (401, 403) or body.get("error_code") in (401, 403) or _AUTH_HINT.search(message):
            raise ExtractError(
                "Gzone từ chối token (hết hạn hoặc sai) - đăng nhập lại zoneplay.vn rồi "
                f"cập nhật secret ZONEPLAY_ACCESS_TOKEN. Gzone báo: {message or page.status}"
            )
    return None


def _code_in(body: dict) -> str | None:
    for value in (body.get("code"), body.get("data")):
        if isinstance(value, list):
            value = value[0] if value else None
        if isinstance(value, dict):
            value = value.get("code")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _json(page: Page, strict: bool = True) -> dict:
    try:
        data = json.loads(page.text)
    except ValueError as exc:
        if strict:
            raise ExtractError(f"API Gzone trả về dữ liệu không phải JSON ({page.url})") from exc
        return {}
    return data if isinstance(data, dict) else {}


def _parse(value: str | None) -> datetime | None:
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").replace(tzinfo=VN_TZ)
    except ValueError:
        return None


def _ended(event: dict) -> bool:
    end = _parse(event.get("to_date"))
    return end is not None and end < datetime.now(VN_TZ)


def _vn_date(value: str | None) -> str | None:
    moment = _parse(value)
    return moment.strftime("%d/%m/%Y") if moment else None


def _plain(html: str | None) -> str | None:
    if not html:
        return None
    return clean_text(BeautifulSoup(html, "html.parser").get_text(" ")) or None
