import pytest

from giftcode_finder.config import ConfigError, load_config


def write(tmp_path, text):
    path = tmp_path / "sources.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_bundled_config_is_valid():
    games = load_config("config/sources.yaml")
    assert games and all(g.sources for g in games)


def test_source_options_are_passed_through(tmp_path):
    games = load_config(write(tmp_path, """
games:
  - id: g
    name: Game
    sources:
      - id: s
        type: html
        url: https://example.test/
        code: .code
        render: true
"""))
    source = games[0].sources[0]
    assert (source.type, source.name, source.options) == ("html", "s", {"code": ".code", "render": True})


@pytest.mark.parametrize(
    "body, message",
    [
        ("games: []", "chưa có game"),
        ("games:\n  - id: Bad Id\n    sources: []", "'id'"),
        ("games:\n  - id: g\n    sources: []", "ít nhất một nguồn"),
        ("games:\n  - id: g\n    sources:\n      - {id: s, type: nope, url: 'https://x.test'}", "'type'"),
        ("games:\n  - id: g\n    sources:\n      - {id: s, type: html, url: 'ftp://x'}", "'url'"),
        (
            "games:\n  - id: g\n    sources:\n      - {id: s, type: html, url: 'https://x.test'}\n"
            "  - id: g\n    sources:\n      - {id: s, type: html, url: 'https://x.test'}",
            "Trùng id",
        ),
    ],
)
def test_invalid_configs(tmp_path, body, message):
    with pytest.raises(ConfigError, match=message):
        load_config(write(tmp_path, body))
