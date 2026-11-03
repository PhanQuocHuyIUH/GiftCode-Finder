"use strict";

const NEW_FOR_MS = 72 * 3600 * 1000;
const SOON_MS = 7 * 86400 * 1000; // codes expiring sooner than this get their own strip
const LATEST_IN_BOX = 6;
const COPIED_KEY = "gcf:copied";
const HEX_COLOR = /^#(?:[0-9a-f]{3}){1,2}$/i;
const BRAND_COLOR = "#a855f7";

const store = {
  read() {
    try {
      return new Set(JSON.parse(localStorage.getItem(COPIED_KEY) || "[]"));
    } catch {
      return new Set();
    }
  },
  write(set) {
    try {
      localStorage.setItem(COPIED_KEY, JSON.stringify([...set]));
    } catch {
      /* private mode: copy still works, it just is not remembered */
    }
  },
};
let copied = store.read();

// Build DOM with textContent only: scraped text must never become HTML.
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

const timeFmt = new Intl.DateTimeFormat("vi-VN", {
  hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit", year: "numeric",
});
const dayFmt = new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
const clockFmt = new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit" });
const relFmt = new Intl.RelativeTimeFormat("vi", { numeric: "auto" });

function ago(iso) {
  const diff = (new Date(iso) - Date.now()) / 1000;
  const steps = [[60, "second"], [3600, "minute"], [86400, "hour"], [Infinity, "day"]];
  let unit = 1;
  for (const [limit, name] of steps) {
    if (Math.abs(diff) < limit) return relFmt.format(Math.round(diff / unit), name);
    unit = limit;
  }
  return "";
}

function stamp(iso) {
  return iso ? `${timeFmt.format(new Date(iso))} (${ago(iso)})` : "—";
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = el("textarea", { readonly: true, style: "position:fixed;opacity:0" });
    area.value = text;
    document.body.append(area);
    area.select();
    const ok = document.execCommand("copy");
    area.remove();
    return ok;
  }
}

let toastTimer;
function toast(message) {
  const box = document.getElementById("toast");
  box.textContent = message;
  box.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => box.classList.remove("show"), 1600);
}

function isNew(item) {
  return Date.now() - new Date(item.first_seen) < NEW_FOR_MS;
}

function badge(item) {
  return isNew(item) && el("span", { class: "badge" }, "MỚI");
}

// Time left before ``iso``; tick() refreshes every countdown each second.
function remaining(iso) {
  const left = Math.floor((new Date(iso) - Date.now()) / 1000);
  if (left <= 0) return { text: "Đã hết hạn", level: "expired" };
  const days = Math.floor(left / 86400);
  const hours = Math.floor((left % 86400) / 3600);
  if (days >= 7) return { text: `Còn ${days} ngày`, level: "ok" };
  if (days >= 1) return { text: `Còn ${days} ngày ${hours} giờ`, level: days < 3 ? "soon" : "ok" };
  const pad = (n) => String(n).padStart(2, "0");
  return { text: `Còn ${pad(hours)}:${pad(Math.floor((left % 3600) / 60))}:${pad(left % 60)}`, level: "urgent" };
}

const narrow = window.matchMedia("(max-width: 560px)");

function tick() {
  for (const node of document.querySelectorAll("[data-expires]")) {
    const { text, level } = remaining(node.dataset.expires);
    const end = new Date(node.dataset.expires);
    const until = level === "urgent" ? `hết hạn lúc ${clockFmt.format(end)}` : `HSD ${dayFmt.format(end)}`;
    // Compact countdowns (cards, chips, phones) leave out the date.
    const compact = level === "expired" || "compact" in node.dataset || narrow.matches;
    node.textContent = compact ? `⏳ ${text}` : `⏳ ${text} · ${until}`;
    node.dataset.level = level;
    if (compact && level !== "expired") node.title = until;
  }
}

// --- Games ---------------------------------------------------------------

function codesOf(game) {
  return (game.items || []).filter((i) => i.code);
}

