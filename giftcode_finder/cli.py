"""Command line entry point: ``python -m giftcode_finder <command>``."""

from __future__ import annotations

import argparse
import os
import sys
import traceback

from .config import ConfigError, Game, load_config
from .extractors import FEEDS, extract
from .fetch import Fetcher
from .inspect import inspect_url
from .publish import build_site, codes_markdown, site_data, update_readme, write_step_summary
from .state import SourceResult, attach_events, load_state, now_iso, save_state, split_hidden, update_state
from .tft import TftResult, load_history, load_tft_config, save_history, update_history

IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to a legacy code page that cannot print Vietnamese.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"Lỗi cấu hình: {exc}", file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m giftcode_finder",
        description="Lấy giftcode game từ các trang web đã cấu hình.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="quét mọi nguồn, cập nhật dữ liệu, README và trang web")
    run.add_argument("--config", default="config/sources.yaml")
    run.add_argument("--state", default="data/codes.json")
    run.add_argument("--site-template", default="site")
    run.add_argument("--site-dir", default="_site")
    run.add_argument("--readme", default="README.md")
    run.add_argument("--only", action="append", metavar="GAME[/NGUON]", help="chỉ quét game/nguồn này")
    run.add_argument("--dry-run", action="store_true", help="chỉ in code ra màn hình, không ghi file")
    run.add_argument("--strict", action="store_true", help="trả mã lỗi nếu có nguồn bị lỗi")
    run.add_argument("--debug", action="store_true", help="in traceback khi nguồn bị lỗi")
    run.add_argument("--tft-config", default="config/tft.yaml")
    run.add_argument("--tft-data", default="data/tft.json")
    run.add_argument("--tft-db", default="data/tft_db", help="thư mục bảng thông số TFT theo mùa")
    run.add_argument("--no-tft", action="store_true", help="bỏ qua phần cập nhật TFT")
    run.set_defaults(func=cmd_run)

    tft = sub.add_parser("tft", help="đọc patch notes Teamfight Tactics (không ghi file)")
    tft.add_argument("--config", default="config/tft.yaml")
    tft.add_argument("--data", default="data/tft.json")
    tft.add_argument("--save", action="store_true", help="ghi kết quả vào --data")
    tft.add_argument("--show", type=int, default=0, metavar="N", help="in N thay đổi đầu của mỗi mục")
    tft.add_argument("--outline", metavar="URL", help="in dàn ý (tiêu đề, danh sách) của một bài patch notes")
    tft.add_argument("--describe-db", type=int, metavar="MÙA", help="in cấu trúc dữ liệu game (Community Dragon) của mùa này")
    tft.set_defaults(func=cmd_tft)

    ins = sub.add_parser("inspect", help="phân tích cấu trúc trang để cấu hình nguồn mới")
    ins.add_argument("urls", nargs="*", metavar="URL", help="mặc định: mọi nguồn trong config")
    ins.add_argument("--config", default="config/sources.yaml")
    ins.add_argument("--render", action="store_true", help="tải bằng trình duyệt headless (trang dùng JavaScript)")
    ins.add_argument("--scan-js", action="store_true", help="tìm URL API trong các file JS của trang")
    ins.add_argument("--grep", action="append", default=[], metavar="CHỮ", help="in đoạn JS quanh chữ này (lặp lại được)")
    ins.add_argument("--grep-width", type=int, default=300, metavar="N", help="số ký tự in quanh mỗi chỗ --grep tìm thấy")
    ins.add_argument("--grep-limit", type=int, default=8, metavar="N", help="số chỗ tối đa in cho mỗi --grep")
    ins.add_argument("--click", metavar="SELECTOR", help="bấm phần tử này sau khi tải (vd: 'text=Nhận'), ngụ ý --render")
    ins.add_argument("--text", type=int, default=0, metavar="N", help="in N dòng chữ hiển thị")
    ins.add_argument("--html", type=int, default=0, metavar="N", help="in N dòng HTML của <body>")
    ins.set_defaults(func=cmd_inspect)
    return parser


