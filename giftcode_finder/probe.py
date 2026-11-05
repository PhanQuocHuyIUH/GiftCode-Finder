"""Temporary: print how a reward-table page is built (for writing its reader)."""

from __future__ import annotations

import json
import re
import sys

from bs4 import BeautifulSoup

from .fetch import Fetcher


def keys_of(value, path="", depth=0, out=None):
    out = out if out is not None else []
    if depth > 7 or len(out) > 120:
        return out
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(v, (dict, list)):
                out.append(f"{path}.{k} ({type(v).__name__}{len(v)})")
                keys_of(v, f"{path}.{k}", depth + 1, out)
    elif isinstance(value, list) and value:
        keys_of(value[0], f"{path}[0]", depth + 1, out)
    return out


def main(urls):
    fetcher = Fetcher()
    for url in urls:
        print(f"\n##### {url}")
        try:
            page = fetcher.fetch(url)
        except Exception as exc:
            print("ERR", exc)
            continue
        html = page.text
        soup = BeautifulSoup(html, "html.parser")
        print("len", len(html), "title", soup.title.string if soup.title else None)
        nd = soup.find("script", id="__NEXT_DATA__")
        if nd and nd.string:
            data = json.loads(nd.string)
            pp = data.get("props", {}).get("pageProps", {})
            print("pageProps keys:", list(pp))
            for line in keys_of(pp)[:60]:
                print("  ", line)
            print("pageProps json:", json.dumps(pp, ensure_ascii=False)[:5000])
            text = json.dumps(data, ensure_ascii=False)
            for m in list(re.finditer(r"(probab|chance|rate|percent|weight)", text, re.I))[:5]:
                print("  ctx:", text[max(0, m.start() - 300): m.start() + 300])
        pushes = re.findall(r"self\.__next_f\.push\(\[1,\"(.*?)\"\]\)", html, re.S)
        print("next_f pushes", len(pushes), sum(len(p) for p in pushes))
        joined = "".join(pushes)
        for m in list(re.finditer(r"(probab|chance|percent|weight|%)", joined, re.I))[:6]:
            print("  rsc ctx:", joined[max(0, m.start() - 250): m.start() + 250])
        links = sorted({a["href"] for a in soup.find_all("a", href=True) if "/rewards/" in a["href"] or "/tables/" in a["href"]})
        print("links", len(links), links[:80])
        body = soup.get_text(" ", strip=True)
        print("text:", body[1200:2600])
        imgs = [i.get("src") for i in soup.find_all("img")][:15]
        print("imgs:", imgs)


if __name__ == "__main__":
    main(sys.argv[1:])