// The game's colors from the config, or three derived from its id.
function colorsOf(game) {
  const own = (game.colors || []).filter((c) => HEX_COLOR.test(c));
  if (own.length) return [own[0], own[1] || own[0], own[2] || own[1] || own[0]];
  let hash = 0;
  for (const ch of game.id) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  const hue = hash % 360;
  return [`hsl(${hue} 85% 58%)`, `hsl(${(hue + 55) % 360} 80% 52%)`, `hsl(${(hue + 170) % 360} 90% 66%)`];
}

function themeStyle(game) {
  const [c1, c2, c3] = colorsOf(game);
  return `--c1:${c1};--c2:${c2};--c3:${c3}`;
}

// The page glow takes the color of the game on screen.
function setTheme(game) {
  const color = typeof game === "string" ? game : game ? colorsOf(game)[0] : BRAND_COLOR;
  document.documentElement.style.setProperty("--b1", color);
}

function soonestExpiry(items) {
  const now = new Date().toISOString();
  return items
    .filter((i) => i.expires_at && i.expires_at > now)
    .sort((a, b) => a.expires_at.localeCompare(b.expires_at))[0];
}

function expiringSoon(data) {
  const now = Date.now();
  return data.games
    .flatMap((game) => codesOf(game).map((item) => ({ game, item })))
    .filter(({ item }) => item.expires_at && new Date(item.expires_at) - now > 0 && new Date(item.expires_at) - now < SOON_MS)
    .sort((a, b) => a.item.expires_at.localeCompare(b.item.expires_at));
}

function latestCodes(data, count) {
  return data.games
    .flatMap((game) => codesOf(game).map((item) => ({ game, item })))
    .sort((a, b) => b.item.first_seen.localeCompare(a.item.first_seen) || (b.item.since || "").localeCompare(a.item.since || ""))
    .slice(0, count);
}

function center(node) {
  const box = node.getBoundingClientRect();
  return [box.left + box.width / 2, box.top + box.height / 2];
}

async function copyCode(game, code, event) {
  const source = event && event.currentTarget; // gone once the copy is awaited
  if (!(await copyText(code))) {
    toast("Không sao chép được, hãy chọn và copy tay");
    return false;
  }
  copied.add(`${game.id}:${code}`);
  store.write(copied);
  toast(`Đã sao chép ${code}`);
  // Keyboard clicks have no pointer position: burst from the element instead.
  if (event && (event.clientX || event.clientY)) FX.burst(event.clientX, event.clientY, [...colorsOf(game), "#ffffff"]);
  else if (source) FX.burst(...center(source), [...colorsOf(game), "#ffffff"]);
  return true;
}

// The countdown (or the raw expiry text); without one, when it was first seen.
function metaLine(item) {
  if (item.expires_at) return el("span", { class: "code-meta" }, el("span", { class: "expiry", "data-expires": item.expires_at }));
  if (item.expires) return el("span", { class: "code-meta" }, el("span", { class: "expiry" }, `⏳ HSD ${item.expires}`));
  const seen = new Date(item.first_seen);
  const day = `${String(seen.getDate()).padStart(2, "0")}/${String(seen.getMonth() + 1).padStart(2, "0")}`;
  return el("span", { class: "code-meta" }, `thấy lần đầu ${day}`);
}

function codeRow(game, item) {
  const key = `${game.id}:${item.code}`;
  const info = [item.title !== item.code && item.title, item.reward].filter(Boolean).join(" · ");
  const action = el("span", { class: "code-action" }, copied.has(key) ? "✓ Đã chép" : "Sao chép");
  const button = el(
    "button",
    {
      type: "button",
      class: `code${copied.has(key) ? " copied" : ""}`,
      title: "Bấm để sao chép",
      onclick: async (event) => {
        if (!(await copyCode(game, item.code, event))) return;
        button.classList.add("copied");
        action.textContent = "✓ Đã chép";
        button.classList.remove("flip");
        void button.offsetWidth; // restart the flip
        button.classList.add("flip");
      },
    },
    el("span", { class: "code-stub", "aria-hidden": "true" }, "🎟️"),
    el(
      "span",
      { class: "code-main" },
      el("span", { class: "code-value" }, item.code, badge(item)),
      info && el("span", { class: "code-info" }, info),
      metaLine(item),
    ),
    action,
  );
  return el("li", {}, button);
}

