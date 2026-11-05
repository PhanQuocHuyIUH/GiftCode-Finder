from giftcode_finder.tft_db import build_db, clean, fill

GAME = {
    "setData": [
        {"number": 18, "name": "Set18", "champions": [
            {"apiName": "TFT18_Ahri", "name": "Ahri", "cost": 4, "traits": ["Pháp Sư"], "squareIcon": "ASSETS/A.tex",
             "stats": {"hp": 800, "mana": 90, "initialMana": 30, "damage": 45, "armor": 30, "magicResist": 30,
                       "attackSpeed": 0.75, "range": 4, "critChance": 0.25, "critMultiplier": 1.4},
             "ability": {"name": "Cầu Lửa", "desc": "Gây <magicDamage>@ModifiedDamage@ (%i:scaleAP%)</magicDamage> sát thương.<br>Hồi @ManaRefund@ năng lượng, @Chance*100@% cơ hội.",
                         "variables": [{"name": "Damage", "value": [0, 200, 300, 450, 0, 0, 0]},
                                       {"name": "ManaRefund", "value": [0, 10, 10, 10]},
                                       {"name": "Chance", "value": [0, 0.25, 0.25, 0.25]}]}},
            {"apiName": "TFT18_Dummy", "name": "Bù Nhìn", "cost": 8, "traits": []},
        ], "traits": [
            {"apiName": "TFT18_Mage", "name": "Pháp Sư", "icon": "ASSETS/T.tex",
             "desc": "Pháp sư mạnh hơn.<br><row>(@MinUnits@) @AP@ SMPT</row><row>(@MinUnits@) @AP@ SMPT</row>",
             "effects": [{"minUnits": 2, "maxUnits": 3, "style": 1, "variables": {"AP": 20}},
                         {"minUnits": 4, "maxUnits": 25000, "style": 3, "variables": {"AP": 50}}]},
        ]},
        {"number": 18, "name": "Set18_Mode", "champions": []},
    ],
    "items": [
        {"apiName": "TFT_Item_BFSword", "name": "Kiếm B.F.", "desc": "+@AD*100@% SMCK", "effects": {"AD": 0.1}, "composition": []},
        {"apiName": "TFT_Item_Deathblade", "name": "Kiếm Tử Thần", "desc": "Khuếch đại @BonusDamage*100@%",
         "effects": {"AD": 0.55, "BonusDamage": 0.08}, "composition": ["TFT_Item_BFSword", "TFT_Item_BFSword"]},
        {"apiName": "TFT18_Augment_Gold", "name": "Kho Vàng", "desc": "Nhận @Gold@ vàng.", "effects": {"Gold": 10},
         "icon": "ASSETS/Maps/TFT/Icons/Augments/Hexcore/Gold-II.tex"},
        {"apiName": "TFT17_Augment_Old", "name": "Cũ", "desc": "x", "effects": {}},
    ],
}


def test_markup_and_placeholders():
    assert clean("A<br>B %i:scaleAP% <b>C</b>") == "A\nB SMPT C"
    assert fill("@X@ và @Y*100@%", lambda n, t: {"X": "1", "Y": "50" if t else "0,5"}.get(n)) == "1 và 50%"
    assert fill("@Missing@", lambda n, t: None) == "?"


def test_build_db_fills_stats_breakpoints_recipes():
    db = build_db(GAME, 18, "https://cd.test/")
    assert [c["name"] for c in db["champions"]] == ["Ahri"]  # the dummy is not a champion
    ahri = db["champions"][0]
    assert ahri["icon"] == "https://cd.test/assets/a.png" and ahri["stats"]["hp"] == 800
    assert ahri["ability"]["desc"] == "Gây 200/300/450 (SMPT) sát thương.\nHồi 10 năng lượng, 25% cơ hội."
    assert {"name": "Damage", "value": "200/300/450"} in ahri["ability"]["variables"]
    mage = db["traits"][0]
    assert mage["desc"] == "Pháp sư mạnh hơn."
    assert [b["text"] for b in mage["breakpoints"]] == ["(2) 20 SMPT", "(4) 50 SMPT"]
    blade = next(i for i in db["items"] if i["name"] == "Kiếm Tử Thần")
    assert blade["from"] == ["Kiếm B.F.", "Kiếm B.F."] and blade["desc"] == "Khuếch đại 8%"
    assert {"label": "SMCK", "value": "55%"} in blade["stats"]
    assert [a["name"] for a in db["augments"]] == ["Kho Vàng"] and db["augments"][0]["tier"] == 2
    assert db["augments"][0]["desc"] == "Nhận 10 vàng."
    assert build_db(GAME, 99, "https://cd.test/") is None


