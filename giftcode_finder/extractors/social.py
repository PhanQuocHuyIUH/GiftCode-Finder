"""Official posts: a Threads profile, or a Discord channel read by a bot.

Publishers announce codes in short posts, for example Kuro Games after each
Wuthering Waves preview livestream:

  Here are the redemption codes for Wuthering Waves Version 3.7 Preview
  Special Broadcast: [FALLINGSANCTUM], [FINDSENTINEL], and [WAKINGMOON],
  valid until 2026-09-21 08:59 (PT). Be sure to claim your rewards ...

A post that talks about codes gives the code-shaped words it marks up
(brackets, backticks, bold, or a line of their own) and the deadline written
after "valid until", "expires", "hết hạn", ... Posts whose deadline has passed
are skipped. Both sources are feeds that only show recent posts, so a code
whose post scrolled away stays listed until it expires (see ``FEEDS``).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from ..codes import Code, clean_code, clean_lines, clean_text, parse_vn_time, utc_iso
from ..config import Source
from ..fetch import Fetcher
from . import ExtractError, register

# A post about codes...
_ABOUT_CODES = re.compile(r"code|redeem|redemption|mã|兑换|コード|코드", re.I)
# ...marks each one up: [CODE], `CODE`, **CODE**, or CODE on a line of its own.
_MARKED = re.compile(
    r"\[(?P<bracket>[^\]\s]+)\]|`(?P<tick>[^`\s]+)`|\*\*(?P<bold>[^*\s]+)\*\*"
    r"|^[^\w\n]*(?P<line>[A-Z0-9][A-Z0-9._-]+)[^\w\n]*$",
    re.M,
)
_CODE_SHAPE = re.compile(r"(?=[A-Z0-9._-]*[A-Z])[A-Z0-9][A-Z0-9._-]{2,48}[A-Z0-9]")
_NOT_CODES = {"CODE", "CODES", "EVENT", "FAQ", "IMPORTANT", "LIVE", "NEW", "NOTE", "NOTICE", "REDEMPTION", "UPDATE"}
_DEADLINE = re.compile(
    r"\b(?:valid (?:until|till|through)|available until|redeem(?:able)? (?:by|before|until)"
    r"|expir\w*|until|hết hạn|hạn (?:sử dụng|dùng)|HSD)",
    re.I,
)
# A deadline ends with its sentence: "... 08:59 (PT). Be sure ..."
_SENTENCE_END = re.compile(r"[!?\n]|\.\s+[A-Z]")
# Mentions and markdown around a title, and the wording before its subject.
_TITLE_JUNK = re.compile(r"https?://\S+|<[@#][!&]?\d+>|@everyone|@here|[*_~`>#|]")
_TITLE_NOISE = re.compile(r"^(?:here (?:are|is) )?(?:the )?(?:redemption |redeem )?codes? (?:for|from) (?:the )?", re.I)


def codes_from_post(
    text: str, *, since: str | None = None, link: str | None = None, now: datetime | None = None
) -> list[Code]:
    """The codes a post announces, with its deadline; none once it passed."""
    text = clean_lines(text or "")
    if not _ABOUT_CODES.search(text):
        return []
    found = []
    for match in _MARKED.finditer(text):
        value = clean_code(next(v for v in match.groups() if v))  # **[CODE]** -> CODE
        if _CODE_SHAPE.fullmatch(value) and value not in _NOT_CODES:
            found.append(value)
    if not found:
        return []
    now = now or _now()
    expires, expires_at = _deadline(text, now)
    if expires_at and expires_at <= utc_iso(now):
        return []
    title = _title(text)
    return [
        Code(code=code, title=title, expires=expires, expires_at=expires_at, since=since, link=link)
        for code in dict.fromkeys(found)
    ]


def _deadline(text: str, now: datetime) -> tuple[str | None, str | None]:
    for match in _DEADLINE.finditer(text):
        window = text[match.end() : match.end() + 80]
        if end := _SENTENCE_END.search(window):
            window = window[: end.start()]
        window = window.strip(" :.,")
        if moment := parse_vn_time(window, now):
            return window, moment
    return None, None


def _title(text: str) -> str | None:
    """The post's first line, up to a colon: what the codes are for."""
    for line in text.splitlines():
        if head := clean_text(_TITLE_JUNK.sub("", line).split(":", 1)[0]):
            return _TITLE_NOISE.sub("", head)[:120] or None
    return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Threads ---------------------------------------------------------------

THREADS_POST = "https://www.threads.com/@{user}/post/{code}"
_THREADS_USER = re.compile(r"threads\.(?:com|net)/@(?P<user>[\w.]+)")
# Post URLs carry the post id in Instagram's base64 alphabet.
_SHORTCODE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


@register("threads", empty_ok=True, feed=True)
def extract_threads(source: Source, fetcher: Fetcher) -> list[Code]:
    match = _THREADS_USER.search(source.url)
    if not match:
        raise ExtractError("url Threads phải có dạng https://www.threads.com/@<tên>")
    # Threads only renders posts for a browser; signed out it shows the latest few.
    page = fetcher.render(source.url, wait_ms=int(source.get("wait_ms", 0)))
    posts = threads_posts(page.text, match["user"])
    if not posts:
        raise ExtractError("Không đọc được bài đăng nào trên Threads (trang có thể bắt đăng nhập hoặc đã đổi cấu trúc)")
    codes = []
    for post in posts:
        codes += codes_from_post(post["text"], since=post["since"], link=post["link"])
    return codes


