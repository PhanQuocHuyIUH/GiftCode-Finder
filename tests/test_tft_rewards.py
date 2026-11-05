from pathlib import Path

from giftcode_finder.tft_rewards import build_rewards, list_tables, parse_table

HTML = (Path(__file__).parent / "fixtures" / "lolchess_rewards.html").read_text(encoding="utf-8")
EXPEDITION = """<div class="RewardContainer"><img src="/ico.png"/><h2 class="title">Expedition</h2>
<div class="description"><p>After losing 33 gold of champions, gain a powerful reward.</p></div>
<section data-reward-row-key="DT_Expedition"><div class="RewardItem" data-reward-key="FiveCostUnit"><div><img src="/5cost.png"/><span>x2</span></div><div>Tướng 5 vàng</div></div>
<div class="RewardItem" data-reward-key="Gold"><div><img src="/gold.png"/><span>x15</span></div><div>Vàng</div></div></section></div>"""


def test_menu_lists_loot_tables_only():
    assert list_tables(HTML, 18) == ["coven", "expedition"]


def test_table_with_milestones_and_chances():
    table = parse_table(HTML, "coven", "https://lolchess.gg/rewards/set18/coven?hl=vi")
    assert table["title"] == "Coven" and table["updated"] == "October 21, 2026"
    assert table["desc"].startswith("Gather Essence")
    group = table["groups"][0]
    assert group["title"] == "130 Essence" and group["note"] == "28 Sức Mạnh Phép Thuật"
    assert group["rows"][0] == {"chance": "25%", "items": [
        {"key": "Gold", "name": "Vàng", "qty": 6, "icon": "https://cdn.dak.gg/ico-gold.png"},
        {"key": "Component", "name": "Trang Bị Thành Phần Ngẫu Nhiên", "qty": None, "icon": "https://cdn.dak.gg/ico-component.png"},
    ]}


def test_plain_list_and_links_to_the_season_data():
    db = {"augments": [{"id": "TFT_Augment_Expedition", "name": "Cuộc Viễn Chinh"}],
          "traits": [{"id": "DA_18_Coven", "name": "Tiên Hắc Ám"}],
          "champions": [{"id": "DA_18_Elise", "name": "Elise", "cost": 1}], "items": []}
    pages = {"https://lolchess.gg/rewards/set18?hl=vi": HTML,
             "https://lolchess.gg/rewards/set18/coven?hl=vi": HTML,
             "https://lolchess.gg/rewards/set18/expedition?hl=vi": EXPEDITION}
    rewards = build_rewards(18, pages.__getitem__, db, log=lambda *_: None)
    coven, expedition = rewards["tables"]
    assert coven["links"] == ["Tiên Hắc Ám"] and expedition["links"] == ["Cuộc Viễn Chinh"]
    elise = coven["groups"][0]["rows"][1]["items"][0]
    assert (elise["name"], elise["kind"], elise["cost"], elise["qty"]) == ("Elise", "champions", 1, 3)
    row = expedition["groups"][0]["rows"][0]
    assert row["chance"] is None and [(i["name"], i["qty"]) for i in row["items"]] == [("Tướng 5 vàng", 2), ("Vàng", 15)]
    assert row["items"][0]["icon"] == "https://lolchess.gg/5cost.png"