// A giftcode the source lists without its value (it needs a login there).
function lockedRow(item) {
  return el(
    "li",
    {},
    el(
      "a",
      { class: "code locked", href: item.link, target: "_blank", rel: "noopener" },
      el(
        "span",
        { class: "code-main" },
        el("span", { class: "locked-title" }, "🔒 ", item.title || "Sự kiện giftcode", badge(item)),
        el("span", { class: "code-info" }, [item.reward, "đăng nhập trang nguồn để xem mã"].filter(Boolean).join(" · ")),
        metaLine(item),
      ),
      el("span", { class: "code-action" }, "Nhận code ↗"),
    ),
  );
}

function oldRow(code) {
  return el(
    "li",
    {},
    el(
      "div",
      { class: "code" },
      el(
        "span",
        { class: "code-main" },
        el("span", { class: "code-value" }, code.code),
        el("span", { class: "code-info" }, `gỡ khỏi trang nguồn ${dayFmt.format(new Date(code.removed_at))}`),
      ),
    ),
  );
}

function sourceLine(source) {
  const link = el("a", { href: source.url, target: "_blank", rel: "noopener" }, source.name);
  if (source.ok === null) return el("li", { class: "src" }, el("i", { class: "dot" }), link, el("small", {}, "chưa quét"));
  if (!source.ok) {
    return el("li", { class: "src bad" }, el("i", { class: "dot" }), link, el("small", {}, `lỗi: ${source.error}`));
  }
  const locked = source.hidden ? ` · ${source.hidden} cần đăng nhập` : "";
  return el(
    "li",
    { class: "src ok" },
    el("i", { class: "dot" }),
    link,
    el("small", {}, `${source.count} code${locked} · kiểm tra ${ago(source.checked_at)}`),
  );
}

// A section heading with its icon on a small 3D tile.
function heading(icon, text, tone = "violet", extra = "") {
  return el("h2", { class: `section-title ${extra}`.trim() }, el("span", { class: `st-ico tone-${tone}`, "aria-hidden": "true" }, icon), el("span", {}, text));
}

// A CSS cube showing ``label`` on its sides (game badge on cards and pages).
function labelCube(label, size = "") {
  return el(
    "span",
    { class: `lcube ${size}`, "aria-hidden": "true" },
    el("span", { class: "lcube-in" }, ["f", "b", "r", "l", "t", "d"].map((side) => el("i", { class: `lc-${side}` }, side === "t" || side === "d" ? "🎁" : label))),
  );
}

function initials(name) {
  return name.split(/\s+/).filter(Boolean).map((word) => word[0]).join("").slice(0, 2).toUpperCase() || "?";
}

// The game's initials in its colors: its badge on its page.
function monogram(game, size = "") {
  return el("span", { class: `mono ${size}`, style: `view-transition-name: mono-${game.id}`, "aria-hidden": "true" }, initials(game.name));
}

function countText(game) {
  const items = game.items || [];
  const codes = codesOf(game).length;
  const locked = items.length - codes;
  return `${codes} code${locked ? ` · 🔒 ${locked}` : ""}`;
}

// --- Home: pick a game ----------------------------------------------------

function intro(data, soonCount) {
  const codeCount = data.games.reduce((n, game) => n + codesOf(game).length, 0);
  const stat = (value, label, tone = "") => {
    const number = el("b", {}, value);
    FX.countUp(number, value);
    return el("div", { class: `stat ${tone}` }, number, el("span", {}, label));
  };
  return el(
    "section",
    { class: "intro" },
    el("p", { class: "live" }, el("i", { class: "live-dot" }), `Tự cập nhật mỗi giờ · kiểm tra ${ago(data.generated_at)}`),
    el("h1", { class: "intro-title" }, "Giftcode mới nhất,", el("br"), el("span", { class: "accent" }, "bấm là chép.")),
    el("p", { class: "intro-sub" }, "Chọn game để xem code, mở hộp quà để lấy code mới nhất. Code livestream có đồng hồ đếm ngược hạn dùng."),
    el(
      "div",
      { class: "stats" },
      stat(codeCount, "code đang dùng được"),
      stat(data.games.length, "game", "cyan"),
      soonCount > 0 && stat(soonCount, "sắp hết hạn", "warn"),
    ),
  );
}

