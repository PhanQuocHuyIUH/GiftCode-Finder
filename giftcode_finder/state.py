"""History of every code seen, persisted in ``data/codes.json``.

Only facts that change when the code list changes are stored (first seen,
removed at, which sources list it), so the scheduled job commits only when
something actually happened.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .codes import DETAIL_FIELDS, Code, code_key

MAX_REMOVED_PER_GAME = 50


@dataclass
class SourceResult:
    game_id: str
    source_id: str
    checked_at: str
    codes: list[Code] | None = None  # None when the source could not be read
    error: str | None = None
    hidden: list[Code] = field(default_factory=list)  # listed, but the value is hidden
    feed: bool = False  # the source only shows recent posts

    @property
    def ok(self) -> bool:
        return self.codes is not None


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_state(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return {"updated_at": None, "games": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: str | Path, state: dict) -> bool:
    """Write ``state``; return False when the file already had that content."""
    path = Path(path)
    text = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def split_hidden(result: SourceResult, items: list[Code], state: dict) -> None:
    """Store ``items`` on ``result``, separating codes from hidden ones.

    A hidden item whose link was seen before with a code gets that code back:
    a source that keeps listing the same event keeps its code, even when the
    value can no longer be fetched (for example after a login expired).
    """
    known = {e["link"]: e["code"] for e in state["games"].get(result.game_id, []) if e.get("link") and e["code"]}
    for item in items:
        if item.code is None and item.link in known:
            item.code = known[item.link]
    result.codes = [i for i in items if i.code is not None]
    result.hidden = [i for i in items if i.code is None]


def attach_events(results: list[SourceResult], state: dict, game_name: str = "") -> None:
    """Give hidden events the codes other sources publish for them.

    Gzone lists "STRINOVA URBINO" without its code while the guide lists
    "URBINO": an event takes a known code that appears as a word of its
    title. Each code belongs to one event; older events choose first, and a
    word equal to the game name is the last resort, so a new "Strinova ..."
    event is not mistaken for the existing STRINOVA code.
    """
    if not results:
        return
    entries = state["games"].get(results[0].game_id, [])
    linked = {e["code"] for e in entries if e["code"] and e.get("link")}
    linked |= {i.code for r in results if r.ok for i in r.codes if i.link}
    pool = [e["code"] for e in entries if e["code"] and not e["removed_at"]]
    pool += [i.code for r in results if r.ok for i in r.codes if not i.link]
    available = {code_key(c): c for c in pool if c not in linked and len(code_key(c)) >= 3}
    game = code_key(game_name)

    events = [(r, i) for r in results if r.ok for i in r.hidden if i.title]
    # Oldest first; sources list newest first, so ties fall back to reverse order.
    order = sorted(range(len(events)), key=lambda n: (events[n][1].since or "", -n))
    choices = {}
    for n in order:
        title = events[n][1].title
        words = {code_key(w) for w in title.split()} | {code_key(title)}
        keys = [k for k in available if k in words]
        choices[n] = sorted(keys, key=lambda k: (k != code_key(title), k == game))

    owner: dict[str, int] = {}

    def assign(n: int, seen: set) -> bool:
        for key in choices[n]:
            if key not in seen:
                seen.add(key)
                if key not in owner or assign(owner[key], seen):
                    owner[key] = n
                    return True
        return False

    for n in order:
        assign(n, set())
    for key, n in owner.items():
        result, item = events[n]
        item.code = available[key]
        result.hidden.remove(item)
        result.codes.append(item)


def entry_key(entry: dict) -> str:
    return entry["code"] or f"link:{entry.get('link')}"


def update_state(state: dict, results: list[SourceResult], now: str) -> tuple[dict, dict[str, list[dict]]]:
    """Fold scrape results into ``state``.

    Returns the new state and, per game, the entries seen for the first time.
    """
    games = dict(state.get("games") or {})
    new_by_game = {}
    for game_id in dict.fromkeys(r.game_id for r in results):
        game_results = [r for r in results if r.game_id == game_id]
        entries, new = merge_game(games.get(game_id, []), game_results, now)
        if entries or game_id in games:
            games[game_id] = entries
        if new:
            new_by_game[game_id] = new
    changed = games != (state.get("games") or {})
    return {
        "updated_at": now if changed else state.get("updated_at"),
        "games": games,
    }, new_by_game


def merge_game(entries: list[dict], results: list[SourceResult], now: str) -> tuple[list[dict], list[dict]]:
    """Merge one game's results into its entries.

    An entry is a code, or - with ``code`` None - an event whose code is
    hidden, keyed by its link. When an event's code becomes known the code
    entry takes over the event's first-seen time.
    """
    previous = {entry_key(e): e for e in entries}
    active: dict[str, dict] = {}

    def entry_for(key: str, code: str | None) -> dict:
        if key not in active:
            old = previous.get(key, {})
            active[key] = {
                "code": code,
                **{name: old.get(name) for name in DETAIL_FIELDS},
                "sources": [],
                "first_seen": old.get("first_seen", now),
                "removed_at": None,
            }
        return active[key]

    def add_source(entry: dict, source_id: str) -> None:
        if source_id not in entry["sources"]:
            entry["sources"].append(source_id)

    for result in results:
        if result.ok:
            for item in result.codes + result.hidden:
                entry = entry_for(item.code or f"link:{item.link}", item.code)
                add_source(entry, result.source_id)
                for name in DETAIL_FIELDS:
                    entry[name] = getattr(item, name) or entry[name]
            if result.feed:
                # A post that scrolled out of the feed still vouches for its
                # codes until they expire.
                for old in entries:
                    if (
                        old["code"]
                        and old["removed_at"] is None
                        and result.source_id in old["sources"]
                        and (old.get("expires_at") or "") > now
                    ):
                        add_source(entry_for(entry_key(old), old["code"]), result.source_id)
        else:
            # A failing source keeps vouching for what it listed last time,
            # so an outage never looks like every code expired.
            for old in entries:
                if old["removed_at"] is None and result.source_id in old["sources"]:
                    add_source(entry_for(entry_key(old), old["code"]), result.source_id)

    # Hidden events whose code is now known fold into that code's entry.
    by_link = {e["link"]: e for e in active.values() if e["code"] and e.get("link")}
    for event in [e for e in entries if not e["code"]] + [e for e in active.values() if not e["code"]]:
        code_entry = by_link.get(event.get("link"))
        if code_entry:
            code_entry["first_seen"] = min(code_entry["first_seen"], event["first_seen"])
            active.pop(entry_key(event), None)

    # Codes no longer listed move to the history; events just disappear.
    removed = []
    for old in entries:
        if old["code"] and entry_key(old) not in active:
            removed.append(old if old["removed_at"] else {**old, "removed_at": now})
    removed.sort(key=lambda e: e["removed_at"], reverse=True)

    new = [e for e in active.values() if e["first_seen"] == now]
    return list(active.values()) + removed[:MAX_REMOVED_PER_GAME], new
