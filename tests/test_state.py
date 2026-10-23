from giftcode_finder.codes import Code
from giftcode_finder.state import SourceResult, update_state

T1, T2, T3 = "2026-10-23T01:00:00Z", "2026-10-23T02:00:00Z", "2026-10-23T03:00:00Z"


def ok(source_id, *codes, game="g"):
    return SourceResult(game, source_id, checked_at="", codes=[Code(c) for c in codes])


def failed(source_id, game="g"):
    return SourceResult(game, source_id, checked_at="", error="timeout")


def codes(state, game="g"):
    return {e["code"]: e for e in state["games"][game]}


def test_first_run_marks_everything_new():
    state, new = update_state({"games": {}}, [ok("a", "AAA", "BBB")], T1)
    assert [e["code"] for e in new["g"]] == ["AAA", "BBB"]
    assert codes(state)["AAA"] == {
        "code": "AAA",
        "reward": None,
        "expires": None,
        "sources": ["a"],
        "first_seen": T1,
        "removed_at": None,
    }
    assert state["updated_at"] == T1


def test_unchanged_scan_keeps_state_and_timestamp():
    state, _ = update_state({"games": {}}, [ok("a", "AAA")], T1)
    again, new = update_state(state, [ok("a", "AAA")], T2)
    assert again == state
    assert new == {}


def test_new_and_removed_codes():
    state, _ = update_state({"games": {}}, [ok("a", "AAA", "BBB")], T1)
    state, new = update_state(state, [ok("a", "CCC", "AAA")], T2)
    assert [e["code"] for e in new["g"]] == ["CCC"]
    entries = codes(state)
    assert entries["AAA"]["first_seen"] == T1
    assert entries["BBB"]["removed_at"] == T2
    assert [e["code"] for e in state["games"]["g"]] == ["CCC", "AAA", "BBB"]
    assert state["updated_at"] == T2


def test_failed_source_keeps_its_codes_active():
    state, _ = update_state({"games": {}}, [ok("a", "AAA"), ok("b", "BBB")], T1)
    state, new = update_state(state, [ok("a", "AAA"), failed("b")], T2)
    assert new == {}
    assert codes(state)["BBB"]["removed_at"] is None
    assert codes(state)["BBB"]["sources"] == ["b"]


def test_code_listed_by_two_sources_survives_one_removal():
    state, _ = update_state({"games": {}}, [ok("a", "AAA"), ok("b", "AAA")], T1)
    assert codes(state)["AAA"]["sources"] == ["a", "b"]
    state, _ = update_state(state, [ok("a"), ok("b", "AAA")], T2)
    assert codes(state)["AAA"]["removed_at"] is None
    assert codes(state)["AAA"]["sources"] == ["b"]


def test_reappearing_code_is_reactivated_not_new():
    state, _ = update_state({"games": {}}, [ok("a", "AAA")], T1)
    state, _ = update_state(state, [ok("a", "BBB")], T2)
    state, new = update_state(state, [ok("a", "AAA", "BBB")], T3)
    assert new == {}
    assert codes(state)["AAA"]["removed_at"] is None
    assert codes(state)["AAA"]["first_seen"] == T1


def test_details_are_kept_when_a_later_scan_lacks_them():
    state, _ = update_state({"games": {}}, [ok("a", "AAA")], T1)
    rich = SourceResult("g", "a", checked_at="", codes=[Code("AAA", reward="100 KC", expires="31/12")])
    state, _ = update_state(state, [rich], T2)
    state, _ = update_state(state, [ok("a", "AAA")], T3)
    assert codes(state)["AAA"]["reward"] == "100 KC"
    assert codes(state)["AAA"]["expires"] == "31/12"


def test_other_games_untouched():
    state, _ = update_state({"games": {}}, [ok("a", "AAA", game="x"), ok("a", "BBB", game="y")], T1)
    state, _ = update_state(state, [ok("a", "CCC", game="x")], T2)
    assert [e["code"] for e in state["games"]["y"]] == ["BBB"]
    assert codes(state, "y")["BBB"]["removed_at"] is None