def _selected(games: list[Game], only: list[str] | None) -> list[tuple[Game, list]]:
    picked = []
    for game in games:
        sources = [
            s for s in game.sources if not only or game.id in only or f"{game.id}/{s.id}" in only
        ]
        if sources:
            picked.append((game, sources))
    if only and not picked:
        raise ConfigError(f"Không có game/nguồn nào khớp {', '.join(only)}")
    return picked


def scrape(
    games: list[tuple[Game, list]], fetcher: Fetcher, state: dict, debug: bool = False
) -> list[SourceResult]:
    results = []
    for game, sources in games:
        game_results = []
        for source in sources:
            result = SourceResult(game.id, source.id, checked_at=now_iso(), feed=source.type in FEEDS)
            try:
                split_hidden(result, extract(source, fetcher), state)
            except Exception as exc:  # one broken site must not stop the others
                result.error = str(exc) or type(exc).__name__
                if debug:
                    traceback.print_exc()
            game_results.append(result)
        attach_events(game_results, state, game.name)
        for source, result in zip(sources, game_results):
            _report(game, source, result)
        results += game_results
    return results


def _report(game: Game, source, result: SourceResult) -> None:
    label = f"{game.id}/{source.id}"
    if result.ok:
        listed = f" - {', '.join(c.code for c in result.codes)}" if result.codes else ""
        print(f"✓ {label}: {len(result.codes)} code{listed}")
        if result.hidden:
            titles = ", ".join(c.title or c.link for c in result.hidden)
            print(f"  {len(result.hidden)} sự kiện cần đăng nhập mới xem được mã: {titles}")
    else:
        print(f"✗ {label}: {result.error}")
        if IN_CI:
            print(f"::warning title=Lỗi nguồn {label}::{result.error}")


def cmd_run(args: argparse.Namespace) -> int:
    games = load_config(args.config)
    state = load_state(args.state)
    results = scrape(_selected(games, args.only), Fetcher(), state, debug=args.debug)
    failed = [r for r in results if not r.ok]

    tft = None if args.dry_run or args.no_tft else run_tft(args.tft_config, args.tft_data, Fetcher(), args.tft_db)

    if not args.dry_run:
        now = now_iso()
        state, new_by_game = update_state(state, results, now)
        save_state(args.state, state)
        data = site_data(games, state, results, now)
        tft_data = None if args.no_tft else tft_site_data(tft, args.tft_data)
        build_site(data, args.site_template, args.site_dir, tft=tft_data, tft_db_dir=None if args.no_tft else args.tft_db)
        update_readme(args.readme, codes_markdown(data))
        write_step_summary(data, new_by_game)
        new = [e for entries in new_by_game.values() for e in entries]
        new_codes = sum(1 for e in new if e["code"])
        new_events = len(new) - new_codes
        print(f"{new_codes} code mới, {new_events} sự kiện mới cần đăng nhập; trang web ở {args.site_dir}/")
        if out := os.environ.get("GITHUB_OUTPUT"):
            with open(out, "a", encoding="utf-8") as fh:
                fh.write(f"new_codes={new_codes}\nnew_events={new_events}\nfailed_sources={len(failed)}\n")
                fh.write(f"new_patches={len(tft.new_versions) if tft else 0}\n")

    return 1 if args.strict and failed else 0


def run_tft(config_path: str, data_path: str, fetcher: Fetcher, db_dir: str | None = None) -> TftResult | None:
    """Update ``data_path`` with new TFT patch notes; never fails the run."""
    try:
        config = load_tft_config(config_path)
    except ConfigError as exc:
        print(f"✗ tft: {exc}")
        return None
    if config is None:
        return None
    print("TFT: đọc patch notes")
    history = load_history(data_path)
    try:
        result = update_history(config, history, fetcher, db_dir=db_dir)
    except Exception as exc:  # the giftcodes must still be published
        traceback.print_exc()
        return TftResult(history=history, errors=[str(exc)], checked_at=now_iso())
    save_history(data_path, result.history)
    patches = result.history.get("patches", [])
    print(f"{'✓' if not result.errors else '✗'} tft: {len(patches)} phiên bản, mới: {', '.join(result.new_versions) or 'không'}")
    for error in result.errors:
        print(f"  lỗi: {error}")
        if IN_CI:
            print(f"::warning title=Lỗi đọc patch notes TFT::{error}")
    return result


