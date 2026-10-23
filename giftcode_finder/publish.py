"""Outputs: the static web page, the README code table and the CI summary."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Game
from .state import SourceResult

VN_TZ = timezone(timedelta(hours=7))
README_START = "<!-- GIFTCODES:START -->"
README_END = "<!-- GIFTCODES:END -->"
DATA_PLACEHOLDER = "__GCF_DATA__"


def site_data(games: list[Game], state: dict, results: list[SourceResult], generated_at: str) -> dict:
    status = {(r.game_id, r.source_id): r for r in results}
    repo = os.environ.get("GITHUB_REPOSITORY")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    workflow = os.environ.get("GCF_WORKFLOW_FILE", "scrape.yml")
    out_games = []
    for game in games:
        sources, hidden = [], []
        for source in game.sources:
            result = status.get((game.id, source.id))
            sources.append(
                {
                    "id": source.id,
                    "name": source.name,
                    "url": source.url,
                    "ok": result.ok if result else None,
                    "count": len(result.codes) if result and result.ok else None,
                    "hidden": len(result.hidden) if result else 0,
                    "error": result.error if result else None,
                    "checked_at": result.checked_at if result else None,
                }
            )
            for item in result.hidden if result else []:
                hidden.append(
                    {
                        "title": item.title,
                        "reward": item.reward,
                        "expires": item.expires,
                        "link": item.link,
                        "source": source.id,
                    }
                )
        out_games.append(
            {
                "id": game.id,
                "name": game.name,
                "redeem_url": game.redeem_url,
                "redeem_note": game.redeem_note,
                "sources": sources,
                "codes": state["games"].get(game.id, []),
                "hidden": hidden,
            }
        )
    return {
        "generated_at": generated_at,
        "updated_at": state.get("updated_at"),
        "repo_url": f"{server}/{repo}" if repo else None,
        "workflow_url": f"{server}/{repo}/actions/workflows/{workflow}" if repo else None,
        "games": out_games,
    }


def build_site(data: dict, template_dir: str | Path, out_dir: str | Path) -> Path:
    template_dir, out_dir = Path(template_dir), Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(template_dir, out_dir)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    (out_dir / "codes.json").write_text(payload + "\n", encoding="utf-8")
    index = out_dir / "index.html"
    # "</" would let the data close the <script> tag it is embedded in.
    embedded = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    index.write_text(index.read_text(encoding="utf-8").replace(DATA_PLACEHOLDER, embedded), encoding="utf-8")
    return out_dir


def vn_time(iso: str | None, with_time: bool = True) -> str:
    if not iso:
        return "—"
    moment = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(VN_TZ)
    return moment.strftime("%d/%m/%Y %H:%M" if with_time else "%d/%m/%Y")


def _cell(value: str | None) -> str:
    return (value or "—").replace("|", "\\|").replace("\n", " ")


def codes_markdown(data: dict, new_by_game: dict[str, list[dict]] | None = None) -> str:
    new_by_game = new_by_game or {}
    lines = []
    for game in data["games"]:
        active = [c for c in game["codes"] if not c["removed_at"]]
        new_codes = {c["code"] for c in new_by_game.get(game["id"], [])}
        lines.append(f"### {game['name']} — {len(active)} code")
        lines.append("")
        if active:
            lines.append("| Code | Sự kiện | Hạn dùng | Thấy lần đầu |")
            lines.append("|---|---|---|---|")
            for c in active:
                badge = " 🆕" if c["code"] in new_codes else ""
                event = " — ".join(x for x in (c.get("title"), c.get("reward")) if x and x != c["code"])
                if c.get("link"):
                    event = f"[{_cell(event or 'Xem')}]({c['link']})"
                lines.append(
                    f"| `{c['code']}`{badge} | {_cell(event)} | {_cell(c['expires'])} "
                    f"| {vn_time(c['first_seen'], with_time=False)} |"
                )
            lines += ["", "Sao chép tất cả:", "", "```text", *[c["code"] for c in active], "```"]
        else:
            lines.append("_Chưa có code nào đang hoạt động._")
        lines.append("")
        if game.get("hidden"):
            count = len(game["hidden"])
            lines += [f"<details><summary>{count} sự kiện cần đăng nhập để xem mã (bấm để nhận)</summary>", ""]
            for h in game["hidden"]:
                expires = f" — hạn {h['expires']}" if h.get("expires") else ""
                lines.append(f"- [{_cell(h['title'] or h['link'])}]({h['link']}){expires}")
            lines += ["", "</details>", ""]
        source_links = ", ".join(f"[{s['name']}]({s['url']})" for s in game["sources"])
        lines.append(f"Nguồn: {source_links}")
        if game.get("redeem_note") or game.get("redeem_url"):
            note = game.get("redeem_note") or "Trang nhập code"
            lines.append(f"Cách nhập: {note}" + (f" — {game['redeem_url']}" if game.get("redeem_url") else ""))
        lines.append("")
    lines.append(f"_Code thay đổi lần cuối: {vn_time(data.get('updated_at'))} (giờ Việt Nam)._")
    return "\n".join(lines).rstrip() + "\n"


def update_readme(path: str | Path, markdown: str) -> bool:
    path = Path(path)
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    start, end = text.find(README_START), text.find(README_END)
    if start == -1 or end < start:
        return False
    updated = text[: start + len(README_START)] + "\n" + markdown + text[end:]
    if updated == text:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def status_markdown(data: dict) -> str:
    lines = ["| Game | Nguồn | Trạng thái |", "|---|---|---|"]
    for game in data["games"]:
        for s in game["sources"]:
            if s["ok"]:
                state = f"✅ {s['count']} code" + (f", {s['hidden']} sự kiện ẩn mã" if s["hidden"] else "")
            else:
                state = f"❌ {_cell(s['error'])}"
            lines.append(f"| {game['name']} | [{s['name']}]({s['url']}) | {state} |")
    return "\n".join(lines) + "\n"


def write_step_summary(data: dict, new_by_game: dict[str, list[dict]]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    total_new = sum(len(v) for v in new_by_game.values())
    head = f"## 🎁 Giftcode — {total_new} code mới\n\n" if total_new else "## 🎁 Giftcode\n\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(head + status_markdown(data) + "\n" + codes_markdown(data, new_by_game))