function soonStrip(entries) {
  return el(
    "section",
    { class: "soon", "aria-label": "Code sắp hết hạn" },
    heading("🔥", "Sắp hết hạn — chép ngay kẻo lỡ", "hot"),
    el(
      "div",
      { class: "soon-list" },
      entries.map(({ game, item }) =>
        el(
          "button",
          {
            type: "button",
            class: "soon-item",
            style: themeStyle(game),
            title: "Bấm để sao chép",
            onclick: (event) => copyCode(game, item.code, event),
          },
          el("b", {}, item.code),
          el("span", { class: "soon-meta" }, `${game.name} · `, el("span", { class: "expiry", "data-expires": item.expires_at, "data-compact": "" })),
          el("span", { class: "soon-ico", "aria-hidden": "true" }, "⏳"),
        ),
      ),
    ),
  );
}

function gameTile(game, index) {
  const items = game.items || [];
  const newest = items[0];
  const next = soonestExpiry(items);
  const codes = codesOf(game).length;
  const locked = items.length - codes;
  const search = [game.name, ...items.map((i) => i.code || i.title || "")].join(" ").toLowerCase();
  return el(
    "a",
    {
      class: "gcard",
      href: `#/${encodeURIComponent(game.id)}`,
      style: `${themeStyle(game)};--i:${index}`,
      "data-search": search,
      "aria-label": `${game.name}: ${codes} code`,
    },
    el("span", { class: "gcard-pattern", "aria-hidden": "true" }),
    el("span", { class: "gcard-art", "aria-hidden": "true" }, initials(game.name)),
    labelCube(initials(game.name)),
    el(
      "span",
      { class: "gcard-head" },
      el("span", { class: "gcard-count" }, el("b", {}, codes), locked ? `code · 🔒 ${locked}` : "code"),
      items.some(isNew) && el("span", { class: "badge" }, "MỚI"),
      el("span", { class: "gcard-go", "aria-hidden": "true" }, "→"),
    ),
    el("h3", { class: "gcard-title" }, game.name),
    newest &&
      el(
        "p",
        { class: "gcard-latest" },
        "Mới nhất ",
        newest.code ? el("b", {}, newest.code) : `🔒 ${newest.title || "sự kiện mới"}`,
        ` · ${ago(newest.first_seen)}`,
      ),
    next && el("p", { class: "gcard-expiry" }, el("span", { class: "expiry", "data-expires": next.expires_at, "data-compact": "" })),
  );
}

function picker(data, first) {
  const cards = data.games.map(gameTile);
  const empty = el("p", { class: "empty" }, "Không có game nào khớp.");
  empty.hidden = true;
  const search =
    cards.length > 3 &&
    el("input", {
      class: "search",
      type: "search",
      placeholder: "Tìm game hoặc code…",
      autocomplete: "off",
      oninput: (event) => {
        const query = event.target.value.trim().toLowerCase();
        let shown = 0;
        for (const card of cards) {
          card.hidden = Boolean(query) && !card.dataset.search.includes(query);
          if (!card.hidden) shown += 1;
        }
        empty.hidden = shown > 0;
      },
    });
  return el(
    "section",
    { class: `picker${first ? " is-first" : ""}`, id: "chon-game" },
    heading("🎮", "Chọn game", "cyan"),
    search,
    cards.length ? el("div", { class: "gcards" }, cards) : el("p", { class: "empty" }, "Chưa có game nào trong cấu hình."),
    empty,
  );
}

