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

function codeKey(game, code) {
  return `${game.id}:${code.code}`;
}

function codeRow(game, code) {
  const key = codeKey(game, code);
  const isNew = Date.now() - new Date(code.first_seen) < NEW_FOR_MS;
  const info = [
    code.reward && `🎁 ${code.reward}`,
    code.expires && `⏳ ${code.expires}`,
    `thấy từ ${dayFmt.format(new Date(code.first_seen))}`,
  ].filter(Boolean).join(" · ");
  const action = el("span", { class: "code-action" }, copied.has(key) ? "✓ Đã chép" : "Sao chép");
  const button = el(
    "button",
    {
      type: "button",
      class: `code${copied.has(key) ? " copied" : ""}`,
      title: "Bấm để sao chép",
      onclick: async () => {
        if (!(await copyText(code.code))) return toast("Không sao chép được, hãy chọn và copy tay");
        copied.add(key);
        store.write(copied);
        button.classList.add("copied");
        action.textContent = "✓ Đã chép";
        toast(`Đã sao chép ${code.code}`);
      },
    },
    el(
      "span",
      { class: "code-main" },
      el("span", { class: "code-value" }, code.code, isNew && el("span", { class: "badge" }, "MỚI")),
      el("span", { class: "code-info" }, info),
    ),
    action,
  );
  return el("li", {}, button);
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
  return el(
    "li",
    {},
    el("span", { class: "ok" }, "✓ "),
    link,
    ` · ${source.count} code · kiểm tra ${ago(source.checked_at)}`,
  );
}

function gameCard(game) {
  const active = game.codes.filter((c) => !c.removed_at);
  const old = game.codes.filter((c) => c.removed_at);
  const copyAll = active.length > 1 && el(
    "button",
    {
      type: "button",
      class: "btn",
      onclick: async () => {
        if (await copyText(active.map((c) => c.code).join("\n"))) toast(`Đã sao chép ${active.length} code`);
      },
    },
    "Sao chép tất cả",
  );
  const redeem = (game.redeem_note || game.redeem_url) && el(
    "p",
    { class: "redeem" },
    "Cách nhập: ",
    game.redeem_note || "",
    game.redeem_url && el("a", { href: game.redeem_url, target: "_blank", rel: "noopener" }, game.redeem_note ? " (mở trang)" : "mở trang nhập code"),
  );
  return el(
    "section",
    { class: "game", "data-search": [game.name, ...game.codes.map((c) => c.code)].join(" ").toLowerCase() },
    el(
      "div",
      { class: "game-head" },
      el("h2", {}, game.name, " ", el("span", { class: "count" }, `${active.length} code`)),
      copyAll,
    ),
    el("ul", { class: "sources" }, game.sources.map(sourceLine)),
    redeem,
    active.length
      ? el("ul", { class: "codes" }, active.map((c) => codeRow(game, c)))
      : el("p", { class: "none" }, "Chưa có code nào đang hoạt động."),
    old.length > 0 && el(
      "details",
      { class: "old" },
      el("summary", {}, `Code không còn trên trang nguồn (${old.length})`),
      el("ul", { class: "codes" }, old.map(oldRow)),
    ),
  );
}

function render(data) {
  const meta = document.getElementById("meta");
  meta.replaceChildren(
    `Kiểm tra lúc ${stamp(data.generated_at)}`,
    data.workflow_url ? " · " : "",
    data.workflow_url ? el("a", { href: data.workflow_url, target: "_blank", rel: "noopener" }, "Quét lại ngay") : "",
  );

  const list = document.getElementById("games");
  list.replaceChildren(...data.games.map(gameCard));

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
