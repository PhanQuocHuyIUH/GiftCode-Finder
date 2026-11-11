import json
from pathlib import Path

from giftcode_finder.tft import (
    Article,
    TftConfig,
    build_names,
    direction,
    parse_article,
    parse_listing,
    update_history,
    version_of,
)

FIXTURES = Path(__file__).parent / "fixtures"
NAMES = {
    "setData": [
        {"number": 15, "champions": [{"name": "Old", "traits": ["x"]}]},
        {
            "number": 16,
            "champions": [
                {"name": "Ahri", "traits": ["x"], "squareIcon": "ASSETS/Characters/TFT16_Ahri/HUD/TFT16_Ahri_Square.TFT_Set16.tex"},
                {"name": "Kai'Sa", "traits": ["x"]},
                {"name": "Jinx", "traits": ["x"]},
                {"name": "Target Dummy", "traits": []},
            ],
            "traits": [{"name": "Bruiser", "icon": "ASSETS/UX/Traits/Bruiser.tex"}, {"name": "Sorcerer"}],
        },
    ],
    "items": [
        {"apiName": "TFT_Item_Bloodthirster", "name": "Bloodthirster", "icon": "ASSETS/Items/BT.tex"},
        {"apiName": "TFT_Item_BlueBuff", "name": "Blue Buff"},
        {"apiName": "TFT16_Augment_Cyber", "name": "Cybernetic Implants"},
    ],
}
ARTICLE = Article(
    url="https://teamfighttactics.leagueoflegends.com/en-us/news/game-updates/teamfight-tactics-patch-16-5-notes/",
    title="Teamfight Tactics patch 16.5 notes",
    version="16.5",
    locale="en-us",
)


def parsed():
    names = build_names(NAMES, 16, "https://cd.test/")
    return parse_article((FIXTURES / "tft_patch_sample.html").read_text(encoding="utf-8"), ARTICLE, names)


def changes(patch, kind):
    return [c for s in patch["sections"] if s["kind"] == kind for c in s["changes"]]


def test_version_from_title_or_url():
    assert version_of("Teamfight Tactics patch 16.5 notes", "") == "16.5"
    assert version_of("Bản cập nhật ĐTCL 17.2b", "") == "17.2b"
    assert version_of("Patch notes", "https://x.test/vi-vn/news/game-updates/teamfight-tactics-patch-16-10-notes/") == "16.10"
    assert version_of("Teamfight Tactics patch 13.6 notes (2025)", "/teamfight-tactics-patch-136-notes-2025/") == "13.6"
    assert version_of("Dev blog", "/news/dev/dev-blog/") is None


def test_direction_reads_numbers_and_inverts_costs():
    assert direction("Ability Damage", "200/300/450", "220/330/500") == "buff"
    assert direction("Mana", "0/60", "0/50") == "buff"
    assert direction("Level 8 XP cost", "68", "72") == "nerf"
    assert direction("Mana Refund", "10", "8") == "nerf"
    assert direction("Năng lượng", "30/90", "30/80") == "buff"
    assert direction("Giảm hồi chiêu", "10%", "15%") == "buff"
    assert direction("Damage", "100/200", "120/180") == "adjust"
    assert direction("Tier", "Silver", "Gold") == "adjust"