function giftScene(latest, games = []) {
  const faces = () => ["front", "back", "right", "left", "top", "bottom"].map((side) => el("span", { class: `face f-${side}` }));
  const bow = (plane) =>
    el("span", { class: `bow ${plane}` }, el("span", { class: "loop l" }), el("span", { class: "loop r" }), el("span", { class: "knot" }));
  const chips = latest.map(({ game, item }) =>
    el(
      "button",
      {
        type: "button",
        class: "chip",
        style: themeStyle(game),
        "aria-label": `Sao chép ${item.code} (${game.name})`,
        onclick: (event) => copyCode(game, item.code, event),
      },
      el("b", {}, item.code),
      el("small", {}, game.name),
    ),
  );
  return el(
    "section",
    { class: "gift", "aria-label": "Hộp quà code mới nhất" },
    heading("🎁", "Hộp quà code mới", "pink", "gift-title"),
    el(
      "div",
      { class: "gift-area" },
      el("span", { class: "gift-ring", "aria-hidden": "true" }),
      el(
        "span",
        { class: "orbit", "aria-hidden": "true" },
        el(
          "span",
          { class: "orbit-in" },
          ["#ffc94d", "#ff4fd8", "#22d3ee", "#b18cff", "#ffc94d", "#34d399", "#ff4fd8", "#22d3ee"].map((c, k) => el("i", { style: `--k:${k};--c:${c}` })),
          // Every game circles the box as a little planet with its initials.
          games.slice(0, 4).map((game, k) => el("b", { class: "planet", style: `${themeStyle(game)};--k:${k};--n:${Math.min(games.length, 4)}` }, initials(game.name))),
        ),
      ),
      el("span", { class: "gift-glow", "aria-hidden": "true" }),
      el("span", { class: "beams", "aria-hidden": "true" }, [0, 1, 2, 3, 4, 5].map((k) => el("i", { style: `--k:${k}` }))),
      el(
        "div",
        { class: "box-pos", "aria-hidden": "true" },
        el(
          "div",
          { class: "box-turn" },
          el(
            "div",
            { class: "box-spin" },
            el("div", { class: "box" }, el("div", { class: "cube base" }, faces()), el("div", { class: "cube lid" }, faces(), bow("b1"), bow("b2"))),
          ),
        ),
      ),
      el("div", {
        class: "box-hit",
        role: "button",
        tabindex: "0",
        "aria-expanded": "false",
        "aria-label": latest.length ? "Mở hộp quà xem các code mới nhất" : "Hộp quà",
      }),
    ),
    el("p", { class: "gift-hint" }, latest.length ? "Kéo để xoay · chạm để mở hộp" : "Kéo để xoay hộp quà"),
    el("div", { class: "gift-chips" }, chips),
  );
}

// A strip of the newest codes (and the TFT patch) running across the page.
function ticker(data) {
  const items = latestCodes(data, 12).map(({ game, item }) =>
    el("span", { class: "tk-item", style: themeStyle(game) }, el("i", { class: "tk-dot" }), el("b", {}, item.code), el("small", {}, game.name)),
  );
  const tft = data.tft && data.tft.latest;
  if (tft) {
    const counts = tft.counts || {};
    items.unshift(el("span", { class: "tk-item tk-gold" }, "⚔️ ĐTCL ", el("b", {}, tft.version), el("small", {}, `▲${counts.buff || 0} ▼${counts.nerf || 0}`)));
  }
  items.push(el("span", { class: "tk-item" }, "⏱ ", el("small", {}, "tự cập nhật mỗi giờ")));
  if (items.length < 2) return null;
  const run = () => el("div", { class: "tk-run" }, items.map((node) => node.cloneNode(true)));
  return el("div", { class: "ticker", "aria-hidden": "true" }, el("div", { class: "tk-track" }, run(), run()));
}