def threads_posts(html: str, user: str) -> list[dict]:
    """The profile's threads, newest first, from the JSON the page ships with."""
    posts = {}
    for script in BeautifulSoup(html, "html.parser").find_all("script"):
        body = script.get_text()
        if "thread_items" not in body:
            continue
        try:
            data = json.loads(body)
        except ValueError:
            continue
        for items in _values_of(data, "thread_items"):
            entries = [i["post"] for i in items if isinstance(i, dict) and isinstance(i.get("post"), dict)]
            entries = [p for p in entries if (p.get("user") or {}).get("username", user).lower() == user.lower()]
            if not entries:
                continue
            # A thread is its post and the author's own replies under it.
            first = entries[0]
            pk = str(first.get("pk") or first.get("id") or "").split("_")[0]
            code = first.get("code") or (_shortcode(int(pk)) if pk.isdigit() else None)
            posts[pk] = {
                "text": "\n".join(_post_text(p) for p in entries),
                "since": _timestamp(first.get("taken_at")),
                "link": THREADS_POST.format(user=user, code=code) if code else None,
            }
    return list(posts.values())


def _values_of(data, key: str):
    """Every value stored under ``key`` anywhere in ``data``."""
    stack = [data]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            if isinstance(value.get(key), list):
                yield value[key]
            stack.extend(reversed(list(value.values())))
        elif isinstance(value, list):
            stack.extend(reversed(value))


def _post_text(post: dict) -> str:
    fragments = (((post.get("text_post_app_info") or {}).get("text_fragments") or {}).get("fragments")) or []
    text = "".join(f.get("plaintext") or "" for f in fragments if isinstance(f, dict))
    return text or ((post.get("caption") or {}).get("text") or "")


def _timestamp(seconds) -> str | None:
    try:
        return utc_iso(datetime.fromtimestamp(int(seconds), timezone.utc))
    except (TypeError, ValueError, OverflowError):
        return None


def _shortcode(pk: int) -> str:
    code = ""
    while pk:
        pk, digit = divmod(pk, 64)
        code = _SHORTCODE[digit] + code
    return code


# --- Discord ---------------------------------------------------------------

DISCORD_API = "https://discord.com/api/v10"
DISCORD_MESSAGE = "https://discord.com/channels/{guild}/{channel}/{message}"
_DISCORD_CHANNEL = re.compile(r"discord(?:app)?\.com/channels/(?P<guild>\d+)/(?P<channel>\d+)")
_CROSSPOSTED = 1 << 1  # message flag: published here from a followed channel


@register("discord", empty_ok=True, feed=True)
def extract_discord(source: Source, fetcher: Fetcher) -> list[Code]:
    """Recent messages of a channel, read with the bot token in ``token_env``.

    A bot cannot join an official server, so the channel is one in your own
    server that follows the official announcements channel.
    """
    match = _DISCORD_CHANNEL.search(source.url)
    if not match:
        raise ExtractError("url Discord phải là link kênh dạng https://discord.com/channels/<id server>/<id kênh>")
    token_env = str(source.get("token_env", "DISCORD_BOT_TOKEN"))
    token = os.environ.get(token_env, "").strip()
    if not token:
        raise ExtractError(f"Chưa có token bot Discord - thêm secret {token_env} (xem README)")
    api = str(source.get("api", DISCORD_API)).rstrip("/")
    page = fetcher.fetch(
        f"{api}/channels/{match['channel']}/messages",
        params={"limit": min(int(source.get("limit", 50)), 100)},  # Discord's maximum
        headers={"Authorization": f"Bot {token}", "User-Agent": "DiscordBot (giftcode-finder, 1.0)"},
        check=False,
    )
    if page.status == 401:
        raise ExtractError(f"Discord từ chối token bot - kiểm tra lại secret {token_env}")
    if page.status in (403, 404):
        raise ExtractError(
            "Bot không xem được kênh này - kiểm tra link kênh và quyền View Channel + Read Message History của bot"
        )
    if page.status >= 400:
        raise ExtractError(f"Discord trả về HTTP {page.status}")
    try:
        messages = json.loads(page.text)
    except ValueError as exc:
        raise ExtractError("Discord trả về dữ liệu không phải JSON") from exc
    if not isinstance(messages, list):
        raise ExtractError("Discord không trả danh sách tin nhắn")
    texts = [_message_text(m) for m in messages]
    if messages and not any(t.strip() for t in texts):
        raise ExtractError(
            "Bot đọc được kênh nhưng tin nhắn trống - bật Message Content Intent cho bot "
            "(Discord Developer Portal → Bot)"
        )
    codes = []
    for message, text in zip(messages, texts):
        codes += codes_from_post(text, since=parse_vn_time(message.get("timestamp")), link=_message_link(message, match))
    return codes


def _message_text(message: dict) -> str:
    parts = [message.get("content") or ""]
    for embed in message.get("embeds") or []:
        parts += [embed.get("title") or "", embed.get("description") or ""]
        for field in embed.get("fields") or []:
            parts += [field.get("name") or "", field.get("value") or ""]
        parts.append((embed.get("footer") or {}).get("text") or "")
    return "\n".join(p for p in parts if p)


def _message_link(message: dict, channel: re.Match) -> str:
    """The original post for a crossposted message, else the message itself."""
    ref = message.get("message_reference") or {}
    if message.get("flags", 0) & _CROSSPOSTED and all(ref.get(k) for k in ("guild_id", "channel_id", "message_id")):
        return DISCORD_MESSAGE.format(guild=ref["guild_id"], channel=ref["channel_id"], message=ref["message_id"])
    return DISCORD_MESSAGE.format(guild=channel["guild"], channel=channel["channel"], message=message.get("id"))