def test_article_sections_and_subjects():
    patch = parsed()
    assert patch["version"] == "16.5" and patch["set"] == 16
    assert patch["published_at"] == "2026-10-21T18:00:00Z"
    assert patch["highlights"] == "https://cmsassets.rgpub.io/highlights.png"
    champs = changes(patch, "champions")
    assert [(c["subject"], c["stat"], c["dir"]) for c in champs] == [
        ("Ahri", "Mana", "buff"),
        ("Ahri", "Ability Damage", "nerf"),
        ("Kai'Sa", "Attack Speed", "buff"),
        ("Jinx", "Rocket Damage", "nerf"),  # under a "Nerfs" heading
    ]
    assert champs[0]["group"] == "Tier 1"
    assert patch["icons"]["Ahri"] == "https://cd.test/assets/characters/tft16_ahri/hud/tft16_ahri_square.tft_set16.png"
    traits = changes(patch, "traits")
    assert [(c["subject"], c["dir"]) for c in traits] == [("Bruiser", "nerf"), ("Sorcerer", "buff")]
    items = changes(patch, "items")
    assert [c["dir"] for c in items] == ["buff", "nerf", "removed"]
    assert changes(patch, "augments")[0]["subject"] == "Cybernetic Implants"
    assert [c["dir"] for c in changes(patch, "mechanics")] == ["nerf", "new"]
    assert changes(patch, "fixes")[0]["dir"] == "fix"
    assert patch["sections"][0]["notes"] == ["Welcome to patch 16.5! This patch tones down fast 8."]


def test_names_skip_other_sets_and_dummies():
    names = build_names(NAMES, 16, "https://cd.test/")
    known = {name for name, _, _ in names.entries}
    assert "old" not in known and "target dummy" not in known
    assert names.match("Kai'Sa Attack Speed")[0] == "Kai'Sa"
    assert names.match("Ahriman Mana") is None


def test_listing_reads_links_and_next_data():
    data = {"props": {"pageProps": {"page": {"blades": [{"items": [
        {"title": "Teamfight Tactics patch 16.4 notes", "publishedAt": "2026-10-07T18:00:00.000Z",
         "action": {"payload": {"url": "/en-us/news/game-updates/teamfight-tactics-patch-16-4-notes/"}},
         "media": {"url": "https://img.test/164.jpg"}},
        {"title": "Patch 16.5 preview", "action": {"payload": {"url": "/en-us/news/dev/patch-16-5-preview/"}}},
    ]}]}}}}
    html = (
        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
        '<a href="/en-us/news/game-updates/teamfight-tactics-patch-16-5-notes/"><h2>Teamfight Tactics patch 16.5 notes</h2>'
        '<time datetime="2026-10-21T18:00:00.000Z"></time></a>'
        '<a href="/en-us/news/game-updates/teamfight-tactics-patch-16-4-notes/">Teamfight Tactics patch 16.4 notes</a>'
    )
    found = parse_listing(html, "https://teamfighttactics.leagueoflegends.com/en-us/news/tags/patch-notes/")
    assert [a.version for a in found] == ["16.5", "16.4"]
    assert found[0].url == "https://teamfighttactics.leagueoflegends.com/en-us/news/game-updates/teamfight-tactics-patch-16-5-notes/"
    assert found[0].published_at == "2026-10-21T18:00:00.000Z"
    assert found[1].image == "https://img.test/164.jpg" and found[1].locale == "en-us"


class FakeFetcher:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def fetch(self, url, **kwargs):
        self.calls.append(url)
        if url not in self.pages:
            raise RuntimeError(f"HTTP 404 {url}")

        class Page:
            pass

        page = Page()
        page.url, page.text = url, self.pages[url]
        return page


def test_history_keeps_old_patches_and_reads_new_once():
    listing = "https://t.test/en-us/news/tags/patch-notes/"
    article = "https://t.test/en-us/news/game-updates/teamfight-tactics-patch-16-5-notes/"
    fetcher = FakeFetcher({
        listing: f'<a href="{article}">Teamfight Tactics patch 16.5 notes</a>',
        article: (FIXTURES / "tft_patch_sample.html").read_text(encoding="utf-8"),
    })
    config = TftConfig(listings=["https://broken.test/", listing])
    old = {"version": "16.4", "set": 16, "sections": [], "published_at": "2026-10-07T18:00:00Z"}
    result = update_history(config, {"patches": [old]}, fetcher, log=lambda *_: None)
    assert result.new_versions == ["16.5"]
    assert [p["version"] for p in result.history["patches"]] == ["16.5", "16.4"]
    assert result.errors and "broken.test" in result.errors[0]
    stamp = result.history["updated_at"]
    again = update_history(config, result.history, fetcher, log=lambda *_: None)
    # The newest article is fetched again for B-patches, but unchanged text is not re-parsed.
    assert again.new_versions == [] and again.history["updated_at"] == stamp


