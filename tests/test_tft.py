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
    fetcher.calls.clear()
    again = update_history(config, result.history, fetcher, log=lambda *_: None)
    assert again.new_versions == [] and article not in fetcher.calls


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
