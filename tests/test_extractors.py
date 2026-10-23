import pytest

from giftcode_finder.config import Source
from giftcode_finder.extractors import ExtractError, extract
from giftcode_finder.fetch import Page


class FakeFetcher:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def fetch(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Page(url, 200, "text/html", self.text)

    def render(self, url, **kwargs):
        self.calls.append((url, {"render": True, **kwargs}))
        return Page(url, 200, "text/html", self.text)


def source(kind, **options):
    return Source(id="s", name="S", type=kind, url="https://example.test/codes", options=options)


HTML = """
<ul class="list">
  <li class="item"><b class="code">ABC123</b><i class="gift">100 Vàng</i><em>31/12/2026</em></li>
  <li class="item"><b class="code"> P.U.S </b><i class="gift">Thẻ đổi tên</i></li>
  <li class="item"><b class="code">ABC123</b></li>
  <li class="item"><b class="code">Hết hạn rồi</b></li>
</ul>
<button data-clipboard-text="COPYME">Sao chép</button>
"""


def test_html_item_selectors():
    codes = extract(
        source("html", item="li.item", code=".code", reward=".gift", expires="em"),
        FakeFetcher(HTML),
    )
    assert [(c.code, c.reward, c.expires) for c in codes] == [
        ("ABC123", "100 Vàng", "31/12/2026"),
        ("P.U.S", "Thẻ đổi tên", None),
    ]


def test_html_attribute():
    codes = extract(source("html", code="[data-clipboard-text]", attr="data-clipboard-text"), FakeFetcher(HTML))
    assert [c.code for c in codes] == ["COPYME"]


def test_regex_named_groups():
    text = "<p>Code: WELCOME2026 - quà: 50 KC</p><p>Code: VIPPRO - quà: Skin</p>"
    codes = extract(
        source("regex", pattern=r"Code:\s*(?P<code>\S+)\s*-\s*quà:\s*(?P<reward>[^\n<]+)"),
        FakeFetcher(text),
    )
    assert [(c.code, c.reward) for c in codes] == [("WELCOME2026", "50 KC"), ("VIPPRO", "Skin")]


def test_json_items_path_and_fields():
    body = '{"data": {"list": [{"gift_code": "AAA111", "desc": "Quà 1", "end": "2026-12-01"}, {"gift_code": "BBB222"}]}}'
    codes = extract(
        source("json", items="data.list", code="gift_code", reward="desc", expires="end"),
        FakeFetcher(body),
    )
    assert [(c.code, c.reward, c.expires) for c in codes] == [
        ("AAA111", "Quà 1", "2026-12-01"),
        ("BBB222", None, None),
    ]


def test_json_auto_finds_nested_codes():
    body = '{"a": [{"code": "ONE111"}, {"x": {"code": "TWO222"}}], "b": {"code": "THREE3"}}'
    assert [c.code for c in extract(source("json"), FakeFetcher(body))] == ["ONE111", "TWO222", "THREE3"]


def test_json_from_script_tag():
    page = '<script id="__NEXT_DATA__" type="application/json">{"props": {"codes": [{"code": "NEXT01"}]}}</script>'
    codes = extract(source("json", script="#__NEXT_DATA__", items="props.codes"), FakeFetcher(page))
    assert [c.code for c in codes] == ["NEXT01"]


def test_exclude_and_pattern():
    codes = extract(
        source("html", code=".code", exclude=["abc123"], code_pattern=r"[A-Z.]+"),
        FakeFetcher(HTML),
    )
    assert [c.code for c in codes] == ["P.U.S"]


def test_render_option_uses_browser():
    fetcher = FakeFetcher(HTML)
    extract(source("html", code=".code", render=True, wait_for=".list"), fetcher)
    assert fetcher.calls[0][1]["render"] is True
    assert fetcher.calls[0][1]["wait_for"] == ".list"


def test_empty_result_is_an_error_unless_allowed():
    with pytest.raises(ExtractError):
        extract(source("html", code=".missing"), FakeFetcher(HTML))
    assert extract(source("html", code=".missing", allow_empty=True), FakeFetcher(HTML)) == []
