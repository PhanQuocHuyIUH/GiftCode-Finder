"use strict";

const NEW_FOR_MS = 72 * 3600 * 1000;
const COPIED_KEY = "gcf:copied";

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

function tick() {
  for (const node of document.querySelectorAll("[data-expires]")) {
    const { text, level } = remaining(node.dataset.expires);
    const end = new Date(node.dataset.expires);
    const until = level === "urgent" ? `hết hạn lúc ${clockFmt.format(end)}` : `HSD ${dayFmt.format(end)}`;
    node.textContent = level === "expired" ? `⏳ ${text}` : `⏳ ${text} · ${until}`;
    node.dataset.level = level;
  }
}

// Countdown (or the raw expiry text) and when the item was first seen.
function metaLine(item) {
  const expiry = item.expires_at
    ? el("span", { class: "expiry", "data-expires": item.expires_at })
    : item.expires && el("span", { class: "expiry" }, `⏳ HSD ${item.expires}`);
  const seen = new Date(item.first_seen);
  const day = `${String(seen.getDate()).padStart(2, "0")}/${String(seen.getMonth() + 1).padStart(2, "0")}`;
  return el("span", { class: "code-meta" }, expiry, expiry && " · ", `thấy ${day}`);
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
      onclick: async () => {
        if (!(await copyText(item.code))) return toast("Không sao chép được, hãy chọn và copy tay");
        copied.add(key);
        store.write(copied);
        button.classList.add("copied");
        action.textContent = "✓ Đã chép";
        toast(`Đã sao chép ${item.code}`);
      },
    },
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
  if (source.ok === null) return el("li", {}, link, " · chưa quét");
  if (!source.ok) return el("li", {}, el("span", { class: "bad" }, "⚠ "), link, ` lỗi: ${source.error}`);
  const locked = source.hidden ? ` · ${source.hidden} cần đăng nhập` : "";
  return el(
    "li",
    {},
    el("span", { class: "ok" }, "✓ "),
    link,
    ` · ${source.count} code${locked} · kiểm tra ${ago(source.checked_at)}`,
  );
}

function gameCard(game) {
  const items = game.items || [];
  const codes = items.filter((i) => i.code);
  const locked = items.length - codes.length;
  const old = game.old || [];
  const copyAll = codes.length > 1 && el(
    "button",
    {
      type: "button",
      class: "btn",
      onclick: async () => {
        if (await copyText(codes.map((c) => c.code).join("\n"))) toast(`Đã sao chép ${codes.length} code`);
      },
    },
    "Sao chép tất cả",
  );
  const redeem = (game.redeem_note || game.redeem_url) && el(
    "p",
    { class: "redeem" },
    game.redeem_note && `Cách nhập: ${game.redeem_note} `,
    game.redeem_url && el("a", { href: game.redeem_url, target: "_blank", rel: "noopener" }, "Xem hướng dẫn"),
  );
  const search = [game.name, ...items.map((i) => i.code || i.title || "")].join(" ").toLowerCase();
  return el(
    "section",
    { class: "game", "data-search": search },
    el(
      "div",
      { class: "game-head" },
      el(
        "h2",
        {},
        game.name,
        " ",
        el("span", { class: "count" }, `${codes.length} code${locked ? ` · ${locked} cần đăng nhập` : ""}`),
      ),
      copyAll,
    ),
    el("ul", { class: "sources" }, game.sources.map(sourceLine)),
    redeem,
    items.length
      ? el("ul", { class: "codes" }, items.map((i) => (i.code ? codeRow(game, i) : lockedRow(i))))
      : el("p", { class: "none" }, "Chưa có code nào đang hoạt động."),
    old.length > 0 && el(
      "details",
      { class: "old" },
      el("summary", {}, `Code không còn trên trang nguồn (${old.length})`),
      el("ul", { class: "codes" }, old.map(oldRow)),
    ),
  );
}

// The most recently found item across all games (items come newest first).
function latestLine(data) {
  let best = null;
  for (const game of data.games) {
    const item = (game.items || [])[0];
    if (item && (!best || item.first_seen > best.item.first_seen)) best = { game, item };
  }
  if (!best) return null;
  const { game, item } = best;
  const name = item.code
    ? el("b", { class: "latest-code" }, item.code)
    : el("a", { href: item.link, target: "_blank", rel: "noopener" }, `🔒 ${item.title || "Sự kiện mới"} (cần đăng nhập)`);
  return el("p", { class: "latest" }, "🆕 Mới nhất: ", name, ` · ${game.name} · thấy ${ago(item.first_seen)}`);
}

function render(data) {
  const meta = document.getElementById("meta");
  meta.replaceChildren(
    `Kiểm tra lúc ${stamp(data.generated_at)}`,
    data.workflow_url ? " · " : "",
    data.workflow_url ? el("a", { href: data.workflow_url, target: "_blank", rel: "noopener" }, "Quét lại ngay") : "",
  );
  const latest = latestLine(data);
  if (latest) meta.after(latest);

  const list = document.getElementById("games");
  list.replaceChildren(...data.games.map(gameCard));
  tick();
  setInterval(tick, 1000);

  const search = document.getElementById("search");
  const empty = document.getElementById("empty");
  if (data.games.length > 3) {
    search.hidden = false;
    search.addEventListener("input", () => {
      const query = search.value.trim().toLowerCase();
      let shown = 0;
      for (const card of list.children) {
        card.hidden = query && !card.dataset.search.includes(query);
        if (!card.hidden) shown += 1;
      }
      empty.hidden = shown > 0;
    });
  }

  document.getElementById("foot").replaceChildren(
    el("p", {}, `Code đổi lần cuối: ${stamp(data.updated_at)}. Trang tự cập nhật mỗi giờ bằng GitHub Actions.`),
    el(
      "p",
      {},
      el("a", { href: "codes.json" }, "Dữ liệu JSON"),
      data.repo_url ? " · " : "",
      data.repo_url ? el("a", { href: data.repo_url, target: "_blank", rel: "noopener" }, "Mã nguồn & cấu hình") : "",
    ),
  );
}

async function load() {
  const embedded = document.getElementById("gcf-data").textContent.trim();
  if (embedded && !embedded.startsWith("__")) return JSON.parse(embedded);
  const response = await fetch("codes.json", { cache: "no-store" });
  return response.json();
}

load()
  .then(render)
  .catch((err) => {
    document.getElementById("meta").textContent = `Không tải được dữ liệu: ${err.message}`;
  });