VI_NAMES = {
    "setData": [{"number": 18, "champions": [
        {"name": "Caitlyn", "traits": ["x"], "squareIcon": "ASSETS/c.tex"},
        {"name": "Bụi Gai Đỏ", "traits": ["x"]},
    ], "traits": [{"name": "Gai Đen", "icon": "ASSETS/g.tex"}, {"name": "Tiên Linh", "icon": "ASSETS/t.tex"}]}],
    "items": [{"apiName": "TFT_Item_Radiant_Adaptive", "name": "Mũ Thích Nghi"}],
}


def test_vietnamese_article_structure():
    names = build_names(VI_NAMES, 18, "https://cd.test/")
    article = Article("https://t.test/vi-vn/news/game-updates/teamfight-tactics-patch-18-5",
                      "Thông tin cập nhật ĐTCL 18.5", "18.5", locale="vi-vn")
    patch = parse_article((FIXTURES / "tft_patch_vi.html").read_text(encoding="utf-8"), article, names)
    assert patch["title"] == "Thông tin cập nhật ĐTCL 18.5"
    assert patch["highlights"] == "https://cmsassets.rgpub.io/185-highlights.jpg"
    titles = [s["title"] for s in patch["sections"]]
    assert not any("TRANG TRÍ" in t for t in titles)  # cosmetics are skipped
    mid = patch["sections"][1]["changes"]
    assert (mid[0]["subject"], mid[0]["kind"], mid[0]["dir"], mid[0]["date"]) == ("Bụi Gai Đỏ", "champions", "nerf", "Ngày 22/10")
    assert [(c["subject"], c["dir"]) for c in mid[1:3]] == [("Đổ Xúc Xắc", "buff"), ("Tay Sai", "nerf")]
    assert mid[1]["group"] == "TINH LINH"
    assert mid[3]["dir"] == "fix"
    big = {c["subject"]: c for s in patch["sections"] if s["title"] == "THAY ĐỔI LỚN" for c in s["changes"]}
    assert big["Gai Đen"]["kind"] == "traits" and big["Gai Đen"]["dir"] == "nerf"
    assert big["Tiên Linh (2/4)"]["dir"] == "buff" and patch["icons"]["Tiên Linh (2/4)"] == "https://cd.test/assets/t.png"
    assert big["Caitlyn"]["kind"] == "champions" and big["Caitlyn"]["group"] == "Bậc 2" and big["Caitlyn"]["dir"] == "buff"
    assert big["Mũ Thích Nghi"]["kind"] == "items" and big["Mũ Thích Nghi"]["dir"] == "nerf"
    augment = [c for c in big.values() if c["kind"] == "augments"]
    assert augment and augment[0]["dir"] == "nerf"


def test_new_parser_version_reads_listed_patches_again():
    listing = "https://t.test/en-us/news/tags/patch-notes/"
    article = "https://t.test/en-us/news/game-updates/teamfight-tactics-patch-16-5-notes/"
    fetcher = FakeFetcher({
        listing: f'<a href="{article}">Teamfight Tactics patch 16.5 notes</a>',
        article: (FIXTURES / "tft_patch_sample.html").read_text(encoding="utf-8"),
    })
    stale = {"version": "16.5", "set": 16, "sections": [], "fetched_at": "2099-01-01T00:00:00Z"}
    result = update_history(TftConfig(listings=[listing]), {"parser": 0, "patches": [stale]}, fetcher, log=lambda *_: None)
    assert article in fetcher.calls
    assert result.history["patches"][0]["sections"] and result.history["parser"] > 0