def tft_site_data(result: TftResult | None, data_path: str) -> dict | None:
    history = result.history if result is not None else load_history(data_path)
    if not history.get("patches") and result is None:
        return None
    return {
        **history,
        "checked_at": result.checked_at if result else None,
        "errors": result.errors if result else [],
    }


def print_outline(html: str) -> None:
    """Headings of a patch notes article, each with its first list items."""
    from bs4 import BeautifulSoup

    from .tft import _container

    root = _container(BeautifulSoup(html, "html.parser"))
    for node in root.find_all(["h1", "h2", "h3", "h4", "h5", "p", "ul", "blockquote", "table"]):
        if node.name == "p" and not (node.find(["strong", "b"]) and len(node.get_text(strip=True)) < 60):
            continue
        if node.name == "ul" and node.find_parent("ul"):
            continue
        text = " ".join(node.get_text(" ", strip=True).split())[:100]
        attrs = " ".join(f"{k}={v if isinstance(v, str) else ' '.join(v)}" for k, v in node.attrs.items())[:60]
        if node.name == "ul":
            items = node.find_all("li", recursive=False)
            nested = sum(1 for li in items if li.find(["ul", "ol"]))
            first = [str(li)[:160] for li in items[:2]]
            print(f"      ul: {len(items)} li ({nested} lồng) {first}")
        else:
            print(f"  <{node.name} {attrs}> {text}")


def cmd_tft(args: argparse.Namespace) -> int:
    config = load_tft_config(args.config)
    if config is None:
        print(f"Không có {args.config}")
        return 2
    if args.outline:
        print_outline(Fetcher().fetch(args.outline).text)
        return 0
    if args.describe_db:
        import json

        from .tft_db import build_db, describe

        url = config.names_url.replace("{locale}", config.db_locale)
        raw = json.loads(Fetcher().fetch(url).text)
        print(describe(raw, args.describe_db))
        db = build_db(raw, args.describe_db, config.asset_base)
        if db:
            for key in ("champions", "traits", "items", "augments"):
                print(f"\n## {key}: {len(db[key])}")
                for entry in db[key][:3]:
                    print("  ", json.dumps(entry, ensure_ascii=False)[:900])
        return 0
    history = load_history(args.data)
    result = update_history(config, history, Fetcher())
    for patch in result.history.get("patches", [])[:3]:
        print(f"\n== {patch['version']} {patch['title']} ({patch['published_at']}) {patch['counts']}")
        for section in patch["sections"]:
            print(f"  [{section['kind']}] {section['title']} — {len(section['changes'])} thay đổi")
            for change in section["changes"][: args.show]:
                who = change["subject"] or "·"
                print(f"     {change['dir']:7} {who} | {change['stat']} | {change['before']} -> {change['after']} || {(change.get('text') or '')[:110]}")
    if args.save:
        save_history(args.data, result.history)
    for error in result.errors:
        print(f"lỗi: {error}")
    return 1 if result.errors and not result.history.get("patches") else 0


def cmd_inspect(args: argparse.Namespace) -> int:
    urls = args.urls or [s.url for g in load_config(args.config) for s in g.sources]
    fetcher = Fetcher()
    status = 0
    for url in urls:
        print(f"\n##### {url}")
        try:
            inspect_url(
                url,
                render=args.render,
                scan_js=args.scan_js,
                grep=args.grep,
                grep_width=args.grep_width,
                grep_limit=args.grep_limit,
                click=args.click,
                dump_text=args.text,
                dump_html=args.html,
                fetcher=fetcher,
            )
        except Exception as exc:  # report and move on to the next URL
            print(f"Lỗi: {exc}")
            status = 1
    return status
