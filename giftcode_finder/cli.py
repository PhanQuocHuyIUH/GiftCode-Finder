"""Command line entry point: ``python -m giftcode_finder <command>``."""

from __future__ import annotations

import argparse
import os
import sys
import traceback

from .config import ConfigError, Game, load_config
from .extractors import extract
from .fetch import Fetcher
from .inspect import inspect_url
from .publish import build_site, codes_markdown, site_data, update_readme, write_step_summary
from .state import SourceResult, load_state, now_iso, save_state, update_state

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
    run.set_defaults(func=cmd_run)

    ins = sub.add_parser("inspect", help="phân tích cấu trúc trang để cấu hình nguồn mới")
    ins.add_argument("urls", nargs="*", metavar="URL", help="mặc định: mọi nguồn trong config")
    ins.add_argument("--config", default="config/sources.yaml")
    ins.add_argument("--render", action="store_true", help="tải bằng trình duyệt headless (trang dùng JavaScript)")
    ins.add_argument("--scan-js", action="store_true", help="tìm URL API trong các file JS của trang")
    ins.add_argument("--grep", action="append", default=[], metavar="CHỮ", help="in đoạn JS quanh chữ này (lặp lại được)")
    ins.add_argument("--grep-width", type=int, default=300, metavar="N", help="số ký tự in quanh mỗi chỗ --grep tìm thấy")
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


def scrape(games: list[tuple[Game, list]], fetcher: Fetcher, debug: bool = False) -> list[SourceResult]:
    results = []
    for game, sources in games:
        for source in sources:
            result = SourceResult(game.id, source.id, checked_at=now_iso())
            try:
                result.codes = extract(source, fetcher)
            except Exception as exc:  # one broken site must not stop the others
                result.error = str(exc) or type(exc).__name__
                if debug:
                    traceback.print_exc()
            _report(game, source, result)
            results.append(result)
    return results


def _report(game: Game, source, result: SourceResult) -> None:
    label = f"{game.id}/{source.id}"
    if result.ok:
        print(f"✓ {label}: {len(result.codes)} code - {', '.join(c.code for c in result.codes)}")
    else:
        print(f"✗ {label}: {result.error}")
        if IN_CI:
            print(f"::warning title=Lỗi nguồn {label}::{result.error}")


def cmd_run(args: argparse.Namespace) -> int:
    games = load_config(args.config)
    results = scrape(_selected(games, args.only), Fetcher(), debug=args.debug)
    failed = [r for r in results if not r.ok]

    if not args.dry_run:
        now = now_iso()
        state, new_by_game = update_state(load_state(args.state), results, now)
        save_state(args.state, state)
        data = site_data(games, state, results, now)
        build_site(data, args.site_template, args.site_dir)
        update_readme(args.readme, codes_markdown(data))
        write_step_summary(data, new_by_game)
        new_count = sum(len(v) for v in new_by_game.values())
        print(f"{new_count} code mới; trang web đã tạo ở {args.site_dir}/")
        if out := os.environ.get("GITHUB_OUTPUT"):
            with open(out, "a", encoding="utf-8") as fh:
                fh.write(f"new_codes={new_count}\nfailed_sources={len(failed)}\n")

    return 1 if args.strict and failed else 0


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
                click=args.click,
                dump_text=args.text,
                dump_html=args.html,
                fetcher=fetcher,
            )
        except Exception as exc:  # report and move on to the next URL
            print(f"Lỗi: {exc}")
            status = 1
    return status
