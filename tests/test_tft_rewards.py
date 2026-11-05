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


def test_dice_tables_and_choice_lists():
    dice = """<div class="RewardContainer"><h2 class="title">A Magic Roll</h2><table><thead><tr><th class="dice">Dice Total</th><th>Rewards</th></tr></thead><tbody>
    <tr><td class="dice"><span>4, 5, 6</span></td><td class="inline"><p>Your units gain 250 max HP</p></td></tr>
    <tr><td class="dice"><span>9, 10</span></td><td><div class="RewardItem PortraitReward"><div class="champion"><div class="portrait"><img src="/c.png"/><div class="amount">x2</div></div></div><span class="name">Tướng 2 vàng</span></div></td></tr>
    </tbody></table></div>"""
    table = parse_table(dice, "a-magic-roll", "https://lolchess.gg/x")
    rows = table["groups"][0]["rows"]
    assert rows[0]["chance"] == "4, 5, 6" and rows[0]["items"][0]["name"] == "Your units gain 250 max HP"
    assert (rows[1]["items"][0]["name"], rows[1]["items"][0]["qty"]) == ("Tướng 2 vàng", 2)
    choices = """<div class="RewardContainer"><h2 class="title">Primal</h2><ul><li><div><img src="/b.png"/><h3>Phước Lành Của Gấu</h3></div><p>Hành quyết dưới 12% Máu</p></li></ul></div>"""
    item = parse_table(choices, "primal", "https://lolchess.gg/x")["groups"][0]["rows"][0]["items"][0]
    assert (item["name"], item["desc"]) == ("Phước Lành Của Gấu", "Hành quyết dưới 12% Máu")


def test_older_layout_without_container_class():
    old = """<div><h2 class="title">SET 15 Tables</h2><div class="head"><img src="/ico-crystal.png"/><div class="content"><div><h3 class="title">Crystal Gambit</h3>
    <p class="description">Gain crystals on losses.</p></div><div class="updated-at">Updated: November 5, 2025</div></div></div>
    <section><header><strong>3 Crystal Gambit</strong></header><table><tbody><tr><td class="probability">50%</td>
    <td><div class="RewardItem" data-reward-key="Gold"><div><img src="/g.png"/><span>x4</span></div><div>Vàng</div></div></td></tr></tbody></table></section></div>"""
    table = parse_table(old, "crystal-gambit", "https://lolchess.gg/rewards/set15/crystal-gambit")
    assert (table["title"], table["updated"], table["desc"]) == ("Crystal Gambit", "November 5, 2025", "Gain crystals on losses.")
    assert table["groups"][0]["title"] == "3 Crystal Gambit" and table["groups"][0]["rows"][0]["items"][0]["qty"] == 4
