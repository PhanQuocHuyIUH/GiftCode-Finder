"""Loading and validating ``config/sources.yaml``."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_ID = re.compile(r"[a-z0-9][a-z0-9_-]*")


class ConfigError(Exception):
    pass


@dataclass
class Source:
    id: str
    name: str
    type: str
    url: str
    options: dict = field(default_factory=dict)

    def get(self, key: str, default=None):
        return self.options.get(key, default)


@dataclass
class Game:
    id: str
    name: str
    sources: list[Source]
    redeem_url: str | None = None
    redeem_note: str | None = None


def load_config(path: str | Path) -> list[Game]:
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Không đọc được {path}: {exc}") from exc
    games = [_game(entry, i) for i, entry in enumerate(raw.get("games") or [])]
    if not games:
        raise ConfigError(f"{path}: chưa có game nào trong mục 'games'")
    _unique([g.id for g in games], "game")
    return games


def _game(entry: dict, index: int) -> Game:
    where = f"games[{index}]"
    if not isinstance(entry, dict):
        raise ConfigError(f"{where}: phải là một object")
    game_id = _require_id(entry, where)
    where = f"game '{game_id}'"
    sources = [_source(s, where, i) for i, s in enumerate(entry.get("sources") or [])]
    if not sources:
        raise ConfigError(f"{where}: cần ít nhất một nguồn trong 'sources'")
    _unique([s.id for s in sources], f"nguồn của {where}")
    return Game(
        id=game_id,
        name=str(entry.get("name") or game_id),
        sources=sources,
        redeem_url=entry.get("redeem_url"),
        redeem_note=entry.get("redeem_note"),
    )


def _source(entry: dict, game_where: str, index: int) -> Source:
    # Imported here so the extractor registry is filled before validation.
    from .extractors import EXTRACTORS

    where = f"{game_where} sources[{index}]"
    if not isinstance(entry, dict):
        raise ConfigError(f"{where}: phải là một object")
    options = dict(entry)
    source_id = _require_id(options, where)
    where = f"{game_where} nguồn '{source_id}'"
    kind = options.pop("type", None)
    if kind not in EXTRACTORS:
        raise ConfigError(f"{where}: 'type' phải là một trong {sorted(EXTRACTORS)}")
    url = options.pop("url", None)
    if not url or not str(url).startswith(("http://", "https://")):
        raise ConfigError(f"{where}: thiếu 'url' hợp lệ")
    options.pop("id")
    return Source(
        id=source_id,
        name=str(options.pop("name", None) or source_id),
        type=kind,
        url=str(url),
        options=options,
    )


def _require_id(entry: dict, where: str) -> str:
    value = str(entry.get("id") or "")
    if not _ID.fullmatch(value):
        raise ConfigError(f"{where}: 'id' phải gồm chữ thường, số, '-' hoặc '_' (đang là {value!r})")
    return value


def _unique(ids: list[str], what: str) -> None:
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ConfigError(f"Trùng id {what}: {', '.join(dupes)}")