def test_hashed_keys_and_literal_newlines():
    from giftcode_finder.tft_db import fnv1a

    assert fnv1a("StonebarkTreeBonusHealth") == "{b027c2f9}"
    assert clean("A \\n B") == "A\nB"
    game = {"setData": [{"number": 19, "champions": [
        {"apiName": "DA_19_Akali", "name": "Akali", "cost": 1, "traits": ["X"], "stats": {},
         "ability": {"desc": "Gây @ModifiedDamage@ sát thương.", "variables": []}}],
        "traits": [{"name": "Rừng", "desc": "<row>(@MinUnits@) +@StonebarkTreeBonusHealth@ Máu</row>",
                    "effects": [{"minUnits": 3, "variables": {"{b027c2f9}": 200.0}}]}]}], "items": []}
    db = build_db(game, 19, "https://cd.test/")
    assert db["champions"][0]["ability"]["desc"] == "Gây ? sát thương."  # the page fills in patch-note values
    assert db["traits"][0]["breakpoints"][0]["text"] == "(3) +200 Máu"


def test_augment_stages_pool_and_item_kinds():
    from giftcode_finder.tft_db import item_kind

    game = {"setData": [{"number": 20, "champions": [], "traits": [],
                         "augments": ["TFT20_Augment_Chaos", "TFT20_Augment_Chaos_Variant", "TFT20_Augment_Patience"],
                         "items": ["TFT_Item_BFSword", "TFT_Item_Deathblade", "TFT5_Item_DeathbladeRadiant", "TFT_Item_Artifact_Fishbones", "TFT20_Item_FooEmblemItem"]}],
            "items": [
        {"apiName": "TFT20_Augment_Chaos", "name": "Triệu Gọi Hỗn Mang", "desc": "Nhận 1 phần thưởng ngẫu nhiên.",
         "tags": ["{b72bd3bf}", "{d02ae323}", "{d12ae4b6}", "{cf1fd3af}"]},
        {"apiName": "TFT20_Augment_Chaos_Variant", "name": "Triệu Gọi Hỗn Mang", "desc": "Biến thể.", "tags": ["{cf1fd3af}"]},
        {"apiName": "TFT20_Augment_Patience", "name": "Kiên Nhẫn", "desc": "Đổi miễn phí.",
         "tags": ["{b72bd3bf}", "{d12ae4b6}", "{d22ae649}", "{d11fd6d5}"]},
        {"apiName": "TFT_Item_BFSword", "name": "Kiếm B.F.", "desc": "x", "tags": ["component"]},
        {"apiName": "TFT_Item_Deathblade", "name": "Kiếm Tử Thần", "desc": "x", "composition": ["TFT_Item_BFSword", "TFT_Item_BFSword"]},
        {"apiName": "TFT5_Item_DeathbladeRadiant", "name": "Kiếm Tử Thần Ánh Sáng", "desc": "x"},
        {"apiName": "TFT_Item_Artifact_Fishbones", "name": "Đại Bác", "desc": "x"},
        {"apiName": "TFT20_Item_FooEmblemItem", "name": "Ấn Foo", "desc": "x", "composition": ["TFT_Item_Spatula", "TFT_Item_BFSword"]},
    ]}
    db = build_db(game, 20, "https://cd.test/")
    chaos = [a for a in db["augments"] if a["name"] == "Triệu Gọi Hỗn Mang"]
    assert len(chaos) == 1 and chaos[0]["pool"] and chaos[0]["stages"] == ["4-2"] and chaos[0]["tier"] == 3
    patience = next(a for a in db["augments"] if a["name"] == "Kiên Nhẫn")
    assert patience["stages"] == ["2-1"] and patience["tier"] == 1
    kinds = {i["name"]: i["kind"] for i in db["items"]}
    assert kinds == {"Kiếm B.F.": "component", "Kiếm Tử Thần": "completed", "Kiếm Tử Thần Ánh Sáng": "radiant",
                     "Đại Bác": "artifact", "Ấn Foo": "emblem"}
    assert item_kind({"apiName": "DA_18_AfterShock", "icon": "assets/ux/tft/hud/zaps/wands/x.tex"}) == "mechanic"


def test_items_listed_twice_are_merged():
    from giftcode_finder.tft_db import merge_items

    items = merge_items([
        {"name": "Huyết Kiếm", "desc": "", "stats": [], "from": [], "icon": None, "kind": "other"},
        {"name": "Huyết Kiếm", "desc": "Hút máu.", "stats": [{"label": "SMCK", "value": "15%"}], "from": ["a", "b"], "icon": "i", "kind": "completed"},
        {"name": "Ấn Gai Đen", "desc": "", "stats": [], "from": [], "kind": "emblem"},
    ])
    assert items[0] == {"name": "Huyết Kiếm", "desc": "Hút máu.", "stats": [{"label": "SMCK", "value": "15%"}], "from": ["a", "b"], "icon": "i", "kind": "completed"}
    assert items[1]["desc"] == "Người mang trang bị này được tính thêm tộc/hệ Gai Đen."
