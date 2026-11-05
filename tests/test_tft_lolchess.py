import json

from giftcode_finder.tft_lolchess import _stats_rows, enrich, fetch_lists


def page(kind, entries):
    data = {"props": {"pageProps": {"dehydratedState": {"queries": [{"state": {"data": {kind: entries}}}]}}}}
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'


def test_stats_rows():
    rows = _stats_rows(["Sát Thương: 455(%i:scaleAP%) [455 / 685 / 3500]", "Thời gian: 2 giây", 5])
    assert rows == [{"name": "Sát Thương", "value": "455/685/3500"}, {"name": "Thời gian", "value": "2 giây"}]


def test_fetch_and_enrich():
    pages = {
        "https://lolchess.gg/champions/set18?hl=vi": page("champions", [
            {"ingameKey": "TFT18_Ahri", "skill": {"name": "Cầu Lửa", "desc": "Gây 455 sát thương.",
                                                  "stats": ["Sát Thương: 455 [455 / 685 / 3500]"],
                                                  "startingMana": 30, "skillMana": 90}}]),
        "https://lolchess.gg/augments/set18?hl=vi": page("augments", [
            {"ingameKey": "TFT18_Augment_Chaos", "desc": "Nhận 3 vàng.", "tiers": [{"stage": "4-2"}]},
            {"ingameKey": "TFT18_Augment_Known", "desc": "Nhận ? vàng.", "stage": ["2-1"]}]),
        "https://lolchess.gg/items/set18?hl=vi": page("items", [
            {"ingameKey": "TFT_Item_Sword", "desc": "Mạnh hơn 10%.", "fromDesc": "%i:scaleAD% +10% SMCK<br>%i:scaleHealth% 150 Máu"}]),
    }

    def fetch(url):
        if url not in pages:
            raise OSError("404")
        return pages[url]

    lists = fetch_lists(18, fetch, log=lambda *_: None)
    assert set(lists) == {"champions", "augments", "items"}
    db = {
        "champions": [{"id": "TFT18_Ahri", "ability": {"name": "Cầu Lửa", "desc": "Gây ? sát thương.", "variables": []},
                       "stats": {"mana": 0, "initialMana": 0}}],
        "augments": [{"id": "TFT18_Augment_Chaos", "desc": "Nhận ? vàng.", "pool": None, "stages": None},
                     {"id": "TFT18_Augment_Known", "desc": "Nhận 2 vàng.", "pool": True, "stages": ["3-2"]}],
        "items": [{"id": "TFT_Item_Sword", "desc": "Mạnh hơn ?%.", "stats": []}],
    }
    counts = enrich(db, lists)
    champ = db["champions"][0]
    assert champ["ability"]["desc"] == "Gây 455 sát thương."
    assert champ["ability"]["variables"] == [{"name": "Sát Thương", "value": "455/685/3500"}]
    assert champ["stats"] == {"mana": 90, "initialMana": 30}
    chaos, known = db["augments"]
    assert chaos["desc"] == "Nhận 3 vàng." and chaos["pool"] is True and chaos["stages"] == ["4-2"]
    # A known description is not replaced by one that still has "?", and known stages stay.
    assert known["desc"] == "Nhận 2 vàng." and known["stages"] == ["3-2"]
    item = db["items"][0]
    assert item["desc"] == "Mạnh hơn 10%."
    assert [s["value"] for s in item["stats"]] == ["+10% SMCK", "150 Máu"]
    assert counts == {"champions": 1, "augments": 1, "stages": 1, "items": 1}
    assert db["filled_from"] == "LoLCHESS.GG"


def test_round_flags_and_name_fallback():
    lists = {
        "augments": [
            {"ingameKey": "TFT18_Augment_Rolls", "desc": "Nhận ? Máu.", "isRound32": True, "isRound42": True, "isRound21": False},
            {"ingameKey": "TFT14_Augment_Rolls", "name": "Ván Cờ May Rủi", "desc": "Nhận 8 Máu.", "isRound21": True},
        ],
        "items": [{"ingameKey": "DA_Item_Old", "name": "Đao Tím", "desc": "Gây thêm 15 sát thương phép."}],
    }
    db = {
        "augments": [{"id": "TFT18_Augment_Rolls", "name": "Ván Cờ May Rủi", "desc": "Nhận ? Máu.", "pool": None, "stages": None}],
        "items": [{"id": "TFT_Item_WitsEnd", "name": "Đao Tím", "desc": "Gây thêm ? sát thương phép.", "stats": []}],
    }
    enrich(db, lists)
    augment = db["augments"][0]
    # Numbers from the namesake, stages only from the entry with the same id.
    assert augment["desc"] == "Nhận 8 Máu." and augment["stages"] == ["3-2", "4-2"]
    assert db["items"][0]["desc"] == "Gây thêm 15 sát thương phép."