function steps() {
  const list = [
    ["1", "Chọn game", "Mỗi game có trang riêng — lưu ra màn hình chính điện thoại để mở nhanh.", "pink"],
    ["2", "Bấm vào code", "Code được chép ngay (kèm pháo giấy 🎉). Code đã chép được đánh dấu.", "cyan"],
    ["3", "Nhập trong game", "Xem mục “Cách nhập code” ở trang game. Code livestream có đếm ngược.", "gold"],
  ];
  return el(
    "section",
    { class: "steps" },
    heading("✨", "Dùng thế nào?", "gold"),
    el(
      "div",
      { class: "steps-grid" },
      list.map(([n, title, text, tone]) => el("div", { class: `step tone-${tone}` }, el("span", { class: "step-n" }, n), el("h3", {}, title), el("p", {}, text))),
    ),
  );
}

function renderHome(data, first) {
  document.title = "GiftCode Finder – Chọn game";
  setTheme(null);
  const soon = expiringSoon(data);
  const view = document.getElementById("view");
  view.className = "wrap home";
  view.removeAttribute("style");
  view.replaceChildren(
    ...[
      ticker(data),
      intro(data, soon.length),
      soon.length > 0 && soonStrip(soon),
      picker(data, first),
      TFT.promo(data.tft),
      giftScene(latestCodes(data, LATEST_IN_BOX), data.games),
      steps(),
    ].filter(Boolean),
  );
  FX.giftBox(view.querySelector(".gift"));
  FX.reveal(view.querySelectorAll(".soon, .picker, .tftp, .steps, .gift"));
  view.querySelectorAll(".gcard").forEach(FX.tilt);
  const promo = view.querySelector(".tftp-card");
  if (promo) FX.pauseAway(promo);
}

// --- Game page ------------------------------------------------------------

function renderGame(data, game) {
  document.title = `${game.name} – GiftCode Finder`;
  setTheme(game);
  const items = game.items || [];
  const codes = codesOf(game);
  const old = game.old || [];
  const copyAll =
    codes.length > 1 &&
    el(
      "button",
      {
        type: "button",
        class: "btn btn-primary",
        onclick: async (event) => {
          const button = event.currentTarget;
          if (!(await copyText(codes.map((c) => c.code).join("\n")))) return toast("Không sao chép được");
          toast(`Đã sao chép ${codes.length} code`);
          FX.burst(...center(button), colorsOf(game));
        },
      },
      `Sao chép cả ${codes.length} code`,
    );
  const guide =
    game.redeem_url && el("a", { class: "btn btn-ghost", href: game.redeem_url, target: "_blank", rel: "noopener" }, "Hướng dẫn nhập ↗");
  const head = el(
    "header",
    { class: "ghead" },
    el("span", { class: "ghead-pattern", "aria-hidden": "true" }),
    el("span", { class: "ghead-art", "aria-hidden": "true" }, initials(game.name)),
    labelCube(initials(game.name), "lcube-lg"),
    el(
      "div",
      { class: "ghead-main" },
      monogram(game, "mono-lg"),
      el(
        "div",
        { class: "ghead-text" },
        el("h1", { class: "ghead-title" }, game.name),
        el("p", { class: "ghead-meta" }, `${countText(game)} · kiểm tra ${ago(data.generated_at)}`),
      ),
    ),
    (copyAll || guide) && el("div", { class: "ghead-actions" }, copyAll, guide),
  );
  const list = el(
    "section",
    { class: "gmain" },
    heading("🎟️", "Code đang dùng được", "pink"),
    items.length
      ? el("ul", { class: "codes" }, items.map((i, n) => {
          const row = i.code ? codeRow(game, i) : lockedRow(i);
          row.style.setProperty("--i", n);
          return row;
        }))
      : el("p", { class: "none" }, "Chưa có code nào đang hoạt động — trang tự kiểm tra lại mỗi giờ."),
  );
  const side = el(
    "aside",
    { class: "gside" },
    game.redeem_note &&
      el("section", { class: "panel tone-gold" }, el("h2", { class: "panel-title" }, "📝 Cách nhập code"), el("p", { class: "redeem" }, game.redeem_note)),
    el("section", { class: "panel tone-cyan" }, el("h2", { class: "panel-title" }, "📡 Nguồn"), el("ul", { class: "sources" }, game.sources.map(sourceLine))),
    old.length > 0 &&
      el(
        "details",
        { class: "panel old" },
        el("summary", {}, `Code không còn trên trang nguồn (${old.length})`),
        el("ul", { class: "codes" }, old.map(oldRow)),
      ),
  );
  const view = document.getElementById("view");
  view.className = "wrap gpage";
  view.setAttribute("style", themeStyle(game));
  view.replaceChildren(el("nav", { class: "crumbs" }, el("a", { class: "back", href: "#/" }, "← Chọn game khác")), head, el("div", { class: "glayout" }, list, side));
  FX.tilt(head);
}

