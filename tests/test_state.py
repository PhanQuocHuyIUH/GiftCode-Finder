from giftcode_finder.codes import Code
from giftcode_finder.state import SourceResult, attach_events, split_hidden, update_state

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
        "title": None,
        "reward": None,
        "expires": None,
        "expires_at": None,
        "since": None,
        "link": None,
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


def test_failing_source_without_history_records_nothing():
    state, new = update_state({"updated_at": None, "games": {}}, [failed("a")], T1)
    assert state == {"updated_at": None, "games": {}}
    assert new == {}


def test_split_hidden_restores_codes_learned_from_the_same_link():
    state, _ = update_state(
        {"games": {}},
        [SourceResult("g", "a", checked_at="", codes=[Code("P.U.S", title="Strinova PUS", link="https://x/941")])],
        T1,
    )
    result = SourceResult("g", "a", checked_at="")
    split_hidden(result, [Code(None, title="Strinova PUS", link="https://x/941"), Code(None, link="https://x/942")], state)
    assert [(c.code, c.link) for c in result.codes] == [("P.U.S", "https://x/941")]
    assert [c.link for c in result.hidden] == ["https://x/942"]
    state, new = update_state(state, [result], T2)
    assert [e["link"] for e in new["g"]] == ["https://x/942"]
    assert codes(state)["P.U.S"]["removed_at"] is None


def hidden(source_id, *links, game="g"):
    result = SourceResult(game, source_id, checked_at="", codes=[])
    result.hidden = [Code(None, title=f"Event {link}", link=link) for link in links]
    return result


def events(state, game="g"):
    return {e["link"]: e for e in state["games"][game] if e["code"] is None}


def test_hidden_events_are_tracked_like_codes():
    state, new = update_state({"games": {}}, [hidden("a", "L1", "L2")], T1)
    assert [e["link"] for e in new["g"]] == ["L1", "L2"]
    assert events(state)["L1"]["first_seen"] == T1
    state, new = update_state(state, [hidden("a", "L1", "L2", "L3")], T2)
    assert [e["link"] for e in new["g"]] == ["L3"]


def test_event_code_found_later_keeps_the_event_first_seen():
    state, _ = update_state({"games": {}}, [hidden("a", "L1")], T1)
    revealed = SourceResult("g", "a", checked_at="", codes=[Code("URBINO", title="Event L1", link="L1")])
    state, new = update_state(state, [revealed], T2)
    assert new == {}
    assert events(state) == {}
    assert codes(state)["URBINO"]["first_seen"] == T1


def test_vanished_event_leaves_no_history():
    state, _ = update_state({"games": {}}, [hidden("a", "L1"), ok("b", "AAA")], T1)
    state, _ = update_state(state, [hidden("a"), ok("b", "AAA")], T2)
    assert [e["code"] for e in state["games"]["g"]] == ["AAA"]


GZONE_EVENTS = [
    ("STRINGIFY", "945", "2026-10-21T04:45:00Z"),
    ("SUPERSTRING", "944", "2026-10-21T04:45:00Z"),
    ("STRINOVA URBINO", "943", "2026-10-20T04:44:00Z"),
    ("THESCISSORS", "942", "2026-10-21T04:34:00Z"),
    ("Strinova PUS", "941", "2026-10-21T04:33:00Z"),
    ("Strinova VN", "940", "2026-10-20T04:32:00Z"),
]
GUIDE_CODES = ["STRINOVA", "P.U.S", "THESCISSORS", "URBINO", "SUPERSTRING", "STRINGIFY"]


def gzone(*extra):
    result = SourceResult("g", "gzone", checked_at="", codes=[])
    result.hidden = [Code(None, title=t, link=l, since=s) for t, l, s in [*GZONE_EVENTS, *extra]]
    return result


def test_attach_events_matches_event_titles_to_published_codes():
    results = [ok("guide", *GUIDE_CODES), gzone()]
    attach_events(results, {"games": {}}, game_name="Strinova")
    assert results[1].hidden == []
    assert {c.link: c.code for c in results[1].codes} == {
        "945": "STRINGIFY",
        "944": "SUPERSTRING",
        "943": "URBINO",
        "942": "THESCISSORS",
        "941": "P.U.S",
        "940": "STRINOVA",
    }


def test_new_event_named_after_the_game_stays_hidden():
    state, _ = update_state({"games": {}}, [ok("guide", *GUIDE_CODES)], T1)
    results = [ok("guide", *GUIDE_CODES), gzone(("Strinova Halloween", "950", "2026-10-31T00:00:00Z"))]
    attach_events(results, state, game_name="Strinova")
    assert [c.title for c in results[1].hidden] == ["Strinova Halloween"]
    assert {c.link: c.code for c in results[1].codes}["940"] == "STRINOVA"


def test_attach_events_skips_codes_already_tied_to_another_event():
    state, _ = update_state(
        {"games": {}},
        [SourceResult("g", "gzone", checked_at="", codes=[Code("STRINOVA", title="Strinova VN", link="940")])],
        T1,
    )
    result = SourceResult("g", "gzone", checked_at="", codes=[])
    result.hidden = [Code(None, title="Strinova Halloween", link="950")]
    attach_events([result], state, game_name="Strinova")
    assert [c.title for c in result.hidden] == ["Strinova Halloween"]


def test_attach_events_skips_codes_tied_to_an_event_in_the_same_run():
    revealed = SourceResult("g", "gzone", checked_at="", codes=[Code("URBINO", title="STRINOVA URBINO", link="943")])
    revealed.hidden = [Code(None, title="URBINO VIP", link="999")]
    results = [ok("guide", "URBINO"), revealed]
    attach_events(results, {"games": {}}, game_name="Strinova")
    assert [c.title for c in revealed.hidden] == ["URBINO VIP"]


def feed(source_id, *codes, game="g"):
    return SourceResult(game, source_id, checked_at="", codes=list(codes), feed=True)


def test_feed_keeps_codes_until_they_expire():
    stream = Code("WAKINGMOON", expires_at="2026-10-23T02:30:00Z")
    state, _ = update_state({"games": {}}, [feed("threads", stream), ok("site", "WUTHERINGGIFT")], T1)
    # The post scrolled out of the feed: the code is still good.
    state, _ = update_state(state, [feed("threads"), ok("site", "WUTHERINGGIFT")], T2)
    assert codes(state)["WAKINGMOON"]["removed_at"] is None
    assert codes(state)["WAKINGMOON"]["sources"] == ["threads"]
    state, _ = update_state(state, [feed("threads"), ok("site", "WUTHERINGGIFT")], T3)
    assert codes(state)["WAKINGMOON"]["removed_at"] == T3


def test_feed_drops_codes_without_a_deadline_like_any_source():
    state, _ = update_state({"games": {}}, [feed("threads", Code("AAA"))], T1)
    state, _ = update_state(state, [feed("threads")], T2)
    assert codes(state)["AAA"]["removed_at"] == T2
