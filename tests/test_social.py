"""Official posts: Threads profiles and Discord channels."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from giftcode_finder.config import Source, load_config
from giftcode_finder.extractors import FEEDS, ExtractError, extract, social
from giftcode_finder.fetch import Page

FIXTURES = Path(__file__).parent / "fixtures"
# Wuthering Waves' profile as served signed out on 2026-10-23 (trimmed), with
# the official Version 3.7 livestream post of 2026-09-19 among its threads.
THREADS = (FIXTURES / "threads_wutheringwaves.html").read_text(encoding="utf-8")
LIVESTREAM_POST = (
    "Here are the redemption codes for Wuthering Waves Version 3.7 Preview Special Broadcast: "
    "[FALLINGSANCTUM], [FINDSENTINEL], and [WAKINGMOON], valid until 2026-09-21 08:59 (PT). "
    "Be sure to claim your rewards in the game before they expire!\n\n#WutheringWaves"
)
DURING_STREAM = datetime(2026, 9, 19, 13, 0, tzinfo=timezone.utc)


@pytest.fixture
def clock(monkeypatch):
    def set_now(moment):
        monkeypatch.setattr(social, "_now", lambda: moment)

    set_now(DURING_STREAM)
    return set_now


class FakeFetcher:
    def __init__(self, text="", status=200):
        self.text, self.status = text, status
        self.calls = []

    def fetch(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Page(url, self.status, "application/json", self.text)

    def render(self, url, **kwargs):
        self.calls.append((url, {"render": True, **kwargs}))
        return Page(url, 200, "text/html", self.text)


def wuwa_threads():
    game = next(g for g in load_config("config/sources.yaml") if g.id == "wuthering-waves")
    return next(s for s in game.sources if s.type == "threads")


def test_livestream_post_gives_its_codes_and_deadline():
    codes = social.codes_from_post(LIVESTREAM_POST, now=DURING_STREAM)
    assert [c.code for c in codes] == ["FALLINGSANCTUM", "FINDSENTINEL", "WAKINGMOON"]
    first = codes[0]
    # 08:59 Pacific Daylight Time = 22:59 in Vietnam.
    assert first.expires_at == "2026-09-21T15:59:00Z"
    assert first.expires == "2026-09-21 08:59 (PT)"
    assert first.title == "Wuthering Waves Version 3.7 Preview Special Broadcast"


def test_post_past_its_deadline_gives_nothing():
    assert social.codes_from_post(LIVESTREAM_POST, now=datetime(2026, 10, 23, tzinfo=timezone.utc)) == []


def test_bracketed_names_in_other_posts_are_not_codes():
    banner = "[Version 3.7 Featured Convene: Phase II]\nFeatured Resonator Convenes [Nine Deaths], [ONE] soon."
    assert social.codes_from_post(banner, now=DURING_STREAM) == []
    heading = "**IMPORTANT**: new redemption code\n`STARRYSTAGE2`\nExpires October 13, 2026 (08:59 AM UTC-7)."
    codes = social.codes_from_post(heading, now=datetime(2026, 10, 11, tzinfo=timezone.utc))
    assert [(c.code, c.expires_at) for c in codes] == [("STARRYSTAGE2", "2026-10-13T15:59:00Z")]


def test_discord_style_markup():
    text = (
        "https://youtu.be/livestream\n**Redemption codes** for the 3.8 livestream:\n"
        "**[ALPHA38]** · `BETA38`\n🎁 GAMMA38\nValid until <t:1790006340:F>"
    )
    codes = social.codes_from_post(text, now=DURING_STREAM)
    assert [c.code for c in codes] == ["ALPHA38", "BETA38", "GAMMA38"]
    assert codes[0].expires_at == "2026-09-21T15:59:00Z"
    assert codes[0].title == "3.8 livestream"


def test_threads_profile(clock):
    src = wuwa_threads()
    assert src.type in FEEDS
    fetcher = FakeFetcher(THREADS)
    codes = extract(src, fetcher)
    assert fetcher.calls[0][1]["render"]
    assert [c.code for c in codes] == ["FALLINGSANCTUM", "FINDSENTINEL", "WAKINGMOON"]
    assert codes[0].since == "2026-09-19T12:25:00Z"
    assert codes[0].link == "https://www.threads.com/@wutheringwaves/post/DdN_M0tv2pC"
    assert codes[0].expires_at == "2026-09-21T15:59:00Z"


def test_threads_without_live_codes_is_fine(clock):
    clock(datetime(2026, 10, 23, 14, tzinfo=timezone.utc))
    assert extract(wuwa_threads(), FakeFetcher(THREADS)) == []


def test_threads_page_without_posts_fails(clock):
    login_wall = "<html><body>Đăng nhập hoặc đăng ký Threads</body></html>"
    with pytest.raises(ExtractError, match="Threads"):
        extract(wuwa_threads(), FakeFetcher(login_wall))


CHANNEL = "https://discord.com/channels/111/222"
MESSAGES = [
    {
        # Published into our channel from the followed official channel.
        "id": "903",
        "content": "@everyone " + LIVESTREAM_POST,
        "timestamp": "2026-09-19T12:26:03.512000+00:00",
        "flags": 2,
        "message_reference": {"type": 0, "guild_id": "444", "channel_id": "555", "message_id": "666"},
        "embeds": [],
    },
    {
        "id": "902",
        "content": "",
        "timestamp": "2026-09-18T10:00:00+00:00",
        "flags": 0,
        "embeds": [{"title": "Gift code", "description": "**WUTHERINGGIFT** - 50 Astrite"}],
    },
    {"id": "901", "content": "Version 3.7 is coming!", "timestamp": "2026-09-17T10:00:00+00:00", "embeds": []},
]


def discord(**options):
    return Source(id="discord", name="Discord", type="discord", url=CHANNEL, options=options)


def test_discord_channel(clock, monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "bot-token")
    fetcher = FakeFetcher(json.dumps(MESSAGES))
    codes = extract(discord(), fetcher)
    url, kwargs = fetcher.calls[0]
    assert url == "https://discord.com/api/v10/channels/222/messages"
    assert kwargs["headers"]["Authorization"] == "Bot bot-token"
    assert [c.code for c in codes] == ["FALLINGSANCTUM", "FINDSENTINEL", "WAKINGMOON", "WUTHERINGGIFT"]
    assert codes[0].link == "https://discord.com/channels/444/555/666"
    assert codes[0].since == "2026-09-19T12:26:03Z"
    assert codes[0].expires_at == "2026-09-21T15:59:00Z"
    assert codes[0].title == "Wuthering Waves Version 3.7 Preview Special Broadcast"
    assert codes[3].link == "https://discord.com/channels/111/222/902"
    assert codes[3].expires_at is None


def test_discord_needs_the_bot_token(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    with pytest.raises(ExtractError, match="DISCORD_BOT_TOKEN"):
        extract(discord(), FakeFetcher("[]"))


@pytest.mark.parametrize("status, hint", [(401, "token"), (403, "quyền"), (404, "link kênh")])
def test_discord_access_errors(monkeypatch, status, hint):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "bot-token")
    with pytest.raises(ExtractError, match=hint):
        extract(discord(), FakeFetcher('{"message": "Missing Access", "code": 50001}', status=status))


def test_discord_without_message_content_intent(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "bot-token")
    blank = [dict(m, content="", embeds=[]) for m in MESSAGES]
    with pytest.raises(ExtractError, match="Message Content Intent"):
        extract(discord(), FakeFetcher(json.dumps(blank)))
