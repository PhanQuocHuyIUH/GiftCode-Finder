"use strict";

const NEW_FOR_MS = 72 * 3600 * 1000;
const SOON_MS = 7 * 86400 * 1000; // codes expiring sooner than this get their own strip
const LATEST_COUNT = 6;
const COPIED_KEY = "gcf:copied";
const HEX_COLOR = /^#(?:[0-9a-f]{3}){1,2}$/i;

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
  for (const child of children.flat(Infinity)) {
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
  return isNew(item) && el("span", { class: "badge" }, "Mới");
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
    node.textContent = compact ? text : `${text} · ${until}`;
    node.dataset.level = level;
    if (compact && level !== "expired") node.title = until;
  }
}

// --- Games ---------------------------------------------------------------

// A code past its expiry is still listed by its source for a while.
function isLive(item) {
  return !item.expires_at || new Date(item.expires_at) > Date.now();
}

// The codes that can still be redeemed.
function codesOf(game) {
  return (game.items || []).filter((i) => i.code && isLive(i));
}

// The game's own color (from the config, or derived from its id): the one
// place a game brings its color is its monogram.
function colorOf(game) {
  const own = (game.colors || []).find((c) => HEX_COLOR.test(c));
  if (own) return own;
  let hash = 0;
  for (const ch of game.id) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return `hsl(${hash % 360} 55% 50%)`;
}

function initials(name) {
  return name.split(/\s+/).filter(Boolean).map((word) => word[0]).join("").slice(0, 2).toUpperCase() || "?";
}

