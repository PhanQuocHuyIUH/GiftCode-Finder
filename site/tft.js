"use strict";

// Teamfight Tactics patch notes: pick a season, spin through its patches and
// see every buff, nerf and change, by champion, trait, item, augment...
// The data (tft.json) is large, so it loads only when this page opens.
// Uses el(), ago(), setTheme(), toast() from app.js (loaded after this file,
// but only called once the page runs).
const TFT = (() => {
  const GOLD = "#ffc94d";
  const KINDS = {
    all: ["Tất cả", "✨"],
    champions: ["Tướng", "🦸"],
    traits: ["Tộc/Hệ", "🧬"],
    items: ["Trang bị", "🗡️"],
    augments: ["Nâng cấp", "💠"],
    mechanics: ["Cơ chế", "⚙️"],
    modes: ["Chế độ chơi", "🎮"],
    fixes: ["Sửa lỗi", "🔧"],
    other: ["Khác", "✳️"],
  };
  const DIRS = {
    buff: ["Tăng sức mạnh", "▲", "Tăng"],
    nerf: ["Giảm sức mạnh", "▼", "Giảm"],
    adjust: ["Điều chỉnh", "◆", "Điều chỉnh"],
    new: ["Mới", "✦", "Mới"],
    removed: ["Gỡ bỏ", "✕", "Gỡ bỏ"],
    fix: ["Sửa lỗi", "✔", "Sửa lỗi"],
    mixed: ["Vừa tăng vừa giảm", "◆", "Tăng & giảm"],
  };
  const NAMED = new Set(["champions", "traits", "items", "augments"]);
  const dateFmt = new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
  const shortDate = new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit" });

  let data = null;
  let loading = null;
  const state = { kind: "all", dir: "all", query: "", wide: false, hotfix: "all", patch: null };

  // Diacritics off, so "ahri" finds "Ahri" and "giap" finds "Giáp".
  const fold = (text) =>
    String(text || "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/đ/g, "d")
      .replace(/Đ/g, "D")
      .toLowerCase();

  function load(summary) {
    if (data) return Promise.resolve(data);
    if (!loading) {
      const v = encodeURIComponent((summary && summary.version) || "");
      loading = fetch(`tft.json?v=${v}`)
        .then((response) => {
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return response.json();
        })
        .then((json) => {
          data = json;
          return json;
        })
        .catch((error) => {
          loading = null;
          throw error;
        });
    }
    return loading;
  }

  // --- Small pieces -------------------------------------------------------

  function hexPrism(label, size = "") {
    return el(
      "div",
      { class: `hexstage ${size}`, "aria-hidden": "true" },
      el(
        "div",
        { class: "hexprism" },
        [0, 1, 2, 3, 4, 5].map((k) => el("i", { style: `--k:${k}` }, k % 2 ? "TFT" : label)),
        el("span", { class: "cap top" }),
      ),
    );
  }

  function dpill(dir, count) {
    const [label, icon, short] = DIRS[dir];
    return el("span", { class: "dpill", "data-dir": dir, title: label }, icon, " ", count !== undefined ? [el("b", {}, count), " ", short.toLowerCase()] : short);
  }

  function when(iso) {
    return iso ? `${dateFmt.format(new Date(iso))} (${ago(iso)})` : "";
  }

  function setLabel(patch) {
    return `Mùa ${patch.set}${patch.set_name ? ` — ${patch.set_name}` : ""}`;
  }

  function cssUrl(url) {
    return url ? `url("${String(url).replace(/["\\\n]/g, "")}")` : "none";
  }

  function avatar(name, icon, kind) {
    const fallback = () => el("span", { class: "av", "aria-hidden": "true" }, name ? initialsOf(name) : KINDS[kind] ? KINDS[kind][1] : "•");
    if (!icon) return fallback();
    const img = el("img", { class: "av", src: icon, alt: "", loading: "lazy", decoding: "async", referrerpolicy: "no-referrer" });
    img.addEventListener("error", () => img.replaceWith(fallback()), { once: true });
    return img;
  }

  function initialsOf(name) {
    const words = String(name).replace(/\(.*?\)/g, "").split(/\s+/).filter(Boolean);
    return (words.length > 1 ? words[0][0] + words[1][0] : (words[0] || "?").slice(0, 2)).toUpperCase();
  }

  function changesOf(patch) {
    return patch.sections.flatMap((section) => section.changes.map((change) => ({ ...change, section: section.title, version: patch.version })));
  }

  const hotfixesOf = (patch) => patch.hotfixes || [];
  const latestHotfix = (patch) => hotfixesOf(patch).slice(-1)[0] || null;
  const dayMonth = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : "");

  function haystack(change) {
    return fold([change.subject, change.stat, change.before, change.after, change.text, change.group, change.section].join(" "));
  }

  function matches(change, query) {
    if (state.hotfix === "base" && change.hotfix) return false;
    if (state.hotfix !== "all" && state.hotfix !== "base" && change.hotfix !== state.hotfix) return false;
    if (state.kind !== "all" && change.kind !== state.kind) return false;
    if (state.dir !== "all" && change.dir !== state.dir) return false;
    return !query || haystack(change).includes(query);
  }

  // --- Cards --------------------------------------------------------------

  // Numbers of a value as the patch notes write them: "1.000" and "1,000" are
  // thousands, "0,5" a half; per-star values "200/300/450" give three.
  function numbers(text) {
    return (String(text || "").match(/-?\d+(?:[.,]\d+)*/g) || []).map((raw) =>
      /^-?\d{1,3}(?:[.,]\d{3})+$/.test(raw) ? Number(raw.replace(/[.,]/g, "")) : Number(raw.replace(",", ".")),
    );
  }

  // How much a value moved, in percent of the old value (averaged over stars).
  function delta(change) {
    const a = numbers(change.before);
    const b = numbers(change.after);
    if (!a.length || a.length !== b.length) return null;
    const pairs = a.map((x, i) => [x, b[i]]).filter(([x, y]) => x !== y && x !== 0);
    if (!pairs.length) return null;
    return (pairs.reduce((sum, [x, y]) => sum + (y - x) / Math.abs(x), 0) / pairs.length) * 100;
  }

  function line(change) {
    const [label, icon] = DIRS[change.dir] || DIRS.adjust;
    const parts = [el("i", { title: label }, icon)];
    const move = change.before && change.after ? delta(change) : null;
    const big = move !== null && Math.abs(move) >= 25 && (change.dir === "buff" || change.dir === "nerf");
    if (change.before && change.after) {
      parts.push(
        el(
          "span",
          { class: "ln-stat" },
          change.stat || "Thay đổi",
          big && el("em", { class: "big-tag", title: "Thay đổi lớn (từ 25% trở lên)" }, "🔥 lớn"),
          change.hotfix && el("em", { class: "hf-tag", title: `Thêm trong bản vá ${change.version || ""}${change.hotfix}` }, `⚡ ${change.version || ""}${change.hotfix}`),
        ),
        el(
          "span",
          { class: `ln-vals${change.before.length + change.after.length > 34 ? " long" : ""}` },
          el("s", {}, change.before),
          el("span", { class: "arr", "aria-label": "thành" }, "→"),
          el("b", {}, change.after),
          move !== null && el("span", { class: "delta", title: "Mức thay đổi so với giá trị cũ" }, `${move > 0 ? "+" : "−"}${Math.abs(move) < 10 ? Math.abs(move).toFixed(1).replace(".", ",") : Math.round(Math.abs(move))}%`),
        ),
      );
    } else {
      parts.push(
        el(
          "span",
          { class: "ln-text" },
          change.hotfix && el("em", { class: "hf-tag" }, `⚡ ${change.version || ""}${change.hotfix}`),
          change.text || change.stat || "",
        ),
      );
    }
    return el("li", { class: `ln${big ? " is-big" : ""}${change.hotfix ? " is-hotfix" : ""}`, "data-dir": change.dir }, parts);
  }

  function overall(changes) {
    const dirs = new Set(changes.map((c) => c.dir));
    if (dirs.size === 1) return [...dirs][0];
    if (dirs.has("buff") && dirs.has("nerf")) return "mixed";
    if (dirs.has("buff")) return "buff";
    if (dirs.has("nerf")) return "nerf";
    return [...dirs].find((d) => d !== "adjust") || "adjust";
  }

  function card(subject, changes, icons, index, title) {
    const first = changes[0];
    const dir = overall(changes);
    const meta = [KINDS[first.kind] && first.kind !== "other" ? KINDS[first.kind][0] : null, first.group, first.date].filter(Boolean);
    return el(
      "article",
      { class: "sc", "data-dir": dir, "data-kind": first.kind, style: `--i:${index}` },
      el(
        "header",
        {
          class: `sc-head${subject && NAMED.has(first.kind) ? " has-sheet" : ""}`,
          "data-sheet": subject && NAMED.has(first.kind) ? subject : null,
          title: subject && NAMED.has(first.kind) ? `Xem thông số ${subject}` : null,
        },
        avatar(subject, subject ? icons[subject] : null, first.kind),
        el("div", { class: "sc-name" }, el("h3", {}, subject || title || "Thay đổi chung"), meta.length > 0 && el("small", {}, meta.join(" · "))),
        dpill(dir),
      ),
      el("ul", { class: "lines" }, changes.map(line)),
    );
  }

  // Consecutive changes about the same thing become one card.
  function cards(changes, icons, title) {
    const groups = [];
    const bySubject = new Map();
    const loose = [];
    for (const change of changes) {
      if (!change.subject) {
        loose.push(change);
        continue;
      }
      const key = `${change.subject}\u0000${change.kind}`;
      if (!bySubject.has(key)) {
        const group = { subject: change.subject, changes: [] };
        bySubject.set(key, group);
        groups.push(group);
      }
      bySubject.get(key).changes.push(change);
    }
    const out = groups.map((g, i) => card(g.subject, g.changes, icons, i));
    if (loose.length) out.push(card(null, loose, icons, out.length, title));
    return el("div", { class: "cards" }, out);
  }

  // The first developer note stays in view; the rest fold away so changes come first.
  function notesBlock(notes) {
    if (notes.length <= 1) return notes.map(note);
    const more = el("details", { class: "more-notes" }, el("summary", {}, `💬 Xem thêm ${notes.length - 1} ghi chú của Riot`), notes.slice(1).map(note));
    return [note(notes[0]), more];
  }

  function note(text) {
    const node = el("p", { class: "note is-clamped", title: "Bấm để đọc hết" }, el("span", {}, text));
    node.addEventListener("click", () => node.classList.remove("is-clamped"), { once: true });
    return node;
  }

  // --- Sections of the page ----------------------------------------------

  function hero(patch, latest) {
    const counts = patch.counts || {};
    const total = (counts.buff || 0) + (counts.nerf || 0) + (counts.adjust || 0) || 1;
    const lightbox =
      patch.highlights &&
      el(
        "dialog",
        { class: "lightbox", "aria-label": `Tiêu điểm bản ${patch.version}` },
        el("img", { src: patch.highlights, alt: `Tiêu điểm cập nhật ${patch.version}`, loading: "lazy" }),
        el(
          "form",
          { method: "dialog" },
          el("a", { href: patch.highlights, target: "_blank", rel: "noopener" }, "Mở ảnh gốc ↗"),
          el("button", { type: "submit" }, "Đóng"),
        ),
      );
    if (lightbox) lightbox.addEventListener("click", (event) => event.target === lightbox && lightbox.close());
    const tiles = Object.keys(DIRS)
      .filter((dir) => dir !== "mixed")
      .map((dir) => {
        const [label, icon, short] = DIRS[dir];
        const number = el("b", {}, counts[dir] || 0);
        FX.countUp(number, counts[dir] || 0);
        return el(
          "button",
          {
            type: "button",
            class: `tile${state.dir === dir ? " is-on" : ""}`,
            "data-dir": dir,
            "data-filter-dir": dir,
            title: `Chỉ xem: ${label}`,
            disabled: !counts[dir],
            "aria-pressed": String(state.dir === dir),
          },
          el("i", { "aria-hidden": "true" }, icon),
          number,
          el("span", {}, short),
        );
      });
    const pct = (n) => `${((100 * (n || 0)) / total).toFixed(1)}%`;
    return el(
      "section",
      { class: "tft-hero" },
      patch.image && el("div", { class: "tft-hero-bg", style: `background-image:${cssUrl(patch.image)}` }),
      el(
        "div",
        { class: "tft-hero-text" },
        el("p", { class: "tft-kicker" }, `⚔️ Đấu Trường Chân Lý · ${setLabel(patch)}`),
        el("h1", { class: "tft-title" }, "Bản cập nhật ", el("span", { class: "ver" }, patch.version), patch.version === latest && el("span", { class: "badge", style: "margin-left:12px;vertical-align:.6em" }, "MỚI NHẤT")),
        el(
          "p",
          { class: "tft-meta" },
          patch.published_at && el("span", {}, `📅 ${when(patch.published_at)}`),
          el("a", { href: patch.url, target: "_blank", rel: "noopener" }, "Đọc bài gốc ↗"),
          summaryRef && summaryRef.checked_at && patch.version === latest && el("span", { class: "live-mini" }, el("i", { class: "live-dot" }), `kiểm tra bài của Riot ${ago(summaryRef.checked_at)}`),
          lightbox && el("button", { type: "button", class: "linkbtn", onclick: () => lightbox.showModal() }, "🖼 Ảnh tiêu điểm"),
        ),
        hotfixLine(patch, latest),
        el("div", { class: "tiles" }, tiles),
        el(
          "div",
          { class: "balance", role: "img", "aria-label": `${counts.buff || 0} tăng, ${counts.adjust || 0} điều chỉnh, ${counts.nerf || 0} giảm` },
          el("i", { class: "b-buff", style: `width:${pct(counts.buff)}` }),
          el("i", { class: "b-adjust", style: `width:${pct(counts.adjust)}` }),
          el("i", { class: "b-nerf", style: `width:${pct(counts.nerf)}` }),
        ),
        el("p", { class: "balance-legend" }, el("span", {}, `▲ ${counts.buff || 0} tăng`), el("span", {}, `${counts.nerf || 0} giảm ▼`)),
      ),
      hexPrism(patch.version),
      lightbox,
    );
  }

  function seasons(patches, current) {
    const sets = [];
    for (const patch of patches) {
      let entry = sets.find((s) => s.set === patch.set);
      if (!entry) sets.push((entry = { set: patch.set, name: patch.set_name, newest: patch.version, count: 0 }));
      entry.count += 1;
    }
    return el(
      "nav",
      { class: "seasons", "aria-label": "Chọn mùa" },
      sets.map((s) =>
        el(
          "a",
          {
            class: `season${s.set === current.set ? " is-on" : ""}`,
            href: `#/tft/${encodeURIComponent(s.newest)}`,
            "aria-current": s.set === current.set ? "true" : null,
          },
          el("b", {}, `Mùa ${s.set}`),
          el("small", {}, `${s.name ? `${s.name} · ` : ""}${s.count} bản`),
        ),
      ),
    );
  }

  function carousel(patches, current, latest) {
    const ordered = patches.filter((p) => p.set === current.set).slice().reverse(); // oldest first
    const bar = (counts) => {
      const total = (counts.buff || 0) + (counts.nerf || 0) + (counts.adjust || 0) || 1;
      return ["buff", "adjust", "nerf"].map((d) => el("i", { class: `b-${d}`, style: `width:${((100 * (counts[d] || 0)) / total).toFixed(1)}%` }));
    };
    const track = el(
      "div",
      { class: "pflow-track", role: "list" },
      ordered.map((patch) =>
        el(
          "a",
          {
            class: `pcard${patch.version === current.version ? " is-on" : ""}`,
            role: "listitem",
            href: `#/tft/${encodeURIComponent(patch.version)}`,
            style: `--img:${cssUrl(patch.image)}`,
            "aria-current": patch.version === current.version ? "true" : null,
            "aria-label": `Bản ${patch.version}`,
          },
          patch.version === latest && el("span", { class: "badge" }, "MỚI"),
          hotfixesOf(patch).length > 0 && el("span", { class: "pcard-hf" }, `⚡ ${latestHotfix(patch).label}`),
          el("span", {}, el("span", { class: "pcard-ver" }, patch.version), el("span", { class: "pcard-date", style: "display:block" }, patch.published_at ? shortDate.format(new Date(patch.published_at)) : "")),
          el(
            "span",
            {},
            el("span", { class: "pcard-bar" }, bar(patch.counts || {})),
            el(
              "span",
              { class: "pcard-nums" },
              el("span", { "data-dir": "buff" }, `▲${(patch.counts || {}).buff || 0}`),
              el("span", { "data-dir": "nerf" }, `▼${(patch.counts || {}).nerf || 0}`),
            ),
          ),
        ),
      ),
    );
    const wrap = el(
      "section",
      { class: "pflow", "aria-label": `Các bản cập nhật mùa ${current.set}` },
      el("button", { type: "button", class: "pflow-nav prev", "aria-label": "Bản trước" }, "‹"),
      track,
      el("button", { type: "button", class: "pflow-nav next", "aria-label": "Bản sau" }, "›"),
    );
    return { wrap, track };
  }

  // Who changed the most this patch, as avatars to click.
  function movers(patch, onPick) {
    const score = new Map();
    for (const change of changesOf(patch)) {
      if (!change.subject || !NAMED.has(change.kind)) continue;
      const entry = score.get(change.subject) || { name: change.subject, kind: change.kind, up: 0, down: 0 };
      if (change.dir === "buff") entry.up += 1;
      if (change.dir === "nerf") entry.down += 1;
      score.set(change.subject, entry);
    }
    const all = [...score.values()];
    const up = all.filter((e) => e.up > e.down).sort((a, b) => b.up - b.down - (a.up - a.down)).slice(0, 10);
    const down = all.filter((e) => e.down > e.up).sort((a, b) => b.down - b.up - (a.down - a.up)).slice(0, 10);
    if (!up.length && !down.length) return null;
    const column = (list, dir, title) =>
      el(
        "div",
        { class: "mover-col", "data-dir": dir },
        el("h3", {}, title),
        list.length
          ? el(
              "div",
              { class: "mover-list" },
              list.map((e) =>
                el(
                  "button",
                  { type: "button", class: "mover", "data-dir": dir, title: `Xem thay đổi của ${e.name}`, onclick: () => onPick(e.name) },
                  avatar(e.name, patch.icons[e.name], e.kind),
                  e.name,
                  el("em", {}, dir === "buff" ? `▲${e.up}` : `▼${e.down}`),
                ),
              ),
            )
          : el("p", { class: "none", style: "margin:0;font-size:.85rem" }, "Không có."),
      );
    return el("section", { class: "movers" }, column(up, "buff", "▲ Được tăng sức mạnh"), column(down, "nerf", "▼ Bị giảm sức mạnh"));
  }

  function tools(patch, repaint) {
    const all = changesOf(patch);
    const kindCount = (kind) => (kind === "all" ? all.length : all.filter((c) => c.kind === kind).length);
    const search = el("input", {
      class: "search",
      type: "search",
      placeholder: "Tìm tướng, tộc hệ, trang bị, nâng cấp… (vd: Ahri)",
      autocomplete: "off",
      "aria-label": "Tìm trong bản cập nhật",
      value: state.query,
    });
    let timer;
    search.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        state.query = search.value.trim();
        repaint();
      }, 140);
    });
    const wide = el("input", { type: "checkbox", checked: state.wide || null });
    wide.addEventListener("change", () => {
      clearTimeout(timer);
      state.query = search.value.trim();
      state.wide = wide.checked;
      repaint();
    });
    const chip = (group, value, label, count, tone) =>
      el(
        "button",
        {
          type: "button",
          class: `chipbtn${state[group] === value ? " is-on" : ""}`,
          style: tone ? `--tone:${tone}` : null,
          "data-group": group,
          "data-value": value,
          "aria-pressed": String(state[group] === value),
        },
        label,
        count !== undefined && el("small", {}, count),
      );
    const kinds = Object.keys(KINDS).filter((k) => k === "all" || kindCount(k) > 0);
    const dirTones = { buff: "var(--buff)", nerf: "var(--nerf)", adjust: "var(--adjust)", new: "var(--fresh)", removed: "var(--gone)", fix: "var(--fix)" };
    const dirs = ["all", ...Object.keys(dirTones).filter((d) => (patch.counts || {})[d])];
    const node = el(
      "div",
      { class: "tft-tools" },
      el(
        "div",
        { class: "tools-row" },
        search,
        el("label", { class: "toggle", title: "Tìm trong mọi bản của mùa này, xem lịch sử tăng/giảm" }, wide, `Cả mùa ${patch.set}`),
      ),
      el("nav", { class: "kind-tabs", "aria-label": "Loại thay đổi" }, kinds.map((k) => chip("kind", k, `${KINDS[k][1]} ${KINDS[k][0]}`, kindCount(k)))),
      el(
        "div",
        { class: "kind-tabs", role: "group", "aria-label": "Tăng hay giảm" },
        dirs.map((d) => (d === "all" ? chip("dir", "all", "Mọi thay đổi") : chip("dir", d, `${DIRS[d][1]} ${DIRS[d][2]}`, patch.counts[d], dirTones[d]))),
      ),
    );
    node.addEventListener("click", (event) => {
      const button = event.target.closest("[data-group]");
      if (!button) return;
      const { group, value } = button.dataset;
      state[group] = state[group] === value && value !== "all" ? "all" : value;
      repaint();
    });
    return { node, search, wide };
  }

  // 18.5 (launch) → 18.5b → 18.5c: the updates Riot added after the patch went
  // live, newest marked; clicking one shows only its changes.
  function hotfixLine(patch, latest) {
    const fixes = hotfixesOf(patch);
    if (!fixes.length) return null;
    const all = changesOf(patch);
    const baseCount = all.filter((c) => !c.hotfix).length;
    const newest = fixes[fixes.length - 1];
    const step = (id, title, date, count, extra) =>
      el(
        "button",
        { type: "button", class: `hf${state.hotfix === id ? " is-on" : ""}${extra || ""}`, "data-hotfix": id, "aria-pressed": String(state.hotfix === id) },
        el("b", {}, title),
        el("small", {}, date),
        el("span", {}, `${count} thay đổi`),
      );
    return el(
      "div",
      { class: "hf-wrap" },
      el("p", { class: "hf-title" }, `⚡ Phiên bản này có ${fixes.length} bản vá giữa phiên bản · mới nhất `, el("b", {}, newest.label), newest.date ? ` (${dayMonth(newest.date)})` : ""),
      el(
        "div",
        { class: "hf-line", role: "group", "aria-label": "Bản vá trong phiên bản" },
        step("base", patch.version, patch.published_at ? `${dayMonth(patch.published_at.slice(0, 10))} · ra mắt` : "ra mắt", baseCount, " is-base"),
        fixes.map((f) => [
          el("i", { class: "hf-arrow", "aria-hidden": "true" }, "→"),
          step(f.id, f.label, f.date ? dayMonth(f.date) : "giữa phiên bản", f.count, f === newest ? (patch.version === latest ? " is-newest is-live" : " is-newest") : ""),
        ]),
        state.hotfix !== "all" && el("button", { type: "button", class: "chipbtn", "data-hotfix": "all" }, "✕ Xem tất cả"),
      ),
    );
  }

  // One tile per kind: what got stronger or weaker at a glance.
  function kindSummary(patch) {
    const inHotfix = (c) => state.hotfix === "all" || (state.hotfix === "base" ? !c.hotfix : c.hotfix === state.hotfix);
    const all = changesOf(patch).filter(inHotfix);
    const tiles = ["champions", "traits", "items", "augments", "mechanics", "modes"]
      .map((kind) => {
        const mine = all.filter((c) => c.kind === kind);
        if (!mine.length) return null;
        const n = (d) => mine.filter((c) => c.dir === d).length;
        return el(
          "button",
          { type: "button", class: `ksum${state.kind === kind ? " is-on" : ""}`, "data-group": "kind", "data-value": kind, "data-kind": kind },
          el("span", { class: "ksum-ico", "aria-hidden": "true" }, KINDS[kind][1]),
          el("b", {}, KINDS[kind][0]),
          el(
            "span",
            { class: "ksum-n" },
            n("buff") > 0 && el("em", { "data-dir": "buff" }, `▲${n("buff")}`),
            n("nerf") > 0 && el("em", { "data-dir": "nerf" }, `▼${n("nerf")}`),
            n("adjust") + n("new") + n("removed") > 0 && el("em", { "data-dir": "adjust" }, `◆${n("adjust") + n("new") + n("removed")}`),
          ),
        );
      })
      .filter(Boolean);
    return tiles.length ? el("section", { class: "ksums", "aria-label": "Tóm tắt theo loại" }, tiles) : null;
  }

  function sectionView(patch, query) {
    const plain = state.kind === "all" && state.dir === "all" && state.hotfix === "all" && !query;
    const out = [];
    const intro = patch.sections.filter((s) => !s.changes.length).flatMap((s) => s.notes);
    if (plain) {
      out.push(...notesBlock(intro));
      for (const section of patch.sections) {
        if (!section.changes.length) continue;
        const kind = KINDS[section.kind] ? section.kind : "other";
        const mine = section.changes.map((c) => ({ ...c, section: section.title, version: patch.version }));
        if (section.mid) {
          // Mid-patch updates: one highlighted block per update, newest first.
          const letters = [...new Set(mine.map((c) => c.hotfix).filter(Boolean))].sort().reverse();
          const newest = latestHotfix(patch);
          out.push(
            el(
              "section",
              { class: "tsec is-hotfix" },
              el("div", { class: "tsec-head" }, el("span", { class: "ico", "aria-hidden": "true" }, "⚡"), el("h2", {}, section.title), el("small", {}, `${section.changes.length}`)),
              notesBlock(section.notes),
              letters.length
                ? letters.map((letter) => {
                    const info = hotfixesOf(patch).find((f) => f.id === letter) || { label: `${patch.version}${letter}` };
                    const group = mine.filter((c) => c.hotfix === letter);
                    return el(
                      "div",
                      { class: `hf-block${newest && newest.id === letter ? " is-newest" : ""}` },
                      el(
                        "p",
                        { class: "hf-block-head" },
                        el("b", {}, `Bản vá ${info.label}`),
                        info.date ? ` · ${dayMonth(info.date)}/${info.date.slice(0, 4)}` : "",
                        ` · ${group.length} thay đổi`,
                        newest && newest.id === letter && el("span", { class: "badge" }, "MỚI NHẤT"),
                      ),
                      cards(group, patch.icons, section.title),
                    );
                  })
                : cards(mine, patch.icons, section.title),
            ),
          );
          continue;
        }
        out.push(
          el(
            "section",
            { class: "tsec" },
            el("div", { class: "tsec-head" }, el("span", { class: "ico", "aria-hidden": "true" }, KINDS[kind][1]), el("h2", {}, section.title), el("small", {}, `${section.changes.length}`)),
            notesBlock(section.notes),
            cards(mine, patch.icons, section.title),
          ),
        );
      }
      return out;
    }
    const found = changesOf(patch).filter((c) => matches(c, query));
    if (!found.length) return [el("p", { class: "empty" }, "Không có thay đổi nào khớp bộ lọc.")];
    out.push(
      el(
        "section",
        { class: "tsec" },
        el(
          "div",
          { class: "tsec-head" },
          el("span", { class: "ico", "aria-hidden": "true" }, KINDS[state.kind][1]),
          el("h2", {}, state.kind === "all" ? "Kết quả" : KINDS[state.kind][0]),
          el("small", {}, `${found.length} thay đổi`),
        ),
        cards(found, patch.icons, "Khác"),
      ),
    );
    return out;
  }

  // Every patch of the season that touched what was searched: its history.
  function historyView(patches, current, query) {
    const season = patches.filter((p) => p.set === current.set);
    const items = [];
    let up = 0;
    let down = 0;
    for (const patch of season) {
      const found = changesOf(patch).filter((c) => matches(c, query));
      if (!found.length) continue;
      up += found.filter((c) => c.dir === "buff").length;
      down += found.filter((c) => c.dir === "nerf").length;
      items.push(
        el(
          "li",
          { class: "tl-item" },
          el(
            "div",
            { class: "tl-head" },
            el("a", { href: `#/tft/${encodeURIComponent(patch.version)}` }, `Bản ${patch.version}`),
            el("small", {}, patch.published_at ? dateFmt.format(new Date(patch.published_at)) : ""),
            dpill(overall(found)),
          ),
          cards(found, patch.icons, "Khác"),
        ),
      );
    }
    if (!items.length) return [el("p", { class: "empty" }, `Không bản nào trong mùa ${current.set} khớp bộ lọc.`)];
    return [
      el(
        "div",
        { class: "tsec-head" },
        el("span", { class: "ico", "aria-hidden": "true" }, "🕰️"),
        el("h2", {}, query ? `“${state.query}” qua mùa ${current.set}` : `Mùa ${current.set}`),
        el("small", {}, `${items.length} bản · ▲${up} ▼${down}`),
      ),
      el("ol", { class: "timeline" }, items),
    ];
  }


  // --- Stat sheets (data/tft_db/<set>.json) -----------------------------------

  const dbs = {};
  const dbLoaded = {}; // set -> db once loaded (for icons in reward chips)
  const COST_COLORS = { 1: "#9aa4b8", 2: "#34d399", 3: "#3b82f6", 4: "#c026d3", 5: "#ffc94d", 6: "#ff6a3d", 7: "#ff4fd8" };
  const TIERS = { 1: ["Bạc", "#c0c8d8"], 2: ["Vàng", "#ffc94d"], 3: ["Kim cương", "#c084fc"] };
  const TYPES = { champions: ["Tướng", "🦸"], traits: ["Tộc/Hệ", "🧬"], items: ["Trang bị", "🗡️"], augments: ["Nâng cấp", "💠"], rewards: ["Phần thưởng & lõi đặc biệt", "🎁"] };
  let summaryRef = null;

  function dbSets() {
    return (summaryRef && summaryRef.db_sets) || [];
  }

  function loadDb(set) {
    if (!dbs[set]) {
      const v = encodeURIComponent((summaryRef && summaryRef.version) || "");
      dbs[set] = fetch(`tft-db-${set}.json?v=${v}`)
        .then((response) => {
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return response.json();
        })
        .then((db) => {
          db.index = new Map();
          for (const type of Object.keys(TYPES)) {
            for (const entry of db[type] || []) {
              const key = fold(entry.name);
              // Champions win over same-named items (an emblem named after a trait...).
              if (entry.name && !db.index.has(key)) db.index.set(key, { type, entry });
            }
          }
          dbLoaded[set] = db;
          return db;
        })
        .catch((error) => {
          delete dbs[set];
          throw error;
        });
    }
    return dbs[set];
  }

  function bare(name) {
    return fold(String(name || "").replace(/\s*\([^)]*\)\s*$/, ""));
  }

  // Every change of the season about ``name``, newest patch first.
  function seasonHistory(set, name) {
    const key = bare(name);
    const out = [];
    for (const patch of (data && data.patches) || []) {
      if (patch.set !== set) continue;
      const found = changesOf(patch).filter((c) => c.subject && bare(c.subject) === key);
      if (found.length) out.push({ patch, found });
    }
    return out;
  }

  function richText(text) {
    // Numbers stand out; text stays text (never HTML).
    const parts = String(text || "").split(/(\d+(?:[.,]\d+)?(?:\/\d+(?:[.,]\d+)?)*%?)/);
    return parts.map((part, i) => (i % 2 ? el("b", { class: "num" }, part) : part));
  }

  function statTile(label, value, icon) {
    return el("div", { class: "stile" }, el("span", { class: "stile-ico", "aria-hidden": "true" }, icon), el("b", {}, value ?? "—"), el("small", {}, label));
  }

  const fmt = (n, digits = 2) => (typeof n === "number" ? String(Math.round(n * 10 ** digits) / 10 ** digits).replace(".", ",") : "—");

  function sheetBody(set, db, hit, open) {
    const { type, entry } = hit;
    const parts = [];
    const tone = type === "champions" ? COST_COLORS[entry.cost] || GOLD : type === "augments" ? (TIERS[entry.tier] || [, GOLD])[1] : type === "traits" ? "#a78bfa" : "#60a5fa";
    const subtitle = [];
    if (type === "champions") subtitle.push(`${entry.cost} vàng`);
    if (type === "augments" && TIERS[entry.tier]) subtitle.push(`Nâng cấp ${TIERS[entry.tier][0]}`);
    if (type === "augments") subtitle.push(entry.pool === false ? "Không có trong vòng chọn" : entry.stages && entry.stages.length ? `Xuất hiện ở ${entry.stages.join(", ")}` : "Không ra ở lượt chọn thường");
    if (type === "items" && entry.kind) subtitle.push((ITEM_KINDS.find(([k]) => k === entry.kind) || [, "Trang bị"])[1]);
    if (type === "items" && entry.from && entry.from.length) subtitle.push("Trang bị ghép");
    parts.push(
      el(
        "header",
        { class: "sheet-head", style: `--tone:${tone}` },
        avatar(entry.name, entry.icon, type),
        el(
          "div",
          { class: "sheet-title" },
          el("small", {}, `${TYPES[type][1]} ${TYPES[type][0]} · Mùa ${set}`),
          el("h2", {}, entry.name),
          subtitle.length > 0 && el("p", {}, subtitle.join(" · ")),
          type === "champions" &&
            el("div", { class: "chips" }, entry.traits.map((t) => el("button", { type: "button", class: "chipbtn", onclick: () => open(t) }, `🧬 ${t}`))),
        ),
      ),
    );
    if (type === "champions") {
      const st = entry.stats || {};
      parts.push(
        el(
          "div",
          { class: "stiles" },
          statTile("Máu", fmt(st.hp, 0), "❤️"),
          statTile("Sức mạnh công kích", fmt(st.damage, 0), "⚔️"),
          statTile("Tốc độ đánh", fmt(st.attackSpeed), "⚡"),
          statTile("Giáp", fmt(st.armor, 0), "🛡️"),
          statTile("Kháng phép", fmt(st.magicResist, 0), "🔮"),
          statTile("Năng lượng", st.mana != null ? `${fmt(st.initialMana, 0)}/${fmt(st.mana, 0)}` : "—", "💧"),
          statTile("Tầm đánh (ô)", fmt(st.range, 0), "🎯"),
          statTile("Chí mạng", st.critChance != null ? `${fmt(st.critChance * 100, 0)}% · x${fmt(st.critMultiplier)}` : "—", "💥"),
        ),
      );
      const ab = entry.ability || {};
      parts.push(
        el(
          "section",
          { class: "sheet-sec" },
          el("h3", {}, "✨ Kỹ năng", ab.name ? `: ${ab.name}` : ""),
          ab.desc && el("p", { class: "sheet-desc" }, richText(ab.desc)),
          ab.variables && ab.variables.length
            ? el(
                "table",
                { class: "vars" },
                el("thead", {}, el("tr", {}, el("th", {}, "Chỉ số kỹ năng"), el("th", {}, "1★ / 2★ / 3★"))),
                el("tbody", {}, ab.variables.map((v) => el("tr", {}, el("td", {}, v.name), el("td", {}, v.value)))),
              )
            : null,
          latestValues(set, entry.name, !(ab.variables && ab.variables.length)),
        ),
      );
    }
    if (type === "traits") {
      if (entry.desc) parts.push(el("p", { class: "sheet-desc" }, richText(entry.desc)));
      parts.push(
        el(
          "section",
          { class: "sheet-sec" },
          el("h3", {}, "📶 Các mốc kích hoạt"),
          el(
            "ol",
            { class: "bps" },
            entry.breakpoints.map((b) => el("li", { "data-style": b.style }, el("span", { class: "bp-n" }, b.min), el("span", {}, richText(b.text.replace(/^\(\d+\)\s*/, "") || "—")))),
          ),
        ),
      );
      const members = db.champions.filter((c) => c.traits.includes(entry.name));
      if (members.length)
        parts.push(
          el(
            "section",
            { class: "sheet-sec" },
            el("h3", {}, `🦸 Tướng (${members.length})`),
            el("div", { class: "mini-grid" }, members.map((c) => miniChamp(c, open))),
          ),
        );
    }
    if (type === "items" || type === "augments") {
      if (entry.stats && entry.stats.length)
        parts.push(el("div", { class: "chips" }, entry.stats.map((x) => el("span", { class: "dpill", "data-dir": "new" }, `${x.label} `, el("b", {}, x.value)))));
      if (entry.desc) parts.push(el("p", { class: "sheet-desc" }, richText(entry.desc)));
      if (entry.from && entry.from.length) {
        parts.push(
          el(
            "section",
            { class: "sheet-sec" },
            el("h3", {}, "🧩 Công thức"),
            el(
              "div",
              { class: "recipe" },
              entry.from.map((name, i) => {
                const part = db.index.get(fold(name));
                return [i > 0 && el("span", { class: "plus" }, "+"), el("button", { type: "button", class: "mover", onclick: () => open(name) }, avatar(name, part && part.entry.icon, "items"), name)];
              }),
            ),
          ),
        );
      }
    }
    if (type === "augments" && entry.pool !== false) parts.push(el("div", { class: "sheet-sec" }, el("h3", {}, "⏱ Giai đoạn xuất hiện"), stagePills(entry.stages || [])));
    const rewards =
      (type === "traits" && REWARD_RX.test([entry.desc, ...(entry.breakpoints || []).map((b) => b.text)].join(" "))) ||
      (type === "augments" && RANDOM_RX.test(entry.desc || ""));
    const loot = rewardTables(set, entry.name);
    if (loot) parts.push(el("section", { class: "sheet-sec" }, el("h3", {}, "🎰 Phần thưởng & tỉ lệ"), loot.map((t) => lootView(t, set))));
    if (rewards) {
      const table = rewardTable(set, entry.name, !loot);
      if (table) parts.push(el("section", { class: "sheet-sec" }, table));
    } else if (type !== "champions") {
      const values = latestValues(set, entry.name, false);
      if (values) parts.push(el("section", { class: "sheet-sec" }, values));
    }
    const history = seasonHistory(set, entry.name);
    parts.push(
      el(
        "section",
        { class: "sheet-sec" },
        el("h3", {}, `🕰️ Thay đổi trong mùa ${set}`),
        history.length
          ? el(
              "ol",
              { class: "timeline" },
              history.map(({ patch, found }) =>
                el(
                  "li",
                  { class: "tl-item" },
                  el("div", { class: "tl-head" }, el("a", { href: `#/tft/${encodeURIComponent(patch.version)}` }, `Bản ${patch.version}`), dpill(overall(found))),
                  el("ul", { class: "lines" }, found.map(line)),
                ),
              ),
            )
          : el("p", { class: "none" }, "Chưa có thay đổi nào trong các bản cập nhật của mùa."),
      ),
    );
    return parts;
  }

  // The newest value of every stat the season's patch notes changed: the
  // ability numbers when the game data leaves them out ("?").
  function latestValues(set, name, primary) {
    const rows = new Map();
    for (const { patch, found } of seasonHistory(set, name)) {
      for (const change of found) {
        if (!change.after || !change.stat) continue;
        const key = fold(change.stat);
        if (!rows.has(key)) rows.set(key, { stat: change.stat, value: change.after, version: patch.version, dir: change.dir });
      }
    }
    if (!rows.size) {
      return primary ? el("p", { class: "none" }, "Dữ liệu game chưa kèm số liệu kỹ năng (chỗ “?”), và các bản cập nhật của mùa chưa đổi chỉ số nào của tướng này.") : null;
    }
    return el(
      "div",
      {},
      el("h4", { class: "vars-title" }, primary ? "📊 Số liệu kỹ năng (theo bản cập nhật gần nhất)" : "📊 Số liệu mới nhất theo patch notes"),
      el(
        "table",
        { class: "vars" },
        el("thead", {}, el("tr", {}, el("th", {}, "Chỉ số"), el("th", {}, "Giá trị hiện tại"), el("th", {}, "Từ bản"))),
        el(
          "tbody",
          {},
          [...rows.values()].map((r) =>
            el("tr", { "data-dir": r.dir }, el("td", {}, r.stat), el("td", {}, r.value), el("td", { class: "ver-cell" }, el("a", { href: `#/tft/${r.version}` }, r.version))),
          ),
        ),
      ),
    );
  }

  function miniChamp(c, open) {
    return el(
      "button",
      { type: "button", class: "mini", style: `--tone:${COST_COLORS[c.cost] || GOLD}`, onclick: () => open(c.name), title: c.name },
      avatar(c.name, c.icon, "champions"),
      el("span", {}, c.name),
    );
  }

  let sheetDialog = null;
  function openSheet(set, name) {
    if (!dbSets().includes(set)) {
      toast(`Chưa có bảng thông số mùa ${set}`);
      return;
    }
    if (!sheetDialog) {
      sheetDialog = el("dialog", { class: "sheet", "aria-label": "Thông số" });
      sheetDialog.addEventListener("click", (event) => event.target === sheetDialog && sheetDialog.close());
      document.body.append(sheetDialog);
    }
    const dialog = sheetDialog;
    const show = (content) => {
      dialog.replaceChildren(
        el("form", { method: "dialog", class: "sheet-close" }, el("button", { type: "submit", "aria-label": "Đóng" }, "✕")),
        el("div", { class: "sheet-in" }, content),
      );
      if (!dialog.open) dialog.showModal();
      dialog.scrollTop = 0;
    };
    show(el("div", { class: "skeleton" }, el("i"), el("i")));
    Promise.all([loadDb(set), data ? Promise.resolve(data) : load(summaryRef), loadRewards(set)])
      .then(([db]) => {
        const hit = db.index.get(fold(name)) || db.index.get(bare(name));
        if (!hit) {
          show([el("h2", {}, name), el("p", { class: "none" }, "Không tìm thấy thông số trong dữ liệu game (có thể là cơ chế, không phải tướng/trang bị)."), ...sheetHistoryOnly(set, name)]);
          return;
        }
        show(sheetBody(set, db, hit, (other) => openSheet(set, other)));
      })
      .catch((error) => show(el("p", { class: "empty" }, `Không tải được thông số: ${error.message}`)));
  }

  function sheetHistoryOnly(set, name) {
    const history = seasonHistory(set, name);
    if (!history.length) return [];
    return [
      el("h3", {}, `🕰️ Thay đổi trong mùa ${set}`),
      el("ol", { class: "timeline" }, history.map(({ patch, found }) => el("li", { class: "tl-item" }, el("div", { class: "tl-head" }, el("a", { href: `#/tft/${patch.version}` }, `Bản ${patch.version}`)), el("ul", { class: "lines" }, found.map(line))))),
    ];
  }

  // --- The lookup page: #/tft/tra-cuu[/<set>] --------------------------------

  const dbState = { type: "champions", query: "", stage: "all", tier: "all", showGone: false, itemKind: "completed" };

  function renderDb(view, appData, set) {
    const sets = dbSets();
    const current = sets.includes(set) ? set : sets[0];
    const patch = ((data && data.patches) || []).find((p) => p.set === current);
    const setName = patch && patch.set_name;
    document.title = `Tra cứu thông số ĐTCL mùa ${current} – GiftCode Finder`;
    const body = el("div", { class: "db-body" }, el("div", { class: "skeleton" }, el("i"), el("i")));
    const search = el("input", { class: "search", type: "search", placeholder: "Tìm tướng, tộc hệ, trang bị, nâng cấp…", value: dbState.query, "aria-label": "Tìm trong bảng thông số" });
    const tabs = el(
      "nav",
      { class: "kind-tabs", "aria-label": "Loại" },
      Object.entries(TYPES).map(([type, [label, icon]]) =>
        el("button", { type: "button", class: `chipbtn${dbState.type === type ? " is-on" : ""}`, "data-type": type, "aria-pressed": String(dbState.type === type) }, `${icon} ${label}`),
      ),
    );
    view.replaceChildren(
      el(
        "section",
        { class: "tft-hero db-hero" },
        el(
          "div",
          { class: "tft-hero-text" },
          el("p", { class: "tft-kicker" }, "📚 Đấu Trường Chân Lý · Tra cứu thông số"),
          el("h1", { class: "tft-title" }, "Mùa ", el("span", { class: "ver" }, current), setName ? ` · ${setName}` : ""),
          el("p", { class: "tft-meta" }, "Chỉ số gốc của mọi tướng, mốc tộc/hệ, trang bị và nâng cấp theo dữ liệu game mới nhất. Bấm vào một ô để xem đầy đủ và lịch sử tăng/giảm trong mùa."),
        ),
        hexPrism(`S${current}`),
      ),
      viewSwitch("db", current),
      el(
        "nav",
        { class: "seasons", "aria-label": "Chọn mùa" },
        sets.map((n) => el("a", { class: `season${n === current ? " is-on" : ""}`, href: `#/tft/tra-cuu/${n}` }, el("b", {}, `Mùa ${n}`), el("small", {}, "thông số"))),
      ),
      el("div", { class: "tft-tools" }, el("div", { class: "tools-row" }, search), tabs),
      body,
    );
    Promise.all([loadDb(current), loadRewards(current)])
      .then(([db]) => {
        const paint = () => {
          const q = fold(dbState.query);
          for (const b of tabs.querySelectorAll("[data-type]")) {
            const on = b.dataset.type === dbState.type;
            b.classList.toggle("is-on", on);
            b.setAttribute("aria-pressed", String(on));
          }
          body.replaceChildren(...dbGrid(db, current, dbState.type, q));
        };
        tabs.addEventListener("click", (event) => {
          const b = event.target.closest("[data-type]");
          if (!b) return;
          dbState.type = b.dataset.type;
          paint();
        });
        body.addEventListener("click", (event) => {
          const f = event.target.closest("[data-db]");
          if (!f) return;
          const key = f.dataset.db;
          dbState[key] = key === "showGone" ? !dbState.showGone : f.dataset.value;
          paint();
        });
        let timer;
        search.addEventListener("input", () => {
          clearTimeout(timer);
          timer = setTimeout(() => {
            dbState.query = search.value.trim();
            paint();
          }, 120);
        });
        paint();
      })
      .catch((error) => body.replaceChildren(el("p", { class: "empty" }, `Không tải được thông số: ${error.message}`)));
  }

  function dbGrid(db, set, type, q) {
    const open = (name) => openSheet(set, name);
    if (type === "rewards") return rewardsView(db, set, q, open);
    const hit = (e) => !q || fold([e.name, e.desc, (e.traits || []).join(" "), (e.ability && e.ability.name) || ""].join(" ")).includes(q);
    const list = (db[type] || []).filter(hit);
    if (!list.length) return [el("p", { class: "empty" }, "Không có mục nào khớp.")];
    if (type === "champions") {
      const byCost = new Map();
      for (const c of list) byCost.set(c.cost, [...(byCost.get(c.cost) || []), c]);
      return [...byCost.entries()].map(([cost, champs]) =>
        el(
          "section",
          { class: "tsec" },
          el("div", { class: "tsec-head" }, el("span", { class: "ico", style: `background:${COST_COLORS[cost] || GOLD};color:#111` }, cost), el("h2", {}, `Tướng ${cost} vàng`), el("small", {}, champs.length)),
          el(
            "div",
            { class: "champ-grid" },
            champs.map((c) =>
              el(
                "button",
                { type: "button", class: "champ", style: `--tone:${COST_COLORS[c.cost] || GOLD}`, onclick: () => open(c.name) },
                avatar(c.name, c.icon, "champions"),
                el("b", {}, c.name),
                el("small", {}, c.traits.join(" · ")),
                el("span", { class: "champ-stats" }, `❤️${fmt(c.stats.hp, 0)} ⚔️${fmt(c.stats.damage, 0)} 💧${fmt(c.stats.initialMana, 0)}/${fmt(c.stats.mana, 0)}`),
              ),
            ),
          ),
        ),
      );
    }
    if (type === "traits") {
      return [
        el(
          "div",
          { class: "cards" },
          list.map((t, i) =>
            el(
              "article",
              { class: "sc db-card", "data-dir": "new", style: `--i:${i}`, tabindex: "0", role: "button", onclick: () => open(t.name), onkeydown: (e) => e.key === "Enter" && open(t.name) },
              el("header", { class: "sc-head" }, avatar(t.name, t.icon, "traits"), el("div", { class: "sc-name" }, el("h3", {}, t.name), el("small", {}, `Mốc: ${t.breakpoints.map((b) => b.min).join(" / ")}`))),
              el("p", { class: "sheet-desc small" }, richText(t.desc || "")),
            ),
          ),
        ),
      ];
    }
    if (type === "augments") return augmentGrid(db, set, list, open);
    if (type === "items") return itemGrid(db, list, open);
    return [];
  }

  // --- Lookup: augments by stage, items by kind, rewards -----------------------

  const STAGES = ["2-1", "3-2", "4-2"];
  const ITEM_KINDS = [
    ["completed", "Trang bị ghép", "⚔️"],
    ["component", "Thành phần", "🧩"],
    ["radiant", "Ánh Sáng", "✨"],
    ["artifact", "Tạo tác (Ornn)", "🔨"],
    ["emblem", "Ấn", "🧬"],
    ["support", "Hỗ trợ", "🤝"],
    ["mechanic", "Cơ chế mùa", "🌿"],
    ["consumable", "Tiêu hao", "🧪"],
    ["other", "Khác", "✳️"],
  ];
  // Traits that pay out (cash-out traits) and augments with random or conditional rewards.
  const REWARD_RX = /phần thưởng|báu vật|chiến lợi phẩm|nổ hũ|chuyển đổi .*thành|tích lũy|tích trữ|rương|loot|payout|cash ?out/i;
  const RANDOM_RX = /ngẫu nhiên|phần thưởng|báu vật|trứng|rương|nở ra|sau \d+ vòng|mỗi \d+ vòng|tích lũy|khi .{0,40}(đạt|hoàn thành)|random|reward|egg/i;
  const CHANCE_RX = /tỉ lệ|tỷ lệ|cơ hội|xác suất|\bchance\b|\bodds\b/i;

  function chip(label, on, attrs) {
    return el("button", { type: "button", class: `chipbtn${on ? " is-on" : ""}`, "aria-pressed": String(on), ...attrs }, label);
  }

  function stagePills(stages) {
    return el(
      "span",
      { class: "stages", title: stages.length ? `Xuất hiện ở giai đoạn ${stages.join(", ")}` : "Không xuất hiện ở lượt chọn nâng cấp thường" },
      STAGES.map((stage) => el("i", { class: stages.includes(stage) ? "on" : "" }, stage)),
    );
  }

  function augmentCard(a, i, open, extra) {
    const [tierName, tierColor] = TIERS[a.tier] || ["?", "#94a3b8"];
    return el(
      "article",
      {
        class: `sc db-card aug${a.pool ? "" : " is-gone"}`,
        style: `--i:${i};--tone:${tierColor}`,
        tabindex: "0",
        role: "button",
        onclick: () => open(a.name),
        onkeydown: (ev) => ev.key === "Enter" && open(a.name),
      },
      el(
        "header",
        { class: "sc-head" },
        avatar(a.name, a.icon, "augments"),
        el("div", { class: "sc-name" }, el("h3", {}, a.name), el("small", {}, `Nâng cấp ${tierName}`)),
        a.pool ? stagePills(a.stages) : el("span", { class: "gone-tag" }, "Không có trong vòng chọn"),
      ),
      el("p", { class: "sheet-desc small" }, richText(a.desc || "")),
      extra,
    );
  }

  function augmentPasses(a) {
    return (
      (dbState.showGone || a.pool) &&
      (dbState.stage === "all" || (a.pool && a.stages.includes(dbState.stage))) &&
      (dbState.tier === "all" || String(a.tier) === dbState.tier)
    );
  }

  // Stage and tier chips, shared by the augment list and the rewards tab.
  function augmentFilters(list, set, note = true) {
    const latest = ((data && data.patches) || []).find((p) => p.set === set);
    const newestSet = Math.max(...dbSets());
    const gone = list.filter((a) => !a.pool).length;
    return el(
      "div",
      { class: "db-filters" },
      el(
        "div",
        { class: "kind-tabs", role: "group", "aria-label": "Giai đoạn" },
        chip("Mọi giai đoạn", dbState.stage === "all", { "data-db": "stage", "data-value": "all" }),
        STAGES.map((stage) => chip(`⏱ ${stage}`, dbState.stage === stage, { "data-db": "stage", "data-value": stage })),
      ),
      el(
        "div",
        { class: "kind-tabs", role: "group", "aria-label": "Bậc" },
        chip("Mọi bậc", dbState.tier === "all", { "data-db": "tier", "data-value": "all" }),
        Object.entries(TIERS).map(([tier, [name, color]]) => chip([el("i", { class: "tier-dot", style: `background:${color}` }), name], dbState.tier === tier, { "data-db": "tier", "data-value": tier, style: `--tone:${color}` })),
        gone > 0 && chip(`${dbState.showGone ? "✓ " : ""}Hiện cả ${gone} lõi không có trong vòng chọn`, dbState.showGone, { "data-db": "showGone", "data-value": "toggle" }),
      ),
      note &&
        el(
          "p",
          { class: "db-note" },
          `Giai đoạn xuất hiện và lõi có trong vòng chọn đọc từ dữ liệu game ${set === newestSet ? `của bản hiện tại${latest ? ` (${latest.version})` : ""}` : `lần cuối mùa ${set} có trong game`}. Lõi chỉ đến từ nguồn khác (Triệu Gọi Hỗn Mang, Ân Huệ…) hoặc đã gỡ được ẩn, bật nút trên để xem.`,
        ),
    );
  }

  function augmentGrid(db, set, list, open) {
    const shown = list.filter(augmentPasses);
    const filters = augmentFilters(list, set);
    if (!shown.length) return [filters, el("p", { class: "empty" }, "Không có lõi nào khớp bộ lọc.")];
    const groups = new Map();
    for (const a of shown) {
      const key = a.pool ? a.tier || 0 : "gone";
      groups.set(key, [...(groups.get(key) || []), a]);
    }
    return [
      filters,
      ...[...groups.entries()].map(([key, entries]) =>
        el(
          "section",
          { class: "tsec" },
          el(
            "div",
            { class: "tsec-head" },
            el("span", { class: "ico", style: key === "gone" ? "" : `background:${(TIERS[key] || [, "#94a3b8"])[1]};color:#111` }, key === "gone" ? "🚫" : "💠"),
            el("h2", {}, key === "gone" ? "Không có trong vòng chọn" : `Nâng cấp ${(TIERS[key] || ["khác"])[0]}`),
            el("small", {}, entries.length),
          ),
          el("div", { class: "cards" }, entries.map((a, i) => augmentCard(a, i, open))),
        ),
      ),
    ];
  }

  function recipe(db, names) {
    if (!names || !names.length) return null;
    return el(
      "span",
      { class: "mini-recipe", title: `Ghép từ: ${names.join(" + ")}` },
      names.map((name, i) => {
        const part = db.index.get(fold(name));
        return [i > 0 && "+", avatar(name, part && part.entry.icon, "items"), el("small", {}, name)];
      }),
    );
  }

  function itemGrid(db, list, open) {
    const counts = Object.fromEntries(ITEM_KINDS.map(([kind]) => [kind, list.filter((i) => (i.kind || "other") === kind).length]));
    if (!counts[dbState.itemKind]) dbState.itemKind = (ITEM_KINDS.find(([kind]) => counts[kind]) || ["completed"])[0];
    const filters = el(
      "div",
      { class: "db-filters" },
      el(
        "div",
        { class: "kind-tabs", role: "group", "aria-label": "Loại trang bị" },
        ITEM_KINDS.filter(([kind]) => counts[kind]).map(([kind, label, icon]) => chip([`${icon} ${label} `, el("small", {}, counts[kind])], dbState.itemKind === kind, { "data-db": "itemKind", "data-value": kind })),
      ),
    );
    const seen = new Set();
    const shown = list.filter((i) => (i.kind || "other") === dbState.itemKind && !seen.has(i.name) && seen.add(i.name));
    return [
      filters,
      el(
        "div",
        { class: "cards" },
        shown.map((item, i) =>
          el(
            "article",
            { class: "sc db-card item-card", "data-dir": "new", style: `--i:${i}`, tabindex: "0", role: "button", onclick: () => open(item.name), onkeydown: (ev) => ev.key === "Enter" && open(item.name) },
            el("header", { class: "sc-head" }, avatar(item.name, item.icon, "items"), el("div", { class: "sc-name" }, el("h3", {}, item.name), recipe(db, item.from))),
            item.stats && item.stats.length > 0 && el("div", { class: "item-stats" }, item.stats.map((x) => el("span", {}, `${x.label} `, el("b", {}, x.value)))),
            el("p", { class: "sheet-desc small" }, richText(item.desc || "")),
          ),
        ),
      ),
    ];
  }

  // "2x Gói Trang Bị Hoàn Chỉnh + Caitlyn 2* + 12v" as picture chips: gold coins,
  // XP, starred champions, items (with their icons when known), chests and bundles.
  const REWARD_ICONS = [
    [/xẻng vàng|spatula/i, "🥄"],
    [/chảo vàng|frying pan/i, "🍳"],
    [/trứng|egg/i, "🥚"],
    [/rương|chest/i, "🧰"],
    [/ánh sáng|radiant/i, "✨"],
    [/tạo tác|ornn|artifact/i, "🔨"],
    [/hỗ trợ|support/i, "🤝"],
    [/ấn\b|emblem/i, "🧬"],
    [/gói|bộ |anvil|đe/i, "📦"],
    [/hoàn chỉnh|completed/i, "⚔️"],
    [/thành phần|component/i, "🧩"],
    [/đổi lại|lượt đổi|reroll/i, "🔄"],
    [/máu|health|hp/i, "❤️"],
    [/tướng|champion/i, "🦸"],
    [/vương miện|crown/i, "👑"],
    [/găng|gloves/i, "🧤"],
  ];

  function rewardChips(text, set) {
    const db = dbLoaded[set];
    const parts = String(text || "")
      .split(/\s*\+\s*|\s*,\s*(?=\d|[A-ZĐÂÊÔƠƯ])|\s+và\s+(?=\d)/)
      .map((t) => t.trim())
      .filter(Boolean);
    if (parts.length < 1) return null;
    const chips = parts.map((part) => {
      let label = part;
      let qty = null;
      const gold = part.match(/^(\d+)\s*(?:v|vàng|gold)$/i);
      if (gold) return el("span", { class: "rchip gold" }, el("span", { class: "rchip-ico" }, "🪙"), el("b", {}, gold[1]), el("small", {}, "vàng"));
      const xp = part.match(/^(\d+)\s*(?:xp|kn|kinh nghiệm)$/i);
      if (xp) return el("span", { class: "rchip xp" }, el("span", { class: "rchip-ico" }, "📘"), el("b", {}, xp[1]), el("small", {}, "XP"));
      const count = label.match(/^(\d+)\s*x\s*|^(\d+)\s+(?=\D)/i);
      if (count) {
        qty = count[1] || count[2];
        label = label.slice(count[0].length);
      }
      const star = label.match(/^(.+?)\s*(\d)\s*(?:\*|★|sao)$/i);
      const name = star ? star[1].trim() : label;
      const hit = db && (db.index.get(fold(name)) || db.index.get(bare(name)));
      const icon = hit && hit.entry.icon;
      const emoji = !icon && (REWARD_ICONS.find(([rx]) => rx.test(name)) || [, "🎁"])[1];
      return el(
        "span",
        { class: `rchip${hit && hit.type === "champions" ? " champ" : ""}`, title: part },
        icon ? avatar(name, icon, hit.type) : el("span", { class: "rchip-ico" }, emoji),
        qty && el("em", { class: "rchip-qty" }, `${qty}×`),
        el("span", { class: "rchip-name" }, name),
        star && el("span", { class: "rchip-star" }, "★".repeat(Number(star[2]))),
      );
    });
    return el("span", { class: "rchips" }, chips);
  }

  // A value that reads like loot gets chips; numbers and sentences stay text.
  const looksLikeLoot = (text) => /\+|\d\s*(?:v|vàng)\b|trang bị|rương|gói|\d\s*\*|ánh sáng|tạo tác|xẻng|chảo|găng|trứng/i.test(text || "") && String(text).length < 160;

  // What the season's patch notes said about ``name``'s rewards: the newest
  // value of every line, chance lines marked (the game data has no loot tables).
  function rewardTable(set, name, open = false) {
    const key = bare(name);
    const rows = new Map();
    for (const patch of ((data && data.patches) || []).filter((p) => p.set === set)) {
      for (const c of changesOf(patch)) {
        const hay = fold([c.subject, c.stat, c.text, c.group].join(" "));
        if (!(c.subject && bare(c.subject) === key) && !hay.includes(key)) continue;
        // "Nổ Hũ 130 · Phần thưởng" or the nested heading ("Phần Thưởng … mốc 250 Tinh Hoa").
        const head = [c.subject && bare(c.subject) !== key ? c.subject : null, c.group, c.stat].filter(Boolean).join(" · ");
        const label = head || c.text || "";
        const value = c.after || (head && c.text) || "";
        // Same milestone, several reward options: the old value tells them apart.
        const id = fold(`${label}|${c.before || ""}|${c.after ? "" : value}`);
        if (!label || rows.has(id)) continue;
        rows.set(id, { label, before: c.before || "", value, version: patch.version, chance: CHANCE_RX.test(`${label} ${value}`) });
      }
    }
    if (!rows.size) return null;
    const list = [...rows.values()].slice(0, 60);
    return el(
      "details",
      { class: "rewards", open: open || null },
      el("summary", {}, `🎁 Phần thưởng & số liệu theo patch notes (${list.length})`),
      el(
        "table",
        { class: "vars" },
        el("thead", {}, el("tr", {}, el("th", {}, "Mục"), el("th", {}, "Hiện tại"), el("th", {}, "Bản"))),
        el(
          "tbody",
          {},
          list.map((r) =>
            el("tr", { class: r.chance ? "is-chance" : "" }, el("td", {}, r.chance ? "🎲 " : "", r.label, r.before && el("small", { class: "was" }, `trước: ${r.before}`)), el("td", {}, looksLikeLoot(r.value) ? rewardChips(r.value, set) : r.value || "—"), el("td", { class: "ver-cell" }, el("a", { href: `#/tft/${r.version}` }, r.version))),
          ),
        ),
      ),
      el("p", { class: "db-note" }, "Riot không đưa bảng phần thưởng hay xác suất vào dữ liệu game; bảng gom từ các dòng patch notes của mùa (giá trị mới nhất). Dòng 🎲 là dòng có nhắc tỉ lệ."),
    );
  }

  // --- Loot tables (LoLCHESS.GG), one file per season --------------------------

  const rewardFiles = {};
  const rewardsLoaded = {};

  function loadRewards(set) {
    if (!((summaryRef && summaryRef.reward_sets) || []).includes(set)) return Promise.resolve(null);
    if (!rewardFiles[set]) {
      const v = encodeURIComponent((summaryRef && summaryRef.version) || "");
      rewardFiles[set] = fetch(`tft-rewards-${set}.json?v=${v}`)
        .then((response) => (response.ok ? response.json() : null))
        .then((rewards) => {
          if (rewards) {
            rewards.byName = new Map();
            for (const table of rewards.tables) {
              for (const name of table.links || []) rewards.byName.set(fold(name), [...(rewards.byName.get(fold(name)) || []), table]);
            }
          }
          rewardsLoaded[set] = rewards;
          return rewards;
        })
        .catch(() => null);
    }
    return rewardFiles[set];
  }

  function rewardTables(set, name) {
    const rewards = rewardsLoaded[set];
    return (rewards && rewards.byName.get(fold(name))) || null;
  }

  function lootItem(item, set) {
    const db = dbLoaded[set];
    const known = db && db.index.get(fold(item.name));
    const icon = (known && known.entry.icon) || item.icon;
    const champ = item.kind === "champions" || (known && known.type === "champions");
    const cost = item.cost || (known && known.entry.cost);
    return el(
      "span",
      { class: `rchip loot-item${champ ? " champ" : ""}`, style: champ && cost ? `--ring:${COST_COLORS[cost] || GOLD}` : null, title: item.name },
      avatar(item.name, icon, champ ? "champions" : "items"),
      item.qty && item.qty > 1 && el("em", { class: "rchip-qty" }, `${item.qty}×`),
      el("span", { class: "rchip-name" }, item.name),
    );
  }

  function parseChance(text) {
    const match = String(text || "").match(/(\d+(?:[.,]\d+)?)/);
    return match ? Number(match[1].replace(",", ".")) : null;
  }

  // One loot table: milestones, then one row per outcome with its chance.
  function lootView(table, set) {
    return el(
      "div",
      { class: "loot-box" },
      table.groups.map((group) => {
        const chances = group.rows.map((r) => parseChance(r.chance)).filter((x) => x !== null);
        const best = chances.length && new Set(chances).size > 1 ? Math.max(...chances) : null;
        return el(
          "div",
          { class: "loot-group-box" },
          (group.title || group.note) && el("p", { class: "loot-group" }, group.title ? `🎯 ${group.title}` : "", group.note && el("small", {}, ` · ${group.note}`)),
          el(
            "div",
            { class: "loot" },
            group.rows.map((row) =>
              el(
                "div",
                { class: `loot-row${best !== null && parseChance(row.chance) === best ? " top" : ""}` },
                el("span", { class: `loot-chance${row.chance ? "" : " none"}` }, row.chance || "chắc chắn"),
                el("span", { class: "rchips" }, row.items.map((item) => lootItem(item, set))),
              ),
            ),
          ),
        );
      }),
      el("p", { class: "loot-src" }, "Tỉ lệ & phần thưởng theo ", el("a", { href: table.url, target: "_blank", rel: "noopener" }, "LoLCHESS.GG ↗"), table.updated ? ` · cập nhật ${table.updated}` : ""),
    );
  }

  function lootCard(table, set, db, open, i) {
    const name = (table.links && table.links[0]) || table.title;
    const hit = db.index.get(fold(name));
    const aug = hit && hit.type === "augments" ? hit.entry : null;
    const [tierName, tierColor] = aug ? TIERS[aug.tier] || ["", GOLD] : ["", GOLD];
    return el(
      "article",
      { class: "sc db-card reward-card has-loot", style: `--i:${i};--tone:${tierColor}` },
      el(
        "header",
        { class: `sc-head${hit ? " has-sheet" : ""}`, onclick: hit ? () => open(name) : null },
        avatar(name, (hit && hit.entry.icon) || table.icon, hit ? hit.type : "augments"),
        el("div", { class: "sc-name" }, el("h3", {}, name), el("small", {}, [hit ? TYPES[hit.type][0] : "Bảng phần thưởng", aug && tierName ? ` · ${tierName}` : "", name !== table.title ? ` · ${table.title}` : ""].join(""))),
        aug && aug.pool && stagePills(aug.stages),
      ),
      el("p", { class: "sheet-desc small" }, richText((hit && hit.entry.desc) || table.desc || "")),
      lootView(table, set),
    );
  }

  function rewardsView(db, set, q, open) {
    const hit = (e) => !q || fold([e.name, e.desc].join(" ")).includes(q);
    const rewards = rewardsLoaded[set];
    const augs = db.augments.filter(hit);
    const passes = (name) => {
      const entry = db.index.get(fold(name));
      return !entry || entry.type !== "augments" || augmentPasses(entry.entry);
    };
    // Tables of the reward-table site: the main thing on this tab.
    const tables = ((rewards && rewards.tables) || []).filter((t) => {
      const name = (t.links && t.links[0]) || t.title;
      return (!q || fold(`${name} ${t.title} ${t.desc || ""}`).includes(q)) && passes(name);
    });
    const withLoot = new Set(tables.flatMap((t) => (t.links || []).map(fold)));
    const traits = db.traits.filter((t) => hit(t) && !withLoot.has(fold(t.name)) && REWARD_RX.test([t.desc, ...t.breakpoints.map((b) => b.text)].join(" ")));
    const pool = augs.filter(augmentPasses);
    const random = pool.filter((a) => !withLoot.has(fold(a.name)) && RANDOM_RX.test(a.desc || ""));
    const traitNames = db.traits.map((t) => t.name).filter((n) => n && n.length > 2);
    const byTrait = new Map();
    for (const a of pool) {
      const trait = traitNames.find((n) => fold(`${a.name} ${a.desc}`).includes(fold(n)));
      if (trait) byTrait.set(trait, [...(byTrait.get(trait) || []), a]);
    }
    const out = [
      augmentFilters(augs, set, false),
      el("p", { class: "db-note" }, "Bảng phần thưởng có tỉ lệ (từ LoLCHESS.GG), tộc/hệ “nổ hũ”, lõi cho phần thưởng ngẫu nhiên hoặc cần điều kiện, lõi theo tộc/hệ. Bộ lọc giai đoạn và bậc áp dụng cho các lõi."),
    ];
    if (tables.length) {
      const linked = tables.filter((t) => t.links && t.links.length);
      const other = tables.filter((t) => !(t.links && t.links.length));
      const block = (title, icon, list) =>
        el(
          "section",
          { class: "tsec" },
          el("div", { class: "tsec-head" }, el("span", { class: "ico" }, icon), el("h2", {}, title), el("small", {}, list.length)),
          el("div", { class: "cards wide-cards" }, list.map((t, i) => lootCard(t, set, db, open, i))),
        );
      if (linked.length) out.push(block("Bảng phần thưởng của lõi & tộc/hệ", "🎰", linked));
      if (other.length) out.push(block("Bảng phần thưởng khác (Tinh Linh, sự kiện, PvE…)", "🗃️", other));
    }
    if (traits.length)
      out.push(
        el(
          "section",
          { class: "tsec" },
          el("div", { class: "tsec-head" }, el("span", { class: "ico" }, "💰"), el("h2", {}, "Tộc/hệ có phần thưởng (theo patch notes)"), el("small", {}, traits.length)),
          el(
            "div",
            { class: "cards wide-cards" },
            traits.map((t, i) =>
              el(
                "article",
                { class: "sc db-card reward-card", "data-dir": "new", style: `--i:${i}` },
                el("header", { class: "sc-head has-sheet", "data-sheet": t.name, onclick: () => open(t.name) }, avatar(t.name, t.icon, "traits"), el("div", { class: "sc-name" }, el("h3", {}, t.name), el("small", {}, `Mốc: ${t.breakpoints.map((b) => b.min).join(" / ")}`))),
                el("p", { class: "sheet-desc" }, richText(t.desc || "")),
                el("ol", { class: "bps" }, t.breakpoints.map((b) => el("li", { "data-style": b.style }, el("span", { class: "bp-n" }, b.min), el("span", {}, richText(b.text.replace(/^\(\d+\)\s*/, "") || "—"))))),
                rewardTable(set, t.name, true),
              ),
            ),
          ),
        ),
      );
    if (random.length)
      out.push(
        el(
          "section",
          { class: "tsec" },
          el("div", { class: "tsec-head" }, el("span", { class: "ico" }, "🎲"), el("h2", {}, "Lõi phần thưởng ngẫu nhiên & có điều kiện"), el("small", {}, random.length)),
          el("div", { class: "cards" }, random.map((a, i) => augmentCard(a, i, open, rewardTable(set, a.name)))),
        ),
      );
    if (byTrait.size)
      out.push(
        el(
          "section",
          { class: "tsec" },
          el("div", { class: "tsec-head" }, el("span", { class: "ico" }, "🧬"), el("h2", {}, "Lõi theo tộc/hệ"), el("small", {}, [...byTrait.values()].reduce((n, l) => n + l.length, 0))),
          [...byTrait.entries()]
            .sort((x, y) => x[0].localeCompare(y[0]))
            .map(([trait, list]) =>
              el(
                "div",
                { class: "trait-augs" },
                el("p", { class: "hf-block-head" }, el("b", {}, trait), ` · ${list.length} lõi`),
                el("div", { class: "cards" }, list.map((a, i) => augmentCard(a, i, open))),
              ),
            ),
        ),
      );
    if (out.length === 2) out.push(el("p", { class: "empty" }, "Không có mục nào khớp."));
    return out;
  }

  // "Patch notes" | "Stat lookup" switch shown on both pages.
  function viewSwitch(active, set) {
    const has = dbSets().length > 0;
    return el(
      "nav",
      { class: "vswitch", "aria-label": "Chế độ xem" },
      el("a", { class: active === "notes" ? "is-on" : "", href: "#/tft" }, "📰 Bản cập nhật"),
      has && el("a", { class: active === "db" ? "is-on" : "", href: `#/tft/tra-cuu/${set || dbSets()[0]}` }, "📚 Tra cứu thông số"),
    );
  }

  // --- The page -------------------------------------------------------------

  function render(view, appData, version, options = {}) {
    document.title = "Cập nhật ĐTCL / TFT – GiftCode Finder";
    setTheme(GOLD);
    view.className = "wrap tftpage";
    view.removeAttribute("style");
    if (!appData.tft) {
      view.replaceChildren(
        el(
          "section",
          { class: "tft-hero" },
          el("div", {}, el("p", { class: "tft-kicker" }, "⚔️ Đấu Trường Chân Lý"), el("h1", { class: "tft-title" }, "Chưa có dữ liệu"), el("p", { class: "none" }, "Trang sẽ có bản cập nhật TFT sau lần quét tới (mỗi giờ).")),
          hexPrism("TFT"),
        ),
      );
      return;
    }
    summaryRef = appData.tft;
    if (!data) {
      view.replaceChildren(el("div", { class: "skeleton", "aria-label": "Đang tải" }, el("i"), el("i"), el("i")));
      load(appData.tft)
        .then(() => {
          if (location.hash.replace(/^#\/?/, "").startsWith("tft")) render(view, appData, version, options);
        })
        .catch((error) => {
          view.replaceChildren(el("p", { class: "empty" }, `Không tải được dữ liệu TFT: ${error.message}. `, el("a", { href: location.href, onclick: () => location.reload() }, "Thử lại")));
        });
      return;
    }
    const lookup = String(version || "").match(/^tra-cuu(?:\/(\d+))?$/);
    if (lookup) {
      renderDb(view, appData, lookup[1] ? Number(lookup[1]) : (data.patches[0] || {}).set);
      if (!options.keepScroll) window.scrollTo(0, 0);
      return;
    }
    const patches = data.patches || [];
    if (!patches.length) {
      view.replaceChildren(el("p", { class: "empty" }, "Chưa có bản cập nhật nào."));
      return;
    }
    const latest = patches[0].version;
    const patch = patches.find((p) => p.version === version) || patches[0];
    if (version && patch.version !== version) toast(`Không có bản ${version}, đang hiện bản ${patch.version}`);
    document.title = `ĐTCL ${patch.version} – Cập nhật TFT`;

    const body = el("div", { class: "tft-body" });
    let controls;
    const repaint = () => {
      const query = fold(state.query);
      if (controls) {
        for (const button of controls.node.querySelectorAll("[data-group]")) {
          const on = state[button.dataset.group] === button.dataset.value;
          button.classList.toggle("is-on", on);
          button.setAttribute("aria-pressed", String(on));
        }
        controls.wide.checked = state.wide;
      }
      for (const tile of view.querySelectorAll("[data-filter-dir]")) {
        const on = state.dir === tile.dataset.filterDir;
        tile.classList.toggle("is-on", on);
        tile.setAttribute("aria-pressed", String(on));
      }
      // The hotfix strip and the per-kind tiles follow the filters too.
      const strip = view.querySelector(".hf-wrap");
      if (strip) strip.replaceWith(hotfixLine(patch, latest));
      const sums = view.querySelector(".ksums");
      const fresh = kindSummary(patch);
      if (sums && fresh) sums.replaceWith(fresh);
      body.replaceChildren(...(state.wide && (query || state.kind !== "all" || state.dir !== "all") ? historyView(patches, patch, query) : sectionView(patch, query)));
    };
    controls = tools(patch, repaint);
    const pick = (name) => openSheet(patch.set, name);
    body.addEventListener("click", (event) => {
      const head = event.target.closest("[data-sheet]");
      if (head) openSheet(patch.set, head.dataset.sheet);
    });
    if (state.patch !== patch.version) {
      state.hotfix = "all"; // a new patch starts with all its changes
      state.patch = patch.version;
    }
    const flow = carousel(patches, patch, latest);
    const top = hero(patch, latest);
    const summaryTiles = kindSummary(patch);
    // One delegated handler on the shared view (replaced on every render, never stacked).
    if (view.tftClick) view.removeEventListener("click", view.tftClick);
    view.tftClick = (event) => {
      const fix = event.target.closest("[data-hotfix]");
      if (fix) {
        state.hotfix = state.hotfix === fix.dataset.hotfix ? "all" : fix.dataset.hotfix;
        repaint();
        return;
      }
      const sum = event.target.closest(".ksum");
      if (sum) {
        state.kind = state.kind === sum.dataset.value ? "all" : sum.dataset.value;
        repaint();
      }
    };
    view.addEventListener("click", view.tftClick);
    top.addEventListener("click", (event) => {
      const tile = event.target.closest("[data-filter-dir]");
      if (!tile || tile.disabled) return;
      state.dir = state.dir === tile.dataset.filterDir ? "all" : tile.dataset.filterDir;
      repaint();
    });
    const summary = appData.tft;
    const problems =
      summary.errors && summary.errors.length
        ? el("p", { class: "note", style: "margin-top:20px" }, `Lần kiểm tra gần nhất gặp lỗi: ${summary.errors.join(" · ")}`)
        : null;
    view.replaceChildren(
      top,
      viewSwitch("notes", patch.set),
      seasons(patches, patch),
      flow.wrap,
      summaryTiles,
      movers(patch, pick),
      controls.node,
      body,
      problems,
      el(
        "p",
        { class: "foot", style: "border:0;padding:8px 0 0" },
        "Nội dung từ bài patch notes chính thức của Riot Games; tên và biểu tượng từ Community Dragon. Tăng/giảm được xếp tự động theo con số (năng lượng, hồi chiêu, giá tiền giảm là tăng sức mạnh) nên vài dòng có thể chưa chuẩn — xem bài gốc khi cần.",
      ),
    );
    repaint();
    FX.pauseAway(top);
    const carouselCtl = FX.coverflow(flow.track);
    flow.wrap.querySelector(".prev").addEventListener("click", () => carouselCtl.step(-1));
    flow.wrap.querySelector(".next").addEventListener("click", () => carouselCtl.step(1));
    const selected = flow.track.querySelector(".is-on");
    if (selected) {
      // Again once fonts and the page transition have settled the layout.
      requestAnimationFrame(() => carouselCtl.center(selected, false));
      setTimeout(() => carouselCtl.center(selected, false), 400);
    }
    if (!options.keepScroll) window.scrollTo(0, 0);
  }

  // The home page card that leads here.
  function promo(summary) {
    if (!summary || !summary.latest) return null;
    const latest = summary.latest;
    const counts = latest.counts || {};
    return el(
      "section",
      { class: "tftp", "aria-label": "Cập nhật Đấu Trường Chân Lý" },
      el(
        "a",
        { class: "tftp-card", href: "#/tft" },
        el(
          "div",
          {},
          el("p", { class: "tftp-kicker" }, "⚔️ Mới · Cập nhật ĐTCL / TFT"),
          el("h2", { class: "tftp-title" }, "Bản ", el("span", { class: "ver" }, latest.version), latest.set_name ? ` · ${latest.set_name}` : ""),
          el("p", { class: "tftp-sub" }, `Tướng, tộc hệ, trang bị, nâng cấp nào được tăng hay bị giảm sức mạnh — xem theo từng bản, từng mùa (${summary.patches} bản).`),
          (latest.hotfixes || []).length > 0 &&
            el(
              "p",
              { class: "tftp-hf" },
              "⚡ Đã có bản vá ",
              el("b", {}, latest.hotfixes[latest.hotfixes.length - 1].label),
              latest.hotfixes[latest.hotfixes.length - 1].date ? ` · ${dayMonth(latest.hotfixes[latest.hotfixes.length - 1].date)}` : "",
              ` · ${latest.hotfixes[latest.hotfixes.length - 1].count} thay đổi`,
            ),
          el("div", { class: "dirs" }, ["buff", "nerf", "adjust"].filter((d) => counts[d]).map((d) => dpill(d, counts[d]))),
          el("span", { class: "tftp-cta" }, "Xem chi tiết ", el("i", { "aria-hidden": "true" }, "→")),
        ),
        hexPrism(latest.version),
      ),
    );
  }

  return { render, promo, load, openSheet };
})();