// --- Routing ----------------------------------------------------------------
// #/<game id> shows a game, #/tft (or #/tft/<patch>) the TFT patch notes,
// anything else the home page.

let DATA = null;
let shown; // what is on screen: "home", "game:<id>", "tft:<patch>"
let homeScroll = 0;

function route() {
  let path;
  try {
    path = decodeURIComponent(location.hash.replace(/^#\/?/, ""));
  } catch {
    return { key: "home" }; // a mangled link: show the home page
  }
  const tft = path.match(/^tft(?:\/(.+))?$/);
  if (tft) return { key: `tft:${tft[1] || ""}`, tft: tft[1] || "" };
  const game = DATA.games.find((g) => g.id === path);
  return game ? { key: `game:${game.id}`, game } : { key: "home" };
}

function markNav(key) {
  const section = key.startsWith("tft") ? "tft" : "home";
  for (const link of document.querySelectorAll("[data-nav]")) {
    link.classList.toggle("is-active", link.dataset.nav === section);
    if (link.dataset.nav === section) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}

function show(animate = true) {
  const where = route();
  if (where.key === shown) return;
  if (shown === "home") homeScroll = window.scrollY;
  const first = shown === undefined;
  const sameTft = shown && shown.startsWith("tft:") && where.key.startsWith("tft:");
  shown = where.key;
  markNav(where.key);
  const update = () => {
    if (where.game) {
      renderGame(DATA, where.game);
      window.scrollTo(0, 0);
    } else if (where.tft !== undefined) {
      TFT.render(document.getElementById("view"), DATA, where.tft, { keepScroll: sameTft });
      if (!sameTft) window.scrollTo(0, 0);
    } else {
      renderHome(DATA, first);
      window.scrollTo(0, homeScroll);
    }
    tick();
  };
  // Switching patches inside the TFT page swaps content in place.
  if (animate && !sameTft) FX.transition(update);
  else update();
}

function chrome(data) {
  document.getElementById("meta").replaceChildren(
    data.workflow_url ? el("a", { class: "rescan", href: data.workflow_url, target: "_blank", rel: "noopener" }, "↻ Quét lại ngay") : "",
  );
  document.getElementById("foot").replaceChildren(
    el("p", {}, `Kiểm tra lúc ${stamp(data.generated_at)} · code đổi lần cuối ${stamp(data.updated_at)}.`),
    el("p", {}, "Trang tự cập nhật mỗi giờ bằng GitHub Actions."),
    el(
      "p",
      {},
      el("a", { href: "codes.json" }, "Dữ liệu JSON"),
      data.repo_url ? " · " : "",
      data.repo_url ? el("a", { href: data.repo_url, target: "_blank", rel: "noopener" }, "Mã nguồn & cấu hình") : "",
    ),
  );
}

function start(data) {
  DATA = data;
  chrome(data);
  FX.scene();
  show(false);
  setInterval(tick, 1000);
  window.addEventListener("hashchange", () => show());
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && shown !== "home" && !document.querySelector("dialog[open]")) location.hash = "#/";
  });
}

async function load() {
  const embedded = document.getElementById("gcf-data").textContent.trim();
  if (embedded && !embedded.startsWith("__")) return JSON.parse(embedded);
  const response = await fetch("codes.json", { cache: "no-store" });
  return response.json();
}

load()
  .then(start)
  .catch((err) => {
    document.getElementById("meta").textContent = `Không tải được dữ liệu: ${err.message}`;
  });