function monogram(game, size = "") {
  return el("span", { class: `mono ${size}`.trim(), style: `--game:${colorOf(game)}`, "aria-hidden": "true" }, initials(game.name));
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

async function copyCode(game, code) {
  if (!(await copyText(code))) {
    toast("Không sao chép được, hãy chọn và copy tay");
    return false;
  }
  copied.add(`${game.id}:${code}`);
  store.write(copied);
  toast(`Đã sao chép ${code}`);
  return true;
}

// The countdown (or the raw expiry text); without one, when it was first seen.
// On pages that mix games, the game's name comes first.
function metaLine(item, game) {
  const from = game && el("span", { class: "code-game" }, game.name);
  if (item.expires_at) return el("span", { class: "code-meta" }, from, el("span", { class: "expiry", "data-expires": item.expires_at }));
  if (item.expires) return el("span", { class: "code-meta" }, from, el("span", { class: "expiry" }, `HSD ${item.expires}`));
  const seen = new Date(item.first_seen);
  const day = `${String(seen.getDate()).padStart(2, "0")}/${String(seen.getMonth() + 1).padStart(2, "0")}`;
  return el("span", { class: "code-meta" }, from, el("span", {}, `thấy lần đầu ${day}`));
}

function codeRow(game, item, withGame = false) {
  const key = `${game.id}:${item.code}`;
  const info = [item.title !== item.code && item.title, item.reward].filter(Boolean).join(" · ");
  const action = el("span", { class: "code-action" }, copied.has(key) ? "Đã chép" : "Sao chép");
  const button = el(
    "button",
    {
      type: "button",
      class: `code${copied.has(key) ? " copied" : ""}`,
      title: "Bấm để sao chép",
      onclick: async () => {
        if (!(await copyCode(game, item.code))) return;
        button.classList.add("copied");
        action.textContent = "Đã chép";
      },
    },
    el(
      "span",
      { class: "code-main" },
      el("span", { class: "code-value" }, item.code, badge(item)),
      info && el("span", { class: "code-info" }, info),
      metaLine(item, withGame && game),
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
        el("span", { class: "locked-title" }, item.title || "Sự kiện giftcode", badge(item)),
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
      { class: "code is-old" },
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

// One region of a page: a title (with an optional note beside it) over its content.
function region(title, aside, body, extra = "") {
  return el(
    "section",
    { class: `region ${extra}`.trim() },
    el("div", { class: "region-head" }, el("h2", {}, title), aside && el("span", {}, aside)),
    body,
  );
}

function panel(title, body, extra = "") {
  return el("section", { class: `panel ${extra}`.trim() }, el("h2", { class: "panel-title" }, title), body);
}

function countText(game) {
  const items = game.items || [];
  const codes = codesOf(game).length;
  const locked = items.filter((i) => !i.code).length;
  return `${codes} code${locked ? ` · ${locked} cần đăng nhập` : ""}`;
}

// --- Home ------------------------------------------------------------------

function pageHead(data, soonCount) {
  const codeCount = data.games.reduce((n, game) => n + codesOf(game).length, 0);
  const fact = (value, label, tone = "") => el("div", { class: `fact ${tone}`.trim() }, el("b", {}, value), el("span", {}, label));
  return el(
    "header",
    { class: "pagehead" },
    el(
      "div",
      { class: "pagehead-text" },
      el("h1", {}, "Giftcode mới nhất"),
      el("p", {}, `Bấm vào code để sao chép. Trang tự kiểm tra các nguồn, lần gần nhất ${ago(data.generated_at)}.`),
    ),
    el(
      "div",
      { class: "facts" },
      fact(codeCount, "code đang dùng được"),
      fact(data.games.length, "game"),
      soonCount > 0 && fact(soonCount, "sắp hết hạn", "is-warn"),
    ),
  );
}

function gameCard(game) {
  const items = game.items || [];
  const newest = items.find(isLive);
  const next = soonestExpiry(items);
  const search = [game.name, ...items.map((i) => i.code || i.title || "")].join(" ").toLowerCase();
  return el(
    "a",
    { class: "gcard", href: `#/${encodeURIComponent(game.id)}`, "data-search": search, "aria-label": `${game.name}: ${countText(game)}` },
    monogram(game),
    el(
      "span",
      { class: "gcard-body" },
      el("b", { class: "gcard-title" }, game.name, items.some(isNew) && el("span", { class: "badge" }, "Mới")),
      el("span", { class: "gcard-meta" }, countText(game), newest ? ` · mới nhất ${ago(newest.first_seen)}` : ""),
      next && el("span", { class: "gcard-meta" }, "Hạn gần nhất: ", el("span", { class: "expiry", "data-expires": next.expires_at, "data-compact": "" })),
    ),
    el("span", { class: "gcard-go", "aria-hidden": "true" }, "→"),
  );
}

function gamePicker(data) {
  const cards = data.games.map(gameCard);
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
  return region("Chọn game", `${cards.length} game`, [
    search,
    cards.length ? el("div", { class: "gcards" }, cards) : el("p", { class: "empty" }, "Chưa có game nào trong cấu hình."),
    empty,
  ]);
}

function howTo() {
  const steps = [
    ["Chọn game", "Mỗi game có trang riêng với đủ code và cách nhập."],
    ["Bấm vào code", "Code được chép ngay và được đánh dấu đã chép."],
    ["Nhập trong game", "Code có hạn dùng sẽ kèm đồng hồ đếm ngược."],
  ];
  return panel("Cách dùng", el("ol", { class: "howto" }, steps.map(([title, text]) => el("li", {}, el("b", {}, title), el("span", {}, text)))));
}

function renderHome(data) {
  document.title = "GiftCode Finder – Chọn game";
  const soon = expiringSoon(data);
  const latest = latestCodes(data, LATEST_COUNT);
  const view = document.getElementById("view");
  view.className = "wrap home";
  view.replaceChildren(
    ...[
      pageHead(data, soon.length),
      soon.length > 0 &&
        region("Sắp hết hạn", "chép trước khi hết hạn", el("ul", { class: "codes" }, soon.map(({ game, item }) => codeRow(game, item, true))), "is-warn"),
      gamePicker(data),
      el(
        "div",
        { class: "split" },
        region(
          "Code mới nhất",
          latest.length ? `${latest.length} code gần đây` : "",
          latest.length
            ? el("ul", { class: "codes" }, latest.map(({ game, item }) => codeRow(game, item, true)))
            : el("p", { class: "none" }, "Chưa có code nào đang hoạt động."),
        ),
        el("aside", { class: "aside" }, TFT.promo(data.tft), howTo()),
      ),
    ].filter(Boolean),
  );
}

// --- Game page ------------------------------------------------------------

function renderGame(data, game) {
  document.title = `${game.name} – GiftCode Finder`;
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
        onclick: async () => {
          if (!(await copyText(codes.map((c) => c.code).join("\n")))) return toast("Không sao chép được");
          toast(`Đã sao chép ${codes.length} code`);
        },
      },
      `Sao chép cả ${codes.length} code`,
    );
  const guide = game.redeem_url && el("a", { class: "btn", href: game.redeem_url, target: "_blank", rel: "noopener" }, "Hướng dẫn nhập ↗");
  const head = el(
    "header",
    { class: "ghead" },
    monogram(game, "mono-lg"),
    el(
      "div",
      { class: "ghead-text" },
      el("h1", {}, game.name),
      el("p", {}, `${countText(game)} · kiểm tra ${ago(data.generated_at)}`),
    ),
    (copyAll || guide) && el("div", { class: "ghead-actions" }, copyAll, guide),
  );
  const live = items.filter(isLive);
  const expired = items.filter((i) => !isLive(i));
  const rows = (list) => el("ul", { class: "codes" }, list.map((i) => (i.code ? codeRow(game, i) : lockedRow(i))));
  const list = el(
    "div",
    { class: "stack" },
    region(
      "Code đang dùng được",
      live.length ? `${live.length} mục` : "",
      live.length ? rows(live) : el("p", { class: "none" }, "Chưa có code nào đang hoạt động — trang tự kiểm tra lại định kỳ."),
    ),
    expired.length > 0 && region("Đã hết hạn", "trang nguồn vẫn còn liệt kê", rows(expired), "is-past"),
  );
  const side = el(
    "aside",
    { class: "aside" },
    game.redeem_note && panel("Cách nhập code", el("p", { class: "redeem" }, game.redeem_note)),
    panel("Nguồn", el("ul", { class: "sources" }, game.sources.map(sourceLine))),
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
  view.replaceChildren(el("nav", { class: "crumbs" }, el("a", { class: "back", href: "#/" }, "← Tất cả game")), head, el("div", { class: "split" }, list, side));
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
      renderHome(DATA);
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
    data.workflow_url ? el("a", { class: "rescan", href: data.workflow_url, target: "_blank", rel: "noopener" }, "Quét lại ngay ↻") : "",
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
