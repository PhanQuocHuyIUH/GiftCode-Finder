import json

from giftcode_finder.config import Game, Source
from giftcode_finder.publish import (
    README_END,
    README_START,
    build_site,
    codes_markdown,
    site_data,
    update_readme,
    vn_time,
)
from giftcode_finder.state import SourceResult

GAME = Game(
    id="g",
    name="Game",
    sources=[Source(id="a", name="Trang A", type="html", url="https://a.test/")],
)
STATE = {
    "updated_at": "2026-10-23T05:00:00Z",
    "games": {
        "g": [
            {"code": "AAA", "reward": "Quà | đặc biệt", "expires": None, "sources": ["a"],
             "first_seen": "2026-10-23T05:00:00Z", "removed_at": None},
            {"code": "OLD", "reward": None, "expires": None, "sources": ["a"],
             "first_seen": "2026-10-01T05:00:00Z", "removed_at": "2026-10-20T05:00:00Z"},
        ]
    },
}
RESULTS = [SourceResult("g", "a", checked_at="2026-10-23T05:00:00Z", codes=[])]


def test_vn_time_converts_to_utc_plus_7():
    assert vn_time("2026-10-23T18:30:00Z") == "24/10/2026 01:30"
    assert vn_time(None) == "—"


def test_markdown_lists_only_active_codes():
    md = codes_markdown(site_data([GAME], STATE, RESULTS, "2026-10-23T06:00:00Z"))
    assert "| `AAA` | Quà \\| đặc biệt | — | 23/10/2026 |" in md
    assert "OLD" not in md
    assert "```text\nAAA\n```" in md
    assert "[Trang A](https://a.test/)" in md


def test_update_readme_replaces_between_markers(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(f"# Title\n{README_START}\nold\n{README_END}\nfooter\n", encoding="utf-8")
    assert update_readme(readme, "new table\n")
    assert readme.read_text(encoding="utf-8") == f"# Title\n{README_START}\nnew table\n{README_END}\nfooter\n"
    assert not update_readme(readme, "new table\n")


def test_build_site_embeds_data_safely(tmp_path):
    template = tmp_path / "tpl"
    template.mkdir()
    (template / "index.html").write_text('<script id="d">__GCF_DATA__</script>', encoding="utf-8")
    data = {"games": [], "note": "</script><b>x</b>"}
    out = build_site(data, template, tmp_path / "out")
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "</script><b>" not in html
    assert json.loads(html.removeprefix('<script id="d">').removesuffix("</script>")) == data
    assert json.loads((out / "codes.json").read_text(encoding="utf-8")) == data


def entry(code, first_seen, since=None, link=None, title=None, expires_at=None):
    return {"code": code, "title": title, "reward": None, "expires": None, "expires_at": expires_at,
            "since": since, "link": link, "sources": ["a"], "first_seen": first_seen, "removed_at": None}


def test_items_are_newest_first_with_hidden_events_inline():
    state = {"updated_at": None, "games": {"g": [
        entry("OLD1", "2026-10-20T00:00:00Z"),
        entry("SAME_A", "2026-10-22T00:00:00Z", since="2026-10-01T00:00:00Z"),
        entry("SAME_B", "2026-10-22T00:00:00Z", since="2026-10-05T00:00:00Z"),
        entry(None, "2026-10-23T00:00:00Z", link="https://x/950", title="Sự kiện mới",
              expires_at="2026-10-30T16:59:59Z"),
    ]}}
    data = site_data([GAME], state, RESULTS, "2026-10-23T06:00:00Z")
    items = data["games"][0]["items"]
    assert [i["code"] or i["title"] for i in items] == ["Sự kiện mới", "SAME_B", "SAME_A", "OLD1"]
    md = codes_markdown(data)
    assert "| 🔒 [Nhận code](https://x/950) | Sự kiện mới | 30/10/2026 23:59 |" in md
    assert "```text\nSAME_B\nSAME_A\nOLD1\n```" in md
    assert "### Game — 3 code, 1 sự kiện cần đăng nhập" in md


def test_build_site_versions_assets(tmp_path):
    template = tmp_path / "tpl"
    template.mkdir()
    (template / "index.html").write_text('<script src="app.js?v=__GCF_VERSION__"></script>__GCF_DATA__', encoding="utf-8")
    (template / "app.js").write_text("one", encoding="utf-8")
    first = (build_site({}, template, tmp_path / "a") / "index.html").read_text(encoding="utf-8")
    (template / "app.js").write_text("two", encoding="utf-8")
    second = (build_site({}, template, tmp_path / "b") / "index.html").read_text(encoding="utf-8")
    assert "__GCF_VERSION__" not in first and first != second


def test_game_with_the_newest_item_comes_first():
    other = Game(id="h", name="Other", sources=[Source(id="a", name="A", type="html", url="https://a.test/")])
    state = {"updated_at": None, "games": {
        "g": [entry("OLDER", "2026-10-20T00:00:00Z")],
        "h": [entry("NEWER", "2026-10-23T00:00:00Z")],
    }}
    data = site_data([GAME, other], state, RESULTS, "2026-10-23T06:00:00Z")
    assert [g["id"] for g in data["games"]] == ["h", "g"]
