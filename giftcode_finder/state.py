"""History of every code seen, persisted in ``data/codes.json``.

Only facts that change when the code list changes are stored (first seen,
removed at, which sources list it), so the scheduled job commits only when
something actually happened.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .codes import Code

MAX_REMOVED_PER_GAME = 50


@dataclass
class SourceResult:
    game_id: str
    source_id: str
    checked_at: str
    codes: list[Code] | None = None  # None when the source could not be read
    error: str | None = None

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


def update_state(state: dict, results: list[SourceResult], now: str) -> tuple[dict, dict[str, list[dict]]]:
    """Fold scrape results into ``state``.

    Returns the new state and, per game, the entries seen for the first time.
    """
    games = dict(state.get("games") or {})
    new_by_game = {}
    for game_id in dict.fromkeys(r.game_id for r in results):
        game_results = [r for r in results if r.game_id == game_id]
        entries, new = merge_game(games.get(game_id, []), game_results, now)
        games[game_id] = entries
        if new:
            new_by_game[game_id] = new
    changed = games != (state.get("games") or {})
    return {
        "updated_at": now if changed else state.get("updated_at"),
        "games": games,
    }, new_by_game


def merge_game(entries: list[dict], results: list[SourceResult], now: str) -> tuple[list[dict], list[dict]]:
    previous = {e["code"]: e for e in entries}
    active: dict[str, dict] = {}

    def entry_for(code: str) -> dict:
        if code not in active:
            old = previous.get(code, {})
            active[code] = {
                "code": code,
                "reward": old.get("reward"),
                "expires": old.get("expires"),
                "sources": [],
                "first_seen": old.get("first_seen", now),
                "removed_at": None,
            }
        return active[code]

    def add_source(entry: dict, source_id: str) -> None:
        if source_id not in entry["sources"]:
            entry["sources"].append(source_id)

    for result in results:
        if result.ok:
            for item in result.codes:
                entry = entry_for(item.code)
                add_source(entry, result.source_id)
                entry["reward"] = item.reward or entry["reward"]
                entry["expires"] = item.expires or entry["expires"]
        else:
            # A failing source keeps vouching for the codes it listed last time,
            # so an outage never looks like every code expired.
            for old in entries:
                if old["removed_at"] is None and result.source_id in old["sources"]:
                    add_source(entry_for(old["code"]), result.source_id)

    removed = []
    for old in entries:
        if old["code"] not in active:
            removed.append(old if old["removed_at"] else {**old, "removed_at": now})
    removed.sort(key=lambda e: e["removed_at"], reverse=True)

    new = [e for code, e in active.items() if code not in previous]
    return list(active.values()) + removed[:MAX_REMOVED_PER_GAME], new