def test_numbers_with_thousands_and_several_stats_in_one_bullet():
    assert direction("Sát Thương", "700 SMPT", "1.000 SMPT") == "buff"
    assert direction("Damage", "1,100", "950") == "nerf"
    assert direction("Tốc Độ Đánh", "0,8", "0,85") == "buff"
    from giftcode_finder.tft import Names, _Parser

    parser = _Parser(Names())
    parser.open_section("THAY ĐỔI LỚN")
    parser.add("Sát Thương Chính: 1.100 SMPT ⇒ 1.500 SMPT, Thời Gian Choáng: 1,5 giây ⇒ 3 giây", "Meep")
    assert [(c["stat"], c["after"], c["subject"]) for c in parser.sections[0].changes] == [
        ("Sát Thương Chính", "1.500 SMPT", "Meep"), ("Thời Gian Choáng", "3 giây", "Meep")]


def test_mid_patch_updates_become_lettered_hotfixes():
    from giftcode_finder.tft import hotfixes

    names = build_names(VI_NAMES, 18, "https://cd.test/")
    article = Article("https://t.test/vi-vn/news/game-updates/teamfight-tactics-patch-18-5", "ĐTCL 18.5", "18.5", "2026-10-20T18:00:00Z", locale="vi-vn")
    patch = parse_article((FIXTURES / "tft_patch_vi.html").read_text(encoding="utf-8"), article, names)
    assert patch["hotfixes"] == [{"id": "b", "label": "18.5b", "date": "2026-10-22", "count": 4,
                                  "counts": {"buff": 1, "nerf": 2, "adjust": 0, "new": 0, "removed": 0, "fix": 1}}]
    mid = patch["sections"][1]
    assert mid["mid"] and all(c["hotfix"] == "b" and "mid" not in c for c in mid["changes"])
    assert not any("hotfix" in c for s in patch["sections"][2:] for c in s["changes"])

    # Several dated updates are lettered in date order; an explicit "15.1B" keeps its letter.
    changes = [{"mid": "20/08", "dir": "buff"}, {"mid": "13/08", "dir": "nerf"}, {"mid": "15/08", "dir": "fix"}]
    fixes = hotfixes(changes, "15.2", "2025-08-12T18:00:00Z")
    assert [(f["label"], f["date"]) for f in fixes] == [("15.2b", "2025-08-13"), ("15.2c", "2025-08-15"), ("15.2d", "2025-08-20")]
    assert [c["hotfix"] for c in changes] == ["d", "b", "c"]
    assert [f["label"] for f in hotfixes([{"mid": "b", "dir": "buff"}], "15.1", None)] == ["15.1b"]


def test_nested_forms_stay_with_their_champion():
    from giftcode_finder.tft import _Parser
    from bs4 import BeautifulSoup

    names = build_names({"setData": [{"number": 18, "champions": [{"name": "Nidalee", "traits": ["x"]}]}]}, 18, "https://cd.test/")
    parser = _Parser(names)
    parser.open_section("THAY ĐỔI LỚN")
    html = "<ul><li>Nidalee<ul><li>Dạng SMCK<ul><li>Hồi máu: 300 ⇒ 325</li></ul></li></ul></li></ul>"
    parser.list(BeautifulSoup(html, "html.parser").ul)
    change = parser.sections[0].changes[0]
    assert (change["subject"], change["group"], change["dir"]) == ("Nidalee", "Dạng SMCK", "buff")


def test_daily_refresh_runs_once_per_day(tmp_path):
    from datetime import datetime, timezone

    from giftcode_finder.tft import _due_today, _mark_done

    db_dir = tmp_path / "tft_db"
    morning = datetime(2026, 11, 10, 2, 14, tzinfo=timezone.utc)
    assert _due_today(db_dir, "sheets", morning)
    _mark_done(db_dir, "sheets", morning)
    # Later the same day: done; the next day, whatever the hour: due again.
    assert not _due_today(db_dir, "sheets", morning.replace(hour=23))
    assert _due_today(db_dir, "rewards", morning)
    assert _due_today(db_dir, "sheets", datetime(2026, 11, 11, 15, 21, tzinfo=timezone.utc))
