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
