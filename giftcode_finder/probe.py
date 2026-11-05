"""Temporary: outline of reward pages the table reader does not understand yet."""
import re
import sys

from bs4 import BeautifulSoup, Tag

from .fetch import Fetcher


def outline(node, depth=0, out=None):
    out = out if out is not None else []
    if len(out) > 140 or depth > 14:
        return out
    for child in node.children:
        if isinstance(child, Tag):
            if child.name in ("style", "svg", "script"):
                continue
            own = " ".join(t.strip() for t in child.find_all(string=True, recursive=False) if t.strip())[:60]
            attrs = {k: v for k, v in child.attrs.items() if k.startswith("data-") or k in ("aria-label",)}
            cls = [c for c in child.get("class", []) if not c.startswith(("css-", "e"))]
            out.append("  " * depth + f"<{child.name} {cls or ''} {attrs or ''}> {own}")
            outline(child, depth + 1, out)
    return out


for url in sys.argv[1:]:
    html = Fetcher().fetch(url).text
    box = BeautifulSoup(html, "html.parser").select_one(".RewardContainer")
    print("#####", url, "box" if box else "NO BOX")
    if box:
        print("\n".join(outline(box)[:140]))
